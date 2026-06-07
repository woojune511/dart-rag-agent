import unittest

from src.agent.financial_graph_reconciliation import (
    ALLOWED_REFLECTION_RETRY_STRATEGIES,
    _normalise_reflection_plan_record,
)


class ReflectionCapabilityContractTests(unittest.TestCase):
    def test_allowed_retry_strategies_are_bounded(self) -> None:
        self.assertEqual(
            ALLOWED_REFLECTION_RETRY_STRATEGIES,
            {
                "retry_retrieval",
                "synthesize_from_task_outputs",
                "stop_insufficient",
            },
        )

    def test_normalise_reflection_plan_rejects_unknown_strategy(self) -> None:
        plan = _normalise_reflection_plan_record(
            {
                "status": "ready",
                "retry_objective": "find_missing_values",
                "retry_strategy": "unbounded_agent_loop",
                "missing_info": [" value "],
                "subqueries": [" query "],
                "preferred_sections": [],
                "explanation": "unit test",
            },
            fallback_plan={"retry_strategy": "stop_insufficient"},
            missing_info=["fallback value"],
            preferred_sections=["fallback section"],
        )

        self.assertEqual(plan["retry_strategy"], "stop_insufficient")
        self.assertEqual(plan["missing_info"], ["value"])
        self.assertEqual(plan["subqueries"], ["query"])
        self.assertEqual(plan["preferred_sections"], ["fallback section"])

    def test_normalise_reflection_plan_falls_back_without_subqueries(self) -> None:
        plan = _normalise_reflection_plan_record(
            {
                "status": "ready",
                "retry_strategy": "retry_retrieval",
                "missing_info": [],
                "subqueries": [],
            },
            fallback_plan={
                "status": "ready",
                "retry_strategy": "retry_retrieval",
                "missing_info": ["fallback value"],
                "subqueries": ["fallback query"],
            },
            missing_info=["missing value"],
            preferred_sections=["section"],
        )

        self.assertEqual(plan["subqueries"], ["fallback query"])
        self.assertEqual(
            plan["explanation"],
            "fallback to heuristic because reflection planner returned no subqueries",
        )


if __name__ == "__main__":
    unittest.main()
