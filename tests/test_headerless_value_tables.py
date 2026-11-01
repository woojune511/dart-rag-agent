"""Recover unambiguous single-row values without inventing column headers."""

import json
import unittest

from lxml import etree

from src.processing.financial_parser import FinancialParser
from src.processing.table_records import (
    build_table_row_records,
    build_table_value_records,
    infer_table_header_row_count,
)
from src.processing.table_structure import build_table_object


class HeaderlessValueTableTests(unittest.TestCase):
    def table(self, xml):
        return build_table_object(etree.fromstring(xml))

    def test_single_label_value_row_retains_original_axes_value_and_unit(self):
        for value in ("2,135,000", "0", "(1,250)", "-12.5", "6.25%"):
            with self.subTest(value=value):
                table = self.table(
                    f"<TABLE><TR><TD>Potential effect</TD><TD>{value}</TD></TR></TABLE>"
                )
                grid_before = [list(row) for row in table["grid"]]
                rows = build_table_row_records(table, "shares")
                self.assertEqual(infer_table_header_row_count(table["grid"]), 0)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["row_headers"], ["Potential effect"])
                self.assertEqual(rows[0]["cells"][0]["column_index"], 1)
                self.assertEqual(rows[0]["cells"][0]["column_headers"], [])
                self.assertEqual(rows[0]["cells"][0]["value_text"], value)
                self.assertEqual(rows[0]["cells"][0]["unit_hint"], "shares")
                values = build_table_value_records(rows, table_id="sample", unit_hint="shares")
                self.assertEqual(len(values), 1)
                self.assertEqual(values[0]["semantic_label"], "Potential effect")
                self.assertEqual(values[0]["value_text"], value)
                self.assertEqual(values[0]["column_headers"], [])
                self.assertEqual(values[0]["unit_hint"], "shares")
                self.assertEqual(table["grid"], grid_before)

    def test_single_row_with_multiple_axis_cells_preserves_blank_coordinates(self):
        table = self.table("""<TABLE><TR><TD>Group A</TD><TD>Quantity</TD>
            <TD>100</TD><TD></TD><TD>90</TD></TR></TABLE>""")
        rows = build_table_row_records(table, "units")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["row_headers"], ["Group A", "Quantity"])
        self.assertEqual([cell["column_index"] for cell in rows[0]["cells"]], [2, 4])
        self.assertEqual([cell["value_text"] for cell in rows[0]["cells"]], ["100", "90"])

    def test_year_only_numeric_headers_remain_headers(self):
        for cells in (
            ["Metric", "2025", "2024"],
            ["Metric", "2025년", "2024년"],
            ["Metric", "2025.12.31", "2024.12.31"],
            ["Metric", "2025", "100"],
        ):
            with self.subTest(cells=cells):
                self.assertEqual(infer_table_header_row_count([cells]), 1)

    def test_explicit_thead_and_th_preserve_numeric_header_authority(self):
        for xml in (
            "<TABLE><THEAD><TR><TD>Quantity</TD><TD>100</TD></TR></THEAD></TABLE>",
            "<TABLE><TR><TH>Quantity</TH><TH>100</TH></TR></TABLE>",
        ):
            with self.subTest(xml=xml):
                table = self.table(xml)
                self.assertEqual(table["header_row_count"], 1)
                self.assertEqual(build_table_row_records(table, "units"), [])

    def test_text_caption_and_unlabelled_numeric_row_are_not_values(self):
        for cells in (
            ["Current period", "(unit: millions)"],
            ["Title", "Title"],
            ["", "100"],
            ["100", "90"],
            ["구분", "100"],
            ["Quantity", "100", "See note"],
        ):
            with self.subTest(cells=cells):
                self.assertEqual(infer_table_header_row_count([cells]), 1)

    def test_multirow_inference_remains_unchanged(self):
        self.assertEqual(infer_table_header_row_count([
            ["Metric", "2025", "2024"], ["Quantity", "100", "90"]
        ]), 1)
        self.assertEqual(infer_table_header_row_count([
            ["Metric", "Amounts", "Amounts"],
            ["Metric", "Current", "Previous"],
            ["Quantity", "100", "90"],
        ]), 2)
        # A first numeric row in a multi-row table remains outside this narrow fix.
        self.assertEqual(infer_table_header_row_count([
            ["Quantity", "100"], ["Other", "90"]
        ]), 1)

    def test_serialized_table_has_value_and_no_fabricated_header(self):
        table = self.table(
            "<TABLE><TR><TD>Potential effect</TD><TD>2,135,000</TD></TR></TABLE>"
        )
        bundle = FinancialParser()._build_table_context_bundle(
            table["table_text"], "Sample", "sample::table:1",
            table_object=table, context_prefix="(단위: 백만원)",
        )
        persisted = json.loads(bundle["table_object_json"])
        self.assertEqual(persisted["header_rows"], [])
        self.assertEqual(persisted["table_header_context"], "")
        self.assertEqual(len(persisted["rows"]), 1)
        self.assertEqual(len(persisted["values"]), 1)
        self.assertEqual(persisted["values"][0]["value_text"], "2,135,000")
        self.assertEqual(persisted["values"][0]["unit_hint"], "백만원")
        self.assertEqual(persisted["values"][0]["column_headers"], [])


if __name__ == "__main__":
    unittest.main()
