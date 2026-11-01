"""Offline UI checks: exact report selection and honest recorded-status display."""

from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src.agent.financial_run_result import FINANCIAL_RUN_RESULT_SCHEMA_VERSION, FinancialRunResultV1
from src.ui.query_presentation import indexed_report_catalog, query_status_notices


METADATAS = [
    {"company": "Birch", "year": 2040, "report_type": "annual", "rcept_no": "r1"},
    {"company": "Birch", "year": 2040, "report_type": "annual", "rcept_no": "r1"},
    {"company": "Birch", "year": 2040, "report_type": "amended", "rcept_no": "r2"},
    {"company": "Birch", "year": 2041, "report_type": "annual", "rcept_no": "r3"},
    {"company": "Cedar", "year": 2040, "report_type": "annual", "rcept_no": "r4"},
]


def saved_result(*, mode="hybrid", omitted=None, search=None):
    source = {"source_id": "r1:c1", "text": "Original source text.", "context": {"company": "Birch", "year": 2040}}
    return FinancialRunResultV1(
        FINANCIAL_RUN_RESULT_SCHEMA_VERSION,
        {"answer": "Saved answer.", "abstained": False, "companies": ["Birch"], "years": [2040],
         "citations": ["r1:c1"], "cited_sources": [source],
         "retrieval_status": {"retrieval_mode": mode, "degraded": mode in {"bm25_only", "bm25_fallback"}}},
        {"retrieved_sources": [source], "retrieval_debug_trace": {
            "omitted": omitted or [], "search": search or {"retrieval_mode": mode},
            "selected_source_ids": ["r1:c1"], "context_bytes": 512, "context_byte_limit": 65536,
        }},
    )


class QueryPresentationTests(unittest.TestCase):
    def test_catalog_deduplicates_only_receipts_and_preserves_observed_labels(self):
        before = deepcopy(METADATAS)
        catalog, missing = indexed_report_catalog(METADATAS)
        by_receipt = {row["receipt"]: row for row in catalog}
        self.assertEqual(set(by_receipt), {"r1", "r2", "r3", "r4"})
        self.assertIn("amended", by_receipt["r2"]["label"])
        self.assertIn("접수 r1", by_receipt["r1"]["label"])
        self.assertEqual(missing, 0)
        self.assertEqual(METADATAS, before)

    def test_missing_identity_is_not_replaced_with_company_year_or_an_invented_id(self):
        catalog, missing = indexed_report_catalog([None, {}, {"company": "Birch", "year": 2040}, {"rcept_no": "r1"}])
        self.assertEqual(missing, 3)
        self.assertEqual([row["receipt"] for row in catalog], ["r1"])
        self.assertEqual(catalog[0]["companies"], [])
        self.assertEqual(catalog[0]["years"], [])
        self.assertIn("기업명 미기록", catalog[0]["label"])

    def test_catalog_does_not_choose_between_conflicting_metadata(self):
        catalog, _ = indexed_report_catalog([
            {"rcept_no": "r1", "company": "Birch", "year": 2040},
            {"rcept_no": "r1", "company": "Cedar", "year": "2041"},
            {"rcept_no": "r1", "year": True},
            {"rcept_no": "r1", "year": "²"},
        ])
        self.assertEqual(catalog[0]["companies"], ["Birch", "Cedar"])
        self.assertEqual(catalog[0]["years"], [2041, 2040])

    def test_cached_fallback_keeps_recorded_mode_and_reason(self):
        result = saved_result(mode="bm25_fallback", search={
            "retrieval_mode": "cache", "cached_retrieval_mode": "bm25_fallback",
            "cached_vector_skipped_reason": "vector_store_read_error",
        })
        notices = query_status_notices(result.agent_answer, result.review_trace)
        self.assertTrue(any(level == "warning" and "인덱스를 읽지 못" in text for level, text in notices))
        self.assertTrue(any("재사용" in text for _, text in notices))

    def test_each_recorded_degradation_reason_is_shown_without_raw_error_text(self):
        for reason, expected in (("force_bm25_only", "현재 설정"), ("capacity_cooldown", "일시 대기"),
                                 ("embedding_capacity_error", "한도에 도달"), ("new_reason", "기록되지 않았")):
            with self.subTest(reason=reason):
                result = saved_result(mode="bm25_only", search={"vector_skipped_reason": reason, "error": "private raw error"})
                notices = query_status_notices(result.agent_answer, result.review_trace)
                self.assertTrue(any(level == "warning" and expected in text for level, text in notices))
                self.assertNotIn("private raw error", str(notices))

    def test_omissions_are_counted_by_recorded_reason_without_mutating_trace(self):
        result = saved_result(omitted=[{"source_id": "r1:c2", "reason": "context_byte_limit"},
                                     {"reason": "missing_source_identity_or_text"}, {"reason": "future_reason"}])
        before = deepcopy(result.to_projection())
        notices = query_status_notices(result.agent_answer, result.review_trace)
        self.assertTrue(any(level == "warning" and "근거 3개" in text and "용량 제한 1개" in text
                            and "본문 누락 1개" in text and "기타 기록된 사유 1개" in text for level, text in notices))
        self.assertEqual(result.to_projection(), before)

    def test_missing_observations_are_not_a_normal_or_complete_result(self):
        notices = query_status_notices({}, {})
        self.assertTrue(any("검색 방식 정보가 기록되지" in text for _, text in notices))
        self.assertTrue(any("생략 여부가 기록되지" in text for _, text in notices))
        self.assertFalse(any("생략된 근거는 없습니다" in text for _, text in notices))

    def test_store_degradation_remains_visible_without_query_telemetry(self):
        notices = query_status_notices({}, {}, store_degraded=True)
        self.assertTrue(any(level == "warning" and "저장소에 검색 제한" in text for level, text in notices))
        self.assertTrue(any("검색 방식 정보가 기록되지" in text for _, text in notices))
        self.assertFalse(any("키워드 검색만 사용했습니다" in text for _, text in notices))

    def test_empty_scope_is_not_reported_as_keyword_search_from_store_state(self):
        notices = query_status_notices({"retrieval_status": {"retrieval_mode": "empty_scope"}},
                                      {"retrieval_debug_trace": {"omitted": []}}, store_degraded=True)
        self.assertTrue(any("일치하는 자료가 없습니다" in text for _, text in notices))
        self.assertFalse(any("키워드 검색만 사용했습니다" in text for _, text in notices))

    def test_observed_empty_scope_and_zero_omissions_are_distinct_from_unknown(self):
        notices = query_status_notices({"retrieval_status": {"retrieval_mode": "empty_scope"}},
                                      {"retrieval_debug_trace": {"omitted": []}})
        self.assertTrue(any("일치하는 자료가 없습니다" in text for _, text in notices))
        self.assertTrue(any("생략된 근거는 없습니다" in text for _, text in notices))
        self.assertFalse(any(level == "warning" for level, _ in notices))


