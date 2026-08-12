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
| What is the architecture state? | Phase 3 OPEN; bounded caller-facing run-projection ownership is closed, four named debt groups remain |
| What just changed? | Six public and two owner-private evidence/answer/review/debug projections moved to `financial_agent_run_projection.py` in `84fe1d5` |
| What passed? | Focused 8/8, run-projection owner 65/65, affected eight-module semantic set 515/515, import-side-effect 19/19, semantic/import union 534/534, runtime audit 217, full unittest 1,744/1,744 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 74-line prepared public-answer state-projection seam into `financial_agent_run_projection.py`; dynamic repair/rebuild callers, evidence selection, graph execution, trace/ledger work, and final sequencing remain hard stops |

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
- The latest owner batch moved bounded caller-facing run projection. In
  `84fe1d5`, exactly four source/test files changed. The eight selected definition
  spans totaled 189 lines and became six public plus two owner-private functions
  totaling 184 owner lines. Eleven calls finish as nine graph-external and two
  owner-local; retired selected private source/test refs are zero and no wrapper
  or alias remains. Source is `+232/-211`, net `+21`; tests are `+1,702/-17`, net
  `+1,685`; the whole commit is `+1,934/-228`, net `+1,706`. Main graph moved from
  1,205 to 1,011 physical lines and the new owner contains 215 lines. The
  committed source diff SHA-256 is
  `84b8d32bee450cde9370fa6f72646f006ce9bb47413169b34c1c50b0053a5a24`.
  Runtime-evidence selection/fallback, structured and stale answer repair, trace
  resolution/rebuild, graph execution, compatibility assembly, mutable state/
  evidence, artifact/ledger mutation, and final sequencing remain graph/existing-
  owner responsibilities. This is ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 14,715 lines, main graph 1,011,
  graph helpers 6,269,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,603,
  dependency projection 3,417, reconciliation 2,079, aggregate projection 3,180,
  task artifacts 1,460, reflection projection 260, and run projection 215.

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
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering and trace inspection, result support/reuse predicates, prepared growth/ratio material inspection, final-answer evidence filtering/operand append/surface-operand projection, and growth-answer completion/sanitization |
| Composition, trace, artifacts | `financial_aggregate_state.py`, `financial_runtime_trace.py`, and `financial_task_artifacts.py`; the task-artifact owner includes bounded reconciliation artifact refs, runtime-evidence merge, and ratio result-row projection but not ledger mutation orchestration |
| Caller-facing run projection | `financial_agent_run_projection.py`; state-free runtime-evidence metadata/citation and agent-answer/review/debug projection over already prepared values, excluding evidence selection, answer/trace repair, graph execution, and final sequencing |
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
| Latest focused owner checkpoint | PASS, new focused 8 / 8; run-projection owner 65 / 65 |
| Latest semantic regression set | PASS, affected eight-module set 515 / 515; semantic/import union 534 / 534 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,744 / 1,744 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_agent_run_projection`,
`tests.test_financial_aggregate_rank_dedupe`,
`tests.test_evaluator_runtime_projection`,
`tests.test_benchmark_runner_runtime_projection`,
`tests.test_operation_contracts`, `tests.test_financial_router_response`,
`tests.test_ops_runtime_projection_modes`, and
`tests.test_report_scoped_cache_contract`. `tests.test_import_side_effects`
passed separately at 19 / 19 and together with the semantic set as a 534-test
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
| Aggregate repair and precedence | Partially advanced through period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, prepared growth-numeric rendering and trace inspection, result support/reuse, prepared material inspection, bounded row/gap/lookup-answer ownership, final-answer evidence/surface-operand projection, and growth-answer completion/sanitization; promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, lookup magnitude, same-block unit/table repair, and dependency input matching/binding; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Minimally advanced through bounded read-only reconciliation artifact-reference projection; artifact mutation and whole-ledger synchronization require separate contracts |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is one characterize-first seam from
`financial_graph.py` into the existing state-free
`financial_agent_run_projection.py` owner. Move
`_structured_result_answer_for_missing_public_answer(...)` (21 definition-span
lines), `_complete_aggregate_public_answer_projection(...)` (30),
`_public_projection_state(...)` (17), and `_with_public_answer(...)` (6) as four
public functions without the leading underscore. The 74 former lines project to
20 + 29 + 16 + 6 = 71 owner lines. Thirteen current direct calls finish as 12
graph-external and one owner-local: `with_public_answer` is external six/local
one, `public_projection_state` external four, and the two answer selectors
external one each. Together with the completed owner, the selected surface would
be public ten plus owner-private two with 24 calls split external 21/local three.
Delete every old body and retarget directly; add no wrapper, alias, callback,
carrier, reason, flag, or new output field.

Public `structured_result_answer_for_missing_public_answer(public_answer,
structured_result)` preserves normalized answer comparison, structured-answer
numeric gating, configured missing-marker access, and the exact rule that only a
missing-marked public answer may adopt a non-missing structured answer. Public
`complete_aggregate_public_answer_projection(*, subtask_results, base_answer,
public_answer)` preserves preferred complete-answer selection, projection
construction, the answer-without-trace fallback, runtime-projection metadata,
and both repair flags. Public `with_public_answer(state, public_answer)` returns a
fresh shallow state with synchronized `answer` and `compressed_answer`. Public
`public_projection_state(final, *, public_answer, runtime_calculation_trace,
runtime_evidence=None)` owner-locally applies that copy, installs the supplied
trace, and only when evidence is supplied preserves its list identity under
`runtime_evidence` while creating the current stable concatenated
`evidence_items` list. No selected function mutates caller input.

The owner adds `re`/`Optional`, `CALCULATION_NARRATIVE_POLICY`, existing answer-
projection `_preferred_complete_aggregate_subtask_answer`, runtime-trace
`_attach_runtime_projection_metadata`, `_build_aggregate_calculation_projection`,
and `_structured_result_subtask_rows_and_answer`; `_normalise_spaces` and
`RuntimeCalculationTrace` are already owner-held. These dependency modules do
not import the run-projection owner or graph, so the DAG remains acyclic. The
selected spans hit no runtime-domain baseline record; the reviewed count remains
217. Only the graph's narrative-policy import is projected to become dead; all
other touched graph imports retain nonselected uses.

Before source movement, add exactly six CURRENT-SOURCE methods: direct structured-
result fallback; direct aggregate completion; direct public-state/answer-copy;
exact four-definition/13-call/import-DAG/baseline inventory; executable
`FinancialAgent.run()` exact args/order/adoption/laziness/exception-stop; and an
executable retained-repair caller matrix spanning stale structured repair,
structured-public trace projection, and public runtime-trace repair. Pin shallow
copy and nested/list identity, stable evidence concatenation, missing-marker and
subtask-result gates, metadata flags, unchanged mutable inputs, and propagating
exceptions. Then move, retarget, delete, migrate current graph-private test
patches, require retired refs zero, and run focused six, run-projection tests
71/71, affected
semantic 521, import-side-effect 19, union 540, runtime audit 217, projected full
discovery 1,750, pycompile/fresh import, DAG, body/caller parity, and diff-check
gates sequentially. The affected eight-module set remains the current one.

Keep `_structured_result_projection_for_stale_public_numeric_answer(...)` and
`_apply_stale_structured_numeric_public_answer_repair(...)` graph-owned because
they call the dynamic calculation-mixin complete-numeric replacement path. Keep
`_structured_public_answer_trace_projection(...)` and
`_repair_public_runtime_calculation_trace(...)` because they call dynamic
structured-subtask, collapsed-ratio, and period-repair owners. Keep retrieved-
ratio context repair, `_runtime_evidence_from_retrieved_docs(...)`,
`FinancialAgent.run()` sequencing, graph construction, legacy compatibility
assembly, retrieval/provenance construction, mutable state/evidence, task/
artifact ledger mutation, promotion, sync/rebuild, and final sequencing in their
current owners. Do not expand route construction, model initialization, direct
structured-row/value, collapsed-ratio, prepared-candidate, compact-ratio,
ontology-compatibility, bound-callback, evidence-mutation, or ledger seams. No
behavior, accuracy, ranking, performance, total-code or executed-path reduction,
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
