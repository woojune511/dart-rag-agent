from __future__ import annotations

import unittest

from src.agent.financial_surface_contracts import operand_segment_label


class FinancialSurfaceContractTests(unittest.TestCase):
    def test_operand_segment_label_reads_only_normalized_binding_policy_value(self) -> None:
        self.assertEqual(
            operand_segment_label(
                {
                    "segment_label": "ignored top-level",
                    "binding_policy": {"segment_label": "  Division   A  "},
                }
            ),
            "Division A",
        )
        self.assertEqual(operand_segment_label({"segment_label": "top-level only"}), "")
        self.assertEqual(operand_segment_label({"binding_policy": {"segment_label": " "}}), "")
        self.assertEqual(operand_segment_label({}), "")


if __name__ == "__main__":
    unittest.main()
