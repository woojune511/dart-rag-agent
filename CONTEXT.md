# 프로젝트 컨텍스트 — 다음 세션 인수인계

> 새 세션에서 바로 이어 작업할 때 먼저 이 파일을 읽으면 됩니다.

---

## 목적

이 프로젝트는 **DART 공개 공시 문서를 기반으로 한국어 재무 질문에 답하는 RAG 분석 시스템**입니다.  
포트폴리오 관점에서는 다음 역량을 보여주는 것이 핵심입니다.

- DART 데이터 수집 및 전처리
- 구조 기반 청킹과 하이브리드 검색
- LangGraph 기반 분석 에이전트
- 평가 파이프라인 + MLflow
- FastAPI/Streamlit 형태의 서비스화

---

## 현재 상태 요약

핵심 기능은 한 번 다 연결된 상태입니다.

- DART 수집 가능
- DART XML 파싱 및 구조 기반 청킹 가능
- ChromaDB + BM25 하이브리드 검색 가능
- LangGraph 기반 질의 분석 가능
- FastAPI / Streamlit UI 동작 경로 존재
- MLflow 기반 평가 파이프라인 존재

최근에는 **Parent-Child + Contextual Retrieval 청킹 고도화**를 구현했습니다.

- 인덱싱 방식: `agent.ingest()` → `agent.contextual_ingest()`
- 자식 청크(~1500자)로 검색, 부모 청크(섹션 전체, 최대 6000자)를 LLM 컨텍스트로 전달
- 인덱싱 시 LLM이 청크당 1문장 컨텍스트 생성 후 prepend (Contextual Retrieval)
- LLM 컨텍스트 생성 병렬 처리: ThreadPoolExecutor(max_workers=3)
- 부모 청크 영속 저장: `data/chroma_dart/parents.json`

---

## 현재 아키텍처

```text
질문
  → classify
  → extract
  → retrieve
  → evidence
  → analyze
  → cite
  → 답변
```

인덱싱 파이프라인:

```text
parse_document()
  → build_parents()          # 섹션 단위 부모 청크 생성
  → _generate_context() x N  # LLM으로 청크당 1문장 컨텍스트 (병렬)
  → add_documents()          # "컨텍스트\n\n청크원문" 형태로 ChromaDB+BM25 인덱싱
  → add_parents()            # parents.json에 부모 청크 저장
```

### 핵심 파일

| 파일 | 역할 |
|---|---|
| `src/ingestion/dart_fetcher.py` | DART API 조회, corp code 해석, 문서 다운로드 |
| `src/processing/financial_parser.py` | DART XML 파싱, 섹션 추출, 구조 기반 청킹, `build_parents()` |
| `src/storage/vector_store.py` | 다국어 임베딩 + ChromaDB + BM25 + RRF + 부모 청크 JSON 저장 |
| `src/agent/financial_graph.py` | LangGraph 재무 분석 에이전트, `contextual_ingest()`, `_generate_context()` |
| `src/ops/evaluator.py` | 평가 실행, MLflow 로깅, 단일 기업 평가 슬라이스 |
| `src/api/financial_router.py` | FastAPI 엔드포인트 |
| `app.py` | Streamlit UI (contextual_ingest + 진행 상황 표시) |
| `main.py` | FastAPI 진입점 |

---

## 구현된 개선 내용 (전체 누적)

### 1. Retrieval / Indexing

- 기본 임베딩 모델을 한국어 친화적인 다국어 모델로 교체 (`paraphrase-multilingual-MiniLM-L12-v2`)
- 컬렉션 이름을 `dart_reports_v2`로 올려 재인덱싱 기준 분리
- hybrid search 병합 키를 `page_content`가 아니라 `chunk_uid`로 변경
- 회사/연도/섹션 필터가 non-empty면 그대로 유지
- exact company / year / section / topic overlap 기반 rerank 추가
- **[NEW] Contextual Retrieval**: 인덱싱 시 LLM 1문장 컨텍스트 prepend
- **[NEW] Parent-child chunking**: 검색은 자식(~1500자), LLM 컨텍스트는 부모(~6000자)

### 2. Chunking / Metadata

청크 메타데이터에 아래 필드를 추가했습니다.

- `chunk_uid`
- `block_type`
- `section_path`
- `table_context`
- **[NEW] `parent_id`** (`{rcept_no}::{section_path}` 형태)

### 3. Reasoning

```text
retrieve → evidence → analyze
```

- 상위 청크에서 먼저 evidence bullet을 뽑고, 최종 답변은 그 evidence만으로 작성
- 검색 시 부모 청크(섹션 전체)를 LLM에 전달 → 맥락 손실 감소

### 4. Evaluation

지표:

- faithfulness
- answer_relevancy
- context_recall
- retrieval_hit_at_k
- section_match_rate
- citation_coverage

---

## 현재 문서/환경 상태

- `.venv` 생성 완료
- `requirements.txt` 설치 완료
- 최신 코드 변경 push 완료

환경 변수:

```text
GOOGLE_API_KEY=...
DART_API_KEY=...
```

---

## 검증 상태

완료:

- 주요 Python 파일 `py_compile` 통과
- synthetic DART XML로 parser 스모크 테스트 통과
- `chunk_uid`, `block_type`, `section_path`, `table_context`, `parent_id` 생성 확인
- 삼성전자 2023 `dart_reports_v2` 재인덱싱 완료 (409청크, rule-based 방식 기준)
- "반도체 사업의 주요 리스크" end-to-end 질의 검증 완료 — 8청크 반환, 정상 답변 생성
- 파서 오분류(감사제도→리스크) 수정 및 반영 확인
- `contextual_ingest()` 구현 완료 (app.py 연결 포함)

잔여 작업:

- 삼성전자 2023 기존 청크 삭제 후 `contextual_ingest`로 재인덱싱 및 검증 필요
- NAVER 2024 데이터는 미인덱싱 상태 (멀티기업 테스트 필요 시 재수집 필요)
- Python 3.14 환경에서 `langchain_core`의 Pydantic v1 관련 경고 잔존

---

## 지금 바로 이어서 할 만한 일

### 우선순위 높음

- 삼성전자 2023 재인덱싱 (`contextual_ingest`) 후 "반도체 리스크" 질의 결과 비교 검증
- 추가 기업 인덱싱 후 멀티기업 비교 질의 검증

### 다음 확장 후보

- 멀티 기업 비교 질의 품질 개선
- 표 중심 수치 질의 전용 reasoning 강화
- 재무제표 / 리스크 / 사업개요별 섹션별 프롬프트 세분화
- 평가 데이터셋 정교화 및 회귀 테스트 자동화

---

## 참고 문서

- `README.md`: 사용법과 전체 구조
- `DECISIONS.md`: 의사결정 및 버그 해결 로그
- `PLAN.md`: 앞으로의 확장 로드맵
- `REVIEW_FINDINGS.md`: 최근 코드 리뷰 findings
