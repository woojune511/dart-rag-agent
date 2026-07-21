# Codebase Map

이 문서는 이 저장소를 **아주 큰 단위부터 세세한 함수 단위까지** 내려가며 파악할 수 있게 만드는 안내서다.

목표는 두 가지다.

1. 지금 실제로 돌아가는 코드와 실험/평가용 코드를 분리해서 본다.
2. 파일을 나열해서 읽는 대신, **실행 경로**와 **책임 경계** 기준으로 내려간다.

대표 질문 1개를 끝까지 추적한 예시는 [Question Trace Walkthrough](question_trace_walkthrough.md)를 같이 보면 된다.
핵심 class/function 역할을 실행 흐름 중심으로 압축한 문서는
[Runtime Flow And Roles](runtime_flow_roles.md)를 보면 된다.

---

## 1. 먼저 알아야 할 사실

이 레포가 복잡하게 느껴지는 이유는 “코드가 많아서”보다 아래 세 축이 한 저장소 안에 같이 있기 때문이다.

- **실서비스 경로**: FastAPI, ingest, query, single-agent runtime
- **MAS 실험 경로**: orchestrator / analyst / researcher / critic skeleton
- **평가/실험 경로**: benchmark runner, evaluator, replay, retrospective analysis

이 세 축을 처음부터 섞어 읽으면 구조가 잘 안 잡힌다.

---

## 2. 가장 큰 그림

### 현재 실제 서비스 요청 경로

```text
HTTP request
  -> main.py
  -> src/api/financial_router.py
  -> FinancialAgent
  -> parser / vector store / router / graph nodes
  -> final answer / citations / structured_result
```

### MAS 실험 경로

```text
original_query
  -> Orchestrator plan
  -> Analyst / Researcher
  -> Critic
  -> Orchestrator merge
  -> final_report
```

### 평가 경로

```text
benchmark profile
  -> benchmark_runner
  -> ingest / agent run / evaluator
  -> results.json / summary.md / review.md
```

---

## 3. 어디부터 읽어야 하는가

추천 순서는 아래다.

| 순서 | 파일 | 왜 먼저 보는가 |
| --- | --- | --- |
| 1 | [README.md](../../README.md) | 프로젝트 목적, 현재 포지셔닝 |
| 2 | [CONTEXT.md](../../CONTEXT.md) | 현재 snapshot |
| 3 | [PLAN.md](../../PLAN.md) | 지금 진행 중인 축 |
| 4 | [main.py](../../main.py) | 서비스 진입점 |
| 5 | [src/api/financial_router.py](../../src/api/financial_router.py) | API가 실제 엔진을 어떻게 호출하는지 |
| 6 | [src/agent/financial_graph.py](../../src/agent/financial_graph.py) | single-agent 핵심 graph wiring |
| 7 | `financial_graph_*` mixin 파일들 | phase별 실제 구현 |
| 8 | [src/processing/financial_parser.py](../../src/processing/financial_parser.py) | 문서가 chunk로 바뀌는 방식 |
| 9 | [src/storage/vector_store.py](../../src/storage/vector_store.py) | retrieval 저장/조회 구조 |
| 10 | [src/routing/query_router.py](../../src/routing/query_router.py) | 질문 intent routing |
| 11 | [src/agent/mas_graph.py](../../src/agent/mas_graph.py) | MAS skeleton wiring |
| 12 | [src/ops/benchmark_runner.py](../../src/ops/benchmark_runner.py) | 평가/실험 orchestration |
| 13 | `tests/` | 실행 계약을 테스트 관점에서 확인 |

---

## 4. 디렉터리 지도로 보기

