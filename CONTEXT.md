# 프로젝트 컨텍스트 — Claude와의 대화 이어가기

> 이 파일은 다른 기기/세션에서 Claude와 대화를 이어갈 때 읽어줄 것을 요청하세요.
> 새 대화 시작 시: "CONTEXT.md 읽고 이어서 작업해줘"

---

## 목적

Applied AI Technical Engineer (ML) / 전문연구요원 JD에 맞춘 포트폴리오 프로젝트.
**DART(전자공시시스템) 공개 데이터 기반 기업 공시 분석 AI Agent** 구축 중.

JD 핵심 요구사항:
- RAG + Hybrid Search (Vector DB + BM25)
- LangGraph 기반 AI Agent 오케스트레이션
- MLOps: 평가 파이프라인 + MLflow 실험 추적
- FastAPI 서비스화

---

## 현재 프로젝트 구조

```
research agent/
├── src/
│   ├── ingestion/
│   │   └── dart_fetcher.py       ✅ Phase 1 완료
│   ├── processing/
│   │   └── pdf_parser.py         ✅ 기존 코드 재활용 예정
│   ├── storage/
│   │   └── vector_store.py       ✅ 기존 코드 재활용 예정
│   ├── agent/
│   │   └── rag_chain.py          ✅ 기존 코드 재활용 예정 (프롬프트 교체 필요)
│   ├── api/                      ❌ Phase 5에서 구현 예정
│   └── ops/                      ❌ Phase 4에서 구현 예정
├── archive/                      기존 arxiv/github 관련 코드 보관 (.gitignore)
├── data/                         다운로드 데이터 (.gitignore)
├── PLAN.md                       전체 구현 계획 상세
├── CONTEXT.md                    이 파일
├── .env                          API 키 (GOOGLE_API_KEY, DART_API_KEY)
└── requirements.txt
```

---

## 구현 완료 항목

### Phase 1 — DART 데이터 수집 레이어 ✅
**파일**: `src/ingestion/dart_fetcher.py`

- `DARTFetcher` 클래스
  - `get_corp_code(company_name)` — 회사명 → DART corp_code (부분 일치 폴백)
  - `get_filing_list(corp_code, year, report_type)` — 공시 목록 조회
  - `download_document(report)` — 문서 ZIP → 본문 HTML 로컬 저장
  - `fetch_company_reports(company_name, years)` — 일괄 수집 고수준 인터페이스
- `ReportMetadata` Pydantic 모델 (rcept_no, corp_name, stock_code, year 등)
- 저장 경로: `data/reports/{corp_name}/{year}_{report_type}_{rcept_no}.html`

**미완료**: DART_API_KEY 미발급 상태 (인증 메일 대기 중). 발급 후 스모크 테스트 필요.

```bash
# 스모크 테스트 명령어
cd src && python -m ingestion.dart_fetcher
```

---

## 다음 단계

### Phase 2 — 재무 문서 파싱 특화 (다음 작업)
**신규 파일**: `src/processing/financial_parser.py`

기존 `pdf_parser.py`의 `PDFParser`를 확장:
- HTML 파싱 지원 추가 (DART 문서가 HTML 형식으로 다운로드됨)
- 재무 도메인 섹션 자동 분류:
  - `사업의 개요`, `주요 리스크`, `재무 현황`, `임원 현황` 등
- 청크 메타데이터에 재무 필드 추가:
  ```python
  {
    "company": "삼성전자",
    "stock_code": "005930",
    "year": 2023,
    "report_type": "사업보고서",
    "section": "주요 리스크",
    "source_page": 42
  }
  ```

### Phase 3 — Financial Analysis Agent
**신규 파일**: `src/agent/financial_graph.py`

LangGraph 기반 멀티스텝 분석 Agent:
```
query_classifier → entity_extractor → retrieval → analyst → citation
```
- 쿼리 유형: 단순 QA / 기업 간 비교 / 시계열 트렌드 / 리스크 분석
- 기존 `rag_chain.py`의 RAGAgent를 재활용하되 프롬프트 교체 필요

### Phase 4 — 평가 파이프라인
**신규 파일**: `src/ops/evaluator.py`
- 평가셋 20개 질문 + 수동 정답
- Faithfulness / Answer Relevancy / Context Recall 지표
- MLflow 실험 추적

### Phase 5 — FastAPI + Streamlit UI
**신규 파일**: `src/api/financial_router.py`
- `POST /ingest`, `POST /query`, `GET /companies`

---

## 주요 기술 결정 사항

| 항목 | 결정 | 이유 |
|---|---|---|
| 문서 포맷 | HTML (DART ZIP 추출) | DART API가 PDF 아닌 HTML 반환 |
| LLM | Google Gemini 2.5-flash | 기존 GOOGLE_API_KEY 활용 |
| Vector DB | ChromaDB (로컬) | 기존 코드 재활용 |
| Hybrid Search | Dense + BM25 + RRF | 기존 vector_store.py 재활용 |
| Orchestration | LangGraph | JD 요구사항 |

---

## 환경 설정

```bash
# 가상환경 (uv 사용)
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt

# .env 파일에 필요한 키
GOOGLE_API_KEY=...   # 발급됨
DART_API_KEY=...     # 발급 대기 중
```

---

## 참고 링크

- DART OpenAPI 키 발급: https://opendart.fss.or.kr/intro/main.do
- DART API 문서: https://opendart.fss.or.kr/guide/main.do
- 상세 구현 계획: `PLAN.md` 참고
