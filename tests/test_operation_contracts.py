import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

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
    _build_generic_required_operands,
    _build_generic_retrieval_queries,
    _label_implies_percent_metric,
    _normalise_operand_value,
    _operand_row_matches_requirement,
    _requires_direct_numeric_grounding,
)
from src.agent.financial_graph_models import EvidenceExtraction
from src.config.ontology import FinancialOntologyManager
import src.config.ontology as ontology_module


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
        return _StubStructuredLLM(self._response)


class _FailingStructuredLLM:
    def __call__(self, _prompt_value):
        raise RuntimeError("structured output disabled for test")

    def invoke(self, _prompt_value):
        raise RuntimeError("structured output disabled for test")


class _FailingLLM:
    def with_structured_output(self, _schema):
        return _FailingStructuredLLM()


class OperationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.ontology = FinancialOntologyManager(Path("src/config/financial_ontology_concepts_v3.draft.json"))

    def test_percent_label_inference_uses_generic_surface_markers_only(self) -> None:
        self.assertTrue(_label_implies_percent_metric("순이자마진"))
        self.assertTrue(_label_implies_percent_metric("부채비율"))
        self.assertFalse(_label_implies_percent_metric("NIM"))

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

    def test_percent_period_comparison_queries_are_compact_and_without_duplicate_year_tokens(self) -> None:
        queries = _build_generic_retrieval_queries(
            query="2023년 KB금융의 순이자마진(NIM) 수치를 사업보고서에서 찾고, 전년 대비 증감폭(%p)을 계산해 줘.",
            metric_label="순이자마진 차이",
            operand_specs=[
                {
                    "label": "2023년 순이자마진",
                    "aliases": ["순이자마진", "NIM"],
                    "concept": "net_interest_margin",
                    "role": "current_period",
                    "period_hint": "2023",
                },
                {
                    "label": "2022년 순이자마진",
                    "aliases": ["순이자마진", "NIM"],
                    "concept": "net_interest_margin",
                    "role": "prior_period",
                    "period_hint": "2022",
                },
            ],
            preferred_sections=["영업의 개황", "영업현황"],
            report_scope={"company": "KB금융", "year": 2023},
            constraints={"period_focus": "multi_period"},
        )
        self.assertTrue(any("2023년 2022년 순이자마진" in item for item in queries))
        self.assertFalse(any("2023년 2023" in item for item in queries))
        self.assertFalse(any("2022년 2022" in item for item in queries))

    def test_generic_required_operands_inherit_concept_metadata_when_label_is_known(self) -> None:
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            operands = _build_generic_required_operands(
                "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출하고, 전년 대비 증감액을 계산해 줘",
                {"company": "네이버", "year": 2023},
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(
            [(row["concept"], row["role"]) for row in operands],
            [
                ("income_before_income_taxes", "current_period"),
                ("income_before_income_taxes", "prior_period"),
            ],
        )
        self.assertTrue(all("income_statement" in row.get("preferred_statement_types", []) for row in operands))
        self.assertTrue(all(bool(row.get("surface_contract")) for row in operands))

    def test_parenthesized_won_value_normalizes_as_negative_krw(self) -> None:
        normalized_value, normalized_unit = _normalise_operand_value("(640,623,697,250)", "원")
        self.assertEqual(normalized_unit, "KRW")
        self.assertEqual(normalized_value, -640623697250.0)

    def test_operand_requirement_matching_respects_explicit_roles(self) -> None:
        row = {
            "label": "2023 법인세비용차감전순이익",
            "matched_operand_label": "법인세비용차감전순이익",
            "matched_operand_concept": "income_before_income_taxes",
            "matched_operand_role": "current_period",
        }
        current_req = {
            "label": "법인세비용차감전순이익",
            "concept": "income_before_income_taxes",
            "role": "current_period",
        }
        prior_req = {
            "label": "법인세비용차감전순이익",
            "concept": "income_before_income_taxes",
            "role": "prior_period",
        }
        self.assertTrue(_operand_row_matches_requirement(row, current_req))
        self.assertFalse(_operand_row_matches_requirement(row, prior_req))

    def test_difference_task_uses_deterministic_subtract_plan(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._plan_formula_calculation(
            {
                "query": "2023년 잉여현금흐름(FCF)을 영업활동현금흐름에서 유형자산 취득액을 차감하여 계산해 줘.",
                "active_subtask": {
                    "task_id": "task_fcf",
                    "metric_family": "concept_difference",
                    "metric_label": "잉여현금흐름(FCF)",
                    "operation_family": "difference",
                    "required_operands": [
                        {"label": "영업활동현금흐름", "role": "minuend", "required": True},
                        {"label": "유형자산 취득액", "role": "subtrahend", "required": True},
                    ],
                },
                "calculation_operands": [
                    {
                        "operand_id": "op_001",
                        "label": "2023 영업활동현금흐름",
                        "raw_value": "2,002,233,273,518",
                        "raw_unit": "원",
                        "normalized_value": 2002233273518.0,
                        "normalized_unit": "KRW",
                        "matched_operand_role": "minuend",
                    },
                    {
                        "operand_id": "op_002",
                        "label": "2023 유형자산 취득액",
                        "raw_value": "(640,623,697,250)",
                        "raw_unit": "원",
                        "normalized_value": -640623697250.0,
                        "normalized_unit": "KRW",
                        "matched_operand_role": "subtrahend",
                    },
                ],
                "artifacts": [],
                "tasks": [],
            }
        )
        plan = result["calculation_plan"]
        self.assertEqual(plan["status"], "ok")
        self.assertEqual(plan["operation"], "subtract")
        self.assertEqual(plan["formula"], "A + B")
        self.assertEqual(plan["ordered_operand_ids"], ["op_001", "op_002"])

    def test_formula_planner_prefers_resolved_runtime_trace_over_stale_flat_fields(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._plan_formula_calculation(
            {
                "query": "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출해 줘.",
                "active_subtask": {
                    "task_id": "task_lookup",
                    "metric_family": "concept_lookup",
                    "metric_label": "법인세비용차감전순이익",
                    "operation_family": "lookup",
                },
                "resolved_calculation_trace": {
                    "calculation_operands": [
                        {
                            "operand_id": "op_001",
                            "label": "2023 법인세비용차감전순이익",
                            "raw_value": "1,481,396,318",
                            "raw_unit": "천원",
                            "normalized_value": 1481396318000.0,
                            "normalized_unit": "KRW",
                        }
                    ],
                    "calculation_plan": {},
                    "calculation_result": {},
                },
                "calculation_operands": [],
                "calculation_plan": {"status": "stale"},
                "calculation_result": {"status": "stale"},
                "artifacts": [],
                "tasks": [],
            }
        )
        self.assertEqual(
            result["resolved_calculation_trace"]["calculation_plan"]["operation"],
            "lookup",
        )
        self.assertEqual(
            result["resolved_calculation_trace"]["calculation_operands"][0]["operand_id"],
            "op_001",
        )

    def test_formula_planner_prefers_task_ledger_over_stale_resolved_trace(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._plan_formula_calculation(
            {
                "query": "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출해 줘.",
                "active_subtask": {
                    "task_id": "task_lookup",
                    "metric_family": "concept_lookup",
                    "metric_label": "법인세비용차감전순이익",
                    "operation_family": "lookup",
                },
                "resolved_calculation_trace": {
                    "calculation_operands": [
                        {
                            "operand_id": "stale_row",
                            "label": "stale",
                            "raw_value": "999",
                            "raw_unit": "천원",
                            "normalized_value": 999000.0,
                            "normalized_unit": "KRW",
                        }
                    ],
                    "calculation_plan": {"status": "stale"},
                    "calculation_result": {"status": "stale"},
                },
                "tasks": [
                    {
                        "task_id": "task_lookup",
                        "kind": "calculation",
                        "status": "completed",
                        "artifact_ids": ["artifact:operands"],
                    }
                ],
                "artifacts": [
                    {
                        "artifact_id": "artifact:operands",
                        "task_id": "task_lookup",
                        "kind": "operand_set",
                        "payload": {
                            "calculation_operands": [
                                {
                                    "operand_id": "fresh_row",
                                    "label": "2023 법인세비용차감전순이익",
                                    "raw_value": "1,481,396,318",
                                    "raw_unit": "천원",
                                    "normalized_value": 1481396318000.0,
                                    "normalized_unit": "KRW",
                                }
                            ]
                        },
                    }
                ],
                "calculation_operands": [],
                "calculation_plan": {},
                "calculation_result": {},
            }
        )
        self.assertEqual(
            result["resolved_calculation_trace"]["calculation_operands"][0]["operand_id"],
            "fresh_row",
        )
        self.assertEqual(
            result["resolved_calculation_trace"]["calculation_plan"]["operation"],
            "lookup",
        )

    def test_compositional_difference_uses_primary_value_without_period_slots(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._execute_calculation(
            {
                "query": "2023년 잉여현금흐름(FCF)을 영업활동현금흐름에서 유형자산 취득액을 차감하여 계산해 줘.",
                "active_subtask": {
                    "task_id": "task_fcf",
                    "metric_family": "concept_difference",
                    "metric_label": "잉여현금흐름(FCF)",
                    "operation_family": "difference",
                    "required_operands": [
                        {"label": "영업활동현금흐름", "role": "minuend", "required": True},
                        {"label": "유형자산 취득액", "role": "subtrahend", "required": True},
                    ],
                },
                "calculation_operands": [
                    {
                        "operand_id": "op_001",
                        "evidence_id": "cf_2023",
                        "label": "2023 영업활동현금흐름",
                        "raw_value": "2,002,233,273,518",
                        "raw_unit": "원",
                        "normalized_value": 2002233273518.0,
                        "normalized_unit": "KRW",
                        "period": "2023",
                        "matched_operand_role": "minuend",
                        "matched_operand_concept": "operating_cash_flow",
                    },
                    {
                        "operand_id": "op_002",
                        "evidence_id": "ppe_2023",
                        "label": "2023 유형자산의 취득",
                        "raw_value": "(640,623,697,250)",
                        "raw_unit": "원",
                        "normalized_value": -640623697250.0,
                        "normalized_unit": "KRW",
                        "period": "2023",
                        "matched_operand_role": "subtrahend",
                        "matched_operand_concept": "property_plant_equipment_acquisition",
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
                    "formula": "A + B",
                    "pairwise_formula": "",
                    "result_unit": "",
                    "operation_text": "영업활동현금흐름 - 유형자산 취득액",
                    "explanation": "fcf",
                },
                "artifacts": [],
                "tasks": [],
            }
        )
        slots = result["calculation_result"]["answer_slots"]
        self.assertEqual(slots["primary_value"]["role"], "primary_value")
        self.assertEqual(slots["current_value"]["rendered_value"], "2조 22억원")
        self.assertEqual(slots["prior_value"]["rendered_value"], "-6,406억원")
        self.assertEqual(slots["delta_value"]["rendered_value"], "1조 3,616억원")

    def test_rendered_subtraction_answer_rewrites_double_negative_subtrahend(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            SimpleNamespace(
                final_answer="2023년 연결기준 잉여현금흐름(FCF)은 1조 3,616억원입니다. 이는 2023년 영업활동현금흐름 2조 22억원에서 2023년 유형자산의 취득 -6,406억원을 차감하여 계산된 결과입니다."
            )
        )
        state = {
            "query": "2023년 잉여현금흐름(FCF)을 영업활동현금흐름에서 유형자산 취득액을 차감하여 계산해 줘.",
            "calculation_plan": {
                "status": "ok",
                "mode": "single_value",
                "operation": "subtract",
                "ordered_operand_ids": ["op_001", "op_002"],
                "variable_bindings": [
                    {"variable": "A", "operand_id": "op_001"},
                    {"variable": "B", "operand_id": "op_002"},
                ],
                "formula": "A + B",
                "pairwise_formula": "",
                "result_unit": "",
                "operation_text": "영업활동현금흐름 + 유형자산의 취득",
                "explanation": "sign-aware subtraction",
            },
            "calculation_operands": [
                {
                    "operand_id": "op_001",
                    "label": "2023 영업활동현금흐름",
                    "raw_value": "2,002,233,273,518",
                    "raw_unit": "원",
                    "normalized_value": 2002233273518.0,
                    "normalized_unit": "KRW",
                    "matched_operand_role": "minuend",
                },
                {
                    "operand_id": "op_002",
                    "label": "2023 유형자산의 취득",
                    "raw_value": "(640,623,697,250)",
                    "raw_unit": "원",
                    "normalized_value": -640623697250.0,
                    "normalized_unit": "KRW",
                    "matched_operand_role": "subtrahend",
                },
            ],
            "calculation_result": {
                "status": "ok",
                "result_value": 1361609576268.0,
                "result_unit": "KRW",
                "rendered_value": "1조 3,616억원",
                "answer_slots": {
                    "operation_family": "difference",
                    "components_by_role": {
                        "minuend": [
                            {
                                "status": "ok",
                                "role": "minuend",
                                "label": "2023 영업활동현금흐름",
                                "concept": "operating_cash_flow",
                                "period": "2023",
                                "raw_value": "2,002,233,273,518",
                                "raw_unit": "원",
                                "normalized_value": 2002233273518.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "2조 22억원",
                                "source_row_id": "cf_2023",
                                "source_row_ids": ["cf_2023"],
                            }
                        ],
                        "subtrahend": [
                            {
                                "status": "ok",
                                "role": "subtrahend",
                                "label": "2023 유형자산의 취득",
                                "concept": "property_plant_equipment_acquisition",
                                "period": "2023",
                                "raw_value": "(640,623,697,250)",
                                "raw_unit": "원",
                                "normalized_value": -640623697250.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "-6,406억원",
                                "source_row_id": "ppe_2023",
                                "source_row_ids": ["ppe_2023"],
                            }
                        ],
                    },
                },
            },
        }

        rendered = agent._render_calculation_answer(state)

        self.assertIn("6,406억원을 차감", rendered["answer"])
        self.assertNotIn("-6,406억원을 차감", rendered["answer"])

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
        self.assertEqual(calc["answer_slots"]["operation_family"], "difference")
        self.assertEqual(calc["answer_slots"]["current_value"]["status"], "ok")
        self.assertEqual(calc["answer_slots"]["prior_value"]["status"], "ok")
        self.assertEqual(calc["answer_slots"]["delta_value"]["status"], "ok")
        self.assertEqual(
            calc["answer_slots"]["current_value"]["rendered_value"],
            "1조 4,814억원",
        )
        self.assertEqual(
            calc["answer_slots"]["prior_value"]["rendered_value"],
            "1조 837억원",
        )
        self.assertEqual(
            calc["answer_slots"]["delta_value"]["rendered_value"],
            "3,977억원",
        )
        self.assertEqual(calc["answer_slots"]["direction"], "increase")
        self.assertEqual(calc["answer_slots"]["current_value"]["source_row_id"], "cand_2023")
        self.assertEqual(calc["answer_slots"]["prior_value"]["source_row_id"], "cand_2022")

    def test_percent_difference_preserves_two_decimal_percent_rendering(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._execute_calculation(
            {
                "query": "2023년 KB금융의 순이자마진(NIM) 수치를 사업보고서에서 찾고, 전년 대비 증감폭(%p)을 계산해 줘.",
                "active_subtask": {
                    "task_id": "task_nim_diff",
                    "metric_family": "concept_difference",
                    "metric_label": "순이자마진 증감폭",
                    "query": "2023년 KB금융의 순이자마진(NIM) 수치를 사업보고서에서 찾고, 전년 대비 증감폭(%p)을 계산해 줘.",
                    "operation_family": "difference",
                },
                "calculation_operands": [
                    {
                        "operand_id": "op_001",
                        "evidence_id": "nim_2023",
                        "label": "2023년 명목순이자마진(NIM)",
                        "normalized_value": 1.83,
                        "normalized_unit": "PERCENT",
                        "raw_value": "1.83",
                        "raw_unit": "%",
                        "period": "2023",
                        "matched_operand_role": "current_period",
                    },
                    {
                        "operand_id": "op_002",
                        "evidence_id": "nim_2022",
                        "label": "2022년 명목순이자마진(NIM)",
                        "normalized_value": 1.73,
                        "normalized_unit": "PERCENT",
                        "raw_value": "1.73",
                        "raw_unit": "%",
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
                    "result_unit": "%p",
                    "operation_text": "순이자마진 증감폭",
                    "explanation": "difference",
                },
                "artifacts": [],
                "tasks": [],
            }
        )
        calc = result["calculation_result"]
        self.assertEqual(calc["status"], "ok")
        self.assertEqual(calc["rendered_value"], "0.10%p")
        self.assertEqual(calc["answer_slots"]["primary_value"]["status"], "ok")
        self.assertEqual(calc["answer_slots"]["current_value"]["rendered_value"], "1.83%")
        self.assertEqual(calc["answer_slots"]["prior_value"]["rendered_value"], "1.73%")
        self.assertEqual(calc["answer_slots"]["delta_value"]["rendered_value"], "0.10%p")

    def test_failed_lookup_emits_explicit_missing_primary_slot(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._execute_calculation(
            {
                "query": "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출해 줘.",
                "active_subtask": {
                    "task_id": "task_lookup_missing",
                    "metric_family": "concept_lookup",
                    "metric_label": "법인세비용차감전순이익",
                    "query": "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출해 줘.",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "법인세비용차감전순이익",
                            "concept": "income_before_income_taxes",
                            "role": "operand",
                            "period_hint": "2023년",
                        }
                    ],
                },
                "calculation_operands": [],
                "calculation_plan": {
                    "status": "incomplete",
                    "mode": "none",
                    "operation": "none",
                    "ordered_operand_ids": [],
                    "variable_bindings": [],
                    "formula": "",
                    "pairwise_formula": "",
                    "result_unit": "천원",
                    "operation_text": "",
                    "explanation": "no operation or operands",
                },
            }
        )
        calc = result["calculation_result"]
        self.assertEqual(calc["status"], "insufficient_operands")
        self.assertEqual(calc["answer_slots"]["operation_family"], "lookup")
        self.assertEqual(calc["answer_slots"]["primary_value"]["status"], "missing")
        self.assertEqual(calc["answer_slots"]["primary_value"]["label"], "법인세비용차감전순이익")
        self.assertEqual(calc["answer_slots"]["primary_value"]["concept"], "income_before_income_taxes")

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

    def test_ratio_task_with_explicit_concepts_requires_direct_numeric_grounding(self) -> None:
        self.assertTrue(
            _requires_direct_numeric_grounding(
                {
                    "operation_family": "ratio",
                    "required_operands": [
                        {"label": "부채총계", "concept": "total_liabilities", "role": "numerator_1", "required": True},
                        {"label": "자본총계", "concept": "total_equity", "role": "denominator_1", "required": True},
                    ],
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
