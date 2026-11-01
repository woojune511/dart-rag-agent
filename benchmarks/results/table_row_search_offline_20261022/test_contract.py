import copy
import importlib.util
import unittest
from collections import Counter
from pathlib import Path

spec = importlib.util.spec_from_file_location("row_diagnostic", Path(__file__).with_name("run.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RowContract(unittest.TestCase):
    def fixture(self):
        text = "[unit_hint: GHOST]\n\nItem | Q1 | Q2\nUnits | USD\nAlpha | 10 | (20)\nBeta | 30 | 40"
        meta = {"chunk_uid": "doc:1", "rcept_no": "doc", "section_path": "Section",
                "table_source_id": "table", "table_view": "row_window"}
        obj = {"table_id": "table", "source_document_sha256": "hash", "header_rows": [["Item", "Q1", "Q2"]],
               "rows": [{"row_id": "r1", "row_label": "Alpha", "row_headers": ["Alpha"], "cells": [
                   {"cell_id": "c1", "column_index": 1, "column_headers": ["Q1"], "value_text": "10", "unit_hint": "USD"},
                   {"cell_id": "c2", "column_index": 2, "column_headers": ["Q2"], "value_text": "(20)", "unit_hint": "USD"}]}]}
        return text, meta, obj

    def extract(self, *args):
        return m.row_views(*args, "hash", Counter())

    def test_original_value_header_and_span(self):
        text, meta, obj = self.fixture()
        row, = self.extract(text, meta, obj)
        self.assertEqual(text[slice(*row["parent_span"])], "Alpha | 10 | (20)")
        self.assertIn("Q2 | (20)", row["search_text"])
        self.assertEqual(row["verified_units"], ["USD"])

    def test_full_table_metadata_cannot_expose_missing_parent_row(self):
        text, meta, obj = self.fixture()
        self.assertEqual(self.extract(text.replace("Alpha | 10 | (20)", "Other | 10 | (20)"), meta, obj), [])

    def test_swapped_value_columns_rejected(self):
        text, meta, obj = self.fixture()
        self.assertEqual(self.extract(text.replace("Alpha | 10 | (20)", "Alpha | (20) | 10"), meta, obj), [])

    def test_wrong_header_column_rejected(self):
        text, meta, obj = self.fixture()
        obj["rows"][0]["cells"][0]["column_headers"] = ["Q2"]
        self.assertEqual(self.extract(text, meta, obj), [])

    def test_ambiguous_duplicate_line_rejected(self):
        text, meta, obj = self.fixture()
        self.assertEqual(self.extract(text + "\nAlpha | 10 | (20)", meta, obj), [])

    def test_hidden_prefix_is_not_unit_evidence(self):
        text, meta, obj = self.fixture()
        for cell in obj["rows"][0]["cells"]:
            cell["unit_hint"] = "GHOST"
        row, = self.extract(text, meta, obj)
        self.assertEqual(row["verified_units"], [])
        self.assertNotIn("GHOST", row["search_text"])

    def test_no_report_year_or_alias_injection(self):
        text, meta, obj = self.fixture()
        meta.update(year=2099, table_value_labels_text="INVENTED_ALIAS")
        row, = self.extract(text, meta, obj)
        self.assertNotIn("2099", row["search_text"])
        self.assertNotIn("INVENTED_ALIAS", row["search_text"])

    def test_wrong_source_or_table_rejected(self):
        text, meta, obj = self.fixture()
        for key in ("table_id", "source_document_sha256"):
            bad = copy.deepcopy(obj)
            bad[key] = "wrong"
            self.assertEqual(self.extract(text, meta, bad), [])

    def test_projected_columns_not_assumed_original_positions(self):
        text, meta, obj = self.fixture()
        meta["table_view"] = "column_row_window"
        self.assertEqual(self.extract(text, meta, obj), [])

    def test_one_parent_max_not_sum_and_scope_preserved(self):
        docs = {"a": {"receipt": "x", "order": 0}, "b": {"receipt": "x", "order": 1}, "c": {"receipt": "y", "order": 2}}
        results = m.fold_scores([3., 4., 5., 100.], ["a", "a", "b", "c"], docs, "x")
        self.assertEqual([(r["uid"], r["score"]) for r in results], [("b", 5.), ("a", 4.)])

    def test_network_disabled(self):
        with self.assertRaisesRegex(RuntimeError, "network is disabled"):
            m.socket.create_connection(("example.com", 443))

    def test_parent_packet_is_not_rewritten(self):
        docs = {"doc:1": {"receipt": "doc", "text": " original | 1 ", "metadata": {"company": "X"}}}
        p, omitted = m.packet({"question": "Q", "report_scope": {"rcept_no": "doc"}}, [{"uid": "doc:1"}], docs, ["company"], set())
        self.assertEqual(p["documents"][0]["text"], " original | 1 ")
        self.assertEqual(omitted, [])


if __name__ == "__main__":
    unittest.main()
