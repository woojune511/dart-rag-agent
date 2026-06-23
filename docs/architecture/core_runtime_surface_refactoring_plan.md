# Core Runtime Surface Refactoring Plan

This plan defines the preferred direction for reducing project complexity without
removing the core financial QA capabilities. The goal is not line-count
reduction by itself. The goal is to make the default product path small and
explicit, while moving review, debug, benchmark, and experimental surfaces behind
clear boundaries.

This document complements `docs/architecture/agent_runtime_contract.md`. If a
runtime behavior question conflicts with the runtime contract, the contract wins.
If a structural refactor changes the contract, update both documents.

## Primary Direction

The default runtime should make one user question resolve to one grounded answer:

```text
main.py -> financial_router.py -> FinancialAgent
  -> parser/vector/router/graph -> answer
```

The core runtime should stay focused on:

- DART section and table structure preservation
- `section_path`, `table_context`, `period_focus`, `unit_hint`,
  `statement_type`, and `consolidation_scope`
- value-cell-first table metadata
- operand binding trace
- deterministic calculation
- `structured_result`
- `resolved_calculation_trace`
- reviewer gate and task artifact trace

These are structural capabilities and should not be removed merely to make code
shorter.

The surfaces that should move away from the default product path are:

- benchmark and eval workflows
- MAS experiments and skeleton nodes
- broad internal debug fields in public API responses
- disabled-by-design cache or reviewer handoff paths
- portfolio and retrospective ops scripts
- legacy compatibility mirrors that can conflict with canonical traces

## Target Layout

The long-term target is a clearer split between core product runtime, ingest,
experiments, evaluation, and ops:

```text
src/
  app/
    api/
      financial_router.py
    main.py

  core/
    runtime/
      agent.py
      graph.py
      state.py
      output.py

    retrieval/
      query_planning.py
      retriever.py
      evidence.py
      structure_expansion.py

    calculation/
      operands.py
      binding.py
      formula_planner.py
      executor.py
      renderer.py
      verifier.py
      reflection.py

    contracts/
      answer_slots.py
      traces.py
      artifacts.py
      evidence_schema.py

  ingest/
    parser/
      financial_parser.py
      sections.py
      tables.py
      chunking.py
      value_records.py
    storage/
      vector_store.py
      embeddings.py
      bm25.py
      structure_graph.py

  experimental/
    mas/

  eval/
    evaluator.py
    benchmark_runner.py
    gates/

  ops/
```

Do not make this move as a big-bang change. Preserve public facades first, then
move implementation behind them.

## Refactoring Principles

1. Hide execution surfaces before deleting features.
2. Keep `FinancialAgent` as the product runtime facade until a replacement has
   the same tests and review gates.
3. Keep benchmark, eval, and MAS compatibility adapters outside the core answer
   path.
4. Preserve canonical trace schemas before removing legacy fields.
5. Prefer no-behavior-change extraction before behavioral repair.
6. Do not introduce benchmark-specific or company-specific runtime branches.
7. Keep deterministic calculation and provenance validation in code; keep domain
   vocabulary in ontology, policy, config, or documented data artifacts.

## Recommended PR Sequence

### PR 1: Output Boundary Cleanup

Add typed projections without changing existing behavior:

- `AgentAnswer`: public answer fields
- `ReviewTrace`: evidence, retrieval, numeric, and task artifact review fields
- `DebugBundle`: usage, retry, and raw debug fields

`FinancialAgent.run()` may continue returning the existing dict shape through a
compatibility adapter, but new code should consume explicit projections.

### PR 2: Public Response Slimming

Keep the API default response focused on answer, citations, query metadata,
`structured_result`, and `resolved_calculation_trace`.

Expose review/debug bundles only through explicit reviewer, ops, or debug flags.
Keep evaluator compatibility in an adapter, not in the default API model.

### PR 3: State Type Split

Split `FinancialAgentState` into concern-specific TypedDicts while preserving the
current graph node contract:

- `RoutingState`
- `RetrievalState`
- `EvidenceState`
- `CalculationState`
- `ReflectionState`
- `LedgerState`

Then compose `FinancialAgentState` from those pieces. This reduces conceptual
surface without changing runtime behavior.

### PR 4: Calculation Extraction

Refactor `financial_graph_calculation.py` so the mixin becomes orchestration
only. Extract stable responsibilities in this order:

1. pure helper functions
2. normalization
3. operand binding
4. deterministic execution
5. answer slot construction and rendering
6. verification
7. reflection and repair

Responsibilities should remain clear:

- binding decides which numbers are used
- executor calculates only
- renderer formats answer text from slots and trace
- verifier checks trace and answer consistency
- reflection decides the next action after failure

#### PR 4 Current Status And Stop Line

Status as of 2026-06-17: the high-risk calculation extraction work is
functionally complete enough to pause. The file is still large, but the most
important runtime boundaries now have focused modules and regression coverage:

- answer slot construction:
  `src/agent/financial_answer_slots.py`
- calculation execution/result payload helpers:
  `src/agent/financial_calculation_execution.py`
- calculation rendering helpers:
  `src/agent/financial_graph_calculation_rendering.py`
- text/narrative surface helpers:
  `src/agent/financial_text_surface.py`
- reflection/task-artifact projection helpers:
  `src/agent/financial_reflection_projection.py`

The extracted surfaces now cover:

- failure `calculation_result` payloads
- scalar current/prior/delta state assembly
- scalar and time-series result payload construction
- scalar and time-series result `series` rows
- scalar and time-series rendered result display
- time-series pairwise YoY growth calculations
- successful scalar and time-series task/artifact publication
- answer-slot row construction and aggregate slot assembly
- reflection action/report and task-artifact integrity feedback

Verification baseline after the extraction sequence:

- `tests.test_operation_contracts`: `226` OK
- `tests.test_subtask_loop`: `210` OK
- `tests.test_financial_calculation_execution` +
  `tests.test_financial_calculation_rendering`: `22` OK
- `python -m src.ops.audit_runtime_domain_terms`: passed with `216` reviewed
  literals

Stop line: do not continue splitting `financial_graph_calculation.py` merely to
reduce file size. Continue PR 4 only when a concrete bug or contract gap points
to one of these specific seams:

- metric-name derivation for time-series results
- remaining calculation normalization/repair helpers that can be moved without
  adding domain vocabulary to runtime code
- verification/reflection callbacks that need a clearer typed boundary
- removal of compatibility aliases after callers no longer depend on them

