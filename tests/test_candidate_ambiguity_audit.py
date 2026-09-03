from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog,
    build_semantic_source_candidates,
    semantic_candidate_catalog_fingerprint,
    semantic_candidate_id_fingerprint,
)
from src.ops.audit_candidate_ambiguity import (
    build_candidate_ambiguity_audit,
    load_saved_plans,
    render_markdown,
)


def _obligation() -> dict:
    return {
        "obligation_id": "ob_value",
        "kind": "direct_value",
        "label": "target entity quantity",
        "required": True,
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


def _candidate(candidate_id: str, *, period: str) -> dict:
    return {
        "candidate_id": candidate_id,
        "kind": "numeric",
        "candidate_kind": "structured_value",
        "source_candidate_id": f"source-{candidate_id}",
        "evidence_id": f"evidence-{candidate_id}",
        "source_row_id": f"row-{candidate_id}",
        "physical_table_id": "table-sample",
        "physical_row_id": f"row-{candidate_id}",
        "physical_cell_id": f"cell-{candidate_id}",
        "row_label": "target entity",
        "row_headers": ["target entity"],
        "local_entity_surfaces": ["target entity"],
        "column_headers": ["quantity"],
        "raw_value": "10",
        "raw_unit": "items",
        "normalized_value": 10.0,
        "normalized_unit": "COUNT",
        "document_company": "sample company",
        "company": "sample company",
        "year": 2024 if period else None,
        "value_year": 2024 if period else None,
        "period": period,
        "consolidation_scope": "unknown",
        "segment": "",
        "basis": "",
        "source_text": "target entity quantity 10 items",
    }


def _v6_plan() -> dict:
    cohort = {
        "cohort_id": "ob_value:output",
        "owner_id": "ob_value",
        "parent_obligation_id": "ob_value",
        "owner_type": "obligation",
        "candidate_kind": "numeric",
        "candidate_ids": ["compatible", "unknown"],
        "match_counts": {
            "compatible": 1,
            "unknown_only": 1,
            "explicit_conflict": 0,
        },
    }
    return {
        "answer_obligations": [_obligation()],
        "proposed_candidates": [
            _candidate("compatible", period="2024"),
            _candidate("unknown", period=""),
        ],
        "candidate_cohorts": [cohort],
        "candidate_stage_diagnostics": {
            "schema": "semantic_candidate_stage_diagnostics_v6",
            "catalog_candidate_count": 2,
            "prompt_candidate_count": 2,
            "cohorts": [cohort],
            "evidence_bundle_option_selections": [],
            "islands": [
                {
                    "island_id": "island_001",
                    "obligation_ids": ["ob_value"],
                    "call_count": 1,
                    "retry_count": 0,
                    "prompt_bytes": 200,
                }
            ],
        },
    }


class CandidateAmbiguityAuditTests(unittest.TestCase):
    def test_v6_reprojects_only_the_saved_admitted_cohort(self) -> None:
        audit = build_candidate_ambiguity_audit(
            [
                {
                    "question_id": "question-1",
                    "source_file": "saved/results.json",
                    "plan": _v6_plan(),
                }
            ]
        )

        ranking = audit["questions"][0]["cohorts"][0]["ranking"]
        self.assertEqual(ranking["status"], "available")
        self.assertEqual(ranking["population"], "admitted_cohort")
        self.assertEqual(
            ranking["source"],
            "provider_free_saved_plan_reprojection",
        )
        self.assertEqual(ranking["top_two_relation"], "separated")
        self.assertEqual(
            ranking["first_differing_factor"],
            "applicability_state",
        )
        self.assertFalse(
            audit["summary"]["full_catalog_ranking_available"]
        )

    def test_v6_replays_a_verified_full_catalog_from_structure_graph(self) -> None:
        metadata = {
            "chunk_uid": "chunk-a",
            "company": "sample company",
            "year": 2024,
            "section": "sample section",
            "section_path": "sample section",
            "block_type": "paragraph",
        }
        document = SimpleNamespace(
            page_content="target entity quantity 10%",
            metadata=metadata,
        )
        alternate_metadata = {
            **metadata,
            "chunk_uid": "chunk-b",
            "year": None,
        }
        alternate_document = SimpleNamespace(
            page_content="target entity quantity 11%",
            metadata=alternate_metadata,
        )
        source_candidates = build_semantic_source_candidates(
            {
                "retrieved_docs": [
                    (document, 0.0),
                    (alternate_document, 0.0),
                ],
                "seed_retrieved_docs": [],
            },
            source_anchor_builder=lambda row: (
                f"[{row.get('company')} | {row.get('year')} | "
                f"{row.get('section_path')}]"
            ),
        )
        catalog = build_semantic_candidate_catalog(source_candidates)
        numeric_by_source = {
            str(candidate.get("source_candidate_id") or ""): candidate
            for candidate in catalog
            if candidate.get("kind") == "numeric"
        }
        selected_candidate = numeric_by_source["chunk-a"]
        alternate_candidate = numeric_by_source["chunk-b"]
        cohort = {
            "cohort_id": "ob_value:output",
            "owner_id": "ob_value",
            "parent_obligation_id": "ob_value",
            "owner_type": "obligation",
            "candidate_kind": "numeric",
            "candidate_ids": [selected_candidate["candidate_id"]],
            "match_counts": {},
            "limit": 4,
        }
        bundle_selection = {
            "constraint_id": "bundle-selected",
            "selected_option_id": "option-a",
            "ranked_options": [
                {
                    "option_id": "option-a",
                    "physical_table_id": "table-a",
                    "physical_row_id": "row-a",
                    "candidate_ids_by_owner": {
                        "ob_value": [selected_candidate["candidate_id"]]
                    },
                },
                {
                    "option_id": "option-b",
                    "physical_table_id": "table-b",
                    "physical_row_id": "row-b",
                    "candidate_ids_by_owner": {
                        "ob_value": [alternate_candidate["candidate_id"]]
                    },
                },
            ],
        }
        obligation = _obligation()
        obligation["display_unit"] = "percent"
        plan = {
            "answer_obligations": [obligation],
            "candidate_catalog_fingerprint": (
                semantic_candidate_catalog_fingerprint(catalog)
            ),
            "candidate_cohorts": [cohort],
            "proposed_candidates": [selected_candidate],
            "evidence_bundle_option_selections": [bundle_selection],
            "candidate_stage_diagnostics": {
                "schema": "semantic_candidate_stage_diagnostics_v6",
                "source_window": {
                    "retrieved_source_ids": ["chunk-a", "chunk-b"],
                    "retrieved_unidentified_count": 0,
                    "seed_source_ids": [],
                    "seed_unidentified_count": 0,
                },
                "source_candidate_count": len(source_candidates),
                "source_candidate_id_fingerprint": (
                    semantic_candidate_id_fingerprint(
                        [item["candidate_id"] for item in source_candidates]
                    )
                ),
                "catalog_candidate_count": len(catalog),
                "catalog_candidate_id_fingerprint": (
                    semantic_candidate_id_fingerprint(
                        [item["candidate_id"] for item in catalog]
                    )
                ),
                "prompt_candidate_count": 1,
                "cohorts": [cohort],
                "evidence_bundle_option_selections": [bundle_selection],
                "islands": [],
            },
        }

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = root / "store"
            store.mkdir()
            (store / "document_structure_graph.json").write_text(
                json.dumps(
                    {
                        "nodes": {
                            "chunk-a": {
                                "chunk_uid": "chunk-a",
                                "text": document.page_content,
                                "metadata": metadata,
                            },
                            "chunk-b": {
                                "chunk_uid": "chunk-b",
                                "text": alternate_document.page_content,
                                "metadata": alternate_metadata,
                            },
                        },
                        "parents": {},
                        "sections": {},
                    }
                ),
                encoding="utf-8",
            )
            results_path = root / "results.json"
            results_path.write_text(
                json.dumps(
                    {
                        "store": {"persist_directory": str(store)},
                        "per_question": [
                            {
                                "id": "question-replay",
                                "question": "Return the quantity.",
                                "resolved_calculation_trace": {
                                    "calculation_plan": plan
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            saved = load_saved_plans([results_path])
            audit = build_candidate_ambiguity_audit(saved)
            mismatched_saved = json.loads(json.dumps(saved))
            mismatched_saved[0]["plan"]["candidate_catalog_fingerprint"] = (
                "different-catalog"
            )
            mismatch_audit = build_candidate_ambiguity_audit(
                mismatched_saved
            )

        question = audit["questions"][0]
        self.assertEqual(question["catalog_replay"]["status"], "verified")
        ranking = question["cohorts"][0]["ranking"]
        self.assertEqual(ranking["population"], "eligible_catalog")
        self.assertEqual(
            ranking["source"],
            "provider_free_structure_graph_replay",
        )
        margin = question["complete_row_bundles"][0]["top_two_margin"]
        self.assertEqual(
            margin["source"],
            "provider_free_structure_graph_replay",
        )
        self.assertEqual(margin["status"], "separated")
        self.assertEqual(margin["position_sum_delta"], 1)
        self.assertTrue(audit["summary"]["full_catalog_ranking_available"])
        mismatch_question = mismatch_audit["questions"][0]
        self.assertEqual(mismatch_question["catalog_replay"]["status"], "mismatch")
        self.assertEqual(
            mismatch_question["cohorts"][0]["ranking"]["population"],
            "admitted_cohort",
        )

    def test_v7_uses_full_catalog_ranking_and_bundle_margin(self) -> None:
        ranking = {
            "schema": "candidate_ranking_diagnostics_v1",
            "status": "available",
            "population": "eligible_catalog",
            "source": "runtime_candidate_matching",
            "eligible_candidate_count": 4,
            "top_tier_candidate_count": 2,
            "top_two_relation": "tie",
            "first_differing_factor": "",
        }
        cohort = {
            "cohort_id": "ob_value:output",
            "owner_id": "ob_value",
            "parent_obligation_id": "ob_value",
            "owner_type": "obligation",
            "candidate_kind": "numeric",
            "candidate_ids": ["candidate-a"],
            "match_counts": {
                "compatible": 2,
                "unknown_only": 2,
                "explicit_conflict": 3,
            },
            "ranking_diagnostics": ranking,
        }
        selection = {
            "constraint_id": "bundle-1",
            "selected_option_id": "option-a",
            "selected_physical_table_id": "table-a",
            "selected_physical_row_id": "row-a",
            "complete_option_count": 2,
            "ranked_options": [
                {"option_id": "option-a"},
                {"option_id": "option-b"},
            ],
            "ranked_option_diagnostics": [
                {
                    "option_id": "option-a",
                    "position_sum": 0,
                    "worst_position": 0,
                },
                {
                    "option_id": "option-b",
                    "position_sum": 2,
                    "worst_position": 1,
                },
            ],
        }
        plan = {
            "candidate_cohorts": [cohort],
            "candidate_stage_diagnostics": {
                "schema": "semantic_candidate_stage_diagnostics_v7",
                "catalog_candidate_count": 7,
                "prompt_candidate_count": 1,
                "cohorts": [cohort],
                "evidence_bundle_option_selections": [selection],
                "islands": [
                    {
                        "island_id": "island-1",
                        "obligation_ids": ["ob_value"],
                        "call_count": 2,
                        "retry_count": 1,
                        "prompt_bytes": 300,
                        "accepted_program_fingerprint": "accepted",
                    }
                ],
            },
        }

        audit = build_candidate_ambiguity_audit(
            [
                {
                    "question_id": "question-2",
                    "source_file": "saved/results.json",
                    "plan": plan,
                }
            ]
        )

        self.assertTrue(audit["summary"]["full_catalog_ranking_available"])
        self.assertEqual(audit["summary"]["ambiguous_top_tier_count"], 1)
        self.assertEqual(audit["summary"]["multi_option_bundle_count"], 1)
        bundle = audit["questions"][0]["complete_row_bundles"][0]
        self.assertEqual(bundle["top_two_margin"]["status"], "separated")
        self.assertEqual(bundle["top_two_margin"]["position_sum_delta"], 2)
        self.assertEqual(bundle["top_two_margin"]["worst_position_delta"], 1)
        self.assertEqual(
            audit["questions"][0]["islands"][0]["failure_class"],
            "recovered_after_retry",
        )
        self.assertIn("eligible_catalog", render_markdown(audit))

    def test_saved_trace_mirrors_are_deduplicated(self) -> None:
        plan = _v6_plan()
        question = {
            "id": "question-1",
            "question": "Return the quantity.",
            "resolved_calculation_trace": {"calculation_plan": plan},
            "structured_result": {
                "resolved_calculation_trace": {"calculation_plan": plan}
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.json"
            path.write_text(
                json.dumps({"per_question": [question]}),
                encoding="utf-8",
            )
            rows = load_saved_plans([path])

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["question_id"], "question-1")


if __name__ == "__main__":
    unittest.main()
