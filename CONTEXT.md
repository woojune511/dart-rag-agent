# 프로젝트 컨텍스트 / 다음 세션 인수인계

> 다음 세션에서 바로 이어서 작업할 수 있도록 현재 구조, 최근 변경, 검증 상태를 정리합니다.

---

## 목적

이 프로젝트는 DART 공개 공시 문서를 기반으로 한국어 기업 공시 질의응답을 수행하는 RAG 분석 에이전트입니다.

현재 목표는 다음 네 축을 안정화하는 것입니다.

- DART 수집과 파싱
- retrieval 정확도
- reasoning 품질
- 실행 시간과 운영 편의성

---

## 현재 상태 요약

기본 제품 흐름은 이미 동작합니다.

- DART 문서 수집 가능
- DART XML 파싱 및 구조 기반 청킹 가능
- ChromaDB + BM25 하이브리드 검색 가능
- LangGraph 기반 질의 분석 가능
- FastAPI / Streamlit 경로 존재
- MLflow 기반 평가 파이프라인 존재

최근에는 retrieval 정확도 개선 이후, parent-child + contextual retrieval와 ingest 속도 개선이 추가로 들어갔습니다.

핵심 상태:

- 검색은 자식 청크 기준
- 답변 컨텍스트는 부모 섹션 텍스트 우선
- 인덱싱은 contextual ingest 기준
- contextual ingest는 병렬 LLM batch 호출 사용
- 파서 기본 청크 설정은 `2500 / 320`

---

## 현재 아키텍처

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

인덱싱 파이프라인:

```text
fetch_report()
  -> process_document()
  -> build_parents()
  -> contextual_ingest()
      -> LLM batch로 청크별 1문장 컨텍스트 생성
      -> 메타데이터 prefix + 자식 청크 원문으로 인덱싱
      -> parents.json 저장
```

---

## 주요 파일

| 파일 | 역할 |
|---|---|
| `src/ingestion/dart_fetcher.py` | DART API 조회, corp code 해석, 문서 다운로드 |
| `src/processing/financial_parser.py` | DART XML 파싱, 구조 기반 청킹, `build_parents()` |
| `src/storage/vector_store.py` | 다국어 임베딩 + ChromaDB + BM25 + RRF + 부모 청크 저장 |
| `src/agent/financial_graph.py` | LangGraph 에이전트, evidence-first reasoning, `contextual_ingest()` |
| `src/ops/evaluator.py` | 평가 실행, retrieval 지표 포함 MLflow 로깅 |
| `src/api/financial_router.py` | FastAPI 엔드포인트 |
| `app.py` | Streamlit UI |
| `main.py` | FastAPI 진입점 |

---

## 최근 구현 사항

### 1. 정확도 스프린트 반영

- 임베딩 모델을 `paraphrase-multilingual-MiniLM-L12-v2`로 변경
- 컬렉션을 `dart_reports_v2`로 분리
- `chunk_uid` 기준 hybrid dedup 적용
- company / year strict filter 보강
- evidence-first answer synthesis 도입
- retrieval-aware evaluation 지표 추가

### 2. parent-child + contextual retrieval

- 모든 자식 청크에 `parent_id` 부여
- 같은 섹션 자식 청크를 합쳐 부모 청크 생성
- `data/chroma_dart/parents.json`에 부모 텍스트 저장
- 인덱싱 시 각 자식 청크 앞에 LLM이 생성한 1문장 컨텍스트를 prepend
- 답변 생성 시 같은 `parent_id`는 중복 없이 부모 텍스트로 확장

### 3. contextual ingest 병렬화

이전:

- 청크마다 순차 `invoke()` 호출
- 문서 하나를 통으로 인덱싱할 때 체감 속도가 매우 느림

현재:

- `llm.batch(..., config={"max_concurrency": ...})` 사용
- 기본 병렬도는 환경변수 `CONTEXTUAL_INGEST_MAX_WORKERS` 또는 코드 기본값 사용
- app/API 둘 다 같은 병렬 설정 사용

### 4. 청크 크기 조정

최종 채택 설정:

- `chunk_size = 2500`
- `chunk_overlap = 320`

보완 사항:

- 인덱싱 텍스트 앞에 deterministic metadata prefix 추가
- 포함 내용:
  - 회사 / 연도 / 보고서
  - 섹션 breadcrumb
  - block type / section label

목적:

- 큰 청크로 갈수록 희석되는 retrieval 신호를 보강

---

## 현재 청킹 전략

