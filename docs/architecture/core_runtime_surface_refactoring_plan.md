# Core Runtime Surface Refactoring Plan

Last revised: 2026-08-10

This is the active boundary and phased plan for reducing repository complexity
while preserving verified financial QA behavior. Detailed chronology lives in
Git history, `docs/history/implementation_history.md`, and
`docs/history/experiment_history.md`; `docs/overview/project_status.md`
contains current state and is the sole authority for next-work priority.

`docs/architecture/agent_runtime_contract.md` remains authoritative for runtime
behavior. Update both documents if a structural change alters that contract.

## Portfolio outcome

The repository should communicate one product claim:

> Retrieve numeric evidence from DART filings, use an LLM to plan the required
> calculation, execute it deterministically, and return a provenance-validated
> answer with an inspectable trace.

The default path should be understandable in about ten minutes:

```text
main.py -> financial_router.py -> FinancialAgent.run()
  -> semantic plan
  -> hybrid retrieval and structural rerank
  -> evidence and operand binding
  -> deterministic formula execution
  -> answer, structured_result, resolved_calculation_trace
```

Multi-agent orchestration is an experiment around this runtime. It is not the
default product engine and must not dominate reviewer-facing documentation.

## Surface classification

### Core

Core code is required by the default user path:

- FastAPI boundary and `FinancialAgent.run()` facade
- DART parsing, chunking, and structural metadata
- embedding configuration, Chroma, BM25, and structure storage
- query planning, retrieval, reranking, evidence selection, and reconciliation
- operand binding, deterministic execution, rendering, and verification
- `answer_slots`, `structured_result`, `resolved_calculation_trace`, citations,
  and `retrieval_debug_trace`
- ontology, retrieval policy, and runtime config consumed by those paths

Core runtime code may not import evaluator, benchmark, portfolio-review, MAS,
or cache-promotion implementations.

### Evaluation

Evaluation proves core behavior but is not part of request execution:

- evaluator and benchmark runner
- focused profiles and regression fixtures
- portfolio and capability gates
- experiment reports and reproducibility logs

Evaluation may consume public core contracts. Core must never depend on
evaluation normalization or score rules.

### Experimental and internal

These surfaces remain opt-in and outside the default product story:

- `src/experimental/mas/`
- disabled query-time graph-expansion variants
- report-cache and reflection promotion workflows
- diagnostic probes, smoke commands, and retrospective scripts

Keep an explicit import boundary. A feature that is disabled by default does
not justify extra state fields or imports in the core request path unless the
runtime contract requires them.

### Legacy compatibility

Legacy code includes old import paths, flat response mirrors, stale aliases,
callerless wrappers, and test-only production helpers. It is temporary, not a
fourth architecture layer.

Every compatibility surface must have:

1. a known caller;
2. a canonical replacement;
3. a removal condition;
4. a contract test only when external compatibility is still required.

If no caller remains, delete the surface and its private-helper-only test in the
same change.

## Refactoring rules

1. Preserve behavior before changing behavior. Do not mix owner extraction with
   retrieval tuning or benchmark repair.
2. Move implementation to an actual owner. A new facade that merely adds
   another forwarding layer is not progress.
3. Delete duplicated or callerless surfaces after migration. File splitting
   without caller migration does not reduce the conceptual surface.
4. Keep one canonical answer and calculation trace. Compatibility mirrors may
   read from them but may not override them.
5. Keep domain vocabulary in ontology, policy, config, or documented data.
6. Keep LLM semantics separate from deterministic execution and validation.
7. Keep benchmark artifacts, local stores, and caches out of source changes.

## Execution sequence

### Phase 0: Correctness prerequisites

Status: completed on 2026-07-22.

Close correctness gaps that would be hidden by structural work:

- numeric evidence equivalence must preserve sign;
- final-answer numeric backfill must select provenance using value, label, and
  period compatibility rather than numeric equality and list order alone.

Required proof: small contract tests, runtime-domain-term audit, and full unit
test discovery. No fresh benchmark ingest is required for these projection-only
changes.

### Phase 1: Reviewer-facing repositioning

