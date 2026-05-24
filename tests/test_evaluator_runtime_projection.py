import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.evaluator import (
    _build_example_report_scope,
    _compute_numeric_result_correctness,
    _numeric_values_equivalent,
    _operand_matches,
    EvalExample,
    _resolve_evaluator_operands,
    _resolve_runtime_calculation_trace,
    _should_override_numeric_grounding,
)


class EvaluatorRuntimeProjectionTests(unittest.TestCase):
    def test_should_override_numeric_grounding_for_direct_composed_ratio(self) -> None:
        numeric_eval = {
            "numeric_equivalence": 1.0,
            "numeric_grounding": 0.0,
            "numeric_retrieval_support": 1.0,
        }
        calculation_operands = [
            {
                "label": "매출원가",
                "source_row_id": "row_cost",
                "source_anchor": "연결 손익계산서",
            },
            {
                "label": "판매비와관리비",
                "source_row_id": "row_sga",
                "source_anchor": "연결 손익계산서",
            },
            {
                "label": "매출액",
                "source_row_id": "row_revenue",
                "source_anchor": "연결 손익계산서",
            },
        ]

        self.assertTrue(
            _should_override_numeric_grounding(
                numeric_eval=numeric_eval,
                calculation_operands=calculation_operands,
                operand_selection_correctness=1.0,
                numeric_result_correctness=1.0,
                grounded_rendering_correctness=1.0,
            )
        )

    def test_should_not_override_numeric_grounding_for_task_output_only_operands(self) -> None:
        numeric_eval = {
            "numeric_equivalence": 1.0,
            "numeric_grounding": 0.0,
            "numeric_retrieval_support": 1.0,
        }
        calculation_operands = [
            {
                "label": "매출원가",
                "source_row_id": "task_output:task_2",
                "source_anchor": "연결 손익계산서",
            }
        ]

        self.assertFalse(
            _should_override_numeric_grounding(
                numeric_eval=numeric_eval,
                calculation_operands=calculation_operands,
                operand_selection_correctness=1.0,
                numeric_result_correctness=1.0,
                grounded_rendering_correctness=1.0,
            )
        )

    def test_should_override_numeric_grounding_when_numeric_result_is_unavailable(self) -> None:
        numeric_eval = {
            "numeric_equivalence": 1.0,
            "numeric_grounding": 0.0,
            "numeric_retrieval_support": 1.0,
        }
        calculation_operands = [
            {
                "label": "매출액",
                "source_row_id": "row_revenue",
                "source_anchor": "연결 손익계산서",
            }
        ]

        self.assertTrue(
            _should_override_numeric_grounding(
                numeric_eval=numeric_eval,
                calculation_operands=calculation_operands,
                operand_selection_correctness=1.0,
                numeric_result_correctness=None,
                grounded_rendering_correctness=1.0,
            )
        )

    def test_build_example_report_scope_preserves_multi_report_inventory(self) -> None:
        example = EvalExample(
            id="sam_t2_002",
            question="2023년 CAPEX 총액과 전년 대비 증감률은?",
            ground_truth="53조 1,139억원, 전년과 거의 동일",
            company="삼성전자",
            year=2023,
            section="시설투자",
            source_reports=[
                {
                    "corp_name": "삼성전자",
                    "year": 2023,
                    "report_type": "사업보고서",
                    "rcept_no": "20240312000736",
                },
                {
                    "corp_name": "삼성전자",
                    "year": 2022,
                    "report_type": "사업보고서",
                    "rcept_no": "20230308000592",
                },
            ],
        )

        scope = _build_example_report_scope(example)

        self.assertEqual(scope["company"], "삼성전자")
        self.assertEqual(scope["year"], 2023)
        self.assertEqual(scope["report_type"], "사업보고서")
        self.assertNotIn("rcept_no", scope)
        self.assertEqual(len(scope["source_reports"]), 2)

    def test_build_example_report_scope_keeps_single_receipt_scope(self) -> None:
        example = EvalExample(
            id="nav_t1_071",
            question="2023년 법인세비용차감전순이익과 전년 대비 증감액은?",
            ground_truth="1조 4,814억원, 3,977억원 증가",
            company="네이버",
            year=2023,
            section="손익계산서",
            source_report={
                "corp_name": "네이버",
                "year": 2023,
                "report_type": "사업보고서",
                "rcept_no": "20240314002112",
            },
        )

        scope = _build_example_report_scope(example)

        self.assertEqual(scope["company"], "네이버")
        self.assertEqual(scope["year"], 2023)
        self.assertEqual(scope["report_type"], "사업보고서")
        self.assertEqual(scope["rcept_no"], "20240314002112")

    def test_resolve_runtime_trace_prefers_aggregate_subtasks(self) -> None:
        result = {
            "answer": "부채비율은 25.4%입니다. 유동비율은 258.8%입니다.",
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "debt_ratio",
                    "metric_label": "부채비율",
                    "answer": "부채비율은 25.4%입니다.",
                    "status": "ok",
                    "calculation_operands": [
                        {"row_id": "debt", "label_kr": "부채총계", "value": "92228115"},
                        {"row_id": "equity", "label_kr": "자본총계", "value": "363677865"},
                    ],
                    "calculation_plan": {"status": "ok", "operation": "divide"},
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "25.4%",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "primary_value": {"rendered_value": "25.4%"},
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "current_ratio",
                    "metric_label": "유동비율",
                    "answer": "유동비율은 258.8%입니다.",
                    "status": "ok",
                    "calculation_operands": [
                        {"row_id": "current_assets", "label_kr": "유동자산", "value": "137621922"},
                        {"row_id": "current_liabilities", "label_kr": "유동부채", "value": "53186439"},
                    ],
                    "calculation_plan": {"status": "ok", "operation": "divide"},
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "258.8%",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "primary_value": {"rendered_value": "258.8%"},
                        },
                    },
                },
            ],
        }

        trace = _resolve_runtime_calculation_trace(result)

        self.assertEqual(len(trace["calculation_operands"]), 4)
        self.assertEqual(trace["calculation_plan"]["mode"], "aggregate_subtasks")
        self.assertEqual(trace["calculation_result"]["formatted_result"], result["answer"])
        self.assertEqual(
            trace["calculation_result"]["derived_metrics"]["subtask_ids"],
            ["task_1", "task_2"],
        )
        self.assertEqual(
            trace["calculation_result"]["answer_slots"]["operation_family"],
            "aggregate_subtasks",
        )

    def test_resolve_runtime_trace_can_project_single_task_from_ledger(self) -> None:
        result = {
            "answer": "2023년 연결기준 부채비율은 25.4%입니다.",
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "active_subtask": {"task_id": "task_1"},
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "status": "completed",
                    "artifact_ids": ["artifact:001", "artifact:002", "artifact:003"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:001",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"row_id": "debt", "label_kr": "부채총계", "value": "92228115"},
                            {"row_id": "equity", "label_kr": "자본총계", "value": "363677865"},
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:002",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {"status": "ok", "operation": "divide"}
                    },
                },
                {
                    "artifact_id": "artifact:003",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "payload": {
                        "calculation_result": {"status": "ok", "rendered_value": "25.4%"}
                    },
                },
            ],
        }

        trace = _resolve_runtime_calculation_trace(result)

        self.assertEqual(len(trace["calculation_operands"]), 2)
        self.assertEqual(trace["calculation_plan"]["operation"], "divide")
        self.assertEqual(trace["calculation_result"]["rendered_value"], "25.4%")

    def test_resolve_runtime_trace_prefers_explicit_structured_contract(self) -> None:
        result = {
            "calculation_operands": [{"label": "stale", "value": "999"}],
            "calculation_plan": {"status": "stale"},
            "calculation_result": {"status": "stale", "rendered_value": "999"},
            "resolved_calculation_trace": {
                "calculation_operands": [{"label": "fresh", "value": "123"}],
                "calculation_plan": {"status": "ok", "operation": "lookup"},
                "calculation_result": {"status": "ok", "rendered_value": "123"},
            },
            "structured_result": {"status": "ok", "rendered_value": "123"},
        }

        trace = _resolve_runtime_calculation_trace(result)

        self.assertEqual(trace["calculation_operands"], [{"label": "fresh", "value": "123"}])
        self.assertEqual(trace["calculation_plan"]["operation"], "lookup")
        self.assertEqual(trace["calculation_result"]["rendered_value"], "123")

    def test_resolve_evaluator_operands_prefers_answer_slots_components(self) -> None:
        operands = [
            {"operand_id": "legacy", "label": "legacy", "raw_value": "999", "raw_unit": "%"},
        ]
        calculation_result = {
            "status": "ok",
            "answer_slots": {
                "operation_family": "difference",
                "components_by_role": {
                    "current_period": [
                        {
                            "status": "ok",
                            "role": "current_period",
                            "label": "2023 명목순이자마진(NIM)",
                            "concept": "net_interest_margin",
                            "period": "2023",
                            "raw_value": "1.83",
                            "raw_unit": "%",
                            "normalized_value": 1.83,
                            "normalized_unit": "PERCENT",
                            "rendered_value": "1.83%",
                            "source_row_id": "row_2023",
                            "source_row_ids": ["row_2023"],
                            "source_anchor": "표 A",
                        }
                    ],
                    "prior_period": [
                        {
                            "status": "ok",
                            "role": "prior_period",
                            "label": "2022 명목순이자마진(NIM)",
                            "concept": "net_interest_margin",
                            "period": "2022",
                            "raw_value": "1.73",
                            "raw_unit": "%",
                            "normalized_value": 1.73,
                            "normalized_unit": "PERCENT",
                            "rendered_value": "1.73%",
                            "source_row_id": "row_2022",
                            "source_row_ids": ["row_2022"],
                            "source_anchor": "표 A",
                        }
                    ],
                },
            },
        }

        resolved = _resolve_evaluator_operands(operands, calculation_result)

        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[0]["source_row_id"], "row_2023")
        self.assertEqual(resolved[0]["normalized_value"], 1.83)
        self.assertEqual(resolved[1]["source_row_id"], "row_2022")
        self.assertEqual(resolved[1]["normalized_value"], 1.73)

    def test_resolve_evaluator_operands_flattens_aggregate_subtask_answer_slots(self) -> None:
        operands = [
            {"operand_id": "stale_current", "label": "2023 시설투자(CAPEX)", "raw_value": "531,139", "raw_unit": "억원"},
            {"operand_id": "stale_prior", "label": "2022 시설투자(CAPEX)", "raw_value": "531,153", "raw_unit": ""},
        ]
        calculation_result = {
            "status": "ok",
            "answer_slots": {
                "operation_family": "aggregate_subtasks",
                "subtask_results": [
                    {
                        "task_id": "task_1",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2023 시설투자(CAPEX)",
                                "concept": "capital_expenditure_total",
                                "period": "2023",
                                "raw_value": "531,139",
                                "raw_unit": "억원",
                                "normalized_value": 53113900000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "53조 1,139억원",
                                "source_row_id": "row_2023",
                                "source_row_ids": ["row_2023"],
                                "source_anchor": "표 A",
                            },
                        },
                    },
                    {
                        "task_id": "task_2",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "components_by_role": {
                                "current_period": [
                                    {
                                        "status": "ok",
                                        "role": "current_period",
                                        "label": "2023 시설투자(CAPEX)",
                                        "concept": "capital_expenditure_total",
                                        "period": "2023",
                                        "raw_value": "531,139",
                                        "raw_unit": "억원",
                                        "normalized_value": 53113900000000.0,
                                        "normalized_unit": "KRW",
                                        "rendered_value": "53조 1,139억원",
                                        "source_row_id": "row_2023",
                                        "source_row_ids": ["row_2023"],
                                        "source_anchor": "표 A",
                                    }
                                ],
                                "prior_period": [
                                    {
                                        "status": "ok",
                                        "role": "prior_period",
                                        "label": "2022 시설투자(CAPEX)",
                                        "concept": "capital_expenditure_total",
                                        "period": "2022",
                                        "raw_value": "531,153",
                                        "raw_unit": "억원",
                                        "normalized_value": 53115300000000.0,
                                        "normalized_unit": "KRW",
                                        "rendered_value": "53조 1,153억원",
                                        "source_row_id": "row_2022",
                                        "source_row_ids": ["row_2022"],
                                        "source_anchor": "표 A",
                                    }
                                ],
                            },
                        },
                    },
                ],
            },
        }

        resolved = _resolve_evaluator_operands(operands, calculation_result)

        self.assertEqual(len(resolved), 2)
        self.assertEqual(resolved[0]["source_row_id"], "row_2023")
        self.assertEqual(resolved[1]["source_row_id"], "row_2022")

    def test_resolve_evaluator_operands_dedupes_task_output_duplicates(self) -> None:
        calculation_result = {
            "status": "ok",
            "answer_slots": {
                "operation_family": "ratio",
                "components_by_role": {
                    "numerator_1": [
                        {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "2023 매출원가",
                            "concept": "cost_of_sales",
                            "period": "2023",
                            "raw_value": "129,179,183",
                            "raw_unit": "백만원",
                            "normalized_value": 129179183000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "129조 1,792억원",
                            "source_row_id": "row_cost",
                            "source_row_ids": ["row_cost"],
                            "source_anchor": "연결 손익계산서",
                        },
                        {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "매출원가",
                            "concept": "cost_of_sales",
                            "period": "2023",
                            "raw_value": "129,179,183",
                            "raw_unit": "백만원",
                            "normalized_value": 129179183000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "129조 1,792억원",
                            "source_row_id": "task_output:task_2",
                            "source_row_ids": ["task_output:task_2"],
                            "source_anchor": "연결 손익계산서",
                        },
                    ],
                },
            },
        }

        resolved = _resolve_evaluator_operands([], calculation_result)

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["source_row_id"], "row_cost")
        self.assertEqual(resolved[0]["normalized_unit"], "KRW")

    def test_resolve_evaluator_operands_dedupes_aggregate_subtask_duplicates(self) -> None:
        calculation_result = {
            "status": "ok",
            "answer_slots": {
                "operation_family": "aggregate_subtasks",
                "subtask_results": [
                    {
                        "task_id": "task_2",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "components_by_role": {
                                "numerator_1": [
                                    {
                                        "status": "ok",
                                        "role": "numerator_1",
                                        "label": "2023 매출원가",
                                        "concept": "cost_of_sales",
                                        "period": "2023",
                                        "raw_value": "129,179,183",
                                        "raw_unit": "백만원",
                                        "normalized_value": 129179183000000.0,
                                        "normalized_unit": "KRW",
                                        "source_row_id": "row_cost",
                                        "source_anchor": "연결 손익계산서",
                                    }
                                ],
                            },
                        },
                    },
                    {
                        "task_id": "task_1",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "components_by_role": {
                                "numerator_1": [
                                    {
                                        "status": "ok",
                                        "role": "numerator_1",
                                        "label": "매출원가",
                                        "concept": "cost_of_sales",
                                        "period": "2023",
                                        "raw_value": "129,179,183",
                                        "raw_unit": "백만원",
                                        "normalized_value": 129179183000000.0,
                                        "normalized_unit": "KRW",
                                        "source_row_id": "task_output:task_2",
                                        "source_anchor": "연결 손익계산서",
                                    }
                                ],
                            },
                        },
                    },
                ],
            },
        }

        resolved = _resolve_evaluator_operands([], calculation_result)

        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["source_row_id"], "row_cost")

    def test_numeric_result_correctness_can_use_answer_slots_primary_value(self) -> None:
        example = EvalExample(
            id="T",
            question="2023년 KB금융의 순이자마진은?",
            ground_truth="1.83%",
            company="KB금융",
            year=2023,
            section="II. 사업의 내용",
            category="numeric_fact",
            answer_key="1.83%",
            evidence=[],
            answer_type="numeric",
            expected_calculation_result={
                "normalized_value": 1.83,
                "normalized_unit": "PERCENT",
                "tolerance": 0.0,
            },
        )
        calculation_result = {
            "status": "ok",
            "result_value": None,
            "answer_slots": {
                "operation_family": "lookup",
                "primary_value": {
                    "status": "ok",
                    "role": "primary_value",
                    "label": "명목순이자마진(NIM)",
                    "concept": "net_interest_margin",
                    "period": "2023",
                    "raw_value": "1.83",
                    "raw_unit": "%",
                    "normalized_value": 1.83,
                    "normalized_unit": "PERCENT",
                    "rendered_value": "1.83%",
                    "source_row_id": "row_1",
                    "source_row_ids": ["row_1"],
                    "source_anchor": "표 A",
                },
            },
        }

        score = _compute_numeric_result_correctness(example, calculation_result)

        self.assertEqual(score, 1.0)

    def test_numeric_result_correctness_can_use_aggregate_subtask_primary_value(self) -> None:
        example = EvalExample(
            id="mix_t1_064",
            question="영업비용률은?",
            ground_truth="90.7%",
            company="현대자동차",
            year=2023,
            section="연결 손익계산서",
            category="numeric_fact",
            answer_key="90.7%",
            evidence=[],
            answer_type="numeric",
            expected_calculation_result={
                "normalized_value": 90.7004990957441,
                "normalized_unit": "PERCENT",
                "tolerance": 0.0,
            },
        )
        calculation_result = {
            "status": "ok",
            "result_value": None,
            "answer_slots": {
                "operation_family": "aggregate_subtasks",
                "subtask_results": [
                    {
                        "task_id": "task_1",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "영업비용률",
                                "normalized_value": 90.7004990957441,
                                "normalized_unit": "PERCENT",
                                "rendered_value": "90.7%",
                            },
                        },
                    }
                ],
            },
        }

        score = _compute_numeric_result_correctness(example, calculation_result)

        self.assertEqual(score, 1.0)

    def test_percent_equivalence_allows_display_rounding_gap(self) -> None:
        left = {
            "kind": "percent",
            "value_text": "25.36",
            "unit_text": "%",
            "normalized_value": 25.36,
        }
        right = {
            "kind": "percent",
            "value_text": "25.4",
            "unit_text": "%",
            "normalized_value": 25.4,
        }

        self.assertTrue(_numeric_values_equivalent(left, right))

    def test_operand_match_accepts_parenthesized_negative_and_display_scale(self) -> None:
        expected = {
            "label": "영업활동으로 인한 현금흐름",
            "period": "2023",
            "raw_value": "2,002",
            "raw_unit": "십억원",
        }
        actual = {
            "label": "2023 영업활동현금흐름",
            "period": "2023",
            "raw_value": "2,002,233,273,518",
            "raw_unit": "원",
            "normalized_value": 2002233273518.0,
            "normalized_unit": "KRW",
        }
        negative_expected = {
            "label": "유형자산의 취득",
            "period": "2023",
            "raw_value": "(640,623,697,250)",
            "raw_unit": "원",
        }
        negative_actual = {
            "label": "2023 유형자산의 취득",
            "period": "2023",
            "raw_value": "(640,623,697,250)",
            "raw_unit": "원",
            "normalized_value": -640623697250.0,
            "normalized_unit": "KRW",
        }

        self.assertTrue(_operand_matches(expected, actual))
        self.assertTrue(_operand_matches(negative_expected, negative_actual))


if __name__ == "__main__":
    unittest.main()