DART XML 구조를 우선 보존하는 2단계 청킹입니다.

1. `SECTION-1/2/3`로 섹션 분리
2. 섹션 내에서 문단과 표 블록 수집
3. 작은 표는 문단과 함께 누적
4. 큰 표는 standalone 처리
5. 너무 긴 블록만 재분할
6. 같은 섹션 자식 청크를 부모 청크로 묶음

기본값:

- `chunk_size = 2500`
- `chunk_overlap = 320`
- standalone table threshold = `1250`
- `build_parents(max_parent_len=6000)`

주요 메타데이터:

- `chunk_uid`
- `block_type`
- `section`
- `section_path`
- `table_context`
- `parent_id`
- `company`, `year`, `report_type`, `rcept_no`

메모:

- `table_context`는 실제 요약이 아니라 preview 성격이 강함
- 답변은 preview만 사용하지 않고 부모 원문 또는 `컨텍스트 + 자식 원문`을 사용

---

## 검증 상태

### 정적 / 로컬 검증

완료:

- 주요 Python 파일 `py_compile` 통과
- synthetic DART XML 기준 parser 스모크 테스트 통과
- `chunk_uid`, `block_type`, `section_path`, `table_context`, `parent_id` 생성 확인
- `contextual_ingest()`의 batch 경로 사용 확인
- `VectorStoreManager`의 parents 저장/조회 확인

### 실제 외부 연동 검증

실제 환경 변수:

- `GOOGLE_API_KEY`
- `DART_API_KEY`

실제 테스트 대상:

- 삼성전자 2024 사업보고서
- 접수번호 `20250311001085`

확인한 흐름:

- DART fetch 성공
- parser 실행 성공
- `contextual_ingest()` 성공
- 실제 질문 2개 smoke 성공

검증한 질의:

- "회사가 영위하는 주요 사업은 무엇인가요?"
- "주요 리스크는 무엇인가요?"

리스크 질의는 최종 `2500 / 320` 설정에서 다시 정상적으로 회복됨.

---

## 벤치마크 요약

기준 문서:

- 삼성전자 2024 사업보고서

비교 결과:

| 설정 | 파싱 시간 | 청크 수 | contextual ingest 시간 | 결과 |
|---|---:|---:|---:|---|
| `1500 / 200` | `1.603초` | `502` | `1013.569초` | 기존 |
| `2800 / 350` | `0.548초` | `266` | `292.289초` | 속도 우수, 리스크 retrieval 품질 회귀 |
| `2500 / 320` | `0.608초` | `300` | `584.25초` | 최종 채택 |

해석:

- 병목은 parser가 아니라 contextual ingest 단계
- 청크 수 감소만으로도 문서 전체 인덱싱 시간이 크게 줄어듦
- 다만 너무 큰 청크는 리스크 질의 품질을 무너뜨릴 수 있어 `2800 / 350`은 폐기

---

## 현재 남은 이슈

### 우선순위 높음

- 실제 데이터셋 기준으로 `contextual_ingest()` 재인덱싱 범위를 더 넓혀 검증할 것
- 삼성전자 외 다른 기업에서도 `2500 / 320` 설정이 유지되는지 확인할 것
- multi-company / comparison 질의에서 larger chunk가 retrieval contamination을 다시 유발하지 않는지 확인할 것

### 우선순위 중간

- `table_context`를 preview로 명확히 다룰지, 이름을 바꿀지 검토
- contextual ingest 결과를 `chunk_uid` 기준으로 캐시할지 검토
- parent chunk 길이 `6000` 유지가 최적인지 추가 점검

### 운영 메모

- Python 3.14 환경에서 `langchain_core`의 Pydantic v1 경고가 계속 남아 있음
- `langchain_community.vectorstores.Chroma` deprecation 경고가 있음
- Hugging Face 모델 캐시 `.hf_cache/`가 로컬에 생성됨

---

## 다음 세션 추천 작업

1. 삼성전자 외 1~2개 기업으로 동일한 smoke benchmark 실행
2. FastAPI / Streamlit 경로에서 실제 인덱싱-질의 UX 점검
3. contextual ingest 캐시 여부 검토
4. evaluation dataset에 larger chunk 회귀 케이스 추가

---

## 참고 문서

- `README.md`: 사용법과 현재 구조
- `DECISIONS.md`: 기술 결정과 해결 로그
- `PLAN.md`: 다음 확장 로드맵
- `REVIEW_FINDINGS.md`: 최근 코드 리뷰 findings
