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
| What just changed? | `c837e31` moved the exact 17-line contextual-aggregate preference predicate to public surface-contract ownership without changing its three caller branches |
| What passed? | Focused 4/4, owner module 122/122, affected eleven-module semantic set 1,082/1,082, import-side-effect 19/19, runtime audit 217, full unittest 1,975/1,975 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest contextual-aggregate-preference ownership change |
| What is next? | Add four CURRENT-SOURCE contracts, then move only the exact 9-line balance-sheet aggregate-operand predicate to surface-contract ownership |

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
- Commit `9092f5e` moved the exact 16-line candidate value-role and 18-line
  aggregation-stage definitions from `financial_graph_helpers.py` to public
  `candidate_value_role(...)` and `candidate_aggregation_stage(...)` in
  `financial_row_surfaces.py`. Their 22 direct calls remain graph-external,
  11 per function across semantic priority, direct grounding/acceptance, ratio
  acceptance, matching, direct strength, and scoring; owner-local calls remain
  zero. Source is `+59/-57`, net `+2`; tests are `+1,167/-69`, net `+1,098`;
  and the whole commit is `+1,226/-126`, net `+1,100`. Graph helpers moved from
  5,718 to 5,682 lines, row surfaces from 389 to 427, graph-helper tests from
  15,886 to 16,984, and four methods moved discovery from 1,927 to 1,931. The
  source diff SHA-256 is
  `5bde3c6eb94508a4afab190cd3db4d866b265ff6f0103a028711e41c2159d8b8`.
  Focused 4/4, owner 78/78, affected semantic 1,038/1,038, import 19/19, audit
  218, and full 1,931/1,931 passed with pycompile/fresh import/public identity,
  selected-body 2/2, retained graph 104/104 and retained row 20/20, all 22
  caller expressions, full DAG parity, retired executable graph-private refs
  zero, and diff check. Direct/ratio acceptance, matching, match strength,
  semantic priority, scoring/ranking, candidate/evidence adoption, and graph/
  artifact/ledger state remain graph-owned. This is ownership relocation, not
  a behavior or benchmark claim.
- Commit `78e3508` moved the exact 15-line candidate operand-context and 19-line
  table-row structured-sibling definitions from `financial_graph_helpers.py`
  to public `candidate_has_operand_context_surface(...)` and
  `table_row_has_matching_structured_sibling(...)` in
  `financial_row_surfaces.py`. Their two direct calls remain graph-external in
  direct-match strength and direct grounding; owner-local calls remain zero.
  Source is `+49/-41`, net `+8`; tests are `+986/-17`, net `+969`; and the
  whole commit is `+1,035/-58`, net `+977`. Graph helpers moved from 5,682 to
  5,646 lines, row surfaces from 427 to 471, graph-helper tests from 16,984 to
  17,953, and four methods moved discovery from 1,931 to 1,935. The source diff
  SHA-256 is
  `228c458d7909609f45806214d1d0dcb4f0a0969648582552ba03b93d1e0b1966`.
  Focused 4/4, owner 82/82, affected semantic 1,042/1,042, import 19/19, audit
  218, and full 1,935/1,935 passed with pycompile/fresh import/public identity,
  selected-body 2/2, retained graph 102/102 and retained row 22/22, both caller
  expressions, full DAG parity, retired executable graph-private refs zero,
  and diff check. Direct grounding/acceptance, matching, match strength,
  scoring/ranking, candidate/evidence adoption, and graph/artifact/ledger state
  remain graph-owned. This is ownership relocation, not a behavior or benchmark
  claim.
- Commit `0bfa1f0` moved the exact 21-line candidate selected-cell definition
  from `financial_graph_helpers.py` to public
  `candidate_selected_cell_for_operand(...)` in
  `financial_structured_cells.py`. Its sole direct call remains graph-external
  in deterministic reconciliation after period-focus resolution and before
  direct acceptance; the seven direct `select_structured_cell(...)` calls
  finish external six/owner-local one. Source is `+30/-26`, net `+4`; tests are
  `+1,266/-27`, net `+1,239`; and the whole commit is `+1,296/-53`, net
  `+1,243`. Graph helpers moved from 5,646 to 5,623 lines, structured cells from
  335 to 362, graph-helper tests from 17,953 to 19,190, operation contracts from
  11,558 to 11,560, and four methods moved discovery from 1,935 to 1,939. The
  source diff SHA-256 is
  `eba52c11252de00d12fa808276b8c7b80b7d8dccbd7bbb828696fe5b2c37494f`.
  Focused 4/4, owner 86/86, affected semantic 1,046/1,046, import 19/19, audit
  218, and full 1,939/1,939 passed with pycompile/fresh import/public identity,
  selected-body 1/1, retained graph 101/101 and retained structured owner 7/7,
  sole-caller and full DAG parity, retired executable graph-private refs zero,
  and diff check. Direct acceptance, signatures, matching/scoring, candidate/
  evidence adoption, retry assembly, and graph/artifact/ledger state remain
  graph-owned. This is ownership relocation, not a behavior or benchmark claim.
- Commit `2b0e9c1` moved the exact 56-line scoped surface-affinity definition
  from `financial_graph_helpers.py` to public
  `scoped_surface_affinity_priority(...)` in
  `financial_surface_contracts.py`. Its two direct calls remain owner-external
  in evidence prioritization and coherent ratio-context scoring, with the same
  caller gates, inputs, weights, order, and exception stops. The selected
  operand-segment dependency is now owner-local. Source is `+67/-64`, net
  `+3`; tests are `+851/-15`, net `+836`; and the whole commit is `+918/-79`,
  net `+839`. Graph helpers moved from 5,623 to 5,564 lines, surface contracts
  from 334 to 396, graph-helper tests from 19,190 to 20,026, and four methods
  moved discovery from 1,939 to 1,943. The source diff SHA-256 is
  `a9d2c5aad44530e9cbcc9d6c27e9644109251adfcc3f17ae705c6936f2015377`.
  Focused 4/4, owner 90/90, affected semantic 1,050/1,050, import 19/19, audit
  218, and full 1,943/1,943 passed with pycompile/fresh import/public identity
  2/2, selected-body 1/1, retained graph 100/100 and retained surface owner
  16/16, both caller expressions and bodies, full 48-module DAG parity,
  retired executable graph-private refs zero, and diff check. Eligibility,
  schema scoring, evidence/operand-row construction, direct/ratio acceptance,
  broader ranking, result adoption, and graph/artifact/ledger state remain
  caller- or graph-owned. This is ownership relocation, not a behavior or
  benchmark claim.
- Commit `7ec0cc3` moved the exact 30-line candidate period/table coherence
  definition from `financial_graph_helpers.py` to public
  `candidate_period_table_coherence_bonus(...)` in
  `financial_scope_policies.py`. Its sole direct `AugAssign` call remains
  owner-external in `_score_operand_candidate(...)` at caller `try` depth zero,
  after source/metadata-period scoring and before report-scope/final-table
  scoring. Source is `+34/-34`, net `0`; tests are `+788/-30`, net `+758`; and
  the whole commit is `+822/-64`, net `+758`. Graph helpers moved from 5,564
  to 5,532 lines, scope policy from 497 to 529, graph-helper tests from 20,026
  to 20,784, and four methods moved discovery from 1,943 to 1,947. The source
  diff SHA-256 is
  `33d6fdd3e6216ab2e963fe6480484d7d7b59ee5d333c58b678479d0ed90c139d`.
  Focused 4/4, owner 94/94, affected semantic 1,054/1,054, import 19/19, audit
  218, and full 1,947/1,947 passed with pycompile/fresh import/public identity
  1/1, selected-body 1/1, retained graph 99/99 and retained scope owner 18/18,
  sole-caller/body and full 48-module DAG parity, retired executable graph-
  private refs zero, and diff check. Candidate/year extraction, target-year
  policy, source/report/other score work, matching/acceptance, ranking/adoption,
  and graph/artifact/ledger state remain outside. This is ownership relocation,
  not a behavior or benchmark claim.
