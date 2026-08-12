import ast
import inspect
import json
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import src.agent.financial_graph as financial_graph
import src.agent.financial_agent_run_projection as financial_agent_run_projection
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import FinancialAgentCalculationMixin
from src.agent.financial_graph_reconciliation import FinancialAgentReconciliationMixin
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
    def test_graph_shell_owns_conditional_route_methods(self) -> None:
        route_methods = {
            "_route_after_prepare_retry",
            "_route_after_expand",
            "_route_after_numeric_extractor",
            "_route_after_evidence",
            "_route_after_reconcile_plan",
            "_route_after_advance_subtask",
            "_route_after_aggregate_subtasks",
            "_route_after_validate",
            "_route_after_formula_planner",
            "_route_after_calculator",
        }

        self.assertTrue(route_methods.issubset(FinancialAgent.__dict__))
        self.assertTrue(route_methods.isdisjoint(FinancialAgentCalculationMixin.__dict__))
        self.assertIn("_active_retry_strategy", FinancialAgent.__dict__)
        self.assertNotIn("_active_retry_strategy", FinancialAgentCalculationMixin.__dict__)
        self.assertIn("_is_reflection_eligible", FinancialAgent.__dict__)
        self.assertNotIn("_is_reflection_eligible", FinancialAgentReconciliationMixin.__dict__)

    def test_graph_shell_route_matrix_preserves_branch_precedence_and_canonical_trace_boundary(self) -> None:
        canonical_incomplete_plan = {
            "resolved_calculation_trace": {"calculation_plan": {"status": "incomplete"}}
        }
        canonical_ok_plan = {
            "resolved_calculation_trace": {"calculation_plan": {"status": "ok"}}
        }
        canonical_insufficient_result = {
            "resolved_calculation_trace": {"calculation_result": {"status": "insufficient_operands"}}
        }
        canonical_parse_error_result = {
            "resolved_calculation_trace": {"calculation_result": {"status": "parse_error"}}
        }
        canonical_ok_result = {
            "resolved_calculation_trace": {"calculation_result": {"status": "ok"}}
        }
        cases = [
            (
                "prepare_synthesis",
                "_route_after_prepare_retry",
                {"retry_strategy": "synthesize_from_task_outputs"},
                "operand_extractor",
            ),
            ("prepare_default", "_route_after_prepare_retry", {}, "retrieve"),
            (
                "expand_narrative_priority",
                "_route_after_expand",
                {"active_subtask": {"operation_family": "narrative_summary"}, "calc_subtasks": [{}]},
                "evidence",
            ),
            (
                "expand_loop_lookup",
                "_route_after_expand",
                {"active_subtask": {"operation_family": "lookup"}, "calc_subtasks": [{}]},
                "numeric_extractor",
            ),
            (
                "expand_loop_arithmetic",
                "_route_after_expand",
                {"active_subtask": {"operation_family": "ratio"}, "calc_subtasks": [{}]},
                "evidence",
            ),
            ("expand_numeric", "_route_after_expand", {"intent": "numeric_fact"}, "numeric_extractor"),
            ("expand_default", "_route_after_expand", {}, "evidence"),
            (
                "numeric_lookup_missing_with_docs",
                "_route_after_numeric_extractor",
                {
                    "active_subtask": {"operation_family": "lookup"},
                    "calc_subtasks": [{}],
                    "evidence_status": "missing",
                    "retrieved_docs": ["doc"],
                },
                "reconcile_plan",
            ),
            (
                "numeric_loop_default",
                "_route_after_numeric_extractor",
                {"active_subtask": {"operation_family": "ratio"}, "calc_subtasks": [{}]},
                "advance_subtask",
            ),
            ("numeric_no_loop", "_route_after_numeric_extractor", {}, "cite"),
            (
                "evidence_narrative_priority",
                "_route_after_evidence",
                {"active_subtask": {"operation_family": "narrative_summary"}, "calc_subtasks": [{}]},
                "compress",
            ),
            ("evidence_loop", "_route_after_evidence", {"calc_subtasks": [{}]}, "reconcile_plan"),
            ("evidence_comparison", "_route_after_evidence", {"intent": "comparison"}, "reconcile_plan"),
            ("evidence_default", "_route_after_evidence", {}, "compress"),
            (
                "reconcile_ready",
                "_route_after_reconcile_plan",
                {"reconciliation_result": {"status": "ready"}},
                "operand_extractor",
            ),
            (
                "reconcile_synthesis_override",
                "_route_after_reconcile_plan",
                {"reconciliation_result": {"status": "insufficient_operands", "retry_strategy": "synthesize_from_task_outputs"}},
                "operand_extractor",
            ),
            (
                "reconcile_retry",
                "_route_after_reconcile_plan",
                {"reconciliation_result": {"status": "retry_retrieval"}},
                "retrieve",
            ),
            (
                "reconcile_insufficient_fillable",
                "_route_after_reconcile_plan",
                {
                    "reconciliation_result": {"status": "insufficient_operands"},
                    "active_subtask": {
                        "operation_family": "narrative_summary",
                        "required_operands": [{"label": "value"}],
                    },
                    "retrieved_docs": ["doc"],
                },
                "operand_extractor",
            ),
            (
                "reconcile_insufficient_direct_grounding",
                "_route_after_reconcile_plan",
                {
                    "reconciliation_result": {"status": "insufficient_operands"},
                    "active_subtask": {
                        "operation_family": "lookup",
                        "required_operands": [{"label": "value"}],
                    },
                    "retrieved_docs": ["doc"],
                },
                "advance_subtask",
            ),
            (
                "reconcile_default",
                "_route_after_reconcile_plan",
                {"reconciliation_result": {"status": "stopped"}},
                "advance_subtask",
            ),
            (
                "advance_complete",
                "_route_after_advance_subtask",
                {"subtask_loop_complete": True},
                "aggregate_subtasks",
            ),
            (
                "advance_lookup",
                "_route_after_advance_subtask",
                {"active_subtask": {"operation_family": "lookup"}},
                "retrieve",
            ),
            (
                "advance_arithmetic",
                "_route_after_advance_subtask",
                {"active_subtask": {"operation_family": "ratio"}},
                "reconcile_plan",
            ),
            (
                "aggregate_exclusive_priority",
                "_route_after_aggregate_subtasks",
                {
                    "semantic_plan": {"status": "narrative_policy_exclusive"},
                    "planner_feedback": "retry",
                },
                "cite",
            ),
            (
                "aggregate_feedback",
                "_route_after_aggregate_subtasks",
                {"planner_feedback": "retry", "plan_loop_count": 0},
                "pre_calc_planner",
            ),
            (
                "aggregate_blocked",
                "_route_after_aggregate_subtasks",
                {"planner_feedback": "retry", "replan_blocked_reason": "blocked"},
                "cite",
            ),
            ("aggregate_default", "_route_after_aggregate_subtasks", {}, "cite"),
            (
                "validate_narrative_loop",
                "_route_after_validate",
                {"active_subtask": {"operation_family": "narrative_summary"}, "calc_subtasks": [{}]},
                "advance_subtask",
            ),
            ("validate_default", "_route_after_validate", {}, "cite"),
            (
                "formula_ineligible",
                "_route_after_formula_planner",
                {"intent": "qa", **canonical_incomplete_plan},
                "calculator",
            ),
            (
                "formula_retry_exhausted",
                "_route_after_formula_planner",
                {"intent": "comparison", "reflection_count": 1, **canonical_incomplete_plan},
                "calculator",
            ),
            (
                "formula_canonical_incomplete",
                "_route_after_formula_planner",
                {"intent": "comparison", "calculation_plan": {"status": "ok"}, **canonical_incomplete_plan},
                "reflection_replan",
            ),
            (
                "formula_ignores_legacy_incomplete",
                "_route_after_formula_planner",
                {"intent": "comparison", "calculation_plan": {"status": "incomplete"}, **canonical_ok_plan},
                "calculator",
            ),
            (
                "calculator_ineligible",
                "_route_after_calculator",
                {"intent": "qa", **canonical_insufficient_result},
                "calc_render",
            ),
            (
                "calculator_retry_exhausted",
                "_route_after_calculator",
                {"intent": "comparison", "reflection_count": 1, **canonical_insufficient_result},
                "calc_render",
            ),
            (
                "calculator_canonical_insufficient",
                "_route_after_calculator",
                {"intent": "comparison", "calculation_result": {"status": "ok"}, **canonical_insufficient_result},
                "reflection_replan",
            ),
            (
                "calculator_canonical_parse_error",
                "_route_after_calculator",
                {"intent": "trend", **canonical_parse_error_result},
                "reflection_replan",
            ),
            (
                "calculator_ignores_legacy_error",
                "_route_after_calculator",
                {"intent": "comparison", "calculation_result": {"status": "parse_error"}, **canonical_ok_result},
                "calc_render",
            ),
        ]
        agent = FinancialAgent.__new__(FinancialAgent)

        for name, method_name, state, expected in cases:
            with self.subTest(name=name):
                original = deepcopy(state)
                self.assertEqual(getattr(agent, method_name)(state), expected)
                self.assertEqual(state, original)

    def test_build_graph_resolves_state_type_hints_for_langgraph_routes(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)

        graph = FinancialAgent._build_graph(agent)

        self.assertIsNotNone(graph)
        conditional_edges = {
            (edge.source, edge.target)
            for edge in graph.get_graph().edges
            if edge.conditional
        }
        self.assertEqual(
            conditional_edges,
            {
                ("expand", "numeric_extractor"),
                ("expand", "evidence"),
                ("numeric_extractor", "reconcile_plan"),
                ("numeric_extractor", "advance_subtask"),
                ("numeric_extractor", "cite"),
                ("evidence", "reconcile_plan"),
                ("evidence", "compress"),
                ("reconcile_plan", "operand_extractor"),
                ("reconcile_plan", "retrieve"),
                ("reconcile_plan", "advance_subtask"),
                ("formula_planner", "reflection_replan"),
                ("formula_planner", "calculator"),
                ("prepare_retry", "operand_extractor"),
                ("prepare_retry", "retrieve"),
                ("calculator", "reflection_replan"),
                ("calculator", "calc_render"),
                ("advance_subtask", "reconcile_plan"),
                ("advance_subtask", "retrieve"),
                ("advance_subtask", "evidence"),
                ("advance_subtask", "aggregate_subtasks"),
                ("aggregate_subtasks", "pre_calc_planner"),
                ("aggregate_subtasks", "cite"),
                ("validate", "advance_subtask"),
                ("validate", "cite"),
            },
        )

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

    def test_structured_result_projection_uses_numeric_coverage_owner_at_replacement_boundary(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        public_answer = "target share is 10%."
        replacement_answer = "target share is 20%."
        row = {
            "task_id": "task_ratio",
            "operation_family": "ratio",
            "answer": replacement_answer,
            "calculation_result": {
                "status": "ok",
                "formatted_result": replacement_answer,
            },
        }
        structured_result = {"subtask_results": [row]}
        projection = {
            "calculation_result": {
                "status": "ok",
                "subtask_results": [row],
            }
        }
        replacement_builder = Mock(return_value=replacement_answer)
        coverage = Mock(side_effect=(False, True, True, RuntimeError("coverage owner failed")))
        projection_builder = Mock(return_value=projection)

        def project_result(structured=structured_result):
            return agent._structured_result_projection_for_stale_public_numeric_answer(
                {"query": "target share"},
                public_answer=public_answer,
                structured_result=structured,
                evidence_items=[],
            )

        with patch.object(
            agent,
            "_complete_numeric_projection_replacement_answer",
            replacement_builder,
        ), patch.multiple(
            financial_graph,
            answer_covers_numeric_answer=coverage,
            _build_aggregate_calculation_projection=projection_builder,
        ):
            self.assertEqual(project_result({}), ("", {}))
            replacement_builder.assert_not_called()
            coverage.assert_not_called()

            answer, projected = project_result()
            self.assertEqual(project_result(), ("", {}))
            with self.assertRaisesRegex(RuntimeError, "coverage owner failed"):
                project_result()

        self.assertEqual(
            [item.args for item in coverage.call_args_list],
            [
                (public_answer, replacement_answer),
                (public_answer, replacement_answer),
                (replacement_answer, public_answer),
                (public_answer, replacement_answer),
            ],
        )
        projection_builder.assert_called_once_with([row], replacement_answer)
        self.assertEqual(answer, replacement_answer)
        self.assertEqual(projected["calculation_result"]["subtask_results"], [row])
        self.assertEqual(projected["runtime_projection"]["source"], "structured_result_subtasks")

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

    def test_current_source_run_projection_seam_a_defaults_and_metadata_compaction_contract(self) -> None:
        nested = {"preserve": True}

        class IterationBomb:
            def __iter__(self):
                raise AssertionError("fallback list should stay lazy")

            def __deepcopy__(self, _memo):
                return self

        scoped_final = {
            "report_scope": {"company": "  Scope Co  ", "year": 0, "nested": nested},
            "companies": IterationBomb(),
            "years": IterationBomb(),
        }
        before_scoped = deepcopy(scoped_final)

        scoped = financial_agent_run_projection._runtime_evidence_defaults(scoped_final)

        self.assertEqual(scoped, {"company": "Scope Co", "year": 0})
        self.assertEqual(scoped_final, before_scoped)
        self.assertIs(scoped_final["report_scope"]["nested"], nested)

        fallback_final = {
            "report_scope": {"company": "   ", "year": ""},
            "companies": ["", "  Fallback Co  ", "Later Co"],
            "years": [2024, 2023],
        }
        self.assertEqual(
            financial_agent_run_projection._runtime_evidence_defaults(fallback_final),
            {"company": "Fallback Co", "year": 2024},
        )
        self.assertEqual(
            financial_agent_run_projection._runtime_evidence_defaults({}),
            {"company": "", "year": None},
        )

        class StringBomb:
            def __str__(self):
                raise RuntimeError("company coercion failed")

        with self.assertRaisesRegex(RuntimeError, "company coercion failed"):
            financial_agent_run_projection._runtime_evidence_defaults(
                {
                    "report_scope": {"company": StringBomb()},
                    "years": [2024],
                },
            )

        class MappingCopyBomb:
            def keys(self):
                raise RuntimeError("mapping copy failed")

            def __getitem__(self, _key):
                raise AssertionError("mapping values should not be read after keys fail")

        with self.assertRaisesRegex(RuntimeError, "mapping copy failed"):
            financial_agent_run_projection._runtime_evidence_defaults(
                {"report_scope": MappingCopyBomb()},
            )

        metadata = {
            "nested": nested,
            "boundary": "x" * 4_000,
            "too_long": "x" * 4_001,
            "table_object_json": "{}",
            "table_value_records_json": "[]",
            "table_row_records_json": "r" * 20_000,
            "blank": None,
        }
        before_metadata = deepcopy(metadata)

        compacted = financial_agent_run_projection._compact_runtime_evidence_metadata(metadata)

        self.assertIsNot(compacted, metadata)
        self.assertIs(compacted["nested"], nested)
        self.assertEqual(compacted["boundary"], "x" * 4_000)
        self.assertEqual(compacted["table_row_records_json"], "r" * 20_000)
        self.assertIsNone(compacted["blank"])
        self.assertEqual(
            compacted["metadata_compacted_fields"],
            ["table_object_json", "table_value_records_json", "too_long"],
        )
        self.assertNotIn("too_long", compacted)
        self.assertNotIn("table_object_json", compacted)
        self.assertNotIn("table_value_records_json", compacted)
        self.assertEqual(metadata, before_metadata)
        self.assertIs(metadata["nested"], nested)

        oversized_rows = {
            "table_row_records_json": "r" * 20_001,
            "kept": "value",
        }
        oversized_result = financial_agent_run_projection._compact_runtime_evidence_metadata(oversized_rows)
        self.assertEqual(
            oversized_result,
            {
                "kept": "value",
                "metadata_compacted_fields": ["table_row_records_json"],
            },
        )
        self.assertEqual(oversized_rows["table_row_records_json"], "r" * 20_001)

        class MetadataStringBomb:
            def __str__(self):
                raise RuntimeError("metadata coercion failed")

        exploding_metadata = {
            "table_object_json": MetadataStringBomb(),
            "later": "untouched",
        }
        with self.assertRaisesRegex(RuntimeError, "metadata coercion failed"):
            financial_agent_run_projection._compact_runtime_evidence_metadata(exploding_metadata)
        self.assertEqual(set(exploding_metadata), {"table_object_json", "later"})

        class TruthBomb:
            def __bool__(self):
                raise RuntimeError("metadata truth failed")

        with self.assertRaisesRegex(RuntimeError, "metadata truth failed"):
            financial_agent_run_projection._compact_runtime_evidence_metadata(TruthBomb())

    def test_current_source_run_projection_seam_a_enrichment_contract(self) -> None:
        nested = {"preserve": True}
        events = []

        class Agent:
            pass

        agent = Agent()
        defaults = {"company": "Default Co", "year": 2024}
        agent._runtime_evidence_defaults = Mock(
            side_effect=lambda final: events.append(("defaults", final)) or defaults
        )
        compacted_rows = []

        def compact(metadata):
            events.append(("compact", metadata))
            result = {**metadata, "compacted": len(compacted_rows) + 1}
            compacted_rows.append(result)
            return result

        agent._compact_runtime_evidence_metadata = Mock(side_effect=compact)
        evidence_items = [
            {
                "evidence_id": "one",
                "source_anchor": " explicit anchor ",
                "metadata": {
                    "company": "Existing Co",
                    "year": 2023,
                    "section_path": "ignored path",
                    "nested": nested,
                },
                "nested": nested,
            },
            {
                "evidence_id": "two",
                "metadata": {"section_path": "  path / two  ", "nested": nested},
                "nested": nested,
            },
            {
                "evidence_id": "three",
                "metadata": {
                    "source_anchor": "",
                    "section_title": "  title three  ",
                    "nested": nested,
                },
                "nested": nested,
            },
            {
                "evidence_id": "four",
                "metadata": {"section": "  section four  ", "nested": nested},
                "nested": nested,
            },
            {
                "evidence_id": "five",
                "metadata": {
                    "company": " ",
                    "year": 0,
                    "source_anchor": "  metadata source  ",
                    "section_path": "ignored path",
                    "nested": nested,
                },
                "nested": nested,
            },
            {
                "evidence_id": "six",
                "metadata": {"section": "", "nested": nested},
                "nested": nested,
            },
        ]
        before_items = deepcopy(evidence_items)

        def normalize(value):
            events.append(("normalize", value))
            return " ".join(str(value).split())

        with (
            patch.object(
                financial_agent_run_projection,
                "_runtime_evidence_defaults",
                agent._runtime_evidence_defaults,
            ),
            patch.object(
                financial_agent_run_projection,
                "_compact_runtime_evidence_metadata",
                agent._compact_runtime_evidence_metadata,
            ),
            patch.object(financial_agent_run_projection, "_normalise_spaces", side_effect=normalize),
        ):
            enriched = financial_agent_run_projection.enrich_runtime_evidence_metadata(
                {"report_scope": {"company": "Default Co", "year": 2024}},
                evidence_items,
            )

        self.assertEqual([event[0] for event in events], [
            "defaults",
            "compact",
            "normalize",
            "compact",
            "normalize",
            "compact",
            "normalize",
            "compact",
            "normalize",
            "compact",
            "compact",
        ])
        self.assertEqual(
            [row["evidence_id"] for row in enriched],
            ["one", "two", "three", "four", "five", "six"],
        )
        self.assertIsNot(enriched, evidence_items)
        for original, projected in zip(evidence_items, enriched):
            self.assertIsNot(projected, original)
            self.assertIs(projected["nested"], original["nested"])
            self.assertIsNot(projected["metadata"], original["metadata"])
            self.assertIs(projected["metadata"]["nested"], nested)
        self.assertEqual(enriched[0]["source_anchor"], " explicit anchor ")
        self.assertEqual(enriched[0]["metadata"]["company"], "Existing Co")
        self.assertEqual(enriched[0]["metadata"]["year"], 2023)
        self.assertEqual(enriched[1]["source_anchor"], "path / two")
        self.assertEqual(enriched[1]["metadata"]["company"], "Default Co")
        self.assertEqual(enriched[1]["metadata"]["year"], 2024)
        self.assertEqual(enriched[2]["source_anchor"], "title three")
        self.assertEqual(enriched[3]["source_anchor"], "section four")
        self.assertEqual(enriched[4]["source_anchor"], "metadata source")
        self.assertEqual(enriched[4]["metadata"]["company"], " ")
        self.assertEqual(enriched[4]["metadata"]["year"], 2024)
        self.assertNotIn("source_anchor", enriched[5])
        self.assertEqual(evidence_items, before_items)
        self.assertTrue(all(row["metadata"]["nested"] is nested for row in evidence_items))
        self.assertTrue(all(result is row["metadata"] for result, row in zip(compacted_rows, enriched)))

        empty_agent = Agent()
        empty_agent._runtime_evidence_defaults = Mock(return_value={"company": "", "year": None})
        empty_agent._compact_runtime_evidence_metadata = Mock()
        with (
            patch.object(
                financial_agent_run_projection,
                "_runtime_evidence_defaults",
                empty_agent._runtime_evidence_defaults,
            ),
            patch.object(
                financial_agent_run_projection,
                "_compact_runtime_evidence_metadata",
                empty_agent._compact_runtime_evidence_metadata,
            ),
        ):
            self.assertEqual(
                financial_agent_run_projection.enrich_runtime_evidence_metadata({}, []),
                [],
            )
        empty_agent._runtime_evidence_defaults.assert_called_once_with({})
        empty_agent._compact_runtime_evidence_metadata.assert_not_called()

        class EvidenceIterationBomb:
            def __bool__(self):
                return True

            def __iter__(self):
                raise AssertionError("evidence iteration should be stopped")

        failing_defaults_agent = Agent()
        failing_defaults_agent._runtime_evidence_defaults = Mock(
            side_effect=RuntimeError("defaults failed")
        )
        failing_defaults_agent._compact_runtime_evidence_metadata = Mock()
        with (
            patch.object(
                financial_agent_run_projection,
                "_runtime_evidence_defaults",
                failing_defaults_agent._runtime_evidence_defaults,
            ),
            patch.object(
                financial_agent_run_projection,
                "_compact_runtime_evidence_metadata",
                failing_defaults_agent._compact_runtime_evidence_metadata,
            ),
            self.assertRaisesRegex(RuntimeError, "defaults failed"),
        ):
            financial_agent_run_projection.enrich_runtime_evidence_metadata(
                {},
                EvidenceIterationBomb(),
            )
        failing_defaults_agent._compact_runtime_evidence_metadata.assert_not_called()

        iteration_agent = Agent()
        iteration_agent._runtime_evidence_defaults = Mock(return_value=defaults)
        iteration_agent._compact_runtime_evidence_metadata = Mock()
        with (
            patch.object(
                financial_agent_run_projection,
                "_runtime_evidence_defaults",
                iteration_agent._runtime_evidence_defaults,
            ),
            patch.object(
                financial_agent_run_projection,
                "_compact_runtime_evidence_metadata",
                iteration_agent._compact_runtime_evidence_metadata,
            ),
            self.assertRaisesRegex(AssertionError, "evidence iteration should be stopped"),
        ):
            financial_agent_run_projection.enrich_runtime_evidence_metadata(
                {},
                EvidenceIterationBomb(),
            )
        iteration_agent._compact_runtime_evidence_metadata.assert_not_called()

        failing_compact_agent = Agent()
        failing_compact_agent._runtime_evidence_defaults = Mock(return_value=defaults)
        failing_compact_agent._compact_runtime_evidence_metadata = Mock(
            side_effect=RuntimeError("compact failed")
        )
        with (
            patch.object(
                financial_agent_run_projection,
                "_runtime_evidence_defaults",
                failing_compact_agent._runtime_evidence_defaults,
            ),
            patch.object(
                financial_agent_run_projection,
                "_compact_runtime_evidence_metadata",
                failing_compact_agent._compact_runtime_evidence_metadata,
            ),
            patch.object(financial_agent_run_projection, "_normalise_spaces", return_value="anchor"),
            self.assertRaisesRegex(RuntimeError, "compact failed"),
        ):
            financial_agent_run_projection.enrich_runtime_evidence_metadata(
                {},
                [{"metadata": {"section": "anchor"}}, {"metadata": {"section": "later"}}],
            )
        self.assertEqual(failing_compact_agent._compact_runtime_evidence_metadata.call_count, 1)

        normalization_agent = Agent()
        normalization_agent._runtime_evidence_defaults = Mock(return_value=defaults)
        normalization_agent._compact_runtime_evidence_metadata = Mock()
        with (
            patch.object(
                financial_agent_run_projection,
                "_runtime_evidence_defaults",
                normalization_agent._runtime_evidence_defaults,
            ),
            patch.object(
                financial_agent_run_projection,
                "_compact_runtime_evidence_metadata",
                normalization_agent._compact_runtime_evidence_metadata,
            ),
            patch.object(
                financial_agent_run_projection,
                "_normalise_spaces",
                side_effect=RuntimeError("normalization failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "normalization failed"),
        ):
            financial_agent_run_projection.enrich_runtime_evidence_metadata(
                {},
                [{"metadata": {"source_anchor": "anchor"}}],
            )
        normalization_agent._compact_runtime_evidence_metadata.assert_not_called()

    def test_current_source_run_projection_seam_a_static_binding_dag_and_baseline_contract(self) -> None:
        module_trees = {
            "graph": ast.parse(inspect.getsource(financial_graph)),
            "owner": ast.parse(inspect.getsource(financial_agent_run_projection)),
        }
        target_names = {
            "_runtime_evidence_defaults",
            "_compact_runtime_evidence_metadata",
            "enrich_runtime_evidence_metadata",
        }
        retired_enrich_name = "_" + "enrich_runtime_evidence_metadata"
        definitions = {
            (module_name, node.name): node
            for module_name, module_tree in module_trees.items()
            for node in ast.walk(module_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in target_names | {retired_enrich_name}
        }
        self.assertEqual(
            set(definitions),
            {
                ("owner", "_runtime_evidence_defaults"),
                ("owner", "_compact_runtime_evidence_metadata"),
                ("owner", "enrich_runtime_evidence_metadata"),
            },
        )
        self.assertEqual(
            {name: node.end_lineno - node.lineno + 1 for (_, name), node in definitions.items()},
            {
                "_runtime_evidence_defaults": 11,
                "_compact_runtime_evidence_metadata": 25,
                "enrich_runtime_evidence_metadata": 25,
            },
        )
        self.assertTrue(Path("src/agent/financial_agent_run_projection.py").exists())

        calls = {name: [] for name in target_names}

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            def visit_Call(self, node):
                if isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                    receiver = ast.unparse(node.func.value)
                elif isinstance(node.func, ast.Name):
                    name = node.func.id
                    receiver = ""
                else:
                    name = ""
                    receiver = ""
                if name in target_names:
                    calls[name].append(
                        (
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "<module>",
                            receiver,
                            [ast.unparse(arg) for arg in node.args],
                            [(keyword.arg, ast.unparse(keyword.value)) for keyword in node.keywords],
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

        for module_name, module_tree in module_trees.items():
            BindingVisitor(module_name).visit(module_tree)
        self.assertEqual(
            calls["_runtime_evidence_defaults"],
            [("owner", "enrich_runtime_evidence_metadata", "", ["final"], [], 0)],
        )
        self.assertEqual(
            calls["_compact_runtime_evidence_metadata"],
            [("owner", "enrich_runtime_evidence_metadata", "", ["metadata"], [], 0)],
        )
        self.assertEqual(
            calls["enrich_runtime_evidence_metadata"],
            [
                ("graph", "_runtime_evidence_from_retrieved_docs", "", ["final", "filtered"], [], 0),
                (
                    "graph",
                    "_runtime_evidence_from_retrieved_docs",
                    "",
                    ["final", "selected_existing"],
                    [],
                    0,
                ),
                ("graph", "_runtime_evidence_from_retrieved_docs", "", ["final", "existing"], [], 0),
                ("graph", "_runtime_evidence_from_retrieved_docs", "", ["final", "filtered"], [], 0),
            ],
        )
        self.assertEqual(sum(len(rows) for rows in calls.values()), 6)
        self.assertEqual(len(calls["enrich_runtime_evidence_metadata"]), 4)
        self.assertEqual(
            len(calls["_runtime_evidence_defaults"]) + len(calls["_compact_runtime_evidence_metadata"]),
            2,
        )

        project_root = Path(__file__).resolve().parents[1]
        agent_module_trees = {}
        for path in (project_root / "src" / "agent").glob("*.py"):
            agent_module_trees[f"src.agent.{path.stem}"] = ast.parse(path.read_text(encoding="utf-8-sig"))
        edges = {name: set() for name in agent_module_trees}
        for module_name, module_tree in agent_module_trees.items():
            for node in ast.walk(module_tree):
                imported = None
                if isinstance(node, ast.ImportFrom) and node.module:
                    imported = node.module
                if imported in edges:
                    edges[module_name].add(imported)

        def reachable(start, target):
            pending = [start]
            seen = set()
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(edges.get(current, ()))
            return False

        owner_module = "src.agent.financial_agent_run_projection"
        graph_module = "src.agent.financial_graph"
        self.assertIn(owner_module, agent_module_trees)
        self.assertIn(owner_module, edges[graph_module])
        self.assertFalse(reachable(owner_module, graph_module))
        self.assertFalse(reachable("src.agent.financial_graph_state", owner_module))
        self.assertFalse(reachable("src.agent.financial_runtime_normalization", owner_module))

        from src.ops.audit_runtime_domain_terms import (
            collect_runtime_domain_term_occurrences,
            collect_runtime_domain_terms,
        )

        baseline = json.loads(
            (project_root / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8-sig"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        self.assertEqual(len(collect_runtime_domain_terms(project_root)), 217)
        occurrences = collect_runtime_domain_term_occurrences(project_root)
        selected_ranges = [(node.lineno, node.end_lineno) for node in definitions.values()]
        self.assertEqual(
            [
                row
                for row in occurrences
                if row["path"] == "src/agent/financial_agent_run_projection.py"
                and any(start <= row["line"] <= end for start, end in selected_ranges)
            ],
            [],
        )

    def test_current_source_run_projection_seam_a_runtime_evidence_caller_contract(self) -> None:
        nested = {"preserve": True}
        events = []

        class Agent:
            pass

        agent = Agent()
        trace = {"calculation_operands": [{"operand_id": "one", "nested": nested}]}
        agent._project_runtime_calculation_trace = Mock(
            side_effect=lambda final: events.append(("project", final)) or trace
        )
        enriched_numeric = [{"evidence_id": "numeric-enriched"}]

        def enrich(final, rows):
            events.append(("enrich", final, rows))
            return enriched_numeric

        enrich_projection = Mock(side_effect=enrich)
        existing = {"evidence_id": "existing", "nested": nested}
        numeric_final = {
            "answer": " answer 10 ",
            "evidence_items": [existing],
            "selected_claim_ids": ["selected"],
            "nested": nested,
        }
        before_numeric = deepcopy(numeric_final)
        appended = [{"evidence_id": "appended", "nested": nested}]
        filtered = [{"evidence_id": f"filtered-{index}", "nested": nested} for index in range(10)]

        def append(items, *, operands, final_answer):
            events.append(("append", items, operands, final_answer))
            return appended

        def filter_rows(items, *, final_answer, selected_claim_ids):
            events.append(("filter", items, final_answer, selected_claim_ids))
            return filtered

        with (
            patch.object(financial_graph, "_normalise_spaces", side_effect=lambda value: " ".join(str(value).split())),
            patch.object(financial_graph, "extract_numeric_surface_candidates", return_value=[{"value": 10}]),
            patch.object(financial_graph, "append_operand_evidence_for_final_answer", side_effect=append),
            patch.object(financial_graph, "filter_aggregate_evidence_for_final_answer", side_effect=filter_rows),
            patch.object(financial_graph, "enrich_runtime_evidence_metadata", enrich_projection),
        ):
            numeric_result = FinancialAgent._runtime_evidence_from_retrieved_docs(agent, numeric_final)

        self.assertIs(numeric_result, enriched_numeric)
        self.assertEqual([event[0] for event in events], ["project", "append", "filter", "enrich"])
        append_event = events[1]
        self.assertEqual(append_event[1], [existing])
        self.assertIsNot(append_event[1], numeric_final["evidence_items"])
        self.assertIsNot(append_event[1][0], existing)
        self.assertIs(append_event[1][0]["nested"], nested)
        self.assertEqual(append_event[2], trace["calculation_operands"])
        self.assertIsNot(append_event[2], trace["calculation_operands"])
        self.assertIs(append_event[2][0], trace["calculation_operands"][0])
        self.assertEqual(append_event[3], "answer 10")
        self.assertIs(events[2][1], appended)
        self.assertEqual(events[2][3], ["selected"])
        self.assertIs(events[3][1], numeric_final)
        self.assertEqual(events[3][2], filtered[:8])
        self.assertIsNot(events[3][2], filtered)
        self.assertTrue(all(left is right for left, right in zip(events[3][2], filtered)))
        self.assertEqual(numeric_final, before_numeric)
        self.assertIs(numeric_final["nested"], nested)

        selected_agent = Agent()
        selected_enriched = [{"evidence_id": "selected-enriched"}]
        selected_projection = Mock(return_value=selected_enriched)
        selected_final = {
            "answer": "narrative",
            "evidence_items": [
                {"evidence_id": "drop", "nested": nested},
                {"evidence_id": "keep", "nested": nested},
            ],
            "kept_claim_ids": [" keep ", ""],
        }
        before_selected = deepcopy(selected_final)
        with (
            patch.object(financial_graph, "_normalise_spaces", return_value="narrative"),
            patch.object(financial_graph, "extract_numeric_surface_candidates", return_value=[]),
            patch.object(financial_graph, "append_operand_evidence_for_final_answer") as stopped_append,
            patch.object(financial_graph, "filter_aggregate_evidence_for_final_answer") as stopped_filter,
            patch.object(financial_graph, "enrich_runtime_evidence_metadata", selected_projection),
        ):
            selected_result = FinancialAgent._runtime_evidence_from_retrieved_docs(
                selected_agent,
                selected_final,
            )
        self.assertIs(selected_result, selected_enriched)
        selected_rows = selected_projection.call_args.args[1]
        self.assertEqual([row["evidence_id"] for row in selected_rows], ["keep"])
        self.assertIsNot(selected_rows[0], selected_final["evidence_items"][1])
        self.assertIs(selected_rows[0]["nested"], nested)
        stopped_append.assert_not_called()
        stopped_filter.assert_not_called()
        self.assertEqual(selected_final, before_selected)

        existing_agent = Agent()
        existing_enriched = [{"evidence_id": "existing-enriched"}]
        existing_projection = Mock(return_value=existing_enriched)
        existing_final = {"answer": "narrative", "evidence_items": [existing]}
        with (
            patch.object(financial_graph, "_normalise_spaces", return_value="narrative"),
            patch.object(financial_graph, "extract_numeric_surface_candidates", return_value=[]),
            patch.object(financial_graph, "enrich_runtime_evidence_metadata", existing_projection),
        ):
            existing_result = FinancialAgent._runtime_evidence_from_retrieved_docs(
                existing_agent,
                existing_final,
            )
        self.assertIs(existing_result, existing_enriched)
        fallback_rows = existing_projection.call_args.args[1]
        self.assertEqual(fallback_rows, [existing])
        self.assertIsNot(fallback_rows[0], existing)
        self.assertIs(fallback_rows[0]["nested"], nested)

        retrieved_nested = {"retrieved": True}
        retrieved_doc = {
            "page_content": " retrieved 20 ",
            "metadata": {"section_path": " path ", "nested": retrieved_nested},
        }
        retrieved_final = {
            "answer": "answer 20",
            "evidence_items": [],
            "seed_retrieved_docs": [(retrieved_doc, 0.9)],
            "retrieved_docs": [retrieved_doc],
        }
        before_retrieved = deepcopy(retrieved_final)
        retrieved_agent = Agent()
        retrieved_agent._project_runtime_calculation_trace = Mock(
            return_value={"calculation_operands": []}
        )
        retrieved_enriched = [{"evidence_id": "retrieved-enriched"}]
        retrieved_projection = Mock(return_value=retrieved_enriched)
        retrieved_filtered = [{"evidence_id": "retrieved::kept"}]
        retrieved_filter = Mock(side_effect=[[], retrieved_filtered])
        with (
            patch.object(financial_graph, "_normalise_spaces", side_effect=lambda value: " ".join(str(value).split())),
            patch.object(financial_graph, "extract_numeric_surface_candidates", return_value=[{"value": 20}]),
            patch.object(financial_graph, "append_operand_evidence_for_final_answer", return_value=[]),
            patch.object(financial_graph, "filter_aggregate_evidence_for_final_answer", retrieved_filter),
            patch.object(financial_graph, "enrich_runtime_evidence_metadata", retrieved_projection),
        ):
            retrieved_result = FinancialAgent._runtime_evidence_from_retrieved_docs(
                retrieved_agent,
                retrieved_final,
            )
        self.assertIs(retrieved_result, retrieved_enriched)
        self.assertEqual(retrieved_filter.call_count, 2)
        generated_rows = retrieved_filter.call_args_list[1].args[0]
        self.assertEqual(len(generated_rows), 1)
        self.assertEqual(generated_rows[0]["evidence_id"], "retrieved::001")
        self.assertEqual(generated_rows[0]["claim"], "retrieved 20")
        self.assertIs(generated_rows[0]["metadata"]["nested"], retrieved_nested)
        retrieved_projection.assert_called_once_with(
            retrieved_final,
            retrieved_filtered,
        )
        self.assertEqual(retrieved_final, before_retrieved)

        failing_agent = Agent()
        failing_agent._project_runtime_calculation_trace = Mock(return_value=trace)
        failing_projection = Mock(side_effect=RuntimeError("enrich failed"))
        with (
            patch.object(financial_graph, "_normalise_spaces", return_value="answer 10"),
            patch.object(financial_graph, "extract_numeric_surface_candidates", return_value=[{"value": 10}]),
            patch.object(financial_graph, "append_operand_evidence_for_final_answer", return_value=appended),
            patch.object(financial_graph, "filter_aggregate_evidence_for_final_answer", return_value=filtered),
            patch.object(financial_graph, "enrich_runtime_evidence_metadata", failing_projection),
            self.assertRaisesRegex(RuntimeError, "enrich failed"),
        ):
            FinancialAgent._runtime_evidence_from_retrieved_docs(failing_agent, numeric_final)
        self.assertEqual(numeric_final, before_numeric)

    def test_current_source_run_projection_seam_b_agent_answer_and_debug_projection_contract(self) -> None:
        nested = {"preserve": True}
        calculation_debug = {"source": "trace", "nested": nested}
        final_for_debug = {
            financial_agent_run_projection.CALCULATION_DEBUG_TRACE_FIELD: calculation_debug
        }
        before_debug_final = deepcopy(final_for_debug)

        debug_traces = financial_agent_run_projection.project_debug_traces(final_for_debug)

        self.assertEqual(debug_traces, {"calculation": calculation_debug})
        self.assertIsNot(debug_traces["calculation"], calculation_debug)
        self.assertIs(debug_traces["calculation"]["nested"], nested)
        self.assertEqual(final_for_debug, before_debug_final)
        self.assertIs(
            final_for_debug[financial_agent_run_projection.CALCULATION_DEBUG_TRACE_FIELD]["nested"],
            nested,
        )
        self.assertEqual(
            financial_agent_run_projection.project_debug_traces({}),
            {"calculation": {}},
        )

        class DebugCopyBomb:
            def keys(self):
                raise RuntimeError("debug copy failed")

            def __getitem__(self, _key):
                raise AssertionError("debug mapping values should stay unread")

        with self.assertRaisesRegex(RuntimeError, "debug copy failed"):
            financial_agent_run_projection.project_debug_traces(
                {financial_agent_run_projection.CALCULATION_DEBUG_TRACE_FIELD: DebugCopyBomb()},
            )

        access_events = []

        class RecordingFinal(dict):
            def __getitem__(self, key):
                access_events.append(("item", key))
                return dict.__getitem__(self, key)

            def get(self, key, default=None):
                access_events.append(("get", key, default))
                return dict.get(self, key, default)

        report_scope = {"company": "Scope", "nested": nested}
        planned_metric_families = ["ratio"]
        routing_scores = {"ratio": 0.9}
        companies = ["Company"]
        years = [2024]
        final = RecordingFinal(
            {
                "query": "query",
                "report_scope": report_scope,
                "query_type": "comparison",
                "intent": "explicit-intent",
                "planner_mode": "retry",
                "planner_feedback": "feedback",
                "plan_loop_count": 2,
                "target_metric_family": "ratio",
                "target_metric_family_hint": "hint",
                "planned_metric_families": planned_metric_families,
                "format_preference": "brief",
                "routing_source": "semantic",
                "routing_confidence": 0.9,
                "routing_scores": routing_scores,
                "companies": companies,
                "years": years,
            }
        )
        before_final = deepcopy(dict(final))
        access_events.clear()
        citations = ["citation"]
        structured_result = {"status": "ok", "nested": nested}
        runtime_trace = {"calculation_result": structured_result, "nested": nested}

        answer = financial_agent_run_projection.project_agent_answer(
            final,
            public_answer="public answer",
            citations=citations,
            structured_result=structured_result,
            runtime_calculation_trace=runtime_trace,
        )

        self.assertEqual(
            list(answer),
            [
                "query",
                "report_scope",
                "query_type",
                "intent",
                "planner_mode",
                "planner_feedback",
                "plan_loop_count",
                "target_metric_family",
                "target_metric_family_hint",
                "planned_metric_families",
                "format_preference",
                "routing_source",
                "routing_confidence",
                "routing_scores",
                "companies",
                "years",
                "answer",
                "citations",
                "resolved_calculation_trace",
                "structured_result",
            ],
        )
        self.assertEqual(
            access_events,
            [
                ("item", "query"),
                ("get", "report_scope", {}),
                ("item", "query_type"),
                ("item", "query_type"),
                ("get", "intent", "comparison"),
                ("get", "planner_mode", "initial"),
                ("get", "planner_feedback", ""),
                ("get", "plan_loop_count", 0),
                ("get", "target_metric_family", ""),
                ("get", "target_metric_family", ""),
                ("get", "target_metric_family_hint", "ratio"),
                ("get", "planned_metric_families", []),
                ("get", "format_preference", ""),
                ("get", "routing_source", ""),
                ("get", "routing_confidence", 0.0),
                ("get", "routing_scores", {}),
                ("item", "companies"),
                ("item", "years"),
            ],
        )
        self.assertIs(answer["report_scope"], report_scope)
        self.assertIs(answer["planned_metric_families"], planned_metric_families)
        self.assertIs(answer["routing_scores"], routing_scores)
        self.assertIs(answer["companies"], companies)
        self.assertIs(answer["years"], years)
        self.assertIs(answer["citations"], citations)
        self.assertIs(answer["structured_result"], structured_result)
        self.assertIs(answer["resolved_calculation_trace"], runtime_trace)
        self.assertEqual(answer["intent"], "explicit-intent")
        self.assertEqual(answer["target_metric_family_hint"], "hint")
        self.assertEqual(dict(final), before_final)
        self.assertIs(final["report_scope"]["nested"], nested)

        fallback_answer = financial_agent_run_projection.project_agent_answer(
            {
                "query": "fallback query",
                "query_type": "lookup",
                "companies": [],
                "years": [],
            },
            public_answer="",
            citations=[],
            structured_result={},
            runtime_calculation_trace={},
        )
        self.assertEqual(
            {key: fallback_answer[key] for key in (
                "report_scope",
                "intent",
                "planner_mode",
                "planner_feedback",
                "plan_loop_count",
                "target_metric_family",
                "target_metric_family_hint",
                "planned_metric_families",
                "format_preference",
                "routing_source",
                "routing_confidence",
                "routing_scores",
            )},
            {
                "report_scope": {},
                "intent": "lookup",
                "planner_mode": "initial",
                "planner_feedback": "",
                "plan_loop_count": 0,
                "target_metric_family": "",
                "target_metric_family_hint": "",
                "planned_metric_families": [],
                "format_preference": "",
                "routing_source": "",
                "routing_confidence": 0.0,
                "routing_scores": {},
            },
        )

        class RequiredFieldBomb(dict):
            def __getitem__(self, key):
                if key == "query":
                    raise RuntimeError("query access failed")
                raise AssertionError("later indexed field should stay unread")

            def get(self, *_args, **_kwargs):
                raise AssertionError("fallback fields should stay unread")

        with self.assertRaisesRegex(RuntimeError, "query access failed"):
            financial_agent_run_projection.project_agent_answer(
                RequiredFieldBomb(),
                public_answer="",
                citations=[],
                structured_result={},
                runtime_calculation_trace={},
            )

        llm_usage = {"tokens": 3, "nested": nested}
        phase_usage = {"planner": {"tokens": 2}, "nested": nested}
        embedding_usage = {"requests": 1, "nested": nested}
        debug_bundle = financial_agent_run_projection.project_debug_bundle(
            debug_traces=debug_traces,
            llm_usage=llm_usage,
            llm_usage_by_phase=phase_usage,
            embedding_usage=embedding_usage,
        )
        self.assertEqual(
            list(debug_bundle),
            ["debug_traces", "llm_usage", "llm_usage_by_phase", "embedding_usage"],
        )
        self.assertIs(debug_bundle["debug_traces"], debug_traces)
        self.assertIs(debug_bundle["llm_usage"], llm_usage)
        self.assertIs(debug_bundle["llm_usage_by_phase"], phase_usage)
        self.assertIs(debug_bundle["embedding_usage"], embedding_usage)

    def test_current_source_run_projection_seam_b_review_trace_and_citation_contract(self) -> None:
        nested = {"preserve": True}
        review_keys = [
            "seed_retrieved_docs",
            "retrieved_docs",
            "retrieval_debug_trace",
            "retrieval_debug_trace_history",
            "evidence_items",
            "selected_claim_ids",
            "draft_points",
            "kept_claim_ids",
            "dropped_claim_ids",
            "unsupported_sentences",
            "sentence_checks",
            "numeric_debug_trace",
            "numeric_debug_trace_history",
            "planner_debug_trace",
            "missing_info",
            "reflection_count",
            "retry_reason",
            "retry_strategy",
            "retry_queries",
            "reconciliation_retry_count",
            "reflection_plan",
            "reflection_request",
            "reflection_action",
            "reflection_report",
            "semantic_plan",
            "calc_subtasks",
            "retrieval_queries",
            "active_subtask_index",
            "active_subtask",
            "subtask_results",
            "subtask_debug_trace",
            "subtask_loop_complete",
            "reconciliation_result",
            "tasks",
            "artifacts",
            "task_artifact_trace",
        ]
        final_values = {
            key: {"field": key, "nested": nested}
            for key in review_keys
            if key
            not in {
                "evidence_items",
                "task_artifact_trace",
                "reflection_count",
                "retry_reason",
                "retry_strategy",
                "reconciliation_retry_count",
                "active_subtask_index",
                "subtask_loop_complete",
            }
        }
        final_values.update(
            {
                "reflection_count": 2,
                "retry_reason": "reason",
                "retry_strategy": "strategy",
                "reconciliation_retry_count": 3,
                "active_subtask_index": 4,
                "subtask_loop_complete": ["truthy"],
            }
        )
        review_access = []

        class RecordingReviewFinal(dict):
            def __getitem__(self, key):
                review_access.append(("item", key))
                return dict.__getitem__(self, key)

            def get(self, key, default=None):
                review_access.append(("get", key))
                return dict.get(self, key, default)

        final_values = RecordingReviewFinal(final_values)
        before_review_final = deepcopy(dict(final_values))
        review_access.clear()
        runtime_evidence = [{"evidence_id": "runtime", "nested": nested}]
        task_artifact_trace = {"integrity_status": "ok", "nested": nested}

        review = financial_agent_run_projection.project_review_trace(
            final_values,
            runtime_evidence=runtime_evidence,
            task_artifact_trace=task_artifact_trace,
        )

        self.assertEqual(list(review), review_keys)
        for key, value in final_values.items():
            if key == "subtask_loop_complete":
                self.assertIs(review[key], True)
            else:
                self.assertIs(review[key], value)
        self.assertIs(review["evidence_items"], runtime_evidence)
        self.assertIs(review["task_artifact_trace"], task_artifact_trace)
        self.assertEqual(
            review_access,
            [
                ("get", "seed_retrieved_docs"),
                ("item", "retrieved_docs"),
                ("get", "retrieval_debug_trace"),
                ("get", "retrieval_debug_trace_history"),
                ("get", "selected_claim_ids"),
                ("get", "draft_points"),
                ("get", "kept_claim_ids"),
                ("get", "dropped_claim_ids"),
                ("get", "unsupported_sentences"),
                ("get", "sentence_checks"),
                ("get", "numeric_debug_trace"),
                ("get", "numeric_debug_trace_history"),
                ("get", "planner_debug_trace"),
                ("get", "missing_info"),
                ("get", "reflection_count"),
                ("get", "retry_reason"),
                ("get", "retry_strategy"),
                ("get", "retry_queries"),
                ("get", "reconciliation_retry_count"),
                ("get", "reflection_plan"),
                ("get", "reflection_request"),
                ("get", "reflection_action"),
                ("get", "reflection_report"),
                ("get", "semantic_plan"),
                ("get", "calc_subtasks"),
                ("get", "retrieval_queries"),
                ("get", "active_subtask_index"),
                ("get", "active_subtask"),
                ("get", "subtask_results"),
                ("get", "subtask_debug_trace"),
                ("get", "subtask_loop_complete"),
                ("get", "reconciliation_result"),
                ("get", "tasks"),
                ("get", "artifacts"),
            ],
        )
        self.assertEqual(dict(final_values), before_review_final)
        self.assertIs(final_values["retrieved_docs"]["nested"], nested)

        default_review = financial_agent_run_projection.project_review_trace(
            {"retrieved_docs": []},
            runtime_evidence=[],
            task_artifact_trace={},
        )
        self.assertEqual(list(default_review), review_keys)
        self.assertEqual(default_review["seed_retrieved_docs"], [])
        self.assertEqual(default_review["retrieval_debug_trace"], {})
        self.assertEqual(default_review["reflection_count"], 0)
        self.assertEqual(default_review["retry_reason"], "")
        self.assertEqual(default_review["retry_strategy"], "")
        self.assertEqual(default_review["active_subtask_index"], 0)
        self.assertIs(default_review["subtask_loop_complete"], False)

        with self.assertRaises(KeyError):
            financial_agent_run_projection.project_review_trace(
                {},
                runtime_evidence=[],
                task_artifact_trace={},
            )

        class ReviewTruthBomb:
            def __bool__(self):
                raise RuntimeError("review truth failed")

        with self.assertRaisesRegex(RuntimeError, "review truth failed"):
            financial_agent_run_projection.project_review_trace(
                {"retrieved_docs": [], "subtask_loop_complete": ReviewTruthBomb()},
                runtime_evidence=[],
                task_artifact_trace={},
            )

        evidence_nested = {"evidence": True}
        citations = [" Original ", "", " CASE ", "original"]
        evidence = [
            {
                "source_anchor": " Alpha ",
                "metadata": {"company": " Co ", "year": 2024, "nested": evidence_nested},
                "nested": evidence_nested,
            },
            {
                "metadata": {
                    "source_anchor": " [Existing] ",
                    "section_path": "ignored",
                    "company": "Ignored Co",
                    "year": 2022,
                    "nested": evidence_nested,
                },
                "nested": evidence_nested,
            },
            {
                "metadata": {
                    "section_path": " Path ",
                    "section": "ignored",
                    "company": "Co",
                    "nested": evidence_nested,
                },
                "nested": evidence_nested,
            },
            {
                "metadata": {"section": " Section ", "year": " 2023 ", "nested": evidence_nested},
                "nested": evidence_nested,
            },
            {
                "metadata": {"section_title": "Title is not a citation fallback", "nested": evidence_nested},
                "nested": evidence_nested,
            },
            {
                "source_anchor": " case ",
                "metadata": {"nested": evidence_nested},
                "nested": evidence_nested,
            },
        ]
        before_citations = deepcopy(citations)
        before_evidence = deepcopy(evidence)
        normalize_events = []

        def normalize(value):
            normalize_events.append(value)
            return " ".join(str(value).split())

        with patch.object(financial_agent_run_projection, "_normalise_spaces", side_effect=normalize):
            projected_citations = financial_agent_run_projection.augment_citations_from_runtime_evidence(
                citations,
                evidence,
            )

        self.assertEqual(
            projected_citations,
            [
                "Original",
                "CASE",
                "original",
                "[Co | 2024 | Alpha]",
                "[Existing]",
                "[Co | Path]",
                "[2023 | Section]",
            ],
        )
        self.assertEqual(citations, before_citations)
        self.assertEqual(evidence, before_evidence)
        self.assertTrue(all(row["nested"] is evidence_nested for row in evidence))
        self.assertTrue(all(row["metadata"]["nested"] is evidence_nested for row in evidence))
        self.assertIn("CASE", normalize_events)
        self.assertIn("case", normalize_events)

        class EvidenceIterationBomb:
            def __bool__(self):
                return True

            def __iter__(self):
                raise AssertionError("evidence should stay lazy after citation failure")

        with (
            patch.object(
                financial_agent_run_projection,
                "_normalise_spaces",
                side_effect=RuntimeError("citation normalization failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "citation normalization failed"),
        ):
            financial_agent_run_projection.augment_citations_from_runtime_evidence(
                ["citation"],
                EvidenceIterationBomb(),
            )

        class EvidenceCopyBomb:
            def keys(self):
                raise RuntimeError("evidence copy failed")

            def __getitem__(self, _key):
                raise AssertionError("evidence values should stay unread")

        with (
            patch.object(
                financial_agent_run_projection,
                "_normalise_spaces",
                side_effect=lambda value: str(value).strip(),
            ),
            self.assertRaisesRegex(RuntimeError, "evidence copy failed"),
        ):
            financial_agent_run_projection.augment_citations_from_runtime_evidence(
                [],
                [EvidenceCopyBomb()],
            )

    def test_current_source_run_projection_seam_b_static_binding_dag_and_baseline_contract(self) -> None:
        module_trees = {
            "graph": ast.parse(inspect.getsource(financial_graph)),
            "owner": ast.parse(inspect.getsource(financial_agent_run_projection)),
        }
        current_targets = {
            "project_debug_traces": 2,
            "project_agent_answer": 33,
            "project_review_trace": 44,
            "project_debug_bundle": 13,
            "augment_citations_from_runtime_evidence": 31,
        }
        retired_targets = {f"_{name}" for name in current_targets}
        definitions = {
            (module_name, node.name): node
            for module_name, module_tree in module_trees.items()
            for node in ast.walk(module_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name in set(current_targets) | retired_targets
        }
        self.assertEqual(
            set(definitions),
            {("owner", name) for name in current_targets},
        )
        self.assertEqual(
            {
                name: definitions[("owner", name)].end_lineno
                - definitions[("owner", name)].lineno
                + 1
                for name in current_targets
            },
            current_targets,
        )

        calls = {name: [] for name in current_targets}

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name):
                self.module_name = module_name
                self.function_stack = []
                self.try_depth = 0

            def visit_FunctionDef(self, node):
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            def visit_Call(self, node):
                if isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                    receiver = ast.unparse(node.func.value)
                elif isinstance(node.func, ast.Name):
                    name = node.func.id
                    receiver = ""
                else:
                    name = ""
                    receiver = ""
                if name in calls:
                    calls[name].append(
                        (
                            self.module_name,
                            self.function_stack[-1] if self.function_stack else "<module>",
                            receiver,
                            [ast.unparse(arg) for arg in node.args],
                            [(keyword.arg, ast.unparse(keyword.value)) for keyword in node.keywords],
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

        for module_name, module_tree in module_trees.items():
            BindingVisitor(module_name).visit(module_tree)

        self.assertEqual(
            calls,
            {
                "project_debug_traces": [
                    ("graph", "run", "", ["final"], [], 0),
                ],
                "project_agent_answer": [
                    (
                        "graph",
                        "run",
                        "",
                        ["final"],
                        [
                            ("public_answer", "public_answer"),
                            ("citations", "citations"),
                            ("structured_result", "structured_result"),
                            ("runtime_calculation_trace", "runtime_calculation_trace"),
                        ],
                        0,
                    )
                ],
                "project_review_trace": [
                    (
                        "graph",
                        "run",
                        "",
                        ["final"],
                        [
                            ("runtime_evidence", "runtime_evidence"),
                            ("task_artifact_trace", "task_artifact_trace"),
                        ],
                        0,
                    )
                ],
                "project_debug_bundle": [
                    (
                        "graph",
                        "run",
                        "",
                        [],
                        [
                            ("debug_traces", "debug_traces"),
                            ("llm_usage", "llm_usage"),
                            ("llm_usage_by_phase", "llm_usage_by_phase"),
                            ("embedding_usage", "embedding_usage"),
                        ],
                        0,
                    )
                ],
                "augment_citations_from_runtime_evidence": [
                    (
                        "graph",
                        "run",
                        "",
                        ["final['citations']", "runtime_evidence"],
                        [],
                        0,
                    )
                ],
            },
        )
        self.assertEqual(sum(len(rows) for rows in calls.values()), 5)

        a_public_calls = []
        a_local_calls = []
        for module_name, module_tree in module_trees.items():
            for node in ast.walk(module_tree):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Name) and node.func.id == "enrich_runtime_evidence_metadata":
                    a_public_calls.append(module_name)
                if isinstance(node.func, ast.Name) and node.func.id in {
                    "_runtime_evidence_defaults",
                    "_compact_runtime_evidence_metadata",
                }:
                    a_local_calls.append(module_name)
        self.assertEqual(a_public_calls, ["graph"] * 4)
        self.assertEqual(a_local_calls, ["owner"] * 2)
        self.assertEqual(len(a_public_calls) + 5, 9)
        self.assertEqual(len(a_local_calls), 2)

        project_root = Path(__file__).resolve().parents[1]
        agent_module_trees = {}
        for path in (project_root / "src" / "agent").glob("*.py"):
            agent_module_trees[f"src.agent.{path.stem}"] = ast.parse(
                path.read_text(encoding="utf-8-sig")
            )
        edges = {name: set() for name in agent_module_trees}
        for module_name, module_tree in agent_module_trees.items():
            for node in ast.walk(module_tree):
                if isinstance(node, ast.ImportFrom) and node.module in edges:
                    edges[module_name].add(node.module)

        def reachable(start, target):
            pending = [start]
            seen = set()
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(edges.get(current, ()))
            return False

        owner_module = "src.agent.financial_agent_run_projection"
        graph_module = "src.agent.financial_graph"
        self.assertIn(owner_module, edges[graph_module])
        self.assertFalse(reachable(owner_module, graph_module))
        self.assertFalse(reachable("src.agent.financial_graph_state", owner_module))
        self.assertFalse(reachable("src.agent.financial_runtime_normalization", owner_module))

        from src.ops.audit_runtime_domain_terms import (
            collect_runtime_domain_term_occurrences,
            collect_runtime_domain_terms,
        )

        self.assertEqual(len(collect_runtime_domain_terms(project_root)), 217)
        occurrences = collect_runtime_domain_term_occurrences(project_root)
        selected_ranges = [
            (node.lineno, node.end_lineno)
            for (module_name, _), node in definitions.items()
            if module_name == "owner"
        ]
        self.assertEqual(
            [
                row
                for row in occurrences
                if row["path"] == "src/agent/financial_agent_run_projection.py"
                and any(start <= row["line"] <= end for start, end in selected_ranges)
            ],
            [],
        )

    def test_current_source_run_projection_seam_b_run_caller_contract(self) -> None:
        nested = {"preserve": True}
        runtime_evidence = [{"evidence_id": "runtime", "nested": nested}]
        initial_trace = {"calculation_result": {"status": "initial"}, "nested": nested}
        repaired_trace = {"calculation_result": {"status": "repaired"}, "nested": nested}
        appended_trace = {"calculation_result": {"status": "appended"}, "nested": nested}
        task_artifact_trace = {"integrity_status": "ok", "nested": nested}
        debug_traces = {"calculation": {"source": "test"}, "nested": nested}
        projected_citations = ["projected citation"]
        agent_answer = {"agent_marker": "agent", "nested": nested}
        review_trace = {"review_marker": "review", "nested": nested}
        debug_bundle = {"debug_marker": "debug", "nested": nested}
        llm_usage = {"tokens": 3, "nested": nested}
        llm_usage_by_phase = {"planner": {"tokens": 2}, "nested": nested}
        embedding_usage = {"requests": 1, "nested": nested}

        class Usage:
            def reset_current_thread(self):
                return None

            def snapshot_current_thread(self):
                return llm_usage

            def snapshot_current_thread_by_phase(self):
                return llm_usage_by_phase

        class Vsm:
            def reset_current_thread_embedding_usage(self):
                return None

            def get_current_thread_embedding_usage_snapshot(self):
                return embedding_usage

        def configure(final, events, *, fail_review=False):
            agent = FinancialAgent.__new__(FinancialAgent)
            agent.graph = _FakeGraph(final)
            agent.vsm = Vsm()
            agent.llm_usage_callback = Usage()
            agent._project_runtime_calculation_trace = Mock(return_value=initial_trace)
            agent._repair_public_runtime_calculation_trace = Mock(
                side_effect=[initial_trace, repaired_trace]
            )
            agent._public_projection_state = Mock(return_value={})
            agent._late_runtime_numeric_answer = Mock(return_value="")
            agent._with_public_answer = Mock(
                side_effect=lambda state, answer: {**dict(state), "answer": answer}
            )
            agent._runtime_evidence_from_retrieved_docs = Mock(return_value=runtime_evidence)
            agent._complete_aggregate_public_answer_projection = Mock(return_value=("", {}))
            agent._structured_result_answer_for_missing_public_answer = Mock(return_value="")
            agent._apply_stale_structured_numeric_public_answer_repair = Mock(
                side_effect=lambda state, **kwargs: (
                    kwargs["public_answer"],
                    state,
                    kwargs["runtime_calculation_trace"],
                )
            )
            agent._structured_public_answer_trace_projection = Mock(return_value={})
            agent._retrieved_ratio_context_projection_for_public_answer = Mock(return_value={})
            projections = {}
            projections["debug"] = Mock(
                side_effect=lambda final_arg: events.append(("debug", final_arg)) or debug_traces
            )
            projections["citations"] = Mock(
                side_effect=lambda citations_arg, evidence_arg: events.append(
                    ("citations", citations_arg, evidence_arg)
                )
                or projected_citations
            )
            projections["agent"] = Mock(
                side_effect=lambda final_arg, **kwargs: events.append(
                    ("agent", final_arg, kwargs)
                )
                or agent_answer
            )

            def review(final_arg, **kwargs):
                events.append(("review", final_arg, kwargs))
                if fail_review:
                    raise RuntimeError("review projection failed")
                return review_trace

            projections["review"] = Mock(side_effect=review)
            projections["bundle"] = Mock(
                side_effect=lambda **kwargs: events.append(("bundle", kwargs)) or debug_bundle
            )
            return agent, projections

        final = self._base_final_state()
        final["structured_result"] = {"status": "structured", "nested": nested}
        final["evidence_items"] = [{"evidence_id": "final", "nested": nested}]
        final["nested"] = nested
        before_final = deepcopy(final)
        events = []
        agent, projections = configure(final, events)

        def append_surface(trace, evidence, *, final_answer):
            events.append(("append", trace, evidence, final_answer))
            return appended_trace

        def project_artifacts(tasks, artifacts):
            events.append(("artifact", tasks, artifacts))
            return task_artifact_trace

        with (
            patch.object(financial_graph, "_structured_result_subtask_rows_and_answer", return_value=([], "")),
            patch.object(
                financial_graph,
                "append_final_answer_surface_operands_from_evidence",
                side_effect=append_surface,
            ),
            patch.object(financial_graph, "_project_task_artifact_trace", side_effect=project_artifacts),
            patch.object(financial_graph, "project_debug_traces", projections["debug"]),
            patch.object(
                financial_graph,
                "augment_citations_from_runtime_evidence",
                projections["citations"],
            ),
            patch.object(financial_graph, "project_agent_answer", projections["agent"]),
            patch.object(financial_graph, "project_review_trace", projections["review"]),
            patch.object(financial_graph, "project_debug_bundle", projections["bundle"]),
        ):
            result = FinancialAgent.run(agent, "query", report_scope={"company": "Scope"})

        self.assertEqual(
            [event[0] for event in events],
            ["append", "debug", "citations", "artifact", "agent", "review", "bundle"],
        )
        self.assertIs(events[0][1], repaired_trace)
        self.assertEqual(events[0][3], "25.4%")
        projected_final = events[1][1]
        self.assertIsNot(projected_final, final)
        self.assertEqual(projected_final, final)
        self.assertIs(projected_final["nested"], nested)
        self.assertIs(events[2][1], final["citations"])
        self.assertIs(events[2][2], runtime_evidence)
        self.assertIs(events[3][1], final["tasks"])
        self.assertIs(events[3][2], final["artifacts"])
        self.assertIs(events[4][1], projected_final)
        agent_kwargs = events[4][2]
        self.assertEqual(agent_kwargs["public_answer"], "25.4%")
        self.assertIs(agent_kwargs["citations"], projected_citations)
        self.assertIsNot(agent_kwargs["structured_result"], final["structured_result"])
        self.assertIs(agent_kwargs["structured_result"]["nested"], nested)
        self.assertIs(agent_kwargs["runtime_calculation_trace"], appended_trace)
        self.assertIs(events[5][1], projected_final)
        self.assertIs(events[5][2]["runtime_evidence"], runtime_evidence)
        self.assertIs(events[5][2]["task_artifact_trace"], task_artifact_trace)
        self.assertIs(events[6][1]["debug_traces"], debug_traces)
        self.assertIs(events[6][1]["llm_usage"], llm_usage)
        self.assertIs(events[6][1]["llm_usage_by_phase"], llm_usage_by_phase)
        self.assertIs(events[6][1]["embedding_usage"], embedding_usage)
        self.assertIs(result["agent_answer"], agent_answer)
        self.assertIs(result["review_trace"], review_trace)
        self.assertIs(result["debug_bundle"], debug_bundle)
        self.assertEqual(result["agent_marker"], "agent")
        self.assertEqual(result["review_marker"], "review")
        self.assertEqual(result["debug_marker"], "debug")
        self.assertEqual(final, before_final)
        self.assertIs(final["nested"], nested)
        self.assertIs(runtime_evidence[0]["nested"], nested)

        failure_events = []
        failing_agent, failing_projections = configure(final, failure_events, fail_review=True)
        with (
            patch.object(financial_graph, "_structured_result_subtask_rows_and_answer", return_value=([], "")),
            patch.object(
                financial_graph,
                "append_final_answer_surface_operands_from_evidence",
                side_effect=lambda trace, evidence, *, final_answer: failure_events.append(
                    ("append", trace, evidence, final_answer)
                )
                or appended_trace,
            ),
            patch.object(
                financial_graph,
                "_project_task_artifact_trace",
                side_effect=lambda tasks, artifacts: failure_events.append(
                    ("artifact", tasks, artifacts)
                )
                or task_artifact_trace,
            ),
            patch.object(financial_graph, "project_debug_traces", failing_projections["debug"]),
            patch.object(
                financial_graph,
                "augment_citations_from_runtime_evidence",
                failing_projections["citations"],
            ),
            patch.object(financial_graph, "project_agent_answer", failing_projections["agent"]),
            patch.object(financial_graph, "project_review_trace", failing_projections["review"]),
            patch.object(financial_graph, "project_debug_bundle", failing_projections["bundle"]),
            self.assertRaisesRegex(RuntimeError, "review projection failed"),
        ):
            FinancialAgent.run(failing_agent, "query")
        self.assertEqual(
            [event[0] for event in failure_events],
            ["append", "debug", "citations", "artifact", "agent", "review"],
        )
        failing_projections["bundle"].assert_not_called()
        self.assertIs(failure_events[2][1], final["citations"])
        self.assertIs(failure_events[2][2], runtime_evidence)
        self.assertIs(failure_events[5][2]["runtime_evidence"], runtime_evidence)
        self.assertIs(failure_events[5][2]["task_artifact_trace"], task_artifact_trace)
        self.assertEqual(final, before_final)
        self.assertIs(final["nested"], nested)
        self.assertIs(runtime_evidence[0]["nested"], nested)


if __name__ == "__main__":
    unittest.main()
