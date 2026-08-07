import unittest
from copy import deepcopy

import src.agent.financial_numeric_surface as financial_numeric_surface
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import FinancialAgentCalculationMixin
from src.agent.financial_numeric_surface import (
    extract_numeric_surface_candidates,
    numeric_surface_candidates_equivalent,
)


class FinancialNumericProvenanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = FinancialAgent.__new__(FinancialAgent)

    def test_normalized_numeric_candidate_extractor_has_numeric_surface_owner(self) -> None:
        self.assertTrue(
            hasattr(financial_numeric_surface, "numeric_candidates_with_spans_from_surface")
        )
        self.assertNotIn(
            "_numeric_candidates_with_spans_from_surface",
            FinancialAgentCalculationMixin.__dict__,
        )

    def test_normalized_numeric_candidate_matrix_preserves_units_year_guard_and_spans(
        self,
    ) -> None:
        million_krw = "\ubc31\ub9cc\uc6d0"
        hundred_million_krw = "\uc5b5\uc6d0"
        cases = [
            (
                "explicit_units",
                f"2023 1,234{million_krw} 12.5% 42",
                {},
                [
                    ("currency", 1_234_000_000.0, "KRW", "1,234", million_krw, 1_000_000.0, (5, 10)),
                    ("percent", 12.5, "PERCENT", "12.5", "%", 1.0, (14, 18)),
                ],
            ),
            (
                "metadata_unit_hint",
                "2023 1,234 12",
                {"unit_hint": million_krw},
                [
                    ("currency", 1_234_000_000.0, "KRW", "1,234", million_krw, 1_000_000.0, (5, 10)),
                ],
            ),
            (
                "parenthetical_negative",
                f"metric (1,234){hundred_million_krw}",
                {},
                [
                    (
                        "currency",
                        -123_400_000_000.0,
                        "KRW",
                        "(1,234)",
                        hundred_million_krw,
                        100_000_000.0,
                        (7, 14),
                    ),
                ],
            ),
            (
                "invalid_metadata_unit_falls_back_to_text",
                f"1,234{hundred_million_krw}",
                {"unit_hint": "unknown"},
                [
                    (
                        "currency",
                        123_400_000_000.0,
                        "KRW",
                        "1,234",
                        hundred_million_krw,
                        100_000_000.0,
                        (0, 5),
                    ),
                ],
            ),
            (
                "short_generic",
                "42",
                {},
                [("generic", 42.0, "", "42", "", 1.0, (0, 2))],
            ),
        ]

        for name, surface, metadata, expected in cases:
            with self.subTest(name=name):
                original_metadata = deepcopy(metadata)
                candidates = financial_numeric_surface.numeric_candidates_with_spans_from_surface(
                    surface,
                    metadata,
                )
                signature = [
                    (
                        item["kind"],
                        item["normalized_value"],
                        item["normalized_unit"],
                        item["value_text"],
                        item["unit_text"],
                        item["display_step"],
                        tuple(item["span"]),
                    )
                    for item in candidates
                ]
                self.assertEqual(signature, expected)
                self.assertTrue(all(item["value"] == item["normalized_value"] for item in candidates))
                self.assertTrue(all(item["unit"] == item["unit_text"] for item in candidates))
                self.assertEqual(metadata, original_metadata)

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
