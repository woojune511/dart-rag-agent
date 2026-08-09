# 프로젝트 컨텍스트

> 새 세션에서 현재 상태를 2분 안에 파악하기 위한 snapshot이다. 현재 계약과
> 우선순위는 [project_status.md](docs/overview/project_status.md), 구조적 결정은
> [DECISIONS.md](DECISIONS.md)를 따른다. 구현 및 실험의 상세 연대기는 각각
> [implementation_history.md](docs/history/implementation_history.md)와
> [experiment_history.md](docs/history/experiment_history.md)에 있다.

Last updated: 2026-08-09

## 현재 범위

- 제품 surface는 DART 공시를 분석하는 single-agent `FinancialAgent`다.
- 핵심 흐름은 구조 보존 ingest, dense/BM25 hybrid retrieval, LLM semantic
  planning, deterministic calculation, evidence/provenance validation이다.
- MAS, report cache promotion, evaluator, benchmark runner, review workflow는
  optional 또는 experimental surface다.
- 범용 agent, broad web workflow, productivity tool 확장은 현재 범위가 아니다.

## 현재 소스 상태

- PR #79부터 #84까지의 portfolio core simplification과 PR #85의 handoff
  문서 압축이 `main`에 병합됐다.
- 최신 확인 merge commit은 PR #85의 `f0a5145`다.
- `FinancialAgent.run()`의 public numeric surface는
  `resolved_calculation_trace`, `structured_result`, task/artifact projection을
  사용하며 top-level `calculation_*` compatibility mirror를 되살리지 않는다.
- default import와 unconfigured invocation은 MAS, evaluator, benchmark,
  promotion, portfolio-review, persisted cache-index 구현을 로드하지 않는다.
- tracked benchmark result surface는 과거 324개 raw/intermediate 파일에서
  history가 직접 참조하는 compact summary 및 작은 diagnostic 26개로 줄었다.
  전체 result bundle, store, cache, heartbeat log는 local-only다.
- 현재 `codex/finalize-five-minute-review` branch HEAD가 local source
  checkpoint다. 정확한 commit은 `git log`로 확인하며, 이 branch는 아직
  push/merge하지 않았다.
