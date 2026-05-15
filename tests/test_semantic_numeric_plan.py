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
        task = result["calc_subtasks"][0]
        self.assertEqual(task["metric_family"], "concept_ratio")
        self.assertEqual(task["operation_family"], "ratio")
        self.assertEqual(
            [(row["label"], row["role"], row["concept"]) for row in task["required_operands"]],
            [
                ("부채총계", "numerator_1", "total_liabilities"),
                ("자본총계", "denominator_1", "total_equity"),
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
        self.assertEqual(len(result["calc_subtasks"]), 2)
        self.assertEqual(
            [task["metric_label"] for task in result["calc_subtasks"]],
            ["부채비율", "유동비율"],
        )

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
        task = result["calc_subtasks"][0]
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
                    "query": "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출하고, 전년 대비 증감액을 계산해 줘.",
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
        self.assertIn("concept_llm_planner", plan.get("planner_notes") or [])
        self.assertEqual(plan.get("planned_metric_families"), ["concept_lookup", "concept_difference"])
        self.assertEqual(
            [(task["metric_label"], task["metric_family"], task["operation_family"]) for task in result["calc_subtasks"]],
            [
                ("2023년 법인세비용차감전순이익", "concept_lookup", "lookup"),
                ("법인세비용차감전순이익 증감액", "concept_difference", "difference"),
            ],
        )
        self.assertEqual(
            [(row["label"], row["role"]) for row in result["calc_subtasks"][0]["required_operands"]],
            [("법인세비용차감전순이익", "current_period")],
        )
        self.assertEqual(
            [(row["label"], row["role"]) for row in result["calc_subtasks"][1]["required_operands"]],
            [
                ("법인세비용차감전순이익", "current_period"),
                ("법인세비용차감전순이익", "prior_period"),
            ],
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
        self.assertEqual(len(result["calc_subtasks"]), 2)
        self.assertEqual(
            [task["task_id"] for task in result["calc_subtasks"]],
            ["task_1", "task_2"],
        )
        self.assertEqual(
            [task["metric_label"] for task in result["calc_subtasks"]],
            ["부채비율", "유동비율"],
        )
        self.assertEqual(result["active_subtask_index"], 1)
        self.assertEqual(result["active_subtask"]["task_id"], "task_2")
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


if __name__ == "__main__":
    unittest.main()
