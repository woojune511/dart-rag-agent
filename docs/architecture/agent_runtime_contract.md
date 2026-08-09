# Agent Runtime Contract

이 문서는 에이전트가 코드를 수정하거나 실험을 설계할 때 고정해야 하는 runtime 계약이다. 목표는 benchmark row에 맞춘 즉흥 패치를 막고, ingest, retrieval, planning, calculation, evaluation을 재현 가능한 시스템 경계로 나누는 것이다.

## 1. Canonical Ingest

Routine validation의 기준 ingest는 `structural_selective_v2_prefix_2500_320`이다.

코드 기준값:

- `CANONICAL_INGEST_PROFILE_ID = "structural_selective_v2_prefix_2500_320"`
- `CANONICAL_INGEST_MODE = "structural_selective_v2"`
- `CANONICAL_CHUNK_SIZE = 2500`
- `CANONICAL_CHUNK_OVERLAP = 320`

## 1.1 Canonical Embedding Runtime

Routine validation now treats OpenAI `text-embedding-3-large` as the canonical
remote embedding runtime:

- `CANONICAL_EMBEDDING_PROVIDER = "openai"`
- `CANONICAL_EMBEDDING_MODEL = "text-embedding-3-large"`
- `CANONICAL_EMBEDDING_DIMENSION = 3072`

Runtime provider selection is still environment-aware:

- `DART_EMBEDDING_PROVIDER` explicitly overrides the canonical provider.
- If no provider is set and `OPENAI_API_KEY` is available, use OpenAI.
- If OpenAI is unavailable but `GOOGLE_API_KEY` is available, fall back to
  Google embeddings.
- If no remote embedding key is available, fall back to the local HuggingFace
  embedding model for development only.

Changing embedding provider, model, or dimension invalidates vector-store
compatibility. Treat a provider/model/dimension mismatch as a cache miss and
reindex rather than reusing an old Chroma store.

다른 ingest 방식은 experimental profile로만 사용한다. 품질 비교가 필요하면 profile 이름과 결과 디렉터리로 격리하고, runtime default를 조용히 바꾸지 않는다.

## 2. Retrieval Trace

retrieval 단계는 최소한 `retrieval_debug_trace`를 남긴다.

필수 필드:

- `query_bundle`: 실제 retrieval 후보 query 목록
- `executed_queries`: 실행 query, `k`, `where_filter`, source(`primary` 또는 `retry`)
- `where_filter`: 최종 metadata filter
- `effective_k`: retrieval node가 적용한 k
- `retry_queries`: reflection retry query 목록
- `candidate_count`: rerank 전후 후보 수 판단에 쓸 후보 수
- `seed_count`: seed retrieval docs 수
- `selected_count`: 최종 선택 docs 수
- `selected_chunks`: rank, score, chunk uid, section, block type, company, year, receipt
- `policy_trace`: intent, operation family, format preference, retrieval hint, preferred sections, scope flags

이 trace는 answer 품질을 보정하기 위한 데이터가 아니라, 왜 그 evidence가 선택됐는지 검증하기 위한 감사 로그다.

## 3. Focused Verification Gate

변경 검증 순서는 다음으로 고정한다.

1. 관련 unit/contract test
2. `python -m unittest discover -s tests`
3. 필요한 경우 focused benchmark 또는 eval-only
4. full benchmark

full benchmark는 store/cache/input 조건이 확인됐을 때만 실행한다. 5분 이상 결과 파일이 생성되지 않으면 `results.json` 존재 여부만 보지 말고 실행 heartbeat를 확인한다. 로그 출력, store/cache 파일 갱신, 프로세스 CPU/IO가 계속 움직이면 fresh store 구축 또는 장기 ingest로 분류하고 monitored run으로 전환한다. 가능하면 `benchmark_runner --progress-heartbeat-sec <seconds> --heartbeat-log <path>`로 runner-native heartbeat를 켜서 phase/progress/store mtime을 직접 남긴다. 결과 파일도 없고 heartbeat도 없으면 중단하고, 코드 실패인지 실행 환경 문제인지 분리해서 기록한다.

## 4. Task Ledger And Artifact Store

agentic workflow의 기본 통신 모델은 자유 채팅이 아니라 task ledger와 artifact store다.

Task ledger는 다음을 표현해야 한다.

- task id, assignee, instruction, status
- dependency(`depends_on`)
- produced artifact ids
- retry count와 blocked reason

Artifact store는 다음을 표현해야 한다.

- artifact id, kind, producer task id
- payload 또는 content
- evidence links
- metadata

Runtime callers and benchmark outputs must expose a compact
`task_artifact_trace` projection in addition to the raw task and artifact
records. The projection is the boundary that future Orchestrator, Analyst,
Researcher, and Critic roles should consume before reading free-form LLM text.
The MAS skeleton must also keep this projection on `MultiAgentState` at
orchestration join points. Worker nodes should write artifacts with stable
`artifact_id`, `kind`, payload, and evidence refs. The Critic should write
`critic_report` artifacts, and the final Orchestrator merge should write an
`aggregated_answer` artifact for the final report.
Worker artifact consumers should read answer text, payload, selected artifact
id, and evidence refs through the shared MAS worker-artifact boundary
projection. This keeps Critic review and Orchestrator final synthesis aligned
on payload-first answer selection and evidence-ref dedupe instead of duplicating
role-specific artifact parsing rules.
The final report record must also preserve carry-forward provenance as typed
fields: `source_task_ids`, `source_artifact_ids`, `evidence_refs`, and
`subtask_results`. Each subtask result row should include the worker `task_id`,
the selected worker `artifact_id` / `source_artifact_id`, and the answer surface
used by final synthesis. Runtime and smoke surfaces should derive compact
carry-forward counts and id lists from the shared MAS schema helper rather than
reimplementing the projection in one-off scripts.
Analyst worker tasks are `calculation` tasks and must write separate
`operand_set`, `calculation_plan`, and primary `calculation_result` artifacts.
Researcher worker tasks are `retrieval` tasks and must write a `retrieval_bundle`
artifact containing retrieved candidates and provenance.

The projection must include:

- normalized task views with task id, kind, label, status, artifact ids,
  artifact kinds, latest artifact id/kind/status, and latest artifact summary
- normalized artifact views with artifact id, producer task id, kind, status,
  summary, payload keys, and evidence refs
- aggregate counts for tasks and artifacts
- missing artifact ids referenced by tasks but absent from the artifact store
- orphan artifact ids present in the store but not referenced by any task
- an `integrity_status`, `integrity_issue_count`, and structured
  `integrity_issues` list

Integrity issues are structural runtime-contract signals, not benchmark score
signals. Duplicate task or artifact ids and missing artifact references are
errors. Orphan artifacts and completed or partial tasks without produced
artifacts are warnings. These checks must stay generic; they cannot depend on
company names, benchmark ids, financial metric names, or question-specific
phrases.

Warning-level issues are non-blocking by default. They become blocking only when
the final aggregated answer directly depends on the warned object. If an
`aggregated_answer` source references an orphan artifact, emit
`final_source_orphan_artifact` as an error. If an `aggregated_answer` source
references a completed or partial task that produced no artifacts, emit
`final_source_task_without_artifacts` as an error. Keep the original warning in
the trace so callers can distinguish the structural warning from its final-source
promotion.

Typed task acceptance may add required artifact-kind checks. A completed
`calculation` task must reference all of:

- `operand_set`
- `calculation_plan`
- `calculation_result`

If any required kind is absent from the attached artifacts, the projection must
emit `missing_required_artifact_kind` as an error with the task id, task kind,
and missing artifact kind.

Attached calculation artifacts must also carry the minimum payload shape needed
to close a numeric answer:

- `operand_set.payload.calculation_operands` must be a non-empty list
- `calculation_plan.payload.calculation_plan` must include an operation or mode
- `calculation_result.payload.calculation_result` must include a rendered or
  formatted value, or non-empty `answer_slots`

If the payload shape is absent, emit `missing_required_artifact_payload` with
the task id, artifact id, artifact kind, and missing payload key. A completed
calculation task must also preserve at least one evidence reference, either in
artifact-level `evidence_refs` or in payload provenance fields such as evidence
ids or source row ids. If no attached artifact preserves provenance, emit
`missing_required_evidence_ref`.

A completed `reconciliation` task must reference a `reconciliation_result`
artifact. That artifact must contain `payload.reconciliation_result.status`. If
the reconciliation status is `ready` or `ok`, the artifact must also preserve
candidate or evidence provenance through artifact-level `evidence_refs` or
payload fields such as `candidate_ids`, evidence ids, or source row ids. Missing
kind, payload status, or ready/ok provenance should reuse the same generic
integrity issue types: `missing_required_artifact_kind`,
`missing_required_artifact_payload`, and `missing_required_evidence_ref`.

A completed `retrieval` task must reference a `retrieval_bundle` artifact. The
bundle must contain at least one retrieved candidate list, such as
`retrieved_docs`, `seed_retrieved_docs`, `evidence_items`, `documents`, or the
same fields nested under `retrieval_bundle`. Retrieved candidates must also
preserve provenance through artifact-level `evidence_refs` or payload fields
such as `chunk_id`, `doc_id`, source anchors, evidence ids, or source row ids.
An empty bundle or missing provenance should emit
`missing_required_artifact_payload` / `missing_required_evidence_ref` and block
final close.

A completed `synthesis` task must reference an `aggregated_answer` artifact.
The artifact must contain final answer text through `final_answer`, `answer`, or
`payload.aggregated_answer.final_answer`. It must also preserve source material
through `subtask_results`, source task/artifact ids, or structured trace/result
payloads such as `resolved_calculation_trace`, `structured_result`, or
`calculation_result`. A completed synthesis answer must preserve provenance via
artifact-level `evidence_refs` or payload provenance fields including source
task/artifact ids, evidence ids, source row ids, source anchors, or candidate
ids. Missing final text, missing source material, or missing provenance should
emit the same generic integrity errors used by the other task families and block
final close.

