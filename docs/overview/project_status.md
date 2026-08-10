# Project Status

> Single authority for current product state, gates, blockers, and priority.
> Stable runtime semantics live in
> [agent_runtime_contract.md](../architecture/agent_runtime_contract.md); completed
> implementation and experiment chronology live in
> [implementation_history.md](../history/implementation_history.md) and
> [experiment_history.md](../history/experiment_history.md).

Last updated: 2026-08-10

## At A Glance

| Question | Current answer |
| --- | --- |
| What is the product? | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Is the core path blocked? | No known unit/contract correctness blocker |
| What is the architecture state? | Phase 3 OPEN; narrative-answer validation owner milestone closed, four named debt groups remain |
| What just changed? | Narrative intent/signal, answer completeness, and growth numeric-trace guards moved to `financial_answer_projection.py` in `d6723b8`, `04a8b3c`, and `fd82367` |
| What passed? | Focused 4/4, migrated 12/12, affected seven-module set 690/690, runtime audit 217, full unittest 1,594/1,594 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | Three characterize-first operand-preparation seams into `financial_operand_resolution.py`; graph orchestration remains a hard stop |

## Product Boundary

The reviewer-facing product is the single-agent `FinancialAgent` runtime:

1. preserve DART section and table structure during ingest;
2. retrieve through dense/BM25 hybrid search and structure-aware expansion;
3. use an LLM for intent and semantic planning;
4. bind operands and execute calculations deterministically;
5. return evidence-backed answers with calculation and provenance traces.

MAS, report-cache promotion, evaluators, benchmark runners, and extended review
workflows are optional or experimental. They must not load during default imports
or an unconfigured `FinancialAgent` invocation.

## Current Source State

- PRs #79 through #84 completed the July portfolio-core simplification; PR #85
  compressed the earlier handoff documents. Latest confirmed upstream merge is
  `main@f0a5145`.
- The local checkpoint is the current HEAD of
  `codex/finalize-five-minute-review`; use `git log` for the exact commit. It is
  not represented here as pushed or merged.
- Canonical numeric output is `resolved_calculation_trace`, explicit
  `structured_result`, and task/artifact projection. Default output does not
  revive top-level `calculation_*` compatibility mirrors.
- Default import and deterministic invocation gates isolate MAS, evaluator,
  benchmark, promotion, portfolio-review, and persisted cache-index code.
- Tracked benchmark output remains limited to compact history-linked summaries
  and diagnostics. Full bundles, stores, caches, and heartbeat logs are local-only.
- The latest owner batch moved narrative intent/signal, answer truncation/context
  coverage, source-stated growth, and untraced numeric guards behind seven public
  answer-projection APIs. All 36 calls remain in the graph and retired old
  identifiers are zero. Query/evidence preparation, answer composition/refresh,
  promotion, sync/rebuild, mutable state/evidence, ledger, callbacks, and final
  sequencing remain graph-owned. This is ownership relocation, not a behavior or
  performance claim.
- Current physical sizes are: calculation graph 17,097 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, operand resolution 3,105, and aggregate projection
  1,511.

Exact behavior, laziness, identity, exception, and caller-placement contracts are
kept in [agent_runtime_contract.md](../architecture/agent_runtime_contract.md).
Commit-level diffs and validation are kept in
[implementation_history.md](../history/implementation_history.md).

## Runtime Ownership

| Surface | Current owner and boundary |
| --- | --- |
| Public entry | `FinancialAgent.run()` |
| DART ingest | parser modules plus canonical profile in `src/config/runtime_contract.py` |
| Retrieval | `financial_retrieval_pipeline.py`; graph evidence owns structure expansion and evidence construction |
| Calculation orchestration | `financial_graph_calculation.py`; reads graph state, prepares inputs, places owner calls, and projects state/task/artifact results |
| Operand policy and resolution | `financial_operand_resolution.py`, including ratio denominator sign policy and evidence-local unit/period coercion |
| Dependency and execution | `financial_dependency_projection.py` and `financial_calculation_execution.py` |
| Calculation rendering | `financial_graph_calculation_rendering.py`, including ratio unit/query/result projection and scalar/time-series display helpers |
| Answer and numeric surfaces | `financial_answer_slots.py`, `financial_answer_projection.py`, and `financial_numeric_surface.py`, including period/material, ratio-readiness, narrative validation, and numeric/scale predicates |
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, source/coherence preparation, result/nested ranks, and stable dedupe |
| Composition, trace, artifacts | `financial_aggregate_state.py`, `financial_runtime_trace.py`, and `financial_task_artifacts.py` |
| Optional systems | `src.experimental.mas` and explicitly configured cache/eval/review paths |

For topology rather than normative behavior, use
[runtime_flow_roles.md](runtime_flow_roles.md).

## Current Gate Status

| Gate | Latest status |
| --- | --- |
| Runtime contract gate | Recorded PASS; upstream raw bundle local-only |
| Hard structural numeric gate | Recorded PASS, 5 / 5; upstream raw bundle local-only |
| Concept runtime gap gate | Recorded PASS, 7 / 7; upstream raw bundle local-only |
| Policy-driven runtime gate | Recorded PASS; upstream raw bundle local-only |
| Expanded structural numeric gate | Recorded PASS, 9 / 9; upstream raw bundle local-only |
| Plain-retrieval comparison | Recorded 5 / 9 diagnostic baseline; not synchronized after later repairs |
| Reflection promotion gate | READY |
| Report-cache promotion evidence | READY, serving disabled |
| Promotion trace materiality gate | READY |
| REFERENCE_NOTE capability gate | READY, Researcher context-only |
| Demo fixture contract | `fixture_contract_ready`; manifest verified, live replay false |
| Portfolio review surface | `review_surface_ready`; unit suite and audit are `not_run` by that command |
| Latest focused owner checkpoint | PASS, 4 / 4 |
| Latest migrated narrative checkpoint | PASS, 12 / 12 |
| Latest affected regression set | PASS, seven-module set 690 / 690 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,594 / 1,594 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The affected set is `tests.test_financial_answer_projection`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, `tests.test_lookup_recovery_policy`,
`tests.test_financial_aggregate_rank_dedupe`, and `tests.test_operation_contracts`.

