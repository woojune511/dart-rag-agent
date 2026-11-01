"""Preserve complete, non-overlapping relative period labels from table axes."""

import json
import unittest
from unittest.mock import patch

from lxml import etree

from src.processing.financial_parser import FinancialParser, _infer_period_focus
from src.processing.table_records import (
    build_table_row_records,
    build_table_value_records,
    extract_period_labels,
)
from src.processing.table_structure import build_table_object


class TablePeriodOverlapTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("Offline only")))

    def test_one_literal_relative_period_produces_one_complete_label(self):
        for label in ("당기", "당기말", "전기", "전기말", "전전기", "전전기말"):
            with self.subTest(label=label):
                self.assertEqual(extract_period_labels(f"② {label} (단위: 천원)"), [label])

    def test_relative_period_focus_does_not_count_nested_substrings(self):
        for label, expected in (("당기", "current"), ("당기말", "current"),
                                ("전기", "prior"), ("전기말", "prior"),
                                ("전전기", "unknown"), ("전전기말", "unknown")):
            with self.subTest(label=label):
                self.assertEqual(_infer_period_focus(extract_period_labels(label)), expected)

    def test_genuine_relative_comparison_preserves_existing_label_priority(self):
        labels = extract_period_labels("전전기말 | 전기말 | 당기말")
        self.assertEqual(labels, ["당기말", "전기말", "전전기말"])
        self.assertEqual(_infer_period_focus(labels), "multi_period")
        self.assertEqual(extract_period_labels("전기 | 당기"), ["당기", "전기"])

    def test_repeated_literal_period_is_deduplicated(self):
        labels = extract_period_labels("당기말\n항목 | 당기말")
        self.assertEqual(labels, ["당기말"])
        self.assertEqual(_infer_period_focus(labels), "current")

    def test_separate_duration_and_endpoint_are_not_semantically_collapsed(self):
        labels = extract_period_labels("당기 | 당기말")
        self.assertEqual(labels, ["당기", "당기말"])
        self.assertEqual(_infer_period_focus(labels), "multi_period")

    def test_absolute_date_and_year_behavior_is_unchanged(self):
        self.assertEqual(extract_period_labels("2024년 2023.12.31"), ["2024", "2023"])
        self.assertEqual(extract_period_labels("2024.01.01 ~ 2024.12.31"), ["2024"])
        self.assertEqual(_infer_period_focus(extract_period_labels("2024년")), "current")
        self.assertEqual(extract_period_labels("제 25 기"), [])
        self.assertEqual(_infer_period_focus([]), "unknown")

    def test_relative_and_absolute_labels_do_not_imply_an_invented_year_link(self):
        labels = extract_period_labels("전전기말 (2023년)")
        self.assertEqual(labels, ["전전기말", "2023"])
        self.assertEqual(_infer_period_focus(labels), "multi_period")

    def test_value_records_keep_the_exact_axis_period_number_and_unit(self):
        source = ("<TABLE><THEAD><TR><TH>항목</TH><TH>전전기말</TH><TH>전기말</TH><TH>당기말</TH>"
                  "</TR></THEAD><TBODY><TR><TD>Quantity</TD><TD>70</TD><TD>90</TD><TD>100</TD>"
                  "</TR></TBODY></TABLE>")
        element = etree.fromstring(source)
        original = etree.tostring(element)
        table = build_table_object(element)
        rows = build_table_row_records(table, "천원")
        values = build_table_value_records(rows, table_id="sample", unit_hint="천원")
        self.assertEqual([value["period_text"] for value in values], ["전전기말", "전기말", "당기말"])
        self.assertEqual([value["period_labels"] for value in values], [["전전기말"], ["전기말"], ["당기말"]])
        self.assertEqual([value["column_headers"] for value in values], [["전전기말"], ["전기말"], ["당기말"]])
        self.assertEqual([value["value_text"] for value in values], ["70", "90", "100"])
        self.assertEqual([value["unit_hint"] for value in values], ["천원"] * 3)
        self.assertEqual([value["column_index"] for value in values], [1, 2, 3])
        self.assertEqual(etree.tostring(element), original)

    def test_bundle_repetition_preserves_single_period_and_original_table(self):
        element = etree.fromstring("<TABLE><THEAD><TR><TH>항목</TH><TH>당기말</TH></TR></THEAD>"
                                   "<TBODY><TR><TD>Quantity</TD><TD>100</TD></TR></TBODY></TABLE>")
        table = build_table_object(element)
        parser = FinancialParser()
        bundle = parser._build_table_context_bundle(table["table_text"], "Synthetic", "sample",
            table_object=table, context_prefix="당기말 (단위: 천원)")
        persisted = json.loads(bundle["table_object_json"])
        self.assertEqual(bundle["period_labels"], ["당기말"])
        self.assertEqual(bundle["period_focus"], "current")
        self.assertEqual(persisted["period_labels"], ["당기말"])
        self.assertEqual(persisted["header_rows"], [["항목", "당기말"]])
        self.assertEqual(persisted["values"][0]["value_text"], "100")
        self.assertEqual(persisted["values"][0]["unit_hint"], "천원")


if __name__ == "__main__":
    unittest.main()
