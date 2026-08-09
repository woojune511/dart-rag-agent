# 프로젝트 컨텍스트

> 새 세션에서 현재 상태를 2분 안에 파악하기 위한 snapshot이다. 현재 계약과
> 우선순위는 [project_status.md](docs/overview/project_status.md), 구조적 결정은
> [DECISIONS.md](DECISIONS.md)를 따른다. 구현 및 실험의 상세 연대기는 각각
> [implementation_history.md](docs/history/implementation_history.md)와
> [experiment_history.md](docs/history/experiment_history.md)에 있다.

Last updated: 2026-08-10

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
  aggregate-role preference predicate를 적용한다. 같은 owner의 plain table-label
  metadata scorer는 graph-built slot과 evidence만 받아 empty-slot/label/unit/digit
  gate 뒤 기존 additive weights를 그대로 계산한다. 첫 두 caller는 empty slot도
  scorer에 전달하고 period-context caller는 empty slot을 먼저 건너뛰는 비대칭을
  유지한다. 같은 owner의 plain direct-target conflict predicate는 graph가 준비한
  target row, existing rows와 required operands만 받아 unit/value conflict와 aggregate
  preference를 판정한다. Target/existing gate, matcher별 row copy, repeated unit
  normalization, aggregate-role veto, aggregate-like와 structured-source lazy access
  순서를 보존한다. `operand_row_values_differ`의 float `TypeError`/`ValueError`는 기존
  raw/value fallback으로 이어지고, 그 밖의 mapping/matcher/copy/string/normalizer/
  cleaner/iteration 예외는 전파된다. Typed base-scorer reason은 contract output이지
  runtime trace가 아니다. Direct
  preferred slot에는 score precedence와 ratio peer-unit
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
  유지한다. 같은 owner의 plain `surface_contract_numeric_evidence_items(...)`는
  evidence와 required-operand sequence를 source order대로 처리한다. Falsy input은 fresh
  empty list를 반환하고, retained evidence는 fresh top-level copy와 nested alias를
  유지한다. Fixed surface-field order, positive/negative/numeric predicate laziness,
  global first-seen key dedupe, input immutability와 uncaught exception 순서도 보존한다.
  같은 owner의 plain `ratio_context_has_metric_surface(...)`는 task의 metric-label
  surfaces와 graph가 전달한 retrieved ratio context를 state-free bool로 비교한다.
  Task field/alias 수집과 repeated normalization, stable label dedupe, 모든 context
  evidence/metadata의 eager shallow-copy 및 fixed-surface materialization, first-match
  laziness, input immutability와 uncaught exception 순서를 보존한다. Graph는 existing
  ratio-result row의 family/task/signature/status/artifact/value/completeness/tolerance
  gate, exact-object owner call과 결과 inversion, recalculation/adoption, evidence,
  state/artifact 및 final orchestration을 유지한다.
  Dependency owner는 graph가 준비한 source slot, operand와 optional
  structured-realigned operand sequence만 받는 plain equivalence predicate도 소유한다.
  Marker-first direct copy와 fallback role/raw/id filtering, final non-task source-id
  intersection, input immutability와 uncaught exception 순서를 보존한다. Graph는
  operation-family/source-slot/candidate preparation, source-task/material/
  anchor-projection mismatch gate, coherence rank와 ratio scope를 유지한다. 같은 owner는
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
  dependency row construction을 유지한다. 같은 owner의 plain predicate는
  dependency-resolved `task_output:` row의 normalized KRW value가 raw/result unit
  normalization과 exact scaled tolerance에 일치하는지만 판정한다. Graph는 row
  coercion과 table-metadata repair의 두 call placement와 이후 mutation/orchestration을
  유지한다.