Do not start new PR 4 work for broad aesthetic cleanup, unrelated rename churn,
or benchmark-specific score tuning. The next implementation focus should move
to PR 8 requirements/docs cleanup or PR 5 parser extraction unless a
calculation regression appears.

#### PR 4 Simplification Addendum

Status as of 2026-06-17: PR 4 was briefly reopened for deletion-oriented
simplification, not helper extraction.

- Removed runtime-dead `_preferred_complete_nested_numeric_narrative_answer`
  and its dedicated `_preserve_evidence_numeric_display` helper.
- Removed private-helper-only tests for that unused branch while preserving
  source-stated growth conflict coverage.
- Removed `_apply_mutable_numeric_answer` so its two call sites use the
  canonical `_apply_numeric_answer_to_aggregate_state` path directly.
- Removed runtime-dead `_narrative_summary_gap_is_satisfied` and its
  private-helper-only test.
- Removed the deleted helper's regex literal from the reviewed runtime
  domain-term audit baseline.
- Removed 7 thin wrapper shims that only forwarded to
  `calculation_rendering` / `financial_answer_slots` and had no remaining
  agent runtime callers.
- Removed `_replace_aggregate_final_answer` and `_replace_aggregate_results`
  as middle wrappers used only by mutable aggregate state helpers.
- Removed the unused `_render_grounded_operand_display` agent shim; the
  module-level rendering helper remains the active implementation.
- Result:
  - `src/agent/financial_graph_calculation.py`: `18,623` -> `18,296` lines.
  - Latest runtime-only diff: `3` deletions.
- Verification:
  - `python -m src.ops.audit_runtime_domain_terms`: passed
    (`215` reviewed literals).
  - `.venv/bin/python -m unittest tests.test_aggregate_subtask_projection tests.test_operation_contracts tests.test_subtask_loop tests.test_financial_calculation_execution tests.test_financial_calculation_rendering`:
    `507` OK.
  - `.venv/bin/python -m unittest tests.test_financial_answer_slots tests.test_financial_calculation_rendering tests.test_operation_contracts tests.test_subtask_loop tests.test_financial_calculation_execution`:
    `464` OK.
  - `.venv/bin/python -m unittest tests.test_runtime_domain_term_audit tests.test_subtask_loop tests.test_aggregate_subtask_projection tests.test_operation_contracts tests.test_financial_calculation_execution tests.test_financial_calculation_rendering`:
    `513` OK.
  - `.venv/bin/python -m unittest discover -s tests`: `1223` OK.
  - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
    `Status: ready`.
  - `git diff --check`: passed.

Further PR 4 work should use the same deletion-oriented rule: remove a dead or
duplicated patch path only when runtime callers, private-helper-only tests, and
review gates confirm the behavior is covered elsewhere. Do not count moving
code to another file as simplification.

#### PR 4 Post-Stop-Line Cleanup Addendum

Status as of 2026-06-18: a follow-up cleanup pass was completed after the
stop line, but only for duplicated runtime contracts and large nested patch
layers. It did not add domain terms or benchmark-specific runtime branches.

- Lookup recovery helpers moved into `src/agent/financial_lookup_recovery.py`.
- Artifact payload/provenance contract validators now live in
  `src/agent/financial_artifact_contracts.py`; `_project_task_artifact_trace()`
  consumes them as a ledger projection rule instead of owning the contract. The
  critic runtime acceptance contract also moved there, so contract code no
  longer depends on the MAS state/type module. Current reviewer/researcher ops
  import the contract owner directly; the experimental MAS type facade remains
  only as a compatibility export.
- Task/artifact ledger write helpers and caller-facing ledger projection helpers
  now live in `src/agent/financial_task_artifacts.py`; `financial_graph_helpers.py`
  keeps only the task-trace state projection aliases it still uses internally,
  while runtime, benchmark, MAS bridge, and focused ledger tests import the
  owner module directly. Ledger helpers are no longer part of the helper
  star-export surface, and unused ledger compatibility aliases were removed.
  `project_task_artifact_trace()` now delegates task/artifact view projection
  and integrity issue assembly to private owner-internal helpers.
- `financial_graph.py` now imports only its runtime projection helpers from
  `financial_graph_helpers.py`; contract tests and shadow ops scripts import
  private helper functions from the helper owner module directly instead of
  relying on the facade to re-export them.
- `financial_graph_evidence.py`, `financial_graph_planning.py`,
  `financial_graph_reconciliation.py`, and `financial_graph_calculation.py`
  now import their `financial_graph_helpers.py` dependencies explicitly instead
  of through the helper wildcard import.
- Aggregate answer projection callers now import
  `_preferred_complete_aggregate_subtask_answer()` from
  `financial_answer_projection.py`, the owner module, instead of indirectly
  through `financial_graph_helpers.py`.
- Shared runtime normalization/display primitives now live in
  `src/agent/financial_runtime_normalization.py`; extracted modules import
  text normalization, source-row-id cleanup, numeric parsing/unit
  normalization, compact KRW formatting, and display-label cleanup from that
  owner instead of the broad helper module.
- Restricted arithmetic formula evaluation now lives in
  `src/agent/financial_formula_eval.py`; calculation execution paths import
  `_safe_eval_formula()` from that owner instead of the broad helper module.
- Lazy LangChain prompt/parser construction helpers now live in
  `src/agent/financial_langchain_loaders.py`; calculation, evidence, planning,
  reconciliation, RAG, orchestrator, and researcher modules import that owner
  instead of repeating identical `ChatPromptTemplate`, `StrOutputParser`, and
  `RunnablePassthrough` loader helpers while preserving the import-time
  `langchain_core` boundary. Agent-runtime `Document` construction is also
  routed through the same loader owner, with `TYPE_CHECKING` annotations left
  as the only direct `langchain_core.documents` imports outside the owner.
- Lazy structured-output model loaders now live in
  `src/agent/financial_graph_model_loaders.py`; calculation, evidence,
  planning, reconciliation, runtime-trace, and answer-slot modules import that
  owner instead of repeating one-line `financial_graph_models` loaders while
  preserving the import-time Pydantic boundary; model resolution is cached after
  first use.
- Answer-slot operation assembly in `src/agent/financial_answer_slots.py` now
  keeps component grouping, lookup primary slot construction, and current/prior
  period slot construction in private owner-internal helpers. This leaves the
  public `build_answer_slots()` contract intact while making the projection
  owner easier to audit.
