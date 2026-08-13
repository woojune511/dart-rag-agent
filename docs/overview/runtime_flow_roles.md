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
output sequencing을 담당한다. 준비된 evidence/answer/review/debug 값의 state-free
projection은 `financial_agent_run_projection.py`가 소유한다.

- `__init__()`: vector store, router, LLM route, graph를 초기화한다.
- `_build_llm_routes()`: phase별 LLM 설정을 만든다.
- `_create_chat_model()`: route spec으로 실제 chat model instance를 만든다.
- `_llm_for_phase(phase)`: graph node가 사용할 phase별 LLM을 반환한다.
- `_build_graph()`: LangGraph node와 conditional edge의 canonical order다.
- `run(query, report_scope=None)`: 초기 `FinancialAgentState`를 만들고 graph를
  실행한 뒤 API/benchmark가 쓰는 안정적인 결과 dict로 정규화한다. 최신 return
  shape는 named projection인 `agent_answer`, `review_trace`, `debug_bundle`을
  포함하고, 기존 flat field는 compatibility adapter로 유지한다.
- `financial_agent_run_projection.project_agent_answer()`: public answer,
  citations, `structured_result`, `resolved_calculation_trace`를 묶는다.
- `financial_agent_run_projection.project_review_trace()`: retrieval/evidence/
  numeric/retry/subtask/task-artifact review material을 묶는다.
- `financial_agent_run_projection.project_debug_bundle()`와
  `project_debug_traces()`: calculation trace와 usage를 caller-facing bundle로
  모은다.
- `financial_agent_run_projection.augment_citations_from_runtime_evidence()`:
  이미 준비된 runtime evidence에서 citation을 보강한다.
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
- `_project_runtime_calculation_trace(state)`: canonical calculation trace를 만든다.

이 파일에 남은 top-level helper들은 execution-task logical projection,
dependency closure와 non-numeric operation-intent override를 담당한다.

## 6. Retrieval And Evidence Layer

### `src/agent/financial_retrieval_pipeline.py::FinancialRetrievalPipelineMixin`

역할은 active subtask와 report scope를 실제 retrieval 실행과 trace로 바꾸는
것이다.

- `_retrieve(state)`: metadata filter, query bundle/budget, cache reuse,
  BM25/vector hybrid retrieval, retry retrieval, seed/visible 결과와
  `retrieval_debug_trace`를 만든다.
- `_rerank_docs(docs, state)`: query intent, section bias, numeric signal,
  narrative policy를 반영해 후보를 재정렬한다.
- `_select_narrative_summary_docs(...)`: narrative/table/policy coverage를
  유지하면서 visible retrieval window를 고른다.
- `_ensure_preferred_operand_section_docs(...)`: required operand와 period
  coverage를 만족하는 후보가 final window에서 사라지지 않게 한다.

query/filter/search/rerank/selection/trace의 실제 구현은 이 파일 한 곳에 있고,
evidence mixin에는 `_retrieve` 호환 복사본이 없다.

### `src/agent/financial_graph_evidence.py::FinancialAgentEvidenceMixin`

역할은 검색된 문서를 구조 graph로 확장하고, 답변에 쓸 evidence를 고르는
것이다.

- `_expand_via_structure_graph(state)`: seed docs 주변의 section/table/reference
  graph를 따라 후보 evidence를 확장한다.
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

### `src/agent/financial_retrieval_hints.py`

현재 ontology/policy 기반 statement type, preferred section, query suffix와
active-subtask section hint를 state-free하게 투영한다. 다음 선택은 evidence
mixin의 query focus-term, preferred-section evidence subset, compression-guidance
projection만 이 owner로 옮긴다. 검색 실행, document/evidence construction,
prompt/model invocation과 state mutation은 evidence/retrieval graph에 남는다.

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
- `financial_reconciliation_candidates.py`: 이미 준비된 candidate/cell의
  statement/unit/period/score/identity/row/match/ID projection을 담당한다.
- `_llm_rerank_operand_candidates(...)`: deterministic ranking이 부족한 경우에만
  LLM rerank 후보를 사용한다.
