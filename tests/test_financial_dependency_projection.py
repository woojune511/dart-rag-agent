import math
import unittest
from copy import deepcopy
from typing import Any, Dict, List, Mapping
from unittest.mock import patch

import src.agent.financial_dependency_projection as dependency_projection
from src.agent.financial_dependency_projection import (
    DependencyRatioResultProjectionInput,
    DirectDependencySelectionInput,
    DependencyRecalculatedRowFinalizationInput,
    DependencyRecalculationCandidateProjectionInput,
    DependencyStructuredProvenanceAdoptionInput,
    LateDependencyRemergeInput,
    LateOperandFinalizationInput,
    MainOperandPrecedenceInput,
    adopt_dependency_structured_provenance,
    align_dependency_rows_with_sibling_direct_context,
    build_dependency_ratio_result_projection,
    decide_task_output_operand_resolution,
    dependency_binding_identity,
    direct_rows_resolved_dependency_keys,
    filter_direct_rows_by_dependency_producer_scope,
    finalize_dependency_recalculated_row,
    period_comparison_direct_rows_conflict_with_dependency_outputs,
    prefer_complete_ratio_direct_context_rows,
    resolve_dependency_recalculation_candidate_projection,
    resolve_late_dependency_remerge,
    resolve_late_operand_finalization,
    resolve_main_operand_precedence,
    resolve_dependency_producer_scope,
    select_direct_dependency_operand_rows,
    summarize_dependency_bindings,
)


