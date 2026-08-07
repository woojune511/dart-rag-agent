# 프로젝트 컨텍스트

> 새 세션에서 현재 상태를 2분 안에 파악하기 위한 snapshot이다. 현재 계약과
> 우선순위는 [project_status.md](docs/overview/project_status.md), 구조적 결정은
> [DECISIONS.md](DECISIONS.md)를 따른다. 구현 및 실험의 상세 연대기는 각각
> [implementation_history.md](docs/history/implementation_history.md)와
> [experiment_history.md](docs/history/experiment_history.md)에 있다.

Last updated: 2026-08-08

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
  push/merge하지 않았다. 계산 경로는 graph-state adapter, state-free operand
  resolution, dependency projection, deterministic execution owner로 나뉜다.
  dependency owner는 main precedence, typed late re-merge, generic normalized-unit
  filter와 no-filter empty preservation을 포함한 typed terminal finalization을
  소유한다. graph는 evidence context builder, percent-point query gate, coverage와
  logging/state projection, 기타 fallback, aggregate repair를 유지한다.
  graph에는 graph-private typed calculation-candidate seam이 있어 preparation,
  result projection, state/ledger projection을 분리한다. stale repair는 이 seam으로
  candidate를 한 번 prepare/execute하고, execution owner의 typed value-only
  freshness assessment 뒤 stale일 때만 result를 project한다. graph에는
  applicability/same-slot guard가 남아 있다. `be2e7bf`는 accepted stale repair의
  caller projection을 제한적으로 동기화한다. render는 selected/kept refs와 같은
  id의 최신 calculation-result artifact를, planning capture는 반환 row refs만,
  aggregate는 pre-filter evidence snapshot에서 유일한 provenance target과 accepted
  refilter를 동기화한다. ambiguous refs는 보존하며 전체 ledger synchronization을
  완료한 것은 아니다. `2cfa867`은 이 aggregate provenance selection과 canonical
  aggregate operation-family normalization을 typed state-free
  `financial_aggregate_projection.py` owner로 옮겼다. graph는 기존 68개 caller를
  위한 1-line delegate와 repair acceptance, pre-filter snapshot, accepted refilter,
  answer/state orchestration을 유지한다. `1a3979e`는 graph-private typed
  `_CalculationCandidateRun`과 `_run_calculation_candidate()`를 추가했다. primary
  `_execute_calculation()`은 기존 state/ledger projector를 유지하지만,
  dependency·period의 contract-valid scalar recovery는 candidate projection의
  operands, plan, result만 직접 소비한다. 이 두 경로의 내부
  `_execute_calculation()` 호출, strict trace 재조회, 버려지던 state/ledger
  projection은 제거됐다. 결과, 순서, 입력 불변성, failure/no-op identity는
  유지된다. `af968a6`은 difference/growth deterministic plan builder와 raw/guarded
  typed decision을 state-free `financial_calculation_execution.py` owner로 옮겼다.
  graph는 state/query 해석과 percent-point result-unit policy를 적용하는 thin
  adapter 및 primary full state/artifact projection을 유지한다. period recovery의
  ready/guarded 경로는 selected plan을 직접 소비해 planner/artifact/runtime
  projection을 만들지 않고, not-applicable 경로는 builder를 다시 호출하지 않은 채
  기존 fallback으로 이어진다.
  별도 behavior fix `ec93f8a`는 complete plan을 만든 뒤 percent-point policy를
  평가하도록 adapter를 고쳤다. eligible `%p` query와 두 `PERCENT` operand는 복사된
  plan의 `result_unit="%p"`를 받고, non-eligible/no-plan 경로는 유지된다.
  별도 behavior fix `8296eb1`은 parent `structured_result`/`subtask_results`가
  explicit dependency recalculation trace를 override하던 P1을 막는다. 이어진
  behavior-preserving structural cleanup `ea84921`은 기존 executable plan이면 raw
  builder를 호출하지 않고, invalid/absent plan이면 raw plan을 한 번만 만든다. graph는
  그 explicit raw plan과 pre-candidate operands를 direct `_CalculationCandidateInput`에
  넘기고 ratio formatter에는 active task와 같은 operands를 명시적으로 전달한다.
  dependency synthetic-state helper와 raw-plan callback은 삭제됐지만 primary
  state/artifact projection, repair acceptance와 absolute-ratio orchestration은 graph에
  남아 있다. 재사용된 비정상 dependency `time_series` plan의 state-projector 예외
  parity는 이 supported scalar cleanup의 보장 범위가 아니다.

