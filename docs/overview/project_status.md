# Project Status

> Current repository state only. Start with [README.md](../../README.md), then
> [portfolio_one_pager.md](portfolio_one_pager.md) and
> [portfolio_experiment_report.md](portfolio_experiment_report.md). Historical
> implementation and experiment details live in
> [implementation_history.md](../history/implementation_history.md) and
> [experiment_history.md](../history/experiment_history.md).

Last updated: 2026-08-10

## Product Boundary

The portfolio product is the single-agent `FinancialAgent` runtime for DART
filing analysis. Its reviewer-facing engineering story is:

1. preserve DART section and table structure during ingest;
2. retrieve with dense/BM25 hybrid search and structure-aware expansion;
3. use an LLM for intent and semantic planning;
4. bind operands and execute calculations deterministically;
5. return evidence-backed answers with calculation and provenance traces.

MAS, report-cache promotion, evaluators, benchmark runners, and extended review
workflows remain optional or experimental. They must not load during default
imports or an unconfigured `FinancialAgent` invocation.

## Current Source State

- PRs #79 through #84 completed the portfolio core simplification sequence on
  2026-07-22; PR #85 compressed the current-state and handoff documents.
- Latest confirmed merge: PR #85, `main@f0a5145`.
- The current local branch HEAD on `codex/finalize-five-minute-review` is the
  source checkpoint; use `git log` for its exact commit. The local checkpoint is
  ahead of its tracked upstream and remains unpushed and unmerged.
- Canonical public numeric contracts are `resolved_calculation_trace`, explicit
  `structured_result`, and task/artifact projections.
- Top-level `calculation_*` compatibility mirrors are not part of the default
  `FinancialAgent.run()` response.
- Default import and deterministic invocation regression gates cover isolation
  from MAS, evaluator, benchmark, promotion, portfolio-review, and persisted
  cache-index implementations.
- Tracked benchmark outputs were reduced from 324 raw/intermediate files to 26
  compact, history-linked summaries and diagnostics. Full result bundles,
  stores, caches, and heartbeat logs are local-only.
- Runtime routing canonical examples now live under `src/config`; the held-out
  routing set remains under `benchmarks/golden`, and a normalized disjointness
  contract prevents train/eval question overlap.
- The portfolio demo fixture has a checked-in SHA-256 evidence manifest and
  validates calculation, display, operand, source/citation, and critic-target
  invariants before reporting `fixture_contract_ready`.
- Benchmark JSON writes are atomic, failed runs emit a terminal failed
  heartbeat, and `--eval-output-dir` preserves source bundles during eval-only
  refreshes.
- `.github/workflows/validation.yml` defines the Python 3.13 publication
  validation path; `.python-version` is the interpreter source of truth.
- The calculation path now has explicit graph-state orchestration, state-free
  operand/dependency owners, deterministic plan/execution ownership, and pure
  aggregate provenance selection. Canonical public output remains
  `resolved_calculation_trace`, explicit `structured_result`, and task/artifact
  projections.
- Dependency recalculation now uses a typed plan disposition. Executable
  `single_value` plans are reused, invalid or absent plans are rebuilt once, and
  executable non-`single_value` plans are `unsupported_mode`: the affected row
  is not recalculated, and the no-change path retains original list/row identity,
  before raw-plan construction, candidate execution, or ratio formatting.
- Required candidate merge now has a typed state-free operand-resolution owner.
  It applies coherent-first candidate merge, evaluates required coverage, and
  selects complete-ratio candidate-first or current-first precedence. The graph
  retains evidence/candidate builders, dependency producer-scope filtering, the
  lazy coherent-context builder gate, and runtime projection.
- Direct structured acceptance now has a typed state-free operand-resolution
  owner. It preserves the existing ordered requirement/surface, ambiguity, and
  lookup direct-support gates, including lookup's second ambiguity check and
  no-stage identity. The graph retains row/evidence construction, coercion,
  scope/target policy, and the applicability gate.
- Direct structured-evidence base scoring now has a typed state-free
  operand-resolution owner with `no_structured_cells`,
  `surface_contract_not_satisfied`, and `evidence_scored` dispositions. The
  ordered aggregate-role preference predicate is co-located there and remains
  guarded at its original call sites. Graph and lookup recovery consume the
  scorer directly; the old graph-private scorer and lookup-recovery callback
  parameters are gone. Reasons are contract outputs, not runtime trace fields.
- Table-label metadata lookup scoring is now a plain public operand-owner
  primitive. It preserves the empty-slot/table-label/unit/digit gates, exact
  additive weights, repeated access and normalization, input immutability, and
  uncaught exception order. The graph retains all three slot builders and later
  period/context/scope/ambiguity/tie/grouping/selection policy; the first two
  callers still score empty slots while the period-context caller skips them.
- Direct target-metric fallback unit/value conflict is now a plain public operand-
  owner predicate. It preserves target/existing gates, matcher-specific row-copy
  repetition, repeated unit normalization, aggregate-role veto, aggregate-like
  and structured-source lazy access, stable first-conflict order, and input
  immutability. The existing value-difference helper still catches float
  `TypeError`/`ValueError` and falls back to raw/value comparison; mapping,
  matcher, copy, string, normalizer, cleaner, iteration, `RuntimeError`, and other
  exceptions propagate. The graph retains target construction, evidence coercion,
  scope, adoption/evidence append, candidate preparation, and later orchestration.
