# DART 기업 공시 분석 AI Agent

DART(전자공시시스템) 공개 공시 문서를 수집하고, 자연어 질문에 대해 근거 기반 답변을 생성하는 한국어 RAG 분석 시스템입니다.  
현재 구현은 DART 수집, DART XML 파싱, 하이브리드 검색, LangGraph 기반 분석, 평가, FastAPI/Streamlit 제공까지 포함합니다.

## 지원 쿼리 예시

- "삼성전자 2023년 반도체 사업의 주요 리스크 요인은 무엇인가요?"
- "삼성전자와 SK하이닉스의 2023년 영업이익을 비교해주세요"
- "네이버 최근 3년간 매출 성장 트렌드를 분석해주세요"
- "삼성전자 2024년 연결 기준 매출액과 영업이익은?"

## 기술 스택

| 분류 | 기술 |
|---|---|
| LLM | Google Gemini 2.5-flash |
| Orchestration | LangGraph |
| Search / RAG | ChromaDB + BM25 + RRF Hybrid Search |
| Embedding | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| Parsing | lxml 기반 DART XML 파싱 + 구조 우선 청킹 |
| Data Ingestion | DART OpenAPI |
| MLOps | MLflow |
| API | FastAPI + uvicorn |
| UI | Streamlit |
| 환경 | Python + uv |

## 현재 아키텍처

```text
사용자 질문
    ↓
[QueryClassifier]   qa / comparison / trend / risk 분류
    ↓
[EntityExtractor]   기업명, 연도, 섹션 필터, 주제어 추출
    ↓
[Retriever]         Dense + BM25 + RRF + strict metadata filter + rerank
    ↓
[Evidence]          상위 청크에서 근거 bullet 추출
    ↓
[Analyst]           근거 bullet만 사용해 최종 답변 생성
    ↓
[CitationFormatter] 출처 메타데이터 정리
    ↓
최종 답변
```

## 프로젝트 구조

```text
dart-rag-agent/
├── src/
│   ├── ingestion/
│   │   └── dart_fetcher.py       DART API 연동 및 공시 문서 수집
│   ├── processing/
│   │   ├── financial_parser.py   DART XML 파싱 + 구조 기반 청킹
│   │   └── pdf_parser.py         레거시 DocumentChunk 참조용 모듈
│   ├── storage/
│   │   └── vector_store.py       ChromaDB + BM25 + RRF Hybrid Search
│   ├── agent/
│   │   ├── financial_graph.py    LangGraph Financial Analysis Agent
│   │   └── rag_chain.py          이전 범용 RAG 체인 (현재 주 경로 아님)
│   ├── api/
│   │   └── financial_router.py   FastAPI 라우터
│   └── ops/
│       └── evaluator.py          RAG 평가 파이프라인 (MLflow 연동)
├── data/
│   ├── reports/                  다운로드된 DART 공시 문서
│   ├── chroma_dart/              ChromaDB 영속 저장소
│   └── eval/                     평가 데이터셋
├── app.py                        Streamlit UI
├── main.py                       FastAPI 진입점
├── CONTEXT.md                    다음 세션 인수인계 문서
├── DECISIONS.md                  기술 결정 및 문제 해결 로그
├── PLAN.md                       다음 확장 로드맵
└── REVIEW_FINDINGS.md            최근 코드 리뷰 기록
```

## 구현 상태

- [x] DART API 연동 및 공시 문서 수집
- [x] DART XML 파서 + 구조 기반 청킹
- [x] LangGraph 기반 재무 분석 에이전트
- [x] FastAPI REST API + Streamlit UI
- [x] MLflow 연동 평가 파이프라인
- [x] 단일 기업 정확도 향상 스프린트

### 최근 정확도 향상 반영 사항

- 임베딩 기본값을 다국어 모델 `paraphrase-multilingual-MiniLM-L12-v2`로 교체
- Chroma 컬렉션을 `dart_reports_v2`로 분리해 재인덱싱 기준 명확화
- 하이브리드 검색 dedup 기준을 raw text 대신 `chunk_uid`로 변경
- 회사/연도/섹션 필터가 1개 결과만 남겨도 유지되도록 strict filter 적용
- 청크 메타데이터에 `chunk_uid`, `block_type`, `section_path`, `table_context` 추가
- 답변 생성을 evidence-first 방식으로 변경
- 평가 지표에 `retrieval_hit_at_k`, `section_match_rate`, `citation_coverage` 추가

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

