# 프로젝트 컨텍스트

> 새 세션에서 현재 상태를 2분 안에 파악하기 위한 handoff다. 현재 제품 상태,
> 검증, blocker와 우선순위의 단일 기준은
> [project_status.md](docs/overview/project_status.md)다. 세부 runtime 동작은
> [agent_runtime_contract.md](docs/architecture/agent_runtime_contract.md), 완료된 변경은
> [implementation_history.md](docs/history/implementation_history.md)를 따른다.

Last updated: 2026-08-14

## 현재 범위

- 제품은 DART 공시를 분석하는 single-agent `FinancialAgent`다.
- 핵심 흐름은 구조 보존 ingest, dense/BM25 hybrid retrieval, LLM semantic
  planning, deterministic calculation, evidence/provenance validation이다.
- MAS, report-cache promotion, evaluator, benchmark runner와 review workflow는
  optional 또는 experimental surface다.
- 범용 agent, broad web workflow, productivity-tool 확장은 현재 범위가 아니다.

## 현재 checkpoint

| 항목 | 현재 상태 |
| --- | --- |
| Source checkpoint | local code checkpoint `80a37f8` on `codex/finalize-five-minute-review`; 이 handoff 문서 commit과 이후 변경은 `git log`로 확인 |
| Public numeric contract | `resolved_calculation_trace`, explicit `structured_result`, task/artifact projection |
| Default runtime boundary | MAS/eval/benchmark/promotion/cache 구현은 unconfigured import/invocation에서 격리 |
| Calculation ownership | graph-state orchestrator와 state-free owner들로 분리 중; runtime/ontology deterministic planning은 `financial_calculation_execution.py`, semantic-planner scope/shape/segment/task validation과 narrative-task policy projection은 `financial_graph_helpers.py`, candidate surface/segment/metadata policy projection은 `financial_surface_contracts.py`, row text·aggregate-like row stage/role·segment-local/segment-metric composition은 `financial_row_surfaces.py`, aggregate calculation/public projection·bounded repair·quantitative-impact parsing/composition은 `financial_aggregate_projection.py`, read-only focus/section/compression hint projection은 `financial_retrieval_hints.py`, collapsed-ratio evidence repair는 `financial_runtime_trace.py`, direct structured lookup과 lookup answer-slot/support projection은 `financial_lookup_recovery.py`, nested result projection은 `financial_answer_projection.py`, query-focus/source-visible text projection은 `financial_text_surface.py`, caller-facing run projection은 `financial_agent_run_projection.py`, prepared candidate와 structured period-pair projection은 `financial_reconciliation_candidates.py`, reflection retry-query projection은 `financial_reflection_projection.py`에 귀속 |
| Phase 3 | OPEN; generic operand-period/structured-cell, candidate report/period-scope, candidate surface-contract/segment-binding, candidate metadata-policy, segment-local/segment-metric과 aggregate-like row stage/role ownership까지 수렴했지만 broader alignment/rebuild와 ledger ownership 전체는 미완료 |
| Runtime correctness | 알려진 unit/contract blocker 없음; 최신 수치는 [Current Gate Status](docs/overview/project_status.md#current-gate-status) 참조 |
| Benchmark | 최신 코드에 대한 refresh 상태는 [Project Status](docs/overview/project_status.md#current-gate-status)만 기준으로 사용 |

## 남은 Phase 3 범위

세부 우선순위는 [Next Work](docs/overview/project_status.md#next-work)가 단일 기준이다.
현재 durable debt는 다음 네 범주다.

1. 일부 진행된 aggregate repair/precedence decision; period/material/source/
   coherence/rank/dedupe, narrative-validation policy, row-focus, growth display/material,
   result support/reuse, prepared material inspection/rendering, growth trace inspection,
   bounded aggregate row/gap/lookup-answer surface, final-answer evidence/provenance/operand
   projection, aggregate calculation/public projection, subtask upsert/rank,
   nested traversal/scoring/selected-result promotion과
   growth-answer numeric completion/sanitization과 deterministic quantitative-
   impact parsing/composition은 state-free owner로 이동했으며
   bounded nested-result replacement와 arithmetic surface sync까지 이동했으며
   broader alignment/rebuild/final sequencing은 graph에 유지
2. 일부 진행된 dependency 및 ratio/absolute seam; ratio presentation/readiness/
   scale, bounded operand preparation, lookup magnitude, same-block unit/table repair,
   direct structured lookup-row/value projection, dependency input
   matching/binding policy, deterministic runtime/ontology planning, semantic-
   planner scope/shape/segment/task validation, narrative-task policy와
   lookup answer-slot/support projection, generic operand-period, structured-cell
   selection/scoring, candidate report/period-scope, candidate surface-contract/
   segment-binding, candidate metadata-policy, segment-local/segment-metric과
   aggregate-like row stage/role ownership은 이동했고 graph-state lookup,
   broader evidence orchestration과 주변 sequencing은 제외
3. bounded read-only reconciliation artifact-reference projection까지만 진행된 broader
   task/artifact ledger synchronization; artifact mutation과 whole-ledger sync는 제외
4. public contract 이동과 함께 일부 진행된 private API/test mesh

이 목록은 총 작업량이나 정해진 slice 수를 의미하지 않는다. 완료된 owner 이동은
behavior·accuracy·performance 개선이나 Phase 3 완료를 뜻하지 않는다.
`d1305f8`의 7/15줄 segment-local/segment-metric pair에 이어 `80a37f8`에서
정확한 10/2줄 aggregate-like row stage/role pair도
`financial_row_surfaces.py`로 이동했다. Candidate value-role/stage 16/18줄과
direct/ratio acceptance, matching/scoring은 graph에 남는다. 다음 production
이동은 아직 선택하지 않았으며 lookup-hint projection 5/14/7/5줄 경계의
characterize-only inventory가 [Next Work](docs/overview/project_status.md#next-work)의
단일 우선순위다.

## 구현 원칙

- benchmark 질문, 회사명과 metric-specific phrase를 runtime branch에 넣지 않는다.
- 금융 domain vocabulary는 ontology, retrieval policy, config 또는 documented data
  artifact에 둔다.
- LLM은 intent와 semantics를 판단하고, 산술·unit conversion·dependency binding·
  dedupe·validation은 deterministic code가 담당한다.
- answer composer는 evidence에 없는 claim을 만들지 않는다.
- parser/ingest/cache signature가 바뀌지 않으면 store-fixed `eval-only`를 fresh
  ingest보다 우선한다.
- `src/agent` 또는 `src/routing` 변경은 broader tests 전에
  `python -m src.ops.audit_runtime_domain_terms`를 실행한다.
- benchmark/store/cache/heartbeat output은 명시적 승인 없이는 stage하지 않는다.

## 새 세션 시작 순서

1. `AGENTS.md`
2. 이 문서
3. [project_status.md](docs/overview/project_status.md)
4. `git status -sb`
5. `git log -5 --oneline`
6. 선택된 batch가 있으면 관련 runtime contract와 focused test

ChatGPT/Codex memory는 사용자 선호와 반복 작업 습관만 보조한다. 최신 commit,
blocker, benchmark, API/model 상태와 artifact 위치는 repo 문서와 Git을 우선한다.

## 문서 지도

| 필요한 정보 | 권위 문서 |
| --- | --- |
| 현재 제품·gate·blocker·우선순위 | [project_status.md](docs/overview/project_status.md) |
| runtime behavior contract | [agent_runtime_contract.md](docs/architecture/agent_runtime_contract.md) |
| 실행 topology와 owner 역할 | [runtime_flow_roles.md](docs/overview/runtime_flow_roles.md) |
| Phase debt와 stop line | [core_runtime_surface_refactoring_plan.md](docs/architecture/core_runtime_surface_refactoring_plan.md) |
| 구현 연대기와 commit별 수치 | [implementation_history.md](docs/history/implementation_history.md) |
| benchmark와 실험 연대기 | [experiment_history.md](docs/history/experiment_history.md) |
| 장기 backlog | [backlog_and_next_epics.md](docs/planning/backlog_and_next_epics.md) |

이 축약 이전 snapshot은 Git의 `1897fd1^:CONTEXT.md`에서 확인할 수 있다.
