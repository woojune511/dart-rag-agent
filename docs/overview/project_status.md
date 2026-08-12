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
| What is the architecture state? | Phase 3 OPEN; prepared structured-reconciliation candidate projection is now owner-held, four named debt groups remain |
| What just changed? | Eleven structured candidate metadata/unit/period/score/identity/row/match/ID projections moved to `financial_reconciliation_candidates.py` in `bb0a982` |
| What passed? | Focused 8/8, candidate-owner 8/8, affected seven-module semantic set 486/486, import-side-effect 19/19, semantic/import union 505/505, runtime audit 217, full unittest 1,758/1,758 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 107-line reflection retry-query projection batch into `financial_reflection_projection.py`; heuristic dependency resolution, prompt/LLM planning, action/report/artifact mutation, and final sequencing remain hard stops |

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
- The latest owner batch moved prepared structured-reconciliation candidate
  projection. In `bb0a982`, exactly eight source/test files changed. The eleven
  selected definition spans totaled 293 lines and became seven public plus four
  owner-private functions totaling 285 owner lines. Twenty-six calls finish as
  19 reconciliation-external and seven owner-local. Retired selected private
  source/test refs are zero and no wrapper or alias remains. Source is
  `+357/-331`, net `+26`; tests are `+686/-30`, net `+656`; the whole commit is
  `+1,043/-361`, net `+682`. Reconciliation moved from 2,079 to 1,776 physical
  lines and the new owner contains 329. The committed source diff SHA-256 is
  `6469dfd06b0efd36c92d252753ba96ecdeb5421e4dc3fdaac0c492cdd4167a5f`.
  Candidate collection, structured-pair/operand extraction orchestration, LLM
  reranking, evidence construction, artifact/retry/state mutation, and final
  sequencing remain graph-owned. This is ownership relocation, not a behavior
  claim.
