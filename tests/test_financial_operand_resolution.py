from __future__ import annotations

import re
import unittest
from collections.abc import Mapping
from copy import deepcopy
from itertools import permutations
from types import SimpleNamespace
from typing import Any, Dict, List
from unittest.mock import patch

import src.agent.financial_operand_resolution as operand_resolution
from src.agent.financial_graph_calculation import FinancialAgentCalculationMixin
from src.agent.financial_operand_resolution import (
    DirectStructuredPreferredSlotAdoptionInput,
    DirectStructuredOperandAcceptanceInput,
    RecoveredOperandContextAdoptionInput,
    RequiredOperandCandidateMergeInput,
    _evidence_item_for_operand_row,
    _evidence_items_by_id,
    _evidence_surface_contains_segment_label,
    _filter_operand_rows_by_required_surface_contract,
    _llm_lookup_operand_has_direct_support,
    _missing_required_operands,
    _operand_row_display_unit_set,
    _operand_row_conflicts_with_requirement,
    _operand_row_groups_collapse_to_same_slot,
    _operand_row_has_direct_evidence_surface,
    _operand_row_matches_requirement,
    _operand_row_satisfies_required_surface_contract,
    _operand_rows_conflict_by_required_role,
    _operand_rows_have_single_table_context,
    _period_comparison_operand_rows_collapse_to_same_slot,
    _ratio_operand_rows_collapse_to_same_slot,
    collect_retrieval_context_docs,
    collect_retrieved_operand_evidence_candidates,
    direct_lookup_row_is_ambiguous_context_table,
    merge_operand_rows,
    resolve_direct_structured_operand_acceptance,
    resolve_direct_structured_preferred_slot_adoption,
    resolve_recovered_operand_context_adoption,
    resolve_required_operand_candidate_merge,
    select_sibling_direct_operand_candidate,
    select_supplemental_operand_candidate,
)


def _doc(
    chunk_uid: str,
    text: str,
    *,
    anchor: str = "",
    object_id: str = "",
) -> SimpleNamespace:
    metadata: Dict[str, Any] = {}
    if chunk_uid:
        metadata["chunk_uid"] = chunk_uid
    if anchor:
        metadata["anchor"] = anchor
    return SimpleNamespace(
        page_content=text,
        metadata=metadata,
        id=object_id,
    )


def _candidate(
    evidence_id: str,
    source_anchor: str,
    *,
    row_text: str,
) -> Dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_anchor": source_anchor,
        "source_context": "context",
        "raw_row_text": row_text,
    }


