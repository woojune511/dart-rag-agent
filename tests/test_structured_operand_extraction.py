import json
import sys
import unittest
from pathlib import Path

from langchain_core.documents import Document

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.financial_graph import FinancialAgent


class StructuredOperandExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = FinancialAgent.__new__(FinancialAgent)

    def test_direct_structured_row_operands_are_extracted_from_reconciliation(self) -> None:
        row_records = [
            {
                "row_id": "r1",
                "row_label": "부채총계",
                "row_headers": ["부채총계"],
                "cells": [
                    {"column_headers": ["2023"], "value_text": "92,228,115", "unit_hint": "백만원"},
                    {"column_headers": ["2022"], "value_text": "93,674,903", "unit_hint": "백만원"},
                ],
            },
            {
                "row_id": "r2",
                "row_label": "자본총계",
                "row_headers": ["자본총계"],
                "cells": [
                    {"column_headers": ["2023"], "value_text": "363,677,865", "unit_hint": "백만원"},
                    {"column_headers": ["2022"], "value_text": "354,749,604", "unit_hint": "백만원"},
                ],
            },
        ]
        metadata = {
            "chunk_uid": "chunk_001",
            "company": "삼성전자",
            "year": 2023,
            "block_type": "table",
            "statement_type": "summary_financials",
            "consolidation_scope": "consolidated",
            "period_labels": ["2023", "2022"],
            "table_source_id": "table_001",
            "table_header_context": "구분 | 2023 | 2022 | 단위: 백만원",
            "table_summary_text": "구분 | 2023 | 2022 | 단위: 백만원\n부채총계 | 자본총계",
            "table_row_labels_text": "부채총계\n자본총계",
            "table_row_records_json": json.dumps(row_records, ensure_ascii=False),
            "section_path": "III. 재무에 관한 사항 > 1. 요약재무정보",
        }
        state = {
            "query": "2023년 연결기준 부채비율을 계산해 줘",
            "years": [2023],
            "report_scope": {"company": "삼성전자", "year": "2023", "consolidation": "연결"},
            "intent": "comparison",
            "topic": "부채비율 계산",
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [(Document(page_content="요약재무정보 표", metadata=metadata), 1.0)],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "debt_ratio",
                "metric_label": "부채비율",
                "query": "2023년 연결기준 부채비율을 계산해 줘",
                "required_operands": [
                    {"label": "부채총계", "aliases": ["총부채"], "role": "numerator", "required": True},
                    {"label": "자본총계", "aliases": ["총자본"], "role": "denominator", "required": True},
                ],
                "constraints": {
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                    "entity_scope": "company",
                    "segment_scope": "none",
                },
            },
            "reconciliation_result": {
                "status": "ready",
                "task_id": "task_1",
                "matched_operands": [
                    {"label": "부채총계", "matched": True, "candidate_ids": ["chunk_001::rowrec:0"], "reason": "matched_candidates"},
                    {"label": "자본총계", "matched": True, "candidate_ids": ["chunk_001::rowrec:1"], "reason": "matched_candidates"},
                ],
                "missing_operands": [],
                "retry_queries": [],
                "notes": ["same_table_candidate_available"],
            },
        }

        result = self.agent._extract_calculation_operands(state)
        rows = list(result.get("calculation_operands") or [])

        self.assertEqual(result.get("calculation_debug_trace", {}).get("source"), "structured_row_direct")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["raw_value"], "92,228,115")
        self.assertEqual(rows[0]["normalized_unit"], "KRW")
        self.assertEqual(rows[0]["period"], "2023")
        self.assertEqual(rows[1]["raw_value"], "363,677,865")
        self.assertEqual(rows[1]["period"], "2023")

    def test_direct_structured_column_operands_are_extracted_from_reconciliation(self) -> None:
        row_records = [
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
        ]
        metadata = {
            "chunk_uid": "chunk_002",
            "company": "삼성전자",
            "year": 2023,
            "block_type": "table",
            "statement_type": "summary_financials",
            "consolidation_scope": "consolidated",
            "period_labels": ["2023", "2022"],
            "table_source_id": "table_002",
            "table_header_context": "구분 | 부채총계 | 자본총계 | 단위: 백만원",
            "table_summary_text": "구분 | 부채총계 | 자본총계",
            "table_row_labels_text": "2023\n2022",
            "table_row_records_json": json.dumps(row_records, ensure_ascii=False),
            "section_path": "III. 재무에 관한 사항 > 1. 요약재무정보",
        }
        state = {
            "query": "2023년 연결기준 부채비율을 계산해 줘",
            "years": [2023],
            "report_scope": {"company": "삼성전자", "year": "2023", "consolidation": "연결"},
            "intent": "comparison",
            "topic": "부채비율 계산",
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [(Document(page_content="요약재무정보 표", metadata=metadata), 1.0)],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "debt_ratio",
                "metric_label": "부채비율",
                "query": "2023년 연결기준 부채비율을 계산해 줘",
                "required_operands": [
                    {"label": "부채총계", "aliases": ["총부채"], "role": "numerator", "required": True},
                    {"label": "자본총계", "aliases": ["총자본"], "role": "denominator", "required": True},
                ],
                "constraints": {
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                    "entity_scope": "company",
                    "segment_scope": "none",
                },
            },
            "reconciliation_result": {
                "status": "ready",
                "task_id": "task_1",
                "matched_operands": [
                    {"label": "부채총계", "matched": True, "candidate_ids": ["chunk_002::colrec:0"], "reason": "matched_candidates"},
                    {"label": "자본총계", "matched": True, "candidate_ids": ["chunk_002::colrec:1"], "reason": "matched_candidates"},
                ],
                "missing_operands": [],
                "retry_queries": [],
                "notes": [],
            },
        }

        rows = self.agent._extract_structured_operands_from_reconciliation(state)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["raw_value"], "92,228,115")
        self.assertEqual(rows[0]["period"], "2023")
        self.assertEqual(rows[1]["raw_value"], "363,677,865")
        self.assertEqual(rows[1]["period"], "2023")

    def test_direct_structured_value_operands_are_extracted_from_reconciliation(self) -> None:
        metadata = {
            "chunk_uid": "chunk_003",
            "company": "삼성전자",
            "year": 2023,
            "block_type": "table",
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
                    },
                    {
                        "value_id": "table_003:v:1:1",
                        "row_index": 1,
                        "column_index": 1,
                        "semantic_label": "자본총계",
                        "semantic_aliases": ["자본총계", "총자본"],
                        "label_source": "row",
                        "row_label": "자본총계",
                        "row_headers": ["자본총계"],
                        "column_headers": ["2023"],
                        "period_text": "2023",
                        "period_labels": ["2023"],
                        "value_text": "363,677,865",
                        "unit_hint": "백만원",
                    },
                ],
                ensure_ascii=False,
            ),
        }
        state = {
            "query": "2023년 연결기준 부채비율을 계산해 줘",
            "years": [2023],
            "report_scope": {"company": "삼성전자", "year": "2023", "consolidation": "연결"},
            "intent": "comparison",
            "topic": "부채비율 계산",
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [(Document(page_content="요약재무정보 표", metadata=metadata), 1.0)],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "debt_ratio",
                "metric_label": "부채비율",
                "query": "2023년 연결기준 부채비율을 계산해 줘",
                "required_operands": [
                    {"label": "부채총계", "aliases": ["총부채"], "role": "numerator", "required": True},
                    {"label": "자본총계", "aliases": ["총자본"], "role": "denominator", "required": True},
                ],
                "constraints": {
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                    "entity_scope": "company",
                    "segment_scope": "none",
                },
            },
            "reconciliation_result": {
                "status": "ready",
                "task_id": "task_1",
                "matched_operands": [
                    {"label": "부채총계", "matched": True, "candidate_ids": ["chunk_003::value:0"], "reason": "matched_candidates"},
                    {"label": "자본총계", "matched": True, "candidate_ids": ["chunk_003::value:1"], "reason": "matched_candidates"},
                ],
                "missing_operands": [],
                "retry_queries": [],
                "notes": [],
            },
        }

        rows = self.agent._extract_structured_operands_from_reconciliation(state)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["raw_value"], "92,228,115")
        self.assertEqual(rows[0]["period"], "2023")
        self.assertEqual(rows[1]["raw_value"], "363,677,865")
        self.assertEqual(rows[1]["period"], "2023")

    def test_direct_extraction_rescores_candidates_and_prefers_current_aggregate(self) -> None:
        current_metadata = {
            "chunk_uid": "chunk_current",
            "company": "SK하이닉스",
            "year": 2023,
            "block_type": "table",
            "statement_type": "notes",
            "consolidation_scope": "consolidated",
            "period_labels": ["당기"],
            "period_focus": "current",
            "table_source_id": "table_current",
            "table_header_context": "구분 | 공시금액 | (단위: 백만원)",
            "table_value_records_json": json.dumps(
                [
                    {
                        "value_id": "table_current:v:0:1",
                        "row_index": 0,
                        "column_index": 1,
                        "semantic_label": "단기차입금 합계",
                        "semantic_aliases": ["단기차입금 합계", "단기차입금"],
                        "label_source": "row",
                        "row_label": "단기차입금 합계",
                        "row_headers": ["단기차입금"],
                        "column_headers": ["공시금액"],
                        "period_text": "당기",
                        "period_labels": ["당기"],
                        "value_text": "4,145,647",
                        "unit_hint": "백만원",
                        "aggregate_label": "단기차입금 합계",
                        "aggregate_role": "direct_total",
                    }
                ],
                ensure_ascii=False,
            ),
            "section_path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
        }
        prior_metadata = {
            **current_metadata,
            "chunk_uid": "chunk_prior",
            "period_labels": ["전기"],
            "period_focus": "prior",
            "table_source_id": "table_prior",
            "table_value_records_json": json.dumps(
                [
                    {
                        "value_id": "table_prior:v:0:1",
                        "row_index": 0,
                        "column_index": 1,
                        "semantic_label": "단기차입금",
                        "semantic_aliases": ["단기차입금"],
                        "label_source": "row",
                        "row_label": "단기차입금",
                        "row_headers": ["단기차입금"],
                        "column_headers": ["공시금액"],
                        "period_text": "전기",
                        "period_labels": ["전기"],
                        "value_text": "3,833,263",
                        "unit_hint": "백만원",
                        "aggregate_label": "",
                        "aggregate_role": "none",
                    }
                ],
                ensure_ascii=False,
            ),
        }
        state = {
            "query": "2023년 연결 재무상태표에서 단기차입금을 찾아줘",
            "years": [2023],
            "report_scope": {"company": "SK하이닉스", "year": "2023", "consolidation": "연결"},
            "intent": "comparison",
            "topic": "단기차입금",
            "evidence_items": [],
            "evidence_bullets": [],
            "retrieved_docs": [
                (Document(page_content="전기 표", metadata=prior_metadata), 1.0),
                (Document(page_content="당기 표", metadata=current_metadata), 0.9),
            ],
            "seed_retrieved_docs": [],
            "evidence_status": "missing",
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "generic_numeric",
                "metric_label": "단기차입금",
                "query": "2023년 연결 재무상태표에서 단기차입금을 찾아줘",
                "preferred_statement_types": ["notes"],
                "required_operands": [
                    {"label": "단기차입금", "aliases": [], "required": True},
                ],
                "constraints": {
                    "consolidation_scope": "consolidated",
                    "period_focus": "current",
                    "entity_scope": "company",
                    "segment_scope": "none",
                },
            },
            "reconciliation_result": {
                "status": "ready",
                "task_id": "task_1",
                "matched_operands": [
                    {
                        "label": "단기차입금",
                        "matched": True,
                        "candidate_ids": ["chunk_prior::value:0", "chunk_current::value:0"],
                        "reason": "matched_candidates",
                    }
                ],
                "missing_operands": [],
                "retry_queries": [],
                "notes": [],
            },
        }

        rows = self.agent._extract_structured_operands_from_reconciliation(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["raw_value"], "4,145,647")
        self.assertEqual(rows[0]["period"], "당기")


if __name__ == "__main__":
    unittest.main()
