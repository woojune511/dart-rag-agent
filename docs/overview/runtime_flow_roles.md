# Runtime Flow And Roles

이 문서는 코드 전체를 파일 목록이 아니라 실행 흐름과 책임 경계로 읽기 위한
요약이다. 모든 private helper를 사전처럼 나열하지 않고, 실제 호출 경로에
걸리는 class/function과 helper 역할군을 중심으로 정리한다.

## 1. 큰 실행 경로

### API 질의 경로

```text
main.py
  -> src/api/financial_router.py::query()
  -> FinancialAgent.run()
  -> LangGraph nodes
  -> answer / citations / structured_result / resolved_calculation_trace
```

핵심은 `FinancialAgent`다. API router는 입력 검증과 응답 포맷만 담당하고,
질문 분류, 검색, evidence 구성, 계산, 검증은 agent graph 내부에서 처리한다.

### 문서 적재 경로

```text
financial_router.py::ingest()
  -> DARTFetcher.fetch_company_reports()
  -> FinancialParser.process_document()
  -> FinancialAgent.contextual_ingest()
  -> VectorStoreManager.add_documents()
```

수집은 `ingestion`, 구조 복원과 chunk 생성은 `processing`, 저장과 검색은
`storage`, contextual ingest orchestration은 `agent`가 맡는다.

### benchmark/evaluation 경로

```text
benchmark profile
  -> src/ops/benchmark_runner.py
  -> ingest or store restore
  -> FinancialAgent.run()
  -> src/ops/evaluator.py
  -> results / summary / review artifacts
```

`src/ops`는 운영 runtime이 아니라 검증, replay, gate, 진단용 코드다.

## 2. 서비스 진입점

### `main.py`

- `lifespan(app)`: FastAPI 시작 시 `init_components()`를 호출한다.
- `root()`: 단순 service metadata endpoint다.
- `app.include_router(router)`: 실제 API는 `src/api/financial_router.py`로 넘긴다.

### `src/api/financial_router.py`

- `init_components()`: singleton으로 `VectorStoreManager`, `FinancialAgent`,
  `FinancialParser`, `DARTFetcher`를 만든다.
- `_require(component, name)`: 초기화되지 않은 singleton 접근을 503으로 막는다.
- `health()`: BM25 doc count 기준의 간단한 health check.
- `get_companies()`: Chroma metadata를 훑어 인덱싱된 회사/연도 목록을 만든다.
- `ingest(req)`: DART fetch, parser, contextual ingest를 순서대로 실행한다.
- `query(req)`: `FinancialAgent.run(question)`을 호출하고 caller-facing payload로
  축약한다.

## 3. Single-Agent 핵심

### `src/agent/financial_graph.py::FinancialAgent`

이 class는 실제 runtime의 중심이다. 구현 세부는 mixin에 나뉘어 있고,
`FinancialAgent` 본체는 초기화, LLM route 구성, graph wiring, caller-facing
output projection을 담당한다.

- `__init__()`: vector store, router, LLM route, graph를 초기화한다.
- `_build_llm_routes()`: phase별 LLM 설정을 만든다.
- `_create_chat_model()`: route spec으로 실제 chat model instance를 만든다.
- `_llm_for_phase(phase)`: graph node가 사용할 phase별 LLM을 반환한다.
- `_build_graph()`: LangGraph node와 conditional edge의 canonical order다.
- `run(query, report_scope=None)`: 초기 `FinancialAgentState`를 만들고 graph를
  실행한 뒤 API/benchmark가 쓰는 안정적인 결과 dict로 정규화한다. 최신 return
  shape는 named projection인 `agent_answer`, `review_trace`, `debug_bundle`을
  포함하고, 기존 flat field는 compatibility adapter로 유지한다.
- `_project_agent_answer()`: public answer, citations, `structured_result`,
  `resolved_calculation_trace`를 묶는다.
- `_project_review_trace()`: retrieval/evidence/numeric/retry/subtask/task-artifact
  review material을 묶는다.
- `_project_debug_bundle()`: calculation debug trace, LLM usage, phase usage,
  embedding usage를 묶는다.
- `_project_debug_traces()`: retrieval/calculation/debug trace를 caller-facing
  bundle로 모은다.
- `_augment_citations_from_runtime_evidence()`: runtime evidence에서 citation을
  보강한다.
