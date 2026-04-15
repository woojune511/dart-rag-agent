# Review Findings

> 특정 시점의 코드 리뷰 결과를 보관하는 문서다. 현재 상태를 설명하는 문서가 아니라, 어떤 문제를 발견했고 이후 어떤 변경으로 이어졌는지 추적하기 위한 아카이브다.

---

## Snapshot

- Review type: static code review
- Scope:
  - `app.py`
  - `main.py`
  - `src/api/financial_router.py`
  - `src/agent/financial_graph.py`
  - `src/storage/vector_store.py`
  - `src/processing/financial_parser.py`
- Method: code inspection + `py_compile`
- Excluded:
  - DART end-to-end ingestion
  - Gemini real-query execution
  - Chroma persistence validation
  - MLflow runtime validation

---

## Findings

### 1. Metadata post-filter가 1개 결과를 남겨도 무시되던 문제

- Severity: High
- Status: Resolved
- Original impact:
  - single-company, single-year 질의에서 broader candidate가 다시 섞이면서 다른 기업 문서 contamination이 발생할 수 있었다.
- Resolution:
  - strict metadata filtering을 non-empty 기준으로 유지하도록 수정했다.

### 2. Streamlit 연도 선택 범위가 현재 달력을 따라가지 못하던 문제

- Severity: Medium
- Status: Resolved
- Original impact:
  - backend는 지원하지만 UI에서는 최신 연도를 선택할 수 없었다.
- Resolution:
  - 연도 선택 범위를 현재 기준으로 확장했다.

### 3. Hybrid fusion이 raw `page_content` 기준으로 dedup되던 문제

- Severity: Medium
- Status: Resolved
- Original impact:
  - 반복 boilerplate와 유사 표 헤더 때문에 서로 다른 chunk가 하나로 합쳐질 수 있었다.
- Resolution:
  - fusion key를 `chunk_uid` 기준으로 변경했다.

### 4. UI의 chunk type 표시가 parser metadata와 완전히 맞지 않던 문제

- Severity: Low
- Status: Partially resolved
- Original impact:
  - retrieval debug panel에서 chunk 유형 표시가 불명확했다.
- Current note:
  - parser는 현재 `block_type` metadata를 제공한다.
  - UI가 이 값을 일관되게 노출하는지는 추가 점검 여지가 남아 있다.

---

## What Changed Because Of This Review

이 리뷰 이후 실제로 이어진 주요 변경은 아래와 같다.

- strict metadata filtering 보강
- `chunk_uid` 기반 fusion
- richer chunk metadata 도입
- retrieval debug 정보 확장
- 이후 benchmark runner와 retrieval-aware evaluation 체계 구축

즉, 단순 bug list를 남기는 데서 끝난 리뷰가 아니라 retrieval contamination을 구조적으로 줄이는 변경의 출발점 역할을 했다.

---

## How To Use This Document

- 현재 코드 상태를 이해하려면 `README.md`, `CONTEXT.md`, `DECISIONS.md`를 먼저 본다.
- 이 문서는 과거 리뷰 관찰과 그 후속 조치를 추적하는 참고 자료로 사용한다.
