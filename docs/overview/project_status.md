# Project Status

> Current repository state only. Start with [README.md](../../README.md), then
> [portfolio_one_pager.md](portfolio_one_pager.md) and
> [portfolio_experiment_report.md](portfolio_experiment_report.md). Historical
> implementation and experiment details live in
> [implementation_history.md](../history/implementation_history.md) and
> [experiment_history.md](../history/experiment_history.md).

Last updated: 2026-08-09

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
- At the current checkpoint, `financial_graph_calculation.py` is 18,877 lines,
  `financial_graph_helpers.py` is 6,311,
  `financial_graph_reconciliation.py` is 2,428,
  `financial_lookup_recovery.py` is 609,
  `financial_answer_slots.py` is 594,
  `financial_aggregate_projection.py` is 1,019,
  `financial_aggregate_state.py` is 161,
  `financial_operand_resolution.py` is 2,610,
  `financial_dependency_projection.py` is 3,187,
  `financial_task_artifacts.py` is 1,180, and
  `financial_calculation_execution.py` is 837. These figures are not a
  total-code or broad executed-path/performance reduction claim.
- The latest calculation checkpoint passed targeted 4/4 and affected 632/632
  tests, the 217-literal runtime audit, and full discovery over 1,505/1,505 tests.
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
| Generic operand candidate resolution and unit normalization/alignment | `financial_operand_resolution.py`; owns coherent-first required-candidate merge, complete-ratio candidate-first/current-first precedence, ordered typed direct structured acceptance, typed direct structured-evidence base scoring and the neutral ordered aggregate-role predicate, prepared preferred-slot adoption/overlay, recovered-context merge/replacement plus referenced-evidence adoption, post-coercion per-row lookup direct-support, required match/surface, lookup-rematch, direct-first merge, the plain embedded/rendered single-row repair, and shared-context multi-row ratio display-unit alignment while graph retains scope/target policy, model/evidence/id/coercion/applicability/exception/fallback orchestration, stateful preferred-slot preparation, query/report-scope score augmentation, ambiguity/tie-break, recovery eligibility/builders/logging, ratio-recovered/runtime projection, row construction/provenance, plan/map propagation, evidence-driven sibling candidate alignment, and ratio append/merge policy |
| Dependency binding summary, projection, source-set selector, typed main/late/final application, recalculation plan disposition, prepared ratio-artifact conflict selection, two-stage post-candidate finalization, prepared structured-provenance adoption, prepared dependency-source ratio-result projection, and dependency-row unit inference | `financial_dependency_projection.py`; the provenance seam mutates the graph-built row in place after graph-owned stateful lookup, the ratio-result seam builds the fresh canonical result/slot containers with exact source/component aliases, and the plain unit primitive preserves slot-before-sibling raw precedence plus `UNKNOWN`-only policy inference; graph retains row construction/normalization and conditional re-inference, evidence coercion/append, raw-plan and candidate construction/execution, source-slot selection and component ranking, ratio/query/absolute policy, source-id cleaning, task-artifact/ledger conflict short-circuit, compact formatting, caller iteration/projection, repair acceptance, other fallback, and aggregate sequencing |
| Deterministic difference/growth plan decision, primary plan validation, formula execution, and value-only stale freshness assessment | `financial_calculation_execution.py`; state-free construction plus typed raw/guarded selection are owner-owned, while the state/query adapter, lazy dependency raw-plan construction, and primary runtime/task/artifact projection remain graph-owned; dependency receives the raw plan explicitly and broader ledger synchronization remains open |
| Answer slots and ratio result-display synchronization | `financial_answer_slots.py`; owns answer-slot construction plus typed calculation-result/primary-slot display consistency, including formula-mismatch copy versus ordinary in-place update and current-surface/percent-policy/exception order, while graph callers retain ordered-row gating and propagation, compact-answer construction, and state/task/operand/period/metric formatting |
| Aggregate projection, stale provenance selection, signature/sign rank, prepared collapsed-ratio magnitude transformation, answer-candidate packaging/application/final-answer synchronization, generated-provenance filtering, nested-row consistency, prepared projection-row surface synchronization, and prepared arithmetic-component synchronization | `financial_aggregate_projection.py`; canonical operation-family normalization, aggregate-result signature and growth sign-consistency primitives, state-free target selection, prepared result/slot transforms, candidate packaging/application, claim-id merge, provenance filtering, nested-row recursion, selected-row numeric/result/slot/lookup synchronization, and lookup-slot to component/series/delta synchronization are owner-owned, while full dedupe/rank tuples/nested promotion, evidence/kept-id and candidate/sentence selection, conflict/coverage/render gates, lookup primary-slot preparation and gating, per-row task mapping/propagation, rebuild gating, selected claims, surface-operand append, mutable state/evidence, artifact/ledger, stale repair, downstream coherence/answer/coverage, and final orchestration remain graph-owned |
| Aggregate composition carrier and common transition | `financial_aggregate_state.py`; owns public `AggregateCompositionState` and the state-free answer/claim/projection/lock/feedback transition, while graph retains all producers and gates, call placement, sequential state handoff, later `_replace`, broader answer precedence, state/evidence/LLM work, and final orchestration |
| Task/artifact projection and prepared late aggregate-artifact payload synchronization | `financial_task_artifacts.py`; owns artifact/task projection helpers and typed first exact-id payload/summary replacement over graph-prepared artifacts, while graph retains the initial copy, ratio/render/completeness/formatter/projection mutation and `None`/blank-id gates, artifact creation/finalization, ledger-level id/order, and final orchestration |
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
| Latest calculation runtime checkpoint | PASS: targeted 4/4 and affected 632/632 tests on 2026-08-09 |
| Runtime domain-term audit | PASS, 217 reviewed literals on 2026-08-09 |
| Full unittest discovery | PASS, 1,505/1,505 tests locally on 2026-08-09 |
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
structured acceptance and evidence scoring, single-row embedded/rendered-unit
normalization repair, shared-context multi-row ratio display-unit alignment,
preferred-slot and recovered-context
adoption, post-coercion LLM selection, scalar plan disposition, ratio-artifact
conflict selection, two-stage post-candidate finalization, structured-provenance
adoption, dependency-source ratio-result projection, and dependency-row unit
inference. Named answer-slot,
calculation, and aggregate owners cover ratio result/primary-slot display
consistency, deterministic planning/execution, stale and generated provenance
handling, collapsed-ratio magnitude transformation, candidate
packaging/application and final-answer synchronization, nested aggregate-row
consistency, prepared projection-row surface synchronization, and prepared
lookup-slot to arithmetic component/series/delta synchronization. The task-artifact
owner also covers prepared late aggregate-artifact payload/summary replacement,
while the aggregate-state owner covers the public composition carrier and its
common answer/claim/projection/lock/feedback transition. The aggregate projection
owner also exposes the canonical aggregate-result signature and growth operand
sign-consistency rank primitives.
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
evidence-driven sibling candidate alignment and preparation/map propagation,
downstream evidence coercion/append,
collapsed-ratio trace/eligibility/completeness/query gates and prepared copies,
downstream coherence/answer/coverage/final projection, aggregate/filter sequencing,
aggregate nested-result promotion, preliminary/final projection rebuild,
dependency alignment and preserved-field merge,
aggregate candidate discovery/scoring/selection, narrative refresh, packaging
and composition-transition call placement/laziness, application invocation/
broader answer precedence, mutable state/evidence,
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

