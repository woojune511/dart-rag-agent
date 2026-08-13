# Project Status

> Single authority for current product state, gates, blockers, and priority.
> Stable runtime semantics live in
> [agent_runtime_contract.md](../architecture/agent_runtime_contract.md); completed
> implementation and experiment chronology live in
> [implementation_history.md](../history/implementation_history.md) and
> [experiment_history.md](../history/experiment_history.md).

Last updated: 2026-08-14

## At A Glance

| Question | Current answer |
| --- | --- |
| What is the product? | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Is the core path blocked? | No known unit/contract correctness blocker |
| What is the architecture state? | Phase 3 OPEN; deterministic runtime and ontology planning are execution-owned, four named debt groups remain |
| What just changed? | `55bc286` moved the exact 11/25-line query/task period-focus pair from graph helpers to public scope-policy ownership |
| What passed? | Focused 4/4, owner module 74/74, affected eleven-module semantic set 1,034/1,034, import-side-effect 19/19, runtime audit 218, full unittest 1,927/1,927 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest query/task period-focus ownership change |
| What is next? | Add four CURRENT-SOURCE contracts, then move only the exact 16/18-line candidate value-role/aggregation-stage pair to row-surface ownership |

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
- Commit `f9244d6` moved six narrative-task policy definitions totaling 143
  lines from `financial_graph_planning.py` into `financial_graph_helpers.py`.
  Public hybrid-task build/append, numeric-before-narrative ordering, and
  exclusive-policy projection plus two owner-private predicates preserve the
  exact definition-span total. Thirteen selected calls finish graph-external
  six and owner-local seven; all remain direct and outside `try`. Source is
  `+173/-173`, net `0`; tests are `+1,245/-15`, net `+1,230`; and the whole
  commit is `+1,418/-188`, net `+1,230`. Planning moved from 1,765 to 1,602
  physical lines and graph helpers from 6,559 to 6,722. Six new unittest
  methods moved full discovery from 1,847 to 1,853. The source diff SHA-256 is
  `da20f913c7205a1e0694ce655b91b8dad0b1d43437a6099626881716ded176b0`.
  The helper owner is public/private 9/134, the ten newly dead planning imports
  were removed, retired executable private refs are zero, and the reviewed
  runtime-domain baseline remains 218 without a record move. Model invocation,
  logical/execution task projection, query routing, plan adoption, mutable
  task/state/artifact/ledger work, retrieval/evidence work, and final
  sequencing remain graph-owned. This is ownership relocation, not a behavior
  claim.
- Commit `ae1f599` moved ten lookup answer-slot/support definitions totaling
  342 definition-span lines plus three compiled policy regex bindings from
  `financial_graph_planning.py` into `financial_lookup_recovery.py`. Four
  selected functions are public and six remain owner-private. Fifteen direct
  calls finish graph-external six and owner-local nine, all outside `try`; old
  private definitions and executable source/test refs are zero. Source is
  `+383/-379`, net `+4`; tests are `+1,133/-12`, net `+1,121`; and the whole
  commit is `+1,516/-391`, net `+1,125`. Planning moved from 1,602 to 1,240
  physical lines and lookup recovery from 788 to 1,154. Eight new tests moved
  discovery from 1,853 to 1,861. The source diff SHA-256 is
  `1556379052fd83f517ac559a7ff0e8fb6908ab675032faede3cb94287c56f397`.
  The lookup owner is public/private 15/13, three newly dead planning imports
  were removed, and the reviewed runtime-domain baseline remains 218 without a
  record move. Retrieval/prepared-document pool construction, active result/
  evidence/state mutation, nested-result promotion, calculation/dependency
  orchestration, trace/artifact/ledger work, and final sequencing remain graph-
  owned. This is ownership relocation, not a behavior claim.
- Commit `02d1422` moved private 40-line focus-term, 59-line preferred-section
  subset, and 18-line compression-guidance definitions from
  `financial_graph_evidence.py` into `financial_retrieval_hints.py` as three
  public functions. Their three direct calls remain graph-external and outside
  `try`; the selected subset's active-section helper call is now owner-local.
  Source is `+134/-125`, net `+9`; tests are `+830/-0`; and the whole commit is
  `+964/-125`, net `+839`. Graph evidence moved from 4,579 to 4,461 physical
  lines and retrieval hints from 167 to 294. Five new tests moved full
  discovery from 1,861 to 1,866 and AST-counted test methods from 1,831 to
  1,836. The source diff SHA-256 is
  `d2925a071c1555658c448d0779168e851304e7602431df8da216904dc60959ec`.
  The retrieval-hint owner is public/private 3/9, its graph-state and operation-
  policy dependencies are acyclic, the graph's dead active-section import was
  removed, retired executable private refs are zero, and the runtime-domain
  baseline remains 218. Context construction, model invocation, evidence
  construction/ranking/mutation, mutable state, trace/artifact/ledger work, and
  final sequencing remain graph-owned. This is ownership relocation, not a
  behavior claim.
