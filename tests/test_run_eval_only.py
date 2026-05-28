import unittest
from unittest.mock import patch

from src.ops.run_eval_only import _validate_store_for_eval_only


class _FakeVectorStoreManager:
    health = {"ok": True, "result_count": 1}
    init_kwargs = None

    def __init__(self, **kwargs):
        type(self).init_kwargs = dict(kwargs)

    def validate_vector_index(self):
        return dict(type(self).health)


class RunEvalOnlyTests(unittest.TestCase):
    def setUp(self) -> None:
        _FakeVectorStoreManager.health = {"ok": True, "result_count": 1}
        _FakeVectorStoreManager.init_kwargs = None

    def test_validate_store_for_eval_only_fails_strict_on_broken_vector_index(self) -> None:
        _FakeVectorStoreManager.health = {
            "ok": False,
            "error": "Error loading hnsw index",
            "vector_store_read_error": True,
            "embedding_capacity_error": False,
        }
        store_info = {
            "persist_directory": "benchmarks/results/example/store",
            "collection_name": "dart_reports_v2_example",
            "embedding_provider": "google",
            "embedding_model_name": "models/gemini-embedding-2",
        }

        with patch("src.ops.run_eval_only.VectorStoreManager", _FakeVectorStoreManager):
            with self.assertRaisesRegex(RuntimeError, "Vector store health check failed"):
                _validate_store_for_eval_only(store_info, allow_degraded_retrieval=False)

        self.assertFalse(_FakeVectorStoreManager.init_kwargs["allow_query_embedding_fallback"])

    def test_validate_store_for_eval_only_allows_degraded_diagnostic_mode(self) -> None:
        _FakeVectorStoreManager.health = {
            "ok": False,
            "error": "Error loading hnsw index",
            "vector_store_read_error": True,
            "embedding_capacity_error": False,
        }
        store_info = {
            "persist_directory": "benchmarks/results/example/store",
            "collection_name": "dart_reports_v2_example",
            "embedding_provider": "google",
            "embedding_model_name": "models/gemini-embedding-2",
        }

        with patch("src.ops.run_eval_only.VectorStoreManager", _FakeVectorStoreManager):
            health = _validate_store_for_eval_only(store_info, allow_degraded_retrieval=True)

        self.assertFalse(health["ok"])
        self.assertTrue(_FakeVectorStoreManager.init_kwargs["allow_query_embedding_fallback"])


if __name__ == "__main__":
    unittest.main()
