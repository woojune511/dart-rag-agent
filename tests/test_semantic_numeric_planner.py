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


class SemanticNumericPlannerTests(unittest.TestCase):
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
