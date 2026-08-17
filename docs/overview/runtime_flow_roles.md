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

현재 ontology/policy 기반 statement type, preferred section, query suffix,
prepared metric/operand query-match projection과 active-subtask section
hint뿐 아니라 query focus-term, preferred-section
evidence subset, compression guidance를 state-free하게 투영한다. 검색 실행,
document/context/evidence construction과 ranking, prompt/model invocation,
state adoption은 evidence/retrieval graph에 남는다.

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
| `financial_operand_resolution.py` | candidate-to-operand matching, direct-match-strength and complete deterministic operand-candidate scoring, direct-candidate semantic-priority projection, canonical-statement-winner, ratio-component and direct acceptance, and direct-grounding classification plus candidate merge/adoption, lookup-hint projection/matching, direct candidate logical/family signature, location/entity subject-score projection, deterministic positional preference scoring, unit and period coercion, dependency-task KRW consistency, table-metadata/raw-unit repair, growth raw-scale alignment/period conflict, ratio display alignment, and denominator sign policy |
| `financial_dependency_projection.py` | dependency precedence/projection, recalculation disposition, provenance and source-slot consistency, plus dependency input matching, sibling-output synthesis preference, and task-output binding projection; dependency-task KRW-consistency implementation and ownership moved to the operand owner |
| `financial_reconciliation_candidates.py` | prepared candidate/cell statement, unit, period, score, identity, operand-row, match, candidate-ID, and structured period-pair projection; full operand extraction, collection, reranking, evidence construction, retry, and state mutation remain outside |
| `financial_calculation_execution.py` | state-free base/runtime operation and ontology plan construction, validation/guard, formula execution, and stale-value assessment; dynamic metric-family selection, lookup/LLM planning, and state projection remain graph-owned |
| `financial_answer_slots.py` | answer-slot construction, shared slot-material/period policy, ratio consolidation/collapse/completeness, and source display compatibility |
| `financial_answer_projection.py` | aggregate-row growth-period conflict, material-gap, row-material, nested-row traversal/operation/specificity and bounded selected-result promotion, narrative intent/surface/trace validation, and final-answer projection policy |
| `financial_numeric_surface.py` | numeric extraction/equivalence, answer/reference comparison, table support, numeric-support predicates, and ratio scale checks |
| `financial_text_surface.py` | shared token/sentence normalization, Korean particle polishing, narrative term/variant/context presentation, prepared-document snippet projection, retrieved-source preservation, query-focus marker projection, source-visible term preservation, and table-noise/fragment predicates |
| `financial_lookup_recovery.py` | lookup magnitude, selected-evidence consistency, refinement eligibility, unit normalization, successful-row alignment/replacement, direct structured-row/value projection, active-task matching, prose answer-slot synthesis, and supporting-document projection over supplied evidence |
| `financial_retrieval_hints.py` | ontology/policy-backed statement, section, and query hints plus read-only evidence focus/subset/compression guidance and query-to-prepared-metric/operand matching; retrieval execution, context/evidence construction and ranking, model invocation, and state adoption remain graph-owned |
| `financial_scope_policies.py` | report/consolidation scope, single-report-scope classification, public query/task and generic operand target-year/period-focus policy, candidate report/year matching and binding bonuses, and candidate period/table coherence scoring |
| `financial_operation_policies.py` | state-free operation-family and numeric-grounding policy over supplied query/task data; marker vocabulary remains in retrieval policy/config, and the final private visibility seam is `requires_direct_numeric_grounding(...)` |
| `financial_surface_contracts.py` | operand needles/public segment-label projection, positive/negative surface-term contracts, candidate concept-conflict, contextual-aggregate preference, candidate required/numeric/descriptor projection, segment-surface matching/bonuses, local aggregate context, consolidation scope, binding-shape admission, selected-unit-family projection, and scoped surface-affinity scoring over supplied items |
| `financial_row_surfaces.py` | row/table text matching and parsing, column-candidate and delta-like row-label classification, aggregate-like row stage/role and candidate value-role/stage projection, candidate operand-context and structured-sibling projection, segment-local binding, segment-metric composition, and sibling-surface hit counting |
| `financial_structured_cells.py` | fiscal ordinal/rank, period-text, ordinary/aggregate cell selection, candidate selected-cell preparation, public scoring, and owner-private operand affinity |
| `financial_aggregate_projection.py` | aggregate signatures, primary/source/coherence and dependency-source preparation, result/nested ranks, stable dedupe, repair/projection transforms, duplicate growth-prior recovery, final evidence/provenance projection, own-evidence lookup-unit alignment, compact prompt rows, row/sentence/rendered selectors, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering, result support/reuse predicates, final-answer evidence filter/operand append/surface-operand projection, and deterministic quantitative-impact parsing/composition |
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
- 완료된 read-only evidence-hint batch는 evidence mixin의 focus-term 40줄,
  preferred-section subset 59줄, compression guidance 18줄을
  `financial_retrieval_hints.py`의 public 3으로 옮겼다. 세 call은 external
  3/local 0이고 owner 함수 수는 public/private 3/9다. Focused 5/5,
  semantic 692/692, import 19/19, audit 218과 full 1,866/1,866이 통과했다.
   Context/evidence construction, model invocation, mutable state와 final
   sequencing은 graph에 남는다.
- 완료된 quantitative-impact batch는 evidence mixin의 labeled-numeric parser
  33줄과 supported composer 195줄을 `financial_aggregate_projection.py`의
  owner-private 33줄/public 194줄로 옮겼다. 네 call은 external 3/local 1이고
  owner 함수 수는 public/private 76/12다. Focused 5/5, owner 93/93, semantic
  812/812, import 19/19, audit 218과 full 1,871/1,871이 통과했다.
  Validation/model fallback, evidence selection, mutable composition state와
  final sequencing은 graph에 남는다.
- 완료된 generic operand-period/structured-cell ownership batch는 정확한
  285줄 graph-helper surface를 scope/structured-cell owner의 public 5와
  owner-private 1로 옮겼다. 선택된 57개 call은 external 53/local 4이며
  combined focused 10/10, semantic 838/838, import 19/19, audit 218, full
  1,881/1,881이 통과했다. Candidate/evidence construction, direct structured
  lookup/value projection, reconciliation orchestration, state/callback/carrier/
  ledger와 final sequencing은 graph owner에 남는다.