- Commit `7aba7f2` moved the former static 33-line labeled-numeric parser and
  195-line supported quantitative-impact composer from
  `financial_graph_evidence.py` into `financial_aggregate_projection.py` as an
  owner-private 33-line parser and public 194-line composer. Three composer
  calls remain graph-external and the parser call is owner-local; old private
  definitions and executable source/test refs are zero. Source is `+237/-235`,
  net `+2`; tests are `+1,119/-12`, net `+1,107`; and the whole commit is
  `+1,356/-247`, net `+1,109`. Graph evidence moved from 4,461 to 4,230
  physical lines, calculation from 13,464 to 13,465, aggregate projection from
  3,714 to 3,946, and five new tests moved discovery from 1,866 to 1,871. The
  source diff SHA-256 is
  `7c267108053b986aff1eb6ddae9b6d51514a42ad7749e94b4fa96849c5439972`.
  The aggregate owner is public/private 76/12; the graph's two dead quantitative-
  policy imports were removed and the reviewed runtime-domain baseline remains
  218. Validation/model fallback, evidence combination/selection, mutable
  composition state, trace/artifact/ledger work, and final sequencing remain
  graph-owned. This is ownership relocation, not a behavior claim.
- Commits `4cdbf93` and `6d6ce2a` moved the exact 40-line generic operand-period
  policy seam and 245-line structured-cell selection/scoring seam from
  `financial_graph_helpers.py` into `financial_scope_policies.py` and
  `financial_structured_cells.py`. The destination surface is public five plus
  owner-private one; the 57 selected calls finish external 53/owner-local four.
  Retired graph-private definitions and executable source/test refs are zero.
  Across `9fe1a45..6d6ce2a`, source is `+390/-371`, net `+19`; tests are
  `+2,086/-49`, net `+2,037`; and the whole range is `+2,476/-420`, net
  `+2,056`. Graph helpers moved from 6,722 to 6,429 physical lines, scope policy
  from 168 to 215, structured cells from 73 to 335, and ten new methods moved
  AST-counted/full discovery from 1,871 to 1,881. The range source diff SHA-256
  is `a8d384543529aa1c3ac9b976c0a46cbde23792fb245e2f9993a51d69e51524d7`.
  The scope owner is public/private 3/7 and the structured-cell owner 3/4.
  All selected dependencies are one-way, the graph's dead fiscal-ordinal import
  was removed, and the reviewed runtime-domain baseline remains 218. Candidate/
  evidence construction and adoption, direct structured lookup/value
  projection, reconciliation orchestration, mutable state/evidence, callbacks,
  carriers, trace/artifact/ledger work, and final sequencing remain graph-owned.
  This is ownership relocation, not a behavior claim.
- Commit `ba35519` moved the exact 31/39/46/49/27/36-line candidate report/
  period-scope definitions, 228 old definition-span lines in total, from
  `financial_graph_helpers.py` into `financial_scope_policies.py`. Public
  `candidate_matches_target_report_scope(...)`,
  `candidate_report_scope_binding_bonus(...)`,
  `candidate_matches_operand_target_year(...)`, and
  `candidate_explicit_years(...)` plus owner-private receipt and comparative-
  fallback helpers leave 18 selected calls at graph-external 10/owner-local
  eight. Retired graph-private source/test refs are zero. Source is
  `+257/-253`, net `+4`; tests are `+1,416/-16`, net `+1,400`; and the whole
  commit is `+1,673/-269`, net `+1,404`. Graph helpers moved from 6,429 to
  6,191 physical lines, scope policy from 215 to 457, and six new methods moved
  AST-counted/full discovery from 1,881 to 1,887. The source diff SHA-256 is
  `853f3a95a4ef0bf8aa5e4900b62d04deef48b1dd6fb58278d75a7b550c61dc01`.
  The scope owner is public/private 7/9; the graph's newly dead report-source
  and structured-period-scoring imports were removed, dependency edges remain
  acyclic, and the reviewed runtime-domain baseline remains 218. Validation
  passed focused 6/6, affected eight-module semantic 844/844, import 19/19,
  audit 218, full 1,887/1,887, pycompile/fresh import, DAG/body/full-caller
  parity, retired-ref zero, and diff check. Candidate/evidence construction and
  adoption, broad scoring/reconciliation, mutable state/evidence, callbacks,
  carriers, trace/artifact/ledger work, and final sequencing remain graph-owned.
  This is ownership relocation, not a behavior claim.
