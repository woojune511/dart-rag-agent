from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from src.agent.financial_calculation_execution import _same_source_context, project_semantic_program_operand
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog,
    build_semantic_source_candidates,
    semantic_candidate_catalog_fingerprint,
)
from src.agent.financial_source_bundles import build_semantic_source_bundles
from tests.test_semantic_evidence_bundles import _bundle_obligation


def table_document(receipt="report-a", *, chunk="0", values=("10", "20"), year=2024):
    cells = [
        {"cell_id": f"r0:c{index}", "column_index": index,
         "column_headers": ["2024", metric], "value_text": value, "unit_hint": "%"}
        for index, (metric, value) in enumerate(zip(("alpha metric", "beta metric"), values))
    ]
    return SimpleNamespace(
        page_content="Target Entity | " + " | ".join(values),
        metadata={
            "rcept_no": receipt, "chunk_uid": f"{receipt or 'legacy'}:{year}:{chunk}",
            "company": "sample", "year": year, "consolidation_scope": "consolidated",
            "section_path": "sample section", "table_source_id": "sample section::table:1",
            "local_heading": "sample table", "is_table": True, "block_type": "table",
            "table_row_records_json": json.dumps([
                {"row_id": "r0", "row_label": "Target Entity",
                 "row_headers": ["Target Entity"], "cells": cells},
            ]),
        },
    )


def project(retrieved, seed=()):
    sources = build_semantic_source_candidates(
        {"retrieved_docs": [(doc, 0.0) for doc in retrieved],
         "seed_retrieved_docs": [(doc, 0.0) for doc in seed]},
        source_anchor_builder=lambda meta: f"[{meta['company']} | {meta['year']} | {meta['section_path']}]",
    )
    return build_semantic_candidate_catalog(sources)


def cells(catalog):
    return [row for row in catalog if row.get("physical_cell_id")]


def by_id(catalog):
    return {row["candidate_id"]: row for row in catalog}