- Commit `23f08b2` moved the exact 53-line candidate location/entity subject-
  score definition from `financial_graph_helpers.py` to public
  `candidate_location_entity_subject_score(...)` in
  `financial_operand_resolution.py`. Its sole direct `AugAssign` remains owner-
  external/local 1/0 in `_score_operand_candidate(...)` after numeric-signal
  scoring and before descriptor/statement/scope/period/source/table work.
  Source is `+57/-56`, net `+1`; tests are `+890/-23`, net `+867`; and the
  whole commit is `+947/-79`, net `+868`. Graph helpers moved from 5,532 to
  5,478 lines, operand resolution from 3,695 to 3,750, graph-helper tests from
  20,784 to 21,651, and four methods moved discovery from 1,947 to 1,951. The
  source diff SHA-256 is
  `4d1144206071e440dbb5815904ab2f30cc5d955c8938fb767ea3673a6e31f105`.
  Focused 4/4, owner 98/98, affected semantic 1,058/1,058, import 19/19, audit
  218, and full 1,951/1,951 passed with pycompile/fresh import/public identity
  1/1, selected-body 1/1, retained graph 98/98 and retained operand owner
  80/80, sole-caller/body and full 48-module DAG parity, retired executable
  graph-private refs zero, and diff check. Operand policy, candidate/evidence
  construction, other scoring, matching/acceptance/ranking, adoption, retrieval,
  and graph/artifact/ledger state remain outside. This is ownership relocation,
  not a behavior or benchmark claim.
- Commit `e04a7bf` moved the exact 7-line delta-like row-label classifier from
  `financial_graph_helpers.py` to public `is_delta_like_row_label(...)` in
  `financial_row_surfaces.py` with the selected body unchanged. Its three direct
  calls finish owner-external/local 3/0: two in direct grounding and one in
  operand scoring. Source is `+14/-12`, net `+2`; tests are `+811/-25`, net
  `+786`; and the whole commit is `+825/-37`, net `+788`. Graph helpers moved
  from 5,478 to 5,470 lines, row surfaces from 471 to 481, graph-helper tests
  from 21,651 to 22,437, and four methods moved discovery from 1,951 to 1,955.
  The source diff SHA-256 is
  `b3ceafde06df105a8d62b77dae1e8d6f61711ed04e2132e9f90213012d4c7e0c`.
  Focused 4/4, owner 102/102, affected semantic 1,062/1,062, import 19/19,
  audit 218, and full 1,955/1,955 passed with pycompile/fresh import/public
  identity 1/1, selected-body 1/1, retained graph 97/97 and retained row owner
  24/24, all three caller expressions and two caller bodies, full 48-module DAG
  parity, retired executable graph-private refs zero, and diff check. Period-
  focus policy, candidate/evidence construction, broader scoring, matching/
  acceptance/ranking, adoption, retrieval, and graph/artifact/ledger state remain
  outside. This is ownership relocation, not a behavior or benchmark claim.
- Commit `c4558b7` moved the exact 7-line preference-bonus definition from
  `financial_graph_helpers.py` to public `preference_bonus(...)` in
  `financial_operand_resolution.py` with the selected body unchanged. Its two
  direct scorer `AugAssign` calls finish owner-external/local 2/0 and remain
  consecutive. Source is `+12/-11`, net `+1`; tests are `+734/-21`, net `+713`;
  and the whole commit is `+746/-32`, net `+714`. Graph helpers moved from
  5,470 to 5,462 lines, operand resolution from 3,750 to 3,759, graph-helper
  tests from 22,437 to 23,150, and four methods moved discovery from 1,955 to
  1,959. The source diff SHA-256 is
  `319be70af91d64a48d09ec63a1524fe3f5b4834b32238a32a1f1e967e1ec69e5`.
  Focused 4/4, owner 106/106, affected semantic 1,066/1,066, import 19/19,
  audit 218, and full 1,959/1,959 passed with pycompile/fresh import/public
  identity 1/1, selected-body 1/1, retained graph 96/96 and retained operand
  owner 81/81, both caller expressions and the sole caller body, full 48-module
  DAG parity, retired executable graph-private refs zero, and diff check.
  Caller collection preparation, role/stage derivation, other scoring,
  matching/acceptance/ranking, adoption, retrieval, and graph/artifact/ledger
  state remain outside. This is ownership relocation, not a behavior or
  benchmark claim.
- Commit `0dc278e` moved the exact 10-line column-candidate-label definition
  from `financial_graph_helpers.py` to public `column_candidate_label(...)` in
  `financial_row_surfaces.py` with the selected body unchanged. Its sole direct
  call finishes owner-external/local 1/0 in the table-column reconciliation
  candidate builder. Source is `+14/-14`, net zero; the graph-helper test is
  `+688/-22`, net `+666`; the reviewed baseline is `+3/-3`; and the whole
  commit is `+705/-39`, net `+666`. Graph helpers moved from 5,462 to 5,450
  lines, row surfaces from 481 to 493, graph-helper tests from 23,150 to 23,816,
  and four methods moved discovery from 1,959 to 1,963. The source diff
  SHA-256 is
  `053f3195dce934a7d005e8d61b57355c2639b215834eb29f741ed6592d86a9f7`.
  Focused 4/4, owner 110/110, affected semantic 1,070/1,070, import 19/19,
  audit 218, and full 1,963/1,963 passed with pycompile/fresh import/public
  identity 1/1, selected-body parity 1/1, all 95 retained graph functions after
  target-call normalization, all 25 retained row-owner functions, sole caller/
  body, full 48-module/203-edge DAG parity, retired executable graph-private
  refs zero, and diff check. The audit corrected the characterization's stale
  line-derived zero-hit claim: the unchanged year regex is one reviewed record,
  so only that existing record's owner path, fingerprint, and line moved while
  its literal, category, count, and the 218-record total stayed unchanged.
  Row/cell preparation, grouping/candidate construction, matching/scoring/
  acceptance, adoption, retrieval, and graph/artifact/ledger state remain
  outside. This is ownership relocation, not a behavior or benchmark claim.
