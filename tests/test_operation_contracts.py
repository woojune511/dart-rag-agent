import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_helpers import (
    _assign_ratio_roles_to_concepts,
    _build_concept_task_constraints,
    _build_generic_required_operands,
    _build_generic_retrieval_queries,
    _candidate_direct_match_strength,
    _candidate_is_direct_grounding_candidate,
    _candidate_matches_operand,
    _candidate_matches_operand_target_year,
    _candidate_row_block_signature,
    _candidate_satisfies_direct_acceptance_contract,
    _coerce_lookup_magnitude_value,
    _desired_statement_types,
    _extract_generic_operand_labels,
    _label_implies_percent_metric,
    _normalise_operand_value,
    _operand_target_years,
    _operand_row_matches_requirement,
    _order_concept_specs_by_query,
    _resolve_candidate_local_unit_hint,
    _requires_direct_numeric_grounding,
    _structured_cell_period_text,
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

    def test_structured_cell_period_text_uses_report_year_for_current_fiscal_cell(self) -> None:
        period = _structured_cell_period_text(
            {
                "column_headers": ["제54기"],
                "_report_year": 2022,
                "_sibling_cells": [
                    {"column_headers": ["제54기"], "_report_year": 2022},
                    {"column_headers": ["제53기"], "_report_year": 2022},
                ],
            },
            [2023, 2022],
            "current",
        )
        self.assertEqual(period, "2022")

    def test_structured_cell_period_text_uses_report_year_for_prior_fiscal_cell(self) -> None:
        period = _structured_cell_period_text(
            {
                "column_headers": ["제53기"],
                "_report_year": 2022,
                "_sibling_cells": [
                    {"column_headers": ["제54기"], "_report_year": 2022},
                    {"column_headers": ["제53기"], "_report_year": 2022},
                ],
            },
            [2023, 2022],
            "prior",
        )
        self.assertEqual(period, "2021")

    def test_operating_expense_lookup_coerces_parenthesized_statement_value_to_positive_magnitude(self) -> None:
        normalized_value, normalized_unit = _normalise_operand_value("(8,181,823,307)", "천원")
        coerced = _coerce_lookup_magnitude_value(
            normalized_value=normalized_value,
            normalized_unit=normalized_unit,
            raw_value="(8,181,823,307)",
            concept="operating_expense_total",
            statement_type="income_statement",
            row_label="영업비용 (주25)",
            semantic_label="영업비용",
        )
        self.assertEqual(normalized_unit, "KRW")
        self.assertEqual(coerced, 8_181_823_307_000.0)

    def test_cost_of_sales_lookup_coerces_parenthesized_statement_value_to_positive_magnitude(self) -> None:
        normalized_value, normalized_unit = _normalise_operand_value("(60,000,000)", "백만원")
        coerced = _coerce_lookup_magnitude_value(
            normalized_value=normalized_value,
            normalized_unit=normalized_unit,
            raw_value="(60,000,000)",
            concept="cost_of_sales",
            statement_type="income_statement",
            row_label="매출원가",
            semantic_label="매출원가",
        )
        self.assertEqual(normalized_unit, "KRW")
        self.assertEqual(coerced, 60_000_000_000_000.0)

    def test_desired_statement_types_uses_ontology_matched_concepts(self) -> None:
        statement_types = _desired_statement_types(
            "2023년 손익계산서에서 매출원가와 판매비와관리비를 합산해 매출액 대비 영업비용률을 계산해 줘.",
            "",
        )
        self.assertIn("income_statement", statement_types)
        self.assertIn("summary_financials", statement_types)

    def test_extract_generic_operand_labels_uses_ontology_match_seeds(self) -> None:
        labels = _extract_generic_operand_labels(
            "2023년 손익계산서에서 매출원가와 판매비와관리비를 합산해 총 영업비용을 구한 뒤, 전체 매출액 대비 영업비용률을 계산해 줘."
        )
        self.assertIn("매출원가", labels)
        self.assertIn("판매비와관리비", labels)
        self.assertIn("매출액", labels)

    def test_non_expense_lookup_preserves_negative_parenthesized_value(self) -> None:
        normalized_value, normalized_unit = _normalise_operand_value("(1,234)", "천원")
        coerced = _coerce_lookup_magnitude_value(
            normalized_value=normalized_value,
            normalized_unit=normalized_unit,
            raw_value="(1,234)",
            concept="pretax_income",
            statement_type="income_statement",
            row_label="법인세비용차감전순이익",
            semantic_label="법인세비용차감전순이익",
        )
        self.assertEqual(normalized_unit, "KRW")
        self.assertEqual(coerced, -1_234_000.0)

    def test_resolved_period_text_prefers_report_year_when_it_matches_target_year(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        period = agent._resolved_period_text_for_operand(
            operand={"label": "2023 시설투자(CAPEX)", "role": "current_period", "period_hint": "2023"},
            cell={"column_headers": [], "_report_year": 2022},
            query_years=[2023, 2022],
            period_focus="multi_period",
        )
        self.assertEqual(period, "2022")

    def test_resolved_period_text_does_not_shift_report_year_for_prior_without_explicit_headers(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        period = agent._resolved_period_text_for_operand(
            operand={"label": "2022 시설투자(CAPEX)", "role": "prior_period", "period_hint": "2022"},
            cell={"column_headers": [], "_report_year": 2023},
            query_years=[2023, 2022],
            period_focus="multi_period",
        )
        self.assertEqual(period, "2023")

    def test_operand_target_years_prefers_latest_year_for_current_period_role(self) -> None:
        years = _operand_target_years(
            {"label": "시설투자(CAPEX)", "role": "current_period"},
            [2023, 2022],
        )
        self.assertEqual(years, [2023])

    def test_operand_target_years_prefers_second_latest_year_for_prior_period_role(self) -> None:
        years = _operand_target_years(
            {"label": "시설투자(CAPEX)", "role": "prior_period"},
            [2023, 2022],
        )
        self.assertEqual(years, [2022])

    def test_capex_total_rejects_non_aggregate_note_detail_candidate(self) -> None:
        operand = {
            "label": "시설투자(CAPEX)",
            "concept": "capital_expenditure_total",
            "role": "operand",
            "preferred_sections": ["원재료 및 생산설비", "시설투자", "사업의 내용"],
        }
        candidate = {
            "candidate_kind": "structured_value",
            "metadata": {
                "row_label": "일반취득 및 자본적지출(*1)",
                "semantic_label": "일반취득 및 자본적지출",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "local_heading": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "statement_type": "notes",
                "value_role": "detail",
                "aggregation_stage": "none",
            },
        }
        self.assertFalse(
            _candidate_satisfies_direct_acceptance_contract(
                candidate,
                operand=operand,
                constraints={"period_focus": "unknown"},
                query_years=[2022],
                operation_family="lookup",
                selected_cell={"column_headers": ["2022"], "value_text": "117,933", "unit_hint": "백만원"},
            )
        )

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

    def test_generic_required_operands_extract_share_of_total_ratio_roles(self) -> None:
        operands = _build_generic_required_operands(
            "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
            {"company": "네이버", "year": 2023},
        )
        self.assertEqual(
            [(row["label"], row["role"]) for row in operands],
            [
                ("인건비(종업원급여)", "numerator_1"),
                ("영업비용", "denominator_1"),
            ],
        )
        self.assertIn("종업원급여", operands[0]["aliases"])
        self.assertIn("인건비", operands[0]["aliases"])
        self.assertEqual(operands[1]["binding_policy"]["prefer_value_roles"][:1], ["aggregate"])
        self.assertEqual(
            operands[1]["binding_policy"]["prefer_aggregation_stages"][:3],
            ["final", "subtotal", "direct"],
        )

    def test_generic_ratio_retrieval_queries_include_combined_numerator_denominator_terms(self) -> None:
        queries = _build_generic_retrieval_queries(
            query="2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
            metric_label="영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
            operand_specs=[
                {
                    "label": "인건비(종업원급여)",
                    "aliases": ["인건비", "종업원급여"],
                    "role": "numerator_1",
                },
                {
                    "label": "영업비용",
                    "aliases": ["영업비용"],
                    "role": "denominator_1",
                },
            ],
            preferred_sections=["영업비용", "연결재무제표 주석", "손익계산서"],
            report_scope={"company": "네이버", "year": 2023},
            constraints={"period_focus": "current"},
        )
        self.assertTrue(any("2023년 영업비용 인건비(종업원급여)" in item for item in queries))
        self.assertTrue(any("2023년 종업원급여 연결재무제표 주석" in item for item in queries))

    def test_generic_ratio_operand_rejects_liability_row_for_non_liability_label(self) -> None:
        row = {
            "label": "단기종업원급여부채",
            "matched_operand_label": "",
            "matched_operand_concept": "",
            "matched_operand_role": "numerator_1",
        }
        operand = {
            "label": "인건비(종업원급여)",
            "aliases": ["인건비", "종업원급여"],
            "role": "numerator_1",
        }
        self.assertFalse(_operand_row_matches_requirement(row, operand))

    def test_generic_ratio_denominator_accepts_aggregate_total_row_via_table_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        rows = agent._build_required_operands_from_candidates(
            [
                {
                    "evidence_id": "ev_001",
                    "source_anchor": "[네이버 | 2023 | III. 재무에 관한 사항 > 연결재무제표 주석(영업비용)]",
                    "source_context": "[표: III. 재무에 관한 사항 > 연결재무제표 주석(영업비용)]",
                    "raw_row_text": "합계 | 8,181,823,307 | 7,520,000,000",
                    "metadata": {
                        "table_context": "III. 재무에 관한 사항 > 연결재무제표 주석(영업비용)",
                        "table_header_context": "구분 | 2023년 | 2022년",
                        "unit_hint": "천원",
                        "statement_type": "notes",
                        "consolidation_scope": "consolidated",
                    },
                }
            ],
            required_operands=[
                {
                    "label": "영업비용",
                    "aliases": ["영업비용"],
                    "role": "denominator_1",
                    "binding_policy": {
                        "prefer_value_roles": ["aggregate"],
                        "prefer_aggregation_stages": ["final", "subtotal", "direct"],
                    },
                }
            ],
            query="2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
            topic="영업비용",
            report_scope={"company": "네이버", "year": 2023},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["matched_operand_label"], "영업비용")
        self.assertEqual(rows[0]["matched_operand_role"], "denominator_1")
        self.assertEqual(rows[0]["period"], "2023년")
        self.assertEqual(rows[0]["normalized_unit"], "KRW")
        self.assertEqual(rows[0]["normalized_value"], 8181823307000.0)

    def test_share_of_total_ratio_assigns_roles_from_query_shape(self) -> None:
        concept_specs = [
            {
                "name": "영업비용",
                "concept": "operating_expense_total",
                "aliases": ["영업비용 합계"],
                "keywords": ["영업비용"],
            },
            {
                "name": "종업원급여",
                "concept": "employee_benefits_expense",
                "aliases": ["인건비", "인건비(종업원급여)"],
                "keywords": ["종업원급여", "인건비"],
            },
        ]

        roles = _assign_ratio_roles_to_concepts(
            "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
            concept_specs,
        )

        ordered_specs = _order_concept_specs_by_query(
            concept_specs,
            "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
        )
        paired = sorted(
            [
                (spec["concept"], role)
                for spec, role in zip(ordered_specs, roles)
                if role
            ]
        )
        self.assertEqual(
            paired,
            [
                ("employee_benefits_expense", "numerator_1"),
                ("operating_expense_total", "denominator_1"),
            ],
        )

    def test_contextual_aggregate_match_requires_local_metric_context(self) -> None:
        operand = {
            "label": "영업비용",
            "concept": "operating_expense_total",
            "aliases": ["영업비용 합계", "영업비용 총계"],
            "binding_policy": {
                "prefer_value_roles": ["aggregate"],
                "prefer_aggregation_stages": ["final", "subtotal", "direct"],
            },
            "surface_contract": {
                "positive": ["영업비용"],
                "negative": [],
            },
        }
        broad_context_candidate = {
            "candidate_kind": "table_row",
            "text": "합계 | 12,602,060",
            "metadata": {
                "row_label": "합계",
                "row_text": "합계 | 12,602,060",
                "row_context_text": "공시금액 종업원급여(*) ... 합계 8,181,823,307 영업비용",
                "local_heading": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "table_context": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "value_role": "aggregate",
                "aggregation_stage": "final",
            },
        }
        local_metric_candidate = {
            "candidate_kind": "table_row",
            "text": "합계 | 8,181,823,307",
            "metadata": {
                "row_label": "합계",
                "row_text": "합계 | 8,181,823,307",
                "row_context_text": "종업원급여(*) 1,701,418,940 ... 합계 8,181,823,307",
                "local_heading": "25. 영업비용 (연결)",
                "table_context": "25. 영업비용 (연결)",
                "table_summary_text": "당기 및 전기 중 영업비용의 내역은 다음과 같습니다.",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "value_role": "aggregate",
                "aggregation_stage": "final",
            },
        }

        self.assertFalse(_candidate_matches_operand(broad_context_candidate, operand))
        self.assertLess(_candidate_direct_match_strength(broad_context_candidate, operand), 1.0)
        self.assertTrue(_candidate_matches_operand(local_metric_candidate, operand))
        self.assertGreaterEqual(_candidate_direct_match_strength(local_metric_candidate, operand), 1.0)

    def test_structured_value_does_not_match_only_broad_table_context(self) -> None:
        operand = {
            "label": "영업비용",
            "concept": "operating_expense_total",
            "aliases": ["영업비용 합계", "영업비용 총계"],
            "binding_policy": {
                "prefer_value_roles": ["aggregate"],
                "prefer_aggregation_stages": ["final", "subtotal", "direct"],
            },
            "surface_contract": {
                "positive": ["영업비용"],
                "negative": [],
            },
        }
        wrong_structured_value = {
            "candidate_kind": "structured_value",
            "text": "25. 영업비용 (연결) 종업원급여(*) 1,492,548,615 합계 6,915,414,298",
            "metadata": {
                "row_label": "종업원급여(*)",
                "semantic_label": "종업원급여",
                "local_heading": "25. 영업비용 (연결)",
                "table_context": "25. 영업비용 (연결)",
                "row_context_text": "종업원급여(*) 1,492,548,615 ... 합계 6,915,414,298 영업비용",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "value_role": "detail",
                "aggregation_stage": "direct",
            },
        }

        self.assertFalse(_candidate_matches_operand(wrong_structured_value, operand))

    def test_candidate_row_block_signature_tracks_local_subtable_header(self) -> None:
        row_context_text = "\n".join(
            [
                "| 주식결제형 주식기준보상 | 현금결제형 주식기준보상 | 양도제한조건부 주식",
                "종업원 주식기준보상거래로부터의 비용 | 85,523 | 55,935 | 49,909",
                "| 공시금액",
                "법정적립금(*) | 8,240,670",
                "합계 | 24,544,359,051",
                "| 공시금액",
                "종업원급여(*) | 1,701,418,940",
                "합계 | 8,181,823,307",
            ]
        )
        reserve_candidate = {
            "metadata": {
                "table_source_id": "notes_table",
                "row_index": 4,
                "row_text": "합계 | 24,544,359,051",
                "row_context_text": row_context_text,
            }
        }
        operating_expense_candidate = {
            "metadata": {
                "table_source_id": "notes_table",
                "row_index": 7,
                "row_text": "합계 | 8,181,823,307",
                "row_context_text": row_context_text,
            }
        }

        self.assertNotEqual(
            _candidate_row_block_signature(reserve_candidate),
            _candidate_row_block_signature(operating_expense_candidate),
        )

    def test_candidate_target_year_respects_prior_period_focus(self) -> None:
        current_operand = {
            "label": "2023년 종업원급여",
            "concept": "employee_benefits_expense",
            "role": "current_period",
            "period_hint": "2023",
        }
        prior_operand = {
            "label": "2022년 종업원급여",
            "concept": "employee_benefits_expense",
            "role": "prior_period",
            "period_hint": "2022",
        }
        prior_candidate = {
            "candidate_kind": "structured_value",
            "metadata": {
                "year": 2023,
                "period_focus": "prior",
                "period_labels": ["전기"],
            },
        }
        current_candidate = {
            "candidate_kind": "structured_value",
            "metadata": {
                "year": 2023,
                "period_focus": "current",
                "period_labels": ["당기"],
            },
        }

        self.assertFalse(_candidate_matches_operand_target_year(prior_candidate, current_operand, [2023]))
        self.assertTrue(_candidate_matches_operand_target_year(current_candidate, current_operand, [2023]))
        self.assertTrue(_candidate_matches_operand_target_year(prior_candidate, prior_operand, [2023]))

    def test_unknown_separate_note_candidate_is_rejected_for_consolidated_lookup(self) -> None:
        operand = {
            "label": "2023년 종업원급여",
            "concept": "employee_benefits_expense",
            "aliases": ["종업원급여", "인건비"],
            "role": "current_period",
            "period_hint": "2023",
        }
        separate_note_candidate = {
            "candidate_kind": "structured_row",
            "text": "종업원급여(*) | 594,106,898",
            "metadata": {
                "row_label": "종업원급여(*)",
                "semantic_label": "종업원급여",
                "statement_type": "notes",
                "consolidation_scope": "unknown",
                "section_path": "III. 재무에 관한 사항 > 5. 재무제표 주석",
                "table_context": "III. 재무에 관한 사항 > 5. 재무제표 주석",
                "period_focus": "current",
                "period_labels": ["당기"],
                "year": 2023,
                "structured_cells": [
                    {"column_headers": ["공시금액"], "value_text": "594,106,898", "unit_hint": "천원"}
                ],
            },
        }

        self.assertFalse(
            _candidate_is_direct_grounding_candidate(
                separate_note_candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
                query_years=[2023],
                operation_family="lookup",
                report_scope={"company": "네이버", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240318000844"},
            )
        )

    def test_unknown_section_four_financial_statement_candidate_is_inferred_as_separate(self) -> None:
        operand = {
            "label": "영업비용",
            "concept": "operating_expense_total",
            "aliases": ["영업비용", "영업비용 합계"],
            "role": "primary_value",
            "binding_policy": {
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        separate_candidate = {
            "candidate_kind": "structured_value",
            "text": "영업비용 (주24) | (3,896,593,637,516)",
            "metadata": {
                "row_label": "영업비용 (주24)",
                "semantic_label": "영업비용 (주24)",
                "statement_type": "income_statement",
                "consolidation_scope": "unknown",
                "section_path": "III. 재무에 관한 사항 > 4. 재무제표",
                "period_focus": "current",
                "period_labels": ["제 25 기"],
                "year": 2023,
                "structured_cells": [
                    {"column_headers": ["제 25 기"], "value_text": "(3,896,593,637,516)", "unit_hint": "원"}
                ],
            },
        }

        self.assertFalse(
            _candidate_is_direct_grounding_candidate(
                separate_candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
                query_years=[2023],
                operation_family="lookup",
                report_scope={"company": "네이버", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240318000844"},
            )
        )

    def test_prior_table_row_candidate_is_rejected_for_current_lookup(self) -> None:
        operand = {
            "label": "2023년 종업원급여",
            "concept": "employee_benefits_expense",
            "aliases": ["종업원급여", "종업원급여(*)", "인건비"],
            "role": "numerator_1",
            "period_hint": "2023",
            "binding_policy": {
                "prefer_value_roles": ["detail", "aggregate"],
                "prefer_aggregation_stages": ["direct", "final", "subtotal", "none"],
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        candidate = {
            "candidate_kind": "table_row",
            "text": "종업원급여(*) | 1,492,548,615",
            "metadata": {
                "row_label": "종업원급여(*)",
                "row_text": "종업원급여(*) | 1,492,548,615",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "table_context": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "period_focus": "prior",
                "year": 2023,
            },
        }

        self.assertFalse(
            _candidate_is_direct_grounding_candidate(
                candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
                query_years=[2023],
                operation_family="lookup",
                report_scope={"company": "네이버", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240318000844"},
            )
        )

    def test_table_row_broad_row_labels_do_not_create_direct_match(self) -> None:
        operand = {
            "label": "2023년 종업원급여",
            "concept": "employee_benefits_expense",
            "aliases": ["종업원급여", "종업원급여(*)", "인건비"],
            "role": "numerator_1",
            "period_hint": "2023",
            "binding_policy": {
                "prefer_value_roles": ["detail", "aggregate"],
                "prefer_aggregation_stages": ["direct", "final", "subtotal", "none"],
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        candidate = {
            "candidate_kind": "table_row",
            "text": "합계 | 6,915,414,298",
            "metadata": {
                "row_label": "합계",
                "aggregate_label": "합계",
                "row_text": "합계 | 6,915,414,298",
                "table_row_labels_text": "\n".join(["공시금액", "종업원급여(*)", "기타", "합계"]),
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "table_context": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "period_focus": "current",
                "year": 2023,
            },
        }

        self.assertFalse(_candidate_matches_operand(candidate, operand))
        self.assertLess(_candidate_direct_match_strength(candidate, operand), 1.0)

    def test_lookup_direct_acceptance_rejects_raw_table_row_when_structured_records_exist(self) -> None:
        operand = {
            "label": "영업비용",
            "concept": "operating_expense_total",
            "aliases": ["영업비용", "영업비용 합계", "영업비용 총계"],
            "role": "primary_value",
            "binding_policy": {
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        candidate = {
            "candidate_kind": "table_row",
            "text": "영업비용 (주25) | (8,181,823,306,977)",
            "metadata": {
                "row_label": "영업비용 (주25)",
                "row_text": "영업비용 (주25) | (8,181,823,306,977)",
                "statement_type": "income_statement",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["제 25 기"],
                "year": 2023,
                "table_row_records_json": "[{\"row_id\":\"0:0\",\"row_label\":\"영업비용 (주25)\",\"row_headers\":[\"영업비용 (주25)\"]}]",
                "table_value_records_json": "[{\"value_id\":\"x\",\"row_label\":\"영업비용 (주25)\",\"semantic_label\":\"영업비용 (주25)\",\"semantic_aliases\":[\"영업비용 (주25)\"]}]",
            },
        }

        self.assertFalse(
            _candidate_is_direct_grounding_candidate(
                candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
                query_years=[2023],
                operation_family="lookup",
                report_scope={"company": "네이버", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240318000844"},
            )
        )

    def test_lookup_direct_acceptance_allows_raw_table_row_when_no_matching_structured_sibling_exists(self) -> None:
        operand = {
            "label": "2023년 종업원급여",
            "concept": "employee_benefits_expense",
            "aliases": ["종업원급여", "종업원급여(*)", "인건비"],
            "role": "primary_value",
            "binding_policy": {
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        candidate = {
            "candidate_kind": "table_row",
            "text": "종업원급여(*) | 1,701,418,940",
            "metadata": {
                "row_label": "종업원급여(*)",
                "row_text": "종업원급여(*) | 1,701,418,940",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "period_focus": "unknown",
                "period_labels": [],
                "year": 2023,
                "value_role": "detail",
                "aggregation_stage": "none",
                "table_row_records_json": "[{\"row_id\":\"0:0\",\"row_label\":\"무위험이자율\",\"row_headers\":[\"무위험이자율\"]}]",
                "table_value_records_json": "[{\"value_id\":\"x\",\"row_label\":\"무위험이자율\",\"semantic_label\":\"무위험이자율\",\"semantic_aliases\":[\"무위험이자율\"]}]",
            },
        }

        self.assertTrue(
            _candidate_is_direct_grounding_candidate(
                candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
                query_years=[2023],
                operation_family="lookup",
                report_scope={"company": "네이버", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240318000844"},
            )
        )

    def test_lookup_direct_match_strips_note_reference_parentheticals(self) -> None:
        operand = {
            "label": "영업비용",
            "concept": "operating_expense_total",
            "aliases": ["영업비용", "영업비용 합계", "영업비용 총계"],
            "role": "primary_value",
            "binding_policy": {
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        candidate = {
            "candidate_kind": "structured_value",
            "text": "영업비용 (주25) | (8,181,823,306,977)",
            "metadata": {
                "row_label": "영업비용 (주25)",
                "semantic_label": "영업비용 (주25)",
                "statement_type": "income_statement",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["제 25 기", "제 24 기"],
                "year": 2023,
                "value_role": "detail",
                "aggregation_stage": "none",
                "structured_cells": [
                    {"column_headers": ["제 25 기"], "value_text": "(8,181,823,306,977)", "unit_hint": "원"},
                    {"column_headers": ["제 24 기"], "value_text": "(6,915,414,298,267)", "unit_hint": "원"},
                ],
            },
        }

        self.assertGreaterEqual(_candidate_direct_match_strength(candidate, operand), 2.5)
        self.assertTrue(
            _candidate_satisfies_direct_acceptance_contract(
                candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
                query_years=[2023],
                operation_family="lookup",
                selected_cell={"column_headers": ["제 25 기"], "value_text": "(8,181,823,306,977)", "unit_hint": "원", "_report_year": 2023},
                report_scope={"company": "네이버", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240318000844"},
            )
        )

    def test_operand_text_match_ignores_leading_year_prefix_for_lookup_labels(self) -> None:
        operand = {
            "label": "2023년 영업비용",
            "concept": "operating_expense_total",
            "aliases": ["영업비용", "영업비용 합계", "영업비용 총계"],
            "role": "primary_value",
            "binding_policy": {
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        candidate = {
            "candidate_kind": "structured_value",
            "text": "영업비용 (주25) | (8,181,823,306,977)",
            "metadata": {
                "row_label": "영업비용 (주25)",
                "semantic_label": "영업비용 (주25)",
                "statement_type": "income_statement",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["제 25 기", "제 24 기"],
                "year": 2023,
                "value_role": "detail",
                "aggregation_stage": "none",
                "structured_cells": [
                    {"column_headers": ["제 25 기"], "value_text": "(8,181,823,306,977)", "unit_hint": "원"},
                    {"column_headers": ["제 24 기"], "value_text": "(6,915,414,298,267)", "unit_hint": "원"},
                ],
            },
        }

        self.assertTrue(_candidate_matches_operand(candidate, operand))
        self.assertGreaterEqual(_candidate_direct_match_strength(candidate, operand), 2.5)

    def test_operand_text_match_ignores_leading_year_prefix_for_note_rows(self) -> None:
        operand = {
            "label": "2023년 종업원급여",
            "concept": "employee_benefits_expense",
            "aliases": ["종업원급여", "종업원급여(*)", "인건비"],
            "role": "primary_value",
            "binding_policy": {
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        candidate = {
            "candidate_kind": "structured_value",
            "text": "종업원급여(*) | 1,701,418,940",
            "metadata": {
                "row_label": "종업원급여(*)",
                "semantic_label": "종업원급여(*)",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["2023"],
                "year": 2023,
                "value_role": "detail",
                "aggregation_stage": "none",
                "structured_cells": [
                    {"column_headers": ["공시금액"], "value_text": "1,701,418,940", "unit_hint": "천원"},
                ],
            },
        }

        self.assertTrue(_candidate_matches_operand(candidate, operand))
        self.assertGreaterEqual(_candidate_direct_match_strength(candidate, operand), 2.5)

    def test_lookup_direct_acceptance_rejects_broad_partial_related_party_label(self) -> None:
        operand = {
            "label": "영업비용",
            "concept": "operating_expense_total",
            "aliases": ["영업비용", "영업비용 합계", "영업비용 총계"],
            "role": "primary_value",
            "binding_policy": {
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        candidate = {
            "candidate_kind": "structured_value",
            "text": "영업비용 등 | 11,781,510",
            "metadata": {
                "row_label": "영업비용 등",
                "semantic_label": "영업비용 등",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["2023"],
                "year": 2023,
                "value_role": "detail",
                "aggregation_stage": "none",
                "structured_cells": [
                    {
                        "column_headers": ["전체 특수관계자", "특수관계자", "관계기업"],
                        "value_text": "11,781,510",
                        "unit_hint": "천원",
                    }
                ],
            },
        }

        self.assertLess(_candidate_direct_match_strength(candidate, operand), 2.0)
        self.assertFalse(
            _candidate_satisfies_direct_acceptance_contract(
                candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
                query_years=[2023],
                operation_family="lookup",
                selected_cell={
                    "column_headers": ["전체 특수관계자", "특수관계자", "관계기업"],
                    "value_text": "11,781,510",
                    "unit_hint": "천원",
                    "_report_year": 2023,
                },
                report_scope={"company": "네이버", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240318000844"},
            )
        )

    def test_lookup_direct_acceptance_rejects_mda_raw_table_row_for_canonical_statement_operand(self) -> None:
        operand = {
            "label": "2023년 영업비용",
            "concept": "operating_expense_total",
            "aliases": ["영업비용", "영업비용 합계", "영업비용 총계"],
            "role": "primary_value",
            "binding_policy": {
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        candidate = {
            "candidate_kind": "table_row",
            "text": "영업비용 | 8,181.8 | 6,915.4 | 18.3% | 100.0%",
            "metadata": {
                "row_label": "영업비용",
                "row_text": "영업비용 | 8,181.8 | 6,915.4 | 18.3% | 100.0%",
                "statement_type": "mda",
                "consolidation_scope": "unknown",
                "period_focus": "multi_period",
                "period_labels": ["당기", "2023", "2022"],
                "year": 2023,
                "value_role": "detail",
                "aggregation_stage": "none",
            },
        }

        self.assertFalse(
            _candidate_is_direct_grounding_candidate(
                candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
                query_years=[2023],
                operation_family="lookup",
                report_scope={"company": "네이버", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240318000844"},
            )
        )

    def test_resolve_candidate_local_unit_hint_uses_nearest_report_unit(self) -> None:
        candidate = {
            "metadata": {
                "chunk_uid": "20240318000844:240:156",
                "year": 2023,
                "row_label": "종업원급여(*)",
            }
        }
        report_html = """
        <P>당기</P>
        <P>(단위 : 천원)</P>
        <P USERMARK=\"F-GL11\">종업원급여(*)</P>
        <P USERMARK=\"F-GL11\">1,701,418,940</P>
        """
        with patch("src.agent.financial_graph_helpers._resolve_report_path_from_receipt", return_value="dummy.html"), patch(
            "src.agent.financial_graph_helpers._cached_report_text",
            return_value=report_html,
        ):
            self.assertEqual(
                _resolve_candidate_local_unit_hint(candidate, "1,701,418,940"),
                "천원",
            )

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

    def test_growth_rate_coerces_unknown_prior_unit_from_same_concept_current_row(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._execute_calculation(
            {
                "query": "2023년 시설투자(CAPEX) 총액과 전년 대비 증감률을 계산해 줘.",
                "active_subtask": {
                    "task_id": "task_capex_growth",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "시설투자(CAPEX) 총액 증감률",
                    "query": "2023년 시설투자(CAPEX) 총액과 전년 대비 증감률을 계산해 줘.",
                    "operation_family": "growth_rate",
                },
                "calculation_operands": [
                    {
                        "operand_id": "op_001",
                        "evidence_id": "capex_2023",
                        "label": "2023 시설투자(CAPEX)",
                        "raw_value": "531,139",
                        "raw_unit": "억원",
                        "normalized_value": 53113900000000.0,
                        "normalized_unit": "KRW",
                        "period": "2023",
                        "matched_operand_concept": "capital_expenditure_total",
                        "matched_operand_role": "current_period",
                    },
                    {
                        "operand_id": "op_002",
                        "evidence_id": "capex_2022",
                        "label": "2022 시설투자(CAPEX)",
                        "raw_value": "531,153",
                        "raw_unit": "",
                        "normalized_value": 531153.0,
                        "normalized_unit": "UNKNOWN",
                        "period": "2022",
                        "matched_operand_concept": "capital_expenditure_total",
                        "matched_operand_role": "prior_period",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "growth_rate",
                    "ordered_operand_ids": ["op_001", "op_002"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "op_001"},
                        {"variable": "B", "operand_id": "op_002"},
                    ],
                    "formula": "((A - B) / B) * 100",
                    "pairwise_formula": "",
                    "result_unit": "%",
                    "operation_text": "시설투자(CAPEX) 총액 증감률",
                    "explanation": "growth rate",
                },
                "artifacts": [],
                "tasks": [],
            }
        )
        calc = result["calculation_result"]
        self.assertEqual(calc["status"], "ok")
        self.assertEqual(calc["answer_slots"]["prior_value"]["normalized_unit"], "KRW")
        self.assertEqual(calc["answer_slots"]["prior_value"]["raw_unit"], "억원")
        self.assertEqual(calc["rendered_value"], "-0.0026%")
        trace_operands = list((result.get("resolved_calculation_trace") or {}).get("calculation_operands") or [])
        prior_operand = next(row for row in trace_operands if row.get("operand_id") == "op_002")
        self.assertEqual(prior_operand["normalized_unit"], "KRW")
        self.assertEqual(prior_operand["raw_unit"], "억원")

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

    def test_generic_required_operands_map_capex_query_to_capital_expenditure_total(self) -> None:
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            operands = _build_generic_required_operands(
                "2023년 시설투자(CAPEX) 총액을 찾고 전년 대비 증감률을 계산해 줘.",
                {"company": "삼성전자", "year": 2023},
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(
            [(row["concept"], row["role"]) for row in operands],
            [
                ("capital_expenditure_total", "current_period"),
                ("capital_expenditure_total", "prior_period"),
            ],
        )
        self.assertTrue(all("원재료 및 생산설비" in row.get("preferred_sections", []) for row in operands))


if __name__ == "__main__":
    unittest.main()
