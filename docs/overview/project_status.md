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
| What just changed? | Eight semantic-planner normalization/validation definitions totaling 273 old lines moved to `financial_graph_helpers.py` as five public and three owner-private functions totaling 271 lines in `fb970a5` |
| What passed? | Focused 7/7, helper owner 12/12, affected eight-module semantic set 434/434, import-side-effect 19/19, runtime audit 218, full unittest 1,847/1,847 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest semantic-planner ownership change |
| What is next? | One characterize-first 143-line narrative-task policy batch into `financial_graph_helpers.py`; model invocation, graph plan adoption, state/artifact mutation, and final sequencing remain hard stops |

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
- Commit `79a460a` moved the former 202-line
  `_extract_structured_period_pair_rows(...)` body from the reconciliation mixin
  to public 201-line `extract_structured_period_pair_rows(...)` in
  `financial_reconciliation_candidates.py`. Its sole exact nine-keyword call
  remains direct, graph-external, and outside `try`; the old mixin definition
  and executable private refs are zero. Source is `+207/-204`, net `+3`; tests
  are `+763/-29`, net `+734`; and the whole commit is `+970/-233`, net `+737`.
  Reconciliation moved from 1,667 to 1,465 physical lines and the candidate
  owner from 329 to 534. Six new test methods moved discovery from 1,834 to
  1,840. The source diff SHA-256 is
  `8bd82f6adb5e9722771953888dbeef6e129332ae4b749b6483ba46017db7cf3e`.
  The candidate owner is public/private 8/4, its new graph-helper and row-surface
  imports are acyclic, and the reviewed runtime-domain baseline remains 218
  records without a record move. Full operand extraction, candidate collection
  and selection, LLM reranking, evidence construction, artifact/retry/state
  mutation, ledger work, and final sequencing remain graph-owned. This is
  ownership relocation, not a behavior claim.
- Commit `fb970a5` moved eight semantic-planner normalization and validation
  definitions totaling 273 old definition-span lines from
  `financial_graph_planning.py` into `financial_graph_helpers.py`. Public
  segment-sum/analysis-shape predicates, segment-label projection, scope
  alignment, and planner-task validation plus three owner-private helpers now
  total 271 owner lines. Sixteen selected calls finish graph-external nine and
  owner-local seven; all remain direct and outside `try`. Source is
  `+303/-296`, net `+7`; tests are `+1,557/-9`, net `+1,548`; and the whole
  commit is `+1,860/-305`, net `+1,555`. Planning moved from 2,048 to 1,765
  physical lines and graph helpers from 6,269 to 6,559. Seven new unittest
  methods moved full discovery from 1,840 to 1,847. The source diff SHA-256 is
  `9e0310f17edd4ea004425957e8044fc6ae0f79538ab140bd4a9e8007aa4d63cc`.
  The helper owner is public/private 5/132, its dependency changes are acyclic,
  the two now-dead planning imports were removed, and the reviewed runtime-
  domain baseline remains 218 without a record move. Model invocation, query
  routing, plan adoption, mutable task/state/artifact/ledger work, and final
  sequencing remain graph-owned. This is ownership relocation, not a behavior
  claim.
