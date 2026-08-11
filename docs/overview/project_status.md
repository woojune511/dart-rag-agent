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
| What is the architecture state? | Phase 3 OPEN; aggregate result support/reuse predicate owner milestone closed, four named debt groups remain |
| What just changed? | Four public aggregate result support/reuse predicates moved to `financial_aggregate_projection.py` in `6d6c9c3` |
| What passed? | New focused 6/6, focused plus migrated methods 8/8, aggregate-owner module 28/28, semantic regression set 743/743, nine-module union 762/762, import-side-effect 19/19, runtime audit 217, full unittest 1,662/1,662 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 135-line prepared aggregate material-inspection batch into `financial_aggregate_projection.py`; answer composition, artifact/state mutation, and final sequencing remain hard stops |

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
- The latest owner batch moved the four-function aggregate result support/reuse
  predicate boundary. In `6d6c9c3`, the exact changed files are
  `financial_aggregate_projection.py`, `financial_graph_calculation.py`,
  `test_aggregate_subtask_projection.py`,
  `test_financial_aggregate_rank_dedupe.py`, and `test_financial_text_surface.py`.
  The 81 old graph definition-span lines became four public owner spans
  39 + 10 + 16 + 12 = 77. Twelve calls now place 11 in the graph and one owner-
  local; retired graph-private definitions and test references are zero. Source
  is `+100/-96`, net `+4`; tests are `+906/-6`, net `+900`; the whole commit is
  `+1,006/-102`, net `+904`. The graph moved from 15,961 to 15,880 physical lines
  and aggregate projection from 2,059 to 2,144. The frozen source diff SHA-256 is
  `32a2895fe0e196eaff951ba4ef2440ceb3b9596a8e270e7aaac4b296f91ae693`.
  Answer choice, composition, mutable state/evidence, and final sequencing remain
  graph-owned. This is ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 15,880 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,235, and aggregate projection 2,144.

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
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, and result support/reuse predicates |
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
| Latest focused owner checkpoint | PASS, new focused 6 / 6; focused plus migrated methods 8 / 8; aggregate-owner module 28 / 28 |
| Text-owner module | PASS, 20 / 20 |
| Latest semantic regression set | PASS, eight-module set 743 / 743 |
| Latest semantic/import union | PASS, nine-module set 762 / 762 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,662 / 1,662 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_text_surface`,
`tests.test_financial_aggregate_rank_dedupe`,
`tests.test_financial_answer_projection`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, `tests.test_lookup_recovery_policy`,
and `tests.test_operation_contracts`. Adding `tests.test_import_side_effects`
forms the 762-test union.

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
| Aggregate repair and precedence | Partially advanced through period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, result support/reuse, and bounded row/gap/lookup-answer ownership; promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, and unit/table repair; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Essentially untouched; requires a separate behavior contract |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is one characterize-first prepared aggregate
material-inspection move into `financial_aggregate_projection.py`:

1. publish `growth_required_display_values(...)` from the current 32-line graph
   body at lines 2911-2942;
2. publish `has_strong_growth_trace_for_answer_refresh(...)` from the current
   33-line body at lines 3287-3319;
3. publish `aggregate_lookup_primary_slots(...)` from the current 12-line body at
   lines 4134-4145;
4. move `_ratio_result_numeric_value(...)` from the current 14-line body at lines
   10918-10931 as an owner-private helper;
5. publish `retrieved_ratio_projection_conflicts_with_existing_complete_result(...)`
   from the current 44-line body at lines 10933-10976.

The profiled boundary is 135 old definition-span lines, four public APIs plus one
owner-private helper, and 17 direct calls. Projected owner spans are
31 + 32 + 11 + 13 + 43 = 130 lines. Final placement is 16 graph-external and one
owner-local call: growth-required displays 11/0, strong-growth trace 3/0, lookup
primary slots 1/0, ratio numeric value 0/1, and retrieved-ratio conflict 1/0.
Every current reference is a direct call at Try depth zero; production has no
`hasattr`, callback binding, non-call reference, or compatibility alias for the
selected cluster.

The aggregate owner already owns operation-family, growth display/material,
result-signature, answer-slot material, source-id cleanup, normalization, and
typing dependencies. Add only `growth_row_has_conflicting_periods` on the existing
answer-projection edge, `coerce_slot_numeric` and `ratio_components_are_complete`
on the existing answer-slots edge, and `ratio_context_has_metric_surface` from
operand resolution. None of those owners can reach aggregate projection, so the
new operand edge is one-way and the import DAG stays acyclic. The five bodies hit
no runtime-domain baseline record; the reviewed count remains 217. They inspect
already prepared rows, slots, and ratio evidence, return values/slots/booleans,
and do not mutate inputs, state, evidence, artifacts, or ledgers.

Before source movement, add at least seven CURRENT-SOURCE methods: separate direct
growth-display, strong-growth-trace, and lookup-primary-slot branch/access/
laziness/copy/no-mutation/exception matrices; one direct ratio-value/conflict
matrix fixing result-value precedence, completion/tolerance/signature/context
gates, stable scan, and exception behavior; one exact definition/call/
distribution/import-DAG/baseline method; one executable matrix covering selected
growth display/refresh callers; and one executable matrix covering arithmetic-slot
sync plus retrieved-ratio conflict caller arguments, order, adoption, laziness,
identity, no-mutation, and owner-exception stop. Then move/retarget/delete without
a wrapper or alias, migrate every existing private direct/patch/static reference,
require retired graph-private refs zero, and run focused, aggregate-owner,
affected semantic, import-side-effect, runtime-audit, full-discovery, and
diff-check gates sequentially.

This narrowly supersedes the earlier stop on `_growth_required_display_values`
because its display/material dependencies are now owner-local; it does not move
`_compose_complete_growth_numeric_answer(...)`, narrative/growth answer choice,
`_sync_aggregate_arithmetic_subtask_surfaces(...)`,
`_append_ratio_result_from_retrieved_context(...)`, ratio-artifact retrieval,
compact-ratio state/trace, mutable state/evidence, or final sequencing. Retain the
rejections for direct structured/precision reverse cycles, source-visible query
terms, dependency-slot period/state coupling, evidence construction or mutation,
ontology compatibility, artifact/ledger, callbacks, promotion, sync/rebuild, and
final orchestration. No behavior, accuracy, ranking, performance, total-code or
executed-path reduction, benchmark, schedule, or Phase 3 completion claim follows.

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
