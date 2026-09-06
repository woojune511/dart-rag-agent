from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from src.agent.financial_candidate_matching import project_candidate_fact
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog,
    build_semantic_source_candidates,
    semantic_candidate_catalog_fingerprint,
)


def document(text: str, *, source_id: str = "source-a", paragraph: bool = False):
    return SimpleNamespace(page_content=text, metadata={
        "chunk_uid": source_id, "company": "sample", "year": 2024,
        "is_table": not paragraph, "block_type": "paragraph" if paragraph else "table",
        "table_source_id": "section::table:1", "unit_hint": "백만원",
        "table_row_records_json": json.dumps([
            {"row_id": "r0", "row_label": "other result", "row_headers": ["other result"],
             "cells": [{"cell_id": "r0:c1", "column_index": 1,
                        "column_headers": ["2024"], "value_text": "123,456", "unit_hint": "백만원"}]},
            {"row_id": "r1", "row_label": "total", "row_headers": ["total"],
             "cells": [{"cell_id": "r1:c1", "column_index": 1,
                        "column_headers": ["2024"], "value_text": "900,000", "unit_hint": "백만원"}]},
        ]),
    })


def catalog(*docs):
    state = {"retrieved_docs": [(doc, 0.0) for doc in docs], "seed_retrieved_docs": []}
    sources = build_semantic_source_candidates(state, source_anchor_builder=lambda _: "[sample]")
    return build_semantic_candidate_catalog(sources)


NOTE = "The production incentive covers units made locally; the amount is included above."
TABLE = f"other result | 123,456\nExplanation | {NOTE}\ntotal | 900,000"


