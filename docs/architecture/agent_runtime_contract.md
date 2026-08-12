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

Required-operand prose numeric-evidence surface filtering through
`surface_contract_numeric_evidence_items(...)` is a plain, state-free
`financial_operand_resolution.py` owner seam. Left-to-right falsy evidence and
required-operand gates each return a fresh empty list. On the nonempty path the
owner shallow-copies every attempted evidence row before reading `claim`,
`quote_span`, and `raw_row_text` in that order, joining and normalizing their
string surfaces, and applying blank then digit gates. Every attempted required
operand is copied before positive-surface matching, the lazy negative-surface
veto, and nearby numeric extraction.

Only a complete match reads `evidence_id`, then lazily falls back to
`source_anchor` and the first 120 normalized-surface characters. The stringified
key participates in one global first-seen set. A unique key appends the already
fresh shallow evidence row and breaks its requirement loop; a duplicate continues
through later requirements. Result and input order remain stable, the outer list
and retained top-level rows are fresh, untouched nested values remain aliased,
inputs are unmodified, and truthiness, iteration, mapping copy, string, join,
normalization, regex, predicate, extraction, and hash exceptions remain uncaught
at their existing stages.

The graph retains evidence and reconciliation preparation, required-operand list
construction, direct-grounding computation, and the unconditional owner call at
the existing pre-narrative position, including when direct grounding is false.
It passes the exact current evidence list and fresh prepared requirement list,
then retains narrative/restriction gates, surface-result merge/dedupe/logging,
the later missing-required fallback-row merge, LLM/state work, and final
orchestration. The exact owner result feeds those consumers and an owner exception
still stops every later stage. This seam claims only required-operand prose
numeric-evidence surface filtering, not retrieval or evidence selection,
faithfulness or filtering-policy improvement, new behavior, performance,
total-code or executed-path reduction, broad private-surface cleanup, or Phase 3
completion.

Retrieved ratio-context task-metric surface detection through
`ratio_context_has_metric_surface(context_evidence, task)` is another plain,
state-free `financial_operand_resolution.py` owner seam. It reads task
`metric_label`, `target_metric`, `label`, and `name` before eagerly materializing
`aliases`. Retained values are stringified and normalized in the comprehension
filter and again for storage; an empty result returns `False` before context
access. Otherwise stable `dict.fromkeys` dedupe and hashing create one label-only
operand per retained metric surface.

The owner then shallow-copies every context evidence and metadata mapping and
materializes all context surfaces before attempting any match. Evidence fields
are read as `claim`, `quote_span`, `raw_row_text`, and `source_context`; metadata
fields are read as `row_label`, `semantic_label`, `aggregate_label`,
`table_summary_text`, `table_title`, `table_context`,
`table_row_labels_text`, `table_value_labels_text`, and `row_text`, followed by
list materialization of `semantic_aliases` and `row_headers`. The later matching
pass normalizes surfaces in stable order, skips blanks, and tests metric operands
lazily. The first match returns `True`; otherwise the result is `False`. Inputs
remain unmodified, and mapping, copy, truthiness, list, iteration, string,
normalization, hashing, equality, and matcher exceptions remain uncaught in the
existing order.

The graph retains existing ratio-result iteration and every family, task,
signature, status, artifact-backed, numeric-value, component-completeness, and
scaled-tolerance gate. Only the first eligible conflicting row invokes the owner
with the exact current context-evidence and task objects; the graph preserves the
logical inversion in which an owner `True` means no conflict and `False` means
conflict. Earlier exits are owner-zero, and an owner exception stops later rows
and downstream conflict work. Ratio recalculation, projection/adoption,
precedence, evidence selection, state, artifact, and final orchestration remain
graph-owned. This seam claims only retrieved ratio-context task-metric surface-
detection ownership, not conflict or precedence policy, recalculation or
adoption, evidence selection, behavior or policy improvement, performance,
total-code or executed-path reduction, broad private-surface cleanup, or Phase 3
completion.

Evidence-local unit and period coercion are plain, state-free
`financial_operand_resolution.py` owner seams. Public
`coerce_operand_unit_from_evidence(*, raw_value, raw_unit, evidence_item)` first
shallow-copies evidence metadata, reads `unit_hint`, stringifies and strips the
current raw unit, and always invokes the owner-private value-surface inference
before later fallback gates. Inference normalizes and digit-gates the raw value,
then eagerly reads claim, quote span, raw-row text, and `source_context`. It tries
the render-policy parenthetical value/unit pattern before the generic inline
policy pattern, preserving candidate concatenation, repeated string filtering,
stable longest-first unit alternation, alias lookup, first-match return, and the
private right-boundary predicate.

The boundary predicate catches only `IndexError` from a missing match group.
End-of-text returns before policy access. The remaining path shallow-copies render
policy, materializes every allowed prefix with repeated string conversion, applies
stable lazy prefix matching, then reads the block pattern and tests exactly the
single character at the unit boundary. Other mapping, copy, slicing, string,
iteration, normalization, regex, match-group, and boundary exceptions propagate.

When inference returns a surface unit, the owner performs operand normalization in
surface, current, and hint order, followed by all three normalized-family
conversions. The private core confirmation reads only claim, quote span, and raw-
row text; it deliberately excludes `source_context`. It normalizes value, unit,
and core before their falsy gate, then preserves compacting, unit-policy/alias/
pattern access, right-boundary checks, match-group order, and first exact value/unit
match. Confirmed support preserves an exactly normalized current display unit and
otherwise returns the surface unit. A usable surface family conflicting with the
current family first or hint family second returns `current_unit or unit_hint`;
other surface paths return the inferred unit.

Without a surface unit, no-hint, no-current, and normalized-equality exits precede
render-policy access. Only the remaining mismatch path reads the bare-numeric
pattern, builds ambiguous-KRW and configured display-unit sets in literal order,
and lets the hint replace the current unit when all final conditions hold. Repeated
conversion, set, mapping, regex, and exception behavior is unchanged; neither input
is mutated.

Public `coerce_operand_period_from_evidence_surface(row, evidence_item)` builds the
same three-field private core surface first. Blank core, zero or multiple distinct
evidence years, and a current period already containing the sole evidence year
return the exact input row. A conflicting current-period year returns a fresh
shallow row with `period` then `period_source` updated. With no period year, the
second period/label/matched-label scan keeps exact identity on a matching year and
otherwise returns the same fresh two-field update. Stable year dedupe, nested
aliases, input immutability, access order, and uncaught exceptions remain unchanged.

The graph-evidence builder calls the public unit owner after retaining raw-value/
unit fallback and header/family gates. The calculation graph calls it from own-
evidence alignment and from the retained row coordinator, and calls the public
period owner after metadata overlay but before direct structured-value, magnitude,
and precision work. Own-evidence iteration, slot/evidence selection, normalization,
copy/adoption, and all row-coordinator guards remain graph-owned. Lookup recovery
imports the public unit owner directly: its direct unit-hint branch remains owner-
zero, both other branches invoke the owner in their existing positions, and the
graph-local normalize closure remains without injecting a callback. This boundary
claims only state-free evidence-local unit inference/coercion and period coercion
ownership, one callback removal, and old-body deletion—not unit/render policy or
behavior improvement, evidence construction, structured-value/magnitude/precision
ownership, performance, total-code or executed-path reduction, broad private-
surface cleanup, or Phase 3 completion.

Ontology-driven ratio denominator sign handling is another plain, state-free
`financial_operand_resolution.py` seam. Public
`apply_operation_sign_policy(operands, *, operation, operation_family)` normalizes
`operation` first. A normalized `ratio` skips operation-family normalization;
otherwise the family is normalized once. When neither is ratio, the function
returns the exact input list before any row access.

The ratio path shallow-copies rows in stable order. Role resolution uses truthy
`matched_operand_role`, lazy `role`, then `""`; non-denominator rows skip policy
resolution. The owner-private `_binding_policy_for_operand_row` first shallow-
copies the row policy, then resolves truthy `matched_operand_concept`, lazy
`concept`, and `""` before stringification and stripping. A blank concept returns
the copied row policy without ontology access. Otherwise it shallow-copies the
ontology binding policy and overlays the row policy so explicit row values win.

Only exact normalized `ratio_denominator_sign == "magnitude"` reaches value
conversion. `None`, float `TypeError` or `ValueError`, zero, positive, and `NaN`
leave the row unchanged. A negative value writes positive `normalized_value`,
`sign_policy_applied`, the pre-transform float as `source_normalized_value`, and
the merged `binding_policy` in that order. If any row changes, every returned row
is a fresh top-level copy and nested aliases remain; otherwise the exact original
list and row identities are returned. Inputs remain unmodified and exceptions
outside the two conversion catches propagate in their existing order.

The graph calls this owner once for a surviving prepared candidate after growth
recovery and the growth-period conflict exit, and before equality-gated operand-
map/runtime propagation, lookup-magnitude coercion, execution, state, artifact,
and final projection. All preparation, evidence/dependency repair, recovery,
conflict-call/failure projection, propagation, execution, and orchestration remain
graph-owned. This seam
claims only binding-policy merge and ratio-denominator magnitude-transform
ownership plus old-body deletion—not sign-policy improvement, broader ontology
ownership, behavior, performance, total-code or executed-path reduction, or
Phase 3 completion.

Prepared KRW raw-unit and growth-operand checks are three more plain, state-free
`financial_operand_resolution.py` seams. Public
`repair_krw_normalized_values_from_raw_units(operands)` shallow-copies every row
in stable order before reading normalized unit. Non-KRW rows skip raw surfaces.
The KRW path reads `raw_unit` before lazy `result_unit`, then `raw_value`, and
normalizes that raw pair before reading current normalized value. `None` owner
values or non-KRW owner units return through the unchanged path. Float conversion
catches only `TypeError` and `ValueError`; equality and either zero precede the
absolute-magnitude distortion calculation, and only distortion at least `100.0`
repairs the row.

A repaired row writes prior numeric value to `source_normalized_value`, then
owner numeric value, owner unit, and `unit_normalization_repair_source` in that
order. Any repair returns the fresh stable list with every top-level row copied;
without a repair the exact input list and row identities return despite transient
copies. Nested aliases remain and inputs are not mutated. Mapping, copy, string,
normalizer, comparison, truthiness, and arithmetic exceptions outside the two
float catches propagate.

Public `align_growth_operand_units_when_raw_scale_matches(ordered_operands)`
requires exactly two rows. It scans current role and then prior role independently;
when neither is explicit it assigns positions `0, 1`, and when one is missing it
uses the other position. It shallow-copies current then prior before concept
gates. Two truthy unequal concepts stop, while a blank concept does not. Raw
units must both be truthy and unequal, and both normalized units must uppercase
to exact `KRW` without whitespace normalization. Raw numbers parse current then
prior before normalized values are read.

Missing or zero raw numbers and missing normalized values stop. Ratio conversion
catches only `TypeError`, `ValueError`, and `ZeroDivisionError`; both ratios must
be positive, raw ratio is inclusively within `0.01..100.0`, and scale distortion
is at least `100.0`. The owner then normalizes the prior raw value with the current
raw unit. Only a non-`None` KRW result produces a fresh prior row with raw unit,
normalized value/unit, and `unit_alignment_source`; the outer list is fresh while
the non-prior row retains identity and nested aliases. All no-op paths return the
exact input list, inputs remain unmodified, and uncaught access/copy/string/
normalization/arithmetic exceptions propagate.

Public `growth_operand_periods_conflict(ordered_operands)` also requires exactly
two rows before any row access. It scans for current first, then restarts at row
zero for prior; each scan stops at its first match and shallow-copies only that
matched row. Missing either role returns `False`. Per row, truthy `period`
precedes lazy `label`, then the owner calls `period_match_key` for current and
prior in that order. Both calls occur before the final
`bool(current and prior and current == prior)` truth/equality chain. Input rows
remain unmodified and mapping, iteration/copy, string, key-owner, truthiness, and
equality exceptions propagate.

The graph retains `_prepare_calculation_candidate` and all carriers. Public table-
metadata repair is called after evidence-row coercion; raw-unit repair follows it
before operand indexing and plan access. Growth alignment remains after donor-unit
propagation and before duplicate-prior recovery; only a non-equal owner result is
adopted. Period conflict remains after duplicate recovery and its adoption, and
before sign policy and execution; `True` returns exact `insufficient_operands` /
`growth operands share the same period`, `False` continues, and an owner exception
stops downstream work. Evidence selection and row coercion, donor propagation,
duplicate recovery, operand-map/runtime adoption, sign/execution, state, artifact,
ledger, and final projection remain graph-owned. These seams claim ownership
relocation and old-body deletion only, not behavior, accuracy, ranking, performance,
total-code or executed-path reduction, benchmark improvement, or Phase 3 completion.

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

The caller now lives inside
`financial_aggregate_projection.aggregate_result_dependency_coherence_ranks(...)`
after source-task, source-slot material, anchor, and projection-mismatch
preparation. The enclosing aggregate-rank contract is specified in Section 9.
This predicate itself still adds no wrapper, result carrier, reason, flag,
callback, config input, compatibility alias, or trace field, and it does not move
provenance adoption, promotion, state, artifact, ledger, or final orchestration.

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

Dependency task-output normalized-KRW consistency is a plain public operand-owner
predicate. It short-circuits dependency resolution, the
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
wrapper, reason, flag, callback, config input, or trace field. Its two semantic
placements are one external graph call during evidence-row coercion and one owner-
local call from public table-metadata repair.

`repair_krw_operand_units_from_table_metadata(operands, evidence_items)` is the
co-located public operand-owner transform. It builds the evidence-id index first;
an empty index returns the exact input list before render-policy access. Otherwise
it snapshots `CALCULATION_RENDER_POLICY`, normalizes configured KRW display units
and scales, then shallow-copies each operand in stable row order before invoking
the consistency predicate. A consistent dependency row skips raw-value/unit and
evidence surfaces.

For a non-KRW normalized row, only `COUNT`, `UNKNOWN`, or blank with a nonblank raw
value may scan alternate table evidence. The scan preserves evidence order, requires
a table-backed surface containing the value, applies the row label when present,
and accepts an inline configured KRW display unit or the table `unit_hint`. For an
already-KRW row, raw value/unit precede evidence lookup; the matched evidence must
be table-backed, expose a distinct configured unit hint with known scales and at
least `100.0` distortion, and visibly contain the raw value. Both branches require
the owner normalizer to return a non-`None` value and exact `KRW`.

A repair writes `source_raw_unit`, optional `source_normalized_value`, repaired
`raw_unit`, `normalized_value`, `normalized_unit`, `rendered_value`, and
`unit_normalization_repair_source` in that order. Current-value conversion catches
only `TypeError` and `ValueError`; all other mapping, iteration/copy, policy,
truthiness, string, regex, normalization, float-scale, comparison, formatting, and
arithmetic exceptions propagate. Any repair returns a fresh stable list with every
top-level row copied and nested aliases preserved; without a repair the exact input
list and row identities return despite transient copies. Neither operands nor
evidence are mutated.

The graph retains the external predicate branch and table-repair caller, evidence/
query/row preparation, caller carriers, ordinary table-repair assignment, failure
projection, state, artifacts, and final orchestration. This move changes ownership
only; it adds no behavior, trace field, callback, benchmark, performance, total-
code, executed-path, or Phase 3 completion claim.

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

