"""Explicit document header structure precedes nonnumeric-row inference."""

import json
from pathlib import Path
import unittest
import tempfile
from lxml import etree

from src.processing.financial_parser import FinancialParser
from src.processing.table_records import build_table_row_records
from src.processing.table_structure import build_table_object


class TableHeaderScopeTests(unittest.TestCase):
    def test_new_parser_default_does_not_silently_adopt_an_older_store(self):
        from dataclasses import replace
        from src.config.runtime_contract import CANONICAL_PARSER_SCHEMA_VERSION
        from src.storage.store_manifest import canonical_store_manifest, write_store_manifest, assess_store_readiness

        expected = canonical_store_manifest(collection_name="test")
        self.assertEqual(CANONICAL_PARSER_SCHEMA_VERSION, "financial_parser_v5_inherited_heading_style")
        for version in ("financial_parser_v1", "financial_parser_v3_heading_scope",
                        "financial_parser_v4_label_only_table_context"):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                old = replace(expected, ingest=replace(expected.ingest, parser_schema_version=version))
                path = write_store_manifest(directory, old)
                before = path.read_bytes()
                readiness = assess_store_readiness(directory, expected=expected)
                self.assertFalse(readiness.ready)
                self.assertEqual(readiness.status, "mismatch")
                self.assertEqual(path.read_bytes(), before)

    def test_thead_does_not_absorb_a_textual_business_description(self):
        root = etree.parse(str(Path(__file__).parent / "fixtures/source_context_hierarchy.xml")).getroot()
        table = build_table_object(root.findall(".//TABLE")[1])
        records = build_table_row_records(table, "백만원")
        amount = next(r for r in records if r["row_label"] == "영업이익")
        cell = next(c for c in amount["cells"] if c["value_text"] == "100")
        self.assertEqual(table["header_row_count"], 1)
        self.assertEqual(cell["column_headers"], ["공시금액"])
        self.assertTrue(any("제품을 생산하고 판매합니다." in c["source_text"]
                            for c in table["source_contexts"] if c["relation"] == "table_text_row"))

    def test_explicit_multirow_headers_keep_colspan_and_rowspan_axes(self):
        xml = """<TABLE><THEAD>
          <TR><TH ROWSPAN="2">Metric</TH><TH COLSPAN="2">Amounts</TH></TR>
          <TR><TH>2024</TH><TH>2023</TH></TR></THEAD>
          <TBODY><TR><TD>Quantity</TD><TD>100</TD><TD>90</TD></TR></TBODY></TABLE>"""
        table = build_table_object(etree.fromstring(xml))
        cells = build_table_row_records(table, "")[0]["cells"]
        self.assertEqual(table["header_row_count"], 2)
        self.assertEqual([c["column_headers"] for c in cells], [["Amounts", "2024"], ["Amounts", "2023"]])

    def test_leading_all_th_row_is_header_but_body_row_th_is_not(self):
        xml = """<TABLE><TR><TH>Metric</TH><TH>Value</TH></TR>
          <TR><TH>Description</TH><TD>Textual explanation</TD></TR>
          <TR><TH>Quantity</TH><TD>100</TD></TR></TABLE>"""
        table = build_table_object(etree.fromstring(xml))
        records = build_table_row_records(table, "")
        self.assertEqual(table["header_row_count"], 1)
        self.assertEqual(records[-1]["cells"][0]["column_headers"], ["Value"])
        self.assertEqual(table["grid"][1], ["Description", "Textual explanation"])

    def test_tables_without_header_structure_keep_existing_inference(self):
        table = build_table_object(etree.fromstring(
            "<TABLE><TR><TD>Metric</TD><TD>Value</TD></TR><TR><TD>Quantity</TD><TD>100</TD></TR></TABLE>"))
        self.assertNotIn("header_row_count", table)
        self.assertEqual(build_table_row_records(table, "")[0]["cells"][0]["column_headers"], ["Value"])

    def test_persisted_header_rows_and_header_context_use_the_same_structure(self):
        fixture = Path(__file__).parent / "fixtures/source_context_hierarchy.xml"
        chunks = FinancialParser().process_document(str(fixture), {"year": 2024, "rcept_no": "fixture"})
        table = json.loads(chunks[0].metadata["table_object_json"])
        self.assertEqual(table["header_rows"], [["항목", "공시금액"]])
        self.assertNotIn("제품", table["table_header_context"])
        self.assertEqual(table["header_scope_source"], "thead")


if __name__ == "__main__":
    unittest.main()
