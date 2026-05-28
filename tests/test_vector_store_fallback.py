import unittest
from collections import OrderedDict

from langchain_core.documents import Document

from src.storage.vector_store import VectorStoreManager


class _CapacityErrorVectorStore:
    def similarity_search_with_score(self, query, k=4, filter=None):
        raise RuntimeError("429 RESOURCE_EXHAUSTED: Error embedding content")


class _FailIfRetriedVectorStore:
    def __init__(self):
        self.calls = 0

    def similarity_search_with_score(self, query, k=4, filter=None):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED: Error embedding content")
        raise AssertionError("search retried after capacity error")


class _CountVectorStore:
    def __init__(self, results):
        self.calls = 0
        self._results = results

    def similarity_search_with_score(self, query, k=4, filter=None):
        self.calls += 1
        return list(self._results)


class _FlakyAddVectorStore:
    def __init__(self):
        self.calls = 0

    def add_texts(self, texts, metadatas):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("503 UNAVAILABLE: service is currently unavailable")


class _CaptureAddVectorStore:
    def __init__(self):
        self.calls = []

    def add_texts(self, texts, metadatas):
        self.calls.append((list(texts), [dict(metadata) for metadata in metadatas]))


class _SimpleBM25:
    def __init__(self, scores):
        self._scores = scores

    def get_scores(self, tokenized_query):
        return list(self._scores)


class _BrokenHnswVectorStore:
    def similarity_search_with_score(self, query, k=4, filter=None):
        raise RuntimeError("Error sending backfill request to compactor: Error constructing hnsw segment reader: Error loading hnsw index")


class _BrokenGetVectorStore:
    def get(self):
        raise RuntimeError("Error loading hnsw index")


