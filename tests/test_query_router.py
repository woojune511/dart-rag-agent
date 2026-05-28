import unittest

from src.routing.query_router import QueryRouter


class QueryRouterGuardrailTests(unittest.TestCase):
    def test_numeric_guardrail_keeps_direct_ratio_fact_on_fast_path(self) -> None:
        router = QueryRouter.__new__(QueryRouter)
        semantic_result = {"fast_path": True, "intent": "numeric_fact"}

        self.assertFalse(
            router._blocks_numeric_fast_path("영업이익률은 몇 퍼센트인가요?", semantic_result)
        )
        self.assertFalse(
            router._blocks_numeric_fast_path("각 부문별 매출 비중은 어떻게 되나요?", semantic_result)
        )

    def test_numeric_guardrail_blocks_explicit_calculation_ratio(self) -> None:
        router = QueryRouter.__new__(QueryRouter)
        semantic_result = {"fast_path": True, "intent": "numeric_fact"}

        self.assertTrue(
            router._blocks_numeric_fast_path(
                "2023년 영업비용 중 인건비가 차지하는 비중을 계산해 줘.",
                semantic_result,
            )
        )


if __name__ == "__main__":
    unittest.main()
