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

if __name__ == "__main__":
    unittest.main()
