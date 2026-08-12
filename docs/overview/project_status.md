# Project Status

> Single authority for current product state, gates, blockers, and priority.
> Stable runtime semantics live in
> [agent_runtime_contract.md](../architecture/agent_runtime_contract.md); completed
> implementation and experiment chronology live in
> [implementation_history.md](../history/implementation_history.md) and
> [experiment_history.md](../history/experiment_history.md).

Last updated: 2026-08-13

## At A Glance

| Question | Current answer |
| --- | --- |
| What is the product? | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Is the core path blocked? | No known unit/contract correctness blocker |
| What is the architecture state? | Phase 3 OPEN; collapsed-ratio evidence repair is runtime-trace-owned, four named debt groups remain |
| What just changed? | The 310-line collapsed-ratio trace-repair seam moved to `financial_runtime_trace.py` in `8861253` |
| What passed? | Focused 6/6, aggregate-subtask 124/124, text-surface 20/20, affected eight-module semantic set 832/832, import-side-effect 19/19, runtime audit 217, full unittest 1,803/1,803 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | Two sequential characterize-first direct structured-evidence seams totaling 220 old lines into `financial_lookup_recovery.py`; graph-state lookup/scoring, operand-row orchestration, precision refinement, mutable evidence, ledger, and final sequencing remain hard stops |

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
- The latest two-seam owner batch moved prepared nested-result replacement and
  arithmetic subtask-surface synchronization. Across `6ed195e..b5d97ee`, the
  former 64 + 124 = 188 graph definition lines became public 63 + 123 = 186
  owner lines; all four selected calls remain graph-external and retired
  private refs are zero. Source is `+197/-204`, net `-7`; tests are
  `+1,569/-184`, net `+1,385`; the whole range is `+1,766/-388`, net `+1,378`.
  Calculation moved from 14,719 to 14,521 physical lines and aggregate
  projection from 3,350 to 3,541. The range source diff SHA-256 is
  `ee76d6ffa2c0e1f14e8dec7630a6f11e5f39ad4323e1ed5a23f07e6d0fbda1f8`.
  Graph state/evidence, dependency alignment, projection rebuild,
  artifact/ledger mutation, and final sequencing remain graph-owned. This is
  ownership relocation, not a behavior claim.
- Commit `b3bb764` moved the former 53-line
  `_recover_duplicate_growth_prior_operand(...)` body to one 52-line public
  `recover_duplicate_growth_prior_operand(...)` owner function. Its sole call
  remains graph-external in calculation-candidate preparation, after growth
  unit alignment and before the period-conflict gate. Source is `+56/-55`, net
  `+1`; tests are `+629/-26`, net `+603`; the whole commit is `+685/-81`, net
  `+604`. Calculation moved from 14,521 to 14,468 physical lines and aggregate
  projection from 3,541 to 3,595. Four new test methods moved discovery from
  1,789 to 1,793. The source diff SHA-256 is
  `1a02ec371d28b6012b064281260ad3b274bc9f1ef0b330d0724c36d545b56d1a`.
  Retired private refs are zero in source and tests. Candidate construction,
  unit/period alignment, execution, state/evidence, rebuild, artifact/ledger,
  and final sequencing remain graph-owned. This is ownership relocation, not a
  behavior claim.
- Commit `d31e67a` moved the former 48-line
  `_filter_final_aggregate_evidence_and_projection(...)` body to one 47-line
  public `filter_final_aggregate_evidence_and_projection(...)` owner function.
  Its two calls remain graph-external in aggregate orchestration, before the
  ordinary state sync/runtime-ratio repair and after conditional stale-state
  replacement respectively. Source is `+52/-53`, net `-1`; tests are
  `+646/-41`, net `+605`; the whole commit is `+698/-94`, net `+604`.
  Calculation moved from 14,468 to 14,418 physical lines and aggregate
  projection from 3,595 to 3,644. Four new test methods moved discovery from
  1,793 to 1,797. The source diff SHA-256 is
  `f10c327aca0fb5a4a885892354bef1b840caaf224a9696ae113c9d650df45df1`.
  Retired private refs are zero in source and tests. Evidence preparation,
  stale/runtime-ratio repair, state synchronization, answer composition,
  artifact/ledger mutation, and final sequencing remain graph-owned. This is
  ownership relocation, not a behavior claim.