- Current physical sizes are: calculation graph 13,467 lines, calculation
  execution 1,074, main graph 938,
  graph evidence 4,229, retrieval hints 318,
  graph helpers 5,394, scope policy 539, structured cells 362, surface contracts
  445, row surfaces 493,
  planning 1,240, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 625, text surface 642, operand resolution 3,759,
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
| Scope and structured-cell policy | `financial_scope_policies.py` owns report/consolidation and single-report-scope classification, public query/task and operand target-year/period-focus projection, candidate report/year matching and binding bonuses, and candidate period/table coherence scoring; `financial_structured_cells.py` owns fiscal rank/period text, ordinary/aggregate selection, public scoring, candidate selected-cell preparation, and owner-private operand affinity |
| Candidate and row surface contracts | `financial_surface_contracts.py` owns operand needles/segment labels, positive/negative term matching, candidate concept-conflict, contextual-aggregate preference, candidate required/numeric/descriptor projection, segment-surface matching/bonuses, local aggregate context, consolidation scope, binding-shape admission, selected-unit-family projection, and scoped surface-affinity scoring over supplied items; `financial_row_surfaces.py` owns row text matching/parsing, column-candidate and delta-like row-label classification, aggregate-like row stage/role and candidate value-role/stage projection, candidate operand-context and structured-sibling projection, segment-local binding, segment-metric composition, and sibling-surface hit counting |
| Operand policy and resolution | `financial_operand_resolution.py`, including lookup-hint projection/matching, direct candidate logical/family signature projection, candidate location/entity subject scoring, deterministic positional preference scoring, ratio sign policy, evidence-local unit/period coercion, dependency-task KRW consistency, table-metadata/raw-unit repair, and growth alignment/period conflict |
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
| Latest focused owner checkpoint | PASS, contextual-aggregate-preference ownership 4 / 4; owner module 122 / 122 |
| Latest semantic regression set | PASS, affected eleven-module set 1,082 / 1,082 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed records |
| Full unittest discovery | PASS, 1,975 / 1,975 |
| Benchmark refresh after latest contextual-aggregate-preference ownership change | **NOT RUN** |
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
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, lookup magnitude and hint projection/matching, same-block unit/table repair, direct structured lookup-row/value projection, lookup answer-slot/support projection, dependency input matching/binding, deterministic runtime/ontology planning, generic operand-period, query/task period-focus and single-report-scope policy, structured-cell selection/scoring and candidate selected-cell preparation, candidate report/period-scope policy and period/table coherence scoring, candidate concept-conflict and contextual-aggregate preference, candidate surface-contract/segment binding and scoped surface-affinity scoring, candidate metadata-policy projection, candidate location/entity subject scoring, deterministic positional preference scoring, column-candidate and delta-like row-label classification, segment-local/segment-metric row-surface ownership, aggregate-like row and candidate value-role/stage projection, candidate operand-context/structured-sibling projection, direct candidate logical/family signature projection, sibling-surface hit counting, and query-to-metric/operand matching; graph-state lookup, direct/ratio acceptance, broader evidence orchestration, scoring/reconciliation, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Minimally advanced through bounded read-only reconciliation artifact-reference projection; artifact mutation and whole-ledger synchronization require separate contracts |
| Private API mesh and test co-location | Partially advanced as public contracts, semantic-planner normalization/validation, narrative-task policy, lookup answer-slot/support, read-only retrieval-hint projection, and quantitative-impact projection moved; broader evidence and orchestration seams remain |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The characterize-only inventory selects exactly one production follow-on. Move
only the current exact 9-line
`_is_balance_sheet_aggregate_operand(operand: Dict[str, Any]) -> bool`
definition from `financial_graph_helpers.py` to the existing
`financial_surface_contracts.py` owner as public
`is_balance_sheet_aggregate_operand(...)`.

No production source or test has moved for this projection. The predicate
classifies only already prepared operand needles against the declarative
`HELPER_RUNTIME_POLICY["balance_sheet_aggregate_labels"]` prior. It does not
define or expand those labels, build a candidate, score or admit a row,
retrieve evidence, or read/write graph state. The destination already imports
`re`, `_normalise_spaces`, and `HELPER_RUNTIME_POLICY` and owns
`_operand_needles(...)`; graph already reaches it and it does not reach graph.
Current public/private counts are graph helpers 9/83 and surface contracts
12/7; projected counts are 9/82 and 13/7. The full 48-module/203-internal-edge
DAG remains unchanged, and the selected span contains zero of the 217 reviewed
runtime-domain records.

Preserve the exact operand-needle phase. Call `_operand_needles(operand)` once
with the original operand identity and consume its result eagerly in the
current set comprehension. Every returned needle, including a falsey or blank
one, goes directly to `_normalise_spaces(needle)` without a local string
conversion or filter. Pass that exact result to positional
`re.sub(r"\s+", "", normalized)` and insert the substitution result into the
fresh set. Preserve hashing, equality, duplicate collapse, and complete
materialization. Only after the set is complete call `needles.discard("")`
once. Do not replace the set with an ordered collection, add a pre-filter, or
move blank removal into the comprehension.

Only after needle preparation and discard evaluate exact
`HELPER_RUNTIME_POLICY.get("balance_sheet_aggregate_labels")`, its raw
`or ()`, and pass the resulting iterable through the current generator to one
`set(...)` call. Do not copy or mutate the policy. For each policy item, the
filter calls `str(item)` once and tests that exact result directly; it does not
strip. An empty string is dropped after one conversion, while a retained item
is stringified again, normalized once, then passed to exact positional
`re.sub(r"\s+", "", ...)`. A whitespace-only string is therefore retained by
the filter and may become `""` in the label set. Preserve eager full
consumption by `set(...)`, hashing/equality, duplicate collapse, and the fact
that this second set does not discard its blank result.

After both sets are complete, preserve exact
`any(needle in aggregate_labels for needle in needles)`. It scans the native
set iteration, not original operand order; membership stops at the first hit
and the built-in `any(...)` result is returned without a second coercion. Empty
needle or policy sets return exact `False`. Do not sort, alias, broaden,
case-fold, add policy labels, or synthesize candidate support.

There is no exception boundary. Operand-needle call/iteration, normalization,
`re.sub` lookup/call, first-set hash/equality and discard, policy get/truth/
iteration, string conversion/truth, `set` lookup/construction, second-set hash/
equality, membership, and `any(...)` lookup/call failures remain uncaught.
Inputs and checked-in policy remain unmodified. No wrapper, graph alias,
callback, reason, flag, trace, coercion, fallback, or compatibility bridge is
permitted.

The projection has exactly two direct `ast.Name` calls, each positional exact
`operand`, with no keywords, caller `try` depth zero, and immediate `If`
parent. In `_candidate_source_priority_bonus(...)` the gate remains body
statement 1 of 6, immediately after `score = 0.0` and before capex,
contextual-aggregate, and note-aggregate work. Truth only enters the existing
balance-sheet source-priority branch; falsehood skips it, and either
non-returning path continues the later caller work unchanged.

In `_candidate_satisfies_direct_acceptance_contract(...)` the gate remains
body statement 13 of 19, after grounding, selected-cell/period, binding-policy,
lookup-unit/direct-strength, prepared statement/value-role/stage/context, and
canonical-statement guards, but before capex, metadata-period/target-year, and
final-return work. A truthy gate rejects only the existing exact
`statement_type == "notes" and value_role == "detail"` combination; truth with
any other prepared values and falsehood both continue. Helper or caller-side
result-truth failures stop all later work in either caller.

Moving the declarative label values, `_operand_needles(...)`, either caller
branch, capex or contextual/note predicates, source-priority scoring, direct
grounding/acceptance preparation, period/unit/report/canonical policy, broader
matching/scoring/ranking, candidate/evidence construction or adoption,
report-file I/O, retrieval, graph state, model invocation, artifact/ledger
mutation, retry, or final sequencing is rejected.