Status: completed on 2026-07-22 for README, portfolio one-pager, project status,
and this execution plan. Follow-up reviewer documents should adopt the same
boundary when they are next touched.

- Make `DART Financial Agentic RAG` the primary name and story.
- Show the single-agent pipeline before optional capabilities.
- Keep the first-read path to README, one-pager, one trace walkthrough, one
  experiment report, and technical highlights.
- Move MAS, cache promotion, reflection promotion, and internal gates to an
  optional/experimental section.
- State benchmark limitations next to quantitative claims.

Completion condition: a reviewer can identify the problem, core pipeline,
representative result, and demo command without reading internal status logs.

### Phase 2: Give retrieval one owner

Status: completed on 2026-07-22 as a no-behavior-change owner extraction.

- `_retrieve`, query/filter construction, reranking, candidate selection, and
  trace projection now live in `financial_retrieval_pipeline.py`.
- Retrieval-only module helpers moved with the implementation; evidence imports
  only the shared lookup/evidence helpers it still consumes.
- `FinancialAgentEvidenceMixin` no longer defines `_retrieve` or reranking.
- Focused owner/scope/query/import tests cover the new boundary.
- Full unittest discovery passes with `1349` tests.

Create `src/agent/financial_retrieval_pipeline.py` as the implementation owner
for:

- retrieval query bundle assembly;
- metadata filter construction;
- dense/BM25 execution and reuse;
- deterministic structural reranking;
- visible and seed candidate selection;
- `retrieval_debug_trace` construction.

`financial_graph_evidence.py` should retain evidence construction, evidence
preservation, narrative support, and final evidence validation. Its `_retrieve`
node may delegate to the retrieval owner, but it must not keep a second copy of
the pipeline.

Completion conditions:

- one retrieval implementation owner;
- unchanged graph node contract and debug trace schema;
- focused retrieval tests import or exercise the new owner;
- no retrieval behavior tuning in the extraction change;
- old implementation deleted after caller migration.

### Phase 3: Converge on one calculation path

Status: in progress. The July canonical public-projection milestone is complete:
legacy flat mirrors cannot override `agent_answer` or the resolved trace. The
broader single-calculation-path phase is not complete.

Current calculation ownership is:

- `financial_graph_calculation.py` remains the graph-state adapter and
  orchestrator. It constructs and coerces direct rows, applies consolidation
  scope and target-override policy, prepares evidence/query inputs, builds
  required candidates, applies dependency producer-scope filtering, and invokes
  the coherent-context builder lazily. It also owns direct structured preference
  preparation through runtime evidence overlay, row iteration, peer-unit
  preparation, strongest-slot building, query/report-scope score augmentation,
  ambiguity/tie-break policy and sequential adoption, direct target-metric
  fallback construction/evidence coercion/scope gating plus target adoption and
  evidence append around the owner conflict call, recovered-context
  eligibility, document/evidence and context-row builders, recovery logging and
  ratio-recovered flag projection, retry gates,
  post-coercion LLM invocation, evidence/scope/id/coercion/applicability and
  exception/fallback orchestration, graph-private candidate preparation,
  required-operand/evidence preparation and direct-grounding computation around
  the unconditional prose numeric-evidence filter call, narrative/restriction
  gates, surface-result merge/dedupe/logging and later fallback-row merge,
  state/task/artifact projection, prepared reconciliation-reference owner inputs
  and its two call placements, operand-set artifact and integrity/replan consumers,
  repair acceptance, aggregate/filter
  sequencing, recalculated ratio-value coercion, dependency candidate-input
  construction/execution, absolute-ratio query/transform invocation,
  task-artifact/ledger conflict short-circuit and formatting, collapsed-ratio
  trace/eligibility/completeness/query gates and prepared-copy
  construction, downstream coherence/answer/coverage/final projection,
  dependency-row construction, stateful structured-provenance lookup and
  downstream evidence coercion/append, dependency-coherence source-slot/candidate/
  marked-row preparation, source-task/material/anchor-projection gates, rank and
  ratio-scope orchestration around the owner equivalence call, evidence-driven
  sibling-table candidate alignment and preparation/map propagation,
  other ratio/absolute
  orchestration, and remaining fallbacks.
