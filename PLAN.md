# 실행 계획

> 이 문서는 **현재 active plan만 유지하는 실행 문서**다.  
> 과거 실험과 장기 방향은 [DECISIONS.md](C:/Users/geonj/Desktop/research%20agent/DECISIONS.md)와 [docs/planning/backlog_and_next_epics.md](C:/Users/geonj/Desktop/research%20agent/docs/planning/backlog_and_next_epics.md)로 보낸다.

## Active Snapshot

| 항목 | 현재 상태 |
| --- | --- |
| 현재 1순위 | **planner는 재료를 모으고, synthesizer가 질문 충족 여부를 판단하는 구조를 runtime에 정착** |
| 지금 하지 않을 것 | 범용 agent 확장, broad web workflow, cosmetic retrieval tuning |
| 다음 큰 순서 | `planner/synthesizer contract -> result schema settling -> concept-only planner canary -> DART multi-document reasoning` |

## Immediate Focus

- curated dataset 연결과 parser baseline regression은 1차 기준선까지는 지나갔다.
- 지금 가장 가까운 구현 초점은 **planner/synthesizer contract + concept-only planning + result schema settling** 이다.
  - ontology는 metric recipe보다 concept / group concept / binding prior 중심으로 축소
  - planner는 질문을 `operation_family + required_operands` 형태의 재료 수집 task로 분해
  - final synthesizer는 원본 질문과 `subtask_results`를 보고 최종 답 또는 `planner_feedback`를 결정
  - planner는 `planner_feedback`를 받아 기존 `pre_calc_planner`에서 patch append 방식으로 replan
  - runtime state에 `tasks`, `artifacts`, `table_object_json`을 남겨 source of truth를 만들기 시작
  - ambiguous top candidate는 deterministic scoring 후에만 LLM rerank로 보정

## Active Workstreams

### 0. Planner and synthesizer contract

| 항목 | 내용 |
| --- | --- |
| 목표 | planner는 재료 수집만 하고, final synthesizer가 질문 충족 여부와 최종 refusal을 책임지는 구조 정착 |
| 현재 자산 | concept-only ontology v3 draft, LLM concept planner, lightweight validator, `planner_feedback`, `plan_loop_count`, aggregate synthesizer |
| 현재 문제 | `lookup`, `difference`, `ratio`가 answer contract를 충분히 구조화해 남기지 않아 synthesizer가 일부 질문에서 약함 |
| 다음 할 일 | `NAV_T1_071`류를 기준으로 `planner_feedback -> replan -> close/refusal` 루프를 end-to-end 검증 |
| 종료 조건 | planner와 synthesizer의 책임 경계가 안정되고, 부족 재료는 planner replan으로 보강하거나 aggregate refusal로 닫힘 |

### 1. Result schema settling

| 항목 | 내용 |
| --- | --- |
| 목표 | lookup/difference/ratio 결과를 answer-friendly structured result로 남겨 synthesizer가 안정적으로 조합 |
| 현재 상태 | `calculation_result.series`, `derived_metrics`는 있으나 `current_value`, `prior_value`, `delta_value` 같은 operation-specific slots는 약함 |
| 다음 할 일 | operation별 structured result schema 초안 추가 및 renderer / synthesizer가 그 필드를 우선 사용하게 정리 |
| 종료 조건 | single-task와 multi-subtask 모두 원본 질문 충족 여부를 structured result만 보고 판정 가능 |

### 2. Concept-only planner validation

| 항목 | 내용 |
| --- | --- |
| 목표 | concept-only ontology + LLM planner가 implicit / shorthand / multi-metric query를 runtime default로 감당할 수 있는지 검증 |
| 현재 관측 | concept planner canary에서 `SKH_T1_060`, `MIX_T1_021`, implicit `부채비율` / `유동비율` / `FCF`는 잘 분해된다. `NAV_T1_071`는 planner 차원에서 `lookup + difference`로 개선됐지만 e2e close는 더 확인 필요 |
| 다음 할 일 | concept planner canary와 ontology shadow compare를 계속 돌리며 default 승격 기준 정리 |
| 종료 조건 | planner가 benchmark-shaped `metric_family` 없이도 주요 numeric family를 안정적으로 재료 수집 task로 분해 |

### 3. DART multi-document reasoning

| 항목 | 내용 |
| --- | --- |
| 목표 | 같은 회사의 사업/반기/분기/정정공시를 함께 읽는 DART 범위 reasoning으로 확장 |
| 선행 조건 | single-doc planner/synthesizer contract와 structured result schema가 안정화 |
| 다음 할 일 | `multi_report_eval_full.curated.json`를 기준으로 report linker / period comparator / disclosure diff 방향 정리 |
| 종료 조건 | multi-report 질문에서 report binding과 period binding이 안정적으로 유지됨 |

## Success Criteria

- planner가 답변 문장을 직접 결정하지 않고 필요한 재료를 안정적으로 수집한다.
- final synthesizer가 원본 질문 충족 여부를 보고 close / replan / refusal을 일관되게 결정한다.
- runtime source of truth가 `tasks + artifacts + table objects + structured results`로 이동한다.
