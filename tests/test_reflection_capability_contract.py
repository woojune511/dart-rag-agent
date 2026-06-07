import unittest

from src.agent.financial_graph_reconciliation import FinancialAgentReconciliationMixin
from src.agent.financial_graph_reconciliation import (
    ALLOWED_REFLECTION_RETRY_STRATEGIES,
    _normalise_reflection_plan_record,
)


class _ReflectionHarness(FinancialAgentReconciliationMixin):
    pass


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

    def test_build_reflection_request_uses_strict_runtime_trace_and_budget(self) -> None:
        request = _ReflectionHarness()._build_reflection_request(
            {
                "query": "find missing value",
                "active_subtask": {"task_id": "task_1"},
                "reflection_count": 0,
                "evidence_status": "missing",
                "evidence_items": [{"evidence_id": "e1"}],
                "retrieved_docs": [object()],
                "seed_retrieved_docs": [object(), object()],
                "resolved_calculation_trace": {},
                "structured_result": {},
                "calculation_operands": [{"label": "legacy"}],
                "calculation_plan": {"status": "legacy"},
                "calculation_result": {"status": "legacy"},
            },
            missing_info=[" value "],
            failure_status="incomplete",
        )

        self.assertEqual(request["active_task_id"], "task_1")
        self.assertEqual(request["missing_info"], ["value"])
        self.assertEqual(request["remaining_retry_budget"], 1)
        self.assertEqual(request["runtime_trace_summary"]["operand_count"], 0)
        self.assertEqual(request["runtime_trace_summary"]["plan_status"], "")
        self.assertEqual(request["runtime_trace_summary"]["result_status"], "")
        self.assertEqual(request["evidence_summary"]["evidence_item_count"], 1)
        self.assertEqual(request["evidence_summary"]["retrieved_doc_count"], 1)
        self.assertEqual(request["evidence_summary"]["seed_retrieved_doc_count"], 2)

    def test_build_reflection_request_clamps_budget_after_one_retry(self) -> None:
        request = _ReflectionHarness()._build_reflection_request(
            {
                "query": "find missing value",
                "active_subtask": {},
                "reflection_count": 1,
                "resolved_calculation_trace": {},
                "structured_result": {},
            },
            missing_info=[],
            failure_status="incomplete",
        )

        self.assertEqual(request["remaining_retry_budget"], 0)


if __name__ == "__main__":
    unittest.main()
