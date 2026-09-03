from __future__ import annotations

import unittest

from src.agent.financial_candidate_tiebreaker import (
    SemanticTieBreakBatchV1,
    SemanticTieBreakScoreV1,
)
from src.ops.semantic_tiebreaker_promotion_gate import (
    build_pairs,
    evaluate_gate,
    load_fixture,
    render_text,
)


class SemanticTieBreakerPromotionGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = load_fixture()
        cls.pairs = build_pairs(cls.payload)

    def _batch(self, overrides: dict[str, float] | None = None) -> SemanticTieBreakBatchV1:
        scores = {
            "market_share_5_6": 0.1,
            "sales_growth_11_5": 0.9,
            "research_cost_line": 0.2,
            "research_total_line": 0.8,
            "company_overview": 0.1,
            "technology_strategy": 0.9,
            "operating_margin_7": 0.2,
            "revenue_growth_18": 0.8,
            "profit_driver": 0.9,
            "generic_market_context": 0.1,
            "duplicate_a": 0.5,
            "duplicate_b": 0.5,
        }
        scores.update(overrides or {})
        return SemanticTieBreakBatchV1(
            status="applied",
            scorer_id="fixture-scorer",
            requested_pair_count=len(self.pairs),
            unique_inference_pair_count=len(
                {pair.pair_fingerprint for pair in self.pairs}
            ),
            scores=tuple(
                SemanticTieBreakScoreV1(
                    cohort_id=pair.cohort_id,
                    candidate_id=pair.candidate_id,
                    score=scores[pair.candidate_id],
                )
                for pair in self.pairs
            ),
        )

    def test_fixture_projects_candidate_identity_for_same_sentence_values(self) -> None:
        pairs = {
            pair.candidate_id: pair
            for pair in self.pairs
            if pair.cohort_id == "growth:output"
        }

        self.assertEqual(len(self.pairs), 12)
        self.assertEqual(
            pairs["market_share_5_6"].target_text,
            pairs["sales_growth_11_5"].target_text,
        )
        self.assertNotEqual(
            pairs["market_share_5_6"].evidence_text,
            pairs["sales_growth_11_5"].evidence_text,
        )
        self.assertIn(
            "[SELECTED VALUE 5.6%]",
            pairs["market_share_5_6"].evidence_text,
        )
        self.assertIn(
            "[SELECTED VALUE 11.5%]",
            pairs["sales_growth_11_5"].evidence_text,
        )
        self.assertNotEqual(
            pairs["market_share_5_6"].pair_fingerprint,
            pairs["sales_growth_11_5"].pair_fingerprint,
        )

    def test_duplicate_evidence_has_one_semantic_identity(self) -> None:
        pairs = [
            pair
            for pair in self.pairs
            if pair.cohort_id == "duplicate_profit:output"
        ]

        self.assertEqual(len(pairs), 2)
        self.assertEqual(pairs[0].pair_fingerprint, pairs[1].pair_fingerprint)

    def test_ready_requires_quality_gain_abstention_and_latency(self) -> None:
        result = evaluate_gate(
            self.payload,
            self._batch(),
            warm_latency_ms=[410.0, 470.0, 520.0],
            cold_load_ms=5000.0,
            resolved_device="cpu",
        )

        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["promotion_ready"])
        self.assertEqual(result["metrics"]["baseline_top1_accuracy"], 0.2)
        self.assertEqual(result["metrics"]["model_top1_accuracy"], 1.0)
        self.assertEqual(result["metrics"]["top1_gain"], 0.8)
        self.assertEqual(result["metrics"]["confident_selection_rate"], 1.0)
        self.assertEqual(result["metrics"]["abstention_accuracy"], 1.0)
        self.assertEqual(result["metrics"]["warm_p95_ms"], 520.0)
        self.assertIn("Status: ready", render_text(result))

    def test_confident_wrong_selection_blocks_promotion(self) -> None:
        result = evaluate_gate(
            self.payload,
            self._batch(
                {
                    "market_share_5_6": 0.95,
                    "sales_growth_11_5": 0.1,
                }
            ),
            warm_latency_ms=[500.0],
        )

        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["checks"]["confident_errors"])
        self.assertEqual(
            result["confident_error_case_ids"],
            ["same_sentence_growth_vs_market_share"],
        )

    def test_low_margin_and_slow_p95_do_not_claim_promotion(self) -> None:
        result = evaluate_gate(
            self.payload,
            self._batch(
                {
                    "sales_growth_11_5": 0.51,
                    "market_share_5_6": 0.5,
                    "research_total_line": 0.51,
                    "research_cost_line": 0.5,
                    "technology_strategy": 0.51,
                    "company_overview": 0.5,
                }
            ),
            warm_latency_ms=[900.0, 1100.0],
        )

        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["checks"]["confident_selection_rate"])
        self.assertFalse(result["checks"]["warm_latency"])


if __name__ == "__main__":
    unittest.main()
