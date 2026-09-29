"""Heading ownership survives parsing, persistence, retrieval and answer packets.

Only embeddings and answer generation are synthetic. Chroma, graph sidecars,
BM25, RRF, retrieval caching and SimpleRagAgent packet assembly are exercised.
"""
from collections import OrderedDict
from contextlib import closing
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from langchain_core.documents import Document
from src.agent.simple_rag import SimpleRagAgent
from src.config.simple_rag import RagAnswer
from src.ops import build_parser_store_successor as builder
from src.ops.plan_parser_store_successor import parse_source_projection
from src.storage.graph_persistence import load_structure_graph, persist_structure_graph
from src.storage.metadata_payloads import compact_node_for_storage, load_table_payloads, metadata_for_chroma
from src.storage.store_manifest import canonical_store_manifest
from src.storage.structure_graph import empty_structure_graph, update_structure_graph
from src.storage.vector_store import VectorStoreManager


class PacketRecorder:
    def __init__(self):
        self.packets = []

    def with_structured_output(self, schema):
        assert schema is RagAnswer
        return self

    def invoke(self, messages):
        packet = json.loads(messages[1][1])
        self.packets.append(packet)
        return RagAnswer(answer="Fixture only", cited_source_ids=[packet["documents"][0]["source_id"]], abstained=False)


class HeadingScopeDeliveryTests(unittest.TestCase):
    def setUp(self):
        for name in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
            self.enterContext(patch(name, side_effect=AssertionError("Provider-free test")))

    def exercise(self, boundary, *, expected="나. Issuer topic", forbidden="Birch"):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "filing.xml"
            source.write_text(
                '<DOCUMENT><SECTION-1><TITLE ATOC="Y">I. 회사의 개요</TITLE>'
                '<SECTION-2><TITLE ATOC="Y">1. 회사의 개요</TITLE>'
                '<P>가. Group topic</P><P>[Birch]</P><P>Birch description.</P>'
                '<TABLE><TR><TD>birchwitness</TD><TD>17</TD></TR></TABLE>'
                + boundary +
                '<TABLE><TR><TD>issuerwitness</TD><TD>29</TD></TR></TABLE>'
                '</SECTION-2></SECTION-1></DOCUMENT>', encoding="utf8")
            manifest = canonical_store_manifest(collection_name="heading_delivery", embedding_dimension=3)
            chunks, texts, _, _ = parse_source_projection(
                [{"source_file": str(source), "metadata": {"rcept_no": "fixture", "company": "Issuer", "year": 2040}}], manifest)
            metadata = [c.metadata for c in chunks]
            graph = update_structure_graph(empty_structure_graph(), texts, metadata,
                                           chunk_uid_from_metadata=lambda m: m["chunk_uid"])
            graph_path, payload_path = root / "graph.json", root / "payloads.json"
            persist_structure_graph(graph_path, payload_path, graph, compact_node_for_storage=compact_node_for_storage)
            # Reload actual persisted metadata; do not reuse parser objects.
            graph = load_structure_graph(graph_path)
            table_metadata = next(m for m,t in zip(metadata,texts) if "issuerwitness" in t)
            self.assertEqual(table_metadata["local_heading"], expected)
            self.assertIn("29", next(t for t in texts if "issuerwitness" in t))
            self.assertFalse(any("birchwitness" in t and "issuerwitness" in t for t in texts))

            vectors = [[1.,0.,0.] if "issuerwitness" in t else [0.,1.,0.] if "birchwitness" in t else [0.,0.,1.] for t in texts]
            with closing(builder._client(root / "chroma")) as client:
                col = client.create_collection(manifest.collection_name, embedding_function=None)
                col.add(ids=[m["chunk_uid"] for m in metadata], documents=texts,
                        metadatas=[metadata_for_chroma(m) for m in metadata], embeddings=vectors)
            with closing(builder._client(root / "chroma")) as client:
                col = client.get_collection(manifest.collection_name, embedding_function=None)
                dense_calls = []
                def dense(query, *, k, filter):
                    dense_calls.append(query)
                    vector = [1.,0.,0.] if query == "issuerwitness" else [0.,1.,0.]
                    reply = col.query(query_embeddings=[vector], n_results=min(k,len(texts)), where=filter)
                    return [(Document(page_content=t,metadata=m),float(d)) for t,m,d in
                            zip(reply["documents"][0],reply["metadatas"][0],reply["distances"][0])]
                store = VectorStoreManager.__new__(VectorStoreManager)
                store.vector_store = SimpleNamespace(similarity_search_with_score=dense)
                store.embeddings = None
                store.force_bm25_only = False
                store.allow_query_embedding_fallback = False
                store._vector_capacity_cooldown_until = 0
                store._structure_graph = graph
                store._table_payloads = load_table_payloads(payload_path)
                store._search_cache = OrderedDict()
                store._search_cache_telemetry = {}
                store.search_cache_size = 16
                docs, metadatas = store._structure_graph_bm25_payload()
                store._build_bm25_index(docs, metadatas)
                recorder = PacketRecorder()
                with patch.object(SimpleRagAgent,"_build_llm_routes",return_value={"default":recorder}):
                    agent = SimpleRagAgent(store,k=1)
                for query in ("birchwitness","issuerwitness","birchwitness","issuerwitness"):
                    result = agent.run(query,report_scope={"rcept_no":"fixture"},include_review_trace=True)
                    packet = recorder.packets[-1]
                    document, = packet["documents"]
                    self.assertIn(query,document["text"])
                    if query == "issuerwitness":
                        self.assertEqual(document["context"]["local_heading"],expected)
                        if forbidden:
                            self.assertNotIn(forbidden,json.dumps(document,ensure_ascii=False))
                    else:
                        self.assertIn("[Birch]",document["context"]["local_heading"])
                    cited, = result.agent_answer["cited_sources"]
                    self.assertEqual(cited["context"],document["context"])
                    self.assertEqual(cited["text"],document["text"])
                self.assertEqual(dense_calls,["birchwitness","issuerwitness"])
                self.assertEqual(recorder.packets[1],recorder.packets[3])
                self.assertTrue(store.last_search_telemetry["cache_hit"])

    def test_plain_peer_does_not_inherit_previous_subject_through_cached_search(self):
        self.exercise('<P>나. Issuer topic</P><P>Issuer description.</P>')

    def test_inline_bold_peer_does_not_inherit_previous_subject(self):
        self.exercise('<P><SPAN USERMARK="B">나. Issuer topic</SPAN>Issuer description.</P>')

    def test_inherited_bold_peer_survives_persistence_and_cached_search(self):
        self.exercise('<P USERMARK=" B">나. Issuer topic'
                      '<SPAN USERMARK=" !B">Issuer description.</SPAN></P>')

    def test_true_child_preserves_named_subject_through_delivery(self):
        self.exercise('<P>(1) Child topic</P><P>Child description.</P>',
                      expected="가. Group topic > [Birch] > (1) Child topic", forbidden=None)


if __name__ == "__main__":
    unittest.main()
