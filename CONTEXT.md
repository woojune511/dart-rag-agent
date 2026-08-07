# 프로젝트 컨텍스트

> 새 세션에서 현재 상태를 2분 안에 파악하기 위한 snapshot이다. 현재 계약과
> 우선순위는 [project_status.md](docs/overview/project_status.md), 구조적 결정은
> [DECISIONS.md](DECISIONS.md)를 따른다. 구현 및 실험의 상세 연대기는 각각
> [implementation_history.md](docs/history/implementation_history.md)와
> [experiment_history.md](docs/history/experiment_history.md)에 있다.

Last updated: 2026-08-07

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
  execution owner는 typed state-free stale freshness assessment도 소유하지만,
  graph에는 applicability/same-slot guard, 두 번째 `_execute_calculation()`,
  caller projection과 ledger synchronization 책임이 남아 있다.

## 현재 검증 기준

| 항목 | 상태 |
| --- | --- |
| Recorded benchmark evidence | 정확한 수치와 raw-artifact 경계는 [project_status.md](docs/overview/project_status.md)를 단일 기준으로 사용 |
| Demo fixture contract | `fixture_contract_ready`; SHA-256 manifest verified, live replay 아님 |
| Portfolio review surface | `review_surface_ready`; unit test/domain audit은 이 명령에서 `not_run` |
| Calculation owner contract | typed stale freshness assessment focused 29개 PASS; benchmark refresh 미실행 |
| Runtime validation | Python 3.13 full unittest 1,472개 PASS; domain-term audit 217개 literal PASS |
| Publication validation | [validation.yml](.github/workflows/validation.yml)과 [project_status.md](docs/overview/project_status.md)를 기준으로 확인 |

현재 알려진 unit/contract correctness blocker는 없다. 별도 behavior fix
`b16a6c5`는 scope-rejected dependency의 late 재도입을 막았고, `c6f6fdf`는
terminal percent filter 뒤 unfiltered snapshot 재도입을 막았다. `5b44875`는 그
post-late finalization을 product behavior 변경 없이 state-free owner로 옮겼고,
별도 `8ebb239`는 필터 뒤 empty/partial coverage를 다시 계산한다. 그 뒤
`f0eafae`는 원문 표시값의 반복 stale repair를 막았고,
`2496fce`는 그 freshness assessment만 state-free execution owner로 옮겼다.
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

다음 구조 작업은 shared prepared-candidate/projection 경계를 characterization해
stale assessment 뒤 중복 formula execution을 제거할 수 있는지 검증하는 bounded
slice다. ledger synchronization은 별도 behavior contract로 분리하고, aggregate
precedence, 남은 deterministic/LLM fallback, private API mesh도 별도 follow-up으로
유지한다. 새 benchmark claim이 필요하면
현재 profile과 store signature를 먼저 확인하고 monitored store-fixed
`eval-only`로 갱신한다.

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
