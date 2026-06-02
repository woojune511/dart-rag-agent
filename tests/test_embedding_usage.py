import unittest

from src.utils.embedding_usage import (
    TrackingEmbeddings,
    estimate_embedding_cost_usd,
    estimate_embedding_input_tokens,
)


class _FakeEmbeddings:
    def embed_query(self, text):
        return [float(len(text))]

    def embed_documents(self, texts):
        return [[float(len(text))] for text in texts]


class EmbeddingUsageTests(unittest.TestCase):
    def test_tracking_embeddings_records_query_and_document_inputs(self) -> None:
        embeddings = TrackingEmbeddings(_FakeEmbeddings())

        self.assertEqual(embeddings.embed_query("abcd"), [4.0])
        self.assertEqual(embeddings.embed_documents(["abcd", "abcdefgh"]), [[4.0], [8.0]])

        usage = embeddings.snapshot_usage()
        self.assertEqual(usage["embedding_api_calls"], 2)
        self.assertEqual(usage["embedding_text_count"], 3)
        self.assertEqual(usage["embedding_input_chars"], 16)
        self.assertEqual(usage["query_embedding_api_calls"], 1)
        self.assertEqual(usage["query_embedding_text_count"], 1)
        self.assertEqual(usage["document_embedding_api_calls"], 1)
        self.assertEqual(usage["document_embedding_text_count"], 2)

    def test_embedding_cost_uses_explicit_embedding_rate_only(self) -> None:
        usage = {"embedding_estimated_input_tokens": 2_000_000}

        self.assertIsNone(estimate_embedding_cost_usd(usage, {"input_per_million_tokens_usd": 1.0}))
        self.assertEqual(
            estimate_embedding_cost_usd(usage, {"embedding_input_per_million_tokens_usd": 0.5}),
            1.0,
        )

    def test_local_token_estimate_is_nonzero_for_nonempty_text(self) -> None:
        self.assertEqual(estimate_embedding_input_tokens(""), 0)
        self.assertEqual(estimate_embedding_input_tokens("a"), 1)
        self.assertEqual(estimate_embedding_input_tokens("abcd"), 1)
        self.assertEqual(estimate_embedding_input_tokens("abcde"), 2)


if __name__ == "__main__":
    unittest.main()