- `_runtime_evidence_from_retrieved_docs()`: retrieved docs를 runtime evidence
  fallback으로 투영한다.

### `FinancialAgent._build_graph()` 순서

```text
classify
-> extract
-> pre_calc_planner
-> retrieve
-> expand
-> numeric_extractor or evidence
-> reconcile_plan
-> operand_extractor
-> formula_planner
-> calculator
-> calc_render
-> calc_verify
-> advance_subtask
-> aggregate_subtasks
-> cite
```

계산 실패나 근거 부족이 있으면 `reflection_replan -> prepare_retry`를 거쳐
`retrieve` 또는 `operand_extractor`로 되돌아갈 수 있다.
Narrative path는 `evidence -> compress -> validate -> cite`로 진행하고,
calculation aggregate path는 `aggregate_subtasks -> cite` 또는 추가 planning으로
갈 수 있다.

## 4. Agent State And Schemas

### `src/agent/financial_graph_state.py`

이 파일은 graph node 사이의 lightweight state 계약이다. 먼저 이 파일을 읽으면
노드 사이에 어떤 값이 오가는지 잡힌다.

- `FinancialAgentState`: single-agent graph 전체 state. query, routing,
  retrieved docs, evidence, operands, calculation trace, subtasks, retry state를
  모두 담는다.

### `src/agent/financial_graph_models.py`

이 파일은 LLM structured-output과 answer slot 검증용 Pydantic schema를 담는다.
호환성을 위해 state 타입도 re-export하지만, runtime graph schema는
`financial_graph_state.py`를 source of truth로 본다.
- `EntityExtraction`: 회사/연도/topic 추출 결과.
- `EvidenceItem`, `EvidenceExtraction`: source-grounded evidence payload.
- `NumericExtraction`: lookup/single numeric fact extraction 결과.
- `CalculationOperand`, `OperandExtraction`: 계산에 투입할 operand row.
- `CalculationPlan`: deterministic calculator가 실행할 formula plan.
- `CalculationResult`: 계산 실행 결과와 operand/result metadata.
- `CalculationRenderOutput`: answer text와 structured slots.
- `CalculationVerificationOutput`: answer/calculation consistency check 결과.
- `RetrievalTask`, `SemanticPlan`, `ConceptPlannerOutput`: planner가 만든 subtask
  및 concept-driven plan.
- `ReflectionRequest`, `ReflectionPlanRecord`, `ReflectionAction`,
  `ReflectionReport`: bounded reflection/retry 계약.
- `AnswerSlotValue`와 `*AnswerSlots`: 최종 답변의 source-visible display와
  calculated value를 구조화하는 schema.
- `ValidationOutput`: final answer validation 결과.

## 5. Planning Layer

### `src/agent/financial_graph_planning.py::FinancialAgentPlanningMixin`

역할은 질문을 실행 가능한 subtask와 runtime projection으로 바꾸는 것이다.

- `_classify_query(state)`: `QueryRouter.route()`로 intent, format preference,
  routing confidence를 채운다.
- `_extract_entities(state)`: query와 report scope에서 회사/연도 등 scope hint를
  추출한다.
- `_build_llm_concept_numeric_plan(...)`: LLM과 ontology 기반으로 numeric task
  후보를 만든다.
- `_validate_concept_planner_task(...)`: planner task가 runtime contract를
  만족하는지 확인한다.
- `_plan_semantic_numeric_tasks(state)`: 현재 query를 `RetrievalTask` 목록과
  active subtask로 바꾼다.
- `_capture_current_subtask_result(state)`: 현재 subtask의 결과를 projection에
  저장한다.
- `_upsert_subtask_result(...)`: subtask result를 품질 rank 기준으로 갱신한다.
- `_project_runtime_calculation_trace(state)`: canonical calculation trace를 만든다.

이 파일의 top-level helper들은 대부분 slot 추출, task dedupe, plan shape 보존,
hybrid narrative subtask 삽입을 담당한다.

## 6. Retrieval And Evidence Layer

### `src/agent/financial_graph_evidence.py::FinancialAgentEvidenceMixin`

역할은 문서를 검색하고, 구조 graph로 확장하고, 답변에 쓸 evidence를 고르는
것이다.

- `_retrieve(state)`: active subtask와 report scope를 기준으로 metadata filter,
  query variants, cache reuse, BM25/vector hybrid retrieval을 수행한다.