- 완료된 candidate report/period-scope batch는 graph helper의 정확한 228줄을
  `financial_scope_policies.py`의 public 4와 owner-private 2로 옮겼다. 18개
  call은 external 10/local 8이고 owner public/private 함수 수는 7/9다.
  Focused 6/6, semantic 844/844, import 19/19, audit 218, full 1,887/1,887이
  통과했다. Broad operand scoring/reconciliation, candidate/evidence
  construction/adoption, state/callback/carrier/ledger와 final sequencing은
  graph owner에 남는다.
- 완료된 candidate surface-contract/segment-binding batch는 graph helper의
  정확한 128줄을 `financial_surface_contracts.py`의 public 5와 owner-private
  1로 옮겼다. Reconciliation의 descriptor call을 포함한 17개 call은
  external 15/local 2이고 owner public/private 함수 수는 5/7이다. Focused
  6/6, owner 41/41, semantic 851/851, import 19/19, audit 218, full
  1,893/1,893이 통과했다. Direct/ratio acceptance, broad scoring/
  reconciliation, candidate/evidence construction/adoption, state/callback/
  carrier/ledger와 final sequencing은 graph owner에 남는다.
- 완료된 candidate metadata-policy batch는 graph helper의 정확한 116줄을
  `financial_surface_contracts.py`의 public 4로 옮겼다. Local aggregate
  context 3개, consolidation scope 2개, binding-policy shape 2개, selected unit
  family 1개 호출은 external 8/local 0으로 유지되고 owner public/private
  함수 수는 9/7이다. Focused 6/6, owner 47/47, semantic 857/857, import
  19/19, audit 218, full 1,899/1,899이 통과했다. Aggregate row-role/stage
  inference, direct/ratio acceptance, broad
  scoring/reconciliation, candidate/evidence construction/adoption, mutable
  state, callback, carrier, ledger와 final sequencing은 graph owner에 남는다.
- 완료된 segment-local/segment-metric batch는 graph helper의 정확한 7/15줄
  정의를 `financial_row_surfaces.py`의 public 두 함수로 옮겼다. Call은
  external 2/local 1이고 owner public/private는 2/15, graph helper는 9/110이다.
  Focused 4/4, owner 51/51, semantic 861/861, import 19/19, audit 218, full
  1,903/1,903과 pycompile/fresh import, AST/caller/DAG parity가 통과했다.
  Aggregate row/value role-stage, direct/ratio acceptance, broad scoring/
  reconciliation, state/evidence/ledger와 final sequencing은 graph에 남는다.
- 완료된 aggregate-like row stage/role batch는 graph helper의 정확한 10/2줄
  정의를 `financial_row_surfaces.py`의 public 두 함수로 옮겼다. Call은
  external 5/local 1이고 owner public/private는 4/15, graph helper는 9/108이다.
  Focused 4/4, owner 55/55, semantic 865/865, import 19/19, audit 218, full
  1,907/1,907과 pycompile/fresh import, AST/caller/DAG parity가 통과했다.
  Candidate value-role/stage 16/18줄과 각 11 call, direct/ratio acceptance,
  matching/scoring, state/evidence/ledger와 final sequencing은 graph에 남는다.
- 완료된 lookup-hint projection/match batch는 graph helper의 정확한
  5/14/7/5줄 네 정의를 `financial_operand_resolution.py`의 public API로
  옮겼다. Call은 graph-external 16/owner-local 1이고 graph helper public/
  private는 9/104, operand resolution은 41/37이다. Focused 4/4, owner
  127/127, semantic 938/938, import 19/19, audit 218, full 1,911/1,911과
  pycompile/fresh import/public identity, AST/caller/DAG parity가 통과했다.
  Lookup task construction, candidate admission/scoring, retry assembly,
  state/evidence/ledger와 final sequencing은 graph에 남는다.
- 완료된 direct candidate-signature batch는 graph helper의 정확한 26/22줄
  pair를 `financial_operand_resolution.py`의 public API로 옮겼다. Call은
  graph-external 2/owner-local 0이고 block-signature call은 external 4/local
  3이다. Graph helper public/private는 9/102, operand resolution은 43/37이다.
  Focused 4/4, owner 131/131, semantic 942/942, import 19/19, audit 218, full
  1,915/1,915와 pycompile/fresh import/public identity, AST/caller/DAG parity가
  통과했다. Direct acceptance, collapse, sibling/canonical/semantic/score,
  state/evidence/ledger와 final sequencing은 graph에 남는다.
- 완료된 `a530033` sibling-surface hit-count batch는 graph helper의 정확한 30줄
  projection을 `financial_row_surfaces.py`의 public API로 옮겼다. 세 call은
  sorted-key, top-hit, positive-top filter 위치에서 external 3/local 0을
  유지한다. Graph helper public/private는 9/101, row surfaces는 5/15다.
  Focused 4/4, owner 67/67, semantic 946/946, import 19/19, audit 218, full
  1,919/1,919과 pycompile/fresh import/public identity, AST/caller/DAG parity가
  통과했다. Sibling-list preparation, rank/filter adoption, canonical/
  semantic/score policy, state/evidence/ledger와 final sequencing은 graph에
  남는다.
- 완료된 `8e4dca4` query-to-metric/operand match batch는 graph helper의 정확한
  6/14줄 pair를 `financial_retrieval_hints.py`의 public API로 옮겼다. 네
  call은 strong-metric, target component/mention, task-loop weak-match 위치에서
  external 4/local 0을 유지한다. Graph helper public/private는 9/99,
  retrieval hints는 5/9다. Focused 4/4, owner 75/75, semantic 955/955, import
  19/19, audit 218, full 1,923/1,923과 pycompile/fresh import/public identity,
  AST/caller/DAG parity가 통과했다. Ontology/formula policy, metric admission,
  task/query construction, state/evidence/ledger와 final sequencing은 graph에
  남는다.
- 완료된 `55bc286` period-focus batch는 graph helper의 정확한 11/25줄
  query/task pair를 `financial_scope_policies.py`의 public API로 옮겼다.
  여섯 call은 hybrid, concept, heuristic, metric-task constraint builder에서
  external 6/local 0을 유지한다. Graph helper public/private는 9/97, scope
  policy는 9/9다. Focused 4/4, owner 74/74, semantic 1,034/1,034, import
  19/19, audit 218, full 1,927/1,927과 pycompile/fresh import/public identity,
  AST/caller/DAG parity가 통과했다. Consolidation/default, operation/operand/
  task/query construction, candidate ranking/admission, state/evidence/ledger와
  final sequencing은 graph에 남는다.
