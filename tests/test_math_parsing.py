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
    EvalExample,
    _compute_numeric_equivalence,
    _compute_numeric_evaluation,
    _compute_operand_selection_correctness,
    _compute_operand_grounding_score,
    _extract_composite_krw_value,
    _extract_numeric_candidates,
    _normalise_math_operand_value,
    _normalise_period_text,
    _numeric_values_equivalent,
)


class _ExplodingLLM:
    def invoke(self, _prompt):
        raise AssertionError("LLM should be skipped in deterministic numeric fast gate")


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

    def test_agent_normalization_handles_scaled_count_units(self) -> None:
        cases = [
            ("87.0", "만 대", 870_000.0),
            ("78.1만대", "", 781_000.0),
            ("1.2", "백만 개", 1_200_000.0),
        ]
        for raw_value, raw_unit, expected in cases:
            with self.subTest(raw_value=raw_value, raw_unit=raw_unit):
                value, unit = _normalise_operand_value(raw_value, raw_unit)
                self.assertEqual(unit, "COUNT")
                self.assertEqual(value, expected)

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

    def test_percent_equivalence_allows_small_formula_rounding_gap(self) -> None:
        left = _extract_numeric_candidates("증가율은 70.24%입니다.")[0]
        right = _extract_numeric_candidates("증가율은 약 70.28%입니다.")[0]
        self.assertTrue(_numeric_values_equivalent(left, right))

    def test_ratio_equivalence_allows_display_rounding_gap(self) -> None:
        left = _extract_numeric_candidates("coverage ratio is 3.5269배입니다.")[0]
        right = _extract_numeric_candidates("coverage ratio is approximately 3.53배입니다.")[0]

        self.assertTrue(_numeric_values_equivalent(left, right))

    def test_numeric_equivalence_rejects_extra_unsupported_answer_number(self) -> None:
        score, debug = _compute_numeric_equivalence(
            answer="이익은 (573,884)백만원이고 손실은 906,120백만원이며 순효과는 -1조 4,800억원입니다.",
            answer_key="이익은 573,884백만원이고 손실은 906,120백만원이며 순효과는 -332,236백만원입니다.",
            canonical_evidence=[],
        )

        self.assertEqual(score, 0.0)
        self.assertEqual(debug["reason"], "unsupported_answer_numeric_claim")
        self.assertIn("1조 4,800억원", [item["value_text"] for item in debug["unsupported_answer_candidates"]])

    def test_numeric_equivalence_allows_runtime_supported_auxiliary_numbers(self) -> None:
        score, debug = _compute_numeric_equivalence(
            answer="전년 대비 약 70.24% 증가했고, 고정이하여신비율은 1.01%입니다.",
            answer_key="전년 대비 증가율은 약 70.28%입니다.",
            canonical_evidence=[],
            support_texts=[
                "고정이하여신비율은 1.01%(전년대비 0.31%p 상승) 시현하였습니다.",
            ],
        )

        self.assertEqual(score, 1.0)
        self.assertEqual(debug["reason"], "equivalent_value")
        self.assertEqual(debug["unsupported_answer_candidates"], [])

    def test_numeric_equivalence_requires_all_multi_value_answer_claims_to_match(self) -> None:
        score, debug = _compute_numeric_equivalence(
            answer="재고자산평가손실은 (1,124,562,480,391)원, 환입은 (106,656)천원, 폐기손실은 25,163,510천원입니다.",
            answer_key="재고자산평가손실 2,526,280천원, 환입 48,885,812천원, 폐기손실 25,163,510천원입니다.",
            canonical_evidence=[],
        )

        self.assertEqual(score, 0.0)
        self.assertEqual(debug["reason"], "unsupported_answer_numeric_claim")

    def test_numeric_fast_gate_skips_llm_grounding_when_operands_are_grounded(self) -> None:
        example = EvalExample(
            id="comparison_002",
            question="SDC와 Harman 부문 매출 합계를 계산해 줘.",
            ground_truth="합계는 43조 4,327억원이다.",
            answer_key="합계는 43조 4,327억원이다.",
            company="삼성전자",
            year=2024,
            section="연결재무제표 주석",
            answer_type="numeric",
            category="comparison",
        )
        runtime_evidence = [
            {
                "claim": "매출액 | SDC 29,157,820 백만원 | Harman 14,274,930 백만원",
                "quote_span": "SDC 29,157,820 백만원 | Harman 14,274,930 백만원",
                "metadata": {"company": "삼성전자", "year": 2024},
            }
        ]
        calculation_operands = [
            {
                "label": "SDC 매출액",
                "raw_value": "29,157,820",
                "raw_unit": "백만원",
                "normalized_value": 29_157_820_000_000.0,
                "normalized_unit": "KRW",
            },
            {
                "label": "Harman 매출액",
                "raw_value": "14,274,930",
                "raw_unit": "백만원",
                "normalized_value": 14_274_930_000_000.0,
                "normalized_unit": "KRW",
            },
        ]

        result = _compute_numeric_evaluation(
            llm=_ExplodingLLM(),
            example=example,
            answer="합계는 43조 4,327억원입니다.",
            runtime_evidence=runtime_evidence,
            contexts=[],
            calculation_operands=calculation_operands,
            retrieval_hit_at_k=1.0,
            deterministic_grounding_only=True,
        )

        self.assertEqual(result["numeric_final_judgement"], "PASS")
        self.assertEqual(result["numeric_grounding"], 1.0)

    def test_numeric_fast_gate_does_not_call_llm_when_operand_grounding_is_unavailable(self) -> None:
        example = EvalExample(
            id="numeric_debug",
            question="계산 결과를 확인해 줘.",
            ground_truth="정답은 10이다.",
            answer_key="정답은 10이다.",
            company="테스트",
            year=2024,
            section="",
            answer_type="numeric",
            category="comparison",
        )

        result = _compute_numeric_evaluation(
            llm=_ExplodingLLM(),
            example=example,
            answer="정답은 10입니다.",
            runtime_evidence=[],
            contexts=[],
            calculation_operands=[],
            retrieval_hit_at_k=0.0,
            deterministic_grounding_only=True,
        )

        self.assertEqual(result["numeric_final_judgement"], "UNCERTAIN")
        self.assertIsNone(result["numeric_grounding"])
        self.assertTrue(result["numeric_debug"]["grounding"]["llm_skipped"])

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

    def test_operand_grounding_score_handles_unitless_percent_table_cells(self) -> None:
        runtime_evidence = [
            {
                "source_anchor": "[KB금융 | 2023 | II. 사업의 내용 > 2. 영업의 현황]",
                "claim": "명목순이자마진(NIM) | 명목순이자마진(NIM) | 1.83 | 1.73 | 1.58",
                "quote_span": "명목순이자마진(NIM) | 명목순이자마진(NIM) | 1.83 | 1.73 | 1.58",
                "raw_row_text": "명목순이자마진(NIM) | 명목순이자마진(NIM) | 1.83 | 1.73 | 1.58",
            }
        ]
        operands = [
            {
                "operand_id": "op_001",
                "label": "2023년 NIM",
                "raw_value": "1.83",
                "raw_unit": "%",
                "normalized_value": 1.83,
                "normalized_unit": "PERCENT",
                "period": "2023년",
            },
            {
                "operand_id": "op_002",
                "label": "2022년 NIM",
                "raw_value": "1.73",
                "raw_unit": "%",
                "normalized_value": 1.73,
                "normalized_unit": "PERCENT",
                "period": "2022년",
            },
        ]
        score, debug = _compute_operand_grounding_score(
            runtime_evidence=runtime_evidence,
            contexts=[],
            calculation_operands=operands,
        )
        self.assertEqual(score, 1.0)
        self.assertEqual(len(debug["matched_operands"]), 2)
        self.assertEqual(len(debug["unmatched_operands"]), 0)

    def test_operand_grounding_score_accepts_resolved_direct_operand_when_corpus_is_sparse(self) -> None:
        runtime_evidence = []
        contexts = []
        operands = [
            {
                "operand_id": "op_001",
                "label": "2023 매출원가",
                "concept": "cost_of_sales",
                "period": "2023",
                "raw_value": "129,179,183",
                "raw_unit": "백만원",
                "normalized_value": 129_179_183_000_000.0,
                "normalized_unit": "KRW",
                "source_row_id": "20240313001451:54:1::value:3",
                "source_anchor": "[현대자동차 | 2023 | III. 재무에 관한 사항 > 2. 연결재무제표]",
            }
        ]

        score, debug = _compute_operand_grounding_score(
            runtime_evidence=runtime_evidence,
            contexts=contexts,
            calculation_operands=operands,
        )

        self.assertEqual(score, 1.0)
        self.assertEqual(len(debug["matched_operands"]), 1)
        self.assertEqual(debug["matched_operands"][0]["matched_source"], "resolved_operand")
        self.assertEqual(len(debug["unmatched_operands"]), 0)

    def test_operand_selection_correctness_allows_period_and_value_alias_match(self) -> None:
        expected_operands = [
            {"label": "2023년 NIM", "period": "2023", "raw_value": "1.83", "raw_unit": "%"},
            {"label": "2022년 NIM", "period": "2022", "raw_value": "1.73", "raw_unit": "%"},
        ]
        calculation_operands = [
            {
                "label": "2023 순이자마진",
                "period": "2023",
                "normalized_value": 1.83,
                "normalized_unit": "PERCENT",
            },
            {
                "label": "2022 순이자마진",
                "period": "2022",
                "normalized_value": 1.73,
                "normalized_unit": "PERCENT",
            },
        ]
        score = _compute_operand_selection_correctness(
            type("Example", (), {"expected_operands": expected_operands})(),
            calculation_operands,
        )
        self.assertEqual(score, 1.0)

    def test_operand_selection_correctness_normalises_year_suffix_in_periods(self) -> None:
        expected_operands = [
            {"label": "영업비용 합계", "period": "2023년", "raw_value": "8,181,823,307", "raw_unit": "천원"},
            {"label": "종업원급여", "period": "2023년", "raw_value": "1,701,418,940", "raw_unit": "천원"},
        ]
        calculation_operands = [
            {
                "label": "2023 영업비용",
                "period": "2023",
                "normalized_value": 8_181_823_307_000.0,
                "normalized_unit": "KRW",
                "raw_value": "8,181,823,307",
                "raw_unit": "천원",
            },
            {
                "label": "2023 종업원급여",
                "period": "2023",
                "normalized_value": 1_701_418_940_000.0,
                "normalized_unit": "KRW",
                "raw_value": "1,701,418,940",
                "raw_unit": "천원",
            },
        ]
        score = _compute_operand_selection_correctness(
            type("Example", (), {"expected_operands": expected_operands})(),
            calculation_operands,
        )
        self.assertEqual(score, 1.0)

    def test_normalise_period_text_collapses_year_suffix(self) -> None:
        self.assertEqual(_normalise_period_text("2023년"), "2023")
        self.assertEqual(_normalise_period_text("2023"), "2023")


if __name__ == "__main__":
    unittest.main()