- Current physical sizes are: calculation graph 13,464 lines, calculation
  execution 1,074, main graph 938,
  graph helpers 6,559,
  planning 1,765, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 625, text surface 642, operand resolution 3,603,
  dependency projection 3,417, reconciliation 1,465, reconciliation candidates
  534, aggregate projection 3,714, runtime trace 1,412, lookup recovery 788,
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
| Semantic planning normalization | `financial_graph_helpers.py`; state-free scope normalization, plan-shape predicates, segment-label projection, and planner-task validation, excluding model invocation and plan/state adoption |
| Operand policy and resolution | `financial_operand_resolution.py`, including ratio sign policy, evidence-local unit/period coercion, dependency-task KRW consistency, table-metadata/raw-unit repair, and growth alignment/period conflict |
| Dependency and execution | `financial_dependency_projection.py`, including dependency input matching/binding, sibling-output synthesis preference, sibling lookup-surface preparation, and resolved reconciliation projection, plus `financial_calculation_execution.py`, including base/runtime deterministic operation planning, ontology planning, plan guarding, execution, and value freshness |
| Lookup recovery | `financial_lookup_recovery.py`, including lookup magnitude/unit recovery, selected-evidence consistency/refinement, successful-row alignment/replacement, and direct structured lookup-row/value projection over already supplied evidence |
| Structured reconciliation candidates | `financial_reconciliation_candidates.py`; state-free statement/unit/period/score/identity/row/match, candidate-ID, and structured period-pair projection over already prepared mappings |
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
| Latest focused owner checkpoint | PASS, semantic-planner batch 7 / 7; graph-helper owner 12 / 12 |
| Latest semantic regression set | PASS, affected eight-module set 434 / 434 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 218 reviewed records |
| Full unittest discovery | PASS, 1,847 / 1,847 |
| Benchmark refresh after latest semantic-planner ownership change | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_graph_helpers`,
`tests.test_semantic_numeric_plan`, `tests.test_semantic_numeric_planner`,
`tests.test_reconciliation_plan`, `tests.test_operation_contracts`,
`tests.test_part_whole_ratio_contract`, `tests.test_concept_runtime_contracts`,
and `tests.test_structured_operand_extraction`.
`tests.test_import_side_effects`
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
| Private API mesh and test co-location | Partially advanced as public contracts and semantic-planner normalization/validation move; narrative-task policy and broader orchestration remain |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture work is one characterize-first narrative-task
policy batch from `financial_graph_planning.py` into its existing semantic-
planning owner, `financial_graph_helpers.py`. Move six definitions totaling 143
old definition-span lines: owner-private `_is_narrative_summary_task(...)` 4
and `_needs_hybrid_narrative_subtask(...)` 2; public
`build_hybrid_narrative_subtask(...)` 63,
`append_hybrid_narrative_task(...)` 38,
`push_narrative_tasks_after_numeric(...)` 31, and
`exclusive_narrative_task_policy_active(...)` 5. The target projects from
public/private 5/132 to 9/134; no compatibility wrapper or alias is allowed.

All 13 selected references are direct calls outside `try` blocks. After the
move, six remain graph-external and seven become owner-local: narrative-summary
predicate 0/5, hybrid-need predicate 0/1, hybrid-task builder 1/1, hybrid append
2/0, numeric-before-narrative ordering 2/0, and exclusive-policy gate 1/0.
Preserve intent and narrative-context gating, consolidation and period focus,
active-policy and slot-group order, format preference precedence, stable
retrieval-query dedupe, preferred sections, copied input tasks, task-ID
increment rules, narrative-task detection, numeric dependency append order,
numeric-before-narrative ordering, input immutability, access laziness, and
uncaught exceptions.

The target already owns `PLANNING_POLICY`, normalization, `_infer_period_focus`,
`_desired_consolidation_scope`, typing, and regex support. Add the active-
narrative-policy, slot, section, suffix, and term helpers on its existing
retrieval-policy edge, `_query_requests_narrative_context` on its existing
operation-policy edge, and `default_format_preference` through one reviewed,
acyclic routing edge. No routing module imports the helper owner. Retire the
planning module's ten newly dead imports: `_infer_period_focus`,
`_query_requests_narrative_context`, `_desired_consolidation_scope`,
`NARRATIVE_BASE_RETRIEVAL_SUFFIXES`, `active_narrative_policies`,
`narrative_policy_preferred_sections`, `narrative_policy_query_suffixes`,
`narrative_policy_slot_groups`, `narrative_policy_terms`, and
`default_format_preference`. The selected spans contain zero reviewed runtime-
domain records, so audit total must remain 218.

Before production movement, add exactly six CURRENT-SOURCE methods to
`tests.test_financial_graph_helpers`: one direct predicate/gate matrix; direct
builder, append, and numeric-before-narrative ordering matrices; one exact six-
definition/143-line/13-call/signature/try-depth/DAG/dead-import/baseline
inventory; and one executable contract covering
`_plan_exclusive_narrative_task(...)` plus both replan and initial paths in
`_plan_semantic_numeric_tasks(...)`. Pin exact arguments, identity/copy/no-
mutation, ordering, adoption, laziness, and exception stop. Freeze source before
public retarget; wrappers, aliases, callback bridges, and executable retired
private refs are forbidden.

Projected gates are focused 6/6, helper owner 18/18, affected eight-module
semantic 440/440, import-side-effect 19/19, runtime audit 218, full discovery
1,853/1,853, pycompile/fresh import, DAG/body/full-caller parity, retired-ref
zero, and diff check. The semantic set remains
`tests.test_financial_graph_helpers`, `tests.test_semantic_numeric_plan`,
`tests.test_semantic_numeric_planner`, `tests.test_reconciliation_plan`,
`tests.test_operation_contracts`, `tests.test_part_whole_ratio_contract`,
`tests.test_concept_runtime_contracts`, and
`tests.test_structured_operand_extraction`.

Keep `_project_logical_tasks_from_execution_tasks(...)`,
`_dependency_closure_task_ids(...)`,
`_non_numeric_operation_intent_override(...)`,
`_plan_exclusive_narrative_task(...)`, and
`_plan_semantic_numeric_tasks(...)` graph-owned. LLM/model invocation, query
routing, task/state/artifact/ledger mutation, plan adoption, retrieval/evidence
work, and final sequencing remain hard stops. Continue to reject evidence-
building and narrative-evidence mutation, ratio operand assembly that would
introduce a graph-helper/operand reverse cycle, precision/custom-carrier moves,
compact-ratio state, ontology compatibility gates, vector-store callbacks, and
broader state/ledger extraction. No behavior, accuracy, ranking, performance,
total-code or executed-path reduction, benchmark, schedule, or Phase 3
completion claim follows.

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
