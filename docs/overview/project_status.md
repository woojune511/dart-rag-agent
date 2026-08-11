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
| What is the architecture state? | Phase 3 OPEN; prepared narrative presentation owner milestone closed, four named debt groups remain |
| What just changed? | Two prepared-document/source-preservation surfaces moved to `financial_text_surface.py` in `55f7ce3` |
| What passed? | Focused 5/5 plus migrated 4/4 independently, text owner 20/20, semantic regression set 719/719, nine-module union 738/738, import-side-effect 19/19, runtime audit 217, full unittest 1,638/1,638 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 131-line dependency-source preparation batch into `financial_aggregate_projection.py`; callback and compact-ratio carriers remain hard stops |

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
- The latest owner batch published prepared-document snippet projection and
  prepared-evidence source-surface preservation. Across `7aa3e23..55f7ce3`,
  the exact changed files are `financial_graph_calculation.py`,
  `financial_text_surface.py`, `test_financial_text_surface.py`, and
  `test_subtask_loop.py`. The 141 old graph definition-span lines became two
  public APIs with owner spans 68 and 71. Cumulatively, seven text APIs place 27
  calls as 22 graph-external and five owner-local: context terms 13/5, focus
  variants 2/0, parenthetical variants 3/0, context sentence selection 1/0,
  context inclusion 1/0, document snippet 1/0, and retrieved-source preservation
  1/0. Retired graph-private references are zero. Source is `+152/-146`, net
  `+6`; tests are `+1,304/-11`, net `+1,293`; the whole range is
  `+1,456/-157`, net `+1,299`. The frozen source diff SHA-256 is
  `288189968a74337f54912578d1446f00cf186c64a5a6c6428058100688ee54e4`.
  Query/evidence preparation, composition, mutable state/evidence,
  artifacts/ledger, promotion, sync/rebuild, callbacks, and final sequencing
  remain graph-owned. This is ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 16,297 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,235, and aggregate projection 1,702.

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
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, source/coherence preparation, result/nested ranks, stable dedupe, narrative-row/gap policy, and lookup-answer surfaces |
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
| Latest focused owner checkpoint | PASS, focused 5 / 5 and migrated 4 / 4 independently; combined 9 / 9 |
| Text-owner module | PASS, 20 / 20 |
| Latest semantic regression set | PASS, eight-module set 719 / 719 |
| Latest semantic/import union | PASS, nine-module set 738 / 738 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,638 / 1,638 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_text_surface`,
`tests.test_financial_aggregate_rank_dedupe`,
`tests.test_financial_answer_projection`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, `tests.test_lookup_recovery_policy`,
and `tests.test_operation_contracts`. Adding `tests.test_import_side_effects`
forms the 738-test union.

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

The sole selected architecture batch is one characterize-first dependency-source
preparation move from graph lines 7339-7473 into
`financial_aggregate_projection.py`:

1. publish `ratio_rebuild_component_seeds(...)` from the current 34-line body;
2. co-locate owner-private `_dependency_source_text_match_score(...)` from the
   current 21-line body;
3. publish `dependency_source_slot_match_score(...)` from the current 16-line
   body;
4. publish `best_dependency_source_for_seed(...)` from the current 36-line body;
5. publish `component_slot_from_dependency_source(...)` from the current 24-line
   body.

The profiled boundary is 131 old definition-span lines, four public APIs plus one
owner-private helper, and nine calls. Projected owner spans are
33 + 21 + 15 + 35 + 23 = 127 lines. Seven calls remain graph-external and two
become owner-local: seed collection 1/0, text score 0/1, slot score 1/1, best
source selection 3/0, and component projection 2/0. The functions share one
aggregate source-slot preparation owner and the retained
`_ratio_answer_from_dependency_source_slots(...)` caller boundary.

The aggregate owner already has normalization, answer-slot material gating,
dependency-slot scoring, and local aggregate source-task inference. Add only the
existing-direction dependencies: `financial_answer_slots`,
`dependency_ratio_role_group(...)` and `dependency_operand_from_source_slot(...)`
from `financial_dependency_projection.py`, and `narrative_context_terms(...)`
from `financial_text_surface.py`. The dependency and text owners do not import
aggregate projection, so there is no reverse path. No runtime-domain baseline
record moves; the reviewed count remains 217.

Before source movement, add at least six CURRENT-SOURCE methods: direct seed
collection; the text/slot scoring pair; best-source selection including inference,
exclusion, tie order, shallow-copy identity, laziness, and exception stop;
component construction; one exact definition/call/distribution/dependency-DAG
method; and one executable ratio caller method covering exact arguments, order,
adoption, identity/content, and owner-exception stop. Then publish/retarget/delete
without a wrapper or compatibility alias, require retired graph-private refs
zero, and run focused, affected semantic, import-side-effect, runtime audit, full
discovery, and diff-check gates sequentially.

Keep the adjacent 38-line `_aggregate_dependency_source_slot_by_task_id(...)` in
the graph because it passes the bound
`self._aggregate_result_operation_family` callback into the dependency builder.
Keep the adjacent 145-line `_ratio_answer_from_dependency_source_slots(...)` in
the graph because it owns source adoption, dependency-ratio result projection,
and the compact-ratio state/trace carrier. The bounded public-four selection
supersedes the earlier broad ratio-helper public-surface-sprawl rejection; the
compact-ratio/state parent remains the hard stop.

Reject direct structured-evidence movement because its correct operand owner is
blocked by the graph-helpers/operand-resolution cycle and moving it to graph
helpers would preserve owner debt. Narrative row-focus movement has a broader
instance-patched compose/intent compatibility surface. Compact-ratio rendering
retains state/trace carriers and thirteen callers. Precision/carrier, ontology,
evidence construction or mutation, mutable state/evidence, artifact/ledger,
callback, promotion, sync/rebuild, and final-orchestration expansion remain out
of scope. No behavior, accuracy, ranking, performance, total-code or executed-
path reduction, benchmark, schedule, or Phase 3 completion claim follows.

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
