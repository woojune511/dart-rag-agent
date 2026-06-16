import unittest

from src.agent.financial_answer_slots import (
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


if __name__ == "__main__":
    unittest.main()
