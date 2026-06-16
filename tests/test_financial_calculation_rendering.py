import unittest

from src.agent.financial_graph_calculation_rendering import (
    coerce_rendered_value_for_direction,
    direction_hint_for_result,
    scalar_result_display,
)


class FinancialCalculationRenderingTests(unittest.TestCase):
    def test_direction_hint_for_result_uses_operation_policy(self) -> None:
        policy = {
            "direction_hints": {
                "subtract": {
                    "positive": "positive hint",
                    "negative": "negative hint",
                    "zero": "zero hint",
                }
            }
        }

        self.assertEqual(
            direction_hint_for_result(operation="subtract", result_value=1.0, render_policy=policy),
            "positive hint",
        )
        self.assertEqual(
            direction_hint_for_result(operation="subtract", result_value=-1.0, render_policy=policy),
            "negative hint",
        )
        self.assertEqual(
            direction_hint_for_result(operation="subtract", result_value=0.0, render_policy=policy),
            "zero hint",
        )
        self.assertEqual(
            direction_hint_for_result(operation="divide", result_value=1.0, render_policy=policy),
            "",
        )

    def test_coerce_rendered_value_for_direction_strips_duplicate_negative_sign(self) -> None:
        result = coerce_rendered_value_for_direction(
            {"rendered_value": "-123"},
            direction_hint="negative hint",
            result_value=-123.0,
        )

        self.assertEqual(result["rendered_value"], "123")

    def test_coerce_rendered_value_for_direction_keeps_value_without_direction_hint(self) -> None:
        result = coerce_rendered_value_for_direction(
            {"rendered_value": "-123"},
            direction_hint="",
            result_value=-123.0,
        )

        self.assertEqual(result["rendered_value"], "-123")

    def test_scalar_result_display_uses_krw_display_unit_when_available(self) -> None:
        result = scalar_result_display(
            result_value=1_000_000.0,
            result_unit="",
            normalized_unit="KRW",
            result_display_unit="백만원",
        )

        self.assertEqual(result["rendered_value"], "1백만원")
        self.assertEqual(result["rendered_with_unit"], "1백만원")
        self.assertEqual(result["result_display_unit"], "백만원")

    def test_scalar_result_display_appends_non_krw_result_unit(self) -> None:
        result = scalar_result_display(
            result_value=12.345,
            result_unit="%",
            normalized_unit="PERCENT",
        )

        self.assertEqual(result["rendered_value"], "12.35")
        self.assertEqual(result["rendered_with_unit"], "12.35%")

    def test_scalar_result_display_preserves_grounded_lookup_display(self) -> None:
        result = scalar_result_display(
            result_value=100_000_000.0,
            result_unit="",
            normalized_unit="KRW",
            operation_family="lookup",
            ordered_operands=[
                {
                    "raw_value": "100",
                    "raw_unit": "백만원",
                    "normalized_value": 100_000_000.0,
                    "normalized_unit": "KRW",
                    "rendered_value": "100백만원",
                    "value_coercion": True,
                }
            ],
        )

        self.assertEqual(result["rendered_value"], "100백만원")
        self.assertEqual(result["rendered_with_unit"], "100백만원")


if __name__ == "__main__":
    unittest.main()
