from __future__ import annotations

import unittest

from src.agent.financial_artifact_contracts import payload_missing_contract


class FinancialArtifactContractTests(unittest.TestCase):
    def test_narrative_aggregate_retains_its_actual_source_material(self):
        self.assertEqual(
            payload_missing_contract("aggregated_answer", {
                "final_answer": "Grounded statement.",
                "evidence_items": [{"evidence_id": "e1", "claim": "Grounded statement."}],
                "structured_result": {}, "resolved_calculation_trace": {},
            }),
            "",
        )

    def test_narrative_answer_without_source_material_remains_invalid(self):
        self.assertEqual(
            payload_missing_contract("aggregated_answer", {
                "final_answer": "Unsupported statement.", "evidence_items": [],
                "structured_result": {}, "resolved_calculation_trace": {},
            }),
            "aggregated_answer.source_material",
        )


if __name__ == "__main__":
    unittest.main()
