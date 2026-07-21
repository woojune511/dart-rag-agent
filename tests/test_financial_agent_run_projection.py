import unittest
from types import SimpleNamespace

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_state import AgentAnswer, DebugBundle, FinancialAgentState, ReviewTrace
from src.agent.financial_graph_state import (
    CalculationState,
    EvidenceState,
    LedgerState,
    ReflectionState,
    RetrievalState,
    RoutingState,
)
from src.config.retrieval_policy import CALCULATION_NARRATIVE_POLICY
from src.utils.gemini_usage import GeminiUsageCallbackHandler


class _FakeGraph:
    def __init__(self, final_state):
        self._final_state = final_state
        self.initial_state = None

    def invoke(self, initial):
        self.initial_state = dict(initial)
        return dict(self._final_state)


class _FakeDoc:
    def __init__(self, page_content, metadata=None):
        self.page_content = page_content
        self.metadata = dict(metadata or {})


class _PhaseUsageGraph:
    def __init__(self, final_state, agent):
        self._final_state = final_state
        self._agent = agent

    def invoke(self, _initial):
        self._agent._llm_for_phase("numeric_extraction")
        self._agent.llm_usage_callback.on_llm_end(
            SimpleNamespace(
                llm_output=None,
                generations=[
                    [
                        SimpleNamespace(
                            message=SimpleNamespace(
                                usage_metadata={
                                    "input_tokens": 100,
                                    "output_tokens": 20,
                                }
                            )
                        )
                    ]
                ],
            )
        )
        return dict(self._final_state)