- Commit `3ca0144` moved the exact 25/15/20/23/12/33-line candidate required-
  surface, numeric-signal, descriptor-row, segment-surface, segment-match, and
  segment-bonus definitions, 128 old definition-span lines in total, from
  `financial_graph_helpers.py` into `financial_surface_contracts.py`. Public
  `candidate_has_required_surface_contract(...)`,
  `candidate_has_numeric_value_signal(...)`, `candidate_is_descriptor_row(...)`,
  `candidate_matches_segment_binding(...)`, and
  `candidate_segment_binding_bonus(...)` plus owner-private segment-surface
  assembly leave 17 selected calls at graph/reconciliation-external 15 and
  owner-local two. Retired graph-private source/test refs are zero. Source is
  `+162/-158`, net `+4`; tests are `+781/-7`, net `+774`; and the whole commit
  is `+943/-165`, net `+778`. Graph helpers moved from 6,191 to 6,056 physical
  lines, reconciliation from 1,467 to 1,466, surface contracts from 69 to 209,
  and six new methods moved AST-counted/full discovery from 1,887 to 1,893.
  The source diff SHA-256 is
  `cdd2ced140b9add6bd549e839514038dacede28700ebd25854b7fb6c3e9e1702`.
  The surface owner is public/private 5/7, selected dependencies remain one-way,
  and the reviewed runtime-domain baseline remains 218. Validation passed
  focused 6/6, owner modules 41/41, affected nine-module semantic 851/851,
  import 19/19, audit 218, full 1,893/1,893, pycompile/fresh import,
  DAG/body/full-caller parity, retired-ref zero, and diff check. Candidate/
  evidence construction and adoption, direct/ratio acceptance, broad scoring/
  reconciliation, mutable state/evidence, callbacks, carriers, trace/artifact/
  ledger work, and final sequencing remain graph-owned. This is ownership
  relocation, not a behavior claim.
- Commit `a904f28` moved the exact 12/26/38/40-line candidate local aggregate-
  context, consolidation-scope, binding-policy shape, and selected-unit-family
  definitions, 116 old definition-span lines in total, from
  `financial_graph_helpers.py` into `financial_surface_contracts.py` as public
  `candidate_local_aggregate_context(...)`,
  `candidate_consolidation_scope(...)`,
  `binding_policy_allows_candidate_shape(...)`, and
  `candidate_selected_unit_family(...)`. Their eight direct calls remain graph-
  external 3/2/2/1 and owner-local zero, all outside `try`; retired private
  source/test refs are zero. Source is `+139/-134`, net `+5`; tests are
  `+1,116/-9`, net `+1,107`; and the whole commit is `+1,255/-143`, net
  `+1,112`. Graph helpers moved from 6,056 to 5,936 physical lines, surface
  contracts from 209 to 334, and six new methods moved full discovery from
  1,893 to 1,899. The source diff SHA-256 is
  `0e62e924b473c256d505164160b8e00419a8be0c022c7b3d036da0465bafcae7`.
  The surface owner is public/private 9/7 and graph helpers 9/112; the new
  operation-policy edge is one-way, selected dependencies remain acyclic, and
  the reviewed runtime-domain baseline remains 218. Validation passed focused
  6/6, owner modules 47/47, affected nine-module semantic 857/857, import 19/19,
  audit 218, full 1,899/1,899, pycompile/fresh import, DAG/body/full-caller
  parity over 121 retained graph functions, retired-ref zero, and diff check.
  Candidate/evidence construction and adoption, direct/ratio acceptance, broad
  scoring/reconciliation, mutable state/evidence, callbacks, carriers,
  trace/artifact/ledger work, and final sequencing remain graph-owned. This is
  ownership relocation, not a behavior claim.