- `_expand_via_structure_graph(state)`: seed docs 주변의 section/table/reference
  graph를 따라 후보 evidence를 확장한다.
- `_rerank_docs(docs, state)`: query intent, section bias, numeric signal,
  narrative policy 등을 반영해 retrieved docs를 재정렬한다.
- `_extract_numeric_fact(state)`: lookup/single numeric fact 후보를 추출하고
  direct support를 확인한다.
- `_extract_evidence(state)`: narrative/mixed answer에 필요한 evidence item을
  만든다.
- `_compress_answer(state)`: evidence를 바탕으로 간결한 answer draft를 만든다.
- `_validate_answer(state)`: answer가 evidence coverage와 task intent를
  만족하는지 확인한다.
- `_format_context(docs)`, `_build_evidence_context(...)`: LLM prompt에 넣을
  context surface를 구성한다.
- `_build_runtime_evidence_item(...)`: source anchor, quote, metadata를 runtime
  evidence row로 정규화한다.
- `_filter_evidence_items_for_required_operands(...)`: required operand와 충돌하는
  evidence를 제거한다.

이 파일의 helper 역할군:

- lookup direct-support 검사
- period/count operand coverage 확인
- narrative policy/facet/driver evidence 보강
- ratio component 후보 추출
- runtime evidence 정렬, dedupe, citation anchor 생성

## 7. Reconciliation Layer

### `src/agent/financial_graph_reconciliation.py::FinancialAgentReconciliationMixin`

역할은 retrieved docs와 structured table candidate를 실제 operand 후보로 맞추는
것이다.

- `_reconcile_retrieved_evidence(state)`: retrieval 결과에서 structured candidate를
  만들고 active task의 operand requirement와 맞춘다.
- `_build_reconciliation_candidates(state)`: table cell, sibling row, section seed
  등을 candidate 목록으로 만든다.
- `_extract_structured_operands_from_reconciliation(state)`: reconciliation match를
  calculation operand row로 변환한다.
- `_find_reconciliation_match_entry(...)`: required operand와 candidate cell의
  label/period/unit/provenance match를 찾는다.
- `_llm_rerank_operand_candidates(...)`: deterministic ranking이 부족한 경우에만
  LLM rerank 후보를 사용한다.
- `_plan_reflection_retry(state)`: 근거 부족 시 retry query/action 계획을 만든다.
- `_supplement_section_seed_docs(state)`: 최종 window 밖으로 밀린 seed evidence를
  required operand 계약에 맞게 보존한다.

helper 역할군은 structured cell identity, period score, unit repair, sibling
lookup surface matching, retry query 생성이다.

## 8. Calculation Layer

### `src/agent/financial_graph_calculation.py::FinancialAgentCalculationMixin`

가장 큰 파일이다. 역할은 evidence/structured rows를 deterministic calculation으로
닫는 것이다.

- `_extract_calculation_operands(state)`: reconciliation direct row, evidence
  fallback, dependency output을 합쳐 operand set을 만든다.
- `_plan_formula_calculation(state)`: operand를 executable calculation plan으로
  바꾼다.
- `_execute_calculation(state)`: formula family에 따라 차이, 비율, 성장률, 합산
  등을 deterministic하게 계산한다.
- `_render_calculation_answer(state)`: 계산 결과를 answer text와 answer slots로
  렌더링한다.
- `_verify_calculation_answer(state)`: answer text, result, operands의 일관성을
  확인한다.
- `_advance_calculation_subtask(state)`: 현재 subtask를 완료/실패 처리하고 다음
  subtask로 이동한다.
- `_aggregate_calculation_subtasks(state)`: 여러 subtask 결과를 최종 aggregate
  answer로 합친다.
- `_prepare_reflection_retry(state)`: reflection action에 따라 retry state를
  구성한다.
- `_format_citations(state)`: 마지막 citation/result payload를 정리한다.
- `_route_after_*`: graph conditional edge를 결정한다.

helper 역할군:

- dependency binding
- unit conversion/repair
- period alignment
- ratio/growth operand ordering
- source-visible display 보존
- stale projection 방지
- aggregate result dedupe/ranking
- narrative context preservation

## 9. Projection And Helper Modules

### `src/agent/financial_answer_projection.py`