- `_plan_reflection_retry(state)`: 근거 부족 시 retry query/action 계획을 만든다.
- `_supplement_section_seed_docs(state)`: 최종 window 밖으로 밀린 seed evidence를
  required operand 계약에 맞게 보존한다.

graph mixin에 남은 helper 역할군은 candidate collection, structured-pair/
operand extraction orchestration, LLM rerank, evidence construction, seed
preservation과 retry planning이다.

## 8. Calculation Layer

### `src/agent/financial_graph_calculation.py::FinancialAgentCalculationMixin`

이 mixin은 큰 파일이지만 state-free 계산 규칙의 최종 owner가 아니다. Graph state를
읽고 갱신하고, evidence/query/row 입력을 준비하고, owner 호출 시점을 정하고,
반환값을 trace/task/artifact/final state로 투영하는 adapter/orchestrator다.

주요 graph node는 다음과 같다.

- `_extract_calculation_operands(state)`: direct, recovered, dependency operand를
  준비하고 state-free resolution owner를 호출한다.
- `_plan_formula_calculation(state)`: state/query를 deterministic plan 입력으로
  바꾸고 selected plan을 runtime state에 투영한다.
- `_run_calculation_candidate(state)`와
  `_run_calculation_candidate_input(...)`: prepared candidate pipeline을 실행한다.
- `_execute_calculation(state)`: validated binding을 execution owner에 넘기고
  result/trace/artifact를 반영한다.
- `_render_calculation_answer(state)`와
  `_verify_calculation_answer(state)`: answer rendering과 consistency gate를 담당한다.
- `_advance_calculation_subtask(state)`와
  `_aggregate_calculation_subtasks(state)`: subtask progression과 aggregate
  orchestration을 담당한다.
- `_prepare_reflection_retry(state)`, `_format_citations(state)`,
  `_route_after_*`: retry, final citation, graph edge를 담당한다.

State-free owner topology:

| Owner | 역할 |
| --- | --- |
| `financial_operand_resolution.py` | candidate match/merge/adoption, unit and period coercion, dependency-task KRW consistency, table-metadata/raw-unit repair, growth raw-scale alignment/period conflict, ratio display alignment, and denominator sign policy |
| `financial_dependency_projection.py` | dependency precedence/projection, recalculation disposition, provenance and source-slot consistency, plus dependency input matching, sibling-output synthesis preference, and task-output binding projection; dependency-task KRW-consistency implementation and ownership moved to the operand owner |
| `financial_reconciliation_candidates.py` | prepared candidate/cell statement, unit, period, score, identity, operand-row, match, candidate-ID, and structured period-pair projection; full operand extraction, collection, reranking, evidence construction, retry, and state mutation remain outside |
| `financial_calculation_execution.py` | state-free base/runtime operation and ontology plan construction, validation/guard, formula execution, and stale-value assessment; dynamic metric-family selection, lookup/LLM planning, and state projection remain graph-owned |
| `financial_answer_slots.py` | answer-slot construction, shared slot-material/period policy, ratio consolidation/collapse/completeness, and source display compatibility |
| `financial_answer_projection.py` | aggregate-row growth-period conflict, material-gap, row-material, nested-row traversal/operation/specificity and bounded selected-result promotion, narrative intent/surface/trace validation, and final-answer projection policy |
| `financial_numeric_surface.py` | numeric extraction/equivalence, answer/reference comparison, table support, numeric-support predicates, and ratio scale checks |
| `financial_text_surface.py` | shared token/sentence normalization, Korean particle polishing, narrative term/variant/context presentation, prepared-document snippet projection, retrieved-source preservation, query-focus marker projection, source-visible term preservation, and table-noise/fragment predicates |
| `financial_lookup_recovery.py` | lookup magnitude, selected-evidence consistency, refinement eligibility, unit normalization, successful-row alignment/replacement, direct structured-row/value projection, active-task matching, prose answer-slot synthesis, and supporting-document projection over supplied evidence |
| `financial_retrieval_hints.py` | ontology/policy-backed statement, section, and query hints; read-only evidence focus/subset/compression guidance is the selected next boundary, while retrieval, evidence construction, and model invocation remain graph-owned |
| `financial_aggregate_projection.py` | aggregate signatures, primary/source/coherence and dependency-source preparation, result/nested ranks, stable dedupe, repair/projection transforms, duplicate growth-prior recovery, final evidence/provenance projection, own-evidence lookup-unit alignment, compact prompt rows, row/sentence/rendered selectors, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering, result support/reuse predicates, and final-answer evidence filter/operand append/surface-operand projection |
| `financial_aggregate_state.py` | aggregate composition carrier and state-free transition |
| `financial_runtime_trace.py` | runtime trace projection, material-numeric predicate, prepared operand overlay, and collapsed-ratio evidence repair |
| `financial_agent_run_projection.py` | caller-facing evidence metadata/citation, agent-answer/review/debug bundle, structured missing-answer selection, aggregate completion, and prepared public-answer state projection; graph execution, dynamic answer repair, evidence selection, trace/ledger work remain outside |
| `financial_task_artifacts.py` | task/artifact projection, prepared artifact/ref enrichment, runtime-evidence merge, and ratio task-result row projection |
| `financial_reflection_projection.py` | reflection request/plan normalization, strict summaries, synthesis source, deterministic action/report, and bounded artifact-integrity feedback; heuristic and LLM planning remain outside |
| `financial_graph_calculation_rendering.py` | calculation answer rendering plus ratio result-unit, absolute-query, and result projection policy |