- 계산 경로는 graph-state adapter와 state-free operand, dependency,
  deterministic-execution owner로 나뉜다. Operand owner는 producer-scope
  filtering 뒤의 required candidate와 graph가 lazy하게 만든 coherent candidate를
  merge하고, complete ratio candidate-first 또는 그 밖의 current-first precedence를
  state-free result로 반환한다. 같은 owner는 graph가 구성·coerce·scope-filter한
  direct structured row에 required match/surface, ambiguity, lookup direct-support
  gate를 runtime 순서대로 적용하는 typed acceptance도 소유한다. Graph가 준비한
  structured evidence에는 operand/evidence만 받는 typed base scorer와 ordered
  aggregate-role preference predicate를 적용한다. Scorer reason은 contract output이지
  runtime trace가 아니다. Direct preferred slot에는 score precedence와 ratio peer-unit
  alignment, exact row overlay를 typed state-free result로 적용한다. Graph가 복구한
  period/ratio row에는
  period recovered-first merge 또는 coherent-ratio replacement와 사용 evidence
  adoption을 typed state-free result로 적용한다. Graph가 LLM row를 coerce하고
  applicability를 확인한 뒤에는 같은 owner가 per-row lookup direct-support와,
  required operand가 있을 때의 ordered match/surface, lookup rematch,
  direct-first merge를 두 typed state-free seam으로 적용한다. 이 seam의 reason과
  application flag는 contract output이지 runtime trace가 아니다. 같은 operand owner는
  graph가 준비한 단일 row의 embedded raw-unit 또는 rendered-unit normalization repair를
  plain state-free transform으로 소유한다. 모든 경로에서 fresh top-level dict를 만들고
  nested alias, scaled tolerance와 `NaN` 비대칭, first rendered match, access/exception
  순서를 보존하며 input을 변경하지 않는다. 같은 owner가 graph가 선택한 ordered ratio
  operands에는 shared table id 또는 complete section/statement/scope context 안의 display
  unit을 largest configured scale로 정렬한다. No-change는 exact input list/row identity를,
  changed path는 모든 row의 fresh top-level copy와 nested alias를 보존한다. Graph는
  evidence-driven sibling aligner와 candidate selection, caller gate와 operand-map propagation을
  유지한다. Dependency owner는
  main precedence, late re-merge, terminal finalization, dependency recalculation plan
  disposition을 소유한다. Graph가 준비한 ordered artifact rows와 이미 coerce한
  recalculated numeric authority에는 status fallback, artifact numeric precedence,
  scaled tolerance, stable first-conflict selection과 shallow-copy preservation marker를
  typed state-free result로 적용한다. 이 reason/flag도 runtime trace가 아니다.
  Executable `single_value` plan은 reuse하고 invalid/absent plan은 한 번 rebuild하며,
  executable non-`single_value` plan은 `unsupported_mode`로 해당 row를 재계산하지
  않는다. 다른 row도 바뀌지 않은 no-change 경로에서는 원본 list/row identity를
  유지한다. Supported candidate 실행 뒤 Stage 1은 operand-row/plan/result shallow
  copy와 두 번째 mutable result copy를 만들고 `calculation_result.status`로만
  disposition을 결정한다. Graph가 query/absolute transform, artifact-ledger conflict
  short-circuit와 formatter를 적용한 뒤 Stage 2는 truthy formatted result와
  trace-first/fallback row projection을 소유한다. 이 readiness/reason은 trace가
  아니며 selected evidence projection은 추가되지 않았다. Graph가 dependency row와
  초기 unit fields를 만든 뒤 stateful lookup으로 structured provenance를 찾으면, dependency
  owner가 같은 mutable row에 source anchor/chunk id, converted-display 보존 또는 unit
  realignment, consolidation/statement/table metadata를 runtime 순서대로 적용한다.
  Typed reason과 application flag는 trace가 아니며 provenance input은 변경하지 않는다.
  Dependency-source ratio rebuild의 이미 준비된 result/slot/value/unit/source-id
  payload도 같은 owner가 fresh canonical calculation result로 투영한다. 네 result/slot
  surface는 exact source-id list를 공유하고 numerator/denominator slot identity를
  group/role list에서 유지한다. Dependency row의 display/normalized unit inference도
  같은 owner의 plain state-free primitive다. Slot raw unit을 sibling result unit보다
  우선하고, normalized unit이 `UNKNOWN`일 때만 percent, KRW, count policy를 기존
  membership 순서로 적용한다. Graph는 네 caller gate, conditional re-inference와
  dependency row construction을 유지한다.