class VectorStoreFallbackTests(unittest.TestCase):
    def _build_manager(self, vector_store, *, docs, metadatas, scores):
        manager = object.__new__(VectorStoreManager)
        manager.vector_store = vector_store
        manager.bm25 = _SimpleBM25(scores)
        manager.bm25_docs = docs
        manager.bm25_metadatas = metadatas
        manager.allow_query_embedding_fallback = True
        manager.vector_capacity_cooldown_sec = 90.0
        manager._vector_capacity_cooldown_until = 0.0
        manager.search_cache_size = 256
        manager._search_cache = OrderedDict()
        manager._structure_graph = {"nodes": {}, "parents": {}, "sections": {}}
        return manager

    def test_search_falls_back_to_bm25_when_embedding_capacity_is_exhausted(self) -> None:
        manager = self._build_manager(
            _CapacityErrorVectorStore(),
            docs=[
                "법인세비용차감전순이익 1,481,396,317,551",
                "다른 문장",
            ],
            metadatas=[
                {"company": "NAVER", "year": 2023, "chunk_uid": "a"},
                {"company": "NAVER", "year": 2023, "chunk_uid": "b"},
            ],
            scores=[3.0, 0.0],
        )

        results = manager.search("법인세비용차감전순이익", k=1, where_filter={"company": "NAVER", "year": 2023})

        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0][0], Document)
        self.assertIn("법인세비용차감전순이익", results[0][0].page_content)

    def test_capacity_error_does_not_retry_unfiltered_vector_search(self) -> None:
        vector_store = _FailIfRetriedVectorStore()
        manager = self._build_manager(
            vector_store,
            docs=["법인세비용차감전순이익 1,481,396,317,551"],
            metadatas=[{"company": "NAVER", "year": 2023, "chunk_uid": "a"}],
            scores=[2.0],
        )

        results = manager.search("법인세비용차감전순이익", k=1, where_filter={"company": "NAVER"})

        self.assertEqual(vector_store.calls, 1)
        self.assertEqual(len(results), 1)

    def test_capacity_error_opens_cooldown_and_skips_next_vector_search(self) -> None:
        vector_store = _FailIfRetriedVectorStore()
        manager = self._build_manager(
            vector_store,
            docs=["법인세비용차감전순이익 1,481,396,317,551"],
            metadatas=[{"company": "NAVER", "year": 2023, "chunk_uid": "a"}],
            scores=[2.0],
        )

        first_results = manager.search("법인세비용차감전순이익", k=1, where_filter={"company": "NAVER"})
        second_results = manager.search("시설투자 총액", k=1, where_filter={"company": "NAVER"})

        self.assertEqual(vector_store.calls, 1)
        self.assertTrue(manager.in_capacity_cooldown())
        self.assertEqual(len(first_results), 1)
        self.assertEqual(len(second_results), 1)

    def test_search_falls_back_to_bm25_when_hnsw_reader_is_unavailable(self) -> None:
        manager = self._build_manager(
            _BrokenHnswVectorStore(),
            docs=["시설투자 총액 531,139억원"],
            metadatas=[{"company": "삼성전자", "year": 2023, "chunk_uid": "capex"}],
            scores=[4.0],
        )

        results = manager.search("시설투자 총액", k=1, where_filter={"company": "삼성전자", "year": 2023})

        self.assertEqual(len(results), 1)
        self.assertIn("531,139", results[0][0].page_content)

    def test_init_bm25_recovers_from_structure_graph_when_chroma_get_fails(self) -> None:
        manager = object.__new__(VectorStoreManager)
        manager.vector_store = _BrokenGetVectorStore()
        manager._structure_graph = {
            "nodes": {
                "chunk-a": {
                    "chunk_uid": "chunk-a",
                    "chunk_id": 1,
                    "sub_chunk_idx": 0,
                    "text": "시설투자 총액 531,139억원",
                    "metadata": {"company": "삼성전자", "year": 2023, "chunk_uid": "chunk-a"},
                }
            }
        }
        manager.bm25 = None
        manager.bm25_docs = []
        manager.bm25_metadatas = []

        manager._init_bm25()

        self.assertIsNotNone(manager.bm25)
        self.assertEqual(manager.bm25_docs, ["시설투자 총액 531,139억원"])
        self.assertEqual(manager.bm25_metadatas[0]["chunk_uid"], "chunk-a")

    def test_validate_vector_index_reports_hnsw_reader_failure_without_bm25_fallback(self) -> None:
        manager = self._build_manager(
            _BrokenHnswVectorStore(),
            docs=["시설투자 총액 531,139억원"],
            metadatas=[{"company": "삼성전자", "year": 2023, "chunk_uid": "capex"}],
            scores=[4.0],
        )

        health = manager.validate_vector_index()

        self.assertFalse(health["ok"])
        self.assertTrue(health["vector_store_read_error"])
        self.assertIn("hnsw", health["error"].lower())

    def test_validate_vector_index_succeeds_when_vector_search_returns_results(self) -> None:
        vector_doc = Document(
            page_content="시설투자 총액 531,139억원",
            metadata={"company": "삼성전자", "year": 2023, "chunk_uid": "capex"},
        )
        manager = self._build_manager(
            _CountVectorStore([(vector_doc, 0.25)]),
            docs=["시설투자 총액 531,139억원"],
            metadatas=[{"company": "삼성전자", "year": 2023, "chunk_uid": "capex"}],
            scores=[1.0],
        )

        health = manager.validate_vector_index()

        self.assertTrue(health["ok"])
        self.assertEqual(health["result_count"], 1)

    def test_add_documents_retries_transient_embedding_failure(self) -> None:
        manager = object.__new__(VectorStoreManager)
        vector_store = _FlakyAddVectorStore()
        manager.vector_store = vector_store
        manager.vector_add_max_retries = 2
        manager.vector_add_retry_sleep_sec = 0.0
        manager._structure_graph = {"nodes": {}, "parents": {}, "sections": {}}
        manager._update_structure_graph = lambda chunks, metadatas: None
        manager._init_bm25 = lambda: None

        result = manager.add_documents(
            ["시설투자 총액 531,139억원"],
            [{"company": "삼성전자", "year": 2023, "chunk_uid": "capex"}],
            batch_size=1,
        )

        self.assertEqual(vector_store.calls, 2)
        self.assertEqual(result["added_chunks"], 1)

    def test_add_documents_strips_large_table_payloads_from_chroma_metadata(self) -> None:
        manager = object.__new__(VectorStoreManager)
        vector_store = _CaptureAddVectorStore()
        manager.vector_store = vector_store
        manager.vector_add_max_retries = 1
        manager.vector_add_retry_sleep_sec = 0.0
        manager._structure_graph = {"nodes": {}, "parents": {}, "sections": {}}
        manager._save_structure_graph = lambda: None
        manager.persist = lambda: None
        manager._init_bm25 = lambda: None

        metadata = {
            "company": "ACME",
            "year": 2023,
            "chunk_uid": "chunk-1",
            "table_summary_text": "summary",
            "table_row_records_json": "[large rows]",
            "table_value_records_json": "[large values]",
            "table_object_json": "{large object}",
        }

        manager.add_documents(["table text"], [metadata], batch_size=1)

        chroma_metadata = vector_store.calls[0][1][0]
        self.assertEqual(chroma_metadata["chunk_uid"], "chunk-1")
        self.assertEqual(chroma_metadata["table_summary_text"], "summary")
        self.assertNotIn("table_row_records_json", chroma_metadata)
        self.assertNotIn("table_value_records_json", chroma_metadata)
        self.assertNotIn("table_object_json", chroma_metadata)
        graph_metadata = manager._structure_graph["nodes"]["chunk-1"]["metadata"]
        self.assertEqual(graph_metadata["table_row_records_json"], "[large rows]")

    def test_search_hydrates_vector_metadata_from_structure_graph(self) -> None:
        vector_doc = Document(page_content="sanitized text", metadata={"chunk_uid": "chunk-1", "company": "ACME"})
        manager = self._build_manager(
            _CountVectorStore([(vector_doc, 0.25)]),
            docs=[],
            metadatas=[],
            scores=[],
        )
        manager._structure_graph = {
            "nodes": {
                "chunk-1": {
                    "text": "full table text",
                    "metadata": {
                        "chunk_uid": "chunk-1",
                        "company": "ACME",
                        "table_row_records_json": "[large rows]",
                    },
                }
            },
            "parents": {},
            "sections": {},
        }

        results = manager.search("table", k=1)

        self.assertEqual(results[0][0].page_content, "full table text")
        self.assertEqual(results[0][0].metadata["table_row_records_json"], "[large rows]")

    def test_search_cache_reuses_previous_results_for_same_query(self) -> None:
        vector_doc = Document(
            page_content="시설투자 총액 531,139억원",
            metadata={"company": "삼성전자", "year": 2023, "chunk_uid": "capex"},
        )
        vector_store = _CountVectorStore([(vector_doc, 0.25)])
        manager = self._build_manager(
            vector_store,
            docs=["시설투자 총액 531,139억원"],
            metadatas=[{"company": "삼성전자", "year": 2023, "chunk_uid": "capex"}],
            scores=[1.0],
        )

        first_results = manager.search("시설투자 총액", k=1, where_filter={"company": "삼성전자"})
        second_results = manager.search("시설투자 총액", k=1, where_filter={"company": "삼성전자"})

        self.assertEqual(vector_store.calls, 1)
        self.assertEqual(len(first_results), 1)
        self.assertEqual(len(second_results), 1)
        self.assertEqual(first_results[0][0].page_content, second_results[0][0].page_content)


if __name__ == "__main__":
    unittest.main()