- Prepared preferred-slot adoption now has a typed state-free operand-resolution
  owner. It preserves higher/equal-score rejection, ratio peer-unit alignment,
  exact row overlay, top-level copy/nested identity, sequential row application,
  and input immutability. Its reasons are contract outputs, not runtime trace
  fields. The graph retains runtime evidence overlay, row matching and iteration,
  peer-unit preparation, the strongest-slot builder, query/report-scope score
  augmentation, ambiguity/tie-break policy, and sequential adoption.
- Recovered context adoption now has a typed state-free operand-resolution owner.
  It preserves period recovered-first/current missing-fill versus coherent-ratio
  replacement, referenced-evidence filtering and order, existing-id exclusion,
  candidate duplicates, top-level row-copy/nested identity, and no-context
  identity. The graph retains recovery eligibility, document/evidence collection,
  context-row builders, logging, and ratio-recovered/runtime projection.
- Post-coercion LLM operand selection now has two typed state-free
  operand-resolution seams: per-row lookup direct-support, then required
  match/surface, lookup rematch, and direct-first merge. Their reasons and flags
  are contract outputs, not runtime trace fields. The graph retains model
  invocation, evidence lookup, scope skip, id assignment, coercion,
  applicability, the enclosing exception boundary, and fallback orchestration.
- Ratio artifact conflict selection now has a typed state-free dependency owner.
  It receives ordered graph-prepared artifact rows plus an already-coerced
  recalculated value and owns status fallback, artifact numeric precedence,
  scaled tolerance, stable first-conflict selection, and the shallow-copy
  preservation marker. Its reason/flag are not runtime trace fields. The graph
  retains recalculated-value coercion and invalid-value builder laziness,
  task-artifact/ledger row construction, absolute-ratio query/transform
  invocation, and the caller's no-change/final projection contract; a selected
  row is therefore not guaranteed to reach final output.
- Collapsed-ratio runtime absolute-magnitude projection now has a typed
  state-free aggregate owner. The graph retains trace and collapsed-row
  eligibility, completeness and query gates, prepares mutable result/slot/primary
  copies, and retains downstream coherence, compact-answer, coverage, and final
  projection. The owner mutates only those prepared copies in the existing
  order, returns the same result identity, preserves caught `TypeError`/`ValueError`
  partial updates and `RuntimeError` propagation, and adds no reason/flag/trace
  field.
- Dependency post-candidate finalization now has two typed state-free owner
  stages. Stage 1 shallow-copies candidate operands, plan, and result, creates a
  distinct mutable result, and uses only normalized `calculation_result.status`
  for disposition. The graph retains query/absolute handling, artifact-ledger
  conflict short-circuit, and formatting. Stage 2 applies a truthy formatted
  result and projects the final row with the existing trace-first and source-id
  fallbacks while preserving result identity. Its readiness and reason are not
  trace fields, and no selected-evidence projection is added. A non-`ok` nested path returns its
  supplied local row; original list/row identities are guaranteed only when the
  enclosing pass has no other changes.
- Prepared dependency structured-provenance adoption now has a typed state-free
  owner seam. The graph constructs and normalizes the row, resolves provenance
  from `vsm` graph state, skips the owner when none exists, and retains evidence
  lookup/coercion/append. The owner mutates that same row in anchor/chunk-id,
  converted-display preservation or unit-realignment, and metadata-overlay order;
  nested identity and provenance input immutability are retained. Its typed reason
  and application flag are not trace fields. The corrected graph fixtures attach
  their structure graph to the production `vsm` surface.
- Structured-unit-realigned operand/source-slot equivalence is now a plain public
  dependency-owner predicate. It preserves marker-first direct copy and fallback-
  sequence laziness, fallback role/raw/id filtering and stable order, final
  non-task source-id intersection, input immutability, and uncaught access/copy/
  normalization/iteration exceptions. The graph retains operation-family,
  source-slot/candidate/marked-row preparation, source-task/material/anchor-
  projection gates, rank disposition, ratio scope, and all later orchestration.
- Prepared dependency-source ratio-result projection now has a typed state-free
  dependency-owner seam. It builds fresh calculation-result, answer-slot,
  primary-value, group/role, and component-list containers while preserving
  untouched nested identities, the exact four-surface source-id-list alias, and
  numerator/denominator slot reuse. The graph retains source-slot selection,
  component ranking and gates, ratio/query/absolute policy, source-id cleaning,
  compact formatting, and all owner applicability/laziness. The seam adds no
  reason, application flag, or trace field.
- Prepared aggregate answer-candidate application and final-answer projection
  synchronization now have typed owner seams. The owner keeps the same aggregate
  projection and existing calculation-result identities, normalizes the answer,
  applies formatted/rendered/status mutations in the existing order, and returns
  a new current-first stable merged claim-id list. The graph retains candidate
  build/refresh/selection, mutable state/evidence, artifact/ledger, stale repair,
  answer precedence, and final orchestration.
- Generated aggregate-provenance filtering now has a typed state-free aggregate
  owner seam. Empty kept-evidence input returns the exact projection identity;
  nonempty filtering preserves the existing shallow-copy, stable id-order,
  conditional subtask replacement, and input-immutability contracts. The graph
  retains evidence/kept-id selection, rebuild gating, selected claims, surface-
  operand append, stale repair, ledger, and final orchestration.
- Recursive nested aggregate-row consistency now has a typed state-free aggregate
  owner seam. It builds the normalized current-row authority map before recursion,
  uses last-row-wins task-id precedence, and preserves the three nested surfaces,
  stable order, invalid-item skip, cycle/depth, copy/identity, input-immutability,
  and uncaught-exception contracts. The graph retains the outer empty/no-change
  gates, promotion, preliminary/final rebuild, dependency alignment, preserved-
  field merge, and all later state/evidence/artifact/ledger/repair/answer work.
