# Project Status

> Current repository state only. Start with [README.md](../../README.md), then
> [portfolio_one_pager.md](portfolio_one_pager.md) and
> [portfolio_experiment_report.md](portfolio_experiment_report.md). Historical
> implementation and experiment details live in
> [implementation_history.md](../history/implementation_history.md) and
> [experiment_history.md](../history/experiment_history.md).

Last updated: 2026-08-07

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
- The calculation owner slice makes the primary graph-state orchestration,
  state-free operand-resolution, and deterministic-execution boundaries
  explicit. Dependency-binding summary and direct-versus-dependency selector
  ownership are co-located without callback injection. The same dependency
  owner now returns the typed main-path application result for final ratio
  override or purge, producer-scope filtering, duplicate guarding, and
  missing-binding fill. The separate `b16a6c5` behavior fix prevents
  consolidation- or producer-scope-rejected dependency rows from re-entering
  through the active late snapshot. The dependency owner now also returns the
  typed late application result for coherent-first context merge,
  alignment/preference, complete-context veto, and dependency re-merge. The
  separate `c6f6fdf` behavior fix makes percent-point filtering terminal, so an
  empty filtered result cannot restore unfiltered post-main selected or active
  dependency snapshots. The behavior-preserving `5b44875` slice moves the
  generic normalized-unit filter and no-filter selected-first/dependency-second
  preservation into a typed finalization result. The separate `8ebb239` behavior
  fix recomputes empty and partial post-filter coverage. Graph-level evidence
  context builders plus retry, the percent-point query gate, logging, coverage
  and state projection, other fallback paths, and aggregate repair remain in the
  adapter. The original
  owner-extraction slice changed
  `financial_graph_calculation.py` from 21,642 to 19,682 lines while source as a
  whole grew by 1,095 lines. The typed main-path application changes the graph
  adapter from 19,686 to 19,587 lines while the two changed source files have a
  net increase of 109 lines as policy moves into the dependency owner.
  Product-runtime behavior is intended to remain unchanged; the precedence logic
  is relocated behind one owner contract rather than removed from the executed
  path.

The late-owner slice changes `financial_graph_calculation.py` from 19,587 to
19,564 lines and `financial_dependency_projection.py` from 2,656 to 2,760 lines.
The two source files have a net increase of 81 lines. Product-runtime behavior is
intended to remain unchanged; this slice relocates late precedence logic rather
than removing it from execution. Its typed reason is not currently projected to
the runtime trace.

After `c6f6fdf` moves the graph to 19,565 lines, the behavior-preserving
`5b44875` finalization relocation changes the graph to 19,567 lines and the
dependency owner from 2,760 to 2,833 lines, for a structural source net of 75
lines. The separate `8ebb239` coverage fix leaves the final graph at 19,576
lines. From the `77d5bff` baseline, the whole bounded slice changes the graph by
12 and the owner by 73 lines, for a two-source net of 85 lines. The executed
finalization policy moved owners; it was not removed from runtime. Neither the
late nor finalization reason is currently projected to the runtime trace.

The separate `f0eafae` behavior fix prevents repeated stale repair when a
source-stated display differs from formula precision but its traced formula
value still matches the current operands. Structural commit `2496fce` moves only
that bound-operand freshness assessment into `financial_calculation_execution.py`
as a typed state-free result. At that checkpoint, the graph still retained the
second `_execute_calculation()` and discarded recalculation projection.
Mechanically, the graph changes from 19,591 to 19,558 lines and the execution
owner from 614 to 712 lines, for a two-source net increase of 65 lines. From the
`73d593e` baseline, the whole stale-result bounded slice changes the graph from
19,576 to 19,558 lines and grows the execution owner by 98 lines, for a two-source
net increase of 80 lines.

Commit `406c1ef` separately characterizes stale execution snapshots. The
behavior-preserving `c2a5e96` decomposition then creates graph-private typed
candidate preparation, deterministic result projection, and state/ledger
projection seams. Stale repair uses the first two directly, removing its second
`_execute_calculation()` and discarded ledger/trace projection. The graph grows
from 19,558 to 19,730 lines (`+172`); full discovery at that checkpoint passed
1,473 tests. This is an internal graph decomposition, not an execution-owner move.