Graph adapter에 남는 역할은 다음 범주로 읽으면 된다.

1. graph-state, query, task, evidence와 artifact lookup
2. direct/recovered/dependency row construction, coercion, scope와 applicability gate
3. owner 입력 preparation, caller placement, sequential adoption과 equality gate
4. LLM invocation, prompt/debug payload, retry와 exception/fallback orchestration
5. mutable calculation/task/artifact/ledger state projection
6. aggregate evidence selection, dependency-coherence row replacement, sync/rebuild와 final-answer sequencing
7. broader ledger synchronization과 아직 선택되지 않은 private helper mesh

최근 owner 이동에는 ratio sign/presentation/readiness/scale policy, numeric support,
aggregate selector, slot-material/period policy, aggregate source/coherence preparation,
material-gap, result/nested rank, dedupe, narrative-answer validation, bounded aggregate
row/gap/lookup-answer policy, narrative term/variant/context sentence presentation,
prepared-document snippet projection and retrieved-source preservation,
  prepared KRW raw-unit/growth alignment/period-conflict, dependency-task KRW consistency,
  lookup magnitude와 same-block/table-metadata KRW repair, direct structured
  lookup-row/value projection, aggregate ratio seed/source scoring/selection/component
projection, aggregate result support/reuse predicate와 prepared growth-numeric
rendering, dependency input matching/binding/synthesis policy, prepared structured-
reconciliation candidate projection, final-answer evidence filtering/operand
append/surface-operand projection, nested-row traversal/operation/specificity와
bounded selected-result promotion이 포함된다. Graph는 query/evidence preparation,
caller placement, answer composition/refresh, broader dependency-coherence row
replacement, sync/rebuild, mutable state/evidence, ledger와 callback/final
orchestration을 유지한다.

함수별 identity, copy, laziness, access, exception, precedence와 caller stop line은
[Agent Runtime Contract](../architecture/agent_runtime_contract.md)가 단일 기준이다.
현재 gate와 다음 작업은 [Project Status](project_status.md), commit별 이동 수치와
claim limit은 [Implementation History](../history/implementation_history.md)를 본다.

## 9. Projection And Helper Modules

### `src/agent/financial_answer_projection.py`

Aggregate/narrative row의 state-free answer policy owner다.

- `growth_row_has_conflicting_periods(...)`,
  `material_gap_feedback_for_subtask_result(...)`,
  `subtask_row_has_material(...)`: period/material readiness를 판정한다.
- `query_requests_explanatory_context(...)`,
  `sentence_has_growth_explanatory_signal(...)`,
  `answer_looks_truncated(...)`, `answer_covers_narrative_context(...)`:
  narrative intent와 answer surface completeness를 판정한다.