- `financial_operand_resolution.py` owns state-free candidate matching,
  grounding, selection, and merge behavior, including coherent-first required
  candidate merge followed by complete-ratio candidate-first or current-first
  precedence. It also owns ordered typed direct structured acceptance across
  required match/surface, ambiguity, and lookup direct-support gates, plus typed
  prepared preferred-slot score/ratio-alignment adoption and exact overlay. It
  owns recovered-context period merge or coherent-ratio replacement and
  referenced evidence adoption after graph-owned builders run. It also owns the
  post-coercion per-row lookup direct-support decision and the required
  match/surface, lookup-rematch, direct-first merge decision as separate typed
  state-free seams. Its typed direct structured-evidence base scorer and neutral
  ordered aggregate-role preference predicate are also state-free; graph and
  lookup-recovery callers consume the scorer directly without the former
  graph-private method or callback parameters. The same owner exposes the plain
  table-label metadata lookup scorer over a graph-built slot and evidence item.
  It preserves the literal empty-slot/label/unit/digit gates, additive weights,
  repeated access and exception order, while graph retains all three slot builders,
  their empty-slot invocation asymmetry, and downstream selection policy.
  It also owns the plain direct target-metric fallback conflict predicate over a
  graph-prepared target row, existing rows, and required operands. The predicate
  preserves target/existing gates, matcher-specific row-copy repetition, known-unit
  construction, aggregate-role veto, aggregate-like and structured-source lazy
  access, input immutability, and exact exception behavior. In particular,
  `operand_row_values_differ` retains its helper-local float `TypeError`/`ValueError`
  catch and raw/value fallback while other exceptions propagate. Graph retains
  target construction, evidence pool/coercion, scope, adoption/evidence append,
  candidate preparation, state, artifact, and final orchestration.
  The same owner also owns the plain state-free single-row embedded/rendered-unit
  normalization repair transform. It preserves fresh top-level copy and nested-
  alias behavior, scaled tolerance and `NaN` semantics, stable first rendered
  match, original-field precedence, input immutability, and exact access/exception
  order. It also owns plain shared-context multi-row ratio display-unit alignment,
  preserving policy/grouping order, partial repair, exact no-change identity,
  changed-path copies and nested aliases, and uncaught exceptions. Graph retains
  all row construction, provenance, plan/map and evidence-driven sibling
  alignment, ratio/append, state, artifact, and final orchestration.
  The same owner owns plain `surface_contract_numeric_evidence_items(...)` for
  required-operand prose numeric-evidence filtering. It preserves fresh-empty
  falsy results, fixed evidence surface-field
  access, per-attempt row copies, positive/negative/numeric predicate laziness,
  global first-seen key dedupe, stable order, fresh retained top-level rows,
  nested aliases, input immutability, and uncaught exception order. Graph retains
  evidence/reconciliation and required-list preparation, the unconditional call
  after direct-grounding computation, narrative/restriction gates, both result
  merge paths, LLM/state work, and final orchestration.
  It also owns plain `ratio_context_has_metric_surface(...)` over graph-prepared
  context evidence and task metadata. The predicate preserves eager task-label
  and alias collection, repeated normalization, stable dedupe, all-context
  evidence/metadata copies and fixed-surface materialization before matching,
  first-match laziness, input immutability, and uncaught exception order. Graph
  retains existing-result iteration, family/task/signature/status/artifact/value/
  completeness/tolerance gates, exact-object call placement and result inversion,
  ratio recalculation/adoption, evidence selection, state, artifact, and final
  orchestration.
