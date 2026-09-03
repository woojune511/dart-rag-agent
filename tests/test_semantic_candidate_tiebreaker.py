from __future__ import annotations

import unittest
from typing import Sequence
from unittest.mock import patch

from src.agent.financial_candidate_tiebreaker import (
    LocalCrossEncoderTieBreaker,
    SemanticTieBreakBatchV1,
    SemanticTieBreakPairV2,
    SemanticTieBreakScoreV1,
)
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
from src.config.retrieval_policy import CALCULATION_PROMPT_POLICY


def _candidate(
    candidate_id: str,
    *,
    row_id: str,
    column: str,
    value: str,
) -> dict:
    return {
        "candidate_id": candidate_id,
        "kind": "numeric",
        "candidate_kind": "structured_value",
        "source_candidate_id": f"source-{row_id}",
        "evidence_id": "sample-table",
        "source_anchor": "[sample]",
        "source_row_id": row_id,
        "table_source_id": "sample-table",
        "physical_table_id": "sample-table",
        "physical_row_id": row_id,
        "physical_cell_id": f"{row_id}-{column}",
        "row_label": "Target Entity",
        "row_headers": ["Target Entity"],
        "local_entity_surfaces": ["Target Entity"],
        "column_headers": [column],
        "raw_value": value,
        "raw_unit": "million",
        "normalized_value": float(value),
        "normalized_unit": "KRW",
        "company": "Filing Company",
        "document_company": "Filing Company",
        "consolidation_scope": "unknown",
        "segment": "",
        "basis": "",
        "period": "2024",
        "context_fingerprint": "sample-table",
        "source_text": f"Target Entity | {column} {value} million",
    }


def _obligation(obligation_id: str, metric: str) -> dict:
    return {
        "obligation_id": obligation_id,
        "kind": "direct_value",
        "label": metric,
        "required": True,
        "display_unit": "million",
        "display_format": "",
        "scope": {
            "company": "Filing Company",
            "period": "2024",
            "consolidation_scope": "unknown",
            "segment": "",
            "basis": "",
        },
        "retrieval_hints": [],
        "concept_hints": [],
        "semantic_target": {
            "local_subjects": ["Target Entity"],
            "concept_keys": [],
            "metric_surfaces": [metric],
        },
        "evidence_requirements": [],
        "depends_on": [],
        "coupling_key": "",
    }


class _ScoreByCandidate:
    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = dict(scores)
        self.calls: list[tuple[SemanticTieBreakPairV2, ...]] = []

    def score_pairs(
        self,
        pairs: Sequence[SemanticTieBreakPairV2],
    ) -> SemanticTieBreakBatchV1:
        rows = tuple(pairs)
        self.calls.append(rows)
        return SemanticTieBreakBatchV1(
            status="applied",
            scorer_id="fake_semantic_scorer",
            scores=tuple(
                SemanticTieBreakScoreV1(
                    cohort_id=pair.cohort_id,
                    candidate_id=pair.candidate_id,
                    score=self.scores[pair.candidate_id],
                )
                for pair in rows
            ),
            requested_pair_count=len(rows),
            unique_inference_pair_count=len(rows),
        )


