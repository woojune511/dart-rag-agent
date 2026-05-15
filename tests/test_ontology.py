import json
import tempfile
import unittest
from pathlib import Path

from src.config.ontology import FinancialOntologyManager


class FinancialOntologyManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        path = Path("src/config/financial_ontology.json")
        self.ontology = FinancialOntologyManager(path)
        self.ontology_v2 = FinancialOntologyManager(Path("src/config/financial_ontology_v2.draft.json"))
        self.ontology_v3 = FinancialOntologyManager(Path("src/config/financial_ontology_concepts_v3.draft.json"))

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

    def test_v2_operand_spec_resolves_concept_aliases_and_binding_policy(self) -> None:
        specs = self.ontology_v2.build_operand_spec("asset_debt_burden_ratio")
        bonds = next(spec for spec in specs if spec["concept"] == "bonds_payable")

        self.assertEqual(bonds["label"], "사채")
        self.assertIn("회사채", bonds["aliases"])
        self.assertIn("notes", bonds["preferred_statement_types"])
        self.assertIn("aggregate", bonds["binding_policy"].get("prefer_value_roles", []))
        self.assertIn("final", bonds["binding_policy"].get("prefer_aggregation_stages", []))

    def test_v2_component_specs_expose_concept_binding_metadata(self) -> None:
        specs = self.ontology_v2.component_specs("유무형자산 대비 차입금 비중을 계산해 줘", intent="comparison")
        bonds = next(spec for spec in specs if spec["concept"] == "bonds_payable")

        self.assertEqual(bonds["name"], "사채")
        self.assertIn("차입금 및 사채", bonds["preferred_sections"])
        self.assertIn("detail", bonds["binding_policy"].get("avoid_value_roles", []))

    def test_binding_policy_override_takes_precedence_over_concept_default(self) -> None:
        payload = {
            "binding_policy_defaults": {
                "prefer_value_roles": ["detail"],
                "prefer_aggregation_stages": ["none"],
            },
            "metric_families": {
                "demo_metric": {
                    "display_name": "데모 지표",
                    "aliases": ["데모 지표"],
                    "components": {
                        "numerator": {
                            "concept_ref": "demo_concept",
                            "binding_policy_override": {
                                "prefer_value_roles": ["aggregate"],
                                "prefer_aggregation_stages": ["final"],
                            },
                        }
                    },
                }
            },
            "concepts": {
                "demo_concept": {
                    "display_name": "데모 개념",
                    "aliases": ["데모 개념"],
                    "binding_policy": {
                        "prefer_value_roles": ["detail"],
                        "prefer_aggregation_stages": ["direct"],
                    },
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ontology.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            ontology = FinancialOntologyManager(path)

            spec = ontology.build_operand_spec("demo_metric")[0]
            self.assertEqual(spec["concept"], "demo_concept")
            self.assertEqual(spec["binding_policy"]["prefer_value_roles"], ["aggregate"])
            self.assertEqual(spec["binding_policy"]["prefer_aggregation_stages"], ["final"])

    def test_v3_concept_only_ontology_matches_general_concepts(self) -> None:
        specs = self.ontology_v3.concept_specs(
            "2023년 연결 재무상태표에서 단기차입금, 장기차입금, 사채를 찾아줘.",
            intent="comparison",
        )
        concept_keys = [spec["concept"] for spec in specs]
        self.assertIn("short_term_borrowings", concept_keys)
        self.assertIn("long_term_borrowings", concept_keys)
        self.assertIn("bonds_payable", concept_keys)

    def test_v3_preferred_sections_fall_back_to_concept_priors(self) -> None:
        sections = self.ontology_v3.preferred_sections(
            "2023년 연결 재무상태표에서 사채와 장기차입금을 찾아줘.",
            intent="comparison",
        )
        self.assertIn("차입금 및 사채", sections)
        self.assertIn("연결재무제표 주석", sections)

    def test_v3_query_hints_fall_back_to_concept_aliases(self) -> None:
        hints = self.ontology_v3.query_hints(
            "2023년 연결 재무상태표에서 유동자산과 유동부채를 찾아줘.",
            intent="comparison",
        )
        self.assertIn("유동자산", hints)
        self.assertIn("유동부채", hints)

    def test_v3_group_concepts_are_matched_for_common_shorthand(self) -> None:
        specs = self.ontology_v3.concept_specs(
            "2023년 연결 재무상태표에서 유·무형자산의 총합 대비 차입금 비중을 계산해 줘.",
            intent="comparison",
        )
        concept_keys = [spec["concept"] for spec in specs]
        self.assertIn("tangible_and_intangible_assets", concept_keys)
        self.assertIn("borrowings", concept_keys)
        group_spec = next(spec for spec in specs if spec["concept"] == "tangible_and_intangible_assets")
        self.assertTrue(group_spec.get("is_group"))
        self.assertEqual(
            group_spec.get("member_concepts"),
            ["property_plant_equipment", "intangible_assets"],
        )


if __name__ == "__main__":
    unittest.main()