- Runtime trace construction/update, report-cache candidate projection,
  aggregate-subtask trace projection, structured-result compatibility
  projection, and `_resolve_runtime_calculation_trace()` now live in
  `src/agent/financial_runtime_trace.py`; runtime, ops, MAS, and focused tests
  import that owner directly instead of routing trace resolution through
  `financial_graph_helpers.py`. Aggregate-subtask calculation projection now
  delegates per-subtask row projection, source id rollup, and nested answer-slot
  subtask payload construction to private owner-internal helpers.
- Retrieval/statement hint helpers now live in
  `src/agent/financial_retrieval_hints.py`; evidence, reconciliation,
  planning, and focused hint tests import the hint owner directly instead of
  keeping section/retrieval policy resolution inside
  `financial_graph_helpers.py`.
- Operand surface-contract helpers now live in
  `src/agent/financial_surface_contracts.py`; calculation and evidence import
  positive/negative surface checks from that owner directly.
- Structured cell period/fiscal helpers now live in
  `src/agent/financial_structured_cells.py`; calculation, evidence,
  reconciliation, and focused contract tests import the period helper from that
  owner directly while the heavier structured-cell selector/scorer stays in
  `financial_graph_helpers.py`.
- Row/table text-surface helpers now live in
  `src/agent/financial_row_surfaces.py`; calculation, evidence,
  reconciliation, planning, and focused tests import operand needles,
  operand text matching, numeric-after-operand extraction, period-label
  stripping, surface-match variants, unstructured row parsing, and row-label
  extraction from narrow owners. Numeric-after-operand extraction now delegates
  parenthetical exact-value/unit handling and nearest prefix/suffix candidate
  collection to private owner-internal helpers. Broader reconciliation candidate
  scoring and binding still stays in `financial_graph_helpers.py`.
- Dependency projection slot-diff, lookup-slot scoring, source-task id,
  ratio-role grouping, source-slot acceptance, and source-value dedupe helpers
  now live in `src/agent/financial_dependency_projection.py`; calculation and
  focused projection tests import the dependency owner directly instead of
  routing those repair predicates through `financial_graph_helpers.py`.
  Dependency lookup-slot collection now delegates operation normalization,
  producer-task synthesis, answer-numeric context filling, and per-result slot
  selection to private owner-internal helpers.
- Lookup magnitude coercion and ontology lookup-hint resolution now live in
  `src/agent/financial_lookup_recovery.py`; planning, reconciliation,
  calculation, and focused operation tests import the lookup recovery owner
  directly instead of routing lookup normalization helpers through
  `financial_graph_helpers.py`. Lookup value-refinement acceptance now delegates
  scope gating, structured-surface checks, table-label precision acceptance, and
  same-unit refinement checks to private owner-internal helpers.
- Evidence candidate prioritization now lives locally in
  `src/agent/financial_graph_evidence.py`, and section-hint alias cleanup lives
  in `src/agent/financial_retrieval_hints.py`; evidence, reconciliation, and
  focused operation tests use those owners directly instead of routing
  retrieval/evidence shaping helpers through `financial_graph_helpers.py`.
- Operation-family percent-point policy helpers now live in
  `src/agent/financial_operation_policies.py`; evidence, reconciliation,
  calculation, and focused tests import that policy owner directly instead of
  depending on the broad helper module.
- Percent-metric label classification now also lives in
  `src/agent/financial_operation_policies.py`; reconciliation and focused
  operation tests import that owner directly instead of routing unit-family
  hints through `financial_graph_helpers.py`.
- Operation/query policy helpers for ratio-percent intent, narrative-context
  detection, single-metric period comparison, and direct numeric grounding now
  also live in `src/agent/financial_operation_policies.py`; planning,
  evidence, reconciliation, calculation, and focused tests import that owner
  directly.
- Report-scope and consolidation policy helpers now live in
  `src/agent/financial_scope_policies.py`; evidence, planning, calculation,
  rendering, and focused scope tests import that policy owner directly while
  broader reconciliation candidate binding stays in `financial_graph_helpers.py`.
- Slot-based difference answer rendering in
  `src/agent/financial_graph_calculation_rendering.py` now delegates nested
  aggregate-subtask difference lookup, prefix construction, and template
  rendering to private owner-internal helpers.
- Period/scope utilities for metadata period-match strength, period sort keys,
  and report-scope year extraction now also live in
  `src/agent/financial_scope_policies.py`; evidence and calculation import
  that owner directly, with the runtime domain-term audit baseline updated only
  for the regex/literal path move.
- Shared text-surface utilities for tokenization, sentence splitting, anchor
  cleanup, and rerank-metadata stripping now live in
  `src/agent/financial_text_surface.py`; evidence and calculation import the
  text owner directly, with the runtime domain-term audit baseline updated only
  for the regex path move.
- Shared numeric-surface extraction in `src/agent/financial_numeric_surface.py`
  now delegates mixed-currency extraction, numeric pattern construction, and
  per-match candidate classification to private owner-internal helpers.
- Evidence-only metric-term extraction and nearby-value extraction helpers now
  live locally in `src/agent/financial_graph_evidence.py`, removing another
  evidence-specific dependency from `financial_graph_helpers.py`.
- `financial_graph_helpers.py` also dropped unused owner-module imports left
  behind by the extraction pass, so imported primitives now reflect helpers
  used directly by the remaining planning/reconciliation code.
- `financial_task_artifacts.py` now keeps `__all__` limited to caller-facing
  ledger mutation/projection functions; runtime-trace internals still import
  the narrower helpers directly without making them star-exported API.

#### Current Local Split Plan

The current local cleanup diff is large enough that more extraction should stop
until it is split into reviewable units. The exact current file buckets,
minimum gates, and buildable split guidance are captured in
`docs/architecture/current_runtime_cleanup_split_manifest.md`.

