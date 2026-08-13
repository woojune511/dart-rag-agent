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
| What is the architecture state? | Phase 3 OPEN; deterministic runtime and ontology planning are execution-owned, four named debt groups remain |
| What just changed? | Three query-focus/source-visible text functions totaling 220 old definition lines moved to `financial_text_surface.py` in `6d54b2f` |
| What passed? | Focused 10/10, text owner 30/30, affected seven-module semantic set 808/808, import-side-effect 19/19, runtime audit 218, full unittest 1,834/1,834 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest text-ownership changes |
| What is next? | One characterize-first 202-line structured period-pair projection into `financial_reconciliation_candidates.py`; candidate collection, full operand extraction, state/artifact work, LLM reranking, and final sequencing remain hard stops |

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
- An earlier two-seam owner batch moved prepared nested-result replacement and
  arithmetic subtask-surface synchronization. Across `6ed195e..b5d97ee`, the
  former 64 + 124 = 188 graph definition lines became public 63 + 123 = 186
  owner lines; all four selected calls remain graph-external and retired
  private refs are zero. Source is `+197/-204`, net `-7`; tests are
  `+1,569/-184`, net `+1,385`; the whole range is `+1,766/-388`, net `+1,378`.
  Calculation moved from 14,719 to 14,521 physical lines and aggregate
  projection from 3,350 to 3,541. The range source diff SHA-256 is
  `ee76d6ffa2c0e1f14e8dec7630a6f11e5f39ad4323e1ed5a23f07e6d0fbda1f8`.
  Graph state/evidence, dependency alignment, projection rebuild,
  artifact/ledger mutation, and final sequencing remain graph-owned. This is
  ownership relocation, not a behavior claim.
- Commit `b3bb764` moved the former 53-line
  `_recover_duplicate_growth_prior_operand(...)` body to one 52-line public
  `recover_duplicate_growth_prior_operand(...)` owner function. Its sole call
  remains graph-external in calculation-candidate preparation, after growth
  unit alignment and before the period-conflict gate. Source is `+56/-55`, net
  `+1`; tests are `+629/-26`, net `+603`; the whole commit is `+685/-81`, net
  `+604`. Calculation moved from 14,521 to 14,468 physical lines and aggregate
  projection from 3,541 to 3,595. Four new test methods moved discovery from
  1,789 to 1,793. The source diff SHA-256 is
  `1a02ec371d28b6012b064281260ad3b274bc9f1ef0b330d0724c36d545b56d1a`.
  Retired private refs are zero in source and tests. Candidate construction,
  unit/period alignment, execution, state/evidence, rebuild, artifact/ledger,
  and final sequencing remain graph-owned. This is ownership relocation, not a
  behavior claim.
- Commit `d31e67a` moved the former 48-line
  `_filter_final_aggregate_evidence_and_projection(...)` body to one 47-line
  public `filter_final_aggregate_evidence_and_projection(...)` owner function.
  Its two calls remain graph-external in aggregate orchestration, before the
  ordinary state sync/runtime-ratio repair and after conditional stale-state
  replacement respectively. Source is `+52/-53`, net `-1`; tests are
  `+646/-41`, net `+605`; the whole commit is `+698/-94`, net `+604`.
  Calculation moved from 14,468 to 14,418 physical lines and aggregate
  projection from 3,595 to 3,644. Four new test methods moved discovery from
  1,793 to 1,797. The source diff SHA-256 is
  `f10c327aca0fb5a4a885892354bef1b840caaf224a9696ae113c9d650df45df1`.
  Retired private refs are zero in source and tests. Evidence preparation,
  stale/runtime-ratio repair, state synchronization, answer composition,
  artifact/ledger mutation, and final sequencing remain graph-owned. This is
  ownership relocation, not a behavior claim.
- Commit `8861253` moved the former 310-line
  `_repair_collapsed_ratio_trace_from_evidence(...)` body to one 309-line public
  `repair_collapsed_ratio_trace_from_evidence(...)` runtime-trace function. Its
  two calls remain graph-external in `financial_graph.py`: one after a nonempty
  structured public projection and one before the separate period-comparison
  repair. Source is `+322/-315`, net `+7`; tests are `+1,574/-166`, net
  `+1,408`; the whole commit is `+1,896/-481`, net `+1,415`. Calculation moved
  from 14,418 to 14,106 physical lines, main graph from 937 to 938, and runtime
  trace from 1,094 to 1,412. Six new test methods moved discovery from 1,797 to
  1,803. The source diff SHA-256 is
  `a83d1ddaa2167516789bc9de1a90033dd7183d6764ddf0609bf91a777199e451`.
  Retired private refs are zero, the runtime-trace owner contains three public
  and 28 private top-level functions, and the reviewed runtime-domain count
  remains 217. Public-answer orchestration, period repair, retrieval/canonical
  evidence construction, mutable state/evidence, artifact/ledger mutation, and
  final sequencing remain graph-owned. This is ownership relocation, not a
  behavior claim.