- Base and refreshed aggregate-answer candidate packaging now have typed state-
  free aggregate-owner seams. They preserve answer normalization, stable blank-
  filtered but duplicate-retaining claim-id order, three-flag coercion, fresh
  payload/list identity, input immutability, refreshed mapping copy/fallback, and
  exact access/exception order. The graph retains discovery, scoring/selection,
  narrative refresh, branch-local call placement/laziness, application invocation,
  answer precedence, and later projection/state/evidence/rebuild/orchestration.
- Prepared aggregate projection-row surface synchronization now has a typed
  state-free aggregate-owner seam. It preserves first-candidate ratio/growth
  versus last-candidate other numeric selection, exact raw answer/rendered
  surfaces, conditional result/slot/lookup copies, retained nested identities,
  input immutability, repeated operation-family access, and uncaught exception
  order. The graph retains candidate/sentence/conflict gates, rendered extraction,
  iteration, lookup primary-slot preparation and gating, row-map propagation,
  projection rebuild, and final orchestration.
- Ratio result-display synchronization now has a typed answer-slot owner seam.
  Status, operation-family, source-stated, percent-unit, parser, and equivalence
  gates retain their existing order. Formula mismatch returns a copied result and
  derived-metric surface; an ordinary successful display update mutates the exact
  prepared result while replacing only answer-slot and primary-value containers.
  The graph retains ordered-row gates/comparison/propagation, compact-answer
  construction, and all state, task, operand, period, and metric formatting.
- Source-task display compatibility for a prepared answer slot now has a plain
  answer-slot owner seam through `source_task_display_compatible_with_slot(...)`.
  It preserves source-display-first normalization, rendered/raw equality,
  `task_output:`, raw-unit, normalized-unit and configured KRW-display shortcuts,
  repeated policy-item stringification, input immutability, and uncaught exception
  order. Graph retains source-task/slot lookup and material gating, truthy call
  placement, True adoption, False rendered/raw fallback, growth calculation/
  material semantics, state, artifact, and final orchestration.
- Prepared lookup-slot to aggregate arithmetic-component synchronization now has
  a typed state-free aggregate-owner seam. Empty lookup and ineligible rows retain
  exact identity; eligible rows preserve conditional shallow-copy/nested-alias,
  concept-first then bidirectional-label first-match, overlay/source fallback,
  series, delta, input-immutability, and exception-order contracts. The graph
  retains lookup primary-slot preparation and its truthy gate, sequential row
  iteration, task-id/equality mapping, ordered/slot propagation, rebuild, and all
  later state/evidence/artifact/ledger and final orchestration.
- Prepared late aggregate-artifact payload and summary synchronization now has a
  typed state-free task-artifact owner seam. It preserves copy-all-before-search,
  stable raw exact-id first-match, fresh top-level/payload/projection-surface
  containers, shallow nested aliases, input immutability, and uncaught access/
  copy/slice order. The graph retains its initial artifact copy, all ratio,
  rendered, completeness, formatter and projection-mutation gates, the
  `None`/blank-id owner gate, aggregate artifact creation/finalization, and final
  orchestration. Empty-list plus nonblank-id remains owner-one.
- Single-row embedded or rendered-unit operand normalization repair now has a
  plain state-free operand-owner transform. It always returns a fresh top-level
  row, preserves nested aliases and input immutability, and retains the exact
  tolerance, `NaN`, original-field, first-match, access, and exception contracts.
  The four graph calls remain after their existing construction/plan gates and
  before provenance/evidence, multi-row alignment, or ratio append/merge work.
- Shared-table/context multi-row ratio display-unit alignment is also a plain
  operand-owner transform. No-change preserves exact list/row identities;
  changed paths copy every top-level row, preserve nested aliases and order, and
  retain the literal policy/grouping/partial-repair/exception contract. Graph
  keeps the evidence-driven outer aligner, candidate selection, ratio preparation,
  operand-map propagation, and later orchestration.
- Aggregate composition now has a public `AggregateCompositionState` carrier and
  a state-free transition in `financial_aggregate_state.py`. It preserves answer
  normalization with lazy fallback, current-first claim normalization/dedupe,
  projection reset/override alias precedence, narrative-lock semantics, separate
  feedback truthiness reads, fresh carrier/list identity, input immutability, and
  uncaught exception order. The graph retains all five producers and their gates,
  sequential transition placement, initial/final carrier construction, later
  `_replace` transitions, broader answer/claim/projection precedence, state/evidence/
  LLM work, and final orchestration.
- Canonical aggregate-result signature and growth operand sign-consistency rank
  are now plain state-free `financial_aggregate_projection.py` primitives. The
  graph retains all seven signature and four rank call positions, including the
  explicit repair-row copy and repeated calls, plus full dedupe, rank tuples,
  nested promotion, result precedence, and later orchestration.
- Dependency-row display and normalized-unit inference is now a plain state-free
  `financial_dependency_projection.py` primitive. Slot raw unit precedes the
  lazy sibling-result fallback, and only `UNKNOWN` normalized units read the
  percent/KRW/count policy. The graph retains all four call gates, conditional
  second inference, row construction, ratio append/merge, and later orchestration.
- Dependency task-output normalized-KRW consistency is now a plain public
  dependency-owner predicate. It preserves the exact early gates, raw/result-unit
  fallback, scaled tolerance, conversion exception boundary, and input
  immutability. The graph retains row coercion, table-metadata repair, both call
  placements, mutation, and later orchestration.