Canonical answer-slot material detection is the plain public
`financial_answer_slots.answer_slot_has_material(slot)` predicate. A non-dictionary
or falsy slot returns `False` before field access. The owner then stringifies,
strips, and lowercases `status`; exact `missing` returns `False`. A
`normalized_value` other than `None` returns `True`, including zero and `NaN`.
Only the remaining path resolves truthy `rendered_value` before lazy `raw_value`,
then stringifies, strips, and boolean-coerces that surface. It does not copy or
mutate the slot and catches no truthiness, mapping, string, or other exception.

All consumers retain every semantic call placement, prepared slot, surrounding
short circuit, and later owned work; the graph's pre-existing callback pass-
throughs remain unchanged. The shared predicate owns only slot material. Answer-
projection policy consumes it for material decisions and aggregate projection
consumes those decisions for ranking and dedupe; graph state remains outside it.

Aggregate source preparation is owned by three plain public
`financial_aggregate_projection.py` functions. `aggregate_row_primary_answer_slot`
copies `calculation_result`, selects truthy result answer slots before the lazy row
fallback, copies those slots, and returns a fresh copy of truthy `primary_value` or
a fresh empty dictionary. Nested values keep their aliases and no access or copy
exception is caught.

`aggregate_source_slot_by_task_id(ordered_results)` scans the supplied sequence in
stable order, skips non-dictionaries, normalizes task ids, and calls the primary-
slot owner with a shallow row copy. Empty ids and slots are skipped. For each
retained slot it resolves consolidation scope from slot before row and fills only
a missing slot scope; it then normalizes the row metric label and fills only a
missing slot label. Duplicate task ids replace the value without moving the key's
first insertion position. The returned map and retained top-level slots are fresh,
untouched nested values remain shared, and inputs remain unmodified.

`aggregate_source_task_ids_for_operand(operand, source_slots)` resolves the
normalized explicit `source_task_id` before cleaned `task_output:` row ids, removes
that prefix, filters blanks, and applies stable first-occurrence dedupe. Any
explicit id suppresses inference; an empty source map also returns immediately.
Only inference resolves normalized `role` before lazy `matched_operand_role`, then
scans the source map in insertion order. Each source slot is shallow-copied,
filtered by `answer_slot_has_material`, and retained when
`dependency_lookup_slot_match_score(slot, operand, role) >= 12`. None of these
owners catches normalization, mapping, copy, iteration, hashing, predicate, or
matcher exceptions.

Dependency coherence is owned by two public aggregate functions and one owner-
private candidate collector. `_aggregate_result_candidate_operands(row)` copies
the calculation result before selecting truthy result answer slots over the row
fallback. It collects strict dictionary operands in this exact order: row
`calculation_operands`, result `calculation_operands`, every
`components_by_group` value, then every `components_by_role` value. Every retained
occurrence is a fresh shallow copy; order and duplicates are preserved and nested
values remain shared.

`aggregate_result_dependency_coherence_ranks(row, source_slot_by_task_id=None)`
resolves operation family first. A family outside `ratio`, `sum`, `difference`,
and `growth_rate` returns `(1, 1)` before source-map copy or candidate collection.
The eligible path shallow-copies the source map, collects candidates, and creates
a separate ordered shallow-copy list of candidates with truthy structured-
realignment markers.

For each candidate, source-task resolution receives that candidate and the copied
map. Only the first resolved id selects the material source slot. A material slot
sets the seen-material flag before source-anchor then operand-anchor normalization;
projection mismatch is evaluated even when the anchors already mismatch. A
mismatch that is not exempted by the structured-realignment predicate returns
dependency rank `0` and scope rank `2` only when an earlier operand established
scope, otherwise `1`.

Ratio scope evaluation follows that projection block and may use a nonmaterial
source slot. Its generator stops at the first present source slot even when that
slot normalizes to a blank scope; later ids are then not consulted. A nonblank
source scope sets the seen-scope flag before operand-scope resolution. A mismatch
returns scope rank `0` and dependency rank `2` when any material source was seen,
otherwise `1`. Exhaustion returns dependency rank `2` or `1` from seen material
and scope rank `2` or `1` from seen scope. Inputs are not mutated and mapping,
copy, truthiness, normalization, predicate, iteration, and other exceptions remain
uncaught.

`aggregate_dependency_slot_coherence_rank_for_operands(...)` prepares its row
left-to-right: raw operation family, a fresh stable list of shallow-copied strict
dictionary operands, then a shallow calculation-result copy. Preparation failure
stops before `aggregate_source_slot_by_task_id(ordered_results)`; source-map
failure stops before the rank owner. The wrapper returns only the dependency-rank
element. All eight former external placements retain their gates and adoption:
three direct graph rank placements, one direct owner-private aggregate placement,
and four graph wrapper placements. The wrapper's internal rank call remains
owner-local.

Answer-slot period policy is public in `financial_answer_slots.py`.
`answer_slot_period_hint(slot)` normalizes the explicit period first and returns
it before label, policy-pattern, or regex access. Otherwise it normalizes the
label, reads the configured pattern, skips regex for a blank pattern, and returns
the normalized full match or `""`. `period_match_key(value)` truthiness-resolves
and stringifies the value, normalizes spaces, then removes every non-digit with
`re.sub(r"\D", "", ...)`; Unicode digit semantics therefore follow Python regex.
Neither owner copies input or catches mapping, truthiness, string, policy, regex,
match, or normalization exceptions. All 21 semantic placements remain: 17 graph
calls and four answer-projection consumer calls.

Material projection policy is public in `financial_answer_projection.py`.
`growth_row_has_conflicting_periods(row)` shallow-copies calculation result,
result-first answer slots, and current/prior slots; each normalized slot period
precedes its result-period fallback. A blank key or unequal keys returns `False`
before answer surface access. Equal nonblank keys normalize row answer/formatted/
rendered and result formatted/rendered surfaces, collect distinct `20\d{2}` years,
and return `True` only when fewer than two are present.

`material_gap_feedback_for_subtask_result(row)` resolves metric label from row
metric label, answer, task id, then policy default; status from row before result;
and rendered material from result formatted value, result rendered value, then row
answer. Operation family resolves result answer-slot family, row plan family,
result derived-metric family, row plan operation, then a `concept_` metric-family
suffix. Aggregate-subtask rows scan nested results in reverse, skip only
conflicting nonblank metric labels, and recurse owner-locally. Lookup/single-value
require a primary slot. Difference and growth require current/prior slots, then
delta-or-primary and primary respectively; growth checks period conflict first.
An `ok` status plus a rendered digit preserves the existing growth and ratio/sum
result fallback. Missing labels and final feedback use only
`CALCULATION_FEEDBACK_POLICY` templates; unknown families return `""`.

`subtask_row_has_material(row)` shallow-copies result and result-first answer
slots, probes fresh copies of `primary_value`, `current_value`, `prior_value`, then
`delta_value`, and stops at the first material slot. Only the remaining path checks
result rendered value before row answer, then truthiness of a fresh source-row-id
list. The three public owners catch no access, copy, normalization, regex,
iteration, recursion, predicate, formatting, or other exception. Consumers retain
32 external placements: 24 graph, five planning, and three aggregate-owner calls;
gap recursion and its growth-conflict call are owner-local.

Aggregate ranking and dedupe are in `financial_aggregate_projection.py`.
Owner-private `_aggregate_result_rank(row, source_slot_by_task_id=None)` returns
exactly `(status, material, answer, growth_sign, dependency_slot,
scope_coherence, operand_count)`. Status precedence is row before result;
material precedes normalized answer presence, growth sign, dependency/scope
coherence, and list-materialized source-row count. Status ranks remain `ok=4`,
`partial|ready=3`, `insufficient_operands|retry_retrieval=1`, and otherwise `0`.

Public `nested_aggregate_result_rank(row)` returns exactly `(status, material,
gap_free, non_aggregate, growth_sign, source_count, digit_count, answer_length)`.
It shallow-copies result first, resolves status from row before result, then
evaluates the remaining dimensions left-to-right. Source count cleans row source
ids, result source ids, row selected claims, then result evidence ids. Answer text
uses row answer before result formatted value and rendered value; digit count uses
`re.findall(r"\d", ...)`.

Public `dedupe_aggregate_subtask_results(ordered_results)` builds the source map
before its signature/rank loop. Blank signatures pass through without ranking.
For each signature, a greater rank wins and an equal later index replaces the
incumbent; winners and passthrough rows are then sorted by their retained original
index.
The returned list and every retained top-level row are fresh, nested aliases are
preserved, and input rows remain unmodified. Mapping, copy, truthiness, iteration,
hashing, ranking, sorting, regex, and dependency exceptions remain uncaught.

The graph retains two nested-rank calls in the existing promotion comparator and
eight dedupe placements across the existing aggregate coordinators, including
their gates, argument identity, adoption, and exception stop. Promotion,
sync/rebuild, nested traversal, mutable state/evidence, artifact/ledger, callbacks,
and final orchestration remain graph/planning-owned. These owner moves make no
behavior, ranking, accuracy, performance, total-code, executed-path, or Phase 3
completion claim.

Narrative term, variant, prepared-evidence sentence, context-inclusion,
prepared-document snippet, and retrieved-source preservation surfaces are public
in `financial_text_surface.py`.
`narrative_context_terms(query)` stringifies and normalizes the query before
tokenizing it with the reviewed character regex. It then
materializes the configured stopword set. Tokens are processed in source order:
strip, minimum length, exact stopword, and numeric-content gates precede stable
first-seen dedupe. Policy, regex, string, normalization, iteration, hashing, and
containment exceptions remain uncaught, and the query is not mutated.

`narrative_focus_variants(query)` eagerly builds the normalized lowercase union
of generic-focus and context-reuse exclusions, then calls the term owner. For
each retained term it evaluates the normalized whole term, parenthetical matches
in match order, and the normalized outside-parentheses surface. Blank, short,
and generic candidates are discarded before stable first-seen dedupe.
`parenthetical_focus_variants(query)` also calls the term owner, but ignores a
term without an opening parenthesis and retains only matched parenthetical and
outside-parentheses surfaces of length at least two. Neither owner mutates input,
and their access, policy, regex, string, normalization, iteration, containment,
and hashing exceptions propagate.

`narrative_context_sentence_from_evidence(query, evidence_items)` applies the
narrative-request gate before term extraction and returns `""` for either
failure. It then scans `evidence_items or []` in stable order, shallow-copies each
attempted evidence mapping, eagerly assembles normalized source text from source
anchor and the evidence metadata's section path/section, and resolves claim before quote
span before raw-row text. Blank claims are skipped. Score is query-term overlap
plus the existing priority-section and support-level bonuses. Only a strictly
higher score replaces the current candidate, so equal scores retain the first
candidate. A positive winner is sentence-split and reduced to the first split
sentence when one exists; an empty split result preserves the unsplit winning
claim. That selected surface is then truncated to 220 characters and right-
stripped. Inputs and nested values are
unmodified; mapping, copy, truthiness, string, join, normalization, policy,
iteration, containment, split, and slicing exceptions remain uncaught.

`include_narrative_context_if_needed(answer, *, query, narrative_context)`
normalizes answer and context eagerly. Blank answer, blank context, or a failed
narrative-request gate returns the normalized answer before term or exclusion
policy access. The remaining path calls the term owner, materializes configured
reuse exclusions, and preserves exact case-sensitive containment semantics. If
any retained query term is in the context and any such term is already in the
answer, or the full context is already contained in the answer, the answer is
returned unchanged. Otherwise the normalized context is prefixed to the answer
and normalized once more. The function does not mutate inputs and catches no
access, truthiness, string, normalization, policy, iteration, containment, join,
or owner exception.

`policy_required_realized_snippet_from_doc(*, doc, policy)` copies document
metadata before reading the policy's required realized terms. A blank term set
returns `""`; otherwise the owner eagerly assembles value labels, row labels,
table summary, table context, and page content in that order and normalizes the
joined surface. It retains the first configured term with a case-insensitive
surface match and opens a 520-character window at that match. Numeric candidates
use the existing parenthesized/negative/decimal/percent regex, then discard exact
20xx years and unsigned integer surfaces of at most two digits. The label uses
the existing case-sensitive optional-parenthetical regex and reviewed footnote-
suffix cleanup. Two numeric candidates plus a unit use the current/change
template; one plus a unit uses the current template. Otherwise the first split
sentence containing the term case-insensitively and any digit is normalized and
truncated to 220 characters; an absent sentence falls back to the first 220
window characters. Particle and sentence calls are owner-local. The document,
metadata, policy, and nested values remain unmodified, and access, mapping,
truthiness, string, policy, regex, format, normalization, iteration, slicing, and
owner exceptions remain uncaught.

`preserve_retrieved_narrative_source_surface(answer, evidence_items)` normalizes
the answer and returns early for a blank answer or evidence sequence. Numeric
candidates are extracted before answer sentence splitting; an empty sentence
result returns before narrative policy or evidence access. The owner scans
evidence stably, shallow-copies each attempted item, accepts only
`retrieved_narrative::` ids, resolves claim and then quote span before raw row
text, and rejects blank/equal or missing-marker claims. Content terms are the
owner's narrative-context terms of length at least three. Quote sentences are
scored by term overlap; only a strictly greater score replaces the incumbent, so
the first tie wins. The minimum score remains `max(2, min(4,
len(claim_terms) // 2 or 1))`. Answer sentences are considered stably; missing-
marker sentences and sentences supporting the answer's numeric candidates are
never replaced. A matching claim or sufficient overlap replaces at most the
first still-unclaimed answer sentence, and the final sentence sequence is joined
and normalized. The answer, evidence list, item mappings, and nested values stay
unmodified. Mapping, copy, truthiness, string, prefix, policy, term-owner,
numeric-owner, sentence-owner, iteration, containment, hashing, comparison, and
normalization exceptions remain uncaught.

Across the selected text boundary, 288 old graph definition-span lines now form
seven public APIs. Of 27 calls, 22 remain graph-external and five are owner-local:
context terms 13/5, focus variants 2/0, parenthetical variants 3/0, evidence
sentence selection 1/0, context inclusion 1/0, document snippet 1/0, and
retrieved-source preservation 1/0. Retired graph-private references are zero.
The graph callers retain their exact gates, arguments, scoring/adoption order,
input identities, and exception stop. The two latest 69- and 72-line graph
bodies are 68- and 71-line owner functions. The clean `7aa3e23..55f7ce3`
range changed source by `+152/-146`, tests by `+1,304/-11`, and all four changed
files by `+1,456/-157`; the AST-counted unittest inventory and full discovery
moved from 1,633 to 1,638. Retrieval,
evidence ids/windows/provenance, evidence construction, composition, mutable
state/evidence, task/artifact ledger, promotion, sync/rebuild, callbacks, and
final sequencing remain graph-owned. Benchmark refresh was **NOT RUN**, remote
CI is unverified, and this ownership relocation establishes no behavior,
accuracy, ranking, performance, total-code, executed-path, benchmark, schedule,
or Phase 3 completion claim.