- Commit `8861253` moved the former 310-line
  `_repair_collapsed_ratio_trace_from_evidence(...)` body to one 309-line public
  `repair_collapsed_ratio_trace_from_evidence(...)` runtime-trace function. Its
  two calls remain graph-external in `financial_graph.py`: one after a nonempty
  structured public projection and one before the separate period-comparison
  repair. Source is `+322/-315`, net `+7`; tests are `+1,574/-166`, net
  `+1,408`; the whole commit is `+1,896/-481`, net `+1,415`. Calculation moved
  from 14,418 to 14,106 physical lines, main graph from 937 to 938, and runtime
  trace from 1,094 to 1,412. Six new test methods moved discovery from 1,797 to
  1,803. The source diff SHA-256 is
  `a83d1ddaa2167516789bc9de1a90033dd7183d6764ddf0609bf91a777199e451`.
  Retired private refs are zero, the runtime-trace owner contains three public
  and 28 private top-level functions, and the reviewed runtime-domain count
  remains 217. Public-answer orchestration, period repair, retrieval/canonical
  evidence construction, mutable state/evidence, artifact/ledger mutation, and
  final sequencing remain graph-owned. This is ownership relocation, not a
  behavior claim.
- Current physical sizes are: calculation graph 14,106 lines, main graph 938,
  graph helpers 6,269,
  planning 2,048, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 625, text surface 411, operand resolution 3,603,
  dependency projection 3,417, reconciliation 1,667, reconciliation candidates
  329, aggregate projection 3,644, runtime trace 1,412, lookup recovery 557,
  task artifacts 1,460, reflection projection
  374, and run projection 302.

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
| Dependency and execution | `financial_dependency_projection.py`, including dependency input matching/binding, sibling-output synthesis preference, sibling lookup-surface preparation, and resolved reconciliation projection, plus `financial_calculation_execution.py` |
| Structured reconciliation candidates | `financial_reconciliation_candidates.py`; state-free statement/unit/period/score/identity/row/match and candidate-ID projection over already prepared mappings |
| Calculation rendering | `financial_graph_calculation_rendering.py`, including ratio unit/query/result projection and scalar/time-series display helpers |
| Answer and numeric surfaces | `financial_answer_slots.py`, `financial_answer_projection.py`, `financial_numeric_surface.py`, and `financial_text_surface.py`, including period/material, nested-row traversal/scoring/selected-result promotion, ratio-readiness, narrative validation, numeric/scale predicates, and shared sentence/token surfaces |
| Aggregate projection | `financial_aggregate_projection.py`, including aggregate calculation/public projection, subtask upsert/rank, selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, nested-result replacement, arithmetic subtask-surface synchronization, duplicate growth-prior recovery, final evidence/provenance projection, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering and trace inspection, result support/reuse predicates, prepared growth/ratio material inspection, final-answer evidence filtering/operand append/surface-operand projection, and growth-answer completion/sanitization |
| Composition, trace, artifacts | `financial_aggregate_state.py`, `financial_runtime_trace.py`, and `financial_task_artifacts.py`; runtime trace includes collapsed-ratio evidence repair and the task-artifact owner includes bounded reconciliation artifact refs, runtime-evidence merge, and ratio result-row projection, but neither owns ledger mutation orchestration |
| Caller-facing run projection | `financial_agent_run_projection.py`; state-free runtime-evidence metadata/citation, agent-answer/review/debug, structured missing-answer selection, aggregate completion, and prepared public-answer state projection, excluding evidence selection, dynamic answer/trace repair, graph execution, and final sequencing |
| Reflection projection | `financial_reflection_projection.py`; deterministic retry-query construction/finalization, action/report, synthesis-source, request/plan normalization, strict summaries, and bounded request construction are owner-held |
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
| Latest focused owner checkpoint | PASS, collapsed-ratio characterization 6 / 6; aggregate-subtask 124 / 124; text-surface 20 / 20 |
| Latest semantic regression set | PASS, affected eight-module set 832 / 832; semantic/import union 851 / 851 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,803 / 1,803 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_aggregate_rank_dedupe`,
`tests.test_aggregate_subtask_projection`, `tests.test_financial_answer_projection`,
`tests.test_financial_text_surface`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, `tests.test_lookup_recovery_policy`,
and `tests.test_operation_contracts`. `tests.test_import_side_effects` passed
separately at 19 / 19 and together with the semantic set as an 851-test union.

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
| Aggregate repair and precedence | Partially advanced through aggregate calculation/public projection, subtask upsert/rank, nested traversal/scoring/selected-result promotion, nested-result replacement, arithmetic subtask-surface synchronization, period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, prepared growth-numeric rendering and trace inspection, result support/reuse, prepared material inspection, bounded row/gap/lookup-answer ownership, final-answer evidence/provenance/surface-operand projection, and growth-answer completion/sanitization; broader alignment/rebuild and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, lookup magnitude, same-block unit/table repair, and dependency input matching/binding; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Minimally advanced through bounded read-only reconciliation artifact-reference projection; artifact mutation and whole-ledger synchronization require separate contracts |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture work is a two-seam, characterize-first direct
structured-evidence batch into the existing `financial_lookup_recovery.py`
owner. Execute the seams sequentially and freeze each before starting the next.

Seam A moves the current graph-private
`_lookup_row_from_direct_structured_evidence(operand, evidence_item, *, index)`
definition (81 lines) as public
`lookup_row_from_direct_structured_evidence(operand, evidence_item, *, index)`
(projected 80 lines). Its body has no `self` load. The four direct callers remain
graph-external and outside `try` blocks: three in
`_best_direct_lookup_slot_from_evidence_pool(...)` use `index=1`, while one in
`_period_table_direct_operand_rows(...)` uses `index=operand_index`.

Seam B then moves
`_coerce_operand_value_from_direct_structured_evidence(row, evidence_item)`
(139 lines) as public
`coerce_operand_value_from_direct_structured_evidence(row, evidence_item)`
(projected 138 lines). Its sole direct call remains graph-external and outside a
`try` block in `_coerce_operand_row_from_evidence(...)`, after period coercion
and before lookup-magnitude coercion, structured-cell early return, dependency
early return, and precision refinement. Across both seams, delete the old
bodies and retarget all five calls directly; add no wrapper, alias, callback,
carrier, reason, flag, or output field. The final selected distribution is five
graph-external calls and zero owner-local calls. The lookup owner moves from
public/private 9/7 to 11/7.

Preserve metadata and structured-cell shallow copies, stable cell order,
year/period focus, ordinary and aggregate cell selection, aggregate-role
preference, normalization, empty/no-selection/no-value identity returns, exact
direct-row field construction, magnitude-record adoption, authoritative-surface
matching, query-year soft conversion failures, current-value equality and
`1e-6` tolerance, period-specific override, rendered-value construction,
nested alias identity, input immutability, access laziness, and all uncaught
exceptions. These functions project already-supplied operand rows and prepared
evidence; they do not select the evidence pool or mutate graph state/evidence.

The destination already owns normalization and
`coerce_lookup_magnitude_record(...)`, and already imports operand-resolution
symbols. Add the public aggregate-role preference plus the existing structured
cell selectors/period-focus helper, structured-cell period text, row-surface
operand matching, and positive-surface predicate. Those are one-way
lookup-owner-to-helper edges; none reaches lookup recovery, calculation, or the
main graph, so the move is acyclic. The selected spans contain no reviewed
runtime-domain record and the audit count remains 217. Every touched graph
dependency import remains live outside the selected bodies.

Before each production move, add exactly four CURRENT-SOURCE methods to
`tests.test_lookup_recovery_policy`. Seam A requires two direct branch/access/
copy/order/no-mutation/exception matrices, one exact 81-line/four-call/signature/
try-depth/DAG/baseline inventory, and one executable combined caller test for
pool and period-table args, index values, adoption, laziness, and exception stop.
Seam B requires two direct gate/surface/selection/equality/tolerance/copy/
no-mutation/exception matrices, one exact 139-line/one-call/signature/try-depth/
DAG/baseline inventory, and one executable `_coerce_operand_row_from_evidence`
test fixing exact args, adoption, order, early returns, precision handoff, and
exception stop. Hold production until each focused 4/4 passes, then retarget
owner-direct tests and graph-import caller patches. Migrate the five existing
private references in `tests.test_operation_contracts` and require retired
private source/test refs to reach zero.

Projected final gates after both seams are focused 4/4 per seam and combined
8/8, lookup-recovery owner 24/24, affected seven-module semantic 818/818,
import-side-effect 19/19, semantic/import union 837/837, runtime audit 217, full
discovery 1,811/1,811, pycompile/fresh import, DAG/body/caller parity,
retired-ref zero, and diff check. The semantic set is
`tests.test_lookup_recovery_policy`, `tests.test_financial_calculation_execution`,
`tests.test_financial_operand_resolution`, `tests.test_aggregate_subtask_projection`,
`tests.test_subtask_loop`, `tests.test_financial_agent_run_projection`, and
`tests.test_operation_contracts`.

Keep `_best_direct_lookup_slot_from_evidence_pool(...)`,
`_period_table_direct_operand_rows(...)`, `_coerce_operand_row_from_evidence(...)`,
evidence-pool selection/scoring, state/report scope, table-label lookup,
precision refinement, mutable evidence, artifact/ledger mutation, and final
sequencing in the graph. Do not move the broader
`_lookup_value_from_table_label_metadata(...)` path because it passes the
dynamic `_slot_metric_keys` callback. Reject graph-helper relocation, the
precision/carrier cluster, ontology compatibility paths, prepared-candidate and
compact-ratio state carriers, and state/ledger expansions. No behavior,
accuracy, ranking, performance, total-code or executed-path reduction,
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