- `growth_uses_source_stated_result(...)`,
  `growth_sentence_has_untraced_material_numeric(...)`,
  `growth_answer_has_untraced_numeric_sentence(...)`: source-stated result와
  untraced numeric narrative를 판정한다.
- `nested_subtask_rows(...)`와 owner-private operation/specificity helpers는
  준비된 nested result를 depth-first로 투영하고 rank를 계산하며,
  `promote_nested_subtask_result_if_more_specific(...)`는 현재 material 보호와
  stable winner 규칙 안에서 선택된 result만 반환한다. Task/state capture와
  broader dependency-coherence replacement는 소유하지 않는다.
- `_preferred_complete_aggregate_subtask_answer(...)`와 내부 numeric-surface
  helpers: 더 완성된 answer candidate를 evidence-visible 숫자 표면으로 비교한다.
- 이 모듈은 회사명, benchmark id, report phrase, metric-specific keyword branch를
  갖지 않는다.

### `src/agent/financial_text_surface.py`

여러 answer-composition 경로가 공유하는 state-free text surface owner다.

- 내부 token/sentence/anchor/rerank-metadata helpers는 정규화된 text fragment를
  준비한다.
- `topic_particle(...)`와 `polish_korean_particle_pairs(...)`는 policy와 한글
  음절 구조에 따라 조사 표면만 다듬는다.
- `split_narrative_sentences(...)`,
  `narrative_sentence_looks_table_noisy(...)`,
  `narrative_sentence_looks_abbreviated_fragment(...)`는 sentence splitting과
  table-noise/fragment 판정만 소유한다.
- `narrative_context_terms(...)`, `narrative_focus_variants(...)`,
  `parenthetical_focus_variants(...)`는 query term과 focus surface를 만들고,
  `narrative_context_sentence_from_evidence(...)`와
  `include_narrative_context_if_needed(...)`는 이미 준비된 evidence에서 text
  sentence를 고르고 answer에 포함할지 결정한다.
- `policy_required_realized_snippet_from_doc(...)`는 이미 준비된 document
  surface에서 policy-required label/value snippet을 고르고,
  `preserve_retrieved_narrative_source_surface(...)`는 이미 준비된 answer/evidence
  sentence 사이에서 retrieved source wording을 보존한다. 이 owner는 retrieval,
  evidence construction, composition, state 또는 ledger를 소유하지 않는다.
- 일곱 public API의 27개 call은 graph external 22개와 owner-local 5개로
  배치된다. 세부 분포와 exception/identity 계약은
  [Agent Runtime Contract](../architecture/agent_runtime_contract.md)를 따른다.
- `query_focus_marker_groups(...)`, `query_focus_markers(...)`,
  `preserve_source_visible_query_terms(...)`는 retrieval/evidence/calculation
  caller가 준비한 query, answer, result, evidence, document surface만 읽어 marker와
  missing-term note를 투영한다. 세 API의 12개 call은 graph external 10개와
  owner-local 2개이고, retrieval/reranking, evidence construction, aggregate
  adoption과 state/ledger sequencing은 기존 graph owner에 남는다.
- 완료된 dependency-source preparation은
  `financial_aggregate_projection.py`의 public seed/slot-score/best-source/
  component 함수와 owner-private text score로 배치된다. 아홉 call은 graph
  external 7개와 owner-local 2개이며, bound callback source map과 compact-ratio
  state/trace caller는 graph에 남는다.
- 완료된 narrative row-focus selection도 같은 owner의 public sentence/context
  함수로 배치된다. 세 call은 모두 graph-external이고 dynamic driver discovery,
  answer composition/validation, evidence/state sequencing은 graph에 남는다.
- 완료된 growth display/material projection도 같은 owner의 public display,
  material-equality, prior-recovery 함수와 owner-private source-task helper로
  배치된다. 18 call은 graph external 15개와 owner-local 3개이며 growth answer
  construction, duplicate recovery, evidence/state sequencing은 graph에 남는다.