- Prepared reconciliation-artifact evidence-reference enrichment is now a plain
  public task-artifact owner seam backed by a private strict-dictionary ten-field
  operand-ref collector. It preserves empty-ref artifact-list identity and
  laziness, operand-before-extra and old-before-new stable ref order, nonempty-path
  copies of every top-level artifact, nested aliases, task/kind/payload/result/
  status gates, input immutability, and uncaught exception order. The private
  source-id cleaner is imported from `financial_runtime_normalization.py`; only
  the public enrichment function is exported. The graph retains both call
  placements, prepared task/artifact/state inputs, downstream operand-set artifact
  and integrity/replan consumers, and final orchestration.
- Compact aggregate-synthesis prompt-row projection is now a plain public aggregate-
  owner seam. It preserves calculation-result/answer-slot/ordered fallback
  precedence, material operand filtering, stable task grouping, fixed field and
  repeated-getter order, fresh compact containers, nested aliases, input
  immutability, and uncaught owner exceptions. The graph retains post-period-
  realignment input preparation, the LLM/model/prompt gate, JSON/debug/prompt and
  structured-LLM invocation, the enclosing catch/fallback, composition, state,
  evidence, and final orchestration.
- The shared material-numeric predicate is now public in
  `financial_runtime_trace.py`. It preserves the `missing` gate, raw/unit and
  raw/value/rendered/display fallback order, digit threshold, normalized-value
  access, raw-value fallback, input immutability, and uncaught exceptions. Runtime
  trace retains prepared row/source-id normalization before the predicate and key/
  dedupe/append work afterward; the aggregate owner consumes the same public
  predicate without a compatibility alias.
- Table numeric-support text and prepared evidence promotion now belong to
  `financial_numeric_surface.py`. The support helper remains private; public
  `promote_table_numeric_support_evidence(...)` preserves no-support identity,
  supported-path evidence/metadata copies,
  stable first-four and answer-major matching, nested aliases, header and claim/
  quote order, input immutability, and uncaught exceptions. Graph keeps candidate/
  support and evidence-selection gates, local evidence/metadata preparation,
  retrieved-narrative skipping, later filtering, and final orchestration.
- Generic numeric-answer coverage and outside-reference comparison now also belong
  to plain public `financial_numeric_surface.py` predicates. Both extract the answer
  before the second input. Coverage preserves numeric-list-first empty gates and
  numeric-major/answer-minor `all(any(...))`; outside-reference comparison preserves
  answer-list-first empty gates and answer-major/reference-minor
  `any(not any(...))`. Graph keeps all 12 prepared-input call placements, result
  polarity, public/structured projection, preservation, scoring, arithmetic sync,
  stale/initial-state policy, evidence support, and final orchestration.
- Required-operand prose numeric-evidence surface filtering through public
  `surface_contract_numeric_evidence_items(...)` now belongs to the plain operand
  owner. It preserves fresh-empty falsy results, fixed
  claim/quote/raw surface access, per-attempt row copies, positive/negative/numeric
  predicate laziness, global first-seen key dedupe, stable order, fresh retained
  top-level rows, nested aliases, input immutability, and uncaught exceptions.
  Graph keeps evidence/reconciliation and required-list preparation, direct-
  grounding computation, unconditional pre-narrative call placement, narrative/
  restriction gates, both result merge paths, LLM/state work, and final orchestration.
- Retrieved ratio-context task-metric surface detection through public
  `ratio_context_has_metric_surface(...)` now belongs to the plain operand owner.
  It preserves eager task-field/alias collection, repeated normalization, stable
  label dedupe, all-context evidence/metadata copies and fixed-surface
  materialization before matching, first-match laziness, input immutability, and
  uncaught exceptions. Graph retains existing-result iteration, family/task/
  signature/status/artifact/value/completeness/tolerance gates, exact-object call
  placement and result inversion, ratio recalculation/adoption, evidence
  selection, state, artifact, and final orchestration.
- Aggregate-subtask numeric-answer conflict and direct-source-reference detection
  now belong to plain public `financial_aggregate_projection.py` predicates.
  Numeric conflict preserves candidate-before-current answer fallback, both
  extractor calls, empty-side gating, and asymmetric candidate-major equivalence.
  Direct-source detection preserves calculation-result copy, the four fixed
  source surfaces, source-id cleaning order, and lazy non-`task_output:` matching.
  Both inputs and uncaught exception order remain unchanged. Graph keeps task-
  ledger conflict/fallback disposition, sentence scoring, arithmetic-surface
  synchronization, the direct-source/family/conflict/sign-rank nested-promotion
  chain, and all state/evidence/provenance/artifact/final orchestration.
- At the current checkpoint, `financial_graph_calculation.py` is 18,253 lines,
  `financial_graph.py` is 1,200,
  `financial_graph_helpers.py` is 6,311,
  `financial_graph_reconciliation.py` is 2,428,
  `financial_lookup_recovery.py` is 609,
  `financial_answer_slots.py` is 625,
  `financial_aggregate_projection.py` is 1,151,
  `financial_aggregate_state.py` is 161,
  `financial_operand_resolution.py` is 2,831,
  `financial_dependency_projection.py` is 3,257,
  `financial_task_artifacts.py` is 1,250,
  `financial_numeric_surface.py` is 575,
  `financial_runtime_trace.py` is 1,065, and
  `financial_calculation_execution.py` is 837. These figures are not a
  total-code or broad executed-path/performance reduction claim.
- The latest calculation checkpoint passed targeted 6/6 and affected 644/644
  tests, the 217-literal runtime audit, and full discovery over 1,531/1,531 tests.
  Benchmark refresh remains NOT RUN.