A completed `critic` task must reference a `critic_report` artifact. The report
must contain a verdict signal through `passed`, `verdict`, or `status`; target
or checked task/artifact refs; and either blocking issues/findings or an
acceptance reason/rationale/feedback. Critic reports must also preserve
provenance through artifact-level `evidence_refs` or payload refs such as
target, checked, source, evidence, or artifact ids. Missing verdict, target refs,
reason/issues, or provenance should emit the same generic integrity errors and
block final close.

Runtime critic acceptance is contract-based, not score-threshold-based.
`deterministic_score` is diagnostic metadata for audit/debug traces. A runtime
acceptance decision should follow the normalized report contract: `passed`,
`verdict`, or `status` may provide the verdict signal, but conflicting verdict
signals block acceptance. Accepted reports need a normalized passed verdict,
target refs, an acceptance reason, and no blocking issues; rejected reports stay
blocked even when their diagnostic score is high. Final close/replan integrity
checks should consume
`financial_artifact_contracts.critic_report_runtime_acceptance_state()` so a
structurally complete rejected critic report still blocks final close. Planner
feedback and smoke/review handoff summaries should surface the normalized
runtime acceptance status, reasons, and target refs so the retry path can
explain why the critic blocked the close. Rejected critic integrity issues
should also project target task and artifact ids separately from raw target
refs, so replan carry-forward can fail the rejected worker task rather than only
failing the critic task that reported the rejection.

Final synthesis must treat `integrity_status = "error"` as a blocking
acceptance condition. If the replan budget remains, the aggregate step should
emit planner feedback and route back to planning. If the replan budget is
exhausted, the final answer may preserve visible partial material but must add
an explicit refusal/uncertainty sentence instead of closing as fully answered.
MAS state should expose this control path explicitly through `planner_feedback`,
`replan_budget`, and `replan_count` so callers can distinguish a replan request
from a final blocked/refusal answer.
Warning-level issues remain observable contract signals and should not block a
final answer unless promoted by the final-source policy above.

Orchestrator, Analyst, Researcher, Critic은 이 구조를 통해 상태를 교환한다. LLM 메시지 전문은 보조 로그일 수 있지만, 다음 단계의 입력 계약이 되어서는 안 된다.

## 5. Boundary Rules

Parser regex는 DART 문서 구조 복원용이다. answer나 retrieval decision을 특정 benchmark에 맞추는 용도로 쓰지 않는다.

Retrieval/routing policy는 `src/config/retrieval_policy.py`처럼 명명된 config에 둔다. 특정 회사, 질문, 평가 row 이름이 runtime branch에 들어가면 중단하고 일반 정책인지 다시 분류한다.

Numeric path는 deterministic contract를 따른다. 산술, 단위 변환, operand ordering, dependency binding, dedupe, validation은 코드가 담당한다. LLM은 intent, concept, evidence interpretation처럼 의미 판단에만 쓴다.

Evaluator는 평가 정의를 담을 수 있지만, runtime agent가 evaluator trick을 따라가면 안 된다.

## 5.1 Report-Scoped Value Cache Contract

Report-scoped cache is a runtime contract for reusing already grounded values,
not a shortcut around evidence. The current code-level contract lives in
`src/config/report_scoped_cache.py`.

Cache keys are versioned and normalized from:

- report scope: `company`, `report_type`, `rcept_no`, `year`
- value identity: `concept_id` or `metric_label`, plus `period`
- provenance scope: `consolidation_scope`, `statement_type`, `source_section`,
  and `source_table_id`

A candidate value is `reusable` only when it has a complete report key, a
structured value kind such as `structured_row`, `operand`, or
`calculation_result`, and traceable provenance. Prose lookups, partial
provenance, or missing statement/consolidation/section scope must be classified
as `requires_evidence_verification` before reuse. Synthesized answers, refusals,
LLM-only interpretations, and value-free payloads are `not_cacheable`.

Cache writes and reads must use this classification before bypassing retrieval.
If the value is not `reusable`, runtime may still use the cache as a candidate
hint, but it must verify the source evidence again before answering.

Runtime calculation traces may include a read-only `report_cache_candidate`
projection. This projection is observability only: it records the classifier
status, reasons, normalized key, and deterministic key id, but it must not cause
cache read/write behavior or retrieval bypass by itself.

MAS smoke and export-style observability surfaces may summarize these candidates
by case and by status/reason count. If the same candidate appears in both
compatibility `content` and typed `payload`, summary counts should dedupe it by
artifact/key/status/reasons so handoff metrics describe candidate values rather
than projection copies.

### Cache Consumer Rehydration Boundary

A readable persisted entry is not automatically safe to use as an answer. A
future cache consumer must first prove that the entry can be rehydrated into the
same runtime surfaces that normal retrieval/calculation would have produced.
The code-level readiness check is
`classify_report_cache_rehydration_candidate()`, and it remains disabled for
serving: `enabled = false` and `serving_enabled = false` are part of the
contract.
The optional projection helper
`build_report_cache_rehydrated_candidate_artifact()` may rebuild the answer,
citations, evidence items, structured result, and calculation trace into an
artifact-like candidate payload, but that payload must remain `status =
candidate` and must not be inserted into the task/artifact ledger as a served
answer.
That candidate must also carry calculation-ledger-oriented metadata without
turning into a ledger write: `source = report_cache_rehydration`,
`cache_origin = local_cache_index`, `report_cache_key_id`,
`rehydration_status`, guarded `consumer_admissibility.status`, and disabled
`serving_enabled` / `ledger_insertion_enabled` flags.

A rehydratable entry must include all of the following:

- a readable local-cache-index entry according to `classify_report_cache_entry()`
- `answer_slots` with a `primary_value` display/raw surface
- citation or source-anchor material that can be shown to the user
- rehydratable evidence material, such as evidence refs, source row ids, or
  evidence items
- calculation trace material with `calculation_result` and
  `calculation_operands`

If any of those surfaces are missing, the future consumer must treat the entry
as a diagnostic candidate only and execute normal retrieval. The fallback is not
to synthesize missing evidence from the cache value; it is to recover evidence
through the existing retrieval and validation path.

### Guarded Cache Consumer Promotion Design

Cache serving remains disabled until the consumer path can satisfy the same
task/artifact contract as normal retrieval and calculation. A future
implementation must be behind an explicit enable flag, and the default behavior
must remain normal retrieval with trace-only diagnostics.

The only allowed read source is a readable `local_cache_index` entry. Runtime
trace projections, artifact-store projections, smoke output, and benchmark
exports are observability surfaces only; they cannot become cache hits. A
consumer must start from `ReportCacheIndex.lookup_diagnostics()`, select a
single rehydration-ready match, and preserve the normal-retrieval fallback when
there is no exact readable and rehydratable match.

Before a rehydrated candidate can influence the final answer, it must enter the
task/artifact ledger through an explicit producer policy. It must not be hidden
inside free-form agent text or top-level compatibility fields. The future
implementation has two acceptable shapes:

- declare a dedicated cache-rehydration task/artifact kind in the schema and
  contract, then teach integrity projection how to validate it
- or map the rehydrated value into the existing calculation task contract by
  producing the same required `operand_set`, `calculation_plan`, and
  `calculation_result` artifacts with explicit cache-origin metadata

Until one of those shapes is implemented and contract-tested, rehydrated output
must stay `status = candidate` and outside the ledger.
The first contract-tested shape is the calculation-task mapping. The helper
`build_report_cache_calculation_contract_projection()` may project a
rehydration-ready candidate into a candidate `calculation` task plus
`operand_set`, `calculation_plan`, and `calculation_result` artifacts using the
same artifact id pattern as Analyst output. This projection is still a schema
contract only: every projected task/artifact must remain `status = candidate`
with `serving_enabled = false` and `ledger_insertion_enabled = false`.
`validate_report_cache_calculation_contract_projection()` is the read-only
validator for that shape. It checks the required calculation artifact kinds,
minimum payload surfaces, preserved evidence refs, and disabled serving/ledger
flags, then reports whether the projection is valid for the contract without
writing it to the ledger. Reviewer-facing smoke output may expose this
validation status and fallback reasons, but it must not treat a valid candidate
as a served answer.

The consumer must recheck provenance before serving. The cached display value,
normalized value, `answer_slots.primary_value`, citation/source anchors,
evidence items or refs, source row/table ids, and calculation operands must
agree with the cache key's report/value/provenance scope. A mismatch is a cache
miss, not a repair opportunity. The consumer must not synthesize citations,
operands, source rows, or calculation traces from the cached answer text.

The following trace-only diagnostics become blocking for an enabled consumer:

- `serving_enabled = false` or any disabled mode marker on the candidate
- no readable `local_cache_index` match
- more than one selected match for the same key without a deterministic tie
  policy in config
- `rehydration_ready = false` or any rehydration block reason
- missing answer slots, citation/source anchors, evidence material, or
  calculation trace material
- cache key id mismatch or incomplete report/value/provenance key fields
- source scope mismatch across report, statement, consolidation, section, table,
  row, period, or value identity fields
- ledger insertion without required artifact kinds, payload shape, and evidence
  refs

When any blocking condition appears, runtime must record the diagnostic reason
and execute normal retrieval. A cache miss must be observable, but it must not
degrade answer correctness or weaken final-source integrity checks.

`classify_report_cache_guarded_consumer_candidate()` is the current pure helper
for this design surface. It does not enable reads; it classifies whether a
local-index entry is structurally admissible for a future schema-backed consumer
or must fall back to normal retrieval. Even an admissible result reports
`enabled = false`, `serving_enabled = false`, and `mode = trace_only`.

## 6. Concept Planner Candidate Validation

LLM concept planner는 의미 해석을 보조할 수 있지만, ontology concept를
무근거로 선택해서 runtime task를 열면 안 된다.

- query/topic/planner feedback에서 매칭된 ontology concept가 있으면 planner
  후보는 그 concept set과 group member로 제한한다.
- 명시 concept 매칭이 없어 전체 ontology catalog fallback을 쓰는 경우에도,
  `surface_contract.positive`가 정의된 concept는 해당 positive term이
  query/topic/planner feedback에 나타날 때만 허용한다.