- `financial_dependency_projection.py` owns dependency binding/projection,
  direct-versus-dependency selection, typed main/late/final application, and
  dependency recalculation plan disposition. Executable `single_value` plans
  are reused, invalid or absent plans rebuild once, and executable
  non-`single_value` plans are `unsupported_mode`, do not recalculate that row,
  and preserve original ordered-result identity on the enclosing no-change path
  before builder, candidate, or formatter work. For graph-prepared artifact rows
  and an already-coerced recalculated ratio value, it also owns typed status/numeric
  precedence, scaled-tolerance, and stable first-conflict selection. After
  candidate execution it owns typed Stage 1 operand/plan/result shallow copies,
  the second mutable result and result-status disposition, plus Stage 2 truthy
  formatted-result mutation and trace-first/fallback final row projection. It
  also owns typed in-place adoption of graph-resolved structured provenance into
  a graph-built dependency row: source ids/anchor, converted-display preservation
  or unit realignment, and nonempty scope/statement/table metadata overlay. For
  graph-prepared dependency-source ratio fields, it owns the typed fresh
  calculation-result/answer-slot projection and its exact source-list and
  component-slot alias contract; source selection, ratio/query policy, source-id
  cleaning, and compact formatting remain graph-owned. It also owns plain
  dependency-row display/normalized-unit inference with slot-before-sibling raw
  precedence and `UNKNOWN`-only percent/KRW/count policy membership. The four
  call gates, conditional re-inference, row construction, ratio append/merge,
  and state/evidence/artifact/final orchestration remain graph-owned. The same
  owner also owns the plain dependency task-output normalized-KRW consistency
  predicate with its short-circuit gates, raw/result-unit fallback, exact scaled
  tolerance, input immutability, and conversion-try exception boundary. Row
  coercion, table-metadata repair, both call placements, mutation, and later
  orchestration remain graph-owned. The same owner owns the plain prepared
  structured-unit-realigned operand/source-slot equivalence predicate. It preserves
  marker-first copy and fallback-sequence laziness, fallback role/raw/id filtering,
  final non-task source-id intersection, input immutability, and uncaught access/
  copy/normalization/iteration exceptions. Full coherence-rank preparation,
  source-task/material/anchor-projection gates, rank disposition, ratio scope, and
  provenance/adoption/state/artifact/final orchestration remain graph-owned.
- `financial_calculation_execution.py` owns deterministic difference/growth
  plan construction, plan validation, formula execution, and value-only stale
  assessment.
- `financial_answer_slots.py` owns answer-slot construction plus typed ratio
  calculation-result and primary-slot display synchronization. It preserves the
  formula-mismatch copy versus ordinary in-place update distinction, current-
  surface precedence, percent policy, and exception order; graph callers retain
  compact-answer and ordered-row orchestration. The same owner now exposes plain
  `source_task_display_compatible_with_slot(...)`, preserving source-display-first
  normalization, rendered/raw equality, `task_output:`, raw-unit, normalized-unit,
  configured KRW-display short circuits, input immutability, and uncaught exception
  order. Graph retains source-task/slot lookup, material gating, call placement,
  False-path rendered/raw fallback, and all growth/state/artifact orchestration.
- `financial_aggregate_projection.py` owns pure stale provenance target
  selection, canonical aggregate operation-family normalization, canonical
  aggregate-result signature and growth operand sign-consistency rank primitives,
  the typed state-free negative runtime-ratio absolute-magnitude transformation over
  graph-prepared mutable result/slot/primary copies, typed base/refreshed answer-
  candidate payload packaging, and typed prepared candidate application/final-
  answer projection synchronization. It also owns
  typed state-free filtering of generated aggregate provenance from a graph-
  prepared projection and kept-evidence-id sequence, plus recursive consistency
  synchronization of graph-prepared nested subtask rows against current ordered
  task results. It also owns typed state-free synchronization of a graph-selected
  projection row with prepared raw answer/rendered surfaces, including numeric-
  candidate selection and conditional result/slot/lookup copy semantics. For
  graph-prepared lookup primary slots, it owns typed arithmetic component, series,
  and difference/sum delta synchronization with the existing match, copy/alias,
  stable-order, and exception contracts. It also owns plain compact aggregate-
  synthesis prompt-row projection over graph-prepared ordered results and aggregate
  projection. Projected-row precedence, material operand filtering, stable grouping,
  fixed field/getter order, fresh containers, nested aliases, and uncaught
  exceptions remain unchanged. Graph retains the LLM gate, model/prompt setup,
  post-period inputs, JSON/debug/prompt invocation, catch/fallback, composition,
  state, and evidence orchestration.
