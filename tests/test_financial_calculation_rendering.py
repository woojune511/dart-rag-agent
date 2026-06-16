import unittest

from src.agent.financial_graph_calculation_rendering import (
    coerce_rendered_value_for_direction,
    direction_hint_for_result,
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


if __name__ == "__main__":
    unittest.main()
