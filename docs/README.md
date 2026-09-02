# Documentation Map

현재 규칙과 상태를 먼저 읽고, 과거 계획과 실행 로그는 필요한 근거를 찾을 때만
연다. 파일이 오래됐다는 이유만으로 삭제하지 않지만 historical 문서를 현재
work queue나 release evidence로 사용하지 않는다.

## Current Authority

| 문서 | 단일 책임 |
| --- | --- |
| [../AGENTS.md](../AGENTS.md) | 작업 방식, 빠른 개발 루프, 중단 조건 |
| [../CONTEXT.md](../CONTEXT.md) | 현재 checkout과 handoff snapshot |
| [overview/project_status.md](overview/project_status.md) | 현재 제품 경계, 검증 상태, blocker, 다음 작업 |
| [architecture/agent_runtime_contract.md](architecture/agent_runtime_contract.md) | normative runtime contract와 release gate |
| [overview/runtime_flow_roles.md](overview/runtime_flow_roles.md) | source에서 생성·검사되는 graph topology |
| [overview/codebase_map.md](overview/codebase_map.md) | 현재 code ownership과 실행 경로 |

구현 사실은 source와 tests로 다시 확인한다. 문서가 충돌하면 runtime behavior는
runtime contract와 source/tests를, 현재 상태와 다음 작업은 `project_status.md`를
우선한다. history, release note, portfolio 문서는 이 권위를 덮지 않는다.

## Developer Path

새 작업은 다음 순서로 시작한다.

1. `AGENTS.md`
2. `CONTEXT.md`
3. `project_status.md`
4. `git status`와 최근 commit
5. 변경할 경계의 contract·owner file·focused test

단계별 실행 기록을 current 문서에 누적하지 않는다. 검증된 현재 상태만 handoff와
status에 반영하고, chronology는 Git 또는 history 문서에서 찾는다.

## Reviewer Path

| 순서 | 문서 | 역할 |
| --- | --- | --- |
| 1 | [../README.md](../README.md) | 프로젝트 요약, 실행 명령, claim boundary |
| 2 | [overview/portfolio_one_pager.md](overview/portfolio_one_pager.md) | 짧은 포트폴리오 설명 |
| 3 | [overview/portfolio_experiment_report.md](overview/portfolio_experiment_report.md) | 기록된 실험 방법과 한계 |
| 4 | [overview/technical_highlights.md](overview/technical_highlights.md) | 주요 구현 surface |
| 5 | [overview/portfolio_demo_walkthrough.md](overview/portfolio_demo_walkthrough.md) | fixture-backed demo 검토 순서 |

포트폴리오 문서의 수치와 상태는 checkpoint-specific이다. 현재 release 상태는 항상
`project_status.md`에서 확인한다. 용어와 claim 수준은
[documentation_claim_boundaries.md](overview/documentation_claim_boundaries.md)를
따른다.

## Contract And Operations Reference

| 문서 | 역할 |
| --- | --- |
| [architecture/evidence_schema.md](architecture/evidence_schema.md) | evidence와 provenance schema |
| [architecture/retrieval_policy_schema.md](architecture/retrieval_policy_schema.md) | ontology·policy·runtime 경계 |
| [overview/question_trace_walkthrough.md](overview/question_trace_walkthrough.md) | 질문 하나의 runtime 흐름 |
| [evaluation/evaluation_metrics_v1.md](evaluation/evaluation_metrics_v1.md) | evaluator metric 정의 |
| [evaluation/benchmark_dataset_design.md](evaluation/benchmark_dataset_design.md) | curated dataset 설계 원칙 |
| [evaluation/numeric_regression_methodology.md](evaluation/numeric_regression_methodology.md) | numeric regression 분류 방법 |
| [evaluation/retrieval_trace_debugging.md](evaluation/retrieval_trace_debugging.md) | retrieval trace 진단 절차 |

`requirements-review.txt`는 fixture와 reviewer gate용 lightweight profile이고,
`requirements.txt`는 ingest, API, benchmark, full development profile이다.

## Historical And Checkpoint Material

| 문서 | 보존 목적 |
| --- | --- |
| [../PLAN.md](../PLAN.md) | 2026-06-11 이전 실행 계획 |
| [../DECISIONS.md](../DECISIONS.md) | append-only 설계 판단 기록 |
| [architecture/core_runtime_surface_refactoring_plan.md](architecture/core_runtime_surface_refactoring_plan.md) | 완료·대체된 단계별 refactoring 계획 |
| [architecture/current_runtime_cleanup_split_manifest.md](architecture/current_runtime_cleanup_split_manifest.md) | 이전 cleanup 분리 manifest |
| [planning/backlog_and_next_epics.md](planning/backlog_and_next_epics.md) | 과거 roadmap snapshot |
| [history/implementation_history.md](history/implementation_history.md) | 구현 연대기 |
| [history/experiment_history.md](history/experiment_history.md) | 실험 연대기 |
| [evaluation/benchmarking.md](evaluation/benchmarking.md) | benchmark guide와 누적 실행 로그 |
| [evaluation/runtime_contract_gate.md](evaluation/runtime_contract_gate.md) | 이전 runtime gate profile 기록 |
| [releases/v0.1.0-runtime-contract-ready.md](releases/v0.1.0-runtime-contract-ready.md) | 과거 release checkpoint |
| [releases/v0.2.0-portfolio-ready.md](releases/v0.2.0-portfolio-ready.md) | 과거 portfolio checkpoint |

## Maintenance Rules

- current authority 문서는 짧게 유지하고 날짜별 실행 일지를 붙이지 않는다.
- 동일한 사실은 한 current 문서에서만 소유한다. 다른 문서는 링크한다.
- 새 runtime 규칙은 runtime contract, 현재 gate와 다음 작업은 project status,
  checkout handoff는 context에만 기록한다.
- 과거 문서는 append-oriented로 보존하되 첫 화면에 `historical` 또는 checkpoint
  성격을 명시한다.
- provider-free, fixture, historical artifact 결과를 live/provider/release 증거로
  승격하지 않는다.
