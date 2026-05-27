import json
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
    _candidate_explicit_years,
    _build_concept_task_constraints,
    _infer_concept_ratio_result_unit,
    _build_generic_required_operands,
    _build_generic_retrieval_queries,
    _build_lookup_producer_task_from_binding,
    _build_table_row_reconciliation_candidates,
    _candidate_direct_match_strength,
    _candidate_is_direct_grounding_candidate,
    _candidate_matches_operand,
    _candidate_matches_operand_target_year,
    _candidate_selected_cell_for_operand,
    _candidate_row_block_signature,
    _candidate_satisfies_direct_acceptance_contract,
    _coerce_lookup_magnitude_value,
    _desired_consolidation_scope,
    _desired_statement_types,
    _extract_generic_operand_labels,
    _label_implies_percent_metric,
    _normalise_operand_value,
    _operand_target_years,
    _operand_row_matches_requirement,
    _order_concept_specs_by_query,
    _resolve_candidate_local_unit_hint,
    _requires_direct_numeric_grounding,
    _retrieval_hint_from_topic,
    _structured_cell_period_text,
    _supplement_section_terms_for_query,
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
    def test_financial_statement_queries_default_to_consolidated_scope(self) -> None:
        self.assertEqual(
            _desired_consolidation_scope(
                "2023년 재무제표 주석에서 재고자산평가손실 규모를 찾아줘.",
                {"company": "삼성전자", "year": 2023},
            ),
            "consolidated",
        )
        self.assertEqual(
            _desired_consolidation_scope(
                "2023년 별도 재무제표 주석에서 재고자산평가손실 규모를 찾아줘.",
                {"company": "삼성전자", "year": 2023},
            ),
            "separate",
        )

    def test_quantitative_impact_answer_uses_retrieved_labeled_values(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._compose_supported_quantitative_impact_answer(
            query="2023년 주석에서 손상차손 규모를 찾고 이것이 영업비용에 미친 영향을 분석해 줘.",
            evidence_items=[
                {
                    "evidence_id": "ev_001",
                    "claim": "손상차손 2,000",
                    "metadata": {
                        "table_value_labels_text": "손상차손 2,000",
                        "unit_hint": "백만원",
                        "statement_type": "notes",
                        "consolidation_scope": "consolidated",
                        "period_focus": "current",
                    },
                },
                {
                    "evidence_id": "ev_002",
                    "claim": "영업비용 100,000",
                    "metadata": {
                        "table_value_labels_text": "영업비용 100,000",
                        "unit_hint": "백만원",
                        "statement_type": "income_statement",
                        "consolidation_scope": "consolidated",
                        "period_focus": "current",
                    },
                },
            ],
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("손상차손은 2,000백만원", result["answer"])
        self.assertIn("영업비용 100,000백만원 대비 약 2.00%", result["answer"])
        self.assertEqual(result["supporting_claim_ids"], ["ev_001", "ev_002"])

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

    def test_candidate_explicit_years_infers_current_and_prior_from_relative_headers(self) -> None:
        candidate = {
            "metadata": {
                "year": 2023,
                "structured_cells": [
                    {"column_headers": ["연결", "당기", "금액"], "value_text": "2,546,649"},
                    {"column_headers": ["연결", "전기", "금액"], "value_text": "1,801,079"},
                ],
            }
        }
        self.assertEqual(_candidate_explicit_years(candidate), [2022, 2023])

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

    def test_numeric_impairment_lookup_supplements_goodwill_total_and_impairment_row(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row_records = [
            {
                "row_label": "손상 및 환입",
                "cells": [
                    {"column_headers": ["산업재산권"], "value_text": "(177,537)"},
                    {"column_headers": ["영업권"], "value_text": "(19,630,042)"},
                ],
            },
            {
                "row_label": "기말금액",
                "cells": [
                    {"column_headers": ["산업재산권"], "value_text": "1,420,529"},
                    {"column_headers": ["영업권"], "value_text": "2,578,089,956"},
                ],
            },
        ]
        metadata = {
            "company": "네이버",
            "year": 2023,
            "report_type": "사업보고서",
            "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
            "statement_type": "notes",
            "consolidation_scope": "consolidated",
            "unit_hint": "천원",
            "table_row_records_json": json.dumps(row_records, ensure_ascii=False),
        }
        docs = [
            (
                Document(
                    page_content="| 산업재산권 | 브랜드 | 소프트웨어 | 영업권 | ...",
                    metadata=metadata,
                ),
                1.0,
            )
        ]
        supplemented = agent._supplement_numeric_impairment_lookup(
            {
                "query": "2023년 연결재무제표 주석에서 인식된 '영업권(Goodwill)'의 총액을 찾고, 손상차손 발생 여부를 확인해 줘."
            },
            docs,
        )
        self.assertIsNotNone(supplemented)
        self.assertIn("2,578,089,956천원", supplemented["answer"])
        self.assertIn("손상차손이 발생", supplemented["answer"])
        self.assertEqual(len(supplemented["evidence_items"]), 2)

    def test_extract_numeric_fact_uses_deterministic_impairment_lookup_after_llm_failure(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _FailingLLM()
        row_records = [
            {
                "row_label": "손상 및 환입",
                "cells": [
                    {"column_headers": ["영업권"], "value_text": "(19,630,042)"},
                ],
            },
            {
                "row_label": "기말금액",
                "cells": [
                    {"column_headers": ["영업권"], "value_text": "2,578,089,956"},
                ],
            },
        ]
        metadata = {
            "company": "네이버",
            "year": 2023,
            "report_type": "사업보고서",
            "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
            "statement_type": "notes",
            "consolidation_scope": "consolidated",
            "unit_hint": "천원",
            "table_row_records_json": json.dumps(row_records, ensure_ascii=False),
        }
        result = agent._extract_numeric_fact(
            {
                "query": "2023년 연결재무제표 주석에서 인식된 '영업권(Goodwill)'의 총액을 찾고, 손상차손 발생 여부를 확인해 줘.",
                "retrieved_docs": [
                    (
                        Document(
                            page_content="| 산업재산권 | 브랜드 | 소프트웨어 | 영업권 | ...",
                            metadata=metadata,
                        ),
                        1.0,
                    )
                ],
            }
        )
        self.assertIn("2,578,089,956천원", result["answer"])
        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertEqual(result["selected_claim_ids"], ["ev_001", "ev_002"])

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

    def test_concept_ratio_result_unit_infers_times_for_coverage_ratio(self) -> None:
        query = "\uc774\uc790\ubcf4\uc0c1\ubc30\uc728(\uc601\uc5c5\uc774\uc775 / \uc774\uc790\ube44\uc6a9)\uc744 \uacc4\uc0b0\ud574\uc918"
        self.assertEqual(_infer_concept_ratio_result_unit(query, "\uc774\uc790\ubcf4\uc0c1\ubc30\uc728", "ratio"), "\ubc30")

    def test_foreign_currency_gain_lookup_coerces_parenthesized_amount_to_magnitude(self) -> None:
        normalized_value, normalized_unit = _normalise_operand_value("(573,884)", "\ubc31\ub9cc\uc6d0")
        coerced = _coerce_lookup_magnitude_value(
            normalized_value=normalized_value,
            normalized_unit=normalized_unit,
            raw_value="(573,884)",
            concept="foreign_currency_translation_gain",
            statement_type="notes",
            row_label="\uc678\ud654\ud658\uc0b0\uc774\uc775",
            semantic_label="\uc678\ud654\ud658\uc0b0\uc774\uc775",
        )
        self.assertEqual(normalized_unit, "KRW")
        self.assertEqual(coerced, 573_884_000_000.0)

    def test_inventory_loss_surface_contract_rejects_summary_etc_row(self) -> None:
        operand = {
            "label": "\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4",
            "concept": "inventory_valuation_loss",
            "surface_contract": {
                "positive": ["\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4"],
                "negative": ["\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4 \ub4f1"],
            },
        }
        candidate = {
            "candidate_kind": "structured_value",
            "metadata": {
                "semantic_label": "\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4 \ub4f1",
                "row_label": "\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4 \ub4f1",
                "unit_hint": "\ubc31\ub9cc\uc6d0",
            },
        }
        self.assertFalse(_candidate_matches_operand(candidate, operand))

    def test_table_object_rows_expand_to_reconciliation_candidates(self) -> None:
        metadata = {
            "unit_hint": "\ucc9c\uc6d0",
            "statement_type": "notes",
            "consolidation_scope": "consolidated",
            "period_focus": "current",
            "table_object_json": json.dumps(
                {
                    "rows": [
                        {
                            "row_label": "\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4",
                            "row_headers": ["\uc870\uc815\ud56d\ubaa9\uc5d0 \uc758\ud55c \ud569\uacc4", "\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4"],
                            "cells": [
                                {
                                    "column_headers": ["\uacf5\uc2dc\uae08\uc561"],
                                    "value_text": "2,526,280",
                                    "unit_hint": "\ucc9c\uc6d0",
                                }
                            ],
                        }
                    ]
                },
                ensure_ascii=False,
            ),
        }

        candidates = _build_table_row_reconciliation_candidates(
            candidate_id_prefix="report:chunk",
            anchor="[셀트리온 | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
            table_text="",
            metadata=metadata,
        )

        candidate = next(
            item
            for item in candidates
            if item["candidate_kind"] == "structured_row"
            and item["metadata"]["row_label"] == "\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4"
        )
        self.assertEqual(candidate["candidate_kind"], "structured_row")
        self.assertEqual(candidate["metadata"]["row_label"], "\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4")
        self.assertEqual(candidate["metadata"]["semantic_label"], "\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4")
        self.assertEqual(candidate["metadata"]["structured_cells"][0]["value_text"], "2,526,280")
        self.assertTrue(
            _candidate_matches_operand(
                candidate,
                {
                    "label": "\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4",
                    "concept": "inventory_valuation_loss",
                    "surface_contract": {
                        "positive": ["\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4"],
                        "negative": ["\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4\ud658\uc785"],
                    },
                },
            )
        )

    def test_inventory_loss_ontology_removes_ambiguous_reversal_aliases(self) -> None:
        concept = self.ontology.concept("inventory_valuation_loss") or {}
        aliases = list(concept.get("aliases") or [])
        keywords = list(concept.get("keywords") or [])

        self.assertNotIn("\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4(\ud658\uc785)", aliases)
        self.assertNotIn("\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4(\ub610\ub294 \ud658\uc785)", aliases)
        self.assertNotIn("\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4(\ud658\uc785)", keywords)

    def test_lookup_retrieval_queries_include_ontology_query_surfaces(self) -> None:
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            queries = _build_generic_retrieval_queries(
                query="2023\ub144 \uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4\uc744 \ucc3e\uc544\uc918.",
                metric_label="\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4",
                operand_specs=[
                    {
                        "label": "2023\ub144 \uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4",
                        "concept": "inventory_valuation_loss",
                        "aliases": ["\uc7ac\uace0\uc790\uc0b0 \ud3c9\uac00\uc190\uc2e4"],
                    }
                ],
                preferred_sections=["\uc601\uc5c5\uc73c\ub85c\ubd80\ud130 \ucc3d\ucd9c\ub41c \ud604\uae08"],
                report_scope={"year": 2023},
                constraints={"period_focus": "current"},
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        joined_queries = "\n".join(queries)
        self.assertIn(
            "\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4 \uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4\ud658\uc785 \uc7ac\uace0\uc790\uc0b0\ud3d0\uae30\uc190\uc2e4",
            joined_queries,
        )
        self.assertIn("\uc601\uc5c5\uc73c\ub85c\ubd80\ud130 \ucc3d\ucd9c\ub41c \ud604\uae08", joined_queries)

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
        self.assertFalse(any("2023년 2022년 [" in item for item in queries))

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

    def test_lookup_producer_task_preserves_binding_concept_for_generic_consumer_operand(self) -> None:
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            task = _build_lookup_producer_task_from_binding(
                binding={
                    "role": "denominator_1",
                    "concept": "operating_expense_total",
                    "period": "2023",
                    "label": "영업비용",
                },
                consumer_task={
                    "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
                    "metric_label": "종업원급여 비중",
                    "operation_family": "ratio",
                    "required_operands": [
                        {"label": "종업원급여", "role": "numerator_1"},
                        {"label": "영업비용", "role": "denominator_1"},
                    ],
                    "constraints": {"consolidation_scope": "consolidated", "period_focus": "current"},
                },
                next_task_id="task_2",
                report_scope={"company": "NAVER", "year": 2023, "report_type": "사업보고서"},
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        operand = task["required_operands"][0]
        self.assertEqual(task["metric_family"], "concept_lookup")
        self.assertEqual(operand["concept"], "operating_expense_total")
        self.assertIn("영업비용", operand["surface_contract"]["positive"])
        self.assertIn("종업원급여", operand["surface_contract"]["negative"])
        self.assertEqual(task["preferred_statement_types"], ["income_statement", "summary_financials"])

        employee_benefits_candidate = {
            "candidate_kind": "table_row",
            "text": "종업원급여(*) | 1,701,418,940",
            "metadata": {
                "row_label": "종업원급여(*)",
                "row_text": "종업원급여(*) | 1,701,418,940",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "table_context": "25. 영업비용 (연결)",
                "local_heading": "25. 영업비용 (연결)",
                "period_focus": "current",
                "period_labels": ["2023"],
                "year": 2023,
                "value_role": "detail",
                "aggregation_stage": "none",
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "1,701,418,940", "unit_hint": "천원"}
                ],
            },
        }
        self.assertFalse(
            _candidate_is_direct_grounding_candidate(
                employee_benefits_candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
                query_years=[2023],
                operation_family="lookup",
                report_scope={"company": "NAVER", "year": 2023, "report_type": "사업보고서"},
            )
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

    def test_segment_bound_retrieval_queries_prefix_generic_aliases_with_segment_label(self) -> None:
        queries = _build_generic_retrieval_queries(
            query="커머스 부문의 2023년 매출 성장률(전년 대비)을 계산해 줘.",
            metric_label="커머스 부문 매출 성장률",
            operand_specs=[
                {
                    "label": "2023년 커머스 매출액",
                    "aliases": ["매출액", "매출", "영업수익"],
                    "role": "current_period",
                    "period_hint": "당기",
                    "binding_policy": {"segment_label": "커머스"},
                },
                {
                    "label": "2022년 커머스 매출액",
                    "aliases": ["매출액", "매출", "영업수익"],
                    "role": "prior_period",
                    "period_hint": "전기",
                    "binding_policy": {"segment_label": "커머스"},
                },
            ],
            preferred_sections=["부문정보", "영업부문"],
            report_scope={"company": "네이버", "year": 2023},
            constraints={"period_focus": "multi_period", "segment_scope": "segment"},
        )
        self.assertTrue(any("2023년 당기 커머스 매출액" in item for item in queries))
        self.assertTrue(any("2022년 전기 커머스 영업수익" in item for item in queries))
        self.assertFalse(any(item == "2023년 매출액" for item in queries))
        self.assertFalse(any(item == "2022년 영업수익" for item in queries))

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

    def test_lookup_direct_acceptance_requires_row_local_segment_surface(self) -> None:
        operand = {
            "label": "2023년 커머스 매출액",
            "concept": "revenue",
            "aliases": ["커머스 매출액", "커머스 매출", "매출액", "매출", "영업수익", "수익"],
            "role": "current_period",
            "binding_policy": {
                "segment_label": "커머스",
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        candidate = {
            "candidate_kind": "structured_value",
            "text": "매출액 9조 6,706억원 (커머스 부문 실적 설명 포함)",
            "metadata": {
                "row_label": "매출액",
                "semantic_label": "매출액",
                "statement_type": "income_statement",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["2023"],
                "year": 2023,
                "value_role": "aggregate",
                "aggregation_stage": "final",
                "local_heading": "연결 손익계산서",
                "section_path": "III. 재무에 관한 사항 > 2. 연결재무제표 > 2-2. 연결 손익계산서",
                "table_summary_text": "커머스 부문 실적 설명과 함께 매출액이 언급된다.",
            },
        }

        self.assertFalse(
            _candidate_satisfies_direct_acceptance_contract(
                candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current", "segment_scope": "segment"},
                query_years=[2023],
                operation_family="lookup",
                selected_cell=None,
                report_scope={"company": "네이버", "year": 2023, "report_type": "사업보고서"},
            )
        )

    def test_lookup_direct_acceptance_allows_segment_row_when_row_surface_matches(self) -> None:
        operand = {
            "label": "2023년 커머스 매출액",
            "concept": "revenue",
            "aliases": ["커머스 매출액", "커머스 매출", "매출액", "매출", "영업수익", "수익"],
            "role": "current_period",
            "binding_policy": {
                "segment_label": "커머스",
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        candidate = {
            "candidate_kind": "structured_value",
            "text": "- 커머스 | 2,546,649",
            "metadata": {
                "row_label": "- 커머스",
                "semantic_label": "- 커머스",
                "semantic_aliases": ["- 커머스", "연결", "금액"],
                "row_headers": ["- 커머스"],
                "table_row_labels_text": "영업수익\n- 커머스\n- 핀테크",
                "value_text": "2,546,649",
                "statement_type": "unknown",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["당기"],
                "year": 2023,
                "value_role": "detail",
                "aggregation_stage": "none",
                "local_heading": "가. 부문별 매출실적 > (2) 서비스별 영업현황",
                "section_path": "II. 사업의 내용 > 4. 매출 및 수주상황",
                "structured_cells": [
                    {
                        "column_headers": ["연결", "당기", "금액"],
                        "value_text": "2,546,649",
                        "unit_hint": "백만원",
                    }
                ],
            },
        }

        self.assertTrue(
            _candidate_satisfies_direct_acceptance_contract(
                candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current", "segment_scope": "segment"},
                query_years=[2023],
                operation_family="lookup",
                selected_cell=None,
                report_scope={"company": "네이버", "year": 2023, "report_type": "사업보고서"},
            )
        )

    def test_lookup_direct_acceptance_allows_prior_segment_row_from_latest_multi_report_receipt(self) -> None:
        operand = {
            "label": "2022년 커머스 매출액",
            "concept": "revenue",
            "aliases": ["커머스 매출액", "커머스 매출", "매출액", "매출", "영업수익", "수익"],
            "role": "prior_period",
            "binding_policy": {
                "segment_label": "커머스",
                "prefer_period_focus": "prior",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        candidate = {
            "candidate_kind": "structured_value",
            "text": "- 커머스 | 2,546,649 | 1,801,079",
            "metadata": {
                "row_label": "- 커머스",
                "semantic_label": "- 커머스",
                "semantic_aliases": ["- 커머스", "연결", "금액"],
                "row_headers": ["- 커머스"],
                "table_row_labels_text": "영업수익\n- 커머스\n- 핀테크",
                "statement_type": "unknown",
                "consolidation_scope": "consolidated",
                "period_focus": "multi_period",
                "period_labels": ["당기", "전기"],
                "year": 2023,
                "rcept_no": "20240318000844",
                "value_role": "detail",
                "aggregation_stage": "none",
                "local_heading": "가. 부문별 매출실적 > (2) 서비스별 영업현황",
                "section_path": "II. 사업의 내용 > 4. 매출 및 수주상황",
                "structured_cells": [
                    {"column_headers": ["연결", "당기", "금액"], "value_text": "2,546,649", "unit_hint": "백만원"},
                    {"column_headers": ["연결", "당기", "비중"], "value_text": "26.4", "unit_hint": "백만원"},
                    {"column_headers": ["연결", "전기", "금액"], "value_text": "1,801,079", "unit_hint": "백만원"},
                    {"column_headers": ["연결", "전기", "비중"], "value_text": "21.9", "unit_hint": "백만원"},
                ],
            },
        }

        selected_cell = _candidate_selected_cell_for_operand(
            candidate,
            operand=operand,
            query_years=[2023, 2022],
            period_focus="prior",
        )
        self.assertIsNotNone(selected_cell)
        self.assertEqual((selected_cell or {}).get("value_text"), "1,801,079")
        self.assertTrue(
            _candidate_satisfies_direct_acceptance_contract(
                candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "prior", "segment_scope": "segment"},
                query_years=[2023, 2022],
                operation_family="lookup",
                selected_cell=selected_cell,
                report_scope={
                    "source_reports": [
                        {"corp_name": "NAVER", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240318000844"},
                        {"corp_name": "NAVER", "year": 2022, "report_type": "사업보고서", "rcept_no": "20230314001049"},
                    ]
                },
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

    def test_lookup_calculation_preserves_source_table_unit_in_rendered_value(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._execute_calculation(
            {
                "query": "2023년 재고자산평가손실을 찾아줘.",
                "active_subtask": {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 재고자산평가손실",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "2023년 재고자산평가손실",
                            "concept": "inventory_valuation_loss",
                            "role": "current_period",
                            "required": True,
                        }
                    ],
                },
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "lookup",
                    "ordered_operand_ids": ["op_001"],
                    "variable_bindings": [{"variable": "A", "operand_id": "op_001"}],
                    "formula": "A",
                    "result_unit": "천원",
                },
                "calculation_operands": [
                    {
                        "operand_id": "op_001",
                        "evidence_id": "row_001",
                        "label": "2023년 재고자산평가손실",
                        "matched_operand_label": "2023년 재고자산평가손실",
                        "matched_operand_concept": "inventory_valuation_loss",
                        "matched_operand_role": "current_period",
                        "raw_value": "2,526,280",
                        "raw_unit": "천원",
                        "normalized_value": 2526280000.0,
                        "normalized_unit": "KRW",
                        "period": "2023",
                    }
                ],
                "artifacts": [],
                "tasks": [],
            }
        )

        calculation_result = result["calculation_result"]
        self.assertEqual(calculation_result["rendered_value"], "2,526,280천원")
        self.assertEqual(calculation_result["series"][0]["rendered_value"], "2,526,280천원")
        primary_value = calculation_result["answer_slots"]["primary_value"]
        self.assertEqual(primary_value["raw_value"], "2,526,280")
        self.assertEqual(primary_value["raw_unit"], "천원")
        self.assertEqual(primary_value["rendered_value"], "2,526,280천원")

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

    def test_operand_requirement_rejects_conflicting_row_concept_even_when_label_matches(self) -> None:
        row = {
            "label": "2023년 영업비용",
            "concept": "employee_benefits_expense",
            "matched_operand_role": "primary_value",
            "raw_value": "1,701,418,940",
        }
        operand = {
            "label": "2023년 영업비용",
            "concept": "operating_expense_total",
            "role": "primary_value",
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

    def test_direct_numeric_mixed_query_preserves_narrative_evidence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            EvidenceExtraction(
                coverage="sufficient",
                evidence=[
                    {
                        "source_anchor": "[NAVER | 2023 | IV. 이사의 경영진단 및 분석의견 > 3. 재무상태 및 영업실적 > 나. 영업실적]",
                        "claim": "커머스 부문 매출은 2조 5,466억원으로 전년 대비 41.4% 증가했다.",
                        "quote_span": "커머스 | 2,546,649 | 1,801,079",
                        "support_level": "direct",
                        "question_relevance": "high",
                        "allowed_terms": ["커머스", "매출"],
                    },
                    {
                        "source_anchor": "[NAVER | 2023 | IV. 이사의 경영진단 및 분석의견]",
                        "claim": "2023년 초 글로벌 C2C 경쟁력 강화를 위해 인수한 Poshmark의 성공적인 체질 개선이 커머스 성장에 기여했다.",
                        "quote_span": "Poshmark의 성공적인 체질 개선",
                        "support_level": "direct",
                        "question_relevance": "high",
                        "allowed_terms": ["Poshmark", "커머스"],
                    },
                ],
            )
        )
        state = {
            "query": "2023년 커머스 부문 매출 성장률을 계산하고, 포시마크 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            "query_type": "trend",
            "topic": "커머스 부문 매출 성장률과 포시마크 영향",
            "retrieved_docs": [
                (
                    Document(
                        page_content="커머스 | 2,546,649 | 1,801,079",
                        metadata={
                            "company": "NAVER",
                            "year": 2023,
                            "section_path": "IV. 이사의 경영진단 및 분석의견 > 3. 재무상태 및 영업실적 > 나. 영업실적",
                            "block_type": "table",
                            "table_source_id": "20240318000844:418:3",
                            "table_header_context": "서비스별 영업수익 당기 전기",
                        },
                    ),
                    1.0,
                ),
                (
                    Document(
                        page_content="2023년 초 글로벌 C2C 경쟁력 강화를 위해 인수한 Poshmark의 성공적인 체질 개선이 커머스 성장에 기여했다.",
                        metadata={
                            "company": "NAVER",
                            "year": 2023,
                            "section_path": "IV. 이사의 경영진단 및 분석의견",
                            "block_type": "paragraph",
                        },
                    ),
                    0.9,
                ),
            ],
            "active_subtask": {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "커머스 부문 매출 성장률",
                "query": "2023년 커머스 부문 매출 성장률을 계산해 줘.",
                "operation_family": "growth_rate",
                "required_operands": [
                    {
                        "label": "2023년 커머스 매출액",
                        "concept": "revenue",
                        "role": "current_period",
                        "required": True,
                    },
                    {
                        "label": "2022년 커머스 매출액",
                        "concept": "revenue",
                        "role": "prior_period",
                        "required": True,
                    },
                ],
            },
        }

        result = agent._extract_evidence(state)

        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertEqual(len(result["evidence_items"]), 2)
        self.assertTrue(any("Poshmark" in str(item.get("claim") or "") for item in result["evidence_items"]))
        self.assertTrue(
            any(
                "Poshmark" in str(item.get("claim") or "")
                and str((item.get("metadata") or {}).get("block_type") or "") == "paragraph"
                for item in result["evidence_items"]
            )
        )

    def test_narrative_summary_doc_selection_prefers_mda_paragraphs(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        reranked = [
            (
                Document(
                    page_content="커머스 | 2,546.6 | 1,801.1 | 41.4%",
                    metadata={
                        "chunk_id": "table-1",
                        "block_type": "table",
                        "section_path": "IV. 이사의 경영진단 및 분석의견 > 3. 재무상태 및 영업실적 > 나. 영업실적",
                    },
                ),
                0.95,
            ),
            (
                Document(
                    page_content=(
                        "서치플랫폼은 신규 상품 출시와 AI 기술을 활용한 플랫폼 고도화로 "
                        "광고 효율을 개선했습니다."
                    ),
                    metadata={
                        "chunk_id": "generic-iv",
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견",
                    },
                ),
                0.99,
            ),
            (
                Document(
                    page_content=(
                        "Poshmark 인수 계약의 목적 및 내용은 글로벌 커머스 시장 진출이며, "
                        "예상효과는 Discovery형 소셜 커머스를 결합해 북미 시장을 공략하는 것입니다."
                    ),
                    metadata={
                        "chunk_id": "contract-1",
                        "block_type": "paragraph",
                        "section_path": "II. 사업의 내용 > 6. 주요계약 및 연구개발활동",
                    },
                ),
                0.98,
            ),
            (
                Document(
                    page_content=(
                        "네이버의 커머스 사업은 스마트스토어와 브랜드스토어의 지속적인 성장, "
                        "그리고 2023년 초 글로벌 C2C 경쟁력 강화를 위해 인수한 Poshmark의 성공적인 체질 개선 등으로 "
                        "전년 대비 41.4% 성장하였습니다."
                    ),
                    metadata={
                        "chunk_id": "para-1",
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견 > 3. 재무상태 및 영업실적 > 나. 영업실적",
                    },
                ),
                0.72,
            ),
            (
                Document(
                    page_content="사업 개요 문단",
                    metadata={
                        "chunk_id": "para-2",
                        "block_type": "paragraph",
                        "section_path": "II. 사업의 내용 > 1. 사업의 개요",
                    },
                ),
                0.70,
            ),
        ]
        state = {
            "query": "커머스 부문의 2023년 매출 성장률을 계산하고, 포시마크 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            "active_subtask": {
                "operation_family": "narrative_summary",
            },
        }

        docs = agent._select_narrative_summary_docs(reranked, state, 3)

        self.assertEqual(docs[0][0].metadata.get("chunk_id"), "para-1")
        self.assertNotEqual(docs[0][0].metadata.get("chunk_id"), "contract-1")
        self.assertNotEqual(docs[0][0].metadata.get("chunk_id"), "generic-iv")

    def test_narrative_summary_doc_selection_adds_missing_driver_from_table_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        reranked = [
            (
                Document(
                    page_content=(
                        "네이버의 커머스 사업은 스마트스토어와 브랜드스토어의 지속적인 성장, "
                        "그리고 2023년 초 글로벌 C2C 경쟁력 강화를 위해 인수한 Poshmark의 성공적인 체질 개선 등으로 "
                        "전년 대비 41.4% 성장하였습니다."
                    ),
                    metadata={
                        "chunk_id": "para-turnaround",
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견 > 3. 재무상태 및 영업실적 > 나. 영업실적",
                    },
                ),
                0.92,
            ),
            (
                Document(
                    page_content="요약 테이블",
                    metadata={
                        "chunk_id": "table-effect",
                        "block_type": "table",
                        "section_path": "IV. 이사의 경영진단 및 분석의견",
                        "table_context": "Poshmark 연결 편입효과에 따른 영업수익 증가",
                    },
                ),
                0.71,
            ),
        ]
        state = {
            "query": "커머스 부문의 2023년 매출 성장률을 계산하고, 포시마크 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            "active_subtask": {
                "operation_family": "narrative_summary",
            },
        }

        docs = agent._select_narrative_summary_docs(reranked, state, 3)
        chunk_ids = [item[0].metadata.get("chunk_id") for item in docs]

        self.assertIn("table-effect", chunk_ids)

    def test_narrative_summary_doc_selection_prefers_dividend_policy_sections(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        reranked = [
            (
                Document(
                    page_content="연결 현금흐름표 일부",
                    metadata={
                        "chunk_id": "cashflow-table",
                        "block_type": "table",
                        "section_path": "III. 재무에 관한 사항 > 2. 연결재무제표",
                        "table_context": "배당금 지급 9조 8,645억원",
                    },
                ),
                0.84,
            ),
            (
                Document(
                    page_content=(
                        "당사의 유동성은 당기 영업활동 현금흐름으로 유입되었고, "
                        "배당금 지급 9조 8,645억원 등이 유출되었습니다."
                    ),
                    metadata={
                        "chunk_id": "liquidity-payout",
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견 > 유동성 및 자금조달",
                    },
                ),
                0.83,
            ),
            (
                Document(
                    page_content=(
                        "2024년 1월 2024~2026년의 주주환원 정책을 발표하였으며 "
                        "잉여현금흐름의 50%를 재원으로 활용하여 연간 9.8조원 수준의 정규배당을 유지하고 "
                        "정규배당 이후에도 잔여 재원이 발생하는 경우 추가로 환원할 계획입니다."
                    ),
                    metadata={
                        "chunk_id": "dividend-policy",
                        "block_type": "paragraph",
                        "section_path": "III. 재무에 관한 사항 > 6. 배당에 관한 사항",
                    },
                ),
                0.67,
            ),
            (
                Document(
                    page_content="일반 경영진단 문단",
                    metadata={
                        "chunk_id": "generic-mda",
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견",
                    },
                ),
                0.79,
            ),
        ]
        state = {
            "query": "2023년 연결 현금흐름표에서 '배당금 지급'으로 유출된 현금 규모를 찾고, 사업보고서의 '배당에 관한 사항'을 바탕으로 2024~2026년 주주환원 정책을 요약해 줘.",
            "active_subtask": {
                "operation_family": "narrative_summary",
            },
        }

        docs = agent._select_narrative_summary_docs(reranked, state, 3)
        chunk_ids = [item[0].metadata.get("chunk_id") for item in docs]

        self.assertIn("dividend-policy", chunk_ids[:2])
        self.assertIn("liquidity-payout", chunk_ids)

    def test_dividend_policy_hybrid_answer_prefers_cashflow_payout_over_policy_dividend_total(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        query = (
            "2023년 연결 현금흐름표에서 '배당금 지급'으로 유출된 현금 규모를 찾고, "
            "사업보고서의 '배당에 관한 사항'을 바탕으로 2024~2026년 주주환원 정책을 요약해 줘."
        )
        evidence_items = [
            {
                "evidence_id": "ev_000",
                "source_anchor": "20240312000736::III. 재무에 관한 사항 > 6. 배당에 관한 사항",
                "claim": "2023년(제55기) 연결 현금흐름표에서 '배당금 지급'으로 유출된 현금 규모는 9조 8,094억원입니다.",
                "quote_span": "현금배당금총액(백만원) | 9,809,438",
                "metadata": {
                    "section_path": "III. 재무에 관한 사항 > 6. 배당에 관한 사항",
                    "table_context": "2021~2023년 주주환원 정책",
                },
            },
            {
                "evidence_id": "ev_001",
                "source_anchor": "20240312000736::IV. 이사의 경영진단 및 분석의견",
                "claim": (
                    "당기말 현재 당사 차입금은 12조 6,859억원이며, "
                    "당사의 유동성은 ... 배당금 지급 9조 8,645억원 등이 유출되었으며"
                ),
                "quote_span": (
                    "당기말 현재 당사 차입금은 12조 6,859억원이며, "
                    "배당금 지급 9조 8,645억원 등이 유출되었으며"
                ),
                "metadata": {
                    "section_path": "IV. 이사의 경영진단 및 분석의견 > 유동성 및 자금조달",
                },
            },
            {
                "evidence_id": "ev_001b",
                "source_anchor": "20240312000736::III. 재무에 관한 사항 > 6. 배당에 관한 사항",
                "claim": "당사는 2021~2023년의 주주환원 정책에 따라 3년간 잉여현금흐름의 50%를 재원으로 정규 배당을 연간 총 9.8조원 수준으로 실시하였습니다.",
                "quote_span": "2021~2023년의 주주환원 정책에 따라 3년간 잉여현금흐름의 50%를 재원으로 정규 배당을 연간 총 9.8조원 수준으로 실시하였습니다.",
                "metadata": {
                    "section_path": "III. 재무에 관한 사항 > 6. 배당에 관한 사항",
                },
            },
            {
                "evidence_id": "ev_002",
                "source_anchor": "20240312000736::III. 재무에 관한 사항 > 6. 배당에 관한 사항",
                "claim": (
                    "2024년부터 2026년까지 3년간 발생하는 잉여현금흐름의 50%를 재원으로 활용하여 "
                    "연간 9.8조원 수준의 정규배당을 유지하되, 정규배당 이후에도 잔여 재원이 발생하는 경우에 추가로 환원할 계획입니다."
                ),
                "quote_span": (
                    "2024년부터 2026년까지 3년간 발생하는 잉여현금흐름의 50%를 재원으로 활용하여 "
                    "연간 9.8조원 수준의 정규배당을 유지하되, 정규배당 이후에도 잔여 재원이 발생하는 경우에 추가로 환원할 계획입니다."
                ),
            },
        ]

        result = agent._compose_dividend_policy_hybrid_answer(query=query, evidence_items=evidence_items)

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("9조 8,645억원", result["answer"])
        self.assertIn("잉여현금흐름의 50%", result["answer"])
        self.assertIn("정규배당", result["answer"])
        self.assertIn("추가로 환원", result["answer"])
        self.assertNotIn("9조 8,094억원", result["answer"])
        self.assertNotIn("2021~2023년", result["answer"])

    def test_dividend_policy_evidence_supplement_adds_cashflow_and_policy_snippets(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        query = (
            "2023년 연결 현금흐름표에서 '배당금 지급'으로 유출된 현금 규모를 찾고, "
            "사업보고서의 '배당에 관한 사항'을 바탕으로 2024~2026년 주주환원 정책을 요약해 줘."
        )
        docs = [
            (
                Document(
                    page_content=(
                        "당사의 유동성은 당기 영업활동 현금흐름으로 44조 1,374억원이 유입되었고, "
                        "유·무형자산의 취득 60조 5,342억원, 배당금 지급 9조 8,645억원 등이 유출되었습니다."
                    ),
                    metadata={
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견 > 유동성 및 자금조달",
                    },
                ),
                0.91,
            ),
            (
                Document(
                    page_content=(
                        "2024년부터 2026년까지 3년간 발생하는 잉여현금흐름의 50%를 재원으로 활용하여 "
                        "연간 9.8조원 수준의 정규배당을 유지하되, 정규배당 이후에도 잔여 재원이 발생하는 경우에 추가로 환원할 계획입니다."
                    ),
                    metadata={
                        "block_type": "paragraph",
                        "section_path": "III. 재무에 관한 사항 > 6. 배당에 관한 사항",
                    },
                ),
                0.87,
            ),
        ]

        supplemented = agent._supplement_dividend_policy_evidence(
            [],
            docs,
            query=query,
            anchor_lookup={},
        )

        merged = " ".join(str(item.get("claim") or "") for item in supplemented)
        self.assertIn("9조 8,645억원", merged)
        self.assertIn("정규배당", merged)
        self.assertIn("추가로 환원", merged)

    def test_direct_numeric_operand_extraction_preserves_narrative_supplement_for_mixed_query(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "query": "2023년 커머스 부문 매출 성장률을 계산하고, 포시마크 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            "query_type": "trend",
            "intent": "trend",
            "topic": "커머스 부문 매출 성장률과 포시마크 영향",
            "active_subtask": {
                "task_id": "task_lookup",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 커머스 매출액",
                "query": "2023년 커머스 매출액을 찾아 줘.",
                "operation_family": "lookup",
                "required_operands": [
                    {
                        "label": "2023년 커머스 매출액",
                        "concept": "revenue",
                        "role": "current_period",
                        "required": True,
                    }
                ],
            },
            "evidence_items": [
                {
                    "evidence_id": "ev_001",
                    "source_anchor": "[NAVER | 2023 | IV. 이사의 경영진단 및 분석의견 > 3. 재무상태 및 영업실적 > 나. 영업실적]",
                    "claim": "커머스 | 2,546,649 | 1,801,079",
                    "quote_span": "커머스 | 2,546,649 | 1,801,079",
                    "support_level": "direct",
                    "metadata": {
                        "block_type": "table",
                        "table_source_id": "20240318000844:418:3",
                    },
                    "raw_row_text": "커머스 | 2,546,649 | 1,801,079",
                },
                {
                    "evidence_id": "ev_002",
                    "source_anchor": "[NAVER | 2023 | IV. 이사의 경영진단 및 분석의견]",
                    "claim": "2023년 초 글로벌 C2C 경쟁력 강화를 위해 인수한 Poshmark의 성공적인 체질 개선이 커머스 성장에 기여했다.",
                    "quote_span": "Poshmark의 성공적인 체질 개선",
                    "support_level": "direct",
                    "metadata": {"block_type": "paragraph"},
                },
            ],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "sufficient",
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "subtask_results": [],
        }
        direct_rows = [
            {
                "evidence_id": "ev_recon_001",
                "label": "2023년 커머스 매출액",
                "matched_operand_label": "2023년 커머스 매출액",
                "matched_operand_role": "current_period",
                "raw_value": "2조 5,466억원",
                "normalized_value": 2546649000000.0,
                "normalized_unit": "KRW",
                "source_anchor": "[NAVER | 2023 | IV. 이사의 경영진단 및 분석의견 > 3. 재무상태 및 영업실적 > 나. 영업실적]",
            }
        ]
        reconciliation_evidence = [
            {
                "evidence_id": "ev_recon_001",
                "source_anchor": "[NAVER | 2023 | IV. 이사의 경영진단 및 분석의견 > 3. 재무상태 및 영업실적 > 나. 영업실적]",
                "claim": "커머스 | 2,546,649 | 1,801,079",
                "quote_span": "커머스 | 2,546,649 | 1,801,079",
                "raw_row_text": "커머스 | 2,546,649 | 1,801,079",
                "support_level": "direct",
                "metadata": {
                    "block_type": "table",
                    "table_source_id": "20240318000844:418:3",
                },
            }
        ]

        with patch.object(agent, "_extract_structured_operands_from_reconciliation", return_value=direct_rows), patch.object(
            agent,
            "_evidence_items_from_reconciliation_matches",
            return_value=reconciliation_evidence,
        ):
            result = agent._extract_calculation_operands(state)

        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertEqual(len(result["evidence_items"]), 2)
        self.assertTrue(any("Poshmark" in str(item.get("claim") or "") for item in result["evidence_items"]))

    def test_narrative_summary_supplements_missing_consolidation_effect_driver(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        metadata = {
            "company": "NAVER",
            "year": 2023,
            "report_type": "사업보고서",
            "section_path": "IV. 이사의 경영진단 및 분석의견 > 3. 재무상태 및 영업실적 > 나. 영업실적",
            "section": "경영진단",
            "block_type": "paragraph",
            "chunk_id": "mda-001",
        }
        docs = [
            (
                Document(
                    page_content=(
                        "커머스는 Poshmark의 성공적인 체질 개선 등으로 전년 대비 41.4% 성장했습니다. "
                        "또한 Poshmark 연결 편입효과에 따른 영업수익 증가가 이어졌습니다."
                    ),
                    metadata=metadata,
                ),
                0.92,
            )
        ]
        anchor = agent._build_source_anchor(metadata)
        anchor_lookup = {anchor: metadata}
        evidence_items = [
            {
                "evidence_id": "ev_001",
                "source_anchor": anchor,
                "claim": "Poshmark의 성공적인 체질 개선이 커머스 성장에 기여했다.",
                "quote_span": "Poshmark의 성공적인 체질 개선",
                "support_level": "direct",
                "question_relevance": "high",
                "allowed_terms": ["Poshmark", "커머스"],
                "metadata": metadata,
            }
        ]

        supplemented = agent._supplement_narrative_driver_evidence(
            evidence_items,
            docs,
            query="커머스 부문의 2023년 매출 성장률을 계산하고, 포시마크 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            anchor_lookup=anchor_lookup,
        )

        self.assertEqual(len(supplemented), 2)
        self.assertTrue(
            any("연결 편입" in str(item.get("claim") or "") for item in supplemented),
            supplemented,
        )

    def test_narrative_summary_supplements_missing_consolidation_effect_from_table_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        metadata = {
            "company": "NAVER",
            "year": 2023,
            "report_type": "사업보고서",
            "section_path": "IV. 이사의 경영진단 및 분석의견",
            "section": "경영진단",
            "block_type": "table",
            "chunk_id": "mda-table-001",
            "table_context": "Poshmark 연결 편입효과에 따른 영업수익 증가",
        }
        docs = [
            (
                Document(
                    page_content="수익성 표",
                    metadata=metadata,
                ),
                0.88,
            )
        ]
        anchor = agent._build_source_anchor(metadata)
        anchor_lookup = {anchor: metadata}
        evidence_items = [
            {
                "evidence_id": "ev_001",
                "source_anchor": anchor,
                "claim": "Poshmark의 성공적인 체질 개선이 커머스 성장에 기여했다.",
                "quote_span": "Poshmark의 성공적인 체질 개선",
                "support_level": "direct",
                "question_relevance": "high",
                "allowed_terms": ["Poshmark", "커머스"],
                "metadata": metadata,
            }
        ]

        supplemented = agent._supplement_narrative_driver_evidence(
            evidence_items,
            docs,
            query="커머스 부문의 2023년 매출 성장률을 계산하고, 포시마크 인수가 커머스 실적에 미친 영향을 요약해 줘.",
            anchor_lookup=anchor_lookup,
        )

        self.assertEqual(len(supplemented), 2)
        self.assertTrue(
            any("연결 편입" in str(item.get("claim") or "") for item in supplemented),
            supplemented,
        )

    def test_compressed_narrative_answer_preserves_supported_consolidation_effect(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        answer = "네이버 커머스 부문은 2023년에 전년 대비 41.4% 성장했습니다. 이러한 성장은 포시마크의 체질 개선에 기인합니다."
        selected_evidence = [
            {
                "claim": "Poshmark의 성공적인 체질 개선이 커머스 성장에 기여했다.",
                "quote_span": "Poshmark의 성공적인 체질 개선",
            },
            {
                "claim": "Poshmark 연결 편입효과에 따른 영업수익 증가",
                "quote_span": "Poshmark 연결 편입효과에 따른 영업수익 증가",
            },
        ]

        augmented = agent._augment_narrative_answer_with_supported_drivers(
            answer,
            selected_evidence,
            query="커머스 부문의 2023년 매출 성장률을 계산하고, 포시마크 인수가 커머스 실적에 미친 영향을 요약해 줘.",
        )

        self.assertIn("연결 편입 효과", augmented)

    def test_selected_narrative_claim_ids_expand_to_include_missing_driver_marker(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence_items = [
            {
                "evidence_id": "ev_001",
                "claim": "Poshmark의 성공적인 체질 개선이 커머스 성장에 기여했다.",
                "quote_span": "Poshmark의 성공적인 체질 개선",
                "question_relevance": "high",
                "support_level": "direct",
            },
            {
                "evidence_id": "ev_003",
                "claim": "Poshmark 연결 편입효과에 따른 영업수익 증가",
                "quote_span": "Poshmark 연결 편입효과에 따른 영업수익 증가",
                "question_relevance": "medium",
                "support_level": "partial",
            },
        ]

        expanded = agent._expand_selected_claim_ids_for_narrative_drivers(
            ["ev_001"],
            evidence_items,
            query="커머스 부문의 2023년 매출 성장률을 계산하고, 포시마크 인수가 커머스 실적에 미친 영향을 요약해 줘.",
        )

        self.assertEqual(expanded, ["ev_001", "ev_003"])

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
