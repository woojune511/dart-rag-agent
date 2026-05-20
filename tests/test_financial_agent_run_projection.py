import unittest

from src.agent.financial_graph import FinancialAgent


class _FakeGraph:
    def __init__(self, final_state):
        self._final_state = final_state

    def invoke(self, initial):
        return dict(self._final_state)


class FinancialAgentRunProjectionTests(unittest.TestCase):
    def test_run_prefers_resolved_trace_and_nests_legacy_projection(self) -> None:
        final_state = {
            "query": "test question",
            "report_scope": {},
            "query_type": "comparison",
            "intent": "comparison",
            "planner_mode": "initial",
            "planner_feedback": "",
            "plan_loop_count": 0,
            "target_metric_family": "debt_ratio",
            "target_metric_family_hint": "debt_ratio",
            "planned_metric_families": ["debt_ratio"],
            "format_preference": "brief",
            "routing_source": "rule",
            "routing_confidence": 0.9,
            "routing_scores": {"comparison": 0.9},
            "companies": ["삼성전자"],
            "years": [2023],
            "answer": "25.4%",
            "citations": ["[1]"],
            "seed_retrieved_docs": [],
            "retrieved_docs": [],
            "evidence_items": [],
            "selected_claim_ids": [],
            "draft_points": [],
            "kept_claim_ids": [],
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "numeric_debug_trace": {},
            "calculation_operands": [{"label": "stale", "value": "999"}],
            "calculation_plan": {"status": "stale"},
            "calculation_result": {"status": "stale", "rendered_value": "999"},
            "calculation_debug_trace": {},
            "planner_debug_trace": {},
            "missing_info": [],
            "reflection_count": 0,
            "retry_reason": "",
            "retry_queries": [],
            "reconciliation_retry_count": 0,
            "reflection_plan": {},
            "semantic_plan": {},
            "calc_subtasks": [],
            "retrieval_queries": [],
            "active_subtask_index": 0,
            "active_subtask": {},
            "subtask_results": [],
            "subtask_debug_trace": {},
            "subtask_loop_complete": False,
            "reconciliation_result": {},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {
                "calculation_operands": [{"label": "fresh", "value": "123"}],
                "calculation_plan": {"operation": "lookup"},
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "123",
                    "answer_slots": {"operation_family": "lookup"},
                },
            },
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)

        result = agent.run("test question")

        self.assertEqual(result["structured_result"]["rendered_value"], "123")
        self.assertEqual(
            result["resolved_calculation_trace"]["calculation_plan"]["operation"],
            "lookup",
        )
        self.assertEqual(
            result["resolved_calculation_trace"]["calculation_operands"],
            [{"label": "fresh", "value": "123"}],
        )
        self.assertNotIn("calculation_operands", result)
        self.assertNotIn("calculation_plan", result)
        self.assertNotIn("calculation_result", result)
        self.assertNotIn("legacy_calculation_projection", result)


if __name__ == "__main__":
    unittest.main()
