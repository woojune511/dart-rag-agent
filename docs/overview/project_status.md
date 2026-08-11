# Project Status

> Single authority for current product state, gates, blockers, and priority.
> Stable runtime semantics live in
> [agent_runtime_contract.md](../architecture/agent_runtime_contract.md); completed
> implementation and experiment chronology live in
> [implementation_history.md](../history/implementation_history.md) and
> [experiment_history.md](../history/experiment_history.md).

Last updated: 2026-08-12

## At A Glance

| Question | Current answer |
| --- | --- |
| What is the product? | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Is the core path blocked? | No known unit/contract correctness blocker |
| What is the architecture state? | Phase 3 OPEN; bounded reconciliation artifact-reference ownership is closed, four named debt groups remain |
| What just changed? | Three public reconciliation artifact-reference projections and one owner-private matcher moved to `financial_task_artifacts.py` in `c825ab7`; a pre-move audit also removed the newly dead reconciliation `_operand_text_match` import |
| What passed? | Focused 6/6, task-artifact owner 9/9, affected eight-module semantic set 817/817, import-side-effect 19/19, semantic/import union 836/836, runtime audit 217, full unittest 1,692/1,692 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 79-line reflection request/plan projection cluster into `financial_reflection_projection.py`; reflection planning, model invocation, retry application, ledger mutation, and routing remain hard stops |

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
- The latest owner batch moved bounded reconciliation artifact-reference
  projection. In `c825ab7`, exactly five source/test files changed. The
  15 + 51 + 29 + 32 = 127 reconciliation definition-span lines became three
  public task-artifact functions plus one owner-private matcher spanning
  15 + 50 + 29 + 32 = 126 lines. Four selected calls remain graph-external and
  one matcher call is owner-local; retired selected private source/test refs are
  zero. A pre-move audit corrected the prior statement that every selected graph
  import would remain live: `_operand_text_match` became unused and was removed.
  Source is `+153/-138`, net `+15`; tests are `+1,455/-4`, net `+1,451`; the whole
  commit is `+1,608/-142`, net `+1,466`. Reconciliation moved from 2,429 to 2,302
  physical lines and task artifacts from 1,250 to 1,392. The committed source
  diff SHA-256 is
  `65819999639a808bb95ec29ddf6547751fddaff3eed4e3af321210d367a43b55`.
  Candidate/cell selection, artifact mutation, mutable state/evidence, retry
  planning, ledger work, and final sequencing remain graph-owned. This is
  ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 15,419 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,335, reconciliation 2,302, aggregate projection 2,530,
  task artifacts 1,392, and reflection projection 158.

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
| Dependency and execution | `financial_dependency_projection.py`, including dependency input matching/binding and sibling-output synthesis preference, plus `financial_calculation_execution.py` |
| Calculation rendering | `financial_graph_calculation_rendering.py`, including ratio unit/query/result projection and scalar/time-series display helpers |
| Answer and numeric surfaces | `financial_answer_slots.py`, `financial_answer_projection.py`, `financial_numeric_surface.py`, and `financial_text_surface.py`, including period/material, ratio-readiness, narrative validation, numeric/scale predicates, and shared sentence/token surfaces |
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering and trace inspection, result support/reuse predicates, and prepared growth/ratio material inspection |
| Composition, trace, artifacts | `financial_aggregate_state.py`, `financial_runtime_trace.py`, and `financial_task_artifacts.py`; the task-artifact owner includes bounded reconciliation artifact candidate/evidence-reference projection but not ledger mutation orchestration |
| Reflection projection | `financial_reflection_projection.py`; deterministic action/report and synthesis-source projection are owner-held while request/plan projection is the next selected move |
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
| Latest focused owner checkpoint | PASS, new focused 6 / 6; task-artifact owner module 9 / 9 |
| Latest semantic regression set | PASS, affected eight-module set 817 / 817; semantic/import union 836 / 836 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,692 / 1,692 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_task_artifacts`,
`tests.test_structured_operand_extraction`, `tests.test_reconciliation_plan`,
`tests.test_operation_contracts`, `tests.test_financial_dependency_projection`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`, and
`tests.test_financial_agent_run_projection`. `tests.test_import_side_effects`
passed separately at 19 / 19 and together with the semantic set as an 836-test
union.

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
| Aggregate repair and precedence | Partially advanced through period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, prepared growth-numeric rendering and trace inspection, result support/reuse, prepared material inspection, and bounded row/gap/lookup-answer ownership; promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, unit/table repair, and dependency input matching/binding; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Minimally advanced through bounded read-only reconciliation artifact-reference projection; artifact mutation and whole-ledger synchronization require separate contracts |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is one characterize-first reflection
request/plan projection move into the existing `financial_reflection_projection.py`
owner. Publish `_normalise_reflection_plan_record(...)` as
`normalise_reflection_plan_record(...)` and the mixin method
`_build_reflection_request(...)` as `build_reflection_request(...)`. Keep
`_reflection_runtime_trace_summary(...)` and `_reflection_evidence_summary(...)`
owner-private. Move the existing public bounded-strategy constant
`ALLOWED_REFLECTION_RETRY_STRATEGIES` and private one-retry budget constant with
the bodies; do not duplicate or import them back from reconciliation.