- 완료된 result support/reuse predicate도 같은 owner의 public dependency/
  realignment/narrative/numeric-reuse 함수로 배치된다. 12 call은 graph external
  11개와 owner-local 1개이며 answer choice, composition, state/evidence, final
  sequencing은 graph에 남는다.
- 완료된 prepared material-inspection cluster도 같은 owner의 public growth-
  required display, strong-trace, lookup-slot, retrieved-ratio-conflict 함수와
  owner-private ratio-value helper로 배치된다. 17 call은 graph external 16개와
  owner-local 1개이며 growth composition, ratio artifact/state,
  final sequencing은 graph에 남는다.
- 완료된 prepared growth-numeric renderer도 같은 owner의 public
  `compose_complete_growth_numeric_answer(...)`로 배치된다. 아홉 call은 모두
  graph-external이며 answer replacement/refresh, sentence repair, state/evidence,
  final sequencing은 graph에 남는다.
- 완료된 prepared growth trace-inspection cluster도 같은 owner의 public
  `growth_answer_has_untraced_numeric_material(...)`,
  `narrative_summary_conflicts_with_growth_trace(...)`,
  `growth_narrative_numeric_incompatible_with_trace(...)`로 배치된다. 19개 call은
  모두 graph-external이며 answer replacement/refresh, source-visible sentence
  repair, state/evidence, final sequencing은 graph에 남는다.
- 완료된 dependency input-binding policy도
  `financial_dependency_projection.py`의 public slot-match, sibling-output
  preference, task-output binding 함수로 배치된다. 사전 source audit이 기존
  4-call 계획에서 누락된 reconciliation caller 3개를 찾아 총 7개 call을 모두
  graph-external로 retarget했고, owner-local selected call은 없다.
- 완료된 reconciliation artifact-reference projection도
  `financial_task_artifacts.py`의 public per-operand/general candidate-id와
  evidence-ref 함수, owner-private operand-surface matcher로 배치된다. 네 call은
  graph-external이고 matcher 한 call은 owner-local이다. candidate/cell selection,
  artifact creation/mutation, mutable reconciliation state와 final sequencing은
  graph에 남는다.
- 완료된 reflection request/plan projection은
  `financial_reflection_projection.py`의 public planner-record normalizer/request
  builder와 owner-private strict runtime/evidence summaries로 배치된다. 두 call은
  graph-external이고 summary 두 call은 owner-local이다. heuristic planning,
  prompt/model invocation, retry application, report/artifact ledger mutation,
  routing, mutable state/evidence와 final sequencing은 graph에 남는다.
- 완료된 dependency reconciliation preparation은
  `financial_dependency_projection.py`의 public sibling-surface와 resolved-result
  함수로 배치된다. 다섯 call은 모두 graph-external이며 dependency-state lookup,
  candidate/cell/evidence construction, LLM reranking, artifact/ledger mutation,
  mutable state/evidence와 final sequencing은 graph에 남는다.
- 완료된 prepared runtime-evidence/task-artifact row projection도
  `financial_task_artifacts.py`의 public evidence merge와 ratio result-row 함수로
  배치된다. 네 call은 모두 graph-external이며 operand/evidence selection, ratio
  conflict/arithmetic, artifact/ledger mutation, mutable state/evidence와 final
  sequencing은 graph에 남는다.
- 완료된 final-answer evidence projection도 같은 aggregate owner의 public
  `filter_aggregate_evidence_for_final_answer(...)`와
  `append_operand_evidence_for_final_answer(...)`로 배치된다. 일곱 call은 모두
  graph-external이며 retrieved evidence preparation, selected-claim/provenance,
  answer composition/refresh, artifact/ledger mutation, mutable state/evidence와
  final sequencing은 graph에 남는다.
- 완료된 growth-answer cleanup도 같은 aggregate owner의 public
  `ensure_complete_growth_numeric_answer(...)`와
  `strip_untraced_numeric_material_from_growth_narrative_sentence(...)`로
  배치된다. 19개 call은 모두 graph-external이며 final-growth selection,
  answer refresh/composition, compact-ratio state/trace, mutable state/evidence,
  artifact/ledger mutation과 final sequencing은 graph에 남는다.
