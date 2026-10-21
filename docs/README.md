# 문서 지도

[프로젝트 홈](../README.md)에서 시작하고, 아래 네 경로 중 필요한 내용을 확인하세요.

## 처음 읽는 순서

| 경로 | 읽을 내용 |
| --- | --- |
| [사용 예시](overview/simple_rag_demo.md) | 설치 없이 저장된 질문·답변·인용 원문 확인 |
| [아키텍처와 설계 판단](overview/project_overview.md) | 파서·검색·답변 경로와 구현 파일, 선택의 근거 |
| [평가 결과와 한계](evaluation/README.md) | 77문항 전체 결과, 별도 비교 실험, 실패와 분모 구분 |
| [로컬 실행](operations/quickstart.md) | 오프라인 데모와 실제 API·Streamlit의 준비 조건 |

짧은 한·영 소개는 [Project Summary](overview/project_summary.md)에 있습니다.
개발 작업은 아래 authority 문서부터 확인합니다. 과거 계획과 실행 로그는 필요한
근거를 찾을 때 열며, historical 문서를 현재 작업 목록이나 release 근거로 쓰지 않습니다.

## Current Authority

| 문서 | 단일 책임 |
| --- | --- |
| [../AGENTS.md](../AGENTS.md) | 작업 방식, 빠른 개발 루프, 중단 조건 |
| [../CONTEXT.md](../CONTEXT.md) | 현재 checkout과 handoff snapshot |
| [overview/project_status.md](overview/project_status.md) | 현재 제품 경계, 검증 상태, blocker, 다음 작업 |
| [overview/portfolio_scope.md](overview/portfolio_scope.md) | 포트폴리오 범위, 삭제 근거, 기준선 비교와 완료 기준 |
| [architecture/agent_runtime_contract.md](architecture/agent_runtime_contract.md) | normative runtime contract와 release gate |
| [overview/runtime_flow_roles.md](overview/runtime_flow_roles.md) | source에서 생성·검사되는 graph topology |
| [overview/codebase_map.md](overview/codebase_map.md) | 현재 code ownership과 실행 경로 |

구현 사실은 source와 tests로 다시 확인한다. 문서가 충돌하면 runtime behavior는
runtime contract와 source/tests를, 현재 상태와 다음 작업은 `project_status.md`를
우선한다. history, release note, 소개 문서는 이 권위를 덮지 않는다.

## Developer Path

새 작업은 다음 순서로 시작한다.

1. `AGENTS.md`
2. `CONTEXT.md`
3. `project_status.md`
4. `git status`와 최근 commit
5. 변경할 경계의 contract·owner file·focused test

단계별 실행 기록을 current 문서에 누적하지 않는다. 검증된 현재 상태만 handoff와
status에 반영하고, chronology는 Git 또는 history 문서에서 찾는다.

## 상세 검토

최신 비교는 [검색 범위·생성 모델과 답변 품질](evaluation/rag_quality_progress_2026-10-21.md),
평가 정의는 [서술형 필수·선택 기준](evaluation/narrative_rubric_v1_2026-10-20.md),
초기 전체 결과는 [77문항 평가](evaluation/simple_rag_full77_result.md),
구조 효과는 [77문항 3조건 비교](evaluation/structure_full77_result.md),
제품 범위는 [portfolio scope](overview/portfolio_scope.md)에서 확인합니다.
각 보고서의 실행 시점·조건을 유지하며, 현재 소스에 대한 새 성능 측정으로 읽지 않습니다.

이전 [experiment report](overview/experiment_report.md),
[technical highlights](overview/technical_highlights.md),
[compiled fixture walkthrough](overview/demo_walkthrough.md)는 과거
Planner/Compiler 자료입니다. 현재 앱의 데모·품질 결과와 별개입니다.
[표현과 근거의 경계](overview/documentation_claim_boundaries.md)를 따릅니다.

## Contract And Operations Reference

The current application uses [simple RAG](architecture/agent_runtime_contract.md).
The former Planner/Compiler has a separate [comparison contract](architecture/compiled_workflow_contract.md);
its fixtures and older walkthroughs do not establish the default application's guarantees.

| 문서 | 역할 |
| --- | --- |
| [architecture/evidence_schema.md](architecture/evidence_schema.md) | evidence와 provenance schema |
| [architecture/retrieval_policy_schema.md](architecture/retrieval_policy_schema.md) | ontology·policy·runtime 경계 |
| [overview/question_trace_walkthrough.md](overview/question_trace_walkthrough.md) | 질문 하나의 runtime 흐름 |
| [evaluation/evaluation_metrics_v1.md](evaluation/evaluation_metrics_v1.md) | evaluator metric 정의 |
| [evaluation/benchmark_dataset_design.md](evaluation/benchmark_dataset_design.md) | curated dataset 설계 원칙 |
| [evaluation/numeric_regression_methodology.md](evaluation/numeric_regression_methodology.md) | numeric regression 분류 방법 |
| [evaluation/reviewed_case_evidence_status.md](evaluation/reviewed_case_evidence_status.md) | 기존 5문항의 live·fixture·exact replay 구분과 남은 근거 결함 |
| [evaluation/lge_t1_051_calculation_source_review_v2.md](evaluation/lge_t1_051_calculation_source_review_v2.md) | LG 원문 기간·행·출처 검토와 명시적 평가 successor |
| [evaluation/retrieval_trace_debugging.md](evaluation/retrieval_trace_debugging.md) | retrieval trace 진단 절차 |
| [operations/parser_store_successor.md](operations/parser_store_successor.md) | 원본 보존·동일 입력 벡터 재사용·새 parser 저장소 생성 절차 |

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
| [v0.2.0 검토 체크포인트](releases/v0.2.0-portfolio-ready.md) | 과거 검토 checkpoint |
| [releases/v0.3.0-runtime-contract-ready.md](releases/v0.3.0-runtime-contract-ready.md) | 현재 source-bundle/runtime 계약 checkpoint |

## Maintenance Rules

- current authority 문서는 짧게 유지하고 날짜별 실행 일지를 붙이지 않는다.
- 동일한 사실은 한 current 문서에서만 소유한다. 다른 문서는 링크한다.
- 새 runtime 규칙은 runtime contract, 현재 gate와 다음 작업은 project status,
  checkout handoff는 context에만 기록한다.
- 과거 문서는 append-oriented로 보존하되 첫 화면에 `historical` 또는 checkpoint
  성격을 명시한다.
- provider-free, fixture, historical artifact 결과를 live/provider/release 증거로
  승격하지 않는다.
