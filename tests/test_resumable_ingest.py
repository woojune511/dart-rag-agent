import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.benchmark_runner import _cache_meta_is_completed
from src.storage.vector_store import VectorStoreManager


class _FakeVectorStore:
    def __init__(self, metadatas=None):
        self.metadatas = list(metadatas or [])
        self.add_calls = []

    def get(self, where=None, limit=None):
        rows = list(self.metadatas)
        if where and "rcept_no" in where:
            rows = [row for row in rows if str(row.get("rcept_no")) == str(where["rcept_no"])]
        if limit is not None:
            rows = rows[:limit]
        return {"ids": [str(i) for i in range(len(rows))], "metadatas": rows}

    def add_texts(self, texts, metadatas):
        self.add_calls.append({"texts": list(texts), "metadatas": list(metadatas)})
        self.metadatas.extend(dict(metadata or {}) for metadata in metadatas)


class ResumableIngestTests(unittest.TestCase):
    def _make_manager(self, existing_metadatas=None):
        manager = VectorStoreManager.__new__(VectorStoreManager)
        manager.vector_store = _FakeVectorStore(existing_metadatas)
        manager._update_structure_graph = Mock()
        manager._init_bm25 = Mock()
        return manager

    def test_add_documents_skips_existing_chunk_uids_when_resume_enabled(self) -> None:
        manager = self._make_manager(
            [{"chunk_uid": "r1::chunk:1", "rcept_no": "r1"}]
        )

        result = manager.add_documents(
            ["old", "new"],
            [
                {"chunk_uid": "r1::chunk:1", "rcept_no": "r1"},
                {"chunk_uid": "r1::chunk:2", "rcept_no": "r1"},
            ],
            resume=True,
            batch_size=8,
        )

        self.assertEqual(result["added_chunks"], 1)
        self.assertEqual(result["skipped_chunks"], 1)
        self.assertEqual(result["batch_count"], 1)
        self.assertEqual(len(manager.vector_store.add_calls), 1)
        self.assertEqual(manager.vector_store.add_calls[0]["texts"], ["new"])
        self.assertEqual(
            [metadata["chunk_uid"] for metadata in manager.vector_store.add_calls[0]["metadatas"]],
            ["r1::chunk:2"],
        )
        manager._update_structure_graph.assert_called_once()
        manager._init_bm25.assert_called_once()

    def test_add_documents_batches_pending_chunks_and_skips_input_duplicates(self) -> None:
        manager = self._make_manager()

        result = manager.add_documents(
            ["a", "b", "dup", "c"],
            [
                {"chunk_uid": "r1::chunk:1", "rcept_no": "r1"},
                {"chunk_uid": "r1::chunk:2", "rcept_no": "r1"},
                {"chunk_uid": "r1::chunk:2", "rcept_no": "r1"},
                {"chunk_uid": "r1::chunk:3", "rcept_no": "r1"},
            ],
            resume=False,
            batch_size=2,
        )

        self.assertEqual(result["added_chunks"], 3)
        self.assertEqual(result["skipped_chunks"], 1)
        self.assertEqual(result["batch_count"], 2)
        self.assertEqual(len(manager.vector_store.add_calls), 2)
        self.assertEqual(manager.vector_store.add_calls[0]["texts"], ["a", "b"])
        self.assertEqual(manager.vector_store.add_calls[1]["texts"], ["c"])
        self.assertEqual(manager._update_structure_graph.call_count, 2)
        manager._init_bm25.assert_called_once()

    def test_cache_meta_completed_distinguishes_in_progress(self) -> None:
        self.assertTrue(_cache_meta_is_completed({"status": "completed"}))
        self.assertTrue(_cache_meta_is_completed({"signature": {"x": 1}}))
        self.assertFalse(_cache_meta_is_completed({"status": "in_progress"}))


if __name__ == "__main__":
    unittest.main()