- 일반 정책/법령/시장 맥락이 특정 세액공제, 특정 회계처리, 특정 metric
  concept로 승격되려면 ontology alias나 surface contract가 그 좁은 의미를
  직접 지지해야 한다.
- 거부된 LLM planner task는 runtime branch로 보정하지 말고 validator note와
  retrieval trace를 통해 원인을 확인한다.

이 규칙은 LLM의 semantic flexibility를 유지하면서, benchmark나 특정 문항에서
그럴듯해 보이는 concept 과매칭이 runtime execution으로 넘어가는 것을 막기
위한 최소 게이트다.

### Segment Binding Scope

Planner/runtime code may attach a `segment_label` only when the segment surface
and the numeric metric surface are co-located in the same query clause or a very
near local span. A segment mentioned only in a separate narrative/background
clause must not scope an unrelated numeric lookup. Mixed numeric+narrative
queries should remain split into a company-level numeric task plus a narrative
task when the query wording supports that split.

This is a generic binding rule, not a place to encode company names, segment
names, or benchmark-specific vocabulary. Metric surfaces must come from the
ontology/policy-backed concept spec or the inferred generic metric label.

### Non-Numeric Intent With Numeric Operations

Routing intent is not the only gate into the numeric planner. If a query is
routed as a non-numeric intent such as `qa`, `risk`, or `business_overview`, the
planner may still promote it to the numeric task pipeline when a declarative
policy proves that the query contains an executable numeric operation contract.

The promotion must be based on generic signals:

- configured source/target intents and allowed operation families
- ontology concepts and unit families, when matched
- or a dry-run semantic numeric plan that produces required operands with
  allowed operation and unit families

The promotion must not branch on company names, benchmark ids, specific policy
topics, or report-specific phrases. Mixed questions that contain both numeric
operation and explanatory/narrative requirements should still create a numeric
child task plus a `narrative_summary` child task in the task ledger, rather than
falling back to a single general-search answer.

## 7. Ontology-Driven Prose Lookup Slots

When a concept lookup obtains the required numeric value from prose rather than
from a structured table row, the runtime contract is:

- use ontology aliases and `surface_contract.positive` terms to locate the
  value in the answer/evidence text
- synthesize a normal `answer_slots.primary_value` record with concept, role,
  period, rendered value, normalized value, and provenance
- promote the retrieved source document containing that value into
  `runtime_evidence`
- compose aggregate difference answers from slot `rendered_value` fields when
  all operands are available

This keeps domain vocabulary in ontology/config while allowing deterministic
dependency binding and evaluator-visible grounding. Runtime code should not add
company-specific or benchmark-specific branches for these cases.

## 8. Retrieved Evidence Preservation For Calculation

Reconciliation is a candidate matcher, not the final authority on whether a
calculation can proceed. If reconciliation reports insufficient operands but the
active calculation subtask still has required operands and retrieved documents,
the graph must route through operand extraction once before advancing or
abstaining.

The operand extractor may promote retrieved raw chunks into calculation evidence
when all of these are true:

- the active task is not a direct numeric lookup that requires structured
  grounding
- the retrieved chunk carries text that matches the required operand surfaces
  from the task/ontology contract
- the extracted value remains attached to the source chunk metadata and evidence
  id

This rule prevents lossy evidence summaries from hiding values that retrieval
already found. It does not permit benchmark-specific fallback answers: extracted
rows still have to satisfy the generic required-operand matcher, unit
normalization, period checks, and provenance checks.

When graph expansion adds parent, table-context, sibling, or other structural
documents, the expanded `retrieved_docs` window can crowd out a raw seed chunk
that contains the required numeric sentence. The calculation path must treat
`seed_retrieved_docs` as eligible candidate evidence for required-operand
extraction, as long as the same generic matcher/provenance/unit checks pass.
Do not recover these chunks by company name, benchmark id, or topic-specific
keywords in runtime code.

`REFERENCE_NOTE` is one of these structural expansion relations. Its current
capability boundary is Researcher graph-expansion context only: retrieved
documents may carry `graph_relation = reference_note`, and Researcher outputs
may carry them inside a `retrieval_bundle`, but this does not make the note a
cache read source, retrieval-bypass authority, task/artifact ledger producer,
or final-answer acceptance authority. The repo-local
`src.ops.reference_note_capability_gate` command is the reviewer gate for this
boundary.

When structured table metadata provides both `table_row_labels_text` and row
records, operand precision refinement must prefer the structured cell from the
same matched row label before considering nearby previous rows. Previous-row
fallback is only for explanatory rows that name an operand but carry no value
cell themselves. This avoids binding a requested metric such as cost of sales
to the value from an adjacent revenue row.

If the source text already states a derived display value, such as a
year-over-year percentage next to the current and prior values, the runtime
should preserve that source-stated display in `calculation_result.rendered_value`
and answer slots when it is attached to the same evidence. The deterministic
formula result should remain traceable, for example in `derived_metrics`, when
it differs because the source rounded or displayed the value at a different
precision.

### Adaptive Retrieval Stop Gate

Retrieval fan-out may be reduced only when the runtime can prove generic
coverage from already retrieved documents. The stop decision must not use
company names, benchmark ids, topic-specific phrases, or domain vocabulary in
runtime control flow.

The allowed stop signals are:

- active task `required_operands`
- operand surface coverage from task/ontology aliases
- period coverage from task constraints, query years, or report scope
- numeric signal in the retrieved document text or table metadata
- source provenance through chunk ids and retrieval trace entries

The first conservative stop gate is scoped to focused operand retrieval:
after primary retrieval, if every required operand is covered by a retrieved
document with matching period and numeric signal, the runtime may skip
additional focused operand queries. The trace must record the coverage summary,
whether focused retrieval was skipped, and the reason. The default query-budget
profile remains unchanged until a focused gate confirms that this generic stop
condition preserves answer quality.

Mixed numeric+narrative tasks are a stricter case. If the current task ledger
contains a `narrative_summary` sibling task, numeric child tasks must keep
focused operand retrieval even when primary operand coverage is complete. This
prevents a numeric-only child answer from starving the final aggregate answer of
the narrative evidence required by the user query.

### Deterministic Calculation Ownership And Selection

`financial_graph_calculation.py` is the graph-state adapter and orchestrator for
calculation. It may read and mutate graph state, decide when an owner runs, and
project owner results, but it must delegate state-free operand resolution and
formula execution to their owner modules.

`financial_operand_resolution.py` owns state-free candidate matching, grounding,
generic candidate selection, and merge behavior. Candidate selection must be
invariant to input order. If equally ranked candidates carry conflicting
normalized values, the resolver must abstain instead of selecting whichever
candidate arrived first. If tied candidates are value-equivalent, it may select
one through a stable provenance and candidate-identity ordering.

The same owner also owns the typed direct structured-evidence base scorer. It
receives only the operand and one evidence item, returns `no_structured_cells`
or `surface_contract_not_satisfied` at the existing early-return boundaries,
and otherwise returns `evidence_scored` with the component score. The ordered
aggregate-role preference predicate is co-located in this neutral owner and is
evaluated only at the original guarded call sites; callers must not replace it
with an eager boolean. These reasons are inspectable contract outputs, not
runtime trace fields. Graph and lookup-recovery callers consume the owner
directly; the former graph-private scorer and lookup-recovery scorer callbacks
are not compatibility seams.

The operand owner also exposes the plain public table-label metadata lookup
scorer. It receives only a graph-built slot and evidence item. An empty slot
returns `0.0` before evidence access; otherwise normalized-unit access, metadata
copy, the table-value-label gate, slot-first raw-unit fallback, raw-value digit
count, and the existing additive score components run in their literal order.
Unit hint, table source, slot-first source anchor, aggregate value role,
final-before-direct/subtotal stage, exact-or-compact matched label, and the final
known-versus-unknown unit adjustment retain their exact weights. Repeated getters,
normalizations, whitespace truthiness, surface iteration, compact-label set
construction, input immutability, and uncaught mapping, copy, string, regex,
iteration, and normalization exceptions are unchanged.

The three graph calls remain immediately after their respective table-label slot
builders and before caller-owned period, context, scope, ambiguity, tie, grouping,
or final-selection policy. The direct lookup and dependency-row callers still
invoke the scorer for an empty slot; the period-context caller still skips an
empty slot before scorer invocation. This seam owns only the state-free score,
not slot construction, evidence iteration, selection, or downstream policy, and
adds no wrapper, reason, flag, callback, config input, or trace field.

The operand owner also exposes the plain public direct target-metric fallback
conflict predicate. It receives only the graph-prepared target row, existing rows,
and required operands. Target-row then existing-row truthiness gates retain their
short-circuit order. Required operands cause a fresh row copy for each matcher
attempt and another copy when a row is retained; an empty requirement sequence
skips matcher access and copies each retained row once. No matching row returns
before target-unit access. Known existing units retain the repeated getter,
string, normalization, and uppercase evaluation in the set filter and expression.
A blank or `UNKNOWN` target unit, or a target unit outside that known set, is a
conflict.

The first matching required operand is copied in source order. Aggregate-role
preference vetoes replacement before target aggregate-like surface access;
otherwise value role and aggregation stage precede the lazy aggregate-label OR.
Existing rows then retain unit compatibility, value comparison, cleaned evidence/
source ids, and lazy table-source, statement-type, and source-anchor order. The
first differing structured row conflicts only with an aggregate-like target.
Inputs remain unmodified. The existing `operand_row_values_differ` helper keeps
its float `TypeError`/`ValueError` catch and raw/value fallback; the predicate adds
no broader catch, so mapping, matcher, copy, truthiness, string, normalization,
source-id cleaning, iteration, `RuntimeError`, and other exceptions propagate.

The sole graph call remains after target construction, evidence coercion, target
truthiness, and requested-scope acceptance. Graph retains the target builder,
evidence pool and coercion, scope gate, target adoption and evidence append,
candidate preparation, state/artifact projection, and final orchestration. This
seam owns only prepared direct-target fallback unit/value conflict and aggregate-
preference disposition. It does not establish target/evidence selection, whole-
operand precedence, total-code or executed-path reduction, performance, private-
mesh cleanup, or Phase 3 completion.