- `financial_runtime_trace.py` owns the public shared operand material-numeric
  predicate consumed by runtime-trace append and aggregate prompt projection. Its
  `missing` gate, lazy unit/value fallbacks, digit threshold, normalized-value
  access, raw-value fallback, no-mutation, and uncaught-exception contract remain
  unchanged; trace-owned source normalization, key construction, dedupe, and append
  stay outside the predicate.
- `financial_aggregate_state.py` owns the public `AggregateCompositionState`
  carrier and its common state-free transition. The transition preserves answer
  normalization and lazy fallback, current-first claim cleanup/dedupe, projection
  reset/override alias precedence, narrative-lock fallback, independently evaluated
  feedback clearing, fresh carrier/list identity, and uncaught exception order.
  Producer construction and gates, sequential invocation, later `_replace`, broader
  answer precedence, state/evidence/LLM work, and final orchestration remain graph-owned.
- `financial_task_artifacts.py` owns prepared late aggregate-artifact payload and
  summary synchronization. It preserves copy-all-before-search, raw exact first-
  match, shallow aliases, overwrite/access order, input immutability, and uncaught
  exceptions. It also owns the private strict-dictionary ten-field operand-ref
  collector and public prepared reconciliation-artifact evidence-ref enrichment.
  That seam preserves empty-ref identity/laziness, old-first stable ref order,
  fresh top-level copies on the nonempty path, nested aliases, task/kind/payload/
  result/status gates, and exact uncaught exception order. The owner imports the
  private source-id cleaner from `financial_runtime_normalization.py`; it does not
  export the collector. Artifact creation/finalization, ledger-level id/order,
  graph state/input preparation, integrity/replan policy, and final orchestration
  remain graph-owned.
- `financial_numeric_surface.py` owns the private table numeric-support text helper
  and the plain public prepared-evidence promoter. Empty/no-support paths preserve
  exact evidence identity; supported paths preserve stable first-four selection,
  fresh evidence/metadata copies, nested aliases, claim/quote order, header laziness,
  input immutability, and uncaught exception order. Evidence selection, retrieved-
  narrative skipping, local row preparation, later filtering, state/artifact work,
  and final orchestration remain graph-owned.

At the latest checkpoint, the graph is 18,328 lines, the graph helper module is
6,311, graph reconciliation is 2,428, lookup recovery is 609, the operand owner
is 2,831, the answer-slot owner is 625, the aggregate owner is 1,106, the
aggregate-state owner is 161, the dependency owner is 3,257, the task-artifact
owner is 1,250, the numeric-surface owner is 539, the runtime-trace owner is 1,065,
and the execution owner is 837. The latest owner slice passed targeted 3/3 tests,
affected 676/676 tests, the 217-literal audit, and full discovery over 1,525/1,525
tests.
Benchmark refresh is NOT RUN. Exact commit boundaries, intermediate
metrics, and claim limits live in
`docs/history/implementation_history.md`; they are intentionally not repeated
in this plan.

Phase 3 remains open for these unordered follow-ups:

- move bounded aggregate repair/precedence decisions behind the aggregate owner;
- isolate other remaining dependency and ratio/absolute seams without moving
  graph state lookup;
- keep broader task/artifact ledger synchronization as a separately specified
  behavior contract;
- reduce the remaining private-API mesh and co-locate tests only as their public
  contracts move.

Priority and sequencing are owned by
`docs/overview/project_status.md#next-work`; this plan records debt and stop
lines, not a competing queue.

The canonical path is:

```text
OperandResolver -> FormulaExecutor -> AnswerRenderer -> Verifier
```

Use existing owner modules before adding new ones:

- `financial_answer_slots.py`
- `financial_operand_resolution.py`
- `financial_dependency_projection.py`
- `financial_calculation_execution.py`
- `financial_aggregate_projection.py`
- `financial_aggregate_state.py`
- `financial_graph_calculation_rendering.py`
- `financial_numeric_surface.py`
- `financial_runtime_trace.py`
- `financial_answer_projection.py`