Detailed correctness/relocation chronology, intermediate metrics, and validation
boundaries live in
[implementation_history.md](../history/implementation_history.md). This
current-state document does not duplicate that commit diary.

## Runtime Ownership

| Surface | Current owner |
| --- | --- |
| Public entry point | `FinancialAgent.run()` |
| DART parsing | `FinancialParser.process_document()` and parser modules |
| Canonical ingest profile | `src/config/runtime_contract.py` |
| Query/filter/search/rerank/selection trace | `financial_retrieval_pipeline.py` |
| Structure expansion and evidence construction | `financial_graph_evidence.py` |
| Semantic plan | LLM-backed planning contract |
| Calculation graph-state orchestration | `financial_graph_calculation.py` adapter |
| Generic operand candidate resolution, unit normalization/alignment, required-operand prose evidence filtering, and retrieved ratio-context metric-surface detection | `financial_operand_resolution.py`; owns coherent-first required-candidate merge, complete-ratio candidate-first/current-first precedence, ordered typed direct structured acceptance, typed direct structured-evidence base scoring, the neutral ordered aggregate-role predicate, plain table-label metadata lookup scoring, the plain direct target-metric fallback unit/value conflict and aggregate-preference predicate, prepared preferred-slot adoption/overlay, recovered-context merge/replacement plus referenced-evidence adoption, post-coercion per-row lookup direct-support, required match/surface, lookup-rematch, direct-first merge, the plain embedded/rendered single-row repair, shared-context multi-row ratio display-unit alignment, plain `surface_contract_numeric_evidence_items(...)`, and plain `ratio_context_has_metric_surface(...)` while graph retains scope/target policy, table-label slot builders and downstream selection, direct-target construction/evidence coercion/scope/adoption, model/evidence/id/coercion/applicability/exception/fallback orchestration, stateful preferred-slot preparation, query/report-scope score augmentation, ambiguity/tie-break, recovery eligibility/builders/logging, ratio-recovered/runtime projection, row construction/provenance, plan/map propagation, evidence-driven sibling candidate alignment, filter input preparation/call placement/result merging, existing ratio-result gate/iteration and conflict inversion, and ratio append/merge policy |
| Dependency binding summary, projection, source-set selector, typed main/late/final application, recalculation plan disposition, prepared ratio-artifact conflict selection, two-stage post-candidate finalization, prepared structured-provenance adoption, structured-unit/source-slot equivalence, prepared dependency-source ratio-result projection, dependency-row unit inference, and task-output normalized-KRW consistency | `financial_dependency_projection.py`; the provenance seam mutates the graph-built row in place after graph-owned stateful lookup, the structured-unit predicate preserves marker/fallback and final source-id matching order, the ratio-result seam builds fresh canonical result/slot containers with exact source/component aliases, the unit primitive preserves slot-before-sibling raw precedence plus `UNKNOWN`-only policy inference, and the task-output predicate preserves its early gates, tolerance, and conversion exception boundary; graph retains row construction/normalization and conditional re-inference, row coercion and table-metadata repair, evidence coercion/append, raw-plan and candidate construction/execution, source-slot/candidate/marked-row preparation and coherence-rank orchestration, source-slot selection and component ranking, ratio/query/absolute policy, source-id cleaning, task-artifact/ledger conflict short-circuit, compact formatting, caller iteration/projection, repair acceptance, other fallback, and aggregate sequencing |
| Deterministic difference/growth plan decision, primary plan validation, formula execution, and value-only stale freshness assessment | `financial_calculation_execution.py`; state-free construction plus typed raw/guarded selection are owner-owned, while the state/query adapter, lazy dependency raw-plan construction, and primary runtime/task/artifact projection remain graph-owned; dependency receives the raw plan explicitly and broader ledger synchronization remains open |
| Answer slots, ratio result-display synchronization, and source-task display compatibility | `financial_answer_slots.py`; owns answer-slot construction, typed calculation-result/primary-slot display consistency, and plain `source_task_display_compatible_with_slot(...)`, including formula-mismatch copy versus ordinary in-place update, current-surface/percent-policy order, source-display/rendered/raw and unit-policy shortcuts, and exception order, while graph callers retain ordered-row gating/propagation, source-task/slot lookup and material gate, compatibility call placement and fallback, compact-answer construction, growth semantics, and state/task/operand/period/metric formatting |
| Numeric surface extraction/equivalence, generic answer/reference comparison, and prepared table-support promotion | `financial_numeric_surface.py`; owns plain `answer_covers_numeric_answer(...)` and `answer_has_numeric_material_outside_reference(...)` with eager answer-first extraction, opposite numeric-major/answer-major nested comparisons, empty-list gates, and uncaught exceptions, plus the private table-support text helper and public prepared-evidence promoter; graph retains all prepared target construction, 12 comparison call placements and polarity, public/structured projection, preservation/scoring/synchronization, stale/initial-state and evidence-support policy, local evidence copies, retrieved-narrative skip, filtering, state/artifact work, and final orchestration |
| Aggregate projection, stale provenance selection, signature/sign rank, compact synthesis prompt-row projection, aggregate-subtask numeric predicates, prepared collapsed-ratio magnitude transformation, answer-candidate packaging/application/final-answer synchronization, generated-provenance filtering, nested-row consistency, prepared projection-row surface synchronization, and prepared arithmetic-component synchronization | `financial_aggregate_projection.py`; canonical operation-family normalization, aggregate-result signature and growth sign-consistency primitives, plain numeric-conflict/direct-source predicates, state-free target selection, compact synthesis-input projection, prepared result/slot transforms, candidate packaging/application, claim-id merge, provenance filtering, nested-row recursion, selected-row numeric/result/slot/lookup synchronization, and lookup-slot to component/series/delta synchronization are owner-owned, while task-ledger replacement and conflict fallback, sentence scoring, arithmetic-surface synchronization, full dedupe/rank tuples/nested promotion, LLM/model/prompt construction and invocation, JSON/debug projection and catch/fallback, evidence/kept-id and candidate/sentence selection, conflict/coverage/render gates, lookup primary-slot preparation and gating, per-row task mapping/propagation, rebuild gating, selected claims, surface-operand append, mutable state/evidence, artifact/ledger, stale repair, downstream coherence/answer/coverage, and final orchestration remain graph-owned |
| Shared operand material-numeric predicate | `financial_runtime_trace.py`; owns the public state-free `missing`/unit/value/digit/normalized-value disposition shared by runtime-trace append and aggregate prompt projection, while runtime trace retains row/source-id preparation plus key/dedupe/append and graph retains synthesis orchestration |
| Aggregate composition carrier and common transition | `financial_aggregate_state.py`; owns public `AggregateCompositionState` and the state-free answer/claim/projection/lock/feedback transition, while graph retains all producers and gates, call placement, sequential state handoff, later `_replace`, broader answer precedence, state/evidence/LLM work, and final orchestration |
| Task/artifact projection, prepared late aggregate-artifact payload synchronization, and prepared reconciliation evidence-ref enrichment | `financial_task_artifacts.py`; owns artifact/task projection helpers, typed first exact-id payload/summary replacement over graph-prepared artifacts, a private strict-dictionary ten-field operand-ref collector, and public empty-ref identity/nonempty-copy reconciliation enrichment; the latter uses the private runtime-normalization source-id cleaner and exports only the public function, while graph retains both reconciliation caller placements and prepared inputs, downstream operand-set artifact and integrity/replan work, the aggregate artifact initial copy and ratio/render/completeness/formatter/projection mutation gates, artifact creation/finalization, ledger-level id/order, and final orchestration |
| Public calculation projection | `resolved_calculation_trace` and `structured_result` |
| Optional MAS | `src.experimental.mas` facade |
| Optional persisted report cache | configured `ReportCacheIndex` boundary |

