import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.financial_graph import _extract_composite_krw, _normalise_operand_value
from src.ops.evaluator import _extract_composite_krw_value, _normalise_math_operand_value


class CompositeKrwParsingTests(unittest.TestCase):
    def test_agent_parser_handles_spacing_variants(self) -> None:
        expected = 111_065_900_000_000.0
        cases = [
            "111조659억원",
            "111 조 659 억원",
            "111조  659억",
            "111조 659억 원",
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(_extract_composite_krw(case), expected)

    def test_evaluator_parser_handles_spacing_variants(self) -> None:
        expected = 111_065_900_000_000.0
        cases = [
            "111조659억원",
            "111 조 659 억원",
            "111조  659억",
            "111조 659억 원",
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertEqual(_extract_composite_krw_value(case), expected)

    def test_agent_normalization_prefers_composite_krw(self) -> None:
        value, unit = _normalise_operand_value("35조 215억원", "억원")
        self.assertEqual(unit, "KRW")
        self.assertEqual(value, 35_021_500_000_000.0)

    def test_evaluator_normalization_prefers_composite_krw(self) -> None:
        value, unit = _normalise_math_operand_value("35조 215억원", "억원")
        self.assertEqual(unit, "KRW")
        self.assertEqual(value, 35_021_500_000_000.0)


if __name__ == "__main__":
    unittest.main()
