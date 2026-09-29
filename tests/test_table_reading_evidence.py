"""Physical-row reading must not depend on executable scalar extraction."""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from langchain_core.documents import Document
from src.processing.financial_parser import FinancialParser
from src.agent.financial_reconciliation_candidates import (
    build_semantic_source_candidates, build_semantic_candidate_catalog,
    semantic_candidate_catalog_fingerprint,
)
from src.agent.financial_graph_calculation import (
    FinancialAgentCalculationMixin, _semantic_candidate_cohorts, _semantic_candidate_visibility,
)
from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from src.agent.financial_source_bundles import build_semantic_source_bundles
from tests.semantic_program_test_support import _obligation


class TableReadingEvidenceTests(unittest.TestCase):
    def project(self, rows):
        body = "".join("<TR>" + "".join(f"<TD>{cell}</TD>" for cell in row) + "</TR>" for row in rows)
        source = ('<DOCUMENT><SECTION-1><TITLE ATOC="Y">II. 사업의 내용</TITLE>'
                  '<SECTION-2><TITLE ATOC="Y">1. Overview</TITLE><TABLE>'
                  '<THEAD><TR><TH>Route</TH><TH>Description</TH><TH>Share</TH></TR></THEAD>'
                  f'<TBODY>{body}</TBODY></TABLE></SECTION-2></SECTION-1></DOCUMENT>')
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.xml"
            path.write_text(source, encoding="utf-8")
            chunks = FinancialParser().process_document(str(path), {"company": "Example", "year": 2041, "rcept_no": "anonymous"})
        docs = [Document(page_content=chunk.content, metadata=chunk.metadata) for chunk in chunks]
        sources = build_semantic_source_candidates({"retrieved_docs": [(doc, 0) for doc in docs]}, source_anchor_builder=lambda _: "[Example | 2041 | Overview]")
        return docs, sources, build_semantic_candidate_catalog(sources)

    def test_composite_display_keeps_reading_evidence_without_guessing_scalar(self):
        _, sources, catalog = self.project([("Alpha", "partner locations", "14,200(35%)")])
        rows = [row for row in catalog if "partner locations" in row["source_bundle_text"]]
        self.assertTrue(rows)
        self.assertTrue(all(row["kind"] == "narrative" and row["normalized_value"] is None for row in rows))
        self.assertIn("14,200(35%)", rows[0]["source_bundle_text"])
        self.assertTrue(rows[0]["physical_table_id"] and rows[0]["physical_row_id"])
        self.assertEqual(build_semantic_candidate_catalog(sources), catalog)

    def test_mixed_and_pure_text_rows_survive_beside_numeric_rows(self):
        _, _, catalog = self.project([
            ("Alpha", "partner locations", "35%"),
            ("Beta", "online locations", "14,200(65%)"),
            ("Gamma", "direct locations", "not stated"),
        ])
        for description in ("partner locations", "online locations", "direct locations"):
            with self.subTest(description=description):
                self.assertTrue(any(description in row["source_bundle_text"] for row in catalog))
        self.assertEqual([row["raw_value"] for row in catalog if row["kind"] == "numeric"], ["35%"])

    def test_all_narrative_modes_can_select_numeric_row_text(self):
        _, _, catalog = self.project([("Alpha", "partner locations", "35%"), ("Beta", "online locations", "65%")])
        numeric_ids = {row["candidate_id"] for row in catalog if row["kind"] == "numeric"}
        self.assertEqual(len(numeric_ids), 2)
        for mode in ("declared_inputs", "source_defined_group"):
            with self.subTest(mode=mode):
                owner = _obligation("explain", "narrative", "Describe locations", evidence_mode=mode)
                plan = _semantic_candidate_cohorts(catalog, [owner])
                self.assertTrue(numeric_ids.issubset(plan["visible_candidate_ids"]))
                payload = FinancialAgentCalculationMixin._semantic_program_prompt_payload(catalog, plan)
                self.assertEqual(len(payload["source_bundles_by_id"]), 2)
                for candidate in payload["candidates_by_id"].values():
                    self.assertNotIn("source_text", candidate)

    def test_row_matching_is_not_suppressed_by_prose_kind_preference(self):
        _, _, catalog = self.project([("Alpha", "partner locations", "35%")])
        numeric_id = next(row["candidate_id"] for row in catalog if row["kind"] == "numeric")
        catalog.extend(build_semantic_candidate_catalog([
            {"candidate_id": f"unrelated-{index}", "candidate_kind": "chunk", "source_anchor": "[Example]",
             "text": f"Unrelated background observation {index}.", "metadata": {"is_table": False}}
            for index in range(8)]))
        owner = _obligation("explain", "narrative", "partner locations",
            semantic_target={"local_subjects": [], "concept_keys": [], "metric_surfaces": ["partner locations"]})
        plan = _semantic_candidate_cohorts(catalog, [owner])
        self.assertIn(numeric_id, plan["visible_candidate_ids"])

    def test_duplicate_chunk_order_does_not_change_row_catalog_or_bundles(self):
        docs, _, expected = self.project([("Alpha", "partner locations", "14,200(35%)"), ("Beta", "online locations", "65%")])
        stream = [(doc, 0) for doc in docs]
        for order in (stream * 2, list(reversed(stream)) * 2):
            sources = build_semantic_source_candidates({"retrieved_docs": order}, source_anchor_builder=lambda _: "[Example | 2041 | Overview]")
            catalog = build_semantic_candidate_catalog(sources)
            self.assertEqual(semantic_candidate_catalog_fingerprint(catalog), semantic_candidate_catalog_fingerprint(expected))
            self.assertEqual(build_semantic_source_bundles(catalog), build_semantic_source_bundles(expected))

    def test_reading_only_candidate_cannot_become_a_direct_numeric_value(self):
        _, _, catalog = self.project([("Alpha", "partner locations", "14,200(35%)")])
        self.assertTrue(catalog)
        row = next(row for row in catalog if "partner locations" in row["source_bundle_text"])
        before = deepcopy(catalog)
        validation = validate_semantic_calculation_program(
            program={"direct_bindings": [{"obligation_id": "value", "candidate_id": row["candidate_id"]}]},
            obligations=[_obligation("value", "direct_value", "value")], candidate_catalog=catalog, query="Get the value")
        self.assertIn("unknown_or_nonnumeric_candidate", {error["code"] for error in validation["errors"]})
        self.assertEqual(catalog, before)

    def test_reading_evidence_keeps_owner_visibility_and_scope_authority(self):
        _, _, catalog = self.project([("Alpha", "partner locations", "14,200(35%)"), ("Beta", "online locations", "65%")])
        reading = next(row for row in catalog if row["kind"] == "narrative")
        number = next(row for row in catalog if row["kind"] == "numeric")
        owner = _obligation("explain", "narrative", "Describe locations")
        visibility = _semantic_candidate_visibility(catalog,
            visible_candidate_ids=[row["candidate_id"] for row in catalog],
            candidate_ids_by_owner={"explain": [reading["candidate_id"]], "other": [number["candidate_id"]]})
        def validate(candidate_id, current_owner=owner):
            return validate_semantic_calculation_program(
                program={"narrative_bindings": [{"obligation_id": "explain", "candidate_ids": [candidate_id], "text": "Alpha partner locations"}]},
                obligations=[current_owner], candidate_catalog=catalog, query="Describe locations", candidate_visibility=visibility)
        self.assertEqual(validate(reading["candidate_id"])["status"], "ready")
        self.assertIn("candidate_not_exposed_to_compiler", {e["code"] for e in validate(number["candidate_id"])["errors"]})
        self.assertIn("unknown_narrative_candidate", {e["code"] for e in validate("invented-id")["errors"]})
        conflict = {**owner, "scope": {**owner["scope"], "company": "Different Company"}}
        self.assertNotEqual(validate(reading["candidate_id"], conflict)["status"], "ready")

    def test_reading_only_rows_still_obey_global_narrative_capacity(self):
        catalog = build_semantic_candidate_catalog([
            {"candidate_id": f"row-{index}", "candidate_kind": "structured_row", "source_anchor": f"[Company{index}]",
             "text": "Unresolved 14,200(35%)", "metadata": {"company": f"Company{index}",
                 "physical_table_id": f"table-{index}", "physical_row_id": "row", "row_label": "Unresolved",
                 "structured_cells": [{"value_text": "14,200(35%)", "unit_hint": "%"}]}}
            for index in range(33)])
        self.assertEqual(len(catalog), 33)
        owner = _obligation("explain", "narrative", "Describe sources", evidence_requirements=[
            {"requirement_id": f"req-{index}", "required": True, "scope": {"company": f"Company{index}"}}
            for index in range(33)])
        plan = _semantic_candidate_cohorts(catalog, [owner])
        self.assertEqual(plan["status"], "capacity_exceeded")

    def test_added_text_row_does_not_switch_existing_prose_numeric_projection(self):
        source = "Total 29%.\nAlpha | plain description"
        table = {"table_id": "table-a", "rows": [], "values": [], "source_contexts": []}
        def catalog(contexts):
            metadata = {"chunk_uid": "same-chunk", "is_table": True, "rcept_no": "same-report",
                "table_object_json": json.dumps({**table, "source_contexts": contexts})}
            document = Document(page_content=source, metadata=metadata)
            return build_semantic_candidate_catalog(build_semantic_source_candidates(
                {"retrieved_docs": [(document, 0)]}, source_anchor_builder=lambda _: "[same-report]"))
        before = catalog([])
        after = catalog([{"relation": "table_text_row", "source_locator": "/TABLE/TR[2]",
            "source_text": "Alphaplain description", "source_span": [0, 22]}])
        numeric_before = [row for row in before if row["kind"] == "numeric"]
        self.assertTrue(numeric_before)
        self.assertEqual([row for row in after if row["kind"] == "numeric"], numeric_before)
        self.assertTrue({row["candidate_id"] for row in before}.issubset({row["candidate_id"] for row in after}))


if __name__ == "__main__":
    unittest.main()
