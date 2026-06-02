# Question Trace Walkthrough

이 문서는 **질문 1개가 실제 코드에서 어떻게 흘러가는지**를 따라가며, 큰 그림부터 함수 단위까지 연결해서 보게 만드는 walkthrough다.

같이 보면 좋은 문서:

- [Codebase Map](docs/overview/codebase_map.md)

---

## 1. 대표 질문

대표 질문은 아래로 잡는다.

> **"삼성전자 2024년 영업이익률은 얼마인가?"**

이 질문이 좋은 이유는 단순 lookup이 아니라 보통 아래를 모두 거치기 때문이다.

- 기업/연도 scope 해석
- numeric intent routing
- semantic task planning
- retrieval + structure expansion
- evidence reconciliation
- operand extraction
- formula planning
- deterministic calculation
- final answer aggregation

주의할 점도 하나 있다.

- **실행할 때 생성되는 정확한 subtask 목록은 planner LLM 산출물에 따라 조금 달라질 수 있다.**
- 하지만 **어떤 노드 순서로 흐르고, 어떤 state 계약을 채우는지**는 거의 고정돼 있다.

즉, 이 문서는 “정확한 프롬프트 응답”보다 **안정적인 런타임 skeleton**을 이해하는 데 초점을 둔다.

---

## 2. 한 화면으로 보는 호출 체인

```text
POST /api/query
  -> query() in src/api/financial_router.py
  -> FinancialAgent.run(query)
  -> LangGraph invoke(initial_state)
  -> classify
  -> extract
  -> pre_calc_planner
  -> retrieve
  -> expand
  -> evidence or numeric_extractor
  -> reconcile_plan
  -> operand_extractor
  -> formula_planner
  -> calculator
  -> calc_render
  -> calc_verify
  -> advance_subtask
  -> aggregate_subtasks
  -> cite
  -> QueryResponse(answer, citations, structured_result, resolved_calculation_trace)
```

핵심은 이거다.

- API 레이어는 아주 얇다.
- 실제 복잡성은 거의 전부 `FinancialAgent` graph 안에 있다.
- 숫자 질문은 보통 `calc_subtasks`를 만들고 그 subtask loop를 돈다.

---

## 3. 진입점부터 보기

### 3.1 서버 진입점

- [main.py](main.py)
- [src/api/financial_router.py](src/api/financial_router.py)

`main.py`는 FastAPI app을 띄우고, startup에서 `init_components()`를 호출한다.

`init_components()`는 아래 객체를 한 번만 만든다.

- `VectorStoreManager`
- `FinancialAgent`
- `FinancialParser`
- `DARTFetcher`

즉, 질문 처리 시점에는 parser나 store가 새로 만들어지는 게 아니라, **이미 초기화된 agent singleton**을 호출한다.

### 3.2 실제 요청 처리

`POST /api/query`는 결국 아래 한 줄이 핵심이다.

```python
result = agent.run(req.question)
```

여기서 API는 분석 자체를 하지 않는다. 그냥 `FinancialAgent.run()`에 넘기고, 결과에서 아래 필드만 꺼내 응답으로 돌려준다.

- `answer`
- `query_type`
- `companies`
- `years`
- `citations`
- `structured_result`
- `resolved_calculation_trace`

즉, **외부 계약의 중심은 `FinancialAgent.run()` 반환값**이다.

---

## 4. `FinancialAgent.run()`이 하는 일

- [src/agent/financial_graph.py](src/agent/financial_graph.py)

`run()`은 크게 세 단계만 한다.

1. usage/telemetry reset
2. `initial_state` 생성
3. LangGraph 실행 후 caller-facing payload로 정리

### 4.1 왜 `initial_state`가 중요할까

이 레포는 함수 인자보다 **state dictionary**가 사실상 진짜 계약이다.

초기 state에서 특히 먼저 눈에 들어와야 할 필드는 아래다.

| 필드 | 의미 |
| --- | --- |
| `query` | 원문 질문 |
| `report_scope` | 외부에서 강제한 회사/연도/보고서 범위 |
| `query_type`, `intent` | routing 결과 |
| `companies`, `years`, `topic`, `section_filter` | 질문 scope 힌트 |
| `retrieval_queries`, `retry_queries` | retrieval용 query bundle |
| `seed_retrieved_docs`, `retrieved_docs` | retrieval 결과 |
| `calc_subtasks`, `active_subtask`, `active_subtask_index` | 숫자 질문 loop의 핵심 |
| `evidence_items` | 근거 claim 단위 구조화 결과 |
| `reconciliation_result` | required operand와 evidence candidate를 매칭한 결과 |
| `resolved_calculation_trace` | 계산 runtime의 선호 trace 계약 |
| `structured_result` | 외부 caller가 믿어야 하는 구조화 결과 |
| `tasks`, `artifacts` | 내부 ledger 성격의 실행 기록 |

