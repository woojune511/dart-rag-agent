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
| What is the architecture state? | Phase 3 OPEN; prepared growth trace-inspection owner milestone closed, four named debt groups remain |
| What just changed? | Three public growth trace-inspection predicates moved to `financial_aggregate_projection.py` in `c010a42` |
| What passed? | New focused 6/6, aggregate-owner module 46/46, affected semantic set 761/761, nine-module union 780/780, import-side-effect 19/19, runtime audit 217, full unittest 1,680/1,680 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 93-line dependency input-binding policy cluster into `financial_dependency_projection.py`; graph-state operand construction, evidence coercion, ratio projection, and final sequencing remain hard stops |

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
- The latest owner batch moved three prepared growth trace-inspection predicates.
  In `c010a42`, exactly seven source/test files changed. The 29 + 57 + 44 = 130
  graph definition-span lines became three public aggregate-owner functions with
  spans 28 + 56 + 43 = 127. All 19 selected calls remain graph-external and
  retired selected graph-private source/test references are zero. Source is
  `+158/-153`, net `+5`; tests are `+946/-80`, net `+866`; the whole commit is
  `+1,104/-233`, net `+871`. The graph moved from 15,643 to 15,512 physical lines
  and aggregate projection from 2,394 to 2,530. The committed source diff
  SHA-256 is
  `598f5e476cf0d8fef1c3767f2b6d33c82f1202702fd58e8c7d6e8c625fb7e348`.
  Answer replacement/refresh, sentence repair, arithmetic synchronization,
  retrieved-ratio artifact/state handling, mutable state/evidence, and final
  sequencing remain graph-owned. This is ownership relocation, not a behavior
  claim.
- Current physical sizes are: calculation graph 15,512 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,235, and aggregate projection 2,530.

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
| Latest focused owner checkpoint | PASS, new focused 6 / 6; aggregate-owner module 46 / 46 |
| Text-owner module | PASS, 20 / 20 |
| Latest semantic regression set | PASS, affected eight-module set 761 / 761 |
| Latest semantic/import union | PASS, nine-module set 780 / 780 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,680 / 1,680 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_text_surface`,
`tests.test_financial_aggregate_rank_dedupe`,
`tests.test_financial_answer_projection`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, `tests.test_lookup_recovery_policy`,
and `tests.test_operation_contracts`. Adding `tests.test_import_side_effects`
forms the 780-test union.

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
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, and unit/table repair; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Essentially untouched; requires a separate behavior contract |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is one characterize-first dependency input-
binding policy move into `financial_dependency_projection.py`. Publish the
current graph helpers `_dependency_slot_matches_input(...)`,
`_task_prefers_sibling_output_synthesis(...)`, and
`_task_output_input_bindings(...)` as public owner APIs without the leading
underscore.

The current definition spans are 62 + 15 + 16 = 93 lines at graph lines
6013-6074, 6711-6725, and 6727-6742. Removing only `self` produces projected
owner spans 61 + 14 + 15 = 90 lines. Their 2 + 1 + 1 = four production uses are
all direct `self` calls at Try depth zero: slot matching in
`_build_dependency_operand_rows(...)` and
`_append_ratio_result_from_task_outputs(...)`, task-output binding projection in
`_dependency_binding_resolution_state(...)`, and sibling-output preference in
`_extract_calculation_operands(...)`. There are no non-call bindings, `hasattr`
gates, callbacks, wrappers, aliases, or production override surfaces. All four
selected calls remain graph-external and owner-local selected calls remain zero.

The dependency owner already has `re`, `Any`/`Dict`/`List`/`Optional`, stable
normalization, and dependency projection policy. Add only `FinancialAgentState`
from graph state plus `_operand_period_focus(...)` from graph helpers. Graph
helpers do not reach the dependency owner, so the direct one-way import remains
cycle-free; no selected graph dependency becomes dead. The three bodies hit no
runtime-domain baseline record and the reviewed count remains 217.

`dependency_slot_matches_input(...)` rejects unequal nonblank concepts, then
resolves period mismatch through the binding focus. A current/prior focus may use
the report year; only `TypeError` and `ValueError` from that optional integer
conversion are caught. Without a usable year it compares the slot focus. Label
matching permits exact, contained, or sibling-row material, while an explicit
segment must occur case-insensitively in the slot or sibling label. The two task-
output helpers shallow-copy the active subtask and each inspected binding, scan
inputs in stable order, normalize source preferences, require `task_output` and
a nonblank preferred task id, and either return on the first qualifying binding
or return the stable list of qualifying binding copies. They mutate no state,
binding, slot, sibling row, or nested input.

Before source movement, add exactly six CURRENT-SOURCE methods: one direct slot-
matching matrix; one direct sibling-output-preference matrix; one direct task-
output-binding matrix; one exact definition/span/four-call/argument/Try-depth/
distribution/import-DAG/dead-import/baseline method; one executable matrix for
the two slot-matcher callers; and one executable matrix for binding-resolution
and operand-extraction callers. Pin concept/period/year/focus/label/segment access
order, the integer-conversion catch boundary, stable binding order, shallow-copy
and nested identity, no mutation, exact call arguments, boolean/list adoption,
and owner-exception downstream stop. Then move/retarget/delete without a wrapper
or alias, migrate the two existing operation-contract direct references, require
retired graph-private refs zero, and run focused six, dependency-owner, the
affected eight-module semantic set, import-side-effect, runtime-audit, full-
discovery, fresh-import, DAG, and diff-check gates sequentially. At the current
inventory, adding exactly six methods projects a 69-test dependency-owner module,
1,686 full tests, an 844-test semantic set, and an 863-test semantic/import union.
The planned semantic set is `tests.test_financial_dependency_projection`,
`tests.test_financial_operand_resolution`,
`tests.test_financial_calculation_execution`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, `tests.test_lookup_recovery_policy`,
and `tests.test_operation_contracts`; `tests.test_import_side_effects` forms the
union.

Keep `_build_dependency_operand_rows(...)`,
`_dependency_binding_resolution_state(...)`, `_extract_calculation_operands(...)`,
`_append_ratio_result_from_task_outputs(...)`, graph-state producer/result lookup,
`_structured_graph_provenance_for_dependency_operand(...)`, operand/evidence
construction and coercion, ratio result projection, mutable state/evidence,
ledger, callbacks, promotion, sync/rebuild, and final orchestration in the graph.
`_operand_period_focus(...)` remains a graph-helper dependency rather than a new
relocation target. Answer replacement/refresh,
source-visible sentence repair, compact-ratio state/trace, direct structured and
precision reverse-cycle clusters, ontology compatibility, carriers, and evidence
mutation remain rejected. No behavior, accuracy, ranking, performance, total-
code or executed-path reduction, benchmark, schedule, or Phase 3 completion
claim follows.

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