The next bounded architecture work is to characterize and relocate graph
`_dependency_task_output_has_consistent_krw_unit` (`15336-15355`) into
`financial_dependency_projection.py`. The owner should expose the plain public
predicate
`dependency_task_output_has_consistent_krw_unit(row: Mapping[str, Any]) -> bool`;
no dataclass, reason, flag, callback, or config input is required. Calls
at `10488` and `15447` must remain at their exact semantic positions and retain
their current laziness.

Characterization must preserve the short-circuit order for dependency-resolved,
`task_output:` source id, and normalized-KRW gates before any value work. Raw value
is read before raw-unit truthy fallback to result unit; a whitespace-only raw unit
therefore suppresses the fallback before normalization. Operand normalization,
expected-KRW gating, current-then-expected float conversion, and the exact scaled
tolerance `max(1e-6, abs(expected) * 1e-9)` remain unchanged for zero, negative,
invalid, and `NaN` values. Only float `TypeError` and `ValueError` are caught;
mapping, truthiness, string, normalizer, and other exceptions still propagate in
the existing order, and the row is never mutated.

Add a compact direct gate, access, fallback, normalization, tolerance, exception,
and immutability matrix. The existing dependency-output consistency fixture should
spy numerator and denominator row coercion followed by numerator and denominator
table repair, preserving the observed `False, True, False, True` results across
exactly four owner calls; an owner exception must stop later work. The current
read-only inventory observes 354 calls across 134 tests, split 313 and 41 between
the two production sites, but has no direct predicate contract.

Acceptance deletes only graph `15336-15355`, migrates both calls, leaves no old
definition or private self reference, and stops before
`_coerce_operand_row_from_evidence` and
`_repair_krw_operand_units_from_table_metadata`. The graph retains row coercion,
table-metadata repair, operand/evidence selection and mutation, state, and final
orchestration. The allowed claim is dependency task-output normalized-KRW
consistency-predicate ownership and the 20-line old-body deletion only, not broader
KRW or unit policy, row/table repair, dependency binding/evidence, total-code or
executed-path reduction, performance, broader private-mesh cleanup, or Phase 3
completion. The evidence-local unit-coercion cluster remains a medium-high-risk
follow-up because of its regex, callback, policy, and access-order surface; growth
raw-scale repair remains deferred until its hidden KRW and threshold policy debt is
named and characterized.
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
