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
| What is the architecture state? | Phase 3 OPEN; bounded dependency reconciliation preparation ownership is closed, four named debt groups remain |
| What just changed? | Two public sibling-surface/resolved-reconciliation projections moved to `financial_dependency_projection.py` in `5a0c3e0` |
| What passed? | Focused 6/6, dependency owner 75/75, affected eight-module semantic set 823/823, import-side-effect 19/19, semantic/import union 842/842, runtime audit 217, full unittest 1,704/1,704 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 64-line prepared runtime-evidence/task-artifact row projection pair into `financial_task_artifacts.py`; graph callers, conflict selection, state/evidence mutation, and ledger sequencing remain hard stops |

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
- The latest owner batch moved bounded dependency reconciliation preparation. In
  `5a0c3e0`, exactly four source/test files changed. The 48 + 28 = 76
  reconciliation definition-span lines became two public dependency functions
  spanning 47 + 27 = 74 lines. All five selected calls remain graph-external;
  retired selected private source/test refs are zero and no wrapper or alias
  remains. Source is `+93/-85`, net `+8`; tests are `+1,228/-28`, net `+1,200`;
  the whole commit is `+1,321/-113`, net `+1,208`. Reconciliation moved from
  2,211 to 2,137 physical lines and dependency projection from 3,335 to 3,417.
  The committed source diff SHA-256 is
  `c9e931e818cfc7661ccb05bc162078a4db83120aab44f6dd9331dac51fa7a501`.
  Dependency-state lookup, candidate/cell/evidence construction, LLM reranking,
  artifact/ledger mutation, retry selection, mutable state/evidence, and final
  sequencing remain graph-owned. This is ownership relocation, not a behavior
  claim.
- Current physical sizes are: calculation graph 15,419 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,417, reconciliation 2,137, aggregate projection 2,530,
  task artifacts 1,392, and reflection projection 260.

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
| Calculation rendering | `financial_graph_calculation_rendering.py`, including ratio unit/query/result projection and scalar/time-series display helpers |
| Answer and numeric surfaces | `financial_answer_slots.py`, `financial_answer_projection.py`, `financial_numeric_surface.py`, and `financial_text_surface.py`, including period/material, ratio-readiness, narrative validation, numeric/scale predicates, and shared sentence/token surfaces |
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering and trace inspection, result support/reuse predicates, and prepared growth/ratio material inspection |
| Composition, trace, artifacts | `financial_aggregate_state.py`, `financial_runtime_trace.py`, and `financial_task_artifacts.py`; the task-artifact owner includes bounded reconciliation artifact candidate/evidence-reference projection but not ledger mutation orchestration |
| Reflection projection | `financial_reflection_projection.py`; deterministic action/report, synthesis-source, request/plan normalization, strict summaries, and bounded request construction are owner-held |
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
| Latest focused owner checkpoint | PASS, new focused 6 / 6; dependency owner 75 / 75 |
| Latest semantic regression set | PASS, affected eight-module set 823 / 823; semantic/import union 842 / 842 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,704 / 1,704 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_dependency_projection`,
`tests.test_financial_task_artifacts`, `tests.test_reconciliation_plan`,
`tests.test_structured_operand_extraction`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, `tests.test_operation_contracts`,
and `tests.test_aggregate_subtask_projection`. `tests.test_import_side_effects`
passed separately at 19 / 19 and together with the semantic set as an 842-test
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

The sole selected architecture batch is one characterize-first prepared runtime-
evidence/task-artifact row projection move into the existing
`financial_task_artifacts.py` owner. Publish
`_evidence_items_with_runtime(...)` as `evidence_items_with_runtime(...)` and
`_ratio_result_rows_from_task_artifacts(...)` as
`ratio_result_rows_from_task_artifacts(...)`. Delete both mixin bodies and
retarget every caller directly; do not add a wrapper, alias, callback, result
carrier, reason, or compatibility attribute.

The current calculation definition spans are 21 + 43 = 64 lines at lines
524-544 and 10517-10559. Removing only `self` yields projected owner spans 20 +
42 = 62. The four current loads are all direct calls at Try depth zero with no
non-call binding: runtime-evidence merging is called twice by
`_extract_calculation_operands(...)`; ratio artifact-row projection is called
once by `_preferred_ratio_artifact_row_for_conflicting_recalculation(...)` and
once by `_append_ratio_result_from_retrieved_context(...)`. Final selected
distribution is four graph-external and zero owner-local calls.

The task-artifact owner already has `Any`/`Dict`/`List`, `ArtifactKind`,
`_normalise_spaces(...)`, and the `TYPE_CHECKING` `FinancialAgentState`; the move
adds no module dependency. The graph already imports the owner, the owner does
not import the calculation graph, and the import DAG therefore remains
unchanged. All selected graph imports remain live after deletion. The spans hit
no runtime-domain baseline record, so the reviewed count remains 217. Current
candidate-private references are six source definition/call refs plus five
ratio-row test refs; migration must reduce all retired refs to zero.

Runtime-evidence merging copies only the top-level input list, retains existing
item identity, scans `state.runtime_evidence` in stable order, ignores non-
dictionaries, suppresses duplicate nonblank evidence ids, and appends fresh shallow
copies while preserving nested identity. Ratio artifact-row projection
normalizes the task id, scans copied artifact records in stable order, admits
only the matching calculation-result kind with a nonempty result payload,
preserves the formatted-result/rendered-value/summary fallback and task/status/
source-reference defaults, and returns fresh row dictionaries. Neither function
mutates caller inputs or catches mapping, iteration, truthiness, string,
normalization, or copy exceptions.

Before source movement, add exactly six CURRENT-SOURCE methods in the task-
artifact owner suite: direct runtime-evidence and direct ratio artifact-row
matrices; one exact definition/span/four-call/argument/Try-depth/distribution/
import-DAG/baseline method; one executable `_extract_calculation_operands(...)`
matrix covering both lookup and ratio placements; one executable preferred-ratio-
artifact caller matrix; and one executable retrieved-ratio append caller matrix.
Pin stable order, blank/nonblank id behavior, kind/task/result gates, answer and
status fallback order, fresh top-level copies and nested identities, exact
argument identity, caller adoption, laziness, no mutation, and exception
propagation/downstream stop. Then move, retarget, delete, migrate the five
existing graph-private ratio-row test refs, require retired refs zero, and run
focused six, the task-artifact owner, the affected ten-module semantic set,
import-side-effect, union, runtime-audit, full-discovery, pycompile/fresh-import,
DAG, parity, and diff-check gates sequentially. At the current inventory the
semantic set is 826 tests and its import union is 845; exactly six new methods
project 832 semantic, 851 union, and 1,710 full tests.

Keep all three graph callers and both surrounding graph pipelines. In
particular, retain operand extraction gates and evidence selection, ratio
conflict selection, retrieved-ratio arithmetic and answer projection, mutable
state/evidence, artifact creation/update, task/artifact ledger mutation,
promotion, sync/rebuild, and final sequencing. Do not absorb the adjacent
`_preferred_ratio_artifact_row_for_conflicting_recalculation(...)`: doing so
would add task-artifacts -> aggregate-projection while the existing aggregate-
projection -> runtime-trace -> task-artifacts path creates a cycle. Do not expand
into structured-cell helpers, reflection planning, slot/gap callbacks, compact-
ratio state/trace, ontology compatibility, prepared carriers, answer refresh, or
evidence mutation. No behavior, accuracy, ranking, performance, total-code or
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
