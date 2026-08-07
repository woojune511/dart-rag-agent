from __future__ import annotations

import unittest
from copy import deepcopy
from itertools import permutations
from types import SimpleNamespace
from typing import Any, Dict, List

import src.agent.financial_operand_resolution as operand_resolution
from src.agent.financial_graph_calculation import FinancialAgentCalculationMixin
from src.agent.financial_operand_resolution import (
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
    def test_evidence_identity_and_surface_helpers_have_operand_resolution_owner(self) -> None:
        helper_names = (
            "_canonical_structured_reconciliation_id",
            "_canonicalize_structured_operand_reconciliation_refs",
            "_operand_slot_has_evidence_surface_match",
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