- Current physical sizes are: calculation graph 14,715 lines, main graph 936,
  graph helpers 6,269,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,603,
  dependency projection 3,417, reconciliation 1,776, reconciliation candidates
  329, aggregate projection 3,180, task artifacts 1,460, reflection projection
  260, and run projection 302.

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
| Answer and numeric surfaces | `financial_answer_slots.py`, `financial_answer_projection.py`, `financial_numeric_surface.py`, and `financial_text_surface.py`, including period/material, ratio-readiness, narrative validation, numeric/scale predicates, and shared sentence/token surfaces |
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering and trace inspection, result support/reuse predicates, prepared growth/ratio material inspection, final-answer evidence filtering/operand append/surface-operand projection, and growth-answer completion/sanitization |
| Composition, trace, artifacts | `financial_aggregate_state.py`, `financial_runtime_trace.py`, and `financial_task_artifacts.py`; the task-artifact owner includes bounded reconciliation artifact refs, runtime-evidence merge, and ratio result-row projection but not ledger mutation orchestration |
| Caller-facing run projection | `financial_agent_run_projection.py`; state-free runtime-evidence metadata/citation, agent-answer/review/debug, structured missing-answer selection, aggregate completion, and prepared public-answer state projection, excluding evidence selection, dynamic answer/trace repair, graph execution, and final sequencing |
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
| Latest focused owner checkpoint | PASS, new focused 8 / 8; reconciliation-candidate owner 8 / 8 |
| Latest semantic regression set | PASS, affected seven-module set 486 / 486; semantic/import union 505 / 505 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,758 / 1,758 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_reconciliation_candidates`,
`tests.test_reconciliation_plan`, `tests.test_financial_operand_resolution`,
`tests.test_financial_dependency_projection`,
`tests.test_financial_task_artifacts`, `tests.test_operation_contracts`, and
`tests.test_structured_operand_extraction`. `tests.test_import_side_effects`
passed separately at 19 / 19 and together with the semantic set as a 505-test
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

The sole selected architecture batch is one characterize-first reflection
retry-query projection move into the existing
`financial_reflection_projection.py` owner. Move
`_build_retry_queries(...)` (26 current definition-span lines) as public
`build_retry_queries(...)` and `_finalize_retry_queries(...)` (81) as public
`finalize_retry_queries(...)`. Removing the standalone `self` parameter from the
second signature projects the 107 former lines to 106 owner lines. The three
current calls finish as two graph-external calls and one owner-local
`finalize_retry_queries(...) -> build_retry_queries(...)` call. Delete both old
bodies and retarget directly; add no wrapper, compatibility alias, callback,
carrier, reason, flag, or output field. The reflection owner becomes public
eight plus owner-private two.

`build_retry_queries(...)` must preserve company precedence from explicit state
then the first seed-document company, eager year integer conversion, required
query access, topic/intent fallbacks, preferred calculation-section lookup,
missing-info order, the first two preferred sections, whitespace normalization,
stable first-seen dedupe, and blank rejection. `finalize_retry_queries(...)`
must preserve repeated normalization of planner subqueries, fallback to the
builder only when no base query survives, retry-objective augmentation for the
first two missing items, explicit companies access, seed-before-retrieved report-
company fallback, global-plus-plan section aliasing and stable dedupe, section-
qualified query expansion, per-query raw-section replacement, report-company
prefixing, and final stable dedupe. Both functions read already prepared state
and plan mappings, return fresh lists, mutate no caller input, and preserve the
current access, laziness, identity, `KeyError`, conversion, metadata, helper, and
normalizer exception scopes.

The owner adds only `_preferred_calc_sections` and `_section_hint_alias` from
`financial_retrieval_hints`; normalization and state typing are already owned.
Retrieval hints, runtime normalization, and runtime trace do not import or reach
reflection projection, and reflection projection does not reach either graph
mixin, so the import DAG remains acyclic. The selected spans hit no runtime-
domain baseline record and the reviewed count remains 217. Reconciliation keeps
its `_preferred_calc_sections` import for heuristic and LLM-plan preparation,
while `_section_hint_alias` becomes owner-only and should be removed there. All
calculation imports touched outside the selected call remain live.

Before production movement, add exactly six CURRENT-SOURCE methods to
`tests.test_reflection_capability_contract`: direct builder branch/access/
dedupe/no-mutation/exception behavior; direct finalizer planner/objective/
section/company behavior; direct finalizer fallback/laziness/copy/exception
behavior; exact 26/81-definition, 2/1-call, planned 26/80-owner-span,
external-two/local-one, import-DAG, baseline, dead-import and try-depth inventory;
an executable `_heuristic_reflection_query_plan(...)` caller test; and an
executable `_prepare_reflection_retry(...)` caller test. Pin exact args and list
identity, call order, result adoption, input/nested identity, no mutation, and
owner-exception downstream stop. Only after focused 6/6 is independently green
may source move. Then retarget existing private build-query patches, require
retired selected private refs zero, and run reflection owner 24/24, affected
eight-module semantic 758/758, import-side-effect 19/19, union 777/777, runtime
audit 217, projected full discovery 1,764/1,764, pycompile/fresh import,
DAG/body/caller parity, and diff-check gates sequentially. The semantic set is
`tests.test_reflection_capability_contract`,
`tests.test_financial_dependency_projection`, `tests.test_reconciliation_plan`,
`tests.test_subtask_loop`, `tests.test_financial_agent_run_projection`,
`tests.test_operation_contracts`, `tests.test_retrieval_scope`, and
`tests.test_reflection_promotion_gate`.

Keep `_select_retry_strategy_for_reconciliation(...)`,
`_heuristic_reflection_query_plan(...)`, `_infer_missing_info(...)`, and
`_plan_reflection_retry(...)` in reconciliation because they retain dynamic
dependency-resolution/calc-family/mixin or prompt/LLM behavior. Keep
`_prepare_reflection_retry(...)`, action/report/artifact construction, mutable
state clearing, retrieval routing, retry eligibility/budget/promotion, and final
sequencing in their current owners. Do not expand structured-pair extraction,
direct structured-value/precision, compact-ratio, ontology-compatibility,
bound-callback, evidence-mutation, state, carrier, or ledger seams. No behavior,
accuracy, ranking, performance, total-code or executed-path reduction,
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