- Execution owner는 deterministic difference/growth plan construction, plan
  validation, formula execution, value-only freshness assessment를 소유한다.
  Answer-slot owner는 prepared ratio calculation result와 primary slot의 display를
  typed result로 동기화한다. Formula-trace mismatch에서는 top-level result와
  derived metrics를 복사하고, 그 외 성공 경로에서는 전달된 result identity를
  그대로 갱신하며 status/unit/current-surface gate와 예외 순서를 보존한다.
  같은 owner의 plain `source_task_display_compatible_with_slot(...)`는 graph가 찾은
  source-task display를 prepared answer slot과 비교한다. Blank display, rendered/raw
  equality, `task_output:` source, raw-unit blank/containment, normalized-unit 및
  configured KRW display gate의 short-circuit/access/exception 순서를 보존하고 input을
  변경하지 않는다. Graph는 source-task/slot lookup과 material gate, source-display
  truthy call gate, owner True adoption/False rendered-then-raw fallback, growth material,
  state/artifact 및 final orchestration을 유지한다.
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
  같은 owner는 graph가 준비한 ordered results와 aggregate projection을 final
  synthesis용 compact prompt rows로 투영한다. Result/answer-slot/ordered fallback
  precedence, material operand filtering과 stable task grouping, fixed field/getter
  순서, fresh container와 nested alias 계약을 유지한다. Runtime-trace owner의
  public material-numeric predicate를 공유하며, 그 predicate는 `missing` gate,
  raw/unit 및 raw/value/rendered/display fallback, digit gate와 normalized-value
  access 순서를 기존 그대로 보존한다. 같은 runtime-trace owner의 plain
  `overlay_calculation_operands_from_slots(...)`는 trace operand를 stable order로
  shallow-copy하고 matched-role 우선 lookup key로 graph가 준비한 slot의 일곱
  value/unit/source field를 overlay한다. Falsy slot no-op, optional normalized-role
  lookup, fresh list/top-level rows, nested aliases, input immutability와 uncaught
  exception 순서를 보존한다.
  같은 owner의 plain `subtask_numeric_answers_conflict(...)`는 candidate row를
  current row보다 먼저 answer/formatted/rendered fallback 순서로 resolve하고 두
  numeric surface를 모두 추출한 뒤, candidate-major/current-minor
  `all(any(...))` equivalence를 기존 비대칭과 short-circuit 순서로 적용한다.
  Plain `subtask_row_has_direct_source_refs(...)`는 calculation-result를 먼저
  shallow-copy하고 row/result의 네 source surface를 기존 cleaner 순서로 합친 뒤
  `task_output:`이 아닌 첫 direct ref를 판정한다. 두 predicate 모두 input을
  변경하거나 exception을 catch하지 않는다.
  Numeric-surface owner는 table metadata에서 final-answer numeric support text를
  만드는 helper를 private하게 소유하고, 준비된 evidence를 promote하는 plain public
  `promote_table_numeric_support_evidence(...)`를 제공한다. Empty/no-support 경로는
  exact evidence identity를 유지하고,
  support 경로는 fresh top-level evidence와 metadata copy를 만들되 다른 nested alias를
  보존한다. Stable first-four line, answer-major equivalence, header laziness, claim/quote
  access와 uncaught exception 순서도 기존과 같다.
  같은 numeric-surface owner의 plain `answer_covers_numeric_answer(...)`와
  `answer_has_numeric_material_outside_reference(...)`는 두 input surface를 모두
  answer-first로 추출한 뒤 각각 numeric-major `all(any(...))` coverage와
  answer-major `any(not any(...))` outside-reference 비교를 수행한다. Empty-list gate,
  stable lazy equivalence, input immutability와 uncaught exception 순서를 보존한다.
  Task-artifact owner는 graph가 준비한 artifact records, final answer와 aggregate
  projection으로 첫 exact-id aggregate artifact의 payload와 summary를 동기화한다.
  Stable order, copy-all-before-search, shallow alias와 예외 순서를 유지한다. 같은
  owner의 private collector와 public enrichment primitive는 graph가 준비한 operand
  rows와 extra refs를 reconciliation artifact evidence refs에 반영한다. Empty refs는
  exact artifact-list identity와 access laziness를, nonempty refs는 모든 artifact의
  fresh top-level copy와 nested alias를 유지한다. Strict-dict row gate, 열 개 source-ref
  field 순서, stable old-first dedupe, task/kind/payload/result/status gate와 uncaught
  exception 순서는 바뀌지 않으며 runtime-normalization의 private source-id cleaner를
  owner가 직접 사용한다. Public enrichment만 export되고 collector는 private다.
- Aggregate-state owner는 public `AggregateCompositionState`와 공통 state-free
  composition transition을 소유한다. 이 transition은 answer fallback, current-first
  claim merge, projection reset/override, narrative lock와 feedback clear/preserve를
  기존 평가 순서와 alias 계약대로 새 carrier에 적용한다. Graph는 다섯 producer와
  모든 gate, 순차 state handoff, later `_replace`, broader answer precedence와 final
  orchestration을 유지한다.
