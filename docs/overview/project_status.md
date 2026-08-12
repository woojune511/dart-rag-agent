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
| What is the architecture state? | Phase 3 OPEN; bounded caller-facing run projection plus prepared public-answer state projection are owner-held, four named debt groups remain |
| What just changed? | Four prepared public-answer selectors/state projections moved to `financial_agent_run_projection.py` in `a88b215` |
| What passed? | Focused 6/6, run-projection owner 71/71, affected eight-module semantic set 521/521, import-side-effect 19/19, semantic/import union 540/540, runtime audit 217, full unittest 1,750/1,750 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | Two characterize-first seams totaling 293 state-free structured-reconciliation candidate-projection lines into a dedicated owner; LLM rerank, evidence/state mutation, artifact/ledger work, retry orchestration, and final sequencing remain hard stops |

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
- The latest owner batch moved prepared public-answer selection/state projection.
  In `a88b215`, exactly four source/test files changed. The four selected
  definition spans totaled 74 lines and became four public functions totaling
  71 owner lines. Thirteen calls finish as 12 graph-external and one owner-local;
  the cumulative run owner is public ten plus owner-private two with 24 selected
  calls split external 21/local three. Retired selected private source/test refs
  are zero and no wrapper or alias remains. Source is `+105/-93`, net `+12`;
  tests are `+1,269/-8`, net `+1,261`; the whole commit is `+1,374/-101`, net
  `+1,273`. Main graph moved from 1,011 to 936 physical lines and the run owner
  from 215 to 302. The committed source diff SHA-256 is
  `45e12114a8bfb2f7513cbde887b7fe4a8a7b5ed65c2300af902939b6dc38fc45`.
  Dynamic structured/stale answer repair, trace resolution/rebuild, runtime-
  evidence selection, graph execution, compatibility assembly, mutable state/
  evidence, artifact/ledger mutation, and final sequencing remain graph/existing-
  owner responsibilities. This is ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 14,715 lines, main graph 936,
  graph helpers 6,269,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,603,
  dependency projection 3,417, reconciliation 2,079, aggregate projection 3,180,
  task artifacts 1,460, reflection projection 260, and run projection 302.

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
| Latest focused owner checkpoint | PASS, new focused 6 / 6; run-projection owner 71 / 71 |
| Latest semantic regression set | PASS, affected eight-module set 521 / 521; semantic/import union 540 / 540 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,750 / 1,750 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_agent_run_projection`,
`tests.test_financial_aggregate_rank_dedupe`,
`tests.test_evaluator_runtime_projection`,
`tests.test_benchmark_runner_runtime_projection`,
`tests.test_operation_contracts`, `tests.test_financial_router_response`,
`tests.test_ops_runtime_projection_modes`, and
`tests.test_report_scoped_cache_contract`. `tests.test_import_side_effects`
passed separately at 19 / 19 and together with the semantic set as a 540-test
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

The sole selected architecture batch is two sequential characterize-first seams
from `financial_graph_reconciliation.py` into a new state-free
`financial_reconciliation_candidates.py` owner. The target boundary is the
candidate metadata/unit/period/score/identity/row and candidate-ID projection
that runs over already prepared mappings; it does not read or mutate
`FinancialAgentState`.

Seam A moves `_candidate_statement_type(...)` (36 definition-span lines),
`_structured_candidate_unit_hint(...)` (38),
`_fallback_period_text_for_operand(...)` (11), `_structured_cell_identity(...)`
(10), `_resolved_period_text_for_operand(...)` (29),
`_pair_candidate_period_score(...)` (33),
`_build_operand_row_from_candidate_cell(...)` (63), and
`_effective_structured_cell_unit_hint(...)` (17). The 237 former lines project
to 232 owner lines. Publish `structured_cell_identity`,
`pair_candidate_period_score`, `build_operand_row_from_candidate_cell`, and
`effective_structured_cell_unit_hint`; keep the other four owner-private. Its 18
current direct calls finish as 11 reconciliation-external and seven owner-local.

Seam B moves `_find_reconciliation_match_entry(...)` (17),
`_expand_structured_candidate_ids(...)` (26), and
`_structured_candidate_from_id(...)` (13) as three public functions without the
leading underscore. The 56 former lines project to 53 owner lines and all eight
current calls remain reconciliation-external. Together the batch is 293 former
lines becoming 285 owner lines across seven public and four owner-private
functions. Twenty-six calls finish as 19 external and seven owner-local. Delete
every old body and retarget directly; add no wrapper, alias, callback, carrier,
reason, flag, or new output field.

The selected functions preserve explicit statement-type fallback, configured
statement markers, percent and ambiguous-unit handling, period-focus/report-year
fallback, candidate plus structured-cell scoring, stable identity construction,
exact-role-before-first-match selection, lookup magnitude coercion, fresh operand
row construction, stable candidate-ID expansion, and shallow candidate copies.
They preserve current eager access, first-match/tie order, `None` rejection,
top-level copy and nested identity, caller-input immutability, and uncaught
exception behavior.

The new owner depends on existing normalization, operation-policy, structured-
cell, operand-resolution, retrieval-policy, and `financial_graph_helpers`
scoring/period helpers. None imports the new owner, so the import DAG remains
acyclic; the generic helper module remains a dependency rather than becoming a
relocation target. The selected spans hit no runtime-domain baseline record and
the reviewed count remains 217. After movement, reconciliation imports for
`_operand_target_years`, `_resolve_candidate_local_unit_hint`,
`_score_structured_cell`, `coerce_lookup_magnitude_value`,
`_structured_cell_period_text`, `_label_implies_percent_metric`,
`_normalise_operand_value`, and
`FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES` become owner-only and should be
removed from the mixin; every other touched import retains nonselected uses.

Before either source seam moves, add exactly eight CURRENT-SOURCE methods in a
dedicated candidate-owner test module: direct statement/unit handling; direct
period/identity resolution; direct candidate/cell scoring; direct row build and
effective-unit projection; direct reconciliation-match selection; direct ID
expansion/candidate-copy behavior; exact 11-definition/26-call/import-DAG/
baseline/dead-import inventory; and an executable caller matrix spanning
`_extract_structured_period_pair_rows(...)` plus
`_extract_structured_operands_from_reconciliation(...)`. Pin exact args/order,
stable first selection, shallow copies and nested/list identity, no input
mutation, access/laziness boundaries, adoption, and downstream exception-stop.
Then move A and B sequentially, retarget existing private test patches, require
retired refs zero, and run focused eight, candidate-owner eight, affected
seven-module semantic 486, import-side-effect 19, union 505, runtime audit 217,
projected full discovery 1,758, pycompile/fresh import, DAG, body/caller parity,
and diff-check gates sequentially. The semantic set is the new candidate-owner
module plus `tests.test_reconciliation_plan`,
`tests.test_financial_operand_resolution`,
`tests.test_financial_dependency_projection`,
`tests.test_financial_task_artifacts`, `tests.test_operation_contracts`, and
`tests.test_structured_operand_extraction`.

Keep `_extract_structured_period_pair_rows(...)`, structured-cell selection,
`_extract_structured_operands_from_reconciliation(...)`, candidate collection,
LLM reranking, reconciliation evidence-item construction, artifact updates,
retry planning, mutable reconciliation state/evidence, and final sequencing in
their current owners. Do not move or duplicate graph-helper scoring primitives
to avoid a second owner, and do not expand direct structured-value, precision,
prepared-candidate, compact-ratio, ontology-compatibility, bound-callback,
evidence-mutation, state, or ledger seams. No behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark, schedule, or
Phase 3 completion claim follows.

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
