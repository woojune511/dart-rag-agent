# 프로젝트 컨텍스트

> 이 문서는 **현재 상태만 짧게 유지하는 snapshot 문서**다.  
> 세션이 바뀌거나 기준선이 바뀌면 **덮어써서 최신 상태로 유지**한다.

역사적 실험 기록과 누적 판단은 [DECISIONS.md](DECISIONS.md)를 본다.  
남은 backlog와 다음 큰 구조 과제는 [docs/planning/backlog_and_next_epics.md](docs/planning/backlog_and_next_epics.md)를 본다.

## Current Snapshot

| 항목 | 현재 기준 |
| --- | --- |
| 프로젝트 정의 | DART 공시를 도메인으로 사용하는 **multi-agent financial analysis lab** |
| 현재 구현 핵심 | strong single-agent graph를 MAS worker들로 감싼 live E2E skeleton |
| 기준 문서 | `삼성전자 2024 사업보고서` |
| 기본 retrieval | `Chroma + BM25 + RRF`, structure-aware parser / chunking |
| 기본 analyst core | evidence-first math path, `formula planner + safe AST evaluator` |
| evaluator 역할 | final correctness / grounding과 retrieval diagnostic을 분리 |
| 현재 우선순위 | parser normalize/sanitize로 hidden structure recovery를 안정화한 뒤, MAS quality pass로 연결 |

## 현재 구현 단계

| 구성 | 상태 | 해석 |
| --- | --- | --- |
| Orchestrator | partial | real planner / merge node와 E2E smoke 완료 |
| Analyst | partial | `FinancialAgent.run()` wrapper migration + `report_scope` 반영 완료 |
| Researcher | partial | scoped narrative retrieval + summary + critic grounding smoke 완료 |
| Critic | partial | deterministic runtime critic live, LLM critic pending |
| Shared state ledger | live | `tasks`, `artifacts`, `evidence_pool`, `critic_reports`가 실제 흐름에서 사용 중 |
| Self-reflection | experimental | bounded retry checkpoint는 있으나 최종 MAS 설계는 아님 |
| Parser normalization | experimental | `local_heading` 구조 복원은 일부 성공, invalid XML-like markup sanitize는 미구현 |

## 최근 정량 증거

| 실험 | 핵심 변화 | 기록 위치 |
| --- | --- | --- |
| Evaluator support | false negative rate `12.5% -> 0.0%` | [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md) |
| Math architecture | strict correctness `0.556 -> 1.000` | [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md) |
| Ontology retrieval | calc success `0.333 -> 1.000` | [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md) |
| MAS Analyst smoke | numeric result parity `1.000`, calc status parity `1.000` | [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md) |
| MAS Researcher smoke | citation parity `1.000`, critic pass `1.000` | [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md) |
| MAS E2E smoke | final report 생성 `2/2`, critic-triggered retry `1/2` | [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md) |
| Parser structure smoke | `IV. 이사의 경영진단 및 분석의견` 하위 heading 복원 성공, `II > 7. 기타 참고사항` 후반부는 XML recover 손실 확인 | [benchmarks/results/naver_2023_structure_outline.json](benchmarks/results/naver_2023_structure_outline.json) |

## 고정 가능한 기준선

| 벤치셋 | 핵심 해석 | 현재 상태 |
| --- | --- | --- |
| `dev_math_focus` | analyst core의 numeric baseline | `Faithfulness 1.000`, `Completeness 1.000`, `Numeric Pass 1.000` |
| `dev_fast_focus_selective_serial` | broader sanity check | math-specialized evaluator 회귀 없음 |

## 해석 원칙

| 신호 | 무엇을 의미하나 | 현재 해석 |
| --- | --- | --- |
| `final answer correctness` | 최종 답이 질문에 맞는가 | 최우선 |
| `operand grounding` | 계산/답변에 쓴 숫자가 실제 읽은 텍스트에 있었는가 | 최종 numeric PASS의 핵심 |
| `retrieval_hit_at_k` | expected section hit 여부 | retriever diagnostic |
| `section_match_rate` | top-k purity / section alignment | retriever diagnostic |
| `context_precision_at_k` | retrieved context purity | retriever diagnostic |

