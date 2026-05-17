import unittest

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


class _SimpleBM25:
    def __init__(self, scores):
        self._scores = scores

    def get_scores(self, tokenized_query):
        return list(self._scores)


class VectorStoreFallbackTests(unittest.TestCase):
    def _build_manager(self, vector_store, *, docs, metadatas, scores):
        manager = object.__new__(VectorStoreManager)
        manager.vector_store = vector_store
        manager.bm25 = _SimpleBM25(scores)
        manager.bm25_docs = docs
        manager.bm25_metadatas = metadatas
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


if __name__ == "__main__":
    unittest.main()
