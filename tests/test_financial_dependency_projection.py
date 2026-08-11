import math
import unittest
from copy import deepcopy
from typing import Any, Dict, List, Mapping
from unittest.mock import patch

import src.agent.financial_dependency_projection as dependency_projection
import src.agent.financial_operand_resolution as operand_resolution
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
    def test_structured_unit_realigned_source_slot_match_matrix(self) -> None:
        matches = dependency_projection.structured_unit_realigned_operand_matches_source_slot

        def source(**updates: Any) -> Dict[str, Any]:
            row = {
                "raw_value": "100",
                "normalized_unit": "KRW",
                "source_row_id": "source",
                "source_row_ids": ["source"],
            }
            row.update(updates)
            return row

        def operand(*, marked: bool = True, **updates: Any) -> Dict[str, Any]:
            row = {
                "unit_realigned_from_structured_provenance": marked,
                "role": "denominator_1",
                "raw_value": "100",
                "normalized_unit": "KRW",
                "source_row_id": "task_output:task_den",
                "source_row_ids": ["task_output:task_den", "source"],
                "nested": {"keep": True},
            }
            row.update(updates)
            return row

        for name, source_updates, operand_updates, expected in (
            ("exact", {}, {}, True),
            ("source raw blank", {"raw_value": ""}, {}, False),
            ("source raw mismatch", {"raw_value": "101"}, {}, False),
            ("candidate raw blank", {}, {"raw_value": ""}, False),
            ("candidate raw mismatch", {}, {"raw_value": "101"}, False),
            ("source unit blank", {"normalized_unit": ""}, {}, False),
            ("source unit mismatch", {"normalized_unit": "COUNT"}, {}, False),
            ("candidate unit blank", {}, {"normalized_unit": ""}, False),
            ("candidate unit mismatch", {}, {"normalized_unit": "COUNT"}, False),
            ("source ids blank", {"source_row_id": "", "source_row_ids": []}, {}, False),
            ("candidate ids blank", {}, {"source_row_id": "", "source_row_ids": []}, False),
            ("disjoint ids", {}, {"source_row_ids": ["other"]}, False),
            ("source task output only", {"source_row_id": "task_output:a", "source_row_ids": []}, {}, False),
            ("candidate task output only", {}, {"source_row_ids": ["task_output:b"]}, False),
            (
                "task output filtered with shared id",
                {"source_row_ids": ["task_output:a", " shared "]},
                {"source_row_ids": ["task_output:b", "shared"]},
                True,
            ),
            ("normalized unit", {"normalized_unit": " krw "}, {"normalized_unit": "krw"}, True),
        ):
            with self.subTest(marked=name):
                self.assertEqual(matches(source(**source_updates), operand(**operand_updates)), expected)

        class AccessMapping(Mapping[str, Any]):
            def __init__(self, values, events, name):
                self.values = values
                self.events = events
                self.name = name

            def __len__(self):
                return len(self.values)

            def __iter__(self):
                return iter(self.values)

            def __getitem__(self, key):
                return self.values[key]

            def keys(self):
                self.events.append(f"copy:{self.name}")
                return self.values.keys()

            def get(self, key, default=None):
                self.events.append(f"get:{self.name}:{key}")
                return self.values.get(key, default)

        class TruthBomb:
            def __bool__(self):
                raise RuntimeError("structured list accessed")

        marker_events: List[str] = []
        direct_operand = AccessMapping(operand(), marker_events, "operand")
        source_events: List[str] = []
        tracked_source = AccessMapping(source(), source_events, "source")
        self.assertTrue(
            matches(  # type: ignore[arg-type]
                tracked_source,
                direct_operand,
                structured_realigned_operands=TruthBomb(),
            )
        )
        self.assertEqual(marker_events, ["get:operand:unit_realigned_from_structured_provenance", "copy:operand"])
        self.assertEqual(
            source_events,
            [
                "get:source:source_row_id",
                "get:source:source_row_ids",
                "get:source:raw_value",
                "get:source:normalized_unit",
            ],
        )

        for name, unmarked, marked_rows, expected in (
            ("no marked", operand(marked=False), [], False),
            (
                "matched-role fallback",
                operand(marked=False, role="", matched_operand_role="denominator_1"),
                [operand(role="", matched_operand_role="denominator_1")],
                True,
            ),
            (
                "role mismatch",
                operand(marked=False, role="numerator_1"),
                [operand(role="denominator_1")],
                False,
            ),
            ("raw mismatch", operand(marked=False, raw_value="99"), [operand(raw_value="100")], False),
            (
                "selection ids disjoint",
                operand(marked=False, source_row_id="", source_row_ids=["operand"]),
                [operand(source_row_id="", source_row_ids=["marked"])],
                False,
            ),
            (
                "blank operand fields are wildcards",
                operand(marked=False, role="", matched_operand_role="", raw_value="", source_row_id="", source_row_ids=[]),
                [operand()],
                True,
            ),
            (
                "blank marked role is wildcard",
                operand(marked=False),
                [operand(role="", matched_operand_role="")],
                True,
            ),
            (
                "blank marked ids survive selection but fail intersection",
                operand(marked=False, source_row_id="", source_row_ids=[]),
                [operand(source_row_id="", source_row_ids=[])],
                False,
            ),
        ):
            with self.subTest(fallback=name):
                self.assertEqual(
                    matches(source(), unmarked, structured_realigned_operands=marked_rows),
                    expected,
                )

        class SourceBomb:
            def get(self, _key, _default=None):
                raise RuntimeError("source accessed without candidates")

        self.assertFalse(
            matches(
                SourceBomb(),  # type: ignore[arg-type]
                operand(marked=False),
                structured_realigned_operands=[],
            )
        )

        scan_events: List[str] = []

        class CountingString:
            def __init__(self, name, value):
                self.name = name
                self.value = value
                self.calls = 0

            def __str__(self):
                self.calls += 1
                scan_events.append(self.name)
                return self.value

        surviving_first_raw = CountingString("first.raw", "100")
        surviving_second_raw = CountingString("second.raw", "100")
        marked_rows = [
            AccessMapping(operand(role="other"), scan_events, "role-mismatch"),
            AccessMapping(operand(raw_value="other"), scan_events, "raw-mismatch"),
            AccessMapping(
                operand(source_row_id="", source_row_ids=["disjoint"]),
                scan_events,
                "id-mismatch",
            ),
            AccessMapping(operand(raw_value=surviving_first_raw), scan_events, "first"),
            AccessMapping(operand(raw_value=surviving_second_raw), scan_events, "second"),
        ]
        self.assertTrue(
            matches(
                source(),
                operand(marked=False),
                structured_realigned_operands=marked_rows,  # type: ignore[arg-type]
            )
        )
        self.assertEqual(
            [event for event in scan_events if event.startswith("copy:")],
            ["copy:first", "copy:second"],
        )
        self.assertNotIn("get:role-mismatch:source_row_id", scan_events)
        self.assertNotIn("get:raw-mismatch:source_row_id", scan_events)
        self.assertEqual((surviving_first_raw.calls, surviving_second_raw.calls), (2, 1))

        source_row = source()
        operand_row = operand(marked=False)
        marked_rows = [operand()]
        before = deepcopy((source_row, operand_row, marked_rows))
        self.assertTrue(matches(source_row, operand_row, structured_realigned_operands=marked_rows))
        self.assertEqual((source_row, operand_row, marked_rows), before)

    def test_structured_unit_realigned_source_slot_match_exception_contract(self) -> None:
        matches = dependency_projection.structured_unit_realigned_operand_matches_source_slot
        source = {"raw_value": "100", "normalized_unit": "KRW", "source_row_id": "source"}
        marked = {
            "unit_realigned_from_structured_provenance": True,
            "raw_value": "100",
            "normalized_unit": "KRW",
            "source_row_id": "source",
        }

        class GetBomb:
            def get(self, _key, _default=None):
                raise RuntimeError("mapping get failed")

        with self.assertRaisesRegex(RuntimeError, "mapping get failed"):
            matches(source, GetBomb())  # type: ignore[arg-type]

        class CopyBomb(Mapping[str, Any]):
            def __len__(self):
                return 1

            def __iter__(self):
                return iter(("unit_realigned_from_structured_provenance",))

            def __getitem__(self, _key):
                raise RuntimeError("dict copy failed")

            def get(self, key, default=None):
                return True if key == "unit_realigned_from_structured_provenance" else default

        with self.assertRaisesRegex(RuntimeError, "dict copy failed"):
            matches(source, CopyBomb())  # type: ignore[arg-type]

        class TruthBomb:
            def __bool__(self):
                raise RuntimeError("truthiness failed")

        class IterBomb:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("iteration failed")

        unmarked = {**marked, "unit_realigned_from_structured_provenance": False}
        with self.assertRaisesRegex(RuntimeError, "truthiness failed"):
            matches(source, unmarked, structured_realigned_operands=TruthBomb())
        with self.assertRaisesRegex(RuntimeError, "iteration failed"):
            matches(source, unmarked, structured_realigned_operands=IterBomb())

        class StringBomb:
            def __str__(self):
                raise RuntimeError("string failed")

        with self.assertRaisesRegex(RuntimeError, "string failed"):
            matches(source, {**unmarked, "role": StringBomb()}, structured_realigned_operands=[])

        with patch.object(
            dependency_projection,
            "_normalise_spaces",
            side_effect=RuntimeError("normalizer failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalizer failed"):
                matches(source, marked)
        with patch.object(
            dependency_projection,
            "_clean_source_row_ids",
            side_effect=RuntimeError("cleaner failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "cleaner failed"):
                matches(source, marked)
        class UnhashableId:
            __hash__ = None

            def __bool__(self):
                return True

            def startswith(self, _prefix):
                return False

        with patch.object(
            dependency_projection,
            "_clean_source_row_ids",
            return_value=[UnhashableId()],
        ):
            with self.assertRaises(TypeError):
                matches(source, marked)

        class StartsWithBomb:
            def __bool__(self):
                return True

            def startswith(self, _prefix):
                raise RuntimeError("startswith failed")

        with patch.object(
            dependency_projection,
            "_clean_source_row_ids",
            return_value=[StartsWithBomb()],
        ):
            with self.assertRaisesRegex(RuntimeError, "startswith failed"):
                matches(source, marked)

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
            return operand_resolution.dependency_task_output_has_consistent_krw_unit(row)

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
            operand_resolution,
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
            operand_resolution,
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
                operand_resolution,
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
                operand_resolution,
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
                operand_resolution,
                "_normalise_operand_value",
                return_value=(1.0, "KRW"),
            ):
                self.assertFalse(consistent({**base, "normalized_value": _BadFloat(error_type)}))
        with patch.object(
            operand_resolution,
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
            operand_resolution,
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
                operand_resolution,
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
            operand_resolution,
            "_normalise_operand_value",
            side_effect=RuntimeError("normalizer failed"),
        ), self.assertRaisesRegex(RuntimeError, "normalizer failed"):
            consistent({**base, "normalized_value": 1.0})

    def test_dependency_task_output_krw_consistency_pins_prefix_unit_and_raw_fallback_order(self) -> None:
        consistent = operand_resolution.dependency_task_output_has_consistent_krw_unit
        events = []

        class TrackedRow(Mapping[str, Any]):
            def __init__(self, values, *, fail_key=""):
                self.values = values
                self.fail_key = fail_key

            def __len__(self):
                return len(self.values)

            def __iter__(self):
                return iter(self.values)

            def __getitem__(self, key):
                return self.values[key]

            def get(self, key, default=None):
                events.append(("get", key))
                if key == self.fail_key:
                    raise RuntimeError(f"failed to read {key}")
                return self.values.get(key, default)

        def normalize(value):
            events.append(("spaces", value))
            return value.strip()

        def normalize_operand(raw_value, raw_unit):
            events.append(("operand", raw_value, raw_unit))
            return 100.0, "KRW"

        values = {
            "dependency_resolved": True,
            "source_row_id": "task_output:dependency",
            "normalized_unit": " krw ",
            "raw_value": " 100 ",
            "raw_unit": "",
            "result_unit": " won ",
            "normalized_value": 100.0,
            "nested": {"preserve": True},
        }
        before = deepcopy(values)
        with patch.object(operand_resolution, "_normalise_spaces", side_effect=normalize), patch.object(
            operand_resolution,
            "_normalise_operand_value",
            side_effect=normalize_operand,
        ):
            self.assertTrue(consistent(TrackedRow(values)))
        self.assertEqual(values, before)
        self.assertEqual(
            events,
            [
                ("get", "dependency_resolved"),
                ("get", "source_row_id"),
                ("get", "normalized_unit"),
                ("spaces", " krw "),
                ("get", "raw_value"),
                ("spaces", " 100 "),
                ("get", "raw_unit"),
                ("get", "result_unit"),
                ("spaces", " won "),
                ("operand", "100", "won"),
                ("get", "normalized_value"),
            ],
        )

        for name, row_values, expected_events in (
            (
                "dependency gate",
                {"dependency_resolved": False},
                [("get", "dependency_resolved")],
            ),
            (
                "source prefix",
                {"dependency_resolved": True, "source_row_id": "local:dependency"},
                [("get", "dependency_resolved"), ("get", "source_row_id")],
            ),
            (
                "normalized unit",
                {
                    "dependency_resolved": True,
                    "source_row_id": "task_output:dependency",
                    "normalized_unit": "COUNT",
                },
                [
                    ("get", "dependency_resolved"),
                    ("get", "source_row_id"),
                    ("get", "normalized_unit"),
                    ("spaces", "COUNT"),
                ],
            ),
        ):
            with self.subTest(name=name), patch.object(
                operand_resolution,
                "_normalise_spaces",
                side_effect=normalize,
            ), patch.object(
                operand_resolution,
                "_normalise_operand_value",
                side_effect=AssertionError("operand normalization must remain lazy"),
            ):
                events.clear()
                self.assertFalse(consistent(TrackedRow(row_values)))
                self.assertEqual(events, expected_events)

        truthy_raw_unit = {**values, "raw_unit": "won", "result_unit": "unused"}
        with patch.object(operand_resolution, "_normalise_spaces", side_effect=normalize), patch.object(
            operand_resolution,
            "_normalise_operand_value",
            return_value=(100.0, "KRW"),
        ):
            events.clear()
            self.assertTrue(consistent(TrackedRow(truthy_raw_unit, fail_key="result_unit")))
            self.assertNotIn(("get", "result_unit"), events)

        blank_raw = {**values, "raw_value": "", "raw_unit": "won"}
        with patch.object(operand_resolution, "_normalise_spaces", side_effect=normalize):
            events.clear()
            with self.assertRaisesRegex(RuntimeError, "failed to read raw_unit"):
                consistent(TrackedRow(blank_raw, fail_key="raw_unit"))
        self.assertEqual(events[-3:], [("get", "raw_value"), ("spaces", ""), ("get", "raw_unit")])

        class BoolBomb:
            def __bool__(self):
                raise RuntimeError("dependency truthiness failed")

        with self.assertRaisesRegex(RuntimeError, "dependency truthiness failed"):
            consistent(TrackedRow({"dependency_resolved": BoolBomb()}))

        events.clear()
        with (
            patch.object(
                operand_resolution,
                "_normalise_spaces",
                side_effect=RuntimeError("space normalization failed"),
            ),
            patch.object(operand_resolution, "_normalise_operand_value") as later_normalizer,
            self.assertRaisesRegex(RuntimeError, "space normalization failed"),
        ):
            consistent(TrackedRow(values))
        self.assertEqual(
            events,
            [("get", "dependency_resolved"), ("get", "source_row_id"), ("get", "normalized_unit")],
        )
        later_normalizer.assert_not_called()

    def test_dependency_task_output_krw_consistency_pins_numeric_tolerance_and_exception_order(self) -> None:
        import builtins

        consistent = operand_resolution.dependency_task_output_has_consistent_krw_unit
        base = {
            "dependency_resolved": True,
            "source_row_id": "task_output:dependency",
            "normalized_unit": "KRW",
            "raw_value": "1",
            "raw_unit": "won",
        }

        class ComparisonBomb:
            def __ne__(self, other):
                raise RuntimeError("expected unit comparison failed")

        with patch.object(
            operand_resolution,
            "_normalise_operand_value",
            return_value=(None, ComparisonBomb()),
        ):
            self.assertFalse(consistent({**base, "normalized_value": 1.0}))
        with patch.object(
            operand_resolution,
            "_normalise_operand_value",
            return_value=(1.0, ComparisonBomb()),
        ), self.assertRaisesRegex(RuntimeError, "expected unit comparison failed"):
            consistent({**base, "normalized_value": 1.0})

        events = []

        class NumericInput:
            def __init__(self, name, value, *, error=None):
                self.name = name
                self.value = value
                self.error = error

        def convert(value):
            events.append(("float", value.name))
            if value.error is not None:
                raise value.error(f"failed to convert {value.name}")
            return value.value

        def absolute(value):
            events.append(("abs", value))
            return builtins.abs(value)

        def maximum(*values):
            events.append(("max", values))
            return builtins.max(*values)

        with patch.object(
            operand_resolution,
            "_normalise_operand_value",
            return_value=(NumericInput("expected", 1_000_000_000.0), "KRW"),
        ), patch.object(operand_resolution, "float", side_effect=convert, create=True), patch.object(
            operand_resolution,
            "abs",
            side_effect=absolute,
            create=True,
        ), patch.object(operand_resolution, "max", side_effect=maximum, create=True):
            self.assertTrue(
                consistent({**base, "normalized_value": NumericInput("current", 1_000_000_001.0)})
            )
        self.assertEqual(
            events,
            [
                ("float", "current"),
                ("float", "expected"),
                ("abs", 1.0),
                ("abs", 1_000_000_000.0),
                ("max", (1e-06, 1.0)),
            ],
        )

        with patch.object(
            operand_resolution,
            "_normalise_operand_value",
            return_value=(0.0, "KRW"),
        ):
            self.assertFalse(consistent({**base, "normalized_value": 1.000001e-6}))

        for error_type, propagates in ((TypeError, False), (ValueError, False), (RuntimeError, True)):
            with self.subTest(error_type=error_type), patch.object(
                operand_resolution,
                "_normalise_operand_value",
                return_value=(NumericInput("expected", 1.0, error=error_type), "KRW"),
            ), patch.object(operand_resolution, "float", side_effect=convert, create=True):
                events.clear()
                row = {**base, "normalized_value": NumericInput("current", 1.0)}
                if propagates:
                    with self.assertRaisesRegex(RuntimeError, "failed to convert expected"):
                        consistent(row)
                else:
                    self.assertFalse(consistent(row))
                self.assertEqual(events, [("float", "current"), ("float", "expected")])

        def failing_absolute(value):
            events.append(("abs", value))
            raise RuntimeError("absolute tolerance failed")

        with patch.object(
            operand_resolution,
            "_normalise_operand_value",
            return_value=(NumericInput("expected", 1.0), "KRW"),
        ), patch.object(operand_resolution, "float", side_effect=convert, create=True), patch.object(
            operand_resolution,
            "abs",
            side_effect=failing_absolute,
            create=True,
        ), patch.object(
            operand_resolution,
            "max",
            side_effect=AssertionError("max must remain lazy"),
            create=True,
        ):
            events.clear()
            with self.assertRaisesRegex(RuntimeError, "absolute tolerance failed"):
                consistent({**base, "normalized_value": NumericInput("current", 1.0)})
        self.assertEqual(events, [("float", "current"), ("float", "expected"), ("abs", 0.0)])

    def test_dependency_task_output_krw_consistency_graph_binding_pins_exact_call_distribution_and_placement(self) -> None:
        import ast
        import inspect

        from src.agent import financial_graph_calculation as graph_calculation

        function_name = "dependency_task_output_has_consistent_krw_unit"
        tree = ast.parse(inspect.getsource(graph_calculation))
        owner_tree = ast.parse(inspect.getsource(operand_resolution))
        bindings = [
            alias
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_operand_resolution"
            for alias in node.names
            if alias.name == function_name
        ]
        self.assertEqual([(alias.name, alias.asname) for alias in bindings], [(function_name, None)])
        repair_bindings = [
            alias
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_operand_resolution"
            for alias in node.names
            if alias.name == "repair_krw_operand_units_from_table_metadata"
        ]
        self.assertEqual(
            [(alias.name, alias.asname) for alias in repair_bindings],
            [("repair_krw_operand_units_from_table_metadata", None)],
        )

        graph_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == function_name
        ]
        owner_calls = [
            node
            for node in ast.walk(owner_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == function_name
        ]
        self.assertEqual((len(graph_calls), len(owner_calls)), (1, 1))
        graph_methods = {
            node.name: node
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        owner_methods = {
            node.name: node
            for node in ast.walk(owner_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        expected = {
            "_coerce_operand_row_from_evidence": (graph_methods, graph_calls, "updated"),
            "repair_krw_operand_units_from_table_metadata": (owner_methods, owner_calls, "next_row"),
        }
        distributed = {}
        for method_name, (methods, calls, argument_name) in expected.items():
            method = methods[method_name]
            method_calls = [call for call in calls if call in ast.walk(method)]
            self.assertEqual(len(method_calls), 1, method_name)
            call = method_calls[0]
            self.assertEqual(
                ([ast.dump(argument) for argument in call.args], call.keywords),
                ([ast.dump(ast.Name(id=argument_name, ctx=ast.Load()))], []),
            )
            distributed[method_name] = call
        self.assertEqual(set(distributed.values()), set([*graph_calls, *owner_calls]))

        coerce = graph_methods["_coerce_operand_row_from_evidence"]
        self.assertEqual(
            [ast.dump(statement) for statement in coerce.body[:2]],
            [
                ast.dump(
                    ast.Assign(
                        targets=[ast.Name(id="updated", ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Name(id="dict", ctx=ast.Load()),
                            args=[ast.Name(id="row", ctx=ast.Load())],
                            keywords=[],
                        ),
                    )
                ),
                ast.dump(
                    ast.Assign(
                        targets=[ast.Name(id="preserve_dependency_unit", ctx=ast.Store())],
                        value=distributed["_coerce_operand_row_from_evidence"],
                    )
                ),
            ],
        )

        table_repair = owner_methods["repair_krw_operand_units_from_table_metadata"]
        operand_loop = next(
            node
            for node in ast.walk(table_repair)
            if isinstance(node, ast.For)
            and isinstance(node.target, ast.Name)
            and node.target.id == "row"
            and isinstance(node.iter, ast.Name)
            and node.iter.id == "operands"
        )
        self.assertEqual(ast.dump(operand_loop.body[0]), ast.dump(
            ast.Assign(
                targets=[ast.Name(id="next_row", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="dict", ctx=ast.Load()),
                    args=[ast.Name(id="row", ctx=ast.Load())],
                    keywords=[],
                ),
            )
        ))
        self.assertIsInstance(operand_loop.body[1], ast.If)
        self.assertEqual(ast.dump(operand_loop.body[1].test), ast.dump(distributed[
            "repair_krw_operand_units_from_table_metadata"
        ]))

    def test_dependency_task_output_krw_consistency_graph_callers_pin_gate_adoption_and_exception_stop(self) -> None:
        from src.agent import financial_graph_calculation as graph_calculation
        from src.agent.financial_graph import FinancialAgent

        agent = FinancialAgent.__new__(FinancialAgent)
        shared = {"preserve": True}
        base = {
            "dependency_resolved": True,
            "source_row_id": "task_output:dependency",
            "source_row_ids": ["task_output:dependency", "ev_table"],
            "evidence_id": "ev_table",
            "raw_value": "100",
            "raw_unit": "백만원",
            "normalized_value": 100_000_000.0,
            "normalized_unit": "KRW",
            "nested": shared,
        }
        original = deepcopy(base)
        with (
            patch.object(
                graph_calculation,
                "dependency_task_output_has_consistent_krw_unit",
                side_effect=[True, False],
            ) as gate,
            patch.object(
                graph_calculation,
                "coerce_operand_unit_from_evidence",
                return_value="원",
            ) as unit_coercion,
            patch.object(
                graph_calculation,
                "_normalise_operand_value",
                return_value=(100.0, "KRW"),
            ) as normalizer,
            patch.object(
                graph_calculation,
                "coerce_lookup_magnitude_record",
                side_effect=lambda row, _evidence: row,
            ),
        ):
            preserved = agent._coerce_operand_row_from_evidence(base, None)
            adopted = agent._coerce_operand_row_from_evidence(base, None)
        self.assertEqual(base, original)
        self.assertIsNot(preserved, base)
        self.assertIsNot(adopted, base)
        self.assertIs(preserved["nested"], shared)
        self.assertIs(adopted["nested"], shared)
        self.assertEqual(
            (preserved["raw_unit"], preserved["normalized_value"], adopted["raw_unit"], adopted["normalized_value"]),
            ("백만원", 100_000_000.0, "원", 100.0),
        )
        self.assertEqual(gate.call_count, 2)
        self.assertTrue(all(call.args[0] is not base for call in gate.call_args_list))
        self.assertTrue(all(call.args[0]["nested"] is shared for call in gate.call_args_list))
        unit_coercion.assert_called_once_with(raw_value="100", raw_unit="백만원", evidence_item=None)
        normalizer.assert_called_once_with("100", "원")

        rows = [{**base, "operand_id": "preserved"}, {**base, "operand_id": "adopted"}]
        rows_before = deepcopy(rows)
        evidence_items = [{
            "evidence_id": "ev_table",
            "raw_row_text": "target 100 원",
            "metadata": {"block_type": "table", "unit_hint": "원"},
        }]
        with (
            patch.object(
                operand_resolution,
                "dependency_task_output_has_consistent_krw_unit",
                side_effect=[True, False],
            ) as table_gate,
            patch.object(
                operand_resolution,
                "_normalise_operand_value",
                return_value=(100.0, "KRW"),
            ) as table_normalizer,
        ):
            repaired = operand_resolution.repair_krw_operand_units_from_table_metadata(rows, evidence_items)
        self.assertEqual(rows, rows_before)
        self.assertIsNot(repaired, rows)
        self.assertIsNot(repaired[0], rows[0])
        self.assertIsNot(repaired[1], rows[1])
        self.assertIs(repaired[0]["nested"], shared)
        self.assertIs(repaired[1]["nested"], shared)
        self.assertEqual(repaired[0]["raw_unit"], "백만원")
        self.assertEqual(
            (
                repaired[1]["raw_unit"],
                repaired[1]["normalized_value"],
                repaired[1]["unit_normalization_repair_source"],
            ),
            ("원", 100.0, "table_metadata_unit_hint"),
        )
        self.assertTrue(all(call.args[0] is not rows[index] for index, call in enumerate(table_gate.call_args_list)))
        table_normalizer.assert_called_once_with("100", "원")

        with (
            patch.object(
                graph_calculation,
                "dependency_task_output_has_consistent_krw_unit",
                side_effect=RuntimeError("dependency unit gate failed"),
            ),
            patch.object(graph_calculation, "coerce_operand_unit_from_evidence") as stopped_coercion,
            patch.object(graph_calculation, "_normalise_operand_value") as stopped_coerce_normalizer,
            patch.object(graph_calculation, "coerce_lookup_magnitude_record") as stopped_lookup,
            self.assertRaisesRegex(RuntimeError, "dependency unit gate failed"),
        ):
            agent._coerce_operand_row_from_evidence(base, None)
        stopped_coercion.assert_not_called()
        stopped_coerce_normalizer.assert_not_called()
        stopped_lookup.assert_not_called()

        with (
            patch.object(
                operand_resolution,
                "dependency_task_output_has_consistent_krw_unit",
                side_effect=RuntimeError("dependency unit gate failed"),
            ),
            patch.object(operand_resolution, "_normalise_operand_value") as stopped_table_normalizer,
            self.assertRaisesRegex(RuntimeError, "dependency unit gate failed"),
        ):
            operand_resolution.repair_krw_operand_units_from_table_metadata([base], evidence_items)
        stopped_table_normalizer.assert_not_called()

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

    def test_current_source_dependency_slot_match_policy_matrix(self) -> None:
        matches = dependency_projection.dependency_slot_matches_input

        def binding(**updates: Any) -> Dict[str, Any]:
            row = {
                "concept": "revenue",
                "period": "2023",
                "role": "current_period",
                "label": "segment revenue",
                "segment_label": "enterprise",
                "nested": {"keep": True},
            }
            row.update(updates)
            return row

        def slot(**updates: Any) -> Dict[str, Any]:
            row = {
                "concept": "revenue",
                "period": "2023",
                "label": "2023 segment revenue",
                "nested": {"keep": True},
            }
            row.update(updates)
            return row

        sibling = {"metric_label": "Enterprise segment revenue", "nested": {"keep": True}}
        state = {"report_scope": {"year": 2023}, "nested": {"keep": True}}
        originals = deepcopy((binding(), slot(), sibling, state))

        self.assertTrue(matches(binding(), slot(), sibling_row=sibling, state=state))
        self.assertEqual((binding(), slot(), sibling, state), originals)

        class StringBomb:
            def __str__(self) -> str:
                raise RuntimeError("period accessed after concept mismatch")

        self.assertFalse(
            matches(
                binding(concept="other", period=StringBomb()),
                slot(period=StringBomb()),
                sibling_row=sibling,
                state=state,
            )
        )

        for name, row_binding, row_slot, row_state, expected in (
            (
                "current report year",
                binding(period="current", role="current_period", segment_label=""),
                slot(period="2023"),
                {"report_scope": {"year": 2023}},
                True,
            ),
            (
                "current wrong year",
                binding(period="current", role="current_period", segment_label=""),
                slot(period="2022"),
                {"report_scope": {"year": 2023}},
                False,
            ),
            (
                "prior report year",
                binding(period="prior", role="prior_period", segment_label=""),
                slot(period="2022"),
                {"report_scope": {"year": 2023}},
                True,
            ),
            (
                "prior wrong year",
                binding(period="prior", role="prior_period", segment_label=""),
                slot(period="2023"),
                {"report_scope": {"year": 2023}},
                False,
            ),
            (
                "unknown binding focus",
                binding(period="custom", role="operand", segment_label=""),
                slot(period="2023"),
                {"report_scope": {"year": 2023}},
                False,
            ),
        ):
            with self.subTest(name=name):
                self.assertEqual(
                    matches(row_binding, row_slot, sibling_row=sibling, state=row_state),
                    expected,
                )

        focus_events: List[Any] = []

        def focus_side_effect(row: Mapping[str, Any], default: str) -> str:
            focus_events.append((dict(row), default))
            return "current"

        with patch.object(dependency_projection, "_operand_period_focus", side_effect=focus_side_effect):
            self.assertTrue(
                matches(
                    binding(period="binding period", segment_label=""),
                    slot(period="slot period"),
                    sibling_row=sibling,
                    state={"report_scope": {"year": "not-a-year"}},
                )
            )
        self.assertEqual(
            focus_events,
            [
                ({"period_hint": "binding period", "role": "current_period"}, "unknown"),
                ({"period_hint": "slot period"}, "unknown"),
            ],
        )

        class YearTypeError:
            def __int__(self) -> int:
                raise TypeError("unsupported year")

        with patch.object(dependency_projection, "_operand_period_focus", side_effect=focus_side_effect):
            focus_events.clear()
            self.assertTrue(
                matches(
                    binding(period="binding period", segment_label=""),
                    slot(period="slot period"),
                    sibling_row=sibling,
                    state={"report_scope": {"year": YearTypeError()}},
                )
            )
        self.assertEqual(len(focus_events), 2)

        class YearRuntimeError:
            def __int__(self) -> int:
                raise RuntimeError("year conversion escaped")

        with patch.object(dependency_projection, "_operand_period_focus", return_value="current") as focus:
            with self.assertRaisesRegex(RuntimeError, "year conversion escaped"):
                matches(
                    binding(period="binding period", segment_label=""),
                    slot(period="slot period"),
                    sibling_row=sibling,
                    state={"report_scope": {"year": YearRuntimeError()}},
                )
        self.assertEqual(focus.call_count, 1)

        self.assertTrue(
            matches(
                binding(label="revenue", segment_label=""),
                slot(label="segment revenue schedule"),
                sibling_row={"metric_label": "other"},
                state=state,
            )
        )
        self.assertTrue(
            matches(
                binding(label="revenue", segment_label=""),
                slot(label="other"),
                sibling_row={"metric_label": "revenue schedule"},
                state=state,
            )
        )
        self.assertFalse(
            matches(
                binding(label="revenue", segment_label=""),
                slot(label="other"),
                sibling_row={"metric_label": "unrelated"},
                state=state,
            )
        )
        self.assertTrue(
            matches(
                binding(label="", segment_label="ENTERPRISE"),
                slot(label="enterprise segment"),
                sibling_row={"metric_label": ""},
                state=state,
            )
        )
        self.assertFalse(
            matches(
                binding(label="", segment_label="retail"),
                slot(label="enterprise segment"),
                sibling_row={"metric_label": ""},
                state=state,
            )
        )

        class LabelBomb:
            def __str__(self) -> str:
                raise AssertionError("label normalization must stay after period resolution")

        with patch.object(dependency_projection.re, "findall", side_effect=RuntimeError("year scan failed")):
            with self.assertRaisesRegex(RuntimeError, "year scan failed"):
                matches(
                    binding(period="current", label=LabelBomb(), segment_label=""),
                    slot(period="2023", label=LabelBomb()),
                    sibling_row={"metric_label": LabelBomb()},
                    state=state,
                )

    def test_current_source_sibling_output_preference_policy_matrix(self) -> None:
        prefers = dependency_projection.task_prefers_sibling_output_synthesis

        class IterBomb:
            def __iter__(self):
                raise AssertionError("inputs must stay lazy behind operation gate")

        self.assertFalse(
            prefers(
                {
                    "active_subtask": {
                        "operation_family": "lookup",
                        "inputs": IterBomb(),
                    }
                }
            )
        )

        qualifying = {
            "source_preference": [" retrieval ", " TASK_OUTPUT "],
            "preferred_task_id": " task_source ",
            "nested": {"keep": True},
        }

        class BindingBomb(Mapping[str, Any]):
            def __iter__(self):
                raise AssertionError("stable scan must stop at first qualifying binding")

            def __len__(self) -> int:
                return 1

            def __getitem__(self, key: str) -> Any:
                raise AssertionError(key)

        for operation in (" difference ", "GROWTH_RATE", "ratio", "sum"):
            late_bomb = BindingBomb()
            inputs = [qualifying, late_bomb]
            state = {
                "active_subtask": {
                    "operation_family": operation,
                    "inputs": inputs,
                    "nested": {"keep": True},
                },
                "nested": {"keep": True},
            }
            qualifying_before = deepcopy(qualifying)
            with self.subTest(operation=operation):
                self.assertTrue(prefers(state))
                self.assertIs(state["active_subtask"]["inputs"], inputs)
                self.assertIs(inputs[0], qualifying)
                self.assertIs(inputs[1], late_bomb)
                self.assertEqual(qualifying, qualifying_before)

        for name, candidate in (
            ("no task output", {"source_preference": ["retrieval"], "preferred_task_id": "task"}),
            ("blank task id", {"source_preference": ["task_output"], "preferred_task_id": "  "}),
            ("empty source preference", {"source_preference": ["", None], "preferred_task_id": "task"}),
        ):
            with self.subTest(name=name):
                self.assertFalse(
                    prefers(
                        {
                            "active_subtask": {
                                "operation_family": "ratio",
                                "inputs": [candidate],
                            }
                        }
                    )
                )

        events: List[str] = []

        def normalise(value: str) -> str:
            events.append(value)
            if value == "task_output":
                raise RuntimeError("source preference normalization failed")
            return value.strip()

        with patch.object(dependency_projection, "_normalise_spaces", side_effect=normalise):
            with self.assertRaisesRegex(RuntimeError, "source preference normalization failed"):
                prefers(
                    {
                        "active_subtask": {
                            "operation_family": "ratio",
                            "inputs": [
                                {
                                    "source_preference": ["task_output"],
                                    "preferred_task_id": "task",
                                }
                            ],
                        }
                    }
                )
        self.assertEqual(events, ["ratio", "task_output"])

    def test_current_source_task_output_binding_projection_matrix(self) -> None:
        project = dependency_projection.task_output_input_bindings
        shared_nested = {"keep": True}
        operation_sentinel = object()
        state = {
            "active_subtask": {
                "operation_family": operation_sentinel,
                "inputs": [
                    {
                        "role": "first",
                        "source_preference": [" task_output ", "retrieval"],
                        "preferred_task_id": " task_a ",
                        "nested": shared_nested,
                    },
                    {
                        "role": "skip_source",
                        "source_preference": ["retrieval"],
                        "preferred_task_id": "task_b",
                    },
                    {
                        "role": "skip_id",
                        "source_preference": ["task_output"],
                        "preferred_task_id": " ",
                    },
                    {
                        "role": "second",
                        "source_preference": ["TASK_OUTPUT"],
                        "preferred_task_id": "task_c",
                        "nested": shared_nested,
                    },
                ],
            },
            "nested": {"keep": True},
        }
        inputs_before = deepcopy(state["active_subtask"]["inputs"])
        state_nested_before = deepcopy(state["nested"])

        projected = project(state)

        self.assertEqual([item["role"] for item in projected], ["first", "second"])
        self.assertIsNot(projected, state["active_subtask"]["inputs"])
        self.assertIsNot(projected[0], state["active_subtask"]["inputs"][0])
        self.assertIsNot(projected[1], state["active_subtask"]["inputs"][3])
        self.assertIs(projected[0]["nested"], shared_nested)
        self.assertIs(projected[1]["nested"], shared_nested)
        self.assertIs(state["active_subtask"]["operation_family"], operation_sentinel)
        self.assertEqual(state["active_subtask"]["inputs"], inputs_before)
        self.assertEqual(state["nested"], state_nested_before)
        self.assertEqual(project({"active_subtask": {"inputs": []}}), [])

        class CopyBomb(Mapping[str, Any]):
            def __iter__(self):
                raise RuntimeError("binding copy failed")

            def __len__(self) -> int:
                return 1

            def __getitem__(self, key: str) -> Any:
                raise RuntimeError(key)

        with self.assertRaisesRegex(RuntimeError, "binding copy failed"):
            project({"active_subtask": {"inputs": [CopyBomb()]}})

        normalised: List[str] = []

        def normalise(value: str) -> str:
            normalised.append(value)
            if value == "task_a":
                raise RuntimeError("task id normalization failed")
            return value.strip()

        with patch.object(dependency_projection, "_normalise_spaces", side_effect=normalise):
            with self.assertRaisesRegex(RuntimeError, "task id normalization failed"):
                project(
                    {
                        "active_subtask": {
                            "inputs": [
                                {
                                    "source_preference": ["task_output"],
                                    "preferred_task_id": "task_a",
                                },
                                CopyBomb(),
                            ]
                        }
                    }
                )
        self.assertEqual(normalised, ["task_output", "task_output", "task_a"])

    def test_current_source_dependency_input_policy_bindings_pin_exact_boundary(self) -> None:
        import ast
        import inspect
        import json
        from pathlib import Path

        from src.agent import financial_graph_calculation as graph_calculation
        from src.agent import financial_graph_reconciliation as graph_reconciliation

        targets = {
            "dependency_slot_matches_input": 61,
            "task_prefers_sibling_output_synthesis": 15,
            "task_output_input_bindings": 16,
        }
        retired = {f"_{name}" for name in targets}
        graph_tree = ast.parse(inspect.getsource(graph_calculation))
        reconciliation_tree = ast.parse(inspect.getsource(graph_reconciliation))
        owner_tree = ast.parse(inspect.getsource(dependency_projection))
        graph_defs = {
            node.name: node
            for node in ast.walk(graph_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        owner_defs = {
            node.name: node
            for node in ast.walk(owner_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        reconciliation_defs = {
            node.name: node
            for node in ast.walk(reconciliation_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertEqual(
            {name: owner_defs[name].end_lineno - owner_defs[name].lineno + 1 for name in targets},
            targets,
        )
        self.assertTrue(retired.isdisjoint(graph_defs))
        self.assertTrue(retired.isdisjoint(reconciliation_defs))
        self.assertEqual(sum(targets.values()), 92)

        def target_name(call: ast.Call) -> str:
            if isinstance(call.func, ast.Name):
                return call.func.id
            if isinstance(call.func, ast.Attribute):
                return call.func.attr
            return ""

        graph_calls = [
            node
            for node in ast.walk(graph_tree)
            if isinstance(node, ast.Call) and target_name(node) in targets
        ]
        reconciliation_calls = [
            node
            for node in ast.walk(reconciliation_tree)
            if isinstance(node, ast.Call) and target_name(node) in targets
        ]
        owner_calls = [
            node
            for node in ast.walk(owner_tree)
            if isinstance(node, ast.Call) and target_name(node) in targets
        ]
        calls = [*graph_calls, *reconciliation_calls, *owner_calls]
        self.assertEqual(
            {name: sum(target_name(call) == name for call in calls) for name in targets},
            {
                "dependency_slot_matches_input": 2,
                "task_prefers_sibling_output_synthesis": 4,
                "task_output_input_bindings": 1,
            },
        )
        self.assertEqual((len(graph_calls), len(reconciliation_calls), len(owner_calls)), (4, 3, 0))

        caller_expectations = {
            ("calculation", "_build_dependency_operand_rows"): (
                graph_defs,
                graph_calls,
                "dependency_slot_matches_input",
                ["binding", "source_slot"],
                {"sibling_row": "sibling_row", "state": "state"},
            ),
            ("calculation", "_append_ratio_result_from_task_outputs"): (
                graph_defs,
                graph_calls,
                "dependency_slot_matches_input",
                ["binding", "source_slot"],
                {"sibling_row": "sibling_row", "state": "state"},
            ),
            ("calculation", "_dependency_binding_resolution_state"): (
                graph_defs,
                graph_calls,
                "task_output_input_bindings",
                ["state"],
                {},
            ),
            ("calculation", "_extract_calculation_operands"): (
                graph_defs,
                graph_calls,
                "task_prefers_sibling_output_synthesis",
                ["state"],
                {},
            ),
            ("reconciliation", "_reconcile_retrieved_evidence"): (
                reconciliation_defs,
                reconciliation_calls,
                "task_prefers_sibling_output_synthesis",
                ["state"],
                {},
            ),
            ("reconciliation", "_select_retry_strategy_for_reconciliation"): (
                reconciliation_defs,
                reconciliation_calls,
                "task_prefers_sibling_output_synthesis",
                ["state"],
                {},
            ),
            ("reconciliation", "_heuristic_reflection_query_plan"): (
                reconciliation_defs,
                reconciliation_calls,
                "task_prefers_sibling_output_synthesis",
                ["state"],
                {},
            ),
        }

        def try_depth(root: ast.AST, target: ast.AST) -> int:
            def visit(node: ast.AST, depth: int) -> int | None:
                if node is target:
                    return depth
                next_depth = depth + int(isinstance(node, (ast.Try, ast.TryStar)))
                for child in ast.iter_child_nodes(node):
                    found = visit(child, next_depth)
                    if found is not None:
                        return found
                return None

            result = visit(root, 0)
            self.assertIsNotNone(result)
            return int(result)

        distributed: List[ast.Call] = []
        for (module_name, caller_name), (definitions, module_calls, callee_name, args, kwargs) in caller_expectations.items():
            caller = definitions[caller_name]
            caller_calls = [call for call in module_calls if call in ast.walk(caller)]
            self.assertEqual(len(caller_calls), 1, (module_name, caller_name))
            call = caller_calls[0]
            self.assertEqual(target_name(call), callee_name)
            self.assertIsInstance(call.func, ast.Name)
            self.assertEqual(
                [ast.dump(argument) for argument in call.args],
                [ast.dump(ast.Name(id=name, ctx=ast.Load())) for name in args],
            )
            self.assertEqual(
                {item.arg: ast.dump(item.value) for item in call.keywords},
                {
                    name: ast.dump(ast.Name(id=value, ctx=ast.Load()))
                    for name, value in kwargs.items()
                },
            )
            self.assertEqual(try_depth(caller, call), 0)
            distributed.append(call)
        self.assertEqual(set(distributed), set(calls))

        graph_bindings = [
            (alias.name, alias.asname)
            for node in graph_tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_dependency_projection"
            for alias in node.names
            if alias.name in targets
        ]
        reconciliation_bindings = [
            (alias.name, alias.asname)
            for node in reconciliation_tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_dependency_projection"
            for alias in node.names
            if alias.name in targets
        ]
        self.assertEqual(
            graph_bindings,
            [
                ("dependency_slot_matches_input", None),
                ("task_output_input_bindings", None),
                ("task_prefers_sibling_output_synthesis", None),
            ],
        )
        self.assertEqual(reconciliation_bindings, [("task_prefers_sibling_output_synthesis", None)])

        dependency_names = {"re", "_normalise_spaces", "_operand_period_focus", "FinancialAgentState"}
        graph_loads = {
            name: sum(
                isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == name
                for node in ast.walk(graph_tree)
            )
            for name in dependency_names
        }
        selected_loads = {
            name: sum(
                isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id == name
                for method_name in targets
                for node in ast.walk(owner_defs[method_name])
            )
            for name in dependency_names
        }
        self.assertTrue(all(graph_loads[name] > 0 for name in dependency_names))
        self.assertTrue(all(selected_loads[name] > 0 for name in dependency_names))

        agent_dir = Path(inspect.getfile(graph_calculation)).parent

        def agent_imports(path: Path) -> set[str]:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            imports: set[str] = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom):
                    if node.module == "src.agent":
                        imports.update(alias.name for alias in node.names)
                    elif node.module and node.module.startswith("src.agent."):
                        imports.add(node.module.rsplit(".", 1)[-1])
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("src.agent."):
                            imports.add(alias.name.rsplit(".", 1)[-1])
            return imports

        graph: Dict[str, set[str]] = {
            path.stem: agent_imports(path)
            for path in agent_dir.glob("*.py")
        }

        def reaches(start: str, target: str) -> bool:
            pending = [start]
            seen: set[str] = set()
            while pending:
                current = pending.pop()
                if current in seen:
                    continue
                seen.add(current)
                for dependency in graph.get(current, set()):
                    if dependency == target:
                        return True
                    pending.append(dependency)
            return False

        self.assertFalse(reaches("financial_graph_helpers", "financial_dependency_projection"))
        self.assertFalse(reaches("financial_graph_state", "financial_dependency_projection"))
        self.assertFalse(reaches("financial_dependency_projection", "financial_graph_calculation"))
        self.assertFalse(reaches("financial_dependency_projection", "financial_graph_reconciliation"))

        baseline = json.loads(
            (Path(__file__).parent / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        selected_literals = {
            node.value
            for method_name in targets
            for node in ast.walk(owner_defs[method_name])
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path") == "src/agent/financial_dependency_projection.py"
                and record.get("text") in selected_literals
            ],
            [],
        )

    def test_current_source_dependency_slot_match_callers_pin_adoption_and_exception_stop(self) -> None:
        from src.agent import financial_graph_calculation as graph_calculation
        from src.agent.financial_graph import FinancialAgent

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
                        "source_preference": ["task_output"],
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
            "nested": {"keep": True},
        }
        state_before = deepcopy(state)
        matcher_calls: List[Any] = []

        def matcher(*args: Any, **kwargs: Any) -> bool:
            matcher_calls.append((args, kwargs))
            return True

        with patch.object(graph_calculation, "dependency_slot_matches_input", side_effect=matcher):
            rows = agent._build_dependency_operand_rows(state)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(matcher_calls), 1)
        match_args, match_kwargs = matcher_calls[0]
        self.assertEqual(match_args[0]["preferred_task_id"], "task_current")
        self.assertEqual(match_args[1]["normalized_value"], 100)
        self.assertEqual(match_kwargs["sibling_row"]["task_id"], "task_current")
        self.assertIs(match_kwargs["state"], state)
        self.assertEqual(state, state_before)

        with patch.object(graph_calculation, "dependency_slot_matches_input", return_value=False):
            self.assertEqual(agent._build_dependency_operand_rows(state), [])

        with patch.object(
            graph_calculation,
            "dependency_slot_matches_input",
            side_effect=RuntimeError("dependency match failed"),
        ), patch.object(
            graph_calculation,
            "score_direct_structured_lookup_evidence",
            side_effect=AssertionError("downstream scoring must stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency match failed"):
                agent._build_dependency_operand_rows(state)
        self.assertEqual(state, state_before)

        ordered = [
            {
                "task_id": "task_source",
                "operation_family": "lookup",
                "status": "ok",
                "metric_label": "metric",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "label": "metric",
                            "concept": "metric",
                            "period": "2023",
                            "raw_value": "10",
                            "raw_unit": "COUNT",
                            "normalized_value": 10.0,
                            "normalized_unit": "COUNT",
                        }
                    },
                },
            }
        ]
        ratio_state = {
            "query": "ratio",
            "calc_subtasks": [
                {
                    "task_id": "task_ratio",
                    "operation_family": "ratio",
                    "metric_label": "ratio",
                    "inputs": [
                        {
                            "label": "metric",
                            "concept": "metric",
                            "period": "2023",
                            "role": "numerator_1",
                            "source_preference": ["task_output"],
                            "preferred_task_id": "task_source",
                        }
                    ],
                }
            ],
        }
        ordered_before = deepcopy(ordered)
        ratio_before = deepcopy(ratio_state)
        fallback_calls: List[Any] = []
        matcher_calls.clear()
        with patch.object(graph_calculation, "dependency_slot_matches_input", side_effect=matcher), patch.object(
            graph_calculation,
            "_operand_text_match",
            side_effect=lambda *args, **kwargs: fallback_calls.append((args, kwargs)) or False,
        ):
            self.assertIs(agent._append_ratio_result_from_task_outputs(ordered, ratio_state), ordered)
        self.assertEqual(len(matcher_calls), 1)
        self.assertEqual(fallback_calls, [])
        ratio_args, ratio_kwargs = matcher_calls[0]
        self.assertEqual([item.get("concept") for item in ratio_args], ["metric", "metric"])
        self.assertEqual(ratio_kwargs["sibling_row"]["task_id"], "task_source")
        self.assertIs(ratio_kwargs["state"], ratio_state)

        with patch.object(graph_calculation, "dependency_slot_matches_input", return_value=False), patch.object(
            graph_calculation,
            "_operand_text_match",
            side_effect=lambda *args, **kwargs: fallback_calls.append((args, kwargs)) or False,
        ):
            fallback_calls.clear()
            self.assertIs(agent._append_ratio_result_from_task_outputs(ordered, ratio_state), ordered)
        self.assertEqual(len(fallback_calls), 1)

        with patch.object(
            graph_calculation,
            "dependency_slot_matches_input",
            side_effect=RuntimeError("ratio dependency match failed"),
        ), patch.object(
            graph_calculation,
            "_operand_text_match",
            side_effect=AssertionError("fallback must stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "ratio dependency match failed"):
                agent._append_ratio_result_from_task_outputs(ordered, ratio_state)
        self.assertEqual(ordered, ordered_before)
        self.assertEqual(ratio_state, ratio_before)

    def test_current_source_dependency_binding_callers_pin_adoption_and_exception_stop(self) -> None:
        from src.agent import financial_graph_calculation as graph_calculation
        from src.agent import financial_graph_reconciliation as graph_reconciliation
        from src.agent.financial_graph import FinancialAgent

        agent = FinancialAgent.__new__(FinancialAgent)
        state = {"active_subtask": {"inputs": []}, "nested": {"keep": True}}
        bindings = [{"role": "numerator", "nested": {"keep": True}}]
        rows = [{"matched_operand_role": "numerator", "nested": {"keep": True}}]
        owner_result = {"bindings": bindings, "rows": rows, "all_resolved": True}
        events: List[Any] = []

        def binding_projection(received_state: Mapping[str, Any]) -> List[Dict[str, Any]]:
            events.append(("bindings", received_state))
            return bindings

        def row_projection(received_state: Mapping[str, Any]) -> List[Dict[str, Any]]:
            events.append(("rows", received_state))
            return rows

        def summarize(received_bindings: Any, received_rows: Any) -> Dict[str, Any]:
            events.append(("summarize", received_bindings, received_rows))
            self.assertIs(received_bindings, bindings)
            self.assertIs(received_rows, rows)
            return owner_result

        with patch.object(graph_calculation, "task_output_input_bindings", side_effect=binding_projection), patch.object(
            agent,
            "_build_dependency_operand_rows",
            side_effect=row_projection,
        ), patch.object(graph_calculation, "summarize_dependency_bindings", side_effect=summarize):
            resolved = agent._dependency_binding_resolution_state(state)
        self.assertIs(resolved, owner_result)
        self.assertEqual(
            events,
            [("bindings", state), ("rows", state), ("summarize", bindings, rows)],
        )

        with patch.object(
            graph_calculation,
            "task_output_input_bindings",
            side_effect=RuntimeError("binding projection failed"),
        ), patch.object(
            agent,
            "_build_dependency_operand_rows",
            side_effect=AssertionError("row projection must stop"),
        ), patch.object(
            graph_calculation,
            "summarize_dependency_bindings",
            side_effect=AssertionError("summary must stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "binding projection failed"):
                agent._dependency_binding_resolution_state(state)

        extract_state = {
            "query": "q",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "retry_strategy": "synthesize_from_task_outputs",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "ratio",
                "operation_family": "ratio",
                "required_operands": [],
                "inputs": [],
            },
            "subtask_results": [],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "reconciliation_result": {},
            "calc_subtasks": [],
            "semantic_plan": {},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "nested": {"keep": True},
        }
        extract_before = deepcopy(extract_state)
        empty_dependency_state = {
            "rows": [],
            "bindings": [],
            "binding_keys": set(),
            "resolved_keys": set(),
            "missing_bindings": [],
            "all_resolved": True,
        }

        for preference, expected_source in ((True, "dependency_synthesis_only"), (False, "")):
            call_states: List[Any] = []

            def preference_owner(received_state: Mapping[str, Any]) -> bool:
                call_states.append(received_state)
                return preference

            with patch.object(
                agent,
                "_dependency_binding_resolution_state",
                return_value=empty_dependency_state,
            ), patch.object(
                graph_calculation,
                "task_prefers_sibling_output_synthesis",
                side_effect=preference_owner,
            ):
                extracted = agent._extract_calculation_operands(extract_state)
            self.assertEqual(call_states, [extract_state])
            self.assertEqual(
                str(extracted.get("calculation_debug_trace", {}).get("source") or ""),
                expected_source,
            )
            self.assertEqual(extract_state, extract_before)

        with patch.object(
            agent,
            "_dependency_binding_resolution_state",
            return_value=empty_dependency_state,
        ), patch.object(
            agent,
            "_active_retry_strategy",
            return_value="retry_retrieval",
        ), patch.object(
            graph_calculation,
            "task_prefers_sibling_output_synthesis",
            side_effect=AssertionError("preference must stay lazy for other retry strategies"),
        ):
            agent._extract_calculation_operands(extract_state)

        with patch.object(
            agent,
            "_dependency_binding_resolution_state",
            return_value=empty_dependency_state,
        ), patch.object(
            graph_calculation,
            "task_prefers_sibling_output_synthesis",
            side_effect=RuntimeError("synthesis preference failed"),
        ), patch.object(
            graph_calculation,
            "resolve_main_operand_precedence",
            side_effect=AssertionError("main precedence must stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "synthesis preference failed"):
                agent._extract_calculation_operands(extract_state)
        self.assertEqual(extract_state, extract_before)

        reconciliation_state = {
            "active_subtask": {"task_id": "task_ratio", "operation_family": "ratio"},
            "tasks": [{"task_id": "task_ratio"}],
            "artifacts": [],
            "reconciliation_retry_count": 0,
            "query": "ratio query",
            "topic": "ratio topic",
            "intent": "numeric_fact",
            "nested": {"keep": True},
        }
        reconciliation_before = deepcopy(reconciliation_state)
        resolved_dependency_state = {"all_resolved": True, "rows": rows, "bindings": bindings}
        resolved_reconciliation = {"task_id": "task_ratio", "status": "ready"}
        active_subtask = {"task_id": "task_ratio", "operation_family": "ratio"}
        reconciliation_events: List[Any] = []

        with patch.object(
            graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            side_effect=lambda subtask, received_state: reconciliation_events.append(
                ("active", subtask, received_state)
            )
            or active_subtask,
        ), patch.object(
            agent,
            "_dependency_binding_resolution_state",
            side_effect=lambda received_state: reconciliation_events.append(
                ("dependency", received_state)
            )
            or resolved_dependency_state,
        ), patch.object(
            graph_reconciliation,
            "task_prefers_sibling_output_synthesis",
            side_effect=lambda received_state: reconciliation_events.append(
                ("preference", received_state)
            )
            or True,
        ), patch.object(
            graph_reconciliation,
            "dependency_resolved_reconciliation_result",
            side_effect=lambda **kwargs: reconciliation_events.append(("resolved", kwargs))
            or resolved_reconciliation,
        ), patch.object(
            graph_reconciliation,
            "reconciliation_evidence_refs",
            return_value=[],
        ), patch.object(
            graph_reconciliation,
            "_reconciliation_result_artifact_update",
            return_value={"tasks": reconciliation_state["tasks"], "artifacts": []},
        ):
            reconciled = agent._reconcile_retrieved_evidence(reconciliation_state)
        self.assertIs(reconciled["reconciliation_result"], resolved_reconciliation)
        self.assertEqual([event[0] for event in reconciliation_events], ["active", "dependency", "preference", "resolved"])
        self.assertIs(reconciliation_events[0][2], reconciliation_state)
        self.assertIs(reconciliation_events[1][1], reconciliation_state)
        self.assertIs(reconciliation_events[2][1], reconciliation_state)
        self.assertIs(reconciliation_events[3][1]["active_subtask"], active_subtask)
        self.assertIs(reconciliation_events[3][1]["dependency_state"], resolved_dependency_state)
        self.assertEqual(reconciliation_state, reconciliation_before)

        with patch.object(
            graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            return_value=active_subtask,
        ), patch.object(
            agent,
            "_dependency_binding_resolution_state",
            return_value=resolved_dependency_state,
        ), patch.object(
            graph_reconciliation,
            "task_prefers_sibling_output_synthesis",
            side_effect=RuntimeError("reconciliation preference failed"),
        ), patch.object(
            graph_reconciliation,
            "dependency_resolved_reconciliation_result",
            side_effect=AssertionError("resolved reconciliation must stop"),
        ), patch.object(
            graph_reconciliation,
            "_reconciliation_result_artifact_update",
            side_effect=AssertionError("artifact update must stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "reconciliation preference failed"):
                agent._reconcile_retrieved_evidence(reconciliation_state)

        with patch.object(
            graph_reconciliation,
            "task_prefers_sibling_output_synthesis",
            side_effect=AssertionError("ready status must skip preference"),
        ):
            self.assertEqual(
                agent._select_retry_strategy_for_reconciliation(
                    reconciliation_state,
                    {"status": " ready "},
                ),
                "",
            )

        retry_events: List[Any] = []
        with patch.object(
            graph_reconciliation,
            "task_prefers_sibling_output_synthesis",
            side_effect=lambda received_state: retry_events.append(("preference", received_state)) or True,
        ), patch.object(
            agent,
            "_dependency_binding_resolution_state",
            side_effect=lambda received_state: retry_events.append(("dependency", received_state))
            or resolved_dependency_state,
        ):
            self.assertEqual(
                agent._select_retry_strategy_for_reconciliation(
                    reconciliation_state,
                    {"status": "retry_retrieval"},
                ),
                "synthesize_from_task_outputs",
            )
        self.assertEqual(retry_events, [("preference", reconciliation_state), ("dependency", reconciliation_state)])

        with patch.object(graph_reconciliation, "task_prefers_sibling_output_synthesis", return_value=False), patch.object(
            agent,
            "_dependency_binding_resolution_state",
            side_effect=AssertionError("dependency state must stay lazy after false preference"),
        ):
            self.assertEqual(
                agent._select_retry_strategy_for_reconciliation(
                    reconciliation_state,
                    {"status": "insufficient_operands"},
                ),
                "stop_insufficient",
            )

        reflection_events: List[Any] = []
        with patch.object(
            agent,
            "_dependency_binding_resolution_state",
            side_effect=lambda received_state: reflection_events.append(("dependency", received_state))
            or resolved_dependency_state,
        ), patch.object(
            graph_reconciliation,
            "task_prefers_sibling_output_synthesis",
            side_effect=lambda received_state: reflection_events.append(("preference", received_state))
            or True,
        ), patch.object(
            agent,
            "_infer_missing_info",
            side_effect=lambda received_state, operands: reflection_events.append(
                ("missing", received_state, operands)
            )
            or ["missing value"],
        ), patch.object(
            agent,
            "_build_retry_queries",
            side_effect=lambda received_state, missing: reflection_events.append(
                ("queries", received_state, missing)
            )
            or ["retry query"],
        ), patch.object(
            graph_reconciliation,
            "_preferred_calc_sections",
            side_effect=lambda *args: reflection_events.append(("sections", args)) or ["section"],
        ):
            reflection_plan = agent._heuristic_reflection_query_plan(
                reconciliation_state,
                [],
                retry_objective="resolve_binding",
                explanation="explain",
            )
        self.assertEqual(reflection_plan["retry_strategy"], "synthesize_from_task_outputs")
        self.assertEqual(reflection_plan["subqueries"], ["retry query"])
        self.assertEqual(
            [event[0] for event in reflection_events],
            ["dependency", "preference", "missing", "queries", "sections"],
        )
        self.assertIs(reflection_events[0][1], reconciliation_state)
        self.assertIs(reflection_events[1][1], reconciliation_state)
        self.assertIs(reflection_events[2][1], reconciliation_state)
        self.assertIs(reflection_events[3][1], reconciliation_state)

        with patch.object(
            agent,
            "_dependency_binding_resolution_state",
            return_value=resolved_dependency_state,
        ), patch.object(
            graph_reconciliation,
            "task_prefers_sibling_output_synthesis",
            side_effect=RuntimeError("reflection preference failed"),
        ), patch.object(
            agent,
            "_infer_missing_info",
            side_effect=AssertionError("missing-info projection must stop"),
        ), patch.object(
            agent,
            "_build_retry_queries",
            side_effect=AssertionError("query projection must stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "reflection preference failed"):
                agent._heuristic_reflection_query_plan(reconciliation_state, [])
        self.assertEqual(reconciliation_state, reconciliation_before)

    def test_current_source_sibling_lookup_surface_projection_pins_branches_and_copy_contract(self) -> None:
        nested = {"keep": True}
        same_task_string_calls: List[str] = []

        class StringBomb:
            def __init__(self, message: str, calls: List[str] | None = None) -> None:
                self.message = message
                self.calls = calls

            def __str__(self) -> str:
                if self.calls is not None:
                    self.calls.append(self.message)
                raise RuntimeError(self.message)

        active_subtask = {
            "task_id": " task-active ",
            "sibling_lookup_surfaces": [" existing ", "dup", " "],
            "nested": nested,
        }
        state = {
            "calc_subtasks": [
                {
                    "task_id": "task-active",
                    "operation_family": StringBomb("same task family accessed", same_task_string_calls),
                },
                {
                    "task_id": "skip",
                    "operation_family": "sum",
                    "metric_family": "other",
                    "metric_label": StringBomb("invalid task label accessed"),
                },
                {
                    "task_id": "lookup-a",
                    "operation_family": " LOOKUP ",
                    "metric_family": "other",
                    "metric_label": "2024 Revenue",
                    "required_operands": [
                        {
                            "label": "2023 Cost",
                            "aliases": ["Revenue", " alias ", ""],
                            "nested": nested,
                        }
                    ],
                },
                {
                    "task_id": "lookup-b",
                    "operation_family": "other",
                    "metric_family": " concept_single_value ",
                    "metric_label": "2025 Margin",
                    "required_operands": [
                        {
                            "label": "2024 Expense",
                            "aliases": ["alias", "tail"],
                        }
                    ],
                },
                {
                    "task_id": "lookup-c",
                    "operation_family": "single_value",
                    "metric_family": "other",
                    "metric_label": "",
                    "required_operands": [
                        {
                            "label": "",
                            "aliases": [" alias-only "],
                        }
                    ],
                },
            ],
            "nested": nested,
        }
        def frozen(value: Any) -> Any:
            if type(value) is dict:
                return tuple((key, frozen(item)) for key, item in value.items())
            if type(value) is list:
                return tuple(frozen(item) for item in value)
            if type(value) is tuple:
                return tuple(frozen(item) for item in value)
            return value

        active_before = frozen(active_subtask)
        state_before = frozen(state)
        policy_events: List[tuple[str, str]] = []
        regex_events: List[tuple[str, str, str]] = []
        pattern = r"^(?:20\d{2}\s*)"

        class RecordingPolicy:
            def get(self, key: str, default: Any = None) -> Any:
                policy_events.append(("get", key))
                if key == "lookup_surface_period_prefix_pattern":
                    return pattern
                return default

        original_sub = dependency_projection.re.sub

        def recording_sub(expression: str, replacement: str, value: str) -> str:
            regex_events.append((expression, replacement, value))
            return original_sub(expression, replacement, value)

        with patch.object(
            dependency_projection,
            "RECONCILIATION_POLICY",
            RecordingPolicy(),
        ), patch.object(
            dependency_projection.re,
            "sub",
            side_effect=recording_sub,
        ):
            projected = dependency_projection.active_subtask_with_sibling_lookup_surfaces(
                active_subtask,
                state,
            )

        self.assertIsNot(projected, active_subtask)
        self.assertIs(projected["nested"], nested)
        self.assertEqual(
            projected["sibling_lookup_surfaces"],
            [
                "existing",
                "dup",
                "Revenue",
                "Cost",
                "alias",
                "Margin",
                "Expense",
                "tail",
                "alias-only",
            ],
        )
        self.assertEqual(
            policy_events,
            [
                ("get", "lookup_surface_period_prefix_pattern"),
                ("get", "lookup_surface_period_prefix_pattern"),
                ("get", "lookup_surface_period_prefix_pattern"),
            ],
        )
        self.assertEqual(
            regex_events,
            [
                (pattern, "", "2024 Revenue"),
                (pattern, "", "2023 Cost"),
                (pattern, "", "2025 Margin"),
                (pattern, "", "2024 Expense"),
                (pattern, "", ""),
                (pattern, "", ""),
            ],
        )
        self.assertEqual(same_task_string_calls, [])
        self.assertEqual(frozen(active_subtask), active_before)
        self.assertEqual(frozen(state), state_before)
        self.assertIs(active_subtask["nested"], nested)
        self.assertIs(state["nested"], nested)
        self.assertIs(state["calc_subtasks"][2]["required_operands"][0]["nested"], nested)

        with patch.object(
            dependency_projection,
            "RECONCILIATION_POLICY",
            {"lookup_surface_period_prefix_pattern": ""},
        ), patch.object(
            dependency_projection.re,
            "sub",
            side_effect=AssertionError("blank pattern must skip regex"),
        ):
            blank_active = dependency_projection.active_subtask_with_sibling_lookup_surfaces(
                {"task_id": " "},
                {
                    "calc_subtasks": [
                        {
                            "task_id": " ",
                            "operation_family": "single_value",
                            "metric_label": "2024 Kept",
                        }
                    ]
                },
            )
        self.assertEqual(blank_active["sibling_lookup_surfaces"], ["2024 Kept"])

        class StateGetBomb:
            def get(self, key: str, default: Any = None) -> Any:
                raise AssertionError(f"state access after surface failure: {key}")

        with self.assertRaisesRegex(RuntimeError, "existing surface failed"):
            dependency_projection.active_subtask_with_sibling_lookup_surfaces(
                {"sibling_lookup_surfaces": [StringBomb("existing surface failed")]},
                StateGetBomb(),
            )

        class CopyBomb(Mapping[str, Any]):
            def __init__(self, message: str) -> None:
                self.message = message

            def __getitem__(self, key: str) -> Any:
                raise RuntimeError(self.message)

            def __iter__(self):
                raise RuntimeError(self.message)

            def __len__(self) -> int:
                return 1

        with self.assertRaisesRegex(RuntimeError, "active copy failed"):
            dependency_projection.active_subtask_with_sibling_lookup_surfaces(
                CopyBomb("active copy failed"),
                StateGetBomb(),
            )

        with self.assertRaisesRegex(RuntimeError, "task copy failed"):
            dependency_projection.active_subtask_with_sibling_lookup_surfaces(
                {},
                {"calc_subtasks": [CopyBomb("task copy failed")]},
            )

        class PolicyBomb:
            def get(self, key: str, default: Any = None) -> Any:
                raise RuntimeError("policy access failed")

        with patch.object(dependency_projection, "RECONCILIATION_POLICY", PolicyBomb()):
            with self.assertRaisesRegex(RuntimeError, "policy access failed"):
                dependency_projection.active_subtask_with_sibling_lookup_surfaces(
                    {},
                    {
                        "calc_subtasks": [
                            {
                                "operation_family": "lookup",
                                "metric_label": StringBomb("label must stop after policy"),
                            }
                        ]
                    },
                )

        class AliasIterationBomb:
            def __iter__(self):
                raise RuntimeError("alias iteration failed")

        with patch.object(
            dependency_projection,
            "RECONCILIATION_POLICY",
            {"lookup_surface_period_prefix_pattern": ""},
        ):
            with self.assertRaisesRegex(RuntimeError, "alias iteration failed"):
                dependency_projection.active_subtask_with_sibling_lookup_surfaces(
                    {},
                    {
                        "calc_subtasks": [
                            {
                                "operation_family": "lookup",
                                "metric_label": "",
                                "required_operands": [
                                    {"label": "", "aliases": AliasIterationBomb()}
                                ],
                            }
                        ]
                    },
                )

        class OperandIterationBomb:
            def __iter__(self):
                raise AssertionError("operand iteration must stop after regex")

        with patch.object(
            dependency_projection,
            "RECONCILIATION_POLICY",
            {"lookup_surface_period_prefix_pattern": pattern},
        ), patch.object(
            dependency_projection.re,
            "sub",
            side_effect=RuntimeError("prefix regex failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "prefix regex failed"):
                dependency_projection.active_subtask_with_sibling_lookup_surfaces(
                    {},
                    {
                        "calc_subtasks": [
                            {
                                "operation_family": "lookup",
                                "metric_label": "2024 Revenue",
                                "required_operands": OperandIterationBomb(),
                            }
                        ]
                    },
                )

    def test_current_source_dependency_resolved_result_pins_order_copy_and_exceptions(self) -> None:
        access_events: List[tuple[str, str]] = []
        normalise_events: List[str] = []
        nested = {"keep": True}

        class RecordingBinding(Mapping[str, Any]):
            def __init__(self, name: str, values: Dict[str, Any]) -> None:
                self.name = name
                self.values = values

            def __getitem__(self, key: str) -> Any:
                access_events.append((self.name, key))
                return self.values[key]

            def __iter__(self):
                return iter(self.values)

            def __len__(self) -> int:
                return len(self.values)

        first = RecordingBinding(
            "first",
            {
                "preferred_task_id": " task-a ",
                "label": " Revenue ",
                "role": " numerator ",
                "concept": " sales ",
                "nested": nested,
            },
        )
        second = RecordingBinding(
            "second",
            {
                "preferred_task_id": " ",
                "label": " Cost ",
                "role": " denominator ",
                "concept": " expense ",
            },
        )
        active_subtask = {"task_id": " task-ratio ", "nested": nested}
        dependency_state = {"bindings": [first, second], "nested": nested}
        active_before = dict(active_subtask)
        bindings_before = [dict(first), dict(second)]

        def normalise(value: str) -> str:
            normalise_events.append(value)
            return value.strip()

        access_events.clear()
        with patch.object(dependency_projection, "_normalise_spaces", side_effect=normalise):
            result = dependency_projection.dependency_resolved_reconciliation_result(
                active_subtask=active_subtask,
                dependency_state=dependency_state,
            )

        self.assertEqual(
            access_events,
            [
                ("first", "preferred_task_id"),
                ("first", "label"),
                ("first", "role"),
                ("first", "concept"),
                ("second", "preferred_task_id"),
                ("second", "label"),
                ("second", "role"),
                ("second", "concept"),
            ],
        )
        self.assertEqual(
            normalise_events,
            [" task-a ", " Revenue ", " numerator ", " sales ", " ", " Cost ", " denominator ", " expense "],
        )
        self.assertEqual(
            result,
            {
                "status": "ready",
                "task_id": " task-ratio ",
                "matched_operands": [
                    {
                        "label": "Revenue",
                        "role": "numerator",
                        "concept": "sales",
                        "matched": True,
                        "candidate_ids": ["task_output:task-a"],
                        "reason": "resolved_from_task_outputs",
                    },
                    {
                        "label": "Cost",
                        "role": "denominator",
                        "concept": "expense",
                        "matched": True,
                        "candidate_ids": [],
                        "reason": "resolved_from_task_outputs",
                    },
                ],
                "missing_operands": [],
                "retry_queries": [],
                "notes": ["dependency_task_outputs_ready"],
                "retry_strategy": "",
            },
        )
        self.assertIsNot(result["matched_operands"], dependency_state["bindings"])
        self.assertIsNot(result["matched_operands"][0], first)
        self.assertIsNot(result["missing_operands"], result["retry_queries"])
        self.assertEqual(active_subtask, active_before)
        self.assertEqual([dict(first), dict(second)], bindings_before)
        self.assertIs(active_subtask["nested"], nested)
        self.assertIs(dependency_state["nested"], nested)

        stop_events: List[tuple[str, str]] = []

        class TaskIdBomb:
            def __str__(self) -> str:
                raise AssertionError("task id must stop after binding failure")

        failing_binding = RecordingBinding(
            "failing",
            {
                "preferred_task_id": "source",
                "label": "label",
                "role": "boom-role",
                "concept": "concept",
            },
        )

        def failing_normalise(value: str) -> str:
            stop_events.append(("normalise", value))
            if value == "boom-role":
                raise RuntimeError("role normalization failed")
            return value

        access_events.clear()
        with patch.object(dependency_projection, "_normalise_spaces", side_effect=failing_normalise):
            with self.assertRaisesRegex(RuntimeError, "role normalization failed"):
                dependency_projection.dependency_resolved_reconciliation_result(
                    active_subtask={"task_id": TaskIdBomb()},
                    dependency_state={"bindings": [failing_binding, second]},
                )
        self.assertEqual(
            access_events,
            [
                ("failing", "preferred_task_id"),
                ("failing", "label"),
                ("failing", "role"),
            ],
        )
        self.assertEqual(
            stop_events,
            [("normalise", "source"), ("normalise", "label"), ("normalise", "boom-role")],
        )

        class BindingIterationBomb:
            def __iter__(self):
                raise RuntimeError("binding iteration failed")

        with self.assertRaisesRegex(RuntimeError, "binding iteration failed"):
            dependency_projection.dependency_resolved_reconciliation_result(
                active_subtask={"task_id": TaskIdBomb()},
                dependency_state={"bindings": BindingIterationBomb()},
            )

        class ActiveTaskAccessBomb:
            def get(self, key: str, default: Any = None) -> Any:
                raise RuntimeError("active task access failed")

        with self.assertRaisesRegex(RuntimeError, "active task access failed"):
            dependency_projection.dependency_resolved_reconciliation_result(
                active_subtask=ActiveTaskAccessBomb(),
                dependency_state={"bindings": []},
            )

    def test_current_source_dependency_reconciliation_bindings_pin_exact_move_boundary(self) -> None:
        import ast
        import inspect
        import json
        from pathlib import Path

        from src.agent import financial_graph_reconciliation as graph_reconciliation

        graph_tree = ast.parse(inspect.getsource(graph_reconciliation))
        owner_tree = ast.parse(inspect.getsource(dependency_projection))
        graph_defs = {
            node.name: node
            for node in ast.walk(graph_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        owner_defs = {
            node.name: node
            for node in ast.walk(owner_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        targets = {
            "active_subtask_with_sibling_lookup_surfaces": 47,
            "dependency_resolved_reconciliation_result": 27,
        }
        self.assertEqual(
            {
                name: owner_defs[name].end_lineno - owner_defs[name].lineno + 1
                for name in targets
            },
            targets,
        )
        self.assertTrue({f"_{name}" for name in targets}.isdisjoint(graph_defs))
        self.assertEqual(sum(targets.values()), 74)

        def target_name(call: ast.Call) -> str:
            if isinstance(call.func, ast.Name):
                return call.func.id
            if isinstance(call.func, ast.Attribute):
                return call.func.attr
            return ""

        selected_calls = [
            node
            for node in ast.walk(graph_tree)
            if isinstance(node, ast.Call) and target_name(node) in targets
        ]
        self.assertEqual(
            {
                name: sum(target_name(call) == name for call in selected_calls)
                for name in targets
            },
            {
                "active_subtask_with_sibling_lookup_surfaces": 4,
                "dependency_resolved_reconciliation_result": 1,
            },
        )
        selected_loads = [
            node
            for node in ast.walk(graph_tree)
            if (
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id in targets
            )
            or (
                isinstance(node, ast.Attribute)
                and isinstance(node.ctx, ast.Load)
                and node.attr in targets
            )
        ]
        parent = {
            child: node
            for node in ast.walk(graph_tree)
            for child in ast.iter_child_nodes(node)
        }
        self.assertEqual(len(selected_loads), len(selected_calls))
        self.assertTrue(
            all(
                isinstance(parent.get(node), ast.Call) and parent[node].func is node
                for node in selected_loads
            )
        )

        caller_expectations = {
            "_rerank_reconciliation_matches_with_llm": "active_subtask_with_sibling_lookup_surfaces",
            "_evidence_items_from_reconciliation_matches": "active_subtask_with_sibling_lookup_surfaces",
            "_extract_structured_operands_from_reconciliation": "active_subtask_with_sibling_lookup_surfaces",
            "_reconcile_retrieved_evidence": "active_subtask_with_sibling_lookup_surfaces",
        }

        def try_depth(root: ast.AST, target: ast.AST) -> int:
            def visit(node: ast.AST, depth: int) -> int | None:
                if node is target:
                    return depth
                next_depth = depth + int(isinstance(node, (ast.Try, ast.TryStar)))
                for child in ast.iter_child_nodes(node):
                    found = visit(child, next_depth)
                    if found is not None:
                        return found
                return None

            result = visit(root, 0)
            self.assertIsNotNone(result)
            return int(result)

        distributed: List[ast.Call] = []
        expected_first_argument = ast.dump(
            ast.parse("dict(state.get('active_subtask') or {})", mode="eval").body
        )
        for caller_name, callee_name in caller_expectations.items():
            caller = graph_defs[caller_name]
            calls = [
                call
                for call in selected_calls
                if call in ast.walk(caller) and target_name(call) == callee_name
            ]
            self.assertEqual(len(calls), 1, caller_name)
            call = calls[0]
            self.assertIsInstance(call.func, ast.Name)
            self.assertEqual(
                [ast.dump(argument) for argument in call.args],
                [expected_first_argument, ast.dump(ast.Name(id="state", ctx=ast.Load()))],
            )
            self.assertEqual(call.keywords, [])
            self.assertEqual(try_depth(caller, call), 0)
            distributed.append(call)

        reconcile_caller = graph_defs["_reconcile_retrieved_evidence"]
        result_calls = [
            call
            for call in selected_calls
            if call in ast.walk(reconcile_caller)
            and target_name(call) == "dependency_resolved_reconciliation_result"
        ]
        self.assertEqual(len(result_calls), 1)
        result_call = result_calls[0]
        self.assertIsInstance(result_call.func, ast.Name)
        self.assertEqual(result_call.args, [])
        self.assertEqual(
            {keyword.arg: ast.unparse(keyword.value) for keyword in result_call.keywords},
            {
                "active_subtask": "active_subtask",
                "dependency_state": "dependency_state",
            },
        )
        self.assertEqual(try_depth(reconcile_caller, result_call), 0)
        distributed.append(result_call)
        self.assertEqual(set(distributed), set(selected_calls))

        graph_imports = [
            node
            for node in graph_tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.config.retrieval_policy"
        ]
        owner_imports = [
            node
            for node in owner_tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.config.retrieval_policy"
        ]
        self.assertEqual(len(graph_imports), 1)
        self.assertEqual(len(owner_imports), 1)
        self.assertIn(
            "RECONCILIATION_POLICY",
            {alias.name for alias in graph_imports[0].names},
        )
        self.assertIn(
            "RECONCILIATION_POLICY",
            {alias.name for alias in owner_imports[0].names},
        )

        selected_bindings = [
            alias.name
            for node in graph_tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_dependency_projection"
            for alias in node.names
            if alias.name in targets
        ]
        self.assertEqual(
            selected_bindings,
            [
                "active_subtask_with_sibling_lookup_surfaces",
                "dependency_resolved_reconciliation_result",
            ],
        )

        selected_nodes = [owner_defs[name] for name in targets]
        dependency_names = {
            "re",
            "Any",
            "Dict",
            "List",
            "FinancialAgentState",
            "_normalise_spaces",
            "RECONCILIATION_POLICY",
        }
        outside_loads = {
            name: sum(
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == name
                for node in ast.walk(graph_tree)
            )
            for name in dependency_names
        }
        self.assertTrue(all(outside_loads[name] > 0 for name in dependency_names))
        owner_selected_loads = {
            name: sum(
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == name
                for selected in selected_nodes
                for node in ast.walk(selected)
            )
            for name in dependency_names
        }
        self.assertTrue(all(owner_selected_loads[name] > 0 for name in dependency_names))

        agent_dir = Path(inspect.getfile(graph_reconciliation)).parent

        def agent_imports(path: Path) -> set[str]:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            imports: set[str] = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom):
                    if node.module == "src.agent":
                        imports.update(alias.name for alias in node.names)
                    elif node.module and node.module.startswith("src.agent."):
                        imports.add(node.module.rsplit(".", 1)[-1])
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("src.agent."):
                            imports.add(alias.name.rsplit(".", 1)[-1])
            return imports

        module_graph = {
            path.stem: agent_imports(path)
            for path in agent_dir.glob("*.py")
        }

        def reaches(start: str, target: str) -> bool:
            pending = [start]
            seen: set[str] = set()
            while pending:
                current = pending.pop()
                if current in seen:
                    continue
                seen.add(current)
                for dependency in module_graph.get(current, set()):
                    if dependency == target:
                        return True
                    pending.append(dependency)
            return False

        self.assertFalse(
            reaches("financial_dependency_projection", "financial_graph_reconciliation")
        )
        self.assertFalse(
            reaches("financial_dependency_projection", "financial_graph_calculation")
        )

        baseline = json.loads(
            (Path(__file__).parent / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path") == "src/agent/financial_dependency_projection.py"
                and record.get("text")
                in {
                    node.value
                    for selected in selected_nodes
                    for node in ast.walk(selected)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                }
            ],
            [],
        )
        self.assertEqual((len(selected_calls), 0), (5, 0))

    def test_current_source_sibling_surface_rerank_caller_pins_args_adoption_and_stop(self) -> None:
        from src.agent import financial_graph_reconciliation as graph_reconciliation
        from src.agent.financial_graph import FinancialAgent

        agent = FinancialAgent.__new__(FinancialAgent)
        state_nested = {"keep": True}
        operand_nested = {"operand": True}
        row_nested = {"row": True}
        state = {
            "active_subtask": {"task_id": "raw-task", "nested": state_nested},
            "query": "state query",
            "report_scope": {"year": 2024},
            "nested": state_nested,
        }
        projected_active = {
            "task_id": "projected-task",
            "query": "projected query",
            "operation_family": "lookup",
            "required_operands": [
                {
                    "label": "Metric",
                    "role": "component",
                    "concept": "revenue",
                    "nested": operand_nested,
                }
            ],
            "preferred_statement_types": ["statement"],
            "constraints": {"period_focus": "current"},
        }
        result = {
            "matched_operands": [
                {
                    "label": "Metric",
                    "role": "component",
                    "candidate_ids": ["candidate"],
                    "nested": row_nested,
                }
            ],
            "notes": ["existing"],
            "nested": row_nested,
        }
        candidates = [{"candidate_id": "candidate", "nested": state_nested}]
        state_before = deepcopy(state)
        result_before = deepcopy(result)
        candidates_before = deepcopy(candidates)
        events: List[Any] = []

        def active_owner(subtask: Dict[str, Any], received_state: Dict[str, Any]) -> Dict[str, Any]:
            events.append(("active", subtask, received_state))
            self.assertIsNot(subtask, state["active_subtask"])
            self.assertEqual(subtask, state["active_subtask"])
            self.assertIs(subtask["nested"], state_nested)
            self.assertIs(received_state, state)
            return projected_active

        def candidate_match(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
            events.append(("match", candidate, operand))
            self.assertIs(candidate, candidates[0])
            self.assertIsNot(operand, projected_active["required_operands"][0])
            self.assertEqual(operand, projected_active["required_operands"][0])
            self.assertIs(operand["nested"], operand_nested)
            return True

        def candidate_score(candidate: Dict[str, Any], **kwargs: Any) -> float:
            events.append(("score", candidate, kwargs))
            self.assertIs(candidate, candidates[0])
            self.assertEqual(kwargs["preferred_statement_types"], ["statement"])
            self.assertEqual(kwargs["constraints"], projected_active["constraints"])
            self.assertIsNot(kwargs["constraints"], projected_active["constraints"])
            self.assertEqual(kwargs["query_years"], [2024])
            self.assertEqual(kwargs["report_scope"], state["report_scope"])
            self.assertIsNot(kwargs["report_scope"], state["report_scope"])
            self.assertIs(kwargs["operand"], events[1][2])
            return 4.0

        def should_rerank(scored: List[Dict[str, Any]]) -> bool:
            events.append(("should", scored))
            self.assertEqual(len(scored), 1)
            self.assertIs(scored[0]["candidate"], candidates[0])
            self.assertEqual(scored[0]["score"], 4.0)
            return False

        with patch.object(
            graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            side_effect=active_owner,
        ), patch.object(
            graph_reconciliation,
            "_candidate_matches_operand",
            side_effect=candidate_match,
        ), patch.object(
            graph_reconciliation,
            "_score_operand_candidate",
            side_effect=candidate_score,
        ), patch.object(
            agent,
            "_should_llm_rerank_candidates",
            side_effect=should_rerank,
        ), patch.object(
            agent,
            "_llm_rerank_operand_candidates",
            side_effect=AssertionError("LLM rerank must stay lazy after false decision"),
        ):
            projected = agent._rerank_reconciliation_matches_with_llm(
                state,
                result,
                candidates,
                [2024],
            )

        self.assertEqual([event[0] for event in events], ["active", "match", "score", "should"])
        self.assertIsNot(projected, result)
        self.assertIsNot(projected["matched_operands"], result["matched_operands"])
        self.assertIsNot(projected["matched_operands"][0], result["matched_operands"][0])
        self.assertIs(projected["matched_operands"][0]["nested"], row_nested)
        self.assertEqual(projected["matched_operands"][0]["candidate_ids"], ["candidate"])
        self.assertEqual(projected["notes"], ["existing"])
        self.assertEqual(state, state_before)
        self.assertEqual(result, result_before)
        self.assertEqual(candidates, candidates_before)
        self.assertIs(state["nested"], state_nested)
        self.assertIs(result["nested"], row_nested)

        with patch.object(
            graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            side_effect=RuntimeError("active projection failed"),
        ), patch.object(
            graph_reconciliation,
            "_candidate_matches_operand",
            side_effect=AssertionError("candidate matching must stop"),
        ), patch.object(
            graph_reconciliation,
            "_score_operand_candidate",
            side_effect=AssertionError("candidate scoring must stop"),
        ), patch.object(
            agent,
            "_should_llm_rerank_candidates",
            side_effect=AssertionError("rerank decision must stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "active projection failed"):
                agent._rerank_reconciliation_matches_with_llm(
                    state,
                    result,
                    candidates,
                    [2024],
                )
        self.assertEqual(state, state_before)
        self.assertEqual(result, result_before)
        self.assertEqual(candidates, candidates_before)

    def test_current_source_sibling_surface_evidence_and_operand_callers_pin_gates_and_stop(self) -> None:
        from src.agent import financial_graph_reconciliation as graph_reconciliation
        from src.agent.financial_graph import FinancialAgent

        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"keep": True}
        evidence_state = {
            "reconciliation_result": {"status": "ready", "matched_operands": []},
            "active_subtask": {"task_id": "raw-task", "nested": nested},
            "report_scope": {},
            "nested": nested,
        }
        evidence_before = deepcopy(evidence_state)
        projected_active = {
            "task_id": "projected-task",
            "operation_family": "lookup",
            "required_operands": [],
            "constraints": {},
        }
        evidence_events: List[Any] = []

        def evidence_active(subtask: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
            evidence_events.append(("active", subtask, state))
            self.assertIsNot(subtask, evidence_state["active_subtask"])
            self.assertEqual(subtask, evidence_state["active_subtask"])
            self.assertIs(subtask["nested"], nested)
            self.assertIs(state, evidence_state)
            return projected_active

        def query_years(state: Dict[str, Any]) -> List[int]:
            evidence_events.append(("years", state))
            self.assertIs(state, evidence_state)
            return [2024]

        def candidates_owner(state: Dict[str, Any]) -> List[Dict[str, Any]]:
            evidence_events.append(("candidates", state))
            self.assertIs(state, evidence_state)
            return []

        with patch.object(
            graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            side_effect=evidence_active,
        ), patch.object(
            graph_reconciliation,
            "_query_years_from_state",
            side_effect=query_years,
        ), patch.object(
            agent,
            "_build_reconciliation_candidates",
            side_effect=candidates_owner,
        ), patch.object(
            agent,
            "_complete_required_operand_from_ontology",
            side_effect=AssertionError("empty projected operands must stay lazy"),
        ), patch.object(
            agent,
            "_expand_structured_candidate_ids",
            side_effect=AssertionError("lookup operation must skip artifact expansion"),
        ):
            self.assertEqual(
                agent._evidence_items_from_reconciliation_matches(evidence_state),
                [],
            )
        self.assertEqual([event[0] for event in evidence_events], ["active", "years", "candidates"])
        self.assertEqual(evidence_state, evidence_before)
        self.assertIs(evidence_state["nested"], nested)

        operand_state = {
            "reconciliation_result": {"status": "ready"},
            "active_subtask": {"task_id": "raw-task", "nested": nested},
            "nested": nested,
        }
        operand_before = deepcopy(operand_state)
        operand_events: List[Any] = []

        def operand_active(subtask: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
            operand_events.append(("active", subtask, state))
            self.assertIsNot(subtask, operand_state["active_subtask"])
            self.assertIs(subtask["nested"], nested)
            self.assertIs(state, operand_state)
            return {"required_operands": []}

        with patch.object(
            graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            side_effect=operand_active,
        ), patch.object(
            agent,
            "_complete_required_operand_from_ontology",
            side_effect=AssertionError("empty operands must stop ontology completion"),
        ), patch.object(
            graph_reconciliation,
            "_query_years_from_state",
            side_effect=AssertionError("empty operands must stop year resolution"),
        ), patch.object(
            agent,
            "_build_reconciliation_candidates",
            side_effect=AssertionError("empty operands must stop candidate construction"),
        ):
            self.assertEqual(
                agent._extract_structured_operands_from_reconciliation(operand_state),
                [],
            )
        self.assertEqual([event[0] for event in operand_events], ["active"])
        self.assertEqual(operand_state, operand_before)
        self.assertIs(operand_state["nested"], nested)

        with patch.object(
            graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            side_effect=RuntimeError("evidence active projection failed"),
        ), patch.object(
            graph_reconciliation,
            "_query_years_from_state",
            side_effect=AssertionError("evidence year resolution must stop"),
        ), patch.object(
            agent,
            "_build_reconciliation_candidates",
            side_effect=AssertionError("evidence candidates must stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "evidence active projection failed"):
                agent._evidence_items_from_reconciliation_matches(evidence_state)

        with patch.object(
            graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            side_effect=RuntimeError("operand active projection failed"),
        ), patch.object(
            agent,
            "_complete_required_operand_from_ontology",
            side_effect=AssertionError("operand ontology completion must stop"),
        ), patch.object(
            graph_reconciliation,
            "_query_years_from_state",
            side_effect=AssertionError("operand year resolution must stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "operand active projection failed"):
                agent._extract_structured_operands_from_reconciliation(operand_state)
        self.assertEqual(evidence_state, evidence_before)
        self.assertEqual(operand_state, operand_before)

    def test_current_source_dependency_reconciliation_caller_pins_order_adoption_and_stop(self) -> None:
        from src.agent import financial_graph_reconciliation as graph_reconciliation
        from src.agent.financial_graph import FinancialAgent

        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"keep": True}
        state = {
            "active_subtask": {"task_id": "raw-task", "operation_family": "ratio", "nested": nested},
            "tasks": [{"task_id": "raw-task", "nested": nested}],
            "artifacts": [],
            "reconciliation_retry_count": 0,
            "nested": nested,
        }
        state_before = deepcopy(state)
        projected_active = {"task_id": "projected-task", "operation_family": "ratio", "nested": nested}
        dependency_state = {
            "all_resolved": True,
            "bindings": [{"preferred_task_id": "source-task"}],
            "nested": nested,
        }
        resolved_result = {
            "status": "ready",
            "task_id": "projected-task",
            "matched_operands": [],
            "nested": nested,
        }
        evidence_refs = ["task_output:source-task"]
        ledger_tasks = [{"task_id": "projected-task", "status": "completed"}]
        ledger_artifacts = [{"artifact_id": "reconciliation:projected-task"}]
        events: List[Any] = []

        def active_owner(subtask: Dict[str, Any], received_state: Dict[str, Any]) -> Dict[str, Any]:
            events.append(("active", subtask, received_state))
            self.assertIsNot(subtask, state["active_subtask"])
            self.assertEqual(subtask, state["active_subtask"])
            self.assertIs(subtask["nested"], nested)
            self.assertIs(received_state, state)
            return projected_active

        def dependency_owner(received_state: Dict[str, Any]) -> Dict[str, Any]:
            events.append(("dependency", received_state))
            self.assertIs(received_state, state)
            return dependency_state

        def preference_owner(received_state: Dict[str, Any]) -> bool:
            events.append(("preference", received_state))
            self.assertIs(received_state, state)
            return True

        def result_owner(**kwargs: Any) -> Dict[str, Any]:
            events.append(("result", kwargs))
            self.assertIs(kwargs["active_subtask"], projected_active)
            self.assertIs(kwargs["dependency_state"], dependency_state)
            return resolved_result

        def refs_owner(received_result: Dict[str, Any]) -> List[str]:
            events.append(("refs", received_result))
            self.assertIs(received_result, resolved_result)
            return evidence_refs

        def ledger_owner(**kwargs: Any) -> Dict[str, Any]:
            events.append(("ledger", kwargs))
            self.assertIs(kwargs["active_subtask"], projected_active)
            self.assertIs(kwargs["reconciliation_result"], resolved_result)
            self.assertIs(kwargs["evidence_refs"], evidence_refs)
            self.assertEqual(kwargs["summary"], "reconciliation=ready(dependency_outputs)")
            return {"tasks": ledger_tasks, "artifacts": ledger_artifacts}

        with patch.object(
            graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            side_effect=active_owner,
        ), patch.object(
            agent,
            "_dependency_binding_resolution_state",
            side_effect=dependency_owner,
        ), patch.object(
            graph_reconciliation,
            "task_prefers_sibling_output_synthesis",
            side_effect=preference_owner,
        ), patch.object(
            graph_reconciliation,
            "dependency_resolved_reconciliation_result",
            side_effect=result_owner,
        ), patch.object(
            graph_reconciliation,
            "reconciliation_evidence_refs",
            side_effect=refs_owner,
        ), patch.object(
            graph_reconciliation,
            "_reconciliation_result_artifact_update",
            side_effect=ledger_owner,
        ), patch.object(
            agent,
            "_build_reconciliation_candidates",
            side_effect=AssertionError("dependency-ready path must skip candidates"),
        ):
            updates = agent._reconcile_retrieved_evidence(state)

        self.assertEqual(
            [event[0] for event in events],
            ["active", "dependency", "preference", "result", "refs", "ledger"],
        )
        self.assertIs(updates["reconciliation_result"], resolved_result)
        self.assertEqual(updates["tasks"], ledger_tasks)
        self.assertIsNot(updates["tasks"], ledger_tasks)
        self.assertIs(updates["tasks"][0], ledger_tasks[0])
        self.assertEqual(updates["artifacts"], ledger_artifacts)
        self.assertIsNot(updates["artifacts"], ledger_artifacts)
        self.assertIs(updates["artifacts"][0], ledger_artifacts[0])
        self.assertEqual(updates["retry_strategy"], "")
        self.assertEqual(updates["retry_queries"], [])
        self.assertEqual(updates["retry_reason"], "")
        self.assertEqual(state, state_before)
        self.assertIs(state["nested"], nested)

        with patch.object(
            graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            side_effect=RuntimeError("active owner failed"),
        ), patch.object(
            agent,
            "_dependency_binding_resolution_state",
            side_effect=AssertionError("dependency resolution must stop"),
        ), patch.object(
            graph_reconciliation,
            "task_prefers_sibling_output_synthesis",
            side_effect=AssertionError("preference must stop"),
        ), patch.object(
            graph_reconciliation,
            "dependency_resolved_reconciliation_result",
            side_effect=AssertionError("result projection must stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "active owner failed"):
                agent._reconcile_retrieved_evidence(state)

        failure_events: List[str] = []
        with patch.object(
            graph_reconciliation,
            "active_subtask_with_sibling_lookup_surfaces",
            side_effect=lambda subtask, received_state: failure_events.append("active") or projected_active,
        ), patch.object(
            agent,
            "_dependency_binding_resolution_state",
            side_effect=lambda received_state: failure_events.append("dependency") or dependency_state,
        ), patch.object(
            graph_reconciliation,
            "task_prefers_sibling_output_synthesis",
            side_effect=lambda received_state: failure_events.append("preference") or True,
        ), patch.object(
            graph_reconciliation,
            "dependency_resolved_reconciliation_result",
            side_effect=RuntimeError("result owner failed"),
        ), patch.object(
            graph_reconciliation,
            "reconciliation_evidence_refs",
            side_effect=AssertionError("evidence refs must stop"),
        ), patch.object(
            graph_reconciliation,
            "_reconciliation_result_artifact_update",
            side_effect=AssertionError("ledger must stop"),
        ):
            with self.assertRaisesRegex(RuntimeError, "result owner failed"):
                agent._reconcile_retrieved_evidence(state)
        self.assertEqual(failure_events, ["active", "dependency", "preference"])
        self.assertEqual(state, state_before)


if __name__ == "__main__":
    unittest.main()