## 현재 검증 기준

| 항목 | 상태 |
| --- | --- |
| Recorded benchmark evidence | 정확한 수치와 raw-artifact 경계는 [project_status.md](docs/overview/project_status.md)를 단일 기준으로 사용 |
| Demo fixture contract | `fixture_contract_ready`; SHA-256 manifest verified, live replay 아님 |
| Portfolio review surface | `review_surface_ready`; unit test/domain audit은 이 명령에서 `not_run` |
| Latest aggregate provenance owner contract | affected regression 564개 PASS; benchmark refresh 미실행 |
| Latest deterministic operation-plan owner contract | targeted 4개, focused owner+aggregate 107개, affected regression 564개 PASS; benchmark refresh 미실행 |
| Latest percent-point plan-unit fix | targeted/adjacent 4개, execution module 29개, unique affected 593개 PASS; benchmark refresh 미실행 |
| Latest dependency trace-isolation fix | targeted 4개, full unittest 1,480개 PASS; benchmark refresh 미실행 |
| Latest dependency recalculation cleanup | targeted 3개, affected regression 615개 PASS; benchmark refresh 미실행 |
| Runtime validation | full unittest 1,479개 PASS; domain-term audit 217개 literal PASS |
| Publication validation | [validation.yml](.github/workflows/validation.yml)과 [project_status.md](docs/overview/project_status.md)를 기준으로 확인 |

