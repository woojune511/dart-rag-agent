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
| What is the architecture state? | Phase 3 OPEN; aggregate growth display/material owner milestone closed, four named debt groups remain |
| What just changed? | Three public growth display/material APIs plus one owner-private helper moved to `financial_aggregate_projection.py` in `d4d19fc` |
| What passed? | New focused 7/7, aggregate-owner module 22/22, migrated existing methods 4/4, semantic regression set 737/737, nine-module union 756/756, import-side-effect 19/19, runtime audit 217, full unittest 1,656/1,656 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 81-line aggregate result support/reuse predicate batch into `financial_aggregate_projection.py`; composition, mutable state/evidence, and final sequencing remain hard stops |

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
- The latest owner batch moved the four-function aggregate growth display/material
  boundary. In `d4d19fc`, the exact changed files are
  `financial_aggregate_projection.py`, `financial_graph_calculation.py`,
  `test_financial_aggregate_rank_dedupe.py`,
  `test_financial_answer_projection.py`, `test_operation_contracts.py`, and
  `test_subtask_loop.py`. The 107 old graph definition-span lines became owner
  spans 23 + 8 + 17 + 55 = 103: three public APIs plus one owner-private helper.
  Eighteen calls now place 15 in the graph and three owner-local; retired graph-
  private definitions and test references are zero. Source is `+134/-127`, net
  `+7`; tests are `+1,066/-18`, net `+1,048`; the whole commit is `+1,200/-145`,
  net `+1,055`. The frozen source diff SHA-256 is
  `c25590b321b0cc32e6220d9f33c196c0570b15442cfe840bd34d6242f2ac8d02`.
  Growth answer construction, duplicate recovery, and surrounding sequencing
  remain graph-owned. This is ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 15,961 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,235, and aggregate projection 2,059.

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
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, and growth display/material projection |
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
| Latest focused owner checkpoint | PASS, new focused 7 / 7; aggregate-owner module 22 / 22; migrated existing methods 4 / 4 |
| Text-owner module | PASS, 20 / 20 |
| Latest semantic regression set | PASS, eight-module set 737 / 737 |
| Latest semantic/import union | PASS, nine-module set 756 / 756 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,656 / 1,656 |
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
| Aggregate repair and precedence | Partially advanced through period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, and bounded row/gap/lookup-answer ownership; promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, and unit/table repair; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Essentially untouched; requires a separate behavior contract |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is one characterize-first aggregate result
support/reuse predicate move into `financial_aggregate_projection.py`:

1. publish `aggregate_results_include_dependency_numeric_result(...)` from the
   current 40-line graph body at lines 2907-2946;
2. publish `aggregate_results_include_source_task_slot_realignment(...)` from the
   current 11-line body at lines 3623-3633;
3. publish `answer_reuses_narrative_summary_text(...)` from the current 17-line
   body at lines 3680-3696;
4. publish `answer_reuses_numeric_narrative_summary_text(...)` from the current
   13-line body at lines 3698-3710.

The profiled boundary is 81 old definition-span lines, four public APIs, and 12
direct calls. Projected owner spans are 39 + 10 + 16 + 12 = 77 lines. Final
placement is 11 graph-external and one owner-local call: dependency-result 1/0,
source-task realignment 1/0, narrative-summary reuse 2/1, and numeric narrative
reuse 7/0. Every current reference is a direct call at Try depth zero; production
has no `hasattr`, callback binding, non-call reference, or compatibility alias for
the selected cluster.

The aggregate owner already has every dependency: aggregate operation-family and
narrative-row predicates, source-row-id cleanup, normalization, `re`, typing, and
numeric-surface extraction. The move adds no import or module edge, has no reverse
dependency path, moves no runtime-domain baseline record, and keeps the reviewed
count at 217. These predicates read prepared aggregate rows and answer strings,
return booleans, and do not mutate inputs, state, evidence, artifacts, or ledgers.

Before source movement, add at least six CURRENT-SOURCE methods: separate direct
dependency-result and source-task-realignment branch/access/laziness/no-mutation/
exception matrices; one direct narrative-reuse pair matrix that fixes blank,
narrative-row, length/digit, substring-direction, numeric-kind/count, and helper
exception behavior; one exact definition/call/distribution/import-DAG/baseline
method; one executable caller matrix for `_preferred_aggregate_fallback_answer`
and the source-realignment gate inside `_aggregate_calculation_subtasks`; and one
executable matrix covering representative initial/final/refresh/aggregate reuse
callers, exact arguments, order, adoption, laziness, input identity, and owner-
exception stop. Then move/retarget/delete without a wrapper or alias, migrate the
aggregate-subtask static reference and text-surface instance patch, require
retired graph-private refs zero, and run focused, affected semantic, import-side-
effect, runtime audit, full discovery, and diff-check gates sequentially.

Keep `_preferred_aggregate_fallback_answer(...)`,
`_refresh_numeric_answer_preserving_narrative_context(...)`,
`_apply_initial_aggregate_answer_composition(...)`,
`_apply_final_narrative_repair_pipeline(...)`, and
`_aggregate_calculation_subtasks(...)` in the graph because they own answer
choice, mutable state, evidence, adoption, and final sequencing. Do not add the
adjacent `_growth_narrative_numeric_incompatible_with_trace(...)` or conflicting/
uncovered narrative candidate helpers: they cross growth calculation, dynamic
driver discovery, or composition. Retain the earlier rejections for source-
visible query terms, direct structured/precision cycles, ratio artifacts,
compact-ratio state/trace, dependency-slot period/state coupling, evidence
construction or mutation, ontology compatibility, artifact/ledger, callbacks,
promotion, sync/rebuild, and final orchestration. No behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark, schedule, or
Phase 3 completion claim follows.

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