The operand owner also exposes a plain state-free single-row transform for
embedded raw-unit or rendered-unit normalization repair. It executes the former
graph body literally: `dict(row or {})` always creates a fresh top-level result,
including every no-op path, while untouched nested values retain their aliases
and the input remains unmodified. Raw and rendered surfaces, normalized-unit and
KRW-policy gates, inline parsing, the second policy copy, stable first eligible
rendered match, original-field preserve-or-fill writes, and all early returns keep
their existing order. The scaled tolerance and repeated float conversions are
unchanged. In particular, an embedded-unit row with a current `NaN` remains
unrepaired while a numeric raw surface with a matching rendered unit repairs its
current `NaN` value. Only the two existing normalized-value `TypeError` and
`ValueError` conversions are caught; mapping, truthiness, string, policy-copy,
regex, iteration, normalizer, and other exceptions still propagate.

The four graph calls remain at their original semantic positions: after a
dependency row is built and before structured-provenance/evidence work; after
candidate plan guards and before multi-row sibling-ratio alignment; and at the
two prepared ratio-append row construction sites before later coverage, merge,
and projection. The graph retains every applicability gate, row and evidence
builder, plan and operand-map propagation, evidence-driven sibling alignment, ratio and
append policy, and state/artifact/final orchestration. This seam adds no wrapper,
reason, application flag, graph state, callback, or trace field and claims only
single-row normalization-repair ownership.

The operand owner also exposes the plain state-free multi-row transform
`align_ratio_operand_units_with_shared_table_context`. It keeps the former graph
body literal: the length, copied render-policy, KRW and eligible-unit gates run in
their original order; configured units retain repeated normalization and eager
scale conversion; table id takes precedence over the complete section/statement/
scope fallback; and target selection remains the unsorted set-backed largest
configured scale. There is no separate tolerance or finiteness gate. Per-row
normalization may repair only part of an eligible group, and every policy,
mapping, copy, truthiness, string, float, `max`, or normalizer exception remains
uncaught in the same access order.

No-change returns the exact input list and row identities, including after
discarded top-level copies. Any accepted repair returns a fresh list and fresh
top-level dictionaries for every row while preserving untouched nested aliases,
stable row order, and input immutability. The three graph calls remain after the
outer length/evidence gates: no-evidence and unchanged-evidence paths pass the
original list, while an accepted evidence realignment passes the already aligned
list. The graph retains that evidence-driven outer aligner, candidate selection,
ratio-family preparation and operand-map propagation, ratio policy, and later
state/artifact orchestration. This relocation adds no wrapper, reason, flag,
callback, or trace field and claims only shared-context multi-row display-unit
alignment ownership.

Within `_extract_calculation_operands`, the same owner also receives the current
post-main operand rows, required candidate rows after producer-scope filtering,
and any coherent candidate rows built by the graph. It merges coherent rows into
the ratio candidate set first when they are present, evaluates required-operand
coverage, then prefers a complete ratio candidate set over the current rows;
partial ratio and non-ratio sets keep current rows first and fill only missing
requirements. The transformation is state-free, preserves preferred-row order
through the existing top-level shallow-copy merge contract, and does not receive
graph state or builder callbacks.

The operand owner also owns typed direct structured-row acceptance. The graph
invokes it only when direct rows are non-empty and either required operands exist
or the operation is `lookup`/`single_value`. For required operands, the owner
applies requirement matching and the required surface contract, then rejects
ambiguous context-table rows. Surviving `lookup`/`single_value` rows next apply
direct-support filtering when requirements exist and the ambiguity gate again;
without requirements, only that lookup ambiguity gate runs. This order and its
short-circuit behavior are contractual. Applied filters create ordered subsets
while retaining row-dict identity; no-stage paths retain the input-list identity.
The typed application flags are inspectable owner outputs, not runtime trace
fields. The owner receives explicit row, evidence, requirement, operation, and
ambiguity-context values, never `FinancialAgentState` or a callback.

After the graph has copied and matched a direct row, built the strongest
preferred evidence slot, invoked the owner scorer for current and preferred
evidence, and prepared the normalized peer raw-unit set, the operand owner
applies a typed state-free preferred-slot adoption contract. It tests a higher
current score and then an
equal score, retaining the current row unless a ratio candidate with the same raw
value improves peer-unit alignment. This strict comparison order is contractual;
NaN scores fall through to adoption as before. Other prepared candidates are
adopted through the existing exact overlay: the selected source and
numeric/display fields replace the current fields, unmatched current fields and
nested identities are retained, and the required label, concept, and role are
normalized into the matched fields. A
rejected result returns the prepared current-row identity; an adopted result is a
new top-level row. The graph assigns only adopted rows immediately, preserving
the existing sequential peer-unit behavior for later ratio operands. The typed
reason and alignment flag are inspectable owner outputs, not runtime trace
fields. This resolver receives no graph state, evidence builder, scorer, or
callback.

After the graph has built recovered period-comparison or coherent-ratio rows,
the operand owner also applies their typed, state-free adoption contract. The
graph calls this resolver only inside its non-empty recovered-row gate. Period
context is preferred first and fills missing requirements from the current rows;
coherent ratio context replaces the current rows instead. Both paths retain the
existing top-level shallow-copy and stable-order merge behavior. Evidence
adoption is restricted to ids referenced by recovered rows, excludes ids already
present in the current evidence list, and preserves the source order and
duplicates of newly adopted candidates. Applied paths return new row/evidence
lists without mutating their inputs; the no-context owner path retains the input
identities. Adoption reasons and adopted ids are inspectable owner outputs, not
runtime trace fields. The graph does not pass state or a builder callback.

After LLM extraction, the graph still resolves evidence, skips scope conflicts,
assigns `op_{index}` ids, coerces rows, and applies the operation-specific
applicability gate. For each surviving coerced row, the operand owner makes a
typed lookup direct-support decision while retaining that row's identity. When
required operands exist, a second typed owner seam applies ordered requirement
matching and surface validation, performs the lookup binding-policy rematch, and
then applies the existing direct-first missing-fill merge. Without a merge,
surviving LLM row identities and order are retained; a merge preserves direct
row order first and uses the existing top-level shallow-copy contract. The two
stages intentionally do not reuse the pre-LLM acceptance/ambiguity contract,
because their evaluation order differs and this path has no direct-row ambiguity
gate. Owner exceptions continue through the existing graph `try` boundary. The
typed reasons and application flags are inspectable contract outputs, not
runtime trace fields.

`financial_dependency_projection.py` owns dependency-binding summaries,
state-free dependency projection, and the direct-versus-dependency source-set
selector. The selector calls the co-located period-conflict and sibling-alignment
decisions directly; graph callers must not inject those decisions through
callbacks. It also owns the typed application of that selector to the main
operand path: final ratio override or purge, producer-scope filtering, duplicate
guarding, and missing-binding fill are one state-free transformation with an
inspectable result. Rows rejected by consolidation or dependency-producer scope
must also be removed from the active dependency snapshot so a later fallback
cannot reintroduce them. After the graph builds sibling and coherent evidence
contexts, the same owner applies the late path's coherent-first context merge,
alignment and direct-context preference, complete-context veto, and dependency
re-merge as another typed state-free result. The same owner then performs a
terminal typed finalization. The graph translates percent-point intent into a
generic `required_normalized_unit`; the owner applies the unit/value filter
without receiving the raw query or a callback. An active filter is terminal, so
an empty filtered result cannot fall through to preservation. With no filter and
no late rows, the owner preserves the post-main selected snapshot first and the
active dependency snapshot second, retaining order through top-level shallow
copies. Its reason fields are owner-contract outputs; they are not currently
projected as runtime trace fields.

The graph adapter still owns direct-row and evidence construction, coercion,
consolidation-scope filtering, target override, the acceptance applicability
gate, and direct structured preference preparation: runtime evidence overlay,
row copying and matching, peer-unit preparation, strongest-slot building,
query/report-scope score augmentation, ambiguity and tie-break policy, and
sequential iteration. It also owns recovered-context eligibility,
document/evidence collection, and period/ratio context-row builders.
It also owns recovery logging and ratio-recovered flag projection,
required-candidate builders, producer-scope filtering, the lazy coherent-context
builder gate, post-coercion LLM invocation and model-row dumping, evidence lookup,
scope-conflict skip, operand-id assignment, applicability and enclosing exception
boundaries, retry and
dependency-guard decisions, the percent-point query gate, other deterministic/LLM
fallback paths, coverage decisions, and state, trace, artifact, and logging
projection. Aggregate repair also remains graph-owned, so this is not a
single-owner end-to-end precedence claim. A task output may
override a direct row only through an explicit decision reason and provenance
record. The decision must retain the
current and candidate source identities needed to inspect value, materiality,
anchor, and scope conflicts; list order must never act as an implicit override
rule.

`financial_calculation_execution.py` owns plan validation and state-free
execution. Before execution it must validate `ordered_operand_ids` and
`variable_bindings` against the available operand-id set and the operation's
required roles. It returns a typed `CalculationExecutionOutcome` and does not
mutate graph state. The graph adapter projects that outcome into
`resolved_calculation_trace`, `structured_result`, and the task/artifact ledger.

The same owner builds supported deterministic difference/growth plans from
explicit inputs and returns a typed `DeterministicOperationPlanDecision` that
keeps both the raw plan and the selected ready/guarded plan. The graph retains a
thin adapter that reads state/query context. It first obtains the complete owner
plan and then evaluates the percent-point result-unit policy against that plan;
an eligible query with two `PERCENT` operands receives a copied plan whose
`result_unit` is `%p`. A non-eligible query or missing plan is unchanged. The
complete-plan ordering is a behavior contract distinct from the state-free owner
relocation. The primary planner still performs the existing runtime and
task/artifact projection.

