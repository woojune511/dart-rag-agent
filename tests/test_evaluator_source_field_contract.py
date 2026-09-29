"""Opt-in source identity must not be inferred from an answer's display label."""

from copy import deepcopy
from dataclasses import asdict
import unittest

from src.ops.evaluator import (
    _compute_accepted_calculation_variant_match,
    _example_from_dict,
    _record_matches_variant_constraints,
)
from tests.test_evaluator_calculation_variants import _example, _trace


def _source_case():
    example = _example()
    example.accepted_calculation_variants = example.accepted_calculation_variants[:1]
    variant = example.accepted_calculation_variants[0]
    operands, plan, result = _trace()
    for expected, actual in zip(variant.expected_operands, operands):
        expected.pop("strict_label")
        expected.update(row_label=actual["label"], strict_period=True,
                        source_period_surface="Reported amount",
                        source_document_id="filing:sample-2024")
        actual.update(row_label=actual["label"], label="User-facing description",
                      source_period_surface="Reported amount",
                      source_document_id="filing:sample-2024")
    variant.expected_calculation_result.pop("strict_label")
    variant.expected_calculation_result["kind"] = "derived_value"
    result["outputs"][-1]["label"] = "Another faithful result description"
    return example, operands, plan, result


def _match(example, operands, plan, result):
    return _compute_accepted_calculation_variant_match(
        example=example, calculation_operands=operands,
        calculation_plan=plan, calculation_result=result)


class EvaluatorSourceFieldContractTests(unittest.TestCase):
    def test_source_row_and_heading_are_separate_from_answer_label_and_period(self):
        case = _source_case()
        before = deepcopy(case)
        self.assertEqual(_match(*case)[0], 1.0)
        self.assertEqual(case, before)

    def test_wrong_or_missing_explicit_source_field_cannot_be_rescued_by_label(self):
        for field in ("row_label", "source_period_surface", "source_document_id"):
            for value in (None, "", "wrong source field"):
                with self.subTest(field=field, value=value):
                    example, operands, plan, result = _source_case()
                    actual = operands[0]
                    actual["label"] = example.accepted_calculation_variants[0].expected_operands[0]["label"]
                    actual["answer_slot"] = {field: actual[field]}
                    if value is None:
                        actual.pop(field)
                    else:
                        actual[field] = value
                    self.assertEqual(_match(example, operands, plan, result)[0], 0.0)

    def test_strict_period_requires_resolved_period_not_filing_or_heading(self):
        for period in (None, "", "2023", "current", "Reported amount", "2024/2023", "2024 Q4"):
            with self.subTest(period=period):
                example, operands, plan, result = _source_case()
                operands[0].update(period=period, value_year=2024,
                                   source_period_surface="Reported amount")
                self.assertEqual(_match(example, operands, plan, result)[0], 0.0)
        example, operands, plan, result = _source_case()
        operands[0]["period"] = "2024년"
        self.assertEqual(_match(example, operands, plan, result)[0], 1.0)

    def test_strict_label_still_matches_answer_identity_not_source_row(self):
        matches, reasons = _record_matches_variant_constraints(
            {"label": "Expected identity", "strict_label": True},
            {"label": "Other identity", "row_label": "Expected identity"})
        self.assertFalse(matches)
        self.assertIn("strict_label_mismatch", reasons)

    def test_undeclared_fields_preserve_legacy_behavior(self):
        example, operands, plan, result = _example(), *_trace()
        operands[0]["period"] = "current"
        self.assertEqual(_match(example, operands, plan, result)[0], 1.0)

    def test_derived_kind_cannot_be_replaced_with_a_direct_result(self):
        example, operands, plan, result = _source_case()
        result["outputs"][-1]["kind"] = "direct_value"
        self.assertEqual(_match(example, operands, plan, result)[0], 0.0)

    def test_existing_source_scope_value_operation_and_binding_guards_remain(self):
        changes = (
            ("operand", "source_anchor", "wrong-source"),
            ("operand", "statement_type", "summary_financials"),
            ("operand", "consolidation_scope", "separate"),
            ("operand", "normalized_value", 500_000_000.0),
            ("result", "normalized_value", 500_000_000.0),
            ("result", "operation_family", "sum"),
            ("result", "candidate_ids", ["cand-left"]),
        )
        for target, field, value in changes:
            with self.subTest(target=target, field=field):
                example, operands, plan, result = _source_case()
                actual = operands[0] if target == "operand" else result["outputs"][-1]
                actual[field] = value
                self.assertEqual(_match(example, operands, plan, result)[0], 0.0)

    def test_explicit_source_fields_accept_only_declared_nonempty_alternatives(self):
        for expected in ("Closing measure", ["Different spelling", "Closing measure"]):
            self.assertTrue(_record_matches_variant_constraints(
                {"row_label": expected}, {"row_label": "Closing measure"})[0])
        for field in ("row_label", "source_period_surface", "source_document_id", "kind"):
            for value in (None, "", [], [""], ["ok", None], 2024, True, {"value": "ok"}):
                with self.subTest(field=field, value=value):
                    expected = {field: value}
                    self.assertFalse(_record_matches_variant_constraints(expected, {})[0])

    def test_loader_rejects_malformed_opt_in_contract_on_operands_and_result(self):
        for field, value in (("strict_period", "true"), ("strict_period", 1),
                             ("row_label", []), ("source_period_surface", None),
                             ("source_document_id", {}), ("kind", "")):
            for result_target in (False, True):
                with self.subTest(field=field, result_target=result_target):
                    item = asdict(_example())
                    variant = item["accepted_calculation_variants"][0]
                    target = variant["expected_calculation_result"] if result_target else variant["expected_operands"][0]
                    target[field] = value
                    with self.assertRaisesRegex(ValueError, field):
                        _example_from_dict(item)

    def test_strict_period_requires_a_nonempty_expected_period(self):
        for value in (None, "", 2024):
            with self.subTest(value=value):
                self.assertFalse(_record_matches_variant_constraints(
                    {"strict_period": True, "period": value}, {"period": "2024"})[0])


if __name__ == "__main__":
    unittest.main()
