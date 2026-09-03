import sys
import json
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.routing.query_router import QueryRouter


class _ExplodingEmbeddings:
    def embed_documents(self, _queries):
        raise AssertionError("semantic router should be disabled")

    def embed_query(self, _query):
        raise AssertionError("semantic router should be disabled")


class _ExplodingLLM:
    def with_structured_output(self, _schema):
        raise AssertionError("LLM fallback should be disabled")


class _CountingEmbeddings:
    def __init__(self):
        self.document_calls = 0

    def embed_documents(self, queries):
        self.document_calls += 1
        return [[1.0, 0.0] for _query in queries]

    def embed_query(self, _query):
        return [1.0, 0.0]


class QueryRouterLowApiTests(unittest.TestCase):
    def test_disabled_semantic_and_llm_router_uses_heuristic_fallback(self) -> None:
        router = QueryRouter(
            embeddings=_ExplodingEmbeddings(),
            llm=_ExplodingLLM(),
            enable_semantic_router=False,
            enable_llm_fallback=False,
        )

        result = router.route("두 값을 더해 합계를 계산해 줘.")

        self.assertEqual(result.routing_source, "heuristic_fallback")
        self.assertEqual(result.intent, "comparison")
        self.assertEqual(result.format_preference, "table")

    def test_canonical_embeddings_are_cached_by_file_and_embedding_spec(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            canonical_path = Path(temporary_directory) / "canonical.json"
            canonical_path.write_text(
                json.dumps([{"id": "qa", "queries": ["sample question"]}]),
                encoding="utf-8",
            )
            first_embeddings = _CountingEmbeddings()
            second_embeddings = _CountingEmbeddings()
            spec = {
                "provider": "test",
                "model_name": "deterministic",
                "dimension": 2,
            }

            first = QueryRouter(
                embeddings=first_embeddings,
                llm=_ExplodingLLM(),
                canonical_queries_path=canonical_path,
                embedding_spec=spec,
                enable_llm_fallback=False,
            )
            second = QueryRouter(
                embeddings=second_embeddings,
                llm=_ExplodingLLM(),
                canonical_queries_path=canonical_path,
                embedding_spec=spec,
                enable_llm_fallback=False,
            )

        self.assertTrue(first._semantic_router["enabled"])
        self.assertTrue(second._semantic_router["enabled"])
        self.assertEqual(first_embeddings.document_calls, 1)
        self.assertEqual(second_embeddings.document_calls, 0)


if __name__ == "__main__":
    unittest.main()
