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
    FinancialAgent,
    _build_semantic_numeric_plan,
    _extract_numeric_value_after_operand_text,
    _parse_unstructured_table_row_cells,
)


class SemanticNumericPlanTests(unittest.TestCase):
    def test_parse_unstructured_row_uses_header_context(self) -> None:
        cells = _parse_unstructured_table_row_cells(
            "법인세비용차감전순이익 | 1,481,396,318 | 1,083,717,091",
            {
                "table_header_context": "구분 | 2023년 | 2022년",
                "unit_hint": "천원",
            },
        )

        self.assertEqual(len(cells), 2)
        self.assertEqual(cells[0]["column_headers"], ["2023년"])
        self.assertEqual(cells[0]["value_text"], "1,481,396,318")
        self.assertEqual(cells[1]["column_headers"], ["2022년"])
        self.assertEqual(cells[1]["value_text"], "1,083,717,091")

    def test_fallback_builds_generic_task_for_year_over_year_metric(self) -> None:
        plan = _build_semantic_numeric_plan(
            query="2023년 연결 손익계산서에서 '법인세비용차감전순이익'을 추출하고, 전년 대비 증감액을 계산해 줘.",
            topic="법인세비용차감전순이익",
            intent="comparison",
            report_scope={"company": "네이버", "year": 2023, "report_type": "사업보고서"},
            target_metric_family="",
        )

        self.assertEqual(plan["status"], "heuristic_fallback")
        self.assertEqual(len(plan["tasks"]), 1)
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "generic_numeric")
        self.assertEqual(task["metric_label"], "법인세비용차감전순이익")
        operand_labels = [row["label"] for row in task["required_operands"]]
        self.assertEqual(
            operand_labels,
            ["2023년 법인세비용차감전순이익", "2022년 법인세비용차감전순이익"],
        )
        self.assertIn("income_statement", task["preferred_statement_types"])
        self.assertIn("연결 손익계산서", task["preferred_sections"])
        self.assertIn("법인세비용", task["preferred_sections"])

    def test_fallback_builds_explicit_operand_list_for_multi_operand_ratio(self) -> None:
        plan = _build_semantic_numeric_plan(
            query="2023년 연결 재무상태표에서 유·무형자산의 총합 대비 차입금(단기차입금, 장기차입금, 사채 합산)의 비중을 계산해 줘.",
            topic="유무형자산 대비 차입금 비중",
            intent="comparison",
            report_scope={"company": "SK하이닉스", "year": 2023, "report_type": "사업보고서", "consolidation": "연결"},
            target_metric_family="",
        )

        self.assertEqual(plan["status"], "heuristic_fallback")
        task = plan["tasks"][0]
        operand_labels = [row["label"] for row in task["required_operands"]]
        self.assertEqual(
            operand_labels,
            ["유형자산", "무형자산", "단기차입금", "장기차입금", "사채"],
        )
        self.assertIn("balance_sheet", task["preferred_statement_types"])
        self.assertIn("연결 재무상태표", task["preferred_sections"])
        self.assertIn("차입금 및 사채", task["preferred_sections"])
        self.assertIn("notes", task["preferred_statement_types"])

    def test_fallback_builds_explicit_operand_list_for_gain_loss_difference(self) -> None:
        plan = _build_semantic_numeric_plan(
            query="2023년 주석에서 외화환산이익과 외화환산손실 금액을 각각 찾고, 해당 연도의 환율 변동이 영업외수지에 미친 순효과(이익-손실)를 계산해 줘.",
            topic="외화환산손익",
            intent="comparison",
            report_scope={"company": "SK하이닉스", "year": 2023, "report_type": "사업보고서"},
            target_metric_family="",
        )

        self.assertEqual(plan["status"], "heuristic_fallback")
        task = plan["tasks"][0]
        operand_labels = [row["label"] for row in task["required_operands"]]
        self.assertEqual(operand_labels, ["외화환산이익", "외화환산손실"])
        self.assertIn("notes", task["preferred_statement_types"])
        self.assertIn("연결재무제표 주석", task["preferred_sections"])
        self.assertIn("cash_flow", task["preferred_statement_types"])
        self.assertIn("현금흐름표 (연결)", task["preferred_sections"])

    def test_component_only_false_positive_is_dropped_before_fallback(self) -> None:
        plan = _build_semantic_numeric_plan(
            query="2023년 손익계산서에서 '매출원가'와 '판매비와관리비'를 합산하여 '총 영업비용'을 구한 뒤, 전체 매출액 대비 영업비용률을 계산해 줘.",
            topic="총 영업비용 비율",
            intent="comparison",
            report_scope={"company": "현대자동차", "year": 2023, "report_type": "사업보고서"},
            target_metric_family="rnd_ratio",
        )

        self.assertEqual(plan["status"], "heuristic_fallback")
        self.assertIn("drop_weak_target:rnd_ratio", plan["planner_notes"])
        task = plan["tasks"][0]
        operand_labels = [row["label"] for row in task["required_operands"]]
        self.assertEqual(operand_labels, ["매출원가", "판매비와관리비", "매출액"])

    def test_extract_numeric_value_after_operand_text_handles_spaced_korean_text(self) -> None:
        value = _extract_numeric_value_after_operand_text(
            "회 사 채 | 13,189,950 | 7,467,594 | 5,722,356",
            {"label": "사채", "aliases": ["사채"]},
        )
        self.assertEqual(value, "13,189,950")

    def test_generic_operand_fallback_builds_rows_from_claim_text(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        rows = agent._build_required_operands_from_candidates(
            [
                {
                    "evidence_id": "ev_001",
                    "source_anchor": "[SK하이닉스 | 2023 | IV. 이사의 경영진단 및 분석의견]",
                    "claim": "2023년(제76기) 연결 재무상태표 상 유형자산은 52,704,853백만원입니다.",
                    "metadata": {
                        "statement_type": "mda",
                        "consolidation_scope": "consolidated",
                    },
                },
                {
                    "evidence_id": "ev_002",
                    "source_anchor": "[SK하이닉스 | 2023 | IV. 이사의 경영진단 및 분석의견]",
                    "claim": "2023년(제76기) 연결 재무상태표 상 무형자산은 3,834,567백만원입니다.",
                    "metadata": {
                        "statement_type": "mda",
                        "consolidation_scope": "consolidated",
                    },
                },
            ],
            required_operands=[
                {"label": "유형자산", "aliases": ["유형자산"]},
                {"label": "무형자산", "aliases": ["무형자산"]},
            ],
            query="2023년 연결 재무상태표에서 유·무형자산의 총합을 계산해 줘.",
            topic="유무형자산",
            report_scope={"company": "SK하이닉스", "year": 2023},
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["raw_value"], "52,704,853")
        self.assertEqual(rows[0]["raw_unit"], "백만원")
        self.assertEqual(rows[1]["raw_value"], "3,834,567")
        self.assertEqual(rows[1]["raw_unit"], "백만원")


if __name__ == "__main__":
    unittest.main()
