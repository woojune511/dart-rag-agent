"""Exposure relevance is separate from numeric source interpretation/authority."""
from copy import deepcopy
import json
import unittest

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_candidate_matching import structured_subject_evidence
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
from src.agent.financial_reconciliation_candidates import semantic_candidate_catalog_fingerprint


def owner(subject="Orion division", *, period="2042"):
    return {"obligation_id": "amount", "kind": "direct_value", "label": "service amount",
        "required": True, "display_unit": "USD", "retrieval_hints": [], "concept_hints": [],
        "scope": {"company": "Example", "period": period, "consolidation_scope": "consolidated"},
        "semantic_target": {"local_subjects": [subject], "concept_keys": [], "metric_surfaces": ["service amount"]},
        "evidence_requirements": [], "depends_on": []}


def cell(identifier, *, row="service amount", columns=(), period="2042", company="Example", unit="USD", table=None):
    table = table or identifier
    return {"candidate_id": identifier, "source_candidate_id": identifier, "evidence_id": identifier,
        "kind": "numeric", "candidate_kind": "structured_value", "source_anchor": "[example]",
        "source_document_id": "receipt:example", "company": company, "document_company": company,
        "year": 2042, "period": period, "consolidation_scope": "consolidated",
        "table_source_id": table, "physical_table_id": table, "physical_row_id": row,
        "source_row_id": row, "physical_cell_id": identifier, "row_label": row, "row_headers": [row],
        "column_headers": list(columns), "raw_value": "120", "raw_unit": unit,
        "normalized_value": 120.0, "normalized_unit": unit, "source_text": row,
        "context_fingerprint": table}