Domain vocabulary belongs in ontology, retrieval policy, config, or documented
data artifacts. Runtime control flow implements generic mechanisms only.

## Current Gate Status

| Gate | Latest status |
| --- | --- |
| Runtime contract gate | Recorded PASS; upstream raw bundle local-only |
| Hard structural numeric gate | Recorded PASS, 5 / 5; upstream raw bundle local-only |
| Concept runtime gap gate | Recorded PASS, 7 / 7; upstream raw bundle local-only |
| Policy-driven runtime gate | Recorded PASS; upstream raw bundle local-only |
| Expanded structural numeric gate | Recorded PASS, 9 / 9; upstream raw bundle local-only |
| Plain-retrieval comparison | Recorded 5 / 9 diagnostic baseline; not synchronized after the latest structural repair |
| Reflection promotion gate | READY |
| Report-cache promotion evidence | READY, serving disabled |
| Promotion trace materiality gate | READY |
| REFERENCE_NOTE capability gate | READY, Researcher context-only |
| Demo fixture contract | `fixture_contract_ready`; bound manifest verified, live replay false |
| Portfolio review surface | `review_surface_ready`; unit suite and domain audit explicitly `not_run` by this command |
| Latest calculation runtime checkpoint | PASS: targeted 6/6 and affected 644/644 tests on 2026-08-10 |
| Runtime domain-term audit | PASS, 217 reviewed literals on 2026-08-10 |
| Full unittest discovery | PASS, 1,531/1,531 tests locally on 2026-08-10 |
| Benchmark refresh after the latest calculation changes | NOT RUN; recorded benchmark evidence predates the latest behavior changes |
| GitHub Actions validation | Workflow defined; no remote run observed for the local branch |

The structural and plain numbers are retained recorded evidence, not a claim
that every change reran a paid benchmark. Their raw result bundles are not
checked in, so they are not independently reproducible from this checkout. The
demo manifest only binds the compact fixture and states that limitation; it
does not promote the fixture into proof of the upstream run. Fresh benchmark
work is required when parser, ingest, store signature, retrieval behavior, or a
material answer contract changes. Because the latest calculation changes include
candidate-conflict, dependency-precedence, prepared-value stale repair,
stale-repair provenance synchronization, and dependency trace isolation, their
unit/contract evidence must not be presented as a refreshed benchmark result.

## Reviewer Evidence Surface

- Product and quick start: [README.md](../../README.md)
- Five-minute summary: [portfolio_one_pager.md](portfolio_one_pager.md)
- Experiment narrative: [portfolio_experiment_report.md](portfolio_experiment_report.md)
- Demo evidence manifest:
  [evidence_manifest.json](../../tests/fixtures/portfolio_demo/evidence_manifest.json)
- Publication validation workflow:
  [validation.yml](../../.github/workflows/validation.yml)
- Runtime architecture and stop lines:
  [core_runtime_surface_refactoring_plan.md](../architecture/core_runtime_surface_refactoring_plan.md)
- Benchmark operation and interpretation: [benchmarking.md](../evaluation/benchmarking.md)
- Detailed experiment chronology: [experiment_history.md](../history/experiment_history.md)
- Core simplification chronology: [implementation_history.md](../history/implementation_history.md)

Reviewer-facing claims should resolve through these documents and the compact
source-controlled fixtures they reference. Local `benchmarks/results/**` data is
not part of the published product surface.

## Active Blockers