The numbered buckets below are review-topic buckets, not an automatically
buildable file-only commit order. The current source diff has cross-bucket
imports: runtime projection call sites use new runtime trace/task-artifact and
primitive owner modules, task-trace owners use primitive normalization helpers,
and primitive call sites use task-artifact owners. For a buildable patch series,
either land `runtime_projection`, `task_trace`, and `primitive_owner` together
as one source cleanup change followed by a docs/audit change, or first partial
stage an owner-foundation commit containing only the new owner modules before
landing caller rewrites/removals by review topic.
The manifest includes the exact owner-foundation import gate and staging
command for that granular route.
The same manifest also records the import-time performance overlay: heavyweight
provider/router/LangGraph/prompt/parser/embedding dependencies are lazy-loaded
at runtime construction or LLM-chain/provider creation sites. The recorded
smoke reduced `src.agent.financial_graph` import from `3.807s` to `0.450s`,
kept MAS/RAG/storage imports mostly below `0.5s`, fixed `src.ops.evaluator`
package import path resolution, moved ops provider imports to execution
points, and preserved focused plus full unittest gates.
The follow-up import boundary pass also moved MAS graph construction,
debug-workflow parser/store imports, and retrospective ontology evaluator
helper imports to execution points; the recorded smoke keeps those debug/ops
module imports around `0.10s` while preserving their existing patch/test
surfaces.
The API entrypoint now follows the same boundary: `main.py` can import and
construct the FastAPI app without loading parser/vector-store/agent/fetcher
runtime components until lifespan initialization.
`src/api/financial_router.py` also no longer mutates `sys.path` at import time;
component construction still lazy-loads parser/store/fetcher/agent at FastAPI
lifespan initialization using package-qualified `src.*` imports.
A bounded ops bootstrap cleanup converted selected diagnostic/eval/smoke scripts
to package-qualified `src.*` imports and conditional project-root bootstrap only
for direct file execution; package imports for those touched scripts no longer
mutate `sys.path`.
A later deletion-only cleanup removed stale direct-run demo surfaces from
`src/agent/financial_graph.py`, `src/agent/rag_chain.py`,
`src/storage/vector_store.py`, `src/processing/financial_parser.py`, and
`src/processing/pdf_parser.py`. The same deletion-only rule was then applied to
`src/ingestion/dart_fetcher.py`, and its import-time `logging.basicConfig()`
side effect was removed. These were not default runtime, parser, search,
ingest, reviewer-gate, or README quick-review entry points; maintained
execution surfaces remain the documented `src.ops` commands and API/runtime
facades.

1. Runtime projection and legacy mirror cleanup.
   - Scope: remove stale top-level `calculation_*` mirror reads/writes from
     current runtime paths; keep public `FinancialAgent.run()` and historical
     replay compatibility at explicit projection boundaries.
   - Include the runtime trace projection tests and docs that describe the
     canonical `resolved_calculation_trace` contract.
   - Gate: focused runtime projection tests, then full unittest.

2. Task/artifact and trace owner extraction.
   - Scope: `financial_artifact_contracts.py`,
     `financial_task_artifacts.py`, `financial_runtime_trace.py`, and caller
     import rewrites in MAS/ops/tests.
   - Keep behavior unchanged; this is a boundary extraction for task ledger,
     critic acceptance, and trace projection contracts.
   - Gate: task artifact projection tests, MAS smoke tests that are already
     covered by unittest, portfolio review gates.

3. Shared primitive owner extraction.
   - Scope: runtime normalization/display, formula evaluation, text surface,
     numeric/row surface helpers, structured-cell period helpers, surface
     contracts, scope policies, operation policies, lookup recovery, dependency
     projection helpers, retrieval hints, and evidence-local prioritization.
   - Keep broader semantic planning and reconciliation scorer functions in
     `financial_graph_helpers.py` until they can be moved as coherent owner
     modules.
   - Gate: runtime domain-term audit, focused operation/reconciliation/evidence
     suites, full unittest.

4. Documentation and audit baseline reconciliation.
   - Scope: architecture/status/walkthrough docs and
     `runtime_domain_terms_baseline.json` moves that correspond only to file
     ownership changes.
   - Do not stage benchmark outputs, local stores, temporary profiles, or
     `benchmarks/results/**`.
   - Gate: `git diff --check`, runtime domain-term audit, artifact hygiene
     check via `git status --short`.

Stop line for the current local cleanup:

- Do not continue extracting semantic numeric planning or reconciliation scorer
  internals in this diff.
- Do not move functions only to reduce line count if the owner boundary is not
  clearer after the move.
- Do not introduce domain vocabulary in runtime code to compensate for any
  regression. Use ontology, retrieval policy, parser structure, or evidence
  schema instead.
- `financial_graph_helpers.py` no longer maintains a large private-helper
  `__all__` star-export list now that repo callers use explicit imports.
- `_refine_operand_precision_from_evidence_table()` now delegates contextual
  note-row and flattened-table-surface cell recovery to named helpers.
- `_extract_calculation_operands()` now publishes operand-set artifacts through
  `_operand_set_artifact_update()` instead of repeating task/artifact ledger
  publication in three branches.
- `_extract_numeric_value_after_operand_text()` now delegates parenthetical
  exact-value/unit handling and nearest prefix/suffix candidate collection to
  owner-internal helpers in `financial_row_surfaces.py`.
- `realign_lookup_row_from_dependency_projection()` now delegates required
  operand selection, projection candidate/source validation, and updated
  slot/result construction to owner-internal helpers in
  `financial_dependency_projection.py`.
- `fill_missing_ratio_dependency_operands()` now delegates present-group
  detection, inferred denominator requirement synthesis, operand seed
  construction, source-slot recovery, table-evidence recovery, and source-value
  dedupe to owner-internal helpers in `financial_dependency_projection.py`.
- `build_answer_slots()` now delegates period-comparison detection,
  current/prior/delta slot assembly, and difference direction projection to
  owner-internal helpers in `financial_answer_slots.py`.
- `benchmark_contextual_ingest()` and `contextual_ingest()` now share
  contextual batch generation, response/fallback handling, index-payload
  construction, and usage metric collection helpers in
  `financial_graph_contextual.py`.

Measured cleanup:

- `_project_task_artifact_trace()`: `501` -> `78` lines, nested helpers
  `5` -> `0`, with task/artifact view projection and integrity issue assembly
  moved to private helpers inside `financial_task_artifacts.py`.
- `_refine_operand_precision_from_evidence_table()`: `567` -> `258` lines,
  nested helpers `2` -> `0`.
- `_extract_calculation_operands()`: `1196` -> `1139` lines.
- `_build_aggregate_calculation_projection()`: `159` -> `59` lines, with
  per-subtask projection, aggregate source id rollup, and answer-slot subtask
  payload construction moved to private helpers inside `financial_runtime_trace.py`.
- `build_dependency_lookup_slots_by_task()`: `100` -> `32` lines, with
  operation normalization, producer-task synthesis, answer-numeric context, and
  per-result lookup-slot selection moved to private helpers inside
  `financial_dependency_projection.py`.
- `compose_slot_based_difference_answer()`: `103` -> `69` lines, with nested
  difference-result lookup, prefix construction, and template rendering moved
  to private helpers inside `financial_graph_calculation_rendering.py`.