- Execution owner는 deterministic difference/growth plan construction, plan
  validation, formula execution, value-only freshness assessment를 소유한다.
  Answer-slot owner는 prepared ratio calculation result와 primary slot의 display를
  typed result로 동기화한다. Formula-trace mismatch에서는 top-level result와
  derived metrics를 복사하고, 그 외 성공 경로에서는 전달된 result identity를
  그대로 갱신하며 status/unit/current-surface gate와 예외 순서를 보존한다.
  Aggregate owner는 pure stale provenance target selection, canonical aggregate
  operation-family normalization, aggregate-result signature와 growth operand
  sign-consistency rank primitive, graph가 준비한
  calculation-result/slot/primary copies의 negative runtime-ratio
  absolute-magnitude projection, base/refreshed answer candidate payload packaging,
  prepared candidate application과 final-answer projection synchronization을 소유한다.
  Packaging seam은 normalized answer, stable nonblank claim-id list와 세 기존 flag를
  fresh payload로 만들며, application seam은 같은 aggregate projection
  identity를 유지하고 normalized answer와 current-first stable merged claim-id list를
  반환한다. 같은 owner는 graph가 선택한 kept evidence ids를 받아 aggregate
  projection의 generated provenance만 state-free하게 filter한다. Empty kept set은
  입력 projection identity를 그대로 유지하고, nonempty 경로는 기존 shallow-copy와
  stable id-order 계약을 보존한다. 또한 graph가 준비한 ordered result rows의 세
  nested subtask surface를 current top-level task row와 재귀적으로 동기화하며,
  last-id-wins, stable order, cycle/depth, conditional shallow-copy 계약을 유지한다.
  Graph가 선택한 aggregate projection row와 answer/rendered surface에는 first/last
  numeric selection과 conditional result/slot/lookup surface synchronization을 typed
  state-free result로 적용하며 raw answer, copy/identity, access/exception 순서를 보존한다.
  Graph가 준비한 lookup primary slots에는 arithmetic component, series와
  difference/sum delta synchronization을 typed state-free result로 적용한다. Empty/
  ineligible row identity, eligible shallow-copy와 nested alias, concept-first/label
  match, stable first-slot, overlay와 예외 순서를 유지한다.
  Task-artifact owner는 graph가 준비한 artifact records, final answer와 aggregate
  projection으로 첫 exact-id aggregate artifact의 payload와 summary를 동기화한다.
  Stable order, copy-all-before-search, shallow alias와 예외 순서를 유지한다.
- Aggregate-state owner는 public `AggregateCompositionState`와 공통 state-free
  composition transition을 소유한다. 이 transition은 answer fallback, current-first
  claim merge, projection reset/override, narrative lock와 feedback clear/preserve를
  기존 평가 순서와 alias 계약대로 새 carrier에 적용한다. Graph는 다섯 producer와
  모든 gate, 순차 state handoff, later `_replace`, broader answer precedence와 final
  orchestration을 유지한다.
- Graph는 direct row/evidence construction, coercion과 scope filtering,
  target override, acceptance applicability gate, direct structured preference의
  runtime evidence overlay, row iteration, peer-unit preparation, strongest-slot
  builder, query/report-scope score 보강, ambiguity/tie-break와 sequential adoption,
  recovered-context eligibility와 document/evidence 및 row builder,
  required-candidate builder와 lazy coherent-context builder를 유지한다. Post-coercion
  LLM 경로에서도 model invocation, evidence lookup, scope-conflict skip, operand-id
  assignment, coercion, applicability gate, enclosing try와 fallback을 유지한다.
  Recovery logging과 ratio-recovered flag projection, retry/query gate,
  state/task/artifact projection, repair acceptance, aggregate/filter sequencing,
  dependency source-slot 선택과 component ranking, ratio formula/query policy,
  source-id cleaning, compact formatting,
  recalculated result-value coercion과 invalid-value artifact-builder skip,
  dependency-unit inference의 네 call placement와 conditional second inference,
  dependency candidate-input construction/execution, query/absolute transform,
  task-artifact/ledger conflict short-circuit와 formatter, sibling-table evidence selection과
  candidate realignment 및 preparation/map propagation, collapsed-ratio
  trace/eligibility/completeness/query gate와 prepared
  copies, downstream coherence/compact-answer/coverage/final projection, structured
  provenance lookup과 후속 evidence lookup/coercion/append, aggregate evidence와
  kept-id selection, rebuild gate, selected claims, final-answer surface-operand append,
  nested-result promotion, preliminary/final projection rebuild, dependency alignment,
  preserved-field merge, aggregate candidate discovery/scoring/selection, narrative
  refresh, packaging과 composition-transition call placement/laziness, application
  invocation과 broader answer precedence,
  aggregate row candidate/sentence/conflict gate, rendered extraction, row iteration,
  lookup primary-slot 준비와 truthy gate, per-row owner iteration, task-id/equality
  update map, ordered/slot propagation과 final projection rebuild,
  ordered ratio-row gate와 before/after display comparison, compact-answer construction,
  row answer/result propagation과 state/active-subtask/operand/period/metric formatting,
  aggregate artifact의 initial copy, ratio/render/completeness/formatter/projection
  mutation과 `None`/blank-id gate, ledger creation/finalization, mutable state/evidence,
  stale repair와 final
  orchestration, full aggregate dedupe/rank tuple/nested promotion, 기타 absolute-ratio 및
  fallback orchestration도 graph에 남는다. 전체 ledger
  synchronization과 broader single-calculation-path Phase 3는 완료되지 않았다.

