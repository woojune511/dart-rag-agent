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
| What is the architecture state? | Phase 3 OPEN; dependency input-binding owner milestone closed, four named debt groups remain |
| What just changed? | Three public dependency input-binding policies moved to `financial_dependency_projection.py` in `7a20aab`; a pre-move audit also found and retargeted three reconciliation callers omitted by the prior plan |
| What passed? | Focused 6/6, dependency-owner module 69/69, affected nine-module semantic set 895/895, import-side-effect 19/19, runtime audit 217, full unittest 1,686/1,686 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 127-line reconciliation artifact-reference projection cluster into `financial_task_artifacts.py`; reconciliation candidate construction, artifact mutation, retry planning, and final sequencing remain hard stops |

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
- The latest owner batch moved three dependency input-binding policies. In
  `7a20aab`, exactly five source/test files changed. The 62 + 15 + 16 = 93 graph
  definition-span lines became three public dependency-owner functions with
  actual spans 61 + 15 + 16 = 92; the two one-line signatures do not shrink
  physically when `self` is removed. A pre-move source audit corrected the prior
  four-call plan by finding three additional reconciliation callers. All seven
  calls are now direct external imports at Try depth zero, owner-local selected
  calls remain zero, and retired selected private source/test refs are zero.
  Source is `+111/-103`, net `+8`; tests are `+1,164/-2`, net `+1,162`; the whole
  commit is `+1,275/-105`, net `+1,170`. Calculation graph moved from 15,512 to
  15,419 physical lines, reconciliation from 2,428 to 2,429, and dependency
  projection from 3,235 to 3,335. The committed source diff SHA-256 is
  `b840839073e6d7febe828d75004e15e3a45ae2e298a5ded6c303cc53738162e1`.
  Operand/evidence construction, reconciliation state projection, ratio result
  projection, mutable state/evidence, ledger work, and final sequencing remain
  graph-owned. This is ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 15,419 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,335, reconciliation 2,429, and aggregate projection 2,530.

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
| Latest focused owner checkpoint | PASS, new focused 6 / 6; dependency-owner module 69 / 69 |
| Latest semantic regression set | PASS, affected nine-module set 895 / 895 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,686 / 1,686 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_dependency_projection`,
`tests.test_financial_operand_resolution`,
`tests.test_financial_calculation_execution`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, `tests.test_lookup_recovery_policy`,
`tests.test_operation_contracts`, and `tests.test_reconciliation_plan`.
`tests.test_import_side_effects` passed separately at 19 / 19; no combined-union
run is claimed for this checkpoint.

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
| Broader task/artifact ledger synchronization | Essentially untouched; requires a separate behavior contract |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is one characterize-first reconciliation
artifact-reference projection move into `financial_task_artifacts.py`. Move the
current reconciliation helpers `_artifact_text_matches_operand_surface(...)`,
`_reconciliation_artifact_candidate_ids_for_operand(...)`,
`_reconciliation_artifact_candidate_ids(...)`, and
`_reconciliation_evidence_refs(...)`. Keep the text matcher owner-private and
publish the other three without leading underscores.

The current definition spans are 15 + 51 + 29 + 32 = 127 lines at reconciliation
lines 196-210, 212-262, 264-292, and 395-426. Removing only the multiline `self`
argument yields projected owner spans 15 + 50 + 29 + 32 = 126. Their current five
uses are direct `self` calls at Try depth zero: one text match inside the selected
per-operand artifact scan; both artifact-id projections in
`_extract_structured_operands_from_reconciliation(...)`; and two evidence-ref
projections in `_reconcile_retrieved_evidence(...)`. The final selected
distribution is four graph-external calls and one owner-local call. There are no
non-call bindings, `hasattr` gates, callbacks, wrappers, aliases, or production
override surfaces.

The task/artifact owner already has `re`, `Any`/`Dict`/`List`, stable
normalization, and artifact projection. Add only the graph-state type,
`_operand_text_match(...)`, and `_operand_needles(...)`; use a type-only state
import. Row and surface owners do not import task artifacts, task artifacts do
not import reconciliation, and the resulting one-way imports remain cycle-free.
All selected reconciliation imports remain live elsewhere. The four bodies hit
no runtime-domain baseline record, so the reviewed count remains 217.

The owner-private text matcher normalizes the supplied surface, tries the shared
operand matcher first, then compares whitespace-compacted text and operand
needles in stable order. Per-operand candidate projection scans prepared
artifacts in order, accepts kinds containing the exact reconciliation-result
surface, copies payload/result/match entries, matches label/concept/role surfaces,
stably deduplicates candidate ids, and uses artifact evidence refs only when no
matched operand surface was found. General candidate projection preserves the
top-level reconciliation refs before artifact refs and payload refs. Evidence-ref
projection scans only dict match rows, reads its ten provenance key families in
order, recursively flattens list/tuple/set values, filters blank and
`none`/`null`/`nan` strings, and stably deduplicates. These functions read/copy
already prepared state, result, and artifact records; they mutate no input,
artifact list, payload, match row, evidence ref, or nested value.

Before source movement, add exactly six CURRENT-SOURCE methods in the task-
artifact owner suite: one direct text-match matrix; one direct per-operand id
matrix; one direct general id matrix; one direct evidence-ref matrix; one exact
definition/span/five-call/argument/Try-depth/distribution/import-DAG/dead-import/
baseline method; and one executable matrix for structured-operand extraction and
both reconciliation evidence-ref caller placements. Pin branch/access order,
case and substring behavior, stable scan/dedupe/fallback order, shallow copies
and nested identity, recursive flattening, no mutation, exact call arguments,
list adoption, and owner-exception downstream stop. Then move/retarget/delete
without a wrapper or alias, migrate the two existing private test references,
require retired reconciliation-private source/test refs zero, and run focused
six, task-artifact owner, the affected eight-module semantic set, import-side-
effect, runtime-audit, full-discovery, fresh-import, DAG, and diff-check gates
sequentially. At the current inventory, adding exactly six methods projects a
9-test task-artifact module, 1,692 full tests, an 817-test semantic set, and an
836-test semantic/import union. The semantic set is
`tests.test_financial_task_artifacts`, `tests.test_structured_operand_extraction`,
`tests.test_reconciliation_plan`, `tests.test_operation_contracts`,
`tests.test_financial_dependency_projection`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`, and
`tests.test_financial_agent_run_projection`; `tests.test_import_side_effects`
forms the union.

Keep `_extract_structured_operands_from_reconciliation(...)`, candidate-map and
structured-cell selection, `_reconcile_retrieved_evidence(...)`, artifact update
and ledger mutation, evidence construction, reranking/LLM work, reflection
request/retry planning, mutable state, callbacks, promotion, sync/rebuild, and
final orchestration in the graph. Structured-cell/precision moves remain blocked
by graph-helper reverse edges; slot/gap expansion remains blocked by a live
callback and ledger consumer; compact-ratio work remains state/trace-coupled;
ontology compatibility, prepared carriers, answer refresh, and evidence mutation
remain rejected. No behavior, accuracy, ranking, performance, total-code or
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