- Commit `d1305f8` moved the exact 7-line segment-local binding and 15-line
  segment-metric composition definitions from `financial_graph_helpers.py` to
  public `candidate_has_segment_local_binding(...)` and
  `candidate_supports_segment_metric_combo(...)` in
  `financial_row_surfaces.py`. Calls are external 2/local 1 and all remain
  direct `ast.Name` calls outside `try`; retired private source/test refs are
  zero. Source is `+31/-29`, tests `+606/-7`, and the whole commit `+637/-36`.
  Graph helpers moved from 5,936 to 5,912 lines, row surfaces from 312 to 338,
  and four tests moved discovery from 1,899 to 1,903. Focused 4/4, owner 51/51,
  semantic 861/861, import 19/19, audit 218, and full 1,903/1,903 passed in the
  project `.venv`, along with pycompile/fresh import and AST/caller/DAG parity.
  Aggregate row/value role-stage inference, direct/ratio acceptance, matching/
  scoring/reconciliation, state/evidence, and final sequencing remain graph-
  owned. This is ownership relocation, not a behavior claim.
- Commit `80a37f8` moved the exact 10-line aggregate-like row-stage and two-line
  row-role definitions from `financial_graph_helpers.py` to public
  `aggregate_like_row_stage(...)` and `aggregate_like_row_role(...)` in
  `financial_row_surfaces.py`. Stage calls finish graph-external three/owner-
  local one and role calls graph-external two, for external five/local one; all
  are direct `ast.Name` calls outside `try`. Retired private source/test refs are
  zero. Source is `+27/-22`, tests `+584/-5`, and the whole commit `+611/-27`.
  Graph helpers moved from 5,912 to 5,898 lines, row surfaces from 338 to 357,
  and four tests moved discovery from 1,903 to 1,907. The source diff SHA-256 is
  `075e776a65b50061c7751b2340b7eb256ad8d8f0cfbc85887a3f42867f2ae55a`.
  Focused 4/4, owner 55/55, semantic 865/865, import 19/19, audit 218, and full
  1,907/1,907 passed in the project `.venv`, along with pycompile/fresh import,
  selected body 2/2, retained graph 117, full caller/DAG parity, and diff check.
  Candidate value-role/stage interpretation, direct/ratio acceptance, matching/
  scoring/reconciliation, state/evidence, and final sequencing remain graph-
  owned. This is ownership relocation, not a behavior claim.
- Commit `2eec794` moved the exact 5/14/7/5-line lookup canonical-row,
  canonical-statement, query-surface, and surface-match definitions from
  `financial_graph_helpers.py` to public
  `lookup_prefers_canonical_statement_rows(...)`,
  `lookup_canonical_statement_preferences(...)`,
  `lookup_query_surface_preferences(...)`, and
  `operand_lookup_surface_match(...)` in
  `financial_operand_resolution.py`. Calls finish graph-external 7/5/3/1 and
  owner-local 0/0/1/0, for external 16/local one; all are direct `ast.Name`
  calls outside `try`. Retired private source/test refs are zero. Source is
  `+60/-57`, net `+3`; tests are `+1,673/-20`, net `+1,653`; and the whole
  commit is `+1,733/-77`, net `+1,656`. Graph helpers moved from 5,898 to 5,861
  lines, operand resolution from 3,603 to 3,643, graph-helper tests from 9,323
  to 10,976, and four tests moved discovery from 1,907 to 1,911. The source
  diff SHA-256 is
  `262d0304e03d9574acd45cb97e1c8b4ec4c32164f766a60c057c7bb526cc8416`.
  Focused 4/4, owner 127/127, affected ten-module semantic 938/938, import
  19/19, audit 218, and full 1,911/1,911 passed in the project `.venv`, along
  with pycompile/fresh import/public identity, selected body 4/4, retained
  graph 113, full caller/DAG parity, retired-ref zero, and diff check. Lookup
  task construction, candidate admission/scoring, retry assembly, state/
  evidence, and final sequencing remain graph-owned. This is ownership
  relocation, not a behavior claim.