- 완료된 `9092f5e` candidate value-role/aggregation-stage batch는 graph
  helper의 정확한 16/18줄 pair를 `financial_row_surfaces.py`의 public API로
  옮겼다. 각 함수의 11개 call, 총 22개 call은 semantic priority, direct
  grounding/acceptance, ratio acceptance, matching, direct strength, scoring
  위치에서 external 22/local 0을 유지한다. Graph helper public/private는
  9/95, row surfaces는 7/15다. Focused 4/4, owner 78/78, semantic
  1,038/1,038, import 19/19, audit 218, full 1,931/1,931과 pycompile/fresh
  import/public identity, AST/caller/DAG parity가 통과했다. Admission,
  matching/strength, semantic priority, scoring/ranking, state/evidence/ledger와
  final sequencing은 graph에 남는다.
- 완료된 `78e3508` candidate row-context batch는 graph helper의 정확한
  15/19줄 candidate operand-context/table-row structured-sibling pair를 같은
  row owner의 public API로 옮겼다. 두 call은 direct strength와 direct
  grounding에서 external 2/local 0을 유지한다. Graph helper public/private는
  9/93, row surfaces는 9/15다. Focused 4/4, owner 82/82, semantic
  1,042/1,042, import 19/19, audit 218, full 1,935/1,935와 pycompile/fresh
  import/public identity, AST/caller/DAG parity가 통과했다. Direct acceptance,
  matching/strength, scoring/ranking, state/evidence/ledger와 final sequencing은
  graph에 남는다.
- 완료된 `0bfa1f0` candidate selected-cell batch는 graph helper의 정확한
  21줄 preparation projection을 `financial_structured_cells.py`의 public
  API로 옮겼다. Sole call은 deterministic reconciliation에서 external 1/
  local 0을 유지하고, selector call은 external 6/local 1이다. Graph helper
  public/private는 9/92, structured cells는 4/4다. Focused 4/4, owner 86/86,
  semantic 1,046/1,046, import 19/19, audit 218, full 1,939/1,939와
  pycompile/fresh import/public identity, AST/caller/DAG parity가 통과했다.
  Direct acceptance, signatures, matching/scoring, state/evidence/ledger와
  final sequencing은 graph에 남는다.
- 완료된 `2b0e9c1` scoped surface-affinity batch는 graph helper의 정확한
  56줄 projection을 `financial_surface_contracts.py`의 public API로 옮겼다.
  두 call은 evidence prioritization과 coherent ratio-context scoring에서
  external 2/local 0을 유지하고 selected operand-segment dependency는 owner-
  local이다. Graph helper public/private는 9/91, surface contracts는 10/7이다.
  Focused 4/4, owner 90/90, semantic 1,050/1,050, import 19/19, audit 218,
  full 1,943/1,943와 pycompile/fresh import/public identity, AST/caller/DAG
  parity가 통과했다. Caller eligibility/schema score, evidence/operand-row
  construction, acceptance, broader ranking/adoption과 state/evidence/ledger는
  graph 또는 caller에 남는다.
- 완료된 `7ec0cc3` candidate period/table coherence batch는 graph helper의
  정확한 30줄 projection을 `financial_scope_policies.py`의 public API로
  옮겼다. Sole call은 operand scorer에서 external 1/local 0을 유지하고
  explicit-year/target-year dependency는 external/local 0/5와 8/6으로
  수렴했다. Graph helper public/private는 9/90, scope policy는 10/9다.
  Focused 4/4, owner 94/94, semantic 1,054/1,054, import 19/19, audit 218,
  full 1,947/1,947와 pycompile/fresh import/public identity, AST/caller/DAG
  parity가 통과했다. Candidate/year extraction, target-year policy, 다른
  scoring, acceptance/ranking/adoption과 state/evidence/ledger는 graph 또는
  기존 owner에 남는다.
- 완료된 `23f08b2` candidate location/entity subject-score batch는 graph
  helper의 정확한 53줄 projection을 `financial_operand_resolution.py`의
  public API로 옮겼다. Sole call은 operand scorer에서 external 1/local 0을
  유지한다. Graph helper public/private는 9/89, operand resolution은
  44/37이다. Focused 4/4, owner 98/98, semantic 1,058/1,058, import 19/19,
  audit 218, full 1,951/1,951와 pycompile/fresh import/public identity,
  AST/caller/DAG parity가 통과했다. 다른 scoring, matching/acceptance/ranking/
  adoption과 state/evidence/ledger는 graph 또는 기존 owner에 남는다.
- 완료된 `e04a7bf` delta-like row-label batch는 graph helper의 정확한 7줄
  classifier를 `financial_row_surfaces.py`의 public API로 옮겼다. 세 call은
  direct grounding과 operand scorer에서 external 3/local 0으로 수렴했다.
  Graph helper public/private는 9/88, row surfaces는 10/15이다. Focused 4/4,
  owner 102/102, semantic 1,062/1,062, import 19/19, audit 218, full
  1,955/1,955와 pycompile/fresh import/public identity, AST/caller/DAG parity가
  통과했다. Period policy, broader scoring, matching/acceptance/ranking/adoption과
  state/evidence/ledger는 graph 또는 기존 owner에 남는다.
- 완료된 `c4558b7` preference-bonus batch는 graph helper의 정확한 7줄
  projection을 `financial_operand_resolution.py`의 public API로 옮겼다. 두
  scorer call은 external 2/local 0으로 수렴했다. Graph helper public/private는
  9/87, operand resolution은 45/37이다. Focused 4/4, owner 106/106, semantic
  1,066/1,066, import 19/19, audit 218, full 1,959/1,959와 pycompile/fresh
  import/public identity, AST/caller/DAG parity가 통과했다. Caller collection,
  다른 scoring, matching/acceptance/ranking/adoption과 state/evidence/ledger는
  graph 또는 기존 owner에 남는다.
- 완료된 `0dc278e` column-candidate-label batch는 graph helper의
  정확한 10줄 projection을 `financial_row_surfaces.py`의 public API로
  옮겼다. Sole call은 table-column reconciliation candidate builder에서
  external 1/local 0으로 수렴했다. Graph helper public/private는 9/86,
  row surfaces는 11/15이다. Focused 4/4, owner 110/110, semantic
  1,070/1,070, import 19/19, audit 218, full 1,963/1,963과 pycompile/fresh
  import/public identity, AST/caller/DAG parity가 통과했다. Audit은 기존
  year regex의 owner-path 이동을 감지해 literal/count와 218개 total은
  그대로 두고 baseline path/fingerprint/line만 교정했다. Row/cell
  preparation, grouping/candidate construction, matching/scoring/acceptance,
  state/evidence/ledger는 graph 또는 기존 owner에 남는다.
