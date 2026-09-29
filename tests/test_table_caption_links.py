from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from langchain_core.documents import Document
from lxml import etree

from src.agent.simple_rag import SimpleRagAgent
from src.ops.build_table_caption_links import build_sidecar, main
from src.processing.table_caption_links import build_report_caption_links, caption_labels
from src.processing.table_structure import build_table_object
from src.storage.graph_persistence import persist_structure_graph
from src.storage.metadata_payloads import compact_node_for_storage
from src.storage.structure_graph import update_structure_graph
from src.storage.table_caption_links import CAPTION_LINK_FILENAME, get_caption_doc, load_caption_links
from src.storage.vector_store import VectorStoreManager
from tests.test_simple_rag import LLM, Store, hit


XML = '''<DOCUMENT><BODY><TABLE-GROUP>
<TABLE><TR><TD>(기준일 :</TD><TD>2040년 12월 31일</TD><TD>)</TD><TD>(단위 : 주)</TD></TR></TABLE>
<TABLE><TR><TD>종류</TD><TD>수량</TD></TR><TR><TD>A</TD><TD>100</TD></TR><TR><TD>B</TD><TD>20</TD></TR></TABLE>
</TABLE-GROUP></BODY></DOCUMENT>'''


def fixture():
    raw = XML.encode()
    digest = hashlib.sha256(raw).hexdigest()
    root = etree.fromstring(raw)
    texts, metadatas = [], []
    for index, table in enumerate(root.iter('TABLE')):
        obj = build_table_object(table)
        obj['source_document_sha256'] = digest
        texts.append('[source]\n\n' + obj['table_text'])
        metadatas.append(dict(chunk_uid=('c', 't')[index], rcept_no='r', parent_id='p',
                              chunk_id=index, sub_chunk_idx=index, block_type='table',
                              table_object_json=json.dumps(obj, ensure_ascii=False)))
    graph = update_structure_graph({}, texts, metadatas, lambda m: m['chunk_uid'])
    return root, digest, graph