Continue work in `financial_graph_calculation.py` only for a concrete caller
migration, contract gap, or bug. Each extraction must move callers and delete
the old implementation. Do not split the file merely to reduce line count.

Completion conditions:

- partial: converge on one source of truth for operands, formula result, and
  rendered answer;
- met: legacy flat mirrors cannot override `agent_answer` or the resolved trace;
- partial: remove wrappers with no runtime caller as each bounded owner move
  deletes its old implementation;
- open: organize tests by operand, execution, rendering, verification, and
  projection contracts rather than private helper location.

### Phase 4: Isolate optional systems

Status: completed on 2026-07-22. The default entrypoints pass fresh-process
import checks, and a deterministic `FinancialAgent` construction plus `run()`
invocation loads none of the reviewed MAS, evaluator, benchmark, promotion,
portfolio-review, or persisted-cache implementations. The only remaining local
cache-index import is guarded by an explicitly configured index path. Cache
candidate trace policy remains unchanged; further isolation requires a concrete
product requirement or observed default-runtime leak.

- Default runtime imports must not load MAS, evaluator, benchmark, cache
  promotion, or portfolio-review implementations.
- New MAS callers use `src.experimental.mas`; legacy `src.agent` MAS imports
  remain only while a verified external caller requires them.
- Candidate-only cache and promotion gates remain evaluation/internal surfaces
  until a separate product requirement enables them.
- Debug and review bundles are opt-in at API boundaries.

Completion condition: importing and invoking the default runtime does not load
optional systems, while their focused tests still pass independently.

### Phase 5: Reduce review and test noise

Status: completed on 2026-07-22. PR #84 reduced checked-in benchmark outputs to
history-linked compact summaries and small diagnostics, while full result
bundles remain local-only. The final documentation slice converted `CONTEXT.md`
and `docs/overview/project_status.md` from chronological diaries into current
state snapshots. Oversized tests were not split because no public behavior
changed; they remain an opportunistic cleanup alongside the contract they
exercise.

- Split oversized test files by public contract when touching the relevant
  behavior; do not perform an all-at-once test rewrite.
- Publish the portfolio claim through one structural summary, one plain
  comparison, and a small fixture set; internal history may retain compact
  directly linked summaries and diagnostics.
- Keep full local result bundles, stores, caches, and heartbeat logs untracked.
- Prefer current architecture docs over chronological implementation diaries.

Completion condition met: reviewer-facing docs link to a small evidence set,
while implementation history, experiment history, and Git preserve chronology
without defining the product surface.

## Deletion criteria

Before deleting or archiving a module, answer:

1. Is it required by `FinancialAgent.run()`?
2. Is it required by `FinancialParser.process_document()`?
3. Is it required by `VectorStoreManager.search()` or canonical ingest?
4. Is it required to create `structured_result` or
   `resolved_calculation_trace`?
5. Is it required by README quick-review commands?
6. Is it current evidence for a reviewer-facing claim?
7. Does a real external caller still use its compatibility path?

If every answer is no, delete it. If an answer is yes, move it to the correct
surface or preserve a narrow adapter with a named removal condition.

## Verification order

For every phase:

1. run the smallest owner/contract tests;
2. for changes under `src/agent` or `src/routing`, run
   `python -m src.ops.audit_runtime_domain_terms`;
3. run `python -m unittest discover -s tests`;
4. run `portfolio_review_gates` when reviewer-facing behavior changes;
5. use a focused store-fixed eval-only benchmark only when runtime behavior may
   affect answer quality;
6. run a full benchmark only with known store/cache inputs and heartbeat logs.

Always check `git diff --check` and artifact hygiene before handoff.

## Stop lines

Stop and reassess when:

- an extraction creates a new forwarding layer without moving callers;
- a deletion requires weakening a public contract;
- a runtime rule needs company, benchmark, or metric-specific vocabulary;
- evidence faithfulness decreases to improve a score;
- optional systems still leak into the default import path;
- a long benchmark has neither results nor a heartbeat;
- experimental artifacts would need to be committed without explicit approval.
