# DART 기업 공시 분석 AI Agent

DART(전자공시시스템) 공개 데이터를 기반으로 자연어 질문에 답하는 기업 공시 분석 AI Agent.  
사업보고서를 자동 수집하고, Hybrid Search + LangGraph 기반 멀티스텝 분석을 수행한다.

## 지원 쿼리 예시

- "삼성전자 2023년 반도체 사업의 주요 리스크 요인은 무엇인가요?"
- "삼성전자와 SK하이닉스의 2023년 영업이익을 비교해주세요"
- "네이버 최근 3년간 매출 성장 트렌드를 분석해주세요"
- "삼성전자 2024년 연결 기준 매출액과 영업이익은?"

## 기술 스택

| 분류 | 기술 |
|---|---|
| LLM | Google Gemini 2.5-flash (구조화 출력, LLM-as-judge) |
| Orchestration | LangGraph (5-노드 선형 파이프라인) |
| Search / RAG | ChromaDB (Dense) + BM25 (Sparse) + RRF Hybrid Search |
| Parsing | lxml (DART 독자 XML), 2-level 구조 기반 청킹 |
| Data Ingestion | DART OpenAPI (공시 목록 조회 + 문서 ZIP 다운로드) |
| MLOps | MLflow (지표 추적, 실험 비교) |
| API | FastAPI + uvicorn |
| UI | Streamlit |
| 환경 | Python, uv |

## 아키텍처

```
사용자 질문
    ↓
[QueryClassifier]  qa / comparison / trend / risk 분류 (Gemini structured output)
    ↓
[EntityExtractor]  기업명, 연도, 섹션 필터 추출
    ↓
[Retriever]        Hybrid Search (Dense + BM25 + RRF) + 메타데이터 후처리 필터
    ↓
[Analyst]          쿼리 유형별 전용 프롬프트로 답변 생성
    ↓
[CitationFormatter] 중복 제거 출처 목록
    ↓
최종 답변
```

## 프로젝트 구조

```
research-agent/
├── src/
│   ├── ingestion/
│   │   └── dart_fetcher.py       DART API 연동 및 공시 문서 수집
│   ├── processing/
│   │   └── financial_parser.py   DART XML 파싱 + 2-level 구조 기반 청킹
│   ├── storage/
│   │   └── vector_store.py       ChromaDB + BM25 + RRF Hybrid Search
│   ├── agent/
│   │   └── financial_graph.py    LangGraph Financial Analysis Agent
│   ├── api/
│   │   └── financial_router.py   FastAPI 라우터
│   └── ops/
│       └── evaluator.py          RAG 평가 파이프라인 (MLflow 연동)
├── data/
│   ├── reports/                  다운로드된 DART 공시 문서
│   ├── chroma_dart/              ChromaDB 영속 저장소
│   └── eval/                     평가 데이터셋 (20개 질문)
├── app.py                        Streamlit UI
├── main.py                       FastAPI 진입점
├── DECISIONS.md                  기술 결정 및 문제 해결 로그
└── PLAN.md                       전체 구현 계획
```

## 구현 현황

- [x] Phase 1 — DART API 연동 및 공시 문서 수집
- [x] Phase 2 — DART XML 파서 + 2-level 구조 기반 청킹
- [x] Phase 3 — Financial Analysis Agent (LangGraph 5-노드)
- [x] Phase 4 — RAG 평가 파이프라인 (Faithfulness / Relevancy / Recall + MLflow)
- [x] Phase 5 — FastAPI REST API + Streamlit UI

## 로컬 실행

### 1. 환경 설정

```bash
uv venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```

`.env` 파일에 API 키를 설정한다:

```
GOOGLE_API_KEY=...   # https://aistudio.google.com
DART_API_KEY=...     # https://opendart.fss.or.kr/intro/main.do
```

### 2. Streamlit UI 실행 (권장)

```bash
streamlit run app.py
```

- **Tab 1**: 기업명 + 연도 입력 → DART 수집 + 인덱싱
- **Tab 2**: 자연어 질문 입력 → Agent 분석 → 답변 + 출처
- **Tab 3**: 평가 지표 bar chart + MLflow 실험 이력

### 3. FastAPI REST API 실행

```bash
uvicorn main:app --reload --port 8000
```

Swagger UI: http://localhost:8000/docs

| 엔드포인트 | 설명 |
|---|---|
| `POST /api/ingest` | `{ "company": "삼성전자", "years": [2024] }` → 수집 + 인덱싱 |
| `POST /api/query` | `{ "question": "..." }` → 분석 답변 반환 |
| `GET  /api/companies` | 인덱싱된 기업 목록 조회 |
| `GET  /api/health` | 서버 상태 확인 |

### 4. 개별 모듈 스모크 테스트

```bash
cd src

# DART 수집
python -m ingestion.dart_fetcher

# 파서 + 청킹
python -m processing.financial_parser

# Agent 실행
python -m agent.financial_graph

# 평가 파이프라인
python -m ops.evaluator
```

### 5. MLflow 실험 UI

```bash
mlflow ui --backend-store-uri mlruns/
# → http://localhost:5000
```

## 청킹 전략

DART XML의 문서 구조를 그대로 활용하는 2-level 청킹을 사용한다.

| Level | 방식 | 적용 조건 |
|---|---|---|
| 1 | 구조 경계 (P 블록 누적 + 대형 TABLE 단독) | 기본 |
| 2 | RecursiveCharacterTextSplitter | 단일 블록이 chunk_size(1500자) 초과 시 폴백 |

- 소형 테이블(< 750자): 인접 단락과 함께 누적해 맥락 보존
- 대형 테이블(≥ 750자): 단독 청크, 헤더 행 반복 포함으로 계정명 컨텍스트 유지
- 결과: 573청크, 중앙값 1,345자 (chunk_size=1,500)

## 평가 지표

| 지표 | 측정 대상 | 구현 |
|---|---|---|
| Faithfulness | 답변이 컨텍스트에만 근거하는가 | LLM-as-judge (Gemini) |
| Answer Relevancy | 질문-답변 의미 유사도 | HuggingFace 임베딩 코사인 |
| Context Recall | 정답 키워드 검색 커버리지 | 한국어 토큰 overlap |

스모크 테스트 결과 (리스크 3문항): F=0.733 / R=0.562 / C=0.167

## 주요 기술 결정 및 문제 해결

상세 내용은 [DECISIONS.md](DECISIONS.md) 참고.  
주요 이슈 요약:

- **lxml 프록시 ID 재사용 버그**: `id()` 기반 skip set → 구조적 재귀로 교체
- **LIBRARY 태그 누락**: DART XML의 숨겨진 wrapper 태그로 섹션 콘텐츠 0개 → 근본 원인 분석 후 수정
- **청킹 중앙값 98자 → 1,345자**: ALL-TABLE-STANDALONE 방식에서 크기 임계값 기반 방식으로 전환
- **사업보고서 날짜 범위 오류**: N년 보고서는 N+1년 3월 접수 → `bgn_de={N+1}0101` 수정
- **네이버/NAVER 이름 불일치**: 별칭 딕셔너리 + 4단계 폴백 매칭