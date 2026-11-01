"""
Streamlit UI — DART 공시 검색·질의응답 (experimental)

탭 구성:
  Tab 1: 질문 분석         — 보고서 선택 → 검색 → 답변 + 출처·검색 상태
  Tab 2: 기업 데이터 수집 — DART 수집 + 파싱 + 인덱싱

실행:
    streamlit run app.py
"""

import logging
import os
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import streamlit as st

from src.ui.query_presentation import indexed_report_catalog, query_status_notices

# src 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.WARNING)
CONTEXT_MAX_WORKERS = int(os.environ.get("CONTEXTUAL_INGEST_MAX_WORKERS", "8"))

# --------------------------------------------------------------------------
# 컴포넌트 싱글턴 (캐시 리소스 — 앱 전체에서 한 번만 초기화)
# --------------------------------------------------------------------------

@st.cache_resource(show_spinner="모델 및 DB 로딩 중...")
def load_components():
    from src.api.services import build_app_services

    return build_app_services(project_root=Path(__file__).resolve().parent)


# --------------------------------------------------------------------------
# 페이지 설정
# --------------------------------------------------------------------------

st.set_page_config(
    page_title="DART 공시 분석 AI",
    page_icon="📊",
    layout="wide",
)

st.title("📊 DART 공시 검색·질의응답")
st.caption(
    "Experimental UI — DART(전자공시시스템) 기반 기업 공시 문서를 분석합니다."
)

# --------------------------------------------------------------------------
# 탭 구성
# --------------------------------------------------------------------------

tab2, tab1 = st.tabs(["💬 질문 분석", "📥 데이터 수집"])


# ══════════════════════════════════════════════════════════════════════════
# 기업 데이터 수집
# ══════════════════════════════════════════════════════════════════════════

with tab1:
    st.subheader("기업 공시 문서 수집 및 인덱싱")
    st.caption("DART에서 사업보고서를 다운로드하고 벡터 DB에 인덱싱합니다.")

    col1, col2 = st.columns([2, 1])

    with col1:
        company_input = st.text_input(
            "기업명",
            placeholder="예: 삼성전자, SK하이닉스, 네이버",
            key="ingest_company",
        )

    with col2:
        current_year = max(2026, datetime.now().year)
        year_options = list(range(current_year, current_year - 6, -1))
        selected_years = st.multiselect(
            "연도",
            options=year_options,
            default=[2023],
            key="ingest_years",
        )

    if st.button("🔄 수집 및 인덱싱", type="primary", disabled=not (company_input and selected_years)):
        services = load_components()

        with st.status(f"'{company_input}' {selected_years} 처리 중...", expanded=True) as status:
            try:
                st.write("📡 DART 공시 수집·파싱·컨텍스트 생성·인덱싱 중...")
                with services.serialized_sync_operation():
                    ingest_service = services.ingest_service
                    if ingest_service is None:
                        raise RuntimeError(services.readiness.reason)
                    try:
                        result = ingest_service.ingest_company(
                            company_input,
                            selected_years,
                            max_workers=CONTEXT_MAX_WORKERS,
                        )
                    finally:
                        services.refresh_readiness()
                if not int(result.get("files_fetched") or 0):
                    status.update(label="공시 문서를 찾을 수 없습니다.", state="error")
                    st.error(f"'{company_input}'의 {selected_years} 공시 문서를 찾을 수 없습니다.")
                else:
                    st.session_state.pop("query_report_catalog", None)
                    total_chunks = int(result.get("chunks_added") or 0)
                    skipped = int(result.get("reports_skipped") or 0)
                    if total_chunks == 0 and skipped > 0:
                        status.update(label="이미 모두 인덱싱된 문서입니다.", state="complete")
                        st.info(f"ℹ️ {skipped}개 문서가 이미 인덱싱되어 있어 건너뛰었습니다.")
                    else:
                        skip_msg = f" ({skipped}개 기존 건너뜀)" if skipped else ""
                        status.update(label=f"완료! {total_chunks}개 청크 인덱싱{skip_msg}", state="complete")
                        st.success(f"✅ **{total_chunks}개 청크** 인덱싱 완료{skip_msg}")

            except Exception as e:
                status.update(label="오류 발생", state="error")
                st.error(f"오류: {e}")

    # 현재 인덱싱 현황
    st.divider()
    st.subheader("현재 인덱싱 현황")

    if st.button("🔍 현황 조회"):
        services = load_components()
        try:
            with services.serialized_sync_operation():
                vsm = services.store
                if vsm is None:
                    raise RuntimeError(services.readiness.reason)
                data = vsm.vector_store.get(include=["metadatas"])
            metadatas = data.get("metadatas") or []
            st.session_state["query_report_catalog"] = indexed_report_catalog(metadatas)

            if not metadatas:
                st.info("인덱싱된 문서가 없습니다.")
            else:
                company_stats: dict = {}
                for meta in metadatas:
                    company = meta.get("company", "unknown")
                    year    = meta.get("year")
                    company_stats.setdefault(company, {"years": set(), "count": 0})
                    company_stats[company]["count"] += 1
                    if year:
                        company_stats[company]["years"].add(int(year))

                import pandas as pd
                rows = [
                    {
                        "기업명": company,
                        "연도": ", ".join(str(y) for y in sorted(info["years"])),
                        "청크 수": info["count"],
                    }
                    for company, info in sorted(company_stats.items())
                ]
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True)
                st.caption(f"총 {len(metadatas):,}개 청크 인덱싱됨")
        except Exception as e:
            st.error(f"조회 실패: {e}")


