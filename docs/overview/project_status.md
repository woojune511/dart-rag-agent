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
| What is the architecture state? | Phase 3 OPEN; prepared aggregate material-inspection owner milestone closed, four named debt groups remain |
| What just changed? | Four public aggregate material-inspection functions plus one owner-private ratio helper moved to `financial_aggregate_projection.py` in `df7afc2` |
| What passed? | New focused 7/7, aggregate-owner module 35/35, five changed test modules 328/328, semantic regression set 754/754, ten-module union 773/773, import-side-effect 19/19, runtime audit 217, full unittest 1,669/1,669 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 100-line prepared growth-numeric renderer into `financial_aggregate_projection.py`; answer selection/refresh, mutable state/evidence, and final sequencing remain hard stops |

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
- The latest owner batch moved the prepared aggregate material-inspection
  boundary. In `df7afc2`, exactly seven source/test files changed:
  `financial_aggregate_projection.py`, `financial_graph_calculation.py`, and five
  focused test modules. The 135 old graph definition-span lines became public
  owner spans 31 + 32 + 11 + 43 plus one 13-line owner-private helper. Seventeen
  calls now place 16 in the graph and one owner-local; retired selected graph-
  private definitions and test references are zero. Source is `+164/-157`, net
  `+7`; tests are `+1,039/-44`, net `+995`; the whole commit is `+1,203/-201`,
  net `+1,002`. The graph moved from 15,880 to 15,743 physical lines and aggregate
  projection from 2,144 to 2,288. The committed source diff SHA-256 is
  `846da97ce32136e2b05ff221c29c4f09c5a541ed70785df556be195dad81f6fd`.
  Growth answer construction, arithmetic synchronization, retrieved-ratio
  artifact/state handling, mutable state/evidence, and final sequencing remain
  graph-owned. This is ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 15,743 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,235, and aggregate projection 2,288.

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
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, result support/reuse predicates, and prepared growth/ratio material inspection |
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
| Latest focused owner checkpoint | PASS, new focused 7 / 7; aggregate-owner module 35 / 35; five changed test modules 328 / 328 |
| Text-owner module | PASS, 20 / 20 |
| Latest semantic regression set | PASS, nine-module set 754 / 754 |
| Latest semantic/import union | PASS, ten-module set 773 / 773 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,669 / 1,669 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_text_surface`,
`tests.test_financial_aggregate_rank_dedupe`,
`tests.test_financial_answer_projection`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, `tests.test_lookup_recovery_policy`,
`tests.test_operation_contracts`, and `tests.test_financial_ratio_readiness`.
Adding `tests.test_import_side_effects` forms the 773-test union.

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
| Aggregate repair and precedence | Partially advanced through period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, result support/reuse, prepared material inspection, and bounded row/gap/lookup-answer ownership; promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, and unit/table repair; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Essentially untouched; requires a separate behavior contract |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is one characterize-first prepared growth-
numeric rendering move into `financial_aggregate_projection.py`: publish the
current graph `_compose_complete_growth_numeric_answer(row, ordered_results,
evidence_items=None)` body at lines 2914-3013 as
`compose_complete_growth_numeric_answer(...)`.

The boundary is one 100-line definition and nine direct calls, all at Try depth
zero. Removing only `self` produces a projected 99-line public owner function;
all nine calls remain graph-external and owner-local selected calls remain zero.
Production has no `hasattr`, callback binding, non-call reference, wrapper, or
compatibility alias for this function. The owner already contains operation-
family resolution, growth slot display/material comparison, recovered-prior
material, calculation rendering, answer-slot material, normalization, regex,
typing, and narrative policy. Add only `topic_particle` on the existing text-
surface edge and `CALCULATION_SLOT_POLICY` on the existing retrieval-policy edge,
so no module edge or import cycle is introduced. Both graph imports remain live
outside the moved body. The body hits no runtime-domain baseline record and the
reviewed count remains 217.

The function shallow-copies prepared calculation-result and answer-slot maps,
requires a growth-rate row and material primary slot, resolves growth/current/
prior display values including owner-local prior recovery, strips period text
from the selected metric label, derives period/direction wording from policy,
and returns one normalized policy-template sentence. It mutates no row, slot,
ordered-result, or evidence object. Only `TypeError` and `ValueError` from the
optional normalized-direction float conversion are caught; all other mapping,
copy, truthiness, string, regex, owner, rendering, policy, formatting, and
normalization exceptions propagate.

Before source movement, add exactly five CURRENT-SOURCE methods: two direct
matrices covering the full gate/value/recovery/label/period/direction/template
branches, access order, laziness, shallow-copy identity, no mutation, and caught
versus propagated exceptions; one exact definition/span/nine-call/argument/
Try-depth/distribution/import-DAG/baseline method; one executable matrix covering
the preferred/complete-answer callers; and one executable matrix covering the
narrative/support callers. Pin exact row/list/evidence identities, caller order,
return adoption, early-stop laziness, mutable-input content and nested identity,
and owner-exception downstream stop. Then move/retarget/delete without a wrapper
or alias, migrate every existing private direct/patch/static reference, require
retired graph-private refs zero, and run focused, aggregate-owner, affected
semantic, import-side-effect, runtime-audit, full-discovery, fresh-import, and
diff-check gates sequentially.

This narrowly supersedes the prior stop on the renderer because growth display,
material comparison, and prior recovery are now owner-local and this function
only projects already prepared row/slot/evidence surfaces into a string. Retain
`_ensure_complete_growth_numeric_answer(...)`,
`_final_growth_answer_without_untraced_numeric_sentences(...)`,
`_enforce_source_stated_growth_answer_contract(...)`,
`_strip_untraced_numeric_material_from_growth_narrative_sentence(...)`, answer
selection/refresh, arithmetic synchronization, retrieved-ratio artifact/state,
evidence construction or mutation, mutable state, ledger, callbacks, promotion,
sync/rebuild, and final orchestration in the graph. Direct structured/precision
reverse cycles, ontology compatibility, compact-ratio state/trace, carrier, and
source-visible query-term expansions remain rejected. No behavior, accuracy,
ranking, performance, total-code or executed-path reduction, benchmark, schedule,
or Phase 3 completion claim follows.

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
