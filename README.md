# DART 기업 공시 분석 AI Agent

DART 전자공시 문서를 수집하고, 기업 공시에 대한 자연어 질문에 근거 기반 답변을 생성하는 한국어 RAG 분석 에이전트입니다.

현재 구현 범위에는 DART 수집, DART XML 파싱, 구조 기반 청킹, parent-child retrieval, contextual retrieval, LangGraph 기반 분석, 평가 파이프라인, FastAPI/Streamlit 인터페이스가 포함됩니다.

## 예시 질문

- "삼성전자 2024 사업보고서에서 회사가 영위하는 주요 사업은 무엇인가요?"
- "삼성전자 2024 사업보고서에서 주요 리스크로 언급된 내용은 무엇인가요?"
- "삼성전자와 SK하이닉스의 2024 영업이익을 비교해 주세요."
- "네이버 최근 3개년 연구개발 투자 흐름을 요약해 주세요."

## 기술 스택

| 분류 | 기술 |
|---|---|
| LLM | Google Gemini 2.5-flash |
| Orchestration | LangGraph |
| Search / RAG | ChromaDB + BM25 + RRF Hybrid Search |
| Embedding | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Parsing | `lxml` 기반 DART XML 파싱 |
| Data Ingestion | DART OpenAPI |
| MLOps | MLflow |
| API | FastAPI + uvicorn |
| UI | Streamlit |
| 환경 | Python + uv |

## 현재 아키텍처

```text
사용자 질문
    -> [QueryClassifier]   qa / comparison / trend / risk 분류
    -> [EntityExtractor]   기업명, 연도, 섹션 힌트, 주제 추출
    -> [Retriever]         Dense + BM25 + RRF + strict metadata filter + rerank
    -> [Evidence]          상위 청크에서 evidence bullet 추출
    -> [Analyst]           evidence bullet만 사용해 최종 답변 생성
    -> [CitationFormatter] 출처 메타데이터 정리
    -> 최종 답변
```

검색 인덱싱은 parent-child + contextual retrieval 구조를 사용합니다.

- 검색 대상: 자식 청크
- 답변 컨텍스트: 부모 섹션 청크 우선
- 인덱싱 텍스트: `LLM 컨텍스트 1문장 + 메타데이터 prefix + 자식 청크 원문`

## 프로젝트 구조

```text
dart-rag-agent/
├── src/
│   ├── ingestion/
│   │   └── dart_fetcher.py       DART API 연동 및 공시 문서 수집
│   ├── processing/
│   │   ├── financial_parser.py   DART XML 파싱 + 구조 기반 청킹
│   │   └── pdf_parser.py         과거 DocumentChunk 참조용 모듈
│   ├── storage/
│   │   └── vector_store.py       ChromaDB + BM25 + RRF + parents.json 관리
│   ├── agent/
│   │   ├── financial_graph.py    LangGraph Financial Analysis Agent
│   │   └── rag_chain.py          이전 범용 RAG 체인
│   ├── api/
│   │   └── financial_router.py   FastAPI 라우터
│   └── ops/
│       └── evaluator.py          평가 파이프라인
├── data/
│   ├── reports/                  다운로드한 DART 공시 문서
│   ├── chroma_dart/              ChromaDB 영속 저장소
│   └── eval/                     평가 데이터
├── app.py                        Streamlit UI
├── main.py                       FastAPI 진입점
├── CONTEXT.md                    다음 세션 인수인계 문서
├── DECISIONS.md                  기술 결정 로그
├── PLAN.md                       다음 확장 로드맵
└── REVIEW_FINDINGS.md            코드 리뷰 기록
```

## 구현 상태

- [x] DART API 연동 및 공시 문서 수집
- [x] DART XML 파싱 + 구조 기반 청킹
- [x] ChromaDB + BM25 하이브리드 검색
- [x] parent-child retrieval
- [x] contextual retrieval
- [x] evidence-first answer synthesis
- [x] FastAPI REST API + Streamlit UI
- [x] MLflow 연동 평가 파이프라인
- [x] 단일 기업 정확도 개선 스프린트
- [x] contextual ingest 병렬화 및 청크 크기 튜닝

## 최근 반영 사항

### 정확도 개선

- 임베딩 기본값을 다국어 모델 `paraphrase-multilingual-MiniLM-L12-v2`로 교체
- Chroma 컬렉션을 `dart_reports_v2`로 분리해 재인덱싱 기준 명확화
- hybrid dedup 기준을 raw text 대신 `chunk_uid`로 변경
- company / year strict filter를 non-empty 기준으로 유지하도록 수정
- 검색 rerank에 company / year / section / topic overlap boost 추가
- answer generation을 evidence-first 흐름으로 재구성
- 평가 지표에 `retrieval_hit_at_k`, `section_match_rate`, `citation_coverage` 추가

### parent-child + contextual retrieval

- 각 자식 청크에 `parent_id`를 부여하고 섹션 단위 부모 청크를 생성
- `parents.json`에 부모 텍스트를 별도 저장
- 검색은 자식 청크로 수행하고, 답변 컨텍스트는 부모 청크를 우선 사용
- 자식 청크 인덱싱 시 LLM이 생성한 1문장 컨텍스트를 prepend

### 속도 개선

