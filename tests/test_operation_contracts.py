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
    _build_semantic_numeric_plan,
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
    _score_operand_candidate,
    _coerce_lookup_magnitude_value,
    _desired_consolidation_scope,
    _desired_statement_types,
    _extract_numeric_value_after_operand_text,
    _extract_generic_operand_labels,
    _label_implies_percent_metric,
    _normalise_operand_value,
    _operand_target_years,
    _operand_row_matches_requirement,
    _order_concept_specs_by_query,
    _parse_unstructured_table_row_cells,
    _resolve_candidate_local_unit_hint,
    _requires_direct_numeric_grounding,
    _retrieval_hint_from_topic,
    _resolve_runtime_calculation_trace,
    _structured_cell_period_text,
    _supplement_section_terms_for_query,
)
from src.agent.financial_graph_models import (
    CalculationPlan,
    CalculationRenderOutput,
    CalculationVerificationOutput,
    EvidenceExtraction,
    NumericExtraction,
)
from src.agent.financial_graph_planning import _build_hybrid_narrative_subtask, _refine_lookup_slot_unit_from_evidence
from src.config.ontology import FinancialOntologyManager
import src.config.ontology as ontology_module


def _with_runtime_calculation_trace(state):
    updated = dict(state)
    if not updated.get("resolved_calculation_trace"):
        updated["resolved_calculation_trace"] = {
            "calculation_operands": list(updated.get("calculation_operands") or []),
            "calculation_plan": dict(updated.get("calculation_plan") or {}),
            "calculation_result": dict(updated.get("calculation_result") or {}),
        }
    return updated


def _execute_calculation_with_runtime_trace(agent, state):
    return agent._execute_calculation(_with_runtime_calculation_trace(state))


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


class _CapturingStructuredLLM:
    def __init__(self, response):
        self._response = response
        self.prompt_text = ""

    def __call__(self, prompt_value):
        return self.invoke(prompt_value)

    def invoke(self, prompt_value):
        self.prompt_text = prompt_value.to_string() if hasattr(prompt_value, "to_string") else str(prompt_value)
        return self._response


class _CapturingLLM:
    def __init__(self, response):
        self.structured = _CapturingStructuredLLM(response)

    def with_structured_output(self, _schema):
        return self.structured


class _CountingStructuredLLM:
    def __init__(self, response):
        self._response = response
        self.invoke_count = 0

    def __call__(self, prompt_value):
        return self.invoke(prompt_value)

    def invoke(self, _prompt_value):
        self.invoke_count += 1
        return self._response


class _CountingLLM:
    def __init__(self, response):
        self.structured = _CountingStructuredLLM(response)

    def with_structured_output(self, _schema):
        return self.structured


class _FailingStructuredLLM:
    def __call__(self, _prompt_value):
        raise RuntimeError("structured output disabled for test")

    def invoke(self, _prompt_value):
        raise RuntimeError("structured output disabled for test")


class _FailingLLM:
    def with_structured_output(self, _schema):
        return _FailingStructuredLLM()