### 2. 인덱싱 관련 주의

현재 기본 컬렉션은 `dart_reports_v2`입니다.  
이전 `dart_reports` 컬렉션과 임베딩 모델이 다르므로, 실제 사용 전에는 문서를 다시 수집하거나 재인덱싱하는 것이 안전합니다.

### 3. Streamlit UI 실행

```bash
streamlit run app.py
```

- Tab 1: 기업명 + 연도 기반 DART 수집 및 인덱싱
- Tab 2: 자연어 질문 분석, 답변, 출처, 검색 청크 확인
- Tab 3: 평가 지표 및 MLflow 실험 확인

### 4. FastAPI 실행

```bash
uvicorn main:app --reload --port 8000
```

Swagger UI: `http://localhost:8000/docs`

| 엔드포인트 | 설명 |
|---|---|
| `POST /api/ingest` | `{ "company": "삼성전자", "years": [2024] }` → 수집 + 인덱싱 |
| `POST /api/query` | `{ "question": "..." }` → 분석 답변 반환 |
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

## 검색 파이프라인

```text
질문
 ├─ [Dense] ChromaDB similarity search + metadata where_filter
 ├─ [Sparse] BM25 (character bigram)
 ├─ [Fusion] RRF by chunk_uid
 ├─ [Strict Filter] company / year / section
 └─ [Rerank] exact metadata match + topic lexical overlap
      ↓
    최종 k개 청크
```

### 검색 설계 포인트

- BM25는 한국어 조사 결합형을 처리하기 위해 character bigram 토크나이저 사용
- 회사/연도 조건은 가능하면 Chroma 검색 시점부터 적용
- strict filter는 결과가 1개라도 남아 있으면 유지
- 동일 본문 반복 문구는 `chunk_uid`로 구분해 서로 다른 청크가 합쳐지지 않게 처리

## 청킹 전략

DART XML의 구조를 우선 보존하는 2단계 청킹을 사용합니다.

| Level | 방식 | 적용 조건 |
|---|---|---|
| 1 | 구조 경계 기준 블록 청킹 | 기본 |
| 2 | RecursiveCharacterTextSplitter 폴백 | 단일 블록이 길 때 |

### 청크 메타데이터

- `chunk_uid`: 청크의 안정적 식별자
- `block_type`: `paragraph` 또는 `table`
- `section`: 규칙 기반 섹션 라벨
- `section_path`: 중첩 섹션 breadcrumb
- `table_context`: 표 직전 문맥 요약
- `company`, `year`, `report_type`, `rcept_no` 등 출처 메타데이터

### 테이블 처리 전략

- 소형 표는 인접 단락과 함께 누적해 문맥 유지
- 대형 표는 단독 청크로 분리
- 큰 표가 여러 청크로 나뉘는 경우 첫 청크에 `table_context` 유지

## 평가 지표

| 지표 | 설명 |
|---|---|
| Faithfulness | 답변이 검색 근거에 충실한가 |
| Answer Relevancy | 질문과 답변의 의미 관련성 |
| Context Recall | 정답 정보가 검색 컨텍스트에 포함되는가 |
| Retrieval Hit@K | 기대 근거가 상위 검색 결과에 포함되는가 |
| Section Match Rate | 예상 섹션과 실제 검색 섹션이 맞는가 |
| Citation Coverage | 최종 답변의 근거 bullet이 출처와 연결되는가 |

## 참고 문서

- [CONTEXT.md](CONTEXT.md): 다음 세션 인수인계용 현재 상태 정리
- [DECISIONS.md](DECISIONS.md): 문제 해결 및 기술 결정 로그
- [PLAN.md](PLAN.md): 다음 확장 로드맵
- [REVIEW_FINDINGS.md](REVIEW_FINDINGS.md): 최근 코드 리뷰 findings