| 경로 | 역할 |
| --- | --- |
| `src/api/` | FastAPI 엔드포인트 |
| `src/ingestion/` | DART 원문 수집 |
| `src/processing/` | XML/PDF 파싱, chunk 생성, 구조 복원 |
| `src/storage/` | Chroma + BM25 + metadata filtering + embedding runtime |
| `src/routing/` | 질문 의도 분류, format preference, semantic/LLM fallback |
| `src/agent/` | 실제 분석 런타임과 MAS skeleton |
| `src/agent/nodes/` | MAS worker / orchestrator / critic adapters |
| `src/config/` | runtime contract, retrieval policy, ontology |
| `src/ops/` | benchmark, evaluator, replay, debug 도구 |
| `src/schema/` | parser가 사용하는 table/value schema |
| `src/utils/` | LLM/embedding usage tracking |
| `benchmarks/profiles/` | 실험 설정 |
| `benchmarks/datasets/` | 평가 질문셋 |
| `benchmarks/results/` | 실험 산출물 |
| `tests/` | 모듈별 실행 계약 확인 |
| `docs/` | 방향, 평가 기준, 설계 문서 |

---

## 5. “지금 실제 엔진”은 어디인가

처음 파악할 때 가장 중요한 기준은 아래다.

- **실제 서비스 엔진**은 `FinancialAgent` 중심이다.
- **MAS skeleton**은 `FinancialAgent`를 감싸거나 병렬화하려는 실험 축이다.
- **benchmark runner**는 실서비스 엔진과 MAS 실험 축을 검증하는 외부 orchestrator다.

즉, 현재 코드베이스를 이해하는 1순위는 아래다.

- [src/agent/financial_graph.py](../../src/agent/financial_graph.py)
- [src/agent/financial_graph_models.py](../../src/agent/financial_graph_models.py)
- `src/agent/financial_graph_planning.py`
- `src/agent/financial_graph_contextual.py`
- `src/agent/financial_retrieval_pipeline.py`
- `src/agent/financial_graph_evidence.py`
- `src/agent/financial_graph_calculation.py`
- `src/agent/financial_graph_reconciliation.py`

---

## 6. 실제 서비스 골든 패스

질문 하나가 어떻게 흘러가는지 큰 순서만 보면 아래다.

### A. API query path

1. [main.py](../../main.py) 에서 FastAPI 앱이 뜬다.
2. [src/api/financial_router.py](../../src/api/financial_router.py) 의 `POST /api/query`가 요청을 받는다.
3. router는 `FinancialAgent.run(question)`을 호출한다.
4. [src/agent/financial_graph.py](../../src/agent/financial_graph.py) 의 `_build_graph()` 순서대로 LangGraph가 돈다.
5. 최종적으로 `answer`, `citations`, `structured_result`, `resolved_calculation_trace`가 응답으로 나온다.

### B. FinancialAgent graph order

`_build_graph()` 기준 canonical order:

```text
classify
-> extract
-> pre_calc_planner
-> retrieve
-> expand
-> (numeric_extractor | evidence)
-> reconcile_plan
-> operand_extractor
-> formula_planner
-> calculator
-> calc_render
-> calc_verify
-> advance_subtask
-> aggregate_subtasks
-> compress
-> validate
-> cite
```

중요한 점은 이 graph가 단순 linear가 아니라, 계산 실패 시 `reflection_replan` / `prepare_retry`를 거쳐 retrieval로 다시 돌아갈 수 있다는 점이다.

---

## 7. Ingest 골든 패스

문서 적재는 아래 경로로 이해하면 된다.

1. [src/api/financial_router.py](../../src/api/financial_router.py) 의 `POST /api/ingest`
2. `DARTFetcher.fetch_company_reports(...)`
3. `FinancialParser.process_document(...)`
4. `FinancialAgent.contextual_ingest(...)`
5. `VectorStoreManager`에 vector + BM25 + metadata 저장

여기서 핵심은:

- 수집은 `ingestion`
- 구조 복원과 청킹은 `processing`
- 저장과 retrieval은 `storage`
- contextual ingest 규칙은 `agent` mixin

---

## 8. MAS 골든 패스

MAS 쪽은 실서비스 기본 경로와 별개로 이해하는 게 낫다.

### 핵심 파일

