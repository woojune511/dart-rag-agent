import unittest

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_numeric_surface import (
    extract_numeric_surface_candidates,
    numeric_surface_candidates_equivalent,
)


class FinancialNumericProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = FinancialAgent.__new__(FinancialAgent)

    def test_currency_surface_equivalence_preserves_sign(self) -> None:
        positive = extract_numeric_surface_candidates("1,000백만원")[0]
        negative = extract_numeric_surface_candidates("(1,000)백만원")[0]

        self.assertFalse(numeric_surface_candidates_equivalent(positive, negative))
        self.assertTrue(numeric_surface_candidates_equivalent(negative, dict(negative)))

    def test_final_answer_surface_prefers_matching_label_and_period_provenance(self) -> None:
        final_answer = "2023 target metric is 1,000백만원."
        projection = {
            "calculation_operands": [],
            "calculation_result": {"status": "ok", "current_period": "2023"},
        }
        evidence_items = [
            {
                "evidence_id": "wrong",
                "claim": "2022 unrelated metric is 1,000백만원.",
                "quote_span": "2022 unrelated metric is 1,000백만원.",
                "metadata": {"row_label": "unrelated metric", "year": 2022},
            },
            {
                "evidence_id": "correct",
                "claim": "2023 target metric is 1,000백만원.",
                "quote_span": "2023 target metric is 1,000백만원.",
                "metadata": {"row_label": "target metric", "year": 2023},
            },
        ]

        updated = self.agent._append_final_answer_surface_operands_from_evidence(
            projection,
            evidence_items,
            final_answer=final_answer,
        )

        operands = list(updated.get("calculation_operands") or [])
        self.assertEqual(len(operands), 1)
        self.assertEqual(operands[0]["source_row_id"], "correct")
        self.assertEqual(operands[0]["period"], "2023")

    def test_final_answer_surface_rejects_opposite_sign_evidence(self) -> None:
        updated = self.agent._append_final_answer_surface_operands_from_evidence(
            {"calculation_operands": [], "calculation_result": {"status": "ok"}},
            [
                {
                    "evidence_id": "negative",
                    "claim": "target metric is (1,000)백만원.",
                    "quote_span": "target metric is (1,000)백만원.",
                    "metadata": {"row_label": "target metric"},
                }
            ],
            final_answer="target metric is 1,000백만원.",
        )

        self.assertEqual(updated["calculation_operands"], [])


if __name__ == "__main__":
    unittest.main()