class NumericSubjectExposureTests(unittest.TestCase):
    def test_descriptive_subject_exposes_own_row_or_column_before_total_rows(self):
        for layout in ("row", "column"):
            with self.subTest(layout=layout):
                target = cell("target", table="z-target", row="Orion" if layout == "row" else "service amount",
                              columns=["value"] if layout == "row" else ["Orion"])
                catalog = [cell("total-a"), cell("total-b"), target]
                request = owner()
                original = deepcopy((catalog, request))
                fingerprint = semantic_candidate_catalog_fingerprint(catalog)
                for ordered in (catalog, list(reversed(catalog))):
                    plan = _semantic_candidate_cohorts(ordered, [request])
                    cohort = next(c for c in plan["cohorts"] if c["cohort_id"] == "amount:output")
                    self.assertEqual(cohort["exposure_candidate_ids"][0], "target")
                    self.assertLessEqual(len(cohort["ranking_diagnostics"]["selected_source_bundle_ids"]), 2)
                    match = plan["candidate_match_by_id"]["target"]["amount"]
                    self.assertEqual(match["subject_state"], "unknown")
                    self.assertEqual(match["state"], "unknown_only")
                    self.assertEqual(match["target_local_subjects"], ["Orion division"])
                self.assertEqual(structured_subject_evidence(target, ["Orion division"])["state"], "unknown")
                self.assertEqual((catalog, request), original)
                self.assertEqual(semantic_candidate_catalog_fingerprint(catalog), fingerprint)

    def test_period_pairs_stay_in_their_own_requirements_and_bundles(self):
        request = owner()
        request.update(kind="derived_value", display_unit="%", evidence_requirements=[
            {"requirement_id": f"amount:{year}", "required": True, "label": "service amount",
             "scope": {"period": str(year)}, "semantic_target": deepcopy(request["semantic_target"])}
            for year in (2041, 2042)])
        catalog = [cell(f"{row}-{year}", row=row, table=row, period=str(year))
                   for row in ("service amount", "service amount (*1)", "Orion") for year in (2041, 2042)]
        plan = _semantic_candidate_cohorts(catalog, [request])
        for year in (2041, 2042):
            key = f"amount:{year}"
            self.assertIn(f"Orion-{year}", plan["candidate_ids_by_owner"][key])
            self.assertNotIn(f"Orion-{4083-year}", plan["candidate_ids_by_owner"][key])
        self.assertIn("Orion-2041", plan["visible_candidate_ids"])
        self.assertIn("Orion-2042", plan["visible_candidate_ids"])

    def test_exact_subject_precedes_hint_without_promoting_hint_identity(self):
        catalog = [cell("hint", row="Orion"), cell("exact", row="Orion division"), cell("total")]
        plan = _semantic_candidate_cohorts(catalog, [owner()])
        cohort = next(c for c in plan["cohorts"] if c["cohort_id"] == "amount:output")
        self.assertEqual(cohort["exposure_candidate_ids"], ["exact", "hint"])
        matches = plan["candidate_match_by_id"]
        self.assertEqual(matches["exact"]["amount"]["subject_state"], "match")
        self.assertEqual(matches["hint"]["amount"]["subject_state"], "unknown")
        self.assertEqual(matches["hint"]["amount"]["state"], "unknown_only")

    def test_body_metadata_neighbor_axes_and_repetition_cannot_supply_hint(self):
        target = cell("target", row="Unrelated", table="shared")
        target.update(source_text="Orion " * 100, source_bundle_text="Orion " * 100,
            row_context_text="Orion", local_entity_surfaces=["Orion"], segment="Orion",
            source_contexts=[{"relation": "ancestor_heading", "source_text": "Orion"}])
        neighbor = cell("neighbor", row="Orion", table="shared")
        plan = _semantic_candidate_cohorts([target, neighbor], [owner()])
        self.assertEqual(plan["candidate_match_by_id"]["target"]["amount"]["numeric_subject_hint"], "unknown")
        for copies in (1, 20):
            repeated = {**neighbor, "row_headers": ["Orion"] * copies}
            current = _semantic_candidate_cohorts([repeated], [owner()])
            self.assertEqual(current["candidate_match_by_id"]["neighbor"]["amount"]["rank_vector"],
                             plan["candidate_match_by_id"]["neighbor"]["amount"]["rank_vector"])

    def test_literal_hint_does_not_join_words_trim_qualifiers_or_use_periods(self):
        for subject, row, columns in (
            ("Orion division", "Ori", []),
            ("Orion division", "OrionPrime", []),
            ("Orion division", "Orion (net)", []),
            ("Orion division", "Ori on", []),
            ("Orion division", "Unrelated", ["Ori", "on"]),
            ("AB division", "A/B", []),
            ("2042 division", "2042", []),
            ("Orion - division", "-", []),
        ):
            with self.subTest(subject=subject, row=row, columns=columns):
                plan = _semantic_candidate_cohorts([cell("candidate", row=row, columns=columns)], [owner(subject)])
                match = plan["candidate_match_by_id"]["candidate"]["amount"]
                self.assertEqual(match["numeric_subject_hint"], "unknown")
                self.assertNotEqual(match["subject_state"], "match")

    def test_complete_qualified_axis_is_a_hint_without_target_rewriting(self):
        request = owner("ORION   Holdings division")
        candidate = cell("candidate", row="Orion Holdings (*1)")
        before = deepcopy((request, candidate))
        plan = _semantic_candidate_cohorts([candidate], [request])
        match = plan["candidate_match_by_id"]["candidate"]["amount"]
        self.assertEqual(match["numeric_subject_hint"], "row_axis_literal")
        self.assertEqual(match["subject_state"], "unknown")
        self.assertEqual((request, candidate), before)

    def test_literal_hint_cannot_override_source_conditions_or_retry_exclusion(self):
        request = owner()
        request["source_sections"] = ["Allowed"]
        target = cell("target", row="Orion")
        foreign = cell("foreign", row="Orion", company="Another")
        wrong_period = cell("wrong-period", row="Orion", period="2041")
        wrong_unit = cell("wrong-unit", row="Orion", unit="PERCENT")
        wrong_section = cell("wrong-section", row="Orion")
        catalog = [target, foreign, wrong_period, wrong_unit, wrong_section]
        for candidate in catalog:
            candidate["section_path"] = "Other" if candidate is wrong_section else "Allowed"
        plan = _semantic_candidate_cohorts(catalog, [request])
        self.assertEqual(plan["candidate_ids_by_owner"]["amount"], ["target"])
        excluded = _semantic_candidate_cohorts(catalog, [request],
            excluded_candidate_ids_by_owner={"amount": ["target"]})
        self.assertEqual(excluded["candidate_ids_by_owner"]["amount"], [])

    def test_hint_stays_out_of_compiler_input_and_is_owner_local(self):
        catalog = [cell("orion", row="Orion"), cell("lyra", row="Lyra")]
        first, second = owner(), owner("Lyra division")
        second["obligation_id"] = "second"
        plan = _semantic_candidate_cohorts(catalog, [first, second])
        self.assertEqual(plan["candidate_match_by_id"]["orion"]["amount"]["numeric_subject_hint"], "row_axis_literal")
        self.assertEqual(plan["candidate_match_by_id"]["orion"]["second"]["numeric_subject_hint"], "unknown")
        payload = FinancialAgent._semantic_program_prompt_payload(catalog, plan)
        self.assertNotIn("numeric_subject_hint", json.dumps(payload))


if __name__ == "__main__":
    unittest.main()
