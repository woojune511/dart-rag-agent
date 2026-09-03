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

    def test_metric_family_is_retrieval_policy_not_a_calculation_recipe(self) -> None:
        metric = self.ontology.best_metric_family("EBITDA", intent="comparison")
        self.assertIsNotNone(metric)
        self.assertEqual(metric.get("key"), "ebitda")
        for removed_key in (
            "components",
            "denominator_aggregation",
            "direct_lookup_preferred",
            "formula_family",
            "formula_template",
            "result_unit",
        ):
            self.assertNotIn(removed_key, metric)
        self.assertIn("mda", metric.get("statement_type_hints") or [])
        self.assertTrue(metric.get("preferred_sections"))
        self.assertTrue(metric.get("query_hints"))

    def test_query_hints_are_declarative_and_do_not_expose_operand_roles(self) -> None:
        hints = self.ontology.query_hints("ROE", intent="comparison")
        self.assertTrue(hints)
        payload_text = json.dumps(self.ontology.payload, ensure_ascii=False)
        self.assertNotIn('"components"', payload_text)
        self.assertNotIn('"denominator_aggregation"', payload_text)

    def test_v2_concept_binding_metadata_remains_available(self) -> None:
        policy = self.ontology_v2.binding_policy_for_concept("bonds_payable")
        self.assertIn("aggregate", policy.get("prefer_value_roles", []))
        concept = self.ontology_v2.concept("bonds_payable")
        self.assertIsNotNone(concept)
        self.assertIn("notes", concept.get("preferred_statement_types") or [])

    def test_concept_binding_policy_overrides_default_policy(self) -> None:
        payload = {
            "binding_policy_defaults": {
                "prefer_value_roles": ["detail"],
                "prefer_aggregation_stages": ["none"],
            },
            "concepts": {
                "demo_concept": {
                    "display_name": "demo concept",
                    "aliases": ["demo alias"],
                    "binding_policy": {
                        "prefer_value_roles": ["aggregate"],
                        "prefer_aggregation_stages": ["final"],
                    },
                }
            },
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "ontology.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            ontology = FinancialOntologyManager(path)

            spec = ontology.concept_specs("demo alias")[0]
            self.assertEqual(spec["concept"], "demo_concept")
            self.assertEqual(
                spec["binding_policy"]["prefer_value_roles"],
                ["aggregate"],
            )
            self.assertEqual(
                spec["binding_policy"]["prefer_aggregation_stages"],
                ["final"],
            )

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

    def test_v3_matches_ampc_production_tax_credit_concept(self) -> None:
        specs = self.ontology_v3.concept_specs(
            "미국 인플레이션 감축법(IRA)에 따른 세액공제(AMPC) 금액을 제외해 줘.",
            intent="comparison",
        )
        concept_keys = [spec["concept"] for spec in specs]

        self.assertIn("advanced_manufacturing_production_credit", concept_keys)
        ampc = next(spec for spec in specs if spec["concept"] == "advanced_manufacturing_production_credit")
        self.assertIn("IRA Tax Credit", ampc["aliases"])
        self.assertIn("이사의 경영진단 및 분석의견", ampc["preferred_sections"])

    def test_v3_maps_equipment_investment_alias_to_capex_concept(self) -> None:
        specs = self.ontology_v3.concept_specs(
            "2023\ub144 \uc124\ube44\ud22c\uc790 \ucd1d\uc561\uc744 \ucc3e\uc544\uc918.",
            intent="comparison",
        )
        concept_keys = [spec["concept"] for spec in specs]

        self.assertIn("capital_expenditure_total", concept_keys)
        capex = next(spec for spec in specs if spec["concept"] == "capital_expenditure_total")
        self.assertIn("\uc124\ube44\ud22c\uc790", capex["aliases"])
        self.assertIn("\uc6d0\uc7ac\ub8cc \ubc0f \uc0dd\uc0b0\uc124\ube44", capex["preferred_sections"])

    def test_v3_ampc_concept_does_not_match_general_ira_policy_context(self) -> None:
        specs = self.ontology_v3.concept_specs(
            "인플레이션 감축법(IRA) 등 보호무역주의 정책에 대한 대응 필요성을 요약해 줘.",
            intent="trend",
        )
        concept_keys = [spec["concept"] for spec in specs]

        self.assertNotIn("advanced_manufacturing_production_credit", concept_keys)

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


    def test_default_runtime_ontology_includes_concept_overlay(self) -> None:
        specs = self.ontology.concept_specs(
            "2023년 연결 손익계산서에서 법인세비용차감전순이익을 추출하고 전년 대비 증감액을 계산해 줘.",
            intent="comparison",
        )
        concept_keys = [spec["concept"] for spec in specs]
        self.assertIn("income_before_income_taxes", concept_keys)

    def test_default_runtime_ontology_matches_spaced_income_before_tax_alias(self) -> None:
        specs = self.ontology.concept_specs(
            "2023년 연결 손익계산서에서 법인세비용 차감 전 당기순손익을 찾아줘.",
            intent="comparison",
        )
        concept_keys = [spec["concept"] for spec in specs]
        self.assertIn("income_before_income_taxes", concept_keys)


    def test_v3_maps_operating_loss_surface_to_operating_income_concept(self) -> None:
        specs = self.ontology_v3.concept_specs(
            "2023년 SK온 영업손실의 전체 연결 영업이익 대비 비중을 계산해 줘",
            intent="comparison",
        )
        concept_keys = [spec["concept"] for spec in specs]
        self.assertIn("operating_income", concept_keys)


    def test_v3_matches_dart_derived_note_concepts(self) -> None:
        cases = [
            ("2023년 이자비용과 이자수익을 찾아줘", {"interest_expense", "interest_income"}),
            ("2023년 대손상각비와 손실충당금 전입액을 찾아줘", {"bad_debt_expense", "credit_loss_provision_expense"}),
            ("2023년 감가상각비와 무형자산상각비를 찾아줘", {"depreciation_expense", "amortization_expense"}),
            ("2023년 손상차손과 영업권손상차손을 찾아줘", {"impairment_loss", "goodwill_impairment_loss"}),
        ]

        for query, expected_concepts in cases:
            with self.subTest(query=query):
                specs = self.ontology_v3.concept_specs(query, intent="comparison")
                concept_keys = {spec["concept"] for spec in specs}
                self.assertTrue(expected_concepts.issubset(concept_keys))

    def test_v3_interest_expense_requires_direct_interest_cost_surface(self) -> None:
        concept = self.ontology_v3.concepts["interest_expense"]

        self.assertNotIn("금융비용", concept.get("aliases") or [])
        self.assertNotIn("금융비용", concept.get("keywords") or [])
        self.assertIn("이자비용", (concept.get("surface_contract") or {}).get("positive") or [])
        self.assertIn("금융비용", (concept.get("surface_contract") or {}).get("negative") or [])
        self.assertTrue((concept.get("binding_policy") or {}).get("require_surface_contract_for_direct_lookup"))
        self.assertTrue((concept.get("binding_policy") or {}).get("require_surface_contract_for_direct_match"))


if __name__ == "__main__":
    unittest.main()