## 현재 검증 기준

| 항목 | 상태 |
| --- | --- |
| Recorded benchmark evidence | 정확한 수치와 raw-artifact 경계는 [project_status.md](docs/overview/project_status.md)를 단일 기준으로 사용 |
| Demo fixture contract | `fixture_contract_ready`; SHA-256 manifest verified, live replay 아님 |
| Portfolio review surface | `review_surface_ready`; unit test/domain audit은 이 명령에서 `not_run` |
| Latest calculation runtime validation | targeted 4/4, affected 632/632, full unittest 1,505/1,505 PASS |
| Runtime domain-term audit | 217개 reviewed literal PASS |
| Benchmark refresh after latest calculation changes | NOT RUN; 이전 recorded benchmark를 최신 변경의 검증 근거로 사용하지 않음 |
| Publication validation | [validation.yml](.github/workflows/validation.yml)과 [project_status.md](docs/overview/project_status.md)를 기준으로 확인 |

현재 알려진 unit/contract correctness blocker는 없다. Commit별 correctness,
structural relocation, source metrics, validation, claim limits는
[implementation_history.md](docs/history/implementation_history.md)에만 보존한다.

## 구현 원칙

- benchmark 질문이나 회사명을 runtime branch에 넣지 않는다.
- 금융 domain vocabulary는 ontology, retrieval policy, config, documented data
  artifact에 둔다.
- LLM은 intent와 semantics를 판단하고, 산술·단위·dependency binding·dedupe·
  validation은 deterministic code가 담당한다.
- answer composer는 evidence에 없는 claim을 만들지 않는다.
- parser/ingest/cache signature가 바뀌지 않으면 store-fixed `eval-only`를
  fresh ingest보다 우선한다.
- `src/agent` 또는 `src/routing`을 바꾸면 broader tests 전에
  `python -m src.ops.audit_runtime_domain_terms`를 실행한다.

## 바로 다음에 할 일

현재 우선순위와 stop line의 단일 기준은
[project_status.md의 Next Work](docs/overview/project_status.md#next-work)다.
이 snapshot에서는 같은 backlog를 반복하지 않는다. 새 세션은 해당 section에서
첫 bounded slice와 검증 경계를 확인한다.

## 새 세션 시작 순서

1. `AGENTS.md`
2. 이 문서
3. [project_status.md](docs/overview/project_status.md)
4. `git status -sb`
5. `git log -5 --oneline`

ChatGPT/Codex memory는 사용자 선호와 반복 작업 습관만 보조적으로 사용한다.
최신 커밋, blocker, benchmark 결과, API/model 상태의 사실 근거는 repo 문서와
Git이다.

## 상세 기록

- 구조 및 runtime 단순화: [implementation_history.md](docs/history/implementation_history.md)
- benchmark 및 실험: [experiment_history.md](docs/history/experiment_history.md)
- 현재 실행 계획과 stop line:
  [core_runtime_surface_refactoring_plan.md](docs/architecture/core_runtime_surface_refactoring_plan.md)
- 장기 backlog: [backlog_and_next_epics.md](docs/planning/backlog_and_next_epics.md)

이 reviewer 정리 이전 snapshot은 Git의 `main@f0a5145:CONTEXT.md`에서 복구할
수 있다.
