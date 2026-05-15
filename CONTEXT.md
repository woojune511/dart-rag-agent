# 프로젝트 컨텍스트

> 이 문서는 **현재 상태만 빠르게 파악하기 위한 snapshot 문서**다.  
> 과거 판단과 이유는 [DECISIONS.md](C:/Users/geonj/Desktop/research%20agent/DECISIONS.md), 장기 backlog는 [docs/planning/backlog_and_next_epics.md](C:/Users/geonj/Desktop/research%20agent/docs/planning/backlog_and_next_epics.md)를 본다.

## 현재 범위

- 이 프로젝트의 현재 범위는 **DART 공시 분석 내부**에 한정한다.
- 범용 agent, broad web workflow, productivity tool 확장은 당분간 하지 않는다.
- 목표는 DART single-document / multi-document 분석을 빠르게 안정화하고 닫는 것이다.

## 최신 상태

- curated benchmark 경로를 실제 profile과 evaluator에 연결했다.
- parser는 단순 chunk normalization을 넘어 **table-aware grounding** 단계로 들어갔다.
  - 병합된 `ROWSPAN/COLSPAN`을 canonical grid로 복원
  - `table_summary_text`, `table_row_labels_text`, `table_row_records_json`, `table_object_json` 생성
  - structured row-aware reconciliation 추가
- numeric question 경로에는 아래가 들어갔다.
  - ontology 기반 pre-retrieval semantic planning
  - post-retrieval reconciliation
  - multi-metric 질문용 subtask loop / aggregation
  - ready 상태 numeric subtask에 대한 direct `structured_row -> operand` 추출
  - `table_value_records_json -> structured_value` 기반 value-cell-first grounding
- planner / ontology 경로는 최근 아래 방향으로 이동했다.
  - benchmark-shaped `metric_family` 확장을 줄이고 concept-only ontology v3 draft를 추가
  - ontology는 `concept`, `concept_group`, statement/section prior, binding prior 중심으로 축소 시작
  - planner는 `metric_family`보다 `operation_family + required_operands` 중심의 IR로 점진 이동
  - implicit query도 LLM concept planner가 concept 조합으로 풀도록 canary path를 추가
  - planner validator는 형식 / 허용 concept / 허용 operation만 보는 얇은 contract checker로 유지
- answer path는 최근 아래 방향으로 이동했다.
  - planner는 “최종 문장을 최소화”하는 대신 **필요한 재료를 빠짐없이 모으는 방향**으로 조정
  - final synthesizer가 원본 질문과 `subtask_results`를 함께 읽고 최종 답을 조합
  - 재료가 부족하면 synthesizer가 `planner_feedback`를 남기고 기존 `pre_calc_planner`를 replan mode로 재사용
  - replan budget을 모두 써도 재료가 부족하면 `aggregate_subtasks`가 사용자-facing 최종 refusal / partial answer를 확정
- 내부 실행 구조 일반화를 위한 1차 schema를 추가했다.
  - `tasks`, `artifacts` state 추가
  - parser의 `table_object / row_record / cell_record`를 정식 출력으로 승격 시작
  - semantic plan / reconciliation / operand set / calculation plan / calculation result / aggregated answer를 artifact로 기록 시작
- evaluator는 이제 top-level `calculation_*`만 읽지 않고 runtime ledger를 다시 투영해 trace를 복원한다.
  - single-task 계산은 `tasks + artifacts`에서 operand/plan/result를 다시 읽는다
  - multi-subtask 계산은 `subtask_results`를 aggregate projection으로 다시 묶는다
- numeric reconciliation은 최근 아래 방향으로 보강됐다.
  - `structured_row` 중 `범위/하위범위/상위범위` 같은 descriptor row penalty
  - `chunk`보다 `structured_row / table_row / evidence_row` 우대
  - top candidate가 애매할 때만 LLM rerank helper 사용
  - `retrieved_docs`뿐 아니라 `seed_retrieved_docs`도 reconciliation candidate pool에 포함
  - `유형자산/무형자산/자산총계/부채총계/자본총계` 계열은 `summary_financials / balance_sheet` row를 우대
