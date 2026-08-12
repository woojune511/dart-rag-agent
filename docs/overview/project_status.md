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
| What is the architecture state? | Phase 3 OPEN; final aggregate evidence/provenance projection is aggregate-projection-owned, four named debt groups remain |
| What just changed? | The 48-line final aggregate evidence/provenance seam moved to `financial_aggregate_projection.py` in `d31e67a` |
| What passed? | Focused 4/4, aggregate owner 84/84, affected seven-module semantic set 806/806, import-side-effect 19/19, runtime audit 217, full unittest 1,797/1,797 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 310-line collapsed-ratio runtime-trace repair seam into `financial_runtime_trace.py`; public-answer orchestration, period repair, mutable state, canonical evidence construction, ledger, and final sequencing remain hard stops |

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
- Current physical sizes are: calculation graph 14,418 lines, main graph 937,
  graph helpers 6,269,
  planning 2,048, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 625, text surface 411, operand resolution 3,603,
  dependency projection 3,417, reconciliation 1,667, reconciliation candidates
  329, aggregate projection 3,644, runtime trace 1,094, task artifacts 1,460, reflection projection
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
| Latest focused owner checkpoint | PASS, final evidence/provenance characterization 4 / 4; aggregate owner 84 / 84 |
| Latest semantic regression set | PASS, affected seven-module set 806 / 806; semantic/import union 825 / 825 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,797 / 1,797 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_aggregate_rank_dedupe`,
`tests.test_aggregate_subtask_projection`, `tests.test_financial_answer_projection`,
`tests.test_subtask_loop`, `tests.test_financial_agent_run_projection`,
`tests.test_lookup_recovery_policy`, and `tests.test_operation_contracts`.
`tests.test_import_side_effects` passed separately at 19 / 19 and together with
the semantic set as an 825-test union.

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

The sole selected architecture seam is the state-free collapsed-ratio runtime
trace repair in `financial_graph_calculation.py`. Move the current
`_repair_collapsed_ratio_trace_from_evidence(state, trace)` definition (310
lines) to `financial_runtime_trace.py` as public
`repair_collapsed_ratio_trace_from_evidence(state, trace)` (projected 309
lines). Its body has no `self` load. The two direct callers remain in
`financial_graph.py`, outside `try` blocks: `_structured_public_answer_trace_projection(...)`
passes its prepared `public_projection_state(...)` and
`structured_public_projection`; `_repair_public_runtime_calculation_trace(...)`
passes `projection_state, runtime_calculation_trace`, adopts the returned trace,
and then runs the separate period-comparison repair. Delete the old body and
retarget both calls directly; add no wrapper, alias, callback, carrier, reason,
flag, or output field. The selected API distribution is two graph-external
calls and zero owner-local calls.

Preserve ratio/status/component gates; numerator/denominator identity by cleaned
source IDs and normalized value; stable copied collection of already-prepared
evidence and context-doc surfaces; aggregate-token and label/concept term
matching; anchor compatibility; numeric-candidate extraction order, unit
filtering, numerator all-term requirement, stable rank/tie order, and zero/equal
value rejection; percent formatting; slot/source/role projection; operand
overlay; trace copy and nested-alias behavior; input immutability; access
laziness; the existing `TypeError`/`ValueError` soft fallbacks; and all other
uncaught exceptions. This is bounded read-only evidence-surface selection over
already supplied state and trace data, not retrieval or canonical
evidence-ID/window/provenance construction and mutation.

The destination already owns `overlay_calculation_operands_from_slots(...)`,
normalization, and the graph-state type edge. Add `FinancialAgentState` to that
existing type import plus direct imports for calculation rendering,
`extract_numeric_surface_candidates(...)`,
`numeric_candidates_with_spans_from_surface(...)`,
`narrative_context_terms(...)`, and `STRUCTURED_CELL_AFFINITY_POLICY`. These add
one-way owner-to-helper edges; none of those dependencies reaches runtime trace,
graph, or calculation, so the move is acyclic. The selected span contains no reviewed
runtime-domain record and the audit count remains 217. The old calculation
import of `numeric_candidates_with_spans_from_surface(...)` becomes dead;
`overlay_calculation_operands_from_slots(...)`, normalization, text terms,
rendering, and policy remain live elsewhere.

Before production movement, add exactly six CURRENT-SOURCE methods to
`tests.test_aggregate_subtask_projection`: direct early-gate/identity/laziness
coverage; direct evidence/context-doc collection and copy/access coverage;
direct ranking/anchor/unit/tie coverage; direct numeric/result/slot/overlay and
exception coverage; one exact 310-line/two-call/import-DAG/dead-import/baseline/
try-depth inventory; and one executable two-caller test fixing exact args,
adoption, the structured-projection gate, the runtime-repair-to-period-repair
order, mutable-input preservation, and exception stop. Hold production until
focused 6/6 passes. After the literal move, retarget direct tests to the runtime
trace owner and caller patches to the graph import site; migrate existing
private references in `tests.test_financial_agent_run_projection`,
`tests.test_aggregate_subtask_projection`, and `tests.test_subtask_loop`, and
require retired private source/test refs to reach zero.

Projected gates are focused 6/6, aggregate-subtask/runtime-trace contract
124/124, affected seven-module semantic 812/812, import-side-effect 19/19,
semantic/import union 831/831, runtime audit 217, full discovery 1,803/1,803,
pycompile/fresh import, DAG/body/caller parity, retired-ref zero, and diff check.
The semantic set remains `tests.test_financial_aggregate_rank_dedupe`,
`tests.test_aggregate_subtask_projection`, `tests.test_financial_answer_projection`,
`tests.test_subtask_loop`, `tests.test_financial_agent_run_projection`,
`tests.test_lookup_recovery_policy`, and `tests.test_operation_contracts`.

Keep `_structured_public_answer_trace_projection(...)`,
`_repair_public_runtime_calculation_trace(...)`, public-answer projection,
period-comparison repair, graph execution, retrieval/canonical evidence construction,
mutable state/evidence, artifact/ledger mutation, and final sequencing in the
graph. Keep `_ordered_aggregate_subtask_results_for_repair(...)` graph-owned
because it reads graph state directly. Reject the direct-structured/precision
clusters that create reverse owner edges, retrieved-narrative evidence
constructors, slot/gap callback-and-ledger cluster, compact-ratio state carrier,
ontology compatibility path, prepared-candidate carrier, and state/ledger
expansions. No behavior, accuracy, ranking, performance, total-code or
executed-path reduction, benchmark, schedule, or Phase 3 completion claim
follows.

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