class CaptionLinkTests(unittest.TestCase):
    def setUp(self):
        self.network = patch('socket.socket.connect', side_effect=AssertionError('network forbidden'))
        self.network.start(); self.addCleanup(self.network.stop)
        self.root, self.digest, self.graph = fixture()

    def build(self):
        return build_report_caption_links(self.root, self.digest, 'r', self.graph, dict)

    def document(self, uid='t'):
        node = self.graph['nodes'][uid]
        return Document(page_content=node['text'], metadata=deepcopy(node['metadata']))

    def test_exact_four_column_pair_preserves_sources(self):
        before = deepcopy(self.graph)
        links = self.build()['links']
        self.assertEqual(list(links), ['t'])
        caption = get_caption_doc(self.graph, links, self.document(), dict)
        self.assertEqual(caption, self.document('c'))
        caption.metadata['rcept_no'] = 'changed'
        self.assertEqual(self.graph, before)

    def test_rejects_mixed_invalid_or_duplicate_labels(self):
        for text in ['(단위:123원)', '본문 (단위:원)', '(단위:원)(단위:주)',
                     '(기준일:2040년2월30일)', '(단위:주) 100']:
            with self.subTest(text=text):
                self.assertIsNone(caption_labels(dict(table_text=text, row_count=1, column_count=4)))
        self.assertIsNone(caption_labels(dict(table_text='(단위:주)', row_count=1, column_count=9)))

    def test_intervening_paragraph_or_tail_prevents_link(self):
        group = next(self.root.iter('TABLE-GROUP'))
        group[0].tail = 'unrelated prose'
        self.assertFalse(self.build()['links'])
        group[0].tail = None
        group.insert(1, etree.Element('P'))
        self.assertFalse(self.build()['links'])

    def test_duplicate_raw_table_or_stored_view_is_ambiguous(self):
        original = deepcopy(self.root)
        self.root.append(deepcopy(list(self.root.iter('TABLE'))[1]))
        self.assertFalse(self.build()['links'])
        self.root = original
        other = deepcopy(self.graph['nodes']['t']); other['chunk_uid'] = 't2'
        self.graph['nodes']['t2'] = other
        self.assertFalse(self.build()['links'])

    def test_wrong_scope_heading_body_or_locator_is_excluded(self):
        for kind in ['parent', 'receipt', 'body', 'locator', 'hash']:
            with self.subTest(kind=kind):
                self.root, self.digest, self.graph = fixture()
                node = self.graph['nodes']['c']
                if kind == 'parent':node['parent_id'] = 'other'
                if kind == 'receipt':node['metadata']['rcept_no'] = 'other'
                if kind == 'body':node['text'] += '\nunrelated paragraph'
                if kind in {'locator', 'hash'}:
                    obj = json.loads(node['metadata']['table_object_json'])
                    obj['source_table_locator' if kind == 'locator' else 'source_document_sha256'] = 'wrong'
                    node['metadata']['table_object_json'] = json.dumps(obj)
                self.assertFalse(self.build()['links'])

    def test_stale_deleted_or_changed_binding_fails_closed(self):
        for kind in ['body', 'metadata', 'parent', 'delete', 'selected']:
            with self.subTest(kind=kind):
                self.root, self.digest, self.graph = fixture()
                links = self.build()['links']; doc = self.document()
                if kind == 'body':self.graph['nodes']['c']['text'] += 'changed'
                if kind == 'metadata':self.graph['nodes']['c']['metadata']['year'] = 2041
                if kind == 'parent':self.graph['nodes']['t']['parent_id'] = 'other'
                if kind == 'delete':del self.graph['nodes']['c']
                if kind == 'selected':doc.page_content += 'changed'
                with self.assertRaises(ValueError):get_caption_doc(self.graph, links, doc, dict)

    def test_build_save_reload_and_real_manager_delivery(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp); raw = folder/'report.xml'; raw.write_bytes(XML.encode('utf8'))
            persist_structure_graph(folder/'document_structure_graph.json', folder/'table_payloads.json',
                                    self.graph, compact_node_for_storage=compact_node_for_storage)
            before = {p.name: p.read_bytes() for p in folder.iterdir()}
            result = build_sidecar(folder, {'r': str(raw)})
            sidecar = folder/CAPTION_LINK_FILENAME
            sidecar.write_text(json.dumps(result), encoding='utf8')
            self.assertEqual(load_caption_links(sidecar), result['links'])
            with (patch('src.storage.vector_store._chroma_cls', return_value=lambda **kw: object()),
                  patch('src.storage.vector_store.create_embeddings', side_effect=AssertionError('provider forbidden')),
                  patch.object(VectorStoreManager, '_init_bm25')):
                manager = VectorStoreManager(persist_directory=tmp, force_bm25_only=True,
                                             experimental_caption_links_path=sidecar)
            table = manager.get_structure_node('t')
            doc = Document(page_content=table['text'], metadata=table['metadata'])
            caption = manager.get_table_caption_doc(doc)
            self.assertEqual(caption.page_content, self.document('c').page_content)
            manager.search = lambda *args, **kwargs: [(doc, .5)]
            model = LLM()
            with patch.object(SimpleRagAgent, '_build_llm_routes', return_value={'default': model}):
                response = SimpleRagAgent(manager).run('q', report_scope={'rcept_no': 'r'}, include_review_trace=True)
            docs = json.loads(model.calls[0][1][1])['documents']
            self.assertEqual([d['chunk_id'] for d in docs], ['c', 't'])
            self.assertEqual(docs[1]['text'], doc.page_content)
            self.assertEqual(response.review_trace['retrieval_debug_trace']['caption_bundles'][0]['caption_chunk_id'], 'c')
            self.assertEqual({name:(folder/name).read_bytes() for name in before}, before)
            with self.assertRaises(FileExistsError):
                main(['--store-dir', tmp, '--reports-json', str(raw), '--output', str(sidecar)])
            raw.write_text(XML+' ', encoding='utf8')
            with self.assertRaises(ValueError):build_sidecar(folder, {'r': str(raw)})

    def test_default_manager_ignores_present_experimental_sidecar(self):
        for content in [json.dumps(self.build()), '{malformed']:
            with self.subTest(content=content[:20]), TemporaryDirectory() as tmp:
                folder = Path(tmp)
                persist_structure_graph(folder/'document_structure_graph.json', folder/'table_payloads.json',
                                        self.graph, compact_node_for_storage=compact_node_for_storage)
                (folder/CAPTION_LINK_FILENAME).write_text(content, encoding='utf8')
                before = {p.name:p.read_bytes() for p in folder.iterdir()}
                with (patch('src.storage.vector_store._chroma_cls', return_value=lambda **kw: object()),
                      patch('src.storage.vector_store.create_embeddings', side_effect=AssertionError('provider forbidden')),
                      patch('src.storage.vector_store.load_caption_links', side_effect=AssertionError('default reads experiment')),
                      patch.object(VectorStoreManager, '_init_bm25')):
                    manager = VectorStoreManager(persist_directory=tmp, force_bm25_only=True)
                node = manager.get_structure_node('t')
                doc = Document(page_content=node['text'], metadata=node['metadata'])
                self.assertIsNone(manager.get_table_caption_doc(doc))
                manager.search = lambda *args, **kwargs: [(doc, .5)]
                model = LLM()
                with patch.object(SimpleRagAgent, '_build_llm_routes', return_value={'default':model}):
                    response = SimpleRagAgent(manager).run('q', report_scope={'rcept_no':'r'}, include_review_trace=True)
                docs = json.loads(model.calls[0][1][1])['documents']
                self.assertEqual([d['chunk_id'] for d in docs], ['t'])
                self.assertNotIn('caption_bundles', response.review_trace['retrieval_debug_trace'])
                self.assertEqual({p.name:p.read_bytes() for p in folder.iterdir()}, before)

    def test_invalid_explicit_sidecar_stops_before_store_or_provider_construction(self):
        with TemporaryDirectory() as tmp:
            malformed = Path(tmp)/'bad.json'
            malformed.write_text('{malformed', encoding='utf8')
            for path in ['', False, Path(tmp)/'missing.json', malformed]:
                with (self.subTest(path=path),
                      patch('src.storage.vector_store._chroma_cls') as chroma,
                      patch('src.storage.vector_store.create_embeddings') as embeddings,
                      self.assertRaises(ValueError)):
                    VectorStoreManager(persist_directory=str(Path(tmp)/'unused'),
                                       experimental_caption_links_path=path)
                chroma.assert_not_called(); embeddings.assert_not_called()
                self.assertFalse((Path(tmp)/'unused').exists())

    def test_absent_or_malformed_sidecar(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/CAPTION_LINK_FILENAME
            self.assertEqual(load_caption_links(path), {})
            for payload in [{'version':True,'links':{}}, {'version':1,'links':{'t':{}}}, []]:
                path.write_text(json.dumps(payload), encoding='utf8')
                with self.assertRaises(ValueError):load_caption_links(path)

    def test_cached_bm25_search_still_revalidates_caption(self):
        # With only two documents, a term in one document has zero BM25 IDF.
        self.graph['nodes']['u'] = dict(chunk_uid='u', text='unrelated note', parent_id='other',
                                       metadata=dict(chunk_uid='u', rcept_no='r', parent_id='other'))
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            persist_structure_graph(folder/'document_structure_graph.json', folder/'table_payloads.json',
                                    self.graph, compact_node_for_storage=compact_node_for_storage)
            (folder/CAPTION_LINK_FILENAME).write_text(json.dumps(self.build()), encoding='utf8')
            with (patch('src.storage.vector_store._chroma_cls', return_value=lambda **kw: object()),
                  patch('src.storage.vector_store.create_embeddings', side_effect=AssertionError('provider forbidden'))):
                manager = VectorStoreManager(persist_directory=tmp, force_bm25_only=True,
                                             experimental_caption_links_path=folder/CAPTION_LINK_FILENAME)
            first = manager.search('수량', k=8, where_filter={'rcept_no':'r'})
            second = manager.search('수량', k=8, where_filter={'rcept_no':'r'})
            self.assertEqual(first, second)
            self.assertEqual(manager.last_search_telemetry['retrieval_mode'], 'cache')
            table = next(doc for doc, score in second if doc.metadata['chunk_uid'] == 't')
            self.assertEqual(manager.get_table_caption_doc(table).metadata['chunk_uid'], 'c')
            manager._structure_graph['nodes']['c']['text'] += 'changed'
            with self.assertRaises(ValueError):manager.get_table_caption_doc(table)


class CaptionPacketTests(unittest.TestCase):
    def run_packet(self, hits, *, max_bytes=65536, caption=None, scope=None):
        self.store = Store(hits)
        bound_caption = hit(chunk='caption', text='As of 2040; units')[0] if caption is None else caption
        self.store.get_table_caption_doc = lambda doc: bound_caption if doc.metadata['chunk_uid'] == 'table' else None
        self.model = LLM()
        with patch.object(SimpleRagAgent, '_build_llm_routes', return_value={'default': self.model}):
            return SimpleRagAgent(self.store, max_context_bytes=max_bytes).run('q', report_scope=scope, include_review_trace=True)

    def test_duplicate_caption_kept_once_without_losing_other_hits(self):
        hits = [hit(chunk='table'), hit(chunk='other'), hit(chunk='caption', text='As of 2040; units')]
        result = self.run_packet(hits)
        docs = result.review_trace['retrieved_sources']
        self.assertEqual([d['chunk_id'] for d in docs], ['caption','table','other'])
        self.assertIsNone(docs[0]['score'])
        self.assertEqual(len(self.store.calls), 1); self.assertEqual(len(self.model.calls), 1)

    def test_count_and_byte_overflow_stop_before_generation(self):
        for hits, maximum in [([hit(chunk='table')]+[hit(chunk=str(i)) for i in range(7)], 65536),
                              ([hit(chunk='table'), hit(chunk='large', text='x'*2000)], 800)]:
            with self.subTest(maximum=maximum), self.assertRaisesRegex(ValueError,'Whole caption bundle'):
                self.run_packet(hits, max_bytes=maximum)
            self.assertEqual(self.model.calls, [])

    def test_scope_and_source_conflicts_are_not_repaired(self):
        for cap, hits, scope in [
            (hit(receipt='r2', chunk='caption')[0], [hit(chunk='table')], None),
            (hit(company='Other', chunk='caption')[0], [hit(chunk='table')], {'company':'Issuer'}),
            (None, [hit(chunk='table'),hit(chunk='caption',text='conflict')], None),
        ]:
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                self.run_packet(hits, caption=cap, scope=scope)
            self.assertEqual(self.model.calls, [])


if __name__ == '__main__':
    unittest.main()
