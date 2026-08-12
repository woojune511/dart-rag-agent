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
| What is the architecture state? | Phase 3 OPEN; bounded nested traversal/scoring/promotion selection is now answer-projection-owned, four named debt groups remain |
| What just changed? | The 128-line nested subtask selection/promotion cluster moved to `financial_answer_projection.py` in `a8ad25f` |
| What passed? | Focused 6/6, answer-projection owner 23/23, affected six-module semantic set 770/770, import-side-effect 19/19, semantic/import union 789/789, runtime audit 217, full unittest 1,777/1,777 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | Two sequential characterize-first aggregate-result seams totaling 188 lines into `financial_aggregate_projection.py`: nested-result replacement first, arithmetic surface sync second; graph state, alignment/rebuild, ledger, and final sequencing remain hard stops |

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
- The latest owner batch moved nested-row traversal, operation/specificity
  scoring, and bounded selected-result promotion. In `a8ad25f`, exactly six
  source/test files changed. The four selected definition spans totaled 128
  lines and became two public plus two owner-private functions totaling 126
  owner lines. Six calls finish as two graph-external and four owner-local.
  Retired planning definitions and selected mixin-qualified refs are zero.
  Source is `+138/-135`, net `+3`; tests are `+673/-23`, net `+650`; the whole
  commit is `+811/-158`, net `+653`. Answer projection moved from 491 to 625
  physical lines, planning from 2,180 to 2,048, and calculation from 14,718 to
  14,719. The committed source diff SHA-256 is
  `ce62390b757ff986fe704f40fce1e690a6473819890d1725a5aec5e82850687b`.
  Task/state capture, dependency-coherence winner replacement, projection
  alignment/rebuild, artifact/ledger mutation, and final sequencing remain
  graph-owned. This is ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 14,719 lines, main graph 937,
  graph helpers 6,269,
  planning 2,048, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 625, text surface 411, operand resolution 3,603,
  dependency projection 3,417, reconciliation 1,667, reconciliation candidates
  329, aggregate projection 3,350, task artifacts 1,460, reflection projection
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
| Aggregate projection | `financial_aggregate_projection.py`, including aggregate calculation/public projection, subtask upsert/rank, selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering and trace inspection, result support/reuse predicates, prepared growth/ratio material inspection, final-answer evidence filtering/operand append/surface-operand projection, and growth-answer completion/sanitization |
| Composition, trace, artifacts | `financial_aggregate_state.py`, `financial_runtime_trace.py`, and `financial_task_artifacts.py`; the task-artifact owner includes bounded reconciliation artifact refs, runtime-evidence merge, and ratio result-row projection but not ledger mutation orchestration |
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
| Latest focused owner checkpoint | PASS, new focused 6 / 6; answer-projection owner 23 / 23 |
| Latest semantic regression set | PASS, affected six-module set 770 / 770; semantic/import union 789 / 789 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,777 / 1,777 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_answer_projection`,
`tests.test_aggregate_subtask_projection`, `tests.test_financial_aggregate_rank_dedupe`,
`tests.test_subtask_loop`, `tests.test_financial_agent_run_projection`, and
`tests.test_operation_contracts`.
`tests.test_import_side_effects` passed separately at 19 / 19 and together with
the semantic set as a 789-test union.

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
| Aggregate repair and precedence | Partially advanced through aggregate calculation/public projection, subtask upsert/rank, nested traversal/scoring/selected-result promotion, period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, prepared growth-numeric rendering and trace inspection, result support/reuse, prepared material inspection, bounded row/gap/lookup-answer ownership, final-answer evidence/surface-operand projection, and growth-answer completion/sanitization; broader row replacement, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, lookup magnitude, same-block unit/table repair, and dependency input matching/binding; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Minimally advanced through bounded read-only reconciliation artifact-reference projection; artifact mutation and whole-ledger synchronization require separate contracts |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is two sequential characterize-first seams
from `financial_graph_calculation.py` into the existing
`financial_aggregate_projection.py` owner. Seam A moves
`_promote_stronger_nested_aggregate_results(...)` (64 current definition-span
lines) as public `promote_stronger_nested_aggregate_results(...)` (projected 63
lines). Seam B then moves `_sync_aggregate_arithmetic_subtask_surfaces(...)`
(124) as public `sync_aggregate_arithmetic_subtask_surfaces(...)` (projected
123). The batch removes 188 old definition lines, publishes two APIs totaling
186 owner lines, and leaves the four selected calls graph-external with zero
selected owner-local calls. Delete each old body and retarget directly; add no
wrapper, alias, callback, carrier, reason, flag, or output field. After both
seams the aggregate owner projects from public 70/private 11 to public
72/private 11.

Seam A must preserve task-ID map construction and copy order, source-slot map
construction before aggregate scanning, non-aggregate and blank-ID skips,
nested aggregate/material-gap/current-row exclusions, replacement chaining,
current-status fallback, direct-source/numeric-conflict/sign-consistency
protection, strict nested-rank and dependency-coherence comparisons, stable
winner order, carry-forward of four provenance containers, unchanged-list
identity, changed-row shallow copies, nested aliases, input immutability, and
uncaught exceptions. Its three exact callers remain
`_promote_and_align_aggregate_results(ordered_results)`,
`_sync_projection_subtask_results_with_nested_promotions(projection_subtask_results)`,
and `_prepare_initial_aggregate_state(ordered_results)`.

Seam B must preserve copied projection/result/answer-slot rows, empty-projection
identity, planned arithmetic-task filtering, operation-family and row-surface
precedence, lookup and arithmetic coverage gates, stable candidate-index order,
the second answer-sentence selection on adoption, numeric conflict and lookup
cardinality rules, rendered-value projection, row-surface synchronization,
lookup-slot/component synchronization, ordered-result and answer-slot row
replacement, changed/unchanged identity, nested aliases, input immutability,
access laziness, and uncaught exceptions. Its sole exact caller remains
`_aggregate_calculation_subtasks(ordered_results, aggregate_projection,
final_answer)`. All four calls remain outside `try` blocks and keep their exact
positional arguments and current adoption points.

The aggregate owner already owns every selected dependency except the public
`nested_subtask_rows(...)` symbol on its existing one-way answer-projection
edge. It already owns or imports aggregate operation/rank/coherence/source-slot,
numeric-surface, row-surface sync, normalization, typing, and synchronization
input contracts. Aggregate projection reaches answer projection, numeric
surface, and normalization, none of which reaches aggregate; it does not reach
the calculation graph, while calculation already imports aggregate. The move
therefore adds no module edge or cycle. Remove the now-dead calculation imports
`AggregateArithmeticComponentSyncInput`,
`AggregateProjectionRowSurfaceSyncInput`, `aggregate_lookup_primary_slots`,
`aggregate_projection_rendered_value`, `synchronize_aggregate_arithmetic_components`,
`synchronize_aggregate_projection_row_surface`, `subtask_row_has_direct_source_refs`,
and `nested_subtask_rows`; all other selected dependencies remain live. The
selected spans hit no runtime-domain baseline record, so the reviewed count
remains 217.

Before Seam A production movement, add exactly six CURRENT-SOURCE methods to
`tests.test_financial_aggregate_rank_dedupe`: two direct promotion matrices for
gates, replacement chaining, conflict/sign/rank/coherence ordering, stable
selection, carry-forward, copy/identity/no-mutation and exceptions; one exact
64-line/three-call/import-DAG/baseline/dead-import/try-depth inventory; and one
executable caller method for each of its three callers. Hold source until
focused 6/6 passes, then move, retarget all direct/private tests, require the old
definition and qualified refs to reach zero, and freeze the source before Seam
B characterization.

Before Seam B production movement, add exactly six more CURRENT-SOURCE methods
to the same owner test module: empty/plan/operation gate, candidate eligibility,
row/answer-slot/component adoption, and access/copy/laziness/no-mutation/
exception matrices; one exact 124-line/one-call/final-distribution/DAG/baseline/
dead-import/try-depth inventory; and one executable aggregate-orchestrator
caller test. Hold source until focused 6/6 passes, then move and retarget the
existing private references in `tests.test_financial_aggregate_rank_dedupe`,
`tests.test_aggregate_subtask_projection`, `tests.test_financial_answer_projection`,
and `tests.test_subtask_loop`.

After both seams require focused 12/12, aggregate owner 76/76, affected
seven-module semantic 798/798, import-side-effect 19/19, union 817/817, runtime
audit 217, projected full discovery 1,789/1,789, pycompile/fresh import,
DAG/body/caller parity, retired selected refs zero, and diff-check gates. The
semantic set is `tests.test_financial_aggregate_rank_dedupe`,
`tests.test_aggregate_subtask_projection`, `tests.test_financial_answer_projection`,
`tests.test_subtask_loop`, `tests.test_financial_agent_run_projection`,
`tests.test_lookup_recovery_policy`, and `tests.test_operation_contracts`.

This batch supersedes only the earlier broad synchronization hard stop for these
two state-free prepared-row transforms. Keep
`_sync_projection_subtask_results_with_nested_promotions(...)`,
`_promote_and_align_aggregate_results(...)`, `_prepare_initial_aggregate_state(...)`,
`_aggregate_calculation_subtasks(...)`, dependency alignment, projection
rebuild, graph state/evidence, artifact/ledger mutation, and final sequencing in
calculation. Reject the direct structured/precision cluster because its correct
operand owner would create the known graph-helper reverse cycle; reject the
slot/gap cluster because it crosses callback and final-ledger consumers; and
continue rejecting compact-ratio, ontology-compatibility, carrier,
evidence-mutation, state, and ledger expansions. No behavior, accuracy, ranking,
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