class SemanticTableIdentityTests(unittest.TestCase):
    def test_different_filings_with_same_local_ids_keep_every_cell(self):
        for values in (("30", "40"), ("10", "20")):
            with self.subTest(values=values):
                docs = [table_document(), table_document("report-b", values=values)]
                before = deepcopy(docs)
                catalog = project(docs)
                numeric = cells(catalog)
                self.assertEqual(len(numeric), 4)
                self.assertEqual(len({r["candidate_id"] for r in numeric}), 4)
                self.assertEqual(len({r["physical_table_id"] for r in numeric}), 2)
                self.assertEqual(len({r["physical_cell_key"] for r in numeric}), 4)
                self.assertEqual(len({r["source_document_id"] for r in numeric}), 2)
                self.assertEqual({r["table_source_id"] for r in numeric}, {"sample section::table:1"})
                self.assertEqual({r["physical_row_id"] for r in numeric}, {"r0"})
                self.assertEqual({r["physical_cell_id"] for r in numeric}, {"r0:c0", "r0:c1"})
                self.assertEqual(docs, before)

    def test_duplicates_dedupe_within_filing_not_across_filings_or_streams(self):
        a, duplicate = table_document(), table_document(chunk="1")
        b = table_document("report-b", values=("30", "40"))
        expected = project([a, b, duplicate])
        self.assertEqual(len(cells(expected)), 4)
        for retrieved, seed in (([duplicate, b, a], []), ([b], [duplicate, a]), ([], [a, b, duplicate])):
            actual = project(retrieved, seed)
            self.assertEqual(semantic_candidate_catalog_fingerprint(actual), semantic_candidate_catalog_fingerprint(expected))
            self.assertEqual(by_id(actual), by_id(expected))

    def test_identity_does_not_depend_on_which_other_reports_are_retrieved(self):
        a, b = table_document(), table_document("report-b")
        alone = {r["candidate_id"] for r in project([a])}
        together = {r["candidate_id"] for r in project([a, b])}
        self.assertEqual(len(together), 2 * len(alone))
        self.assertTrue(alone < together)

    def test_legacy_metadata_uses_report_scope_and_content_without_inventing_receipts(self):
        a = table_document("")
        duplicate = table_document("", chunk="1")
        older = table_document("", year=2023)
        amended = table_document("", chunk="2", values=("30", "40"))
        self.assertEqual(len(cells(project([a, duplicate]))), 2)
        catalog = project([a, duplicate, older, amended])
        self.assertEqual(len(cells(catalog)), 6)
        self.assertTrue(all(not r.get("source_document_id") for r in catalog))
        self.assertEqual(by_id(catalog), by_id(project([amended, older, duplicate, a])))

    def test_explicit_legacy_document_identity_separates_identical_reports(self):
        a, b = table_document(""), table_document("", chunk="1")
        a.metadata["document_id"], b.metadata["document_id"] = "doc-a", "doc-b"
        self.assertEqual(len(cells(project([a, b]))), 4)

    def test_value_only_record_view_uses_the_same_filing_boundary(self):
        docs = [table_document(), table_document("report-b")]
        for doc in docs:
            row = json.loads(doc.metadata.pop("table_row_records_json"))[0]
            doc.metadata["table_value_records_json"] = json.dumps([
                {**cell, "value_id": f"table:v:{index}", "row_index": 0,
                 "row_label": row["row_label"], "row_headers": row["row_headers"]}
                for index, cell in enumerate(row["cells"])
            ])
        catalog = cells(project(docs))
        self.assertEqual(len(catalog), 4)
        self.assertEqual({r["candidate_kind"] for r in catalog}, {"structured_value"})
        self.assertEqual(len({r["physical_table_id"] for r in catalog}), 2)

    def test_relative_period_owner_only_sees_the_matching_filing_cells(self):
        docs = [table_document("report-old", year=2023), table_document()]
        for doc in docs:
            rows = json.loads(doc.metadata["table_row_records_json"])
            for cell, period in zip(rows[0]["cells"], ("당기", "전기")):
                cell["column_headers"][0] = period
            doc.metadata["table_row_records_json"] = json.dumps(rows)
        catalog = project(docs)
        plan = _semantic_candidate_cohorts(catalog, [_bundle_obligation("current", "alpha metric")])
        visible = set(plan["candidate_ids_by_owner"]["current"])
        numeric = [r for r in cells(catalog) if r["candidate_id"] in visible]
        self.assertEqual(len(numeric), 1)
        self.assertEqual(numeric[0]["source_document_id"], "rcept_no:report-a")
        self.assertEqual(numeric[0]["value_year"], 2024)

    def test_execution_evidence_keeps_raw_and_qualified_provenance(self):
        catalog = project([table_document()])
        candidate = cells(catalog)[0]
        cid = candidate["candidate_id"]
        evidence = FinancialAgent._semantic_program_evidence_items(catalog, [cid])[0]
        operand = project_semantic_program_operand(candidate)
        for key in ("source_document_id", "table_source_id", "physical_table_id", "physical_row_id", "physical_cell_id"):
            self.assertEqual(operand[key], candidate[key])
            self.assertEqual(evidence["metadata"].get(key), candidate[key])

    def test_pipe_fallback_and_table_context_share_the_qualified_identity(self):
        a, b = table_document(), table_document("report-b")
        for doc in (a, b):
            del doc.metadata["table_row_records_json"]
            del doc.metadata["table_source_id"]
            doc.metadata["unit_hint"] = "%"
        catalog = project([a, b])
        numeric = cells(catalog)
        self.assertEqual(len(numeric), 4)
        for context in (row for row in catalog if row["candidate_kind"] == "table_context"):
            self.assertIn(context["physical_table_id"], {r["physical_table_id"] for r in numeric})
        self.assertEqual(by_id(catalog), by_id(project([b, a])))

    def test_bundles_and_owner_options_do_not_join_rows_from_different_filings(self):
        catalog = project([table_document(), table_document("report-b", values=("30", "40"))])
        table_bundles = [b for b in build_semantic_source_bundles(catalog) if b.source_kind == "table_row"]
        self.assertEqual(len(table_bundles), 2)
        obligations = [_bundle_obligation("alpha", "alpha metric"), _bundle_obligation("beta", "beta metric")]
        plan = _semantic_candidate_cohorts(catalog, obligations)
        selection = plan["evidence_bundle_option_selections"][0]
        self.assertEqual(selection["complete_option_count"], 2)
        by_id = {row["candidate_id"]: row for row in catalog}
        for bundle in table_bundles:
            self.assertEqual(len({by_id[cid]["source_document_id"] for cid in bundle.candidate_ids}), 1)
        payload = FinancialAgent._semantic_program_prompt_payload(catalog, plan)
        for cid, row in payload["candidates_by_id"].items():
            self.assertEqual(row["source_document_id"], by_id[cid]["source_document_id"])
            self.assertEqual(row["table_source_id"], "sample section::table:1")
        reversed_catalog = project([table_document("report-b", values=("30", "40")), table_document()])
        reversed_plan = _semantic_candidate_cohorts(reversed_catalog, obligations)
        self.assertEqual(plan, reversed_plan)

    def test_scope_witness_cannot_bridge_a_different_filing_via_local_table_or_anchor(self):
        catalog = cells(project([table_document(), table_document("report-b")]))
        self.assertEqual(len(catalog), 4)
        first = catalog[0]
        same = next(r for r in catalog if r["physical_table_id"] == first["physical_table_id"] and r != first)
        other = next(r for r in catalog if r["physical_table_id"] != first["physical_table_id"])
        self.assertTrue(_same_source_context(first, same))
        self.assertFalse(_same_source_context(first, other))
        self.assertFalse(_same_source_context(first, {**other, "physical_table_id": ""}))


if __name__ == "__main__":
    unittest.main()