- `contextual_ingest()`를 순차 `invoke()` 반복에서 `llm.batch(..., max_concurrency=...)` 기반 병렬 처리로 전환
- `CONTEXTUAL_INGEST_MAX_WORKERS` 환경변수로 병렬도 제어
- 파서 기본 청크 크기를 `2500 / 320`으로 조정해 자식 청크 수를 줄임
- 인덱싱 텍스트 앞에 `회사 / 연도 / 보고서 / 섹션 / 블록 타입` 메타데이터 prefix를 추가해 큰 청크에서도 retrieval 신호가 덜 묻히도록 보완

## 청킹 전략

DART XML 구조를 최대한 보존하는 2단계 청킹을 사용합니다.

| Level | 방식 | 적용 조건 |
|---|---|---|
| 1 | 구조 경계 기반 블록 청킹 | 기본 |
| 2 | `RecursiveCharacterTextSplitter` 재분할 | 단일 블록이 너무 길 때 |

기본 파라미터:

- `chunk_size = 2500`
- `chunk_overlap = 320`
- large table standalone threshold = `chunk_size // 2 = 1250`
- `build_parents(max_parent_len=6000)` 유지

청킹 흐름:

1. `SECTION-1/2/3` 기준으로 섹션 분리
2. 섹션 내부에서 `P`, `TABLE`, `TABLE-GROUP` 블록 수집
3. 작은 표는 인접 문단과 함께 누적
4. 큰 표는 단독 청크 처리
5. 너무 긴 블록만 문자 단위로 재분할
6. 같은 섹션의 자식 청크를 묶어 부모 청크 생성

청크 메타데이터:

- `chunk_uid`
- `block_type`
- `section`
- `section_path`
- `table_context`
- `parent_id`
- `company`, `year`, `report_type`, `rcept_no`

참고:

- 현재 `table_context`는 실제 요약이 아니라 직전 문단 preview에 가깝습니다.
- 답변은 이 preview만으로 생성하지 않고, 부모 섹션 원문 또는 `컨텍스트 + 자식 원문`을 사용합니다.

## 검색 파이프라인

```text
질문
  -> [Dense] ChromaDB similarity search + metadata where_filter
  -> [Sparse] BM25 (character bigram)
  -> [Fusion] RRF by chunk_uid
  -> [Strict Filter] company / year
  -> [Rerank] exact metadata match + topic lexical overlap
  -> 최종 k개 청크
```

추가 메모:

- BM25는 한국어 조사 결합을 다루기 위해 character bigram 토크나이저를 사용합니다.
- section 정보는 hard filter보다 rerank boost로 더 많이 반영합니다.
- 동일한 boilerplate 문구는 `chunk_uid` 기준으로 별도 청크로 유지됩니다.

## 벤치마크 메모

기준 문서:

- 삼성전자 2024 사업보고서
- DART 접수번호 `20250311001085`

대표 비교 결과:

| 설정 | 파싱 시간 | 청크 수 | contextual ingest 시간 | 비고 |
|---|---:|---:|---:|---|
| `1500 / 200` | `1.603초` | `502` | `1013.569초` | 기존 기준 |
| `2800 / 350` | `0.548초` | `266` | `292.289초` | 속도는 좋지만 리스크 질의 품질 회귀 |
| `2500 / 320` | `0.608초` | `300` | `584.25초` | 최종 채택 |

채택 이유:

- `2500 / 320`은 청크 수와 contextual ingest 시간을 충분히 줄이면서도
- 사업 질의와 리스크 질의가 모두 정상적으로 회복된 가장 균형 잡힌 설정이었습니다.

## 로컬 실행

### 1. 환경 설정

```bash
uv venv .venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```

`.env` 파일:

```text
GOOGLE_API_KEY=...
DART_API_KEY=...
```

### 2. 인덱스 관련 주의

현재 기본 컬렉션은 `dart_reports_v2`입니다.

- 임베딩 모델이 바뀌었기 때문에 기존 `dart_reports` 인덱스와 혼용하지 않는 것을 권장합니다.
- 실제 사용 전에는 `contextual_ingest()` 기준으로 재인덱싱하는 것이 가장 안전합니다.

### 3. Streamlit UI 실행

```bash
streamlit run app.py
```

- Tab 1: DART 수집 및 contextual ingest
- Tab 2: 질의 / 답변 / 인용 / retrieval debug
- Tab 3: 평가 및 MLflow 지표 확인

### 4. FastAPI 실행

```bash
uvicorn main:app --reload --port 8000
```

Swagger UI: `http://localhost:8000/docs`

| 엔드포인트 | 설명 |
|---|---|
| `POST /api/ingest` | `{ "company": "삼성전자", "years": [2024] }` 형태로 수집 + 인덱싱 |
| `POST /api/query` | `{ "question": "..." }` 형태로 분석 답변 반환 |
| `GET /api/companies` | 인덱싱된 기업 목록 조회 |
| `GET /api/health` | 서버 상태 확인 |

### 5. 개별 모듈 스모크 테스트

```bash
cd src
python -m ingestion.dart_fetcher
python -m processing.financial_parser
python -m agent.financial_graph
python -m ops.evaluator
```

### 6. MLflow UI

```bash
mlflow ui --backend-store-uri mlruns/
```

## 참고 문서

- [CONTEXT.md](CONTEXT.md): 다음 세션 인수인계와 현재 상태 메모
- [DECISIONS.md](DECISIONS.md): 기술 결정과 문제 해결 로그
- [PLAN.md](PLAN.md): 다음 확장 로드맵
- [REVIEW_FINDINGS.md](REVIEW_FINDINGS.md): 최근 코드 리뷰 findings