Aggregate/narrative subtask 결과 중 caller-facing public answer로 승격할 답변을
고르는 pure helper다. PR #77 이후 `KBF_T2_018` 같은 mixed growth+narrative
projection 문제를 일반 numeric-surface consistency로 처리한다.

- `_preferred_complete_aggregate_subtask_answer(...)`: public answer보다 완성된
  aggregate/narrative answer candidate를 선택한다.
- 내부 numeric-surface helpers: candidate가 기존 answer의 숫자 표면과 충분히
  겹치고, 충돌 numeric surface를 줄이는지 본다.
- 이 모듈은 회사명, benchmark id, report phrase, metric-specific keyword branch를
  갖지 않는다.

### `src/agent/financial_graph_helpers.py`

여러 mixin이 공유하는 runtime helper 묶음이다. 현재는 helper surface가 아직 크기
때문에, 읽을 때 목적별로 들어가야 한다.

- task/artifact projection
- runtime calculation trace construction and metadata
- `structured_result` / `resolved_calculation_trace` compatibility projection
- source row/evidence id cleanup
- numeric parsing and unit normalization helpers
- retrieval hint / operand matching helpers

`_preferred_complete_aggregate_subtask_answer`는 compatibility를 위해 여기서
re-export되지만 실제 구현은 `financial_answer_projection.py`에 있다.

### Extracted calculation helpers

- `financial_answer_slots.py`: answer slot payload construction
- `financial_calculation_execution.py`: deterministic result payload helpers
- `financial_graph_calculation_rendering.py`: calculation answer rendering
- `financial_reflection_projection.py`: reflection/task-artifact projection
- `financial_text_surface.py`: text/narrative surface helpers
- `financial_numeric_surface.py`: numeric display surface extraction/equivalence

## 10. Rendering Helpers

### `src/agent/financial_graph_calculation_rendering.py`

계산 결과를 사용자에게 보이는 문자열로 바꾸는 순수 helper 모음이다.

- `format_calculation_value(...)`: normalized unit 기준 result 표시.
- `format_calculation_value_in_display_unit(...)`: display unit 기준 result 표시.
- `render_value_with_unit(...)`: 값과 단위를 결합해 표기.
- `render_grounded_operand_display(row)`: source-visible operand display를 보존.
- `compose_slot_based_difference_answer(...)`: answer slot 기반 차이 답변 생성.

## 11. Contextual Ingest

### `src/agent/financial_graph_contextual.py::FinancialAgentContextualMixin`

- `ingest(chunks)`: plain ingest wrapper.
- `contextual_ingest(...)`: chunk별 context prefix를 만들고 vector store에 넣는다.
- `benchmark_contextual_ingest(...)`: benchmark runner가 ingest metrics를 얻기
  위한 variant.
- `_generate_context(...)`: LLM context 생성.
- `_fallback_context(...)`: LLM을 쓰지 못할 때 metadata 기반 context 생성.
- `_build_index_prefix(...)`: 검색 index text 앞에 붙일 구조 metadata prefix 생성.

## 12. Parser And Storage

### `src/processing/financial_parser.py::FinancialParser`

DART XML/HTML을 section, paragraph, table, structured value record로 바꾼다.

- `process_document(file_path, source_metadata)`: parser의 public main entry.
- `parse_sections(file_path)`: section text를 빠르게 확인하는 경로.
- `extract_structure_outline(file_path)`: 문서 구조 outline을 뽑는다.
- `build_parents(chunks)`: parent chunk map을 만든다.
- `_extract_sections(...)`: XML root에서 section 단위 블록을 추출한다.
- `_collect_blocks(...)`: paragraph/table/local heading을 block으로 정리한다.
- `_build_table_object(...)`: HTML table을 `TableObject` 유사 payload로 만든다.
- `_build_table_row_records(...)`, `_build_table_value_records(...)`: row/value
  level structured record를 생성한다.
- `_chunk_blocks(...)`: section block을 chunk size에 맞게 나눈다.

top-level helper들은 DART 문서 구조 복원용 regex/heuristic이다. runtime routing
rule이 아니라 parser structure recovery 용도다.

### `src/storage/vector_store.py::VectorStoreManager`

Chroma vector store, BM25, structure graph, metadata filter를 묶은 retrieval
관리자다.

- `__init__()`: embedding provider, Chroma collection, BM25/structure graph를
  초기화한다.