- `lookup_recovery_value_refinement_allowed()`: `120` -> `47` lines, with
  scope gating, structured-surface checks, table-label precision acceptance, and
  same-unit refinement checks moved to private helpers inside
  `financial_lookup_recovery.py`.
- `extract_numeric_surface_candidates()`: `101` -> `28` lines, with
  mixed-currency extraction, numeric pattern construction, and per-match
  candidate classification moved to private helpers inside
  `financial_numeric_surface.py`.
- `_extract_numeric_value_after_operand_text()`: `107` -> `16` lines, with
  parenthetical exact-value/unit handling and nearest prefix/suffix candidate
  collection moved to private helpers inside `financial_row_surfaces.py`.
- `realign_lookup_row_from_dependency_projection()`: `138` -> `66` lines,
  with required operand selection, projection candidate/source validation, and
  updated slot/result construction moved to private helpers inside
  `financial_dependency_projection.py`.
- `fill_missing_ratio_dependency_operands()`: `129` -> `52` lines, with
  present-group detection, inferred denominator requirement synthesis, operand
  seed construction, source-slot recovery, table-evidence recovery, and
  source-value dedupe moved to private helpers inside
  `financial_dependency_projection.py`.
- `build_answer_slots()`: `210` -> `96` lines, with component grouping, lookup
  primary, period-value slot assembly, period-comparison detection,
  current/prior/delta slot assembly, and difference direction projection moved
  to private helpers inside the same owner module.
- `benchmark_contextual_ingest()`: `115` -> `80` lines, with contextual batch
  generation, response/fallback handling, index-payload construction, and usage
  metric collection shared with `contextual_ingest()` through private helpers in
  `financial_graph_contextual.py`.
- stale direct-run demos: removed from `src/agent/financial_graph.py`,
  `src/agent/rag_chain.py`, `src/storage/vector_store.py`,
  `src/processing/financial_parser.py`, `src/processing/pdf_parser.py`, and
  `src/ingestion/dart_fetcher.py`; `dart_fetcher.py` also no longer configures
  root logging during import.

Validation:

- targeted operand/ledger/subtask suites: `479` OK
- full unittest discovery: `1248` OK
- runtime domain-term audit: passed with `215` reviewed literals
- latest row-surface helper extraction validation:
  - focused operation/semantic numeric suite: `324` OK
  - broader projection/subtask/aggregate suite: `464` OK
  - full unittest discovery: `1324` OK, `full_elapsed=13.985`
  - runtime domain-term audit: passed with `215` reviewed literals
  - source-wide import smoke: `modules=112`, `failures=0`,
    `slow_ge_0_05=1`
- latest dependency realignment helper extraction validation:
  - focused operation/subtask/aggregate suite: `550` OK
  - broader projection/evaluator suite: `238` OK
  - full unittest discovery: `1324` OK, `full_elapsed=14.240`
  - runtime domain-term audit: passed with `215` reviewed literals
  - source-wide import smoke: `modules=112`, `failures=0`,
    `slow_ge_0_05=1`
- latest ratio dependency helper extraction validation:
  - focused operation/subtask/aggregate suite: `550` OK
  - broader projection/evaluator suite: `238` OK
  - full unittest discovery: `1324` OK, `full_elapsed=13.960`
  - runtime domain-term audit: passed with `215` reviewed literals
  - source-wide import smoke: `modules=112`, `failures=0`,
    `slow_ge_0_05=1`
- latest answer-slot period helper extraction validation:
  - focused answer-slot/calculation suite: `493` OK
  - broader projection/evaluator suite: `238` OK
  - full unittest discovery: `1324` OK, `full_elapsed=14.440`
  - runtime domain-term audit: passed with `215` reviewed literals
  - source-wide import smoke: `modules=112`, `failures=0`,
    `slow_ge_0_05=1`
- latest contextual ingest helper extraction validation:
  - direct contextual ingest smoke: passed
  - focused benchmark/import/agent projection suite: `86` OK
  - broader evaluator/structured/semantic projection suite: `169` OK
  - full unittest discovery: `1324` OK, `full_elapsed=13.898`
  - runtime domain-term audit: passed with `215` reviewed literals
  - source-wide import smoke: `modules=112`, `failures=0`,
    `slow_ge_0_05=1`
- latest pushed commit for this cleanup sequence: `9de3c16`
- latest local trace-owner cleanup validation:
  - focused evidence/retrieval/structured extraction suite: `382` OK
  - focused trace projection suite: `346` OK
  - full unittest discovery: `1273` OK
  - runtime domain-term audit: passed with `215` reviewed literals
  - portfolio review gates: `Status: ready`
- latest direct-run demo deletion validation:
  - `python3 -m py_compile src/storage/vector_store.py src/agent/financial_graph.py src/agent/rag_chain.py src/ingestion/dart_fetcher.py src/processing/financial_parser.py src/processing/pdf_parser.py`:
    passed across the touched direct-run cleanup files
  - `python3 -m unittest tests.test_financial_parser tests.test_vector_store_fallback tests.test_financial_agent_run_projection`:
    `103` OK
  - `python3 -m unittest tests.test_resumable_ingest tests.test_generate_grounded_answer_drafts tests.test_financial_router_response`:
    `28` OK
  - direct import smoke:
    `src.agent.rag_chain import_elapsed=0.026`,
    `src.processing.financial_parser import_elapsed=0.063`,
    `src.processing.pdf_parser import_elapsed=0.000`,
    `src.storage.vector_store import_elapsed=0.016`,
    `src.agent.financial_graph import_elapsed=0.041`,
    `src.ingestion.dart_fetcher import_elapsed=0.126`,
    `root_logging_level_changed=False`
  - non-ops direct-run scan: no `if __name__ == "__main__"` demo surfaces
    remain under `src/agent`, `src/api`, `src/ingestion`, `src/storage`,
    `src/processing`, or `src/routing`
  - combined agent/ops/routing/storage/processing import smoke: `modules=101`,
    `failures=0`, `slow_ge_0_20=0`
  - combined agent/api/ingestion/ops/routing/storage/processing import smoke:
    `modules=103`, `failures=0`, `slow_ge_0_20=0`,
    `logging_level_changes=0`; after completing the bounded ops bootstrap
    cleanup, latest combined package import smoke reports `modules=111`,
    `failures=0`, `slow_ge_0_20=0`, `logging_level_changes=0`, and
    `syspath_changes=0`
  - API import side-effect check:
    `src.api.financial_router import_elapsed=0.211/0.245/0.210`,
    `syspath_changed=False`
  - `python3 -m unittest tests.test_financial_router_response`: `3` OK
  - touched ops direct `--help` smoke: passed across the diagnostic, eval,
    smoke, rebuild, retrospective, and replay CLI files changed in the bounded
    bootstrap pass
  - focused ops/bootstrap suite:
    `python3 -m unittest tests.test_mas_direct_worker_probe tests.test_ops_runtime_projection_modes tests.test_run_eval_only tests.test_benchmark_runner_runtime_projection tests.test_benchmark_fanout_cost_audit tests.test_report_cache_index_smoke_contract`:
    `45` OK
  - focused final ops/bootstrap repeat:
    `python3 -m unittest tests.test_run_eval_only tests.test_benchmark_runner_runtime_projection tests.test_ops_runtime_projection_modes`:
    `34` OK
  - full unittest discovery: `1284` OK, `full_elapsed=6.178`
  - final full unittest repeat after completing ops direct-run bootstrap
    cleanup: `python3 -m unittest discover -s tests`: `1284` OK,
    `full_elapsed=6.716`
  - runtime domain-term audit: passed with `215` reviewed literals