The current definition spans are 35 + 15 + 7 + 22 = 79 lines at reconciliation
lines 136-170, 173-187, 190-196, and 200-221. Removing only `self` from the request
builder yields projected owner spans 35 + 15 + 7 + 21 = 78. The four current
calls are direct: the request builder is called once by `_plan_reflection_retry`
at Try depth zero; plan normalization is called once inside that method's
structured-planner `try`; and the two summaries become owner-local request-builder
calls. The final selected distribution is two graph-external and two owner-local
calls. There are no non-call bindings, `hasattr` gates, callbacks, wrappers,
aliases, or production override surfaces.

The reflection owner already has `Any`/`Dict`/`List`, graph-state types under
`TYPE_CHECKING`, and stable normalization. Add the strict
`_resolve_runtime_calculation_trace(...)` dependency and extend the type-only
imports with `ReflectionPlanRecord` and `ReflectionRequest`. Runtime trace does
not import reflection projection, reflection projection does not import
reconciliation, and the simulated import graph remains acyclic. The graph keeps
its independent runtime-trace import for retry planning. The selected spans hit
no runtime-domain baseline record, so the reviewed count remains 217.

Plan normalization shallow-copies the planner record, normalizes missing info,
subqueries, sections, and retry strategy, applies the bounded allowed-strategy
fallback, fills missing lists, and replaces the whole record with the heuristic
fallback when subqueries remain empty. Runtime summary resolves only the strict
current trace from a top-level state copy and projects operand count plus plan and
result surfaces. Evidence summary projects counts and status from prepared state.
The public request builder copies active-task input, strips missing-info items,
composes both summaries, and clamps remaining retry budget at zero. Inputs and
nested state remain unmodified; current mapping, conversion, iteration, string,
copy, and resolver exceptions keep their existing scope.

Before source movement, add exactly six CURRENT-SOURCE methods in the reflection
contract suite: one direct plan-normalization matrix; one direct runtime-summary
matrix; one direct evidence-summary matrix; one direct request-builder matrix;
one exact constants/definition/span/four-call/argument/Try-depth/distribution/
import-DAG/baseline method; and one executable `_plan_reflection_retry(...)`
caller matrix. Pin access and fallback order, allowed-strategy bounds, strict
trace resolution, summary identity and adoption, budget clamping, shallow copies,
nested aliases, no mutation, exact arguments, exception propagation before the
planner, and the existing structured-planner catch/fallback when normalization
raises. Then move/retarget/delete without a wrapper or alias, migrate the existing
reflection contract imports and harness calls, require retired reconciliation-
private source/test refs zero, and run focused six, reflection owner/contract,
the affected seven-module semantic set, import-side-effect, runtime-audit,
full-discovery, fresh-import, DAG, and diff-check gates sequentially. At the
current inventory, exactly six new methods project an 18-test reflection contract
module, 1,698 full tests, an 800-test semantic set, and an 819-test semantic/import
union. The semantic set is `tests.test_reflection_capability_contract`,
`tests.test_reconciliation_plan`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, `tests.test_operation_contracts`,
`tests.test_aggregate_subtask_projection`, and
`tests.test_financial_dependency_projection`; `tests.test_import_side_effects`
forms the union.

Keep `_heuristic_reflection_query_plan(...)`, `_finalize_retry_queries(...)`,
`_plan_reflection_retry(...)`, missing-info inference, prompt/model invocation,
retry action application, reflection report/artifact ledger mutation, eligibility,
routing, mutable state/evidence, promotion, and final orchestration in the graph.
Do not move the same request cluster to task artifacts: runtime trace already
imports that owner and would form a cycle. The 76-line sibling/dependency
reconciliation helper pair remains a less cohesive, broader-caller alternative;
structured-cell/precision reverse-cycle work, slot/gap callback/ledger expansion,
compact-ratio state/trace, ontology compatibility, prepared carriers, answer
refresh, and evidence mutation remain rejected. No behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark, schedule, retry-
promotion, or Phase 3 completion claim follows.

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