- 완료된 `471f6a5` single-report-scope batch는 graph helper의 정확한 8줄
  predicate를 `financial_scope_policies.py`의 public API로 옮겼다. Sole call은
  `align_scope_hints(...)`의 company-scope branch에서 external 1/local 0으로
  수렴했다. Graph helper public/private는 9/85, scope policies는 11/9이다.
  Focused 4/4, owner 114/114, semantic 1,074/1,074, import 19/19, audit 218,
  full 1,967/1,967과 pycompile/fresh import/public identity, AST/caller/DAG
  parity가 통과했다. Company/year alignment, report inventory/selection,
  candidate/evidence construction, file I/O와 state/evidence/ledger는 graph
  또는 기존 owner에 남는다.
- 완료된 `4c8c89c` candidate-concept-conflict batch는 두 inline marker를
  retrieval policy의 단일 constant로 분류하고 graph helper의 정확한 27줄
  predicate를 `financial_surface_contracts.py`의 public API로 옮겼다. 세 call은
  candidate matching/direct strength/scoring에서 external 3/local 0으로
  수렴했다. Graph/surface public/private는 9/84와 11/7이다. Focused 4/4,
  owner 118/118, semantic 1,078/1,078, import 19/19, audit 217, full
  1,971/1,971과 pycompile/fresh import/public identity, policy-normalized body,
  caller/DAG parity가 통과했다. Marker grouped record가 runtime에서 제거되어
  reviewed baseline은 218에서 217로 줄었다. Other matching, scoring,
  acceptance, construction/adoption과 state/evidence/ledger는 graph 또는 기존
  owner에 남는다.
- 완료된 `c837e31` contextual-aggregate-preference batch는 graph helper의
  정확한 17줄 predicate를 `financial_surface_contracts.py`의 public API로
  옮겼다. 세 call은 source priority, candidate matching, direct strength에서
  external 3/local 0으로 수렴했다. Graph/surface public/private는 9/83과
  12/7이다. Focused 4/4, owner 122/122, semantic 1,082/1,082, import 19/19,
  audit 217, full 1,975/1,975와 pycompile/fresh identity, body/caller/DAG
  parity가 통과했다. Caller contextual branches, other matching/scoring,
  candidate/evidence work와 state/artifact/ledger는 graph 또는 기존 owner에
  남는다.
- 완료된 `f35be1a` balance-sheet-aggregate-operand batch는 graph helper의
  정확한 9줄 predicate를 `financial_surface_contracts.py`의 public API로
  옮겼다. 두 call은 source priority와 direct acceptance에서 external 2/local
  0으로 수렴했다. Graph/surface public/private는 9/82와 13/7이다. Focused
  4/4, owner 126/126, semantic 1,086/1,086, import 19/19, audit 217, full
  1,979/1,979와 pycompile/fresh identity, body/caller/DAG parity가 통과했다.
  Caller scoring/acceptance, other predicates, candidate/evidence work와 state/
  artifact/ledger는 graph 또는 기존 owner에 남는다.
- 완료된 `cefde44` CAPEX-total-operand batch는 inline ontology key를 retrieval
  policy의 `CAPEX_TOTAL_CONCEPT_KEY`로 명명하고 graph helper의 정확한 13줄
  predicate를 `financial_surface_contracts.py`의 public API로 옮겼다. 네 call은
  source priority, direct acceptance, candidate matching, direct strength에서
  external 4/local 0으로 수렴했다. Graph/surface public/private는 9/81과
  14/7이다. Focused 4/4, owner 130/130, semantic 1,090/1,090, import 19/19,
  audit 217, full 1,983/1,983과 pycompile/fresh identity, policy-normalized
  body/caller/DAG parity가 통과했다. Caller scoring/acceptance/matching/strength,
  candidate/evidence work와 state/artifact/ledger는 graph 또는 기존 owner에
  남는다.
- 완료된 `1119ac3` note-aggregate lookup-preference batch는 graph helper의
  정확한 23줄 predicate를 `financial_surface_contracts.py`의 public API로
  옮겼다. 한 call은 source priority에서 external 1/local 0으로 수렴했다.
  Graph/surface public/private는 9/80과 15/7이다. Focused 4/4, owner 134/134,
  semantic 1,094/1,094, import 19/19, audit 217, full 1,987/1,987과
  pycompile/fresh identity, body/caller/DAG parity가 통과했다. Source-priority
  score branch와 전체 candidate scoring, candidate/evidence work 및 state/
  artifact/ledger는 graph 또는 기존 owner에 남는다.
- 완료된 `334fff0` candidate source-priority batch는 graph helper의 정확한
  76줄 scorer를
  `financial_operand_resolution.candidate_source_priority_bonus(...)` public
  API로 옮겼다. 한 call은 broad graph scorer에서 external 1/local 0으로
  수렴했다. Graph/operand-resolution public/private는 9/79와 46/37이다.
  Focused 4/4, owner 138/138, semantic 1,098/1,098, import 19/19, audit 217,
  full 1,991/1,991과 body/caller/DAG parity가 통과했다. Broad candidate
  scoring, period/table/report score, acceptance/ranking, candidate/evidence와
  state/artifact/ledger는 graph 또는 기존 owner에 남는다.
- 완료된 `1a24bc1` candidate-to-operand matching batch는 graph helper의 정확한
  83줄 predicate를
  `financial_operand_resolution.candidate_matches_operand(...)` public API로
  옮겼다. Pre-move 문서의 one-caller inventory를 live source 기준으로 교정해
  deterministic graph filter, active reconciliation rerank filter, ops
  ontology-shadow filter 세 곳을 모두 갱신했다. Graph/operand-resolution
  public/private는 9/78과 47/37이다. Focused 4/4, owner 142/142, semantic
  1,102/1,102, reconciliation plan 51/51, import 19/19, audit 217, full
  1,995/1,995와 body/caller/DAG parity가 통과했다. Candidate construction,
  direct/ratio acceptance, direct strength, broad ranking/adoption과 state/
  artifact/ledger는 graph 또는 기존 owner에 남는다.
- 완료된 `91ceae7` candidate direct-match-strength batch는 graph helper의
  정확한 122줄 scorer를
  `financial_operand_resolution.candidate_direct_match_strength(...)` public
  API로 옮겼다. 여섯 graph caller의 여덟 call은 external 8/local 0으로
  수렴했고 threshold/addition/tuple 위치는 유지됐다. Graph/operand-resolution
  public/private는 9/77과 48/37이다. Focused 4/4, graph owner 146/146,
  operand owner 69/69, semantic 1,106/1,106, reconciliation plan 51/51, import
  19/19, audit 217, full 1,999/1,999와 body/caller/48-module/203-edge DAG
  parity가 통과했다. Direct/ratio acceptance, semantic priority, broad scoring/
  ranking, candidate/evidence와 state/artifact/ledger는 graph 또는 기존 owner에
  남는다.
