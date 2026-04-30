# Docs Index

`docs/`는 역할별로 나눠 관리한다.

현재 이 저장소는 단순한 DART QA 앱보다 **DART 도메인 위에서 multi-agent financial analysis system을 설계/검증하는 프로젝트**로 읽는 것이 맞다.

## 읽는 순서

| 순서 | 문서 | 용도 |
| --- | --- | --- |
| 1 | [overview/technical_highlights.md](overview/technical_highlights.md) | 포트폴리오용 핵심 기술 요약 |
| 2 | [architecture/architecture_direction.md](architecture/architecture_direction.md) | MAS 방향성과 topology / communication / memory 설계 |
| 3 | [../CONTEXT.md](../CONTEXT.md) | 현재 기준 상태 snapshot |
| 4 | [../PLAN.md](../PLAN.md) | 현재 active work |
| 5 | [evaluation/benchmarking.md](evaluation/benchmarking.md) | benchmark 운영 기준 + retrospective scorecard |
| 6 | [../DECISIONS.md](../DECISIONS.md) | append-only 설계 판단 로그 |

## 폴더 역할

### `overview/`
- 프로젝트를 빠르게 설명할 때 먼저 보는 요약 문서

### `architecture/`
- 현재 아키텍처 설계, schema, routing, numeric reasoning 관련 문서

### `evaluation/`
- benchmark 운영 방식, 단일 문서 평가 기준, metric spec
- retrospective scorecard 실험 설계는 `evaluation/benchmarking.md` 안에서 함께 관리

### `planning/`
- backlog, next epics, 향후 구조 과제

### `history/`
- 과거 실험 흐름, 회고성 refactor plan, 버전별 변화 기록

## Source Of Truth

| 질문 | 먼저 볼 문서 |
| --- | --- |
| 이 프로젝트를 어떤 시스템으로 봐야 하나? | [architecture/architecture_direction.md](architecture/architecture_direction.md) |
| 지금 시스템 상태가 어떤가? | [../CONTEXT.md](../CONTEXT.md) |
| 지금 무엇을 구현 중인가? | [../PLAN.md](../PLAN.md) |
| 왜 이런 구조를 택했나? | [../DECISIONS.md](../DECISIONS.md) |
| benchmark를 어떻게 돌리고 해석하나? | [evaluation/benchmarking.md](evaluation/benchmarking.md) |
| metric 정의는 무엇인가? | [evaluation/evaluation_metrics_v1.md](evaluation/evaluation_metrics_v1.md) |
| 과거 실험은 어떻게 흘러왔나? | [history/experiment_history.md](history/experiment_history.md) |

## 문서 성격 구분

- 최신 상태를 유지하는 문서:
  - [../CONTEXT.md](../CONTEXT.md)
  - [../PLAN.md](../PLAN.md)
  - [planning/backlog_and_next_epics.md](planning/backlog_and_next_epics.md)
- 누적 기록 문서:
  - [../DECISIONS.md](../DECISIONS.md)
  - [history/experiment_history.md](history/experiment_history.md)
- 설계 / 기준 문서:
  - `architecture/`
  - `evaluation/`

## 현재 문서 읽기 관점

| 관점 | 먼저 볼 문서 |
| --- | --- |
| MAS topology / role / memory 설계 | [architecture/architecture_direction.md](architecture/architecture_direction.md) |
| 현재 구현 상태 | [../CONTEXT.md](../CONTEXT.md) |
| 현재 구현 우선순위 | [../PLAN.md](../PLAN.md) |
| 왜 이런 방향으로 바뀌었는가 | [../DECISIONS.md](../DECISIONS.md) |