이걸 먼저 이해하면, 개별 helper를 읽다가 길을 잃을 가능성이 크게 줄어든다.

---

## 5. Graph Wiring 먼저 읽기

- [src/agent/financial_graph.py](src/agent/financial_graph.py)

이 파일의 `_build_graph()`는 “무슨 순서로 일이 벌어지는지”를 보여주는 **정답 지도**다.  
세부 구현은 mixin에 있지만, 순서는 여기서 확정된다.

### 5.1 planning / retrieval 구간

- `classify`
- `extract`
- `pre_calc_planner`
- `retrieve`
- `expand`

### 5.2 evidence / numeric 분기

- `numeric_extractor`
- `evidence`
- `reconcile_plan`

### 5.3 calculation subgraph

- `operand_extractor`
- `formula_planner`
- `reflection_replan`
- `prepare_retry`
- `calculator`
- `calc_render`
- `calc_verify`
- `advance_subtask`
- `aggregate_subtasks`

### 5.4 narrative / finish 구간

- `compress`
- `validate`
- `cite`

처음 읽을 때는 `_build_graph()`만 보고 아래 질문에 답할 수 있으면 된다.

1. 숫자 질문이 narrative path로 빠지는가, calculation path로 빠지는가?
2. retry는 어떤 노드에서 다시 `retrieve`로 돌아가는가?
3. subtask loop는 어느 노드가 책임지는가?

---

## 6. 이 질문이 실제로 흐르는 방식

이제 대표 질문 `"삼성전자 2024년 영업이익률은 얼마인가?"`를 기준으로 따라가 보자.

### 6.1 `classify`: 질문 의도 분류

- 구현: [src/routing/query_router.py](src/routing/query_router.py)
- 노드: `FinancialAgentPlanningMixin._classify_query()`

여기서는 `QueryRouter.route()`가 먼저 돈다.

핵심 포인트:

- semantic router가 canonical query 예시 임베딩과 비교한다.
- 필요하면 LLM fallback을 쓴다.
- 결과로 `intent`, `format_preference`, `routing_confidence`, `routing_scores`를 state에 넣는다.

이 질문은 보통 아래 중 하나로 정리된다.

- `numeric_fact`
- 또는 숫자 계산형 `comparison`/`trend` 계열

중요한 건 이름 자체보다, **이 시점부터 numeric pipeline 후보가 된다는 점**이다.

### 6.2 `extract`: 가벼운 scope 힌트 추출

- 구현: [src/agent/financial_graph_planning.py](src/agent/financial_graph_planning.py)
- 함수: `_extract_entities()`

이 단계는 거대한 NER가 아니다. 오히려 아주 보수적으로 아래 정도만 seed한다.

- 질문에 직접 보이는 연도
- `report_scope`에 들어온 회사/연도
- `topic = query`
- `section_filter = None`

즉, 이 단계는 “정답을 이해”하기보다 **planner가 쓸 초기 힌트**를 깔아놓는 단계다.

### 6.3 `pre_calc_planner`: 숫자 질문을 subtask로 분해

- 구현: [src/agent/financial_graph_planning.py](src/agent/financial_graph_planning.py)
- 함수: `_plan_semantic_numeric_tasks()`

이 단계가 single-agent runtime의 핵심 전환점이다.

질문이 non-numeric이면:

- `fallback_general_search`
- `calc_subtasks = []`
- `retrieval_queries = [query]`

질문이 numeric이면:

- semantic numeric plan을 만든다.
- 필요한 경우 concept-level task로 쪼갠다.
- `calc_subtasks`, `active_subtask`, `retrieval_queries`를 채운다.

이 질문에서는 보통 아래와 비슷한 구조가 된다.

1. 2024년 영업이익 lookup
2. 2024년 매출액 lookup
3. 영업이익률 ratio 계산

실제 task label은 달라도 구조는 대체로 이렇다.  
즉, “영업이익률”을 한 번에 답하려 하기보다 **필요한 숫자와 최종 연산을 분리**한다.

### 6.4 `retrieve`: query bundle로 후보 chunk 수집

- 구현: [src/agent/financial_graph_evidence.py](src/agent/financial_graph_evidence.py)
- 함수: `_retrieve()`

이 함수는 생각보다 단순한 vector search wrapper가 아니다. 실제로는 아래를 조합한다.