- 완료된 `1be4cad` direct-candidate semantic-priority batch는 graph helper의
  정확한 53줄 projection을 public
  `financial_operand_resolution.direct_candidate_semantic_priority(...)`로
  옮겼다. 한 graph caller의 세 call은 external 3/local 0으로 수렴했고
  sort-key, top/next recompute, strict compare, fallback/collapse/adoption은
  유지됐다. Graph/operand-resolution public/private는 9/76과 49/37이다.
  Focused 4/4, graph owner 150/150, operand owner 69/69, semantic
  1,110/1,110, reconciliation plan 51/51, import 19/19, audit 217, full
  2,003/2,003과 body/caller/48-module/204-edge DAG parity가 통과했다. Collection
  sorting, acceptance, broad scoring/ranking, candidate/evidence와
  state/artifact/ledger는 graph 또는 기존 owner에 남는다.
- 완료된 `73a049c` canonical-statement-winner batch는 graph helper의 정확한
  42줄 predicate를 public
  `financial_operand_resolution.candidate_is_canonical_statement_winner(...)`로
  옮겼다. 한 graph call은 external 1/local 0으로 수렴했고 direct-entry
  dictionary order, `canonical_winner` 저장과 후속 rank/collapse/adoption은
  유지됐다. Graph/operand-resolution public/private는 9/75와 50/37이다.
  Focused 4/4, graph owner 154/154, operand owner 69/69, semantic
  1,114/1,114, reconciliation plan 51/51, import 19/19, audit 217, full
  2,007/2,007과 body/caller/48-module/204-edge DAG parity가 통과했다.
  Direct-entry construction, acceptance, broad scoring/ranking,
  candidate/evidence와 state/artifact/ledger는 graph 또는 기존 owner에 남는다.
- 완료된 `20feddc` ratio-component-acceptance batch는 graph helper의 정확한
  68줄 predicate를 public
  `financial_operand_resolution.candidate_satisfies_ratio_component_acceptance_contract(...)`로
  옮겼다. 세 reconciliation call은 external 3/local 0으로 수렴했고 first-hit
  return, combined-condition `continue`, later fallback assignment와 same-block/
  candidate/cell adoption은 유지됐다. Graph/operand-resolution public/private는
  9/74와 51/37이다. Focused 4/4, graph owner 158/158, operand owner 69/69,
  semantic 1,118/1,118, reconciliation plan 51/51, import 19/19, audit 217,
  full 2,011/2,011과 body/caller/48-module/204-edge DAG parity가 통과했다.
  Cell preparation/selection, direct acceptance, sorting/scoring, evidence와
  state/artifact/ledger는 reconciliation 또는 기존 owner에 남는다.
- 완료된 `4c422ed` direct-grounding batch는 graph helper의 정확한 86줄
  predicate를 public
  `financial_operand_resolution.candidate_is_direct_grounding_candidate(...)`로
  옮겼다. Graph와 reconciliation의 세 call은 external 3/local 0으로
  수렴했고 direct-acceptance first rejection, ordered non-lookup filtering,
  unique/ambiguous fallback, first-hit/ratio-cell fallback과 candidate/cell
  adoption은 유지됐다. Graph/operand-resolution public/private는 9/73과
  52/37이다. Focused 4/4, graph owner 162/162, operand owner 69/69, semantic
  1,122/1,122, reconciliation plan 51/51, import 19/19, audit 217, full
  2,015/2,015와 body/caller/48-module/204-edge DAG parity가 통과했다.
  Candidate/cell construction, direct/ratio acceptance, sorting/scoring,
  evidence와 state/artifact/ledger는 caller 또는 기존 owner에 남는다.
- 완료된 `6ebcf59` direct-acceptance batch는 graph helper의 정확한 161줄
  predicate를 public
  `financial_operand_resolution.candidate_satisfies_direct_acceptance_contract(...)`로
  옮겼다. Graph reconciliation, nested reconciliation과 period-pair projection의
  다섯 call은 public owner에 수렴했고 direct-then-ratio laziness, rejection
  stop, pair score/append, fallback과 candidate/cell adoption은 유지됐다.
  Graph/operand-resolution public/private는 9/72와 53/37이다. Focused 4/4,
  graph owner 166/166, operand owner 69/69, semantic 1,126/1,126,
  reconciliation plan 51/51, import 19/19, audit 217, full 2,019/2,019와 body/
  caller/48-module/205-edge DAG parity가 통과했다. Candidate/cell construction,
  ratio acceptance, broad scoring/ranking, evidence와 state/artifact/ledger는
  caller 또는 기존 owner에 남는다.
- 완료된 `3d6986e` operand-candidate scorer batch는 graph helper의 정확한
  315줄 scorer를 public
  `financial_operand_resolution.score_operand_candidate(...)`로 옮겼다.
  일곱 call은 public owner에 수렴했고 exact input, sorting/key/score storage,
  pair selection, fallback/adoption과 exception stop은 네 caller 모듈에
  유지됐다. Graph/operand-resolution public/private는 9/71과 54/37이다.
  Focused 4/4, graph owner 170/170, operand owner 69/69, semantic
  1,130/1,130, reconciliation plan 51/51, import 19/19, audit 217, full
  2,023/2,023과 body/caller/48-module/205-edge DAG parity가 통과했다. 인접한
  report-file/local-unit I/O helper는 graph에 남는다.
- 완료된 `cce5700` segment-label API batch는 이미 올바른 surface owner에
  있던 정확한 3줄 private helper를 public `operand_segment_label(...)`로
  이름 수렴시켰다. 외부 10/local 3 call은 모두 public API를 사용하며 exact
  argument, fallback/normalization, laziness, adoption과 stop은 유지됐다.
  Surface/graph/operand public/private는 16/6, 9/71, 54/37이다. Focused 4/4,
  graph owner 174/174, surface owner 1/1, operand owner 69/69, semantic
  1,134/1,134, reconciliation plan 51/51, import 19/19, audit 217, full
  2,027/2,027과 exact rename/body/caller/48-module/205-edge DAG parity가
  통과했다.