class SemanticCandidateTieBreakerTests(unittest.TestCase):
    def test_cross_encoder_batches_and_caches_pair_scores(self) -> None:
        class FakeModel:
            def __init__(self) -> None:
                self.calls: list[list[tuple[str, str]]] = []

            def predict(self, pairs, **_kwargs):
                self.calls.append(list(pairs))
                return [0.2, 0.8]

        model = FakeModel()
        factory_calls = []

        def factory(model_name, **kwargs):
            factory_calls.append((model_name, kwargs))
            return model

        scorer = LocalCrossEncoderTieBreaker(
            model_name="local/test-model",
            revision="revision-1",
            model_factory=factory,
        )
        owner = _obligation("ob_metric", "metric alpha")
        pairs = [
            SemanticTieBreakPairV2.create(
                cohort_id="ob_metric:output",
                owner_id="ob_metric",
                candidate_id=candidate_id,
                query="Find metric alpha",
                owner=owner,
                parent_owner=None,
                resolved_target={
                    "local_subjects": ["Target Entity"],
                    "concept_keys": [],
                    "metric_surfaces": ["metric alpha"],
                    "expected_unit_family": "KRW",
                },
                candidate=candidate,
                candidate_text=str(candidate["source_text"]),
            )
            for candidate_id, candidate in (
                (
                    "candidate-a",
                    _candidate(
                        "candidate-a",
                        row_id="row-a",
                        column="metric alpha",
                        value="10",
                    ),
                ),
                (
                    "candidate-b",
                    _candidate(
                        "candidate-b",
                        row_id="row-b",
                        column="metric alpha",
                        value="20",
                    ),
                ),
            )
        ]

        first = scorer.score_pairs(pairs)
        second = scorer.score_pairs(pairs)

        self.assertEqual(first.status, "applied")
        self.assertEqual(first.unique_inference_pair_count, 2)
        self.assertEqual(second.unique_inference_pair_count, 0)
        self.assertEqual(second.cache_hit_count, 2)
        self.assertEqual(len(factory_calls), 1)
        self.assertEqual(len(model.calls), 1)
        self.assertEqual(
            [item.score for item in second.scores],
            [0.2, 0.8],
        )

    def test_prepare_loads_model_without_running_inference(self) -> None:
        class FakeModel:
            def __init__(self) -> None:
                self.predict_calls = 0

            def predict(self, _pairs, **_kwargs):
                self.predict_calls += 1
                return []

        model = FakeModel()
        scorer = LocalCrossEncoderTieBreaker(
            model_name="local/test-model",
            model_factory=lambda *_args, **_kwargs: model,
        )

        self.assertTrue(scorer.prepare())
        self.assertTrue(scorer.prepare())
        self.assertEqual(model.predict_calls, 0)
        self.assertEqual(scorer.load_error_code, "")

    def test_semantics_only_reorders_the_strongest_factor_tie(self) -> None:
        owner = _obligation("ob_metric", "metric alpha")
        left = _candidate(
            "left",
            row_id="row-left",
            column="metric alpha",
            value="10",
        )
        right = _candidate(
            "right",
            row_id="row-right",
            column="metric alpha",
            value="20",
        )
        lower_tier = _candidate(
            "lower-tier",
            row_id="row-lower",
            column="unrelated column",
            value="30",
        )
        scorer = _ScoreByCandidate({"left": 0.1, "right": 0.9})

        plan = _semantic_candidate_cohorts(
            [lower_tier, right, left],
            [owner],
            query="Find metric alpha",
            semantic_tiebreaker=scorer,
        )
        output = next(
            row
            for row in plan["cohorts"]
            if row["cohort_id"] == "ob_metric:output"
        )

        self.assertEqual(len(scorer.calls), 1)
        self.assertEqual(
            {pair.candidate_id for pair in scorer.calls[0]},
            {"left", "right"},
        )
        self.assertEqual(
            output["candidate_ids"],
            ["right", "left", "lower-tier"],
        )
        semantic = output["ranking_diagnostics"]["semantic_tiebreaker"]
        self.assertEqual(semantic["status"], "applied")
        self.assertEqual(semantic["ordered_candidate_ids"], ["right", "left"])
        payload = FinancialAgent._semantic_program_prompt_payload(
            [lower_tier, right, left],
            plan,
        )
        self.assertNotIn("ranking_diagnostics", payload["cohorts"][0])
        self.assertNotIn("semantic_tiebreaker", payload)

    def test_low_semantic_margin_preserves_deterministic_order(self) -> None:
        owner = _obligation("ob_metric", "metric alpha")
        left = _candidate(
            "left",
            row_id="row-left",
            column="metric alpha",
            value="10",
        )
        right = _candidate(
            "right",
            row_id="row-right",
            column="metric alpha",
            value="20",
        )
        scorer = _ScoreByCandidate({"left": 0.50, "right": 0.51})

        plan = _semantic_candidate_cohorts(
            [right, left],
            [owner],
            query="Find metric alpha",
            semantic_tiebreaker=scorer,
        )
        output = next(
            row
            for row in plan["cohorts"]
            if row["cohort_id"] == "ob_metric:output"
        )

        self.assertEqual(output["candidate_ids"], ["left", "right"])
        semantic = output["ranking_diagnostics"]["semantic_tiebreaker"]
        self.assertEqual(semantic["status"], "abstained_low_margin")
        self.assertAlmostEqual(semantic["top_score_margin"], 0.01)

    def test_pair_projection_marks_the_selected_physical_value(self) -> None:
        owner = _obligation("ob_metric", "metric alpha")
        candidate = {
            **_candidate(
                "candidate-a",
                row_id="row-a",
                column="metric alpha",
                value="10",
            ),
            "period": "metric alpha",
            "value_year": 2024,
            "source_period_surface": "metric alpha",
            "period_source": "source_surface_unresolved",
        }

        pair = SemanticTieBreakPairV2.create(
            cohort_id="ob_metric:output",
            owner_id="ob_metric",
            candidate_id="candidate-a",
            query="Find metric alpha",
            owner=owner,
            parent_owner=None,
            resolved_target={
                "local_subjects": ["Target Entity"],
                "concept_keys": [],
                "metric_surfaces": ["metric alpha"],
                "expected_unit_family": "KRW",
            },
            candidate=candidate,
            candidate_text=str(candidate["source_text"]),
        )

        self.assertIn("[SELECTED VALUE 10 million]", pair.evidence_text)
        self.assertNotIn("period source", pair.evidence_text)

    def test_pair_projection_marks_zero_without_matching_a_larger_number(self) -> None:
        owner = _obligation("ob_metric", "metric alpha")
        candidate = {
            **_candidate(
                "candidate-zero",
                row_id="row-zero",
                column="metric alpha",
                value="0",
            ),
            "raw_value": 0,
            "source_text": "metric alpha 100 million | metric alpha 0 million",
        }

        pair = SemanticTieBreakPairV2.create(
            cohort_id="ob_metric:output",
            owner_id="ob_metric",
            candidate_id="candidate-zero",
            query="Find metric alpha",
            owner=owner,
            parent_owner=None,
            resolved_target={
                "local_subjects": ["Target Entity"],
                "concept_keys": [],
                "metric_surfaces": ["metric alpha"],
                "expected_unit_family": "KRW",
            },
            candidate=candidate,
            candidate_text=str(candidate["source_text"]),
        )

        self.assertIn("100 million", pair.evidence_text)
        self.assertIn("[SELECTED VALUE 0 million]", pair.evidence_text)
        self.assertNotIn("1[SELECTED VALUE", pair.evidence_text)

    def test_complete_row_bundle_aggregates_semantic_owner_order(self) -> None:
        obligations = [
            _obligation("ob_alpha", "metric alpha"),
            _obligation("ob_beta", "metric beta"),
        ]
        catalog = [
            _candidate(
                "alpha-a",
                row_id="row-a",
                column="metric alpha",
                value="10",
            ),
            _candidate(
                "beta-a",
                row_id="row-a",
                column="metric beta",
                value="11",
            ),
            _candidate(
                "alpha-b",
                row_id="row-b",
                column="metric alpha",
                value="20",
            ),
            _candidate(
                "beta-b",
                row_id="row-b",
                column="metric beta",
                value="21",
            ),
        ]
        scorer = _ScoreByCandidate(
            {
                "alpha-a": 0.1,
                "alpha-b": 0.9,
                "beta-a": 0.2,
                "beta-b": 0.8,
            }
        )

        plan = _semantic_candidate_cohorts(
            catalog,
            obligations,
            query="Find both metrics",
            semantic_tiebreaker=scorer,
        )

        self.assertEqual(len(scorer.calls), 1)
        self.assertEqual(len(scorer.calls[0]), 4)
        self.assertEqual(len(plan["evidence_bundle_constraints"]), 1)
        selection = plan["evidence_bundle_option_selections"][0]
        self.assertEqual(selection["selected_physical_row_id"], "row-b")
        self.assertEqual(
            plan["candidate_ids_by_owner"]["ob_alpha"],
            ["alpha-b"],
        )
        self.assertEqual(
            plan["candidate_ids_by_owner"]["ob_beta"],
            ["beta-b"],
        )

    def test_large_top_tier_skips_semantic_scoring(self) -> None:
        owner = _obligation("ob_metric", "metric alpha")
        catalog = [
            _candidate(
                f"candidate-{index}",
                row_id=f"row-{index}",
                column="metric alpha",
                value=str(index),
            )
            for index in range(3)
        ]
        scorer = _ScoreByCandidate(
            {
                candidate["candidate_id"]: float(index)
                for index, candidate in enumerate(catalog)
            }
        )
        policy = CALCULATION_PROMPT_POLICY["semantic_top_tier_tiebreaker"]

        with patch.dict(policy, {"max_candidates_per_cohort": 2}):
            plan = _semantic_candidate_cohorts(
                catalog,
                [owner],
                query="Find metric alpha",
                semantic_tiebreaker=scorer,
            )

        output = next(
            row
            for row in plan["cohorts"]
            if row["cohort_id"] == "ob_metric:output"
        )
        self.assertEqual(scorer.calls, [])
        self.assertEqual(
            output["ranking_diagnostics"]["semantic_tiebreaker"]["status"],
            "skipped_capacity",
        )

    def test_query_pair_capacity_skips_the_whole_semantic_batch(self) -> None:
        obligations = [
            _obligation("ob_alpha", "metric alpha"),
            _obligation("ob_beta", "metric beta"),
        ]
        catalog = [
            _candidate(
                f"{metric}-{index}",
                row_id=f"{metric}-row-{index}",
                column=f"metric {metric}",
                value=str(index),
            )
            for metric in ("alpha", "beta")
            for index in range(2)
        ]
        scorer = _ScoreByCandidate(
            {
                candidate["candidate_id"]: float(index)
                for index, candidate in enumerate(catalog)
            }
        )
        policy = CALCULATION_PROMPT_POLICY["semantic_top_tier_tiebreaker"]

        with patch.dict(
            policy,
            {
                "max_candidates_per_cohort": 2,
                "max_pairs_per_query": 3,
            },
        ):
            plan = _semantic_candidate_cohorts(
                catalog,
                obligations,
                query="Find both metrics",
                semantic_tiebreaker=scorer,
            )

        self.assertEqual(scorer.calls, [])
        self.assertEqual(
            plan["semantic_tiebreaker"]["status"],
            "skipped_capacity",
        )
        output_statuses = {
            cohort["ranking_diagnostics"]["semantic_tiebreaker"]["status"]
            for cohort in plan["cohorts"]
            if cohort["cohort_id"].endswith(":output")
        }
        self.assertEqual(output_statuses, {"skipped_capacity"})


if __name__ == "__main__":
    unittest.main()
