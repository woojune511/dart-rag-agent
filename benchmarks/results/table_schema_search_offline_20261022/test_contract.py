"""Offline boundary tests; these do not score any real benchmark question."""
import copy
import socket
import unittest

import run


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.parent = {"receipt": "doc", "text": "item | 123", "metadata": {"table_source_id": "T"}}
        self.obj = {"source_document_sha256": "sha", "table_id": "T", "source_table_locator": "/T", "header_rows": [["item", "2023"]]}
        self.row = {"receipt": "doc", "parent_text_sha256": run.prior.text_sha("item | 123"),
                    "source_document_sha256": "sha", "table_locator": "/T", "parent_span": [0, 10],
                    "raw_line": "item | 123", "row_headers": ["item"],
                    "cells": [{"column_index": 1, "value_text": "123", "column_headers": ["2023"]}]}

    def test_valid_binding(self):
        run.admit_row(self.row, self.parent, self.obj, "sha")

    def test_wrong_cell_column_rejected(self):
        self.row["cells"][0]["column_index"] = 0
        with self.assertRaises(AssertionError):
            run.admit_row(self.row, self.parent, self.obj, "sha")

    def test_wrong_header_rejected(self):
        self.row["cells"][0]["column_headers"] = ["2022"]
        with self.assertRaises(AssertionError):
            run.admit_row(self.row, self.parent, self.obj, "sha")

    def test_tampered_source_rejected(self):
        self.parent["text"] = "item | 999"
        with self.assertRaises(AssertionError):
            run.admit_row(self.row, self.parent, self.obj, "sha")

    def test_wrong_table_rejected(self):
        self.obj["table_id"] = "OTHER"
        with self.assertRaises(AssertionError):
            run.admit_row(self.row, self.parent, self.obj, "sha")

    def test_interleave_dedup_and_fallback(self):
        a = [{"uid": u, "score": 100.0} for u in ["a", "b", "c"]]
        s = [{"uid": u, "score": 0.01} for u in ["a", "z", "b"]]
        self.assertEqual([x["uid"] for x in run.interleave(a, s, 4)], ["a", "z", "b", "c"])
        self.assertEqual([x["uid"] for x in run.interleave(a, [], 4)], ["a", "b", "c"])

    def test_table_route_scope_and_original_owner_lookup(self):
        docs = {u: {"order": i} for i, u in enumerate(["a", "b", "c", "x"])}
        tables = [{"table_key": "T", "receipt": "doc", "owners": ["a", "b"]},
                  {"table_key": "U", "receipt": "doc", "owners": ["c"]},
                  {"table_key": "X", "receipt": "other", "owners": ["x"]}]
        hits, ranks = run.table_sources([2, 1, 1000], tables, docs, [1, 5, 7, 100], "doc")
        self.assertEqual([h["uid"] for h in hits], ["b", "c", "a"])
        self.assertEqual([h["table_key"] for h in ranks], ["T", "U"])

    def test_network_denied(self):
        with self.assertRaises(RuntimeError):
            socket.create_connection(("example.invalid", 443))


if __name__ == "__main__":
    unittest.main()
