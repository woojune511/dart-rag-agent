import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.financial_graph import (
    _extract_composite_krw,
    _normalise_operand_value,
    _should_coerce_percent_point_unit,
)
from src.ops.evaluator import (
    _compute_operand_grounding_score,
    _extract_composite_krw_value,
    _extract_numeric_candidates,
    _normalise_math_operand_value,
    _numeric_values_equivalent,
)


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

    def test_currency_equivalence_allows_display_unit_rounding_gap(self) -> None:
        left = _extract_numeric_candidates("차이는 63조 8,217억원입니다.")[0]
        right = _extract_numeric_candidates("차이는 63조 8,218억원입니다.")[0]
        self.assertTrue(_numeric_values_equivalent(left, right))

    def test_currency_equivalence_still_rejects_large_gap(self) -> None:
        left = _extract_numeric_candidates("차이는 63조 8,217억원입니다.")[0]
        right = _extract_numeric_candidates("차이는 63조 8,220억원입니다.")[0]
        self.assertFalse(_numeric_values_equivalent(left, right))

    def test_percent_point_query_coerces_result_unit(self) -> None:
        operands = [
            {"operand_id": "op_001", "normalized_unit": "PERCENT"},
            {"operand_id": "op_002", "normalized_unit": "PERCENT"},
        ]
        plan = {
            "mode": "single_value",
            "operation": "subtract",
            "ordered_operand_ids": ["op_001", "op_002"],
            "formula": "A - B",
            "result_unit": "%",
        }
        self.assertTrue(
            _should_coerce_percent_point_unit(
                "2024년과 2023년의 연구개발비 / 매출액 비중 차이는 몇 %p인가요?",
                operands,
                plan,
            )
        )

    def test_operand_grounding_score_passes_for_grounded_comparison_operands(self) -> None:
        runtime_evidence = [
            {
                "source_anchor": "[삼성전자 | 2024 | IV. 이사의 경영진단 및 분석의견]",
                "claim": "2024년 DX 부문의 매출은 174조 8,877억원이고 DS 부문의 매출은 111조 659억 5천만원입니다.",
                "quote_span": "매출 | DX 부문 | 174,887,683 | DS 부문 | 111,065,950",
            }
        ]
        contexts = [
            "구분 | 부문 | 제56기 | 제55기 | 증감(률) 매출 | DX 부문 | 174,887,683 | DS 부문 | 111,065,950"
        ]
        operands = [
            {
                "operand_id": "op_001",
                "label": "DX부문 매출",
                "raw_value": "174조 8,877억원",
                "raw_unit": "원",
                "normalized_value": 174_887_700_000_000.0,
                "normalized_unit": "KRW",
                "period": "2024년",
                "source_anchor": "[삼성전자 | 2024 | IV. 이사의 경영진단 및 분석의견]",
            },
            {
                "operand_id": "op_002",
                "label": "DS부문 매출",
                "raw_value": "111조 659억 5천만원",
                "raw_unit": "원",
                "normalized_value": 111_065_900_000_000.0,
                "normalized_unit": "KRW",
                "period": "2024년",
                "source_anchor": "[삼성전자 | 2024 | IV. 이사의 경영진단 및 분석의견]",
            },
        ]
        score, debug = _compute_operand_grounding_score(
            runtime_evidence=runtime_evidence,
            contexts=contexts,
            calculation_operands=operands,
        )
        self.assertEqual(score, 1.0)
        self.assertEqual(len(debug["matched_operands"]), 2)
        self.assertEqual(len(debug["unmatched_operands"]), 0)

    def test_operand_grounding_score_is_partial_when_one_operand_is_missing(self) -> None:
        runtime_evidence = [
            {
                "source_anchor": "[삼성전자 | 2024 | IV. 이사의 경영진단 및 분석의견]",
                "claim": "2024년 DX 부문의 매출은 174조 8,877억원입니다.",
                "quote_span": "매출 | DX 부문 | 174,887,683",
            }
        ]
        contexts = ["매출 | DX 부문 | 174,887,683"]
        operands = [
            {
                "operand_id": "op_001",
                "label": "DX부문 매출",
                "raw_value": "174조 8,877억원",
                "raw_unit": "원",
                "normalized_value": 174_887_700_000_000.0,
                "normalized_unit": "KRW",
                "period": "2024년",
            },
            {
                "operand_id": "op_002",
                "label": "DS부문 매출",
                "raw_value": "111조 659억 5천만원",
                "raw_unit": "원",
                "normalized_value": 111_065_900_000_000.0,
                "normalized_unit": "KRW",
                "period": "2024년",
            },
        ]
        score, debug = _compute_operand_grounding_score(
            runtime_evidence=runtime_evidence,
            contexts=contexts,
            calculation_operands=operands,
        )
        self.assertEqual(score, 0.5)
        self.assertEqual(len(debug["matched_operands"]), 1)
        self.assertEqual(len(debug["unmatched_operands"]), 1)

    def test_operand_grounding_score_handles_unitless_table_cells_with_implied_scale(self) -> None:
        runtime_evidence = [
            {
                "source_anchor": "[삼성전자 | 2024 | IV. 이사의 경영진단 및 분석의견]",
                "claim": "삼성전자의 2024년 연결기준 영업이익은 32조 7,260억원으로 2023년 대비 26조 1,590억원(398.3%) 증가했습니다.",
                "quote_span": "영업이익 | 32,725,961 | 6,566,976 | 26,158,985 | 398.3%",
            }
        ]
        operands = [
            {
                "operand_id": "op_001",
                "label": "2024년 영업이익",
                "raw_value": "32조 7,260억원",
                "raw_unit": "원",
                "normalized_value": 32_726_000_000_000.0,
                "normalized_unit": "KRW",
                "period": "2024년",
            },
            {
                "operand_id": "op_002",
                "label": "2023년 영업이익",
                "raw_value": "6조 5,670억원",
                "raw_unit": "원",
                "normalized_value": 6_567_000_000_000.0,
                "normalized_unit": "KRW",
                "period": "2023년",
            },
        ]
        score, debug = _compute_operand_grounding_score(
            runtime_evidence=runtime_evidence,
            contexts=[],
            calculation_operands=operands,
        )
        self.assertEqual(score, 1.0)
        self.assertEqual(len(debug["matched_operands"]), 2)


if __name__ == "__main__":
    unittest.main()
