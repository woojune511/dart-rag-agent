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
│   │   ├── pdf_parser.py         ✅ 기존 코드 (DocumentChunk 정의 포함)
│   │   └── financial_parser.py   ✅ Phase 2 완료
│   ├── storage/
│   │   └── vector_store.py       ✅ 기존 코드 재활용 예정
│   ├── agent/
│   │   └── rag_chain.py          ✅ 기존 코드 재활용 예정 (프롬프트 교체 필요)
│   ├── api/                      ❌ Phase 5에서 구현 예정
│   └── ops/                      ❌ Phase 4에서 구현 예정
├── archive/                      기존 arxiv/github 관련 코드 보관 (.gitignore)
├── data/
│   └── reports/삼성전자/          ✅ 2023 사업보고서 다운로드됨 (4.4MB DART XML)
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
  - `download_document(report)` — 문서 ZIP → 본문 파일 로컬 저장
  - `fetch_company_reports(company_name, years)` — 일괄 수집 고수준 인터페이스
- `ReportMetadata` Pydantic 모델 (rcept_no, corp_name, stock_code, year 등)
- 저장 경로: `data/reports/{corp_name}/{year}_{report_type}_{rcept_no}.html`
- DART_API_KEY는 `.env`에 있음. 스모크 테스트 완료 (삼성전자 2023 사업보고서)

```bash
cd src && python -m ingestion.dart_fetcher
```

### Phase 2 — DART XML 파서 ✅
**파일**: `src/processing/financial_parser.py`

DART 고유 XML 포맷(`.html` 확장자로 저장)을 파싱:

- `FinancialParser` 클래스
  - `parse_sections(file_path)` → `List[(title, label, text)]`
  - `process_document(file_path, source_metadata)` → `List[DocumentChunk]`
- **파싱 방식**: `SECTION-1/2/3` 태그를 섹션 경계로 사용, `<TITLE ATOC="Y">` 헤더 활용
- **텍스트 추출**: `P` 태그(itertext), `TD`/`TU`(P 자식 없는 경우) — 중복 방지
- **섹션 분류**: 22개 레이블 키워드 매핑 (리스크, 재무제표, 임원현황 등)
- **청킹**: `RecursiveCharacterTextSplitter(1500자, overlap 200)`
- **출력**: `DocumentChunk(content, metadata)` — `vector_store.py` 호환

스모크 테스트 결과: 삼성전자 2023 사업보고서 → 42개 섹션 / 615개 청크

```bash
cd src && python -m processing.financial_parser
```

**중요 기술 사항**:
- DART XML은 `.html` 확장자로 저장되지만 실제로는 DART 독자 XML 포맷
- lxml의 `etree.XMLParser(recover=True, huge_tree=True)` 필요
- `DocumentChunk`는 `pdf_parser.py`에서 import (`from processing.pdf_parser import DocumentChunk`)

---

### Phase 3 — LangGraph Financial Analysis Agent ✅
**파일**: `src/agent/financial_graph.py`

LangGraph 5-노드 파이프라인: `classify → extract → retrieve → analyze → cite`

- `QueryClassification` (Pydantic): qa/comparison/trend/risk 분류 (Gemini structured output)
- `EntityExtraction` (Pydantic): company, year, topic, section_filter 추출
- `_retrieve`: 하이브리드 검색 + section/company/year 메타데이터 후처리 필터
- `_analyze`: 쿼리 유형별 전용 프롬프트 (리스크 항목화, 표 비교, 연도별 트렌드 등)
- `_format_citations`: 중복 제거 인용 목록

공개 인터페이스:
- `agent.ingest(chunks)` — DocumentChunk → ChromaDB (`data/chroma_dart/`, collection="dart_reports")
- `agent.run(query)` → `{query, query_type, companies, years, answer, citations}`

스모크 테스트: 삼성전자 2023 615청크 인덱싱 후 리스크 질의 정상 답변 확인

```bash
cd src && python -m agent.financial_graph
```

---

## 다음 단계

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
| 문서 포맷 | DART 독자 XML (.html 확장자) | DART API ZIP 내부 파일 형식 |
| LLM | Google Gemini 2.5-flash | 기존 GOOGLE_API_KEY 활용 |
| Vector DB | ChromaDB (로컬) | 기존 코드 재활용 |
| Hybrid Search | Dense + BM25 + RRF | 기존 vector_store.py 재활용 |
| Orchestration | LangGraph | JD 요구사항 |
| XML 파서 | lxml (recover=True) | DART XML 비표준 구조 대응 |

---

## 환경 설정

```bash
# 가상환경 (uv 사용)
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt

# .env 파일에 필요한 키
GOOGLE_API_KEY=...   # 발급됨
DART_API_KEY=...     # 발급됨 (.env에 저장)
```

---

## 참고 링크

- DART OpenAPI: https://opendart.fss.or.kr/intro/main.do
- DART API 문서: https://opendart.fss.or.kr/guide/main.do
- 상세 구현 계획: `PLAN.md` 참고
