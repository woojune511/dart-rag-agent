"""Declared document scope guides exposure without becoming subject authority."""
from copy import deepcopy
import json
import unittest

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
from src.agent.financial_reconciliation_candidates import semantic_candidate_catalog_fingerprint
from tests.test_numeric_subject_exposure import cell, owner


def request(basis="combined measure ledger"):
    row = owner()
    row["semantic_target"]["local_subjects"] = []
    row["scope"]["basis"] = basis
    row["retrieval_hints"] = [f"{basis} service amount"]
    return row


def context(text, relation="ancestor_heading", **extra):
    return {"source_text": text, "relation": relation, "context_id": "ctx:" + text,
            "source_locator": "/document/title", "source_span": [0, len(text)], **extra}


def candidate(key, *, title=None, **kwargs):
    row = cell(key, **kwargs)
    row["source_contexts"] = [] if title is None else [context(title)]
    return row


def exposure(catalog, obligation):
    projection = _semantic_candidate_cohorts(catalog, [obligation])
    cohort = next(row for row in projection["cohorts"] if row["owner_type"] == "obligation")
    return cohort["exposure_candidate_ids"], projection


class NumericScopeExposureTests(unittest.TestCase):
    def test_basis_fragments_do_not_become_inferred_subjects(self):
        for scope_basis, observed in (("combined measure ledger", "measure ledger"),
                                       ("통합 관측명세서", "관측명세서")):
            with self.subTest(basis=scope_basis):
                wanted = candidate("wanted")
                distractor = candidate("distractor", row=observed)
                distractor["local_entity_surfaces"] = [observed]
                obligation = request(scope_basis)
                original = deepcopy((wanted, distractor, obligation))
                _, plan = exposure([distractor, wanted], obligation)
                for matches in plan["candidate_match_by_id"].values():
                    self.assertEqual(matches["amount"]["target_local_subjects"], [])
                self.assertEqual((wanted, distractor, obligation), original)

    def test_explicit_subject_and_longer_inferred_name_are_preserved(self):
        obligation = request("measure ledger")
        obligation["semantic_target"]["local_subjects"] = ["measure ledger"]
        source = candidate("explicit", row="measure ledger")
        source["local_entity_surfaces"] = ["measure ledger"]
        _, plan = exposure([source], obligation)
        self.assertEqual(plan["candidate_match_by_id"]["explicit"]["amount"]["target_local_subjects"], ["measure ledger"])
        obligation = request("Ledger")
        obligation["label"] = "Ledger Labs service amount"
        source = candidate("inferred", row="Ledger Labs")
        source["local_entity_surfaces"] = ["Ledger Labs"]
        _, plan = exposure([source], obligation)
        self.assertEqual(plan["candidate_match_by_id"]["inferred"]["amount"]["target_local_subjects"], ["Ledger Labs"])

    def test_tied_metric_bundles_expose_requested_basis_with_all_cells(self):
        for title in ("Combined comparative measure ledger", "COMBINED  measure ledger"):
            with self.subTest(title=title):
                wanted = candidate("z-wanted", row="service amount (*1)", table="z", title=title)
                neighbor = {**deepcopy(wanted), "candidate_id": "z-neighbor", "physical_cell_id": "second"}
                catalog = [candidate("a-summary"), candidate("b-summary"), wanted, neighbor]
                obligation = request()
                original = deepcopy((catalog, obligation))
                fingerprint = semantic_candidate_catalog_fingerprint(catalog)
                plans = []
                for rows in (catalog, list(reversed(catalog))):
                    selected, plan = exposure(rows, obligation)
                    self.assertEqual(set(selected[:2]), {"z-wanted", "z-neighbor"})
                    self.assertEqual(len(selected), 3)
                    cohort = next(row for row in plan["cohorts"] if row["owner_type"] == "obligation")
                    self.assertEqual(len(cohort["ranking_diagnostics"]["selected_source_bundle_ids"]), 2)
                    self.assertEqual(plan["candidate_match_by_id"]["z-wanted"]["amount"]["numeric_basis_hint"], "context_terms")
                    plans.append(plan)
                self.assertEqual(plans[0], plans[1])
                self.assertEqual((catalog, obligation), original)
                self.assertEqual(semantic_candidate_catalog_fingerprint(catalog), fingerprint)

    def test_each_requirement_uses_its_effective_basis_without_parent_hint_leak(self):
        parent = request()
        parent.update(kind="derived_value", display_unit="%", evidence_requirements=[
            {"requirement_id": "first", "label": "alpha amount", "scope": {}, "required": True,
             "display_unit": "USD", "retrieval_hints": ["combined measure ledger alpha amount"],
             "semantic_target": {"local_subjects": [], "concept_keys": [], "metric_surfaces": ["alpha amount"]}},
            {"requirement_id": "second", "label": "beta amount", "scope": {"basis": "regional register"}, "required": True,
             "display_unit": "USD", "retrieval_hints": ["regional register beta amount"],
             "semantic_target": {"local_subjects": [], "concept_keys": [], "metric_surfaces": ["beta amount"]}},
        ])
        catalog = [candidate(f"{key}-{metric}", row=f"{metric} amount", title=title)
                   for key, title in (("a", "overview"), ("b", "overview"),
                                      ("z-first", "combined measure ledger"), ("z-second", "regional register"))
                   for metric in ("alpha", "beta")]
        decoy = candidate("decoy", row="measure ledger")
        decoy["local_entity_surfaces"] = ["measure ledger", "regional register"]
        plan = _semantic_candidate_cohorts([*catalog, decoy], [parent])
        for req, cid in (("first", "z-first-alpha"), ("second", "z-second-beta")):
            cohort = next(row for row in plan["cohorts"] if row["owner_id"] == req)
            self.assertEqual(cohort["exposure_candidate_ids"][0], cid)
            self.assertEqual(plan["candidate_match_by_id"][cid][req]["target_local_subjects"], [])
        self.assertEqual(plan["candidate_match_by_id"]["z-first-beta"]["second"]["numeric_basis_hint"], "unknown")

    def test_basis_hint_never_beats_better_metric_or_known_subject(self):
        exact = candidate("a-exact")
        contained = candidate("z-hint", row="other service amount balance", title="combined measure ledger")
        selected, _ = exposure([contained, exact], request())
        self.assertEqual(selected[0], "a-exact")
        obligation = request()
        obligation["semantic_target"]["local_subjects"] = ["Orion"]
        exact = candidate("a-subject", columns=["Orion"])
        hinted = candidate("z-hint", title="combined measure ledger")
        selected, _ = exposure([hinted, exact], obligation)
        self.assertEqual(selected[0], "a-subject")

    def test_only_one_attached_context_partition_can_supply_the_hint(self):
        variants = [
            {"source_text": "combined measure ledger"},
            {"source_bundle_text": "combined measure ledger"},
            {"local_heading": "combined measure ledger", "basis": "combined measure ledger"},
            {"source_anchor": "[combined measure ledger]", "statement_type": "combined measure ledger"},
            {"source_contexts": [context("combined measure ledger", "following_block")]},
            {"source_contexts": [context("combined measure"), context("ledger")]},
            {"source_contexts": [context("combined measure | ledger", source_segments=[
                {"text_span": [0, 16]}, {"text_span": [19, 25]}])]},
        ]
        for changes in variants:
            with self.subTest(changes=changes):
                source = {**candidate("source"), **changes}
                _, plan = exposure([source], request())
                self.assertEqual(plan["candidate_match_by_id"]["source"]["amount"]["numeric_basis_hint"], "unknown")
        for relation in ("ancestor_heading", "intermediate_heading", "caption", "preceding_block"):
            with self.subTest(relation=relation):
                source = candidate("source")
                source["source_contexts"] = [context("combined measure ledger", relation)]
                _, plan = exposure([source], request())
                self.assertEqual(plan["candidate_match_by_id"]["source"]["amount"]["numeric_basis_hint"], "context_terms")

    def test_repetition_does_not_change_rank_or_expose_diagnostic_to_compiler(self):
        ranks = []
        for count in (1, 20):
            source = candidate("source", title="combined measure ledger " * count)
            obligation = request("combined measure ledger " * count)
            _, plan = exposure([source], obligation)
            ranks.append(plan["candidate_match_by_id"]["source"]["amount"]["rank_vector"])
            payload = FinancialAgent._semantic_program_prompt_payload([source], plan)
            self.assertNotIn("numeric_basis_hint", json.dumps(payload))
        self.assertEqual(ranks[0], ranks[1])

    def test_hint_cannot_override_source_conditions_or_bundle_retry_exclusion(self):
        obligation = request()
        obligation["source_sections"] = ["Allowed"]
        good = candidate("good", title="combined measure ledger", table="shared")
        sibling = {**deepcopy(good), "candidate_id": "sibling", "physical_cell_id": "sibling"}
        sources = [good, sibling,
                   candidate("foreign", company="Other", title="combined measure ledger"),
                   candidate("period", period="2041", title="combined measure ledger"),
                   candidate("unit", unit="PERCENT", title="combined measure ledger"),
                   candidate("section", title="combined measure ledger")]
        for row in sources:
            row["section_path"] = "Other" if row["candidate_id"] == "section" else "Allowed"
        _, plan = exposure(sources, obligation)
        self.assertEqual(set(plan["candidate_ids_by_owner"]["amount"]), {"good", "sibling"})
        excluded = _semantic_candidate_cohorts(sources, [obligation], excluded_candidate_ids_by_owner={"amount": ["good"]})
        self.assertEqual(excluded["visible_candidate_ids"], [])


if __name__ == "__main__":
    unittest.main()