Before production movement, add exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_balance_sheet_aggregate_operand_pins_needles_policy_normalization_and_result`;
- `test_current_source_balance_sheet_aggregate_operand_pins_laziness_identity_immutability_and_exceptions`;
- `test_current_source_balance_sheet_aggregate_operand_bindings_pin_def_calls_policy_dag_imports_and_baseline`;
- `test_current_source_balance_sheet_aggregate_operand_callers_pin_gate_order_args_adoption_and_stops`.

They must pin the exact 9-line definition/signature, original operand identity,
needle-set normalization/substitution/dedupe/discard ordering, policy get/or and
filter-versus-expression string conversions, whitespace behavior, eager policy
set materialization, native set membership and exact result, policy/input
immutability, every uncaught failure, both caller expressions/positions/
arguments/branches/stops, current/projected function counts, import DAG, and
zero selected-body runtime-domain records.

Projected post-move gates are focused 4/4, graph-helper characterization owner
126/126, affected eleven-module semantic set 1,086/1,086,
import-side-effects 19/19, audit 217, and full discovery 1,979/1,979, plus
pycompile/fresh import and public identity 1/1, selected-body parity 1/1, all 91
retained graph and 19 retained surface-owner functions, both callers, full
48-module/203-edge DAG parity, retired executable graph-private refs zero, and
`git diff --check`. These are projections to verify, not completed results.

Static definition/call/DAG/function-count and selected-body audit inspection,
direct behavior probes 6/6, and caller gate/branch probes 3/3 passed. Benchmark
refresh and remote CI were **NOT RUN**. This characterization makes no
behavior, accuracy, ranking, performance, benchmark, schedule, ledger, or
Phase 3 completion claim.

## Completed Contextual-Aggregate-Preference Characterization

Commit `c837e31` moved the exact former 17-line graph predicate to public
`financial_surface_contracts.operand_prefers_contextual_aggregate_match(...)`
with its body unchanged. The old private definition and all executable private
references are gone; no graph alias or compatibility bridge was added.

Binding-policy get/or/copy ordering, dropped-once and retained-twice item
stringification, normalization, role-before-stage-before-contract precedence,
case-sensitive schema membership, original operand identity, exact final
boolean, nested identities, immutability, and every uncaught failure remain
pinned by four CURRENT-SOURCE methods. The three graph calls finish external/
local 3/0 with positional exact `operand`, no keywords, caller `try` depth zero,
and immediate `If` parents. Their source-priority, candidate-matching, and
direct-strength branches remain caller-owned and unchanged.

Production source is `+23/-22`, net `+1`: graph helpers are `+4/-22` and move
from 5,412 to 5,394 physical lines; surface contracts are `+19/-0` and move
from 426 to 445. Graph-helper tests are `+1,084/-32`, net `+1,052`, and move
from 25,304 to 26,356 lines. The whole commit is `+1,107/-54`, net `+1,053`,
and four methods move discovery from 1,971 to 1,975. Final public/private counts
are graph 9/83 and surface owner 12/7. The source diff SHA-256 is
`23f01c478d1d63b68e4f499254fa43ecc388bc0a53cd0b6391ce6f238f044fc5`.

Focused 4/4, owner 122/122, affected semantic 1,082/1,082, import 19/19,
audit 217, and full 1,975/1,975 passed. Pycompile, fresh import/public identity
2/2, selected-body parity 1/1, retained graph exact 89/92 and call-normalized
92/92, retained surface owner 18/18, all three callers, full 48-module/203-edge
DAG parity, retired private refs zero, non-ASCII preservation, and
`git diff --check` also passed. Benchmark refresh and remote CI were
**NOT RUN**.

This milestone changes only deterministic contextual-aggregate-preference
ownership. It proves no behavior, accuracy, ranking, performance, total-code or
executed-path reduction, benchmark improvement, schedule, ledger completion,
or Phase 3 completion.

### Historical Contextual-Aggregate-Preference Characterization Contract

The characterize-only inventory selects exactly one production follow-on. Move
only the current 17-line
`_operand_prefers_contextual_aggregate_match(operand: Dict[str, Any]) -> bool`
definition from `financial_graph_helpers.py` to the existing
`financial_surface_contracts.py` owner as public
`operand_prefers_contextual_aggregate_match(...)`.

No production source or test has moved for this projection. The helper consumes
one already prepared operand mapping and decides only whether its binding-policy
preferences and positive surface contract authorize the callers' existing
contextual aggregate branches. It does not build candidate context, match a
candidate, change a score, retrieve evidence, or read/write graph state. The
destination already imports `_normalise_spaces` and owns
`_operand_surface_contract(...)`; graph already reaches the destination and the
destination does not reach graph. Current public/private counts are graph
helpers 9/84 and surface contracts 11/7; projected counts are 9/83 and 12/7.
The full 48-module/203-internal-edge DAG remains unchanged.

Preserve exact binding-policy preparation. Evaluate
`operand.get("binding_policy")`, its raw `or {}`, and one `dict(...)` shallow
copy in that order. A falsey raw value selects the fresh empty literal before
the copy; a truthy value is passed directly to `dict`. The copied mapping is
fresh while nested identities remain unchanged. No deep copy, mapping fallback,
or input mutation is allowed.

Build `preferred_value_roles` first and `preferred_aggregation_stages` second.
For each corresponding raw iterable, preserve exact `.get(...) or []`, eager
left-to-right iteration, and the current comprehension ordering. Each item is
first evaluated as `str(item).strip()` in the filter. A blank item is dropped
after that one string/strip path. A retained item is stringified again and that
exact second string is passed once to `_normalise_spaces(...)`; the normalized
result is retained even when falsey. Preserve duplicates, order, list
materialization, and the separation between the filter and retained expression.

After both fresh lists are complete, exact `"aggregate" not in
preferred_value_roles` returns `False` before stage membership or surface-
contract work. On a role hit, scan the stage list through the current ordered
`any(stage in {"final", "subtotal", "direct"} ...)`; the first hit stops the
scan. A complete miss returns exact `False` before the contract helper. These
schema markers remain exact, case-sensitive runtime contract values; do not
normalize, alias, expand, or move them into a new domain policy.

Only after both gates pass call `_operand_surface_contract(operand)` once with
the original operand identity, call `.get("positive")` directly on its exact
return, apply `bool(...)` once, and return that exact boolean. Do not copy the
contract, add `or []`, inspect negative terms, or infer support from candidate
text. Raw operand/mapping truth, dictionary construction, mapping get,
iteration, string/strip, normalization, list membership/equality, stage
membership, `any`, contract call/get, and final truth failures all remain
uncaught. No wrapper, graph alias, callback, reason, flag, trace, coercion, or
fallback is permitted.

The projection has exactly three direct `ast.Name` calls, each positional exact
`operand`, with no keywords, caller `try` depth zero, and immediate `If` parent.
In `_candidate_source_priority_bonus(...)` the gate remains body statement 3,
after the balance-sheet and capex branches and before note-aggregate scoring.
In `_candidate_matches_operand(...)` it remains body statement 16, after the
capex branch and before the structured-candidate stop and free-text fallback.
In `_candidate_direct_match_strength(...)` it remains body statement 9, after
the capex branch and before aggregate-signal scoring. Truth only enters each
caller's existing contextual branch; falsehood skips that branch and continues
the current caller. Helper or result-truth failures remain uncaught and stop all
later caller work.

Moving any caller branch, `candidate_local_aggregate_context(...)`, positive-
surface matching, candidate value-role/stage projection, balance-sheet/capex or
note-aggregate predicates, source-priority scoring, broader candidate matching
or direct-strength scoring, candidate/evidence construction or adoption,
report-file I/O, retrieval, graph state, model invocation, artifact/ledger
mutation, retry, or final sequencing is rejected. This batch isolates only the
generic binding-policy/surface-contract preference predicate; the domain-
qualified balance-sheet/capex/source-priority cluster still requires its own
policy-and-owner characterization.

Before production movement, add exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_operand_prefers_contextual_aggregate_match_pins_role_stage_and_contract_precedence`;
- `test_current_source_operand_prefers_contextual_aggregate_match_pins_copy_laziness_identity_and_exceptions`;
- `test_current_source_operand_prefers_contextual_aggregate_match_bindings_pin_def_calls_dag_imports_and_baseline`;
- `test_current_source_operand_prefers_contextual_aggregate_match_callers_pin_gate_order_args_adoption_and_stops`.

They must pin the exact 17-line definition/signature, copy and repeated
stringification/normalization behavior, role-before-stage-before-contract
precedence, exact membership and return values, nested identities and input
immutability, every uncaught failure, all three caller expressions/positions/
arguments/branches/stops, current/projected function counts, import DAG, and
zero selected-body runtime-domain records.

