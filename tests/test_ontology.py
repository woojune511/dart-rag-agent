import unittest
from pathlib import Path

from src.config.ontology import FinancialOntologyManager


class FinancialOntologyManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        path = Path("src/config/financial_ontology.json")
        self.ontology = FinancialOntologyManager(path)

    def test_metric_matching_supports_implicit_ratio_query(self) -> None:
        metric = self.ontology.best_metric_family("2023년 연결기준 부채비율을 계산해 줘.", intent="comparison")
        self.assertIsNotNone(metric)
        self.assertEqual(metric.get("key"), "debt_ratio")

    def test_metric_aliases_are_exposed(self) -> None:
        aliases = self.ontology.aliases_for_metric("free_cash_flow")
        self.assertIn("FCF", aliases)
        self.assertIn("잉여현금흐름", aliases)

    def test_statement_type_hints_are_exposed(self) -> None:
        hints = self.ontology.statement_type_hints_for_metric("debt_ratio")
        self.assertIn("balance_sheet", hints)
        self.assertIn("summary_financials", hints)

    def test_retrieval_keywords_include_component_aliases(self) -> None:
        keywords = self.ontology.retrieval_keywords_for_metric("roe")
        self.assertIn("당기순이익", keywords)
        self.assertIn("지배기업주주지분순이익", keywords)
        self.assertIn("자본총계", keywords)

    def test_default_constraints_are_normalised(self) -> None:
        constraints = self.ontology.default_constraints_for_metric("current_ratio")
        self.assertEqual(constraints["period_focus"], "current")
        self.assertEqual(constraints["entity_scope"], "company")
        self.assertEqual(constraints["segment_scope"], "none")
        self.assertEqual(constraints["consolidation_scope"], "unknown")

    def test_build_operand_spec_contains_aliases_and_required_flag(self) -> None:
        specs = self.ontology.build_operand_spec("debt_ratio")
        self.assertEqual(len(specs), 2)
        numerator = next(spec for spec in specs if spec["role"] == "numerator")
        denominator = next(spec for spec in specs if spec["role"] == "denominator")
        self.assertEqual(numerator["label"], "부채총계")
        self.assertIn("총부채", numerator["aliases"])
        self.assertTrue(numerator["required"])
        self.assertEqual(denominator["label"], "자본총계")


if __name__ == "__main__":
    unittest.main()
