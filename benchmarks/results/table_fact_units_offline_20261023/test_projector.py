"""Synthetic-only unit contracts; no report/panel or model/store imports."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import unittest

from lxml import etree

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("fact_unit_projector", HERE / "projector.py")
projector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projector)
SHA = "1" * 64


def ctx(node, tree, relation="preceding_block"):
    text = "".join(node.itertext())
    return {"document_sha256": SHA, "source_locator": tree.getpath(node),
            "parent_locator": tree.getpath(node.getparent()), "source_span": [0, len(text)],
            "source_text": text, "relation": relation}


def fixture():
    tree = etree.ElementTree(etree.fromstring(
        b'<DOCUMENT><BODY><TITLE>Report</TITLE><P>Currency: million; ratios retain %</P>'
        b'<TABLE><THEAD><TR><TH>Item</TH><TH>Current</TH><TH>Prior</TH></TR></THEAD>'
        b'<TBODY><TR><TD>Operating result</TD><TD>10</TD><TD>20</TD></TR></TBODY>'
        b'</TABLE><P>Next heading</P></BODY></DOCUMENT>'
    ))
    table = tree.xpath('//TABLE')[0]
    obj = {"table_id": "s::table:1", "source_document_sha256": SHA,
           "source_table_locator": tree.getpath(table), "row_count": 2, "column_count": 3,
           "header_rows": [["Item", "Current", "Prior"]],
           "rows": [{"row_id": "2:0", "row_headers": ["Operating result"], "cells": [
               {"column_index": 1, "column_headers": ["Current"], "value_text": "10", "unit_hint": "%"},
               {"column_index": 2, "column_headers": ["Prior"], "value_text": "20", "period_text": "1900"},
           ]}], "source_contexts": [ctx(table.getprevious(), tree)],
           "unit_hint": "%", "company": "Not the table subject", "period_text": "1900"}
    return tree, obj


def run(tree, obj):
    return projector.build_units({"table_object_json": json.dumps(obj), "table_source_id": obj["table_id"],
                                  "chunk_uid": "synthetic:1:0", "company": "File issuer"}, tree, SHA)


def aggregate_fixture():
    tree = etree.ElementTree(etree.fromstring(
        b'<DOCUMENT><TABLE><TR><TH>Item</TH><TH>Subitem</TH><TH>Current</TH><TH>Prior</TH></TR>'
        b'<TR><TD>Detail</TD><TD>One</TD><TD>10</TD><TD>20</TD></TR>'
        b'<TR><TD>Sum</TD><TD>-</TD><TD>-</TD><TD>99</TD></TR></TABLE></DOCUMENT>'
    ))
    obj = {"table_id": "s::table:1", "source_document_sha256": SHA,
           "source_table_locator": "/DOCUMENT/TABLE", "row_count": 3, "column_count": 4,
           "header_rows": [["Item", "Subitem", "Current", "Prior"]], "source_contexts": [],
           "rows": [
               {"row_id": "3:0", "row_headers": ["Detail", "One"], "cells": [
                   {"column_index": 2, "column_headers": ["Current"], "value_text": "10"},
                   {"column_index": 3, "column_headers": ["Prior"], "value_text": "20"}]},
               {"row_id": "3:1", "row_headers": ["Sum", "-"], "cells": [
                   {"column_index": 3, "column_headers": ["Prior"], "value_text": "99"}]},
           ]}
    return tree, obj


class UnitProjectionContracts(unittest.TestCase):
    def globally_rejects(self, tree, obj, reason):
        projection, receipt = run(tree, obj)
        self.assertIsNone(projection)
        self.assertEqual("REJECTED", receipt["status"])
        self.assertEqual(reason, receipt["reason"], receipt)

    def test_two_units_with_complete_dependency_references(self):
        tree, obj = fixture(); projection, receipt = run(tree, obj)
        self.assertEqual("ADMITTED", receipt["status"])
        self.assertEqual([[1, 1], [1, 2]], [u["at"] for u in projection["units"]])
        for unit in projection["units"]:
            self.assertTrue(all(loc in projection["cells"] for loc in [unit["value"], *unit["row_axes"], *unit["column_axes"]]))
        self.assertEqual([0], projection["frame"]["declared_header_source_tr_indices"])
        self.assertEqual(2, len(receipt["unit_witnesses"]))

    def test_no_scalar_semantic_fields_exported(self):
        tree, obj = fixture(); projection, receipt = run(tree, obj)
        def keys(x):
            if isinstance(x, dict):
                return set(x) | set().union(*(keys(v) for v in x.values()))
            if isinstance(x, list):
                return set().union(*(keys(v) for v in x))
            return set()
        self.assertFalse(set(projector.IGNORED_SCALARS) & keys(projection))
        self.assertNotIn("Not the table subject", json.dumps(projection))
        self.assertFalse(receipt["semantic_axis_assignments_certified"])

    def test_bad_aggregate_row_does_not_poison_detail_units(self):
        tree, obj = aggregate_fixture(); projection, receipt = run(tree, obj)
        self.assertEqual([[1, 2], [1, 3]], [u["at"] for u in projection["units"]])
        self.assertEqual("row_axis_not_unique_or_missing", receipt["rows"][1]["reason"])
        self.assertNotIn("99", [c[4] for c in projection["cells"].values()])

    def test_changed_value_rejects_only_that_cell(self):
        tree, obj = fixture(); obj["rows"][0]["cells"][0]["value_text"] = "99"
        projection, receipt = run(tree, obj)
        self.assertEqual([[1, 2]], [u["at"] for u in projection["units"]])
        self.assertEqual("cell_value_or_column_mismatch", receipt["rows"][0]["cells"][0]["reason"])

    def test_duplicate_column_rejects_entire_row_before_first_cell(self):
        tree, obj = fixture(); obj["rows"][0]["cells"][1]["column_index"] = 1
        projection, receipt = run(tree, obj)
        self.assertIsNone(projection)
        self.assertEqual("NO_UNITS", receipt["status"])
        self.assertEqual("duplicate_column_address", receipt["rows"][0]["reason"])
        self.assertEqual([], receipt["rows"][0]["cells"])

    def test_outside_column_contaminates_row_axes(self):
        tree, obj = fixture(); obj["rows"][0]["cells"][1]["column_index"] = 99
        projection, receipt = run(tree, obj)
        self.assertIsNone(projection)
        self.assertEqual("outside_column_index", receipt["rows"][0]["reason"])

    def test_bool_column_is_not_integer_address(self):
        tree, obj = fixture(); obj["rows"][0]["cells"][0]["column_index"] = True
        projection, receipt = run(tree, obj)
        self.assertIsNone(projection)
        self.assertEqual("invalid_column_index", receipt["rows"][0]["reason"])

    def test_duplicate_rows_reject_all_declarations(self):
        tree, obj = fixture(); obj["rows"].append(copy.deepcopy(obj["rows"][0]))
        projection, receipt = run(tree, obj)
        self.assertIsNone(projection)
        self.assertEqual(["duplicate_row_address"] * 2, [r["reason"] for r in receipt["rows"]])

    def test_bad_row_address_does_not_poison_valid_other_row(self):
        tree, obj = aggregate_fixture(); obj["rows"][1]["row_id"] = "3:99"
        projection, receipt = run(tree, obj)
        self.assertEqual(2, len(projection["units"]))
        self.assertEqual("outside_row_id", receipt["rows"][1]["reason"])

    def test_row_axis_failure_propagates_to_all_values(self):
        tree, obj = fixture(); obj["rows"][0]["row_headers"] = ["Absent"]
        projection, receipt = run(tree, obj)
        self.assertIsNone(projection)
        self.assertEqual("row_axis_not_unique_or_missing", receipt["rows"][0]["reason"])
        self.assertEqual([], receipt["rows"][0]["cells"])

    def test_bad_cell_header_rejects_only_dependent_cell_even_repeated_value(self):
        tree, obj = fixture(); tree.xpath('//TBODY/TR/TD[3]')[0].text = "10"
        obj["rows"][0]["cells"][1]["value_text"] = "10"
        obj["rows"][0]["cells"][0]["column_headers"] = ["Prior"]
        projection, receipt = run(tree, obj)
        self.assertEqual([[1, 2]], [u["at"] for u in projection["units"]])
        self.assertEqual("column_header_mismatch", receipt["rows"][0]["cells"][0]["reason"])

    def test_repeated_values_keep_distinct_source_cells(self):
        tree, obj = fixture(); tree.xpath('//TBODY/TR/TD[3]')[0].text = "10"
        obj["rows"][0]["cells"][1]["value_text"] = "10"
        projection, _ = run(tree, obj)
        self.assertNotEqual(projection["units"][0]["value"], projection["units"][1]["value"])
        self.assertNotEqual(projection["units"][0]["unit_id"], projection["units"][1]["unit_id"])

    def test_missing_value_cell_never_filled_from_xml(self):
        tree, obj = fixture(); obj["rows"][0]["cells"].pop()
        projection, _ = run(tree, obj)
        self.assertEqual([[1, 1]], [u["at"] for u in projection["units"]])
        self.assertNotIn("20", [c[4] for c in projection["cells"].values()])

    def test_text_row_cannot_add_new_numeric_candidate(self):
        tree, obj = fixture(); obj["rows"][0]["cells"].pop()
        obj["source_contexts"].append(ctx(tree.xpath('//TBODY/TR')[0], tree, "table_text_row"))
        projection, receipt = run(tree, obj)
        self.assertEqual(1, len(projection["units"]))
        self.assertEqual("EXCLUDED", receipt["contexts"][1]["status"])
        self.assertEqual(1, len(projection["frame"]["literal_source_contexts"]))

    def test_bad_context_span_excluded_without_poisoning_units(self):
        tree, obj = fixture(); obj["source_contexts"][0]["source_span"][0] = 1
        projection, receipt = run(tree, obj)
        self.assertEqual(2, len(projection["units"]))
        self.assertEqual([], projection["frame"]["literal_source_contexts"])
        self.assertEqual("context_text_span_mismatch", receipt["contexts"][0]["reason"])

    def test_bad_context_hash_excluded_without_scalar_fallback(self):
        tree, obj = fixture(); obj["source_contexts"][0]["document_sha256"] = "2" * 64
        projection, receipt = run(tree, obj)
        self.assertEqual([], projection["frame"]["literal_source_contexts"])
        self.assertEqual("context_hash_mismatch", receipt["contexts"][0]["reason"])
        self.assertNotIn("1900", json.dumps(projection))

    def test_false_preceding_relation_is_excluded(self):
        tree, obj = fixture(); after = tree.xpath('//TABLE')[0].getnext()
        after.text = obj["source_contexts"][0]["source_text"]
        obj["source_contexts"] = [ctx(after, tree)]
        projection, receipt = run(tree, obj)
        self.assertEqual([], projection["frame"]["literal_source_contexts"])
        self.assertEqual("context_relation_mismatch", receipt["contexts"][0]["reason"])

    def test_following_context_excluded(self):
        tree, obj = fixture(); obj["source_contexts"].append(ctx(tree.xpath('//TABLE')[0].getnext(), tree, "following_block"))
        projection, receipt = run(tree, obj)
        self.assertEqual(1, len(projection["frame"]["literal_source_contexts"]))
        self.assertEqual("EXCLUDED", receipt["contexts"][1]["status"])

    def test_invalid_context_container_is_local(self):
        tree, obj = fixture(); obj["source_contexts"] = "broken"
        projection, receipt = run(tree, obj)
        self.assertEqual(2, len(projection["units"]))
        self.assertEqual("invalid_source_contexts", receipt["contexts"][0]["reason"])

    def test_global_header_prefix_gate_even_if_other_column_changed(self):
        tree, obj = fixture(); obj["header_rows"][0][0] = "Different"
        self.globally_rejects(tree, obj, "header_prefix_mismatch")

    def test_global_header_shape_gate(self):
        tree, obj = fixture(); obj["header_rows"][0].pop()
        self.globally_rejects(tree, obj, "header_prefix_mismatch")

    def test_wrong_source_hash_is_global(self):
        tree, obj = fixture(); obj["source_document_sha256"] = "2" * 64
        self.globally_rejects(tree, obj, "table_document_hash_mismatch")

    def test_nested_table_is_global(self):
        tree, obj = fixture(); tree.xpath('//TBODY/TR/TD')[0].append(etree.fromstring(b'<TABLE><TR><TD>X</TD></TR></TABLE>'))
        self.globally_rejects(tree, obj, "nested_table")

    def test_span_origin_and_shared_header_dedupe(self):
        tree = etree.ElementTree(etree.fromstring(b'<DOCUMENT><TABLE><TR><TH>Item</TH><TH COLSPAN="2">Both</TH></TR><TR><TD>A</TD><TD>1</TD><TD>2</TD></TR></TABLE></DOCUMENT>'))
        obj = {"table_id": "t", "source_document_sha256": SHA, "source_table_locator": "/DOCUMENT/TABLE",
               "row_count": 2, "column_count": 3, "header_rows": [["Item", "Both", "Both"]], "source_contexts": [],
               "rows": [{"row_id": "2:0", "row_headers": ["A"], "cells": [
                   {"column_index": 1, "column_headers": ["Both"], "value_text": "1"},
                   {"column_index": 2, "column_headers": ["Both"], "value_text": "2"}]}]}
        projection, receipt = run(tree, obj)
        shared = tree.getpath(tree.xpath('//TH[2]')[0])
        self.assertEqual([0, 1, 1, 2, "Both"], projection["cells"][shared])
        self.assertTrue(all(shared in u["column_axes"] for u in projection["units"]))
        self.assertEqual(1, sum(loc == shared for loc in projection["cells"]))
        self.assertEqual([[0, 1], [0, 2]], next(c for c in receipt["cell_mapping"] if c["cell_locator"] == shared)["expanded_coordinates"])

    def test_raw_tr_and_expanded_row_are_distinct(self):
        tree, obj = fixture(); body = tree.xpath('//TBODY')[0]
        body.insert(0, etree.fromstring(b'<TR><TD></TD><TD></TD><TD></TD></TR>'))
        projection, receipt = run(tree, obj)
        self.assertEqual([1, 1], projection["units"][0]["at"])
        self.assertEqual(2, projection["cells"][projection["units"][0]["value"]][0])
        self.assertEqual([1], receipt["raw_row_mapping"]["dropped_empty_source_tr_indices"])

    def test_value_colspan_retains_every_occupied_column_header(self):
        tree = etree.ElementTree(etree.fromstring(b'<DOCUMENT><TABLE><TR><TH>Item</TH><TH>Current</TH><TH>Prior</TH></TR><TR><TD>A</TD><TD COLSPAN="2">10</TD></TR></TABLE></DOCUMENT>'))
        obj = {"table_id": "t", "source_document_sha256": SHA, "source_table_locator": "/DOCUMENT/TABLE",
               "row_count": 2, "column_count": 3, "header_rows": [["Item", "Current", "Prior"]], "source_contexts": [],
               "rows": [{"row_id": "2:0", "row_headers": ["A"], "cells": [
                   {"column_index": 1, "column_headers": ["Current"], "value_text": "10"}]}]}
        projection, _ = run(tree, obj); unit = projection["units"][0]
        self.assertEqual([1, 1, 1, 2, "10"], projection["cells"][unit["value"]])
        self.assertEqual(["Item", "Current", "Prior"], [projection["cells"][loc][4] for loc in unit["column_axes"]])

    def test_rowspan_axis_keeps_raw_origin_and_current_row_binding(self):
        tree = etree.ElementTree(etree.fromstring(b'<DOCUMENT><TABLE><TR><TH>Item</TH><TH>Amount</TH></TR><TR><TD ROWSPAN="2">A</TD><TD>10</TD></TR><TR><TD>20</TD></TR></TABLE></DOCUMENT>'))
        obj = {"table_id": "t", "source_document_sha256": SHA, "source_table_locator": "/DOCUMENT/TABLE",
               "row_count": 3, "column_count": 2, "header_rows": [["Item", "Amount"]], "source_contexts": [],
               "rows": [{"row_id": "3:0", "row_headers": ["A"], "cells": [
                   {"column_index": 1, "column_headers": ["Amount"], "value_text": "10"}]},
                        {"row_id": "3:1", "row_headers": ["A"], "cells": [
                   {"column_index": 1, "column_headers": ["Amount"], "value_text": "20"}]}]}
        projection, _ = run(tree, obj); first, second = projection["units"]
        self.assertEqual([2, 1], second["at"])
        self.assertEqual(first["row_axes"], second["row_axes"])
        self.assertEqual([1, 0, 2, 1, "A"], projection["cells"][second["row_axes"][0]])

    def test_inferred_leading_data_not_declared_header(self):
        tree, obj = fixture(); tree.xpath('//THEAD')[0].tag = 'TBODY'
        for node in tree.xpath('//TH'): node.tag = 'TD'
        projection, _ = run(tree, obj)
        self.assertEqual([], projection["frame"]["declared_header_source_tr_indices"])
        self.assertIn("Current", [projection["cells"][loc][4] for loc in projection["units"][0]["column_axes"]])

    def test_acquisition_date_preserves_its_own_column_role(self):
        tree = etree.ElementTree(etree.fromstring(b'<DOCUMENT><TABLE><TR><TH>Company</TH><TH>Acquired</TH><TH>Closing balance</TH></TR><TR><TD>Alpha</TD><TD>2020.03.01</TD><TD>100</TD></TR></TABLE></DOCUMENT>'))
        obj = {"table_id": "t", "source_document_sha256": SHA, "source_table_locator": "/DOCUMENT/TABLE",
               "row_count": 2, "column_count": 3, "header_rows": [["Company", "Acquired", "Closing balance"]], "source_contexts": [],
               "rows": [{"row_id": "2:0", "row_headers": ["Alpha", "2020.03.01"], "cells": [
                   {"column_index": 2, "column_headers": ["Closing balance"], "value_text": "100", "period_text": "2020"}]}]}
        projection, _ = run(tree, obj); unit = projection["units"][0]
        self.assertEqual(["Company", "Acquired", "Closing balance"], [projection["cells"][loc][4] for loc in unit["column_axes"]])
        self.assertEqual(["Alpha", "2020.03.01"], [projection["cells"][loc][4] for loc in unit["row_axes"]])
        self.assertNotIn("period_text", json.dumps(projection))

    def test_empty_axes_explicitly_unresolved(self):
        tree, obj = fixture(); obj["rows"][0]["row_headers"] = []
        projection, receipt = run(tree, obj)
        self.assertEqual(2, len(projection["units"]))
        self.assertTrue(all(w["empty_row_axes"] for w in receipt["unit_witnesses"]))
        self.assertTrue(all(w["semantic_axes_unresolved"] for w in receipt["unit_witnesses"]))

    def test_no_numeric_rows_is_not_whole_table_failure(self):
        tree, obj = fixture(); obj["rows"] = []
        projection, receipt = run(tree, obj)
        self.assertIsNone(projection)
        self.assertEqual("NO_UNITS", receipt["status"])
        self.assertTrue(receipt["global_validation_passed"])

    def test_deterministic_order_ignores_record_and_cell_input_order(self):
        tree, obj = aggregate_fixture(); obj["rows"][1]["row_headers"] = ["Sum"]
        first, _ = run(tree, obj)
        obj["rows"].reverse()
        for row in obj["rows"]: row["cells"].reverse()
        second, _ = run(tree, obj)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main(verbosity=2)
