import inspect
import math
import unittest
from collections.abc import Mapping
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from src.agent import (
    financial_aggregate_state,
    financial_aggregate_projection,
    financial_calculation_execution,
    financial_graph_calculation,
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
from src.agent.financial_graph_planning import _refine_lookup_slot_unit_from_evidence
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


class AggregateSubtaskProjectionTests(unittest.TestCase):
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
                    _answer_slot_has_material=lambda *_args, **_kwargs: False,
                    _answer_matches_supported_aggregate_subtask=lambda *_args, **_kwargs: locked,
                    _compose_growth_narrative_answer=compose("growth", growth),
                    _compose_entity_table_summary_answer=compose("entity", entity),
                    _compose_business_technology_focus_answer=compose("business", business),
                    _compose_dividend_policy_hybrid_answer=compose("dividend", dividend),
                    _compose_supported_quantitative_impact_answer=compose("quantitative", quantitative),
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
            "_operand_text_match",
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
            "_operand_text_match",
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

        answer, status, calculation_result = agent._promote_nested_subtask_result_if_more_specific(
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

        refined = _refine_lookup_slot_unit_from_evidence(slot, evidence)

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
        aggregate_projection = agent._build_aggregate_calculation_projection(ordered_results, "coverage ratio is 0.0035배.")

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
        original_final_filter = agent._filter_final_aggregate_evidence_and_projection

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
                agent,
                "_filter_final_aggregate_evidence_and_projection",
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
                agent,
                "_build_deterministic_operation_plan",
                wraps=agent._build_deterministic_operation_plan,
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
        current_unit_coercion = agent._coerce_operand_unit_from_evidence

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
                agent,
                "_coerce_operand_unit_from_evidence",
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
                ("_repair_krw_operand_units_from_table_metadata", "op_numerator", False, None, False),
                (
                    "_repair_krw_operand_units_from_table_metadata",
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
            patch.object(agent, "_coerce_operand_unit_from_evidence") as later_unit_coercion,
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency unit gate failed"):
                agent._coerce_operand_row_from_evidence(numerator_row, None)
        later_unit_coercion.assert_not_called()

        with (
            patch.object(
                financial_graph_calculation,
                "dependency_task_output_has_consistent_krw_unit",
                side_effect=RuntimeError("dependency unit gate failed"),
            ),
            patch.object(financial_graph_calculation, "_normalise_operand_value") as later_normalizer,
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency unit gate failed"):
                agent._repair_krw_operand_units_from_table_metadata(
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

        plan = agent._build_deterministic_ontology_plan(state, operands)

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
                agent,
                "_build_deterministic_operation_plan",
                wraps=agent._build_deterministic_operation_plan,
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

        refined = _refine_lookup_slot_unit_from_evidence(slot, evidence)

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

    def test_ratio_components_are_not_complete_when_groups_are_same_slot(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        calculation_result = {
            "status": "ok",
            "rendered_value": "100%",
            "answer_slots": {
                "operation_family": "ratio",
                "components_by_group": {
                    "numerator": [
                        {
                            "label": "segment operating income",
                            "raw_value": "(581,816)",
                            "raw_unit": "million",
                            "normalized_value": -581_816_000_000.0,
                            "source_row_id": "task_output:task_source",
                            "source_row_ids": ["task_output:task_source", "row_segment"],
                        }
                    ],
                    "denominator": [
                        {
                            "label": "segment operating income",
                            "raw_value": "(581,816)",
                            "raw_unit": "million",
                            "normalized_value": -581_816_000_000.0,
                            "source_row_id": "task_output:task_source",
                            "source_row_ids": ["task_output:task_source", "row_segment"],
                        }
                    ],
                },
            },
        }

        self.assertFalse(agent._ratio_components_are_complete(calculation_result))

    def test_ratio_components_are_not_complete_when_same_source_value_has_different_labels(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        calculation_result = {
            "status": "ok",
            "rendered_value": "100%",
            "answer_slots": {
                "operation_family": "ratio",
                "components_by_group": {
                    "numerator": [
                        {
                            "label": "segment operating income",
                            "raw_value": "1,064,063",
                            "raw_unit": "million",
                            "normalized_value": 1_064_063_000_000.0,
                            "source_row_id": "row_same",
                            "source_row_ids": ["row_same"],
                        }
                    ],
                    "denominator": [
                        {
                            "label": "total operating income",
                            "raw_value": "1,064,063",
                            "raw_unit": "million",
                            "normalized_value": 1_064_063_000_000.0,
                            "source_row_id": "row_same",
                            "source_row_ids": ["row_same"],
                        }
                    ],
                },
            },
        }

        self.assertFalse(agent._ratio_components_are_complete(calculation_result))

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
                financial_graph_calculation,
                "build_deterministic_operation_plan",
                wraps=financial_graph_calculation.build_deterministic_operation_plan,
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
        agent._surface_contract_numeric_evidence_items = lambda _items, _operands: []
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

        with patch.object(
            financial_graph_calculation,
            "resolve_recovered_operand_context_adoption",
            side_effect=record_adoption,
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

        projection = agent._build_aggregate_calculation_projection(
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

    def test_numeric_answer_coverage_requires_all_trace_values(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)

        self.assertFalse(
            agent._answer_covers_numeric_answer(
                "The final answer is 258.77% using 259백만원 and 100백만원.",
                "Debt ratio is 25.36%. Current ratio is 258.77%.",
            )
        )
        self.assertTrue(
            agent._answer_covers_numeric_answer(
                "Debt ratio is 25.4%. Current ratio is 258.77%.",
                "Debt ratio is 25.36%. Current ratio is 258.77%.",
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
            agent._growth_answer_has_untraced_numeric_material(
                answer,
                ordered_results,
                evidence_items,
            )
        )
        self.assertFalse(
            agent._narrative_summary_conflicts_with_growth_trace(
                answer,
                ordered_results,
                evidence_items,
            )
        )


if __name__ == "__main__":
    unittest.main()
