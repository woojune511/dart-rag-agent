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
| What is the architecture state? | Phase 3 OPEN; reflection retry-query projection is now owner-held, four named debt groups remain |
| What just changed? | Retry-query construction and finalization moved to `financial_reflection_projection.py` in `b74535e` |
| What passed? | Focused 6/6, reflection-owner 24/24, affected eight-module semantic set 758/758, import-side-effect 19/19, semantic/import union 777/777, runtime audit 217, full unittest 1,764/1,764 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 156-line aggregate subtask projection/upsert batch into `financial_aggregate_projection.py`; nested promotion, mutable state, synchronization/rebuild, and final sequencing remain hard stops |

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
- The latest owner batch moved reflection retry-query construction and
  finalization. In `b74535e`, exactly five source/test files changed. The two
  selected definition spans totaled 107 lines and became two public functions
  totaling 106 owner lines. Three calls finish as two graph-external and one
  owner-local. Retired selected private source/test refs are zero and no wrapper
  or alias remains. Source is `+118/-112`, net `+6`; tests are `+1,113/-4`, net
  `+1,109`; the whole commit is `+1,231/-116`, net `+1,115`. Reconciliation moved
  from 1,776 to 1,667 physical lines, reflection projection from 260 to 374, and
  calculation from 14,715 to 14,716. The committed source diff SHA-256 is
  `728603f15ce24c0915444755442bc6cf3be4a2bbd26c6f41adffedcb08ccdbb1`.
  Heuristic dependency/calc-family resolution, missing-info inference, prompt/
  model planning, action/report/artifact construction, mutable state, routing/
  promotion, and final sequencing remain graph-owned. This is ownership
  relocation, not a behavior claim.