- 현재 `active_subtask.query`
- subtask별 `retrieval_queries`
- state-level `retrieval_queries`
- retry 시 `retry_queries`
- operand-focused queries
- report scope 기반 metadata filter

여기서 중요한 state:

- `retrieval_queries`
- `retry_queries`
- `retrieval_debug_trace`
- `seed_retrieved_docs`
- `retrieved_docs`

이 단계의 읽기 포인트는 두 가지다.

1. 어떤 query bundle이 실제 실행되었는가
2. company/year/report_type/rcept_no filter가 얼마나 강하게 적용되었는가

### 6.5 `expand`: 구조 그래프 기준으로 문맥 확장

- 구현: [src/agent/financial_graph_evidence.py](src/agent/financial_graph_evidence.py)
- 함수: `_expand_via_structure_graph()`

초기 retrieval hit만으로는 표 제목, 상위 문단, sibling row가 부족할 수 있다.  
그래서 이 단계에서 structural context를 붙인다.

예를 들면 이런 것들이다.

- parent paragraph
- section lead
- reference note
- table context
- sibling block

즉, vector search는 후보를 가져오고, `expand`는 **그 후보를 사람이 읽을 수 있는 문맥으로 복원**하는 역할에 가깝다.

### 6.6 `route_after_expand`: 숫자 직행인지, evidence 추출인지 결정

- 구현: [src/agent/financial_graph_calculation.py](src/agent/financial_graph_calculation.py)
- 함수: `_route_after_expand()`

분기 규칙은 대략 이렇다.

- active subtask가 `lookup`/`single_value`면 `numeric_extractor`
- 계산형 subtask면 `evidence`
- narrative summary면 `evidence`

즉, **질문 전체가 숫자 질문인지**보다 **현재 active subtask가 어떤 operation_family인지**가 더 중요하다.

### 6.7 `numeric_extractor` 또는 `evidence`

관련 구현:

- [src/agent/financial_graph_evidence.py](src/agent/financial_graph_evidence.py)
- 함수: `_extract_numeric_fact()`, `_extract_evidence()`

두 경로 차이는 이렇다.

- `numeric_extractor`: 단일 숫자 lookup이 가능한지 직접 본다.
- `evidence`: 계산/서술에 쓸 claim 단위 evidence를 구조화한다.

영업이익률 질문에서는 보통 lookup subtask와 ratio subtask가 섞이므로, loop의 어느 시점이냐에 따라 둘 다 지나갈 수 있다.

### 6.8 `reconcile_plan`: 필요한 operand와 실제 근거 후보를 맞춘다

- 구현: [src/agent/financial_graph_reconciliation.py](src/agent/financial_graph_reconciliation.py)
- 함수: `_reconcile_retrieved_evidence()`

이 단계는 매우 중요하다. retrieval이 “문서 후보를 많이 가져오는 일”이라면, reconciliation은 “그중에서 현재 subtask가 필요로 하는 operand를 실제로 매칭하는 일”이다.

즉, 여기서 하는 일은 대충 아래다.

- active subtask가 요구하는 `required_operands` 확인
- retrieved/evidence 후보를 reconciliation candidate로 변환
- 연도/period/role/statement type 등을 보고 맞는 후보를 선택
- `ready`, `retry_retrieval`, `insufficient_operands` 중 하나로 상태 결정

여기서 보면 좋은 state:

- `active_subtask.required_operands`
- `evidence_items`
- `reconciliation_result`
- `retry_strategy`
- `retry_queries`

숫자 질문 디버깅은 보통 retrieval보다 **이 단계 실패인지 아닌지**가 더 중요하다.

### 6.9 `operand_extractor`: 계산 가능한 operand row로 정규화

- 구현: [src/agent/financial_graph_calculation.py](src/agent/financial_graph_calculation.py)
- 함수: `_extract_calculation_operands()`

이 함수는 reconciliation 결과를 계산에 바로 쓸 수 있는 row로 바꾼다.

예:

- `raw_value`
- `raw_unit`
- `normalized_value`
- `normalized_unit`
- `period`
- `source_anchor`

즉, 이 단계부터는 “문장/표 해석”보다 **계산 입력 테이블 만들기**에 가깝다.

### 6.10 `formula_planner`: 연산식 구성

- 구현: [src/agent/financial_graph_calculation.py](src/agent/financial_graph_calculation.py)
- 함수: `_plan_formula_calculation()`

이 단계는 numeric runtime의 두 번째 핵심이다.

보는 포인트:

- 가능한 한 deterministic plan을 우선한다.
- `lookup`, `difference`, `ratio`, `growth_rate`, `sum` 같은 operation family로 정리한다.
- required operand가 빠져 있으면 incomplete plan으로 표시한다.

