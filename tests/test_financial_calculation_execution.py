import unittest

from src.agent.financial_calculation_execution import build_failed_calculation_result


class FinancialCalculationExecutionTests(unittest.TestCase):
    def test_build_failed_calculation_result_uses_missing_primary_slot_without_operands(self) -> None:
        result = build_failed_calculation_result(
            active_subtask={
                "operation_family": "lookup",
                "metric_label": "법인세비용차감전순이익",
                "required_operands": [
                    {
                        "role": "operand",
                        "label": "법인세비용차감전순이익",
                        "concept": "income_before_income_taxes",
                        "period_hint": "2023년",
                    }
                ],
            },
            operation_family="lookup",
            runtime_operands=[],
            result_unit="",
            source_normalized_unit="UNKNOWN",
            status="insufficient_operands",
            reason="no operation or operands",
        )

        self.assertEqual(result["status"], "insufficient_operands")
        self.assertEqual(result["result_value"], None)
        self.assertEqual(result["series"], [])
        self.assertEqual(result["explanation"], "no operation or operands")
        self.assertEqual(result["answer_slots"]["operation_family"], "lookup")
        self.assertEqual(result["answer_slots"]["primary_value"]["status"], "missing")
        self.assertEqual(result["answer_slots"]["primary_value"]["concept"], "income_before_income_taxes")

    def test_build_failed_calculation_result_preserves_operand_components_when_available(self) -> None:
        result = build_failed_calculation_result(
            active_subtask={"operation_family": "ratio", "metric_label": "ratio"},
            operation_family="ratio",
            runtime_operands=[
                {
                    "operand_id": "op_1",
                    "label": "분자",
                    "matched_operand_role": "numerator",
                    "raw_value": "10",
                    "raw_unit": "%",
                    "normalized_value": 10.0,
                    "normalized_unit": "PERCENT",
                    "evidence_id": "ev_1",
                }
            ],
            result_unit="%",
            source_normalized_unit="PERCENT",
            status="unit_mismatch",
            reason="unit families differ",
        )

        self.assertEqual(result["status"], "unit_mismatch")
        self.assertEqual(result["answer_slots"]["components_by_role"]["numerator"][0]["source_row_id"], "ev_1")


if __name__ == "__main__":
    unittest.main()
