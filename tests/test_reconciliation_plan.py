import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_helpers import (
    _build_table_row_reconciliation_candidates,
    _build_lookup_producer_task_from_binding,
    _build_reconciliation_retry_queries,
    _candidate_is_direct_grounding_candidate,
    _candidate_matches_operand,
    _deterministic_reconcile_task,
    _score_operand_candidate,
)


class ReconciliationPlanTests(unittest.TestCase):
    def _active_subtask(self):
        return {
            "task_id": "task_1",
            "metric_family": "debt_ratio",
            "metric_label": "부채비율",
            "query": "2023년 연결기준 부채비율을 계산해 줘.",
            "required_operands": [
                {"label": "부채총계", "aliases": ["총부채"], "role": "numerator", "required": True},
                {"label": "자본총계", "aliases": ["총자본"], "role": "denominator", "required": True},
            ],
            "preferred_statement_types": ["balance_sheet", "summary_financials"],
            "preferred_sections": ["재무상태표", "요약재무정보"],
            "constraints": {
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "entity_scope": "company",
                "segment_scope": "none",
            },
        }

    def test_ready_when_all_operands_are_present(self) -> None:
        active_subtask = self._active_subtask()
        candidates = [
            {
                "candidate_id": "ev_001",
                "source_anchor": "[삼성전자 | 2023 | III. 재무에 관한 사항 > 1. 요약재무정보]",
                "text": "부채총계 92,228,115 자본총계 363,677,865",
                "metadata": {
                    "statement_type": "summary_financials",
                    "consolidation_scope": "consolidated",
                    "period_labels": ["2023", "2022"],
                    "table_source_id": "table_001",
                },
            },
            {
                "candidate_id": "ev_002",
                "source_anchor": "[삼성전자 | 2023 | III. 재무에 관한 사항 > 2. 연결재무제표 > 2-1. 연결 재무상태표]",
                "text": "부채총계 92,228,115 자본총계 363,677,865",
                "metadata": {
                    "statement_type": "balance_sheet",
                    "consolidation_scope": "consolidated",
                    "period_labels": ["2023"],
                    "table_source_id": "table_001",
                },
            },
        ]
        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=[2023],
            reconciliation_retry_count=0,
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["missing_operands"], [])
        self.assertIn("same_table_candidate_available", result["notes"])

    def test_retry_when_operand_is_missing(self) -> None:
        active_subtask = self._active_subtask()
        candidates = [
            {
                "candidate_id": "ev_001",
                "source_anchor": "[삼성전자 | 2023 | III. 재무에 관한 사항 > 1. 요약재무정보]",
                "text": "자본총계 363,677,865",
                "metadata": {
                    "statement_type": "summary_financials",
                    "consolidation_scope": "consolidated",
                    "period_labels": ["2023"],
                },
            }
        ]
        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=[2023],
            reconciliation_retry_count=0,
        )
        self.assertEqual(result["status"], "retry_retrieval")
        self.assertEqual(result["missing_operands"], ["부채총계"])
        self.assertTrue(any("부채총계" in item for item in result["retry_queries"]))

    def test_lookup_requires_direct_grounding_candidate_to_be_ready(self) -> None:
        active_subtask = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "metric_label": "2023년 영업비용",
            "operation_family": "lookup",
            "required_operands": [
                {
                    "label": "영업비용",
                    "concept": "operating_expense_total",
                    "role": "current_period",
                    "required": True,
                }
            ],
            "preferred_statement_types": ["notes"],
            "constraints": {
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "entity_scope": "company",
                "segment_scope": "none",
            },
        }
        candidates = [
            {
                "candidate_id": "chunk_001",
                "candidate_kind": "chunk",
                "source_anchor": "[네이버 | 2023 | III. 재무에 관한 사항 > 연결재무제표 주석]",
                "text": "당기 및 전기 중 영업비용의 내역은 다음과 같습니다. 종업원급여 1,701,418,940 ...",
                "metadata": {
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "period_labels": ["2023"],
                    "table_source_id": "table_25",
                },
            }
        ]

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=[2023],
            reconciliation_retry_count=0,
        )

        self.assertEqual(result["status"], "retry_retrieval")
        self.assertEqual(result["missing_operands"], ["영업비용"])
        matched = result["matched_operands"][0]
        self.assertFalse(matched["matched"])
        self.assertEqual(matched["reason"], "no_direct_grounding_candidate")
        self.assertEqual(matched["candidate_ids"], ["chunk_001"])

    def test_lookup_rejects_ambiguous_multiple_direct_candidates(self) -> None:
        active_subtask = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "metric_label": "2023년 영업비용",
            "operation_family": "lookup",
            "required_operands": [
                {
                    "label": "영업비용",
                    "concept": "operating_expense_total",
                    "role": "current_period",
                    "required": True,
                }
            ],
            "preferred_statement_types": ["notes"],
            "constraints": {
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "entity_scope": "company",
                "segment_scope": "none",
            },
        }
        candidates = [
            {
                "candidate_id": "value_001",
                "candidate_kind": "structured_value",
                "source_anchor": "[네이버 | 2023 | III. 재무에 관한 사항 > 연결재무제표 주석]",
                "text": "영업비용 6,915,414,298",
                "metadata": {
                    "row_label": "영업비용",
                    "semantic_label": "영업비용",
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                    "period_labels": ["2023"],
                    "structured_cells": [{"column_headers": ["2023"], "value_text": "6,915,414,298", "unit_hint": "천원"}],
                    "value_role": "aggregate",
                    "aggregation_stage": "direct",
                    "table_source_id": "table_25",
                },
            },
            {
                "candidate_id": "value_002",
                "candidate_kind": "structured_value",
                "source_anchor": "[네이버 | 2023 | III. 재무에 관한 사항 > 연결재무제표 주석]",
                "text": "영업비용 8,181,823,307",
                "metadata": {
                    "row_label": "영업비용",
                    "semantic_label": "영업비용",
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                    "period_labels": ["2023"],
                    "structured_cells": [{"column_headers": ["2023"], "value_text": "8,181,823,307", "unit_hint": "천원"}],
                    "value_role": "aggregate",
                    "aggregation_stage": "direct",
                    "table_source_id": "table_25",
                },
            },
        ]

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=[2023],
            reconciliation_retry_count=0,
        )

        self.assertEqual(result["status"], "retry_retrieval")
        self.assertEqual(result["missing_operands"], ["영업비용"])
        matched = result["matched_operands"][0]
        self.assertFalse(matched["matched"])
        self.assertEqual(matched["reason"], "no_direct_grounding_candidate")

    def test_lookup_dedupes_equivalent_direct_candidates_from_same_row(self) -> None:
        active_subtask = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "metric_label": "2023년 종업원급여",
            "query": "2023년 연결 재무제표 주석에서 종업원급여를 찾아줘",
            "operation_family": "lookup",
            "required_operands": [
                {
                    "label": "종업원급여",
                    "concept": "employee_benefits_expense",
                    "aliases": ["인건비", "종업원급여(*)"],
                    "role": "current_period",
                    "required": True,
                    "period_hint": "2023",
                }
            ],
            "preferred_statement_types": ["notes"],
            "constraints": {
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "entity_scope": "company",
                "segment_scope": "none",
            },
        }
        row_context_text = "\n".join(
            [
                "| 공시금액",
                "종업원급여(*) | 1,701,418,940",
                "합계 | 8,181,823,307",
            ]
        )
        shared_metadata = {
            "statement_type": "notes",
            "consolidation_scope": "consolidated",
            "table_source_id": "table_25",
            "year": 2023,
            "period_focus": "current",
            "period_labels": ["당기"],
            "local_heading": "25. 영업비용 (연결)",
            "table_context": "25. 영업비용 (연결)",
            "table_summary_text": "당기 및 전기 중 영업비용의 내역은 다음과 같습니다.",
            "row_text": "종업원급여(*) | 1,701,418,940",
            "row_context_text": row_context_text,
            "row_label": "종업원급여(*)",
            "semantic_label": "종업원급여",
            "semantic_aliases": ["종업원급여", "인건비"],
            "row_index": 1,
            "structured_cells": [
                {"column_headers": ["공시금액"], "value_text": "1,701,418,940", "unit_hint": "천원"}
            ],
        }
        candidates = [
            {
                "candidate_id": "dup_value_candidate",
                "candidate_kind": "structured_value",
                "text": "종업원급여(*) 1,701,418,940",
                "metadata": dict(shared_metadata),
            },
            {
                "candidate_id": "dup_row_candidate",
                "candidate_kind": "structured_row",
                "text": "종업원급여(*) | 1,701,418,940",
                "metadata": dict(shared_metadata),
            },
        ]

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=[2023],
            reconciliation_retry_count=0,
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["missing_operands"], [])
        matched = result["matched_operands"][0]
        self.assertTrue(matched["matched"])
        self.assertEqual(matched["reason"], "matched_direct_candidate")
        self.assertEqual(matched["candidate_ids"], ["dup_value_candidate", "dup_row_candidate"])

    def test_lookup_prefers_table_family_with_requested_sibling_surfaces(self) -> None:
        loss = "\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4"
        reversal = "\uc7ac\uace0\uc790\uc0b0\ud3c9\uac00\uc190\uc2e4\ud658\uc785"
        disposal = "\uc7ac\uace0\uc790\uc0b0\ud3d0\uae30\uc190\uc2e4"
        active_subtask = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "metric_label": f"2023\ub144 {loss}",
            "operation_family": "lookup",
            "sibling_lookup_surfaces": [reversal, disposal],
            "required_operands": [
                {
                    "label": loss,
                    "concept": "inventory_valuation_loss",
                    "role": "operand",
                    "required": True,
                    "unit_family": "KRW",
                    "surface_contract": {"positive": [loss], "negative": [reversal]},
                }
            ],
            "preferred_statement_types": ["notes", "cash_flow"],
            "constraints": {"period_focus": "current", "consolidation_scope": "consolidated"},
        }
        candidates = [
            {
                "candidate_id": "tax_note_loss",
                "candidate_kind": "structured_value",
                "text": f"{loss} 27,270,605",
                "metadata": {
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                    "year": 2023,
                    "unit_hint": "\ucc9c\uc6d0",
                    "row_label": loss,
                    "semantic_label": loss,
                    "table_row_labels_text": f"\uae30\ub9d0 {loss} \uacf5\uc815\uac00\uce58\ud3c9\uac00",
                    "structured_cells": [
                        {"column_headers": ["\uacf5\uc2dc\uae08\uc561"], "value_text": "27,270,605", "unit_hint": "\ucc9c\uc6d0"}
                    ],
                },
            },
            {
                "candidate_id": "cash_flow_loss",
                "candidate_kind": "structured_value",
                "text": f"{loss} 2,526,280 {reversal} (48,885,812) {disposal} 25,163,510",
                "metadata": {
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                    "year": 2023,
                    "unit_hint": "\ucc9c\uc6d0",
                    "row_label": loss,
                    "semantic_label": loss,
                    "table_row_labels_text": f"\uc870\uc815\ud56d\ubaa9 {loss} {reversal} {disposal}",
                    "structured_cells": [
                        {"column_headers": ["\uacf5\uc2dc\uae08\uc561"], "value_text": "2,526,280", "unit_hint": "\ucc9c\uc6d0"}
                    ],
                },
            },
        ]

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=[2023],
            reconciliation_retry_count=1,
            report_scope={"year": 2023},
        )

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["matched_operands"][0]["candidate_ids"][0], "cash_flow_loss")

    def test_lookup_collapses_same_family_direct_candidates_to_single_winner(self) -> None:
        active_subtask = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "metric_label": "2023년 매출액",
            "query": "2023년 연결 손익계산서에서 매출액을 찾아줘",
            "operation_family": "lookup",
            "required_operands": [
                {
                    "label": "매출액",
                    "concept": "revenue",
                    "role": "current_period",
                    "required": True,
                    "period_hint": "2023",
                }
            ],
            "preferred_statement_types": ["income_statement", "summary_financials"],
            "constraints": {
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "entity_scope": "company",
                "segment_scope": "none",
            },
        }
        base_metadata = {
            "statement_type": "income_statement",
            "consolidation_scope": "consolidated",
            "table_source_id": "income_table_1",
            "year": 2023,
            "period_focus": "current",
            "period_labels": ["2023"],
            "local_heading": "연결 손익계산서",
            "section_path": "III. 재무에 관한 사항 > 2. 연결재무제표 > 2-2. 연결 손익계산서",
            "row_label": "매출액",
            "semantic_label": "매출액",
            "row_index": 1,
        }
        candidates = [
            {
                "candidate_id": "revenue_value_1",
                "candidate_kind": "structured_value",
                "text": "매출액 162,663,579",
                "metadata": {
                    **base_metadata,
                    "structured_cells": [{"column_headers": [], "value_text": "162,663,579", "unit_hint": "백만원"}],
                },
            },
            {
                "candidate_id": "revenue_value_2",
                "candidate_kind": "structured_value",
                "text": "매출액 162,663,579",
                "metadata": {
                    **base_metadata,
                    "structured_cells": [{"column_headers": [], "value_text": "162,663,579", "unit_hint": "백만원"}],
                },
            },
        ]

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=[2023],
            reconciliation_retry_count=0,
        )

        self.assertEqual(result["status"], "ready")
        matched = result["matched_operands"][0]
        self.assertTrue(matched["matched"])
        self.assertEqual(matched["reason"], "matched_direct_candidate")
        self.assertEqual(matched["candidate_ids"][0], "revenue_value_1")

    def test_lookup_prefers_unique_canonical_statement_winner(self) -> None:
        active_subtask = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "metric_label": "2023년 영업비용",
            "query": "2023년 연결 영업비용을 찾아줘",
            "operation_family": "lookup",
            "required_operands": [
                {
                    "label": "영업비용",
                    "concept": "operating_expense_total",
                    "role": "current_period",
                    "required": True,
                    "period_hint": "2023",
                    "preferred_statement_types": ["income_statement", "summary_financials", "notes"],
                }
            ],
            "preferred_statement_types": ["income_statement", "summary_financials", "notes"],
            "constraints": {
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "entity_scope": "company",
                "segment_scope": "none",
            },
        }
        candidates = [
            {
                "candidate_id": "expense_notes",
                "candidate_kind": "structured_value",
                "text": "영업비용 8,181,823,307",
                "metadata": {
                    "row_label": "영업비용",
                    "semantic_label": "영업비용",
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                    "period_labels": ["2023"],
                    "structured_cells": [{"column_headers": ["2023"], "value_text": "8,181,823,307", "unit_hint": "천원"}],
                    "value_role": "aggregate",
                    "aggregation_stage": "direct",
                    "table_source_id": "notes_25",
                    "local_heading": "25. 영업비용 (연결)",
                    "section_path": "III. 재무에 관한 사항 > 연결재무제표 주석",
                },
            },
            {
                "candidate_id": "expense_income_statement",
                "candidate_kind": "structured_value",
                "text": "영업비용 8,181,823,307",
                "metadata": {
                    "row_label": "영업비용 (주25)",
                    "semantic_label": "영업비용",
                    "statement_type": "income_statement",
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                    "period_labels": ["2023"],
                    "structured_cells": [{"column_headers": ["2023"], "value_text": "8,181,823,307", "unit_hint": "천원"}],
                    "value_role": "aggregate",
                    "aggregation_stage": "direct",
                    "table_source_id": "is_1",
                    "local_heading": "연결 손익계산서",
                    "section_path": "III. 재무에 관한 사항 > 2. 연결재무제표 > 2-2. 연결 손익계산서",
                },
            },
        ]

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=[2023],
            reconciliation_retry_count=0,
        )

        self.assertEqual(result["status"], "ready")
        matched = result["matched_operands"][0]
        self.assertTrue(matched["matched"])
        self.assertEqual(matched["candidate_ids"][0], "expense_income_statement")

    def test_lookup_rejects_note_section_row_for_canonical_statement_cost_of_sales(self) -> None:
        active_subtask = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "metric_label": "2023년 매출원가",
            "query": "2023년 연결 매출원가를 찾아줘",
            "operation_family": "lookup",
            "required_operands": [
                {
                    "label": "매출원가",
                    "concept": "cost_of_sales",
                    "role": "numerator_1",
                    "required": True,
                    "period_hint": "2023",
                    "preferred_statement_types": ["income_statement", "summary_financials", "notes"],
                }
            ],
            "preferred_statement_types": ["income_statement", "summary_financials", "notes"],
            "constraints": {
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "entity_scope": "company",
                "segment_scope": "none",
            },
        }
        candidates = [
            {
                "candidate_id": "cost_note_row",
                "candidate_kind": "table_row",
                "text": "매출원가 | 106,235",
                "metadata": {
                    "row_label": "매출원가",
                    "semantic_label": "매출원가",
                    "statement_type": "income_statement",
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                    "period_labels": ["당기"],
                    "year": 2023,
                    "structured_cells": [{"column_headers": ["당기"], "value_text": "106,235", "unit_hint": "백만원"}],
                    "value_role": "detail",
                    "aggregation_stage": "none",
                    "table_source_id": "note_like_table",
                    "local_heading": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                    "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                },
            },
            {
                "candidate_id": "cost_income_statement",
                "candidate_kind": "structured_value",
                "text": "매출원가 | 129,179,183",
                "metadata": {
                    "row_label": "매출원가",
                    "semantic_label": "매출원가",
                    "statement_type": "income_statement",
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                    "period_labels": ["제 56 기"],
                    "year": 2023,
                    "structured_cells": [{"column_headers": ["제 56 기"], "value_text": "129,179,183", "unit_hint": "백만원"}],
                    "value_role": "detail",
                    "aggregation_stage": "none",
                    "table_source_id": "income_statement_main",
                    "local_heading": "연결 손익계산서",
                    "section_path": "III. 재무에 관한 사항 > 2. 연결재무제표 > 2-2. 연결 손익계산서",
                },
            },
        ]

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=[2023],
            reconciliation_retry_count=0,
        )

        self.assertEqual(result["status"], "ready")
        matched = result["matched_operands"][0]
        self.assertTrue(matched["matched"])
        self.assertEqual(matched["candidate_ids"][0], "cost_income_statement")

    def test_insufficient_after_retry_is_exhausted(self) -> None:
        active_subtask = self._active_subtask()
        candidates = []
        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=[2023],
            reconciliation_retry_count=1,
        )
        self.assertEqual(result["status"], "insufficient_operands")
        self.assertEqual(set(result["missing_operands"]), {"부채총계", "자본총계"})
        self.assertEqual(result["retry_queries"], [])

    def test_retry_strategy_prefers_synthesis_for_derived_task_with_dependency_outputs(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "종업원급여 비중",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "종업원급여", "concept": "employee_benefits_expense", "role": "numerator_1"},
                    {"label": "영업비용", "concept": "operating_expense_total", "role": "denominator_1"},
                ],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "employee_benefits_expense",
                        "period": "2023",
                        "label": "종업원급여",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "operating_expense_total",
                        "period": "2023",
                        "label": "영업비용",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023년 종업원급여",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "2023년 종업원급여",
                                "concept": "employee_benefits_expense",
                                "period": "2023",
                                "raw_value": "1,701,418,940",
                                "raw_unit": "천원",
                                "normalized_value": 1701418940000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "1조 7,014억원",
                            },
                        },
                    },
                }
            ],
            "reconciliation_result": {},
            "reflection_plan": {},
            "retry_strategy": "",
        }

        strategy = agent._select_retry_strategy_for_reconciliation(
            state,
            {"status": "retry_retrieval", "missing_operands": ["영업비용"]},
        )

        self.assertEqual(strategy, "retry_retrieval")

    def test_retry_strategy_prefers_synthesis_only_after_all_dependency_outputs_resolve(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "employee expense ratio",
                "operation_family": "ratio",
                "required_operands": [
                    {"label": "employee benefits expense", "concept": "employee_benefits_expense", "role": "numerator_1"},
                    {"label": "operating expense total", "concept": "operating_expense_total", "role": "denominator_1"},
                ],
                "inputs": [
                    {
                        "role": "numerator_1",
                        "concept": "employee_benefits_expense",
                        "period": "2023",
                        "label": "employee benefits expense",
                        "preferred_task_id": "task_2",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                    {
                        "role": "denominator_1",
                        "concept": "operating_expense_total",
                        "period": "2023",
                        "label": "operating expense total",
                        "preferred_task_id": "task_3",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 employee benefits expense",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "2023 employee benefits expense",
                                "concept": "employee_benefits_expense",
                                "period": "2023",
                                "raw_value": "1,701,418,940",
                                "raw_unit": "KRW",
                                "normalized_value": 1701418940000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "1.7T KRW",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_3",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 operating expense total",
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "2023 operating expense total",
                                "concept": "operating_expense_total",
                                "period": "2023",
                                "raw_value": "8,181,823,307",
                                "raw_unit": "KRW",
                                "normalized_value": 8181823307000.0,
                                "normalized_unit": "KRW",
                                "rendered_value": "8.2T KRW",
                            },
                        },
                    },
                },
            ],
            "reconciliation_result": {},
            "reflection_plan": {},
            "retry_strategy": "",
        }

        strategy = agent._select_retry_strategy_for_reconciliation(
            state,
            {"status": "retry_retrieval", "missing_operands": []},
        )

        self.assertEqual(strategy, "synthesize_from_task_outputs")

    def test_report_scope_prefers_prior_year_receipt_for_multi_report_lookup(self) -> None:
        operand = {
            "label": "2022년 시설투자(CAPEX) 총액",
            "aliases": ["시설투자(CAPEX) 총액", "CAPEX 총액"],
            "role": "prior_period",
            "preferred_sections": ["시설투자 현황"],
            "binding_policy": {
                "prefer_value_roles": ["aggregate"],
                "prefer_aggregation_stages": ["final", "direct"],
            },
        }
        constraints = {
            "consolidation_scope": "consolidated",
            "period_focus": "current",
        }
        report_scope = {
            "company": "삼성전자",
            "year": 2023,
            "source_reports": [
                {"corp_name": "삼성전자", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240312000736"},
                {"corp_name": "삼성전자", "year": 2022, "report_type": "사업보고서", "rcept_no": "20230308000592"},
            ],
        }
        current_candidate = {
            "candidate_id": "cur_2023",
            "candidate_kind": "structured_value",
            "text": "시설투자 현황 합 계 531,139",
            "metadata": {
                "company": "삼성전자",
                "year": 2023,
                "rcept_no": "20240312000736",
                "statement_type": "business_overview",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "row_label": "합 계",
                "semantic_label": "시설투자(CAPEX) 총액",
                "value_role": "aggregate",
                "aggregation_stage": "final",
                "local_heading": "시설투자 현황",
                "section_path": "II. 사업의 내용 > 시설투자 현황",
                "period_labels": ["2023", "2022"],
                "table_source_id": "table_2023",
            },
        }
        prior_candidate = {
            "candidate_id": "cur_2022",
            "candidate_kind": "structured_value",
            "text": "시설투자 현황 합 계 531,153",
            "metadata": {
                "company": "삼성전자",
                "year": 2022,
                "rcept_no": "20230308000592",
                "statement_type": "business_overview",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "row_label": "합 계",
                "semantic_label": "시설투자(CAPEX) 총액",
                "value_role": "aggregate",
                "aggregation_stage": "final",
                "local_heading": "시설투자 현황",
                "section_path": "II. 사업의 내용 > 시설투자 현황",
                "period_labels": ["2022"],
                "table_source_id": "table_2022",
            },
        }

        current_score = _score_operand_candidate(
            current_candidate,
            operand=operand,
            preferred_statement_types=["business_overview"],
            constraints=constraints,
            query_years=[2023],
            report_scope=report_scope,
        )
        prior_score = _score_operand_candidate(
            prior_candidate,
            operand=operand,
            preferred_statement_types=["business_overview"],
            constraints=constraints,
            query_years=[2023],
            report_scope=report_scope,
        )

        self.assertGreater(prior_score, current_score)
        self.assertFalse(
            _candidate_is_direct_grounding_candidate(
                current_candidate,
                operand=operand,
                constraints=constraints,
                query_years=[2023],
                operation_family="lookup",
                report_scope=report_scope,
            )
        )
        self.assertTrue(
            _candidate_is_direct_grounding_candidate(
                prior_candidate,
                operand=operand,
                constraints=constraints,
                query_years=[2023],
                operation_family="lookup",
                report_scope=report_scope,
            )
        )

    def test_report_scope_allows_latest_comparative_prior_column(self) -> None:
        operand = {
            "label": "2022년 법인세비용차감전순이익",
            "aliases": ["법인세비용차감전순이익", "법인세비용차감전순손익"],
            "role": "prior_period",
            "preferred_sections": ["연결재무제표 주석"],
            "binding_policy": {
                "prefer_value_roles": ["detail", "aggregate"],
                "prefer_aggregation_stages": ["direct", "final", "subtotal"],
                "prefer_period_focus": "prior",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        constraints = {
            "consolidation_scope": "consolidated",
            "period_focus": "prior",
        }
        report_scope = {
            "company": "네이버",
            "year": 2023,
            "source_reports": [
                {"corp_name": "네이버", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240318000844"},
                {"corp_name": "네이버", "year": 2022, "report_type": "사업보고서", "rcept_no": "20230314001049"},
            ],
        }
        comparative_candidate = {
            "candidate_id": "tax_note_prior_column",
            "candidate_kind": "structured_value",
            "text": "법인세비용차감전순손익 1,083,717,091",
            "metadata": {
                "company": "네이버",
                "year": 2023,
                "rcept_no": "20240318000844",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "period_focus": "prior",
                "row_label": "법인세비용차감전순손익",
                "semantic_label": "법인세비용차감전순손익",
                "value_role": "detail",
                "aggregation_stage": "direct",
                "local_heading": "28. 법인세비용 (연결)",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석 > 28. 법인세용 (연결)",
                "period_labels": ["2023", "2022"],
                "table_source_id": "tax_note_2023",
            },
        }

        score = _score_operand_candidate(
            comparative_candidate,
            operand=operand,
            preferred_statement_types=["notes"],
            constraints=constraints,
            query_years=[2023],
            report_scope=report_scope,
        )

        self.assertGreater(score, 0.0)
        self.assertTrue(
            _candidate_is_direct_grounding_candidate(
                comparative_candidate,
                operand=operand,
                constraints=constraints,
                query_years=[2023],
                operation_family="lookup",
                report_scope=report_scope,
            )
        )

    def test_blank_business_table_unit_uses_local_report_unit_hint(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        candidate = {
            "candidate_id": "capex_2022",
            "metadata": {
                "statement_type": "business_overview",
                "row_label": "합 계",
                "chunk_uid": "20230308000592:18:3",
                "year": 2022,
            },
        }
        operand = {
            "label": "2022년 시설투자(CAPEX) 총액",
            "unit_family": "KRW",
        }
        selected_cell = {
            "column_headers": ["2022"],
            "value_text": "531,153",
            "unit_hint": "",
        }

        with patch("src.agent.financial_graph_reconciliation._resolve_candidate_local_unit_hint", return_value="억원"):
            unit = agent._structured_candidate_unit_hint(
                raw_value="531,153",
                raw_unit="",
                candidate=candidate,
                operand=operand,
                selected_cell=selected_cell,
            )

        self.assertEqual(unit, "억원")


    def test_table_row_candidates_expose_row_labels_for_operand_matching(self) -> None:
        candidates = _build_table_row_reconciliation_candidates(
            candidate_id_prefix="doc_1",
            anchor="[삼성전자 | 2023 | III. 재무에 관한 사항 > 1. 요약재무정보]",
            table_text="\n".join(
                [
                    "구분 | 2023 | 2022 | 단위: 백만원",
                    "부채총계 | 92,228,115 | 93,674,903 |",
                    "자본총계 | 363,677,865 | 354,749,604 |",
                ]
            ),
            metadata={
                "statement_type": "summary_financials",
                "consolidation_scope": "consolidated",
                "period_labels": ["2023", "2022"],
                "table_source_id": "table_001",
                "table_header_context": "구분 | 2023 | 2022 | 단위: 백만원",
                "table_summary_text": "구분 | 2023 | 2022 | 단위: 백만원\n부채총계 | 자본총계",
                "table_row_labels_text": "구분\n부채총계\n자본총계",
            },
        )

        self.assertGreaterEqual(len(candidates), 3)
        debt_candidate = next(candidate for candidate in candidates if candidate["metadata"].get("row_label") == "부채총계")
        equity_candidate = next(candidate for candidate in candidates if candidate["metadata"].get("row_label") == "자본총계")

        self.assertEqual(debt_candidate["candidate_kind"], "table_row")
        self.assertTrue(_candidate_matches_operand(debt_candidate, {"label": "부채총계", "aliases": ["총부채"]}))
        self.assertTrue(_candidate_matches_operand(equity_candidate, {"label": "자본총계", "aliases": ["총자본"]}))


    def test_structured_row_candidates_are_built_from_row_record_json(self) -> None:
        metadata = {
            "statement_type": "summary_financials",
            "consolidation_scope": "consolidated",
            "period_labels": ["2023", "2022"],
            "table_source_id": "table_001",
            "table_header_context": "구분 | 2023 | 2022 | 단위: 백만원",
            "table_summary_text": "구분 | 2023 | 2022 | 단위: 백만원\\n부채총계 | 자본총계",
            "table_row_labels_text": "구분\\n부채총계\\n자본총계",
            "table_row_records_json": json.dumps(
                [
                    {
                        "row_id": "r1",
                        "row_label": "부채총계",
                        "row_headers": ["부채총계"],
                        "cells": [
                            {"column_headers": ["2023"], "value_text": "92,228,115", "unit_hint": "백만원"},
                            {"column_headers": ["2022"], "value_text": "93,674,903", "unit_hint": "백만원"},
                        ],
                    }
                ],
                ensure_ascii=False,
            ),
        }
        candidates = _build_table_row_reconciliation_candidates(
            candidate_id_prefix="doc_2",
            anchor="[삼성전자 | 2023 | III. 재무에 관한 사항 > 1. 요약재무정보]",
            table_text="ignored fallback text",
            metadata=metadata,
        )

        candidate = next(item for item in candidates if item["candidate_kind"] == "structured_row")
        self.assertEqual(candidate["candidate_kind"], "structured_row")
        self.assertEqual(candidate["metadata"].get("row_headers"), ["부채총계"])
        self.assertTrue(_candidate_matches_operand(candidate, {"label": "부채총계", "aliases": ["총부채"]}))

    def test_raw_table_rows_are_retained_even_when_row_record_json_exists(self) -> None:
        metadata = {
            "statement_type": "notes",
            "consolidation_scope": "consolidated",
            "period_labels": ["당기", "전기"],
            "table_source_id": "table_229",
            "table_header_context": "공시금액 | 항목 | 값 | 단위: 천원",
            "table_summary_text": "법인세비용 관련 표",
            "table_row_records_json": json.dumps(
                [
                    {
                        "row_id": "r1",
                        "row_label": "법인세비용",
                        "row_headers": ["법인세비용"],
                        "cells": [
                            {"column_headers": ["당기"], "value_text": "496,378,555", "unit_hint": "천원"},
                            {"column_headers": ["전기"], "value_text": "410,536,791", "unit_hint": "천원"},
                        ],
                    }
                ],
                ensure_ascii=False,
            ),
        }
        table_text = "\n".join(
            [
                "공시금액 | 법인세비용 | 496,378,555",
                "공시금액 | 법인세비용차감전순손익 | 1,481,396,318",
                "공시금액 | 법인세비용차감전순손익 | 1,083,717,091",
            ]
        )

        candidates = _build_table_row_reconciliation_candidates(
            candidate_id_prefix="doc_229",
            anchor="[NAVER | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
            table_text=table_text,
            metadata=metadata,
        )

        raw_target_rows = [
            item
            for item in candidates
            if item["candidate_kind"] == "table_row"
            and "법인세비용차감전순손익" in str((item.get("metadata") or {}).get("row_text") or "")
        ]
        self.assertTrue(raw_target_rows)

    def test_structured_column_candidates_are_built_from_period_rows(self) -> None:
        metadata = {
            "statement_type": "summary_financials",
            "consolidation_scope": "consolidated",
            "period_labels": ["2023", "2022"],
            "table_source_id": "table_002",
            "table_header_context": "구분 | 부채총계 | 자본총계 | 단위: 백만원",
            "table_summary_text": "구분 | 부채총계 | 자본총계",
            "table_row_labels_text": "2023\n2022",
            "table_row_records_json": json.dumps(
                [
                    {
                        "row_id": "r1",
                        "row_label": "2023",
                        "row_headers": ["2023"],
                        "cells": [
                            {"column_headers": ["부채총계"], "value_text": "92,228,115", "unit_hint": "백만원"},
                            {"column_headers": ["자본총계"], "value_text": "363,677,865", "unit_hint": "백만원"},
                        ],
                    },
                    {
                        "row_id": "r2",
                        "row_label": "2022",
                        "row_headers": ["2022"],
                        "cells": [
                            {"column_headers": ["부채총계"], "value_text": "93,674,903", "unit_hint": "백만원"},
                            {"column_headers": ["자본총계"], "value_text": "354,749,604", "unit_hint": "백만원"},
                        ],
                    },
                ],
                ensure_ascii=False,
            ),
        }
        candidates = _build_table_row_reconciliation_candidates(
            candidate_id_prefix="doc_3",
            anchor="[삼성전자 | 2023 | III. 재무에 관한 사항 > 1. 요약재무정보]",
            table_text="ignored fallback text",
            metadata=metadata,
        )

        debt_candidate = next(item for item in candidates if item["candidate_kind"] == "structured_column_value" and item["metadata"].get("row_label") == "부채총계")
        self.assertTrue(_candidate_matches_operand(debt_candidate, {"label": "부채총계", "aliases": ["총부채"]}))
        self.assertEqual(
            [cell["column_headers"] for cell in debt_candidate["metadata"].get("structured_cells", [])],
            [["2023"], ["2022"]],
        )

    def test_structured_value_candidates_are_built_from_value_records(self) -> None:
        metadata = {
            "statement_type": "summary_financials",
            "consolidation_scope": "consolidated",
            "period_labels": ["2023", "2022"],
            "table_source_id": "table_003",
            "table_header_context": "구분 | 2023 | 2022 | 단위: 백만원",
            "table_summary_text": "구분 | 2023 | 2022 | 단위: 백만원\n부채총계 | 자본총계",
            "table_row_labels_text": "부채총계\n자본총계",
            "table_value_records_json": json.dumps(
                [
                    {
                        "value_id": "table_003:v:0:1",
                        "row_index": 0,
                        "column_index": 1,
                        "semantic_label": "부채총계",
                        "semantic_aliases": ["부채총계", "총부채"],
                        "label_source": "row",
                        "row_label": "부채총계",
                        "row_headers": ["부채총계"],
                        "column_headers": ["2023"],
                        "period_text": "2023",
                        "period_labels": ["2023"],
                        "value_text": "92,228,115",
                        "unit_hint": "백만원",
                    }
                ],
                ensure_ascii=False,
            ),
        }
        candidates = _build_table_row_reconciliation_candidates(
            candidate_id_prefix="doc_4",
            anchor="[삼성전자 | 2023 | III. 재무에 관한 사항 > 1. 요약재무정보]",
            table_text="ignored fallback text",
            metadata=metadata,
        )

        candidate = next(item for item in candidates if item["candidate_kind"] == "structured_value")
        self.assertEqual(candidate["metadata"].get("row_label"), "부채총계")
        self.assertTrue(_candidate_matches_operand(candidate, {"label": "부채총계", "aliases": ["총부채"]}))

    def test_final_aggregate_value_scores_above_subtotal_for_generic_operand(self) -> None:
        operand = {"label": "장기차입금", "aliases": ["장기 차입금", "장기차입금 합계"], "required": True}
        subtotal_candidate = {
            "candidate_id": "value_subtotal",
            "candidate_kind": "structured_value",
            "text": "장기차입금 합계 12,164,595",
            "metadata": {
                "row_label": "장기차입금 합계",
                "aggregate_role": "subtotal",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "period_labels": ["2023"],
                "structured_cells": [
                    {"column_headers": ["장기차입금 합계"], "value_text": "12,164,595", "unit_hint": "백만원"},
                ],
            },
        }
        final_candidate = {
            "candidate_id": "value_final",
            "candidate_kind": "structured_value",
            "text": "장기차입금 합계 10,121,033",
            "metadata": {
                "row_label": "장기차입금 합계",
                "aggregate_role": "final_total",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "period_labels": ["2023"],
                "structured_cells": [
                    {"column_headers": ["장기차입금 합계"], "value_text": "10,121,033", "unit_hint": "백만원"},
                ],
            },
        }

        subtotal_score = _score_operand_candidate(
            subtotal_candidate,
            operand=operand,
            preferred_statement_types=["notes"],
            constraints={"consolidation_scope": "consolidated"},
            query_years=[2023],
        )
        final_score = _score_operand_candidate(
            final_candidate,
            operand=operand,
            preferred_statement_types=["notes"],
            constraints={"consolidation_scope": "consolidated"},
            query_years=[2023],
        )

        self.assertGreater(final_score, subtotal_score)

    def test_lookup_accepts_unique_final_note_winner_for_long_term_borrowings(self) -> None:
        active_subtask = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "metric_label": "2023년 장기차입금",
            "operation_family": "lookup",
            "required_operands": [
                {
                    "label": "장기차입금",
                    "concept": "long_term_borrowings",
                    "aliases": ["장기 차입금", "장기차입금 합계"],
                    "role": "current_period",
                    "required": True,
                    "preferred_statement_types": ["notes"],
                    "binding_policy": {
                        "prefer_value_roles": ["aggregate", "detail"],
                        "prefer_aggregation_stages": ["final", "direct", "subtotal", "none"],
                        "prefer_period_focus": "current",
                        "prefer_consolidation_scope": "consolidated",
                    },
                }
            ],
            "preferred_statement_types": ["notes"],
            "constraints": {"consolidation_scope": "consolidated", "period_focus": "current"},
        }
        summary_candidate = {
            "candidate_id": "value_summary",
            "candidate_kind": "structured_value",
            "text": "장기차입금 10,121,033",
            "metadata": {
                "row_label": "장기차입금",
                "semantic_label": "장기차입금",
                "aggregate_role": "none",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["2023"],
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "10,121,033", "unit_hint": "백만원"},
                ],
            },
        }
        subtotal_candidate = {
            "candidate_id": "value_subtotal",
            "candidate_kind": "structured_value",
            "text": "장기차입금 합계 12,164,595",
            "metadata": {
                "row_label": "장기차입금 합계",
                "aggregate_role": "subtotal",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["2023"],
                "structured_cells": [
                    {"column_headers": ["장기차입금 합계"], "value_text": "12,164,595", "unit_hint": "백만원"},
                ],
            },
        }
        final_candidate = {
            "candidate_id": "value_final",
            "candidate_kind": "structured_value",
            "text": "장기차입금 합계 10,121,033",
            "metadata": {
                "row_label": "장기차입금 합계",
                "aggregate_role": "final_total",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["2023"],
                "structured_cells": [
                    {"column_headers": ["장기차입금 합계"], "value_text": "10,121,033", "unit_hint": "백만원"},
                ],
            },
        }

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=[summary_candidate, subtotal_candidate, final_candidate],
            years=[2023],
            reconciliation_retry_count=0,
        )

        self.assertEqual(result["status"], "ready")
        matched = result["matched_operands"][0]
        self.assertTrue(matched["matched"])
        self.assertEqual(matched["candidate_ids"][0], "value_final")

    def test_descriptor_structured_row_is_penalized_below_numeric_row(self) -> None:
        operand = {"label": "단기차입금", "aliases": [], "required": True}
        good_candidate = {
            "candidate_id": "row_good",
            "candidate_kind": "structured_row",
            "text": "단기차입금 4,145,647",
            "metadata": {
                "row_label": "단기차입금",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "period_labels": ["2023"],
                "table_source_id": "table_001",
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "4,145,647", "unit_hint": "백만원"},
                ],
            },
        }
        bad_candidate = {
            "candidate_id": "row_bad",
            "candidate_kind": "structured_row",
            "text": "하위범위 상위범위 범위 합계",
            "metadata": {
                "row_label": "하위범위",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "period_labels": ["2023"],
                "table_source_id": "table_001",
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "하위범위", "unit_hint": ""},
                    {"column_headers": ["2023"], "value_text": "상위범위", "unit_hint": ""},
                ],
            },
        }

        good_score = _score_operand_candidate(
            good_candidate,
            operand=operand,
            preferred_statement_types=["notes"],
            constraints={"consolidation_scope": "consolidated"},
            query_years=[2023],
        )
        bad_score = _score_operand_candidate(
            bad_candidate,
            operand=operand,
            preferred_statement_types=["notes"],
            constraints={"consolidation_scope": "consolidated"},
            query_years=[2023],
        )

        self.assertGreater(good_score, bad_score)

    def test_table_row_is_preferred_over_chunk_when_both_match(self) -> None:
        operand = {"label": "유형자산", "aliases": [], "required": True}
        table_row_candidate = {
            "candidate_id": "row_001",
            "candidate_kind": "table_row",
            "text": "유형자산 | 52,704,853 | 60,228,584",
            "metadata": {
                "row_label": "유형자산",
                "row_text": "유형자산 | 52,704,853 | 60,228,584",
                "statement_type": "balance_sheet",
                "consolidation_scope": "consolidated",
                "period_labels": ["2023", "2022"],
                "table_source_id": "table_bs",
            },
        }
        chunk_candidate = {
            "candidate_id": "chunk_001",
            "candidate_kind": "chunk",
            "text": "유형자산은 전기 대비 감소하였습니다. 유형자산 52,704,853 ...",
            "metadata": {
                "statement_type": "mda",
                "consolidation_scope": "consolidated",
                "period_labels": ["2023"],
            },
        }

        row_score = _score_operand_candidate(
            table_row_candidate,
            operand=operand,
            preferred_statement_types=["balance_sheet", "notes"],
            constraints={"consolidation_scope": "consolidated"},
            query_years=[2023],
        )
        chunk_score = _score_operand_candidate(
            chunk_candidate,
            operand=operand,
            preferred_statement_types=["balance_sheet", "notes"],
            constraints={"consolidation_scope": "consolidated"},
            query_years=[2023],
        )

        self.assertGreater(row_score, chunk_score)

    def test_consolidated_summary_row_is_preferred_over_separate_summary_row_for_aggregate_metric(self) -> None:
        operand = {"label": "유형자산", "aliases": [], "required": True}
        consolidated_candidate = {
            "candidate_id": "row_consolidated",
            "candidate_kind": "structured_row",
            "text": "ㆍ유형자산 제76기 52,704,853 제75기 60,228,528",
            "metadata": {
                "row_label": "ㆍ유형자산",
                "row_headers": ["ㆍ유형자산"],
                "statement_type": "summary_financials",
                "consolidation_scope": "unknown",
                "local_heading": "가. 요약연결재무정보",
                "section_path": "III. 재무에 관한 사항 > 1. 요약재무정보",
                "period_labels": ["제76기", "제75기"],
                "table_source_id": "table_consolidated",
                "structured_cells": [
                    {"column_headers": ["제76기"], "value_text": "52,704,853", "unit_hint": "백만원"},
                ],
            },
        }
        separate_candidate = {
            "candidate_id": "row_separate",
            "candidate_kind": "structured_row",
            "text": "ㆍ유형자산 제76기 38,974,277 제75기 43,151,324",
            "metadata": {
                "row_label": "ㆍ유형자산",
                "row_headers": ["ㆍ유형자산"],
                "statement_type": "summary_financials",
                "consolidation_scope": "unknown",
                "local_heading": "나. 요약 별도재무정보",
                "section_path": "III. 재무에 관한 사항 > 1. 요약재무정보",
                "period_labels": ["제76기", "제75기"],
                "table_source_id": "table_separate",
                "structured_cells": [
                    {"column_headers": ["제76기"], "value_text": "38,974,277", "unit_hint": "백만원"},
                ],
            },
        }

        consolidated_score = _score_operand_candidate(
            consolidated_candidate,
            operand=operand,
            preferred_statement_types=["balance_sheet", "summary_financials", "notes"],
            constraints={"consolidation_scope": "consolidated"},
            query_years=[2023],
        )
        separate_score = _score_operand_candidate(
            separate_candidate,
            operand=operand,
            preferred_statement_types=["balance_sheet", "summary_financials", "notes"],
            constraints={"consolidation_scope": "consolidated"},
            query_years=[2023],
        )

        self.assertGreater(consolidated_score, separate_score)

    def test_binding_policy_prefers_final_note_aggregate_over_detail_row_for_bonds(self) -> None:
        operand = {
            "label": "사채",
            "concept": "bonds_payable",
            "aliases": ["회사채", "원화일반사채"],
            "required": True,
            "preferred_sections": ["차입금 및 사채", "사채"],
            "preferred_statement_types": ["notes"],
            "binding_policy": {
                "prefer_value_roles": ["aggregate"],
                "prefer_aggregation_stages": ["final", "direct", "subtotal"],
                "avoid_value_roles": ["detail", "adjustment"],
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        detail_candidate = {
            "candidate_id": "bond_detail",
            "candidate_kind": "structured_value",
            "text": "사채 0",
            "metadata": {
                "row_label": "사채",
                "semantic_label": "사채",
                "aggregate_role": "none",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석 > 차입금 및 사채",
                "period_focus": "current",
                "period_labels": ["2023"],
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "0", "unit_hint": "백만원"},
                ],
            },
        }
        final_total_candidate = {
            "candidate_id": "bond_final",
            "candidate_kind": "structured_value",
            "text": "사채 합계 9,490,410",
            "metadata": {
                "row_label": "사채 합계",
                "semantic_label": "사채 합계",
                "aggregate_label": "사채 합계",
                "aggregate_role": "final_total",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석 > 차입금 및 사채",
                "period_focus": "current",
                "period_labels": ["2023"],
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "9,490,410", "unit_hint": "백만원"},
                ],
            },
        }

        detail_score = _score_operand_candidate(
            detail_candidate,
            operand=operand,
            preferred_statement_types=["notes"],
            constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
            query_years=[2023],
        )
        final_score = _score_operand_candidate(
            final_total_candidate,
            operand=operand,
            preferred_statement_types=["notes"],
            constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
            query_years=[2023],
        )

        self.assertGreater(final_score, detail_score)

    def test_lookup_accepts_unique_final_note_winner_for_bonds(self) -> None:
        active_subtask = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "metric_label": "2023년 사채",
            "operation_family": "lookup",
            "required_operands": [
                {
                    "label": "사채",
                    "concept": "bonds_payable",
                    "aliases": ["회사채", "원화일반사채"],
                    "role": "current_period",
                    "required": True,
                    "preferred_sections": ["차입금 및 사채", "사채"],
                    "preferred_statement_types": ["notes"],
                    "binding_policy": {
                        "prefer_value_roles": ["aggregate"],
                        "prefer_aggregation_stages": ["final", "direct", "subtotal"],
                        "avoid_value_roles": ["detail", "adjustment"],
                        "prefer_period_focus": "current",
                        "prefer_consolidation_scope": "consolidated",
                    },
                }
            ],
            "preferred_statement_types": ["notes"],
            "constraints": {"consolidation_scope": "consolidated", "period_focus": "current"},
        }
        detail_candidate = {
            "candidate_id": "bond_detail",
            "candidate_kind": "structured_value",
            "text": "사채 9,490,410",
            "metadata": {
                "row_label": "사채",
                "semantic_label": "사채",
                "aggregate_role": "none",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석 > 차입금 및 사채",
                "period_focus": "current",
                "period_labels": ["2023"],
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "9,490,410", "unit_hint": "백만원"},
                ],
            },
        }
        final_total_candidate = {
            "candidate_id": "bond_final",
            "candidate_kind": "structured_value",
            "text": "사채 합계 9,490,410",
            "metadata": {
                "row_label": "사채",
                "semantic_label": "사채",
                "semantic_aliases": ["사채", "회사채", "원화일반사채"],
                "aggregate_label": "사채 합계",
                "aggregate_role": "final_total",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석 > 차입금 및 사채",
                "period_focus": "current",
                "period_labels": ["2023"],
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "9,490,410", "unit_hint": "백만원"},
                ],
            },
        }

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=[detail_candidate, final_total_candidate],
            years=[2023],
            reconciliation_retry_count=0,
        )

        self.assertEqual(result["status"], "ready")
        matched = result["matched_operands"][0]
        self.assertTrue(matched["matched"])
        self.assertEqual(matched["candidate_ids"][0], "bond_final")

    def test_lookup_accepts_policy_surface_final_total_for_bonds(self) -> None:
        active_subtask = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "metric_label": "2023년 사채",
            "operation_family": "lookup",
            "required_operands": [
                {
                    "label": "사채",
                    "concept": "bonds_payable",
                    "aliases": ["회사채", "원화일반사채"],
                    "role": "current_period",
                    "required": True,
                    "preferred_sections": ["차입금 및 사채", "사채"],
                    "preferred_statement_types": ["notes"],
                    "binding_policy": {
                        "prefer_value_roles": ["aggregate", "detail"],
                        "prefer_aggregation_stages": ["final", "direct", "subtotal", "none"],
                        "prefer_period_focus": "current",
                        "prefer_consolidation_scope": "consolidated",
                    },
                }
            ],
            "preferred_statement_types": ["notes"],
            "constraints": {"consolidation_scope": "consolidated", "period_focus": "current"},
        }
        final_total_candidate = {
            "candidate_id": "bond_final_generic",
            "candidate_kind": "structured_value",
            "text": "차입금명칭 원화일반사채 외화일반사채 외화교환사채 차감 계 9,490,410",
            "metadata": {
                "row_label": "차감 계",
                "semantic_label": "차입금명칭 합계",
                "semantic_aliases": ["차입금명칭 합계", "차입금명칭", "차감 계"],
                "aggregate_label": "차입금명칭 합계",
                "aggregate_role": "final_total",
                "aggregation_stage": "final",
                "value_role": "aggregate",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석 > 차입금 및 사채",
                "period_focus": "current",
                "period_labels": ["2023"],
                "table_row_labels_text": "차입금명칭 원화일반사채 외화일반사채 외화교환사채 합계 차감 계",
                "structured_cells": [
                    {"column_headers": ["차입금명칭 합계"], "value_text": "9,490,410", "unit_hint": "백만원"},
                ],
            },
        }

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=[final_total_candidate],
            years=[2023],
            reconciliation_retry_count=1,
        )

        self.assertEqual(result["status"], "ready")
        matched = result["matched_operands"][0]
        self.assertTrue(matched["matched"])
        self.assertEqual(matched["candidate_ids"][0], "bond_final_generic")

    def test_note_aggregate_structured_value_beats_mixed_table_row_summary(self) -> None:
        operand = {
            "label": "장기차입금",
            "concept": "long_term_borrowings",
            "aliases": ["장기 차입금", "장기차입금 합계"],
            "required": True,
            "preferred_statement_types": ["notes"],
            "binding_policy": {
                "prefer_value_roles": ["aggregate", "detail"],
                "prefer_aggregation_stages": ["final", "direct", "subtotal", "none"],
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        mixed_summary_candidate = {
            "candidate_id": "summary_row",
            "candidate_kind": "table_row",
            "text": "장기차입금 | 10,121,033 | 장기차입금 | 9,073,567",
            "metadata": {
                "row_label": "장기차입금",
                "row_text": "장기차입금 | 10,121,033 | 장기차입금 | 9,073,567",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["당기"],
                "row_context_text": "x" * 3000,
                "table_source_id": "table_summary",
            },
        }
        final_note_candidate = {
            "candidate_id": "detail_final",
            "candidate_kind": "structured_value",
            "text": "차감 계, 장기차입금 10,121,033",
            "metadata": {
                "row_label": "차감 계, 장기차입금",
                "semantic_label": "장기차입금 합계",
                "semantic_aliases": ["장기차입금 합계", "장기차입금"],
                "aggregate_label": "장기차입금 합계",
                "aggregate_role": "final_total",
                "aggregation_stage": "final",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["2023"],
                "table_source_id": "table_95",
                "structured_cells": [
                    {"column_headers": ["차입금명칭", "장기 차입금", "장기차입금 합계"], "value_text": "10,121,033", "unit_hint": "백만원"},
                ],
            },
        }
        summary_score = _score_operand_candidate(
            mixed_summary_candidate,
            operand=operand,
            preferred_statement_types=["notes"],
            constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
            query_years=[2023],
        )
        final_score = _score_operand_candidate(
            final_note_candidate,
            operand=operand,
            preferred_statement_types=["notes"],
            constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
            query_years=[2023],
        )

        self.assertGreater(final_score, summary_score)

    def test_retry_queries_expand_to_aggregate_surface_for_note_lookup(self) -> None:
        active_subtask = {
            "metric_label": "2023년 장기차입금",
            "preferred_sections": ["차입금 및 사채"],
            "constraints": {"consolidation_scope": "consolidated"},
            "required_operands": [
                {
                    "label": "장기차입금",
                    "aliases": ["장기 차입금"],
                    "binding_policy": {
                        "prefer_value_roles": ["aggregate", "detail"],
                        "prefer_aggregation_stages": ["final", "direct", "subtotal", "none"],
                    },
                }
            ],
        }
        queries = _build_reconciliation_retry_queries(
            active_subtask=active_subtask,
            missing_operands=["장기차입금"],
            years=[2023],
        )

        self.assertTrue(any("장기차입금 합계" in query for query in queries))

    def test_retry_queries_do_not_duplicate_period_or_metric_surface(self) -> None:
        active_subtask = {
            "metric_label": "regional sales volume",
            "preferred_sections": ["Management discussion"],
            "constraints": {},
            "required_operands": [
                {
                    "label": "2023년 regional sales volume",
                    "aliases": ["regional sales volume"],
                    "role": "current_period",
                },
                {
                    "label": "2022년 regional sales volume",
                    "aliases": ["regional sales volume"],
                    "role": "prior_period",
                },
            ],
        }

        queries = _build_reconciliation_retry_queries(
            active_subtask=active_subtask,
            missing_operands=["2023년 regional sales volume", "2022년 regional sales volume"],
            years=[2023],
        )

        self.assertIn("2023년 regional sales volume", queries)
        self.assertIn("2023년 2022년 regional sales volume", queries)
        self.assertFalse(any("2023년 2023년" in query for query in queries))
        self.assertFalse(any("regional sales volume regional sales volume" in query for query in queries))

    def test_retry_queries_preserve_canonical_sections_for_statement_lookup(self) -> None:
        active_subtask = {
            "metric_label": "2023년 매출원가",
            "preferred_sections": ["연결재무제표 주석", "연결 손익계산서"],
            "constraints": {"consolidation_scope": "consolidated"},
            "required_operands": [
                {
                    "label": "매출원가",
                    "concept": "cost_of_sales",
                    "aliases": ["매출 원가"],
                    "preferred_sections": ["연결 손익계산서", "손익계산서", "요약재무정보"],
                }
            ],
        }
        queries = _build_reconciliation_retry_queries(
            active_subtask=active_subtask,
            missing_operands=["매출원가"],
            years=[2023],
        )

        self.assertTrue(any("연결 손익계산서" in query for query in queries))
        self.assertTrue(any("손익계산서" in query for query in queries))
        self.assertFalse(any("연결재무제표 주석" in query for query in queries if "매출원가" in query))

    def test_lookup_producer_inherits_ontology_aggregate_query_surfaces(self) -> None:
        consumer_task = {
            "query": "2023년 유·무형자산 총합 대비 차입금 비중을 계산해 줘.",
            "metric_label": "유·무형자산 대비 차입금 비중",
            "preferred_sections": ["차입금 및 사채", "연결재무제표 주석"],
            "preferred_statement_types": ["notes", "balance_sheet"],
            "constraints": {"consolidation_scope": "consolidated", "period_focus": "current"},
            "required_operands": [
                {
                    "label": "장기차입금",
                    "concept": "long_term_borrowings",
                    "aliases": ["장기 차입금"],
                    "role": "numerator_2",
                    "preferred_sections": ["차입금 및 사채"],
                    "preferred_statement_types": ["notes"],
                    "binding_policy": {
                        "prefer_value_roles": ["aggregate", "detail"],
                        "prefer_aggregation_stages": ["final", "direct", "subtotal", "none"],
                    },
                }
            ],
        }
        binding = {
            "role": "numerator_2",
            "concept": "long_term_borrowings",
            "period": "2023",
        }
        task = _build_lookup_producer_task_from_binding(
            binding=binding,
            consumer_task=consumer_task,
            next_task_id="task_lookup",
            report_scope={"year": 2023, "company": "SK하이닉스"},
        )

        retrieval_queries = list(task.get("retrieval_queries") or [])
        self.assertTrue(any("장기차입금 합계" in query for query in retrieval_queries))
        self.assertTrue(any("차감 계, 장기차입금" in query for query in retrieval_queries))

    def test_lookup_producer_preserves_explicit_dependency_aggregate_policy(self) -> None:
        consumer_task = {
            "query": "2023년 무형자산상각비가 영업이익률을 얼마나 낮추었는지 계산해 줘.",
            "metric_label": "영업이익률 감소 영향",
            "operation_family": "ratio",
            "required_operands": [
                {
                    "label": "매출액",
                    "concept": "revenue",
                    "role": "denominator",
                    "binding_policy": {
                        "prefer_value_roles": ["aggregate"],
                        "prefer_aggregation_stages": ["final", "subtotal", "direct"],
                    },
                }
            ],
            "constraints": {"consolidation_scope": "consolidated", "period_focus": "current"},
        }
        binding = {
            "role": "denominator",
            "concept": "revenue",
            "period": "2023",
            "label": "매출액",
            "binding_policy": {
                "prefer_value_roles": ["aggregate"],
                "prefer_aggregation_stages": ["final", "subtotal", "direct"],
            },
        }

        task = _build_lookup_producer_task_from_binding(
            binding=binding,
            consumer_task=consumer_task,
            next_task_id="task_lookup",
            report_scope={"year": 2023, "company": "셀트리온"},
        )

        policy = task["required_operands"][0]["binding_policy"]
        self.assertEqual(policy["prefer_value_roles"], ["aggregate"])
        self.assertEqual(policy["prefer_aggregation_stages"], ["final", "subtotal", "direct"])

    def test_balance_sheet_aggregate_prefers_canonical_statement_aggregate_over_note_detail(self) -> None:
        operand = {
            "label": "유형자산",
            "concept": "property_plant_equipment",
            "aliases": ["유형자산"],
            "required": True,
            "preferred_statement_types": ["summary_financials", "balance_sheet"],
            "binding_policy": {
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        canonical_candidate = {
            "candidate_id": "ppe_summary",
            "candidate_kind": "structured_value",
            "text": "유형자산 52,704,853",
            "metadata": {
                "row_label": "유형자산",
                "semantic_label": "유형자산",
                "aggregate_label": "유형자산",
                "aggregate_role": "direct_total",
                "statement_type": "summary_financials",
                "consolidation_scope": "consolidated",
                "section_path": "III. 재무에 관한 사항 > 1. 요약재무정보",
                "period_focus": "current",
                "period_labels": ["2023", "2022"],
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "52,704,853", "unit_hint": "백만원"},
                    {"column_headers": ["2022"], "value_text": "48,123,111", "unit_hint": "백만원"},
                ],
            },
        }
        note_detail_candidate = {
            "candidate_id": "ppe_note_detail",
            "candidate_kind": "structured_value",
            "text": "공시금액 유형자산 7,691",
            "metadata": {
                "row_label": "공시금액 유형자산",
                "semantic_label": "공시금액 유형자산",
                "aggregate_role": "none",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "period_focus": "current",
                "period_labels": ["2023"],
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "7,691", "unit_hint": "백만원"},
                ],
            },
        }

        canonical_score = _score_operand_candidate(
            canonical_candidate,
            operand=operand,
            preferred_statement_types=["summary_financials", "balance_sheet", "notes"],
            constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
            query_years=[2023],
        )
        note_detail_score = _score_operand_candidate(
            note_detail_candidate,
            operand=operand,
            preferred_statement_types=["summary_financials", "balance_sheet", "notes"],
            constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
            query_years=[2023],
        )

        self.assertGreater(canonical_score, note_detail_score)

    def test_reconcile_preserves_direct_grounding_candidate_even_if_not_in_top_three(self) -> None:
        active_subtask = {
            "task_id": "task_lookup",
            "metric_family": "concept_lookup",
            "metric_label": "법인세비용차감전순이익",
            "query": "2023년 연결 손익계산서에서 법인세비용차감전순이익을 찾아줘",
            "operation_family": "lookup",
            "required_operands": [
                {
                    "label": "법인세비용차감전순이익",
                    "aliases": ["세전이익"],
                    "concept": "income_before_income_taxes",
                    "role": "current_period",
                    "required": True,
                    "period_hint": "2023",
                }
            ],
            "preferred_statement_types": ["income_statement", "summary_financials"],
            "constraints": {
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "entity_scope": "company",
                "segment_scope": "none",
            },
        }
        narrative_candidates = []
        for index in range(3):
            narrative_candidates.append(
                {
                    "candidate_id": f"chunk_narrative_{index}",
                    "candidate_kind": "chunk",
                    "text": f"법인세비용차감전순이익 관련 서술 {index}",
                    "metadata": {
                        "statement_type": "income_statement",
                        "consolidation_scope": "consolidated",
                        "period_labels": ["2023"],
                    },
                }
            )
        direct_candidate = {
            "candidate_id": "chunk_direct::value:0",
            "candidate_kind": "structured_value",
            "text": "법인세비용차감전순이익 1,481,396,317,551",
            "metadata": {
                "semantic_label": "법인세비용차감전순이익",
                "semantic_aliases": ["법인세비용차감전순이익", "세전이익"],
                "row_label": "법인세비용차감전순이익",
                "statement_type": "income_statement",
                "consolidation_scope": "consolidated",
                "period_labels": ["2023", "2022"],
                "period_focus": "current",
                "table_source_id": "table_direct",
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "1,481,396,317,551", "unit_hint": "원"},
                ],
            },
        }
        self.assertTrue(
            _candidate_is_direct_grounding_candidate(
                direct_candidate,
                operand=active_subtask["required_operands"][0],
                constraints=active_subtask["constraints"],
                query_years=[2023],
                operation_family="lookup",
            )
        )

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=[*narrative_candidates, direct_candidate],
            years=[2023],
            reconciliation_retry_count=0,
        )

        candidate_ids = result["matched_operands"][0]["candidate_ids"]
        self.assertIn("chunk_direct::value:0", candidate_ids)

    def test_current_period_binding_penalizes_delta_like_row_below_absolute_row(self) -> None:
        operand = {
            "label": "2023년 법인세비용차감전순이익",
            "concept": "income_before_income_taxes",
            "aliases": [
                "법인세비용차감전순이익",
                "법인세비용 차감 전 순이익",
                "법인세비용 차감 전 당기순손익",
            ],
            "role": "current_period",
            "required": True,
        }
        absolute_candidate = {
            "candidate_id": "ibt_absolute",
            "candidate_kind": "structured_value",
            "text": "법인세비용차감전순이익 1,481,396,317,551",
            "metadata": {
                "row_label": "법인세비용차감전순이익",
                "semantic_label": "법인세비용차감전순이익",
                "statement_type": "income_statement",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["2023", "2022"],
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "1,481,396,317,551", "unit_hint": "원"},
                ],
            },
        }
        delta_candidate = {
            "candidate_id": "ibt_delta",
            "candidate_kind": "structured_value",
            "text": "법인세비용차감전순이익 증가(감소) 71,156,179",
            "metadata": {
                "row_label": "법인세비용차감전순이익 증가(감소)",
                "semantic_label": "법인세비용차감전순이익 증가(감소)",
                "statement_type": "income_statement",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["2023", "2022"],
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "71,156,179", "unit_hint": "원"},
                ],
            },
        }

        absolute_score = _score_operand_candidate(
            absolute_candidate,
            operand=operand,
            preferred_statement_types=["income_statement", "summary_financials", "notes"],
            constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
            query_years=[2023],
        )
        delta_score = _score_operand_candidate(
            delta_candidate,
            operand=operand,
            preferred_statement_types=["income_statement", "summary_financials", "notes"],
            constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
            query_years=[2023],
        )

        self.assertGreater(absolute_score, delta_score)

    def test_percent_metric_multi_period_row_scores_above_single_period_note_row(self) -> None:
        operand = {
            "label": "2023년 순이자마진",
            "concept": "net_interest_margin",
            "aliases": ["순이자마진", "NIM"],
            "role": "current_period",
            "required": True,
            "period_hint": "2023",
            "unit_family": "PERCENT",
            "preferred_statement_types": ["mda", "summary_financials", "notes"],
            "binding_policy": {
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        multi_period_candidate = {
            "candidate_id": "nim_multi",
            "candidate_kind": "structured_value",
            "text": "순이자마진 2023 1.83 2022 1.73",
            "metadata": {
                "row_label": "순이자마진",
                "semantic_label": "순이자마진",
                "semantic_aliases": ["순이자마진", "NIM"],
                "statement_type": "mda",
                "consolidation_scope": "consolidated",
                "section_path": "II. 사업의 내용 > 영업의 개황",
                "period_labels": ["2023", "2022"],
                "table_source_id": "nim_table",
                "structured_cells": [
                    {"column_headers": ["2023", "NIM"], "value_text": "1.83", "unit_hint": "%", "period_text": "2023"},
                    {"column_headers": ["2022", "NIM"], "value_text": "1.73", "unit_hint": "%", "period_text": "2022"},
                ],
            },
        }
        single_period_note_candidate = {
            "candidate_id": "nim_note_single",
            "candidate_kind": "structured_value",
            "text": "순이자마진 1.83",
            "metadata": {
                "row_label": "순이자마진",
                "semantic_label": "순이자마진",
                "semantic_aliases": ["순이자마진", "NIM"],
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "period_labels": ["2023"],
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "1.83", "unit_hint": "%", "period_text": "2023"},
                ],
            },
        }

        multi_score = _score_operand_candidate(
            multi_period_candidate,
            operand=operand,
            preferred_statement_types=["mda", "summary_financials", "notes"],
            constraints={"consolidation_scope": "consolidated", "period_focus": "multi_period"},
            query_years=[2023, 2022],
        )
        single_score = _score_operand_candidate(
            single_period_note_candidate,
            operand=operand,
            preferred_statement_types=["mda", "summary_financials", "notes"],
            constraints={"consolidation_scope": "consolidated", "period_focus": "multi_period"},
            query_years=[2023, 2022],
        )

        self.assertGreater(multi_score, single_score)

    def test_pretax_income_operand_rejects_continuing_income_surrogate_candidate(self) -> None:
        operand = {
            "label": "2023년 법인세비용차감전순이익",
            "concept": "income_before_income_taxes",
            "aliases": [
                "법인세비용차감전순이익",
                "법인세비용차감전순손익",
                "세전이익",
            ],
            "role": "current_period",
            "required": True,
        }
        surrogate_candidate = {
            "candidate_id": "surrogate_continuing_income",
            "candidate_kind": "chunk",
            "text": "2023년 연결 손익계산서에서 법인세비용차감전순이익에 해당하는 계속영업순이익은 985,018백만원입니다.",
            "metadata": {
                "row_label": "계속영업순이익",
                "semantic_label": "계속영업순이익",
                "statement_type": "summary_financials",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["2023", "2022"],
            },
        }

        self.assertFalse(_candidate_matches_operand(surrogate_candidate, operand))
        self.assertLess(
            _score_operand_candidate(
                surrogate_candidate,
                operand=operand,
                preferred_statement_types=["income_statement", "summary_financials", "notes"],
                constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
                query_years=[2023],
            ),
            0.0,
        )

    def test_nim_operand_rejects_bank_plus_card_variant_candidate(self) -> None:
        operand = {
            "label": "2023년 순이자마진",
            "concept": "net_interest_margin",
            "aliases": ["순이자마진", "NIM"],
            "role": "current_period",
            "required": True,
            "unit_family": "PERCENT",
            "surface_contract": {
                "positive": ["명목순이자마진", "순이자마진"],
                "negative": ["NIM(은행+카드)", "은행+카드"],
            },
        }
        surrogate_candidate = {
            "candidate_id": "nim_bank_card_variant",
            "candidate_kind": "structured_value",
            "text": "NIM(은행+카드) 2.44 0.13 2.30",
            "metadata": {
                "row_label": "NIM(은행+카드)",
                "semantic_label": "NIM(은행+카드)",
                "semantic_aliases": ["NIM(은행+카드)"],
                "statement_type": "mda",
                "consolidation_scope": "consolidated",
                "period_focus": "multi_period",
                "period_labels": ["2023", "2022"],
            },
        }

        self.assertFalse(_candidate_matches_operand(surrogate_candidate, operand))
        self.assertLess(
            _score_operand_candidate(
                surrogate_candidate,
                operand=operand,
                preferred_statement_types=["mda", "summary_financials", "notes"],
                constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
                query_years=[2023, 2022],
            ),
            0.0,
        )


    def test_segment_scoped_sum_prefers_segment_revenue_row_over_company_total_row(self) -> None:
        operand = {
            "label": "SDC 매출액",
            "concept": "revenue",
            "aliases": ["SDC", "매출액"],
            "role": "addend_1",
            "required": True,
            "binding_policy": {
                "segment_label": "SDC",
                "prefer_consolidation_scope": "consolidated",
                "prefer_period_focus": "current",
            },
            "preferred_statement_types": ["notes", "mda", "summary_financials"],
        }
        segment_candidate = {
            "candidate_id": "segment_sdc_revenue",
            "candidate_kind": "structured_value",
            "text": "SDC | 매출액 | 25,000,000",
            "metadata": {
                "row_label": "SDC",
                "semantic_label": "SDC 매출액",
                "semantic_aliases": ["SDC", "매출액"],
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "section_path": "II. 사업의 내용 > 매출 및 수주상황",
                "period_focus": "current",
                "period_labels": ["2024"],
                "table_source_id": "segment_table",
                "structured_cells": [
                    {"column_headers": ["2024", "매출액"], "value_text": "25,000,000", "unit_hint": "백만원"},
                ],
            },
        }
        total_candidate = {
            "candidate_id": "company_total_revenue",
            "candidate_kind": "structured_value",
            "text": "매출액 300,870,903",
            "metadata": {
                "row_label": "매출액",
                "semantic_label": "매출액",
                "semantic_aliases": ["Revenue", "매출"],
                "statement_type": "summary_financials",
                "consolidation_scope": "consolidated",
                "section_path": "III. 재무에 관한 사항 > 1. 요약재무정보",
                "period_focus": "current",
                "period_labels": ["2024"],
                "table_source_id": "summary_revenue_table",
                "structured_cells": [
                    {"column_headers": ["2024"], "value_text": "300,870,903", "unit_hint": "백만원"},
                ],
            },
        }

        segment_score = _score_operand_candidate(
            segment_candidate,
            operand=operand,
            preferred_statement_types=["notes", "mda", "summary_financials"],
            constraints={"consolidation_scope": "consolidated", "period_focus": "current", "segment_scope": "segment"},
            query_years=[2024],
        )
        total_score = _score_operand_candidate(
            total_candidate,
            operand=operand,
            preferred_statement_types=["notes", "mda", "summary_financials"],
            constraints={"consolidation_scope": "consolidated", "period_focus": "current", "segment_scope": "segment"},
            query_years=[2024],
        )

        self.assertGreater(segment_score, total_score)
        self.assertTrue(
            _candidate_is_direct_grounding_candidate(
                segment_candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current", "segment_scope": "segment"},
                query_years=[2024],
                operation_family="sum",
            )
        )
        self.assertFalse(
            _candidate_is_direct_grounding_candidate(
                total_candidate,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current", "segment_scope": "segment"},
                query_years=[2024],
                operation_family="sum",
            )
        )

    def test_segment_sum_reconcile_splits_sdc_and_harman_addends(self) -> None:
        active_subtask = {
            "task_id": "task_sum_segments",
            "metric_family": "concept_sum",
            "metric_label": "SDC와 Harman 부문 매출 합계",
            "query": "삼성전자 2024 사업보고서에서 SDC와 Harman 부문의 매출 합계는 얼마인가요?",
            "operation_family": "sum",
            "required_operands": [
                {
                    "label": "SDC 매출액",
                    "aliases": ["SDC", "매출액"],
                    "concept": "revenue",
                    "role": "addend_1",
                    "required": True,
                    "binding_policy": {"segment_label": "SDC", "prefer_consolidation_scope": "consolidated"},
                },
                {
                    "label": "Harman 매출액",
                    "aliases": ["Harman", "매출액"],
                    "concept": "revenue",
                    "role": "addend_2",
                    "required": True,
                    "binding_policy": {"segment_label": "Harman", "prefer_consolidation_scope": "consolidated"},
                },
            ],
            "preferred_statement_types": ["notes", "mda", "summary_financials"],
            "constraints": {
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "entity_scope": "company",
                "segment_scope": "segment",
            },
        }
        candidates = [
            {
                "candidate_id": "company_total_revenue",
                "candidate_kind": "structured_value",
                "text": "매출액 300,870,903",
                "metadata": {
                    "row_label": "매출액",
                    "semantic_label": "매출액",
                    "statement_type": "summary_financials",
                    "consolidation_scope": "consolidated",
                    "section_path": "III. 재무에 관한 사항 > 1. 요약재무정보",
                    "period_focus": "current",
                    "period_labels": ["2024"],
                    "table_source_id": "summary_revenue_table",
                    "structured_cells": [{"column_headers": ["2024"], "value_text": "300,870,903", "unit_hint": "백만원"}],
                },
            },
            {
                "candidate_id": "segment_sdc_revenue",
                "candidate_kind": "structured_value",
                "text": "SDC | 매출액 | 24,200,000",
                "metadata": {
                    "row_label": "SDC",
                    "semantic_label": "SDC 매출액",
                    "semantic_aliases": ["SDC", "매출액"],
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "section_path": "II. 사업의 내용 > 매출 및 수주상황",
                    "period_focus": "current",
                    "period_labels": ["2024"],
                    "table_source_id": "segment_revenue_table",
                    "structured_cells": [{"column_headers": ["2024", "매출액"], "value_text": "24,200,000", "unit_hint": "백만원"}],
                },
            },
            {
                "candidate_id": "segment_harman_revenue",
                "candidate_kind": "structured_value",
                "text": "Harman | 매출액 | 19,232,700",
                "metadata": {
                    "row_label": "Harman",
                    "semantic_label": "Harman 매출액",
                    "semantic_aliases": ["Harman", "매출액"],
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "section_path": "II. 사업의 내용 > 매출 및 수주상황",
                    "period_focus": "current",
                    "period_labels": ["2024"],
                    "table_source_id": "segment_revenue_table",
                    "structured_cells": [{"column_headers": ["2024", "매출액"], "value_text": "19,232,700", "unit_hint": "백만원"}],
                },
            },
        ]

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=[2024],
            reconciliation_retry_count=0,
        )

        self.assertEqual(result["status"], "ready")
        match_map = {
            (item["label"], item["role"]): item["candidate_ids"][0]
            for item in result["matched_operands"]
        }
        self.assertEqual(match_map[("SDC 매출액", "addend_1")], "segment_sdc_revenue")
        self.assertEqual(match_map[("Harman 매출액", "addend_2")], "segment_harman_revenue")

    def test_segment_lookup_reconcile_filters_company_total_when_segment_row_exists(self) -> None:
        active_subtask = {
            "task_id": "task_growth_current",
            "metric_family": "concept_lookup",
            "metric_label": "2023년 커머스 매출액",
            "query": "네이버 2023년 커머스 부문의 매출은 얼마인가요?",
            "operation_family": "lookup",
            "required_operands": [
                {
                    "label": "2023년 커머스 매출액",
                    "aliases": ["커머스", "매출액", "매출", "영업수익"],
                    "concept": "revenue",
                    "role": "primary",
                    "required": True,
                    "binding_policy": {
                        "segment_label": "커머스",
                        "prefer_consolidation_scope": "consolidated",
                        "prefer_period_focus": "current",
                    },
                    "preferred_statement_types": ["notes", "mda", "summary_financials"],
                }
            ],
            "preferred_statement_types": ["notes", "mda", "summary_financials"],
            "constraints": {
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "entity_scope": "company",
                "segment_scope": "segment",
            },
        }
        total_candidate = {
            "candidate_id": "company_total_revenue",
            "candidate_kind": "structured_value",
            "text": "영업수익 9,670,600",
            "metadata": {
                "row_label": "영업수익",
                "semantic_label": "영업수익",
                "semantic_aliases": ["영업수익", "매출액", "매출"],
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "section_path": "II. 사업의 내용 > 4. 매출 및 수주상황",
                "local_heading": "가. 부문별 매출실적 > (2) 서비스별 영업현황",
                "table_row_labels_text": "영업수익 | - 서치플랫폼 | - 커머스 | - 핀테크",
                "table_context": "서비스별 영업현황",
                "period_focus": "current",
                "period_labels": ["2023", "2022"],
                "table_source_id": "segment_revenue_table",
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "9,670,600", "unit_hint": "백만원"},
                ],
            },
        }
        segment_candidate = {
            "candidate_id": "segment_commerce_revenue",
            "candidate_kind": "structured_value",
            "text": "- 커머스 2,546,649",
            "metadata": {
                "row_label": "- 커머스",
                "semantic_label": "- 커머스",
                "semantic_aliases": ["커머스"],
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "section_path": "II. 사업의 내용 > 4. 매출 및 수주상황",
                "local_heading": "가. 부문별 매출실적 > (2) 서비스별 영업현황",
                "table_row_labels_text": "영업수익 | - 서치플랫폼 | - 커머스 | - 핀테크",
                "table_context": "서비스별 영업현황",
                "period_focus": "current",
                "period_labels": ["2023", "2022"],
                "table_source_id": "segment_revenue_table",
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "2,546,649", "unit_hint": "백만원"},
                ],
            },
        }

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=[total_candidate, segment_candidate],
            years=[2023, 2022],
            reconciliation_retry_count=0,
        )

        self.assertEqual(result["status"], "ready")
        matched = result["matched_operands"][0]
        self.assertEqual(matched["reason"], "matched_direct_candidate")
        self.assertEqual(matched["candidate_ids"][0], "segment_commerce_revenue")
        self.assertNotIn("company_total_revenue", matched["candidate_ids"][:1])

    def test_capex_total_prefers_business_section_aggregate_over_cash_flow_acquisition(self) -> None:
        operand = {
            "label": "시설투자(CAPEX)",
            "concept": "capital_expenditure_total",
            "aliases": ["시설투자", "CAPEX", "CapEx"],
            "required": True,
            "preferred_sections": ["원재료 및 생산설비", "시설투자", "사업의 내용"],
            "preferred_statement_types": [],
            "binding_policy": {
                "prefer_value_roles": ["aggregate", "detail"],
                "prefer_aggregation_stages": ["final", "direct", "subtotal", "none"],
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
            "surface_contract": {
                "positive": ["시설투자", "CAPEX", "CapEx", "자본적 지출"],
                "negative": ["유형자산의 취득", "유형자산 취득"],
            },
        }
        business_candidate = {
            "candidate_id": "capex_business_total",
            "candidate_kind": "structured_value",
            "text": "합 계 531,139",
            "metadata": {
                "row_label": "합 계",
                "semantic_label": "합 계",
                "aggregate_label": "합 계",
                "aggregate_role": "final_total",
                "statement_type": "unknown",
                "consolidation_scope": "unknown",
                "section_path": "II. 사업의 내용 > 3. 원재료 및 생산설비",
                "local_heading": "II. 사업의 내용 > 3. 원재료 및 생산설비",
                "period_focus": "multi_period",
                "period_labels": ["2023", "2022"],
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "531,139", "unit_hint": "억원"},
                    {"column_headers": ["2022"], "value_text": "531,153", "unit_hint": "억원"},
                ],
            },
        }
        cash_flow_candidate = {
            "candidate_id": "capex_cash_flow",
            "candidate_kind": "structured_value",
            "text": "유형자산의 취득 (57,611,292)",
            "metadata": {
                "row_label": "유형자산의 취득",
                "semantic_label": "유형자산의 취득",
                "aggregate_role": "none",
                "statement_type": "cash_flow",
                "consolidation_scope": "consolidated",
                "section_path": "III. 재무에 관한 사항 > 2. 연결재무제표",
                "local_heading": "III. 재무에 관한 사항 > 2. 연결재무제표",
                "period_focus": "multi_period",
                "period_labels": ["2023", "2022"],
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "(57,611,292)", "unit_hint": "백만원"},
                    {"column_headers": ["2022"], "value_text": "(49,430,428)", "unit_hint": "백만원"},
                ],
            },
        }

        business_score = _score_operand_candidate(
            business_candidate,
            operand=operand,
            preferred_statement_types=[],
            constraints={"consolidation_scope": "unknown", "period_focus": "current"},
            query_years=[2023, 2022],
        )
        cash_flow_score = _score_operand_candidate(
            cash_flow_candidate,
            operand=operand,
            preferred_statement_types=[],
            constraints={"consolidation_scope": "unknown", "period_focus": "current"},
            query_years=[2023, 2022],
        )

        self.assertGreater(business_score, cash_flow_score)

    def test_capex_total_accepts_aggregate_table_row_from_business_section(self) -> None:
        operand = {
            "label": "시설투자(CAPEX)",
            "aliases": ["시설투자", "CAPEX", "CapEx", "시설투자 총액"],
            "concept": "capital_expenditure_total",
            "role": "current_period",
            "preferred_sections": ["원재료 및 생산설비", "시설투자", "사업의 내용"],
            "surface_contract": {
                "positive": ["시설투자", "CAPEX", "CapEx", "자본적 지출"],
                "negative": ["유형자산의 취득", "유형자산 취득"],
            },
            "binding_policy": {
                "prefer_value_roles": ["aggregate", "detail"],
                "prefer_aggregation_stages": ["final", "direct", "subtotal", "none"],
            },
        }
        candidates = _build_table_row_reconciliation_candidates(
            candidate_id_prefix="doc_capex",
            anchor="[삼성전자 | 2023 | II. 사업의 내용 > 3. 원재료 및 생산설비]",
            table_text="\n".join(
                [
                    "구 분 | 내 용 | 투자기간 | 대상자산 | 투자액",
                    "DS 부문 | 신ㆍ증설, 보완 등 | 2023.01~2023.12 | 건물ㆍ설비 등 | 483,723",
                    "SDC | 신ㆍ증설, 보완 등 | 2023.01~2023.12 | 건물ㆍ설비 등 | 23,856",
                    "기 타 | 신ㆍ증설, 보완 등 | 2023.01~2023.12 | 건물ㆍ설비 등 | 23,560",
                    "합 계 | 합 계 | 합 계 | 합 계 | 531,139",
                ]
            ),
            metadata={
                "statement_type": "unknown",
                "consolidation_scope": "consolidated",
                "period_labels": ["2023"],
                "table_source_id": "table_capex",
                "section_path": "II. 사업의 내용 > 3. 원재료 및 생산설비",
                "table_context": "(시설투자 현황) 2023년 중 DS 부문 및 SDC 등의 첨단공정 증설ㆍ전환과 인프라 투자를 중심으로 53.1조원의 시설투자가 이루어졌습니다.",
                "table_header_context": "구 분 | 내 용 | 투자기간 | 대상자산 | 투자액",
            },
        )

        aggregate_row = next(
            candidate
            for candidate in candidates
            if candidate["candidate_kind"] == "table_row"
            and str((candidate.get("metadata") or {}).get("row_label") or "") == "합 계"
        )

        self.assertTrue(_candidate_matches_operand(aggregate_row, operand))
        self.assertTrue(
            _candidate_is_direct_grounding_candidate(
                aggregate_row,
                operand=operand,
                constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
                query_years=[2023],
                operation_family="lookup",
            )
        )

        revenue_total = {
            "candidate_id": "rev_total",
            "candidate_kind": "table_row",
            "text": "합 계 | 합 계 | 합 계 | 2,589,355",
            "metadata": {
                "row_text": "합 계 | 합 계 | 합 계 | 2,589,355",
                "row_label": "합 계",
                "structured_cells": [{"column_headers": ["제55기"], "value_text": "2,589,355", "unit_hint": "억원"}],
                "aggregate_label": "합 계",
                "aggregate_role": "final_total",
                "value_role": "aggregate",
                "aggregation_stage": "final",
                "section_path": "II. 사업의 내용 > 4. 매출 및 수주상황",
                "table_context": "2023년 매출은 258조 9,355억원으로 전년 대비 14.3% 감소하였습니다.",
            },
        }
        self.assertFalse(_candidate_matches_operand(revenue_total, operand))

    def test_deterministic_reconcile_prioritizes_direct_candidate_ids(self) -> None:
        active_subtask = {
            "task_id": "task_capex",
            "metric_family": "concept_lookup",
            "metric_label": "2023년 시설투자(CAPEX) 총액",
            "operation_family": "lookup",
            "required_operands": [
                {
                    "label": "시설투자(CAPEX)",
                    "aliases": ["시설투자", "CAPEX", "CapEx"],
                    "concept": "capital_expenditure_total",
                    "role": "current_period",
                    "required": True,
                    "preferred_sections": ["원재료 및 생산설비", "시설투자", "사업의 내용"],
                    "binding_policy": {
                        "prefer_value_roles": ["aggregate", "detail"],
                        "prefer_aggregation_stages": ["final", "direct", "subtotal", "none"],
                    },
                    "surface_contract": {
                        "positive": ["시설투자", "CAPEX", "CapEx", "자본적 지출"],
                        "negative": ["유형자산의 취득", "유형자산 취득"],
                    },
                }
            ],
            "preferred_statement_types": [],
            "constraints": {"consolidation_scope": "consolidated", "period_focus": "current"},
        }
        candidates = [
            {
                "candidate_id": "chunk_1",
                "candidate_kind": "chunk",
                "text": "시설투자 현황 53.1조원",
                "metadata": {
                    "section_path": "II. 사업의 내용 > 3. 원재료 및 생산설비",
                    "table_context": "(시설투자 현황) 53.1조원의 시설투자가 이루어졌습니다.",
                },
            },
            {
                "candidate_id": "row_capex",
                "candidate_kind": "table_row",
                "text": "합 계 | 합 계 | 합 계 | 합 계 | 531,139",
                "metadata": {
                    "row_text": "합 계 | 합 계 | 합 계 | 합 계 | 531,139",
                    "row_label": "합 계",
                    "structured_cells": [{"column_headers": ["투자액"], "value_text": "531,139", "unit_hint": "억원"}],
                    "aggregate_label": "합 계",
                    "aggregate_role": "final_total",
                    "value_role": "aggregate",
                    "aggregation_stage": "final",
                    "section_path": "II. 사업의 내용 > 3. 원재료 및 생산설비",
                    "table_context": "(시설투자 현황) 53.1조원의 시설투자가 이루어졌습니다.",
                    "consolidation_scope": "consolidated",
                },
            },
        ]

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=[2023],
            reconciliation_retry_count=0,
        )
        matched = result["matched_operands"][0]
        self.assertEqual(matched["candidate_ids"][0], "row_capex")

    def test_deterministic_reconcile_accepts_capex_row_when_surface_lives_in_row_context(self) -> None:
        active_subtask = {
            "task_id": "task_capex",
            "metric_family": "concept_lookup",
            "metric_label": "2023년 시설투자(CAPEX) 총액",
            "operation_family": "lookup",
            "required_operands": [
                {
                    "label": "시설투자(CAPEX)",
                    "aliases": ["시설투자", "CAPEX", "CapEx"],
                    "concept": "capital_expenditure_total",
                    "role": "current_period",
                    "required": True,
                    "preferred_sections": ["원재료 및 생산설비", "시설투자", "사업의 내용"],
                    "binding_policy": {
                        "prefer_value_roles": ["aggregate", "detail"],
                        "prefer_aggregation_stages": ["final", "direct", "subtotal", "none"],
                        "prefer_period_focus": "current",
                        "prefer_consolidation_scope": "consolidated",
                    },
                    "surface_contract": {
                        "positive": ["시설투자", "CAPEX", "CapEx", "자본적 지출"],
                        "negative": ["유형자산의 취득", "유형자산 취득"],
                    },
                }
            ],
            "preferred_statement_types": [],
            "constraints": {"consolidation_scope": "consolidated", "period_focus": "current"},
        }
        candidates = [
            {
                "candidate_id": "row_capex_fresh",
                "candidate_kind": "table_row",
                "text": "합 계 | 합 계 | 합 계 | 합 계 | 531,139",
                "metadata": {
                    "row_text": "합 계 | 합 계 | 합 계 | 합 계 | 531,139",
                    "row_label": "합 계",
                    "structured_cells": [
                        {
                            "column_headers": ["1,680,454"],
                            "value_text": "531,139",
                            "unit_hint": "억원",
                            "_report_year": 2023,
                        }
                    ],
                    "aggregate_label": "합 계",
                    "aggregate_role": "final_total",
                    "value_role": "aggregate",
                    "aggregation_stage": "final",
                    "section_path": "II. 사업의 내용 > 3. 원재료 및 생산설비",
                    "table_context": "당사의 시설 및 설비는 토지, 건물 및 구축물, 기계장치 등이 있으며 장부금액이 증가하였습니다.",
                    "row_context_text": "(시설투자 현황) 53.1조원의 시설투자가 이루어졌습니다.",
                    "consolidation_scope": "consolidated",
                },
            }
        ]

        result = _deterministic_reconcile_task(
            active_subtask=active_subtask,
            candidates=candidates,
            years=[2023],
            reconciliation_retry_count=0,
        )
        matched = result["matched_operands"][0]
        self.assertEqual(result["status"], "ready")
        self.assertEqual(matched["candidate_ids"][0], "row_capex_fresh")
        self.assertTrue(matched["matched"])

    def test_ratio_operand_extraction_recovers_same_table_aggregate_denominator(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        shared_row_context = "\n".join(
            [
                "| 공시금액",
                "법정적립금(*) | 8,240,670",
                "합계 | 24,544,359,051",
                "| 공시금액",
                "종업원급여(*) | 1,701,418,940",
                "합계 | 8,181,823,307",
            ]
        )
        candidates = [
            {
                "candidate_id": "num_candidate",
                "candidate_kind": "table_row",
                "source_anchor": "[네이버 | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
                "text": "종업원급여 1,701,418,940",
                "metadata": {
                    "row_label": "종업원급여",
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "table_source_id": "table_25",
                    "year": 2023,
                    "local_heading": "25. 영업비용 (연결)",
                    "table_context": "25. 영업비용 (연결)",
                    "table_summary_text": "당기 및 전기 중 영업비용의 내역은 다음과 같습니다.",
                    "row_text": "종업원급여(*) | 1,701,418,940",
                    "row_context_text": shared_row_context,
                    "value_role": "detail",
                    "aggregation_stage": "none",
                    "row_index": 4,
                    "structured_cells": [
                        {"column_headers": ["2023"], "value_text": "1,701,418,940", "unit_hint": "천원"}
                    ],
                },
            },
            {
                "candidate_id": "wrong_den_candidate",
                "candidate_kind": "table_row",
                "source_anchor": "[네이버 | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
                "text": "합계 24,544,359,051",
                "metadata": {
                    "row_label": "합계",
                    "aggregate_label": "합계",
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "table_source_id": "table_25",
                    "year": 2023,
                    "local_heading": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                    "table_context": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                    "row_text": "합계 | 24,544,359,051",
                    "row_context_text": shared_row_context,
                    "value_role": "aggregate",
                    "aggregation_stage": "final",
                    "row_index": 2,
                    "structured_cells": [
                        {"column_headers": ["2023"], "value_text": "24,544,359,051", "unit_hint": "천원"}
                    ],
                },
            },
            {
                "candidate_id": "den_candidate",
                "candidate_kind": "table_row",
                "source_anchor": "[네이버 | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
                "text": "합계 8,181,823,307",
                "metadata": {
                    "row_label": "합계",
                    "aggregate_label": "합계",
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "table_source_id": "table_25",
                    "year": 2023,
                    "local_heading": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                    "table_context": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                    "row_text": "합계 | 8,181,823,307",
                    "row_context_text": shared_row_context,
                    "value_role": "aggregate",
                    "aggregation_stage": "final",
                    "row_index": 5,
                    "structured_cells": [
                        {"column_headers": ["2023"], "value_text": "8,181,823,307", "unit_hint": "원"}
                    ],
                },
            },
        ]
        agent._build_reconciliation_candidates = lambda _state: candidates
        state = {
            "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
            "years": [2023],
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "영업비용 대비 인건비(종업원급여) 비중",
                "operation_family": "ratio",
                "required_operands": [
                    {
                        "label": "영업비용",
                        "concept": "operating_expense_total",
                        "aliases": ["영업비용 합계"],
                        "role": "denominator_1",
                        "required": True,
                        "binding_policy": {
                            "prefer_value_roles": ["aggregate"],
                            "prefer_aggregation_stages": ["final", "subtotal", "direct"],
                        },
                        "surface_contract": {"positive": ["영업비용"], "negative": []},
                    },
                    {
                        "label": "종업원급여",
                        "concept": "employee_benefits_expense",
                        "aliases": ["인건비", "인건비(종업원급여)"],
                        "role": "numerator_1",
                        "required": True,
                    },
                ],
                "preferred_statement_types": ["notes"],
                "constraints": {
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                    "entity_scope": "company",
                    "segment_scope": "none",
                },
            },
            "reconciliation_result": {
                "status": "ready",
                "matched_operands": [
                    {"label": "영업비용", "role": "denominator_1", "candidate_ids": []},
                    {"label": "종업원급여", "role": "numerator_1", "candidate_ids": ["num_candidate"]},
                ],
            },
        }

        rows = agent._extract_structured_operands_from_reconciliation(state)
        self.assertEqual(len(rows), 2)
        by_role = {row["matched_operand_role"]: row for row in rows}
        self.assertEqual(by_role["numerator_1"]["raw_value"], "1,701,418,940")
        self.assertEqual(by_role["denominator_1"]["raw_value"], "8,181,823,307")
        self.assertEqual(by_role["denominator_1"]["table_source_id"], "table_25")
        self.assertEqual(by_role["denominator_1"]["raw_unit"], "천원")
        self.assertEqual(by_role["denominator_1"]["normalized_value"], 8181823307000.0)

    def test_ratio_operand_extraction_uses_raw_row_sibling_before_same_table_denominator_recovery(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        shared_row_context = "\n".join(
            [
                "| 공시금액",
                "법정적립금(*) | 8,240,670",
                "합계 | 24,544,359,051",
                "| 공시금액",
                "종업원급여(*) | 1,701,418,940",
                "합계 | 8,181,823,307",
            ]
        )
        candidates = [
            {
                "candidate_id": "num_evidence",
                "candidate_kind": "chunk",
                "source_anchor": "[네이버 | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
                "text": "종업원급여 1,701,418,940",
                "metadata": {
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "table_source_id": "table_25",
                    "year": 2023,
                    "table_context": "25. 영업비용 (연결)",
                    "row_text": "종업원급여(*) | 1,701,418,940",
                    "row_context_text": shared_row_context,
                },
            },
            {
                "candidate_id": "num_evidence::raw_row",
                "candidate_kind": "evidence_row",
                "source_anchor": "[네이버 | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
                "text": "종업원급여(*) | 1,701,418,940",
                "metadata": {
                    "row_label": "종업원급여",
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "table_source_id": "table_25",
                    "year": 2023,
                    "local_heading": "25. 영업비용 (연결)",
                    "table_context": "25. 영업비용 (연결)",
                    "table_summary_text": "당기 및 전기 중 영업비용의 내역은 다음과 같습니다.",
                    "row_text": "종업원급여(*) | 1,701,418,940",
                    "row_context_text": shared_row_context,
                    "value_role": "detail",
                    "aggregation_stage": "none",
                    "row_index": 4,
                    "structured_cells": [
                        {"column_headers": ["2023"], "value_text": "1,701,418,940", "unit_hint": "천원"}
                    ],
                },
            },
            {
                "candidate_id": "den_candidate",
                "candidate_kind": "table_row",
                "source_anchor": "[네이버 | 2023 | III. 재무에 관한 사항 > 3. 연결재무제표 주석]",
                "text": "합계 8,181,823,307",
                "metadata": {
                    "row_label": "합계",
                    "aggregate_label": "합계",
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "table_source_id": "table_25",
                    "year": 2023,
                    "local_heading": "25. 영업비용 (연결)",
                    "table_context": "25. 영업비용 (연결)",
                    "row_text": "합계 | 8,181,823,307",
                    "row_context_text": shared_row_context,
                    "value_role": "aggregate",
                    "aggregation_stage": "final",
                    "row_index": 5,
                    "structured_cells": [
                        {"column_headers": ["2023"], "value_text": "8,181,823,307", "unit_hint": "천원"}
                    ],
                },
            },
        ]
        agent._build_reconciliation_candidates = lambda _state: candidates
        state = {
            "query": "2023년 영업비용 중 인건비(종업원급여)가 차지하는 비중을 계산해 줘.",
            "years": [2023],
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_ratio",
                "metric_label": "영업비용 대비 인건비(종업원급여) 비중",
                "operation_family": "ratio",
                "required_operands": [
                    {
                        "label": "영업비용",
                        "concept": "operating_expense_total",
                        "aliases": ["영업비용 합계"],
                        "role": "denominator_1",
                        "required": True,
                        "binding_policy": {
                            "prefer_value_roles": ["aggregate"],
                            "prefer_aggregation_stages": ["final", "subtotal", "direct"],
                        },
                        "surface_contract": {"positive": ["영업비용"], "negative": []},
                    },
                    {
                        "label": "종업원급여",
                        "concept": "employee_benefits_expense",
                        "aliases": ["인건비", "인건비(종업원급여)"],
                        "role": "numerator_1",
                        "required": True,
                    },
                ],
                "preferred_statement_types": ["notes"],
                "constraints": {
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                    "entity_scope": "company",
                    "segment_scope": "none",
                },
            },
            "reconciliation_result": {
                "status": "ready",
                "matched_operands": [
                    {"label": "영업비용", "role": "denominator_1", "candidate_ids": []},
                    {"label": "종업원급여", "role": "numerator_1", "candidate_ids": ["num_evidence"]},
                ],
            },
        }

        rows = agent._extract_structured_operands_from_reconciliation(state)
        self.assertEqual(len(rows), 2)
        by_role = {row["matched_operand_role"]: row for row in rows}
        self.assertEqual(by_role["numerator_1"]["raw_value"], "1,701,418,940")
        self.assertEqual(by_role["numerator_1"]["evidence_id"], "num_evidence::raw_row")
        self.assertEqual(by_role["denominator_1"]["raw_value"], "8,181,823,307")
        self.assertEqual(by_role["denominator_1"]["table_source_id"], "table_25")

    def test_lookup_operand_extraction_uses_raw_row_sibling_for_capex_total(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        candidates = [
            {
                "candidate_id": "recon_capex",
                "candidate_kind": "chunk",
                "source_anchor": "[삼성전자 | 2023 | II. 사업의 내용 > 3. 원재료 및 생산설비]",
                "text": "합 계 | 합 계 | 합 계 | 합 계 | 531,139",
                "metadata": {
                    "statement_type": "unknown",
                    "consolidation_scope": "consolidated",
                    "table_source_id": "capex_table",
                    "year": 2023,
                    "table_context": "(시설투자 현황) 53.1조원의 시설투자가 이루어졌습니다.",
                    "section_path": "II. 사업의 내용 > 3. 원재료 및 생산설비",
                    "row_text": "합 계 | 합 계 | 합 계 | 합 계 | 531,139",
                },
            },
            {
                "candidate_id": "recon_capex::raw_row",
                "candidate_kind": "evidence_row",
                "source_anchor": "[삼성전자 | 2023 | II. 사업의 내용 > 3. 원재료 및 생산설비]",
                "text": "합 계 | 합 계 | 합 계 | 합 계 | 531,139",
                "metadata": {
                    "row_label": "합 계",
                    "aggregate_label": "합 계",
                    "statement_type": "unknown",
                    "consolidation_scope": "consolidated",
                    "table_source_id": "capex_table",
                    "year": 2023,
                    "local_heading": "II. 사업의 내용 > 3. 원재료 및 생산설비",
                    "table_context": "(시설투자 현황) 53.1조원의 시설투자가 이루어졌습니다.",
                    "section_path": "II. 사업의 내용 > 3. 원재료 및 생산설비",
                    "row_text": "합 계 | 합 계 | 합 계 | 합 계 | 531,139",
                    "value_role": "aggregate",
                    "aggregation_stage": "final",
                    "structured_cells": [
                        {"column_headers": ["투자액"], "value_text": "531,139", "unit_hint": "억원"}
                    ],
                },
            },
        ]
        agent._build_reconciliation_candidates = lambda _state: candidates
        state = {
            "query": "2023년 시설투자(CAPEX) 총액을 찾아 줘.",
            "years": [2023],
            "report_scope": {"company": "삼성전자", "year": 2023, "report_type": "사업보고서", "rcept_no": "20240312000736"},
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 시설투자(CAPEX) 총액",
                "operation_family": "lookup",
                "required_operands": [
                    {
                        "label": "시설투자(CAPEX)",
                        "aliases": ["시설투자", "CAPEX", "CapEx"],
                        "concept": "capital_expenditure_total",
                        "role": "current_period",
                        "required": True,
                        "preferred_sections": ["원재료 및 생산설비", "시설투자", "사업의 내용"],
                        "binding_policy": {
                            "prefer_value_roles": ["aggregate", "detail"],
                            "prefer_aggregation_stages": ["final", "direct", "subtotal", "none"],
                            "prefer_period_focus": "current",
                            "prefer_consolidation_scope": "consolidated",
                        },
                        "surface_contract": {
                            "positive": ["시설투자", "CAPEX", "CapEx", "자본적 지출"],
                            "negative": ["유형자산의 취득", "유형자산 취득"],
                        },
                    }
                ],
                "preferred_statement_types": [],
                "constraints": {"consolidation_scope": "consolidated", "period_focus": "current"},
            },
            "reconciliation_result": {
                "status": "ready",
                "matched_operands": [
                    {"label": "시설투자(CAPEX)", "role": "current_period", "candidate_ids": ["recon_capex"]}
                ],
            },
        }

        rows = agent._extract_structured_operands_from_reconciliation(state)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["evidence_id"], "recon_capex::raw_row")
        self.assertEqual(row["raw_value"], "531,139")
        self.assertEqual(row["raw_unit"], "억원")

    def test_company_total_lookup_scores_canonical_income_statement_above_related_party_note(self) -> None:
        operand = {
            "label": "영업비용",
            "concept": "operating_expense_total",
            "aliases": ["영업비용", "영업비용 합계", "영업비용 총계"],
            "role": "primary_value",
            "required": True,
            "preferred_statement_types": ["income_statement", "summary_financials", "notes"],
            "binding_policy": {
                "prefer_period_focus": "current",
                "prefer_consolidation_scope": "consolidated",
            },
        }
        canonical_candidate = {
            "candidate_id": "income_statement_opex",
            "candidate_kind": "structured_value",
            "text": "영업비용 (주25) (8,181,823,306,977)",
            "metadata": {
                "row_label": "영업비용 (주25)",
                "semantic_label": "영업비용 (주25)",
                "statement_type": "income_statement",
                "consolidation_scope": "consolidated",
                "section_path": "III. 재무에 관한 사항 > 2. 연결재무제표 > 연결 손익계산서",
                "period_focus": "current",
                "period_labels": ["제 25 기", "제 24 기"],
                "structured_cells": [
                    {"column_headers": ["제 25 기"], "value_text": "(8,181,823,306,977)", "unit_hint": "원"},
                ],
                "value_role": "detail",
                "aggregation_stage": "none",
            },
        }
        related_party_candidate = {
            "candidate_id": "related_party_opex",
            "candidate_kind": "structured_value",
            "text": "영업비용 등 11,781,510",
            "metadata": {
                "row_label": "영업비용 등",
                "semantic_label": "영업비용 등",
                "semantic_aliases": ["영업비용 등", "전체 특수관계자", "특수관계자", "관계기업"],
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
                "table_row_labels_text": "전체 특수관계자\n특수관계자\n관계기업\n영업비용 등",
                "period_focus": "current",
                "period_labels": ["2023"],
                "structured_cells": [
                    {
                        "column_headers": ["전체 특수관계자", "특수관계자", "관계기업"],
                        "value_text": "11,781,510",
                        "unit_hint": "천원",
                    }
                ],
                "value_role": "detail",
                "aggregation_stage": "none",
            },
        }

        canonical_score = _score_operand_candidate(
            canonical_candidate,
            operand=operand,
            preferred_statement_types=["income_statement", "summary_financials", "notes"],
            constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
            query_years=[2023],
        )
        related_party_score = _score_operand_candidate(
            related_party_candidate,
            operand=operand,
            preferred_statement_types=["income_statement", "summary_financials", "notes"],
            constraints={"consolidation_scope": "consolidated", "period_focus": "current"},
            query_years=[2023],
        )

        self.assertGreater(canonical_score, related_party_score)

if __name__ == "__main__":
    unittest.main()