- parser/table grounding은 최근 아래 방향으로 더 확장됐다.
  - `table_value_records_json`과 `structured_value` candidate 추가
  - `TBODY/TE` 셀을 실제 value cell로 읽도록 확장
  - `(단위 : 백만원)` 같은 unit-only standalone table도 다음 실제 표의 context hint로 승격
  - wide merged-header note table에서 `direct_total / subtotal / final_total / adjustment` aggregate role 복원
- 최근 canary / e2e 관측은 다음과 같다.
  - ontology-v2 canary에서 `SKH_T1_060`은 `42.0%`, `MIX_T1_021`은 부채비율 `25.4%` / 유동비율 `258.8%`로 닫혔다
  - concept-planner shadow canary에서는 `SKH_T1_060`, `MIX_T1_021`, implicit `부채비율` / `유동비율` / `FCF`가 concept-only planner로도 자연스럽게 분해된다
  - `NAV_T1_071`는 planner 차원에서는 `lookup + difference` 재료 수집 구조로 정리됐지만, end-to-end answer contract와 result schema는 아직 더 다듬어야 한다

## 현재 핵심 한계

- legacy `calculation_*` 필드가 아직 evaluator와 runtime 일부 경로의 사실상 기준처럼 남아 있다.
- planner / synthesizer / result schema의 경계가 이제 막 생겼기 때문에, single-task와 multi-subtask가 항상 같은 answer contract를 공유하지는 못한다.
- concept-only planner는 single-metric / group concept / multi-metric 분해 품질이 좋아졌지만, 모든 numeric family에서 runtime default로 올리기엔 아직 canary가 더 필요하다.
- `NAV_T1_071`류 “현재값 + 전년 대비 증감” 질문은 planner가 재료를 수집하도록 바뀌었지만, `difference` / `lookup` 결과를 더 구조적으로 남기는 result schema 정리가 필요하다.
- final refusal ownership은 `aggregate_subtasks`로 올라왔지만, 실제 benchmark 문항에서 `planner_feedback -> replan -> close/refusal`이 자연스럽게 도는 end-to-end 검증은 아직 얕다.

## 바로 다음에 할 일

| 순서 | 할 일 | 목적 |
| --- | --- | --- |
| 1 | `NAV_T1_071` 같은 문항으로 `planner_feedback -> replan -> close/refusal` 루프를 end-to-end 재검증 | planner/synthesizer feedback loop를 실제 질문에서 닫기 |
| 2 | `lookup`, `difference`, `ratio` 결과를 더 구조화된 result schema로 남기기 | synthesizer가 원본 질문 충족 여부를 더 안정적으로 판정 |
| 3 | concept-only planner canary를 더 넓혀 runtime default 승격 가능성 검토 | benchmark-shaped metric ontology 의존 축소 |
| 4 | `tasks + artifacts`를 runtime source of truth로 더 강하게 쓰고 legacy `calculation_*`를 projection으로 내리기 | multi-step numeric trace를 덮어쓰지 않고 보존 |

## 현재 우선순위 요약

1. planner/synthesizer feedback loop 검증
2. result schema settling
3. concept-only planner default 승격 검토
4. runtime schema settling

## 현재 해석

- 지금 시스템은 “질문 1개 -> 답 1개” 구조에서 더 멀어져, `task + artifact + structured table object + final synthesizer` 중심으로 이동 중이다.
- planner는 점점 benchmark-shaped metric family보다 **concept + operation + material gathering** 쪽으로 옮겨가고 있다.
- answer completeness와 최종 refusal은 planner가 아니라 final synthesizer / aggregate 단계가 책임지는 방향으로 경계가 정리되고 있다.
- 다만 아직은 완전한 source of truth 이전 단계이며, evaluator 호환을 위해 legacy 필드를 병행 유지한다.
- 따라서 다음 구현은 retrieval / parser local patch보다 **planner-synthesizer contract와 structured result schema를 더 강하게 만드는 방향**이 맞다.
