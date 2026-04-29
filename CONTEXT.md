# 프로젝트 컨텍스트

> 이 문서는 **현재 상태만 짧게 유지하는 snapshot 문서**다.  
> 세션이 바뀌거나 기준선이 바뀌면 **덮어써서 최신 상태로 유지**한다.

역사적 실험 기록과 누적 판단은 [DECISIONS.md](DECISIONS.md)를 본다.  
남은 backlog와 다음 큰 구조 과제는 [docs/planning/backlog_and_next_epics.md](docs/planning/backlog_and_next_epics.md)를 본다.

## Current Snapshot

| 항목 | 현재 기준 |
| --- | --- |
| 기준 문서 | `삼성전자 2024 사업보고서` |
| 기본 retrieval | `Chroma + BM25 + RRF`, structure-aware parser / chunking |
| 기본 reasoning | evidence-first, math 질문은 `formula planner + safe AST evaluator` |
| math evaluator | `display-aware numeric equivalence`, `operand grounding` |
| retrieval metric 역할 | 최종 PASS/FAIL이 아니라 **diagnostic only** |
| 현재 baseline 상태 | `dev_math_focus`는 고정 가능, broader sanity check도 큰 회귀 없음 |
| 현재 우선순위 | local patch보다 **구조 확장** |

## 최근 정량 증거

| 실험 | 핵심 변화 | 기록 위치 |
| --- | --- | --- |
| Evaluator support | false negative rate `12.5% -> 0.0%` | [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md) |
| Math architecture | strict correctness `0.556 -> 1.000` | [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md) |
| Ontology retrieval | calc success `0.333 -> 1.000` | [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md) |

## 고정 가능한 기준선

| 벤치셋 | 핵심 해석 | 현재 상태 |
| --- | --- | --- |
| `dev_math_focus` | math 질문군 정답성 기준선 | `Faithfulness 1.000`, `Completeness 1.000`, `Numeric Pass 1.000` |
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

## Non-blocking Quality Debt

다음 항목들은 **blocker가 아니라 backlog 성격의 품질 부채**로 본다.

| 항목 | 현재 판단 | 이유 |
| --- | --- | --- |
| `business_overview_001` | 급하지 않음 | 근거를 찾고 답도 맞지만 retrieval purity / packaging debt가 남음 |
| `risk_analysis_001` | 급하지 않음 | retrieval보다 selection / formatting 성격이 큼 |
| retrieval purity debt | backlog | top-k 잡음은 남아 있지만 정답성 자체를 깨지는 않음 |
| 일부 남은 duct tape | backlog | 구조 확장 이후 정리하는 편이 안전 |

## 다음 구조 과제

| 순서 | Phase | 목표 | 종료 조건 |
| --- | --- | --- | --- |
| 1 | `REFERENCE_NOTE Phase 1a` | section-path reference graph edge 연결 | parser metadata 기록, expansion trace에 `reference_note` relation 노출, why 질문에서 표 수치와 참조 설명을 함께 사용 |
| 2 | `REFERENCE_NOTE Phase 1b` | `(주석 14 참조)`, `(*1)` 같은 numbered note reference 연결 | note number를 실제 target chunk로 resolve, 검색 없이 graph relation으로 병합 |
| 3 | 제한적 `self-reflection` | operand 부족 / source miss에 한해 1회 재검색 | `operand 누락 감지 -> 1회 재검색 -> 성공` 흐름이 로그에 남고 bounded retry 유지 |
| 4 | `cross-document / cross-company reasoning` | 기업/문서 경계를 보존한 비교 계산 | entity / report / period binding 혼동 없이 정답 도출 |

## 문서 역할

| 문서 | 역할 | 운영 원칙 |
| --- | --- | --- |
| [CONTEXT.md](CONTEXT.md) | 최신 상태 snapshot | 덮어써서 최신 상태 유지 |
| [PLAN.md](PLAN.md) | 현재 active plan | 바로 다음 실행 순서만 유지 |
| [DECISIONS.md](DECISIONS.md) | append-only 결정 로그 | 과거 판단과 근거 누적 |
| [docs/planning/backlog_and_next_epics.md](docs/planning/backlog_and_next_epics.md) | backlog / major epics | living backlog 유지 |
