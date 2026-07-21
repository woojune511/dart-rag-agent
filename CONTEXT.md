# 프로젝트 컨텍스트

> 새 세션에서 현재 상태를 2분 안에 파악하기 위한 snapshot이다. 현재 계약과
> 우선순위는 [project_status.md](docs/overview/project_status.md), 구조적 결정은
> [DECISIONS.md](DECISIONS.md)를 따른다. 구현 및 실험의 상세 연대기는 각각
> [implementation_history.md](docs/history/implementation_history.md)와
> [experiment_history.md](docs/history/experiment_history.md)에 있다.

Last updated: 2026-07-22

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

## 현재 검증 기준

| 항목 | 상태 |
| --- | --- |
| Expanded structural numeric gate | PASS, 9 / 9 |
| Plain-retrieval comparison | 5 / 9 diagnostic baseline |
| Portfolio review gates | READY |
| Reflection promotion gate | READY |
| Report-cache promotion evidence | READY, serving disabled |
| REFERENCE_NOTE capability | READY, Researcher context-only |
| Full unittest discovery | 1,352 passed after final reviewer walkthrough |

현재 active correctness blocker는 없다. 문서 및 artifact surface만 바꾸는
작업에는 fresh ingest나 benchmark refresh가 필요하지 않다.

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

다음 작업은 실제 blocker, 구체적인 caller 요구, 또는 특정 reviewer 설명
공백이 재현될 때만 연다.

지금은 broad runtime refactor, 전면적인 test-file 분할, 새 MAS 기능,
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