- Commit `5f9dc5c` moved the former 81-line direct structured lookup-row and
  139-line direct structured operand-value bodies to public 80-line
  `lookup_row_from_direct_structured_evidence(...)` and 138-line
  `coerce_operand_value_from_direct_structured_evidence(...)` in
  `financial_lookup_recovery.py`. All five calls remain graph-external and the
  old private source/test refs are zero. Source is `+241/-229`, net `+12`;
  tests are `+1,229/-8`, net `+1,221`; the whole commit is `+1,470/-237`, net
  `+1,233`. Calculation moved from 14,106 to 13,887 physical lines and lookup
  recovery from 557 to 788. Eight new test methods moved discovery from 1,803
  to 1,811. The source diff SHA-256 is
  `c4b9c78f90715b4332b559159220e00e6f00d46d2912a4f982cdbabaf0fd271e`.
  The lookup owner contains 11 public and seven private top-level functions;
  the newly dead calculation `_structured_cell_period_text` import was removed
  and the reviewed runtime-domain count remains 217. Evidence-pool
  selection/scoring, state/report scope, table-label lookup, precision
  refinement, mutable evidence, artifact/ledger mutation, and final sequencing
  remain graph-owned. This is ownership relocation, not a behavior claim.
- Commit `a476dd9` moved the former 62-line own-evidence lookup-unit alignment
  body to public 61-line
  `align_lookup_result_units_from_own_evidence(...)` in
  `financial_aggregate_projection.py`. Both calls remain graph-external and the
  old private source/test refs are zero. Source is `+74/-68`, net `+6`; tests
  are `+786/-13`, net `+773`; the whole commit is `+860/-81`, net `+779`.
  Calculation moved from 13,887 to 13,823 physical lines and aggregate
  projection from 3,644 to 3,714. Four new test methods moved discovery from
  1,811 to 1,815. The source diff SHA-256 is
  `bbe5f3cc62535f3fe8b6d2c2a4a56a27b10d0515cf0fff2083105d34ed171e19`.
  The aggregate owner contains 75 public and 11 private top-level functions;
  the newly dead calculation `lookup_primary_slot` and
  `replace_lookup_primary_slot` imports were removed and the reviewed
  runtime-domain count remains 217. Peer-source callback alignment, evidence
  preparation, rebuild, mutable state/evidence, artifact/ledger mutation, and
  final sequencing remain graph-owned. This is ownership relocation, not a
  behavior claim.
- Commit `c021d30` moved the former 37-line runtime operation-plan adapter and
  200-line ontology plan out of the calculation mixin as public 36-line
  `build_runtime_deterministic_operation_plan(...)` and 195-line
  `build_deterministic_ontology_plan(...)` in
  `financial_calculation_execution.py`. All four selected calls remain direct,
  graph-external, and outside `try` blocks; the ontology caller still copies
  the active task before invoking dynamic `self._calc_metric_family(state)`.
  Source is `+247/-244`, net `+3`; tests are `+1,111/-17`, net `+1,094`;
  the reviewed baseline is `+9/-9`; the whole commit is `+1,367/-270`, net
  `+1,097`. Calculation moved from 13,823 to 13,589 physical lines and the
  execution owner from 837 to 1,074. Nine new test methods moved discovery from
  1,815 to 1,824. The source diff SHA-256 is
  `3d93584b12246297296b01f738fedb55e3b8aa71b7805b5d7003f430bbfd411b`.
  The execution owner contains 13 public and zero private top-level functions,
  the old mixin definitions and executable private call/patch refs are zero,
  and exactly three reviewed runtime-domain records moved with unchanged text,
  category, and count; the reviewed total remains 217. Deterministic lookup
  planning, guard/adoption, LLM planning, state/trace/artifact updates,
  execution orchestration, and final sequencing remain graph-owned. This is
  ownership relocation, not a behavior claim.
