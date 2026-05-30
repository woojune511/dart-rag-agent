import sys
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


if __name__ == "__main__":
    unittest.main()
