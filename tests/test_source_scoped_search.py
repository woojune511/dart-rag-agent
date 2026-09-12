"""Anonymous eligibility-before-top-K regressions; no model or stored corpus."""
from collections import OrderedDict
from copy import deepcopy
import unittest
from unittest.mock import patch
from uuid import uuid4

from langchain_core.documents import Document

from src.agent.financial_source_scope import (
    build_source_section_inventory, resolve_source_section_bindings,
    source_section_applicability,
)
from src.storage.bm25_index import metadata_matches_filter
from src.storage.vector_store import VectorStoreManager
from tests.semantic_program_test_support import _obligation
from tests.test_retrieval_scope_isolation import _Pipeline, _state


def doc(uid, path="Selected notes", receipt="filing-A", **extra):
    return Document(page_content="measurement observations", metadata={
        "chunk_uid": uid, "rcept_no": receipt, "section_path": path,
        "block_type": "paragraph", **extra,
    })


class Scores:
    def __init__(self, count):
        self.count = count

    def get_scores(self, tokens):
        return list(range(self.count, 0, -1))


class Dense:
    def __init__(self, docs, failure=None):
        self.docs, self.failure, self.calls = docs, failure, []

    def similarity_search_with_score(self, query, k, filter=None):
        self.calls.append((query, k, deepcopy(filter)))
        if self.failure:
            raise self.failure
        eligible = [row for row in self.docs if metadata_matches_filter(row.metadata, filter)]
        return [(row, 1.0) for row in eligible[:k]]


class Pipeline(_Pipeline):
    k = 1

    def _supplement_section_seed_docs(self, state):
        # Isolate ordinary search, not recovery from an unrelated supplement.
        return []


def pipeline(docs, *, failure=None, bm25_only=False):
    manager = VectorStoreManager.__new__(VectorStoreManager)
    manager.vector_store = Dense(docs, failure)
    manager.bm25 = Scores(len(docs))
    manager.bm25_docs = [row.page_content for row in docs]
    manager.bm25_metadatas = [deepcopy(row.metadata) for row in docs]
    manager.allow_query_embedding_fallback = True
    manager.force_bm25_only = bm25_only
    manager.vector_capacity_cooldown_sec = 0
    manager._vector_capacity_cooldown_until = 0.0
    manager.search_cache_size = 32
    manager._search_cache = OrderedDict()
    manager._structure_graph = {"nodes": {}, "parents": {}, "sections": {}}
    result = Pipeline()
    result.vsm = manager
    return result


def state(owners=None, **extra):
    return _state(**{
        "query": "Describe measurements.", "topic": "measurements", "companies": [], "years": [],
        "report_scope": {}, "intent": "qa", "query_type": "qa", "format_preference": "paragraph",
        "semantic_plan": {"program_required": True},
        "answer_obligations": owners if owners is not None else [
            _obligation("notes", "narrative", "Measurements", source_sections=["Selected notes"])],
        **extra,
    })


def execute(agent, request):
    plan = agent._build_plan(request)
    searches = agent._execute_searches(request, plan)
    selection = agent._select_evidence(request, plan, searches)
    trace = agent._build_trace(request, plan, searches, selection)
    return searches, selection, trace


def bound_owner(metadata, *, path, receipt="filing-A"):
    inventory = build_source_section_inventory(metadata)
    section = next(row for row in inventory["sections"]
        if row["document_id"] == f"rcept_no:{receipt}" and row["path"] == path.split(" > "))
    owner = _obligation("notes", "narrative", "Measurements", source_section_bindings=[{
        "request_unit_id": "request_001", "requested_text": "Describe measurements",
        "section_ids": [section["section_id"]],
    }])
    return resolve_source_section_bindings([owner], query="Describe measurements.", inventory=inventory)[0]


