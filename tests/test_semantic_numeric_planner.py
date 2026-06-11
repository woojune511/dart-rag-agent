import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.financial_graph import _build_semantic_numeric_plan
from src.agent.financial_graph_planning import FinancialAgentPlanningMixin, _non_numeric_operation_intent_override


class SemanticNumericPlannerTests(unittest.TestCase):
    def test_summary_only_query_does_not_promote_to_numeric_fact(self) -> None:
        intent, note = _non_numeric_operation_intent_override(
            query="2023년 전동화 플랫폼의 주요 성과를 요약해 줘.",
            topic="전동화 플랫폼 성과 요약",
            intent="business_overview",
        )

        self.assertEqual(intent, "business_overview")
        self.assertEqual(note, "")

    def test_lookup_and_summary_query_can_promote_to_numeric_fact(self) -> None:
        intent, note = _non_numeric_operation_intent_override(
            query="2023년 연결기준 매출액 규모를 알려주고 사업 성과를 요약해 줘.",
            topic="매출액 규모와 사업 성과",
            intent="business_overview",
        )

        self.assertEqual(intent, "numeric_fact")
        self.assertEqual(note, "non_numeric_operation_promoted_by_ontology")

    def test_single_report_scope_collapses_company_aliases_to_metadata_company(self) -> None:
        mixin = FinancialAgentPlanningMixin()

        companies, years = mixin._align_scope_hints(
            companies=["Hyundai Motor Company"],
            years=[],
            report_scope={
                "company": "현대자동차",
                "year": 2023,
                "rcept_no": "20240313001451",
            },
        )

        self.assertEqual(companies, ["현대자동차"])
        self.assertEqual(years, [2023])

    def test_single_metric_ratio_plan(self) -> None:
        plan = _build_semantic_numeric_plan(
            query="2023년 연결기준 부채비율을 계산해 줘.",
            topic="부채비율 계산",
            intent="comparison",
            report_scope={"company": "삼성전자", "year": "2023", "consolidation": "연결"},
            target_metric_family="debt_ratio",
        )
        self.assertEqual(plan["status"], "ok")
        self.assertEqual(len(plan["tasks"]), 1)
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "debt_ratio")
        self.assertEqual(task["constraints"]["consolidation_scope"], "consolidated")
        labels = [row["label"] for row in task["required_operands"]]
        self.assertEqual(labels, ["부채총계", "자본총계"])
        self.assertTrue(any("부채총계" in item for item in task["retrieval_queries"]))

    def test_multi_metric_ratio_plan(self) -> None:
        plan = _build_semantic_numeric_plan(
            query="2023년 연결기준 부채비율과 유동비율을 각각 계산해 줘.",
            topic="부채비율과 유동비율 계산",
            intent="comparison",
            report_scope={"company": "삼성전자", "year": "2023", "consolidation": "연결"},
            target_metric_family="",
        )
        self.assertEqual(plan["status"], "ok")
        metric_families = [task["metric_family"] for task in plan["tasks"]]
        self.assertIn("debt_ratio", metric_families)
        self.assertIn("current_ratio", metric_families)

    def test_percent_point_margin_impact_plans_ratio_derived_drag_metric(self) -> None:
        plan = _build_semantic_numeric_plan(
            query="2023년 무형자산상각비 총액을 찾고, 이것이 영업이익률을 얼마나 낮추었는지(%p) 추정해 줘.",
            topic="영업이익률 영향 계산",
            intent="numeric_fact",
            report_scope={"company": "셀트리온", "year": "2023", "consolidation": "연결"},
            target_metric_family="",
        )

        self.assertEqual(plan["status"], "ok")
        metric_families = [task["metric_family"] for task in plan["tasks"]]
        self.assertIn("operating_margin_drag", metric_families)
        self.assertIn("operating_margin", metric_families)
        drag_task = next(task for task in plan["tasks"] if task["metric_family"] == "operating_margin_drag")
        self.assertEqual(drag_task["operation_family"], "ratio")
        self.assertEqual(
            [(row["role"], row["concept"]) for row in drag_task["required_operands"]],
            [("numerator", "amortization_expense"), ("denominator", "revenue")],
        )
        for row in drag_task["required_operands"]:
            self.assertEqual(row["binding_policy"]["prefer_value_roles"], ["aggregate"])
            self.assertEqual(row["binding_policy"]["prefer_aggregation_stages"], ["final", "subtotal", "direct"])

    def test_implicit_fcf_plan(self) -> None:
        plan = _build_semantic_numeric_plan(
            query="2023년 FCF를 계산해 줘.",
            topic="FCF 계산",
            intent="comparison",
            report_scope={"company": "네이버", "year": "2023", "consolidation": "연결"},
            target_metric_family="free_cash_flow",
        )
        self.assertEqual(plan["status"], "ok")
        task = plan["tasks"][0]
        labels = [row["label"] for row in task["required_operands"]]
        self.assertEqual(labels, ["영업활동현금흐름", "유형자산의 취득"])
        self.assertIn("cash_flow", task["preferred_statement_types"])

    def test_missing_ontology_match_falls_back(self) -> None:
        plan = _build_semantic_numeric_plan(
            query="2023년 이 회사의 핵심 체력을 계산해 줘.",
            topic="핵심 체력",
            intent="comparison",
            report_scope={"company": "네이버", "year": "2023", "consolidation": "연결"},
            target_metric_family="",
        )
        self.assertEqual(plan["status"], "heuristic_fallback")
        self.assertFalse(plan["fallback_to_general_search"])
        self.assertEqual(len(plan["tasks"]), 1)
        self.assertEqual(plan["tasks"][0]["metric_family"], "generic_numeric")


if __name__ == "__main__":
    unittest.main()