- Current physical sizes are: calculation graph 14,716 lines, main graph 936,
  graph helpers 6,269,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,603,
  dependency projection 3,417, reconciliation 1,667, reconciliation candidates
  329, aggregate projection 3,180, task artifacts 1,460, reflection projection
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
| Answer and numeric surfaces | `financial_answer_slots.py`, `financial_answer_projection.py`, `financial_numeric_surface.py`, and `financial_text_surface.py`, including period/material, ratio-readiness, narrative validation, numeric/scale predicates, and shared sentence/token surfaces |
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering and trace inspection, result support/reuse predicates, prepared growth/ratio material inspection, final-answer evidence filtering/operand append/surface-operand projection, and growth-answer completion/sanitization |
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
| Latest focused owner checkpoint | PASS, new focused 6 / 6; reflection owner 24 / 24 |
| Latest semantic regression set | PASS, affected eight-module set 758 / 758; semantic/import union 777 / 777 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,764 / 1,764 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_reflection_capability_contract`,
`tests.test_financial_dependency_projection`, `tests.test_reconciliation_plan`,
`tests.test_subtask_loop`, `tests.test_financial_agent_run_projection`,
`tests.test_operation_contracts`, `tests.test_retrieval_scope`, and
`tests.test_reflection_promotion_gate`. `tests.test_import_side_effects` passed
separately at 19 / 19 and together with the semantic set as a 777-test union.

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

The sole selected architecture batch is one characterize-first aggregate
subtask projection/upsert move from `financial_graph_planning.py` into the
existing `financial_aggregate_projection.py` owner. Move
`_build_aggregate_calculation_projection(...)` (69 current definition-span
lines) as public `build_aggregate_calculation_projection(...)`,
`_structured_subtask_projection_for_public_answer(...)` (36) as public
`structured_subtask_projection_for_public_answer(...)`,
`_upsert_subtask_result(...)` (23) as public `upsert_subtask_result(...)`, and
`_subtask_upsert_quality_rank(...)` (28) as owner-private
`_subtask_upsert_quality_rank(...)`. Removing four standalone `self` parameters
projects the 156 former lines to 152 owner lines. Six selected calls finish as
four graph-external calls and two owner-local upsert-rank calls. Delete the old
bodies and retarget directly; add no wrapper, compatibility alias, callback,
carrier, reason, flag, or output field. The aggregate owner becomes public 70
plus owner-private 11.

`build_aggregate_calculation_projection(...)` must preserve ordered row scans,
the owner-local aggregate-operation-family decision, conflicting-growth period
rejection, material-gap projection, answer-slot/source-reference clearing on a
fresh row/result copy, runtime-trace aggregate construction, stable runtime-
evidence order and ID-or-surface dedupe, and the current returned four-field
shape. `structured_subtask_projection_for_public_answer(...)` must preserve
structured-result/public-answer equality gates, current rendered-value checks,
preferred complete-answer fallback, runtime-trace aggregate construction,
subtask-results materiality, and attached projection metadata. Both functions
must retain mapping/list access order, shallow-copy and nested-identity behavior,
input immutability, helper laziness, and uncaught exception propagation.

`upsert_subtask_result(...)` must preserve empty-current list copying, task-ID
matching, first-seen row order, quality-rank comparison, stable existing-row
preference only when its rank is strictly greater, current-row adoption on ties,
duplicate task-ID replacement behavior, append-on-miss, caller row identity, and
no input mutation. Its owner-private rank must preserve status, material,
structured-payload, cleaned-source-count, digit-count, and answer-length tuple
order together with the current status fallbacks, truthiness, normalization,
source cleaning, and exception scopes.

The aggregate owner already owns every runtime dependency used by the selected
bodies or an existing edge to it: answer-projection growth/material predicates,
runtime normalization, runtime-trace projection helpers, and the owner-local
`aggregate_result_operation_family(...)`. Add only the existing runtime-trace
symbols, `_preferred_complete_aggregate_subtask_answer`, and type-only graph-state
annotation imports. Runtime trace and graph state do not import aggregate
projection. Graph calculation and the main graph already import the aggregate
owner, while planning does not need to import it after these four bodies are
removed; therefore this exact cut adds no cycle. The selected spans hit no
runtime-domain baseline record and the reviewed count remains 217. Remove only
planning imports made dead by the selected bodies: the preferred-complete-answer,
growth-conflict/material-gap, attach-metadata, runtime aggregate-builder, and
structured-result-row helpers. `_clean_source_row_ids` and
`subtask_row_has_material` remain live in the retained planning code.

Before production movement, add exactly seven CURRENT-SOURCE methods to
`tests.test_aggregate_subtask_projection`: a direct aggregate-calculation
projection branch/copy/evidence-order/dedupe/exception matrix; a direct
structured-public projection gate/adoption/metadata/laziness/exception matrix;
a direct upsert/rank/tie/order/identity/no-mutation/exception matrix; exact
69/36/23/28-definition, six-call, planned 68/35/22/27-owner-span,
external-four/local-two, import-DAG, baseline, dead-import and try-depth
inventory; an executable `_rebuild_aggregate_projection(...)` caller test; an
executable `_structured_public_answer_trace_projection(...)` caller test; and a
combined executable `_advance_calculation_subtask(...)` plus
`_prepare_initial_aggregate_state(...)` upsert caller test. Pin exact args and
list/mapping identity, call order, result adoption, input/nested identity, no
mutation, and owner-exception downstream stop. Only after focused 7/7 is
independently green may source move.

Then retarget selected mixin direct calls and patches while leaving the distinct
runtime-trace private `_build_aggregate_calculation_projection(...)` helper and
its tests intact. Require the planning definitions and selected mixin-qualified
refs to be zero, and run aggregate-subtask owner 118/118, affected seven-module
semantic 780/780, import-side-effect 19/19, union 799/799, runtime audit 217,
projected full discovery 1,771/1,771, pycompile/fresh import, DAG/body/caller
parity, and diff-check gates sequentially. The semantic set is
`tests.test_financial_aggregate_rank_dedupe`,
`tests.test_aggregate_subtask_projection`, `tests.test_financial_answer_projection`,
`tests.test_lookup_recovery_policy`, `tests.test_financial_agent_run_projection`,
`tests.test_subtask_loop`, and `tests.test_operation_contracts`.

Keep `_capture_current_subtask_result(...)`, `_rebuild_aggregate_projection(...)`,
`_structured_public_answer_trace_projection(...)`, both upsert callers, mutable
state clearing, projection filtering, nested-result promotion, aggregate
recovery/alignment/synchronization, artifact/ledger mutation, and final
sequencing in their current graph owners. Do not co-move `_nested_subtask_rows`,
operation-family/specificity scoring, or nested promotion: that expansion would
make planning import aggregate while aggregate already reaches planning through
dependency projection, creating an import cycle. Also reject direct structured-
value/precision, compact-ratio, ontology-compatibility, bound-callback,
evidence-mutation, state, carrier, and ledger seams. No behavior, accuracy,
ranking, performance, total-code or executed-path reduction, benchmark,
schedule, or Phase 3 completion claim follows.

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