- [src/agent/mas_graph.py](../../src/agent/mas_graph.py)
- [src/agent/mas_types.py](../../src/agent/mas_types.py)
- [src/agent/nodes/orchestrator_node.py](../../src/agent/nodes/orchestrator_node.py)
- [src/agent/nodes/analyst_node.py](../../src/agent/nodes/analyst_node.py)
- [src/agent/nodes/researcher_node.py](../../src/agent/nodes/researcher_node.py)
- [src/agent/nodes/critic_node.py](../../src/agent/nodes/critic_node.py)

### 실행 개념

```text
original_query
-> Orchestrator_Plan
-> Analyst / Researcher
-> Critic
-> retry if rejected
-> Orchestrator_Merge
-> final_report
```

여기서 Analyst는 기존 `FinancialAgent`를 wrapper로 감싼 adapter에 가깝다.  
즉 MAS를 이해하려면 먼저 single-agent를 이해해야 한다.

---

## 9. 상태와 계약을 먼저 봐야 하는 파일

함수보다 먼저 봐야 하는 것은 “상태 객체”다.

| 파일 | 왜 중요한가 |
| --- | --- |
| [src/agent/financial_graph_models.py](../../src/agent/financial_graph_models.py) | single-agent state와 structured output schema |
| [src/agent/mas_types.py](../../src/agent/mas_types.py) | MAS task/artifact/evidence ledger schema |
| [src/config/runtime_contract.py](../../src/config/runtime_contract.py) | runtime contract |
| [docs/architecture/agent_runtime_contract.md](../architecture/agent_runtime_contract.md) | 구현 단위 계약 해설 |

읽을 때는 먼저 `TypedDict`와 `BaseModel` 이름만 훑고, 그 다음 실제 graph에서 어떤 필드가 자주 쓰이는지만 보라.

---

## 10. 함수 단위로 내려가는 방법

함수를 처음부터 읽지 말고 아래 순서를 고정한다.

1. **entrypoint**를 본다.
2. **state shape**를 본다.
3. **graph wiring**을 본다.
4. **node body**를 본다.
5. 마지막에 **helper**를 본다.

이 레포에 적용하면:

1. `main.py`
2. `financial_router.py`
3. `financial_graph_models.py`
4. `financial_graph.py::_build_graph`
5. 각 mixin의 `_classify_query`, `_retrieve`, `_extract_evidence`, `_plan_formula_calculation`, `_execute_calculation` 등
6. `financial_graph_helpers.py`

---

## 11. 큰 파일을 읽는 실전 요령

### `financial_graph.py`

이 파일은 “구현 세부”보다 **wiring 파일**로 읽는다.

- `_build_llm_routes()`는 모델 선택
- `_build_graph()`는 실행 순서
- `run()`은 초기 상태와 결과 정규화

즉 여기서는 “무슨 노드가 있나”와 “어떻게 분기되나”만 보면 된다.

### `financial_parser.py`

이 파일은 parser 자체가 아니라 “원문 구조 보존기”로 읽어야 한다.

처음엔 아래 네 가지만 본다.

- `DocumentChunk`
- heading/path 보정 함수군
- table/value semantic 추출 함수군
- `FinancialParser` 클래스

### `vector_store.py`

처음엔 아래만 본다.

- embedding provider 선택
- metadata sanitize
- `VectorStoreManager`

BM25 fallback, cache, transient error 처리까지 한 번에 이해하려고 하면 피곤하다. 먼저 저장/조회 인터페이스만 잡는다.

### `benchmark_runner.py`

이 파일은 초반엔 전부 읽지 않는다. 아래 세 함수만 중심에 둔다.

- `run_screening_experiment`
- `_run_company_bundle`
- `main`

나머지는 실험 지원용 helper가 많다.

---

## 12. 처음부터 보면 안 되는 곳

아래는 초반에 보면 오히려 구조 파악을 방해하는 곳이다.

- `benchmarks/results/` 전체
- `src/ops/benchmark_runner.py`의 helper 세부
- `tests/` 전체를 처음부터 순서대로 읽기
- `financial_graph_helpers.py`를 먼저 읽기

이 영역은 핵심 흐름을 잡은 뒤에 보는 게 맞다.

---