There is no known unit/contract correctness blocker in the single-agent path.
The current evidence limitation is explicit: the calculation owner slice passed
focused and full regression tests, but its benchmark refresh has not run.
Optional MAS and cache-promotion work is intentionally disabled or experimental
rather than an incomplete product requirement.

The July canonical public-projection milestone is complete, but the broader
single-calculation-path Phase 3 remains open. Named operand and dependency owners
now cover main/late/terminal precedence, required-candidate merge, direct
structured acceptance, direct structured-evidence scoring, table-label metadata
lookup scoring, direct target-metric fallback conflict disposition, single-row
embedded/rendered-unit normalization repair, shared-context multi-row ratio
display-unit alignment, preferred-slot and recovered-context adoption, post-
coercion LLM selection, scalar plan disposition, ratio-artifact conflict selection,
two-stage post-candidate finalization, structured-provenance adoption, dependency-
source ratio-result projection, dependency-row unit inference, task-output
normalized-KRW consistency, prepared structured-unit/source-slot equivalence, and
required-operand prose numeric-evidence surface filtering, plus retrieved ratio-
context task-metric surface detection.
Named answer-slot,
calculation, and aggregate owners cover ratio result/primary-slot display
consistency, source-task display compatibility, deterministic planning/execution,
stale and generated provenance
handling, collapsed-ratio magnitude transformation, candidate
packaging/application and final-answer synchronization, nested aggregate-row
consistency, prepared projection-row surface synchronization, and prepared
lookup-slot to arithmetic component/series/delta synchronization, plus compact
aggregate-synthesis prompt-row projection backed by the shared public runtime-
trace material predicate. The aggregate owner also owns the plain subtask numeric-
conflict and direct-source-reference predicates, including their asymmetric
numeric equivalence and fixed source-cleaning contracts. The task-artifact
owner also covers prepared late aggregate-artifact payload/summary replacement,
a private ten-field operand-ref collector, and public prepared reconciliation
evidence-ref enrichment, while the aggregate-state owner covers the public
composition carrier and its common answer/claim/projection/lock/feedback
transition. The aggregate projection
owner also exposes the canonical aggregate-result signature and growth operand
sign-consistency rank primitives.
The numeric-surface owner additionally covers private table-support text assembly,
public prepared evidence promotion, and plain numeric-answer coverage/outside-
reference comparison. Graph keeps all comparison target construction and 12 call
placements/polarity, public and structured projection, preservation and scoring,
arithmetic synchronization, stale/initial-state and evidence-support policy, all
final-answer evidence candidate/support/selection gates, local row/metadata
preparation, retrieved-narrative skipping, later filtering, and final orchestration.
The graph still owns
operand/evidence adapters and builders, direct-row coercion and scope/target policy,
direct structured preference applicability, runtime evidence preparation, row
matching/iteration, peer-unit preparation, strongest-slot building,
query/report-scope score augmentation, ambiguity/tie-break and sequential adoption,
recovered-context eligibility and row/evidence construction, producer-scope filtering, lazy coherent-context
construction, retry and
query gates, LLM invocation plus evidence/scope/id/coercion/applicability and
exception/fallback orchestration, candidate preparation/execution plus
state/task/artifact projection, repair acceptance, artifact/ledger conflict
construction and short-circuit, dependency formatter, recalculated-value coercion,
dependency-row construction, stateful structured-provenance lookup,
dependency row-coercion and table-metadata-repair predicate call placement,
evidence-driven sibling candidate alignment and preparation/map propagation,
downstream evidence coercion/append,
collapsed-ratio trace/eligibility/completeness/query gates and prepared copies,
downstream coherence/answer/coverage/final projection, aggregate/filter sequencing,
aggregate nested-result promotion, preliminary/final projection rebuild,
dependency alignment and preserved-field merge,
required-operand/evidence list preparation and direct-grounding computation around
the prose numeric-evidence filter call, narrative/restriction gates, surface-result
merge/dedupe/logging and later missing-required fallback-row merge,
retrieved ratio-context existing-result iteration and family/task/signature/status/
artifact-backed/value/completeness/tolerance gates around the metric-surface owner
call, logical conflict inversion and downstream recalculation/adoption,
source-task/source-slot lookup and material gate, truthy display-compatibility call
placement, True-path source adoption, False-path rendered/raw fallback, and later
growth calculation/material/state/artifact orchestration,
aggregate candidate discovery/scoring/selection, narrative refresh, packaging
and composition-transition call placement/laziness, application invocation/
broader answer precedence, aggregate-synthesis LLM/model/prompt setup,
post-period-realignment inputs, JSON/debug/prompt and structured-LLM invocation,
catch/fallback, mutable state/evidence,
aggregate task-ledger conflict/fallback disposition, projection sentence scoring
and arithmetic-surface synchronization around the numeric-conflict calls, the
status/material/direct-source/family/conflict/sign-rank chain inside full nested
promotion,
final-answer table-support owner call placement and returned-row adoption inside
the broader evidence filter,
aggregate evidence/kept-id selection, rebuild gating, selected-claim filtering,
surface-operand append, lookup primary-slot preparation/gating, per-row task
mapping/propagation and rebuild, the initial late-artifact copy and ratio/render/
completeness/formatter/projection-mutation/`None`/blank-id gates, aggregate artifact
creation/finalization, broader artifact/ledger work, stale repair and final orchestration,
other absolute-ratio handling, and other
deterministic/LLM fallbacks. Broader ledger synchronization and the private
helper mesh are also open. No current result supports a whole-ledger,
end-to-end owner, total-code reduction, or broad performance claim.

