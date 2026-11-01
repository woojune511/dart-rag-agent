"""Explicit row-unit annotations must not inherit an unrelated table unit."""

import copy
import unittest

from src.processing.table_records import build_table_row_records, build_table_value_records


class TableRowUnitTests(unittest.TestCase):
    def records(self, label, *, table_unit="백만원", axes=None):
        labels = list(axes) if axes is not None else [label]
        table = {
            "row_count": 2,
            "header_row_count": 1,
            "grid": [[*["구분"] * len(labels), "당기", "전기"],
                     [*labels, "36,000", "(1,200)"]],
        }
        original = copy.deepcopy(table)
        rows = build_table_row_records(table, table_unit)
        values = build_table_value_records(rows, table_id="test", unit_hint=table_unit)
        self.assertEqual(table, original)
        self.assertEqual([cell["value_text"] for cell in rows[0]["cells"]],
                         ["36,000", "(1,200)"])
        self.assertEqual([cell["column_headers"] for cell in rows[0]["cells"]],
                         [["당기"], ["전기"]])
        return rows, values

    def assert_unit(self, label, expected, **kwargs):
        rows, values = self.records(label, **kwargs)
        self.assertEqual([cell["unit_hint"] for cell in rows[0]["cells"]], [expected] * 2)
        self.assertEqual([value["unit_hint"] for value in values], [expected] * 2)
        self.assertEqual([value["normalized_unit"] for value in values], ["UNKNOWN"] * 2)
        self.assertEqual([value["normalized_value"] for value in values], [None] * 2)

    def test_scaled_currency_row_annotation_overrides_table_unit(self):
        for currency in ("USD", "CNY", "NOK", "EUR"):
            with self.subTest(currency=currency):
                self.assert_unit(f"금액 (천{currency}) [{currency}, 천]", f"천{currency}")

    def test_explicit_declaration_preserves_source_surface(self):
        self.assert_unit("금액 (단위: 천 USD)", "천 USD")

    def test_foreign_currency_scale_annotation_alone_is_preserved(self):
        self.assert_unit("금액 [CNY, 천]", "CNY, 천")

    def test_repeated_equivalent_annotations_are_not_a_conflict(self):
        self.assert_unit("금액 (천USD) (천 USD) [USD, 천]", "천USD")

    def test_declared_opaque_physical_unit_is_preserved_without_normalization(self):
        self.assert_unit("수량 (단위 : tCO2-eq)", "tCO2-eq")

    def test_explicit_count_and_percent_units_override_table_unit(self):
        for label, unit in (("인원(명)", "명"), ("구성비율(%)", "%"),
                            ("액면가액(원)", "원"), ("교환가액(원/주)", "원/주")):
            with self.subTest(label=label):
                self.assert_unit(label, unit)

    def test_distinct_row_units_do_not_fall_back_to_table_unit(self):
        self.assert_unit("금액(천USD)(천CNY)", "")

    def test_distinct_units_across_row_axes_do_not_fall_back(self):
        self.assert_unit("", "", axes=["금액(천USD)", "차이(백만원)"])

    def test_multiple_units_in_one_declaration_are_ambiguous(self):
        self.assert_unit("항목(단위: 원, %)", "")

    def test_multiple_units_in_one_annotation_are_ambiguous(self):
        self.assert_unit("항목(원, %)", "")

    def test_no_annotation_retains_table_unit(self):
        self.assert_unit("금액", "백만원")

    def test_bare_currency_axis_is_not_a_row_unit_declaration(self):
        for currency in ("USD", "CNY", "NOK", "EUR"):
            with self.subTest(currency=currency):
                self.assert_unit(currency, "천원", table_unit="천원")

    def test_unscaled_currency_reference_does_not_infer_denomination(self):
        self.assert_unit("외화(USD)", "천원", table_unit="천원")

    def test_company_abbreviation_is_not_a_share_unit(self):
        self.assert_unit("(주)예시", "백만원")

    def test_currency_prose_is_not_a_unit_declaration(self):
        for label in ("금액(USD 기준)", "금액(천USD 환산)", "미국 USD 관련 금액"):
            with self.subTest(label=label):
                self.assert_unit(label, "백만원")

    def test_percentage_note_is_not_a_unit_declaration(self):
        for label in ("북미(전기 대비 5%)", "지역(비중 20%)", "금액(주1)"):
            with self.subTest(label=label):
                self.assert_unit(label, "백만원")

    def test_unit_annotation_without_table_hint_is_preserved(self):
        self.assert_unit("금액(천EUR)", "천EUR", table_unit="")

    def test_legacy_value_records_without_cell_unit_can_use_table_unit(self):
        rows = [{"row_label": "금액", "row_headers": ["금액"],
                 "cells": [{"column_index": 1, "column_headers": ["당기"],
                            "value_text": "36,000"}]}]
        values = build_table_value_records(rows, table_id="legacy", unit_hint="천원")
        self.assertEqual(values[0]["unit_hint"], "천원")

    def test_explicit_column_conflict_does_not_get_row_currency(self):
        table = {"row_count": 2, "header_row_count": 1,
                 "grid": [["구분", "금액(천USD)", "변동률(%)"],
                          ["금액(천USD)", "36,000", "5"]]}
        rows = build_table_row_records(table, "백만원")
        values = build_table_value_records(rows, table_id="mixed", unit_hint="백만원")
        self.assertEqual([cell["unit_hint"] for cell in rows[0]["cells"]], ["천USD", ""])
        self.assertEqual([value["unit_hint"] for value in values], ["천USD", ""])

    def test_unresolved_explicit_declaration_does_not_use_table_money(self):
        self.assert_unit("항목(단위: 원 USD)", "")

    def test_repeated_table_declaration_is_not_a_specific_column_unit(self):
        table = {"row_count": 3, "header_row_count": 2,
                 "grid": [["(단위: 백만원)"] * 3,
                          ["구분", "당기", "전기"],
                          ["구성비율(%)", "30", "20"]]}
        rows = build_table_row_records(table, "백만원")
        self.assertEqual([cell["unit_hint"] for cell in rows[0]["cells"]], ["%", "%"])

    def test_named_column_money_still_blocks_a_row_percent_override(self):
        table = {"row_count": 2, "header_row_count": 1,
                 "grid": [["구분", "금액(백만원)"], ["구성비율(%)", "30"]]}
        rows = build_table_row_records(table, "백만원")
        self.assertEqual(rows[0]["cells"][0]["unit_hint"], "")


if __name__ == "__main__":
    unittest.main()
