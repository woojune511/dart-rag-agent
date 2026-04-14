# Review Findings

> 특정 시점의 코드 리뷰 결과를 보관하는 문서입니다. 현재 상태와 1:1로 일치하지 않을 수 있으므로, 해결 여부를 함께 표시합니다.

---

## Snapshot

- Review type: static code review
- Scope: `app.py`, `main.py`, `src/api/financial_router.py`, `src/agent/financial_graph.py`, `src/storage/vector_store.py`, `src/processing/financial_parser.py`
- Method: code inspection + `py_compile`
- Excluded: DART / Gemini / ChromaDB / MLflow end-to-end execution

---

## Findings

### 1. Metadata post-filters were skipped when only one chunk survived

- Severity: High
- Status: Resolved
- Original impact:
  - single-company, single-year 질문에서도 broader candidate가 다시 섞일 수 있었음
- Resolution:
  - strict metadata filter가 non-empty면 유지되도록 수정

### 2. Streamlit year selection lagged behind the current calendar

- Severity: Medium
- Status: Resolved
- Original impact:
  - UI에서 최신 연도를 선택할 수 없어 backend capability가 가려졌음
- Resolution:
  - 연도 선택 범위를 최신 연도 기준으로 확장

### 3. Hybrid fusion used raw `page_content` as the merge key

- Severity: Medium
- Status: Resolved
- Original impact:
  - 반복 boilerplate나 표 헤더가 다른 청크를 같은 결과로 합칠 수 있었음
- Resolution:
  - merge key를 `chunk_uid` 기준으로 변경

### 4. Retrieved chunk type field in Streamlit was not backed by parser metadata

- Severity: Low
- Status: Partially resolved
- Original impact:
  - retrieval debug panel에서 chunk type 가시성이 낮았음
- Current note:
  - parser에는 `block_type` 메타데이터가 존재
  - UI가 현재 필드명을 일관되게 쓰는지는 다시 확인 가치가 있음

---

## Lessons

이 리뷰에서 가장 중요했던 포인트는 단순 버그 나열보다, retrieval contamination의 구조적 원인을 찾았다는 점입니다.

특히 아래 세 가지가 이후 설계 변경으로 이어졌습니다.

- strict metadata filtering 보강
- `chunk_uid` 기반 fusion
- richer metadata와 retrieval debug 강화

---

## How To Use This Document

- 현재 코드 상태를 설명하는 문서로 쓰지 않음
- 과거 리뷰에서 어떤 문제가 있었고, 그것이 어떤 설계 변경으로 이어졌는지 추적하는 아카이브로 사용
- 현재 상태는 `README.md`, `CONTEXT.md`, `DECISIONS.md`를 우선 참고