- 완료된 final-answer surface operand projection도 같은 aggregate owner의
  public `append_final_answer_surface_operands_from_evidence(...)`로 배치된다.
  두 call은 모두 graph-external이며 prepared projection/evidence의 복사 기반
  operand와 stale growth-result 투영만 owner가 담당한다. 두 caller, evidence
  filtering/provenance adoption, public-answer/runtime-evidence preparation,
  retrieval/provenance construction, evidence-list mutation, mutable state,
  artifact/ledger mutation과 final sequencing은 graph에 남는다.
- 완료된 operand magnitude/unit batch는 public ontology lookup/magnitude coercion과
  row-block signature/same-block note-unit repair를 operand owner의 public 4개로
  배치한다. 15개 call은 external 12/local 3이며 lookup-record recovery,
  report-file/local-unit lookup, structured-cell selection, candidate extraction,
  mutable reconciliation state/artifact/retry와 final sequencing은 기존 owner에 남는다.
- 완료된 caller-facing run projection은 준비된 evidence metadata/citation,
  public agent-answer/review/debug bundle, structured missing-answer 선택,
  aggregate completion과 prepared public-answer state projection을 public 10개와
  owner-private 2개로 배치한다. 선택된 24개 call은 external 21/local 3이며
  runtime-evidence 선택/fallback, dynamic structured/stale answer repair, trace
  resolution/rebuild, graph execution, compatibility assembly, mutable state/evidence,
  artifact/ledger와 final sequencing은 graph에 남는다.
- 완료된 reconciliation-candidate batch는 prepared candidate metadata/unit/
  period/score/identity/row/match/ID projection 293줄을 새 owner의 public 7개와
  owner-private 4개로 옮겼다. 26개 call은 external 19/local 7이며 collection,
  structured-pair extraction, LLM rerank, evidence/state/artifact/retry는 graph에
  남는다.
- 완료된 reflection retry-query batch는 builder/finalizer 107줄을 기존
  reflection owner의 public 2개로 옮겼다. 세 call은 external 2/local 1이며
  heuristic dependency resolution, prompt/LLM planning, action/report/artifact,
  state/routing/promotion은 graph에 남는다.
- 완료된 aggregate subtask projection/upsert batch는 aggregate calculation/public
  projection과 subtask upsert/rank 156줄을 기존 aggregate owner의 public 3개와
  owner-private 1개, 실제 153줄로 옮겼다. 여섯 call은 external 4/local 2이며
  distinct runtime-trace private builder는 그대로 남는다.
- 완료된 nested selection/promotion batch는 traversal, operation/specificity
  scoring과 bounded selected-result promotion 128줄을 answer-projection owner의
  public 2개와 owner-private 2개, 실제 126줄로 옮겼다. 여섯 call은 external
  2/local 4이며 state/task capture와 broader replacement는 그대로 남는다.
- 완료된 aggregate-result batch는 nested-result replacement 64줄과 arithmetic
  subtask-surface sync 124줄을 aggregate owner의 public 2개, 실제 186줄로
  옮겼다. 네 call은 external 4/local 0이며 broader alignment/rebuild와 caller
  orchestration은 그대로 남는다.
- 완료된 duplicate growth-prior recovery는 calculation mixin의 53줄을
  aggregate owner의 public 52줄로 옮겼다. 한 call은 graph-external이고 owner
  public/private 함수 수는 73/11이다. Candidate preparation과 unit/period
  alignment, execution, state/evidence, rebuild, artifact/ledger와 final
  sequencing은 graph에 남는다.
- 완료된 final aggregate evidence/provenance projection은 calculation mixin의
  48줄을 aggregate owner의 public 47줄로 옮겼다. 두 call은 graph-external이고
  owner public/private 함수 수는 74/11이다. Focused 4/4, semantic 806/806,
  import 19/19, audit 217과 full 1,797/1,797이 통과했다.
- 완료된 collapsed-ratio runtime-trace repair는 calculation mixin의 310줄을
  runtime-trace owner의 public 309줄로 옮겼다. 두 call은 main graph external이고
  owner public/private 함수 수는 3/28이다. Focused 6/6, aggregate-subtask
  124/124, text-surface 20/20, semantic 832/832, import 19/19, audit 217과 full
  1,803/1,803이 통과했다.
