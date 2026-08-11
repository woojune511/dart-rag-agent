# Project Status

> Single authority for current product state, gates, blockers, and priority.
> Stable runtime semantics live in
> [agent_runtime_contract.md](../architecture/agent_runtime_contract.md); completed
> implementation and experiment chronology live in
> [implementation_history.md](../history/implementation_history.md) and
> [experiment_history.md](../history/experiment_history.md).

Last updated: 2026-08-11

## At A Glance

| Question | Current answer |
| --- | --- |
| What is the product? | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Is the core path blocked? | No known unit/contract correctness blocker |
| What is the architecture state? | Phase 3 OPEN; aggregate narrative row-focus owner milestone closed, four named debt groups remain |
| What just changed? | Two public narrative row-focus APIs moved to `financial_aggregate_projection.py` in `fcf4c55` |
| What passed? | New focused 5/5, aggregate-owner module 15/15, migrated existing methods 3/3, semantic regression set 730/730, nine-module union 749/749, import-side-effect 19/19, runtime audit 217, full unittest 1,649/1,649 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 107-line growth display/material batch into `financial_aggregate_projection.py`; composition, duplicate recovery, state, and evidence orchestration remain hard stops |

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
- The latest owner batch moved the two-function aggregate narrative row-focus
  boundary. In `fcf4c55`, the exact changed files are
  `financial_aggregate_projection.py`, `financial_graph_calculation.py`,
  `test_financial_aggregate_rank_dedupe.py`,
  `test_financial_answer_projection.py`, and `test_financial_text_surface.py`.
  The 95 old graph definition-span lines became public owner spans 26 and 67.
  All three calls remain graph-external: sentence selection 1/0 and context
  selection 2/0. Retired graph-private definitions are zero. Source is
  `+105/-101`, net `+4`; tests are `+721/-3`, net `+718`; the whole commit is
  `+826/-104`, net `+722`. The frozen source diff SHA-256 is
  `4ce346bc63cd45a6f25efcb758ac491df5bc58a704e8e14c5da2eed17ad44c62`.
  Dynamic narrative-driver discovery and growth composition/validation remain
  graph-owned. This is ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 16,069 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,235, and aggregate projection 1,944.

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
| Answer and numeric surfaces | `financial_answer_slots.py`, `financial_answer_projection.py`, `financial_numeric_surface.py`, and `financial_text_surface.py`, including period/material, ratio-readiness, narrative validation, numeric/scale predicates, and shared sentence/token surfaces |
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, and lookup-answer surfaces |
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
| Latest focused owner checkpoint | PASS, new focused 5 / 5; aggregate-owner module 15 / 15; migrated existing methods 3 / 3 |
| Text-owner module | PASS, 20 / 20 |
| Latest semantic regression set | PASS, eight-module set 730 / 730 |
| Latest semantic/import union | PASS, nine-module set 749 / 749 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,649 / 1,649 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_text_surface`,
`tests.test_financial_aggregate_rank_dedupe`,
`tests.test_financial_answer_projection`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, `tests.test_lookup_recovery_policy`,
and `tests.test_operation_contracts`. Adding `tests.test_import_side_effects`
forms the 749-test union.

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
| Aggregate repair and precedence | Partially advanced through period/material/source/coherence/rank/dedupe, narrative validation, and bounded row/gap/lookup-answer ownership; promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, and unit/table repair; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Essentially untouched; requires a separate behavior contract |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is one characterize-first aggregate growth
display/material move from graph lines 2945-3054 into
`financial_aggregate_projection.py`:

1. move `_slot_display_from_source_task(...)` as an owner-private 24-line helper;
2. publish `growth_slot_display_value(...)` from the current 9-line body;
3. publish `growth_slots_share_material(...)` from the current 18-line body;
4. publish `recover_growth_prior_material_from_evidence(...)` from the current
   56-line body.

The profiled boundary is 107 old definition-span lines, three public APIs plus
one owner-private helper, and 18 calls. Projected owner spans are
23 + 8 + 17 + 55 = 103 lines. Final placement is 15 graph-external and three
owner-local calls: source-task display 0/1, growth display 7/2, material equality
4/0, and prior-material recovery 4/0. Every current reference is a direct call at
Try depth zero; production has no `hasattr`, callback binding, or compatibility
alias for the selected cluster.

The aggregate owner already has the answer-slots module edge and material gate,
normalization, `re`, typing, narrative sentence splitting, and
`CALCULATION_NARRATIVE_POLICY`. The move adds only an answer-slots symbol/import
on that existing edge, no new module dependency edge, and no
runtime-domain baseline record; the reviewed count remains 217. The functions
read prepared result rows, slots, and evidence, return a display string, boolean,
or fresh recovery dictionary, and do not mutate their inputs, state, artifacts,
or ledgers.

Before source movement, add at least seven CURRENT-SOURCE methods: a direct
source-task/growth-display branch/access/laziness/identity/exception matrix; a
direct material-equality display/float/exact-equality/caught-error matrix; a direct
prior-evidence year/unit/sentence-order/fallback/no-mutation/exception matrix;
one exact definition/call/distribution/import-DAG/baseline method; executable
`_growth_required_display_values(...)` and
`_compose_complete_growth_numeric_answer(...)` caller methods; and one executable
matrix covering `_compose_growth_narrative_answer(...)` plus
`_recover_duplicate_growth_prior_operand(...)` arguments, adoption, laziness,
input identity, and owner-exception stop. Then move/retarget/delete without a
wrapper or alias, migrate direct tests and instance patches in operation,
subtask, answer-projection, and aggregate-rank suites, require retired graph-
private refs zero, and run focused, affected semantic, import-side-effect,
runtime audit, full discovery, and diff-check gates sequentially.

Keep `_growth_required_display_values(...)`,
`_compose_complete_growth_numeric_answer(...)`,
`_compose_growth_narrative_answer(...)`, and
`_recover_duplicate_growth_prior_operand(...)` in the graph because they own
broader answer construction, evidence choice, duplicate recovery, adoption, and
caller sequencing. Reject `_preserve_source_visible_query_terms(...)` because it
consumes inherited query-focus and ontology seams. Reject direct structured and
precision movement because the correct operand owner is blocked by the graph-
helpers/operand-resolution cycle. The ratio-artifact cluster reads the task
artifact ledger; compact-ratio rendering retains state/trace carriers and
thirteen callers. Dependency-slot matching is a smaller mixed period-focus/state
boundary. Evidence construction or mutation, ontology compatibility, mutable
state/evidence, artifact/ledger, callback, promotion, sync/rebuild, and final
orchestration remain out of scope. No behavior, accuracy, ranking, performance,
total-code or executed-path reduction, benchmark, schedule, or Phase 3
completion claim follows.

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
