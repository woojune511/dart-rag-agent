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
from src.config.ontology import FinancialOntologyManager
import src.config.ontology as ontology_module


class ConceptRuntimeContractTests(unittest.TestCase):
    def test_default_runtime_ontology_dedupes_ratio_group_and_member_concepts(self) -> None:
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager()
            plan = _build_semantic_numeric_plan(
                query="2023년 연결 재무상태표에서 유·무형자산의 총합 대비 차입금(단기차입금, 장기차입금, 사채 합산)의 비중을 계산해 줘.",
                topic="유·무형자산 대비 차입금 비중",
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

    def test_concept_runtime_builds_difference_task_for_nim(self) -> None:
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query="2023년 KB금융의 순이자마진(NIM) 수치를 사업보고서에서 찾고, 전년 대비 증감폭(%p)을 계산해 줘.",
                topic="순이자마진 증감폭",
                intent="comparison",
                report_scope={"company": "KB금융", "year": 2023, "report_type": "사업보고서"},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_difference")
        self.assertEqual(task["operation_family"], "difference")
        self.assertEqual(
            [(row["label"], row["role"], row["concept"], row.get("unit_family")) for row in task["required_operands"]],
            [
                ("2023년 순이자마진", "current_period", "net_interest_margin", "PERCENT"),
                ("2022년 순이자마진", "prior_period", "net_interest_margin", "PERCENT"),
            ],
        )
        for operand in task["required_operands"]:
            self.assertEqual(
                operand.get("surface_contract"),
                {
                    "positive": ["명목순이자마진", "순이자마진"],
                    "negative": ["NIM(은행+카드)", "은행+카드"],
                },
            )


if __name__ == "__main__":
    unittest.main()