The graph adapter contains a graph-private typed calculation-candidate seam. It
separates candidate preparation and canonical execution, deterministic result
projection, and graph-state/ledger projection. `_CalculationCandidateRun` and
`_run_calculation_candidate()` expose the prepared candidate and deterministic
projection together, while `_run_calculation_candidate_input()` accepts the same
graph-private pipeline input without resolving a graph-state trace first. The
primary `_execute_calculation()` graph-node adapter still applies the existing
state/ledger projector. Dependency and period recovery instead consume only the
candidate projection's operands, plan, and result copies for contract-valid
scalar recalculation. This is an internal graph decomposition, not a move of
preparation or result projection into the execution owner.

The execution module owns the typed, state-free value-only stale-result
assessment. `StaleCalculationValueAssessment` compares a canonical value from a
prepared `CalculationExecutionOutcome` with the projected result. It uses the
traced formula value only when the source-stated-result flag is active and keeps
the existing absolute/scaled tolerance and NaN behavior. Unavailable expected or
current values return typed non-stale reasons without mutating inputs.

The graph owns status/mode/formula applicability and the period-comparison
same-slot veto. After those gates, stale repair prepares and executes one
candidate, returns the original operand/plan/result identities on preparation
failure or a current assessment, and performs deterministic result projection
only when stale. A current result therefore still incurs one preparation and
formula evaluation; an actual stale repair evaluates the formula once rather
than through separate pre-preparation assessment and execution. Accepted repair
callers synchronize only their owned provenance surfaces. Render updates
selected/kept refs and the latest same-id calculation-result artifact without
reordering or replacing unrelated artifacts. Planning capture updates refs on
the returned row only. Aggregate repair snapshots its evidence window before the
first final filter, supersedes a stale provenance target only when that target is
unique, and re-filters the snapshot after acceptance. Ambiguous target refs must
be preserved rather than destructively removed.

`financial_aggregate_projection.py` owns that target selection as a typed,
state-free result together with the canonical `aggregate_result_operation_family`
normalization used by the selection. The graph passes the original ordered rows,
selected ids, evidence window, and pre-repair aggregate projection without
mutating them. It retains a one-line operation-family delegate for its existing
68 callers, plus repair acceptance, the pre-filter snapshot and accepted
re-filter, and answer/state orchestration. Moving the pure policy does not move
those sequencing responsibilities.

These projections do not change numeric freshness or repair acceptance, and they
are not a claim that the whole task/artifact ledger is synchronized. The
dependency and period scalar recovery callers no longer invoke the internal
`_execute_calculation()` wrapper or create a state/ledger projection that they
discard. Dependency recovery also no longer constructs and re-reads a strict
trace; period recovery retains the graph-state candidate wrapper. Their result,
operand order, plan, input immutability, and failure/no-op identity contracts
remain unchanged. For period recovery, a ready or guarded deterministic decision
supplies its selected plan directly, so those branches create no
planner/artifact/runtime projection.
A `not_applicable` decision enters the existing fallback continuation without
rebuilding the deterministic plan.

Dependency recalculation must isolate its explicit operands, plan, and result
from stale parent `structured_result` or `subtask_results` surfaces. The graph
passes selected plan, updated operands, active task, query, and evidence through
`_CalculationCandidateInput`; ratio formatting receives that active task and
the same pre-candidate operands explicitly.

The dependency owner classifies plan disposition by syntactic executability and
mode:

- an invalid or absent plan is `rebuild`, and the graph constructs the raw plan
  exactly once;
- an executable `single_value` plan is `reuse`, with no raw-plan construction;
- an executable non-`single_value` plan is `unsupported_mode`, and the graph
  leaves that recalculation row unchanged before raw-plan construction,
  candidate execution, or ratio formatting. When the enclosing alignment pass
  accepts no other row change, it returns the original ordered-result identity.

After a supported candidate runs, the dependency owner applies two state-free
post-candidate stages. Stage 1 receives only the candidate operand rows, plan,
and calculation result, not the graph-private candidate wrapper. In the existing
order it shallow-copies each operand row, the plan, and the result, makes a second
top-level mutable result copy, and decides readiness from normalized
`calculation_result.status`. Candidate-wrapper status, reason, and selected
evidence ids are not inputs. The trace result and mutable result are distinct
top-level dictionaries with retained nested identities; the typed readiness and
reason are owner-contract fields, not runtime trace fields.

The graph then retains the absolute-ratio query and transform invocation,
task-artifact/ledger construction and conflict short-circuit, and ratio or scalar
formatting. Only after those steps does Stage 2 mutate `formatted_result` when
the prepared answer is truthy and project the final row. Calculation operands
and plan use trace-first then graph-prepared fallback order; source ids use the
mutable result first and the current row second. The final row keeps the same
mutable calculation-result identity while copying the selected operand list,
plan dictionary, source-id list, and row top level with existing nested
identities. No selected-evidence or ledger projection is added.

Dependency structured-provenance adoption is a separate typed state-free seam.
The graph still builds and normalizes the dependency row, resolves structured
provenance from graph/store state, and skips the owner call entirely when that
lookup returns no provenance. For a truthy provenance mapping, the owner receives
only that read-only mapping and the graph-built mutable row. It mutates the same
row in the existing order: normalized source anchor, stable cleaned chunk id,
converted-display policy and current-value consistency, source-visible or
high-magnitude converted-unit preservation versus optional unit realignment, and
finally nonempty consolidation, statement, and table metadata overlay.

The owner returns the same row identity and retains untouched nested identities;
it does not mutate the provenance mapping. The existing
`unit_realigned_from_structured_provenance` row marker is set only when the
realignment succeeds. The typed `unit_realignment_applied` field and reason are
owner-contract outputs, not runtime trace fields. The existing float
`TypeError`/`ValueError` fallback is unchanged, no broader exception boundary is
added, and an exception after source-anchor or chunk-id adoption still propagates
with those earlier in-place mutations intact. The graph retains downstream
evidence lookup, row coercion, append/order, and all stateful provenance lookup.

The dependency owner also exposes the plain public structured-unit-realigned
operand/source-slot equivalence predicate. It receives only a graph-prepared
source slot, operand, and optional ordered structured-realigned operand sequence.
The operand marker is the first access. A truthy marker creates a fresh top-level
operand copy without touching the fallback sequence, role, raw value, or source-id
surfaces. Without the marker, operand role uses `role` before lazy
`matched_operand_role`, followed by raw value and cleaned ids. Fallback rows retain
their order: role and raw value are read before their filters, and only survivors
reach cleaned-id overlap and a top-level copy. No candidate returns `False` before
source-slot access.

For a nonempty candidate list, source ids are cleaned and `task_output:` ids are
excluded before source raw value and normalized unit. Candidates are scanned in
order through raw equality, normalized-unit equality, cleaned non-task ids, and a
nonempty source/candidate-id intersection. The fallback preselection deliberately
does not remove `task_output:` ids. The predicate does not mutate inputs and adds
no catch: mapping, copy, truthiness, string, normalization, source-id cleaning,
iteration, hashing, prefix-check, and other exceptions propagate.

The sole graph call remains inside the dependency-coherence rank method after
operation-family, source-task, source-slot material, anchor, and projection-
mismatch preparation. Graph retains source-slot maps, candidate and marked-row
construction, source-task selection, rank disposition, ratio-scope checks, and all
provenance/adoption/state/artifact/final orchestration. This seam owns only the
prepared equivalence predicate and adds no wrapper, result carrier, reason, flag,
callback, config input, compatibility alias, or trace field. It does not establish
whole coherence-rank or provenance-adoption ownership, unit-policy improvement,
total-code or executed-path reduction, performance, private-mesh cleanup, or
Phase 3 completion.

For supported ratio recalculation, artifact precedence is split at a narrower
boundary. The graph coerces the recalculated top-level `result_value`; an
unavailable value returns before artifact-row construction. It then builds the
ordered task-artifact rows from graph/ledger state. The dependency owner receives
only those prepared rows and the already-coerced numeric authority. It applies
outer-row status with calculation-result fallback, resolves artifact numeric
authority in the order result value, primary normalized value, primary raw value,
then row value, skips values within the existing scaled tolerance, and selects
the first material conflict. A selected row is a new top-level shallow copy with
the preservation marker and retained nested identities. The typed reason and
flag are inspectable owner outputs, not runtime trace fields. The graph retains
absolute-ratio query/transform invocation and caller projection. In particular,
when the enclosing pass accepts no other alignment, its no-change identity contract can
discard the local selected-row copy; owner selection is not a guarantee that the
artifact row reaches final output.

Prepared dependency-source ratio-result projection is another typed, state-free
dependency-owner seam. It receives only the graph-prepared calculation result,
answer slots, metric label, numerator and denominator slots, numeric result and
units, rendered value, and cleaned source-row-id list. It returns a fresh
calculation-result dictionary with fresh answer-slot, primary-value, group/role,
and singleton-list containers while retaining untouched nested identities. The
exact source-row-id list is shared by result source rows, result evidence ids,
answer-slot source rows, and primary-value source rows; the exact numerator and
denominator slot objects are reused in their group and role lists. Mapping
expansion, literal overwrite, source-list truthiness/indexing, input immutability,
and uncaught exception order remain unchanged. This seam adds no reason,
application flag, or runtime trace field.

The graph retains source-slot construction and selection, component ranking and
slot construction, same-slot and numeric gates, ratio formula/query and absolute
policy, result extraction, source-id cleaning, owner applicability/laziness, and
compact-ratio formatting. This seam does not own dependency precedence or final
answer selection.

Dependency-row display and normalized-unit inference is a plain public,
state-free `financial_dependency_projection.py` primitive. It reads the slot raw
unit first, then lazily falls back to the sibling result unit and finally the
empty string. A truthy whitespace-only slot value therefore still suppresses
the sibling fallback before normalization. It then reads and normalizes the
slot normalized unit, using `UNKNOWN` for a missing or normalized-empty value.
Known normalized units return without reading the render policy.

