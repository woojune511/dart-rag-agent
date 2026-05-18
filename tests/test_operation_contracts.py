import sys
import unittest
from pathlib import Path

from langchain_core.documents import Document

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_helpers import (
    _build_concept_task_constraints,
    _build_generic_retrieval_queries,
    _operand_row_matches_requirement,
)
from src.agent.financial_graph_models import EvidenceExtraction
from src.config.ontology import FinancialOntologyManager


class _StubStructuredLLM:
    def __init__(self, response):
        self._response = response

    def invoke(self, _prompt_value):
        return self._response


class _StubLLM:
    def __init__(self, response):
        self._response = response

    def with_structured_output(self, _schema):
        return _StubStructuredLLM(self._response)


class OperationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ontology = FinancialOntologyManager(Path("src/config/financial_ontology_concepts_v3.draft.json"))

    def test_lookup_task_prefers_current_period_when_operand_role_is_current(self) -> None:
        constraints = _build_concept_task_constraints(
            "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출해 줘.",
            {"company": "네이버", "year": 2023},
            self.ontology,
            operand_specs=[
                {
                    "label": "법인세비용차감전순이익",
                    "role": "current_period",
                }
            ],
            operation_family="lookup",
        )
        self.assertEqual(constraints["period_focus"], "current")

    def test_difference_task_uses_multi_period_when_current_and_prior_are_both_required(self) -> None:
        constraints = _build_concept_task_constraints(
            "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출하고 전년 대비 증감액을 계산해 줘.",
            {"company": "네이버", "year": 2023},
            self.ontology,
            operand_specs=[
                {"label": "법인세비용차감전순이익", "role": "current_period"},
                {"label": "법인세비용차감전순이익", "role": "prior_period"},
            ],
            operation_family="difference",
        )
        self.assertEqual(constraints["period_focus"], "multi_period")

    def test_retrieval_queries_include_prior_year_for_prior_period_operand(self) -> None:
        queries = _build_generic_retrieval_queries(
            query="2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출하고 전년 대비 증감액을 계산해 줘.",
            metric_label="법인세비용차감전순이익 증감액",
            operand_specs=[
                {
                    "label": "법인세비용차감전순이익",
                    "aliases": ["법인세비용차감전순손익"],
                    "role": "current_period",
                    "period_hint": "당기",
                },
                {
                    "label": "법인세비용차감전순이익",
                    "aliases": ["법인세비용차감전순손익"],
                    "role": "prior_period",
                    "period_hint": "전기",
                },
            ],
            preferred_sections=["연결 손익계산서"],
            report_scope={"company": "네이버", "year": 2023},
            constraints={"period_focus": "multi_period"},
        )
        self.assertTrue(any("2022년" in item and "전기" in item for item in queries))
        self.assertTrue(any("2023년" in item and "당기" in item for item in queries))

    def test_difference_result_exposes_structured_value_slots(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._execute_calculation(
            {
                "query": "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출하고 전년 대비 증감액을 계산해 줘.",
                "active_subtask": {
                    "task_id": "task_2",
                    "metric_family": "concept_difference",
                    "metric_label": "법인세비용차감전순이익 증감액",
                    "query": "2023년 연결기준 법인세비용차감전순이익 증감액을 계산해 줘.",
                    "operation_family": "difference",
                },
                "calculation_operands": [
                    {
                        "operand_id": "op_001",
                        "evidence_id": "cand_2023",
                        "label": "2023년 법인세비용차감전순이익",
                        "normalized_value": 1481396318000.0,
                        "normalized_unit": "KRW",
                        "raw_value": "1,481,396,318",
                        "raw_unit": "천원",
                        "period": "2023",
                        "matched_operand_role": "current_period",
                    },
                    {
                        "operand_id": "op_002",
                        "evidence_id": "cand_2022",
                        "label": "2022년 법인세비용차감전순이익",
                        "normalized_value": 1083717091000.0,
                        "normalized_unit": "KRW",
                        "raw_value": "1,083,717,091",
                        "raw_unit": "천원",
                        "period": "2022",
                        "matched_operand_role": "prior_period",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "subtract",
                    "ordered_operand_ids": ["op_001", "op_002"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "op_001"},
                        {"variable": "B", "operand_id": "op_002"},
                    ],
                    "formula": "A - B",
                    "pairwise_formula": "",
                    "result_unit": "",
                    "operation_text": "법인세비용차감전순이익 증감액",
                    "explanation": "difference",
                },
                "artifacts": [],
                "tasks": [],
            }
        )
        calc = result["calculation_result"]
        self.assertEqual(calc["status"], "ok")
        self.assertEqual(calc["current_period"], "2023")
        self.assertEqual(calc["prior_period"], "2022")
        self.assertEqual(calc["current_value"], 1481396318000.0)
        self.assertEqual(calc["prior_value"], 1083717091000.0)
        self.assertEqual(calc["delta_value"], 397679227000.0)
        self.assertEqual(calc["source_row_ids"], ["cand_2023", "cand_2022"])

    def test_lookup_plan_requires_single_direct_operand_instead_of_reconstruction(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        plan_result = agent._plan_formula_calculation(
            {
                "query": "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출해 줘.",
                "active_subtask": {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 법인세비용차감전순이익",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "2023년 법인세비용차감전순이익",
                            "concept": "income_before_income_taxes",
                            "required": True,
                        }
                    ],
                },
                "calculation_operands": [
                    {
                        "operand_id": "op_001",
                        "label": "2023년 계속영업순이익",
                        "raw_value": "985,018",
                        "raw_unit": "백만원",
                        "normalized_value": 985018000000.0,
                        "normalized_unit": "KRW",
                        "period": "2023년",
                    },
                    {
                        "operand_id": "op_002",
                        "label": "2023년 법인세비용",
                        "raw_value": "496,378",
                        "raw_unit": "백만원",
                        "normalized_value": 496378000000.0,
                        "normalized_unit": "KRW",
                        "period": "2023년",
                    },
                ],
                "artifacts": [],
                "tasks": [],
            }
        )
        self.assertEqual(plan_result["calculation_plan"]["status"], "incomplete")
        self.assertEqual(plan_result["calculation_plan"]["mode"], "none")
        self.assertFalse(plan_result["planner_debug_trace"]["llm_invoked"])
        self.assertTrue(plan_result["planner_debug_trace"]["guard_applied"])

    def test_lookup_plan_uses_single_direct_operand_when_available(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        plan_result = agent._plan_formula_calculation(
            {
                "query": "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출해 줘.",
                "active_subtask": {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 법인세비용차감전순이익",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "2023년 법인세비용차감전순이익",
                            "concept": "income_before_income_taxes",
                            "required": True,
                        }
                    ],
                },
                "calculation_operands": [
                    {
                        "operand_id": "op_001",
                        "label": "2023년 법인세비용차감전순이익",
                        "matched_operand_label": "2023년 법인세비용차감전순이익",
                        "matched_operand_concept": "income_before_income_taxes",
                        "raw_value": "1,481,396,318",
                        "raw_unit": "천원",
                        "normalized_value": 1481396318000.0,
                        "normalized_unit": "KRW",
                        "period": "2023년",
                    }
                ],
                "artifacts": [],
                "tasks": [],
            }
        )
        self.assertEqual(plan_result["calculation_plan"]["status"], "ok")
        self.assertEqual(plan_result["calculation_plan"]["operation"], "lookup")
        self.assertEqual(plan_result["calculation_plan"]["formula"], "A")
        self.assertFalse(plan_result["planner_debug_trace"]["llm_invoked"])

    def test_operand_requirement_rejects_surrogate_metric_label(self) -> None:
        operand = {
            "label": "2023년 법인세비용차감전순이익",
            "aliases": ["법인세비용차감전순이익", "세전이익"],
            "concept": "income_before_income_taxes",
            "role": "current_period",
            "required": True,
        }
        row = {
            "label": "2023년 법인세비용차감전순이익 (계속영업순이익)",
            "period": "2023년",
            "raw_value": "985,018",
            "raw_unit": "백만원",
        }
        self.assertFalse(_operand_row_matches_requirement(row, operand))

    def test_evidence_item_conflict_rejects_continuing_income_quote_for_pretax_operand(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        operand = {
            "label": "2023년 법인세비용차감전순이익",
            "aliases": ["법인세비용차감전순이익", "세전이익"],
            "concept": "income_before_income_taxes",
            "role": "current_period",
            "required": True,
        }
        item = {
            "source_anchor": "[NAVER | 2023 | III. 재무에 관한 사항 > 1. 요약재무정보]",
            "claim": "2023년 NAVER의 연결 손익계산서상 법인세비용차감전순이익은 985,018백만원이며, 2022년에는 673,180백만원입니다.",
            "quote_span": "계속영업순이익 | 985,018 | 673,180",
        }
        self.assertTrue(agent._evidence_item_conflicts_with_operand(item, operand))

    def test_extract_evidence_preserves_missing_for_direct_lookup_without_context_fallback(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(EvidenceExtraction(coverage="missing", evidence=[]))
        state = {
            "query": "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출해 줘.",
            "query_type": "qa",
            "topic": "법인세비용차감전순이익",
            "retrieved_docs": [
                (
                    Document(
                        page_content="법인세용차감전순손익 | 1,481,396,318 | 1,083,717,091",
                        metadata={
                            "company": "NAVER",
                            "year": 2023,
                            "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석 > 28. 법인세용",
                            "statement_type": "notes",
                        },
                    ),
                    1.0,
                )
            ],
            "active_subtask": {
                "task_id": "task_lookup_missing",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 법인세비용차감전순이익",
                "query": "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출해 줘.",
                "operation_family": "lookup",
                "required_operands": [
                    {
                        "label": "2023년 법인세비용차감전순이익",
                        "concept": "income_before_income_taxes",
                        "role": "current_period",
                        "required": True,
                    }
                ],
            },
        }

        result = agent._extract_evidence(state)

        self.assertEqual(result["evidence_status"], "missing")
        self.assertEqual(result["evidence_items"], [])
        self.assertEqual(result["evidence_bullets"], [])


if __name__ == "__main__":
    unittest.main()