Aggregate dependency-source preparation is now owned by
`financial_aggregate_projection.py`. Public
`ratio_rebuild_component_seeds(row, calculation_result, answer_slots)` scans
`components_by_group` and then `components_by_role` in mapping order before the
row-first/fallback-result calculation operands. Every dictionary seed is
shallow-copied, its normalized explicit or fallback role fills only a missing
`matched_operand_role`, and the dependency role group sends it to numerator or
denominator. A seed outside those groups is retained only when the answer-slot
material gate succeeds. Inputs and nested values are not mutated; mapping,
iteration, copy, string, normalization, group, and material-gate exceptions are
uncaught.

Owner-private `_dependency_source_text_match_score(left, right)` normalizes both
surfaces before its blank gate. Exact equality adds six, containment adds three,
and the return adds the size of the case-folded intersection of narrative terms
of length at least two. Public `dependency_source_slot_match_score(slot, seed,
role)` calls the dependency lookup-slot scorer first, then builds slot label,
metric, concept, and period text plus seed label/matched-label, concept, and
period/matched-period text, and adds the owner-private text score. All access,
string, normalization, policy-term, and scorer exceptions propagate.

Public `best_dependency_source_for_seed(...)` shallow-copies and normalizes the
seed's role, matched role, label, and concept before inferring source task ids.
Excluded task ids are skipped. Inferred tasks receive a floor of 12; nonpositive
scores are discarded. Ranking is descending by `(score, task_id)`, so the
lexically greater task id wins an equal score. No winner returns four empty/zero
values; a winner returns a shallow copy of its slot, the prepared seed, and the
score. Public `component_slot_from_dependency_source(...)` shallow-copies and
role-completes the seed, delegates source-operand construction with exact task id,
builds the answer slot with the exact default role, and then records role, source
task id, and `dependency_resolved = True`. No selected helper catches owner or
access exceptions.

The five former graph bodies span 131 old lines and now occupy
33 + 21 + 15 + 35 + 23 = 127 owner lines. Nine calls finish at seven graph-
external and two owner-local; retired graph-private references are zero. The
source-slot map with its bound operation-family callback and the 145-line ratio
caller with compact-ratio state/trace/result projection remain graph-owned. The
clean `8dc6054..df3b63b` range changed source by `+157/-147`, tests by
`+1,299/-27`, and all five files by `+1,456/-174`; six tests moved full discovery
from 1,638 to 1,644. Benchmark refresh was **NOT RUN**, remote CI is unverified,
and this relocation establishes no behavior, accuracy, ranking, performance,
total-code, executed-path, benchmark, schedule, or Phase 3 completion claim.

Aggregate narrative row-focus projection is now owned by
`financial_aggregate_projection.py`. Public
`narrative_row_focus_sentence(ordered_results=..., focus_variants=...)` returns
`None` before row access when focus variants are empty. Otherwise it scans rows
in order, resolves operation family before normalized metric family, and accepts
only a narrative-summary row. It cleans claim ids, reads narrative markers,
splits the row answer, and for each sentence performs normalization, table-noise,
then abbreviation-fragment filtering. The first sentence containing any focus
variant case-insensitively wins as `(0, sentence, claim_ids)`. Stable row/sentence
order, input identity, and nested values are preserved; access, truthiness,
iteration, normalization, policy, splitter, predicate, and comparison exceptions
are uncaught.

Public `narrative_row_focus_context(query=..., ordered_results=...,
focus_variants=..., max_sentences=2)` also returns before query-term access for
an empty focus list. It filters narrative rows and sentences through the same
owner surfaces, then scores each focus sentence as five per focus hit, three per
impact-marker hit, one per query-term hit, minus one per numeric surface. Stable
descending sorting retains the first equal-score sentence. A winning sentence
that already contains an impact marker returns alone; otherwise later sentences
and then earlier sentences with query or impact support are appended until the
exact maximum. Claim ids and joined context are returned without mutating rows.
Owner, policy, regex, splitter, predicate, access, normalization, iteration,
sorting, containment, and comparison exceptions propagate.

The two former graph bodies span 95 old lines and occupy 26 + 67 = 93 owner
lines. Their three calls remain graph-external: sentence selection once and
context selection twice. Retired graph-private definitions are zero. The
`fcf4c55` source diff is `+105/-101`, tests are `+721/-3`, and the whole commit is
`+826/-104`; five tests moved full discovery from 1,644 to 1,649. Dynamic
narrative-driver discovery, growth answer composition/validation, evidence/state
sequencing, and artifact/ledger work remain graph-owned. Benchmark refresh was
**NOT RUN**, remote CI is unverified, and this relocation establishes no
behavior, accuracy, ranking, performance, total-code, executed-path, benchmark,
schedule, or Phase 3 completion claim.

The growth display/material cluster subsequently moved in `d4d19fc`; its exact
owner semantics are specified in the source-task compatibility section below.
Aggregate result support/reuse predicates are now also public in
`financial_aggregate_projection.py`.

`aggregate_results_include_dependency_numeric_result(ordered_results)` scans in
stable row order and resolves aggregate operation family before any result or
source access. Only ratio, sum, difference, and growth-rate rows continue. It
shallow-copies the calculation result and sends result-level source ids, row-level
source ids, and nested row/result operand source ids to source-id cleanup in that
exact order. Any `task_output:` id returns `True` before dependency-flag access;
otherwise only a truthy `dependency_resolved` on a dictionary row operand returns
`True`. Result operands contribute source ids but not that final flag gate.

`aggregate_results_include_source_task_slot_realignment(ordered_results)` tests
raw `aligned_from_source_task_slots` truthiness before operation-family access and
accepts the same four arithmetic families. Stable scan returns on the first
supported aligned row. `answer_reuses_narrative_summary_text(answer,
ordered_results)` normalizes the answer and returns before row iteration when it
is blank. It scans only narrative-summary rows, normalizes each row answer,
requires at least 20 characters plus one digit, and accepts either exact substring
direction. `answer_reuses_numeric_narrative_summary_text(...)` calls that owner
first and skips numeric extraction on `False`; otherwise it extracts from the
original answer, removes candidates whose exact kind is `percent`, and requires
at least two remaining candidates.

The four functions copy no top-level input and mutate no row or nested value. They
catch no mapping, truthiness, iteration, copy, string, regex, normalization,
operation-family, source-cleanup, narrative-row, or numeric-extraction exception.
Their 81 old graph lines occupy 39 + 10 + 16 + 12 = 77 owner lines. Twelve calls
finish at 11 graph-external and one owner-local: 1/0, 1/0, 2/1, and 7/0 in the
order above. Retired graph-private references are zero. The `6d6c9c3` source diff
is `+100/-96`, tests are `+906/-6`, and all five files are `+1,006/-102`; six
tests moved full discovery from 1,656 to 1,662. Benchmark refresh was **NOT RUN**,
remote CI is unverified, and this relocation establishes no behavior, accuracy,
ranking, performance, total-code, executed-path, benchmark, schedule, or Phase 3
completion claim.

Prepared aggregate material inspection is also owned by
`financial_aggregate_projection.py`.

Public `growth_required_display_values(row, ordered_results,
evidence_items=None)` shallow-copies the calculation result, result-first answer
slots, and primary/current/prior slots. It resolves prior display before testing
current/prior material equality; equal material invokes the owner recovery helper
and replaces only a truthy recovered display. It then resolves current, prior,
and growth displays in that order, with calculation-result rendered value before
primary-slot display, removes blank values, and returns stable first-occurrence
deduplication. There is no operation-family gate in this projection.

Public `has_strong_growth_trace_for_answer_refresh(ordered_results)` scans in row
order. Operation family precedes period-conflict and every result/slot access.
Only a non-conflicting growth row with material primary/current/prior slots can
continue. For current then prior, it cleans the scalar and plural source-row ids
together and counts the slot only when normalized value is not `None` and at
least one cleaned id is not `task_output:`. Two direct operands return `True`;
otherwise scanning continues and eventually returns `False`.

Public `aggregate_lookup_primary_slots(rows)` iterates `rows or []`, skips a
non-dict before operation-family resolution, and accepts only lookup rows. It
shallow-copies calculation result, result-first answer slots, and primary slot,
then appends only a material primary-slot copy in stable order. Owner-private
`_ratio_result_numeric_value(row)` shallow-copies the same result/slot surfaces
and returns the first non-`None` coercion in exact precedence: result value,
primary normalized value, primary raw value, then row result value.

Public `retrieved_ratio_projection_conflicts_with_existing_complete_result(
ordered_results, task, *, result_value, context_evidence)` normalizes the task id
and metric label, derives a ratio signature, and scans prepared rows in stable
order. It filters non-dicts, non-ratios, incompatible task ids/signatures, non-ok
status, missing numeric result, and incomplete non-artifact results in that order.
The comparison tolerance is the greater of `5e-4` times the maximum absolute
value or one, and `1e-6`. An equal-within-tolerance row continues; the first
material mismatch returns the negation of the operand owner’s metric-surface
check over the supplied context evidence. No qualifying mismatch returns
`False`.

These five helpers do not mutate their row, slot, ordered-result, task, or
evidence inputs. They catch no mapping, truthiness, iteration, copy, string,
normalization, owner, numeric-coercion, signature, float, absolute-value, or
comparison exception. Their 135 old graph definition lines occupy public owner
spans 31 + 32 + 11 + 43 plus one 13-line owner-private span. Seventeen selected
calls finish at 16 graph-external and one owner-local; retired selected graph-
private references are zero. The `df7afc2` source diff is `+164/-157`, tests are
`+1,039/-44`, and all seven files are `+1,203/-201`; seven tests moved full
discovery from 1,662 to 1,669. Benchmark refresh was **NOT RUN**, remote CI is
unverified, and this relocation establishes no behavior, accuracy, ranking,
performance, total-code, executed-path, benchmark, schedule, or Phase 3
completion claim.

Prepared growth-numeric rendering is now also owned by
`financial_aggregate_projection.py`.

Public `compose_complete_growth_numeric_answer(row, ordered_results,
evidence_items=None)` first shallow-copies the calculation result and result-first
answer slots, then checks the aggregate operation family. Only a `growth_rate`
row continues. It shallow-copies primary/current/prior slots, requires material
primary content, resolves growth display from calculation result before primary
slot fallback, and resolves current then prior absolute displays. Equal current/
prior material invokes recovered-prior evidence; only a truthy recovered display
replaces the prior value and only its associated truthy period replaces the prior
period. A missing growth, current, or prior display returns `""` before label or
policy rendering.

Metric-label precedence is current slot, primary slot, then row. Period text is
removed with `CALCULATION_SLOT_POLICY`, and a blank cleaned label returns `""`.
Current period is current then primary; prior period is prior then the narrative-
policy default, unless recovered evidence supplied a period. Explicit direction
or direction hint wins. Otherwise normalized numeric sign is tried, and a
rendered-value leading minus is the final fallback. Only `TypeError` and
`ValueError` from that optional float conversion are caught. Direction words,
year suffixes, period/prior templates, topic particle, and the final sentence
template come from policy; the final result is normalized once.

The renderer mutates no row, slot, ordered-result, or evidence input. Mapping,
copy, truthiness, string, regex, owner, rendering, policy, formatting, and final
normalization exceptions propagate. Its former 100-line graph body is one 99-line
public owner function. Nine selected calls remain graph-external and owner-local
selected calls remain zero; retired graph-private references are zero. The
`5fb0267` source diff is `+117/-111`, tests are `+989/-38`, and all six files are
`+1,106/-149`; five tests moved full discovery from 1,669 to 1,674. The committed
source-only diff SHA-256 is
`a92591876808e7e4744d7deb5d9ff83d7282d61cfaaeb7bfcf852ea232a2687b`.
Benchmark refresh was **NOT RUN**, remote CI is unverified, and this relocation
establishes no behavior, accuracy, ranking, performance, total-code,
executed-path, benchmark, schedule, or Phase 3 completion claim.

Prepared growth trace inspection is now also owned by
`financial_aggregate_projection.py`.

Public `growth_answer_has_untraced_numeric_material(answer, ordered_results,
evidence_items=None)` normalizes the answer and returns `False` when blank. It
scans prepared rows in order, resolves operation family before period conflict,
and considers only nonconflicting growth rows. Complete-answer rendering precedes
required-display projection. A blank renderer or empty required-display set skips
the row. The whole normalized answer is tested first; only a negative result
splits the answer and checks sentences in stable order. The first whole-answer or
sentence conflict returns `True`.

Public `narrative_summary_conflicts_with_growth_trace(narrative_answer,
ordered_results, evidence_items=None)` has the same answer, operation, period,
renderer, and required-display gates. It reads the percent pattern before the row
scan. For every eligible row it builds evidence text in supplied item order from
claim, quote, raw-row, source-context, and selected metadata fields, then appends
evidence-visible numeric display candidates. The allowed surface is complete
answer, required values, evidence text, and evidence display text in that order.
It returns `True` only when at least one normalized percent token from the
narrative is absent from that allowed surface.

Public `growth_narrative_numeric_incompatible_with_trace(*,
narrative_answer, numeric_answer, ordered_results, evidence_items=None)` returns
`False` for a blank normalized narrative. It starts trace surfaces with the
numeric answer, then appends each eligible growth row's complete renderer and
required displays in row order. It extracts trace candidates before narrative
candidates. Empty candidates on either side return `False`; otherwise every
narrative candidate must have at least one equivalent trace candidate, and the
function returns the negation of that all/any relation.

The three predicates mutate no answer, row, ordered-result, evidence, metadata,
or nested input. They catch no mapping, copy, iteration, truthiness, string,
normalization, regex, policy, owner, extraction, or comparison exception. Their
130 old graph definition-span lines occupy public owner spans 28 + 56 + 43 =
127. All 19 selected calls remain graph-external and owner-local selected calls
remain zero; retired selected graph-private references are zero. The `c010a42`
source diff is `+158/-153`, tests are `+946/-80`, and all seven files are
`+1,104/-233`; six tests moved full discovery from 1,674 to 1,680. The committed
source-only diff SHA-256 is
`598f5e476cf0d8fef1c3767f2b6d33c82f1202702fd58e8c7d6e8c625fb7e348`.
Benchmark refresh was **NOT RUN**, remote CI is unverified, and this relocation
establishes no behavior, accuracy, ranking, performance, total-code,
executed-path, benchmark, schedule, or Phase 3 completion claim.

Dependency input-binding policy is owned by
`financial_dependency_projection.py`. Public
`dependency_slot_matches_input(binding, slot, *, sibling_row, state=None)`
normalizes binding and slot concepts first and rejects unequal nonblank concepts
before period, label, or segment access. Unequal nonblank periods resolve the
binding focus through `_operand_period_focus(...)`; only current/prior continue.
An optional report-scope year is converted with `int`, catching only
`TypeError`/`ValueError`. When a usable year and slot years exist, current
requires that year and prior requires year minus one; otherwise slot focus must
equal binding focus. Unequal nonblank labels pass only when the binding label is
contained in the slot or sibling label. A nonblank segment must occur
case-insensitively in the combined slot/sibling label.

Public `task_prefers_sibling_output_synthesis(state)` shallow-copies the active
subtask, gates on exact normalized difference/growth-rate/ratio/sum operations,
then scans input bindings in order and returns on the first task-output source
with a nonblank preferred task id. Public `task_output_input_bindings(state)`
uses the same binding and source-preference normalization but returns all
qualifying shallow binding copies in stable order. Nested values remain shared;
neither helper mutates state, active subtask, inputs, bindings, slot, sibling row,
or nested values. The three APIs catch no mapping/copy/iteration/truthiness/
string/normalization exception beyond the matcher's narrow optional-year
`TypeError`/`ValueError` boundary.

