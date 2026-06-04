import unittest

from src.agent.financial_graph import FinancialAgent


class _FakeGraph:
    def __init__(self, final_state):
        self._final_state = final_state

    def invoke(self, initial):
        return dict(self._final_state)


class _FakeDoc:
    def __init__(self, page_content, metadata=None):
        self.page_content = page_content
        self.metadata = dict(metadata or {})


class FinancialAgentRunProjectionTests(unittest.TestCase):
    def _base_final_state(self):
        return {
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
            "retrieval_debug_trace": {"selected_count": 1},
            "retrieval_debug_trace_history": [],
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

    def test_run_prefers_resolved_trace_and_nests_legacy_projection(self) -> None:
        final_state = self._base_final_state()
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

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
        self.assertEqual(result["retrieval_debug_trace"], {"selected_count": 1})
        self.assertNotIn("calculation_operands", result)
        self.assertNotIn("calculation_plan", result)
        self.assertNotIn("calculation_result", result)
        self.assertNotIn("legacy_calculation_projection", result)

    def test_run_preserves_numeric_runtime_evidence_from_retrieved_docs_when_empty(self) -> None:
        final_state = self._base_final_state()
        final_state["resolved_calculation_trace"] = {}
        final_state["structured_result"] = {}
        final_state["calculation_operands"] = []
        final_state["calculation_plan"] = {}
        final_state["calculation_result"] = {}
        final_state["retrieved_docs"] = [
            _FakeDoc(
                "Metric table row shows current period value 25.4%.",
                {"section_path": "Financial review", "block_type": "table"},
            )
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(len(result["evidence_items"]), 1)
        self.assertEqual(result["evidence_items"][0]["evidence_id"], "retrieved::001")
        self.assertIn("25.4%", result["evidence_items"][0]["quote_span"])

    def test_run_keeps_existing_runtime_evidence(self) -> None:
        final_state = self._base_final_state()
        final_state["evidence_items"] = [
            {
                "evidence_id": "ev_existing",
                "source_anchor": "Existing section",
                "claim": "Existing claim",
                "quote_span": "Existing quote",
                "metadata": {},
            }
        ]
        final_state["retrieved_docs"] = [
            _FakeDoc("Metric table row shows current period value 25.4%.")
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual([item["evidence_id"] for item in result["evidence_items"]], ["ev_existing"])

    def test_run_filters_existing_runtime_evidence_with_trace_operand_support(self) -> None:
        final_state = self._base_final_state()
        final_state["answer"] = "The final ratio is 25.4%."
        final_state["evidence_items"] = [
            {
                "evidence_id": "ev_wrong",
                "source_anchor": "Segment table",
                "claim": "A context-dependent segment row shows 99.9%.",
                "quote_span": "A context-dependent segment row shows 99.9%.",
                "metadata": {},
            }
        ]
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [
                {
                    "operand_id": "ratio_operand",
                    "label": "final ratio",
                    "raw_value": "25.4",
                    "raw_unit": "%",
                    "normalized_value": 25.4,
                    "normalized_unit": "PERCENT",
                    "source_anchor": "Supported table",
                    "matched_operand_role": "primary_value",
                }
            ],
            "calculation_plan": {"operation": "lookup"},
            "calculation_result": {
                "status": "ok",
                "rendered_value": "25.4%",
                "answer_slots": {"operation_family": "lookup"},
            },
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual([item["evidence_id"] for item in result["evidence_items"]], ["operand::ratio_operand"])
        self.assertIn("25.4%", result["evidence_items"][0]["quote_span"])


if __name__ == "__main__":
    unittest.main()