class FinancialAgentRunProjectionTests(unittest.TestCase):
    def test_build_graph_resolves_state_type_hints_for_langgraph_routes(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)

        graph = FinancialAgent._build_graph(agent)

        self.assertIsNotNone(graph)

    def test_state_typing_keeps_debug_surface_optional_without_flat_calculation_mirrors(self) -> None:
        self.assertIn("answer", AgentAnswer.__optional_keys__)
        self.assertIn("task_artifact_trace", ReviewTrace.__optional_keys__)
        self.assertIn("llm_usage", DebugBundle.__optional_keys__)
        self.assertNotIn("calculation_operands", FinancialAgentState.__optional_keys__)
        self.assertNotIn("calculation_plan", FinancialAgentState.__optional_keys__)
        self.assertNotIn("calculation_result", FinancialAgentState.__optional_keys__)
        self.assertIn("calculation_debug_trace", FinancialAgentState.__optional_keys__)
        self.assertIn("debug_traces", FinancialAgentState.__optional_keys__)
        self.assertIn("reflection_request", FinancialAgentState.__optional_keys__)
        self.assertIn("reflection_action", FinancialAgentState.__optional_keys__)
        self.assertIn("reflection_report", FinancialAgentState.__optional_keys__)
        self.assertIn("replan_blocked_reason", FinancialAgentState.__optional_keys__)
        self.assertNotIn("calculation_debug_trace", FinancialAgentState.__required_keys__)

    def test_state_typing_is_split_by_runtime_concern_without_changing_full_shape(self) -> None:
        component_keys = set().union(
            RoutingState.__required_keys__,
            RoutingState.__optional_keys__,
            RetrievalState.__required_keys__,
            RetrievalState.__optional_keys__,
            EvidenceState.__required_keys__,
            EvidenceState.__optional_keys__,
            CalculationState.__required_keys__,
            CalculationState.__optional_keys__,
            ReflectionState.__required_keys__,
            ReflectionState.__optional_keys__,
            LedgerState.__required_keys__,
            LedgerState.__optional_keys__,
        )

        self.assertEqual(
            FinancialAgentState.__required_keys__ | FinancialAgentState.__optional_keys__,
            component_keys,
        )
        self.assertIn("query", RoutingState.__required_keys__)
        self.assertIn("retrieved_docs", RetrievalState.__required_keys__)
        self.assertIn("evidence_items", EvidenceState.__required_keys__)
        self.assertIn("resolved_calculation_trace", CalculationState.__required_keys__)
        self.assertIn("reflection_request", ReflectionState.__optional_keys__)
        self.assertIn("tasks", LedgerState.__required_keys__)

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
            "numeric_debug_trace_history": [],
            "calculation_operands": [{"label": "stale", "value": "999"}],
            "calculation_plan": {"status": "stale"},
            "calculation_result": {"status": "stale", "rendered_value": "999"},
            "calculation_debug_trace": {"source": "unit_test"},
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

    def test_run_prefers_resolved_trace_and_omits_flat_compatibility_mirrors(self) -> None:
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
        self.assertEqual(
            result["resolved_calculation_trace"]["runtime_projection"]["source"],
            "resolved_calculation_trace",
        )
        self.assertFalse(
            result["resolved_calculation_trace"]["runtime_projection"]["legacy_fallback"]
        )
        self.assertEqual(result["retrieval_debug_trace"], {"selected_count": 1})
        self.assertEqual(result["reflection_request"], {})
        self.assertEqual(result["reflection_action"], {})
        self.assertEqual(result["reflection_report"], {})
        self.assertEqual(result["agent_answer"]["answer"], result["answer"])
        self.assertEqual(result["agent_answer"]["structured_result"], result["structured_result"])
        self.assertEqual(
            result["agent_answer"]["resolved_calculation_trace"],
            result["resolved_calculation_trace"],
        )
        self.assertEqual(result["review_trace"]["retrieval_debug_trace"], result["retrieval_debug_trace"])
        self.assertEqual(result["review_trace"]["task_artifact_trace"], result["task_artifact_trace"])
        self.assertEqual(result["debug_bundle"]["debug_traces"], result["debug_traces"])
        self.assertEqual(result["debug_bundle"]["llm_usage"], result["llm_usage"])
        self.assertNotIn("calculation_operands", result)
        self.assertNotIn("calculation_plan", result)
        self.assertNotIn("calculation_result", result)
        self.assertNotIn("legacy_calculation_projection", result)

    def test_run_reprojects_trace_after_structured_late_numeric_answer(self) -> None:
        final_state = self._base_final_state()
        final_state["answer"] = "target coverage is 3.5배."
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [
                {"matched_operand_role": "numerator_1", "raw_value": "100", "raw_unit": "unit"},
                {"matched_operand_role": "denominator_1", "raw_value": "20", "raw_unit": "unit"},
            ],
            "calculation_plan": {"operation": "ratio"},
            "calculation_result": {
                "status": "ok",
                "rendered_value": "5배",
                "answer_slots": {
                    "operation_family": "ratio",
                    "primary_value": {"status": "ok", "rendered_value": "5배"},
                },
            },
        }
        final_state["structured_result"] = {
            "formatted_result": "target coverage is 3.5배.",
            "rendered_value": "target coverage is 3.5배.",
            "subtask_results": [
                {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "metric_label": "target coverage",
                    "operation_family": "ratio",
                    "answer": "target coverage is 3.5배.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "3.5배",
                        "formatted_result": "target coverage is 3.5배.",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "metric_label": "target coverage",
                            "primary_value": {"status": "ok", "rendered_value": "3.5배"},
                            "components_by_group": {
                                "numerator": [
                                    {
                                        "status": "ok",
                                        "role": "numerator_1",
                                        "label": "target numerator",
                                        "raw_value": "350",
                                        "raw_unit": "unit",
                                        "normalized_value": 350.0,
                                        "normalized_unit": "COUNT",
                                        "rendered_value": "350unit",
                                    }
                                ],
                                "denominator": [
                                    {
                                        "status": "ok",
                                        "role": "denominator_1",
                                        "label": "target denominator",
                                        "raw_value": "100",
                                        "raw_unit": "unit",
                                        "normalized_value": 100.0,
                                        "normalized_unit": "COUNT",
                                        "rendered_value": "100unit",
                                    }
                                ],
                            },
                        },
                    },
                }
            ],
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["resolved_calculation_trace"]
        self.assertEqual(result["answer"], "target coverage is 3.5배.")
        self.assertEqual(trace["runtime_projection"]["source"], "structured_result_subtasks")
        self.assertEqual(trace["calculation_plan"]["mode"], "aggregate_subtasks")
        self.assertEqual(trace["calculation_result"]["formatted_result"], "target coverage is 3.5배.")
        self.assertEqual(trace["calculation_result"]["subtask_results"][0]["calculation_result"]["rendered_value"], "3.5배")

    def test_run_prefers_structured_numeric_answer_over_missing_public_answer(self) -> None:
        final_state = self._base_final_state()
        missing_marker = next(iter(CALCULATION_NARRATIVE_POLICY["missing_answer_markers"]))
        final_state["answer"] = f"target denominator {missing_marker}."
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [
                {"matched_operand_role": "numerator_1", "raw_value": "100", "raw_unit": "unit"},
                {"matched_operand_role": "denominator_1", "raw_value": "20", "raw_unit": "unit"},
            ],
            "calculation_plan": {"operation": "ratio"},
            "calculation_result": {
                "status": "ok",
                "rendered_value": "5배",
                "answer_slots": {
                    "operation_family": "ratio",
                    "primary_value": {"status": "ok", "rendered_value": "5배"},
                },
            },
        }
        final_state["structured_result"] = {
            "formatted_result": "target coverage is 3.5배.",
            "rendered_value": "target coverage is 3.5배.",
            "subtask_results": [
                {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "metric_label": "target coverage",
                    "operation_family": "ratio",
                    "answer": "target coverage is 3.5배.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "3.5배",
                        "formatted_result": "target coverage is 3.5배.",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "metric_label": "target coverage",
                            "primary_value": {"status": "ok", "rendered_value": "3.5배"},
                        },
                    },
                }
            ],
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(result["answer"], "target coverage is 3.5배.")
        self.assertEqual(
            result["resolved_calculation_trace"]["runtime_projection"]["source"],
            "structured_result_subtasks",
        )

    def test_run_promotes_complete_nested_aggregate_answer_over_numeric_only_public_answer(self) -> None:
        final_state = self._base_final_state()
        numeric_answer = "2023 segment expense was 300, up 50% from 200 in 2022."
        complete_answer = (
            "2023 segment expense was 300, up 50% from 200 in 2022. "
            "The increase reflected conservative risk actions under a stressed scenario."
        )
        noisy_nested_answer = (
            "2023 segment expense was 300, up 150% from 120 in 2022. "
            f"{numeric_answer} "
            "The increase reflected conservative risk actions under a stressed scenario. "
            "A separate risk indicator moved by 0.31%p to 1.01%."
        )
        final_state["answer"] = numeric_answer
        final_state["compressed_answer"] = numeric_answer
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [],
            "calculation_plan": {"status": "ok", "mode": "aggregate_subtasks"},
            "calculation_result": {
                "status": "ok",
                "formatted_result": numeric_answer,
                "rendered_value": numeric_answer,
                "answer_slots": {"operation_family": "aggregate_subtasks"},
            },
        }
        growth_result = {
            "status": "ok",
            "rendered_value": "50%",
            "formatted_result": numeric_answer,
            "answer_slots": {
                "operation_family": "growth_rate",
                "primary_value": {"status": "ok", "rendered_value": "50%"},
                "current_value": {"status": "ok", "rendered_value": "300"},
                "prior_value": {"status": "ok", "rendered_value": "200"},
            },
        }
        final_state["structured_result"] = {
            "status": "ok",
            "formatted_result": numeric_answer,
            "rendered_value": numeric_answer,
            "subtask_results": [
                {
                    "task_id": "task_growth",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "segment expense growth",
                    "operation_family": "growth_rate",
                    "answer": numeric_answer,
                    "status": "ok",
                    "calculation_result": growth_result,
                },
                {
                    "task_id": "task_summary",
                    "metric_family": "narrative_summary",
                    "metric_label": "driver summary",
                    "operation_family": "aggregate_subtasks",
                    "answer": noisy_nested_answer,
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "formatted_result": noisy_nested_answer,
                        "rendered_value": noisy_nested_answer,
                        "subtask_results": [],
                        "answer_slots": {"operation_family": "aggregate_subtasks"},
                    },
                },
            ],
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["resolved_calculation_trace"]
        self.assertEqual(result["answer"], complete_answer)
        self.assertNotIn("150%", result["answer"])
        self.assertNotIn("0.31%p", result["answer"])
        self.assertEqual(trace["calculation_result"]["formatted_result"], complete_answer)
        self.assertEqual(trace["runtime_projection"]["source"], "structured_result_subtasks")
        self.assertTrue(trace["runtime_projection"]["complete_aggregate_answer_selected"])

    def test_run_drops_noisy_numeric_prefix_when_clean_aggregate_answer_is_nested(self) -> None:
        final_state = self._base_final_state()
        clean_answer = (
            "2023 segment expense was 300, up 50% from 200 in 2022. "
            "The increase reflected conservative risk actions under a stressed scenario."
        )
        noisy_answer = "2022 segment expense was 900, up 800% from 100 in 2021. " + clean_answer
        final_state["answer"] = noisy_answer
        final_state["compressed_answer"] = noisy_answer
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [],
            "calculation_plan": {"status": "ok", "mode": "aggregate_subtasks"},
            "calculation_result": {
                "status": "ok",
                "formatted_result": noisy_answer,
                "rendered_value": noisy_answer,
                "answer_slots": {"operation_family": "aggregate_subtasks"},
            },
        }
        final_state["structured_result"] = {
            "status": "ok",
            "formatted_result": noisy_answer,
            "rendered_value": noisy_answer,
            "subtask_results": [
                {
                    "task_id": "task_growth",
                    "metric_family": "concept_growth_rate",
                    "operation_family": "growth_rate",
                    "answer": "50%",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "formatted_result": "50%",
                        "answer_slots": {"operation_family": "growth_rate"},
                    },
                },
                {
                    "task_id": "task_summary",
                    "metric_family": "narrative_summary",
                    "operation_family": "aggregate_subtasks",
                    "answer": clean_answer,
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "formatted_result": clean_answer,
                        "answer_slots": {"operation_family": "aggregate_subtasks"},
                    },
                },
            ],
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(result["answer"], clean_answer)
        self.assertNotIn("800%", result["answer"])
        self.assertEqual(
            result["resolved_calculation_trace"]["calculation_result"]["formatted_result"],
            clean_answer,
        )

    def test_run_prefers_numeric_consistent_aggregate_when_public_has_conflicting_prefix(self) -> None:
        final_state = self._base_final_state()
        clean_answer = (
            "2023 segment expense was 3,146,409백만원, up 70.28% from 1,847,775백만원 in 2022. "
            "The increase reflected conservative risk actions under a stressed scenario."
        )
        noisy_answer = (
            "2023 segment expense was 3,146억원, up 142.19% from 1,299억원 in 2022. "
            "2023 segment expense was 3,146,409백만원, up 70.28% from 1,847,775백만원 in 2022. "
            "The increase reflected conservative risk actions."
        )
        final_state["answer"] = noisy_answer
        final_state["compressed_answer"] = noisy_answer
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [],
            "calculation_plan": {"status": "ok", "mode": "aggregate_subtasks"},
            "calculation_result": {
                "status": "ok",
                "formatted_result": noisy_answer,
                "rendered_value": noisy_answer,
                "answer_slots": {"operation_family": "aggregate_subtasks"},
            },
        }
        final_state["structured_result"] = {
            "status": "ok",
            "formatted_result": noisy_answer,
            "rendered_value": noisy_answer,
            "subtask_results": [
                {
                    "task_id": "task_summary",
                    "metric_family": "narrative_summary",
                    "operation_family": "aggregate_subtasks",
                    "answer": clean_answer,
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "formatted_result": clean_answer,
                        "answer_slots": {"operation_family": "aggregate_subtasks"},
                    },
                }
            ],
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(result["answer"], clean_answer)
        self.assertNotIn("142.19%", result["answer"])
        self.assertNotIn("1,299억원", result["answer"])
        self.assertEqual(
            result["resolved_calculation_trace"]["calculation_result"]["formatted_result"],
            clean_answer,
        )

    def test_run_prefers_complete_structured_ratio_over_stale_public_ratio(self) -> None:
        final_state = self._base_final_state()
        final_state["query"] = "calculate target borrowing share"
        final_state["answer"] = "target share is 7.87%. 계산: short component / tangible base."
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [
                {"matched_operand_role": "numerator_1", "raw_value": "4,146", "raw_unit": "백만원"},
                {"matched_operand_role": "denominator_1", "raw_value": "52,705", "raw_unit": "백만원"},
            ],
            "calculation_plan": {"status": "ok", "operation": "ratio"},
            "calculation_result": {
                "status": "ok",
                "result_value": 7.87,
                "result_unit": "%",
                "rendered_value": "7.87%",
                "formatted_result": "target share is 7.87%.",
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "target share",
                    "primary_value": {"status": "ok", "rendered_value": "7.87%"},
                },
            },
        }
        ratio_result = {
            "status": "ok",
            "result_value": 42.02,
            "result_unit": "%",
            "rendered_value": "42.02%",
            "formatted_result": "target share is 42.02%.",
            "answer_slots": {
                "operation_family": "ratio",
                "metric_label": "target share",
                "primary_value": {
                    "status": "ok",
                    "rendered_value": "42.02%",
                    "normalized_value": 42.02,
                    "normalized_unit": "PERCENT",
                },
                "components_by_group": {
                    "numerator": [
                        {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "short component",
                            "raw_value": "4,146",
                            "raw_unit": "백만원",
                            "normalized_value": 4146000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "4,146백만원",
                            "source_row_id": "ev_short",
                        },
                        {
                            "status": "ok",
                            "role": "numerator_2",
                            "label": "long component",
                            "raw_value": "10,121",
                            "raw_unit": "백만원",
                            "normalized_value": 10121000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "10,121백만원",
                            "source_row_id": "ev_long",
                        },
                        {
                            "status": "ok",
                            "role": "numerator_3",
                            "label": "bond component",
                            "raw_value": "9,490",
                            "raw_unit": "백만원",
                            "normalized_value": 9490000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "9,490백만원",
                            "source_row_id": "ev_bond",
                        },
                    ],
                    "denominator": [
                        {
                            "status": "ok",
                            "role": "denominator_1",
                            "label": "tangible base",
                            "raw_value": "52,705",
                            "raw_unit": "백만원",
                            "normalized_value": 52705000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "52,705백만원",
                            "source_row_id": "ev_tangible",
                        },
                        {
                            "status": "ok",
                            "role": "denominator_2",
                            "label": "intangible base",
                            "raw_value": "3,835",
                            "raw_unit": "백만원",
                            "normalized_value": 3835000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "3,835백만원",
                            "source_row_id": "ev_intangible",
                        },
                    ],
                },
            },
        }
        final_state["structured_result"] = {
            "subtask_results": [
                {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "metric_label": "target share",
                    "operation_family": "ratio",
                    "answer": "target share is 42.02%.",
                    "status": "ok",
                    "calculation_result": ratio_result,
                    "calculation_operands": [
                        slot
                        for slots in ratio_result["answer_slots"]["components_by_group"].values()
                        for slot in slots
                    ],
                }
            ],
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertIn("42.02%", result["answer"])
        self.assertNotIn("7.87%", result["answer"])
        self.assertEqual(
            result["resolved_calculation_trace"]["runtime_projection"]["source"],
            "structured_result_subtasks",
        )
        self.assertTrue(
            result["resolved_calculation_trace"]["runtime_projection"]["public_answer_repaired"]
        )

    def test_run_refreshes_public_answer_from_resolved_ratio_trace(self) -> None:
        final_state = self._base_final_state()
        final_state["answer"] = "segment revenue ratio is 100%."
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [],
            "calculation_plan": {"status": "ok", "operation": "ratio"},
            "calculation_result": {
                "status": "ok",
                "result_value": 50.0,
                "result_unit": "%",
                "rendered_value": "50%",
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "segment revenue ratio",
                    "primary_value": {"status": "ok", "rendered_value": "50%"},
                    "components_by_group": {
                        "numerator": [
                            {
                                "status": "ok",
                                "role": "numerator_1",
                                "label": "segment revenue",
                                "raw_value": "10",
                                "raw_unit": "million",
                                "normalized_value": 10.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "10 million",
                                "source_row_id": "row_segment",
                            }
                        ],
                        "denominator": [
                            {
                                "status": "ok",
                                "role": "denominator_1",
                                "label": "total revenue",
                                "raw_value": "20",
                                "raw_unit": "million",
                                "normalized_value": 20.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "20 million",
                                "source_row_id": "row_total",
                            }
                        ],
                    },
                },
            },
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertIn("50%", result["answer"])
        self.assertNotIn("100%", result["answer"])

    def test_run_repairs_collapsed_ratio_trace_from_runtime_evidence(self) -> None:
        final_state = self._base_final_state()
        final_state["answer"] = "segment operating income ratio is 100%."
        final_state["evidence_items"] = [
            {
                "evidence_id": "ev_num",
                "claim": "segment operating income 10백만원",
                "quote_span": "segment operating income 10백만원",
            },
            {
                "evidence_id": "ev_den",
                "claim": "total operating income 20백만원",
                "quote_span": "total operating income 20백만원",
            },
        ]
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [
                {
                    "operand_id": "op_001",
                    "matched_operand_role": "numerator_1",
                    "raw_value": "5",
                    "raw_unit": "백만원",
                    "normalized_value": 5.0,
                    "normalized_unit": "KRW",
                    "source_row_id": "ev_same",
                },
                {
                    "operand_id": "op_002",
                    "matched_operand_role": "denominator_1",
                    "raw_value": "5",
                    "raw_unit": "백만원",
                    "normalized_value": 5.0,
                    "normalized_unit": "KRW",
                    "source_row_id": "ev_same",
                },
            ],
            "calculation_plan": {"status": "ok", "operation": "ratio"},
            "calculation_result": {
                "status": "ok",
                "result_value": 100.0,
                "result_unit": "%",
                "rendered_value": "100%",
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "segment operating income ratio",
                    "primary_value": {"status": "ok", "rendered_value": "100%"},
                    "components_by_group": {
                        "numerator": [
                            {
                                "status": "ok",
                                "role": "numerator_1",
                                "label": "segment operating income",
                                "concept": "operating_income",
                                "raw_value": "5",
                                "raw_unit": "백만원",
                                "normalized_value": 5.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "5백만원",
                                "source_row_id": "ev_same",
                            }
                        ],
                        "denominator": [
                            {
                                "status": "ok",
                                "role": "denominator_1",
                                "label": "operating income",
                                "raw_value": "5",
                                "raw_unit": "백만원",
                                "normalized_value": 5.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "5백만원",
                                "source_row_id": "ev_same",
                            }
                        ],
                    },
                },
            },
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertIn("50%", result["answer"])
        self.assertEqual(result["resolved_calculation_trace"]["calculation_result"]["rendered_value"], "50%")
        self.assertTrue(
            result["resolved_calculation_trace"]["calculation_result"]["stale_result_repaired_from_evidence"]
        )

    def test_run_repairs_period_comparison_trace_from_source_stated_evidence(self) -> None:
        final_state = self._base_final_state()
        final_state["query"] = "calculate year-over-year operating profit growth and summarize the MD&A impact"
        final_state["answer"] = (
            "2023 operating profit was 810,900백만원 versus 3,390,092백만원, down -76.08%. "
            "The MD&A says operating profit was 409,219백만원 and decreased 84.3%."
        )
        final_state["evidence_items"] = [
            {
                "evidence_id": "ev_mda",
                "source_anchor": "company | 2023 | MD&A",
                "claim": "Operating profit was 409,219백만원 and decreased 84.3%.",
                "quote_span": "Operating profit was 409,219백만원 and decreased 84.3%.",
                "metadata": {
                    "year": 2023,
                    "statement_type": "mda",
                    "unit_hint": "백만원",
                    "table_source_id": "mda::table:1",
                    "table_row_labels_text": "Operating profit",
                    "table_value_labels_text": (
                        "Operating profit 409,219\n"
                        "Operating profit 2,600,786\n"
                        "Operating profit 712,064\n"
                        "Operating profit -84.3%"
                    ),
                },
            }
        ]
        final_state["calc_subtasks"] = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "refining operating profit growth",
                "operation_family": "growth_rate",
                "required_operands": [
                    {
                        "label": "refining operating profit",
                        "aliases": ["Operating profit"],
                        "concept": "operating_income",
                        "role": "current_period",
                        "required": True,
                        "unit_family": "KRW",
                    },
                    {
                        "label": "refining operating profit",
                        "aliases": ["Operating profit"],
                        "concept": "operating_income",
                        "role": "prior_period",
                        "required": True,
                        "unit_family": "KRW",
                    },
                ],
            }
        ]
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [
                {
                    "operand_id": "current_period",
                    "matched_operand_role": "current_period",
                    "raw_value": "810,900",
                    "raw_unit": "백만원",
                    "normalized_value": 810_900_000_000.0,
                    "normalized_unit": "KRW",
                    "source_row_id": "task_output:current",
                },
                {
                    "operand_id": "prior_period",
                    "matched_operand_role": "prior_period",
                    "raw_value": "3,390,092",
                    "raw_unit": "백만원",
                    "normalized_value": 3_390_092_000_000.0,
                    "normalized_unit": "KRW",
                    "source_row_id": "task_output:prior",
                },
            ],
            "calculation_plan": {
                "status": "ok",
                "operation": "growth_rate",
                "task_id": "task_growth",
                "metric_label": "refining operating profit growth",
            },
            "calculation_result": {
                "status": "ok",
                "result_value": -76.08,
                "result_unit": "%",
                "rendered_value": "-76.08%",
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "metric_label": "refining operating profit growth",
                    "primary_value": {"status": "ok", "rendered_value": "-76.08%"},
                    "current_value": {
                        "status": "ok",
                        "role": "current_value",
                        "label": "refining operating profit",
                        "raw_value": "810,900",
                        "raw_unit": "백만원",
                        "normalized_value": 810_900_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "810,900백만원",
                        "source_row_id": "task_output:current",
                        "source_row_ids": ["task_output:current", "row_current"],
                    },
                    "prior_value": {
                        "status": "ok",
                        "role": "prior_value",
                        "label": "refining operating profit",
                        "raw_value": "3,390,092",
                        "raw_unit": "백만원",
                        "normalized_value": 3_390_092_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "3,390,092백만원",
                        "source_row_id": "task_output:prior",
                        "source_row_ids": ["task_output:prior", "row_prior"],
                    },
                },
            },
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace_result = result["resolved_calculation_trace"]["calculation_result"]
        self.assertIn("84.3%", result["answer"])
        self.assertNotIn("-76.08%", result["answer"])
        self.assertEqual(trace_result["rendered_value"], "-84.3%")
        self.assertTrue(trace_result["derived_metrics"]["source_stated_result_used"])
        self.assertEqual(trace_result["answer_slots"]["current_value"]["raw_value"], "409,219")
        self.assertEqual(trace_result["answer_slots"]["prior_value"]["raw_value"], "2,600,786")
        self.assertTrue(trace_result["stale_result_repaired_from_evidence"])

    def test_run_repairs_aggregate_period_comparison_subtask_from_source_stated_evidence(self) -> None:
        final_state = self._base_final_state()
        final_state["query"] = "calculate year-over-year operating profit growth and summarize the MD&A impact"
        final_state["answer"] = (
            "2023 operating profit was 810,900백만원 versus 3,390,092백만원, down -76.08%. "
            "The margin decline weighed on performance."
        )
        final_state["evidence_items"] = [
            {
                "evidence_id": "ev_mda",
                "source_anchor": "company | 2023 | MD&A",
                "claim": "Operating profit | 409,219 | 2,600,786 | 712,064 | -84.3%",
                "quote_span": "Operating profit | 409,219 | 2,600,786 | 712,064 | -84.3%",
                "metadata": {
                    "year": 2023,
                    "statement_type": "mda",
                    "unit_hint": "백만원",
                    "table_source_id": "mda::table:1",
                    "table_row_labels_text": "Operating profit",
                    "table_value_labels_text": (
                        "Operating profit 409,219\n"
                        "Operating profit 2,600,786\n"
                        "Operating profit 712,064\n"
                        "Operating profit -84.3%"
                    ),
                },
            }
        ]
        final_state["calc_subtasks"] = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "refining operating profit growth",
                "operation_family": "growth_rate",
                "required_operands": [
                    {
                        "label": "refining operating profit",
                        "aliases": ["Operating profit"],
                        "concept": "operating_income",
                        "role": "current_period",
                        "required": True,
                        "unit_family": "KRW",
                    },
                    {
                        "label": "refining operating profit",
                        "aliases": ["Operating profit"],
                        "concept": "operating_income",
                        "role": "prior_period",
                        "required": True,
                        "unit_family": "KRW",
                    },
                ],
            }
        ]
        growth_row = {
            "task_id": "task_growth",
            "metric_family": "concept_growth_rate",
            "metric_label": "refining operating profit growth",
            "operation_family": "growth_rate",
            "answer": "-76.08%",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "result_value": -76.08,
                "result_unit": "%",
                "rendered_value": "-76.08%",
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "metric_label": "refining operating profit growth",
                    "primary_value": {"status": "ok", "rendered_value": "-76.08%"},
                    "current_value": {
                        "status": "ok",
                        "role": "current_value",
                        "label": "refining operating profit",
                        "raw_value": "810,900",
                        "raw_unit": "백만원",
                        "normalized_value": 810_900_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "810,900백만원",
                        "source_row_id": "task_output:current",
                        "source_row_ids": ["task_output:current", "row_current"],
                    },
                    "prior_value": {
                        "status": "ok",
                        "role": "prior_value",
                        "label": "refining operating profit",
                        "raw_value": "3,390,092",
                        "raw_unit": "백만원",
                        "normalized_value": 3_390_092_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "3,390,092백만원",
                        "source_row_id": "task_output:prior",
                        "source_row_ids": ["task_output:prior", "row_prior"],
                    },
                },
            },
        }
        final_state["subtask_results"] = [growth_row]
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [],
            "calculation_plan": {"status": "ok", "mode": "aggregate_subtasks"},
            "calculation_result": {
                "status": "ok",
                "operation_family": "aggregate_subtasks",
                "rendered_value": final_state["answer"],
                "formatted_result": final_state["answer"],
                "subtask_results": [growth_row],
                "answer_slots": {
                    "operation_family": "aggregate_subtasks",
                    "subtask_results": [growth_row],
                },
            },
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace_result = result["resolved_calculation_trace"]["calculation_result"]
        self.assertIn("84.3%", result["answer"])
        self.assertNotIn("-76.08%", result["answer"])
        self.assertTrue(trace_result["stale_result_repaired_from_evidence"])
        repaired_growth = trace_result["subtask_results"][0]["calculation_result"]
        self.assertEqual(repaired_growth["rendered_value"], "-84.3%")
        self.assertEqual(repaired_growth["answer_slots"]["current_value"]["raw_value"], "409,219")

    def test_run_prefers_supported_nested_aggregate_answer_over_stale_prefix(self) -> None:
        final_state = self._base_final_state()
        stale_answer = "2023 operating profit was 810,900백만원 versus 3,390,092백만원, down -76.08%."
        supported_answer = "The refining segment operating profit was 409,219백만원, down 84.3% year over year."
        final_state["answer"] = f"{stale_answer} {supported_answer}"
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [],
            "calculation_plan": {"status": "ok", "mode": "aggregate_subtasks"},
            "calculation_result": {
                "status": "ok",
                "operation_family": "aggregate_subtasks",
                "rendered_value": final_state["answer"],
                "formatted_result": final_state["answer"],
                "subtask_results": [
                    {
                        "task_id": "task_growth",
                        "operation_family": "growth_rate",
                        "answer": "-76.08%",
                        "status": "ok",
                        "calculation_result": {"status": "ok", "rendered_value": "-76.08%"},
                    },
                    {
                        "task_id": "task_narrative",
                        "operation_family": "aggregate_subtasks",
                        "answer": supported_answer,
                        "status": "ok",
                        "calculation_result": {
                            "status": "ok",
                            "operation_family": "aggregate_subtasks",
                            "rendered_value": supported_answer,
                            "formatted_result": supported_answer,
                        },
                    },
                ],
            },
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(result["answer"], supported_answer)
        self.assertNotIn("-76.08%", result["answer"])

    def test_run_repairs_collapsed_ratio_trace_from_dict_retrieved_doc(self) -> None:
        final_state = self._base_final_state()
        final_state["answer"] = "segment operating income ratio is 100%."
        final_state["evidence_items"] = []
        final_state["retrieved_docs"] = [
            {
                "page_content": "segment operating income (1)원 ... total operating income 51,988,692백만원",
                "metadata": {"section_path": "Unrelated section", "unit_hint": "백만원"},
            },
            {
                "page_content": "segment operating income 50.5% ... segment operating income 10백만원 ... operating income total 20백만원",
                "metadata": {"section_path": "Segment note", "unit_hint": "백만원"},
            }
        ]
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [
                {
                    "operand_id": "op_001",
                    "matched_operand_role": "numerator_1",
                    "raw_value": "5",
                    "raw_unit": "백만원",
                    "normalized_value": 5.0,
                    "normalized_unit": "KRW",
                    "source_row_id": "ev_same",
                },
                {
                    "operand_id": "op_002",
                    "matched_operand_role": "denominator_1",
                    "raw_value": "5",
                    "raw_unit": "백만원",
                    "normalized_value": 5.0,
                    "normalized_unit": "KRW",
                    "source_row_id": "ev_same",
                },
            ],
            "calculation_plan": {"status": "ok", "operation": "ratio"},
            "calculation_result": {
                "status": "ok",
                "result_value": 100.0,
                "result_unit": "%",
                "rendered_value": "100%",
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "segment operating income ratio",
                    "primary_value": {"status": "ok", "rendered_value": "100%"},
                    "components_by_group": {
                        "numerator": [
                            {
                                "status": "ok",
                                "role": "numerator_1",
                                "label": "segment operating income",
                                "raw_value": "5",
                                "raw_unit": "백만원",
                                "normalized_value": 5.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "5백만원",
                                "source_row_id": "ev_same",
                                "source_anchor": "Segment note",
                            }
                        ],
                        "denominator": [
                            {
                                "status": "ok",
                                "role": "denominator_1",
                                "label": "total operating income",
                                "concept": "operating_income",
                                "raw_value": "5",
                                "raw_unit": "백만원",
                                "normalized_value": 5.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "5백만원",
                                "source_row_id": "ev_same",
                                "source_anchor": "Segment note",
                            }
                        ],
                    },
                },
            },
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertIn("50%", result["answer"])
        trace_result = result["resolved_calculation_trace"]["calculation_result"]
        self.assertEqual(trace_result["rendered_value"], "50%")
        self.assertTrue(trace_result["stale_result_repaired_from_evidence"])

    def test_run_projects_llm_usage_by_phase_from_callback(self) -> None:
        final_state = self._base_final_state()
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm_usage_callback = GeminiUsageCallbackHandler()
        agent.llm_routes = {"default": object()}
        agent.graph = _PhaseUsageGraph(final_state, agent)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(result["llm_usage"]["api_calls"], 1)
        self.assertEqual(result["llm_usage"]["total_tokens"], 120)
        self.assertEqual(result["llm_usage_by_phase"]["numeric_extraction"]["api_calls"], 1)
        self.assertEqual(result["llm_usage_by_phase"]["numeric_extraction"]["prompt_tokens"], 100)
        self.assertEqual(result["llm_usage_by_phase"]["numeric_extraction"]["output_tokens"], 20)
        self.assertEqual(result["llm_usage_by_phase"]["numeric_extraction"]["total_tokens"], 120)

    def test_run_initial_state_does_not_seed_optional_calculation_mirrors(self) -> None:
        final_state = self._base_final_state()
        fake_graph = _FakeGraph(final_state)
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = fake_graph
        agent.vsm = object()

        agent.run("test question")

        self.assertNotIn("calculation_operands", fake_graph.initial_state)
        self.assertNotIn("calculation_plan", fake_graph.initial_state)
        self.assertNotIn("calculation_result", fake_graph.initial_state)
        self.assertNotIn("calculation_debug_trace", fake_graph.initial_state)

    def test_run_projects_calculation_debug_trace_under_debug_traces(self) -> None:
        final_state = self._base_final_state()
        final_state["calculation_debug_trace"] = {
            "source": "structured_row_direct",
            "coverage": "sufficient",
        }
        final_state["numeric_debug_trace_history"] = [
            {"numeric_extraction_prompt": {"selected_doc_count": 2}}
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(
            result["debug_traces"]["calculation"],
            {"source": "structured_row_direct", "coverage": "sufficient"},
        )
        self.assertNotIn("calculation_debug_trace", result)
        self.assertEqual(
            result["numeric_debug_trace_history"],
            [{"numeric_extraction_prompt": {"selected_doc_count": 2}}],
        )

    def test_run_debug_trace_projection_tolerates_missing_calculation_debug_trace(self) -> None:
        final_state = self._base_final_state()
        final_state.pop("calculation_debug_trace", None)
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(result["debug_traces"]["calculation"], {})
        self.assertNotIn("calculation_debug_trace", result)

    def test_run_public_projection_adds_read_only_report_cache_candidate(self) -> None:
        final_state = self._base_final_state()
        final_state["report_scope"] = {
            "company": "ACME",
            "report_type": "annual",
            "rcept_no": "r1",
            "year": "2023",
        }
        final_state["active_subtask"] = {
            "metric_family": "metric_family",
            "metric_label": "metric label",
        }
        final_state["resolved_calculation_trace"]["calculation_operands"] = [
            {
                "label": "metric",
                "raw_value": "123",
                "period": "2023",
                "consolidation_scope": "consolidated",
                "statement_type": "statement",
                "source_section": "section",
                "table_source_id": "table-1",
                "source_row_id": "row-1",
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        candidate = result["resolved_calculation_trace"]["report_cache_candidate"]
        self.assertTrue(candidate["read_only"])
        self.assertEqual(candidate["status"], "reusable")
        self.assertEqual(candidate["key"]["company"], "ACME")
        self.assertEqual(candidate["key"]["metric_label"], "metric label")

    def test_run_public_projection_rejects_legacy_top_level_trace(self) -> None:
        final_state = self._base_final_state()
        final_state["resolved_calculation_trace"] = {}
        final_state["structured_result"] = {}
        final_state["calculation_operands"] = [{"label": "legacy", "value": "25.4"}]
        final_state["calculation_plan"] = {"status": "ok", "operation": "lookup"}
        final_state["calculation_result"] = {
            "status": "ok",
            "rendered_value": "25.4%",
            "answer_slots": {"operation_family": "lookup"},
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(result["resolved_calculation_trace"], {})
        self.assertEqual(result["structured_result"], {})
        self.assertNotIn("calculation_operands", result)
        self.assertNotIn("calculation_plan", result)
        self.assertNotIn("calculation_result", result)

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

    def test_run_compacts_large_runtime_evidence_metadata(self) -> None:
        final_state = self._base_final_state()
        final_state["report_scope"] = {"company": "ExampleCo", "year": 2023}
        final_state["evidence_items"] = [
            {
                "evidence_id": "ev_existing",
                "source_anchor": "Financial review",
                "claim": "Metric value is 25.4%.",
                "quote_span": "Metric value is 25.4%.",
                "metadata": {
                    "section_path": "Financial review",
                    "table_object_json": "{" + ("x" * 50_000) + "}",
                    "table_value_records_json": "[" + ("y" * 30_000) + "]",
                    "table_row_records_json": '[{"row_label":"Metric","cells":[{"value_text":"25.4%"}]}]',
                    "table_value_labels_text": "Metric 25.4%",
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        metadata = result["evidence_items"][0]["metadata"]
        self.assertNotIn("table_object_json", metadata)
        self.assertNotIn("table_value_records_json", metadata)
        self.assertIn("table_row_records_json", metadata)
        self.assertEqual(metadata["company"], "ExampleCo")
        self.assertEqual(metadata["year"], 2023)
        self.assertEqual(
            metadata["metadata_compacted_fields"],
            ["table_object_json", "table_value_records_json"],
        )

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

    def test_run_projects_operand_runtime_evidence_with_report_scope_metadata(self) -> None:
        final_state = self._base_final_state()
        final_state["report_scope"] = {"company": "NAVER", "year": 2023}
        final_state["companies"] = ["NAVER"]
        final_state["years"] = [2023]
        final_state["answer"] = (
            "네이버의 2023년 연결기준 잉여현금흐름은 1조 3,616억원입니다. "
            "이는 영업활동현금흐름 2조 22억원에서 유형자산 취득액 6,406억원을 "
            "차감하여 계산된 결과입니다."
        )
        final_state["citations"] = []
        final_state["evidence_items"] = []
        final_state["retrieved_docs"] = []
        final_state["resolved_calculation_trace"] = {
            "calculation_operands": [
                {
                    "operand_id": "operating_cash_flow",
                    "label": "2023 영업활동현금흐름",
                    "raw_value": "2,002,233,273,518",
                    "raw_unit": "원",
                    "rendered_value": "2조 22억원",
                    "normalized_unit": "KRW",
                    "matched_operand_role": "minuend",
                    "source_anchor": "III. 재무에 관한 사항 > 연결현금흐름표",
                    "source_quote": "영업활동현금흐름 2,002,233,273,518원",
                },
                {
                    "operand_id": "ppe_acquisition",
                    "label": "2023 유형자산 취득액",
                    "raw_value": "(640,623,697,250)",
                    "raw_unit": "원",
                    "rendered_value": "6,406억원",
                    "normalized_unit": "KRW",
                    "matched_operand_role": "subtrahend",
                    "source_anchor": "III. 재무에 관한 사항 > 연결현금흐름표",
                    "source_quote": "유형자산의 취득 (640,623,697,250)원",
                },
            ],
            "calculation_plan": {"operation": "subtract"},
            "calculation_result": {
                "status": "ok",
                "rendered_value": "1조 3,616억원",
                "answer_slots": {"operation_family": "difference"},
            },
        }
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        evidence_ids = [item["evidence_id"] for item in result["evidence_items"]]
        self.assertEqual(evidence_ids, ["operand::operating_cash_flow", "operand::ppe_acquisition"])
        self.assertTrue(all(item["metadata"]["company"] == "NAVER" for item in result["evidence_items"]))
        self.assertTrue(all(item["metadata"]["year"] == 2023 for item in result["evidence_items"]))
        self.assertTrue(any("NAVER | 2023 | III. 재무에 관한 사항" in item for item in result["citations"]))

    def test_run_projects_task_artifact_trace_for_callers(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_1",
                "kind": "calculation",
                "label": "ratio calculation",
                "status": "completed",
                "metric_family": "ratio",
                "artifact_ids": ["artifact_1", "artifact_missing"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_1",
                "task_id": "task_1",
                "kind": "calculation_result",
                "status": "ok",
                "summary": "25.4%",
                "payload": {"calculation_result": {"rendered_value": "25.4%"}},
                "evidence_refs": ["ev_001"],
            },
            {
                "artifact_id": "artifact_orphan",
                "task_id": "missing_task",
                "kind": "operand_set",
                "status": "ok",
                "summary": "unused",
                "payload": {"calculation_operands": []},
                "evidence_refs": [],
            },
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        self.assertEqual(result["tasks"], final_state["tasks"])
        self.assertEqual(result["artifacts"], final_state["artifacts"])
        trace = result["task_artifact_trace"]
        self.assertEqual(trace["task_count"], 1)
        self.assertEqual(trace["artifact_count"], 2)
        self.assertEqual(trace["tasks"][0]["latest_artifact_id"], "artifact_1")
        self.assertEqual(trace["tasks"][0]["latest_artifact_summary"], "25.4%")
        self.assertEqual(trace["artifacts"][0]["payload_keys"], ["calculation_result"])
        self.assertEqual(trace["orphan_artifact_ids"], ["artifact_orphan"])
        self.assertEqual(trace["missing_artifact_ids"], ["artifact_missing"])
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            [
                "missing_artifact_reference",
                "orphan_artifact",
                "missing_required_artifact_kind",
                "missing_required_artifact_kind",
            ],
        )
        self.assertEqual(
            [
                issue.get("artifact_kind")
                for issue in trace["integrity_issues"]
                if issue["type"] == "missing_required_artifact_kind"
            ],
            ["calculation_plan", "operand_set"],
        )

    def test_run_marks_completed_calculation_without_artifacts_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_1",
                "kind": "calculation",
                "label": "ratio calculation",
                "status": "completed",
                "metric_family": "ratio",
                "artifact_ids": [],
            }
        ]
        final_state["artifacts"] = []
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issue_count"], 5)
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            [
                "task_without_artifacts",
                "missing_required_artifact_kind",
                "missing_required_artifact_kind",
                "missing_required_artifact_kind",
                "missing_required_evidence_ref",
            ],
        )
        self.assertEqual(
            [
                issue.get("artifact_kind")
                for issue in trace["integrity_issues"]
                if issue["type"] == "missing_required_artifact_kind"
            ],
            ["calculation_plan", "calculation_result", "operand_set"],
        )

    def test_run_marks_completed_calculation_with_empty_payloads_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_1",
                "kind": "calculation",
                "label": "ratio calculation",
                "status": "completed",
                "metric_family": "ratio",
                "artifact_ids": ["artifact_operand", "artifact_plan", "artifact_result"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_operand",
                "task_id": "task_1",
                "kind": "operand_set",
                "status": "ok",
                "payload": {"calculation_operands": []},
            },
            {
                "artifact_id": "artifact_plan",
                "task_id": "task_1",
                "kind": "calculation_plan",
                "status": "ok",
                "payload": {"calculation_plan": {"status": "ok"}},
            },
            {
                "artifact_id": "artifact_result",
                "task_id": "task_1",
                "kind": "calculation_result",
                "status": "ok",
                "payload": {"calculation_result": {"status": "ok"}},
            },
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            [
                "missing_required_artifact_payload",
                "missing_required_artifact_payload",
                "missing_required_artifact_payload",
                "missing_required_evidence_ref",
            ],
        )
        self.assertEqual(
            [
                issue.get("payload_key")
                for issue in trace["integrity_issues"]
                if issue["type"] == "missing_required_artifact_payload"
            ],
            [
                "calculation_operands",
                "calculation_plan.operation",
                "calculation_result.rendered_value_or_answer_slots",
            ],
        )

    def test_run_marks_completed_reconciliation_without_result_artifact_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reconcile",
                "kind": "reconciliation",
                "label": "reconcile operands",
                "status": "completed",
                "artifact_ids": [],
            }
        ]
        final_state["artifacts"] = []
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["task_without_artifacts", "missing_required_artifact_kind"],
        )
        self.assertEqual(trace["integrity_issues"][1]["artifact_kind"], "reconciliation_result")

    def test_run_marks_reconciliation_result_without_status_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reconcile",
                "kind": "reconciliation",
                "label": "reconcile operands",
                "status": "completed",
                "artifact_ids": ["artifact_reconcile"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_reconcile",
                "task_id": "task_reconcile",
                "kind": "reconciliation_result",
                "status": "ok",
                "payload": {"reconciliation_result": {}},
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "missing_required_artifact_payload")
        self.assertEqual(trace["integrity_issues"][0]["payload_key"], "reconciliation_result.status")

    def test_run_marks_ready_reconciliation_without_provenance_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reconcile",
                "kind": "reconciliation",
                "label": "reconcile operands",
                "status": "completed",
                "artifact_ids": ["artifact_reconcile"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_reconcile",
                "task_id": "task_reconcile",
                "kind": "reconciliation_result",
                "status": "ok",
                "payload": {"reconciliation_result": {"status": "ready", "matched_operands": []}},
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "missing_required_evidence_ref")
        self.assertEqual(trace["integrity_issues"][0]["task_kind"], "reconciliation")

    def test_run_accepts_ready_reconciliation_with_candidate_provenance(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reconcile",
                "kind": "reconciliation",
                "label": "reconcile operands",
                "status": "completed",
                "artifact_ids": ["artifact_reconcile"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_reconcile",
                "task_id": "task_reconcile",
                "kind": "reconciliation_result",
                "status": "ok",
                "payload": {
                    "reconciliation_result": {
                        "status": "ready",
                        "matched_operands": [{"candidate_ids": ["ev_001"]}],
                    }
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["integrity_issues"], [])

    def test_run_marks_completed_retrieval_without_bundle_artifact_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_retrieve",
                "kind": "retrieval",
                "label": "retrieve evidence",
                "status": "completed",
                "artifact_ids": [],
            }
        ]
        final_state["artifacts"] = []
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["task_without_artifacts", "missing_required_artifact_kind", "missing_required_evidence_ref"],
        )
        self.assertEqual(trace["integrity_issues"][1]["artifact_kind"], "retrieval_bundle")

    def test_run_marks_empty_retrieval_bundle_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_retrieve",
                "kind": "retrieval",
                "label": "retrieve evidence",
                "status": "completed",
                "artifact_ids": ["artifact_retrieve"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_retrieve",
                "task_id": "task_retrieve",
                "kind": "retrieval_bundle",
                "status": "ok",
                "payload": {"retrieved_docs": []},
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["missing_required_artifact_payload", "missing_required_evidence_ref"],
        )
        self.assertEqual(trace["integrity_issues"][0]["payload_key"], "retrieval_bundle.items")

    def test_run_accepts_retrieval_bundle_with_chunk_provenance(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_retrieve",
                "kind": "retrieval",
                "label": "retrieve evidence",
                "status": "completed",
                "artifact_ids": ["artifact_retrieve"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_retrieve",
                "task_id": "task_retrieve",
                "kind": "retrieval_bundle",
                "status": "ok",
                "payload": {"retrieved_docs": [{"chunk_id": "chunk_001", "text": "supporting evidence"}]},
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["integrity_issues"], [])

    def test_run_marks_completed_synthesis_without_aggregated_answer_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_synthesis",
                "kind": "synthesis",
                "label": "final merge",
                "status": "completed",
                "artifact_ids": [],
            }
        ]
        final_state["artifacts"] = []
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["task_without_artifacts", "missing_required_artifact_kind", "missing_required_evidence_ref"],
        )
        self.assertEqual(trace["integrity_issues"][1]["artifact_kind"], "aggregated_answer")

    def test_run_marks_text_only_synthesis_answer_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_synthesis",
                "kind": "synthesis",
                "label": "final merge",
                "status": "completed",
                "artifact_ids": ["artifact_synthesis"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_synthesis",
                "task_id": "task_synthesis",
                "kind": "aggregated_answer",
                "status": "ok",
                "payload": {"final_answer": "최종 답변입니다."},
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["missing_required_artifact_payload", "missing_required_evidence_ref"],
        )
        self.assertEqual(trace["integrity_issues"][0]["payload_key"], "aggregated_answer.source_material")

    def test_run_accepts_synthesis_answer_with_source_and_evidence_refs(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_synthesis",
                "kind": "synthesis",
                "label": "final merge",
                "status": "completed",
                "artifact_ids": ["artifact_synthesis"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_synthesis",
                "task_id": "task_synthesis",
                "kind": "aggregated_answer",
                "status": "ok",
                "payload": {
                    "final_answer": "최종 답변입니다.",
                    "subtask_results": [{"task_id": "task_1", "answer": "근거 답변"}],
                },
                "evidence_refs": ["ev_001"],
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["integrity_issues"], [])

    def test_run_marks_completed_reflection_without_report_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reflection",
                "kind": "reflection",
                "label": "reflect retry",
                "status": "completed",
                "artifact_ids": [],
            }
        ]
        final_state["artifacts"] = []
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["task_without_artifacts", "missing_required_artifact_kind"],
        )
        self.assertEqual(trace["integrity_issues"][1]["artifact_kind"], "reflection_report")

    def test_run_accepts_reflection_report_handoff_without_evidence_refs(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reflection",
                "kind": "reflection",
                "label": "reflect retry",
                "status": "completed",
                "artifact_ids": ["artifact_reflection"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_reflection",
                "task_id": "task_reflection",
                "kind": "reflection_report",
                "status": "retry_prepared",
                "payload": {
                    "reflection_report": {
                        "outcome": "retry_prepared",
                        "action_taken": "retry_retrieval",
                        "budget_consumed": 1,
                        "target_task_ids": ["task_1"],
                        "target_artifact_ids": [],
                        "blocking_issues": [],
                    },
                    "reflection_action": {
                        "action_type": "retry_retrieval",
                        "retry_queries": ["find missing value"],
                        "retrieval_scope_hints": [],
                        "synthesis_source_ids": [],
                        "stop_reason": "",
                    },
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["integrity_issues"], [])

    def test_run_marks_reflection_report_without_action_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reflection",
                "kind": "reflection",
                "label": "reflect retry",
                "status": "completed",
                "artifact_ids": ["artifact_reflection"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_reflection",
                "task_id": "task_reflection",
                "kind": "reflection_report",
                "status": "retry_prepared",
                "payload": {
                    "reflection_report": {
                        "outcome": "retry_prepared",
                        "budget_consumed": 1,
                    }
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "missing_required_artifact_payload")
        self.assertEqual(trace["integrity_issues"][0]["payload_key"], "reflection_report.action_taken")

    def test_run_marks_retry_reflection_without_retry_queries_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reflection",
                "kind": "reflection",
                "label": "reflect retry",
                "status": "completed",
                "artifact_ids": ["artifact_reflection"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_reflection",
                "task_id": "task_reflection",
                "kind": "reflection_report",
                "status": "retry_prepared",
                "payload": {
                    "reflection_report": {
                        "outcome": "retry_prepared",
                        "action_taken": "retry_retrieval",
                        "budget_consumed": 1,
                    },
                    "reflection_action": {
                        "action_type": "retry_retrieval",
                        "retry_queries": [],
                    },
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "missing_required_artifact_payload")
        self.assertEqual(trace["integrity_issues"][0]["payload_key"], "reflection_action.retry_queries")

    def test_run_marks_synthesis_reflection_without_source_ids_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_reflection",
                "kind": "reflection",
                "label": "reflect synthesis",
                "status": "completed",
                "artifact_ids": ["artifact_reflection"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_reflection",
                "task_id": "task_reflection",
                "kind": "reflection_report",
                "status": "retry_prepared",
                "payload": {
                    "reflection_report": {
                        "outcome": "retry_prepared",
                        "action_taken": "synthesize_from_task_outputs",
                        "budget_consumed": 1,
                    },
                    "reflection_action": {
                        "action_type": "synthesize_from_task_outputs",
                        "synthesis_source_ids": [],
                    },
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "missing_required_artifact_payload")
        self.assertEqual(
            trace["integrity_issues"][0]["payload_key"],
            "reflection_action.synthesis_source_ids",
        )

    def test_run_marks_completed_critic_without_report_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_critic",
                "kind": "critic",
                "label": "review outputs",
                "status": "completed",
                "artifact_ids": [],
            }
        ]
        final_state["artifacts"] = []
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["task_without_artifacts", "missing_required_artifact_kind", "missing_required_evidence_ref"],
        )
        self.assertEqual(trace["integrity_issues"][1]["artifact_kind"], "critic_report")

    def test_run_marks_critic_report_without_verdict_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_critic",
                "kind": "critic",
                "label": "review outputs",
                "status": "completed",
                "artifact_ids": ["artifact_critic"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_critic",
                "task_id": "task_critic",
                "kind": "critic_report",
                "status": "ok",
                "payload": {
                    "critic_report": {
                        "target_task_id": "task_synthesis",
                        "acceptance_reason": "grounded",
                    }
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "missing_required_artifact_payload")
        self.assertEqual(trace["integrity_issues"][0]["payload_key"], "critic_report.verdict")

    def test_run_marks_critic_report_without_target_refs_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_critic",
                "kind": "critic",
                "label": "review outputs",
                "status": "completed",
                "artifact_ids": ["artifact_critic"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_critic",
                "task_id": "task_critic",
                "kind": "critic_report",
                "status": "ok",
                "payload": {
                    "critic_report": {
                        "passed": True,
                        "verdict": "passed",
                        "acceptance_reason": "grounded",
                    }
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "missing_required_artifact_payload")
        self.assertEqual(trace["integrity_issues"][0]["payload_key"], "critic_report.target_refs")

    def test_run_marks_critic_report_without_reason_or_issues_as_integrity_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_critic",
                "kind": "critic",
                "label": "review outputs",
                "status": "completed",
                "artifact_ids": ["artifact_critic"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_critic",
                "task_id": "task_critic",
                "kind": "critic_report",
                "status": "ok",
                "payload": {
                    "critic_report": {
                        "passed": True,
                        "verdict": "passed",
                        "target_task_id": "task_synthesis",
                    }
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "missing_required_artifact_payload")
        self.assertEqual(
            trace["integrity_issues"][0]["payload_key"],
            "critic_report.acceptance_reason_or_issues",
        )

    def test_run_accepts_critic_report_with_target_reason_and_provenance(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_critic",
                "kind": "critic",
                "label": "review outputs",
                "status": "completed",
                "artifact_ids": ["artifact_critic"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_critic",
                "task_id": "task_critic",
                "kind": "critic_report",
                "status": "ok",
                "payload": {
                    "critic_report": {
                        "passed": True,
                        "verdict": "passed",
                        "target_task_id": "task_synthesis",
                        "target_artifact_ids": ["artifact_synthesis"],
                        "acceptance_reason": "grounded",
                    }
                },
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "ok")
        self.assertEqual(trace["integrity_issues"], [])

    def test_run_blocks_rejected_critic_report_even_with_high_score(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_1",
                "kind": "retrieval",
                "label": "retrieve evidence",
                "status": "completed",
                "artifact_ids": ["artifact_1"],
            },
            {
                "task_id": "task_critic",
                "kind": "critic",
                "label": "review outputs",
                "status": "completed",
                "artifact_ids": ["artifact_critic"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_1",
                "task_id": "task_1",
                "kind": "retrieval_bundle",
                "status": "ok",
                "payload": {"retrieval_bundle": {"retrieved_docs": [{"id": "doc_1"}]}},
                "evidence_refs": ["doc_1"],
            },
            {
                "artifact_id": "artifact_critic",
                "task_id": "task_critic",
                "kind": "critic_report",
                "status": "rejected",
                "payload": {
                    "critic_report": {
                        "passed": False,
                        "verdict": "rejected",
                        "target_task_id": "task_1",
                        "target_artifact_ids": ["artifact_1"],
                        "blocking_issues": ["missing evidence"],
                        "deterministic_score": 1.0,
                    }
                },
                "evidence_refs": ["artifact_1"],
            }
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(trace["integrity_issues"][0]["type"], "critic_report_rejected")
        self.assertEqual(
            trace["integrity_issues"][0]["runtime_acceptance_status"],
            "blocked",
        )
        self.assertIn("critic_rejected", trace["integrity_issues"][0]["reasons"])
        self.assertEqual(trace["integrity_issues"][0]["target_task_ids"], ["task_1"])
        self.assertEqual(
            trace["integrity_issues"][0]["target_artifact_ids"],
            ["artifact_1"],
        )

    def test_run_keeps_orphan_artifact_warning_non_blocking_when_not_final_source(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_review",
                "kind": "verification",
                "label": "review",
                "status": "completed",
                "artifact_ids": ["artifact_review"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_review",
                "task_id": "task_review",
                "kind": "semantic_plan",
                "status": "ok",
                "payload": {"status": "ok"},
            },
            {
                "artifact_id": "artifact_orphan",
                "task_id": "missing_task",
                "kind": "semantic_plan",
                "status": "ok",
                "payload": {"status": "ok"},
            },
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "warning")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["orphan_artifact"],
        )

    def test_run_promotes_final_source_orphan_artifact_warning_to_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_synthesis",
                "kind": "synthesis",
                "label": "final merge",
                "status": "completed",
                "artifact_ids": ["artifact_synthesis"],
            }
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_synthesis",
                "task_id": "task_synthesis",
                "kind": "aggregated_answer",
                "status": "ok",
                "payload": {
                    "final_answer": "최종 답변입니다.",
                    "source_artifact_ids": ["artifact_orphan"],
                },
                "evidence_refs": ["artifact_orphan"],
            },
            {
                "artifact_id": "artifact_orphan",
                "task_id": "missing_task",
                "kind": "semantic_plan",
                "status": "ok",
                "payload": {"status": "ok"},
            },
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["orphan_artifact", "final_source_orphan_artifact"],
        )
        self.assertEqual(trace["integrity_issues"][1]["artifact_id"], "artifact_orphan")

    def test_run_promotes_final_source_task_without_artifacts_warning_to_error(self) -> None:
        final_state = self._base_final_state()
        final_state["tasks"] = [
            {
                "task_id": "task_source",
                "kind": "verification",
                "label": "source review",
                "status": "completed",
                "artifact_ids": [],
            },
            {
                "task_id": "task_synthesis",
                "kind": "synthesis",
                "label": "final merge",
                "status": "completed",
                "artifact_ids": ["artifact_synthesis"],
            },
        ]
        final_state["artifacts"] = [
            {
                "artifact_id": "artifact_synthesis",
                "task_id": "task_synthesis",
                "kind": "aggregated_answer",
                "status": "ok",
                "payload": {
                    "final_answer": "최종 답변입니다.",
                    "source_task_ids": ["task_source"],
                },
                "evidence_refs": ["ev_001"],
            },
        ]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.graph = _FakeGraph(final_state)
        agent.vsm = object()

        result = agent.run("test question")

        trace = result["task_artifact_trace"]
        self.assertEqual(trace["integrity_status"], "error")
        self.assertEqual(
            [issue["type"] for issue in trace["integrity_issues"]],
            ["task_without_artifacts", "final_source_task_without_artifacts"],
        )
        self.assertEqual(trace["integrity_issues"][1]["task_id"], "task_source")


if __name__ == "__main__":
    unittest.main()
