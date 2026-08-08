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
  source checkpoint; use `git log` for its exact commit. The branch has not been
  pushed or merged.
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
- Prepared preferred-slot adoption now has a typed state-free operand-resolution
  owner. It preserves higher/equal-score rejection, ratio peer-unit alignment,
  exact row overlay, top-level copy/nested identity, sequential row application,
  and input immutability. Its reasons are contract outputs, not runtime trace
  fields. The graph retains runtime evidence overlay, row matching and iteration,
  peer-unit preparation, and the strongest-slot builder and scoring.
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
- At the current checkpoint, `financial_graph_calculation.py` is 19,676 lines,
  `financial_aggregate_projection.py` is 427,
  `financial_operand_resolution.py` is 2,270,
  `financial_dependency_projection.py` is 3,089, and
  `financial_calculation_execution.py` is 837. These figures are not a
  total-code or broad executed-path/performance reduction claim.
- The latest calculation checkpoint passed targeted 5/5 and affected 296/296
  tests, the 217-literal runtime audit, and full discovery over 1,490/1,490 tests.
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
| Generic operand candidate resolution | `financial_operand_resolution.py`; owns coherent-first required-candidate merge, complete-ratio candidate-first/current-first precedence, ordered typed direct structured acceptance, prepared preferred-slot adoption/overlay, recovered-context merge/replacement plus referenced-evidence adoption, post-coercion per-row lookup direct-support, and required match/surface, lookup-rematch, direct-first merge while graph retains scope/target policy, model/evidence/id/coercion/applicability/exception/fallback orchestration, stateful preferred-slot preparation/scoring, recovery eligibility/builders/logging, and ratio-recovered/runtime projection |
| Dependency binding summary, projection, source-set selector, typed main/late/final application, recalculation plan disposition, prepared ratio-artifact conflict selection, two-stage post-candidate finalization, and prepared structured-provenance adoption | `financial_dependency_projection.py`; the provenance seam mutates the graph-built row in place after graph-owned stateful lookup, while graph retains row construction/normalization and evidence coercion/append; Stage 1 owns candidate field copies and result-status disposition, Stage 2 owns truthy formatted-result/final-row projection, while graph retains raw-plan and candidate construction/execution, recalculated-value coercion and invalid-value artifact-builder laziness, absolute-ratio query/transform invocation, task-artifact/ledger conflict short-circuit, formatter, caller iteration/projection, repair acceptance, other fallback, and aggregate sequencing |
| Deterministic difference/growth plan decision, primary plan validation, formula execution, and value-only stale freshness assessment | `financial_calculation_execution.py`; state-free construction plus typed raw/guarded selection are owner-owned, while the state/query adapter, lazy dependency raw-plan construction, and primary runtime/task/artifact projection remain graph-owned; dependency receives the raw plan explicitly and broader ledger synchronization remains open |
| Aggregate projection, stale provenance selection, and prepared collapsed-ratio magnitude transformation | `financial_aggregate_projection.py`; canonical aggregate operation-family normalization, typed state-free target selection, and the result/slot/primary prepared-copy transform are owner-owned, while trace/eligibility/completeness/query gates, downstream coherence/answer/coverage, acceptance/filter sequencing, and final projection remain graph-owned |
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
| Latest calculation runtime checkpoint | PASS: targeted 5/5 and affected 296/296 tests on 2026-08-09 |
| Runtime domain-term audit | PASS, 217 reviewed literals on 2026-08-09 |
| Full unittest discovery | PASS, 1,490/1,490 tests locally on 2026-08-09 |
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
single-calculation-path Phase 3 remains open. Dependency precedence, late merge,
terminal finalization, required-candidate merge, direct structured acceptance,
prepared preferred-slot adoption, recovered-context adoption, scalar plan
disposition, post-coercion LLM operand selection, deterministic plan/execution,
prepared ratio-artifact conflict selection, two-stage dependency post-candidate
finalization, prepared dependency structured-provenance adoption, and pure aggregate provenance
selection have named owners. The graph still owns
operand/evidence adapters and builders, direct-row coercion and scope/target policy, direct
structured preference applicability, runtime evidence preparation, row
matching/iteration, peer-unit preparation and strongest-slot scoring,
recovered-context eligibility and row/evidence construction, producer-scope filtering, lazy coherent-context
construction, retry and
query gates, LLM invocation plus evidence/scope/id/coercion/applicability and
exception/fallback orchestration, candidate preparation/execution plus
state/task/artifact projection, repair acceptance, artifact/ledger conflict
construction and short-circuit, dependency formatter, recalculated-value coercion,
dependency-row construction/normalization, stateful structured-provenance lookup,
downstream evidence coercion/append,
collapsed-ratio trace/eligibility/completeness/query gates and prepared copies,
downstream coherence/answer/coverage/final projection, aggregate/filter sequencing,
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

The next bounded architecture work is to characterize and relocate only the pure
`_direct_structured_lookup_evidence_score`
(`financial_graph_calculation.py:1725-1838`) into
`financial_operand_resolution.py`, deleting that graph scorer body. The operand
owner should expose typed score input/result contracts that receive only the
operand and evidence item, with the internal reasons
`no_structured_cells`, `surface_contract_not_satisfied`, and `evidence_scored`;
those reasons are contract outputs, not runtime trace fields. Before moving it,
define the neutral-owner
boundary for `_operand_prefers_aggregate_value_role`
(`financial_graph_helpers.py:3548-3559`): co-locate and expose that predicate from
the operand owner, then update graph and graph-helper consumers through one-way
imports. Do not make the operand owner import `financial_graph_helpers.py`, and
do not replace the predicate with an eagerly computed boolean that changes
evaluation or exception order.

Characterization must lock the exact score-component matrix and input
immutability: missing structured cells, required positive-surface gating,
exact/fuzzy row and semantic labels, numeric-cell normalization and header
affinity, direct-row and single/multi-cell adjustments, adjustment/detail
penalties, preferred aggregate role/stage bonuses, normalization failure, and
exception propagation. The graph must retain
`_best_direct_lookup_slot_from_evidence_pool` (`1922-2229`), evidence iteration,
query/report-scope scoring, ambiguity and tie-break policy, and the outer
sequential preferred-slot adoption loop (`2231-2292`). No graph state, callback,
or batch precomputation should cross the scorer boundary.

The allowed structural claim is scorer ownership plus deletion of that one
private aggregate-role predicate. It is not a claim that preferred-slot building,
selection, sequential adoption, the broader private mesh, total code, executed
paths, or performance have been reduced.

The prepared aggregate final-answer mutation helper
(`financial_graph_calculation.py:4927-4946`) is a safe but lower-semantic runner-up
and remains an unordered backlog item rather than a precedence claim. Aggregate
stale-repair/precedence, other ratio/absolute handling, broader ledger
synchronization, remaining fallbacks, private facade/API cleanup, and further
test co-location also remain separate work. The Phase 3 backlog in the
refactoring plan is unordered; this section is the authority for priority.

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
