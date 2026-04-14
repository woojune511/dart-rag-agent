# 프로젝트 컨텍스트

> 다음 세션에서 바로 이어 작업할 수 있도록 현재 상태와 남은 과제를 정리한 문서입니다.

---

## 1. 현재 제품 상태

핵심 경로는 이미 동작합니다.

- DART OpenAPI로 공시 문서 수집 가능
- DART XML 파싱과 구조 기반 청킹 가능
- ChromaDB + BM25 + RRF 하이브리드 검색 가능
- LangGraph 기반 질의 분석과 답변 생성 가능
- FastAPI / Streamlit 경로 존재
- MLflow 기반 평가 파이프라인 존재

현재 기본 동작 흐름은 아래와 같습니다.

```text
질문
  -> classify
  -> extract
  -> retrieve
  -> evidence
  -> analyze
  -> cite
  -> 답변
```

---

## 2. 현재 기본 설계

### Retrieval

- 임베딩 모델: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- 컬렉션: `dart_reports_v2`
- 검색 방식: Dense + BM25 + RRF
- BM25 토크나이저: 한국어 character bigram
- metadata filtering: company / year는 non-empty면 유지
- dedup 기준: raw text가 아닌 `chunk_uid`

### Chunking

- 기본값: `chunk_size=2500`, `chunk_overlap=320`
- 구조 기반 1차 청킹 후, 긴 블록만 문자 단위 재분할
- 대형 표 threshold: `chunk_size // 2`
- 주요 메타데이터:
  - `chunk_uid`
  - `block_type`
  - `section`
  - `section_path`
  - `table_context`
  - `parent_id`

### Reasoning

- evidence-first 구조 사용
- 검색은 자식 청크 기준
- 답변 컨텍스트는 부모 섹션 텍스트 우선
- 인덱싱 시 `LLM context + metadata prefix + child chunk` 형태 사용

---

## 3. 최근 반영 사항

### Parent-child + contextual retrieval

- 자식 청크마다 `parent_id`를 부여
- 같은 섹션의 자식 청크를 합쳐 부모 청크 생성
- `data/chroma_dart/parents.json`에 부모 텍스트 저장
- 답변 단계에서는 부모 텍스트를 우선 사용

### Contextual ingest 병렬화

- 순차 `invoke()` 반복 대신 `llm.batch(..., max_concurrency=...)` 사용
- 병렬도는 `CONTEXTUAL_INGEST_MAX_WORKERS` 환경변수 또는 코드 기본값 사용
- app/API 모두 같은 기본 동작 사용

### Chunk tuning

- 후보 실험:
  - `1500 / 200`
  - `2800 / 350`
  - `2500 / 320`
- 현재 채택값:
  - `2500 / 320`

### 벤치마크 자동화 뼈대

- `src/ops/benchmark_runner.py` 추가
- `benchmarks/experiment_matrix.sample.json` 추가
- `benchmarks/eval_dataset.template.json` 추가
- 결과 산출물:
  - `results.json`
  - `summary.csv`
  - `summary.md`

---

## 4. 검증 메모

### 코드/로컬 검증

- 주요 Python 파일 `py_compile` 통과
- `python -m src.ops.benchmark_runner --help` 동작 확인
- synthetic XML 기준 parser 스모크 테스트 통과
- `chunk_uid`, `block_type`, `section_path`, `table_context`, `parent_id` 생성 확인

### 실제 외부 연동 검증

확인한 경로:

- DART fetch
- parser 실행
- contextual ingest
- 실제 질문 2개 smoke

테스트 대상:

- 삼성전자 2024 사업보고서
- 접수번호 `20250311001085`

검증 질문:

- 회사가 영위하는 주요 사업은 무엇인가요?
- 주요 리스크는 무엇인가요?

---

## 5. 벤치마크 요약

기준 문서:

- 삼성전자 2024 사업보고서

대표 비교:

| 설정 | 파싱 시간 | 청크 수 | contextual ingest 시간 | 해석 |
|---|---:|---:|---:|---|
| `1500 / 200` | `1.603초` | `502` | `1013.569초` | 기준선 |
| `2800 / 350` | `0.548초` | `266` | `292.289초` | 가장 빠르지만 리스크 질의 품질 회귀 |
| `2500 / 320` | `0.608초` | `300` | `584.25초` | 최종 채택 |

핵심 해석:

- 병목은 parser보다 contextual ingest 단계
- 단순 병렬화만으로는 부족하고, 청크 수 자체를 줄이는 tuning이 필요함
- `2800 / 350`은 속도는 좋지만 retrieval 품질이 흔들렸고
- `2500 / 320`이 속도와 품질의 균형이 가장 좋았음

---

## 6. 문서 역할

- `README.md`: 외부 공개용 개요와 사용법
- `DECISIONS.md`: 중요한 기술 판단과 선택 근거
- `CONTEXT.md`: 현재 상태와 handoff 메모
- `PLAN.md`: 다음 실험과 로드맵
- `REVIEW_FINDINGS.md`: 코드 리뷰 아카이브
- `docs/benchmarking.md`: 실험 실행과 해석 가이드

---

## 7. 남은 우선순위

### 높음

1. 실제 공시 기준 curated eval set 보강
2. 다른 기업에서도 `2500 / 320` 설정 검증
3. contextual ingest 비용/속도/정확도 비교 실험 본격화
4. comparison 질의에서 retrieval contamination 재검증

### 중간

1. `chunk_uid` 기준 contextual cache 검토
2. `table_context` 이름을 preview 의미로 바꿀지 검토
3. parent chunk 길이 `6000` 최적값 점검

### 운영 메모

- Python 3.14에서 `langchain_core` Pydantic v1 경고 존재
- `langchain_community.vectorstores.Chroma` deprecation 경고 존재
- Hugging Face 캐시 `.hf_cache/`는 `.gitignore`에 추가 완료