- `add_documents(...)`: documents를 Chroma와 BM25/structure graph에 저장한다.
- `search(query, k, k_rrf, where_filter)`: vector + BM25 hybrid search를 수행한다.
- `validate_vector_index(...)`: vector index 상태를 검사한다.
- `persist()`: Chroma와 sidecar 상태를 저장한다.
- `get_structure_node(...)`, `get_sibling_docs(...)`, `get_reference_docs(...)`,
  `get_section_lead_doc(...)`: graph expansion이 쓰는 구조 조회 API.
- `is_indexed(rcept_no)`: 같은 report 중복 ingest를 막는다.

helper 역할군은 embedding runtime 선택, Chroma metadata 정규화, filter match,
search cache, sidecar table payload 저장, transient error/cooldown 처리다.

## 13. Routing And Ontology

### `src/routing/query_router.py::QueryRouter`

- `route(query)`: 최종 routing decision. semantic route와 fallback을 합쳐
  `QueryRouteResult`를 반환한다.
- `semantic_route(query)`: canonical example embedding과 query embedding의
  similarity로 intent 후보를 만든다.
- `_blocks_numeric_fast_path(...)`: operation signal 없는 keyword-only fast path를
  막는 guardrail.
- `default_format_preference(intent)`: intent별 기본 answer format을 정한다.

### `src/config/ontology.py::FinancialOntologyManager`

runtime code에 domain vocabulary를 박지 않기 위한 declarative layer 접근자다.

- `match_concepts(...)`, `match_metric_families(...)`: query/topic/intent에 맞는
  concept/metric family를 찾는다.
- `best_metric_family(...)`: 가장 적합한 metric family 하나를 고른다.
- `build_operand_spec(key)`: metric family의 operand spec을 만든다.
- `preferred_sections(...)`, `supplement_sections(...)`, `query_hints(...)`,
  `row_patterns(...)`: retrieval/planner가 쓸 declarative hint를 제공한다.
- `binding_policy_for_concept(...)`: operand binding policy를 반환한다.

## 14. DART Fetcher

### `src/ingestion/dart_fetcher.py::DARTFetcher`

- `_load_corp_codes()`: DART corp code 목록을 로드한다.
- `get_corp_code(company_name)`: 회사명에서 corp code를 찾는다.
- `get_filing_list(...)`: DART API에서 filing metadata를 조회한다.
- `download_document(report)`: report file을 내려받아 local path를 채운다.
- `fetch_company_reports(company, years)`: public ingest entry. 조회와 다운로드를
  묶어 `ReportMetadata` 목록을 반환한다.

## 15. MAS Experimental Path

MAS는 현재 single-agent runtime을 typed task/artifact ledger로 감싸는 실험 축이다.

### `src/agent/mas_graph.py`

- `build_initial_state(...)`: MAS state 초기화.
- `build_mas_graph(...)`: Orchestrator, Analyst, Researcher, Critic, Merge graph를
  wiring한다.
- `run_mas_graph(...)`: graph 실행 wrapper.
- `check_critic_approval(...)`: critic verdict에 따라 retry/merge route 결정.
- `check_orchestrator_merge_outcome(...)`: final merge 후 종료/재계획 route 결정.

### `src/agent/mas_types.py`

- `AgentTask`, `Artifact`, `EvidenceRecord`, `CriticReport`, `FinalReport`,
  `MultiAgentState`: MAS ledger schema.
- `build_agent_task(...)`, `build_artifact(...)`, `build_evidence_record(...)`,
  `build_critic_report(...)`, `build_final_report_record(...)`: typed record
  constructor.
- `project_worker_artifact_boundary(...)`: worker artifact가 외부로 노출할 최소
  계약을 만든다.
- `project_mas_task_artifact_trace(...)`: reviewer/caller가 볼 compact integrity
  projection을 만든다.
- `attach_task_artifact_trace(...)`: final state에 trace를 붙인다.

### MAS nodes

- `orchestrator_node.py`
  - `FinancialOrchestratorPlannerCore.run()`: query를 analyst/researcher task로
    나눈다.
  - `FinancialOrchestratorMergeCore.run()`: accepted worker artifacts를 final
    report로 합친다.
  - `make_run_orchestrator_plan(...)`, `make_run_orchestrator_merge(...)`: core를
    LangGraph node function으로 감싼다.
