# DART Multi-Agent Financial Analysis Lab

DART 전자공시 문서를 테스트베드로 삼아, **금융 문서용 multi-agent system**을 설계하고 검증하는 프로젝트입니다.  
단순한 “공시 QA 챗봇”보다, 아래 질문에 답하는 것이 현재 목표입니다.

- 어떤 **agent topology**가 재무 문서 분석에 적합한가
- agent 간 **communication contract**는 어떻게 설계해야 하는가
- 각 agent의 **role / tool boundary**는 어디까지가 좋은가
- **memory / cache / state update**는 어떤 계층으로 나눠야 하는가
- retrieval, calculation, critique를 어떻게 분리해야 **설명 가능성**과 **정확성**을 함께 가져갈 수 있는가

## 프로젝트 포지셔닝

| 항목 | 현재 정의 |
| --- | --- |
| 프로젝트 성격 | DART 도메인을 사용하는 **MAS 설계/검증 실험실** |
| 단기 목표 | working MAS skeleton을 E2E로 개통하고 worker/critic/orchestrator contract 고정 |
| 중기 목표 | LLM critic, researcher quality tuning, agentic reflection loop |
| 장기 목표 | cross-document / cross-company financial analysis |
| 현재 구현 상태 | real `Orchestrator + Analyst + Researcher + Critic` E2E smoke까지 연결 완료 |

## 목표 토폴로지

```text
User Query
  -> Orchestrator
      -> Analyst Agent   ----\
      -> Research Agent  -----+-> Critic Stack -> Orchestrator Merge -> Final Report
      -> Cache / Memory  -----/
```

### Agent 역할

| Agent | 역할 | 직접 하지 않을 일 |
| --- | --- | --- |
| Orchestrator | task decomposition, assignment, final merge | 직접 검색/계산 |
| Analyst | 수치 추출, formula planning, 계산 | 자유 서술형 맥락 요약 |
| Researcher | 비정형 텍스트 탐색, why/context 추출, note traversal | 수치 계산 확정 |
| Critic | grounding, binding, scope, completeness 검증 | 원문 검색 대행 |

### Communication 모델

이 프로젝트는 agent 간 자유 채팅보다 **task ledger + artifact store**를 지향합니다.

| 계층 | 용도 |
| --- | --- |
| `tasks` | 오케스트레이터가 분해한 작업 단위 |
| `task_results` | Analyst / Researcher가 제출한 구조화 결과 |
| `evidence_pool` | 검색된 근거, quote, source anchor |
| `critic_reports` | deterministic / LLM critic의 검증 결과 |
| `final_report` | 최종 사용자 응답 |

## Memory / Cache 철학

장기 메모리보다 먼저 **report-scoped cache**를 명확히 둡니다.

| 계층 | 정의 |
| --- | --- |
| Graph State | 한 번의 실행 중 공유되는 작업 상태 |
| Report-scoped cache | `company + report_type + rcept_no + year + metric` 기준 재사용 가능한 값 |
| Benchmark artifacts | 실험 재현성을 위한 결과 번들 |
| Long-term memory | 나중 단계. 현재는 우선순위 아님 |

## 현재 구현 자산

MAS 전체는 아직 구현 전이지만, 아래 자산은 이미 꽤 강합니다.

| 축 | 현재 자산 |
| --- | --- |
| Parser | DART 구조 보존 parser, section/table-aware chunking |
| Retrieval | dense + BM25 + RRF hybrid, metadata filter, parent-child expansion |
| Graph | document-structure expansion, `reference_note` phase 1a wiring |
| Analyst core | formula planner + safe AST calculator |
| Evaluation | operand grounding evaluator, display-aware equivalence, benchmark/replay infra |
| Experiment loop | benchmark runner, store-fixed eval-only, retrospective replay scripts |

## 현재 구현 상태

| 구성 | 상태 | 비고 |
| --- | --- | --- |
| Orchestrator | partial | real task planning / merge node와 E2E smoke 완료 |
| Analyst Agent | partial | existing `FinancialAgent.run()`을 MAS worker로 wrapper migration |
| Research Agent | partial | scoped semantic retrieval + LLM summary + grounding wiring |
| Critic Stack | partial | deterministic runtime critic live, LLM critic pending |
| Shared task ledger | live | `tasks`, `artifacts`, `evidence_pool`, `critic_reports` 사용 중 |
| Bounded reflection | experimental | single-agent graph 안의 checkpoint 구현, 최종 설계 아님 |

## 최근 정량 근거

