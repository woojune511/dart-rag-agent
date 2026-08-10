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
| What is the architecture state? | Phase 3 OPEN; aggregate coherence-rank foundation closed, four named debt groups remain |
| What just changed? | Shared slot-material detection, aggregate source preparation, and dependency-coherence ranks moved to state-free owners in `477abff`, `68d6546`, and `194e397` |
| What passed? | Focused 4/4, affected four-module set 655/655, runtime audit 217, full unittest 1,561/1,561 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | Three sequential characterize-first seams: period keys → material projection → aggregate rank/dedupe closure; hard-stop before promotion, sync/rebuild, and planning nested traversal |

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
- The latest foundation batch moved canonical answer-slot material detection,
  aggregate primary/source preparation, and dependency-coherence ranking behind
  six public APIs plus one owner-private candidate helper. Retired moved
  references and graph references to that private helper are zero. Full result
  and nested rank, promotion, dedupe, and material-gap policy remain graph-owned;
  row-material policy and nested traversal remain planning-owned. This is
  ownership relocation, not a behavior or performance claim.
- Current physical sizes are: calculation graph 17,665 lines, planning 2,361,
  answer-slot owner 636, and aggregate owner 1,409.

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
| Answer and numeric surfaces | `financial_answer_slots.py` and `financial_numeric_surface.py`, including shared slot-material and numeric-support predicates |
| Aggregate projection | `financial_aggregate_projection.py`, including row/sentence/rendered selectors, source preparation, and dependency-coherence ranks |
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
| Latest affected regression set | PASS, four-module set 655 / 655 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,561 / 1,561 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The affected set is `tests.test_aggregate_subtask_projection`,
`tests.test_subtask_loop`, `tests.test_financial_agent_run_projection`, and
`tests.test_operation_contracts`.

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
| Aggregate repair and precedence | Partially advanced through shared material/source/coherence foundations; full result/nested rank, promotion, and dedupe remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced; graph-state lookup remains graph-owned |
| Broader task/artifact ledger synchronization | Essentially untouched; requires a separate behavior contract |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The aggregate coherence-rank foundation batch is complete. The next architecture
batch is three sequential characterize-first prerequisite-to-closure seams:

1. publish `answer_slot_period_hint(...)` and `period_match_key(...)` from
   `financial_answer_slots.py`;
2. publish `growth_row_has_conflicting_periods(...)`,
   `material_gap_feedback_for_subtask_result(...)`, and
   `subtask_row_has_material(...)` from `financial_answer_projection.py`;
3. keep `_aggregate_result_rank(...)` owner-private while publishing
   `nested_aggregate_result_rank(...)` and
   `dedupe_aggregate_subtask_results(...)` from the aggregate owner.

The dependency DAG is answer slots → answer projection → aggregate, with no
cycle. The read-only profiled selected inventory is 257 old definition lines and
63 external retargets; it is a boundary, not a completion or schedule estimate. Execute each
seam only after its current-source tests are green, beginning with seam A while
production source is held.

Hard-stop before graph `_promote_stronger_nested_aggregate_results(...)`,
`_sync_projection_subtask_results_with_nested_promotions(...)`, and planning
`_nested_subtask_rows(...)`. Mutable state/evidence, task/artifact ledger mutation,
callbacks, and final orchestration remain graph-owned. No behavior, ranking,
performance, or Phase 3 completion claim follows from this plan.

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