- 완료된 `ae964b3` operand-needles API batch는 같은 surface owner의 정확한
  4줄 private helper를 public `operand_needles(...)`로 이름 수렴시켰다. 외부
  20/local 4 call과 9개 외부 binding은 모두 public API를 사용하며 exact
  argument, 반복 변환, comprehension/loop/starred-list evaluation, adoption과
  stop은 유지됐다. Public 이름과 충돌한 한 local list만
  `normalized_operand_needles`로 명확히 바뀌었다. Surface/graph/operand
  public/private는 17/5, 9/71, 54/37이다. Focused 4/4, graph owner 178/178,
  surface owner 1/1, operand owner 69/69, semantic 1,138/1,138, additional
  caller 17/17, reconciliation plan 51/51, import 19/19, audit 217, full
  2,031/2,031과 transform/body/identity/caller/48-module/205-edge DAG parity가
  통과했다.
- 완료된 `83cf700` negative-surface API batch는 같은 surface owner의 정확한
  3줄 private helper를 public `text_has_negative_surface(...)`로 이름
  수렴시켰다. 외부 8/local 2 call과 5개 외부 binding은 모두 public API를
  사용하며 graph calculation과 graph helpers는 import-only로 남았다. Exact
  argument, boolean/generator short-circuit, adoption과 stop은 유지됐다.
  Surface/graph/operand public/private는 18/4, 9/71, 54/37이다. Focused 4/4,
  graph owner 182/182, surface owner 1/1, operand owner 69/69, semantic
  1,142/1,142, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
  import 19/19, audit 217, full 2,035/2,035와 transform/body/identity/caller/
  48-module/205-edge DAG parity가 통과했다.
- 완료된 `a0c9a84` positive-surface API batch는 같은 surface owner의 정확한
  3줄 private helper를 public `text_has_positive_surface(...)`로 이름
  수렴시켰다. 외부 25/local 1 call과 6개 외부 binding은 모두 public API를
  사용하는 live caller다. Exact argument, boolean/generator/conditional
  short-circuit, scoring/adoption과 stop은 유지됐다. Surface/graph/operand
  public/private는 19/3, 9/71, 54/37이다. Focused 4/4, graph owner 186/186,
  surface owner 1/1, operand owner 69/69, semantic 1,146/1,146, additional
  retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217,
  full 2,039/2,039와 transform/body/identity/caller/48-module/205-edge DAG
  parity가 통과했다.
- 완료된 `faf75a0` text contract-term API batch는 같은 surface owner의 정확한
  13줄 private helper를 public `text_has_contract_term(...)`로 이름
  수렴시켰다. 외부 1/local 3 call과 한 외부 binding은 모두 public API를
  사용하는 live caller다. Normalization, compact matching, ordered lazy
  iteration, direct-before-compact short-circuit과 stop은 유지됐다. Surface/
  graph/operand public/private는 20/2, 9/71, 54/37이다. Focused 4/4, graph
  owner 190/190, surface owner 1/1, operand owner 69/69, semantic 1,150/1,150,
  additional retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19,
  audit 217, full 2,043/2,043와 transform/body/identity/caller/48-module/
  205-edge DAG parity가 통과했다.
- 완료된 `5b71fd6` operand surface-contract API batch는 같은 owner의 정확한
  22줄 private helper를 public `operand_surface_contract(...)`로 이름
  수렴시켰다. 외부 2/local 5 call과 두 외부 binding은 public API를 사용하며
  operand resolution은 live caller, graph helpers는 import-only다. Explicit-
  contract/legacy-policy/needle-fallback의 순서·복사·laziness·failure stop은
  유지됐다. Surface/graph/operand public/private는 21/1, 9/71, 54/37이다.
  Focused 4/4, graph owner 194/194, surface owner 1/1, operand owner 69/69,
  semantic 1,154/1,154, additional retrieval-pipeline 1/1, reconciliation plan
  51/51, import 19/19, audit 217, full 2,047/2,047와 transform/body/identity/
  caller/48-module/205-edge DAG parity가 통과했다.
- 완료된 `ea830ed` generic-column-header API batch는 row-surface owner의
  정확한 2줄 private helper를 public `generic_column_headers()`로 이름
  수렴시켰다. Row-local 1/external 1 call과 structured-cell binding은 public
  API를 사용하며 policy projection·laziness·identity·failure stop은 유지됐다.
  Row/structured public/private는 12/14, 4/4이다. Focused 4/4, graph owner
  198/198, surface owner 1/1, operand owner 69/69, semantic 1,158/1,158,
  additional retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19,
  audit 217, full 2,051/2,051와 transform/body/identity/caller/48-module/
  205-edge DAG parity가 통과했다.
- 완료된 `786a356` table-row-label API batch는 같은 owner의 정확한 9줄
  private helper를 public `extract_table_row_label(...)`로 이름 수렴시켰다.
  Graph evidence/helpers/reconciliation의 external call 3개와 live binding은
  public API를 사용하며 normalization·delimiter split/fallthrough·identity·
  failure stop은 유지됐다. Row public/private는 13/13이다. Focused 4/4,
  graph owner 202/202, surface owner 1/1, operand owner 69/69, semantic
  1,162/1,162, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
  import 19/19, audit 217, full 2,055/2,055와 transform/body/identity/caller/
  48-module/205-edge DAG parity가 통과했다.
- 완료된 `472906e` financial-label-annotation API batch는 같은 owner의
  정확한 9줄 private helper를 public
  `strip_financial_label_annotations(...)`로 이름 수렴시켰다. Row-local 2/
  graph-helper 1/operand-resolution 2 direct calls과 두 외부 binding은 public
  API를 사용한다. Truth/normalization/annotation-regex/whitespace-strip,
  exact identity와 caller adoption/stop은 유지됐다. Row/graph/operand public/
  private는 14/12, 9/71, 54/37이다. Focused 4/4, graph owner 206/206, surface
  owner 1/1, operand owner 69/69, semantic 1,166/1,166, additional retrieval-
  pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217, full
  2,059/2,059와 transform/body/identity/caller/48-module/205-edge DAG parity가
  통과했다.
- 완료된 `98aee5a` leading-period-qualifier API batch는 같은 owner의 정확한
  14줄 private helper를 public `strip_leading_period_qualifiers(...)`로 이름
  수렴시켰다. Row-local 3/aggregate-projection 1 direct call과 live external
  binding은 public API를 사용한다. Truth/normalization/compile/sub-strip-
  equality loop, exact adopted identity와 caller adoption/stop은 유지됐다.
  Row public/private는 15/11이다. Focused 4/4, graph owner 210/210, surface
  owner 1/1, operand owner 69/69, semantic 1,170/1,170, additional retrieval-
  pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217, full
  2,063/2,063와 transform/body/identity/caller/48-module/205-edge DAG parity가
  통과했다.