class FinancialDependencyProjectionTests(unittest.TestCase):
    def test_dependency_row_unit_inference_preserves_policy_and_access_contract(self) -> None:
        def infer(slot, sibling_result):
            return dependency_projection.infer_dependency_row_unit(slot, sibling_result)

        slot = {"raw_unit": "  million  ", "normalized_unit": " krw ", "nested": {"keep": True}}
        sibling_result = {"result_unit": "%", "nested": {"keep": True}}
        inputs_before = deepcopy((slot, sibling_result))
        self.assertEqual(infer(slot, sibling_result), ("million", "KRW"))
        self.assertEqual((slot, sibling_result), inputs_before)
        self.assertEqual(
            infer({"raw_unit": "", "normalized_unit": "count"}, {"result_unit": " units "}),
            ("units", "COUNT"),
        )

        events = []

        class _TrackedMapping(Mapping[str, Any]):
            def __init__(self, name, values, *, fail_key=""):
                self.name = name
                self.values = values
                self.fail_key = fail_key

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
                if key == self.fail_key:
                    raise RuntimeError(f"failed to read {self.name}.{key}")
                return self.values.get(key, default)

        class _TrackedUnits:
            def __init__(self, name, values, *, fail=False):
                self.name = name
                self.values = values
                self.fail = fail

            def __iter__(self):
                events.append(f"iter:{self.name}")
                if self.fail:
                    raise RuntimeError(f"failed to iterate {self.name}")
                return iter(self.values)

        lazy_sibling = _TrackedMapping("sibling", {}, fail_key="result_unit")
        with patch.object(
            dependency_projection,
            "CALCULATION_RENDER_POLICY",
            _TrackedMapping("policy", {}, fail_key="keys"),
        ):
            self.assertEqual(
                infer(_TrackedMapping("slot", {"raw_unit": " % ", "normalized_unit": "percent"}), lazy_sibling),
                ("%", "PERCENT"),
            )
        self.assertEqual(events, ["get:slot:raw_unit", "get:slot:normalized_unit"])

        events.clear()
        whitespace_sibling = _TrackedMapping("sibling", {}, fail_key="result_unit")
        self.assertEqual(
            infer(_TrackedMapping("slot", {"raw_unit": "   ", "normalized_unit": "UNKNOWN"}), whitespace_sibling),
            ("", "UNKNOWN"),
        )
        self.assertNotIn("get:sibling:result_unit", events)

        policy = {
            "percent_display_units": ("%", "shared"),
            "krw_display_units": ("won", "shared", "krw_count"),
            "krw_normalized_unit": "custom_krw",
            "count_display_units": ("count", "shared", "krw_count"),
        }
        for raw_unit, expected in (
            ("%", "PERCENT"),
            ("shared", "PERCENT"),
            ("won", "CUSTOM_KRW"),
            ("krw_count", "CUSTOM_KRW"),
            ("count", "COUNT"),
            ("other", "UNKNOWN"),
        ):
            with self.subTest(raw_unit=raw_unit), patch.object(
                dependency_projection,
                "CALCULATION_RENDER_POLICY",
                policy,
            ):
                self.assertEqual(infer({"raw_unit": raw_unit}, {}), (raw_unit, expected))

        for configured_unit, expected in (("", "KRW"), (" custom_krw ", " CUSTOM_KRW ")):
            with self.subTest(configured_unit=configured_unit), patch.object(
                dependency_projection,
                "CALCULATION_RENDER_POLICY",
                {
                    "percent_display_units": (),
                    "krw_display_units": ("won",),
                    "krw_normalized_unit": configured_unit,
                    "count_display_units": (),
                },
            ):
                self.assertEqual(infer({"raw_unit": "won"}, {}), ("won", expected))

        events.clear()
        tracked_policy = _TrackedMapping(
            "policy",
            {
                "percent_display_units": _TrackedUnits("percent", ["%"]),
                "krw_display_units": _TrackedUnits("krw", ["won"]),
                "krw_normalized_unit": "KRW",
                "count_display_units": _TrackedUnits("count", ["count"]),
            },
        )
        with patch.object(dependency_projection, "CALCULATION_RENDER_POLICY", tracked_policy):
            self.assertEqual(
                infer(
                    _TrackedMapping("slot", {"raw_unit": "", "normalized_unit": "UNKNOWN"}),
                    _TrackedMapping("sibling", {"result_unit": "%"}),
                ),
                ("%", "PERCENT"),
            )
        self.assertEqual(
            events,
            [
                "get:slot:raw_unit",
                "get:sibling:result_unit",
                "get:slot:normalized_unit",
                "keys:policy",
                "getitem:policy:percent_display_units",
                "getitem:policy:krw_display_units",
                "getitem:policy:krw_normalized_unit",
                "getitem:policy:count_display_units",
                "iter:percent",
            ],
        )

        events.clear()
        failing_policy = {
            "percent_display_units": _TrackedUnits("percent", [], fail=True),
            "krw_display_units": _TrackedUnits("krw", ["won"]),
        }
        with patch.object(
            dependency_projection,
            "CALCULATION_RENDER_POLICY",
            failing_policy,
        ), self.assertRaisesRegex(RuntimeError, "failed to iterate percent"):
            infer({"raw_unit": "won"}, {})
        self.assertEqual(events, ["iter:percent"])

        events.clear()
        with self.assertRaisesRegex(RuntimeError, "failed to read slot.raw_unit"):
            infer(
                _TrackedMapping("slot", {}, fail_key="raw_unit"),
                _TrackedMapping("sibling", {}, fail_key="result_unit"),
            )
        self.assertEqual(events, ["get:slot:raw_unit"])

    def test_dependency_task_output_krw_consistency_preserves_gate_numeric_and_exception_contract(self) -> None:
        def consistent(row):
            return dependency_projection.dependency_task_output_has_consistent_krw_unit(row)

        row = {
            "dependency_resolved": True,
            "source_row_id": "task_output:lookup",
            "raw_value": "100",
            "raw_unit": "원",
            "normalized_value": 100.0,
            "normalized_unit": "KRW",
            "nested": {"keep": True},
        }
        row_before = deepcopy(row)
        self.assertTrue(consistent(row))
        self.assertEqual(row, row_before)

        events = []

        class _TrackedRow(Mapping[str, Any]):
            def __init__(self, values, *, fail_key="", fail_type=RuntimeError):
                self.values = values
                self.fail_key = fail_key
                self.fail_type = fail_type

            def __len__(self):
                return len(self.values)

            def __iter__(self):
                return iter(self.values)

            def __getitem__(self, key):
                return self.values[key]

            def get(self, key, default=None):
                events.append(f"get:{key}")
                if key == self.fail_key:
                    raise self.fail_type(f"failed to read {key}")
                return self.values.get(key, default)

        with patch.object(
            dependency_projection,
            "_normalise_operand_value",
            side_effect=AssertionError("normalizer must stay lazy"),
        ):
            for values, expected_events in (
                ({}, ["get:dependency_resolved"]),
                (
                    {"dependency_resolved": True, "source_row_id": "local"},
                    ["get:dependency_resolved", "get:source_row_id"],
                ),
                (
                    {
                        "dependency_resolved": True,
                        "source_row_id": "task_output:lookup",
                        "normalized_unit": "COUNT",
                    },
                    ["get:dependency_resolved", "get:source_row_id", "get:normalized_unit"],
                ),
            ):
                with self.subTest(values=values):
                    events.clear()
                    self.assertFalse(consistent(_TrackedRow(values)))
                    self.assertEqual(events, expected_events)

            events.clear()
            self.assertFalse(
                consistent(
                    _TrackedRow(
                        {
                            "dependency_resolved": True,
                            "source_row_id": "task_output:lookup",
                            "normalized_unit": "KRW",
                            "raw_value": "1",
                            "raw_unit": "   ",
                            "result_unit": "원",
                        }
                    )
                )
            )
            self.assertEqual(
                events,
                [
                    "get:dependency_resolved",
                    "get:source_row_id",
                    "get:normalized_unit",
                    "get:raw_value",
                    "get:raw_unit",
                ],
            )

            events.clear()
            self.assertFalse(
                consistent(
                    _TrackedRow(
                        {
                            "dependency_resolved": True,
                            "source_row_id": "task_output:lookup",
                            "normalized_unit": "KRW",
                            "raw_value": "",
                            "raw_unit": "원",
                        }
                    )
                )
            )
            self.assertEqual(
                events,
                [
                    "get:dependency_resolved",
                    "get:source_row_id",
                    "get:normalized_unit",
                    "get:raw_value",
                    "get:raw_unit",
                ],
            )

        def record_normalizer(raw_value, raw_unit):
            events.append(f"normalize:{raw_value}:{raw_unit}")
            return 1.0, "KRW"

        events.clear()
        with patch.object(
            dependency_projection,
            "_normalise_operand_value",
            side_effect=record_normalizer,
        ):
            self.assertTrue(
                consistent(
                    _TrackedRow(
                        {
                            "dependency_resolved": True,
                            "source_row_id": "task_output:lookup",
                            "normalized_unit": " krw ",
                            "raw_value": " 1 ",
                            "raw_unit": "",
                            "result_unit": " 원 ",
                            "normalized_value": 1.0,
                        }
                    )
                )
            )
        self.assertEqual(
            events,
            [
                "get:dependency_resolved",
                "get:source_row_id",
                "get:normalized_unit",
                "get:raw_value",
                "get:raw_unit",
                "get:result_unit",
                "normalize:1:원",
                "get:normalized_value",
            ],
        )

        base = {
            "dependency_resolved": True,
            "source_row_id": "task_output:lookup",
            "normalized_unit": "KRW",
            "raw_value": "1",
            "raw_unit": "원",
        }
        for normalizer_result, current_value, expected in (
            ((None, "KRW"), 1.0, False),
            ((1.0, "COUNT"), 1.0, False),
            ((1.0, "krw"), 1.0, False),
            ((1.0, "KRW"), 1.0, True),
        ):
            with self.subTest(normalizer_result=normalizer_result), patch.object(
                dependency_projection,
                "_normalise_operand_value",
                return_value=normalizer_result,
            ):
                self.assertEqual(consistent({**base, "normalized_value": current_value}), expected)

        for expected_value, current_value, expected in (
            (0.0, 0.0, True),
            (0.0, 1e-6, True),
            (1_000_000_000.0, 1_000_000_001.0, True),
            (1_000_000_000.0, 1_000_000_001.0001, False),
            (-1_000_000_000.0, -999_999_999.0, True),
            (1.0, math.nan, False),
        ):
            with self.subTest(expected_value=expected_value, current_value=current_value), patch.object(
                dependency_projection,
                "_normalise_operand_value",
                return_value=(expected_value, "KRW"),
            ):
                self.assertEqual(consistent({**base, "normalized_value": current_value}), expected)

        class _BadFloat:
            def __init__(self, error_type):
                self.error_type = error_type

            def __float__(self):
                raise self.error_type("failed to coerce float")

        for error_type in (TypeError, ValueError):
            with self.subTest(error_type=error_type), patch.object(
                dependency_projection,
                "_normalise_operand_value",
                return_value=(1.0, "KRW"),
            ):
                self.assertFalse(consistent({**base, "normalized_value": _BadFloat(error_type)}))
        with patch.object(
            dependency_projection,
            "_normalise_operand_value",
            return_value=(_BadFloat(ValueError), "KRW"),
        ):
            self.assertFalse(consistent({**base, "normalized_value": 1.0}))

        float_events = []

        class _TrackedFloat:
            def __init__(self, name, *, fail=False):
                self.name = name
                self.fail = fail

            def __float__(self):
                float_events.append(self.name)
                if self.fail:
                    raise ValueError(f"failed to coerce {self.name}")
                return 1.0

        with patch.object(
            dependency_projection,
            "_normalise_operand_value",
            return_value=(_TrackedFloat("expected"), "KRW"),
        ):
            self.assertFalse(
                consistent({**base, "normalized_value": _TrackedFloat("current", fail=True)})
            )
        self.assertEqual(float_events, ["current"])

        for error_type in (TypeError, ValueError, RuntimeError):
            with self.subTest(mapping_error_type=error_type):
                events.clear()
                with self.assertRaisesRegex(error_type, "failed to read source_row_id"):
                    consistent(
                        _TrackedRow(
                            {"dependency_resolved": True},
                            fail_key="source_row_id",
                            fail_type=error_type,
                        )
                    )
                self.assertEqual(events, ["get:dependency_resolved", "get:source_row_id"])

        for error_type, expected_exception in (
            (TypeError, False),
            (ValueError, False),
            (RuntimeError, True),
        ):
            events.clear()
            failing_row = _TrackedRow(
                {
                    **base,
                    "normalized_value": 1.0,
                },
                fail_key="normalized_value",
                fail_type=error_type,
            )
            with self.subTest(normalized_get_error_type=error_type), patch.object(
                dependency_projection,
                "_normalise_operand_value",
                return_value=(1.0, "KRW"),
            ):
                if expected_exception:
                    with self.assertRaisesRegex(error_type, "failed to read normalized_value"):
                        consistent(failing_row)
                else:
                    self.assertFalse(consistent(failing_row))
            self.assertEqual(
                events,
                [
                    "get:dependency_resolved",
                    "get:source_row_id",
                    "get:normalized_unit",
                    "get:raw_value",
                    "get:raw_unit",
                    "get:normalized_value",
                ],
            )

        class _BadString:
            def __str__(self):
                raise RuntimeError("failed to stringify source")

        with self.assertRaisesRegex(RuntimeError, "failed to stringify source"):
            consistent({"dependency_resolved": True, "source_row_id": _BadString()})
        with patch.object(
            dependency_projection,
            "_normalise_operand_value",
            side_effect=RuntimeError("normalizer failed"),
        ), self.assertRaisesRegex(RuntimeError, "normalizer failed"):
            consistent({**base, "normalized_value": 1.0})

    def test_dependency_ratio_result_projection_preserves_aliases_and_access_order(self) -> None:
        marker = {"preserve": True}
        numerator = {"slot": "numerator", "metadata": marker}
        denominator = {"slot": "denominator", "metadata": marker}
        source_ids = ["ev_num", "ev_den"]
        calculation_result = {
            "status": "partial",
            "operation_family": "difference",
            "result_value": -1.0,
            "result_unit": "old",
            "rendered_value": "old",
            "formatted_result": "old",
            "source_row_ids": ["stale"],
            "source_evidence_ids": ["stale"],
            "answer_slots": {"legacy": True},
            "metadata": marker,
        }
        answer_slots = {
            "metric_label": "stale",
            "operation_family": "difference",
            "source_row_ids": ["stale"],
            "primary_value": {"rendered_value": "stale"},
            "components_by_group": {"operand": [{"stale": True}]},
            "components_by_role": {"operand_1": [{"stale": True}]},
            "metadata": marker,
        }

        def build(result=calculation_result, slots=answer_slots, ids=source_ids):
            return build_dependency_ratio_result_projection(
                DependencyRatioResultProjectionInput(
                    calculation_result=result,
                    answer_slots=slots,
                    metric_label="target share",
                    numerator_slot=numerator,
                    denominator_slot=denominator,
                    result_value=80.0,
                    result_unit="%",
                    normalized_unit="PERCENT",
                    rendered_value="80%",
                    source_row_ids=ids,
                )
            ).calculation_result

        inputs = (calculation_result, answer_slots, numerator, denominator, source_ids)
        inputs_before = deepcopy(inputs)
        selected = build()
        selected_slots = selected["answer_slots"]
        primary = selected_slots["primary_value"]
        grouped = selected_slots["components_by_group"]
        by_role = selected_slots["components_by_role"]

        self.assertEqual(
            tuple(selected[key] for key in (
                "status", "operation_family", "result_value", "result_unit",
                "rendered_value", "formatted_result",
            )),
            ("ok", "ratio", 80.0, "%", "80%", ""),
        )
        self.assertIs(selected["metadata"], marker)
        self.assertIsNot(selected, calculation_result)
        self.assertIsNot(selected_slots, answer_slots)
        self.assertIsNot(primary, answer_slots["primary_value"])
        self.assertEqual(list(selected), list(calculation_result))
        self.assertEqual(list(selected_slots), list(answer_slots))
        self.assertEqual(
            primary,
            {
                "status": "ok",
                "role": "primary_value",
                "label": "target share",
                "concept": "",
                "period": "",
                "raw_value": "80%",
                "raw_unit": "%",
                "normalized_value": 80.0,
                "normalized_unit": "PERCENT",
                "rendered_value": "80%",
                "source_row_id": "ev_num",
                "source_row_ids": source_ids,
                "source_anchor": "",
            },
        )
        self.assertTrue(all(value is source_ids for value in (
            selected["source_row_ids"], selected["source_evidence_ids"],
            selected_slots["source_row_ids"], primary["source_row_ids"],
        )))
        self.assertIsNot(grouped, answer_slots["components_by_group"])
        self.assertIsNot(by_role, answer_slots["components_by_role"])
        self.assertEqual(len({id(rows) for rows in (*grouped.values(), *by_role.values())}), 4)
        self.assertIsNot(grouped["numerator"], by_role["numerator_1"])
        self.assertIsNot(grouped["denominator"], by_role["denominator_1"])
        self.assertIs(grouped["numerator"][0], numerator)
        self.assertIs(by_role["numerator_1"][0], numerator)
        self.assertIs(grouped["denominator"][0], denominator)
        self.assertIs(by_role["denominator_1"][0], denominator)
        self.assertIs(selected_slots["metadata"], marker)
        self.assertNotIn("legacy", selected_slots)
        self.assertEqual(inputs, inputs_before)

        empty_ids = []
        empty_selected = build({}, {}, empty_ids)
        empty_primary = empty_selected["answer_slots"]["primary_value"]
        self.assertEqual(empty_primary["source_row_id"], "")
        self.assertTrue(all(value is empty_ids for value in (
            empty_selected["source_row_ids"], empty_selected["source_evidence_ids"],
            empty_selected["answer_slots"]["source_row_ids"], empty_primary["source_row_ids"],
        )))

        events = []

        class _TrackingMapping(Mapping):
            def __init__(self, name, values, *, fail_key=""):
                self.name = name
                self.values = values
                self.fail_key = fail_key

            def __len__(self):
                events.append(f"len:{self.name}")
                return len(self.values)

            def __iter__(self):
                events.append(f"iter:{self.name}")
                return iter(self.values)

            def keys(self):
                events.append(f"keys:{self.name}")
                return self.values.keys()

            def __getitem__(self, key):
                events.append(f"getitem:{self.name}:{key}")
                if key == self.fail_key:
                    raise RuntimeError(f"failed to expand {self.name}")
                return self.values[key]

            def get(self, _key, _default=None):
                raise RuntimeError(f"unexpected get from {self.name}")

        class _TrackingIds(list):
            def __init__(self, values, *, fail_bool=False, fail_index=False):
                super().__init__(values)
                self.fail_bool = fail_bool
                self.fail_index = fail_index

            def __bool__(self):
                events.append("bool:ids")
                if self.fail_bool:
                    raise RuntimeError("failed source id truthiness")
                return len(self) > 0

            def __getitem__(self, index):
                events.append(f"index:ids:{index}")
                if self.fail_index:
                    raise RuntimeError("failed source id index")
                return super().__getitem__(index)

        tracked_ids = _TrackingIds(["ev_num"])
        tracked = build(
            _TrackingMapping("result", {"metadata": marker}),
            _TrackingMapping("slots", {"metadata": marker}),
            tracked_ids,
        )
        self.assertEqual(events, [
            "keys:result", "getitem:result:metadata", "keys:slots",
            "getitem:slots:metadata", "bool:ids", "index:ids:0",
        ])
        self.assertIs(tracked["source_row_ids"], tracked_ids)

        events.clear()
        with self.assertRaisesRegex(RuntimeError, "failed to expand slots"):
            build(
                _TrackingMapping("result", {"metadata": marker}),
                _TrackingMapping("slots", {"metadata": marker}, fail_key="metadata"),
                _TrackingIds(["ev_num"]),
            )
        self.assertEqual(events, [
            "keys:result", "getitem:result:metadata", "keys:slots", "getitem:slots:metadata",
        ])

        for ids, message, expected_tail in (
            (
                _TrackingIds(["ev_num"], fail_bool=True),
                "truthiness",
                ["keys:result", "keys:slots", "bool:ids"],
            ),
            (
                _TrackingIds(["ev_num"], fail_index=True),
                "index",
                ["keys:result", "keys:slots", "bool:ids", "index:ids:0"],
            ),
        ):
            with self.subTest(source_ids=message):
                events.clear()
                with self.assertRaisesRegex(RuntimeError, message):
                    build(
                        _TrackingMapping("result", {}),
                        _TrackingMapping("slots", {}),
                        ids,
                    )
                self.assertEqual(events, expected_tail)

    def test_dependency_recalculation_candidate_and_row_projection_contracts(self) -> None:
        nested_marker = {"preserve": True}
        candidate_operands = [{"operand_id": "candidate", "metadata": nested_marker}]
        candidate_plan = {"operation": "ratio", "metadata": nested_marker}
        candidate_result = {
            "status": " OK ",
            "answer_slots": {"metadata": nested_marker},
        }
        candidate_inputs = (candidate_operands, candidate_plan, candidate_result)
        candidate_inputs_before = deepcopy(candidate_inputs)

        candidate = resolve_dependency_recalculation_candidate_projection(
            DependencyRecalculationCandidateProjectionInput(
                calculation_operands=candidate_operands,
                calculation_plan=candidate_plan,
                calculation_result=candidate_result,
            )
        )

        trace = candidate.recalculated_trace
        self.assertEqual((candidate.candidate_ready, candidate.reason), (True, "candidate_ready"))
        self.assertIsNot(trace["calculation_operands"], candidate_operands)
        self.assertIsNot(trace["calculation_operands"][0], candidate_operands[0])
        self.assertIs(trace["calculation_operands"][0]["metadata"], nested_marker)
        self.assertIsNot(trace["calculation_plan"], candidate_plan)
        self.assertIs(trace["calculation_plan"]["metadata"], nested_marker)
        self.assertIsNot(trace["calculation_result"], candidate_result)
        self.assertIsNot(candidate.recalculated_result, trace["calculation_result"])
        self.assertIs(
            candidate.recalculated_result["answer_slots"],
            trace["calculation_result"]["answer_slots"],
        )
        self.assertEqual(candidate_inputs, candidate_inputs_before)

        rejected = resolve_dependency_recalculation_candidate_projection(
            DependencyRecalculationCandidateProjectionInput([], {}, {"status": "parse_error"})
        )
        self.assertEqual((rejected.candidate_ready, rejected.reason), (False, "calculation_result_not_ok"))

        current_row = {
            "answer": "current answer",
            "source_row_ids": ["row_current"],
            "metadata": nested_marker,
        }
        trace_operand = {"operand_id": "trace", "metadata": nested_marker}
        fallback_operand = {"operand_id": "fallback"}
        trace_operands = [trace_operand]
        fallback_operands = [fallback_operand]
        trace_plan = {"operation": "ratio", "metadata": nested_marker}
        fallback_plan = {"operation": "difference"}
        recalculated_result = {
            "status": "ok",
            "source_row_ids": ["row_recalculated"],
            "metadata": nested_marker,
        }
        inputs = (current_row, trace_operands, fallback_operands, trace_plan, fallback_plan)
        inputs_before = deepcopy(inputs)
        recalculated_result_before = deepcopy(recalculated_result)

        selected = finalize_dependency_recalculated_row(
            DependencyRecalculatedRowFinalizationInput(
                current_row=current_row,
                recalculated_trace={
                    "calculation_operands": trace_operands,
                    "calculation_plan": trace_plan,
                },
                updated_operands=fallback_operands,
                fallback_calculation_plan=fallback_plan,
                recalculated_result=recalculated_result,
                formatted_answer="recalculated answer",
            )
        ).selected_row

        self.assertIsNot(selected, current_row)
        self.assertEqual(selected["answer"], "recalculated answer")
        self.assertEqual(selected["status"], "ok")
        self.assertIsNot(selected["calculation_operands"], trace_operands)
        self.assertIs(selected["calculation_operands"][0], trace_operand)
        self.assertIsNot(selected["calculation_plan"], trace_plan)
        self.assertEqual(selected["calculation_plan"]["operation"], "ratio")
        self.assertIs(selected["calculation_plan"]["metadata"], nested_marker)
        self.assertIs(selected["calculation_result"], recalculated_result)
        self.assertEqual(selected["source_row_ids"], ["row_recalculated"])
        self.assertIsNot(selected["source_row_ids"], recalculated_result["source_row_ids"])
        self.assertIs(selected["metadata"], nested_marker)

        fallback_result = {}
        fallback_selected = finalize_dependency_recalculated_row(
            DependencyRecalculatedRowFinalizationInput(
                current_row=current_row,
                recalculated_trace={},
                updated_operands=fallback_operands,
                fallback_calculation_plan=fallback_plan,
                recalculated_result=fallback_result,
                formatted_answer="",
            )
        ).selected_row
        self.assertEqual(fallback_selected["answer"], "current answer")
        self.assertIsNot(fallback_selected["calculation_operands"], fallback_operands)
        self.assertIs(fallback_selected["calculation_operands"][0], fallback_operand)
        self.assertEqual(fallback_selected["calculation_plan"]["operation"], "difference")
        self.assertIs(fallback_selected["calculation_result"], fallback_result)
        self.assertEqual(fallback_selected["source_row_ids"], ["row_current"])
        self.assertEqual(inputs, inputs_before)
        self.assertEqual(
            recalculated_result,
            {**recalculated_result_before, "formatted_result": "recalculated answer"},
        )

    def test_dependency_structured_provenance_adoption_contracts(self) -> None:
        nested = {"preserve": True}
        provenance = {
            "source_anchor": " [ExampleCo | 2023 | Financial statements] ",
            "chunk_uid": " node_1 ",
            "unit_hint": "백만원",
            "consolidation_scope": " consolidated ",
            "statement_type": " income_statement ",
            "table_source_id": " table_income ",
        }

        def operand_row(**updates):
            return {
                "raw_value": "100",
                "raw_unit": "천원",
                "normalized_value": 100000.0,
                "normalized_unit": "KRW",
                "rendered_value": "100천원",
                "source_anchor": "old anchor",
                "source_row_ids": ["ev_lookup", "ev_lookup"],
                "consolidation_scope": "separate",
                "statement_type": "notes",
                "table_source_id": "old_table",
                "metadata": nested,
                **updates,
            }

        adopted_metadata = ("consolidated", "income_statement", "table_income")
        original_metadata = ("separate", "notes", "old_table")
        cases = (
            (
                "realigned", {}, {},
                ("백만원", 100000000.0, True, "structured_unit_realigned", adopted_metadata),
            ),
            (
                "visible", {"raw_unit": "원", "normalized_value": 100.0, "rendered_value": "100원"}, {},
                ("원", 100.0, False, "source_visible_converted_unit_preserved", adopted_metadata),
            ),
            (
                "high_magnitude_tolerance",
                {"raw_value": "651,481,422,157", "raw_unit": "원", "normalized_value": 651481422757.0, "rendered_value": ""},
                {},
                ("원", 651481422757.0, False, "source_visible_converted_unit_preserved", adopted_metadata),
            ),
            (
                "same_unit", {"raw_unit": "백만원", "normalized_value": 100000000.0, "rendered_value": "100백만원"}, {},
                ("백만원", 100000000.0, False, "structured_unit_unchanged", adopted_metadata),
            ),
            (
                "unnormalizable",
                {"raw_value": "not-a-number", "raw_unit": "원", "normalized_value": None, "rendered_value": ""},
                {"consolidation_scope": "", "statement_type": "", "table_source_id": ""},
                ("원", None, False, "structured_unit_unchanged", original_metadata),
            ),
        )
        invalid_expected = ("백만원", 100000000.0, True, "structured_unit_realigned", adopted_metadata)
        cases += tuple(
            (f"invalid_{type(value).__name__}", {"raw_unit": "원", "normalized_value": value, "rendered_value": ""}, {}, invalid_expected)
            for value in ("not-a-number", None)
        )
        for name, row_updates, provenance_updates, expected in cases:
            with self.subTest(name=name):
                row = operand_row(**row_updates)
                case_provenance = {**provenance, **provenance_updates}
                provenance_before = deepcopy(case_provenance)
                result = adopt_dependency_structured_provenance(
                    DependencyStructuredProvenanceAdoptionInput(row, case_provenance)
                )
                self.assertIs(result.dependency_row, row)
                self.assertEqual(
                    (
                        row["raw_unit"], row["normalized_value"],
                        result.unit_realignment_applied, result.reason,
                        (row["consolidation_scope"], row["statement_type"], row["table_source_id"]),
                    ),
                    expected,
                )
                self.assertEqual(row["source_row_ids"], ["ev_lookup", "node_1"])
                self.assertEqual(row["source_anchor"], "[ExampleCo | 2023 | Financial statements]")
                self.assertEqual(bool(row.get("unit_realigned_from_structured_provenance")), expected[2])
                self.assertIs(row["metadata"], nested)
                self.assertEqual(case_provenance, provenance_before)

        exception_row = operand_row()
        exception_provenance = deepcopy(provenance)
        exception_provenance_before = deepcopy(exception_provenance)
        with patch.object(
            dependency_projection,
            "_normalise_operand_value",
            side_effect=RuntimeError("normalization failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalization failed"):
                adopt_dependency_structured_provenance(
                    DependencyStructuredProvenanceAdoptionInput(exception_row, exception_provenance)
                )
        self.assertEqual(exception_row["source_anchor"], "[ExampleCo | 2023 | Financial statements]")
        self.assertEqual(exception_row["source_row_ids"], ["ev_lookup", "node_1"])
        self.assertEqual(
            (
                exception_row["consolidation_scope"],
                exception_row["statement_type"],
                exception_row["table_source_id"],
            ),
            ("separate", "notes", "old_table"),
        )
        self.assertNotIn("unit_realigned_from_structured_provenance", exception_row)
        self.assertIs(exception_row["metadata"], nested)
        self.assertEqual(exception_provenance, exception_provenance_before)

    def test_resolve_dependency_producer_scope_preserves_task_precedence_and_hint_order(self) -> None:
        binding = {
            "preferred_task_id": "task_cost",
            "label": "cost",
            "concept": "cost_of_sales",
            "role": "numerator_1",
        }
        calc_task = {
            "task_id": "task_cost",
            "source": "calc_subtasks",
            "preferred_statement_types": ["summary_financials", "cash_flow_statement"],
            "preferred_sections": ["Summary", "Main Statement"],
            "required_operands": [
                {
                    "concept": "cost_of_sales",
                    "role": "numerator_1",
                    "preferred_statement_types": ["income_statement", "summary_financials"],
                    "preferred_sections": ["Income Statement", "Summary"],
                },
                {
                    "concept": "revenue",
                    "role": "denominator_1",
                    "preferred_statement_types": ["notes"],
                    "preferred_sections": ["Notes"],
                },
            ],
        }
        semantic_task = {
            "task_id": "task_cost",
            "source": "semantic_plan",
            "preferred_statement_types": ["semantic_only"],
            "preferred_sections": ["Semantic Only"],
        }

        scope = resolve_dependency_producer_scope(
            binding,
            producer_tasks=[calc_task, semantic_task],
        )

        self.assertEqual(scope.producer_task["source"], "calc_subtasks")
        self.assertEqual(
            scope.preferred_statement_types,
            ("income_statement", "summary_financials", "cash_flow_statement"),
        )
        self.assertEqual(
            scope.preferred_sections,
            ("Income Statement", "Summary", "Main Statement"),
        )

        missing_scope = resolve_dependency_producer_scope(
            {"preferred_task_id": "missing"},
            producer_tasks=[calc_task, semantic_task],
        )
        self.assertEqual(missing_scope.producer_task, {})
        self.assertEqual(missing_scope.preferred_statement_types, ())
        self.assertEqual(missing_scope.preferred_sections, ())

    def test_filter_dependency_rows_applies_statement_and_note_scope_contracts(self) -> None:
        binding = {
            "preferred_task_id": "task_cost",
            "label": "cost",
            "concept": "cost_of_sales",
            "role": "numerator_1",
        }
        base_row = {
            "label": "cost",
            "matched_operand_label": "cost",
            "matched_operand_concept": "cost_of_sales",
            "matched_operand_role": "numerator_1",
        }
        cases = [
            (
                "statement_mismatch",
                {"task_id": "task_cost", "preferred_statement_types": ["income_statement"]},
                {**base_row, "statement_type": "notes"},
                "statement_type",
            ),
            (
                "note_scope_rejected",
                {"task_id": "task_cost", "preferred_statement_types": ["income_statement"]},
                {**base_row, "statement_type": "income_statement", "source_anchor": "Financial Statement Notes"},
                "section_scope",
            ),
            (
                "note_section_allowed",
                {
                    "task_id": "task_cost",
                    "preferred_statement_types": ["income_statement"],
                    "preferred_sections": ["Financial Statement Notes"],
                },
                {**base_row, "statement_type": "income_statement", "source_anchor": "Financial Statement Notes"},
                "",
            ),
            (
                "notes_statement_allowed",
                {"task_id": "task_cost", "preferred_statement_types": ["notes"]},
                {**base_row, "statement_type": "notes", "source_anchor": "Financial Statement Notes"},
                "",
            ),
            (
                "blank_scope_allowed",
                {"task_id": "task_cost", "preferred_statement_types": ["income_statement"]},
                {**base_row, "statement_type": "income_statement"},
                "",
            ),
        ]

        for name, producer_task, row, expected_reason in cases:
            with self.subTest(name=name):
                filtered, rejected = filter_direct_rows_by_dependency_producer_scope(
                    bindings=[binding],
                    operand_rows=[row],
                    producer_tasks=[producer_task],
                )
                if expected_reason:
                    self.assertEqual(filtered, [])
                    self.assertEqual(rejected[0]["reject_reason"], expected_reason)
                else:
                    self.assertEqual(filtered, [row])
                    self.assertEqual(rejected, [])

    def test_filter_dependency_rows_preserves_order_inputs_and_rejection_diagnostics(self) -> None:
        binding = {
            "preferred_task_id": "task_cost",
            "label": "cost",
            "concept": "cost_of_sales",
            "role": "numerator_1",
        }
        producer_task = {
            "task_id": "task_cost",
            "preferred_statement_types": ["income_statement"],
            "preferred_sections": ["Income Statement"],
        }
        rejected_row = {
            "label": "cost",
            "matched_operand_label": "cost",
            "matched_operand_concept": "cost_of_sales",
            "matched_operand_role": "numerator_1",
            "statement_type": " cash_flow_statement ",
        }
        kept_row = {
            "label": "cost",
            "matched_operand_label": "cost",
            "matched_operand_concept": "cost_of_sales",
            "matched_operand_role": "numerator_1",
            "statement_type": "income_statement",
        }
        unmatched_row = {
            "label": "revenue",
            "matched_operand_label": "revenue",
            "matched_operand_concept": "revenue",
            "matched_operand_role": "denominator_1",
            "statement_type": "notes",
        }
        bindings = [binding]
        operand_rows = [rejected_row, kept_row, unmatched_row]
        original_bindings = deepcopy(bindings)
        original_rows = deepcopy(operand_rows)

        filtered, rejected = filter_direct_rows_by_dependency_producer_scope(
            bindings=bindings,
            operand_rows=operand_rows,
            producer_tasks=[producer_task],
        )

        self.assertEqual(filtered, [kept_row, unmatched_row])
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["binding"], binding)
        self.assertEqual(rejected[0]["row"], rejected_row)
        self.assertEqual(rejected[0]["reject_reason"], "statement_type")
        self.assertEqual(rejected[0]["preferred_statement_types"], ["income_statement"])
        self.assertEqual(rejected[0]["preferred_sections"], ["Income Statement"])
        self.assertEqual(rejected[0]["row_statement_type"], "cash_flow_statement")
        self.assertEqual(bindings, original_bindings)
        self.assertEqual(operand_rows, original_rows)

    def test_dependency_binding_summary_preserves_schema_and_copy_contract(self) -> None:
        current_binding = {
            "label": " Target ",
            "role": "Current_Period",
        }
        first_prior_binding = {
            "label": "target",
            "role": "prior_period",
            "metadata": {"source": "first"},
        }
        blank_binding = {"label": " ", "role": ""}
        second_prior_binding = {
            "label": "target",
            "role": "prior_period",
            "metadata": {"source": "second"},
        }
        bindings = [
            current_binding,
            first_prior_binding,
            blank_binding,
            second_prior_binding,
        ]
        rows = [
            {
                "matched_operand_label": "Target",
                "matched_operand_role": "Current_Period",
            },
            {},
        ]
        bindings_before = deepcopy(bindings)
        rows_before = deepcopy(rows)

        summary = summarize_dependency_bindings(bindings, rows)

        self.assertEqual(
            summary["binding_keys"],
            {("Target", "Current_Period"), ("target", "prior_period")},
        )
        self.assertEqual(
            summary["resolved_keys"],
            {("Target", "Current_Period"), ("", "")},
        )
        self.assertEqual(
            summary["missing_bindings"],
            [first_prior_binding, second_prior_binding],
        )
        self.assertIsNot(summary["missing_bindings"][0], first_prior_binding)
        self.assertIs(
            summary["missing_bindings"][0]["metadata"],
            first_prior_binding["metadata"],
        )
        self.assertEqual(summary["binding_count"], 4)
        self.assertEqual(summary["resolved_binding_count"], 2)
        self.assertTrue(summary["has_bindings"])
        self.assertTrue(summary["has_rows"])
        self.assertFalse(summary["all_resolved"])
        self.assertEqual(bindings, bindings_before)
        self.assertEqual(rows, rows_before)
        summary["missing_bindings"][0]["label"] = "mutated"
        self.assertEqual(first_prior_binding["label"], "target")

    def test_dependency_binding_summary_all_resolved_truth_table(self) -> None:
        binding = {"label": "target", "role": "current_period"}
        row = {
            "matched_operand_label": "target",
            "matched_operand_role": "current_period",
        }
        cases = [
            ("empty", [], [], 0, 0, False, False, False),
            ("binding without row", [binding], [], 1, 0, True, False, False),
            ("resolved", [binding], [row], 1, 1, True, True, True),
            (
                "duplicate bindings",
                [binding, dict(binding)],
                [row],
                2,
                2,
                True,
                True,
                True,
            ),
            (
                "blank binding and row",
                [{"label": "", "role": ""}],
                [{}],
                1,
                1,
                True,
                True,
                True,
            ),
        ]

        for (
            name,
            bindings,
            rows,
            binding_count,
            resolved_count,
            has_bindings,
            has_rows,
            all_resolved,
        ) in cases:
            with self.subTest(name=name):
                summary = summarize_dependency_bindings(bindings, rows)
                self.assertEqual(summary["binding_count"], binding_count)
                self.assertEqual(summary["resolved_binding_count"], resolved_count)
                self.assertEqual(summary["has_bindings"], has_bindings)
                self.assertEqual(summary["has_rows"], has_rows)
                self.assertEqual(summary["all_resolved"], all_resolved)

    def test_direct_rows_resolve_canonical_dependency_keys_via_matcher(self) -> None:
        current_binding = {
            "label": " target ",
            "concept": "target_concept",
            "role": "current_period",
            "period_hint": "2023",
            "unit_family": "KRW",
        }
        bindings = [
            current_binding,
            dict(current_binding),
            {**current_binding, "role": "prior_period"},
            {"label": "", "role": ""},
        ]
        rows = [
            {
                "label": "unrelated surface",
                "matched_operand_concept": "target_concept",
                "matched_operand_role": "current_period",
                "period": "2023",
                "normalized_unit": "KRW",
            }
        ]
        bindings_before = deepcopy(bindings)
        rows_before = deepcopy(rows)

        resolved_keys = direct_rows_resolved_dependency_keys(bindings, rows)

        self.assertEqual(
            dependency_binding_identity(current_binding),
            ("target", "current_period"),
        )
        self.assertEqual(resolved_keys, {("target", "current_period")})
        self.assertEqual(bindings, bindings_before)
        self.assertEqual(rows, rows_before)

    def _task_output_row(self, **overrides):
        row = {
            "dependency_resolved": True,
            "source_task_id": "task_total",
            "evidence_id": "task_output:task_total",
            "source_row_ids": ["task_output:task_total", "shared_total"],
            "raw_value": "2,000",
            "raw_unit": "천원",
            "normalized_value": 2_000_000.0,
            "normalized_unit": "KRW",
        }
        row.update(overrides)
        return row

    def _direct_row(self, **overrides):
        row = {
            "evidence_id": "direct_detail",
            "source_row_ids": ["direct_detail", "shared_total"],
            "raw_value": "1,500",
            "raw_unit": "천원",
            "normalized_value": 1_500_000.0,
            "normalized_unit": "KRW",
        }
        row.update(overrides)
        return row

    def _source_operand_row(
        self,
        candidate_id: str,
        *,
        label: str,
        role: str,
        value: float,
        table_source_id: str,
        source_row_ids: List[str] | None = None,
        dependency_resolved: bool = False,
        source_task_id: str = "",
    ) -> Dict[str, Any]:
        return {
            "evidence_id": candidate_id,
            "source_row_id": candidate_id,
            "source_row_ids": list(source_row_ids or [candidate_id]),
            "label": label,
            "matched_operand_label": label,
            "matched_operand_role": role,
            "raw_value": str(value),
            "raw_unit": "unit",
            "normalized_value": value,
            "normalized_unit": "KRW",
            "table_source_id": table_source_id,
            "dependency_resolved": dependency_resolved,
            "source_task_id": source_task_id,
        }

    def _source_selection_fixture(
        self,
        *,
        roles: tuple[str, str] = ("numerator_1", "denominator_1"),
        labels: tuple[str, str] = ("target", "base"),
        direct_values: tuple[float, float] = (80.0, 40.0),
        dependency_values: tuple[float, float] = (100.0, 50.0),
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        required_operands = [
            {"label": label, "role": role, "required": True}
            for label, role in zip(labels, roles)
        ]
        direct_rows = [
            self._source_operand_row(
                f"direct_{index}",
                label=label,
                role=role,
                value=value,
                table_source_id="direct_table",
            )
            for index, (label, role, value) in enumerate(
                zip(labels, roles, direct_values),
                start=1,
            )
        ]
        dependency_rows = [
            self._source_operand_row(
                f"dependency_{index}",
                label=label,
                role=role,
                value=value,
                table_source_id="dependency_table",
                source_row_ids=[f"task_output:task_{index}"],
                dependency_resolved=True,
                source_task_id=f"task_{index}",
            )
            for index, (label, role, value) in enumerate(
                zip(labels, roles, dependency_values),
                start=1,
            )
        ]
        return required_operands, direct_rows, dependency_rows

    def _source_selection_input(
        self,
        required_operands: List[Dict[str, Any]],
        direct_rows: List[Dict[str, Any]],
        dependency_rows: List[Dict[str, Any]],
        **overrides: Any,
    ) -> DirectDependencySelectionInput:
        values: Dict[str, Any] = {
            "operation_family": "ratio",
            "required_operands": required_operands,
            "direct_rows": direct_rows,
            "dependency_rows": dependency_rows,
            "desired_consolidation_scope": "unknown",
            "reconciliation_evidence_present": False,
            "direct_rows_cover_required_operands": True,
            "dependency_rows_cover_required_operands": True,
            "direct_rows_have_coherent_context": True,
            "retrieved_ratio_context_recovered": False,
            "ratio_direct_context_should_override_dependency": False,
            "required_prefers_aggregate_stage": False,
        }
        values.update(overrides)
        return DirectDependencySelectionInput(**values)

    def _main_precedence_input(
        self,
        required_operands: List[Dict[str, Any]],
        direct_rows: List[Dict[str, Any]],
        dependency_rows: List[Dict[str, Any]],
        dependency_bindings: List[Dict[str, Any]],
        dependency_binding_keys: set[tuple[str, str]],
        dependency_resolved_keys: set[tuple[str, str]],
        missing_dependency_bindings: List[Dict[str, Any]],
        **overrides: Any,
    ) -> MainOperandPrecedenceInput:
        values: Dict[str, Any] = {
            "operation_family": "ratio",
            "required_operands": required_operands,
            "direct_rows": direct_rows,
            "dependency_rows": dependency_rows,
            "dependency_bindings": dependency_bindings,
            "dependency_binding_keys": dependency_binding_keys,
            "dependency_resolved_keys": dependency_resolved_keys,
            "missing_dependency_bindings": missing_dependency_bindings,
            "producer_tasks": [],
            "desired_consolidation_scope": "unknown",
            "reconciliation_evidence_present": False,
            "retrieved_ratio_context_recovered": False,
        }
        values.update(overrides)
        return MainOperandPrecedenceInput(**values)

    def _late_remerge_input(
        self,
        required_operands: List[Dict[str, Any]],
        operand_rows: List[Dict[str, Any]],
        dependency_rows: List[Dict[str, Any]],
        **overrides: Any,
    ) -> LateDependencyRemergeInput:
        values: Dict[str, Any] = {
            "operation_family": "ratio",
            "required_operands": required_operands,
            "operand_rows": operand_rows,
            "dependency_rows": dependency_rows,
            "sibling_context_rows": [],
            "coherent_context_rows": [],
            "prefer_direct_rows_over_dependency": False,
            "required_prefers_aggregate_stage": False,
        }
        values.update(overrides)
        return LateDependencyRemergeInput(**values)

    def _late_finalization_input(
        self,
        operand_rows: List[Dict[str, Any]],
        direct_structured_rows: List[Dict[str, Any]],
        dependency_rows: List[Dict[str, Any]],
        **overrides: Any,
    ) -> LateOperandFinalizationInput:
        values: Dict[str, Any] = {
            "operand_rows": operand_rows,
            "direct_structured_rows": direct_structured_rows,
            "dependency_rows": dependency_rows,
            "required_normalized_unit": None,
        }
        values.update(overrides)
        return LateOperandFinalizationInput(**values)

    def test_late_finalization_percent_filter_preserves_eligible_order_and_row_identity(self) -> None:
        _required_operands, direct_rows, dependency_rows = self._source_selection_fixture()
        operand_rows = [
            {**direct_rows[0], "normalized_unit": "PERCENT"},
            dict(direct_rows[1]),
            {**dependency_rows[0], "evidence_id": "percent_2", "normalized_unit": "PERCENT"},
        ]
        owner_input = self._late_finalization_input(
            operand_rows,
            direct_rows,
            dependency_rows,
            required_normalized_unit="PERCENT",
        )
        input_snapshot = deepcopy(owner_input)

        result = resolve_late_operand_finalization(owner_input)

        self.assertEqual(
            [row.get("evidence_id") for row in result.operand_rows],
            ["direct_1", "percent_2"],
        )
        self.assertIs(result.operand_rows[0], operand_rows[0])
        self.assertIs(result.operand_rows[1], operand_rows[2])
        self.assertTrue(result.operand_filter_applied)
        self.assertEqual(result.preserved_operand_source, "")
        self.assertEqual(result.finalization_reason, "normalized_unit_filtered")
        self.assertEqual(owner_input, input_snapshot)

    def test_late_finalization_empty_percent_filter_blocks_all_preservation(self) -> None:
        _required_operands, direct_rows, dependency_rows = self._source_selection_fixture()

        result = resolve_late_operand_finalization(
            self._late_finalization_input(
                direct_rows,
                direct_rows,
                dependency_rows,
                required_normalized_unit="PERCENT",
            )
        )

        self.assertEqual(result.operand_rows, [])
        self.assertTrue(result.operand_filter_applied)
        self.assertEqual(result.preserved_operand_source, "")
        self.assertEqual(result.finalization_reason, "normalized_unit_filtered")

    def test_late_finalization_existing_rows_preserve_list_identity(self) -> None:
        _required_operands, direct_rows, dependency_rows = self._source_selection_fixture()

        result = resolve_late_operand_finalization(
            self._late_finalization_input(direct_rows, direct_rows, dependency_rows)
        )

        self.assertIs(result.operand_rows, direct_rows)
        self.assertFalse(result.operand_filter_applied)
        self.assertEqual(result.preserved_operand_source, "")
        self.assertEqual(result.finalization_reason, "operand_rows_retained")

    def test_late_finalization_empty_rows_preserve_direct_shallow_copies(self) -> None:
        _required_operands, direct_rows, dependency_rows = self._source_selection_fixture()
        direct_rows[0]["metadata"] = {"token": "shared"}
        input_snapshot = deepcopy(direct_rows)

        result = resolve_late_operand_finalization(
            self._late_finalization_input([], direct_rows, dependency_rows)
        )

        self.assertEqual(
            [row.get("evidence_id") for row in result.operand_rows],
            ["direct_1", "direct_2"],
        )
        self.assertIsNot(result.operand_rows, direct_rows)
        self.assertTrue(
            all(result_row is not direct_row for result_row, direct_row in zip(result.operand_rows, direct_rows))
        )
        self.assertIs(result.operand_rows[0]["metadata"], direct_rows[0]["metadata"])
        self.assertEqual(result.preserved_operand_source, "structured_rows")
        self.assertEqual(result.finalization_reason, "structured_rows_preserved")
        self.assertEqual(direct_rows, input_snapshot)

    def test_late_finalization_empty_direct_rows_preserve_dependency_copies(self) -> None:
        _required_operands, _direct_rows, dependency_rows = self._source_selection_fixture()

        result = resolve_late_operand_finalization(
            self._late_finalization_input([], [], dependency_rows)
        )

        self.assertEqual(
            [row.get("evidence_id") for row in result.operand_rows],
            ["dependency_1", "dependency_2"],
        )
        self.assertIsNot(result.operand_rows, dependency_rows)
        self.assertTrue(
            all(
                result_row is not dependency_row
                for result_row, dependency_row in zip(result.operand_rows, dependency_rows)
            )
        )
        self.assertEqual(result.preserved_operand_source, "dependency_outputs")
        self.assertEqual(result.finalization_reason, "dependency_rows_preserved")

    def test_late_finalization_all_empty_preserves_operand_identity_and_reason(self) -> None:
        operand_rows: List[Dict[str, Any]] = []

        result = resolve_late_operand_finalization(
            self._late_finalization_input(operand_rows, [], [])
        )

        self.assertIs(result.operand_rows, operand_rows)
        self.assertFalse(result.operand_filter_applied)
        self.assertEqual(result.preserved_operand_source, "")
        self.assertEqual(result.finalization_reason, "no_operand_rows")

    def test_ratio_artifact_conflict_selection_preserves_numeric_authority_order_and_inputs(self) -> None:
        nested_context = {"keep": "artifact"}
        artifact_rows = [
            {
                "artifact_id": "non_ok",
                "status": "parse_error",
                "calculation_result": {"status": "ok", "result_value": 150.0},
            },
            {"artifact_id": "no_value", "status": "ok", "calculation_result": {}},
            {
                "artifact_id": "calculation_result_value",
                "status": "ok",
                "result_value": 400.0,
                "calculation_result": {
                    "result_value": 100.04,
                    "answer_slots": {
                        "primary_value": {"normalized_value": 200.0, "raw_value": "300"}
                    },
                },
            },
            {
                "artifact_id": "primary_normalized_value",
                "result_value": 300.0,
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {"normalized_value": 100.03, "raw_value": "200"}
                    },
                },
            },
            {
                "artifact_id": "primary_raw_value",
                "status": "ok",
                "result_value": 300.0,
                "calculation_result": {
                    "answer_slots": {"primary_value": {"raw_value": "100.02"}}
                },
            },
            {"artifact_id": "row_value", "status": "ok", "calculation_result": {}, "result_value": 100.01},
            {
                "artifact_id": "first_conflict",
                "status": "ok",
                "calculation_result": {"result_value": 120.0, "nested": nested_context},
                "nested": nested_context,
            },
            {"artifact_id": "later_conflict", "status": "ok", "calculation_result": {"result_value": 130.0}},
        ]
        selection_input = dependency_projection.RatioArtifactConflictSelectionInput(
            artifact_rows,
            100.0,
        )
        input_before = deepcopy(selection_input)

        with patch.object(
            dependency_projection,
            "_ratio_artifact_numeric_value",
            wraps=dependency_projection._ratio_artifact_numeric_value,
        ) as numeric_value:
            result = dependency_projection.resolve_ratio_artifact_conflict_selection(
                selection_input
            )

        self.assertEqual(selection_input, input_before)
        self.assertEqual(
            [call.args[0]["artifact_id"] for call in numeric_value.call_args_list],
            [
                "no_value",
                "calculation_result_value",
                "primary_normalized_value",
                "primary_raw_value",
                "row_value",
                "first_conflict",
            ],
        )
        self.assertEqual(
            (result.conflict_selected, result.reason, result.selected_artifact_row["artifact_id"]),
            (True, "conflicting_artifact_selected", "first_conflict"),
        )
        self.assertTrue(
            result.selected_artifact_row["artifact_ratio_result_preserved_over_alignment"]
        )
        self.assertIsNot(result.selected_artifact_row, artifact_rows[-2])
        self.assertIs(result.selected_artifact_row["nested"], nested_context)
        self.assertIs(
            result.selected_artifact_row["calculation_result"],
            artifact_rows[-2]["calculation_result"],
        )

        no_match = dependency_projection.resolve_ratio_artifact_conflict_selection(
            dependency_projection.RatioArtifactConflictSelectionInput(
                artifact_rows[:-2],
                100.0,
            )
        )
        self.assertEqual(
            (no_match.selected_artifact_row, no_match.conflict_selected, no_match.reason),
            ({}, False, "no_conflicting_artifact"),
        )

    def test_late_remerge_complete_coherent_context_blocks_dependency(self) -> None:
        required_operands, direct_rows, dependency_rows = self._source_selection_fixture()
        operand_rows = [dict(direct_rows[0])]
        sibling_context_rows = [dict(direct_rows[0])]
        owner_input = self._late_remerge_input(
            required_operands,
            operand_rows,
            dependency_rows,
            sibling_context_rows=sibling_context_rows,
            coherent_context_rows=direct_rows,
        )
        input_snapshot = deepcopy(owner_input)

        result = resolve_late_dependency_remerge(owner_input)

        self.assertEqual(
            [row.get("evidence_id") for row in result.active_direct_context_rows],
            ["direct_1", "direct_2"],
        )
        self.assertEqual(
            [row.get("evidence_id") for row in result.operand_rows],
            ["direct_1", "direct_2"],
        )
        self.assertTrue(result.complete_direct_context_blocks_dependency_remerge)
        self.assertFalse(result.dependency_remerge_applied)
        self.assertEqual(result.dependency_remerge_reason, "complete_direct_context")
        self.assertEqual(owner_input, input_snapshot)

    def test_late_remerge_incomplete_context_applies_dependency_first_copy(self) -> None:
        required_operands, direct_rows, dependency_rows = self._source_selection_fixture()
        operand_rows = [dict(direct_rows[0])]
        sibling_context_rows = [dict(direct_rows[0])]
        owner_input = self._late_remerge_input(
            required_operands,
            operand_rows,
            dependency_rows,
            sibling_context_rows=sibling_context_rows,
        )
        input_snapshot = deepcopy(owner_input)

        result = resolve_late_dependency_remerge(owner_input)

        self.assertIs(result.active_direct_context_rows, sibling_context_rows)
        self.assertFalse(result.complete_direct_context_blocks_dependency_remerge)
        self.assertTrue(result.dependency_remerge_applied)
        self.assertEqual(result.dependency_remerge_reason, "dependency_remerged")
        self.assertEqual(
            [row.get("evidence_id") for row in result.operand_rows],
            ["dependency_1", "dependency_2"],
        )
        self.assertIsNot(result.operand_rows, dependency_rows)
        self.assertTrue(
            all(
                result_row is not dependency_row
                for result_row, dependency_row in zip(result.operand_rows, dependency_rows)
            )
        )
        self.assertEqual(owner_input, input_snapshot)

    def test_late_remerge_aggregate_veto_still_remerges_dependency(self) -> None:
        required_operands, direct_rows, dependency_rows = self._source_selection_fixture()
        result = resolve_late_dependency_remerge(
            self._late_remerge_input(
                required_operands,
                direct_rows,
                dependency_rows,
                sibling_context_rows=direct_rows,
                coherent_context_rows=direct_rows,
                required_prefers_aggregate_stage=True,
            )
        )

        self.assertEqual(result.active_direct_context_rows, [])
        self.assertFalse(result.complete_direct_context_blocks_dependency_remerge)
        self.assertTrue(result.dependency_remerge_applied)
        self.assertEqual(result.dependency_remerge_reason, "dependency_remerged")
        self.assertEqual(
            [row.get("evidence_id") for row in result.operand_rows],
            ["dependency_1", "dependency_2"],
        )

    def test_late_remerge_no_dependency_preserves_operand_identity(self) -> None:
        required_operands, direct_rows, _dependency_rows = self._source_selection_fixture()
        result = resolve_late_dependency_remerge(
            self._late_remerge_input(
                required_operands,
                direct_rows,
                [],
                operation_family="difference",
            )
        )

        self.assertIs(result.operand_rows, direct_rows)
        self.assertEqual(result.active_direct_context_rows, [])
        self.assertFalse(result.complete_direct_context_blocks_dependency_remerge)
        self.assertFalse(result.dependency_remerge_applied)
        self.assertEqual(result.dependency_remerge_reason, "no_dependency_rows")

    def test_late_remerge_direct_precedence_preserves_operand_identity(self) -> None:
        required_operands, direct_rows, dependency_rows = self._source_selection_fixture()
        result = resolve_late_dependency_remerge(
            self._late_remerge_input(
                required_operands,
                direct_rows,
                dependency_rows,
                operation_family="difference",
                prefer_direct_rows_over_dependency=True,
            )
        )

        self.assertIs(result.operand_rows, direct_rows)
        self.assertFalse(result.dependency_remerge_applied)
        self.assertEqual(result.dependency_remerge_reason, "direct_precedence")

    def test_direct_dependency_precedence_no_dependency_preserves_identity(self) -> None:
        required_operands, direct_rows, _dependency_rows = self._source_selection_fixture()
        dependency_rows: List[Dict[str, Any]] = []
        direct_snapshot = deepcopy(direct_rows)

        decision = select_direct_dependency_operand_rows(
            self._source_selection_input(
                required_operands,
                direct_rows,
                dependency_rows,
            )
        )

        self.assertIs(decision.operand_rows, direct_rows)
        self.assertIs(decision.dependency_rows, dependency_rows)
        self.assertEqual(decision.precedence, "no_dependency")
        self.assertFalse(decision.dependency_merge_applied)
        self.assertEqual(direct_rows, direct_snapshot)

        ratio_decision = select_direct_dependency_operand_rows(
            self._source_selection_input(
                required_operands,
                direct_rows,
                dependency_rows,
                retrieved_ratio_context_recovered=True,
                ratio_direct_context_should_override_dependency=True,
            )
        )

        self.assertIs(ratio_decision.operand_rows, direct_rows)
        self.assertTrue(ratio_decision.prefer_direct_rows_over_dependency)

    def test_period_conflict_requires_reconciliation_to_prefer_direct(self) -> None:
        required_operands, direct_rows, dependency_rows = self._source_selection_fixture(
            roles=("current_period", "prior_period"),
            labels=("current", "prior"),
            direct_values=(120.0, 100.0),
            dependency_values=(90.0, 70.0),
        )

        for reconciliation_present, expected_precedence, expected_prefix in (
            (False, "dependency_first", "dependency_"),
            (True, "direct_first", "direct_"),
        ):
            with self.subTest(reconciliation_present=reconciliation_present):
                decision = select_direct_dependency_operand_rows(
                    self._source_selection_input(
                        required_operands,
                        direct_rows,
                        dependency_rows,
                        operation_family="growth_rate",
                        reconciliation_evidence_present=reconciliation_present,
                    )
                )

                self.assertEqual(decision.precedence, expected_precedence)
                self.assertTrue(
                    all(
                        str(row.get("evidence_id") or "").startswith(expected_prefix)
                        for row in decision.operand_rows
                    )
                )
                self.assertEqual(
                    decision.period_dependency_blocks_direct_context,
                    not reconciliation_present,
                )

    def test_ratio_context_and_aggregation_veto_are_distinct(self) -> None:
        required_operands, direct_rows, dependency_rows = self._source_selection_fixture()

        for reconciliation_present, retrieved_context, aggregate_veto, expected_precedence in (
            (False, True, False, "direct_first"),
            (True, False, False, "direct_first"),
            (True, False, True, "dependency_first"),
        ):
            with self.subTest(
                reconciliation_present=reconciliation_present,
                retrieved_context=retrieved_context,
                aggregate_veto=aggregate_veto,
            ):
                decision = select_direct_dependency_operand_rows(
                    self._source_selection_input(
                        required_operands,
                        direct_rows,
                        dependency_rows,
                        reconciliation_evidence_present=reconciliation_present,
                        retrieved_ratio_context_recovered=retrieved_context,
                        ratio_direct_context_should_override_dependency=retrieved_context,
                        required_prefers_aggregate_stage=aggregate_veto,
                    )
                )

                self.assertEqual(decision.precedence, expected_precedence)
                if aggregate_veto:
                    self.assertIs(decision.dependency_rows, dependency_rows)
                    self.assertTrue(
                        all(
                            str(row.get("evidence_id") or "").startswith("dependency_")
                            for row in decision.operand_rows
                        )
                    )
                    self.assertTrue(
                        all(
                            "sibling_table_context_realignment_blocked" not in row
                            and "sibling_table_context_realigned" not in row
                            for row in decision.dependency_rows
                        )
                    )
                else:
                    self.assertIsNot(decision.dependency_rows, dependency_rows)

    def test_lookup_keeps_complete_dependency_precedence(self) -> None:
        required_operands = [{"label": "target", "role": "primary_value", "required": True}]
        direct_rows = [
            self._source_operand_row(
                "direct_lookup",
                label="target",
                role="primary_value",
                value=80.0,
                table_source_id="direct_table",
            )
        ]
        dependency_rows = [
            self._source_operand_row(
                "dependency_lookup",
                label="target",
                role="primary_value",
                value=100.0,
                table_source_id="dependency_table",
                source_row_ids=["task_output:task_lookup"],
                dependency_resolved=True,
                source_task_id="task_lookup",
            )
        ]

        decision = select_direct_dependency_operand_rows(
            self._source_selection_input(
                required_operands,
                direct_rows,
                dependency_rows,
                operation_family="lookup",
                reconciliation_evidence_present=True,
            )
        )

        self.assertEqual(decision.precedence, "dependency_first")
        self.assertEqual(
            [row.get("evidence_id") for row in decision.operand_rows],
            ["dependency_lookup"],
        )

    def test_requested_scope_filter_preserves_merge_order_and_input_immutability(self) -> None:
        required_operands, direct_rows, dependency_rows = self._source_selection_fixture()
        direct_rows = [
            {
                **direct_rows[1],
                "consolidation_scope": "unknown",
            }
        ]
        dependency_rows = [
            {
                **dependency_rows[0],
                "consolidation_scope": "consolidated",
            },
            {
                **dependency_rows[1],
                "consolidation_scope": "separate",
            },
        ]
        direct_snapshot = deepcopy(direct_rows)
        dependency_snapshot = deepcopy(dependency_rows)

        decision = select_direct_dependency_operand_rows(
            self._source_selection_input(
                required_operands,
                direct_rows,
                dependency_rows,
                operation_family="lookup",
                desired_consolidation_scope="consolidated",
                direct_rows_cover_required_operands=False,
            )
        )

        self.assertEqual(
            [row.get("evidence_id") for row in decision.operand_rows],
            ["dependency_1"],
        )
        self.assertEqual(direct_rows, direct_snapshot)
        self.assertEqual(dependency_rows, dependency_snapshot)
        self.assertIsNot(decision.operand_rows[0], dependency_rows[0])

    def test_main_precedence_ratio_override_purges_active_dependency_state_atomically(self) -> None:
        required_operands, direct_rows, dependency_rows = self._source_selection_fixture(
            direct_values=(80.0, 40.0),
            dependency_values=(100.0, 50.0),
        )
        dependency_rows[0]["raw_unit"] = "dependency_unit_a"
        dependency_rows[1]["raw_unit"] = "dependency_unit_b"
        dependency_bindings = [
            {"label": "target", "role": "numerator_1", "preferred_task_id": "task_1"},
            {"label": "base", "role": "denominator_1", "preferred_task_id": "task_2"},
        ]
        dependency_binding_keys = {
            dependency_binding_identity(binding)
            for binding in dependency_bindings
        }
        dependency_resolved_keys = {
            dependency_binding_identity(dependency_bindings[0])
        }
        missing_dependency_bindings = [dict(dependency_bindings[1])]
        precedence_input = self._main_precedence_input(
            required_operands,
            direct_rows,
            dependency_rows,
            dependency_bindings,
            dependency_binding_keys,
            dependency_resolved_keys,
            missing_dependency_bindings,
            retrieved_ratio_context_recovered=True,
        )
        input_snapshot = deepcopy(precedence_input)

        result = resolve_main_operand_precedence(precedence_input)

        self.assertNotEqual(
            [row["normalized_value"] for row in dependency_rows],
            [row["normalized_value"] for row in direct_rows],
        )
        self.assertEqual(
            {row["raw_unit"] for row in dependency_rows},
            {"dependency_unit_a", "dependency_unit_b"},
        )
        self.assertEqual({row["raw_unit"] for row in direct_rows}, {"unit"})
        self.assertTrue(result.ratio_direct_context_should_override_dependency)
        self.assertTrue(result.ratio_direct_context_override_applied)
        self.assertFalse(result.required_prefers_aggregate_stage)
        self.assertTrue(result.direct_dependency_fill_allowed)
        self.assertEqual(result.source_selection.precedence, "no_dependency")
        self.assertIs(result.source_selection.operand_rows, direct_rows)
        self.assertEqual(
            [row.get("evidence_id") for row in result.selected_operand_rows],
            ["direct_1", "direct_2"],
        )
        self.assertEqual(result.source_selection.dependency_rows, [])
        self.assertIsNot(result.source_selection.dependency_rows, dependency_rows)
        self.assertEqual(result.active_dependency_rows, [])
        self.assertIs(
            result.active_dependency_rows,
            result.source_selection.dependency_rows,
        )
        self.assertEqual(result.active_dependency_bindings, [])
        self.assertIsNot(result.active_dependency_bindings, dependency_bindings)
        self.assertEqual(result.dependency_resolved_keys, set())
        self.assertIsNot(result.dependency_resolved_keys, dependency_resolved_keys)
        self.assertEqual(result.missing_dependency_bindings, [])
        self.assertIsNot(result.missing_dependency_bindings, missing_dependency_bindings)
        self.assertIs(result.dependency_binding_keys, dependency_binding_keys)
        self.assertEqual(result.rejected_dependency_scope_rows, [])
        self.assertEqual(precedence_input, input_snapshot)

    def test_main_precedence_aggregate_stage_veto_preserves_dependency_state_identity(self) -> None:
        required_operands, direct_rows, dependency_rows = self._source_selection_fixture(
            direct_values=(100.0, 50.0),
            dependency_values=(100.0, 50.0),
        )
        required_operands = [
            {
                **operand,
                "binding_policy": {"prefer_aggregation_stages": ["final", "subtotal"]},
            }
            for operand in required_operands
        ]
        dependency_bindings = [
            {"label": "target", "role": "numerator_1", "preferred_task_id": "task_1"},
            {"label": "base", "role": "denominator_1", "preferred_task_id": "task_2"},
        ]
        dependency_binding_keys = {
            dependency_binding_identity(binding)
            for binding in dependency_bindings
        }
        dependency_resolved_keys = set(dependency_binding_keys)
        missing_dependency_bindings = [
            {"label": "unfilled", "role": "denominator_2", "preferred_task_id": "task_3"}
        ]
        precedence_input = self._main_precedence_input(
            required_operands,
            direct_rows,
            dependency_rows,
            dependency_bindings,
            dependency_binding_keys,
            dependency_resolved_keys,
            missing_dependency_bindings,
            retrieved_ratio_context_recovered=True,
        )
        input_snapshot = deepcopy(precedence_input)

        result = resolve_main_operand_precedence(precedence_input)

        self.assertTrue(result.required_prefers_aggregate_stage)
        self.assertTrue(result.ratio_direct_context_should_override_dependency)
        self.assertFalse(result.ratio_direct_context_override_applied)
        self.assertFalse(result.direct_dependency_fill_allowed)
        self.assertEqual(result.source_selection.precedence, "dependency_first")
        self.assertIs(result.source_selection.dependency_rows, dependency_rows)
        self.assertIs(result.active_dependency_rows, dependency_rows)
        self.assertIs(result.active_dependency_bindings, dependency_bindings)
        self.assertIs(result.dependency_binding_keys, dependency_binding_keys)
        self.assertIs(result.dependency_resolved_keys, dependency_resolved_keys)
        self.assertIs(result.missing_dependency_bindings, missing_dependency_bindings)
        self.assertEqual(
            [row.get("evidence_id") for row in result.selected_operand_rows],
            ["dependency_1", "dependency_2"],
        )
        self.assertTrue(
            all(
                "sibling_table_context_realigned" not in row
                and "sibling_table_context_realignment_blocked" not in row
                for row in result.source_selection.dependency_rows
            )
        )
        self.assertEqual(result.rejected_dependency_scope_rows, [])
        self.assertEqual(precedence_input, input_snapshot)

    def test_main_precedence_missing_binding_scope_pass_preserves_rejection_order(self) -> None:
        required_operands = [
            {"label": "current", "role": "current_period", "required": True},
            {"label": "prior", "role": "prior_period", "required": True},
        ]
        dependency_rows = [
            {
                **self._source_operand_row(
                    "dependency_current",
                    label="current",
                    role="current_period",
                    value=120.0,
                    table_source_id="dependency_table",
                    source_row_ids=["task_output:task_current"],
                    dependency_resolved=True,
                    source_task_id="task_current",
                ),
                "statement_type": "cash_flow_statement",
            }
        ]
        direct_rows = [
            {
                **self._source_operand_row(
                    "direct_prior",
                    label="prior",
                    role="prior_period",
                    value=100.0,
                    table_source_id="direct_table",
                ),
                "statement_type": "income_statement",
                "source_anchor": "Financial Statement Notes",
            },
        ]
        dependency_bindings = [
            {"label": "current", "role": "current_period", "preferred_task_id": "task_current"},
        ]
        missing_dependency_bindings = [
            {"label": "prior", "role": "prior_period", "preferred_task_id": "task_prior"},
        ]
        dependency_binding_keys = {
            dependency_binding_identity(binding)
            for binding in [*dependency_bindings, *missing_dependency_bindings]
        }
        dependency_resolved_keys = {
            dependency_binding_identity(dependency_bindings[0])
        }
        producer_tasks = [
            {"task_id": "task_current", "preferred_statement_types": ["income_statement"]},
            {"task_id": "task_prior", "preferred_statement_types": ["income_statement"]},
        ]
        precedence_input = self._main_precedence_input(
            required_operands,
            direct_rows,
            dependency_rows,
            dependency_bindings,
            dependency_binding_keys,
            dependency_resolved_keys,
            missing_dependency_bindings,
            operation_family="difference",
            producer_tasks=producer_tasks,
        )
        input_snapshot = deepcopy(precedence_input)

        result = resolve_main_operand_precedence(precedence_input)

        self.assertEqual(result.source_selection.precedence, "dependency_first")
        self.assertTrue(result.direct_dependency_fill_allowed)
        self.assertEqual(
            [row.get("evidence_id") for row in result.source_selection.operand_rows],
            ["dependency_current", "direct_prior"],
        )
        self.assertEqual(result.selected_operand_rows, [])
        self.assertEqual(result.active_dependency_rows, [])
        self.assertEqual(
            [entry["row"].get("evidence_id") for entry in result.rejected_dependency_scope_rows],
            ["dependency_current", "direct_prior"],
        )
        self.assertEqual(
            [entry["reject_reason"] for entry in result.rejected_dependency_scope_rows],
            ["statement_type", "section_scope"],
        )
        self.assertIs(result.missing_dependency_bindings, missing_dependency_bindings)
        self.assertEqual(precedence_input, input_snapshot)

    def test_main_precedence_duplicate_guard_removes_resolved_direct_row_after_selection(self) -> None:
        dependency_rows = [
            {
                **self._source_operand_row(
                    "dependency_current",
                    label="current",
                    role="current_period",
                    value=120.0,
                    table_source_id="dependency_table",
                    source_row_ids=["task_output:task_current"],
                    dependency_resolved=True,
                    source_task_id="task_current",
                ),
                "source_anchor": "dependency_current_anchor",
            }
        ]
        direct_rows = [
            {
                **self._source_operand_row(
                    "direct_current",
                    label="current",
                    role="current_period",
                    value=125.0,
                    table_source_id="direct_current_table",
                ),
                "source_anchor": "direct_current_anchor",
            },
            {
                **self._source_operand_row(
                    "direct_prior",
                    label="prior",
                    role="prior_period",
                    value=100.0,
                    table_source_id="direct_prior_table",
                ),
                "source_anchor": "direct_prior_anchor",
            },
        ]
        dependency_bindings = [
            {"label": "current", "role": "current_period", "preferred_task_id": "task_current"},
            {"label": "prior", "role": "prior_period", "preferred_task_id": "task_prior"},
        ]
        dependency_binding_keys = {
            dependency_binding_identity(binding)
            for binding in dependency_bindings
        }
        dependency_resolved_keys = {
            dependency_binding_identity(dependency_bindings[0])
        }
        missing_dependency_bindings = [dict(dependency_bindings[1])]
        precedence_input = self._main_precedence_input(
            [],
            direct_rows,
            dependency_rows,
            dependency_bindings,
            dependency_binding_keys,
            dependency_resolved_keys,
            missing_dependency_bindings,
            operation_family="growth_rate",
        )
        input_snapshot = deepcopy(precedence_input)

        result = resolve_main_operand_precedence(precedence_input)

        self.assertEqual(result.source_selection.precedence, "dependency_first")
        self.assertEqual(
            [row.get("evidence_id") for row in result.source_selection.operand_rows],
            ["dependency_current", "direct_current", "direct_prior"],
        )
        self.assertEqual(
            [row.get("evidence_id") for row in result.selected_operand_rows],
            ["dependency_current", "direct_prior"],
        )
        rows_by_role = {
            row["matched_operand_role"]: row
            for row in result.selected_operand_rows
        }
        self.assertEqual(
            rows_by_role["current_period"]["source_row_ids"],
            ["task_output:task_current"],
        )
        self.assertTrue(rows_by_role["current_period"]["dependency_resolved"])
        self.assertEqual(rows_by_role["prior_period"]["evidence_id"], "direct_prior")
        self.assertFalse(rows_by_role["prior_period"]["dependency_resolved"])
        self.assertTrue(result.direct_dependency_fill_allowed)
        self.assertEqual(result.missing_dependency_bindings, [])
        self.assertIsNot(result.missing_dependency_bindings, missing_dependency_bindings)
        self.assertEqual(result.rejected_dependency_scope_rows, [])
        self.assertEqual(precedence_input, input_snapshot)

    def test_preferred_stage_mismatch_keeps_task_output_with_reason(self) -> None:
        current = self._task_output_row(
            binding_policy={"prefer_aggregation_stages": ["final", "subtotal"]},
            aggregation_stage="final",
        )
        candidate = self._direct_row(aggregation_stage="none", value_role="detail")

        decision = decide_task_output_operand_resolution(current, candidate)

        self.assertEqual(decision.action, "keep_current")
        self.assertEqual(decision.reason, "candidate_stage_not_preferred")
        self.assertEqual(
            decision.current_source_ids,
            ("shared_total", "task_output:task_total"),
        )
        self.assertEqual(
            decision.candidate_source_ids,
            ("direct_detail", "shared_total"),
        )
        self.assertTrue(decision.values_differ)
        self.assertTrue(decision.materially_conflicting)

    def test_shared_source_allows_candidate_at_preferred_stage(self) -> None:
        current = self._task_output_row(
            binding_policy={"prefer_aggregation_stages": ["final", "subtotal"]},
        )
        candidate = self._direct_row(aggregation_stage="subtotal")

        decision = decide_task_output_operand_resolution(current, candidate)

        self.assertEqual(decision.action, "use_candidate")
        self.assertEqual(decision.reason, "shared_source")

    def test_disjoint_task_output_provenance_keeps_current(self) -> None:
        current = self._task_output_row(source_row_ids=["task_output:task_total"])
        candidate = self._direct_row(source_row_ids=["direct_detail"])

        decision = decide_task_output_operand_resolution(current, candidate)

        self.assertTrue(decision.keep_current_value)
        self.assertEqual(decision.reason, "provenance_conflict")

    def test_task_output_id_without_explicit_source_task_does_not_expand_protection(self) -> None:
        current = self._task_output_row(
            source_task_id="",
            source_row_ids=["task_output:task_total"],
        )
        candidate = self._direct_row(source_row_ids=["direct_detail"])

        decision = decide_task_output_operand_resolution(current, candidate)

        self.assertEqual(decision.action, "use_candidate")
        self.assertEqual(decision.reason, "current_missing_source_task")

    def test_shared_source_with_conflicting_anchor_keeps_current(self) -> None:
        current = self._task_output_row(source_anchor="task_anchor")
        candidate = self._direct_row(source_anchor="direct_anchor")

        decision = decide_task_output_operand_resolution(current, candidate)

        self.assertEqual(decision.action, "keep_current")
        self.assertEqual(decision.reason, "provenance_conflict")
        self.assertTrue(decision.anchor_conflict)

    def test_scope_conflict_keeps_dependency_value_without_task_output_id(self) -> None:
        current = self._task_output_row(
            evidence_id="dependency_value",
            source_row_ids=["dependency_value", "shared_total"],
            consolidation_scope="연결",
        )
        candidate = self._direct_row(
            source_row_ids=["direct_detail", "shared_total"],
            consolidation_scope="별도",
        )

        decision = decide_task_output_operand_resolution(current, candidate)

        self.assertEqual(decision.action, "keep_current")
        self.assertEqual(decision.reason, "provenance_conflict")
        self.assertTrue(decision.scope_conflict)

    def test_immaterial_difference_uses_candidate(self) -> None:
        current = self._task_output_row(normalized_value=1_000.0)
        candidate = self._direct_row(normalized_value=1_000.4)

        decision = decide_task_output_operand_resolution(current, candidate)

        self.assertEqual(decision.action, "use_candidate")
        self.assertEqual(decision.reason, "within_material_tolerance")
        self.assertTrue(decision.values_differ)
        self.assertFalse(decision.materially_conflicting)

    def test_weak_unit_repair_candidate_precedes_provenance_guard(self) -> None:
        current = self._task_output_row(
            source_row_ids=["task_output:task_total"],
            unit_normalization_repair_source="alternate_table_krw_surface",
            source_raw_unit="",
        )
        candidate = self._direct_row(source_row_ids=["direct_detail"])

        decision = decide_task_output_operand_resolution(current, candidate)

        self.assertEqual(decision.action, "use_candidate")
        self.assertEqual(decision.reason, "unit_repair_candidate")

    def test_complete_period_context_overrides_large_scale_distortion(self) -> None:
        current = self._task_output_row(
            source_row_ids=["task_output:task_total"],
            normalized_value=1_000.0,
        )
        candidate = self._direct_row(
            source_row_ids=["direct_period_row"],
            normalized_value=100_000.0,
        )

        default_decision = decide_task_output_operand_resolution(current, candidate)
        period_decision = decide_task_output_operand_resolution(
            current,
            candidate,
            context="complete_period",
        )

        self.assertEqual(default_decision.action, "keep_current")
        self.assertEqual(default_decision.reason, "provenance_conflict")
        self.assertEqual(period_decision.action, "use_candidate")
        self.assertEqual(period_decision.reason, "complete_period_context_override")

    def test_coherent_ratio_same_table_context_overrides_task_output(self) -> None:
        current = self._task_output_row(
            source_row_ids=["task_output:task_total"],
            table_source_id="table_1",
        )
        candidate = self._direct_row(
            source_row_ids=["direct_component"],
            table_source_id="table_1",
        )

        decision = decide_task_output_operand_resolution(
            current,
            candidate,
            context="coherent_ratio",
        )

        self.assertEqual(decision.action, "use_candidate")
        self.assertEqual(decision.reason, "coherent_ratio_same_table_override")

    def test_coherent_ratio_scale_context_overrides_matching_raw_surface(self) -> None:
        current = self._task_output_row(
            source_row_ids=["task_output:task_total"],
            table_source_id="task_table",
            raw_value="1,500",
            raw_unit="천원",
            normalized_value=1_500_000.0,
        )
        candidate = self._direct_row(
            source_row_ids=["direct_component"],
            table_source_id="direct_table",
            raw_value="1,500",
            raw_unit="원",
            normalized_value=1_500.0,
        )

        decision = decide_task_output_operand_resolution(
            current,
            candidate,
            context="coherent_ratio",
        )

        self.assertEqual(decision.action, "use_candidate")
        self.assertEqual(decision.reason, "coherent_ratio_scale_override")

    def test_incoherent_ratio_context_preserves_disjoint_provenance(self) -> None:
        current = self._task_output_row(source_row_ids=["task_output:task_total"])
        candidate = self._direct_row(source_row_ids=["direct_detail"])

        decision = decide_task_output_operand_resolution(current, candidate, context="default")

        self.assertEqual(decision.action, "keep_current")
        self.assertEqual(decision.reason, "provenance_conflict")

    def test_period_comparison_allows_direct_rows_over_weak_unit_repaired_task_output(self) -> None:
        dependency_rows = [
            {
                "matched_operand_role": "current_period",
                "label": "selected metric",
                "raw_value": "3,146,409",
                "raw_unit": "백만원",
                "normalized_value": 3_146_409_000_000.0,
                "normalized_unit": "KRW",
                "source_row_id": "task_output:current",
                "source_row_ids": ["task_output:current", "current_cell"],
                "source_task_id": "current",
                "dependency_resolved": True,
            },
            {
                "matched_operand_role": "prior_period",
                "label": "selected metric",
                "raw_value": "54",
                "raw_unit": "백만원",
                "normalized_value": 54_000_000.0,
                "normalized_unit": "KRW",
                "source_row_id": "task_output:prior",
                "source_row_ids": ["task_output:prior", "weak_cell"],
                "source_task_id": "prior",
                "dependency_resolved": True,
                "source_raw_unit": "",
                "source_normalized_value": 54.0,
                "unit_normalization_repair_source": "alternate_table_krw_surface",
            },
        ]
        direct_rows = [
            {
                "matched_operand_role": "current_period",
                "label": "selected metric",
                "raw_value": "3,146,409",
                "raw_unit": "백만원",
                "normalized_value": 3_146_409_000_000.0,
                "normalized_unit": "KRW",
                "source_row_id": "table_current",
                "table_source_id": "period_table",
            },
            {
                "matched_operand_role": "prior_period",
                "label": "selected metric",
                "raw_value": "1,847,775",
                "raw_unit": "백만원",
                "normalized_value": 1_847_775_000_000.0,
                "normalized_unit": "KRW",
                "source_row_id": "table_prior",
                "table_source_id": "period_table",
            },
        ]

        conflicts = period_comparison_direct_rows_conflict_with_dependency_outputs(
            dependency_rows,
            direct_rows,
        )

        self.assertFalse(conflicts)

    def test_dependency_alignment_preserves_task_output_when_direct_value_has_distinct_provenance(self) -> None:
        dependency_rows = [
            {
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "100",
                "raw_unit": "unit",
                "normalized_value": 100.0,
                "normalized_unit": "COUNT",
                "source_task_id": "task_lookup",
                "source_row_id": "task_output:task_lookup",
                "source_row_ids": ["task_output:task_lookup", "ev_lookup"],
                "dependency_resolved": True,
            }
        ]
        direct_rows = [
            {
                "evidence_id": "ev_direct_num",
                "source_row_id": "ev_direct_num",
                "source_row_ids": ["ev_direct_num"],
                "table_source_id": "table_a",
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "80",
                "raw_unit": "unit",
                "normalized_value": 80.0,
                "normalized_unit": "COUNT",
            },
            {
                "evidence_id": "ev_direct_den",
                "source_row_id": "ev_direct_den",
                "source_row_ids": ["ev_direct_den"],
                "table_source_id": "table_a",
                "label": "base value",
                "matched_operand_label": "base value",
                "matched_operand_role": "denominator_1",
                "raw_value": "40",
                "raw_unit": "unit",
                "normalized_value": 40.0,
                "normalized_unit": "COUNT",
            },
        ]

        rows = align_dependency_rows_with_sibling_direct_context(dependency_rows, direct_rows)

        self.assertEqual(rows[0]["raw_value"], "100")
        self.assertEqual(rows[0]["normalized_value"], 100.0)
        self.assertEqual(rows[0]["source_row_ids"], ["task_output:task_lookup", "ev_lookup"])
        self.assertTrue(rows[0]["sibling_table_context_realignment_blocked"])
        self.assertNotIn("sibling_table_context_realigned", rows[0])

    def test_dependency_alignment_preserves_task_output_only_row_when_direct_value_conflicts(self) -> None:
        dependency_rows = [
            {
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "120",
                "raw_unit": "unit",
                "normalized_value": 120.0,
                "normalized_unit": "COUNT",
                "source_task_id": "task_lookup",
                "source_row_id": "task_output:task_lookup",
                "source_row_ids": ["task_output:task_lookup"],
                "dependency_resolved": True,
            }
        ]
        direct_rows = [
            {
                "evidence_id": "ev_direct_num",
                "source_row_id": "ev_direct_num",
                "source_row_ids": ["ev_direct_num"],
                "table_source_id": "table_a",
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "70",
                "raw_unit": "unit",
                "normalized_value": 70.0,
                "normalized_unit": "COUNT",
            },
            {
                "evidence_id": "ev_direct_den",
                "source_row_id": "ev_direct_den",
                "source_row_ids": ["ev_direct_den"],
                "table_source_id": "table_a",
                "label": "base value",
                "matched_operand_label": "base value",
                "matched_operand_role": "denominator_1",
                "raw_value": "30",
                "raw_unit": "unit",
                "normalized_value": 30.0,
                "normalized_unit": "COUNT",
            },
        ]

        rows = align_dependency_rows_with_sibling_direct_context(dependency_rows, direct_rows)

        self.assertEqual(rows[0]["raw_value"], "120")
        self.assertEqual(rows[0]["normalized_value"], 120.0)
        self.assertEqual(rows[0]["source_row_ids"], ["task_output:task_lookup"])
        self.assertTrue(rows[0]["sibling_table_context_realignment_blocked"])
        self.assertNotIn("sibling_table_context_realigned", rows[0])

    def test_dependency_alignment_preserves_source_task_row_when_shared_id_has_conflicting_anchor(self) -> None:
        dependency_rows = [
            {
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "120",
                "raw_unit": "unit",
                "normalized_value": 120.0,
                "normalized_unit": "COUNT",
                "source_task_id": "task_lookup",
                "source_row_id": "ev_shared",
                "source_row_ids": ["ev_shared"],
                "source_anchor": "source task table",
                "dependency_resolved": True,
            }
        ]
        direct_rows = [
            {
                "evidence_id": "ev_shared",
                "source_row_id": "ev_shared",
                "source_row_ids": ["ev_shared"],
                "source_anchor": "direct sibling table",
                "table_source_id": "table_a",
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "70",
                "raw_unit": "unit",
                "normalized_value": 70.0,
                "normalized_unit": "COUNT",
            },
            {
                "evidence_id": "ev_direct_den",
                "source_row_id": "ev_direct_den",
                "source_row_ids": ["ev_direct_den"],
                "source_anchor": "direct sibling table",
                "table_source_id": "table_a",
                "label": "base value",
                "matched_operand_label": "base value",
                "matched_operand_role": "denominator_1",
                "raw_value": "30",
                "raw_unit": "unit",
                "normalized_value": 30.0,
                "normalized_unit": "COUNT",
            },
        ]

        rows = align_dependency_rows_with_sibling_direct_context(dependency_rows, direct_rows)

        self.assertEqual(rows[0]["raw_value"], "120")
        self.assertEqual(rows[0]["normalized_value"], 120.0)
        self.assertEqual(rows[0]["source_anchor"], "source task table")
        self.assertTrue(rows[0]["sibling_table_context_realignment_blocked"])
        self.assertNotIn("sibling_table_context_realigned", rows[0])

    def test_dependency_alignment_realigns_task_output_to_same_table_component_row(self) -> None:
        dependency_rows = [
            {
                "label": "short-term borrowings",
                "matched_operand_label": "short-term borrowings",
                "matched_operand_role": "numerator_1",
                "raw_value": "9,857,189",
                "raw_unit": "백만원",
                "normalized_value": 9857189000000.0,
                "normalized_unit": "KRW",
                "source_task_id": "task_short",
                "source_row_id": "task_output:task_short",
                "source_row_ids": ["task_output:task_short", "ev_subtotal", "chunk_table"],
                "table_source_id": "table_borrowings",
                "dependency_resolved": True,
            }
        ]
        direct_rows = [
            {
                "evidence_id": "row_short",
                "source_row_id": "row_short",
                "source_row_ids": ["row_short", "chunk_table"],
                "table_source_id": "table_borrowings",
                "label": "short-term borrowings",
                "matched_operand_label": "short-term borrowings",
                "matched_operand_role": "numerator_1",
                "raw_value": "4,145,647",
                "raw_unit": "백만원",
                "normalized_value": 4145647000000.0,
                "normalized_unit": "KRW",
            },
            {
                "evidence_id": "row_long",
                "source_row_id": "row_long",
                "source_row_ids": ["row_long", "chunk_table"],
                "table_source_id": "table_borrowings",
                "label": "long-term borrowings",
                "matched_operand_label": "long-term borrowings",
                "matched_operand_role": "numerator_2",
                "raw_value": "10,121,033",
                "raw_unit": "백만원",
                "normalized_value": 10121033000000.0,
                "normalized_unit": "KRW",
            },
            {
                "evidence_id": "row_bond",
                "source_row_id": "row_bond",
                "source_row_ids": ["row_bond", "chunk_table"],
                "table_source_id": "table_borrowings",
                "label": "bonds",
                "matched_operand_label": "bonds",
                "matched_operand_role": "numerator_3",
                "raw_value": "9,490,410",
                "raw_unit": "백만원",
                "normalized_value": 9490410000000.0,
                "normalized_unit": "KRW",
            },
        ]

        rows = align_dependency_rows_with_sibling_direct_context(dependency_rows, direct_rows)

        self.assertEqual(rows[0]["raw_value"], "4,145,647")
        self.assertEqual(rows[0]["source_row_id"], "row_short")
        self.assertTrue(rows[0]["sibling_table_context_realigned"])

    def test_dependency_alignment_is_invariant_to_complete_context_candidate_order(self) -> None:
        dependency_rows = [
            {
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "100",
                "raw_unit": "unit",
                "normalized_value": 100.0,
                "normalized_unit": "KRW",
                "source_task_id": "task_target",
                "source_row_id": "task_output:task_target",
                "source_row_ids": ["task_output:task_target", "shared_chunk"],
                "table_source_id": "table_good",
                "dependency_resolved": True,
            }
        ]
        direct_rows = [
            {
                "evidence_id": "direct_good",
                "source_row_id": "direct_good",
                "source_row_ids": ["direct_good", "shared_chunk"],
                "table_source_id": "table_good",
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "80",
                "raw_unit": "unit",
                "normalized_value": 80.0,
                "normalized_unit": "KRW",
            },
            {
                "evidence_id": "good_den",
                "source_row_id": "good_den",
                "source_row_ids": ["good_den"],
                "table_source_id": "table_good",
                "label": "base value",
                "matched_operand_label": "base value",
                "matched_operand_role": "denominator_1",
                "raw_value": "40",
                "raw_unit": "unit",
                "normalized_value": 40.0,
                "normalized_unit": "KRW",
            },
            {
                "evidence_id": "direct_alt",
                "source_row_id": "direct_alt",
                "source_row_ids": ["direct_alt"],
                "table_source_id": "table_alt",
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "70",
                "raw_unit": "unit",
                "normalized_value": 70.0,
                "normalized_unit": "KRW",
            },
            {
                "evidence_id": "alt_den",
                "source_row_id": "alt_den",
                "source_row_ids": ["alt_den"],
                "table_source_id": "table_alt",
                "label": "base value",
                "matched_operand_label": "base value",
                "matched_operand_role": "denominator_1",
                "raw_value": "35",
                "raw_unit": "unit",
                "normalized_value": 35.0,
                "normalized_unit": "KRW",
            },
        ]

        forward = align_dependency_rows_with_sibling_direct_context(
            dependency_rows,
            direct_rows,
        )
        reversed_rows = align_dependency_rows_with_sibling_direct_context(
            dependency_rows,
            list(reversed(direct_rows)),
        )

        for rows in (forward, reversed_rows):
            self.assertEqual(rows[0]["raw_value"], "80")
            self.assertEqual(rows[0]["source_row_id"], "direct_good")
            self.assertTrue(rows[0]["sibling_table_context_realigned"])
            self.assertEqual(
                rows[0]["sibling_direct_candidate_selection_reason"],
                "shared_source_context",
            )

    def test_dependency_alignment_preserves_current_on_ambiguous_complete_contexts(self) -> None:
        dependency_rows = [
            self._task_output_row(
                label="target value",
                matched_operand_label="target value",
                matched_operand_role="numerator_1",
                raw_value="100",
                raw_unit="unit",
                normalized_value=100.0,
                normalized_unit="KRW",
                source_task_id="task_target",
                source_row_id="task_output:task_target",
                source_row_ids=["task_output:task_target"],
                table_source_id="",
            )
        ]
        direct_rows = [
            self._direct_row(
                evidence_id="direct_a",
                source_row_id="direct_a",
                source_row_ids=["direct_a"],
                table_source_id="table_a",
                label="target value",
                matched_operand_label="target value",
                matched_operand_role="numerator_1",
                raw_value="80",
                raw_unit="unit",
                normalized_value=80.0,
                normalized_unit="KRW",
            ),
            self._direct_row(
                evidence_id="den_a",
                source_row_id="den_a",
                source_row_ids=["den_a"],
                table_source_id="table_a",
                label="base value",
                matched_operand_label="base value",
                matched_operand_role="denominator_1",
                raw_value="40",
                raw_unit="unit",
                normalized_value=40.0,
                normalized_unit="KRW",
            ),
            self._direct_row(
                evidence_id="direct_b",
                source_row_id="direct_b",
                source_row_ids=["direct_b"],
                table_source_id="table_b",
                label="target value",
                matched_operand_label="target value",
                matched_operand_role="numerator_1",
                raw_value="70",
                raw_unit="unit",
                normalized_value=70.0,
                normalized_unit="KRW",
            ),
            self._direct_row(
                evidence_id="den_b",
                source_row_id="den_b",
                source_row_ids=["den_b"],
                table_source_id="table_b",
                label="base value",
                matched_operand_label="base value",
                matched_operand_role="denominator_1",
                raw_value="35",
                raw_unit="unit",
                normalized_value=35.0,
                normalized_unit="KRW",
            ),
        ]

        for ordered_rows in (direct_rows, list(reversed(direct_rows))):
            rows = align_dependency_rows_with_sibling_direct_context(
                dependency_rows,
                ordered_rows,
            )

            self.assertEqual(rows[0]["raw_value"], "100")
            self.assertEqual(rows[0]["source_row_id"], "task_output:task_target")
            self.assertTrue(rows[0]["sibling_table_context_realignment_blocked"])
            self.assertEqual(
                rows[0]["sibling_table_context_realignment_blocked_reason"],
                "ambiguous_direct_context_candidates",
            )

    def test_period_comparison_complete_direct_context_does_not_block_dependency(self) -> None:
        dependency_rows = [
            {
                "label": "prior metric",
                "matched_operand_label": "metric",
                "matched_operand_role": "prior_period",
                "raw_value": "54",
                "raw_unit": "백만원",
                "normalized_value": 54000000.0,
                "normalized_unit": "KRW",
                "source_task_id": "task_prior",
                "source_row_id": "task_output:task_prior",
                "source_row_ids": ["task_output:task_prior", "ev_note"],
                "dependency_resolved": True,
            }
        ]
        direct_rows = [
            {
                "label": "current metric",
                "matched_operand_label": "metric",
                "matched_operand_role": "current_period",
                "raw_value": "3,146,409",
                "raw_unit": "백만원",
                "normalized_value": 3146409000000.0,
                "normalized_unit": "KRW",
                "source_row_id": "row_current",
                "source_row_ids": ["row_current"],
                "table_source_id": "period_table",
            },
            {
                "label": "prior metric",
                "matched_operand_label": "metric",
                "matched_operand_role": "prior_period",
                "raw_value": "1,847,775",
                "raw_unit": "백만원",
                "normalized_value": 1847775000000.0,
                "normalized_unit": "KRW",
                "source_row_id": "row_prior",
                "source_row_ids": ["row_prior"],
                "table_source_id": "period_table",
            },
        ]

        self.assertFalse(
            period_comparison_direct_rows_conflict_with_dependency_outputs(
                dependency_rows,
                direct_rows,
            )
        )

    def test_dependency_alignment_still_realigns_unanchored_row_to_complete_direct_context(self) -> None:
        dependency_rows = [
            {
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "100",
                "raw_unit": "unit",
                "normalized_value": 100.0,
                "normalized_unit": "COUNT",
                "source_row_id": "ev_lookup",
                "source_row_ids": ["ev_lookup"],
            }
        ]
        direct_rows = [
            {
                "evidence_id": "ev_direct_num",
                "source_row_id": "ev_direct_num",
                "source_row_ids": ["ev_direct_num"],
                "table_source_id": "table_a",
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "80",
                "raw_unit": "unit",
                "normalized_value": 80.0,
                "normalized_unit": "COUNT",
            },
            {
                "evidence_id": "ev_direct_den",
                "source_row_id": "ev_direct_den",
                "source_row_ids": ["ev_direct_den"],
                "table_source_id": "table_a",
                "label": "base value",
                "matched_operand_label": "base value",
                "matched_operand_role": "denominator_1",
                "raw_value": "40",
                "raw_unit": "unit",
                "normalized_value": 40.0,
                "normalized_unit": "COUNT",
            },
        ]

        rows = align_dependency_rows_with_sibling_direct_context(dependency_rows, direct_rows)

        self.assertEqual(rows[0]["raw_value"], "80")
        self.assertEqual(rows[0]["normalized_value"], 80.0)
        self.assertEqual(rows[0]["source_row_ids"], ["ev_direct_num"])
        self.assertTrue(rows[0]["sibling_table_context_realigned"])

    def test_dependency_alignment_noop_preserves_input_identity(self) -> None:
        dependency_rows = [{"matched_operand_role": "numerator_1", "raw_value": "100"}]

        aligned = align_dependency_rows_with_sibling_direct_context(dependency_rows, [])

        self.assertIs(aligned, dependency_rows)

    def test_complete_ratio_preference_uses_coherent_direct_rows(self) -> None:
        required_operands = [
            {"label": "target value", "role": "numerator_1", "required": True},
            {"label": "base value", "role": "denominator_1", "required": True},
        ]
        operand_rows = [
            {
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "100",
                "normalized_value": 100.0,
                "normalized_unit": "COUNT",
            }
        ]
        direct_rows = [
            {
                "evidence_id": "direct_target",
                "table_source_id": "ratio_table",
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "80",
                "normalized_value": 80.0,
                "normalized_unit": "COUNT",
            },
            {
                "evidence_id": "direct_base",
                "table_source_id": "ratio_table",
                "label": "base value",
                "matched_operand_label": "base value",
                "matched_operand_role": "denominator_1",
                "raw_value": "40",
                "normalized_value": 40.0,
                "normalized_unit": "COUNT",
            },
        ]

        preferred = prefer_complete_ratio_direct_context_rows(
            operand_rows=operand_rows,
            direct_rows=direct_rows,
            required_operands=required_operands,
        )

        rows_by_role = {row["matched_operand_role"]: row for row in preferred}
        self.assertEqual(rows_by_role["numerator_1"]["raw_value"], "80")
        self.assertEqual(rows_by_role["denominator_1"]["raw_value"], "40")

    def test_complete_ratio_preference_blocks_incoherent_provenance(self) -> None:
        required_operands = [
            {"label": "target value", "role": "numerator_1", "required": True},
            {"label": "base value", "role": "denominator_1", "required": True},
        ]
        operand_rows = [
            {
                "dependency_resolved": True,
                "source_task_id": "task_target",
                "source_row_id": "task_output:task_target",
                "source_row_ids": ["task_output:task_target"],
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "100",
                "normalized_value": 100.0,
                "normalized_unit": "COUNT",
            }
        ]
        direct_rows = [
            {
                "evidence_id": "direct_target",
                "source_row_id": "direct_target",
                "table_source_id": "target_table",
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "raw_value": "80",
                "normalized_value": 80.0,
                "normalized_unit": "COUNT",
            },
            {
                "evidence_id": "direct_base",
                "source_row_id": "direct_base",
                "table_source_id": "base_table",
                "label": "base value",
                "matched_operand_label": "base value",
                "matched_operand_role": "denominator_1",
                "raw_value": "40",
                "normalized_value": 40.0,
                "normalized_unit": "COUNT",
            },
        ]

        preferred = prefer_complete_ratio_direct_context_rows(
            operand_rows=operand_rows,
            direct_rows=direct_rows,
            required_operands=required_operands,
        )

        target_row = next(row for row in preferred if row["matched_operand_role"] == "numerator_1")
        self.assertEqual(target_row["raw_value"], "100")
        self.assertTrue(target_row["complete_ratio_direct_context_preference_blocked"])
        self.assertEqual(
            target_row["complete_ratio_direct_context_preference_blocked_reason"],
            "task_output_value_provenance_mismatch",
        )

    def test_complete_ratio_preference_incomplete_context_preserves_input_identity(self) -> None:
        required_operands = [
            {"label": "target value", "role": "numerator_1", "required": True},
            {"label": "base value", "role": "denominator_1", "required": True},
        ]
        operand_rows = [{"label": "target value", "matched_operand_role": "numerator_1"}]
        incomplete_direct_rows = [
            {
                "label": "target value",
                "matched_operand_label": "target value",
                "matched_operand_role": "numerator_1",
                "table_source_id": "ratio_table",
            }
        ]

        preferred = prefer_complete_ratio_direct_context_rows(
            operand_rows=operand_rows,
            direct_rows=incomplete_direct_rows,
            required_operands=required_operands,
        )

        self.assertIs(preferred, operand_rows)


if __name__ == "__main__":
    unittest.main()