- Commit `8cdcc94` moved the exact 26-line direct logical candidate-signature
  and 22-line direct family candidate-signature definitions from
  `financial_graph_helpers.py` to public
  `candidate_direct_logical_signature(...)` and
  `candidate_direct_family_signature(...)` in
  `financial_operand_resolution.py`. Their two calls remain graph-external and
  owner-local zero; the shared block-signature calls finish external four/local
  three. Source is `+56/-55`, net `+1`; tests are `+1,428/-10`, net `+1,418`;
  and the whole commit is `+1,484/-65`, net `+1,419`. Graph helpers moved from
  5,861 to 5,810 lines, operand resolution from 3,643 to 3,695, and four methods
  moved discovery from 1,911 to 1,915. The source diff SHA-256 is
  `d22527be5fbcc25f8ab381134312fcb030f74d52c2e9c6b9a682060f0cbed68e`.
  Focused 4/4, owner 131/131, affected semantic 942/942, import 19/19, audit
  218, and full 1,915/1,915 passed with pycompile/fresh import/public identity,
  selected-body 2/2, retained graph 111/111, full caller/DAG parity, retired-ref
  zero, and diff check. Selected-cell construction, direct acceptance, entry
  collapse and sibling/canonical/semantic/score policy remain graph-owned. This
  is ownership relocation, not a behavior or benchmark claim.
- Commit `a530033` moved the exact 30-line sibling-surface hit-count definition
  from `financial_graph_helpers.py` to public
  `candidate_sibling_surface_hit_count(...)` in
  `financial_row_surfaces.py`. Its three direct calls remain graph-external in
  sorted-key, top-hit recomputation, and positive-top filtering; owner-local
  calls remain zero. Source is `+36/-36`, net zero; tests are `+968/-9`, net
  `+959`; and the whole commit is `+1,004/-45`, net `+959`. Graph helpers moved
  from 5,810 to 5,778 lines, row surfaces from 357 to 389, graph-helper tests
  from 12,394 to 13,353, and four methods moved discovery from 1,915 to 1,919.
  The source diff SHA-256 is
  `0c369d873a91d678a19d9a766a41152afaa8c97aca83cd7270ca2d81ea9d7466`.
  Focused 4/4, owner 67/67, affected semantic 946/946, import 19/19, audit 218,
  and full 1,919/1,919 passed with pycompile/fresh import/public identity,
  selected-body 1/1, retained graph 110/110, full caller/DAG parity, retired-ref
  zero, and diff check. Sibling-list preparation, direct-entry collapse,
  sorted/top/filter ranking, canonical/semantic/score policy, and reconciliation
  adoption remain graph-owned. This is ownership relocation, not a behavior or
  benchmark claim.
- Commit `8e4dca4` moved the exact 6-line query-to-metric mention and 14-line
  query-to-operand component-match definitions from
  `financial_graph_helpers.py` to public `query_mentions_metric(...)` and
  `query_component_match_count(...)` in `financial_retrieval_hints.py`. Their
  four calls remain graph-external in strong-metric filtering, target-component
  assignment, target mention admission, and the task-loop weak-match guard;
  owner-local calls remain zero. Source is `+30/-28`, net `+2`; tests are
  `+1,321/-8`, net `+1,313`; and the whole commit is `+1,351/-36`, net
  `+1,315`. Graph helpers moved from 5,778 to 5,756 lines, retrieval hints from
  294 to 318, graph-helper tests from 13,353 to 14,666, and four methods moved
  discovery from 1,919 to 1,923. The source diff SHA-256 is
  `5199849efa1388dfdd30178ba0bbe14f198e3c46f4e365647cc031070cab0fbd`.
  Focused 4/4, owner 75/75, affected semantic 955/955, import 19/19, audit 218,
  and full 1,923/1,923 passed with pycompile/fresh import/public identity,
  selected-body 2/2, retained graph 108/108, full caller/DAG parity, retired-ref
  zero, and diff check. Ontology lookup, operation/metric admission, task/query
  construction, and plan adoption remain graph-owned. This is ownership
  relocation, not a behavior or benchmark claim.