Projected post-move gates are focused 4/4, graph-helper characterization owner
122/122, affected eleven-module semantic set 1,082/1,082,
import-side-effects 19/19, audit 217, and full discovery 1,975/1,975, plus
pycompile/fresh import and public identity 1/1, selected body parity 1/1, all 92
retained graph and 18 retained surface-owner functions, all three callers, full
48-module/203-edge DAG parity, retired executable graph-private refs zero, and
`git diff --check`. These are projections to verify, not completed results.

Static definition/call/DAG/function-count and selected-body audit inspection,
direct behavior probes 8/8, and caller gate/argument probes 3/3 passed.
Benchmark refresh and remote CI were **NOT RUN**. This characterization makes
no behavior, accuracy, ranking, performance, benchmark, schedule, ledger, or
Phase 3 completion claim.

## Completed Candidate-Concept-Conflict Characterization

Commit `4c8c89c` declared exact
`CANDIDATE_CONCEPT_CONFLICT_EXCLUSIVE_MARKER = "부채"` in retrieval policy and
moved the exact former 27-line graph predicate to public
`financial_surface_contracts.candidate_conflicts_with_operand_concept(...)`.
The three graph calls remain positional exact `candidate, operand`, at caller
`try` depth zero and immediate `If` parents; their `False`, `0.0`, and `-10.0`
conflict returns and placement are unchanged.

Repeated operand normalization, ordered metadata surfaces, shallow-copy and
nested-identity behavior, special-marker precedence and candidate-text
exclusion, negative-before-positive-before-text fallback, exact returns, all
uncaught failures, caller stops, and input immutability are pinned by four
CURRENT-SOURCE methods. No graph alias, wrapper, callback, carrier, reason,
flag, trace, new marker family, coercion, or fallback was added.

Production source is `+36/-32`, net `+4`: graph helpers are `+4/-32` and move
from 5,440 to 5,412 physical lines; surface contracts are `+30/-0` and move
from 396 to 426; retrieval policy is `+2/-0`. Tests and the reviewed fixture are
`+1,004/-118`, net `+886`; graph-helper tests are `+962/-65`, net `+897`, and
move from 24,407 to 25,304 lines. The whole commit is `+1,040/-150`, net
`+890`, and four methods move discovery from 1,967 to 1,971. Final
public/private counts are graph 9/84 and surface owner 11/7. The source diff
SHA-256 is
`bf99e85d3326af212d057d1f6f6fff175768e71149fe44fdb6ae7e865a7b017a`.

The audit corrected the characterization's stale line-derived zero-hit claim:
the two removed inline marker occurrences formed one grouped reviewed record
under the graph path. Moving the only literal to excluded config therefore
reduces the reviewed baseline from 218 to 217; the fixture and its exact-count
contracts were updated without weakening the audit.

Focused 4/4, owner 118/118, affected semantic 1,078/1,078, import 19/19,
audit 217, and full 1,971/1,971 passed. Pycompile, fresh import/public identity,
policy-normalized selected-body parity, retained graph exact 90/93 and
normalized 93/93, retained surface owner 17/17, all three callers, full
48-module/203-edge DAG parity, retired private refs zero, non-ASCII diff audit,
and `git diff --check` also passed. Benchmark refresh and remote CI were
**NOT RUN**.

This milestone changes only deterministic candidate concept-conflict ownership
and vocabulary placement. It proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

### Historical Candidate-Concept-Conflict Characterization Contract

The historical characterize-only inventory selected exactly one production
follow-on. In one bounded policy-and-owner batch, first declare exact
`CANDIDATE_CONCEPT_CONFLICT_EXCLUSIVE_MARKER = "부채"` in
`src/config/retrieval_policy.py`, then move the current 27-line
`_candidate_conflicts_with_operand_concept(candidate: Dict[str, Any], operand:
Dict[str, Any]) -> bool` definition from `financial_graph_helpers.py` to the
existing `financial_surface_contracts.py` owner as public
`candidate_conflicts_with_operand_concept(...)`.

No production source or test has moved for this projection at this
characterization checkpoint. The marker is a reviewed domain prior used by the
legacy conflict fallback when an operand lacks a sufficiently discriminating
surface contract. Its value therefore belongs in retrieval policy, not runtime
control flow. Runtime code may load the named marker and perform generic
ordered membership only; it must not retain either inline marker literal or a
domain-named control variable. This is a behavior-preserving classification,
not a new candidate rule or an authorization to add marker families.

The selected helper consumes only already supplied candidate/operand mappings
and the surface owner's existing normalization, operand-needle, surface-
contract, positive-surface, and negative-surface primitives. It does not build
candidates, resolve periods or units, score/rank a winner, retrieve evidence,
or read/write graph state. Graph already reaches `financial_surface_contracts`
and that owner does not reach graph helpers. The config extraction adds no
runtime module edge. Current top-level public/private counts are graph helpers
9/85 and surface contracts 10/7; projected counts are 9/84 and 11/7. The full
48-module/203-internal-edge DAG remains unchanged.

The move must preserve this exact marker and operand-needle contract:

- call `_operand_needles(operand)` once and consume it eagerly in the current
  list comprehension. Each raw needle first enters `_normalise_spaces(...)` in
  the filter; a falsey result is dropped after one normalization, while a
  retained needle is normalized again and the exact second result is stored.
  Duplicate/order behavior and raw inputs remain unchanged;
- only after the fresh normalized list is complete, evaluate ordered
  `exclusive_marker in needle` membership through the current `any(...)`.
  Preserve first-hit short circuit and exact truth. The checked-in policy
  marker is the exact former inline value; do not normalize, expand, alias, or
  synthesize it in runtime code;
- the marker result means only that the operand already expects the exclusive
  surface. It is not itself a positive match and must not skip later contract
  checks except where the current `not expects...` gate already does so.

Then preserve candidate authoritative-surface preparation exactly. Evaluate
`candidate.get("metadata")`, raw `or {}`, and one `dict(...)` shallow copy.
Build surfaces in exact order: `semantic_label`, `row_label`,
`aggregate_label`, joined `semantic_aliases`, then joined `row_headers`.
Scalar values keep get/or/string/strip order. Alias/header iterables are eager;
each retained item is stringified/stripped in the filter and again in the
retained expression, while a blank item is processed only by the filter. The
second exact strings feed `" ".join(...)`. The final fresh list applies raw
surface truth in order. Inputs remain unmodified and nested identities remain
untouched.

If the operand does not expect the policy marker, normalize each authoritative
surface once in order and return exact `True` at the first marker membership.
This gate remains before `_operand_surface_contract(...)`; it does not inspect
`candidate["text"]`. If the operand expects the marker, skip this candidate-
marker scan. Next call `_operand_surface_contract(operand)` once. A falsey
contract returns exact `False`. Otherwise scan every authoritative surface for
negative contract support first, in order; the first hit returns exact `True`
and therefore outranks any positive surface. Only after a complete negative
miss scan the same surfaces for positive support; the first hit returns exact
`False`. Only after both misses evaluate exact
`str(candidate.get("text") or "")` and return the exact result of one final
`_text_has_negative_surface(..., operand)` call. Candidate text never receives
the special policy-marker gate or a positive-surface fallback.

There is no catch boundary. Preserve every current uncaught operand iteration,
normalization, membership, candidate/metadata get and truth, dictionary copy,
string/strip/join, authoritative-surface truth, contract lookup/truth,
positive/negative helper, candidate-text conversion, and returned-result
failure. Do not add a wrapper, graph alias, callback, reason, flag, trace,
coercion, fallback, or policy default.

