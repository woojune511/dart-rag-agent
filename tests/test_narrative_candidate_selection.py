"""Anonymous reading/selection contracts; no reviewed answers or source IDs."""
from copy import deepcopy
import unittest

from src.agent.financial_candidate_matching import project_candidate_fact
from src.agent.financial_graph_calculation import (
    _rank_applicable_owner_candidates, _semantic_candidate_cohorts,
)
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog, semantic_candidate_catalog_fingerprint,
)
from src.agent.financial_runtime_normalization import _normalise_operand_value


def owner(label="service portfolio", *, kind="narrative", year="2042"):
    return {
        "obligation_id": "overview", "kind": kind, "label": label,
        "required": True, "display_unit": "",
        "scope": {"company": "Example issuer", "period": year},
        "semantic_target": {"metric_surfaces": [label], "local_subjects": [], "concept_keys": []},
        "evidence_requirements": [], "depends_on": [], "coupling_key": "",
    }


def candidate(cid, *, table="", section="Chapter > Detail", text="Unrelated description.",
              heading="", row="row-1", cell="cell-1", year="2042", document="report-A"):
    result = {
        "candidate_id": cid, "kind": "numeric" if table else "narrative",
        "candidate_kind": "structured_row" if table else "chunk",
        "source_document_id": document, "source_candidate_id": f"source-{cid}",
        "evidence_id": f"evidence-{cid}",
        "source_anchor": f"[Example issuer | {year} | {section}]",
        "source_text": text, "source_bundle_text": text,
        "context_fingerprint": f"context-{cid}",
        "company": "Example issuer", "document_company": "Example issuer", "period": year,
        "row_label": "Item alpha" if table else "",
        "row_headers": ["Item alpha"] if table else [],
        "column_headers": ["Count"] if table else [],
        "normalized_unit": "UNKNOWN", "local_entity_surfaces": [],
    }
    if table:
        value, dimension = _normalise_operand_value("1", "COUNT")
        result.update(physical_table_id=table, physical_row_id=row, physical_cell_id=cell,
                      raw_value="1", raw_unit="COUNT", normalized_value=value, normalized_unit=dimension)
    if heading:
        result["source_contexts"] = [{"relation": "ancestor_heading", "source_text": heading}]
    return result