- Graph는 direct row/evidence construction, coercion과 scope filtering,
  target override, acceptance applicability gate, table-label metadata scorer의
  세 caller placement와 empty-slot 비대칭, direct structured preference의
  target builder, evidence pool/coercion, scope gate, conflict-owner call placement,
  target adoption과 evidence append,
  runtime evidence overlay, row iteration, peer-unit preparation, strongest-slot
  builder, query/report-scope score 보강, ambiguity/tie-break와 sequential adoption,
  recovered-context eligibility와 document/evidence 및 row builder,
  required-candidate builder와 lazy coherent-context builder를 유지한다. Post-coercion
  LLM 경로에서도 model invocation, evidence lookup, scope-conflict skip, operand-id
  assignment, coercion, applicability gate, enclosing try와 fallback을 유지한다.
  Required-operand surface filter 주변에서는 evidence/reconciliation 및 required-list
  preparation, direct-grounding computation, unconditional owner call placement, narrative/
  restriction gate, surface-result merge/dedupe/logging, later missing-required fallback-row
  merge와 이후 LLM/state/final orchestration을 유지한다.
  Recovery logging과 ratio-recovered flag projection, retry/query gate,
  state/task/artifact projection, repair acceptance, aggregate/filter sequencing,
  dependency source-slot 선택과 component ranking, ratio formula/query policy,
  source-id cleaning, compact formatting,
  recalculated result-value coercion과 invalid-value artifact-builder skip,
  dependency-unit inference의 네 call placement와 conditional second inference,
  dependency task-output KRW consistency predicate의 두 call placement, row
  coercion과 table-metadata repair,
  dependency candidate-input construction/execution, query/absolute transform,
  task-artifact/ledger conflict short-circuit와 formatter, sibling-table evidence selection과
  candidate realignment 및 preparation/map propagation, collapsed-ratio
  trace/eligibility/completeness/query gate와 prepared role-map, default-mode overlay
  owner call 및 empty result까지 unconditional adoption, single-period comparison의
  evidence/realignment gate와 four-alias role-map, normalized-mode owner call 및
  truthy-only adoption, prepared
  copies, retrieved ratio-context의 existing-result iteration, signature/status/artifact-
  backed/value/completeness/tolerance gate와 metric-surface owner call placement/inversion,
  downstream coherence/compact-answer/coverage/final projection, structured
  provenance lookup과 후속 evidence lookup/coercion/append, aggregate evidence와
  kept-id selection, rebuild gate, selected claims, final-answer surface-operand append,
  nested-result promotion, preliminary/final projection rebuild, dependency alignment,
  preserved-field merge, aggregate candidate discovery/scoring/selection, narrative
  refresh, packaging과 composition-transition call placement/laziness, application
  invocation과 broader answer precedence, aggregate synthesis의 LLM gate/model/
  prompt construction, post-period-realignment input preparation, JSON/debug/prompt
  invocation과 enclosing catch/fallback,
  final-answer evidence filter의 candidate/selection/support gate와 local evidence/
  metadata copy, retrieved-narrative promoter skip, numeric-support owner call placement,
  returned-row adoption과 후속 selection/filtering,
  aggregate row candidate/sentence/conflict gate, rendered extraction, row iteration,
  lookup primary-slot 준비와 truthy gate, per-row owner iteration, task-id/equality
  update map, ordered/slot propagation과 final projection rebuild,
  ordered ratio-row gate와 before/after display comparison, compact-answer construction,
  row answer/result propagation과 state/active-subtask/operand/period/metric formatting,
  source-task display lookup과 material gate, truthy compatibility-owner call placement,
  False-path rendered/raw fallback 및 이후 growth calculation/material sequencing,
  aggregate task-ledger finalization의 replacement gate와 numeric-conflict-before-
  preservation disposition, projection-row sentence scorer 및 arithmetic-surface
  synchronizer의 numeric-conflict call placement와 polarity,
  public/structured projection, task-answer preservation, score, arithmetic sync,
  recovered-ratio row, stale repair와 initial-state 경로의 numeric coverage/outside-
  reference owner call placement, 선행 gate와 결과 polarity,
  aggregate artifact의 initial copy, ratio/render/completeness/formatter/projection
  mutation과 `None`/blank-id gate, ledger creation/finalization, mutable state/evidence,
  reconciliation-ref owner의 두 call placement와 artifact/task/state input 구성,
  operand-set artifact 및 integrity/replan 소비, stale repair와 final
  orchestration, full aggregate dedupe/rank tuple/nested promotion의 status/material/
  direct-source/family/numeric-conflict/sign-rank chain, 기타 absolute-ratio 및
  fallback orchestration도 graph에 남는다. 전체 ledger
  synchronization과 broader single-calculation-path Phase 3는 완료되지 않았다.

## 현재 검증 기준

| 항목 | 상태 |
| --- | --- |
| Recorded benchmark evidence | 정확한 수치와 raw-artifact 경계는 [project_status.md](docs/overview/project_status.md)를 단일 기준으로 사용 |
| Demo fixture contract | `fixture_contract_ready`; SHA-256 manifest verified, live replay 아님 |
| Portfolio review surface | `review_surface_ready`; unit test/domain audit은 이 명령에서 `not_run` |
| Latest calculation runtime validation | targeted 4/4, affected 582/582, full unittest 1,535/1,535 PASS |
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