- Commit `55bc286` moved the exact 11-line query period-focus and 25-line
  operand-role period-focus definitions from `financial_graph_helpers.py` to
  public `query_period_focus(...)` and
  `task_period_focus_from_operands(...)` in `financial_scope_policies.py`.
  Their six calls remain graph-external across hybrid, concept, heuristic, and
  metric-task constraint builders; owner-local calls remain zero. Source is
  `+48/-46`, net `+2`; tests are `+1,238/-18`, net `+1,220`; and the whole
  commit is `+1,286/-64`, net `+1,222`. Graph helpers moved from 5,756 to
  5,718 lines, scope policy from 457 to 497, graph-helper tests from 14,666 to
  15,886, semantic-plan tests remained 2,949, and four methods moved discovery
  from 1,923 to 1,927. The source diff SHA-256 is
  `aa560ff1fd01dca72fe55120b8dc8fbd67e95d27d6f3ebc87e863012a7054da9`.
  Focused 4/4, owner 74/74, affected semantic 1,034/1,034, import 19/19,
  audit 218, and full 1,927/1,927 passed with pycompile/fresh import/public
  identity, selected-body 2/2, retained graph 106/106, full caller/DAG parity,
  retired executable private refs zero, and diff check. Consolidation/default
  resolution, operation inference, operand/task/query construction, caller
  policy, ranking/admission, and plan/state adoption remain graph-owned. This
  is ownership relocation, not a behavior or benchmark claim.
- Current physical sizes are: calculation graph 13,467 lines, calculation
  execution 1,074, main graph 938,
  graph evidence 4,229, retrieval hints 318,
  graph helpers 5,718, scope policy 497, structured cells 335, surface contracts
  334, row surfaces 389,
  planning 1,240, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 625, text surface 642, operand resolution 3,695,
  dependency projection 3,419, reconciliation 1,466, reconciliation candidates
  532, aggregate projection 3,946, runtime trace 1,412, lookup recovery 1,154,
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
| Retrieval | `financial_retrieval_pipeline.py`; `financial_retrieval_hints.py` owns statement/section hints, focus-term, preferred-section subset, compression-guidance, and query-to-prepared-metric/operand matching projection, while graph evidence owns structure expansion, context/evidence construction, ranking, model invocation, and state adoption |
| Calculation orchestration | `financial_graph_calculation.py`; reads graph state, prepares inputs, places owner calls, and projects state/task/artifact results |
| Semantic planning normalization | `financial_graph_helpers.py`; state-free scope normalization, plan-shape predicates, segment-label projection, planner-task validation, and narrative-task policy projection, excluding model invocation and plan/state adoption |
| Scope and structured-cell policy | `financial_scope_policies.py` owns report/consolidation scope, public query/task and operand target-year/period-focus projection, and candidate report/year matching and binding bonuses; `financial_structured_cells.py` owns fiscal rank/period text, ordinary/aggregate selection, public scoring, and owner-private operand affinity |
| Candidate and row surface contracts | `financial_surface_contracts.py` owns operand needles/segment labels, positive/negative term matching, candidate required/numeric/descriptor projection, segment-surface matching/bonuses, local aggregate context, consolidation scope, binding-shape admission, and selected-unit-family projection; `financial_row_surfaces.py` owns row text matching/parsing, aggregate-like row stage/role projection, segment-local binding, segment-metric composition, and sibling-surface hit counting |
| Operand policy and resolution | `financial_operand_resolution.py`, including lookup-hint projection/matching, direct candidate logical/family signature projection, ratio sign policy, evidence-local unit/period coercion, dependency-task KRW consistency, table-metadata/raw-unit repair, and growth alignment/period conflict |
| Dependency and execution | `financial_dependency_projection.py`, including dependency input matching/binding, sibling-output synthesis preference, sibling lookup-surface preparation, and resolved reconciliation projection, plus `financial_calculation_execution.py`, including base/runtime deterministic operation planning, ontology planning, plan guarding, execution, and value freshness |
| Lookup recovery | `financial_lookup_recovery.py`, including lookup magnitude/unit recovery, selected-evidence consistency/refinement, successful-row alignment/replacement, direct structured lookup-row/value projection, active-task matching, prose answer-slot synthesis, and supporting-document projection over already supplied evidence |
| Structured reconciliation candidates | `financial_reconciliation_candidates.py`; state-free statement/unit/period/score/identity/row/match, candidate-ID, and structured period-pair projection over already prepared mappings |
| Calculation rendering | `financial_graph_calculation_rendering.py`, including ratio unit/query/result projection and scalar/time-series display helpers |
| Answer and numeric surfaces | `financial_answer_slots.py`, `financial_answer_projection.py`, `financial_numeric_surface.py`, and `financial_text_surface.py`, including period/material, nested-row traversal/scoring/selected-result promotion, ratio-readiness, narrative validation, numeric/scale predicates, shared sentence/token surfaces, query-focus marker projection, and source-visible term preservation |
| Aggregate projection | `financial_aggregate_projection.py`, including aggregate calculation/public projection, subtask upsert/rank, selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, nested-result replacement, arithmetic subtask-surface synchronization, duplicate growth-prior recovery, final evidence/provenance projection, own-evidence lookup-unit alignment, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering and trace inspection, result support/reuse predicates, prepared growth/ratio material inspection, final-answer evidence filtering/operand append/surface-operand projection, growth-answer completion/sanitization, and deterministic quantitative-impact parsing/composition |
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
| Latest focused owner checkpoint | PASS, query/task period-focus ownership 4 / 4; owner module 74 / 74 |
| Latest semantic regression set | PASS, affected eleven-module set 1,034 / 1,034 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 218 reviewed records |
| Full unittest discovery | PASS, 1,927 / 1,927 |
| Benchmark refresh after latest query/task period-focus ownership change | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_graph_helpers`,
`tests.test_semantic_numeric_plan`,
`tests.test_financial_operand_resolution`,
`tests.test_financial_surface_contracts`,
`tests.test_financial_dependency_projection`,
`tests.test_financial_reconciliation_candidates`,
`tests.test_lookup_recovery_policy`, `tests.test_operation_contracts`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`, and
`tests.test_financial_agent_run_projection`. `tests.test_import_side_effects`
passed separately at 19 / 19.

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
| Aggregate repair and precedence | Partially advanced through aggregate calculation/public projection, subtask upsert/rank, nested traversal/scoring/selected-result promotion, nested-result replacement, arithmetic subtask-surface synchronization, period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, prepared growth-numeric rendering and trace inspection, result support/reuse, prepared material inspection, bounded row/gap/lookup-answer ownership, final-answer evidence/provenance/surface-operand projection, own-evidence lookup-unit alignment, growth-answer completion/sanitization, and deterministic quantitative-impact parsing/composition; peer-source alignment, broader rebuild and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, lookup magnitude and hint projection/matching, same-block unit/table repair, direct structured lookup-row/value projection, lookup answer-slot/support projection, dependency input matching/binding, deterministic runtime/ontology planning, generic operand-period and query/task period-focus policy, structured-cell selection/scoring, candidate report/period-scope policy, candidate surface-contract/segment binding, candidate metadata-policy projection, segment-local/segment-metric row-surface ownership, aggregate-like row stage/role projection, direct candidate logical/family signature projection, sibling-surface hit counting, and query-to-metric/operand matching; graph-state lookup, direct/ratio acceptance, broader evidence orchestration, scoring/reconciliation, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Minimally advanced through bounded read-only reconciliation artifact-reference projection; artifact mutation and whole-ledger synchronization require separate contracts |
| Private API mesh and test co-location | Partially advanced as public contracts, semantic-planner normalization/validation, narrative-task policy, lookup answer-slot/support, read-only retrieval-hint projection, and quantitative-impact projection moved; broader evidence and orchestration seams remain |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The characterize-only inventory selects exactly one production follow-on. Move
the exact adjacent current definitions from `financial_graph_helpers.py` to
public functions in the existing `financial_row_surfaces.py` owner:

- `_candidate_value_role(candidate: Dict[str, Any]) -> str` becomes
  `candidate_value_role(...)`; its definition span is 16 lines;
- `_candidate_aggregation_stage(candidate: Dict[str, Any]) -> str` becomes
  `candidate_aggregation_stage(...)`; its definition span is 18 lines.

No production source or test has moved for this pair at this characterization
checkpoint. These functions project role/stage labels from already supplied
candidate metadata and delegate only their row-label fallback to the public
`aggregate_like_row_role(...)` and `aggregate_like_row_stage(...)` functions
already owned by row surfaces. They do not decide candidate admission, match
strength, semantic priority, score, direct/ratio acceptance, evidence adoption,
or graph state. The row owner already imports `Any`, `Dict`, and normalization,
and already owns the aggregate-like row projections. Graph already reaches it
and the owner does not reach graph. Current top-level counts are graph helpers
public/private 9/97 and row surfaces 5/15; projected counts are 9/95 and 7/15.

`candidate_value_role(...)` must preserve this exact lazy precedence:

- shallow-copy `candidate.get("metadata") or {}` with `dict(...)` before any
  field projection;
- normalize the stringified explicit `value_role` and return it immediately
  when truthy;
- otherwise normalize `aggregate_role`; map `adjustment` to `adjustment` and
  `direct_total`, `subtotal`, or `final_total` to `aggregate`;