현재 알려진 unit/contract correctness blocker는 없다. 별도 behavior fix
`b16a6c5`는 scope-rejected dependency의 late 재도입을 막았고, `c6f6fdf`는
terminal percent filter 뒤 unfiltered snapshot 재도입을 막았다. `5b44875`는 그
post-late finalization을 product behavior 변경 없이 state-free owner로 옮겼고,
별도 `8ebb239`는 필터 뒤 empty/partial coverage를 다시 계산한다. 그 뒤
`f0eafae`는 원문 표시값의 반복 stale repair를 막았고,
`2496fce`는 그 freshness assessment만 state-free execution owner로 옮겼다.
`406c1ef`는 stale 실행 snapshot을 characterization했고, `c2a5e96`은 product
behavior를 유지하면서 shared candidate pipeline을 graph-private seam으로
분해했다. 별도 behavior fix `f2af4f4`는 pre-preparation raw 값 `0.0035`를
current로 오판하던 경로를 prepared canonical 값 `3.5` 기준으로 고치고 stale
formula evaluation을 2회에서 1회로 줄였다. 이어진 behavior fix `be2e7bf`는
numeric freshness나 repair acceptance를 바꾸지 않고 render, capture, aggregate의
accepted repair provenance를 위 범위로 동기화했다. 이 commit은 graph를
19,736→19,933줄, graph planning을 2,367→2,371줄, task artifacts를
1,047→1,128줄로 바꿨고 source net은 `+282`줄이다. 이어진 behavior-preserving
relocation `2cfa867`은 graph의 old provenance body를 삭제하고 selection과 canonical
operation-family normalization을 aggregate owner로 옮겼다. graph는
19,933→19,802줄(`-131`), owner는 195→376줄(`+181`)이 됐으며 두 source의
합계는 `+197/-147`, net `+50`줄이다. 이는 total code reduction이나
executed-path reduction claim이 아니다.
이어진 `1a3979e`는 graph-private candidate run을 dependency·period recovery와
primary graph-node adapter가 공유하게 했다. graph는 19,802→19,813줄이며 source
diff는 `+36/-25`, net `+11`줄이다. tests는 `+176/-57`, net `+119`줄이고 whole
commit은 `+212/-82`, net `+130`줄이다. 두 characterized success path에서 state
projector 호출은 1회에서 0회가 됐지만, 이는 broad performance improvement나
total code reduction claim이 아니다. 재사용된 비정상 dependency `time_series`
plan의 state-projector exception parity까지 보장하는 변경도 아니다.
`af968a6`은 execution owner를 679→837줄(`+158`), graph를
19,813→19,786줄(`-27`, `+91/-118`)로 바꿨다. source는 `+249/-118`, net
`+131`줄이고 tests는 `+182/-5`, net `+177`줄이며 whole commit은
`+431/-123`, net `+308`줄이다. supported contract-valid difference/growth 결과와
순서, 입력 불변성은 유지하지만 malformed difference 입력의 percent-point policy
평가 시점과 예외 순서까지 동일하다는 주장은 하지 않는다. graph 감소를 전체 code
감소나 broad executed-path/performance 개선으로 해석하지 않는다.
별도 `ec93f8a`는 incomplete plan으로 percent-point policy를 평가하던 기존 버그를
고쳤다. graph diff는 `+9/-9`로 line-neutral이고 tests는 `+32/-0`, whole commit은
`+41/-9`, net `+32`줄이다. 이 fix는 eligible `%p` unit을 복구하지만 malformed
difference 입력 전체의 평가/예외 순서 parity를 주장하지 않는다.
별도 behavior fix `8296eb1`은 dependency owner를 2,833→2,835줄(`+2`)로 바꾸고
회귀 테스트 63줄을 더해 whole commit net `+65`줄이다. targeted 4개, 217-literal
audit, full 1,480개 테스트가 통과했다. 이어진 structural cleanup `ea84921`은 graph를
19,786→19,828줄(`+75/-33`, net `+42`), dependency owner를
2,835→2,796줄(`+3/-42`, net `-39`)로 바꿔 source는 `+78/-75`, net `+3`줄이다.
tests는 `+167/-90`, net `+77`줄이고 whole commit은 `+245/-165`, net `+80`줄이다.
targeted 3개, affected 615개, 같은 audit와 full 1,479개 테스트가 통과했다. 이 수치는
behavior fix와 supported scalar 구조 정리의 경계이며 broad performance, total-code
reduction, dependency owner 완료 또는 Phase 3 완료 주장이 아니다.
이 변경들에 대한 benchmark refresh는 실행하지 않았으므로, 이전
recorded benchmark를 검증 근거로 삼거나 새 score claim을 만들지 않는다.

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

README에서 시작하는 최종 reviewer walkthrough는 완료됐다. 대표 demo는
semantic planning, hybrid retrieval, deterministic calculation, provenance,
task/artifact integrity, critic acceptance를 한 흐름으로 보여준다. cache와
promotion surface는 명시적인 optional deep-validation 경로로 분리돼 있다.

다음 구조 작업은 재사용된 비정상 dependency `time_series` executable plan의
candidate/exception 동작을 먼저 characterization하는 bounded slice다. 그 경로가
supported contract가 아니라면 새 behavior를 섞지 않고 다음 bounded repair cluster로
넘어간다. 전체 ledger sync, aggregate precedence, 남은 deterministic/LLM fallback,
graph-owned artifact/absolute-ratio orchestration과 private facade/API mesh는 별도
follow-up으로 유지한다. 새 benchmark claim이 필요하면 현재 profile과 store
signature를 먼저 확인하고 monitored store-fixed `eval-only`로 갱신한다.

지금은 두 구조 slice를 한꺼번에 묶는 broad runtime refactor, 전면적인 test-file 분할, 새 MAS 기능,
cache serving 활성화를 시작하지 않는다. oversized test는 해당 public contract를
실제로 수정할 때만 함께 나눈다.

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