- 완료된 `05415ed` surface-match-variants API batch는 같은 owner의 정확한
  11줄 private helper를 public `surface_match_variants(...)`로 이름
  수렴시켰다. Row-local 2/graph-calculation 2/operand-resolution 5 direct
  call과 두 external binding은 public API를 사용한다. Raw truth/
  normalization, eager annotation/period order, truth-filtered ordered dedupe,
  first-representative identity와 caller adoption/stop은 유지됐다. Row public/
  private는 16/10이다. Focused 4/4, graph owner 214/214, surface owner 1/1,
  operand owner 69/69, semantic 1,174/1,174, additional retrieval-pipeline 1/1,
  reconciliation plan 51/51, import 19/19, audit 217, full 2,067/2,067와
  transform/body/identity/caller/48-module/205-edge DAG parity가 통과했다.
- 완료된 `6f28f8b` operand-text-match API batch는 같은 owner의 정확한 16줄
  private helper를 public `operand_text_match(...)`로 이름 수렴시켰다. 10개
  module의 62 call과 9개 external binding은 public API를 사용한다. Variant/
  needle 반복, per-haystack fresh needle lookup, exact/substring/compact
  short-circuit, exact bool result와 36 caller의 adoption/stop은 유지됐다.
  Row public/private는 17/9이다. Focused 4/4, graph owner 218/218, surface
  owner 1/1, operand owner 69/69, semantic 1,178/1,178, additional retrieval-
  pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217, full
  2,071/2,071와 transform 16/16/body/identity/caller/48-module/205-edge DAG
  parity가 통과했다. 최초 graph-only test inventory가 빠뜨린 5개 test
  module의 live ref 30개도 public binding으로 갱신됐다.
- 완료된 `7739ab0` numeric-value-after-operand-text API batch는 같은 owner의
  정확한 16줄 private helper를 public
  `extract_numeric_value_after_operand_text(...)`로 이름 수렴시켰다. Graph
  calculation/evidence와 operand resolution의 5개 call 및 3개 external
  binding은 public API를 사용한다. Normalization, needle compact, escaped
  spaced-pattern, search, candidate distance sort, first result identity와 3개
  caller의 adoption/stop은 유지됐다. Row public/private는 18/8이다. Focused
  4/4, graph owner 222/222, surface owner 1/1, operand owner 69/69, semantic
  1,182/1,182, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
  import 19/19, audit 217, full 2,075/2,075와 transform 8/8/body/identity/
  caller/48-module/205-edge DAG parity가 통과했다.
- 완료된 `72eb1b8` structured-candidate-row-text API batch는 같은 owner의
  정확한 24줄 private helper를 public
  `format_structured_candidate_row_text(...)`로 이름 수렴시켰다. Graph
  helpers의 2개 call과 1개 external binding은 public API를 사용한다.
  Label/header order와 dedupe, repeated header normalization, cell-part
  construction/join, caller assignment/adoption/stop은 유지됐다. Row public/
  private는 19/7이다. Focused 4/4, graph owner 226/226, surface owner 1/1,
  operand owner 69/69, semantic 1,186/1,186, additional retrieval-pipeline 1/1,
  reconciliation plan 51/51, import 19/19, audit 217, full 2,079/2,079와
  transform/body/identity/caller/48-module/205-edge DAG parity가 통과했다.
- 완료된 `ac90a62` unstructured-table-row parser API batch는 같은 owner의
  정확한 47줄 private helper를 public
  `parse_unstructured_table_row_cells(...)`로 이름 수렴시켰다. 5개
  importer의 7개 external call과 6개 caller 정의는 public API를 사용한다.
  Row/header/period fallback, numeric/labeled-value parsing, caller gate/
  adoption/stop은 유지됐고 row public/private는 20/6이다. Focused 4/4,
  graph owner 230/230, surface owner 1/1, operand owner 69/69, semantic
  1,190/1,190, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
  import 19/19, audit 217, full 2,083/2,083와 transform/body/identity/caller/
  48-module/205-edge DAG parity가 통과했다.
- 완료된 `89227aa` structured-cell period-text API batch는 같은 owner의
  정확한 35줄 private helper를 public `structured_cell_period_text(...)`로
  이름 수렴시켰다. 4개 importer의 4개 external call과 4개 caller 정의는
  public API를 사용한다. Policy marker, query/report year, fiscal-rank/header
  fallback과 caller gate/adoption/stop은 유지됐고 structured-cell public/
  private는 5/3이다. Focused 4/4, graph owner 234/234, surface owner 1/1,
  operand owner 69/69, semantic 1,194/1,194, additional retrieval-pipeline 1/1,
  reconciliation plan 51/51, import 19/19, audit 217, full 2,087/2,087와
  transform/body/identity/caller/48-module/205-edge DAG parity가 통과했다.
- 완료된 `f010b6f` ratio-percent-query API batch는 operation-policy owner의
  정확한 3줄 private classifier를 public `is_ratio_percent_query(...)`로 이름
  수렴시켰다. 4개 importer의 7개 external call은 public API를 사용한다. 한
  positional argument/no keyword, 6개 depth-zero caller와 기존 broad handler
  내부 calculation depth-one caller, normalization/policy-marker iteration/
  short-circuit, caller gate/adoption/exception scope는 유지됐고 operation-
  policy public/private는 1/6이다. Focused 4/4, graph owner 238/238, surface
  owner 1/1, operand owner 69/69, semantic 1,198/1,198, reflection capability
  24/24, retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit
  217, full 2,091/2,091와 transform/body/identity/caller/48-module/205-edge DAG
  parity가 통과했다.
- 완료된 `1883395` narrative-context-query API batch는 같은 operation-policy
  owner의 정확한 6줄 private classifier를 public
  `query_requests_narrative_context(...)`로 이름 수렴시켰다. 5개 importer의
  18개 external call은 public API를 사용하며 한 positional argument/no
  keyword와 caller `try` depth zero를 유지한다. 입력 truth/string/
  normalization/lowercase, blank early return, policy-hint tuple construction,
  membership short-circuit와 calculation/evidence/hybrid-task/compression/text-
  surface caller gate/adoption/stop은 유지됐고 operation-policy public/private는
  2/5이다. Focused 4/4, graph owner 242/242, surface owner 1/1, operand owner
  69/69, semantic 1,202/1,202, answer projection 23/23, retrieval hints 5/5,
  text surface 30/30, reflection capability 24/24, retrieval-pipeline 1/1,
  reconciliation plan 51/51, import 19/19, audit 217, full 2,095/2,095와
  transform/body/identity/caller/48-module/205-edge DAG parity가 통과했다.
