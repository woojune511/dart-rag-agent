from __future__ import annotations

import unittest

from src.ops.export_semantic_tiebreak_cases import (
    LABELING_TEMPLATE_SCHEMA,
    build_labeling_template,
    render_summary,
)


def _obligation() -> dict:
    return {
        "obligation_id": "ob_value",
        "kind": "direct_value",
        "label": "target quantity",
        "display_unit": "items",
        "scope": {
            "company": "sample company",
            "period": "2024",
            "consolidation_scope": "unknown",
            "segment": "",
            "basis": "",
        },
        "semantic_target": {
            "local_subjects": ["target entity"],
            "concept_keys": [],
            "metric_surfaces": ["quantity"],
        },
        "evidence_requirements": [],
    }


def _candidate(candidate_id: str, *, period: str, value: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "kind": "numeric",
        "candidate_kind": "structured_value",
        "source_candidate_id": f"source-{candidate_id}",
        "evidence_id": f"evidence-{candidate_id}",
        "physical_table_id": f"table-{candidate_id}",
        "physical_row_id": f"row-{candidate_id}",
        "physical_cell_id": f"cell-{candidate_id}",
        "row_label": "target entity",
        "row_headers": ["target entity"],
        "local_entity_surfaces": ["target entity"],
        "column_headers": ["quantity"],
        "raw_value": value,
        "raw_unit": "items",
        "normalized_value": float(value),
        "normalized_unit": "COUNT",
        "company": "sample company",
        "document_company": "sample company",
        "period": period,
        "year": 2024 if period else None,
        "value_year": 2024 if period else None,
        "consolidation_scope": "unknown",
        "segment": "",
        "basis": "",
        "statement_type": "operating_statement",
        "source_text": f"target entity | quantity {value} items",
    }


class ExportSemanticTieBreakCasesTests(unittest.TestCase):
    def test_exports_only_the_verified_strongest_factor_tier(self) -> None:
        obligation = _obligation()
        catalog = [
            _candidate("candidate-b", period="2024", value="20"),
            _candidate("candidate-lower", period="", value="30"),
            _candidate("candidate-a", period="2024", value="10"),
        ]
        cohort = {
            "cohort_id": "ob_value:output",
            "owner_id": "ob_value",
            "parent_obligation_id": "ob_value",
            "owner_type": "obligation",
            "candidate_kind": "numeric",
            "candidate_ids": ["candidate-a"],
            "limit": 4,
        }
        saved = {
            "question_id": "question-1",
            "question": "Return the target quantity.",
            "source_file": "saved/results.json",
            "store": {"persist_directory": "unused"},
            "plan": {
                "answer_obligations": [obligation],
                "candidate_cohorts": [cohort],
            },
        }

        template = build_labeling_template(
            [saved],
            catalog_replay=lambda _plan, _store: (
                catalog,
                {"status": "verified", "reason": ""},
            ),
        )

        self.assertEqual(template["schema"], LABELING_TEMPLATE_SCHEMA)
        self.assertEqual(template["pair_schema"], "semantic_tie_break_pair_v5")
        self.assertEqual(template["summary"]["case_count"], 1)
        self.assertEqual(template["summary"]["candidate_pair_count"], 2)
        case = template["cases"][0]
        self.assertEqual(case["label_status"], "unlabeled")
        self.assertEqual(case["expected_action"], "")
        self.assertEqual(
            case["baseline_candidate_ids"],
            ["candidate-a", "candidate-b"],
        )
        self.assertNotIn(
            "candidate-lower",
            {
                candidate["candidate_id"]
                for candidate in case["candidates"]
            },
        )
        self.assertTrue(
            all(
                candidate["evidence_locator"] == "unique_value_surface"
                for candidate in case["candidates"]
            )
        )
        self.assertTrue(
            all(
                candidate["fact_role"]["schema"] == "candidate_fact_role_v1"
                for candidate in case["candidates"]
            )
        )
        self.assertTrue(
            all(
                candidate["candidate"]["statement_type"]
                == "operating_statement"
                for candidate in case["candidates"]
            )
        )
        self.assertIn("Cases: 1", render_summary(template))
        relocated = {**saved, "source_file": "other/location/results.json"}
        relocated_template = build_labeling_template(
            [relocated],
            catalog_replay=lambda _plan, _store: (
                catalog,
                {"status": "verified", "reason": ""},
            ),
        )
        self.assertEqual(
            template["template_fingerprint"],
            relocated_template["template_fingerprint"],
        )

    def test_unverified_catalog_is_reported_without_exporting_cases(self) -> None:
        template = build_labeling_template(
            [
                {
                    "question_id": "question-1",
                    "question": "Return the target quantity.",
                    "source_file": "saved/results.json",
                    "plan": {},
                    "store": {},
                }
            ],
            catalog_replay=lambda _plan, _store: (
                [],
                {"status": "mismatch", "reason": "saved_fingerprint_mismatch"},
            ),
        )

        self.assertEqual(template["cases"], [])
        self.assertEqual(template["summary"]["skipped_plan_count"], 1)
        self.assertEqual(
            template["skipped"][0]["reason"],
            "saved_fingerprint_mismatch",
        )

    def test_excludes_source_defined_group_from_atomic_label_cases(self) -> None:
        obligation = {
            **_obligation(),
            "kind": "narrative",
            "evidence_mode": "source_defined_group",
        }
        cohort = {
            "cohort_id": "ob_value:output",
            "owner_id": "ob_value",
            "parent_obligation_id": "ob_value",
            "owner_type": "obligation",
            "candidate_kind": "evidence",
            "candidate_ids": ["candidate-a", "candidate-b"],
            "limit": 6,
        }
        saved = {
            "question_id": "question-group",
            "question": "Summarize the evidence group.",
            "source_file": "saved/results.json",
            "store": {"persist_directory": "unused"},
            "plan": {
                "answer_obligations": [obligation],
                "candidate_cohorts": [cohort],
            },
        }

        template = build_labeling_template(
            [saved],
            catalog_replay=lambda _plan, _store: (
                [
                    _candidate("candidate-a", period="2024", value="10"),
                    _candidate("candidate-b", period="2024", value="20"),
                ],
                {"status": "verified", "reason": ""},
            ),
        )

        self.assertEqual(template["cases"], [])
        self.assertEqual(template["summary"]["excluded_cohort_count"], 1)
        self.assertEqual(
            template["summary"]["excluded_cohort_reason_counts"],
            {"source_defined_group": 1},
        )
        self.assertEqual(
            template["excluded_cohorts"][0]["reason"],
            "source_defined_group",
        )


if __name__ == "__main__":
    unittest.main()