이 질문의 전형적인 결과는 아래와 비슷하다.

- `operation_family = ratio`
- `variable_bindings = A: 영업이익, B: 매출액`
- `formula = A / B * 100`
- `result_unit = %`

### 6.11 `reflection_replan` / `prepare_retry`: operand가 부족하면 재검색

관련 구현:

- [src/agent/financial_graph_planning.py](src/agent/financial_graph_planning.py) 의 `_plan_reflection_retry()`
- [src/agent/financial_graph_calculation.py](src/agent/financial_graph_calculation.py) 의 `_prepare_reflection_retry()`

언제 여기로 오나:

- formula plan이 incomplete일 때
- calculator가 `insufficient_operands` 또는 `parse_error`를 낼 때

이 단계는 아래를 만든다.

- `missing_info`
- `retry_reason`
- `retry_strategy`
- `retry_queries`
- `reflection_count`

그리고 다시 `retrieve`로 돌아간다.

즉, 이 시스템의 retry는 “답변을 억지로 꾸미는 단계”가 아니라 **부족한 operand를 다시 찾는 retrieval retry**다.

### 6.12 `calculator`: 실제 계산 실행

- 구현: [src/agent/financial_graph_calculation.py](src/agent/financial_graph_calculation.py)
- 함수: `_execute_calculation()`

여기서 하는 일:

- plan의 variable binding을 실제 operand row에 대입
- unit family가 맞는지 검사
- normalized value가 있는지 검사
- 안전한 env에서 계산식 실행
- `calculation_result`와 `answer_slots` 생성

여기서 중요한 건 이 계산이 **문장 생성이 아니라 deterministic execution**이라는 점이다.

### 6.13 `calc_render` / `calc_verify`: 계산 결과를 답변 문장으로 정리

관련 구현:

- `_render_calculation_answer()`
- `_verify_calculation_answer()`

역할 분리:

- `calc_render`: 계산 결과를 사람이 읽을 답변으로 정리
- `calc_verify`: render된 답변이 계산 결과와 충돌하지 않는지 한 번 더 점검

즉, LLM이 쓰이는 곳이 있더라도, 이미 계산된 구조화 결과를 **표현하는 단계**이지 수치를 새로 발명하는 단계가 아니다.

### 6.14 `advance_subtask`: 다음 subtask로 이동

- 구현: [src/agent/financial_graph_calculation.py](src/agent/financial_graph_calculation.py)
- 함수: `_advance_calculation_subtask()`

이 함수가 하는 일:

- 현재 subtask 결과를 `subtask_results`에 저장
- 다음 task가 있으면 `active_subtask_index`와 `active_subtask`를 갱신
- 다음 task용으로 answer/evidence/calculation 관련 임시 state를 비운다

즉, 숫자 질문 loop를 실제로 굴리는 핵심 포인터는 아래 두 개다.

- `active_subtask_index`
- `active_subtask`

### 6.15 `aggregate_subtasks`: subtask 결과를 최종 답으로 합친다

- 구현: [src/agent/financial_graph_calculation.py](src/agent/financial_graph_calculation.py)
- 함수: `_aggregate_calculation_subtasks()`

이 단계에서는 전체 subtask 결과를 모아 최종 caller-facing answer를 만든다.

영업이익률 질문에서는 보통 아래 같은 재료가 합쳐진다.

- 영업이익 lookup 결과
- 매출액 lookup 결과
- ratio 계산 결과
- 필요한 경우 narrative context

이 단계가 끝나면 아래가 사실상 최종형에 가깝다.

- `answer`
- `structured_result`
- `resolved_calculation_trace`

### 6.16 `cite`: citation 문자열 부착

- 구현: [src/agent/financial_graph_calculation.py](src/agent/financial_graph_calculation.py)
- 함수: `_format_citations()`

마지막으로 `retrieved_docs`에서 citation 문자열을 만들고 종료한다.

즉, citation은 별도 deep reasoning의 결과가 아니라, **최종 사용된 retrieval window를 caller-friendly string으로 포맷한 것**에 가깝다.

---

## 7. 이 질문에서 state가 변하는 순서

아래 순서만 기억해도 디버깅 속도가 크게 빨라진다.