- 완료된 `1c8400f` percent-metric-label API batch는 같은 operation-policy
  owner의 정확한 8줄 private classifier를 public
  `label_implies_percent_metric(...)`로 이름 수렴시켰다. 4개 importer의 5개
  external call은 한 positional argument/no keyword와 caller `try` depth
  zero를 유지한다. 입력 truth/string/normalization, blank early return,
  configured marker와 `%`/`%p` tuple construction, membership short-circuit 및
  unit-family/operand-conflict/reconciliation/candidate-surface caller gate/
  adoption/stop은 유지됐고 operation-policy public/private는 3/4이다.
  Focused 4/4, graph owner 246/246, surface owner 1/1, operand owner 69/69,
  semantic 1,206/1,206, reflection promotion 15/15, reflection capability
  24/24, retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit
  217, full 2,099/2,099와 transform/body/identity/caller/48-module/205-edge DAG
  parity가 통과했다.
- 완료된 `f0fae1f` single-metric-period-comparison API batch는 같은 owner의
  정확한 11줄 private classifier를 public
  `is_single_metric_period_comparison(...)`로 이름 수렴시켰다. 소스의 4개
  call은 두 positional arguments/no keyword와 caller `try` depth zero를
  유지한다. Query normalization, period-policy snapshot, marker tuple/
  membership short-circuit, truthy-label filtering, stable hash/equality
  dedupe와 도달 가능한 generic-operand, operation-family, direct-grounding
  caller gate/adoption/stop은 유지됐다. CURRENT-SOURCE 계약은 concept-
  operand call이 앞선 cardinality invariant 때문에 runtime-unreachable임도
  고정했다. Operation-policy public/private는 4/3이다. Focused 4/4, graph
  owner 250/250, surface owner 1/1, operand owner 69/69, semantic
  1,210/1,210, reflection promotion 15/15, reflection capability 24/24,
  retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217,
  full 2,103/2,103와 transform/body/identity/caller/48-module/205-edge DAG
  parity가 통과했다.
- 완료된 `ca2969b` dead-branch batch는
  `_build_concept_required_operands(...)`의 runtime-unreachable 9줄만
  replacement 없이 삭제했다. `ordered_specs`와 one-to-one으로 다시 만든
  `raw_explicit_roles`의 cardinality invariant, ordering, earlier difference/
  growth return, downstream role hints와 operand construction은 유지됐다.
  Helper call/caller는 4/4에서 도달 가능한 3/3으로 줄었다. Focused 4/4,
  graph owner 254/254, surface owner 1/1, operand owner 69/69, semantic
  1,214/1,214, reflection promotion 15/15, reflection capability 24/24,
  retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217,
  full 2,107/2,107와 exact-deletion/owner/caller/48-module/205-edge DAG parity가
  통과했다.
- 완료된 `1d8eb67` visibility batch는 operation-policy owner의 정확한 12줄
  `_is_percent_point_difference_query(...)`을 public
  `is_percent_point_difference_query(...)`로 이름 수렴시켰다. Policy snapshot,
  direct-marker precedence, ratio-metric/comparison-marker gating과 8개 call의
  caller adoption/stop은 유지됐다. Operation-policy public/private는 5/2다.
  Focused pre/post 4/4, graph owner 258/258, surface owner 1/1, operand owner
  69/69, semantic 1,218/1,218, reflection promotion 15/15, reflection capability
  24/24, retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit
  217, full 2,111/2,111와 transform/body/identity/seven-caller/48-module/
  205-edge DAG parity가 통과했다.
- 완료된 `a893cb3` visibility batch는 같은 owner의 정확한 21줄
  `_should_coerce_percent_point_unit(...)`을 public
  `should_coerce_percent_point_unit(...)`로 이름 수렴시켰다. Percent-point/
  mode/ordered-ID/operand-map/unit gates와 operation/formula result, 두 caller의
  argument/adoption/fallback/exception scope는 유지됐다. Operation-policy
  public/private는 6/1이다. Focused pre/post 4/4, graph owner 262/262,
  calculation-execution 45/45, math parsing 24/24, surface owner 1/1, operand
  owner 69/69, semantic 1,222/1,222, reflection promotion 15/15, reflection
  capability 24/24, retrieval-pipeline 1/1, reconciliation plan 51/51, import
  19/19, audit 217, full 2,115/2,115와 transform/body/identity/two-caller/
  48-module/205-edge DAG parity가 통과했다.
- 완료된 `7de65fc` visibility batch는 같은 owner의 정확한 40줄
  `_requires_direct_numeric_grounding(...)`을 public
  `requires_direct_numeric_grounding(...)`로 이름 수렴시켰다. Task shallow
  copy, operation precedence, required-row filter/copy ordering, ratio/sum 및
  difference/growth 결과, fallback classifier adoption과 세 caller의 gate/
  argument/adoption/exception scope는 유지됐다. Operation-policy public/
  private는 7/0이다. Focused pre/post 4/4, graph owner 266/266, operation
  contracts 242/242, retrieval hints 5/5, task artifacts 15/15, semantic
  1,226/1,226, reflection promotion 15/15, reflection capability 24/24,
  retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217,
  full 2,119/2,119와 transform/body/identity/three-caller/48-module/205-edge DAG
  parity가 통과했다.
- 새 characterize-only inventory는 scope-policy owner의 정확한 15줄
  `_desired_consolidation_scope(...)`을 public
  `desired_consolidation_scope(...)`로 이름 수렴시킨다. Query/metadata/default
  precedence와 copy/eager-lazy evaluation, exact scope results, immutability 및
  다섯 importer·열두 call·열한 caller의 gate/argument/adoption/exception
  scope를 유지해야 한다. 계산 extraction의 같은 이름 지역 store 1개/load
  8개는 `requested_consolidation_scope`로 선택 변경하고 기존 keyword 이름
  2개는 유지해 unbound-local 충돌을 제거해야 한다. 정확한 네 CURRENT-SOURCE
  method와 projection은
  [Project Status의 Next Work](project_status.md#next-work)가 단일 기준이다.

### `src/agent/financial_graph_helpers.py`

여러 mixin이 공유하는 runtime helper 묶음이다. 현재는 helper surface가 아직 크기
때문에, 읽을 때 목적별로 들어가야 한다.

- task/artifact projection
- runtime calculation trace construction and metadata
- `structured_result` / `resolved_calculation_trace` compatibility projection
- source row/evidence id cleanup
- numeric parsing and unit normalization helpers
- caller-side reconciliation candidate construction/ranking orchestration
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