- 완료된 direct structured-evidence batch는 calculation mixin의 lookup-row
  81줄과 operand-value coercion 139줄을 lookup-recovery owner의 public 80줄과
  138줄로 옮겼다. 다섯 call은 graph external이고 owner public/private 함수
  수는 11/7이다. Focused 4/4 per seam, combined 8/8, lookup owner 24/24,
  semantic 818/818, import 19/19, audit 217과 full 1,811/1,811이 통과했다.
- 완료된 own-evidence lookup-unit alignment는 calculation mixin의 62줄을
  aggregate owner의 public 61줄로 옮겼다. 두 call은 graph external이고 owner
  public/private 함수 수는 75/11이다. Focused 4/4, aggregate owner 88/88,
  semantic 882/882, import 19/19, audit 217과 full 1,815/1,815가 통과했다.
- 완료된 deterministic-plan batch는 calculation mixin의 runtime adapter
  37줄과 ontology plan 200줄을 calculation-execution owner의 public 36줄과
  195줄로 옮겼다. 네 call은 graph external이고 owner public/private 함수
  수는 13/0이다. Focused 9/9, execution owner 45/45, semantic 883/883,
  import 19/19, audit 217과 full 1,824/1,824가 통과했다. Dynamic metric-family
  dispatch, lookup/LLM planning, state/trace/artifact update, execution
  orchestration과 final sequencing은 graph에 남는다.
- 완료된 query-focus/text-surface batch는 retrieval/calculation mixin의
  85+8+127 definition-span 줄을 text owner의 public 85+8+126줄로 옮겼다.
  열두 call은 external 10/local 2이고 owner public/private 함수 수는 15/4다.
  Focused 10/10, text owner 30/30, semantic 808/808, import 19/19, audit 218과
  full 1,834/1,834가 통과했다.
- 완료된 structured period-pair batch는 reconciliation mixin의 202줄을
  reconciliation-candidate owner의 public 201줄로 옮겼다. 유일한 call은 graph
  external이고 owner public/private 함수 수는 8/4다. Focused 6/6, candidate
  owner 14/14, semantic 787/787, import 19/19, audit 218과 full 1,840/1,840가
  통과했다. Full operand extraction, candidate collection/selection, LLM
  rerank, evidence/state/artifact/ledger와 final sequencing은 graph에 남는다.
- 완료된 semantic-planner normalization/validation batch는 planning의 scope,
  plan-shape, segment-label, task-validation 정의 273줄을
  `financial_graph_helpers.py`의 public 5/owner-private 3, 271줄로 옮겼다.
  열여섯 call은 external 9/local 7이고 helper owner 함수 수는 5/132다.
  Focused 7/7, helper owner 12/12, semantic 434/434, import 19/19, audit 218과
  full 1,847/1,847이 통과했다. LLM/model invocation, plan adoption,
  task/state/artifact/ledger와 final sequencing은 graph에 남는다.
- 완료된 narrative-task policy batch는 planning의 정의 143줄을
  `financial_graph_helpers.py`의 public 4/owner-private 2로 옮겼다. 열세
  call은 external 6/local 7이고 helper owner 함수 수는 9/134다. Focused
  6/6, helper owner 18/18, semantic 440/440, import 19/19, audit 218과 full
  1,853/1,853이 통과했다. Model invocation, plan adoption, task/state/
  artifact/ledger와 final sequencing은 graph에 남는다.
- 완료된 lookup answer-slot/support batch는 planning의 정의 342줄과 policy
  regex binding 3개를 `financial_lookup_recovery.py`의 public 4/owner-private
  6으로 옮겼다. 열다섯 call은 external 6/local 9이고 owner 함수 수는
  public/private 15/13이다. Focused 8/8, owner 32/32, semantic 864/864,
  import 19/19, audit 218과 full 1,861/1,861이 통과했다. Retrieval pool,
  mutable result/evidence/state, orchestration과 final sequencing은 graph에 남는다.
