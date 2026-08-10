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
| What is the architecture state? | Phase 3 OPEN; operand-preparation owner milestone closed, four named debt groups remain |
| What just changed? | KRW raw-unit repair, growth raw-scale alignment, and growth-period conflict moved to `financial_operand_resolution.py` in `d13c8cd`, `ae8acba`, and `d8bb90d` |
| What passed? | Focused 4/4, affected seven-module set 762/762, runtime audit 217, full unittest 1,606/1,606 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | Two characterize-first operand unit/table-repair seams into `financial_operand_resolution.py`; graph orchestration remains a hard stop |

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
- The latest owner batch moved KRW raw-unit normalization repair, growth raw-scale
  alignment, and growth-period conflict behind three public operand-resolution
  APIs. All three call placements remain in the graph and retired old identifiers
  are zero. Evidence-row/table preparation, operand-map and plan access, recovery,
  sign/execution, mutable state, artifacts, and final sequencing remain graph-
  owned. This is ownership relocation, not a behavior or performance claim.
- Current physical sizes are: calculation graph 16,936 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, operand resolution 3,272, and aggregate projection
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
| Operand policy and resolution | `financial_operand_resolution.py`, including ratio sign policy, evidence-local unit/period coercion, KRW raw-unit repair, and growth alignment/period conflict |
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
| Latest affected regression set | PASS, seven-module set 762 / 762 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,606 / 1,606 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The affected set is `tests.test_financial_operand_resolution`,
`tests.test_financial_calculation_execution`, `tests.test_financial_answer_slots`,
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
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale and bounded operand-preparation ownership; graph-state lookup, table/evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Essentially untouched; requires a separate behavior contract |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The next architecture batch is one two-commit, one-owner characterize-first
operand unit/table-repair sequence into `financial_operand_resolution.py`:

1. move existing public `dependency_task_output_has_consistent_krw_unit(...)`
   from dependency projection (20 definition-span lines, two current calls);
2. publish `repair_krw_operand_units_from_table_metadata(...)` (166 old graph
   definition-span lines, one current call).

The read-only profiled boundary is two public APIs, 186 old definition-span
lines, and three current calls. Final placement is two external graph calls and
one owner-local repair-to-predicate call. `financial_dependency_projection.py`
already imports operand resolution, so the first move removes an implementation
from that dependency direction; the graph already imports the operand owner.
The second seam uses owner-existing evidence lookup, row matching, normalization,
regex, and render-policy dependencies. No reverse owner import is added. Commit
order is A then B, not a dependency arrow, and this is not a schedule estimate.

The ontology foundation remains excluded. Its four call placements include three
`hasattr(self, "_complete_required_operand_from_ontology")` compatibility gates:
deleting the private attribute changes those paths, while retaining an alias or
wrapper fails the old-private deletion criterion; co-moving `_concept_spec_for_key` fixes an import cycle but not that behavior blocker.

Require at least four CURRENT-SOURCE characterize methods per seam: two direct
branch/identity/laziness/exception/no-mutation matrices, one exact static binding/
order method, and one executable caller adoption/exception-stop method. Keep
source held until those focused tests are green, then retarget direct public
imports and delete the old bodies.

The graph retains `_coerce_operand_row_from_evidence` and
`_prepare_calculation_candidate`. The predicate stays after the graph's shallow
row copy and before raw-value/unit coercion; after the second move the table repair
uses it owner-locally. Table repair stays after evidence-row coercion and before
`repair_krw_normalized_values_from_raw_units`, operand indexing, and plan access.
All evidence selection/direct-structured mutation, caller/carrier preparation,
adoption/failure projection, plan/execution, ontology completion, duplicate
recovery, graph state, task/artifact ledger, promotion, sync/rebuild, callbacks,
and final orchestration remain outside this batch. No behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark, or Phase 3
completion claim follows.

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
