"""
Streamlit UI — DART 공시 분석 AI Agent

탭 구성:
  Tab 1: 기업 데이터 수집 — DART 수집 + 파싱 + 인덱싱
  Tab 2: 질문 분석         — 자연어 질문 → Agent → 답변 + 출처
  Tab 3: 평가 대시보드     — 지표 시각화 + MLflow 실험 결과

실행:
    streamlit run app.py
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import streamlit as st

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
    from storage.vector_store import DEFAULT_COLLECTION_NAME, VectorStoreManager
    from agent.financial_graph import FinancialAgent
    from processing.financial_parser import (
        DEFAULT_CHUNK_OVERLAP,
        DEFAULT_CHUNK_SIZE,
        FinancialParser,
    )
    from ingestion.dart_fetcher import DARTFetcher
    from ops.evaluator import RAGEvaluator

    _PROJECT_ROOT = Path(__file__).resolve().parent
    chroma_path   = str(_PROJECT_ROOT / "data" / "chroma_dart")
    reports_dir   = str(_PROJECT_ROOT / "data" / "reports")

    vsm     = VectorStoreManager(persist_directory=chroma_path, collection_name=DEFAULT_COLLECTION_NAME)
    agent   = FinancialAgent(vsm, k=8)
    parser  = FinancialParser(chunk_size=DEFAULT_CHUNK_SIZE, chunk_overlap=DEFAULT_CHUNK_OVERLAP)
    fetcher = DARTFetcher(download_dir=reports_dir)
    evaluator = RAGEvaluator(agent)

    return vsm, agent, parser, fetcher, evaluator


# --------------------------------------------------------------------------
# 페이지 설정
# --------------------------------------------------------------------------

st.set_page_config(
    page_title="DART 공시 분석 AI",
    page_icon="📊",
    layout="wide",
)

st.title("📊 DART 공시 분석 AI Agent")
st.caption("DART(전자공시시스템) 기반 기업 공시 문서를 분석하는 AI Agent")

# --------------------------------------------------------------------------
# 탭 구성
# --------------------------------------------------------------------------

tab1, tab2, tab3 = st.tabs(["📥 데이터 수집", "💬 질문 분석", "📈 평가 대시보드"])


# ══════════════════════════════════════════════════════════════════════════
# Tab 1: 기업 데이터 수집
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
        vsm, agent, parser, fetcher, evaluator = load_components()

        with st.status(f"'{company_input}' {selected_years} 처리 중...", expanded=True) as status:
            try:
                st.write("📡 DART API에서 공시 목록 조회...")
                reports = fetcher.fetch_company_reports(company_input, selected_years)

                if not reports:
                    status.update(label="공시 문서를 찾을 수 없습니다.", state="error")
                    st.error(f"'{company_input}'의 {selected_years} 공시 문서를 찾을 수 없습니다.")
                else:
                    total_chunks = 0
                    skipped = 0
                    progress = st.progress(0)
                    for i, report in enumerate(reports):
                        if not report.file_path or not Path(report.file_path).exists():
                            continue
                        if vsm.is_indexed(report.rcept_no):
                            st.write(f"⏭️ 이미 인덱싱됨: {report.corp_name} {report.year} 사업보고서 — 건너뜀")
                            skipped += 1
                            progress.progress((i + 1) / len(reports))
                            continue
                        st.write(f"📄 파싱 중: {report.corp_name} {report.year} 사업보고서")
                        meta = {
                            "company":     report.corp_name,
                            "stock_code":  report.stock_code or "unknown",
                            "year":        report.year,
                            "report_type": report.report_type,
                            "rcept_no":    report.rcept_no,
                        }
                        chunks = parser.process_document(report.file_path, meta)
                        if chunks:
                            st.write(f"  → LLM 컨텍스트 생성 및 인덱싱 중: {len(chunks)}개 청크 (병렬 {CONTEXT_MAX_WORKERS}개)")
                            ctx_progress = st.progress(0, text="LLM 컨텍스트 생성 중... (0/{})".format(len(chunks)))

                            def _on_ctx_progress(done, total, _pb=ctx_progress):
                                _pb.progress(done / total, text=f"LLM 컨텍스트 생성 중... ({done}/{total})")

                            agent.contextual_ingest(
                                chunks,
                                on_progress=_on_ctx_progress,
                                max_workers=CONTEXT_MAX_WORKERS,
                            )
                            ctx_progress.empty()
                            total_chunks += len(chunks)
                        progress.progress((i + 1) / len(reports))

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
        vsm, *_ = load_components()
        try:
            data = vsm.vector_store.get(include=["metadatas"])
            metadatas = data.get("metadatas") or []

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
# Tab 2: 질문 분석
# ══════════════════════════════════════════════════════════════════════════

with tab2:
    st.subheader("자연어 질문 분석")
    st.caption("질문을 입력하면 LangGraph 기반 AI Agent가 분석합니다.")

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

    if st.button("🔍 분석 실행", type="primary", disabled=not question):
        _, agent, *_ = load_components()

        with st.spinner("Agent 분석 중..."):
            try:
                result = agent.run(question)

                # 쿼리 유형 배지
                qtype_label = {
                    "qa":         "📋 단순 QA",
                    "comparison": "⚖️ 기업 비교",
                    "trend":      "📈 트렌드 분석",
                    "risk":       "⚠️ 리스크 분석",
                }.get(result.get("query_type", ""), "🔍 분석")

                col_a, col_b, col_c = st.columns(3)
                col_a.metric("쿼리 유형", qtype_label)
                extracted_companies = result.get("companies", [])
                extracted_years     = result.get("years", [])
                col_b.metric(
                    "인식된 기업",
                    ", ".join(extracted_companies) if extracted_companies else "—",
                    help="Agent가 질문에서 추출한 기업명. 비어있으면 필터 미적용.",
                )
                col_c.metric(
                    "인식된 연도",
                    ", ".join(str(y) for y in extracted_years) if extracted_years else "—",
                    help="Agent가 질문에서 추출한 연도. 비어있으면 필터 미적용.",
                )

                st.divider()
                st.subheader("답변")
                st.markdown(result.get("answer", "답변 없음"))

                citations = result.get("citations", [])
                if citations:
                    with st.expander(f"📚 출처 ({len(citations)}건)", expanded=False):
                        for i, cite in enumerate(citations, 1):
                            st.markdown(f"**{i}.** {cite}")

                retrieved_docs = result.get("retrieved_docs", [])
                if retrieved_docs:
                    with st.expander(f"🔎 검색된 청크 ({len(retrieved_docs)}개) — 클릭하여 검색 결과 원문 확인", expanded=False):
                        for i, item in enumerate(retrieved_docs, 1):
                            doc, score = (item[0], item[1]) if isinstance(item, (tuple, list)) else (item, None)
                            meta = getattr(doc, "metadata", {}) or {}
                            section  = meta.get("section_path", meta.get("section", "—"))
                            chunk_tp = meta.get("block_type", "—")
                            company  = meta.get("company", "—")
                            year     = meta.get("year", "—")
                            score_str = f"{score:.4f}" if score is not None else "—"
                            st.markdown(
                                f"**#{i}** &nbsp; `{company} {year}` &nbsp; 섹션: `{section}` &nbsp; "
                                f"유형: `{chunk_tp}` &nbsp; 점수: `{score_str}`"
                            )
                            if meta.get("table_context"):
                                st.caption(f"Table context: {meta['table_context']}")
                            st.text_area(
                                label=f"청크 #{i} 내용",
                                value=getattr(doc, "page_content", None) or getattr(doc, "content", ""),
                                height=150,
                                disabled=True,
                                key=f"chunk_text_{i}",
                                label_visibility="collapsed",
                            )
                            st.divider()

            except Exception as e:
                st.error(f"분석 실패: {e}")


# ══════════════════════════════════════════════════════════════════════════
# Tab 3: 평가 대시보드
# ══════════════════════════════════════════════════════════════════════════

with tab3:
    st.subheader("RAG 평가 대시보드")
    st.caption("Faithfulness / Answer Relevancy / Context Recall 지표와 MLflow 실험 결과를 확인합니다.")

    _PROJECT_ROOT = Path(__file__).resolve().parent

    col_run, col_cfg = st.columns([2, 1])

    with col_cfg:
        st.markdown("**평가 설정**")
        n_questions = st.slider("평가 문항 수", min_value=1, max_value=20, value=3, step=1)
        run_name_input = st.text_input("MLflow Run 이름", value="streamlit_eval")

    with col_run:
        st.markdown("**평가 실행**")
        if st.button("▶️ 평가 시작", type="primary"):
            _, agent, _, _, evaluator = load_components()
            dataset = evaluator.load_dataset()
            subset = evaluator.build_single_company_eval_slice(dataset, max_questions=n_questions)

            with st.spinner(f"{len(subset)}개 질문 평가 중..."):
                results = evaluator.run(
                    examples=subset,
                    run_name=run_name_input,
                    params={"n_questions": len(subset), "mode": "single_company_accuracy"},
                )

            st.session_state["eval_results"] = results["per_question"]
            st.session_state["eval_aggregate"] = results["aggregate"]
            st.success("평가 완료! MLflow에 기록되었습니다.")

    # 결과 표시
    if "eval_aggregate" in st.session_state:
        agg = st.session_state["eval_aggregate"]

        st.divider()
        st.subheader("집계 지표")

        c1, c2, c3 = st.columns(3)
        c1.metric("Faithfulness", f"{agg['faithfulness']:.3f}", help="답변이 컨텍스트에 근거하는 정도 (LLM judge)")
        c2.metric("Answer Relevancy", f"{agg['answer_relevancy']:.3f}", help="질문-답변 의미 유사도 (임베딩 코사인)")
        c3.metric("Context Recall", f"{agg['context_recall']:.3f}", help="정답 키워드 검색 커버리지")

        c4, c5, c6 = st.columns(3)
        c4.metric("Retrieval Hit@k", f"{agg['retrieval_hit_at_k']:.3f}", help="기대 회사/연도/섹션이 검색 결과에 포함되는 비율")
        c5.metric("Section Match", f"{agg['section_match_rate']:.3f}", help="검색 청크 중 기대 섹션 비율")
        c6.metric("Citation Coverage", f"{agg['citation_coverage']:.3f}", help="최종 인용이 기대 회사/연도/섹션을 얼마나 덮는지")

        st.metric("평균 점수", f"{agg['avg_score']:.3f}")

        # 레이더 차트
        try:
            import pandas as pd
            import altair as alt

            chart_data = pd.DataFrame({
                "지표": [
                    "Faithfulness",
                    "Answer Relevancy",
                    "Context Recall",
                    "Retrieval Hit@k",
                    "Section Match",
                    "Citation Coverage",
                ],
                "점수": [
                    agg["faithfulness"],
                    agg["answer_relevancy"],
                    agg["context_recall"],
                    agg["retrieval_hit_at_k"],
                    agg["section_match_rate"],
                    agg["citation_coverage"],
                ],
            })

            bar = (
                alt.Chart(chart_data)
                .mark_bar()
                .encode(
                    x=alt.X("지표:N", sort=None),
                    y=alt.Y("점수:Q", scale=alt.Scale(domain=[0, 1])),
                    color=alt.Color(
                        "지표:N",
                        scale=alt.Scale(
                            domain=[
                                "Faithfulness",
                                "Answer Relevancy",
                                "Context Recall",
                                "Retrieval Hit@k",
                                "Section Match",
                                "Citation Coverage",
                            ],
                            range=["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", "#B279A2"],
                        ),
                        legend=None,
                    ),
                    tooltip=["지표", alt.Tooltip("점수:Q", format=".3f")],
                )
                .properties(width=400, height=280, title="RAG 평가 지표")
            )
            st.altair_chart(bar, use_container_width=False)
        except Exception:
            pass

        # 문항별 결과 테이블
        st.divider()
        st.subheader("문항별 결과")
        per = st.session_state["eval_results"]
        import pandas as pd
        df = pd.DataFrame([
            {
                "ID": r.id,
                "질문": r.question[:45] + "..." if len(r.question) > 45 else r.question,
                "Faithfulness": f"{r.faithfulness:.2f}",
                "Relevancy":    f"{r.answer_relevancy:.2f}",
                "Recall":       f"{r.context_recall:.2f}",
                "Hit@k":        f"{r.retrieval_hit_at_k:.2f}",
                "Section":      f"{r.section_match_rate:.2f}",
                "Citation":     f"{r.citation_coverage:.2f}",
                "Latency(s)":   f"{r.latency_sec:.1f}",
                "오류": r.error or "",
            }
            for r in per
        ])
        st.dataframe(df, use_container_width=True, hide_index=True)

    # MLflow 실험 이력
    st.divider()
    st.subheader("MLflow 실험 이력")
    mlruns_path = _PROJECT_ROOT / "mlruns"

    if st.button("📂 실험 이력 불러오기"):
        try:
            import mlflow
            client = mlflow.tracking.MlflowClient(tracking_uri=str(mlruns_path))
            experiments = client.search_experiments()
            all_runs = []
            for exp in experiments:
                runs = client.search_runs(
                    experiment_ids=[exp.experiment_id],
                    order_by=["start_time DESC"],
                    max_results=20,
                )
                for run in runs:
                    m = run.data.metrics
                    all_runs.append({
                        "실험":           exp.name,
                        "Run":            run.info.run_name or run.info.run_id[:8],
                        "Faithfulness":   f"{m.get('agg_faithfulness', m.get('faithfulness', 0)):.3f}",
                        "Relevancy":      f"{m.get('agg_answer_relevancy', m.get('answer_relevancy', 0)):.3f}",
                        "Recall":         f"{m.get('agg_context_recall', m.get('context_recall', 0)):.3f}",
                        "Avg Score":      f"{m.get('agg_avg_score', 0):.3f}",
                        "시작 시각":       run.info.start_time,
                    })

            if all_runs:
                import pandas as pd
                df_runs = pd.DataFrame(all_runs)
                st.dataframe(df_runs, use_container_width=True, hide_index=True)
            else:
                st.info("실험 이력이 없습니다. 평가를 먼저 실행하세요.")
        except Exception as e:
            st.error(f"MLflow 조회 실패: {e}")

    st.caption("💡 상세 실험 비교: `mlflow ui --backend-store-uri mlruns/` 실행 후 http://localhost:5000 접속")