- only after those paths miss, choose `row_label` before `semantic_label` with
  the existing raw `or` semantics, stringify it, call
  `aggregate_like_row_role(...)`, and return its result only when it is exactly
  `aggregate`; otherwise return `detail`.

`candidate_aggregation_stage(...)` must use the same metadata-copy, explicit-
field, aggregate-role, and row-label/semantic-label ordering. Its aggregate-role
map is `direct_total -> direct`, `subtotal -> subtotal`, and
`final_total -> final`. Its fallback returns the exact
`aggregate_like_row_stage(...)` result when that result is not `none`, otherwise
`none`.

Preserve raw mapping access, `or` truth-value semantics, immediate string
coercion at the current sites, normalization, exact case-sensitive comparisons,
shallow-copy/nested identity, input immutability, and uncaught mapping,
truth-value, stringification, normalization, hashing/membership, and row-owner
errors. No catch, wrapper, graph alias, callback, reason, flag, trace, or new
fallback is allowed.

The pair currently has 22 direct `ast.Name` calls, 11 per function, all in graph
helpers, with one positional `candidate` argument, no keywords, and caller
`try` depth zero. The callers are `_direct_candidate_semantic_priority(...)`,
`_candidate_is_direct_grounding_candidate(...)`,
`_candidate_satisfies_direct_acceptance_contract(...)`,
`_candidate_satisfies_ratio_component_acceptance_contract(...)`,
`_candidate_matches_operand(...)`, `_candidate_direct_match_strength(...)`, and
`_score_operand_candidate(...)`. Calls finish graph-external 22/owner-local
zero. Both selected spans contain zero of the 218 reviewed runtime-domain
records. Existing tests have a large private-name patch/import mesh, so every
executable direct call and patch target must move to the public row-owner names
without preserving a graph compatibility alias.

Caller policy remains graph-owned and unchanged. Direct semantic priority reads
role then stage before match strength. Direct grounding and both acceptance
contracts read role then stage before binding-shape and later period/unit/
section policy. Candidate matching and direct strength retain their current
short-circuit placement, including paths that do not call one or both
projections. Scoring reads role then stage only after numeric-cell/direct-match
preparation and before stage/role preference bonuses. Exceptions stop the rest
of the current caller; moving or eagerly precomputing projections is rejected.

Moving any caller body, candidate metadata construction, row-label inference,
binding policy, direct/ratio acceptance, candidate matching, match-strength or
semantic-priority calculation, scoring/ranking, candidate/evidence adoption,
state/artifact/ledger mutation, or final sequencing is rejected. A new module
or compatibility bridge would add surface without resolving a boundary.

Before production movement, add exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_candidate_value_role_pins_precedence_laziness_identity_and_exceptions`;
- `test_current_source_candidate_aggregation_stage_pins_precedence_laziness_identity_and_exceptions`;
- `test_current_source_candidate_value_stage_bindings_pin_defs_calls_dag_and_baseline`;
- `test_current_source_candidate_value_stage_callers_pin_order_short_circuits_and_stops`.

They must pin the exact 16/18-line spans and signatures, metadata shallow copy,
field-get/string/normalization counts, explicit and aggregate-role precedence,
row-label-before-semantic fallback, exact mappings/defaults, nested identity,
input immutability, uncaught errors, all 22 call expressions and contexts,
direct-name/try-depth placement, per-caller order and short-circuit/exception
stops, current/projected function counts, import DAG, and zero selected-body
runtime-domain records. Projected post-move gates are focused 4/4, graph-helper/
row-surface owner 78/78, affected semantic set 1,038/1,038, import-side-effects
19/19, audit 218, and full discovery 1,931/1,931, plus pycompile/fresh import and
public identity 2/2, selected-body parity 2/2, all 104 retained graph functions,
full caller/DAG parity, retired executable graph-private refs zero, and
`git diff --check`. The projected semantic count is the current affected
1,034-test set plus four new CURRENT-SOURCE methods; it is a projection to be
verified, not an executed result.

Keep admission, matching, match strength, semantic priority, scoring/ranking,
candidate/evidence construction and adoption, graph state, model invocation,
artifact/ledger mutation, and final sequencing graph-owned. The inventory and
future relocation establish no behavior, accuracy, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim. Static AST/DAG and
selected-body baseline plus two existing role/stage caller probes passed for
this inventory; benchmark refresh and remote CI were **NOT RUN**.

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
