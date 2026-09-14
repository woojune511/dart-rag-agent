from copy import deepcopy
import unittest

from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
from tests.semantic_program_test_support import _candidate, _obligation, _scope


def reading(identifier, topic, *, year=2042, company="Example", section="Overview"):
    return {"candidate_id": identifier, "kind": "narrative", "candidate_kind": "chunk",
            "company": company, "document_company": company, "year": year,
            "period": str(year), "consolidation_scope": "consolidated",
            "source_document_id": f"{company}-{year}", "section_path": section,
            "source_candidate_id": identifier, "source_anchor": f"[{company} | {year} | {section}]",
            "source_text": f"The unit describes {topic} in this passage.", "normalized_unit": "UNKNOWN"}


class CandidateAuthorityProjectionTests(unittest.TestCase):
    def narrative(self):
        scope = _scope(company="Example", period="2042", consolidation_scope="consolidated")
        return _obligation("answer", "narrative", "explain", scope=scope,
            evidence_requirements=[
                {"requirement_id": f"answer:{name}", "required": True, "label": name,
                 "scope": scope, "semantic_target": {"metric_surfaces": [name]}}
                for name in ("formation", "outcome")])

    def test_same_source_scope_shares_visible_union_not_rank_quota(self):
        owner = self.narrative()
        catalog = [reading(f"{topic}-{i}", topic) for topic in ("formation", "outcome") for i in range(6)]
        before = deepcopy((catalog, owner))
        result = _semantic_candidate_cohorts(catalog, [owner])
        expected = set(result["visible_candidate_ids"])
        self.assertEqual(len(expected), 12)
        for name in ("formation", "outcome"):
            self.assertEqual(set(result["candidate_ids_by_owner"][f"answer:{name}"]), expected)
        for cohort in result["cohorts"]:
            self.assertLessEqual(len(cohort["exposure_candidate_ids"]), 6)
        reversed_result = _semantic_candidate_cohorts(list(reversed(catalog)), [owner])
        self.assertEqual(result["candidate_ids_by_owner"], reversed_result["candidate_ids_by_owner"])
        self.assertEqual((catalog, owner), before)

    def test_source_sections_and_filings_do_not_share_authority(self):
        owners = [self.narrative(), _obligation("other", "narrative", "other",
                  scope=_scope(company="Foreign", period="2042", consolidation_scope="consolidated"))]
        owners[0]["evidence_requirements"][0]["source_sections"] = ["Overview"]
        owners[0]["evidence_requirements"][1]["source_sections"] = ["Notes"]
        catalog = [reading("overview", "formation"), reading("notes", "outcome", section="Notes"),
                   reading("foreign", "formation", company="Foreign")]
        result = _semantic_candidate_cohorts(catalog, owners)
        self.assertEqual(set(result["candidate_ids_by_owner"]["answer:formation"]), {"overview"})
        self.assertEqual(set(result["candidate_ids_by_owner"]["answer:outcome"]), {"notes"})

    def test_numeric_periods_and_retry_exclusion_remain_local(self):
        owner = _obligation("change", "derived_value", "change", evidence_requirements=[
            {"requirement_id": f"change:{year}", "required": True, "label": "quantity",
             "scope": _scope(period=str(year))} for year in (2041, 2042)])
        catalog = [_candidate(str(year), year - 2000, period=str(year)) for year in (2041, 2042)]
        result = _semantic_candidate_cohorts(catalog, [owner])
        self.assertEqual(set(result["candidate_ids_by_owner"]["change:2041"]), {"2041"})
        self.assertEqual(set(result["candidate_ids_by_owner"]["change:2042"]), {"2042"})
        excluded = _semantic_candidate_cohorts(catalog, [owner],
            excluded_candidate_ids_by_owner={"change:2041": ["2041"]})
        self.assertNotIn("2041", excluded["candidate_ids_by_owner"]["change:2041"])


if __name__ == "__main__":
    unittest.main()
