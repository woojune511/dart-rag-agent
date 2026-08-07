import unittest
from copy import deepcopy

from src.agent.financial_dependency_projection import (
    align_dependency_rows_with_sibling_direct_context,
    decide_task_output_operand_resolution,
    filter_direct_rows_by_dependency_producer_scope,
    period_comparison_direct_rows_conflict_with_dependency_outputs,
    prefer_complete_ratio_direct_context_rows,
    resolve_dependency_producer_scope,
)


class FinancialDependencyProjectionTests(unittest.TestCase):
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