- 다음 선택은 evidence mixin의 focus-term 40줄, preferred-section subset 59줄,
  compression guidance 18줄을 `financial_retrieval_hints.py`의 public 3으로
  이동하는 한 batch다. 세 call은 external 3/local 0으로 유지되며 exact
  boundary와 hard stop은
  [Project Status의 Next Work](project_status.md#next-work)만 기준으로 삼는다.

### `src/agent/financial_graph_helpers.py`

여러 mixin이 공유하는 runtime helper 묶음이다. 현재는 helper surface가 아직 크기
때문에, 읽을 때 목적별로 들어가야 한다.

- task/artifact projection
- runtime calculation trace construction and metadata
- `structured_result` / `resolved_calculation_trace` compatibility projection
- source row/evidence id cleanup
- numeric parsing and unit normalization helpers
- retrieval hint / operand matching helpers
- semantic planner scope normalization, plan-shape validation, segment-label
  projection, and planner-task contract helpers
- narrative-task predicate, construction, append, dependency-order, and
  exclusive-policy projection; model invocation and state/task adoption remain
  outside

`_preferred_complete_aggregate_subtask_answer`는 compatibility를 위해 여기서
re-export되지만 실제 구현은 `financial_answer_projection.py`에 있다.

### Calculation owner index

계산 owner의 현재 역할은 위
[Calculation Layer](#8-calculation-layer) 표를 사용한다. 이 section에서는 같은
owner 계약을 반복하지 않는다. Public API의 정확한 semantics는
[Agent Runtime Contract](../architecture/agent_runtime_contract.md), 파일별 위치는
[Codebase Map](codebase_map.md)을 따른다.

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

MAS는 single-agent runtime을 typed task/artifact ledger로 감싸는 optional
experimental 축이다. 새 caller의 public import boundary는
`src.experimental.mas` facade다.

### `src.experimental.mas`

- `graph.py`: `build_initial_state(...)`, `build_mas_graph(...)`,
  `run_mas_graph(...)`를 노출한다.
- `types.py`: `AgentTask`, `Artifact`, `EvidenceRecord`, `CriticReport`,
  `FinalReport`, `MultiAgentState`와 typed constructor/projection을 노출한다.
- `nodes.py`: orchestrator, analyst, researcher, critic node factory를 노출한다.
- `diagnostics.py`: opt-in diagnostic helper만 노출한다.

현재 facade 구현은 compatibility를 위해 `src.agent.mas_graph`,
`src.agent.mas_types`, `src.agent.nodes.*`에 위임한다. 이 legacy module들은
새 caller의 owner/import surface가 아니며, 검증된 compatibility caller가 남아
있는 동안의 implementation detail이다. Analyst node는 numeric task를 기존
`FinancialAgent.run()`에 위임한다.

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
- `src/ops/portfolio_fixture_contract.py::evaluate_fixture_contract()`:
  curated fixture의 manifest binding과 cross-surface contract를 판정한다.
- `src/ops/portfolio_demo.py::build_demo()`: 판정 결과를 reviewer-facing demo
  projection으로 구성하고 CLI renderer에 전달한다.
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
7. `src/agent/financial_retrieval_pipeline.py::FinancialRetrievalPipelineMixin`
8. `src/agent/financial_graph_evidence.py::FinancialAgentEvidenceMixin`
9. `src/agent/financial_graph_reconciliation.py::FinancialAgentReconciliationMixin`
10. `src/agent/financial_graph_calculation.py::FinancialAgentCalculationMixin`
11. `src/agent/financial_operand_resolution.py`
12. `src/agent/financial_dependency_projection.py`
13. `src/agent/financial_task_artifacts.py`
14. `src/agent/financial_reflection_projection.py`
15. `src/agent/financial_calculation_execution.py`
16. `src/agent/financial_answer_projection.py`
17. `src/processing/financial_parser.py::FinancialParser.process_document`
18. `src/storage/vector_store.py::VectorStoreManager.search`
19. `src/ops/benchmark_runner.py`와 `src/ops/evaluator.py`
20. MAS가 필요할 때만 `src.experimental.mas` facade; legacy `src.agent` 구현은 compatibility 확인 시에만

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
