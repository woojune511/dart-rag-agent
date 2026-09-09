"""Provider-free scope and failure checks with unrelated synthetic sources."""

from collections import OrderedDict
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from langchain_core.documents import Document

from src.storage.bm25_index import collect_bm25_results
from src.storage.vector_store import VectorStoreManager
from src.utils.provider_errors import ProviderAdmissionError


def _manager(vector_store, *, fallback=False):
    manager = VectorStoreManager.__new__(VectorStoreManager)
    manager.vector_store = vector_store
    manager.force_bm25_only = False
    manager.allow_query_embedding_fallback = fallback
    manager._vector_capacity_cooldown_until = 0.0
    manager.vector_capacity_cooldown_sec = 0.0
    manager.bm25 = None
    manager.bm25_docs = []
    manager.bm25_metadatas = []
    manager.search_cache_size = 16
    manager._search_cache = OrderedDict()
    manager._structure_graph = {"nodes": {}}
    return manager


class StorageFailureBoundariesTests(unittest.TestCase):
    def test_filtered_search_error_never_widens_scope_or_populates_cache(self):
        failure = ValueError("unsupported filter")
        foreign = Document(page_content="unrelated source", metadata={"rcept_no": "other"})
        for fallback in (False, True):
            with self.subTest(fallback=fallback):
                backend = Mock()
                backend.similarity_search_with_score.side_effect = [failure, [(foreign, 0.1)]]
                manager = _manager(backend, fallback=fallback)
                with self.assertRaises(ValueError) as caught:
                    manager.search("generic question", k=1, where_filter={"rcept_no": "requested"})
                self.assertIs(caught.exception, failure)
                backend.similarity_search_with_score.assert_called_once_with(
                    "generic question", k=2, filter={"rcept_no": "requested"},
                )
                self.assertFalse(manager._search_cache)

    def test_admission_error_is_terminal_even_when_message_looks_retryable(self):
        for message in ("budget denied", "429 resource_exhausted"):
            with self.subTest(message=message):
                failure = ProviderAdmissionError("budget_exceeded", message)
                backend = Mock()
                backend.similarity_search_with_score.side_effect = failure
                manager = _manager(backend, fallback=True)
                with self.assertRaises(ProviderAdmissionError) as caught:
                    manager.search("generic question", where_filter={"year": 2031})
                self.assertIs(caught.exception, failure)
                self.assertEqual(backend.similarity_search_with_score.call_count, 1)
                self.assertFalse(manager._search_cache)

    def test_bm25_filters_before_top_n_so_other_sources_cannot_displace_hits(self):
        for reverse in (False, True):
            rows = [(f"foreign-{i}", 20 - i, "other") for i in range(9)]
            rows += [("wanted-high", 2, "requested"), ("wanted-low", 1, "requested")]
            if reverse:
                rows.reverse()
            with self.subTest(reverse=reverse):
                results = collect_bm25_results(
                    SimpleNamespace(get_scores=lambda _query: [row[1] for row in rows]),
                    [row[0] for row in rows],
                    [{"rcept_no": row[2]} for row in rows],
                    "question", k=1, where_filter={"rcept_no": "requested"},
                )
                self.assertEqual([doc.page_content for doc, _ in results], ["wanted-high", "wanted-low"])

    def test_bm25_preserves_positive_ranked_breadth_when_unfiltered(self):
        results = collect_bm25_results(
            SimpleNamespace(get_scores=lambda _query: [1, 4, 0, 3, 2]),
            ["a", "b", "c", "d", "e"], [{} for _ in range(5)], "q", k=1,
        )
        self.assertEqual([doc.page_content for doc, _ in results], ["b", "d", "e"])

    def test_explicit_backend_persist_failure_propagates(self):
        failure = OSError("synthetic disk failure")
        backend = Mock()
        backend.persist.side_effect = failure
        manager = _manager(backend)
        with self.assertRaises(OSError) as caught:
            manager.persist()
        self.assertIs(caught.exception, failure)

    def test_backend_without_manual_persist_remains_supported(self):
        _manager(SimpleNamespace()).persist()

    def test_vector_add_cannot_retry_terminal_admission_error(self):
        failure = ProviderAdmissionError("budget_exceeded", "429 resource_exhausted")
        backend = Mock()
        backend.add_texts.side_effect = failure
        manager = _manager(backend)
        manager.vector_add_max_retries = 4
        manager.vector_add_retry_sleep_sec = 0
        with self.assertRaises(ProviderAdmissionError) as caught:
            manager._add_one_vector_batch(
                batch_texts=["source"], chroma_metadatas=[{"chunk_uid": "a"}],
                batch_index=1, total_batches=1,
            )
        self.assertIs(caught.exception, failure)
        self.assertEqual(backend.add_texts.call_count, 1)

    def test_search_cache_does_not_share_documents_with_callers(self):
        backend = Mock()
        backend.similarity_search_with_score.return_value = [(
            Document(page_content="original", metadata={"chunk_uid": "a", "nested": {"scope": "original"}}), 0.1,
        )]
        manager = _manager(backend)
        first = manager.search("same query", k=1)
        first[0][0].page_content = "mutated first result"
        first[0][0].metadata["nested"]["scope"] = "mutated"
        second = manager.search("same query", k=1)
        self.assertEqual(second[0][0].page_content, "original")
        self.assertEqual(second[0][0].metadata["nested"]["scope"], "original")
        second[0][0].page_content = "mutated cache hit"
        self.assertEqual(manager.search("same query", k=1)[0][0].page_content, "original")
        self.assertEqual(backend.similarity_search_with_score.call_count, 1)

    def test_graph_commit_invalidates_cache_but_failed_commit_preserves_it(self):
        with TemporaryDirectory() as directory:
            backend = Mock()
            backend.similarity_search_with_score.return_value = [(
                Document(page_content="stored", metadata={"chunk_uid": "a"}), 0.1,
            )]
            manager = _manager(backend)
            manager._graph_path = Path(directory) / "graph.json"
            manager._table_payloads_path = Path(directory) / "payloads.json"
            manager._table_payloads = {}
            manager._update_structure_graph(["original"], [{"chunk_uid": "a"}])
            manager.search("same query", k=1)
            with patch("src.storage.graph_persistence.atomic_write_json", side_effect=OSError("write failure")):
                with self.assertRaises(OSError):
                    manager._update_structure_graph(["uncommitted"], [{"chunk_uid": "a"}])
            self.assertEqual(manager.search("same query", k=1)[0][0].page_content, "original")
            self.assertEqual(backend.similarity_search_with_score.call_count, 1)
            manager._update_structure_graph(["committed successor"], [{"chunk_uid": "a"}])
            self.assertFalse(manager._search_cache)
            self.assertFalse(manager._search_cache_telemetry)
            self.assertEqual(manager.search("same query", k=1)[0][0].page_content, "committed successor")
            self.assertEqual(backend.similarity_search_with_score.call_count, 2)


if __name__ == "__main__":
    unittest.main()