The separate `f2af4f4` behavior fix compares freshness with the prepared canonical
value. A raw pre-preparation value of 0.0035 that previously appeared current is
now compared with canonical 3.5 and repaired. An actual stale repair evaluates
the formula once instead of twice; current results still prepare and evaluate
once, and only stale values run result projection. The execution owner changes
from 712 to 679 lines (`-33`), the graph changes from 19,730 to 19,736 (`+6`), and
the source net is `-27`; the whole source/test diff is net `-83` lines. This does
not add ledger or selected-claim synchronization.

Validation follows the commit boundaries: `c6f6fdf` passed 3 focused contracts,
the 217-literal audit, and full discovery over 1,462 tests; `5b44875` passed 52
focused contracts, the same audit, and full discovery over 1,468 tests; after
`8ebb239`, 53 focused contracts, the same audit, and all 1,468 tests passed on
Python 3.13. After `f0eafae` and `2496fce`, 29 focused stale/execution contracts,
the same 217-literal audit, and all 1,472 tests passed on Python 3.13. The final
`f2af4f4` state passed 345 unique focused contracts; the core 7-contract subset
and 2 adapter/time-series spot contracts were also rerun. The 217-literal audit
and all 1,472 tests passed on Python 3.13. Benchmark refresh remains not run.

The Phase 5 completion change also removes chronological implementation diaries
from this current-state document and `CONTEXT.md`. Detailed pre-compression text
remains recoverable from `main@294b4ea`.

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
| Generic operand candidate resolution | `financial_operand_resolution.py` |
| Dependency binding summary, projection, source-set selector, typed main-path application, typed late dependency re-merge, and typed terminal finalization | `financial_dependency_projection.py`; query gating, other fallback, and aggregate precedence remain graph-owned |
| Primary plan validation, formula execution, and value-only stale freshness assessment | `financial_calculation_execution.py`; candidate preparation/result/state seams remain graph-private, and caller provenance/ledger synchronization remains open |
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
| Latest dependency-precedence focused contracts | PASS, 53 owner/graph tests after typed finalization and coverage repair on 2026-08-07 |
| Latest stale/candidate focused contracts | PASS, 345 unique focused tests after `f2af4f4` on 2026-08-07; core 7 and spot 2 were subset reruns |
| Runtime domain-term audit | PASS, 217 reviewed literals on 2026-08-07 |
| Full unittest discovery | PASS, 1,472 tests locally on Python 3.13 after prepared-value freshness repair on 2026-08-07 |
| Benchmark refresh after the latest calculation changes | NOT RUN; recorded benchmark evidence predates the latest behavior changes |
| GitHub Actions validation | Workflow defined; no remote run observed for the local branch |

The structural and plain numbers are retained recorded evidence, not a claim
that every change reran a paid benchmark. Their raw result bundles are not
checked in, so they are not independently reproducible from this checkout. The
demo manifest only binds the compact fixture and states that limitation; it
does not promote the fixture into proof of the upstream run. Fresh benchmark
work is required when parser, ingest, store signature, retrieval behavior, or a
material answer contract changes. Because the latest calculation changes include
candidate-conflict, dependency-precedence, and prepared-value stale-repair
behavior, their unit/contract evidence must not be presented as a refreshed
benchmark result.

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

Phase 3 also remains architecturally open: the dependency selector, binding
summary, typed main-path application, typed late re-merge, and typed terminal
finalization are co-located, but the graph adapter retains context/evidence
builders plus retry, the percent-point query gate, post-filter coverage and state
projection, other fallback paths, and aggregate repair. Private helper imports
are broad. The calculation candidate seam remains graph-private. Stale repair no
longer recursively calls `_execute_calculation()`, but its result provenance is not
synchronized into the ledger or selected claims as one behavior contract.
Dependency and period recovery still create state projections their callers
discard, and absolute-ratio/trend projection boundaries remain graph-owned. These
are named follow-ups, not hidden claims that the calculation monolith is resolved.

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

The next architecture change, if continued, should characterize stale-result
projection provenance and ledger/selected-claim synchronization as one bounded
behavior contract. Cleanup of the dependency and period recovery callers that
discard state projection should remain a separate slice. Aggregate precedence,
remaining deterministic/LLM fallbacks, absolute-ratio/trend projection debt, and
the private-API mesh remain separate follow-ups.

Before publishing a new score for the latest calculation changes, verify that a
local store matches the active profile and cache signature, then prefer a
monitored store-fixed `eval-only` refresh. If that cannot be established, keep
the benchmark status as not run.

Do not combine both architecture slices into another broad refactor or start an
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
