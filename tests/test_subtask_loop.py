import sys
import unittest
from pathlib import Path

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_models import AggregateSynthesisOutput, CalculationOperand, OperandExtraction


class _StubStructuredLLM:
    def __init__(self, response):
        self._response = response

    def __call__(self, _prompt_value):
        return self._response

    def invoke(self, _prompt_value):
        return self._response


class _StubLLM:
    def __init__(self, response):
        self._response = response

    def with_structured_output(self, _schema):
        return RunnableLambda(lambda _prompt_value: self._response)


class SubtaskLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = FinancialAgent.__new__(FinancialAgent)

    def test_growth_rate_task_consumes_sibling_lookup_outputs_before_retrieval(self) -> None:
        state = {
            "query": "2023년 시설투자(CAPEX) 총액과 전년 대비 증감률을 계산해 줘.",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "삼성전자", "year": 2023},
            "topic": "시설투자(CAPEX) 총액과 전년 대비 증감률",
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "concept_growth_rate",
                "metric_label": "시설투자(CAPEX) 증감률",
                "query": "2023년 시설투자(CAPEX) 증감률을 계산해 줘.",
                "operation_family": "growth_rate",
                "required_operands": [
                    {"label": "2023년 시설투자(CAPEX) 총액", "concept": "capital_expenditure_total", "role": "current_period"},
                    {"label": "2022년 시설투자(CAPEX) 총액", "concept": "capital_expenditure_total", "role": "prior_period"},
                ],
                "depends_on": ["task_1", "task_3"],
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "capital_expenditure_total",
                        "period": "2023",
                        "label": "2023년 시설투자(CAPEX) 총액",
                        "preferred_task_id": "task_1",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "prior_period",
                        "concept": "capital_expenditure_total",
                        "period": "2022",
                        "label": "2022년 시설투자(CAPEX) 총액",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 시설투자(CAPEX) 총액",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 53113900000000.0,
                        "result_unit": "원",
                        "rendered_value": "53조 1,139억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 시설투자(CAPEX) 총액",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2023년 시설투자(CAPEX) 총액",
                                "concept": "capital_expenditure_total",
                                "period": "2023",
                                "raw_value": "53조 1,139억원",
                                "raw_unit": "원",
                                "normalized_value": 53113900000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "53조 1,139억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022년 시설투자(CAPEX) 총액",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 18116800000000.0,
                        "result_unit": "원",
                        "rendered_value": "18조 1,168억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2022년 시설투자(CAPEX) 총액",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2022년 시설투자(CAPEX) 총액",
                                "concept": "capital_expenditure_total",
                                "period": "2022",
                                "raw_value": "18조 1,168억원",
                                "raw_unit": "원",
                                "normalized_value": 18116800000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "18조 1,168억원",
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        extracted = self.agent._extract_calculation_operands(state)
        merged_state = {**state, **extracted}
        self.assertEqual(len(extracted["calculation_operands"]), 2)
        self.assertEqual(
            [row["matched_operand_role"] for row in extracted["calculation_operands"]],
            ["current_period", "prior_period"],
        )

        planned = self.agent._plan_formula_calculation(merged_state)
        self.assertEqual(planned["calculation_plan"]["status"], "ok")
        self.assertEqual(planned["calculation_plan"]["operation"], "growth_rate")
        self.assertEqual(len(planned["calculation_plan"]["ordered_operand_ids"]), 2)

    def test_narrative_summary_subtask_routes_from_evidence_to_compress_and_then_retrieve(self) -> None:
        state = {
            "query": "2023년 커머스 부문 매출 성장률을 계산하고, 포시마크 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            "query_type": "trend",
            "intent": "trend",
            "calc_subtasks": [
                {"task_id": "task_1", "operation_family": "lookup"},
                {"task_id": "task_2", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 1,
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "metric_label": "질문 관련 배경/영향 설명",
                "operation_family": "narrative_summary",
            },
        }

        self.assertEqual(self.agent._route_after_evidence(state), "compress")
        self.assertEqual(self.agent._route_after_validate(state), "advance_subtask")
        self.assertEqual(self.agent._route_after_advance_subtask(state), "retrieve")

    def test_numeric_extractor_advances_when_subtask_loop_exists(self) -> None:
        state = {
            "query": "2023년 연결 현금흐름표에서 배당금 지급 규모를 찾고 주주환원 정책을 요약해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "operation_family": "single_value"},
                {"task_id": "task_2", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "operation_family": "single_value",
            },
        }

        self.assertEqual(self.agent._route_after_numeric_extractor(state), "advance_subtask")

    def test_numeric_extractor_missing_lookup_falls_back_to_reconciliation(self) -> None:
        state = {
            "query": "2023년 재고자산평가손실 규모를 찾아줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "operation_family": "lookup"},
                {"task_id": "task_2", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "operation_family": "lookup",
                "metric_label": "재고자산평가손실",
            },
            "retrieved_docs": [(object(), 1.0)],
            "evidence_status": "missing",
        }

        self.assertEqual(self.agent._route_after_numeric_extractor(state), "reconcile_plan")

    def test_lookup_subtask_routes_to_numeric_extractor_even_when_top_level_intent_is_qa(self) -> None:
        state = {
            "query": "2023년 재무제표 주석에서 재고자산평가손실 규모와 매출원가 영향을 분석해 줘.",
            "query_type": "qa",
            "intent": "qa",
            "calc_subtasks": [
                {"task_id": "task_1", "operation_family": "lookup"},
                {"task_id": "task_2", "operation_family": "lookup"},
                {"task_id": "task_3", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "operation_family": "lookup",
                "metric_label": "재고자산평가손실(환입) 등",
            },
        }

        self.assertEqual(self.agent._route_after_expand(state), "numeric_extractor")

    def test_non_narrative_subtask_routes_to_reconcile_plan_even_when_top_level_intent_is_qa(self) -> None:
        state = {
            "query": "2023년 재무제표 주석에서 재고자산평가손실 규모와 매출원가 영향을 분석해 줘.",
            "query_type": "qa",
            "intent": "qa",
            "calc_subtasks": [
                {"task_id": "task_1", "operation_family": "lookup"},
                {"task_id": "task_2", "operation_family": "lookup"},
                {"task_id": "task_3", "operation_family": "narrative_summary"},
            ],
            "active_subtask_index": 1,
            "active_subtask": {
                "task_id": "task_2",
                "operation_family": "lookup",
                "metric_label": "매출원가",
            },
        }

        self.assertEqual(self.agent._route_after_evidence(state), "reconcile_plan")

    def test_reconcile_short_circuits_when_dependency_outputs_are_fully_resolved(self) -> None:
        state = {
            "query": "커머스 부문의 2023년 매출 성장률(전년 대비)을 계산해 줘.",
            "query_type": "trend",
            "intent": "trend",
            "report_scope": {
                "source_reports": [
                    {"corp_name": "NAVER", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240318000844"},
                    {"corp_name": "NAVER", "year": 2022, "report_type": "사업보고서", "rcept_no": "20230314001049"},
                ]
            },
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_growth_rate",
                "metric_label": "커머스 부문 매출 성장률",
                "query": "연결기준 커머스 부문 매출 성장률(커머스 매출액/커머스 매출액)을 계산해 줘.",
                "operation_family": "growth_rate",
                "required_operands": [
                    {"label": "커머스 매출액", "concept": "revenue", "role": "current_period"},
                    {"label": "커머스 매출액", "concept": "revenue", "role": "prior_period"},
                ],
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "revenue",
                        "period": "2023",
                        "label": "커머스 매출액",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                        "segment_label": "커머스",
                    },
                    {
                        "role": "prior_period",
                        "concept": "revenue",
                        "period": "2022",
                        "label": "커머스 매출액",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                        "segment_label": "커머스",
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022년 커머스 매출액",
                    "status": "ok",
                    "calculation_result": {
                        "result_value": 1801079000000,
                        "result_unit": "KRW",
                        "answer_slots": {
                            "primary_value": {
                                "label": "2022년 커머스 매출액",
                                "raw_value": "1조 8,011억원",
                                "raw_unit": "원",
                                "normalized_value": 1801079000000,
                                "normalized_unit": "KRW",
                                "period": "2022",
                                "source_anchor": "[NAVER | 2022 | IV. 이사의 경영진단 및 분석의견]",
                            }
                        },
                    },
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 커머스 매출액",
                    "status": "ok",
                    "calculation_result": {
                        "result_value": 2546649000000,
                        "result_unit": "KRW",
                        "answer_slots": {
                            "primary_value": {
                                "label": "2023년 커머스 매출액",
                                "raw_value": "2조 5,466억원",
                                "raw_unit": "원",
                                "normalized_value": 2546649000000,
                                "normalized_unit": "KRW",
                                "period": "2023",
                                "source_anchor": "[NAVER | 2023 | IV. 이사의 경영진단 및 분석의견]",
                            }
                        },
                    },
                },
            ],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_items": [],
            "reconciliation_retry_count": 0,
            "tasks": [],
            "artifacts": [],
        }

        updates = self.agent._reconcile_retrieved_evidence(state)
        result = updates["reconciliation_result"]
        self.assertEqual(result["status"], "ready")
        self.assertEqual(
            [item["reason"] for item in result["matched_operands"]],
            ["resolved_from_task_outputs", "resolved_from_task_outputs"],
        )
        self.assertEqual(updates["retry_strategy"], "")

    def test_ratio_task_consumes_sibling_lookup_outputs_before_retrieval(self) -> None:
        state = {
            "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "report_scope": {"company": "네이버", "year": 2023},
            "topic": "종업원급여 비중",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "종업원급여 비중",
                "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "종업원급여", "concept": "employee_benefits_expense", "role": "numerator_1"},
                    {"label": "영업비용", "concept": "operating_expense_total", "role": "denominator_1"},
                ],
                "depends_on": ["task_2", "task_3"],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "employee_benefits_expense",
                        "period": "2023",
                        "label": "종업원급여",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "operating_expense_total",
                        "period": "2023",
                        "label": "영업비용",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 종업원급여",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 1701418940000.0,
                        "result_unit": "천원",
                        "rendered_value": "1조 7,014억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 종업원급여",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2023년 종업원급여",
                                "concept": "employee_benefits_expense",
                                "period": "2023",
                                "raw_value": "1,701,418,940",
                                "raw_unit": "천원",
                                "normalized_value": 1701418940000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "1조 7,014억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 영업비용",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 8181823307000.0,
                        "result_unit": "천원",
                        "rendered_value": "8조 1,818억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 영업비용",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2023년 영업비용",
                                "concept": "operating_expense_total",
                                "period": "2023",
                                "raw_value": "8,181,823,307",
                                "raw_unit": "천원",
                                "normalized_value": 8181823307000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "8조 1,818억원",
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        extracted = self.agent._extract_calculation_operands(state)
        merged_state = {**state, **extracted}
        self.assertEqual(
            [row["matched_operand_role"] for row in extracted["calculation_operands"]],
            ["numerator_1", "denominator_1"],
        )

        planned = self.agent._plan_formula_calculation(merged_state)
        self.assertEqual(planned["calculation_plan"]["status"], "ok")
        self.assertEqual(planned["calculation_plan"]["operation"], "ratio")
        self.assertEqual(len(planned["calculation_plan"]["ordered_operand_ids"]), 2)

    def test_synthesis_retry_strategy_blocks_broad_fallback_for_ratio_task(self) -> None:
        state = {
            "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "report_scope": {"company": "네이버", "year": 2023},
            "topic": "종업원급여 비중",
            "retry_strategy": "synthesize_from_task_outputs",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "종업원급여 비중",
                "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "종업원급여", "concept": "employee_benefits_expense", "role": "numerator_1"},
                    {"label": "영업비용", "concept": "operating_expense_total", "role": "denominator_1"},
                ],
                "depends_on": ["task_2", "task_3"],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "employee_benefits_expense",
                        "period": "2023",
                        "label": "종업원급여",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "operating_expense_total",
                        "period": "2023",
                        "label": "영업비용",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 종업원급여",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 1701418940000.0,
                        "result_unit": "천원",
                        "rendered_value": "1조 7,014억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 종업원급여",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2023년 종업원급여",
                                "concept": "employee_benefits_expense",
                                "period": "2023",
                                "raw_value": "1,701,418,940",
                                "raw_unit": "천원",
                                "normalized_value": 1701418940000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "1조 7,014억원",
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "retry_retrieval", "retry_strategy": "synthesize_from_task_outputs"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        extracted = self.agent._extract_calculation_operands(state)

        self.assertEqual(extracted["calculation_debug_trace"]["source"], "dependency_binding_guard")
        self.assertEqual(extracted["calculation_debug_trace"]["retry_strategy"], "synthesize_from_task_outputs")
        self.assertEqual(len(extracted["calculation_operands"]), 1)
        self.assertEqual(extracted["calculation_operands"][0]["matched_operand_role"], "numerator_1")
        self.assertTrue(extracted["calculation_operands"][0]["dependency_resolved"])

    def test_route_after_reconcile_plan_uses_operand_extractor_for_synthesis_strategy(self) -> None:
        route = self.agent._route_after_reconcile_plan(
            {
                "reconciliation_result": {
                    "status": "retry_retrieval",
                    "retry_strategy": "synthesize_from_task_outputs",
                }
            }
        )

        self.assertEqual(route, "operand_extractor")

    def test_dependency_guard_blocks_direct_rows_for_unresolved_ratio_binding(self) -> None:
        state = {
            "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "report_scope": {"company": "네이버", "year": 2023},
            "topic": "종업원급여 비중",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "종업원급여 비중",
                "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "종업원급여", "concept": "employee_benefits_expense", "role": "numerator_1"},
                    {"label": "영업비용", "concept": "operating_expense_total", "role": "denominator_1"},
                ],
                "depends_on": ["task_2", "task_3"],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "employee_benefits_expense",
                        "period": "2023",
                        "label": "종업원급여",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "operating_expense_total",
                        "period": "2023",
                        "label": "영업비용",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 종업원급여",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 1701418940000.0,
                        "result_unit": "천원",
                        "rendered_value": "1조 7,014억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 종업원급여",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2023년 종업원급여",
                                "concept": "employee_benefits_expense",
                                "period": "2023",
                                "raw_value": "1,701,418,940",
                                "raw_unit": "천원",
                                "normalized_value": 1701418940000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "1조 7,014억원",
                            },
                        },
                    },
                }
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [
            {
                "operand_id": "op_001",
                "evidence_id": "value:employee",
                "label": "2023 종업원급여",
                "raw_value": "1,701,418,940",
                "raw_unit": "천원",
                "normalized_value": 1701418940000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "matched_operand_label": "종업원급여",
                "matched_operand_concept": "employee_benefits_expense",
                "matched_operand_role": "numerator_1",
            },
            {
                "operand_id": "op_002",
                "evidence_id": "value:expense",
                "label": "2023 영업비용",
                "raw_value": "6,915,414,298",
                "raw_unit": "천원",
                "normalized_value": 6915414298000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "matched_operand_label": "영업비용",
                "matched_operand_concept": "operating_expense_total",
                "matched_operand_role": "denominator_1",
            },
        ]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: []

        extracted = self.agent._extract_calculation_operands(state)

        self.assertEqual(extracted["calculation_debug_trace"]["source"], "dependency_binding_guard")
        self.assertEqual(len(extracted["calculation_operands"]), 1)
        self.assertEqual(extracted["calculation_operands"][0]["matched_operand_role"], "numerator_1")
        self.assertTrue(extracted["calculation_operands"][0]["dependency_resolved"])
        self.assertEqual(
            extracted["calculation_debug_trace"]["missing_dependency_bindings"][0]["role"],
            "denominator_1",
        )

    def test_ratio_missing_dependency_binding_can_fall_back_to_retrieved_docs(self) -> None:
        state = {
            "query": "Calculate employee benefits as a share of 2023 operating expense.",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "NAVER", "year": 2023},
            "topic": "employee benefits ratio",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "employee benefits ratio",
                "query": "Calculate employee benefits as a share of 2023 operating expense.",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "employee benefits", "concept": "employee_benefits_expense", "role": "numerator_1"},
                    {"label": "operating expense", "concept": "operating_expense_total", "role": "denominator_1"},
                ],
                "depends_on": ["task_2", "task_3"],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "employee_benefits_expense",
                        "period": "2023",
                        "label": "employee benefits",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "operating_expense_total",
                        "period": "2023",
                        "label": "operating expense",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 employee benefits",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "label": "employee benefits",
                                "concept": "employee_benefits_expense",
                                "period": "2023",
                                "raw_value": "1,701,418,940",
                                "raw_unit": "thousand KRW",
                                "normalized_value": 1701418940000.0,
                                "normalized_unit": "KRW",
                            }
                        },
                    },
                }
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [
                (
                    Document(
                        page_content="operating expense | 8,181,823,307",
                        metadata={"block_type": "table", "table_source_id": "naver-op-expense"},
                    ),
                    1.0,
                )
            ],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        self.agent.llm = _StubLLM(
            OperandExtraction(
                coverage="sufficient",
                operands=[
                    CalculationOperand(
                        operand_id="op_001",
                        evidence_id="ev_doc_001",
                        source_anchor="[NAVER | 2023]",
                        label="operating expense",
                        raw_value="8,181,823,307",
                        raw_unit="thousand KRW",
                        normalized_value=8181823307000.0,
                        normalized_unit="KRW",
                        period="2023",
                    )
                ],
            )
        )
        self.agent._extract_structured_operands_from_reconciliation = lambda _state: []
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: []

        extracted = self.agent._extract_calculation_operands(state)

        self.assertNotEqual(extracted["calculation_debug_trace"].get("source"), "dependency_binding_guard")
        self.assertEqual(extracted["evidence_status"], "sufficient")
        self.assertEqual(len(extracted["calculation_operands"]), 2)
        self.assertEqual(
            [row.get("matched_operand_role") for row in extracted["calculation_operands"]],
            ["numerator_1", None],
        )

    def test_growth_rate_direct_rows_can_fill_missing_task_output_binding(self) -> None:
        state = {
            "query": "2023년 시설투자(CAPEX) 총액의 전년 대비 증감률을 계산해 줘.",
            "query_type": "trend",
            "intent": "trend",
            "report_scope": {"company": "삼성전자", "year": 2023},
            "topic": "시설투자(CAPEX) 총액 증감률",
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "concept_growth_rate",
                "metric_label": "시설투자(CAPEX) 총액 증감률",
                "query": "2023년 시설투자(CAPEX) 총액의 전년 대비 증감률을 계산해 줘.",
                "operation_family": "growth_rate",
                "required_operands": [
                    {"label": "시설투자(CAPEX)", "concept": "capital_expenditure_total", "role": "current_period", "period": "2023"},
                    {"label": "시설투자(CAPEX)", "concept": "capital_expenditure_total", "role": "prior_period", "period": "2022"},
                ],
                "depends_on": ["task_1", "task_3"],
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "capital_expenditure_total",
                        "period": "2023",
                        "label": "시설투자(CAPEX)",
                        "preferred_task_id": "task_1",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "prior_period",
                        "concept": "capital_expenditure_total",
                        "period": "2022",
                        "label": "시설투자(CAPEX)",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 시설투자(CAPEX) 총액",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 53113900000000.0,
                        "result_unit": "억원",
                        "rendered_value": "53조 1,139억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 시설투자(CAPEX) 총액",
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
                            },
                        },
                    },
                }
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {"status": "ready"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        self.agent._extract_structured_operands_from_reconciliation = lambda _state: [
            {
                "operand_id": "op_001",
                "evidence_id": "value:capex:2023",
                "label": "2023 시설투자(CAPEX)",
                "raw_value": "531,139",
                "raw_unit": "억원",
                "normalized_value": 53113900000000.0,
                "normalized_unit": "KRW",
                "period": "2023",
                "matched_operand_label": "시설투자(CAPEX)",
                "matched_operand_concept": "capital_expenditure_total",
                "matched_operand_role": "current_period",
            },
            {
                "operand_id": "op_002",
                "evidence_id": "value:capex:2022",
                "label": "2022 시설투자(CAPEX)",
                "raw_value": "531,153",
                "raw_unit": "억원",
                "normalized_value": 53115300000000.0,
                "normalized_unit": "KRW",
                "period": "2022",
                "matched_operand_label": "시설투자(CAPEX)",
                "matched_operand_concept": "capital_expenditure_total",
                "matched_operand_role": "prior_period",
            },
        ]
        self.agent._evidence_items_from_reconciliation_matches = lambda _state: []

        extracted = self.agent._extract_calculation_operands(state)

        self.assertNotEqual(extracted["calculation_debug_trace"]["source"], "dependency_binding_guard")
        self.assertEqual(extracted["evidence_status"], "sufficient")
        self.assertEqual(len(extracted["calculation_operands"]), 2)
        self.assertEqual(
            {row["matched_operand_role"] for row in extracted["calculation_operands"]},
            {"current_period", "prior_period"},
        )

    def test_sum_task_consumes_sibling_lookup_outputs_before_retrieval(self) -> None:
        state = {
            "query": "삼성전자 2024 사업보고서에서 SDC와 Harman 부문의 매출 합계는 얼마인가요?",
            "query_type": "comparison",
            "intent": "comparison",
            "report_scope": {"company": "삼성전자", "year": 2024},
            "topic": "SDC와 Harman 부문 매출 합계",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_sum",
                "metric_label": "SDC 및 Harman 부문 매출 합계",
                "query": "삼성전자 2024 사업보고서에서 SDC와 Harman 부문의 매출 합계는 얼마인가요?",
                "operation_family": "sum",
                "required_operands": [
                    {"label": "SDC 매출액", "concept": "revenue", "role": "addend_1"},
                    {"label": "Harman 매출액", "concept": "revenue", "role": "addend_2"},
                ],
                "depends_on": ["task_2", "task_3"],
                "inputs": [
                    {
                        "role": "addend_1",
                        "concept": "revenue",
                        "period": "2024",
                        "label": "SDC 매출액",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                        "segment_label": "SDC",
                    },
                    {
                        "role": "addend_2",
                        "concept": "revenue",
                        "period": "2024",
                        "label": "Harman 매출액",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                        "segment_label": "Harman",
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2024년 SDC 매출액",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 29157800000000.0,
                        "result_unit": "억원",
                        "rendered_value": "29조 1,578억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2024년 SDC 매출액",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2024년 SDC 매출액",
                                "concept": "revenue",
                                "period": "2024",
                                "raw_value": "291,578",
                                "raw_unit": "억원",
                                "normalized_value": 29157800000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "29조 1,578억원",
                                "source_anchor": "segment_sdc_revenue",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2024년 Harman 매출액",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 14274900000000.0,
                        "result_unit": "억원",
                        "rendered_value": "14조 2,749억원",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2024년 Harman 매출액",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "2024년 Harman 매출액",
                                "concept": "revenue",
                                "period": "2024",
                                "raw_value": "142,749",
                                "raw_unit": "억원",
                                "normalized_value": 14274900000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "14조 2,749억원",
                                "source_anchor": "segment_harman_revenue",
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "reconciliation_result": {},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        extracted = self.agent._extract_calculation_operands(state)
        merged_state = {**state, **extracted}
        self.assertEqual(
            [row["matched_operand_role"] for row in extracted["calculation_operands"]],
            ["addend_1", "addend_2"],
        )

        planned = self.agent._plan_formula_calculation(merged_state)
        self.assertEqual(planned["calculation_plan"]["status"], "ok")
        self.assertEqual(planned["calculation_plan"]["operation"], "add")
        self.assertEqual(len(planned["calculation_plan"]["ordered_operand_ids"]), 2)

    def test_advance_subtask_records_result_and_rotates(self) -> None:
        state = {
            "query": "2023년 연결기준 부채비율과 유동비율을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "debt_ratio", "metric_label": "부채비율", "query": "2023년 연결기준 부채비율을 계산해 줘."},
                {"task_id": "task_2", "metric_family": "current_ratio", "metric_label": "유동비율", "query": "2023년 연결기준 유동비율을 계산해 줘."},
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "debt_ratio", "metric_label": "부채비율", "query": "2023년 연결기준 부채비율을 계산해 줘."},
            "subtask_results": [],
            "subtask_debug_trace": {},
            "answer": "2023년 연결기준 부채비율은 25.4%입니다.",
            "compressed_answer": "2023년 연결기준 부채비율은 25.4%입니다.",
            "selected_claim_ids": ["ev_001"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "부채비율",
                    "status": "completed",
                    "artifact_ids": ["artifact:001", "artifact:002", "artifact:003", "artifact:004"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:001",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"row_id": "row_1", "label_kr": "부채총계", "value": "92228115"},
                            {"row_id": "row_2", "label_kr": "자본총계", "value": "363677865"},
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:002",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {
                            "status": "ok",
                            "operation": "divide",
                            "ordered_operand_ids": ["row_1", "row_2"],
                        }
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
                {
                    "artifact_id": "artifact:004",
                    "task_id": "task_1",
                    "kind": "reconciliation_result",
                    "payload": {"reconciliation_result": {"status": "ready"}},
                },
            ],
            "calculation_result": {"status": "stale", "rendered_value": "999%"},
            "reconciliation_result": {"status": "stale"},
        }
        updated = self.agent._advance_calculation_subtask(state)
        self.assertEqual(updated["active_subtask_index"], 1)
        self.assertEqual(updated["active_subtask"]["task_id"], "task_2")
        self.assertFalse(updated["subtask_loop_complete"])
        self.assertEqual(len(updated["subtask_results"]), 1)
        self.assertEqual(updated["subtask_results"][0]["task_id"], "task_1")
        self.assertEqual(updated["subtask_results"][0]["answer"], "2023년 연결기준 부채비율은 25.4%입니다.")
        self.assertEqual(updated["subtask_results"][0]["artifact_ids"], ["artifact:001", "artifact:002", "artifact:003", "artifact:004"])
        self.assertEqual(len(updated["subtask_results"][0]["calculation_operands"]), 2)
        self.assertEqual(updated["subtask_results"][0]["calculation_plan"]["operation"], "divide")
        self.assertEqual(updated["subtask_results"][0]["calculation_result"]["rendered_value"], "25.4%")
        self.assertEqual(updated["answer"], "")
        self.assertEqual(updated["resolved_calculation_trace"]["calculation_operands"], [])
        self.assertEqual(updated["structured_result"], {})

    def test_aggregate_subtasks_joins_answers_in_task_order(self) -> None:
        state = {
            "query": "2023년 연결기준 부채비율과 유동비율을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "debt_ratio", "metric_label": "부채비율", "query": "2023년 연결기준 부채비율을 계산해 줘."},
                {"task_id": "task_2", "metric_family": "current_ratio", "metric_label": "유동비율", "query": "2023년 연결기준 유동비율을 계산해 줘."},
            ],
            "active_subtask_index": 1,
            "active_subtask": {"task_id": "task_2", "metric_family": "current_ratio", "metric_label": "유동비율", "query": "2023년 연결기준 유동비율을 계산해 줘."},
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "debt_ratio",
                    "metric_label": "부채비율",
                    "query": "2023년 연결기준 부채비율을 계산해 줘.",
                    "answer": "2023년 연결기준 부채비율은 25.4%입니다.",
                    "status": "ok",
                    "artifact_ids": ["artifact:001", "artifact:002", "artifact:003"],
                    "selected_claim_ids": ["ev_001"],
                    "runtime_evidence": [
                        {
                            "evidence_id": "ev_001",
                            "source_anchor": "[삼성전자 | 2023 | III. 재무에 관한 사항 > 1. 요약재무정보]",
                            "raw_row_text": "부채총계 | 92,228,115",
                        }
                    ],
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
                            "primary_value": {"rendered_value": "25.4%", "role": "primary_value"},
                        },
                    },
                    "reconciliation_result": {"status": "ready"},
                }
            ],
            "answer": "2023년 연결기준 유동비율은 258.8%입니다.",
            "compressed_answer": "2023년 연결기준 유동비율은 258.8%입니다.",
            "selected_claim_ids": ["ev_002"],
            "evidence_items": [
                {
                    "evidence_id": "ev_002",
                    "source_anchor": "[삼성전자 | 2023 | III. 재무에 관한 사항 > 1. 요약재무정보]",
                    "raw_row_text": "유동자산 | 137,621,922",
                }
            ],
            "tasks": [
                {
                    "task_id": "task_2",
                    "kind": "calculation",
                    "label": "유동비율",
                    "status": "completed",
                    "artifact_ids": ["artifact:011", "artifact:012", "artifact:013", "artifact:014"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:011",
                    "task_id": "task_2",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"row_id": "current_assets", "label_kr": "유동자산", "value": "137621922"},
                            {"row_id": "current_liabilities", "label_kr": "유동부채", "value": "53186439"},
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:012",
                    "task_id": "task_2",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {"status": "ok", "operation": "divide"}
                    },
                },
                {
                    "artifact_id": "artifact:013",
                    "task_id": "task_2",
                    "kind": "calculation_result",
                    "payload": {
                        "calculation_result": {"status": "ok", "rendered_value": "258.8%"}
                    },
                },
                {
                    "artifact_id": "artifact:014",
                    "task_id": "task_2",
                    "kind": "reconciliation_result",
                    "payload": {"reconciliation_result": {"status": "ready"}},
                },
            ],
            "calculation_result": {"status": "stale", "rendered_value": "999%"},
            "reconciliation_result": {"status": "stale"},
        }
        updated = self.agent._aggregate_calculation_subtasks(state)
        self.assertTrue(updated["subtask_loop_complete"])
        self.assertEqual(len(updated["subtask_results"]), 2)
        self.assertEqual(
            updated["answer"],
            "2023년 연결기준 부채비율은 25.4%입니다. 2023년 연결기준 유동비율은 258.8%입니다.",
        )
        self.assertEqual(updated["selected_claim_ids"], ["ev_001", "ev_002"])
        self.assertEqual(len(updated["calculation_operands"]), 4)
        self.assertEqual(updated["calculation_plan"]["mode"], "aggregate_subtasks")
        self.assertEqual(updated["calculation_plan"]["subtask_count"], 2)
        self.assertEqual(updated["calculation_result"]["formatted_result"], updated["answer"])
        self.assertEqual(len(updated["evidence_items"]), 2)
        self.assertEqual(
            [row["evidence_id"] for row in updated["evidence_items"]],
            ["ev_001", "ev_002"],
        )
        self.assertEqual(
            updated["calculation_result"]["derived_metrics"]["subtask_ids"],
            ["task_1", "task_2"],
        )
        self.assertEqual(
            updated["calculation_result"]["answer_slots"]["operation_family"],
            "aggregate_subtasks",
        )
        self.assertEqual(
            len(updated["calculation_result"]["answer_slots"]["subtask_results"]),
            2,
        )

    def test_aggregate_subtasks_dedupes_nested_operand_mirrors(self) -> None:
        projection = self.agent._build_aggregate_calculation_projection(
            [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 연구개발비용 총액",
                    "answer": "2023년 연결 연구개발비용 총액은 28,352,769 백만원입니다.",
                    "status": "ok",
                    "calculation_operands": [
                        {
                            "operand_id": "primary_value",
                            "label": "연구개발비용",
                            "raw_value": "28,352,769",
                            "raw_unit": "백만원",
                            "source_row_id": "ev_001",
                            "source_row_ids": ["ev_001"],
                        }
                    ],
                    "calculation_plan": {"status": "ok", "operation": "lookup"},
                    "calculation_result": {"status": "ok", "rendered_value": "28,352,769백만원"},
                },
                {
                    "task_id": "task_2",
                    "metric_family": "narrative_summary",
                    "metric_label": "질문 관련 배경/영향 설명",
                    "answer": "Harman은 SDV 전환에 대응합니다.",
                    "status": "ok",
                    "calculation_operands": [
                        {
                            "task_id": "task_1",
                            "metric_family": "concept_lookup",
                            "metric_label": "2023년 연구개발비용 총액",
                            "operand_id": "primary_value",
                            "label": "연구개발비용",
                            "raw_value": "28,352,769",
                            "raw_unit": "백만원",
                            "source_row_id": "ev_001",
                            "source_row_ids": ["ev_001"],
                        }
                    ],
                    "calculation_plan": {"status": "ok", "mode": "aggregate_subtasks"},
                    "calculation_result": {"status": "ok", "rendered_value": "Harman은 SDV 전환에 대응합니다."},
                },
            ],
            "2023년 연결 연구개발비용 총액은 28,352,769백만원입니다. Harman은 SDV 전환에 대응합니다.",
        )

        self.assertEqual(len(projection["calculation_operands"]), 1)
        self.assertEqual(projection["calculation_result"]["source_row_ids"], ["ev_001"])

    def test_aggregate_subtasks_prefers_narrative_summary_fallback_over_partial_failures(self) -> None:
        self.agent.llm = None
        state = {
            "query": "2023년 총 영업비용과 영업비용률을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_3", "metric_family": "concept_lookup", "metric_label": "2023년 매출원가"},
                {"task_id": "task_4", "metric_family": "concept_lookup", "metric_label": "2023년 판매비와관리비"},
                {"task_id": "task_1", "metric_family": "concept_ratio", "metric_label": "영업비용률"},
                {"task_id": "task_2", "metric_family": "narrative_summary", "metric_label": "질문 관련 배경/영향 설명"},
            ],
            "active_subtask_index": 3,
            "active_subtask": {"task_id": "task_2", "metric_family": "narrative_summary", "metric_label": "질문 관련 배경/영향 설명"},
            "subtask_results": [
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 매출원가",
                    "answer": "2023년 매출원가 계산에 필요한 값(2023년 매출원가)을 문서 근거에서 충분히 확인하지 못해 계산할 수 없습니다.",
                    "status": "partial",
                    "calculation_result": {"status": "partial", "answer_slots": {"operation_family": "aggregate_subtasks", "subtask_results": []}},
                },
                {
                    "task_id": "task_4",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 판매비와관리비",
                    "answer": "2023년 판매비와관리비 계산에 필요한 값(2023년 판매비와관리비)을 문서 근거에서 충분히 확인하지 못해 계산할 수 없습니다.",
                    "status": "partial",
                    "calculation_result": {"status": "partial", "answer_slots": {"operation_family": "aggregate_subtasks", "subtask_results": []}},
                },
                {
                    "task_id": "task_1",
                    "metric_family": "concept_ratio",
                    "metric_label": "영업비용률",
                    "answer": "",
                    "status": "insufficient_operands",
                    "calculation_result": {
                        "status": "insufficient_operands",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "metric_label": "영업비용률",
                            "primary_value": {"status": "missing", "role": "primary_value", "label": "영업비용률"},
                        },
                    },
                },
            ],
            "answer": "매출원가는 129,179,183 백만원입니다. 판매비와관리비는 18,357,495 백만원입니다. 총 영업비용은 147,536,678 백만원입니다. 매출액 대비 영업비용률은 약 90.70%입니다.",
            "compressed_answer": "매출원가는 129,179,183 백만원입니다. 판매비와관리비는 18,357,495 백만원입니다. 총 영업비용은 147,536,678 백만원입니다. 매출액 대비 영업비용률은 약 90.70%입니다.",
            "plan_loop_count": 2,
            "selected_claim_ids": ["ev_001"],
            "tasks": [],
            "artifacts": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)
        self.assertEqual(
            updated["answer"],
            "매출원가는 129,179,183 백만원입니다. 판매비와관리비는 18,357,495 백만원입니다. 총 영업비용은 147,536,678 백만원입니다. 매출액 대비 영업비용률은 약 90.70%입니다.",
        )
        self.assertEqual(updated["planner_feedback"], "")

    def test_narrative_summary_gap_check_handles_wrapped_lookup_rows(self) -> None:
        rows = [
            {
                "task_id": "task_3",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 매출원가",
                "status": "partial",
                "answer": "2023년 매출원가 계산에 필요한 값(2023년 매출원가)을 문서 근거에서 충분히 확인하지 못해 계산할 수 없습니다.",
                "calculation_result": {
                    "status": "partial",
                    "answer_slots": {"operation_family": "aggregate_subtasks", "subtask_results": []},
                },
            },
            {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "metric_label": "질문 관련 배경/영향 설명",
                "status": "ok",
                "answer": "매출원가는 129,179,183 백만원입니다. 판매비와관리비는 18,357,495 백만원입니다. 총 영업비용은 147,536,678 백만원입니다. 매출액 대비 영업비용률은 약 90.70%입니다.",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {"operation_family": "aggregate_subtasks", "subtask_results": []},
                },
            },
        ]

        self.assertTrue(self.agent._narrative_summary_gap_is_satisfied(rows[0], rows))

    def test_lookup_gap_check_handles_aggregate_wrapped_lookup_rows(self) -> None:
        rows = [
            {
                "task_id": "task_2",
                "metric_family": "concept_lookup",
                "metric_label": "재고자산평가손실환입",
                "status": "partial",
                "answer": "재고자산평가손실환입 계산에 필요한 값(재고자산평가손실환입)을 문서 근거에서 충분히 확인하지 못했습니다.",
                "calculation_result": {
                    "status": "partial",
                    "answer_slots": {"operation_family": "aggregate_subtasks", "subtask_results": []},
                },
            },
            {
                "task_id": "task_6",
                "metric_family": "concept_ratio",
                "metric_label": "매출원가 대비 재고자산평가손실(환입) 비중",
                "status": "ok",
                "answer": "재고자산평가손실(환입) 등은 5,037,579백만원입니다.",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "매출원가 대비 재고자산평가손실(환입) 비중",
                            "normalized_value": 2.79,
                            "normalized_unit": "PERCENT",
                            "rendered_value": "2.79%",
                        },
                        "components_by_role": {
                            "numerator_1": [
                                {
                                    "status": "ok",
                                    "role": "numerator_1",
                                    "label": "재고자산평가손실(환입) 등",
                                    "period": "2023",
                                    "raw_value": "5,037,579",
                                    "raw_unit": "백만원",
                                    "normalized_value": 5037579000000.0,
                                    "normalized_unit": "KRW",
                                    "rendered_value": "5,037,579백만원",
                                }
                            ]
                        },
                    },
                },
            },
        ]

        self.assertTrue(self.agent._lookup_gap_is_satisfied_by_sibling_slots(rows[0], rows))
        self.assertEqual(self.agent._infer_planner_feedback_from_answer_slots(rows), "")

    def test_capture_current_subtask_result_prefers_live_active_trace_over_stale_artifact(self) -> None:
        state = {
            "query": "2023년 연결기준 영업비용률을 계산해 줘.",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "영업비용률",
                "query": "2023년 연결기준 영업비용률을 계산해 줘.",
            },
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "영업비용률",
                    "status": "completed",
                    "artifact_ids": ["artifact:401", "artifact:402", "artifact:403"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:401",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"operand_id": "stale_op", "label": "stale", "raw_value": "0", "raw_unit": "%"}
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:402",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {"status": "ok", "operation": "ratio"}
                    },
                },
                {
                    "artifact_id": "artifact:403",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "payload": {
                        "calculation_result": {
                            "status": "ok",
                            "rendered_value": "stale",
                            "answer_slots": {
                                "operation_family": "ratio",
                                "primary_value": {"status": "missing", "label": "영업비용률"},
                            },
                        }
                    },
                },
            ],
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {
                        "operand_id": "rev",
                        "label": "매출액",
                        "raw_value": "162,663,579",
                        "raw_unit": "백만원",
                        "normalized_value": 162663579000000.0,
                        "normalized_unit": "KRW",
                    }
                ],
                "calculation_plan": {"status": "ok", "operation": "ratio"},
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "90.7%",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "primary_value": {
                            "status": "ok",
                            "label": "영업비용률",
                            "raw_value": "90.7",
                            "raw_unit": "%",
                            "normalized_value": 90.7,
                            "normalized_unit": "PERCENT",
                            "rendered_value": "90.7%",
                        },
                    },
                },
            },
            "answer": "2023년 연결기준 영업비용률은 90.7%입니다.",
            "compressed_answer": "2023년 연결기준 영업비용률은 90.7%입니다.",
            "reconciliation_result": {"status": "ready"},
        }

        current = self.agent._capture_current_subtask_result(state)

        self.assertEqual(current["calculation_result"]["rendered_value"], "90.7%")
        self.assertEqual(
            current["calculation_result"]["answer_slots"]["primary_value"]["rendered_value"],
            "90.7%",
        )
        self.assertEqual(current["calculation_operands"][0]["operand_id"], "rev")

    def test_capture_current_subtask_result_promotes_single_lookup_prose_value(self) -> None:
        state = {
            "query": "2023년 연결 연구개발비용 총액을 추출하고, Harman 부문 기술 초점을 요약해 줘.",
            "answer": "2023년 연결 연구개발비용 총액은 28,352,769 백만원입니다.",
            "compressed_answer": "2023년 연결 연구개발비용 총액은 28,352,769 백만원입니다.",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 연결 연구개발비용 총액",
                "query": "2023년 연결 연구개발비용 총액을 찾아 줘.",
                "operation_family": "lookup",
            },
            "selected_claim_ids": ["ev_001"],
            "evidence_items": [],
            "retrieved_docs": [
                (
                    Document(
                        page_content="연구개발비용 계 | 28,352,769 | ※ 연결 누계기준입니다.",
                        metadata={
                            "company": "삼성전자",
                            "year": 2023,
                            "section_path": "II. 사업의 내용 > 6. 주요계약 및 연구개발활동",
                        },
                    ),
                    0.9,
                )
            ],
            "seed_retrieved_docs": [],
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "reconciliation_result": {},
        }

        current = self.agent._capture_current_subtask_result(state)

        self.assertEqual(current["status"], "ok")
        self.assertEqual(current["calculation_result"]["answer_slots"]["operation_family"], "lookup")
        self.assertEqual(
            current["calculation_result"]["answer_slots"]["primary_value"]["rendered_value"],
            "28,352,769백만원",
        )
        self.assertEqual(len(current["calculation_operands"]), 1)
        self.assertEqual(current["calculation_operands"][0]["rendered_value"], "28,352,769백만원")
        self.assertTrue(current["calculation_operands"][0]["source_row_ids"])

    def test_capture_current_subtask_result_prefers_deterministic_dividend_hybrid_answer(self) -> None:
        state = {
            "query": "2023년 연결 현금흐름표에서 '배당금 지급'으로 유출된 현금 규모를 찾고, 사업보고서의 '배당에 관한 사항'을 바탕으로 2024~2026년 주주환원 정책을 요약해 줘.",
            "answer": "2023년 연결 현금흐름표상 배당금 지급으로 유출된 현금은 9조 8,094억원입니다.",
            "compressed_answer": "2023년 연결 현금흐름표상 배당금 지급으로 유출된 현금은 9조 8,094억원입니다.",
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "narrative_summary",
                "metric_label": "질문 관련 배경/영향 설명",
                "query": "2023년 연결 현금흐름표에서 '배당금 지급'으로 유출된 현금 규모를 찾고, 사업보고서의 '배당에 관한 사항'을 바탕으로 2024~2026년 주주환원 정책을 요약해 줘.",
                "operation_family": "narrative_summary",
            },
            "evidence_items": [
                {
                    "evidence_id": "ev_001",
                    "source_anchor": "[삼성전자 | 2023 | III. 재무에 관한 사항 > 6. 배당에 관한 사항]",
                    "claim": "2023년(제55기) 연결 현금흐름표에서 '배당금 지급'으로 유출된 현금 규모는 9조 8,094억원입니다.",
                    "quote_span": "현금배당금총액(백만원) | 9,809,438",
                    "metadata": {
                        "section_path": "III. 재무에 관한 사항 > 6. 배당에 관한 사항",
                    },
                },
                {
                    "evidence_id": "ev_002",
                    "source_anchor": "[삼성전자 | 2023 | III. 재무에 관한 사항 > 6. 배당에 관한 사항]",
                    "claim": "삼성전자는 2024년부터 2026년까지 3년간 잉여현금흐름의 50%를 재원으로 연간 9.8조원 수준의 정규배당을 유지하고, 정규배당 이후 잔여 재원이 발생하면 추가로 환원할 계획입니다.",
                    "quote_span": "2024년부터 2026년까지 3년간 발생하는 잉여현금흐름의 50%를 재원으로 활용하여 연간 9.8조원 수준의 정규배당을 유지하되, 정규배당 이후에도 잔여 재원이 발생하는 경우에 추가로 환원할 계획입니다.",
                    "metadata": {
                        "section_path": "III. 재무에 관한 사항 > 6. 배당에 관한 사항",
                    },
                },
                {
                    "evidence_id": "ev_003",
                    "source_anchor": "[삼성전자 | 2023 | IV. 이사의 경영진단 및 분석의견]",
                    "claim": "당기말 현재 당사 차입금은 12조 6,859억원이며, 당사의 유동성은 당기 영업활동 현금흐름으로 44조 1,374억원이 유입되었고, 배당금 지급 9조 8,645억원 등이 유출되었습니다.",
                    "quote_span": "당기말 현재 당사 차입금은 12조 6,859억원이며, 배당금 지급 9조 8,645억원 등이 유출되었습니다.",
                    "metadata": {
                        "section_path": "IV. 이사의 경영진단 및 분석의견 > 유동성 및 자금조달",
                    },
                },
            ],
            "selected_claim_ids": ["ev_001", "ev_002"],
            "tasks": [],
            "artifacts": [],
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "reconciliation_result": {},
        }

        current = self.agent._capture_current_subtask_result(state)

        self.assertIn("9조 8,645억원", current["answer"])
        self.assertIn("2024년부터 2026년까지", current["answer"])
        self.assertEqual(current["selected_claim_ids"], ["ev_003", "ev_002"])

    def test_project_legacy_calculation_fields_prefers_ledger_trace_over_stale_top_level(self) -> None:
        state = {
            "answer": "2023년 연결기준 부채비율은 25.4%입니다.",
            "compressed_answer": "2023년 연결기준 부채비율은 25.4%입니다.",
            "active_subtask": {"task_id": "task_1"},
            "subtask_results": [],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "부채비율",
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
                        "calculation_result": {
                            "status": "ok",
                            "rendered_value": "25.4%",
                            "answer_slots": {
                                "operation_family": "ratio",
                                "primary_value": {"status": "ok", "rendered_value": "25.4%"},
                            },
                        }
                    },
                },
            ],
            "calculation_operands": [{"row_id": "stale"}],
            "calculation_plan": {"status": "stale"},
            "calculation_result": {"status": "stale", "rendered_value": "999%"},
        }

        projected = self.agent._project_legacy_calculation_fields(state)

        self.assertEqual(len(projected["calculation_operands"]), 2)
        self.assertEqual(projected["calculation_plan"]["operation"], "divide")
        self.assertEqual(projected["calculation_result"]["rendered_value"], "25.4%")

    def test_project_legacy_calculation_fields_prefers_ledger_trace_over_stale_resolved_trace(self) -> None:
        state = {
            "answer": "2023년 연결기준 부채비율은 25.4%입니다.",
            "compressed_answer": "2023년 연결기준 부채비율은 25.4%입니다.",
            "active_subtask": {"task_id": "task_1"},
            "subtask_results": [],
            "resolved_calculation_trace": {
                "calculation_operands": [{"row_id": "stale"}],
                "calculation_plan": {"operation": "stale"},
                "calculation_result": {"status": "stale", "rendered_value": "999%"},
            },
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "부채비율",
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
                        "calculation_result": {
                            "status": "ok",
                            "rendered_value": "25.4%",
                            "answer_slots": {
                                "operation_family": "ratio",
                                "primary_value": {"status": "ok", "rendered_value": "25.4%"},
                            },
                        }
                    },
                },
            ],
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }

        projected = self.agent._project_legacy_calculation_fields(state)

        self.assertEqual(len(projected["calculation_operands"]), 2)
        self.assertEqual(projected["calculation_plan"]["operation"], "divide")
        self.assertEqual(projected["calculation_result"]["rendered_value"], "25.4%")

    def test_capture_current_subtask_result_ignores_stale_aggregate_resolved_trace(self) -> None:
        state = {
            "query": "2023년 시설투자(CAPEX) 총액을 찾아 줘.",
            "answer": "2023년 시설투자(CAPEX) 총액은 53조 1,139억원입니다.",
            "compressed_answer": "2023년 시설투자(CAPEX) 총액은 53조 1,139억원입니다.",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 시설투자(CAPEX) 총액",
                "query": "2023년 시설투자(CAPEX) 총액을 찾아 줘.",
            },
            "resolved_calculation_trace": {
                "calculation_operands": [],
                "calculation_plan": {"status": "ok", "mode": "aggregate_subtasks", "subtask_count": 2},
                "calculation_result": {
                    "status": "partial",
                    "rendered_value": "stale aggregate",
                    "answer_slots": {"operation_family": "aggregate_subtasks", "subtask_results": []},
                },
            },
            "calculation_operands": [
                {
                    "operand_id": "capex_2023",
                    "label": "2023 시설투자(CAPEX)",
                    "raw_value": "531,139",
                    "raw_unit": "억원",
                    "normalized_value": 53113900000000.0,
                    "normalized_unit": "KRW",
                    "matched_operand_role": "current_period",
                    "matched_operand_concept": "capital_expenditure_total",
                }
            ],
            "calculation_plan": {"status": "ok", "operation": "lookup", "mode": "single_value"},
            "calculation_result": {
                "status": "ok",
                "rendered_value": "53조 1,139억원",
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {
                        "status": "ok",
                        "label": "2023 시설투자(CAPEX)",
                        "concept": "capital_expenditure_total",
                        "period": "2023년",
                        "raw_value": "531,139",
                        "raw_unit": "억원",
                        "normalized_value": 53113900000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "53조 1,139억원",
                    }
                },
            },
            "tasks": [],
            "artifacts": [],
        }

        current = self.agent._capture_current_subtask_result(state)

        self.assertEqual(current["calculation_plan"]["operation"], "lookup")
        self.assertEqual(current["calculation_result"]["rendered_value"], "53조 1,139억원")
        self.assertEqual(current["calculation_operands"][0]["operand_id"], "capex_2023")

    def test_project_legacy_calculation_fields_prefers_live_lookup_over_stale_aggregate_trace(self) -> None:
        state = {
            "answer": "2023년 시설투자(CAPEX) 총액은 53조 1,139억원입니다.",
            "compressed_answer": "2023년 시설투자(CAPEX) 총액은 53조 1,139억원입니다.",
            "active_subtask": {"task_id": "task_1"},
            "resolved_calculation_trace": {
                "calculation_operands": [],
                "calculation_plan": {"status": "ok", "mode": "aggregate_subtasks", "subtask_count": 2},
                "calculation_result": {
                    "status": "partial",
                    "rendered_value": "stale aggregate",
                    "answer_slots": {"operation_family": "aggregate_subtasks", "subtask_results": []},
                },
            },
            "calculation_operands": [
                {
                    "operand_id": "capex_2023",
                    "label": "2023 시설투자(CAPEX)",
                    "raw_value": "531,139",
                    "raw_unit": "억원",
                    "normalized_value": 53113900000000.0,
                    "normalized_unit": "KRW",
                }
            ],
            "calculation_plan": {"status": "ok", "operation": "lookup", "mode": "single_value"},
            "calculation_result": {
                "status": "ok",
                "rendered_value": "53조 1,139억원",
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {"status": "ok", "rendered_value": "53조 1,139억원"},
                },
            },
            "tasks": [],
            "artifacts": [],
        }

        projected = self.agent._project_legacy_calculation_fields(state)

        self.assertEqual(projected["calculation_plan"]["operation"], "lookup")
        self.assertEqual(projected["calculation_result"]["rendered_value"], "53조 1,139억원")
        self.assertEqual(projected["calculation_operands"][0]["operand_id"], "capex_2023")

    def test_route_after_aggregate_subtasks_reuses_pre_calc_planner_when_feedback_exists(self) -> None:
        route = self.agent._route_after_aggregate_subtasks(
            {
                "planner_feedback": "유동비율 계산 재료 누락",
                "plan_loop_count": 0,
            }
        )
        self.assertEqual(route, "pre_calc_planner")
        self.assertEqual(
            self.agent._route_after_aggregate_subtasks(
                {
                    "planner_feedback": "",
                    "plan_loop_count": 0,
                }
            ),
            "cite",
        )

    def test_aggregate_subtasks_can_emit_planner_feedback_for_replan(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 법인세비용차감전순이익은 확인되었지만, 전년 대비 비교를 위해 2022년 값이 추가로 필요합니다.",
                    "planner_feedback": "2022년 법인세비용차감전순이익 raw value를 찾는 lookup task를 추가하세요.",
                }
            )
        )
        state = {
            "query": "2023년 법인세비용차감전순이익을 보여주고 전년 대비 증감액을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "2023년 법인세비용차감전순이익", "query": "2023년 법인세비용차감전순이익을 찾아줘."},
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "2023년 법인세비용차감전순이익", "query": "2023년 법인세비용차감전순이익을 찾아줘."},
            "subtask_results": [],
            "answer": "2023년 법인세비용차감전순이익은 1조 4,813억원입니다.",
            "compressed_answer": "2023년 법인세비용차감전순이익은 1조 4,813억원입니다.",
            "selected_claim_ids": ["ev_100"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "2023년 법인세비용차감전순이익",
                    "status": "completed",
                    "artifact_ids": ["artifact:101", "artifact:102", "artifact:103"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:101",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"row_id": "pretax_2023", "label": "2023년 법인세비용차감전순이익", "normalized_value": 1481396318000, "raw_value": "1,481,396,318", "raw_unit": "천원", "period": "2023년"}
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:102",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {"status": "ok", "operation": "lookup"}
                    },
                },
                {
                    "artifact_id": "artifact:103",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "payload": {
                        "calculation_result": {"status": "ok", "rendered_value": "1조 4,813억원", "series": []}
                    },
                },
            ],
            "calculation_result": {"status": "ok", "rendered_value": "1조 4,813억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 0,
        }
        updated = self.agent._aggregate_calculation_subtasks(state)
        self.assertEqual(updated["planner_mode"], "replan")
        self.assertEqual(
            updated["planner_feedback"],
            "2022년 법인세비용차감전순이익 raw value를 찾는 lookup task를 추가하세요.",
        )
        self.assertIn("2023년 법인세비용차감전순이익은 확인되었지만", updated["answer"])
        self.assertEqual(
            self.agent._route_after_aggregate_subtasks(
                {
                    "planner_feedback": "추가 재계획 필요",
                    "plan_loop_count": 2,
                }
            ),
            "cite",
        )

    def test_aggregate_subtasks_emits_final_refusal_when_replan_budget_is_exhausted(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 법인세비용차감전순이익은 1조 4,813억원입니다.",
                    "planner_feedback": "2022년 법인세비용차감전순이익 raw value가 여전히 필요합니다.",
                }
            )
        )
        state = {
            "query": "2023년 법인세비용차감전순이익을 보여주고 전년 대비 증감액을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "2023년 법인세비용차감전순이익", "query": "2023년 법인세비용차감전순이익을 찾아줘."},
            ],
            "active_subtask_index": 0,
            "active_subtask": {"task_id": "task_1", "metric_family": "concept_lookup", "metric_label": "2023년 법인세비용차감전순이익", "query": "2023년 법인세비용차감전순이익을 찾아줘."},
            "subtask_results": [],
            "answer": "2023년 법인세비용차감전순이익은 1조 4,813억원입니다.",
            "compressed_answer": "2023년 법인세비용차감전순이익은 1조 4,813억원입니다.",
            "selected_claim_ids": ["ev_100"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "2023년 법인세비용차감전순이익",
                    "status": "completed",
                    "artifact_ids": ["artifact:101", "artifact:102", "artifact:103"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:101",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"row_id": "pretax_2023", "label": "2023년 법인세비용차감전순이익", "normalized_value": 1481396318000, "raw_value": "1,481,396,318", "raw_unit": "천원", "period": "2023년"}
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:102",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {"status": "ok", "operation": "lookup"}
                    },
                },
                {
                    "artifact_id": "artifact:103",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "payload": {
                        "calculation_result": {"status": "ok", "rendered_value": "1조 4,813억원", "series": []}
                    },
                },
            ],
            "calculation_result": {"status": "ok", "rendered_value": "1조 4,813억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 2,
        }
        updated = self.agent._aggregate_calculation_subtasks(state)
        self.assertEqual(updated["planner_mode"], "initial")
        self.assertEqual(
            updated["planner_feedback"],
            "2022년 법인세비용차감전순이익 raw value가 여전히 필요합니다.",
        )
        self.assertIn("2023년 법인세비용차감전순이익은 1조 4,813억원입니다.", updated["answer"])
        self.assertIn("원하신 답을 완전히 확정할 수는 없습니다.", updated["answer"])

    def test_aggregate_subtasks_ignores_spurious_llm_feedback_when_material_is_complete(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 연결기준 매출액은 162조 6,636억원입니다.",
                    "planner_feedback": "추가 재료 확인이 필요합니다.",
                }
            )
        )
        state = {
            "query": "2023년 연결기준 매출액은 얼마야?",
            "calc_subtasks": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 연결기준 매출액",
                    "query": "2023년 연결기준 매출액을 찾아줘.",
                },
            ],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 연결기준 매출액",
                "query": "2023년 연결기준 매출액을 찾아줘.",
            },
            "subtask_results": [],
            "answer": "2023년 연결기준 매출액은 162조 6,636억원입니다.",
            "compressed_answer": "2023년 연결기준 매출액은 162조 6,636억원입니다.",
            "selected_claim_ids": ["ev_rev"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "2023년 연결기준 매출액",
                    "status": "completed",
                    "artifact_ids": ["artifact:301", "artifact:302", "artifact:303"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:301",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {
                                "row_id": "revenue_2023",
                                "label": "2023년 연결기준 매출액",
                                "normalized_value": 162663579000000.0,
                                "raw_value": "162,663,579",
                                "raw_unit": "백만원",
                                "period": "2023년",
                            }
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:302",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {"status": "ok", "operation": "lookup"}
                    },
                },
                {
                    "artifact_id": "artifact:303",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "payload": {
                        "calculation_result": {
                            "status": "ok",
                            "rendered_value": "162조 6,636억원",
                            "answer_slots": {
                                "operation_family": "lookup",
                                "primary_value": {
                                    "status": "ok",
                                    "label": "2023년 연결기준 매출액",
                                    "period": "2023년",
                                    "raw_value": "162,663,579",
                                    "raw_unit": "백만원",
                                    "normalized_value": 162663579000000.0,
                                    "normalized_unit": "KRW",
                                    "rendered_value": "162조 6,636억원",
                                },
                            },
                        }
                    },
                },
            ],
            "calculation_result": {"status": "ok", "rendered_value": "162조 6,636억원"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 2,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_feedback"], "")
        self.assertEqual(updated["planner_mode"], "initial")
        self.assertEqual(updated["answer"], "2023년 연결기준 매출액은 162조 6,636억원입니다.")
        self.assertNotIn("완전히 확정할 수는 없습니다", updated["answer"])

    def test_aggregate_subtasks_dedupes_stale_failed_metric_before_feedback(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 연결기준 매출액은 162조 6,636억원입니다. 매출원가는 129조 1,792억원, 판매비와관리비는 18조 3,575억원입니다. 이를 합산한 총 영업비용은 147조 5,367억원이며, 전체 매출액 대비 영업비용률은 90.7%입니다.",
                    "planner_feedback": "영업비용률 계산 재료가 아직 부족합니다.",
                }
            )
        )
        state = {
            "query": "2023년 손익계산서에서 '매출원가'와 '판매비와관리비'를 합산하여 '총 영업비용'을 구한 뒤, 전체 매출액 대비 영업비용률을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_4"},
                {"task_id": "task_5"},
                {"task_id": "task_1"},
                {"task_id": "task_6"},
                {"task_id": "task_2"},
            ],
            "active_subtask_index": 4,
            "active_subtask": {
                "task_id": "task_2",
                "metric_family": "concept_ratio",
                "metric_label": "영업비용률",
                "operation_family": "ratio",
            },
            "subtask_results": [
                {
                    "task_id": "task_4",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 매출액",
                    "status": "ok",
                    "answer": "2023년 연결기준 매출액은 162조 6,636억원입니다.",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 매출액",
                            "primary_value": {
                                "status": "ok",
                                "label": "매출액",
                                "normalized_value": 162663579000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "162조 6,636억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_5",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 매출원가",
                    "status": "ok",
                    "answer": "2023년 연결기준 매출원가는 129조 1,792억원입니다.",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 매출원가",
                            "primary_value": {
                                "status": "ok",
                                "label": "매출원가",
                                "normalized_value": 129179183000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "129조 1,792억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_1",
                    "metric_family": "concept_ratio",
                    "metric_label": "영업비용률",
                    "status": "insufficient_operands",
                    "answer": "",
                    "calculation_result": {
                        "status": "insufficient_operands",
                        "answer_slots": {
                            "operation_family": "ratio",
                            "metric_label": "영업비용률",
                            "primary_value": {"status": "missing", "label": "영업비용률"},
                        },
                    },
                },
                {
                    "task_id": "task_6",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 판매비와관리비",
                    "status": "ok",
                    "answer": "2023년 판매비와관리비는 18조 3,575억원입니다.",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "metric_label": "2023년 판매비와관리비",
                            "primary_value": {
                                "status": "ok",
                                "label": "판매비와관리비",
                                "normalized_value": 18357495000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "18조 3,575억원",
                            },
                        },
                    },
                },
            ],
            "answer": "2023년 연결기준 영업비용률은 90.7%입니다.",
            "calculation_result": {
                "status": "ok",
                "answer_slots": {
                    "operation_family": "ratio",
                    "metric_label": "영업비용률",
                    "components_by_role": {
                        "numerator_1": [{"status": "ok", "label": "매출원가"}],
                        "numerator_2": [{"status": "ok", "label": "판매비와관리비"}],
                        "denominator_1": [{"status": "ok", "label": "매출액"}],
                    },
                    "primary_value": {
                        "status": "ok",
                        "label": "영업비용률",
                        "normalized_value": 90.7004990957441,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "90.7%",
                    },
                },
                "source_row_ids": [],
            },
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "selected_claim_ids": [],
            "plan_loop_count": 2,
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_feedback"], "")
        self.assertNotIn("완전히 확정할 수는 없습니다", updated["answer"])

    def test_aggregate_subtasks_uses_answer_slots_gap_check_without_llm(self) -> None:
        state = {
            "query": "2023년 법인세비용차감전순이익을 보여주고 전년 대비 증감액을 계산해 줘.",
            "calc_subtasks": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_difference",
                    "metric_label": "법인세비용차감전순이익 증감액",
                    "query": "법인세비용차감전순이익 증감액을 계산해 줘.",
                },
            ],
            "active_subtask_index": 0,
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_difference",
                "metric_label": "법인세비용차감전순이익 증감액",
                "query": "법인세비용차감전순이익 증감액을 계산해 줘.",
            },
            "subtask_results": [],
            "answer": "2023년 법인세비용차감전순이익은 1조 4,814억원입니다.",
            "compressed_answer": "2023년 법인세비용차감전순이익은 1조 4,814억원입니다.",
            "selected_claim_ids": ["ev_200"],
            "tasks": [
                {
                    "task_id": "task_1",
                    "kind": "calculation",
                    "label": "법인세비용차감전순이익 증감액",
                    "status": "completed",
                    "artifact_ids": ["artifact:201", "artifact:202", "artifact:203"],
                }
            ],
            "artifacts": [
                {
                    "artifact_id": "artifact:201",
                    "task_id": "task_1",
                    "kind": "operand_set",
                    "payload": {
                        "calculation_operands": [
                            {"row_id": "pretax_2023", "label": "2023년 법인세비용차감전순이익", "normalized_value": 1481396318000},
                        ]
                    },
                },
                {
                    "artifact_id": "artifact:202",
                    "task_id": "task_1",
                    "kind": "calculation_plan",
                    "payload": {
                        "calculation_plan": {"status": "ok", "operation": "subtract"}
                    },
                },
                {
                    "artifact_id": "artifact:203",
                    "task_id": "task_1",
                    "kind": "calculation_result",
                    "payload": {
                        "calculation_result": {
                            "status": "partial",
                            "rendered_value": "",
                            "answer_slots": {
                                "operation_family": "difference",
                                "current_value": {"period": "2023년", "rendered_value": "1조 4,814억원"},
                            },
                        }
                    },
                },
            ],
            "calculation_result": {"status": "partial"},
            "reconciliation_result": {"status": "ready"},
            "planner_feedback": "",
            "planner_mode": "initial",
            "plan_loop_count": 0,
        }
        updated = self.agent._aggregate_calculation_subtasks(state)
        self.assertEqual(updated["planner_mode"], "replan")
        self.assertIn("법인세비용차감전순이익 증감액 계산에 필요한", updated["planner_feedback"])
        self.assertIn("prior", updated["planner_feedback"])

    def test_aggregate_subtasks_ignores_growth_gap_when_sibling_lookups_cover_periods(self) -> None:
        ordered_results = [
            {
                "task_id": "task_1",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 시설투자(CAPEX) 총액",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "label": "2023 시설투자(CAPEX)",
                            "concept": "capital_expenditure_total",
                            "period": "2023년",
                            "rendered_value": "53조 1,139억원",
                        },
                    },
                },
            },
            {
                "task_id": "task_2",
                "metric_family": "concept_growth_rate",
                "metric_label": "시설투자(CAPEX) 증감률",
                "status": "insufficient_operands",
                "calculation_result": {
                    "status": "insufficient_operands",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "components_by_role": {
                            "current_period": [
                                {
                                    "status": "ok",
                                    "label": "2023 시설투자(CAPEX)",
                                    "concept": "capital_expenditure_total",
                                    "period": "2023년",
                                    "rendered_value": "53조 1,139억원",
                                }
                            ]
                        },
                        "current_value": {
                            "status": "missing",
                            "label": "시설투자(CAPEX)",
                            "concept": "capital_expenditure_total",
                            "period": "",
                        },
                        "prior_value": {
                            "status": "missing",
                            "label": "시설투자(CAPEX)",
                            "concept": "capital_expenditure_total",
                            "period": "2022년",
                        },
                        "primary_value": {
                            "status": "missing",
                            "label": "시설투자(CAPEX) 증감률",
                        },
                    },
                },
            },
            {
                "task_id": "task_3",
                "metric_family": "concept_lookup",
                "metric_label": "2022년 시설투자(CAPEX) 총액",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "label": "시설투자(CAPEX) 총액",
                            "period": "2022년",
                            "rendered_value": "18조 1,168억원",
                        },
                    },
                },
            },
        ]

        feedback = self.agent._infer_planner_feedback_from_answer_slots(ordered_results)

        self.assertEqual(feedback, "")

    def test_aggregate_subtasks_ignores_failed_lookup_when_growth_slots_cover_value(self) -> None:
        self.agent.llm = _StubLLM(
            AggregateSynthesisOutput.model_validate(
                {
                    "final_answer": "2023년 시설투자(CAPEX) 총액은 53조 1,139억원이며, 이는 전년(2022년)의 53조 1,153억원 대비 0.0026% 감소한 수치입니다.",
                    "planner_feedback": "2023년 시설투자(CAPEX) 총액 direct value가 누락되었습니다.",
                }
            )
        )
        state = {
            "query": "2023년 메모리 반도체 업황 악화에도 불구하고 집행된 시설투자(CAPEX) 총액을 찾고, 전년(2022년) 대비 증감률을 계산해 줘.",
            "calc_subtasks": [
                {"task_id": "task_1"},
                {"task_id": "task_4"},
                {"task_id": "task_2"},
            ],
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 시설투자(CAPEX) 총액",
                    "answer": "2023년 시설투자(CAPEX) 총액 계산에 필요한 값(시설투자(CAPEX))을 문서 근거에서 충분히 확인하지 못해 계산할 수 없습니다.",
                    "status": "insufficient_operands",
                    "calculation_result": {},
                },
                {
                    "task_id": "task_4",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022년 시설투자(CAPEX)",
                    "answer": "2022년 시설투자(CAPEX)은 53조 1,153억원입니다.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "시설투자(CAPEX)",
                                "concept": "capital_expenditure_total",
                                "period": "2022",
                                "rendered_value": "53조 1,153억원",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_2",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "시설투자(CAPEX) 총액 증감률",
                    "answer": "2023년 연결기준 시설투자(CAPEX) 총액 증감률은 2023 시설투자(CAPEX) 53조 1,139억원이 시설투자(CAPEX) 53조 1,153억원 대비 0.0026% 감소한 결과입니다.",
                    "status": "ok",
                    "runtime_evidence": [
                        {
                            "evidence_id": "ev_003",
                            "support_level": "context",
                            "source_anchor": "[삼성전자 | 2023 | IV. 이사의 경영진단 및 분석의견]",
                            "claim": "2023년 세계 경제의 불확실성 지속 및 경기 둔화로 경영 여건이 악화되었으며, 특히 메모리 등 부품 사업이 약세를 보였습니다.",
                        }
                    ],
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "-0.0026%",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "시설투자(CAPEX) 총액 증감률",
                                "period": "2023",
                                "rendered_value": "-0.0026%",
                            },
                            "current_value": {
                                "status": "ok",
                                "role": "current_value",
                                "label": "2023 시설투자(CAPEX)",
                                "concept": "capital_expenditure_total",
                                "period": "2023",
                                "rendered_value": "53조 1,139억원",
                            },
                            "prior_value": {
                                "status": "ok",
                                "role": "prior_value",
                                "label": "시설투자(CAPEX)",
                                "concept": "capital_expenditure_total",
                                "period": "2022",
                                "rendered_value": "53조 1,153억원",
                            },
                        },
                    },
                },
            ],
            "plan_loop_count": 2,
            "artifacts": [],
            "selected_claim_ids": [],
        }

        updated = self.agent._aggregate_calculation_subtasks(state)

        self.assertEqual(updated["planner_feedback"], "")
        self.assertNotIn("완전히 확정할 수는 없습니다", updated["answer"])
        self.assertIn("메모리", updated["answer"])
        self.assertEqual(updated["calculation_result"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