Open work should be created only when one of these conditions is met:

- a reproducible runtime or evidence-faithfulness regression appears;
- a reviewer-facing demo cannot explain a core contract;
- a dependency, parser, ingest, or store-signature change requires new evidence;
- a real caller still depends on a compatibility path scheduled for removal.

## Next Work

The final README-first walkthrough is complete. The primary path now runs one
fixture-backed command and exposes semantic planning, hybrid retrieval,
deterministic calculation, provenance, task/artifact integrity, and critic
acceptance in a coherent trace. Optional cache and promotion surfaces are
separate deep-validation paths.

The next bounded architecture work is the prepared calculation-operand slot
overlay. Move only graph `_updated_operands_from_slots` (`12513-12540`) to the
plain public API
`financial_runtime_trace.overlay_calculation_operands_from_slots(trace: Mapping[str, Any], slot_by_role: Mapping[str, Mapping[str, Any]], *, normalize_role: bool = False) -> List[Dict[str, Any]]`.
Replace its two calls in place at `12506` and `12764`. Add no wrapper, carrier,
reason, flag, callback, config input, compatibility alias, or trace field. The
runtime-trace owner already imports `Mapping`, `Any`, `Dict`, `List`, and the
normalizer; the calculation graph already consumes that owner, which has no
reverse graph dependency, so no new edge or cycle is required.

Characterization must first evaluate `trace` truthiness, then
`calculation_operands` access and truthiness, and then materialize the operand list
before processing a row. The owner always creates a fresh result list and shallow-
copies every operand in stable input order. Per row it resolves a role through
truthy `matched_operand_role`, then lazy `role`, then `""`, and stringifies that
surface. `normalize_role` is tested per row; when truthy, whitespace normalization
and lowercasing affect only the lookup key. Do not strip or lowercase the default
path.

The owner calls `slot_by_role.get(role)` for each copied row. A missing or falsy
slot leaves that fresh row otherwise unchanged. A truthy slot overwrites exactly
`raw_value`, `raw_unit`, `normalized_value`, `normalized_unit`, `source_row_id`,
`source_row_ids`, and `source_anchor` in that order, including overwriting stale
values with `None` when a key is absent. Slot values and unrelated nested values
retain their exact identities; the input trace, operands, slot map, and slots stay
unmodified. Catch no truthiness, mapping/list materialization, iteration, copy,
getter, string, normalization, lowercasing, update, or other exception, and do not
dedupe, tuple-convert, pre-copy the slot map, or cache role resolution across rows.

The collapsed-ratio repair call at `12506` retains graph construction of the
numerator/denominator role map and passes the exact original trace with the default
`normalize_role=False`. It adopts the returned list unconditionally, including a
fresh empty list, before assigning the repaired calculation result. The single-
period comparison call at `12764` retains graph construction of current/prior plus
minuend/subtrahend aliases, passes `normalize_role=True`, and replaces trace
operands only when the returned list is truthy; an empty result preserves the
existing trace operand surface. Both callers retain every evidence, applicability,
ranking, formula, slot/result repair, realignment, and state/finalization gate.
Owner exceptions stop their later assignment or return work.

Current-source profiling reaches the helper four times across three fixtures with
the full 1,531-test baseline green: two default-mode calls in two collapsed-ratio
fixtures and two normalized-mode calls from one period-comparison fixture. Every
observed call has two operands, uses truthy `matched_operand_role`, and matches both
slots; direct behavioral references are zero and the integrations assert repaired
answers/results rather than operand overlay identity or fields. Add compact direct
behavior/identity and access/exception methods covering empty and poisoned traces,
role precedence and fallback, exact versus normalized keys, missing/falsy/truthy
slots, fixed seven-field overwrite order, stable duplicate rows, fresh list/row
identity, nested aliases, immutability, and representative propagated exceptions.
Add one focused wiring fixture per caller to pin exact prepared arguments, default
versus normalized mode, unconditional-empty versus truthy-only adoption, result
identity, earlier owner-zero gates, and exception stop without asserting broad
repair outputs.

Acceptance deletes only the 28 graph definition lines, leaves one public owner
definition and two graph calls, and requires the old definition, self references,
wrappers, and aliases to be zero. Stop before graph
`_runtime_evidence_rows_with_context_docs` (`12542`). The allowed claim is only
prepared role-slot-to-calculation-operand overlay ownership and old-body deletion—
not collapsed-ratio or period evidence selection, ranking, formula/query policy,
slot/result repair, realignment, call placement or adoption policy, state/artifact
or final orchestration, behavior improvement, performance, total-code or executed-
path reduction, broader private-mesh cleanup, or Phase 3 completion. The broader
evidence-local unit cluster remains deferred because its regex, policy, shared-
surface, and callback boundaries need separate characterization.
The Phase 3 backlog in the refactoring plan is unordered; this section is the
authority for priority.

Before publishing a new score for the latest calculation changes, verify that a
local store matches the active profile and cache signature, then prefer a
monitored store-fixed `eval-only` refresh. If that cannot be established, keep
the benchmark status as not run.

Do not combine multiple architecture slices into another broad refactor or start an
all-at-once test split, new MAS capability, or cache-serving path without a
concrete blocker.
Oversized tests are split only when their public contract is being changed.

## Session Handoff

A new session should read, in order:

1. [AGENTS.md](../../AGENTS.md)
2. [CONTEXT.md](../../CONTEXT.md)
3. this document
4. `git status -sb`
5. `git log -5 --oneline`

Repository documents and Git history override ChatGPT/Codex memory for current
commits, blockers, benchmark results, API/model state, and artifact locations.