> 현재 원칙은 **정답성 / grounding / retrieval diagnostic을 분리해서 본다**는 것이다.  
> 이 분리는 이후 MAS critic 설계의 출발점이기도 하다.

## 현재 아키텍처 전환 포인트

| 항목 | 현재 판단 |
| --- | --- |
| 기존 single-agent graph | 버릴 대상이 아니라 **Analyst / Researcher / Critic 자산으로 분해할 기반** |
| self-reflection rule patch | 최종 설계가 아니라 **agentic reflection 재설계를 위한 checkpoint** |
| `reference_note` phase 1a | 동작은 확인됐지만, 지금은 MAS roadmap 안의 capability로 재배치 |
| report-scoped cache | 장기 memory보다 먼저 설계해야 할 저장 계층 |
| XML-like source normalization | raw DART source를 수정하지 않고 parser 쪽 sanitize/normalize로 해결 |

## 다음 구조 과제

| 순서 | Phase | 목표 | 종료 조건 |
| --- | --- | --- | --- |
| 1 | MAS skeleton | shared state, task ledger, artifact schema 고정 | 완료: parallel workers + critic loop + merge live |
| 2 | Analyst migration | 현재 numeric/evidence path를 Analyst agent로 이식 | 완료: real store smoke 기준 numeric parity 확보 |
| 3 | Critic stack | deterministic critic + LLM critic 분리 | 진행 중: deterministic live, LLM critic 미구현 |
| 4 | Researcher attachment | why/context retrieval과 note traversal을 별도 agent로 분리 | 진행 중: v1 live, retrieval/summarization quality tuning 남음 |
| 5 | Parser normalize/sanitize layer | invalid XML-like markup를 흡수해 `local_heading`과 section subtree를 안정화 | NAVER `II > 7`의 `[클라우드]`, `(가) 영업 개요`까지 구조 복원 |
| 6 | Orchestrator quality pass | task decomposition / merge 품질 고도화 | mixed-intent baseline과 merge 품질 지표 확보 |
| 7 | Agentic self-reflection | retry를 rule patch가 아니라 ReflectionPlan/VerificationReport 구조로 재설계 | bounded retry가 task/critic contract 위에서 동작 |
| 8 | Cross-document / cross-company | entity/report/period namespace를 보존한 비교 분석 | 기업/문서 혼동 없는 multi-entity task 처리 |

## Non-blocking Quality Debt

다음 항목들은 **blocker가 아니라 backlog 성격의 품질 부채**로 본다.

| 항목 | 현재 판단 | 이유 |
| --- | --- | --- |
| `business_overview_001` | 급하지 않음 | 근거를 찾고 답도 맞지만 retrieval purity / packaging debt가 남음 |
| `risk_analysis_001` | 급하지 않음 | retrieval보다 selection / formatting 성격이 큼 |
| retrieval purity debt | backlog | top-k 잡음은 남아 있지만 정답성 자체를 깨지는 않음 |
| 일부 남은 duct tape | backlog | MAS role split 이후 정리하는 편이 안전 |

## 문서 역할

| 문서 | 역할 | 운영 원칙 |
| --- | --- | --- |
| [CONTEXT.md](CONTEXT.md) | 최신 상태 snapshot | 덮어써서 최신 상태 유지 |
| [PLAN.md](PLAN.md) | 현재 active plan | 바로 다음 구현 단계만 유지 |
| [DECISIONS.md](DECISIONS.md) | append-only 결정 로그 | 과거 판단과 근거 누적 |
| [docs/planning/backlog_and_next_epics.md](docs/planning/backlog_and_next_epics.md) | backlog / major epics | living backlog 유지 |
