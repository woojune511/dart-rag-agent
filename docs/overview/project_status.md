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
| What is the architecture state? | Phase 3 OPEN; operand unit/table-repair owner milestone closed, four named debt groups remain |
| What just changed? | Dependency-task KRW consistency and table-metadata KRW repair moved to `financial_operand_resolution.py` in `25318f1` and `21f3a83` |
| What passed? | Focused 4/4, affected seven-module set 813/813, runtime audit 217, full unittest 1,614/1,614 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | Two characterize-first aggregate answer-surface commits into `financial_aggregate_projection.py`; graph orchestration remains a hard stop |

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
- The latest owner batch co-located dependency-task KRW consistency and table-
  metadata KRW repair behind two public operand-resolution APIs. Final placement
  is two external graph calls and one owner-local predicate call; old owner/private
  references are zero. Evidence/query/row preparation, caller carriers,
  adoption/failure, plan/execution, mutable state, artifacts, and final sequencing
  remain graph-owned. This is ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 16,770 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, operand resolution 3,461, dependency projection
  3,235, and aggregate projection 1,511.

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
| Operand policy and resolution | `financial_operand_resolution.py`, including ratio sign policy, evidence-local unit/period coercion, dependency-task KRW consistency, table-metadata/raw-unit repair, and growth alignment/period conflict |
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
| Latest affected regression set | PASS, seven-module set 813 / 813 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,614 / 1,614 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The affected set is `tests.test_financial_dependency_projection`,
`tests.test_financial_operand_resolution`, `tests.test_financial_calculation_execution`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, and `tests.test_operation_contracts`.

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
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, and unit/table repair; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Essentially untouched; requires a separate behavior contract |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The next architecture batch is one two-commit, one-owner characterize-first
aggregate answer-surface sequence into `financial_aggregate_projection.py`:

1. publish `row_is_narrative_summary(...)` (4 old definition-span lines, 20
   current calls) and `safe_partial_answer_for_numeric_gap(...)` (26 lines, four
   calls); the safe-partial call to the row predicate becomes owner-local;
2. atomically publish `compose_lookup_list_numeric_answer(...)` (27 lines) and
   `append_uncovered_lookup_numeric_items(...)` (92 lines), and co-locate private
   `_lookup_numeric_item_answer(...)` (34 lines).

The read-only profiled boundary is 183 old definition-span lines, four public APIs
plus one owner-private helper, and 28 current calls. Final placement is 23 external
graph calls and five owner-local calls: row predicate 17/3, safe partial 4/0,
compose 1/0, append 1/0, and private lookup 0/2. Commit B is atomic because the
current graph append helper calls private lookup; splitting it would require an
unwanted public helper, wrapper, or retained old body. Commit order is A then B,
not a dependency arrow or schedule estimate.

The owner already has answer-slot material, material-gap, numeric extraction, row
matching, and normalization dependencies. Add `answer_covers_numeric_answer` via
the existing numeric-surface direction and `CALCULATION_RENDER_POLICY`; neither
creates a reverse import.

A requires at least four CURRENT-SOURCE methods: direct row precedence/access/
exception; direct safe-partial status→gap→answer/formatted/rendered fallback,
stable dedupe, laziness, no-mutation, and exceptions; exact row20/safe4 binding
and post-A external23/local1; and executable caller args/adoption/exception-stop.
B requires at least five: direct compose, private lookup, and append matrices;
static current compose1/lookup2/append1 and post-B external2/local lookup2 plus
row-local2; and executable `_prepare_initial_aggregate_state` compose plus
`_aggregate_calculation_subtasks` append args/adoption/order/exception-stop.

Retain graph `_unresolved_structured_numeric_gap`, `_lookup_value_from_table_label_metadata`,
`_preferred_aggregate_fallback_answer`, `_apply_initial_aggregate_answer_composition`,
`_apply_final_narrative_repair_pipeline`, `_resolve_aggregate_feedback_state`, both executable callers, and the other 17 row callers. Do not absorb LLM/composition/feedback,
state/evidence mutation, artifact/ledger, promotion, sync/rebuild, or final sequencing.

Reject ontology compatibility (four placements/three `hasattr` gates), the 720-line precision
cluster (`_OperandPrecisionContext` plus a reverse import cycle), carrier projection,
stateful compact-ratio work, and evidence-selection/mutation bundling.
Hold source until each current-source gate passes; then retarget/delete, require old
refs zero, and run focused, affected, audit, full, and diff-check sequentially.
No behavior, accuracy, ranking, performance, total-code or executed-path reduction,
benchmark, schedule, or Phase 3 completion claim follows.

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