- current local split/import cleanup also keeps API and store-fixed eval entry
  points lazy, including `src.ops.benchmark_runner` and
  `src.ops.generate_grounded_answer_drafts`; `src.ops.evaluator` now keeps
  MLflow and vector-store embedding imports at evaluation execution points.
  Latest full unittest discovery: `1284` OK.

Continue from here only for similarly concrete duplication or contract seams,
especially `_extract_calculation_operands()` fallback assembly. Do not reopen
PR 4 for broad file-size reduction or cosmetic helper moves.

### PR 5: Parser Extraction

Keep `FinancialParser.process_document()` as the public facade. Move XML loading,
section extraction, table reconstruction, value record construction, chunking,
and reference resolution behind that facade.

Add or preserve metadata snapshot tests because table/value-record drift can
change retrieval behavior.

#### PR 5 Current Status

Status as of 2026-06-17: PR 5 is functionally complete enough to pause. The
main parser facade remains `FinancialParser.process_document()`, while the
largest parser responsibilities now sit behind focused modules.

- Added `src/processing/table_records.py` for parser-normalized table row/value
  record construction.
- `FinancialParser._build_table_row_records()` and
  `FinancialParser._build_table_value_records()` remain as compatibility
  wrappers behind the `FinancialParser.process_document()` facade.
- Generic table-axis, period-label, aggregate-role, row-record, and value-record
  helpers now live in the parser table-record module instead of the main parser
  facade.
- Added `src/processing/table_structure.py` for XML table grid reconstruction,
  merged-cell propagation, table text formatting, span detection, row-label
  extraction, and table-object payload assembly.
- `FinancialParser._cell_span_int()`, `_normalize_table_grid()`,
  `_format_table_grid()`, `_table_has_spans()`,
  `_extract_table_row_labels_from_grid()`, `_build_table_object()`, and
  `_grid_row_to_text()` remain compatibility wrappers.
- Added `src/processing/section_extraction.py` for section tag iteration,
  section path construction, parse budget/fallback orchestration, parse timing,
  and section payload assembly.
- `FinancialParser._build_section_path()` and `_extract_sections()` remain
  compatibility wrappers.
- Added `src/processing/block_collection.py` for the paragraph/table/local
  heading block state machine. `FinancialParser._collect_blocks()` remains as a
  compatibility wrapper that wires parser-specific callbacks into the extracted
  collector.
- Added `src/processing/chunking.py` for table row/window splitting, narrative
  table-row splitting, wide-table column windows, table metadata propagation,
  and section block chunk assembly.
- `FinancialParser._split_table_by_rows()`, `_looks_like_table_header_row()`,
  `_split_table_text_fragment()`, `_split_long_table_row()`,
  `_split_wide_table_by_columns()`, `_split_table_for_chunks()`, and
  `_chunk_blocks()` remain compatibility wrappers.
- Added `src/processing/reference_resolution.py` for quoted intra-filing
  reference hint canonicalization, reference index construction, and section
  path resolution.
- `_build_reference_index()` and `_extract_reference_section_paths()` remain
  local wrappers for parser assembly/tests. Obsolete pass-through wrappers for
  reference text canonicalization and direct path resolution were removed once
  no runtime or contract test callers remained.
- Verification:
  - `uv run --with-requirements requirements-review.txt python -m unittest tests.test_financial_parser`:
    `28` OK
  - `.venv/bin/python -m unittest tests.test_vector_store_fallback`:
    `14` OK
  - `python -m py_compile src/processing/financial_parser.py src/processing/table_records.py src/processing/table_structure.py src/processing/section_extraction.py src/processing/block_collection.py src/processing/chunking.py src/processing/reference_resolution.py`:
    passed
  - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
    `Status: ready`
  - `git diff --check`: passed

Stop line: do not continue splitting `financial_parser.py` merely to reduce
file size. Continue PR 5 only when a concrete parser regression or metadata
snapshot drift points to one of these specific seams:

- XML loading and parser input normalization
- parser configuration/value defaults that need a typed boundary
- remaining small helpers that can move without changing metadata schema
- removal of compatibility wrappers after callers no longer depend on them

The next implementation focus should move to PR 6 vector store extraction unless
a parser-specific bug appears.

### PR 6: Vector Store Extraction

Keep `VectorStoreManager.search()` public behavior stable. Move embedding
provider selection, Chroma access, BM25, hybrid merge, structure graph expansion,
and metadata sidecars behind smaller internal modules.

Search telemetry keys should remain stable.

#### PR 6 Current Status

Status as of 2026-06-17: PR 6 has started with a no-behavior-change extraction
behind the `VectorStoreManager` facade.

- Added `src/storage/embedding_config.py` for embedding provider selection,
  default model selection, known dimension lookup, runtime spec construction,
  and embedding factory creation.
- Preserved the existing `src.storage.vector_store` import surface for
  `DEFAULT_EMBEDDING_PROVIDER`, `DEFAULT_EMBEDDING_MODEL`,
  `create_embeddings`, `get_embedding_runtime_spec`,
  `infer_embedding_dimension`, and `_select_default_embedding_provider`.
- Added `src/storage/metadata_payloads.py` for Chroma metadata sanitization,
  table payload sidecar id/stats/load, metadata hydration, and compact node
  storage helpers.
- Preserved the existing metadata/payload helper surface in
  `src.storage.vector_store` through compatibility wrappers.
- Added `src/storage/bm25_index.py` for Korean/ASCII tokenization, metadata
  filter matching, BM25 index construction, and BM25 candidate collection.