class SemanticSourceContextTests(unittest.TestCase):
    def test_attached_table_keeps_prose_without_duplicate_numeric_cells(self):
        text = (
            "[table_value_labels: 123,456 900,000]\n\n"
            "other result | 123,456\ntotal | 900,000\n\n"
            "The discussion reports an adjustment of 6,700억원.\n\n"
            "The acquired business increased the segment's reach."
        )
        doc = document(text, paragraph=True)
        before = deepcopy(doc.metadata)
        rows = catalog(doc)
        self.assertEqual(doc.metadata, before)
        self.assertEqual(len([r for r in rows if r.get("physical_cell_id")]), 2)
        self.assertEqual(len([r for r in rows if r["raw_value"] == "123,456"]), 1)
        prose = [r for r in rows if r["candidate_kind"] == "sentence_value"]
        self.assertTrue(any(r["raw_value"] == "6,700" for r in prose))
        narrative = [r for r in rows if r["kind"] == "narrative"]
        self.assertTrue(any("increased the segment's reach" in r["source_text"] for r in narrative))
        self.assertFalse(any("table_value_labels" in r["source_text"] for r in narrative))
        self.assertTrue(all(not r["physical_table_id"] for r in prose))

    def test_row_note_is_exact_local_context_not_an_extra_numeric_cell(self):
        rows = catalog(document(TABLE))
        numeric = [r for r in rows if r["kind"] == "numeric"]
        self.assertEqual(len(numeric), 2)
        target = next(r for r in numeric if r["physical_row_id"] == "r0")
        other = next(r for r in numeric if r["physical_row_id"] == "r1")
        self.assertIn(NOTE, target["source_bundle_text"])
        self.assertNotIn(NOTE, other["source_bundle_text"])
        self.assertNotIn("900,000", target["source_bundle_text"])
        context = target["source_context_provenance"]
        start, end = context["source_span"]
        self.assertEqual(context["source_id"], "source-a")
        self.assertEqual(TABLE[start:end], target["source_bundle_text"])
        self.assertEqual(target["row_headers"], ["other result"])
        self.assertIn(NOTE, " ".join(project_candidate_fact(target).text_metric_surfaces))

    def test_physical_identity_survives_context_enrichment(self):
        before = [r for r in catalog(document("other result | 123,456\ntotal | 900,000")) if r["kind"] == "numeric"]
        after = [r for r in catalog(document(TABLE)) if r["kind"] == "numeric"]
        self.assertEqual(semantic_candidate_catalog_fingerprint(before), semantic_candidate_catalog_fingerprint(after))
        for original, enriched in zip(before, after):
            for field in ("candidate_id", "raw_value", "raw_unit", "physical_cell_key", "context_fingerprint"):
                self.assertEqual(original[field], enriched[field])

    def test_bracketed_source_note_after_metadata_prefix_is_preserved(self):
        text = "[section: sample]\nother result | 123,456\n\n[Note: the amount excludes discontinued operations.]"
        rows = catalog(document(text, paragraph=True))
        self.assertTrue(any("[Note:" in r["source_text"] for r in rows if r["kind"] == "narrative"))

    def test_duplicate_attachments_choose_context_independently_of_order(self):
        plain = document("other result | 123,456\ntotal | 900,000", source_id="source-z")
        detailed = document(TABLE)
        forward, reverse = catalog(plain, detailed), catalog(detailed, plain)
        self.assertEqual(semantic_candidate_catalog_fingerprint(forward), semantic_candidate_catalog_fingerprint(reverse))
        for rows in (forward, reverse):
            target = next(r for r in rows if r.get("physical_row_id") == "r0")
            self.assertIn(NOTE, target["source_bundle_text"])
            self.assertEqual(target["source_context_provenance"]["source_id"], "source-a")

    def test_prompt_serializes_row_context_once_with_exact_provenance(self):
        rows = catalog(document(TABLE))
        target = next(r for r in rows if r.get("physical_row_id") == "r0")
        payload = FinancialAgent._semantic_program_prompt_payload(rows, {
            "visible_candidate_ids": [target["candidate_id"]], "cohorts": [],
        })
        self.assertEqual(json.dumps(payload, ensure_ascii=False).count(NOTE), 1)
        prompt_row = payload["candidates_by_id"][target["candidate_id"]]
        self.assertEqual(prompt_row["source_context_provenance"], target["source_context_provenance"])

    def test_ambiguous_matching_row_does_not_borrow_a_note(self):
        text = f"other result | 123,456\nExplanation | {NOTE}\nother result | 123,456\ntotal | 900,000"
        target = next(r for r in catalog(document(text)) if r.get("physical_row_id") == "r0")
        self.assertNotIn(NOTE, target["source_bundle_text"])

    def test_unprojected_numeric_unit_row_is_not_annotation(self):
        text = f"other result | 123,456\nper item | 5,287원\nExplanation | {NOTE}\ntotal | 900,000"
        target = next(r for r in catalog(document(text)) if r.get("physical_row_id") == "r0")
        self.assertNotIn(NOTE, target["source_bundle_text"])
        self.assertNotIn("5,287", target["source_bundle_text"])

    def test_context_does_not_cross_report_scope_when_legacy_table_ids_collide(self):
        earlier = document("other result | 123,456\ntotal | 900,000", source_id="old-report")
        earlier.metadata["year"] = 2023
        current = document(TABLE)
        targets = [r for r in catalog(earlier, current) if r.get("physical_row_id") == "r0"]
        self.assertEqual(len(targets), 2)
        by_year = {r["year"]: r for r in targets}
        self.assertNotIn(NOTE, by_year[2023]["source_bundle_text"])
        self.assertIn(NOTE, by_year[2024]["source_bundle_text"])
        self.assertNotEqual(by_year[2023]["physical_table_id"], by_year[2024]["physical_table_id"])

    def test_adjacent_context_respects_existing_numeric_window(self):
        text = "other result | 123,456\nExplanation | " + "long context " * 60 + "\ntotal | 900,000"
        target = next(r for r in catalog(document(text)) if r.get("physical_row_id") == "r0")
        self.assertLessEqual(len(target["source_bundle_text"]), 420)
        self.assertEqual(target["raw_value"], "123,456")

    def test_repeated_equal_cells_require_all_physical_occurrences(self):
        doc = document(TABLE)
        rows = json.loads(doc.metadata["table_row_records_json"])
        rows[0]["cells"].append({**rows[0]["cells"][0], "cell_id": "r0:c2", "column_index": 2})
        doc.metadata["table_row_records_json"] = json.dumps(rows)
        target = next(r for r in catalog(doc) if r.get("physical_row_id") == "r0")
        self.assertNotIn(NOTE, target["source_bundle_text"])
        doc.page_content = TABLE.replace("other result | 123,456", "other result | 123,456 | 123,456")
        target = next(r for r in catalog(doc) if r.get("physical_row_id") == "r0")
        self.assertIn(NOTE, target["source_bundle_text"])


if __name__ == "__main__":
    unittest.main()