Recorded structural and plain-retrieval numbers are historical evidence, not a
claim that the latest owner changes reran a paid benchmark. Their upstream raw
bundles are not checked in and are not independently reproducible from this
checkout. A fresh benchmark is required before publishing a new score after a
material parser, ingest, store-signature, retrieval, or answer-contract change.

## Active Blockers And Remaining Debt

| Area | State |
| --- | --- |
| Core correctness | No known unit/contract blocker |
| Latest benchmark evidence | Limited: refresh not run after the latest calculation changes |
| Phase 3 | Open; owner moves do not establish an end-to-end calculation or ledger owner |
| Optional MAS/cache serving | Intentionally disabled or experimental, not a product blocker |

The durable Phase 3 debt is:

| Debt group | Progress boundary |
| --- | --- |
| Aggregate repair and precedence | Partially advanced through period/material/source/coherence/rank/dedupe and narrative-validation ownership; promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale ownership; graph-state lookup and surrounding orchestration remain graph-owned |
| Broader task/artifact ledger synchronization | Essentially untouched; requires a separate behavior contract |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The next architecture batch is one three-commit, one-owner characterize-first
operand-preparation sequence into `financial_operand_resolution.py`:

1. publish `repair_krw_normalized_values_from_raw_units(...)` (47 old graph
   definition-span lines, one graph call);
2. publish `align_growth_operand_units_when_raw_scale_matches(...)` (90 lines,
   one graph call);
3. publish `growth_operand_periods_conflict(...)` (24 lines, one graph call).

The read-only profiled boundary is three public APIs, 161 old graph
definition-span lines, and three external graph calls, with no selected
owner-local absorption. The owner already uses runtime normalization; the second
seam adds its existing `_parse_number_text`, and the third adds public
`period_match_key` from answer slots. The dependency direction is graph → operand
resolution → runtime normalization/answer slots, with no reverse import from
those dependencies to the owner. Commit order is A → B → C, not a dependency
arrow. This inventory is not a completion or schedule estimate.

The adjacent `_complete_required_operand_from_ontology` is explicitly excluded:
it has two graph calls and depends on graph-helper-private
`_concept_spec_for_key`, while graph helpers already import operand resolution;
moving it as-is would create a reverse cycle. Require at least four CURRENT-SOURCE
characterize methods per seam: two direct branch/identity/laziness/exception/
no-mutation methods, one exact-one static binding/order method, and one executable
caller adoption/exception-stop method. Keep source held until those focused tests
are green, then use a direct public graph import and delete the old body.
The graph retains `_prepare_calculation_candidate`: repair stays after table-
metadata repair and before operand indexing/plan access; alignment stays after
donor-unit propagation and before duplicate-prior recovery; conflict stays after
that recovery and before sign policy/execution. Caller/carrier preparation,
adoption, and failure projection stay graph-owned.
Definition-movement hard stops are `_repair_krw_operand_units_from_table_metadata`,
`_recover_duplicate_growth_prior_operand`, and `_late_runtime_numeric_answer`.
Do not absorb ontology completion, evidence recovery, duplicate-prior recovery,
graph state, carriers, callbacks, task/artifact ledger, promotion, sync/rebuild,
or final orchestration. No behavior, accuracy, ranking, performance, total-code
or executed-path reduction, benchmark, or Phase 3 completion claim follows.

Run focused tests, the affected set, domain audit, full discovery, and
`git diff --check` sequentially. Benchmark work remains separate: before
publishing a new score, verify the local store/profile/cache signature and prefer
a monitored store-fixed `eval-only` refresh.

Priority is owned by this section. The durable plan records debt and stop lines,
not a competing queue.

## Reviewer Evidence Surface

- Product and quick start: [README.md](../../README.md)
- Five-minute summary: [portfolio_one_pager.md](portfolio_one_pager.md)
- Experiment narrative: [portfolio_experiment_report.md](portfolio_experiment_report.md)
- Demo evidence manifest:
  [evidence_manifest.json](../../tests/fixtures/portfolio_demo/evidence_manifest.json)
- Publication workflow: [validation.yml](../../.github/workflows/validation.yml)
- Architecture debt and stop lines:
  [core_runtime_surface_refactoring_plan.md](../architecture/core_runtime_surface_refactoring_plan.md)
- Benchmark interpretation: [benchmarking.md](../evaluation/benchmarking.md)
- Implementation chronology: [implementation_history.md](../history/implementation_history.md)
- Experiment chronology: [experiment_history.md](../history/experiment_history.md)

Local `benchmarks/results/**` data is not part of the published product surface.

## Session Handoff

Read in order:

1. [AGENTS.md](../../AGENTS.md)
2. [CONTEXT.md](../../CONTEXT.md)
3. this document
4. `git status -sb`
5. `git log -5 --oneline`

Repository documents and Git history override ChatGPT/Codex memory for current
commits, blockers, benchmark results, API/model state, and artifact locations.
