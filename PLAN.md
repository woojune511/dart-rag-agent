# 실행 계획

> 이 문서는 **현재 active plan만 유지하는 실행 문서**다.  
> 과거 실험과 장기 방향은 [DECISIONS.md](C:/Users/geonj/Desktop/research%20agent/DECISIONS.md)와 [docs/planning/backlog_and_next_epics.md](C:/Users/geonj/Desktop/research%20agent/docs/planning/backlog_and_next_epics.md)로 보낸다.

## Active Snapshot

| 항목 | 현재 상태 |
| --- | --- |
| 현재 1순위 | **DART 범위 안에서 `tasks/artifacts/table object` schema를 runtime에 정착시키고 structured table grounding을 안정화** |
| 지금 하지 않을 것 | 범용 agent 확장, broad web workflow, cosmetic retrieval tuning |
| 다음 큰 순서 | `schema settling -> structured table grounding coverage -> numeric end-to-end validation -> DART multi-document reasoning` |

## Immediate Focus

- curated dataset 연결과 parser baseline regression은 1차 기준선까지는 지나갔다.
- 지금 가장 가까운 구현 초점은 **schema settling + semantic numeric planner + table-aware grounding + reconciliation hardening** 이다.
  - ontology 기반으로 필요한 operand와 scope를 먼저 계획
  - retrieval 이후 reconciliation으로 부족 operand를 잡음
  - parser가 만든 structured table row를 direct operand 경로로 소비
  - 최근에는 `table_value_records_json -> structured_value` 경로를 추가해 wide note table도 value-cell-first로 읽기 시작
  - runtime state에 `tasks`, `artifacts`, `table_object_json`을 남겨 다음 단계의 source of truth를 만들기 시작
  - ambiguous top candidate는 deterministic scoring 후에만 LLM rerank로 보정

## Active Workstreams

### 0. Runtime schema settling

| 항목 | 내용 |
| --- | --- |
| 목표 | `tasks`, `artifacts`, `table_object_json`를 DART numeric path의 정식 runtime schema로 정착 |
| 현재 자산 | `src/schema/dart_schema.py`, semantic planner artifact, reconciliation artifact, operand/calculation artifact, parser `table_object_json` |
| 현재 문제 | evaluator projection은 들어갔지만 runtime operand path는 아직 partial direct rows를 버리는 구간이 남아 있음 |
| 다음 할 일 | artifact ledger projection 유지, 그리고 operand extraction에서 partial direct rows를 fallback rows와 merge |
| 종료 조건 | multi-step numeric 질문에서도 마지막 subtask만 남지 않고 structured trace가 artifact 기준으로 보존됨 |

### 1. Structured table grounding coverage

| 항목 | 내용 |
| --- | --- |
| 목표 | parser의 `table_object / row / cell`을 reconciliation과 operand extraction 전반에서 더 직접 소비 |
| 현재 상태 | `table_value_records_json` / `structured_value`가 들어갔고, `TBODY/TE` 및 unit-only standalone table hint까지 parser가 보존한다. `SKH_T1_060`은 자산 + current 단기/장기차입금까지 회복 |
| 다음 할 일 | current-period `사채 final_total`이 detail bond row보다 우선되도록 aggregate binding 보강 |
| 종료 조건 | 주요 numeric family에서 chunk text fallback 비중이 줄고 structured value/cell path가 우선 경로가 됨 |

### 2. Numeric end-to-end validation

| 항목 | 내용 |
| --- | --- |
| 목표 | structured trace와 최종 답변이 함께 맞는지 numeric family별로 다시 고정 |
| 현재 관측 | multi-metric numeric smoke subset에서 retrieval hit은 유지되고, `SKH_T1_060`은 refusal을 벗어나 `25.2%`까지 계산하지만 사채 aggregate 오선택으로 아직 오답 |
| 다음 할 일 | `single_doc_eval_multi_metric_numeric.curated.json`와 `multi_metric_numeric_smoke.json` 기준으로 trace/evaluator 회귀 반복 |
| 종료 조건 | final answer와 structured trace가 모두 같은 subtask 집합을 보존 |

### 3. DART multi-document reasoning

| 항목 | 내용 |
| --- | --- |
| 목표 | 같은 회사의 사업/반기/분기/정정공시를 함께 읽는 DART 범위 reasoning으로 확장 |
| 선행 조건 | single-doc numeric path가 artifact/task/table object 기준으로 안정화 |
| 다음 할 일 | `multi_report_eval_full.curated.json`를 기준으로 report linker / period comparator / disclosure diff 방향 정리 |
| 종료 조건 | multi-report 질문에서 report binding과 period binding이 안정적으로 유지됨 |

## Success Criteria

- runtime source of truth가 `tasks + artifacts + table objects`로 이동한다.
- numeric 질문에서 final answer와 structured trace가 함께 맞는다.
- DART 범위 안에서 single-doc 다음 단계인 multi-document reasoning으로 자연스럽게 넘어갈 수 있다.
