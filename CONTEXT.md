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
- 내부 실행 구조 일반화를 위한 1차 schema를 추가했다.
  - `tasks`, `artifacts` state 추가
  - parser의 `table_object / row_record / cell_record`를 정식 출력으로 승격 시작
  - semantic plan / reconciliation / operand set / calculation plan / calculation result / aggregated answer를 artifact로 기록 시작

## 현재 핵심 한계

- legacy `calculation_*` 필드가 아직 evaluator와 runtime 일부 경로의 사실상 기준처럼 남아 있다.
- multi-subtask numeric question에서 최종 자연어 답과 structured trace가 완전히 같은 결과 집합을 보존하지 못하는 경우가 있다.
- structured table grounding은 핵심 비율 문항에서 동작하기 시작했지만, 더 넓은 numeric family로의 확장이 아직 필요하다.

## 바로 다음에 할 일

| 순서 | 할 일 | 목적 |
| --- | --- | --- |
| 1 | `tasks + artifacts`를 runtime source of truth로 더 강하게 쓰고 legacy `calculation_*`를 projection으로 내리기 | multi-step numeric trace를 덮어쓰지 않고 보존 |
| 2 | `table_object_json` / `row_record` / `cell_record`를 reconciliation과 operand extraction 전반에서 더 직접 소비하게 넓히기 | alias/rule보다 구조 중심 grounding으로 전환 |
| 3 | `MIX_T1_021`류 복수 지표 질문을 포함해 더 많은 numeric family를 end-to-end 재검증 | 최종 답과 structured trace의 일치 회복 |
| 4 | single-doc numeric path가 안정화되면 DART multi-document reasoning(사업/반기/분기/정정공시)으로 확장 | DART 범위 안에서 다음 단계로 이동 |

## 현재 우선순위 요약

1. runtime schema settling
2. structured table grounding coverage 확대
3. numeric end-to-end validation
4. DART multi-document reasoning

## 현재 해석

- 지금 시스템은 “질문 1개 -> 답 1개” 구조에서 벗어나기 시작했고, `task + artifact + structured table object` 중심으로 옮겨가는 중이다.
- 다만 아직은 완전한 source of truth 이전 단계이며, evaluator 호환을 위해 legacy 필드를 병행 유지한다.
- 따라서 다음 구현은 **새 구조를 더 강하게 쓰는 방향**이어야 하고, 기능을 넓히기 전에 내부 표현을 먼저 굳히는 것이 맞다.