The projection has three direct `ast.Name` calls, each with exact positional
`candidate, operand`, no keywords, caller `try` depth zero, and immediate `If`
parent. `_candidate_matches_operand(...)` calls it as its first executable
condition; truth returns exact `False`, falsehood continues candidate-kind and
surface matching. `_candidate_direct_match_strength(...)` calls it immediately
after its docstring; truth returns exact `0.0`, falsehood continues strength
preparation. `_score_operand_candidate(...)` first shallow-copies candidate
metadata, then calls it; truth returns exact `-10.0`, falsehood initializes and
continues the score. Any helper or caller-side truth failure remains uncaught
and stops every later caller operation and enclosing adoption.

Moving the callers, other operand/surface matching, direct or ratio acceptance,
candidate construction, broader score/rank work, candidate/evidence adoption,
report-file I/O, retrieval, graph state, model invocation, artifact/ledger
mutation, retry assembly, or final sequencing is rejected. Balance-sheet/capex
aggregate predicates and source-priority scoring remain excluded until their
separate declarative dependencies are classified. The cycle-forming candidate
builder, graph-state year projection, and local report-file unit-hint cluster
remain outside this batch.

Before production movement, add exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_candidate_concept_conflict_pins_marker_precedence_and_contract_fallback`;
- `test_current_source_candidate_concept_conflict_pins_copy_laziness_identity_and_exceptions`;
- `test_current_source_candidate_concept_conflict_bindings_pin_def_calls_policy_dag_and_baseline`;
- `test_current_source_candidate_concept_conflict_callers_pin_gate_args_returns_and_stops`.

They must pin the 27-line current definition and complete positional signature,
the exact policy value and removal of inline runtime vocabulary, repeated
needle/alias/header normalization or stringification, ordered authoritative
surfaces, special-marker precedence and text exclusion, negative-before-
positive-before-text contract flow, exact returns, shallow-copy/nested identity
and input immutability, every uncaught error, all three caller expressions and
gate/order/return/stops, current/projected function counts, import DAG, and zero
selected-body runtime-domain records.

Projected post-move gates are focused 4/4, graph-helper characterization owner
118/118, affected eleven-module semantic set 1,078/1,078,
import-side-effects 19/19, audit 218, and full discovery 1,971/1,971, plus
pycompile/fresh import and public identity 1/1, selected policy-normalized body
parity 1/1, all 93 retained graph and 17 retained surface-owner functions, all
three caller expressions/bodies, full 48-module/203-edge DAG parity, retired
executable graph-private refs zero, and `git diff --check`. Counts are the
current executed sets plus four new methods and remain projections to verify.

Static definition/call/DAG/function-count and selected-body baseline inspection,
direct behavior probes 8/8, and caller gate/order/return probes 3/3 passed.
Benchmark refresh and remote CI were **NOT RUN**. This characterization makes
no behavior, accuracy, ranking, performance, benchmark, schedule, ledger, or
Phase 3 completion claim.

## Completed Single-Report-Scope Characterization

The historical characterization below predates `471f6a5`. Commit `471f6a5`
moved the exact former 8-line predicate to public
`financial_scope_policies.has_single_report_scope(...)` with its body and sole
caller placement unchanged. Source is `+12/-12`: graph helpers moved from
5,450 to 5,440 physical lines and scope policies from 529 to 539. Tests are
`+620/-29`, moving graph-helper tests from 23,816 to 24,407 lines; the whole
commit is `+632/-41`. Four methods moved discovery from 1,963 to 1,967. The
source diff SHA-256 is
`2deab9c118170b25431f43717bd2dc0328798416cbd3da18cc29891b7ab369cf`.

Executed gates passed focused 4/4, owner 114/114, affected semantic
1,074/1,074, import 19/19, audit 218, and full 1,967/1,967. Pycompile, fresh
import/public identity, whole-function/body parity, retained graph 94/94 after
target-call normalization, retained scope owner 19/19, the sole caller/body,
48-module/203-edge DAG parity, zero selected-body audit hits, retired private
refs zero, and diff check also passed. Benchmark refresh and remote CI were
**NOT RUN**. The section is retained only as an audit record and is not an
active or competing priority.

The characterize-only inventory selects exactly one production follow-on. Move
the exact current 8-line
`_has_single_report_scope(report_scope: Dict[str, Any]) -> bool` definition from
`financial_graph_helpers.py` to the existing `financial_scope_policies.py`
owner as public `has_single_report_scope(...)`.

No production source or test has moved for this projection at this
characterization checkpoint. The helper receives one caller-supplied report-
scope mapping and returns only whether its copied scope resolves to at most one
source receipt. It does not normalize company/year lists, align scope hints,
select a report, read a report file, build candidates/evidence, retrieve
documents, or read/write graph state. The destination already imports `Any`
and `Dict` and owns `_report_scope_source_receipts(...)`. Graph already reaches
scope policies and that owner does not reach graph helpers, so the move adds no
module edge. Current top-level public/private counts are graph helpers 9/86 and
scope policies 10/9; projected counts are 9/85 and 11/9.

`has_single_report_scope(...)` must preserve this exact copy and explicit-
receipt contract:

- evaluate raw `report_scope or {}` first, then call `dict(...)` exactly once.
  A truthy input is passed directly to `dict`; a falsey input selects the fresh
  empty literal before the copy. Raw input truth, mapping iteration/key-value
  access, and `dict` construction all remain outside the function's `try` and
  therefore uncaught. The resulting `scope` is a fresh shallow dictionary:
  top-level mutations never reach the input, while nested value identities are
  preserved exactly;
- call exact `scope.get("rcept_no")`, apply raw `or ""`, call `str(...)`, then
  `.strip()`, and apply truth to that exact stripped result. All receipt-key
  lookup, raw truth, string conversion, strip, and stripped-result truth work
  remains outside the `try`. A truthy stripped receipt number returns exact
  `True` before source-receipt projection or length access;
- only on a falsey stripped receipt number enter the current `try`, call
  `_report_scope_source_receipts(scope)` once with the exact fresh scope as one
  positional argument and no keywords, call `len(...)` once on its exact
  result, compare `<= 1`, and return that result. Zero or one receipt returns
  `True`; two or more returns `False`.

The `except Exception` boundary must remain exact and cover only source-receipt
projection, length, comparison, and return-expression evaluation inside the
current `try`. Any caught `Exception` returns exact `False`; `BaseException`
subclasses and every error before the `try` remain uncaught. Do not add a
string coercion, deep copy, alternate receipt source, catch expansion, wrapper,
graph alias, callback, reason, flag, trace, or fallback.

The projection currently has one direct `ast.Name` call in
`align_scope_hints(...)`, positional with exact `report_scope`, no keywords,
caller `try` depth zero, and immediate parent `If`. The caller extracts the
scope company/year and fully prepares fresh normalized company/year lists
first. It calls the helper only under truthy `scope_company`, before any scope-
company adoption and before the later scope-year adoption.

A truthy result replaces the prepared company list with exact
`[scope_company]`. A falsey result falls through in order: an empty prepared
list becomes `[scope_company]`; otherwise a missing scope company is prepended;
otherwise the existing list is retained. A falsey scope company skips the
helper entirely. Errors before the helper's `try` remain uncaught and stop all
later company/year adoption, while an ordinary receipt-projection `Exception`
is converted inside the helper to `False` and therefore follows the caller's
existing fallback branch. Supplied report-scope and company/year inputs remain
unmodified.

After the move the selected call finishes owner-external one/owner-local zero.
The full 48-module/203-internal-edge agent import DAG must remain unchanged;
graph replaces its private `_report_scope_source_receipts` import with the
public predicate, and the selected span contains zero of the 218 reviewed
runtime-domain records.

Moving `align_scope_hints(...)`, company/year normalization, report inventory/
receipt projection, consolidation or candidate scope policy, report selection,
candidate/evidence construction, retrieval, report-file I/O, graph state,
artifact/ledger mutation, or final sequencing is rejected. The local report-
path/text/unit-hint cluster remains excluded because it performs file I/O and
needs a separate owner contract. Candidate concept-conflict and balance-sheet/
capex aggregate predicates remain excluded until their direct domain markers
are classified into policy/ontology. `_build_reconciliation_candidate(...)`
remains excluded because its natural owner currently reaches graph helpers and
a one-function move would create a cycle. `_query_years_from_state(...)`
remains graph-owned because it reads graph state. A new module or compatibility
bridge would add surface without resolving this boundary.

The completed movement added exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_has_single_report_scope_pins_receipt_precedence_and_cardinality`;
- `test_current_source_has_single_report_scope_pins_copy_laziness_identity_and_exception_boundary`;
- `test_current_source_has_single_report_scope_bindings_pin_def_call_dag_imports_and_baseline`;
- `test_current_source_has_single_report_scope_caller_pins_gate_order_adoption_and_stops`.

