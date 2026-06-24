# Docs Index

`docs/`는 reviewer-facing 문서와 appendix/internal log를 분리해서 읽는다.
이 프로젝트는 단순 DART QA 앱보다 **DART 재무 공시 위에서
contract-driven Agentic RAG runtime을 설계/검증하는 프로젝트**로 보는 것이
맞다.

## Target Reader

포트폴리오/아키텍처 문서는 LLM, RAG, embedding retrieval, agent workflow,
grounding/evaluation에 익숙한 독자를 기준으로 한다. 입문 설명보다 다음을
우선한다.

- 어떤 financial-RAG failure mode를 다루는가
- 어떤 runtime state / artifact / trace가 그 문제를 표현하는가
- 어떤 gate나 실험이 claim을 검증하는가
- 어떤 기능은 아직 의도적으로 disabled 상태인가

용어와 claim boundary는
[overview/documentation_claim_boundaries.md](overview/documentation_claim_boundaries.md)를
따른다.

## Quick Review Path

리뷰어가 실제로 먼저 읽을 core path는 아래 5개면 충분하다. 면접에서 말로
설명할 compact talk track이나 이력서 문구는 reviewer path 바깥의 optional
deliverable로 둔다:
[overview/portfolio_interview_narrative.md](overview/portfolio_interview_narrative.md),
[overview/portfolio_resume_snippets.md](overview/portfolio_resume_snippets.md).

| 순서 | 문서 | 역할 |
| --- | --- | --- |
| 1 | [../README.md](../README.md) | 프로젝트 한 장 요약과 실행 가능한 reviewer commands |
| 2 | [overview/portfolio_one_pager.md](overview/portfolio_one_pager.md) | 문제, 방법, 현재 evidence를 가장 짧게 정리 |
| 3 | [overview/portfolio_experiment_report.md](overview/portfolio_experiment_report.md) | 실험 설계, 결과, 대표 failure analysis |
| 4 | [overview/technical_highlights.md](overview/technical_highlights.md) | 핵심 technical claims와 구현 surface |
| 5 | [overview/portfolio_demo_walkthrough.md](overview/portfolio_demo_walkthrough.md) | fixture-backed demo 출력과 검토 순서 |

발표가 필요하면
[overview/portfolio_presentation_outline.md](overview/portfolio_presentation_outline.md)를
추가로 본다.

## Dependency Profiles

- `requirements-review.txt`: reviewer-facing fixture/gate 명령용 lightweight
  profile. `portfolio_demo`, `portfolio_review_gates`, runtime domain-term audit
  같은 quick review path가 이 profile을 사용한다.
- `requirements.txt`: full development / ingest / benchmark / app profile.
  전체 테스트, fresh ingest, benchmark, Streamlit/API 실행처럼 무거운 경로에
  사용한다.

## Appendix

깊게 검토할 때 보는 문서다.

| 문서 | 역할 |
| --- | --- |
| [releases/v0.2.0-portfolio-ready.md](releases/v0.2.0-portfolio-ready.md) | 현재 포트폴리오 제출 기준 release checkpoint |
| [overview/codebase_map.md](overview/codebase_map.md) | 코드 ownership과 실행 경로 |
| [overview/question_trace_walkthrough.md](overview/question_trace_walkthrough.md) | 질문 하나가 runtime graph를 통과하는 흐름 |
| [architecture/agent_runtime_contract.md](architecture/agent_runtime_contract.md) | agent/task/artifact runtime contract |
| [architecture/architecture_direction.md](architecture/architecture_direction.md) | MAS topology와 장기 구조 방향 |
| [architecture/retrieval_policy_schema.md](architecture/retrieval_policy_schema.md) | retrieval policy / ontology / runtime keyword boundary |
| [architecture/evidence_schema.md](architecture/evidence_schema.md) | evidence object와 provenance schema |
| [evaluation/evaluation_metrics_v1.md](evaluation/evaluation_metrics_v1.md) | evaluator metric 정의 |
| [evaluation/evaluator_design_rationale.md](evaluation/evaluator_design_rationale.md) | numeric evaluator 분리 이유 |
| [evaluation/structural_trace_diagnostics.md](evaluation/structural_trace_diagnostics.md) | structural-vs-plain separating trace와 operand/row-binding 진단 |
| [evaluation/benchmark_dataset_design.md](evaluation/benchmark_dataset_design.md) | curated dataset track rationale |
| [evaluation/numeric_regression_methodology.md](evaluation/numeric_regression_methodology.md) | numeric benchmark failure를 일반 runtime fix로 닫는 운영 방법론 |
| [evaluation/runtime_contract_gate.md](evaluation/runtime_contract_gate.md) | runtime gate 운영 기록 |

## Internal Logs

아래 문서는 최신 handoff와 과거 실험을 보존하는 internal running log다. 리뷰어
first-read 문서가 아니며, 필요한 근거를 추적할 때만 본다.

| 문서 | 역할 |
| --- | --- |
| [../CONTEXT.md](../CONTEXT.md) | 최신 작업 상태 snapshot |
| [../PLAN.md](../PLAN.md) | active work와 다음 작업 |
| [../DECISIONS.md](../DECISIONS.md) | append-only 설계 판단 로그 |
| [overview/project_status.md](overview/project_status.md) | 긴 구현/gate 상태 로그 |
| [history/experiment_history.md](history/experiment_history.md) | 과거 실험 흐름 |
| [evaluation/benchmarking.md](evaluation/benchmarking.md) | benchmark 운영 상세 로그 |
| [planning/backlog_and_next_epics.md](planning/backlog_and_next_epics.md) | backlog와 future epics |

## Maintenance Rule

- reviewer-facing 문서는 짧게 유지한다.
- 긴 수치/실험 로그는 `project_status`, `experiment_history`,
  `benchmarking`에 남긴다.
- 새 claim을 README나 portfolio 문서에 넣기 전에 appendix/internal log에
  근거가 있는지 확인한다.