class QueryPanelTests(unittest.TestCase):
    def setUp(self):
        import streamlit as st
        self.st = st
        original_path = list(sys.path)
        self.addCleanup(lambda: sys.path.__setitem__(slice(None), original_path))
        st.cache_resource.clear()
        self.addCleanup(st.cache_resource.clear)
        self.metadata_get = Mock(return_value={"metadatas": deepcopy(METADATAS)})
        self.agent = Mock()
        self.agent.run.return_value = saved_result()
        self.services = SimpleNamespace(
            store=SimpleNamespace(vector_store=SimpleNamespace(get=self.metadata_get)), agent=self.agent,
            readiness=SimpleNamespace(ready=True, reason="", degraded=False), serialized_sync_operation=nullcontext,
        )
        self.build = self.enterContext(patch("src.api.services.build_app_services", return_value=self.services))
        self.enterContext(patch("dotenv.load_dotenv"))

    def app(self):
        from streamlit.testing.v1 import AppTest
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
        self.assertEqual(len(app.exception), 0)
        app.text_area(key="custom_question").set_value("Question about 2049?\nKeep units.").run()
        return app

    def run_button(self, app):
        return next(button for button in app.button if button.label == "🔍 분석 실행")

    def picker(self, app):
        app.radio(key="query_scope_mode").set_value("목록에서 선택").run()
        app.button(key="query_catalog_refresh").click().run()
        self.assertEqual(len(app.exception), 0)

    def test_opening_screen_does_not_initialize_store_or_generate(self):
        app = self.app()
        self.assertEqual(app.tabs[0].label, "💬 질문 분석")
        self.build.assert_not_called()
        self.metadata_get.assert_not_called()
        self.agent.run.assert_not_called()

    def test_multiple_report_selection_passes_only_explicit_receipts_and_exact_question(self):
        app = self.app()
        self.picker(app)
        self.assertTrue(self.run_button(app).disabled)
        app.selectbox(key="report_company_filter").set_value("Birch").run()
        app.selectbox(key="report_year_filter").set_value(2040).run()
        self.assertEqual(len(app.multiselect(key="selected_reports").options), 2)
        app.multiselect(key="selected_reports").set_value(["r1", "r2"]).run()
        self.run_button(app).click().run()
        self.assertEqual(len(app.exception), 0)
        self.agent.run.assert_called_once_with("Question about 2049?\nKeep units.",
                                               report_scope={"source_receipts": ["r1", "r2"]}, include_review_trace=True)
        self.metadata_get.assert_called_once_with(include=["metadatas"])
        self.assertTrue(any(item.value == "Original source text." for item in app.text))

    def test_empty_selection_after_filter_change_cannot_widen_to_all_reports(self):
        app = self.app()
        self.picker(app)
        app.multiselect(key="selected_reports").set_value(["r1"]).run()
        app.selectbox(key="report_company_filter").set_value("Cedar").run()
        self.assertEqual(app.multiselect(key="selected_reports").value, [])
        self.assertTrue(self.run_button(app).disabled)
        self.agent.run.assert_not_called()

    def test_failed_refresh_discards_stale_catalog_and_blocks_selected_report_query(self):
        app = self.app()
        self.picker(app)
        app.multiselect(key="selected_reports").set_value(["r1"]).run()
        self.metadata_get.side_effect = RuntimeError("unavailable")
        app.button(key="query_catalog_refresh").click().run()
        self.assertTrue(self.run_button(app).disabled)
        self.assertTrue(any("불러오지 못" in item.value for item in app.error))
        self.agent.run.assert_not_called()

    def test_no_identifiable_reports_never_becomes_unrestricted_query(self):
        self.metadata_get.return_value = {"metadatas": [{"company": "Birch", "year": 2040}]}
        app = self.app()
        self.picker(app)
        self.assertTrue(self.run_button(app).disabled)
        self.assertTrue(any("접수번호가 없는 자료 1개" in item.value for item in app.warning))
        self.agent.run.assert_not_called()

    def test_recorded_omission_and_cached_degradation_are_beside_answer_and_survive_rerun(self):
        self.agent.run.return_value = saved_result(mode="bm25_fallback", omitted=[
            {"source_id": "r1:c2", "reason": "context_byte_limit"},
        ], search={"retrieval_mode": "cache", "cached_retrieval_mode": "bm25_fallback",
                   "cached_vector_skipped_reason": "embedding_capacity_error"})
        app = self.app()
        self.run_button(app).click().run()
        self.assertEqual(len(app.exception), 0)
        status_columns = [column for column in app.get("column")
                          if any(item.value == "**검색·근거 상태**" for item in column.markdown)]
        self.assertEqual(len(status_columns), 1)
        status_column = status_columns[0]
        self.assertTrue(any("키워드 검색만" in item.value for item in status_column.warning))
        self.assertTrue(any("근거 1개" in item.value for item in status_column.warning))
        self.assertTrue(any("재사용" in item.value for item in status_column.caption))
        app.radio(key="query_scope_mode").set_value("목록에서 선택").run()
        self.assertTrue(any(item.value == "Saved answer." for item in app.markdown))
        self.assertTrue(any("이 답변의 검색 범위: 인덱싱된 전체 보고서" in item.value for item in app.caption))
        self.assertTrue(any("근거 1개" in item.value for item in app.warning))
        self.agent.run.assert_called_once()
        self.assertIsNone(self.agent.run.call_args.kwargs["report_scope"])

    def test_direct_scope_requires_a_valid_condition(self):
        app = self.app()
        app.radio(key="query_scope_mode").set_value("조건 직접 입력").run()
        self.assertTrue(self.run_button(app).disabled)
        app.text_input(key="query_scope_company").set_value("Birch")
        app.text_input(key="query_scope_year").set_value("bad").run()
        self.assertTrue(self.run_button(app).disabled)
        app.text_input(key="query_scope_year").set_value("2040").run()
        self.run_button(app).click().run()
        self.agent.run.assert_called_once_with("Question about 2049?\nKeep units.",
                                               report_scope={"company": "Birch", "year": 2040}, include_review_trace=True)


if __name__ == "__main__":
    unittest.main()