- Preserved the existing BM25 helper surface in `src.storage.vector_store`
  through compatibility wrappers.
- Added `src/storage/structure_graph.py` for structure graph payload
  normalization, BM25 payload projection, vector result hydration,
  relationship rebuild/update, indexed chunk uid lookup, and graph accessor
  document creation.
- Preserved the existing structure graph helper/accessor surface in
  `src.storage.vector_store` through compatibility wrappers.
- Added `src/storage/chroma_backend.py` for lazy Chroma class access, vector
  index probing, and Chroma/vector exception classification.
- Preserved the existing `src.storage.vector_store` Chroma/error helper surface
  through compatibility wrappers.
- Added `src/storage/search_merge.py` for search result identity, stable search
  cache keys, and RRF result merging.
- Preserved the existing `src.storage.vector_store` search identity/cache helper
  surface through compatibility wrappers.
- Added `src/storage/document_batches.py` for add-document input preparation,
  resume lookup scoping, pending filtering, and batch slicing helpers.
- `VectorStoreManager.add_documents()` now delegates empty/no-pending result
  projection, BM25-only vector-skip updates, retrying vector batch writes, and
  per-batch graph/progress accounting to private owner-internal helpers.
- Added `src/storage/parent_store.py` for parent chunk JSON load/save, lookup,
  merge, and receipt-scoped deletion helpers without changing `parents.json`
  artifacts.
- Added `src/storage/graph_persistence.py` for structure graph JSON load/save
  and table payload sidecar persistence without changing
  `document_structure_graph.json` or `table_payloads.json` artifacts.
- `VectorStoreManager.search()` behavior and telemetry keys are unchanged.
- Verification:
  - `.venv/bin/python -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config`:
    `18` OK
  - `python -m py_compile src/storage/vector_store.py src/storage/embedding_config.py src/storage/metadata_payloads.py src/storage/bm25_index.py src/storage/structure_graph.py`:
    passed
  - `python3 -m py_compile src/storage/chroma_backend.py src/storage/vector_store.py`:
    passed
  - `python3 -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config tests.test_resumable_ingest tests.test_rebuild_vector_store`:
    `44` OK
  - `python3 -m py_compile src/storage/search_merge.py src/storage/vector_store.py`:
    passed
  - `python3 -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config tests.test_resumable_ingest tests.test_rebuild_vector_store`:
    `46` OK
  - `python3 -m py_compile src/storage/document_batches.py src/storage/vector_store.py`:
    passed
  - `python3 -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config tests.test_resumable_ingest tests.test_rebuild_vector_store`:
    `48` OK
  - `python3 -m py_compile src/storage/parent_store.py src/storage/vector_store.py`:
    passed
  - `python3 -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config tests.test_resumable_ingest tests.test_rebuild_vector_store`:
    `49` OK
  - `python3 -m py_compile src/storage/graph_persistence.py src/storage/vector_store.py`:
    passed
  - `python3 -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config tests.test_resumable_ingest tests.test_rebuild_vector_store`:
    `50` OK
  - latest add-document runtime-path split:
    `python3 -m py_compile src/storage/document_batches.py src/storage/vector_store.py`:
    passed
  - latest focused storage gate:
    `python3 -m unittest tests.test_vector_store_fallback tests.test_resumable_ingest tests.test_rebuild_vector_store`:
    `46` OK
  - latest broader ingest/eval gate:
    `python3 -m unittest tests.test_benchmark_runner_runtime_projection tests.test_run_eval_only tests.test_embedding_runtime_config tests.test_financial_parser`:
    `52` OK
  - latest full unittest discovery: `1324` OK, `full_elapsed=13.522`
  - latest runtime domain-term audit: passed with `215` reviewed literals
  - latest source-wide import smoke: `modules=112`, `failures=0`,
    `slow_ge_0_05=1`
  - combined agent/ops/routing/storage/processing import smoke:
    `modules=97`, `failures=0`, `slow_ge_0_20=0`
  - `git diff --check`: passed

Stop line: do not continue splitting `vector_store.py` merely to reduce file
size. Continue PR 6 only when a concrete vector-store bug or telemetry contract
gap points to one of these specific seams:

- Chroma access/probe wrappers
- hybrid merge and result identity helpers
- `add_documents` preparation/batching helpers
- remaining persistence helpers that can move without changing store artifacts

Do not combine these extractions with retrieval behavior tuning.

### PR 7: MAS Isolation

Move MAS code under `experimental/mas` and keep compatibility shims only where
needed. Documentation should describe MAS as an experimental wrapper around the
core financial runtime, not as the default product engine.

#### PR 7 Current Status

Status as of 2026-06-17: PR 7 has started with a no-behavior-change import
boundary.

- Added `src/experimental/mas/` as the experimental namespace for MAS graph,
  typed state, and node factories.
- Existing `src.agent.mas_graph`, `src.agent.mas_types`, and
  `src.agent.nodes.*` implementation/import paths remain compatibility
  surfaces. Files have not moved yet.
- Added `tests/test_experimental_mas_namespace.py` to pin re-export
  compatibility and dummy MAS graph execution through the experimental
  namespace.
- Migrated public MAS imports in ops smoke/review scripts to
  `src.experimental.mas`.
- Kept `mas_direct_worker_probe.py` Researcher private diagnostic helper imports
  on the legacy implementation path to avoid widening the public facade
  prematurely.
- Migrated public MAS graph/type/node factory imports in focused MAS tests to
  `src.experimental.mas`.
- Legacy test imports remain only for compatibility assertions and
  implementation-private helper/constant tests.
- Added `src.experimental.mas.diagnostics` for MAS worker-probe Researcher
  diagnostic helpers, and moved `src/ops/mas_direct_worker_probe.py` off direct
  `src.agent.nodes.researcher_node` private-helper imports.
- Diagnostic helpers are not re-exported by top-level `src.experimental.mas`;
  callers must opt into the diagnostic module explicitly.
- Extended the no-behavior-change import boundary across ops CLI/MAS smoke
  scripts so parser/vector-store/MAS runtime construction happens at execution
  points, not during module import.
- Extended the same boundary to storage/evaluator imports: Chroma backend
  construction and evaluator trace/numeric-surface helpers now load at runtime
  use sites.
- Extended the boundary to processing parsers: text splitter and PDF extraction
  backends now load when parser instances split/extract content, not during
  parser module import.