class SourceScopedSearchTests(unittest.TestCase):
    def test_scope_precedes_dense_lexical_and_rrf_limits(self):
        docs = [doc(f"wrong-{i}", "Other notes") for i in range(24)] + [doc("right")]
        agent, request = pipeline(docs), state()
        original = deepcopy(request)
        searches, selection, trace = execute(agent, request)
        self.assertEqual([row.metadata["chunk_uid"] for row, _ in selection["docs"]], ["right"])
        self.assertEqual([row.metadata["chunk_uid"] for row, _ in selection["seed_docs"]], ["right"])
        self.assertEqual(len(agent.vsm.vector_store.calls), 1)
        applied = searches["executed_queries"][0]["where_filter"]
        self.assertTrue(metadata_matches_filter(docs[-1].metadata, applied))
        self.assertFalse(metadata_matches_filter(docs[0].metadata, applied))
        self.assertEqual(searches["executed_queries"][0]["search_telemetry"]["bm25_result_count"], 1)
        self.assertEqual(trace["retrieval_debug_trace"]["source_scope_search"]["eligible_source_count"], 1)
        self.assertEqual(request, original)

    def test_resolved_scope_is_filing_and_full_branch_qualified(self):
        docs = [doc("same-local", "Notes > Selected", "filing-B"),
                doc("other", "Other > Selected"), doc("same-local", "Notes > Selected"),
                doc("child", "Notes > Selected > Detail")]
        owner = bound_owner([row.metadata for row in docs], path="Notes > Selected")
        searches, _, _ = execute(pipeline(docs), state([owner]))
        self.assertEqual({(row.metadata["rcept_no"], row.metadata["chunk_uid"]) for row, _ in searches["docs"]},
            {("filing-A", "same-local"), ("filing-A", "child")})

    def test_output_union_and_unrestricted_sibling_do_not_widen_owner_authority(self):
        docs = [doc("outside", "Other notes"), doc("notes"), doc("overview", "Overview")]
        notes = state()["answer_obligations"][0]
        overview = _obligation("overview", "narrative", "Overview", source_sections=["Overview"])
        searches, _, _ = execute(pipeline(docs), state([notes, overview]))
        self.assertEqual({row.metadata["chunk_uid"] for row, _ in searches["docs"]}, {"notes", "overview"})
        unrestricted = _obligation("all", "narrative", "Overview")
        searches, _, _ = execute(pipeline(docs), state([notes, unrestricted]))
        self.assertIsNone(searches["executed_queries"][0]["where_filter"])
        self.assertIn("outside", [row.metadata["chunk_uid"] for row, _ in searches["docs"]])
        self.assertEqual(source_section_applicability(docs[0].metadata, notes)["state"], "conflict")

    def test_primary_retry_and_both_caches_share_the_resolved_filter(self):
        docs = [doc("other", "Other notes"), doc("right")]
        agent = pipeline(docs)
        first, _, _ = execute(agent, state(retry_queries=["additional measurements"]))
        self.assertEqual(len(first["executed_queries"]), 2)
        filters = [row["where_filter"] for row in first["executed_queries"]]
        self.assertEqual(filters[0], filters[1])
        cache = first["retrieval_query_result_cache"]
        again, _, _ = execute(agent, state(retry_queries=["additional measurements"], retrieval_query_result_cache=cache))
        self.assertEqual(len(again["reused_queries"]), 2)
        self.assertEqual(len(agent.vsm.vector_store.calls), 2)
        other = _obligation("notes", "narrative", "Measurements", source_sections=["Other notes"])
        different, _, _ = execute(agent, state([other], retrieval_query_result_cache=cache))
        self.assertEqual(different["reused_queries"], [])
        self.assertEqual([row.metadata["chunk_uid"] for row, _ in different["docs"]], ["other"])
        self.assertEqual(len(agent.vsm.vector_store.calls), 3)
        execute(agent, state([other]))  # No phase cache, but the storage cache is scoped too.
        self.assertEqual(len(agent.vsm.vector_store.calls), 3)
        self.assertTrue(agent.vsm.last_search_telemetry["cache_hit"])

    def test_empty_or_unresolved_scope_makes_no_dense_call(self):
        for owner in (state()["answer_obligations"][0],
                      _obligation("notes", "narrative", "Measurements", source_section_bindings=[{"section_ids": []}])):
            with self.subTest(owner=owner):
                agent = pipeline([doc("other", "Other notes")])
                _, selected, trace = execute(agent, state([owner]))
                self.assertEqual(selected["docs"], [])
                self.assertEqual(agent.vsm.vector_store.calls, [])
                self.assertEqual(agent.vsm.last_search_telemetry["vector_skipped_reason"], "empty_source_scope")
                self.assertEqual(trace["retrieval_debug_trace"]["source_scope_search"]["eligible_source_count"], 0)

    def test_bm25_only_and_capacity_fallback_keep_early_scope(self):
        docs = [doc(f"wrong-{i}", "Other notes") for i in range(24)] + [doc("right")]
        for agent in (pipeline(docs, bm25_only=True), pipeline(docs, failure=RuntimeError("429 RESOURCE_EXHAUSTED"))):
            _, selected, _ = execute(agent, state())
            self.assertEqual([row.metadata["chunk_uid"] for row, _ in selected["docs"]], ["right"])
            self.assertLessEqual(len(agent.vsm.vector_store.calls), 1)

    def test_filter_is_deterministic_and_legacy_explicit_id_is_filing_qualified(self):
        docs = [doc("a"), doc("b", receipt="filing-B"), doc("legacy")]
        docs[-1].metadata.pop("chunk_uid")
        docs[-1].metadata["id"] = "record"
        first, _, _ = execute(pipeline(docs), state())
        second, _, _ = execute(pipeline(list(reversed(docs))), state())
        left = first["executed_queries"][0]["where_filter"]
        self.assertEqual(left, second["executed_queries"][0]["where_filter"])
        self.assertTrue(metadata_matches_filter(docs[-1].metadata, left))
        self.assertFalse(metadata_matches_filter({**docs[-1].metadata, "rcept_no": "filing-C"}, left))

    def test_unaddressable_source_is_observable_not_an_unfiltered_search(self):
        unaddressable = doc("unknown")
        unaddressable.metadata.pop("chunk_uid")
        agent = pipeline([unaddressable])
        _, selected, trace = execute(agent, state())
        self.assertEqual(agent.vsm.vector_store.calls, [])
        self.assertEqual(selected["docs"], [])
        self.assertEqual(trace["retrieval_debug_trace"]["source_scope_search"]["unaddressable_source_count"], 1)

    def test_report_filter_and_requirement_intersection_remain_independent(self):
        docs = [doc("wrong-year", year=2041), doc("foreign", receipt="filing-B", year=2042),
                doc("right", year=2042), doc("peer", "Selected notes > Appendix", year=2042)]
        parent = state()["answer_obligations"][0]
        parent["evidence_requirements"] = [{"requirement_id": "input", "source_sections": ["Appendix"]}]
        agent = pipeline(docs)
        request = state([parent], report_scope={"rcept_no": "filing-A", "year": 2042})
        before = deepcopy((request, agent.vsm.bm25_metadatas))
        searches, _, _ = execute(agent, request)
        self.assertEqual({row.metadata["chunk_uid"] for row, _ in searches["docs"]}, {"right", "peer"})
        requirement = parent["evidence_requirements"][0]
        self.assertEqual(source_section_applicability(docs[2].metadata, requirement, parent)["state"], "conflict")
        self.assertEqual(source_section_applicability(docs[3].metadata, requirement, parent)["state"], "match")
        self.assertEqual((request, agent.vsm.bm25_metadatas), before)

    def test_native_chroma_applies_same_union_before_dense_top_k(self):
        import chromadb
        from chromadb.config import Settings

        docs = [doc(f"wrong-{i}", "Other notes") for i in range(24)] + [
            doc("right-A"), doc("right-B", receipt="filing-B")]
        client = chromadb.EphemeralClient(Settings(anonymized_telemetry=False))
        name = "scoped-search-" + uuid4().hex
        collection = client.create_collection(name, embedding_function=None)
        try:
            collection.add(ids=[row.metadata["chunk_uid"] for row in docs],
                documents=[row.page_content for row in docs], metadatas=[row.metadata for row in docs],
                embeddings=[[1.0, 0.0]] * 24 + [[0.0, 1.0], [0.0, 1.0]])
            baseline = collection.query(query_embeddings=[[1.0, 0.0]], n_results=8)
            self.assertTrue(all(uid.startswith("wrong-") for uid in baseline["ids"][0]))

            class NativeDense(Dense):
                def similarity_search_with_score(self, query, k, filter=None):
                    self.calls.append((query, k, deepcopy(filter)))
                    result = collection.query(query_embeddings=[[1.0, 0.0]], where=filter, n_results=k)
                    return [(Document(page_content=text, metadata=metadata), score) for text, metadata, score in zip(
                        result["documents"][0], result["metadatas"][0], result["distances"][0])]

            agent = pipeline(docs)
            agent.vsm.vector_store = NativeDense(docs)
            with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")) as connect:
                searches, selected, _ = execute(agent, state())
            connect.assert_not_called()
            self.assertEqual({row.metadata["chunk_uid"] for row, _ in searches["docs"]}, {"right-A", "right-B"})
            self.assertEqual(len(selected["docs"]), 1)
            telemetry = searches["executed_queries"][0]["search_telemetry"]
            self.assertEqual(telemetry["vector_result_count"], 2)
            self.assertEqual(telemetry["bm25_result_count"], 2)
            self.assertEqual(len(agent.vsm.vector_store.calls), 1)
        finally:
            client.delete_collection(name)


if __name__ == "__main__":
    unittest.main()
