# Project Status

> Current repository state only. Start with [README.md](../../README.md), then
> [portfolio_one_pager.md](portfolio_one_pager.md) and
> [portfolio_experiment_report.md](portfolio_experiment_report.md). Historical
> implementation and experiment details live in
> [implementation_history.md](../history/implementation_history.md) and
> [experiment_history.md](../history/experiment_history.md).

Last updated: 2026-08-08

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
  scope/target policy, the applicability gate, direct structured evidence
  preference/refinement, and recovered context/evidence adoption.
- At the current checkpoint, `financial_graph_calculation.py` is 19,792 lines,
  `financial_operand_resolution.py` is 1,953,
  `financial_dependency_projection.py` is 2,813, and
  `financial_calculation_execution.py` is 837. These figures are not a
  total-code or broad executed-path/performance reduction claim.
- The latest calculation checkpoint passed 7/7 targeted and 301/301 affected
  tests, the 217-literal runtime audit, and full discovery over 1,482/1,482 tests
  on Python 3.13. Benchmark refresh remains NOT RUN.

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
| Generic operand candidate resolution | `financial_operand_resolution.py`; owns coherent-first required-candidate merge, complete-ratio candidate-first/current-first precedence, and ordered typed direct structured acceptance while graph retains builders, scope/target policy, applicability gates, direct structured evidence preference/refinement, and recovered context/evidence adoption |
| Dependency binding summary, projection, source-set selector, typed main/late/final application, and dependency recalculation plan disposition | `financial_dependency_projection.py`; graph builds explicit raw plans and retains query gates, repair acceptance, other fallback, and aggregate sequencing |
| Deterministic difference/growth plan decision, primary plan validation, formula execution, and value-only stale freshness assessment | `financial_calculation_execution.py`; state-free construction plus typed raw/guarded selection are owner-owned, while the state/query adapter, lazy dependency raw-plan construction, and primary runtime/task/artifact projection remain graph-owned; dependency receives the raw plan explicitly and broader ledger synchronization remains open |
| Aggregate projection and stale provenance selection | `financial_aggregate_projection.py`; canonical aggregate operation-family normalization and typed state-free target selection are owner-owned, while acceptance/filter sequencing remains graph-owned |
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
| Latest calculation runtime checkpoint | PASS: 7/7 targeted and 301/301 affected tests on 2026-08-08 |
| Runtime domain-term audit | PASS, 217 reviewed literals on 2026-08-08 |
| Full unittest discovery | PASS, 1,482/1,482 tests locally on 2026-08-08 |
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
scalar plan disposition, deterministic plan/execution, and pure aggregate
provenance selection have named owners. The graph still owns operand/evidence
adapters and builders, direct-row coercion and scope/target policy, direct
structured evidence preference/refinement, recovered context/evidence
adoption, producer-scope filtering, lazy coherent-context construction, retry and
query gates, candidate preparation plus state/task/artifact projection, repair
acceptance, aggregate/filter sequencing, absolute-ratio handling, and other
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

The next bounded architecture slice is recovered context/evidence adoption at
the current `financial_graph_calculation.py:15145-15231` inside
`_extract_calculation_operands`. Keep document collection and context-row builders
in the graph, and move only the duplicated state-free adoption bodies at
`15165-15187` and `15208-15231` to the operand owner. Characterize the period
merge-versus-ratio replacement distinction, used-evidence filtering and order,
duplicate/existing evidence-id behavior, copy identity, and no-context laziness.
The function remains an 818-line graph adapter under the established
definition-to-next-definition count; do not split it by size alone.

After that, characterize direct structured evidence preference/refinement at
the current `financial_graph_calculation.py:15097-15112`. Its strongest-slot
builder and scoring remain graph-state dependent, so extract only a genuinely
state-free decision after its preparation/adoption seam is explicit. Then
characterize post-coercion LLM selection at the current
`financial_graph_calculation.py:15514-15535` as a separate slice. Preserve its
operand-id assignment, direct-support-before-surface evaluation order, enclosing
exception boundary, and absence of the direct-row ambiguity gate. Aggregate
repair/precedence selection, dependency post-candidate finalization, ratio
artifact/absolute orchestration, broader ledger synchronization, remaining
fallbacks, private facade/API cleanup, and contract-aligned test co-location
remain separate work. The Phase 3 backlog in the refactoring plan is unordered;
this section is the authority for priority.

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