- Commit `6d54b2f` moved the former 85-line query-focus marker-group, 8-line
  flattened-marker, and 127-line source-visible term-preservation definitions
  into `financial_text_surface.py` as public 85-line
  `query_focus_marker_groups(...)`, 8-line `query_focus_markers(...)`, and
  126-line `preserve_source_visible_query_terms(...)`. Twelve selected calls
  finish as ten graph-external and two owner-local; the old private definitions,
  executable calls, patches, and the evidence stopword alias are zero. Source is
  `+255/-245`, net `+10`; tests are `+1,199/-41`, net `+1,158`; the reviewed
  baseline is `+12/-3`, net `+9`; and the whole commit is `+1,466/-289`, net
  `+1,177`. Calculation moved from 13,589 to 13,464 physical lines, graph
  evidence from 4,581 to 4,579, retrieval from 2,736 to 2,642, and text surface
  from 411 to 642. Ten new tests moved discovery from 1,824 to 1,834.
  The source-only diff SHA-256 is
  `b27abac6c0b25f3e8aa888856ba7017c5b300463c7da4cbe68c7096e401781be`;
  source plus baseline is
  `42ae44c153d6bd8af1396a61ef3f23dad37945c7a94422aee8dc8bb66e080e11`.
  One reviewed `[가-힣]` occurrence split from a retrieval count-two record into
  retrieval and text-owner count-one records, preserving literal/category and
  occurrence count while moving the reviewed record total from 217 to 218.
  Retrieval/reranking, evidence construction, aggregate orchestration, mutable
  state/evidence, artifact/ledger work, and final sequencing remain graph-owned.
  This is ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 13,464 lines, calculation
  execution 1,074, main graph 938,
  graph helpers 6,269,
  planning 2,048, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 625, text surface 642, operand resolution 3,603,
  dependency projection 3,417, reconciliation 1,667, reconciliation candidates
  329, aggregate projection 3,714, runtime trace 1,412, lookup recovery 788,
  task artifacts 1,460, reflection projection
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
| Dependency and execution | `financial_dependency_projection.py`, including dependency input matching/binding, sibling-output synthesis preference, sibling lookup-surface preparation, and resolved reconciliation projection, plus `financial_calculation_execution.py`, including base/runtime deterministic operation planning, ontology planning, plan guarding, execution, and value freshness |
| Lookup recovery | `financial_lookup_recovery.py`, including lookup magnitude/unit recovery, selected-evidence consistency/refinement, successful-row alignment/replacement, and direct structured lookup-row/value projection over already supplied evidence |
| Structured reconciliation candidates | `financial_reconciliation_candidates.py`; state-free statement/unit/period/score/identity/row/match and candidate-ID projection over already prepared mappings |
| Calculation rendering | `financial_graph_calculation_rendering.py`, including ratio unit/query/result projection and scalar/time-series display helpers |
| Answer and numeric surfaces | `financial_answer_slots.py`, `financial_answer_projection.py`, `financial_numeric_surface.py`, and `financial_text_surface.py`, including period/material, nested-row traversal/scoring/selected-result promotion, ratio-readiness, narrative validation, numeric/scale predicates, shared sentence/token surfaces, query-focus marker projection, and source-visible term preservation |
| Aggregate projection | `financial_aggregate_projection.py`, including aggregate calculation/public projection, subtask upsert/rank, selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, nested-result replacement, arithmetic subtask-surface synchronization, duplicate growth-prior recovery, final evidence/provenance projection, own-evidence lookup-unit alignment, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering and trace inspection, result support/reuse predicates, prepared growth/ratio material inspection, final-answer evidence filtering/operand append/surface-operand projection, and growth-answer completion/sanitization |
| Composition, trace, artifacts | `financial_aggregate_state.py`, `financial_runtime_trace.py`, and `financial_task_artifacts.py`; runtime trace includes collapsed-ratio evidence repair and the task-artifact owner includes bounded reconciliation artifact refs, runtime-evidence merge, and ratio result-row projection, but neither owns ledger mutation orchestration |
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
| Latest focused owner checkpoint | PASS, query-focus Seam A 5 / 5; source-visible Seam B 5 / 5; combined 10 / 10; text owner 30 / 30 |
| Latest semantic regression set | PASS, affected seven-module set 808 / 808 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 218 reviewed records |
| Full unittest discovery | PASS, 1,834 / 1,834 |
| Benchmark refresh after latest text-ownership changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_text_surface`,
`tests.test_financial_retrieval_pipeline`, `tests.test_operation_contracts`,
`tests.test_financial_aggregate_rank_dedupe`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, and
`tests.test_aggregate_subtask_projection`. `tests.test_import_side_effects`
passed separately at 19 / 19; no combined-union run is claimed for this commit.

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
| Aggregate repair and precedence | Partially advanced through aggregate calculation/public projection, subtask upsert/rank, nested traversal/scoring/selected-result promotion, nested-result replacement, arithmetic subtask-surface synchronization, period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, prepared growth-numeric rendering and trace inspection, result support/reuse, prepared material inspection, bounded row/gap/lookup-answer ownership, final-answer evidence/provenance/surface-operand projection, own-evidence lookup-unit alignment, and growth-answer completion/sanitization; peer-source alignment, broader rebuild and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, lookup magnitude, same-block unit/table repair, direct structured lookup-row/value projection, dependency input matching/binding, and deterministic runtime/ontology planning; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Minimally advanced through bounded read-only reconciliation artifact-reference projection; artifact mutation and whole-ledger synchronization require separate contracts |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture work is one characterize-first prepared
structured period-pair projection into the existing
`financial_reconciliation_candidates.py` owner. Move reconciliation-private
`_extract_structured_period_pair_rows(...)` (202 definition-span lines) as
projected public 201-line `extract_structured_period_pair_rows(...)`. Its sole
caller remains a direct imported-name call in
`_extract_structured_operands_from_reconciliation(...)`, graph-external and
outside `try`, with the exact nine keywords `required_operands`,
`reconciliation_result`, `candidate_map`, `preferred_statement_types`,
`constraints`, `query_years`, `start_index`, `operation_family`, and
`report_scope`. The candidate owner projects from public/private 7/4 to 8/4.

The function receives prepared operand, match, candidate, constraint, scope,
and year mappings only. Preserve current-period/prior-period grouping by concept
then label; first-seen candidate-ID dedupe and structured-ID expansion;
candidate-kind and direct-acceptance gates; copied metadata/cell/sibling
surfaces; same-candidate and same-table cross-candidate pair scoring; strict
first-max tie retention; cell identity and equal-period rejection; table-source
bonuses; current/prior unit-hint propagation; stable row order and start-index
increments; handled `(label, role)` pairs; fresh row/set outputs; nested alias
behavior; caller-input immutability; access laziness; and uncaught exceptions.

The target already imports `financial_graph_helpers`; add only
`_candidate_satisfies_direct_acceptance_contract` on that existing edge and
`_parse_unstructured_table_row_cells` from `financial_row_surfaces`. Neither
dependency reaches back to the candidate owner, and the owner does not reach
`financial_graph_reconciliation`, so the import DAG remains acyclic. The
selected span has zero reviewed runtime-domain baseline records; audit total
must remain 218. The graph's two dependency symbols remain live in other
reconciliation paths, so no projected dead import is claimed.

Before production movement, add exactly six CURRENT-SOURCE methods to
`tests.test_financial_reconciliation_candidates`: four direct matrices for
grouping/candidate gates, same-candidate pairing, same-table cross-candidate
fallback, and
unit/row/handled/copy/exception behavior; one exact 202-line/one-call/signature/
keyword/try-depth/DAG/baseline/retired-ref inventory; and one executable
`_extract_structured_operands_from_reconciliation(...)` caller contract for
exact arguments, result adoption, row ordering, handled-row skip, input
identity/no-mutation, and exception stop. Freeze source before public-retarget;
compatibility wrappers, aliases, and executable retired private refs are
forbidden.

Projected gates after the six methods are focused 6/6, candidate owner 14/14,
affected seven-module semantic 787/787, import-side-effect 19/19, runtime audit
218, full discovery 1,840/1,840, pycompile/fresh import, DAG/body/full-caller
parity, retired-ref zero, and diff check. The semantic set is
`tests.test_financial_reconciliation_candidates`,
`tests.test_financial_operand_resolution`, `tests.test_financial_task_artifacts`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, and
`tests.test_operation_contracts`.

This narrowly supersedes the former conservative stop on structured-pair
projection; full `_extract_structured_operands_from_reconciliation(...)`,
candidate collection/selection, LLM reranking, evidence construction,
artifact/retry/state mutation, ledger work, and final sequencing remain graph-
owned. Continue to reject precision and direct-structured carrier expansions
that create `financial_graph_helpers` reverse cycles, reconciliation seed
supplementation that owns vector-store state, compact-ratio/state carriers,
ontology completion with guarded compatibility placements, bound callbacks,
and broader state/ledger extraction. No behavior, accuracy, ranking,
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