class NarrativeCandidateSelectionTests(unittest.TestCase):
    def select(self, catalog, target=None, *, limit=6, parent=None, excluded=()):
        before = deepcopy(catalog)
        result = _rank_applicable_owner_candidates(catalog, owner=target or owner(),
            candidate_kind="evidence", limit=limit, parent_owner=parent,
            excluded_candidate_ids=excluded)
        self.assertEqual(catalog, before)
        return result

    def test_local_row_reading_is_available_only_to_narrative_matching(self):
        row = candidate("row", table="table", text="Distribution routes > Partners | Retail outlets | 1")
        self.assertEqual(project_candidate_fact(row).text_metric_surfaces, ())
        _, _, narrative, _ = self.select([row], owner("distribution routes"))
        _, _, numeric, _ = self.select([row], owner("distribution routes", kind="direct_value"))
        self.assertEqual(narrative["row"]["state"], "compatible")
        self.assertNotEqual(narrative["row"]["reading_metric_state"], "unknown")
        self.assertEqual(numeric["row"]["metric_state"], "unknown")
        self.assertEqual(numeric["row"]["state"], "unknown_only")

    def test_narrative_format_does_not_create_a_cell_precision_bonus(self):
        table = candidate("row", table="table", heading="Service portfolio")
        prose = candidate("text", text="Service portfolio includes alpha and beta.")
        _, _, matches, diagnostics = self.select([table, prose])
        self.assertEqual(matches["row"]["rank_vector"], matches["text"]["rank_vector"])
        self.assertEqual(matches["row"]["reading_metric_state"], "unknown")
        self.assertNotEqual(matches["row"]["context_metric_state"], "unknown")
        self.assertEqual(diagnostics["selection_unit"], "narrative_source_hierarchy")

    def test_detail_volume_cannot_starve_a_peer_section_with_reading_evidence(self):
        for year, suffix in (("2038", "a"), ("2046", "z")):
            with self.subTest(year=year, suffix=suffix):
                details = [candidate(f"detail-{i}-{suffix}", table=f"table-{i}",
                    section="Chapter > A detail", heading="Primary service portfolio", year=year)
                    for i in range(80)]
                overview = candidate(f"overview-{suffix}", section="Chapter > Z overview",
                    text="The service portfolio combines alpha, beta and gamma.", year=year)
                catalog = [*details, overview]
                target = owner("primary service portfolio", year=year)
                selected, _, _, _ = self.select(catalog, target)
                self.assertIn(overview["candidate_id"], {row["candidate_id"] for row in selected})
                self.assertEqual(len(selected), 6)
                reverse, _, _, _ = self.select(list(reversed(catalog)), target)
                self.assertEqual(selected, reverse)

    def test_parent_sections_share_capacity_before_one_parents_many_descendants(self):
        many = [candidate(f"a-{i}", table=f"table-{i}",
            section=f"A chapter > Section {i}", heading="Service portfolio") for i in range(20)]
        peer = candidate("z-peer", table="z-table", section="Z chapter > Section",
                         text="Service portfolio | Partners | 1")
        selected, _, _, _ = self.select([*many, peer], limit=2)
        self.assertIn("z-peer", {row["candidate_id"] for row in selected})

    def test_reading_does_not_spend_every_slot_on_cells_of_one_physical_row(self):
        cells = [candidate(f"a-{i:02d}", table="table", row="row-A", cell=f"cell-{i}",
                           heading="Service portfolio") for i in range(12)]
        other = candidate("z-other", table="table", row="row-B", heading="Service portfolio")
        selected, _, _, _ = self.select([*cells, other])
        self.assertIn("z-other", {row["candidate_id"] for row in selected})
        self.assertEqual(len(selected), 6)

    def test_table_only_and_prose_only_sources_fill_the_existing_limit(self):
        for table_only in (True, False):
            with self.subTest(table_only=table_only):
                catalog = [candidate(f"source-{i}", table=f"table-{i}" if table_only else "",
                    text="Service portfolio includes alpha.") for i in range(9)]
                selected, _, _, _ = self.select(catalog)
                self.assertEqual(len(selected), 6)

    def test_company_period_subject_and_unit_conflicts_are_not_repaired_by_reading(self):
        target = owner("service portfolio")
        target["semantic_target"]["local_subjects"] = ["Alpha Unit"]
        correct = candidate("correct", table="table", heading="Service portfolio")
        correct.update(row_label="Alpha Unit", row_headers=["Alpha Unit"])
        different = candidate("other", table="table", row="other", heading="Service portfolio")
        different.update(row_label="Beta Unit", row_headers=["Beta Unit"])
        wrong_company = {**correct, "candidate_id": "wrong-company", "company": "Other issuer"}
        wrong_period = {**correct, "candidate_id": "wrong-period", "period": "2039"}
        selected, _, matches, _ = self.select([correct, different, wrong_company, wrong_period], target)
        self.assertEqual([row["candidate_id"] for row in selected], ["correct"])
        for cid in ("other", "wrong-company", "wrong-period"):
            self.assertEqual(matches[cid]["state"], "explicit_conflict")
        target["display_unit"] = "USD"
        selected, _, matches, _ = self.select([correct], target)
        self.assertEqual(selected, [])
        self.assertEqual(matches["correct"]["unit_state"], "conflict")

    def test_source_keys_are_not_used_in_place_of_a_present_local_reading_match(self):
        distractions = [candidate(f"a-{i}", table=f"a-{i}") for i in range(20)]
        row = candidate("z-row", table="z-table", text="Distribution routes > Partners | 1")
        selected, _, matches, _ = self.select([*distractions, row], owner("distribution routes"))
        self.assertEqual(selected[0]["candidate_id"], "z-row")
        self.assertEqual(matches["z-row"]["state"], "compatible")

    def test_requirements_inherit_narrative_reading_from_their_parent(self):
        parent = owner("distribution routes")
        requirement = {"requirement_id": "routes", "label": "distribution routes",
                       "scope": parent["scope"], "semantic_target": parent["semantic_target"]}
        parent["evidence_requirements"] = [requirement]
        row = candidate("row", table="table", text="Distribution routes > Partners | 1")
        plan = _semantic_candidate_cohorts([row], [parent])
        self.assertEqual(plan["candidate_ids_by_owner"]["routes"], ["row"])
        self.assertEqual(plan["candidate_match_by_id"]["row"]["routes"]["state"], "compatible")

    def test_actual_catalog_continuations_participate_without_changing_source_or_ids(self):
        body = "Opening statement. " * 90 + "Distribution routes include direct delivery."
        source = {"candidate_id": "body", "candidate_kind": "chunk", "source_anchor": "[sample]",
                  "text": body, "source_text_exact": body, "metadata": {"is_table": False}}
        catalog = build_semantic_candidate_catalog([source])
        before = deepcopy(catalog)
        fingerprint = semantic_candidate_catalog_fingerprint(catalog)
        narrative = next(row for row in catalog if row["kind"] == "narrative")
        self.assertNotIn("Distribution routes", narrative["source_bundle_text"])
        target = owner("distribution routes")
        target["scope"] = {}
        _, _, matches, _ = self.select(catalog, target)
        self.assertEqual(matches[narrative["candidate_id"]]["state"], "compatible")
        self.assertEqual(catalog, before)
        self.assertEqual(semantic_candidate_catalog_fingerprint(catalog), fingerprint)

    def test_document_identity_keeps_same_named_sections_diverse(self):
        sources = [candidate(f"a-{i}", table=f"table-{i}", document="report-A",
                             heading="Service portfolio") for i in range(12)]
        other = candidate("z-other", table="z-table", document="report-B", heading="Service portfolio")
        selected, _, _, _ = self.select([*sources, other], limit=2)
        self.assertEqual({row["source_document_id"] for row in selected}, {"report-A", "report-B"})

    def test_exclusion_and_unknown_state_remain_explicit(self):
        catalog = [candidate("a", table="table-a", text="Service portfolio | Partners | 1"),
                   candidate("b", table="table-b")]
        selected, _, matches, _ = self.select(catalog, excluded=["a"])
        self.assertEqual([row["candidate_id"] for row in selected], ["b"])
        self.assertEqual(matches["b"]["state"], "unknown_only")


if __name__ == "__main__":
    unittest.main()
