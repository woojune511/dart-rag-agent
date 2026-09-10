"""Period labels are source context, not inferred value-subject authority."""

from copy import deepcopy
import unittest

from src.agent.financial_candidate_matching import build_candidate_matches
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog, semantic_candidate_catalog_fingerprint,
)


def source(name, row_headers, column, *, year=2028, table=None):
    return {
        "candidate_id": name,
        "candidate_kind": "structured_value",
        "source_anchor": "[anonymous filing]",
        "text": " | ".join([*row_headers, column, "125 USD"]),
        "metadata": {
            "company": "Filing Entity", "year": year,
            "row_label": row_headers[-1], "row_headers": row_headers,
            "table_source_id": table or name, "physical_table_id": table or name,
            "physical_row_id": name,
            "structured_cells": [{
                "cell_id": name + ":value", "column_headers": [column],
                "value_text": "125", "unit_hint": "USD",
            }],
        },
    }


def owner(label, *, year=2028, subjects=()):
    return {
        "obligation_id": "measure", "kind": "direct_value", "label": label,
        "scope": {"company": "Filing Entity", "period": str(year)},
        "display_unit": "USD", "retrieval_hints": [],
        "semantic_target": {
            "local_subjects": list(subjects), "concept_keys": [],
            "metric_surfaces": ["reported measure"],
        },
    }


class SemanticSubjectPeriodBoundaryTests(unittest.TestCase):
    def test_period_only_surfaces_never_become_inferred_subjects(self):
        for period in (
            "1998년", "2028년", "2032년 말", "2032년 12월말",
            "2032년 12월 31일", "2032.12.31", "2032-12-31", "FY 2032",
            "24년", "'31년", "’27년 말",
            "제 18 기", "제72기", "당기말", "전전기말", "current period", "prior",
        ):
            with self.subTest(period=period):
                catalog = build_semantic_candidate_catalog([
                    source("measure", ["reported measure"], "제 18 기"),
                    source("other", [period, "unrelated amount"], period),
                ])
                before = deepcopy(catalog)
                for location in ("label", "retrieval_hints"):
                    obligation = owner("reported measure")
                    if location == "label":
                        obligation["label"] = period + " reported measure"
                    else:
                        obligation["retrieval_hints"] = [period]
                    matches = build_candidate_matches(catalog, owner=obligation,
                        base_applicability_by_id={row["candidate_id"]: {"state": "compatible"} for row in catalog})
                    self.assertTrue(matches)
                    for match in matches.values():
                        self.assertEqual(match.target_local_subjects, ())
                        self.assertEqual(match.subject_state, "unspecified")
                self.assertEqual(catalog, before)

    def test_fiscal_metric_reaches_bounded_cohort_despite_calendar_distractors(self):
        for year in (2021, 2032):
            with self.subTest(year=year):
                catalog = build_semantic_candidate_catalog([
                    source("exact", ["reported measure"], "제 18 기", year=year),
                    source("other-a", [f"{year}년", "unrelated amount"], f"{year}년", year=year),
                    source("other-b", [f"{year}년", "another amount"], f"{year}년", year=year),
                ])
                exact = next(row for row in catalog if row["row_label"] == "reported measure")
                self.assertEqual((exact["normalized_value"], exact["normalized_unit"]), (125, "USD"))
                self.assertEqual(exact["value_year"], year)
                obligation = owner(f"{year}년 reported measure", year=year)
                before, fingerprint = deepcopy(catalog), semantic_candidate_catalog_fingerprint(catalog)
                plans = [_semantic_candidate_cohorts(rows, [obligation])
                         for rows in (catalog, list(reversed(catalog)))]
                for plan in plans:
                    self.assertEqual(plan["candidate_ids_by_owner"]["measure"][0], exact["candidate_id"])
                    match = plan["candidate_match_by_id"][exact["candidate_id"]]["measure"]
                    self.assertEqual(match["target_local_subjects"], [])
                    self.assertEqual(match["state"], "compatible")
                self.assertEqual(plans[0]["candidate_ids_by_owner"], plans[1]["candidate_ids_by_owner"])
                self.assertEqual(catalog, before)
                self.assertEqual(semantic_candidate_catalog_fingerprint(catalog), fingerprint)

    def test_required_input_uses_the_same_subject_boundary(self):
        catalog = build_semantic_candidate_catalog([
            source("exact", ["reported measure"], "제 18 기"),
            source("other", ["2028년", "unrelated amount"], "2028년"),
        ])
        obligation = owner("reported measure")
        obligation.update(kind="derived_value", evidence_requirements=[{
            "requirement_id": "input", "label": "2028년 reported measure",
            "scope": deepcopy(obligation["scope"]),
            "semantic_target": deepcopy(obligation["semantic_target"]),
        }])
        plan = _semantic_candidate_cohorts(catalog, [obligation])
        for owners in plan["candidate_match_by_id"].values():
            self.assertEqual(owners["input"]["target_local_subjects"], [])

    def test_temporal_substrings_do_not_erase_inferred_entity_names(self):
        for name in ("Orbit 2032", "Orbit 32", "FY Labs", "Current Systems", "전기공업", "제7기술"):
            with self.subTest(name=name):
                catalog = build_semantic_candidate_catalog([
                    source("entity", [name], "reported measure"),
                ])
                matches = build_candidate_matches(catalog, owner=owner(name + " reported measure"),
                    base_applicability_by_id={row["candidate_id"]: {"state": "compatible"} for row in catalog})
                self.assertTrue(matches)
                self.assertTrue(all(match.target_local_subjects == (name,) for match in matches.values()))

    def test_explicit_subject_is_not_reclassified_even_if_named_like_a_period(self):
        for name in ("Current", "2028년", "Orbit 2032"):
            with self.subTest(name=name):
                catalog = build_semantic_candidate_catalog([
                    source("exact", [name], "2028", table="same-table"),
                    source("wrong", ["Other Entity"], "2028", table="same-table"),
                ])
                obligation = owner(name + " reported measure", subjects=[name])
                plan = _semantic_candidate_cohorts(catalog, [obligation])
                for candidate in catalog:
                    match = plan["candidate_match_by_id"][candidate["candidate_id"]]["measure"]
                    self.assertEqual(match["target_local_subjects"], [name])
                    if candidate["row_label"] == name:
                        self.assertEqual(match["subject_state"], "match")
                        self.assertIn(candidate["candidate_id"], plan["candidate_ids_by_owner"]["measure"])
                    else:
                        self.assertEqual(match["state"], "explicit_conflict")
                        self.assertNotIn(candidate["candidate_id"], plan["candidate_ids_by_owner"]["measure"])


if __name__ == "__main__":
    unittest.main()