They pin the exact 8-line span/signature, raw input truth and copy operand,
fresh shallow-copy/nested identity behavior, explicit receipt-number lookup/
conversion/strip/truth fast path, receipt-helper and length laziness, exact
zero/one/many cardinality results, the precise `Exception` catch boundary and
uncaught `BaseException`/pre-try failures, input immutability, the sole caller
expression/gate/argument/order/adoption/stops, current/projected function
counts, import DAG, and zero selected-body runtime-domain records.

Executed post-move gates are focused 4/4, graph-helper characterization owner
114/114, affected eleven-module semantic set 1,074/1,074, import-side-effects
19/19, audit 218, and full discovery 1,967/1,967, plus pycompile/fresh import and
public identity 1/1, selected-body parity 1/1, all 94 retained graph and 19
retained scope-owner functions, the sole caller expression/body, full
48-module/203-edge DAG parity, retired executable graph-private refs zero, and
`git diff --check`.

Keep caller-owned company/year alignment, report selection/inventory,
candidate/evidence construction, score/rank/admission/acceptance, report-file
I/O, retrieval, graph state, model invocation, artifact/ledger mutation, retry
assembly, and final sequencing outside this owner move. The inventory and
ownership relocation establish no behavior, accuracy, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim. Static definition/
call/DAG/function-count and selected-body baseline inspection, direct behavior
probes 6/6, and caller order/adoption/stop probes 3/3 passed; benchmark refresh
and remote CI were **NOT RUN**.

## Completed Preference-Bonus Characterization

The historical characterization below predates `c4558b7`. Its move and
projected gates are complete; it is retained only as an audit record and is not
an active or competing priority.

The characterize-only inventory selects exactly one production follow-on. Move
the exact current 7-line
`_preference_bonus(value: str, preferred: List[str], *, base: float = 0.4) -> float`
definition from `financial_graph_helpers.py` to the existing
`financial_operand_resolution.py` owner as public `preference_bonus(...)`.

No production source or test has moved for this projection at this
characterization checkpoint. The helper receives one already prepared value,
one caller-prepared preference iterable, and a keyword-only base. It returns
only a deterministic positional bonus. It does not derive candidate roles or
stages, read operand policy, build candidates, decide acceptance, own the
surrounding score/rank, adopt a winner, retrieve evidence, or read/write graph
state. The destination already imports `List` and `_normalise_spaces`; graph
already reaches operand resolution and that owner does not reach graph helpers,
so the move adds no module edge. Current top-level public/private counts are
graph helpers 9/88 and operand resolution 44/37; projected counts are 9/87 and
45/37.

`preference_bonus(...)` must preserve this exact preference materialization
contract:

- call `iter(preferred)` through the list comprehension and consume it eagerly
  in source order. For each raw item, call `_normalise_spaces(item)` in the
  filter and apply raw truth to that result. A falsey result skips the item
  after one normalization; a retained item calls `_normalise_spaces(item)`
  again and appends that exact second result. Thus retained items normalize
  twice, dropped items once, non-repeatable normalization remains observable,
  and all preference work completes before value normalization;
- build a fresh ordered list without string coercion or mutation of the supplied
  iterable/items. Preserve raw item identity at the normalization boundary,
  eager iteration, duplicate/order retention, nested identity, and input
  immutability;
- only after the ordered list completes, call `_normalise_spaces(value)` once.
  Apply raw truth to that target first. A falsey target returns exact `0.0`
  without list membership, index, length, max, or multiplication.
  A truthy missing target performs ordered list membership and returns exact
  `0.0`.

When membership succeeds, preserve the separate
`ordered.index(target)` scan from the beginning and its first-equal result.
Then evaluate `base * max(len(ordered) - index, 1)` exactly in that order:
`len` once, subtraction, `max` once with the computed distance and integer
`1`, then left-hand base multiplication. With ordinary strings and default
base, a three-item ordered list scores first/middle/last as `1.2/0.8/0.4`;
duplicates use the first equal index. Do not coerce base or the product to
`float`; return the exact multiplication result. Preserve repeated equality
between membership and index, stateful equality behavior, the keyword-only
`base=0.4` default, and every currently uncaught preferred iteration,
normalization, truth, equality/membership, index, length, subtraction, max, and
multiplication error. No new catch, wrapper, graph alias, callback, reason,
flag, trace, coercion, or fallback is allowed.

The projection currently has two direct `ast.Name` calls, both in
`_score_operand_candidate(...)`, at caller `try` depth zero and
`AugAssign` depth one. The first receives exact positional `value_role` and
`preferred_value_roles` with keyword `base=0.6`; the second immediately
receives exact positional `aggregation_stage` and
`preferred_aggregation_stages` with keyword `base=0.5`. Both occur after
the caller has rebuilt its preferred/avoid role and stage collections and after
candidate period-focus scoring, but before avoid-role/stage penalties,
preferred-section scoring, source priority, metadata-period, table-coherence,
report-scope, final-table, and return work. The first result is added to
`score` before the second call; the second result is then added. A first-call
failure stops the second call and every later operation. A second-call failure
preserves only local intermediate mutation before propagating and still stops
all later work and enclosing ranking/adoption. Caller-side addition errors
remain uncaught.

After the move the calls finish owner-external two/owner-local zero. The full
48-module agent import DAG must remain unchanged; the selected span contains
zero of the 218 reviewed runtime-domain records. Graph continues to use
`_normalise_spaces` elsewhere, so its existing normalization import is not
part of this move.

Moving caller-side preference/avoid collection construction, value-role or
aggregation-stage derivation, candidate construction, concept/direct matching,
direct/ratio acceptance, source/report/period or broader score/rank work,
candidate/evidence adoption, retrieval, state/artifact/ledger mutation, or
final sequencing is rejected. A new module or compatibility bridge would add
surface without resolving a boundary. Candidate concept-conflict remains
excluded because its direct domain marker first requires policy/ontology
classification; source-priority scoring remains excluded because it depends on
four graph-private policy helpers. `_build_reconciliation_candidate(...)`
remains excluded because its candidate owner reaches graph, and
`_query_years_from_state(...)` reads graph state.

