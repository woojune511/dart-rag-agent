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

        candidate = next(item for item in candidates if item["candidate_kind"] == "structured_row")
        self.assertEqual(candidate["candidate_kind"], "structured_row")
        self.assertEqual(candidate["metadata"].get("row_headers"), ["부채총계"])
        self.assertTrue(_candidate_matches_operand(candidate, {"label": "부채총계", "aliases": ["총부채"]}))

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


if __name__ == "__main__":
    unittest.main()