Only `UNKNOWN` takes a fresh render-policy snapshot. Policy membership is
evaluated in percent, KRW, then count order; the KRW branch uppercases the
configured normalized unit with `KRW` fallback without adding another whitespace
normalization step. No mapping, truthiness, string, normalization, policy-copy,
iteration, or set-construction exception is caught, and neither input is mutated.
The four graph calls remain at their existing semantic positions, including the
conditional second inference after a prepared row changes. The graph retains all
state, task, binding, slot/source selection, row repair and construction,
task-output and retrieved-context ratio append/merge, evidence, artifact, and
final orchestration.

Dependency task-output normalized-KRW consistency is a separate plain public
dependency-owner predicate. It short-circuits dependency resolution, the
`task_output:` source prefix, and normalized-KRW gates before reading value
fields. Raw value is read before raw-unit truthy fallback to result unit, so a
truthy whitespace-only raw unit suppresses that fallback before normalization.
It then preserves the existing operand normalization, expected-KRW gate,
current-before-expected conversion, and inclusive scaled tolerance.

The normalized-value mapping access is inside the conversion `try`; a
`TypeError` or `ValueError` raised by that access, current conversion, or expected
conversion returns `False`. Earlier mapping `TypeError`/`ValueError`, all
`RuntimeError` instances, and other truthiness, string, normalizer, or arithmetic
exceptions propagate. The predicate never mutates its input and adds no result
wrapper, reason, flag, callback, config input, or trace field. Its two graph calls
remain at the original row-coercion and table-metadata-repair positions. The graph
retains both caller gates, operand/evidence selection and mutation, table repair,
state, and final orchestration.

The nested non-`ok` path returns the graph-supplied local row. The enclosing pass
returns the original ordered-result and original row identities only when no
other row changes; when another row changes, an unchanged row may be the graph's
top-level copy. Caller-owned ordered results, state, and aggregate projection
remain unmodified; Stage 2 intentionally mutates only its graph-prepared mutable
calculation-result input.
This contract does not move primary state/artifact projection, repair acceptance,
aggregate sequencing, structured-provenance lookup, or absolute-ratio
orchestration out of the graph. It does
not establish whole-ledger synchronization, broad performance or total-code
reduction, a single end-to-end calculation owner, or complete Phase 3. Exact
change chronology and validation evidence live in
`docs/history/implementation_history.md`.

## 9. Aggregate Subtask Projection

For collapsed-ratio runtime recovery, the aggregate owner exposes a typed,
state-free absolute-magnitude projection over graph-prepared mutable copies of
the calculation result, answer slots, and primary value. The graph still
resolves the runtime trace, checks collapsed-row eligibility, ratio completeness,
and query intent, prepares those copies, and retains downstream dependency
coherence, compact-answer, numeric-coverage, and final projection.

The owner preserves the existing mutation and exception order: it reads and
coerces `result_value` twice for a negative value, updates the copied result and
primary value, applies the existing unit fallbacks, invokes the existing
calculation rendering owner, and only then attaches the prepared slots. It
returns the same calculation-result identity it received. `TypeError` and
`ValueError` remain caught; when rendering fails after the numeric update, the
positive `result_value` remains on the copied result while its old attached slots
and rendered value remain. `RuntimeError` still propagates. No decision reason,
application flag, or runtime trace field is added by this seam, and it does not
move query policy, rendering policy, aggregate sequencing, ledger state, or
final projection into the aggregate owner.

Prepared aggregate answer-candidate packaging is a typed, state-free aggregate-
owner seam. Base packaging receives the raw answer, optional claim-id iterable,
and existing `sync_projection`, `sync_rendered_for_aggregate`, and `status_ok`
values. It returns a fresh candidate dictionary whose insertion and evaluation
order remains answer, selected claim ids, then the three flags. The answer is
normalized with `_normalise_spaces(str(answer or ""))`. Claim ids retain source
order and duplicates, blanks are removed, and every retained id preserves the
existing two `str(claim_id).strip()` evaluations. The flags are coerced to
`bool` in their existing order. The returned claim list is new and the input
iterable is not mutated.

Refreshed packaging first executes `dict(refreshed_answer or {})`, then evaluates
the copied payload's answer with the fallback, then its selected-claim ids, and
only then delegates to base packaging. A truthy whitespace-only refreshed answer
therefore still suppresses the fallback before normalizing to empty. Neither path
catches mapping, string, iteration, or boolean-conversion failures; the existing
cross-function access and stop order remains observable. The result adds no new
decision reason or trace field.

Seven direct base-packaging calls remain at their original graph branch or loop
positions, and the single refreshed-packaging call remains after graph-owned
narrative refresh. Candidate discovery, scoring and selection, branch gates,
refresh policy, call placement and laziness, application invocation and answer
precedence, projection/state/evidence mutation, rebuild, and final orchestration
remain graph-owned. This seam claims only prepared candidate payload/schema
ownership and deletion of the two specific private graph packagers, not
application-policy or composition ownership, broad private-surface cleanup,
total-code or executed-path reduction, performance improvement, or Phase 3
completion.

Prepared aggregate answer-candidate application and final-answer projection
synchronization are separate typed owner seams. The application owner receives
the graph-prepared mutable aggregate projection, the current selected-claim
sequence, and the raw prepared candidate mapping. It normalizes the candidate
answer first. When `sync_projection` is true, it evaluates
`sync_rendered_for_aggregate` and `status_ok` before entering projection sync;
the sync mutates the same projection in `formatted_result`, conditional
aggregate-mode `rendered_value`, then optional `status="ok"` order. It then
normalizes nonempty claim ids and returns a new `List[str]` with stable
current-first, candidate-second first-occurrence order. The result retains the
same aggregate-projection identity and any existing calculation-result and
nested identities. Candidate and selected-id inputs remain unmodified.

The existing lazy and partial-mutation exception boundaries remain intact. A
false sync flag does not read the rendered/status flags or mutate the projection.
An empty normalized answer still reads both flags, but sync does not create a
calculation result; claim merging still runs. A rendered-mode lookup failure may
propagate after `formatted_result` changed and before rendered/status updates,
while a candidate claim-id lookup failure may propagate after projection sync
completed. These typed results add no decision reason, application flag, or
runtime trace field. Candidate builders and refresh, answer selection and
precedence, mutable aggregate state/evidence, artifact/ledger work, stale repair,
and final orchestration remain graph-owned.

Aggregate composition uses the public `AggregateCompositionState` carrier and a
state-free transition owned by `financial_aggregate_state.py`. The transition
normalizes the supplied answer before lazily reading the current answer. It
consumes all current claim ids before incoming ids, preserves two
`str(claim_id).strip()` evaluations for every retained id, and returns a fresh
stable current-first `dict.fromkeys` deduped list. It reads the current projection
override before reset handling; truthy reset wins, an accepted dictionary override
retains exact alias identity, and other inputs retain the current alias.

`narrative_answer_locked=None` preserves the current value; other inputs are
converted with `bool`. The transition evaluates `clear_feedback` independently for
planner then deterministic feedback and reads each current field only on that
field's false path. It always returns a fresh carrier without mutating its input
and catches no normalization, access, iteration, string, hash, truthiness, or
constructor exception. The graph retains the five producers and their gates,
sequential call placement and state handoff, initial/final carrier construction,
later `_replace` transitions, broader answer/claim/projection precedence,
state/evidence/LLM work, and final orchestration. This seam claims only public
carrier and common-transition ownership, not broader composition ownership,
performance or executed-path reduction, private-mesh cleanup, or Phase 3
completion.

Prepared aggregate-provenance filtering is another typed state-free aggregate
owner seam. The graph supplies the aggregate projection and its already-selected
kept-evidence-id sequence. If the normalized kept set is empty, the owner returns
the exact input projection before reading or copying it. Otherwise it shallow-
copies the projection, calculation result, derived metrics, truthy answer slots,
and accepted dictionary subtask rows in the existing order. It applies the shared
source-id cleaner, removes only unkept `ev_` and `recon::` ids, and retains other
ids in stable order. The input projection and kept-id sequence remain unmodified;
untouched nested values retain their identities.

The existing conditional projection shape is part of the contract. A falsy
answer-slot value is not overwritten. While rebuilding truthy answer-slot
subtasks, non-dictionary entries are skipped and the rebuilt list replaces the
old list only when at least one dictionary row remains; therefore an all-invalid
or empty list retains its original nested identity, while a mixed list drops its
invalid entries. No exception is caught, and earlier local copies are not exposed
when normalization or mapping access fails. The seam adds no decision reason,
application flag, or trace field. Evidence filtering and kept-id selection,
projection-rebuild gating, selected-claim filtering, final-answer surface-operand
append, stale repair, ledger work, and final orchestration remain graph-owned.

Recursive nested aggregate-row consistency is a separate typed, state-free
aggregate-owner seam. The graph supplies its already-promoted, dependency-
aligned, preserved-field-merged ordered rows. Before descending, the owner builds
the complete current-row authority map from normalized nonempty task ids; when
ids repeat, the last top-level row remains authoritative. It then traverses, in
stable order, calculation-result subtask rows, calculation-result answer-slot
subtask rows, and row-level answer-slot subtask rows. Non-dictionary nested items
are skipped. A matching non-cyclic task id uses the current top-level row, while
the ancestor-id stack prevents replacement cycles and depth greater than eight
returns a shallow row copy without descending further.

Each owner call returns a new ordered list, and every top-level input row becomes
a new dictionary; even an empty input returns a distinct empty list. Truthy
calculation-result dictionaries are shallow-
copied. Answer-slot dictionaries are copied and reassigned only when their nested
subtask rows are truthy and rewritten; otherwise untouched nested values retain
their existing identities. The owner does not mutate the supplied rows and does
not catch mapping access, normalization, `dict`, or `list` failures. It preserves
the existing map-before-recursion and access/copy order and adds no reason, flag,
or trace field.

The graph keeps the empty-projection and unchanged promotion/alignment gates,
which return the original ordered-result and projection identities without
calling the owner. On the changed path it retains nested-result promotion,
preliminary projection rebuild, dependency alignment, preserved-field merge, and
the final projection rebuild around the single owner call. State/evidence,
artifact/ledger, repair, and answer orchestration also remain graph-owned. This
seam does not establish final-projection ownership, broad executed-path or total-
code reduction, performance improvement, broad private-surface cleanup, or Phase
3 completion.

