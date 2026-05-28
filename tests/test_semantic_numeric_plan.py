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
    _infer_period_focus,
    _is_percent_point_difference_query,
    _merge_operand_rows,
    _missing_required_operands,
    _parse_unstructured_table_row_cells,
)
from src.agent.financial_graph_helpers import _extract_segment_labels_from_query
from src.agent.financial_graph_helpers import _annotate_task_dependencies
from src.agent.financial_graph_planning import _llm_plan_preserves_analysis_shape, _llm_plan_preserves_segment_sum_shape
from src.agent.financial_graph_models import ConceptPlannerOutput


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


class SemanticNumericPlanTests(unittest.TestCase):
    def test_hybrid_numeric_query_appends_narrative_summary_subtask(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent._build_llm_concept_numeric_plan = lambda **_kwargs: None
        state = {
            "query": "2023년 커머스 부문 매출 성장률을 계산하고, 포시마크 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            "query_type": "trend",
            "intent": "trend",
            "topic": "커머스 부문 매출 성장률 및 포시마크 인수 영향",
            "report_scope": {
                "company": "네이버",
                "year": 2023,
            },
            "planner_mode": "initial",
            "planner_feedback": "",
            "plan_loop_count": 0,
            "target_metric_family": "",
            "target_metric_family_hint": "",
            "companies": ["네이버"],
            "years": [2023, 2022],
            "section_filter": None,
            "tasks": [],
            "artifacts": [],
        }

        result = agent._plan_semantic_numeric_tasks(state)

        self.assertGreaterEqual(len(result["calc_subtasks"]), 4)
        self.assertEqual(result["calc_subtasks"][-1]["operation_family"], "narrative_summary")
        self.assertEqual(result["active_subtask"]["operation_family"], "lookup")
        self.assertTrue(any("영향" in str(item) for item in result["calc_subtasks"][-1]["retrieval_queries"]))
        self.assertTrue(
            any("연결 편입 효과" in str(item) for item in result["calc_subtasks"][-1]["retrieval_queries"])
        )
        self.assertTrue(
            any("영업수익 증가" in str(item) for item in result["calc_subtasks"][-1]["retrieval_queries"])
        )

    def test_dividend_policy_query_appends_dividend_focused_narrative_subtask(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent._build_llm_concept_numeric_plan = lambda **_kwargs: None
        state = {
            "query": "2023년 연결 현금흐름표에서 '배당금 지급'으로 유출된 현금 규모를 찾고, 사업보고서의 '배당에 관한 사항'을 바탕으로 2024~2026년 주주환원 정책을 요약해 줘.",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "topic": "배당금 지급과 주주환원 정책",
            "report_scope": {
                "company": "삼성전자",
                "year": 2023,
            },
            "planner_mode": "initial",
            "planner_feedback": "",
            "plan_loop_count": 0,
            "target_metric_family": "",
            "target_metric_family_hint": "",
            "companies": ["삼성전자"],
            "years": [2023],
            "section_filter": None,
            "tasks": [],
            "artifacts": [],
        }

        result = agent._plan_semantic_numeric_tasks(state)

        numeric_task = result["calc_subtasks"][0]
        narrative_task = result["calc_subtasks"][-1]
        self.assertIn("배당에 관한 사항", numeric_task["preferred_sections"])
        self.assertIn("유동성 및 자금조달", numeric_task["preferred_sections"])
        self.assertEqual(narrative_task["operation_family"], "narrative_summary")
        self.assertTrue(
            any("배당에 관한 사항 주주환원 정책" in str(item) for item in narrative_task["retrieval_queries"])
        )
        self.assertTrue(
            any("잉여현금흐름 정규배당 추가 환원" in str(item) for item in narrative_task["retrieval_queries"])
        )
        self.assertIn("III. 재무에 관한 사항 > 6. 배당에 관한 사항", narrative_task["preferred_sections"])

    def test_dependency_annotation_reorders_lookup_tasks_before_growth_rate(self) -> None:
        tasks = _annotate_task_dependencies(
            [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "시설투자(CAPEX) 증감률",
                    "query": "2023년 시설투자(CAPEX) 총액과 전년 대비 증감률을 계산해 줘.",
                    "operation_family": "growth_rate",
                    "required_operands": [
                        {"label": "2023년 시설투자(CAPEX) 총액", "concept": "capital_expenditure_total", "role": "current_period"},
                        {"label": "2022년 시설투자(CAPEX) 총액", "concept": "capital_expenditure_total", "role": "prior_period"},
                    ],
                },
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 시설투자(CAPEX) 총액",
                    "query": "2023년 시설투자(CAPEX) 총액을 찾아 줘.",
                    "operation_family": "lookup",
                    "required_operands": [
                        {"label": "2023년 시설투자(CAPEX) 총액", "concept": "capital_expenditure_total", "role": "current_period"},
                    ],
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022년 시설투자(CAPEX) 총액",
                    "query": "2022년 시설투자(CAPEX) 총액을 찾아 줘.",
                    "operation_family": "lookup",
                    "required_operands": [
                        {"label": "2022년 시설투자(CAPEX) 총액", "concept": "capital_expenditure_total", "role": "prior_period"},
                    ],
                },
            ],
            report_scope={"company": "삼성전자", "year": 2023},
        )

        self.assertEqual([task["task_id"] for task in tasks], ["task_1", "task_3", "task_2"])
        self.assertEqual(tasks[2]["depends_on"], ["task_1", "task_3"])
        self.assertEqual(
            [(item["role"], item["preferred_task_id"]) for item in tasks[2]["inputs"]],
            [("current_period", "task_1"), ("prior_period", "task_3")],
        )

    def test_dependency_annotation_synthesizes_missing_prior_lookup_task(self) -> None:
        tasks = _annotate_task_dependencies(
            [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 시설투자(CAPEX) 총액",
                    "query": "2023년 시설투자(CAPEX) 총액을 찾아 줘.",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "시설투자(CAPEX)",
                            "concept": "capital_expenditure_total",
                            "role": "current_period",
                            "preferred_sections": ["원재료 및 생산설비"],
                        },
                    ],
                },
                {
                    "task_id": "task_2",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "시설투자(CAPEX) 증감률",
                    "query": "2023년 시설투자(CAPEX) 총액과 전년 대비 증감률을 계산해 줘.",
                    "operation_family": "growth_rate",
                    "required_operands": [
                        {
                            "label": "시설투자(CAPEX)",
                            "concept": "capital_expenditure_total",
                            "role": "current_period",
                            "preferred_sections": ["원재료 및 생산설비"],
                        },
                        {
                            "label": "시설투자(CAPEX)",
                            "concept": "capital_expenditure_total",
                            "role": "prior_period",
                            "preferred_sections": ["원재료 및 생산설비"],
                        },
                    ],
                    "preferred_sections": ["원재료 및 생산설비"],
                    "constraints": {"consolidation_scope": "consolidated", "period_focus": "multi_period", "entity_scope": "company", "segment_scope": "none"},
                },
            ],
            report_scope={"company": "삼성전자", "year": 2023},
        )

        self.assertEqual([task["task_id"] for task in tasks], ["task_1", "task_3", "task_2"])
        self.assertEqual(tasks[1]["operation_family"], "lookup")
        self.assertEqual(tasks[1]["metric_family"], "concept_lookup")
        self.assertEqual(tasks[1]["required_operands"][0]["role"], "prior_period")
        self.assertIn("2022년", tasks[1]["metric_label"])
        self.assertEqual(tasks[2]["depends_on"], ["task_1", "task_3"])

    def test_dependency_annotation_synthesizes_lookup_tasks_for_ratio(self) -> None:
        tasks = _annotate_task_dependencies(
            [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_ratio",
                    "metric_label": "종업원급여 비중",
                    "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
                    "operation_family": "ratio",
                    "required_operands": [
                        {
                            "label": "종업원급여",
                            "concept": "employee_benefits_expense",
                            "role": "numerator_1",
                            "preferred_sections": ["영업비용"],
                        },
                        {
                            "label": "영업비용",
                            "concept": "operating_expense_total",
                            "role": "denominator_1",
                            "preferred_sections": ["영업비용"],
                        },
                    ],
                    "preferred_sections": ["영업비용"],
                    "constraints": {
                        "consolidation_scope": "consolidated",
                        "period_focus": "current",
                        "entity_scope": "company",
                        "segment_scope": "none",
                    },
                }
            ],
            report_scope={"company": "네이버", "year": 2023},
        )

        self.assertEqual([task["task_id"] for task in tasks], ["task_2", "task_3", "task_1"])
        self.assertEqual([task["operation_family"] for task in tasks], ["lookup", "lookup", "ratio"])
        self.assertEqual(tasks[2]["depends_on"], ["task_2", "task_3"])
        self.assertEqual(
            [(item["role"], item["preferred_task_id"]) for item in tasks[2]["inputs"]],
            [("numerator_1", "task_2"), ("denominator_1", "task_3")],
        )
        self.assertEqual(
            [(task["metric_label"], task["required_operands"][0]["role"]) for task in tasks[:2]],
            [("2023년 종업원급여", "numerator_1"), ("2023년 영업비용", "denominator_1")],
        )
        self.assertNotIn("prefer_value_roles", tasks[0]["required_operands"][0].get("binding_policy") or {})
        self.assertNotIn("prefer_aggregation_stages", tasks[1]["required_operands"][0].get("binding_policy") or {})
        self.assertEqual(tasks[1]["preferred_statement_types"][:2], ["income_statement", "summary_financials"])
        self.assertEqual(tasks[1]["preferred_sections"][:4], ["연결 손익계산서", "손익계산서", "요약재무정보", "영업비용"])

    def test_dependency_annotation_synthesizes_lookup_tasks_for_difference(self) -> None:
        tasks = _annotate_task_dependencies(
            [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_difference",
                    "metric_label": "법인세비용차감전순이익 증감액",
                    "query": "2023년 법인세비용차감전순이익과 전년 대비 증감액을 계산해 줘",
                    "operation_family": "difference",
                    "required_operands": [
                        {
                            "label": "2023년 법인세비용차감전순이익",
                            "concept": "income_before_income_taxes",
                            "role": "current_period",
                            "preferred_sections": ["연결 손익계산서"],
                        },
                        {
                            "label": "2022년 법인세비용차감전순이익",
                            "concept": "income_before_income_taxes",
                            "role": "prior_period",
                            "preferred_sections": ["연결 손익계산서"],
                        },
                    ],
                    "preferred_sections": ["연결 손익계산서"],
                    "constraints": {
                        "consolidation_scope": "consolidated",
                        "period_focus": "multi_period",
                        "entity_scope": "company",
                        "segment_scope": "none",
                    },
                }
            ],
            report_scope={"company": "네이버", "year": 2023},
        )

        self.assertEqual([task["task_id"] for task in tasks], ["task_2", "task_3", "task_1"])
        self.assertEqual([task["operation_family"] for task in tasks], ["lookup", "lookup", "difference"])
        self.assertEqual(tasks[2]["depends_on"], ["task_2", "task_3"])
        self.assertEqual(
            [(item["role"], item["preferred_task_id"]) for item in tasks[2]["inputs"]],
            [("current_period", "task_2"), ("prior_period", "task_3")],
        )
        self.assertEqual(
            [(task["metric_label"], task["required_operands"][0]["role"]) for task in tasks[:2]],
            [("2023년 법인세비용차감전순이익", "current_period"), ("2022년 법인세비용차감전순이익", "prior_period")],
        )

    def test_dependency_annotation_synthesizes_lookup_tasks_for_segment_sum(self) -> None:
        tasks = _annotate_task_dependencies(
            [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_sum",
                    "metric_label": "SDC 및 Harman 부문 매출 합계",
                    "query": "삼성전자 2024 사업보고서에서 SDC와 Harman 부문의 매출 합계는 얼마인가요?",
                    "operation_family": "sum",
                    "required_operands": [
                        {
                            "label": "SDC 매출액",
                            "concept": "revenue",
                            "role": "addend_1",
                            "preferred_sections": ["매출 및 수주상황"],
                            "binding_policy": {"segment_label": "SDC"},
                        },
                        {
                            "label": "Harman 매출액",
                            "concept": "revenue",
                            "role": "addend_2",
                            "preferred_sections": ["매출 및 수주상황"],
                            "binding_policy": {"segment_label": "Harman"},
                        },
                    ],
                    "preferred_sections": ["매출 및 수주상황"],
                    "constraints": {
                        "consolidation_scope": "consolidated",
                        "period_focus": "current",
                        "entity_scope": "company",
                        "segment_scope": "segment",
                    },
                }
            ],
            report_scope={"company": "삼성전자", "year": 2024},
        )

        self.assertEqual([task["task_id"] for task in tasks], ["task_2", "task_3", "task_1"])
        self.assertEqual([task["operation_family"] for task in tasks], ["lookup", "lookup", "sum"])
        self.assertEqual(tasks[2]["depends_on"], ["task_2", "task_3"])
        self.assertEqual(
            [(item["role"], item["preferred_task_id"]) for item in tasks[2]["inputs"]],
            [("addend_1", "task_2"), ("addend_2", "task_3")],
        )
        self.assertEqual(
            [
                (
                    task["metric_label"],
                    task["required_operands"][0]["role"],
                    dict(task["required_operands"][0].get("binding_policy") or {}).get("segment_label"),
                )
                for task in tasks[:2]
            ],
            [("2024년 SDC 매출액", "addend_1", "SDC"), ("2024년 Harman 매출액", "addend_2", "Harman")],
        )

    def test_extract_entities_keeps_metric_family_hint_empty_by_default(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._extract_entities(
            {
                "query": "2023년 연결 기준 부채비율을 계산해 줘",
                "intent": "comparison",
                "query_type": "comparison",
                "report_scope": {"company": "삼성전자", "year": 2023},
            }
        )

        self.assertEqual(result["companies"], ["삼성전자"])
        self.assertEqual(result["years"], [2023])
        self.assertEqual(result["target_metric_family"], "")
        self.assertEqual(result["target_metric_family_hint"], "")

    def test_calc_metric_family_prefers_active_subtask_only(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        self.assertEqual(
            agent._calc_metric_family(
                {
                    "active_subtask": {"metric_family": "concept_ratio"},
                    "target_metric_family": "debt_ratio",
                }
            ),
            "concept_ratio",
        )
        self.assertEqual(
            agent._calc_metric_family(
                {
                    "active_subtask": {},
                    "target_metric_family": "debt_ratio",
                }
            ),
            "",
        )

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
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_v2.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="2023년 연결 손익계산서에서 '법인세비용차감전순이익'을 추출하고, 전년 대비 증감액을 계산해 줘.",
                topic="법인세비용차감전순이익",
                intent="comparison",
                report_scope={"company": "네이버", "year": 2023, "report_type": "사업보고서"},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(plan["status"], "heuristic_fallback")
        self.assertIn("planner_no_metric_keys", plan["planner_notes"])
        self.assertIn("planner_fallback:heuristic_numeric_task", plan["planner_notes"])
        self.assertTrue(any(str(note).startswith("planner_ontology_matches:") for note in plan["planner_notes"]))
        self.assertEqual(len(plan["tasks"]), 1)
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "generic_numeric")
        self.assertTrue(task["metric_label"])
        operand_labels = [row["label"] for row in task["required_operands"]]
        self.assertEqual(
            operand_labels,
            ["2023년 법인세비용차감전순이익", "2022년 법인세비용차감전순이익"],
        )
        self.assertIn("income_statement", task["preferred_statement_types"])
        self.assertIn("연결 손익계산서", task["preferred_sections"])
        self.assertIn("법인세비용", task["preferred_sections"])

    def test_fallback_builds_explicit_operand_list_for_multi_operand_ratio(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_v2.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="2023년 연결 재무상태표에서 유·무형자산의 총합 대비 차입금(단기차입금, 장기차입금, 사채 합산)의 비중을 계산해 줘.",
                topic="유무형자산 대비 차입금 비중",
                intent="comparison",
                report_scope={"company": "SK하이닉스", "year": 2023, "report_type": "사업보고서", "consolidation": "연결"},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertIn(plan["status"], {"heuristic_fallback", "concept_fallback"})
        task = plan["tasks"][0]
        operand_labels = [row["label"] for row in task["required_operands"]]
        operand_concepts = [row.get("concept", "") for row in task["required_operands"]]
        self.assertIn("short_term_borrowings", operand_concepts)
        self.assertIn("long_term_borrowings", operand_concepts)
        self.assertIn("bonds_payable", operand_concepts)
        self.assertTrue(any(concept in operand_concepts for concept in ["property_plant_equipment", "intangible_assets"]))
        self.assertIn("balance_sheet", task["preferred_statement_types"])
        self.assertIn("연결 재무상태표", task["preferred_sections"])
        self.assertIn("차입금 및 사채", task["preferred_sections"])
        self.assertIn("notes", task["preferred_statement_types"])
        self.assertEqual(task["constraints"]["period_focus"], "current")

    def test_target_metric_family_is_retained_when_components_match_v2_ontology(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_v2.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="2023년 연결 재무상태표에서 유·무형자산의 총합 대비 차입금(단기차입금, 장기차입금, 사채 합산)의 비중을 계산해 줘.",
                topic="유무형자산 대비 차입금 비중",
                intent="comparison",
                report_scope={
                    "company": "SK하이닉스",
                    "year": 2023,
                    "report_type": "사업보고서",
                    "consolidation": "연결",
                },
                target_metric_family="asset_debt_burden_ratio",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(plan["status"], "ok")
        self.assertEqual(len(plan["tasks"]), 1)
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "asset_debt_burden_ratio")
        self.assertEqual(plan["planned_metric_families"], ["asset_debt_burden_ratio"])
        operand_labels = [row["label"] for row in task["required_operands"]]
        self.assertEqual(
            operand_labels,
            ["단기차입금", "장기차입금", "사채", "유형자산", "무형자산"],
        )

    def test_concept_only_ontology_builds_ratio_task_from_explicit_concepts(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="2023년 연결기준 부채총계와 자본총계를 찾아 부채총계/자본총계 비율을 계산해 줘.",
                topic="부채총계와 자본총계 비율",
                intent="comparison",
                report_scope={"company": "삼성전자", "year": 2023, "report_type": "사업보고서", "consolidation": "연결"},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_ratio")
        self.assertEqual(task["operation_family"], "ratio")
        self.assertEqual(plan["planned_metric_families"], ["concept_ratio"])
        self.assertEqual(
            [(row["label"], row["role"], row["concept"]) for row in task["required_operands"]],
            [
                ("부채총계", "numerator_1", "total_liabilities"),
                ("자본총계", "denominator_1", "total_equity"),
            ],
        )
        self.assertIn("balance_sheet", task["preferred_statement_types"])
        self.assertIn("요약재무정보", task["preferred_sections"])

    def test_concept_only_ontology_builds_sum_task_from_explicit_concepts(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="2023년 연결기준 단기차입금, 장기차입금, 사채를 합산해 줘.",
                topic="차입금 합산",
                intent="comparison",
                report_scope={"company": "SK하이닉스", "year": 2023, "report_type": "사업보고서", "consolidation": "연결"},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_sum")
        self.assertEqual(task["operation_family"], "sum")
        self.assertEqual(
            [(row["label"], row["role"], row["concept"]) for row in task["required_operands"]],
            [
                ("단기차입금", "addend_1", "short_term_borrowings"),
                ("장기차입금", "addend_2", "long_term_borrowings"),
                ("사채", "addend_3", "bonds_payable"),
            ],
        )
        self.assertIn("notes", task["preferred_statement_types"])
        self.assertIn("차입금 및 사채", task["preferred_sections"])

    def test_concept_only_ontology_builds_segment_sum_task_with_repeated_addends(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="삼성전자 2024 사업보고서에서 SDC와 Harman 부문의 매출 합계는 얼마인가요?",
                topic="SDC와 Harman 부문 매출 합계",
                intent="comparison",
                report_scope={"company": "삼성전자", "year": 2024, "report_type": "사업보고서", "consolidation": "연결"},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_sum")
        self.assertEqual(task["operation_family"], "sum")
        self.assertEqual(
            [(row["label"], row["role"], row["concept"]) for row in task["required_operands"]],
            [
                ("SDC 매출액", "addend_1", "revenue"),
                ("Harman 매출액", "addend_2", "revenue"),
            ],
        )
        self.assertEqual(task["constraints"]["segment_scope"], "segment")

    def test_concept_only_ontology_expands_group_concepts_for_ratio_task(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="2023년 연결 재무상태표에서 유·무형자산의 총합 대비 차입금 비중을 계산해 줘.",
                topic="유무형자산 대비 차입금 비중",
                intent="comparison",
                report_scope={"company": "SK하이닉스", "year": 2023, "report_type": "사업보고서", "consolidation": "연결"},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_ratio")
        self.assertEqual(
            [(row["label"], row["role"], row["concept"]) for row in task["required_operands"]],
            [
                ("유형자산", "denominator_1", "property_plant_equipment"),
                ("무형자산", "denominator_2", "intangible_assets"),
                ("단기차입금", "numerator_1", "short_term_borrowings"),
                ("장기차입금", "numerator_2", "long_term_borrowings"),
                ("사채", "numerator_3", "bonds_payable"),
            ],
        )

    def test_concept_only_ontology_builds_period_difference_task_for_single_concept(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출하고, 전년 대비 증감액을 계산해 줘.",
                topic="법인세비용차감전순이익",
                intent="comparison",
                report_scope={"company": "네이버", "year": 2023, "report_type": "사업보고서"},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_difference")
        self.assertEqual(task["operation_family"], "difference")
        self.assertEqual(
            [row["label"] for row in task["required_operands"]],
            ["2023년 법인세비용차감전순이익", "2022년 법인세비용차감전순이익"],
        )
        self.assertEqual(
            [row["role"] for row in task["required_operands"]],
            ["current_period", "prior_period"],
        )

    def test_concept_only_ontology_builds_ratio_task_for_rnd_over_revenue(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="삼성전자 2024 사업보고서에서 연구개발비용이 전체 매출에서 차지하는 비중은 얼마인가요?",
                topic="삼성전자 2024 사업보고서에서 연구개발비용이 전체 매출에서 차지하는 비중은 얼마인가요?",
                intent="comparison",
                report_scope={"company": "삼성전자", "year": 2024, "report_type": "사업보고서"},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(plan["status"], "concept_fallback")
        self.assertIn("concept_first_preferred", plan["planner_notes"])
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_ratio")
        self.assertEqual(task["operation_family"], "ratio")
        self.assertEqual(
            [(row["label"], row["role"], row["concept"]) for row in task["required_operands"]],
            [
                ("연구개발비용", "numerator_1", "research_and_development_expense"),
                ("매출액", "denominator_1", "revenue"),
            ],
        )

    def test_concept_only_ontology_builds_ratio_task_for_employee_benefits_share_of_operating_expense(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
                topic="영업비용 중 인건비(종업원급여)가 차지하는 비중",
                intent="comparison",
                report_scope={"company": "네이버", "year": 2023, "report_type": "사업보고서"},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(plan["status"], "concept_fallback")
        self.assertIn("concept_first_preferred", plan["planner_notes"])
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_ratio")
        self.assertEqual(task["operation_family"], "ratio")
        self.assertEqual(
            sorted((row["label"], row["role"], row["concept"]) for row in task["required_operands"]),
            sorted(
                [
                    ("종업원급여", "numerator_1", "employee_benefits_expense"),
                    ("영업비용", "denominator_1", "operating_expense_total"),
                ]
            ),
        )

    def test_concept_only_ontology_builds_component_operating_expense_ratio_task(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="2023년 손익계산서에서 매출원가와 판매비와관리비를 합산해 총 영업비용을 구한 뒤, 전체 매출액 대비 영업비용률을 계산해 줘.",
                topic="총 영업비용 비율",
                intent="comparison",
                report_scope={"company": "현대자동차", "year": 2023, "report_type": "사업보고서"},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_ratio")
        self.assertEqual(task["operation_family"], "ratio")
        self.assertEqual(
            [(row["label"], row["role"], row["concept"]) for row in task["required_operands"]],
            [
                ("매출원가", "numerator_1", "cost_of_sales"),
                ("판매비와관리비", "numerator_2", "selling_general_administrative_expense"),
                ("매출액", "denominator_1", "revenue"),
            ],
        )

    def test_dependency_annotation_synthesizes_lookup_tasks_for_component_operating_expense_ratio(self) -> None:
        tasks = _annotate_task_dependencies(
            [
                {
                    "task_id": "task_1",
                    "metric_family": "concept_ratio",
                    "metric_label": "매출액 대비 영업비용률",
                    "query": "2023년 손익계산서에서 매출원가와 판매비와관리비를 합산해 총 영업비용을 구한 뒤, 전체 매출액 대비 영업비용률을 계산해 줘.",
                    "operation_family": "ratio",
                    "required_operands": [
                        {"label": "매출원가", "concept": "cost_of_sales", "role": "numerator_1"},
                        {"label": "판매비와관리비", "concept": "selling_general_administrative_expense", "role": "numerator_2"},
                        {"label": "매출액", "concept": "revenue", "role": "denominator_1"},
                    ],
                }
            ],
            report_scope={"company": "현대자동차", "year": 2023},
        )

        self.assertEqual(
            [task["operation_family"] for task in tasks],
            ["lookup", "lookup", "lookup", "ratio"],
        )
        ratio_task = tasks[-1]
        self.assertEqual(ratio_task["depends_on"], ["task_2", "task_3", "task_4"])
        self.assertEqual(
            [(item["role"], item["preferred_task_id"]) for item in ratio_task["inputs"]],
            [("numerator_1", "task_2"), ("numerator_2", "task_3"), ("denominator_1", "task_4")],
        )
        lookup_tasks = tasks[:-1]
        canonical_lookup_by_label = {
            str(task["metric_label"]).split(" ", 1)[-1]: task for task in lookup_tasks
        }
        self.assertEqual(
            canonical_lookup_by_label["매출원가"]["preferred_sections"],
            ["연결 손익계산서", "손익계산서", "요약재무정보"],
        )
        self.assertEqual(
            canonical_lookup_by_label["판매비와관리비"]["preferred_sections"],
            ["연결 손익계산서", "손익계산서", "요약재무정보"],
        )
        self.assertNotIn("연결재무제표 주석", canonical_lookup_by_label["매출원가"]["preferred_sections"])
        self.assertNotIn("연결재무제표 주석", canonical_lookup_by_label["판매비와관리비"]["preferred_sections"])

    def test_implicit_ratio_query_is_decomposed_by_llm_concept_planner(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            ConceptPlannerOutput.model_validate(
                {
                    "tasks": [
                        {
                            "metric_label": "부채비율",
                            "operation_family": "ratio",
                            "operands": [
                                {"concept": "total_liabilities", "role": "numerator_1"},
                                {"concept": "total_equity", "role": "denominator_1"},
                            ],
                        }
                    ],
                    "rationale": "부채비율은 부채총계/자본총계로 해석한다.",
                }
            )
        )
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            result = agent._plan_semantic_numeric_tasks(
                {
                    "query": "2023년 연결기준 부채비율을 계산해 줘.",
                    "intent": "comparison",
                    "query_type": "comparison",
                    "topic": "부채비율",
                    "report_scope": {"company": "삼성전자", "year": 2023, "report_type": "사업보고서", "consolidation": "연결"},
                    "target_metric_family": "",
                    "target_metric_family_hint": "",
                    "tasks": [],
                    "artifacts": [],
                }
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        plan = dict(result.get("semantic_plan") or {})
        self.assertEqual(plan.get("status"), "concept_fallback")
        self.assertIn("concept_llm_planner", plan.get("planner_notes") or [])
        self.assertEqual(plan.get("planned_metric_families"), ["concept_ratio"])
        self.assertEqual([task["operation_family"] for task in result["calc_subtasks"]], ["lookup", "lookup", "ratio"])
        task = next(
            task
            for task in result["calc_subtasks"]
            if task.get("metric_family") == "concept_ratio"
        )
        self.assertEqual(task["metric_family"], "concept_ratio")
        self.assertEqual(task["operation_family"], "ratio")
        self.assertEqual(len(task.get("depends_on") or []), 2)
        self.assertEqual(
            [(row["label"], row["role"], row["concept"]) for row in task["required_operands"]],
            [
                ("부채총계", "numerator_1", "total_liabilities"),
                ("자본총계", "denominator_1", "total_equity"),
            ],
        )

    def test_llm_lookup_task_with_mismatched_metric_label_is_rejected_and_resynthesized(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            ConceptPlannerOutput.model_validate(
                {
                    "tasks": [
                        {
                            "metric_label": "영업비용 중 인건비(종업원급여) 비중",
                            "operation_family": "ratio",
                            "operands": [
                                {"concept": "employee_benefits_expense", "role": "numerator_1"},
                                {"concept": "operating_expense_total", "role": "denominator_1"},
                            ],
                        },
                        {
                            "metric_label": "2023년 영업비용",
                            "operation_family": "lookup",
                            "operands": [
                                {"concept": "employee_benefits_expense", "role": "denominator_1"},
                            ],
                        },
                        {
                            "metric_label": "2023년 종업원급여",
                            "operation_family": "lookup",
                            "operands": [
                                {"concept": "employee_benefits_expense", "role": "numerator_1"},
                            ],
                        },
                    ],
                    "rationale": "비중 계산을 위한 조회 작업을 분리한다.",
                }
            )
        )
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            result = agent._plan_semantic_numeric_tasks(
                {
                    "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
                    "intent": "comparison",
                    "query_type": "comparison",
                    "topic": "영업비용 중 인건비(종업원급여)가 차지하는 비중",
                    "report_scope": {"company": "NAVER", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240318000844"},
                    "target_metric_family": "",
                    "target_metric_family_hint": "",
                    "tasks": [],
                    "artifacts": [],
                }
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        notes = result["semantic_plan"].get("planner_notes") or []
        self.assertTrue(any(str(note).startswith("lookup_metric_operand_mismatch:") for note in notes))
        lookups = [task for task in result["calc_subtasks"] if task.get("operation_family") == "lookup"]
        operating_expense_lookups = [
            task
            for task in lookups
            if any(
                operand.get("concept") == "operating_expense_total"
                for operand in task.get("required_operands") or []
            )
        ]
        self.assertEqual(len(operating_expense_lookups), 1)
        self.assertIn("영업비용", operating_expense_lookups[0]["metric_label"])
        self.assertFalse(
            any(
                "영업비용" in str(task.get("metric_label") or "")
                and any(
                    operand.get("concept") == "employee_benefits_expense"
                    for operand in task.get("required_operands") or []
                )
                for task in lookups
            )
        )

    def test_llm_ratio_preserves_same_concept_segment_and_company_operands(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            ConceptPlannerOutput.model_validate(
                {
                    "tasks": [
                        {
                            "metric_label": "SK온 영업손실의 전체 연결 영업이익 대비 비중",
                            "operation_family": "ratio",
                            "operands": [
                                {"concept": "operating_income", "role": "numerator_1"},
                                {"concept": "operating_income", "role": "denominator_1"},
                            ],
                        }
                    ],
                    "rationale": "segment operating loss divided by company operating income",
                }
            )
        )
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            result = agent._plan_semantic_numeric_tasks(
                {
                    "query": "2023년 배터리 사업 부문(SK온)의 영업손실이 전체 연결 영업이익의 몇 % 수준인지 계산해 줘.",
                    "intent": "comparison",
                    "query_type": "comparison",
                    "topic": "SK온 영업손실 비중",
                    "report_scope": {"company": "SK이노베이션", "year": 2023, "report_type": "사업보고서"},
                    "target_metric_family": "",
                    "target_metric_family_hint": "",
                    "tasks": [],
                    "artifacts": [],
                }
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        ratio_task = next(
            task for task in result["calc_subtasks"] if task.get("metric_family") == "concept_ratio"
        )
        operands = ratio_task["required_operands"]
        self.assertEqual(
            [(row["concept"], row["role"]) for row in operands],
            [("operating_income", "numerator_1"), ("operating_income", "denominator_1")],
        )
        self.assertEqual(dict(operands[0].get("binding_policy") or {}).get("segment_label"), "SK온")
        self.assertNotIn("segment_label", dict(operands[1].get("binding_policy") or {}))

    def test_concept_only_ontology_builds_fcf_difference_from_component_group(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="2023년 FCF를 계산해 줘.",
                topic="FCF",
                intent="comparison",
                report_scope={"company": "NAVER", "year": 2023, "report_type": "사업보고서", "consolidation": "연결"},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_difference")
        self.assertEqual(task["operation_family"], "difference")
        self.assertEqual(
            [(row["concept"], row["role"]) for row in task["required_operands"]],
            [
                ("operating_cash_flow", "minuend"),
                ("property_plant_equipment_acquisition", "subtrahend"),
            ],
        )

    def test_implicit_multi_metric_query_is_split_by_llm_concept_planner(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            ConceptPlannerOutput.model_validate(
                {
                    "tasks": [
                        {
                            "metric_label": "부채비율",
                            "operation_family": "ratio",
                            "operands": [
                                {"concept": "total_liabilities", "role": "numerator_1"},
                                {"concept": "total_equity", "role": "denominator_1"},
                            ],
                        },
                        {
                            "metric_label": "유동비율",
                            "operation_family": "ratio",
                            "operands": [
                                {"concept": "current_assets", "role": "numerator_1"},
                                {"concept": "current_liabilities", "role": "denominator_1"},
                            ],
                        },
                    ],
                    "rationale": "각 metric을 별도 ratio task로 분해한다.",
                }
            )
        )
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            result = agent._plan_semantic_numeric_tasks(
                {
                    "query": "2023년 연결기준 부채비율과 유동비율을 각각 계산해 줘.",
                    "intent": "comparison",
                    "query_type": "comparison",
                    "topic": "부채비율과 유동비율",
                    "report_scope": {"company": "삼성전자", "year": 2023, "report_type": "사업보고서", "consolidation": "연결"},
                    "target_metric_family": "",
                    "target_metric_family_hint": "",
                    "tasks": [],
                    "artifacts": [],
                }
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(result["planned_metric_families"], ["concept_ratio", "concept_ratio"])
        self.assertEqual(len(result["calc_subtasks"]), 6)
        self.assertEqual(
            [task["operation_family"] for task in result["calc_subtasks"]],
            ["lookup", "lookup", "ratio", "lookup", "lookup", "ratio"],
        )
        ratio_labels = [
            task["metric_label"]
            for task in result["calc_subtasks"]
            if task.get("operation_family") == "ratio"
        ]
        self.assertEqual(ratio_labels, ["부채비율", "유동비율"])

    def test_llm_concept_planner_can_override_deterministic_group_fallback(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            ConceptPlannerOutput.model_validate(
                {
                    "tasks": [
                        {
                            "metric_label": "유·무형자산 대비 차입금 비중",
                            "operation_family": "ratio",
                            "operands": [
                                {"concept": "short_term_borrowings", "role": "numerator_1"},
                                {"concept": "long_term_borrowings", "role": "numerator_2"},
                                {"concept": "bonds_payable", "role": "numerator_3"},
                                {"concept": "property_plant_equipment", "role": "denominator_1"},
                                {"concept": "intangible_assets", "role": "denominator_2"},
                            ],
                        }
                    ],
                    "rationale": "유·무형자산은 유형자산과 무형자산으로 펼치고 차입금은 세 개의 차입 개념으로 분해한다.",
                }
            )
        )
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            result = agent._plan_semantic_numeric_tasks(
                {
                    "query": "2023년 연결 재무상태표에서 유·무형자산의 총합 대비 차입금 비중을 계산해 줘.",
                    "intent": "comparison",
                    "query_type": "comparison",
                    "topic": "유무형자산 대비 차입금 비중",
                    "report_scope": {"company": "SK하이닉스", "year": 2023, "report_type": "사업보고서", "consolidation": "연결"},
                    "target_metric_family": "",
                    "target_metric_family_hint": "",
                    "tasks": [],
                    "artifacts": [],
                }
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        plan = dict(result.get("semantic_plan") or {})
        self.assertIn("concept_llm_planner", plan.get("planner_notes") or [])
        self.assertEqual(
            [task["operation_family"] for task in result["calc_subtasks"][-1:]],
            ["ratio"],
        )
        task = next(
            task
            for task in result["calc_subtasks"]
            if task.get("metric_family") == "concept_ratio"
        )
        self.assertTrue(task["metric_label"])
        self.assertEqual(
            [(row["concept"], row["role"]) for row in task["required_operands"]],
            [
                ("short_term_borrowings", "numerator_1"),
                ("long_term_borrowings", "numerator_2"),
                ("bonds_payable", "numerator_3"),
                ("property_plant_equipment", "denominator_1"),
                ("intangible_assets", "denominator_2"),
            ],
        )
        self.assertIn("concept_llm_planner", plan.get("planner_notes") or [])
        self.assertEqual(
            [task["operation_family"] for task in result["calc_subtasks"][-1:]],
            ["ratio"],
        )
        task = next(
            task
            for task in result["calc_subtasks"]
            if task.get("metric_family") == "concept_ratio"
        )
        self.assertEqual(task["metric_label"], "유·무형자산 대비 차입금 비중")
        self.assertEqual(
            [(row["label"], row["role"], row["concept"]) for row in task["required_operands"]],
            [
                ("단기차입금", "numerator_1", "short_term_borrowings"),
                ("장기차입금", "numerator_2", "long_term_borrowings"),
                ("사채", "numerator_3", "bonds_payable"),
                ("유형자산", "denominator_1", "property_plant_equipment"),
                ("무형자산", "denominator_2", "intangible_assets"),
            ],
        )

    def test_llm_concept_planner_can_keep_raw_lookup_and_difference_materials(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            ConceptPlannerOutput.model_validate(
                {
                    "companies": ["네이버"],
                    "years": [2023, 2022],
                    "topic": "법인세비용차감전순이익 추출 및 전년 대비 증감액 계산",
                    "section_filter": "연결 손익계산서",
                    "tasks": [
                        {
                            "metric_label": "2023년 법인세비용차감전순이익",
                            "operation_family": "lookup",
                            "operands": [
                                {"concept": "income_before_income_taxes", "role": "current_period"},
                            ],
                        },
                        {
                            "metric_label": "법인세비용차감전순이익 증감액",
                            "operation_family": "difference",
                            "operands": [
                                {"concept": "income_before_income_taxes", "role": "current_period"},
                                {"concept": "income_before_income_taxes", "role": "prior_period"},
                            ],
                        },
                    ],
                    "rationale": "원문 질문이 현재 연도 값과 전년 대비 증감액을 모두 요구하므로 raw lookup과 difference를 함께 유지한다.",
                }
            )
        )
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            result = agent._plan_semantic_numeric_tasks(
                {
                    "query": "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출하고, 전년 대비 증감액을 계산해 줘",
                    "intent": "comparison",
                    "query_type": "comparison",
                    "topic": "법인세비용차감전순이익",
                    "report_scope": {"company": "네이버", "year": 2023, "report_type": "사업보고서"},
                    "target_metric_family": "",
                    "target_metric_family_hint": "",
                    "tasks": [],
                    "artifacts": [],
                }
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        plan = dict(result.get("semantic_plan") or {})
        subtasks = result["calc_subtasks"]
        difference_task = subtasks[2]
        self.assertIn("concept_llm_planner", plan.get("planner_notes") or [])
        self.assertEqual(plan.get("planned_metric_families"), ["concept_lookup", "concept_difference"])
        self.assertEqual(
            [(task["metric_family"], task["operation_family"]) for task in subtasks],
            [
                ("concept_lookup", "lookup"),
                ("concept_lookup", "lookup"),
                ("concept_difference", "difference"),
            ],
        )
        self.assertEqual([row["role"] for row in subtasks[0]["required_operands"]], ["current_period"])
        self.assertEqual([row["role"] for row in subtasks[1]["required_operands"]], ["prior_period"])
        self.assertEqual(
            [row["role"] for row in difference_task["required_operands"]],
            ["current_period", "prior_period"],
        )
        self.assertEqual(difference_task.get("depends_on"), ["task_1", "task_3"])
        self.assertEqual(result["years"], [2023, 2022])
        self.assertTrue(result.get("topic"))
        self.assertTrue(result.get("section_filter"))

    def test_llm_concept_planner_preserves_repeated_concepts_for_segment_sum(self) -> None:

        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            ConceptPlannerOutput.model_validate(
                {
                    "companies": ["삼성전자"],
                    "years": [2024],
                    "topic": "SDC 및 Harman 부문 매출 합계",
                    "section_filter": "영업부문",
                    "tasks": [
                        {
                            "metric_label": "SDC 및 Harman 부문 매출 합계",
                            "operation_family": "sum",
                            "operands": [
                                {"concept": "revenue", "role": "addend_1"},
                                {"concept": "revenue", "role": "addend_2"},
                            ],
                        }
                    ],
                    "rationale": "같은 revenue concept라도 SDC와 Harman 부문의 addend를 분리해 합산해야 한다.",
                }
            )
        )
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            result = agent._plan_semantic_numeric_tasks(
                {
                    "query": "삼성전자 2024 사업보고서에서 SDC와 Harman 부문의 매출 합계는 얼마인가요?",
                    "intent": "comparison",
                    "query_type": "comparison",
                    "topic": "SDC와 Harman 부문 매출 합계",
                    "report_scope": {"company": "삼성전자", "year": 2024, "report_type": "사업보고서", "consolidation": "연결"},
                    "target_metric_family": "",
                    "target_metric_family_hint": "",
                    "tasks": [],
                    "artifacts": [],
                }
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        plan = dict(result.get("semantic_plan") or {})
        self.assertIn("concept_llm_planner", plan.get("planner_notes") or [])
        self.assertEqual(plan.get("planned_metric_families"), ["concept_sum"])
        self.assertEqual(len(result["calc_subtasks"]), 3)
        self.assertEqual(
            [task["operation_family"] for task in result["calc_subtasks"]],
            ["lookup", "lookup", "sum"],
        )
        sum_task = next(
            task
            for task in result["calc_subtasks"]
            if task.get("metric_family") == "concept_sum"
        )
        self.assertEqual(
            [(row["label"], row["role"], row["concept"]) for row in sum_task["required_operands"]],
            [
                ("SDC 매출액", "addend_1", "revenue"),
                ("Harman 매출액", "addend_2", "revenue"),
            ],
        )
        self.assertEqual(
            [dict(row.get("binding_policy") or {}).get("segment_label") for row in sum_task["required_operands"]],
            ["SDC", "Harman"],
        )
        self.assertEqual(result["companies"], ["삼성전자"])
        self.assertEqual(result["years"], [2024])
        self.assertEqual(result["section_filter"], "영업부문")

    def test_llm_concept_planner_rehydrates_segment_lookup_operand(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            ConceptPlannerOutput.model_validate(
                {
                    "companies": ["삼성전자"],
                    "years": [2024],
                    "topic": "SDC 부문 매출액",
                    "section_filter": "영업부문",
                    "tasks": [
                        {
                            "metric_label": "SDC 부문 매출액",
                            "operation_family": "lookup",
                            "operands": [
                                {"concept": "revenue", "role": ""}
                            ],
                        }
                    ],
                    "rationale": "SDC 부문 매출액을 조회한다.",
                }
            )
        )
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            result = agent._plan_semantic_numeric_tasks(
                {
                    "query": "삼성전자 2024 사업보고서에서 SDC와 Harman 부문의 매출 합계는 얼마인가요?",
                    "intent": "comparison",
                    "query_type": "comparison",
                    "topic": "SDC 부문 매출액",
                    "report_scope": {"company": "삼성전자", "year": 2024, "report_type": "사업보고서", "consolidation": "연결"},
                    "target_metric_family": "",
                    "target_metric_family_hint": "",
                    "tasks": [],
                    "artifacts": [],
                }
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        operand = result["calc_subtasks"][0]["required_operands"][0]
        self.assertEqual(operand["label"], "2024년 SDC 매출액")
        self.assertEqual(dict(operand.get("binding_policy") or {}).get("segment_label"), "SDC")

    def test_llm_concept_planner_rehydrates_segment_growth_operands(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            ConceptPlannerOutput.model_validate(
                {
                    "companies": ["NAVER"],
                    "years": [2023, 2022],
                    "topic": "커머스 부문 매출 성장률",
                    "section_filter": "영업부문",
                    "tasks": [
                        {
                            "metric_label": "커머스 부문 매출 성장률",
                            "operation_family": "growth_rate",
                            "operands": [
                                {"concept": "revenue", "role": "current_period"},
                                {"concept": "revenue", "role": "prior_period"},
                            ],
                        }
                    ],
                    "rationale": "커머스 부문의 전년 대비 매출 성장률을 계산한다.",
                }
            )
        )
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            result = agent._plan_semantic_numeric_tasks(
                {
                    "query": "커머스 부문의 2023년 매출 성장률(전년 대비)을 계산해 줘.",
                    "intent": "trend",
                    "query_type": "trend",
                    "topic": "커머스 부문 매출 성장률",
                    "report_scope": {
                        "company": "NAVER",
                        "year": 2023,
                        "report_type": "사업보고서",
                        "source_reports": [
                            {"corp_name": "NAVER", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240318000844"},
                            {"corp_name": "NAVER", "year": 2022, "report_type": "사업보고서", "rcept_no": "20230314001049"},
                        ],
                    },
                    "target_metric_family": "",
                    "target_metric_family_hint": "",
                    "tasks": [],
                    "artifacts": [],
                }
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        growth_task = next(task for task in result["calc_subtasks"] if task["task_id"] == "task_1")
        operands = growth_task["required_operands"]
        self.assertEqual(
            [(row["label"], row["role"], dict(row.get("binding_policy") or {}).get("segment_label")) for row in operands],
            [
                ("커머스 매출액", "current_period", "커머스"),
                ("커머스 매출액", "prior_period", "커머스"),
            ],
        )
        lookup_labels = {
            task["task_id"]: task["required_operands"][0]["label"]
            for task in result["calc_subtasks"]
            if task["task_id"] in {"task_2", "task_3"}
        }
        self.assertEqual(
            lookup_labels,
            {
                "task_2": "2023년 커머스 매출액",
                "task_3": "2022년 커머스 매출액",
            },
        )

    def test_replan_mode_appends_patch_tasks_without_overwriting_existing_plan(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            ConceptPlannerOutput.model_validate(
                {
                    "tasks": [
                        {
                            "metric_label": "유동비율",
                            "operation_family": "ratio",
                            "operands": [
                                {"concept": "current_assets", "role": "numerator_1"},
                                {"concept": "current_liabilities", "role": "denominator_1"},
                            ],
                        }
                    ],
                    "rationale": "기존 부채비율 plan은 유지하고, 누락된 유동비율 task만 추가한다.",
                }
            )
        )
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            result = agent._plan_semantic_numeric_tasks(
                {
                    "query": "2023년 연결기준 부채비율과 유동비율을 계산해 줘.",
                    "intent": "comparison",
                    "query_type": "comparison",
                    "topic": "부채비율과 유동비율",
                    "report_scope": {"company": "삼성전자", "year": 2023, "report_type": "사업보고서", "consolidation": "연결"},
                    "planner_mode": "replan",
                    "planner_feedback": "유동비율 계산에 필요한 유동자산과 유동부채 재료가 누락되었습니다.",
                    "plan_loop_count": 0,
                    "target_metric_family": "",
                    "target_metric_family_hint": "",
                    "semantic_plan": {
                        "status": "ok",
                        "tasks": [
                            {
                                "task_id": "task_1",
                                "metric_family": "debt_ratio",
                                "metric_label": "부채비율",
                                "operation_family": "ratio",
                            }
                        ],
                        "planner_notes": ["legacy_planner"],
                    },
                    "calc_subtasks": [
                        {
                            "task_id": "task_1",
                            "metric_family": "debt_ratio",
                            "metric_label": "부채비율",
                            "query": "2023년 연결기준 부채비율을 계산해 줘.",
                            "operation_family": "ratio",
                            "required_operands": [
                                {"label": "부채총계", "concept": "total_liabilities", "role": "numerator_1"},
                                {"label": "자본총계", "concept": "total_equity", "role": "denominator_1"},
                            ],
                            "preferred_statement_types": ["balance_sheet"],
                            "preferred_sections": ["재무상태표"],
                            "retrieval_queries": ["부채총계 자본총계"],
                            "constraints": {"consolidation_scope": "consolidated", "period_focus": "current", "entity_scope": "company", "segment_scope": "none"},
                        }
                    ],
                    "retrieval_queries": ["부채총계 자본총계"],
                    "active_subtask_index": 0,
                    "active_subtask": {"task_id": "task_1", "metric_family": "debt_ratio"},
                    "subtask_results": [
                        {
                            "task_id": "task_1",
                            "metric_family": "debt_ratio",
                            "metric_label": "부채비율",
                            "answer": "2023년 연결기준 부채비율은 25.4%입니다.",
                        }
                    ],
                    "subtask_debug_trace": {},
                    "subtask_loop_complete": True,
                    "tasks": [],
                    "artifacts": [],
                }
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(result["planner_mode"], "initial")
        self.assertEqual(result["planner_feedback"], "")
        self.assertEqual(result["plan_loop_count"], 1)
        self.assertEqual(len(result["calc_subtasks"]), 4)
        self.assertEqual(
            [task["operation_family"] for task in result["calc_subtasks"]],
            ["ratio", "lookup", "lookup", "ratio"],
        )
        self.assertEqual(
            [task["metric_label"] for task in result["semantic_plan"]["tasks"]],
            ["부채비율", "유동비율"],
        )
        self.assertEqual(result["active_subtask_index"], 1)
        self.assertEqual(result["active_subtask"]["operation_family"], "lookup")
        self.assertEqual(result["active_subtask"]["metric_label"], "2023년 유동자산")
        self.assertEqual(len(result["subtask_results"]), 1)
        self.assertEqual(result["subtask_results"][0]["task_id"], "task_1")
        self.assertIn("planner_replan", result["semantic_plan"]["planner_notes"])
        self.assertEqual(result["planned_metric_families"], ["debt_ratio", "concept_ratio"])

    def test_invalid_llm_concept_plan_falls_back_to_heuristic_path(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            ConceptPlannerOutput.model_validate(
                {
                    "tasks": [
                        {
                            "metric_label": "부채비율",
                            "operation_family": "ratio",
                            "operands": [
                                {"concept": "not_a_real_concept", "role": "numerator_1"},
                                {"concept": "total_equity", "role": "denominator_1"},
                            ],
                        }
                    ],
                    "rationale": "invalid concept example",
                }
            )
        )
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            result = agent._plan_semantic_numeric_tasks(
                {
                    "query": "2023년 연결기준 부채비율을 계산해 줘.",
                    "intent": "comparison",
                    "query_type": "comparison",
                    "topic": "부채비율",
                    "report_scope": {"company": "삼성전자", "year": 2023, "report_type": "사업보고서", "consolidation": "연결"},
                    "target_metric_family": "",
                    "target_metric_family_hint": "",
                    "tasks": [],
                    "artifacts": [],
                }
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        plan = dict(result.get("semantic_plan") or {})
        self.assertEqual(plan.get("status"), "heuristic_fallback")
        self.assertEqual(result["calc_subtasks"][0]["metric_family"], "generic_numeric")

    def test_multi_metric_query_tracks_planned_metric_families(self) -> None:
        plan = _build_semantic_numeric_plan(
            query="2023년 연결기준 부채비율(부채총계/자본총계)과 유동비율(유동자산/유동부채)을 각각 계산해 줘.",
            topic="부채비율과 유동비율",
            intent="comparison",
            report_scope={"company": "삼성전자", "year": 2023, "report_type": "사업보고서", "consolidation": "연결"},
            target_metric_family="debt_ratio",
        )

        self.assertEqual(plan["status"], "ok")
        self.assertEqual(plan["planned_metric_families"], ["debt_ratio", "current_ratio"])
        self.assertEqual(
            [task["metric_family"] for task in plan["tasks"]],
            ["debt_ratio", "current_ratio"],
        )

    def test_single_year_query_defaults_period_focus_to_current(self) -> None:
        self.assertEqual(
            _infer_period_focus("2023년 연결 재무상태표에서 단기차입금을 찾아줘."),
            "current",
        )
        self.assertEqual(
            _infer_period_focus("2023년과 2022년 부채비율을 비교해 줘."),
            "unknown",
        )

    def test_fallback_builds_explicit_operand_list_for_gain_loss_difference(self) -> None:
        plan = _build_semantic_numeric_plan(
            query="2023년 주석에서 외화환산이익과 외화환산손실 금액을 각각 찾고, 해당 연도의 환율 변동이 영업외수지에 미친 순효과(이익-손실)를 계산해 줘.",
            topic="외화환산손익",
            intent="comparison",
            report_scope={"company": "SK하이닉스", "year": 2023, "report_type": "사업보고서"},
            target_metric_family="",
        )

        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["operation_family"], "difference")
        self.assertEqual(
            [(row["concept"], row["role"]) for row in task["required_operands"]],
            [
                ("foreign_currency_translation_gain", "minuend"),
                ("foreign_currency_translation_loss", "subtrahend"),
            ],
        )
        operand_labels = [row["label"] for row in task["required_operands"]]
        self.assertEqual(operand_labels, ["외화환산이익", "외화환산손실"])
        self.assertIn("notes", task["preferred_statement_types"])
        self.assertIn("연결재무제표 주석", task["preferred_sections"])
        self.assertIn("cash_flow", task["preferred_statement_types"])
        self.assertIn("현금흐름표 (연결)", task["preferred_sections"])

    def test_component_only_false_positive_is_dropped_before_fallback(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_v2.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="2023년 손익계산서에서 '매출원가'와 '판매비와관리비'를 합산하여 '총 영업비용'을 구한 뒤, 전체 매출액 대비 영업비용률을 계산해 줘.",
                topic="총 영업비용 비율",
                intent="comparison",
                report_scope={"company": "현대자동차", "year": 2023, "report_type": "사업보고서"},
                target_metric_family="rnd_ratio",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertIn(plan["status"], {"heuristic_fallback", "concept_fallback"})
        if plan["status"] == "heuristic_fallback":
            self.assertIn("drop_weak_target:rnd_ratio", plan["planner_notes"])
        task = plan["tasks"][0]
        operand_labels = [row["label"] for row in task["required_operands"]]
        self.assertNotEqual(task["metric_family"], "rnd_ratio")
        self.assertGreaterEqual(len(operand_labels), 1)

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

    def test_merge_operand_rows_keeps_direct_rows_and_fills_missing_operands(self) -> None:
        required_operands = [
            {"label": "유형자산", "aliases": ["유형자산"]},
            {"label": "무형자산", "aliases": ["무형자산"]},
            {"label": "사채", "aliases": ["사채"]},
        ]
        direct_rows = [
            {
                "label": "제76기 ㆍ유형자산",
                "raw_value": "52,704,853",
                "source_anchor": "[SK하이닉스 | 2023 | III. 요약연결재무정보]",
            },
            {
                "label": "제76기 ㆍ무형자산",
                "raw_value": "3,834,567",
                "source_anchor": "[SK하이닉스 | 2023 | III. 요약연결재무정보]",
            },
        ]
        fallback_rows = [
            {
                "label": "2023년 사채",
                "raw_value": "9,490,410",
                "source_anchor": "[SK하이닉스 | 2023 | III. 연결재무제표 주석]",
            },
            {
                "label": "2023년 유형자산",
                "raw_value": "999",
                "source_anchor": "[noise]",
            },
        ]

        missing = _missing_required_operands(required_operands, direct_rows)
        merged = _merge_operand_rows(
            direct_rows,
            fallback_rows,
            required_operands=required_operands,
        )

        self.assertEqual([item["label"] for item in missing], ["사채"])
        self.assertEqual(len(merged), 3)
        self.assertEqual(merged[0]["raw_value"], "52,704,853")
        self.assertEqual(merged[1]["raw_value"], "3,834,567")
        self.assertEqual(merged[2]["raw_value"], "9,490,410")

    def test_ratio_query_is_not_misclassified_as_percent_point_difference(self) -> None:
        self.assertFalse(
            _is_percent_point_difference_query(
                "2023년 연결 재무상태표에서 유·무형자산의 총합 대비 차입금(단기차입금, 장기차입금, 사채 합산)의 비중을 계산해 줘."
            )
        )
        self.assertTrue(
            _is_percent_point_difference_query(
                "2023년과 2022년 부채비율의 차이를 %p 기준으로 계산해 줘."
            )
        )


    def test_extract_segment_labels_from_query_captures_mixed_segment_and_plain_metric_mentions(self) -> None:
        labels = _extract_segment_labels_from_query(
            "Samsung 2024 report에서 DS 부문 매출은 SDC 매출보다 얼마나 더 큰가요?",
            {"company": "Samsung", "year": 2024, "report_type": "report"},
        )
        self.assertEqual(labels, ["DS", "SDC"])

    def test_extract_segment_labels_from_query_strips_year_tokens_for_growth_queries(self) -> None:
        labels = _extract_segment_labels_from_query(
            "커머스 부문의 2023년 매출 성장률(전년 대비)을 계산해 줘.",
            {"company": "네이버", "year": 2023, "report_type": "report"},
        )
        self.assertEqual(labels, ["커머스"])

    def test_extract_segment_labels_from_query_ignores_year_prefixed_metric_mentions(self) -> None:
        labels = _extract_segment_labels_from_query(
            "2023년 핀테크 부문의 전년 대비 결제액 또는 영업수익 증가율을 계산해 줘.",
            {"company": "네이버", "year": 2023, "report_type": "report"},
        )
        self.assertEqual(labels, ["핀테크"])

    def test_llm_concept_planner_rehydrates_segment_difference_operands(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            ConceptPlannerOutput.model_validate(
                {
                    "companies": ["Samsung"],
                    "years": [2024],
                    "topic": "DX와 DS 부문 매출 차이",
                    "section_filter": "영업부문",
                    "tasks": [
                        {
                            "metric_label": "DX와 DS 부문 매출 차이",
                            "operation_family": "difference",
                            "operands": [
                                {"concept": "revenue", "role": "minuend"},
                                {"concept": "revenue", "role": "subtrahend"},
                            ],
                        }
                    ],
                    "rationale": "DX와 DS 부문 매출 차이를 revenue difference로 해석한다.",
                }
            )
        )
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            result = agent._plan_semantic_numeric_tasks(
                {
                    "query": "Samsung 2024 report에서 DX와 DS 부문의 매출 차이가 얼마인지 알려줘",
                    "intent": "comparison",
                    "query_type": "comparison",
                    "topic": "DX와 DS 부문 매출 차이",
                    "report_scope": {"company": "Samsung", "year": 2024, "report_type": "report", "consolidation": "연결"},
                    "target_metric_family": "",
                    "target_metric_family_hint": "",
                    "tasks": [],
                    "artifacts": [],
                }
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        difference_task = next(
            task for task in result["calc_subtasks"] if task.get("operation_family") == "difference"
        )
        operands = difference_task["required_operands"]
        self.assertEqual(
            [(row["role"], dict(row.get("binding_policy") or {}).get("segment_label")) for row in operands],
            [("minuend", "DX"), ("subtrahend", "DS")],
        )
        self.assertEqual(difference_task.get("depends_on"), ["task_2", "task_3"])

    def test_entity_scoped_difference_query_builds_concept_task_without_metric_family_hint(self) -> None:

        plan = _build_semantic_numeric_plan(
            query="Samsung 2024 report에서 DX와 DS 부문의 매출 차이는 얼마인가요?",
            topic="DX와 DS 부문 매출 차이",
            intent="comparison",
            report_scope={"company": "Samsung", "year": 2024, "report_type": "report"},
            target_metric_family="",
        )
        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_difference")
        self.assertEqual(task["operation_family"], "difference")
        self.assertEqual(
            [(row["label"], row["role"], dict(row.get("binding_policy") or {}).get("segment_label")) for row in task["required_operands"]],
            [("DX 매출액", "minuend", "DX"), ("DS 매출액", "subtrahend", "DS")],
        )

    def test_entity_scoped_difference_query_with_mixed_mentions_builds_concept_task(self) -> None:
        plan = _build_semantic_numeric_plan(
            query="Samsung 2024 report에서 DS 부문 매출은 SDC 매출보다 얼마나 더 큰가요?",
            topic="DS 부문 매출과 SDC 매출 차이",
            intent="comparison",
            report_scope={"company": "Samsung", "year": 2024, "report_type": "report"},
            target_metric_family="",
        )
        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_difference")
        self.assertEqual(task["operation_family"], "difference")
        self.assertEqual(
            [(row["label"], row["role"], dict(row.get("binding_policy") or {}).get("segment_label")) for row in task["required_operands"]],
            [("DS 매출액", "minuend", "DS"), ("SDC 매출액", "subtrahend", "SDC")],
        )

    def test_entity_scoped_growth_rate_query_builds_segment_bound_period_operands(self) -> None:
        plan = _build_semantic_numeric_plan(
            query="커머스 부문의 2023년 매출 성장률(전년 대비)을 계산해 줘.",
            topic="커머스 부문 매출 성장률",
            intent="comparison",
            report_scope={"company": "네이버", "year": 2023, "report_type": "report"},
            target_metric_family="",
        )
        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_growth_rate")
        self.assertEqual(task["operation_family"], "growth_rate")
        self.assertEqual(
            [(row["label"], row["role"], row["concept"], dict(row.get("binding_policy") or {}).get("segment_label")) for row in task["required_operands"]],
            [
                ("2023년 커머스 매출액", "current_period", "revenue", "커머스"),
                ("2022년 커머스 매출액", "prior_period", "revenue", "커머스"),
            ],
        )
        retrieval_queries = task.get("retrieval_queries") or []
        self.assertTrue(any("커머스" in query for query in retrieval_queries))

    def test_segment_sum_llm_override_is_rejected_when_shape_degrades(self) -> None:
        base_plan = {
            "status": "concept_fallback",
            "tasks": [
                {
                    "metric_family": "concept_sum",
                    "operation_family": "sum",
                    "constraints": {"segment_scope": "segment"},
                    "required_operands": [
                        {"label": "SDC 매출액", "role": "addend_1", "concept": "revenue"},
                        {"label": "Harman 매출액", "role": "addend_2", "concept": "revenue"},
                    ],
                }
            ],
        }
        degraded_llm_plan = {
            "status": "concept_fallback",
            "tasks": [
                {
                    "metric_family": "concept_lookup",
                    "operation_family": "lookup",
                    "constraints": {"segment_scope": "segment"},
                    "required_operands": [
                        {"label": "연구개발비용", "role": "", "concept": "research_and_development_expense"},
                    ],
                }
            ],
        }
        preserved_llm_plan = {
            "status": "concept_fallback",
            "tasks": [
                {
                    "metric_family": "concept_sum",
                    "operation_family": "sum",
                    "constraints": {"segment_scope": "segment"},
                    "required_operands": [
                        {"label": "매출액", "role": "addend_1", "concept": "revenue"},
                        {"label": "매출액", "role": "addend_2", "concept": "revenue"},
                    ],
                }
            ],
        }

        self.assertFalse(_llm_plan_preserves_segment_sum_shape(base_plan, degraded_llm_plan))
        self.assertTrue(_llm_plan_preserves_segment_sum_shape(base_plan, preserved_llm_plan))

    def test_concept_only_ontology_builds_capex_growth_task_for_multi_report_query(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="2023년 메모리 반도체 업황 악화에도 불구하고 집행된 시설투자(CAPEX) 총액을 찾고, 전년(2022년) 대비 증감률을 계산해 줘.",
                topic="시설투자(CAPEX) 총액 및 증감률",
                intent="comparison",
                report_scope={"company": "삼성전자", "year": 2023, "report_type": "사업보고서", "consolidation": "연결"},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_growth_rate")
        self.assertEqual(task["operation_family"], "growth_rate")
        self.assertEqual(
            [(row["concept"], row["role"]) for row in task["required_operands"]],
            [
                ("capital_expenditure_total", "current_period"),
                ("capital_expenditure_total", "prior_period"),
            ],
        )
        self.assertIn("원재료 및 생산설비", task["preferred_sections"])
        self.assertNotIn("cash_flow", task["preferred_statement_types"])

    def _build_v3_concept_plan(self, query: str) -> dict:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            return _build_semantic_numeric_plan(
                query=query,
                topic="",
                intent="comparison",
                report_scope={"company": "테스트", "year": 2023, "report_type": "사업보고서", "consolidation": "연결"},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

    def test_concept_only_ontology_builds_shadow_gap_concept_tasks(self) -> None:
        cases = [
            (
                "2023년 신용손실충당금전입액과 전년 대비 증감률을 계산해줘",
                "growth_rate",
                [
                    ("credit_loss_provision_expense", "current_period"),
                    ("credit_loss_provision_expense", "prior_period"),
                ],
            ),
            (
                "2023년 외화환산이익과 외화환산손실의 순효과를 계산해줘",
                "difference",
                [
                    ("foreign_currency_translation_gain", "minuend"),
                    ("foreign_currency_translation_loss", "subtrahend"),
                ],
            ),
            (
                "2023년 자본화된 개발비가 연구개발비에서 차지하는 비율을 계산해줘",
                "ratio",
                [
                    ("capitalized_development_cost", "numerator_1"),
                    ("research_and_development_expense", "denominator_1"),
                ],
            ),
            (
                "2023년 이자보상배율(영업이익 / 이자비용)을 계산해줘",
                "ratio",
                [
                    ("operating_income", "numerator_1"),
                    ("interest_expense", "denominator_1"),
                ],
            ),
            (
                "2023년 경비차감전영업이익 대비 판매비와관리비 비율을 계산해줘",
                "ratio",
                [
                    ("pre_expense_operating_profit", "denominator_1"),
                    ("selling_general_administrative_expense", "numerator_1"),
                ],
            ),
        ]

        for query, operation_family, expected_operands in cases:
            with self.subTest(query=query):
                plan = self._build_v3_concept_plan(query)
                self.assertEqual(plan["status"], "concept_fallback")
                task = plan["tasks"][0]
                self.assertEqual(task["operation_family"], operation_family)
                self.assertEqual(
                    [(row["concept"], row["role"]) for row in task["required_operands"]],
                    expected_operands,
                )

    def test_concept_only_ontology_matches_inventory_loss_lookup_variants(self) -> None:
        plan = self._build_v3_concept_plan(
            "2023년 재고자산평가손실, 환입, 폐기손실 금액을 찾아줘"
        )

        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["operation_family"], "single_value")
        self.assertEqual(
            [row["concept"] for row in task["required_operands"]],
            [
                "inventory_valuation_loss",
                "inventory_valuation_loss_reversal",
                "inventory_disposal_loss",
            ],
        )

    def test_parenthetical_inventory_adjustment_impact_builds_ratio_task(self) -> None:
        plan = self._build_v3_concept_plan(
            "2023년 재무제표 주석에서 '재고자산평가손실(또는 환입)' 규모를 찾고, 이것이 매출원가에 미친 영향을 분석해 줘."
        )

        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_ratio")
        self.assertEqual(task["operation_family"], "ratio")
        self.assertEqual(
            [(row["concept"], row["role"]) for row in task["required_operands"]],
            [
                ("inventory_valuation_adjustment", "numerator_1"),
                ("cost_of_sales", "denominator_1"),
            ],
        )
        self.assertIn("analysis_hints", task)

    def test_parenthetical_inventory_adjustment_shadows_split_loss_concepts(self) -> None:
        import src.config.ontology as ontology_module
        from src.config.ontology import FinancialOntologyManager

        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            ontology = ontology_module._ONTOLOGY_SINGLETON
            specs = ontology.concept_specs(
                "2023년 재고자산평가손실(또는 환입)이 매출원가에 미친 영향을 분석해 줘.",
                "",
                "comparison",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        concepts = [spec["concept"] for spec in specs]
        self.assertIn("inventory_valuation_adjustment", concepts)
        self.assertIn("cost_of_sales", concepts)
        self.assertNotIn("inventory_valuation_loss", concepts)
        self.assertNotIn("inventory_valuation_loss_reversal", concepts)

    def test_llm_analysis_override_must_preserve_ratio_shape(self) -> None:
        base_plan = {
            "tasks": [
                {
                    "operation_family": "ratio",
                    "analysis_hints": {"preferred_operation": "ratio"},
                    "required_operands": [
                        {"concept": "inventory_valuation_adjustment", "role": "numerator_1"},
                        {"concept": "cost_of_sales", "role": "denominator_1"},
                    ],
                }
            ]
        }
        lookup_only_plan = {
            "tasks": [
                {
                    "operation_family": "lookup",
                    "required_operands": [
                        {"concept": "inventory_valuation_adjustment", "role": ""},
                    ],
                },
                {
                    "operation_family": "lookup",
                    "required_operands": [
                        {"concept": "cost_of_sales", "role": ""},
                    ],
                },
            ]
        }
        compatible_plan = {
            "tasks": [
                {
                    "operation_family": "ratio",
                    "required_operands": [
                        {"concept": "inventory_valuation_adjustment", "role": "numerator_1"},
                        {"concept": "cost_of_sales", "role": "denominator_1"},
                    ],
                }
            ]
        }

        self.assertFalse(_llm_plan_preserves_analysis_shape(base_plan, lookup_only_plan))
        self.assertTrue(_llm_plan_preserves_analysis_shape(base_plan, compatible_plan))


if __name__ == "__main__":
    unittest.main()
