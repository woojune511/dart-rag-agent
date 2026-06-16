import unittest

from src.agent.financial_answer_slots import (
    build_answer_slots,
    build_calculated_value_slot,
    build_missing_value_slot,
    build_operand_value_slot,
    coerce_slot_numeric,
    slot_status,
)


class FinancialAnswerSlotTests(unittest.TestCase):
    def test_slot_status_uses_numeric_then_surface_material(self) -> None:
        self.assertEqual(slot_status(normalized_value=1.0, rendered_value="", raw_value=""), "ok")
        self.assertEqual(slot_status(normalized_value=None, rendered_value="123", raw_value=""), "derived")
        self.assertEqual(slot_status(normalized_value=None, rendered_value="", raw_value=""), "missing")

    def test_coerce_slot_numeric_returns_none_for_unparseable_values(self) -> None:
        self.assertEqual(coerce_slot_numeric("12.5"), 12.5)
        self.assertIsNone(coerce_slot_numeric("not numeric"))

    def test_build_missing_value_slot_preserves_source_ids_and_policy_defaults(self) -> None:
        slot = build_missing_value_slot(
            role="primary_value",
            label=" 매출 ",
            concept="revenue",
            source_row_ids=["", "row_1", "row_1"],
        )

        self.assertEqual(slot["status"], "missing")
        self.assertEqual(slot["role"], "primary_value")
        self.assertEqual(slot["label"], "매출")
        self.assertEqual(slot["concept"], "revenue")
        self.assertEqual(slot["normalized_unit"], "UNKNOWN")
        self.assertEqual(slot["source_row_id"], "row_1")
        self.assertEqual(slot["source_row_ids"], ["row_1"])

    def test_build_operand_value_slot_renders_normalized_value(self) -> None:
        slot = build_operand_value_slot(
            {
                "label": "자본",
                "matched_operand_role": "denominator",
                "matched_operand_concept": "equity",
                "raw_value": "100",
                "raw_unit": "%",
                "normalized_value": 100.0,
                "normalized_unit": "PERCENT",
                "source_row_ids": ["row_a"],
                "source_anchor": "anchor",
            },
            default_role="operand",
        )

        self.assertEqual(slot["status"], "ok")
        self.assertEqual(slot["role"], "denominator")
        self.assertEqual(slot["label"], "자본")
        self.assertEqual(slot["concept"], "equity")
        self.assertEqual(slot["rendered_value"], "100%")
        self.assertEqual(slot["source_row_id"], "row_a")
        self.assertEqual(slot["source_anchor"], "anchor")

    def test_build_calculated_value_slot_uses_display_unit_renderer(self) -> None:
        slot = build_calculated_value_slot(
            label="차이",
            normalized_value=1_000_000.0,
            normalized_unit="KRW",
            display_unit="백만원",
            period="2023",
            source_row_ids=["row_a", "row_b"],
            role="delta_value",
        )

        self.assertEqual(slot["status"], "ok")
        self.assertEqual(slot["role"], "delta_value")
        self.assertEqual(slot["rendered_value"], "1백만원")
        self.assertEqual(slot["source_row_ids"], ["row_a", "row_b"])

    def test_build_answer_slots_creates_missing_lookup_primary_value(self) -> None:
        slots = build_answer_slots(
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
            ordered_operands=[],
            result_value=None,
            result_unit="",
            normalized_unit="UNKNOWN",
            source_normalized_unit="UNKNOWN",
            current_value=None,
            prior_value=None,
            delta_value=None,
            current_period="2023",
            prior_period="",
            source_row_ids=[],
        )

        self.assertEqual(slots["operation_family"], "lookup")
        self.assertEqual(slots["primary_value"]["status"], "missing")
        self.assertEqual(slots["primary_value"]["concept"], "income_before_income_taxes")
        self.assertEqual(slots["primary_value"]["period"], "2023년")

    def test_build_answer_slots_creates_difference_period_slots(self) -> None:
        slots = build_answer_slots(
            active_subtask={
                "operation_family": "difference",
                "metric_label": "증감액",
                "required_operands": [
                    {"role": "current_period", "label": "당기"},
                    {"role": "prior_period", "label": "전기"},
                ],
            },
            operation_family="difference",
            ordered_operands=[
                {
                    "evidence_id": "row_current",
                    "label": "당기",
                    "matched_operand_role": "current_period",
                    "raw_value": "3",
                    "raw_unit": "%",
                    "normalized_value": 3.0,
                    "normalized_unit": "PERCENT",
                    "period": "2023",
                },
                {
                    "evidence_id": "row_prior",
                    "label": "전기",
                    "matched_operand_role": "prior_period",
                    "raw_value": "1",
                    "raw_unit": "%",
                    "normalized_value": 1.0,
                    "normalized_unit": "PERCENT",
                    "period": "2022",
                },
            ],
            result_value=2.0,
            result_unit="%p",
            normalized_unit="PERCENT",
            source_normalized_unit="PERCENT",
            current_value=3.0,
            prior_value=1.0,
            delta_value=2.0,
            current_period="2023",
            prior_period="2022",
            source_row_ids=["row_current", "row_prior"],
        )

        self.assertEqual(slots["operation_family"], "difference")
        self.assertEqual(slots["primary_value"]["role"], "delta_value")
        self.assertEqual(slots["current_value"]["rendered_value"], "3%")
        self.assertEqual(slots["prior_value"]["rendered_value"], "1%")
        self.assertEqual(slots["delta_value"]["rendered_value"], "2.00%p")
        self.assertEqual(slots["direction"], "increase")


if __name__ == "__main__":
    unittest.main()
