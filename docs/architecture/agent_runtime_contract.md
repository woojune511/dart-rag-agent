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

## 9. Aggregate Subtask Projection

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
`calculation_result` mirrors are not the long-term source of truth. Caller,
evaluator, and benchmark surfaces should consume `resolved_calculation_trace`
first, then task/artifact ledger projections, then aggregate subtask
projections. If the resolver must fall back to legacy top-level
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
New readers that do not need external compatibility may call
`_resolve_runtime_calculation_trace(..., allow_legacy_top_level = false)`.
Strict mode rejects top-level `calculation_*` fallback while still allowing
non-legacy `structured_result` projection.
Evaluator result export, benchmark serialized/review export, eligible
analyst/MAS artifact handoff consumers, current-runtime debug readers,
reflection retry planning, formula planning input resolution, calculation
execution input resolution, dependency-projection recalculation result readers,
route-decision readers after formula planning/calculation,
render/verification/retry preparation readers, and late runtime numeric answer
shaping use strict mode, so those review, runtime handoff, debug, retry,
planning, execution, routing, and answer preparation surfaces do not resurrect
legacy top-level mirrors.
Historical replay, retrospective readers, and public runtime projection bridges
may opt into legacy compatibility when they read older result bundles or older
caller surfaces. In the live agent, that bridge is limited to
`FinancialAgent.run()`/export-facing projection; new internal current-state
readers must use strict mode.
Helper-level adapters may preserve legacy fallback only when their surface is
explicitly compatibility-oriented: `_resolve_runtime_structured_result()` is for
export/review adapters that may read older payloads, and
`_runtime_trace_state_update()` may carry omitted trace parts from older state
surfaces. Migrated live graph nodes should pass updated trace parts explicitly
instead of relying on that carry-forward.

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
display fields.

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
MAS nodes that write artifacts should publish `Artifact` entries through
`build_artifact()`. The helper owns artifact id defaults, kind/status/summary
normalization, payload projection, evidence link/ref mirroring, producer task id,
and metadata normalization while preserving the existing compatibility `content`
field.
MAS consumers should read typed artifact projections first: answer and
calculation status from `payload`, evidence from `evidence_refs`, and only then
fall back to compatibility `content`/`evidence_links` for older callers.

When a node updates the runtime trace through `_runtime_trace_state_update()`,
the helper defaults to `include_compatibility_mirrors = false`. Branches that
still need top-level `calculation_*` compatibility mirrors must opt in
explicitly and explain the external reader that still requires those mirrors.
Current converted branches include calculation verification skip, formula
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
default. Active-task artifact projection uses strict current-state resolution as
well: empty `resolved_calculation_trace` must not resurrect legacy top-level
`calculation_*` fields, except for the explicit stale-aggregate to live
non-aggregate override. Downstream readers must use `resolved_calculation_trace`.