- Full caller import scan result:
  - New public/ops/test callers use `src.experimental.mas`.
  - `src.experimental.mas.*` modules intentionally bridge to the current
    `src.agent.*` implementation while files remain unmoved.
  - `tests/test_experimental_mas_namespace.py` keeps legacy imports only for
    compatibility identity assertions.
  - Focused node tests keep legacy imports only for implementation-private
    constants/helpers.
  - `src.agent.*` internal imports remain implementation dependencies.
- Compatibility shim strategy:
  - Keep `src.agent.multi_agent_graph` and `src.agent.nodes.__init__` as
    compatibility surfaces for earlier imports.
  - Keep `src.agent.mas_graph`, `src.agent.mas_types`, and
    `src.agent.nodes.*` as implementation files for now, not redirect shims.
  - Do not move implementation files unless a later PR demonstrates a concrete
    maintenance benefit and preserves compatibility tests.
- Verification:
  - `.venv/bin/python -m unittest tests.test_experimental_mas_namespace tests.test_multi_agent_graph tests.test_analyst_node tests.test_researcher_node tests.test_critic_node tests.test_orchestrator_node`:
    `36` OK
  - `.venv/bin/python -m unittest tests.test_experimental_mas_namespace tests.test_mas_e2e_smoke tests.test_mas_direct_worker_probe tests.test_mas_e2e_smoke_contract tests.test_mas_researcher_smoke_contract tests.test_portfolio_demo`:
    `31` OK
  - `python -m py_compile src/experimental/__init__.py src/experimental/mas/__init__.py src/experimental/mas/graph.py src/experimental/mas/nodes.py src/experimental/mas/types.py src/experimental/mas/diagnostics.py`:
    passed
  - `python -m py_compile src/ops/portfolio_demo.py src/ops/mas_analyst_smoke.py src/ops/mas_researcher_smoke.py src/ops/mas_e2e_smoke.py src/ops/mas_direct_worker_probe.py`:
    passed
  - full `src.ops` package import smoke:
    `modules=42`, `failures=0`, `slow_ge_0_20=0`
  - combined agent/ops/routing/storage import smoke:
    `modules=88`, `failures=0`, `slow_ge_0_20=0`
  - combined agent/ops/routing/storage/processing import smoke:
    `modules=96`, `failures=0`, `slow_ge_0_20=0`; latest repeat after
    structure graph persistence extraction: `modules=101`, `failures=0`,
    `slow_ge_0_20=0`
  - `python3 -m unittest tests.test_mas_researcher_smoke_contract tests.test_mas_e2e_smoke tests.test_mas_e2e_smoke_contract tests.test_mas_direct_worker_probe`:
    `24` OK
  - `python3 -m unittest tests.test_vector_store_fallback tests.test_resumable_ingest tests.test_rebuild_vector_store tests.test_embedding_runtime_config tests.test_embedding_usage tests.test_run_eval_only`:
    `51` OK
  - `python3 -m unittest tests.test_evaluator_runtime_projection tests.test_evaluator_progress tests.test_ops_runtime_projection_modes`:
    `82` OK
  - `python3 -m unittest tests.test_financial_parser`:
    `30` OK
  - `python3 -m unittest discover -s tests`:
    `1277` OK; latest repeat after structure graph persistence extraction:
    `1284` OK, `full_elapsed=6.774`
  - `python -m py_compile tests/test_analyst_node.py tests/test_researcher_node.py tests/test_critic_node.py tests/test_orchestrator_node.py tests/test_multi_agent_graph.py`:
    passed
  - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
    ready
  - `python -m src.ops.audit_runtime_domain_terms`:
    passed
  - `git diff --check`: passed

Next PR 7 seam should remain no-behavior-change. Do not move implementation
files by default; either reassess whether the move is still useful, or switch to
PR 8 requirements/docs cleanup.

### PR 8: Requirements And Docs Cleanup

Split dependencies or introduce extras so core, API, ingest, eval, dev, and UI
dependencies are not all presented as one default install surface.

Simplify reviewer-facing docs and move stale benchmark or retrospective material
to appendix/internal locations.

#### PR 8 Current Status

Status as of 2026-06-17: PR 8 has a lightweight reviewer profile and a full
development profile.

- `requirements-review.txt` is the quick review profile for fixture-backed
  demo/gate commands.
- `requirements.txt` is documented as the full development / ingest /
  benchmark / app dependency lock.
- README representative checks are split into lightweight reviewer commands,
  capability-specific gates, and full development commands.
- README quick review path now references command names and keeps executable
  reviewer command strings in the representative-checks block only.
- `docs/README.md` documents the dependency profile boundary.
- `docs/overview/portfolio_one_pager.md` now links to README for reviewer
  commands instead of duplicating the command block.
- `docs/overview/portfolio_one_pager.md` no longer carries a stale exact full
  unittest count; latest counts live in `project_status.md` and the current
  cleanup manifest.
- `docs/README.md` separates the core 5-document reviewer path from optional
  interview/resume deliverables.
- Verification:
  - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_demo --format json`:
    `ready`
  - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
    `Status: ready`
  - `requirements.txt` and `requirements-review.txt` parsed via
    `packaging.requirements.Requirement`
  - reviewer-facing doc local link check:
    passed; latest repeat checked `49` local markdown links with `0` missing
  - reviewer-facing stale test-count search:
    no matches for `1223` or `latest full unittest discovery passed`
  - `git diff --check`: passed
- Next PR 8 seam should stay docs-only unless a command actually needs a new
  dependency profile. Prefer closing PR 8 with a stop-line before final
  portfolio review.

## Deletion Criteria

Before deleting or archiving a module, answer these questions:

1. Is it required by the default `FinancialAgent.run()` query path?
2. Is it required by `FinancialParser.process_document()`?
3. Is it required by `VectorStoreManager.search()`?
4. Is it required to create `structured_result` or
   `resolved_calculation_trace`?
5. Is it required by `portfolio_review_gates` or README quick review commands?
6. Is it current evidence for a reviewer-facing project claim?

If all answers are "no", it is a candidate for deletion or archive. If any
answer is "yes", move or isolate it before deleting.

## First Files To Touch

Prefer starting with:

- `src/agent/financial_graph.py`
- `src/agent/financial_graph_models.py`
- `src/agent/financial_graph_calculation.py`
- `src/processing/financial_parser.py`
- `src/storage/vector_store.py`
- `src/api/financial_router.py`

Prefer touching later:

- `benchmarks/results/**`
- `docs/history/**`
- `docs/evaluation/benchmarking.md`
- `src/ops/**`

Core boundaries should be established before ops and evaluation surfaces are
reshaped.
