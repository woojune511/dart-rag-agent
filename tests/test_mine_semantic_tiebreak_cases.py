from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.ops.mine_semantic_tiebreak_cases import (
    EVIDENCE_MINING_SCHEMA,
    build_evidence_mining_template,
    load_saved_question_contexts,
    match_candidate_source_ids,
    match_evidence_source_ids,
    render_review_packet,
    render_summary,
)


def _obligation() -> dict:
    return {
        "obligation_id": "ob_value",
        "kind": "direct_value",
        "label": "target quantity",
        "required": True,
        "display_unit": "items",
        "display_format": "",
        "scope": {
            "company": "sample company",
            "period": "2024",
            "consolidation_scope": "unknown",
            "segment": "",
            "basis": "",
        },
        "retrieval_hints": [],
        "concept_hints": [],
        "semantic_target": {
            "local_subjects": ["target entity"],
            "concept_keys": [],
            "metric_surfaces": ["quantity"],
        },
        "evidence_requirements": [],
        "depends_on": [],
        "coupling_key": "",
    }


def _candidate(candidate_id: str, value: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "kind": "numeric",
        "candidate_kind": "structured_value",
        "source_candidate_id": f"source-{candidate_id}",
        "evidence_id": "source-node",
        "source_anchor": "[sample]",
        "source_row_id": f"row-{candidate_id}",
        "table_source_id": "sample-table",
        "physical_table_id": "sample-table",
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
        "period": "2024",
        "period_role": "current",
        "period_label_surfaces": ["current"],
        "period_source": "report_current",
        "year": 2024,
        "value_year": 2024,
        "consolidation_scope": "unknown",
        "segment": "",
        "basis": "",
        "table_context": "sample table",
        "source_text": f"target entity | quantity {value} items",
    }


def _context() -> dict:
    return {
        "question_id": "question-1",
        "question": "Return the target quantity.",
        "source_file": "saved/results.json",
        "store": {"persist_directory": "unused"},
        "plan": {"answer_obligations": [_obligation()]},
        "obligation_fingerprint": "obligation-fingerprint",
    }


def _dataset_row() -> dict:
    return {
        "id": "question-1",
        "question": "Return the target quantity.",
        "verification_status": "verified",
        "answer_type": "numeric",
        "answer_key": "The target quantity is 20 items.",
        "evidence": [
            {
                "section_path": "section",
                "quote": "target entity quantity 20 items",
                "why_it_supports_answer": "Contains the requested value.",
            }
        ],
        "source_reports": [],
    }