Before production movement, add exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_preference_bonus_pins_preferred_normalization_membership_index_and_score`;
- `test_current_source_preference_bonus_pins_laziness_identity_immutability_and_exceptions`;
- `test_current_source_preference_bonus_bindings_pin_def_calls_dag_imports_and_baseline`;
- `test_current_source_preference_bonus_caller_pins_order_args_adoption_and_stops`.

They must pin the exact 7-line span and complete positional/keyword-only
signature, eager preference iteration, raw normalization inputs, once-versus-
twice normalization, second-result retention, duplicate/order behavior, value
normalization timing, falsey/missing exact `0.0`, separate membership/index
scans, first-equal index, default/custom base and exact multiplication result,
identity, immutability, every uncaught error, both caller expressions,
arguments/order/adoption and exception stops, current/projected function
counts, import DAG, and zero selected-body runtime-domain records.

Projected post-move gates are focused 4/4, graph-helper characterization owner
106/106, affected semantic set 1,066/1,066, import-side-effects 19/19, audit
218, and full discovery 1,959/1,959, plus pycompile/fresh import and public
identity 1/1, selected-body parity 1/1, all 96 retained graph and 81 retained
operand-owner functions, both caller expressions and the sole caller body, full
48-module DAG parity, retired executable graph-private refs zero, and
`git diff --check`. The semantic and full counts are the current executed sets
plus four new CURRENT-SOURCE methods; they are projections to verify.

Keep caller collection preparation, role/stage derivation, all surrounding
score/rank work, matching/admission/acceptance, candidate/evidence adoption,
graph state, model invocation, artifact/ledger mutation, retry assembly, and
final sequencing outside this owner move. The inventory and future relocation
establish no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim. Static definition/call/DAG/function-count
and selected-body baseline inspection, direct behavior probes 6/6, and caller
order/adoption/stop probes 3/3 passed; benchmark refresh and remote CI were
**NOT RUN**.

## Completed Delta-Like Row-Label Characterization

The historical characterization below predates `e04a7bf`. Its move and projected
gates are complete; it is retained only as an audit record and is not an active
or competing priority.

The characterize-only inventory selects exactly one production follow-on. Move
the exact current 7-line
`_is_delta_like_row_label(label: str) -> bool` definition from
`financial_graph_helpers.py` to the existing `financial_row_surfaces.py` owner
as public `is_delta_like_row_label(...)`.

No production source or test has moved for this projection at this
characterization checkpoint. It receives one already prepared label and returns
only a policy-driven classification. It does not build candidates, infer period
focus, decide acceptance, own score/rank, adopt a winner, retrieve evidence, or
read/write graph state. The destination already imports `_normalise_spaces` and
has an existing `src.config.retrieval_policy` edge; adding only
`OPERAND_CANDIDATE_SCORING_POLICY` to that import adds no module edge. Graph
already reaches the row owner and the owner does not reach graph helpers.
Current top-level public/private counts are graph helpers 9/89 and row surfaces
9/15; projected counts are 9/88 and 10/15.

`is_delta_like_row_label(...)` must preserve this exact normalization, policy,
marker, and result contract:

- first evaluate `label or ""` with raw truth semantics, stringify that selected
  value once, and call `_normalise_spaces(...)` once. A falsey normalized result
  returns exact `False` before policy access. A falsey raw label therefore does
  not invoke that object's `__str__`, while normalization errors remain uncaught;
- only then shallow-copy `OPERAND_CANDIDATE_SCORING_POLICY`, access
  `delta_row_markers`, apply raw `or ()`, iterate it eagerly into a tuple, and
  preserve `str(item)` in both the filter and retained expression. A retained
  marker is stringified twice, a blank marker once, and every marker is consumed
  before result membership begins;
- finally evaluate `any(token in text for token in delta_markers)` in policy
  order. Membership stops at the first hit and returns the exact boolean from
  `any(...)`. With the checked-in policy, labels containing `증가(감소)`, `증가`,
  `감소`, `증감`, or `변동` classify true; ordinary labels and blanks classify
  false.

Preserve the exact policy shallow copy, raw label/marker truth behavior, repeated
marker stringification, eager tuple materialization, ordered membership and
first-hit short circuit, nested identities, input/policy immutability, and every
currently uncaught label, normalization, mapping-copy/get, truth, iteration,
string, tuple, membership, and `any(...)` error. No new catch, wrapper, graph
alias, callback, reason, flag, trace, coercion, or fallback is allowed.

The projection currently has three direct `ast.Name` calls, all positional with
no keywords and at caller `try` depth zero. In
`_candidate_is_direct_grounding_candidate(...)`, the first receives the prepared
`semantic_label` only when desired period focus is exact current/prior, after
candidate kind/numeric/direct-match/shape/canonical/consolidation/period setup
and before segment/report/target-period checks; true rejects immediately. The
second receives `row_text` only for lookup/single-value table rows, after
segment/report/target-period checks and after the structured-sibling rejection;
its own falsey row-text gate skips the call and true rejects immediately. In
`_score_operand_candidate(...)`, the third receives exact left-to-right
`semantic_label or row_label` only for current/prior focus, after consolidation/
period resolution and before candidate-period, segment, source/table, and return
work; true subtracts `4.0`, false changes nothing, and scoring continues.
Uncaught failures stop every later caller operation and enclosing adoption.

After the move the calls finish owner-external three/owner-local zero. The full
48-module agent import DAG must remain unchanged; the selected span contains
zero of the 218 reviewed runtime-domain records. Graph still uses
`OPERAND_CANDIDATE_SCORING_POLICY` elsewhere, so its existing policy import is
not part of this move.

Moving period-focus derivation, candidate construction, concept/direct matching,
direct/ratio acceptance, broader scoring/ranking, candidate/evidence adoption,
retrieval, state/artifact/ledger mutation, or final sequencing is rejected. A
new module or compatibility bridge would add surface without resolving a
boundary. Candidate concept-conflict is excluded from this pure move because
its direct domain marker first requires policy/ontology classification; source-
priority scoring is excluded because it still depends on four graph-private
policy helpers. `_build_reconciliation_candidate(...)` remains excluded because
its candidate owner reaches graph, and `_query_years_from_state(...)` reads graph
state.

Before production movement, add exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_delta_like_row_label_pins_normalization_policy_markers_and_result`;
- `test_current_source_delta_like_row_label_pins_laziness_repeated_strings_immutability_and_exceptions`;
- `test_current_source_delta_like_row_label_bindings_pin_def_calls_dag_imports_and_baseline`;
- `test_current_source_delta_like_row_label_callers_pin_gates_args_adoption_and_stops`.

They must pin the exact 7-line span and complete positional signature, raw label
truth/string and one normalization, blank early return, policy copy/access and
falsey marker fallback, eager marker tuple, repeated retained-marker strings,
checked-in true/false examples, ordered membership/first-hit behavior, nested
identity, immutability, every uncaught error, all three caller expressions,
gates/arguments/order/adoption and exception stops, current/projected function
counts, import DAG, and zero selected-body runtime-domain records.
Projected post-move gates are focused 4/4, graph-helper characterization owner
102/102, affected semantic set 1,062/1,062, import-side-effects 19/19, audit
218, and full discovery 1,955/1,955, plus pycompile/fresh import and public
identity 1/1, selected-body parity 1/1, all 97 retained graph and 24 retained
row-owner functions, all three caller expressions and two caller bodies, full
48-module DAG parity, retired executable graph-private refs zero, and
`git diff --check`.
The semantic and full counts are the current executed sets plus four new
CURRENT-SOURCE methods; they are projections to verify.

Keep period-focus policy, candidate/evidence construction, all score/rank work,
matching/admission/acceptance, candidate/evidence adoption, graph state, model
invocation, artifact/ledger mutation, retry assembly, and final sequencing
outside this owner move. The inventory and future relocation
establish no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim. Static definition/call/DAG/function-count
and selected-body baseline inspection, direct behavior probes 5/5, and four
existing grounding/scorer caller probes passed; benchmark refresh and remote CI were
**NOT RUN**.

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
