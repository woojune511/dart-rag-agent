import unittest
from dataclasses import FrozenInstanceError

from src.agent.financial_answer_slots import build_calculated_value_slot
from src.agent.financial_graph_calculation_rendering import render_grounded_operand_display
from src.agent.financial_reconciliation_candidates import build_semantic_candidate_catalog
from src.agent.financial_runtime_normalization import (
    _normalise_operand_value,
    resolve_unit_spec,
    source_display_precision,
)


def _catalog_value(raw_value, raw_unit):
    catalog = build_semantic_candidate_catalog([
        {
            "candidate_id": "sample-source",
            "candidate_kind": "structured_value",
            "source_anchor": "sample",
            "text": f"quantity {raw_value}",
            "metadata": {
                "row_label": "quantity",
                "table_source_id": "sample-table",
                "structured_cells": [{"value_text": raw_value, "unit_hint": raw_unit}],
            },
        }
    ])
    return next(row for row in catalog if row["kind"] == "numeric")


class NumericUnitContractTests(unittest.TestCase):
    def test_canonical_units_are_immutable_and_have_base_displays(self):
        for symbol, display in (("KRW", "원"), ("USD", "USD"), ("COUNT", ""), ("PERCENT", "%")):
            with self.subTest(symbol=symbol):
                spec = resolve_unit_spec(symbol)
                self.assertEqual((spec.normalized_dimension, spec.scale, spec.display_unit), (symbol, 1.0, display))
                self.assertEqual(_normalise_operand_value("1", symbol), (1.0, symbol))
                slot = build_calculated_value_slot(
                    label="quantity", normalized_value=1,
                    normalized_unit=symbol, display_unit=symbol,
                )
                self.assertEqual(slot["rendered_value"], f"1{display}")
                self.assertEqual(
                    render_grounded_operand_display({
                        "raw_value": "1", "raw_unit": symbol,
                        "normalized_value": 1, "normalized_unit": symbol,
                    }),
                    f"1{display}",
                )
                with self.assertRaises(FrozenInstanceError):
                    spec.scale = 10
        self.assertIsNone(resolve_unit_spec(""))
        self.assertIsNone(resolve_unit_spec("UNKNOWN"))
        self.assertIsNone(resolve_unit_spec("unregistered-unit"))

    def test_real_catalog_to_calculated_display_preserves_scale(self):
        for raw_a, raw_b, unit, expected in (
            ("87.0", "78.0", "만 대", "9만 대"),
            ("2", "1", "백만달러", "1백만달러"),
            ("7.5", "2.0", "백만원", "5.5백만원"),
            ("1.83", "1.73", "%p", "0.10%p"),
        ):
            with self.subTest(unit=unit):
                left, right = _catalog_value(raw_a, unit), _catalog_value(raw_b, unit)
                self.assertEqual(left["normalized_unit"], right["normalized_unit"])
                slot = build_calculated_value_slot(
                    label="difference",
                    normalized_value=left["normalized_value"] - right["normalized_value"],
                    normalized_unit=left["normalized_unit"],
                    display_unit=unit,
                )
                self.assertEqual(slot["rendered_value"], expected)

    def test_signed_composite_sources_retain_sign_and_currency(self):
        for raw_value, raw_unit, expected, dimension in (
            ("-1조원", "원", -1e12, "KRW"),
            ("(1조원)", "원", -1e12, "KRW"),
            ("△1조 2억원", "원", -1_000_200_000_000, "KRW"),
            ("▲1조 2억 원", "원", -1_000_200_000_000, "KRW"),
            ("1조달러", "USD", 1e12, "USD"),
            ("(1조 2억달러)", "USD", -1_000_200_000_000, "USD"),
        ):
            with self.subTest(raw_value=raw_value):
                candidate = _catalog_value(raw_value, raw_unit)
                self.assertEqual(candidate["normalized_value"], expected)
                self.assertEqual(candidate["normalized_unit"], dimension)
                self.assertEqual(render_grounded_operand_display(candidate), raw_value)
        self.assertEqual(_normalise_operand_value("1조달러suffix", "USD"), (None, "UNKNOWN"))

    def test_simple_inline_and_parenthesized_sources_preserve_display(self):
        for raw, unit, expected_value, dimension, display in (
            ("(1,234)", "백만원", -1_234_000_000, "KRW", "(1,234)백만원"),
            ("(1.2백만달러)", "USD", -1_200_000, "USD", "(1.2백만달러)"),
            ("-1.2만 대", "개", -12_000, "COUNT", "-1.2만 대"),
            ("1.2%p", "원", 1.2, "PERCENT", "1.2%p"),
            ("3", "items", 3, "COUNT", "3items"),
        ):
            with self.subTest(raw=raw):
                candidate = _catalog_value(raw, unit)
                self.assertEqual(candidate["normalized_value"], expected_value)
                self.assertEqual(candidate["normalized_unit"], dimension)
                self.assertEqual(render_grounded_operand_display(candidate), display)

    def test_source_precision_is_expressed_in_base_units(self):
        for raw, unit, expected in (
            ("1.2", "백만원", 50_000),
            ("1.2만 대", "", 500),
            ("11.5%", "", 0.05),
            ("(1조 2억원)", "원", 50_000_000),
            ("1조달러", "USD", 500_000_000_000),
            ("(1,234)", "백만원", 500_000),
        ):
            with self.subTest(raw=raw, unit=unit):
                self.assertEqual(source_display_precision(raw, unit), expected)

    def test_nonfinite_values_and_scale_overflow_are_not_candidates(self):
        for raw, unit in (("nan", "원"), ("inf", "USD"), ("1e308", "백만원"), ("9" * 400 + "조원", "원")):
            with self.subTest(unit=unit):
                self.assertEqual(_normalise_operand_value(raw, unit), (None, "UNKNOWN"))


if __name__ == "__main__":
    unittest.main()