class MineSemanticTieBreakCasesTests(unittest.TestCase):
    def test_loads_question_plan_with_owning_store(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result_path = Path(temp_dir) / "results.json"
            result_path.write_text(
                json.dumps(
                    {
                        "company_runs": [
                            {
                                "results": [
                                    {
                                        "store": {
                                            "persist_directory": "saved-store"
                                        },
                                        "full_eval": {
                                            "per_question": [
                                                {
                                                    "id": "question-1",
                                                    "question": "Question?",
                                                    "resolved_calculation_trace": {
                                                        "calculation_plan": {
                                                            "answer_obligations": [
                                                                _obligation()
                                                            ]
                                                        }
                                                    },
                                                }
                                            ]
                                        },
                                    }
                                ]
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            contexts = load_saved_question_contexts([result_path])

        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0]["question_id"], "question-1")
        self.assertEqual(
            contexts[0]["store"]["persist_directory"],
            "saved-store",
        )
        self.assertTrue(contexts[0]["obligation_fingerprint"])

    def test_matches_only_exact_normalized_evidence_quotes(self) -> None:
        nodes = {
            "source-a": {"text": "Target Entity: 20 items."},
            "source-b": {"text": "Other entity: 20 items."},
        }

        source_ids, matched, unmatched = match_evidence_source_ids(
            nodes,
            [
                {"quote": "target entity 20 items"},
                {"quote": "missing evidence"},
            ],
        )

        self.assertEqual(source_ids, ["source-a"])
        self.assertEqual(matched[0]["source_ids"], ["source-a"])
        self.assertEqual(unmatched[0]["quote_index"], 1)

    def test_matches_candidate_to_direct_or_table_source_node(self) -> None:
        source_nodes = [
            {
                "source_id": "source-node",
                "table_source_id": "sample-table",
            },
            {
                "source_id": "prose-node",
                "table_source_id": "",
            },
        ]

        self.assertEqual(
            match_candidate_source_ids(_candidate("candidate-a", "10"), source_nodes),
            ["source-node"],
        )
        self.assertEqual(
            match_candidate_source_ids(
                {
                    "evidence_id": "prose-node",
                    "source_candidate_id": "prose-node",
                },
                source_nodes,
            ),
            ["prose-node"],
        )

    def test_builds_unlabeled_current_id_case_with_source_review(self) -> None:
        catalog = [
            _candidate("candidate-b", "20"),
            _candidate("candidate-a", "10"),
        ]

        template = build_evidence_mining_template(
            [_context()],
            {"question-1": _dataset_row()},
            catalog_loader=lambda _context, _row: (
                catalog,
                {
                    "status": "verified",
                    "source_ids": ["source-node"],
                    "source_node_count": 1,
                    "catalog_candidate_count": 2,
                    "matched_evidence": [
                        {"quote_index": 0, "source_ids": ["source-node"]}
                    ],
                    "unmatched_evidence": [],
                    "source_nodes": [
                        {
                            "source_id": "source-node",
                            "table_source_id": "sample-table",
                            "section_path": "section",
                            "text": "Exact original source node text.",
                            "text_sha256": "source-text-fingerprint",
                        }
                    ],
                    "scope_fingerprint": "scope-fingerprint",
                },
            ),
        )

        self.assertEqual(template["schema"], EVIDENCE_MINING_SCHEMA)
        self.assertEqual(template["pair_schema"], "semantic_tie_break_pair_v4")
        self.assertEqual(template["summary"]["case_count"], 1)
        self.assertEqual(template["summary"]["candidate_pair_count"], 2)
        self.assertEqual(
            template["question_outcomes"][0]["status"],
            "cases_found",
        )
        case = template["cases"][0]
        self.assertEqual(case["label_status"], "unlabeled")
        self.assertEqual(
            case["source_review"]["dataset_reference_answer"],
            "The target quantity is 20 items.",
        )
        quote_hits = {
            candidate["candidate_id"]: candidate["reference_quote_indexes"]
            for candidate in case["candidates"]
        }
        self.assertEqual(quote_hits["candidate-b"], [0])
        self.assertEqual(quote_hits["candidate-a"], [])
        for candidate in case["candidates"]:
            self.assertEqual(candidate["referenced_source_ids"], ["source-node"])
            self.assertEqual(candidate["source_reference_status"], "resolved")
        case["source_review"]["source_nodes"][0]["rcept_no"] = "receipt-123"
        case["source_review"]["local_report_paths"] = [
            str((Path.cwd() / "filing_receipt-123.html").resolve())
        ]
        self.assertIn("Cases: 1", render_summary(template))
        rendered = render_review_packet(template)
        self.assertIn("candidate-a", rendered)
        self.assertIn("candidate-b", rendered)
        self.assertIn("Human label", rendered)
        self.assertIn("Exact original source node text.", rendered)
        self.assertIn("Source 1", rendered)
        self.assertIn("Original filing:", rendered)
        self.assertIn("filing_receipt-123.html", rendered)
        self.assertIn("Role:</strong> direct_value", rendered)
        self.assertIn("company=sample company", rendered)

    def test_skips_unverified_dataset_rows(self) -> None:
        dataset_row = {**_dataset_row(), "verification_status": "draft"}

        template = build_evidence_mining_template(
            [_context()],
            {"question-1": dataset_row},
            catalog_loader=lambda _context, _row: self.fail(
                "catalog loader should not run"
            ),
        )

        self.assertEqual(template["cases"], [])
        self.assertEqual(template["summary"]["skipped_question_count"], 1)
        self.assertEqual(
            template["skipped"][0]["reason"],
            "dataset_question_not_verified",
        )


if __name__ == "__main__":
    unittest.main()