Prepared aggregate projection-row surface synchronization is a typed, state-free
aggregate-owner seam. The owner receives only the graph-selected projection row,
raw answer, and raw rendered value. It normalizes the answer only to select a
numeric surface: ratio/growth use the first candidate and other operation
families use the last. The exact raw answer remains on the row and formatted
result, and the exact rendered input retains its existing conditional updates.

The owner always returns a fresh top-level row. A missing or falsy calculation
result returns before replacement, preserving any present empty nested-result
identity and key shape. A truthy result is shallow-copied; result, answer-slot,
primary-value, lookup series, role/group container, and derived-metric copies are
created only behind their existing gates. Lookup dict-only filtering, first-item
replacement, empty-list primary fallback, role-before-group order, untouched
nested aliases, repeated operation-family resolution, and uncaught mapping/list/
normalization exception order remain unchanged. Inputs are not mutated, and no
reason, application flag, or trace field is added.

The graph retains candidate-index and answer-sentence selection, numeric conflict
and coverage gates, rendered-value extraction, row iteration, lookup primary-slot
preparation and its truthy gate, updated-row task mapping, ordered/slot-row
propagation, projection rebuild, and final orchestration. This seam does not own
answer selection, aggregate precedence, arithmetic-component synchronization,
final projection, state/evidence, or artifact/ledger work.

Prepared aggregate arithmetic-component synchronization is a separate typed,
state-free aggregate-owner seam. It receives one graph-prepared projection row
and the ordered lookup primary-slot sequence. Empty lookup input returns the
exact row before operation-family access; an ineligible row returns the exact
row after one family resolution. An eligible row returns a fresh top-level row,
copies a truthy calculation result, and conditionally creates fresh answer-slot,
role/group, series, and difference/sum delta containers. Untouched nested values
and non-dictionary role/group items retain their identities. Empty or all-invalid
series keep the original key/list alias, while an attached nonempty dictionary
series drops non-dictionary items.

Concept equality precedes bidirectional label matching and the first matching
lookup slot wins. Replacement values retain the existing `None`-only overlay,
repeated getter, source-field fallback, and alias behavior. Operation family is
resolved again before delta projection. The owner normalizes or copies no input
eagerly, mutates no input, catches no exception, and adds no reason, application
flag, or trace field.

The graph retains lookup primary-slot preparation and its truthy gate, sequential
per-row owner calls, task-id/equality update mapping, ordered/slot-row propagation,
projection rebuild, and later state/evidence/artifact/ledger and answer
orchestration. This seam owns only prepared lookup-slot to arithmetic component,
series, and delta synchronization; it does not own lookup selection, projection-
row surface selection, row-map propagation, aggregate precedence, or final
projection.

Canonical aggregate-result identity and growth sign consistency are plain,
state-free `financial_aggregate_projection.py` primitives. Signature resolution
copies the calculation result and then the selected answer slots before applying
metric precedence from the row, answer slots, and task id. A metric that normalizes
to blank returns before operation-family resolution; otherwise the canonical
aggregate operation-family owner supplies the optional `family:metric` prefix.

Growth sign ranking resolves that same operation-family owner first. A non-growth
row returns rank `1` after that first owner access but before the rank body's
repeated/direct calculation-result copy. A growth row then copies calculation
result, answer slots, current slot, and prior slot in that order, converts current
before prior, catches only `TypeError` and `ValueError`, and returns same-sign `2`,
opposite-sign `0`, or unknown `1` for zero, `NaN`, missing, or invalid values;
infinities retain their numeric signs. Mapping and other access exceptions remain
uncaught.

The graph keeps all seven signature and four rank calls at their existing semantic
positions, including the explicit `dict(row)` repair input and repeated calls in
comprehensions and nested ranking. It still owns full dedupe, rank tuples, nested
promotion, result precedence, and state/evidence/artifact/ledger orchestration.
This boundary claims only the two canonical primitives, not full aggregate ranking
or promotion ownership, total-code or executed-path reduction, performance,
broader private-surface cleanup, or Phase 3 completion.

Ratio calculation-result display synchronization is a typed, state-free
`financial_answer_slots.py` owner seam. The owner receives the exact prepared
calculation-result dictionary. Status and operation-family gates return the same
identity, as does the source-stated-result veto. It reads the raw result before
coercing the formula value and then the result value. A formula mismatch outside
the scaled tolerance creates a shallow top-level result and derived-metric copy;
that copy remains authoritative even when a later unit, parser, or equivalence
gate vetoes display replacement. Without a mismatch, successful synchronization
mutates the exact supplied result.

Percent-unit policy normalization, ratio formatter and target parsing, primary-
slot/result/formatted current-surface precedence, numeric equivalence, and fresh
answer-slot/primary-value updates preserve their existing order. Untouched nested
references remain shared. Formula/result numeric coercion and the later result
`float` conversion catch `TypeError` and `ValueError`; formatter, parser, mapping,
truthiness, policy, and other exceptions propagate. The owner result adds no
reason, application flag,
or trace field; the existing calculation-result synchronization marker remains
unchanged.

The graph retains ordered-row copy, operation-family and truthy-result gates,
before/after rendered comparison, compact-answer construction, row answer/result
updates, and all state, active-subtask, operand, period, and metric formatting.
The two owner calls remain at their original positions. This seam does not own
formula or ratio calculation, query policy, compact-answer rendering, row
selection/propagation, aggregate precedence, state/evidence, or artifact/ledger
work.

Prepared late aggregate-artifact payload synchronization is a typed, state-free
`financial_task_artifacts.py` owner seam. It first creates a fresh top-level copy
of every supplied artifact, then scans in stable order for the first raw exact-id
match. A match receives a fresh payload and artifact dictionary: the raw final
answer, fresh operand list, fresh plan/result dictionaries, and raw-answer
`[:200]` summary overwrite their existing fields in the original evaluation
order. No match still returns a fresh list and fresh top-level artifacts. Untouched
nested values, operand items, and plan/result nested values retain their aliases;
inputs remain unmodified and mapping, truthiness, conversion, iteration, and
slice exceptions remain uncaught. The seam adds no reason, application flag, or
trace field.

The graph retains its initial artifact-list copy before all ratio, rendered,
completeness, compact-formatting, and projection-mutation gates. It calls the
owner after projection mutation only when the original artifact argument is not
`None` and the artifact id is truthy: `None` or a blank id remains owner-zero,
while an empty list plus a nonblank id remains owner-one and the applicable path
keeps both top-level copy passes. Aggregate artifact creation/finalization and all
later ledger/final orchestration remain graph-owned. This seam does not establish
artifact creation or ledger-level id/order ownership, whole-ledger synchronization,
ratio/query/formatting policy, state ownership, or final-projection ownership.

Prepared reconciliation evidence-reference enrichment is a separate plain,
state-free `financial_task_artifacts.py` owner seam. Its owner-private collector
accepts only strict dictionary operand rows and reads `evidence_id`,
`evidence_ids`, `source_evidence_id`, `source_evidence_ids`, `source_row_id`,
`source_row_ids`, `row_id`, `row_ids`, `candidate_id`, and `candidate_ids` in that
order. It cleans each row through the private source-id helper imported from
`financial_runtime_normalization.py`, then performs stable first-seen dedupe. The
collector remains private; only `enrich_reconciliation_artifact_refs(...)` is a
public owner export.

The public owner collects operand refs before cleaned extra refs. If their stable
dedupe is empty, it returns the exact supplied artifact-list identity before
task-id, optional task-id, or artifact access. Otherwise it normalizes the primary
task id and optional task-id sequence in the existing filter-before-expression
order, including repeated string conversion for retained ids. It returns a fresh
list and a fresh top-level copy of every artifact while retaining untouched nested
aliases and stable artifact order. Exact reconciliation kind, optional task-id
membership, repeated payload access, reconciliation-result type, and lowercased
`ok`/`ready` status gates keep their existing short-circuit order. Matching
artifacts receive existing raw `evidence_refs` first and newly collected refs
second under stable dedupe; the pre-existing raw refs are not cleaned. A blank
target-id union matches every otherwise eligible reconciliation artifact. Inputs
remain unmodified, and mapping, copy, truthiness, string, iteration, hashing, and
access exceptions remain uncaught.

The graph retains the two call placements and all prepared inputs. The operand-set
path calls the owner after artifact/task/active-task preparation and passes its
result to operand-set artifact construction. The aggregate-feedback path builds
source task ids, operand rows, and integrity refs before the owner, then passes the
owner result into task-artifact trace and integrity/replan work. An owner exception
still stops those downstream consumers. This seam owns only prepared
reconciliation evidence-reference collection and enrichment; it does not own
artifact creation/finalization, whole-ledger or graph state, integrity/replan
policy, or final orchestration, and it establishes no total-code, executed-path,
performance, broad private-surface, or Phase 3 completion claim.

Aggregate answers must keep child task provenance visible after the final
projection. Each item in `answer_slots.subtask_results` should expose:

- `task_id`: child task identifier
- `operation_family`: child operation family, copied from the child task,
  answer slots, or calculation result
- `source_row_ids`: cleaned source row ids used by the child result
- `source_evidence_ids`: cleaned evidence item ids used by the child result,
  especially for narrative or prose-only child tasks that do not resolve to a
  structured numeric row
- `calculation_result`: child calculation result when available
- `answer_slots`: child answer slots when available

`source_row_ids` may include deterministic dependency references such as
`task_output:<task_id>` together with structured row/evidence ids, but it must
not contain display-only placeholders such as `"None"`. Runtime code should
derive these fields from existing task, slot, trace, and evidence artifacts.
It must not infer them from company names, benchmark ids, or topic-specific
keywords.

`source_evidence_ids` is not a replacement for `source_row_ids`. Numeric and
structured lookup children should keep row/candidate provenance in
`source_row_ids`; narrative children should keep retrieved evidence ids in
`source_evidence_ids` when the child answer is grounded in prose evidence but
has no structured row id.