| 결정 | baseline | proposed | 핵심 변화 |
| --- | --- | --- | --- |
| Evaluator support | section-hit support | operand grounding support | false negative rate `12.5% -> 0.0%` |
| Math architecture | direct calc | formula planner + AST | strict correctness `0.556 -> 1.000` |
| Ratio retrieval | standard retrieval | ontology-guided retrieval | calc success `0.333 -> 1.000` |
| Analyst migration | direct single-agent run | MAS Analyst wrapper | numeric result parity `1.000`, calc status parity `1.000` |
| Researcher migration | direct narrative core | MAS Researcher wrapper | citation parity `1.000`, critic pass `1.000` |
| MAS E2E | no integrated MAS baseline | real `Orchestrator + Workers + Critic + Merge` | final report 생성 `2/2`, critic-triggered retry 관측 `1/2` |

이 수치들은 “현재 single-agent 자산이 얼마나 강한가”를 보여주고, 이후 MAS 이식의 기준선 역할을 합니다.

## 현재 우선순위

1. live MAS E2E baseline 위에서 **Orchestrator / Researcher 품질**과 task decomposition 품질을 측정
2. deterministic critic 위에 **LLM critic layer**를 추가
3. bounded self-reflection을 **rule patch**가 아니라 **agentic reformulation behavior**로 재설계
4. 그 이후 `reference_note`, cross-company, report-scoped cache를 MAS capability로 편입

즉 다음 단계의 초점은 “점수 잘 나오는 단일 파이프라인”이 아니라,  
**설명 가능한 multi-agent topology로 재구성하는 것**입니다.

## 문서 읽는 순서

| 순서 | 문서 | 용도 |
| --- | --- | --- |
| 1 | [docs/overview/technical_highlights.md](docs/overview/technical_highlights.md) | 포트폴리오용 기술 요약 |
| 2 | [docs/architecture/architecture_direction.md](docs/architecture/architecture_direction.md) | MAS 방향성과 agent/tool/memory 설계 |
| 3 | [CONTEXT.md](CONTEXT.md) | 현재 snapshot |
| 4 | [PLAN.md](PLAN.md) | active implementation plan |
| 5 | [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md) | benchmark 운영 기준 + retrospective scorecard |
| 6 | [DECISIONS.md](DECISIONS.md) | append-only 설계 판단 로그 |

## 프로젝트 구조

```text
src/
  ingestion/      DART 수집
  processing/     DART XML 파싱 및 청킹
  storage/        ChromaDB / BM25 / parent store
  agent/          LangGraph 기반 분석 로직
  api/            FastAPI 라우터
  ops/            evaluator / benchmark runner / replay tools
benchmarks/
  profiles/
  results/
docs/
  overview/
  architecture/
  evaluation/
  planning/
  history/
app.py            Streamlit UI
main.py           FastAPI entrypoint
```

## 실행

환경 준비:

```bash
uv venv .venv
.venv\Scripts\activate
uv pip install -r requirements.txt
```

`.env`:

```text
GOOGLE_API_KEY=...
DART_API_KEY=...
```

Streamlit:

```bash
streamlit run app.py
```

FastAPI:

```bash
uvicorn main:app --reload --port 8000
```

## Benchmark 실행

기본 screening:

```bash
python -m src.ops.benchmark_runner --config benchmarks/profiles/dev_fast.json
```

math 기준선:

```bash
python -m src.ops.benchmark_runner --config benchmarks/profiles/dev_math_focus.json
```

store-fixed end-to-end 빠른 회귀:

```bash
python -m src.ops.run_eval_only --config benchmarks/profiles/dev_math_focus.json --source-output-dir benchmarks/results/dev_math_focus_llmshift_2026-04-28 --output-dir benchmarks/results/dev_math_focus_evalonly_example --company-run-id samsung_2024
```

이 경로는 **기존 store를 재사용해 current agent/evaluator를 다시 실행**하는 방식입니다.  
같은 historical answer를 대상으로 evaluator만 비교하려면 retrospective replay 스크립트를 사용해야 합니다.

## 참고 문서

- [docs/architecture/architecture_direction.md](docs/architecture/architecture_direction.md): MAS 방향성과 설계 원칙
- [docs/overview/technical_highlights.md](docs/overview/technical_highlights.md): 포트폴리오용 핵심 기술 포인트
- [CONTEXT.md](CONTEXT.md): 현재 상태와 handoff 메모
- [PLAN.md](PLAN.md): active implementation plan
- [DECISIONS.md](DECISIONS.md): 중요한 설계 판단과 근거
- [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md): benchmark 구조와 metric 해석
- [docs/history/experiment_history.md](docs/history/experiment_history.md): 버전별 코드/실험 변화와 해석