def _operand_row(
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


def _merge_operand_row(
    candidate_id: str,
    *,
    label: str,
    concept: str,
    role: str,
    value: float,
    period: str = "2023",
    source_anchor: str = "",
    bind_explicitly: bool = True,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "evidence_id": candidate_id,
        "source_row_id": candidate_id,
        "source_row_ids": [candidate_id],
        "label": label,
        "period": period,
        "period_source": "evidence_surface",
        "raw_value": str(value),
        "raw_unit": "unit",
        "normalized_value": value,
        "normalized_unit": "KRW",
        "source_anchor": source_anchor or f"[{candidate_id}]",
        "table_source_id": "table_main",
        "consolidation_scope": "consolidated",
        "statement_type": "financial_statement",
    }
    if bind_explicitly:
        row.update(
            {
                "matched_operand_label": label,
                "matched_operand_concept": concept,
                "matched_operand_role": role,
            }
        )
    return row


class FinancialOperandResolutionTests(unittest.TestCase):
    def test_krw_raw_unit_repair_preserves_branch_identity_copy_and_mutation_contract(self) -> None:
        shared = {"preserve": True}
        rows = [
            {
                "operand_id": "non_krw",
                "normalized_unit": "COUNT",
                "raw_unit": "ignored",
                "raw_value": "ignored",
                "nested": shared,
            },
            {
                "operand_id": "small_distortion",
                "normalized_unit": "KRW",
                "normalized_value": 99.0,
                "raw_unit": "원",
                "raw_value": "small",
                "nested": shared,
            },
            {
                "operand_id": "boundary_repair",
                "normalized_unit": " krw ",
                "normalized_value": 10000.0,
                "raw_unit": "원",
                "raw_value": "boundary",
                "nested": shared,
            },
            {
                "operand_id": "trailing_unchanged",
                "normalized_unit": "COUNT",
                "raw_unit": "ignored",
                "raw_value": "ignored",
                "nested": shared,
            },
        ]
        original = deepcopy(rows)

        def normalize(raw_value, raw_unit):
            self.assertEqual(raw_unit, "원")
            return {
                "small": (1.0, "KRW"),
                "boundary": (100.0, "KRW"),
            }[raw_value]

        with patch.object(operand_resolution, "_normalise_operand_value", side_effect=normalize):
            repaired = operand_resolution.repair_krw_normalized_values_from_raw_units(rows)

        self.assertIsNot(repaired, rows)
        self.assertEqual([row["operand_id"] for row in repaired], [row["operand_id"] for row in rows])
        self.assertTrue(all(after is not before for after, before in zip(repaired, rows)))
        self.assertTrue(all(after["nested"] is shared for after in repaired))
        self.assertEqual(rows, original)
        self.assertEqual(
            {
                key: value
                for key, value in repaired[2].items()
                if original[2].get(key) != value
            },
            {
                "normalized_unit": "KRW",
                "source_normalized_value": 10000.0,
                "normalized_value": 100.0,
                "unit_normalization_repair_source": "raw_unit_scale",
            },
        )
        self.assertEqual(repaired[1], rows[1])

        unchanged = [
            {"normalized_unit": "COUNT", "raw_unit": "ignored", "raw_value": "ignored"},
            {"normalized_unit": "KRW", "raw_unit": "원", "raw_value": "equal", "normalized_value": 5.0},
            {"normalized_unit": "KRW", "raw_unit": "원", "raw_value": "zero", "normalized_value": 0.0},
            {"normalized_unit": "KRW", "raw_unit": "원", "raw_value": "expected_zero", "normalized_value": 9.0},
            {"normalized_unit": "KRW", "raw_unit": "원", "raw_value": "missing", "normalized_value": 9.0},
            {"normalized_unit": "KRW", "raw_unit": "원", "raw_value": "wrong_unit", "normalized_value": 9.0},
        ]
        unchanged_original = deepcopy(unchanged)
        unchanged_ids = [id(row) for row in unchanged]

        def unchanged_normalize(raw_value, _raw_unit):
            return {
                "equal": (5.0, "KRW"),
                "zero": (1.0, "KRW"),
                "expected_zero": (0.0, "KRW"),
                "missing": (None, "unit_bomb_is_not_read"),
                "wrong_unit": (1.0, "krw"),
            }[raw_value]

        with patch.object(operand_resolution, "_normalise_operand_value", side_effect=unchanged_normalize):
            same = operand_resolution.repair_krw_normalized_values_from_raw_units(unchanged)
            empty = []
            same_empty = operand_resolution.repair_krw_normalized_values_from_raw_units(empty)

        self.assertIs(same, unchanged)
        self.assertEqual([id(row) for row in same], unchanged_ids)
        self.assertEqual(unchanged, unchanged_original)
        self.assertIs(same_empty, empty)

    def test_krw_raw_unit_repair_preserves_access_laziness_and_exception_contract(self) -> None:
        events = []

        class Probe:
            def __init__(self, name, value, *, truth=True, float_error=None):
                self.name = name
                self.value = value
                self.truth = truth
                self.float_error = float_error

            def __bool__(self):
                events.append(("bool", self.name))
                return self.truth

            def __str__(self):
                events.append(("str", self.name))
                return str(self.value)

            def __float__(self):
                events.append(("float", self.name))
                if self.float_error is not None:
                    raise self.float_error(self.name)
                return float(self.value)

        class Bomb:
            def __getattribute__(self, name):
                if name.startswith("__"):
                    return object.__getattribute__(self, name)
                raise RuntimeError(f"unexpected access: {name}")

            def __bool__(self):
                raise RuntimeError("unexpected bool")

            def __str__(self):
                raise RuntimeError("unexpected str")

            def __float__(self):
                raise RuntimeError("unexpected float")

        class StrBomb:
            def __bool__(self):
                return True

            def __str__(self):
                raise RuntimeError("unexpected str")

        class ComparisonBomb:
            def __eq__(self, _other):
                raise RuntimeError("unexpected unit comparison")

            def __ne__(self, _other):
                raise RuntimeError("unexpected unit comparison")

        def spaces(value):
            events.append(("spaces", value))
            return value.strip()

        def normalize(raw_value, raw_unit):
            events.append(("normalize", raw_value, raw_unit))
            return Probe("expected", 100.0), "KRW"

        row = {
            "normalized_unit": Probe("normalized_unit", " krw "),
            "raw_unit": Probe("raw_unit", " 원 "),
            "result_unit": Bomb(),
            "raw_value": Probe("raw_value", " 100 "),
            "normalized_value": Probe("current", 10000.0),
        }
        with (
            patch.object(operand_resolution, "_normalise_spaces", side_effect=spaces),
            patch.object(operand_resolution, "_normalise_operand_value", side_effect=normalize),
        ):
            repaired = operand_resolution.repair_krw_normalized_values_from_raw_units([row])
        self.assertEqual(
            events,
            [
                ("bool", "normalized_unit"),
                ("str", "normalized_unit"),
                ("spaces", " krw "),
                ("bool", "raw_unit"),
                ("str", "raw_unit"),
                ("spaces", " 원 "),
                ("bool", "raw_value"),
                ("str", "raw_value"),
                ("spaces", " 100 "),
                ("normalize", "100", "원"),
                ("float", "current"),
                ("float", "expected"),
            ],
        )
        self.assertEqual(repaired[0]["normalized_value"], 100.0)

        non_krw_rows = [{
            "normalized_unit": "COUNT",
            "raw_unit": Bomb(),
            "result_unit": Bomb(),
            "raw_value": Bomb(),
        }]
        with patch.object(
            operand_resolution,
            "_normalise_operand_value",
            side_effect=AssertionError("non-KRW normalizer access"),
        ):
            self.assertIs(
                operand_resolution.repair_krw_normalized_values_from_raw_units(non_krw_rows),
                non_krw_rows,
            )

        blank_unit_rows = [{
            "normalized_unit": Probe("blank_unit_normalized", "KRW"),
            "raw_unit": Probe("blank_raw_unit", "", truth=False),
            "result_unit": Probe("blank_result_unit", "", truth=False),
            "raw_value": Probe("eager_raw_value", "7"),
            "normalized_value": Bomb(),
        }]
        events.clear()
        with patch.object(
            operand_resolution,
            "_normalise_operand_value",
            side_effect=AssertionError("blank-unit normalizer access"),
        ):
            self.assertIs(
                operand_resolution.repair_krw_normalized_values_from_raw_units(blank_unit_rows),
                blank_unit_rows,
            )
        self.assertIn(("bool", "eager_raw_value"), events)
        self.assertIn(("str", "eager_raw_value"), events)
        self.assertFalse(any(event[0] in {"normalize", "float"} for event in events))

        blank_value_rows = [{
            "normalized_unit": "KRW",
            "raw_unit": "원",
            "raw_value": Probe("blank_raw_value", "", truth=False),
            "normalized_value": Bomb(),
        }]
        events.clear()
        with patch.object(
            operand_resolution,
            "_normalise_operand_value",
            side_effect=AssertionError("blank-value normalizer access"),
        ):
            self.assertIs(
                operand_resolution.repair_krw_normalized_values_from_raw_units(blank_value_rows),
                blank_value_rows,
            )
        self.assertEqual([event for event in events if event[0] == "bool"], [("bool", "blank_raw_value")])
        self.assertFalse(any(event[0] in {"normalize", "float"} for event in events))

        wrong_unit_rows = [{
            "normalized_unit": "KRW",
            "raw_unit": "원",
            "raw_value": "1",
            "normalized_value": Bomb(),
        }]
        with patch.object(operand_resolution, "_normalise_operand_value", return_value=(1.0, "COUNT")):
            self.assertIs(
                operand_resolution.repair_krw_normalized_values_from_raw_units(wrong_unit_rows),
                wrong_unit_rows,
            )

        events.clear()
        current_bomb = Bomb()

        def no_value_normalizer(raw_value, raw_unit):
            events.append(("normalize", raw_value, raw_unit))
            return None, ComparisonBomb()

        fallback_row = {
            "normalized_unit": Probe("normalized_unit", "KRW"),
            "raw_unit": Probe("raw_unit", "", truth=False),
            "result_unit": Probe("result_unit", "원"),
            "raw_value": Probe("raw_value", "1"),
            "normalized_value": current_bomb,
        }
        fallback_rows = [fallback_row]
        with (
            patch.object(operand_resolution, "_normalise_spaces", side_effect=spaces),
            patch.object(operand_resolution, "_normalise_operand_value", side_effect=no_value_normalizer),
        ):
            same = operand_resolution.repair_krw_normalized_values_from_raw_units(fallback_rows)
        self.assertIs(same, fallback_rows)
        self.assertEqual(
            events,
            [
                ("bool", "normalized_unit"),
                ("str", "normalized_unit"),
                ("spaces", "KRW"),
                ("bool", "raw_unit"),
                ("bool", "result_unit"),
                ("str", "result_unit"),
                ("spaces", "원"),
                ("bool", "raw_value"),
                ("str", "raw_value"),
                ("spaces", "1"),
                ("normalize", "1", "원"),
            ],
        )

        for current_error, expected_error, expected_float_events in (
            (TypeError, RuntimeError, [("float", "current_soft")]),
            (None, ValueError, [("float", "current_soft"), ("float", "expected_soft")]),
        ):
            events.clear()
            current = Probe("current_soft", 10.0, float_error=current_error)
            expected = Probe("expected_soft", 1.0, float_error=expected_error)
            soft_rows = [{
                "normalized_unit": "KRW",
                "raw_unit": "원",
                "raw_value": "1",
                "normalized_value": current,
            }]
            with patch.object(
                operand_resolution,
                "_normalise_operand_value",
                return_value=(expected, "KRW"),
            ):
                self.assertIs(
                    operand_resolution.repair_krw_normalized_values_from_raw_units(soft_rows),
                    soft_rows,
                )
            self.assertEqual([event for event in events if event[0] == "float"], expected_float_events)

        class IterationBomb:
            def __iter__(self):
                raise RuntimeError("operand iteration")

        class CopyBomb(Mapping):
            def __getitem__(self, _key):
                raise AssertionError("unreachable")

            def __iter__(self):
                raise RuntimeError("row copy")

            def __len__(self):
                return 1

        with self.assertRaisesRegex(RuntimeError, "operand iteration"):
            operand_resolution.repair_krw_normalized_values_from_raw_units(IterationBomb())
        with self.assertRaisesRegex(RuntimeError, "row copy"):
            operand_resolution.repair_krw_normalized_values_from_raw_units([CopyBomb()])
        with self.assertRaisesRegex(RuntimeError, "unexpected bool"):
            operand_resolution.repair_krw_normalized_values_from_raw_units(
                [{"normalized_unit": Bomb()}]
            )
        with self.assertRaisesRegex(RuntimeError, "unexpected str"):
            operand_resolution.repair_krw_normalized_values_from_raw_units(
                [{"normalized_unit": StrBomb()}]
            )
        with (
            patch.object(operand_resolution, "_normalise_spaces", side_effect=RuntimeError("spaces")),
            self.assertRaisesRegex(RuntimeError, "spaces"),
        ):
            operand_resolution.repair_krw_normalized_values_from_raw_units(
                [{"normalized_unit": "KRW"}]
            )
        with (
            patch.object(
                operand_resolution,
                "_normalise_operand_value",
                side_effect=RuntimeError("normalizer"),
            ),
            self.assertRaisesRegex(RuntimeError, "normalizer"),
        ):
            operand_resolution.repair_krw_normalized_values_from_raw_units(
                [{"normalized_unit": "KRW", "raw_unit": "원", "raw_value": "1"}]
            )
        with (
            patch.object(
                operand_resolution,
                "_normalise_operand_value",
                return_value=(Probe("expected_runtime", 1.0), "KRW"),
            ),
            self.assertRaisesRegex(RuntimeError, "current_runtime"),
        ):
            operand_resolution.repair_krw_normalized_values_from_raw_units(
                [{
                    "normalized_unit": "KRW",
                    "raw_unit": "원",
                    "raw_value": "1",
                    "normalized_value": Probe("current_runtime", 10.0, float_error=RuntimeError),
                }]
            )
        with (
            patch.object(operand_resolution, "_normalise_operand_value", return_value=(1.0, "KRW")),
            patch("builtins.max", side_effect=RuntimeError("arithmetic")),
            self.assertRaisesRegex(RuntimeError, "arithmetic"),
        ):
            operand_resolution.repair_krw_normalized_values_from_raw_units(
                [{
                    "normalized_unit": "KRW",
                    "raw_unit": "원",
                    "raw_value": "1",
                    "normalized_value": 1000.0,
                }]
            )

    def test_growth_raw_scale_alignment_preserves_roles_threshold_identity_and_copy_contract(self) -> None:
        shared = {"preserve": True}
        rows = [
            {
                "operand_id": "prior",
                "matched_operand_role": "prior_period",
                "matched_operand_concept": "revenue",
                "raw_value": "1000",
                "raw_unit": "천원",
                "normalized_value": 1.0,
                "normalized_unit": "krw",
                "nested": shared,
            },
            {
                "operand_id": "current",
                "matched_operand_role": "current_period",
                "matched_operand_concept": "revenue",
                "raw_value": "2000",
                "raw_unit": "백만원",
                "normalized_value": 200.0,
                "normalized_unit": "KRW",
                "nested": shared,
            },
        ]
        original = deepcopy(rows)
        with (
            patch.object(operand_resolution, "_parse_number_text", side_effect=lambda value: float(value)),
            patch.object(
                operand_resolution,
                "_normalise_operand_value",
                return_value=(1_000_000.0, "KRW"),
            ) as normalizer,
        ):
            aligned = operand_resolution.align_growth_operand_units_when_raw_scale_matches(rows)

        self.assertIsNot(aligned, rows)
        self.assertIs(aligned[1], rows[1])
        self.assertIsNot(aligned[0], rows[0])
        self.assertIs(aligned[0]["nested"], shared)
        self.assertEqual(rows, original)
        normalizer.assert_called_once_with("1000", "백만원")
        self.assertEqual(
            {key: value for key, value in aligned[0].items() if original[0].get(key) != value},
            {
                "raw_unit": "백만원",
                "normalized_value": 1_000_000.0,
                "normalized_unit": "KRW",
                "unit_alignment_source": "growth_raw_scale_match",
            },
        )

        for role_pair, expected_prior_index in (
            (("", ""), 1),
            (("current_period", ""), 1),
            (("", "prior_period"), 1),
        ):
            inferred = [
                {
                    "operand_id": "current",
                    "matched_operand_role": role_pair[0],
                    "matched_operand_concept": "revenue",
                    "raw_value": "2000",
                    "raw_unit": "백만원",
                    "normalized_value": 200.0,
                    "normalized_unit": "KRW",
                },
                {
                    "operand_id": "prior",
                    "matched_operand_role": role_pair[1],
                    "matched_operand_concept": "revenue",
                    "raw_value": "1000",
                    "raw_unit": "천원",
                    "normalized_value": 1.0,
                    "normalized_unit": "KRW",
                },
            ]
            with (
                patch.object(operand_resolution, "_parse_number_text", side_effect=lambda value: float(value)),
                patch.object(operand_resolution, "_normalise_operand_value", return_value=(1_000_000.0, "KRW")),
            ):
                inferred_aligned = operand_resolution.align_growth_operand_units_when_raw_scale_matches(inferred)
            self.assertIsNot(inferred_aligned, inferred)
            self.assertIsNot(inferred_aligned[expected_prior_index], inferred[expected_prior_index])
            self.assertIs(inferred_aligned[1 - expected_prior_index], inferred[1 - expected_prior_index])

        class NoAccess:
            def get(self, *_args, **_kwargs):
                raise RuntimeError("row access")

        for short_rows in ([], [NoAccess()], [NoAccess(), NoAccess(), NoAccess()]):
            self.assertIs(
                operand_resolution.align_growth_operand_units_when_raw_scale_matches(short_rows),
                short_rows,
            )

    def test_growth_raw_scale_alignment_preserves_gate_access_laziness_and_exception_contract(self) -> None:
        class Bomb:
            def __bool__(self):
                raise RuntimeError("unexpected bool")

            def __str__(self):
                raise RuntimeError("unexpected str")

            def __float__(self):
                raise RuntimeError("unexpected float")

        class ComparisonBomb:
            def __eq__(self, _other):
                raise RuntimeError("unexpected comparison")

            def __ne__(self, _other):
                raise RuntimeError("unexpected comparison")

        def base_rows():
            return [
                {
                    "matched_operand_role": "current_period",
                    "matched_operand_concept": "revenue",
                    "raw_value": "2000",
                    "raw_unit": "백만원",
                    "normalized_value": 200.0,
                    "normalized_unit": "KRW",
                },
                {
                    "matched_operand_role": "prior_period",
                    "matched_operand_concept": "revenue",
                    "raw_value": "1000",
                    "raw_unit": "천원",
                    "normalized_value": 1.0,
                    "normalized_unit": "KRW",
                },
            ]

        access_events = []

        class TraceRow(Mapping):
            def __init__(self, name, data, *, copy_error=False):
                self.name = name
                self.data = data
                self.copy_error = copy_error

            def get(self, key, default=None):
                access_events.append(("get", self.name, key))
                return self.data.get(key, default)

            def __iter__(self):
                access_events.append(("copy", self.name))
                if self.copy_error:
                    raise RuntimeError(f"{self.name} copy")
                return iter(self.data)

            def __getitem__(self, key):
                return self.data[key]

            def __len__(self):
                return len(self.data)

        traced_current = TraceRow(
            "current",
            {
                **base_rows()[0],
                "matched_operand_concept": "revenue",
                "raw_unit": Bomb(),
            },
        )
        traced_prior = TraceRow(
            "prior",
            {
                **base_rows()[1],
                "matched_operand_concept": "profit",
                "raw_unit": Bomb(),
            },
        )
        traced_rows = [traced_current, traced_prior]
        self.assertIs(
            operand_resolution.align_growth_operand_units_when_raw_scale_matches(traced_rows),
            traced_rows,
        )
        self.assertEqual(
            [event for event in access_events if event[0] == "copy" or event[2] == "matched_operand_role"],
            [
                ("get", "current", "matched_operand_role"),
                ("get", "current", "matched_operand_role"),
                ("get", "prior", "matched_operand_role"),
                ("copy", "current"),
                ("copy", "prior"),
            ],
        )

        access_events.clear()
        copy_bomb_rows = [
            TraceRow("current", base_rows()[0]),
            TraceRow("prior", base_rows()[1], copy_error=True),
        ]
        with self.assertRaisesRegex(RuntimeError, "prior copy"):
            operand_resolution.align_growth_operand_units_when_raw_scale_matches(copy_bomb_rows)
        self.assertEqual(
            [event for event in access_events if event[0] == "copy"],
            [("copy", "current"), ("copy", "prior")],
        )

        mismatch = base_rows()
        mismatch[1]["matched_operand_concept"] = "profit"
        mismatch[0]["raw_unit"] = Bomb()
        self.assertIs(operand_resolution.align_growth_operand_units_when_raw_scale_matches(mismatch), mismatch)

        equal_units = base_rows()
        equal_units[1]["raw_unit"] = "백만원"
        equal_units[0]["normalized_unit"] = Bomb()
        self.assertIs(
            operand_resolution.align_growth_operand_units_when_raw_scale_matches(equal_units),
            equal_units,
        )

        non_krw = base_rows()
        non_krw[0]["normalized_unit"] = "COUNT"
        non_krw[1]["normalized_unit"] = Bomb()
        self.assertIs(operand_resolution.align_growth_operand_units_when_raw_scale_matches(non_krw), non_krw)

        blank_concept = base_rows()
        blank_concept[0]["matched_operand_concept"] = ""
        with (
            patch.object(operand_resolution, "_parse_number_text", side_effect=[2.0, 1.0]),
            patch.object(operand_resolution, "_normalise_operand_value", return_value=(7.0, "KRW")),
        ):
            self.assertIsNot(
                operand_resolution.align_growth_operand_units_when_raw_scale_matches(blank_concept),
                blank_concept,
            )

        blank_unit = base_rows()
        blank_unit[1]["raw_unit"] = ""
        with patch.object(operand_resolution, "_parse_number_text", side_effect=AssertionError("raw parse")):
            self.assertIs(
                operand_resolution.align_growth_operand_units_when_raw_scale_matches(blank_unit),
                blank_unit,
            )

        prior_non_krw = base_rows()
        prior_non_krw[1]["normalized_unit"] = "COUNT"
        with patch.object(operand_resolution, "_parse_number_text", side_effect=AssertionError("raw parse")):
            self.assertIs(
                operand_resolution.align_growth_operand_units_when_raw_scale_matches(prior_non_krw),
                prior_non_krw,
            )

        parse_events = []
        missing_raw = base_rows()
        missing_raw[0]["normalized_value"] = None
        with patch.object(
            operand_resolution,
            "_parse_number_text",
            side_effect=lambda value: (parse_events.append(value) or (None if value == "2000" else 1.0)),
        ):
            self.assertIs(
                operand_resolution.align_growth_operand_units_when_raw_scale_matches(missing_raw),
                missing_raw,
            )
        self.assertEqual(parse_events, ["2000", "1000"])

        for missing_index in (0, 1):
            missing_normalized = base_rows()
            missing_normalized[missing_index]["normalized_value"] = None
            with patch.object(operand_resolution, "_parse_number_text", side_effect=[2.0, 1.0]):
                self.assertIs(
                    operand_resolution.align_growth_operand_units_when_raw_scale_matches(missing_normalized),
                    missing_normalized,
                )

        zero_ratio = base_rows()
        zero_ratio[0]["normalized_value"] = 0.0
        with patch.object(operand_resolution, "_parse_number_text", side_effect=[2.0, 1.0]):
            self.assertIs(
                operand_resolution.align_growth_operand_units_when_raw_scale_matches(zero_ratio),
                zero_ratio,
            )

        value_events = []

        class ValueProbe:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __bool__(self):
                value_events.append(("bool", self.name))
                return True

            def __str__(self):
                value_events.append(("str", self.name))
                return self.value

        repeated_prior = base_rows()
        repeated_prior[0]["raw_unit"] = ValueProbe("current_unit", "백만원")
        repeated_prior[1]["raw_unit"] = ValueProbe("prior_unit", "천원")
        repeated_prior[0]["raw_value"] = ValueProbe("current_raw", "2000")
        repeated_prior[1]["raw_value"] = ValueProbe("prior_raw", "1000")
        with (
            patch.object(operand_resolution, "_parse_number_text", side_effect=lambda value: float(value)),
            patch.object(operand_resolution, "_normalise_operand_value", return_value=(7.0, "KRW")),
        ):
            self.assertIsNot(
                operand_resolution.align_growth_operand_units_when_raw_scale_matches(repeated_prior),
                repeated_prior,
            )
        self.assertEqual(
            [event for event in value_events if event[0] == "str"],
            [
                ("str", "current_unit"),
                ("str", "prior_unit"),
                ("str", "current_raw"),
                ("str", "prior_raw"),
                ("str", "prior_raw"),
            ],
        )

        for current_raw, prior_raw, current_normalized, prior_normalized, should_align in (
            (0.009, 1.0, 1.0, 1.0, False),
            (0.01, 1.0, 1.0, 1.0, True),
            (1.0, 100.0, 100.0, 1.0, True),
            (100.0, 1.0, 1.0, 100.0, True),
            (100.01, 1.0, 1.0, 100.0, False),
            (2.0, 1.0, 198.0, 1.0, False),
        ):
            threshold_rows = base_rows()
            threshold_rows[0]["normalized_value"] = current_normalized
            threshold_rows[1]["normalized_value"] = prior_normalized
            with (
                patch.object(
                    operand_resolution,
                    "_parse_number_text",
                    side_effect=[current_raw, prior_raw],
                ),
                patch.object(operand_resolution, "_normalise_operand_value", return_value=(7.0, "KRW")),
            ):
                result = operand_resolution.align_growth_operand_units_when_raw_scale_matches(threshold_rows)
            self.assertEqual(result is not threshold_rows, should_align)

        for current_raw, prior_raw, current_normalized, prior_normalized in (
            (TypeError("raw"), 1.0, 100.0, 1.0),
            (1.0, 0.0, 100.0, 1.0),
            (1.0, 1.0, ValueError("normalized"), 1.0),
        ):
            caught_rows = base_rows()
            caught_rows[0]["normalized_value"] = current_normalized
            caught_rows[1]["normalized_value"] = prior_normalized

            class FloatValue:
                def __init__(self, value):
                    self.value = value

                def __bool__(self):
                    return True

                def __float__(self):
                    if isinstance(self.value, BaseException):
                        raise self.value
                    return float(self.value)

            with patch.object(
                operand_resolution,
                "_parse_number_text",
                side_effect=[FloatValue(current_raw), FloatValue(prior_raw)],
            ):
                if isinstance(current_normalized, BaseException):
                    caught_rows[0]["normalized_value"] = FloatValue(current_normalized)
                self.assertIs(
                    operand_resolution.align_growth_operand_units_when_raw_scale_matches(caught_rows),
                    caught_rows,
                )

        owner_gate_rows = base_rows()
        with (
            patch.object(operand_resolution, "_parse_number_text", side_effect=[2.0, 1.0]),
            patch.object(operand_resolution, "_normalise_operand_value", return_value=(None, ComparisonBomb())),
        ):
            self.assertIs(
                operand_resolution.align_growth_operand_units_when_raw_scale_matches(owner_gate_rows),
                owner_gate_rows,
            )
        with (
            patch.object(operand_resolution, "_parse_number_text", side_effect=[2.0, 1.0]),
            patch.object(operand_resolution, "_normalise_operand_value", return_value=(7.0, "COUNT")),
        ):
            self.assertIs(
                operand_resolution.align_growth_operand_units_when_raw_scale_matches(owner_gate_rows),
                owner_gate_rows,
            )
        with (
            patch.object(operand_resolution, "_parse_number_text", side_effect=[2.0, 1.0]),
            patch.object(operand_resolution, "_normalise_operand_value", side_effect=RuntimeError("owner")),
            self.assertRaisesRegex(RuntimeError, "owner"),
        ):
            operand_resolution.align_growth_operand_units_when_raw_scale_matches(base_rows())
        with (
            patch.object(operand_resolution, "_parse_number_text", side_effect=RuntimeError("parse")),
            self.assertRaisesRegex(RuntimeError, "parse"),
        ):
            operand_resolution.align_growth_operand_units_when_raw_scale_matches(base_rows())
        with (
            patch.object(operand_resolution, "_normalise_spaces", side_effect=RuntimeError("spaces")),
            self.assertRaisesRegex(RuntimeError, "spaces"),
        ):
            operand_resolution.align_growth_operand_units_when_raw_scale_matches(base_rows())

        class StrBomb:
            def __bool__(self):
                return True

            def __str__(self):
                raise RuntimeError("string")

        string_rows = base_rows()
        string_rows[0]["matched_operand_role"] = StrBomb()
        with self.assertRaisesRegex(RuntimeError, "string"):
            operand_resolution.align_growth_operand_units_when_raw_scale_matches(string_rows)

    def test_growth_period_conflict_preserves_scan_copy_period_and_mutation_contract(self) -> None:
        class NoAccess:
            def get(self, *_args, **_kwargs):
                raise AssertionError("row access")

            def __iter__(self):
                raise AssertionError("row iteration")

        for short_rows in ([], [NoAccess()], [NoAccess(), NoAccess(), NoAccess()]):
            self.assertFalse(operand_resolution.growth_operand_periods_conflict(short_rows))

        events: List[Any] = []

        class TraceRow(Mapping):
            def __init__(self, name: str, values: Dict[str, Any]):
                self.name = name
                self.values = values

            def __getitem__(self, key):
                events.append((self.name, "item", key))
                return self.values[key]

            def __iter__(self):
                return iter(self.values)

            def __len__(self):
                return len(self.values)

            def get(self, key, default=None):
                events.append((self.name, "get", key))
                return self.values.get(key, default)

            def keys(self):
                events.append((self.name, "copy"))
                return self.values.keys()

        class LabelBomb:
            def __str__(self):
                raise AssertionError("truthy period must skip label")

        shared = {"nested": True}
        current_values = {
            "matched_operand_role": "current_period",
            "period": "2024",
            "label": LabelBomb(),
            "nested": shared,
        }
        prior_values = {
            "matched_operand_role": "prior_period",
            "period": "",
            "label": " 2024 ",
            "nested": shared,
        }
        current_snapshot = dict(current_values)
        prior_snapshot = dict(prior_values)

        def period_key(value):
            events.append(("period_key", value))
            return value.strip()

        with patch.object(operand_resolution, "period_match_key", side_effect=period_key) as key_owner:
            self.assertTrue(
                operand_resolution.growth_operand_periods_conflict(
                    [TraceRow("current", current_values), TraceRow("prior", prior_values)]
                )
            )

        self.assertEqual(
            [event for event in events if event[1:2] in [("get",), ("copy",)] and event[-1:] != ("period",)],
            [
                ("current", "get", "matched_operand_role"),
                ("current", "copy"),
                ("current", "get", "matched_operand_role"),
                ("prior", "get", "matched_operand_role"),
                ("prior", "copy"),
            ],
        )
        self.assertEqual([call.args for call in key_owner.call_args_list], [("2024",), (" 2024 ",)])
        self.assertEqual(current_values, current_snapshot)
        self.assertEqual(prior_values, prior_snapshot)
        self.assertIs(current_values["nested"], shared)
        self.assertIs(prior_values["nested"], shared)

        different = [
            {"matched_operand_role": "current_period", "period": "2024"},
            {"matched_operand_role": "prior_period", "period": "2023"},
        ]
        with patch.object(operand_resolution, "period_match_key", side_effect=lambda value: value):
            self.assertFalse(operand_resolution.growth_operand_periods_conflict(different))

        missing_prior = [
            {"matched_operand_role": "current_period", "period": "2024"},
            {"matched_operand_role": "current_period", "period": "2023"},
        ]
        with patch.object(
            operand_resolution,
            "period_match_key",
            side_effect=AssertionError("period owner access"),
        ):
            self.assertFalse(operand_resolution.growth_operand_periods_conflict(missing_prior))

        missing_current = [
            {"matched_operand_role": "prior_period", "period": "2024"},
            {"matched_operand_role": "prior_period", "period": "2023"},
        ]
        with patch.object(
            operand_resolution,
            "period_match_key",
            side_effect=AssertionError("period owner access"),
        ):
            self.assertFalse(operand_resolution.growth_operand_periods_conflict(missing_current))

    def test_growth_period_conflict_preserves_lazy_truth_and_exception_contract(self) -> None:
        class StrBomb:
            def __str__(self):
                raise RuntimeError("string")

        def rows(*, current_period="2024", prior_period="2024", current_label="", prior_label=""):
            return [
                {
                    "matched_operand_role": "current_period",
                    "period": current_period,
                    "label": current_label,
                },
                {
                    "matched_operand_role": "prior_period",
                    "period": prior_period,
                    "label": prior_label,
                },
            ]

        with patch.object(operand_resolution, "period_match_key", side_effect=lambda value: value):
            self.assertTrue(
                operand_resolution.growth_operand_periods_conflict(
                    rows(current_label=StrBomb(), prior_label=StrBomb())
                )
            )

        with patch.object(operand_resolution, "period_match_key", side_effect=lambda value: value.strip()) as key_owner:
            self.assertTrue(
                operand_resolution.growth_operand_periods_conflict(
                    rows(current_period="", prior_period="", current_label=" 2024 ", prior_label="2024")
                )
            )
        self.assertEqual([call.args for call in key_owner.call_args_list], [(" 2024 ",), ("2024",)])

        truth_events: List[str] = []

        class TruthProbe:
            def __init__(self, name: str, truth: bool):
                self.name = name
                self.truth = truth

            def __bool__(self):
                truth_events.append(self.name)
                return self.truth

        current_falsy = TruthProbe("current", False)
        prior_unread = TruthProbe("prior", True)
        with patch.object(operand_resolution, "period_match_key", side_effect=[current_falsy, prior_unread]) as key_owner:
            self.assertFalse(operand_resolution.growth_operand_periods_conflict(rows()))
        self.assertEqual(key_owner.call_count, 2)
        self.assertEqual(truth_events, ["current", "current"])

        truth_events.clear()
        with patch.object(
            operand_resolution,
            "period_match_key",
            side_effect=[TruthProbe("current", True), TruthProbe("prior", False)],
        ):
            self.assertFalse(operand_resolution.growth_operand_periods_conflict(rows()))
        self.assertEqual(truth_events, ["current", "prior", "prior"])

        class EqualityResult:
            def __bool__(self):
                truth_events.append("result")
                return True

        class EqualityProbe(TruthProbe):
            def __eq__(self, _other):
                truth_events.append("equal")
                return EqualityResult()

        truth_events.clear()
        with patch.object(
            operand_resolution,
            "period_match_key",
            side_effect=[EqualityProbe("current", True), TruthProbe("prior", True)],
        ):
            self.assertTrue(operand_resolution.growth_operand_periods_conflict(rows()))
        self.assertEqual(truth_events, ["current", "prior", "equal", "result"])

        class AccessBomb:
            def get(self, *_args, **_kwargs):
                raise RuntimeError("mapping")

        with self.assertRaisesRegex(RuntimeError, "mapping"):
            operand_resolution.growth_operand_periods_conflict([AccessBomb(), {}])

        class CopyBomb(Mapping):
            def __getitem__(self, key):
                if key == "matched_operand_role":
                    return "current_period"
                raise KeyError(key)

            def __iter__(self):
                return iter(("matched_operand_role",))

            def __len__(self):
                return 1

            def get(self, key, default=None):
                return "current_period" if key == "matched_operand_role" else default

            def keys(self):
                raise RuntimeError("copy")

        with self.assertRaisesRegex(RuntimeError, "copy"):
            operand_resolution.growth_operand_periods_conflict(
                [CopyBomb(), {"matched_operand_role": "prior_period", "period": "2024"}]
            )

        role_string_rows = rows()
        role_string_rows[0]["matched_operand_role"] = StrBomb()
        with self.assertRaisesRegex(RuntimeError, "string"):
            operand_resolution.growth_operand_periods_conflict(role_string_rows)

        with self.assertRaisesRegex(RuntimeError, "string"):
            operand_resolution.growth_operand_periods_conflict(rows(current_period=StrBomb()))

        with (
            patch.object(operand_resolution, "period_match_key", side_effect=RuntimeError("period owner")),
            self.assertRaisesRegex(RuntimeError, "period owner"),
        ):
            operand_resolution.growth_operand_periods_conflict(rows())

        class BoolBomb:
            def __bool__(self):
                raise RuntimeError("truth")

        with self.assertRaisesRegex(RuntimeError, "truth"):
            operand_resolution.growth_operand_periods_conflict(rows(current_period=BoolBomb()))

        with (
            patch.object(operand_resolution, "period_match_key", side_effect=[BoolBomb(), "2024"]),
            self.assertRaisesRegex(RuntimeError, "truth"),
        ):
            operand_resolution.growth_operand_periods_conflict(rows())

        class EqualityBomb:
            def __bool__(self):
                return True

            def __eq__(self, _other):
                raise RuntimeError("equality")

        with (
            patch.object(operand_resolution, "period_match_key", side_effect=[EqualityBomb(), EqualityBomb()]),
            self.assertRaisesRegex(RuntimeError, "equality"),
        ):
            operand_resolution.growth_operand_periods_conflict(rows())

    def test_operation_sign_policy_preserves_identity_and_applies_ontology_override(self) -> None:
        class IterationBomb(list):
            def __iter__(self):
                raise AssertionError("rows must stay untouched on the non-ratio gate")

        family_bomb = object()
        normalize_calls: List[Any] = []

        def normalize(value: Any) -> str:
            normalize_calls.append(value)
            if value is family_bomb:
                raise AssertionError("ratio operation must skip operation_family")
            return str(value).strip()

        empty_operands: List[Dict[str, Any]] = []
        with patch.object(operand_resolution, "_normalise_spaces", side_effect=normalize):
            ratio_empty = operand_resolution.apply_operation_sign_policy(
                empty_operands,
                operation="ratio",
                operation_family=family_bomb,
            )
            family_ratio = operand_resolution.apply_operation_sign_policy(
                empty_operands,
                operation="lookup",
                operation_family="ratio",
            )
            gated_operands = IterationBomb([{"normalized_value": -1.0}])
            non_ratio = operand_resolution.apply_operation_sign_policy(
                gated_operands,
                operation="lookup",
                operation_family="lookup",
            )

        self.assertIs(ratio_empty, empty_operands)
        self.assertIs(family_ratio, empty_operands)
        self.assertIs(non_ratio, gated_operands)
        self.assertEqual(
            normalize_calls,
            ["ratio", "lookup", "ratio", "lookup", "lookup"],
        )

        ontology_calls: List[str] = []

        class Ontology:
            def binding_policy_for_concept(self, concept: str) -> Dict[str, Any]:
                ontology_calls.append(concept)
                return {
                    "ratio_denominator_sign": "signed",
                    "ontology_only": "kept",
                }

        nested = {"source": ["ev_denominator"]}
        operands = [
            {
                "operand_id": "numerator",
                "matched_operand_role": "numerator_1",
                "matched_operand_concept": "operating_income",
                "normalized_value": 300.0,
                "metadata": {"source": ["ev_numerator"]},
            },
            {
                "operand_id": "denominator",
                "role": "denominator_1",
                "concept": "interest_expense",
                "normalized_value": -100.0,
                "binding_policy": {
                    "ratio_denominator_sign": "magnitude",
                    "row_only": True,
                },
                "metadata": nested,
            },
        ]
        original = deepcopy(operands)
        with patch.object(operand_resolution, "get_financial_ontology", return_value=Ontology()):
            updated = operand_resolution.apply_operation_sign_policy(
                operands,
                operation="ratio",
                operation_family="ratio",
            )

        self.assertIsNot(updated, operands)
        self.assertEqual([row["operand_id"] for row in updated], ["numerator", "denominator"])
        self.assertIsNot(updated[0], operands[0])
        self.assertIsNot(updated[1], operands[1])
        self.assertIs(updated[1]["metadata"], nested)
        self.assertEqual(updated[1]["normalized_value"], 100.0)
        self.assertEqual(updated[1]["source_normalized_value"], -100.0)
        self.assertEqual(updated[1]["sign_policy_applied"], "ratio_denominator_magnitude")
        self.assertEqual(
            updated[1]["binding_policy"],
            {
                "ratio_denominator_sign": "magnitude",
                "ontology_only": "kept",
                "row_only": True,
            },
        )
        self.assertEqual(ontology_calls, ["interest_expense"])
        self.assertEqual(operands, original)

        for value in (None, "not-a-number", object(), 0, 2.5, float("nan")):
            with self.subTest(value=value):
                unchanged = [
                    {
                        "matched_operand_role": "denominator",
                        "binding_policy": {"ratio_denominator_sign": "magnitude"},
                        "normalized_value": value,
                    }
                ]
                result = operand_resolution.apply_operation_sign_policy(
                    unchanged,
                    operation="ratio",
                    operation_family="",
                )
                self.assertIs(result, unchanged)
                self.assertIs(result[0], unchanged[0])

        class StringBomb:
            def __str__(self) -> str:
                raise AssertionError("truthy matched fields must skip fallbacks")

        lazy_fallback_row = {
            "matched_operand_role": "denominator",
            "role": StringBomb(),
            "matched_operand_concept": "interest_expense",
            "concept": StringBomb(),
            "binding_policy": {"ratio_denominator_sign": "magnitude"},
            "normalized_value": -2.0,
        }
        lazy_result = operand_resolution.apply_operation_sign_policy(
            [lazy_fallback_row],
            operation="ratio",
            operation_family="",
        )
        self.assertEqual(lazy_result[0]["normalized_value"], 2.0)

        blank_concept_row = {
            "matched_operand_role": "denominator",
            "binding_policy": {"ratio_denominator_sign": "magnitude"},
            "normalized_value": -3.0,
        }
        with patch.object(
            operand_resolution,
            "get_financial_ontology",
            side_effect=AssertionError("blank concept must skip ontology"),
        ):
            blank_concept_result = operand_resolution.apply_operation_sign_policy(
                [blank_concept_row],
                operation="ratio",
                operation_family="ratio",
            )
        self.assertEqual(blank_concept_result[0]["normalized_value"], 3.0)

    def test_operation_sign_policy_access_and_exception_boundaries(self) -> None:
        events: List[str] = []

        class TrackedText:
            def __init__(self, name: str, value: str) -> None:
                self.name = name
                self.value = value

            def __str__(self) -> str:
                events.append(f"str:{self.name}")
                return self.value

        class TrackedFloat:
            def __float__(self) -> float:
                events.append("float:value")
                return -4.0

        class TrackedPolicy(Mapping):
            def __init__(self) -> None:
                self.values = {
                    "ratio_denominator_sign": TrackedText("row-sign", "magnitude"),
                    "row_only": True,
                }

            def __iter__(self):
                events.append("policy:copy")
                return iter(self.values)

            def __len__(self) -> int:
                return len(self.values)

            def __getitem__(self, key: str) -> Any:
                return self.values[key]

        class Ontology:
            def binding_policy_for_concept(self, concept: str) -> Dict[str, Any]:
                events.append(f"ontology:{concept}")
                return ontology_policy

        ontology_policy = {
            "ratio_denominator_sign": TrackedText("ontology-sign", "signed"),
            "ontology_only": ["retained"],
        }
        ontology_sign = ontology_policy["ratio_denominator_sign"]
        ontology_only = ontology_policy["ontology_only"]

        row = {
            "matched_operand_role": TrackedText("role", "denominator_main"),
            "matched_operand_concept": TrackedText("concept", "interest_expense"),
            "binding_policy": TrackedPolicy(),
            "normalized_value": TrackedFloat(),
        }
        with patch.object(operand_resolution, "get_financial_ontology", return_value=Ontology()):
            updated = operand_resolution.apply_operation_sign_policy(
                [row],
                operation="ratio",
                operation_family="ignored",
            )

        milestones = [
            event
            for event in events
            if event
            in {
                "str:role",
                "policy:copy",
                "str:concept",
                "ontology:interest_expense",
                "str:row-sign",
                "float:value",
            }
        ]
        self.assertEqual(
            milestones,
            [
                "str:role",
                "policy:copy",
                "str:concept",
                "ontology:interest_expense",
                "str:row-sign",
                "float:value",
            ],
        )
        self.assertEqual(updated[0]["normalized_value"], 4.0)
        self.assertEqual(updated[0]["binding_policy"]["ontology_only"], ["retained"])
        self.assertTrue(updated[0]["binding_policy"]["row_only"])
        self.assertIs(ontology_policy["ratio_denominator_sign"], ontology_sign)
        self.assertIs(ontology_policy["ontology_only"], ontology_only)
        self.assertEqual(set(ontology_policy), {"ratio_denominator_sign", "ontology_only"})

        class RuntimeFloat:
            def __float__(self) -> float:
                raise RuntimeError("float-stage")

        propagating_cases = (
            (
                "normalizer",
                patch.object(operand_resolution, "_normalise_spaces", side_effect=RuntimeError("normalize-stage")),
                [{"matched_operand_role": "denominator", "normalized_value": -1.0}],
            ),
            (
                "ontology",
                patch.object(operand_resolution, "get_financial_ontology", side_effect=RuntimeError("ontology-stage")),
                [
                    {
                        "matched_operand_role": "denominator",
                        "matched_operand_concept": "interest_expense",
                        "normalized_value": -1.0,
                    }
                ],
            ),
            (
                "float",
                patch.object(operand_resolution, "get_financial_ontology"),
                [
                    {
                        "matched_operand_role": "denominator",
                        "binding_policy": {"ratio_denominator_sign": "magnitude"},
                        "normalized_value": RuntimeFloat(),
                    }
                ],
            ),
        )
        for name, active_patch, operands in propagating_cases:
            with self.subTest(stage=name), active_patch:
                with self.assertRaises(RuntimeError):
                    operand_resolution.apply_operation_sign_policy(
                        operands,
                        operation="ratio",
                        operation_family="ratio",
                    )

    def test_evidence_local_unit_and_period_behavior_matrix(self) -> None:
        coerce_unit = operand_resolution.coerce_operand_unit_from_evidence
        coerce_period = operand_resolution.coerce_operand_period_from_evidence_surface

        class MissingGroupMatch:
            def end(self, _group_name: str) -> int:
                raise IndexError("missing group")

        class PolicyBomb(Mapping):
            def __getitem__(self, _key: str) -> Any:
                raise AssertionError("policy must stay lazy")

            def __iter__(self):
                raise AssertionError("policy must stay lazy")

            def __len__(self) -> int:
                raise AssertionError("policy must stay lazy")

        with patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", PolicyBomb()):
            self.assertTrue(
                operand_resolution._inline_unit_match_has_right_boundary(
                    "unit suffix",
                    MissingGroupMatch(),
                )
            )
            end_match = re.search(r"(?P<unit>unit)", "unit")
            self.assertIsNotNone(end_match)
            self.assertTrue(
                operand_resolution._inline_unit_match_has_right_boundary(
                    "unit",
                    end_match,
                )
            )

        unit_cases = [
            ("not numeric", "  원 ", None, "원"),
            ("not numeric", "", {"metadata": {"unit_hint": " 백만원 "}}, "백만원"),
            ("not numeric", "KRW", {"metadata": {"unit_hint": " krw "}}, "KRW"),
            ("1,000", "원", {"metadata": {"unit_hint": "백만원"}}, "백만원"),
            ("about 1,000", "원", {"metadata": {"unit_hint": "백만원"}}, "원"),
            ("100", "개", {"claim": "100원"}, "원"),
            ("100", "", {"source_context": "100원"}, "원"),
            ("100", "개", {"source_context": "100원"}, "개"),
            ("100", "백만원", {"source_context": "100원"}, "원"),
            ("100", "", {"metadata": {"unit_hint": "%"}, "source_context": "100원"}, "%"),
            ("100", "", {"claim": "100억"}, "억원"),
            ("100", "개", {"claim": "100원화"}, "개"),
            ("100", "개", {"claim": "100원이 지급됐다"}, "원"),
        ]
        for raw_value, raw_unit, evidence_item, expected in unit_cases:
            with self.subTest(raw_value=raw_value, raw_unit=raw_unit, evidence=evidence_item):
                self.assertEqual(
                    coerce_unit(
                        raw_value=raw_value,
                        raw_unit=raw_unit,
                        evidence_item=evidence_item,
                    ),
                    expected,
                )

        unit_evidence = {
            "claim": "100원",
            "metadata": {"unit_hint": "백만원", "nested": {"kept": True}},
        }
        unit_evidence_snapshot = deepcopy(unit_evidence)
        nested_metadata = unit_evidence["metadata"]["nested"]
        self.assertEqual(
            coerce_unit(
                raw_value="100",
                raw_unit="개",
                evidence_item=unit_evidence,
            ),
            "원",
        )
        self.assertEqual(unit_evidence, unit_evidence_snapshot)
        self.assertIs(unit_evidence["metadata"]["nested"], nested_metadata)

        nested = {"kept": True}
        same_period = {"period": "2022년", "label": "metric", "nested": nested}
        self.assertIs(
            coerce_period(
                same_period,
                {"claim": "2022년 metric", "quote_span": "2023년 comparison"},
            ),
            same_period,
        )
        self.assertIs(
            coerce_period(
                same_period,
                {"claim": "2022년 metric and 2022년 repeated"},
            ),
            same_period,
        )
        non_year_row = {"period": "current", "label": "metric"}
        self.assertIs(
            coerce_period(
                non_year_row,
                {"claim": "metric without a year"},
            ),
            non_year_row,
        )
        self.assertIs(
            coerce_period(
                same_period,
                {"source_context": "2023년 context only"},
            ),
            same_period,
        )

        realigned = coerce_period(
            same_period,
            {"claim": "2023년 metric 100"},
        )
        self.assertIsNot(realigned, same_period)
        self.assertEqual(realigned["period"], "2023")
        self.assertEqual(realigned["period_source"], "evidence_surface")
        self.assertIs(realigned["nested"], nested)
        self.assertNotIn("period_source", same_period)

        label_aligned = {"period": "", "label": "2023년 metric", "matched_operand_label": "metric"}
        self.assertIs(
            coerce_period(
                label_aligned,
                {"raw_row_text": "2023년 metric 100"},
            ),
            label_aligned,
        )
        periodless = {"period": "", "label": "metric", "matched_operand_label": "metric"}
        inferred = coerce_period(
            periodless,
            {"quote_span": "2023년 metric 100"},
        )
        self.assertEqual(inferred, {**periodless, "period": "2023", "period_source": "evidence_surface"})
        self.assertIsNot(inferred, periodless)

    def test_evidence_local_unit_and_period_access_and_exception_contract(self) -> None:
        coerce_unit = operand_resolution.coerce_operand_unit_from_evidence
        coerce_period = operand_resolution.coerce_operand_period_from_evidence_surface
        events: List[tuple[str, str]] = []

        class AccessMapping(Mapping):
            def __init__(self, name: str, values: Dict[str, Any]) -> None:
                self.name = name
                self.values = values

            def __bool__(self) -> bool:
                events.append((self.name, "bool"))
                return bool(self.values)

            def get(self, key: str, default: Any = None) -> Any:
                events.append((self.name, f"get:{key}"))
                return self.values.get(key, default)

            def __getitem__(self, key: str) -> Any:
                events.append((self.name, f"item:{key}"))
                return self.values[key]

            def __iter__(self):
                events.append((self.name, "iter"))
                return iter(self.values)

            def __len__(self) -> int:
                events.append((self.name, "len"))
                return len(self.values)

        class StringProbe(str):
            def __new__(cls, name: str, value: str):
                instance = super().__new__(cls, value)
                instance.name = name
                return instance

            def __str__(self) -> str:
                events.append((self.name, "str"))
                return super().__str__()

        metadata = AccessMapping("metadata", {"unit_hint": StringProbe("hint", "백만원")})
        evidence = AccessMapping(
            "evidence",
            {
                "metadata": metadata,
                "claim": StringProbe("claim", "100 백만원"),
                "quote_span": StringProbe("quote", ""),
                "raw_row_text": StringProbe("raw-row", ""),
                "source_context": StringProbe("context", ""),
            },
        )
        self.assertEqual(
            coerce_unit(
                raw_value=StringProbe("raw-value", "100"),
                raw_unit=StringProbe("raw-unit", "원"),
                evidence_item=evidence,
            ),
            "백만원",
        )
        milestones = [
            ("evidence", "bool"),
            ("evidence", "get:metadata"),
            ("metadata", "iter"),
            ("hint", "str"),
            ("raw-unit", "str"),
            ("raw-value", "str"),
            ("evidence", "get:claim"),
            ("evidence", "get:quote_span"),
            ("evidence", "get:raw_row_text"),
            ("evidence", "get:source_context"),
        ]
        positions = [events.index(milestone) for milestone in milestones]
        self.assertEqual(positions, sorted(positions))

        events.clear()
        core_evidence = AccessMapping(
            "core-evidence",
            {
                "claim": "100원",
                "quote_span": "",
                "raw_row_text": "",
                "source_context": StringProbe("core-context", "100개"),
            },
        )
        self.assertTrue(
            operand_resolution._evidence_core_surface_contains_value_unit(
                raw_value="100",
                raw_unit="원",
                evidence_item=core_evidence,
            )
        )
        self.assertEqual(
            [event for event in events if event[0] == "core-evidence" and event[1].startswith("get:")],
            [
                ("core-evidence", "get:claim"),
                ("core-evidence", "get:quote_span"),
                ("core-evidence", "get:raw_row_text"),
            ],
        )
        self.assertNotIn(("core-context", "str"), events)

        finditer_patterns: List[str] = []
        current_finditer = operand_resolution.re.finditer

        def record_finditer(pattern: str, text: str, *args: Any, **kwargs: Any):
            finditer_patterns.append(pattern)
            return current_finditer(pattern, text, *args, **kwargs)

        with patch.object(
            operand_resolution.re,
            "finditer",
            side_effect=record_finditer,
        ):
            self.assertEqual(
                operand_resolution._infer_operand_unit_from_value_surface(
                    raw_value="100",
                    evidence_item={"claim": "100억"},
                ),
                "억원",
            )
        self.assertEqual(len(finditer_patterns), 2)
        self.assertIn("surface_unit", finditer_patterns[0])
        self.assertIn("?P<unit>", finditer_patterns[1])

        class PoisonSurfaceMapping(AccessMapping):
            def get(self, key: str, default: Any = None) -> Any:
                if key != "metadata":
                    raise AssertionError("surface access must stay lazy")
                return super().get(key, default)

        events.clear()
        self.assertEqual(
            coerce_unit(
                raw_value="not numeric",
                raw_unit="원",
                evidence_item=PoisonSurfaceMapping("lazy-evidence", {"metadata": {}}),
            ),
            "원",
        )
        self.assertEqual(
            [event for event in events if event[0] == "lazy-evidence"],
            [("lazy-evidence", "bool"), ("lazy-evidence", "get:metadata")],
        )

        known_surface_events: List[str] = []
        current_normalizer = operand_resolution._normalise_operand_value
        current_space_normalizer = operand_resolution._normalise_spaces

        def record_infer(**_kwargs: Any) -> str:
            known_surface_events.append("infer")
            return "원"

        def record_value_normalizer(raw_value: str, raw_unit: str):
            known_surface_events.append(f"value:{raw_unit}")
            return current_normalizer(raw_value, raw_unit)

        def record_family_normalizer(value: str) -> str:
            known_surface_events.append(f"family:{value}")
            return current_space_normalizer(value)

        def record_core_match(**_kwargs: Any) -> bool:
            known_surface_events.append("core")
            return False

        with (
            patch.object(
                operand_resolution,
                "_infer_operand_unit_from_value_surface",
                side_effect=record_infer,
            ),
            patch.object(
                operand_resolution,
                "_normalise_operand_value",
                side_effect=record_value_normalizer,
            ),
            patch.object(
                operand_resolution,
                "_normalise_spaces",
                side_effect=record_family_normalizer,
            ),
            patch.object(
                operand_resolution,
                "_evidence_core_surface_contains_value_unit",
                side_effect=record_core_match,
            ),
        ):
            self.assertEqual(
                coerce_unit(
                    raw_value="100",
                    raw_unit="개",
                    evidence_item={"metadata": {"unit_hint": "%"}},
                ),
                "개",
            )
        self.assertEqual(
            known_surface_events,
            [
                "infer",
                "value:원",
                "value:개",
                "value:%",
                "family:KRW",
                "family:COUNT",
                "family:PERCENT",
                "core",
            ],
        )

        no_surface_policy_events: List[str] = []

        class RepeatedPolicyString:
            def __init__(self, name: str, value: str) -> None:
                self.name = name
                self.value = value

            def __str__(self) -> str:
                no_surface_policy_events.append(self.name)
                return self.value

        with (
            patch.object(operand_resolution, "_infer_operand_unit_from_value_surface", return_value=""),
            patch.object(
                operand_resolution,
                "CALCULATION_RENDER_POLICY",
                {
                    "operand_unit_bare_numeric_pattern": RepeatedPolicyString(
                        "bare-pattern",
                        r"[\(\)\-]?\d[\d,]*(?:\.\d+)?",
                    ),
                    "operand_unit_ambiguous_krw_units": (
                        RepeatedPolicyString("ambiguous", "원"),
                    ),
                    "krw_display_units": (
                        RepeatedPolicyString("display", "백만원"),
                    ),
                },
            ),
        ):
            self.assertEqual(
                coerce_unit(
                    raw_value="100",
                    raw_unit="원",
                    evidence_item={"metadata": {"unit_hint": "백만원"}},
                ),
                "백만원",
            )
        self.assertEqual(no_surface_policy_events.count("bare-pattern"), 1)
        self.assertEqual(no_surface_policy_events.count("ambiguous"), 2)
        self.assertEqual(no_surface_policy_events.count("display"), 2)
        self.assertLess(
            no_surface_policy_events.index("bare-pattern"),
            no_surface_policy_events.index("ambiguous"),
        )
        self.assertLess(
            no_surface_policy_events.index("ambiguous"),
            no_surface_policy_events.index("display"),
        )

        row_events: List[str] = []

        class PeriodRow(Mapping):
            def __init__(self) -> None:
                self.values = {
                    "period": "",
                    "label": "metric",
                    "matched_operand_label": "metric",
                    "nested": metadata,
                }

            def get(self, key: str, default: Any = None) -> Any:
                row_events.append(f"get:{key}")
                return self.values.get(key, default)

            def __getitem__(self, key: str) -> Any:
                row_events.append(f"item:{key}")
                return self.values[key]

            def __iter__(self):
                row_events.append("iter")
                return iter(self.values)

            def __len__(self) -> int:
                row_events.append("len")
                return len(self.values)

        period_row = PeriodRow()
        period_result = coerce_period(
            period_row,
            {"claim": "2023년 metric 100"},
        )
        self.assertEqual(
            [event for event in row_events if event.startswith("get:")],
            ["get:period", "get:period", "get:label", "get:matched_operand_label"],
        )
        self.assertLess(row_events.index("get:matched_operand_label"), row_events.index("iter"))
        self.assertEqual(period_result["period"], "2023")
        self.assertIs(period_result["nested"], metadata)

        class GetBomb(Mapping):
            def __bool__(self) -> bool:
                return True

            def get(self, _key: str, _default: Any = None) -> Any:
                raise RuntimeError("get failed")

            def __getitem__(self, _key: str) -> Any:
                raise RuntimeError("item failed")

            def __iter__(self):
                raise RuntimeError("iteration failed")

            def __len__(self) -> int:
                return 1

        with self.assertRaisesRegex(RuntimeError, "get failed"):
            coerce_unit(
                raw_value="100",
                raw_unit="원",
                evidence_item=GetBomb(),
            )
        with self.assertRaisesRegex(RuntimeError, "get failed"):
            coerce_period(
                GetBomb(),
                {"claim": "2023년 metric"},
            )

        class MetadataCopyBomb(Mapping):
            def __getitem__(self, _key: str) -> Any:
                raise RuntimeError("metadata item failed")

            def __iter__(self):
                raise RuntimeError("metadata copy failed")

            def __len__(self) -> int:
                return 1

        with self.assertRaisesRegex(RuntimeError, "metadata copy failed"):
            coerce_unit(
                raw_value="100",
                raw_unit="원",
                evidence_item={"metadata": MetadataCopyBomb()},
            )

        class StringBomb:
            def __str__(self) -> str:
                raise RuntimeError("string failed")

        with self.assertRaisesRegex(RuntimeError, "string failed"):
            coerce_unit(
                raw_value="100",
                raw_unit=StringBomb(),
                evidence_item=None,
            )

        with (
            patch.object(operand_resolution, "_infer_operand_unit_from_value_surface", return_value="원"),
            patch.object(
                operand_resolution,
                "_normalise_operand_value",
                side_effect=RuntimeError("normalizer failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalizer failed"):
                coerce_unit(
                    raw_value="100",
                    raw_unit="원",
                    evidence_item=None,
                )

        with (
            patch.object(operand_resolution, "_infer_operand_unit_from_value_surface", return_value=""),
            patch.object(
                operand_resolution,
                "CALCULATION_RENDER_POLICY",
                MetadataCopyBomb(),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "metadata copy failed"):
                coerce_unit(
                    raw_value="100",
                    raw_unit="원",
                    evidence_item={"metadata": {"unit_hint": "백만원"}},
                )

        with patch.object(
            operand_resolution.re,
            "search",
            side_effect=RuntimeError("regex failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "regex failed"):
                operand_resolution._infer_operand_unit_from_value_surface(
                    raw_value="100",
                    evidence_item={"claim": "100원"},
                )

        class MatchGroupBomb:
            def end(self, _group_name: str) -> int:
                return len("100원")

            def group(self, _group_name: str) -> str:
                raise RuntimeError("match group failed")

        with patch.object(
            operand_resolution.re,
            "finditer",
            return_value=[MatchGroupBomb()],
        ):
            with self.assertRaisesRegex(RuntimeError, "match group failed"):
                operand_resolution._infer_operand_unit_from_value_surface(
                    raw_value="100",
                    evidence_item={"claim": "100원"},
                )

        class EndBomb:
            def end(self, _group_name: str) -> int:
                raise RuntimeError("end failed")

        with self.assertRaisesRegex(RuntimeError, "end failed"):
            operand_resolution._inline_unit_match_has_right_boundary("100원", EndBomb())

        policy_events: List[str] = []

        class PolicyString:
            def __init__(self, name: str, value: str) -> None:
                self.name = name
                self.value = value

            def __str__(self) -> str:
                policy_events.append(self.name)
                return self.value

        allowed = re.search(r"(?P<unit>원)", "100원이")
        self.assertIsNotNone(allowed)
        with (
            patch.object(
                operand_resolution,
                "CALCULATION_RENDER_POLICY",
                {
                    "inline_unit_right_boundary_allowed_prefixes": (
                        PolicyString("first-prefix", "이"),
                        PolicyString("retained-prefix", "가"),
                    ),
                    "inline_unit_right_boundary_block_pattern": PolicyString(
                        "lazy-block-pattern",
                        r"[0-9A-Za-z가-힣]",
                    ),
                },
            ),
            patch.object(
                operand_resolution.re,
                "match",
                side_effect=AssertionError("block regex must stay lazy"),
            ),
        ):
            self.assertTrue(
                operand_resolution._inline_unit_match_has_right_boundary(
                    "100원이",
                    allowed,
                )
            )
        self.assertEqual(policy_events.count("first-prefix"), 2)
        self.assertEqual(policy_events.count("retained-prefix"), 2)
        self.assertNotIn("lazy-block-pattern", policy_events)

        policy_events.clear()
        blocked = re.search(r"(?P<unit>원)", "100원화폐")
        self.assertIsNotNone(blocked)
        real_match = re.match
        regex_texts: List[str] = []

        def tracked_match(pattern: str, text: str, *args: Any, **kwargs: Any):
            policy_events.append("regex")
            regex_texts.append(text)
            return real_match(pattern, text, *args, **kwargs)

        with (
            patch.object(
                operand_resolution,
                "CALCULATION_RENDER_POLICY",
                {
                    "inline_unit_right_boundary_allowed_prefixes": (PolicyString("prefix", "이"),),
                    "inline_unit_right_boundary_block_pattern": PolicyString(
                        "block-pattern",
                        r"[0-9A-Za-z가-힣]",
                    ),
                },
            ),
            patch.object(operand_resolution.re, "match", side_effect=tracked_match),
        ):
            self.assertFalse(
                operand_resolution._inline_unit_match_has_right_boundary(
                    "100원화폐",
                    blocked,
                )
            )
        self.assertLess(policy_events.index("prefix"), policy_events.index("block-pattern"))
        self.assertLess(policy_events.index("block-pattern"), policy_events.index("regex"))
        self.assertEqual(regex_texts, ["화"])

    def test_ratio_context_metric_surface_preserves_behavior_contract(self) -> None:
        matches = operand_resolution.ratio_context_has_metric_surface

        class IterBomb:
            def __iter__(self):
                raise RuntimeError("evidence accessed without a metric label")

        self.assertFalse(
            matches(
                IterBomb(),  # type: ignore[arg-type]
                {
                    "metric_label": " ",
                    "target_metric": "",
                    "label": None,
                    "name": "\t",
                    "aliases": ["", "  "],
                },
            )
        )

        task = {"metric_label": "target metric"}
        surface_locations = [
            ("claim", False),
            ("quote_span", False),
            ("raw_row_text", False),
            ("source_context", False),
            ("row_label", True),
            ("semantic_label", True),
            ("aggregate_label", True),
            ("table_summary_text", True),
            ("table_title", True),
            ("table_context", True),
            ("table_row_labels_text", True),
            ("table_value_labels_text", True),
            ("row_text", True),
            ("semantic_aliases", True),
            ("row_headers", True),
        ]
        for key, in_metadata in surface_locations:
            with self.subTest(surface=key):
                value: Any = ["target metric 10"] if key in {"semantic_aliases", "row_headers"} else "target metric 10"
                evidence = {"metadata": {key: value}} if in_metadata else {key: value}
                self.assertTrue(matches([evidence], task))
        self.assertFalse(matches([{"claim": "unrelated 10"}], task))

        nested_metadata = {"row_label": "surface three", "semantic_aliases": ["surface four"], "row_headers": ["surface five"]}
        evidence_items = [
            {
                "claim": " ",
                "quote_span": "surface one",
                "raw_row_text": "",
                "source_context": "surface two",
                "metadata": nested_metadata,
            },
            {"claim": "surface six", "quote_span": "later surface"},
        ]
        aliases = ["metric b", " metric c ", ""]
        ordered_task = {
            "metric_label": " metric a ",
            "target_metric": "metric a",
            "label": "metric b",
            "name": "",
            "aliases": aliases,
        }
        before = deepcopy((evidence_items, ordered_task))
        calls = []

        def operand_match(surface, operand):
            calls.append((surface, operand))
            return surface == "surface six" and operand["label"] == "metric c"

        with patch.object(operand_resolution, "_operand_text_match", side_effect=operand_match):
            self.assertTrue(matches(evidence_items, ordered_task))

        expected_surfaces = [
            "surface one",
            "surface two",
            "surface three",
            "surface four",
            "surface five",
            "surface six",
        ]
        self.assertEqual(
            [(surface, operand["label"]) for surface, operand in calls],
            [
                (surface, label)
                for surface in expected_surfaces
                for label in ("metric a", "metric b", "metric c")
            ],
        )
        self.assertEqual((evidence_items, ordered_task), before)
        self.assertIs(evidence_items[0]["metadata"], nested_metadata)
        self.assertIs(ordered_task["aliases"], aliases)

    def test_ratio_context_metric_surface_preserves_access_and_exception_contract(self) -> None:
        matches = operand_resolution.ratio_context_has_metric_surface
        events: List[str] = []

        class AccessDict(dict):
            def __init__(self, values, owner):
                super().__init__(values)
                self.owner = owner

            def get(self, key, default=None):
                events.append(f"get:{self.owner}:{key}")
                return super().get(key, default)

        class CopyMapping(Mapping):
            def __init__(self, values, owner):
                self.values = values
                self.owner = owner

            def __len__(self):
                return len(self.values)

            def __iter__(self):
                return iter(self.values)

            def __getitem__(self, key):
                return self.values[key]

        real_dict = dict

        class RecordingDict(real_dict):
            def __init__(self, source=(), **kwargs):
                owner = getattr(source, "owner", "generated")
                if owner != "generated":
                    events.append(f"copy:{owner}")
                super().__init__(source, **kwargs)
                self.owner = owner

            def get(self, key, default=None):
                if self.owner != "generated":
                    events.append(f"get:{self.owner}:{key}")
                return super().get(key, default)

        metadata = CopyMapping(
            {
                "row_label": "",
                "semantic_label": "",
                "aggregate_label": "",
                "table_summary_text": "",
                "table_title": "",
                "table_context": "",
                "table_row_labels_text": "",
                "table_value_labels_text": "",
                "row_text": "",
                "semantic_aliases": [],
                "row_headers": [],
            },
            "metadata",
        )
        evidence = CopyMapping(
            {
                "claim": "target metric 10",
                "quote_span": "",
                "raw_row_text": "",
                "source_context": "",
                "metadata": metadata,
            },
            "evidence",
        )
        tracked_task = AccessDict(
            {
                "metric_label": "target metric",
                "target_metric": "",
                "label": "",
                "name": "",
                "aliases": [],
            },
            "task",
        )
        real_match = operand_resolution._operand_text_match

        def tracked_match(surface, operand):
            events.append(f"match:{surface}:{operand['label']}")
            return real_match(surface, operand)

        with (
            patch.object(operand_resolution, "dict", RecordingDict, create=True),
            patch.object(operand_resolution, "_operand_text_match", side_effect=tracked_match),
        ):
            self.assertTrue(matches([evidence], tracked_task))

        milestones = [
            "get:task:metric_label",
            "get:task:target_metric",
            "get:task:label",
            "get:task:name",
            "get:task:aliases",
            "copy:evidence",
            "get:evidence:metadata",
            "copy:metadata",
            "get:evidence:claim",
            "get:evidence:quote_span",
            "get:evidence:raw_row_text",
            "get:evidence:source_context",
            "get:metadata:row_label",
            "get:metadata:semantic_label",
            "get:metadata:aggregate_label",
            "get:metadata:table_summary_text",
            "get:metadata:table_title",
            "get:metadata:table_context",
            "get:metadata:table_row_labels_text",
            "get:metadata:table_value_labels_text",
            "get:metadata:row_text",
            "get:metadata:semantic_aliases",
            "get:metadata:row_headers",
            "match:target metric 10:target metric",
        ]
        cursor = 0
        for event in events:
            if cursor < len(milestones) and event == milestones[cursor]:
                cursor += 1
        self.assertEqual(cursor, len(milestones))

        real_normalize = operand_resolution._normalise_spaces

        def later_normalize(value):
            if value == "later surface":
                raise RuntimeError("later surface normalized")
            return real_normalize(value)

        with patch.object(operand_resolution, "_normalise_spaces", side_effect=later_normalize):
            self.assertTrue(
                matches(
                    [{"claim": "target metric 10", "quote_span": "later surface"}],
                    {"metric_label": "target metric"},
                )
            )

        class GetBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                return iter(("metric_label",))

            def __getitem__(self, key):
                raise KeyError(key)

            def get(self, _key, _default=None):
                raise RuntimeError("mapping get failed")

        class CopyBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                raise RuntimeError("mapping copy failed")

            def __getitem__(self, key):
                raise KeyError(key)

        class IterBomb:
            def __iter__(self):
                raise RuntimeError("iteration failed")

        class StringBomb:
            def __str__(self):
                raise RuntimeError("string failed")

        class CountingString:
            def __init__(self, value):
                self.value = value
                self.calls = 0

            def __bool__(self):
                return True

            def __str__(self):
                self.calls += 1
                return self.value

        retained_label = CountingString("retained")
        blank_label = CountingString("   ")
        normalized_values = []

        def count_normalize(value):
            normalized_values.append(value)
            return real_normalize(value)

        with patch.object(operand_resolution, "_normalise_spaces", side_effect=count_normalize):
            self.assertFalse(
                matches(
                    [],
                    {
                        "metric_label": retained_label,
                        "target_metric": blank_label,
                    },
                )
            )
        self.assertEqual((retained_label.calls, blank_label.calls), (2, 1))
        self.assertEqual((normalized_values.count("retained"), normalized_values.count("   ")), (2, 1))

        with self.assertRaisesRegex(RuntimeError, "mapping get failed"):
            matches([], GetBomb())  # type: ignore[arg-type]
        with self.assertRaisesRegex(RuntimeError, "iteration failed"):
            matches([], {"metric_label": "target", "aliases": IterBomb()})
        with self.assertRaisesRegex(RuntimeError, "iteration failed"):
            matches(IterBomb(), {"metric_label": "target"})  # type: ignore[arg-type]
        with patch.object(operand_resolution, "_operand_text_match") as matcher:
            with self.assertRaisesRegex(RuntimeError, "mapping copy failed"):
                matches(
                    [{"claim": "target 10"}, CopyBomb()],
                    {"metric_label": "target"},
                )
        matcher.assert_not_called()
        with patch.object(operand_resolution, "_operand_text_match") as matcher:
            with self.assertRaisesRegex(RuntimeError, "string failed"):
                matches(
                    [{"claim": "target 10"}, {"claim": StringBomb()}],
                    {"metric_label": "target"},
                )
        matcher.assert_not_called()
        with self.assertRaisesRegex(RuntimeError, "mapping copy failed"):
            matches(
                [{"metadata": CopyBomb()}],
                {"metric_label": "target"},
            )

        class UnhashableLabel:
            __hash__ = None

            def __bool__(self):
                return True

        with patch.object(
            operand_resolution,
            "_normalise_spaces",
            return_value=UnhashableLabel(),
        ):
            with self.assertRaisesRegex(TypeError, "unhashable"):
                matches([], {"metric_label": "target"})
        for name, context, task in (
            ("task", [], {"metric_label": StringBomb()}),
            ("evidence", [{"claim": StringBomb()}], {"metric_label": "target"}),
            (
                "metadata list",
                [{"metadata": {"semantic_aliases": [StringBomb()]}}],
                {"metric_label": "target"},
            ),
        ):
            with self.subTest(string=name), self.assertRaisesRegex(RuntimeError, "string failed"):
                matches(context, task)
        for owner, patch_name in (
            ("normalizer", "_normalise_spaces"),
            ("matcher", "_operand_text_match"),
        ):
            with self.subTest(owner=owner), patch.object(
                operand_resolution,
                patch_name,
                side_effect=RuntimeError(f"{owner} failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, f"{owner} failed"):
                    matches([{"claim": "target 10"}], {"metric_label": "target"})

    def test_surface_contract_numeric_evidence_items_preserves_behavior_contract(self) -> None:
        select = operand_resolution.surface_contract_numeric_evidence_items

        class IterBomb(list):
            def __iter__(self):
                raise RuntimeError("unused input iterated")

        empty_from_evidence = select([], IterBomb([{}]))
        empty_from_requirements = select(IterBomb([{}]), [])
        self.assertEqual(empty_from_evidence, [])
        self.assertEqual(empty_from_requirements, [])
        self.assertIsNot(empty_from_evidence, empty_from_requirements)

        first_nested = {"nested": "first"}
        anchor_nested = {"nested": "anchor"}
        fallback_nested = {"nested": "fallback"}
        evidence_items = [
            {"marker": "blank", "claim": "   "},
            {"marker": "no-digit", "claim": "metric without number"},
            {
                "marker": "first",
                "evidence_id": "shared-id",
                "source_anchor": "first-anchor",
                "claim": "first metric 10",
                "nested": first_nested,
            },
            {
                "marker": "duplicate-id",
                "evidence_id": "shared-id",
                "source_anchor": "different-anchor",
                "claim": "duplicate metric 20",
            },
            {
                "marker": "anchor",
                "source_anchor": "shared-anchor",
                "quote_span": "anchor metric 30",
                "nested": anchor_nested,
            },
            {
                "marker": "duplicate-anchor",
                "source_anchor": "shared-anchor",
                "raw_row_text": "different metric 35",
            },
            {
                "marker": "fallback",
                "raw_row_text": "fallback metric 40",
                "nested": fallback_nested,
            },
        ]
        required_operands = [
            {"role": "positive-miss"},
            {"role": "negative"},
            {"role": "extract-miss"},
            {"role": "match-1"},
            {"role": "match-2"},
        ]
        before = deepcopy((evidence_items, required_operands))
        events = []

        def positive(surface, operand):
            events.append(("positive", surface, operand["role"]))
            return operand["role"] != "positive-miss"

        def negative(surface, operand):
            events.append(("negative", surface, operand["role"]))
            return operand["role"] == "negative"

        def extract(surface, operand):
            events.append(("extract", surface, operand["role"]))
            return "" if operand["role"] == "extract-miss" else "10"

        with (
            patch.object(operand_resolution, "_text_has_positive_surface", side_effect=positive),
            patch.object(operand_resolution, "_text_has_negative_surface", side_effect=negative),
            patch.object(
                operand_resolution,
                "_extract_numeric_value_after_operand_text",
                side_effect=extract,
            ),
        ):
            selected = select(evidence_items, required_operands)

        self.assertEqual([row["marker"] for row in selected], ["first", "anchor", "fallback"])
        self.assertIsNot(selected, evidence_items)
        selected_inputs = (evidence_items[2], evidence_items[4], evidence_items[6])
        for result_row, input_row in zip(selected, selected_inputs):
            self.assertIsNot(result_row, input_row)
        self.assertIs(selected[0]["nested"], first_nested)
        self.assertIs(selected[1]["nested"], anchor_nested)
        self.assertIs(selected[2]["nested"], fallback_nested)
        self.assertEqual((evidence_items, required_operands), before)

        touched_surfaces = {event[1] for event in events}
        self.assertNotIn("", touched_surfaces)
        self.assertNotIn("metric without number", touched_surfaces)
        self.assertIn(("positive", "duplicate metric 20", "match-2"), events)
        self.assertNotIn(("positive", "first metric 10", "match-2"), events)
        self.assertIn(("positive", "different metric 35", "match-2"), events)
        self.assertNotIn(("negative", "first metric 10", "positive-miss"), events)
        self.assertNotIn(("extract", "first metric 10", "positive-miss"), events)
        self.assertNotIn(("extract", "first metric 10", "negative"), events)

        class AnchorBomb:
            def __bool__(self):
                raise RuntimeError("anchor truthiness accessed")

            def __str__(self):
                raise RuntimeError("anchor string accessed")

        with (
            patch.object(operand_resolution, "_text_has_positive_surface", return_value=True),
            patch.object(operand_resolution, "_text_has_negative_surface", return_value=False),
            patch.object(
                operand_resolution,
                "_extract_numeric_value_after_operand_text",
                return_value="10",
            ),
        ):
            id_precedence = select(
                [{"claim": "metric 10", "evidence_id": "id", "source_anchor": AnchorBomb()}],
                [{"role": "current"}],
            )
        self.assertEqual(id_precedence[0]["evidence_id"], "id")

    def test_surface_contract_numeric_evidence_items_preserves_access_and_exception_contract(self) -> None:
        select = operand_resolution.surface_contract_numeric_evidence_items
        events = []

        class TrackedValue:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __bool__(self):
                events.append(f"bool:{self.name}")
                return True

            def __str__(self):
                events.append(f"str:{self.name}")
                return self.value

        real_normalize = operand_resolution._normalise_spaces
        real_search = operand_resolution.re.search

        def normalize(value):
            events.append(f"normalize:{value}")
            return real_normalize(value)

        def search(pattern, value, *args, **kwargs):
            events.append(f"regex:{value}")
            return real_search(pattern, value, *args, **kwargs)

        def positive(surface, _operand):
            events.append(f"positive:{surface}")
            return True

        def negative(surface, _operand):
            events.append(f"negative:{surface}")
            return False

        def extract(surface, _operand):
            events.append(f"extract:{surface}")
            return "10"

        evidence = {
            "evidence_id": "tracked",
            "claim": TrackedValue("claim", "claim 10"),
            "quote_span": TrackedValue("quote", "quote 20"),
            "raw_row_text": TrackedValue("raw", "raw 30"),
        }
        with (
            patch.object(operand_resolution, "_normalise_spaces", side_effect=normalize),
            patch.object(operand_resolution.re, "search", side_effect=search),
            patch.object(operand_resolution, "_text_has_positive_surface", side_effect=positive),
            patch.object(operand_resolution, "_text_has_negative_surface", side_effect=negative),
            patch.object(
                operand_resolution,
                "_extract_numeric_value_after_operand_text",
                side_effect=extract,
            ),
        ):
            selected = select([evidence], [{"role": "current"}])

        self.assertEqual(selected[0]["evidence_id"], "tracked")
        self.assertEqual(
            events,
            [
                "bool:claim",
                "str:claim",
                "bool:quote",
                "str:quote",
                "bool:raw",
                "str:raw",
                "normalize:claim 10 quote 20 raw 30",
                "regex:claim 10 quote 20 raw 30",
                "positive:claim 10 quote 20 raw 30",
                "negative:claim 10 quote 20 raw 30",
                "extract:claim 10 quote 20 raw 30",
            ],
        )

        class BoolBomb(list):
            def __bool__(self):
                raise RuntimeError("truthiness failed")

        class IterBomb(list):
            def __iter__(self):
                raise RuntimeError("iteration failed")

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

        with self.assertRaisesRegex(RuntimeError, "truthiness failed"):
            select(BoolBomb(), [])
        with self.assertRaisesRegex(RuntimeError, "iteration failed"):
            select(IterBomb([{}]), [{}])
        with self.assertRaisesRegex(RuntimeError, "copy failed"):
            select([CopyBomb()], [{}])
        with self.assertRaisesRegex(RuntimeError, "copy failed"):
            select([{"claim": "metric 10"}], [CopyBomb()])
        with self.assertRaisesRegex(RuntimeError, "string failed"):
            select([{"claim": StringBomb()}], [{}])

        row = [{"claim": "metric 10"}]
        requirement = [{"role": "current"}]
        for owner_name, patch_target in (
            ("normalizer", "_normalise_spaces"),
            ("positive", "_text_has_positive_surface"),
        ):
            with self.subTest(propagates=owner_name), patch.object(
                operand_resolution,
                patch_target,
                side_effect=RuntimeError(f"{owner_name} failed"),
            ):
                with self.assertRaisesRegex(RuntimeError, f"{owner_name} failed"):
                    select(row, requirement)
        with patch.object(operand_resolution.re, "search", side_effect=RuntimeError("regex failed")):
            with self.assertRaisesRegex(RuntimeError, "regex failed"):
                select(row, requirement)
        with (
            patch.object(operand_resolution, "_text_has_positive_surface", return_value=True),
            patch.object(
                operand_resolution,
                "_text_has_negative_surface",
                side_effect=RuntimeError("negative failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "negative failed"):
                select(row, requirement)
        with (
            patch.object(operand_resolution, "_text_has_positive_surface", return_value=True),
            patch.object(operand_resolution, "_text_has_negative_surface", return_value=False),
            patch.object(
                operand_resolution,
                "_extract_numeric_value_after_operand_text",
                side_effect=RuntimeError("extract failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "extract failed"):
                select(row, requirement)

        class HashBombString(str):
            def __hash__(self):
                raise RuntimeError("hash failed")

        class HashBombValue:
            def __str__(self):
                return HashBombString("hash-bomb")

        with (
            patch.object(operand_resolution, "_text_has_positive_surface", return_value=True),
            patch.object(operand_resolution, "_text_has_negative_surface", return_value=False),
            patch.object(
                operand_resolution,
                "_extract_numeric_value_after_operand_text",
                return_value="10",
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "hash failed"):
                select(
                    [{"claim": "metric 10", "evidence_id": HashBombValue()}],
                    requirement,
                )

    def test_rendered_unit_operand_normalization_repair_matrix(self) -> None:
        repair = operand_resolution.repair_operand_normalization_from_rendered_unit
        million_won = "\ubc31\ub9cc\uc6d0"
        hundred_million_won = "\uc5b5\uc6d0"
        nested = []

        early_rows = [
            {},
            {"raw_value": "2", "normalized_unit": "KRW"},
            {"rendered_value": f"2{million_won}", "normalized_unit": "KRW"},
            {
                "raw_value": "2",
                "rendered_value": f"2{million_won}",
                "normalized_value": 2.0,
                "normalized_unit": "PERCENT",
                "nested": nested,
            },
        ]
        for row in early_rows:
            with self.subTest(early=row):
                before = deepcopy(row)
                repaired = repair(row)
                self.assertEqual(repaired, before)
                self.assertIsNot(repaired, row)
                self.assertEqual(row, before)
        self.assertIs(repair(early_rows[-1])["nested"], nested)

        inline_row = {
            "raw_value": "2\uc5b5",
            "rendered_value": "2\uc5b5",
            "raw_unit": "\uc6d0",
            "normalized_value": 2.0,
            "normalized_unit": "UNKNOWN",
            "original_raw_unit": "source unit",
            "original_normalized_value": 0.0,
            "nested": nested,
        }
        inline_before = deepcopy(inline_row)
        inline_repaired = repair(inline_row)
        self.assertEqual(inline_repaired["raw_unit"], hundred_million_won)
        self.assertEqual(inline_repaired["normalized_value"], 200_000_000.0)
        self.assertEqual(inline_repaired["normalized_unit"], "KRW")
        self.assertEqual(inline_repaired["original_raw_unit"], "source unit")
        self.assertEqual(inline_repaired["original_normalized_value"], 0.0)
        self.assertTrue(inline_repaired["unit_repaired_from_rendered_value"])
        self.assertIs(inline_repaired["nested"], nested)
        self.assertEqual(inline_row, inline_before)

        inline_close = {
            "raw_value": f"2{million_won}",
            "rendered_value": f"2{million_won}",
            "raw_unit": million_won,
            "normalized_value": 2_000_000.001,
            "normalized_unit": "KRW",
        }
        self.assertEqual(repair(inline_close), inline_close)
        inline_nan = {**inline_close, "normalized_value": float("nan")}
        inline_nan_repaired = repair(inline_nan)
        self.assertIs(inline_nan_repaired["normalized_value"], inline_nan["normalized_value"])
        self.assertNotIn("unit_repaired_from_rendered_value", inline_nan_repaired)

        rendered_row = {
            "raw_value": "2",
            "rendered_value": f"1{million_won} 2\uc5b5 2{million_won}",
            "raw_unit": "\uc6d0",
            "normalized_value": float("nan"),
            "normalized_unit": "KRW",
            "original_raw_unit": "",
            "original_normalized_value": None,
        }
        rendered_before = dict(rendered_row)
        rendered_repaired = repair(rendered_row)
        self.assertEqual(rendered_repaired["raw_unit"], hundred_million_won)
        self.assertEqual(rendered_repaired["normalized_value"], 200_000_000.0)
        self.assertEqual(rendered_repaired["original_raw_unit"], "\uc6d0")
        self.assertIs(rendered_repaired["original_normalized_value"], rendered_row["normalized_value"])
        self.assertTrue(rendered_repaired["unit_repaired_from_rendered_value"])
        self.assertEqual(rendered_row, rendered_before)

        rendered_close = {
            "raw_value": "2",
            "rendered_value": f"2{million_won}",
            "raw_unit": million_won,
            "normalized_value": 2_000_000.001,
            "normalized_unit": "KRW",
        }
        self.assertEqual(repair(rendered_close), rendered_close)

        billion_won = "\uc2ed\uc5b5\uc6d0"
        for boundary_row in (
            {**inline_close, "raw_value": f"1{billion_won}", "rendered_value": f"1{billion_won}", "normalized_value": 1_000_000_001.0},
            {**rendered_close, "raw_value": "1", "rendered_value": f"1{billion_won}", "normalized_value": 1_000_000_001.0},
        ):
            with self.subTest(tolerance_boundary=boundary_row["raw_value"]):
                self.assertEqual(repair(boundary_row), boundary_row)

        blank_pattern_row = {**rendered_close, "normalized_value": 2.0}
        with patch.object(
            operand_resolution,
            "NUMERIC_UNIT_NORMALIZATION_POLICY",
            {"inline_value_unit_pattern": ""},
        ):
            self.assertEqual(repair(blank_pattern_row), blank_pattern_row)

    def test_rendered_unit_operand_normalization_repair_exception_and_access_order(self) -> None:
        repair = operand_resolution.repair_operand_normalization_from_rendered_unit
        events: List[str] = []

        class ValueProbe:
            def __init__(self, name: str, value: str, *, error: Exception | None = None) -> None:
                self.name = name
                self.value = value
                self.error = error

            def __bool__(self) -> bool:
                events.append(f"bool:{self.name}")
                return True

            def __str__(self) -> str:
                events.append(f"str:{self.name}")
                if self.error is not None:
                    raise self.error
                return self.value

        repair(
            {
                "raw_value": ValueProbe("raw", "2"),
                "rendered_value": ValueProbe("rendered", "2%"),
                "normalized_unit": ValueProbe("unit", "PERCENT"),
            },
        )
        self.assertEqual(
            events,
            ["bool:raw", "str:raw", "bool:rendered", "str:rendered", "bool:unit", "str:unit"],
        )

        class MappingFailure:
            def __bool__(self) -> bool:
                events.append("bool:mapping")
                return True

            def keys(self):
                events.append("keys:mapping")
                raise RuntimeError("mapping failed")

        events.clear()
        with self.assertRaisesRegex(RuntimeError, "mapping failed"):
            repair(MappingFailure())
        self.assertEqual(events, ["bool:mapping", "keys:mapping"])

        events.clear()
        with self.assertRaisesRegex(RuntimeError, "raw string failed"):
            repair(
                {
                    "raw_value": ValueProbe("raw", "", error=RuntimeError("raw string failed")),
                    "rendered_value": ValueProbe("rendered", "unused"),
                },
            )
        self.assertEqual(events, ["bool:raw", "str:raw"])

        class FloatFailure:
            def __init__(self, error: Exception) -> None:
                self.error = error

            def __float__(self) -> float:
                raise self.error

        repair_row = {
            "raw_value": "2",
            "rendered_value": "2\ubc31\ub9cc\uc6d0",
            "raw_unit": "\uc6d0",
            "normalized_unit": "KRW",
        }
        for error in (TypeError("bad float"), ValueError("bad float")):
            with self.subTest(caught=type(error).__name__):
                repaired = repair({**repair_row, "normalized_value": FloatFailure(error)})
                self.assertEqual(repaired["normalized_value"], 2_000_000.0)

        with self.assertRaisesRegex(RuntimeError, "float failed"):
            repair({**repair_row, "normalized_value": FloatFailure(RuntimeError("float failed"))})
        with patch.object(
            operand_resolution,
            "_normalise_operand_value",
            side_effect=RuntimeError("normalizer failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalizer failed"):
                repair({**repair_row, "normalized_value": 2.0})
        with patch.object(
            operand_resolution,
            "NUMERIC_UNIT_NORMALIZATION_POLICY",
            {"inline_value_unit_pattern": "("},
        ):
            with self.assertRaises(re.error):
                repair({**repair_row, "normalized_value": 2.0})

    def test_shared_table_ratio_unit_alignment_matrix(self) -> None:
        align = operand_resolution.align_ratio_operand_units_with_shared_table_context
        base_policy = dict(operand_resolution.CALCULATION_RENDER_POLICY)
        scales = dict(base_policy.get("krw_display_unit_scales") or {})
        eligible_units = [
            unit
            for unit in (base_policy.get("source_display_units") or ())
            if unit in scales
        ]
        smaller_unit = min(eligible_units, key=scales.get)
        larger_unit = max(eligible_units, key=scales.get)
        nested = []

        def row(raw_unit: str, **updates: Any) -> Dict[str, Any]:
            result = {
                "raw_value": "2",
                "raw_unit": raw_unit,
                "normalized_value": 0.0,
                "normalized_unit": "KRW",
                "table_source_id": "table:1",
            }
            result.update(updates)
            return result

        operands = [
            row(larger_unit),
            row(smaller_unit, original_raw_unit="kept", nested=nested),
            row(smaller_unit, raw_value="3"),
            row(smaller_unit, raw_value="bad"),
            row(smaller_unit, table_source_id="table:2"),
        ]
        before = deepcopy(operands)

        aligned = align(operands)

        self.assertIsNot(aligned, operands)
        for result, source in zip(aligned, operands):
            self.assertIsNot(result, source)
        self.assertEqual(operands, before)
        self.assertIs(aligned[1]["nested"], nested)
        self.assertEqual(aligned[1]["original_raw_unit"], "kept")
        self.assertEqual(aligned[2]["original_raw_unit"], smaller_unit)
        self.assertEqual(
            (aligned[2]["raw_unit"], aligned[2]["normalized_value"], aligned[2]["normalized_unit"]),
            (larger_unit, 3 * scales[larger_unit], "KRW"),
        )
        self.assertEqual(aligned[2]["rendered_value"], f"3{larger_unit}")
        self.assertTrue(all(aligned[index]["ratio_unit_aligned_from_sibling_table"] for index in (1, 2)))
        self.assertTrue(
            all("ratio_unit_aligned_from_sibling_table" not in aligned[index] for index in (0, 3, 4))
        )

        no_change_cases = [
            [row(smaller_unit)],
            [row(smaller_unit), row(smaller_unit)],
            [row(smaller_unit), row(larger_unit, table_source_id="table:2")],
            [row(smaller_unit, table_source_id=""), row(larger_unit, table_source_id="")],
            [
                row(smaller_unit, table_source_id="table:1", source_table_id="source:same"),
                row(larger_unit, table_source_id="table:2", source_table_id="source:same"),
            ],
            [
                row(smaller_unit, table_source_id="", source_section="notes", statement_type="fs"),
                row(larger_unit, table_source_id="", source_section="notes", statement_type="fs"),
            ],
            [
                row(smaller_unit, normalized_unit="COUNT"),
                row(larger_unit),
            ],
        ]
        for candidate in no_change_cases:
            with self.subTest(no_change=candidate):
                self.assertIs(align(candidate), candidate)

        section = {
            "source_section": "notes",
            "statement_type": "financial_statement",
            "consolidation_scope": "consolidated",
        }
        grouped_cases = (
            [
                row(smaller_unit, table_source_id="", source_table_id="source:1"),
                row(larger_unit, table_source_id="", source_table_id="source:1"),
            ],
            [
                row(smaller_unit, table_source_id="", **section),
                row(larger_unit, table_source_id="", **section),
            ],
        )
        for candidate in grouped_cases:
            self.assertIsNot(align(candidate), candidate)
        table_precedence = [
            row(smaller_unit, table_source_id="table:1", **section),
            row(larger_unit, table_source_id="table:2", **section),
        ]
        self.assertIs(align(table_precedence), table_precedence)

        for policy in (
            {**base_policy, "krw_normalized_unit": ""},
            {**base_policy, "source_display_units": (smaller_unit,)},
        ):
            with patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", policy):
                self.assertIs(align(operands), operands)

        bad_scales = {smaller_unit: "bad", larger_unit: scales[larger_unit]}
        with patch.object(
            operand_resolution,
            "CALCULATION_RENDER_POLICY",
            {**base_policy, "krw_display_unit_scales": bad_scales},
        ):
            with self.assertRaises(ValueError):
                align(operands)
        with patch.object(
            operand_resolution,
            "_normalise_operand_value",
            return_value=(float("nan"), "KRW"),
        ):
            nan_aligned = align(operands)
        self.assertNotEqual(nan_aligned[1]["normalized_value"], nan_aligned[1]["normalized_value"])
        self.assertTrue(nan_aligned[1]["ratio_unit_aligned_from_sibling_table"])
        with patch.object(
            operand_resolution,
            "_normalise_operand_value",
            side_effect=RuntimeError("normalizer failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalizer failed"):
                align(operands)
        self.assertEqual(operands, before)

        class CopyFailure:
            def __init__(self, values: Dict[str, Any]) -> None:
                self.values = values

            def get(self, key: str, default: Any = None) -> Any:
                return self.values.get(key, default)

            def keys(self) -> Any:
                raise RuntimeError("row copy failed")

        with patch.object(operand_resolution, "max", create=True) as maximum:
            with self.assertRaisesRegex(RuntimeError, "row copy failed"):
                align([row(larger_unit), CopyFailure(row(smaller_unit))])  # type: ignore[list-item]
        maximum.assert_not_called()
        with patch.object(
            operand_resolution,
            "max",
            create=True,
            side_effect=RuntimeError("max failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "max failed"):
                align([row(larger_unit), row(smaller_unit)])

    def test_evidence_identity_and_surface_helpers_have_operand_resolution_owner(self) -> None:
        helper_names = (
            "_canonical_structured_reconciliation_id",
            "_canonicalize_structured_operand_reconciliation_refs",
            "_operand_slot_has_evidence_surface_match",
            "repair_operand_normalization_from_rendered_unit",
            "align_ratio_operand_units_with_shared_table_context",
        )

        for helper_name in helper_names:
            with self.subTest(helper=helper_name):
                self.assertTrue(hasattr(operand_resolution, helper_name))
                self.assertNotIn(helper_name, FinancialAgentCalculationMixin.__dict__)

    def test_structured_reconciliation_identity_and_operand_surface_matrix(self) -> None:
        identity_cases = [
            (" recon::table::value:001 ", "table::value:001"),
            ("recon::table::rowrec:002", "table::rowrec:002"),
            ("recon::table::colrec:003", "table::colrec:003"),
            ("recon::table::raw_row", "recon::table::raw_row"),
            ("recon::plain", "recon::plain"),
            ("plain", "plain"),
        ]
        for value, expected in identity_cases:
            with self.subTest(identity=value):
                self.assertEqual(
                    operand_resolution._canonical_structured_reconciliation_id(value),
                    expected,
                )

        row = {
            "evidence_id": " recon::table::value:001 ",
            "source_row_id": "recon::table::raw_row",
            "source_row_ids": [
                "recon::table::value:001",
                "recon::table::rowrec:002",
                "recon::table::value:001",
                "plain",
            ],
        }
        original_row = deepcopy(row)
        canonical_row = operand_resolution._canonicalize_structured_operand_reconciliation_refs(
            row
        )

        self.assertEqual(canonical_row["evidence_id"], "table::value:001")
        self.assertEqual(canonical_row["source_row_id"], "recon::table::raw_row")
        self.assertEqual(
            canonical_row["source_row_ids"],
            ["table::value:001", "table::rowrec:002", "plain"],
        )
        self.assertEqual(row, original_row)

        surface_cases = [
            (
                "matched_line",
                {"_matched_line_label": "target metric"},
                None,
                {"label": "target metric"},
                "",
                True,
            ),
            (
                "metric_label_compact",
                {"_matched_line_label": "targetmetric"},
                None,
                {"label": "other metric"},
                "target metric",
                True,
            ),
            (
                "claim",
                {},
                {"claim": "target metric 10"},
                {"label": "target metric"},
                "",
                True,
            ),
            (
                "structured_cell_alias",
                {},
                {"metadata": {"structured_cells": [{"column_headers": ["target alias"]}]}},
                {"label": "target metric", "aliases": ["target alias"]},
                "",
                True,
            ),
            (
                "unrelated",
                {},
                {"claim": "different measure 10"},
                {"label": "target metric"},
                "",
                False,
            ),
            ("missing_evidence", {}, None, {"label": "target metric"}, "", False),
        ]
        for name, slot, evidence, operand, metric_label, expected in surface_cases:
            with self.subTest(surface=name):
                original_inputs = deepcopy((slot, evidence, operand))
                self.assertEqual(
                    operand_resolution._operand_slot_has_evidence_surface_match(
                        slot,
                        evidence,
                        operand,
                        metric_label=metric_label,
                    ),
                    expected,
                )
                self.assertEqual((slot, evidence, operand), original_inputs)

    @staticmethod
    def _context_dependent_lookup_evidence() -> Dict[str, Any]:
        return {
            "evidence_id": "ev_context_table",
            "claim": "interest expense values",
            "quote_span": "interest expense values",
            "metadata": {
                "table_view": "column_row_window",
                "structured_cells": [
                    {"column_headers": ["segment", "steel"], "value_text": "718,937"},
                    {"column_headers": ["segment", "trading"], "value_text": "284,056"},
                    {"column_headers": ["segment", "construction"], "value_text": "105,102"},
                    {"column_headers": ["segment", "total"], "value_text": "1,180,096"},
                ],
            },
        }

    def test_direct_lookup_row_marks_unscoped_multi_context_table_as_ambiguous(self) -> None:
        self.assertTrue(
            direct_lookup_row_is_ambiguous_context_table(
                {},
                self._context_dependent_lookup_evidence(),
                query="Find the consolidated interest expense.",
                active_subtask={"query": "Find interest expense.", "metric_label": "interest expense"},
                required_operands=[{"label": "interest expense", "concept": "interest_expense"}],
            )
        )

    def test_direct_lookup_row_allows_context_table_when_any_task_surface_requests_scope(self) -> None:
        base_operand = {"label": "interest expense", "concept": "interest_expense"}
        cases = [
            ("top_query", "Find steel segment interest expense.", {}, [base_operand]),
            ("active_query", "Find interest expense.", {"query": "Find steel segment interest expense."}, [base_operand]),
            ("metric_label", "Find interest expense.", {"metric_label": "segment interest expense"}, [base_operand]),
            ("operand_label", "Find interest expense.", {}, [{**base_operand, "label": "segment interest expense"}]),
            ("operand_concept", "Find interest expense.", {}, [{**base_operand, "concept": "segment_interest_expense"}]),
            ("operand_alias", "Find interest expense.", {}, [{**base_operand, "aliases": ["segment interest"]}]),
            (
                "binding_segment",
                "Find interest expense.",
                {},
                [{**base_operand, "binding_policy": {"segment_label": "steel segment"}}],
            ),
            (
                "binding_entity",
                "Find interest expense.",
                {},
                [{**base_operand, "binding_policy": {"entity_label": "steel segment"}}],
            ),
            (
                "constraint_scope",
                "Find interest expense.",
                {},
                [{**base_operand, "constraints": {"segment_scope": "steel segment"}}],
            ),
        ]

        for name, query, active_subtask, required_operands in cases:
            with self.subTest(name=name):
                self.assertFalse(
                    direct_lookup_row_is_ambiguous_context_table(
                        {},
                        self._context_dependent_lookup_evidence(),
                        query=query,
                        active_subtask=active_subtask,
                        required_operands=required_operands,
                    )
                )

    def test_direct_lookup_row_applies_evidence_view_and_cell_count_gates_before_surface_fallback(self) -> None:
        evidence = self._context_dependent_lookup_evidence()
        self.assertFalse(
            direct_lookup_row_is_ambiguous_context_table(
                {},
                None,
                query="Find interest expense.",
                active_subtask={},
                required_operands=[],
            )
        )

        wrong_view = deepcopy(evidence)
        wrong_view["metadata"]["table_view"] = "row_window"
        self.assertFalse(
            direct_lookup_row_is_ambiguous_context_table(
                {},
                wrong_view,
                query="Find interest expense.",
                active_subtask={},
                required_operands=[],
            )
        )

        too_few_cells = deepcopy(evidence)
        too_few_cells["claim"] = "segment values"
        too_few_cells["metadata"]["structured_cells"] = too_few_cells["metadata"]["structured_cells"][:3]
        self.assertFalse(
            direct_lookup_row_is_ambiguous_context_table(
                {},
                too_few_cells,
                query="Find interest expense.",
                active_subtask={},
                required_operands=[],
            )
        )

    def test_direct_lookup_row_requires_distinct_headers_then_uses_raw_surface_fallback(self) -> None:
        duplicate_headers = self._context_dependent_lookup_evidence()
        for cell in duplicate_headers["metadata"]["structured_cells"]:
            cell["column_headers"] = ["segment", "steel"]

        self.assertFalse(
            direct_lookup_row_is_ambiguous_context_table(
                {},
                duplicate_headers,
                query="Find interest expense.",
                active_subtask={},
                required_operands=[],
            )
        )

        raw_surface_evidence = deepcopy(duplicate_headers)
        raw_surface_evidence["metadata"]["table_header_context"] = "steel segment values"
        self.assertTrue(
            direct_lookup_row_is_ambiguous_context_table(
                {},
                raw_surface_evidence,
                query="Find interest expense.",
                active_subtask={},
                required_operands=[],
            )
        )

    @staticmethod
    def _merge_required_operands() -> List[Dict[str, Any]]:
        return [
            {
                "label": "target",
                "concept": "target_metric",
                "role": "numerator_1",
                "period": "2023",
            },
            {
                "label": "base",
                "concept": "base_metric",
                "role": "denominator_1",
                "period": "2023",
            },
            {
                "label": "adjustment",
                "concept": "adjustment_metric",
                "role": "subtrahend",
                "period": "2023",
            },
        ]

    def test_requirement_conflict_and_match_contract(self) -> None:
        operand = {
            "label": "target metric",
            "aliases": ["target alias"],
            "concept": "target_concept",
            "role": "current_period",
            "period_hint": "2023",
            "unit_family": "KRW",
            "surface_contract": {
                "positive": ["target metric"],
                "negative": ["surrogate metric"],
            },
        }
        baseline = {
            "label": "target metric",
            "matched_operand_label": "target metric",
            "matched_operand_concept": "target_concept",
            "matched_operand_role": "current_period",
            "period": "2023",
            "period_source": "evidence_surface",
            "raw_value": "100",
            "normalized_unit": "KRW",
        }
        cases = [
            ("baseline", {}, False, True),
            ("concept conflict", {"concept": "other_concept"}, True, False),
            (
                "evidence period conflict",
                {"label": "2023 target metric", "period": "2022"},
                True,
                False,
            ),
            (
                "role mismatch",
                {"matched_operand_role": "prior_period"},
                False,
                False,
            ),
            ("unit conflict", {"normalized_unit": "PERCENT"}, True, False),
            (
                "negative surface",
                {"label": "surrogate metric", "matched_operand_label": ""},
                True,
                False,
            ),
        ]

        for name, updates, expected_conflict, expected_match in cases:
            with self.subTest(name=name):
                row = {**baseline, **updates}
                self.assertEqual(
                    _operand_row_conflicts_with_requirement(row, operand),
                    expected_conflict,
                )
                self.assertEqual(
                    _operand_row_matches_requirement(row, operand),
                    expected_match,
                )

        source_anchor_only = {
            "label": "unrelated",
            "source_anchor": "table with target alias",
            "period": "2023",
            "normalized_unit": "KRW",
        }
        self.assertTrue(
            _operand_row_matches_requirement(source_anchor_only, operand)
        )

    def test_missing_requirements_preserve_order_and_copy_rows(self) -> None:
        required = [
            {"label": "first", "concept": "first_concept"},
            {"label": "covered", "concept": "covered_concept"},
            {"label": "last", "concept": "last_concept"},
        ]
        rows = [
            {
                "label": "covered",
                "matched_operand_concept": "covered_concept",
            }
        ]
        required_before = deepcopy(required)
        rows_before = deepcopy(rows)

        missing = _missing_required_operands(required, rows)

        self.assertEqual(missing, [required[0], required[2]])
        self.assertIsNot(missing[0], required[0])
        self.assertIsNot(missing[1], required[2])
        self.assertEqual(required, required_before)
        self.assertEqual(rows, rows_before)
        missing[0]["label"] = "mutated"
        self.assertEqual(required[0]["label"], "first")

    def test_direct_evidence_surface_requires_value_and_operand_on_same_surface(self) -> None:
        row = {"raw_value": "(1,234)"}
        operand = {
            "label": "Target Metric",
            "surface_contract": {
                "positive": ["Target Metric"],
                "negative": ["Excluded Metric"],
            },
        }
        cases = [
            (
                "direct text",
                {"claim": "Target Metric (1,234)"},
                True,
            ),
            (
                "separate text surfaces",
                {"claim": "Target Metric", "quote_span": "(1,234)"},
                False,
            ),
            (
                "structured value record",
                {
                    "metadata": {
                        "table_value_records_json": (
                            '[{"semantic_label": "Target Metric", '
                            '"cells": [{"value_text": "1,234"}]}]'
                        )
                    }
                },
                True,
            ),
            (
                "negative surface",
                {"claim": "Excluded Metric Target Metric (1,234)"},
                False,
            ),
            (
                "malformed structured metadata",
                {"metadata": {"table_row_records_json": "{"}},
                False,
            ),
        ]

        for label, evidence_item, expected in cases:
            with self.subTest(label=label):
                self.assertEqual(
                    _operand_row_has_direct_evidence_surface(row, evidence_item, operand),
                    expected,
                )

    def test_lookup_direct_support_preserves_short_circuits_and_evidence_precedence(self) -> None:
        row = {
            "label": "Target Metric",
            "raw_value": "123",
            "source_anchor": " [source] ",
        }
        permissive_operand = {"label": "Target Metric"}
        contracted_operand = {
            "label": "Target Metric",
            "binding_policy": {"require_surface_contract_for_direct_lookup": True},
            "surface_contract": {"positive": ["Specific Target"], "negative": []},
        }
        mismatched_direct_evidence = {
            "claim": "Other Metric 999",
            "source_context": "Target Metric 123",
        }
        supported_evidence = {"claim": "Target Metric 123"}
        inputs_before = deepcopy(
            [row, permissive_operand, contracted_operand, mismatched_direct_evidence, supported_evidence]
        )

        self.assertTrue(_llm_lookup_operand_has_direct_support({}, None, []))
        self.assertTrue(_llm_lookup_operand_has_direct_support(row, None, [permissive_operand]))
        self.assertFalse(_llm_lookup_operand_has_direct_support(row, None, [contracted_operand]))
        self.assertFalse(
            _llm_lookup_operand_has_direct_support(
                row,
                mismatched_direct_evidence,
                [permissive_operand],
            )
        )
        self.assertFalse(
            _llm_lookup_operand_has_direct_support(
                row,
                supported_evidence,
                [contracted_operand, permissive_operand],
            )
        )
        self.assertTrue(
            _llm_lookup_operand_has_direct_support(
                row,
                supported_evidence,
                [permissive_operand, contracted_operand],
            )
        )
        self.assertEqual(
            [row, permissive_operand, contracted_operand, mismatched_direct_evidence, supported_evidence],
            inputs_before,
        )

    def test_evidence_index_and_row_lookup_preserve_alias_precedence(self) -> None:
        evidence_items = [
            {"evidence_id": " duplicate ", "marker": "first"},
            {"evidence_id": "duplicate", "marker": "last"},
            {"evidence_id": "recon::primary", "marker": "reconciliation alias"},
            {"evidence_id": "source", "marker": "later source id"},
        ]
        evidence_items_before = deepcopy(evidence_items)

        evidence_by_id = _evidence_items_by_id(evidence_items)

        self.assertEqual(evidence_by_id["duplicate"]["marker"], "last")
        self.assertIsNot(evidence_by_id["duplicate"], evidence_items[1])
        self.assertIs(
            _evidence_item_for_operand_row(
                {"evidence_id": "primary", "source_row_id": "source"},
                evidence_by_id,
            ),
            evidence_by_id["recon::primary"],
        )
        self.assertEqual(
            _evidence_item_for_operand_row(
                {"evidence_id": "recon::plain"},
                {"plain": {"marker": "stripped alias"}},
            ),
            {"marker": "stripped alias"},
        )
        self.assertEqual(
            _evidence_item_for_operand_row(
                {"evidence_id": "primary"},
                {
                    "primary": {},
                    "recon::primary": {"marker": "truthy fallback"},
                },
            ),
            {"marker": "truthy fallback"},
        )
        self.assertIsNone(_evidence_item_for_operand_row({}, evidence_by_id))
        self.assertEqual(evidence_items, evidence_items_before)

    def test_required_surface_filter_preserves_identity_and_no_evidence_contract(self) -> None:
        rows: List[Dict[str, Any]] = [
            {
                "label": "Target Metric",
                "raw_value": "100",
                "evidence_id": "missing",
            },
            {
                "label": "Target Metric",
                "raw_value": "200",
                "evidence_id": "supported",
            },
        ]
        evidence_items = [
            {
                "evidence_id": "supported",
                "claim": "Target Metric 200",
            }
        ]
        permissive_operand = {"label": "Target Metric"}
        contracted_operand = {
            "label": "Target Metric",
            "binding_policy": {"require_surface_contract_for_direct_lookup": True},
            "surface_contract": {"positive": ["Target Metric"], "negative": []},
        }
        empty_rows: List[Dict[str, Any]] = []

        self.assertIs(
            _filter_operand_rows_by_required_surface_contract(empty_rows, [], [permissive_operand]),
            empty_rows,
        )
        self.assertIs(
            _filter_operand_rows_by_required_surface_contract(rows, evidence_items, []),
            rows,
        )
        permissive = _filter_operand_rows_by_required_surface_contract(
            rows,
            evidence_items,
            [permissive_operand],
            require_direct_support=True,
        )
        self.assertEqual(permissive, rows)
        self.assertIs(permissive[0], rows[0])
        self.assertIs(permissive[1], rows[1])

        contracted = _filter_operand_rows_by_required_surface_contract(
            rows,
            evidence_items,
            [contracted_operand],
            require_direct_support=True,
        )
        self.assertEqual(contracted, [rows[1]])
        self.assertIs(contracted[0], rows[1])
        self.assertTrue(
            _operand_row_satisfies_required_surface_contract(
                rows[0],
                {},
                [permissive_operand],
                require_direct_support=True,
            )
        )

    def test_segment_surface_match_uses_variants_and_word_boundaries(self) -> None:
        cases = [
            ("empty label", "", ["anything"], True),
            ("direct label", "Division A", ["Division A result"], True),
            ("trimmed punctuation", "(Division A)", ["Division A result"], True),
            ("substring only", "Division A", ["Division Alpha result"], False),
            ("missing label", "Division A", ["Division B result"], False),
        ]

        for label, segment_label, surfaces, expected in cases:
            with self.subTest(label=label):
                self.assertEqual(
                    _evidence_surface_contains_segment_label(segment_label, surfaces),
                    expected,
                )

    def test_operand_context_signals_preserve_source_and_display_contract(self) -> None:
        coherent_rows = [
            {
                "table_source_id": " table_a ",
                "source_table_id": "ignored_table",
                "raw_unit": " million ",
            },
            {
                "source_table_id": "table_a",
                "raw_unit": "million",
                "normalized_unit": "KRW",
            },
            {
                "source_anchor": "",
                "raw_unit": "",
                "normalized_unit": "PERCENT",
            },
        ]

        self.assertTrue(_operand_rows_have_single_table_context(coherent_rows))
        self.assertEqual(_operand_row_display_unit_set(coherent_rows), {"million"})
        self.assertFalse(_operand_rows_have_single_table_context([]))
        self.assertFalse(_operand_rows_have_single_table_context([{}]))
        self.assertFalse(
            _operand_rows_have_single_table_context(
                [*coherent_rows, {"source_anchor": "table_b"}]
            )
        )

    def test_required_role_conflict_compares_only_normalized_matching_roles(self) -> None:
        left_rows = [
            {
                "row_id": "left_numerator",
                "matched_operand_role": " NUMERATOR_1 ",
                "normalized_value": 100.0,
            },
            {
                "row_id": "left_prior",
                "role": "Prior_Period",
                "normalized_value": 70.0,
            },
            {"row_id": "left_unbound", "normalized_value": 1.0},
        ]
        right_rows = [
            {
                "row_id": "right_numerator",
                "matched_operand_role": "numerator_1",
                "role": "denominator_1",
                "normalized_value": 100.0,
            },
            {
                "row_id": "right_prior",
                "role": "prior_period",
                "normalized_value": 70.0,
            },
            {
                "row_id": "right_denominator",
                "role": "denominator_1",
                "normalized_value": 999.0,
            },
        ]
        compared_pairs: List[tuple[str, str]] = []

        self.assertFalse(
            _operand_rows_conflict_by_required_role(
                left_rows,
                right_rows,
                operand_row_value_differs=lambda left, right: (
                    compared_pairs.append((left["row_id"], right["row_id"]))
                    or False
                ),
            )
        )
        self.assertEqual(
            compared_pairs,
            [
                ("left_numerator", "right_numerator"),
                ("left_prior", "right_prior"),
            ],
        )

        right_rows[0]["normalized_value"] = 101.0
        self.assertTrue(
            _operand_rows_conflict_by_required_role(
                left_rows,
                right_rows,
                operand_row_value_differs=lambda left, right: (
                    left.get("normalized_value") != right.get("normalized_value")
                ),
            )
        )

    def test_operand_slot_collapse_requires_shared_source_and_value(self) -> None:
        current_row = {
            "matched_operand_role": "current_period",
            "source_row_id": "row_income",
            "source_row_ids": ["row_income"],
            "raw_value": "1,000",
            "normalized_value": 1000.0,
        }
        stale_prior_row = {
            **current_row,
            "matched_operand_role": "prior_period",
        }
        real_prior_row = {
            **stale_prior_row,
            "raw_value": "700",
            "normalized_value": 700.0,
        }

        self.assertTrue(
            _period_comparison_operand_rows_collapse_to_same_slot(
                [current_row, stale_prior_row]
            )
        )
        self.assertFalse(
            _period_comparison_operand_rows_collapse_to_same_slot(
                [current_row, real_prior_row]
            )
        )
        self.assertTrue(
            _period_comparison_operand_rows_collapse_to_same_slot(
                [
                    {**current_row, "matched_operand_role": "minuend"},
                    {**stale_prior_row, "matched_operand_role": "subtrahend"},
                ]
            )
        )

        numerator = {**current_row, "matched_operand_role": "numerator_1"}
        denominator = {**stale_prior_row, "matched_operand_role": "denominator_1"}
        self.assertTrue(
            _ratio_operand_rows_collapse_to_same_slot([numerator, denominator])
        )
        self.assertFalse(
            _ratio_operand_rows_collapse_to_same_slot(
                [numerator, {**denominator, "source_row_id": "row_other", "source_row_ids": ["row_other"]}]
            )
        )
        self.assertFalse(
            _operand_row_groups_collapse_to_same_slot(
                [[{"raw_value": "1"}], [{"raw_value": "1"}]]
            )
        )
        self.assertFalse(_operand_row_groups_collapse_to_same_slot([[], [denominator]]))

    def _sibling_selector_fixture(self) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        current = _operand_row(
            "task_output:task_num",
            label="target",
            role="numerator_1",
            value=100.0,
            table_source_id="table_good",
            source_row_ids=["task_output:task_num", "chunk_good"],
            dependency_resolved=True,
            source_task_id="task_num",
        )
        direct_rows = [
            _operand_row(
                "direct_good",
                label="target",
                role="numerator_1",
                value=80.0,
                table_source_id="table_good",
                source_row_ids=["direct_good", "chunk_good"],
            ),
            _operand_row(
                "good_den",
                label="base",
                role="denominator_1",
                value=40.0,
                table_source_id="table_good",
            ),
            _operand_row(
                "direct_alt",
                label="target",
                role="numerator_1",
                value=70.0,
                table_source_id="table_alt",
            ),
            _operand_row(
                "alt_den",
                label="base",
                role="denominator_1",
                value=35.0,
                table_source_id="table_alt",
            ),
        ]
        return current, direct_rows

    def test_merge_supplemental_selection_is_permutation_invariant(self) -> None:
        required_operands = self._merge_required_operands()
        preferred = [
            _merge_operand_row(
                "preferred_target",
                label="target",
                concept="target_metric",
                role="numerator_1",
                value=100.0,
            )
        ]
        supplemental = [
            _merge_operand_row(
                "supplemental_base",
                label="base",
                concept="base_metric",
                role="denominator_1",
                value=40.0,
            ),
            _merge_operand_row(
                "supplemental_adjustment",
                label="adjustment",
                concept="adjustment_metric",
                role="subtrahend",
                value=5.0,
            ),
            _merge_operand_row(
                "covered_target_noise",
                label="target",
                concept="target_metric",
                role="numerator_1",
                value=999.0,
            ),
            _merge_operand_row(
                "unrelated_noise",
                label="noise",
                concept="noise_metric",
                role="noise_role",
                value=777.0,
            ),
        ]

        for ordered_rows in permutations(supplemental):
            merged = merge_operand_rows(
                preferred,
                list(ordered_rows),
                required_operands=required_operands,
            )

            self.assertEqual(
                [row.get("evidence_id") for row in merged],
                ["preferred_target", "supplemental_base", "supplemental_adjustment"],
            )

    def test_required_candidate_merge_precedence_matrix_and_copy_contracts(self) -> None:
        required_operands = self._merge_required_operands()[:2]

        def row(candidate_id: str, role: str, value: float) -> Dict[str, Any]:
            is_target = role == "numerator_1"
            return _merge_operand_row(
                candidate_id,
                label="target" if is_target else "base",
                concept="target_metric" if is_target else "base_metric",
                role=role,
                value=value,
            )

        current_target = row("current_target", "numerator_1", 100.0)
        current_target["metadata"] = {"nested": ["current"]}
        candidate_target = row("candidate_target", "numerator_1", 200.0)
        candidate_base = row("candidate_base", "denominator_1", 40.0)
        coherent_target = row("coherent_target", "numerator_1", 300.0)
        current_first = "current_operand_rows_preferred"
        candidate_first = "complete_ratio_candidate_rows_preferred"
        current_rows = [current_target]
        complete_candidates = [candidate_target, candidate_base]
        cases = [
            (
                "no candidates", "growth_rate", current_rows, [], [],
                ("current_target",), (), False, False, "no_candidate_rows",
            ),
            (
                "nonratio current first", "difference", current_rows, complete_candidates, [],
                ("current_target", "candidate_base"),
                ("candidate_target", "candidate_base"), True, False, current_first,
            ),
            (
                "partial ratio current first", "ratio", current_rows, [candidate_base], [],
                ("current_target", "candidate_base"), ("candidate_base",),
                False, False, current_first,
            ),
            (
                "complete ratio candidates first", "ratio", current_rows, complete_candidates, [],
                ("candidate_target", "candidate_base"),
                ("candidate_target", "candidate_base"), True, False, candidate_first,
            ),
            (
                "coherent ratio candidates first", "ratio", current_rows,
                complete_candidates, [coherent_target],
                ("coherent_target", "candidate_base"),
                ("coherent_target", "candidate_base"), True, True, candidate_first,
            ),
        ]

        for case in cases:
            (
                name, operation_family, current_rows, candidate_rows, coherent_rows,
                selected_ids, merged_ids, covers_required, coherent_applied, reason,
            ) = case
            with self.subTest(name=name):
                merge_input = RequiredOperandCandidateMergeInput(
                    operation_family=operation_family,
                    required_operands=required_operands,
                    current_operand_rows=current_rows,
                    candidate_operand_rows=candidate_rows,
                    coherent_candidate_rows=coherent_rows,
                )
                input_before = deepcopy(merge_input)

                result = resolve_required_operand_candidate_merge(merge_input)

                self.assertEqual(merge_input, input_before)
                self.assertEqual(
                    (
                        tuple(row["evidence_id"] for row in result.selected_operand_rows),
                        tuple(row["evidence_id"] for row in result.merged_candidate_rows),
                        result.candidate_rows_cover_required,
                        result.coherent_candidate_merge_applied,
                        result.reason,
                    ),
                    (selected_ids, merged_ids, covers_required, coherent_applied, reason),
                )
                self.assertEqual(
                    result.merged_candidate_rows is candidate_rows,
                    not bool(coherent_rows),
                )
                if not candidate_rows:
                    self.assertIs(result.selected_operand_rows, current_rows)
                    continue
                self.assertIsNot(result.selected_operand_rows, current_rows)
                if name == "nonratio current first":
                    self.assertIsNot(result.selected_operand_rows[0], current_rows[0])
                    self.assertIs(
                        result.selected_operand_rows[0]["metadata"],
                        current_rows[0]["metadata"],
                    )

    def test_direct_acceptance_preserves_stage_order_and_short_circuits(self) -> None:
        row_ids = (
            "keep_1",
            "drop_requirement",
            "drop_surface",
            "drop_first_ambiguity",
            "drop_support",
            "drop_second_ambiguity",
            "keep_2",
        )
        rows = [{"evidence_id": row_id, "metadata": {"row": row_id}} for row_id in row_ids]
        events = []
        ambiguity_calls: Dict[str, int] = {}
        ambiguity_subtasks = []

        def passes(stage: str, row: Dict[str, Any]) -> bool:
            row_id = row["evidence_id"]
            events.append((stage, row_id))
            return row_id != f"drop_{stage}"

        def matches(row: Dict[str, Any], _operand: Dict[str, Any]) -> bool:
            return passes("requirement", row)

        def has_surface(row: Dict[str, Any], *_args: Any, **_kwargs: Any) -> bool:
            return passes("surface", row)

        def has_direct_support(row: Dict[str, Any], *_args: Any) -> bool:
            return passes("support", row)

        def is_ambiguous(row: Dict[str, Any], *_args: Any, **kwargs: Any) -> bool:
            row_id = row["evidence_id"]
            call_number = ambiguity_calls.get(row_id, 0) + 1
            ambiguity_calls[row_id] = call_number
            stage = "first_ambiguity" if call_number == 1 else "second_ambiguity"
            ambiguity_subtasks.append(kwargs["active_subtask"])
            events.append((stage, row_id))
            self.assertEqual(kwargs["query"], "original query")
            return row_id == f"drop_{stage}"

        acceptance_input = DirectStructuredOperandAcceptanceInput(
            direct_operand_rows=rows,
            evidence_items=[],
            required_operands=[{"label": "metric", "role": "primary_value"}],
            operation_family="lookup",
            ambiguity_query="original query",
            ambiguity_active_subtask={"task_id": "original"},
        )
        input_before = deepcopy(acceptance_input)
        with (
            patch.object(operand_resolution, "_operand_row_matches_requirement", side_effect=matches),
            patch.object(operand_resolution, "_operand_row_satisfies_required_surface_contract", side_effect=has_surface),
            patch.object(operand_resolution, "direct_lookup_row_is_ambiguous_context_table", side_effect=is_ambiguous),
            patch.object(operand_resolution, "_llm_lookup_operand_has_direct_support", side_effect=has_direct_support),
            patch.object(operand_resolution, "_evidence_items_by_id", wraps=operand_resolution._evidence_items_by_id) as evidence_index,
        ):
            result = resolve_direct_structured_operand_acceptance(acceptance_input)

        stage_order = tuple(dict.fromkeys(stage for stage, _row_id in events))
        observed = [
            (stage, tuple(row_id for event_stage, row_id in events if event_stage == stage))
            for stage in stage_order
        ]
        self.assertEqual(acceptance_input, input_before)
        self.assertEqual(evidence_index.call_count, 2)
        self.assertTrue(
            all(
                subtask == acceptance_input.ambiguity_active_subtask
                and subtask is not acceptance_input.ambiguity_active_subtask
                for subtask in ambiguity_subtasks
            )
        )
        self.assertEqual(len({id(subtask) for subtask in ambiguity_subtasks}), len(ambiguity_subtasks))
        self.assertEqual(
            observed,
            [
                ("requirement", row_ids),
                ("surface", ("keep_1", "drop_surface", "drop_first_ambiguity", "drop_support", "drop_second_ambiguity", "keep_2")),
                ("first_ambiguity", ("keep_1", "drop_first_ambiguity", "drop_support", "drop_second_ambiguity", "keep_2")),
                ("support", ("keep_1", "drop_support", "drop_second_ambiguity", "keep_2")),
                ("second_ambiguity", ("keep_1", "drop_second_ambiguity", "keep_2")),
            ],
        )
        self.assertEqual(
            [row["evidence_id"] for row in result.accepted_operand_rows],
            ["keep_1", "keep_2"],
        )
        self.assertIs(result.accepted_operand_rows[0], rows[0])
        self.assertIs(result.accepted_operand_rows[1], rows[-1])
        self.assertEqual(
            (
                result.required_surface_filter_applied,
                result.pre_lookup_ambiguity_filter_applied,
                result.lookup_direct_support_filter_applied,
                result.lookup_ambiguity_filter_applied,
            ),
            (True, True, True, True),
        )

    def test_direct_acceptance_stage_matrix_and_noop_identity(self) -> None:
        row = {"evidence_id": "direct", "metadata": {"nested": ["value"]}}
        required = [{"label": "metric", "role": "primary_value"}]
        cases = (
            ("empty lookup", [], required, "lookup", (False, False, False, False), True),
            ("no-stage difference", [row], [], "difference", (False, False, False, False), True),
            ("no-required lookup", [row], [], "lookup", (False, False, False, True), False),
            ("required difference", [row], required, "difference", (True, True, False, False), False),
            ("required ratio", [row], required, "ratio", (True, True, False, False), False),
            ("required lookup", [row], required, "lookup", (True, True, True, True), False),
            ("required single value", [row], required, "single_value", (True, True, True, True), False),
        )

        for name, rows, required_operands, operation_family, expected_flags, expected_identity in cases:
            with self.subTest(name=name):
                acceptance_input = DirectStructuredOperandAcceptanceInput(
                    direct_operand_rows=rows,
                    evidence_items=[],
                    required_operands=required_operands,
                    operation_family=operation_family,
                    ambiguity_query="query",
                    ambiguity_active_subtask={"task_id": "task"},
                )
                input_before = deepcopy(acceptance_input)
                with (
                    patch.object(operand_resolution, "_operand_row_matches_requirement", return_value=True),
                    patch.object(operand_resolution, "_operand_row_satisfies_required_surface_contract", return_value=True) as surface_check,
                    patch.object(operand_resolution, "direct_lookup_row_is_ambiguous_context_table", return_value=False),
                    patch.object(operand_resolution, "_llm_lookup_operand_has_direct_support", return_value=True),
                ):
                    result = resolve_direct_structured_operand_acceptance(acceptance_input)

                self.assertEqual(acceptance_input, input_before)
                self.assertEqual(
                    (
                        result.required_surface_filter_applied,
                        result.pre_lookup_ambiguity_filter_applied,
                        result.lookup_direct_support_filter_applied,
                        result.lookup_ambiguity_filter_applied,
                    ),
                    expected_flags,
                )
                self.assertEqual(result.accepted_operand_rows is rows, expected_identity)
                self.assertEqual(
                    [item["evidence_id"] for item in result.accepted_operand_rows],
                    [item["evidence_id"] for item in rows],
                )
                if rows and required_operands:
                    self.assertEqual(
                        surface_check.call_args.kwargs["require_direct_support"],
                        operation_family == "ratio",
                    )

    def test_direct_target_metric_row_unit_conflict_matrix(self) -> None:
        conflicts = operand_resolution.direct_target_metric_row_conflicts_existing_units

        def target(**updates: Any) -> Dict[str, Any]:
            row = {
                "marker": "target",
                "label": "target metric",
                "matched_operand_label": "target metric",
                "matched_operand_role": "primary_value",
                "raw_value": "100",
                "normalized_value": 100.0,
                "normalized_unit": "KRW",
            }
            row.update(updates)
            return row

        def existing(**updates: Any) -> Dict[str, Any]:
            row = {
                "marker": "existing",
                "label": "target metric",
                "matched_operand_label": "target metric",
                "matched_operand_role": "primary_value",
                "raw_value": "100",
                "normalized_value": 100.0,
                "normalized_unit": "KRW",
            }
            row.update(updates)
            return row

        required = [{"label": "target metric", "role": "primary_value", "required": True}]

        class TruthBomb:
            def __bool__(self):
                raise RuntimeError("truthiness accessed")

        self.assertFalse(conflicts({}, TruthBomb(), TruthBomb()))
        self.assertFalse(conflicts(target(), [], TruthBomb()))

        for name, existing_units, target_unit, expected in (
            ("blank existing", [" "], "KRW", False),
            ("unknown existing", [" UNKNOWN "], "KRW", False),
            ("blank target", [" KRW "], " ", True),
            ("unknown target", ["krw"], " unknown ", True),
            ("mismatched target", ["KRW"], "COUNT", True),
            ("same normalized target", [" krw "], "KRW", False),
            ("one matching existing unit", ["COUNT", "KRW"], "krw", False),
        ):
            with self.subTest(unit_case=name):
                self.assertEqual(
                    conflicts(
                        target(normalized_unit=target_unit),
                        [existing(normalized_unit=unit) for unit in existing_units],
                        required,
                    ),
                    expected,
                )

        copy_events: List[str] = []

        class CopyTrackedRow(Mapping):
            def __init__(self, marker: str) -> None:
                self.values = existing(marker=marker)

            def keys(self):
                copy_events.append(f"copy:{self.values['marker']}")
                return self.values.keys()

            def __getitem__(self, key):
                return self.values[key]

            def __iter__(self):
                return iter(self.values)

            def __len__(self):
                return len(self.values)

        first_row = CopyTrackedRow("first")
        second_row = CopyTrackedRow("second")
        match_events: List[tuple[str, str]] = []
        ordered_required = [{"marker": "first"}, {"marker": "second"}]

        def ordered_match(row, operand):
            match_events.append((row["marker"], operand["marker"]))
            if row["marker"] == "target":
                return operand["marker"] == "second"
            return row["marker"] == operand["marker"]

        with patch.object(
            operand_resolution,
            "_operand_row_matches_requirement",
            side_effect=ordered_match,
        ):
            self.assertFalse(
                conflicts(target(), [first_row, second_row], ordered_required)  # type: ignore[list-item]
            )
        self.assertEqual(
            match_events,
            [
                ("first", "first"),
                ("second", "first"),
                ("second", "second"),
                ("target", "first"),
                ("target", "second"),
            ],
        )
        self.assertEqual(copy_events, ["copy:first", "copy:first", "copy:second", "copy:second", "copy:second"])

        copy_events.clear()
        empty_required_row = CopyTrackedRow("empty-required")
        self.assertFalse(conflicts(target(), [empty_required_row], []))  # type: ignore[list-item]
        self.assertEqual(copy_events, ["copy:empty-required"])

        class LaterStringBomb:
            def __str__(self):
                raise RuntimeError("later unit accessed")

        with patch.object(
            operand_resolution,
            "_operand_row_matches_requirement",
            return_value=False,
        ):
            self.assertFalse(
                conflicts(
                    target(normalized_unit=LaterStringBomb()),
                    [existing()],
                    [{"marker": "unmatched"}],
                )
            )

        operand_copy_count = 0

        class AggregatePreferredOperand(Mapping):
            values = {
                "label": "target metric",
                "role": "primary_value",
                "binding_policy": {"prefer_value_roles": ["aggregate"]},
            }

            def keys(self):
                nonlocal operand_copy_count
                operand_copy_count += 1
                return self.values.keys()

            def __getitem__(self, key):
                return self.values[key]

            def __iter__(self):
                return iter(self.values)

            def __len__(self):
                return len(self.values)

        aggregate_preferred = AggregatePreferredOperand()

        class StringBomb:
            def __str__(self):
                raise RuntimeError("later target surface accessed")

        self.assertFalse(
            conflicts(
                target(value_role=StringBomb(), aggregation_stage=StringBomb()),
                [existing(normalized_value=1.0, source_row_id="source")],
                [aggregate_preferred, TruthBomb()],
            )
        )
        self.assertEqual(operand_copy_count, 1)

        aggregate_like_cases = (
            ("value role", {"value_role": " aggregate ", "aggregate_label": StringBomb()}),
            ("direct stage", {"aggregation_stage": " DIRECT ", "aggregate_label": StringBomb()}),
            ("final stage", {"aggregation_stage": "final", "aggregate_label": StringBomb()}),
            ("subtotal stage", {"aggregation_stage": "subtotal", "aggregate_label": StringBomb()}),
            ("aggregate label", {"aggregate_label": " total "}),
        )
        for name, updates in aggregate_like_cases:
            with self.subTest(aggregate_like=name):
                self.assertTrue(
                    conflicts(
                        target(normalized_value=200.0, **updates),
                        [existing(source_row_id="source")],
                        [],
                    )
                )

        class FloatBomb:
            def __init__(self, error: Exception) -> None:
                self.error = error

            def __float__(self):
                raise self.error

        for error in (TypeError("bad float"), ValueError("bad float")):
            with self.subTest(value_fallback=type(error).__name__):
                self.assertFalse(
                    conflicts(
                        target(value_role="aggregate", normalized_value=FloatBomb(error), raw_value="100"),
                        [existing(normalized_value=FloatBomb(error), raw_value="100", source_row_id="source")],
                        [],
                    )
                )
                self.assertTrue(
                    conflicts(
                        target(value_role="aggregate", normalized_value=FloatBomb(error), raw_value="200"),
                        [existing(normalized_value=FloatBomb(error), raw_value="100", source_row_id="source")],
                        [],
                    )
                )

        same_value = existing(normalized_value=200.0, source_row_id=StringBomb())
        self.assertFalse(conflicts(target(value_role="aggregate", normalized_value=200.0), [same_value], []))

        structured_signals = (
            ("evidence id", {"evidence_id": "evidence"}),
            ("source row id", {"source_row_id": "row"}),
            ("source row ids", {"source_row_ids": ["row"]}),
            ("table", {"table_source_id": "table"}),
            ("statement", {"statement_type": "notes"}),
            ("anchor", {"source_anchor": "[anchor]"}),
        )
        for name, updates in structured_signals:
            with self.subTest(structured=name):
                self.assertTrue(
                    conflicts(
                        target(value_role="aggregate", normalized_value=200.0),
                        [existing(**updates)],
                        [],
                    )
                )

        source_access_events: List[str] = []

        class SourceProbe:
            def __init__(self, name: str, value: str, *, explode: bool = False) -> None:
                self.name = name
                self.value = value
                self.explode = explode

            def __str__(self):
                source_access_events.append(self.name)
                if self.explode:
                    raise RuntimeError(f"{self.name} accessed")
                return self.value

        self.assertTrue(
            conflicts(
                target(value_role="aggregate", normalized_value=200.0),
                [
                    existing(
                        table_source_id=SourceProbe("table", ""),
                        statement_type=SourceProbe("statement", "notes"),
                        source_anchor=SourceProbe("anchor", "", explode=True),
                    )
                ],
                [],
            )
        )
        self.assertEqual(source_access_events, ["table", "statement"])
        source_access_events.clear()
        self.assertTrue(
            conflicts(
                target(value_role="aggregate", normalized_value=200.0),
                [
                    existing(
                        source_row_id="source",
                        table_source_id=SourceProbe("table", "", explode=True),
                    )
                ],
                [],
            )
        )
        self.assertEqual(source_access_events, [])
        self.assertFalse(
            conflicts(
                target(normalized_value=200.0),
                [existing(source_row_id="source")],
                [],
            )
        )
        self.assertFalse(
            conflicts(
                target(value_role="aggregate", normalized_value=200.0),
                [existing()],
                [],
            )
        )

        class ValueFloatBomb:
            def __float__(self):
                raise RuntimeError("mismatched existing unit value accessed")

        self.assertFalse(
            conflicts(
                target(value_role="aggregate"),
                [
                    existing(normalized_unit="COUNT", normalized_value=ValueFloatBomb()),
                    existing(normalized_unit="KRW"),
                ],
                [],
            )
        )

        target_row = target(value_role="aggregate", normalized_value=200.0)
        existing_rows = [existing(source_row_id="source")]
        required_rows = list(required)
        before = deepcopy((target_row, existing_rows, required_rows))
        self.assertTrue(conflicts(target_row, existing_rows, required_rows))
        self.assertEqual((target_row, existing_rows, required_rows), before)

    def test_direct_target_metric_row_unit_conflict_access_and_exception_contract(self) -> None:
        conflicts = operand_resolution.direct_target_metric_row_conflicts_existing_units

        target = {
            "label": "target metric",
            "raw_value": "200",
            "normalized_value": 200.0,
            "normalized_unit": "KRW",
            "value_role": "aggregate",
        }
        existing = {
            "label": "target metric",
            "raw_value": "100",
            "normalized_value": 100.0,
            "normalized_unit": "KRW",
            "source_row_id": "source",
        }

        class TruthBomb:
            def __bool__(self):
                raise RuntimeError("truthiness failed")

        class IterBomb:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("iteration failed")

        with self.assertRaisesRegex(RuntimeError, "truthiness failed"):
            conflicts(TruthBomb(), [], [])  # type: ignore[arg-type]
        with self.assertRaisesRegex(RuntimeError, "truthiness failed"):
            conflicts(target, TruthBomb(), [])  # type: ignore[arg-type]
        with self.assertRaisesRegex(RuntimeError, "iteration failed"):
            conflicts(target, IterBomb(), [])  # type: ignore[arg-type]
        with self.assertRaisesRegex(RuntimeError, "iteration failed"):
            conflicts(target, [existing], IterBomb())  # type: ignore[arg-type]

        class CopyBomb(Mapping):
            def keys(self):
                raise RuntimeError("copy failed")

            def __getitem__(self, key):
                raise KeyError(key)

            def __iter__(self):
                return iter(())

            def __len__(self):
                return 1

        with self.assertRaisesRegex(RuntimeError, "copy failed"):
            conflicts(target, [CopyBomb()], [])  # type: ignore[list-item]

        with patch.object(
            operand_resolution,
            "_operand_row_matches_requirement",
            side_effect=RuntimeError("matcher failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "matcher failed"):
                conflicts(target, [existing], [{"label": "target metric"}])

        with patch.object(
            operand_resolution,
            "_normalise_spaces",
            side_effect=RuntimeError("normalizer failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalizer failed"):
                conflicts(target, [existing], [])

        with patch.object(
            operand_resolution,
            "_clean_source_row_ids",
            side_effect=RuntimeError("source cleaner failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "source cleaner failed"):
                conflicts(target, [existing], [])

        class FloatBomb:
            def __float__(self):
                raise RuntimeError("float failed")

        with self.assertRaisesRegex(RuntimeError, "float failed"):
            conflicts(
                {**target, "normalized_value": FloatBomb()},
                [{**existing, "normalized_value": FloatBomb()}],
                [],
            )

        class CountingString:
            def __init__(self, value: str) -> None:
                self.value = value
                self.calls = 0

            def __str__(self):
                self.calls += 1
                return self.value

        existing_unit = CountingString(" KRW ")
        target_unit = CountingString("krw")
        self.assertFalse(
            conflicts(
                {**target, "normalized_unit": target_unit, "value_role": ""},
                [{**existing, "normalized_unit": existing_unit, "normalized_value": 200.0}],
                [],
            )
        )
        self.assertEqual((existing_unit.calls, target_unit.calls), (3, 1))

    def test_table_label_metadata_lookup_score_matrix(self) -> None:
        score = operand_resolution.table_label_metadata_lookup_score

        class AccessMapping(dict):
            def __init__(self, values, events, owner, *, failure_key=None):
                super().__init__(values)
                self._events = events
                self._owner = owner
                self._failure_key = failure_key

            def get(self, key, default=None):
                self._events.append(f"{self._owner}.get:{key}")
                if key == self._failure_key:
                    raise RuntimeError(f"{self._owner}:{key}")
                return super().get(key, default)

        class CopyMapping(Mapping):
            def __init__(self, values, events, *, failure_key=None):
                self._values = values
                self._events = events
                self._failure_key = failure_key

            def __iter__(self):
                self._events.append("metadata.iter")
                return iter(self._values)

            def __len__(self):
                return len(self._values)

            def __getitem__(self, key):
                self._events.append(f"metadata.getitem:{key}")
                if key == self._failure_key:
                    raise RuntimeError(f"metadata:{key}")
                return self._values[key]

        class CountingString:
            def __init__(self, value):
                self.value = value
                self.calls = 0

            def __str__(self):
                self.calls += 1
                return self.value

        class ExplodingString:
            def __str__(self):
                raise RuntimeError("string conversion")

        events = []
        lazy_evidence = AccessMapping({}, events, "evidence", failure_key="metadata")
        self.assertEqual(score({}, lazy_evidence), 0.0)
        self.assertEqual(events, [])

        events = []
        gated_slot = AccessMapping({"normalized_unit": "KRW"}, events, "slot")
        gated_metadata = CopyMapping({"table_value_labels_text": "  "}, events)
        gated_evidence = AccessMapping({"metadata": gated_metadata}, events, "evidence")
        self.assertEqual(score(gated_slot, gated_evidence), 0.0)
        self.assertEqual(
            events,
            [
                "slot.get:normalized_unit",
                "evidence.get:metadata",
                "metadata.iter",
                "metadata.getitem:table_value_labels_text",
            ],
        )

        table_metadata = {"table_value_labels_text": "metric 123", "unit_hint": "million"}
        for name, raw_unit, expected in (
            ("metadata unit fallback", "", 5.5),
            ("truthy whitespace suppresses fallback", "  ", 0.0),
        ):
            with self.subTest(name=name):
                self.assertEqual(
                    score(
                        {
                            "normalized_unit": "UNKNOWN",
                            "raw_unit": raw_unit,
                            "raw_value": "123",
                        },
                        {"metadata": table_metadata},
                    ),
                    expected,
                )

        unknown_evidence = {"metadata": {"table_value_labels_text": "metric"}}
        for raw_value, expected in (("123", 0.0), ("1,234", 5.0)):
            with self.subTest(raw_value=raw_value):
                self.assertEqual(
                    score(
                        {
                            "normalized_unit": "UNKNOWN",
                            "raw_unit": "",
                            "raw_value": raw_value,
                        },
                        unknown_evidence,
                    ),
                    expected,
                )

        known_slot = {"normalized_unit": "KRW", "raw_value": "1"}
        known_evidence = {"metadata": {"table_value_labels_text": "metric 1"}}

        def known_score(slot_update=None, metadata_update=None):
            return score(
                {**known_slot, **(slot_update or {})},
                {
                    "metadata": {
                        **known_evidence["metadata"],
                        **(metadata_update or {}),
                    }
                },
            )

        self.assertEqual(known_score(), 6.75)
        repeated_unit_hint = CountingString("million")
        for name, slot_update, metadata_update, expected in (
            ("unit hint", {}, {"unit_hint": repeated_unit_hint}, 7.25),
            ("table source", {}, {"table_source_id": "table:1"}, 7.25),
            ("aggregate role", {"value_role": "aggregate"}, {}, 8.75),
        ):
            with self.subTest(additive=name):
                self.assertEqual(
                    known_score(slot_update, metadata_update),
                    expected,
                )
        self.assertEqual(repeated_unit_hint.calls, 2)
        for stage, expected in (
            ("final", 9.25),
            ("direct", 8.0),
            ("subtotal", 8.0),
            ("detail", 6.75),
        ):
            with self.subTest(aggregation_stage=stage):
                self.assertEqual(
                    known_score({"aggregation_stage": stage}),
                    expected,
                )

        events = []
        all_weight_slot = AccessMapping(
            {
                "normalized_unit": "KRW",
                "raw_unit": "million",
                "raw_value": "1,234",
                "source_anchor": "slot-anchor",
                "value_role": "aggregate",
                "aggregation_stage": "final",
                "_matched_line_label": "Revenue Total",
                "label": "Revenue Total",
                "matched_operand_label": "",
                "concept": "revenue",
            },
            events,
            "slot",
        )
        all_weight_evidence = AccessMapping(
            {
                "source_anchor": "evidence-anchor",
                "metadata": {
                    "table_value_labels_text": "Revenue Total 1,234",
                    "unit_hint": "million",
                    "table_source_id": "table:1",
                },
            },
            events,
            "evidence",
            failure_key="source_anchor",
        )
        slot_before = deepcopy(dict(all_weight_slot))
        evidence_before = deepcopy(dict(all_weight_evidence))
        self.assertEqual(score(all_weight_slot, all_weight_evidence), 14.5)
        self.assertEqual(dict(all_weight_slot), slot_before)
        self.assertEqual(dict(all_weight_evidence), evidence_before)
        self.assertEqual(
            events,
            [
                "slot.get:normalized_unit",
                "evidence.get:metadata",
                "slot.get:raw_unit",
                "slot.get:raw_value",
                "slot.get:source_anchor",
                "slot.get:value_role",
                "slot.get:aggregation_stage",
                "slot.get:_matched_line_label",
                "slot.get:label",
                "slot.get:matched_operand_label",
                "slot.get:concept",
            ],
        )

        events = []
        fallback_slot = AccessMapping(known_slot, events, "slot")
        fallback_evidence = AccessMapping(
            {**known_evidence, "source_anchor": "evidence-anchor"},
            events,
            "evidence",
        )
        self.assertEqual(score(fallback_slot, fallback_evidence), 7.0)
        self.assertIn("evidence.get:source_anchor", events)

        for name, matched_label, label, expected in (
            ("exact", "Revenue Total", "Revenue Total", 8.75),
            ("compact", "RevenueTotal", "Revenue Total", 8.75),
            ("mismatch", "Other", "Revenue Total", 6.75),
        ):
            with self.subTest(label_match=name):
                self.assertEqual(
                    known_score({"_matched_line_label": matched_label, "label": label}),
                    expected,
                )

        repeated_surface = CountingString("Revenue Total")
        self.assertEqual(
            known_score(
                {"_matched_line_label": "RevenueTotal", "label": repeated_surface}
            ),
            8.75,
        )
        self.assertEqual(repeated_surface.calls, 2)

        events = []
        with self.assertRaisesRegex(RuntimeError, "slot:normalized_unit"):
            score(
                AccessMapping({"sentinel": True}, events, "slot", failure_key="normalized_unit"),
                AccessMapping({}, events, "evidence", failure_key="metadata"),
            )
        self.assertEqual(events, ["slot.get:normalized_unit"])

        events = []
        with self.assertRaisesRegex(RuntimeError, "metadata:table_value_labels_text"):
            score(
                AccessMapping({"normalized_unit": "KRW"}, events, "slot"),
                AccessMapping(
                    {
                        "metadata": CopyMapping(
                            {"table_value_labels_text": "metric"},
                            events,
                            failure_key="table_value_labels_text",
                        )
                    },
                    events,
                    "evidence",
                ),
            )
        self.assertEqual(
            events,
            [
                "slot.get:normalized_unit",
                "evidence.get:metadata",
                "metadata.iter",
                "metadata.getitem:table_value_labels_text",
            ],
        )

        events = []
        with self.assertRaisesRegex(RuntimeError, "string conversion"):
            score(
                AccessMapping({"normalized_unit": ExplodingString()}, events, "slot"),
                AccessMapping({}, events, "evidence", failure_key="metadata"),
            )
        self.assertEqual(events, ["slot.get:normalized_unit"])

        regex_slot = AccessMapping(
            {"normalized_unit": "KRW", "raw_unit": "million", "raw_value": "123"},
            [],
            "slot",
        )
        with patch.object(
            operand_resolution.re,
            "findall",
            side_effect=RuntimeError("digit regex"),
        ), self.assertRaisesRegex(RuntimeError, "digit regex"):
            score(regex_slot, known_evidence)

        real_sub = re.sub

        def fail_compaction(pattern, replacement, value, *args, **kwargs):
            if pattern == r"\s+" and replacement == "":
                raise RuntimeError("compact regex")
            return real_sub(pattern, replacement, value, *args, **kwargs)

        with patch.object(
            operand_resolution.re,
            "sub",
            side_effect=fail_compaction,
        ), self.assertRaisesRegex(RuntimeError, "compact regex"):
            known_score(
                {"_matched_line_label": "Revenue Total", "label": "Revenue Total"}
            )

    def test_direct_structured_preferred_slot_adoption_matrix(self) -> None:
        nested_context = {"keep": "current"}
        current = {
            "operand_id": "primary_value",
            "evidence_id": "ev_current",
            "source_row_id": "ev_current",
            "source_row_ids": ["ev_current"],
            "source_anchor": "current-anchor",
            "label": "target metric",
            "raw_value": "100",
            "raw_unit": "thousand",
            "normalized_value": 100.0,
            "normalized_unit": "COUNT",
            "period": "2023",
            "value_role": "aggregate",
            "aggregation_stage": "final",
            "aggregate_label": "current aggregate",
            "untouched": nested_context,
        }
        required = {"label": " target metric ", "concept": " target_concept ", "role": " primary_value "}
        preferred = {
            "source_row_id": "ev_preferred",
            "label": "preferred target metric",
            "raw_value": "100",
            "raw_unit": "million",
            "normalized_value": 100_000.0,
            "normalized_unit": "COUNT",
            "value_role": "detail",
            "ignored_extra": "do not project",
        }
        expected_adopted = {
            **current,
            "evidence_id": "ev_preferred",
            "source_row_id": "ev_preferred",
            "source_row_ids": [],
            "source_anchor": None,
            "label": "preferred target metric",
            "raw_value": "100",
            "raw_unit": "million",
            "normalized_value": 100_000.0,
            "normalized_unit": "COUNT",
            "period": None,
            "value_role": "detail",
            "aggregation_stage": None,
            "aggregate_label": None,
            "matched_operand_label": "target metric",
            "matched_operand_concept": "target_concept",
            "matched_operand_role": "primary_value",
        }
        cases = (
            ("current higher", "lookup", {"million"}, 12.0, 13.0, False, False, "higher_current_evidence_score"),
            ("equal", "lookup", set(), 12.0, 12.0, False, False, "equal_evidence_score"),
            ("preferred higher", "lookup", set(), 13.0, 12.0, True, False, "preferred_slot_selected"),
            ("nan fallthrough", "lookup", set(), float("nan"), 13.0, True, False, "preferred_slot_selected"),
            ("ratio alignment", "ratio", {"million"}, 12.0, 13.0, True, True, "ratio_unit_alignment_selected"),
        )

        for name, operation, peer_units, preferred_score, current_score, adopted, aligned, reason in cases:
            with self.subTest(name=name):
                adoption_input = DirectStructuredPreferredSlotAdoptionInput(
                    operation_family=operation,
                    row_index=0,
                    current_operand_row=current,
                    required_operand=required,
                    normalized_peer_raw_units=peer_units,
                    preferred_slot=preferred,
                    preferred_score=preferred_score,
                    current_score=current_score,
                )
                input_before = deepcopy(adoption_input)

                result = resolve_direct_structured_preferred_slot_adoption(adoption_input)

                if name == "nan fallthrough":
                    self.assertIs(adoption_input.preferred_score, input_before.preferred_score)
                    self.assertEqual(adoption_input.current_operand_row, input_before.current_operand_row)
                    self.assertEqual(adoption_input.preferred_slot, input_before.preferred_slot)
                else:
                    self.assertEqual(adoption_input, input_before)
                self.assertEqual(result.reason, reason)
                self.assertEqual(result.preferred_slot_adopted, adopted)
                self.assertEqual(result.unit_alignment_improves, aligned)
                if adopted:
                    self.assertEqual(result.selected_operand_row, expected_adopted)
                    self.assertIsNot(result.selected_operand_row, current)
                    self.assertIs(result.selected_operand_row["untouched"], nested_context)
                    self.assertNotIn("ignored_extra", result.selected_operand_row)
                else:
                    self.assertIs(result.selected_operand_row, current)

    def test_recovered_context_adoption_matrix_and_copy_contracts(self) -> None:
        def adoption_row(evidence_id, label, concept, role, value):
            row = _merge_operand_row(
                evidence_id, label=label, concept=concept, role=role, value=value
            )
            row["metadata"] = {"nested": [evidence_id]}
            return row

        period_required = [
            {"label": label, "concept": "metric", "role": role}
            for label, role in (("current", "current_period"), ("prior", "prior_period"))
        ]
        recovered_current = adoption_row("recovered_current", "current", "metric", "current_period", 120.0)
        current_prior = adoption_row("current_prior", "prior", "metric", "prior_period", 80.0)
        period_input = RecoveredOperandContextAdoptionInput(
            "period_comparison", [current_prior], [recovered_current], period_required, [], []
        )
        period_before = deepcopy(period_input)
        period_result = resolve_recovered_operand_context_adoption(period_input)

        self.assertEqual(period_input, period_before)
        self.assertEqual(
            (period_result.context_applied, period_result.reason),
            (True, "period_context_merged"),
        )
        self.assertEqual(
            [row["evidence_id"] for row in period_result.selected_operand_rows],
            ["recovered_current", "current_prior"],
        )
        self.assertIsNot(period_result.selected_operand_rows, period_input.recovered_operand_rows)
        self.assertIsNot(period_result.evidence_items, period_input.evidence_items)
        for selected, source in zip(
            period_result.selected_operand_rows,
            [recovered_current, current_prior],
        ):
            self.assertIsNot(selected, source)
            self.assertIs(selected["metadata"], source["metadata"])

        ratio_required = [
            {"label": label, "concept": concept, "role": role}
            for label, concept, role in (
                ("numerator", "metric", "numerator_1"),
                ("denominator", "base", "denominator_1"),
            )
        ]
        stale_ratio = adoption_row("stale", "numerator", "metric", "numerator_1", 1.0)
        recovered_ratio = [
            adoption_row("existing", "numerator", "metric", "numerator_1", 2.0),
            adoption_row("new", "denominator", "base", "denominator_1", 4.0),
        ]
        existing_item = {"evidence_id": "existing", "metadata": {"marker": "existing"}}
        recovered_items = [
            {"evidence_id": "existing", "metadata": {"marker": "excluded"}},
            {"evidence_id": "unused", "metadata": {"marker": "unused"}},
            {"evidence_id": "new", "metadata": {"marker": "first"}},
            {"evidence_id": "new", "metadata": {"marker": "second"}},
        ]
        ratio_input = RecoveredOperandContextAdoptionInput(
            "coherent_ratio",
            [stale_ratio],
            recovered_ratio,
            ratio_required,
            [existing_item],
            recovered_items,
        )
        ratio_before = deepcopy(ratio_input)
        ratio_result = resolve_recovered_operand_context_adoption(ratio_input)

        self.assertEqual(ratio_input, ratio_before)
        self.assertEqual(
            (ratio_result.context_applied, ratio_result.reason),
            (True, "coherent_ratio_context_replaced"),
        )
        self.assertEqual(
            [row["evidence_id"] for row in ratio_result.selected_operand_rows],
            ["existing", "new"],
        )
        self.assertEqual(ratio_result.adopted_evidence_ids, ("new", "new"))
        self.assertEqual(
            [item["evidence_id"] for item in ratio_result.evidence_items],
            ["existing", "new", "new"],
        )
        self.assertIsNot(ratio_result.evidence_items, ratio_input.evidence_items)
        for actual, expected in zip(
            ratio_result.evidence_items,
            [existing_item, recovered_items[2], recovered_items[3]],
        ):
            self.assertIs(actual, expected)

        no_context_input = RecoveredOperandContextAdoptionInput(
            "period_comparison", [current_prior], [], period_required, [existing_item], recovered_items
        )
        no_context_result = resolve_recovered_operand_context_adoption(no_context_input)
        self.assertIs(no_context_result.selected_operand_rows, no_context_input.current_operand_rows)
        self.assertIs(no_context_result.evidence_items, no_context_input.evidence_items)
        self.assertEqual(
            (no_context_result.context_applied, no_context_result.reason, no_context_result.adopted_evidence_ids),
            (False, "no_context_rows", ()),
        )

    def test_post_coercion_llm_selection_contract(self) -> None:
        required = [
            {"label": "primary", "concept": "primary_metric", "role": "numerator_1"},
            {"label": "secondary", "concept": "secondary_metric", "role": "denominator_1"},
        ]
        candidate = _merge_operand_row(
            "candidate_secondary",
            label="secondary",
            concept="secondary_metric",
            role="denominator_1",
            value=40.0,
        )
        evidence_item = {"evidence_id": "candidate_secondary", "claim": "secondary 40 unit"}

        for accepted, reason in (
            (True, "direct_support_present"),
            (False, "missing_direct_support"),
        ):
            support_input = operand_resolution.PostCoercionLlmDirectSupportInput(
                candidate,
                evidence_item,
                required,
            )
            support_before = deepcopy(support_input)
            with patch.object(
                operand_resolution,
                "_llm_lookup_operand_has_direct_support",
                return_value=accepted,
            ):
                support_result = operand_resolution.resolve_post_coercion_llm_direct_support(
                    support_input
                )
            self.assertEqual(support_input, support_before)
            self.assertIs(support_result.operand_row, candidate)
            self.assertEqual(
                (support_result.direct_support_accepted, support_result.reason),
                (accepted, reason),
            )

        no_required_input = operand_resolution.PostCoercionLlmOperandSelectionInput(
            [candidate], {}, [], [], False, False
        )
        no_required_result = operand_resolution.resolve_post_coercion_llm_operand_selection(
            no_required_input
        )
        self.assertIs(no_required_result.selected_operand_rows, no_required_input.operand_rows)
        self.assertEqual(
            (
                no_required_result.required_surface_filter_applied,
                no_required_result.lookup_rematch_filter_applied,
                no_required_result.direct_merge_applied,
            ),
            (False, False, False),
        )

        direct = _merge_operand_row(
            "direct_primary",
            label="primary",
            concept="primary_metric",
            role="numerator_1",
            value=100.0,
        )
        match_none = _merge_operand_row(
            "match_none", label="other", concept="other", role="other", value=1.0
        )
        surface_false = dict(candidate, evidence_id="surface_false", source_row_id="surface_false")
        selection_input = operand_resolution.PostCoercionLlmOperandSelectionInput(
            [match_none, surface_false, candidate],
            {},
            required,
            [direct],
            True,
            True,
        )
        selection_before = deepcopy(selection_input)
        surface_flags = []

        def surface_contract(row, _evidence_by_id, _required, *, require_direct_support=False):
            surface_flags.append(require_direct_support)
            return row.get("evidence_id") != "surface_false"

        with patch.object(
            operand_resolution,
            "_operand_row_satisfies_required_surface_contract",
            side_effect=surface_contract,
        ):
            selection_result = operand_resolution.resolve_post_coercion_llm_operand_selection(
                selection_input
            )

        self.assertEqual(selection_input, selection_before)
        self.assertEqual(surface_flags, [True, True])
        self.assertEqual(
            [row["evidence_id"] for row in selection_result.selected_operand_rows],
            ["direct_primary", "candidate_secondary"],
        )
        self.assertEqual(
            (
                selection_result.required_surface_filter_applied,
                selection_result.lookup_rematch_filter_applied,
                selection_result.direct_merge_applied,
            ),
            (True, True, True),
        )
        for actual, original in zip(selection_result.selected_operand_rows, [direct, candidate]):
            self.assertIsNot(actual, original)
            self.assertIs(actual["source_row_ids"], original["source_row_ids"])

    def test_supplemental_selector_prefers_explicit_binding_over_loose_match(self) -> None:
        required_operand = self._merge_required_operands()[1]
        exact = _merge_operand_row(
            "exact_base",
            label="base",
            concept="base_metric",
            role="denominator_1",
            value=40.0,
        )
        loose = _merge_operand_row(
            "loose_base",
            label="base",
            concept="",
            role="",
            value=999.0,
            bind_explicitly=False,
        )

        for ordered_rows in permutations([loose, exact]):
            decision = select_supplemental_operand_candidate(
                required_operand,
                list(ordered_rows),
            )

            self.assertEqual(decision.selected_candidate_id, "exact_base")
            self.assertEqual(decision.reason, "highest_binding_specificity")

    def test_supplemental_selector_abstains_on_conflicting_equal_rank(self) -> None:
        required_operands = self._merge_required_operands()[:2]
        preferred = [
            _merge_operand_row(
                "preferred_target",
                label="target",
                concept="target_metric",
                role="numerator_1",
                value=100.0,
            )
        ]
        conflicting = [
            _merge_operand_row(
                "base_a",
                label="base",
                concept="base_metric",
                role="denominator_1",
                value=40.0,
            ),
            _merge_operand_row(
                "base_b",
                label="base",
                concept="base_metric",
                role="denominator_1",
                value=50.0,
            ),
        ]

        for ordered_rows in permutations(conflicting):
            decision = select_supplemental_operand_candidate(
                required_operands[1],
                list(ordered_rows),
            )
            merged = merge_operand_rows(
                preferred,
                list(ordered_rows),
                required_operands=required_operands,
            )

            self.assertIsNone(decision.selected_row)
            self.assertEqual(decision.reason, "ambiguous_conflicting_top_rank")
            self.assertEqual(
                [row.get("evidence_id") for row in merged],
                ["preferred_target"],
            )

    def test_equivalent_supplemental_tie_uses_stable_provenance_id(self) -> None:
        required_operands = self._merge_required_operands()[:2]
        preferred = [
            _merge_operand_row(
                "preferred_target",
                label="target",
                concept="target_metric",
                role="numerator_1",
                value=100.0,
            )
        ]
        equivalent = [
            _merge_operand_row(
                "base_b",
                label="base",
                concept="base_metric",
                role="denominator_1",
                value=40.0,
            ),
            _merge_operand_row(
                "base_a",
                label="base",
                concept="base_metric",
                role="denominator_1",
                value=40.0,
            ),
        ]

        for ordered_rows in permutations(equivalent):
            merged = merge_operand_rows(
                preferred,
                list(ordered_rows),
                required_operands=required_operands,
            )

            self.assertEqual(
                [row.get("evidence_id") for row in merged],
                ["preferred_target", "base_a"],
            )

    def test_merge_preserves_preferred_and_no_required_copy_contracts(self) -> None:
        nested_metadata = {"source": "preferred"}
        preferred_row = _merge_operand_row(
            "preferred_base",
            label="base",
            concept="base_metric",
            role="denominator_1",
            value=40.0,
        )
        preferred_row["metadata"] = nested_metadata
        supplemental_first = _merge_operand_row(
            "supplemental_first",
            label="first",
            concept="",
            role="",
            value=1.0,
        )
        supplemental_duplicate = {
            **supplemental_first,
            "evidence_id": "supplemental_duplicate",
            "source_row_id": "supplemental_duplicate",
        }
        supplemental_second = _merge_operand_row(
            "supplemental_second",
            label="second",
            concept="",
            role="",
            value=2.0,
        )
        preferred = [preferred_row, preferred_row]
        supplemental = [
            supplemental_second,
            supplemental_first,
            supplemental_duplicate,
        ]
        preferred_snapshot = deepcopy(preferred)
        supplemental_snapshot = deepcopy(supplemental)

        merged = merge_operand_rows(
            preferred,
            supplemental,
            required_operands=[],
        )

        self.assertEqual(
            [row.get("evidence_id") for row in merged],
            [
                "preferred_base",
                "preferred_base",
                "supplemental_second",
                "supplemental_first",
            ],
        )
        self.assertIsNot(merged, preferred)
        self.assertIsNot(merged[0], preferred_row)
        self.assertIs(merged[0]["metadata"], nested_metadata)
        self.assertEqual(preferred, preferred_snapshot)
        self.assertEqual(supplemental, supplemental_snapshot)

        required_operands = self._merge_required_operands()
        preferred_target = _merge_operand_row(
            "preferred_target",
            label="target",
            concept="target_metric",
            role="numerator_1",
            value=100.0,
        )
        adjustment = _merge_operand_row(
            "supplemental_adjustment",
            label="adjustment",
            concept="adjustment_metric",
            role="subtrahend",
            value=5.0,
        )
        target_conflict = _merge_operand_row(
            "supplemental_target_conflict",
            label="target",
            concept="target_metric",
            role="numerator_1",
            value=999.0,
        )

        required_merge = merge_operand_rows(
            [preferred_row, preferred_target],
            [target_conflict, adjustment],
            required_operands=required_operands,
        )

        self.assertEqual(
            [row.get("evidence_id") for row in required_merge],
            ["preferred_base", "preferred_target", "supplemental_adjustment"],
        )
        self.assertEqual(
            [row.get("normalized_value") for row in required_merge[:2]],
            [40.0, 100.0],
        )

    def test_sibling_direct_selector_is_permutation_invariant_for_shared_coherent_source(self) -> None:
        current, direct_rows = self._sibling_selector_fixture()

        for ordered_rows in permutations(direct_rows):
            decision = select_sibling_direct_operand_candidate(current, ordered_rows)

            self.assertEqual(decision.selected_candidate_id, "direct_good")
            self.assertEqual(decision.reason, "shared_source_context")
            self.assertEqual(
                {item.candidate_id: item.reason for item in decision.rejected},
                {
                    "alt_den": "binding_mismatch",
                    "direct_alt": "lower_source_coherence",
                    "good_den": "binding_mismatch",
                },
            )

    def test_sibling_direct_selector_ignores_unrelated_complete_table_distractor(self) -> None:
        current, direct_rows = self._sibling_selector_fixture()
        direct_rows = direct_rows[:2]
        noise_rows = [
            _operand_row(
                "noise_num",
                label="unrelated",
                role="numerator_1",
                value=999.0,
                table_source_id="table_noise",
            ),
            _operand_row(
                "noise_den",
                label="noise base",
                role="denominator_1",
                value=1.0,
                table_source_id="table_noise",
            ),
        ]

        variants = [
            [*noise_rows, *direct_rows],
            [*direct_rows, *noise_rows],
            list(reversed([*direct_rows, *noise_rows])),
        ]
        for ordered_rows in variants:
            decision = select_sibling_direct_operand_candidate(current, ordered_rows)

            self.assertEqual(decision.selected_candidate_id, "direct_good")
            rejection_reasons = {
                item.candidate_id: item.reason for item in decision.rejected
            }
            self.assertEqual(rejection_reasons["noise_num"], "binding_mismatch")
            self.assertEqual(rejection_reasons["noise_den"], "binding_mismatch")

    def test_sibling_direct_selector_abstains_on_conflicting_equal_rank_contexts(self) -> None:
        current = _operand_row(
            "task_output:task_num",
            label="target",
            role="numerator_1",
            value=100.0,
            table_source_id="",
            source_row_ids=["task_output:task_num"],
            dependency_resolved=True,
            source_task_id="task_num",
        )
        direct_rows = [
            _operand_row(
                "direct_a",
                label="target",
                role="numerator_1",
                value=80.0,
                table_source_id="table_a",
            ),
            _operand_row(
                "den_a",
                label="base",
                role="denominator_1",
                value=40.0,
                table_source_id="table_a",
            ),
            _operand_row(
                "direct_b",
                label="target",
                role="numerator_1",
                value=70.0,
                table_source_id="table_b",
            ),
            _operand_row(
                "den_b",
                label="base",
                role="denominator_1",
                value=35.0,
                table_source_id="table_b",
            ),
        ]

        decision = select_sibling_direct_operand_candidate(current, direct_rows)

        self.assertIsNone(decision.selected_row)
        self.assertEqual(decision.reason, "ambiguous_conflicting_top_rank")
        rejection_reasons = {
            item.candidate_id: item.reason for item in decision.rejected
        }
        self.assertEqual(
            rejection_reasons["direct_a"],
            "ambiguous_conflicting_top_rank",
        )
        self.assertEqual(
            rejection_reasons["direct_b"],
            "ambiguous_conflicting_top_rank",
        )

    def test_sibling_direct_selector_uses_stable_id_for_equivalent_equal_rank_contexts(self) -> None:
        current = _operand_row(
            "task_output:task_num",
            label="target",
            role="numerator_1",
            value=100.0,
            table_source_id="",
            source_row_ids=["task_output:task_num"],
            dependency_resolved=True,
            source_task_id="task_num",
        )
        direct_rows = [
            _operand_row(
                "direct_b",
                label="target",
                role="numerator_1",
                value=80.0,
                table_source_id="table_b",
            ),
            _operand_row(
                "den_b",
                label="base",
                role="denominator_1",
                value=40.0,
                table_source_id="table_b",
            ),
            _operand_row(
                "direct_a",
                label="target",
                role="numerator_1",
                value=80.0,
                table_source_id="table_a",
            ),
            _operand_row(
                "den_a",
                label="base",
                role="denominator_1",
                value=40.0,
                table_source_id="table_a",
            ),
        ]

        for ordered_rows in permutations(direct_rows):
            decision = select_sibling_direct_operand_candidate(current, ordered_rows)

            self.assertEqual(decision.selected_candidate_id, "direct_a")
            self.assertEqual(decision.reason, "equivalent_top_rank_tiebreak")
            rejection_reasons = {
                item.candidate_id: item.reason for item in decision.rejected
            }
            self.assertEqual(rejection_reasons["direct_b"], "equivalent_duplicate")

    def test_sibling_direct_selector_is_stable_when_equivalent_candidates_share_evidence_id(self) -> None:
        current = _operand_row(
            "task_output:task_num",
            label="target",
            role="numerator_1",
            value=100.0,
            table_source_id="",
            source_row_ids=["task_output:task_num"],
            dependency_resolved=True,
            source_task_id="task_num",
        )
        direct_a = _operand_row(
            "shared_evidence",
            label="target",
            role="numerator_1",
            value=80.0,
            table_source_id="table_shared",
        )
        direct_a.update({"source_row_id": "row_a", "operand_id": "operand_a"})
        direct_b = _operand_row(
            "shared_evidence",
            label="target",
            role="numerator_1",
            value=80.0,
            table_source_id="table_shared",
        )
        direct_b.update({"source_row_id": "row_b", "operand_id": "operand_b"})
        denominator = _operand_row(
            "denominator",
            label="base",
            role="denominator_1",
            value=40.0,
            table_source_id="table_shared",
        )

        for ordered_rows in permutations([direct_a, direct_b, denominator]):
            decision = select_sibling_direct_operand_candidate(current, ordered_rows)

            self.assertEqual(decision.selected_candidate_id, "shared_evidence")
            self.assertEqual(decision.selected_row["operand_id"], "operand_a")
            self.assertEqual(decision.reason, "equivalent_top_rank_tiebreak")

    def test_context_docs_append_unique_seed_docs_after_visible_docs(self) -> None:
        visible = (_doc("visible", "visible"), 0.9)
        shared = (_doc("shared", "shared"), 0.8)
        duplicate_shared = (_doc("shared", "duplicate"), 0.7)
        seed_only = (_doc("seed", "seed"), 0.6)
        object_only = (_doc("", "object", object_id="object-only"), 0.5)
        duplicate_object = (_doc("", "duplicate object", object_id="object-only"), 0.4)

        result = collect_retrieval_context_docs(
            [visible, shared],
            [duplicate_shared, seed_only, object_only, duplicate_object],
            seed_limit=4,
        )

        self.assertEqual(result, [visible, shared, seed_only, object_only])

    def test_retrieved_candidate_collection_preserves_bucket_order_and_seed_dedupe(self) -> None:
        retrieved_docs = [
            (_doc("visible", "visible text"), 0.9),
            (_doc("shared", "shared text"), 0.8),
        ]
        seed_retrieved_docs = [
            (_doc("shared", "duplicate seed text"), 0.7),
            (_doc("seed", "seed text"), 0.6),
        ]
        observed_doc_orders: List[List[str]] = []
        ratio_row = _candidate("ev_ratio", "ratio-anchor", row_text="ratio row")
        ratio_component = _candidate(
            "ev_component",
            "component-anchor",
            row_text="component row",
        )

        def required_builder(
            candidate_items: List[Dict[str, Any]],
            **_kwargs: Any,
        ) -> List[Dict[str, Any]]:
            observed_doc_orders.append(
                [str(item.get("metadata", {}).get("chunk_uid") or "") for item in candidate_items]
            )
            return [{"evidence_id": "ev_operand_doc_001"}]

        def ratio_row_extractor(
            candidate_docs: List[Any],
            _query: str,
            _topic: str,
        ) -> List[Dict[str, Any]]:
            observed_doc_orders.append(
                [str(doc.metadata.get("chunk_uid") or "") for doc, _score in candidate_docs]
            )
            return [ratio_row]

        def ratio_component_extractor(
            candidate_docs: List[Any],
            _query: str,
            _topic: str,
        ) -> List[Dict[str, Any]]:
            observed_doc_orders.append(
                [str(doc.metadata.get("chunk_uid") or "") for doc, _score in candidate_docs]
            )
            return [ratio_component]

        batch = collect_retrieved_operand_evidence_candidates(
            retrieved_docs,
            seed_retrieved_docs,
            existing_evidence_items=[],
            required_operands=[{"label": "absent context term"}],
            missing_dependency_bindings=[],
            query="compare values",
            topic="",
            report_scope={},
            desired_consolidation_scope="unknown",
            build_source_anchor=lambda metadata: str(metadata.get("chunk_uid") or ""),
            build_required_operands_from_candidates=required_builder,
            extract_ratio_row_candidates=ratio_row_extractor,
            extract_ratio_component_candidates=ratio_component_extractor,
        )

        self.assertEqual(
            observed_doc_orders,
            [["visible", "shared", "seed"]] * 3,
        )
        self.assertEqual(
            [item["evidence_id"] for item in batch.evidence_items],
            [
                "ev_operand_doc_001",
                "ev_ratio",
                "ev_component",
                "ev_doc_002",
                "ev_doc_003",
            ],
        )
        self.assertIs(batch.evidence_items[1], ratio_row)
        self.assertIs(batch.evidence_items[2], ratio_component)
        self.assertEqual(len(batch.evidence_bullets), len(batch.evidence_items))

    def test_generic_document_window_uses_dependency_sensitive_cap(self) -> None:
        retrieved_docs = [
            (_doc(f"doc-{index:02d}", f"text {index}"), float(20 - index))
            for index in range(1, 19)
        ]

        def unexpected_required_builder(*_args: Any, **_kwargs: Any) -> List[Dict[str, Any]]:
            self.fail("required operand builder must not run without required operands")

        def collect(missing_bindings: List[Dict[str, Any]]) -> List[str]:
            batch = collect_retrieved_operand_evidence_candidates(
                retrieved_docs,
                [],
                existing_evidence_items=[],
                required_operands=[],
                missing_dependency_bindings=missing_bindings,
                query="compare values",
                topic="",
                report_scope={},
                desired_consolidation_scope="unknown",
                build_source_anchor=lambda metadata: str(metadata.get("chunk_uid") or ""),
                build_required_operands_from_candidates=unexpected_required_builder,
                extract_ratio_row_candidates=lambda *_args: [],
                extract_ratio_component_candidates=lambda *_args: [],
            )
            return [str(item.get("evidence_id") or "") for item in batch.evidence_items]

        self.assertEqual(
            collect([]),
            [f"ev_doc_{index:03d}" for index in range(1, 9)],
        )
        self.assertEqual(
            collect([{"label": "missing"}]),
            [f"ev_doc_{index:03d}" for index in range(1, 17)],
        )

    def test_generic_anchor_dedupe_preserves_existing_missing_term_exception(self) -> None:
        docs = [
            (_doc("first", "needle first", anchor="shared"), 0.9),
            (_doc("second", "needle second", anchor="shared"), 0.8),
        ]

        def collect(
            existing_evidence_items: List[Dict[str, Any]],
            missing_bindings: List[Dict[str, Any]],
        ) -> List[str]:
            batch = collect_retrieved_operand_evidence_candidates(
                docs,
                [],
                existing_evidence_items=existing_evidence_items,
                required_operands=[],
                missing_dependency_bindings=missing_bindings,
                query="compare values",
                topic="",
                report_scope={},
                desired_consolidation_scope="unknown",
                build_source_anchor=lambda metadata: str(metadata.get("anchor") or ""),
                build_required_operands_from_candidates=lambda *_args, **_kwargs: [],
                extract_ratio_row_candidates=lambda *_args: [],
                extract_ratio_component_candidates=lambda *_args: [],
            )
            return [str(item.get("evidence_id") or "") for item in batch.evidence_items]

        self.assertEqual(collect([], []), ["ev_doc_001", "ev_doc_002"])
        self.assertEqual(collect([{"source_anchor": "shared"}], []), [])
        self.assertEqual(
            collect([{"source_anchor": "shared"}], [{"label": "needle"}]),
            ["ev_doc_001", "ev_doc_002"],
        )

    def test_percent_point_query_skips_ratio_component_candidates(self) -> None:
        component_calls: List[bool] = []
        ratio_row = _candidate("ev_ratio", "ratio-anchor", row_text="ratio row")

        def component_extractor(*_args: Any) -> List[Dict[str, Any]]:
            component_calls.append(True)
            return [_candidate("ev_component", "component-anchor", row_text="component")]

        batch = collect_retrieved_operand_evidence_candidates(
            [(_doc("visible", "visible text"), 0.9)],
            [],
            existing_evidence_items=[],
            required_operands=[],
            missing_dependency_bindings=[],
            query="전년 대비 증감폭(%p)을 계산해 줘.",
            topic="",
            report_scope={},
            desired_consolidation_scope="unknown",
            build_source_anchor=lambda metadata: str(metadata.get("chunk_uid") or ""),
            build_required_operands_from_candidates=lambda *_args, **_kwargs: [],
            extract_ratio_row_candidates=lambda *_args: [ratio_row],
            extract_ratio_component_candidates=component_extractor,
        )

        self.assertFalse(component_calls)
        self.assertEqual(
            [item["evidence_id"] for item in batch.evidence_items],
            ["ev_ratio", "ev_doc_001"],
        )

    def test_table_krw_unit_repair_pins_empty_dependency_and_alternate_surface_contract(self) -> None:
        repair = operand_resolution.repair_krw_operand_units_from_table_metadata
        shared = {"preserve": True}
        policy = {
            "krw_display_units": ("won",),
            "krw_display_unit_scales": {"won": 1.0},
        }
        row = {
            "operand_id": "target",
            "label": "target",
            "raw_value": "100",
            "raw_unit": "count",
            "normalized_value": 100.0,
            "normalized_unit": "COUNT",
            "nested": shared,
        }
        operands = [row]
        operands_before = deepcopy(operands)

        class PolicyBomb(Mapping):
            def __getitem__(self, key):
                raise AssertionError(f"policy item must stay lazy: {key}")

            def __iter__(self):
                raise AssertionError("policy iteration must stay lazy")

            def __len__(self):
                raise AssertionError("policy length must stay lazy")

            def keys(self):
                raise RuntimeError("policy keys failed")

        with patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", PolicyBomb()):
            self.assertIs(repair(operands, []), operands)
        self.assertEqual(operands, operands_before)

        with (
            patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", PolicyBomb()),
            patch.object(
                operand_resolution,
                "dependency_task_output_has_consistent_krw_unit",
            ) as stopped_gate,
            self.assertRaisesRegex(RuntimeError, "policy keys failed"),
        ):
            repair(operands, [{"evidence_id": "ev"}])
        stopped_gate.assert_not_called()
        self.assertEqual(operands, operands_before)

        dependency_evidence = [{"evidence_id": "ev", "metadata": {"block_type": "table"}}]
        dependency_before = deepcopy(dependency_evidence)
        seen_dependency_rows = []

        class StringBomb:
            def __bool__(self):
                raise RuntimeError("raw truthiness must stay lazy")

            def __str__(self):
                raise RuntimeError("raw string must stay lazy")

        dependency_row = {
            **row,
            "raw_value": StringBomb(),
            "raw_unit": StringBomb(),
        }
        dependency_operands = [dependency_row]

        def accept_dependency(candidate):
            seen_dependency_rows.append(candidate)
            return True

        with (
            patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", policy),
            patch.object(
                operand_resolution,
                "dependency_task_output_has_consistent_krw_unit",
                side_effect=accept_dependency,
            ),
            patch.object(
                operand_resolution,
                "_normalise_operand_value",
                side_effect=AssertionError("normalizer must stay lazy"),
            ),
        ):
            self.assertIs(repair(dependency_operands, dependency_evidence), dependency_operands)
        self.assertEqual(dependency_evidence, dependency_before)
        self.assertEqual(len(seen_dependency_rows), 1)
        self.assertIsNot(seen_dependency_rows[0], dependency_row)
        self.assertIs(seen_dependency_rows[0]["raw_value"], dependency_row["raw_value"])
        self.assertIs(seen_dependency_rows[0]["raw_unit"], dependency_row["raw_unit"])
        self.assertIs(seen_dependency_rows[0]["nested"], shared)

        evidence_items = [
            {
                "evidence_id": "ev_other",
                "raw_row_text": "other 100won",
                "metadata": {"block_type": "table"},
            },
            {
                "evidence_id": "ev_target",
                "raw_row_text": "target 100won",
                "metadata": {"block_type": "table"},
            },
            {
                "evidence_id": "ev_later",
                "raw_row_text": "later 100won",
                "metadata": {"block_type": "table"},
            },
        ]
        evidence_before = deepcopy(evidence_items)
        match_events = []

        def match(surface, requirement):
            match_events.append((surface, requirement))
            return surface.startswith("target")

        with (
            patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", policy),
            patch.object(
                operand_resolution,
                "dependency_task_output_has_consistent_krw_unit",
                return_value=False,
            ),
            patch.object(operand_resolution, "_operand_text_match", side_effect=match),
            patch.object(
                operand_resolution,
                "_normalise_operand_value",
                return_value=(100.0, "KRW"),
            ) as normalizer,
        ):
            repaired = repair(operands, evidence_items)
        self.assertIsNot(repaired, operands)
        self.assertIsNot(repaired[0], row)
        self.assertIs(repaired[0]["nested"], shared)
        self.assertEqual(operands, operands_before)
        self.assertEqual(evidence_items, evidence_before)
        self.assertEqual([event[0] for event in match_events], ["other 100won", "target 100won"])
        self.assertTrue(all(event[1] == {"label": "target", "aliases": []} for event in match_events))
        normalizer.assert_called_once_with("100", "won")
        self.assertEqual(
            {
                key: repaired[0].get(key)
                for key in (
                    "source_raw_unit",
                    "source_normalized_value",
                    "raw_unit",
                    "normalized_value",
                    "normalized_unit",
                    "rendered_value",
                    "unit_normalization_repair_source",
                )
            },
            {
                "source_raw_unit": "count",
                "source_normalized_value": 100.0,
                "raw_unit": "won",
                "normalized_value": 100.0,
                "normalized_unit": "KRW",
                "rendered_value": "100won",
                "unit_normalization_repair_source": "alternate_table_krw_surface",
            },
        )

        hinted_surface = [{
            "evidence_id": "ev_hint",
            "raw_row_text": "target 100",
            "metadata": {"block_type": "table", "unit_hint": "won"},
        }]
        hinted_before = deepcopy(hinted_surface)
        with (
            patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", policy),
            patch.object(
                operand_resolution,
                "dependency_task_output_has_consistent_krw_unit",
                return_value=False,
            ),
            patch.object(operand_resolution, "_operand_text_match", return_value=True),
            patch.object(
                operand_resolution,
                "_normalise_operand_value",
                return_value=(100.0, "KRW"),
            ) as hinted_normalizer,
        ):
            hinted = repair(operands, hinted_surface)
        self.assertEqual(hinted_surface, hinted_before)
        self.assertEqual(hinted[0]["raw_unit"], "won")
        self.assertEqual(hinted[0]["unit_normalization_repair_source"], "alternate_table_krw_surface")
        hinted_normalizer.assert_called_once_with("100", "won")

        for name, candidate, expected_label in (
            (
                "matched label precedence",
                {
                    **row,
                    "normalized_unit": "UNKNOWN",
                    "matched_operand_label": "matched",
                    "label": "wrong",
                    "semantic_label": "semantic",
                },
                "matched",
            ),
            (
                "semantic label fallback",
                {
                    **row,
                    "normalized_unit": "",
                    "matched_operand_label": "",
                    "label": "",
                    "semantic_label": "semantic",
                },
                "semantic",
            ),
        ):
            label_evidence = [{
                "evidence_id": "ev_label",
                "raw_row_text": f"{expected_label} 100won",
                "metadata": {"block_type": "table"},
            }]
            requirements = []

            def capture_requirement(_surface, requirement):
                requirements.append(requirement)
                return True

            with (
                self.subTest(label_source=name),
                patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", policy),
                patch.object(
                    operand_resolution,
                    "dependency_task_output_has_consistent_krw_unit",
                    return_value=False,
                ),
                patch.object(operand_resolution, "_operand_text_match", side_effect=capture_requirement),
                patch.object(
                    operand_resolution,
                    "_normalise_operand_value",
                    return_value=(100.0, "KRW"),
                ),
            ):
                label_repaired = repair([candidate], label_evidence)
            self.assertEqual(requirements, [{"label": expected_label, "aliases": []}])
            self.assertEqual(label_repaired[0]["raw_unit"], "won")
            self.assertEqual(label_repaired[0]["normalized_unit"], "KRW")

        cases = (
            ("unit family", {**row, "normalized_unit": "PERCENT"}, evidence_items, (100.0, "KRW")),
            ("blank value", {**row, "raw_value": ""}, evidence_items, (100.0, "KRW")),
            (
                "not table",
                row,
                [{"evidence_id": "ev", "raw_row_text": "target 100won", "metadata": {}}],
                (100.0, "KRW"),
            ),
            (
                "value gate",
                row,
                [{"evidence_id": "ev", "raw_row_text": "target 999won", "metadata": {"block_type": "table"}}],
                (100.0, "KRW"),
            ),
            (
                "label gate",
                row,
                [{"evidence_id": "ev", "raw_row_text": "other 100won", "metadata": {"block_type": "table"}}],
                (100.0, "KRW"),
            ),
            (
                "unit gate",
                row,
                [{
                    "evidence_id": "ev",
                    "raw_row_text": "target 100count",
                    "metadata": {"block_type": "table", "unit_hint": "count"},
                }],
                (100.0, "KRW"),
            ),
            ("normalizer value", row, evidence_items[1:2], (None, "KRW")),
            ("normalizer unit", row, evidence_items[1:2], (100.0, "COUNT")),
        )
        for name, candidate, current_evidence, normalizer_result in cases:
            current_operands = [candidate]
            current_before = deepcopy((current_operands, current_evidence))
            with (
                self.subTest(name=name),
                patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", policy),
                patch.object(
                    operand_resolution,
                    "dependency_task_output_has_consistent_krw_unit",
                    return_value=False,
                ),
                patch.object(
                    operand_resolution,
                    "_normalise_operand_value",
                    side_effect=(
                        None if name.startswith("normalizer")
                        else AssertionError("normalizer must stay lazy")
                    ),
                    return_value=normalizer_result,
                ) as current_normalizer,
            ):
                self.assertIs(repair(current_operands, current_evidence), current_operands)
            self.assertEqual(current_normalizer.call_count, 1 if name.startswith("normalizer") else 0)
            self.assertEqual((current_operands, current_evidence), current_before)

        class AlternateFloatBomb:
            def __init__(self, error_type):
                self.error_type = error_type

            def __float__(self):
                raise self.error_type("alternate current value failed")

        for error_type, propagates in ((TypeError, False), (ValueError, False), (RuntimeError, True)):
            alternate_operands = [{**row, "normalized_value": AlternateFloatBomb(error_type)}]
            alternate_before = list(alternate_operands)
            with (
                self.subTest(alternate_float_error=error_type),
                patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", policy),
                patch.object(
                    operand_resolution,
                    "dependency_task_output_has_consistent_krw_unit",
                    return_value=False,
                ),
                patch.object(operand_resolution, "_operand_text_match", return_value=True),
                patch.object(
                    operand_resolution,
                    "_normalise_operand_value",
                    return_value=(100.0, "KRW"),
                ),
            ):
                if propagates:
                    with self.assertRaisesRegex(RuntimeError, "alternate current value failed"):
                        repair(alternate_operands, evidence_items[1:2])
                else:
                    alternate_repaired = repair(alternate_operands, evidence_items[1:2])
                    self.assertNotIn("source_normalized_value", alternate_repaired[0])
                    self.assertEqual(alternate_repaired[0]["raw_unit"], "won")
            self.assertEqual(alternate_operands, alternate_before)

        exception_operands = [dict(row)]
        exception_evidence = deepcopy(evidence_items[1:2])
        exception_before = deepcopy((exception_operands, exception_evidence))
        with patch.object(
            operand_resolution,
            "_evidence_items_by_id",
            side_effect=RuntimeError("index failed"),
        ), self.assertRaisesRegex(RuntimeError, "index failed"):
            repair(exception_operands, exception_evidence)
        self.assertEqual((exception_operands, exception_evidence), exception_before)

        for stage in ("dependency", "label", "normalizer"):
            exception_operands = [dict(row)]
            exception_evidence = deepcopy(evidence_items[1:2])
            exception_before = deepcopy((exception_operands, exception_evidence))
            with (
                self.subTest(exception_stage=stage),
                patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", policy),
                patch.object(
                    operand_resolution,
                    "dependency_task_output_has_consistent_krw_unit",
                    side_effect=RuntimeError("dependency failed") if stage == "dependency" else None,
                    return_value=False,
                ),
                patch.object(
                    operand_resolution,
                    "_operand_text_match",
                    side_effect=RuntimeError("label failed") if stage == "label" else None,
                    return_value=True,
                ),
                patch.object(
                    operand_resolution,
                    "_normalise_operand_value",
                    side_effect=RuntimeError("normalizer failed") if stage == "normalizer" else None,
                    return_value=(100.0, "KRW"),
                ),
                self.assertRaisesRegex(RuntimeError, f"{stage} failed"),
            ):
                repair(exception_operands, exception_evidence)
            self.assertEqual((exception_operands, exception_evidence), exception_before)

    def test_table_krw_unit_repair_pins_metadata_hint_gates_threshold_copy_and_exception_contract(self) -> None:
        repair = operand_resolution.repair_krw_operand_units_from_table_metadata
        shared = {"preserve": True}

        def policy(raw_scale=100.0, hint_scale=1.0, *, include_scales=True):
            return {
                "krw_display_units": ("hundred", "won", "other"),
                "krw_display_unit_scales": (
                    {"hundred": raw_scale, "won": hint_scale} if include_scales else {"hundred": raw_scale}
                ),
            }

        row = {
            "operand_id": "target",
            "evidence_id": "ev_target",
            "source_row_id": "ev_target",
            "raw_value": "100",
            "raw_unit": "hundred",
            "normalized_value": 10_000.0,
            "normalized_unit": "KRW",
            "nested": shared,
        }
        evidence = {
            "evidence_id": "ev_target",
            "raw_row_text": "target 100 won",
            "metadata": {"block_type": "table", "unit_hint": "won"},
        }
        rows = [{**row, "operand_id": "dependency"}, row]
        evidence_items = [evidence]
        before = deepcopy((rows, evidence_items))
        helper_events = []

        def select_evidence(candidate, evidence_by_id):
            helper_events.append((candidate, evidence_by_id))
            return evidence

        with (
            patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", policy()),
            patch.object(
                operand_resolution,
                "dependency_task_output_has_consistent_krw_unit",
                side_effect=[True, False],
            ),
            patch.object(
                operand_resolution,
                "_evidence_item_for_operand_row",
                side_effect=select_evidence,
            ),
            patch.object(
                operand_resolution,
                "_normalise_operand_value",
                return_value=(100.0, "KRW"),
            ) as normalizer,
        ):
            repaired = repair(rows, evidence_items)
        self.assertEqual((rows, evidence_items), before)
        self.assertIsNot(repaired, rows)
        self.assertTrue(all(repaired[index] is not rows[index] for index in range(2)))
        self.assertTrue(all(item["nested"] is shared for item in repaired))
        self.assertEqual(len(helper_events), 1)
        self.assertIsNot(helper_events[0][0], row)
        self.assertEqual(helper_events[0][1]["ev_target"], evidence)
        normalizer.assert_called_once_with("100", "won")
        self.assertEqual(
            {
                key: repaired[1].get(key)
                for key in (
                    "source_raw_unit",
                    "source_normalized_value",
                    "raw_unit",
                    "normalized_value",
                    "normalized_unit",
                    "rendered_value",
                    "unit_normalization_repair_source",
                )
            },
            {
                "source_raw_unit": "hundred",
                "source_normalized_value": 10_000.0,
                "raw_unit": "won",
                "normalized_value": 100.0,
                "normalized_unit": "KRW",
                "rendered_value": "100won",
                "unit_normalization_repair_source": "table_metadata_unit_hint",
            },
        )

        fallback_row = {**row, "raw_unit": "", "result_unit": "hundred"}
        fallback_rows = [fallback_row]
        fallback_before = deepcopy(fallback_rows)
        with (
            patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", policy()),
            patch.object(
                operand_resolution,
                "dependency_task_output_has_consistent_krw_unit",
                return_value=False,
            ),
            patch.object(operand_resolution, "_evidence_item_for_operand_row", return_value=evidence),
            patch.object(
                operand_resolution,
                "_normalise_operand_value",
                return_value=(100.0, "KRW"),
            ) as fallback_normalizer,
        ):
            fallback_repaired = repair(fallback_rows, evidence_items)
        self.assertEqual(fallback_rows, fallback_before)
        self.assertEqual(
            (
                fallback_repaired[0]["source_raw_unit"],
                fallback_repaired[0]["raw_unit"],
                fallback_repaired[0]["normalized_value"],
            ),
            ("hundred", "won", 100.0),
        )
        fallback_normalizer.assert_called_once_with("100", "won")

        same_hint = {**evidence, "metadata": {"block_type": "table", "unit_hint": "hundred"}}
        with (
            patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", policy()),
            patch.object(
                operand_resolution,
                "dependency_task_output_has_consistent_krw_unit",
                return_value=False,
            ),
            patch.object(operand_resolution, "_evidence_item_for_operand_row", return_value=same_hint),
            patch.object(
                operand_resolution,
                "_normalise_operand_value",
                side_effect=AssertionError("normalizer must stay lazy"),
            ) as same_hint_normalizer,
        ):
            self.assertIs(repair(fallback_rows, [same_hint]), fallback_rows)
        same_hint_normalizer.assert_not_called()

        class ResultUnitBomb:
            def __bool__(self):
                raise RuntimeError("result unit truthiness must stay lazy")

            def __str__(self):
                raise RuntimeError("result unit string must stay lazy")

        whitespace_row = {**row, "raw_unit": "   ", "result_unit": ResultUnitBomb()}
        whitespace_rows = [whitespace_row]
        with (
            patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", policy()),
            patch.object(
                operand_resolution,
                "dependency_task_output_has_consistent_krw_unit",
                return_value=False,
            ),
            patch.object(
                operand_resolution,
                "_evidence_item_for_operand_row",
                side_effect=AssertionError("evidence lookup must stay lazy"),
            ) as whitespace_evidence,
            patch.object(
                operand_resolution,
                "_normalise_operand_value",
                side_effect=AssertionError("normalizer must stay lazy"),
            ) as whitespace_normalizer,
        ):
            self.assertIs(repair(whitespace_rows, evidence_items), whitespace_rows)
        whitespace_evidence.assert_not_called()
        whitespace_normalizer.assert_not_called()

        cases = (
            ("blank value", {**row, "raw_value": ""}, evidence, policy(), (100.0, "KRW")),
            ("raw unit", {**row, "raw_unit": "count"}, evidence, policy(), (100.0, "KRW")),
            ("no evidence", row, None, policy(), (100.0, "KRW")),
            ("not table", row, {**evidence, "metadata": {"unit_hint": "won"}}, policy(), (100.0, "KRW")),
            ("blank hint", row, {**evidence, "metadata": {"block_type": "table"}}, policy(), (100.0, "KRW")),
            (
                "same hint",
                row,
                {**evidence, "metadata": {"block_type": "table", "unit_hint": "hundred"}},
                policy(),
                (100.0, "KRW"),
            ),
            (
                "unknown hint",
                row,
                {**evidence, "metadata": {"block_type": "table", "unit_hint": "unknown"}},
                policy(),
                (100.0, "KRW"),
            ),
            ("missing scale", row, evidence, policy(include_scales=False), (100.0, "KRW")),
            ("below threshold", row, evidence, policy(raw_scale=99.0), (100.0, "KRW")),
            ("surface value", row, {**evidence, "raw_row_text": "target 999 won"}, policy(), (100.0, "KRW")),
            ("normalizer value", row, evidence, policy(), (None, "KRW")),
            ("normalizer unit", row, evidence, policy(), (100.0, "COUNT")),
        )
        for name, candidate, selected_evidence, current_policy, normalizer_result in cases:
            current_rows = [candidate]
            current_evidence = [selected_evidence or evidence]
            current_before = deepcopy((current_rows, current_evidence))
            with (
                self.subTest(name=name),
                patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", current_policy),
                patch.object(
                    operand_resolution,
                    "dependency_task_output_has_consistent_krw_unit",
                    return_value=False,
                ),
                patch.object(
                    operand_resolution,
                    "_evidence_item_for_operand_row",
                    return_value=selected_evidence,
                ),
                patch.object(
                    operand_resolution,
                    "_normalise_operand_value",
                    side_effect=(
                        None if name.startswith("normalizer")
                        else AssertionError("normalizer must stay lazy")
                    ),
                    return_value=normalizer_result,
                ) as current_normalizer,
            ):
                self.assertIs(repair(current_rows, current_evidence), current_rows)
            self.assertEqual(current_normalizer.call_count, 1 if name.startswith("normalizer") else 0)
            self.assertEqual((current_rows, current_evidence), current_before)

        class FloatBomb:
            def __init__(self, error_type):
                self.error_type = error_type

            def __float__(self):
                raise self.error_type("current value failed")

        for error_type, propagates in ((TypeError, False), (ValueError, False), (RuntimeError, True)):
            current_rows = [{**row, "normalized_value": FloatBomb(error_type)}]
            current_before = list(current_rows)
            with (
                self.subTest(float_error=error_type),
                patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", policy()),
                patch.object(
                    operand_resolution,
                    "dependency_task_output_has_consistent_krw_unit",
                    return_value=False,
                ),
                patch.object(operand_resolution, "_evidence_item_for_operand_row", return_value=evidence),
                patch.object(
                    operand_resolution,
                    "_normalise_operand_value",
                    return_value=(100.0, "KRW"),
                ),
            ):
                if propagates:
                    with self.assertRaisesRegex(RuntimeError, "current value failed"):
                        repair(current_rows, evidence_items)
                else:
                    repaired = repair(current_rows, evidence_items)
                    self.assertNotIn("source_normalized_value", repaired[0])
                    self.assertEqual(repaired[0]["raw_unit"], "won")
            self.assertEqual(current_rows, current_before)

        class EvidenceBomb(dict):
            def get(self, key, default=None):
                if key == "raw_row_text":
                    raise RuntimeError("surface failed")
                return super().get(key, default)

        bomb = EvidenceBomb(evidence)
        with (
            patch.object(operand_resolution, "CALCULATION_RENDER_POLICY", policy()),
            patch.object(
                operand_resolution,
                "dependency_task_output_has_consistent_krw_unit",
                return_value=False,
            ),
            patch.object(operand_resolution, "_evidence_item_for_operand_row", return_value=bomb),
            patch.object(operand_resolution, "_normalise_operand_value") as stopped_normalizer,
            self.assertRaisesRegex(RuntimeError, "surface failed"),
        ):
            repair([row], [bomb])
        stopped_normalizer.assert_not_called()

    def test_table_krw_unit_repair_static_surface_pins_public_owner_sole_call_and_prepare_order(self) -> None:
        import ast
        import inspect

        from src.agent import financial_graph_calculation as graph_calculation

        source_lines, start_line = inspect.getsourcelines(
            operand_resolution.repair_krw_operand_units_from_table_metadata
        )
        self.assertEqual((start_line, len(source_lines)), (788, 165))
        tree = ast.parse(inspect.getsource(graph_calculation))
        graph_definitions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name == "repair_krw_operand_units_from_table_metadata"
        ]
        self.assertEqual(graph_definitions, [])
        bindings = [
            alias
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_operand_resolution"
            for alias in node.names
            if alias.name == "repair_krw_operand_units_from_table_metadata"
        ]
        self.assertEqual(
            [(alias.name, alias.asname) for alias in bindings],
            [("repair_krw_operand_units_from_table_metadata", None)],
        )
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "repair_krw_operand_units_from_table_metadata"
        ]
        self.assertEqual(len(calls), 1)
        prepare = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_prepare_calculation_candidate"
        )
        call = calls[0]
        self.assertIn(call, list(ast.walk(prepare)))
        self.assertEqual(
            ([ast.dump(argument) for argument in call.args], call.keywords),
            ([
                ast.dump(ast.Name(id="runtime_operands", ctx=ast.Load())),
                ast.dump(ast.Name(id="execution_evidence_items", ctx=ast.Load())),
            ], []),
        )
        parents = {
            child: parent
            for parent in ast.walk(prepare)
            for child in ast.iter_child_nodes(parent)
        }

        def top_statement(node):
            while parents.get(node) is not prepare:
                node = parents[node]
            return node

        def statement_index_for_call(name, *, attribute=False):
            selected = next(
                node
                for node in ast.walk(prepare)
                if isinstance(node, ast.Call)
                and (
                    (
                        attribute
                        and isinstance(node.func, ast.Attribute)
                        and node.func.attr == name
                    )
                    or (not attribute and isinstance(node.func, ast.Name) and node.func.id == name)
                )
            )
            return prepare.body.index(top_statement(selected))

        coerce_index = statement_index_for_call("_coerce_operand_row_from_evidence", attribute=True)
        table_index = prepare.body.index(top_statement(call))
        raw_index = statement_index_for_call("repair_krw_normalized_values_from_raw_units")
        operands_index = next(
            index
            for index, statement in enumerate(prepare.body)
            if isinstance(statement, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "operands" for target in statement.targets)
        )
        plan_index = next(
            index
            for index, statement in enumerate(prepare.body)
            if isinstance(statement, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "plan" for target in statement.targets)
        )
        self.assertEqual(
            (table_index - coerce_index, raw_index - table_index, operands_index - raw_index, plan_index - operands_index),
            (1, 1, 1, 1),
        )
        self.assertFalse(any(isinstance(parent, ast.Try) for parent in parents if call in ast.walk(parent)))

    def test_prepare_candidate_adopts_table_krw_unit_repair_and_stops_before_later_work_on_exception(self) -> None:
        from src.agent import financial_graph_calculation as graph_calculation

        agent = FinancialAgentCalculationMixin()
        shared = {"preserve": True}
        events = []
        table_rows = [{"operand_id": "table", "normalized_value": 2.0, "nested": shared}]

        def coerce(row, evidence):
            events.append(("coerce", row, evidence))
            return row

        def table_repair(rows, evidence_items):
            events.append(("table", rows, evidence_items))
            return table_rows

        def raw_repair(rows):
            events.append(("raw", rows))
            self.assertIs(rows, table_rows)
            return rows

        candidate_input = graph_calculation._CalculationCandidateInput(
            calculation_operands=({"operand_id": "input", "nested": shared},),
            calculation_plan={
                "mode": "none",
                "operation": "none",
                "ordered_operand_ids": [],
                "variable_bindings": [],
                "result_unit": "",
            },
            active_subtask={"operation_family": "lookup", "required_operands": []},
            query="lookup",
            evidence_items=({"evidence_id": "ev"},),
            runtime_evidence=({"evidence_id": "runtime"},),
        )
        with (
            patch.object(agent, "_coerce_operand_row_from_evidence", side_effect=coerce),
            patch.object(
                graph_calculation,
                "repair_krw_operand_units_from_table_metadata",
                side_effect=table_repair,
            ) as table,
            patch.object(
                graph_calculation,
                "repair_krw_normalized_values_from_raw_units",
                side_effect=raw_repair,
            ) as raw,
            patch.object(graph_calculation, "apply_operation_sign_policy") as sign,
            patch.object(graph_calculation, "execute_prepared_calculation_plan") as executor,
        ):
            result = agent._prepare_calculation_candidate(candidate_input)
        self.assertEqual(result.status, "insufficient_operands")
        self.assertEqual(result.calculation_operands[0]["operand_id"], "table")
        self.assertIs(result.calculation_operands[0]["nested"], shared)
        table.assert_called_once()
        self.assertEqual(
            table.call_args.args[1],
            [{"evidence_id": "ev"}, {"evidence_id": "runtime"}],
        )
        raw.assert_called_once_with(table_rows)
        self.assertEqual([event[0] for event in events], ["coerce", "table", "raw"])
        sign.assert_not_called()
        executor.assert_not_called()

        class PlanBomb(Mapping):
            def __getitem__(self, key):
                raise RuntimeError(f"plan touched: {key}")

            def __iter__(self):
                raise RuntimeError("plan touched")

            def __len__(self):
                return 0

        stopped_input = candidate_input._replace(calculation_plan=PlanBomb())
        stop_events = []
        with (
            patch.object(
                agent,
                "_coerce_operand_row_from_evidence",
                side_effect=lambda row, _evidence: (stop_events.append("coerce") or row),
            ),
            patch.object(
                graph_calculation,
                "repair_krw_operand_units_from_table_metadata",
                side_effect=lambda _rows, _evidence: (
                    stop_events.append("table"),
                    (_ for _ in ()).throw(RuntimeError("table repair failed")),
                )[1],
            ),
            patch.object(graph_calculation, "repair_krw_normalized_values_from_raw_units") as stopped_raw,
            patch.object(graph_calculation, "apply_operation_sign_policy") as stopped_sign,
            patch.object(graph_calculation, "execute_prepared_calculation_plan") as stopped_executor,
            self.assertRaisesRegex(RuntimeError, "table repair failed"),
        ):
            agent._prepare_calculation_candidate(stopped_input)
        self.assertEqual(stop_events, ["coerce", "table"])
        stopped_raw.assert_not_called()
        stopped_sign.assert_not_called()
        stopped_executor.assert_not_called()

    def test_current_source_lookup_hints_preserves_precedence_copy_laziness_and_exceptions(self) -> None:
        with patch.object(
            operand_resolution,
            "get_financial_ontology",
            side_effect=AssertionError("blank concept must not load ontology"),
        ):
            self.assertEqual(operand_resolution.lookup_hints_for_concept_key("   "), {})

        shared = {"nested": True}
        direct_hints = {"mode": "direct", "shared": shared}

        class DirectOntology:
            def concept(self, key):
                self_key_calls.append(key)
                return {"lookup_hints": direct_hints}

            def all_concept_specs(self):
                raise AssertionError("direct concept must suppress fallback scan")

        self_key_calls = []
        with patch.object(operand_resolution, "get_financial_ontology", return_value=DirectOntology()):
            direct = operand_resolution.lookup_hints_for_concept_key("  Metric  ")
        self.assertEqual(self_key_calls, ["Metric"])
        self.assertEqual(direct, direct_hints)
        self.assertIsNot(direct, direct_hints)
        self.assertIs(direct["shared"], shared)
        direct["mode"] = "changed"
        self.assertEqual(direct_hints["mode"], "direct")

        group_hints = {"mode": "group"}
        fallback_hints = {"mode": "fallback", "shared": shared}
        specs = [
            {"is_group": True, "concept": "Metric", "lookup_hints": group_hints},
            {"concept": "Other", "lookup_hints": {"mode": "other"}},
            {"concept": " Metric ", "lookup_hints": fallback_hints},
            {"concept": "Metric", "lookup_hints": {"mode": "later"}},
        ]

        class FallbackOntology:
            def concept(self, key):
                fallback_concept_calls.append(key)
                return None

            def all_concept_specs(self):
                fallback_events.append("scan")
                return specs

        fallback_concept_calls = []
        fallback_events = []
        with patch.object(operand_resolution, "get_financial_ontology", return_value=FallbackOntology()):
            fallback = operand_resolution.lookup_hints_for_concept_key("Metric")
            missing = operand_resolution.lookup_hints_for_concept_key("Missing")
        self.assertEqual(fallback, fallback_hints)
        self.assertIsNot(fallback, fallback_hints)
        self.assertIs(fallback["shared"], shared)
        self.assertEqual(missing, {})
        self.assertEqual(fallback_concept_calls, ["Metric", "Missing"])
        self.assertEqual(fallback_events, ["scan", "scan"])

        with (
            patch.object(
                operand_resolution,
                "_normalise_spaces",
                side_effect=RuntimeError("normalization failed"),
            ),
            patch.object(operand_resolution, "get_financial_ontology") as stopped_ontology,
            self.assertRaisesRegex(RuntimeError, "normalization failed"),
        ):
            operand_resolution.lookup_hints_for_concept_key("Metric")
        stopped_ontology.assert_not_called()

        with (
            patch.object(
                operand_resolution,
                "get_financial_ontology",
                side_effect=RuntimeError("ontology failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "ontology failed"),
        ):
            operand_resolution.lookup_hints_for_concept_key("Metric")

    def test_current_source_lookup_magnitude_preserves_gates_surfaces_and_exception_order(self) -> None:
        def coerce(**overrides):
            values = {
                "normalized_value": -10.0,
                "normalized_unit": "KRW",
                "raw_value": "(10)",
                "concept": "metric",
                "statement_type": "notes",
                "row_label": "profit metric",
                "semantic_label": "",
            }
            values.update(overrides)
            return operand_resolution.coerce_lookup_magnitude_value(**values)

        with patch.object(
            operand_resolution,
            "lookup_hints_for_concept_key",
            side_effect=AssertionError("early gate must stay lazy"),
        ):
            self.assertIsNone(coerce(normalized_value=None))
            self.assertEqual(coerce(normalized_unit="krw"), -10.0)
            self.assertEqual(coerce(normalized_unit="COUNT"), -10.0)
            self.assertEqual(coerce(normalized_value=0.0), 0.0)
            self.assertEqual(coerce(normalized_value=10.0), 10.0)

        disabled = {"coerce_parenthesized_negative_to_positive_magnitude": False}
        enabled = {
            "coerce_parenthesized_negative_to_positive_magnitude": True,
            "magnitude_surface_tokens": ["profit"],
        }
        with patch.object(operand_resolution, "lookup_hints_for_concept_key", return_value=disabled):
            self.assertEqual(coerce(), -10.0)
        with patch.object(operand_resolution, "lookup_hints_for_concept_key", return_value=enabled):
            self.assertEqual(coerce(statement_type="balance_sheet"), -10.0)
            self.assertEqual(coerce(row_label="other", semantic_label="surface"), -10.0)
            self.assertEqual(coerce(raw_value="10"), -10.0)
            self.assertEqual(coerce(), 10.0)
            self.assertEqual(coerce(row_label="", semantic_label="", raw_value="-10"), 10.0)
        self.assertEqual(
            enabled,
            {
                "coerce_parenthesized_negative_to_positive_magnitude": True,
                "magnitude_surface_tokens": ["profit"],
            },
        )

        events = []

        def hints(concept):
            events.append(("hints", concept))
            return enabled

        def stopped_normalizer(value):
            events.append(("normalize", value))
            raise RuntimeError("statement normalization failed")

        with (
            patch.object(operand_resolution, "lookup_hints_for_concept_key", side_effect=hints),
            patch.object(operand_resolution, "_normalise_spaces", side_effect=stopped_normalizer),
            self.assertRaisesRegex(RuntimeError, "statement normalization failed"),
        ):
            coerce()
        self.assertEqual(events, [("hints", "metric"), ("normalize", "notes")])

        with (
            patch.object(
                operand_resolution,
                "lookup_hints_for_concept_key",
                side_effect=RuntimeError("hint lookup failed"),
            ),
            patch.object(operand_resolution, "_normalise_spaces") as stopped_spaces,
            self.assertRaisesRegex(RuntimeError, "hint lookup failed"),
        ):
            coerce()
        stopped_spaces.assert_not_called()

    def test_current_source_lookup_magnitude_static_bindings_calls_and_acyclic_plan(self) -> None:
        import ast
        import inspect

        from src.agent import financial_graph_helpers
        from src.agent import financial_graph_reconciliation
        from src.agent import financial_reconciliation_candidates
        from src.agent import financial_lookup_recovery

        lookup_source = inspect.getsource(financial_lookup_recovery)
        helper_source = inspect.getsource(financial_graph_helpers)
        reconciliation_source = inspect.getsource(financial_graph_reconciliation)
        candidate_source = inspect.getsource(financial_reconciliation_candidates)
        owner_source = inspect.getsource(operand_resolution)
        modules = {
            "financial_lookup_recovery": ast.parse(lookup_source),
            "financial_graph_helpers": ast.parse(helper_source),
            "financial_graph_reconciliation": ast.parse(reconciliation_source),
            "financial_reconciliation_candidates": ast.parse(candidate_source),
            "financial_operand_resolution": ast.parse(owner_source),
        }
        selected = {"lookup_hints_for_concept_key", "coerce_lookup_magnitude_value"}
        definitions = {
            module: {
                node.name: node.end_lineno - node.lineno + 1
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name in selected
            }
            for module, tree in modules.items()
        }
        self.assertEqual(
            definitions,
            {
                "financial_lookup_recovery": {
                },
                "financial_graph_helpers": {},
                "financial_graph_reconciliation": {},
                "financial_reconciliation_candidates": {},
                "financial_operand_resolution": {
                    "lookup_hints_for_concept_key": 16,
                    "coerce_lookup_magnitude_value": 32,
                },
            },
        )

        call_rows = []
        for module, tree in modules.items():
            parents = {
                child: parent
                for parent in ast.walk(tree)
                for child in ast.iter_child_nodes(parent)
            }
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if name not in selected:
                    continue
                current = node
                try_depth = 0
                while current in parents:
                    current = parents[current]
                    if isinstance(current, ast.Try):
                        try_depth += 1
                    if isinstance(current, ast.FunctionDef):
                        caller = current.name
                        break
                call_rows.append(
                    (
                        name,
                        module,
                        caller,
                        type(node.func).__name__,
                        len(node.args),
                        tuple(keyword.arg for keyword in node.keywords),
                        try_depth,
                    )
                )
        self.assertEqual(
            sorted(call_rows),
            sorted(
                [
                    ("lookup_hints_for_concept_key", "financial_operand_resolution", "coerce_lookup_magnitude_value", "Name", 1, (), 0),
                    ("lookup_hints_for_concept_key", "financial_operand_resolution", "lookup_prefers_canonical_statement_rows", "Name", 1, (), 0),
                    ("lookup_hints_for_concept_key", "financial_operand_resolution", "lookup_canonical_statement_preferences", "Name", 1, (), 0),
                    ("lookup_hints_for_concept_key", "financial_operand_resolution", "lookup_query_surface_preferences", "Name", 1, (), 0),
                    ("coerce_lookup_magnitude_value", "financial_lookup_recovery", "coerce_lookup_magnitude_record", "Name", 0, ("normalized_value", "normalized_unit", "raw_value", "concept", "statement_type", "row_label", "semantic_label"), 0),
                    ("coerce_lookup_magnitude_value", "financial_reconciliation_candidates", "build_operand_row_from_candidate_cell", "Name", 0, ("normalized_value", "normalized_unit", "raw_value", "concept", "statement_type", "row_label", "semantic_label"), 0),
                    ("coerce_lookup_magnitude_value", "financial_operand_resolution", "repair_note_operand_units_from_same_block", "Name", 0, ("normalized_value", "normalized_unit", "raw_value", "concept", "statement_type", "row_label", "semantic_label"), 0),
                ]
            ),
        )

        def imported_modules(tree):
            return {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            }

        owner_module = "src.agent.financial_operand_resolution"
        self.assertIn(owner_module, imported_modules(modules["financial_lookup_recovery"]))
        self.assertIn(owner_module, imported_modules(modules["financial_graph_helpers"]))
        self.assertIn(owner_module, imported_modules(modules["financial_graph_reconciliation"]))
        self.assertIn(owner_module, imported_modules(modules["financial_reconciliation_candidates"]))
        self.assertNotIn("src.agent.financial_lookup_recovery", imported_modules(modules["financial_operand_resolution"]))
        self.assertNotIn("src.agent.financial_graph_helpers", imported_modules(modules["financial_operand_resolution"]))
        self.assertNotIn("src.agent.financial_graph_reconciliation", imported_modules(modules["financial_operand_resolution"]))
        owner_calls = [row for row in call_rows if row[1] == "financial_operand_resolution"]
        self.assertEqual((len(call_rows), len(call_rows) - len(owner_calls), len(owner_calls)), (7, 2, 5))

    def test_current_source_lookup_magnitude_callers_adopt_exact_results_and_stop_on_exception(self) -> None:
        from src.agent import financial_graph_reconciliation
        from src.agent import financial_lookup_recovery
        from src.agent import financial_reconciliation_candidates
        from src.agent.financial_graph_reconciliation import FinancialAgentReconciliationMixin

        shared = {"preserve": True}
        record = {
            "normalized_value": -12.0,
            "normalized_unit": "KRW",
            "raw_value": "(12)",
            "raw_unit": "억원",
            "rendered_value": "(12)억원",
            "concept": "metric",
            "statement_type": "notes",
            "row_label": "Row",
            "label": "Label",
            "matched_operand_label": "Matched",
            "semantic_label": "Semantic",
            "nested": shared,
        }
        evidence = {
            "metadata": {
                "row_label": "EvidenceRow",
                "semantic_label": "EvidenceSemantic",
                "table_value_labels_text": "TableLabels",
            }
        }
        record_before = deepcopy(record)
        evidence_before = deepcopy(evidence)
        record_calls = []

        def record_owner(**kwargs):
            record_calls.append(kwargs)
            return 12.0

        with patch.object(
            financial_lookup_recovery,
            "coerce_lookup_magnitude_value",
            side_effect=record_owner,
        ):
            updated = financial_lookup_recovery.coerce_lookup_magnitude_record(record, evidence)
        self.assertEqual(
            record_calls,
            [
                {
                    "normalized_value": -12.0,
                    "normalized_unit": "KRW",
                    "raw_value": "(12)",
                    "concept": "metric",
                    "statement_type": "notes",
                    "row_label": "Row Label Matched EvidenceRow",
                    "semantic_label": "Semantic EvidenceSemantic TableLabels",
                }
            ],
        )
        self.assertIsNot(updated, record)
        self.assertIs(updated["nested"], shared)
        self.assertEqual(updated["normalized_value"], 12.0)
        self.assertEqual(updated["rendered_value"], "12억원")
        self.assertEqual(updated["source_rendered_value"], "(12)억원")
        self.assertEqual(updated["value_coercion"], "lookup_magnitude_from_source_surface")
        self.assertEqual(record, record_before)
        self.assertEqual(evidence, evidence_before)

        class RawUnitBomb:
            def __str__(self):
                raise AssertionError("post-owner raw unit work must stop")

        stopped_record = {**record, "raw_unit": RawUnitBomb()}
        with (
            patch.object(
                financial_lookup_recovery,
                "coerce_lookup_magnitude_value",
                side_effect=RuntimeError("record owner failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "record owner failed"),
        ):
            financial_lookup_recovery.coerce_lookup_magnitude_record(stopped_record, evidence)

        agent = FinancialAgentReconciliationMixin()
        candidate = {
            "candidate_id": "candidate",
            "source_anchor": "anchor",
            "metadata": {
                "row_label": "SourceRow",
                "semantic_label": "SourceSemantic",
                "statement_type": "notes",
                "table_source_id": "table",
            },
        }
        selected_cell = {"value_text": "(12)", "unit_hint": "억원"}
        operand = {"label": "Metric", "concept": "metric", "role": "numerator"}
        candidate_before = deepcopy(candidate)
        selected_before = deepcopy(selected_cell)
        operand_before = deepcopy(operand)
        reconciliation_calls = []

        def reconciliation_owner(**kwargs):
            reconciliation_calls.append(kwargs)
            return 12.0

        with (
            patch.object(financial_reconciliation_candidates, "_structured_candidate_unit_hint", return_value="억원"),
            patch.object(financial_reconciliation_candidates, "_normalise_operand_value", return_value=(-12.0, "KRW")),
            patch.object(financial_reconciliation_candidates, "_candidate_statement_type", return_value="notes") as statement,
            patch.object(financial_reconciliation_candidates, "coerce_lookup_magnitude_value", side_effect=reconciliation_owner),
            patch.object(financial_reconciliation_candidates, "_resolved_period_text_for_operand", return_value="2023") as period,
        ):
            row = financial_reconciliation_candidates.build_operand_row_from_candidate_cell(
                candidate=candidate,
                selected_cell=selected_cell,
                operand=operand,
                index=2,
                period_focus="current",
                query_years=[2023],
            )
        self.assertEqual(
            reconciliation_calls,
            [
                {
                    "normalized_value": -12.0,
                    "normalized_unit": "KRW",
                    "raw_value": "(12)",
                    "concept": "metric",
                    "statement_type": "notes",
                    "row_label": "SourceRow",
                    "semantic_label": "SourceSemantic",
                }
            ],
        )
        self.assertEqual(row["operand_id"], "op_002")
        self.assertEqual(row["normalized_value"], 12.0)
        self.assertEqual(row["normalized_unit"], "KRW")
        self.assertEqual(row["period"], "2023")
        self.assertEqual(statement.call_count, 2)
        period.assert_called_once()
        self.assertEqual(candidate, candidate_before)
        self.assertEqual(selected_cell, selected_before)
        self.assertEqual(operand, operand_before)

        with (
            patch.object(financial_reconciliation_candidates, "_structured_candidate_unit_hint", return_value="억원"),
            patch.object(financial_reconciliation_candidates, "_normalise_operand_value", return_value=(-12.0, "KRW")),
            patch.object(financial_reconciliation_candidates, "_candidate_statement_type", return_value="notes"),
            patch.object(
                financial_reconciliation_candidates,
                "coerce_lookup_magnitude_value",
                side_effect=RuntimeError("reconciliation owner failed"),
            ),
            patch.object(financial_reconciliation_candidates, "_resolved_period_text_for_operand") as stopped_period,
            self.assertRaisesRegex(RuntimeError, "reconciliation owner failed"),
        ):
            financial_reconciliation_candidates.build_operand_row_from_candidate_cell(
                candidate=candidate,
                selected_cell=selected_cell,
                operand=operand,
                index=2,
                period_focus="current",
                query_years=[2023],
            )
        stopped_period.assert_not_called()

    def test_current_source_row_block_signature_preserves_header_identity_and_soft_failures(self) -> None:
        class RowIndexBomb:
            def __int__(self):
                raise AssertionError("row index must stay lazy without context")

        self.assertEqual(
            operand_resolution.candidate_row_block_signature(
                {"metadata": {"row_index": RowIndexBomb()}}
            ),
            "",
        )
        self.assertEqual(
            operand_resolution.candidate_row_block_signature(
                {"metadata": {"row_context_text": "row", "row_index": "bad"}}
            ),
            "",
        )
        self.assertEqual(
            operand_resolution.candidate_row_block_signature(
                {"metadata": {"row_context_text": "row", "row_index": 3}}
            ),
            "",
        )
        self.assertEqual(
            operand_resolution.candidate_row_block_signature(
                {"metadata": {"row_context_text": "intro\nvalue", "row_index": 1}}
            ),
            "",
        )

        metadata = {
            "row_context_text": " intro \n | Group | \n | Period | Value | \n Data row \n tail ",
            "row_index": 3,
            "table_source_id": "table_main",
            "nested": {"preserve": True},
        }
        candidate = {"metadata": metadata}
        before = deepcopy(candidate)
        self.assertEqual(
            operand_resolution.candidate_row_block_signature(candidate),
            "table_main::1:| Group | || | Period | Value |",
        )
        self.assertEqual(candidate, before)

        class ContextBomb:
            def __str__(self):
                raise RuntimeError("context failed")

        with self.assertRaisesRegex(RuntimeError, "context failed"):
            operand_resolution.candidate_row_block_signature(
                {"metadata": {"row_context_text": ContextBomb(), "row_index": 0}}
            )

        class RuntimeIndexBomb:
            def __int__(self):
                raise RuntimeError("index failed")

        with self.assertRaisesRegex(RuntimeError, "index failed"):
            operand_resolution.candidate_row_block_signature(
                {"metadata": {"row_context_text": "row", "row_index": RuntimeIndexBomb()}}
            )

        with (
            patch.object(
                operand_resolution,
                "_normalise_spaces",
                side_effect=RuntimeError("normalizer failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "normalizer failed"),
        ):
            operand_resolution.candidate_row_block_signature(
                {"metadata": {"row_context_text": "row", "row_index": 0}}
            )

    def test_current_source_note_unit_repair_preserves_grouping_copy_order_and_exceptions(self) -> None:
        from src.agent import financial_graph_reconciliation
        one_row = [{"statement_type": "notes"}]

        class PolicyBomb(dict):
            def get(self, key, default=None):
                raise AssertionError(f"policy touched: {key}")

        with patch.object(operand_resolution, "RECONCILIATION_POLICY", PolicyBomb()):
            self.assertIs(operand_resolution.repair_note_operand_units_from_same_block(one_row, {}), one_row)

        shared = {"preserve": True}
        rows = [
            {"evidence_id": "non_note", "statement_type": "income_statement", "raw_unit": "", "nested": shared},
            {"evidence_id": "a_resolved", "statement_type": "notes", "raw_unit": "억원", "raw_value": "100", "nested": shared},
            {"evidence_id": "a_ambiguous", "statement_type": "notes", "raw_unit": "", "raw_value": "(10)", "matched_operand_concept": "metric", "matched_operand_label": "Metric", "nested": shared},
            {"evidence_id": "a_null", "statement_type": "notes", "raw_unit": "", "raw_value": "null", "matched_operand_concept": "metric", "matched_operand_label": "Metric", "nested": shared},
            {"evidence_id": "b_resolved_one", "statement_type": "notes", "raw_unit": "원", "raw_value": "1", "nested": shared},
            {"evidence_id": "b_resolved_two", "statement_type": "notes", "raw_unit": "천원", "raw_value": "2", "nested": shared},
            {"evidence_id": "b_ambiguous", "statement_type": "notes", "raw_unit": "", "raw_value": "3", "nested": shared},
            {"evidence_id": "c_ambiguous", "statement_type": "notes", "raw_unit": "", "raw_value": "4", "nested": shared},
        ]
        candidate_map = {
            "a_resolved": {"block": "A"},
            "a_ambiguous": {"block": "A"},
            "a_null": {"block": "A"},
            "b_resolved_one": {"block": "B"},
            "b_resolved_two": {"block": "B"},
            "b_ambiguous": {"block": "B"},
            "c_ambiguous": {"block": "C"},
        }
        rows_before = deepcopy(rows)
        candidates_before = deepcopy(candidate_map)
        signature_calls = []
        normalizer_calls = []
        coercion_calls = []

        def signature(candidate):
            signature_calls.append(candidate)
            return candidate.get("block", "")

        def normalizer(raw_value, inherited_unit):
            normalizer_calls.append((raw_value, inherited_unit))
            if raw_value == "null":
                return None, "KRW"
            return -10.0, "KRW"

        def magnitude(**kwargs):
            coercion_calls.append(kwargs)
            return None if kwargs["normalized_value"] is None else abs(kwargs["normalized_value"])

        policy = {"ambiguous_krw_units": [""], "note_statement_type": "notes"}
        with (
            patch.object(operand_resolution, "RECONCILIATION_POLICY", policy),
            patch.object(operand_resolution, "candidate_row_block_signature", side_effect=signature),
            patch.object(operand_resolution, "_normalise_operand_value", side_effect=normalizer),
            patch.object(operand_resolution, "coerce_lookup_magnitude_value", side_effect=magnitude),
        ):
            repaired = operand_resolution.repair_note_operand_units_from_same_block(rows, candidate_map)
        self.assertEqual([candidate.get("block") for candidate in signature_calls], ["A", "A", "A", "B", "B", "B", "C"])
        self.assertEqual(normalizer_calls, [("(10)", "억원"), ("null", "억원")])
        self.assertEqual(len(coercion_calls), 2)
        self.assertEqual(
            coercion_calls[0],
            {
                "normalized_value": -10.0,
                "normalized_unit": "KRW",
                "raw_value": "(10)",
                "concept": "metric",
                "statement_type": "notes",
                "row_label": "Metric",
                "semantic_label": "Metric",
            },
        )
        self.assertEqual(repaired[2]["raw_unit"], "억원")
        self.assertEqual(repaired[2]["normalized_value"], 10.0)
        self.assertEqual(repaired[2]["normalized_unit"], "KRW")
        self.assertEqual(repaired[3]["raw_unit"], "")
        self.assertNotIn("normalized_value", repaired[3])
        self.assertEqual(repaired[6]["raw_unit"], "")
        self.assertEqual(repaired[7]["raw_unit"], "")
        self.assertEqual([row["evidence_id"] for row in repaired], [row["evidence_id"] for row in rows])
        for original, current in zip(rows, repaired):
            self.assertIsNot(current, original)
            self.assertIs(current["nested"], shared)
        self.assertEqual(rows, rows_before)
        self.assertEqual(candidate_map, candidates_before)

        stopped_rows = [
            {"evidence_id": "resolved", "statement_type": "notes", "raw_unit": "억원", "raw_value": "1"},
            {"evidence_id": "ambiguous", "statement_type": "notes", "raw_unit": "", "raw_value": "2"},
        ]
        stopped_candidates = {"resolved": {"block": "A"}, "ambiguous": {"block": "A"}}
        with (
            patch.object(operand_resolution, "RECONCILIATION_POLICY", policy),
            patch.object(
                operand_resolution,
                "candidate_row_block_signature",
                side_effect=RuntimeError("signature failed"),
            ),
            patch.object(operand_resolution, "_normalise_operand_value") as stopped_normalizer,
            patch.object(operand_resolution, "coerce_lookup_magnitude_value") as stopped_coercion,
            self.assertRaisesRegex(RuntimeError, "signature failed"),
        ):
            operand_resolution.repair_note_operand_units_from_same_block(stopped_rows, stopped_candidates)
        stopped_normalizer.assert_not_called()
        stopped_coercion.assert_not_called()

        with (
            patch.object(operand_resolution, "RECONCILIATION_POLICY", policy),
            patch.object(
                operand_resolution,
                "candidate_row_block_signature",
                side_effect=lambda candidate: candidate["block"],
            ),
            patch.object(operand_resolution, "_normalise_operand_value", return_value=(-2.0, "KRW")),
            patch.object(
                operand_resolution,
                "coerce_lookup_magnitude_value",
                side_effect=RuntimeError("coercion failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "coercion failed"),
        ):
            operand_resolution.repair_note_operand_units_from_same_block(stopped_rows, stopped_candidates)

    def test_current_source_note_unit_static_bindings_distribution_dag_and_baseline(self) -> None:
        import ast
        import inspect
        import json
        from pathlib import Path

        from src.agent import financial_graph_helpers
        from src.agent import financial_graph_reconciliation

        modules = {
            "src/agent/financial_graph_helpers.py": ast.parse(inspect.getsource(financial_graph_helpers)),
            "src/agent/financial_graph_reconciliation.py": ast.parse(inspect.getsource(financial_graph_reconciliation)),
            "src/agent/financial_operand_resolution.py": ast.parse(inspect.getsource(operand_resolution)),
        }
        selected = {"candidate_row_block_signature", "repair_note_operand_units_from_same_block"}
        definitions = {
            path: {
                node.name: (node.lineno, node.end_lineno, node.end_lineno - node.lineno + 1, [argument.arg for argument in node.args.args])
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name in selected
            }
            for path, tree in modules.items()
        }
        self.assertEqual(
            definitions,
            {
                "src/agent/financial_graph_helpers.py": {},
                "src/agent/financial_graph_reconciliation.py": {},
                "src/agent/financial_operand_resolution.py": {
                    "candidate_row_block_signature": (3556, 3584, 29, ["candidate"]),
                    "repair_note_operand_units_from_same_block": (3587, 3643, 57, ["operand_rows", "candidate_map"]),
                },
            },
        )

        call_rows = []
        selected_lines = {}
        for path, tree in modules.items():
            parents = {
                child: parent
                for parent in ast.walk(tree)
                for child in ast.iter_child_nodes(parent)
            }
            for name, (start, end, _span, _args) in definitions[path].items():
                selected_lines[path] = selected_lines.get(path, set()) | set(range(start, end + 1))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                name = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else ""
                )
                if name not in selected:
                    continue
                current = node
                try_depth = 0
                caller = ""
                while current in parents:
                    current = parents[current]
                    if isinstance(current, ast.Try):
                        try_depth += 1
                    if isinstance(current, ast.FunctionDef):
                        caller = current.name
                        break
                call_rows.append((name, path, caller, type(node.func).__name__, len(node.args), len(node.keywords), try_depth))
        signature_callers = sorted(row[2] for row in call_rows if row[0] == "candidate_row_block_signature")
        self.assertEqual(
            signature_callers,
            sorted(
                [
                    "_candidate_direct_logical_signature",
                    "_candidate_direct_family_signature",
                    "repair_note_operand_units_from_same_block",
                    "_extract_structured_operands_from_reconciliation",
                    "_extract_structured_operands_from_reconciliation",
                    "_extract_structured_operands_from_reconciliation",
                    "_extract_structured_operands_from_reconciliation",
                ]
            ),
        )
        repair_calls = [row for row in call_rows if row[0] == "repair_note_operand_units_from_same_block"]
        self.assertEqual(
            repair_calls,
            [
                (
                    "repair_note_operand_units_from_same_block",
                    "src/agent/financial_graph_reconciliation.py",
                    "_extract_structured_operands_from_reconciliation",
                    "Name",
                    2,
                    0,
                    0,
                )
            ],
        )
        signature_calls = [row for row in call_rows if row[0] == "candidate_row_block_signature"]
        self.assertEqual((len(signature_calls), len(repair_calls)), (7, 1))
        owner_path = "src/agent/financial_operand_resolution.py"
        owner_local_calls = [row for row in call_rows if row[1] == owner_path]
        self.assertEqual((len(call_rows) - len(owner_local_calls), len(owner_local_calls)), (7, 1))
        self.assertEqual(len(call_rows), 8)
        self.assertTrue(all(row[-1] == 0 for row in call_rows))

        def import_modules(tree):
            return {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            }

        owner_module = "src.agent.financial_operand_resolution"
        self.assertIn(owner_module, import_modules(modules["src/agent/financial_graph_helpers.py"]))
        self.assertIn(owner_module, import_modules(modules["src/agent/financial_graph_reconciliation.py"]))
        self.assertNotIn("src.agent.financial_graph_helpers", import_modules(modules["src/agent/financial_operand_resolution.py"]))
        self.assertNotIn("src.agent.financial_graph_reconciliation", import_modules(modules["src/agent/financial_operand_resolution.py"]))

        baseline = json.loads(Path("tests/fixtures/runtime_domain_terms_baseline.json").read_text(encoding="utf-8"))
        hits = [
            record
            for record in baseline["records"]
            if record.get("path") in selected_lines
            and selected_lines[record["path"]].intersection(record.get("first_lines") or [])
        ]
        self.assertEqual(len(baseline["records"]), 218)
        self.assertEqual(hits, [])

    def test_current_source_structured_operand_caller_adopts_note_unit_repair_and_propagates_failure(self) -> None:
        from src.agent import financial_graph_reconciliation
        from src.agent.financial_graph_reconciliation import FinancialAgentReconciliationMixin

        agent = FinancialAgentReconciliationMixin()
        nested = {"preserve": True}
        active_subtask = {
            "operation_family": "lookup",
            "required_operands": [{"label": "Metric", "required": True, "nested": nested}],
            "constraints": {},
            "preferred_statement_types": [],
        }
        state = {
            "active_subtask": active_subtask,
            "reconciliation_result": {"status": "ready", "matched_operands": []},
            "report_scope": {},
            "nested": {"state": True},
        }
        state_before = deepcopy(state)
        events = []
        final_rows = [{"operand_id": "repaired", "nested": nested}]
        repair_args = []

        def active_owner(subtask, received_state):
            events.append("active")
            self.assertIs(received_state, state)
            self.assertIsNot(subtask, active_subtask)
            self.assertEqual(subtask, active_subtask)
            return active_subtask

        def years_owner(received_state):
            events.append("years")
            self.assertIs(received_state, state)
            return []

        def candidate_owner(received_state):
            events.append("candidates")
            self.assertIs(received_state, state)
            return []

        def pair_owner(**kwargs):
            events.append("pair")
            self.assertEqual(kwargs["required_operands"][0]["label"], "Metric")
            self.assertIs(kwargs["required_operands"][0]["nested"], nested)
            return [], set()

        def expand_owner(candidate_ids, candidate_map):
            events.append("expand")
            self.assertEqual(candidate_ids, [])
            self.assertEqual(candidate_map, {})
            return []

        def repair_owner(rows, candidate_map):
            events.append("repair")
            repair_args.append((rows, candidate_map))
            return final_rows

        with (
            patch.object(financial_graph_reconciliation, "active_subtask_with_sibling_lookup_surfaces", side_effect=active_owner),
            patch.object(financial_graph_reconciliation, "_query_years_from_state", side_effect=years_owner),
            patch.object(agent, "_build_reconciliation_candidates", side_effect=candidate_owner),
            patch.object(financial_graph_reconciliation, "extract_structured_period_pair_rows", side_effect=pair_owner),
            patch.object(financial_graph_reconciliation, "expand_structured_candidate_ids", side_effect=expand_owner),
            patch.object(financial_graph_reconciliation, "repair_note_operand_units_from_same_block", side_effect=repair_owner),
        ):
            result = agent._extract_structured_operands_from_reconciliation(state)
        self.assertIs(result, final_rows)
        self.assertEqual(events, ["active", "years", "candidates", "pair", "expand", "repair"])
        self.assertEqual(len(repair_args), 1)
        self.assertEqual(repair_args[0], ([], {}))
        self.assertEqual(state, state_before)

        failure_events = []
        with (
            patch.object(financial_graph_reconciliation, "active_subtask_with_sibling_lookup_surfaces", return_value=active_subtask),
            patch.object(financial_graph_reconciliation, "_query_years_from_state", return_value=[]),
            patch.object(agent, "_build_reconciliation_candidates", return_value=[]),
            patch.object(financial_graph_reconciliation, "extract_structured_period_pair_rows", return_value=([], set())),
            patch.object(financial_graph_reconciliation, "expand_structured_candidate_ids", return_value=[]),
            patch.object(
                financial_graph_reconciliation,
                "repair_note_operand_units_from_same_block",
                side_effect=lambda _rows, _map: (
                    failure_events.append("repair"),
                    (_ for _ in ()).throw(RuntimeError("repair failed")),
                )[1],
            ),
            self.assertRaisesRegex(RuntimeError, "repair failed"),
        ):
            agent._extract_structured_operands_from_reconciliation(state)
        self.assertEqual(failure_events, ["repair"])
        self.assertEqual(state, state_before)


if __name__ == "__main__":
    unittest.main()
