# 실행 계획

> 이 문서는 **현재 active plan만 유지하는 실행 문서**다.  
> 끝난 실험이나 과거 단계는 여기 누적하지 않고 [DECISIONS.md](DECISIONS.md)로 보낸다.

## Active Snapshot

| 항목 | 현재 상태 |
| --- | --- |
| 현재 1순위 | **curated dataset을 benchmark/eval 경로에 연결하고, parser baseline regression을 질문 subset으로 확인** |
| 병렬 트랙 | retrospective scorecard는 1차 핵심 실험 완료, 이후 새 결정이 생길 때 추가 |
| 지금 하지 않을 것 | local patch deep dive, cosmetic retrieval tuning, evaluator gaming |
| 다음 큰 순서 | `dataset path migration -> parser regression check -> LLM critic -> orchestrator/researcher quality pass -> agentic self-reflection -> cross-company` |

## Immediate Focus Update

- curated dataset 연결과 parser baseline regression은 1차 기준선까지는 지나갔다.
- 현재 가장 가까운 구현 초점은 **semantic numeric planner + table-aware grounding** 이다.
  - ontology 기반으로 필요한 operand와 scope를 먼저 계획
  - retrieval 이후 reconciliation으로 부족 operand를 점검
  - parser가 만든 structured table row를 direct operand 경로로 소비
- 따라서 당장의 작업 순서는 아래처럼 본다.
  1. structured table grounding coverage 확대
  2. 더 많은 numeric question family에 대한 end-to-end 검증
  3. 그 다음 LLM critic / orchestrator / researcher quality pass

## 현재 목표

| 순서 | 구조 과제 | 현재 해석 |
| --- | --- | --- |
| 1 | MAS skeleton | 완료: parallel fan-out, critic loop, merge live |
| 2 | Analyst migration | 완료: report-scoped wrapper migration + real-store parity smoke |
| 3 | Curated dataset operationalization | 진행 중: `benchmarks/datasets/*curated.json`을 benchmark/profile/evaluator 경로에 연결 |
| 4 | Critic stack | 진행 중: deterministic critic live, LLM critic next |
| 5 | Researcher attachment | 진행 중: v1 retrieval/summary live, quality pass next |
| 6 | Parser simplify/normalize layer | 진행 중: baseline 안정화 거의 완료, regression 확인 단계 |
| 7 | Orchestrator quality pass | parser 안정화 이후 진행 |
| 8 | Agentic self-reflection | rule patch가 아닌 ReflectionPlan / VerificationReport |
| 9 | `cross-document / cross-company reasoning` | MAS contract 위에서 범위 확장 |

현재는 **개통된 MAS baseline 위에서 quality와 critic 계층을 고도화하는 것**이 1순위다.

## 병렬 트랙: Retrospective Scorecard

구조 전환과 별개로, 이미 내린 중요한 기술 결정이 정량적으로 어떤 차이를 만들었는지 남기는 **회고 실험 트랙**을 병렬로 운영한다.

### 운영 원칙

| 원칙 | 설명 |
| --- | --- |
| 새 기능 구현과 retrospective scorecard를 섞지 않음 | active implementation과 회고 실험을 분리 |
| scorecard는 포트폴리오 evidence track | 면접/README에서 쓸 수 있는 수치 근거 확보 |
| 시스템 실험과 evaluator 실험 분리 | architecture improvement와 evaluator fairness를 따로 해석 |
| 중요한 기술 결정은 실험 없이 닫지 않음 | baseline, proposed, metric, artifact가 정리되기 전에는 “채택 완료”로 기록하지 않음 |

### 완료된 1차 실험

| 순서 | 실험 |
| --- | --- |
| 1 | `Section Match Evaluator vs Operand Grounding Evaluator` |
| 2 | `Direct Calc vs Operation Path vs Formula Planner + AST` |
| 3 | `Standard Retrieval vs Ontology-Guided Retrieval` |
| 4 | `Evaluator sub-decision replay audit (Decisions 73 / 75 / 76)` |

정리 위치:
- 실험 설계와 scorecard 형식은 [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md)의 `Retrospective Scorecard Track`
- 완료된 결과는 같은 문서의 `Retrospective Results`

## Active Work

## Decision Gate

앞으로 **기술적으로 중요한 결정**은 아래 네 단계를 통과해야 닫는다.

| 단계 | 무엇을 남기나 |
| --- | --- |
| 1. 가설 정의 | 무엇을 왜 바꾸는지, 어떤 실패를 줄이려는지 |
| 2. 비교 설계 | `baseline`, `proposed`, 질문셋/벤치셋, 주요 metric |
| 3. 실행 artifact | `summary.md`, `summary.json`, 필요시 replay/debug trace |
| 4. 문서 반영 | `benchmarking.md` scorecard, `DECISIONS.md` 해석, 필요시 `technical_highlights.md` |

즉 앞으로는 **결정 -> 실험 -> 기록 -> 채택** 순서를 기본 운영 규칙으로 둔다.

### 0. Curated dataset operationalization

| 항목 | 내용 |
| --- | --- |
| 목표 | 사람이 검수한 curated dataset을 실제 benchmark/evaluator 기준선으로 승격 |
| 현재 자산 | `benchmarks/datasets/single_doc_eval_full.curated.json`, `benchmarks/datasets/multi_report_eval_full.curated.json` |
| 현재 문제 | 일부 benchmark profile / replay script가 아직 `benchmarks/eval_dataset.*` 계열 legacy dataset을 기본값으로 참조 |
| 다음 일 | profile별 `eval_dataset_path` 점검, benchmark runner / evaluator / replay script의 기본 dataset 경로 재정렬 |
| 종료 조건 | 주력 profile과 retrospective script가 curated dataset 또는 명시적 legacy dataset을 의도적으로 사용하도록 정리되고 혼용이 사라짐 |