The purpose of this projection is traceability: evaluator, citation, and
debugging paths should be able to inspect the same child operation, source
rows, and source evidence ids that the aggregate composer used. If a child
value came from prose lookup or retrieved seed evidence, the promoted evidence
id/source row id should stay attached through the aggregate projection rather
than disappearing during final answer synthesis.

When an aggregate numeric child depends on lookup subtasks through
`task_output:<task_id>`, the calculation trace and the serialized child result
must be realigned from the latest producer `answer_slots` before answer
composition. This alignment is allowed to use generic slot provenance,
structured row/header metadata, unit hints, period hints, dedupe, and dependency
bindings. It must not choose values through company names, benchmark ids,
question ids, or topic-specific runtime keywords. If an aggregate projection
contains a weaker echo of the producer result with the same raw display but a
conflicting normalized value, the producer lookup slot remains the source of
truth.

Evaluator-side runtime projection should preserve these fields when it flattens
answer slots into operand-like rows. For aggregate answers it should also
publish a deduped provenance summary, for example under
`calculation_result.derived_metrics.aggregate_subtask_provenance`, so debugging
and retrospective checks can inspect child row/evidence provenance without
re-running the agent.

The compatibility `calculation_operands`, `calculation_plan`, and
`calculation_result` mirrors are not the source of truth. Current caller,
evaluator, and benchmark surfaces consume `resolved_calculation_trace` first,
then task/artifact ledger projections, then aggregate subtask projections.
If an explicit historical resolver must fall back to legacy top-level
`calculation_*` fields, it must mark
`resolved_calculation_trace.runtime_projection.source = "legacy_top_level"` and
`legacy_fallback = true`; canonical or ledger-derived projections must set the
same metadata with `legacy_fallback = false`.
If only `structured_result` is available, the resolver may expose it as a
non-legacy `structured_result` projection. If legacy top-level operands or plans
must be combined with `structured_result`, the projection remains
`legacy_top_level` with `legacy_fallback = true` and records
`calculation_result_source = "structured_result"`.
Evaluator and benchmark review exports should surface projection source,
legacy-fallback status, and calculation-result source as first-class audit
fields alongside the full `resolved_calculation_trace`.
`_resolve_runtime_calculation_trace()` is strict by default. Historical replay
or retrospective readers that need old-bundle compatibility must opt in with
`allow_legacy_top_level = true`. Strict mode rejects top-level `calculation_*`
fallback while still allowing non-legacy `structured_result` projection.
Evaluator result export, benchmark serialized/review export, eligible
analyst/MAS artifact handoff consumers, current-runtime debug readers,
reflection retry planning, formula planning input resolution, calculation
execution input resolution, dependency-projection recalculation result readers,
route-decision readers after formula planning/calculation,
render/verification/retry preparation readers, and late runtime numeric answer
shaping use strict mode, so those review, runtime handoff, debug, retry,
planning, execution, routing, and answer preparation surfaces do not resurrect
legacy top-level mirrors.
Historical replay and retrospective readers may opt into legacy compatibility
when they read older result bundles. `FinancialAgent.run()` and all live-agent
current-state readers use strict mode and do not revive top-level calculation
mirrors.

Reflection retry behavior is being moved toward a bounded capability contract.
See [self_reflection_capability_contract.md](self_reflection_capability_contract.md)
for the target request/plan/action/report boundary and allowed retry
strategies.

The former `_resolve_runtime_structured_result()` public compatibility adapter
has been removed. `FinancialAgent.run()` reads `structured_result` directly and
falls back only to the canonical `resolved_calculation_trace.calculation_result`.
Historical compatibility remains inside explicit resolver call sites rather
than a live public projection helper.
`_runtime_trace_state_update()` is now a strict canonical state-update helper:
callers must pass operands, plan, and result explicitly.

The remaining cleanup scope for internal top-level `calculation_*` mirrors is
tracked in
[`internal_calculation_mirror_cleanup.md`](internal_calculation_mirror_cleanup.md).
That note separates live/public strict readers, historical replay tools, and
internal scratch-state cleanup candidates.

Benchmark runner serialized-result, smoke-summary, and review export surfaces
are strict current-contract projections. They may expose runtime projection
source metadata for audit, but must not use legacy top-level `calculation_*`
mirrors to populate exported `resolved_calculation_trace` fields.

Live evaluator rows are also strict current-contract projections. Fresh
`RAGEvaluator.evaluate_one()` scoring must consume canonical runtime projection
only; legacy top-level `calculation_*` mirrors are reserved for replay,
retrospective, or explicit compatibility tools.

Historical answer replay is an explicit compatibility tool. It may accept
legacy top-level `calculation_*` mirrors from older saved benchmark bundles, but
canonical `resolved_calculation_trace` data must take precedence when both
surfaces are present.

Retrospective operand-grounding rescoring follows the same compatibility policy:
it may accept legacy top-level operands from historical rows, but canonical
`resolved_calculation_trace.calculation_operands` must take precedence.

Retrospective evaluator ablation follows the same compatibility policy for
historical rows. Legacy top-level operands and calculation results may be used as
fallback inputs, but canonical trace operands/results must take precedence.

Retrospective ontology retrieval ablation is not a historical row reader. It
reruns current graph nodes against a persisted store, so it must use strict
current-state projection and must not revive legacy top-level `calculation_*`
mirrors for outcome operands or calculation result display.

Current-run debug helpers, including `debug_math_workflow.py` and
`debug_reference_note_workflow.py`, follow the same strict policy. Their JSON
debug output must be based on canonical `resolved_calculation_trace` and must
not use top-level `calculation_result` fallback to populate structured result
display fields. Calculation diagnostics should be exposed under
`debug_traces.calculation`, not as a fresh ops-level top-level
`calculation_debug_trace` bridge.

`mas_analyst_smoke.py` is a mixed migration smoke reader. Direct
`FinancialAgent.run()` outputs remain compatibility-oriented because they
exercise the public export bridge and may compare older payloads. MAS artifact
readers in the same smoke are current handoff readers and must stay strict:
artifact operand counts, statuses, and calculation-result payloads must not be
populated from legacy top-level mirrors.

`FinancialAgentState.resolved_calculation_trace` should use the
`RuntimeCalculationTrace` shape, and rows in `subtask_results` should use the
`TaskResultRecord` shape. New graph nodes should write these typed projections
directly and treat top-level `calculation_*` mirrors as temporary compatibility
outputs for older internal readers.
MAS nodes that register new ledger tasks should publish `AgentTask` entries
through `build_agent_task()`. Planner, critic, and synthesis task creation must
normalize task id, assignee, instruction, status, context keys, retry count,
kind, label, dependencies, artifact ids, and blocked reason through that helper.
MAS final synthesis should preserve the existing string `final_report` for
caller compatibility, but also publish a typed `FinalReport` projection under
`final_report_record`. The typed projection must carry the final answer, status,
source task ids, source artifact ids, evidence refs, and subtask result
summaries; the `aggregated_answer` artifact payload should mirror that record.
MAS worker nodes should publish `EvidenceRecord` entries through
`build_evidence_record()`. Analyst and Researcher evidence-pool rows must expose
the common `task_id`, `creator`, `kind`, and `source_anchor` fields while
placing producer-specific details such as allowed terms, operand values, units,
periods, and block type under `metadata`.
MAS critic nodes should publish `CriticReport` entries through
`build_critic_report()`. The helper owns verdict normalization, target artifact
refs, acceptance reason, blocking issues, deterministic score, and feedback, and
the `critic_report` artifact payload should mirror the typed report.
Consumers that need an acceptance decision should use
`financial_artifact_contracts.critic_report_runtime_acceptance_state()` so
runtime close/retry decisions stay tied to verdict, target refs, reasons, and
blocking issues instead of offline evaluator-style numeric thresholds.
MAS nodes that write artifacts should publish `Artifact` entries through
`build_artifact()`. The helper owns artifact id defaults, kind/status/summary
normalization, payload projection, evidence link/ref mirroring, producer task id,
and metadata normalization while preserving the existing compatibility `content`
field.
MAS consumers should read typed artifact projections first: answer and
calculation status from `payload`, evidence from `evidence_refs`, and only then
fall back to compatibility `content`/`evidence_links` for older callers.

When a node updates the runtime trace through `_runtime_trace_state_update()`,
the helper publishes only `resolved_calculation_trace` and `structured_result`;
it no longer has an opt-in path for top-level `calculation_*` compatibility
mirrors. Current converted branches include calculation verification skip, formula
planning no-operands, formula planning missing-required-operands, and
calculation execution failure paths, plus deterministic incomplete-plan
branches for lookup plans and operation guard failures. Formula planning
structured-output failures, operand extraction structured-output failures, and
LLM formula-plan guard failures also omit compatibility mirrors once their
readers consume `resolved_calculation_trace`. Render fallback, verification
structured-output failure, and aggregate synthesis fallback branches follow the
same rule. Render success, verification success, aggregate success, calculation
execution success, and operand extraction direct/guard/synthesis/LLM success
branches now also omit compatibility mirrors. Formula planning deterministic
lookup/operation/ontology success branches and LLM success branches follow the
same canonical trace contract, and the remaining formula planning
guard/incomplete branches now do too. Formula planning reads incoming operands
through strict current-state resolution and passes those operands explicitly
through its canonical trace updates. Calculation execution reads incoming
operands and plans through strict current-state resolution and passes the strict
operands and plan explicitly through result/failure trace updates. Late runtime
numeric answer shaping and dependency-projection recalculation result readers
also read through strict current-state resolution. The
non-formula reset/no-op branches in
the calculation node also omit compatibility mirrors, and all
`financial_graph_calculation.py` call sites now rely on the helper's mirror-free
contract. Active-task artifact projection uses strict current-state resolution as
well: empty `resolved_calculation_trace` must not resurrect legacy top-level
`calculation_*` fields. A stale aggregate is replaced only by canonical active
task/artifact ledger material. Downstream readers must use
`resolved_calculation_trace`.