# ══════════════════════════════════════════════════════════════════════════
# 질문 분석
# ══════════════════════════════════════════════════════════════════════════

with tab2:
    st.subheader("자연어 질문 분석")
    st.caption("공시 근거를 검색해 답변합니다. 계산 정확성과 근거의 의미를 자동 검증하지 않습니다.")

    # 예시 질문
    EXAMPLE_QUERIES = [
        "삼성전자 2023년 반도체 사업의 주요 리스크 요인은 무엇인가요?",
        "삼성전자 2023년 연결 매출액과 영업이익은 얼마인가요?",
        "삼성전자의 주요 사업 부문 구성과 각 부문의 역할은?",
        "삼성전자의 환율 변동 리스크 관리 방식을 설명해주세요.",
        "삼성전자 2023년 연구개발 투자 규모와 주요 방향은?",
    ]

    selected_example = st.selectbox(
        "예시 질문 선택 (또는 직접 입력)",
        options=["직접 입력"] + EXAMPLE_QUERIES,
        key="example_select",
    )

    if selected_example == "직접 입력":
        question = st.text_area(
            "질문 입력",
            height=80,
            placeholder="예: 삼성전자 2023년 주요 리스크는 무엇인가요?",
            key="custom_question",
        )
    else:
        question = selected_example
        st.text_area("질문", value=question, height=80, disabled=True, key="shown_question")

    scope_mode = st.radio(
        "검색할 보고서",
        ["전체 보고서", "목록에서 선택", "조건 직접 입력"],
        horizontal=True,
        key="query_scope_mode",
    )
    report_scope, scope_label, scope_ready = {}, "인덱싱된 전체 보고서", True
    if scope_mode == "목록에서 선택":
        if st.button("보고서 목록 불러오기 / 새로고침", key="query_catalog_refresh"):
            st.session_state.pop("query_report_catalog", None)
            try:
                services = load_components()
                with services.serialized_sync_operation():
                    if services.store is None:
                        raise RuntimeError(services.readiness.reason)
                    data = services.store.vector_store.get(include=["metadatas"])
                st.session_state["query_report_catalog"] = indexed_report_catalog(data.get("metadatas") or [])
            except Exception:
                st.error("보고서 목록을 불러오지 못했습니다. 연결 상태를 확인한 뒤 다시 불러오세요.")
        catalog, unidentified = st.session_state.get("query_report_catalog", ([], 0))
        scope_ready = False
        if catalog:
            companies = sorted({company for row in catalog for company in row["companies"]})
            if st.session_state.get("report_company_filter") not in [None, *companies]:
                st.session_state["report_company_filter"] = None
            company = st.selectbox("기업", [None, *companies],
                                   format_func=lambda value: value or "모든 기업", key="report_company_filter")
            visible = [row for row in catalog if company is None or company in row["companies"]]
            years = sorted({year for row in visible for year in row["years"]}, reverse=True)
            if st.session_state.get("report_year_filter") not in [None, *years]:
                st.session_state["report_year_filter"] = None
            year = st.selectbox("보고서 연도", [None, *years],
                                format_func=lambda value: "모든 연도" if value is None else str(value),
                                key="report_year_filter")
            visible = [row for row in visible if year is None or year in row["years"]]
            labels = {row["receipt"]: row["label"] for row in visible}
            chosen = st.session_state.get("selected_reports", [])
            if any(receipt not in labels for receipt in chosen):
                st.session_state["selected_reports"] = [receipt for receipt in chosen if receipt in labels]
            selected = st.multiselect("보고서 선택 (여러 개 선택 가능)", list(labels),
                                      format_func=labels.__getitem__, key="selected_reports")
            if selected:
                report_scope = {"source_receipts": selected}
                scope_label = " / ".join(labels[receipt] for receipt in selected)
                scope_ready = True
            else:
                st.info("검색할 보고서를 하나 이상 선택하세요.")
            st.caption("선택한 접수번호의 보고서에서만 검색합니다. 보고서 연도는 질문의 측정 기간과 다를 수 있습니다.")
        elif "query_report_catalog" in st.session_state:
            st.info("선택할 수 있는 보고서가 없습니다.")
        else:
            st.info("보고서 목록을 불러온 뒤 기업·연도로 좁혀 선택하세요.")
        if unidentified:
            st.warning(f"접수번호가 없는 자료 {unidentified}개는 보고서 목록에서 제외했습니다.")
    elif scope_mode == "조건 직접 입력":
        scope_company = st.text_input("기업명", key="query_scope_company")
        scope_year = st.text_input("보고서 연도", key="query_scope_year", placeholder="예: 2023")
        scope_receipt = st.text_input("공시 접수번호", key="query_scope_receipt")
        if scope_company.strip():
            report_scope["company"] = scope_company.strip()
        if scope_receipt.strip():
            report_scope["rcept_no"] = scope_receipt.strip()
        if scope_year.strip():
            try:
                report_scope["year"] = int(scope_year.strip())
            except ValueError:
                st.error("보고서 연도는 정수로 입력하세요.")
                scope_ready = False
        scope_ready = scope_ready and bool(report_scope)
        scope_label = " · ".join(f"{label}: {report_scope[key]}" for key, label in
                                 (("company", "기업"), ("year", "보고서 연도"), ("rcept_no", "접수번호"))
                                 if key in report_scope)
        st.caption("입력한 조건을 모두 만족하는 보고서에서 검색합니다. 조건을 하나 이상 입력하세요.")
    else:
        st.caption("모든 인덱싱된 보고서에서 검색합니다. 질문 속 기업명·연도를 검색 범위로 자동 적용하지 않습니다.")

    if st.button("🔍 분석 실행", type="primary", disabled=not question.strip() or not scope_ready):
        st.session_state.pop("query_display", None)
        services = load_components()

        with st.spinner("근거 검색 및 답변 생성 중..."):
            try:
                with services.serialized_sync_operation():
                    agent = services.agent
                    if not services.readiness.ready or agent is None:
                        raise RuntimeError(services.readiness.reason)
                    run_result = agent.run(
                        question,
                        report_scope=report_scope or None,
                        include_review_trace=True,
                    )
                    st.session_state["query_display"] = deepcopy({
                        "question": question, "scope_label": scope_label,
                        "answer": run_result.agent_answer, "review": run_result.review_trace or {},
                        "store_degraded": bool(getattr(services.readiness, "degraded", False)),
                    })

            except Exception as e:
                from src.utils.provider_errors import provider_error_projection
                logging.getLogger(__name__).error("Query failed: %s", provider_error_projection(e))
                st.error("답변 생성에 실패했습니다. 설정과 진단 기록을 확인하세요.")

    if "query_display" in st.session_state:
        display = st.session_state["query_display"]
        answer_result, review_trace = display["answer"], display["review"]
        st.divider()
        st.subheader("최근 답변")
        st.caption(f"질문: {display['question']}")
        st.caption(f"이 답변의 검색 범위: {display['scope_label']}")
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("답변 상태", "근거 부족" if answer_result.get("abstained") else "답변 생성")
        col_b.metric("검색된 기업", ", ".join(answer_result.get("companies", [])) or "—",
                     help="검색 근거에 기록된 기업입니다.")
        col_c.metric("검색된 보고서 연도", ", ".join(str(y) for y in answer_result.get("years", [])) or "—",
                     help="검색 근거에 기록된 보고서 연도입니다. 질문의 측정 기간을 판정한 값이 아닙니다.")
        answer_column, status_column = st.columns([3, 2])
        with answer_column:
            st.markdown(answer_result.get("answer", "답변 없음"))
            citations = answer_result.get("citations", [])
            if citations:
                with st.expander(f"📚 출처 ({len(citations)}건)", expanded=False):
                    for i, source in enumerate(answer_result.get("cited_sources", []), 1):
                        st.markdown(f"**{i}.** {source['source_id']}")
                        st.json(source["context"])
                        st.text(source["text"])
            retrieved_sources = review_trace.get("retrieved_sources", [])
            if retrieved_sources:
                with st.expander(f"🔎 답변 입력 근거 ({len(retrieved_sources)}개)"):
                    for source in retrieved_sources:
                        st.markdown(f"**{source['source_id']}**")
                        st.json(source["context"])
                        st.text(source["text"])
        with status_column:
            st.markdown("**검색·근거 상태**")
            for level, message in query_status_notices(
                answer_result, review_trace, store_degraded=display["store_degraded"],
            ):
                getattr(st, level)(message)
            st.caption("출처 ID 검사는 답변의 의미·계산·요청 항목 충족 여부를 검증하지 않습니다.")