### 1. MAS baseline stabilization

| 항목 | 내용 |
| --- | --- |
| 목표 | live `Orchestrator -> Analyst/Researcher -> Critic -> Merge`를 baseline으로 고정 |
| 핵심 산출물 | real store smoke, task decomposition trace, final report synthesis trace |
| 현재 상태 | E2E smoke 2문항 완료, critic-triggered analyst retry 1회 관측 |
| 다음 일 | mixed-intent task completion metric과 latency baseline 수집 |

### 2. Parser simplify/normalize layer

| 항목 | 내용 |
| --- | --- |
| 목표 | parser를 deep hierarchy 복원기가 아니라, high-value section 중심의 RAG-friendly chunker로 단순화 |
| 현재 관측 | sanitize + soft-heading baseline으로 `IV`와 `II > 7`의 핵심 hidden heading은 복원됐고, wide/narrative table split까지 붙으면서 oversized chunk가 사실상 해소됨 |
| 현재 산출물 | [src/ops/dump_report_structure.py](src/ops/dump_report_structure.py), [benchmarks/results/naver_2023_structure_outline.json](benchmarks/results/naver_2023_structure_outline.json) |
| 다음 일 | parser 질문 subset을 돌려 `expected_sections` hit rate와 numeric correctness 회귀가 없는지 확인하고, 필요시 low-value bracket/inline noise만 추가 정리 |
| 종료 조건 | `section_path` 중심 retrieval 품질은 유지하면서 `local_heading`이 soft metadata로 안정화되고, major sample 문서에서 oversized chunk가 재발하지 않음 |

### 3. LLM critic layer

| 항목 | 내용 |
| --- | --- |
| 목표 | deterministic critic 위에 scope/relevance/coherence를 보는 2층 critic 추가 |
| deterministic critic | 이미 live: grounding, basic format/unit, retry routing |
| LLM critic | 최종 task 산출물이 질문 의도에 맞는지, merge 전 artifact scope가 적절한지 평가 |
| 종료 조건 | `critic_reports`에 deterministic/LLM verdict가 함께 남고 retry 기준이 분리됨 |

### 4. Orchestrator / Researcher quality pass

| 항목 | 내용 |
| --- | --- |
| 목표 | task decomposition과 narrative retrieval/summarization의 품질을 E2E 기준으로 올림 |
| 현재 관측 | Researcher migration parity는 높지만 질문 의도 대비 답 품질 편차가 남음 |
| 우선 실험 | mixed-intent completion rate, final report relevance, artifact-level grounding 유지 |
| 종료 조건 | orchestrator plan / merge와 researcher v1의 baseline delta를 정량화 |

### 5. Agentic self-reflection

| 항목 | 내용 |
| --- | --- |
| 목표 | retry를 query string patch가 아니라 **ReflectionPlan -> deterministic execution -> VerificationReport** 구조로 재설계 |
| LLM 책임 | retry 필요성 판단, 문제 재정의, subquery reformulation, acceptance opinion |
| 코드 책임 | retrieval execution, merge/rerank, calculation, grounding, bounded control flow |
| baseline 원칙 | 초기 recovery 실험은 `reference_note OFF` 상태에서 시작해 retry 효과를 분리 측정 |
| 종료 조건 | bounded retry 1회 내에서 false recovery 없이 recovery artifact가 남음 |

### 6. `cross-document / cross-company reasoning`

| 항목 | 내용 |
| --- | --- |
| 선행 조건 | MAS skeleton과 critic stack 안정화 |
| 목표 | 기업/문서 경계를 보존한 multi-entity analysis |
| 핵심 요구 | `entity_id`, `report_id`, `period` namespace, 병렬 retrieval, report-scoped cache |
| 종료 조건 | multi-company ratio / comparison 질문을 binding 혼동 없이 처리 |

## Supporting Capabilities

아래는 메인 아키텍처가 아니라 **MAS 안으로 편입될 capability**로 다룬다.

| capability | 현재 판단 |
| --- | --- |
| `REFERENCE_NOTE Phase 1a` | wiring은 확인됐고, Researcher capability로 재배치 |
| `REFERENCE_NOTE Phase 1b` | numbered note가 필요해질 때 진행 |
| ontology 확장 | Analyst / Researcher query planning 입력으로 점진 편입 |
| report-scoped cache | MAS skeleton 이후 우선 구현 후보 |

## 지금 하지 않을 것

| 항목 | 이유 |
| --- | --- |
| `business_overview_001`, `risk_analysis_001` local patch deep dive | blocker가 아니라 quality debt |
| retrieval purity 점수만 올리기 위한 cosmetic tuning | MAS topology 정리보다 우선순위가 낮음 |
| rule-based self-reflection 분기 더 늘리기 | agentic redesign과 반대 방향 |

이들은 backlog로 남기고, 현재는 **agent boundary와 shared state를 먼저 고정**한다.

## 문서 사용 규칙

| 문서 | 역할 |
| --- | --- |
| [CONTEXT.md](CONTEXT.md) | 현재 상태 요약 |
| [DECISIONS.md](DECISIONS.md) | 누적 결정 로그 |
| [docs/planning/backlog_and_next_epics.md](docs/planning/backlog_and_next_epics.md) | backlog / future epics |
