import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.financial_graph import (
    _build_table_row_reconciliation_candidates,
    _candidate_matches_operand,
    _deterministic_reconcile_task,
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

        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate["candidate_kind"], "structured_row")
        self.assertEqual(candidate["metadata"].get("row_headers"), ["부채총계"])
        self.assertTrue(_candidate_matches_operand(candidate, {"label": "부채총계", "aliases": ["총부채"]}))


if __name__ == "__main__":
    unittest.main()