## 13. 추천하는 실제 파악 루틴

### 1회차: 30~40분

- README
- main.py
- financial_router.py
- financial_graph.py

목표: “질문이 어디로 들어와서 어디로 끝나는가”만 안다.

### 2회차: 60분

- financial_graph_models.py
- planning/contextual/evidence/calculation/reconciliation mixin

목표: “single-agent가 어떤 단계로 답을 만든다”를 안다.

### 3회차: 40분

- financial_parser.py
- vector_store.py
- query_router.py

목표: “문서가 어떻게 쪼개지고, 어떻게 검색되며, 질문이 어떻게 분류되는가”를 안다.

### 4회차: 40분

- mas_graph.py
- mas_types.py
- nodes/*

목표: “single-agent 자산을 MAS로 어떻게 감쌌는가”를 안다.

### 5회차: 필요할 때만

- benchmark_runner.py
- evaluator.py
- tests/*

목표: “이걸 어떻게 검증하는가”를 안다.

---

## 14. 질문 1개로 따라가는 방식

코드베이스를 가장 빨리 이해하는 방법은 “질문 1개를 끝까지 추적”하는 것이다.

예시 질문:

```text
삼성전자 2024년 영업이익률은 얼마인가?
```

이 질문으로 아래를 따라간다.

1. `/api/query`에서 어떤 객체가 호출되는가
2. `FinancialAgent.run()`이 어떤 초기 state를 만드는가
3. `_build_graph()`에서 어떤 분기 노드로 가는가
4. 계산 질문이면 `operand_extractor -> formula_planner -> calculator`가 어떻게 호출되는가
5. 최종 citation은 어디서 붙는가

이 골든 패스를 한 번 따라가면 나머지 함수는 “전체 지도 위의 세부 부품”으로 보이기 시작한다.

---

## 15. 테스트를 읽는 법

테스트는 “검증 코드”가 아니라 “모듈 계약 설명서”처럼 읽는 게 좋다.

시작 추천:

- [tests/test_query_router.py](../../tests/test_query_router.py)
- [tests/test_financial_parser.py](../../tests/test_financial_parser.py)
- [tests/test_multi_agent_graph.py](../../tests/test_multi_agent_graph.py)
- [tests/test_analyst_node.py](../../tests/test_analyst_node.py)
- [tests/test_researcher_node.py](../../tests/test_researcher_node.py)
- [tests/test_critic_node.py](../../tests/test_critic_node.py)

이 파일들은 “이 모듈이 무엇을 보장해야 하는가”를 빨리 보여준다.

---

## 16. 내가 직접 정리해야 하는 메모

읽기만 하면 남는 게 적다. 아래 4개를 직접 적는 게 가장 좋다.

- **1페이지 시스템 지도**: entrypoint → agent → parser/store → output
- **골든 패스 1개**: 질문 하나의 실제 함수 호출 순서
- **모듈 인덱스**: 각 파일의 책임 1줄
- **핫 함수 카드**: 입력 / 출력 / 부작용 / 의존성

---

## 17. 빠르게 grep하는 명령

PowerShell / ripgrep 기준:

```powershell
rg -n "def run\\(|def _build_graph|class FinancialAgent" src/agent
rg -n "POST /api/query|def query\\(" src/api
rg -n "class VectorStoreManager|def .*retrieve|def .*search" src/storage
rg -n "class FinancialParser|def process_document|def _" src/processing/financial_parser.py
rg -n "class QueryRouter|def route|def semantic_route" src/routing/query_router.py
rg -n "run_screening_experiment|_run_company_bundle|def main" src/ops/benchmark_runner.py
```

---

## 18. 이 문서를 어떻게 쓸 것인가

이 문서를 다 읽은 뒤에는 아래 두 질문에 답할 수 있어야 한다.

- “지금 실제 질문 응답은 어느 코드 경로를 타는가?”
- “MAS 실험은 기존 single-agent 위에 어떻게 얹혀 있는가?”

이 두 질문에 답이 되면, 그 다음부터는 세부 함수 파악이 훨씬 쉬워진다.

