"""Provider-free transition inventory keeps source identity and bytes separate."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.ops.plan_parser_store_successor import compare_index_texts, compare_tables, main, plan_store_successor
from src.processing.financial_parser import FinancialParser
from src.storage.store_manifest import canonical_store_manifest, write_store_manifest


def metadata(table, receipt="filing-a"):
    return {"rcept_no": receipt, "table_object_json": json.dumps(table)}


def table(unit="억원"):
    return {"table_id": "section::table:1", "unit_hint": unit, "header_rows": [["Name", "Value"]],
            "rows": [{"row_id": "2:0", "cells": [{"cell_id": "2:0:1", "value_text": "123", "unit_hint": unit}]}],
            "values": [{"value_id": "2:0:1", "value_text": "123", "unit_hint": unit}]}


class ParserStoreSuccessorTests(unittest.TestCase):
    def test_unit_drift_is_not_mistaken_for_missing_table_or_equal_records(self):
        previous, current = table(), table("십억원")
        current["source_contexts"] = [{"relation": "preceding_block", "source_text": "(단위: 십억원)"}]
        before = deepcopy(previous)
        result = compare_tables([metadata(previous)], [metadata(current)])
        row = result["tables"][0]
        self.assertEqual(row["status"], "changed")
        self.assertEqual(row["changed_fields"], ["rows", "unit_hint", "values"])
        self.assertTrue(row["records_equal_except_unit"])
        self.assertFalse(row["header_changed"])
        self.assertEqual(row["unit"], ["억원", "십억원"])
        self.assertEqual(previous, before)

    def test_header_change_is_separate_from_additive_context(self):
        previous = table()
        current = {**previous, "source_contexts": [{"source_text": "Period"}]}
        self.assertEqual(compare_tables([metadata(previous)], [metadata(current)])["tables"][0]["status"], "additive_only")
        current["header_rows"] = [["Name", "Value", "Prior"]]
        self.assertTrue(compare_tables([metadata(previous)], [metadata(current)])["tables"][0]["header_changed"])

    def test_duplicates_are_deterministic_and_conflicting_variants_remain_ambiguous(self):
        rows = [metadata(table()), metadata(table()), metadata(table("USD")), metadata(table(), "filing-b")]
        result = compare_tables(rows, [metadata(table())])
        self.assertEqual(result, compare_tables(list(reversed(rows)), [metadata(table())]))
        self.assertEqual(result["status_counts"], {"ambiguous_payload": 1, "missing_table": 1})
        self.assertEqual(result["tables"][0]["old_variants"], 2)

    def test_embedding_reuse_requires_exact_full_text_in_the_same_filing(self):
        nodes = {"old": {"metadata": {"rcept_no": "a"}, "text": "prefix\n\n123"}}
        chunks = [SimpleNamespace(metadata={"rcept_no": receipt, "chunk_uid": uid})
                  for receipt, uid in [("a", "new"), ("a", "old"), ("b", "other")]]
        texts = ["prefix\n\n123", "different prefix\n\n123", "prefix\n\n123"]
        result = compare_index_texts(nodes, chunks, texts)
        self.assertEqual(result["exact_text_reuse_candidates"], 1)
        self.assertEqual(result["new_or_changed_texts"], 2)
        self.assertEqual(result["same_uid_same_text"], 0)
        self.assertFalse(result["vector_reuse_verified"])
        self.assertEqual(result, compare_index_texts(nodes, chunks[::-1], texts[::-1]))

    def _fixture_store(self, root):
        source = root / "store"
        source.mkdir()
        fixture = Path(__file__).parent / "fixtures/source_context_hierarchy.xml"
        reports = [{"source_file": str(fixture.resolve()), "metadata": {"year": 2024, "rcept_no": "fixture"}}]
        chunks = FinancialParser(section_parse_budget_sec=0).process_document(str(fixture), reports[0]["metadata"])
        nodes = {chunk.metadata["chunk_uid"]: {"chunk_uid": chunk.metadata["chunk_uid"], "text": chunk.content,
                                              "metadata": chunk.metadata} for chunk in chunks}
        (source / "document_structure_graph.json").write_text(json.dumps({"nodes": nodes}), encoding="utf-8")
        manifest = canonical_store_manifest(collection_name="fixture")
        manifest = replace(manifest, ingest=replace(manifest.ingest, parser_schema_version="financial_parser_v1"))
        write_store_manifest(source, manifest)
        return source, reports

    def test_real_parser_no_call_inventory_does_not_publish_or_modify_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, reports = self._fixture_store(root)
            before = {path: path.read_bytes() for path in source.iterdir()}
            with patch("socket.socket.connect", side_effect=AssertionError("no provider")):
                first = plan_store_successor(source, reports)
                second = plan_store_successor(source, reports)
            self.assertEqual(first, second)
            self.assertEqual(first["provider_calls"], 0)
            self.assertFalse(first["ready_to_publish"])
            self.assertFalse(first["manifest_relabel_allowed"])
            self.assertEqual(first["table_comparison"]["status_counts"], {"additive_only": 3})
            self.assertEqual(before, {path: path.read_bytes() for path in source.iterdir()})

    def test_missing_report_or_payload_fails_before_reparse(self):
        with tempfile.TemporaryDirectory() as directory:
            source, reports = self._fixture_store(Path(directory))
            with patch("src.ops.plan_parser_store_successor._ObservedParser.process_document") as parse:
                with self.assertRaisesRegex(ValueError, "every predecessor filing"):
                    plan_store_successor(source, [])
                graph_path = source / "document_structure_graph.json"
                graph = json.loads(graph_path.read_text(encoding="utf-8"))
                next(iter(graph["nodes"].values()))["metadata"]["table_payload_id"] = "missing"
                graph_path.write_text(json.dumps(graph), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Missing predecessor payload"):
                    plan_store_successor(source, reports)
                parse.assert_not_called()

    def test_cli_cannot_write_inside_predecessor_or_overwrite_an_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, reports = self._fixture_store(root)
            spec = root / "spec.json"
            spec.write_text(json.dumps({"stores": [{"source_store": str(source), "reports": reports}]}), encoding="utf-8")
            for output in (source / "new.json", spec):
                with self.assertRaisesRegex(ValueError, "new and outside"):
                    main(["--spec", str(spec), "--output", str(output)])


if __name__ == "__main__":
    unittest.main()
