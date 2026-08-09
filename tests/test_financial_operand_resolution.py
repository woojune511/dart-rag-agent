from __future__ import annotations

import re
import unittest
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

    def test_evidence_identity_and_surface_helpers_have_operand_resolution_owner(self) -> None:
        helper_names = (
            "_canonical_structured_reconciliation_id",
            "_canonicalize_structured_operand_reconciliation_refs",
            "_operand_slot_has_evidence_surface_match",
            "repair_operand_normalization_from_rendered_unit",
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


if __name__ == "__main__":
    unittest.main()
