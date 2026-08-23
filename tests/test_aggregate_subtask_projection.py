import ast
import inspect
import json
import math
import unittest
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.agent import (
    financial_aggregate_state,
    financial_aggregate_projection,
    financial_answer_projection,
    financial_answer_slots,
    financial_calculation_execution,
    financial_graph,
    financial_graph_calculation,
    financial_graph_planning,
    financial_operand_resolution,
    financial_runtime_trace,
)
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_aggregate_state import (
    AggregateCompositionState,
    _AggregateMutableState,
    _AggregateSynthesisState,
    apply_aggregate_composition_answer,
)
from src.agent.financial_aggregate_projection import (
    AggregateArithmeticComponentSyncInput,
    AggregateAnswerCandidateApplicationInput,
    AggregateAnswerCandidatePackagingInput,
    AggregateNestedSubtaskSynchronizationInput,
    AggregateProjectionRowSurfaceSyncInput,
    AggregateProjectionProvenanceFilterInput,
    AggregateProjectionFinalAnswerSyncInput,
    AggregateRefreshedAnswerCandidatePackagingInput,
    AggregateStaleRepairProvenanceInput,
    RuntimeRatioAbsoluteMagnitudeProjectionInput,
    aggregate_artifact_payload,
    aggregate_completion_base_payload,
    aggregate_extend_selected_claim_ids,
    aggregate_integrity_extra_refs,
    aggregate_ordered_result_source_refs,
    aggregate_period_context_evidence_items,
    aggregate_projection_apply_override,
    aggregate_projection_for_integrity,
    aggregate_result_operation_family,
    aggregate_selected_claim_ids,
    aggregate_source_task_ids,
    aggregate_task_status_value,
    apply_aggregate_answer_candidate,
    filter_aggregate_projection_provenance,
    package_aggregate_answer_candidate,
    package_refreshed_aggregate_answer_candidate,
    project_runtime_ratio_absolute_magnitude,
    select_aggregate_stale_repair_provenance,
    synchronize_aggregate_arithmetic_components,
    synchronize_aggregate_projection_row_surface,
    synchronize_nested_aggregate_subtask_rows,
    sync_aggregate_projection_final_answer,
)
from src.agent.financial_operand_resolution import evidence_item_conflicts_requested_scope
from src.agent.financial_dependency_projection import dependency_operand_can_use_source_slot
from src.agent.financial_lookup_recovery import refine_lookup_slot_unit_from_evidence
from src.agent.financial_runtime_trace import _resolve_runtime_calculation_trace
from src.agent.financial_task_artifacts import (
    AggregateArtifactProjectionPayloadSyncInput,
    aggregate_answer_artifact_update,
    calculation_plan_artifact_update,
    calculation_result_artifact_update,
    operand_set_artifact_update,
    reconciliation_result_artifact_update,
    reflection_report_artifact_update,
    semantic_plan_artifact_update,
    synchronize_aggregate_artifact_projection_payload,
    supersede_task_with_aggregate_result,
)


def _stale_provenance_row(
    claim_id: str,
    source_row_id: str = "",
    *,
    operation_family: str = "growth_rate",
    metric_label: str = "revenue growth",
) -> dict:
    row = {
        "operation_family": operation_family,
        "metric_label": metric_label,
        "selected_claim_ids": [claim_id],
    }
    if source_row_id:
        row["calculation_result"] = {"source_row_ids": [source_row_id]}
    return row


def _repaired_growth_result() -> dict:
    return {
        "answer_slots": {
            "operation_family": "growth_rate",
            "metric_label": "revenue growth",
        }
    }


def _collapsed_ratio_trace_fixture() -> dict:
    nested = {"preserve": True}
    return {
        "calculation_operands": [
            {"matched_operand_role": "numerator_1", "raw_value": "old", "nested": nested},
            {"matched_operand_role": "denominator_1", "raw_value": "old", "nested": nested},
        ],
        "calculation_plan": {"operation": "ratio", "nested": nested},
        "calculation_result": {
            "status": "ok",
            "operation_family": "ratio",
            "formatted_result": "stale",
            "answer_slots": {
                "operation_family": "ratio",
                "components_by_group": {
                    "numerator": [
                        {
                            "role": "numerator_1",
                            "label": "alpha beta",
                            "normalized_value": 1.0,
                            "normalized_unit": "KRW",
                            "raw_unit": "KRW",
                            "source_row_id": "same",
                            "source_anchor": "anchor-main",
                            "nested": nested,
                        }
                    ],
                    "denominator": [
                        {
                            "role": "denominator_1",
                            "label": "total",
                            "normalized_value": 1.0,
                            "normalized_unit": "KRW",
                            "raw_unit": "KRW",
                            "source_row_id": "same",
                            "source_anchor": "anchor-total",
                            "nested": nested,
                        }
                    ],
                },
                "components_by_role": {"keep": [{"nested": nested}]},
                "primary_value": {"rendered_value": "stale", "nested": nested},
                "nested": nested,
            },
            "nested": nested,
        },
        "nested": nested,
    }


class AggregateSubtaskProjectionTests(unittest.TestCase):
    def test_current_source_narrative_summary_predicate_precedence_access_and_exceptions(self) -> None:
        nested = {"preserve": True}
        events = []

        class MetricValue:
            def __str__(self) -> str:
                events.append("metric:str")
                return "  Narrative   Summary  "

        class RecordingRow(dict):
            def get(self, key, default=None):
                events.append(f"row:get:{key}")
                return super().get(key, default)

        row = RecordingRow(metric_family=MetricValue(), nested=nested)
        operation_family = Mock(
            side_effect=lambda candidate: events.append("operation") or "lookup"
        )

        def normalise(value):
            events.append(f"normalise:{value}")
            return "Narrative_Summary"

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", operation_family),
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalise),
        ):
            self.assertTrue(financial_aggregate_projection.row_is_narrative_summary(row))
        self.assertEqual(
            events,
            [
                "row:get:metric_family",
                "metric:str",
                "normalise:  Narrative   Summary  ",
                "operation",
            ],
        )
        operation_family.assert_called_once_with(row)
        self.assertIs(row["nested"], nested)
        self.assertEqual(set(row), {"metric_family", "nested"})

        with patch.object(
            financial_aggregate_projection,
            "aggregate_result_operation_family",
            side_effect=("narrative_summary", "lookup"),
        ) as operation_family:
            self.assertTrue(financial_aggregate_projection.row_is_narrative_summary({"metric_family": "other"}))
            self.assertFalse(financial_aggregate_projection.row_is_narrative_summary({"metric_family": "other"}))
        self.assertEqual(operation_family.call_count, 2)

        class GetBomb(dict):
            def get(self, key, default=None):
                raise RuntimeError("metric access failed")

        class StringBomb:
            def __str__(self) -> str:
                raise RuntimeError("metric string failed")

        downstream = Mock(return_value="narrative_summary")
        with patch.object(financial_aggregate_projection, "aggregate_result_operation_family", downstream):
            with self.assertRaisesRegex(RuntimeError, "metric access failed"):
                financial_aggregate_projection.row_is_narrative_summary(GetBomb())
            with self.assertRaisesRegex(RuntimeError, "metric string failed"):
                financial_aggregate_projection.row_is_narrative_summary({"metric_family": StringBomb()})
            with patch.object(
                financial_aggregate_projection,
                "_normalise_spaces",
                side_effect=RuntimeError("metric normalization failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, "metric normalization failed"):
                    financial_aggregate_projection.row_is_narrative_summary({"metric_family": "narrative_summary"})
        downstream.assert_not_called()

        with patch.object(
            financial_aggregate_projection,
            "aggregate_result_operation_family",
            side_effect=RuntimeError("operation family failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "operation family failed"):
                financial_aggregate_projection.row_is_narrative_summary({"metric_family": "narrative_summary"})

        class FalsyMetric:
            def __bool__(self) -> bool:
                events.append("metric:bool:false")
                return False

            def __str__(self) -> str:
                raise RuntimeError("falsy metric string accessed")

        events.clear()
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="lookup") as operation_family,
            patch.object(
                financial_aggregate_projection,
                "_normalise_spaces",
                side_effect=lambda value: events.append(f"normalise:{value}") or value,
            ),
        ):
            self.assertFalse(financial_aggregate_projection.row_is_narrative_summary({"metric_family": FalsyMetric()}))
        self.assertEqual(events, ["metric:bool:false", "normalise:"])
        operation_family.assert_called_once()

        class TruthinessBomb:
            def __bool__(self) -> bool:
                raise RuntimeError("metric truthiness failed")

        downstream = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", downstream),
            patch.object(financial_aggregate_projection, "_normalise_spaces") as normalizer,
        ):
            with self.assertRaisesRegex(RuntimeError, "metric truthiness failed"):
                financial_aggregate_projection.row_is_narrative_summary({"metric_family": TruthinessBomb()})
        normalizer.assert_not_called()
        downstream.assert_not_called()

        class LowerBomb:
            def lower(self):
                raise RuntimeError("metric lower failed")

        downstream = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", downstream),
            patch.object(financial_aggregate_projection, "_normalise_spaces", return_value=LowerBomb()),
        ):
            with self.assertRaisesRegex(RuntimeError, "metric lower failed"):
                financial_aggregate_projection.row_is_narrative_summary({"metric_family": "metric"})
        downstream.assert_not_called()

    def test_current_source_safe_partial_answer_branch_laziness_dedupe_and_exceptions(self) -> None:
        nested = {"preserve": True}

        class AccessBomb(dict):
            def get(self, key, default=None):
                raise RuntimeError(f"unexpected {key} access")

        class StringBomb:
            def __init__(self, message: str):
                self.message = message

            def __str__(self) -> str:
                raise RuntimeError(self.message)

        narrative_row = AccessBomb(kind="narrative")
        failed_row = {
            "status": "failed",
            "calculation_result": AccessBomb(),
            "answer": StringBomb("failed answer accessed"),
        }
        whitespace_status_row = {
            "status": "   ",
            "calculation_result": AccessBomb(),
            "answer": StringBomb("whitespace-status answer accessed"),
        }
        direct_row = {
            "status": "ok",
            "answer": "  direct   answer ",
            "calculation_result": AccessBomb(),
            "nested": nested,
        }
        duplicate_row = {"calculation_result": {"status": "ok"}, "answer": "direct answer"}
        formatted_row = {
            "calculation_result": {"status": "ok", "formatted_result": " formatted answer "}
        }
        rendered_row = {
            "status": "OK",
            "calculation_result": {"rendered_value": " rendered answer "},
        }
        whitespace_formatted_row = {
            "status": "ok",
            "calculation_result": {
                "formatted_result": "   ",
                "rendered_value": StringBomb("rendered fallback accessed"),
            },
        }
        gap_row = {
            "status": "ok",
            "answer": StringBomb("gap answer accessed"),
            "calculation_result": AccessBomb(),
        }
        rows = [
            narrative_row,
            failed_row,
            whitespace_status_row,
            direct_row,
            duplicate_row,
            formatted_row,
            rendered_row,
            whitespace_formatted_row,
            gap_row,
        ]
        original_keys = [tuple(row.keys()) for row in rows]
        narrative_gate = Mock(side_effect=lambda candidate: candidate is narrative_row)
        gap_gate = Mock(side_effect=lambda candidate: "missing" if candidate is gap_row else "")
        with (
            patch.object(financial_aggregate_projection, "row_is_narrative_summary", narrative_gate),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                gap_gate,
            ),
        ):
            answer = financial_aggregate_projection.safe_partial_answer_for_numeric_gap(rows)

        self.assertEqual(answer, "direct answer formatted answer rendered answer")
        self.assertEqual([tuple(row.keys()) for row in rows], original_keys)
        self.assertIs(direct_row["nested"], nested)
        self.assertEqual(narrative_gate.call_args_list, [unittest.mock.call(row) for row in rows])
        self.assertEqual(
            [call.args[0] for call in gap_gate.call_args_list],
            [
                direct_row,
                duplicate_row,
                formatted_row,
                rendered_row,
                whitespace_formatted_row,
                gap_row,
            ],
        )

        copy_events = []

        class RecordingCalculation(Mapping):
            def __init__(self) -> None:
                self.data = {"status": "ok", "formatted_result": "copied answer"}

            def __bool__(self) -> bool:
                copy_events.append("calculation:bool")
                return True

            def get(self, key, default=None):
                copy_events.append(f"calculation:get:{key}")
                return self.data.get(key, default)

            def keys(self):
                copy_events.append("calculation:keys")
                return self.data.keys()

            def __getitem__(self, key):
                copy_events.append(f"calculation:item:{key}")
                return self.data[key]

            def __iter__(self):
                return iter(self.data)

            def __len__(self) -> int:
                return len(self.data)

        recording_calculation = RecordingCalculation()
        recording_row = {"calculation_result": recording_calculation}
        with (
            patch.object(financial_aggregate_projection, "row_is_narrative_summary", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.safe_partial_answer_for_numeric_gap([recording_row]),
                "copied answer",
            )
        self.assertEqual(
            copy_events,
            [
                "calculation:bool",
                "calculation:get:status",
                "calculation:bool",
                "calculation:keys",
                "calculation:item:status",
                "calculation:item:formatted_result",
            ],
        )
        self.assertIs(recording_row["calculation_result"], recording_calculation)
        self.assertEqual(recording_calculation.data, {"status": "ok", "formatted_result": "copied answer"})

        class CopyBomb(RecordingCalculation):
            def keys(self):
                raise RuntimeError("calculation copy failed")

        with (
            patch.object(financial_aggregate_projection, "row_is_narrative_summary", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "calculation copy failed"):
                financial_aggregate_projection.safe_partial_answer_for_numeric_gap(
                    [{"calculation_result": CopyBomb()}]
                )

        status_bomb = AccessBomb()
        with patch.object(financial_aggregate_projection, "row_is_narrative_summary", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "unexpected status access"):
                financial_aggregate_projection.safe_partial_answer_for_numeric_gap([status_bomb])

        gap_runtime_row = {"status": "ok", "answer": "unused"}
        with (
            patch.object(financial_aggregate_projection, "row_is_narrative_summary", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                side_effect=RuntimeError("gap policy failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "gap policy failed"):
                financial_aggregate_projection.safe_partial_answer_for_numeric_gap([gap_runtime_row])

        with patch.object(
            financial_aggregate_projection,
            "row_is_narrative_summary",
            side_effect=RuntimeError("narrative gate failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "narrative gate failed"):
                financial_aggregate_projection.safe_partial_answer_for_numeric_gap([{"status": "ok"}])

        with (
            patch.object(financial_aggregate_projection, "row_is_narrative_summary", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "answer string failed"):
                financial_aggregate_projection.safe_partial_answer_for_numeric_gap(
                    [{"status": "ok", "answer": StringBomb("answer string failed")}]
                )

        with patch.object(financial_aggregate_projection, "row_is_narrative_summary", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "status string failed"):
                financial_aggregate_projection.safe_partial_answer_for_numeric_gap(
                    [{"status": StringBomb("status string failed")}]
                )

        with (
            patch.object(financial_aggregate_projection, "row_is_narrative_summary", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(
                financial_aggregate_projection,
                "_normalise_spaces",
                side_effect=RuntimeError("answer normalization failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "answer normalization failed"):
                financial_aggregate_projection.safe_partial_answer_for_numeric_gap(
                    [{"status": "ok", "answer": "answer"}]
                )

    def test_current_source_answer_surface_static_bindings_and_post_move_distribution(self) -> None:
        module_trees = {
            "graph": ast.parse(inspect.getsource(financial_graph_calculation)),
            "owner": ast.parse(inspect.getsource(financial_aggregate_projection)),
        }
        targets = {
            "row": "row_is_narrative_summary",
            "safe": "safe_partial_answer_for_numeric_gap",
        }
        definitions = {}
        calls = {key: [] for key in targets}

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name) -> None:
                self.module_name = module_name
                self.function_stack = []

            def visit_FunctionDef(self, node):
                if node.name in targets.values():
                    definitions[node.name] = (self.module_name, node)
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node):
                called_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                receiver = (
                    ast.unparse(node.func.value)
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                for key, target in targets.items():
                    if called_name == target:
                        calls[key].append(
                            (
                                self.module_name,
                                self.function_stack[-1] if self.function_stack else "<module>",
                                receiver,
                                tuple(ast.unparse(arg) for arg in node.args),
                                tuple(
                                    (keyword.arg, ast.unparse(keyword.value))
                                    for keyword in node.keywords
                                ),
                            )
                        )
                self.generic_visit(node)

        for module_name, module_tree in module_trees.items():
            BindingVisitor(module_name).visit(module_tree)
        self.assertEqual(
            {
                name: (module_name, node.end_lineno - node.lineno + 1)
                for name, (module_name, node) in definitions.items()
            },
            {
                "row_is_narrative_summary": ("owner", 4),
                "safe_partial_answer_for_numeric_gap": ("owner", 25),
            },
        )
        self.assertEqual(len(calls["row"]), 20)
        self.assertEqual(len(calls["safe"]), 4)
        self.assertEqual(
            Counter((caller, args) for module, caller, receiver, args, keywords in calls["row"]),
            Counter(
                {
                    ("_unresolved_structured_numeric_gap", ("row",)): 1,
                    ("safe_partial_answer_for_numeric_gap", ("row",)): 1,
                    ("compose_lookup_list_numeric_answer", ("row",)): 1,
                    ("append_uncovered_lookup_numeric_items", ("row",)): 1,
                    ("_supported_aggregate_subtask_answer", ("row",)): 1,
                    ("_preferred_conflicting_growth_narrative_answer", ("row",)): 1,
                    ("answer_reuses_narrative_summary_text", ("row",)): 1,
                    ("_refresh_numeric_answer_preserving_narrative_context", ("row",)): 3,
                    ("_preferred_aggregate_fallback_answer", ("row",)): 2,
                    ("_apply_final_narrative_repair_pipeline", ("row",)): 1,
                    ("_prune_nonfocus_numeric_narrative_sentences", ("row",)): 1,
                    ("_preserve_policy_required_context_in_narrative_results", ("row_copy",)): 1,
                    ("_supported_growth_narrative_candidate_sentences", ("row",)): 1,
                    ("_prune_irrelevant_growth_narrative_sentences", ("row",)): 1,
                    ("_prepare_initial_aggregate_state", ("row",)): 1,
                    ("_resolve_aggregate_feedback_state", ("row",)): 1,
                    ("_resolve_aggregate_feedback_state", ("source",)): 1,
                }
            ),
        )
        self.assertEqual(
            Counter((caller, args) for module, caller, receiver, args, keywords in calls["safe"]),
            Counter(
                {
                    ("_preferred_aggregate_fallback_answer", ("ordered_results",)): 1,
                    ("_apply_initial_aggregate_answer_composition", ("ordered_results",)): 1,
                    ("_apply_final_narrative_repair_pipeline", ("ordered_results",)): 1,
                    ("_resolve_aggregate_feedback_state", ("ordered_results",)): 1,
                }
            ),
        )
        self.assertTrue(
            all(
                receiver == "" and not keywords
                for entries in calls.values()
                for _, _, receiver, _, keywords in entries
            )
        )

        owner_local = sum(
            module == "owner"
            for entries in calls.values()
            for module, _caller, _receiver, _args, _keywords in entries
        )
        graph_external = sum(map(len, calls.values())) - owner_local
        self.assertEqual((graph_external, owner_local), (20, 4))
        self.assertEqual(
            [
                (key, caller, args)
                for key, entries in calls.items()
                for module, caller, _receiver, args, _keywords in entries
                if module == "owner"
            ],
            [
                ("row", "answer_reuses_narrative_summary_text", ("row",)),
                ("row", "safe_partial_answer_for_numeric_gap", ("row",)),
                ("row", "compose_lookup_list_numeric_answer", ("row",)),
                ("row", "append_uncovered_lookup_numeric_items", ("row",)),
            ],
        )

    def test_current_source_safe_partial_caller_gate_adoption_and_exception_stop(self) -> None:
        agent = financial_graph_calculation.FinancialAgentCalculationMixin()
        row = {"task_id": "lookup", "nested": {"preserve": True}}
        ordered_results = [row]
        adopted_answer = "safe partial answer"
        events = []

        with (
            patch.object(
                agent,
                "_unresolved_structured_numeric_gap",
                side_effect=lambda rows: events.append(("gap", rows)) or "missing",
            ) as gap_gate,
            patch.object(
                financial_graph_calculation,
                "safe_partial_answer_for_numeric_gap",
                side_effect=lambda rows: events.append(("safe", rows)) or adopted_answer,
            ) as safe_partial,
            patch.object(agent, "_supported_aggregate_subtask_answer") as downstream,
        ):
            actual = agent._preferred_aggregate_fallback_answer(ordered_results, "default")
        self.assertIs(actual, adopted_answer)
        self.assertEqual(events, [("gap", ordered_results), ("safe", ordered_results)])
        gap_gate.assert_called_once_with(ordered_results)
        safe_partial.assert_called_once_with(ordered_results)
        downstream.assert_not_called()
        self.assertIs(ordered_results[0], row)

        downstream = Mock()
        with (
            patch.object(agent, "_unresolved_structured_numeric_gap", return_value="missing"),
            patch.object(
                financial_graph_calculation,
                "safe_partial_answer_for_numeric_gap",
                side_effect=RuntimeError("safe partial failed"),
            ) as safe_partial,
            patch.object(agent, "_supported_aggregate_subtask_answer", downstream),
        ):
            with self.assertRaisesRegex(RuntimeError, "safe partial failed"):
                agent._preferred_aggregate_fallback_answer(ordered_results, "default")
        safe_partial.assert_called_once_with(ordered_results)
        downstream.assert_not_called()

        with (
            patch.object(agent, "_unresolved_structured_numeric_gap", return_value=""),
            patch.object(financial_graph_calculation, "safe_partial_answer_for_numeric_gap") as safe_partial,
            patch.object(
                agent,
                "_supported_aggregate_subtask_answer",
                return_value="supported answer",
            ) as downstream,
        ):
            self.assertEqual(
                agent._preferred_aggregate_fallback_answer(ordered_results, "default"),
                "supported answer",
            )
        safe_partial.assert_not_called()
        downstream.assert_called_once_with(ordered_results)

    def test_current_source_lookup_list_compose_all_lookup_status_gap_dedupe_and_policy(self) -> None:
        agent = financial_graph_calculation.FinancialAgentCalculationMixin()
        nested = {"preserve": True}

        class AccessBomb(dict):
            def get(self, key, default=None):
                raise RuntimeError(f"unexpected {key} access")

        narrative = AccessBomb()
        failed = {
            "kind": "lookup",
            "status": "failed",
            "calculation_result": AccessBomb(),
        }
        gap = {"kind": "lookup", "status": "ok", "answer": "gap"}
        first = {"kind": "lookup", "status": "ok", "nested": nested}
        duplicate = {"kind": "single_value", "calculation_result": {"status": "ok"}}
        second = {"kind": "lookup", "status": "OK"}
        rows = [narrative, failed, gap, first, duplicate, second]
        snapshots = [dict(row) for row in rows]
        policy_events = []

        class RecordingPolicy(dict):
            def get(self, key, default=None):
                policy_events.append(key)
                return super().get(key, default)

        operation_family = Mock(side_effect=lambda row: row["kind"])
        gap_gate = Mock(side_effect=lambda row: "missing" if row is gap else "")
        item_answer = Mock(
            side_effect=lambda row: {
                id(first): "first 1",
                id(duplicate): "first 1",
                id(second): "second 2",
            }[id(row)]
        )
        with (
            patch.object(
                financial_aggregate_projection,
                "row_is_narrative_summary",
                side_effect=lambda row: row is narrative,
            ) as narrative_gate,
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                operation_family,
            ),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                gap_gate,
            ),
            patch.object(financial_aggregate_projection, "_lookup_numeric_item_answer", item_answer),
            patch.object(
                financial_aggregate_projection,
                "CALCULATION_RENDER_POLICY",
                RecordingPolicy(
                    lookup_list_separator=" | ",
                    lookup_list_answer_template="items=[{items}]",
                ),
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.compose_lookup_list_numeric_answer(rows),
                "items=[first 1 | second 2]",
            )
        self.assertEqual(narrative_gate.call_count, len(rows))
        self.assertEqual(
            [call.args[0] for call in operation_family.call_args_list],
            [failed, gap, first, duplicate, second],
        )
        self.assertEqual(
            [call.args[0] for call in gap_gate.call_args_list],
            [gap, first, duplicate, second],
        )
        self.assertEqual(
            [call.args[0] for call in item_answer.call_args_list],
            [first, duplicate, second],
        )
        self.assertEqual(policy_events, ["lookup_list_separator", "lookup_list_answer_template"])
        self.assertEqual([dict(row) for row in rows], snapshots)
        self.assertIs(first["nested"], nested)

        later_row = AccessBomb()
        policy = AccessBomb()
        with (
            patch.object(
                financial_aggregate_projection,
                "row_is_narrative_summary",
                return_value=False,
            ) as narrative_gate,
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=("lookup", "ratio"),
            ) as operation_family,
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(
                financial_aggregate_projection,
                "_lookup_numeric_item_answer",
                return_value="first 1",
            ) as item_answer,
            patch.object(financial_aggregate_projection, "CALCULATION_RENDER_POLICY", policy),
        ):
            self.assertEqual(
                financial_aggregate_projection.compose_lookup_list_numeric_answer(
                    [{"status": "ok"}, {"status": "ok"}, later_row]
                ),
                "",
            )
        self.assertEqual(narrative_gate.call_count, 2)
        self.assertEqual(operation_family.call_count, 2)
        item_answer.assert_called_once()

        for candidate_rows, answers in (
            ([{"status": "ok"}], ["only 1"]),
            ([{"status": "ok"}, {"status": "ok"}], ["same 1", "same 1"]),
        ):
            with (
                patch.object(
                    financial_aggregate_projection,
                    "row_is_narrative_summary",
                    return_value=False,
                ),
                patch.object(
                    financial_aggregate_projection,
                    "aggregate_result_operation_family",
                    return_value="lookup",
                ),
                patch.object(
                    financial_aggregate_projection,
                    "material_gap_feedback_for_subtask_result",
                    return_value="",
                ),
                patch.object(
                    financial_aggregate_projection,
                    "_lookup_numeric_item_answer",
                    side_effect=answers,
                ),
                patch.object(
                    financial_aggregate_projection,
                    "CALCULATION_RENDER_POLICY",
                    AccessBomb(),
                ),
            ):
                self.assertEqual(
                    financial_aggregate_projection.compose_lookup_list_numeric_answer(candidate_rows),
                    "",
                )

        gap_gate = Mock()
        item_answer = Mock()
        with (
            patch.object(financial_aggregate_projection, "row_is_narrative_summary", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=RuntimeError("operation family failed"),
            ) as operation_family,
            patch.object(financial_aggregate_projection, "material_gap_feedback_for_subtask_result", gap_gate),
            patch.object(financial_aggregate_projection, "_lookup_numeric_item_answer", item_answer),
        ):
            with self.assertRaisesRegex(RuntimeError, "operation family failed"):
                financial_aggregate_projection.compose_lookup_list_numeric_answer(
                    [{"status": "ok"}]
                )
        operation_family.assert_called_once()
        gap_gate.assert_not_called()
        item_answer.assert_not_called()

    def test_current_source_append_uncovered_lookup_filter_conflict_dedupe_and_copy_contract(self) -> None:
        agent = financial_graph_calculation.FinancialAgentCalculationMixin()

        class IterationBomb(list):
            def __iter__(self):
                raise RuntimeError("ordered results accessed")

        operation_family = Mock()
        with patch.object(
            financial_aggregate_projection,
            "aggregate_result_operation_family",
            operation_family,
        ):
            self.assertEqual(
                financial_aggregate_projection.append_uncovered_lookup_numeric_items(
                    "  ", IterationBomb()
                ),
                "",
            )
        operation_family.assert_not_called()

        lookup_only = {"kind": "lookup"}
        narrative_gate = Mock()
        primary_slot_owner = Mock()
        item_answer = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=lambda row: row["kind"],
            ) as operation_family,
            patch.object(financial_aggregate_projection, "row_is_narrative_summary", narrative_gate),
            patch.object(
                financial_aggregate_projection,
                "aggregate_row_primary_answer_slot",
                primary_slot_owner,
            ),
            patch.object(financial_aggregate_projection, "_lookup_numeric_item_answer", item_answer),
        ):
            self.assertEqual(
                financial_aggregate_projection.append_uncovered_lookup_numeric_items(
                    "  base answer  ",
                    [object(), lookup_only],
                ),
                "base answer",
            )
        operation_family.assert_called_once_with(lookup_only)
        narrative_gate.assert_not_called()
        primary_slot_owner.assert_not_called()
        item_answer.assert_not_called()

        nested = {"preserve": True}

        class CopyOnlySlot(dict):
            def get(self, key, default=None):
                raise RuntimeError("original component slot accessed")

        component_slot = CopyOnlySlot(
            label="ratio component",
            normalized_value=100.0,
            normalized_unit="COUNT",
            nested=nested,
        )
        ratio = {
            "kind": "ratio",
            "calculation_result": {
                "answer_slots": {
                    "components_by_group": {
                        "numerator": [component_slot, object()],
                        "empty": None,
                    }
                }
            },
        }
        narrative = {"kind": "narrative"}
        failed = {"kind": "lookup", "status": "failed"}
        gap = {"kind": "lookup", "status": "ok"}
        conflict = {"kind": "lookup", "status": "ok"}
        covered = {"kind": "lookup", "calculation_result": {"status": "ok"}}
        label_covered = {"kind": "single_value", "status": "OK"}
        duplicate_one = {"kind": "lookup", "status": "ok"}
        duplicate_two = {"kind": "single_value", "status": "ok"}
        blank_item = {"kind": "lookup", "status": "ok"}
        within_tolerance = {"kind": "lookup", "status": "ok"}
        unit_mismatch = {"kind": "lookup", "status": "ok"}
        invalid_value = {"kind": "lookup", "status": "ok"}
        rows = [
            ratio,
            narrative,
            failed,
            gap,
            conflict,
            covered,
            label_covered,
            duplicate_one,
            duplicate_two,
            blank_item,
            within_tolerance,
            unit_mismatch,
            invalid_value,
            object(),
        ]

        def freeze(value):
            if isinstance(value, dict):
                return tuple((key, freeze(item)) for key, item in value.items())
            if isinstance(value, list):
                return tuple(freeze(item) for item in value)
            if isinstance(value, (str, int, float, bool, type(None))):
                return value
            return ("identity", id(value))

        rows_snapshot = freeze(rows)
        slots = {
            id(conflict): {
                "label": "conflict metric",
                "normalized_value": 101.0,
                "normalized_unit": "COUNT",
            },
            id(covered): {
                "label": "covered metric",
                "normalized_value": 100.0,
                "normalized_unit": "COUNT",
            },
            id(label_covered): {
                "label": "mentioned metric",
                "normalized_value": 100.0,
                "normalized_unit": "COUNT",
            },
            id(duplicate_one): {
                "label": "missing metric",
                "normalized_value": 100.0,
                "normalized_unit": "COUNT",
            },
            id(duplicate_two): {
                "label": "missing metric",
                "normalized_value": 100.0,
                "normalized_unit": "COUNT",
            },
            id(blank_item): {
                "label": "blank metric",
                "normalized_value": 100.0,
                "normalized_unit": "COUNT",
            },
            id(within_tolerance): {
                "label": "ratio component",
                "normalized_value": 100.04,
                "normalized_unit": "COUNT",
            },
            id(unit_mismatch): {
                "label": "ratio component",
                "normalized_value": 101.0,
                "normalized_unit": "KG",
            },
            id(invalid_value): {
                "label": "ratio component",
                "normalized_value": "not numeric",
                "normalized_unit": "COUNT",
            },
        }
        answers = {
            id(covered): "covered 20",
            id(label_covered): "mentioned 30",
            id(duplicate_one): "missing 40.",
            id(duplicate_two): "missing 40.",
            id(blank_item): "",
            id(within_tolerance): "near 50.",
            id(unit_mismatch): "unit 60.",
            id(invalid_value): "invalid 70.",
        }

        def operand_match(text, candidate):
            return (
                text == "ratio component"
                and candidate.get("label") in {"conflict metric", "ratio component"}
            ) or (
                text == "base 100" and candidate.get("label") == "mentioned metric"
            )

        gap_gate = Mock(side_effect=lambda row: "missing" if row is gap else "")
        item_answer = Mock(side_effect=lambda row, **_kwargs: answers[id(row)])
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=lambda row: row["kind"],
            ),
            patch.object(
                financial_aggregate_projection,
                "row_is_narrative_summary",
                side_effect=lambda row: row is narrative,
            ) as narrative_gate,
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                gap_gate,
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_row_primary_answer_slot",
                side_effect=lambda row: slots[id(row)],
            ) as primary_slot_owner,
            patch.object(
                financial_aggregate_projection,
                "operand_text_match",
                side_effect=operand_match,
            ) as operand_match_owner,
            patch.object(financial_aggregate_projection, "_lookup_numeric_item_answer", item_answer),
            patch.object(
                financial_aggregate_projection,
                "answer_covers_numeric_answer",
                side_effect=lambda _answer, item: item == "covered 20",
            ) as coverage_gate,
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                return_value=["100"],
            ) as numeric_candidates,
        ):
            appended = financial_aggregate_projection.append_uncovered_lookup_numeric_items(
                " base 100 ", rows
            )
        self.assertEqual(
            appended,
            "missing 40. near 50. unit 60. invalid 70. base 100",
        )
        self.assertEqual(
            [call.args[0] for call in gap_gate.call_args_list],
            [
                gap,
                conflict,
                covered,
                label_covered,
                duplicate_one,
                duplicate_two,
                blank_item,
                within_tolerance,
                unit_mismatch,
                invalid_value,
            ],
        )
        self.assertEqual(
            [call.args[0] for call in item_answer.call_args_list],
            [
                covered,
                label_covered,
                duplicate_one,
                duplicate_two,
                blank_item,
                within_tolerance,
                unit_mismatch,
                invalid_value,
            ],
        )
        self.assertTrue(
            all(
                call.kwargs == {"require_primary_slot": True, "require_numeric": True}
                for call in item_answer.call_args_list
            )
        )
        self.assertEqual(primary_slot_owner.call_count, 15)
        self.assertEqual(coverage_gate.call_count, 7)
        self.assertEqual(numeric_candidates.call_count, 6)
        self.assertGreaterEqual(operand_match_owner.call_count, 12)
        self.assertEqual(freeze(rows), rows_snapshot)
        self.assertIs(component_slot["nested"], nested)
        self.assertEqual(narrative_gate.call_count, 13)

        item_answer = Mock()
        coverage_gate = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=lambda row: row["kind"],
            ),
            patch.object(financial_aggregate_projection, "row_is_narrative_summary", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_row_primary_answer_slot",
                side_effect=RuntimeError("primary slot failed"),
            ) as primary_slot_owner,
            patch.object(financial_aggregate_projection, "_lookup_numeric_item_answer", item_answer),
            patch.object(financial_aggregate_projection, "answer_covers_numeric_answer", coverage_gate),
        ):
            with self.assertRaisesRegex(RuntimeError, "primary slot failed"):
                financial_aggregate_projection.append_uncovered_lookup_numeric_items(
                    "base 100",
                    [ratio, covered],
                )
        primary_slot_owner.assert_called_once_with(covered)
        item_answer.assert_not_called()
        coverage_gate.assert_not_called()

        operation_family = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "_normalise_spaces",
                side_effect=RuntimeError("answer normalization failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                operation_family,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "answer normalization failed"):
                financial_aggregate_projection.append_uncovered_lookup_numeric_items(
                    "base", [ratio]
                )
        operation_family.assert_not_called()

    def test_current_source_lookup_numeric_item_slot_value_float_flags_and_template(self) -> None:
        agent = financial_graph_calculation.FinancialAgentCalculationMixin()

        class StringBomb:
            def __str__(self) -> str:
                raise RuntimeError("later value accessed")

        class PolicyBomb(dict):
            def get(self, key, default=None):
                raise RuntimeError("template policy accessed")

        missing_slot_row = {
            "calculation_result": {
                "answer_slots": {"primary_value": {"rendered_value": StringBomb()}},
                "formatted_result": StringBomb(),
            },
            "answer": StringBomb(),
        }
        with (
            patch.object(financial_aggregate_projection, "answer_slot_has_material", return_value=False) as material,
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates") as numeric,
            patch.object(financial_aggregate_projection, "CALCULATION_RENDER_POLICY", PolicyBomb()),
        ):
            self.assertEqual(
                financial_aggregate_projection._lookup_numeric_item_answer(
                    missing_slot_row,
                    require_primary_slot=True,
                ),
                "",
            )
        material_primary_slot = material.call_args.args[0]
        self.assertIsNot(
            material_primary_slot,
            missing_slot_row["calculation_result"]["answer_slots"]["primary_value"],
        )
        numeric.assert_not_called()

        nested = {"preserve": True}
        primary_slot = {
            "label": " target ",
            "rendered_value": " (10) ",
            "normalized_value": "10",
            "nested": nested,
        }
        row = {
            "metric_label": "fallback label",
            "answer": StringBomb(),
            "calculation_result": {
                "formatted_result": StringBomb(),
                "rendered_value": StringBomb(),
                "answer_slots": {"primary_value": primary_slot},
            },
        }
        answer_bomb = row["answer"]
        calculation_result = row["calculation_result"]
        formatted_bomb = calculation_result["formatted_result"]
        rendered_bomb = calculation_result["rendered_value"]
        row_keys = tuple(row)
        calculation_result_keys = tuple(calculation_result)
        primary_slot_snapshot = {
            key: value
            for key, value in primary_slot.items()
            if key != "nested"
        }
        policy_events = []

        class RecordingPolicy(dict):
            def get(self, key, default=None):
                policy_events.append(key)
                return super().get(key, default)

        numeric = Mock(return_value=["10"])
        with (
            patch.object(
                financial_aggregate_projection,
                "answer_slot_has_material",
                return_value=True,
            ) as material,
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", numeric),
            patch.object(
                financial_aggregate_projection,
                "CALCULATION_RENDER_POLICY",
                RecordingPolicy(lookup_list_item_template="{label}={value}"),
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection._lookup_numeric_item_answer(
                    row,
                    require_primary_slot=True,
                    require_numeric=True,
                ),
                "target=10",
            )
        numeric.assert_called_once_with("10")
        self.assertEqual(policy_events, ["lookup_list_item_template"])
        material_primary_slot = material.call_args.args[0]
        self.assertIsNot(material_primary_slot, primary_slot)
        self.assertIs(material_primary_slot["nested"], nested)
        self.assertEqual(tuple(row), row_keys)
        self.assertEqual(tuple(calculation_result), calculation_result_keys)
        self.assertEqual(
            {key: value for key, value in primary_slot.items() if key != "nested"},
            primary_slot_snapshot,
        )
        self.assertIs(row["answer"], answer_bomb)
        self.assertIs(row["calculation_result"], calculation_result)
        self.assertIs(calculation_result["formatted_result"], formatted_bomb)
        self.assertIs(calculation_result["rendered_value"], rendered_bomb)
        self.assertIs(primary_slot["nested"], nested)

        calc_formatted = {
            "metric_label": " row label ",
            "answer": StringBomb(),
            "answer_slots": {
                "primary_value": {
                    "label": "slot label",
                    "rendered_value": "row-slot value",
                }
            },
            "calculation_result": {
                "formatted_result": "formatted 20",
                "rendered_value": StringBomb(),
                "answer_slots": {"primary_value": {"normalized_value": "bad"}},
            },
        }
        with (
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates") as numeric,
            patch.object(
                financial_aggregate_projection,
                "CALCULATION_RENDER_POLICY",
                {"lookup_list_item_template": "{label}: {value}"},
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection._lookup_numeric_item_answer(calc_formatted),
                "row label: formatted 20",
            )
        numeric.assert_not_called()

        negative_row = {
            "calculation_result": {
                "answer_slots": {
                    "primary_value": {
                        "label": "loss",
                        "rendered_value": "(5)",
                        "normalized_value": -5,
                    }
                }
            }
        }
        soft_float_row = {
            "calculation_result": {
                "answer_slots": {
                    "primary_value": {
                        "label": "unknown",
                        "rendered_value": "(value)",
                        "normalized_value": object(),
                    }
                }
            }
        }
        with patch.object(
            financial_aggregate_projection,
            "CALCULATION_RENDER_POLICY",
            {"lookup_list_item_template": "{label} {value}"},
        ):
            self.assertEqual(
                financial_aggregate_projection._lookup_numeric_item_answer(negative_row),
                "loss (5)",
            )
            self.assertEqual(
                financial_aggregate_projection._lookup_numeric_item_answer(soft_float_row),
                "unknown (value)",
            )

        numeric_row = {
            "metric_label": "metric",
            "answer": "no digits",
        }
        with (
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", return_value=[]),
            patch.object(financial_aggregate_projection, "CALCULATION_RENDER_POLICY", PolicyBomb()),
        ):
            self.assertEqual(
                financial_aggregate_projection._lookup_numeric_item_answer(
                    numeric_row,
                    require_numeric=True,
                ),
                "",
            )

        with patch.object(
            financial_aggregate_projection,
            "CALCULATION_RENDER_POLICY",
            PolicyBomb(),
        ):
            self.assertEqual(
                financial_aggregate_projection._lookup_numeric_item_answer({"answer": "10"}),
                "",
            )
            self.assertEqual(
                financial_aggregate_projection._lookup_numeric_item_answer(
                    {"metric_label": "metric"}
                ),
                "",
            )

        numeric = Mock()
        with (
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", numeric),
            patch.object(financial_aggregate_projection, "CALCULATION_RENDER_POLICY", PolicyBomb()),
        ):
            with self.assertRaisesRegex(RuntimeError, "later value accessed"):
                financial_aggregate_projection._lookup_numeric_item_answer(
                    {
                        "metric_label": "metric",
                        "calculation_result": {
                            "answer_slots": {
                                "primary_value": {"rendered_value": StringBomb()}
                            }
                        },
                    }
                )
        numeric.assert_not_called()

    def test_current_source_lookup_surface_static_bindings_and_planned_owner_distribution(self) -> None:
        module_trees = {
            "graph": ast.parse(inspect.getsource(financial_graph_calculation)),
            "owner": ast.parse(inspect.getsource(financial_aggregate_projection)),
        }
        targets = {
            "row": "row_is_narrative_summary",
            "safe": "safe_partial_answer_for_numeric_gap",
            "compose": "compose_lookup_list_numeric_answer",
            "lookup": "_lookup_numeric_item_answer",
            "append": "append_uncovered_lookup_numeric_items",
        }
        definitions = {}
        calls = {key: [] for key in targets}

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, module_name) -> None:
                self.module_name = module_name
                self.function_stack = []

            def visit_FunctionDef(self, node):
                if node.name in targets.values():
                    definitions[node.name] = (self.module_name, node)
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            visit_AsyncFunctionDef = visit_FunctionDef

            def visit_Call(self, node):
                called_name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                receiver = (
                    ast.unparse(node.func.value)
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                for key, target in targets.items():
                    if called_name == target:
                        calls[key].append(
                            (
                                self.module_name,
                                self.function_stack[-1] if self.function_stack else "<module>",
                                receiver,
                                tuple(ast.unparse(arg) for arg in node.args),
                                tuple(
                                    (keyword.arg, ast.unparse(keyword.value))
                                    for keyword in node.keywords
                                ),
                            )
                        )
                self.generic_visit(node)

        for module_name, module_tree in module_trees.items():
            BindingVisitor(module_name).visit(module_tree)

        self.assertEqual(
            {
                name: (module_name, node.end_lineno - node.lineno + 1)
                for name, (module_name, node) in definitions.items()
            },
            {
                "row_is_narrative_summary": ("owner", 4),
                "safe_partial_answer_for_numeric_gap": ("owner", 25),
                "compose_lookup_list_numeric_answer": ("owner", 26),
                "_lookup_numeric_item_answer": ("owner", 33),
                "append_uncovered_lookup_numeric_items": ("owner", 91),
            },
        )
        self.assertEqual(
            {key: len(entries) for key, entries in calls.items()},
            {"row": 20, "safe": 4, "compose": 1, "lookup": 2, "append": 1},
        )
        self.assertEqual(
            calls["compose"],
            [("graph", "_prepare_initial_aggregate_state", "", ("ordered_results",), ())],
        )
        self.assertEqual(
            calls["lookup"],
            [
                ("owner", "compose_lookup_list_numeric_answer", "", ("row",), ()),
                (
                    "owner",
                    "append_uncovered_lookup_numeric_items",
                    "",
                    ("row",),
                    (("require_primary_slot", "True"), ("require_numeric", "True")),
                ),
            ],
        )
        self.assertEqual(
            calls["append"],
            [
                (
                    "graph",
                    "_aggregate_calculation_subtasks",
                    "",
                    ("final_answer", "ordered_results"),
                    (),
                )
            ],
        )
        self.assertEqual(
            [
                (module, caller, receiver, args, keywords)
                for module, caller, receiver, args, keywords in calls["row"]
                if caller
                in {"compose_lookup_list_numeric_answer", "append_uncovered_lookup_numeric_items"}
            ],
            [
                ("owner", "compose_lookup_list_numeric_answer", "", ("row",), ()),
                ("owner", "append_uncovered_lookup_numeric_items", "", ("row",), ()),
            ],
        )
        owner_local = sum(
            module == "owner"
            for entries in calls.values()
            for module, _caller, _receiver, _args, _keywords in entries
        )
        graph_external = sum(map(len, calls.values())) - owner_local
        self.assertEqual((graph_external, owner_local), (22, 6))
        self.assertEqual(
            [
                (key, caller, args)
                for key, entries in calls.items()
                for module, caller, _receiver, args, _keywords in entries
                if module == "owner"
            ],
            [
                ("row", "answer_reuses_narrative_summary_text", ("row",)),
                ("row", "safe_partial_answer_for_numeric_gap", ("row",)),
                ("row", "compose_lookup_list_numeric_answer", ("row",)),
                ("row", "append_uncovered_lookup_numeric_items", ("row",)),
                ("lookup", "compose_lookup_list_numeric_answer", ("row",)),
                ("lookup", "append_uncovered_lookup_numeric_items", ("row",)),
            ],
        )

    def test_current_source_lookup_surface_callers_adopt_exact_args_order_and_exception_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = None
        nested = {"preserve": True}
        row = {"task_id": "lookup", "answer": "row answer", "nested": nested}
        ordered_results = [row]
        prepare_state = {
            "query": "",
            "subtask_results": [],
            "calc_subtasks": [],
        }

        def run_prepare(compose_owner, prepared_constructor, events):
            with (
                patch.object(agent, "_capture_current_subtask_result", return_value=row),
                patch.object(financial_graph_calculation, "upsert_subtask_result", return_value=[row]),
                patch.object(
                    financial_graph_calculation,
                    "dedupe_aggregate_subtask_results",
                    side_effect=lambda _rows: ordered_results,
                ),
                patch.object(
                    agent,
                    "_recover_lookup_results_from_sibling_table_evidence",
                    side_effect=lambda rows, _state: rows,
                ),
                patch.object(
                    financial_graph_calculation,
                    "promote_stronger_nested_aggregate_results",
                    side_effect=lambda rows: rows,
                ),
                patch.object(
                    agent,
                    "_align_lookup_result_units_from_peer_source_slots",
                    side_effect=lambda rows: rows,
                ),
                patch.object(
                    agent,
                    "_append_ratio_result_from_retrieved_context",
                    side_effect=lambda rows, _state: rows,
                ),
                patch.object(
                    agent,
                    "_append_ratio_result_from_task_outputs",
                    side_effect=lambda rows, _state: rows,
                ),
                patch.object(
                    agent,
                    "_sync_ratio_result_displays_in_ordered_results",
                    side_effect=lambda rows: events.append(("sync", rows)) or rows,
                ),
                patch.object(agent, "_aggregate_result_operation_family", return_value="lookup"),
                patch.object(
                    agent,
                    "_preferred_aggregate_fallback_answer",
                    side_effect=lambda rows, answer: events.append(("fallback", rows, answer)) or answer,
                ),
                patch.object(
                    agent,
                    "_rebuild_aggregate_projection",
                    return_value={"calculation_result": {"status": "ok"}},
                ),
                patch.object(
                    agent,
                    "_align_lookup_results_with_dependency_projection",
                    side_effect=lambda rows, _state, _projection: rows,
                ),
                patch.object(agent, "_supported_aggregate_subtask_answer", return_value=""),
                patch.object(agent, "_preferred_complete_numeric_answer", return_value=""),
                patch.object(
                    financial_graph_calculation,
                    "row_is_narrative_summary",
                    side_effect=lambda candidate: events.append(("narrative", candidate)) or False,
                ),
                patch.object(
                    financial_graph_calculation,
                    "compose_lookup_list_numeric_answer",
                    compose_owner,
                ),
                patch.object(
                    financial_graph_calculation,
                    "_PreparedAggregateState",
                    prepared_constructor,
                ),
            ):
                return agent._prepare_initial_aggregate_state(prepare_state)

        adopted_lookup_list = "lookup one 1, lookup two 2"
        prepare_events = []
        compose_owner = Mock(
            side_effect=lambda rows: prepare_events.append(("compose", rows)) or adopted_lookup_list
        )
        prepared_constructor = Mock(wraps=financial_graph_calculation._PreparedAggregateState)
        prepared = run_prepare(compose_owner, prepared_constructor, prepare_events)
        compose_owner.assert_called_once_with(ordered_results)
        self.assertIs(compose_owner.call_args.args[0], ordered_results)
        self.assertEqual(
            [event[0] for event in prepare_events],
            ["sync", "fallback", "narrative", "compose"],
        )
        self.assertIs(prepared.ordered_results, ordered_results)
        self.assertIs(prepared.fallback_answer, adopted_lookup_list)
        self.assertIs(prepared.ordered_results[0], row)
        self.assertIs(row["nested"], nested)
        prepared_constructor.assert_called_once_with(
            ordered_results=ordered_results,
            fallback_answer=adopted_lookup_list,
            supported_aggregate_answer="",
            complete_numeric_answer="",
            has_narrative_summary=False,
            has_growth_rate_result=False,
            numeric_answer_locked=False,
        )

        compose_owner = Mock(side_effect=RuntimeError("compose failed"))
        prepared_constructor = Mock(wraps=financial_graph_calculation._PreparedAggregateState)
        with self.assertRaisesRegex(RuntimeError, "compose failed"):
            run_prepare(compose_owner, prepared_constructor, [])
        compose_owner.assert_called_once_with(ordered_results)
        prepared_constructor.assert_not_called()

        aggregate_state = {
            "query": "",
            "seed_retrieved_docs": [],
            "retrieved_docs": [],
            "evidence_items": [],
            "tasks": [],
            "artifacts": [],
        }
        aggregate_state_snapshot = deepcopy(aggregate_state)
        base_answer = "base aggregate 100"
        prepared_state = financial_graph_calculation._PreparedAggregateState(
            ordered_results,
            base_answer,
            "",
            "",
            False,
            False,
            False,
        )
        adopted_answer = "missing lookup 40. base aggregate 100"
        aggregate_events = []
        original_replace = agent._replace_mutable_aggregate_answer

        def record_replace(*args, **kwargs):
            if kwargs.get("candidate_answer") is adopted_answer:
                aggregate_events.append(("adopt", args, kwargs))
            return original_replace(*args, **kwargs)

        with (
            patch.object(
                agent,
                "_prepare_initial_aggregate_state",
                return_value=prepared_state,
            ) as prepare_owner,
            patch.object(
                agent,
                "_compact_ratio_answer_from_projection",
                side_effect=lambda *_args, **_kwargs: aggregate_events.append(("compact",)) or "",
            ),
            patch.object(
                financial_graph_calculation,
                "append_uncovered_lookup_numeric_items",
                side_effect=lambda answer, rows: aggregate_events.append(("append", answer, rows))
                or adopted_answer,
            ) as append_owner,
            patch.object(
                agent,
                "_replace_mutable_aggregate_answer",
                side_effect=record_replace,
            ),
        ):
            aggregate_update = agent._aggregate_calculation_subtasks(aggregate_state)
        prepare_owner.assert_called_once_with(aggregate_state)
        append_owner.assert_called_once()
        self.assertEqual(append_owner.call_args.args[0], base_answer)
        self.assertIs(append_owner.call_args.args[1], ordered_results)
        self.assertEqual([event[0] for event in aggregate_events], ["compact", "append", "adopt"])
        adopt_call = aggregate_events[-1]
        self.assertIs(adopt_call[2]["candidate_answer"], adopted_answer)
        self.assertFalse(adopt_call[2]["sync_rendered_for_aggregate"])
        self.assertTrue(adopt_call[2]["refresh_operand_evidence"])
        self.assertEqual(aggregate_update["answer"], adopted_answer)
        self.assertEqual(aggregate_state, aggregate_state_snapshot)
        self.assertIs(ordered_results[0], row)
        self.assertIs(row["nested"], nested)

        downstream_filter = Mock()
        aggregate_events = []
        with (
            patch.object(agent, "_prepare_initial_aggregate_state", return_value=prepared_state),
            patch.object(
                agent,
                "_compact_ratio_answer_from_projection",
                side_effect=lambda *_args, **_kwargs: aggregate_events.append(("compact",)) or "",
            ),
            patch.object(
                financial_graph_calculation,
                "append_uncovered_lookup_numeric_items",
                side_effect=lambda answer, rows: aggregate_events.append(("append", answer, rows))
                or (_ for _ in ()).throw(RuntimeError("append failed")),
            ) as append_owner,
            patch.object(
                financial_graph_calculation,
                "filter_final_aggregate_evidence_and_projection",
                downstream_filter,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "append failed"):
                agent._aggregate_calculation_subtasks(aggregate_state)
        append_owner.assert_called_once()
        self.assertEqual(append_owner.call_args.args[0], base_answer)
        self.assertIs(append_owner.call_args.args[1], ordered_results)
        self.assertEqual([event[0] for event in aggregate_events], ["compact", "append"])
        downstream_filter.assert_not_called()
        self.assertEqual(aggregate_state, aggregate_state_snapshot)

    def test_aggregate_dependency_candidates_preserve_order_copy_and_access_contract(self) -> None:
        agent = financial_graph_calculation.FinancialAgentCalculationMixin()
        nested = {"preserve": True}

        class RowFallbackBomb(dict):
            def get(self, key, default=None):
                if key == "answer_slots":
                    raise RuntimeError("row answer slots accessed")
                return super().get(key, default)

        row_operand = {"operand_id": "row", "nested": nested}
        result_operand = {"operand_id": "result", "nested": nested}
        group_first = {"operand_id": "group_first", "nested": nested}
        group_second = {"operand_id": "group_second", "nested": nested}
        role_operand = {"operand_id": "role", "nested": nested}
        row = RowFallbackBomb(
            calculation_operands=[None, row_operand, "skip"],
            calculation_result={
                "calculation_operands": [result_operand, object()],
                "answer_slots": {
                    "components_by_group": {
                        "first": [group_first, None],
                        "second": [group_second],
                    },
                    "components_by_role": {
                        "numerator_1": [role_operand, "skip"],
                    },
                },
            },
            answer_slots={"components_by_group": RowFallbackBomb()},
        )
        originals = [
            row_operand,
            result_operand,
            group_first,
            group_second,
            role_operand,
        ]
        snapshots = deepcopy(originals)

        candidates = financial_aggregate_projection._aggregate_result_candidate_operands(row)

        self.assertEqual(
            [candidate["operand_id"] for candidate in candidates],
            ["row", "result", "group_first", "group_second", "role"],
        )
        for candidate, original in zip(candidates, originals):
            self.assertEqual(candidate, original)
            self.assertIsNot(candidate, original)
            self.assertIs(candidate["nested"], nested)
        self.assertEqual(originals, snapshots)

        duplicate_candidates = financial_aggregate_projection._aggregate_result_candidate_operands(
            {
                "calculation_operands": [row_operand, row_operand],
                "calculation_result": {
                    "calculation_operands": [row_operand],
                },
            }
        )
        self.assertEqual(duplicate_candidates, [row_operand, row_operand, row_operand])
        self.assertTrue(all(candidate is not row_operand for candidate in duplicate_candidates))
        self.assertEqual(len({id(candidate) for candidate in duplicate_candidates}), 3)
        self.assertTrue(all(candidate["nested"] is nested for candidate in duplicate_candidates))

        fallback_operand = {"operand_id": "fallback", "nested": nested}
        fallback_candidates = financial_aggregate_projection._aggregate_result_candidate_operands(
            {
                "calculation_result": {"answer_slots": {}},
                "answer_slots": {
                    "components_by_role": {
                        "denominator_1": [fallback_operand],
                    }
                },
            }
        )
        self.assertEqual(fallback_candidates, [fallback_operand])
        self.assertIsNot(fallback_candidates[0], fallback_operand)
        self.assertIs(fallback_candidates[0]["nested"], nested)

        class IterationBomb:
            def __iter__(self):
                raise RuntimeError("row operands iterated")

        class LaterIterationBomb:
            def __iter__(self):
                raise AssertionError("result operands iterated")

        with self.assertRaisesRegex(RuntimeError, "row operands iterated"):
            financial_aggregate_projection._aggregate_result_candidate_operands(
                {
                    "calculation_operands": IterationBomb(),
                    "calculation_result": {
                        "calculation_operands": LaterIterationBomb(),
                        "answer_slots": {},
                    },
                }
            )

    def test_aggregate_dependency_coherence_preserves_state_order_and_exception_contract(self) -> None:
        agent = financial_graph_calculation.FinancialAgentCalculationMixin()

        class SourceMapCopyBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                raise RuntimeError("source map copied")

            def __getitem__(self, key):
                raise KeyError(key)

        candidate_owner = Mock(side_effect=RuntimeError("candidates accessed"))
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="lookup",
            ),
            patch.object(
                financial_aggregate_projection,
                "_aggregate_result_candidate_operands",
                candidate_owner,
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.aggregate_result_dependency_coherence_ranks(
                    {"operation_family": "lookup"},
                    SourceMapCopyBomb(),
                ),
                (1, 1),
            )
        candidate_owner.assert_not_called()

        nested = {"preserve": True}
        operand = {
            "operand_id": "operand",
            "source_anchor": "anchor",
            "nested": nested,
        }
        first_slot = {
            "normalized_value": 1.0,
            "source_anchor": "anchor",
            "consolidation_scope": "consolidated",
            "nested": nested,
        }
        scope_slot = {
            "status": "missing",
            "consolidation_scope": "consolidated",
        }
        source_slots = {
            "task_first": first_slot,
            "task_scope": scope_slot,
        }
        scope_calls = []

        def known_scope(value, *unused):
            scope_calls.append(value)
            return str(value or "").strip()

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="ratio",
            ),
            patch.object(
                financial_aggregate_projection,
                "_aggregate_result_candidate_operands",
                return_value=[operand],
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                return_value=["task_first", "task_scope"],
            ) as task_ids_owner,
            patch.object(
                financial_aggregate_projection,
                "dependency_projection_slot_differs_from_operand",
                return_value=False,
            ) as projection_owner,
            patch.object(
                financial_aggregate_projection,
                "structured_unit_realigned_operand_matches_source_slot",
            ) as structured_owner,
            patch.object(
                financial_aggregate_projection,
                "known_consolidation_scope_value",
                side_effect=known_scope,
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.aggregate_result_dependency_coherence_ranks(
                    {"operation_family": "ratio"},
                    source_slots,
                ),
                (2, 2),
            )
        self.assertIs(task_ids_owner.call_args.args[0], operand)
        prepared_source_slots = task_ids_owner.call_args.args[1]
        self.assertEqual(prepared_source_slots, source_slots)
        self.assertIsNot(prepared_source_slots, source_slots)
        self.assertIs(prepared_source_slots["task_first"], first_slot)
        projected_slot, projected_operand = projection_owner.call_args.args
        self.assertEqual(projected_slot, first_slot)
        self.assertIsNot(projected_slot, first_slot)
        self.assertIs(projected_slot["nested"], nested)
        self.assertIs(projected_operand, operand)
        structured_owner.assert_not_called()
        self.assertEqual(scope_calls, ["consolidated", None])

        first_blank_scope_slot = {
            "normalized_value": 1.0,
            "source_anchor": "anchor",
        }
        later_scoped_slot = {
            "normalized_value": 2.0,
            "source_anchor": "anchor",
            "consolidation_scope": "consolidated",
        }
        first_present_scope_calls = []

        def first_present_scope(value, *unused):
            first_present_scope_calls.append(value)
            return str(value or "").strip()

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="ratio",
            ),
            patch.object(
                financial_aggregate_projection,
                "_aggregate_result_candidate_operands",
                return_value=[operand],
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                return_value=["task_first", "task_later"],
            ),
            patch.object(
                financial_aggregate_projection,
                "dependency_projection_slot_differs_from_operand",
                return_value=False,
            ) as first_projection_owner,
            patch.object(
                financial_aggregate_projection,
                "known_consolidation_scope_value",
                side_effect=first_present_scope,
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.aggregate_result_dependency_coherence_ranks(
                    {"operation_family": "ratio"},
                    {
                        "task_first": first_blank_scope_slot,
                        "task_later": later_scoped_slot,
                    },
                ),
                (2, 1),
            )
        self.assertEqual(first_present_scope_calls, [None])
        self.assertEqual(len(first_projection_owner.call_args_list), 1)
        self.assertEqual(
            first_projection_owner.call_args.args[0],
            first_blank_scope_slot,
        )

        realigned_operand = {
            "operand_id": "realigned",
            "source_anchor": "operand anchor",
            "unit_realigned_from_structured_provenance": True,
            "nested": nested,
        }
        mismatched_slot = {
            "normalized_value": 2.0,
            "source_anchor": "source anchor",
            "nested": nested,
        }
        events = []

        def projection_mismatch(source_slot, candidate):
            events.append("projection")
            return False

        def structured_match(source_slot, candidate, **kwargs):
            events.append("structured")
            self.assertIsNot(source_slot, mismatched_slot)
            self.assertIs(candidate, realigned_operand)
            structured_candidates = kwargs["structured_realigned_operands"]
            self.assertEqual(structured_candidates, [realigned_operand])
            self.assertIsNot(structured_candidates[0], realigned_operand)
            self.assertIs(structured_candidates[0]["nested"], nested)
            return True

        def scope_after_match(value, *unused):
            events.append("scope")
            return str(value or "").strip()

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="ratio",
            ),
            patch.object(
                financial_aggregate_projection,
                "_aggregate_result_candidate_operands",
                return_value=[realigned_operand],
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                return_value=["task_bad"],
            ),
            patch.object(
                financial_aggregate_projection,
                "dependency_projection_slot_differs_from_operand",
                side_effect=projection_mismatch,
            ),
            patch.object(
                financial_aggregate_projection,
                "structured_unit_realigned_operand_matches_source_slot",
                side_effect=structured_match,
            ),
            patch.object(
                financial_aggregate_projection,
                "known_consolidation_scope_value",
                side_effect=scope_after_match,
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.aggregate_result_dependency_coherence_ranks(
                    {"operation_family": "ratio"},
                    {"task_bad": mismatched_slot},
                ),
                (2, 1),
            )
        self.assertEqual(events, ["projection", "structured", "scope"])

        prior_scope_operand = {"operand_id": "scope"}
        bad_operand = {
            "operand_id": "bad",
            "source_anchor": "operand anchor",
        }
        prior_scope_slot = {
            "status": "missing",
            "consolidation_scope": "consolidated",
        }
        bad_slot = {
            "normalized_value": 3.0,
            "source_anchor": "source anchor",
            "consolidation_scope": "ignored current scope",
        }

        def ids_for_operand(candidate, _source_slots):
            return ["task_scope"] if candidate is prior_scope_operand else ["task_bad"]

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="ratio",
            ),
            patch.object(
                financial_aggregate_projection,
                "_aggregate_result_candidate_operands",
                return_value=[prior_scope_operand, bad_operand],
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                side_effect=ids_for_operand,
            ),
            patch.object(
                financial_aggregate_projection,
                "dependency_projection_slot_differs_from_operand",
                return_value=True,
            ),
            patch.object(
                financial_aggregate_projection,
                "structured_unit_realigned_operand_matches_source_slot",
                return_value=False,
            ),
            patch.object(
                financial_aggregate_projection,
                "known_consolidation_scope_value",
                side_effect=lambda value, *unused: str(value or "").strip(),
            ) as prior_scope_owner,
        ):
            self.assertEqual(
                financial_aggregate_projection.aggregate_result_dependency_coherence_ranks(
                    {"operation_family": "ratio"},
                    {"task_scope": prior_scope_slot, "task_bad": bad_slot},
                ),
                (0, 2),
            )
        self.assertEqual(
            [call.args[0] for call in prior_scope_owner.call_args_list],
            ["consolidated", None],
        )

        scoped_operand = {
            "operand_id": "scoped",
            "source_anchor": "anchor",
            "consolidation_scope": "separate",
        }
        scoped_slot = {
            "normalized_value": 4.0,
            "source_anchor": "anchor",
            "consolidation_scope": "consolidated",
        }
        scope_mismatch_events = []

        def scope_mismatch_projection(*unused):
            scope_mismatch_events.append("projection")
            return False

        def scope_mismatch_value(value, *unused):
            scope_mismatch_events.append(str(value or ""))
            return str(value or "").strip()

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="ratio",
            ),
            patch.object(
                financial_aggregate_projection,
                "_aggregate_result_candidate_operands",
                return_value=[scoped_operand],
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                return_value=["task_scope"],
            ),
            patch.object(
                financial_aggregate_projection,
                "dependency_projection_slot_differs_from_operand",
                side_effect=scope_mismatch_projection,
            ),
            patch.object(
                financial_aggregate_projection,
                "known_consolidation_scope_value",
                side_effect=scope_mismatch_value,
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.aggregate_result_dependency_coherence_ranks(
                    {"operation_family": "ratio"},
                    {"task_scope": scoped_slot},
                ),
                (2, 0),
            )
        self.assertEqual(
            scope_mismatch_events,
            ["projection", "consolidated", "separate"],
        )

        material_owner = Mock(side_effect=AssertionError("material reached"))
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="sum",
            ),
            patch.object(
                financial_aggregate_projection,
                "_aggregate_result_candidate_operands",
                return_value=[operand],
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                side_effect=RuntimeError("task ids failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "answer_slot_has_material",
                material_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "task ids failed"):
                financial_aggregate_projection.aggregate_result_dependency_coherence_ranks(
                    {"operation_family": "sum"},
                    source_slots,
                )
        material_owner.assert_not_called()

        class OperandsIterationBomb:
            def __iter__(self):
                raise RuntimeError("operands iterated")

        class ResultCopyBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                raise RuntimeError("result copied")

            def __getitem__(self, key):
                raise KeyError(key)

        for failure, operands, calculation_result in (
            ("operands iterated", OperandsIterationBomb(), {}),
            ("result copied", [operand], ResultCopyBomb()),
        ):
            with self.subTest(wrapper_preparation=failure), patch.object(
                financial_aggregate_projection,
                "aggregate_source_slot_by_task_id",
            ) as source_map_owner:
                with self.assertRaisesRegex(RuntimeError, failure):
                    financial_aggregate_projection.aggregate_dependency_slot_coherence_rank_for_operands(
                        operation_family="sum",
                        operands=operands,
                        ordered_results=[],
                        calculation_result=calculation_result,
                    )
            source_map_owner.assert_not_called()

    def test_aggregate_dependency_rank_callers_preserve_all_args_adoption_and_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)

        preferred_row = {
            "task_id": "task_sum",
            "operation_family": "sum",
            "status": "ok",
            "answer": "sum answer 10",
        }
        preferred_results = [preferred_row]
        source_slots = {"task_lookup": {"normalized_value": 1.0}}
        with (
            patch.object(financial_graph_calculation, "narrative_context_terms", return_value=[]),
            patch.object(
                agent,
                "_aggregate_dependency_source_slot_by_task_id",
                return_value=source_slots,
            ),
            patch.object(
                agent,
                "_aggregate_result_operation_family",
                return_value="sum",
            ),
            patch.object(
                financial_graph_calculation,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_result_dependency_coherence_ranks",
                return_value=(0, 1),
            ) as preferred_rank_owner,
        ):
            self.assertEqual(
                agent._preferred_complete_numeric_answer(preferred_results),
                "",
            )
        self.assertIs(preferred_rank_owner.call_args.args[0], preferred_row)
        self.assertIs(preferred_rank_owner.call_args.args[1], source_slots)

        class LaterSourceIdsBomb:
            def __iter__(self):
                raise AssertionError("source row ids iterated")

        ranked_row = {
            "status": "ok",
            "answer": "answer",
            "calculation_result": {
                "source_row_ids": LaterSourceIdsBomb(),
            },
        }
        rank_source_slots = {"task_a": {"normalized_value": 1.0}}
        with (
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_operand_sign_consistency_rank",
                return_value=3,
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_dependency_coherence_ranks",
                side_effect=RuntimeError("rank coherence failed"),
            ) as result_rank_owner,
        ):
            with self.assertRaisesRegex(RuntimeError, "rank coherence failed"):
                financial_aggregate_projection._aggregate_result_rank(
                    ranked_row,
                    rank_source_slots,
                )
        self.assertIs(result_rank_owner.call_args.args[0], ranked_row)
        self.assertIs(result_rank_owner.call_args.args[1], rank_source_slots)

        material_ranked_row = {
            "status": "ok",
            "answer": "answer",
            "calculation_result": {"source_row_ids": ["row_a", "row_b"]},
        }
        with (
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_operand_sign_consistency_rank",
                return_value=3,
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_dependency_coherence_ranks",
                return_value=(7, 8),
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection._aggregate_result_rank(
                    material_ranked_row,
                    rank_source_slots,
                ),
                (4, 1, 1, 3, 7, 8, 2),
            )

        nested = {"preserve": True}
        current_row = {
            "task_id": "task_growth",
            "operation_family": "growth_rate",
            "status": "partial",
            "nested": nested,
        }
        nested_row = {
            "task_id": "task_growth",
            "operation_family": "growth_rate",
            "status": "ok",
            "answer": "nested answer 10%",
            "nested": nested,
        }
        aggregate_row = {
            "task_id": "task_aggregate",
            "operation_family": "aggregate_subtasks",
            "calculation_result": {"subtask_results": [nested_row]},
        }
        promotion_results = [current_row, aggregate_row]
        promotion_source_slots = {"task_growth": {"normalized_value": 1.0}}
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_slot_by_task_id",
                return_value=promotion_source_slots,
            ),
            patch.object(
                financial_aggregate_projection,
                "nested_subtask_rows",
                return_value=[dict(nested_row)],
            ),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(
                financial_aggregate_projection,
                "nested_aggregate_result_rank",
                side_effect=[2, 1],
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_dependency_coherence_ranks",
                side_effect=[(2, 1), (1, 1)],
            ) as promotion_rank_owner,
        ):
            promoted = financial_aggregate_projection.promote_stronger_nested_aggregate_results(
                promotion_results
            )
        self.assertTrue(promoted[0]["promoted_from_nested_aggregate"])
        self.assertEqual(len(promotion_rank_owner.call_args_list), 2)
        promoted_candidate = promotion_rank_owner.call_args_list[0].args[0]
        promoted_current = promotion_rank_owner.call_args_list[1].args[0]
        self.assertEqual(promoted_candidate, nested_row)
        self.assertEqual(promoted_current, current_row)
        self.assertIsNot(promoted_candidate, nested_row)
        self.assertIsNot(promoted_current, current_row)
        self.assertIs(promoted_candidate["nested"], nested)
        self.assertIs(promoted_current["nested"], nested)
        self.assertIs(
            promotion_rank_owner.call_args_list[0].args[1],
            promotion_source_slots,
        )
        self.assertIs(
            promotion_rank_owner.call_args_list[1].args[1],
            promotion_source_slots,
        )

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_slot_by_task_id",
                return_value=promotion_source_slots,
            ),
            patch.object(
                financial_aggregate_projection,
                "nested_subtask_rows",
                return_value=[dict(nested_row)],
            ),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(
                financial_aggregate_projection,
                "nested_aggregate_result_rank",
                side_effect=[2, 1],
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_dependency_coherence_ranks",
                side_effect=RuntimeError("promotion coherence failed"),
            ) as stopped_promotion_rank,
        ):
            with self.assertRaisesRegex(RuntimeError, "promotion coherence failed"):
                financial_aggregate_projection.promote_stronger_nested_aggregate_results(promotion_results)
        self.assertEqual(len(stopped_promotion_rank.call_args_list), 1)

    def test_aggregate_dependency_wrapper_callers_preserve_all_args_adoption_and_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"preserve": True}

        operand = {"operand_id": "operand", "nested": nested}
        subtask_row = {"task_id": "task_a", "nested": nested}
        ratio_result = {
            "status": "ok",
            "answer_slots": {
                "operation_family": "ratio",
                "metric_label": "target ratio",
            },
            "subtask_results": [subtask_row],
            "nested": nested,
        }
        ratio_projection = {
            "calculation_operands": [operand],
            "calculation_plan": {"operation": "ratio"},
            "calculation_result": ratio_result,
        }
        with (
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_components_are_complete",
                return_value=True,
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_dependency_slot_coherence_rank_for_operands",
                return_value=1,
            ) as compact_wrapper_owner,
            patch.object(
                agent,
                "_compact_ratio_answer",
                return_value=" target ratio 10% ",
            ),
        ):
            self.assertEqual(
                agent._compact_ratio_answer_from_projection({}, ratio_projection),
                "target ratio 10%",
            )
        compact_kwargs = compact_wrapper_owner.call_args.kwargs
        self.assertEqual(compact_kwargs["operation_family"], "ratio")
        self.assertEqual(compact_kwargs["operands"], [operand])
        self.assertIsNot(compact_kwargs["operands"], ratio_projection["calculation_operands"])
        self.assertIs(compact_kwargs["operands"][0], operand)
        self.assertEqual(compact_kwargs["calculation_result"], ratio_result)
        self.assertIsNot(compact_kwargs["calculation_result"], ratio_result)
        self.assertIs(compact_kwargs["calculation_result"]["nested"], nested)
        self.assertEqual(compact_kwargs["ordered_results"], [subtask_row])
        self.assertIsNot(compact_kwargs["ordered_results"][0], subtask_row)
        self.assertIs(compact_kwargs["ordered_results"][0]["nested"], nested)

        compact_answer_owner = Mock(return_value="unused")
        with (
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_components_are_complete",
                return_value=True,
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_dependency_slot_coherence_rank_for_operands",
                side_effect=RuntimeError("compact wrapper failed"),
            ),
            patch.object(agent, "_compact_ratio_answer", compact_answer_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "compact wrapper failed"):
                agent._compact_ratio_answer_from_projection({}, ratio_projection)
        compact_answer_owner.assert_not_called()

        aggregate_state = _AggregateSynthesisState(
            [subtask_row],
            ratio_projection,
            "old answer 5%",
            ["ev_old"],
        )
        repaired_operands = [{"operand_id": "repaired", "nested": nested}]
        repaired_result = {
            "status": "ok",
            "answer_slots": {"operation_family": "ratio"},
            "nested": nested,
        }
        stale_repair = SimpleNamespace(
            repair_applied=True,
            calculation_operands=repaired_operands,
            calculation_plan={"operation": "ratio"},
            calculation_result=repaired_result,
            selected_evidence_ids=("ev_new",),
        )
        repaired_projection = {
            "calculation_operands": repaired_operands,
            "calculation_plan": stale_repair.calculation_plan,
            "calculation_result": repaired_result,
        }
        with (
            patch.object(
                agent,
                "_repair_stale_aggregate_projection_result",
                return_value=(repaired_projection, stale_repair),
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_dependency_slot_coherence_rank_for_operands",
                return_value=0,
            ) as stale_wrapper_owner,
            patch.object(
                financial_graph_calculation,
                "_select_aggregate_stale_repair_provenance",
            ) as stale_provenance_owner,
        ):
            self.assertIs(
                agent._apply_stale_projection_repair_to_aggregate_state(
                    state={"query": "target ratio"},
                    aggregate_state=aggregate_state,
                    evidence_items=[],
                ),
                aggregate_state,
            )
        self.assertEqual(
            stale_wrapper_owner.call_args.kwargs,
            {
                "operation_family": "ratio",
                "operands": repaired_operands,
                "calculation_result": repaired_result,
                "ordered_results": aggregate_state.ordered_results,
            },
        )
        stale_provenance_owner.assert_not_called()

        stale_provenance_owner = Mock()
        with (
            patch.object(
                agent,
                "_repair_stale_aggregate_projection_result",
                return_value=(repaired_projection, stale_repair),
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_dependency_slot_coherence_rank_for_operands",
                side_effect=RuntimeError("stale wrapper failed"),
            ),
            patch.object(
                financial_graph_calculation,
                "_select_aggregate_stale_repair_provenance",
                stale_provenance_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "stale wrapper failed"):
                agent._apply_stale_projection_repair_to_aggregate_state(
                    state={"query": "target ratio"},
                    aggregate_state=aggregate_state,
                    evidence_items=[],
                )
        stale_provenance_owner.assert_not_called()

        runtime_operand = {"operand_id": "runtime", "nested": nested}
        runtime_result = {
            "status": "ok",
            "answer_slots": {
                "operation_family": "ratio",
                "primary_value": {"rendered_value": "10%"},
            },
            "nested": nested,
        }
        runtime_trace = {
            "calculation_operands": [runtime_operand],
            "calculation_plan": {"operation": "ratio"},
            "calculation_result": runtime_result,
        }
        runtime_state = {"query": "target ratio", "subtask_results": [subtask_row]}
        runtime_projection = {"calculation_result": {"formatted_result": "old 5%"}}
        with (
            patch.object(
                financial_graph_calculation,
                "_resolve_runtime_calculation_trace",
                return_value=runtime_trace,
            ),
            patch.object(
                agent,
                "_aggregate_result_operation_family",
                return_value="ratio",
            ),
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_components_collapse_to_same_slot",
                return_value=True,
            ),
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_components_are_complete",
                return_value=True,
            ),
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "ratio_query_requests_absolute_magnitude",
                return_value=False,
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_dependency_slot_coherence_rank_for_operands",
                return_value=1,
            ) as runtime_wrapper_owner,
            patch.object(
                agent,
                "_compact_ratio_answer_from_projection",
                return_value="runtime ratio 10%",
            ),
            patch.object(
                agent,
                "_answer_covers_numeric_projection",
                return_value=False,
            ),
        ):
            projected, runtime_answer = agent._apply_runtime_ratio_projection_for_collapsed_rows(
                runtime_state,
                runtime_projection,
                [subtask_row],
                "old 5%",
            )
        self.assertEqual(runtime_answer, "runtime ratio 10%")
        self.assertEqual(projected["calculation_result"]["formatted_result"], runtime_answer)
        runtime_kwargs = runtime_wrapper_owner.call_args.kwargs
        self.assertEqual(runtime_kwargs["operation_family"], "ratio")
        self.assertEqual(runtime_kwargs["operands"], [runtime_operand])
        self.assertIsNot(runtime_kwargs["operands"], runtime_trace["calculation_operands"])
        self.assertIs(runtime_kwargs["operands"][0], runtime_operand)
        self.assertEqual(runtime_kwargs["calculation_result"], runtime_result)
        self.assertIsNot(runtime_kwargs["calculation_result"], runtime_result)
        self.assertIs(runtime_kwargs["calculation_result"]["nested"], nested)
        self.assertEqual(runtime_kwargs["ordered_results"], [subtask_row])

        runtime_compact_owner = Mock(return_value="unused")
        with (
            patch.object(
                financial_graph_calculation,
                "_resolve_runtime_calculation_trace",
                return_value=runtime_trace,
            ),
            patch.object(
                agent,
                "_aggregate_result_operation_family",
                return_value="ratio",
            ),
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_components_collapse_to_same_slot",
                return_value=True,
            ),
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_components_are_complete",
                return_value=True,
            ),
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "ratio_query_requests_absolute_magnitude",
                return_value=False,
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_dependency_slot_coherence_rank_for_operands",
                side_effect=RuntimeError("runtime wrapper failed"),
            ),
            patch.object(
                agent,
                "_compact_ratio_answer_from_projection",
                runtime_compact_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "runtime wrapper failed"):
                agent._apply_runtime_ratio_projection_for_collapsed_rows(
                    runtime_state,
                    {},
                    [subtask_row],
                    "old 5%",
                )
        runtime_compact_owner.assert_not_called()

        late_state = {"subtask_results": [subtask_row]}
        with (
            patch.object(
                financial_graph_calculation,
                "_resolve_runtime_calculation_trace",
                return_value=runtime_trace,
            ),
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_components_are_complete",
                return_value=True,
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_dependency_slot_coherence_rank_for_operands",
                return_value=0,
            ) as late_wrapper_owner,
            patch.object(agent, "_compact_ratio_answer") as late_compact_owner,
        ):
            self.assertEqual(
                agent._late_runtime_numeric_answer(late_state, "old 5%"),
                "",
            )
        late_kwargs = late_wrapper_owner.call_args.kwargs
        self.assertEqual(late_kwargs["operation_family"], "ratio")
        self.assertEqual(late_kwargs["operands"], [runtime_operand])
        self.assertIs(late_kwargs["operands"][0], runtime_operand)
        self.assertEqual(late_kwargs["calculation_result"], runtime_result)
        self.assertIsNot(late_kwargs["calculation_result"], runtime_result)
        self.assertEqual(late_kwargs["ordered_results"], [subtask_row])
        self.assertIsNot(late_kwargs["ordered_results"][0], subtask_row)
        self.assertIs(late_kwargs["ordered_results"][0]["nested"], nested)
        late_compact_owner.assert_not_called()

        late_compact_owner = Mock()
        with (
            patch.object(
                financial_graph_calculation,
                "_resolve_runtime_calculation_trace",
                return_value=runtime_trace,
            ),
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_components_are_complete",
                return_value=True,
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_dependency_slot_coherence_rank_for_operands",
                side_effect=RuntimeError("late wrapper failed"),
            ),
            patch.object(agent, "_compact_ratio_answer", late_compact_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "late wrapper failed"):
                agent._late_runtime_numeric_answer(late_state, "old 5%")
        late_compact_owner.assert_not_called()

    def test_aggregate_source_slot_preparation_preserves_copy_order_and_overlay_contract(self) -> None:
        nested = {"preserve": True}

        class RowFallbackBomb(dict):
            def get(self, key, default=None):
                if key == "answer_slots":
                    raise RuntimeError("row answer slots accessed")
                return super().get(key, default)

        calculation_primary = {
            "normalized_value": 1.0,
            "nested": nested,
        }
        calculation_row = RowFallbackBomb(
            calculation_result={
                "answer_slots": {
                    "primary_value": calculation_primary,
                }
            },
            answer_slots={"primary_value": {"normalized_value": 99.0}},
        )
        selected = financial_aggregate_projection.aggregate_row_primary_answer_slot(
            calculation_row
        )
        self.assertEqual(selected, calculation_primary)
        self.assertIsNot(selected, calculation_primary)
        self.assertIs(selected["nested"], nested)

        row_primary = {"normalized_value": 2.0, "nested": nested}
        fallback_row = {
            "calculation_result": {"answer_slots": {}},
            "answer_slots": {"primary_value": row_primary},
        }
        fallback_selected = financial_aggregate_projection.aggregate_row_primary_answer_slot(
            fallback_row
        )
        self.assertEqual(fallback_selected, row_primary)
        self.assertIsNot(fallback_selected, row_primary)
        self.assertIs(fallback_selected["nested"], nested)

        self.assertEqual(
            financial_aggregate_projection.aggregate_row_primary_answer_slot(
                {
                    "calculation_result": {"answer_slots": {"secondary": {"value": 1}}},
                    "answer_slots": {"primary_value": {"normalized_value": 3.0}},
                }
            ),
            {},
        )

        first_slot = {"normalized_value": 10.0, "nested": nested}
        second_slot = {
            "normalized_value": 20.0,
            "consolidation_scope": "slot_scope",
            "metric_label": "slot metric",
            "nested": nested,
        }
        replacement_slot = {"normalized_value": 30.0, "nested": nested}
        first_row = {
            "task_id": " task_a ",
            "consolidation_scope": " row_scope_a ",
            "metric_label": " Metric A ",
            "calculation_result": {"answer_slots": {"primary_value": first_slot}},
        }
        second_row = {
            "task_id": "task_b",
            "consolidation_scope": "row_scope_b",
            "metric_label": "row metric b",
            "answer_slots": {"primary_value": second_slot},
        }
        replacement_row = {
            "task_id": "task_a",
            "consolidation_scope": "row_scope_last",
            "metric_label": "Metric Last",
            "answer_slots": {"primary_value": replacement_slot},
        }
        snapshots = deepcopy([first_row, second_row, replacement_row])
        scope_calls = []

        def known_scope(*values):
            scope_calls.append(values)
            return next((str(value).strip() for value in values if str(value or "").strip()), "")

        with patch.object(
            financial_aggregate_projection,
            "known_consolidation_scope_value",
            side_effect=known_scope,
        ):
            source_slots = financial_aggregate_projection.aggregate_source_slot_by_task_id(
                [None, {"task_id": "   ", "answer_slots": RowFallbackBomb()}, first_row, second_row, replacement_row]
            )

        self.assertEqual(list(source_slots), ["task_a", "task_b"])
        self.assertEqual(source_slots["task_a"]["normalized_value"], 30.0)
        self.assertEqual(source_slots["task_a"]["consolidation_scope"], "row_scope_last")
        self.assertEqual(source_slots["task_a"]["metric_label"], "Metric Last")
        self.assertEqual(source_slots["task_b"]["consolidation_scope"], "slot_scope")
        self.assertEqual(source_slots["task_b"]["metric_label"], "slot metric")
        self.assertIs(source_slots["task_a"]["nested"], nested)
        self.assertIs(source_slots["task_b"]["nested"], nested)
        self.assertIsNot(source_slots["task_a"], replacement_slot)
        self.assertIsNot(source_slots["task_b"], second_slot)
        self.assertEqual([first_row, second_row, replacement_row], snapshots)
        self.assertEqual(
            scope_calls,
            [
                (None, " row_scope_a "),
                ("slot_scope", "row_scope_b"),
                (None, "row_scope_last"),
            ],
        )

    def test_aggregate_source_slot_preparation_preserves_lazy_access_and_exceptions(self) -> None:
        nested = {"preserve": True}

        class AccessRow(dict):
            def __init__(self, values, events, *, failure_key=None):
                super().__init__(values)
                self.events = events
                self.failure_key = failure_key

            def get(self, key, default=None):
                self.events.append(key)
                if key == self.failure_key:
                    raise RuntimeError(f"{key} accessed")
                return super().get(key, default)

        blank_events = []
        valid_events = []
        blank_row = AccessRow(
            {"task_id": "  ", "answer_slots": {"primary_value": {"normalized_value": 1.0}}},
            blank_events,
            failure_key="answer_slots",
        )
        valid_row = AccessRow(
            {"task_id": "task_a", "nested": nested, "consolidation_scope": "poison"},
            valid_events,
            failure_key="consolidation_scope",
        )
        prepared_rows = []

        def empty_primary(row):
            prepared_rows.append(row)
            return {}

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_row_primary_answer_slot",
                side_effect=empty_primary,
            ),
            patch.object(
                financial_aggregate_projection,
                "known_consolidation_scope_value",
                side_effect=RuntimeError("scope accessed"),
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.aggregate_source_slot_by_task_id(
                    [None, blank_row, valid_row]
                ),
                {},
            )
        self.assertEqual(blank_events, ["task_id"])
        self.assertEqual(valid_events, ["task_id"])
        self.assertEqual(prepared_rows, [valid_row])
        self.assertIsNot(prepared_rows[0], valid_row)
        self.assertIs(prepared_rows[0]["nested"], nested)

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_row_primary_answer_slot",
                side_effect=RuntimeError("primary failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "known_consolidation_scope_value",
            ) as scope_owner,
        ):
            with self.assertRaisesRegex(RuntimeError, "primary failed"):
                financial_aggregate_projection.aggregate_source_slot_by_task_id(
                    [{"task_id": "task_a"}]
                )
        scope_owner.assert_not_called()

        scope_events = []
        scope_row = AccessRow(
            {
                "task_id": "task_a",
                "consolidation_scope": "row_scope",
                "metric_label": "poison",
            },
            scope_events,
            failure_key="metric_label",
        )
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_row_primary_answer_slot",
                return_value={"normalized_value": 1.0},
            ),
            patch.object(
                financial_aggregate_projection,
                "known_consolidation_scope_value",
                side_effect=RuntimeError("scope failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "scope failed"):
                financial_aggregate_projection.aggregate_source_slot_by_task_id(
                    [scope_row]
                )
        self.assertEqual(scope_events, ["task_id", "consolidation_scope"])

        class CalculationResultBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                raise RuntimeError("calculation result copied")

            def __getitem__(self, key):
                raise KeyError(key)

        with self.assertRaisesRegex(RuntimeError, "calculation result copied"):
            financial_aggregate_projection.aggregate_row_primary_answer_slot(
                {"calculation_result": CalculationResultBomb()}
            )

    def test_aggregate_source_task_ids_preserve_explicit_inference_and_access_contract(self) -> None:
        class AccessOperand(dict):
            def __init__(self, values, events, *, failure_key=None):
                super().__init__(values)
                self.events = events
                self.failure_key = failure_key

            def get(self, key, default=None):
                self.events.append(key)
                if key == self.failure_key:
                    raise RuntimeError(f"{key} accessed")
                return super().get(key, default)

        class SourceSlotsBomb(dict):
            def __bool__(self):
                raise RuntimeError("source slots truth-tested")

            def items(self):
                raise RuntimeError("source slots iterated")

        explicit_events = []
        explicit_operand = AccessOperand(
            {
                "source_task_id": " task_a ",
                "source_row_id": "task_output:task_b",
                "source_row_ids": ["task_output:task_a", "task_output:task_b"],
            },
            explicit_events,
            failure_key="role",
        )
        self.assertEqual(
            financial_aggregate_projection.aggregate_source_task_ids_for_operand(
                explicit_operand,
                SourceSlotsBomb(task_unused={}),
            ),
            ["task_a", "task_b"],
        )
        self.assertEqual(
            explicit_events,
            ["source_task_id", "source_row_id", "source_row_ids"],
        )

        empty_events = []
        empty_operand = AccessOperand({}, empty_events, failure_key="role")
        self.assertEqual(
            financial_aggregate_projection.aggregate_source_task_ids_for_operand(
                empty_operand,
                {},
            ),
            [],
        )
        self.assertEqual(
            empty_events,
            ["source_task_id", "source_row_id", "source_row_ids"],
        )

        nested = {"preserve": True}
        low_slot = {"normalized_value": 1.0, "nested": nested}
        matching_slot = {"normalized_value": 2.0, "nested": nested}
        missing_slot = {"status": "missing", "normalized_value": 3.0}
        source_slots = {
            " task_low ": low_slot,
            " task_match ": matching_slot,
            "task_empty": {},
            "task_missing": missing_slot,
        }
        inference_events = []
        inference_operand = AccessOperand(
            {"role": " numerator_1 ", "matched_operand_role": "unused"},
            inference_events,
            failure_key="matched_operand_role",
        )
        material_calls = []
        score_calls = []

        def has_material(slot):
            material_calls.append(slot)
            return financial_answer_slots.answer_slot_has_material(slot)

        def match_score(slot, operand, role):
            score_calls.append((slot, operand, role))
            return 12 if slot.get("normalized_value") == 2.0 else 11

        with (
            patch.object(
                financial_aggregate_projection,
                "answer_slot_has_material",
                side_effect=has_material,
            ),
            patch.object(
                financial_aggregate_projection,
                "dependency_lookup_slot_match_score",
                side_effect=match_score,
            ),
        ):
            inferred = financial_aggregate_projection.aggregate_source_task_ids_for_operand(
                inference_operand,
                source_slots,
            )

        self.assertEqual(inferred, [" task_match "])
        self.assertEqual(
            inference_events,
            ["source_task_id", "source_row_id", "source_row_ids", "role"],
        )
        self.assertEqual(len(material_calls), 4)
        self.assertEqual(len(score_calls), 2)
        self.assertEqual([call[2] for call in score_calls], ["numerator_1", "numerator_1"])
        self.assertTrue(all(call[1] is inference_operand for call in score_calls))
        self.assertIsNot(material_calls[0], low_slot)
        self.assertIs(material_calls[0]["nested"], nested)
        self.assertIsNot(material_calls[1], matching_slot)
        self.assertIs(material_calls[1]["nested"], nested)

        fallback_events = []
        fallback_operand = AccessOperand(
            {"role": "", "matched_operand_role": " denominator_1 "},
            fallback_events,
        )
        fallback_scores = []

        def fallback_score(slot, operand, role):
            fallback_scores.append((slot, operand, role))
            return 12

        with (
            patch.object(
                financial_aggregate_projection,
                "answer_slot_has_material",
                return_value=True,
            ),
            patch.object(
                financial_aggregate_projection,
                "dependency_lookup_slot_match_score",
                side_effect=fallback_score,
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.aggregate_source_task_ids_for_operand(
                    fallback_operand,
                    {" task_fallback ": {"normalized_value": 1.0}},
                ),
                [" task_fallback "],
            )
        self.assertEqual(
            fallback_events,
            [
                "source_task_id",
                "source_row_id",
                "source_row_ids",
                "role",
                "matched_operand_role",
            ],
        )
        self.assertEqual([call[2] for call in fallback_scores], ["denominator_1"])

        with (
            patch.object(
                financial_aggregate_projection,
                "answer_slot_has_material",
                side_effect=RuntimeError("material failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "dependency_lookup_slot_match_score",
            ) as score_owner,
        ):
            with self.assertRaisesRegex(RuntimeError, "material failed"):
                financial_aggregate_projection.aggregate_source_task_ids_for_operand(
                    {"role": "numerator_1"},
                    {"task_a": {"normalized_value": 1.0}},
                )
        score_owner.assert_not_called()

    def test_aggregate_source_preparation_callers_preserve_exact_args_and_stop(self) -> None:
        agent = financial_graph_calculation.FinancialAgentCalculationMixin()

        lookup_row = {
            "kind": "lookup",
            "status": "ok",
            "metric_label": "metric",
        }
        ratio_row = {
            "kind": "ratio",
            "calculation_result": {
                "answer_slots": {
                    "components_by_group": {
                        "numerator": [
                            {
                                "label": "component",
                                "normalized_value": 10.0,
                                "normalized_unit": "COUNT",
                            }
                        ]
                    }
                }
            },
        }
        lookup_slot = {
            "label": "metric",
            "normalized_value": 10.0,
            "normalized_unit": "COUNT",
        }
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=lambda row: row.get("kind", ""),
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_row_primary_answer_slot",
                side_effect=[lookup_slot, lookup_slot],
            ) as primary_owner,
            patch.object(financial_aggregate_projection, "row_is_narrative_summary", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(financial_aggregate_projection, "_lookup_numeric_item_answer", return_value="metric 10"),
            patch.object(financial_aggregate_projection, "operand_text_match", return_value=False),
            patch.object(financial_aggregate_projection, "answer_covers_numeric_answer", return_value=False),
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", return_value=[]),
        ):
            appended = financial_aggregate_projection.append_uncovered_lookup_numeric_items(
                "aggregate answer 20",
                [lookup_row, ratio_row],
            )
        self.assertIn("metric 10", appended)
        self.assertEqual(len(primary_owner.call_args_list), 2)
        self.assertIs(primary_owner.call_args_list[0].args[0], lookup_row)
        self.assertIs(primary_owner.call_args_list[1].args[0], lookup_row)

        lookup_answer_owner = Mock(return_value="metric 10")
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=lambda row: row.get("kind", ""),
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_row_primary_answer_slot",
                side_effect=RuntimeError("primary failed"),
            ),
            patch.object(financial_aggregate_projection, "row_is_narrative_summary", return_value=False),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ),
            patch.object(financial_aggregate_projection, "_lookup_numeric_item_answer", lookup_answer_owner),
        ):
            with self.assertRaisesRegex(RuntimeError, "primary failed"):
                financial_aggregate_projection.append_uncovered_lookup_numeric_items(
                    "aggregate answer 20",
                    [lookup_row, ratio_row],
                )
        lookup_answer_owner.assert_not_called()

        ordered_results = [{"task_id": "task_a", "nested": {"preserve": True}}]
        source_slots = {"task_a": {"normalized_value": 1.0}}
        rank_calls = []

        def rank(row, prepared_source_slots):
            rank_calls.append((row, prepared_source_slots))
            return (1, 1, 1, 1, 1, 1, 1)

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_slot_by_task_id",
                return_value=source_slots,
            ) as source_map_owner,
            patch.object(financial_aggregate_projection, "aggregate_result_signature", return_value="sig"),
            patch.object(financial_aggregate_projection, "_aggregate_result_rank", side_effect=rank),
        ):
            deduped = financial_aggregate_projection.dedupe_aggregate_subtask_results(
                ordered_results
            )
        self.assertIs(source_map_owner.call_args.args[0], ordered_results)
        self.assertEqual(rank_calls, [(ordered_results[0], source_slots)])
        self.assertEqual(deduped, ordered_results)

        signature_owner = Mock(return_value="sig")
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_slot_by_task_id",
                side_effect=RuntimeError("source map failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_signature",
                signature_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "source map failed"):
                financial_aggregate_projection.dedupe_aggregate_subtask_results(
                    ordered_results
                )
        signature_owner.assert_not_called()

        seed = {"label": " Metric ", "concept": " Concept ", "nested": {"preserve": True}}
        source_slots = {"task_a": {"normalized_value": 1.0}}
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                return_value=["task_a"],
            ) as task_ids_owner,
            patch.object(
                financial_aggregate_projection,
                "dependency_source_slot_match_score",
                return_value=12,
            ) as match_owner,
        ):
            task_id, selected_slot, prepared_seed, score = (
                financial_aggregate_projection.best_dependency_source_for_seed(
                    seed,
                    "numerator_1",
                    source_slots=source_slots,
                )
            )
        self.assertEqual((task_id, score), ("task_a", 12))
        self.assertEqual(selected_slot, source_slots["task_a"])
        self.assertIsNot(selected_slot, source_slots["task_a"])
        self.assertEqual(prepared_seed["role"], "numerator_1")
        self.assertEqual(prepared_seed["matched_operand_role"], "numerator_1")
        self.assertEqual(prepared_seed["matched_operand_label"], "Metric")
        self.assertEqual(prepared_seed["matched_operand_concept"], "Concept")
        self.assertIs(prepared_seed["nested"], seed["nested"])
        self.assertIs(task_ids_owner.call_args.args[0], match_owner.call_args.args[1])
        self.assertIs(task_ids_owner.call_args.args[1], source_slots)
        self.assertIs(match_owner.call_args.args[0], source_slots["task_a"])
        self.assertEqual(match_owner.call_args.args[2], "numerator_1")

        match_owner = Mock(return_value=12)
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                side_effect=RuntimeError("task ids failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "dependency_source_slot_match_score",
                match_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "task ids failed"):
                financial_aggregate_projection.best_dependency_source_for_seed(
                    seed,
                    "numerator_1",
                    source_slots=source_slots,
                )
        match_owner.assert_not_called()

    def test_aggregate_source_preparation_remaining_callers_preserve_exact_args_and_stop(self) -> None:
        agent = financial_graph_calculation.FinancialAgentCalculationMixin()

        lookup_results = [
            {
                "task_id": " task_a ",
                "operation_family": "lookup",
                "metric_label": "metric",
            }
        ]
        source_slot = {
            "normalized_value": 1.0,
            "metric_label": "slot metric",
        }
        source_slots = {"task_a": source_slot}
        with (
            patch.object(
                financial_graph_calculation,
                "aggregate_source_slot_by_task_id",
                return_value=source_slots,
            ) as dependency_map_owner,
            patch.object(
                financial_graph_calculation,
                "build_dependency_lookup_slots_by_task",
                return_value={},
            ) as dependency_builder,
        ):
            prepared = agent._aggregate_dependency_source_slot_by_task_id(
                lookup_results
            )
        self.assertIs(dependency_map_owner.call_args.args[0], lookup_results)
        self.assertIs(dependency_builder.call_args.args[0], lookup_results)
        self.assertEqual(prepared, source_slots)
        self.assertIs(prepared["task_a"], source_slot)

        dependency_builder = Mock(return_value={})
        with (
            patch.object(
                financial_graph_calculation,
                "aggregate_source_slot_by_task_id",
                side_effect=RuntimeError("dependency source map failed"),
            ),
            patch.object(
                financial_graph_calculation,
                "build_dependency_lookup_slots_by_task",
                dependency_builder,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency source map failed"):
                agent._aggregate_dependency_source_slot_by_task_id(lookup_results)
        dependency_builder.assert_not_called()

        nested = {"preserve": True}
        operands = [
            {"operand_id": "operand_a", "nested": nested},
            None,
        ]
        ordered_results = [{"task_id": "task_a"}]
        calculation_result = {"status": "ok", "nested": nested}
        source_slots = {"task_a": {"normalized_value": 1.0}}
        coherence_calls = []

        def coherence(row, prepared_source_slots):
            coherence_calls.append((row, prepared_source_slots))
            return 7, 8

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_slot_by_task_id",
                return_value=source_slots,
            ) as coherence_map_owner,
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_dependency_coherence_ranks",
                side_effect=coherence,
            ),
        ):
            coherence_rank = financial_aggregate_projection.aggregate_dependency_slot_coherence_rank_for_operands(
                operation_family="sum",
                operands=operands,
                ordered_results=ordered_results,
                calculation_result=calculation_result,
            )
        self.assertEqual(coherence_rank, 7)
        self.assertIs(coherence_map_owner.call_args.args[0], ordered_results)
        self.assertEqual(len(coherence_calls), 1)
        prepared_row, adopted_source_slots = coherence_calls[0]
        self.assertEqual(prepared_row["operation_family"], "sum")
        self.assertEqual(prepared_row["calculation_operands"], [operands[0]])
        self.assertIsNot(prepared_row["calculation_operands"][0], operands[0])
        self.assertIs(prepared_row["calculation_operands"][0]["nested"], nested)
        self.assertEqual(prepared_row["calculation_result"], calculation_result)
        self.assertIsNot(prepared_row["calculation_result"], calculation_result)
        self.assertIs(prepared_row["calculation_result"]["nested"], nested)
        self.assertIs(adopted_source_slots, source_slots)

        coherence_owner = Mock(return_value=(7, 8))
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_slot_by_task_id",
                side_effect=RuntimeError("coherence source map failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_dependency_coherence_ranks",
                coherence_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "coherence source map failed"):
                financial_aggregate_projection.aggregate_dependency_slot_coherence_rank_for_operands(
                    operation_family="sum",
                    operands=operands,
                    ordered_results=ordered_results,
                    calculation_result=calculation_result,
                )
        coherence_owner.assert_not_called()

        nested_result = {
            "task_id": " task_a ",
            "operation_family": "lookup",
            "nested": nested,
        }
        nested_results = [nested_result]
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_slot_by_task_id",
                return_value=source_slots,
            ) as nested_map_owner,
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="lookup",
            ),
        ):
            unpromoted = financial_aggregate_projection.promote_stronger_nested_aggregate_results(
                nested_results
            )
        prepared_nested_rows = nested_map_owner.call_args.args[0]
        self.assertEqual(prepared_nested_rows, [nested_result])
        self.assertIsNot(prepared_nested_rows[0], nested_result)
        self.assertIs(prepared_nested_rows[0]["nested"], nested)
        self.assertIs(unpromoted, nested_results)

        operation_owner = Mock(return_value="lookup")
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_slot_by_task_id",
                side_effect=RuntimeError("nested source map failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                operation_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "nested source map failed"):
                financial_aggregate_projection.promote_stronger_nested_aggregate_results(nested_results)
        operation_owner.assert_not_called()

        operand = {"operand_id": "operand_a", "nested": nested}
        coherence_source_slots = {
            "task_a": {"normalized_value": 1.0, "nested": nested}
        }
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="sum",
            ),
            patch.object(
                financial_aggregate_projection,
                "_aggregate_result_candidate_operands",
                return_value=[operand],
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                return_value=["task_a"],
            ) as coherence_ids_owner,
            patch.object(
                financial_aggregate_projection,
                "answer_slot_has_material",
                return_value=False,
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.aggregate_result_dependency_coherence_ranks(
                    {"operation_family": "sum"},
                    coherence_source_slots,
                ),
                (1, 1),
            )
        self.assertIs(coherence_ids_owner.call_args.args[0], operand)
        prepared_coherence_slots = coherence_ids_owner.call_args.args[1]
        self.assertEqual(prepared_coherence_slots, coherence_source_slots)
        self.assertIsNot(prepared_coherence_slots, coherence_source_slots)
        self.assertIs(
            prepared_coherence_slots["task_a"],
            coherence_source_slots["task_a"],
        )

        material_owner = Mock(return_value=False)
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="sum",
            ),
            patch.object(
                financial_aggregate_projection,
                "_aggregate_result_candidate_operands",
                return_value=[operand],
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_source_task_ids_for_operand",
                side_effect=RuntimeError("coherence task ids failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "answer_slot_has_material",
                material_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "coherence task ids failed"):
                financial_aggregate_projection.aggregate_result_dependency_coherence_ranks(
                    {"operation_family": "sum"},
                    coherence_source_slots,
                )
        material_owner.assert_not_called()

    def test_overlay_calculation_operands_from_slots_preserves_copy_and_overlay_contract(self) -> None:
        update = financial_runtime_trace.overlay_calculation_operands_from_slots
        nested = {"keep": True}
        original_ids = ["old"]
        adopted_ids = ["new"]
        operands = [
            {
                "operand_id": "current",
                "matched_operand_role": " Current_Period ",
                "role": "ignored_role",
                "raw_value": "old-current",
                "source_row_ids": original_ids,
                "nested": nested,
            },
            {
                "operand_id": "prior",
                "matched_operand_role": "",
                "role": "prior_period",
                "raw_value": "old-prior",
                "nested": nested,
            },
            {"operand_id": "other", "role": "other", "raw_value": "unchanged", "nested": nested},
        ]
        trace = {"calculation_operands": operands, "nested": nested}
        current_slot = {
            "raw_value": "10",
            "raw_unit": "unit",
            "normalized_value": 10.0,
            "normalized_unit": "COUNT",
            "source_row_id": "row-current",
            "source_row_ids": adopted_ids,
            "source_anchor": "table-current",
        }
        partial_prior_slot = {"raw_value": "5"}
        before = deepcopy((trace, current_slot, partial_prior_slot))

        default_rows = update(
            trace,
            {"current_period": current_slot, "prior_period": partial_prior_slot},
        )
        self.assertEqual(default_rows[0]["raw_value"], "old-current")
        self.assertEqual(
            {key: default_rows[1][key] for key in current_slot},
            {
                "raw_value": "5",
                "raw_unit": None,
                "normalized_value": None,
                "normalized_unit": None,
                "source_row_id": None,
                "source_row_ids": None,
                "source_anchor": None,
            },
        )

        normalized_rows = update(
            trace,
            {"current_period": current_slot, "prior_period": partial_prior_slot},
            normalize_role=True,
        )
        self.assertEqual(
            {key: normalized_rows[0][key] for key in current_slot},
            current_slot,
        )
        self.assertEqual([row["operand_id"] for row in normalized_rows], ["current", "prior", "other"])
        self.assertEqual(normalized_rows[2], operands[2])
        self.assertIsNot(normalized_rows, operands)
        self.assertTrue(all(current is not original for current, original in zip(normalized_rows, operands)))
        self.assertTrue(all(row["nested"] is nested for row in normalized_rows))
        self.assertIs(normalized_rows[0]["source_row_ids"], adopted_ids)
        self.assertEqual((trace, current_slot, partial_prior_slot), before)

        class FalsySlot(dict):
            get_count = 0

            def get(self, key, default=None):
                self.get_count += 1
                return super().get(key, default)

        shared = {"keep": "shared"}
        duplicate_operands = [
            {"operand_id": "dup-a", "role": "duplicate", "nested": shared},
            {"operand_id": "dup-b", "role": "duplicate", "nested": shared},
        ]
        falsy_slot = FalsySlot()
        duplicate_rows = update(
            {"calculation_operands": duplicate_operands},
            {"duplicate": falsy_slot},
        )
        self.assertEqual(duplicate_rows, duplicate_operands)
        self.assertEqual([row["operand_id"] for row in duplicate_rows], ["dup-a", "dup-b"])
        self.assertTrue(all(current is not original for current, original in zip(duplicate_rows, duplicate_operands)))
        self.assertTrue(all(row["nested"] is shared for row in duplicate_rows))
        self.assertEqual(falsy_slot.get_count, 0)

        class PoisonSlots:
            def get(self, *_args):
                raise RuntimeError("slots accessed")

        empty_first = update({}, PoisonSlots())
        empty_second = update({}, PoisonSlots())
        self.assertEqual(empty_first, [])
        self.assertIsNot(empty_first, empty_second)

        class FalsyTrace:
            def __bool__(self):
                return False

            def get(self, *_args):
                raise RuntimeError("falsy trace accessed")

        class FalsyOperands:
            def __bool__(self):
                return False

            def __iter__(self):
                raise RuntimeError("falsy operands iterated")

        class TruthyTrace:
            def __bool__(self):
                return True

            def get(self, key, default=None):
                return FalsyOperands()

        self.assertEqual(update(FalsyTrace(), PoisonSlots()), [])
        self.assertEqual(update(TruthyTrace(), PoisonSlots()), [])

    def test_overlay_calculation_operands_from_slots_preserves_access_and_exception_contract(self) -> None:
        update = financial_runtime_trace.overlay_calculation_operands_from_slots
        events = []
        source_ids = ["row-current"]

        class Role:
            def __str__(self):
                events.append("str:role")
                return " Current_Period "

        class Trace:
            def get(self, key, default=None):
                events.append(f"trace.get:{key}")
                return [{"matched_operand_role": Role(), "role": "poison"}]

        class Slot(Mapping):
            values = {
                "raw_value": "10",
                "raw_unit": "unit",
                "normalized_value": 10.0,
                "normalized_unit": "COUNT",
                "source_row_id": "row-current",
                "source_row_ids": source_ids,
                "source_anchor": "table-current",
            }

            def __len__(self):
                events.append("slot.len")
                return len(self.values)

            def __iter__(self):
                return iter(self.values)

            def __getitem__(self, key):
                return self.values[key]

            def get(self, key, default=None):
                events.append(f"slot.get:{key}")
                return self.values.get(key, default)

        class SlotMap:
            def get(self, key, default=None):
                events.append(f"slots.get:{key}")
                return Slot()

        class RecordingDict(dict):
            def __init__(self, source):
                events.append("copy:operand")
                super().__init__(source)

            def get(self, key, default=None):
                events.append(f"row.get:{key}")
                return super().get(key, default)

        def normalize(value):
            events.append(f"normalize:{value}")
            return value.strip()

        with (
            patch.object(financial_runtime_trace, "dict", RecordingDict, create=True),
            patch.object(financial_runtime_trace, "_normalise_spaces", side_effect=normalize),
        ):
            updated = update(Trace(), SlotMap(), normalize_role=True)
        self.assertEqual(
            events,
            [
                "trace.get:calculation_operands",
                "copy:operand",
                "row.get:matched_operand_role",
                "str:role",
                "normalize: Current_Period ",
                "slots.get:current_period",
                "slot.len",
                "slot.get:raw_value",
                "slot.get:raw_unit",
                "slot.get:normalized_value",
                "slot.get:normalized_unit",
                "slot.get:source_row_id",
                "slot.get:source_row_ids",
                "slot.get:source_anchor",
            ],
        )
        self.assertIs(updated[0]["source_row_ids"], source_ids)

        class GetBomb:
            def get(self, *_args):
                raise RuntimeError("get failed")

        class CopyBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                raise RuntimeError("copy failed")

            def __getitem__(self, key):
                raise KeyError(key)

        class StringBomb:
            def __str__(self):
                raise RuntimeError("string failed")

        for message, trace, slots in (
            ("get failed", GetBomb(), {}),
            ("copy failed", {"calculation_operands": [CopyBomb()]}, {}),
            ("string failed", {"calculation_operands": [{"role": StringBomb()}]}, {}),
            ("get failed", {"calculation_operands": [{"role": "current"}]}, GetBomb()),
        ):
            with self.subTest(propagates=message), self.assertRaisesRegex(RuntimeError, message):
                update(trace, slots)
        with patch.object(
            financial_runtime_trace,
            "_normalise_spaces",
            side_effect=RuntimeError("normalize failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalize failed"):
                update({"calculation_operands": [{"role": "current"}]}, {}, normalize_role=True)

    def test_aggregate_synthesis_prompt_rows_preserve_projection_contract(self) -> None:
        project = financial_aggregate_projection.aggregate_synthesis_prompt_rows
        nested = {"keep": True}
        row_slots = {"primary_value": {"nested": nested}}
        result_slots = {"primary_value": {"rendered_value": "100", "nested": nested}}
        source_ids = ["ev_a"]
        projected_row = {
            "task_id": "task_a",
            "metric_family": "concept_lookup",
            "metric_label": "metric a",
            "operation_family": "lookup",
            "answer": "metric a is 100",
            "rendered_value": "",
            "status": "ok",
            "source_row_ids": source_ids,
            "source_evidence_ids": [],
            "answer_slots": row_slots,
            "calculation_result": {
                "status": "ok",
                "rendered_value": "100",
                "formatted_result": "",
                "answer_slots": result_slots,
                "source_row_ids": source_ids,
                "source_evidence_ids": [],
                "drop": "result debug",
            },
            "runtime_evidence": ["drop"],
        }
        blank_task_row = {"task_id": "", "answer": "blank task"}
        projection = {
            "calculation_operands": [
                {
                    "task_id": "task_a",
                    "operand_id": "op_a",
                    "matched_operand_role": "primary_value",
                    "label": "metric a",
                    "label_kr": "",
                    "raw_value": "100",
                    "value": None,
                    "raw_unit": "count",
                    "normalized_value": 0,
                    "normalized_unit": "COUNT",
                    "period": "2023",
                    "source_row_id": "ev_a",
                    "source_row_ids": source_ids,
                    "source_evidence_ids": [],
                    "drop": "operand debug",
                },
                {"task_id": "task_a", "operand_id": "filtered", "raw_value": "12"},
                {"task_id": "", "operand_id": "blank_task", "raw_value": "1234"},
            ],
            "calculation_result": {
                "subtask_results": [projected_row, "skip", blank_task_row],
                "answer_slots": {"subtask_results": [{"task_id": "answer_slot_fallback"}]},
            },
        }
        ordered_results = [{"task_id": "ordered_fallback", "answer": "ordered"}]
        before = deepcopy((ordered_results, projection))

        compact_rows = project(ordered_results, projection)

        self.assertEqual(
            compact_rows,
            [
                {
                    "task_id": "task_a",
                    "metric_family": "concept_lookup",
                    "metric_label": "metric a",
                    "operation_family": "lookup",
                    "answer": "metric a is 100",
                    "status": "ok",
                    "source_row_ids": source_ids,
                    "answer_slots": row_slots,
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "100",
                        "answer_slots": result_slots,
                        "source_row_ids": source_ids,
                    },
                    "calculation_operands": [
                        {
                            "operand_id": "op_a",
                            "matched_operand_role": "primary_value",
                            "label": "metric a",
                            "raw_value": "100",
                            "raw_unit": "count",
                            "normalized_value": 0,
                            "normalized_unit": "COUNT",
                            "period": "2023",
                            "source_row_id": "ev_a",
                            "source_row_ids": source_ids,
                        }
                    ],
                },
                {
                    "answer": "blank task",
                    "calculation_operands": [{"operand_id": "blank_task", "raw_value": "1234"}],
                },
            ],
        )
        self.assertEqual(
            list(compact_rows[0]),
            [
                "task_id",
                "metric_family",
                "metric_label",
                "operation_family",
                "answer",
                "status",
                "source_row_ids",
                "answer_slots",
                "calculation_result",
                "calculation_operands",
            ],
        )
        self.assertEqual(
            list(compact_rows[0]["calculation_result"]),
            ["status", "rendered_value", "answer_slots", "source_row_ids"],
        )
        self.assertEqual(
            list(compact_rows[0]["calculation_operands"][0]),
            [
                "operand_id",
                "matched_operand_role",
                "label",
                "raw_value",
                "raw_unit",
                "normalized_value",
                "normalized_unit",
                "period",
                "source_row_id",
                "source_row_ids",
            ],
        )
        self.assertIsNot(compact_rows[0]["answer_slots"], row_slots)
        self.assertIsNot(compact_rows, projection["calculation_result"]["subtask_results"])
        self.assertIsNot(compact_rows[0], projected_row)
        self.assertIsNot(compact_rows[1], blank_task_row)
        self.assertIs(compact_rows[0]["answer_slots"]["primary_value"]["nested"], nested)
        self.assertIs(compact_rows[0]["calculation_result"]["answer_slots"], result_slots)
        self.assertIs(compact_rows[0]["source_row_ids"], source_ids)
        self.assertIs(compact_rows[0]["calculation_operands"][0]["source_row_ids"], source_ids)
        self.assertEqual((ordered_results, projection), before)

        fallback_nested = {"keep": "fallback"}
        answer_slot_row = {
            "task_id": "answer_slot",
            "answer": "answer slot",
            "answer_slots": {"primary_value": fallback_nested},
        }
        answer_slot_rows = [answer_slot_row]
        answer_fallback = project(
            ordered_results,
            {
                "calculation_result": {
                    "subtask_results": [],
                    "answer_slots": {"subtask_results": answer_slot_rows},
                }
            },
        )
        self.assertEqual(answer_fallback, answer_slot_rows)
        self.assertIsNot(answer_fallback, answer_slot_rows)
        self.assertIsNot(answer_fallback[0], answer_slot_row)
        self.assertIsNot(answer_fallback[0]["answer_slots"], answer_slot_row["answer_slots"])
        self.assertIs(answer_fallback[0]["answer_slots"]["primary_value"], fallback_nested)

        ordered_nested = {"keep": "ordered"}
        ordered_fallback_rows = [
            {
                "task_id": "ordered_fallback",
                "answer": "ordered",
                "answer_slots": {"primary_value": ordered_nested},
            }
        ]
        ordered_fallback = project(
            ordered_fallback_rows,
            {"calculation_result": {"subtask_results": [], "answer_slots": {"subtask_results": []}}},
        )
        self.assertEqual(ordered_fallback, ordered_fallback_rows)
        self.assertIsNot(ordered_fallback, ordered_fallback_rows)
        self.assertIsNot(ordered_fallback[0], ordered_fallback_rows[0])
        self.assertIsNot(ordered_fallback[0]["answer_slots"], ordered_fallback_rows[0]["answer_slots"])
        self.assertIs(ordered_fallback[0]["answer_slots"]["primary_value"], ordered_nested)

    def test_aggregate_synthesis_prompt_rows_preserve_access_and_exception_contract(self) -> None:
        project = financial_aggregate_projection.aggregate_synthesis_prompt_rows
        events = []

        class AccessMapping(Mapping):
            def __init__(self, name, values):
                self.name = name
                self.values = values

            def __len__(self):
                return len(self.values)

            def __iter__(self):
                return iter(self.values)

            def __getitem__(self, key):
                events.append(f"getitem:{self.name}:{key}")
                return self.values[key]

            def keys(self):
                events.append(f"keys:{self.name}")
                return self.values.keys()

            def get(self, key, default=None):
                events.append(f"get:{self.name}:{key}")
                return self.values.get(key, default)

        class PoisonRows:
            def __bool__(self):
                raise RuntimeError("fallback rows accessed")

            def __iter__(self):
                raise RuntimeError("fallback rows iterated")

        tracked_projection = AccessMapping(
            "projection",
            {
                "calculation_result": AccessMapping(
                    "result",
                    {
                        "answer_slots": AccessMapping("slots", {"subtask_results": PoisonRows()}),
                        "subtask_results": [{"task_id": "task_a"}],
                    },
                ),
                "calculation_operands": [],
            },
        )
        self.assertEqual(project(PoisonRows(), tracked_projection), [{"task_id": "task_a"}])
        self.assertEqual(
            events,
            [
                "get:projection:calculation_result",
                "keys:result",
                "getitem:result:answer_slots",
                "getitem:result:subtask_results",
                "keys:slots",
                "getitem:slots:subtask_results",
                "get:projection:calculation_operands",
            ],
        )

        with patch.object(
            financial_aggregate_projection,
            "operand_row_has_material_numeric_payload",
            side_effect=RuntimeError("material predicate accessed"),
        ) as material_predicate:
            self.assertEqual(project([], {"calculation_result": {}, "calculation_operands": []}), [])
        material_predicate.assert_not_called()

        packaging_events = []

        class CopySource(Mapping):
            def __init__(self, copy_name, values):
                self.copy_name = copy_name
                self.values = values

            def __len__(self):
                return len(self.values)

            def __iter__(self):
                return iter(self.values)

            def __getitem__(self, key):
                return self.values[key]

        tracked_keys = {
            "operand-a-copy": {"task_id", "operand_id", "label_kr", "raw_value"},
            "operand-b-copy": {"task_id", "operand_id", "label_kr", "raw_value"},
            "row": {"task_id", "metric_family", "rendered_value", "answer_slots", "calculation_result"},
            "row-result-copy": {"status", "formatted_result", "answer_slots"},
        }

        class RecordingDict(dict):
            def __init__(self, *args, **kwargs):
                source = args[0] if args else None
                copy_name = str(getattr(source, "copy_name", "") or "")
                if copy_name:
                    packaging_events.append(f"copy:{copy_name}")
                super().__init__(*args, **kwargs)
                self.track_name = f"{copy_name}-copy" if copy_name else ""

            def get(self, key, default=None):
                if key in tracked_keys.get(self.track_name, set()):
                    packaging_events.append(f"get:{self.track_name}:{key}")
                return super().get(key, default)

        shared_nested = {"keep": "nested"}
        operand_a = CopySource(
            "operand-a",
            {
                "task_id": "task_a",
                "operand_id": "op_a",
                "label_kr": "",
                "raw_value": "1234",
                "nested": shared_nested,
            },
        )
        operand_b = CopySource(
            "operand-b",
            {
                "task_id": "task_a",
                "operand_id": "op_b",
                "label_kr": "retained",
                "raw_value": "5678",
                "nested": shared_nested,
            },
        )
        tracked_row = RecordingDict(
            {
                "task_id": "task_a",
                "metric_family": "lookup",
                "rendered_value": "",
                "answer_slots": CopySource("row-slots", {"primary_value": shared_nested}),
                "calculation_result": CopySource(
                    "row-result",
                    {"status": "ok", "formatted_result": "", "answer_slots": {"primary_value": shared_nested}},
                ),
            }
        )
        tracked_row.track_name = "row"
        copied_operands = []

        def accept_material(copied_operand):
            packaging_events.append(f"predicate:{copied_operand['operand_id']}")
            copied_operands.append(copied_operand)
            return True

        with (
            patch.object(financial_aggregate_projection, "dict", RecordingDict, create=True),
            patch.object(
                financial_aggregate_projection,
                "operand_row_has_material_numeric_payload",
                side_effect=accept_material,
            ),
        ):
            tracked_result = project(
                [],
                {
                    "calculation_operands": [operand_a, operand_b],
                    "calculation_result": {"subtask_results": [tracked_row]},
                },
            )
        self.assertEqual(
            packaging_events,
            [
                "copy:operand-a",
                "predicate:op_a",
                "get:operand-a-copy:task_id",
                "get:operand-a-copy:operand_id",
                "get:operand-a-copy:operand_id",
                "get:operand-a-copy:label_kr",
                "get:operand-a-copy:raw_value",
                "get:operand-a-copy:raw_value",
                "copy:operand-b",
                "predicate:op_b",
                "get:operand-b-copy:task_id",
                "get:operand-b-copy:operand_id",
                "get:operand-b-copy:operand_id",
                "get:operand-b-copy:label_kr",
                "get:operand-b-copy:label_kr",
                "get:operand-b-copy:raw_value",
                "get:operand-b-copy:raw_value",
                "get:row:task_id",
                "get:row:task_id",
                "get:row:task_id",
                "get:row:metric_family",
                "get:row:metric_family",
                "get:row:rendered_value",
                "get:row:answer_slots",
                "copy:row-slots",
                "get:row:calculation_result",
                "copy:row-result",
                "get:row-result-copy:status",
                "get:row-result-copy:status",
                "get:row-result-copy:formatted_result",
                "get:row-result-copy:answer_slots",
                "get:row-result-copy:answer_slots",
            ],
        )
        self.assertEqual([row["operand_id"] for row in copied_operands], ["op_a", "op_b"])
        self.assertIsNot(copied_operands[0], operand_a)
        self.assertIs(copied_operands[0]["nested"], shared_nested)
        self.assertEqual(
            [row["operand_id"] for row in tracked_result[0]["calculation_operands"]],
            ["op_a", "op_b"],
        )

        class GetBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                return iter(("calculation_result",))

            def __getitem__(self, key):
                raise KeyError(key)

            def get(self, _key, _default=None):
                raise RuntimeError("mapping get failed")

        class CopyBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                return iter(("value",))

            def __getitem__(self, _key):
                raise RuntimeError("mapping copy failed")

            def __bool__(self):
                return True

        class IterBomb:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("row iteration failed")

        class TruthBomb:
            def __bool__(self):
                raise RuntimeError("truthiness failed")

        class StringBomb:
            def __str__(self):
                raise RuntimeError("string failed")

        class EqualityBomb:
            def __eq__(self, _other):
                raise RuntimeError("equality failed")

        with self.assertRaisesRegex(RuntimeError, "mapping get failed"):
            project([], GetBomb())
        with self.assertRaisesRegex(RuntimeError, "mapping copy failed"):
            project([], {"calculation_result": CopyBomb()})
        with self.assertRaisesRegex(RuntimeError, "row iteration failed"):
            project([], {"calculation_result": {"subtask_results": IterBomb()}})
        with self.assertRaisesRegex(RuntimeError, "truthiness failed"):
            project([], {"calculation_result": {}, "calculation_operands": [TruthBomb()]})
        with self.assertRaisesRegex(RuntimeError, "mapping copy failed"):
            project([], {"calculation_result": {}, "calculation_operands": [CopyBomb()]})
        with patch.object(
            financial_aggregate_projection,
            "operand_row_has_material_numeric_payload",
            return_value=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "string failed"):
                project(
                    [],
                    {
                        "calculation_result": {},
                        "calculation_operands": [{"task_id": StringBomb(), "raw_value": "1234"}],
                    },
                )
            with self.assertRaisesRegex(RuntimeError, "equality failed"):
                project(
                    [],
                    {
                        "calculation_result": {},
                        "calculation_operands": [{"operand_id": EqualityBomb(), "raw_value": "1234"}],
                    },
                )
        with patch.object(
            financial_aggregate_projection,
            "operand_row_has_material_numeric_payload",
            side_effect=RuntimeError("material predicate failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "material predicate failed"):
                project(
                    [{"task_id": "later"}],
                    {
                        "calculation_result": {},
                        "calculation_operands": [{"task_id": StringBomb(), "raw_value": "1234"}],
                    },
                )

    def test_subtask_numeric_conflict_and_direct_source_refs_preserve_behavior(self) -> None:
        conflict = financial_aggregate_projection.subtask_numeric_answers_conflict
        has_direct_refs = financial_aggregate_projection.subtask_row_has_direct_source_refs
        nested = {"keep": True}
        candidate = {
            "answer": "",
            "calculation_result": {
                "formatted_result": "metric is 10.00%",
                "rendered_value": "must stay fallback",
                "nested": nested,
            },
        }
        current = {
            "answer": "metric is 10%",
            "calculation_result": {"formatted_result": "must stay lazy"},
        }
        source_row = {
            "source_row_ids": ["", "task_output:lookup"],
            "selected_claim_ids": ["task_output:claim"],
            "calculation_result": {
                "source_row_ids": ["task_output:result"],
                "source_evidence_ids": ["ev_direct"],
                "nested": nested,
            },
        }
        before = deepcopy((candidate, current, source_row))

        self.assertFalse(conflict(candidate, current))
        self.assertFalse(conflict({"answer": "metric is 10%"}, {"answer": "10% and 20%"}))
        self.assertTrue(conflict({"answer": "10% and 20%"}, {"answer": "metric is 10%"}))
        self.assertTrue(
            conflict(
                {"calculation_result": {"formatted_result": "", "rendered_value": "20%"}},
                {"calculation_result": {"formatted_result": "10%", "rendered_value": "20%"}},
            )
        )
        self.assertFalse(conflict({"answer": "no number"}, {"answer": "10%"}))
        self.assertFalse(has_direct_refs({"source_row_ids": ["", "task_output:lookup"]}))
        self.assertTrue(has_direct_refs(source_row))
        self.assertEqual((candidate, current, source_row), before)
        self.assertIs(candidate["calculation_result"]["nested"], nested)
        self.assertIs(source_row["calculation_result"]["nested"], nested)

    def test_subtask_numeric_conflict_and_direct_source_refs_preserve_access_contract(self) -> None:
        conflict = financial_aggregate_projection.subtask_numeric_answers_conflict
        has_direct_refs = financial_aggregate_projection.subtask_row_has_direct_source_refs
        events = []

        class TrackedGet(Mapping):
            def __init__(self, name, values):
                self.name = name
                self.values = values

            def __len__(self):
                return len(self.values)

            def __iter__(self):
                return iter(self.values)

            def __getitem__(self, key):
                return self.values[key]

            def get(self, key, default=None):
                events.append(f"get:{self.name}:{key}")
                return self.values.get(key, default)

        class TrackedString:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __str__(self):
                events.append(f"str:{self.name}")
                return self.value

        candidate_result = TrackedGet(
            "candidate_result",
            {"formatted_result": "", "rendered_value": TrackedString("candidate_rendered", "candidate")},
        )
        candidate_row = TrackedGet(
            "candidate",
            {"answer": "", "calculation_result": candidate_result},
        )
        current_row = TrackedGet(
            "current",
            {"answer": TrackedString("current_answer", "current")},
        )

        def normalize(value):
            events.append(f"normalize:{value}")
            return value

        def extract(value):
            events.append(f"extract:{value}")
            return ["c1", "c2", "c3"] if value == "candidate" else ["r1", "r2", "r3"]

        def equivalent(left, right):
            events.append(f"equivalent:{left}:{right}")
            if left == "c3" or (left, right) == ("c1", "r3"):
                raise RuntimeError("short-circuited equivalence must stay lazy")
            return (left, right) == ("c1", "r2")

        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_aggregate_projection, "extract_numeric_surface_candidates", side_effect=extract),
            patch.object(financial_aggregate_projection, "numeric_surface_candidates_equivalent", side_effect=equivalent),
        ):
            self.assertTrue(conflict(candidate_row, current_row))
        self.assertEqual(
            events,
            [
                "get:candidate:answer",
                "get:candidate:calculation_result",
                "get:candidate_result:formatted_result",
                "get:candidate:calculation_result",
                "get:candidate_result:rendered_value",
                "str:candidate_rendered",
                "normalize:candidate",
                "get:current:answer",
                "str:current_answer",
                "normalize:current",
                "extract:candidate",
                "extract:current",
                "equivalent:c1:r1",
                "equivalent:c1:r2",
                "equivalent:c2:r1",
                "equivalent:c2:r2",
                "equivalent:c2:r3",
            ],
        )

        for extracted in (
            [[], [{"text": "current"}]],
            [[{"text": "candidate"}], []],
        ):
            with (
                patch.object(
                    financial_aggregate_projection,
                    "extract_numeric_surface_candidates",
                    side_effect=extracted,
                ) as extractor,
                patch.object(
                    financial_aggregate_projection,
                    "numeric_surface_candidates_equivalent",
                    side_effect=RuntimeError("equivalence must stay lazy"),
                ) as lazy_equivalence,
            ):
                self.assertFalse(conflict({"answer": "candidate"}, {"answer": "current"}))
            self.assertEqual(extractor.call_count, 2)
            lazy_equivalence.assert_not_called()

        events.clear()
        row_source_ids = object()
        result_source_ids = object()
        selected_claim_ids = object()
        source_evidence_ids = object()

        class TruthyCalculation:
            def __bool__(self):
                events.append("bool:calculation_input")
                return True

        calculation_input = TruthyCalculation()
        copied_result = TrackedGet(
            "copied_result",
            {
                "source_row_ids": result_source_ids,
                "source_evidence_ids": source_evidence_ids,
            },
        )
        tracked_row = TrackedGet(
            "row",
            {
                "calculation_result": calculation_input,
                "source_row_ids": row_source_ids,
                "selected_claim_ids": selected_claim_ids,
            },
        )

        class SourceId:
            def __init__(self, name, *, truthy=True, task_output=False):
                self.name = name
                self.truthy = truthy
                self.task_output = task_output

            def __bool__(self):
                events.append(f"bool:{self.name}")
                return self.truthy

            def startswith(self, prefix):
                events.append(f"startswith:{self.name}:{prefix}")
                return self.task_output

        class LaterSource:
            def __bool__(self):
                raise RuntimeError("later source must stay lazy")

        cleaner_inputs = []

        def copy_result(value):
            events.append("copy:calculation_input")
            self.assertIs(value, calculation_input)
            return copied_result

        def clean_source_ids(values):
            events.append("clean")
            cleaner_inputs.append(values)
            return [
                SourceId("blank", truthy=False),
                SourceId("task", task_output=True),
                SourceId("direct"),
                LaterSource(),
            ]

        with (
            patch.object(financial_aggregate_projection, "dict", side_effect=copy_result, create=True),
            patch.object(financial_aggregate_projection, "_clean_source_row_ids", side_effect=clean_source_ids),
        ):
            self.assertTrue(has_direct_refs(tracked_row))
        self.assertEqual(
            events,
            [
                "get:row:calculation_result",
                "bool:calculation_input",
                "copy:calculation_input",
                "get:row:source_row_ids",
                "get:copied_result:source_row_ids",
                "get:row:selected_claim_ids",
                "get:copied_result:source_evidence_ids",
                "clean",
                "bool:blank",
                "bool:blank",
                "bool:task",
                "startswith:task:task_output:",
                "bool:direct",
                "startswith:direct:task_output:",
            ],
        )
        self.assertEqual(len(cleaner_inputs), 1)
        for actual, expected in zip(
            cleaner_inputs[0],
            (row_source_ids, result_source_ids, selected_claim_ids, source_evidence_ids),
        ):
            self.assertIs(actual, expected)

        class GetBomb(Mapping):
            def __len__(self):
                return 0

            def __iter__(self):
                return iter(())

            def __getitem__(self, _key):
                raise KeyError

            def get(self, _key, _default=None):
                raise RuntimeError("mapping get failed")

        class StringBomb:
            def __str__(self):
                raise RuntimeError("string failed")

        class StartswithBomb:
            def __bool__(self):
                return True

            def startswith(self, _prefix):
                raise RuntimeError("startswith failed")

        with self.assertRaisesRegex(RuntimeError, "mapping get failed"):
            conflict(GetBomb(), {"answer": "1"})
        with self.assertRaisesRegex(RuntimeError, "string failed"):
            conflict({"answer": StringBomb()}, {"answer": "1"})
        with patch.object(
            financial_aggregate_projection,
            "_normalise_spaces",
            side_effect=RuntimeError("normalization failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalization failed"):
                conflict({"answer": "1"}, {"answer": "1"})
        with patch.object(
            financial_aggregate_projection,
            "extract_numeric_surface_candidates",
            side_effect=RuntimeError("extraction failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "extraction failed"):
                conflict({"answer": "1"}, {"answer": "1"})
        with patch.object(
            financial_aggregate_projection,
            "numeric_surface_candidates_equivalent",
            side_effect=RuntimeError("equivalence failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "equivalence failed"):
                conflict({"answer": "10%"}, {"answer": "20%"})
        with patch.object(
            financial_aggregate_projection,
            "dict",
            side_effect=RuntimeError("mapping copy failed"),
            create=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "mapping copy failed"):
                has_direct_refs({"calculation_result": {"source_row_ids": ["ev"]}})
        with patch.object(
            financial_aggregate_projection,
            "_clean_source_row_ids",
            side_effect=RuntimeError("source cleaning failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "source cleaning failed"):
                has_direct_refs({})
        with patch.object(
            financial_aggregate_projection,
            "_clean_source_row_ids",
            return_value=[StartswithBomb()],
        ):
            with self.assertRaisesRegex(RuntimeError, "startswith failed"):
                has_direct_refs({})

    def test_aggregate_signature_and_growth_sign_rank_preserve_primitive_contract(self) -> None:
        def signature(row, *, delegate=None):
            if delegate is None:
                return financial_aggregate_projection.aggregate_result_signature(row)
            with patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=delegate._aggregate_result_operation_family,
            ):
                return financial_aggregate_projection.aggregate_result_signature(row)

        def sign_rank(row, *, delegate=None):
            if delegate is None:
                return financial_aggregate_projection.growth_operand_sign_consistency_rank(row)
            with patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=delegate._aggregate_result_operation_family,
            ):
                return financial_aggregate_projection.growth_operand_sign_consistency_rank(row)

        row = {
            "task_id": "task_fallback",
            "metric_label": " row   metric ",
            "calculation_result": {
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "slot metric",
                }
            },
            "answer_slots": {"operation_family": "lookup", "metric_label": "row slot metric"},
        }
        row_snapshot = deepcopy(row)
        self.assertEqual(signature(row), "ratio:row metric")
        self.assertEqual(row, row_snapshot)
        self.assertEqual(
            signature(
                {
                    "task_id": "task_fallback",
                    "calculation_result": {
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "metric_label": " slot   metric ",
                        }
                    },
                    "answer_slots": {"metric_label": "row slot metric"},
                }
            ),
            "growth_rate:slot metric",
        )
        self.assertEqual(
            signature(
                {
                    "task_id": "task_fallback",
                    "calculation_result": {},
                    "answer_slots": {"metric_label": " row   slot ", "operation_family": "lookup"},
                }
            ),
            "lookup:row slot",
        )
        self.assertEqual(signature({"task_id": " task   fallback "}), "task fallback")

        lazy_delegate = SimpleNamespace(
            _aggregate_result_operation_family=lambda _row: (_ for _ in ()).throw(
                RuntimeError("family must stay lazy")
            )
        )
        self.assertEqual(
            signature(
                {
                    "metric_label": "   ",
                    "answer_slots": {"metric_label": "must not replace raw whitespace"},
                },
                delegate=lazy_delegate,
            ),
            "",
        )

        events = []

        class _TrackedMapping(Mapping):
            def __init__(self, name, values, *, fail_keys=False):
                self.name = name
                self.values = values
                self.fail_keys = fail_keys

            def __len__(self):
                return len(self.values)

            def __iter__(self):
                return iter(self.values)

            def __getitem__(self, key):
                events.append(f"getitem:{self.name}:{key}")
                return self.values[key]

            def keys(self):
                events.append(f"keys:{self.name}")
                if self.fail_keys:
                    raise RuntimeError(f"failed to copy {self.name}")
                return self.values.keys()

            def get(self, key, default=None):
                events.append(f"get:{self.name}:{key}")
                return self.values.get(key, default)

        tracked_slots = _TrackedMapping(
            "result_slots",
            {"operation_family": "ratio", "metric_label": "slot metric"},
        )
        tracked_result = _TrackedMapping("result", {"answer_slots": tracked_slots})
        tracked_row = _TrackedMapping(
            "row",
            {"calculation_result": tracked_result, "metric_label": ""},
        )
        tracked_delegate = SimpleNamespace(
            _aggregate_result_operation_family=lambda _row: events.append("family") or "ratio"
        )
        self.assertEqual(signature(tracked_row, delegate=tracked_delegate), "ratio:slot metric")
        self.assertEqual(
            events,
            [
                "get:row:calculation_result",
                "keys:result",
                "getitem:result:answer_slots",
                "keys:result_slots",
                "getitem:result_slots:operation_family",
                "getitem:result_slots:metric_label",
                "get:row:metric_label",
                "family",
            ],
        )

        events.clear()
        fallback_slots = _TrackedMapping("row_slots", {"metric_label": "fallback metric"})
        fallback_row = _TrackedMapping(
            "row",
            {
                "calculation_result": _TrackedMapping("result", {"answer_slots": {}}),
                "answer_slots": fallback_slots,
                "metric_label": "",
            },
        )
        fallback_delegate = SimpleNamespace(_aggregate_result_operation_family=lambda _row: "")
        self.assertEqual(signature(fallback_row, delegate=fallback_delegate), "fallback metric")
        self.assertLess(events.index("get:row:answer_slots"), events.index("keys:row_slots"))

        events.clear()
        broken_row = _TrackedMapping(
            "row",
            {"calculation_result": _TrackedMapping("result", {"answer_slots": {}}, fail_keys=True)},
        )
        with self.assertRaisesRegex(RuntimeError, "failed to copy result"):
            signature(broken_row, delegate=tracked_delegate)
        self.assertEqual(events, ["get:row:calculation_result", "keys:result"])

        def growth_row(current, prior, *, result_slots=True):
            slots = {
                "operation_family": "growth_rate",
                "current_value": {"normalized_value": current},
                "prior_value": {"normalized_value": prior},
            }
            if result_slots:
                return {
                    "calculation_result": {"answer_slots": slots},
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "current_value": {"normalized_value": 1},
                        "prior_value": {"normalized_value": -1},
                    },
                }
            return {"calculation_result": {}, "answer_slots": slots}

        for name, current, prior, expected in (
            ("same_positive", 2, 1, 2),
            ("same_negative", -2, -1, 2),
            ("opposite", 2, -1, 0),
            ("zero", 0, 1, 1),
            ("missing", None, 1, 1),
            ("invalid", "invalid", 1, 1),
            ("nan", math.nan, 1, 1),
            ("positive_inf", math.inf, 1, 2),
            ("negative_inf", -math.inf, -1, 2),
        ):
            with self.subTest(rank=name):
                self.assertEqual(sign_rank(growth_row(current, prior)), expected)
        self.assertEqual(sign_rank(growth_row(-2, -1, result_slots=False)), 2)

        class _UnreadableRow(dict):
            def get(self, key, default=None):
                if key == "calculation_result":
                    raise RuntimeError("rank body result must stay lazy")
                return super().get(key, default)

        non_growth_delegate = SimpleNamespace(_aggregate_result_operation_family=lambda _row: "ratio")
        self.assertEqual(sign_rank(_UnreadableRow(), delegate=non_growth_delegate), 1)
        with self.assertRaisesRegex(RuntimeError, "rank body result must stay lazy"):
            sign_rank(
                _UnreadableRow(),
                delegate=SimpleNamespace(
                    _aggregate_result_operation_family=lambda _row: "growth_rate"
                ),
            )

        events.clear()

        class _TrackedNumber:
            def __init__(self, name, value=1.0, error=None):
                self.name = name
                self.value = value
                self.error = error

            def __float__(self):
                events.append(f"float:{self.name}")
                if self.error is not None:
                    raise self.error(f"failed {self.name}")
                return self.value

        growth_delegate = SimpleNamespace(_aggregate_result_operation_family=lambda _row: "growth_rate")
        self.assertEqual(
            sign_rank(
                growth_row(_TrackedNumber("current"), _TrackedNumber("prior")),
                delegate=growth_delegate,
            ),
            2,
        )
        self.assertEqual(events, ["float:current", "float:prior"])

        events.clear()
        self.assertEqual(
            sign_rank(
                growth_row(
                    _TrackedNumber("current", error=TypeError),
                    _TrackedNumber("prior"),
                ),
                delegate=growth_delegate,
            ),
            1,
        )
        self.assertEqual(events, ["float:current", "float:prior"])

        events.clear()
        with self.assertRaisesRegex(RuntimeError, "failed current"):
            sign_rank(
                growth_row(
                    _TrackedNumber("current", error=RuntimeError),
                    _TrackedNumber("prior"),
                ),
                delegate=growth_delegate,
            )
        self.assertEqual(events, ["float:current"])

    def test_aggregate_composition_transition_preserves_state_and_access_contract(self) -> None:
        def apply_transition(state, **kwargs):
            return apply_aggregate_composition_answer(state, **kwargs)

        projection = {"calculation_result": {"status": "ok"}}
        state = AggregateCompositionState(
            final_answer="current answer",
            selected_claim_ids=[" current ", "duplicate"],
            calculation_projection_override=projection,
            narrative_answer_locked=False,
            planner_feedback="planner",
            deterministic_feedback="deterministic",
        )
        state_snapshot = deepcopy(state)
        incoming_projection = {"calculation_result": {"status": "replaced"}}
        transitioned = apply_transition(
            state,
            answer="  replacement   answer  ",
            selected_claim_ids=["duplicate", " incoming ", ""],
            calculation_projection_override=incoming_projection,
            narrative_answer_locked=True,
        )
        self.assertEqual(transitioned.final_answer, "replacement answer")
        self.assertEqual(transitioned.selected_claim_ids, ["current", "duplicate", "incoming"])
        self.assertIsNot(transitioned.selected_claim_ids, state.selected_claim_ids)
        self.assertIs(transitioned.calculation_projection_override, incoming_projection)
        self.assertTrue(transitioned.narrative_answer_locked)
        self.assertEqual((transitioned.planner_feedback, transitioned.deterministic_feedback), ("", ""))
        self.assertIsNot(transitioned, state)
        self.assertEqual(state, state_snapshot)

        preserved = apply_transition(
            state,
            answer="   ",
            calculation_projection_override=("not", "a", "dict"),
            clear_feedback=False,
        )
        self.assertEqual(preserved.final_answer, "current answer")
        self.assertIs(preserved.calculation_projection_override, projection)
        self.assertFalse(preserved.narrative_answer_locked)
        self.assertEqual(
            (preserved.planner_feedback, preserved.deterministic_feedback),
            ("planner", "deterministic"),
        )
        locked_state = state._replace(narrative_answer_locked=True)
        self.assertTrue(apply_transition(locked_state).narrative_answer_locked)
        self.assertFalse(
            apply_transition(locked_state, narrative_answer_locked=False).narrative_answer_locked
        )
        reset = apply_transition(
            state,
            calculation_projection_override=incoming_projection,
            reset_projection_override=True,
        )
        self.assertIsNone(reset.calculation_projection_override)

        events = []

        class _TrackedClaim:
            def __init__(self, name, text, *, fail_on_call=0):
                self.name = name
                self.text = text
                self.fail_on_call = fail_on_call
                self.calls = 0

            def __str__(self):
                self.calls += 1
                events.append(f"str:{self.name}")
                if self.calls == self.fail_on_call:
                    raise RuntimeError(f"failed to stringify {self.name}")
                return self.text

        class _TrackingState:
            def __init__(self):
                self.current_claims = [_TrackedClaim("current", " current ")]
                self.projection = {"marker": True}

            @property
            def final_answer(self):
                events.append("get:final_answer")
                return "fallback"

            @property
            def selected_claim_ids(self):
                events.append("get:selected_claim_ids")
                return self.current_claims

            @property
            def calculation_projection_override(self):
                events.append("get:projection")
                return self.projection

            @property
            def narrative_answer_locked(self):
                events.append("get:lock")
                return True

            @property
            def planner_feedback(self):
                events.append("get:planner")
                return "planner"

            @property
            def deterministic_feedback(self):
                events.append("get:deterministic")
                return "deterministic"

        class _TrackedClear:
            def __init__(self):
                self.values = iter((True, False))

            def __bool__(self):
                events.append("bool:clear")
                return next(self.values)

        tracked_state = _TrackingState()
        incoming_claim = _TrackedClaim("incoming", " incoming ")
        with patch.object(
            financial_aggregate_state,
            "_normalise_spaces",
            side_effect=lambda value: events.append("normalize:answer") or "normalized",
        ):
            tracked = apply_transition(
                tracked_state,
                answer="raw",
                selected_claim_ids=[incoming_claim],
                narrative_answer_locked=False,
                clear_feedback=_TrackedClear(),
            )
        self.assertEqual(tracked.final_answer, "normalized")
        self.assertEqual(tracked.selected_claim_ids, ["current", "incoming"])
        self.assertEqual(tracked.planner_feedback, "")
        self.assertEqual(tracked.deterministic_feedback, "deterministic")
        self.assertEqual(
            events,
            [
                "normalize:answer",
                "get:selected_claim_ids",
                "str:current",
                "str:current",
                "str:incoming",
                "str:incoming",
                "get:projection",
                "bool:clear",
                "bool:clear",
                "get:deterministic",
            ],
        )

        events.clear()
        broken = _TrackedClaim("broken", "broken", fail_on_call=2)
        with self.assertRaisesRegex(RuntimeError, "failed to stringify broken"):
            apply_transition(
                AggregateCompositionState("answer", [], projection, False, "planner", "deterministic"),
                selected_claim_ids=[broken],
            )
        self.assertEqual(events, ["str:broken", "str:broken"])

        class _UnhashableClaimText(str):
            def strip(self, *_args):
                return self

            def __hash__(self):
                raise RuntimeError("failed to hash claim")

        class _UnhashableClaim:
            def __str__(self):
                return _UnhashableClaimText("claim")

        with self.assertRaisesRegex(RuntimeError, "failed to hash claim"):
            apply_transition(
                AggregateCompositionState("answer", [], projection, False, "planner", "deterministic"),
                selected_claim_ids=[_UnhashableClaim()],
            )

    def test_initial_aggregate_composition_wires_public_transition_in_order(self) -> None:
        def build_agent(*, locked=False, growth=None, entity=None, business=None, dividend=None, quantitative=None):
            events = []
            business_inputs = []

            def compose(name, result):
                def run(**kwargs):
                    events.append(name)
                    if name == "business":
                        business_inputs.append(kwargs["existing_answer"])
                    return result

                return run

            return (
                SimpleNamespace(
                    _unresolved_structured_numeric_gap=lambda _rows: False,
                    _answer_matches_supported_aggregate_subtask=lambda *_args, **_kwargs: locked,
                    _compose_growth_narrative_answer=compose("growth", growth),
                    _compose_entity_table_summary_answer=compose("entity", entity),
                    _compose_business_technology_focus_answer=compose("business", business),
                    _compose_dividend_policy_hybrid_answer=compose("dividend", dividend),
                    quantitative_impact_owner=compose("quantitative", quantitative),
                    _augment_narrative_answer_with_supported_drivers=lambda answer, *_args, **_kwargs: answer,
                    _answer_satisfies_growth_narrative_intent=lambda **_kwargs: True,
                ),
                events,
                business_inputs,
            )

        def compose(agent, *, supported_answer=""):
            with (
                patch.object(
                    financial_graph_calculation.calculation_rendering,
                    "coerce_sign_aware_subtraction_answer",
                    side_effect=lambda answer, **_kwargs: answer,
                ),
                patch.object(
                    financial_graph_calculation.calculation_rendering,
                    "compose_slot_based_difference_answer",
                    return_value="",
                ),
                patch.object(
                    financial_graph_calculation,
                    "compose_supported_quantitative_impact_answer",
                    side_effect=agent.quantitative_impact_owner,
                ),
            ):
                return financial_graph_calculation.FinancialAgentCalculationMixin._apply_initial_aggregate_answer_composition(
                    agent,
                    {"query": "summarize", "report_scope": {}},
                    ordered_results=[],
                    preliminary_projection={"calculation_result": {}},
                    aggregate_evidence_items=[],
                    narrative_docs=[],
                    narrative_context="",
                    final_answer="initial answer",
                    supported_aggregate_answer=supported_answer,
                    complete_numeric_answer="numeric answer",
                    has_narrative_summary=False,
                    has_growth_rate_result=False,
                    numeric_answer_locked=False,
                    planner_feedback="planner",
                    deterministic_feedback="deterministic",
                )

        entity_projection = {"calculation_result": {"status": "entity"}}
        agent, events, business_inputs = build_agent(
            entity={
                "compressed_answer": "entity answer",
                "selected_claim_ids": ["entity"],
                "calculation_projection": entity_projection,
            },
            business={"compressed_answer": "business answer", "selected_claim_ids": ["business"]},
        )
        with patch.object(
            financial_graph_calculation,
            "apply_aggregate_composition_answer",
            wraps=apply_aggregate_composition_answer,
        ) as transition:
            composed, complete_numeric_answer = compose(agent)
        self.assertEqual(events, ["growth", "entity", "business", "dividend", "quantitative"])
        self.assertEqual(business_inputs, ["entity answer"])
        self.assertEqual(transition.call_count, 2)
        self.assertEqual(transition.call_args_list[0].args[0].final_answer, "initial answer")
        self.assertEqual(transition.call_args_list[1].args[0].final_answer, "entity answer")
        self.assertEqual(composed.final_answer, "business answer")
        self.assertEqual(composed.selected_claim_ids, ["entity", "business"])
        self.assertIs(composed.calculation_projection_override, entity_projection)
        self.assertEqual(complete_numeric_answer, "numeric answer")

        growth_agent, _, _ = build_agent(
            growth={"compressed_answer": "growth answer", "selected_claim_ids": ["growth"]},
        )
        with patch.object(
            financial_graph_calculation,
            "apply_aggregate_composition_answer",
            wraps=apply_aggregate_composition_answer,
        ) as transition:
            growth_state, _ = compose(growth_agent)
        transition.assert_called_once()
        self.assertTrue(transition.call_args.kwargs["narrative_answer_locked"])
        self.assertEqual((growth_state.final_answer, growth_state.selected_claim_ids), ("growth answer", ["growth"]))

        dividend_agent, _, _ = build_agent(
            dividend={"answer": "dividend answer", "supporting_claim_ids": ["dividend"]},
            quantitative={"answer": "quantitative answer", "supporting_claim_ids": ["quantitative"]},
        )
        with patch.object(
            financial_graph_calculation,
            "apply_aggregate_composition_answer",
            wraps=apply_aggregate_composition_answer,
        ) as transition:
            quantitative_state, _ = compose(dividend_agent)
        self.assertEqual(transition.call_count, 2)
        self.assertTrue(transition.call_args_list[0].kwargs["reset_projection_override"])
        self.assertTrue(transition.call_args_list[1].kwargs["narrative_answer_locked"])
        self.assertEqual(quantitative_state.final_answer, "quantitative answer")
        self.assertEqual(quantitative_state.selected_claim_ids, ["dividend", "quantitative"])

        locked_agent, locked_events, _ = build_agent(
            locked=True,
            growth={"compressed_answer": "growth answer"},
            entity={"compressed_answer": "entity answer"},
            business={"compressed_answer": "business answer"},
            quantitative={"answer": "quantitative answer"},
        )
        with patch.object(financial_graph_calculation, "apply_aggregate_composition_answer") as transition:
            locked_state, _ = compose(locked_agent, supported_answer="supported answer")
        self.assertEqual(locked_events, ["growth", "entity", "business", "dividend", "quantitative"])
        transition.assert_not_called()
        self.assertEqual(locked_state.final_answer, "initial answer")
        self.assertTrue(locked_state.narrative_answer_locked)

        failing_agent, failing_events, _ = build_agent(
            growth={"compressed_answer": "growth answer"},
            entity={"compressed_answer": "entity answer"},
            business={"compressed_answer": "business answer"},
            quantitative={"answer": "quantitative answer"},
        )
        with patch.object(
            financial_graph_calculation,
            "apply_aggregate_composition_answer",
            side_effect=RuntimeError("transition failed"),
        ) as transition:
            with self.assertRaisesRegex(RuntimeError, "transition failed"):
                compose(failing_agent)
        self.assertEqual(failing_events, ["growth", "entity"])
        transition.assert_called_once()

    def test_arithmetic_lookup_slot_sync_preserves_matching_copy_and_order_contract(self) -> None:
        def sync(row, lookup_slots):
            return synchronize_aggregate_arithmetic_components(
                AggregateArithmeticComponentSyncInput(
                    projection_row=row,
                    lookup_slots=lookup_slots,
                )
            ).projection_row

        marker = {"preserve": True}
        empty_row = {"operation_family": "ratio", "nested": marker}
        with patch.object(
            financial_aggregate_projection,
            "aggregate_result_operation_family",
            side_effect=RuntimeError("family must stay lazy"),
        ) as family:
            self.assertIs(sync(empty_row, []), empty_row)
        family.assert_not_called()

        lookup_slots = [{"concept": "metric", "normalized_value": 2.0}]
        inactive = {"operation_family": "lookup", "calculation_result": {"status": "ok"}}
        self.assertIs(sync(inactive, lookup_slots), inactive)

        for case_name, row in (
            ("missing", {"operation_family": "ratio", "nested": marker}),
            (
                "empty",
                {"operation_family": "ratio", "calculation_result": {}, "nested": marker},
            ),
        ):
            with self.subTest(falsy_calculation_result=case_name):
                result = sync(row, lookup_slots)
                self.assertIsNot(result, row)
                self.assertEqual(result, row)
                self.assertEqual("calculation_result" in result, case_name == "empty")
                if case_name == "empty":
                    self.assertIs(result["calculation_result"], row["calculation_result"])
                self.assertIs(result["nested"], marker)

        first = {"concept": "metric", "label": "first", "raw_value": "1"}
        second = {"concept": "metric", "label": "second", "raw_value": "2"}
        component_row = {
            "operation_family": "ratio",
            "calculation_result": {
                "status": "ok",
                "series": [{"concept": "metric", "label": "unrelated"}],
            },
        }
        with patch.object(
            financial_aggregate_projection,
            "operand_text_match",
            side_effect=RuntimeError("label match must stay lazy"),
        ) as label_match:
            selected = sync(component_row, [first, second])
        self.assertEqual(selected["calculation_result"]["series"][0]["raw_value"], "1")
        label_match.assert_not_called()

        match_events = []

        def directional_match(text, operand):
            match_events.append((text, operand["label"]))
            return text == "lookup label"

        directional_slot = {"label": "lookup label", "raw_value": "3"}
        with patch.object(
            financial_aggregate_projection,
            "operand_text_match",
            side_effect=directional_match,
        ):
            selected = sync(
                {
                    "operation_family": "ratio",
                    "calculation_result": {
                        "status": "ok",
                        "series": [{"label": "component label"}],
                    },
                },
                [directional_slot],
            )
        self.assertEqual(selected["calculation_result"]["series"][0]["raw_value"], "3")
        self.assertEqual(
            match_events,
            [
                ("component label", "lookup label"),
                ("lookup label", "component label"),
            ],
        )

        class TrackingDict(dict):
            def __init__(self, *args, fail_key="", fail_call=0, **kwargs):
                super().__init__(*args, **kwargs)
                self.calls = {}
                self.events = []
                self.fail_key = fail_key
                self.fail_call = fail_call

            def get(self, key, default=None):
                self.calls[key] = self.calls.get(key, 0) + 1
                self.events.append(key)
                if key == self.fail_key and self.calls[key] == self.fail_call:
                    raise RuntimeError(f"failed to read {key}")
                return super().get(key, default)

        component = TrackingDict(
            concept="metric",
            raw_value="old",
            raw_unit="old-unit",
            normalized_value=1.0,
            normalized_unit="OLD",
            rendered_value="old",
            source_row_id="row-old",
            source_row_ids=["row-old"],
            source_anchor="anchor-old",
            nested=marker,
        )
        replacement = TrackingDict(
            concept="metric",
            raw_value="new",
            raw_unit=None,
            normalized_value=0.0,
            normalized_unit="",
            rendered_value="new",
            source_row_id="",
            source_row_ids=[],
            source_anchor="anchor-new",
        )
        component_before = deepcopy(dict(component))
        synced = sync(
            {
                "operation_family": "ratio",
                "calculation_result": {"status": "ok", "series": [component]},
            },
            [replacement],
        )["calculation_result"]["series"][0]
        self.assertEqual(
            {key: replacement.calls.get(key, 0) for key in (
                "raw_value", "raw_unit", "normalized_value", "normalized_unit", "rendered_value",
                "source_row_id", "source_row_ids", "source_anchor",
            )},
            {
                "raw_value": 2,
                "raw_unit": 1,
                "normalized_value": 2,
                "normalized_unit": 2,
                "rendered_value": 2,
                "source_row_id": 1,
                "source_row_ids": 1,
                "source_anchor": 1,
            },
        )
        self.assertEqual(
            (synced["raw_value"], synced["raw_unit"], synced["normalized_value"], synced["normalized_unit"]),
            ("new", "old-unit", 0.0, ""),
        )
        self.assertEqual(
            (synced["source_row_id"], synced["source_row_ids"], synced["source_anchor"]),
            ("row-old", ["row-old"], "anchor-new"),
        )
        self.assertIs(synced["source_row_ids"], component["source_row_ids"])
        self.assertIs(synced["nested"], marker)
        self.assertEqual(dict(component), component_before)

        source_component = {
            "concept": "metric",
            "raw_value": "old",
            "nested": marker,
        }
        source_slot = {
            "concept": "metric",
            "raw_value": "new",
            "normalized_value": 2.0,
            "rendered_value": "new",
        }
        role_item = {**source_component, "role": "numerator"}
        group_item = {**source_component, "role": "group"}
        series_item = {**source_component, "period": "2024"}
        mutable_non_dict = ["keep"]
        row = {
            "operation_family": "ratio",
            "nested": marker,
            "calculation_result": {
                "nested": marker,
                "series": [series_item, "drop-series"],
                "answer_slots": {
                    "nested": marker,
                    "components_by_role": {"numerator": [role_item, mutable_non_dict]},
                    "components_by_group": {"numerator": [group_item, mutable_non_dict]},
                },
            },
        }
        row_before = deepcopy(row)
        projected = sync(row, [source_slot])
        result = projected["calculation_result"]
        slots = result["answer_slots"]
        self.assertIs(slots["components_by_role"]["numerator"][1], mutable_non_dict)
        self.assertIs(slots["components_by_group"]["numerator"][1], mutable_non_dict)
        self.assertEqual(result["series"], [{**series_item, **{
            "raw_value": "new",
            "normalized_value": 2.0,
            "rendered_value": "new",
            "source_row_id": None,
            "source_row_ids": None,
            "source_anchor": None,
        }}])
        for original, updated in (
            (role_item, slots["components_by_role"]["numerator"][0]),
            (group_item, slots["components_by_group"]["numerator"][0]),
            (series_item, result["series"][0]),
        ):
            self.assertIsNot(updated, original)
            self.assertEqual(updated["raw_value"], "new")
            self.assertIs(updated["nested"], marker)
        self.assertIs(projected["nested"], marker)
        self.assertIs(result["nested"], marker)
        self.assertIs(slots["nested"], marker)
        self.assertEqual(row, row_before)

        for series in ([], ["invalid", None]):
            with self.subTest(retained_series=series):
                original_series = list(series)
                row = {
                    "operation_family": "growth_rate",
                    "calculation_result": {"status": "ok", "series": original_series},
                }
                projected = sync(row, [source_slot])
                self.assertIs(projected["calculation_result"]["series"], original_series)

        for operation_family in ("difference", "sum"):
            with self.subTest(delta_family=operation_family):
                primary = {"status": "ok", "nested": marker}
                row = {
                    "operation_family": operation_family,
                    "calculation_result": {"status": "ok", "answer_slots": {"primary_value": primary}},
                }
                with patch.object(
                    financial_aggregate_projection,
                    "aggregate_result_operation_family",
                    wraps=financial_aggregate_projection.aggregate_result_operation_family,
                ) as family:
                    projected = sync(row, [source_slot])
                self.assertEqual(family.call_count, 2)
                self.assertTrue(all(item.args[0] is row for item in family.call_args_list))
                delta = projected["calculation_result"]["answer_slots"]["delta_value"]
                self.assertEqual(delta, primary)
                self.assertIsNot(delta, primary)
                self.assertIs(delta["nested"], marker)

        failing_component = TrackingDict(
            concept="metric",
            normalized_value=1.0,
            fail_key="normalized_value",
            fail_call=2,
        )
        with self.assertRaisesRegex(RuntimeError, "failed to read normalized_value"):
            sync(
                {
                    "operation_family": "ratio",
                    "calculation_result": {
                        "status": "ok",
                        "series": [{"concept": "metric"}],
                    },
                },
                [failing_component],
            )
        self.assertEqual(
            failing_component.events,
            ["label", "concept", "raw_value", "raw_unit", "normalized_value", "normalized_value"],
        )

    def test_projection_row_surface_sync_preserves_numeric_selection_and_copy_contract(self) -> None:
        def sync(row, answer, rendered_value):
            return synchronize_aggregate_projection_row_surface(
                AggregateProjectionRowSurfaceSyncInput(
                    projection_row=row,
                    answer=answer,
                    rendered_value=rendered_value,
                )
            ).projection_row

        empty_result: dict = {}
        empty_row = {
            "task_id": "task_empty",
            "calculation_result": empty_result,
            "nested": {"preserve": True},
        }
        empty_projection = sync(
            empty_row,
            "   ",
            "",
        )
        self.assertIsNot(empty_projection, empty_row)
        self.assertEqual(empty_projection["answer"], "   ")
        self.assertTrue(empty_projection["projection_surface_synced_from_final_answer"])
        self.assertIs(empty_projection["calculation_result"], empty_result)
        self.assertIs(empty_projection["nested"], empty_row["nested"])
        self.assertNotIn("rendered_value", empty_projection)

        shared_nested = {"preserve": "nested"}
        ratio_row = {
            "operation_family": "ratio",
            "metric_label": "ratio metric",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "primary_value": {
                        "status": "ok",
                        "period": "2024",
                        "nested": shared_nested,
                    }
                },
                "untouched": shared_nested,
            },
        }
        ratio_before = deepcopy(ratio_row)
        ratio_projection = sync(
            ratio_row,
            "5.0% and 7.0%",
            "5.0%",
        )
        ratio_result = ratio_projection["calculation_result"]
        self.assertEqual(ratio_result["result_value"], 5.0)
        self.assertEqual(ratio_result["formatted_result"], "5.0% and 7.0%")
        self.assertEqual(ratio_result["answer_slots"]["primary_value"]["rendered_value"], "5.0%")
        self.assertIs(ratio_result["untouched"], shared_nested)
        self.assertIs(
            ratio_result["answer_slots"]["primary_value"]["nested"],
            shared_nested,
        )
        self.assertEqual(ratio_row, ratio_before)

        difference_row = {
            "operation_family": "difference",
            "metric_label": "difference metric",
            "calculation_result": {"status": "ok", "answer_slots": {}},
        }
        difference_projection = sync(
            difference_row,
            "5.0% and 7.0%",
            "7.0%",
        )
        self.assertEqual(difference_projection["calculation_result"]["result_value"], 7.0)
        self.assertEqual(
            difference_projection["calculation_result"]["answer_slots"]["primary_value"]["rendered_value"],
            "7.0%",
        )

        ratio_without_primary_slots: dict = {}
        ratio_without_primary = {
            "operation_family": "ratio",
            "calculation_result": {
                "status": "ok",
                "answer_slots": ratio_without_primary_slots,
            },
        }
        ratio_without_primary_projection = sync(
            ratio_without_primary,
            "8.0%",
            "8.0%",
        )
        self.assertIs(
            ratio_without_primary_projection["calculation_result"]["answer_slots"],
            ratio_without_primary_slots,
        )
        self.assertNotIn(
            "primary_value",
            ratio_without_primary_projection["calculation_result"]["answer_slots"],
        )

        lookup_row = {
            "operation_family": "lookup",
            "metric_label": "lookup metric",
            "calculation_result": {
                "status": "ok",
                "series": [
                    {"period": "2024", "nested": shared_nested},
                    "drop-me",
                ],
                "derived_metrics": {"keep": shared_nested},
                "answer_slots": {
                    "primary_value": {"period": "2024", "nested": shared_nested},
                    "components_by_role": {
                        "primary_value": [
                            {"period": "2024", "nested": shared_nested},
                            "drop-me",
                        ]
                    },
                    "components_by_group": {
                        "primary": [{"period": "2024", "nested": shared_nested}]
                    },
                },
            },
        }
        lookup_before = deepcopy(lookup_row)
        lookup_projection = sync(
            lookup_row,
            "12.0%",
            "12.0%",
        )
        lookup_result = lookup_projection["calculation_result"]
        lookup_slots = lookup_result["answer_slots"]
        self.assertEqual(lookup_result["current_value"], 12.0)
        self.assertEqual(len(lookup_result["series"]), 1)
        self.assertEqual(lookup_result["series"][0]["normalized_value"], 12.0)
        self.assertEqual(
            lookup_slots["components_by_role"]["primary_value"][0]["normalized_value"],
            12.0,
        )
        self.assertEqual(
            lookup_slots["components_by_group"]["primary"][0]["normalized_value"],
            12.0,
        )
        self.assertEqual(lookup_result["derived_metrics"]["formula_result_value"], 12.0)
        self.assertIs(lookup_result["derived_metrics"]["keep"], shared_nested)
        self.assertEqual(lookup_row, lookup_before)

        no_numeric_result = {"status": "ok", "rendered_value": "old", "nested": shared_nested}
        no_numeric_row = {"operation_family": "difference", "calculation_result": no_numeric_result}
        no_numeric_projection = sync(no_numeric_row, "no numeric surface", "")
        self.assertEqual(no_numeric_projection["calculation_result"]["formatted_result"], "no numeric surface")
        self.assertEqual(no_numeric_projection["calculation_result"]["rendered_value"], "old")
        self.assertNotIn("result_value", no_numeric_projection["calculation_result"])
        self.assertIs(no_numeric_projection["calculation_result"]["nested"], shared_nested)
        self.assertEqual(no_numeric_row["calculation_result"], no_numeric_result)

        missing_result_row = {"task_id": "task_missing", "nested": shared_nested}
        missing_result_projection = sync(missing_result_row, "raw answer", "rendered")
        self.assertNotIn("calculation_result", missing_result_projection)
        self.assertEqual(missing_result_projection["rendered_value"], "rendered")
        self.assertIs(missing_result_projection["nested"], shared_nested)

        empty_rendered_row = {
            "operation_family": "ratio",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "old result",
                "answer_slots": {"primary_value": {"rendered_value": "old primary"}},
            },
        }
        empty_rendered_projection = sync(empty_rendered_row, "8.0%", "")
        self.assertEqual(empty_rendered_projection["calculation_result"]["rendered_value"], "old result")
        self.assertEqual(
            empty_rendered_projection["calculation_result"]["answer_slots"]["primary_value"]["rendered_value"],
            "",
        )

        empty_derived: dict = {}
        lookup_empty_row = {
            "operation_family": "lookup",
            "metric_label": "lookup fallback",
            "calculation_result": {
                "status": "ok",
                "series": [],
                "derived_metrics": empty_derived,
                "answer_slots": {
                    "primary_value": {"period": "2025"},
                    "components_by_role": {"primary_value": []},
                    "components_by_group": {"primary": [], "primary_value": []},
                },
            },
        }
        lookup_empty_before = deepcopy(lookup_empty_row)
        lookup_empty_projection = sync(lookup_empty_row, "14.0%", "14.0%")
        lookup_empty_result = lookup_empty_projection["calculation_result"]
        lookup_empty_slots = lookup_empty_result["answer_slots"]
        self.assertEqual(lookup_empty_result["current_period"], "2025")
        self.assertEqual(lookup_empty_result["series"][0]["normalized_value"], 14.0)
        self.assertEqual(
            lookup_empty_slots["components_by_role"]["primary_value"][0]["normalized_value"],
            14.0,
        )
        self.assertEqual(
            lookup_empty_slots["components_by_group"]["primary"][0]["normalized_value"],
            14.0,
        )
        self.assertEqual(
            lookup_empty_slots["components_by_group"]["primary_value"][0]["normalized_value"],
            14.0,
        )
        self.assertIs(lookup_empty_result["derived_metrics"], empty_derived)
        self.assertEqual(lookup_empty_row, lookup_empty_before)

        class TrackingRow(dict):
            def __init__(self, *args, fail_operation_read=0, **kwargs):
                super().__init__(*args, **kwargs)
                self.accessed = []
                self.operation_reads = 0
                self.fail_operation_read = fail_operation_read

            def get(self, key, default=None):
                self.accessed.append(key)
                if key == "operation_family":
                    self.operation_reads += 1
                    if self.operation_reads == self.fail_operation_read:
                        raise RuntimeError("operation access failed")
                return super().get(key, default)

        tracked = TrackingRow(
            operation_family="lookup",
            metric_label="tracked lookup",
            calculation_result={"status": "ok", "answer_slots": {"primary_value": {}}},
        )
        sync(tracked, "15.0%", "15.0%")
        self.assertEqual(
            tracked.accessed,
            [
                "calculation_result",
                "calculation_result",
                "operation_family",
                "calculation_result",
                "operation_family",
                "metric_label",
            ],
        )

        failing = TrackingRow(
            operation_family="lookup",
            metric_label="unreached",
            calculation_result={"status": "ok", "answer_slots": {"primary_value": {}}},
            fail_operation_read=2,
        )
        failing_before = deepcopy(dict(failing))
        with self.assertRaisesRegex(RuntimeError, "operation access failed"):
            sync(failing, "16.0%", "16.0%")
        self.assertEqual(
            failing.accessed,
            ["calculation_result", "calculation_result", "operation_family", "calculation_result", "operation_family"],
        )
        self.assertEqual(dict(failing), failing_before)

    def test_runtime_ratio_absolute_magnitude_projection_contract(self) -> None:
        nested_marker = {"preserve": True}

        def prepared(value, *, result_unit=None, normalized_unit=None, raw_unit=None):
            original_primary = {"normalized_value": value, "rendered_value": "old"}
            original_slots = {"primary_value": original_primary}
            calculation_result = {
                "result_value": value,
                "rendered_value": "old",
                "answer_slots": original_slots,
                "metadata": nested_marker,
            }
            primary_value = {**original_primary, "metadata": nested_marker}
            if result_unit is not None:
                calculation_result["result_unit"] = result_unit
            if normalized_unit is not None:
                primary_value["normalized_unit"] = normalized_unit
            if raw_unit is not None:
                primary_value["raw_unit"] = raw_unit
            return calculation_result, dict(original_slots), primary_value, original_slots, original_primary

        with patch.object(
            financial_aggregate_projection.calculation_rendering,
            "format_calculation_value",
        ) as formatter:
            for value in (None, 4.0, float("nan"), -0.0, "not-a-number", {}):
                with self.subTest(no_projection=value):
                    result, slots, primary, original_slots, original_primary = prepared(value)
                    projection = project_runtime_ratio_absolute_magnitude(
                        RuntimeRatioAbsoluteMagnitudeProjectionInput(result, slots, primary)
                    )
                    self.assertIs(projection.calculation_result, result)
                    self.assertIs(result["answer_slots"], original_slots)
                    self.assertIs(result["answer_slots"]["primary_value"], original_primary)
                    self.assertIs(slots["primary_value"], original_primary)
                    self.assertIs(primary["metadata"], nested_marker)
                    if isinstance(value, float) and math.isnan(value):
                        self.assertTrue(math.isnan(result["result_value"]))
                    elif value == 0:
                        self.assertEqual(math.copysign(1.0, result["result_value"]), -1.0)
                    else:
                        self.assertEqual(result["result_value"], value)
            formatter.assert_not_called()

        class CountingNegative:
            def __init__(self):
                self.float_calls = 0

            def __float__(self):
                self.float_calls += 1
                return -3.5

        for units, expected_args in (
            ({}, (3.5, "%", "PERCENT")),
            (
                {
                    "result_unit": "%p",
                    "normalized_unit": "PERCENT_POINT",
                    "raw_unit": "percentage points",
                },
                (3.5, "%p", "PERCENT_POINT"),
            ),
        ):
            with self.subTest(units=units):
                value = CountingNegative()
                result, slots, primary, _, _ = prepared(value, **units)
                with patch.object(
                    financial_aggregate_projection.calculation_rendering,
                    "format_calculation_value",
                    return_value="3.5 rendered",
                ) as formatter:
                    projection = project_runtime_ratio_absolute_magnitude(
                        RuntimeRatioAbsoluteMagnitudeProjectionInput(result, slots, primary)
                    )
                self.assertIs(projection.calculation_result, result)
                self.assertEqual(value.float_calls, 2)
                formatter.assert_called_once_with(*expected_args)
                self.assertEqual(result["result_value"], 3.5)
                self.assertEqual(result["rendered_value"], "3.5 rendered")
                self.assertIs(result["answer_slots"], slots)
                self.assertIs(slots["primary_value"], primary)
                self.assertEqual(primary["normalized_value"], 3.5)
                self.assertEqual(primary["normalized_unit"], units.get("normalized_unit", "PERCENT"))
                self.assertEqual(primary["raw_unit"], units.get("raw_unit", "%"))
                self.assertIs(primary["metadata"], nested_marker)

        for exception_type in (TypeError, ValueError):
            with self.subTest(formatter_exception=exception_type.__name__):
                result, slots, primary, original_slots, original_primary = prepared(-3.5)
                with patch.object(
                    financial_aggregate_projection.calculation_rendering,
                    "format_calculation_value",
                    side_effect=exception_type("cannot format"),
                ):
                    projection = project_runtime_ratio_absolute_magnitude(
                        RuntimeRatioAbsoluteMagnitudeProjectionInput(result, slots, primary)
                    )
                self.assertIs(projection.calculation_result, result)
                self.assertEqual(result["result_value"], 3.5)
                self.assertEqual(result["rendered_value"], "old")
                self.assertIs(result["answer_slots"], original_slots)
                self.assertIs(slots["primary_value"], original_primary)
                self.assertEqual(primary["normalized_value"], 3.5)
                self.assertEqual(primary["normalized_unit"], "PERCENT")
                self.assertEqual(primary["raw_unit"], "%")

        result, slots, primary, original_slots, _ = prepared(-3.5)
        with patch.object(
            financial_aggregate_projection.calculation_rendering,
            "format_calculation_value",
            side_effect=RuntimeError("formatter unavailable"),
        ):
            with self.assertRaisesRegex(RuntimeError, "formatter unavailable"):
                project_runtime_ratio_absolute_magnitude(
                    RuntimeRatioAbsoluteMagnitudeProjectionInput(result, slots, primary)
                )
        self.assertEqual(result["result_value"], 3.5)
        self.assertIs(result["answer_slots"], original_slots)

    def test_semantic_plan_artifact_update_attaches_pending_calculation_tasks(self) -> None:
        updated = semantic_plan_artifact_update(
            tasks=[],
            artifacts=[{"artifact_id": "existing"}],
            artifact_task_id="task_ratio",
            semantic_plan={"status": "ok", "tasks": [{"task_id": "task_ratio"}]},
            retrieval_queries=["q1", "q2"],
            summary="planned 1 numeric task(s)",
            payload_extra={"planner_feedback": "feedback"},
            calculation_tasks=[
                {
                    "task_id": "task_ratio",
                    "metric_label": "ratio task",
                    "metric_family": "ratio",
                    "query": "query",
                    "constraints": {"period": "2023"},
                }
            ],
        )

        self.assertEqual(updated["artifact_id"], "semantic_plan:002")
        self.assertEqual(updated["artifacts"][-1]["kind"], "semantic_plan")
        self.assertEqual(updated["artifacts"][-1]["payload"]["retrieval_queries"], ["q1", "q2"])
        self.assertEqual(updated["artifacts"][-1]["payload"]["planner_feedback"], "feedback")
        self.assertEqual(updated["tasks"][0]["task_id"], "task_ratio")
        self.assertEqual(updated["tasks"][0]["status"], "pending")
        self.assertEqual(updated["tasks"][0]["artifact_ids"], ["semantic_plan:002"])

    def test_reconciliation_result_artifact_update_attaches_reconciliation_task(self) -> None:
        updated = reconciliation_result_artifact_update(
            tasks=[],
            artifacts=[],
            active_subtask={
                "task_id": "task_ratio",
                "metric_label": "ratio task",
                "metric_family": "ratio",
                "query": "query",
                "constraints": {"period": "2023"},
            },
            reconciliation_result={"status": "retry_retrieval", "matched_operands": []},
            summary="reconciliation=retry_retrieval",
            evidence_refs=["ev1", ""],
        )

        self.assertEqual(updated["artifact_id"], "reconcile:task_ratio:001")
        self.assertEqual(updated["artifacts"][0]["kind"], "reconciliation_result")
        self.assertEqual(updated["artifacts"][0]["status"], "retry_retrieval")
        self.assertEqual(updated["artifacts"][0]["evidence_refs"], ["ev1"])
        self.assertEqual(updated["tasks"][0]["kind"], "reconciliation")
        self.assertEqual(updated["tasks"][0]["status"], "partial")
        self.assertEqual(updated["tasks"][0]["constraints"], {"period": "2023"})

    def test_supersede_task_with_aggregate_result_adds_replacement_artifact(self) -> None:
        updated = supersede_task_with_aggregate_result(
            tasks=[
                {
                    "task_id": "task_ratio",
                    "kind": "calculation",
                    "label": "ratio task",
                    "status": "completed",
                    "query": "query",
                    "metric_family": "ratio",
                    "constraints": {"period": "2023"},
                    "artifact_ids": ["result:task_ratio:001"],
                    "notes": ["existing"],
                }
            ],
            artifacts=[{"artifact_id": "result:task_ratio:001", "task_id": "task_ratio", "kind": "calculation_result"}],
            task={"task_id": "task_ratio", "kind": "calculation", "label": "ratio task", "query": "query", "metric_family": "ratio", "constraints": {"period": "2023"}, "notes": ["existing"]},
            aggregate_artifact_id="aggregate:002",
            replacement_summary="aggregate replacement",
            replacement_payload={"replacement_summary": "aggregate replacement"},
        )

        self.assertEqual(updated["artifact_id"], "supersession:task_ratio:002")
        self.assertEqual(updated["artifacts"][-1]["kind"], "calculation_result")
        self.assertEqual(updated["artifacts"][-1]["status"], "superseded_by_aggregate_result")
        self.assertEqual(updated["tasks"][0]["status"], "superseded")
        self.assertEqual(
            updated["tasks"][0]["constraints"]["superseded_by_artifact_id"],
            "aggregate:002",
        )
        self.assertEqual(updated["tasks"][0]["artifact_ids"], ["result:task_ratio:001", "supersession:task_ratio:002"])
        self.assertEqual(updated["tasks"][0]["notes"], ["existing", "superseded_by_aggregate_result"])

    def test_supersede_task_with_aggregate_result_can_mark_without_new_artifact(self) -> None:
        updated = supersede_task_with_aggregate_result(
            tasks=[],
            artifacts=[],
            task={"task_id": "task_pending", "kind": "calculation", "label": "pending task"},
            aggregate_artifact_id="aggregate:001",
        )

        self.assertEqual(updated["artifact_id"], "")
        self.assertEqual(updated["artifacts"], [])
        self.assertEqual(updated["tasks"][0]["task_id"], "task_pending")
        self.assertEqual(updated["tasks"][0]["status"], "superseded")
        self.assertEqual(updated["tasks"][0]["artifact_ids"], [])

    def test_aggregate_answer_artifact_update_attaches_synthesis_task(self) -> None:
        updated = aggregate_answer_artifact_update(
            tasks=[],
            artifacts=[{"artifact_id": "result:task_a:001"}],
            final_answer="final answer",
            payload={"final_answer": "final answer"},
            evidence_refs=["ev1", ""],
            planner_feedback="",
            query="query",
        )

        self.assertEqual(updated["artifact_id"], "aggregate:002")
        self.assertEqual(updated["artifacts"][-1]["artifact_id"], "aggregate:002")
        self.assertEqual(updated["artifacts"][-1]["kind"], "aggregated_answer")
        self.assertEqual(updated["artifacts"][-1]["summary"], "final answer")
        self.assertEqual(updated["artifacts"][-1]["evidence_refs"], ["ev1"])
        self.assertEqual(updated["tasks"][0]["task_id"], "aggregate")
        self.assertEqual(updated["tasks"][0]["kind"], "synthesis")
        self.assertEqual(updated["tasks"][0]["status"], "completed")
        self.assertEqual(updated["tasks"][0]["artifact_ids"], ["aggregate:002"])

    def test_aggregate_answer_artifact_update_marks_feedback_as_partial(self) -> None:
        updated = aggregate_answer_artifact_update(
            tasks=[],
            artifacts=[],
            final_answer="needs review",
            payload={},
            evidence_refs=[],
            planner_feedback="missing detail",
            query="query",
        )

        self.assertEqual(updated["artifacts"][0]["artifact_id"], "aggregate:001")
        self.assertEqual(updated["tasks"][0]["status"], "partial")

    def test_aggregate_artifact_projection_payload_sync_preserves_copy_and_access_contract(self) -> None:
        def sync(artifacts, *, artifact_id="aggregate:target", final_answer="final", projection=None):
            return synchronize_aggregate_artifact_projection_payload(
                AggregateArtifactProjectionPayloadSyncInput(
                    artifacts=artifacts,
                    artifact_id=artifact_id,
                    final_answer=final_answer,
                    aggregate_projection={} if projection is None else projection,
                )
            ).artifacts

        empty_artifacts = []
        empty_result = sync(empty_artifacts)
        self.assertEqual(empty_result, [])
        self.assertIsNot(empty_result, empty_artifacts)

        preserved_payload = {"nested": {"preserve": True}}
        no_match = [{"artifact_id": " aggregate:target ", "payload": preserved_payload}]

        class LazyProjection(dict):
            def get(self, key, default=None):
                raise RuntimeError(f"projection must stay lazy: {key}")

        no_match_result = sync(no_match, projection=LazyProjection())
        self.assertEqual(no_match_result, no_match)
        self.assertIsNot(no_match_result, no_match)
        self.assertIsNot(no_match_result[0], no_match[0])
        self.assertIs(no_match_result[0]["payload"], preserved_payload)

        payload_nested = {"payload": "alias"}
        artifact_nested = {"artifact": "alias"}
        other_payload = {"other": "alias"}
        duplicate_payload = {"duplicate": "untouched"}
        operand_nested = {"operand": "alias"}
        plan_nested = {"plan": "alias"}
        result_nested = {"result": "alias"}
        operands = [{"operand_id": "op_1", "nested": operand_nested}]
        plan = {"operation": "ratio", "nested": plan_nested}
        calculation_result = {"status": "ok", "nested": result_nested}
        projection = {
            "calculation_operands": operands,
            "calculation_plan": plan,
            "calculation_result": calculation_result,
        }
        target_payload = {
            "keep": payload_nested,
            "final_answer": "stale",
            "calculation_operands": ["stale"],
            "calculation_plan": {"stale": True},
            "calculation_result": {"stale": True},
        }
        artifacts = [
            {"artifact_id": "aggregate:other", "payload": other_payload},
            {
                "artifact_id": "aggregate:target",
                "summary": "stale",
                "payload": target_payload,
                "metadata": artifact_nested,
            },
            {"artifact_id": "aggregate:target", "payload": duplicate_payload},
        ]
        artifacts_before = deepcopy(artifacts)
        projection_before = deepcopy(projection)
        final_answer = "answer:" + ("x" * 205)

        updated = sync(artifacts, final_answer=final_answer, projection=projection)

        self.assertIsNot(updated, artifacts)
        self.assertTrue(all(current is not original for current, original in zip(updated, artifacts)))
        self.assertIs(updated[0]["payload"], other_payload)
        self.assertIs(updated[2]["payload"], duplicate_payload)
        target = updated[1]
        payload = target["payload"]
        self.assertEqual(target["summary"], final_answer[:200])
        self.assertIs(target["metadata"], artifact_nested)
        self.assertIsNot(payload, target_payload)
        self.assertIs(payload["keep"], payload_nested)
        self.assertEqual(payload["final_answer"], final_answer)
        self.assertEqual(payload["calculation_operands"], operands)
        self.assertIsNot(payload["calculation_operands"], operands)
        self.assertIs(payload["calculation_operands"][0], operands[0])
        self.assertEqual(payload["calculation_plan"], plan)
        self.assertIsNot(payload["calculation_plan"], plan)
        self.assertIs(payload["calculation_plan"]["nested"], plan_nested)
        self.assertEqual(payload["calculation_result"], calculation_result)
        self.assertIsNot(payload["calculation_result"], calculation_result)
        self.assertIs(payload["calculation_result"]["nested"], result_nested)
        self.assertEqual(artifacts, artifacts_before)
        self.assertEqual(projection, projection_before)

        falsy = sync(
            [{"artifact_id": "aggregate:target", "payload": []}],
            projection={
                "calculation_operands": None,
                "calculation_plan": "",
                "calculation_result": 0,
            },
        )[0]["payload"]
        self.assertEqual(
            falsy,
            {
                "final_answer": "final",
                "calculation_operands": [],
                "calculation_plan": {},
                "calculation_result": {},
            },
        )

        class TrackingProjection(dict):
            def __init__(self):
                super().__init__(calculation_operands=[])
                self.events = []

            def get(self, key, default=None):
                self.events.append(key)
                if key == "calculation_plan":
                    raise RuntimeError("plan access failed")
                return super().get(key, default)

        tracking_projection = TrackingProjection()
        with self.assertRaisesRegex(RuntimeError, "plan access failed"):
            sync([{"artifact_id": "aggregate:target"}], projection=tracking_projection)
        self.assertEqual(
            tracking_projection.events,
            ["calculation_operands", "calculation_plan"],
        )

        class FailingArtifact:
            def __iter__(self):
                raise RuntimeError("late artifact copy failed")

        with self.assertRaisesRegex(RuntimeError, "late artifact copy failed"):
            sync([{"artifact_id": "aggregate:target"}, FailingArtifact()])

    def test_reflection_report_artifact_update_attaches_reflection_task(self) -> None:
        updated = reflection_report_artifact_update(
            tasks=[],
            artifacts=[],
            reflection_task_id="reflection:task_a:001",
            target_task_id="task_a",
            query="query",
            metric_family="ratio",
            reflection_report={
                "outcome": "retry_prepared",
                "action_taken": "retrieve_more",
                "target_task_ids": ["task_a"],
                "target_artifact_ids": ["plan:task_a:001"],
            },
            reflection_action={"action_type": "retrieve_more"},
            reflection_request={"reason": "missing operands"},
            reflection_plan={"status": "retry"},
            retry_strategy="fallback",
        )

        self.assertEqual(updated["artifact_id"], "reflection:task_a:001:report")
        self.assertEqual(updated["artifacts"][0]["kind"], "reflection_report")
        self.assertEqual(updated["artifacts"][0]["summary"], "reflection=retrieve_more")
        self.assertEqual(updated["artifacts"][0]["payload"]["reflection_request"]["reason"], "missing operands")
        self.assertEqual(updated["tasks"][0]["task_id"], "reflection:task_a:001")
        self.assertEqual(updated["tasks"][0]["kind"], "reflection")
        self.assertEqual(updated["tasks"][0]["status"], "completed")
        self.assertEqual(updated["tasks"][0]["constraints"]["target_task_ids"], ["task_a"])

    def test_calculation_plan_artifact_update_appends_and_attaches_calculation_task(self) -> None:
        updated = calculation_plan_artifact_update(
            tasks=[
                {
                    "task_id": "task_ratio",
                    "kind": "calculation",
                    "label": "old label",
                    "status": "pending",
                    "query": "old query",
                    "metric_family": "old_metric",
                    "constraints": {},
                    "artifact_ids": ["operands:task_ratio:001"],
                    "notes": [],
                }
            ],
            artifacts=[{"artifact_id": "operands:task_ratio:001", "task_id": "task_ratio", "kind": "operand_set"}],
            task_id="task_ratio",
            task_label="ratio task",
            query="new query",
            metric_family="ratio",
            calculation_plan={"status": "partial", "mode": "formula", "operation": "divide"},
        )

        self.assertEqual(updated["artifacts"][-1]["artifact_id"], "plan:task_ratio:002")
        self.assertEqual(updated["artifacts"][-1]["kind"], "calculation_plan")
        self.assertEqual(updated["artifacts"][-1]["status"], "partial")
        self.assertEqual(updated["artifacts"][-1]["summary"], "mode=formula op=divide")
        self.assertEqual(updated["artifacts"][-1]["payload"]["calculation_plan"]["operation"], "divide")
        self.assertEqual(updated["tasks"][0]["artifact_ids"], ["operands:task_ratio:001", "plan:task_ratio:002"])
        self.assertEqual(updated["tasks"][0]["status"], "in_progress")
        self.assertEqual(updated["tasks"][0]["query"], "new query")
        self.assertEqual(updated["tasks"][0]["metric_family"], "ratio")

    def test_calculation_plan_artifact_update_defaults_empty_task_id(self) -> None:
        updated = calculation_plan_artifact_update(
            tasks=[],
            artifacts=[],
            task_id="",
            task_label="",
            query="query",
            metric_family="",
            calculation_plan={},
        )

        self.assertEqual(updated["artifacts"][0]["artifact_id"], "plan:calc:001")
        self.assertEqual(updated["artifacts"][0]["task_id"], "calc")
        self.assertEqual(updated["artifacts"][0]["status"], "ok")
        self.assertEqual(updated["tasks"][0]["task_id"], "calc")
        self.assertEqual(updated["tasks"][0]["label"], "calc")

    def test_calculation_result_artifact_update_attaches_completed_calculation_task(self) -> None:
        updated = calculation_result_artifact_update(
            tasks=[],
            artifacts=[{"artifact_id": "plan:task_ratio:001", "task_id": "task_ratio", "kind": "calculation_plan"}],
            task_id="task_ratio",
            task_label="ratio task",
            query="query",
            metric_family="ratio",
            calculation_result={"status": "ok", "rendered_value": "12.3%"},
            evidence_refs=["ev1", ""],
        )

        self.assertEqual(updated["artifact_id"], "result:task_ratio:002")
        self.assertEqual(updated["artifacts"][-1]["kind"], "calculation_result")
        self.assertEqual(updated["artifacts"][-1]["summary"], "12.3%")
        self.assertEqual(updated["artifacts"][-1]["payload"]["calculation_result"]["rendered_value"], "12.3%")
        self.assertEqual(updated["artifacts"][-1]["evidence_refs"], ["ev1"])
        self.assertEqual(updated["tasks"][0]["status"], "completed")
        self.assertEqual(updated["tasks"][0]["artifact_ids"], ["result:task_ratio:002"])

    def test_calculation_result_artifact_update_marks_non_ok_as_failed(self) -> None:
        updated = calculation_result_artifact_update(
            tasks=[],
            artifacts=[],
            task_id="task_ratio",
            task_label="ratio task",
            query="query",
            metric_family="ratio",
            calculation_result={"status": "insufficient_operands", "formatted_result": "missing"},
            evidence_refs=[],
        )

        self.assertEqual(updated["artifacts"][0]["artifact_id"], "result:task_ratio:001")
        self.assertEqual(updated["artifacts"][0]["summary"], "missing")
        self.assertEqual(updated["tasks"][0]["status"], "failed")

    def test_operand_set_artifact_update_appends_and_attaches_calculation_task(self) -> None:
        updated = operand_set_artifact_update(
            tasks=[
                {
                    "task_id": "task_ratio",
                    "kind": "calculation",
                    "label": "old label",
                    "status": "pending",
                    "query": "old query",
                    "metric_family": "old_metric",
                    "constraints": {},
                    "artifact_ids": ["plan:task_ratio:001"],
                    "notes": [],
                }
            ],
            artifacts=[{"artifact_id": "plan:task_ratio:001", "task_id": "task_ratio", "kind": "calculation_plan"}],
            task_id="task_ratio",
            task_label="ratio task",
            query="new query",
            metric_family="ratio",
            operand_rows=[
                {"operand_id": "a", "evidence_id": "ev1"},
                {"operand_id": "b", "evidence_id": ""},
            ],
            status="ok",
            summary="2 operands",
            payload={"calculation_operands": [{"operand_id": "a"}, {"operand_id": "b"}]},
        )

        self.assertEqual(updated["artifacts"][-1]["artifact_id"], "operands:task_ratio:002")
        self.assertEqual(updated["artifacts"][-1]["kind"], "operand_set")
        self.assertEqual(updated["artifacts"][-1]["evidence_refs"], ["ev1"])
        self.assertEqual(updated["tasks"][0]["artifact_ids"], ["plan:task_ratio:001", "operands:task_ratio:002"])
        self.assertEqual(updated["tasks"][0]["status"], "in_progress")
        self.assertEqual(updated["tasks"][0]["query"], "new query")
        self.assertEqual(updated["tasks"][0]["metric_family"], "ratio")

    def test_operand_set_artifact_update_uses_explicit_evidence_refs(self) -> None:
        updated = operand_set_artifact_update(
            tasks=[],
            artifacts=[],
            task_id="",
            task_label="",
            query="query",
            metric_family="",
            operand_rows=[{"evidence_id": "derived"}],
            status="partial",
            summary="summary",
            payload={},
            evidence_refs=["explicit", ""],
        )

        self.assertEqual(updated["artifacts"][0]["artifact_id"], "operands:calc:001")
        self.assertEqual(updated["artifacts"][0]["task_id"], "calc")
        self.assertEqual(updated["artifacts"][0]["evidence_refs"], ["explicit"])
        self.assertEqual(updated["tasks"][0]["task_id"], "calc")
        self.assertEqual(updated["tasks"][0]["label"], "calc")

    def test_aggregate_synthesis_state_updates_selected_fields(self) -> None:
        state = _AggregateSynthesisState(
            [{"task_id": "old"}],
            {"old": True},
            "old answer",
            ["old_ev"],
        )

        updated = state.with_updates(
            aggregate_projection={"new": True},
            final_answer="",
            selected_claim_ids=[],
        )

        self.assertEqual(updated.ordered_results, [{"task_id": "old"}])
        self.assertEqual(updated.aggregate_projection, {"new": True})
        self.assertEqual(updated.final_answer, "")
        self.assertEqual(updated.selected_claim_ids, [])

    def test_aggregate_mutable_state_replaces_synthesis_state_without_touching_evidence(self) -> None:
        evidence_items = [{"evidence_id": "ev1"}]
        mutable_state = _AggregateMutableState(
            _AggregateSynthesisState([], {"old": True}, "old", ["old_ev"]),
            evidence_items,
        )
        replacement = _AggregateSynthesisState(
            [{"task_id": "task_a"}],
            {"new": True},
            "new",
            ["new_ev"],
        )

        updated = mutable_state.with_synthesis_state(replacement)

        self.assertEqual(updated.synthesis_state, replacement)
        self.assertIs(updated.evidence_items, evidence_items)

    def test_aggregate_projection_provenance_filter_preserves_copy_and_order_contract(self) -> None:
        class _TrackingProjection(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.get_calls = 0

            def get(self, key, default=None):
                self.get_calls += 1
                return super().get(key, default)

        class _ExplodingEvidenceId:
            def __str__(self):
                raise RuntimeError("kept evidence unavailable")

        def _filter(projection, kept_evidence_ids):
            return filter_aggregate_projection_provenance(
                AggregateProjectionProvenanceFilterInput(
                    aggregate_projection=projection,
                    kept_evidence_ids=kept_evidence_ids,
                )
            ).aggregate_projection

        marker = {"preserve": True}
        empty_projection = _TrackingProjection(calculation_result={"marker": marker})

        empty_result = _filter(empty_projection, [" ", ""])

        self.assertIs(empty_result, empty_projection)
        self.assertEqual(empty_projection.get_calls, 0)
        with self.assertRaisesRegex(RuntimeError, "kept evidence unavailable"):
            _filter(empty_projection, [_ExplodingEvidenceId()])
        self.assertEqual(empty_projection.get_calls, 0)

        valid_subtask = {
            "task_id": "task_valid",
            "source_evidence_ids": ["recon::drop", "plain_subtask", "ev_keep"],
            "source_row_ids": ["ev_drop", "recon::keep", "plain_subtask"],
            "marker": marker,
        }
        projection = {
            "marker": marker,
            "calculation_result": {
                "source_evidence_ids": [
                    " ev_keep ",
                    ("plain", "ev_drop"),
                    "ev_keep",
                    "operand::prior",
                    "recon::keep",
                    "recon::drop",
                ],
                "source_row_ids": ["ev_drop", "plain_row", "recon::keep", "ev_keep"],
                "derived_metrics": {
                    "aggregate_source_evidence_ids": ["recon::drop", "plain_derived", "ev_keep"],
                    "aggregate_source_row_ids": ["ev_drop", "recon::keep", "plain_derived"],
                    "marker": marker,
                },
                "answer_slots": {
                    "source_row_ids": ["ev_drop", "plain_slot", "recon::keep"],
                    "subtask_results": ["discard", valid_subtask],
                    "marker": marker,
                },
                "marker": marker,
            },
        }
        projection_snapshot = deepcopy(projection)

        kept_evidence_ids = [" ev_keep ", "recon::keep", "ev_keep"]
        filtered = _filter(projection, kept_evidence_ids)

        result = filtered["calculation_result"]
        slots = result["answer_slots"]
        filtered_subtask = slots["subtask_results"][0]
        self.assertEqual(
            (
                result["source_evidence_ids"],
                result["source_row_ids"],
                result["derived_metrics"]["aggregate_source_evidence_ids"],
                result["derived_metrics"]["aggregate_source_row_ids"],
                slots["source_row_ids"],
                filtered_subtask["source_evidence_ids"],
                filtered_subtask["source_row_ids"],
            ),
            (
                ["ev_keep", "plain", "operand::prior", "recon::keep"],
                ["plain_row", "recon::keep", "ev_keep"],
                ["plain_derived", "ev_keep"],
                ["recon::keep", "plain_derived"],
                ["plain_slot", "recon::keep"],
                ["plain_subtask", "ev_keep"],
                ["recon::keep", "plain_subtask"],
            ),
        )
        self.assertEqual([row["task_id"] for row in slots["subtask_results"]], ["task_valid"])
        for selected, original in (
            (filtered, projection),
            (result, projection["calculation_result"]),
            (result["derived_metrics"], projection["calculation_result"]["derived_metrics"]),
            (slots, projection["calculation_result"]["answer_slots"]),
            (filtered_subtask, valid_subtask),
        ):
            self.assertIsNot(selected, original)
        for retained in (
            filtered["marker"],
            result["marker"],
            result["derived_metrics"]["marker"],
            slots["marker"],
            filtered_subtask["marker"],
        ):
            self.assertIs(retained, marker)
        self.assertEqual(projection, projection_snapshot)
        self.assertEqual(kept_evidence_ids, [" ev_keep ", "recon::keep", "ev_keep"])

        invalid_subtasks = ["invalid", None]
        conditional_projection = {
            "calculation_result": {
                "answer_slots": {
                    "source_row_ids": ["plain"],
                    "subtask_results": invalid_subtasks,
                }
            }
        }
        conditional_result = _filter(conditional_projection, ["ev_keep"])
        self.assertIs(
            conditional_result["calculation_result"]["answer_slots"]["subtask_results"],
            invalid_subtasks,
        )
        falsy_slots = {}
        falsy_projection = {"calculation_result": {"answer_slots": falsy_slots}}
        falsy_result = _filter(falsy_projection, ["ev_keep"])
        falsy_calculation_result = falsy_result["calculation_result"]
        self.assertIs(falsy_calculation_result["answer_slots"], falsy_slots)
        self.assertEqual(
            falsy_calculation_result,
            {
                "answer_slots": {},
                "source_evidence_ids": [],
                "source_row_ids": [],
                "derived_metrics": {},
            },
        )

        cleaner = financial_aggregate_projection._clean_source_row_ids
        cleaner_inputs = []

        def _fail_on_derived(values):
            cleaner_inputs.append(values)
            if len(cleaner_inputs) == 3:
                raise RuntimeError("derived provenance unavailable")
            return cleaner(values)

        with patch.object(
            financial_aggregate_projection,
            "_clean_source_row_ids",
            side_effect=_fail_on_derived,
        ):
            with self.assertRaisesRegex(RuntimeError, "derived provenance unavailable"):
                _filter(projection, ["ev_keep"])
        self.assertEqual(
            cleaner_inputs,
            [
                [projection["calculation_result"]["source_evidence_ids"]],
                [projection["calculation_result"]["source_row_ids"]],
                [projection["calculation_result"]["derived_metrics"]["aggregate_source_evidence_ids"]],
            ],
        )
        self.assertEqual(projection, projection_snapshot)

    def test_nested_subtask_sync_preserves_recursive_copy_contract(self) -> None:
        class _TrackingRow(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.get_calls = []

            def get(self, key, default=None):
                self.get_calls.append(key)
                if len(self.get_calls) == 2:
                    raise RuntimeError("task id unavailable")
                return super().get(key, default)

        def sync_rows(ordered_results):
            return synchronize_nested_aggregate_subtask_rows(
                AggregateNestedSubtaskSynchronizationInput(
                    ordered_results=ordered_results,
                )
            ).ordered_results

        marker = {"preserve": True}
        unmatched_marker = {"unmatched": True}
        blank_marker = {"blank": True}
        first_child = {"task_id": " child ", "value": "first", "marker": marker}
        last_child = {"task_id": "child", "value": "last", "marker": marker}
        unmatched = {"task_id": "missing", "value": "unmatched", "marker": unmatched_marker}
        blank = {"task_id": " ", "value": "blank", "marker": blank_marker}
        parent = {
            "task_id": "parent",
            "marker": marker,
            "calculation_result": {
                "marker": marker,
                "subtask_results": [
                    "discard",
                    {"task_id": " child ", "value": "stale"},
                    unmatched,
                    blank,
                ],
                "answer_slots": {
                    "marker": marker,
                    "subtask_results": [{"task_id": "child", "value": "stale_slot"}],
                },
            },
            "answer_slots": {
                "marker": marker,
                "subtask_results": [{"task_id": "child", "value": "stale_row_slot"}],
            },
        }
        ordered_results = [first_child, last_child, parent]
        ordered_snapshot = deepcopy(ordered_results)

        selected = sync_rows(ordered_results)

        selected_parent = selected[2]
        calculation_result = selected_parent["calculation_result"]
        calculation_rows = calculation_result["subtask_results"]
        calculation_slot_rows = calculation_result["answer_slots"]["subtask_results"]
        row_slot_rows = selected_parent["answer_slots"]["subtask_results"]
        self.assertEqual(
            [(row["task_id"], row["value"]) for row in calculation_rows],
            [("child", "last"), ("missing", "unmatched"), (" ", "blank")],
        )
        self.assertEqual(
            [rows[0]["value"] for rows in (calculation_slot_rows, row_slot_rows)],
            ["last", "last"],
        )
        self.assertEqual([row["task_id"] for row in selected], [" child ", "child", "parent"])
        self.assertIsNot(selected, ordered_results)
        for selected_row, original_row in zip(selected, ordered_results):
            self.assertIsNot(selected_row, original_row)
        for selected_value, original_value in (
            (calculation_result, parent["calculation_result"]),
            (calculation_rows, parent["calculation_result"]["subtask_results"]),
            (calculation_result["answer_slots"], parent["calculation_result"]["answer_slots"]),
            (calculation_slot_rows, parent["calculation_result"]["answer_slots"]["subtask_results"]),
            (selected_parent["answer_slots"], parent["answer_slots"]),
            (row_slot_rows, parent["answer_slots"]["subtask_results"]),
            (calculation_rows[1], unmatched),
            (calculation_rows[2], blank),
        ):
            self.assertIsNot(selected_value, original_value)
        for retained, original in (
            (selected[1]["marker"], marker),
            (calculation_rows[0]["marker"], marker),
            (calculation_rows[1]["marker"], unmatched_marker),
            (calculation_rows[2]["marker"], blank_marker),
            (calculation_result["marker"], marker),
            (calculation_result["answer_slots"]["marker"], marker),
            (selected_parent["answer_slots"]["marker"], marker),
        ):
            self.assertIs(retained, original)
        self.assertEqual(ordered_results, ordered_snapshot)

        nested_root = {"task_id": "root", "value": "nested_root"}
        root = {
            "task_id": "root",
            "value": "canonical_root",
            "calculation_result": {"subtask_results": [{"task_id": "child"}]},
        }
        child = {
            "task_id": "child",
            "value": "canonical_child",
            "calculation_result": {"subtask_results": [nested_root]},
        }
        cycle_selected = sync_rows([root, child])
        cycle_child = cycle_selected[0]["calculation_result"]["subtask_results"][0]
        cycle_root = cycle_child["calculation_result"]["subtask_results"][0]
        self.assertEqual((cycle_child["value"], cycle_root["value"]), ("canonical_child", "nested_root"))

        deep_rows = [
            {
                "task_id": f"depth_{index}",
                "calculation_result": {
                    "subtask_results": (
                        [{"task_id": f"depth_{index + 1}"}] if index < 10 else []
                    )
                },
            }
            for index in range(11)
        ]
        deep_snapshot = deepcopy(deep_rows)
        cursor = sync_rows(deep_rows)[0]
        for _ in range(9):
            cursor = cursor["calculation_result"]["subtask_results"][0]
        self.assertEqual(cursor["task_id"], "depth_9")
        self.assertIs(cursor["calculation_result"], deep_rows[9]["calculation_result"])
        self.assertEqual(deep_rows, deep_snapshot)

        empty_results = []
        empty_selected = sync_rows(empty_results)
        self.assertEqual(empty_selected, [])
        self.assertIsNot(empty_selected, empty_results)
        tracking_row = _TrackingRow(task_id="tracked")
        with self.assertRaisesRegex(RuntimeError, "task id unavailable"):
            sync_rows([tracking_row])
        self.assertEqual(tracking_row.get_calls, ["task_id", "task_id"])

    def test_aggregate_answer_candidate_packaging_preserves_normalization_and_access_order(self) -> None:
        events = []

        def package(answer, **kwargs):
            return package_aggregate_answer_candidate(
                AggregateAnswerCandidatePackagingInput(answer=answer, **kwargs)
            ).candidate

        def package_refreshed(refreshed_answer, fallback_answer, **kwargs):
            return package_refreshed_aggregate_answer_candidate(
                AggregateRefreshedAnswerCandidatePackagingInput(
                    refreshed_answer=refreshed_answer,
                    fallback_answer=fallback_answer,
                    **kwargs,
                )
            ).candidate

        class _TrackedValue:
            def __init__(self, name, value, *, truth=True, fail_str_call=0, fail_bool=False):
                self.name = name
                self.value = value
                self.truth = truth
                self.fail_str_call = fail_str_call
                self.fail_bool = fail_bool
                self.str_calls = 0

            def __str__(self):
                self.str_calls += 1
                events.append(f"str:{self.name}")
                if self.str_calls == self.fail_str_call:
                    raise RuntimeError(f"failed to stringify {self.name}")
                return self.value

            def __bool__(self):
                events.append(f"bool:{self.name}")
                if self.fail_bool:
                    raise RuntimeError(f"failed to coerce {self.name}")
                return self.truth

        class _TrackedClaims:
            def __init__(self, values):
                self.values = values

            def __bool__(self):
                events.append("bool:refreshed_claims")
                return bool(self.values)

            def __iter__(self):
                events.append("iter:refreshed_claims")
                return iter(self.values)

        class _TrackingMapping(Mapping):
            def __init__(self, values, *, fail_key=""):
                self.values = values
                self.fail_key = fail_key

            def __len__(self):
                events.append("len:payload")
                return len(self.values)

            def __iter__(self):
                events.append("iter:payload")
                return iter(self.values)

            def __getitem__(self, key):
                events.append(f"getitem:{key}")
                if key == self.fail_key:
                    raise RuntimeError(f"failed to copy {key}")
                return self.values[key]

        claim_ids = [
            _TrackedValue("keep", " keep "),
            _TrackedValue("blank", "  "),
            _TrackedValue("duplicate", "keep"),
        ]
        claim_ids_snapshot = list(claim_ids)
        packaged = package(
            "  final   answer  ",
            selected_claim_ids=claim_ids,
            sync_projection=_TrackedValue("sync", "", truth=True),
            sync_rendered_for_aggregate=_TrackedValue("render", "", truth=False),
            status_ok=_TrackedValue("status", "", truth=True),
        )
        self.assertEqual(
            tuple(packaged.values()),
            ("final answer", ["keep", "keep"], True, False, True),
        )
        self.assertIsNot(packaged["selected_claim_ids"], claim_ids)
        self.assertEqual(claim_ids, claim_ids_snapshot)
        self.assertEqual(events, [
            "str:keep", "str:keep", "str:blank", "str:duplicate", "str:duplicate",
            "bool:sync", "bool:render", "bool:status",
        ])
        fresh_candidate = package("")
        second_fresh_candidate = package("")
        self.assertIsNot(fresh_candidate, second_fresh_candidate)
        self.assertIsNot(fresh_candidate["selected_claim_ids"], second_fresh_candidate["selected_claim_ids"])

        events.clear()
        with self.assertRaisesRegex(RuntimeError, "failed to coerce render"):
            package(
                "answer",
                sync_projection=_TrackedValue("sync", "", truth=True),
                sync_rendered_for_aggregate=_TrackedValue("render", "", fail_bool=True),
                status_ok=_TrackedValue("status", "", truth=True),
            )
        self.assertEqual(events, ["bool:sync", "bool:render"])

        events.clear()
        with self.assertRaisesRegex(RuntimeError, "failed to stringify broken"):
            package(
                "answer",
                selected_claim_ids=[_TrackedValue("broken", "id", fail_str_call=2)],
                sync_projection=_TrackedValue("unreached", "", truth=True),
            )
        self.assertEqual(events, ["str:broken", "str:broken"])

        events.clear()
        marker = {"preserve": True}
        refreshed_claims = _TrackedClaims([_TrackedValue("refreshed_claim", " ev_1 ")])
        refreshed_values = {
            "answer": _TrackedValue("refreshed_answer", " refreshed   answer "),
            "selected_claim_ids": refreshed_claims,
            "metadata": marker,
        }
        refreshed_snapshot = dict(refreshed_values)
        with patch.object(
            financial_aggregate_projection,
            "package_aggregate_answer_candidate",
            wraps=financial_aggregate_projection.package_aggregate_answer_candidate,
        ) as base_packager:
            refreshed = package_refreshed(
                _TrackingMapping(refreshed_values),
                "fallback answer",
                sync_projection=_TrackedValue("refresh_sync", "", truth=False),
                sync_rendered_for_aggregate=_TrackedValue("refresh_render", "", truth=True),
                status_ok=_TrackedValue("refresh_status", "", truth=True),
            )
        base_packager.assert_called_once()
        self.assertIsNot(refreshed, refreshed_values)
        self.assertEqual(refreshed_values, refreshed_snapshot)
        self.assertEqual(
            tuple(refreshed.values()),
            ("refreshed answer", ["ev_1"], False, True, True),
        )
        self.assertIs(refreshed_values["metadata"], marker)
        self.assertIs(refreshed_values["selected_claim_ids"], refreshed_claims)
        self.assertEqual(events, [
            "len:payload", "iter:payload", "getitem:answer", "getitem:selected_claim_ids",
            "getitem:metadata", "bool:refreshed_answer", "str:refreshed_answer",
            "bool:refreshed_claims", "bool:refreshed_claims", "iter:refreshed_claims",
            "str:refreshed_claim", "str:refreshed_claim", "bool:refresh_sync",
            "bool:refresh_render", "bool:refresh_status",
        ])

        fallback = package_refreshed({"answer": None}, " fallback   answer ")
        whitespace = package_refreshed({"answer": "   "}, "fallback answer")
        self.assertEqual((fallback["answer"], whitespace["answer"]), ("fallback answer", ""))

        events.clear()
        with self.assertRaisesRegex(RuntimeError, "failed to copy selected_claim_ids"):
            package_refreshed(
                _TrackingMapping(
                    {"answer": "answer", "selected_claim_ids": ["ev_1"]},
                    fail_key="selected_claim_ids",
                ),
                "fallback",
                sync_projection=_TrackedValue("unreached", "", truth=True),
            )
        self.assertEqual(events, [
            "len:payload", "iter:payload", "getitem:answer", "getitem:selected_claim_ids",
        ])

    def test_aggregate_answer_candidate_application_preserves_projection_and_claim_contract(self) -> None:
        def _apply(projection, selected_claim_ids, candidate):
            result = apply_aggregate_answer_candidate(
                AggregateAnswerCandidateApplicationInput(
                    aggregate_projection=projection,
                    selected_claim_ids=selected_claim_ids,
                    candidate=candidate,
                )
            )
            return result.aggregate_projection, result.final_answer, result.selected_claim_ids

        def _sync(projection, final_answer, **kwargs):
            return sync_aggregate_projection_final_answer(
                AggregateProjectionFinalAnswerSyncInput(
                    aggregate_projection=projection,
                    final_answer=final_answer,
                    **kwargs,
                )
            ).aggregate_projection

        class _TrackingCandidate(dict):
            def __init__(self, *args, failing_key="", **kwargs):
                super().__init__(*args, **kwargs)
                self.accessed = []
                self.failing_key = failing_key

            def get(self, key, default=None):
                self.accessed.append(key)
                if key == self.failing_key:
                    raise RuntimeError(f"failed to read {key}")
                return super().get(key, default)

        class _ExplodingPlan(dict):
            def get(self, _key, _default=None):
                raise RuntimeError("plan mode unavailable")

        marker = {"preserve": True}
        result = {
            "formatted_result": "old",
            "rendered_value": "old",
            "status": "partial",
            "metadata": marker,
        }
        projection = {
            "calculation_plan": {"mode": "aggregate_subtasks"},
            "calculation_result": result,
        }
        current_ids = [" keep ", "duplicate", "", "duplicate"]
        candidate_ids = ["duplicate", " next ", " "]
        candidate = _TrackingCandidate(
            answer="  final   answer  ",
            selected_claim_ids=candidate_ids,
            sync_projection=True,
            sync_rendered_for_aggregate=True,
            status_ok=True,
        )
        candidate_snapshot = deepcopy(dict(candidate))

        selected_projection, final_answer, merged_ids = _apply(
            projection, current_ids, candidate
        )

        self.assertIs(selected_projection, projection)
        self.assertIs(projection["calculation_result"], result)
        self.assertIs(result["metadata"], marker)
        self.assertEqual(
            (final_answer, merged_ids, result["formatted_result"], result["rendered_value"], result["status"]),
            ("final answer", ["keep", "duplicate", "next"], "final answer", "final answer", "ok"),
        )
        self.assertIsNot(merged_ids, current_ids)
        self.assertIsNot(merged_ids, candidate_ids)
        self.assertEqual(current_ids, [" keep ", "duplicate", "", "duplicate"])
        self.assertEqual(dict(candidate), candidate_snapshot)
        self.assertIs(candidate["selected_claim_ids"], candidate_ids)
        self.assertEqual(
            candidate.accessed,
            ["answer", "sync_projection", "sync_rendered_for_aggregate", "status_ok", "selected_claim_ids"],
        )

        empty_projection = {"calculation_plan": {"mode": "aggregate_subtasks"}}
        empty_candidate = _TrackingCandidate(answer=" \n ", selected_claim_ids=[" next ", "keep"])
        selected_projection, final_answer, merged_ids = _apply(
            empty_projection, [" keep ", "keep"], empty_candidate
        )
        self.assertIs(selected_projection, empty_projection)
        self.assertEqual((empty_projection, final_answer, merged_ids), (
            {"calculation_plan": {"mode": "aggregate_subtasks"}}, "", ["keep", "next"]
        ))
        self.assertEqual(
            empty_candidate.accessed,
            ["answer", "sync_projection", "sync_rendered_for_aggregate", "status_ok", "selected_claim_ids"],
        )

        unchanged_result = {"formatted_result": "old", "rendered_value": "old"}
        unchanged_projection = {
            "calculation_plan": {"mode": "aggregate_subtasks"},
            "calculation_result": unchanged_result,
        }
        no_sync = _TrackingCandidate(
            answer=" new   answer ",
            selected_claim_ids=["new"],
            sync_projection=False,
            sync_rendered_for_aggregate=True,
            status_ok=True,
        )
        unchanged_snapshot = deepcopy(unchanged_projection)
        selected_projection, final_answer, merged_ids = _apply(
            unchanged_projection, ["old"], no_sync
        )
        self.assertIs(selected_projection, unchanged_projection)
        self.assertIs(unchanged_projection["calculation_result"], unchanged_result)
        self.assertEqual((unchanged_projection, final_answer, merged_ids), (
            unchanged_snapshot, "new answer", ["old", "new"]
        ))
        self.assertEqual(no_sync.accessed, ["answer", "sync_projection", "selected_claim_ids"])

        flag_error_projection = {
            "calculation_plan": {"mode": "aggregate_subtasks"},
            "calculation_result": {"formatted_result": "old", "rendered_value": "old"},
        }
        flag_error = _TrackingCandidate(
            answer="updated",
            selected_claim_ids=["never-read"],
            sync_projection=True,
            sync_rendered_for_aggregate=True,
            status_ok=True,
            failing_key="status_ok",
        )
        flag_error_snapshot = deepcopy(flag_error_projection)
        with self.assertRaisesRegex(RuntimeError, "failed to read status_ok"):
            _apply(flag_error_projection, ["existing"], flag_error)
        self.assertEqual(flag_error_projection, flag_error_snapshot)
        self.assertEqual(
            flag_error.accessed,
            ["answer", "sync_projection", "sync_rendered_for_aggregate", "status_ok"],
        )

        sync_cases = [
            (
                "missing_result",
                {"calculation_plan": {"mode": "single_value"}},
                {},
                {"formatted_result": "updated"},
            ),
            (
                "nonaggregate",
                {
                    "calculation_plan": {"mode": "single_value"},
                    "calculation_result": {"rendered_value": "preserved", "status": "partial"},
                },
                {},
                {"formatted_result": "updated", "rendered_value": "preserved", "status": "partial"},
            ),
            (
                "render_disabled",
                {
                    "calculation_plan": _ExplodingPlan(marker=True),
                    "calculation_result": {"rendered_value": "preserved", "status": "partial"},
                },
                {"sync_rendered_for_aggregate": False, "status_ok": True},
                {"formatted_result": "updated", "rendered_value": "preserved", "status": "ok"},
            ),
        ]
        for name, sync_projection, sync_kwargs, expected_result in sync_cases:
            with self.subTest(sync=name):
                original_result = sync_projection.get("calculation_result")
                synced = _sync(sync_projection, "updated", **sync_kwargs)
                self.assertIs(synced, sync_projection)
                if original_result is not None:
                    self.assertIs(synced["calculation_result"], original_result)
                self.assertEqual(synced["calculation_result"], expected_result)

        sync_error_result = {"formatted_result": "old", "rendered_value": "old", "status": "partial"}
        sync_error = _TrackingCandidate(
            answer="updated",
            selected_claim_ids=["never-read"],
            sync_projection=True,
            sync_rendered_for_aggregate=True,
            status_ok=True,
        )
        with self.assertRaisesRegex(RuntimeError, "plan mode unavailable"):
            _apply(
                {
                    "calculation_plan": _ExplodingPlan(marker=True),
                    "calculation_result": sync_error_result,
                },
                ["existing"],
                sync_error,
            )
        self.assertEqual(sync_error_result, {
            "formatted_result": "updated", "rendered_value": "old", "status": "partial"
        })
        self.assertNotIn("selected_claim_ids", sync_error.accessed)

        claim_error_result = {"formatted_result": "old", "rendered_value": "old", "status": "partial"}
        claim_error = _TrackingCandidate(
            answer="updated",
            selected_claim_ids=["unavailable"],
            sync_projection=True,
            sync_rendered_for_aggregate=True,
            status_ok=True,
            failing_key="selected_claim_ids",
        )
        with self.assertRaisesRegex(RuntimeError, "failed to read selected_claim_ids"):
            _apply(
                {
                    "calculation_plan": {"mode": "aggregate_subtasks"},
                    "calculation_result": claim_error_result,
                },
                ["existing"],
                claim_error,
            )
        self.assertEqual(claim_error_result, {
            "formatted_result": "updated", "rendered_value": "updated", "status": "ok"
        })

    def test_aggregate_selected_claim_ids_preserves_order_and_dedupes(self) -> None:
        selected = aggregate_selected_claim_ids(
            [
                {"selected_claim_ids": ["ev1", "", "ev2", "ev1"]},
                {"selected_claim_ids": ["ev3"]},
                {"selected_claim_ids": None},
            ],
            ["ev2", "ev4", ""],
        )

        self.assertEqual(selected, ["ev1", "ev2", "ev3", "ev4", ""])

    def test_aggregate_extend_selected_claim_ids_preserves_first_seen_order(self) -> None:
        selected = aggregate_extend_selected_claim_ids(
            ["ev1", "ev2"],
            ["ev2", "ev3", "ev1", ""],
        )

        self.assertEqual(selected, ["ev1", "ev2", "ev3", ""])

    def test_aggregate_result_operation_family_preserves_resolution_precedence(self) -> None:
        cases = [
            (
                "direct",
                {
                    "operation_family": " SUM ",
                    "answer_slots": {"operation_family": "ratio"},
                    "calculation_plan": {"operation": "difference"},
                },
                "sum",
            ),
            (
                "calculation_result_answer_slots",
                {
                    "calculation_result": {
                        "answer_slots": {"operation_family": "ratio"}
                    },
                    "answer_slots": {"operation_family": "difference"},
                    "calculation_plan": {"operation": "sum"},
                },
                "ratio",
            ),
            (
                "row_answer_slots",
                {
                    "answer_slots": {"operation_family": "difference"},
                    "calculation_plan": {"operation": "sum"},
                },
                "difference",
            ),
            ("calculation_plan", {"calculation_plan": {"operation": "growth_rate"}}, "growth_rate"),
            *[
                (f"metric_{metric_family}", {"metric_family": metric_family}, expected)
                for metric_family, expected in (
                    ("concept_lookup", "lookup"),
                    ("custom_ratio", "ratio"),
                    ("custom_growth_rate", "growth_rate"),
                    ("custom_difference", "difference"),
                    ("custom_sum", "sum"),
                )
            ],
            *[
                (f"alias_{alias}", {"operation_family": alias}, expected)
                for alias, expected in (
                    ("divide", "ratio"),
                    (" DiViSiOn ", "ratio"),
                    ("subtract", "difference"),
                    ("subtraction", "difference"),
                    ("add", "sum"),
                    ("addition", "sum"),
                )
            ],
        ]

        for case_name, row, expected in cases:
            with self.subTest(case_name=case_name):
                self.assertEqual(aggregate_result_operation_family(row), expected)

    def test_stale_repair_provenance_selects_unique_overlap_without_mutating_inputs(self) -> None:
        source_fields = {
            "ordered_results": [
                _stale_provenance_row("ev_stale", "row_overlap"),
                _stale_provenance_row("ev_other", "row_other"),
            ],
            "aggregate_projection": {
                "calculation_result": {"source_row_ids": ["row_overlap"]}
            },
            "selected_claim_ids": ["ev_keep", "ev_stale", "ev_existing", "ev_other"],
            "repaired_calculation_result": _repaired_growth_result(),
            "repaired_selected_evidence_ids": [
                "ev_new_b",
                "ev_missing",
                "ev_existing",
                "ev_new_a",
                "ev_new_b",
            ],
            "evidence_items": [
                {"evidence_id": "ev_new_a", "metadata": {"rank": 1}},
                {"evidence_id": "ev_new_b"},
                {"evidence_id": "ev_existing"},
            ],
        }
        provenance_input = AggregateStaleRepairProvenanceInput(**source_fields)
        original_inputs = deepcopy(source_fields)

        result = select_aggregate_stale_repair_provenance(provenance_input)

        self.assertEqual(result.target_resolution, "unique_overlap")
        self.assertEqual(
            result.selected_claim_ids,
            ("ev_keep", "ev_existing", "ev_other", "ev_new_b", "ev_new_a"),
        )
        for field_name, value in source_fields.items():
            self.assertIs(getattr(provenance_input, field_name), value)
        self.assertEqual(source_fields, original_inputs)

    def test_stale_repair_provenance_keeps_ambiguous_targets(self) -> None:
        ordered_results = [
            _stale_provenance_row("ev_stale_a", "row_a"),
            _stale_provenance_row("ev_stale_b", "row_b"),
        ]

        for projection_sources in (["row_a", "row_b"], ["row_projection"]):
            with self.subTest(projection_sources=projection_sources):
                result = select_aggregate_stale_repair_provenance(
                    AggregateStaleRepairProvenanceInput(
                        ordered_results=ordered_results,
                        aggregate_projection={
                            "calculation_result": {"source_row_ids": projection_sources}
                        },
                        selected_claim_ids=["ev_keep", "ev_stale_a", "ev_stale_b"],
                        repaired_calculation_result=_repaired_growth_result(),
                        repaired_selected_evidence_ids=["ev_new"],
                        evidence_items=[{"evidence_id": "ev_new"}],
                    )
                )

                self.assertEqual(result.target_resolution, "ambiguous_target")
                self.assertEqual(
                    result.selected_claim_ids,
                    ("ev_keep", "ev_stale_a", "ev_stale_b", "ev_new"),
                )

    def test_stale_repair_provenance_distinguishes_single_identity_and_no_target(self) -> None:
        cases = [
            (
                "single_identity_candidate",
                [_stale_provenance_row("ev_stale", "row_candidate")],
                _repaired_growth_result(),
                ("ev_keep", "ev_new"),
            ),
            (
                "no_target",
                [_stale_provenance_row("ev_stale")],
                {
                    "operation_family": "growth_rate",
                    "metric_label": "revenue growth",
                    "answer_slots": {"operation_family": "growth_rate"},
                },
                ("ev_stale", "ev_keep", "ev_new"),
            ),
        ]

        for (
            expected_resolution,
            ordered_results,
            repaired_calculation_result,
            expected_selected,
        ) in cases:
            with self.subTest(expected_resolution=expected_resolution):
                result = select_aggregate_stale_repair_provenance(
                    AggregateStaleRepairProvenanceInput(
                        ordered_results=ordered_results,
                        aggregate_projection={
                            "calculation_result": {"source_row_ids": ["row_projection"]}
                        },
                        selected_claim_ids=["ev_stale", "ev_keep"],
                        repaired_calculation_result=repaired_calculation_result,
                        repaired_selected_evidence_ids=["ev_new"],
                        evidence_items=[{"evidence_id": "ev_new"}],
                    )
                )

                self.assertEqual(result.target_resolution, expected_resolution)
                self.assertEqual(result.selected_claim_ids, expected_selected)

    def test_aggregate_ordered_result_source_refs_collects_nested_sources(self) -> None:
        source_refs = aggregate_ordered_result_source_refs(
            [
                {
                    "source_row_id": "row:1",
                    "source_row_ids": ["row:2", "row:1"],
                    "calculation_result": {"source_row_ids": ["calc:1"]},
                    "answer_slots": {"source_row_id": "slot:1", "source_row_ids": ["slot:2"]},
                },
                {
                    "calculation_result": "not-a-dict",
                    "answer_slots": {"source_row_ids": ["row:2", "slot:3"]},
                },
            ]
        )

        self.assertEqual(source_refs, ["row:1", "row:2", "calc:1", "slot:1", "slot:2", "slot:3"])

    def test_aggregate_integrity_projection_helpers_build_ledger_inputs(self) -> None:
        ordered_results = [{"task_id": " task_a "}, {"task_id": ""}, {"task_id": "task_b"}]
        preliminary_projection = {"calculation_result": {"source_row_id": "prelim"}}
        override_projection = {
            "calculation_result": {
                "source_row_ids": ["result:1"],
                "answer_slots": {
                    "source_row_id": "slot:1",
                    "source_row_ids": ["slot:2"],
                },
            }
        }

        projection = aggregate_projection_for_integrity(preliminary_projection, override_projection)
        refs = aggregate_integrity_extra_refs(projection, ["row:1"], ["ev:1"])

        self.assertEqual(aggregate_source_task_ids(ordered_results), ["task_a", "task_b"])
        self.assertIs(projection, override_projection)
        self.assertEqual(refs, [None, ["result:1"], "slot:1", ["slot:2"], ["row:1"], ["ev:1"]])
        self.assertIs(
            aggregate_projection_for_integrity(preliminary_projection, {}),
            preliminary_projection,
        )

    def test_aggregate_projection_apply_override_updates_supported_fields(self) -> None:
        projection = {
            "calculation_operands": ["old_operand"],
            "calculation_plan": {"old": True},
            "calculation_result": {"old": True},
            "evidence_items": ["keep"],
        }
        override = {
            "calculation_operands": ["new_operand"],
            "calculation_plan": {},
            "calculation_result": {"status": "ok"},
            "evidence_items": ["ignored"],
        }

        result = aggregate_projection_apply_override(projection, override)

        self.assertIs(result, projection)
        self.assertEqual(result["calculation_operands"], ["new_operand"])
        self.assertEqual(result["calculation_plan"], {"old": True})
        self.assertEqual(result["calculation_result"], {"status": "ok"})
        self.assertEqual(result["evidence_items"], ["keep"])
        self.assertIs(
            aggregate_projection_apply_override(projection, "not-a-dict"),
            projection,
        )

    def test_aggregate_period_context_evidence_items_dedupes_context_rows(self) -> None:
        context_items = aggregate_period_context_evidence_items(
            [{"evidence_id": "ev1", "claim": "base"}],
            [
                {"evidence_id": " ev1 ", "claim": "duplicate"},
                {"evidence_id": "ev2", "claim": "context"},
                "not-a-row",
                {"claim": "no id"},
            ],
        )

        self.assertEqual(
            context_items,
            [
                {"evidence_id": "ev1", "claim": "base"},
                {"evidence_id": "ev2", "claim": "context"},
                {"claim": "no id"},
            ],
        )

    def test_aggregate_completion_base_payload_builds_non_trace_fields(self) -> None:
        payload = aggregate_completion_base_payload(
            state={"subtask_debug_trace": {"existing": True}},
            ordered_results=[{"task_id": "task_a"}],
            aggregate_projection={"evidence_items": [{"evidence_id": "projection"}]},
            final_answer="final",
            selected_claim_ids=["ev1"],
            aggregate_evidence_items=[],
            tasks=[{"task_id": "aggregate"}],
            artifacts=[{"artifact_id": "aggregate:001"}],
            planner_feedback="needs retry",
            should_replan=True,
            replan_blocked_reason="",
            aggregate_synthesis_debug={"input_json_chars": 10},
        )

        self.assertTrue(payload["subtask_loop_complete"])
        self.assertEqual(payload["answer"], "final")
        self.assertEqual(payload["compressed_answer"], "final")
        self.assertEqual(payload["planner_mode"], "replan")
        self.assertEqual(payload["selected_claim_ids"], ["ev1"])
        self.assertEqual(payload["kept_claim_ids"], ["ev1"])
        self.assertEqual(payload["draft_points"], ["final"])
        self.assertEqual(payload["evidence_items"], [{"evidence_id": "projection"}])
        self.assertEqual(
            payload["subtask_debug_trace"],
            {"existing": True, "aggregate_synthesis_prompt": {"input_json_chars": 10}},
        )

    def test_aggregate_artifact_payload_and_task_status_helpers(self) -> None:
        payload = aggregate_artifact_payload(
            ordered_results=[{"task_id": "task_a"}],
            final_answer="final",
            planner_feedback="retry",
            aggregate_projection={"calculation_result": {"status": "ok"}},
        )

        self.assertEqual(
            payload,
            {
                "subtask_results": [{"task_id": "task_a"}],
                "final_answer": "final",
                "planner_feedback": "retry",
                "calculation_result": {"status": "ok"},
            },
        )
        self.assertEqual(
            aggregate_task_status_value(
                planner_feedback="retry",
                completed_value="completed",
                partial_value="partial",
            ),
            "partial",
        )
        self.assertEqual(
            aggregate_task_status_value(
                planner_feedback="",
                completed_value="completed",
                partial_value="partial",
            ),
            "completed",
        )

    def test_ordered_aggregate_subtask_results_for_repair_preserves_trace_priority(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        calculation_result = {
            "subtask_results": [
                {"task_id": "task_growth", "answer": "fresh trace growth", "status": "ok"},
            ]
        }
        answer_slots = {
            "subtask_results": [
                {"task_id": "task_growth", "answer": "slot duplicate growth", "status": "ok"},
                {"task_id": "task_narrative", "answer": "slot narrative", "status": "ok"},
            ]
        }
        state = {
            "structured_result": {
                "subtask_results": [
                    {"task_id": "task_narrative", "answer": "structured duplicate narrative", "status": "ok"},
                    {"task_id": "task_lookup", "answer": "structured lookup", "status": "ok"},
                ]
            },
            "subtask_results": [
                {"task_id": "task_growth", "answer": "stale state growth", "status": "ok"},
                {"task_id": "task_lookup", "answer": "stale state lookup", "status": "ok"},
            ],
        }

        with patch.object(
            financial_graph_calculation,
            "aggregate_result_signature",
            wraps=financial_aggregate_projection.aggregate_result_signature,
        ) as signature_owner:
            ordered = agent._ordered_aggregate_subtask_results_for_repair(
                state=state,
                calculation_result=calculation_result,
                answer_slots=answer_slots,
            )
        signature_owner.assert_not_called()

        self.assertEqual(
            [(row["task_id"], row["answer"]) for row in ordered],
            [
                ("task_growth", "fresh trace growth"),
                ("task_narrative", "slot narrative"),
                ("task_lookup", "structured lookup"),
            ],
        )

        signature_only_row = {"operation_family": "ratio", "metric_label": "orphan metric"}
        with patch.object(
            financial_graph_calculation,
            "aggregate_result_signature",
            wraps=financial_aggregate_projection.aggregate_result_signature,
        ) as signature_owner:
            fallback_ordered = agent._ordered_aggregate_subtask_results_for_repair(
                state={},
                calculation_result={"subtask_results": [signature_only_row]},
                answer_slots={},
            )
        signature_owner.assert_called_once()
        self.assertEqual(signature_owner.call_args.args[0], signature_only_row)
        self.assertIsNot(signature_owner.call_args.args[0], signature_only_row)
        self.assertEqual(fallback_ordered, [signature_only_row])

    def test_active_lookup_promotes_matching_nested_result_from_aggregate(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        active_subtask = {
            "task_id": "task_prior",
            "metric_family": "concept_lookup",
            "metric_label": "2022 segment revenue",
            "operation_family": "lookup",
        }
        aggregate_result = {
            "status": "partial",
            "rendered_value": "2023 segment revenue is 100.",
            "answer_slots": {"operation_family": "aggregate_subtasks"},
            "subtask_results": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 segment revenue",
                    "answer": "2023 segment revenue is 100.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "100",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "2023 segment revenue",
                                "period": "2023",
                                "raw_value": "100",
                                "normalized_value": 100,
                                "normalized_unit": "KRW",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_prior",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022 segment revenue",
                    "answer": "2022 segment revenue is 80.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "80",
                        "formatted_result": "2022 segment revenue is 80.",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "2022 segment revenue",
                                "period": "2022",
                                "raw_value": "80",
                                "normalized_value": 80,
                                "normalized_unit": "KRW",
                            },
                        },
                    },
                },
            ],
        }

        answer, status, calculation_result = financial_answer_projection.promote_nested_subtask_result_if_more_specific(
            active_subtask=active_subtask,
            answer="2023 segment revenue is 100.",
            status="partial",
            calculation_result=aggregate_result,
        )

        self.assertEqual(answer, "2022 segment revenue is 80.")
        self.assertEqual(status, "ok")
        self.assertEqual(calculation_result["answer_slots"]["primary_value"]["period"], "2022")

    def test_dependency_rows_can_use_sibling_result_without_answer_slots(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "active_subtask": {
                "task_id": "task_growth",
                "operation_family": "growth_rate",
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "revenue",
                        "period": "2023",
                        "label": "2023 segment revenue",
                        "preferred_task_id": "task_current",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    }
                ],
            },
            "calc_subtasks": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 segment revenue",
                    "operation_family": "lookup",
                }
            ],
            "subtask_results": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 segment revenue",
                    "answer": "2023 segment revenue is 100.",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 100,
                        "result_unit": "KRW",
                        "rendered_value": "100",
                    },
                }
            ],
        }

        rows = agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["matched_operand_role"], "current_period")
        self.assertEqual(rows[0]["normalized_value"], 100)

    def test_dependency_rows_synthesize_lookup_slot_from_subtask_answer(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "active_subtask": {
                "task_id": "task_growth",
                "operation_family": "growth_rate",
                "inputs": [
                    {
                        "role": "prior_period",
                        "concept": "revenue",
                        "period": "2022",
                        "label": "segment revenue",
                        "preferred_task_id": "task_prior",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    }
                ],
            },
            "calc_subtasks": [
                {
                    "task_id": "task_prior",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022 segment revenue",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "role": "prior_period",
                            "concept": "revenue",
                            "period": "2022",
                            "label": "segment revenue",
                            "unit_family": "KRW",
                        }
                    ],
                }
            ],
            "subtask_results": [
                {
                    "task_id": "task_prior",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022 segment revenue",
                    "answer": "2022 segment revenue was 1,801,079천원.",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "2022 segment revenue was 1,801,079천원.",
                    },
                }
            ],
        }

        rows = agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["matched_operand_role"], "prior_period")
        self.assertEqual(rows[0]["period"], "2022")

    def test_dependency_rows_synthesize_lookup_slot_with_billion_krw_unit(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "active_subtask": {
                "task_id": "task_growth",
                "operation_family": "growth_rate",
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "provision_expense",
                        "period": "2023",
                        "label": "provision expense",
                        "preferred_task_id": "task_current",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    }
                ],
            },
            "calc_subtasks": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 provision expense",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "role": "current_period",
                            "concept": "provision_expense",
                            "period": "2023",
                            "label": "provision expense",
                            "unit_family": "KRW",
                        }
                    ],
                }
            ],
            "subtask_results": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 provision expense",
                    "answer": "2023 provision expense was 3,146십억원.",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "2023 provision expense was 3,146십억원.",
                    },
                }
            ],
        }

        rows = agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["raw_value"], "3,146")
        self.assertEqual(rows[0]["raw_unit"], "십억원")
        self.assertEqual(rows[0]["normalized_unit"], "KRW")

    def test_lookup_unit_refinement_preserves_explicit_normalized_unit(self) -> None:
        slot = {
            "raw_value": "3,146",
            "raw_unit": "십억원",
            "normalized_value": 3_146_000_000_000.0,
            "normalized_unit": "KRW",
            "rendered_value": "3,146십억원",
        }
        evidence = {
            "claim": "nearby table text says 3,146억원",
            "metadata": {"table_value_labels_text": "metric 3,146억원"},
        }

        refined = refine_lookup_slot_unit_from_evidence(slot, evidence)

        self.assertEqual(refined["raw_unit"], "십억원")
        self.assertEqual(refined["normalized_value"], 3_146_000_000_000.0)

    def test_dependency_projection_recalculates_from_stronger_source_task_slot(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "query": "calculate coverage ratio",
            "calc_subtasks": [
                {
                    "task_id": "task_source",
                    "metric_family": "concept_lookup",
                    "metric_label": "source metric",
                    "operation_family": "lookup",
                },
                {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "metric_label": "coverage ratio",
                    "operation_family": "ratio",
                },
            ],
        }
        ordered_results = [
            {
                "task_id": "task_source",
                "metric_family": "concept_lookup",
                "metric_label": "source metric",
                "operation_family": "lookup",
                "answer": "source metric 3,531,423백만원",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "result_value": 3_531_423_000_000.0,
                    "result_unit": "백만원",
                    "rendered_value": "3,531,423백만원",
                    "source_row_ids": ["recon::source"],
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "source metric",
                            "concept": "source_metric",
                            "period": "2023",
                            "raw_value": "3,531,423",
                            "raw_unit": "백만원",
                            "normalized_value": 3_531_423_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "3,531,423백만원",
                            "source_row_id": "recon::source",
                            "source_row_ids": ["recon::source"],
                            "source_anchor": "[source]",
                        },
                    },
                },
                "source_row_ids": ["recon::source"],
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "coverage ratio",
                "operation_family": "ratio",
                "answer": "coverage ratio is 0.0035배.",
                "status": "ok",
                "calculation_operands": [
                    {
                        "operand_id": "dep_task_source_001",
                        "evidence_id": "task_output:task_source",
                        "source_row_id": "task_output:task_source",
                        "source_row_ids": ["task_output:task_source", "ev_weak"],
                        "label": "source metric",
                        "raw_value": "3,531,423",
                        "raw_unit": "천원",
                        "normalized_value": 3_531_423_000.0,
                        "normalized_unit": "KRW",
                        "period": "2023",
                        "matched_operand_label": "source metric",
                        "matched_operand_concept": "source_metric",
                        "matched_operand_role": "numerator_1",
                        "source_task_id": "task_source",
                        "dependency_resolved": True,
                    },
                    {
                        "operand_id": "denominator_001",
                        "evidence_id": "recon::denominator",
                        "source_row_id": "recon::denominator",
                        "source_row_ids": ["recon::denominator"],
                        "label": "denominator metric",
                        "raw_value": "1,000,000",
                        "raw_unit": "백만원",
                        "normalized_value": 1_000_000_000_000.0,
                        "normalized_unit": "KRW",
                        "period": "2023",
                        "matched_operand_label": "denominator metric",
                        "matched_operand_concept": "denominator_metric",
                        "matched_operand_role": "denominator_1",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "ratio",
                    "ordered_operand_ids": ["dep_task_source_001", "denominator_001"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "dep_task_source_001"},
                        {"variable": "B", "operand_id": "denominator_001"},
                    ],
                    "formula": "((A) / (B))",
                    "result_unit": "배",
                },
                "calculation_result": {
                    "status": "ok",
                    "result_value": 0.003531423,
                    "result_unit": "배",
                    "rendered_value": "0.0035배",
                    "formatted_result": "coverage ratio is 0.0035배.",
                },
                "source_row_ids": ["task_output:task_source", "ev_weak", "recon::denominator"],
            },
        ]
        aggregate_projection = financial_aggregate_projection.build_aggregate_calculation_projection(
            ordered_results,
            "coverage ratio is 0.0035배.",
        )

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            state,
            aggregate_projection,
        )

        ratio_row = next(row for row in aligned if row["task_id"] == "task_ratio")
        numerator = ratio_row["calculation_operands"][0]
        self.assertTrue(ratio_row["aligned_from_source_task_slots"])
        self.assertEqual(numerator["raw_unit"], "백만원")
        self.assertEqual(numerator["normalized_value"], 3_531_423_000_000.0)
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "3.5314배")
        self.assertIn("recon::source", numerator["source_row_ids"])

    def test_dependency_projection_does_not_cross_ratio_role_groups(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_numerator",
                "metric_family": "concept_lookup",
                "metric_label": "segment operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "segment operating income",
                            "concept": "operating_income",
                            "raw_value": "(581,816)",
                            "raw_unit": "million",
                            "normalized_value": -581_816_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_segment",
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share of total operating income",
                "operation_family": "ratio",
                "status": "ok",
                "calculation_operands": [
                    {
                        "operand_id": "num",
                        "source_row_id": "task_output:task_numerator",
                        "source_row_ids": ["task_output:task_numerator", "row_segment"],
                        "source_task_id": "task_numerator",
                        "label": "segment operating income",
                        "raw_value": "(581,816)",
                        "raw_unit": "million",
                        "normalized_value": -581_816_000_000.0,
                        "normalized_unit": "KRW",
                        "matched_operand_concept": "operating_income",
                        "matched_operand_role": "numerator_1",
                    },
                    {
                        "operand_id": "den",
                        "source_row_id": "row_total",
                        "source_row_ids": ["row_total"],
                        "label": "total operating income",
                        "raw_value": "1,903,886",
                        "raw_unit": "million",
                        "normalized_value": 1_903_886_000_000.0,
                        "normalized_unit": "KRW",
                        "matched_operand_concept": "operating_income",
                        "matched_operand_role": "denominator_1",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "ratio",
                    "ordered_operand_ids": ["num", "den"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "num"},
                        {"variable": "B", "operand_id": "den"},
                    ],
                    "formula": "((A) / (B)) * 100",
                    "result_unit": "%",
                },
                "calculation_result": {
                    "status": "ok",
                    "result_value": 30.56,
                    "result_unit": "%",
                    "rendered_value": "30.56%",
                    "formatted_result": "segment share is 30.56%.",
                },
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "calculate segment share",
                "calc_subtasks": [
                    {"task_id": "task_numerator", "operation_family": "lookup"},
                    {"task_id": "task_ratio", "operation_family": "ratio"},
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = aligned[-1]
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertEqual(denominator["raw_value"], "1,903,886")
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "30.56%")

    def test_stale_difference_result_repairs_from_current_operands(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        operands = [
            {
                "operand_id": "op_a",
                "evidence_id": "ev_current",
                "source_row_id": "row_current",
                "label": "current value",
                "raw_value": "1000",
                "raw_unit": "",
                "normalized_value": 1000.0,
                "normalized_unit": "COUNT",
                "matched_operand_role": "minuend",
            },
            {
                "operand_id": "op_b",
                "evidence_id": "ev_adjustment",
                "source_row_id": "row_adjustment",
                "label": "adjustment",
                "raw_value": "250",
                "raw_unit": "",
                "normalized_value": 250.0,
                "normalized_unit": "COUNT",
                "matched_operand_role": "subtrahend",
            },
        ]
        plan = {
            "status": "ok",
            "mode": "single_value",
            "operation": "subtract",
            "ordered_operand_ids": ["op_a", "op_b"],
            "variable_bindings": [
                {"variable": "A", "operand_id": "op_a"},
                {"variable": "B", "operand_id": "op_b"},
            ],
            "formula": "A - B",
            "result_unit": "",
        }
        state = {
            "query": "calculate adjusted value",
            "active_subtask": {
                "task_id": "task_difference",
                "metric_family": "concept_difference",
                "metric_label": "adjusted value",
                "operation_family": "difference",
            },
        }
        execution_state = {
            **state,
            "resolved_calculation_trace": {
                "calculation_operands": operands,
                "calculation_plan": plan,
                "calculation_result": {},
            },
        }
        primary = agent._execute_calculation(execution_state)
        primary_trace = _resolve_runtime_calculation_trace(primary, allow_legacy_top_level=False)
        stale_result = {
            "status": "ok",
            "result_value": 990.0,
            "result_unit": "",
            "rendered_value": "990",
            "source_row_ids": ["row_stale"],
            "derived_metrics": {
                "formula_result_value": 750.0,
                "source_stated_result_used": False,
            },
        }
        with (
            patch.object(
                financial_graph_calculation,
                "assess_stale_calculation_value",
                wraps=financial_graph_calculation.assess_stale_calculation_value,
            ) as freshness_assessment,
            patch.object(
                financial_calculation_execution,
                "_safe_eval_formula",
                wraps=financial_calculation_execution._safe_eval_formula,
            ) as formula_evaluation,
            patch.object(
                financial_graph_calculation,
                "execute_prepared_calculation_plan",
                wraps=financial_graph_calculation.execute_prepared_calculation_plan,
            ) as canonical_execution,
            patch.object(
                agent,
                "_prepare_calculation_candidate",
                wraps=agent._prepare_calculation_candidate,
            ) as candidate_preparation,
            patch.object(
                agent,
                "_project_prepared_calculation_candidate",
                wraps=agent._project_prepared_calculation_candidate,
            ) as candidate_projection,
            patch.object(
                agent,
                "_project_calculation_candidate_state",
                wraps=agent._project_calculation_candidate_state,
            ) as state_projection,
            patch.object(agent, "_execute_calculation", wraps=agent._execute_calculation) as recursive_execute,
        ):
            repair = agent._repair_stale_calculation_result_from_operands(
                state,
                operands=operands,
                plan=plan,
                calculation_result=stale_result,
            )

        repaired_operands = repair.calculation_operands
        repaired_plan = repair.calculation_plan
        repaired_result = repair.calculation_result
        self.assertTrue(repair.repair_applied)
        self.assertEqual(repair.reason, "repaired")
        self.assertEqual(repair.selected_evidence_ids, ("ev_current", "ev_adjustment"))
        self.assertEqual(repaired_operands, operands)
        self.assertEqual(repaired_plan, plan)
        freshness_assessment.assert_called_once_with(
            expected_value=750.0,
            calculation_result=stale_result,
        )
        self.assertEqual(formula_evaluation.call_count, 1)
        self.assertEqual(
            [call.args for call in formula_evaluation.call_args_list],
            [("A - B", {"A": 1000.0, "B": 250.0})],
        )
        canonical_execution.assert_called_once()
        candidate_preparation.assert_called_once()
        candidate_projection.assert_called_once()
        state_projection.assert_not_called()
        recursive_execute.assert_not_called()
        self.assertEqual(primary["selected_claim_ids"], ["ev_current", "ev_adjustment"])
        self.assertEqual(stale_result["status"], primary_trace["calculation_result"]["status"])
        self.assertNotEqual(stale_result["result_value"], primary_trace["calculation_result"]["result_value"])
        self.assertEqual(repaired_result["result_value"], 750.0)
        self.assertEqual(repaired_result["status"], primary_trace["calculation_result"]["status"])
        self.assertEqual(repaired_result["source_row_ids"], primary_trace["calculation_result"]["source_row_ids"])
        self.assertEqual(
            repaired_result["source_row_ids"],
            ["ev_current", "row_current", "ev_adjustment", "row_adjustment"],
        )
        self.assertNotIn("row_stale", repaired_result["source_row_ids"])
        repaired_without_marker = dict(repaired_result)
        repaired_without_marker.pop("stale_result_repaired_from_operands")
        self.assertEqual(repaired_without_marker, primary_trace["calculation_result"])
        self.assertTrue(repaired_result["stale_result_repaired_from_operands"])

        stale_task = {
            "task_id": "task_difference",
            "artifact_ids": [
                "plan:task_difference:001",
                "result:task_difference:002",
            ],
        }
        stale_plan_artifact = {
            "artifact_id": "plan:task_difference:001",
            "task_id": "task_difference",
            "kind": "calculation_plan",
            "evidence_refs": ["ev_stale"],
            "payload": {"calculation_plan": plan},
        }
        stale_artifact = {
            "artifact_id": "result:task_difference:002",
            "task_id": "task_difference",
            "kind": "calculation_result",
            "evidence_refs": ["ev_stale"],
            "payload": {"calculation_result": stale_result},
        }
        render_state = {
            **state,
            "evidence_items": [{"evidence_id": "ev_stale", "claim": "stale adjusted value"}],
            "selected_claim_ids": ["ev_stale"],
            "kept_claim_ids": ["ev_stale"],
            "tasks": [stale_task],
            "artifacts": [stale_plan_artifact, stale_artifact],
            "resolved_calculation_trace": {
                "calculation_operands": operands,
                "calculation_plan": plan,
                "calculation_result": stale_result,
            },
        }
        original_render_lists = (
            render_state["selected_claim_ids"],
            render_state["kept_claim_ids"],
            render_state["tasks"],
            render_state["artifacts"],
        )
        original_render_state = deepcopy(render_state)

        rendered = agent._render_calculation_answer(render_state)
        merged_render_state = {**render_state, **rendered}
        rendered_trace = _resolve_runtime_calculation_trace(
            merged_render_state,
            allow_legacy_top_level=False,
        )
        rendered_result_artifact = next(
            artifact
            for artifact in merged_render_state["artifacts"]
            if artifact.get("kind") == "calculation_result"
        )

        self.assertEqual(
            rendered_trace["calculation_result"]["source_row_ids"],
            ["ev_current", "row_current", "ev_adjustment", "row_adjustment"],
        )
        self.assertIs(render_state["selected_claim_ids"], original_render_lists[0])
        self.assertIs(render_state["kept_claim_ids"], original_render_lists[1])
        self.assertIs(render_state["tasks"], original_render_lists[2])
        self.assertIs(render_state["artifacts"], original_render_lists[3])
        self.assertEqual(render_state, original_render_state)
        self.assertEqual(
            merged_render_state["selected_claim_ids"],
            ["ev_current", "ev_adjustment"],
        )
        self.assertEqual(
            merged_render_state["kept_claim_ids"],
            ["ev_current", "ev_adjustment"],
        )
        self.assertEqual(
            rendered_result_artifact["payload"]["calculation_result"]["source_row_ids"],
            ["ev_current", "row_current", "ev_adjustment", "row_adjustment"],
        )
        self.assertEqual(
            rendered_result_artifact["evidence_refs"],
            ["ev_current", "ev_adjustment"],
        )
        self.assertEqual(merged_render_state["artifacts"][0], stale_plan_artifact)
        self.assertEqual(
            [task["task_id"] for task in merged_render_state["tasks"]],
            ["task_difference"],
        )
        self.assertEqual(
            [artifact["artifact_id"] for artifact in merged_render_state["artifacts"]],
            ["plan:task_difference:001", "result:task_difference:002"],
        )

        outer_row = {
            "task_id": "task_difference",
            "metric_family": "concept_difference",
            "metric_label": "adjusted value",
            "operation_family": "difference",
            "status": "ok",
            "answer": stale_result["rendered_value"],
            "selected_claim_ids": ["ev_stale"],
            "calculation_operands": operands,
            "calculation_plan": plan,
            "calculation_result": stale_result,
        }
        outer_evidence = [
            render_state["evidence_items"][0],
            {"evidence_id": "ev_current", "claim": "current value 1,000"},
            {"evidence_id": "ev_adjustment", "claim": "adjustment 250"},
        ]
        outer_state = {
            **state,
            "calc_subtasks": [state["active_subtask"]],
            "active_subtask_index": 0,
            "subtask_results": [],
            "answer": stale_result["rendered_value"],
            "compressed_answer": stale_result["rendered_value"],
            "selected_claim_ids": ["ev_stale"],
            "kept_claim_ids": ["ev_stale"],
            "evidence_items": outer_evidence,
            "resolved_calculation_trace": {
                "calculation_operands": operands,
                "calculation_plan": plan,
                "calculation_result": stale_result,
            },
            "tasks": [],
            "artifacts": [],
        }
        filter_windows = []
        original_final_filter = financial_aggregate_projection.filter_final_aggregate_evidence_and_projection

        def _record_final_filter(*args, **kwargs):
            output = original_final_filter(*args, **kwargs)
            if not filter_windows:
                # Simulate a lossy first pass while retaining the real outer call/projection.
                output = ([dict(outer_evidence[0])], output[1], ["ev_stale"], ["ev_stale"])
            filter_windows.append(output)
            return output

        agent.llm = None
        with (
            patch.object(agent, "_capture_current_subtask_result", return_value=outer_row),
            patch.object(
                financial_graph_calculation,
                "filter_final_aggregate_evidence_and_projection",
                side_effect=_record_final_filter,
            ),
            patch.object(
                agent,
                "_apply_stale_projection_repair_to_aggregate_state",
                wraps=agent._apply_stale_projection_repair_to_aggregate_state,
            ) as aggregate_repair,
        ):
            agent._aggregate_calculation_subtasks(outer_state)

        filter_window_ids = [
            [item["evidence_id"] for item in window[0]]
            for window in filter_windows
        ]
        self.assertEqual(filter_window_ids[0], ["ev_stale"])
        aggregate_repair.assert_called_once()
        repair_evidence = aggregate_repair.call_args.kwargs["evidence_items"]
        canonical_refs = ["ev_current", "ev_adjustment"]
        self.assertEqual(
            [item["evidence_id"] for item in repair_evidence],
            ["ev_stale", *canonical_refs],
        )

    def test_stale_repair_keeps_inputs_for_failure_and_indeterminate_assessment(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        operands = [{"operand_id": "op_a", "normalized_value": 1.0}]
        plan = {
            "mode": "single_value",
            "formula": "A",
            "variable_bindings": [{"variable": "A", "operand_id": "missing"}],
        }
        indeterminate_result = {"status": "ok", "result_value": 1.0}
        failed_result = {"status": "parse_error", "result_value": None}
        state = {"query": "calculate value"}

        with (
            patch.object(
                financial_graph_calculation,
                "assess_stale_calculation_value",
                wraps=financial_graph_calculation.assess_stale_calculation_value,
            ) as freshness_assessment,
            patch.object(
                financial_calculation_execution,
                "_safe_eval_formula",
                wraps=financial_calculation_execution._safe_eval_formula,
            ) as formula_evaluation,
            patch.object(
                financial_graph_calculation,
                "execute_prepared_calculation_plan",
                wraps=financial_graph_calculation.execute_prepared_calculation_plan,
            ) as canonical_execution,
            patch.object(
                agent,
                "_prepare_calculation_candidate",
                wraps=agent._prepare_calculation_candidate,
            ) as candidate_preparation,
            patch.object(
                agent,
                "_project_prepared_calculation_candidate",
                wraps=agent._project_prepared_calculation_candidate,
            ) as candidate_projection,
            patch.object(
                agent,
                "_project_calculation_candidate_state",
                wraps=agent._project_calculation_candidate_state,
            ) as state_projection,
            patch.object(agent, "_execute_calculation", wraps=agent._execute_calculation) as recursive_execute,
        ):
            indeterminate = agent._repair_stale_calculation_result_from_operands(
                state,
                operands=operands,
                plan=plan,
                calculation_result=indeterminate_result,
            )
            failed = agent._repair_stale_calculation_result_from_operands(
                state,
                operands=operands,
                plan=plan,
                calculation_result=failed_result,
            )

        freshness_assessment.assert_not_called()
        formula_evaluation.assert_not_called()
        canonical_execution.assert_not_called()
        candidate_preparation.assert_called_once()
        candidate_projection.assert_not_called()
        state_projection.assert_not_called()
        recursive_execute.assert_not_called()
        self.assertFalse(indeterminate.repair_applied)
        self.assertEqual(indeterminate.reason, "preparation_failed")
        self.assertEqual(indeterminate.selected_evidence_ids, ())
        self.assertIs(indeterminate.calculation_operands, operands)
        self.assertIs(indeterminate.calculation_plan, plan)
        self.assertIs(indeterminate.calculation_result, indeterminate_result)
        self.assertFalse(failed.repair_applied)
        self.assertEqual(failed.reason, "status_not_ok")
        self.assertEqual(failed.selected_evidence_ids, ())
        self.assertIs(failed.calculation_operands, operands)
        self.assertIs(failed.calculation_plan, plan)
        self.assertIs(failed.calculation_result, failed_result)

    def test_dependency_alignment_keeps_complete_direct_difference_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_gain",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "label": "translation gain",
                            "concept": "translation_gain",
                            "raw_value": "0",
                            "raw_unit": "million",
                            "normalized_value": 0.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "ev_stale_gain",
                        }
                    },
                },
            },
            {
                "task_id": "task_loss",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "label": "translation loss",
                            "concept": "translation_loss",
                            "raw_value": "906,120",
                            "raw_unit": "million",
                            "normalized_value": 906_120_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "ev_loss",
                        }
                    },
                },
            },
            {
                "task_id": "task_net",
                "metric_family": "concept_difference",
                "metric_label": "translation net effect",
                "operation_family": "difference",
                "status": "ok",
                "calculation_operands": [
                    {
                        "operand_id": "op_gain",
                        "label": "translation gain",
                        "matched_operand_label": "translation gain",
                        "matched_operand_concept": "translation_gain",
                        "matched_operand_role": "minuend",
                        "raw_value": "573,884",
                        "raw_unit": "million",
                        "normalized_value": 573_884_000_000.0,
                        "normalized_unit": "KRW",
                        "table_source_id": "notes::table:1",
                        "source_row_id": "ev_gain",
                        "source_row_ids": ["ev_gain"],
                    },
                    {
                        "operand_id": "op_loss",
                        "label": "translation loss",
                        "matched_operand_label": "translation loss",
                        "matched_operand_concept": "translation_loss",
                        "matched_operand_role": "subtrahend",
                        "raw_value": "906,120",
                        "raw_unit": "million",
                        "normalized_value": 906_120_000_000.0,
                        "normalized_unit": "KRW",
                        "table_source_id": "notes::table:1",
                        "source_row_id": "ev_loss",
                        "source_row_ids": ["ev_loss"],
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "subtract",
                    "ordered_operand_ids": ["op_gain", "op_loss"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "op_gain"},
                        {"variable": "B", "operand_id": "op_loss"},
                    ],
                    "formula": "A - B",
                    "result_unit": "",
                },
                "calculation_result": {
                    "status": "ok",
                    "result_value": -332_236_000_000.0,
                    "result_unit": "million",
                    "rendered_value": "-332,236 million",
                },
            },
        ]
        state = {
            "query": "calculate translation net effect",
            "calc_subtasks": [
                {"task_id": "task_gain", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_loss", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {
                    "task_id": "task_net",
                    "metric_family": "concept_difference",
                    "operation_family": "difference",
                    "required_operands": [
                        {
                            "label": "translation gain",
                            "concept": "translation_gain",
                            "role": "minuend",
                            "required": True,
                        },
                        {
                            "label": "translation loss",
                            "concept": "translation_loss",
                            "role": "subtrahend",
                            "required": True,
                        },
                    ],
                },
            ],
        }
        projection = {"calculation_operands": []}
        original_inputs = deepcopy((ordered_results, state, projection))
        original_rows = tuple(ordered_results)

        with (
            patch.object(
                financial_graph_calculation,
                "build_runtime_deterministic_operation_plan",
                wraps=financial_graph_calculation.build_runtime_deterministic_operation_plan,
            ) as raw_plan_builder,
            patch.object(
                agent,
                "_run_calculation_candidate_input",
                wraps=agent._run_calculation_candidate_input,
            ) as run_candidate_input,
            patch.object(
                agent,
                "_compact_ratio_answer",
                wraps=agent._compact_ratio_answer,
            ) as format_ratio,
        ):
            aligned = agent._align_lookup_results_with_dependency_projection(
                ordered_results,
                state,
                projection,
            )

        raw_plan_builder.assert_not_called()
        run_candidate_input.assert_not_called()
        format_ratio.assert_not_called()
        self.assertIs(aligned, ordered_results)
        self.assertEqual((ordered_results, state, projection), original_inputs)
        self.assertTrue(all(row is original for row, original in zip(ordered_results, original_rows)))

        net_row = next(row for row in aligned if row["task_id"] == "task_net")
        self.assertNotIn("aligned_from_source_task_slots", net_row)
        self.assertEqual(net_row["calculation_result"]["result_value"], -332_236_000_000.0)
        self.assertEqual(net_row["calculation_operands"][0]["raw_value"], "573,884")

    def test_aggregate_realigns_stale_difference_row_from_table_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = None
        state = {
            "query": "calculate translation net effect",
            "calc_subtasks": [
                {"task_id": "task_gain", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {"task_id": "task_loss", "metric_family": "concept_lookup", "operation_family": "lookup"},
                {
                    "task_id": "task_net",
                    "metric_family": "concept_difference",
                    "metric_label": "translation net effect",
                    "operation_family": "difference",
                    "required_operands": [
                        {
                            "label": "translation gain",
                            "concept": "translation_gain",
                            "role": "minuend",
                            "required": True,
                        },
                        {
                            "label": "translation loss",
                            "concept": "translation_loss",
                            "role": "subtrahend",
                            "required": True,
                        },
                    ],
                },
            ],
            "active_subtask": {
                "task_id": "task_net",
                "metric_family": "concept_difference",
                "metric_label": "translation net effect",
                "operation_family": "difference",
                "required_operands": [
                    {
                        "label": "translation gain",
                        "concept": "translation_gain",
                        "role": "minuend",
                        "required": True,
                    },
                    {
                        "label": "translation loss",
                        "concept": "translation_loss",
                        "role": "subtrahend",
                        "required": True,
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_gain",
                    "metric_family": "concept_lookup",
                    "metric_label": "translation gain",
                    "operation_family": "lookup",
                    "answer": "translation gain is 0백만원.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "0백만원",
                        "result_value": 0.0,
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "translation gain",
                                "concept": "translation_gain",
                                "raw_value": "0",
                                "raw_unit": "백만원",
                                "normalized_value": 0.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "0백만원",
                                "source_row_id": "ev_stale_gain",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_loss",
                    "metric_family": "concept_lookup",
                    "metric_label": "translation loss",
                    "operation_family": "lookup",
                    "answer": "translation loss is 906,120백만원.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "906,120백만원",
                        "result_value": 906_120_000_000.0,
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "translation loss",
                                "concept": "translation_loss",
                                "raw_value": "906,120",
                                "raw_unit": "백만원",
                                "normalized_value": 906_120_000_000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "906,120백만원",
                                "source_row_id": "ev_loss",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_net",
                    "metric_family": "concept_difference",
                    "metric_label": "translation net effect",
                    "operation_family": "difference",
                    "answer": "-906,120백만원",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": -906_120_000_000.0,
                        "result_unit": "백만원",
                        "rendered_value": "-906,120백만원",
                        "answer_slots": {
                            "operation_family": "difference",
                            "components_by_role": {
                                "minuend": [
                                    {
                                        "status": "ok",
                                        "role": "minuend",
                                        "label": "translation gain",
                                        "concept": "translation_gain",
                                        "raw_value": "0",
                                        "raw_unit": "백만원",
                                        "normalized_value": 0.0,
                                        "normalized_unit": "KRW",
                                        "source_row_id": "task_output:task_gain",
                                    }
                                ],
                                "subtrahend": [
                                    {
                                        "status": "ok",
                                        "role": "subtrahend",
                                        "label": "translation loss",
                                        "concept": "translation_loss",
                                        "raw_value": "906,120",
                                        "raw_unit": "백만원",
                                        "normalized_value": 906_120_000_000.0,
                                        "normalized_unit": "KRW",
                                        "source_row_id": "task_output:task_loss",
                                    }
                                ],
                            },
                        },
                    },
                },
            ],
            "evidence_items": [
                {
                    "evidence_id": "ev_translation_table",
                    "claim": "translation gain 573,884백만원; translation loss 906,120백만원",
                    "raw_row_text": "translation gain 573,884백만원; translation loss 906,120백만원",
                    "metadata": {
                        "unit_hint": "백만원",
                        "table_source_id": "notes::table:1",
                        "table_row_labels_text": "translation gain\ntranslation loss",
                        "table_value_labels_text": "translation gain 573,884\ntranslation loss 906,120",
                        "year": 2023,
                    },
                }
            ],
            "tasks": [],
            "artifacts": [],
            "plan_loop_count": 2,
            "selected_claim_ids": [],
        }

        realigned = agent._realign_period_comparison_results_from_table_label_context(
            state["subtask_results"],
            state,
            state["evidence_items"],
        )
        aggregate_projection = agent._rebuild_aggregate_projection(realigned, "-332,236백만원")
        aligned = agent._align_lookup_results_with_dependency_projection(
            realigned,
            state,
            aggregate_projection,
        )

        net_row = next(row for row in aligned if row["task_id"] == "task_net")
        self.assertTrue(net_row.get("period_comparison_recovered_from_table_label_context"))
        self.assertEqual(net_row["calculation_result"]["result_value"], -332_236_000_000.0)
        self.assertEqual(net_row["calculation_operands"][0]["raw_value"], "573,884")
        self.assertEqual(
            net_row["calculation_result"]["answer_slots"]["components_by_role"]["minuend"][0]["raw_value"],
            "573,884",
        )

    def test_dependency_output_preserves_consistent_krw_unit_over_table_hint(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        numerator = 1_992_636_000_000.0
        denominator = 9_670_643_576_585.0
        state = {
            "query": "calculate expense to revenue ratio",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "expense ratio",
                "operation_family": "ratio",
            },
            "evidence_items": [
                {
                    "evidence_id": "ev_denominator",
                    "raw_row_text": "revenue 9,670,643,576,585",
                    "metadata": {
                        "block_type": "table",
                        "unit_hint": "천원",
                        "table_value_labels_text": "revenue 9,670,643,576,585",
                    },
                }
            ],
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {
                        "operand_id": "op_numerator",
                        "label": "expense",
                        "raw_value": "1,992,636",
                        "raw_unit": "백만원",
                        "normalized_value": numerator,
                        "normalized_unit": "KRW",
                        "matched_operand_role": "numerator",
                    },
                    {
                        "operand_id": "op_denominator",
                        "label": "revenue",
                        "raw_value": "9,670,643,576,585",
                        "raw_unit": "원",
                        "normalized_value": denominator,
                        "normalized_unit": "KRW",
                        "matched_operand_role": "denominator",
                        "source_row_id": "task_output:task_revenue",
                        "source_row_ids": ["task_output:task_revenue", "ev_denominator"],
                        "dependency_resolved": True,
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "ratio",
                    "ordered_operand_ids": ["op_numerator", "op_denominator"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "op_numerator"},
                        {"variable": "B", "operand_id": "op_denominator"},
                    ],
                    "formula": "((A) / (B)) * 100",
                    "result_unit": "%",
                },
                "calculation_result": {},
            },
        }

        gate_calls = []
        unit_calls = []
        current_gate = financial_graph_calculation.dependency_task_output_has_consistent_krw_unit
        current_unit_coercion = financial_operand_resolution.coerce_operand_unit_from_evidence

        def record_gate(row):
            result = current_gate(row)
            gate_calls.append((inspect.currentframe().f_back.f_code.co_name, deepcopy(row), result))
            return result

        def record_unit_coercion(*, raw_value, raw_unit, evidence_item):
            unit_calls.append((raw_value, raw_unit, evidence_item))
            return current_unit_coercion(
                raw_value=raw_value,
                raw_unit=raw_unit,
                evidence_item=evidence_item,
            )

        with (
            patch.object(
                financial_graph_calculation,
                "dependency_task_output_has_consistent_krw_unit",
                new=record_gate,
            ),
            patch.object(
                financial_operand_resolution,
                "dependency_task_output_has_consistent_krw_unit",
                new=record_gate,
            ),
            patch.object(
                financial_graph_calculation,
                "coerce_operand_unit_from_evidence",
                new=record_unit_coercion,
            ),
        ):
            result_state = agent._execute_calculation(state)
        trace = result_state["resolved_calculation_trace"]
        result = trace["calculation_result"]
        denominator_row = next(
            row for row in trace["calculation_operands"] if row["operand_id"] == "op_denominator"
        )

        self.assertEqual(
            [
                (
                    caller,
                    row.get("operand_id"),
                    bool(row.get("dependency_resolved")),
                    row.get("source_row_id"),
                    accepted,
                )
                for caller, row, accepted in gate_calls
            ],
            [
                ("_coerce_operand_row_from_evidence", "op_numerator", False, None, False),
                (
                    "_coerce_operand_row_from_evidence",
                    "op_denominator",
                    True,
                    "task_output:task_revenue",
                    True,
                ),
                ("repair_krw_operand_units_from_table_metadata", "op_numerator", False, None, False),
                (
                    "repair_krw_operand_units_from_table_metadata",
                    "op_denominator",
                    True,
                    "task_output:task_revenue",
                    True,
                ),
            ],
        )
        self.assertEqual(
            [(raw_value, raw_unit) for raw_value, raw_unit, _evidence_item in unit_calls],
            [("1,992,636", "백만원")],
        )
        self.assertAlmostEqual(result["result_value"], (numerator / denominator) * 100, places=6)
        self.assertEqual(denominator_row["raw_unit"], "원")
        self.assertEqual(denominator_row["normalized_value"], denominator)

        numerator_row = state["resolved_calculation_trace"]["calculation_operands"][0]
        with (
            patch.object(
                financial_graph_calculation,
                "dependency_task_output_has_consistent_krw_unit",
                side_effect=RuntimeError("dependency unit gate failed"),
            ),
            patch.object(
                financial_graph_calculation,
                "coerce_operand_unit_from_evidence",
            ) as later_unit_coercion,
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency unit gate failed"):
                agent._coerce_operand_row_from_evidence(numerator_row, None)
        later_unit_coercion.assert_not_called()

        with (
            patch.object(
                financial_operand_resolution,
                "dependency_task_output_has_consistent_krw_unit",
                side_effect=RuntimeError("dependency unit gate failed"),
            ),
            patch.object(financial_operand_resolution, "_normalise_operand_value") as later_normalizer,
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency unit gate failed"):
                financial_operand_resolution.repair_krw_operand_units_from_table_metadata(
                    [numerator_row],
                    state["evidence_items"],
                )
        later_normalizer.assert_not_called()

    def test_formula_task_can_recover_direct_target_metric_row(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence = {
            "evidence_id": "ev_target",
            "source_anchor": "[company | year | management discussion]",
            "claim": "target metric 1,701,152",
            "quote_span": "target metric 1,701,152",
            "metadata": {
                "block_type": "table",
                "row_label": "target metric",
                "semantic_label": "target metric",
                "unit_hint": "백만원",
                "year": 2023,
                "structured_cells": [
                    {
                        "value_text": "1,701,152",
                        "unit_hint": "백만원",
                        "column_headers": ["2023"],
                    }
                ],
            },
        }

        row, operand = agent._direct_target_metric_operand_from_evidence(
            {
                "active_subtask": {
                    "task_id": "task_metric",
                    "metric_family": "concept_sum",
                    "metric_label": "target metric",
                    "operation_family": "sum",
                }
            },
            [evidence],
        )

        self.assertEqual(operand["label"], "target metric")
        self.assertEqual(row["raw_value"], "1,701,152")
        self.assertEqual(row["raw_unit"], "백만원")
        self.assertEqual(row["normalized_value"], 1_701_152_000_000.0)
        self.assertTrue(row["direct_target_metric_lookup"])

    def test_formula_task_can_recover_direct_target_metric_from_retrieved_doc_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        doc = SimpleNamespace(
            page_content="target metric 1,701,152",
            metadata={
                "section_path": "management discussion",
                "block_type": "table",
                "row_label": "target metric",
                "semantic_label": "target metric",
                "unit_hint": "백만원",
                "year": 2023,
                "structured_cells": [
                    {
                        "value_text": "1,701,152",
                        "unit_hint": "백만원",
                        "column_headers": ["2023"],
                    }
                ],
            },
        )
        evidence_pool = agent._ratio_operand_context_evidence_from_docs([(doc, 1.0)], max_docs=1)

        row, operand = agent._direct_target_metric_operand_from_evidence(
            {
                "active_subtask": {
                    "task_id": "task_metric",
                    "metric_family": "concept_sum",
                    "metric_label": "target metric",
                    "operation_family": "sum",
                }
            },
            evidence_pool,
        )

        self.assertEqual(operand["label"], "target metric")
        self.assertEqual(row["raw_value"], "1,701,152")
        self.assertEqual(row["raw_unit"], "백만원")
        self.assertEqual(row["normalized_value"], 1_701_152_000_000.0)
        self.assertTrue(row["direct_target_metric_lookup"])

    def test_formula_task_can_recover_direct_target_metric_from_table_value_labels(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        doc = SimpleNamespace(
            page_content="target metric | 1,701,152 | 1,303,065 | 398,087",
            metadata={
                "company": "Example",
                "year": 2023,
                "section_path": "management discussion",
                "block_type": "table",
                "statement_type": "mda",
                "unit_hint": "백만원",
                "table_row_labels_text": "증감\ntarget metric\noperating income",
                "table_value_labels_text": (
                    "target metric 1,701,152\n"
                    "target metric 1,303,065\n"
                    "target metric 398,087\n"
                    "operating income 1,163,112"
                ),
            },
        )
        evidence_pool = agent._ratio_operand_context_evidence_from_docs([(doc, 1.0)], max_docs=1)

        row, operand = agent._direct_target_metric_operand_from_evidence(
            {
                "active_subtask": {
                    "task_id": "task_metric",
                    "metric_family": "concept_sum",
                    "metric_label": "target metric",
                    "operation_family": "sum",
                }
            },
            evidence_pool,
        )

        self.assertEqual(operand["label"], "target metric")
        self.assertEqual(row["raw_value"], "1,701,152")
        self.assertEqual(row["raw_unit"], "백만원")
        self.assertEqual(row["normalized_value"], 1_701_152_000_000.0)
        self.assertTrue(row["direct_target_metric_lookup"])

    def test_direct_target_metric_prefers_context_matching_consolidation_scope(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        generic_doc = SimpleNamespace(
            page_content="target metric | 43,248 | 52,927 | -9,679",
            metadata={
                "company": "Example",
                "year": 2023,
                "section_path": "management discussion",
                "block_type": "table",
                "statement_type": "mda",
                "unit_hint": "백만원",
                "local_heading": "major performance indicators",
                "table_row_labels_text": "증감\ntarget metric",
                "table_value_labels_text": "target metric 43,248\ntarget metric 52,927\ntarget metric -9,679",
            },
        )
        consolidated_doc = SimpleNamespace(
            page_content="target metric | 1,701,152 | 1,303,065 | 398,087",
            metadata={
                "company": "Example",
                "year": 2023,
                "section_path": "management discussion",
                "block_type": "table",
                "statement_type": "mda",
                "unit_hint": "백만원",
                "local_heading": "연결 영업실적",
                "table_context": "연결회사의 주요 경영지표",
                "table_row_labels_text": "증감\ntarget metric",
                "table_value_labels_text": (
                    "target metric 1,701,152\n"
                    "target metric 1,303,065\n"
                    "target metric 398,087"
                ),
            },
        )
        evidence_pool = agent._ratio_operand_context_evidence_from_docs(
            [(generic_doc, 1.0), (consolidated_doc, 0.9)],
            max_docs=2,
        )

        row, _operand = agent._direct_target_metric_operand_from_evidence(
            {
                "query": "2023년 연결기준 target metric을 답해 줘.",
                "report_scope": {},
                "active_subtask": {
                    "task_id": "task_metric",
                    "metric_family": "concept_sum",
                    "metric_label": "target metric",
                    "operation_family": "sum",
                },
            },
            evidence_pool,
        )

        self.assertEqual(row["raw_value"], "1,701,152")
        self.assertEqual(row["normalized_value"], 1_701_152_000_000.0)

    def test_scope_filter_uses_table_context_for_unknown_metadata_scope(self) -> None:
        matching_context = {
            "metadata": {
                "consolidation_scope": "unknown",
                "section_path": "management discussion",
                "local_heading": "operating performance",
                "table_context": "연결 기준 주요 지표",
            }
        }
        opposing_context = {
            "metadata": {
                "consolidation_scope": "unknown",
                "section_path": "management discussion",
                "local_heading": "별도 기준 주요 지표",
            }
        }

        self.assertFalse(evidence_item_conflicts_requested_scope(matching_context, "consolidated"))
        self.assertTrue(evidence_item_conflicts_requested_scope(opposing_context, "consolidated"))

    def test_lookup_preference_uses_requested_scope_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested_context = {"keep": "lookup"}
        current_rows = [
            {
                "operand_id": "primary_value",
                "evidence_id": "ev_generic",
                "source_row_id": "ev_generic",
                "source_row_ids": ["ev_generic"],
                "label": "target metric",
                "raw_value": "43,248",
                "raw_unit": "백만원",
                "normalized_value": 43_248_000_000.0,
                "normalized_unit": "KRW",
                "matched_operand_label": "target metric",
                "matched_operand_role": "primary_value",
                "nested_context": nested_context,
            }
        ]
        evidence_items = [
            {
                "evidence_id": "ev_generic",
                "claim": "target metric 43,248",
                "metadata": {
                    "block_type": "table",
                    "unit_hint": "백만원",
                    "year": 2023,
                    "local_heading": "major performance indicators",
                    "table_value_labels_text": "target metric 43,248\ntarget metric 52,927",
                },
            },
            {
                "evidence_id": "ev_consolidated",
                "claim": "target metric 1,701,152",
                "metadata": {
                    "block_type": "table",
                    "unit_hint": "백만원",
                    "year": 2023,
                    "local_heading": "연결 기준 operating performance",
                    "table_value_labels_text": "target metric 1,701,152\ntarget metric 1,303,065",
                },
            },
        ]

        current_rows_before = deepcopy(current_rows)
        evidence_items_before = deepcopy(evidence_items)
        resolver_patch = patch.object(
            financial_graph_calculation,
            "resolve_direct_structured_preferred_slot_adoption",
            wraps=financial_graph_calculation.resolve_direct_structured_preferred_slot_adoption,
        )
        resolve_adoption = resolver_patch.start()
        self.addCleanup(resolver_patch.stop)
        rows = agent._prefer_direct_structured_lookup_evidence_rows(
            current_rows,
            evidence_items=evidence_items,
            required_operands=[{"label": "target metric", "role": "primary_value", "required": True}],
            operation_family="lookup",
            state={"query": "2023년 연결기준 target metric을 답해 줘.", "report_scope": {}},
        )

        resolver_patch.stop()
        resolve_adoption.assert_called_once()
        adoption_input = resolve_adoption.call_args.args[0]
        self.assertEqual(adoption_input.operation_family, "lookup")
        self.assertEqual(adoption_input.normalized_peer_raw_units, set())
        self.assertGreater(adoption_input.preferred_score, adoption_input.current_score)
        self.assertEqual(rows[0]["source_row_id"], "ev_consolidated")
        self.assertEqual(rows[0]["raw_value"], "1,701,152")
        self.assertIs(rows[0]["nested_context"], nested_context)
        self.assertEqual(current_rows, current_rows_before)
        self.assertEqual(evidence_items, evidence_items_before)

        with patch.object(
            agent,
            "_best_direct_lookup_slot_from_evidence_pool",
            return_value=({}, 0.0),
        ) as select_preferred, patch.object(
            financial_graph_calculation,
            "score_direct_structured_lookup_evidence",
        ) as score_current, patch.object(
            financial_graph_calculation,
            "resolve_direct_structured_preferred_slot_adoption",
        ) as resolve_adoption:
            unchanged = agent._prefer_direct_structured_lookup_evidence_rows(
                current_rows,
                evidence_items=evidence_items,
                required_operands=[{"label": "target metric", "role": "primary_value", "required": True}],
                operation_family="lookup",
                state={},
            )

        self.assertIsNone(select_preferred.call_args.kwargs["preferred_raw_units"])
        score_current.assert_not_called()
        resolve_adoption.assert_not_called()
        self.assertIsNot(unchanged, current_rows)
        self.assertIsNot(unchanged[0], current_rows[0])
        self.assertIs(unchanged[0]["nested_context"], nested_context)
        self.assertEqual(unchanged, current_rows)

        events = []
        adoption_resolver = financial_graph_calculation.resolve_direct_structured_preferred_slot_adoption
        score_resolver = financial_graph_calculation.score_direct_structured_lookup_evidence
        preferred_slot = {
            **current_rows[0],
            "evidence_id": "ev_consolidated",
            "source_row_id": "ev_consolidated",
            "source_row_ids": ["ev_consolidated"],
            "raw_value": "1,701,152",
            "normalized_value": 1_701_152_000_000.0,
        }

        def _select_preferred(*_args, **_kwargs):
            events.append("select_preferred")
            return preferred_slot, 10.0

        def _score_current(score_input):
            events.append("score_current")
            return score_resolver(score_input)

        def _resolve_adoption(selection_input):
            events.append("resolve_adoption")
            return adoption_resolver(selection_input)

        with patch.object(
            agent,
            "_best_direct_lookup_slot_from_evidence_pool",
            side_effect=_select_preferred,
        ), patch.object(
            financial_graph_calculation,
            "score_direct_structured_lookup_evidence",
            side_effect=_score_current,
        ), patch.object(
            financial_graph_calculation,
            "resolve_direct_structured_preferred_slot_adoption",
            side_effect=_resolve_adoption,
        ):
            preferred = agent._prefer_direct_structured_lookup_evidence_rows(
                current_rows,
                evidence_items=evidence_items,
                required_operands=[{"label": "target metric", "role": "primary_value", "required": True}],
                operation_family="lookup",
                state={},
            )

        self.assertEqual(events, ["select_preferred", "score_current", "resolve_adoption"])
        self.assertEqual(preferred[0]["source_row_id"], "ev_consolidated")

    def test_lookup_recovery_can_use_seed_retrieved_doc_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        generic_doc = SimpleNamespace(
            page_content="target metric | 43,248 | 52,927",
            metadata={
                "company": "Example",
                "year": 2023,
                "section_path": "management discussion",
                "block_type": "table",
                "statement_type": "mda",
                "unit_hint": "백만원",
                "local_heading": "major performance indicators",
                "table_value_labels_text": "target metric 43,248\ntarget metric 52,927",
            },
        )
        consolidated_doc = SimpleNamespace(
            page_content="target metric | 1,701,152 | 1,303,065",
            metadata={
                "company": "Example",
                "year": 2023,
                "section_path": "management discussion",
                "block_type": "table",
                "statement_type": "mda",
                "unit_hint": "백만원",
                "local_heading": "연결 기준 operating performance",
                "table_value_labels_text": "target metric 1,701,152\ntarget metric 1,303,065",
            },
        )
        ordered_results = [
            {
                "task_id": "task_metric",
                "metric_family": "source_stated_metric",
                "metric_label": "target metric",
                "operation_family": "lookup",
                "status": "ok",
                "answer": "target metric 43,248백만원",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "label": "target metric",
                            "role": "primary_value",
                            "raw_value": "43,248",
                            "raw_unit": "백만원",
                            "normalized_value": 43_248_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "ev_generic",
                            "source_row_ids": ["ev_generic"],
                        }
                    },
                },
            }
        ]
        state = {
            "query": "2023년 연결기준 target metric을 답해 줘.",
            "report_scope": {},
            "calc_subtasks": [
                {
                    "task_id": "task_metric",
                    "metric_family": "source_stated_metric",
                    "metric_label": "target metric",
                    "operation_family": "lookup",
                    "required_operands": [
                        {"label": "target metric", "role": "primary_value", "required": True}
                    ],
                }
            ],
            "seed_retrieved_docs": [(generic_doc, 1.0), (consolidated_doc, 0.9)],
            "retrieved_docs": [],
            "evidence_items": [],
            "runtime_evidence": [],
        }

        recovered = agent._recover_lookup_results_from_sibling_table_evidence(ordered_results, state)
        slot = recovered[0]["calculation_result"]["answer_slots"]["primary_value"]

        self.assertEqual(slot["raw_value"], "1,701,152")
        self.assertTrue(recovered[0]["recovered_from_sibling_table_evidence"])

    def test_lookup_task_can_recover_direct_target_metric_from_table_value_labels(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        doc = SimpleNamespace(
            page_content="target metric | 1,701,152 | 1,303,065 | 398,087",
            metadata={
                "company": "Example",
                "year": 2023,
                "section_path": "management discussion",
                "block_type": "table",
                "statement_type": "mda",
                "unit_hint": "백만원",
                "table_row_labels_text": "증감\ntarget metric",
                "table_value_labels_text": "target metric 1,701,152\ntarget metric 1,303,065\ntarget metric 398,087",
            },
        )
        evidence_pool = agent._ratio_operand_context_evidence_from_docs([(doc, 1.0)], max_docs=1)

        row, operand = agent._direct_target_metric_operand_from_evidence(
            {
                "active_subtask": {
                    "task_id": "task_metric",
                    "metric_family": "source_stated_metric",
                    "metric_label": "target metric",
                    "operation_family": "lookup",
                }
            },
            evidence_pool,
        )

        self.assertEqual(operand["label"], "target metric")
        self.assertEqual(row["raw_value"], "1,701,152")
        self.assertTrue(row["direct_target_metric_lookup"])

    def test_ratio_ontology_plan_prefers_matching_operand_role(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "query": "calculate business loss as a percentage of total operating income",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "loss to operating income ratio",
                "operation_family": "ratio",
                "required_operands": [
                    {
                        "role": "numerator_1",
                        "concept": "operating_loss",
                        "label": "business operating loss",
                    },
                    {
                        "role": "denominator_1",
                        "concept": "operating_income",
                        "label": "operating income",
                    },
                ],
            },
        }
        operands = [
            {
                "operand_id": "num",
                "label": "business operating loss",
                "matched_operand_role": "numerator_1",
                "matched_operand_concept": "operating_loss",
                "normalized_value": -580.0,
            },
            {
                "operand_id": "generic",
                "label": "business operating loss",
                "normalized_value": -1070.0,
            },
            {
                "operand_id": "den",
                "label": "operating income",
                "matched_operand_label": "operating income",
                "matched_operand_role": "denominator_1",
                "matched_operand_concept": "operating_income",
                "normalized_value": 1900.0,
            },
        ]

        plan = financial_calculation_execution.build_deterministic_ontology_plan(
            state["active_subtask"],
            operands,
            metric_key="concept_ratio",
        )

        self.assertIsNotNone(plan)
        self.assertEqual(plan["ordered_operand_ids"], ["num", "den"])

    def test_absolute_ratio_query_renders_positive_magnitude(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "query": "calculate the absolute magnitude as a percentage",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "loss to income ratio",
                "operation_family": "ratio",
            },
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {
                        "operand_id": "num",
                        "label": "loss",
                        "raw_value": "(580)",
                        "raw_unit": "",
                        "normalized_value": -580.0,
                        "normalized_unit": "COUNT",
                        "matched_operand_role": "numerator_1",
                    },
                    {
                        "operand_id": "den",
                        "label": "income",
                        "raw_value": "1900",
                        "raw_unit": "",
                        "normalized_value": 1900.0,
                        "normalized_unit": "COUNT",
                        "matched_operand_role": "denominator_1",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "ratio",
                    "ordered_operand_ids": ["num", "den"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "num"},
                        {"variable": "B", "operand_id": "den"},
                    ],
                    "formula": "((A) / (B)) * 100",
                    "result_unit": "%",
                },
                "calculation_result": {},
            },
        }

        result_state = agent._execute_calculation(state)
        result = result_state["resolved_calculation_trace"]["calculation_result"]

        self.assertAlmostEqual(result["result_value"], 30.526315789473685)
        self.assertEqual(result["rendered_value"], "30.53%")

    def test_dependency_projection_recalculates_planless_ratio_from_best_lookup_slot(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_other_numerator",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "numerator",
                            "label": "other numerator",
                            "concept": "other_numerator",
                            "raw_value": "900",
                            "raw_unit": "million",
                            "normalized_value": 900_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_other",
                        },
                    },
                },
            },
            {
                "task_id": "task_numerator",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "numerator",
                            "label": "target numerator",
                            "concept": "target_numerator",
                            "raw_value": "180",
                            "raw_unit": "million",
                            "normalized_value": 180_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_strong_numerator",
                            "source_row_ids": ["row_strong_numerator"],
                            "value_role": "aggregate",
                            "aggregation_stage": "final",
                        },
                    },
                },
            },
            {
                "task_id": "task_denominator",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "denominator",
                            "label": "target denominator",
                            "concept": "target_denominator",
                            "raw_value": "2,000",
                            "raw_unit": "million",
                            "normalized_value": 2_000_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_denominator",
                            "source_row_ids": ["row_denominator"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "margin drag",
                "operation_family": "ratio",
                "answer": "margin drag is 7.50%p.",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "result_value": 7.5,
                    "result_unit": "%p",
                    "rendered_value": "7.50%p",
                    "formatted_result": "margin drag is 7.50%p.",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "metric_label": "margin drag",
                        "components_by_role": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "role": "numerator",
                                    "label": "target numerator",
                                    "concept": "target_numerator",
                                    "raw_value": "150",
                                    "raw_unit": "million",
                                    "normalized_value": 150_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_detail_numerator",
                                }
                            ],
                            "denominator": [
                                {
                                    "status": "ok",
                                    "role": "denominator",
                                    "label": "target denominator",
                                    "concept": "target_denominator",
                                    "raw_value": "2,000",
                                    "raw_unit": "million",
                                    "normalized_value": 2_000_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_denominator",
                                }
                            ],
                        },
                    },
                },
            },
        ]

        stale_subtask = {
            "task_id": "task_stale",
            "status": "ok",
            "answer": "stale aggregate 999",
            "calculation_result": {"status": "ok", "rendered_value": "999"},
        }
        state = {
            "query": "calculate margin drag",
            "answer": "stale aggregate 999",
            "structured_result": {
                "formatted_result": "stale aggregate 999",
                "subtask_results": [stale_subtask],
            },
            "subtask_results": [stale_subtask],
            "calc_subtasks": [
                {"task_id": "task_other_numerator", "operation_family": "lookup"},
                {"task_id": "task_numerator", "operation_family": "lookup"},
                {"task_id": "task_denominator", "operation_family": "lookup"},
                {"task_id": "task_ratio", "operation_family": "ratio", "metric_label": "margin drag"},
            ],
        }
        projection = {"calculation_operands": []}
        original_inputs = deepcopy((ordered_results, state, projection))
        original_rows = tuple(ordered_results)
        candidate_runs = []
        formatter_outputs = []
        original_run = agent._run_calculation_candidate_input
        original_formatter = agent._compact_ratio_answer

        def record_candidate_run(candidate_input):
            candidate_runs.append(original_run(candidate_input))
            return candidate_runs[-1]

        def record_formatted_answer(formatter_state, calculation_result, **kwargs):
            result_snapshot = deepcopy(calculation_result)
            formatted_answer = original_formatter(formatter_state, calculation_result, **kwargs)
            formatter_outputs.append((result_snapshot, formatted_answer))
            return formatted_answer

        with (
            patch.object(
                financial_graph_calculation,
                "build_runtime_deterministic_operation_plan",
                wraps=financial_graph_calculation.build_runtime_deterministic_operation_plan,
            ) as raw_plan_builder,
            patch.object(
                financial_graph_calculation,
                "resolve_deterministic_operation_plan",
                wraps=financial_graph_calculation.resolve_deterministic_operation_plan,
            ) as guarded_plan_resolver,
            patch.object(
                agent,
                "_run_calculation_candidate_input",
                side_effect=record_candidate_run,
            ) as run_candidate_input,
            patch.object(
                agent,
                "_run_calculation_candidate",
                wraps=agent._run_calculation_candidate,
            ) as legacy_run_candidate,
            patch.object(
                agent,
                "_compact_ratio_answer",
                side_effect=record_formatted_answer,
            ) as format_ratio,
        ):
            aligned = agent._align_lookup_results_with_dependency_projection(
                ordered_results,
                state,
                projection,
            )

        raw_plan_builder.assert_called_once()
        guarded_plan_resolver.assert_not_called()
        run_candidate_input.assert_called_once()
        legacy_run_candidate.assert_not_called()
        format_ratio.assert_called_once()

        ratio_row = aligned[-1]
        candidate_input = run_candidate_input.call_args.args[0]
        canonical_projection = candidate_runs[0].projection
        formatter_state, _ = format_ratio.call_args.args
        formatter_kwargs = format_ratio.call_args.kwargs
        formatter_result, formatted_answer = formatter_outputs[0]
        expected_result = dict(canonical_projection.calculation_result)
        expected_result["formatted_result"] = formatted_answer
        self.assertTrue(ratio_row.get("aligned_from_source_task_slots"))
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "9.00%p")
        self.assertEqual(ratio_row["calculation_operands"], list(canonical_projection.calculation_operands))
        self.assertEqual(ratio_row["calculation_plan"], canonical_projection.calculation_plan)
        self.assertEqual(ratio_row["calculation_result"], expected_result)
        self.assertIs(formatter_state, state)
        self.assertEqual(formatter_result, dict(canonical_projection.calculation_result))
        self.assertEqual(
            {key: candidate_input.active_subtask.get(key) for key in state["calc_subtasks"][-1]},
            state["calc_subtasks"][-1],
        )
        self.assertEqual(candidate_input.query, state["query"])
        self.assertEqual(candidate_input.calculation_operands[0]["raw_value"], "180")
        self.assertEqual(formatter_kwargs["active_subtask"], candidate_input.active_subtask)
        self.assertEqual(
            formatter_kwargs["calculation_operands"],
            list(candidate_input.calculation_operands),
        )
        self.assertEqual(candidate_input.calculation_plan, canonical_projection.calculation_plan)
        self.assertEqual(ratio_row["answer"], formatted_answer)
        numerator = ratio_row["calculation_operands"][0]
        self.assertEqual(numerator["raw_value"], "180")
        self.assertIn("task_output:task_numerator", numerator["source_row_ids"])
        self.assertNotIn("900", ratio_row["answer"])
        self.assertEqual((ordered_results, state, projection), original_inputs)
        self.assertTrue(all(row is original for row, original in zip(ordered_results, original_rows)))

    def test_dependency_projection_recalculates_partial_ratio_from_late_lookup_slot(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_segment",
                "metric_family": "concept_lookup",
                "metric_label": "segment operating loss",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating loss",
                            "concept": "operating_income",
                            "raw_value": "(581,816)",
                            "raw_unit": "million",
                            "normalized_value": -581_816_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "(581,816)million",
                            "source_row_id": "row_segment",
                            "source_row_ids": ["row_segment"],
                        },
                    },
                },
            },
            {
                "task_id": "task_total",
                "metric_family": "concept_lookup",
                "metric_label": "total operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "total operating income",
                            "concept": "operating_income",
                            "raw_value": "1,903,886",
                            "raw_unit": "million",
                            "normalized_value": 1_903_886_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "1,903,886million",
                            "source_row_id": "row_total",
                            "source_row_ids": ["row_total"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment loss to total income ratio",
                "operation_family": "ratio",
                "answer": "insufficient operands",
                "status": "insufficient_operands",
                "calculation_operands": [
                    {
                        "operand_id": "num",
                        "source_row_id": "task_output:task_segment",
                        "source_row_ids": ["task_output:task_segment", "row_segment"],
                        "source_task_id": "task_segment",
                        "label": "segment operating loss",
                        "raw_value": "(581,816)",
                        "raw_unit": "million",
                        "normalized_value": -581_816_000_000.0,
                        "normalized_unit": "KRW",
                        "matched_operand_concept": "operating_income",
                        "matched_operand_role": "numerator_1",
                        "dependency_resolved": True,
                    },
                ],
                "calculation_result": {
                    "status": "insufficient_operands",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "metric_label": "segment loss to total income ratio",
                        "components_by_group": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "role": "numerator_1",
                                    "label": "segment operating loss",
                                    "concept": "operating_income",
                                    "raw_value": "(581,816)",
                                    "raw_unit": "million",
                                    "normalized_value": -581_816_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "task_output:task_segment",
                                }
                            ],
                        },
                    },
                },
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "calculate segment loss to total income ratio",
                "calc_subtasks": [
                    {"task_id": "task_segment", "operation_family": "lookup"},
                    {"task_id": "task_total", "operation_family": "lookup"},
                    {
                        "task_id": "task_ratio",
                        "operation_family": "ratio",
                        "metric_label": "segment loss to total income ratio",
                        "required_operands": [
                            {
                                "role": "numerator_1",
                                "label": "segment operating loss",
                                "concept": "operating_income",
                            },
                        ],
                    },
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = aligned[-1]
        self.assertTrue(ratio_row.get("aligned_from_source_task_slots"))
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "-30.56%")
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertEqual(denominator["raw_value"], "1,903,886")
        self.assertIn("task_output:task_total", denominator["source_row_ids"])

    def test_dependency_projection_uses_table_label_for_missing_ratio_role_before_polluted_lookup_slot(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence = {
            "evidence_id": "ev_table",
            "source_anchor": "[source]",
            "metadata": {
                "unit_hint": "백만원",
                "table_value_labels_text": "total operating income 1,903,886\nother metric 100",
            },
        }
        ordered_results = [
            {
                "task_id": "task_segment",
                "metric_family": "concept_lookup",
                "metric_label": "segment operating loss",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating loss",
                            "concept": "operating_income",
                            "raw_value": "(581,816)",
                            "raw_unit": "million",
                            "normalized_value": -581_816_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_segment",
                            "source_row_ids": ["row_segment"],
                        },
                    },
                },
            },
            {
                "task_id": "task_total",
                "metric_family": "concept_lookup",
                "metric_label": "total operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating loss",
                            "concept": "operating_income",
                            "raw_value": "(581,816)",
                            "raw_unit": "million",
                            "normalized_value": -581_816_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "task_output:task_segment",
                            "source_row_ids": ["task_output:task_segment", "row_segment"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment loss to total income ratio",
                "operation_family": "ratio",
                "status": "insufficient_operands",
                "calculation_operands": [
                    {
                        "operand_id": "num",
                        "source_row_id": "task_output:task_segment",
                        "source_row_ids": ["task_output:task_segment", "row_segment"],
                        "source_task_id": "task_segment",
                        "label": "segment operating loss",
                        "raw_value": "(581,816)",
                        "raw_unit": "million",
                        "normalized_value": -581_816_000_000.0,
                        "normalized_unit": "KRW",
                        "matched_operand_concept": "operating_income",
                        "matched_operand_role": "numerator_1",
                    },
                ],
                "calculation_result": {"status": "insufficient_operands"},
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "calculate the absolute segment loss to total income ratio",
                "runtime_evidence": [evidence],
                "calc_subtasks": [
                    {"task_id": "task_segment", "operation_family": "lookup"},
                    {"task_id": "task_total", "operation_family": "lookup"},
                    {
                        "task_id": "task_ratio",
                        "operation_family": "ratio",
                        "metric_label": "segment loss to total income ratio",
                        "required_operands": [
                            {
                                "role": "numerator_1",
                                "label": "segment operating loss",
                                "concept": "operating_income",
                            },
                            {
                                "role": "denominator_1",
                                "label": "total operating income",
                                "concept": "operating_income",
                            },
                        ],
                    },
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = aligned[-1]
        self.assertEqual(ratio_row["status"], "ok")
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertEqual(denominator["raw_value"], "1,903,886")
        self.assertEqual(denominator["source_row_id"], "ev_table")
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "30.56%")

    def test_dependency_projection_prefers_valid_late_lookup_over_table_label_for_missing_ratio_role(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence = {
            "evidence_id": "ev_table",
            "source_anchor": "[source]",
            "metadata": {
                "unit_hint": "million",
                "table_value_labels_text": "total operating income 100\nother metric 50",
            },
        }
        ordered_results = [
            {
                "task_id": "task_segment",
                "metric_family": "concept_lookup",
                "metric_label": "segment operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating income",
                            "concept": "operating_income",
                            "raw_value": "250",
                            "raw_unit": "백만원",
                            "normalized_value": 250_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_segment",
                            "source_row_ids": ["row_segment"],
                        },
                    },
                },
            },
            {
                "task_id": "task_total",
                "metric_family": "concept_lookup",
                "metric_label": "total operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "total operating income",
                            "concept": "operating_income",
                            "raw_value": "1,000",
                            "raw_unit": "million",
                            "normalized_value": 1_000_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_total",
                            "source_row_ids": ["row_total"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share of total operating income",
                "operation_family": "ratio",
                "status": "insufficient_operands",
                "calculation_operands": [
                    {
                        "operand_id": "num",
                        "source_row_id": "task_output:task_segment",
                        "source_row_ids": ["task_output:task_segment", "row_segment"],
                        "source_task_id": "task_segment",
                        "label": "segment operating income",
                        "raw_value": "250",
                        "raw_unit": "million",
                        "normalized_value": 250_000_000.0,
                        "normalized_unit": "KRW",
                        "matched_operand_concept": "operating_income",
                        "matched_operand_role": "numerator_1",
                    },
                ],
                "calculation_result": {"status": "insufficient_operands"},
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "calculate segment share of total operating income",
                "runtime_evidence": [evidence],
                "calc_subtasks": [
                    {"task_id": "task_segment", "operation_family": "lookup"},
                    {"task_id": "task_total", "operation_family": "lookup"},
                    {
                        "task_id": "task_ratio",
                        "operation_family": "ratio",
                        "metric_label": "segment share of total operating income",
                        "required_operands": [
                            {
                                "role": "numerator_1",
                                "label": "segment operating income",
                                "concept": "operating_income",
                            },
                            {
                                "role": "denominator_1",
                                "label": "total operating income",
                                "concept": "operating_income",
                            },
                        ],
                    },
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = aligned[-1]
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertTrue(ratio_row.get("aligned_from_source_task_slots"))
        self.assertEqual(denominator["raw_value"], "1,000")
        self.assertEqual(denominator["source_task_id"], "task_total")
        self.assertIn("task_output:task_total", denominator["source_row_ids"])
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "25%")

    def test_lookup_execution_applies_ontology_magnitude_contract(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        calculation_operands = [
            {
                "operand_id": "op_gain",
                "evidence_id": "gain_cell",
                "source_row_id": "gain_cell",
                "source_row_ids": ["gain_cell"],
                "label": "\uc678\ud654\ud658\uc0b0\uc774\uc775",
                "raw_value": "(573,884)",
                "raw_unit": "\ubc31\ub9cc\uc6d0",
                "normalized_value": -573_884_000_000.0,
                "normalized_unit": "KRW",
                "matched_operand_label": "\uc678\ud654\ud658\uc0b0\uc774\uc775",
                "matched_operand_concept": "foreign_currency_translation_gain",
                "matched_operand_role": "operand",
                "statement_type": "notes",
            }
        ]
        calculation_plan = {
            "status": "ok",
            "mode": "single_value",
            "operation": "lookup",
            "ordered_operand_ids": ["op_gain"],
            "variable_bindings": [{"variable": "A", "operand_id": "op_gain"}],
            "formula": "A",
            "result_unit": "\ubc31\ub9cc\uc6d0",
        }
        state = {
            "query": "lookup translated gain",
            "active_subtask": {
                "task_id": "task_gain",
                "metric_family": "concept_lookup",
                "metric_label": "\uc678\ud654\ud658\uc0b0\uc774\uc775",
                "operation_family": "lookup",
            },
            "resolved_calculation_trace": {
                "calculation_operands": calculation_operands,
                "calculation_plan": calculation_plan,
                "calculation_result": {},
            },
        }

        result = agent._execute_calculation(state)
        trace = _resolve_runtime_calculation_trace(result)
        calculation_result = trace["calculation_result"]
        operand = trace["calculation_operands"][0]

        self.assertEqual(operand["normalized_value"], 573_884_000_000.0)
        self.assertEqual(operand["rendered_value"], "573,884\ubc31\ub9cc\uc6d0")
        self.assertEqual(calculation_result["result_value"], 573_884_000_000.0)
        self.assertEqual(calculation_result["rendered_value"], "573,884\ubc31\ub9cc\uc6d0")

    def test_growth_narrative_prefers_uncovered_parenthetical_focus_variant(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        query = "calculate 2023 growth and summarize Acme(FooBar) impact"
        rows = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "segment revenue growth",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "operation_family": "growth_rate",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "rendered_value": "25%",
                            "normalized_value": 25,
                        },
                        "current_value": {
                            "status": "ok",
                            "label": "segment revenue",
                            "period": "2023",
                            "rendered_value": "125억원",
                            "normalized_value": 12_500_000_000,
                        },
                        "prior_value": {
                            "status": "ok",
                            "label": "segment revenue",
                            "period": "2022",
                            "rendered_value": "100억원",
                            "normalized_value": 10_000_000_000,
                        },
                    },
                },
            },
            {
                "task_id": "task_summary",
                "metric_family": "narrative_summary",
                "metric_label": "impact summary",
                "status": "ok",
                "answer": (
                    "Revenue impact was broad. "
                    "FooBar impact came from integration and operating improvements."
                ),
                "calculation_result": {"operation_family": "narrative_summary"},
            },
        ]

        answer = agent._compose_growth_narrative_answer(
            query=query,
            ordered_results=rows,
            existing_answer="2023 segment revenue was 125억원 versus 100억원, up 25%.",
            evidence_items=[],
        )

        self.assertIsNotNone(answer)
        self.assertIn("FooBar impact", answer["compressed_answer"])

    def test_growth_narrative_preserves_supported_focus_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        query = "calculate 2023 growth and summarize Acme(FooBar) impact"
        rows = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "segment revenue growth",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "operation_family": "growth_rate",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "rendered_value": "25%",
                            "normalized_value": 25,
                        },
                        "current_value": {
                            "status": "ok",
                            "label": "segment revenue",
                            "period": "2023",
                            "rendered_value": "125",
                            "normalized_value": 125,
                        },
                        "prior_value": {
                            "status": "ok",
                            "label": "segment revenue",
                            "period": "2022",
                            "rendered_value": "100",
                            "normalized_value": 100,
                        },
                    },
                },
            },
            {
                "task_id": "task_summary",
                "metric_family": "narrative_summary",
                "metric_label": "impact summary",
                "status": "ok",
                "answer": (
                    "Revenue impact was broad. "
                    "FooBar impact came from operating improvements. "
                    "Additional impact came from consolidation."
                ),
                "calculation_result": {"operation_family": "narrative_summary"},
            },
        ]

        answer = agent._compose_growth_narrative_answer(
            query=query,
            ordered_results=rows,
            existing_answer=(
                "2023 segment revenue was 125 versus 2022 100, up 25%. "
                "FooBar impact came from operating improvements."
            ),
            evidence_items=[],
        )

        self.assertIsNotNone(answer)
        self.assertIn("Additional impact came from consolidation.", answer["compressed_answer"])

    def test_lookup_unit_refinement_prefers_value_local_unit(self) -> None:
        slot = {
            "raw_value": "2,546,649",
            "raw_unit": "천원",
            "normalized_value": 2_546_649_000,
            "normalized_unit": "KRW",
            "rendered_value": "2,546,649천원",
        }
        evidence = {
            "claim": "2,546,649 (천원)",
            "metadata": {"unit_hint": "백만원"},
        }

        refined = refine_lookup_slot_unit_from_evidence(slot, evidence)

        self.assertEqual(refined["raw_unit"], "천원")
        self.assertEqual(refined["normalized_value"], 2_546_649_000)

    def test_compact_ratio_answer_lists_all_component_slots(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        calculation_result = {
            "status": "ok",
            "rendered_value": "42.02%",
            "answer_slots": {
                "operation_family": "ratio",
                "metric_label": "asset funding ratio",
                "primary_value": {"status": "ok", "rendered_value": "42.02%"},
                "components_by_group": {
                    "numerator": [
                        {"label": "short borrowing", "rendered_value": "4,145백만원", "normalized_value": 4_145_000_000, "normalized_unit": "KRW", "raw_unit": "백만원"},
                        {"label": "long borrowing", "rendered_value": "10,121백만원", "normalized_value": 10_121_000_000, "normalized_unit": "KRW", "raw_unit": "백만원"},
                        {"label": "bonds", "rendered_value": "9,490백만원", "normalized_value": 9_490_000_000, "normalized_unit": "KRW", "raw_unit": "백만원"},
                    ],
                    "denominator": [
                        {"label": "tangible assets", "rendered_value": "52,704백만원", "normalized_value": 52_704_000_000, "normalized_unit": "KRW", "raw_unit": "백만원"},
                        {"label": "intangible assets", "rendered_value": "3,834백만원", "normalized_value": 3_834_000_000, "normalized_unit": "KRW", "raw_unit": "백만원"},
                    ],
                },
            },
        }

        answer = agent._compact_ratio_answer({"active_subtask": {"metric_label": "asset funding ratio"}}, calculation_result)

        self.assertIn("asset funding ratio", answer)
        self.assertIn("short borrowing 4,145백만원", answer)
        self.assertIn("long borrowing 10,121백만원", answer)
        self.assertIn("bonds 9,490백만원", answer)
        self.assertIn("tangible assets 52,704백만원", answer)
        self.assertIn("intangible assets 3,834백만원", answer)

    def test_ratio_dependency_source_slot_requires_role_target_match(self) -> None:
        operand = {
            "matched_operand_role": "denominator_1",
            "matched_operand_label": "target asset",
            "matched_operand_concept": "target_asset",
            "source_task_id": "task_borrowing",
        }
        source_slot = {
            "role": "primary_value",
            "label": "source borrowing",
            "concept": "source_borrowing",
            "raw_value": "10,121,033",
            "raw_unit": "million",
            "normalized_value": 10_121_033_000_000.0,
            "normalized_unit": "KRW",
            "value_role": "aggregate",
            "aggregation_stage": "final",
            "source_row_id": "row_borrowing",
            "source_row_ids": ["row_borrowing"],
        }

        self.assertFalse(dependency_operand_can_use_source_slot(operand, source_slot))

    def test_dependency_projection_replaces_collapsed_ratio_role_from_sibling_lookup(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_segment",
                "metric_family": "concept_lookup",
                "metric_label": "segment operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "250",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating income",
                            "concept": "operating_income",
                            "raw_value": "250",
                            "raw_unit": "million",
                            "normalized_value": 250_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_segment",
                            "source_row_ids": ["row_segment"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share of total operating income",
                "operation_family": "ratio",
                "status": "insufficient_operands",
                "calculation_plan": {
                    "status": "incomplete",
                    "mode": "none",
                    "operation": "none",
                    "ordered_operand_ids": [],
                    "variable_bindings": [],
                    "missing_info": ["distinct_ratio_roles"],
                },
                "calculation_result": {
                    "status": "insufficient_operands",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "metric_label": "segment share of total operating income",
                        "components_by_group": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "role": "numerator_1",
                                    "label": "segment operating income",
                                    "concept": "operating_income",
                                    "raw_value": "50",
                                    "raw_unit": "백만원",
                                    "normalized_value": 50_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_same",
                                    "source_row_ids": ["row_same"],
                                }
                            ],
                            "denominator": [
                                {
                                    "status": "ok",
                                    "role": "denominator_1",
                                    "label": "total operating income",
                                    "concept": "operating_income",
                                    "raw_value": "50",
                                    "raw_unit": "백만원",
                                    "normalized_value": 50_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_same",
                                    "source_row_ids": ["row_same"],
                                }
                            ],
                        },
                    },
                },
            },
            {
                "task_id": "task_total",
                "metric_family": "concept_lookup",
                "metric_label": "total operating income",
                "operation_family": "lookup",
                "status": "ok",
                "answer": "전체 영업이익은 1,000 백만원입니다.",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "",
                    "formatted_result": "전체 영업이익은 1,000 백만원입니다.",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "total operating income",
                            "concept": "operating_income",
                            "raw_value": "900",
                            "raw_unit": "million",
                            "normalized_value": 900_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_stale_total",
                            "source_row_ids": ["row_stale_total"],
                        },
                    },
                },
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "calculate segment share of total operating income",
                "calc_subtasks": [
                    {"task_id": "task_segment", "operation_family": "lookup"},
                    {
                        "task_id": "task_ratio",
                        "operation_family": "ratio",
                        "required_operands": [
                            {
                                "label": "segment operating income",
                                "concept": "operating_income",
                                "role": "numerator_1",
                                "required": True,
                            },
                            {
                                "label": "total operating income",
                                "concept": "operating_income",
                                "role": "denominator_1",
                                "required": True,
                            },
                        ],
                    },
                    {"task_id": "task_total", "operation_family": "lookup"},
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = next(row for row in aligned if row["task_id"] == "task_ratio")
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertTrue(ratio_row["aligned_from_source_task_slots"])
        self.assertEqual(denominator["raw_value"], "1,000")
        self.assertEqual(denominator["source_task_id"], "task_total")
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "25%")

    def test_dependency_projection_uses_required_label_when_collapsed_ratio_slot_label_is_generic(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_segment",
                "metric_family": "concept_lookup",
                "metric_label": "segment operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating income",
                            "concept": "operating_income",
                            "raw_value": "250",
                            "raw_unit": "million",
                            "normalized_value": 250_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_segment",
                            "source_row_ids": ["row_segment"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share of total operating income",
                "operation_family": "ratio",
                "status": "insufficient_operands",
                "calculation_result": {
                    "status": "insufficient_operands",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "components_by_group": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "role": "numerator_1",
                                    "label": "segment operating income",
                                    "concept": "operating_income",
                                    "raw_value": "50",
                                    "raw_unit": "million",
                                    "normalized_value": 50_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_same",
                                    "source_row_ids": ["row_same"],
                                }
                            ],
                            "denominator": [
                                {
                                    "status": "ok",
                                    "role": "denominator_1",
                                    "label": "operating income",
                                    "concept": "operating_income",
                                    "raw_value": "50",
                                    "raw_unit": "million",
                                    "normalized_value": 50_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_same",
                                    "source_row_ids": ["row_same"],
                                }
                            ],
                        },
                    },
                },
            },
            {
                "task_id": "task_total",
                "metric_family": "concept_lookup",
                "metric_label": "total operating income",
                "operation_family": "lookup",
                "status": "ok",
                "answer": "Total operating income is 1,000 백만원.",
                "calculation_result": {
                    "status": "ok",
                    "formatted_result": "Total operating income is 1,000 백만원.",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "total operating income",
                            "concept": "operating_income",
                            "raw_value": "1,000",
                            "raw_unit": "million",
                            "normalized_value": 1_000_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_total",
                            "source_row_ids": ["row_total"],
                        },
                    },
                },
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "calculate segment share of total operating income",
                "calc_subtasks": [
                    {"task_id": "task_segment", "operation_family": "lookup"},
                    {
                        "task_id": "task_ratio",
                        "operation_family": "ratio",
                        "required_operands": [
                            {
                                "label": "segment operating income",
                                "concept": "operating_income",
                                "role": "numerator_1",
                                "required": True,
                            },
                            {
                                "label": "total operating income",
                                "concept": "operating_income",
                                "role": "denominator_1",
                                "required": True,
                            },
                        ],
                    },
                    {"task_id": "task_total", "operation_family": "lookup"},
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = next(row for row in aligned if row["task_id"] == "task_ratio")
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertTrue(ratio_row["aligned_from_source_task_slots"])
        self.assertEqual(denominator["raw_value"], "1,000")
        self.assertEqual(denominator["source_task_id"], "task_total")
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "25%")

    def test_dependency_projection_repairs_stale_lookup_slot_label_from_answer_text(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_segment",
                "metric_family": "concept_lookup",
                "metric_label": "segment operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating income",
                            "concept": "operating_income",
                            "raw_value": "250",
                            "raw_unit": "million",
                            "normalized_value": 250_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_segment",
                            "source_row_ids": ["row_segment"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share of total operating income",
                "operation_family": "ratio",
                "status": "insufficient_operands",
                "calculation_result": {
                    "status": "insufficient_operands",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "components_by_group": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "role": "numerator_1",
                                    "label": "segment operating income",
                                    "concept": "operating_income",
                                    "raw_value": "50",
                                    "raw_unit": "million",
                                    "normalized_value": 50_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_same",
                                    "source_row_ids": ["row_same"],
                                }
                            ],
                            "denominator": [
                                {
                                    "status": "ok",
                                    "role": "denominator_1",
                                    "label": "operating income",
                                    "concept": "operating_income",
                                    "raw_value": "50",
                                    "raw_unit": "million",
                                    "normalized_value": 50_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_same",
                                    "source_row_ids": ["row_same"],
                                }
                            ],
                        },
                    },
                },
            },
            {
                "task_id": "task_total",
                "metric_family": "concept_lookup",
                "metric_label": "total operating income",
                "operation_family": "lookup",
                "status": "ok",
                "answer": "Total operating income is 1,000 million.",
                "calculation_result": {
                    "status": "ok",
                    "formatted_result": "Total operating income is 1,000 million.",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating income",
                            "concept": "",
                            "raw_value": "900",
                            "raw_unit": "백만원",
                            "normalized_value": 900_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "",
                            "source_row_ids": [],
                        },
                    },
                },
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "calculate segment share of total operating income",
                    "calc_subtasks": [
                    {"task_id": "task_segment", "operation_family": "lookup"},
                    {
                        "task_id": "task_ratio",
                        "operation_family": "ratio",
                        "required_operands": [
                            {
                                "label": "segment operating income",
                                "concept": "operating_income",
                                "role": "numerator_1",
                                "required": True,
                            },
                            {
                                "label": "operating income",
                                "concept": "",
                                "role": "denominator_1",
                                "required": True,
                            },
                        ],
                    },
                    {
                        "task_id": "task_total",
                        "operation_family": "lookup",
                        "required_operands": [
                            {
                                "label": "total operating income",
                                "concept": "operating_income",
                                "role": "primary_value",
                                "required": True,
                            }
                        ],
                    },
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = next(row for row in aligned if row["task_id"] == "task_ratio")
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertTrue(ratio_row["aligned_from_source_task_slots"])
        self.assertEqual(denominator["raw_value"], "1,000")
        self.assertEqual(denominator["label"], "total operating income")
        self.assertEqual(denominator["source_task_id"], "task_total")
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "25%")

    def test_dependency_projection_repairs_qualified_denominator_lookup_with_blank_slot_metadata(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_vehicle",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 차량 부문 영업이익",
                "operation_family": "lookup",
                "status": "ok",
                "answer": "차량 부문의 영업이익은 12,677,300 백만원입니다.",
                "calculation_result": {
                    "status": "ok",
                    "formatted_result": "차량 부문의 영업이익은 12,677,300 백만원입니다.",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "차량 영업이익",
                            "concept": "operating_income",
                            "raw_value": "12,677,300",
                            "raw_unit": "백만원",
                            "normalized_value": 12_677_300_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "ev_001",
                            "source_row_ids": ["ev_001"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "전체 영업이익에서 차량 부문이 차지하는 비중",
                "operation_family": "ratio",
                "status": "insufficient_operands",
                "calculation_result": {
                    "status": "insufficient_operands",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "components_by_group": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "role": "numerator_1",
                                    "label": "차량 영업이익",
                                    "concept": "operating_income",
                                    "raw_value": "1,064,063",
                                    "raw_unit": "백만원",
                                    "normalized_value": 1_064_063_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "ev_001",
                                    "source_row_ids": ["ev_001"],
                                }
                            ],
                            "denominator": [
                                {
                                    "status": "ok",
                                    "role": "denominator_1",
                                    "label": "영업이익",
                                    "concept": "operating_income",
                                    "raw_value": "1,064,063",
                                    "raw_unit": "백만원",
                                    "normalized_value": 1_064_063_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "ev_001",
                                    "source_row_ids": ["ev_001"],
                                }
                            ],
                        },
                    },
                },
            },
            {
                "task_id": "task_total",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 전체 영업이익",
                "operation_family": "lookup",
                "status": "ok",
                "answer": "전체 영업이익은 15,126,901 백만원입니다.",
                "calculation_result": {
                    "status": "ok",
                    "formatted_result": "전체 영업이익은 15,126,901 백만원입니다.",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "2023년 차량 부문 영업이익",
                            "concept": "",
                            "raw_value": "12,969,227",
                            "raw_unit": "백만원",
                            "normalized_value": 12_969_227_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "",
                            "source_row_ids": [],
                        },
                    },
                },
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "차량 부문이 전체 영업이익에서 차지하는 비중을 계산",
                "calc_subtasks": [
                    {"task_id": "task_vehicle", "operation_family": "lookup"},
                    {
                        "task_id": "task_ratio",
                        "operation_family": "ratio",
                        "required_operands": [
                            {
                                "label": "차량 영업이익",
                                "concept": "operating_income",
                                "role": "numerator_1",
                                "required": True,
                            },
                            {
                                "label": "영업이익",
                                "concept": "operating_income",
                                "role": "denominator_1",
                                "required": True,
                            },
                        ],
                    },
                    {
                        "task_id": "task_total",
                        "operation_family": "lookup",
                        "required_operands": [
                            {
                                "label": "영업이익",
                                "concept": "operating_income",
                                "role": "primary_value",
                                "required": True,
                            }
                        ],
                    },
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = next(row for row in aligned if row["task_id"] == "task_ratio")
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertEqual(denominator["raw_value"], "15,126,901")
        self.assertEqual(denominator["source_task_id"], "task_total")
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "83.81%")

    def test_coherent_ratio_context_skips_collapsed_candidate_group(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        required_operands = [
            {"label": "segment revenue", "role": "numerator_1", "required": True},
            {"label": "total revenue", "role": "denominator_1", "required": True},
        ]
        evidence_items = [
            {
                "evidence_id": "wrong_context",
                "source_anchor": "wrong",
                "metadata": {"table_source_id": "wrong"},
            },
            {
                "evidence_id": "right_context",
                "source_anchor": "right",
                "metadata": {"table_source_id": "right"},
            },
        ]

        def build_rows(group_items, **_kwargs):
            group_id = group_items[0]["evidence_id"]
            if group_id == "wrong_context":
                return [
                    {
                        "operand_id": "numerator_1",
                        "matched_operand_role": "numerator_1",
                        "matched_operand_label": "segment revenue",
                        "raw_value": "100",
                        "raw_unit": "million",
                        "normalized_value": 100_000_000.0,
                        "evidence_id": "row_total",
                        "source_row_id": "row_total",
                    },
                    {
                        "operand_id": "denominator_1",
                        "matched_operand_role": "denominator_1",
                        "matched_operand_label": "total revenue",
                        "raw_value": "100",
                        "raw_unit": "million",
                        "normalized_value": 100_000_000.0,
                        "evidence_id": "row_total",
                        "source_row_id": "row_total",
                    },
                ]
            return [
                {
                    "operand_id": "numerator_1",
                    "matched_operand_role": "numerator_1",
                    "matched_operand_label": "segment revenue",
                    "raw_value": "25",
                    "raw_unit": "million",
                    "normalized_value": 25_000_000.0,
                    "evidence_id": "row_segment",
                    "source_row_id": "row_segment",
                },
                {
                    "operand_id": "denominator_1",
                    "matched_operand_role": "denominator_1",
                    "matched_operand_label": "total revenue",
                    "raw_value": "100",
                    "raw_unit": "million",
                    "normalized_value": 100_000_000.0,
                    "evidence_id": "row_total",
                    "source_row_id": "row_total",
                },
            ]

        agent._build_required_operands_from_candidates = build_rows
        rows = agent._build_complete_ratio_operands_from_coherent_context(
            evidence_items,
            required_operands=required_operands,
            query="segment revenue ratio",
            topic="segment revenue ratio",
            report_scope={},
        )

        self.assertEqual([row["raw_value"] for row in rows], ["25", "100"])

    def test_period_comparison_table_label_context_builds_current_and_prior_rows(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence = {
            "evidence_id": "ev_mda",
            "source_anchor": "company | 2023 | MD&A",
            "claim": "Operating profit decreased because the product-price spread narrowed.",
            "quote_span": "Operating profit decreased because the product-price spread narrowed.",
            "metadata": {
                "year": 2023,
                "statement_type": "mda",
                "unit_hint": "백만원",
                "table_source_id": "mda::table:1",
                "table_row_labels_text": "Revenue\nOperating profit",
                "table_value_labels_text": (
                    "Revenue 1,000\n"
                    "Revenue 900\n"
                    "Revenue 800\n"
                    "Revenue 11.1%\n"
                    "Operating profit 409,219\n"
                    "Operating profit 2,600,786\n"
                    "Operating profit 712,064\n"
                    "Operating profit -84.3%"
                ),
            },
        }
        required_operands = [
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
        ]

        table_lookup = agent._lookup_value_from_table_label_metadata
        table_scorer = financial_graph_calculation.table_label_metadata_lookup_score
        lookup_calls = []
        score_calls = []

        def build_rows():
            return agent._build_period_comparison_operands_from_table_label_context(
                [evidence],
                required_operands=required_operands,
                query="calculate year-over-year operating profit growth and summarize the MD&A impact",
                operation_family="growth_rate",
            )

        def record_lookup(operand, local_evidence):
            slot = table_lookup(operand, local_evidence)
            lookup_calls.append((operand, local_evidence, slot))
            return slot

        def record_score(slot, local_evidence):
            result = table_scorer(slot, local_evidence)
            score_calls.append((slot, local_evidence, result))
            return result

        with patch.object(
            agent,
            "_lookup_value_from_table_label_metadata",
            side_effect=record_lookup,
        ), patch.object(
            financial_graph_calculation,
            "table_label_metadata_lookup_score",
            side_effect=record_score,
        ):
            rows = build_rows()

        self.assertEqual([row["matched_operand_role"] for row in rows], ["current_period", "prior_period"])
        self.assertEqual([row["raw_value"] for row in rows], ["409,219", "2,600,786"])
        self.assertEqual(rows[0]["stated_change_raw_value"], "-84.3")
        self.assertEqual(rows[0]["table_source_id"], "mda::table:1")
        self.assertEqual(
            [
                (call[0].get("role"), call[2].get("raw_value"))
                for call in lookup_calls
            ],
            [("current_period", "409,219"), ("prior_period", "2,600,786")],
        )
        self.assertEqual([call[2] for call in score_calls], [8.0, 8.0])
        for index, (lookup_call, score_call) in enumerate(zip(lookup_calls, score_calls)):
            self.assertIs(lookup_call[0], required_operands[index])
            self.assertIs(score_call[0], lookup_call[2])
            self.assertIs(score_call[1], lookup_call[1])
            self.assertIsNot(lookup_call[1], evidence)
            self.assertEqual(lookup_call[1], evidence)
        self.assertIs(lookup_calls[0][1], lookup_calls[1][1])

        gated_slots = []

        def skip_current_slot(operand, local_evidence):
            slot = (
                {}
                if operand.get("role") == "current_period"
                else table_lookup(operand, local_evidence)
            )
            gated_slots.append((operand, local_evidence, slot))
            return slot

        with patch.object(
            agent,
            "_lookup_value_from_table_label_metadata",
            side_effect=skip_current_slot,
        ), patch.object(
            financial_graph_calculation,
            "table_label_metadata_lookup_score",
            side_effect=RuntimeError("period table score stopped"),
        ) as gated_scorer, self.assertRaisesRegex(RuntimeError, "period table score stopped"):
            build_rows()
        self.assertEqual(len(gated_slots), 2)
        self.assertEqual(gated_slots[0][2], {})
        self.assertEqual(gated_scorer.call_count, 1)
        self.assertIs(gated_scorer.call_args.args[0], gated_slots[1][2])
        self.assertIs(gated_scorer.call_args.args[1], gated_slots[1][1])

    def test_period_comparison_table_label_context_prefers_source_stated_mda_change(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        broad_evidence = {
            "evidence_id": "ev_broad",
            "source_anchor": "company | 2023 | MD&A",
            "claim": "The market spread was volatile during the year.",
            "quote_span": "The market spread was volatile during the year.",
            "metadata": {
                "year": 2023,
                "statement_type": "mda",
                "unit_hint": "백만원",
                "table_source_id": "mda::table:broad",
                "table_row_labels_text": "Operating profit",
                "table_value_labels_text": "Operating profit 810,900\nOperating profit 3,390,092",
            },
        }
        direct_evidence = {
            "evidence_id": "ev_direct",
            "source_anchor": "company | 2023 | MD&A",
            "claim": "Operating profit decreased because the product-price spread narrowed.",
            "quote_span": "Operating profit decreased because the product-price spread narrowed.",
            "metadata": {
                "year": 2023,
                "statement_type": "mda",
                "unit_hint": "백만원",
                "table_source_id": "mda::table:direct",
                "table_row_labels_text": "Operating profit",
                "table_value_labels_text": (
                    "Operating profit 409,219\n"
                    "Operating profit 2,600,786\n"
                    "Operating profit 712,064\n"
                    "Operating profit -84.3%"
                ),
            },
        }
        required_operands = [
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
        ]

        rows = agent._build_period_comparison_operands_from_table_label_context(
            [broad_evidence, direct_evidence],
            required_operands=required_operands,
            query="calculate year-over-year operating profit growth and summarize the MD&A impact",
            operation_family="growth_rate",
        )

        self.assertEqual([row["raw_value"] for row in rows], ["409,219", "2,600,786"])
        self.assertTrue(all(row["table_source_id"] == "mda::table:direct" for row in rows))

    def test_period_comparison_realigns_growth_result_from_late_table_label_evidence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence = {
            "evidence_id": "ev_mda",
            "source_anchor": "company | 2023 | MD&A",
            "claim": "Operating profit decreased because the product-price spread narrowed.",
            "quote_span": "Operating profit decreased because the product-price spread narrowed.",
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
        required_operands = [
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
        ]
        ordered_results = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "refining operating profit growth",
                "operation_family": "growth_rate",
                "answer": "-76.08%",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "result_value": -76.08,
                    "rendered_value": "-76.08%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "metric_label": "refining operating profit growth",
                    },
                },
            }
        ]
        state = {
            "query": "calculate year-over-year operating profit growth and summarize the MD&A impact",
            "report_scope": {"year": 2023},
            "calc_subtasks": [
                {
                    "task_id": "task_growth",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "refining operating profit growth",
                    "operation_family": "growth_rate",
                    "required_operands": required_operands,
                }
            ],
            "tasks": [{"task_id": "existing_task"}],
            "artifacts": [{"artifact_id": "existing_artifact"}],
            "selected_claim_ids": ["ev_existing"],
            "kept_claim_ids": ["ev_existing"],
        }

        evidence_items = [evidence]
        original_state = deepcopy(state)
        original_state_list_ids = tuple(
            id(state[key])
            for key in ("tasks", "artifacts", "selected_claim_ids", "kept_claim_ids")
        )
        original_results = deepcopy(ordered_results)
        original_result_rows = tuple(ordered_results)
        original_evidence = deepcopy(evidence_items)
        candidate_records = []
        original_run = agent._run_calculation_candidate

        def _record_candidate_run(recalculation_state):
            candidate_records.append(original_run(recalculation_state))
            return candidate_records[-1]

        with (
            patch.object(
                financial_graph_calculation,
                "resolve_deterministic_operation_plan",
                wraps=financial_graph_calculation.resolve_deterministic_operation_plan,
            ) as resolve_plan,
            patch.object(
                financial_calculation_execution,
                "build_deterministic_operation_plan",
                wraps=financial_calculation_execution.build_deterministic_operation_plan,
            ) as build_operation_plan,
            patch.object(
                agent,
                "_plan_formula_calculation_from_operation_decision",
                wraps=agent._plan_formula_calculation_from_operation_decision,
            ) as plan_calculation,
            patch.object(
                agent,
                "_calculation_plan_artifact_update",
                wraps=agent._calculation_plan_artifact_update,
            ) as project_plan_artifact,
            patch.object(
                agent,
                "_run_calculation_candidate",
                side_effect=_record_candidate_run,
            ) as run_candidate,
            patch.object(
                agent,
                "_execute_calculation",
                wraps=agent._execute_calculation,
            ) as execute_calculation,
            patch.object(
                agent,
                "_project_calculation_candidate_state",
                wraps=agent._project_calculation_candidate_state,
            ) as state_projection,
        ):
            rows = agent._realign_period_comparison_results_from_table_label_context(
                ordered_results,
                state,
                evidence_items,
            )

        resolve_plan.assert_called_once()
        build_operation_plan.assert_called_once()
        plan_calculation.assert_not_called()
        project_plan_artifact.assert_not_called()
        run_candidate.assert_called_once()
        execute_calculation.assert_not_called()
        state_projection.assert_not_called()

        result = rows[0]["calculation_result"]
        candidate_run = candidate_records[0]
        canonical_projection = candidate_run.projection
        self.assertEqual(result["rendered_value"], "-84.3%")
        self.assertTrue(result["derived_metrics"]["source_stated_result_used"])
        self.assertEqual(result["answer_slots"]["current_value"]["raw_value"], "409,219")
        self.assertEqual(result["answer_slots"]["prior_value"]["raw_value"], "2,600,786")
        self.assertEqual(
            rows[0]["calculation_operands"],
            list(canonical_projection.calculation_operands),
        )
        self.assertEqual(rows[0]["calculation_plan"], canonical_projection.calculation_plan)
        self.assertEqual(rows[0]["calculation_plan"], resolve_plan.call_args.kwargs["plan"])
        self.assertEqual(result, canonical_projection.calculation_result)
        self.assertEqual(state, original_state)
        self.assertEqual(
            tuple(
                id(state[key])
                for key in ("tasks", "artifacts", "selected_claim_ids", "kept_claim_ids")
            ),
            original_state_list_ids,
        )
        self.assertEqual(ordered_results, original_results)
        self.assertTrue(
            all(current is original for current, original in zip(ordered_results, original_result_rows))
        )
        self.assertEqual(evidence_items, original_evidence)
        guarded_decision = financial_calculation_execution.DeterministicOperationPlanDecision(
            status="guarded",
            raw_plan=dict(rows[0]["calculation_plan"]),
            selected_plan={**rows[0]["calculation_plan"], "status": "incomplete"},
        )
        with (
            patch.object(
                financial_graph_calculation,
                "resolve_deterministic_operation_plan",
                return_value=guarded_decision,
            ) as guarded_plan,
            patch.object(agent, "_plan_formula_calculation_from_operation_decision") as unneeded_planner,
            patch.object(agent, "_run_calculation_candidate") as unneeded_candidate_run,
        ):
            planning_failed_rows = agent._realign_period_comparison_results_from_table_label_context(
                ordered_results,
                state,
                evidence_items,
            )

        guarded_plan.assert_called_once()
        unneeded_planner.assert_not_called()
        unneeded_candidate_run.assert_not_called()
        self.assertIs(planning_failed_rows, ordered_results)
        failed_run = candidate_run._replace(
            projection=candidate_run.projection._replace(
                calculation_result={"status": "parse_error"},
            )
        )
        with patch.object(
            agent,
            "_run_calculation_candidate",
            return_value=failed_run,
        ) as failed_candidate_run:
            failed_rows = agent._realign_period_comparison_results_from_table_label_context(
                ordered_results,
                state,
                evidence_items,
            )

        failed_candidate_run.assert_called_once()
        self.assertIs(failed_rows, ordered_results)

    def test_period_comparison_realign_does_not_replace_complete_growth_slots(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence = {
            "evidence_id": "ev_weak_table",
            "source_anchor": "company | 2023 | Notes",
            "claim": "target metric 193,270 target metric 2023",
            "quote_span": "target metric 193,270 target metric 2023",
            "metadata": {
                "year": 2023,
                "statement_type": "notes",
                "table_source_id": "notes::table:1",
                "table_row_labels_text": "target metric",
                "table_value_labels_text": "target metric 193,270\ntarget metric 2023",
            },
        }
        ordered_results = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "target metric growth",
                "operation_family": "growth_rate",
                "answer": "4.51%",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "4.51%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "primary_value": {"status": "ok", "rendered_value": "4.51%"},
                        "current_value": {
                            "status": "ok",
                            "role": "current_value",
                            "label": "target metric",
                            "raw_value": "3,673,524",
                            "raw_unit": "백만원",
                            "normalized_value": 3_673_524_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "3,673,524백만원",
                            "source_row_id": "task_output:current",
                            "source_row_ids": ["task_output:current", "row_current"],
                        },
                        "prior_value": {
                            "status": "ok",
                            "role": "prior_value",
                            "label": "target metric",
                            "raw_value": "3,514,902",
                            "raw_unit": "백만원",
                            "normalized_value": 3_514_902_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "3,514,902백만원",
                            "source_row_id": "task_output:prior",
                            "source_row_ids": ["task_output:prior", "row_prior"],
                        },
                    },
                },
            }
        ]
        state = {
            "query": "calculate year-over-year target metric growth",
            "calc_subtasks": [
                {
                    "task_id": "task_growth",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "target metric growth",
                    "operation_family": "growth_rate",
                    "required_operands": [
                        {"label": "target metric", "role": "current_period", "required": True},
                        {"label": "target metric", "role": "prior_period", "required": True},
                    ],
                }
            ],
        }

        evidence_items = [evidence]
        original_results = deepcopy(ordered_results)
        original_result_row = ordered_results[0]
        with (
            patch.object(
                financial_graph_calculation,
                "resolve_deterministic_operation_plan",
                wraps=financial_graph_calculation.resolve_deterministic_operation_plan,
            ) as resolve_plan,
            patch.object(
                agent,
                "_plan_formula_calculation_from_operation_decision",
                wraps=agent._plan_formula_calculation_from_operation_decision,
            ) as plan_calculation,
            patch.object(
                agent,
                "_run_calculation_candidate",
                wraps=agent._run_calculation_candidate,
            ) as run_candidate,
        ):
            rows = agent._realign_period_comparison_results_from_table_label_context(
                ordered_results,
                state,
                evidence_items,
            )

        resolve_plan.assert_not_called()
        plan_calculation.assert_not_called()
        run_candidate.assert_not_called()
        self.assertIs(rows, ordered_results)
        self.assertIs(rows[0], original_result_row)
        self.assertEqual(ordered_results, original_results)
        self.assertEqual(rows[0]["calculation_result"]["rendered_value"], "4.51%")

    def test_period_comparison_realigns_complete_growth_slots_from_source_stated_change(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence = {
            "evidence_id": "ev_mda",
            "source_anchor": "company | 2023 | MD&A",
            "claim": "Operating profit decreased because the product-price spread narrowed.",
            "quote_span": "Operating profit decreased because the product-price spread narrowed.",
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
        required_operands = [
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
        ]
        ordered_results = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "refining operating profit growth",
                "operation_family": "growth_rate",
                "answer": "-76.08%",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "result_value": -76.08,
                    "rendered_value": "-76.08%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
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
        ]
        state = {
            "query": "calculate year-over-year operating profit growth and summarize the MD&A impact",
            "calc_subtasks": [
                {
                    "task_id": "task_growth",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "refining operating profit growth",
                    "operation_family": "growth_rate",
                    "required_operands": required_operands,
                }
            ],
        }

        rows = agent._realign_period_comparison_results_from_table_label_context(
            ordered_results,
            state,
            [evidence],
        )

        result = rows[0]["calculation_result"]
        self.assertEqual(result["rendered_value"], "-84.3%")
        self.assertTrue(result["derived_metrics"]["source_stated_result_used"])
        self.assertEqual(result["answer_slots"]["current_value"]["raw_value"], "409,219")
        self.assertEqual(result["answer_slots"]["prior_value"]["raw_value"], "2,600,786")

    def test_period_comparison_operand_recovery_uses_seed_table_context_before_dependency_rows(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent._evidence_items_from_reconciliation_matches = lambda _state: []
        agent._direct_target_metric_operand_from_evidence = lambda _state, _items: ({}, {})
        agent._dependency_binding_resolution_state = lambda _state: {
            "rows": [
                {
                    "operand_id": "current_period",
                    "matched_operand_role": "current_period",
                    "matched_operand_label": "target metric",
                    "raw_value": "900",
                    "raw_unit": "million",
                    "normalized_value": 900_000_000.0,
                    "normalized_unit": "KRW",
                    "period": "2023",
                    "source_anchor": "lookup output",
                    "source_row_id": "task_output:current_lookup",
                    "source_task_id": "current_lookup",
                    "dependency_resolved": True,
                },
                {
                    "operand_id": "prior_period",
                    "matched_operand_role": "prior_period",
                    "matched_operand_label": "target metric",
                    "raw_value": "700",
                    "raw_unit": "million",
                    "normalized_value": 700_000_000.0,
                    "normalized_unit": "KRW",
                    "period": "2022",
                    "source_anchor": "lookup output",
                    "source_row_id": "task_output:prior_lookup",
                    "source_task_id": "prior_lookup",
                    "dependency_resolved": True,
                },
            ],
            "bindings": [],
            "resolved_keys": set(),
            "missing_bindings": [],
        }
        stale_visible_doc = SimpleNamespace(
            page_content="summary table",
            metadata={
                "company": "ExampleCo",
                "year": 2022,
                "section_path": "III. Financial statements > Summary",
                "statement_type": "summary_financials",
                "table_source_id": "summary::table:1",
                "table_row_labels_text": "target metric",
                "table_value_labels_text": "target metric 900\ntarget metric 700",
                "unit_hint": "million",
            },
        )
        seed_comparison_doc = SimpleNamespace(
            page_content="comparison table",
            metadata={
                "company": "ExampleCo",
                "year": 2023,
                "section_path": "IV. Management discussion",
                "statement_type": "mda",
                "table_source_id": "mda::table:1",
                "table_row_labels_text": "target metric",
                "table_value_labels_text": (
                    "target metric 1,200\n"
                    "target metric 1,000\n"
                    "target metric 200\n"
                    "target metric 20%"
                ),
                "unit_hint": "million",
            },
        )
        required_operands = [
            {
                "label": "2023 target metric",
                "aliases": ["target metric"],
                "concept": "target_metric",
                "role": "current_period",
                "required": True,
                "unit_family": "KRW",
            },
            {
                "label": "2022 target metric",
                "aliases": ["target metric"],
                "concept": "target_metric",
                "role": "prior_period",
                "required": True,
                "unit_family": "KRW",
            },
        ]
        direct_prior_row = {
            "operand_id": "direct_prior",
            "evidence_id": "ev_direct_prior",
            "label": "2022 target metric",
            "raw_value": "800",
            "normalized_value": 800_000_000.0,
            "normalized_unit": "KRW",
            "matched_operand_label": "2022 target metric",
            "matched_operand_role": "prior_period",
        }
        agent._extract_structured_operands_from_reconciliation = (
            lambda _state: [direct_prior_row]
        )
        original_context_builder = agent._build_period_comparison_operands_from_table_label_context

        def build_current_context(*args, **kwargs):
            rows = original_context_builder(*args, **kwargs)
            return [row for row in rows if row.get("matched_operand_role") == "current_period"]

        agent._build_period_comparison_operands_from_table_label_context = build_current_context
        state = {
            "query": "calculate year-over-year target metric growth and summarize the impact",
            "report_scope": {"year": 2023},
            "active_subtask": {
                "task_id": "task_growth",
                "metric_family": "generic_numeric",
                "metric_label": "target metric growth",
                "operation_family": "growth_rate",
                "required_operands": required_operands,
            },
            "retrieved_docs": [(stale_visible_doc, 1.0)],
            "seed_retrieved_docs": [(seed_comparison_doc, 0.9)],
            "evidence_items": [],
            "evidence_bullets": [],
            "artifacts": [],
            "tasks": [],
        }
        state_before = deepcopy(state)
        direct_prior_before = deepcopy(direct_prior_row)
        adoptions = []
        original_adoption = financial_graph_calculation.resolve_recovered_operand_context_adoption

        def record_adoption(adoption_input):
            adoption = original_adoption(adoption_input)
            adoptions.append((adoption_input, adoption))
            return adoption

        with (
            patch.object(
                financial_graph_calculation,
                "surface_contract_numeric_evidence_items",
                return_value=[],
            ),
            patch.object(
                financial_graph_calculation,
                "resolve_recovered_operand_context_adoption",
                side_effect=record_adoption,
            ),
        ):
            result = agent._extract_calculation_operands(state)

        rows = _resolve_runtime_calculation_trace(result)["calculation_operands"]
        by_role = {row["matched_operand_role"]: row for row in rows}
        self.assertEqual(state, state_before)
        self.assertEqual(direct_prior_row, direct_prior_before)
        self.assertEqual(by_role["current_period"]["raw_value"], "1,200")
        self.assertEqual(by_role["prior_period"]["raw_value"], "800")
        self.assertEqual(by_role["current_period"]["table_source_id"], "mda::table:1")
        self.assertEqual([item["evidence_id"] for item in result["evidence_items"]], ["ratio_doc_context_002"])
        self.assertEqual(len(adoptions), 1)
        adoption_input, adoption = adoptions[0]
        self.assertEqual(
            [row["matched_operand_role"] for row in adoption_input.recovered_operand_rows + adoption_input.current_operand_rows],
            ["current_period", "prior_period"],
        )
        self.assertEqual(adoption.reason, "period_context_merged")
        self.assertEqual(
            [row["matched_operand_role"] for row in adoption.selected_operand_rows],
            ["current_period", "prior_period"],
        )
        self.assertEqual(adoption.adopted_evidence_ids, ("ratio_doc_context_002",))

    def test_preferred_complete_numeric_answer_joins_multiple_ratio_rows(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)

        def ratio_row(task_id: str, label: str, value: str, numerator: str, denominator: str) -> dict:
            return {
                "task_id": task_id,
                "metric_family": "concept_ratio",
                "metric_label": label,
                "operation_family": "ratio",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": value,
                    "answer_slots": {
                        "operation_family": "ratio",
                        "metric_label": label,
                        "primary_value": {"status": "ok", "rendered_value": value},
                        "components_by_group": {
                            "numerator": [
                                {"label": f"{label} numerator", "rendered_value": numerator, "normalized_value": 1, "normalized_unit": "KRW", "raw_unit": "백만원"},
                            ],
                            "denominator": [
                                {"label": f"{label} denominator", "rendered_value": denominator, "normalized_value": 1, "normalized_unit": "KRW", "raw_unit": "백만원"},
                            ],
                        },
                    },
                },
            }

        answer = agent._preferred_complete_numeric_answer(
            [
                ratio_row("task_a", "debt ratio", "25.36%", "10백만원", "40백만원"),
                ratio_row("task_b", "current ratio", "258.77%", "259백만원", "100백만원"),
            ]
        )

        self.assertIn("debt ratio", answer)
        self.assertIn("25.36%", answer)
        self.assertIn("current ratio", answer)
        self.assertIn("258.77%", answer)

    def test_aggregate_projection_skips_operands_for_hidden_subtask_result(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_numerator",
                "metric_family": "concept_lookup",
                "metric_label": "reported numerator",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "120백만원",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "reported numerator",
                            "raw_value": "120",
                            "raw_unit": "백만원",
                            "normalized_value": 120_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "120백만원",
                            "source_row_id": "ev_numerator",
                        },
                    },
                    "source_row_ids": ["ev_numerator"],
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share",
                "operation_family": "ratio",
                "status": "ok",
                "answer": "Segment share is 481.47%.",
                "calculation_operands": [
                    {
                        "operand_id": "numerator_1",
                        "matched_operand_role": "numerator_1",
                        "label": "stale numerator",
                        "raw_value": "6,670,971",
                        "raw_unit": "백만원",
                        "normalized_value": 6_670_971_000_000.0,
                        "normalized_unit": "KRW",
                    },
                    {
                        "operand_id": "denominator_1",
                        "matched_operand_role": "denominator_1",
                        "label": "stale denominator",
                        "raw_value": "1,385,538",
                        "raw_unit": "백만원",
                        "normalized_value": 1_385_538_000_000.0,
                        "normalized_unit": "KRW",
                    },
                ],
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "481.47%",
                    "formatted_result": "Segment share is 481.47%.",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "primary_value": {"status": "ok", "rendered_value": "481.47%"},
                    },
                },
            }
        ]

        projection = financial_aggregate_projection.build_aggregate_calculation_projection(
            ordered_results,
            "Reported numerator is 1.2억원. Segment share is 83.81%.",
        )

        operands = projection["calculation_operands"]
        self.assertEqual(len(operands), 1)
        self.assertEqual(operands[0]["task_id"], "task_numerator")
        self.assertEqual(operands[0]["raw_value"], "120")

    def test_complete_numeric_answer_does_not_replace_unresolved_ratio_final_answer(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share",
                "operation_family": "ratio",
                "status": "in_progress",
                "calculation_result": {
                    "status": "incomplete",
                    "answer_slots": {"operation_family": "ratio"},
                },
            },
            {
                "task_id": "task_sum",
                "metric_family": "concept_sum",
                "metric_label": "combined amount",
                "operation_family": "sum",
                "status": "ok",
                "answer": "Combined amount is 1,250 million.",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "1,250 million",
                    "formatted_result": "Combined amount is 1,250 million.",
                    "answer_slots": {
                        "operation_family": "sum",
                        "primary_value": {
                            "status": "ok",
                            "rendered_value": "1,250 million",
                            "raw_value": "1,250",
                            "raw_unit": "million",
                            "normalized_value": 1_250_000_000.0,
                            "normalized_unit": "KRW",
                        },
                    },
                },
            },
        ]

        numeric_answer = agent._preferred_complete_numeric_answer(ordered_results)

        self.assertIn("1,250", numeric_answer)
        self.assertFalse(
            agent._complete_numeric_answer_can_replace_final(
                numeric_answer,
                ordered_results,
            )
        )

        resolved_results = [
            {
                **ordered_results[0],
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "25.00%",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "primary_value": {
                            "status": "ok",
                            "rendered_value": "25.00%",
                            "raw_value": "25.00",
                            "raw_unit": "%",
                            "normalized_value": 25.0,
                            "normalized_unit": "PERCENT",
                        },
                    },
                },
            },
            ordered_results[1],
        ]

        self.assertTrue(
            agent._complete_numeric_answer_can_replace_final(
                agent._preferred_complete_numeric_answer(resolved_results),
                resolved_results,
            )
        )

    def test_existing_complete_aggregate_artifact_beats_late_partial_answer(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share",
                "operation_family": "ratio",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "25.00%",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "primary_value": {"status": "ok", "rendered_value": "25.00%"},
                    },
                },
            }
        ]
        current_answer = (
            "Segment amount is 250 million and total amount is 1,000 million. "
            "However, the required value was not sufficiently confirmed."
        )
        artifacts = [
            {
                "artifact_id": "aggregate:001",
                "task_id": "aggregate",
                "kind": "aggregated_answer",
                "status": "ok",
                "summary": "Segment amount is 250 million, total amount is 1,000 million, and the share is 25.00%.",
                "payload": {
                    "final_answer": (
                        "Segment amount is 250 million, total amount is 1,000 million, "
                        "and the share is 25.00%."
                    )
                },
                "evidence_refs": ["ev_001"],
            }
        ]

        candidate = agent._preferred_existing_aggregate_artifact_candidate(
            artifacts,
            ordered_results,
            current_answer,
        )

        self.assertEqual(
            candidate["answer"],
            "Segment amount is 250 million, total amount is 1,000 million, and the share is 25.00%.",
        )
        self.assertEqual(candidate["selected_claim_ids"], ["ev_001"])

    def test_table_metadata_source_stated_change_is_allowed_narrative_numeric_material(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "operation_family": "growth_rate",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "operation_family": "growth_rate",
                    "rendered_value": "-76.08%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "primary_value": {"status": "ok", "rendered_value": "-76.08%"},
                    },
                },
            }
        ]
        evidence_items = [
            {
                "claim": "Operating profit decreased because product spreads narrowed.",
                "quote_span": "Operating profit recorded 4,092억원 due to lower spreads.",
                "metadata": {
                    "table_value_labels_text": "Operating profit 409,219\nOperating profit -84.3%",
                },
            }
        ]
        answer = "Operating profit decreased 84.3% to 4,092억원 due to lower spreads."

        self.assertFalse(
            financial_aggregate_projection.growth_answer_has_untraced_numeric_material(
                answer,
                ordered_results,
                evidence_items,
            )
        )
        self.assertFalse(
            financial_aggregate_projection.narrative_summary_conflicts_with_growth_trace(
                answer,
                ordered_results,
                evidence_items,
            )
        )

    def test_current_source_collapsed_ratio_early_gates_identity_laziness_and_soft_fallbacks(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)

        class StateBomb(dict):
            def get(self, key, default=None):
                raise AssertionError(f"state should stay lazy: {key}")

        class StringBomb:
            def __str__(self) -> str:
                raise AssertionError("status should stay lazy")

        extractor = Mock(side_effect=AssertionError("numeric extraction should stay lazy"))
        overlay = Mock(side_effect=AssertionError("operand overlay should stay lazy"))
        with (
            patch.object(financial_runtime_trace, "extract_numeric_surface_candidates", extractor),
            patch.object(financial_runtime_trace, "overlay_calculation_operands_from_slots", overlay),
        ):
            non_ratio = _collapsed_ratio_trace_fixture()
            non_ratio["calculation_result"]["answer_slots"]["operation_family"] = "difference"
            status_value = StringBomb()
            non_ratio["calculation_result"]["status"] = status_value
            frozen_non_ratio_plan = deepcopy(non_ratio["calculation_plan"])
            frozen_non_ratio_slots = deepcopy(non_ratio["calculation_result"]["answer_slots"])
            frozen_non_ratio_operands = deepcopy(non_ratio["calculation_operands"])
            self.assertIs(
                financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(StateBomb(), non_ratio),
                non_ratio,
            )
            self.assertEqual(non_ratio["calculation_plan"], frozen_non_ratio_plan)
            self.assertEqual(non_ratio["calculation_result"]["answer_slots"], frozen_non_ratio_slots)
            self.assertEqual(non_ratio["calculation_operands"], frozen_non_ratio_operands)
            self.assertIs(non_ratio["calculation_result"]["status"], status_value)

            failed = _collapsed_ratio_trace_fixture()
            failed["calculation_result"]["status"] = "failed"
            failed["calculation_result"]["answer_slots"]["components_by_group"] = StringBomb()
            self.assertIs(
                financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(StateBomb(), failed),
                failed,
            )

            missing_component = _collapsed_ratio_trace_fixture()
            missing_component["calculation_result"]["answer_slots"]["components_by_group"][
                "denominator"
            ] = []
            self.assertIs(
                financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(StateBomb(), missing_component),
                missing_component,
            )

            missing_identity = _collapsed_ratio_trace_fixture()
            numerator = missing_identity["calculation_result"]["answer_slots"][
                "components_by_group"
            ]["numerator"][0]
            numerator["source_row_id"] = ""
            self.assertIs(
                financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(StateBomb(), missing_identity),
                missing_identity,
            )

            unequal_identity = _collapsed_ratio_trace_fixture()
            unequal_identity["calculation_result"]["answer_slots"]["components_by_group"][
                "denominator"
            ][0]["normalized_value"] = 2.0
            self.assertIs(
                financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(StateBomb(), unequal_identity),
                unequal_identity,
            )

        class RecordingState(dict):
            def __init__(self):
                super().__init__()
                self.accesses = []

            def get(self, key, default=None):
                self.accesses.append(key)
                return super().get(key, default)

        raw_fallback = _collapsed_ratio_trace_fixture()
        raw_components = raw_fallback["calculation_result"]["answer_slots"][
            "components_by_group"
        ]
        for role in ("numerator", "denominator"):
            raw_components[role][0]["normalized_value"] = None
            raw_components[role][0]["raw_value"] = " 7 "
        recording_state = RecordingState()
        self.assertIs(
            financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(recording_state, raw_fallback),
            raw_fallback,
        )
        self.assertEqual(
            recording_state.accesses,
            ["evidence_items", "runtime_evidence", "seed_retrieved_docs", "retrieved_docs"],
        )

        unequal_raw = _collapsed_ratio_trace_fixture()
        unequal_components = unequal_raw["calculation_result"]["answer_slots"][
            "components_by_group"
        ]
        for role, value in (("numerator", "7"), ("denominator", "8")):
            unequal_components[role][0]["normalized_value"] = None
            unequal_components[role][0]["raw_value"] = value
        self.assertIs(
            financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(StateBomb(), unequal_raw),
            unequal_raw,
        )

        class FloatBomb:
            def __float__(self) -> float:
                raise RuntimeError("identity float failed")

        float_bomb = _collapsed_ratio_trace_fixture()
        float_bomb["calculation_result"]["answer_slots"]["components_by_group"][
            "numerator"
        ][0]["normalized_value"] = FloatBomb()
        with self.assertRaisesRegex(RuntimeError, "identity float failed"):
            financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(StateBomb(), float_bomb)

        clean_bomb = _collapsed_ratio_trace_fixture()
        with patch.object(
            financial_runtime_trace,
            "_clean_source_row_ids",
            side_effect=RuntimeError("source identity failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "source identity failed"):
                financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(StateBomb(), clean_bomb)

        status_bomb = _collapsed_ratio_trace_fixture()
        with patch.object(
            financial_runtime_trace,
            "_normalise_spaces",
            side_effect=("ratio", RuntimeError("status normalization failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "status normalization failed"):
                financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(StateBomb(), status_bomb)

        extractor.assert_not_called()
        overlay.assert_not_called()

    def test_current_source_collapsed_ratio_evidence_and_context_doc_collection_copy_access(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        trace = _collapsed_ratio_trace_fixture()
        nested = trace["nested"]
        state_metadata = {"source_anchor": "anchor-main", "nested": nested}
        runtime_metadata = {"source_anchor": "anchor-total", "nested": nested}
        evidence_item = {
            "evidence_id": "ev-state",
            "claim": "alpha beta 10",
            "source_anchor": "anchor-main",
            "metadata": state_metadata,
            "nested": nested,
        }
        runtime_item = {
            "evidence_id": "ev-runtime",
            "claim": "total 20",
            "source_anchor": "anchor-total",
            "metadata": runtime_metadata,
            "nested": nested,
        }
        doc_events = []

        class RecordingDoc(dict):
            def get(self, key, default=None):
                doc_events.append(f"dict:{key}")
                if key in {"content", "text"}:
                    raise AssertionError(f"{key} should stay lazy")
                return super().get(key, default)

        seed_metadata = {"section_path": "anchor-main / table", "nested": nested}
        seed_doc = RecordingDoc(
            page_content="alpha beta 30",
            metadata=seed_metadata,
            nested=nested,
        )

        class ObjectDoc:
            def __init__(self):
                self._metadata = {"section": "anchor-total", "nested": nested}

            @property
            def page_content(self):
                doc_events.append("object:page_content")
                return "total 40"

            @property
            def content(self):
                raise AssertionError("object content should stay lazy")

            @property
            def text(self):
                raise AssertionError("object text should stay lazy")

            @property
            def metadata(self):
                doc_events.append("object:metadata")
                return self._metadata

        object_doc = ObjectDoc()
        state = {
            "evidence_items": [evidence_item, "skip"],
            "runtime_evidence": [runtime_item],
            "seed_retrieved_docs": [(seed_doc, 0.9)],
            "retrieved_docs": [object_doc],
            "nested": nested,
        }
        frozen_trace = deepcopy(trace)
        frozen_evidence_item = deepcopy(evidence_item)
        frozen_runtime_item = deepcopy(runtime_item)
        frozen_seed_doc = deepcopy(dict(seed_doc))
        frozen_object_metadata = deepcopy(object_doc._metadata)
        metadata_calls = []

        def terms(label):
            return ["alpha", "beta"] if "alpha" in label else ["total"]

        def spans(surface, metadata):
            metadata_calls.append((surface, metadata))
            return []

        with (
            patch.object(financial_runtime_trace, "narrative_context_terms", side_effect=terms),
            patch.object(financial_runtime_trace, "extract_numeric_surface_candidates", return_value=[]),
            patch.object(
                financial_runtime_trace,
                "numeric_candidates_with_spans_from_surface",
                side_effect=spans,
            ),
            patch.object(financial_runtime_trace, "overlay_calculation_operands_from_slots") as stopped_overlay,
        ):
            self.assertIs(
                financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(state, trace),
                trace,
            )
        stopped_overlay.assert_not_called()
        self.assertEqual(
            [surface for surface, _ in metadata_calls],
            [
                "alpha beta 10",
                "alpha beta 30 alpha beta 30",
                "total 20",
                "total 40 total 40",
            ],
        )
        metadata_by_surface = {surface: metadata for surface, metadata in metadata_calls}
        self.assertIsNot(metadata_by_surface["alpha beta 10"], state_metadata)
        self.assertIs(metadata_by_surface["alpha beta 10"]["nested"], nested)
        self.assertIsNot(metadata_by_surface["total 20"], runtime_metadata)
        self.assertIs(metadata_by_surface["total 20"]["nested"], nested)
        self.assertIsNot(metadata_by_surface["alpha beta 30 alpha beta 30"], seed_metadata)
        self.assertIs(metadata_by_surface["alpha beta 30 alpha beta 30"]["nested"], nested)
        self.assertEqual(
            doc_events,
            ["dict:page_content", "dict:metadata", "object:page_content", "object:metadata"],
        )
        self.assertEqual(trace, frozen_trace)
        self.assertEqual(evidence_item, frozen_evidence_item)
        self.assertEqual(runtime_item, frozen_runtime_item)
        self.assertEqual(dict(seed_doc), frozen_seed_doc)
        self.assertEqual(object_doc._metadata, frozen_object_metadata)
        self.assertIs(state["nested"], nested)
        self.assertIs(state["evidence_items"][0], evidence_item)
        self.assertIs(state["runtime_evidence"][0], runtime_item)
        self.assertIs(state["seed_retrieved_docs"][0][0], seed_doc)
        self.assertIs(state["retrieved_docs"][0], object_doc)

        doc_trace = _collapsed_ratio_trace_fixture()
        doc_trace["calculation_result"]["answer_slots"]["components_by_group"][
            "numerator"
        ][0]["source_anchor"] = "anchor-main"
        doc_trace["calculation_result"]["answer_slots"]["components_by_group"][
            "denominator"
        ][0]["source_anchor"] = "anchor-total"
        blank_doc = {"page_content": "", "metadata": {"nested": nested}}
        doc_state = {
            "seed_retrieved_docs": [(seed_doc, 0.9), blank_doc],
            "retrieved_docs": [object_doc],
        }
        captured_roles = []

        def candidates(surface):
            if "alpha" in surface:
                return [
                    {
                        "normalized_value": 30.0,
                        "normalized_unit": "KRW",
                        "value_text": "30",
                        "unit_text": "KRW",
                        "span": (11, 13),
                    }
                ]
            if "total" in surface:
                return [
                    {
                        "normalized_value": 40.0,
                        "normalized_unit": "KRW",
                        "value_text": "40",
                        "unit_text": "KRW",
                        "span": (6, 8),
                    }
                ]
            return []

        def overlay(original_trace, role_updates):
            self.assertIs(original_trace, doc_trace)
            captured_roles.append(role_updates)
            return []

        with (
            patch.object(financial_runtime_trace, "narrative_context_terms", side_effect=terms),
            patch.object(
                financial_runtime_trace,
                "extract_numeric_surface_candidates",
                side_effect=candidates,
            ),
            patch.object(
                financial_runtime_trace,
                "numeric_candidates_with_spans_from_surface",
                return_value=[],
            ),
            patch.object(
                financial_runtime_trace,
                "overlay_calculation_operands_from_slots",
                side_effect=overlay,
            ),
            patch.object(
                financial_runtime_trace.calculation_rendering,
                "format_ratio_percent_result",
                return_value="75.00%",
            ),
        ):
            doc_result = financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(doc_state, doc_trace)
        self.assertEqual(doc_result["calculation_result"]["result_value"], 75.0)
        self.assertEqual(len(captured_roles), 1)
        self.assertEqual(
            [
                captured_roles[0][role]["source_row_id"]
                for role in ("numerator_1", "denominator_1")
            ],
            ["retrieved::001", "retrieved::003"],
        )
        self.assertEqual(
            [
                captured_roles[0][role]["source_anchor"]
                for role in ("numerator_1", "denominator_1")
            ],
            ["anchor-main / table", "anchor-total"],
        )

        class BlankMetadataBomb(dict):
            def get(self, key, default=None):
                if key == "metadata":
                    raise RuntimeError("blank metadata failed")
                return super().get(key, default)

        with self.assertRaisesRegex(RuntimeError, "blank metadata failed"):
            financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(
                {"seed_retrieved_docs": [BlankMetadataBomb(page_content="")]},
                _collapsed_ratio_trace_fixture(),
            )

    def test_current_source_collapsed_ratio_ranking_anchor_unit_and_stable_tie(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        trace = _collapsed_ratio_trace_fixture()
        nested = trace["nested"]
        evidence_items = [
            {
                "evidence_id": "ev-partial",
                "claim": "alpha 99",
                "source_anchor": "anchor-main",
                "metadata": {"source_anchor": "anchor-main", "nested": nested},
            },
            {
                "evidence_id": "ev-anchor-first",
                "claim": "alpha beta 12",
                "source_anchor": "section / anchor-main / table",
                "metadata": {"nested": nested},
            },
            {
                "evidence_id": "ev-anchor-second",
                "claim": "alpha beta 14",
                "source_anchor": "section / anchor-main / table",
                "metadata": {"nested": nested},
            },
            {
                "evidence_id": "ev-total",
                "claim": "total 20",
                "source_anchor": "anchor-total",
                "metadata": {"nested": nested},
            },
            {
                "evidence_id": "ev-aggregate",
                "claim": "aggregate total 40",
                "source_anchor": "anchor-total / table",
                "metadata": {"nested": nested},
            },
        ]
        state = {"evidence_items": evidence_items, "nested": nested}
        frozen_trace = deepcopy(trace)
        frozen_state = deepcopy(state)
        extracted_surfaces = []
        span_surfaces = []
        captured_roles = []

        def terms(label):
            return ["alpha", "beta"] if "alpha" in label else ["total"]

        def candidates(surface):
            extracted_surfaces.append(surface)
            if surface == "alpha beta 12":
                return [
                    {
                        "normalized_value": 999.0,
                        "normalized_unit": "USD",
                        "value_text": "999",
                        "unit_text": "USD",
                        "span": (11, 13),
                    },
                    {
                        "normalized_value": 12.0,
                        "normalized_unit": "KRW",
                        "value_text": "12",
                        "unit_text": "KRW",
                        "span": (11, 13),
                    },
                ]
            if surface == "alpha beta 14":
                return [
                    {
                        "normalized_value": 14.0,
                        "normalized_unit": "KRW",
                        "value_text": "14",
                        "unit_text": "KRW",
                        "span": (11, 13),
                    }
                ]
            if surface == "total 20":
                return [
                    {
                        "normalized_value": 20.0,
                        "normalized_unit": "KRW",
                        "value_text": "20",
                        "unit_text": "KRW",
                        "span": (6, 8),
                    }
                ]
            if surface == "aggregate total 40":
                return [
                    {
                        "normalized_value": 40.0,
                        "normalized_unit": "KRW",
                        "value_text": "40",
                        "unit_text": "KRW",
                        "span": (16, 18),
                    }
                ]
            return []

        def candidates_with_spans(surface, metadata):
            span_surfaces.append((surface, metadata))
            if surface == "alpha beta 12":
                return [
                    {
                        "normalized_value": 13.0,
                        "normalized_unit": "KRW",
                        "value_text": "13",
                        "unit_text": "KRW",
                        "span": (11, 13),
                    }
                ]
            return []

        def overlay(original_trace, role_updates):
            self.assertIs(original_trace, trace)
            captured_roles.append(role_updates)
            return [{"overlay": True, "nested": nested}]

        policy = {"aggregate_tokens": [" aggregate ", "", "aggregate"]}
        with (
            patch.object(financial_runtime_trace, "STRUCTURED_CELL_AFFINITY_POLICY", policy),
            patch.object(financial_runtime_trace, "narrative_context_terms", side_effect=terms),
            patch.object(
                financial_runtime_trace,
                "extract_numeric_surface_candidates",
                side_effect=candidates,
            ),
            patch.object(
                financial_runtime_trace,
                "numeric_candidates_with_spans_from_surface",
                side_effect=candidates_with_spans,
            ),
            patch.object(
                financial_runtime_trace,
                "overlay_calculation_operands_from_slots",
                side_effect=overlay,
            ),
            patch.object(
                financial_runtime_trace.calculation_rendering,
                "format_ratio_percent_result",
                return_value="30.00%",
            ) as renderer,
        ):
            result = financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(state, trace)

        self.assertNotIn("alpha 99", extracted_surfaces)
        self.assertEqual(
            extracted_surfaces,
            ["alpha beta 12", "alpha beta 14", "total 20", "aggregate total 40"],
        )
        self.assertEqual([surface for surface, _ in span_surfaces], extracted_surfaces)
        self.assertEqual(len(captured_roles), 1)
        roles = captured_roles[0]
        self.assertEqual(roles["numerator_1"]["normalized_value"], 12.0)
        self.assertEqual(roles["numerator_1"]["source_row_id"], "ev-anchor-first")
        self.assertEqual(roles["numerator_1"]["normalized_unit"], "KRW")
        self.assertEqual(roles["denominator_1"]["normalized_value"], 40.0)
        self.assertEqual(roles["denominator_1"]["source_row_id"], "ev-aggregate")
        self.assertEqual(result["calculation_result"]["result_value"], 30.0)
        self.assertEqual(result["calculation_result"]["rendered_value"], "30.00%")
        renderer.assert_called_once_with(30.0)
        self.assertEqual(trace, frozen_trace)
        self.assertEqual(state, frozen_state)
        self.assertIs(state["evidence_items"][0], evidence_items[0])
        self.assertIs(state["nested"], nested)

        class PolicyBomb(dict):
            def get(self, key, default=None):
                raise RuntimeError("aggregate policy failed")

        stopped_terms = Mock(side_effect=AssertionError("terms should stay lazy"))
        with (
            patch.object(financial_runtime_trace, "STRUCTURED_CELL_AFFINITY_POLICY", PolicyBomb()),
            patch.object(financial_runtime_trace, "narrative_context_terms", stopped_terms),
            self.assertRaisesRegex(RuntimeError, "aggregate policy failed"),
        ):
            financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(state, trace)
        stopped_terms.assert_not_called()

        with (
            patch.object(financial_runtime_trace, "STRUCTURED_CELL_AFFINITY_POLICY", {"aggregate_tokens": []}),
            patch.object(
                financial_runtime_trace,
                "narrative_context_terms",
                side_effect=RuntimeError("label terms failed"),
            ),
            patch.object(financial_runtime_trace, "extract_numeric_surface_candidates") as stopped_extract,
            self.assertRaisesRegex(RuntimeError, "label terms failed"),
        ):
            financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(state, trace)
        stopped_extract.assert_not_called()

    def test_current_source_collapsed_ratio_result_slot_overlay_and_exception_contract(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        trace = _collapsed_ratio_trace_fixture()
        nested = trace["nested"]
        numerator_slots = trace["calculation_result"]["answer_slots"]["components_by_group"][
            "numerator"
        ]
        denominator_slots = trace["calculation_result"]["answer_slots"]["components_by_group"][
            "denominator"
        ]
        extra_numerator = {
            "role": "numerator_2",
            "label": "extra",
            "normalized_value": 2.0,
            "source_row_id": "extra",
            "nested": nested,
        }
        numerator_slots.extend([extra_numerator, "skip"])
        denominator_slots[0].pop("role")
        state = {
            "evidence_items": [
                {
                    "evidence_id": "ev-n",
                    "claim": "alpha beta 25",
                    "source_row_id": "row-n1",
                    "source_row_ids": ["row-n2", "row-n2"],
                    "source_anchor": "anchor-main",
                    "metadata": {"nested": nested},
                },
                {
                    "evidence_id": "ev-d",
                    "claim": "total 100",
                    "source_row_id": "row-d1",
                    "source_row_ids": ["row-d2"],
                    "source_anchor": "anchor-total",
                    "metadata": {"nested": nested},
                },
            ],
            "nested": nested,
        }
        frozen_trace = deepcopy(trace)
        frozen_state = deepcopy(state)

        class SoftValue:
            def __float__(self) -> float:
                raise TypeError("display conversion is soft")

            def __str__(self) -> str:
                return "100"

        soft_value = SoftValue()

        def terms(label):
            return ["alpha", "beta"] if "alpha" in label else ["total"]

        def happy_candidates(surface):
            if "alpha" in surface:
                return [
                    {
                        "normalized_value": 25.0,
                        "normalized_unit": "KRW",
                        "value": 2500.0,
                        "display_step": 100.0,
                        "unit_text": " KRW ",
                        "span": (11, 13),
                    }
                ]
            return [
                {
                    "normalized_value": 100.0,
                    "normalized_unit": "KRW",
                    "value": soft_value,
                    "span": (6, 9),
                }
            ]

        overlay_result = []
        overlay_calls = []

        def overlay(original_trace, role_updates):
            overlay_calls.append((original_trace, role_updates))
            return overlay_result

        with (
            patch.object(financial_runtime_trace, "STRUCTURED_CELL_AFFINITY_POLICY", {"aggregate_tokens": []}),
            patch.object(financial_runtime_trace, "narrative_context_terms", side_effect=terms),
            patch.object(
                financial_runtime_trace,
                "extract_numeric_surface_candidates",
                side_effect=happy_candidates,
            ),
            patch.object(
                financial_runtime_trace,
                "numeric_candidates_with_spans_from_surface",
                return_value=[],
            ),
            patch.object(
                financial_runtime_trace.calculation_rendering,
                "format_ratio_percent_result",
                return_value="25.00%",
            ) as renderer,
            patch.object(
                financial_runtime_trace,
                "overlay_calculation_operands_from_slots",
                side_effect=overlay,
            ),
        ):
            result = financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(state, trace)

        self.assertIsNot(result, trace)
        self.assertIs(result["calculation_operands"], overlay_result)
        self.assertIs(result["calculation_plan"], trace["calculation_plan"])
        self.assertIs(result["nested"], nested)
        self.assertEqual(len(overlay_calls), 1)
        self.assertIs(overlay_calls[0][0], trace)
        roles = overlay_calls[0][1]
        self.assertEqual(list(roles), ["numerator_1", "denominator_1"])
        self.assertEqual(roles["numerator_1"]["raw_value"], "25")
        self.assertEqual(roles["numerator_1"]["raw_unit"], "KRW")
        self.assertEqual(roles["numerator_1"]["rendered_value"], "25KRW")
        self.assertEqual(
            roles["numerator_1"]["source_row_ids"],
            ["ev-n", "row-n1", "row-n2"],
        )
        self.assertEqual(roles["denominator_1"]["raw_value"], "100")
        self.assertEqual(roles["denominator_1"]["raw_unit"], "KRW")
        self.assertEqual(roles["denominator_1"]["rendered_value"], "100KRW")
        self.assertEqual(
            roles["denominator_1"]["source_row_ids"],
            ["ev-d", "row-d1", "row-d2"],
        )
        calculation_result = result["calculation_result"]
        self.assertIsNot(calculation_result, trace["calculation_result"])
        self.assertEqual(calculation_result["result_value"], 25.0)
        self.assertEqual(calculation_result["result_unit"], "%")
        self.assertEqual(calculation_result["rendered_value"], "25.00%")
        self.assertEqual(calculation_result["formatted_result"], "")
        self.assertTrue(calculation_result["stale_result_repaired_from_evidence"])
        self.assertEqual(
            calculation_result["source_row_ids"],
            ["ev-n", "row-n1", "row-n2", "ev-d", "row-d1", "row-d2"],
        )
        updated_slots = calculation_result["answer_slots"]
        self.assertIsNot(updated_slots, trace["calculation_result"]["answer_slots"])
        self.assertEqual(updated_slots["primary_value"]["normalized_value"], 25.0)
        self.assertEqual(updated_slots["primary_value"]["normalized_unit"], "PERCENT")
        self.assertEqual(updated_slots["primary_value"]["rendered_value"], "25.00%")
        self.assertIs(updated_slots["primary_value"]["nested"], nested)
        self.assertEqual(
            list(updated_slots["components_by_role"]),
            ["keep", "numerator_1", "denominator_1"],
        )
        copied_extra = updated_slots["components_by_group"]["numerator"][1]
        self.assertIsNot(copied_extra, extra_numerator)
        self.assertIs(copied_extra["nested"], nested)
        self.assertEqual(len(updated_slots["components_by_group"]["numerator"]), 2)
        renderer.assert_called_once_with(25.0)
        self.assertEqual(trace, frozen_trace)
        self.assertEqual(state, frozen_state)
        self.assertIs(trace["nested"], nested)
        self.assertIs(state["nested"], nested)

        def run_terminal_candidate(numerator_value, denominator_value):
            terminal_trace = _collapsed_ratio_trace_fixture()
            terminal_state = {
                "evidence_items": [
                    {"evidence_id": "ev-n", "claim": "alpha beta 1"},
                    {"evidence_id": "ev-d", "claim": "total 2"},
                ]
            }

            def terminal_candidates(surface):
                value = numerator_value if "alpha" in surface else denominator_value
                return [
                    {
                        "normalized_value": value,
                        "normalized_unit": "KRW",
                        "value_text": str(value),
                        "span": (len(surface) - 1, len(surface)),
                    }
                ]

            terminal_renderer = Mock(side_effect=AssertionError("render should stay lazy"))
            terminal_overlay = Mock(side_effect=AssertionError("overlay should stay lazy"))
            with (
                patch.object(financial_runtime_trace, "STRUCTURED_CELL_AFFINITY_POLICY", {"aggregate_tokens": []}),
                patch.object(financial_runtime_trace, "narrative_context_terms", side_effect=terms),
                patch.object(
                    financial_runtime_trace,
                    "extract_numeric_surface_candidates",
                    side_effect=terminal_candidates,
                ),
                patch.object(
                    financial_runtime_trace,
                    "numeric_candidates_with_spans_from_surface",
                    return_value=[],
                ),
                patch.object(
                    financial_runtime_trace.calculation_rendering,
                    "format_ratio_percent_result",
                    terminal_renderer,
                ),
                patch.object(
                    financial_runtime_trace,
                    "overlay_calculation_operands_from_slots",
                    terminal_overlay,
                ),
            ):
                returned = financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(
                    terminal_state,
                    terminal_trace,
                )
            self.assertIs(returned, terminal_trace)
            terminal_renderer.assert_not_called()
            terminal_overlay.assert_not_called()

        run_terminal_candidate("not-a-number", 2.0)
        run_terminal_candidate(2.0, 0.0)
        run_terminal_candidate(2.0, 2.0)

        with (
            patch.object(financial_runtime_trace, "STRUCTURED_CELL_AFFINITY_POLICY", {"aggregate_tokens": []}),
            patch.object(financial_runtime_trace, "narrative_context_terms", side_effect=terms),
            patch.object(
                financial_runtime_trace,
                "extract_numeric_surface_candidates",
                side_effect=happy_candidates,
            ),
            patch.object(
                financial_runtime_trace,
                "numeric_candidates_with_spans_from_surface",
                return_value=[],
            ),
            patch.object(
                financial_runtime_trace.calculation_rendering,
                "format_ratio_percent_result",
                side_effect=RuntimeError("ratio rendering failed"),
            ),
            patch.object(financial_runtime_trace, "overlay_calculation_operands_from_slots") as stopped_overlay,
            self.assertRaisesRegex(RuntimeError, "ratio rendering failed"),
        ):
            financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(state, trace)
        stopped_overlay.assert_not_called()

        with (
            patch.object(financial_runtime_trace, "STRUCTURED_CELL_AFFINITY_POLICY", {"aggregate_tokens": []}),
            patch.object(financial_runtime_trace, "narrative_context_terms", side_effect=terms),
            patch.object(
                financial_runtime_trace,
                "extract_numeric_surface_candidates",
                side_effect=happy_candidates,
            ),
            patch.object(
                financial_runtime_trace,
                "numeric_candidates_with_spans_from_surface",
                return_value=[],
            ),
            patch.object(
                financial_runtime_trace.calculation_rendering,
                "format_ratio_percent_result",
                return_value="25.00%",
            ),
            patch.object(
                financial_runtime_trace,
                "overlay_calculation_operands_from_slots",
                side_effect=RuntimeError("operand overlay failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "operand overlay failed"),
        ):
            financial_runtime_trace.repair_collapsed_ratio_trace_from_evidence(state, trace)
        self.assertEqual(trace, frozen_trace)
        self.assertEqual(state, frozen_state)

    def test_current_source_collapsed_ratio_static_binding_dag_and_move_boundary(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        calculation_path = repo_root / "src" / "agent" / "financial_graph_calculation.py"
        graph_path = repo_root / "src" / "agent" / "financial_graph.py"
        owner_path = repo_root / "src" / "agent" / "financial_runtime_trace.py"
        public_name = "repair_collapsed_ratio_trace_from_evidence"
        private_name = "_" + public_name

        def parse(path):
            return ast.parse(path.read_text(encoding="utf-8-sig"))

        calculation_tree = parse(calculation_path)
        graph_tree = parse(graph_path)
        owner_tree = parse(owner_path)
        calculation_class = next(
            node
            for node in calculation_tree.body
            if isinstance(node, ast.ClassDef) and node.name == "FinancialAgentCalculationMixin"
        )
        private_defs = [
            node
            for node in calculation_class.body
            if isinstance(node, ast.FunctionDef) and node.name == private_name
        ]
        self.assertEqual(private_defs, [])
        owner_defs = [
            node
            for node in owner_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == public_name
        ]
        self.assertEqual(len(owner_defs), 1)
        owner_def = owner_defs[0]
        self.assertEqual(owner_def.end_lineno - owner_def.lineno + 1, 309)
        self.assertEqual(
            sum(
                isinstance(node, ast.Name)
                and node.id == "self"
                and isinstance(node.ctx, ast.Load)
                for node in ast.walk(owner_def)
            ),
            0,
        )
        owner_functions = [
            node for node in owner_tree.body if isinstance(node, ast.FunctionDef)
        ]
        self.assertEqual(
            (
                sum(not node.name.startswith("_") for node in owner_functions),
                sum(node.name.startswith("_") for node in owner_functions),
            ),
            (10, 21),
        )

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, relative_path):
                self.relative_path = relative_path
                self.function_stack = []
                self.try_depth = 0
                self.calls = []

            def visit_FunctionDef(self, node):
                self.function_stack.append(node.name)
                self.generic_visit(node)
                self.function_stack.pop()

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            def visit_Call(self, node):
                selector = None
                receiver = None
                if isinstance(node.func, ast.Attribute):
                    selector = node.func.attr
                    receiver = ast.unparse(node.func.value)
                elif isinstance(node.func, ast.Name):
                    selector = node.func.id
                if selector in {private_name, public_name}:
                    self.calls.append(
                        {
                            "path": self.relative_path,
                            "function": self.function_stack[-1] if self.function_stack else "",
                            "selector": selector,
                            "receiver": receiver,
                            "args": [ast.unparse(arg) for arg in node.args],
                            "kwargs": [(item.arg, ast.unparse(item.value)) for item in node.keywords],
                            "try_depth": self.try_depth,
                        }
                    )
                self.generic_visit(node)

        calls = []
        for path in sorted((repo_root / "src" / "agent").glob("*.py")):
            visitor = BindingVisitor(path.relative_to(repo_root).as_posix())
            visitor.visit(parse(path))
            calls.extend(visitor.calls)
        self.assertEqual(
            calls,
            [
                {
                    "path": "src/agent/financial_graph.py",
                    "function": "_structured_public_answer_trace_projection",
                    "selector": public_name,
                    "receiver": None,
                    "args": [
                        "public_projection_state(final, public_answer=public_answer, "
                        "runtime_calculation_trace=structured_public_projection, "
                        "runtime_evidence=runtime_evidence)",
                        "structured_public_projection",
                    ],
                    "kwargs": [],
                    "try_depth": 0,
                },
                {
                    "path": "src/agent/financial_graph.py",
                    "function": "_repair_public_runtime_calculation_trace",
                    "selector": public_name,
                    "receiver": None,
                    "args": ["projection_state", "runtime_calculation_trace"],
                    "kwargs": [],
                    "try_depth": 0,
                },
            ],
        )
        self.assertEqual(sum(call["selector"] == private_name for call in calls), 0)
        self.assertEqual(sum(call["selector"] == public_name for call in calls), 2)

        def imported_modules(path):
            imports = set()
            for node in ast.walk(parse(path)):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module == "src.agent":
                        imports.update(f"src.agent.{item.name}" for item in node.names)
                    elif node.module.startswith(("src.agent.", "src.config.")):
                        imports.add(node.module)
                elif isinstance(node, ast.Import):
                    imports.update(
                        item.name
                        for item in node.names
                        if item.name.startswith(("src.agent.", "src.config."))
                    )
            return imports

        module_edges = {}
        for package in ("agent", "config"):
            for path in sorted((repo_root / "src" / package).glob("*.py")):
                module_edges[f"src.{package}.{path.stem}"] = imported_modules(path)

        def dependency_path(source, target):
            pending = [(source, [source])]
            visited = set()
            while pending:
                current, route = pending.pop()
                if current == target:
                    return route
                if current in visited:
                    continue
                visited.add(current)
                for dependency in module_edges.get(current, set()):
                    if dependency not in visited:
                        pending.append((dependency, [*route, dependency]))
            return None

        destination = "src.agent.financial_runtime_trace"
        forbidden_targets = {
            destination,
            "src.agent.financial_graph",
            "src.agent.financial_graph_calculation",
        }
        new_dependencies = {
            "src.agent.financial_graph_calculation_rendering",
            "src.agent.financial_numeric_surface",
            "src.agent.financial_text_surface",
            "src.config.retrieval_policy",
        }
        for dependency in new_dependencies:
            for target in forbidden_targets:
                self.assertIsNone(dependency_path(dependency, target), (dependency, target))
            self.assertIn(dependency, module_edges[destination])
        self.assertIsNone(dependency_path(destination, "src.agent.financial_graph"))
        self.assertIsNone(
            dependency_path(destination, "src.agent.financial_graph_calculation")
        )

        dependency_names = {
            "numeric_candidates_with_spans_from_surface": (0, 1),
            "overlay_calculation_operands_from_slots": (1, 1),
            "extract_numeric_surface_candidates": (11, 1),
            "narrative_context_terms": (8, 1),
            "STRUCTURED_CELL_AFFINITY_POLICY": (3, 1),
            "calculation_rendering": (22, 1),
        }
        for name, expected in dependency_names.items():
            calculation_loads = sum(
                isinstance(node, ast.Name)
                and node.id == name
                and isinstance(node.ctx, ast.Load)
                for node in ast.walk(calculation_tree)
            )
            owner_loads = sum(
                isinstance(node, ast.Name)
                and node.id == name
                and isinstance(node.ctx, ast.Load)
                for node in ast.walk(owner_def)
            )
            self.assertEqual((calculation_loads, owner_loads), expected, name)

        korean_literals = [
            node.value
            for node in ast.walk(owner_def)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and any("\uac00" <= char <= "\ud7a3" for char in node.value)
        ]
        self.assertEqual(korean_literals, [])
        baseline = json.loads(
            (repo_root / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8-sig"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        candidate_string_literals = [
            node.value
            for node in ast.walk(owner_def)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        selected_baseline_records = [
            record
            for record in baseline["records"]
            if record.get("path") == "src/agent/financial_runtime_trace.py"
            and any(str(record.get("text") or "") in literal for literal in candidate_string_literals)
        ]
        self.assertEqual(selected_baseline_records, [])

        current_test_names = {
            "test_current_source_collapsed_ratio_early_gates_identity_laziness_and_soft_fallbacks",
            "test_current_source_collapsed_ratio_evidence_and_context_doc_collection_copy_access",
            "test_current_source_collapsed_ratio_ranking_anchor_unit_and_stable_tie",
            "test_current_source_collapsed_ratio_result_slot_overlay_and_exception_contract",
            "test_current_source_collapsed_ratio_static_binding_dag_and_move_boundary",
            "test_current_source_collapsed_ratio_two_callers_pin_args_adoption_order_and_stop",
        }

        def legacy_private_refs(path):
            class LegacyVisitor(ast.NodeVisitor):
                def __init__(self):
                    self.count = 0

                def visit_FunctionDef(self, node):
                    if node.name in current_test_names:
                        return
                    self.generic_visit(node)

                def visit_Attribute(self, node):
                    if node.attr == private_name:
                        self.count += 1
                    self.generic_visit(node)

                def visit_Constant(self, node):
                    if node.value == private_name:
                        self.count += 1

            visitor = LegacyVisitor()
            visitor.visit(parse(path))
            return visitor.count

        self.assertEqual(
            {
                path.name: legacy_private_refs(path)
                for path in (
                    repo_root / "tests" / "test_financial_agent_run_projection.py",
                    repo_root / "tests" / "test_aggregate_subtask_projection.py",
                    repo_root / "tests" / "test_subtask_loop.py",
                )
            },
            {
                "test_financial_agent_run_projection.py": 0,
                "test_aggregate_subtask_projection.py": 0,
                "test_subtask_loop.py": 0,
            },
        )

    def test_current_source_collapsed_ratio_two_callers_pin_args_adoption_order_and_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"preserve": True}
        final = {"answer": "old", "nested": nested}
        structured_result = {"subtask_results": [{"task_id": "task"}], "nested": nested}
        runtime_trace = {"calculation_result": {"status": "ok"}, "nested": nested}
        runtime_evidence = [{"evidence_id": "ev-1", "nested": nested}]
        frozen_final = deepcopy(final)
        frozen_structured = deepcopy(structured_result)
        frozen_trace = deepcopy(runtime_trace)
        frozen_evidence = deepcopy(runtime_evidence)
        base_state = {"answer": "public", "base": True, "nested": nested}
        structured_projection = {"projection": True, "nested": nested}
        structured_public_state = {"state": "structured", "nested": nested}
        runtime_public_state = {"state": "runtime", "nested": nested}
        structured_repaired = {"trace": "structured-repaired", "nested": nested}
        collapsed_repaired = {"trace": "collapsed-repaired", "nested": nested}
        period_repaired = {"trace": "period-repaired", "nested": nested}
        events = []

        def with_answer(value, answer):
            events.append(("with", value, answer))
            self.assertIs(value, final)
            self.assertEqual(answer, "public")
            return base_state

        def structured_owner(projection_state, trace):
            events.append(("structured", projection_state, trace))
            self.assertIsNot(projection_state, base_state)
            self.assertEqual(projection_state["answer"], "public")
            self.assertIs(projection_state["structured_result"], structured_result)
            self.assertIs(projection_state["resolved_calculation_trace"], runtime_trace)
            self.assertIs(projection_state["nested"], nested)
            self.assertIs(trace, runtime_trace)
            return structured_projection

        def public_state(value, *, public_answer, runtime_calculation_trace, runtime_evidence):
            events.append(
                (
                    "public",
                    value,
                    public_answer,
                    runtime_calculation_trace,
                    runtime_evidence,
                )
            )
            self.assertIs(value, final)
            self.assertEqual(public_answer, "public")
            self.assertIs(runtime_evidence, runtime_evidence_list)
            if runtime_calculation_trace is structured_projection:
                return structured_public_state
            self.assertIs(runtime_calculation_trace, runtime_trace)
            return runtime_public_state

        collapsed_calls = []

        def collapsed(state, trace):
            events.append(("collapsed", state, trace))
            collapsed_calls.append((state, trace))
            if trace is structured_projection:
                self.assertIs(state, structured_public_state)
                return structured_repaired
            self.assertIs(state, runtime_public_state)
            self.assertIs(trace, runtime_trace)
            return collapsed_repaired

        def period(state, trace):
            events.append(("period", state, trace))
            self.assertIs(state, runtime_public_state)
            self.assertIs(trace, collapsed_repaired)
            return period_repaired

        runtime_evidence_list = runtime_evidence
        with (
            patch.object(financial_graph, "with_public_answer", side_effect=with_answer),
            patch.object(
                financial_graph,
                "structured_subtask_projection_for_public_answer",
                side_effect=structured_owner,
            ),
            patch.object(financial_graph, "public_projection_state", side_effect=public_state),
            patch.object(
                financial_graph,
                "repair_collapsed_ratio_trace_from_evidence",
                side_effect=collapsed,
            ),
            patch.object(agent, "_repair_period_comparison_trace_from_evidence", side_effect=period),
        ):
            structured_result_trace = agent._structured_public_answer_trace_projection(
                final,
                public_answer="public",
                structured_result=structured_result,
                runtime_calculation_trace=runtime_trace,
                runtime_evidence=runtime_evidence,
            )
            runtime_result_trace = agent._repair_public_runtime_calculation_trace(
                final,
                runtime_trace,
                public_answer="public",
                runtime_evidence=runtime_evidence,
            )
        self.assertIs(structured_result_trace, structured_repaired)
        self.assertIs(runtime_result_trace, period_repaired)
        self.assertEqual(
            [event[0] for event in events],
            ["with", "structured", "public", "collapsed", "public", "collapsed", "period"],
        )
        self.assertEqual(
            collapsed_calls,
            [
                (structured_public_state, structured_projection),
                (runtime_public_state, runtime_trace),
            ],
        )

        with (
            patch.object(financial_graph, "with_public_answer", return_value=base_state),
            patch.object(
                financial_graph,
                "structured_subtask_projection_for_public_answer",
                return_value={},
            ),
            patch.object(financial_graph, "public_projection_state") as stopped_public,
            patch.object(
                financial_graph,
                "repair_collapsed_ratio_trace_from_evidence",
            ) as stopped_collapsed,
        ):
            self.assertEqual(
                agent._structured_public_answer_trace_projection(
                    final,
                    public_answer="public",
                    structured_result=structured_result,
                    runtime_calculation_trace=runtime_trace,
                    runtime_evidence=runtime_evidence,
                ),
                {},
            )
        stopped_public.assert_not_called()
        stopped_collapsed.assert_not_called()

        with (
            patch.object(financial_graph, "with_public_answer", return_value=base_state),
            patch.object(
                financial_graph,
                "structured_subtask_projection_for_public_answer",
                return_value=structured_projection,
            ),
            patch.object(financial_graph, "public_projection_state", return_value=structured_public_state),
            patch.object(
                financial_graph,
                "repair_collapsed_ratio_trace_from_evidence",
                side_effect=RuntimeError("structured collapsed failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "structured collapsed failed"):
                agent._structured_public_answer_trace_projection(
                    final,
                    public_answer="public",
                    structured_result=structured_result,
                    runtime_calculation_trace=runtime_trace,
                    runtime_evidence=runtime_evidence,
                )

        with (
            patch.object(financial_graph, "public_projection_state", return_value=runtime_public_state),
            patch.object(
                financial_graph,
                "repair_collapsed_ratio_trace_from_evidence",
                side_effect=RuntimeError("runtime collapsed failed"),
            ),
            patch.object(agent, "_repair_period_comparison_trace_from_evidence") as stopped_period,
        ):
            with self.assertRaisesRegex(RuntimeError, "runtime collapsed failed"):
                agent._repair_public_runtime_calculation_trace(
                    final,
                    runtime_trace,
                    public_answer="public",
                    runtime_evidence=runtime_evidence,
                )
        stopped_period.assert_not_called()

        with (
            patch.object(financial_graph, "public_projection_state", return_value=runtime_public_state),
            patch.object(
                financial_graph,
                "repair_collapsed_ratio_trace_from_evidence",
                return_value=collapsed_repaired,
            ),
            patch.object(
                agent,
                "_repair_period_comparison_trace_from_evidence",
                side_effect=RuntimeError("period repair failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "period repair failed"):
                agent._repair_public_runtime_calculation_trace(
                    final,
                    runtime_trace,
                    public_answer="public",
                    runtime_evidence=runtime_evidence,
                )

        self.assertEqual(final, frozen_final)
        self.assertEqual(structured_result, frozen_structured)
        self.assertEqual(runtime_trace, frozen_trace)
        self.assertEqual(runtime_evidence, frozen_evidence)
        self.assertIs(final["nested"], nested)
        self.assertIs(structured_result["nested"], nested)
        self.assertIs(runtime_trace["nested"], nested)
        self.assertIs(runtime_evidence[0]["nested"], nested)

    def test_current_source_aggregate_calculation_projection_pins_copy_dedupe_and_exceptions(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"preserve": "nested"}
        id_evidence = {"evidence_id": "ev_1", "claim": "first", "nested": nested}
        duplicate_id_evidence = {"evidence_id": "ev_1", "claim": "duplicate", "nested": nested}
        surface_evidence = {
            "source_anchor": " anchor ",
            "quote_span": " quoted   value ",
            "nested": nested,
        }
        duplicate_surface_evidence = {
            "source_anchor": "anchor",
            "quote_span": "quoted value",
            "nested": nested,
        }
        blank_evidence = {"metadata": {"keep": True}, "nested": nested}
        safe_row = {
            "task_id": "safe",
            "operation_family": "lookup",
            "runtime_evidence": [
                id_evidence,
                duplicate_id_evidence,
                surface_evidence,
                duplicate_surface_evidence,
                blank_evidence,
            ],
            "nested": nested,
        }
        conflicting_row = {
            "task_id": "growth",
            "operation_family": "growth_rate",
            "calculation_operands": [{"operand_id": "old"}],
            "source_row_ids": ["row_old"],
            "source_evidence_ids": ["ev_old"],
            "calculation_result": {
                "status": "partial",
                "answer_slots": {
                    "primary_value": {"rendered_value": "10%"},
                    "source_row_ids": ["row_old"],
                },
                "source_row_ids": ["row_old"],
                "source_evidence_ids": ["ev_old"],
                "nested": nested,
            },
            "runtime_evidence": [{"evidence_id": "ev_growth", "nested": nested}],
            "nested": nested,
        }
        nonconflicting_growth = {
            "task_id": "growth_ok",
            "operation_family": "growth_rate",
            "runtime_evidence": [],
            "nested": nested,
        }
        ordered_results = [safe_row, conflicting_row, nonconflicting_growth]
        frozen_results = deepcopy(ordered_results)
        events = []
        captured_projection_rows = []
        aggregate_operands = [{"operand_id": "aggregate"}]
        aggregate_plan = {"operation": "aggregate"}
        aggregate_result = {"status": "ok"}

        def operation_family(row):
            events.append(("operation", row["task_id"]))
            original = next(item for item in ordered_results if item["task_id"] == row["task_id"])
            self.assertIsNot(row, original)
            self.assertIs(row["nested"], nested)
            return row["operation_family"]

        def conflicts(row):
            events.append(("conflict", row["task_id"]))
            self.assertIsNot(row, next(item for item in ordered_results if item["task_id"] == row["task_id"]))
            self.assertIs(row["nested"], nested)
            return row["task_id"] == "growth"

        def material_gap(row):
            events.append(("gap", row["task_id"]))
            self.assertEqual(row["source_row_ids"], ["row_old"])
            self.assertIs(row["nested"], nested)
            return "period conflict"

        def runtime_builder(rows, answer):
            events.append(("builder", answer))
            self.assertEqual(answer, "final answer")
            self.assertEqual([row["task_id"] for row in rows], ["safe", "growth", "growth_ok"])
            self.assertIs(rows[0], safe_row)
            self.assertIsNot(rows[1], conflicting_row)
            self.assertIs(rows[1]["nested"], nested)
            self.assertIs(rows[2], nonconflicting_growth)
            captured_projection_rows.extend(rows)
            return {
                "calculation_operands": aggregate_operands,
                "calculation_plan": aggregate_plan,
                "calculation_result": aggregate_result,
                "ignored": "not returned",
            }

        def normalise(value):
            events.append(("normalise", str(value)))
            return " ".join(str(value).split())

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", side_effect=operation_family),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", side_effect=conflicts) as conflict_owner,
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                side_effect=material_gap,
            ) as gap_owner,
            patch.object(
                financial_aggregate_projection,
                "build_runtime_aggregate_calculation_projection",
                side_effect=runtime_builder,
            ) as builder_owner,
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalise) as normalise_owner,
        ):
            projection = financial_aggregate_projection.build_aggregate_calculation_projection(
                ordered_results,
                "final answer",
            )

        self.assertEqual(
            events[:7],
            [
                ("operation", "safe"),
                ("operation", "growth"),
                ("conflict", "growth"),
                ("gap", "growth"),
                ("operation", "growth_ok"),
                ("conflict", "growth_ok"),
                ("builder", "final answer"),
            ],
        )
        self.assertEqual(conflict_owner.call_count, 2)
        gap_owner.assert_called_once()
        builder_owner.assert_called_once()
        self.assertEqual(normalise_owner.call_count, 3)
        repaired = captured_projection_rows[1]
        self.assertEqual(repaired["calculation_operands"], [])
        self.assertEqual(repaired["source_row_ids"], [])
        self.assertEqual(repaired["source_evidence_ids"], [])
        self.assertEqual(repaired["material_gap_feedback"], "period conflict")
        self.assertEqual(repaired["calculation_result"]["source_row_ids"], [])
        self.assertEqual(repaired["calculation_result"]["source_evidence_ids"], [])
        self.assertEqual(repaired["calculation_result"]["material_gap_feedback"], "period conflict")
        self.assertEqual(repaired["calculation_result"]["answer_slots"]["source_row_ids"], [])
        self.assertIs(
            repaired["calculation_result"]["answer_slots"]["primary_value"],
            conflicting_row["calculation_result"]["answer_slots"]["primary_value"],
        )
        self.assertEqual(set(projection), {"calculation_operands", "calculation_plan", "calculation_result", "evidence_items"})
        self.assertIs(projection["calculation_operands"], aggregate_operands)
        self.assertIs(projection["calculation_plan"], aggregate_plan)
        self.assertIs(projection["calculation_result"], aggregate_result)
        self.assertEqual(
            [item.get("evidence_id") for item in projection["evidence_items"]],
            ["ev_1", None, None, "ev_growth"],
        )
        expected_evidence = [id_evidence, surface_evidence, blank_evidence, conflicting_row["runtime_evidence"][0]]
        for projected, original in zip(projection["evidence_items"], expected_evidence):
            self.assertEqual(projected, original)
            self.assertIsNot(projected, original)
            self.assertIs(projected["nested"], nested)
        self.assertEqual(ordered_results, frozen_results)
        self.assertIs(ordered_results[0], safe_row)
        self.assertIs(ordered_results[1], conflicting_row)
        self.assertIs(ordered_results[2], nonconflicting_growth)

        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                side_effect=RuntimeError("operation failed"),
            ),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods") as stopped_conflict,
            patch.object(financial_aggregate_projection, "build_runtime_aggregate_calculation_projection") as stopped_builder,
        ):
            with self.assertRaisesRegex(RuntimeError, "operation failed"):
                financial_aggregate_projection.build_aggregate_calculation_projection([safe_row], "answer")
        stopped_conflict.assert_not_called()
        stopped_builder.assert_not_called()

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="growth_rate"),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=True),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                side_effect=RuntimeError("gap failed"),
            ),
            patch.object(financial_aggregate_projection, "build_runtime_aggregate_calculation_projection") as stopped_builder,
        ):
            with self.assertRaisesRegex(RuntimeError, "gap failed"):
                financial_aggregate_projection.build_aggregate_calculation_projection(
                    [conflicting_row],
                    "answer",
                )
        stopped_builder.assert_not_called()

        with (
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", return_value="lookup"),
            patch.object(
                financial_aggregate_projection,
                "build_runtime_aggregate_calculation_projection",
                return_value={
                    "calculation_operands": [],
                    "calculation_plan": {},
                    "calculation_result": {},
                },
            ),
            patch.object(
                financial_aggregate_projection,
                "_normalise_spaces",
                side_effect=RuntimeError("surface failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "surface failed"):
                financial_aggregate_projection.build_aggregate_calculation_projection(
                    [{"task_id": "blank", "runtime_evidence": [{"quote_span": "value"}]}],
                    "answer",
                )

    def test_current_source_structured_public_projection_pins_gates_adoption_and_exceptions(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"preserve": True}
        subtask_rows = [{"task_id": "task_a", "nested": nested}]
        structured_result = {"subtask_results": subtask_rows, "nested": nested}
        trace = {
            "calculation_result": {
                "formatted_result": "old answer",
                "answer_slots": {"primary_value": {"rendered_value": "slot answer"}},
            },
            "nested": nested,
        }
        state = {
            "structured_result": structured_result,
            "answer": "  public   answer  ",
            "compressed_answer": "compressed answer",
            "nested": nested,
        }
        frozen_state = deepcopy(state)
        frozen_trace = deepcopy(trace)
        events = []
        projected_result = {"subtask_results": [{"task_id": "projected"}], "nested": nested}
        runtime_projection = {"calculation_result": projected_result, "nested": nested}
        attached_projection = {"attached": True, "nested": nested}

        def normalise(value):
            events.append(("normalise", str(value)))
            return " ".join(str(value).split())

        def structured_rows(value):
            events.append(("structured", value))
            self.assertIsNot(value, structured_result)
            self.assertIs(value["subtask_results"], subtask_rows)
            self.assertIs(value["nested"], nested)
            return subtask_rows, "public answer"

        def preferred(rows, public_answer):
            events.append(("preferred", rows, public_answer))
            self.assertIs(rows, subtask_rows)
            return "preferred answer"

        def runtime_builder(rows, answer):
            events.append(("builder", rows, answer))
            self.assertIs(rows, subtask_rows)
            self.assertEqual(answer, "preferred answer")
            return runtime_projection

        def attach(projection, *, source):
            events.append(("attach", projection, source))
            self.assertIs(projection, runtime_projection)
            self.assertEqual(source, "structured_result_subtasks")
            return attached_projection

        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=normalise),
            patch.object(
                financial_aggregate_projection,
                "structured_result_subtask_rows_and_answer",
                side_effect=structured_rows,
            ),
            patch.object(
                financial_aggregate_projection,
                "preferred_complete_aggregate_subtask_answer",
                side_effect=preferred,
            ),
            patch.object(
                financial_aggregate_projection,
                "build_runtime_aggregate_calculation_projection",
                side_effect=runtime_builder,
            ),
            patch.object(financial_aggregate_projection, "attach_runtime_projection_metadata", side_effect=attach),
        ):
            projection = financial_aggregate_projection.structured_subtask_projection_for_public_answer(
                state,
                trace,
            )

        self.assertIs(projection, attached_projection)
        self.assertEqual([event[0] for event in events], ["normalise", "structured", "normalise", "preferred", "builder", "attach"])
        self.assertEqual(state, frozen_state)
        self.assertEqual(trace, frozen_trace)
        self.assertIs(state["structured_result"], structured_result)
        self.assertIs(trace["nested"], nested)

        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", return_value=""),
            patch.object(
                financial_aggregate_projection,
                "structured_result_subtask_rows_and_answer",
                return_value=(subtask_rows, "public answer"),
            ) as eager_rows,
            patch.object(financial_aggregate_projection, "preferred_complete_aggregate_subtask_answer") as stopped_preferred,
        ):
            self.assertEqual(
                financial_aggregate_projection.structured_subtask_projection_for_public_answer(state, trace),
                {},
            )
        eager_rows.assert_called_once()
        self.assertIsNot(eager_rows.call_args.args[0], structured_result)
        self.assertIs(eager_rows.call_args.args[0]["nested"], nested)
        stopped_preferred.assert_not_called()

        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=lambda value: " ".join(str(value).split())),
            patch.object(
                financial_aggregate_projection,
                "structured_result_subtask_rows_and_answer",
                return_value=(subtask_rows, "different answer"),
            ),
            patch.object(financial_aggregate_projection, "preferred_complete_aggregate_subtask_answer") as stopped_preferred,
        ):
            self.assertEqual(
                financial_aggregate_projection.structured_subtask_projection_for_public_answer(state, trace),
                {},
            )
        stopped_preferred.assert_not_called()

        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=lambda value: " ".join(str(value).split())),
            patch.object(
                financial_aggregate_projection,
                "structured_result_subtask_rows_and_answer",
                return_value=(subtask_rows, "public answer"),
            ),
            patch.object(financial_aggregate_projection, "preferred_complete_aggregate_subtask_answer", return_value="public answer"),
            patch.object(financial_aggregate_projection, "build_runtime_aggregate_calculation_projection") as stopped_builder,
        ):
            same_trace = {"calculation_result": {"formatted_result": "public answer"}}
            self.assertEqual(
                financial_aggregate_projection.structured_subtask_projection_for_public_answer(state, same_trace),
                {},
            )
        stopped_builder.assert_not_called()

        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=lambda value: " ".join(str(value).split())),
            patch.object(
                financial_aggregate_projection,
                "structured_result_subtask_rows_and_answer",
                return_value=(subtask_rows, "public answer"),
            ),
            patch.object(
                financial_aggregate_projection,
                "preferred_complete_aggregate_subtask_answer",
                side_effect=RuntimeError("preferred failed"),
            ),
            patch.object(financial_aggregate_projection, "build_runtime_aggregate_calculation_projection") as stopped_builder,
        ):
            with self.assertRaisesRegex(RuntimeError, "preferred failed"):
                financial_aggregate_projection.structured_subtask_projection_for_public_answer(state, trace)
        stopped_builder.assert_not_called()

        with (
            patch.object(financial_aggregate_projection, "_normalise_spaces", side_effect=lambda value: " ".join(str(value).split())),
            patch.object(
                financial_aggregate_projection,
                "structured_result_subtask_rows_and_answer",
                return_value=(subtask_rows, "public answer"),
            ),
            patch.object(financial_aggregate_projection, "preferred_complete_aggregate_subtask_answer", return_value=""),
            patch.object(
                financial_aggregate_projection,
                "build_runtime_aggregate_calculation_projection",
                return_value={"calculation_result": {}},
            ),
            patch.object(financial_aggregate_projection, "attach_runtime_projection_metadata") as stopped_attach,
        ):
            self.assertEqual(
                financial_aggregate_projection.structured_subtask_projection_for_public_answer(state, trace),
                {},
            )
        stopped_attach.assert_not_called()

    def test_current_source_subtask_upsert_and_rank_pin_order_identity_and_exceptions(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"preserve": True}
        rank_row = {
            "task_id": "rank",
            "status": "ready",
            "answer": "A1 22",
            "source_row_ids": ["row_a"],
            "selected_claim_ids": ["claim_a"],
            "calculation_result": {
                "status": "partial",
                "answer_slots": {"primary_value": {"rendered_value": "A1 22"}},
                "source_row_ids": ["row_b"],
                "source_evidence_ids": ["ev_b"],
            },
            "nested": nested,
        }
        clean_calls = []

        def clean_source_ids(values):
            clean_calls.append(values)
            self.assertIs(values[0], rank_row["source_row_ids"])
            self.assertIs(values[1], rank_row["calculation_result"]["source_row_ids"])
            self.assertIs(values[2], rank_row["selected_claim_ids"])
            self.assertIs(values[3], rank_row["calculation_result"]["source_evidence_ids"])
            return ["row_a", "row_b", "claim_a", "ev_b"]

        with (
            patch.object(financial_aggregate_projection, "subtask_row_has_material", return_value=True) as material_owner,
            patch.object(financial_aggregate_projection, "_clean_source_row_ids", side_effect=clean_source_ids),
            patch.object(
                financial_aggregate_projection,
                "_normalise_spaces",
                side_effect=lambda value: " ".join(str(value).split()),
            ),
        ):
            rank = financial_aggregate_projection._subtask_upsert_quality_rank(rank_row)
        self.assertEqual(rank, (3, 1, 1, 4, 3, 5))
        material_owner.assert_called_once_with(rank_row)
        self.assertEqual(len(clean_calls), 1)

        existing_high = {"task_id": "task", "variant": "high", "nested": nested}
        other = {"task_id": "other", "variant": "other", "nested": nested}
        existing_low = {"task_id": "task", "variant": "low", "nested": nested}
        current = {"task_id": "task", "variant": "current", "nested": nested}
        existing = [existing_high, other, existing_low]
        frozen_existing = deepcopy(existing)
        frozen_current = deepcopy(current)
        rank_args = []

        def rank_value(row):
            rank_args.append(row)
            values = {"high": 5, "low": 1, "current": 3}
            return (values[row["variant"]], 0, 0, 0, 0, 0)

        with patch.object(financial_aggregate_projection, "_subtask_upsert_quality_rank", side_effect=rank_value):
            merged = financial_aggregate_projection.upsert_subtask_result(existing, current)

        self.assertEqual(merged, [existing_high, other, current])
        self.assertIs(merged[0], existing_high)
        self.assertIs(merged[1], other)
        self.assertIs(merged[2], current)
        self.assertEqual([row["variant"] for row in rank_args], ["high", "current", "low", "current"])
        self.assertIsNot(rank_args[0], existing_high)
        self.assertIs(rank_args[0]["nested"], nested)
        self.assertIs(rank_args[1], current)
        self.assertIsNot(rank_args[2], existing_low)
        self.assertIs(rank_args[3], current)
        self.assertEqual(existing, frozen_existing)
        self.assertEqual(current, frozen_current)

        tie_existing = {"task_id": "tie", "variant": "tie", "nested": nested}
        tie_current = {"task_id": "tie", "variant": "current", "nested": nested}
        with patch.object(
            financial_aggregate_projection,
            "_subtask_upsert_quality_rank",
            return_value=(2, 0, 0, 0, 0, 0),
        ):
            tie_result = financial_aggregate_projection.upsert_subtask_result(
                [tie_existing],
                tie_current,
            )
        self.assertEqual(tie_result, [tie_current])
        self.assertIs(tie_result[0], tie_current)

        blank_current = {"task_id": "", "nested": nested}
        blank_result = financial_aggregate_projection.upsert_subtask_result([other], blank_current)
        self.assertEqual(blank_result, [other, blank_current])
        self.assertIs(blank_result[0], other)
        self.assertIs(blank_result[1], blank_current)

        empty_current_result = financial_aggregate_projection.upsert_subtask_result(existing, {})
        self.assertEqual(empty_current_result, existing)
        self.assertIsNot(empty_current_result, existing)
        for projected, original in zip(empty_current_result, existing):
            self.assertIs(projected, original)

        with patch.object(
            financial_aggregate_projection,
            "_subtask_upsert_quality_rank",
            side_effect=RuntimeError("rank failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "rank failed"):
                financial_aggregate_projection.upsert_subtask_result([existing_high, other], current)
        self.assertEqual(existing, frozen_existing)
        self.assertEqual(current, frozen_current)

    def test_current_source_aggregate_subtask_projection_bindings_pin_exact_move_boundary(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        planning_path = project_root / "src" / "agent" / "financial_graph_planning.py"
        owner_path = project_root / "src" / "agent" / "financial_aggregate_projection.py"
        runtime_trace_path = project_root / "src" / "agent" / "financial_runtime_trace.py"
        selected_modules = {
            "planning": planning_path,
            "owner": owner_path,
            "calculation": project_root / "src" / "agent" / "financial_graph_calculation.py",
            "graph": project_root / "src" / "agent" / "financial_graph.py",
        }
        planning_tree = ast.parse(planning_path.read_text(encoding="utf-8-sig"))
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8-sig"))
        runtime_trace_tree = ast.parse(runtime_trace_path.read_text(encoding="utf-8-sig"))
        planning_class = next(
            node
            for node in planning_tree.body
            if isinstance(node, ast.ClassDef) and node.name == "FinancialAgentPlanningMixin"
        )
        retired_spans = {
            f"_{name}": span
            for name, span in {
                "build_aggregate_calculation_projection": 69,
                "structured_subtask_projection_for_public_answer": 36,
                "upsert_subtask_result": 23,
            }.items()
        }
        retired_spans["_subtask_upsert_quality_rank"] = 28
        retired_defs = {
            node.name: node
            for node in planning_class.body
            if isinstance(node, ast.FunctionDef) and node.name in retired_spans
        }
        self.assertEqual(retired_defs, {})
        owner_defs = {
            node.name: node
            for node in owner_tree.body
            if isinstance(node, ast.FunctionDef)
        }
        expected_owner_spans = {
            "build_aggregate_calculation_projection": 68,
            "structured_subtask_projection_for_public_answer": 35,
            "upsert_subtask_result": 22,
            "_subtask_upsert_quality_rank": 28,
        }
        self.assertEqual(
            {
                name: owner_defs[name].end_lineno - owner_defs[name].lineno + 1
                for name in expected_owner_spans
            },
            expected_owner_spans,
        )
        self.assertEqual(
            (
                sum(not name.startswith("_") for name in owner_defs),
                sum(name.startswith("_") for name in owner_defs),
            ),
            (76, 12),
        )
        self.assertEqual(sum(retired_spans.values()), 156)
        self.assertEqual(sum(expected_owner_spans.values()), 153)

        target_names = set(expected_owner_spans)
        selected_calls = []
        for module_name, path in selected_modules.items():
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            parents = {}
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    parents[child] = node
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                    continue
                if node.func.id not in target_names:
                    continue
                current = node
                caller = ""
                try_depth = 0
                while current in parents:
                    current = parents[current]
                    if isinstance(current, ast.Try):
                        try_depth += 1
                    if not caller and isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        caller = current.name
                selected_calls.append(
                    (
                        module_name,
                        caller,
                        node.func.id,
                        tuple(ast.unparse(arg) for arg in node.args),
                        tuple((keyword.arg, ast.unparse(keyword.value)) for keyword in node.keywords),
                        try_depth,
                    )
                )
        self.assertCountEqual(
            selected_calls,
            [
                (
                    "calculation",
                    "_rebuild_aggregate_projection",
                    "build_aggregate_calculation_projection",
                    ("projection_rows", "final_answer"),
                    (),
                    0,
                ),
                (
                    "graph",
                    "_structured_public_answer_trace_projection",
                    "structured_subtask_projection_for_public_answer",
                    ("projection_state", "runtime_calculation_trace"),
                    (),
                    0,
                ),
                (
                    "calculation",
                    "_advance_calculation_subtask",
                    "upsert_subtask_result",
                    ("list(state.get('subtask_results') or [])", "current_result"),
                    (),
                    0,
                ),
                (
                    "calculation",
                    "_prepare_initial_aggregate_state",
                    "upsert_subtask_result",
                    ("list(state.get('subtask_results') or [])", "current_result"),
                    (),
                    0,
                ),
                (
                    "owner",
                    "upsert_subtask_result",
                    "_subtask_upsert_quality_rank",
                    ("dict(row)",),
                    (),
                    0,
                ),
                (
                    "owner",
                    "upsert_subtask_result",
                    "_subtask_upsert_quality_rank",
                    ("current",),
                    (),
                    0,
                ),
            ],
        )
        self.assertEqual(
            (4, 2),
            (
                sum(call[0] != "owner" for call in selected_calls),
                sum(call[0] == "owner" for call in selected_calls),
            ),
        )

        runtime_private_defs = [
            node
            for node in runtime_trace_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "build_runtime_aggregate_calculation_projection"
        ]
        self.assertEqual(len(runtime_private_defs), 1)
        all_private_build_calls = []
        for path in (project_root / "src" / "agent").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if isinstance(node.func, ast.Name) and node.func.id == "build_runtime_aggregate_calculation_projection":
                    all_private_build_calls.append((path.name, node.lineno))
        self.assertEqual(len(all_private_build_calls), 6)

        planning_loads = Counter(
            node.id
            for node in ast.walk(planning_tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        )
        self.assertEqual(
            {
                name: planning_loads[name]
                for name in (
                    "preferred_complete_aggregate_subtask_answer",
                    "growth_row_has_conflicting_periods",
                    "material_gap_feedback_for_subtask_result",
                    "attach_runtime_projection_metadata",
                    "build_runtime_aggregate_calculation_projection",
                    "structured_result_subtask_rows_and_answer",
                )
            },
            {
                "preferred_complete_aggregate_subtask_answer": 0,
                "growth_row_has_conflicting_periods": 0,
                "material_gap_feedback_for_subtask_result": 0,
                "attach_runtime_projection_metadata": 0,
                "build_runtime_aggregate_calculation_projection": 0,
                "structured_result_subtask_rows_and_answer": 0,
            },
        )
        self.assertGreater(planning_loads["_clean_source_row_ids"], 1)
        self.assertEqual(planning_loads["subtask_row_has_material"], 0)

        module_edges = {}
        for path in (project_root / "src" / "agent").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            module_name = f"src.agent.{path.stem}"
            edges = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.agent"):
                    edges.add(node.module)
                elif isinstance(node, ast.Import):
                    edges.update(alias.name for alias in node.names if alias.name.startswith("src.agent"))
            module_edges[module_name] = edges

        def reaches(start, target):
            pending = [start]
            seen = set()
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(module_edges.get(current, ()))
            return False

        self.assertFalse(
            reaches("src.agent.financial_aggregate_projection", "src.agent.financial_graph_planning")
        )
        self.assertFalse(
            reaches("src.agent.financial_graph_planning", "src.agent.financial_aggregate_projection")
        )
        self.assertFalse(
            reaches("src.agent.financial_runtime_trace", "src.agent.financial_aggregate_projection")
        )
        self.assertFalse(
            reaches("src.agent.financial_graph_state", "src.agent.financial_aggregate_projection")
        )
        self.assertIn(
            "src.agent.financial_aggregate_projection",
            module_edges["src.agent.financial_graph_calculation"],
        )
        self.assertIn(
            "src.agent.financial_aggregate_projection",
            module_edges["src.agent.financial_graph"],
        )

        baseline = json.loads(
            (project_root / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8-sig"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        selected_baseline_records = [
            record
            for record in baseline["records"]
            if record.get("path") == "src/agent/financial_graph_planning.py"
            and any(
                1815 <= int(line) <= 1920 or 2305 <= int(line) <= 2356
                for line in (record.get("first_lines") or [])
            )
        ]
        self.assertEqual(selected_baseline_records, [])

    def test_current_source_rebuild_projection_caller_pins_args_adoption_and_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"preserve": True}
        row = {"task_id": "task", "nested": nested}
        ordered_results = [row]
        projection_rows = [{"task_id": "projected", "nested": nested}]
        built_projection = {"calculation_result": {"status": "ok"}, "nested": nested}
        filtered_projection = {"calculation_result": {"status": "filtered"}, "nested": nested}
        frozen_results = deepcopy(ordered_results)
        events = []

        def rows_owner(rows, answer):
            events.append(("rows", rows, answer))
            self.assertIs(rows, ordered_results)
            self.assertEqual(answer, "final answer")
            return projection_rows

        def build_owner(rows, answer):
            events.append(("build", rows, answer))
            self.assertIs(rows, projection_rows)
            self.assertEqual(answer, "final answer")
            return built_projection

        with (
            patch.object(agent, "_projection_rows_for_final_answer", side_effect=rows_owner),
            patch.object(
                financial_graph_calculation,
                "build_aggregate_calculation_projection",
                side_effect=build_owner,
            ),
            patch.object(financial_graph_calculation, "filter_aggregate_projection_provenance") as stopped_filter,
        ):
            result = agent._rebuild_aggregate_projection(ordered_results, "final answer")
        self.assertIs(result, built_projection)
        self.assertEqual([event[0] for event in events], ["rows", "build"])
        stopped_filter.assert_not_called()

        evidence_ids = ["ev_1"]

        def filter_owner(payload):
            events.append(("filter", payload))
            self.assertIsInstance(payload, AggregateProjectionProvenanceFilterInput)
            self.assertIs(payload.aggregate_projection, built_projection)
            self.assertIs(payload.kept_evidence_ids, evidence_ids)
            return SimpleNamespace(aggregate_projection=filtered_projection)

        events.clear()
        with (
            patch.object(agent, "_projection_rows_for_final_answer", side_effect=rows_owner),
            patch.object(
                financial_graph_calculation,
                "build_aggregate_calculation_projection",
                side_effect=build_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "filter_aggregate_projection_provenance",
                side_effect=filter_owner,
            ),
        ):
            result = agent._rebuild_aggregate_projection(
                ordered_results,
                "final answer",
                kept_evidence_ids=evidence_ids,
            )
        self.assertIs(result, filtered_projection)
        self.assertEqual([event[0] for event in events], ["rows", "build", "filter"])
        self.assertEqual(ordered_results, frozen_results)
        self.assertIs(ordered_results[0], row)

        with (
            patch.object(agent, "_projection_rows_for_final_answer", return_value=projection_rows),
            patch.object(
                financial_graph_calculation,
                "build_aggregate_calculation_projection",
                side_effect=RuntimeError("build failed"),
            ),
            patch.object(financial_graph_calculation, "filter_aggregate_projection_provenance") as stopped_filter,
        ):
            with self.assertRaisesRegex(RuntimeError, "build failed"):
                agent._rebuild_aggregate_projection(
                    ordered_results,
                    "final answer",
                    kept_evidence_ids=evidence_ids,
                )
        stopped_filter.assert_not_called()
        self.assertEqual(ordered_results, frozen_results)

    def test_current_source_structured_public_caller_pins_args_adoption_and_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"preserve": True}
        final = {"answer": "old", "nested": nested}
        structured_result = {"subtask_results": [{"task_id": "task"}], "nested": nested}
        runtime_trace = {"calculation_result": {"status": "ok"}, "nested": nested}
        runtime_evidence = [{"evidence_id": "ev_1", "nested": nested}]
        frozen_final = deepcopy(final)
        frozen_structured = deepcopy(structured_result)
        frozen_trace = deepcopy(runtime_trace)
        frozen_evidence = deepcopy(runtime_evidence)
        base_state = {"answer": "public answer", "base": True, "nested": nested}
        owner_projection = {"calculation_result": {"subtask_results": [{}]}, "nested": nested}
        public_state = {"public": True, "nested": nested}
        repaired_trace = {"repaired": True, "nested": nested}
        events = []

        def with_answer(value, answer):
            events.append(("with", value, answer))
            self.assertIs(value, final)
            self.assertEqual(answer, "public answer")
            return base_state

        def owner(projection_state, trace):
            events.append(("owner", projection_state, trace))
            self.assertIsNot(projection_state, base_state)
            self.assertEqual(projection_state["answer"], "public answer")
            self.assertIs(projection_state["structured_result"], structured_result)
            self.assertIs(projection_state["resolved_calculation_trace"], runtime_trace)
            self.assertIs(projection_state["nested"], nested)
            self.assertIs(trace, runtime_trace)
            return owner_projection

        def public_projection(value, *, public_answer, runtime_calculation_trace, runtime_evidence):
            events.append(("public", value, public_answer, runtime_calculation_trace, runtime_evidence))
            self.assertIs(value, final)
            self.assertEqual(public_answer, "public answer")
            self.assertIs(runtime_calculation_trace, owner_projection)
            self.assertIs(runtime_evidence, runtime_evidence_list)
            return public_state

        def repair(value, projection):
            events.append(("repair", value, projection))
            self.assertIs(value, public_state)
            self.assertIs(projection, owner_projection)
            return repaired_trace

        runtime_evidence_list = runtime_evidence
        with (
            patch.object(financial_graph, "with_public_answer", side_effect=with_answer),
            patch.object(
                financial_graph,
                "structured_subtask_projection_for_public_answer",
                side_effect=owner,
            ),
            patch.object(financial_graph, "public_projection_state", side_effect=public_projection),
            patch.object(
                financial_graph,
                "repair_collapsed_ratio_trace_from_evidence",
                side_effect=repair,
            ),
        ):
            result = agent._structured_public_answer_trace_projection(
                final,
                public_answer="public answer",
                structured_result=structured_result,
                runtime_calculation_trace=runtime_trace,
                runtime_evidence=runtime_evidence,
            )
        self.assertIs(result, repaired_trace)
        self.assertEqual([event[0] for event in events], ["with", "owner", "public", "repair"])

        with (
            patch.object(financial_graph, "with_public_answer", return_value=base_state),
            patch.object(financial_graph, "structured_subtask_projection_for_public_answer", return_value={}),
            patch.object(financial_graph, "public_projection_state") as stopped_public,
            patch.object(
                financial_graph,
                "repair_collapsed_ratio_trace_from_evidence",
            ) as stopped_repair,
        ):
            self.assertEqual(
                agent._structured_public_answer_trace_projection(
                    final,
                    public_answer="public answer",
                    structured_result=structured_result,
                    runtime_calculation_trace=runtime_trace,
                    runtime_evidence=runtime_evidence,
                ),
                {},
            )
        stopped_public.assert_not_called()
        stopped_repair.assert_not_called()

        with (
            patch.object(financial_graph, "with_public_answer", return_value=base_state),
            patch.object(
                financial_graph,
                "structured_subtask_projection_for_public_answer",
                side_effect=RuntimeError("structured failed"),
            ),
            patch.object(financial_graph, "public_projection_state") as stopped_public,
            patch.object(
                financial_graph,
                "repair_collapsed_ratio_trace_from_evidence",
            ) as stopped_repair,
        ):
            with self.assertRaisesRegex(RuntimeError, "structured failed"):
                agent._structured_public_answer_trace_projection(
                    final,
                    public_answer="public answer",
                    structured_result=structured_result,
                    runtime_calculation_trace=runtime_trace,
                    runtime_evidence=runtime_evidence,
                )
        stopped_public.assert_not_called()
        stopped_repair.assert_not_called()
        self.assertEqual(final, frozen_final)
        self.assertEqual(structured_result, frozen_structured)
        self.assertEqual(runtime_trace, frozen_trace)
        self.assertEqual(runtime_evidence, frozen_evidence)
        self.assertIs(final["nested"], nested)
        self.assertIs(structured_result["nested"], nested)
        self.assertIs(runtime_trace["nested"], nested)
        self.assertIs(runtime_evidence[0]["nested"], nested)

    def test_current_source_subtask_upsert_callers_pin_args_adoption_and_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"preserve": True}
        existing_row = {"task_id": "task_old", "nested": nested}
        current_row = {"task_id": "task_current", "nested": nested}
        owner_rows = [existing_row, current_row]
        advance_state = {
            "subtask_results": [existing_row],
            "calc_subtasks": [{"task_id": "task_current"}],
            "active_subtask_index": 0,
            "nested": nested,
        }
        frozen_advance = deepcopy(advance_state)
        upsert_calls = []

        def upsert(existing, current):
            upsert_calls.append((existing, current))
            self.assertIsNot(existing, advance_state["subtask_results"])
            self.assertIs(existing[0], existing_row)
            self.assertIs(current, current_row)
            return owner_rows

        with (
            patch.object(agent, "_capture_current_subtask_result", return_value=current_row),
            patch.object(financial_graph_calculation, "upsert_subtask_result", side_effect=upsert),
        ):
            advanced = agent._advance_calculation_subtask(advance_state)
        self.assertIs(advanced["subtask_results"], owner_rows)
        self.assertTrue(advanced["subtask_loop_complete"])
        self.assertEqual(len(upsert_calls), 1)
        self.assertEqual(advance_state, frozen_advance)
        self.assertIs(advance_state["subtask_results"][0], existing_row)

        class RecordingState(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.accesses = []

            def get(self, key, default=None):
                self.accesses.append(key)
                return super().get(key, default)

        stopped_state = RecordingState(advance_state)
        with (
            patch.object(agent, "_capture_current_subtask_result", return_value=current_row),
            patch.object(
                financial_graph_calculation,
                "upsert_subtask_result",
                side_effect=RuntimeError("upsert failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "upsert failed"):
                agent._advance_calculation_subtask(stopped_state)
        self.assertNotIn("calc_subtasks", stopped_state.accesses)

        first = {"task_id": "task_first", "nested": nested}
        second = {"task_id": "task_second", "nested": nested}
        prepare_state = {
            "subtask_results": [existing_row],
            "calc_subtasks": [{"task_id": "task_first"}, {"task_id": "task_second"}],
            "query": "query",
            "nested": nested,
        }
        frozen_prepare = deepcopy(prepare_state)
        dedupe_inputs = []

        def prepare_upsert(existing, current):
            self.assertIsNot(existing, prepare_state["subtask_results"])
            self.assertIs(existing[0], existing_row)
            self.assertIs(current, current_row)
            return [second, first]

        def stop_after_adoption(rows):
            dedupe_inputs.append(rows)
            self.assertEqual(rows, [first, second])
            self.assertIs(rows[0], first)
            self.assertIs(rows[1], second)
            raise RuntimeError("dedupe reached")

        with (
            patch.object(agent, "_capture_current_subtask_result", return_value=current_row),
            patch.object(financial_graph_calculation, "upsert_subtask_result", side_effect=prepare_upsert),
            patch.object(
                financial_graph_calculation,
                "dedupe_aggregate_subtask_results",
                side_effect=stop_after_adoption,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "dedupe reached"):
                agent._prepare_initial_aggregate_state(prepare_state)
        self.assertEqual(len(dedupe_inputs), 1)
        self.assertEqual(prepare_state, frozen_prepare)
        self.assertIs(prepare_state["subtask_results"][0], existing_row)

        with (
            patch.object(agent, "_capture_current_subtask_result", return_value=current_row),
            patch.object(
                financial_graph_calculation,
                "upsert_subtask_result",
                side_effect=RuntimeError("prepare upsert failed"),
            ),
            patch.object(financial_graph_calculation, "dedupe_aggregate_subtask_results") as stopped_dedupe,
        ):
            with self.assertRaisesRegex(RuntimeError, "prepare upsert failed"):
                agent._prepare_initial_aggregate_state(prepare_state)
        stopped_dedupe.assert_not_called()
        self.assertEqual(prepare_state, frozen_prepare)


if __name__ == "__main__":
    unittest.main()