class OperationContractTests(unittest.TestCase):
    def test_narrative_compression_prefers_sufficient_preferred_section_evidence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "query": "Summarize the business performance from the annual report.",
            "topic": "business performance",
            "query_type": "qa",
            "intent": "qa",
            "format_preference": "paragraph",
            "active_subtask": {
                "operation_family": "narrative_summary",
                "preferred_sections": ["Preferred Section"],
            },
        }
        evidence_items = [
            {
                "evidence_id": "ev_001",
                "claim": "A weaker table-side claim.",
                "support_level": "direct",
                "question_relevance": "high",
                "metadata": {"section_path": "Other Section", "block_type": "table"},
            },
            {
                "evidence_id": "ev_002",
                "claim": "A preferred narrative claim.",
                "support_level": "direct",
                "question_relevance": "high",
                "metadata": {"section_path": "Preferred Section", "block_type": "paragraph"},
            },
            {
                "evidence_id": "ev_003",
                "claim": "Another preferred narrative claim.",
                "support_level": "direct",
                "question_relevance": "high",
                "metadata": {"section_path": "Preferred Section", "block_type": "paragraph"},
            },
        ]

        selected = agent._select_evidence_for_compression(evidence_items, "qa", state)

        self.assertEqual([item["evidence_id"] for item in selected], ["ev_002", "ev_003"])

    def test_narrative_compression_keeps_nonpreferred_when_preferred_evidence_is_sparse(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "query": "Summarize the business performance from the annual report.",
            "topic": "business performance",
            "query_type": "qa",
            "intent": "qa",
            "format_preference": "paragraph",
            "active_subtask": {
                "operation_family": "narrative_summary",
                "preferred_sections": ["Preferred Section"],
            },
        }
        evidence_items = [
            {
                "evidence_id": "ev_001",
                "claim": "A relevant non-preferred claim.",
                "support_level": "direct",
                "question_relevance": "high",
                "metadata": {"section_path": "Other Section", "block_type": "paragraph"},
            },
            {
                "evidence_id": "ev_002",
                "claim": "Only one preferred claim.",
                "support_level": "direct",
                "question_relevance": "high",
                "metadata": {"section_path": "Preferred Section", "block_type": "paragraph"},
            },
        ]

        selected = agent._select_evidence_for_compression(evidence_items, "qa", state)

        self.assertEqual([item["evidence_id"] for item in selected], ["ev_001", "ev_002"])

    def test_runtime_evidence_projection_uses_final_kept_claims_for_narrative_answers(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        final = {
            "answer": "The final answer uses two supported claims.",
            "evidence_items": [
                {"evidence_id": "ev_001", "claim": "Unused extracted claim."},
                {"evidence_id": "ev_002", "claim": "Used claim A."},
                {"evidence_id": "ev_003", "claim": "Used claim B."},
            ],
            "kept_claim_ids": ["ev_002", "ev_003"],
            "selected_claim_ids": ["ev_001", "ev_002", "ev_003"],
        }

        projected = agent._runtime_evidence_from_retrieved_docs(final)

        self.assertEqual([item["evidence_id"] for item in projected], ["ev_002", "ev_003"])

    def test_runtime_evidence_projection_keeps_existing_when_no_final_claim_filter_exists(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        final = {
            "answer": "The final answer uses extracted evidence.",
            "evidence_items": [
                {"evidence_id": "ev_001", "claim": "Claim A."},
                {"evidence_id": "ev_002", "claim": "Claim B."},
            ],
            "kept_claim_ids": [],
            "selected_claim_ids": [],
        }

        projected = agent._runtime_evidence_from_retrieved_docs(final)

        self.assertEqual([item["evidence_id"] for item in projected], ["ev_001", "ev_002"])

    def test_lookup_operand_rejects_unlabeled_aggregate_claim(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "label": "2024년 DX 매출액",
            "raw_value": "638,217",
            "raw_unit": "억원",
            "normalized_value": 63821700000000.0,
            "normalized_unit": "KRW",
        }
        evidence_item = {
            "claim": "638,217 (억원)",
            "quote_span": "638,217",
        }
        required_operands = [
            {
                "label": "2024년 DX 매출액",
                "role": "minuend",
                "concept": "revenue",
                "required": True,
            }
        ]

        self.assertFalse(
            agent._llm_lookup_operand_has_direct_support(row, evidence_item, required_operands)
        )

    def test_lookup_operand_rejects_inferred_sum_claim(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "label": "2024년 SDC 매출액",
            "raw_value": "434,327",
            "raw_unit": "억원",
            "normalized_value": 43432700000000.0,
            "normalized_unit": "KRW",
        }
        evidence_item = {
            "claim": "SDC: 291,578, Harman: 142,749 (억원)",
            "quote_span": "SDC: 291,578, Harman: 142,749",
        }
        required_operands = [
            {
                "label": "2024년 SDC 매출액",
                "role": "addend",
                "concept": "revenue",
                "required": True,
            }
        ]

        self.assertFalse(
            agent._llm_lookup_operand_has_direct_support(row, evidence_item, required_operands)
        )

    def test_lookup_operand_accepts_direct_labeled_claim(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "label": "2024년 SDC 매출액",
            "raw_value": "291,578",
            "raw_unit": "억원",
            "normalized_value": 29157800000000.0,
            "normalized_unit": "KRW",
        }
        evidence_item = {
            "claim": "SDC 매출액: 291,578억원, Harman 매출액: 142,749억원",
            "quote_span": "SDC 매출액: 291,578억원",
        }
        required_operands = [
            {
                "label": "2024년 SDC 매출액",
                "role": "addend",
                "concept": "revenue",
                "required": True,
            }
        ]

        self.assertTrue(
            agent._llm_lookup_operand_has_direct_support(row, evidence_item, required_operands)
        )

    def test_lookup_operand_rejects_label_from_broad_context_only(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "label": "2024년 target metric",
            "raw_value": "451,284",
            "raw_unit": "백만원",
            "normalized_value": 451284000000.0,
            "normalized_unit": "KRW",
        }
        evidence_item = {
            "claim": "other metric | item A 451,284 백만원 | other metric total 4,145,647 백만원",
            "quote_span": "other metric | item A 451,284 백만원",
            "source_context": "target metric | target metric total 10,121,033 백만원",
        }
        required_operands = [
            {
                "label": "2024년 target metric",
                "role": "addend",
                "concept": "target_metric",
                "required": True,
            }
        ]

        self.assertFalse(
            agent._llm_lookup_operand_has_direct_support(row, evidence_item, required_operands)
        )

    def test_required_operand_builder_does_not_steal_other_operand_row_from_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        required_operands = [
            {"label": "항목 A", "role": "addend_a", "concept": "metric_a", "required": True},
            {"label": "항목 B", "role": "addend_b", "concept": "metric_b", "required": True},
        ]
        rows = agent._build_required_operands_from_candidates(
            [
                {
                    "evidence_id": "ev_a",
                    "source_anchor": "[회사 | 2024 | 표]",
                    "claim": "항목 A 합계 111 백만원",
                    "source_context": "항목 B 합계 222 백만원",
                    "raw_row_text": "항목 A 합계 111 백만원",
                    "metadata": {"table_source_id": "table:1"},
                },
                {
                    "evidence_id": "ev_b",
                    "source_anchor": "[회사 | 2024 | 표]",
                    "claim": "항목 B 합계 222 백만원",
                    "source_context": "항목 A 합계 111 백만원",
                    "raw_row_text": "항목 B 합계 222 백만원",
                    "metadata": {"table_source_id": "table:1"},
                },
            ],
            required_operands=required_operands,
            query="2024년 항목 A와 항목 B를 합산해 줘.",
            report_scope={"year": 2024},
        )

        by_role = {row["matched_operand_role"]: row for row in rows}
        self.assertEqual(by_role["addend_a"]["raw_value"], "111")
        self.assertEqual(by_role["addend_b"]["raw_value"], "222")

    def test_ratio_operand_rejects_bound_label_without_source_surface_support(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        required_operands = [
            {
                "label": "target denominator",
                "role": "denominator_1",
                "concept": "target_denominator",
                "required": True,
            }
        ]
        evidence_by_id = {
            "ev_statement": {
                "evidence_id": "ev_statement",
                "claim": "source numerator 435,542",
                "quote_span": "source numerator 435,542",
                "metadata": {
                    "table_value_labels_text": "source numerator 435,542\nother metric 478,485",
                    "table_source_id": "table:statement",
                },
            }
        }
        mislabeled_row = {
            "operand_id": "op_002",
            "evidence_id": "ev_statement",
            "source_row_id": "ev_statement",
            "label": "target denominator",
            "matched_operand_label": "target denominator",
            "matched_operand_concept": "target_denominator",
            "matched_operand_role": "denominator_1",
            "raw_value": "478,485",
            "raw_unit": "백만원",
            "normalized_value": 478485000000.0,
            "normalized_unit": "KRW",
        }
        supported_row = {
            **mislabeled_row,
            "raw_value": "11,623",
            "normalized_value": 1162300000000.0,
        }
        evidence_by_id["ev_supported"] = {
            "evidence_id": "ev_supported",
            "claim": "target denominator 11,623",
            "quote_span": "target denominator 11,623",
            "metadata": {"table_source_id": "table:metric"},
        }
        supported_row["evidence_id"] = "ev_supported"
        supported_row["source_row_id"] = "ev_supported"

        self.assertFalse(
            agent._operand_row_satisfies_required_surface_contract(
                mislabeled_row,
                evidence_by_id,
                required_operands,
                require_direct_support=True,
            )
        )
        self.assertTrue(
            agent._operand_row_satisfies_required_surface_contract(
                supported_row,
                evidence_by_id,
                required_operands,
                require_direct_support=True,
            )
        )

    def test_ratio_surface_filter_checks_structured_table_value_surface(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        required_operands = [
            {
                "label": "target numerator",
                "role": "numerator_1",
                "concept": "target_numerator",
                "required": True,
            },
            {
                "label": "target denominator",
                "role": "denominator_1",
                "concept": "target_denominator",
                "required": True,
            },
        ]
        evidence_items = [
            {
                "evidence_id": "ev_table",
                "claim": "target numerator 4,355; target denominator 11,623; other metric 478,485",
                "metadata": {
                    "table_source_id": "table:metrics",
                    "table_object_json": json.dumps(
                        {
                            "rows": [
                                {
                                    "row_label": "target numerator",
                                    "row_headers": ["target numerator"],
                                    "cells": [{"value_text": "4,355", "unit_hint": "억원"}],
                                },
                                {
                                    "row_label": "target denominator",
                                    "row_headers": ["target denominator"],
                                    "cells": [{"value_text": "11,623", "unit_hint": "억원"}],
                                },
                                {
                                    "row_label": "other metric",
                                    "row_headers": ["other metric"],
                                    "cells": [{"value_text": "478,485", "unit_hint": "백만원"}],
                                },
                            ]
                        }
                    ),
                },
            }
        ]
        candidate_rows = [
            {
                "evidence_id": "ev_table",
                "label": "target numerator",
                "matched_operand_label": "target numerator",
                "matched_operand_role": "numerator_1",
                "matched_operand_concept": "target_numerator",
                "raw_value": "4,355",
                "raw_unit": "억원",
            },
            {
                "evidence_id": "ev_table",
                "label": "target denominator",
                "matched_operand_label": "target denominator",
                "matched_operand_role": "denominator_1",
                "matched_operand_concept": "target_denominator",
                "raw_value": "478,485",
                "raw_unit": "백만원",
            },
            {
                "evidence_id": "ev_table",
                "label": "target denominator",
                "matched_operand_label": "target denominator",
                "matched_operand_role": "denominator_1",
                "matched_operand_concept": "target_denominator",
                "raw_value": "11,623",
                "raw_unit": "억원",
            },
        ]

        filtered = agent._filter_operand_rows_by_required_surface_contract(
            candidate_rows,
            evidence_items,
            required_operands,
            require_direct_support=True,
        )

        values_by_role = {row["matched_operand_role"]: row["raw_value"] for row in filtered}
        self.assertEqual(values_by_role, {"numerator_1": "4,355", "denominator_1": "11,623"})

    def test_operating_margin_drag_numerator_requires_exact_surface_contract(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ontology = FinancialOntologyManager(Path("src/config/financial_ontology.json"))
        required_operands = [
            row
            for row in ontology.build_operand_spec("operating_margin_drag")
            if str(row.get("role") or "") == "numerator"
        ]
        self.assertEqual(len(required_operands), 1)
        self.assertTrue(
            (required_operands[0].get("binding_policy") or {}).get("require_surface_contract_for_direct_match")
        )

        evidence_items = [
            {
                "evidence_id": "ev_asset",
                "claim": "무형자산 3,952,108,690",
                "quote_span": "무형자산 3,952,108,690",
                "metadata": {
                    "table_source_id": "table:intangible_assets",
                    "table_value_labels_text": "무형자산 3,952,108,690",
                },
            },
            {
                "evidence_id": "ev_expense",
                "claim": "무형자산상각비 182,049,824",
                "quote_span": "무형자산상각비 182,049,824",
                "metadata": {
                    "table_source_id": "table:expense_by_nature",
                    "table_value_labels_text": "무형자산상각비 182,049,824",
                },
            },
        ]
        candidate_rows = [
            {
                "evidence_id": "ev_asset",
                "label": "무형자산상각비",
                "matched_operand_label": "무형자산상각비",
                "matched_operand_role": "numerator",
                "matched_operand_concept": "amortization_expense",
                "raw_value": "3,952,108,690",
                "raw_unit": "천원",
                "normalized_value": 3952108690000.0,
                "normalized_unit": "KRW",
            },
            {
                "evidence_id": "ev_expense",
                "label": "무형자산상각비",
                "matched_operand_label": "무형자산상각비",
                "matched_operand_role": "numerator",
                "matched_operand_concept": "amortization_expense",
                "raw_value": "182,049,824",
                "raw_unit": "천원",
                "normalized_value": 182049824000.0,
                "normalized_unit": "KRW",
            },
        ]

        filtered = agent._filter_operand_rows_by_required_surface_contract(
            candidate_rows,
            evidence_items,
            required_operands,
            require_direct_support=True,
        )

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["evidence_id"], "ev_expense")
        self.assertEqual(filtered[0]["raw_value"], "182,049,824")

    def test_ratio_coherent_context_rows_can_be_recovered_from_retrieved_docs(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        required_operands = [
            {
                "label": "판매비와관리비",
                "role": "numerator_1",
                "concept": "selling_general_administrative_expense",
                "required": True,
            },
            {
                "label": "경비차감전영업이익",
                "role": "denominator_1",
                "concept": "pre_expense_operating_profit",
                "required": True,
            },
        ]
        docs = [
            (
                Document(
                    page_content=(
                        "구분 | 2023년 | 2022년\n"
                        "경비차감전영업이익 | 11,623 | 9,199\n"
                        "판매비와관리비 | 4,355 | 3,935"
                    ),
                    metadata={
                        "company": "ExampleCo",
                        "year": 2023,
                        "section_path": "Management discussion",
                        "table_source_id": "table:coherent",
                        "unit_hint": "억원",
                        "table_header_context": "구분 | 2023년 | 2022년",
                        "table_value_labels_text": (
                            "경비차감전영업이익 11,623\n"
                            "경비차감전영업이익 9,199\n"
                            "판매비와관리비 4,355\n"
                            "판매비와관리비 3,935"
                        ),
                    },
                ),
                1.0,
            )
        ]

        evidence_items = agent._ratio_operand_context_evidence_from_docs(docs)
        rows = agent._build_complete_ratio_operands_from_coherent_context(
            evidence_items,
            required_operands=required_operands,
            query="Calculate 2023 selling expenses divided by pre-expense operating profit.",
            topic="ratio",
            report_scope={"years": [2023]},
        )

        values_by_role = {row["matched_operand_role"]: row["raw_value"] for row in rows}
        self.assertEqual(values_by_role, {"numerator_1": "4,355", "denominator_1": "11,623"})

    def test_late_runtime_ratio_answer_refreshes_component_display(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "active_subtask": {"metric_label": "CIR"},
            "resolved_calculation_trace": {
                "calculation_plan": {"operation": "ratio"},
                "calculation_operands": [],
                "calculation_result": {
                    "status": "ok",
                    "result_value": 37.4688,
                    "rendered_value": "37.47%",
                    "answer_slots": {
                        "metric_label": "CIR",
                        "operation_family": "ratio",
                        "primary_value": {"rendered_value": "37.47%"},
                        "components_by_group": {
                            "numerator": [
                                {
                                    "label": "판매비와관리비",
                                    "raw_value": "4,355",
                                    "raw_unit": "억원",
                                    "normalized_value": 435500000000,
                                    "normalized_unit": "KRW",
                                    "rendered_value": "4,355억원",
                                    "period": "2023년",
                                }
                            ],
                            "denominator": [
                                {
                                    "label": "경비차감전영업이익",
                                    "raw_value": "11,623",
                                    "raw_unit": "억원",
                                    "normalized_value": 1162300000000,
                                    "normalized_unit": "KRW",
                                    "rendered_value": "11,623억원",
                                    "period": "2023년",
                                }
                            ],
                        },
                    },
                },
            },
        }

        refreshed = agent._late_runtime_numeric_answer(
            state,
            "2023년 CIR은 37.47%입니다. 계산: 판매비와관리비 4,355.42억원 / 경비차감전영업이익 11,623억원.",
        )

        self.assertIn("4,355억원", refreshed)
        self.assertNotIn("4,355.42억원", refreshed)

    def test_operand_coercion_trusts_evidence_surface_unit_and_period(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "operand_id": "op_001",
            "evidence_id": "ev_prior",
            "source_anchor": "[Example | 2023 | Section]",
            "label": "2023년 판매 대수",
            "raw_value": "78.1",
            "raw_unit": "원",
            "normalized_value": 78.1,
            "normalized_unit": "KRW",
            "period": "2023년",
            "matched_operand_role": "current_period",
            "matched_operand_concept": "sales_volume",
            "matched_operand_label": "2023년 판매 대수",
        }
        evidence_item = {
            "evidence_id": "ev_prior",
            "claim": "2022년 판매 대수는 78.1만 대였다.",
            "quote_span": "2022년 판매 대수는 78.1만 대였다.",
        }

        coerced = agent._coerce_operand_row_from_evidence(row, evidence_item)

        self.assertEqual(coerced["period"], "2022")
        self.assertEqual(coerced["period_source"], "evidence_surface")
        self.assertEqual(coerced["normalized_unit"], "COUNT")
        self.assertEqual(coerced["normalized_value"], 781000.0)
        self.assertFalse(
            _operand_row_matches_requirement(
                coerced,
                {
                    "label": "2023년 판매 대수",
                    "role": "current_period",
                    "concept": "sales_volume",
                    "period_hint": "2023",
                    "required": True,
                },
            )
        )
        self.assertTrue(
            _operand_row_matches_requirement(
                {**coerced, "matched_operand_role": "prior_period"},
                {
                    "label": "2022년 판매 대수",
                    "role": "prior_period",
                    "concept": "sales_volume",
                    "period_hint": "2022",
                    "required": True,
                },
            )
        )

    def test_required_operand_builder_retries_after_evidence_period_conflict(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        required_operands = [
            {
                "label": "2023년 판매 대수",
                "role": "current_period",
                "concept": "sales_volume",
                "period_hint": "2023",
                "unit_family": "COUNT",
                "required": True,
            },
            {
                "label": "2022년 판매 대수",
                "role": "prior_period",
                "concept": "sales_volume",
                "period_hint": "2022",
                "unit_family": "COUNT",
                "required": True,
            },
        ]

        rows = agent._build_required_operands_from_candidates(
            [
                {
                    "evidence_id": "ev_prior",
                    "source_anchor": "[Example | 2023 | Section]",
                    "claim": "2022년 판매 대수는 78.1만 대였다.",
                },
                {
                    "evidence_id": "ev_current",
                    "source_anchor": "[Example | 2023 | Section]",
                    "claim": "2023년 판매 대수는 87.0만 대로, 전년 대비 11.5% 증가했다.",
                },
            ],
            required_operands=required_operands,
            query="2023년 판매 대수의 전년 대비 성장률을 계산해 줘.",
            report_scope={"year": 2023},
        )

        by_role = {row["matched_operand_role"]: row for row in rows}
        self.assertEqual(by_role["current_period"]["evidence_id"], "ev_current")
        self.assertEqual(by_role["current_period"]["raw_value"], "87.0")
        self.assertEqual(by_role["current_period"]["normalized_unit"], "COUNT")
        self.assertEqual(by_role["current_period"]["period"], "2023")
        self.assertEqual(by_role["prior_period"]["evidence_id"], "ev_prior")
        self.assertEqual(by_role["prior_period"]["raw_value"], "78.1")
        self.assertEqual(by_role["prior_period"]["normalized_unit"], "COUNT")
        self.assertEqual(by_role["prior_period"]["period"], "2022")

    def test_required_operand_builder_binds_two_period_values_in_one_sentence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        required_operands = [
            {
                "label": "2023년 판매 대수",
                "role": "current_period",
                "concept": "sales_volume",
                "period_hint": "2023",
                "unit_family": "COUNT",
                "required": True,
            },
            {
                "label": "2022년 판매 대수",
                "role": "prior_period",
                "concept": "sales_volume",
                "period_hint": "2022",
                "unit_family": "COUNT",
                "required": True,
            },
        ]

        rows = agent._build_required_operands_from_candidates(
            [
                {
                    "evidence_id": "ev_growth",
                    "source_anchor": "[Example | 2023 | Section]",
                    "claim": "2023년 판매 대수는 87.0만 대로, 2022년 78.1만 대 대비 11.5% 증가했다.",
                },
            ],
            required_operands=required_operands,
            query="2023년 판매 대수의 전년 대비 성장률을 계산해 줘.",
            report_scope={"year": 2023},
        )

        by_role = {row["matched_operand_role"]: row for row in rows}
        self.assertEqual(by_role["current_period"]["raw_value"], "87.0")
        self.assertEqual(by_role["current_period"]["period"], "2023")
        self.assertEqual(by_role["current_period"]["stated_change_raw_value"], "11.5")
        self.assertEqual(by_role["current_period"]["stated_change_raw_unit"], "%")
        self.assertEqual(by_role["prior_period"]["raw_value"], "78.1")
        self.assertEqual(by_role["prior_period"]["period"], "2022")

    def test_segment_row_parser_splits_labeled_value_cells(self) -> None:
        row_text = (
            "매출액 | 기업 전체 총계 / 영업부문 / DX 부문 174,887,683 백만원 | "
            "기업 전체 총계 / 영업부문 / DS 부문 111,065,950 백만원"
        )

        cells = _parse_unstructured_table_row_cells(row_text, {})

        self.assertEqual(cells[0]["value_text"], "174,887,683")
        self.assertEqual(cells[0]["unit_hint"], "백만원")
        self.assertIn("DX 부문", cells[0]["column_headers"][-1])
        self.assertEqual(cells[1]["value_text"], "111,065,950")
        self.assertEqual(cells[1]["unit_hint"], "백만원")
        self.assertIn("DS 부문", cells[1]["column_headers"][-1])

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

    def test_quantitative_impact_answer_uses_supported_cost_loss_relation(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._compose_supported_quantitative_impact_answer(
            query="2023년 주석에서 손상차손 규모를 찾고 이것이 영업비용에 미친 영향을 분석해 줘.",
            evidence_items=[
                {
                    "evidence_id": "ev_loss",
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
                    "evidence_id": "ev_cost",
                    "claim": "영업비용 100,000",
                    "metadata": {
                        "table_value_labels_text": "영업비용 100,000",
                        "unit_hint": "백만원",
                        "statement_type": "income_statement",
                        "consolidation_scope": "consolidated",
                        "period_focus": "current",
                    },
                },
                {
                    "evidence_id": "ev_relation",
                    "claim": "동 비용에는 손상차손 금액이 포함되어 있습니다.",
                },
            ],
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIn("영업비용에 포함되어 비용을 증가시키고", result["answer"])
        self.assertIn("매출총이익을 압박하는 요인", result["answer"])
        self.assertIn("영업비용 100,000백만원 대비 약 2.00%", result["answer"])

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

    def test_lookup_numeric_extractor_rejects_aggregate_result_for_component_operand(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            NumericExtraction(
                period_check="2024년",
                consolidation_check="연결",
                unit="백만원",
                raw_value="638,217",
                final_value="DX 부문과 DS 부문의 2024년 매출액 차이는 638,217백만원입니다.",
            )
        )
        result = agent._extract_numeric_fact(
            {
                "query": "DX 부문과 DS 부문의 2024년 매출액 차이를 계산해 줘.",
                "retrieved_docs": [
                    (
                        Document(
                            page_content="DX 부문과 DS 부문의 2024년 매출액 차이는 638,217 백만원입니다.",
                            metadata={"company": "삼성전자", "year": 2024},
                        ),
                        1.0,
                    )
                ],
                "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
                "active_subtask": {
                    "task_id": "task_1",
                    "operation_family": "lookup",
                    "metric_label": "DX 부문 매출액",
                    "required_operands": [
                        {
                            "label": "DX 부문 매출액",
                            "concept": "revenue",
                            "role": "minuend",
                            "required": True,
                        }
                    ],
                },
            }
        )
        self.assertEqual(result["evidence_status"], "missing")
        self.assertEqual(result["selected_claim_ids"], [])
        self.assertEqual(result["numeric_debug_trace"]["rejected_reason"], "missing_direct_lookup_operand_support")

    def test_numeric_extractor_reuses_duplicate_direct_support_rejection(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        counting_llm = _CountingLLM(
            NumericExtraction(
                period_check="2024년",
                consolidation_check="연결",
                unit="백만원",
                raw_value="638,217",
                final_value="DX 부문과 DS 부문의 2024년 매출액 차이는 638,217백만원입니다.",
            )
        )
        agent.llm = counting_llm
        base_state = {
            "query": "DX 부문과 DS 부문의 2024년 매출액 차이를 계산해 줘.",
            "retrieved_docs": [
                (
                    Document(
                        page_content="DX 부문과 DS 부문의 2024년 매출액 차이는 638,217 백만원입니다.",
                        metadata={"company": "삼성전자", "year": 2024, "chunk_uid": "chunk-1"},
                    ),
                    1.0,
                )
            ],
            "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
            "active_subtask": {
                "task_id": "task_1",
                "operation_family": "lookup",
                "metric_label": "DX 부문 매출액",
                "required_operands": [
                    {
                        "label": "DX 부문 매출액",
                        "concept": "revenue",
                        "role": "minuend",
                        "required": True,
                    }
                ],
            },
        }

        first = agent._extract_numeric_fact(base_state)
        second = agent._extract_numeric_fact(
            {
                **base_state,
                "numeric_debug_trace_history": first["numeric_debug_trace_history"],
            }
        )

        self.assertEqual(counting_llm.structured.invoke_count, 1)
        self.assertEqual(second["evidence_status"], "missing")
        self.assertEqual(second["numeric_debug_trace"]["rejected_reason"], "missing_direct_lookup_operand_support")
        self.assertEqual(
            second["numeric_debug_trace"]["skipped_reason"],
            "duplicate_missing_direct_lookup_operand_support",
        )
        self.assertEqual(len(second["numeric_debug_trace_history"]), 2)

    def test_numeric_extractor_reuses_duplicate_supported_result(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        counting_llm = _CountingLLM(
            NumericExtraction(
                period_check="2024년",
                consolidation_check="연결",
                unit="백만원",
                raw_value="174,887,683",
                final_value="DX 부문의 2024년 매출액은 174,887,683백만원입니다.",
            )
        )
        agent.llm = counting_llm
        base_state = {
            "query": "DX 부문과 DS 부문의 2024년 매출액 차이를 계산해 줘.",
            "retrieved_docs": [
                (
                    Document(
                        page_content=(
                            "매출액 | 기업 전체 총계 / 영업부문 / DX 부문 "
                            "174,887,683 백만원 | 기업 전체 총계 / 영업부문 / DS 부문 "
                            "111,065,950 백만원"
                        ),
                        metadata={"company": "삼성전자", "year": 2024, "chunk_uid": "chunk-1"},
                    ),
                    1.0,
                )
            ],
            "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
            "active_subtask": {
                "task_id": "task_1",
                "operation_family": "lookup",
                "metric_label": "DX 부문 매출액",
                "required_operands": [
                    {
                        "label": "DX 부문 매출액",
                        "concept": "revenue",
                        "role": "minuend",
                        "required": True,
                    }
                ],
            },
        }

        first = agent._extract_numeric_fact(base_state)
        second = agent._extract_numeric_fact(
            {
                **base_state,
                "numeric_debug_trace_history": first["numeric_debug_trace_history"],
            }
        )

        self.assertEqual(counting_llm.structured.invoke_count, 1)
        self.assertEqual(second["evidence_status"], "sufficient")
        self.assertEqual(second["selected_claim_ids"], ["ev_001"])
        self.assertEqual(
            second["numeric_debug_trace"]["skipped_reason"],
            "duplicate_numeric_extraction_result",
        )
        self.assertEqual(len(second["numeric_debug_trace_history"]), 2)

    def test_numeric_extractor_records_prompt_size_diagnostics(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        capturing_llm = _CapturingLLM(
            NumericExtraction(
                period_check="2023",
                consolidation_check="consolidated",
                unit="units",
                raw_value="100",
                final_value="The 2023 target metric is 100 units.",
            )
        )
        agent.llm = capturing_llm
        docs = [
            (
                Document(
                    page_content=f"target metric row {index} | 100 units",
                    metadata={
                        "company": "ExampleCo",
                        "year": 2023,
                        "section_path": f"section {index}",
                        "chunk_uid": f"chunk_{index}",
                        **({"table_context": "header context"} if index == 0 else {}),
                    },
                ),
                1.0,
            )
            for index in range(10)
        ]
        docs[9][0].page_content = "excluded prompt tail " * 200

        result = agent._extract_numeric_fact(
            {
                "query": "Find the 2023 target metric.",
                "retrieved_docs": docs,
            }
        )

        diagnostics = result["numeric_debug_trace"]["numeric_extraction_prompt"]
        self.assertEqual(diagnostics["selected_doc_count"], 8)
        self.assertEqual(len(diagnostics["doc_summaries"]), 8)
        self.assertEqual(diagnostics["table_context_doc_count"], 1)
        self.assertGreater(diagnostics["context_chars"], 0)
        self.assertEqual(diagnostics["query_chars"], len("Find the 2023 target metric."))
        self.assertEqual(len(result["numeric_debug_trace_history"]), 1)
        self.assertEqual(
            result["numeric_debug_trace_history"][0]["numeric_extraction_prompt"]["selected_doc_count"],
            8,
        )
        self.assertNotIn("excluded prompt tail", capturing_llm.structured.prompt_text)
        self.assertEqual(result["evidence_status"], "sufficient")

    def test_lookup_numeric_extractor_accepts_direct_component_row(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            NumericExtraction(
                period_check="2024년",
                consolidation_check="연결",
                unit="백만원",
                raw_value="174,887,683",
                final_value="DX 부문의 2024년 매출액은 174,887,683백만원입니다.",
            )
        )
        result = agent._extract_numeric_fact(
            {
                "query": "DX 부문과 DS 부문의 2024년 매출액 차이를 계산해 줘.",
                "retrieved_docs": [
                    (
                        Document(
                            page_content="매출액 | 기업 전체 총계 / 영업부문 / DX 부문 174,887,683 백만원 | 기업 전체 총계 / 영업부문 / DS 부문 111,065,950 백만원",
                            metadata={"company": "삼성전자", "year": 2024},
                        ),
                        1.0,
                    )
                ],
                "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
                "active_subtask": {
                    "task_id": "task_1",
                    "operation_family": "lookup",
                    "metric_label": "DX 부문 매출액",
                    "required_operands": [
                        {
                            "label": "DX 부문 매출액",
                            "concept": "revenue",
                            "role": "minuend",
                            "required": True,
                        }
                    ],
                },
            }
        )
        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertEqual(result["selected_claim_ids"], ["ev_001"])

    def test_lookup_numeric_extractor_accepts_direct_structured_value_record(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            NumericExtraction(
                period_check="2023",
                consolidation_check="company",
                unit="units",
                raw_value="100",
                final_value="The 2023 total base is 100 units.",
            )
        )
        metadata = {
            "company": "ExampleCo",
            "year": 2023,
            "table_value_records_json": json.dumps(
                [
                    {
                        "semantic_label": "total base",
                        "row_label": "total base",
                        "row_headers": ["total base"],
                        "column_headers": ["2023"],
                        "period_text": "2023",
                        "value_text": "100",
                        "unit_hint": "units",
                    }
                ]
            ),
        }
        result = agent._extract_numeric_fact(
            {
                "query": "Find total base for 2023.",
                "retrieved_docs": [
                    (
                        Document(
                            page_content="Structured table chunk",
                            metadata=metadata,
                        ),
                        1.0,
                    )
                ],
                "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
                "active_subtask": {
                    "task_id": "task_1",
                    "operation_family": "lookup",
                    "metric_label": "2023 total base",
                    "required_operands": [
                        {
                            "label": "2023 total base",
                            "role": "denominator",
                            "required": True,
                        }
                    ],
                },
            }
        )
        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertEqual(result["selected_claim_ids"], ["ev_001"])

    def test_lookup_numeric_extractor_accepts_direct_table_object_row(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            NumericExtraction(
                period_check="2023",
                consolidation_check="company",
                unit="units",
                raw_value="100",
                final_value="The 2023 total base is 100 units.",
            )
        )
        metadata = {
            "company": "ExampleCo",
            "year": 2023,
            "table_object_json": json.dumps(
                {
                    "rows": [
                        {
                            "row_label": "total base",
                            "row_headers": ["total base"],
                            "cells": [
                                {
                                    "column_headers": ["2023"],
                                    "value_text": "100",
                                    "unit_hint": "units",
                                }
                            ],
                        },
                        {
                            "row_label": "other metric",
                            "row_headers": ["other metric"],
                            "cells": [
                                {
                                    "column_headers": ["2023"],
                                    "value_text": "200",
                                    "unit_hint": "units",
                                }
                            ],
                        },
                    ]
                }
            ),
        }
        result = agent._extract_numeric_fact(
            {
                "query": "Find total base for 2023.",
                "retrieved_docs": [
                    (
                        Document(
                            page_content="Structured table chunk",
                            metadata=metadata,
                        ),
                        1.0,
                    )
                ],
                "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
                "active_subtask": {
                    "task_id": "task_1",
                    "operation_family": "lookup",
                    "metric_label": "2023 total base",
                    "required_operands": [
                        {
                            "label": "2023 total base",
                            "role": "denominator",
                            "required": True,
                        }
                    ],
                },
            }
        )
        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertEqual(result["selected_claim_ids"], ["ev_001"])

    def test_lookup_numeric_extractor_accepts_existing_evidence_support(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            NumericExtraction(
                period_check="2023",
                consolidation_check="company",
                unit="units",
                raw_value="100",
                final_value="The 2023 total base is 100 units.",
            )
        )
        result = agent._extract_numeric_fact(
            {
                "query": "Find total base for 2023.",
                "retrieved_docs": [
                    (
                        Document(
                            page_content="Visible prompt context does not include the needed value.",
                            metadata={"company": "ExampleCo", "year": 2023},
                        ),
                        1.0,
                    )
                ],
                "evidence_items": [
                    {
                        "evidence_id": "ev_existing",
                        "claim": "total base | 100 units",
                        "quote_span": "total base | 100 units",
                        "metadata": {"company": "ExampleCo", "year": 2023},
                    }
                ],
                "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
                "active_subtask": {
                    "task_id": "task_1",
                    "operation_family": "lookup",
                    "metric_label": "2023 total base",
                    "required_operands": [
                        {
                            "label": "2023 total base",
                            "role": "denominator",
                            "required": True,
                        }
                    ],
                },
            }
        )
        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertNotEqual(result["numeric_debug_trace"].get("rejected_reason"), "missing_direct_lookup_operand_support")

    def test_lookup_numeric_extractor_checks_prompt_parent_context_support(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            NumericExtraction(
                period_check="2023",
                consolidation_check="company",
                unit="units",
                raw_value="100",
                final_value="The 2023 total base is 100 units.",
            )
        )
        agent.vsm = SimpleNamespace(get_parent=lambda _parent_id: "total base | 100 units\nother metric | 200 units")

        result = agent._extract_numeric_fact(
            {
                "query": "Find total base for 2023.",
                "retrieved_docs": [
                    (
                        Document(
                            page_content="Child chunk without the value.",
                            metadata={
                                "company": "ExampleCo",
                                "year": 2023,
                                "parent_id": "parent_1",
                            },
                        ),
                        1.0,
                    )
                ],
                "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
                "active_subtask": {
                    "task_id": "task_1",
                    "operation_family": "lookup",
                    "metric_label": "2023 total base",
                    "required_operands": [
                        {
                            "label": "2023 total base",
                            "role": "denominator",
                            "required": True,
                        }
                    ],
                },
            }
        )

        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertNotEqual(result["numeric_debug_trace"].get("rejected_reason"), "missing_direct_lookup_operand_support")

    def test_lookup_numeric_extractor_uses_metric_label_as_support_surface(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            NumericExtraction(
                period_check="2023",
                consolidation_check="company",
                unit="units",
                raw_value="100",
                final_value="The 2023 total base is 100 units.",
            )
        )
        result = agent._extract_numeric_fact(
            {
                "query": "Find total base for 2023.",
                "retrieved_docs": [
                    (
                        Document(
                            page_content="total base | 100 units",
                            metadata={"company": "ExampleCo", "year": 2023},
                        ),
                        1.0,
                    )
                ],
                "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
                "active_subtask": {
                    "task_id": "task_1",
                    "operation_family": "lookup",
                    "metric_label": "total base",
                    "required_operands": [
                        {
                            "label": "reported consolidated total base",
                            "role": "denominator",
                            "required": True,
                        }
                    ],
                },
            }
        )
        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertNotEqual(result["numeric_debug_trace"].get("rejected_reason"), "missing_direct_lookup_operand_support")

    def test_lookup_numeric_extractor_does_not_reject_embedded_operation_token_label(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            NumericExtraction(
                period_check="2023 경비차감전대상값",
                consolidation_check="company",
                unit="units",
                raw_value="100",
                final_value="The 2023 경비차감전대상값 is 100 units.",
            )
        )

        result = agent._extract_numeric_fact(
            {
                "query": "Find the target value for 2023.",
                "retrieved_docs": [
                    (
                        Document(
                            page_content="경비차감전대상값 | 100 units\nother metric | 200 units",
                            metadata={"company": "ExampleCo", "year": 2023},
                        ),
                        1.0,
                    )
                ],
                "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
                "active_subtask": {
                    "task_id": "task_1",
                    "operation_family": "lookup",
                    "metric_label": "경비차감전대상값",
                    "required_operands": [
                        {
                            "label": "경비차감전대상값",
                            "role": "denominator",
                            "required": True,
                        }
                    ],
                },
            }
        )

        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertNotEqual(result["numeric_debug_trace"].get("rejected_reason"), "missing_direct_lookup_operand_support")

    def test_lookup_numeric_extractor_accepts_result_surface_grounded_in_source_line(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            NumericExtraction(
                period_check="2023",
                consolidation_check="company",
                unit="units",
                raw_value="100",
                final_value="The source targetdenominator is 100 units.",
            )
        )
        result = agent._extract_numeric_fact(
            {
                "query": "Find the denominator for 2023.",
                "retrieved_docs": [
                    (
                        Document(
                            page_content="targetdenominator (A=B+C) | 100 | 80\nothermetric | 200 | 150",
                            metadata={"company": "ExampleCo", "year": 2023},
                        ),
                        1.0,
                    )
                ],
                "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
                "active_subtask": {
                    "task_id": "task_1",
                    "operation_family": "lookup",
                    "metric_label": "ratio base",
                    "required_operands": [
                        {
                            "label": "reported consolidated base",
                            "role": "denominator",
                            "required": True,
                        }
                    ],
                },
            }
        )
        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertNotEqual(result["numeric_debug_trace"].get("rejected_reason"), "missing_direct_lookup_operand_support")

    def test_lookup_numeric_extractor_accepts_formula_labeled_source_row(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            NumericExtraction(
                period_check="2023",
                consolidation_check="company",
                unit="units",
                raw_value="100",
                final_value="The 2023 total base is 100 units.",
            )
        )
        result = agent._extract_numeric_fact(
            {
                "query": "Find total base for 2023.",
                "retrieved_docs": [
                    (
                        Document(
                            page_content="total base (A=B+C) | 100 | 80",
                            metadata={"company": "ExampleCo", "year": 2023},
                        ),
                        1.0,
                    )
                ],
                "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
                "active_subtask": {
                    "task_id": "task_1",
                    "operation_family": "lookup",
                    "metric_label": "total base",
                    "required_operands": [
                        {
                            "label": "total base",
                            "role": "denominator",
                            "required": True,
                        }
                    ],
                },
            }
        )
        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertEqual(result["selected_claim_ids"], ["ev_001"])

    def test_lookup_numeric_extractor_accepts_period_scope_qualified_direct_row(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            NumericExtraction(
                period_check="2022",
                consolidation_check="consolidated",
                unit="units",
                raw_value="(100)",
                final_value="The prior-period total base is (100) units.",
            )
        )
        result = agent._extract_numeric_fact(
            {
                "query": "Find the prior-period total base.",
                "retrieved_docs": [
                    (
                        Document(
                            page_content="total base | (120) | (100) | (80)",
                            metadata={"company": "ExampleCo", "year": 2023},
                        ),
                        1.0,
                    )
                ],
                "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
                "active_subtask": {
                    "task_id": "task_1",
                    "operation_family": "lookup",
                    "metric_label": "2023년 연결기준 2022년 total base",
                    "required_operands": [
                        {
                            "label": "2023년 연결기준 2022년 total base",
                            "role": "denominator",
                            "required": True,
                        }
                    ],
                },
            }
        )
        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertEqual(result["selected_claim_ids"], ["ev_001"])

    def test_lookup_numeric_extractor_accepts_direct_seed_row_when_visible_docs_lack_support(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            NumericExtraction(
                period_check="2022",
                consolidation_check="consolidated",
                unit="units",
                raw_value="(100)",
                final_value="The prior-period total base is (100) units.",
            )
        )
        result = agent._extract_numeric_fact(
            {
                "query": "Find the prior-period total base.",
                "retrieved_docs": [
                    (
                        Document(
                            page_content="Narrative context without the requested operand row.",
                            metadata={"company": "ExampleCo", "year": 2023, "chunk_uid": "visible_001"},
                        ),
                        1.0,
                    )
                ],
                "seed_retrieved_docs": [
                    (
                        Document(
                            page_content="total base | (120) | (100) | (80)",
                            metadata={"company": "ExampleCo", "year": 2023, "chunk_uid": "seed_001"},
                        ),
                        0.9,
                    )
                ],
                "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
                "active_subtask": {
                    "task_id": "task_1",
                    "operation_family": "lookup",
                    "metric_label": "2023년 연결기준 2022년 total base",
                    "required_operands": [
                        {
                            "label": "2023년 연결기준 2022년 total base",
                            "role": "denominator",
                            "required": True,
                        }
                    ],
                },
            }
        )
        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertEqual(result["selected_claim_ids"], ["ev_001"])

    def test_lookup_numeric_extractor_rejects_substring_numeric_match(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            NumericExtraction(
                period_check="2024년",
                consolidation_check="연결",
                unit="백만원",
                raw_value="291,578",
                final_value="SDC 부문의 2024년 매출액은 291,578백만원입니다.",
            )
        )
        result = agent._extract_numeric_fact(
            {
                "query": "SDC와 Harman 부문의 2024년 매출 합계를 계산해 줘.",
                "retrieved_docs": [
                    (
                        Document(
                            page_content="매출액 | 기업 전체 총계 / 영업부문 / SDC 29,157,820 백만원 | 기업 전체 총계 / 영업부문 / Harman 14,274,930 백만원",
                            metadata={"company": "삼성전자", "year": 2024},
                        ),
                        1.0,
                    )
                ],
                "calc_subtasks": [{"task_id": "task_1", "operation_family": "lookup"}],
                "active_subtask": {
                    "task_id": "task_1",
                    "operation_family": "lookup",
                    "metric_label": "SDC 매출액",
                    "required_operands": [
                        {
                            "label": "SDC 매출액",
                            "concept": "revenue",
                            "role": "addend_1",
                            "required": True,
                        }
                    ],
                },
            }
        )
        self.assertEqual(result["evidence_status"], "missing")
        self.assertEqual(result["numeric_debug_trace"]["rejected_reason"], "missing_direct_lookup_operand_support")

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

    def test_dependency_operand_rows_apply_lookup_magnitude_contract(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "active_subtask": {
                "task_id": "task_1",
                "operation_family": "difference",
                "inputs": [
                    {
                        "label": "\uc678\ud654\ud658\uc0b0\uc774\uc775",
                        "concept": "foreign_currency_translation_gain",
                        "role": "minuend",
                        "source_preference": ["task_output"],
                        "preferred_task_id": "task_gain",
                        "source_slot": "primary_value",
                    }
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_gain",
                    "metric_label": "\uc678\ud654\ud658\uc0b0\uc774\uc775",
                    "calculation_result": {
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "\uc678\ud654\ud658\uc0b0\uc774\uc775",
                                "concept": "foreign_currency_translation_gain",
                                "raw_value": "(573,884)",
                                "raw_unit": "\ubc31\ub9cc\uc6d0",
                                "normalized_value": -573_884_000_000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "(573,884)\ubc31\ub9cc\uc6d0",
                                "source_row_ids": ["gain_cell"],
                            }
                        }
                    },
                    "runtime_evidence": [
                        {
                            "evidence_id": "recon::gain_cell",
                            "quote_span": "\uc678\ud654\ud658\uc0b0\uc774\uc775 (573,884)",
                            "metadata": {
                                "statement_type": "notes",
                                "row_label": "\uc678\ud654\ud658\uc0b0\uc774\uc775",
                                "semantic_label": "\uc678\ud654\ud658\uc0b0\uc774\uc775",
                            },
                        }
                    ],
                }
            ],
        }

        rows = agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["normalized_value"], 573_884_000_000.0)
        self.assertEqual(rows[0]["raw_value"], "(573,884)")
        self.assertEqual(rows[0]["rendered_value"], "573,884\ubc31\ub9cc\uc6d0")
        self.assertEqual(rows[0]["value_coercion"], "lookup_magnitude_from_source_surface")

    def test_difference_source_display_unit_preserves_common_source_unit(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        unit = agent._adjusted_difference_source_display_unit(
            active_subtask={"operation_family": "difference", "metric_label": "net effect"},
            ordered_operands=[
                {"raw_unit": "\ubc31\ub9cc\uc6d0", "normalized_unit": "KRW", "dependency_resolved": True},
                {"raw_unit": "\ubc31\ub9cc\uc6d0", "normalized_unit": "KRW", "dependency_resolved": True},
            ],
        )

        self.assertEqual(unit, "\ubc31\ub9cc\uc6d0")

    def test_aggregate_fallback_prefers_complete_numeric_result(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        answer = agent._preferred_aggregate_fallback_answer(
            [
                {
                    "status": "ok",
                    "operation_family": "lookup",
                    "answer": "(573,884)\ubc31\ub9cc\uc6d0",
                    "calculation_result": {
                        "status": "ok",
                        "source_row_ids": ["lookup_cell"],
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "rendered_value": "573,884\ubc31\ub9cc\uc6d0",
                                "normalized_value": 573_884_000_000.0,
                                "source_row_ids": ["lookup_cell"],
                            },
                        },
                    },
                },
                {
                    "status": "ok",
                    "operation_family": "difference",
                    "calculation_result": {
                        "status": "ok",
                        "formatted_result": "\uc21c\ud6a8\uacfc\ub294 -332,236\ubc31\ub9cc\uc6d0\uc785\ub2c8\ub2e4.",
                        "source_row_ids": ["task_output:task_gain", "task_output:task_loss", "gain_cell", "loss_cell"],
                        "answer_slots": {
                            "operation_family": "difference",
                            "primary_value": {
                                "status": "ok",
                                "rendered_value": "-332,236\ubc31\ub9cc\uc6d0",
                                "normalized_value": -332_236_000_000.0,
                                "source_row_ids": ["gain_cell", "loss_cell"],
                            },
                            "current_value": {
                                "status": "ok",
                                "rendered_value": "573,884\ubc31\ub9cc\uc6d0",
                                "normalized_value": 573_884_000_000.0,
                                "source_row_ids": ["gain_cell"],
                            },
                            "prior_value": {
                                "status": "ok",
                                "rendered_value": "906,120\ubc31\ub9cc\uc6d0",
                                "normalized_value": 906_120_000_000.0,
                                "source_row_ids": ["loss_cell"],
                            },
                        },
                    },
                },
            ],
            "(573,884)\ubc31\ub9cc\uc6d0 \uc21c\ud6a8\uacfc\ub294 -332,236\ubc31\ub9cc\uc6d0\uc785\ub2c8\ub2e4.",
        )

        self.assertEqual(answer, "\uc21c\ud6a8\uacfc\ub294 -332,236\ubc31\ub9cc\uc6d0\uc785\ub2c8\ub2e4.")

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

    def test_count_candidate_prefers_location_sentence_with_entity_subject(self) -> None:
        operand = {
            "label": "지역 시장 판매대수",
            "role": "current_period",
            "unit_family": "COUNT",
            "period_hint": "2023",
        }
        market_total = {
            "candidate_kind": "chunk",
            "text": "2023년 지역시장에서는 전년 대비 12.3% 증가한 1,560.8만 대가 판매되었습니다.",
            "metadata": {"year": 2023, "section_path": "business section"},
        }
        entity_sales = {
            "candidate_kind": "chunk",
            "text": "2023년 지역시장에서 대상회사는 전년 대비 11.5% 증가한 87.0만 대를 판매했습니다.",
            "metadata": {"year": 2023, "section_path": "business section"},
        }

        market_score = _score_operand_candidate(
            market_total,
            operand=operand,
            preferred_statement_types=[],
            constraints={"entity_scope": "company"},
            query_years=[2023, 2022],
            report_scope={},
        )
        entity_score = _score_operand_candidate(
            entity_sales,
            operand=operand,
            preferred_statement_types=[],
            constraints={"entity_scope": "company"},
            query_years=[2023, 2022],
            report_scope={},
        )

        self.assertGreater(entity_score, market_score)

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
        self.assertIn("\uc870\uc815\ud56d\ubaa9\uc5d0 \uc758\ud55c \ud569\uacc4", candidate["metadata"]["row_text"])
        self.assertIn("\uacf5\uc2dc\uae08\uc561 2,526,280 \ucc9c\uc6d0", candidate["metadata"]["row_text"])
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

    def test_table_value_candidates_preserve_row_text_for_evidence_projection(self) -> None:
        metadata = {
            "unit_hint": "\ubc31\ub9cc\uc6d0",
            "statement_type": "notes",
            "consolidation_scope": "consolidated",
            "table_value_records_json": json.dumps(
                [
                    {
                        "row_index": 3,
                        "row_label": "Motional AD LLC (*1,11)",
                        "semantic_label": "\uacf5\ub3d9\uae30\uc5c5\uc5d0 \ub300\ud55c \uc18c\uc720\uc9c0\ubd84\uc728",
                        "row_headers": ["Motional AD LLC (*1,11)", "\ubbf8\uad6d"],
                        "column_headers": ["\ub2f9\uae30"],
                        "period_text": "2023",
                        "value_text": "25.81",
                        "unit_hint": "%",
                    },
                    {
                        "row_index": 3,
                        "row_label": "Motional AD LLC (*1,11)",
                        "semantic_label": "\uacf5\ub3d9\uae30\uc5c5\uc5d0 \ub300\ud55c \ud22c\uc790\uc790\uc0b0",
                        "row_headers": ["Motional AD LLC (*1,11)", "\ubbf8\uad6d"],
                        "column_headers": ["\ub2f9\uae30"],
                        "period_text": "2023",
                        "value_text": "1,294,367",
                        "unit_hint": "\ubc31\ub9cc\uc6d0",
                    },
                ],
                ensure_ascii=False,
            ),
        }

        candidates = _build_table_row_reconciliation_candidates(
            candidate_id_prefix="report:chunk",
            anchor="[현대자동차 | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
            table_text="",
            metadata=metadata,
        )

        candidate = next(
            item
            for item in candidates
            if item["candidate_kind"] == "structured_value"
            and item["metadata"]["semantic_label"] == "\uacf5\ub3d9\uae30\uc5c5\uc5d0 \ub300\ud55c \uc18c\uc720\uc9c0\ubd84\uc728"
        )
        row_text = candidate["metadata"]["row_text"]
        self.assertIn("Motional AD LLC (*1,11)", row_text)
        self.assertIn("\ubbf8\uad6d", row_text)
        self.assertIn("2023 25.81 %", row_text)
        self.assertIn("2023 1,294,367 \ubc31\ub9cc\uc6d0", row_text)

    def test_reconciliation_evidence_uses_structured_value_row_text(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        metadata = {
            "company": "ExampleCo",
            "year": 2023,
            "report_type": "annual",
            "chunk_uid": "chunk_1",
            "section_path": "Notes > Investments",
            "table_value_records_json": json.dumps(
                [
                    {
                        "row_index": 7,
                        "row_label": "Entity Alpha LLC",
                        "semantic_label": "Ownership ratio",
                        "row_headers": ["Entity Alpha LLC", "United States"],
                        "column_headers": ["Current"],
                        "period_text": "2023",
                        "value_text": "25.81",
                        "unit_hint": "%",
                    },
                    {
                        "row_index": 7,
                        "row_label": "Entity Alpha LLC",
                        "semantic_label": "Carrying amount",
                        "row_headers": ["Entity Alpha LLC", "United States"],
                        "column_headers": ["Current"],
                        "period_text": "2023",
                        "value_text": "1,294,367",
                        "unit_hint": "million KRW",
                    },
                ],
                ensure_ascii=False,
            ),
        }
        state = {
            "active_subtask": {
                "task_id": "task_1",
                "operation_family": "lookup",
                "required_operands": [
                    {
                        "label": "Ownership ratio",
                        "role": "ownership_ratio",
                        "unit_family": "PERCENT",
                        "required": True,
                    }
                ],
            },
            "retrieved_docs": [(Document(page_content="", metadata=metadata), 0.1)],
            "seed_retrieved_docs": [],
            "reconciliation_result": {
                "status": "ready",
                "matched_operands": [
                    {
                        "label": "Ownership ratio",
                        "role": "ownership_ratio",
                        "matched": True,
                        "candidate_ids": ["chunk_1::value:0"],
                    }
                ],
            },
        }

        evidence = agent._evidence_items_from_reconciliation_matches(state)

        self.assertEqual(len(evidence), 1)
        self.assertIn("Entity Alpha LLC", evidence[0]["quote_span"])
        self.assertIn("United States", evidence[0]["quote_span"])
        self.assertIn("2023 25.81 %", evidence[0]["quote_span"])
        self.assertIn("2023 1,294,367 million KRW", evidence[0]["quote_span"])
        self.assertEqual(evidence[0]["raw_row_text"], evidence[0]["quote_span"])

    def test_reconciliation_evidence_refs_include_source_row_provenance(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = {
            "status": "ready",
            "matched_operands": [
                {
                    "label": "Lookup value",
                    "matched": True,
                    "candidate_ids": [],
                    "source_row_ids": ["row:alpha"],
                },
                {
                    "label": "Related value",
                    "matched": True,
                    "source_row_id": "row:beta",
                    "evidence_ids": ["ev:beta"],
                },
            ],
        }

        refs = agent._reconciliation_evidence_refs(result)

        self.assertEqual(refs, ["row:alpha", "row:beta", "ev:beta"])

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

    def test_ampc_adjusted_operating_income_uses_ontology_difference_task(self) -> None:
        original_singleton = ontology_module._ONTOLOGY_SINGLETON
        try:
            ontology_module._ONTOLOGY_SINGLETON = FinancialOntologyManager(
                Path("src/config/financial_ontology_concepts_v3.draft.json")
            )
            plan = _build_semantic_numeric_plan(
                query=(
                    "2023년 연결기준 영업이익을 확인하고, 미국 인플레이션 감축법(IRA)에 따른 "
                    "세액공제(AMPC) 금액을 제외했을 때의 '실질 영업이익'을 계산해 줘."
                ),
                topic="",
                intent="comparison",
                report_scope={"company": "LG에너지솔루션", "year": 2023},
                target_metric_family="",
            )
        finally:
            ontology_module._ONTOLOGY_SINGLETON = original_singleton

        self.assertEqual(plan["status"], "concept_fallback")
        task = plan["tasks"][0]
        self.assertEqual(task["operation_family"], "difference")
        operands = task["required_operands"]
        self.assertEqual(
            [(operand["concept"], operand["role"]) for operand in operands],
            [
                ("operating_income", "minuend"),
                ("advanced_manufacturing_production_credit", "subtrahend"),
            ],
        )
        self.assertTrue(
            any("IRA Tax Credit" in query or "AMPC" in query for query in task["retrieval_queries"])
        )

    def test_ampc_concept_rejects_generic_income_tax_credit_adjustment_row(self) -> None:
        ontology = FinancialOntologyManager(Path("src/config/financial_ontology_concepts_v3.draft.json"))
        operand = ontology.concept_specs(
            "미국 인플레이션 감축법(IRA)에 따른 세액공제(AMPC) 금액",
            intent="comparison",
        )[0]
        operand = {**operand, "role": "subtrahend", "period_hint": "2023"}
        candidate = {
            "candidate_kind": "structured_value",
            "text": "세액공제 | (4,556)",
            "metadata": {
                "semantic_label": "세액공제",
                "row_label": "세액공제",
                "row_headers": ["조정사항(개요)", "세액공제"],
                "semantic_aliases": ["세액공제", "조정사항(개요)", "공시금액"],
                "statement_type": "notes",
                "value_role": "detail",
                "aggregation_stage": "direct",
                "period_focus": "current",
                "year": 2023,
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "table_context": "법인세비용 조정사항",
                "structured_cells": [
                    {
                        "value_text": "(4,556)",
                        "unit_hint": "백만원",
                        "column_headers": ["공시금액"],
                        "period_labels": ["2023"],
                    }
                ],
            },
        }
        paragraph_candidate = {
            "candidate_kind": "chunk",
            "text": (
                "영업이익은 원가개선 노력과 약 6,769억원의 IRA Tax Credit의 수익 인식으로 "
                "전년 대비 개선된 약 2조 1,632억원을 기록했습니다."
            ),
            "metadata": {
                "block_type": "paragraph",
                "section_path": "IV. 이사의 경영진단 및 분석의견 > 2. 개요",
            },
        }

        self.assertFalse(_candidate_matches_operand(candidate, operand))
        self.assertFalse(
            _candidate_satisfies_direct_acceptance_contract(
                candidate,
                operand=operand,
                constraints={"period_focus": "current", "consolidation_scope": "consolidated"},
                query_years=[2023],
                operation_family="lookup",
                selected_cell=candidate["metadata"]["structured_cells"][0],
                report_scope={"year": 2023},
            )
        )
        self.assertTrue(_candidate_matches_operand(paragraph_candidate, operand))

    def test_ampc_prose_surface_contract_extracts_preceding_numeric_value(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ontology = FinancialOntologyManager(Path("src/config/financial_ontology_concepts_v3.draft.json"))
        operand = ontology.concept_specs(
            "미국 인플레이션 감축법(IRA)에 따른 세액공제(AMPC) 금액",
            intent="comparison",
        )[0]
        operand = {**operand, "role": "subtrahend", "period_hint": "2023"}

        rows = agent._build_required_operands_from_candidates(
            [
                {
                    "evidence_id": "ev_ampc",
                    "source_anchor": "[LG에너지솔루션 | 2023 | IV. 이사의 경영진단 및 분석의견 > 2. 개요]",
                    "claim": (
                        "영업이익은 원가개선 노력과 약 6,769억원의 IRA Tax Credit의 수익 인식으로 "
                        "전년 대비 +78% 개선된 약 2조 1,632억원을 기록했습니다."
                    ),
                    "metadata": {
                        "section_path": "IV. 이사의 경영진단 및 분석의견 > 2. 개요",
                        "statement_type": "mda",
                    },
                }
            ],
            required_operands=[operand],
            query=(
                "2023년 연결기준 영업이익을 확인하고, 미국 인플레이션 감축법(IRA)에 따른 "
                "세액공제(AMPC) 금액을 제외했을 때의 실질 영업이익을 계산해 줘."
            ),
            topic="",
            report_scope={"company": "LG에너지솔루션", "year": 2023},
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["matched_operand_concept"], "advanced_manufacturing_production_credit")
        self.assertEqual(rows[0]["matched_operand_role"], "subtrahend")
        self.assertEqual(rows[0]["raw_value"], "6,769억원")
        self.assertEqual(rows[0]["normalized_value"], 676900000000.0)

    def test_ampc_prose_surface_contract_prefers_exact_parenthetical_value(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ontology = FinancialOntologyManager(Path("src/config/financial_ontology_concepts_v3.draft.json"))
        operand = ontology.concept_specs(
            "미국 인플레이션 감축법(IRA)에 따른 세액공제(AMPC) 금액",
            intent="comparison",
        )[0]
        operand = {**operand, "role": "subtrahend", "period_hint": "2023"}

        rows = agent._build_required_operands_from_candidates(
            [
                {
                    "evidence_id": "ev_ampc_exact",
                    "source_anchor": "[LG에너지솔루션 | 2023 | IV. 이사의 경영진단 및 분석의견 > 2. 개요]",
                    "claim": (
                        "2023년 영업이익에는 미국 인플레이션 감축법(IRA)에 따른 세액공제"
                        "(Tax Credit) 수익 약 6,769억원(676,874백만원)이 포함되어 있습니다. "
                        "약 6,769억원의 IRA Tax Credit의 수익 인식으로 영업이익이 개선되었습니다."
                    ),
                    "metadata": {
                        "section_path": "IV. 이사의 경영진단 및 분석의견 > 2. 개요",
                        "statement_type": "mda",
                    },
                }
            ],
            required_operands=[operand],
            query=(
                "2023년 연결기준 영업이익을 확인하고, 미국 인플레이션 감축법(IRA)에 따른 "
                "세액공제(AMPC) 금액을 제외했을 때의 실질 영업이익을 계산해 줘."
            ),
            topic="",
            report_scope={"company": "LG에너지솔루션", "year": 2023},
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["matched_operand_concept"], "advanced_manufacturing_production_credit")
        self.assertEqual(rows[0]["matched_operand_role"], "subtrahend")
        self.assertEqual(rows[0]["raw_value"], "676,874백만원")
        self.assertEqual(rows[0]["normalized_value"], 676874000000.0)

    def test_concept_lookup_synthesizes_answer_slot_from_ontology_surface_prose(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "query": "Compute adjusted operating income excluding AMPC.",
            "active_subtask": {
                "task_id": "task_2",
                "operation_family": "lookup",
                "metric_family": "concept_lookup",
                "metric_label": "2023 AMPC amount",
                "query": "Find 2023 AMPC amount.",
                "required_operands": [
                    {
                        "label": "AMPC amount",
                        "concept": "advanced_manufacturing_production_credit",
                        "role": "subtrahend",
                        "period_hint": "2023",
                        "aliases": ["AMPC", "IRA Tax Credit"],
                        "surface_contract": {
                            "positive": ["AMPC", "IRA Tax Credit"],
                            "negative": ["income tax", "deferred tax"],
                        },
                    }
                ],
            },
            "answer": (
                "2023 operating income was 2,163,234백만원. "
                "AMPC amount was 6,769억원, and adjusted operating income was 1,486,334백만원."
            ),
            "compressed_answer": "",
            "selected_claim_ids": ["ev_001"],
            "evidence_items": [],
            "retrieved_docs": [
                Document(
                    page_content=(
                        "영업이익은 원가개선 노력과 약 6,769억원의 IRA Tax Credit의 수익 인식으로 "
                        "전년 대비 개선되었습니다."
                    ),
                    metadata={
                        "company": "LG에너지솔루션",
                        "year": 2023,
                        "section_path": "IV. 이사의 경영진단 및 분석의견 > 2. 개요",
                    },
                )
            ],
            "tasks": [],
            "artifacts": [],
            "calculation_operands": [],
            "calculation_plan": {"operation": "lookup"},
            "calculation_result": {"status": "partial", "answer_slots": {"operation_family": "lookup"}},
            "reconciliation_result": {},
        }

        result = agent._capture_current_subtask_result(state)

        self.assertEqual(result["status"], "ok")
        slot = result["calculation_result"]["answer_slots"]["primary_value"]
        self.assertEqual(slot["concept"], "advanced_manufacturing_production_credit")
        self.assertEqual(slot["rendered_value"], "6,769억원")
        self.assertEqual(slot["role"], "subtrahend")
        self.assertIn("ev_001", result["selected_claim_ids"])
        self.assertTrue(
            any("6,769억원" in str(item.get("claim") or "") for item in result["runtime_evidence"])
        )

    def test_difference_answer_composer_preserves_slot_rendered_values(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        answer = agent._compose_slot_based_difference_answer(
            query="2023년 연결기준 영업이익에서 AMPC 금액을 제외한 실질 영업이익을 계산해 줘.",
            report_scope={"company": "LG에너지솔루션", "year": 2023},
            calculation_result={
                "answer_slots": {
                    "operation_family": "difference",
                    "components_by_role": {
                        "minuend": [
                            {
                                "status": "ok",
                                "label": "영업이익",
                                "period": "2023",
                                "rendered_value": "2조 1,632억원",
                                "normalized_value": 2163200000000.0,
                            }
                        ],
                        "subtrahend": [
                            {
                                "status": "ok",
                                "label": "첨단제조 생산세액공제",
                                "period": "2023",
                                "rendered_value": "6,769억원",
                                "normalized_value": 676900000000.0,
                            }
                        ],
                    },
                    "primary_value": {
                        "status": "ok",
                        "label": "실질 영업이익",
                        "period": "2023",
                        "rendered_value": "1조 4,863억원",
                        "normalized_value": 1486300000000.0,
                    },
                }
            },
        )

        self.assertIn("LG에너지솔루션", answer)
        self.assertIn("2023년 연결기준 영업이익은 2조 1,632억원", answer)
        self.assertIn("첨단제조 생산세액공제 금액은 6,769억원", answer)
        self.assertIn("실질 영업이익은 1조 4,863억원", answer)
        self.assertNotIn("676,900백만원", answer)

    def test_difference_answer_composer_recovers_company_from_slot_anchor(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        answer = agent._compose_slot_based_difference_answer(
            query="2023년 연결기준 영업이익에서 AMPC 금액을 제외한 실질 영업이익을 계산해 줘.",
            report_scope={},
            calculation_result={
                "answer_slots": {
                    "operation_family": "difference",
                    "components_by_role": {
                        "minuend": [
                            {
                                "status": "ok",
                                "label": "영업이익",
                                "period": "2023",
                                "rendered_value": "2,163,234백만원",
                                "normalized_value": 2163234000000.0,
                            }
                        ],
                        "subtrahend": [
                            {
                                "status": "ok",
                                "label": "첨단제조 생산세액공제",
                                "period": "2023년",
                                "rendered_value": "6,769억원",
                                "normalized_value": 676900000000.0,
                                "source_anchor": "[LG에너지솔루션 | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
                            }
                        ],
                    },
                    "primary_value": {
                        "status": "ok",
                        "label": "실질 영업이익",
                        "period": "2023",
                        "rendered_value": "1,486,334백만원",
                        "normalized_value": 1486334000000.0,
                    },
                }
            },
        )

        self.assertIn("LG에너지솔루션 2023년 연결기준 영업이익은 2,163,234백만원", answer)

    def test_adjusted_difference_result_preserves_source_unit_when_excluding_component(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = _execute_calculation_with_runtime_trace(agent,
            {
                "query": (
                    "2023년 연결기준 영업이익을 확인하고, 미국 인플레이션 감축법(IRA)에 따른 "
                    "세액공제(AMPC) 금액을 제외했을 때의 실질 영업이익을 계산해 줘."
                ),
                "active_subtask": {
                    "task_id": "task_ampc_adjusted_income",
                    "metric_family": "concept_difference",
                    "metric_label": "실질 영업이익",
                    "query": (
                        "2023년 연결기준 영업이익에서 AMPC 금액을 제외한 실질 영업이익을 계산해 줘."
                    ),
                    "operation_family": "difference",
                },
                "calculation_operands": [
                    {
                        "operand_id": "op_001",
                        "evidence_id": "ev_operating_income",
                        "label": "영업이익",
                        "normalized_value": 2163234000000.0,
                        "normalized_unit": "KRW",
                        "raw_value": "2,163,234",
                        "raw_unit": "백만원",
                        "period": "2023",
                        "matched_operand_role": "minuend",
                    },
                    {
                        "operand_id": "op_002",
                        "evidence_id": "ev_ampc",
                        "label": "첨단제조 생산세액공제",
                        "normalized_value": 676874000000.0,
                        "normalized_unit": "KRW",
                        "raw_value": "676,874",
                        "raw_unit": "백만원",
                        "period": "2023",
                        "matched_operand_role": "subtrahend",
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
                    "operation_text": "실질 영업이익",
                    "explanation": "difference",
                },
                "artifacts": [],
                "tasks": [],
            }
        )

        trace = _resolve_runtime_calculation_trace(result)
        calc = trace["calculation_result"]
        self.assertEqual(calc["status"], "ok")
        self.assertEqual(calc["rendered_value"], "1,486,360백만원")
        self.assertEqual(calc["answer_slots"]["primary_value"]["rendered_value"], "1,486,360백만원")
        self.assertEqual(calc["answer_slots"]["delta_value"]["rendered_value"], "1,486,360백만원")
        self.assertEqual(
            calc["answer_slots"]["components_by_role"]["subtrahend"][0]["rendered_value"],
            "676,874백만원",
        )

    def test_adjusted_difference_result_uses_source_unit_with_rounded_component_operand(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = _execute_calculation_with_runtime_trace(agent,
            {
                "query": "2023년 연결기준 영업이익에서 AMPC 금액을 제외한 실질 영업이익을 계산해 줘.",
                "active_subtask": {
                    "task_id": "task_ampc_adjusted_income",
                    "metric_family": "concept_difference",
                    "metric_label": "실질 영업이익",
                    "query": "2023년 연결기준 영업이익에서 AMPC 금액을 제외한 실질 영업이익을 계산해 줘.",
                    "operation_family": "difference",
                },
                "calculation_operands": [
                    {
                        "operand_id": "op_001",
                        "evidence_id": "ev_operating_income",
                        "label": "영업이익",
                        "normalized_value": 2163234000000.0,
                        "normalized_unit": "KRW",
                        "raw_value": "2,163,234",
                        "raw_unit": "백만원",
                        "period": "2023",
                        "matched_operand_role": "minuend",
                    },
                    {
                        "operand_id": "op_002",
                        "evidence_id": "ev_ampc",
                        "label": "첨단제조 생산세액공제",
                        "normalized_value": 676900000000.0,
                        "normalized_unit": "KRW",
                        "raw_value": "6,769억원",
                        "raw_unit": "원",
                        "period": "2023년",
                        "matched_operand_role": "subtrahend",
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
                    "operation_text": "실질 영업이익",
                    "explanation": "difference",
                },
                "artifacts": [],
                "tasks": [],
            }
        )

        trace = _resolve_runtime_calculation_trace(result)
        calc = trace["calculation_result"]
        self.assertEqual(calc["status"], "ok")
        self.assertEqual(calc["rendered_value"], "1,486,334백만원")
        self.assertEqual(calc["answer_slots"]["primary_value"]["rendered_value"], "1,486,334백만원")
        self.assertEqual(calc["answer_slots"]["delta_value"]["rendered_value"], "1,486,334백만원")

    def test_execute_calculation_ignores_legacy_top_level_operands_and_plan(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._execute_calculation(
            {
                "query": "Calculate a ratio.",
                "active_subtask": {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "metric_label": "ratio",
                    "operation_family": "ratio",
                    "required_operands": [
                        {"label": "numerator", "role": "numerator", "required": True},
                        {"label": "denominator", "role": "denominator", "required": True},
                    ],
                },
                "resolved_calculation_trace": {},
                "calculation_operands": [
                    {
                        "operand_id": "legacy_a",
                        "label": "numerator",
                        "normalized_value": 10.0,
                        "matched_operand_role": "numerator",
                    },
                    {
                        "operand_id": "legacy_b",
                        "label": "denominator",
                        "normalized_value": 2.0,
                        "matched_operand_role": "denominator",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "ratio",
                    "ordered_operand_ids": ["legacy_a", "legacy_b"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "legacy_a"},
                        {"variable": "B", "operand_id": "legacy_b"},
                    ],
                    "formula": "A / B",
                    "result_unit": "ratio",
                },
                "calculation_result": {"status": "legacy"},
                "artifacts": [],
                "tasks": [],
            }
        )

        trace = _resolve_runtime_calculation_trace(result, allow_legacy_top_level=False)
        self.assertEqual(trace["calculation_operands"], [])
        self.assertEqual(trace["calculation_plan"], {})
        self.assertEqual(trace["calculation_result"]["status"], "insufficient_operands")
        self.assertNotIn("calculation_operands", result)
        self.assertNotIn("calculation_plan", result)
        self.assertNotIn("calculation_result", result)

    def test_operand_precision_refines_rounded_llm_value_from_structured_table_cell(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "label": "첨단제조 생산세액공제 (IRA Tax Credit)",
            "raw_value": "6,769",
            "raw_unit": "억원",
            "normalized_value": 676900000000.0,
            "normalized_unit": "KRW",
        }
        evidence_item = {
            "metadata": {
                "table_row_records_json": json.dumps(
                    [
                        {
                            "row_id": "24:3",
                            "row_label": "기타영업손익",
                            "cells": [
                                {
                                    "cell_id": "24:3:2",
                                    "column_headers": ["공시금액"],
                                    "value_text": "676,874",
                                    "unit_hint": "백만원",
                                }
                            ],
                        },
                        {
                            "row_id": "24:5",
                            "row_label": "판매비와 관리비",
                            "cells": [
                                {
                                    "cell_id": "24:5:2",
                                    "column_headers": ["공시금액"],
                                    "value_text": "3,456,673",
                                    "unit_hint": "백만원",
                                }
                            ],
                        },
                    ],
                    ensure_ascii=False,
                )
            }
        }

        refined = agent._refine_operand_precision_from_evidence_table(row, evidence_item)

        self.assertEqual(refined["raw_value"], "676,874")
        self.assertEqual(refined["raw_unit"], "백만원")
        self.assertEqual(refined["normalized_value"], 676874000000.0)
        self.assertEqual(refined["precision_source"], "structured_table_cell")

    def test_operand_precision_uses_surface_anchor_when_llm_value_is_derived_result(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "label": "첨단제조 생산세액공제 (IRA Tax Credit)",
            "matched_operand_label": "첨단제조 생산세액공제",
            "raw_value": "1,486,334",
            "raw_unit": "백만원",
            "normalized_value": 1486334000000.0,
            "normalized_unit": "KRW",
        }
        evidence_item = {
            "claim": "영업이익: 2,163,234 (백만원), IRA Tax Credit: 6,769 (억원)",
            "quote_span": "영업이익: 2,163,234 (백만원), IRA Tax Credit: 6,769 (억원)",
            "metadata": {
                "table_row_records_json": json.dumps(
                    [
                        {
                            "row_id": "24:1",
                            "row_label": "매출액",
                            "cells": [
                                {
                                    "cell_id": "24:1:2",
                                    "column_headers": ["공시금액"],
                                    "value_text": "33,745,470",
                                    "unit_hint": "백만원",
                                }
                            ],
                        },
                        {
                            "row_id": "24:3",
                            "row_label": "기타영업손익",
                            "cells": [
                                {
                                    "cell_id": "24:3:2",
                                    "column_headers": ["공시금액"],
                                    "value_text": "676,874",
                                    "unit_hint": "백만원",
                                }
                            ],
                        },
                    ],
                    ensure_ascii=False,
                )
            },
        }

        refined = agent._refine_operand_precision_from_evidence_table(row, evidence_item)

        self.assertEqual(refined["raw_value"], "676,874")
        self.assertEqual(refined["raw_unit"], "백만원")
        self.assertEqual(refined["normalized_value"], 676874000000.0)
        self.assertEqual(refined["precision_source"], "surface_anchored_structured_table_cell")

    def test_operand_precision_uses_contextual_note_row_when_llm_claim_is_wrong(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "label": "2023년 첨단제조 생산세액공제 (AMPC)",
            "raw_value": "1,486,334",
            "raw_unit": "백만원",
            "normalized_value": 1486334000000.0,
            "normalized_unit": "KRW",
        }
        evidence_item = {
            "claim": "1,486,334 (백만원)",
            "quote_span": "1,486,334",
            "metadata": {
                "table_row_labels_text": "\n".join(
                    [
                        "공시금액",
                        "매출액",
                        "매출원가",
                        "매출총이익",
                        "기타영업손익",
                        "2023년 1월 1일부터 시행되는 미국 인플레이션감축법 첨단제조 생산세액공제 제도에 따른 수익금액입니다.",
                        "판매비와 관리비",
                    ]
                ),
                "table_row_records_json": json.dumps(
                    [
                        {
                            "row_id": "24:2",
                            "row_label": "매출총이익",
                            "cells": [
                                {
                                    "cell_id": "24:2:2",
                                    "column_headers": ["공시금액"],
                                    "value_text": "4,943,033",
                                    "unit_hint": "백만원",
                                }
                            ],
                        },
                        {
                            "row_id": "24:3",
                            "row_label": "기타영업손익",
                            "cells": [
                                {
                                    "cell_id": "24:3:2",
                                    "column_headers": ["공시금액"],
                                    "value_text": "676,874",
                                    "unit_hint": "백만원",
                                }
                            ],
                        },
                    ],
                    ensure_ascii=False,
                ),
            },
        }

        refined = agent._refine_operand_precision_from_evidence_table(row, evidence_item)

        self.assertEqual(refined["raw_value"], "676,874")
        self.assertEqual(refined["raw_unit"], "백만원")
        self.assertEqual(refined["normalized_value"], 676874000000.0)
        self.assertEqual(refined["precision_source"], "contextual_note_structured_table_cell")

    def test_operand_precision_prefers_matching_contextual_row_over_previous_row(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "label": "Cost of sales",
            "raw_value": "258,935,494",
            "raw_unit": "백만원",
            "normalized_value": 258935494000000.0,
            "normalized_unit": "KRW",
        }
        evidence_item = {
            "claim": "Cost of sales impact analysis",
            "quote_span": "Cost of sales impact analysis",
            "metadata": {
                "table_row_labels_text": "\n".join(["Revenue", "Cost of sales", "Gross profit"]),
                "table_row_records_json": json.dumps(
                    [
                        {
                            "row_id": "is:1",
                            "row_label": "Revenue",
                            "cells": [
                                {
                                    "cell_id": "is:1:1",
                                    "column_headers": ["2023"],
                                    "value_text": "258,935,494",
                                    "unit_hint": "백만원",
                                }
                            ],
                        },
                        {
                            "row_id": "is:2",
                            "row_label": "Cost of sales",
                            "cells": [
                                {
                                    "cell_id": "is:2:1",
                                    "column_headers": ["2023"],
                                    "value_text": "180,388,580",
                                    "unit_hint": "백만원",
                                }
                            ],
                        },
                    ],
                    ensure_ascii=False,
                ),
            },
        }

        refined = agent._refine_operand_precision_from_evidence_table(row, evidence_item)

        self.assertEqual(refined["raw_value"], "180,388,580")
        self.assertEqual(refined["raw_unit"], "백만원")
        self.assertEqual(refined["normalized_value"], 180388580000000.0)
        self.assertEqual(refined["precision_source"], "contextual_note_structured_table_cell")

    def test_operand_value_extraction_prefers_nearest_suffix_value_with_parenthetical_unit(self) -> None:
        operand = {
            "label": "첨단제조 생산세액공제",
            "aliases": ["IRA Tax Credit"],
        }

        value = _extract_numeric_value_after_operand_text(
            "영업이익: 2,163,234 (백만원), IRA Tax Credit: 6,769 (억원)",
            operand,
        )

        self.assertEqual(value, "6,769억원")

    def test_operand_unit_coercion_prefers_value_local_unit_over_table_unit_hint(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence_item = {
            "claim": "영업이익: 2,163,234 (백만원), IRA Tax Credit: 6,769 (억원)",
            "quote_span": "IRA Tax Credit: 6,769 (억원)",
            "metadata": {"unit_hint": "백만원"},
        }

        unit = agent._coerce_operand_unit_from_evidence(
            raw_value="6,769",
            raw_unit="",
            evidence_item=evidence_item,
        )

        self.assertEqual(unit, "억원")

    def test_operand_unit_coercion_overrides_current_krw_unit_with_value_local_unit(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence_item = {
            "claim": "segment revenue 2,176,431,531,380 (원)",
            "quote_span": "2,176,431,531,380",
            "metadata": {"unit_hint": "천원"},
        }

        unit = agent._coerce_operand_unit_from_evidence(
            raw_value="2,176,431,531,380",
            raw_unit="천원",
            evidence_item=evidence_item,
        )

        self.assertEqual(unit, "원")

    def test_structured_direct_operand_row_uses_value_local_unit_from_evidence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "operand_id": "op_001",
            "evidence_id": "candidate_ampc",
            "label": "첨단제조 생산세액공제 (IRA Tax Credit)",
            "raw_value": "6,769",
            "raw_unit": "백만원",
            "normalized_value": 6769000000.0,
            "normalized_unit": "KRW",
        }
        evidence_by_id = {
            "recon::candidate_ampc": {
                "claim": "영업이익: 2,163,234 (백만원), IRA Tax Credit: 6,769 (억원)",
                "quote_span": "IRA Tax Credit: 6,769 (억원)",
                "metadata": {"unit_hint": "백만원"},
            }
        }

        evidence_item = agent._evidence_item_for_operand_row(row, evidence_by_id)
        coerced = agent._coerce_operand_row_from_evidence(row, evidence_item)

        self.assertEqual(coerced["raw_unit"], "억원")
        self.assertEqual(coerced["normalized_value"], 676900000000.0)
        self.assertEqual(coerced["normalized_unit"], "KRW")

    def test_structured_direct_operand_row_repairs_current_unit_from_source_surface(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "operand_id": "op_001",
            "evidence_id": "ev_direct",
            "label": "segment revenue",
            "raw_value": "2,176,431,531,380",
            "raw_unit": "천원",
            "normalized_value": 2176431531380000.0,
            "normalized_unit": "KRW",
        }
        evidence_item = {
            "evidence_id": "ev_direct",
            "claim": "segment revenue 2,176,431,531,380 (원)",
            "quote_span": "2,176,431,531,380",
            "metadata": {"unit_hint": "천원"},
        }

        coerced = agent._coerce_operand_row_from_evidence(row, evidence_item)

        self.assertEqual(coerced["raw_unit"], "원")
        self.assertEqual(coerced["normalized_value"], 2176431531380.0)
        self.assertEqual(coerced["normalized_unit"], "KRW")

    def test_execution_repairs_generated_krw_unit_from_table_metadata(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "query": "Calculate result over cost.",
            "active_subtask": {
                "task_id": "task_ratio",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "result", "role": "numerator", "required": True},
                    {"label": "cost", "role": "denominator", "required": True},
                ],
            },
            "evidence_items": [
                {
                    "evidence_id": "ev_result",
                    "claim": "result 3,500천원",
                    "quote_span": "result 3,500천원",
                    "metadata": {
                        "block_type": "table",
                        "unit_hint": "백만원",
                        "table_source_id": "table_result",
                        "table_value_labels_text": "result 3,500",
                    },
                },
                {
                    "evidence_id": "ev_cost",
                    "claim": "cost 1,000백만원",
                    "quote_span": "cost 1,000백만원",
                    "metadata": {
                        "block_type": "table",
                        "unit_hint": "백만원",
                        "table_source_id": "table_cost",
                        "table_value_labels_text": "cost 1,000",
                    },
                },
            ],
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {
                        "operand_id": "numerator",
                        "matched_operand_label": "result",
                        "matched_operand_role": "numerator",
                        "raw_value": "3,500",
                        "raw_unit": "천원",
                        "normalized_value": 3_500_000.0,
                        "normalized_unit": "KRW",
                        "evidence_id": "ev_result",
                        "source_row_ids": ["ev_result"],
                    },
                    {
                        "operand_id": "denominator",
                        "matched_operand_label": "cost",
                        "matched_operand_role": "denominator",
                        "raw_value": "1,000",
                        "raw_unit": "백만원",
                        "normalized_value": 1_000_000_000.0,
                        "normalized_unit": "KRW",
                        "evidence_id": "ev_cost",
                        "source_row_ids": ["ev_cost"],
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "ratio",
                    "operation_family": "ratio",
                    "formula": "A / B",
                    "result_unit": "배",
                    "ordered_operand_ids": ["numerator", "denominator"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "numerator"},
                        {"variable": "B", "operand_id": "denominator"},
                    ],
                },
                "calculation_result": {},
            },
        }

        result = agent._execute_calculation(state)
        trace = result["resolved_calculation_trace"]
        operands = {row["operand_id"]: row for row in trace["calculation_operands"]}

        self.assertEqual(operands["numerator"]["raw_unit"], "백만원")
        self.assertEqual(operands["numerator"]["source_raw_unit"], "천원")
        self.assertEqual(operands["numerator"]["unit_normalization_repair_source"], "table_metadata_unit_hint")
        self.assertAlmostEqual(trace["calculation_result"]["result_value"], 3.5)

    def test_lookup_slot_refinement_prefers_value_local_unit_over_table_unit_hint(self) -> None:
        slot = {
            "status": "ok",
            "role": "primary_value",
            "label": "첨단제조 생산세액공제",
            "raw_value": "6,769",
            "raw_unit": "백만원",
            "normalized_value": 6769000000.0,
            "normalized_unit": "KRW",
            "rendered_value": "6,769백만원",
        }
        evidence = {
            "claim": "영업이익: 2,163,234 (백만원), IRA Tax Credit: 6,769 (억원)",
            "quote_span": "IRA Tax Credit: 6,769 (억원)",
            "metadata": {"unit_hint": "백만원"},
        }

        refined = _refine_lookup_slot_unit_from_evidence(slot, evidence)

        self.assertEqual(refined["raw_unit"], "억원")
        self.assertEqual(refined["normalized_value"], 676900000000.0)
        self.assertEqual(refined["rendered_value"], "6,769억원")

    def test_lookup_slot_refinement_uses_claim_unit_when_quote_span_has_value_only(self) -> None:
        slot = {
            "status": "ok",
            "role": "primary_value",
            "label": "매출액",
            "raw_value": "2,176,431,531,380",
            "raw_unit": "천원",
            "normalized_value": 2176431531380000.0,
            "normalized_unit": "KRW",
            "rendered_value": "2,176,431,531,380천원",
        }
        evidence = {
            "claim": "2,176,431,531,380 (원)",
            "quote_span": "2,176,431,531,380",
            "metadata": {"unit_hint": "천원"},
        }

        refined = _refine_lookup_slot_unit_from_evidence(slot, evidence)

        self.assertEqual(refined["raw_unit"], "원")
        self.assertEqual(refined["normalized_value"], 2176431531380.0)
        self.assertEqual(refined["rendered_value"], "2,176,431,531,380원")

    def test_lookup_slot_refinement_does_not_treat_adjacent_number_as_unit(self) -> None:
        slot = {
            "status": "ok",
            "role": "primary_value",
            "label": "영업이익",
            "raw_value": "2,163,234",
            "raw_unit": "백만원",
            "normalized_value": 2163234000000.0,
            "normalized_unit": "KRW",
            "rendered_value": "2,163,234백만원",
        }
        evidence = {
            "claim": "영업이익 2,163,234 | 2022년 1,213,705",
            "quote_span": "영업이익 2,163,234",
            "metadata": {"unit_hint": "백만원"},
        }

        refined = _refine_lookup_slot_unit_from_evidence(slot, evidence)

        self.assertEqual(refined["raw_unit"], "백만원")
        self.assertEqual(refined["normalized_value"], 2163234000000.0)

    def test_preferred_complete_numeric_answer_prioritizes_query_matching_metric(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        target_row = {
            "task_id": "task_1",
            "metric_label": "영업이익률 감소 영향",
            "operation_family": "ratio",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "8.36%p",
                "formatted_result": "영업이익률 감소 영향은 8.36%p입니다.",
                "answer_slots": {
                    "components_by_group": {
                        "numerator": [{"raw_value": "182,049,824", "raw_unit": "천원"}],
                        "denominator": [{"raw_value": "2,176,431,531,380", "raw_unit": "원"}],
                    }
                },
            },
        }
        support_row = {
            "task_id": "task_2",
            "metric_label": "영업이익률",
            "operation_family": "ratio",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "29.93%",
                "formatted_result": "영업이익률은 29.93%입니다.",
                "answer_slots": {
                    "components_by_group": {
                        "numerator": [{"raw_value": "651,481,422,157", "raw_unit": "원"}],
                        "denominator": [{"raw_value": "2,176,431,531,380", "raw_unit": "원"}],
                    }
                },
            },
        }

        answer = agent._preferred_complete_numeric_answer(
            [target_row, support_row],
            query="영업이익률 감소 영향을 계산해 줘",
        )

        self.assertIn("8.36%p", answer)
        self.assertNotIn("29.93%", answer)

    def test_lookup_direct_support_accepts_raw_value_with_embedded_unit(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "label": "첨단제조 생산세액공제",
            "matched_operand_label": "첨단제조 생산세액공제",
            "matched_operand_concept": "advanced_manufacturing_production_credit",
            "raw_value": "6,769억원",
        }
        evidence_item = {
            "claim": "영업이익은 물류비 절감 및 6,769억원의 IRA Tax Credit 수익 인식으로 개선되었습니다.",
            "quote_span": "6,769억원의 IRA Tax Credit",
        }
        required_operands = [
            {
                "label": "첨단제조 생산세액공제",
                "concept": "advanced_manufacturing_production_credit",
                "aliases": ["IRA Tax Credit"],
                "surface_contract": {"positive": ["IRA Tax Credit"]},
            }
        ]

        self.assertTrue(agent._llm_lookup_operand_has_direct_support(row, evidence_item, required_operands))

    def test_difference_renderer_prefers_slot_contract_over_llm_rendering(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        calculation_result = {
            "status": "ok",
            "result_value": 1486360000000.0,
            "result_unit": "백만원",
            "rendered_value": "1,486,360백만원",
            "answer_slots": {
                "operation_family": "difference",
                "metric_label": "실질 영업이익",
                "components_by_role": {
                    "minuend": [
                        {
                            "status": "ok",
                            "role": "minuend",
                            "label": "영업이익",
                            "period": "2023",
                            "rendered_value": "2,163,234백만원",
                            "normalized_value": 2163234000000.0,
                        }
                    ]
                },
                "prior_value": {
                    "status": "ok",
                    "role": "prior_value",
                    "label": "첨단제조 생산세액공제 (IRA Tax Credit)",
                    "period": "2023년",
                    "rendered_value": "6,769억원",
                    "normalized_value": 676874000000.0,
                },
                "primary_value": {
                    "status": "ok",
                    "role": "primary_value",
                    "label": "실질 영업이익",
                    "period": "2023",
                    "rendered_value": "1,486,360백만원",
                    "normalized_value": 1486360000000.0,
                },
            },
        }

        rendered = agent._render_calculation_answer(
            {
                "query": "2023년 연결기준 영업이익에서 AMPC 금액을 제외한 실질 영업이익을 계산해 줘.",
                "report_scope": {"company": "LG에너지솔루션", "year": 2023},
                "resolved_calculation_trace": {
                    "calculation_plan": {"operation": "subtract"},
                    "calculation_operands": [],
                    "calculation_result": calculation_result,
                },
                "calculation_plan": {},
                "calculation_result": {},
                "calculation_operands": [],
            }
        )

        trace = _resolve_runtime_calculation_trace(rendered)
        self.assertIn("1,486,360백만원", rendered["answer"])
        self.assertNotIn("1,486,334백만원", rendered["answer"])
        self.assertEqual(trace["calculation_result"]["formatted_result"], rendered["answer"])
        self.assertNotIn("calculation_operands", rendered)
        self.assertNotIn("calculation_plan", rendered)
        self.assertNotIn("calculation_result", rendered)

    def test_render_success_omits_compatibility_mirrors(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(CalculationRenderOutput(final_answer="The result is 25.4%."))
        rendered = agent._render_calculation_answer(
            {
                "query": "calculate ratio",
                "resolved_calculation_trace": {
                    "calculation_operands": [
                        {"operand_id": "op_001", "label": "numerator"},
                        {"operand_id": "op_002", "label": "denominator"},
                    ],
                    "calculation_plan": {"status": "ok", "operation": "ratio"},
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 25.4,
                        "result_unit": "%",
                        "rendered_value": "25.4%",
                    },
                },
                "structured_result": {},
                "calculation_operands": [{"operand_id": "stale"}],
                "calculation_plan": {"status": "stale"},
                "calculation_result": {"status": "stale"},
            }
        )

        trace = _resolve_runtime_calculation_trace(rendered)
        self.assertEqual(rendered["answer"], "The result is 25.4%.")
        self.assertEqual(trace["calculation_result"]["formatted_result"], "The result is 25.4%.")
        self.assertNotIn("calculation_operands", rendered)
        self.assertNotIn("calculation_plan", rendered)
        self.assertNotIn("calculation_result", rendered)

    def test_late_runtime_numeric_answer_uses_resolved_trace(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        answer = agent._late_runtime_numeric_answer(
            {
                "query": "calculate ratio",
                "active_subtask": {"metric_label": "coverage ratio"},
                "resolved_calculation_trace": {
                    "calculation_operands": [],
                    "calculation_plan": {"status": "ok", "operation": "sum"},
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 25.4,
                        "result_unit": "%",
                        "rendered_value": "25.4%",
                        "formatted_result": "The ratio is 25.4%.",
                    },
                },
                "calculation_plan": {"operation": "stale"},
                "calculation_result": {"status": "stale", "rendered_value": "0%"},
            },
            "The draft answer said 0%.",
        )

        self.assertEqual(answer, "The ratio is 25.4%.")

    def test_late_runtime_numeric_answer_ignores_legacy_top_level_trace(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        answer = agent._late_runtime_numeric_answer(
            {
                "query": "calculate ratio",
                "active_subtask": {"metric_label": "coverage ratio"},
                "resolved_calculation_trace": {},
                "calculation_plan": {"status": "ok", "operation": "sum"},
                "calculation_result": {
                    "status": "ok",
                    "result_value": 25.4,
                    "result_unit": "%",
                    "rendered_value": "25.4%",
                    "formatted_result": "The ratio is 25.4%.",
                },
            },
            "The draft answer said 0%.",
        )

        self.assertEqual(answer, "")

    def test_render_structured_output_failure_omits_compatibility_mirrors(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _FailingLLM()
        rendered = agent._render_calculation_answer(
            {
                "query": "calculate ratio",
                "resolved_calculation_trace": {
                    "calculation_operands": [
                        {"operand_id": "op_001", "label": "numerator"},
                        {"operand_id": "op_002", "label": "denominator"},
                    ],
                    "calculation_plan": {"status": "ok", "operation": "ratio"},
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 25.4,
                        "result_unit": "%",
                        "rendered_value": "25.4%",
                    },
                },
                "structured_result": {},
                "calculation_operands": [{"operand_id": "stale"}],
                "calculation_plan": {"status": "stale"},
                "calculation_result": {"status": "stale"},
            }
        )

        trace = _resolve_runtime_calculation_trace(rendered)
        self.assertEqual(rendered["answer"], "25.4%")
        self.assertEqual(trace["calculation_result"]["formatted_result"], "25.4%")
        self.assertEqual(rendered["structured_result"]["formatted_result"], "25.4%")
        self.assertNotIn("calculation_operands", rendered)
        self.assertNotIn("calculation_plan", rendered)
        self.assertNotIn("calculation_result", rendered)

    def test_render_ignores_legacy_top_level_runtime_projection(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        rendered = agent._render_calculation_answer(
            {
                "query": "calculate ratio",
                "resolved_calculation_trace": {},
                "structured_result": {},
                "calculation_operands": [{"operand_id": "legacy"}],
                "calculation_plan": {"status": "ok", "operation": "ratio"},
                "calculation_result": {
                    "status": "ok",
                    "result_value": 25.4,
                    "rendered_value": "25.4%",
                },
            }
        )

        self.assertEqual(rendered, {"answer": "", "compressed_answer": "", "draft_points": []})

    def test_verify_structured_output_failure_omits_compatibility_mirrors(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _FailingLLM()
        verified = agent._verify_calculation_answer(
            {
                "query": "calculate ratio",
                "answer": "25.4%",
                "compressed_answer": "25.4%",
                "resolved_calculation_trace": {
                    "calculation_operands": [
                        {"operand_id": "op_001", "label": "numerator"},
                        {"operand_id": "op_002", "label": "denominator"},
                    ],
                    "calculation_plan": {"status": "ok", "operation": "ratio"},
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 25.4,
                        "result_unit": "%",
                        "rendered_value": "25.4%",
                        "formatted_result": "25.4%",
                    },
                },
                "structured_result": {"status": "ok", "formatted_result": "25.4%"},
                "calculation_operands": [{"operand_id": "stale"}],
                "calculation_plan": {"status": "stale"},
                "calculation_result": {"status": "stale"},
                "calculation_debug_trace": {},
            }
        )

        trace = _resolve_runtime_calculation_trace(verified)
        self.assertEqual(verified["answer"], "25.4%")
        self.assertEqual(trace["calculation_result"]["formatted_result"], "25.4%")
        self.assertEqual(verified["calculation_debug_trace"]["verification"]["verdict"], "error_keep")
        self.assertNotIn("calculation_operands", verified)
        self.assertNotIn("calculation_plan", verified)
        self.assertNotIn("calculation_result", verified)

    def test_verify_ignores_legacy_top_level_runtime_projection(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        verified = agent._verify_calculation_answer(
            {
                "query": "calculate ratio",
                "answer": "25.4%",
                "compressed_answer": "25.4%",
                "resolved_calculation_trace": {},
                "structured_result": {},
                "calculation_operands": [{"operand_id": "legacy"}],
                "calculation_plan": {"status": "ok", "operation": "ratio"},
                "calculation_result": {
                    "status": "ok",
                    "result_value": 25.4,
                    "rendered_value": "25.4%",
                },
                "calculation_debug_trace": {},
            }
        )

        self.assertEqual(verified["answer"], "25.4%")
        self.assertEqual(verified["calculation_debug_trace"]["verification"]["verdict"], "skip")
        self.assertEqual(
            _resolve_runtime_calculation_trace(verified, allow_legacy_top_level=False),
            {},
        )
        self.assertNotIn("calculation_operands", verified)
        self.assertNotIn("calculation_plan", verified)
        self.assertNotIn("calculation_result", verified)

    def test_verify_success_omits_compatibility_mirrors(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            CalculationVerificationOutput(
                verdict="keep",
                issues=[],
                final_answer="25.4%",
            )
        )
        verified = agent._verify_calculation_answer(
            {
                "query": "calculate ratio",
                "answer": "25.4%",
                "compressed_answer": "25.4%",
                "resolved_calculation_trace": {
                    "calculation_operands": [
                        {"operand_id": "op_001", "label": "numerator"},
                        {"operand_id": "op_002", "label": "denominator"},
                    ],
                    "calculation_plan": {"status": "ok", "operation": "ratio"},
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 25.4,
                        "result_unit": "%",
                        "rendered_value": "25.4%",
                        "formatted_result": "25.4%",
                    },
                },
                "structured_result": {"status": "ok", "formatted_result": "25.4%"},
                "calculation_operands": [{"operand_id": "stale"}],
                "calculation_plan": {"status": "stale"},
                "calculation_result": {"status": "stale"},
                "calculation_debug_trace": {},
            }
        )

        trace = _resolve_runtime_calculation_trace(verified)
        self.assertEqual(verified["answer"], "25.4%")
        self.assertEqual(trace["calculation_result"]["formatted_result"], "25.4%")
        self.assertEqual(verified["calculation_debug_trace"]["verification"]["verdict"], "keep")
        self.assertNotIn("calculation_operands", verified)
        self.assertNotIn("calculation_plan", verified)
        self.assertNotIn("calculation_result", verified)

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

    def test_direct_lookup_row_uses_aggregate_cell_when_operand_policy_prefers_aggregate(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = agent._lookup_row_from_direct_structured_evidence(
            {
                "label": "매출액",
                "concept": "revenue",
                "role": "denominator",
                "binding_policy": {
                    "prefer_value_roles": ["aggregate"],
                    "prefer_aggregation_stages": ["final", "subtotal", "direct"],
                },
            },
            {
                "evidence_id": "table::value:0",
                "source_anchor": "[example]",
                "metadata": {
                    "year": 2023,
                    "unit_hint": "천원",
                    "row_label": "매출액",
                    "semantic_label": "매출액",
                    "structured_cells": [
                        {
                            "value_text": "100",
                            "unit_hint": "천원",
                            "column_headers": ["Segment A"],
                            "value_role": "detail",
                            "aggregation_stage": "none",
                        },
                        {
                            "value_text": "300",
                            "unit_hint": "천원",
                            "column_headers": ["제품과 용역 합계"],
                            "value_role": "detail",
                            "aggregation_stage": "none",
                            "aggregate_label": "제품과 용역 합계",
                        },
                    ],
                },
            },
            index=1,
        )

        self.assertEqual(row["raw_value"], "300")
        self.assertEqual(row["aggregate_label"], "제품과 용역 합계")

    def test_table_label_lookup_requires_structured_context_for_aggregate_policy(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        operand = {
            "label": "selected cost",
            "concept": "selected_cost",
            "role": "numerator",
            "binding_policy": {
                "prefer_value_roles": ["aggregate"],
                "prefer_aggregation_stages": ["final", "subtotal", "direct"],
            },
        }

        cell_less = agent._lookup_value_from_table_label_metadata(
            operand,
            {
                "evidence_id": "ev_text_only",
                "source_anchor": "[example]",
                "metadata": {
                    "year": 2023,
                    "unit_hint": "천원",
                    "table_value_labels_text": "\n".join(
                        [
                            "selected cost 100",
                            "selected cost 200",
                            "selected cost 300",
                        ]
                    ),
                },
            },
        )
        self.assertEqual(cell_less, {})

        structured = agent._lookup_value_from_table_label_metadata(
            operand,
            {
                "evidence_id": "ev_structured",
                "source_anchor": "[example]",
                "metadata": {
                    "year": 2023,
                    "unit_hint": "천원",
                    "row_label": "other metric",
                    "semantic_label": "other metric",
                    "table_value_labels_text": "\n".join(
                        [
                            "selected cost 100",
                            "selected cost 200",
                            "selected cost 300",
                        ]
                    ),
                    "structured_cells": [
                        {
                            "value_text": "10",
                            "unit_hint": "천원",
                            "column_headers": ["Segment A"],
                        }
                    ],
                },
            },
        )

        self.assertEqual(structured["raw_value"], "300")
        self.assertEqual(structured["value_role"], "aggregate")
        self.assertEqual(structured["aggregation_stage"], "final")

    def test_required_operand_assembly_prefers_aggregate_table_label_value_with_structured_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        required_operands = [
            {
                "label": "selected cost",
                "concept": "selected_cost",
                "role": "numerator",
                "binding_policy": {
                    "prefer_value_roles": ["aggregate"],
                    "prefer_aggregation_stages": ["final", "subtotal", "direct"],
                },
            }
        ]
        text_only_rows = agent._build_required_operands_from_candidates(
            [
                {
                    "candidate_id": "text_only",
                    "evidence_id": "text_only",
                    "claim": "other metric 10",
                    "metadata": {
                        "year": 2023,
                        "unit_hint": "천원",
                        "table_value_labels_text": "\n".join(
                            ["selected cost 100", "selected cost 200", "selected cost 300"]
                        ),
                    },
                }
            ],
            required_operands=required_operands,
            query="2023년 selected cost를 계산해 줘.",
            topic="selected cost",
            report_scope={"year": 2023},
        )
        self.assertEqual(text_only_rows, [])

        structured_rows = agent._build_required_operands_from_candidates(
            [
                {
                    "candidate_id": "structured",
                    "evidence_id": "structured",
                    "claim": "other metric 10",
                    "metadata": {
                        "year": 2023,
                        "unit_hint": "천원",
                        "row_label": "other metric",
                        "semantic_label": "other metric",
                        "table_value_labels_text": "\n".join(
                            ["selected cost 100", "selected cost 200", "selected cost 300"]
                        ),
                        "structured_cells": [
                            {"value_text": "10", "unit_hint": "천원", "column_headers": ["Segment A"]}
                        ],
                    },
                }
            ],
            required_operands=required_operands,
            query="2023년 selected cost를 계산해 줘.",
            topic="selected cost",
            report_scope={"year": 2023},
        )

        self.assertEqual(len(structured_rows), 1)
        self.assertEqual(structured_rows[0]["raw_value"], "300")
        self.assertEqual(structured_rows[0]["value_role"], "aggregate")
        self.assertEqual(structured_rows[0]["aggregation_stage"], "final")

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

    def test_lookup_direct_acceptance_rejects_percent_row_for_krw_operand(self) -> None:
        operand = {
            "label": "영업이익",
            "concept": "operating_income",
            "aliases": ["영업손익"],
            "role": "primary_value",
            "unit_family": "KRW",
            "binding_policy": {
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        candidate = {
            "candidate_kind": "structured_value",
            "text": "영업이익률 | 2023 | 2.54%",
            "metadata": {
                "row_label": "영업이익률",
                "semantic_label": "영업이익률",
                "statement_type": "summary_financials",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["2023"],
                "year": 2023,
                "value_role": "detail",
                "aggregation_stage": "none",
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "2.54", "unit_hint": "%"},
                ],
            },
        }

        selected_cell = _candidate_selected_cell_for_operand(
            candidate,
            operand=operand,
            query_years=[2023],
            period_focus="current",
        )

        self.assertTrue(_candidate_matches_operand(candidate, operand))
        self.assertFalse(
            _candidate_satisfies_direct_acceptance_contract(
                candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
                query_years=[2023],
                operation_family="lookup",
                selected_cell=selected_cell,
                report_scope={"company": "삼성전자", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240312000736"},
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

    def test_lookup_direct_acceptance_allows_statement_type_when_section_is_parent_financial_statement(self) -> None:
        operand = {
            "label": "2023년 매출원가",
            "concept": "cost_of_sales",
            "aliases": ["매출원가", "매출 원가", "cost of sales"],
            "role": "primary_value",
            "unit_family": "KRW",
            "binding_policy": {
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
            "surface_contract": {
                "positive": ["매출원가", "매출 원가"],
                "negative": ["매출액", "영업비용", "판매비와관리비"],
            },
        }
        selected_cell = {
            "column_headers": ["제 56 기", "당기", "2023"],
            "value_text": "129,179,183",
            "unit_hint": "백만원",
            "_report_year": 2023,
        }
        candidate = {
            "candidate_kind": "structured_value",
            "text": "매출원가 | 129,179,183",
            "metadata": {
                "semantic_label": "매출원가",
                "row_label": "매출원가",
                "statement_type": "income_statement",
                "consolidation_scope": "consolidated",
                "period_focus": "multi_period",
                "period_labels": ["당기", "2023", "2022", "2021"],
                "section_path": "III. 재무에 관한 사항 > 2. 연결재무제표",
                "table_context": "III. 재무에 관한 사항 > 2. 연결재무제표",
                "year": 2023,
                "value_role": "detail",
                "aggregation_stage": "none",
                "unit_hint": "백만원",
            },
        }

        self.assertTrue(
            _candidate_satisfies_direct_acceptance_contract(
                candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
                query_years=[2023],
                operation_family="lookup",
                selected_cell=selected_cell,
                report_scope={"company": "현대자동차", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240313001451"},
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

    def test_precision_refinement_respects_prior_period_structured_cell(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "raw_value": "1,083,717,091,152",
            "raw_unit": "원",
            "normalized_value": 1083717091152.0,
            "normalized_unit": "KRW",
            "period": "2022",
            "label": "2022년 법인세비용차감전순이익",
            "matched_operand_label": "법인세비용차감전순이익",
            "matched_operand_concept": "income_before_income_taxes",
            "matched_operand_role": "prior_period",
        }
        evidence_item = {
            "raw_row_text": (
                "법인세비용차감전순이익 | 제 25 기 1,481,396,317,551 원 | "
                "제 24 기 1,083,717,091,152 원"
            ),
            "metadata": {
                "year": 2023,
                "table_row_labels_text": "법인세비용차감전순이익",
                "table_row_records_json": json.dumps(
                    [
                        {
                            "row_label": "법인세비용차감전순이익",
                            "cells": [
                                {
                                    "column_headers": ["제 25 기"],
                                    "value_text": "1,481,396,317,551",
                                    "unit_hint": "원",
                                },
                                {
                                    "column_headers": ["제 24 기"],
                                    "value_text": "1,083,717,091,152",
                                    "unit_hint": "원",
                                },
                            ],
                        }
                    ],
                    ensure_ascii=False,
                ),
            },
        }

        refined = agent._refine_operand_precision_from_evidence_table(row, evidence_item)

        self.assertEqual(refined["raw_value"], "1,083,717,091,152")
        self.assertEqual(refined["normalized_value"], 1083717091152.0)

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

    def test_dependency_slot_match_respects_symbolic_prior_period_hint(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        binding = {
            "label": "자본총계",
            "concept": "total_equity",
            "role": "denominator_2",
            "period": "prior",
        }
        sibling_row = {"metric_label": "자본총계"}
        state = {"report_scope": {"year": 2023}}

        current_slot = {
            "label": "자본총계",
            "concept": "total_equity",
            "period": "2023",
            "raw_value": "363,677,865",
        }
        prior_slot = {
            "label": "자본총계",
            "concept": "total_equity",
            "period": "2022",
            "raw_value": "354,749,604",
        }

        self.assertFalse(
            agent._dependency_slot_matches_input(
                binding,
                current_slot,
                sibling_row=sibling_row,
                state=state,
            )
        )
        self.assertTrue(
            agent._dependency_slot_matches_input(
                binding,
                prior_slot,
                sibling_row=sibling_row,
                state=state,
            )
        )

    def test_formula_plan_no_operands_omits_compatibility_mirrors(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._plan_formula_calculation(
            {
                "query": "calculate the value",
                "active_subtask": {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "value",
                    "operation_family": "lookup",
                },
                "resolved_calculation_trace": {},
                "structured_result": {},
                "calculation_operands": [],
                "calculation_plan": {},
                "calculation_result": {},
                "artifacts": [],
                "tasks": [],
            }
        )

        trace = _resolve_runtime_calculation_trace(result)
        self.assertEqual(trace["calculation_plan"]["status"], "incomplete")
        self.assertEqual(trace["calculation_plan"]["operation"], "none")
        self.assertEqual(trace["calculation_result"], {})
        self.assertNotIn("calculation_operands", result)
        self.assertNotIn("calculation_plan", result)
        self.assertNotIn("calculation_result", result)

    def test_formula_plan_ignores_legacy_top_level_operands(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._plan_formula_calculation(
            {
                "query": "calculate the value",
                "active_subtask": {
                    "task_id": "task_1",
                    "metric_family": "concept_lookup",
                    "metric_label": "value",
                    "operation_family": "lookup",
                },
                "resolved_calculation_trace": {},
                "structured_result": {},
                "calculation_operands": [
                    {
                        "operand_id": "legacy",
                        "label": "legacy value",
                        "raw_value": "100",
                        "normalized_value": 100.0,
                    }
                ],
                "calculation_plan": {"status": "legacy"},
                "calculation_result": {"status": "legacy"},
                "artifacts": [],
                "tasks": [],
            }
        )

        trace = _resolve_runtime_calculation_trace(result, allow_legacy_top_level=False)
        self.assertEqual(result["planner_debug_trace"]["reason"], "no operands")
        self.assertEqual(trace["calculation_operands"], [])
        self.assertEqual(trace["calculation_plan"]["operation"], "none")
        self.assertEqual(trace["calculation_result"], {})
        self.assertNotIn("calculation_operands", result)
        self.assertNotIn("calculation_plan", result)
        self.assertNotIn("calculation_result", result)

    def test_deterministic_operation_guard_omits_compatibility_mirrors(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._plan_formula_calculation(
            _with_runtime_calculation_trace(
            {
                "query": "calculate the difference",
                "active_subtask": {
                    "task_id": "task_1",
                    "metric_family": "concept_difference",
                    "metric_label": "difference",
                    "operation_family": "difference",
                    "required_operands": [
                        {"label": "value", "required": True},
                        {"label": "value", "required": True},
                    ],
                },
                "structured_result": {},
                "resolved_calculation_trace": {
                    "calculation_operands": [
                        {
                            "operand_id": "op_001",
                            "label": "value",
                            "matched_operand_label": "value",
                            "raw_value": "100",
                            "normalized_value": 100.0,
                        }
                    ],
                    "calculation_plan": {},
                    "calculation_result": {},
                },
                "calculation_operands": [{"operand_id": "legacy"}],
                "calculation_plan": {},
                "calculation_result": {},
                "artifacts": [],
                "tasks": [],
            }
            )
        )

        trace = _resolve_runtime_calculation_trace(result)
        self.assertEqual(result["planner_debug_trace"]["reason"], "invalid_required_operand_bindings")
        self.assertEqual(trace["calculation_plan"]["status"], "incomplete")
        self.assertIn("distinct_operands", trace["calculation_plan"]["missing_info"])
        self.assertEqual(trace["calculation_result"], {})
        self.assertNotIn("calculation_plan", result)
        self.assertNotIn("calculation_result", result)

    def test_formula_plan_structured_output_failure_omits_compatibility_mirrors(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _FailingLLM()
        result = agent._plan_formula_calculation(
            _with_runtime_calculation_trace(
            {
                "query": "calculate the composite value",
                "active_subtask": {
                    "task_id": "task_1",
                    "metric_family": "generic_numeric",
                    "metric_label": "composite value",
                    "operation_family": "generic_numeric",
                },
                "structured_result": {},
                "resolved_calculation_trace": {
                    "calculation_operands": [
                        {
                            "operand_id": "op_001",
                            "label": "value",
                            "raw_value": "100",
                            "normalized_value": 100.0,
                        }
                    ],
                    "calculation_plan": {},
                    "calculation_result": {},
                },
                "calculation_operands": [{"operand_id": "legacy"}],
                "calculation_plan": {},
                "calculation_result": {},
                "artifacts": [],
                "tasks": [],
            }
            )
        )

        trace = _resolve_runtime_calculation_trace(result)
        self.assertTrue(result["planner_debug_trace"]["llm_invoked"])
        self.assertIn("error", result["planner_debug_trace"])
        self.assertEqual(trace["calculation_plan"]["status"], "incomplete")
        self.assertEqual(trace["calculation_plan"]["operation"], "none")
        self.assertEqual(trace["calculation_result"], {})
        self.assertNotIn("calculation_plan", result)
        self.assertNotIn("calculation_result", result)

    def test_llm_formula_plan_guard_omits_compatibility_mirrors(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            CalculationPlan(
                status="ok",
                mode="single_value",
                operation="ratio",
                ordered_operand_ids=["op_001"],
                variable_bindings=[
                    {"variable": "A", "operand_id": "op_001"},
                    {"variable": "B", "operand_id": "op_001"},
                ],
                formula="A / B",
                result_unit="ratio",
            )
        )
        result = agent._plan_formula_calculation(
            {
                "query": "calculate a ratio",
                "active_subtask": {
                    "task_id": "task_1",
                    "metric_family": "generic_numeric",
                    "metric_label": "ratio",
                    "operation_family": "",
                    "required_operands": [
                        {"label": "first value", "role": "numerator", "required": True},
                        {"label": "second value", "role": "denominator", "required": True},
                    ],
                },
                "structured_result": {},
                "resolved_calculation_trace": {
                    "calculation_operands": [
                        {
                            "operand_id": "op_001",
                            "label": "shared value",
                            "raw_value": "100",
                            "normalized_value": 100.0,
                            "matched_operand_role": "numerator",
                        }
                    ],
                    "calculation_plan": {},
                    "calculation_result": {},
                },
                "calculation_operands": [{"operand_id": "legacy"}],
                "calculation_plan": {},
                "calculation_result": {},
                "artifacts": [],
                "tasks": [],
            }
        )

        trace = _resolve_runtime_calculation_trace(result)
        self.assertTrue(result["planner_debug_trace"]["llm_invoked"])
        self.assertTrue(result["planner_debug_trace"]["guard_applied"])
        self.assertEqual(result["planner_debug_trace"]["reason"], "invalid_required_operand_bindings")
        self.assertEqual(trace["calculation_plan"]["status"], "incomplete")
        self.assertIn("denominator", trace["calculation_plan"]["missing_info"])
        self.assertEqual(trace["calculation_result"], {})
        self.assertNotIn("calculation_plan", result)
        self.assertNotIn("calculation_result", result)

    def test_operand_extraction_structured_output_failure_omits_compatibility_mirrors(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _FailingLLM()
        result = agent._extract_calculation_operands(
            {
                "query": "calculate the value",
                "active_subtask": {
                    "task_id": "task_1",
                    "metric_family": "generic_numeric",
                    "metric_label": "value",
                    "operation_family": "generic_numeric",
                },
                "resolved_calculation_trace": {},
                "structured_result": {},
                "evidence_items": [
                    {
                        "evidence_id": "ev_001",
                        "claim": "value is 100",
                        "quote_span": "100",
                        "source_anchor": "[fixture]",
                    }
                ],
                "evidence_bullets": ["- [fixture] value is 100"],
                "retrieved_docs": [],
                "seed_retrieved_docs": [],
                "calculation_operands": [{"operand_id": "stale"}],
                "calculation_plan": {"status": "stale"},
                "calculation_result": {"status": "stale"},
                "artifacts": [],
                "tasks": [],
            }
        )

        trace = _resolve_runtime_calculation_trace(result)
        self.assertEqual(result["evidence_status"], "missing")
        self.assertIn("error", result["calculation_debug_trace"])
        self.assertEqual(trace["calculation_operands"], [])
        self.assertEqual(trace["calculation_plan"], {})
        self.assertEqual(trace["calculation_result"], {})
        self.assertNotIn("calculation_operands", result)
        self.assertNotIn("calculation_plan", result)
        self.assertNotIn("calculation_result", result)

    def test_difference_task_uses_deterministic_subtract_plan(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._plan_formula_calculation(
            _with_runtime_calculation_trace(
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
        )
        trace = _resolve_runtime_calculation_trace(result)
        plan = trace["calculation_plan"]
        self.assertEqual(plan["status"], "ok")
        self.assertEqual(plan["operation"], "subtract")
        self.assertEqual(plan["formula"], "A + B")
        self.assertEqual(plan["ordered_operand_ids"], ["op_001", "op_002"])

    def test_ontology_difference_roles_use_sign_aware_subtraction(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = agent._plan_formula_calculation(
            _with_runtime_calculation_trace(
            {
                "query": "2023년 잉여현금흐름(FCF)을 영업활동현금흐름에서 유형자산 취득액을 차감하여 계산해 줘.",
                "active_subtask": {
                    "task_id": "task_fcf",
                    "metric_family": "free_cash_flow",
                    "metric_label": "잉여현금흐름",
                    "operation_family": "difference",
                    "required_operands": [
                        {"label": "영업활동현금흐름", "role": "numerator", "required": True},
                        {"label": "유형자산의 취득", "role": "denominator", "required": True},
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
                        "matched_operand_role": "numerator",
                    },
                    {
                        "operand_id": "op_002",
                        "label": "2023 유형자산의 취득",
                        "raw_value": "(640,623,697,250)",
                        "raw_unit": "원",
                        "normalized_value": -640623697250.0,
                        "normalized_unit": "KRW",
                        "matched_operand_role": "denominator",
                    },
                ],
                "artifacts": [],
                "tasks": [],
            }
            )
        )
        trace = _resolve_runtime_calculation_trace(result)
        plan = trace["calculation_plan"]
        self.assertEqual(plan["status"], "ok")
        self.assertEqual(plan["operation"], "subtract")
        self.assertEqual(plan["formula"], "A + B")
        self.assertEqual(plan["ordered_operand_ids"], ["op_001", "op_002"])

    def test_roe_ontology_ratio_uses_average_current_and_prior_equity_denominator(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ontology = FinancialOntologyManager(Path("src/config/financial_ontology.json"))
        required_operands = ontology.build_operand_spec("roe")
        state = {
            "query": "2023년 연결기준 자기자본이익률(ROE)을 계산해 줘. (당기순이익 / 평균 자본총계)",
            "active_subtask": {
                "task_id": "task_roe",
                "metric_family": "roe",
                "metric_label": "자기자본이익률",
                "operation_family": "ratio",
                "required_operands": required_operands,
            },
            "calculation_operands": [
                {
                    "operand_id": "op_income",
                    "evidence_id": "row_income",
                    "label": "2023년 연결총당기순이익",
                    "matched_operand_label": "당기순이익",
                    "matched_operand_concept": "net_income",
                    "matched_operand_role": "numerator",
                    "raw_value": "15,487,100",
                    "raw_unit": "백만원",
                    "normalized_value": 15487100000000.0,
                    "normalized_unit": "KRW",
                    "period": "2023",
                },
                {
                    "operand_id": "op_equity_current",
                    "evidence_id": "row_equity_current",
                    "label": "2023년 자본총계",
                    "matched_operand_label": "자본총계",
                    "matched_operand_concept": "total_equity",
                    "matched_operand_role": "denominator_1",
                    "raw_value": "363,677,865",
                    "raw_unit": "백만원",
                    "normalized_value": 363677865000000.0,
                    "normalized_unit": "KRW",
                    "period": "2023",
                },
                {
                    "operand_id": "op_equity_prior",
                    "evidence_id": "row_equity_prior",
                    "label": "2022년 자본총계",
                    "matched_operand_label": "자본총계",
                    "matched_operand_concept": "total_equity",
                    "matched_operand_role": "denominator_2",
                    "raw_value": "354,749,604",
                    "raw_unit": "백만원",
                    "normalized_value": 354749604000000.0,
                    "normalized_unit": "KRW",
                    "period": "2022",
                },
            ],
            "artifacts": [],
            "tasks": [],
        }

        plan_result = agent._plan_formula_calculation(_with_runtime_calculation_trace(state))
        plan_trace = _resolve_runtime_calculation_trace(plan_result)
        plan = plan_trace["calculation_plan"]
        self.assertEqual(plan["status"], "ok")
        self.assertEqual(plan["operation"], "ratio")
        self.assertEqual(plan["ordered_operand_ids"], ["op_income", "op_equity_current", "op_equity_prior"])
        self.assertEqual(plan["formula"], "((A) / (((B + C) / 2))) * 100")

        execution_result = _execute_calculation_with_runtime_trace(agent, {**state, **plan_result})
        trace = _resolve_runtime_calculation_trace(execution_result)
        calc = trace["calculation_result"]
        self.assertEqual(calc["status"], "ok")
        self.assertAlmostEqual(calc["result_value"], 4.3113887664, places=6)
        self.assertEqual(calc["rendered_value"], "4.31%")
        self.assertEqual(len(calc["series"]), 3)

    def test_operating_margin_drag_ratio_renders_percent_point(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ontology = FinancialOntologyManager(Path("src/config/financial_ontology.json"))
        required_operands = ontology.build_operand_spec("operating_margin_drag")
        state = {
            "query": "무형자산상각비가 영업이익률을 얼마나 낮추었는지(%p) 추정해 줘.",
            "active_subtask": {
                "task_id": "task_margin_drag",
                "metric_family": "operating_margin_drag",
                "metric_label": "영업이익률 감소 영향",
                "operation_family": "ratio",
                "required_operands": required_operands,
            },
            "calculation_operands": [
                {
                    "operand_id": "op_amortization",
                    "evidence_id": "row_amortization",
                    "label": "무형자산상각비",
                    "matched_operand_label": "무형자산상각비",
                    "matched_operand_concept": "amortization_expense",
                    "matched_operand_role": "numerator",
                    "raw_value": "182,049,824",
                    "raw_unit": "천원",
                    "normalized_value": 182049824000.0,
                    "normalized_unit": "KRW",
                    "period": "2023",
                },
                {
                    "operand_id": "op_revenue",
                    "evidence_id": "row_revenue",
                    "label": "매출액",
                    "matched_operand_label": "매출액",
                    "matched_operand_concept": "revenue",
                    "matched_operand_role": "denominator",
                    "raw_value": "2,176,431,531",
                    "raw_unit": "천원",
                    "normalized_value": 2176431531000.0,
                    "normalized_unit": "KRW",
                    "period": "2023",
                },
            ],
            "artifacts": [],
            "tasks": [],
        }

        plan_result = agent._plan_formula_calculation(_with_runtime_calculation_trace(state))
        plan = _resolve_runtime_calculation_trace(plan_result)["calculation_plan"]
        self.assertEqual(plan["status"], "ok")
        self.assertEqual(plan["formula"], "((A) / (B)) * 100")
        self.assertEqual(plan["result_unit"], "%p")

        execution_result = _execute_calculation_with_runtime_trace(agent, {**state, **plan_result})
        calc = _resolve_runtime_calculation_trace(execution_result)["calculation_result"]
        self.assertEqual(calc["status"], "ok")
        self.assertAlmostEqual(calc["result_value"], 8.3646014776, places=6)
        self.assertEqual(calc["rendered_value"], "8.36%p")

    def test_ratio_recomputes_operand_scale_from_source_visible_rendered_unit(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ontology = FinancialOntologyManager(Path("src/config/financial_ontology.json"))
        required_operands = ontology.build_operand_spec("operating_margin_drag")
        state = {
            "query": "무형자산상각비가 영업이익률을 얼마나 낮추었는지(%p) 추정해 줘.",
            "active_subtask": {
                "task_id": "task_margin_drag",
                "metric_family": "operating_margin_drag",
                "metric_label": "영업이익률 감소 영향",
                "operation_family": "ratio",
                "required_operands": required_operands,
            },
            "calculation_operands": [
                {
                    "operand_id": "op_amortization",
                    "evidence_id": "row_amortization",
                    "label": "무형자산상각비",
                    "matched_operand_label": "무형자산상각비",
                    "matched_operand_concept": "amortization_expense",
                    "matched_operand_role": "numerator",
                    "raw_value": "182,049,824",
                    "raw_unit": "원",
                    "normalized_value": 182049824.0,
                    "normalized_unit": "KRW",
                    "rendered_value": "182,049,824천원",
                    "period": "2023",
                },
                {
                    "operand_id": "op_revenue",
                    "evidence_id": "row_revenue",
                    "label": "매출액",
                    "matched_operand_label": "매출액",
                    "matched_operand_concept": "revenue",
                    "matched_operand_role": "denominator",
                    "raw_value": "2,176,431,531,380",
                    "raw_unit": "원",
                    "normalized_value": 2176431531380.0,
                    "normalized_unit": "KRW",
                    "rendered_value": "2,176,431,531,380원",
                    "period": "2023",
                },
            ],
            "artifacts": [],
            "tasks": [],
        }

        plan_result = agent._plan_formula_calculation(_with_runtime_calculation_trace(state))
        execution_result = _execute_calculation_with_runtime_trace(agent, {**state, **plan_result})
        trace = _resolve_runtime_calculation_trace(execution_result)
        calc = trace["calculation_result"]
        self.assertEqual(calc["status"], "ok")
        self.assertAlmostEqual(calc["result_value"], 8.364601478, places=6)
        self.assertEqual(calc["rendered_value"], "8.36%p")
        repaired_operand = next(row for row in trace["calculation_operands"] if row["operand_id"] == "op_amortization")
        self.assertEqual(repaired_operand["raw_unit"], "천원")
        self.assertEqual(repaired_operand["normalized_value"], 182049824000.0)
        self.assertTrue(repaired_operand["unit_repaired_from_rendered_value"])

    def test_ratio_recomputes_operand_scale_from_embedded_raw_unit(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ontology = FinancialOntologyManager(Path("src/config/financial_ontology.json"))
        required_operands = ontology.build_operand_spec("operating_margin_drag")
        state = {
            "query": "무형자산상각비가 영업이익률을 얼마나 낮추었는지(%p) 추정해 줘.",
            "active_subtask": {
                "task_id": "task_margin_drag",
                "metric_family": "operating_margin_drag",
                "metric_label": "영업이익률 감소 영향",
                "operation_family": "ratio",
                "required_operands": required_operands,
            },
            "calculation_operands": [
                {
                    "operand_id": "op_amortization",
                    "evidence_id": "task_output:amortization",
                    "label": "무형자산상각비",
                    "matched_operand_label": "무형자산상각비",
                    "matched_operand_concept": "amortization_expense",
                    "matched_operand_role": "numerator",
                    "raw_value": "182,049,824천원",
                    "raw_unit": "천원",
                    "normalized_value": 182049824.0,
                    "normalized_unit": "KRW",
                    "rendered_value": "182,049,824천원",
                    "period": "2023",
                },
                {
                    "operand_id": "op_revenue",
                    "evidence_id": "row_revenue",
                    "label": "매출액",
                    "matched_operand_label": "매출액",
                    "matched_operand_concept": "revenue",
                    "matched_operand_role": "denominator",
                    "raw_value": "2,176,431,531,380",
                    "raw_unit": "원",
                    "normalized_value": 2176431531380.0,
                    "normalized_unit": "KRW",
                    "rendered_value": "2,176,431,531,380원",
                    "period": "2023",
                },
            ],
            "artifacts": [],
            "tasks": [],
        }

        plan_result = agent._plan_formula_calculation(_with_runtime_calculation_trace(state))
        execution_result = _execute_calculation_with_runtime_trace(agent, {**state, **plan_result})
        trace = _resolve_runtime_calculation_trace(execution_result)
        calc = trace["calculation_result"]
        self.assertEqual(calc["status"], "ok")
        self.assertAlmostEqual(calc["result_value"], 8.364601478, places=6)
        self.assertEqual(calc["rendered_value"], "8.36%p")
        repaired_operand = next(row for row in trace["calculation_operands"] if row["operand_id"] == "op_amortization")
        self.assertEqual(repaired_operand["raw_unit"], "천원")
        self.assertEqual(repaired_operand["normalized_value"], 182049824000.0)

    def test_ratio_rejects_implausible_same_unit_krw_percent_result(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ontology = FinancialOntologyManager(Path("src/config/financial_ontology.json"))
        required_operands = ontology.build_operand_spec("operating_margin_drag")
        state = {
            "query": "무형자산상각비가 영업이익률을 얼마나 낮추었는지(%p) 추정해 줘.",
            "active_subtask": {
                "task_id": "task_margin_drag",
                "metric_family": "operating_margin_drag",
                "metric_label": "영업이익률 감소 영향",
                "operation_family": "ratio",
                "required_operands": required_operands,
            },
            "calculation_operands": [
                {
                    "operand_id": "op_amortization",
                    "evidence_id": "row_amortization",
                    "label": "무형자산상각비",
                    "matched_operand_label": "무형자산상각비",
                    "matched_operand_concept": "amortization_expense",
                    "matched_operand_role": "numerator",
                    "raw_value": "3,952,108,690,000,000,000",
                    "raw_unit": "원",
                    "normalized_value": 3.95210869e18,
                    "normalized_unit": "KRW",
                    "period": "2023",
                },
                {
                    "operand_id": "op_revenue",
                    "evidence_id": "row_revenue",
                    "label": "매출액",
                    "matched_operand_label": "매출액",
                    "matched_operand_concept": "revenue",
                    "matched_operand_role": "denominator",
                    "raw_value": "2,176,431,531,380",
                    "raw_unit": "원",
                    "normalized_value": 2176431531380.0,
                    "normalized_unit": "KRW",
                    "period": "2023",
                },
            ],
            "artifacts": [],
            "tasks": [],
        }

        plan_result = agent._plan_formula_calculation(_with_runtime_calculation_trace(state))
        execution_result = _execute_calculation_with_runtime_trace(agent, {**state, **plan_result})
        calc = _resolve_runtime_calculation_trace(execution_result)["calculation_result"]
        self.assertEqual(calc["status"], "scale_mismatch")
        self.assertEqual(calc["rendered_value"], "")

    def test_dependency_aggregate_policy_blocks_detail_context_replacement(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "dependency_resolved": True,
            "source_task_id": "task_revenue",
            "evidence_id": "task_output:task_revenue",
            "source_row_ids": ["task_output:task_revenue", "summary_total_value"],
            "matched_operand_label": "매출액",
            "matched_operand_role": "denominator",
            "raw_value": "2,176,431,531",
            "normalized_value": 2176431531000.0,
            "aggregation_stage": "final",
            "binding_policy": {"prefer_aggregation_stages": ["final", "subtotal"]},
        }
        replacement = {
            "evidence_id": "segment_detail_value",
            "source_row_ids": ["segment_detail_value", "summary_total_value"],
            "matched_operand_label": "매출액",
            "matched_operand_role": "denominator",
            "raw_value": "1,873,430,064",
            "normalized_value": 1873430064000.0,
            "value_role": "detail",
            "aggregation_stage": "none",
        }

        self.assertTrue(agent._task_output_operand_row_should_keep_value(row, replacement))

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
        result = _execute_calculation_with_runtime_trace(agent,
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
        trace = _resolve_runtime_calculation_trace(result)
        slots = trace["calculation_result"]["answer_slots"]
        self.assertEqual(slots["primary_value"]["role"], "primary_value")
        self.assertEqual(slots["current_value"]["rendered_value"], "2조 22억원")
        self.assertEqual(slots["prior_value"]["rendered_value"], "-6,406억원")
        self.assertEqual(slots["delta_value"]["rendered_value"], "1조 3,616억원")
        self.assertNotIn("calculation_result", result)

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

        state["resolved_calculation_trace"] = {
            key: state.pop(key)
            for key in ("calculation_plan", "calculation_operands", "calculation_result")
        }

        rendered = agent._render_calculation_answer(state)

        self.assertIn("6,406억원을 차감", rendered["answer"])
        self.assertNotIn("-6,406억원을 차감", rendered["answer"])

    def test_rendered_subtraction_answer_rewrites_negative_denominator_difference(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        answer = "네이버의 2023년 연결기준 영업활동현금흐름은 2조 22억원이며, 유형자산의 취득 금액은 -6,406억원입니다. 이를 바탕으로 계산된 2023년 잉여현금흐름은 1조 3,616억원입니다."
        rewritten = agent._coerce_sign_aware_subtraction_answer(
            answer,
            calculation_result={
                "status": "ok",
                "answer_slots": {
                    "operation_family": "difference",
                    "components_by_role": {
                        "denominator": [
                            {
                                "status": "ok",
                                "role": "denominator",
                                "label": "2023 유형자산의 취득",
                                "rendered_value": "-6,406억원",
                            }
                        ]
                    },
                },
            },
        )

        self.assertIn("유형자산의 취득 금액은 6,406억원", rewritten)
        self.assertNotIn("-6,406억원", rewritten)

    def test_difference_result_exposes_structured_value_slots(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = _execute_calculation_with_runtime_trace(agent,
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
        trace = _resolve_runtime_calculation_trace(result)
        calc = trace["calculation_result"]
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
        result = _execute_calculation_with_runtime_trace(agent,
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
        trace = _resolve_runtime_calculation_trace(result)
        calc = trace["calculation_result"]
        self.assertEqual(calc["status"], "ok")
        self.assertEqual(calc["rendered_value"], "0.10%p")
        self.assertEqual(calc["answer_slots"]["primary_value"]["status"], "ok")
        self.assertEqual(calc["answer_slots"]["current_value"]["rendered_value"], "1.83%")
        self.assertEqual(calc["answer_slots"]["prior_value"]["rendered_value"], "1.73%")
        self.assertEqual(calc["answer_slots"]["delta_value"]["rendered_value"], "0.10%p")

    def test_growth_rate_coerces_unknown_prior_unit_from_same_concept_current_row(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = _execute_calculation_with_runtime_trace(agent,
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
        trace = _resolve_runtime_calculation_trace(result)
        calc = trace["calculation_result"]
        self.assertEqual(calc["status"], "ok")
        self.assertEqual(calc["answer_slots"]["prior_value"]["normalized_unit"], "KRW")
        self.assertEqual(calc["answer_slots"]["prior_value"]["raw_unit"], "억원")
        self.assertEqual(calc["rendered_value"], "-0.0026%")
        trace_operands = list(trace.get("calculation_operands") or [])
        prior_operand = next(row for row in trace_operands if row.get("operand_id") == "op_002")
        self.assertEqual(prior_operand["normalized_unit"], "KRW")
        self.assertEqual(prior_operand["raw_unit"], "억원")

    def test_growth_rate_preserves_stated_source_percent_when_available(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = _execute_calculation_with_runtime_trace(agent,
            {
                "query": "2023년 지역 시장 판매대수의 전년 대비 성장률을 계산해 줘.",
                "active_subtask": {
                    "task_id": "task_count_growth",
                    "metric_family": "generic_numeric",
                    "metric_label": "지역 시장 판매대수",
                    "operation_family": "growth_rate",
                },
                "calculation_operands": [
                    {
                        "operand_id": "op_001",
                        "evidence_id": "sales_2023",
                        "label": "2023 지역 시장 판매대수",
                        "raw_value": "87.0",
                        "raw_unit": "만 대",
                        "normalized_value": 870000.0,
                        "normalized_unit": "COUNT",
                        "period": "2023년",
                        "matched_operand_role": "current_period",
                        "stated_change_raw_value": "11.5",
                        "stated_change_raw_unit": "%",
                    },
                    {
                        "operand_id": "op_002",
                        "evidence_id": "sales_2023",
                        "label": "2022 지역 시장 판매대수",
                        "raw_value": "78.1",
                        "raw_unit": "만 대",
                        "normalized_value": 781000.0,
                        "normalized_unit": "COUNT",
                        "period": "2022년",
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
                    "result_unit": "%",
                },
                "artifacts": [],
                "tasks": [],
            }
        )

        trace = _resolve_runtime_calculation_trace(result)
        calc = trace["calculation_result"]
        self.assertEqual(calc["rendered_value"], "11.5%")
        self.assertEqual(calc["result_value"], 11.5)
        self.assertEqual(calc["answer_slots"]["current_value"]["rendered_value"], "87.0만 대")
        self.assertEqual(calc["answer_slots"]["prior_value"]["rendered_value"], "78.1만 대")
        self.assertEqual(
            calc["answer_slots"]["components_by_role"]["current_period"][0]["rendered_value"],
            "87.0만 대",
        )
        self.assertEqual(
            calc["answer_slots"]["components_by_role"]["prior_period"][0]["rendered_value"],
            "78.1만 대",
        )
        self.assertEqual(calc["derived_metrics"]["formula_result_value"], 11.395646606914212)
        self.assertTrue(calc["derived_metrics"]["source_stated_result_used"])

    def test_growth_rate_recovers_duplicate_prior_operand_from_evidence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = _execute_calculation_with_runtime_trace(agent,
            {
                "query": "2023년 지역 시장 판매대수의 전년 대비 성장률을 계산해 줘",
                "active_subtask": {
                    "task_id": "task_count_growth",
                    "metric_family": "generic_numeric",
                    "metric_label": "지역 시장 판매대수",
                    "operation_family": "growth_rate",
                },
                "calculation_operands": [
                    {
                        "operand_id": "op_001",
                        "evidence_id": "sales_2023",
                        "label": "2023 지역 시장 판매대수",
                        "raw_value": "87.0",
                        "raw_unit": "만 대",
                        "normalized_value": 870000.0,
                        "normalized_unit": "COUNT",
                        "period": "2023년",
                        "matched_operand_role": "current_period",
                        "stated_change_raw_value": "11.5",
                        "stated_change_raw_unit": "%",
                    },
                    {
                        "operand_id": "op_002",
                        "evidence_id": "sales_2023",
                        "label": "2022 지역 시장 판매대수",
                        "raw_value": "87.0",
                        "raw_unit": "만 대",
                        "normalized_value": 870000.0,
                        "normalized_unit": "COUNT",
                        "period": "2023년",
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
                    "result_unit": "%",
                },
                "evidence_items": [
                    {
                        "evidence_id": "sales_2022",
                        "claim": "2022년 지역 시장 판매대수는 78.1만 대였습니다.",
                        "quote_span": "2022년에는 전년 대비 0.9% 감소한 78.1만 대",
                    }
                ],
                "artifacts": [],
                "tasks": [],
            }
        )

        trace = _resolve_runtime_calculation_trace(result)
        calc = trace["calculation_result"]
        self.assertEqual(calc["answer_slots"]["prior_value"]["period"], "2022년")
        self.assertEqual(calc["answer_slots"]["prior_value"]["rendered_value"], "78.1만 대")
        self.assertEqual(calc["answer_slots"]["prior_value"]["normalized_value"], 781000.0)
        self.assertEqual(calc["derived_metrics"]["formula_result_value"], 11.395646606914212)

    def test_growth_rate_rejects_same_period_current_and_prior_operands(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = _execute_calculation_with_runtime_trace(agent,
            {
                "query": "2023년 target metric의 전년 대비 성장률을 계산해 줘",
                "active_subtask": {
                    "task_id": "task_growth",
                    "metric_family": "generic_numeric",
                    "metric_label": "target metric",
                    "operation_family": "growth_rate",
                },
                "calculation_operands": [
                    {
                        "operand_id": "op_current",
                        "evidence_id": "ev_current",
                        "label": "target metric",
                        "concept": "target_metric",
                        "raw_value": "3,146",
                        "raw_unit": "million",
                        "normalized_value": 3146000000.0,
                        "normalized_unit": "KRW",
                        "period": "2023",
                        "matched_operand_concept": "target_metric",
                        "matched_operand_role": "current_period",
                    },
                    {
                        "operand_id": "op_prior",
                        "evidence_id": "ev_prior_wrong_period",
                        "label": "target metric",
                        "concept": "target_metric",
                        "raw_value": "28",
                        "raw_unit": "million",
                        "normalized_value": 28000000.0,
                        "normalized_unit": "KRW",
                        "period": "2023",
                        "matched_operand_concept": "target_metric",
                        "matched_operand_role": "prior_period",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "growth_rate",
                    "ordered_operand_ids": ["op_current", "op_prior"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "op_current"},
                        {"variable": "B", "operand_id": "op_prior"},
                    ],
                    "formula": "((A - B) / B) * 100",
                    "result_unit": "%",
                },
                "artifacts": [],
                "tasks": [],
            }
        )

        trace = _resolve_runtime_calculation_trace(result)
        calc = trace["calculation_result"]
        self.assertEqual(calc["status"], "insufficient_operands")
        self.assertEqual(calc["rendered_value"], "")
        self.assertNotIn("11135", str(calc.get("result_value") or ""))

    def test_growth_answer_replaces_untraced_numeric_sentence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        growth_row = {
            "task_id": "task_growth",
            "metric_family": "concept_growth_rate",
            "metric_label": "서비스 매출 성장률",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "41.4%",
                "formatted_result": "41.4%",
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "primary_value": {
                        "status": "ok",
                        "role": "primary_value",
                        "label": "서비스 매출 성장률",
                        "period": "2023",
                        "raw_unit": "%",
                        "normalized_value": 41.4,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "41.4%",
                    },
                    "current_value": {
                        "status": "ok",
                        "role": "current_value",
                        "label": "서비스 매출액",
                        "period": "2023",
                        "raw_value": "2,546,649",
                        "raw_unit": "백만원",
                        "normalized_value": 2546649000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "2조 5,466억원",
                    },
                    "prior_value": {
                        "status": "ok",
                        "role": "prior_value",
                        "label": "서비스 매출액",
                        "period": "2022",
                        "raw_value": "1,801,079",
                        "raw_unit": "백만원",
                        "normalized_value": 1801079000000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "1조 8,011억원",
                    },
                },
            },
        }

        answer = agent._ensure_complete_growth_numeric_answer(
            (
                "2023년 서비스 매출액은 3,589,060,852천원이며, 2022년 2,546,648,516천원 대비 "
                "41.4% 성장했습니다. 2023년 서비스 매출액은 2조 5,466억원이며, "
                "2022년 서비스 매출액은 1조 8,011억원입니다. 주요 성장 요인은 근거 문장에 설명되어 있습니다."
            ),
            [growth_row],
        )

        self.assertIn("2조 5,466억원", answer)
        self.assertIn("1조 8,011억원", answer)
        self.assertIn("41.4%", answer)
        self.assertNotIn("3,589,060,852천원", answer)
        self.assertNotIn("2,546,648,516천원", answer)
        self.assertIn("주요 성장 요인", answer)

    def test_growth_slot_keeps_display_when_source_task_unit_conflicts(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        slot = {
            "status": "ok",
            "source_task_id": "task_prior",
            "source_slot": "primary_value",
            "raw_value": "1,801,079",
            "raw_unit": "백만원",
            "normalized_value": 1801079000000.0,
            "normalized_unit": "KRW",
            "rendered_value": "1조 8,011억원",
        }
        ordered_results = [
            {
                "task_id": "task_prior",
                "calculation_result": {
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "raw_value": "1,801,079",
                            "raw_unit": "천원",
                            "normalized_value": 1801079000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "1,801,079천원",
                        }
                    }
                },
            }
        ]

        self.assertEqual(
            agent._growth_slot_display_value(slot, ordered_results),
            "1조 8,011억원",
        )

    def test_growth_numeric_answer_uses_magnitude_for_parenthesized_currency_displays(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        growth_row = {
            "task_id": "task_growth",
            "operation_family": "growth_rate",
            "metric_label": "allowance expense",
            "status": "ok",
            "calculation_result": {
                "status": "ok",
                "rendered_value": "70.28%",
                "answer_slots": {
                    "operation_family": "growth_rate",
                    "metric_label": "allowance expense",
                    "primary_value": {
                        "status": "ok",
                        "role": "primary_value",
                        "label": "allowance expense",
                        "normalized_value": 70.28,
                        "normalized_unit": "PERCENT",
                        "rendered_value": "70.28%",
                        "direction": "increase",
                    },
                    "current_value": {
                        "status": "ok",
                        "role": "current_period",
                        "label": "allowance expense",
                        "period": "2023",
                        "raw_value": "(3,146,409)",
                        "raw_unit": "백만원",
                        "normalized_value": -3_146_409_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "(3,146,409)백만원",
                    },
                    "prior_value": {
                        "status": "ok",
                        "role": "prior_period",
                        "label": "allowance expense",
                        "period": "2022",
                        "raw_value": "(1,847,775)",
                        "raw_unit": "백만원",
                        "normalized_value": -1_847_775_000_000.0,
                        "normalized_unit": "KRW",
                        "rendered_value": "(1,847,775)백만원",
                    },
                },
            },
        }

        answer = agent._compose_complete_growth_numeric_answer(growth_row, [growth_row])

        self.assertIn("3,146,409백만원", answer)
        self.assertIn("1,847,775백만원", answer)
        self.assertNotIn("(3,146,409)백만원", answer)
        self.assertNotIn("(1,847,775)백만원", answer)

    def test_failed_lookup_emits_explicit_missing_primary_slot(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = _execute_calculation_with_runtime_trace(agent,
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
        trace = _resolve_runtime_calculation_trace(result)
        calc = trace["calculation_result"]
        self.assertEqual(calc["status"], "insufficient_operands")
        self.assertEqual(calc["answer_slots"]["operation_family"], "lookup")
        self.assertEqual(calc["answer_slots"]["primary_value"]["status"], "missing")
        self.assertEqual(calc["answer_slots"]["primary_value"]["label"], "법인세비용차감전순이익")
        self.assertEqual(calc["answer_slots"]["primary_value"]["concept"], "income_before_income_taxes")
        self.assertNotIn("calculation_result", result)

    def test_lookup_plan_requires_single_direct_operand_instead_of_reconstruction(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        plan_result = agent._plan_formula_calculation(
            _with_runtime_calculation_trace(
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
        )
        trace = _resolve_runtime_calculation_trace(plan_result)
        self.assertEqual(trace["calculation_plan"]["status"], "incomplete")
        self.assertEqual(trace["calculation_plan"]["mode"], "none")
        self.assertNotIn("calculation_plan", plan_result)
        self.assertNotIn("calculation_result", plan_result)
        self.assertFalse(plan_result["planner_debug_trace"]["llm_invoked"])
        self.assertTrue(plan_result["planner_debug_trace"]["guard_applied"])

    def test_lookup_plan_uses_single_direct_operand_when_available(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        plan_result = agent._plan_formula_calculation(
            _with_runtime_calculation_trace(
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
        )
        trace = _resolve_runtime_calculation_trace(plan_result)
        self.assertEqual(trace["calculation_plan"]["status"], "ok")
        self.assertEqual(trace["calculation_plan"]["operation"], "lookup")
        self.assertEqual(trace["calculation_plan"]["formula"], "A")
        self.assertFalse(plan_result["planner_debug_trace"]["llm_invoked"])

    def test_lookup_calculation_preserves_source_table_unit_in_rendered_value(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = _execute_calculation_with_runtime_trace(agent,
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

        trace = _resolve_runtime_calculation_trace(result)
        calculation_result = trace["calculation_result"]
        self.assertEqual(calculation_result["rendered_value"], "2,526,280천원")
        self.assertEqual(calculation_result["series"][0]["rendered_value"], "2,526,280천원")
        primary_value = calculation_result["answer_slots"]["primary_value"]
        self.assertEqual(primary_value["raw_value"], "2,526,280")
        self.assertEqual(primary_value["raw_unit"], "천원")
        self.assertEqual(primary_value["rendered_value"], "2,526,280천원")

    def test_ratio_calculation_rejects_duplicate_operand_binding(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        result = _execute_calculation_with_runtime_trace(agent,
            {
                "query": "Calculate the ratio between two required values.",
                "active_subtask": {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "metric_label": "required ratio",
                    "operation_family": "ratio",
                    "required_operands": [
                        {
                            "label": "numerator value",
                            "concept": "numerator_value",
                            "role": "numerator_1",
                            "required": True,
                        },
                        {
                            "label": "denominator value",
                            "concept": "denominator_value",
                            "role": "denominator_1",
                            "required": True,
                        },
                    ],
                },
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "ratio",
                    "ordered_operand_ids": ["op_001", "op_001"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "op_001"},
                        {"variable": "B", "operand_id": "op_001"},
                    ],
                    "formula": "(A / B) * 100",
                    "result_unit": "%",
                },
                "calculation_operands": [
                    {
                        "operand_id": "op_001",
                        "evidence_id": "row_001",
                        "label": "numerator value",
                        "matched_operand_label": "numerator value",
                        "matched_operand_concept": "numerator_value",
                        "matched_operand_role": "numerator_1",
                        "raw_value": "250",
                        "raw_unit": "",
                        "normalized_value": 250.0,
                        "normalized_unit": "COUNT",
                        "period": "2023",
                    }
                ],
                "artifacts": [],
                "tasks": [],
            }
        )

        trace = _resolve_runtime_calculation_trace(result)
        self.assertEqual(trace["calculation_result"]["status"], "insufficient_operands")
        self.assertEqual(trace["calculation_plan"]["status"], "incomplete")
        self.assertEqual(trace["calculation_plan"]["mode"], "none")
        self.assertIn("denominator", trace["calculation_plan"]["missing_info"])
        self.assertNotIn("calculation_result", result)
        self.assertNotIn("calculation_plan", result)

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

    def test_narrative_policy_supplements_realized_metric_evidence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StubLLM(
            EvidenceExtraction(
                coverage="sufficient",
                evidence=[
                    {
                        "source_anchor": "[KB금융 | 2023 | II. 사업의 내용 > 2. 영업의 현황]",
                        "claim": "WM/연금부문은 자산관리 적립금 40조원을 돌파했습니다.",
                        "quote_span": "자산관리 적립금 40조원을 돌파",
                        "support_level": "direct",
                        "question_relevance": "high",
                        "allowed_terms": ["WM", "자산관리"],
                    }
                ],
            )
        )
        state = {
            "query": "2023년 순수수료이익 증가율을 계산하고, 자산관리(WM) 부문의 성과를 요약해 줘.",
            "query_type": "comparison",
            "topic": "순수수료이익 증가율 및 자산관리 성과",
            "retrieved_docs": [
                (
                    Document(
                        page_content="WM/연금부문은 퇴직연금 사업자 중 최초로 자산관리 적립금 40조원을 돌파했습니다.",
                        metadata={
                            "company": "KB금융",
                            "year": 2023,
                            "section_path": "II. 사업의 내용 > 2. 영업의 현황",
                            "block_type": "paragraph",
                        },
                    ),
                    0.98,
                ),
                (
                    Document(
                        page_content=(
                            "2023년말 그룹의 총관리자산은 1,216.7조원으로 2022년말 대비 "
                            "70.0조원(6.1%) 증가하였습니다. 이는 은행(+15.6조원), "
                            "증권(+35.6조), 자산운용(+6.8조원), 부동산신탁(+4.1조원) 등 "
                            "자산이 성장한 영향입니다."
                        ),
                        metadata={
                            "company": "KB금융",
                            "year": 2023,
                            "section_path": "II. 사업의 내용 > 5. 재무건전성 등 기타 참고사항",
                            "block_type": "paragraph",
                        },
                    ),
                    0.82,
                ),
            ],
            "active_subtask": {
                "task_id": "task_narrative",
                "metric_family": "narrative_summary",
                "metric_label": "자산관리 성과 요약",
                "operation_family": "narrative_summary",
            },
        }

        result = agent._extract_evidence(state)
        claims = " ".join(str(item.get("claim") or "") for item in result["evidence_items"])

        self.assertEqual(result["evidence_status"], "sufficient")
        self.assertIn("총관리자산", claims)
        self.assertIn("1,216.7조원", claims)
        self.assertIn("70.0조원", claims)

    def test_narrative_policy_supplement_requires_policy_realized_terms(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence_items = [
            {
                "source_anchor": "[KB금융 | 2023 | II. 사업의 내용]",
                "claim": "KB자산운용의 관리자산은 132.3조원으로 전년 대비 증가했습니다.",
                "quote_span": "KB자산운용의 관리자산은 132.3조원",
                "support_level": "direct",
                "question_relevance": "high",
            }
        ]
        docs = [
            (
                Document(
                    page_content="KB자산운용의 관리자산은 132.3조원으로 전년 대비 증가했습니다.",
                    metadata={
                        "chunk_id": "weak-manager-assets",
                        "block_type": "paragraph",
                        "section_path": "II. 사업의 내용 > 영업의 현황",
                    },
                ),
                0.95,
            ),
            (
                Document(
                    page_content=(
                        "계열사별 총관리자산(AUM) 현황\n"
                        "총관리자산(AUM) 주1) | 1,216,729 | 70,039 | 1,146,691"
                    ),
                    metadata={
                        "chunk_id": "group-aum",
                        "block_type": "table",
                        "section_path": "II. 사업의 내용 > 5. 재무건전성 등 기타 참고사항",
                        "table_context": "* 계열사별 총관리자산(AUM) 현황",
                        "table_value_labels_text": (
                            "총관리자산(AUM) 주1) 1,216,729 "
                            "총관리자산(AUM) 주1) 70,039 "
                            "총관리자산(AUM) 주1) 1,146,691"
                        ),
                        "period_focus": "current",
                        "unit_hint": "억원",
                    },
                ),
                0.40,
            ),
        ]

        supplemented = agent._supplement_policy_realized_evidence(
            evidence_items,
            docs,
            query="2023년 순수수료이익 증가율을 계산하고, 자산관리(WM) 부문의 성과를 요약해 줘.",
            anchor_lookup={},
        )
        claims = " ".join(str(item.get("claim") or "") for item in supplemented)

        self.assertGreater(len(supplemented), len(evidence_items))
        self.assertIn("총관리자산(AUM)", claims)
        self.assertIn("1,216,729", claims)

    def test_exclusive_narrative_policy_supplements_refusal_support_evidence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        docs = [
            (
                Document(
                    page_content=(
                        "1. 예측정보에 대한 주의사항 이 사업보고서에는 미래 활동, 사건 또는 현상에 "
                        "대한 예측정보가 포함되어 있으며 다양한 가정과 불확실성으로 실제 결과와 "
                        "차이가 발생할 수 있습니다."
                    ),
                    metadata={
                        "company": "ExampleCo",
                        "year": 2023,
                        "section_path": "IV. 이사의 경영진단 및 분석의견 > 예측정보에 대한 주의사항",
                        "block_type": "paragraph",
                    },
                ),
                0.7,
            )
        ]

        supplemented = agent._supplement_policy_realized_evidence(
            [],
            docs,
            query="2026년 1분기 예상 영업이익과 전기차 판매량을 예측해 줘.",
            anchor_lookup={},
        )
        claims = " ".join(str(item.get("claim") or "") for item in supplemented)

        self.assertTrue(supplemented)
        self.assertIn("예측정보", claims)
        self.assertIn("불확실성", claims)

    def test_missing_exclusive_narrative_preserves_query_focus_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        existing_evidence = [
            {
                "evidence_id": "ev_001",
                "source_anchor": "[ExampleCo | 2023 | IV. 이사의 경영진단 및 분석의견]",
                "claim": "본 자료는 미래에 대한 예측정보를 포함하고 있습니다.",
                "quote_span": "본 자료는 미래에 대한 예측정보를 포함하고 있습니다.",
                "support_level": "direct",
                "question_relevance": "high",
            }
        ]
        docs = [
            (
                Document(
                    page_content="미래 활동에 대한 예측정보는 다양한 불확실성으로 실제 결과와 다를 수 있습니다.",
                    metadata={
                        "company": "ExampleCo",
                        "year": 2023,
                        "section_path": "IV. 이사의 경영진단 및 분석의견",
                        "block_type": "paragraph",
                    },
                ),
                0.95,
            ),
            (
                Document(
                    page_content=(
                        "전기차 사업은 배터리 효율 개선과 충전 인프라 확대를 중심으로 진행되고 "
                        "있으며, 전기차 판매량 관련 시장 수요를 지속적으로 점검하고 있습니다."
                    ),
                    metadata={
                        "company": "ExampleCo",
                        "year": 2023,
                        "section_path": "II. 사업의 내용 > 사업의 개요",
                        "block_type": "paragraph",
                    },
                ),
                0.80,
            ),
        ]

        supplemented = agent._supplement_missing_focus_context_evidence(
            existing_evidence,
            docs,
            query="2026년 예상 전기차 판매량을 알려줘.",
            anchor_lookup={},
            coverage="missing",
        )
        claims = " ".join(str(item.get("claim") or "") for item in supplemented)

        self.assertGreater(len(supplemented), len(existing_evidence))
        self.assertIn("전기차 사업", claims)
        self.assertIn("전기차 판매량", claims)
        self.assertEqual(supplemented[-1]["support_level"], "context")

    def test_missing_focus_context_supplement_only_runs_for_missing_coverage(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        docs = [
            (
                Document(
                    page_content="전기차 사업은 전기차 판매량 관련 시장 수요를 지속적으로 점검하고 있습니다.",
                    metadata={
                        "company": "ExampleCo",
                        "year": 2023,
                        "section_path": "II. 사업의 내용 > 사업의 개요",
                        "block_type": "paragraph",
                    },
                ),
                0.80,
            )
        ]

        supplemented = agent._supplement_missing_focus_context_evidence(
            [],
            docs,
            query="2026년 예상 전기차 판매량을 알려줘.",
            anchor_lookup={},
            coverage="sufficient",
        )

        self.assertEqual(supplemented, [])

    def test_missing_focus_context_requires_specific_marker_pair(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        docs = [
            (
                Document(
                    page_content="기존 생산라인은 수율 향상이 예상되어 원가 효율화에 기여할 수 있습니다.",
                    metadata={
                        "company": "ExampleCo",
                        "year": 2023,
                        "section_path": "II. 사업의 내용 > 사업의 개요",
                        "block_type": "paragraph",
                    },
                ),
                0.80,
            )
        ]

        supplemented = agent._supplement_missing_focus_context_evidence(
            [],
            docs,
            query="2026년 파운드리 3나노 공정의 예상 수율을 알려줘.",
            anchor_lookup={},
            coverage="missing",
        )

        self.assertEqual(supplemented, [])

    def test_missing_decision_context_preserves_search_scope_for_unanswered_lookup(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        docs = [
            (
                Document(
                    page_content="Target capacity is discussed qualitatively, but no 2026 numeric forecast is stated.",
                    metadata={
                        "company": "ExampleCo",
                        "year": 2023,
                        "section_path": "II. Business Overview",
                        "block_type": "paragraph",
                    },
                ),
                0.82,
            )
        ]

        evidence_items, selected_ids = agent._append_missing_decision_context_evidence(
            [],
            final_answer="질문에 필요한 값을 충분히 확보하지 못했습니다.",
            selected_claim_ids=[],
            query="Find the 2026 target capacity numeric forecast.",
            docs=docs,
        )

        self.assertEqual(selected_ids, ["missing_decision_context::001"])
        self.assertEqual(evidence_items[-1]["support_level"], "context")
        self.assertEqual(evidence_items[-1]["metadata"]["missing_decision_context"], True)
        self.assertIn("Target capacity", evidence_items[-1]["quote_span"])

    def test_missing_decision_context_does_not_add_when_selected_evidence_covers_focus(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        docs = [
            (
                Document(
                    page_content="Target capacity is discussed qualitatively.",
                    metadata={"company": "ExampleCo", "year": 2023},
                ),
                0.82,
            )
        ]

        evidence_items, selected_ids = agent._append_missing_decision_context_evidence(
            [
                {
                    "evidence_id": "ev_001",
                    "claim": "Target capacity is discussed qualitatively.",
                    "quote_span": "Target capacity is discussed qualitatively.",
                }
            ],
            final_answer="질문에 필요한 값을 충분히 확보하지 못했습니다.",
            selected_claim_ids=["ev_001"],
            query="Find the 2026 target capacity numeric forecast.",
            docs=docs,
        )

        self.assertEqual(selected_ids, [])
        self.assertEqual([item["evidence_id"] for item in evidence_items], ["ev_001"])

    def test_missing_decision_context_adds_focus_context_when_selected_evidence_is_generic(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        docs = [
            (
                Document(
                    page_content="Forward-looking statements include uncertainty and may differ from actual results.",
                    metadata={"company": "ExampleCo", "year": 2023, "section_path": "Forward-looking caution"},
                ),
                0.95,
            ),
            (
                Document(
                    page_content="Target capacity is discussed qualitatively, but no 2026 numeric forecast is stated.",
                    metadata={"company": "ExampleCo", "year": 2023, "section_path": "Business Overview"},
                ),
                0.82,
            ),
        ]

        evidence_items, selected_ids = agent._append_missing_decision_context_evidence(
            [
                {
                    "evidence_id": "ev_001",
                    "claim": "Forward-looking statements include uncertainty.",
                    "quote_span": "Forward-looking statements include uncertainty.",
                }
            ],
            final_answer="질문에 필요한 값을 충분히 확보하지 못했습니다.",
            selected_claim_ids=["ev_001"],
            query="Find the 2026 target capacity numeric forecast.",
            docs=docs,
        )

        self.assertEqual(selected_ids, ["missing_decision_context::001"])
        self.assertEqual([item["evidence_id"] for item in evidence_items], ["ev_001", "missing_decision_context::001"])
        self.assertIn("Target capacity", evidence_items[-1]["quote_span"])
        self.assertEqual(evidence_items[-1]["metadata"]["query_focus_hits"], ["capacity", "forecast", "numeric", "target"])

    def test_exclusive_narrative_policy_augments_refusal_with_support_sentence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)

        answer = agent._augment_narrative_answer_with_supported_drivers(
            "관련 공시 문서에서 직접적인 근거를 찾지 못했습니다.",
            [
                {
                    "evidence_id": "ev_001",
                    "claim": (
                        "예측정보에 대한 주의사항 이 사업보고서에는 미래 활동, 사건 또는 현상에 "
                        "대한 예측정보가 포함되어 있으며 다양한 가정과 불확실성으로 실제 결과와 "
                        "차이가 발생할 수 있습니다."
                    ),
                    "quote_span": "",
                }
            ],
            query="2026년 1분기 예상 영업이익과 전기차 판매량을 예측해 줘.",
        )

        self.assertIn("직접적인 근거를 찾지 못했습니다", answer)
        self.assertIn("예측정보", answer)
        self.assertIn("불확실성", answer)

    def test_narrative_selection_preserves_policy_realized_metric_candidate(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent._narrative_driver_groups = lambda _query: []
        reranked = [
            (
                Document(
                    page_content="시장 환경 변화와 비용 관리에 대한 일반 설명입니다.",
                    metadata={
                        "chunk_id": "generic-1",
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견",
                    },
                ),
                0.99,
            ),
            (
                Document(
                    page_content="추가 일반 경영진단 문단입니다.",
                    metadata={
                        "chunk_id": "generic-2",
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견",
                    },
                ),
                0.98,
            ),
            (
                Document(
                    page_content="내실성장을 위한 일반 사업 현황 문단이며 전년 대비 개선 흐름을 설명합니다.",
                    metadata={
                        "chunk_id": "generic-3",
                        "block_type": "paragraph",
                        "section_path": "II. 사업의 내용 > 2. 영업의 현황",
                    },
                ),
                0.97,
            ),
            (
                Document(
                    page_content="위탁/자산관리 부문 영업이익은 전년 대비 증가했습니다.",
                    metadata={
                        "chunk_id": "wm-profit",
                        "block_type": "table",
                        "section_path": "II. 사업의 내용 > 2. 영업의 현황",
                    },
                ),
                0.96,
            ),
            (
                Document(
                    page_content="계열사별 손익은 전년대비 개선되었지만 자산 규모 지표는 포함하지 않습니다.",
                    metadata={
                        "chunk_id": "weak-realized",
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견",
                    },
                ),
                0.95,
            ),
            (
                Document(
                    page_content="그룹 총관리자산(AUM)은 1,216.7조원이며 계열사별 자산이 증가했습니다.",
                    metadata={
                        "chunk_id": "wm-aum",
                        "block_type": "table",
                        "section_path": "II. 사업의 내용 > 5. 재무건전성 등 기타 참고사항",
                        "period_focus": "current",
                    },
                ),
                0.40,
            ),
        ]
        state = {
            "query": "2023년 순수수료이익 증가율을 계산하고, 자산관리(WM) 부문의 성과를 요약해 줘.",
            "active_subtask": {
                "operation_family": "narrative_summary",
            },
        }

        docs = agent._select_narrative_summary_docs(reranked, state, 3)
        chunk_ids = [item[0].metadata.get("chunk_id") for item in docs]

        self.assertIn("wm-aum", chunk_ids)

    def test_evidence_extraction_prompt_surfaces_narrative_focus_terms(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _CapturingLLM(EvidenceExtraction(coverage="missing", evidence=[]))
        state = {
            "query": "인플레이션 감축법(IRA) 등 보호무역주의 정책에 대한 대응 필요성을 요약해 줘.",
            "query_type": "qa",
            "topic": "보호무역주의 대응 필요성",
            "retrieved_docs": [
                (
                    Document(
                        page_content=(
                            "미국의 인플레이션 감축법과 유럽의 핵심원자재법 등 각국의 "
                            "보호무역주의에 대한 적극적인 대응이 필요한 상황입니다."
                        ),
                        metadata={
                            "company": "현대자동차",
                            "year": 2023,
                            "section_path": "IV. 이사의 경영진단 및 분석의견",
                            "block_type": "paragraph",
                        },
                    ),
                    1.0,
                )
            ],
            "active_subtask": {
                "task_id": "task_policy_context",
                "metric_family": "narrative_summary",
                "metric_label": "정책 대응 필요성",
                "operation_family": "narrative_summary",
            },
        }

        result = agent._extract_evidence(state)
        prompt_text = agent.llm.structured.prompt_text

        self.assertEqual(result["evidence_status"], "missing")
        self.assertIn("질문 focus terms:", prompt_text)
        self.assertIn("인플레이션", prompt_text)
        self.assertIn("감축법(IRA)", prompt_text)
        self.assertIn("IRA", prompt_text)
        self.assertIn("보호무역주의", prompt_text)
        self.assertIn("대응", prompt_text)
        self.assertIn("필요성", prompt_text)

    def test_evidence_context_prefers_focus_child_over_parent_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.vsm = SimpleNamespace(
            get_parent=lambda _parent_id: "넓은 parent context입니다. 질문 focus term은 여기에 없습니다."
        )
        doc = Document(
            page_content=(
                "미국의 인플레이션 감축법과 유럽의 핵심원자재법 등 각국의 "
                "보호무역주의에 대한 적극적인 대응이 필요한 상황입니다."
            ),
            metadata={
                "company": "현대자동차",
                "year": 2023,
                "section_path": "IV. 이사의 경영진단 및 분석의견",
                "block_type": "paragraph",
                "parent_id": "mda-parent",
            },
        )

        context = agent._build_evidence_context(
            [(doc, 1.0)],
            focus_terms=["IRA", "보호무역주의", "대응"],
        )["context"]

        self.assertIn("보호무역주의에 대한 적극적인 대응", context)
        self.assertNotIn("넓은 parent context", context)

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

    def test_narrative_summary_doc_selection_preserves_entity_metric_tables(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        reranked = [
            (
                Document(
                    page_content="일반 경영진단 문단",
                    metadata={
                        "chunk_id": f"para-{idx}",
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견",
                    },
                ),
                0.95 - (idx * 0.01),
            )
            for idx in range(4)
        ]
        reranked.extend(
            [
                (
                    Document(
                        page_content=(
                            "Motional AD LLC | 자율주행 소프트웨어 개발 | 미국 | "
                            "소유지분율 25.81% | 투자자산 1,294,367"
                        ),
                        metadata={
                            "chunk_id": "investment-table",
                            "block_type": "table",
                            "section_path": "III. 재무에 관한 사항 > 5. 재무제표 주석",
                            "period_focus": "current",
                        },
                    ),
                    0.62,
                ),
                (
                    Document(
                        page_content=(
                            "Motional AD LLC | 영업수익 132,772 | 계속영업손실 (803,742) | "
                            "총포괄손실 (791,627)"
                        ),
                        metadata={
                            "chunk_id": "summary-profit-loss-table",
                            "block_type": "table",
                            "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                            "period_focus": "current",
                        },
                    ),
                    0.55,
                ),
            ]
        )
        state = {
            "query": "모셔널(Motional)의 지분율, 투자장부금액, 요약 손익을 정리해 줘.",
            "active_subtask": {
                "operation_family": "narrative_summary",
            },
        }

        docs = agent._select_narrative_summary_docs(reranked, state, 6)
        chunk_ids = [item[0].metadata.get("chunk_id") for item in docs]

        self.assertIn("investment-table", chunk_ids)
        self.assertIn("summary-profit-loss-table", chunk_ids)

    def test_entity_metric_narrative_task_prefers_table_format(self) -> None:
        task = _build_hybrid_narrative_subtask(
            query="Summarize Motional ownership, carrying amount, and profit or loss.",
            intent="numeric_fact",
            report_scope={"company": "현대자동차", "year": 2023},
            next_task_id="task_2",
        )

        self.assertEqual(task["format_preference_override"], "table")
        self.assertEqual(task["preferred_sections"], [])
        self.assertEqual(task["retrieval_queries"], [task["query"]])

    def test_entity_metric_doc_selection_fills_with_slot_tables_before_generic_paragraphs(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        reranked = [
            (
                Document(
                    page_content="일반 경영진단 문단",
                    metadata={
                        "chunk_id": "generic-mda",
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견",
                    },
                ),
                1.20,
            ),
            (
                Document(
                    page_content=(
                        "기업명 | 주요영업활동 | 소재지 | 소유지분율 | 투자자산\n"
                        "Motional AD LLC | 자율주행 소프트웨어 개발 | 미국 | 25.81% | 1,294,367"
                    ),
                    metadata={
                        "chunk_id": "motional-investment",
                        "block_type": "table",
                        "section_path": "III. 재무에 관한 사항 > 5. 재무제표 주석",
                        "consolidation_scope": "separate",
                        "period_focus": "current",
                    },
                ),
                0.70,
            ),
            (
                Document(
                    page_content=(
                        "회사명 | 계속영업손실 | 총포괄손실\n"
                        "Motional AD LLC | (803,742) | (791,627)"
                    ),
                    metadata={
                        "chunk_id": "motional-profit-loss",
                        "block_type": "table",
                        "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                        "consolidation_scope": "consolidated",
                        "period_focus": "current",
                    },
                ),
                0.60,
            ),
            (
                Document(
                    page_content="Motional AD LLC 이름만 있는 헤더 표",
                    metadata={
                        "chunk_id": "motional-header-only",
                        "block_type": "table",
                        "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                    },
                ),
                0.90,
            ),
        ]
        state = {
            "query": "2023년 타법인출자 현황 또는 주석을 바탕으로 모셔널(Motional)의 지분율, 투자장부금액, 요약 손익을 정리해 줘.",
            "active_subtask": {"operation_family": "narrative_summary", "format_preference_override": "table"},
        }

        docs = agent._select_narrative_summary_docs(reranked, state, 3)
        chunk_ids = [item[0].metadata.get("chunk_id") for item in docs]

        self.assertIn("motional-investment", chunk_ids)
        self.assertIn("motional-profit-loss", chunk_ids)
        self.assertNotIn("generic-mda", chunk_ids[:2])
        self.assertNotIn("motional-header-only", chunk_ids)

    def test_table_focused_narrative_fill_prefers_selected_table_sections(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        reranked = [
            (
                Document(
                    page_content="Generic management discussion paragraph with no entity focus.",
                    metadata={
                        "chunk_id": "generic-high-score",
                        "block_type": "paragraph",
                        "section_path": "IV. Management Discussion",
                    },
                ),
                1.10,
            ),
            (
                Document(
                    page_content="Motional AD LLC | ownership | carrying amount\nMotional AD LLC | 25.81% | 1,294,367",
                    metadata={
                        "chunk_id": "focus-table",
                        "block_type": "table",
                        "section_path": "III. Notes > Investments",
                        "period_focus": "current",
                    },
                ),
                0.80,
            ),
            (
                Document(
                    page_content="Motional AD LLC supporting note text from the same investment note section.",
                    metadata={
                        "chunk_id": "same-section-note",
                        "block_type": "paragraph",
                        "section_path": "III. Notes > Investments",
                    },
                ),
                0.30,
            ),
        ]
        state = {
            "query": "Summarize Motional ownership, carrying amount, and profit or loss.",
            "active_subtask": {"operation_family": "narrative_summary", "format_preference_override": "table"},
        }

        docs = agent._select_narrative_summary_docs(reranked, state, 3)
        chunk_ids = [item[0].metadata.get("chunk_id") for item in docs]

        self.assertEqual(chunk_ids[:2], ["focus-table", "same-section-note"])
        self.assertEqual(chunk_ids[2], "generic-high-score")

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

    def test_query_focus_markers_preserve_parenthetical_entity_pairs(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)

        marker_groups = agent._query_focus_marker_groups(
            "모셔널(Motional)의 지분율과 인플레이션 감축법(IRA) 대응을 요약해 줘."
        )
        variants = [variant for group in marker_groups for variant in group.get("variants", [])]

        self.assertIn("모셔널", variants)
        self.assertIn("Motional", variants)
        self.assertIn("인플레이션 감축법", variants)
        self.assertIn("IRA", variants)
        self.assertNotIn("요약해", variants)

    def test_narrative_summary_doc_selection_preserves_harman_sdv_focus(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        reranked = [
            (
                Document(
                    page_content="2023년 연결 연구개발비용 총액은 28,352,769백만원입니다.",
                    metadata={
                        "chunk_id": "rnd-total",
                        "block_type": "table",
                        "section_path": "II. 사업의 내용 > 6. 주요계약 및 연구개발활동",
                    },
                ),
                0.99,
            ),
            (
                Document(
                    page_content="메모리 사업은 기술 리더십을 기반으로 시장 수요에 대응하고 있습니다.",
                    metadata={
                        "chunk_id": "generic-mda",
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견",
                    },
                ),
                0.98,
            ),
            (
                Document(
                    page_content=(
                        "Harman은 자체적인 혁신과 모바일ㆍITㆍ디스플레이ㆍ반도체 기술과의 융합을 통해 "
                        "사업역량을 확대하고 있습니다."
                    ),
                    metadata={
                        "chunk_id": "harman-mda",
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견",
                    },
                ),
                0.97,
            ),
            (
                Document(
                    page_content=(
                        "Harman은 커넥티드카 제품 및 솔루션을 디자인하고 개발하며, "
                        "전장사업에 무선통신과 디스플레이 등 IT 기술을 접목하고 SDV 차별화 기술 개발에 집중하고 있습니다."
                    ),
                    metadata={
                        "chunk_id": "harman-sdv",
                        "block_type": "paragraph",
                        "section_path": "II. 사업의 내용 > 7. 기타 참고사항 > 사업부문별 현황(Harman)",
                    },
                ),
                0.52,
            ),
        ]
        state = {
            "query": "2023년 연결 연구개발비용 총액을 추출하고, 사업보고서에서 Harman 부문의 전장 사업 방향과 주요 기술 초점을 요약해 줘.",
            "active_subtask": {"operation_family": "narrative_summary"},
        }

        docs = agent._select_narrative_summary_docs(reranked, state, 3)
        chunk_ids = [item[0].metadata.get("chunk_id") for item in docs]

        self.assertIn("harman-sdv", chunk_ids[:2])
        self.assertLess(chunk_ids.index("harman-sdv"), chunk_ids.index("harman-mda"))

    def test_narrative_summary_doc_selection_preserves_ira_policy_focus(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        reranked = [
            (
                Document(
                    page_content="2023년 미국시장에서 현대차는 전년 대비 11.5% 증가한 87.0만 대를 판매했습니다.",
                    metadata={
                        "chunk_id": "us-sales",
                        "block_type": "paragraph",
                        "section_path": "II. 사업의 내용 > 7. 기타 참고사항 > 해외시장",
                    },
                ),
                0.95,
            ),
            (
                Document(
                    page_content=(
                        "미국의 인플레이션 감축법과 유럽의 핵심원자재법 등 각국의 보호무역주의에 "
                        "대한 적극적인 대응이 필요한 상황입니다."
                    ),
                    metadata={
                        "chunk_id": "ira-policy",
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견",
                    },
                ),
                0.43,
            ),
        ]
        state = {
            "query": "2023년 미국 시장 판매대수의 전년 대비 성장률을 계산하고, 사업보고서에서 인플레이션 감축법(IRA) 등 보호무역주의 정책에 대한 대응 필요성을 요약해 줘.",
            "active_subtask": {"operation_family": "narrative_summary"},
        }

        docs = agent._select_narrative_summary_docs(reranked, state, 3)
        chunk_ids = [item[0].metadata.get("chunk_id") for item in docs]

        self.assertIn("ira-policy", chunk_ids)

    def test_narrative_summary_doc_selection_preserves_motional_investment_table_focus(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        reranked = [
            (
                Document(
                    page_content="당사의 연결 매출액은 전년 대비 증가했습니다.",
                    metadata={
                        "chunk_id": "generic-mda",
                        "block_type": "paragraph",
                        "section_path": "IV. 이사의 경영진단 및 분석의견",
                    },
                ),
                0.97,
            ),
            (
                Document(
                    page_content="공동기업과 관계기업에 대한 투자자산 BHAF WAE BHMC HMG Global LLC Motional AD LLC",
                    metadata={
                        "chunk_id": "motional-header-only",
                        "block_type": "table",
                        "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                        "table_context": "공동기업과 관계기업 투자자산 표",
                    },
                ),
                0.82,
            ),
            (
                Document(
                    page_content=(
                        "기업명 | 주요영업활동 | 소재지 | 소유지분율 | 투자자산\n"
                        "Motional AD LLC | 자율주행 소프트웨어 개발 | 미국 | 26% | 700,691"
                    ),
                    metadata={
                        "chunk_id": "motional-consolidated-investment-table",
                        "block_type": "table",
                        "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                        "consolidation_scope": "consolidated",
                        "period_focus": "current",
                        "table_context": "Motional AD LLC 연결 공동기업 투자자산",
                    },
                ),
                0.55,
            ),
            (
                Document(
                    page_content=(
                        "기업명 | 주요영업활동 | 소재지 | 소유지분율 | 투자자산\n"
                        "Motional AD LLC | 자율주행 소프트웨어 개발 | 미국 | 25.81% | 1,294,367"
                    ),
                    metadata={
                        "chunk_id": "motional-table",
                        "block_type": "table",
                        "section_path": "III. 재무에 관한 사항 > 5. 재무제표 주석",
                        "consolidation_scope": "separate",
                        "period_focus": "current",
                        "table_context": "Motional AD LLC 별도 공동기업 투자자산",
                    },
                ),
                0.41,
            ),
            (
                Document(
                    page_content=(
                        "회사명 | 유동자산 | 비유동자산 | 유동부채 | 비유동부채 | 영업수익 | 계속영업손익 | 기타포괄손익 | 총포괄손익\n"
                        "Motional AD LLC | 195,840 | 2,954,385 | 132,590 | 290,284 | 1,775 | (803,742) | 12,115 | (791,627)"
                    ),
                    metadata={
                        "chunk_id": "motional-summary-pl",
                        "block_type": "table",
                        "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                        "consolidation_scope": "consolidated",
                        "period_focus": "current",
                        "table_context": "Motional AD LLC 요약재무정보",
                    },
                ),
                0.39,
            ),
        ]
        state = {
            "query": "2023년 타법인출자 현황 또는 주석을 바탕으로 모셔널(Motional)의 지분율, 투자장부금액, 요약 손익을 정리해 줘.",
            "active_subtask": {"operation_family": "narrative_summary"},
        }

        docs = agent._select_narrative_summary_docs(reranked, state, 3)
        chunk_ids = [item[0].metadata.get("chunk_id") for item in docs]

        self.assertIn("motional-table", chunk_ids)
        self.assertIn("motional-summary-pl", chunk_ids)
        self.assertNotIn("motional-consolidated-investment-table", chunk_ids)
        self.assertNotIn("motional-header-only", chunk_ids[:2])

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

    def test_dividend_policy_aggregate_does_not_append_partial_suffix_when_policy_answer_is_complete(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        query = (
            "2023년 연결 현금흐름표에서 '배당금 지급'으로 유출된 현금 규모를 찾고, "
            "사업보고서의 '배당에 관한 사항'을 바탕으로 2024~2026년 주주환원 정책을 요약해 줘."
        )
        evidence_items = [
            {
                "evidence_id": "ev_001",
                "source_anchor": "20240312000736::IV. 이사의 경영진단 및 분석의견",
                "claim": "당사의 유동성은 배당금 지급 9조 8,645억원 등이 유출되었으며",
                "quote_span": "배당금 지급 9조 8,645억원 등이 유출되었으며",
                "metadata": {
                    "section_path": "IV. 이사의 경영진단 및 분석의견 > 유동성 및 자금조달",
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
                "metadata": {
                    "section_path": "III. 재무에 관한 사항 > 6. 배당에 관한 사항",
                },
            },
        ]
        state = {
            "query": query,
            "calc_subtasks": [
                {
                    "task_id": "task_1",
                    "operation_family": "generic_numeric",
                    "metric_family": "generic_numeric",
                    "metric_label": "배당금 지급",
                    "query": "배당금 지급 금액을 찾아줘.",
                },
                {
                    "task_id": "task_2",
                    "operation_family": "narrative_summary",
                    "metric_family": "narrative_summary",
                    "metric_label": "주주환원 정책",
                    "query": query,
                },
            ],
            "active_subtask": {
                "task_id": "task_2",
                "operation_family": "narrative_summary",
                "metric_family": "narrative_summary",
                "metric_label": "주주환원 정책",
                "query": query,
            },
            "active_subtask_index": 1,
            "subtask_results": [
                {
                    "task_id": "task_1",
                    "metric_family": "generic_numeric",
                    "metric_label": "배당금 지급",
                    "status": "insufficient_operands",
                    "answer": "배당금 지급 계산에 필요한 값을 충분히 확인하지 못해 계산할 수 없습니다.",
                    "calculation_plan": {"operation": "generic_numeric"},
                    "calculation_result": {
                        "status": "insufficient_operands",
                        "answer_slots": {
                            "operation_family": "generic_numeric",
                            "primary_value": {"label": "배당금 지급"},
                        },
                    },
                    "runtime_evidence": [],
                }
            ],
            "answer": "",
            "compressed_answer": "",
            "selected_claim_ids": [],
            "evidence_items": evidence_items,
            "artifacts": [],
            "tasks": [],
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {"status": "partial"},
            "plan_loop_count": 2,
        }

        result = agent._aggregate_calculation_subtasks(state)

        self.assertIn("9조 8,645억원", result["answer"])
        self.assertIn("잉여현금흐름의 50%", result["answer"])
        self.assertNotIn("완전히 확정", result["answer"])
        self.assertEqual(result["planner_feedback"], "")
        trace = _resolve_runtime_calculation_trace(result)
        self.assertEqual(trace["calculation_result"]["status"], "ok")
        self.assertEqual(result["structured_result"]["status"], "ok")
        self.assertNotIn("calculation_result", result)

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

    def test_lookup_prefers_direct_structured_row_label_evidence_over_indirect_aggregate(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "query": "2023년 목표항목 값을 찾아줘",
            "years": [2023],
            "report_scope": {"company": "대상회사", "year": "2023", "consolidation": "연결"},
            "intent": "qa",
            "topic": "목표항목",
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "evidence_status": "sufficient",
            "active_subtask": {
                "task_id": "task_lookup",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 목표항목",
                "operation_family": "lookup",
                "required_operands": [
                    {
                        "label": "목표항목",
                        "concept": "target_metric",
                        "role": "primary_value",
                        "required": True,
                    }
                ],
                "constraints": {
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                },
            },
            "reconciliation_result": {"status": "ready", "matched_operands": []},
        }
        indirect_row = {
            "evidence_id": "ev_indirect",
            "source_row_id": "ev_indirect",
            "source_row_ids": ["ev_indirect"],
            "source_anchor": "[대상회사 | 2023 | table]",
            "label": "목표항목",
            "raw_value": "400",
            "raw_unit": "백만원",
            "normalized_value": 400000000.0,
            "normalized_unit": "KRW",
            "matched_operand_label": "목표항목",
            "matched_operand_concept": "target_metric",
            "matched_operand_role": "primary_value",
        }
        reconciliation_evidence = [
            {
                "evidence_id": "ev_indirect",
                "source_anchor": "[대상회사 | 2023 | table]",
                "claim": "상위항목 합계 | 목표항목 합계 400 백만원",
                "quote_span": "상위항목 합계 | 목표항목 합계 400 백만원",
                "raw_row_text": "상위항목 합계 | 목표항목 합계 400 백만원",
                "metadata": {
                    "row_label": "상위항목 합계",
                    "semantic_label": "상위항목 합계",
                    "value_role": "aggregate",
                    "aggregation_stage": "final",
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "year": 2023,
                    "table_source_id": "table_indirect",
                    "unit_hint": "백만원",
                    "structured_cells": [
                        {"column_headers": ["목표항목 합계"], "value_text": "400", "unit_hint": "백만원"}
                    ],
                },
            },
        ]
        direct_evidence = {
            "evidence_id": "ev_direct",
            "source_anchor": "[대상회사 | 2023 | table]",
            "claim": "목표항목 | 표시금액 900 백만원",
            "quote_span": "목표항목 | 표시금액 900 백만원",
            "raw_row_text": "목표항목 | 표시금액 900 백만원",
            "metadata": {
                "row_label": "목표항목",
                "semantic_label": "목표항목",
                "value_role": "detail",
                "aggregation_stage": "none",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "year": 2023,
                "table_source_id": "table_direct",
                "unit_hint": "백만원",
                "structured_cells": [
                    {"column_headers": ["표시금액"], "value_text": "900", "unit_hint": "백만원"}
                ],
            },
        }
        state["runtime_evidence"] = [direct_evidence]

        with patch.object(
            agent,
            "_extract_structured_operands_from_reconciliation",
            return_value=[indirect_row],
        ), patch.object(
            agent,
            "_evidence_items_from_reconciliation_matches",
            return_value=reconciliation_evidence,
        ):
            result = agent._extract_calculation_operands(state)

        rows = result["calculation_debug_trace"]["operands"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_row_id"], "ev_direct")
        self.assertEqual(rows[0]["raw_value"], "900")

    def test_aggregate_lookup_repair_uses_state_runtime_evidence_for_ok_slot(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        direct_evidence = {
            "evidence_id": "ev_direct",
            "source_anchor": "[대상회사 | 2023 | table]",
            "claim": "목표항목 | 표시금액 900 백만원",
            "quote_span": "목표항목 | 표시금액 900 백만원",
            "raw_row_text": "목표항목 | 표시금액 900 백만원",
            "metadata": {
                "row_label": "목표항목",
                "semantic_label": "목표항목",
                "value_role": "detail",
                "aggregation_stage": "none",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "year": 2023,
                "table_source_id": "table_direct",
                "unit_hint": "백만원",
                "structured_cells": [
                    {"column_headers": ["표시금액"], "value_text": "900", "unit_hint": "백만원"}
                ],
            },
        }
        ordered_results = [
            {
                "task_id": "task_context",
                "metric_family": "concept_lookup",
                "metric_label": "context",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "context",
                            "raw_value": "1",
                            "raw_unit": "백만원",
                            "normalized_value": 1000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "1백만원",
                            "source_row_id": "ev_context",
                            "source_row_ids": ["ev_context"],
                        },
                    },
                },
            },
            {
                "task_id": "task_lookup",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 목표항목",
                "status": "ok",
                "answer": "목표항목 400백만원",
                "calculation_result": {
                    "status": "ok",
                    "result_value": 400000000.0,
                    "result_unit": "백만원",
                    "rendered_value": "400백만원",
                    "formatted_result": "목표항목 400백만원",
                    "source_row_ids": ["ev_indirect"],
                    "answer_slots": {
                        "metric_label": "2023년 목표항목",
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "목표항목",
                            "raw_value": "400",
                            "raw_unit": "백만원",
                            "normalized_value": 400000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "400백만원",
                            "source_row_id": "ev_indirect",
                            "source_row_ids": ["ev_indirect"],
                        },
                    },
                },
            },
        ]
        state = {
            "calc_subtasks": [
                {"task_id": "task_context", "operation_family": "lookup", "required_operands": []},
                {
                    "task_id": "task_lookup",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "목표항목",
                            "concept": "target_metric",
                            "role": "primary_value",
                            "required": True,
                        }
                    ],
                },
            ],
            "evidence_items": [],
            "runtime_evidence": [direct_evidence],
        }

        repaired = agent._recover_lookup_results_from_sibling_table_evidence(ordered_results, state)

        lookup = next(row for row in repaired if row["task_id"] == "task_lookup")
        slot = lookup["calculation_result"]["answer_slots"]["primary_value"]
        self.assertEqual(slot["source_row_id"], "ev_direct")
        self.assertEqual(slot["raw_value"], "900")

    def test_lookup_result_view_aligns_with_dependency_projection(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {"calc_subtasks": []}
        ordered_results = [
            {
                "task_id": "task_lookup",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 목표항목",
                "status": "ok",
                "answer": "400백만원",
                "calculation_result": {
                    "status": "ok",
                    "result_value": 400000000.0,
                    "result_unit": "백만원",
                    "rendered_value": "400백만원",
                    "formatted_result": "400백만원",
                    "source_row_ids": ["ev_indirect"],
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "목표항목",
                            "concept": "target_metric",
                            "raw_value": "400",
                            "raw_unit": "백만원",
                            "normalized_value": 400000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "400백만원",
                            "source_row_id": "ev_indirect",
                            "source_row_ids": ["ev_indirect"],
                        },
                    },
                },
            }
        ]
        aggregate_projection = {
            "calculation_operands": [
                {
                    "label": "목표항목",
                    "matched_operand_label": "목표항목",
                    "matched_operand_concept": "target_metric",
                    "matched_operand_role": "numerator_1",
                    "raw_value": "900",
                    "raw_unit": "백만원",
                    "normalized_value": 900000000.0,
                    "normalized_unit": "KRW",
                    "period": "2023",
                    "source_row_id": "task_output:task_lookup",
                    "source_row_ids": ["task_output:task_lookup", "ev_direct"],
                    "source_anchor": "[대상회사 | 2023 | table]",
                }
            ]
        }

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            state,
            aggregate_projection,
        )

        lookup = aligned[0]
        self.assertEqual(lookup["answer"], "900백만원")
        slot = lookup["calculation_result"]["answer_slots"]["primary_value"]
        self.assertEqual(slot["raw_value"], "900")
        self.assertEqual(slot["source_row_id"], "ev_direct")
        self.assertEqual(
            lookup["calculation_result"]["answer_slots"]["components_by_role"]["numerator_1"][0]["raw_value"],
            "900",
        )
        projection = agent._build_aggregate_calculation_projection(aligned, "900백만원")
        projected_subtask = projection["calculation_result"]["answer_slots"]["subtask_results"][0]
        self.assertEqual(projected_subtask["answer"], "900백만원")
        self.assertEqual(projected_subtask["rendered_value"], "900백만원")
        self.assertEqual(projected_subtask["operation_family"], "lookup")
        self.assertEqual(projected_subtask["source_row_ids"], ["ev_direct"])

    def test_aggregate_projection_keeps_narrative_evidence_ids_separate_from_row_ids(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "segment growth",
                "answer": "Segment grew 25%.",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "operation_family": "growth_rate",
                    "rendered_value": "25%",
                    "source_row_ids": ["row_growth"],
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "source_row_ids": ["row_growth"],
                    },
                },
            },
            {
                "task_id": "task_summary",
                "metric_family": "narrative_summary",
                "metric_label": "context summary",
                "answer": "Management described a policy response.",
                "status": "ok",
                "runtime_evidence": [
                    {
                        "evidence_id": "ev_summary",
                        "claim": "Management described a policy response.",
                    },
                    {
                        "evidence_id": "None",
                        "claim": "Placeholder evidence should not survive.",
                    },
                ],
                "calculation_result": {
                    "status": "ok",
                    "operation_family": "narrative_summary",
                    "rendered_value": "",
                },
            },
        ]

        projection = agent._build_aggregate_calculation_projection(
            ordered_results,
            "Segment grew 25%. Management described a policy response.",
        )
        subtasks = projection["calculation_result"]["answer_slots"]["subtask_results"]

        self.assertEqual(subtasks[0]["operation_family"], "growth_rate")
        self.assertEqual(subtasks[0]["source_row_ids"], ["row_growth"])
        self.assertEqual(subtasks[0]["source_evidence_ids"], [])
        self.assertEqual(subtasks[1]["operation_family"], "narrative_summary")
        self.assertEqual(subtasks[1]["source_row_ids"], [])
        self.assertEqual(subtasks[1]["source_evidence_ids"], ["ev_summary"])

    def test_dependency_operand_rows_prefer_direct_sibling_lookup_evidence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        direct_evidence = {
            "evidence_id": "ev_direct",
            "source_anchor": "[대상회사 | 2023 | table]",
            "claim": "목표항목 | 표시금액 900 백만원",
            "quote_span": "목표항목 | 표시금액 900 백만원",
            "raw_row_text": "목표항목 | 표시금액 900 백만원",
            "metadata": {
                "row_label": "목표항목",
                "semantic_label": "목표항목",
                "value_role": "detail",
                "aggregation_stage": "none",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "year": 2023,
                "table_source_id": "table_direct",
                "unit_hint": "백만원",
                "structured_cells": [
                    {"column_headers": ["표시금액"], "value_text": "900", "unit_hint": "백만원"}
                ],
            },
        }
        state = {
            "active_subtask": {
                "task_id": "task_ratio",
                "operation_family": "ratio",
                "inputs": [
                    {
                        "label": "목표항목",
                        "concept": "target_metric",
                        "role": "numerator_1",
                        "source_preference": ["task_output"],
                        "preferred_task_id": "task_lookup",
                        "source_slot": "primary_value",
                    }
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_context",
                    "runtime_evidence": [direct_evidence],
                    "calculation_result": {},
                },
                {
                    "task_id": "task_lookup",
                    "metric_label": "2023년 목표항목",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 400000000.0,
                        "result_unit": "백만원",
                        "source_row_ids": ["ev_indirect"],
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "role": "primary_value",
                                "label": "목표항목",
                                "concept": "target_metric",
                                "raw_value": "400",
                                "raw_unit": "백만원",
                                "normalized_value": 400000000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "400백만원",
                                "source_row_id": "ev_indirect",
                                "source_row_ids": ["ev_indirect"],
                            },
                        },
                    },
                },
            ],
            "evidence_items": [],
        }

        rows = agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_row_ids"][:2], ["task_output:task_lookup", "ev_direct"])
        self.assertEqual(rows[0]["source_row_id"], "task_output:task_lookup")
        self.assertEqual(rows[0]["raw_value"], "900")

    def test_selected_narrative_claim_ids_expand_to_query_focus_driver(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence_items = [
            {
                "evidence_id": "ev_001",
                "claim": "2023년 연결 연구개발비용 총액은 28,352,769백만원입니다.",
                "quote_span": "28,352,769",
                "question_relevance": "high",
                "support_level": "direct",
            },
            {
                "evidence_id": "ev_002",
                "claim": "Harman은 전장사업에 IT 기술을 접목하고 SDV 차별화 기술 개발에 집중하고 있습니다.",
                "quote_span": "Harman은 전장사업에 IT 기술을 접목하고 SDV 차별화 기술 개발에 집중",
                "question_relevance": "high",
                "support_level": "direct",
            },
        ]

        expanded = agent._expand_selected_claim_ids_for_narrative_drivers(
            ["ev_001"],
            evidence_items,
            query="2023년 연결 연구개발비용 총액을 추출하고, 사업보고서에서 Harman 부문의 전장 사업 방향과 주요 기술 초점을 요약해 줘.",
        )

        self.assertEqual(expanded, ["ev_001", "ev_002"])

    def test_entity_table_summary_answer_extracts_named_entity_rows(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        query = "2023년 타법인출자 현황 또는 주석을 바탕으로 모셔널(Motional)의 지분율, 투자장부금액, 요약 손익을 정리해 줘."
        docs = [
            (
                Document(
                    page_content=(
                        "회사명 | 주요영업활동 | 소재지 | 소유지분율 | 장부금액\n"
                        "Motional AD LLC(*1) | 자율주행 소프트웨어 개발 | 미국 | 25.81% | 1,294,367"
                    ),
                    metadata={
                        "company": "현대자동차",
                        "year": 2023,
                        "report_type": "사업보고서",
                        "section_path": "III. 재무에 관한 사항 > 5. 재무제표 주석",
                        "block_type": "table",
                        "period_focus": "current",
                    },
                ),
                0.91,
            ),
            (
                Document(
                    page_content=(
                        "회사명 | 유동자산 | 비유동자산 | 유동부채 | 비유동부채 | 영업수익 | 계속영업손익 | 기타포괄손익 | 총포괄손익\n"
                        "Motional AD LLC | 195,840 | 2,954,385 | 132,590 | 290,284 | 1,775 | (803,742) | 12,115 | (791,627)"
                    ),
                    metadata={
                        "company": "현대자동차",
                        "year": 2023,
                        "report_type": "사업보고서",
                        "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                        "block_type": "table",
                        "period_focus": "current",
                    },
                ),
                0.88,
            ),
        ]

        result = agent._compose_entity_table_summary_answer(
            query=query,
            docs=docs,
            evidence_items=[],
        )

        self.assertIsNotNone(result)
        assert result is not None
        answer = result["compressed_answer"]
        self.assertIn("25.81%", answer)
        self.assertIn("1,294,367백만원", answer)
        self.assertIn("(803,742)백만원", answer)
        self.assertIn("(791,627)백만원", answer)
        self.assertNotIn("73.28%", answer)
        projection = result["calculation_projection"]
        self.assertEqual(projection["calculation_plan"]["operation_family"], "lookup")
        self.assertEqual(projection["calculation_result"]["answer_slots"]["operation_family"], "lookup")
        self.assertIn("investment_carrying_amount", projection["calculation_result"]["answer_slots"]["components_by_role"])
        self.assertTrue(projection["calculation_result"]["source_row_ids"])
        evidence_text = "\n".join(
            str(item.get("quote_span") or item.get("raw_row_text") or "")
            for item in result.get("evidence_items") or []
        )
        self.assertIn("Motional AD LLC", evidence_text)
        self.assertIn("25.81%", evidence_text)
        self.assertIn("1,294,367", evidence_text)
        self.assertIn("계속영업손실", evidence_text)
        self.assertIn("총포괄손실", evidence_text)
        self.assertIn("(803,742)", evidence_text)
        self.assertIn("(791,627)", evidence_text)
        self.assertTrue(
            any(
                " / " in str(item.get("quote_span") or item.get("raw_row_text") or "")
                and "Motional AD LLC" in str(item.get("quote_span") or item.get("raw_row_text") or "")
                for item in result.get("evidence_items") or []
            )
        )

    def test_business_technology_focus_answer_preserves_harman_required_facets(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        query = "2023년 연결 연구개발비용 총액을 추출하고, Harman 부문의 전장 사업 방향과 주요 기술 초점을 요약해 줘."
        docs = [
            (
                Document(
                    page_content=(
                        "[Harman]Harman은 커넥티드카 제품 및 솔루션 등을 디자인하고 개발하는 전장부품 사업과 "
                        "소비자 오디오 제품 및 프로페셔널 오디오 솔루션을 제공하는 라이프스타일 오디오 사업으로 구성되어 있습니다."
                    ),
                    metadata={"section_path": "I. 회사의 개요 > 1. 회사의 개요"},
                ),
                0.9,
            ),
            (
                Document(
                    page_content=(
                        "Harman은 전장부품 시장에서 차량내 경험의 중심이 되는 디지털 콕핏, 카 오디오 분야에서 선도적 시장 입지를 유지하고 있습니다. "
                        "당사는 Harman의 전장사업에 당사의 무선통신, 디스플레이 등 IT 기술을 지속 접목시켜 차량의 IT기기화에 적극 대응해 나갈 계획입니다."
                        "Harman은 차량의 SDV(Software Defined Vehicle)화 변화에 대응하기 위해 차별화된 기술 개발을 통해 끊임없는 혁신을 추구합니다."
                    ),
                    metadata={"section_path": "II. 사업의 내용 > 7. 기타 참고사항"},
                ),
                0.88,
            ),
            (
                Document(
                    page_content="연구개발비용 계 | 28,352,769 | ※ 연결 누계기준입니다.",
                    metadata={"section_path": "II. 사업의 내용 > 6. 주요계약 및 연구개발활동"},
                ),
                0.85,
            ),
        ]

        result = agent._compose_business_technology_focus_answer(
            query=query,
            existing_answer="2023년 삼성전자의 연결 연구개발비용 총액은 28조 3,528억원입니다.",
            docs=docs,
            evidence_items=[],
        )

        self.assertIsNotNone(result)
        assert result is not None
        answer = result["compressed_answer"]
        self.assertIn("28,352,769백만원", answer)
        self.assertIn("커넥티드카 제품 및 솔루션", answer)
        self.assertIn("무선통신, 디스플레이 등 IT 기술", answer)
        self.assertIn("SDV(Software Defined Vehicle)", answer)

    def test_policy_growth_cases_do_not_use_case_specific_composer(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        self.assertFalse(hasattr(agent, "_compose_sales_growth_policy_answer"))

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