- `analyst_node.py`
  - `make_run_analyst(core_runner)`: numeric task를 기존 `FinancialAgent.run()`에
    위임하고 artifact/evidence record로 변환한다.
- `researcher_node.py`
  - `NarrativeResearcherCore.run()`: vector store에서 narrative docs를 찾고
    compact answer/evidence를 만든다.
  - `make_run_researcher(core_runner)`: researcher core를 MAS node로 감싼다.
- `critic_node.py`
  - `run_critic(state)`: analyst/researcher artifact가 최소 evidence/calculation
    contract를 만족하는지 검사하고 reject feedback을 남긴다.

## 16. Evaluation And Gates

### `src/ops/benchmark_runner.py`

profile 기반 실험 orchestrator다.

- `_run_ingest(...)`: profile 설정에 따라 fresh ingest 또는 cache/store restore.
- `run_screening_experiment(...)`: 단일 experiment 실행.
- `_run_full_evaluation(...)`: agent 결과를 evaluator에 넣어 full eval.
- `_run_company_bundle(...)`: 회사 단위 benchmark bundle 실행.
- `_rerun_company_full_evaluation_only(...)`: store-fixed eval-only refresh.
- `_write_benchmark_outputs(...)`, `_write_multi_company_outputs(...)`: results,
  summary, review artifacts 생성.
- `_BenchmarkProgressReporter`: 장시간 benchmark heartbeat/logger.

### `src/ops/evaluator.py::RAGEvaluator`

- `load_dataset()`: dataset을 `EvalExample`로 로드한다.
- `build_single_company_eval_slice(...)`: 회사별 eval slice 구성.
- `evaluate_one(example)`: agent answer 하나를 faithfulness, completeness,
  retrieval, numeric correctness, operand correctness 등으로 평가한다.
- `run(...)`: dataset 전체 평가.

주요 schema:

- `EvalExample`: 평가 입력 row.
- `EvalEvidence`: canonical evidence.
- `EvalResult`: 평가 결과와 aggregate score.

### review/demo commands

- `src/ops/portfolio_review_gates.py::run_review_gates()`: reviewer-facing gate
  상태를 묶어 ready/not-ready로 요약한다.
- `src/ops/portfolio_demo.py::build_demo()`: fixture-backed demo payload를 만들고
  task/artifact/critic integrity를 요약한다.
- `src/ops/run_eval_only.py::main()`: 기존 benchmark output/store로 eval만 다시
  수행한다.

## 17. 읽는 순서

처음부터 모든 helper를 읽지 말고 아래 순서로 보면 된다.

1. `main.py`
2. `src/api/financial_router.py`
3. `src/agent/financial_graph.py::_build_graph`
4. `src/agent/financial_graph.py::run`
5. `src/agent/financial_graph_state.py::FinancialAgentState`
6. `src/agent/financial_graph_planning.py::FinancialAgentPlanningMixin`
7. `src/agent/financial_graph_evidence.py::FinancialAgentEvidenceMixin`
8. `src/agent/financial_graph_reconciliation.py::FinancialAgentReconciliationMixin`
9. `src/agent/financial_graph_calculation.py::FinancialAgentCalculationMixin`
10. `src/agent/financial_answer_projection.py`
11. `src/processing/financial_parser.py::FinancialParser.process_document`
12. `src/storage/vector_store.py::VectorStoreManager.search`
13. `src/ops/benchmark_runner.py`와 `src/ops/evaluator.py`
14. MAS가 필요할 때만 `src/agent/mas_graph.py`와 `src/agent/nodes/*`

## 18. 헷갈리지 말아야 할 경계

- `FinancialAgent`는 production-like single-agent runtime이다.
- `MAS`는 task/artifact ledger 실험 경로다. Analyst는 상당 부분
  `FinancialAgent` wrapper다.
- `src/ops`는 runtime dependency가 아니라 실험/평가/진단 entrypoint다.
- domain vocabulary는 `src/config/ontology.py`, `src/config/retrieval_policy.py`,
  JSON ontology/config에 있어야 한다.
- parser regex는 DART 문서 구조 복원용이다. retrieval/routing/answer runtime
  branch를 숨기는 곳이 아니다.
- 최종 숫자 답변은 `structured_result`, `resolved_calculation_trace`,
  `evidence_items`를 먼저 보고 판단한다.