| 단계 | 주로 채워지는 state |
| --- | --- |
| `classify` | `query_type`, `intent`, `format_preference`, `routing_scores` |
| `extract` | `companies`, `years`, `topic`, `section_filter` |
| `pre_calc_planner` | `calc_subtasks`, `active_subtask`, `retrieval_queries`, `semantic_plan` |
| `retrieve` | `seed_retrieved_docs`, `retrieved_docs`, `retrieval_debug_trace` |
| `expand` | `retrieved_docs`의 문맥 확장본 |
| `numeric_extractor` / `evidence` | `evidence_items`, `evidence_status` |
| `reconcile_plan` | `reconciliation_result`, `retry_queries`, `retry_reason` |
| `operand_extractor` | `resolved_calculation_trace.calculation_operands` |
| `formula_planner` | `resolved_calculation_trace.calculation_plan`, `missing_info` |
| `calculator` | `resolved_calculation_trace.calculation_result` |
| `advance_subtask` | `subtask_results`, 다음 `active_subtask` |
| `aggregate_subtasks` | 최종 `answer`, `structured_result`, `resolved_calculation_trace` |
| `cite` | `citations` |

실전에서는 이 표를 보고 “지금 고장이 난 층이 planner인지, retrieval인지, reconciliation인지, calculator인지” 먼저 판단하면 된다.

---

## 8. 함수 단위까지 내려갈 때의 읽는 순서

이 질문을 기준으로 함수 단위까지 내려가려면, 아래 순서가 가장 덜 헷갈린다.

1. [src/api/financial_router.py](src/api/financial_router.py)의 `query()`
2. [src/agent/financial_graph.py](src/agent/financial_graph.py)의 `run()`
3. 같은 파일의 `_build_graph()`
4. [src/agent/financial_graph_planning.py](src/agent/financial_graph_planning.py)의 `_classify_query()`
5. 같은 파일의 `_extract_entities()`
6. 같은 파일의 `_plan_semantic_numeric_tasks()`
7. [src/agent/financial_graph_evidence.py](src/agent/financial_graph_evidence.py)의 `_retrieve()`
8. 같은 파일의 `_expand_via_structure_graph()`
9. 같은 파일의 `_extract_numeric_fact()` / `_extract_evidence()`
10. [src/agent/financial_graph_reconciliation.py](src/agent/financial_graph_reconciliation.py)의 `_reconcile_retrieved_evidence()`
11. [src/agent/financial_graph_calculation.py](src/agent/financial_graph_calculation.py)의 `_extract_calculation_operands()`
12. 같은 파일의 `_plan_formula_calculation()`
13. 같은 파일의 `_execute_calculation()`
14. 같은 파일의 `_advance_calculation_subtask()`
15. 같은 파일의 `_aggregate_calculation_subtasks()`
16. 같은 파일의 `_format_citations()`

핵심 원칙은 이거다.

- helper부터 읽지 않는다.
- 먼저 state 계약과 graph wiring을 본다.
- 그 다음 node 본문을 본다.
- helper는 정말 막혔을 때만 내려간다.

---

## 9. 이 질문이 narrative 질문과 다른 점

예를 들어 질문이 `"삼성전자 2024년 주요 리스크는 무엇인가?"`였다면 흐름이 달라진다.

달라지는 지점:

- `pre_calc_planner`에서 `fallback_general_search`
- `calc_subtasks = []`
- `expand` 이후 `evidence`
- `compress`
- `validate`
- `cite`

즉, 숫자 질문의 핵심이 `reconcile -> operand -> formula -> calculator`라면, narrative 질문의 핵심은 `retrieve -> evidence -> compress -> validate`다.

---

## 10. MAS 쪽에서 이 경로를 어떻게 재사용하는가

- [src/agent/mas_graph.py](src/agent/mas_graph.py)
- [src/agent/nodes/analyst_node.py](src/agent/nodes/analyst_node.py)

MAS를 읽을 때 중요한 사실은 하나다.

- MAS가 숫자 계산 엔진을 새로 구현한 게 아니다.
- `Analyst` node가 기존 `FinancialAgent.run()`을 감싸서 재사용한다.

즉, single-agent 경로를 이해하고 나면 MAS에서도 최소한 `Analyst` 부분은 바로 읽힌다.

---

## 11. 이 문서를 어떻게 써야 하는가

가장 효과적인 사용법은 아래다.

1. 이 문서를 먼저 읽고, 대표 질문 흐름을 머리에 넣는다.
2. 그 다음 [Codebase Map](docs/overview/codebase_map.md)으로 돌아가서 디렉터리 지도를 다시 본다.
3. 실제로는 `query()` -> `run()` -> `_build_graph()` -> `pre_calc_planner` -> `retrieve` -> `reconcile` -> `calculator` 순서로 파일을 연다.
4. 필요하면 같은 질문으로 debug logging을 보고 state 필드를 대조한다.

이렇게 읽으면 “파일이 많아서 복잡한 느낌”이 아니라, **질문 하나가 어떤 계약을 지나가는지**로 구조가 보이기 시작한다.