The former definition spans were 62 + 15 + 16 = 93 lines; public owner spans are
61 + 15 + 16 = 92 because two signatures remain one physical line after `self`
removal. A source audit before deletion corrected the prior plan by finding three
additional reconciliation callers. The final seven calls are direct imported
names at Try depth zero: four in calculation and three in reconciliation;
owner-local selected calls are zero, and the three old mixin attributes and
source/test refs are absent. The `7a20aab` source diff is `+111/-103`, tests are
`+1,164/-2`, and all five files are `+1,275/-105`. Six tests moved full discovery
from 1,680 to 1,686. The committed source-only diff SHA-256 is
`b840839073e6d7febe828d75004e15e3a45ae2e298a5ded6c303cc53738162e1`.
Focused 6/6, owner 69/69, affected semantic 895/895, import 19/19, audit 217,
full 1,686/1,686, pycompile/fresh-import, DAG/body/caller parity, and diff check
passed. Benchmark refresh was **NOT RUN**, remote CI is unverified, and the move
establishes no behavior, accuracy, ranking, performance, total-code,
executed-path, benchmark, schedule, or Phase 3 completion claim.

The reconciliation artifact-reference projections are now bounded task-artifact
owner contracts. Their public-three/private-one, external-four/local-one behavior
and retained graph boundary are specified below. The sole next priority is
governed by [Project Status Next Work](../overview/project_status.md#next-work).

Aggregate narrative-row, numeric-gap, and lookup-answer policy is also owned by
`financial_aggregate_projection.py`. Public `row_is_narrative_summary(row)`
normalizes and lowercases the row metric family before resolving the aggregate
operation family, then returns the exact OR of either value being
`narrative_summary`. It neither copies the row nor catches access, string,
normalization, or operation-family exceptions.

Public `safe_partial_answer_for_numeric_gap(ordered_results)` scans rows in
source order, skips narrative rows, resolves status from the row before its
calculation result, and invokes material-gap feedback only for an `ok` row. It
normalizes the row answer first; only a blank answer copies the calculation
result and falls back from formatted result to rendered value. Nonblank answers
are stably deduplicated and space-joined. It does not mutate input or catch
iteration, mapping, truthiness, predicate, copy, normalization, or string
exceptions.

Public `compose_lookup_list_numeric_answer(ordered_results)` skips narrative
rows but returns `""` immediately when any remaining row is not exact `lookup`
or `single_value`. Every eligible row increments the lookup-row count before
status and material-gap filtering. An `ok`, gap-free row delegates to owner-
private `_lookup_numeric_item_answer`; retained items are stably deduplicated,
and both the eligible-row count and item count must be at least two. Only then
are the configured separator and answer template read and the formatted answer
normalized.

`_lookup_numeric_item_answer(...)` shallow-copies calculation result, result-
first answer slots, and primary slot. Its optional primary-material gate precedes
surface access. Value precedence is primary rendered value, result formatted
result, result rendered value, then row answer. Only `TypeError` and `ValueError`
from primary normalized-value conversion are caught. A converted nonnegative
value strips one leading parenthesis and its first closing parenthesis from the
display. Label precedence is primary label before row metric label; blank label
or value returns `""`. The optional numeric gate calls the numeric-surface owner
before the configured item template is read and formatted.

Public `append_uncovered_lookup_numeric_items(answer, ordered_results)` first
normalizes the answer and returns it when blank. It then requires at least one
dictionary row whose aggregate operation is exact `ratio`, `sum`, `difference`,
or `growth_rate`. Ratio component slots are shallow-copied in row, group, and
slot order. The owner-local conflict predicate copies the lookup primary slot,
requires matching nonblank labels, tolerates unequal units when either unit is
blank, and treats values as conflicting only when their difference exceeds
`max(abs(component), abs(lookup), 1.0) * 5e-4`. Only numeric-conversion
`TypeError` and `ValueError` are suppressed.

The append scan then keeps only dictionary, non-narrative, exact lookup/single-
value, `ok`, gap-free, nonconflicting rows. It requires a material primary slot
and numeric item, skips items already covered by numeric-answer comparison, and
also skips a label-overlapping answer that already has a numeric surface.
Remaining items are stably deduplicated, stripped of terminal periods, joined as
period-delimited prefix sentences, and prepended to the original normalized
answer. Inputs and nested values remain unmodified. Apart from the two explicit
numeric-conversion catches, access, copy, truthiness, iteration, predicate,
normalization, numeric-surface, matching, policy, and formatting exceptions
propagate.

These 183 old graph definition-span lines now form four public APIs plus the one
owner-private formatter. Of 28 calls, 23 remain external and five are owner-
local: row predicate 17/3, safe partial 4/0, compose 1/0, append 1/0, and private
lookup 0/2. Retired graph-private references are zero. The graph retains all
external caller gates and argument/adoption/exception order, query/evidence
preparation, answer composition and feedback, mutable state/evidence, artifacts
and ledger, promotion, sync/rebuild, callbacks, and final sequencing. This is an
ownership relocation only; it establishes no behavior, accuracy, ranking,
performance, total-code, executed-path, benchmark, or Phase 3 completion claim.

Narrative-answer validation is public in `financial_answer_projection.py`.
`query_requests_explanatory_context(query)` stringifies, normalizes, and
lowercases the query, and returns `False` for blank text before policy access.
Otherwise it fully materializes the configured explanatory markers as strings
and performs stable lazy containment. `sentence_has_growth_explanatory_signal`
normalizes the sentence and returns `False` before policy access when blank. It
then builds normalized direction words, materializes narrative, impact, and
explanatory markers in that order, excludes blank markers and exact direction
words, and performs stable lazy containment.

`answer_looks_truncated(answer)` normalizes the stringified answer and treats a
blank as truncated. Its terminal-language regex is checked before the generic
terminal-punctuation regex; either match returns `False`, and only the remaining
path returns `True`. `answer_covers_narrative_context(answer, context)` normalizes
and lowercases the answer before normalizing context. Blank context and exact
normalized context containment return `True` before sentence splitting. Each
remaining sentence is lowercased and exact containment skips token work. Tokens
come from `re.findall(r"[\w()]+", ..., re.UNICODE)`, require length at least three,
then exclude numeric full matches; only retained tokens are lowercased. A sentence
with no retained tokens fails; otherwise coverage below the exact `0.75`
threshold fails.

`growth_uses_source_stated_result(row)` shallow-copies calculation result,
result-first answer slots, and current slot. A truthy copied derived-metric flag
wins, followed by normalized current-slot stated change. Only the remaining path
list-materializes row-first calculation operands and lazily accepts a dictionary
whose `matched_operand_role` precedes `role`, is exactly `current_period`, and has
a normalized stated-change value. Input rows and nested values remain unmodified.

`growth_sentence_has_untraced_material_numeric(...)` normalizes the sentence and
returns `False` when blank. It constructs evidence text in item order from claim,
quote, raw-row, source-context, then copied metadata table surfaces; calls the
numeric-display owner with `evidence_items or []` and that text; and builds the
allowed surface in complete-answer, required-value, evidence, display order. A
blank allowed surface returns `False` before policy access. Configured
percent matches are checked first and the first nonblank token absent from the
allowed surface returns `True`. Only the remaining path snapshots render policy,
materializes normalized KRW display units, and applies the same first-unallowed
rule to each unit-specific numeric match.

`growth_answer_has_untraced_numeric_sentence(...)` normalizes answer, complete
answer, and the complete-plus-required allowed surface before its blank gate. It
splits the answer in source order, skips blank sentences and sentences already in
the complete answer, and requires a lazy match to at least one nonblank required
value. It then materializes numeric tokens with the existing percent-capable
pattern and returns at the first token absent from the allowed surface. Otherwise
it returns `False`.

These seven APIs catch no truthiness, string, normalization, policy, mapping,
copy, iteration, split, regex, match, containment, numeric-display, or formatting
exception. The graph retains all 36 direct public placements with the existing
arguments, polarity, gates, adoption, and exception stop: respectively 14, one,
one, nine, one, seven, and three calls in the API order above. Query/evidence
preparation, answer composition and refresh, LLM work, mutable state/evidence,
task/artifact ledger, promotion, sync/rebuild, callbacks, and final orchestration
remain graph-owned. The move makes no behavior, accuracy, ranking, performance,
total-code, executed-path, benchmark, or Phase 3 completion claim.

Ratio presentation policy is public in
`financial_graph_calculation_rendering.py`.
`infer_concept_ratio_result_unit(query, metric_label, operation_family)`
normalizes the operation family first and returns `""` for anything other than
exact `ratio` before query, label, or policy access. The ratio path normalizes the
combined query/label surface, snapshots `CONCEPT_RATIO_RESULT_UNIT_POLICY`, and
materializes multiplier markers before percent markers. A multiplier marker with
no percent marker selects the configured multiplier unit; every other ratio path
selects the configured percent unit.

`ratio_query_requests_absolute_magnitude(query)` normalizes and lowercases the
query, then fully materializes the normalized, lowercased, nonblank marker tuple
even for a blank query. Its return then tests query text, marker-tuple truthiness,
and ordered containment with the existing short-circuiting.
`ratio_result_projection(...)` calls the unit owner first, applies the percent
fallback, then reads the multiplier unit. It divides once into either raw
multiplier/`COUNT` or percent-scaled/`PERCENT` output, applies absolute magnitude
only to a negative result with matching query intent, and builds result value,
unit, normalized unit, then rendered value in that order. Zero division and all
normalization, policy, iteration, containment, formatting, and other exceptions
remain uncaught. Two calls are owner-local; eight remain external: six graph, one
graph-helper, and one planning call with their existing gates and adoption.

Ratio component readiness is public in `financial_answer_slots.py`.
`ratio_component_consolidation_scope(calculation_result, operands=None)` copies
answer slots, scans every component group before operands in stable order, and
deduplicates only exact `consolidated`/`separate` scopes. It returns the sole
distinct scope or `""`. `ratio_components_collapse_to_same_slot(...)` copies
answer slots and the group map, then list-materializes and shallow-copies strict
numerator dictionaries before denominator dictionaries. Each material slot's
identity resolves source ids and six-place/fallback numeric text before evaluating
the tuple fields label, raw value, raw unit, numeric text, and source ids. Only
numeric conversion `TypeError`/`ValueError` falls back to normalized text. Equal complete identity
sets collapse; otherwise a shared nonblank-source identity excluding label also
collapses.

`ratio_components_are_complete(...)` prepares the same fresh numerator and
denominator rows before invoking collapse owner-locally. A collapse returns
`False` before value probes; otherwise numerator material is tested before
denominator material, with rendered, raw, then normalized value precedence and
stable lazy `any(...)`. Inputs remain unmodified and untouched nested aliases are
shared. Other copy, mapping, truthiness, list, iteration, predicate, string,
normalization, and access exceptions propagate. One readiness call is owner-local
and 15 graph calls retain their original positions, polarity, adoption, and stop.

Ratio scale policy is public in `financial_numeric_surface.py`.
`ratio_components_have_suspicious_scale(calculation_result)` shallow-copies the
answer-slot and component-role maps, then scans roles and entries in stable order.
For each entry it reads normalized/lower raw unit and stripped raw value before the
unit gate, requires exact KRW display units and the existing full-match numeric
regex, then counts regex digits and returns at the first count of at least eight.
`ratio_result_has_suspicious_krw_scale(...)` preserves operation-family,
non-`None` result, percent-unit, render-policy snapshot, and source-KRW gates in
that order. It scans all operands, reading normalized unit before value only for a
KRW row, requires two non-`None` KRW values, then converts threshold before the
absolute result. Only conversion `TypeError`/`ValueError` returns `False`; other
exceptions propagate. The final comparison requires a positive threshold and a
strictly greater result. All three graph calls retain their exact arguments,
positive polarity, adoption, and render/verify exception boundaries.

These eight public APIs replace only the selected ratio policy bodies. Graph and
helper consumers retain query/evidence preparation, dependency lookup, compact
answer orchestration, sibling-table alignment, state/evidence, task/artifact
ledger, promotion, sync/rebuild, callbacks, and final sequencing. The move makes
no behavior, accuracy, ranking, performance, total-code, executed-path,
benchmark, or Phase 3 completion claim.

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

Aggregate projection row, answer-sentence, and rendered-value selection are now
three additional plain `financial_aggregate_projection.py` owner seams. Public
`select_aggregate_projection_row_for_task(task_id, ordered_results,
aggregate_projection)` normalizes the target id first and returns `{}` before any
other input access when it is blank. It shallow-copies calculation result and
answer slots, then scans calculation-result subtask rows, answer-slot subtask
rows, and ordered results in that precedence. Each group is materialized only
when reached; non-dictionaries are skipped, the first normalized exact task-id
match wins, and a match returns a fresh shallow row with nested aliases retained.

Public `select_aggregate_projection_answer_sentence(final_answer, row)` normalizes
the answer and returns before row access when blank. It shallow-copies calculation
result, answer slots, and primary slot, then reads metric label, row label, and
primary-slot label in order. Each label is normalized, lowercased, optionally
period-prefix-stripped, and stably deduped. The aggregate operation-family owner
is resolved before sentence splitting; a falsy split falls back to the normalized
whole answer.

Each numeric sentence receives a lexicographic score of label match, ratio/growth
percent presence, difference/sum numeric-candidate count, numeric conflict, and
normalized length. Label scoring preserves exact substring precedence over token
overlap and operand-text matching. `max` keeps the first stable tie. The selected
sentence is scored again and is returned only when label, percent, or arithmetic
score is nonzero; conflict or length alone cannot make it eligible. Repeated
numeric extraction/conflict calls and their exception order remain observable.

Public `aggregate_projection_rendered_value(answer_sentence, operation_family)`
normalizes the sentence and returns before family work when blank. Ratio and
growth families use the first signed percent/percent-point regex match and do not
invoke generic numeric extraction. Other families extract candidates once and
return the normalized text of the last candidate, or `""` when none exists. These
selectors do not mutate inputs and catch no mapping, copy, string, regex,
extraction, scoring, iteration, or other exception.

The three ledger-path calls (two row selections and one answer-sentence
selection) preserve task-id preparation, replacement fallback, conflict checks,
payload copy, supersession, and all ledger mutation. The three arithmetic-surface
synchronization calls (two answer-sentence selections and one rendered-value
selection) preserve candidate iteration, conflict and coverage gates,
operation-family resolution, prepared surface-sync input, lookup-slot work,
row-map propagation, projection rebuild, and final orchestration. Exceptions stop
later caller work. These seams do not own nested promotion, rebuild policy,
aggregate precedence, mutable state/evidence, artifact/ledger synchronization,
callbacks, or final projection.

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

Aggregate-subtask numeric-answer conflict and direct-source-reference detection
are plain, state-free `financial_aggregate_projection.py` owner seams through
`subtask_numeric_answers_conflict(candidate_row, current_row)` and
`subtask_row_has_direct_source_refs(row)`. The conflict owner completely resolves
the candidate answer before accessing the current row. Each side evaluates
`answer`, then `calculation_result.formatted_result`, then a repeated
`calculation_result` access for `rendered_value`, and only then stringifies and
normalizes the selected surface. Both answers are resolved before candidate and
current numeric extraction. Both extractors run before the candidate-first,
current-second empty-result gate; either empty side returns `False`.

For nonempty surfaces, conflict remains the asymmetric candidate-major,
current-minor `not all(any(...))`: every candidate number must match at least one
current number for no conflict, an extra unmatched current number alone does not
create conflict, and both nested iterations retain their stable lazy order. The
owner does not pre-copy or mutate either row and catches no mapping, truthiness,
string, normalization, extraction, equivalence, iteration, or other exception.

The direct-source owner first evaluates and shallow-copies
`row.calculation_result`. It then passes a fresh four-element list to the existing
source-id cleaner in exact order: row `source_row_ids`, copied-result
`source_row_ids`, row `selected_claim_ids`, and copied-result
`source_evidence_ids`. The final lazy `any` skips falsy ids and ids beginning
case-sensitively with `task_output:`, and returns on the first remaining id. The
input row and nested values remain unmodified; row/result access, copy, cleaner,
iteration, truthiness, prefix, and other exceptions remain uncaught.

The graph retains all four consumers and their existing gates and short-circuit
order. Aggregate task-ledger finalization calls numeric conflict before the
answer-preservation fallback in the existing `or` expression. Projection-row
sentence scoring calls it after numeric, label, percent, and arithmetic-score
preparation; the arithmetic-surface synchronizer calls it after row/sentence
eligibility and before family-specific coverage and single-number gates. Nested
promotion keeps status and material checks before direct-source detection, then
family equality, numeric conflict, and the two growth sign ranks. Ledger mutation,
sentence selection, surface synchronization, full nested promotion/ranking,
source selection and provenance policy, state/evidence, artifact/ledger, and final
orchestration remain graph-owned. This pair claims only predicate ownership and
old-body deletion, not behavior or policy improvement, performance, total-code or
executed-path reduction, broad private-surface cleanup, or Phase 3 completion.

Compact aggregate-synthesis prompt-row projection is a plain, state-free
`financial_aggregate_projection.py` owner seam. It copies the prepared aggregate
calculation result before answer slots, then selects projected rows in calculation-
result, answer-slot, and ordered-result fallback order. Aggregate operands are
list-materialized and shallow-copied before the shared material predicate and task-
id access. Fixed compact operand fields retain their insertion and repeated-getter
order, task grouping and operand order remain stable, and projected rows retain
strict dictionary-only admission.

Each retained row preserves row-field, answer-slot copy, calculation-result copy,
compact-result, and prepared operand-attachment order. The outer list, compact rows,
row-level answer slots, compact results, compact operands, and per-task grouping
lists are fresh; retained nested values, including result answer slots, keep their
aliases. Inputs remain unmodified and the owner catches no mapping, truthiness,
copy, conversion, string, predicate, iteration, equality, or other exception.

The shared public `financial_runtime_trace.py` material predicate preserves status
normalization and the `missing` return, raw-unit before lazy unit fallback,
normalized-unit normalization, raw value before lazy value/rendered/display
fallbacks, digit counting, the unknown-or-empty unit plus no-raw-unit and fewer-
than-four-digits gate, and only then normalized-value access with raw-value
truthiness fallback. It adds no catch or mutation. Runtime trace still prepares a
local row and source ids before this predicate and retains key construction,
dedupe, and append afterward. The graph keeps the LLM gate, model/structured-LLM
and prompt construction, post-period-realignment inputs, JSON/debug/prompt and LLM
invocation, enclosing catch/fallback, composition, state, and evidence
orchestration. This boundary claims only compact synthesis-input projection and
shared public material-predicate ownership, not LLM/template/answer policy, token
or prompt-size improvement, total-code or executed-path reduction, performance,
broad private-surface cleanup, or Phase 3 completion.

Prepared calculation-operand slot overlay is a second plain, state-free
`financial_runtime_trace.py` owner seam through
`overlay_calculation_operands_from_slots(trace, slot_by_role, *, normalize_role=False)`.
It evaluates `(trace or {}).get("calculation_operands") or []` and materializes that
operand sequence before processing rows. It always returns a fresh list and shallow-
copies every operand in stable order. Per row it resolves the lookup role through
truthy `matched_operand_role`, lazy `role`, and `""`, then stringifies it. The
`normalize_role` flag is tested for every row; when true, whitespace normalization
and lowercasing affect only the lookup key.

The owner performs one `slot_by_role.get(role)` per copied row. A missing or falsy
slot preserves the otherwise-fresh row. A truthy slot overwrites `raw_value`,
`raw_unit`, `normalized_value`, `normalized_unit`, `source_row_id`,
`source_row_ids`, and `source_anchor` in that exact order, including absent-key
`None` values. Unrelated nested values and adopted slot values retain their exact
identities. The trace, operand rows, slot map, and slots remain unmodified. The
owner catches no truthiness, access, list materialization, iteration, copy, string,
normalization, lowercasing, getter, update, or other exception and does not dedupe,
pre-copy the slot map, or cache role resolution across rows.

The collapsed-ratio repair caller still builds its numerator/denominator role map,
passes the exact original trace with default role handling, and adopts the owner
result unconditionally before assigning the repaired calculation result. The
single-period comparison caller still builds current/prior plus minuend/subtrahend
aliases, passes `normalize_role=True`, and adopts the owner result only when it is
truthy. Graph retains all evidence, applicability, ranking, formula, slot/result
repair, realignment, call-placement/adoption, state, artifact, and finalization
policy. This seam claims only prepared role-slot-to-calculation-operand overlay
ownership plus old-body deletion, not either repair workflow, behavior or
performance improvement, total-code or executed-path reduction, broad private-
surface cleanup, or Phase 3 completion.

Generic numeric-answer coverage and outside-reference comparison are plain,
state-free `financial_numeric_surface.py` owner seams through
`answer_covers_numeric_answer(answer, numeric_answer)` and
`answer_has_numeric_material_outside_reference(answer, reference_answer)`. Both
owners evaluate and extract the answer first and the second input afterward. Each
input preserves truthiness, `str`, whitespace-normalization, and numeric-surface-
extraction order; both extractions complete before candidate-list truthiness is
tested.

Coverage tests the numeric-answer candidate list before the answer list. An empty
numeric list returns `True` without testing answer-list truthiness; otherwise an
empty answer list returns `False`. Its nonempty comparison remains numeric-major in
the outer iteration and answer-minor inside: every numeric-answer candidate must match some
answer candidate through stable lazy `all(any(...))`. Outside-reference comparison
tests answer-list truthiness before reference-list truthiness, returns `False` when
either is empty, and retains answer-major, reference-minor
`any(not any(...))`, stopping on the first answer candidate unmatched by every
reference candidate. Equivalence argument order and nested short-circuit order are
unchanged. Neither owner copies or mutates inputs, and neither catches truthiness,
string, normalization, extraction, list-truthiness, iteration, equivalence, or
other exceptions.

The three `financial_graph.py` and nine calculation-graph calls remain at their
existing positions. The graph modules retain all prepared answer/reference
targets; projection, preservation, scoring, arithmetic-surface synchronization,
recovered-ratio, stale-repair, and initial-state gates; result polarity and later
adoption/mutation; and state, evidence, artifact/ledger, and final orchestration.
This seam claims only generic numeric coverage and outside-reference comparison
ownership plus old-body deletion, not public projection, preservation, scoring,
synchronization, stale or initial-state policy, evidence support, behavior
improvement, performance, total-code or executed-path reduction, broad private-
surface cleanup, or Phase 3 completion.

Numeric conflict and evidence/text candidate support are separate plain,
state-free `financial_numeric_surface.py` owner seams. Public
`numeric_surface_conflicts_with_reference(answer, reference)` normalizes and
extracts the answer before the reference. It returns truthy only when both lists
are nonempty and some answer candidate is unmatched by every reference candidate,
preserving answer-major/reference-minor lazy equivalence order. Its outer
`bool(answer_candidates and reference_candidates and ...)` also preserves the
original repeated truth tests: a decisive empty answer container is tested twice;
with a nonempty answer, a decisive empty reference container is tested twice after
the answer container is tested once. This is intentionally distinct from the
single-gate outside-reference predicate.

Public `evidence_supports_numeric_candidates(evidence, answer_candidates)` first
constructs the owner-standard numeric-support evidence text, extracts evidence
candidates, and returns `False` before answer-candidate iteration when none exist.
Public `text_supports_numeric_candidates(text, answer_candidates)` applies the
same contract to direct text. Both support predicates retain answer-major then
support-candidate-minor stable `any(...)` evaluation. None of the three functions
copies or mutates inputs beyond their existing local support-text construction,
and none catches normalization, extraction, mapping, iteration, equivalence, or
other exceptions.

The graph retains all seven calls and their prepared inputs: answer/evidence
candidate construction, evidence and quote gates, selected/unselected filtering,
aggregate conflict/stale-answer policy, call polarity, later projection, state,
artifact/ledger, and final orchestration. Earlier gates remain owner-zero and an
owner exception stops later caller work. These seams claim only generic numeric
conflict and support-predicate ownership plus old-body deletion—not evidence
selection, answer policy, behavior or accuracy improvement, performance, total-
code or executed-path reduction, public-surface change, or Phase 3 completion.

Table numeric-support text and evidence promotion are plain, state-free
`financial_numeric_surface.py` owner seams. The owner-private support helper first
copies evidence metadata, then reads and splits the table-value-label surface.
Blank lines are normalized once and discarded; retained lines are normalized once
for the gate and again for the stored line. An empty retained-line set returns
before final-answer, render/unit-policy, answer-candidate, or header access.

The nonempty path normalizes the final-answer surface, builds the render-scale and
percent-unit term set, length-sorts and escapes those terms, and processes table
lines in stable order. Numeric stripping precedes unit stripping, punctuation
stripping, compact label normalization, label-length and answer-containment gates,
and numeric extraction. Equivalence remains answer-candidate-major and line-
candidate-minor. The helper retains the first four supporting lines and stops
before accessing a fifth. No support returns before header access; a supported
result reads `table_header_context` before `table_context` and preserves the
existing normalized join behavior.

The public `promote_table_numeric_support_evidence(...)` invokes the private helper
before copying evidence. No support
returns the exact supplied evidence identity. A supported result creates a fresh
top-level evidence dictionary, reads claim before quote span, writes their promoted
surfaces in that order, then shallow-copies metadata and adds
`final_answer_table_numeric_support`. Other nested values retain their identities,
inputs remain unmodified, and neither helper catches mapping, copy, truthiness,
string, split, normalization, policy, set/sort, regex, extraction, equivalence,
iteration, or other exceptions.

The graph retains answer-candidate, evidence-selection, and support gates; local
evidence and pre-owner metadata copies; evidence-id handling; and the retrieved-
narrative skip. It calls the public owner once per non-narrative row with the exact
local evidence dictionary, raw final answer, and shared candidate list, then adopts
the returned row before later selection/filtering. The pre-owner metadata local
remains authoritative for its existing later gates. This seam owns only prepared
table-support text and evidence promotion, not evidence selection or faithfulness
policy, append-evidence behavior, state, artifact/ledger, final orchestration,
performance, total-code or executed-path reduction, or Phase 3 completion.

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

Source-task display compatibility for a prepared answer slot is a plain,
state-free `financial_answer_slots.py` owner seam through
`source_task_display_compatible_with_slot(slot, source_display)`. The owner first
applies source-display truthiness, stringification, and normalization; blank input
returns `False` before slot access. It resolves the slot display from
`rendered_value` before `raw_value`, and normalized exact equality returns `True`.
A normalized `source_row_id` beginning with `task_output:` also returns `True`.
It then normalizes `raw_unit`; blank units and units already contained in the
source display return `True` before normalized-unit or policy access.

Only the remaining path normalizes and uppercases `normalized_unit`, then
stringifies and uppercases configured `krw_normalized_unit`. When they match, the
configured `krw_display_units` tuple is fully materialized in its existing
filter-then-storage order, so each retained item is stringified twice and each
blank item once before containment begins. A configured KRW display unit found in
the source display returns `False`; all other paths return `True`. The owner does
not copy or mutate inputs and catches no mapping, truthiness, string, iteration,
containment, normalization, policy, or other exception.

Prepared aggregate growth display/material projection is now a state-free
`financial_aggregate_projection.py` owner seam. Owner-private
`_slot_display_from_source_task(slot, ordered_results)` resolves normalized
`source_task_id` before a `task_output:` source-row fallback, defaults the source
slot to `primary_value`, scans rows in stable order, and shallow-copies the
calculation-result, answer-slot map, and selected source slot before the material
gate. The first material slot returns normalized `rendered_value` before
`raw_value`; absent ids, rows, or material return a blank string. Top-level inputs
remain unmodified and copied nested values retain identity.

Public `growth_slot_display_value(slot, ordered_results)` obtains that source
display first. A truthy display calls
`source_task_display_compatible_with_slot(...)` once with the exact slot and
prepared string; owner `True` adopts it. Blank or incompatible source display
uses normalized `rendered_value` before `raw_value`. Public
`growth_slots_share_material(current_slot, prior_slot, ordered_results)` calls
the display owner current-first and prior-second. Equal truthy displays return
`True` before normalized-value access; otherwise missing normalized values return
`False`, and exact `float` equality decides the result. Only `TypeError` and
`ValueError` from numeric coercion become `False`; display, mapping, truthiness,
string, normalization, and other exceptions propagate.

Public `recover_growth_prior_material_from_evidence(...)` is owner-zero for empty
evidence or a current slot without a four-digit period/label year. It normalizes
the current raw value and the prior-then-current raw-unit fallback, builds the
same unit-aware number pattern, scans evidence and split sentences in stable
order, requires an earlier year, skips the current value, and returns the first
fresh `{display, period, raw_value, source_quote}` dictionary. A configured year
suffix is applied only on success. The existing blank-unit wildcard behavior,
including its first regex match, is preserved exactly. Inputs and evidence items
are not mutated; mapping, string, regex, sentence splitting, policy, and other
exceptions remain uncaught.

The graph calls public `growth_required_display_values(...)` at the retained
inspection sites and keeps complete and narrative growth answer construction,
duplicate-prior operand recovery, evidence choice, adoption, state, artifacts,
and final orchestration. The original display/material seam still has 15 direct
graph calls and three owner-local calls.
This seam claims display/material ownership only, not growth-calculation or
answer-composition ownership, numeric/render-policy improvement, behavior or
performance improvement, total-code or executed-path reduction, broad private-
surface cleanup, or Phase 3 completion.

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

Prepared reconciliation artifact candidate and evidence-reference projection is
also a plain, read-only `financial_task_artifacts.py` owner seam. Owner-private
`_artifact_text_matches_operand_surface(text, operand)` normalizes the supplied
text and returns `False` for blank input before operand access. It calls the
shared operand matcher first; only a miss compacts whitespace in the text and
each stable operand needle, skips blank needles, and accepts either containment
direction. It catches no truthiness, string, normalization, regex, needle, or
operand-matcher exception.

Public `reconciliation_artifact_candidate_ids_for_operand(state, operand=...)`
scans a copied artifact list in stable order, copies each artifact, accepts kinds
containing `reconciliation_result`, and copies payload, result, and dictionary
match rows. It tests label, concept, and role surfaces in order through the
owner-private matcher and stably deduplicates copied match candidate ids. Once an
artifact has any matching operand surface, its artifact evidence refs are not a
fallback even when the matching row has no candidate id; otherwise its evidence
refs are appended. Public `reconciliation_artifact_candidate_ids(state)` keeps
top-level reconciliation `evidence_refs` then `source_evidence_ids` before each
eligible artifact's refs and payload-result refs, preserving stable first-seen
dedupe.

Public `reconciliation_evidence_refs(result)` accepts only strict dictionary
matched-operand rows and reads candidate, source-row, source-evidence, evidence,
and row id plural/singular families in their existing order. It recursively
flattens list, tuple, and set containers, stringifies and strips leaf values,
filters blank and case-insensitive `none`/`null`/`nan`, and preserves first-seen
order. The selected owners mutate no supplied state, artifact list, payload,
result, match row, operand, id container, or nested item. Mapping, copy,
truthiness, conversion, iteration, regex, hashing, and access exceptions remain
uncaught.

The graph retains structured-candidate and cell selection, candidate-map
construction, evidence construction, list adoption, reconciliation state
projection, artifact creation/update and ledger mutation, reranking/LLM work,
reflection/retry planning, mutable state/evidence, and final sequencing. The four
public calls remain at the original extraction/reconciliation placements and the
text match is owner-local. An owner exception still stops downstream adoption and
state work. Commit `c825ab7` moves only these deterministic bodies: source is
`+153/-138`, tests are `+1,455/-4`, full discovery is 1,692/1,692, and the source
diff SHA-256 is
`65819999639a808bb95ec29ddf6547751fddaff3eed4e3af321210d367a43b55`.
The pre-move audit also established that reconciliation's `_operand_text_match`
import becomes dead and must be removed. The move establishes no behavior,
accuracy, ranking, performance, total-code, executed-path, benchmark, ledger, or
Phase 3 completion claim.

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
`financial_reflection_projection.py` now owns the bounded request/plan projection
contract. Public `normalise_reflection_plan_record(...)` shallow-copies the
planner record, strips missing-info items, repeatedly normalizes subqueries and
preferred sections, normalizes and bounds retry strategy against
`ALLOWED_REFLECTION_RETRY_STRATEGIES`, and fills missing lists from caller
fallbacks. If no normalized subquery survives, it replaces the whole projected
record with a fresh shallow copy of the heuristic fallback and installs the
existing explanation. Nested fallback values retain their current shallow-copy
identity. Mapping, truthiness, iteration, string, and normalization exceptions
are not caught by the owner.

Owner-private `_reflection_runtime_trace_summary(...)` copies the top-level
state before resolving the runtime trace with `allow_legacy_top_level=False`,
then copies operands, plan, and result surfaces and projects only their count,
status, operation/mode fallback, and explanation. Owner-private
`_reflection_evidence_summary(...)` preserves the current evidence-items,
retrieved-docs, seed-docs access order and projects their list counts plus raw
string status. Public `build_reflection_request(...)` shallow-copies the active
subtask, converts reflection count, strips caller-supplied missing info, adopts
both summaries, and clamps the existing one-retry budget at zero. None of these
functions mutates caller state or nested values, and resolver, copy, access,
conversion, iteration, string, and normalizer exceptions preserve their former
scope.

The two public calls remain at their original `_plan_reflection_retry(...)`
positions. Request construction runs before the structured-planner `try`, so an
owner exception propagates and stops heuristic/prompt/model work. Plan
normalization remains inside the existing structured-planner catch boundary, so
an owner exception follows the current heuristic fallback. The two summary calls
are owner-local. The former definition spans were 35 + 15 + 7 + 22 = 79 lines;
the public-two/private-two owner spans are 35 + 15 + 7 + 21 = 78, with two
graph-external and two owner-local calls. Commit `c47ac50` has source
`+110/-99`, tests `+1,199/-14`, and whole-commit `+1,309/-113`; its source diff
SHA-256 is `5cf8c743dd07a22ac9281711638f62588ecd771d708434e1cbcf0a70144cc56a`.
Focused 6/6, reflection contract 18/18, affected semantic 800/800, import 19/19,
union 819/819, audit 217, and full discovery 1,698/1,698 passed. Benchmark refresh
was **NOT RUN**, remote CI is unverified, and the move does not activate
reflection, increase retry budget, change final acceptance, establish promotion
evidence, or prove behavior, accuracy, ranking, performance, total-code,
executed-path, benchmark, schedule, ledger, or Phase 3 completion.

`financial_dependency_projection.py` now owns sibling-surface and resolved-
reconciliation preparation. Public
`active_subtask_with_sibling_lookup_surfaces(active_subtask, calc_subtasks)`
shallow-copies the active subtask, normalizes existing surfaces, scans copied
calculation subtasks in stable order, skips the active id only when nonblank,
accepts the exact lookup/single-value operation or concept metric families,
applies the configured period-prefix regex to metric and operand labels, appends
stripped aliases, and publishes stable first-occurrence dedupe. Public
`dependency_resolved_reconciliation_result(dependency_bindings)` scans bindings
in order and returns a fresh ready result with normalized label/role/concept,
task-output candidate ids, matched flags, fixed reason/notes, and empty missing/
retry fields. Neither catches mapping, iteration, truthiness, string, regex,
policy, or normalization exceptions or mutates inputs.

Commit `5a0c3e0` moved the former 48 + 28 = 76 definition-span lines to public
47 + 27 = 74 owner lines. All five direct calls remain graph-external and at Try
depth zero. Source is `+93/-85`, tests are `+1,228/-28`, and the whole commit is
`+1,321/-113`; the source diff SHA-256 is
`c9e931e818cfc7661ccb05bc162078a4db83120aab44f6dd9331dac51fa7a501`.
Focused 6/6, dependency owner 75/75, affected semantic 823/823, import 19/19,
union 842/842, audit 217, and full discovery 1,704/1,704 passed. Benchmark refresh
was **NOT RUN**, remote CI is unverified, and the move proves no behavior,
accuracy, ranking, performance, total-code, executed-path, benchmark, schedule,
ledger, or Phase 3 completion. All four callers, dependency-state lookup,
candidate/cell and evidence construction, ontology completion, LLM reranking,
retry selection, artifact and ledger mutation, mutable state/evidence,
promotion, sync/rebuild, and final sequencing remain graph-owned.

`financial_task_artifacts.py` now owns prepared runtime-evidence merge and ratio
task-artifact row projection. Public
`evidence_items_with_runtime(evidence_items, state)` keeps the supplied evidence
items and their identities in order, collects existing nonblank ids, then scans
`runtime_evidence` in order. It skips non-dictionaries and duplicate nonblank ids
and appends fresh top-level copies while preserving nested identities. Public
`ratio_result_rows_from_task_artifacts(state, task)` normalizes the task id,
scans copied artifact records in order, admits only matching calculation-result
artifacts with a nonempty result payload, preserves formatted/rendered/summary,
result/artifact status, metric label, and result/evidence-ref fallback order, and
returns fresh row and calculation-result dictionaries. Neither catches mapping,
iteration, truthiness, string, normalization, or copy exceptions or mutates
inputs.

Commit `8d627a6` moved the former 21 + 43 = 64 definition-span lines to public
20 + 42 = 62 owner lines. All four direct calls remain graph-external and at Try
depth zero. Source is `+74/-70`, tests are `+911/-8`, and the whole commit is
`+985/-78`; the source diff SHA-256 is
`07ffa0657a4e7762442aa3d79d88dd06084a0c0319c0eb7fce8185902061018e`.
Focused 6/6, task-artifact owner 15/15, affected semantic 832/832, import 19/19,
union 851/851, audit 217, and full discovery 1,710/1,710 passed. Benchmark refresh
was **NOT RUN**, remote CI is unverified, and the move proves no behavior,
accuracy, ranking, performance, total-code, executed-path, benchmark, schedule,
ledger, or Phase 3 completion. Both operand-extraction placements, preferred
ratio-artifact conflict selection, retrieved-ratio arithmetic/projection, mutable
state/evidence, artifact/ledger mutation, promotion, sync/rebuild, and final
sequencing remain graph-owned. The adjacent preferred selector remains excluded
because moving it would require a task-artifact -> aggregate-projection import
against the existing aggregate-projection -> runtime-trace -> task-artifact path.

`financial_aggregate_projection.py` now owns final-answer evidence filtering and
operand-evidence append projection. Public
`filter_aggregate_evidence_for_final_answer(evidence_items, *, final_answer,
selected_claim_ids)` extracts answer numeric candidates, preserves stable
evidence order and selected/operand numeric-support precedence, applies table-
numeric promotion, retrieved-narrative and reconciliation gates, percent support,
and quote/raw-row consistency, and returns fresh top-level copies or the current
all-filtered fallback. Public
`append_operand_evidence_for_final_answer(evidence_items, *, operands,
final_answer)` copies the evidence list, scans operands in order, preserves
numeric-equivalence and literal-surface support, derived-percent role, source-
anchor and duplicate-id gates, and appends the exact generated operand-evidence
schema with fresh top-level containers and nested identity preserved. Neither
mutates caller inputs or catches mapping, iteration, truthiness, string, regex,
normalization, numeric-surface, or copy exceptions.

The seven public calls remain at their original positions and at Try depth zero:
filtering is called once by
`_filter_final_aggregate_evidence_and_projection(...)` and twice by
`FinancialAgent._runtime_evidence_from_retrieved_docs(...)`; append is called
once by that graph method, once by `_replace_mutable_aggregate_answer(...)`, and
twice by `_apply_final_narrative_repair_pipeline(...)`. All seven calls are graph-
external and none is owner-local. Retrieved-doc/evidence preparation, selected-
claim and projection-provenance updates, answer choice/composition/refresh,
mutable state/evidence, artifact/ledger mutation, promotion, sync/rebuild, and
final sequencing remain graph-owned.

Commit `cde3d98` moved the former 66 + 102 = 168 definition-span lines to public
65 + 101 = 166 owner lines. Source is `+186/-179`, tests are `+1,426/-34`, and
the whole commit is `+1,612/-213`; its source diff SHA-256 is
`1e9aadbbef8bf83438337b2a68f753344f564a2c4a49c5192a61a7c2d02917b8`.
Focused 6/6, aggregate owner 52/52, affected semantic 767/767, import 19/19,
union 786/786, audit 217, and full discovery 1,716/1,716 passed. Benchmark
refresh was **NOT RUN**, remote CI is unverified, and the move proves no
behavior, accuracy, ranking, performance, total-code, executed-path, benchmark,
schedule, ledger, or Phase 3 completion.

Public aggregate-owner
`ensure_complete_growth_numeric_answer(answer, ordered_results,
evidence_items=None)` scans growth rows in reverse order, skips conflicting
periods, adopts the prepared complete growth answer and required display values,
preserves an already complete answer without untraced numeric material, and
otherwise retains stable extra sentences only when they are not already in the
complete answer, do not repeat required values, and are trace-safe. Public
`strip_untraced_numeric_material_from_growth_narrative_sentence(sentence,
ordered_results, evidence_items=None)` prepares complete growth surfaces and
required values, removes only configured untraced percent/KRW tokens, normalizes
punctuation, revalidates numeric trace support, and requires narrative markers,
at least two narrative terms, and non-noisy/non-fragment text before returning a
sanitized sentence. Neither mutates caller inputs or catches mapping, iteration,
truthiness, string, regex, normalization, sentence, numeric-surface, or policy
exceptions.

Commit `3674bb1` moved the former 47 + 108 = 155 definition-span lines to public
46 + 107 = 153 owner lines. All 19 direct calls remain graph-external and at Try
depth zero. Source is `+178/-176`, tests are `+1,547/-77`, and the whole commit is
`+1,725/-253`; the source diff SHA-256 is
`fb580debe8b766ce98f9258f55b13b00d712d5844fb6c18268abed685d38ebb5`.
Focused 6/6, aggregate owner 58/58, affected semantic 773/773, import 19/19,
union 792/792, audit 217, and full discovery 1,722/1,722 passed. Final-growth
selection, answer refresh, initial composition, final narrative repair,
aggregate orchestration, mutable state/evidence, artifact/ledger mutation,
promotion, sync/rebuild, and final sequencing remain graph-owned. Benchmark
refresh was **NOT RUN**, remote CI is unverified, and the move proves no
behavior, accuracy, ranking, performance, total-code, executed-path, benchmark,
schedule, ledger, or Phase 3 completion.

Public aggregate-owner
`append_final_answer_surface_operands_from_evidence(projection,
evidence_items, *, final_answer)` first extracts copied non-percent answer
candidates and returns the original projection when candidates or evidence are
absent. Otherwise it shallow-copies projection and operand rows, detects existing
numeric support, recursively collects period-role hints, scores copied matching
evidence with stable first-winner ties, infers period/role, and appends the exact
fresh operand schema when an answer numeric surface is not represented. It also
may synchronize a stale growth calculation result and plan when copied current/
prior operands produce a percent surface within the existing relative tolerance,
including fresh operand-value answer slots and cleaned source-row ids. It never
mutates caller projection or evidence inputs; after the initial identity gates it
returns a fresh top-level projection even when no append or growth synchronization
occurs. Only candidate-span integer conversion catches `TypeError`/`ValueError`;
other mapping, iteration, truthiness, string, regex, normalization, numeric-
surface, scoring, slot, and copy exceptions propagate.

Commit `fae0516` moved the former 313-line definition to a public 312-line owner
function. Its calculation-filter and `FinancialAgent.run()` calls remain direct,
graph-external, and at Try depth zero. Source is `+325/-319`, tests are
`+983/-9`, and the whole commit is `+1,308/-328`; the source diff SHA-256 is
`6b45dd51cfe790304227f99242525c54a7ddb2c0a65dafe940cb7e42069b8020`.
Focused 6/6, aggregate owner 64/64, affected semantic 790/790, import 19/19,
union 809/809, audit 217, and full discovery 1,728/1,728 passed. Both callers,
evidence filtering/provenance adoption, public-answer/runtime-evidence
preparation, debug/citation projection, mutable state/evidence, artifact/ledger
mutation, promotion, sync/rebuild, and final sequencing remain graph-owned.
Benchmark refresh was **NOT RUN**, remote CI is unverified, and the move proves
no behavior, accuracy, ranking, performance, total-code, executed-path,
benchmark, schedule, ledger, or Phase 3 completion.

The completed operand-owner boundary preserves the characterized behavior.
Public `lookup_hints_for_concept_key(concept_key)`
normalizes the concept key, reads the financial ontology, returns a copied direct
concept hint map when present, otherwise scans non-group concept specs for the
first normalized concept match, and returns a copied hint map or empty mapping.
Public `coerce_lookup_magnitude_value(...)` returns unchanged for null,
non-KRW, or nonnegative values; otherwise it requires ontology opt-in, one of the
current statement types, compatible magnitude surface tokens, and a current
parenthesis/minus source marker before returning the absolute value. It catches
no mapping, ontology, normalization, iteration, string, or truthiness exception.
The hint helper is owner-local to magnitude coercion while three
graph-helper hint calls remain external; lookup-record and one reconciliation
magnitude call remain external and same-block repair becomes owner-local.

Public `candidate_row_block_signature(candidate)` preserves the former
graph-helper contract: copy metadata, require row-context text, softly reject an
invalid integer row index, normalize nonblank lines, validate bounds, find the
nearest preceding contiguous pipe-header block, and return the table-source/
header-position/header-text signature or empty string. Public
`repair_note_operand_units_from_same_block(operand_rows, candidate_map)`
preserves the reconciliation contract: return the original list for fewer than
two rows; otherwise shallow-copy rows, group only configured note rows by the
signature, inherit a unit only when exactly one resolved unit exists, normalize
and ontology-coerce ambiguous rows, retain rows whose normalized value is null,
and preserve stable order, nested aliases, and all caller inputs. The signature's
integer conversion catches only `TypeError`/`ValueError`; other mapping,
iteration, truthiness, string, normalization, ontology, policy, and coercion
exceptions propagate.

Commit `5bd9e6f` moved the former 135 definition-span lines to four public
134-line owner functions. Fifteen calls finish as 12 external and three owner-
local. Source is `+156/-154`, tests are `+867/-13`, and the whole commit is
`+1,023/-167`; its source diff SHA-256 is
`b7bcf68a9cd79ab91f6e30978e434d9b5b504f06a85b4e582c20b0497bbecf21`.
Focused 8/8, operand owner 69/69, affected semantic 813/813, import 19/19,
union 832/832, audit 217, and full discovery 1,736/1,736 passed. Lookup-record
recovery, report-file/local-unit lookup, structured-cell selection, operand-row
construction, candidate extraction, LLM reranking, reconciliation state/
artifact/retry work, mutable evidence, ledger mutation, and final sequencing
remain graph/existing-owner responsibilities. Benchmark refresh was **NOT RUN**,
remote CI is unverified, and the move proves no behavior, accuracy, ranking,
performance, total-code, executed-path, benchmark, schedule, ledger, or Phase 3
completion.

The completed caller-facing run-projection boundary preserves characterized
behavior. Owner-private
`_runtime_evidence_defaults(final)` preserves report-scope company/year
precedence and first-list fallback. Owner-private
`_compact_runtime_evidence_metadata(metadata)` shallow-copies metadata, always
drops table-object/value-record payloads, drops row-record payloads only above
20,000 characters, drops other fields above 4,000 characters, and records sorted
unique removed field names. Public `enrich_runtime_evidence_metadata(final,
evidence_items)` shallow-copies evidence rows and metadata in stable order,
fills absent company/year, derives a blank source anchor from metadata in the
current precedence order, owner-locally compacts metadata, preserves nested
aliases, and leaves inputs unchanged.

Public `project_debug_traces(final)`, `project_agent_answer(...)`,
`project_review_trace(...)`, and `project_debug_bundle(...)` retain their exact
literal output keys, indexed versus defaulted field access, and supplied object
identities. Public `augment_citations_from_runtime_evidence(citations,
runtime_evidence)` copies nonblank citations, normalized-case deduplicates them,
scans copied evidence/metadata in stable order, resolves the anchor through the
current fallback chain, adds company/year brackets only to unbracketed anchors,
and leaves inputs unchanged. These projections catch no mapping, iteration,
truthiness, string, copy, or normalization exceptions.

Commit `84fe1d5` moved the former 189 definition-span lines to a 184-line owner
surface with six public and two owner-private functions. Eleven calls finish as
nine graph-external and two owner-local. Source is `+232/-211`, tests are
`+1,702/-17`, and the whole commit is `+1,934/-228`; its source diff SHA-256 is
`84b8d32bee450cde9370fa6f72646f006ce9bb47413169b34c1c50b0053a5a24`.
Focused 8/8, run-projection owner 65/65, affected semantic 515/515, import
19/19, union 534/534, audit 217, and full discovery 1,744/1,744 passed. The move
adds no output field. Runtime-evidence fallback and selection, structured/stale
answer repair, trace resolution and rebuild, task-artifact projection, graph
execution, compatibility assembly, retrieval/provenance construction, mutable
state/evidence, ledger mutation, and final sequencing remain graph/existing-owner
responsibilities. Benchmark refresh was **NOT RUN**, remote CI is unverified,
and the move proves no behavior, accuracy, ranking, performance, total-code,
executed-path, benchmark, schedule, ledger, or Phase 3 completion.

The completed prepared public-answer state boundary retains the characterized
behavior. Public
`structured_result_answer_for_missing_public_answer(public_answer,
structured_result)` normalizes the public answer, reads the structured subtask
answer, rejects blank/equal/nonnumeric structured answers, then requires the
configured missing-marker set and returns the structured answer only when the
public answer has a marker that the structured answer lacks. It catches no
mapping, truthiness, string, regex, normalization, policy, or structured-result
projection exception.

Public `complete_aggregate_public_answer_projection(*, subtask_results,
base_answer, public_answer)` selects the preferred complete answer using the
base/public fallback, returns empty values when no answer exists, builds an
aggregate runtime projection, and returns the answer with an empty trace when
that projection lacks subtask rows. Otherwise it attaches the existing source
metadata and sets `public_answer_repaired` plus
`complete_aggregate_answer_selected` on a fresh runtime-projection mapping.

Public `with_public_answer(state, public_answer)` shallow-copies state and sets
both `answer` and `compressed_answer`. Public `public_projection_state(final,
*, public_answer, runtime_calculation_trace, runtime_evidence=None)` owner-locally
uses that copy, installs the supplied trace identity, and when runtime evidence
is provided stores that list identity while constructing `evidence_items` as the
stable concatenation of copied list surfaces from final and runtime evidence.
Both leave caller mappings and lists unchanged; mapping, iteration, copy, and
truthiness exceptions propagate.

The `a88b215` movement is the exact 74-line, four-public-function, 13-call batch.
It became 71 owner lines and finishes as 12 graph-external plus one owner-local
call. Dynamic complete-numeric, structured-subtask, collapsed-ratio, period-
repair, retrieved-ratio, runtime-evidence selection, graph execution,
compatibility assembly, mutable state/evidence, artifact/ledger mutation, and
final sequencing remain graph/existing-owner responsibilities. Focused 6/6,
run-owner 71/71, affected semantic 521/521, import 19/19, union 540/540, runtime
audit 217, and full discovery 1,750/1,750 passed. Benchmark refresh was **NOT
RUN**, remote CI is unverified, and the move proves no behavior, accuracy,
ranking, performance, total-code, executed-path, ledger, or Phase 3 completion.

The structured-reconciliation candidate-projection boundary is now owned by
`financial_reconciliation_candidates.py`. The state-free owner receives already
prepared candidate, metadata, structured-cell, operand, constraint, and ID
mappings. It may normalize, score, copy, and project those values, but it does
not read or mutate `FinancialAgentState`, retrieve evidence, call an LLM, update
artifacts, or plan a retry.

Candidate statement projection first prefers normalized explicit
`statement_type`, then constructs the current ordered section/title/heading/
table/source surface and returns the first configured statement type whose
configured marker occurs. Candidate unit projection preserves percent-family
handling, label/header/metadata surface assembly, ambiguous-KRW-unit policy,
local-unit inference, note-statement gating, and raw-unit fallback. All mapping,
truthiness, stringification, normalization, policy, and helper exceptions retain
their current propagation and access order.

Period projection preserves effective operand focus, structured-cell period
resolution, configured period-presence matching, ordered report-year coercion
with `TypeError`/`ValueError` soft skips only, target-year handling, and the
current current/prior/period-hint fallback. Candidate/cell scoring preserves the
sum of the two existing helper scores and returns that score with the resolved
period. Structured-cell identity preserves value-ID precedence, row/column
fallback, and ordered header/value fallback without mutating the cell.

Operand-row projection shallow-copies candidate metadata, derives raw value and
unit with selected-cell precedence, applies candidate-unit handling before
normalization, applies lookup magnitude coercion, returns `None` only when the
normalized value is unavailable, then builds the current fresh row with stable
field names and operand/candidate metadata. Statement type is currently resolved
twice on the successful path and that access count remains part of the literal
contract. Effective-unit projection is the same unit helper over a copied
metadata view. Nested candidate, cell, operand, alias, and header values retain
their identities and caller inputs remain unchanged.

Reconciliation-match selection filters by normalized label, prefers the first
exact role when a role is present, otherwise returns the first label match, and
returns a fresh empty mapping when none exists. Candidate-ID expansion preserves
input order, blank skipping, `recon::` alternate generation, `::raw_row`
variants, first-seen dedupe, and candidate-map membership gating. Candidate
lookup strips the requested ID, returns `None` for absence, shallow-copies the
selected candidate, and changes `evidence_row` to `table_row` only when copied
metadata has a nonblank `row_text`; nested metadata identity remains unchanged.

The completed `bb0a982` boundary is the exact 293-line, 11-function, 26-call
sequence. It became seven public and four owner-private functions totaling 285
owner lines, with 19 reconciliation-external and seven owner-local calls.
Focused 8/8, candidate-owner 8/8, affected semantic 486/486, import 19/19, union
505/505, runtime audit 217, and full discovery 1,758/1,758 passed. Its source
diff SHA-256 is
`6469dfd06b0efd36c92d252753ba96ecdeb5421e4dc3fdaac0c492cdd4167a5f`.
Structured-pair and operand extraction orchestration, candidate collection/
selection, LLM rerank, evidence-item construction, artifact/retry/state
mutation, and final sequencing remain in `financial_graph_reconciliation.py`.
Benchmark refresh was **NOT RUN**, remote CI is unverified, and the move proves
no behavior, accuracy, ranking, performance, total-code, executed-path, ledger,
or Phase 3 completion.

The completed reflection retry-query projection boundary is owned by
`financial_reflection_projection.py`. Public
`build_retry_queries(state, missing_info)` reads explicit companies first and,
only when absent, the first company-bearing seed document. It eagerly converts
every supplied year with `int`, requires `state["query"]`, applies topic and
intent/query-type fallback, obtains preferred calculation sections, constructs
one normalized query per missing-info item with at most two section hints, then
returns a fresh stable first-seen deduplicated list without blanks. It mutates no
state, document metadata, missing-info list, or nested value; mapping, metadata,
iteration, integer conversion, helper, string, and normalization exceptions
retain their current propagation.

Public `finalize_retry_queries(state, reflection_plan, missing_info)` repeatedly
normalizes planner subqueries as it filters them and calls the public builder
only when no base query survives. For `find_missing_values`, `resolve_binding`,
and `find_direct_row`, it appends the first two normalized missing items. It
retains explicit companies access, finds a report-company hint from seed docs
before retrieved docs, combines global and planner-preferred sections through
the current repeated alias calls and stable dedupe, expands section-qualified
queries only for direct-row/binding objectives, replaces raw planner section
text with its alias for every base query, prefixes a missing report company, and
returns a fresh stable deduplicated list. Caller mappings/lists and nested values
remain unchanged; access, truthiness, iteration, metadata, string, helper, and
normalizer exceptions are not newly caught.

The former 26-line builder and 81-line finalizer became 26 and 80 owner lines.
The builder remains graph-external from `_heuristic_reflection_query_plan(...)`
and is owner-local from the finalizer; the finalizer remains graph-external from
`_prepare_reflection_retry(...)`. Both calls stay outside a `try`, preserve exact
state/list identity and arguments, adopt the returned list at the current point,
and allow an owner exception to stop downstream planner-section or action/
report/artifact work. The three calls finish external two/local one.

The owner added only `_preferred_calc_sections` and `_section_hint_alias` through
the existing one-way retrieval-hints dependency; no dependency reaches reflection
projection or either graph mixin, so the DAG remains acyclic. No selected span
moved a reviewed runtime-domain record and the count remains 217. The completed
`b74535e` source is `+118/-112`, tests are `+1,113/-4`, and the whole commit is
`+1,231/-116`. Its source diff SHA-256 is
`728603f15ce24c0915444755442bc6cf3be4a2bbd26c6f41adffedcb08ccdbb1`.
Focused 6/6, reflection owner 24/24, affected semantic 758/758, import 19/19,
union 777/777, runtime audit 217, and full discovery 1,764/1,764 passed.
`_select_retry_strategy_for_reconciliation(...)`, heuristic missing/dependency
resolution, `_plan_reflection_retry(...)`, prompt/model invocation,
`_prepare_reflection_retry(...)`, action/report/artifact construction, state
clearing, routing/promotion, and final sequencing remain graph-owned.

The completed `06710c1` aggregate subtask projection/upsert boundary preserves
the characterized planning-mixin behavior in its aggregate owner.
Public `build_aggregate_calculation_projection(ordered_results, final_answer)`
scans rows in order, uses owner-local `aggregate_result_operation_family(...)`,
and replaces a conflicting growth row only by fresh row/result/answer-slot
copies that clear calculation operands and source references while retaining the
current material-gap feedback. It then delegates to the runtime-trace aggregate
builder, scans copied runtime-evidence rows in stable order, deduplicates by
nonblank evidence ID or the normalized source-anchor/quote/raw-row/claim surface,
and returns only calculation operands, plan, result, and evidence items.

Public `structured_subtask_projection_for_public_answer(state, trace)` copies
the prepared structured result, requires a normalized public answer equal to the
structured answer and at least one subtask row, and compares the current rendered
surface before choosing the preferred complete aggregate answer. It delegates to
the distinct runtime-trace private aggregate builder, returns empty unless the
projected result retains subtask rows, and otherwise attaches the existing
`structured_result_subtasks` metadata. Both public projections preserve current
mapping/list access order, shallow-copy/nested-identity behavior, helper
laziness, input immutability, and uncaught exception propagation.

Public `upsert_subtask_result(existing, current)` returns a fresh list, preserves
input order, matches only a nonblank current task ID, and keeps an existing row
only when owner-private `_subtask_upsert_quality_rank(...)` is strictly greater.
A tie adopts `current`; every matching duplicate is replaced under the same
rule; a missing task is appended. The rank tuple remains status, material,
structured-payload, cleaned-source-count, answer-digit-count, and answer-length
in that exact order, with current fallbacks, truthiness, normalization, and
exception scopes.

The selected graph definitions span 69 + 36 + 23 + 28 = 156 lines and project
to owner spans 68 + 35 + 22 + 28 = 153. Four graph call sites remain external:
one build call in `_rebuild_aggregate_projection(...)`, one structured-public
call in `_structured_public_answer_trace_projection(...)`, and two upsert calls
in `_advance_calculation_subtask(...)` and
`_prepare_initial_aggregate_state(...)`. The two rank calls become owner-local.
All six calls stay outside a `try`, preserve exact arguments and list/mapping
identity, adopt the returned value at the current point, and allow an owner
exception to stop downstream filtering, ratio repair, state clearing, sorting,
recovery, or aggregation work.

The aggregate owner already had the selected bodies' answer-projection,
normalization, runtime-trace, and operation-family dependencies or an existing
one-way edge to them. Runtime trace and graph state do not import aggregate, and
the main graph plus calculation graph already do. Planning need not import
aggregate after this exact move, so the DAG stays acyclic. No selected span moved
a reviewed runtime-domain record and the count remains 217. Source is
`+181/-184`, tests are `+1,143/-41`, and the whole commit is `+1,324/-225`.
Focused 7/7, aggregate-subtask owner 118/118, affected semantic 780/780, import
19/19, union 799/799, audit 217, and full discovery 1,771/1,771 passed. The
source diff SHA-256 is
`0cb0b708ee672f115f0a06eea62217f598e87d1a194f6422d422ba126bb51f7b`.
At that checkpoint nested traversal/scoring/promotion still remained graph-owned;
the subsequent `a8ad25f` boundary below moved only that selected state-free
cluster through the acyclic answer-projection route. State capture, projection
filtering, broader recovery/alignment/synchronization, artifact/ledger mutation,
and final sequencing remain graph-owned.

The completed nested subtask selection/promotion boundary belongs to
`financial_answer_projection.py`. Public
`nested_subtask_rows(calculation_result)` traverses direct and answer-slot child
lists in depth-first source order, skips non-dicts, returns shallow child
copies, preserves nested identity, and never mutates the prepared result.
Owner-private `_subtask_row_operation_family(row)` preserves row, answer-slot,
and calculation-result operation precedence, aggregate-child inference, and the
`concept_` metric-family fallback. Owner-private
`_subtask_row_specificity_score(row, *, active_subtask)` preserves the exact
status/material/non-aggregate/operation/family/label tuple and its task mismatch,
exact-label, substring, and token-overlap rules.

Public `promote_nested_subtask_result_if_more_specific(...)` preserves active-
operation and nested-child gates, stable score ordering, score-prefix filtering,
current-material protection, aggregate-child rejection, answer/status/result
fallback order, fresh selected-result copying, unchanged-path identity, input
immutability, and uncaught exceptions. Its planning caller supplies the exact
four keyword arguments and adopts the returned answer, status, and result before
later narrative synthesis. The calculation caller supplies the exact prepared
calculation result to `nested_subtask_rows(...)` before dependency-coherence
comparison and broader row replacement. Both calls stay outside `try` blocks;
owner exceptions stop downstream work.

The former definition spans were 20 + 19 + 38 + 51 = 128 lines and now occupy
20 + 19 + 37 + 50 = 126 owner lines. The two external calls remain in
`_capture_current_subtask_result(...)` and
`_promote_stronger_nested_aggregate_results(...)`; four helper calls become
owner-local. Answer projection owns all required dependencies and is imported
one-way by planning and calculation, so no new module edge or cycle was
introduced. The selected spans contain no reviewed runtime-domain record.
Source is `+138/-135`, tests are `+673/-23`, and the whole commit is
`+811/-158`. Focused 6/6, answer-projection owner 23/23, affected semantic
770/770, import 19/19, union 789/789, audit 217, and full discovery
1,777/1,777 passed. The source diff SHA-256 is
`ce62390b757ff986fe704f40fce1e690a6473819890d1725a5aec5e82850687b`.

State/task/evidence capture, dependency-coherence winner comparison, broader row
replacement, projection synchronization/rebuild, mutable state/evidence,
artifact/ledger mutation, and final sequencing remain in their current graph
owners. This move establishes no behavior, accuracy, performance, total-code,
executed-path, benchmark, schedule, or Phase 3 completion claim.

The completed aggregate-result boundary is two sequential state-free moves into
`financial_aggregate_projection.py`. Public
`promote_stronger_nested_aggregate_results(ordered_results)` preserves the
former 64-line graph contract after `self` removal: stable task-ID mapping,
source-slot preparation, nested traversal, exclusion order, direct-source/
numeric-conflict/sign protection, strict nested-rank and dependency-coherence
comparisons, replacement chaining, provenance-container carry-forward,
unchanged-list identity, changed-row shallow copies, nested aliases, input
immutability, and uncaught exceptions. Its three graph callers retain their
exact positional arguments and current adoption points.

Public `sync_aggregate_arithmetic_subtask_surfaces(ordered_results,
aggregate_projection, final_answer)` preserves the former 124-line graph
contract after `self` removal: projection/result/slot copying, empty identity,
planned arithmetic-task gates, stable candidate indexes, operation/answer/
numeric-conflict/coverage/cardinality ordering, repeated answer-sentence
selection at adoption, rendered-value and row-surface projection, lookup-slot
component sync, ordered-result and answer-slot replacement, nested aliases,
input immutability, access laziness, and uncaught exceptions. Its sole graph
caller retains exact positional arguments and adopts both returned values at the
current point.

The two old spans total 188 lines and now occupy public spans 63 + 123 = 186.
The selected call distribution is four graph-external and zero owner-local.
Aggregate projection already owns every dependency except
`nested_subtask_rows(...)` on its existing answer-projection edge, and neither
answer projection nor numeric/normalization dependencies reach aggregate. The
owner does not reach calculation, while calculation already imports it, so the
move is acyclic. No selected span contains a reviewed runtime-domain record.
Retired private definitions and refs are zero. Across `6ed195e..b5d97ee`, source
is `+197/-204`, tests are `+1,569/-184`, and the whole range is
`+1,766/-388`. Focused 12/12, aggregate owner 76/76, affected semantic
798/798, import 19/19, audit 217, and full discovery 1,789/1,789 passed. The
range source diff SHA-256 is
`ee76d6ffa2c0e1f14e8dec7630a6f11e5f39ad4323e1ed5a23f07e6d0fbda1f8`.

Only these two prepared-row transforms supersede the earlier broad
synchronization stop. Dependency alignment, projection rebuild, state/evidence
orchestration, artifact/ledger mutation, and final sequencing remain graph-owned.

The completed prepared-growth boundary is public
`recover_duplicate_growth_prior_operand(ordered_operands, evidence_items)` in
`financial_aggregate_projection.py`. It must preserve the former 53-line graph
contract after `self` removal: exact two-operand gating; stable current/prior
role lookup; fresh role-row copies; material-sharing and evidence-recovery
ordering; display/raw-value, unit fallback, and normalization gates; period,
rendered display, source quote, and recovery-source projection; replacement by
operand ID without reordering; unchanged-list identity; changed-prior shallow
copy and nested aliases; input/evidence immutability; access laziness; and
uncaught exceptions. The projected owner span is 52 lines. Its sole graph caller
in `_prepare_calculation_candidate(...)` retains exact positional arguments and
adopts the returned operands after growth unit alignment and before the existing
growth-period conflict check.

The aggregate owner already owns every selected dependency on existing one-way
edges and has no route back to calculation. The move therefore adds no module
edge or cycle and moves no reviewed runtime-domain record. Commit `b3bb764`
records source `+56/-55`, tests `+629/-26`, and whole-commit `+685/-81`.
Focused 4/4, aggregate owner 80/80, affected semantic 838/838, import 19/19,
semantic/import union 857/857, audit 217, and full discovery 1,793/1,793
passed. The source diff SHA-256 is
`1a02ec371d28b6012b064281260ad3b274bc9f1ef0b330d0724c36d545b56d1a`.
Candidate input/carrier construction, direct evidence selection,
duplicate-prior caller adoption, unit and period alignment, calculation
execution, state/evidence, projection rebuild, artifact/ledger mutation, and
final sequencing remain graph-owned.

The completed final-evidence boundary is public
`filter_final_aggregate_evidence_and_projection(aggregate_evidence_items,
aggregate_projection, *, final_answer, selected_claim_ids)` in
`financial_aggregate_projection.py`. It preserves the former 48-line graph
contract after `self` removal: exact delegation to final-answer evidence
filtering; stable kept-evidence-ID collection with non-dict/blank exclusion;
the nonempty-kept-ID gate; selected-claim intersection before operand-evidence
append; stable dedupe and order; prepared provenance filtering; final-answer
surface-operand append; exact four-value return order; shallow copies, nested
aliases, input immutability, access laziness, and uncaught exceptions. The owner
span is 47 lines.

Both `_aggregate_calculation_subtasks(...)` calls retain their exact two
positional arguments and `final_answer`/`selected_claim_ids` keywords. The first
adopts ordinary aggregate evidence/projection output before state sync and
runtime-ratio repair. The conditional second call uses the stale-repair evidence
snapshot only after stale aggregate-state replacement and before the next state
sync. Both remain outside `try` blocks. The destination owns all three selected
helper APIs and the provenance input carrier, so the move adds no module edge or
runtime-domain baseline record. Evidence preparation, stale repair, mutable
state synchronization, runtime-ratio repair, answer composition,
artifact/ledger mutation, and final sequencing remain graph-owned. Commit
`d31e67a` records source `+52/-53`, tests `+646/-41`, and whole-commit
`+698/-94`. Focused 4/4, aggregate owner 84/84, affected semantic 806/806,
import 19/19, semantic/import union 825/825, audit 217, and full discovery
1,797/1,797 passed. The source diff SHA-256 is
`f10c327aca0fb5a4a885892354bef1b840caaf224a9696ae113c9d650df45df1`.

The completed runtime-trace boundary is public
`repair_collapsed_ratio_trace_from_evidence(state, trace)` in
`financial_runtime_trace.py`. It preserves the former 310-line graph contract
in 309 owner lines after removing only `self`: ratio/status/component gates;
cleaned source/value identity; copied prepared evidence/context-doc collection;
aggregate-token, label/concept, anchor and unit matching; stable numeric
candidate rank/tie behavior; zero/equal rejection; formatted percent result;
slot/source/role and operand overlay projection; trace copies/nested aliases;
input immutability; access laziness; existing soft conversion failures; and all
other propagated exceptions.

Both `financial_graph.py` callers retain exact positional arguments and remain
outside `try` blocks. `_structured_public_answer_trace_projection(...)` calls
the owner only after a nonempty structured projection.
`_repair_public_runtime_calculation_trace(...)` adopts the returned trace before
the separate period-comparison repair. Retrieval, public-answer orchestration,
period repair, canonical evidence-ID/window/provenance construction, mutable
state or evidence, artifact/ledger mutation, and final sequencing remain
graph-owned. Commit `8861253` records source `+322/-315`, tests `+1,574/-166`,
and whole-commit `+1,896/-481`. Focused 6/6, aggregate-subtask 124/124,
text-surface 20/20, affected semantic 832/832, import 19/19, semantic/import
union 851/851, audit 217, and full discovery 1,803/1,803 passed. The source diff
SHA-256 is
`a83d1ddaa2167516789bc9de1a90033dd7183d6764ddf0609bf91a777199e451`.

The completed direct structured-evidence boundary is public
`lookup_row_from_direct_structured_evidence(operand, evidence_item, *, index)`
and `coerce_operand_value_from_direct_structured_evidence(row, evidence_item)`
in `financial_lookup_recovery.py`. They preserve the former 81-line and
139-line graph contracts in 80 and 138 owner lines after removing only `self`:
metadata/cell copies; ordinary and aggregate selection; period focus and
aggregate-role preference; authoritative-surface and query-year handling;
normalization, equality, `1e-6` tolerance and period-specific override;
magnitude-record and changed-row adoption; stable order; nested aliases; input
immutability; access laziness; identity returns; and existing soft versus
propagated exceptions.

Their five calculation calls remain direct imported-name calls and outside
`try` blocks. The four lookup-row calls retain their exact `index=1` or
`index=operand_index` arguments in evidence-pool and period-table preparation.
The operand-value call remains after period coercion and before magnitude
coercion, structured/dependency early returns, and precision refinement. The
old private definitions and source/test references are zero. Evidence-pool
selection/scoring, state/report scope, table-label lookup, precision refinement,
mutable evidence, artifact/ledger mutation, and final sequencing remain
graph-owned.

The completed aggregate boundary is public
`align_lookup_result_units_from_own_evidence(ordered_results, evidence_items)`
in `financial_aggregate_projection.py`. It preserves the former 62-line graph
contract in 61 owner lines: evidence-ID indexing and empty-evidence identity;
row order; explicit operation-family precedence with aggregate-family fallback;
lookup/single-value, material-slot, raw-value, evidence, coerced-unit,
unchanged-unit, and normalized-value gates; source-ID cleanup; exact primary-
slot update and replacement marker; unchanged-row alias identity; original-
list identity when nothing changes and a fresh list only on material change;
nested aliases; input/evidence immutability; access laziness; and uncaught
exceptions.

Both calculation callers retain exact positional list identity and remain
outside `try` blocks. The initial-evidence caller adopts the result before
peer-source alignment and the equality-gated dedupe/rebuild path. The late
aggregate caller invokes it after missing-context evidence adoption and before
peer-source alignment and late result replacement. The old mixin definition
and source/test private refs are zero. The graph's now-dead
`lookup_primary_slot` and `replace_lookup_primary_slot` imports retired. Commit
`a476dd9` records source `+74/-68`, tests `+786/-13`, and whole-commit
`+860/-81`. Focused 4/4, aggregate owner 88/88, semantic 882/882, import 19/19,
union 901/901, audit 217, and full discovery 1,815/1,815 passed. The source diff
SHA-256 is
`bbe5f3cc62535f3fe8b6d2c2a4a56a27b10d0515cf0fff2083105d34ed171e19`.

The deterministic-plan boundary completed in `c021d30` and remains governed by
the literal ownership contract recorded here. Public 36-line
`build_runtime_deterministic_operation_plan(...)` in
`financial_calculation_execution.py` preserves resolved-active-task copying,
required filtering, metric fallback, exact base-plan keyword construction,
difference percent-point policy, query fallback laziness, copied output, input
immutability, and exception propagation. Its three graph calls retain their
positional and `active_subtask` keyword contracts outside `try` blocks.

Public 195-line
`build_deterministic_ontology_plan(active_subtask, operands, *, metric_key)` in
the same owner preserves role/scope/statement/stage/source preference, stable
first-max ties, required and ratio-role gates, operand ordering and variable
bindings, average-denominator behavior, unit normalization, ratio/sum formula
and explanation surfaces, input immutability, laziness, and exceptions. Its
sole graph caller copies the active subtask before invoking dynamic
`self._calc_metric_family(state)` and passes both resolved values to the owner.
The former 237 graph definition lines are now 231 owner lines, all four calls
remain graph-external, and three reviewed runtime-domain records moved with
unchanged text/category/count while audit total remains 217. Deterministic
lookup planning, guard/adoption, LLM planning, state/trace/artifact updates,
execution orchestration, and final sequencing stay graph-owned.

The next query-focus/text-surface boundary is sequential and is defined only by
[Project Status Next Work](../overview/project_status.md#next-work). Public
`query_focus_marker_groups(query, *, limit=8)` and
`query_focus_markers(query, *, limit=8)` must preserve normalization, policy
copying, connector/particle cleanup, configured stopword/year/digit/letter/
length gates, extraction order, case-insensitive stable dedupe, labels, slicing,
fresh outputs, laziness, and uncaught exceptions. Public
`preserve_source_visible_query_terms(...)` must preserve answer/marker gates,
support-surface and ontology sibling matching, case-insensitive missing-term
dedupe, four-term cap, template formatting, copied read-only inputs, laziness,
and exceptions. All selected calls stay direct and outside `try`; marker groups
finish external three/local two, flattened markers external five/local zero,
and preservation external two/local zero. Retrieval/reranking, evidence
construction, dynamic active-policy dispatch, aggregate orchestration, mutable
state/evidence, artifact/ledger mutation, and final sequencing stay outside the
text owner. The private stopword class alias has no repository override, patch,
`hasattr`, or non-call binding; the moved public helper owns the reviewed config
constant directly, and a newly discovered compatibility caller is a stop
condition rather than a reason to add a wrapper.

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
