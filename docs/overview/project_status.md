# Project Status

> Single authority for current product state, gates, blockers, and priority.
> Stable runtime semantics live in
> [agent_runtime_contract.md](../architecture/agent_runtime_contract.md); completed
> implementation and experiment chronology live in
> [implementation_history.md](../history/implementation_history.md) and
> [experiment_history.md](../history/experiment_history.md).

Last updated: 2026-08-22

## At A Glance

| Question | Current answer |
| --- | --- |
| What is the product? | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Is the core path blocked? | No known unit/contract correctness blocker |
| What is the architecture state? | Phase 3 OPEN; deterministic runtime and ontology planning are execution-owned, four named debt groups remain |
| What just changed? | `a7c02de` renamed only `financial_operand_resolution._evidence_items_by_id(...)` in place to public `evidence_items_by_id(...)` and updated its four owner-local calls, two imports/eleven external calls, and 57 exact test expectations |
| What passed? | Direct behavior 1/1, two public-owner identities, six structure fingerprints, focused tests 1,004/1,004, runtime audit 217, pycompile 7/7, unchanged 48-module/203-edge DAG, and full unittest 2,143/2,143 for `a7c02de` |
| Was the benchmark refreshed? | **NOT RUN**; this was a name-only visibility cleanup with full-regression parity, not a policy, ingest, retrieval, or answer-behavior change |
| What is next? | Rename only `financial_operand_resolution._missing_required_operands(...)` in place to public `missing_required_operands(...)`; update two owner-local calls, three imports/22 external calls, and 61 exact direct-name/count/fingerprint expectations |

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
  graph helpers 4,294, scope policy 539, structured cells 362, surface contracts
  498, row surfaces 493,
  planning 1,240, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 625, text surface 642, operand resolution 4,816,
  dependency projection 3,419, reconciliation 1,466, reconciliation candidates
  534, aggregate projection 3,946, runtime trace 1,412, lookup recovery 1,154,
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
| Operation-family policy | `financial_operation_policies.py`; state-free query/task classifiers and numeric-grounding policy consume reviewed config while public API visibility is still converging |
| Candidate and row surface contracts | `financial_surface_contracts.py` owns operand needles and public segment-label projection, positive/negative term matching, candidate concept-conflict, contextual-aggregate and note-aggregate lookup preference, balance-sheet aggregate-operand and CAPEX-total operand classification, candidate required/numeric/descriptor projection, segment-surface matching/bonuses, local aggregate context, consolidation scope, binding-shape admission, selected-unit-family projection, and scoped surface-affinity scoring over supplied items; `financial_row_surfaces.py` owns row text matching/parsing, column-candidate and delta-like row-label classification, aggregate-like row stage/role and candidate value-role/stage projection, candidate operand-context and structured-sibling projection, segment-local binding, segment-metric composition, and sibling-surface hit counting |
| Operand policy and resolution | `financial_operand_resolution.py`, including lookup-hint projection/matching, direct candidate logical/family signature projection, candidate-to-operand matching, candidate direct-match-strength scoring, direct-candidate semantic-priority projection, canonical-statement-winner, ratio-component and direct acceptance, direct-grounding classification, candidate location/entity subject scoring, deterministic positional preference scoring, complete deterministic operand-candidate scoring, ratio sign policy, evidence-local unit/period coercion, dependency-task KRW consistency, table-metadata/raw-unit repair, and growth alignment/period conflict |
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
| Latest focused owner checkpoint | PASS, evidence-surface direct behavior 1 / 1, graph/public-owner identity, and affected graph/operand-resolution/dependency/calculation/task-artifact/operation/import set 879 / 879 |
| Latest semantic regression set | PASS, full discovery 2,143 / 2,143 after evidence-surface predicate public rename |
| Reflection-promotion caller module | PASS, 15 / 15 |
| Reflection-capability caller module | PASS, 24 / 24 |
| Reconciliation-plan regression set | PASS, 51 / 51 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed records |
| Full unittest discovery | PASS, 2,143 / 2,143 |
| Benchmark refresh after latest visibility-only cleanup | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_graph_helpers`,
`tests.test_semantic_numeric_plan`, `tests.test_operation_contracts`,
`tests.test_subtask_loop`, `tests.test_aggregate_subtask_projection`,
`tests.test_financial_aggregate_rank_dedupe`,
`tests.test_financial_dependency_projection`,
`tests.test_financial_calculation_execution`,
`tests.test_lookup_recovery_policy`,
`tests.test_financial_reconciliation_candidates`, and
`tests.test_concept_runtime_contracts`. `tests.test_import_side_effects` passed
separately at 19 / 19.

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
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, lookup magnitude and hint projection/matching, same-block unit/table repair, direct structured lookup-row/value projection, lookup answer-slot/support projection, dependency input matching/binding, deterministic runtime/ontology planning, generic operand-period, desired consolidation-scope, query/task period-focus and single-report-scope policy, structured-cell selection/scoring and candidate selected-cell preparation, candidate report/period-scope policy and period/table coherence scoring, candidate concept-conflict, contextual-aggregate and note-aggregate lookup preference, balance-sheet aggregate-operand and CAPEX-total operand classification, candidate surface-contract/segment binding and scoped surface-affinity scoring, candidate metadata-policy projection, candidate location/entity subject and source-priority scoring, deterministic positional preference and complete operand-candidate scoring, candidate-to-operand matching, direct-match-strength scoring, direct-candidate semantic-priority projection, canonical-statement-winner classification, ratio-component and direct acceptance, and direct-grounding classification, column-candidate and delta-like row-label classification, segment-local/segment-metric row-surface ownership, aggregate-like row and candidate value-role/stage projection, candidate operand-context/structured-sibling projection, direct candidate logical/family signature projection, sibling-surface hit counting, and query-to-metric/operand matching; graph-state lookup, reconciliation candidate construction/ranking, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Minimally advanced through bounded read-only reconciliation artifact-reference projection; artifact mutation and whole-ledger synchronization require separate contracts |
| Private API mesh and test co-location | Partially advanced as public contracts, semantic-planner normalization/validation, narrative-task policy, desired consolidation-scope policy, lookup answer-slot/support, read-only retrieval-hint projection, and quantitative-impact projection moved; broader evidence and orchestration seams remain |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

Rename only the exact 10-line
`src.agent.financial_operand_resolution._missing_required_operands(
required_operands: List[Dict[str, Any]],
operand_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]` definition in
place to public `missing_required_operands(...)`. Update its two owner-local
calls, three imports and 22 external calls across
`financial_calculation_execution.py`, `financial_dependency_projection.py`,
and `financial_graph_calculation.py`, plus seventeen existing exact
import/call/patch-string references across seven test files. Do not move the
body, add an alias or wrapper, rename `_operand_row_matches_requirement`, or
broaden operand matching, dependency precedence, calculation guards, fallback
merge, formula planning, ratio-result append, evidence orchestration, or final
sequencing.

The definition remains at lines 1383-1392 with two positional list arguments,
no defaults or keyword-only arguments, and a `List[Dict[str, Any]]` return.
Preserve the fresh `missing` list; direct ordered iteration over
`required_operands` with no falsey fallback; a fresh ordered
`operand_rows` scan for each operand; exact
`_operand_row_matches_requirement(row, operand)` row-before-operand argument
order; generator truth testing and first-match short circuit; covered-row
`continue` before copying; one `dict(operand)` shallow copy per missing
occurrence; ordered append including duplicate required occurrences; fresh
result identity; input and nested-object immutability; evaluation order; and
every uncaught iteration, matcher, truthiness, mapping-conversion, or append
error. The name-normalized definition AST SHA-256 is
`24640a6ba6442b89c9d37bcfa7ca674c2b1448a999e660ecf70a62ae0554588d`;
the exact body-source SHA-256 is
`d22dcfc377128ada24478863e9458d7e3bebd32533707c9a922e63cdc34ca9e0`.

The 24 calls remain at calculation-execution line 165; dependency-projection
lines 973, 1674, 1679, and 1885; graph-calculation lines 2153, 7675, 7705,
7857, 7995, 8975, 9226, 9231, 9439, 9615, 9715, 9721, 9727, 9826, 11798,
11990, and 12052; and owner lines 2355 and 2423. Every call retains two
positional arguments and no keywords. The four graph-extraction calls at lines
9615, 9715, 9721, and 9727 remain at nearest-caller `try` depth one; the other
twenty remain at zero. Preserve all assignments, ternaries, negations,
short-circuit operands, return/continue guards, the seven repeated extraction
calls, and every caller-owned adoption stop. The target-normalized combined
call-record SHA-256 over module, line, caller, arguments, keywords, normalized
parent, and `try` depth is
`ade5c496653812a4bd89d3171131128a8cb4c85779226d3ad03b85e34d684e2c`.

Current production scope is one definition, two owner-local calls, three
external imports, and 22 external calls: 28 selected source API records.
Tests contain seventeen selected exact references across
`test_financial_aggregate_rank_dedupe.py`,
`test_financial_calculation_execution.py`,
`test_financial_graph_helpers.py`,
`test_financial_operand_resolution.py`,
`test_financial_task_artifacts.py`, `test_lookup_recovery_policy.py`, and
`test_semantic_numeric_plan.py`. The future public binding has no
pre-existing definition, import, executable `Name`, attribute, or test patch
target. Graph calculation already contains one unrelated reason string exactly
`"missing_required_operands"`; it remains unchanged and is excluded from the
selected API-record count. After the rename selected private refs must finish
zero, all three external bindings must be identical to the public owner,
selected public API records must total 45 across source/tests, and owner
public/private counts must move exactly 65/26 to 66/25. Owner/calculation-
execution/dependency-projection/graph physical lines remain
4,816/1,074/3,419/13,464.

Update exactly 61 existing test expectations: seventeen selected names; 27
current owner counts from 65/26 to 66/25; two derived counts from 64/26 to
65/25; one owner/class tuple from 65/26/19 to 66/25/19; six caller-body
expectations; and eight aggregate fingerprints. The caller-body replacements
are:

- four `_extract_calculation_operands` expectations from
  `01bad5d9ccc3f43d05df0a30396ee92344fc6f715cb2e212fe6227775fe16f46`
  to `82afc10269670edbb0150da105409ffd667293f5e370f5bd75ea62196d7a64e6`;
- one period-comparison table-label builder expectation from
  `fdd9dcac55f8418ae0ed7f0f2223d6b47718b00c0ef2544dff391777cc85dbf8`
  to `ca2289c647ee7ccc0b3d91433e6c3f5f7c73627ed694c71c331deaa9c58b2bcc`;
- one formula-calculation planner expectation from
  `fae9e68d4b8ce499b9ba09c72b8d50861d881ee9ac51a2e8d3fefbd344c6d415`
  to `e1f6f5b5416c350941a7032ffbf20dca7fecd359d2c0e4c0cb49b2d3c7956728`.

The aggregate replacements are operand-text-match, ratio-percent,
narrative-context, percent-point-difference, percent-point-coercion,
direct-grounding, and both desired-consolidation expectations:

- `85dbeeae58a7b7325a7dce83d9f707167f23a9395692ebab4ebd0c0c3016e7b2`
  to `c6c3cb1b7867d8c409feba7ad3db95496e683fc45540d91bef22f7b0ab58b230`;
- `04f19fd033c6ffe036bbce3a99a88b7c8e162646c01471bd41f2cc40f7de6ae4`
  to `702834d5fc989a5ed74bb39ac139afe8d904ae34c775a8105882dd7e897bcd28`;
- `5e42f1a40f8ff9dced1b903510af8a10bf9327217d52b12ad78ce0ec808c0957`
  to `45d1fc8fae3730e6a33740b931673f8ee1aad939e9149495da766d5229195286`;
- `40be8d4fda403750cfc3b7e6545ae4f5e55a8e809e9c95cea17ac2d41f7e7b32`
  to `95d60340026d113ce57a6893d1405be89414cbb338816ef5a076c5b51ff96b73`;
- `a5308e1856ef1f3e82e7a7994c05c6ca375fd19c2278ad99c98fa3400978e52c`
  to `a01ac156957d31271d60112110b034c8c49829d45853977e8c88cebd39878a3a`;
- `d64ad556454992c68bd9c9dbb4b30954603efbbe53b1f922d54254fd8237beac`
  to `fbf5738defada6bf3b449ffb81b37d454a221730873e3aab0eeedabc66a072af`;
- both
  `2b95b243d13d54d57c5f493d0b59eb9aedcb9bc8621d16a5d3720ab0ef7cbb6b`
  expectations to
  `10e79651281280798e32712626b7ba1526be97ea8e1b01b401100397c6f1afeb`.

Add no test method and weaken no assertion. Projected source/tests/whole
transforms are `+28/-28`, `+61/-61`, and `+89/-89` across exactly four
source and seven test files. The exact temporary diff SHA-256 is
`7311e33650e0467a58bb150b7cb0f3127385d48eaa6c5a85d1e59e9cd42e57d3`.
The projected direct behavior test passed 1/1, three external/public-owner
identity checks and seven fingerprint-specific structure tests passed, and the
affected graph-helper/operand-resolution/dependency-projection/aggregate-
subtask-projection/calculation-execution/task-artifact/operation-contract/
import-side-effects/lookup-recovery/aggregate-rank/semantic-numeric-plan set
passed 1,084/1,084 in 253.268 seconds. Audit 217, pycompile 11/11, retired
selected refs zero, `git diff --check`, and unchanged acyclic 48/203 DAG at
`e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`
also passed. The projection was restored cleanly. Full discovery 2,143/2,143
remains the implementation gate. Benchmark refresh and remote CI remain
**NOT RUN**. This name-only visibility change would prove no behavior,
answer-quality, ranking, performance, benchmark, schedule, ledger, or Phase 3
completion claim.

Keep `_operand_row_matches_requirement`, `evidence_items_by_id`, all caller
bodies, operand/evidence/dependency orchestration, graph state, trace/artifact
mutation, and final sequencing outside this batch. Add no body move, alias,
wrapper, fallback, vocabulary, trace field, or new exception boundary.

## Completed Evidence-Item Index Public API

Commit `a7c02de` renamed only the exact 8-line
`financial_operand_resolution._evidence_items_by_id(...)` definition in place
to public `evidence_items_by_id(...)` and updated its four owner-local calls,
two imports/eleven external calls, and 57 exact test expectations. The
signature, ordered-comprehension evaluation, blank-ID filtering, repeated
retained-ID normalization, key-before-shallow-copy order, duplicate last-value
replacement, caller placement, physical line counts, and orchestration remain
unchanged. Source/tests/whole commit transforms are `+18/-18`, `+56/-56`,
and `+74/-74`; the committed diff SHA-256 is
`8c85749a8ef2e97e7c043211f3d0ff11d8907bc6f66323d487da33638541162f`.
Direct behavior 1/1, two public-owner identities, six structure fingerprints
in 38.921 seconds, focused 1,004/1,004 in 253.742 seconds, audit 217, pycompile
7/7, retired selected refs zero, exact public records 34, owner public/private
65/26, unchanged acyclic 48/203 DAG, and full 2,143/2,143 in 292.697 seconds
passed under `uv run --with-requirements requirements.txt`. Benchmark refresh
and remote CI were **NOT RUN**. This name-only milestone establishes no
behavior, quality, performance, benchmark, schedule, ledger, or Phase 3
completion claim.

## Completed Ratio Operand Same-Slot Predicate Public API

Commit `b5ec9ae` renamed only the exact 13-line
`financial_operand_resolution._ratio_operand_rows_collapse_to_same_slot(...)`
definition in place to public `ratio_operand_rows_collapse_to_same_slot(...)`
and updated its three imports/ten calls and 53 exact test expectations. The
signature, body, group-construction/copy semantics, caller placement, physical
line counts, and orchestration remain unchanged. Source/tests/whole commit
transforms are `+14/-14`, `+53/-53`, and `+67/-67`; the committed diff SHA-256
is `377f47657a869cc9933945009f56ef4e78ee98fbdd1cf6dcaaf81a6e43c3a495`.
Direct behavior and six structure tests passed 7/7 in 38.752 seconds, three
public-owner identities passed, and focused 1,004/1,004 in 255.994 seconds,
audit 217, pycompile 9/9, retired selected refs zero, exact public records 26,
owner public/private 64/27, unchanged acyclic 48/203 DAG, and full
2,143/2,143 in 259.261 seconds passed under
`uv run --with-requirements requirements.txt`. An earlier focused command used
two nonexistent module names; its two loader errors are a command-selection
failure, not a code failure, and are excluded from pass counts. Benchmark
refresh and remote CI were **NOT RUN**. This name-only milestone establishes no
behavior, quality, performance, benchmark, schedule, ledger, or Phase 3
completion claim.

## Completed Operand-Slot Evidence-Surface Predicate Public API

Commit `3198927` renamed only the exact 53-line
`financial_operand_resolution._operand_slot_has_evidence_surface_match(...)`
definition in place to public `operand_slot_has_evidence_surface_match(...)`
and updated its graph import/six calls and 39 exact test expectations. The
signature, body, matched-line/evidence surface semantics, caller placement,
physical line counts, and graph orchestration remain unchanged. Source/tests/
whole commit transforms are `+8/-8`, `+39/-39`, and `+47/-47`; the committed
diff SHA-256 is
`8460f0be379113b651f409164b7fda8cb859d94b0c3c5481ce24d40e073c945e`.
Direct behavior 1/1, graph/public-owner identity, focused 911/911 in 189.724
seconds, audit 217, pycompile 4/4, retired selected refs zero, exact public
records 12, owner public/private 63/28, unchanged acyclic 48/203 DAG, and full
2,143/2,143 in 241.129 seconds passed under
`uv run --with-requirements requirements.txt`. Benchmark refresh and remote CI
were **NOT RUN**. This name-only milestone establishes no behavior, quality,
performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Required-Surface Operand-Row Filter Public API

Commit `03da7b8` renamed only the exact 21-line
`financial_operand_resolution._filter_operand_rows_by_required_surface_contract(...)`
definition in place to public
`filter_operand_rows_by_required_surface_contract(...)` and updated its graph
import/two calls and 39 exact test expectations. The signature, body, early-
return identity, evidence indexing, ordered filtering, lazy matching, caller
placement, physical line counts, and graph orchestration remain unchanged.
Source/tests/whole commit transforms are `+4/-4`, `+39/-39`, and `+43/-43`;
the committed diff SHA-256 is
`9050fa7476700f2041db5a1fedfefbb55ca41315c447c1d98b4fa80ebecb543c`.
Direct behavior 1/1, graph/public-owner identity, focused 911/911 in 308.132
seconds, audit 217, pycompile 6/6, retired selected refs zero, exact public
records 13, owner public/private 62/29, unchanged acyclic 48/203 DAG, and full
2,143/2,143 in 350.243 seconds passed under
`uv run --with-requirements requirements.txt`. Benchmark refresh and remote CI
were **NOT RUN**. This name-only milestone establishes no behavior, quality,
performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Evidence-Surface Segment-Label Predicate Public API

Commit `5bff185` renamed only the exact 31-line
`financial_operand_resolution._evidence_surface_contains_segment_label(...)`
definition in place to public `evidence_surface_contains_segment_label(...)`
and updated its owner-local call, graph import/call, and 38 exact test
expectations. The signature, body, variant/policy/regex semantics, caller
placement, physical line counts, and graph orchestration remain unchanged.
Source/tests/whole commit transforms are `+4/-4`, `+38/-38`, and `+42/-42`;
the committed diff SHA-256 is
`5dcaeb4a7ac08c85a27ced40cfc5159542e1a48a562d489bfb79bab80b9c8e85`.
Direct behavior 1/1 with five internal cases, graph/public-owner identity,
focused 879/879 in 276.791 seconds, audit 217, pycompile 4/4, retired selected
refs zero, exact public records 11, owner public/private 61/30, unchanged
acyclic 48/203 DAG, and full 2,143/2,143 in 326.614 seconds passed under
`uv run --with-requirements requirements.txt`. The earlier bare `uv run`
focused attempt was invalid because runtime dependencies were absent; it is not
a code failure and is excluded from the pass count. Benchmark refresh and
remote CI were **NOT RUN**. This name-only milestone establishes no behavior,
quality, performance, benchmark, schedule, ledger, or Phase 3 completion claim.

The preserved pre-implementation contract follows. It characterized the batch
that `5bff185` has now completed.

Rename only the exact 31-line
`src.agent.financial_operand_resolution._evidence_surface_contains_segment_label(
segment_label: str, surfaces: Sequence[Any]) -> bool` definition in place to
public `evidence_surface_contains_segment_label(...)`. Update its owner-local
call in `_operand_row_satisfies_required_surface_contract`, its import and call
in `financial_graph_calculation.py`, and seven existing exact test name/caller
references. Do not move the body, add an alias or wrapper, rename adjacent
surface helpers, or broaden candidate alignment, operand resolution, evidence
selection, or graph orchestration.

The definition remains at lines 1626-1656 with two positional arguments, no
defaults or keyword-only arguments, and a `bool` return. Preserve ordered
`surface_match_variants(segment_label)` projection; per-variant edge-punctuation
replacement through `re.sub(r"^\W+|\W+$", " ", variant)` followed by
`_normalise_spaces`; truthy ordered dedupe through `dict.fromkeys`; the empty-
variant early `True`; shallow `dict(STRUCTURED_CELL_AFFINITY_POLICY)` copying;
ordered, duplicate-preserving `entity_surface_drop_terms` normalization;
direct surface iteration; `str(surface_value or "")` normalization and blank
skip; case-sensitive escaped word-boundary matching; segment-plus-scope matching
through exact `\s*`; early `True` returns, final `False`, input immutability,
evaluation order, and every uncaught error. The name-normalized definition AST
SHA-256 is
`ff91e27eb3e656a49e3e7f829f76603467e9eec0ae281427b0bb0272205d8b37`;
the exact body-source SHA-256 is
`5a97f20c87ab8dce966863512ecd4cce63518b6c60d45c92820076049d7f2705`.

The owner-local call remains in
`_operand_row_satisfies_required_surface_contract` at line 1699 with positional
`segment_label, segment_surfaces` under negation. The graph call remains in
`_align_ratio_operands_with_sibling_table_context` at line 7558 with positional
`segment_label, candidate_segment_surfaces` under negation. Both have no
keywords and caller `try` depth zero. Their callee-normalized combined
call-record SHA-256 is
`eafc75a21e56ec515578d76c1be7d34621ecb0a513a2eb99fc55555dea9eb6c6`.
The caller-body hashes change only for callee spelling:

- graph ratio-operand alignment:
  `a4026ae1da460a6217d2b38ac7925cca664b886d35eecda9d12728910162d6e9`
  to `167aa22aca021aab8f42bdc57d6b574496c973e49fe56c74094184dc31b50d73`;
- owner required-surface contract:
  `1d7e55158faf8cfc1642dc5e4a61c881c94cbb06d3c8321c63a8d6b8863050c7`
  to `8589bae67df35b3ad342d50de1c14da5beff65bba398074a4252ede239e0cf3e`.

Owner/graph physical line counts remain 4,816/13,464; dependency remains
3,419. Current production scope is one definition, one owner-local call, one
external import, and one external call. Tests contain seven selected exact
name/caller references. The future public name has no pre-existing exact
source/test definition, import, call, patch, attribute, string constant,
wildcard/`__all__`, reviewed introspection consumer, or collision. After the
rename selected private refs must finish zero, the graph binding must be
identical to the public owner, exact public records must total 11, and owner
public/private counts must move exactly 60/31 to 61/30.

Update exactly 38 existing test expectations: seven selected direct/caller
names; 27 current owner counts from 60/31 to 61/30; two derived counts from
59/31 to 60/30; one owner/class tuple from 60/31/19 to 61/30/19; and the
operand-text-match aggregate caller-map hash from
`669ee29a37ca47066d4b54a503136b429e7f3d7afd620754085c5c9059fe784d`
to `194440e30de0fd64151b9fbf608255efab3e6eef18daea7879f2a6345b39b7b7`.
No raw caller-body hash expectation changes. Add no test method and weaken no
assertion.

Projected source/tests/whole transforms are `+4/-4`, `+38/-38`, and
`+42/-42` across exactly two source and two test files. The exact temporary
diff SHA-256 is
`5dcaeb4a7ac08c85a27ced40cfc5159542e1a48a562d489bfb79bab80b9c8e85`.
The projected public direct behavior test passed 1/1 with five internal cases,
the graph/public-owner identity check passed, and the temporary projection
passed focused graph-helper/operand-resolution/dependency-projection/aggregate-
subtask-projection/calculation-execution/task-artifact/operation-contract/
import-side-effects 879/879 in 288.061 seconds, audit 217, pycompile 4/4,
retired selected refs zero, `git diff --check`, and unchanged acyclic 48/203
DAG parity. At characterization time full discovery 2,143/2,143 remained the
implementation gate; commit `5bff185` later satisfied it in 326.614 seconds as
recorded above. Benchmark refresh and remote CI remain **NOT RUN**. This name-
only visibility change proves no behavior, answer-quality, ranking,
performance, benchmark, schedule, ledger, or Phase 3 completion claim.

Keep `surface_match_variants`, `_normalise_spaces`, policy data,
`_operand_row_satisfies_required_surface_contract` body, ratio-operand
alignment logic, all other evidence indexing/resolution, graph state,
trace/artifact mutation, and final sequencing outside this batch. Add no body
move, alias, wrapper, fallback, vocabulary, trace field, or new exception
boundary.

## Completed Period-Comparison Collapse Predicate Public API

Commit `0b2b66d` renamed only the exact 13-line
`financial_operand_resolution._period_comparison_operand_rows_collapse_to_same_slot(...)`
definition in place to public
`period_comparison_operand_rows_collapse_to_same_slot(...)` and updated its two
imports, six direct production calls, and 46 exact test expectations. The
signature, body, role-grouping/collapse semantics, caller placement, physical
line counts, and dependency/calculation orchestration remain unchanged.
Source/tests/whole commit transforms are `+9/-9`, `+46/-46`, and `+55/-55`;
the committed diff SHA-256 is
`63feeb89244685251b5ba7a62302828a91219cbb9c74af0cdf5bec8d1c5ddb2d`.
Direct behavior 1/1, both public-owner identity checks, focused 879/879 in
265.674 seconds, audit 217, pycompile 5/5, retired selected refs zero, exact
public records 13, owner public/private 60/31, unchanged acyclic 48/203 DAG,
and full 2,143/2,143 in 319.738 seconds passed. Benchmark refresh and remote
CI were **NOT RUN**. This name-only milestone establishes no behavior,
quality, performance, benchmark, schedule, ledger, or Phase 3 completion
claim.

The preserved pre-implementation contract follows. It characterized the batch
that `0b2b66d` has now completed.

Rename only the exact 13-line
`src.agent.financial_operand_resolution._period_comparison_operand_rows_collapse_to_same_slot(
rows: List[Dict[str, Any]]) -> bool` definition in place to public
`period_comparison_operand_rows_collapse_to_same_slot(...)`. Update its two
imports and six direct calls across `financial_dependency_projection.py` and
`financial_graph_calculation.py`, plus the existing direct test import and
three calls. Do not move the body, add an alias or wrapper, rename the ratio
collapse helper or shared group predicate, or broaden dependency precedence,
period-pair construction, result repair, or calculation orchestration.

The definition remains at lines 2044-2056 with exactly one positional list
argument, no defaults or keyword-only arguments, and a `bool` return. Preserve
the single return into `_operand_row_groups_collapse_to_same_slot`; fresh outer
and inner lists; two independent `rows or []` iterations; per-row `(row or {})`
fallback; `matched_operand_role` lookup, raw truthiness, exact `str(...)`, and
`_normalise_spaces(...)`; case-sensitive exact role membership; current group
roles `current_period`/`minuend`; prior group roles
`prior_period`/`subtrahend`; ordered selection; shallow `dict(row)` copies only
for selected rows; ignored unmatched rows; callee-owned collapse semantics;
input/nested-object immutability; and every uncaught error. The
name-normalized definition AST SHA-256 is
`d48a08da237d822799926916a0c3147da9182f4746322ce2e252eb3b76465548`;
the exact body-source SHA-256 is
`60a7ff7c915c22320de4eeb31b779013da85cc0dd2bca08b70f65ff8dc7eeda0`.

The dependency calls remain in `resolve_main_operand_precedence` at line 1689
with positional `direct_rows` under negation and in
`resolve_late_dependency_remerge` at line 1890 with positional
`active_direct_context_rows` under negation. The graph calls remain in
`_has_complete_direct_period_context_operands` at line 2157 with positional
`rows`, `_build_period_comparison_operands_from_table_label_context` at line
7859 with positional `rows`, `_extract_calculation_operands` at line 9237 with
positional `direct_structured_rows` under negation, and
`_repair_stale_calculation_result_from_operands` at line 10929 with positional
`operands` inside the existing operation-family conjunction. All six have no
keywords and caller `try` depth zero. Their callee-normalized combined
call-record SHA-256 is
`69d583e1b272d93e6936d0047cf2477734a360483f8973821d7b1226f7899576`.
The six caller-body hashes change only for callee spelling:

- dependency main precedence:
  `4dff58f02f80c8904c71e9c9a40e08a18fecfc3eb0b8ec7897d74cffb463e065`
  to `144d5ea5ded6bc29ea34df4aff50fbba4b39b33ee0f91553c248239a08089131`;
- dependency late remerge:
  `b47724caf75ffdceeb1e51ef177047461a649152ef68c3df3404191970b3d774`
  to `f6262783f4ec98767a281769959c36de07ebcaf45a333fc28887235c3d29e9d2`;
- graph direct-period predicate:
  `9bc0a0d76dd87fddc0adf5b7d6f98c86380d14f9eb2cc8bd673fbb2316f0f885`
  to `138445b4767669215c629c712e4e991e048579b74b4b4eb4c5b55dc1d10f89ff`;
- graph period-comparison builder:
  `92d6a14434df6de4679e37e7b07e19bb99f089ffdb6430a07491d74bd65c19e9`
  to `fdd9dcac55f8418ae0ed7f0f2223d6b47718b00c0ef2544dff391777cc85dbf8`;
- graph operand extraction:
  `572936a307d17648acd61f292cf72f567925579ade4c62b03833bc2b847439d5`
  to `6d90e15c2d17991755550fac996e45d3fd08eff4f5f7ba817b9f503a4b6b9fc9`;
- graph stale-result repair:
  `4fc12f8e88950c298962a13a60c10ca29e618fbe03f5223316e70a6732343502`
  to `30b0e170a6eaf66e9835f2bdf3d1ebb9be16914cb5ab88e83f69d675552afba4`.

Owner/dependency/graph physical line counts remain 4,816/3,419/13,464.
Current production scope is one definition, two external imports, six direct
calls, and zero owner-local calls. Tests contain one direct import and three
direct calls. The future public name has no pre-existing exact source/test
definition, import, call, patch, attribute, string constant, wildcard/
`__all__`, reviewed introspection consumer, or collision. After the rename,
selected private refs must finish zero, both caller bindings must be identical
to the public owner, exact public records must total 13, and owner public/
private counts must move exactly 59/32 to 60/31.

Update exactly 46 existing test expectations: four direct names; 27 current
owner counts from 59/32 to 60/31; two derived counts from 58/32 to 59/31; one
owner/class tuple from 59/32/19 to 60/31/19; four copies of the graph-
extraction caller hash above; one period-comparison-builder caller hash; and
seven aggregate caller-map hashes. The aggregate hashes change from
operand-text-match `bf117326bbbbbcd736c2c689962ba08ff0686f00a119ebe0a80e12e72757f99e`
to `669ee29a37ca47066d4b54a503136b429e7f3d7afd620754085c5c9059fe784d`,
ratio `239a1e1ffe97741c56eabace69a4dfb56dabbcb94c0a8c8f62ef78eea01ab78a`
to `1282a17328f8f2d0c8a69ab3718c3ad84f47d009a3ecad2b0ed2e2afb968ed17`,
narrative `fe06e2d3d20b1ca21c28dc0eef8c387418e133cc253cf3479d2dec2dcf3cf2ee`
to `3957109d9479409bb1ef5145e2170c129a7577f5b9935b7062c06c5828d27a9b`,
percent-point `bdc38b513f4b7e016077484962cc875539bcdae2a7a05821ef845e939eb79691`
to `6a8f69674a105d30e6675d01745a106a3726d147a3d0f7e0fabec402d426978e`,
direct-grounding `9dd76b103df6b790a1ab1485a816e535489d7594eed7a02aa57470075c7cfd85`
to `14c778675708be6e42981dd0451cb1a7e3bf9dab112d60a13218fb032083db58`,
and both desired-consolidation copies from
`5c5b8f1f890fe540a59413440575e37c357745cbd65b98e045ca33a9dbc9a03d`
to `56bdf9bd6df18f5d75cd17391e041d73c7a02c87468d684af6c272e4dab76cf5`.
Add no test method and weaken no assertion.

Projected source/tests/whole transforms are `+9/-9`, `+46/-46`, and
`+55/-55` across exactly three source and two test files. The exact temporary
diff SHA-256 is
`63feeb89244685251b5ba7a62302828a91219cbb9c74af0cdf5bec8d1c5ddb2d`.
The projected public direct behavior test passed 1/1, both public-owner
identity checks passed, and the temporary projection passed focused graph-
helper/operand-resolution/dependency-projection/aggregate-subtask-projection/
calculation-execution/task-artifact/operation-contract/import-side-effects
879/879 in 217.993 seconds, audit 217, pycompile 5/5, retired selected refs
zero, `git diff --check`, and unchanged acyclic 48/203 DAG parity at
`e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
At characterization time full discovery 2,143/2,143 remained the implementation
gate; commit `0b2b66d` later satisfied it in 319.738 seconds as recorded above.
Benchmark refresh and remote CI remain **NOT RUN**. This name-only visibility
change proves no behavior, answer-quality, ranking, performance, benchmark,
schedule, ledger, or Phase 3 completion claim.

Keep `_normalise_spaces`, `_operand_row_groups_collapse_to_same_slot`,
`_ratio_operand_rows_collapse_to_same_slot`, `_missing_required_operands`,
evidence indexing/resolution, public table-context/display-unit/conflict
helpers, dependency coverage/conflict/override policy, period-pair building,
stale-result repair logic, graph state, evidence, trace/artifact mutation, and
final sequencing outside this batch. Add no body move, alias, wrapper,
fallback, trace field, or new exception boundary.

## Completed Single Table-Context Predicate Public API

Commit `c1d3b8c` renamed only the exact 11-line
`financial_operand_resolution._operand_rows_have_single_table_context(...)`
definition in place to public `operand_rows_have_single_table_context(...)`
and updated its two imports, four direct production calls, and 45 exact test
expectations. The signature, body, fallback/normalization/dedupe semantics,
caller placement, physical line counts, and dependency/calculation
orchestration remain unchanged. Source/tests/whole commit transforms are
`+7/-7`, `+45/-45`, and `+52/-52`; the committed diff SHA-256 is
`9733468d7282cb15279adcf01dadc30bd4e07329abff21cd611a22350023c668`.
Direct behavior 1/1, both public-owner identity checks, focused 879/879 in
189.090 seconds, audit 217, pycompile 5/5, retired selected refs zero, exact
public records 12, owner public/private 59/32, unchanged acyclic 48/203 DAG,
and full 2,143/2,143 in 221.803 seconds passed. Benchmark refresh and remote
CI were **NOT RUN**. This name-only milestone establishes no behavior,
quality, performance, benchmark, schedule, ledger, or Phase 3 completion
claim.

The preserved pre-implementation contract follows. It characterized the batch
that `c1d3b8c` has now completed.

The characterized batch renamed only the exact 11-line
`src.agent.financial_operand_resolution._operand_rows_have_single_table_context(
rows: List[Dict[str, Any]]) -> bool` definition in place to public
`operand_rows_have_single_table_context(...)`. Update its two imports and four
direct calls across `financial_dependency_projection.py` and
`financial_graph_calculation.py`, plus the existing direct test import and four
calls. Do not move the body, add an alias or wrapper, rename an adjacent helper,
or broaden dependency precedence or calculation orchestration.

The definition remains at lines 1943-1953 with exactly one positional list
argument, no defaults or keyword-only arguments, and a `bool` return. Preserve
the fresh set comprehension; exact per-row fallback order
`table_source_id` then `source_table_id` then `source_anchor` then `""`; raw
truthiness between fallback fields; exact `str(...)` conversion; filter-first
evaluation; repeated fallback/string/normalization evaluation for retained
rows; single evaluation for rejected blank rows; whitespace-empty filtering;
case preservation; exact-string set dedupe; `len(contexts) == 1`; input and
nested-row immutability; and every uncaught error. The name-normalized
definition AST SHA-256 is
`0bb5e3950243066b194caa42d4cf75c72d1a3c9e48ac1029a379ca2156f9af37`;
the exact body-source SHA-256 is
`64d925632785c2326a8570a519ef1af5fdbdfa6aedb0a50a5267c93d717818f3`.

The dependency calls remain in `resolve_main_operand_precedence` at line 1687
with positional `direct_rows` and in `resolve_late_dependency_remerge` at line
1884 with positional `active_direct_context_rows`. The graph calls remain in
`_has_complete_direct_period_context_operands` at line 2155 with positional
`rows` under the existing negation, and in `_extract_calculation_operands` at
line 9235 with positional `direct_structured_rows`. All four have no keywords
and caller `try` depth zero. Their callee-normalized combined call-record
SHA-256 is
`650c354880e8fdd004d70afc74d3137af2828fa4ca18404a9e6b1c4ec2bbf428`.
The four caller-body hashes change only for callee spelling:

- dependency main precedence:
  `27bde775c46b25711f2a63f6ec1645232b5c7d3092cab325b0902464d2b40926`
  to `4dff58f02f80c8904c71e9c9a40e08a18fecfc3eb0b8ec7897d74cffb463e065`;
- dependency late remerge:
  `dd64ab0ac477b8d7b6fe963b162d3d907bc1b15b6a7a34bc2f323506cc3a50dd`
  to `b47724caf75ffdceeb1e51ef177047461a649152ef68c3df3404191970b3d774`;
- graph direct-period predicate:
  `fbfe8ec9cb7e52a1111b9cb3628322b558adf88eee0da45f2f03917a698cc14a`
  to `9bc0a0d76dd87fddc0adf5b7d6f98c86380d14f9eb2cc8bd673fbb2316f0f885`;
- graph extraction:
  `4ed153c6ba332ae278786367a419359f74aed1d86197b93cd2bdc3bafa0a4c73`
  to `572936a307d17648acd61f292cf72f567925579ade4c62b03833bc2b847439d5`.

Owner/dependency/graph physical line counts remain 4,816/3,419/13,464.
Current production scope is one definition, two external imports, four direct
calls, and zero owner-local calls. Tests contain one direct import and four
direct calls. The future public name has no pre-existing exact source/test
definition, import, call, patch, attribute, string constant, wildcard/`__all__`,
reviewed introspection consumer, or collision. After the rename selected private
refs must finish zero, both caller bindings must be identical to the public
owner, exact public records must total 12, and owner public/private counts must
move exactly 58/33 to 59/32.

Update exactly 45 existing test expectations: five direct names; 27 current
owner counts from 58/33 to 59/32; two derived counts from 57/33 to 58/32; one
owner/class tuple from 58/33/19 to 59/32/19; four copies of the graph-extraction
caller hash above; and six aggregate caller-map hashes. The aggregate hashes
change from ratio
`cd65b6aeb7264111c960a946888feee46790a7458ed9cc4a7d0517d4ec46370a`
to `239a1e1ffe97741c56eabace69a4dfb56dabbcb94c0a8c8f62ef78eea01ab78a`,
narrative
`31953638d15db09d9df0c8263576cd52aecb6f9b4ad604c13bb512fc1fd9a2f5`
to `fe06e2d3d20b1ca21c28dc0eef8c387418e133cc253cf3479d2dec2dcf3cf2ee`,
percent-point
`c4df271495d106f116f5e9575d265ff7f58a07bed22d0aac0a66bb848ab0a5a1`
to `bdc38b513f4b7e016077484962cc875539bcdae2a7a05821ef845e939eb79691`,
direct-grounding
`64e2a49e996110e2fe654302376eaa276c71a9961f0b367f2103c21a2d358ec4`
to `9dd76b103df6b790a1ab1485a816e535489d7594eed7a02aa57470075c7cfd85`,
and both desired-consolidation copies from
`b4109b5d882bd2932b32a3ca669d6cf317ae0227dc7906b731be356c068a7096`
to `5c5b8f1f890fe540a59413440575e37c357745cbd65b98e045ca33a9dbc9a03d`.
Add no test method and weaken no assertion.

Projected source/tests/whole transforms are `+7/-7`, `+45/-45`, and
`+52/-52` across exactly three source and two test files. The exact temporary
diff SHA-256 is
`9733468d7282cb15279adcf01dadc30bd4e07329abff21cd611a22350023c668`.
Current-private and projected-public identity/behavior probes each passed
10/10. The temporary projection also passed focused graph-helper/operand-
resolution/dependency-projection/aggregate-subtask-projection/calculation-
execution/task-artifact/operation-contract/import-side-effects tests 879/879
in 202.661 seconds, audit 217, pycompile 5/5, retired selected refs zero,
`git diff --check`, and unchanged acyclic 48/203 DAG parity at
`e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
At characterization time full discovery 2,143/2,143 remained the
implementation gate; commit `c1d3b8c` later satisfied it in 221.803 seconds as
recorded above. Benchmark refresh and remote CI remain **NOT RUN**. This
name-only visibility change proves no behavior, answer-quality, ranking,
performance, benchmark, schedule, ledger, or Phase 3 completion claim.

Keep `_normalise_spaces`, public `operand_row_display_unit_set`, public
`operand_rows_conflict_by_required_role`, `_missing_required_operands`, both
collapse helpers, all other operand-resolution helpers, dependency coverage/
conflict/override policy, direct-target evidence selection, graph state,
evidence, trace/artifact mutation, and final sequencing outside this batch.
Add no body move, alias, wrapper, fallback, trace field, or new exception
boundary.

## Completed Structured Reconciliation-ID Public API

Commit `48130ab` renamed only the exact 11-line
`financial_operand_resolution._canonical_structured_reconciliation_id(...)`
definition in place to public `canonical_structured_reconciliation_id(...)` and
updated its two owner-local calls, one graph-calculation import/call, and 32
exact test expectations. The signature, body, prefix/marker/raw-row identity
semantics, caller placement, physical line counts, and reconciliation/
calculation orchestration remain unchanged. Selected private refs finish zero,
exact public records total seven, and owner public/private counts are 58/33.

Production source, tests, and the whole commit are `+5/-5`, `+32/-32`, and
`+37/-37` across two source and two test files. The committed diff SHA-256 is
`3ef507bd750b6725df6db06c12a51cf21778797b2a1d81510c48f3efb854ab7f`.
Public identity/behavior 10/10, focused graph-helper/operand-resolution/
aggregate-subtask-projection/calculation-execution/task-artifact/operation-
contract/import tests 804/804 in 209.375 seconds, audit 217, pycompile 4/4,
unchanged acyclic 48/203 DAG, full discovery 2,143/2,143 in 231.057 seconds,
artifact hygiene, and diff checks passed. Benchmark refresh and remote CI were
**NOT RUN**. This name-only visibility milestone establishes no behavior,
quality, performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Operand Display-Unit Set Public API

Commit `6aeb0d1` renamed only the exact six-line
`financial_operand_resolution._operand_row_display_unit_set(...)` definition
in place to public `operand_row_display_unit_set(...)` and updated its one
dependency-projection import, two assignment calls, and 32 exact test
expectations. The signature, body, raw-unit-only normalization, case-preserving
dedupe, caller placement, physical line counts, and dependency-precedence
orchestration remain unchanged. Selected private refs finish zero and owner
public/private counts are 57/34.

Production source, tests, and the whole commit are `+4/-4`, `+32/-32`, and
`+36/-36` across two source and two test files. The committed diff SHA-256 is
`c274aeabfb62d913064ef53ca5cd945e975fbd1629f30202c0fe19db8509afe3`.
Public identity/behavior 10/10, focused graph-helper/operand-resolution/
dependency-projection/operation-contract/import tests 695/695 in 186.694
seconds, audit 217, pycompile 4/4, unchanged acyclic 48/203 DAG, full discovery
2,143/2,143 in 229.386 seconds, artifact hygiene, and diff checks passed.
Benchmark refresh and remote CI were **NOT RUN**. This name-only visibility
milestone establishes no behavior, quality, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Required-Role Operand-Conflict Public API

Commit `dce0d63` renamed only the exact 19-line
`financial_operand_resolution._operand_rows_conflict_by_required_role(...)`
definition in place to public `operand_rows_conflict_by_required_role(...)` and
updated its one dependency-projection import/call plus 33 exact test
expectations. The signature, body, role precedence/normalization, callback
identity/order, early return, caller placement, physical line counts, and
dependency-precedence orchestration remain unchanged. Selected private refs
finish zero and owner public/private counts are 56/35.

Production source, tests, and the whole commit are `+3/-3`, `+33/-33`, and
`+36/-36` across two source and two test files. The committed diff SHA-256 is
`49da7e5486a11db12a9561b9e5592bbfda82411ac96d2c9025f2a0679afdbb03`.
Public identity/behavior 10/10, focused graph-helper/operand-resolution/
dependency-projection/operation-contract/import tests 695/695 in 254.222
seconds, audit 217, pycompile 4/4, unchanged acyclic 48/203 DAG, full discovery
2,143/2,143 in 316.854 seconds, artifact hygiene, and diff checks passed.
Benchmark refresh and remote CI were **NOT RUN**. This name-only visibility
milestone establishes no behavior, quality, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Structured Reconciliation-Reference Public API

Commit `c9a315f` renamed only the exact 17-line
`financial_operand_resolution._canonicalize_structured_operand_reconciliation_refs(...)`
definition in place to public
`canonicalize_structured_operand_reconciliation_refs(...)` and updated its one
graph-calculation import/call plus 42 exact test expectations. The signature,
body, shallow-copy behavior, sibling-helper order, falsey preservation, ordered
dedupe, caller placement, physical line counts, and calculation orchestration
remain unchanged. Selected private refs finish zero and owner public/private
counts are 55/36.

Production source, tests, and the whole commit are `+3/-3`, `+42/-42`, and
`+45/-45` across two source and two test files. The committed diff SHA-256 is
`91d6ee8a832e27c2ba2afb049559ab33ce4c5e95ce5653bf43bdf3ed248e79a4`.
Public identity/behavior 10/10, focused graph-helper/operand-resolution/
calculation-execution/operation-contract/import tests 665/665 in 182.182
seconds, audit 217, pycompile 4/4, unchanged acyclic 48/203 DAG, full discovery
2,143/2,143 in 235.494 seconds, artifact hygiene, and diff checks passed.
Benchmark refresh and remote CI were **NOT RUN**. This name-only visibility
milestone establishes no behavior, quality, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Retrieval Topic-Hint Public API

Commit `31e4c26` renamed only the exact nine-line
`financial_retrieval_hints._retrieval_hint_from_topic(...)` definition in place
to public `retrieval_hint_from_topic(...)` and updated its one import/call in
`financial_retrieval_pipeline.py` plus nine exact test expectations. The
signature, body,
policy-term ordering, lazy ontology access, ordered dedupe, caller arguments and
placement, physical line counts, and retrieval orchestration remain unchanged.
Selected private refs finish zero and owner public/private counts are 7/7.

Production source, tests, and the whole commit are `+3/-3`, `+9/-9`, and
`+12/-12` across two source and two test files. The committed diff SHA-256 is
`e2c2cebe14cef74c92d19cff9b5c7445c3aaa6e74bd0e44f11baa583dc8f6942`.
Public identity/behavior 10/10, focused graph-helper/retrieval-hint/retrieval-
scope/retrieval-pipeline/import tests 343/343 in 180.597 seconds, audit 217,
pycompile 4/4, unchanged acyclic 48/203 DAG, full discovery 2,143/2,143 in
235.375 seconds, artifact hygiene, and diff checks passed. Benchmark refresh
and remote CI were **NOT RUN**. This name-only visibility milestone establishes
no behavior, quality, performance, benchmark, schedule, ledger, or Phase 3
completion claim.

## Completed Retrieval Supplement-Section Public API

Commit `67bc02e` renamed only the exact six-line
`financial_retrieval_hints._supplement_section_terms_for_query(...)` definition
in place to public `supplement_section_terms_for_query(...)` and updated its one
reconciliation import/call plus five exact CURRENT-SOURCE expectations. The
signature, body, fresh-list/intent-gate/lazy-ontology/ordered-dedupe behavior,
caller ordering, physical line counts, and adjacent helpers remain unchanged.
Selected private refs finish zero and owner public/private counts are 6/8.

Production source, tests, and the whole commit are `+3/-3`, `+5/-5`, and
`+8/-8` across two source and two test files. The committed diff SHA-256 is
`a2d27efd562dd2134ea1f0f86a41877a9522811236d59b4d998a2ac99efe774c`.
Public identity/behavior 10/10, focused graph-helper/retrieval-hint/
reconciliation-plan/import tests 365/365 in 200.892 seconds, audit 217,
pycompile 4/4, unchanged acyclic 48/203 DAG, full discovery 2,143/2,143 in
238.281 seconds, artifact hygiene, and diff checks passed. Benchmark refresh
and remote CI were **NOT RUN**. This name-only visibility milestone establishes
no behavior, quality, performance, benchmark, schedule, ledger, or Phase 3
completion claim.

## Completed Retrieval Document-Factory Public API

Commit `f04e774` renamed only the exact two-line
`financial_retrieval_pipeline._make_document(...)` wrapper in place to public
`make_document(...)` and updated its one evidence import plus three direct
calls. The keyword-only signature, exact loader delegation, call expressions
and placement, loader edge, physical line counts, and unrelated storage-local
helpers remain unchanged. Selected private agent refs finish zero.

Production source, tests, and the whole commit are `+5/-5`, `+0/-0`, and
`+5/-5` across two source files. The committed diff SHA-256 is
`87b8eb4bbafb1f461d6671f7753d6de21a607ac038fecbc47ed7d34f532a0d9e`.
Public identity/behavior 4/4, focused graph-helper/text-surface/import tests
339/339 in 203.334 seconds, audit 217, pycompile 2/2, unchanged acyclic 48/203
DAG, full discovery 2,143/2,143 in 271.268 seconds, artifact hygiene, and diff
checks passed. Benchmark refresh and remote CI were **NOT RUN**. This name-only
visibility milestone establishes no behavior, quality, performance, benchmark,
schedule, ledger, or Phase 3 completion claim.

## Completed Graph-Calculation TYPE_CHECKING Import Cleanup

Commit `eea2935` removed only the zero-load, zero-guard `TYPE_CHECKING` entry
from the existing typing import in `financial_graph_calculation.py`. The
physical line, `from __future__ import annotations`, all other source, and the
live `Any`, `Dict`, `List`, `Literal`, `NamedTuple`, `Optional`, and `Sequence`
imports remain unchanged. No test changed.

Production source, tests, and the whole commit are `+1/-1`, `+0/-0`, and
`+1/-1` across one file. The committed diff SHA-256 is
`bbabef4ee357dc074339da22f14fcd998a61c1b335b9e1fd7c3d238fd5880c0a`.
Focused graph-helper/text-surface/import tests passed 339/339 in 169.812
seconds, audit 217, pycompile 1/1, selected consumer and guard zero, unchanged
acyclic 48/203 DAG, full discovery 2,143/2,143 in 214.291 seconds, artifact
hygiene, and diff checks passed. Benchmark refresh and remote CI were **NOT
RUN**. This dead-import-only milestone establishes no behavior, quality,
performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Evidence Operand-Needles Import Cleanup

Commit `5ff7fd2` completed the previously characterized deletion of only the
zero-load `operand_needles` import from `financial_graph_evidence.py`. Its
canonical definition, all 24 source calls (four owner-local and twenty caller
calls), the other eight external importers, the tuple's three live imports, and
all evidence behavior remain unchanged.

Production source is `+0/-1`, tests are `+9/-11`, and the whole commit is
`+9/-12` across exactly two files. Its committed diff SHA-256 is
`62acdb9c825520f15374b801e142afe37882e0896217cbe424ccb8d363619f44`.
Focused graph-helper/text-surface/import tests passed 339/339 in 173.413
seconds, audit 217, pycompile 2/2, selected facade-consumer zero,
`git diff --check`, and the unchanged acyclic 48-module/203-edge DAG passed.
Full discovery passed 2,143/2,143 in 216.116 seconds. Artifact hygiene passed;
benchmark refresh and remote CI were **NOT RUN**. This dead-import-only
milestone establishes no behavior, answer-quality, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Reconciliation-Candidate Import Cleanup

Commit `5de5e23` completed the previously characterized deletion of only
`effective_structured_cell_unit_hint`, `find_reconciliation_match_entry`,
`pair_candidate_period_score`, and `structured_cell_identity` from the
`financial_reconciliation_candidates` import tuple in
`financial_graph_reconciliation.py`. All four canonical owner definitions,
their 2/2/2/4 owner-local calls, the tuple's other four live imports, and all
reconciliation behavior remain unchanged.

Production source is `+0/-4`, tests are `+3/-7`, and the whole commit is
`+3/-11` across exactly three files. Its committed diff SHA-256 is
`133a07f36696c8efd7ac47b5a8459b56198a5293072ef2ef1f29988bdb794e1d`.
Focused graph-helper/reconciliation-candidate/import tests passed 323/323 in
173.754 seconds, audit 217, pycompile 3/3, selected facade-consumer zero,
`git diff --check`, and the unchanged acyclic 48-module/203-edge DAG passed.
Full discovery passed 2,143/2,143 in 235.423 seconds. Artifact hygiene passed;
benchmark refresh and remote CI were **NOT RUN**. This dead-import-only
milestone establishes no behavior, answer-quality, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Graph-Calculation Query-Focus Import Cleanup

Commit `7cdb317` completed the previously characterized deletion of only the
zero-load `query_focus_marker_groups` import from
`financial_graph_calculation.py`. The owner definition, every live call,
`query_focus_markers`, all query-focus behavior, and the separately contracted
`text_has_negative_surface` compatibility identity remain unchanged.

Production source is `-1`, tests are `+7/-7`, and the whole commit is `+7/-8`
across exactly two files. Its committed diff SHA-256 is
`5cfe61d2307cdd4dbcd566e9e504a45cae8008eb1113daa4187feb069b3603b9`.
Focused graph-helper/text-surface/import tests passed 339/339 in 168.331
seconds, audit 217, pycompile 2/2, selected consumer zero, retained
compatibility identity, unchanged acyclic 48/203 DAG, full discovery
2,143/2,143 in 211.992 seconds, artifact hygiene, and diff checks passed.
Benchmark refresh and remote CI were **NOT RUN**. This dead-import-only cleanup
establishes no behavior, quality, performance, benchmark, schedule, ledger, or
Phase 3 completion claim.

## Completed Evidence-Owner Zero-Load Import Cleanup Characterization

The following characterize-only record preceded commit `6d0e21c`. Its deletion
and projected gates are complete; it is retained for audit and is not active or
competing work.

Delete exactly these six zero-load import bindings from
`src/agent/financial_graph_evidence.py` and no other source:

- `classify_report_cache_consumer_candidate` from
  `src.config.report_scoped_cache`;
- `KOREAN_COUNT_UNIT_RE_FRAGMENT`, `METRIC_TOPIC_EXTRACTION_TERMS`,
  `PERIOD_COMPARISON_COUNT_POLICY`, `active_narrative_policies`, and
  `narrative_policy_facets` from `src.config.retrieval_policy`.

Do not delete, move, rename, wrap, or change any imported definition. Preserve
the live copies and calls in `financial_retrieval_pipeline.py`,
`financial_runtime_trace.py`, config, and tests. Keep every other evidence-owner
import, including the similarly named `_active_narrative_policies_for_query(...)`
and `_narrative_policy_facets_for_query(...)` methods and their live policy
dependencies. Add no fallback, compatibility export, `__all__`, or behavior
branch.

All six selected bindings have zero owner `Load` nodes and calls. Repository-
wide source/test analysis finds zero direct import from
`financial_graph_evidence`, module-attribute consumer, or dynamic
`getattr`/`hasattr` consumer for the selected names. The eight exact
`"active_narrative_policies"` test strings patch
`financial_graph_helpers`, not this owner. The selected current/empty binding-
record hashes are
`842dacd35d7991e45be44f6571c9f9c9924699eb6cc9dfb44e5d5c879156131c` /
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.

Physical production scope is one file and exactly six deleted lines. Because
the deletion shifts later absolute line numbers, update exactly nine existing
caller-fingerprint expectations in `tests/test_financial_graph_helpers.py`;
the desired-consolidation caller hash occurs twice, so these are eight unique
old/new pairs. Change no test method, body contract, call record, assertion
strength, or runtime expectation. The fingerprint mapping hash is
`4d6ffde1b5765d0d8c697421f8eb3b6a970d07128b2d2875e17940ff9f57db7f`.
Projected source/test/whole transforms are `+0/-6`, `+9/-9`, and `+9/-15`
across exactly two files. The exact temporary projection diff SHA-256 is
`2f26c4c2be025ddbc7d8c701af0e84707079c17a1934ca82f7a7890dca8d80d3`.

The exact temporary projection passed the affected graph-helper, text-surface,
and import-side-effect set 339/339 in 168.290 seconds, audit 217, pycompile 2/2,
empty selected bindings/consumers, `git diff --check`, and the unchanged
acyclic 48-module/203-edge DAG at
`e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
Required implementation gates are the exact transforms and hashes above,
focused 339/339, audit 217, pycompile, full discovery 2,143/2,143, live/dynamic-
consumer zero, DAG parity, artifact hygiene, and diff check. Benchmark refresh
and remote CI remain **NOT RUN**. This deletion proves no behavior, answer-
quality, ranking, performance, benchmark, schedule, ledger, or Phase 3
completion claim.

## Completed Evidence-Owner Zero-Load Import Cleanup Batch

Commit `6d0e21c` deleted the six selected import bindings and no definition,
owner, live importer, call, policy, or runtime branch. Selected owner loads,
direct imports, module attributes, and dynamic consumers finish zero; retained
retrieval-pipeline, runtime-trace, config, and evidence behavior remain intact.

Production source is exactly `-6`; tests are `+9/-9`, and the whole commit is
`+9/-15` across two files. Nine absolute-line fingerprint expectations account
for the test transform. The committed diff SHA-256 is
`2f26c4c2be025ddbc7d8c701af0e84707079c17a1934ca82f7a7890dca8d80d3`.
Focused graph-helper/text-surface/import tests 339/339 in 169.551 seconds,
audit 217, pycompile 2/2, selected consumer zero, unchanged acyclic
48-module/203-edge DAG, full discovery 2,143/2,143 in 213.316 seconds, artifact
hygiene, and diff checks passed. Benchmark refresh and remote CI were **NOT
RUN**; this dead-import-only batch is not a behavior, quality, ranking,
performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Preferred Aggregate-Answer Selector Characterization

The following characterize-only record preceded commit `f220c9c`. Its rename
and projected gates are complete; it is retained for audit and is not active or
competing work.

Rename the exact current 63-line
`financial_answer_projection._preferred_complete_aggregate_subtask_answer(subtask_results: List[Dict[str, Any]], final_answer: str) -> str`
definition in place to public
`preferred_complete_aggregate_subtask_answer(...)`. Add no compatibility alias,
wrapper, new owner, policy, or behavior branch. The selected function is already
imported by four peer modules; this batch fixes visibility only.

Preserve exact `str(final_answer or "")` selection and one
`_normalise_projection_spaces(...)` call. A blank normalized answer returns `""`
before the row input is materialized. Otherwise eagerly evaluate exact
`list(subtask_results or [])`, preserve row identities, skip non-`Mapping` rows,
and retain the current fresh `dict(...)` copies, operation-family precedence,
metric-family fallback, `ok`/`ready` status gate, and candidate precedence.
Preserve all three existing completion paths: append only nonnumeric narrative
sentences from a candidate suffix; select a numeric candidate already contained
inside a longer answer only when the preceding prefix is also numeric; or adopt
a non-substring candidate only through
`_candidate_reduces_conflicting_numeric_surfaces(...)`. Longest accepted output
wins with stable row order. Keep exact substring/split/regex/normalization order,
raw truth and string conversion, eager list materialization, mapping copies,
input and nested-object immutability, helper laziness, and every uncaught error.

The exact production scope is one definition, four import bindings, and four
two-positional-argument calls over five source paths. Every call has no keyword
and caller `try` depth zero:

| Importer / caller | Exact arguments | Existing adoption |
| --- | --- | --- |
| `financial_agent_run_projection.complete_aggregate_public_answer_projection` | `subtask_results`, `base_answer or public_answer` | blank result returns `("", {})`; a result feeds the existing aggregate projection/attach path |
| `financial_aggregate_projection.structured_subtask_projection_for_public_answer` | `subtask_results`, `public_answer` | exact `or public_answer` fallback before the current-rendered gate |
| `financial_graph.FinancialAgent._structured_result_projection_for_stale_public_numeric_answer` | `subtask_results`, `structured_answer or public_answer` | result remains only the existing equality guard before replacement composition |
| `financial_runtime_trace._structured_result_subtask_projection_if_public_aligned` | `subtask_results`, `public_answer` | exact `or public_answer` fallback before trace comparison/build |

Any selected-function failure must stop later caller work exactly where it does
now. Do not move or publicize its eight owner-private support helpers in this
batch. Numeric-surface extraction/equivalence, broader answer projection,
structured-result repair, evidence construction, retrieval, graph state,
artifact/ledger mutation, and final sequencing remain outside the boundary.

Current/projected owner top-level public/private counts are 12/9 to 13/8.
Selected owner-local calls, non-call loads, module attributes, dynamic
`getattr`/`hasattr` consumers, and public-name collisions are zero. The selected
body AST-dump hash, excluding only the function name/signature, is
`5828d88632c45a63a0376cc823682d8ff13d5f451ef3adf7124a5b89262b6bec`.
Mapping-record SHA-256 is
`96f1acd9f315cf03c630bab38c42ddae77761c29936a22ff0f296fffe9b060ea`.
Current/projected binding-record hashes are
`fbcda4b1226d349d324831f942ac40d4d16c389ef4e69765fec8daf205544502` /
`4d9c472d5e85ce5c83300ec802c1b1f9905da34fdf6d489d400552928d98ec2a`;
call-record hashes are
`d751cfe671ef796048c1464ce42966751060efed2c3acde9b2733083d494ac79` /
`5eb0ba8d59203ec8787553d03acbe009f076b26f5905ff2ec37fb3bf9b9d7bd3`.

Two test files contain 14 exact private-name strings; one existing answer-owner
contract changes only its public/private tuple from `(12, 9)` to `(13, 8)`.
There is no caller-body fingerprint replacement. Projected source/test/whole
transforms are `+9/-9`, `+15/-15`, and `+24/-24` across exactly five source and
three test files. The exact temporary projection diff SHA-256 is
`0212a1273a1dfda7e87ed5cf3986e238e4433e89cbd0bf9cacc95b5439885c1d`.
Add no test method or weakened expectation.

Current and projected direct behavior/order/error probes passed 7/7. The exact
temporary projection passed public identity 4/4, affected plus import tests
527/527 in 181.586 seconds, audit 217, pycompile 8/8, retired private refs zero,
`git diff --check`, and the unchanged acyclic 48-module/203-edge DAG at
`e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
Required implementation gates are the exact transform/hashes above, direct
behavior and identity, affected 527/527, audit 217, pycompile, full discovery
2,143/2,143, and diff check. Benchmark refresh and remote CI remain **NOT RUN**.
This characterization establishes no behavior, answer-quality, ranking,
performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Preferred Aggregate-Answer Selector Public API Batch

Commit `f220c9c` renamed the selected 63-line definition, four import bindings,
and four calls to `preferred_complete_aggregate_subtask_answer(...)` without an
alias, wrapper, owner, policy, or behavior branch. Blank-answer short circuit,
eager row materialization, mapping copies, operation/metric/status/candidate
precedence, all three completion paths, longest/stable selection, caller
fallback/adoption, helper laziness, immutability, and exception stops remain
unchanged. Owner public/private counts finish 13/8 and retired private refs
finish zero.

Production source is `+9/-9`, tests are `+15/-15`, and the whole commit is
`+24/-24` across five source and three test files. The committed diff SHA-256
is `0212a1273a1dfda7e87ed5cf3986e238e4433e89cbd0bf9cacc95b5439885c1d`.
Direct behavior/order/error probes 7/7, public identity 4/4, affected plus
import tests 527/527 in 181.671 seconds, audit 217, pycompile 8/8, retired-ref
zero, unchanged acyclic 48-module/203-edge DAG, full discovery 2,143/2,143 in
214.528 seconds, and diff checks passed. Benchmark refresh and remote CI were
**NOT RUN**; this visibility-only batch is not a behavior, quality, ranking,
performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Text-Surface Primitive Characterization

The following characterize-only record preceded commit `4a4550c`. Its rename
and projected gates are complete; it is retained for audit and is not active or
competing work.

Rename the four externally imported private primitives at the top of
`financial_text_surface.py` in place. Add no compatibility alias, wrapper, new
owner, or behavior branch. The exact mapping and behavior boundary is:

| Current | Public | Exact behavior |
| --- | --- | --- |
| `_tokenize_terms(text: str)` | `tokenize_terms(text: str)` | exact `re.findall(r"[가-힣A-Za-z0-9]+", text or "")`, then a fresh lowercase set containing only tokens whose raw length is at least two |
| `_split_sentences(text: str)` | `split_sentences(text: str)` | call `_normalise_spaces(text)` once, return a fresh empty list on a falsey result, otherwise use the exact punctuation-or-`다` split regex documented below and retain ordered `part.strip()` values |
| `_strip_anchor_text(text: str)` | `strip_anchor_text(text: str)` | remove bracket anchors, then leading `*`/`-`/`•` markers, then return exact `_normalise_spaces(cleaned)` |
| `_strip_rerank_metadata(text: str)` | `strip_rerank_metadata(text: str)` | evaluate exact `str(text or "")`, remove bracket metadata, collapse whitespace, and return `raw.strip()` |

Preserve raw truth before string conversion. Tokenization and anchor stripping
must not add a `str(...)` coercion; a falsey input must select the empty string,
while a truthy non-string remains an uncaught regex error. Rerank stripping must
stringify a truthy input exactly once and must not stringify a falsey input.
Sentence splitting passes the original input directly to `_normalise_spaces`.
Its split pattern remains exact `r"(?<=[.!?])\s+|(?<=다)\s+"`.
Preserve set/list freshness, lowercase and length filtering, set dedupe,
sentence order and duplicates, the repeated `part.strip()` filter/result calls,
both exact regex sequences, input immutability, and every truth, regex,
normalization, string, iteration, length, lowercase, strip, membership, hash, or
comprehension failure. Do not change the distinct public
`split_narrative_sentences(...)` API.

The owner has no local call to any selected function. Current scope is four
definitions, ten import bindings, and 23 direct owner-external calls over six
source paths: 14 tokenizer, one sentence splitter, one anchor stripper, and
seven rerank-metadata stripper calls. Every call has one positional argument,
no keyword, and caller `try` depth zero. Token sets continue to feed label
matching, evidence `allowed_terms`, and retrieval overlap; sentence and anchor
results continue to feed validation fallback checks; stripped rerank text keeps
each caller's existing exact-result versus `or original` adoption. Any selected
failure must stop the remaining caller work exactly where it does now.

Current/projected owner top-level public/private counts are 15/4 to 19/0.
Future public top-level definitions/importer bindings do not collide. One
unrelated function-local list variable already named `split_sentences` remains
scope-local and unchanged. Non-call loads, module attributes, and dynamic
`getattr`/`hasattr` consumers are zero.

Mapping-record SHA-256 is
`bf86fcefc508849d1961e5a8b24f8743fe77f00ff8b1ff62b853deabf1c5b5df`.
Current/projected binding hashes are
`fbc70d3934774fb1d21e5fcf74924f36c3a28181d98668da4d3b211eb1c70f52` /
`265e6f5987c7a8d873cbdaac2e35192c0f9048f8297772945b3c8bde1c2f93b9`;
call-record hashes are
`2b68507a11ae4fb03d4bc786839efb4cda2675efcfb1bebe7b498b027a5eff59` /
`0c0021ed4fffe99cd081121800193812633902965f1d0ee809bed3026d053997`.

Three test files contain 13 exact private-name strings. The rename also changes
the following already-pinned CURRENT-SOURCE fingerprints:

| Scope | Current | Projected | Replacements |
| --- | --- | --- | ---: |
| caller `_augment_narrative_answer_with_supported_drivers` | `11bb6f9d5a54ced825d8082221af1058758a2f74531cc352e381f929e8f7d46f` | `884ad4433b14d5b53bba4ea04d50f1dc5f8349c72a29b70a0e3ee60019d2b15b` | 1 |
| caller `_supplement_policy_realized_evidence` | `48ab56c5528d2499fe5dfd27a491079d7eb771954ce02c3739a0926137b52423` | `7b1a8c031c398d8bc1c26ff8b1f51819043773917449f9535baa9f0448b3b7d0` | 1 |
| caller `collect_retrieved_operand_evidence_candidates` | `837da702ca73fbab5972dbe7dd36329dcfb4e60903231403da89401adc47a789` | `29a40abfdb409f2de5cb1edfa4b30d23640c10fc56e0ed767d25dc6f591cea43` | 1 |
| caller `_rerank_docs` | `45b649d9c97d6f8fb6010f6ebb38a12958624920a558a95b0bac6abf3b3e6f45` | `12767296524cc80df3fb4b2a69478be3c9d73055eab8012c18992f2249ca5a46` | 1 |
| narrative-context caller map | `b28eb301ac4af8d5cfda0d990dfb3f07aed9b47dfc2f4800faf7523332dd0de0` | `ff28482c35a004f7abdd5587d007f674a0aaa8ab205a56a714cba04c7b0ad7ee` | 1 |
| percent-point-difference caller map | `65fc95530821ed9f9cb776d62736c0f5d1e4b1c71cb57b10182c2c10db389b19` | `842df1bdd0864226a82f70dbd6bd4e1794fb734ea7d15f53900d21c86b9afd2f` | 1 |
| metadata-period caller map | `b039d1ffb850ce20cf5b001ed8b272f8f49b7057f7a98fc93330e789af09bb7f` | `518c605a06e0c928dac59c93ea8fe6f04e0cea80bfee0acb6e08a65ea743a650` | 1 |
| desired-consolidation caller map | `53538b42c37007f917208ad83081cc45a4af1523f89339025cf95dd636b3cc43` | `98683c3e8ffe2cd83811601c8309ad72fd76c38e3672c4b4b982fa823c188592` | 2 |
| operand-text caller digest | `d95a92e589b9574fcd8d2a537f63d6edf133046c92517af3382ee9b778d2d0de` | `bf117326bbbbbcd736c2c689962ba08ff0686f00a119ebe0a80e12e72757f99e` | 1 |
| strip-leading-period caller hash | `34c20297894ed727c215c2008282f10faa4d94a960240bf31f74b598ac7851c5` | `9ebfd98aecd1ffebbc128f047bbe985e06f81ed98a3d625f21a42ab7a3c8a612` | 1 |

These are ten fingerprint pairs and 11 replacements. Their canonical mapping
hash is
`9e3bc3b412aa48b6b48e84f655e04d1e16ee9d44511832a74bd54e8513957eb8`.
Projected source/test/whole transforms are `+36/-36`, `+24/-24`, and
`+60/-60`; the exact temporary projection diff hash is
`78d64c25819b505c16ee3962126a98d1e2b6240c09ff41d2fe7749684b189ef0`.
Add no test method or weakened expectation.

Current direct behavior/laziness/error probes pass 8/8. The exact projected
tree passed public identity/behavior 4/4, the three directly affected modules
413/413 plus import-side-effects 19/19 (432/432 combined), source/test pycompile
9/9, runtime audit 217, retired private refs zero, and `git diff --check`.
The recursive agent DAG remains 48 modules/203 edges at
`e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
Required post-edit gates are the complete transform and hashes above, focused
432/432, import 19/19, audit 217, pycompile, full discovery 2,143/2,143, and
diff check. Benchmark refresh and remote CI remain **NOT RUN**.

Keep narrative-policy selection, evidence construction, rerank scoring,
candidate/operand adoption, retrieval, graph state, model invocation,
artifact/ledger mutation, and final sequencing outside this visibility batch.
The inventory and projected tests establish no answer-quality, ranking,
performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Text-Surface Primitive Public API Batch

Commit `4a4550c` renamed the four selected definitions, ten imports, and 23 calls
to `tokenize_terms`, `split_sentences`, `strip_anchor_text`, and
`strip_rerank_metadata` without an alias or wrapper. Exact regex, raw truth and
stringification, normalization, set/list freshness, sentence ordering, caller
adoption, and every exception boundary remain unchanged. Retired private refs
finish zero and owner public/private counts finish 19/0.

Production source is `+36/-36`, tests are `+24/-24`, and the whole commit is
`+60/-60`. Thirteen direct test strings and 11 CURRENT-SOURCE fingerprint
replacements account for the test transform. The committed diff SHA-256 is
`78d64c25819b505c16ee3962126a98d1e2b6240c09ff41d2fe7749684b189ef0`.
Public identity/behavior 4/4, focused 432/432 in 180.672 seconds, audit 217,
source/test pycompile 9/9, unchanged 48-module/203-edge DAG, retired-ref zero,
full 2,143/2,143 in 212.018 seconds, and diff checks passed. Benchmark refresh
and remote CI were **NOT RUN**; this visibility-only batch is not a behavior,
quality, ranking, performance, benchmark, schedule, ledger, or Phase 3
completion claim.

## Completed LangChain-Loader Public API Batch

Commit `643bdf6` renamed all four selected definitions, 14 imports, and 25 calls
to public names without an alias or wrapper. Function-local LangChain imports,
exact factories, returned identities, document keyword-only inputs and fresh
outer metadata copy, nested identities, caller `try` depth, and all exceptions
remain unchanged. Retired private refs finish zero and owner public/private
counts finish 4/0.

Production source is `+42/-42`, tests are `+29/-29`, and the whole commit is
`+71/-71`; its committed diff SHA-256 is
`d0f499aca84aab0aa6f242fdc308b589e8503c036e342c77b872764a784845e3`.
Fresh-import isolation, factory identity 4/4, metadata-copy and exception probes,
affected tests 676/676, import side effects 19/19, audit 217, source/test
pycompile, unchanged 48-module/203-edge DAG, full discovery 2,143/2,143 in
212.658 seconds, and diff checks passed. Benchmark refresh and remote CI were
**NOT RUN**. This is a visibility-only milestone, not a behavior, quality,
ranking, performance, benchmark, schedule, ledger, or Phase 3 completion claim.

The completed pre-commit contract is retained below as an audit record.

The completed batch renamed all four functions in
`financial_langchain_loaders.py` in place to public APIs. It added no
compatibility alias or wrapper, moved no LangChain import to module scope, and
changed no factory, argument evaluation, returned identity, caller gate, or
exception boundary. The exact mapping is:

| Current | Public | Exact lazy behavior |
| --- | --- | --- |
| `_chat_prompt_template_from_template(template: str)` | `chat_prompt_template_from_template(template: str)` | local `ChatPromptTemplate` import, then exact `ChatPromptTemplate.from_template(template)` |
| `_str_output_parser()` | `str_output_parser()` | local `StrOutputParser` import, then zero-argument construction |
| `_runnable_passthrough()` | `runnable_passthrough()` | local `RunnablePassthrough` import, then zero-argument construction |
| `_document(*, page_content: str, metadata: Mapping[str, Any])` | `document(*, page_content: str, metadata: Mapping[str, Any])` | local `Document` import, then exact `Document(page_content=page_content, metadata=dict(metadata))` |

The document inputs remain keyword-only. Preserve the fresh outer metadata dict,
its retained nested-object identities, and every import, attribute, factory, or
mapping-conversion failure. Importing the loader owner must continue to add zero
`langchain_core` modules. The prompt/parser/passthrough/document probes must
return their exact factory results; no caller catches a new failure.

Current scope is four definitions, 14 import bindings, and 25 direct calls over
nine source paths: 16 prompt, six parser, one passthrough, and two document calls.
The two evidence parser calls remain inside caller `try` depth one; every other
selected call remains at depth zero. Current/projected owner public/private
counts are 0/4 to 4/0. Public-name collisions, non-call loads, module attributes,
and source/test `getattr`/`hasattr` consumers are zero.

Mapping-record SHA-256 is
`c8e0fa3d0ad375525bbd70a11c3b144e3c8dfa2769208ff1f9ab4b1d77f4e084`.
Current/projected binding hashes are
`395d4efc19b25d1a9bacbd91288d5f0d54208aa664cc638b3e9e05a89f6d7b64` /
`59bf77dfac15eaf15b59196bc25ba064965491e1e7092539ae95487d8b295e09`;
call-record hashes are
`82d75a0b41292186737024be7b32664d88ac6e6689ce2c49ef818c3423e1cc67` /
`dbad002ce2f18e9f4c1d7e196682309e3edd06f6d2960bf3d879e44d9be32d46`.

Six test files contain 13 exact private patch strings. The rename also changes
the following already-pinned CURRENT-SOURCE fingerprints:

| Scope | Current | Projected | Replacements |
| --- | --- | --- | ---: |
| caller `_extract_calculation_operands` | `b44b7f616419c86f8047ff446b9f6b020fdec15b524374a42eb7240923656393` | `8127401da0b0392eadcfe4730463c2b5fbd267f80eb6e944144559cf986fa5ac` | 4 |
| caller `_plan_formula_calculation_from_operation_decision` | `777472b4cd65105c9f3115db8f320d35c747dbd82264fd6c13169966f64ee589` | `fae9e68d4b8ce499b9ba09c72b8d50861d881ee9ac51a2e8d3fefbd344c6d415` | 1 |
| caller `_extract_evidence` | `c07cdfe9109da26935c275ae85c99d1c23f166d181dfbf919da77bbb3e2ef60b` | `70e15a350298d98dee4b110d4033ef7cb8e336f3801a4050d81bddb9b88a3b6e` | 2 |
| caller `_plan_reflection_retry` | `e7cb9f5d4b30fb5862524e59c6771a7e11d14b0853ba2f6386fc87ebcad16040` | `1797f79af32c1e06b6627a0e25ba0457a8288f9eb001b692c43a86c90678cfb9` | 2 |
| `is_ratio_percent_query` caller map | `f34d81f35d5c2ea72ad442a7b73d63b8696f76dbda1071fe55fd66c909b5618d` | `0e13e85fed6712b333aa659427686113e24d47022ecd7d28f3a1c2f06be5d53e` | 1 |
| narrative-context caller map | `0ecabd140a22cb1f8992ea46f0da815305868d2e1d913f91f70047e0bad2d390` | `b28eb301ac4af8d5cfda0d990dfb3f07aed9b47dfc2f4800faf7523332dd0de0` | 1 |
| percent-point-difference caller map | `66a4431133b269f9f78f16eccc46fecdb27f25f919cb084f9659eba2fdbfbad5` | `65fc95530821ed9f9cb776d62736c0f5d1e4b1c71cb57b10182c2c10db389b19` | 1 |
| percent-point-coercion caller map | `7398adefc5b59d9ce6607cc8ceae0c52da2a062ba8dc3066c9720efad02db927` | `a5308e1856ef1f3e82e7a7994c05c6ca375fd19c2278ad99c98fa3400978e52c` | 1 |
| direct-numeric-grounding caller map | `106f168828edbb8e420d60463381be08b438ee680bdd1d7df2b0ccc150a253a7` | `c54161def8235e16506e68be3e11f3ad3366088f911f649465cd862d9d072cac` | 1 |
| desired-consolidation-scope caller map | `7beaca67827ba25b13fea4c40d71eae90bf440ad19ae79966a849e1561534ba0` | `53538b42c37007f917208ad83081cc45a4af1523f89339025cf95dd636b3cc43` | 2 |

These are nine caller-body plus seven caller-map occurrences, or 16 fingerprint
replacements. Their canonical mapping hash is
`4d9b13ad5541d99acb2cdc86ee9e5c95bf5c61e480a11e693782e96f89d7c323`.
Projected source/test/whole transforms are `+42/-42`, `+29/-29`, and
`+71/-71`. Add no test method or weakened expectation.

Fresh-import isolation, factory identity 4/4, metadata-copy, and
exception-propagation probes passed. AST compilation passed source 9/9 plus
tests 6/6. The recursive agent DAG remained 48 modules/203 edges at
`e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`;
the audit remained 217. Complete transform, retired private refs zero, owner
counts 4/0, mapping/caller/fingerprint parity, affected seven-module tests
676/676, import-side-effect 19/19, runtime audit 217, full discovery
2,143/2,143, source/test pycompile, and `git diff --check` all passed.
Benchmark refresh and remote CI remain **NOT RUN**.

## Completed Graph-Model-Loader Public API Batch

Commit `4dd38ca` renamed all 13 selected definitions, 17 imports, and 18 calls to
public names. Cached `_graph_model(name)` remains the only private owner function.
Lazy import, exact model identity, answer-slot payload identity, exception
propagation, and caller result adoption remain unchanged. Retired private refs
finish zero and owner public/private counts finish 13/1.

The characterize-only checkpoint counted 18 direct test refs but missed nine
caller-body plus seven caller-map fingerprint replacements. Final production is
`+50/-50`, tests are `+34/-34`, and the whole commit is `+84/-84`; no test method
was added or weakened. The committed diff SHA-256 is
`30e6ecf0905c80d799932ade117525ea698afa18b2697bb93d1360091c49ec37`.

Mapping/identity 13/13, affected tests 466/466, import side effects 19/19, audit
217, source/test pycompile, retired-ref zero, unchanged 48-module/203-edge DAG,
and full discovery 2,143/2,143 in 213.609 seconds passed. Benchmark refresh and
remote CI were **NOT RUN**. This visibility-only milestone is not a behavior,
quality, ranking, performance, benchmark, schedule, ledger, or Phase 3
completion claim.

## Completed Dead MAS-Node Helper Cleanup

Commit `3eadee4` deleted the unused Analyst/Researcher `_trace(...)` definitions
and Orchestrator `_artifact_payload(...)`. The selected definition/import/load/
call/attribute/dynamic-consumer record is now empty with hash
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
The live orchestrator `_trace(...)`, artifact answer/reference helpers, and two
`project_worker_artifact_boundary(...)` loads remain intact. No import became
unused and no test expectation changed.

The characterize-only projection counted one blank line per helper, but the
actual top-level separator is two blank lines. The exact patch therefore deletes
12 physical lines, not nine: module sizes are now 317/660/368. Public/private
function counts finish 2/10, 4/22, and 2/14. Production and whole-commit stats
are `-12`; the committed diff SHA-256 is
`2ee08fa81d381d49cc7682926a89ef39b0f9ae856faf2d6411c20f3e45d64d6e`.

Targeted Analyst/Orchestrator/Researcher/MAS tests 45/45, import side effects
19/19, audit 217, pycompile, empty selected record, unchanged 48-module/203-edge
DAG, and full discovery 2,143/2,143 passed. Benchmark refresh and remote CI were
**NOT RUN**. This dead-definition-only optional-MAS milestone is not a behavior,
quality, ranking, performance, benchmark, schedule, ledger, or Phase 3
completion claim.

## Completed Zero-Load Cross-Module Import Cleanup

Commit `be1fbc9` deleted exactly four private import bindings with zero loads and
zero calls in their selected importer: evidence `_document` and runtime-trace
resolution, retrieval-pipeline generic-metric aliases, and graph-calculation
direct-evidence-surface detection. It deleted no helper definition and preserved
repository-wide helper call counts at 2, 19, 4, and 2. Direct module-attribute
and dynamic namespace consumers remain zero.

Production source is `-4`; tests are `+60/-60`; the whole commit is `+60/-64`,
net `-4`. The static inventory finishes empty with hash
`4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
The DAG moved from 48 modules/205 edges to 48/203, removing only
`financial_graph_evidence -> financial_runtime_trace` and
`financial_retrieval_pipeline -> financial_graph_helpers`; its final edge hash
is `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
The committed diff SHA-256 is
`ac9fd2c24689e4c22ea7e16d0471dce7633d2205c8a4894530ab5201378f2ee9`.

The pre-edit inventory found 19 tuple-form DAG expectations, but the first wider
run exposed 26 additional standalone full-DAG expectations. The final test-only
transform therefore updates 45 current-DAG counts, one prior-edge count, two
retrieval-pipeline call lines, and 12 dependent call-record fingerprints: 60
exact replacements, with no new or weakened test. Focused DAG 19/19, graph
290/290, remaining semantic 960/960 for affected 1,250/1,250, separate owner
144/144, reflection/retrieval/reconciliation/import 110/110, audit 217,
pycompile, static live-reference/dynamic-consumer checks, and full 2,143/2,143
passed. Benchmark refresh and remote CI were **NOT RUN**. This dead-import-only
milestone is not a behavior, quality, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Extract-Year-Tokens Public API

Commit `d2a8f8e` renamed the exact former 25-line year-token projection in place
to public `financial_scope_policies.extract_year_tokens(...)`. No wrapper or
private alias remains. The graph-helper import, three calls, and one existing
exact test string use the public identifier. Query `20xx년` extraction order,
scope-year precedence, source-report direct/metadata fallback, equality dedupe,
fresh-list and identity/laziness guarantees, narrow conversion exceptions, and
all three caller result-adoption boundaries remain unchanged.

Production source is `+5/-5`, tests are `+1,148/-51`, and the whole commit is
`+1,153/-56`, net `+1,097`. Four new methods moved discovery from 2,139 to
2,143. Final scope-policy public/private counts are 17/3 and public identity is
2/2. The selected source-body hash remains
`b6e416b8033425999db29cebe67e3760021910aa836dd78614b61340982dcce8`.
Final call-record/caller-map hashes are
`e67fc351713582c74d9c165209ff5bc8449f1439212542ef5bf2cba7e628800b` /
`9b4ab9d450de2701ec06f798c7832f0fc9214a1bddd0af069e870a5d8bec74c2`;
the committed diff SHA-256 is
`997cb4c8e7a9246cfc4371771d792b4a25d0c4de485f990a8523449d17151408`.

Focused pre/post 4/4, retrieval scope 28/28, graph owner 290/290, operation
contracts 242/242, retrieval hints 5/5, task artifacts 15/15, text surface
30/30, calculation execution 45/45, math parsing 24/24, surface owner 1/1,
operand owner 69/69, affected semantic 1,250/1,250, separate owner set 144/144,
reflection/retrieval/reconciliation/import set 110/110, audit 217, and full
2,143/2,143 passed. Production/test transform, selected-body/three-caller
parity, public identity 2/2, unchanged 48-module/205-edge DAG, retired refs zero,
graph-test AST 286/286 plus four methods, pycompile, and diff check also passed.
Benchmark refresh and remote CI were **NOT RUN**. This visibility-only milestone
is not a behavior, quality, ranking, performance, benchmark, schedule, ledger,
or Phase 3 completion claim.

## Completed Report-Scope-Source-Receipts Public API

Commit `faba39e` renamed the exact former 7-line projection in place to public
`financial_scope_policies.report_scope_source_receipts(...)`. No wrapper or
private alias remains. Two owner-local calls, the retrieval importer/call, 28
exact graph-test bindings, and two longer retrieval-caller source strings use
the public identifier. Fresh-list construction, identity-preserving and lazy
source-report iteration, receipt normalization, equality-based first-seen
dedupe, non-mutation, and all three caller exception boundaries remain
unchanged.

Production source is `+5/-5`, tests are `+1,193/-75`, and the whole commit is
`+1,198/-80`, net `+1,118`. Four new methods moved discovery from 2,135 to 2,139.
Final scope-policy public/private counts are 16/4. Final call-record and three-
caller-map hashes are
`03014bbe5bfa18c8d28657847f0cce1ea67b68d9bb024ed13836336ce992e965` and
`4a8265bb5bebf1accedc9f46475fc0bf0d44c0cbeb5aace1d52b474230fec0ed`.
The final caller-body hashes are retrieval
`fb15cdfba59242d19a8fed120f5396c15b4c4448349874f5afb4359ada55fcbf`,
strict-company scope
`1876f174b4877f7356156763b6998fe3cd8db55bb5ffcee6b3884d60740c55e4`,
and single-report scope
`de34955b5bab08ad51e61ebc5707c19cfb50cb657924517a90d1c152bd79e7eb`.
The committed source/test diff SHA-256 is
`b1adfdddca9e994b41d504702dc5fc67661d87c8387282b47327e373bac594d6`.

Focused pre/post 4/4, retrieval scope 28/28, graph owner 286/286, operation
contracts 242/242, retrieval hints 5/5, task artifacts 15/15, text surface
30/30, calculation execution 45/45, math parsing 24/24, surface owner 1/1,
operand owner 69/69, affected semantic 1,246/1,246, reflection promotion 15/15,
reflection capability 24/24, retrieval pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, and full 2,139/2,139 passed. Pycompile, production/
complete transform 5/5 and 3/3, selected-body/three-caller parity, public
identity 2/2, unchanged 48-module/205-edge DAG, retired semantic/test refs zero,
graph-test AST 282/282 plus four methods, exact-string 28/28 and caller-source
2/2 transforms, UTF-8 3/3, non-ASCII 3/3, and diff check passed. Benchmark
refresh and remote CI were **NOT RUN**. This visibility-only milestone proves no
behavior, quality, ranking, performance, benchmark, schedule, ledger, or Phase
3 completion claim.

## Completed Strict-Company-Scope Public API

Commit `579141d` renamed the exact former 10-line policy in place to public
`financial_scope_policies.should_apply_strict_company_scope(...)`. No wrapper or
private alias remains. The sole retrieval importer/call and the four existing
bindings in `tests/test_retrieval_scope.py` use the public identifier. Companies-
first short circuit, shallow scope copy, explicit/source-receipt precedence,
exact booleans, immutability, retrieval company prepend/filter adoption, and
the propagated exception boundary remain unchanged.

Production source is `+3/-3`, tests are `+1,014/-42`, and the whole commit is
`+1,017/-45`, net `+972`. Four new methods moved discovery from 2,131 to 2,135.
Final scope-policy public/private counts are 15/5. Final call-record, one-caller-
map, and caller-body hashes are
`c82616a53264c2b42a488f483c6b833991821a6d2f4ffdb6d1269b4c49fd090b`,
`64ff812d9a106fbbd70a092a89f5eb9e8391de756b7f824c6e738fe37c3286e0`, and
`42f3e9a7359e4c72ddfaeedfdd4441b342ba31b768150db37194d20eeef9f2b4`.
The committed source/test diff SHA-256 is
`683f170f2dd40d325b4d7ce514054b991dc3465859ac61821dc40b604f293c28`.

Focused pre/post 4/4, retrieval scope 28/28, graph owner 282/282, operation
contracts 242/242, retrieval hints 5/5, task artifacts 15/15, text surface
30/30, calculation execution 45/45, math parsing 24/24, surface owner 1/1,
operand owner 69/69, affected semantic 1,242/1,242, reflection promotion 15/15,
reflection capability 24/24, retrieval pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, and full 2,135/2,135 passed. Pycompile, production/
complete transform 3/3 and 4/4, selected-body/sole-caller parity, public identity
2/2, unchanged 48-module/205-edge DAG, retired semantic/test refs zero, graph-
test AST 278/278 plus four methods, UTF-8 4/4, non-ASCII 4/4, and diff check
passed. Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
milestone proves no behavior, quality, ranking, performance, benchmark,
schedule, ledger, or Phase 3 completion claim.

## Completed Extract-Period-Sort-Key Public API And Unused Import Deletion

Commit `d9dddc4` renamed the exact former 10-line policy in place to public
`financial_scope_policies.extract_period_sort_key(...)`. No wrapper or private
alias remains. The sole real importer/call in calculation execution uses the
public identifier, while the graph-calculation private import with zero loads
and zero calls was deleted rather than renamed. Whitespace normalization, first
year match, matched-year/current/prior/default precedence, immutability, stable
sorting, evidence/growth adoption, and caller exception scope remain unchanged.

Production source is `+3/-4`, tests are `+1,016/-42`, and the whole commit is
`+1,019/-46`, net `+973`; production physical lines decrease by one through the
unused-import deletion. Four new methods moved discovery from 2,127 to 2,131.
Final scope-policy public/private counts are 14/6. Final call-record, sole-
caller-map, and caller-body hashes are
`257a8c47456cbf8326c10afcbf693f4aa73de321be9736a84c11b3ba6c334057`,
`d774b540cf895765fab754c99b74d64730d61e8d0e2b63cc5e1dfe67fa67c7d2`,
and `c065ec0fca3b6ba92bc23909c5fd5a3f1cc059dc3c67b48046ef7eeaf665698f`.
The committed source/test diff SHA-256 is
`3e1636144a5ac9308116dee53d920dbed588a6dc7858af366a8ecf7eda4d4e44`.

Focused pre/post 4/4, retrieval scope 28/28, graph owner 278/278, operation
contracts 242/242, retrieval hints 5/5, task artifacts 15/15, text surface 30/30,
calculation execution 45/45, math parsing 24/24, surface owner 1/1, operand owner
69/69, affected semantic 1,238/1,238, reflection promotion 15/15, reflection
capability 24/24, retrieval pipeline 1/1, reconciliation plan 51/51, import
19/19, audit 217, and full 2,131/2,131 passed. Pycompile, production/complete
transform 4/4, selected-body/sole-caller parity, public identity 2/2, unchanged
48-module/205-edge DAG, retired refs/public stores zero, unused-import deletion,
graph-test AST 274/274 plus four methods, UTF-8 4/4, non-ASCII 4/4, and diff check
passed. Benchmark refresh and remote CI were **NOT RUN**. This visibility/
cleanup milestone proves no behavior, quality, ranking, performance, benchmark,
schedule, ledger, or Phase 3 completion claim.

## Completed Metadata-Period-Match-Strength Public API

Commit `5509d78` renamed the exact former 11-line policy in place to public
`financial_scope_policies.metadata_period_match_strength(...)`. No wrapper or
private alias remains. Three external importers, three calls, and all 19
existing test bindings use the public identifier. Input short-circuit order,
repeated label rendering/stripping, set hashing/equality/dedupe/intersection,
zero/full/partial results, immutability, caller score adoption, and exception
scopes remain unchanged.

Production source is `+7/-7`, tests are `+1,148/-57`, and the whole commit is
`+1,155/-64`, net `+1,091`; production physical line counts are unchanged. Four
new methods moved discovery from 2,123 to 2,127. Final scope-policy public/
private counts are 13/7. Final call-record and three-caller-map hashes are
`62d3900668cbfdab705d00ce2afba44ed475740ceed66d8dd9f08bdfb0a30d03`
and `b039d1ffb850ce20cf5b001ed8b272f8f49b7057f7a98fc93330e789af09bb7f`.
The three final caller-body hashes are
`480a1b36d876a9ee12039a7ee24c7866224471037acfbabf8f7693c67b6d0cb9`,
`868506cb65faf31c27717ebed547371547b049d94b521ad4c662e4f7a42f5ea0`,
and `45b649d9c97d6f8fb6010f6ebb38a12958624920a558a95b0bac6abf3b3e6f45`.
The committed source/test diff SHA-256 is
`db3d34f22af44759d21e6ead24680aad7c3b7c290cd1ea3d4f3c009bd7afc19b`.

Focused pre/post rename 4/4, graph owner 274/274, operation contracts 242/242,
retrieval hints 5/5, task artifacts 15/15, text surface 30/30, calculation
execution 45/45, math parsing 24/24, surface owner 1/1, operand owner 69/69,
affected semantic 1,234/1,234, reflection promotion 15/15, reflection capability
24/24, retrieval pipeline 1/1, reconciliation plan 51/51, import 19/19, audit
217, and full 2,127/2,127 passed. Pycompile, production transform 4/4, complete
transform 6/6, selected-body/three-caller parity, all three calls/four source
modules, public identity 4/4, unchanged 48-module/205-edge DAG, retired refs/
public stores zero, graph-test AST 270/270 plus four methods, UTF-8 6/6, non-
ASCII 6/6, and diff check passed. Benchmark refresh and remote CI were **NOT
RUN**. This visibility-only milestone proves no behavior, quality, ranking,
performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Desired-Consolidation-Scope Public API

Commit `d6e7765` renamed the exact former 15-line policy in place to public
`financial_scope_policies.desired_consolidation_scope(...)`. No wrapper or
private alias remains. Five external importers, twelve calls, and all 26 existing
test bindings use the public identifier. Query/metadata/default precedence,
eager shallow policy copies, eager/lazy evaluation boundaries, exact scope
results, immutability, caller gates, and exception scopes remain unchanged. The
calculation caller's one colliding local store and eight loads alone use
`requested_consolidation_scope`; both existing keyword labels remain unchanged.

Production source is `+26/-26`, tests are `+1,801/-64`, and the whole commit is
`+1,827/-90`, net `+1,737`; production physical line counts are unchanged. Four
new methods moved discovery from 2,119 to 2,123. Final scope-policy public/private
counts are 12/8. Final call-record and eleven-caller-map hashes are
`e0e1670ce1714cc446ad4091bafc8efb38ee1a14cf6f03b4ebeadec36be25291`
and `143804328cb07fcfc3d6d6099e59427dafd24296ff0e1f7bb49ba74a1b273ec9`.
The committed source/test diff SHA-256 is
`383134898960245449744387c078a61a6c02ba538cecb4252c60b8f0bcdc898e`.

Focused pre/post rename 4/4, graph owner 270/270, operation contracts 242/242,
retrieval hints 5/5, task artifacts 15/15, text surface 30/30, calculation
execution 45/45, math parsing 24/24, surface owner 1/1, operand owner 69/69,
affected semantic 1,230/1,230, reflection promotion 15/15, reflection capability
24/24, retrieval pipeline 1/1, reconciliation plan 51/51, import 19/19, audit
217, and full 2,123/2,123 passed. Pycompile, production transform 6/6, complete
transform 10/10, selected-body/eleven-caller parity, all twelve calls/six source
modules, public identity 6/6, unchanged 48-module/205-edge DAG, retired refs/
public stores zero, graph-test AST 266/266 plus four methods, collision-local
transform 9/9, retained keyword names 2/2, UTF-8 10/10, non-ASCII 8/8, and diff
check passed. Benchmark refresh and remote CI were **NOT RUN**. This visibility-
only milestone proves no behavior, quality, ranking, performance, benchmark,
schedule, ledger, or Phase 3 completion claim.

## Completed Direct-Numeric-Grounding Public API

Commit `7de65fc` renamed the exact former 40-line policy in place to public
`financial_operation_policies.requires_direct_numeric_grounding(...)`. No
wrapper or private alias remains. Three external importers, three external calls,
and all 19 existing test bindings use the public identifier. Task snapshotting,
operation-family precedence, required-row filter/copy ordering, ratio/sum and
difference/growth results, fallback classifier adoption, immutability, caller
gates, and exception scopes remain unchanged.

Production source is `+7/-7`, tests are `+1,669/-61`, and the whole commit is
`+1,676/-68`, net `+1,608`; production physical line counts are unchanged. Four
new methods moved discovery from 2,115 to 2,119. Final operation-policy public/
private counts are 7/0. Final call-record and three-caller-map hashes are
`d90668f2a62c7ce5d6aff1ee35b4a57c215427ebb0aae86730eeda3252deecdc`
and `66a895f03194fd07f0f54a32075d5229c9f3ebbb5f7d7be4279073a3c1b70bac`.
The committed source/test diff SHA-256 is
`a3409380b1d0d56104ab8caebfc94767089ff74098194575a1fde65aa77bc7b0`.

Focused pre/post rename 4/4, graph owner 266/266, operation contracts 242/242,
retrieval hints 5/5, task artifacts 15/15, calculation execution 45/45, math
parsing 24/24, surface owner 1/1, operand owner 69/69, affected semantic
1,226/1,226, reflection promotion 15/15, reflection capability 24/24,
retrieval pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217, and
full 2,119/2,119 passed. Pycompile, production transform 4/4, complete transform
8/8, selected-body/three-caller parity, all three calls/four source modules,
public identity 4/4, unchanged 48-module/205-edge DAG, retired production refs/
public stores zero, graph-test AST 262/262 plus four methods, UTF-8 8/8,
non-ASCII 4/4, and diff check passed. Benchmark refresh and remote CI were
**NOT RUN**. This visibility-only milestone proves no behavior, quality,
ranking, performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Percent-Point-Unit-Coercion Public API

Commit `a893cb3` renamed the exact former 21-line policy in place to public
`financial_operation_policies.should_coerce_percent_point_unit(...)`. No wrapper
or private alias remains. Two external importers, two external calls, and all 18
existing test bindings use the public identifier. Percent-point/mode/ordered-ID/
operand-map/unit gates, duplicate-last mapping, operation/formula normalization,
exact result, immutability, caller adoption, and exception scopes remain
unchanged.

Production source is `+5/-5`, tests are `+1,589/-48`, and the whole commit is
`+1,594/-53`, net `+1,541`; production physical line counts are unchanged. Four
new methods moved discovery from 2,111 to 2,115. Final operation-policy public/
private counts are 6/1. Final call-record and two-caller-map hashes are
`59d36159e78009dbca607854cf4062b920132c1c1944d62f3adefd29861575b5`
and `a15eb6644ac2c75175109618f2a9fc926cc39354c0b72b94bbc475edab7dd11d`.
The renamed owner-caller also moves the current percent-point-classifier call/
caller-map hashes to
`2e395ec24f0b8c280c1a86744ea34d67e9361907cb004f3f548dc2b898250a55`
and `8ccdb658b0f465b6008e3580ba3cd6e76eb8af16f4af9cc467255487f80ffcd8`.
The committed source/test diff SHA-256 is
`bae62fda6041a01df827633e1f6c1b38ba8c171fa76338d18dde8761250b217a`.

Focused pre/post rename 4/4, graph owner 262/262, calculation-execution owner
45/45, math parsing 24/24, surface owner 1/1, operand owner 69/69, affected
semantic 1,222/1,222, reflection promotion 15/15, reflection capability 24/24,
retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217, and
full 2,115/2,115 passed. Pycompile, production transform 3/3, complete transform
6/6, selected-body/two-caller parity, both calls/three source modules, public
identity 3/3, unchanged 48-module/205-edge DAG, retired production refs/public
stores zero, graph-test AST 258/258 plus four methods, UTF-8 6/6, non-ASCII 5/5,
and diff check passed. Benchmark refresh and remote CI were **NOT RUN**. This
visibility-only milestone proves no behavior, quality, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Percent-Point-Difference Public API

Commit `1d8eb67` renamed the exact former 12-line classifier in place to public
`financial_operation_policies.is_percent_point_difference_query(...)`. No
wrapper or private alias remains. Five external importers, seven external calls,
one owner-local call, and all 15 existing test bindings now use the public
identifier. Raw-input normalization, shallow policy snapshotting, eager marker
tuple construction, direct-marker precedence, ratio/comparison gating, lazy
membership, exact booleans, immutability, and current exception scopes remain
unchanged.

Production source is `+14/-14`, tests are `+1,976/-51`, and the whole commit is
`+1,990/-65`, net `+1,925`; production physical line counts are unchanged. Four
new methods moved discovery from 2,107 to 2,111. Final operation-policy
public/private counts are 5/2. Final call-record and seven-caller-map hashes are
`0269efe3c2a5fc64b44f70b1c2c02206f577ea68c1f3b088d663e6acdfbac444`
and `2f34fd00af1b37503820f103872b91de63d69cc644e53bbe00bf679362e0cf21`.
The committed source/test diff SHA-256 is
`8f6939314dafb61d7aa613afd858c203ed9f0ac454629fd453c2f187f234ed89`.

Focused pre/post rename 4/4, graph owner 258/258, surface owner 1/1, operand
owner 69/69, affected semantic 1,218/1,218, reflection promotion 15/15,
reflection capability 24/24, retrieval-pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, and full 2,111/2,111 passed. Pycompile, production
transform 6/6, complete transform 9/9, selected-body/seven-caller parity, all
eight calls/six source modules, public identity 6/6, unchanged 48-module/
205-edge DAG, retired production refs/public stores zero, graph-test AST
254/254 plus four methods, UTF-8 9/9, non-ASCII 8/8, and diff check passed.
Benchmark refresh and remote CI were **NOT RUN**. This visibility-only milestone
proves no behavior, quality, ranking, performance, benchmark, schedule, ledger,
or Phase 3 completion claim.

## Completed Unreachable Single-Metric Concept Branch Deletion

Commit `ca2969b` deleted exactly the former lines 1623-1631 branch from
`financial_graph_helpers._build_concept_required_operands(...)` without a
replacement. The guard required both one ordered concept spec and an empty
roles list immediately after rebuilding that list one-to-one from the specs;
the branch and its helper call were therefore runtime-unreachable. The earlier
difference/growth return, ordering and role recomputation, downstream role
hints, operand construction/dedupe, inputs, and exception boundaries remain
unchanged.

The owner now spans lines 1590-1720 with 18 top-level statements and body
SHA-256
`dfbc243dd7560578cdab5c18fa33ca0b457c9afc3653a2200d7321b2f2ae4164`.
Public helper references finish 5, graph-helper references finish 3, and direct
calls/callers finish 3/3. Final call-record and caller-map hashes are
`76cd32e8d95fd910137283b602d7ef4fc0115f9c5637b6005d67b4bd900769dd`
and `fc94b25b2c63bb160d0732fb17686ba866abbf7183b8f69758dc32e65791d0a5`.
Operation-policy counts stay 4/3 and the DAG stays 48 modules/205 edges.

Production source is `+0/-9`, tests are `+786/-32`, and the whole commit is
`+786/-41`, net `+745`. The committed source/test diff SHA-256 is
`0d342c2106e55f4079ee658ddce7a940376ba168bb5532e0e69d1118b96dfcef`.
Four new methods moved discovery from 2,103 to 2,107.

Focused pre/post deletion 4/4, graph owner 254/254, surface owner 1/1, operand
owner 69/69, affected semantic 1,214/1,214, reflection promotion 15/15,
reflection capability 24/24, retrieval-pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, and full 2,107/2,107 passed. Pycompile, exact nine-line
production deletion, projected owner/caller hashes, graph-test AST 250/250 plus
four methods, unchanged public identity/owner count/DAG, UTF-8/non-ASCII 2/2,
and diff check passed. Benchmark refresh and remote CI were **NOT RUN**. This
dead-code deletion proves no quality, ranking, performance, benchmark,
schedule, ledger, or Phase 3 completion claim.

## Completed Single-Metric-Period-Comparison Public API

Commit `f0fae1f` renamed the exact former 11-line classifier in place to public
`financial_operation_policies.is_single_metric_period_comparison(...)`. No
wrapper or private alias remains. Query identity/normalization, the shallow
period-policy snapshot, eager marker tuple construction, lazy marker
membership, truthy-label filtering, stable native hash/equality dedupe,
immutability, return values, and uncaught owner failures are unchanged after
definition-name normalization.

All four source calls across two modules now bind the public owner with two
positional arguments, no keywords, and caller `try` depth zero. Three calls are
runtime-reachable and retain their exact generic-operand, operation-family, and
direct-grounding gates, adoption, and stops. The concept-operand call was also
renamed, but its CURRENT-SOURCE contract proved the surrounding cardinality
guard is contradictory, so neither the classifier nor that branch body can run.
Operand construction, operation precedence, grounding, state, artifacts, and
ledgers did not move. Operation-policy counts finish 4/3.

Production source is `+6/-6`, tests are `+1,627/-23`, and the whole commit is
`+1,633/-29`; production physical lines are unchanged. Four new methods moved
discovery from 2,099 to 2,103. The committed source/test diff SHA-256 is
`190b8c55912b139f610b4fda1bca8ada5ee4051ac5142eef0bf112116adb869d`.

Focused pre/post rename 4/4, graph owner 250/250, surface owner 1/1, operand
owner 69/69, affected semantic 1,210/1,210, reflection promotion 15/15,
reflection capability 24/24, retrieval-pipeline 1/1, reconciliation plan 51/51,
import 19/19, runtime audit 217, and full 2,103/2,103 passed. Pycompile,
production transform 2/2, complete transform 3/3, selected-body/four-caller
parity, graph-test AST 246/246 plus four methods, public identity 2/2, all four
calls/two modules, unchanged 48-module/205-edge DAG, retired production refs/
public stores zero, UTF-8 3/3, non-ASCII 2/2, and diff check passed. Benchmark
refresh and remote CI were **NOT RUN**. This visibility-only milestone proves no
quality, ranking, performance, benchmark, schedule, ledger, or Phase 3
completion claim.

## Completed Percent-Metric-Label Public API

Commit `1c8400f` renamed the exact former 8-line classifier in place to public
`financial_operation_policies.label_implies_percent_metric(...)`. No wrapper or
private alias remains. Input truth/empty-string fallback, string conversion,
normalization, blank early return, configured-marker plus `"%"`/`"%p"` tuple
construction, marker order/duplicates/identity, lazy membership, first-truthy
stop, immutability, and uncaught owner failures are unchanged after definition-
name normalization.

All five calls across four importers now bind the public owner with one
positional argument, no keywords, and caller `try` depth zero. Unit-family
inference, operand conflict detection's two short-circuited classifications,
reconciliation unit hinting, and candidate selected-unit projection retain
their exact gates, arguments, true/false adoption, and failure stops.
Normalization, unit policy/selection, conflict/adoption, reconciliation,
candidate/evidence, state, artifacts, and ledgers did not move. Operation-policy
counts finish 3/4.

Production source is `+10/-10`, tests are `+1,196/-28`, and the whole commit is
`+1,206/-38`; production physical lines are unchanged. Four new methods moved
discovery from 2,095 to 2,099. The committed source/test diff SHA-256 is
`0f772a3b30a68ebfeb08ef66c4ebcef6778d59d0a457040c341927981e421917`.

Focused pre/post rename 4/4, graph owner 246/246, surface owner 1/1, operand
owner 69/69, affected semantic 1,206/1,206, reflection promotion 15/15,
reflection capability 24/24, retrieval-pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, and full 2,099/2,099 passed. Pycompile, production
transform 5/5, complete transform 8/8, selected-body/four-caller parity,
existing graph-test AST 242/242 plus four methods, public identity 5/5, all five
calls/four importers, unchanged 48-module/205-edge DAG, retired production
refs/public stores zero, UTF-8 8/8, non-ASCII 5/5, and diff check passed.
Benchmark refresh and remote CI were **NOT RUN**. This milestone changes only
API visibility and structural baselines; it proves no behavior, quality,
ranking, performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Narrative-Context-Query Public API

Commit `1883395` renamed the exact former 6-line classifier in place to public
`financial_operation_policies.query_requests_narrative_context(...)`. No
wrapper or private alias remains. Input truth/empty-string fallback,
conversion/normalization/lowercase order, blank early return, policy lookup,
marker-container truth, eager tuple construction with retained-item double
conversion, lazy membership, first-truthy stop, immutability, and uncaught owner
failures are unchanged after definition-name normalization.

All 18 calls across five importers now bind the public owner with one positional
argument, no keywords, and caller `try` depth zero. Nine calculation callers,
five evidence callers, hybrid-task admission, compression guidance, and two
text-surface projections retain their exact gates, false-result returns,
adoption, and failure stops. Evidence/result mutation, retrieval, calculation,
state, artifacts, and ledgers did not move. Operation-policy counts finish 2/5.

Production source is `+24/-24`, tests are `+1,467/-76`, and the whole commit is
`+1,491/-100`, net `+1,391`; production physical lines are unchanged. Four new
methods moved discovery from 2,091 to 2,095. The committed source/test diff
SHA-256 is
`653a3d7733bb763cb69a1163293a20bbb6171a022c99ceb80d1375260021bcb4`.

Focused pre/post rename 4/4, graph owner 242/242, surface owner 1/1, operand
owner 69/69, affected semantic 1,202/1,202, answer-projection 23/23, retrieval-
hints 5/5, text-surface 30/30, reflection capability 24/24, retrieval-pipeline
1/1, reconciliation plan 51/51, import 19/19, audit 217, and full 2,095/2,095
passed. Pycompile, production transform 6/6, complete transform 12/12,
selected-body/18-caller parity, existing graph-test AST 238/238 plus four
methods, public identity 6/6, all 18 calls/five call modules, unchanged 48-
module/205-edge DAG, retired live refs/public stores zero, UTF-8 12/12, non-
ASCII 9/9, and diff check passed. Benchmark refresh and remote CI were **NOT
RUN**. This milestone changes only API visibility and structural baselines; it
proves no behavior, quality, ranking, performance, benchmark, schedule, ledger,
or Phase 3 completion claim.

## Completed Ratio-Percent-Query Public API

Commit `f010b6f` renamed the exact former 3-line classifier in place to public
`financial_operation_policies.is_ratio_percent_query(...)`. No wrapper or
private alias remains. Input identity into normalization, subsequent policy-
marker lookup, marker-container truth and empty-tuple fallback, lazy membership
iteration, first-truthy short circuit, immutability, and uncaught owner failures
are unchanged after definition-name normalization.

All seven calls across four importers now bind the public owner with one
positional argument and no keywords. Six callers remain at `try` depth zero;
the calculation call remains at depth one behind its missing-operand/no-direct-
grounding gates and existing broad fallback handler. Evidence admission,
operation-family inference, supplemental scoring, missing-info projection,
reflection objective selection, ratio operand fallback, graph state, artifacts,
and ledgers did not move. Operation-policy counts finish 1/6.

Production source is `+12/-12`, tests are `+1,446/-12`, and the whole commit is
`+1,458/-24`, net `+1,434`; production physical lines are unchanged. Four new
methods moved discovery from 2,087 to 2,091. The committed source/test diff
SHA-256 is
`53eea332fd2447c3ccde0c16e20ae1ccb5c2a5cb48a82a11f3c64746636d044c`.

Focused pre/post rename 4/4, graph owner 238/238, surface owner 1/1, operand
owner 69/69, affected semantic 1,198/1,198, reflection capability 24/24,
retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217, and
full 2,091/2,091 passed. Pycompile, production transform 5/5, complete transform
7/7, selected-body/seven-caller parity, existing graph-test AST 234/234 plus
four methods, public identity 5/5, all seven calls/four call modules, unchanged
48-module/205-edge DAG, retired live refs/public stores zero, UTF-8 7/7, non-
ASCII 6/6, and diff check passed. Benchmark refresh and remote CI were **NOT
RUN**. This milestone changes only API visibility and structural baselines; it
proves no behavior, quality, ranking, performance, benchmark, schedule, ledger,
or Phase 3 completion claim.

## Completed Structured-Cell Period-Text Public API

Commit `89227aa` renamed the exact former 35-line helper in place to public
`financial_structured_cells.structured_cell_period_text(...)`. No wrapper or
private alias remains. Policy-copy/marker construction order, repeated marker
and header conversion, report/query-year precedence, narrow integer-conversion
handling, current/prior projection, fiscal-rank/header fallback, immutability,
and uncaught failures are unchanged after definition-name normalization.

All four calls across four importers now bind the public owner with three
positional arguments, no keywords, and caller `try` depth zero. Every importer
shares the exact owner identity; selected-cell scoring, direct acceptance,
lookup realignment, reconciliation fallback/pairing, evidence adoption, graph
state, artifacts, and ledgers did not move. Structured-cell counts finish 5/3.
Production source is `+9/-9`, tests are `+1,670/-45`, and the whole commit is
`+1,679/-54`, net `+1,625`; production physical lines are unchanged. Four new
methods moved discovery from 2,083 to 2,087. The committed source/test diff
SHA-256 is
`ce057382b96c939e60bd0e2f6d14d1773e0c4cd2f759c7bc8983cc65847ed938`.

Focused pre/post rename 4/4, graph owner 234/234, surface owner 1/1, operand
owner 69/69, affected semantic 1,194/1,194, additional retrieval-pipeline 1/1,
reconciliation plan 51/51, import 19/19, audit 217, and full 2,087/2,087 passed.
Pycompile, production transform 5/5, source/test transform 9/9, selected-body/
four-caller parity, existing graph-test AST 230/230 plus four methods, public
identity 5/5, all four calls/four call modules, unchanged 48-module/205-edge
DAG, retired live refs/public stores zero, UTF-8 9/9, non-ASCII 7/7, and diff
check passed. Benchmark refresh and remote CI were **NOT RUN**. This milestone
changes only API visibility and structural baselines; it proves no behavior,
quality, ranking, performance, benchmark, schedule, ledger, or Phase 3
completion claim.

## Completed Unstructured-Table-Row Parser Public API

Commit `ac90a62` renamed the exact former 47-line helper in place to public
`financial_row_surfaces.parse_unstructured_table_row_cells(...)`. No wrapper or
private alias remains. Row/header/period fallback order, repeated conversions,
numeric filtering, labeled-value regex/group order, fresh cell construction,
immutability, and uncaught failures are unchanged after definition-name
normalization.

All seven calls across five importers now bind the public owner with two
positional arguments, no keywords, and caller `try` depth zero. External/local
calls finish 7/0 across six caller definitions, and all five importers share the
exact owner identity. Row counts finish 20/6. Production source is `+13/-13`,
tests are `+1,511/-48`, and the whole commit is `+1,524/-61`, net `+1,463`;
production physical lines are unchanged. Four methods moved discovery from
2,079 to 2,083. The committed source/test diff SHA-256 is
`8faf60239bc6d907001d3144dadd2aa5201e7fb6e0c701b4a9c02e09439fef17`.

Focused pre/post rename 4/4, graph owner 230/230, surface owner 1/1, operand
owner 69/69, affected semantic 1,190/1,190, additional retrieval-pipeline 1/1,
reconciliation plan 51/51, import 19/19, audit 217, and full 2,083/2,083 passed.
Pycompile, production transform 6/6, source/test transform 10/10, selected-body/
six-caller parity, existing graph-test AST 226/226 plus four methods, public
identity 6/6, all seven calls/five call modules, unchanged 48-module/205-edge
DAG, retired live refs/public stores zero, UTF-8 10/10, non-ASCII 9/9, and diff
check passed. Benchmark refresh and remote CI were **NOT RUN**. This milestone
changes only API visibility and structural baselines; it proves no behavior,
quality, ranking, performance, benchmark, schedule, ledger, or Phase 3
completion claim.

## Completed Structured-Candidate-Row-Text Public API

Commit `72eb1b8` renamed the exact former 24-line helper in place to public
`financial_row_surfaces.format_structured_candidate_row_text(...)`. No wrapper
or private alias remains. Label/header eager expansion, ordered dedupe,
repeated retained-header normalization, eager header/value/unit construction,
exact slash/space/pipe joins, truth-gated cell append without dedupe,
immutability, and uncaught failures are unchanged after definition-name
normalization.

Both calls in graph helpers now bind the public owner with three positional
arguments, no keywords, and caller `try` depth zero. External/local calls finish
2/0 across two caller definitions, and the sole external importer shares the
exact owner identity. Row counts finish 19/7. Production source is `+4/-4`,
tests are `+1,150/-22`, and the whole commit is `+1,154/-26`, net `+1,128`;
production physical lines are unchanged. Four methods moved discovery from
2,075 to 2,079. The committed source/test diff SHA-256 is
`c3cbf8676f4e5df9b66101acdaf05070adf07eb6a3e702de883e65f2557e6789`.

Focused pre/post rename 4/4, graph owner 226/226, surface owner 1/1, operand
owner 69/69, affected semantic 1,186/1,186, additional retrieval-pipeline 1/1,
reconciliation plan 51/51, import 19/19, audit 217, and full 2,079/2,079 passed.
Pycompile, production transform 2/2, source/test transform 3/3, selected-body/
two-caller parity, existing graph-test AST 222/222 plus four methods, public
identity 2/2, both calls/the sole call module, unchanged 48-module/205-edge DAG,
retired live refs/public stores zero, UTF-8/non-ASCII preservation 3/3, and
diff check passed. Benchmark refresh and remote CI were **NOT RUN**. This
milestone changes only API visibility and structural baselines; it proves no
behavior, quality, ranking, performance, benchmark, schedule, ledger, or Phase
3 completion claim.

### Structured-candidate-row-text characterization checkpoint

The historical checkpoint below predates `72eb1b8`; it is retained only as an
audit record and is not active or competing work.

That historical inventory selected the smaller of the two remaining
cross-module private-API seams: rename the exact current 24-line
`financial_row_surfaces._format_structured_candidate_row_text(label: str, headers: List[str], cells: List[Dict[str, Any]]) -> str`
definition in place to public `format_structured_candidate_row_text(...)`.
Add no wrapper or private alias. The 47-line unstructured-table parser remains
private and outside this batch; this document maintains no competing
implementation queue. It required four CURRENT-SOURCE contracts before the
rename; no production or test rename had occurred at that checkpoint.

The four top-level statements, one annotated assignment, three plain
assignments, two `for` nodes, two `if` nodes, one return, 19 calls, four list
nodes, one starred item, two generator expressions, five boolean operations,
two comprehension clauses, and absence of `try`, lambda, and list-comprehension
nodes are normative. Initialize one fresh `row_parts` list, then eagerly build
and iterate exact `[label, *headers]`. For each item, preserve exact
`_normalise_spaces(str(part or ""))`; append a cleaned result only when it is
truthy and not already in `row_parts`. Preserve raw truth before string
conversion, header expansion before the first normalization, left-to-right
membership/equality behavior, duplicate suppression, and the first cleaned
representative's identity.

Iterate `cells` left to right. Build each three-item `cell_parts` list eagerly:
first exact `" / ".join(...)` over `cell.get("column_headers") or []`, then the
normalized `value_text`, then the normalized `unit_hint`. The header generator
keeps separate `_normalise_spaces(str(item))` calls in its filter and retained
expression, so a retained item is stringified and normalized twice while a
falsey normalized item is processed once. Preserve exact mapping access/truth,
header iteration, slash join, and value-before-unit order.

For each cell, preserve exact
`_normalise_spaces(" ".join(part for part in cell_parts if part))`, append every
truthy cleaned cell without dedupe, and finally return exact
`" | ".join(row_parts)`. Preserve generator truth/filter order, all join inputs,
input and nested-object immutability, absence of new caching or coercion, and
every uncaught header-expansion, truth, string, normalization, membership,
iteration, mapping, generator, and join failure.

There are two direct external `ast.Name` calls in one importer and two caller
definitions, both with three positional arguments, no keywords, and caller
`try` depth zero. `_build_table_value_reconciliation_candidates(...)` passes
exact `semantic_label`, `row_headers`, and a newly materialized
`list(candidate["metadata"]["structured_cells"] or [])`, assigns the exact
result to candidate metadata, and appends only after a successful call.
`_build_table_row_reconciliation_candidates(...)` passes exact `row_label`,
`row_headers`, and `cells`, assigns the result, then owns row-text
normalization, seen-set adoption, candidate append, and every exception stop.

The sole importer already reaches row surfaces, so the rename changes no module
edge and the full DAG remains acyclic at 48 modules/205 internal edges.
Current/projected row-owner counts are 18/8 to 19/7. No future public-name
definition or `ast.Store` collision exists. The selected body SHA-256 is
`596e6a345e220615c487d56760d77ff26b1cac1ed5721301c16f7ddf15e0a127`.
The private identifier has four production AST references across two source
files. Its two call records hash to
`94d6117e87e0b34cd34de7ba66388aa526ab2b6b0ff5655652c05fadf36ab407`;
the two caller bodies currently hash to
`86812eedef98ec6d9c26017312596c637872e898e3d9be1c86eeacec9fd28f9a`
and `2ef9302c59726decfb3b9429850e54cf757923b56406c7a66b4ed10dc29b7443`.
Existing exact test references are two patch-name constants in one graph-helper
method, so the bounded source/test transform is three files.

The current 304-327 definition span selects no runtime-domain baseline record.
Its exact string literals are `""`, `" "`, `" / "`, `" | "`,
`"column_headers"`, `"value_text"`, and `"unit_hint"`; it owns no integer
literal. The rename moves no line or literal, so all 217 reviewed records must
remain unchanged.

Add exactly these four CURRENT-SOURCE methods to `FinancialGraphHelperTests`:

- `test_current_source_format_structured_candidate_row_text_pins_label_header_cell_order_dedupe_and_result`;
- `test_current_source_format_structured_candidate_row_text_pins_laziness_repeated_header_normalization_immutability_and_exceptions`;
- `test_current_source_format_structured_candidate_row_text_bindings_pin_owner_def_calls_dag_imports_and_baseline`;
- `test_current_source_format_structured_candidate_row_text_callers_pin_args_adoption_and_stops`.

Projected post-rename gates are focused 4/4, graph owner 226/226, surface-
contract owner 1/1, operand owner 69/69, affected eleven-module semantic set
1,186/1,186, additional retrieval-pipeline caller module 1/1, reconciliation
plan 51/51, import side effects 19/19, runtime audit 217, and full discovery
2,079/2,079. Structural gates are exact production transform parity 2/2 and
source/test transform parity 3/3, selected-body and two-caller parity, fresh
public identity 2/2, both calls/the sole call module, unchanged acyclic
48-module/205-edge DAG, retired production/private live-test refs and future public
stores zero, existing graph-test AST parity 222/222 plus four new methods,
UTF-8/non-ASCII preservation 3/3,
pycompile, and `git diff --check`. These are projections, not executed results.
Static definition/signature/call/import/count/DAG/audit inspection passed;
benchmark refresh and remote CI were **NOT RUN**.

## Completed Numeric-Value-After-Operand-Text Public API

Commit `7739ab0` renamed the exact former 16-line private helper in place to
public `financial_row_surfaces.extract_numeric_value_after_operand_text(...)`.
Its four top-level statements, five assignments, four `if` nodes, one loop, two
continues, three returns, nine calls, one generator, one lambda, normalization,
needle compaction, escaped spaced-pattern construction, search, candidate
projection, stable distance sort, and first `[0][1]` result are unchanged after
definition-name normalization. No wrapper or compatibility alias was added.

All five calls across graph calculation, graph evidence, and operand resolution
now bind the public API with two positional arguments, no keywords, and caller
`try` depth zero. External/local calls finish 5/0 across three caller
definitions, and all three external importers share the row-owner function
identity. Caller accumulation, precedence, filtering, dedupe, later work, and
exception stops remain caller-owned.

Production source is `+9/-9`, net `0`; tests are `+1,418/-31`, net `+1,387`;
and the whole commit is `+1,427/-40`, net `+1,387`. Production physical line
counts are unchanged. Four methods moved discovery from 2,071 to 2,075. Final
row counts are 18/8. The committed source/test diff SHA-256 is
`0c1e7bbee0516f8afcc9579c0d66837d586a25522b1e9bb05812e3b5b6daa763`.

Focused pre/post rename 4/4, graph owner 222/222, surface owner 1/1, operand
owner 69/69, affected eleven-module semantic 1,182/1,182, additional retrieval-
pipeline 1/1, reconciliation plan 51/51, import-side-effects 19/19, runtime audit
217, and full discovery 2,075/2,075 passed. Pycompile, production transform
4/4, source/test transform 8/8, selected-body/three-caller parity, existing
graph-test AST 218/218 plus four new methods, public identity 4/4, all five
calls/three modules, zero public stores and retired live refs, unchanged acyclic
48-module/205-edge DAG, UTF-8/non-ASCII preservation 8/8, and diff check passed.
Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only API visibility and recorded structural baselines.
It proves no behavior, quality, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Operand-Text-Match Public API

Commit `6f28f8b` renamed the exact former 16-line private helper in place to public
`financial_row_surfaces.operand_text_match(...)`. Its four top-level statements,
three assignments, two `if` nodes, three loops, three returns, five calls,
variant/needle iteration, per-haystack fresh needle lookup, exact/substring/
compact short-circuit order, exact bool results, and selected body are unchanged
after definition-name normalization. No wrapper or compatibility alias was
added.

All 62 calls across ten source modules now bind the public API with two
positional arguments, no keywords, and caller `try` depth zero. External/local
calls finish 59/3 across 36 caller definitions, and all nine external importers
share the row-owner function identity. Caller gates, scoring, append/fallback,
result adoption, later work, and exception stops remain caller-owned.

The characterize checkpoint counted the 103 exact references in 32 existing
graph-helper methods. Execution additionally found 30 live patch/import
references across five non-graph test modules; those were migrated too. Thus
the verified source/test transform surface is 16 files, not the projected 11.
One task-artifact test keeps the retired spelling only as a negative source-text
assertion, and the four new contracts retain it only for transition checks;
production executable refs and existing live test bindings are zero.

Production source is `+72/-72`, net `0`; tests are `+1,630/-158`, net `+1,472`;
and the whole commit is `+1,702/-230`, net `+1,472`. Production physical line
counts are unchanged. Four methods moved discovery from 2,067 to 2,071. Final
row counts are 17/9. The committed source diff SHA-256 is
`994ebce19f931072d564b7e12678100b79648799b0c09342b4d5e50c65c80a08`.

Focused pre/post rename 4/4, graph owner 218/218, surface owner 1/1, operand
owner 69/69, affected eleven-module semantic 1,178/1,178, additional retrieval-
pipeline 1/1, reconciliation plan 51/51, import-side-effects 19/19, runtime audit
217, and full discovery 2,071/2,071 passed. The additional changed-consumer
union passed 246/246. Pycompile, production transform 10/10, full transform
16/16, selected-body/36-caller parity, existing graph-test AST 214/214 plus four
new methods, public identity 10/10, all 62 calls/ten modules, zero public stores
and retired production refs, unchanged acyclic 48-module/205-edge DAG, UTF-8
decode 16/16, non-ASCII preservation 12/12, and diff check passed. Benchmark
refresh and remote CI were **NOT RUN**.

This milestone changes only API visibility and recorded structural baselines.
It proves no behavior, quality, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Surface-Match-Variants Public API

Commit `05415ed` renamed the exact former 11-line private helper in place to
public `financial_row_surfaces.surface_match_variants(...)`. Its four top-level
statements, one `if`, two returns, one generator expression, and selected body
are exact after definition-name normalization. The private definition and
executable refs are gone; no wrapper or compatibility alias was added.

All nine calls across row surfaces, graph calculation, and operand resolution
now bind the public API at caller `try` depth zero. External/local calls are 7/2
across six caller definitions. Raw/normalized truth, blank fresh-list return,
eager annotation/period order, repeated annotation call, truth/hash/equality
order, first-representative identity, caller assignment/iteration/set/lazy-any
adoption, fallback, scoring, and exception stops remain unchanged.

Production source is `+12/-12`, net `0`; tests are `+1,514/-42`, net `+1,472`;
and the whole commit is `+1,526/-54`, net `+1,472`. Production physical line
counts are unchanged. Four methods moved discovery from 2,063 to 2,067. Final
row counts are 16/10; operand resolution remains 54/37. The committed source
diff SHA-256 is
`a49845578a7a70c8479ac01921d75bc30bdd7631799a2ab0498a59511619e7d9`.

Focused pre/post rename 4/4, graph owner 214/214, surface owner 1/1, operand
owner 69/69, affected eleven-module semantic 1,174/1,174, additional retrieval-
pipeline 1/1, reconciliation plan 51/51, import-side-effects 19/19, runtime audit
217, and full discovery 2,067/2,067 passed. Pycompile, production transform
3/3, selected-body and six caller bodies, existing graph-test AST parity
210/210 plus four new methods, public identity 3/3, all nine calls/three modules,
zero public stores/retired exact private refs, unchanged acyclic 48-module/
205-edge DAG, UTF-8/non-ASCII preservation 4/4, and diff check passed.
Intermediate graph-owner runs exposed only expected static count/hash/method
baselines before the final pass. Benchmark refresh and remote CI were **NOT
RUN**.

This milestone changes only API visibility and recorded structural baselines.
It proves no behavior, quality, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Leading-Period-Qualifier Public API

Commit `98aee5a` renamed the exact former 14-line private helper in place to
public `financial_row_surfaces.strip_leading_period_qualifiers(...)`. Its six
top-level statements, two `if` nodes, two returns, one `while`, and one `break`
are exact after definition-name normalization. The private definition and
executable refs are gone; no wrapper or compatibility alias was added.

All four calls across row surfaces and aggregate projection now bind the public
API at caller `try` depth zero. External/local calls are 1/3. Raw truth,
normalization/blank stop, exact regex compilation, one-prefix-at-a-time
sub/strip/equality looping, immediate-stability and adopted-result identities,
eager row variants, sibling-surface scoring, aggregate stripped-label
expansion, caller adoption, and exception stops remain unchanged.

Production source is `+6/-6`, net `0`; tests are `+1,124/-25`, net `+1,099`;
and the whole commit is `+1,130/-31`, net `+1,099`. Production physical line
counts are unchanged. Four methods moved discovery from 2,059 to 2,063. Final
row-owner counts are 15/11; aggregate projection remains 76/12 with 19 classes.
The committed source diff SHA-256 is
`5556c032ed6fde19f06863ab5833bb919ae1a90189e8b09c1adfa4f2bb2a5307`.

Focused pre/post rename 4/4, graph owner 210/210, surface owner 1/1, operand
owner 69/69, affected eleven-module semantic 1,170/1,170, additional retrieval-
pipeline 1/1, reconciliation plan 51/51, import-side-effects 19/19, runtime audit
217, and full discovery 2,063/2,063 passed. Pycompile, exact production
transform parity 2/2, selected-body and three caller-body parity, existing
graph-test AST parity 206/206 plus four new methods, existing subtask-loop AST
parity 252/252, fresh public identity 1/1, all four calls/two modules, zero
public stores/retired exact private refs, unchanged acyclic 48-module/205-edge
DAG, UTF-8/non-ASCII preservation 4/4, and `git diff --check` passed. Intermediate
owner runs exposed only the expected stale row-count, caller-hash, and prior
method-count baselines before the final pass. Benchmark refresh and remote CI
were **NOT RUN**.

This milestone changes only API visibility and recorded structural baselines.
It proves no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Financial-Label-Annotation Public API

Commit `472906e` renamed the exact former 9-line private helper in place to
public `financial_row_surfaces.strip_financial_label_annotations(...)`. Its
five top-level statements, one `if`, and two returns are exact after
definition-name normalization. The private definition and executable refs are
gone; no wrapper or compatibility alias was added.

All five calls across row surfaces, graph helpers, and operand resolution now
bind the public API at caller `try` depth zero. External/local calls are 3/2,
and both external bindings are live. Raw truth, normalization/blank stop,
annotation regex, whitespace collapse/strip, exact result identities, eager
variant order, aggregate query expansion, needle-set membership/scoring,
caller adoption, and exception stops remain unchanged.

Production source is `+8/-8`, net `0`; tests are `+1,308/-11`, net `+1,297`;
and the whole commit is `+1,316/-19`, net `+1,297`. Production physical line
counts are unchanged. Four methods moved discovery from 2,055 to 2,059. Final
row-owner counts are 14/12; graph helpers remain 9/71 and operand resolution
54/37. The source diff SHA-256 is
`fa6221e4d52b393bc3d6d7103a586bc9b09e55b4d8c2e23c153b7caa8057e5d3`.

Focused pre/post rename 4/4, graph owner 206/206, surface owner 1/1, operand
owner 69/69, affected eleven-module semantic 1,166/1,166, additional retrieval-
pipeline caller module 1/1, reconciliation plan 51/51, import-side-effects
19/19, runtime-domain audit 217, and full discovery 2,059/2,059 passed.
Pycompile, exact production transform parity 3/3, selected-body and three caller
hashes, existing graph-test AST parity 202/202 plus four new methods, fresh
public identity 2/2, all five calls/three modules, zero public-name stores and
retired exact private refs, unchanged 48-module/205-edge acyclic DAG, UTF-8/
non-ASCII preservation 4/4, and `git diff --check` also passed. The first graph-
owner run reported only nine stale row public/private count baselines; their
exact 14/12 updates produced the final 206/206 pass. Benchmark refresh and
remote CI were **NOT RUN**.

This milestone changes only API visibility and recorded structural baselines.
It proves no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Table-Row-Label Public API

Commit `786a356` renamed the exact former 9-line private helper in place to
public `financial_row_surfaces.extract_table_row_label(...)`. Its four top-level
statements, three `if` nodes, and three returns are exact after definition-name
normalization. The private definition and executable refs are gone; no wrapper
or compatibility alias was added.

All three calls across graph evidence, graph helpers, and graph reconciliation
now bind the public API at caller `try` depth zero. External/local calls are
3/0, and all three bindings are live. Raw-argument normalization, blank stop,
delimiter membership/split, exact normalized/first-cell identities, caller
adoption, earlier mutations, later work, and exception stops remain unchanged.

Production source is `+7/-7`, net `0`; tests are `+1,224/-9`, net `+1,215`;
and the whole commit is `+1,231/-16`, net `+1,215`. Production physical line
counts are unchanged. Four methods moved discovery from 2,051 to 2,055. Final
row-owner counts are 13/13. The source diff SHA-256 is
`3406b381e79434e1f1b9550e568be93dff39fefd326dbb29a5dd01fab3804c0c`.

Focused pre/post rename 4/4, graph owner 202/202, surface owner 1/1, operand
owner 69/69, affected eleven-module semantic 1,162/1,162, additional retrieval-
pipeline caller module 1/1, reconciliation plan 51/51, import-side-effects
19/19, runtime-domain audit 217, and full discovery 2,055/2,055 passed.
Pycompile, exact production transform parity 4/4, selected-body and three caller
hashes, existing graph-test AST parity 198/198 plus four new methods, fresh
public identity 3/3, all three calls/importers, zero public-name stores and
retired exact private refs, unchanged 48-module/205-edge acyclic DAG, UTF-8/
non-ASCII preservation 5/5, and `git diff --check` also passed. The first graph-
owner run reported only eight stale row public/private count baselines; their
exact 13/13 updates produced the final 202/202 pass. Benchmark refresh and
remote CI were **NOT RUN**.

This milestone changes only API visibility and recorded structural baselines.
It proves no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Generic-Column-Header Public API

Commit `ea830ed` renamed the exact former 2-line private helper in place to
public `financial_row_surfaces.generic_column_headers()`. Its one-return body is
exact after definition-name normalization. The private definition and
executable refs are gone; no wrapper or compatibility alias was added.

Both calls across the row and structured-cell owners now bind the public API at
caller `try` depth zero. External/local calls are 1/1. The structured-cell
binding is live. Policy get/`or ()`, generator-under-set laziness, dropped-once
and retained-twice stringification, exact second-result insertion, duplicate
collapse, fresh sets, caller adoption, and exception stops remain unchanged.

Production source is `+4/-4`, net `0`; tests are `+804/-31`, net `+773`; and the
whole commit is `+808/-35`, net `+773`. Production physical line counts are
unchanged. Four methods moved discovery from 2,047 to 2,051. Final counts are
row surfaces 12/14 and structured cells 4/4. The source diff SHA-256 is
`5b953b411edaf1fd53ac437179eb1a24dac17960398f6df64bfa6d50676cc37c`.

Focused pre/post rename 4/4, graph owner 198/198, surface owner 1/1, operand
owner 69/69, affected eleven-module semantic 1,158/1,158, additional retrieval-
pipeline caller module 1/1, reconciliation plan 51/51, import-side-effects
19/19, runtime-domain audit 217, and full discovery 2,051/2,051 passed on the
final bytes. Pycompile, exact production transform parity 2/2, selected-body
and two caller hashes, existing graph-test AST parity 194/194 plus four new
methods, fresh public identity 1/1, both calls/two modules, zero public-name
stores and retired exact private refs, unchanged 48-module/205-edge acyclic DAG,
UTF-8/non-ASCII preservation 3/3, and `git diff --check` also passed. Benchmark
refresh and remote CI were **NOT RUN**.

This milestone changes only API visibility and recorded caller-body hashes. It
proves no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Operand Surface-Contract Public API

Commit `5b71fd6` renamed the exact former 22-line private helper in place to
public `financial_surface_contracts.operand_surface_contract(...)`. Its eight-
statement body is exact after definition-name normalization. The private
definition and executable refs are gone; no wrapper or compatibility alias was
added.

All seven calls across operand resolution and the surface owner now bind the
public API at caller `try` depth zero. External/local calls are 2/5. Operand
resolution is a live caller and graph helpers remains an import-only binding.
Explicit-contract priority, fresh positive/negative projection, copied legacy-
policy concept lookup, ordered operand-needle fallback, exact identities,
copies, laziness, later work, and exception stops remain unchanged.

Production source is `+10/-10`, net `0`; tests are `+1,185/-85`, net `+1,100`;
and the whole commit is `+1,195/-95`, net `+1,100`. All production physical
line counts are unchanged. Four methods moved discovery from 2,043 to 2,047.
Final public/private counts are surface contracts 21/1, graph helpers 9/71,
and operand resolution 54/37. The source diff SHA-256 is
`0e9efc0d6d5f8d131a762c1200b77e470f91e598d2db4d51d08da6dc096a866b`.

Focused pre/post rename 4/4, graph owner 194/194, surface owner 1/1, operand
owner 69/69, affected eleven-module semantic 1,154/1,154, additional retrieval-
pipeline caller module 1/1, reconciliation plan 51/51, import-side-effects
19/19, runtime-domain audit 217, and full discovery 2,047/2,047 passed.
Pycompile, exact production transform parity 3/3, selected-body and two
dependent-wrapper hashes, existing graph-test AST parity 190/190 plus four new
methods, fresh public identity 2/2, all seven calls/two call modules plus the
import-only binding, zero public-name stores and retired exact private refs,
unchanged 48-module/205-edge acyclic DAG, UTF-8/non-ASCII preservation 4/4, and
`git diff --check` also passed. The first graph-owner run reported only two
stale raw wrapper-hash expectations; updating them to the exact renamed caller
bodies produced the final 194/194 pass. Benchmark refresh and remote CI were
**NOT RUN**.

This milestone changes only API visibility and recorded caller-body hashes. It
proves no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Text Contract-Term Public API

Commit `faf75a0` renamed the exact former 13-line private helper in place to
public `financial_surface_contracts.text_has_contract_term(...)`. Its five-
statement body is byte-equivalent after definition-name normalization. The
private definition and executable refs are gone; no wrapper or compatibility
alias was added.

All four calls across operand resolution and the surface owner now bind the
public API. External/local calls are 1/3, and the sole external binding is a
live caller. Exact arguments, return identity, positive/negative list
construction, generator filtering/short-circuiting, later work, and exception
stops remain in their existing callers.

Production source is `+6/-6`, net `0`; tests are `+964/-46`, net `+918`; and the
whole commit is `+970/-52`, net `+918`. All production physical line counts are
unchanged. Four methods moved discovery from 2,039 to 2,043. Final public/private
counts are surface contracts 20/2, graph helpers 9/71, and operand resolution
54/37. The source diff SHA-256 is
`cca5735d1b0f269dc5ce7b4e3701c3fb448d6a25c3e655376b5400bea462d7e1`.

Focused pre/post rename 4/4, graph owner 190/190, surface owner 1/1, operand
owner 69/69, affected eleven-module semantic 1,150/1,150, additional retrieval-
pipeline caller module 1/1, reconciliation plan 51/51, import-side-effects
19/19, runtime-domain audit 217, and full discovery 2,043/2,043 passed.
Pycompile, exact production transform parity 2/2, selected-body SHA-256 parity,
dependent positive/negative wrapper hashes 2/2, existing graph-test AST parity
186/186 plus four new methods, fresh public identity 1/1, all four calls/two
call modules with no import-only binding, zero public-name stores and retired
private executable refs, unchanged 48-module/205-edge acyclic DAG, non-ASCII
preservation 3/3, and `git diff --check` also passed. The first graph-owner run
reported only two stale raw wrapper-hash expectations; updating those hashes to
the exact renamed caller bodies produced the final 190/190 pass. Benchmark
refresh and remote CI were **NOT RUN**.

This milestone changes only API visibility and recorded caller-body hashes. It
proves no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Positive-Surface Public API

Commit `a0c9a84` renamed the exact former 3-line private helper in place to
public `financial_surface_contracts.text_has_positive_surface(...)`. Its two-
statement body is byte-equivalent after definition-name normalization. The
private definition and executable refs are gone; no wrapper or compatibility
alias was added.

All twenty-six calls across graph calculation, graph evidence, lookup recovery,
operand resolution, retrieval pipeline, row surfaces, and the surface owner now
bind the public API. External/local calls are 25/1, and all six external
bindings are live callers. Exact arguments, boolean/generator/conditional
short-circuiting, operand copies, surface preparation, scoring/adoption, later
work, and exception stops remain in their existing callers.

Production source is `+33/-33`, net `0`; tests are `+1,234/-73`, net `+1,161`;
and the whole commit is `+1,267/-106`, net `+1,161`. All production physical
line counts are unchanged. Four methods moved discovery from 2,035 to 2,039.
Final public/private counts are surface contracts 19/3, graph helpers 9/71, and
operand resolution 54/37. The source diff SHA-256 is
`fa6ec5508e044215963811971024a2dfe60b375dec46b1435e57a9914163b0cb`.

Focused pre/post rename 4/4, graph owner 186/186, surface owner 1/1, operand
owner 69/69, affected eleven-module semantic 1,146/1,146, additional retrieval-
pipeline caller module 1/1, reconciliation plan 51/51, import-side-effects
19/19, runtime-domain audit 217, and full discovery 2,039/2,039 passed.
Pycompile, exact production transform parity 7/7, untouched-test transform
parity 2/2, selected-body SHA-256 parity, name-normalized owner parity 22/22,
existing graph-test AST parity 182/182 plus four new methods, fresh public
identity 6/6, all twenty-six calls/seven call modules with no import-only
binding, zero public-name stores and retired private executable refs, unchanged
48-module/205-edge acyclic DAG, non-ASCII preservation 10/10, and
`git diff --check` also passed. Benchmark refresh and remote CI were **NOT
RUN**.

This milestone changes only API visibility. It proves no behavior, accuracy,
ranking, performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Negative-Surface Public API

Commit `83cf700` renamed the exact former 3-line private helper in place to
public `financial_surface_contracts.text_has_negative_surface(...)`. Its two-
statement body is byte-equivalent after definition-name normalization. The
private definition and executable refs are gone; no wrapper or compatibility
alias was added.

All ten calls across graph evidence, operand resolution, retrieval pipeline,
and the surface owner now bind the public API. Five external bindings use the
same owner object; graph calculation and graph helpers remain import-only.
Exact arguments, boolean/generator short-circuiting, operand copies, surface
preparation, later adoption, and exception stops remain in their existing
callers.

Production source is `+16/-16`, net `0`; tests are `+990/-27`, net `+963`;
and the whole commit is `+1,006/-43`, net `+963`. All production physical line
counts are unchanged. Four methods moved discovery from 2,031 to 2,035. Final
public/private counts are surface contracts 18/4, graph helpers 9/71, and
operand resolution 54/37. The source diff SHA-256 is
`69d56b303cee0619864af4d3b446b2c344c7f61e035e4f2bea3a54e7a5184991`.

Focused pre/post rename 4/4, graph owner 182/182, surface owner 1/1, operand
owner 69/69, affected eleven-module semantic 1,142/1,142, additional retrieval-
pipeline caller module 1/1, reconciliation plan 51/51, import-side-effects
19/19, runtime-domain audit 217, and full discovery 2,035/2,035 passed.
Pycompile, exact production transform parity 6/6, selected-body SHA-256 parity,
name-normalized owner parity 22/22, fresh public identity 5/5, all ten calls/
four call modules with two import-only bindings, zero public-name stores and
retired private executable refs, unchanged 48-module/205-edge acyclic DAG,
non-ASCII preservation 8/8, and `git diff --check` also passed. Benchmark
refresh and remote CI were **NOT RUN**.

This milestone changes only API visibility. It proves no behavior, accuracy,
ranking, performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Operand-Needles Public API

Commit `ae964b3` renamed the exact former 4-line private helper in place to
public `financial_surface_contracts.operand_needles(...)`. Its three-statement
body is byte-equivalent after definition-name normalization. The private
definition and executable refs are gone; no wrapper or compatibility alias was
added.

All twenty-four calls across graph calculation, reconciliation, lookup
recovery, operand resolution, retrieval pipeline, row surfaces, structured
cells, task artifacts, and the surface owner now bind the public API. Exact
arguments, comprehension/loop/starred-list evaluation, fallback, normalization,
matching, score/adoption, later work, and exception stops remain in their
existing callers. The public name exposed one pre-existing same-name local list
in direct structured lookup scoring; that list alone is now the unambiguous
`normalized_operand_needles`, and the CURRENT-SOURCE caller contract forbids
future public-name stores.

Production source is `+36/-36`, net `0`; tests are `+998/-113`, net `+885`;
and the whole commit is `+1,034/-149`, net `+885`. All production physical line
counts are unchanged. Four methods moved discovery from 2,027 to 2,031. Final
public/private counts are surface contracts 17/5, graph helpers 9/71, and
operand resolution 54/37. The source diff SHA-256 is
`22b638bd5e610ab14088510908c9c39539f977935589cf1c70a6cdac99a84ef0`.

Focused pre/post rename 4/4, graph owner 178/178, surface owner 1/1, operand
owner 69/69, affected eleven-module semantic 1,138/1,138, additional caller
17/17, reconciliation plan 51/51, import-side-effects 19/19, runtime-domain
audit 217, and final full discovery 2,031/2,031 passed. Pycompile, exact
production transform parity 10/10, selected-body SHA-256 parity, name-normalized
owner parity 22/22, fresh public identity 9/9, all twenty-four calls/nine
modules, zero public-name stores, unchanged 48-module/205-edge acyclic DAG,
retired private refs zero, non-ASCII preservation 13/13, and `git diff --check`
also passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only API visibility and one shadow-safe local name. It
proves no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Operand Segment-Label Public API

Commit `cce5700` renamed the exact former 3-line private helper in place to
public `financial_surface_contracts.operand_segment_label(...)`. Its two-
statement body is byte-equivalent after definition-name normalization. The
private definition and executable refs are gone; no wrapper or compatibility
alias was added.

All thirteen calls across graph calculation, graph helpers, operand resolution,
row surfaces, and the surface owner now bind the public API. Exact arguments,
fallback/normalization, generator laziness, short-circuit returns, query/task
projection, reconciliation filtering/ranking, and exception stops remain in
their existing callers.

Production source is `+18/-18`, net `0`; tests are `+925/-63`, net `+862`; and
the whole commit is `+943/-81`, net `+862`. All production physical line counts
are unchanged. Four methods moved discovery from 2,023 to 2,027. Final public/
private counts are surface contracts 16/6, graph helpers 9/71, and operand
resolution 54/37. The source diff SHA-256 is
`416655cdf1c30a24afa9733cdeece140e43bf66016ad650af6ab8fb79808638e`.

Focused pre/post rename 4/4, graph owner 174/174, surface owner 1/1, operand
owner 69/69, affected eleven-module semantic 1,134/1,134, reconciliation plan
51/51, import-side-effects 19/19, runtime-domain audit 217, and full discovery
2,027/2,027 passed. The first full-discovery attempt hit only the 120-second
command limit; the identical command passed in 104.557 seconds with a 300-
second limit. Pycompile, exact production rename parity 5/5, selected-body hash
parity, fresh public identity 4/4, all thirteen calls/five modules, unchanged
48-module/205-edge acyclic DAG parity, retired private AST refs zero, non-ASCII
preservation 7/7, and `git diff --check` also passed. Benchmark refresh and
remote CI were **NOT RUN**.

This milestone changes only API visibility. It proves no behavior, accuracy,
ranking, performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Operand-Candidate Scorer Ownership

Commit `3d6986e` moved the exact former 315-line graph scorer to public
`financial_operand_resolution.score_operand_candidate(...)` with its 62-
statement/two-return/two-`try` body unchanged except for resolving the same-
owner aggregate-role helper by its public name. The private graph definition and
executable private refs are gone; no wrapper or compatibility bridge was added.

All seven calls across graph helpers, reconciliation, period-pair projection,
and ontology-shadow diagnostics now bind the public owner. Exact inputs, score/
key construction, sorting, pair selection, fallback, candidate/evidence
adoption, and exception stops remain caller-owned. The adjacent graph-owned
report-file/local-unit I/O helper did not move.

Production source is `+338/-356`, net `-18`; tests are `+1,542/-364`, net
`+1,178`; and the whole commit is `+1,880/-720`, net `+1,160`. Graph helpers
moved from 4,634 to 4,294 physical lines and operand resolution from 4,494 to
4,816. Four methods moved discovery from 2,019 to 2,023. Final public/private
counts are graph 9/71 and operand resolution 54/37. The source diff SHA-256 is
`2e681d92116eb7b6c213dc505ba61bddbb0aafe65b86eacf917bf4c28d594650`.

Focused pre/post movement 4/4, graph owner 170/170, operand owner 69/69,
affected eleven-module semantic 1,130/1,130, reconciliation plan 51/51,
import-side-effects 19/19, runtime-domain audit 217, and full discovery
2,023/2,023 passed. Pycompile, fresh public identity 4/4, helper-name-normalized
selected-body parity 1/1, retained graph exact 79/80 and call-normalized 80/80,
all 90 retained operand functions, all seven calls/four modules, full unchanged
48-module/205-edge acyclic DAG parity, retired private refs zero, non-ASCII
preservation, and `git diff --check` also passed. Benchmark refresh and remote
CI were **NOT RUN**.

This milestone changes only deterministic operand-candidate scoring ownership.
It proves no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Direct-Acceptance Ownership

Commit `6ebcf59` moved the exact former 161-line graph predicate to public
`financial_operand_resolution.candidate_satisfies_direct_acceptance_contract(...)`
with its nineteen-statement/seventeen-return/one-`try` body unchanged. The old
private definition and executable private refs are gone; no wrapper or
compatibility bridge was added.

All five calls across graph reconciliation, nested reconciliation, and period-
pair extraction now bind the public owner. Their direct-then-ratio laziness,
rejection stops, pair score/append, same-block fallback, candidate/cell adoption,
evidence work, and state sequencing remain caller-owned. Selected-cell
construction/selection, ratio acceptance, broad scoring/ranking, fallback,
evidence, I/O, and graph/artifact/ledger state did not move.

Production source is `+178/-175`, net `+3`; tests are `+1,631/-258`, net
`+1,373`; and the whole commit is `+1,809/-433`, net `+1,376`. Graph helpers
moved from 4,800 to 4,634 physical lines and operand resolution from 4,327 to
4,494. Four methods moved discovery from 2,015 to 2,019. Final public/private
counts are graph 9/72 and operand resolution 53/37. The source diff SHA-256 is
`2ed5b13b639fec8480de6594151a6fe63abdc9af776296d33d4e1614a9d51cc6`.

Focused pre/post movement 4/4, graph owner 166/166, operand owner 69/69,
affected eleven-module semantic 1,126/1,126, reconciliation plan 51/51,
import-side-effects 19/19, runtime-domain audit 217, and full discovery
2,019/2,019 passed. Pycompile, fresh public identity 3/3, exact selected-body
parity 1/1, retained graph exact 80/81 and call-normalized 81/81, all 89 retained
operand functions, all five calls/three caller modules, full 48-module/205-edge
acyclic DAG parity, retired private refs zero, non-ASCII preservation 9/9, and
`git diff --check` also passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic direct-acceptance ownership. It proves
no behavior, accuracy, ranking, performance, benchmark, schedule, ledger, or
Phase 3 completion claim.

## Historical Direct-Grounding Characterization And Ownership Milestone

Commit `4c422ed` completed the move described below. The exact former 86-line
predicate is now public operand-resolution ownership with no graph alias; all
three calls bind that owner. Focused 4/4, graph owner 162/162, operand owner
69/69, affected semantic 1,122/1,122, reconciliation plan 51/51, import
side-effects 19/19, audit 217, and full discovery 2,015/2,015 passed. The
following inventory records the pre-`4c422ed` checkpoint and is not active work.

The characterize-only inventory selected exactly one production follow-on. It
moved only the former exact 86-line
`_candidate_is_direct_grounding_candidate(candidate, *, operand, constraints,
query_years, operation_family="", report_scope=None)` definition from
`financial_graph_helpers.py` to the existing `financial_operand_resolution.py`
owner as public `candidate_is_direct_grounding_candidate(...)`. The completed
move left no graph alias or compatibility bridge.

At that checkpoint, no production source or test had moved. The predicate
classifies one already prepared candidate against kind, numeric, direct-match,
binding-shape, canonical-statement, consolidation, period, segment/report, and
lookup-table-row signals. It does not construct candidates or selected cells,
calculate the broad float score, sort or collapse a collection, run direct or
ratio acceptance, adopt an operand row, invoke a model, or read/write graph
state.

The destination already owns `_normalise_spaces`,
`lookup_prefers_canonical_statement_rows(...)`, and
`candidate_direct_match_strength(...)`; it already imports value-role/stage,
surface-contract, and scope-policy dependencies used by the predicate. Add
`is_delta_like_row_label(...)` and
`table_row_has_matching_structured_sibling(...)` to its existing row-surface
import and `candidate_consolidation_scope(...)` to its existing surface-contract
import. Graph helpers keep their still-used consolidation and delta imports,
drop only the structured-sibling import, and import the new public owner.
Reconciliation moves only this binding from its graph import to its existing
operand-resolution import. No module edge changes: the full DAG remains acyclic
at 48 modules/204 internal edges. Current public/private counts are graph helpers
9/74 and operand resolution 51/37; projected counts are 9/73 and 52/37. The
selected span contains zero of the 217 reviewed runtime-domain records.

Preserve the exact 30-statement body, fifteen returns, no `try`, required
positional `candidate`, three required and two optional keyword-only arguments,
and `bool` result. Shallow-copy candidate metadata first, then preserve raw
candidate-kind lookup/falsey fallback/string/strip and exact membership in the
four current structured/table kinds. Kind rejection stops descriptor and numeric
checks; those checks remain ordered and stop before direct-match strength. Keep
the single direct-strength call and exact `< 1.0` rejection before all binding,
statement, consolidation, and period work.

Preserve the fresh shallow binding-policy mapping, then value-role,
aggregation-stage, and statement-type projection in exact order before the
binding-shape gate. Its miss returns before canonical-statement policy. The
canonical table-row whitelist remains conditional on the existing operand
preference and exact table-row kind, with exact income/summary/notes membership.

Consolidation focus still prefers normalized constraints, falls back to the
copied binding policy only for exact `unknown`, and compares against one
candidate-consolidation result only when both sides are known. Period focus
likewise prefers the owner result with normalized constraint fallback, then the
binding-policy preference only for exact `unknown`. Preserve semantic-label
left-to-right fallback, one normalization call, and the first delta-label check
only for exact current/prior focus. A hit stops segment/report/year work.

Keep strict segment binding before target-report-scope matching. The report gate
receives a fresh shallow `dict(report_scope or {})`; candidate, operand,
constraints, query years, report scope, and nested objects otherwise retain their
current identities. After it passes, preserve candidate-period and normalized
row-text projection, exact `trust_candidate_period_focus` boolean precedence,
and one eager target-year call even when period focus will not be trusted. The
two current/prior mismatch checks remain nested under that trust gate.

The lookup/single-value table-row tail remains lazy: exact operation-family and
kind membership first, structured-sibling rejection next, then truthy row text
before the second delta-label call. Earlier misses must not evaluate later terms;
every surviving path returns exact `True`. There is no exception boundary.
Mapping access, truth, shallow copy, conversion, normalization, strip,
membership, helper calls/results, numeric comparison, and return failures remain
uncaught in current order, and all supplied objects remain unmodified.

The projection has three direct `ast.Name` calls at caller `try` depth zero.
`_candidate_satisfies_direct_acceptance_contract(...)` keeps the exact candidate
and five keyword inputs; false returns before selected-cell period/unit/direct-
strength acceptance work, while true continues unchanged.
`_deterministic_reconcile_task(...)` keeps the exact candidate, operand,
constraints, `years`, operation family, and report scope inside its ordered
non-lookup candidate filter; unique-candidate promotion, ambiguity/no-candidate
fallback, matched/missing rows, ranking, and adoption remain graph-owned. The
nested reconciliation `candidate_supports_operand(...)` call keeps exact
`current` plus operand, constraints, query years, and report scope, deliberately
omits operation family to retain the empty-string default, and returns on direct
acceptance before its ratio-only cell fallback. Candidate/cell construction,
cell selection, direct/ratio acceptance, collection scoring/collapse, fallback,
evidence work, state mutation, I/O, retry, and final sequencing are rejected from
this batch.

Before production movement, add exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_candidate_is_direct_grounding_candidate_pins_precedence_binding_scope_period_operation_and_result`;
- `test_current_source_candidate_is_direct_grounding_candidate_pins_laziness_identity_immutability_and_exceptions`;
- `test_current_source_candidate_is_direct_grounding_candidate_bindings_pin_owner_defs_calls_dag_imports_and_baseline`;
- `test_current_source_candidate_is_direct_grounding_candidate_callers_pin_args_adoption_fallback_and_stops`.

They must pin the exact definition/signature/body, every early gate and lazy
boolean chain, shallow copies, normalization/conversion order, thresholds,
consolidation and period truth tables, exact booleans, identities, immutability,
every uncaught failure, all three caller expressions/arguments/adoption/fallback/
stops, current/projected function counts, unchanged acyclic DAG, and zero
selected-body runtime-domain records.

Projected post-move gates are focused 4/4, graph-helper characterization owner
162/162, operand-resolution owner 69/69, affected eleven-module semantic set
1,122/1,122, reconciliation plan 51/51, import-side-effects 19/19, audit 217,
and full discovery 2,015/2,015, plus pycompile/fresh import and public identity,
selected-body parity 1/1, retained graph exact 80/82 and call-normalized 82/82,
all 88 retained operand-resolution functions, all three calls/two caller
modules, full 48-module/204-edge DAG parity, retired executable graph-private
refs zero, non-ASCII preservation, and `git diff --check`. These are projections
to verify, not completed results.

Static definition/call/DAG/function-count/import and selected-body audit
inspection passed. The ratio-component owner/full gates below remain the latest
executed runtime evidence. Benchmark refresh and remote CI were **NOT RUN**. This
characterization makes no behavior, accuracy, ranking, performance, benchmark,
schedule, ledger, or Phase 3 completion claim.

## Historical Ratio-Component-Acceptance Characterization Checkpoint

The following inventory records the pre-`20feddc` checkpoint; it is not active
work.

The characterize-only inventory selects exactly one production follow-on. Add
four CURRENT-SOURCE contracts, then move only the current exact 68-line
`_candidate_satisfies_ratio_component_acceptance_contract(candidate, *,
operand, constraints, query_years, selected_cell=None, report_scope=None)`
definition from `financial_graph_helpers.py` to the existing
`financial_operand_resolution.py` owner as public
`candidate_satisfies_ratio_component_acceptance_contract(...)`. Do not leave a
graph alias or compatibility bridge.

No production source or test has moved for this projection. The predicate
classifies one already prepared ratio-component candidate against candidate
shape, numeric, segment/report, aggregate, surface, binding-policy, and period
signals. It does not construct candidates or cells, select a structured cell,
calculate the broad float score, sort a collection, run direct acceptance,
adopt an operand row, invoke a model, or read/write graph state.

The destination already owns `_normalise_spaces`, `_operand_surface_contract`,
`candidate_value_role(...)`, `candidate_aggregation_stage(...)`,
`candidate_direct_match_strength(...)`, `operand_period_focus(...)`, and
`candidate_matches_operand_target_year(...)`. Add the existing public
`binding_policy_allows_candidate_shape(...)`,
`candidate_has_required_surface_contract(...)`,
`candidate_has_numeric_value_signal(...)`, `candidate_is_descriptor_row(...)`,
and `candidate_matches_segment_binding(...)` names to its surface-contract
import, and `candidate_matches_target_report_scope(...)` to its scope-policy
import. Both module edges already exist, so the full DAG remains acyclic at 48
modules and 204 internal edges. Current public/private counts are graph helpers
9/75 and operand resolution 50/37; projected counts are 9/74 and 51/37. The
selected span contains zero of the 217 reviewed runtime-domain records.

Preserve the exact 22-statement body, twelve returns, no `try`, required
positional `candidate`, three required and two optional keyword-only arguments,
and `bool` result. Shallow-copy candidate metadata first, then preserve raw
candidate-kind lookup/falsey fallback/string/strip and exact membership in the
five current structured/evidence kinds. Candidate-kind rejection stops before
descriptor, numeric, segment, and report checks. Those four gates remain in
that order and return exact `False` on the first miss.

The report-scope gate must receive a fresh shallow `dict(report_scope or {})`
while candidate, operand, constraints, query years, selected cell, and nested
objects retain their current identities. After it passes, call value-role and
aggregation-stage projection exactly once each. Preserve `direct_row_like` as
one lazy boolean chain: exact table/evidence kind, non-`None` selected cell,
required-surface truth, then one direct-strength call and `>= 1.0`. No later
term may run after an earlier falsey term.

Preserve aggregate truth precedence as exact aggregate value role, then exact
final/subtotal/direct stage membership, then the computed direct-row flag. A
falsey result returns before binding-policy access. The binding-policy gate
receives a fresh shallow `dict(operand.get("binding_policy") or {})` and keeps
exact keyword arguments and failure propagation.

Call `_operand_surface_contract(operand)` once and eagerly materialize
`positive_terms` in source order. A rejected item stringifies once and a
retained item twice. A truthy list requires one selected-cell-aware surface
check and rejects its falsey result without the later direct-strength fallback.
An empty list skips that surface check and evaluates the separate direct-
strength fallback once, rejecting exact values `< 1.0`. This remains distinct
from the earlier lazy direct-row-like strength expression. Stateful iterables,
duplicates, conversion order, and first failure therefore retain their current
effects.

Only after aggregate, binding, and surface gates derive desired period focus
from the original operand and normalized constraint fallback. Then normalize
candidate period focus and call target-year matching exactly once, eagerly
before either current/prior branch. Reject only current-vs-prior or prior-vs-
current mismatch when the target-year result is falsey; every other path
returns exact `True`.

There is no exception boundary. Mapping access, truth, shallow copy,
conversion, strip, membership, list materialization, short-circuit boolean
evaluation, helper calls and result truth, numeric comparison, and return
failures remain uncaught in current order. Candidate, operand, constraints,
query years, selected cell, supplied report scope, their nested objects, and
helper-owned objects remain unmodified.

The projection has three direct `ast.Name` calls, all at caller `try` depth
zero in `financial_graph_reconciliation.py`. Move only the imported binding
from graph helpers to operand resolution. The nested
`candidate_supports_operand(...)` call keeps exact `current` plus the five
keyword inputs and returns `True` on acceptance before scanning another cell.
The first `_extract_structured_operands_from_reconciliation(...)` call remains
the ratio-only fallback in the combined direct-acceptance condition and keeps
its `continue`/candidate-selection stop. The second remains an assignment to
`direct_accept` only after direct acceptance fails, before the same-block
fallback and final candidate/cell adoption. Cell construction/selection,
direct acceptance, candidate sorting, same-block fallback, operand-row
construction, evidence work, state mutation, I/O, retry, and final sequencing
remain reconciliation/existing-owner responsibilities and are rejected from
this batch.

Before production movement, add exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_candidate_satisfies_ratio_component_acceptance_contract_pins_precedence_aggregate_surface_period_and_result`;
- `test_current_source_candidate_satisfies_ratio_component_acceptance_contract_pins_laziness_identity_immutability_and_exceptions`;
- `test_current_source_candidate_satisfies_ratio_component_acceptance_contract_bindings_pin_owner_defs_calls_dag_imports_and_baseline`;
- `test_current_source_candidate_satisfies_ratio_component_acceptance_contract_callers_pin_args_adoption_fallback_and_stops`.

They must pin the exact definition/signature/body, every early gate and lazy
boolean chain, shallow copies, conversion/materialization order, thresholds,
period mismatch truth table, exact booleans, identities, immutability, every
uncaught failure, all three caller expressions/arguments/adoption/fallback/
stops, current/projected function counts, unchanged acyclic DAG, and zero
selected-body runtime-domain records.

Projected post-move gates are focused 4/4, graph-helper characterization owner
158/158, operand-resolution owner 69/69, affected eleven-module semantic set
1,118/1,118, reconciliation plan 51/51, import-side-effects 19/19, audit 217,
and full discovery 2,011/2,011, plus pycompile/fresh import and public identity,
selected-body parity 1/1, retained graph exact 83/83, all 87 retained operand-
resolution functions, all three calls/one caller module, full 48-module/204-
edge DAG parity, retired executable graph-private refs zero, non-ASCII
preservation, and `git diff --check`. These are projections to verify, not
completed results.

Static definition/call/DAG/function-count/import and selected-body audit
inspection passed. The existing owner/full gates remain the latest executed
runtime evidence below. Benchmark refresh and remote CI were **NOT RUN**. This
characterization makes no behavior, accuracy, ranking, performance, benchmark,
schedule, ledger, or Phase 3 completion claim.

## Completed Ratio-Component-Acceptance Ownership

Commit `20feddc` moved the exact former 68-line graph predicate to public
`financial_operand_resolution.candidate_satisfies_ratio_component_acceptance_contract(...)`
with its 22-statement/twelve-return/no-`try` body unchanged. The old private
definition and executable private refs are gone; no wrapper or compatibility
bridge was added.

All three calls in `financial_graph_reconciliation.py` now bind the public owner
with their exact candidate and keyword inputs. The nested first-hit return, the
combined direct/ratio condition and `continue`, the later `direct_accept`
fallback assignment, same-block fallback, and candidate/cell adoption remain in
their original caller positions. This milestone does not move cell preparation
or selection, direct acceptance, candidate sorting/scoring, evidence work, or
state sequencing.

Production source is `+80/-74`, net `+6`; tests are `+1,325/-99`, net `+1,226`;
and the whole commit is `+1,405/-173`, net `+1,232`. Graph helpers moved from
4,958 to 4,888 physical lines, operand resolution from 4,160 to 4,236,
reconciliation remained 1,466, graph-helper tests moved from 35,215 to 36,441,
and four methods moved discovery from 2,007 to 2,011. Final public/private counts
are graph 9/74 and operand resolution 51/37. The source diff SHA-256 is
`f0e6496c26ea5ed85c50db99057911f149d4654690a833d09ff725125e0e2139`.

Focused pre/post movement 4/4, graph owner 158/158, operand owner 69/69,
affected eleven-module semantic 1,118/1,118, reconciliation plan 51/51,
import-side-effects 19/19, runtime-domain audit 217, and full discovery
2,011/2,011 passed. Pycompile, fresh public identity 1/1, exact 68-line body
parity 1/1, retained graph exact 83/83, all 87 retained operand-resolution
functions, all three calls/one caller module, full 48-module/204-edge acyclic DAG
parity, retired private refs zero, non-ASCII preservation 5/5, and
`git diff --check` also passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic ratio-component acceptance ownership.
It proves no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Canonical-Statement-Winner Ownership

Commit `73a049c` moved the exact former 42-line graph predicate to public
`financial_operand_resolution.candidate_is_canonical_statement_winner(...)`
with its 17-statement/seven-return body unchanged. The old private definition
and executable private refs are gone; no wrapper or compatibility bridge was
added.

The sole call in `_deterministic_reconcile_task(...)` now binds the public
owner with exact candidate/operand/year inputs. Direct-entry dictionary order,
storage under `canonical_winner`, later family/logical collapse, semantic
priority, score fallback, and adoption remain graph-owned. This milestone does
not move entry construction, sorting, broad scoring, direct/ratio acceptance,
evidence selection, or state ownership.

Production source is `+50/-46`, net `+4`; tests are `+1,593/-67`, net `+1,526`;
and the whole commit is `+1,643/-113`, net `+1,530`. Graph helpers moved from
5,001 to 4,958 physical lines, operand resolution from 4,113 to 4,160,
graph-helper tests from 33,689 to 35,215, and four methods moved discovery from
2,003 to 2,007. Final public/private counts are graph 9/75 and operand
resolution 50/37. The source diff SHA-256 is
`f3733afbfbbeaec72deafed6a9cfcde10e2c8b1b88e03ece43c10dcd73c563d6`.

Focused pre/post movement 4/4, graph owner 154/154, operand owner 69/69,
affected eleven-module semantic 1,114/1,114, reconciliation plan 51/51,
import-side-effects 19/19, runtime-domain audit 217, and full discovery
2,007/2,007 passed. Pycompile, fresh public identity 1/1, exact 42-line body
parity 1/1, retained graph exact 83/84 and call-normalized 84/84, all 86
retained operand-resolution functions, the sole call/caller, full 48-module/
204-edge acyclic DAG parity, retired private refs zero, non-ASCII preservation
4/4, and `git diff --check` also passed. Benchmark refresh and remote CI were
**NOT RUN**.

This milestone changes only deterministic canonical-statement-winner
ownership. It proves no behavior, accuracy, ranking, performance, benchmark,
schedule, ledger, or Phase 3 completion claim.

## Historical Canonical-Statement-Winner Characterization Checkpoint

The characterize-only inventory selects exactly one production follow-on. Add
four CURRENT-SOURCE contracts, then move only the current exact 42-line
`_candidate_is_canonical_statement_winner(candidate, *, operand, query_years)`
definition from `financial_graph_helpers.py` to the existing
`financial_operand_resolution.py` owner as public
`candidate_is_canonical_statement_winner(...)`. Do not leave a graph alias or
compatibility bridge.

No production source or test has moved for this projection. The predicate
classifies one already prepared candidate against canonical statement, section,
direct-match, and period signals. It does not construct candidates, calculate
the broad float score, sort or collapse a collection, select a winner, apply
direct or ratio acceptance, adopt evidence, invoke a model, or read/write graph
state.

The destination already owns `_normalise_spaces`,
`lookup_prefers_canonical_statement_rows(...)`,
`lookup_canonical_statement_preferences(...)`,
`candidate_direct_match_strength(...)`, and the scoring-policy constant. It
also already imports `candidate_matches_operand_target_year(...)` from scope
policy; add `operand_period_focus(...)` to that existing import. No module edge
is added. The full DAG remains acyclic at 48 modules and 204 internal edges.
Current public/private counts are graph helpers 9/76 and operand resolution
49/37; projected counts are 9/75 and 50/37. The selected span contains zero of
the 217 reviewed runtime-domain records.

Preserve the exact 17-statement body, seven returns, no `try`, required
positional `candidate`, two required keyword-only arguments, and `bool` result.
Canonical-row preference is the first gate and returns exact `False` before
candidate access when disabled. Then shallow-copy candidate metadata, preserve
raw statement-type lookup/falsey fallback/string/strip order, obtain the exact
two-value canonical preference result, and reject a truthy canonical-type
collection that does not contain the stripped statement type.

Do not copy or materialize either returned canonical preference object.
Preserve repeated truth and membership against the exact canonical-type object,
and preserve canonical-section iteration/consumption across the earlier
marker/section scan and the later filtered section gate. Stateful containers,
one-shot iterators, duplicates, and first-hit behavior therefore retain their
current effects.

The canonical-statement-type hit keeps explicit `bool(canonical_types)`, the
second membership test, and exclusion of exact `notes` and `unknown`. Preserve
lazy `local_heading -> table_context -> section_path -> ""` fallback before one
string conversion and normalization, followed by the separate repeated
section-path lookup and normalization. Shallow-copy
`OPERAND_CANDIDATE_SCORING_POLICY`, then eagerly materialize the marker tuple in
order: a rejected marker stringifies once and a retained marker twice. Marker
duplicates and output identities remain unchanged.

`note_context` keeps marker-outer order, heading membership before lazy section-
path membership, and `any(...)` short-circuiting. `allows_note_canonical` keeps
marker-outer/section-inner order, one normalization per visited pair, and its
own short circuit. A note context without an allowed canonical section returns
`False`. The later canonical-section gate remains lazy behind raw section
truth and a canonical-type hit. Its filtered generator normalizes a rejected
section once and a retained section two or three times depending on the first
membership result; first hit stops the scan.

Only after those gates call direct-match strength once and reject exact values
`< 2.5`. Then call target-year matching once. A truthy result returns `True`
without period-focus work. A falsey result normalizes candidate period focus,
calls `operand_period_focus(operand, "unknown")` positionally, and rejects only
when the desired focus is exact `current` or `prior` and differs from the
candidate focus. All other paths return exact `True`.

There is no exception boundary. Mapping access, raw truth, shallow copies,
unpacking, conversion, strip, normalization, iteration, tuple construction,
membership, generator/`any`, helper calls and result truth, comparison, and
return failures remain uncaught in current order. Candidate, operand,
canonical preference objects, metadata and policy sources, nested objects, and
`query_years` remain unmodified and retain identity.

The projection has one direct `ast.Name` call in graph caller
`_deterministic_reconcile_task(...)`, under body statement index 9/17 and at
caller `try` depth zero. It remains the value expression for exact key
`"canonical_winner"` in the direct-entry dictionary, after candidate,
logical/family signatures, selected value text, and broad score. Preserve the
exact positional `candidate` and keyword `operand=operand,
query_years=years`, their identities, dictionary evaluation order, and
exception stop before append. The stored boolean continues to participate only
in existing family/logical-signature ranking, canonical-entry collapse, and
later semantic/score fallback. Entry construction, sorting, collapse, broad
scoring, direct/ratio acceptance, candidate/evidence adoption, I/O, retrieval,
graph state, model invocation, artifact/ledger mutation, retry, and final
sequencing remain graph/existing-owner responsibilities and are rejected from
this batch.

Before production movement, add exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_candidate_is_canonical_statement_winner_pins_precedence_markers_and_result`;
- `test_current_source_candidate_is_canonical_statement_winner_pins_laziness_identity_immutability_and_exceptions`;
- `test_current_source_candidate_is_canonical_statement_winner_bindings_pin_owner_def_calls_dag_imports_and_baseline`;
- `test_current_source_candidate_is_canonical_statement_winner_caller_pins_args_projection_adoption_and_stops`.

They must pin the exact definition/signature/body, all early gates and repeated
reads, marker and section iteration/normalization order, threshold and period
fallback, exact booleans, identities, immutability, every uncaught failure, the
sole caller expression/arguments/dictionary order/adoption/stops,
current/projected function counts, unchanged acyclic DAG, and zero selected-body
runtime-domain records.

Projected post-move gates are focused 4/4, graph-helper characterization owner
154/154, operand-resolution owner 69/69, affected eleven-module semantic set
1,114/1,114, reconciliation plan 51/51, import-side-effects 19/19, audit 217,
and full discovery 2,007/2,007, plus pycompile/fresh import and public identity,
selected-body parity 1/1, retained graph exact 83/84 and call-normalized 84/84,
all 86 retained operand-resolution functions, the sole call/caller, full
48-module/204-edge DAG parity, retired executable graph-private refs zero, non-
ASCII preservation, and `git diff --check`. These are projections to verify,
not completed results.

Static definition/call/DAG/function-count/import and selected-body audit
inspection passed. Direct branch/laziness/identity probes passed 8/8 and related
caller probes passed 3/3. Benchmark refresh and remote CI were **NOT RUN**. This
characterization makes no behavior, accuracy, ranking, performance, benchmark,
schedule, ledger, or Phase 3 completion claim.

## Completed Direct-Candidate Semantic-Priority Ownership

Commit `1be4cad` moved the exact former 53-line graph projection to public
`financial_operand_resolution.direct_candidate_semantic_priority(...)` with its
19-statement/one-return body unchanged. The old private definition and
executable private refs are gone; no wrapper or compatibility bridge was added.

All three direct calls in `_deterministic_reconcile_task(...)` now bind the
public owner. The sort-key candidate copy before float score, reverse ordering,
top/next recomputation, strict tuple comparison, score fallback, collapse, and
adoption remain in their exact graph-owned positions. This milestone does not
move collection sorting, broad scoring, acceptance, winner selection, or state
ownership.

Production source is `+60/-58`, net `+2`; tests are `+1,332/-109`, net
`+1,223`; and the whole commit is `+1,392/-167`, net `+1,225`. Graph helpers
moved from 5,055 to 5,001 physical lines, operand resolution from 4,057 to
4,113, graph-helper tests from 32,466 to 33,689, and four methods moved discovery
from 1,999 to 2,003. Final public/private counts are graph 9/76 and operand
resolution 49/37. The source diff SHA-256 is
`6fe4cf715b6ea401a379f3ca40725ad7ea25e8b0bae16deb0752433f3937d304`.

Focused pre/post movement 4/4, graph owner 150/150, operand owner 69/69,
affected eleven-module semantic 1,110/1,110, reconciliation plan 51/51,
import-side-effects 19/19, runtime-domain audit 217, and full discovery
2,003/2,003 passed. Pycompile, fresh public identity 1/1, exact 53-line body
parity 1/1, retained graph exact 84/85 and call-normalized 85/85, all 85 retained
operand-resolution functions, all three calls/one caller, full 48-module/
204-edge acyclic DAG parity, retired private refs zero, non-ASCII preservation
4/4, and `git diff --check` also passed. Benchmark refresh and remote CI were
**NOT RUN**.

This milestone changes only deterministic semantic-priority ownership. It
proves no behavior, accuracy, ranking, performance, benchmark, schedule, ledger,
or Phase 3 completion claim.

## Historical Direct-Candidate Semantic-Priority Characterization Checkpoint

The characterize-only inventory selected exactly one production follow-on. Add
four CURRENT-SOURCE contracts, then move only the current exact 53-line
`_direct_candidate_semantic_priority(candidate, *, operand,
preferred_statement_types, query_years)` definition from
`financial_graph_helpers.py` to the existing
`financial_operand_resolution.py` owner as public
`direct_candidate_semantic_priority(...)`. Do not leave a graph alias or
compatibility bridge.

No production source or test has moved for this projection. The function
calculates one fixed five-integer semantic-priority tuple for one already
prepared candidate and operand. It does not construct candidates, compute the
broad float score, sort a collection, select a winner, apply direct or ratio
acceptance, adopt evidence, invoke a model, or read/write graph state.

The destination already owns `_normalise_spaces`, `candidate_value_role`,
`candidate_aggregation_stage`, and `candidate_direct_match_strength`. Add only
public `candidate_matches_operand_target_year(...)` from the existing scope-
policy owner. This creates one new direct
`financial_operand_resolution -> financial_scope_policies` edge; scope policy
does not reach operand resolution or graph helpers, so the projected full DAG
remains acyclic at 48 modules and 204 internal edges. Current public/private
counts are graph helpers 9/77 and operand resolution 48/37; projected counts are
9/76 and 49/37. The selected span contains zero of the 217 reviewed runtime-
domain records.

Preserve the exact 19-statement body, one return, no `try`, required positional
`candidate`, three required keyword-only arguments, and
`tuple[int, int, int, int, int]` result. First shallow-copy candidate metadata,
then operand binding policy. Eagerly materialize normalized preferred statement
types from the supplied iterable, followed by normalized preferred value roles
and aggregation stages from raw policy values with their existing `or []`
fallbacks. Each comprehension keeps condition-before-element evaluation:
rejected items stringify/normalize once and retained items twice, in input
order.

After those lists, normalize metadata statement type, then call candidate value-
role, aggregation-stage, direct-match-strength, and candidate-kind normalization
in exact order. Initialize statement, value-role, and aggregation-stage ranks to
zero independently. A membership hit adopts exact
`len(preferences) - preferences.index(value)`, so first occurrence, duplicate,
and list-length behavior remain unchanged. Target-year matching then projects
truth to exact `1` or `0`; exact candidate kind `structured_value` does the same.
Return tuple order stays aggregation-stage rank, value-role rank, statement
rank, and target-year match; the final expression remains
`structured_value_rank + int(direct_match_strength * 10)`, including Python
integer truncation and all current arithmetic/comparison behavior.

There is no exception boundary. Candidate/operand/metadata/binding mappings,
preferred iterables, truth, iteration, conversion, normalization, list
construction, membership/index/length, helper calls and result truth,
multiplication, integer conversion, addition, tuple construction, and return
failures stay uncaught in current order. Candidate, operand, supplied lists,
nested objects, and shallow-copy sources remain unmodified and retain identity.

The projection has three direct `ast.Name` calls in one graph caller,
`_deterministic_reconcile_task(...)`, all under body statement index 9/17 and at
caller `try` depth zero. Each keeps one positional prepared-candidate copy and
the exact `operand`, `preferred_statement_types`, and `query_years` keywords:

- the sort-key lambda keeps `dict(entry.get("candidate") or {})` as the first
  component before the existing float score, with `reverse=True`;
- `top_priority` recomputes from the sorted first entry with
  `dict(ranked_by_priority[0].get("candidate") or {})`;
- `next_priority` recomputes from the sorted second entry with the corresponding
  index-one expression before the strict `top_priority > next_priority`
  comparison.

Preserve repeated evaluation, mapping copies, sort-key order, reverse ordering,
top/next recomputation, strict comparison, and all stops. A unique greater tuple
still collapses to the first ranked entry; a tie still falls through to the
existing score-based fallback. Collection sorting, score fallback, collapse,
candidate/evidence adoption, direct/ratio acceptance, broad scoring, I/O,
retrieval, graph state, model invocation, artifact/ledger mutation, retry, and
final sequencing remain graph/existing-owner responsibilities and are rejected
from this batch.

Before production movement, add exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_direct_candidate_semantic_priority_pins_normalization_ranks_and_tuple`;
- `test_current_source_direct_candidate_semantic_priority_pins_laziness_identity_immutability_and_exceptions`;
- `test_current_source_direct_candidate_semantic_priority_bindings_pin_owner_def_calls_dag_imports_and_baseline`;
- `test_current_source_direct_candidate_semantic_priority_caller_pins_args_sort_recompute_compare_adoption_and_stops`.

They must pin the exact definition/signature/body, three normalization
comprehensions, access and helper order, rank formulas, duplicate/first-index
semantics, exact tuple and integer conversion, identities, immutability, every
uncaught failure, all three caller expressions/arguments/sort/recompute/compare/
adoption/stops, current/projected function counts, the new acyclic DAG edge, and
zero selected-body runtime-domain records.

Projected post-move gates are focused 4/4, graph-helper characterization owner
150/150, operand-resolution owner 69/69, affected eleven-module semantic set
1,110/1,110, reconciliation plan 51/51, import-side-effects 19/19, audit 217,
and full discovery 2,003/2,003, plus pycompile/fresh import and public identity,
selected-body parity 1/1, retained graph exact 84/85 and call-normalized 85/85,
all 85 retained operand-resolution functions, all three calls/one caller, full
48-module/204-edge DAG parity, retired executable graph-private refs zero, non-
ASCII preservation, and `git diff --check`. These are projections to verify,
not completed results.

Static definition/call/DAG/function-count/import and selected-body audit
inspection passed. Direct rank/order/identity/immutability and failure-stop
probes also passed. Benchmark refresh and remote CI were **NOT RUN**. This
characterization makes no behavior, accuracy, ranking, performance, benchmark,
schedule, ledger, or Phase 3 completion claim.

## Completed Candidate Direct-Match-Strength Ownership

Commit `91ceae7` moved the exact former 122-line graph scorer to public
`financial_operand_resolution.candidate_direct_match_strength(...)` with its
body unchanged. The old private definition and executable private refs are gone;
no wrapper or compatibility bridge was added.

All eight direct calls across six graph callers now bind the public owner with
positional exact `candidate, operand`, no keywords, and caller `try` depth zero.
Canonical-winner `< 2.5`, semantic-priority tuple use, direct-grounding `< 1.0`,
direct-acceptance `< 2.0`, ratio-acceptance `>= 1.0` and later `< 1.0`, broad-
score immediate addition, and structured-candidate `>= 2.5`/`>= 1.5` bonuses
remain in their exact caller positions. This milestone does not move threshold,
ranking, acceptance, or adoption ownership.

The historical pre-move checkpoint below misstated the later ratio-component
rejection as `< 2.0`. Live source and the completed CURRENT-SOURCE contract pin
the existing `< 1.0`; this corrects documentation and does not change runtime
behavior.

Production source is `+135/-138`, net `-3`; tests are `+1,078/-226`, net
`+852`; and the whole commit is `+1,213/-364`, net `+849`. Graph helpers moved
from 5,184 to 5,055 physical lines, operand resolution from 3,931 to 4,057,
graph-helper tests from 31,614 to 32,466, and four methods moved discovery from
1,995 to 1,999. Final public/private counts are graph 9/77 and operand resolution
48/37. The source diff SHA-256 is
`fb7cf8e1824f26bc4fd54a303602491f79956eb277d999e2fd45872c0e361de3`.

Focused pre/post movement 4/4, graph owner 146/146, operand owner 69/69,
affected eleven-module semantic 1,106/1,106, reconciliation plan 51/51,
import-side-effects 19/19, runtime-domain audit 217, and full discovery
1,999/1,999 passed. Pycompile, fresh public identity, exact 122-line body parity,
retained graph exact 80/86 and call-normalized 86/86, all 84 retained operand-
resolution functions, all eight calls/six callers, full 48-module/203-edge DAG
parity, retired private refs zero, non-ASCII preservation, and `git diff --check`
also passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic direct-match-strength ownership. It
proves no behavior, accuracy, ranking, performance, benchmark, schedule, ledger,
or Phase 3 completion claim.

## Historical Candidate Direct-Match-Strength Characterization Checkpoint

The characterize-only inventory selects exactly one production follow-on. Add
four CURRENT-SOURCE contracts, then move only the current exact 122-line
`_candidate_direct_match_strength(candidate, operand)` definition from
`financial_graph_helpers.py` to the existing
`financial_operand_resolution.py` owner as public
`candidate_direct_match_strength(...)`. Do not leave a graph alias or
compatibility bridge.

No production source or test has moved for this projection. The function scores
how directly one already prepared candidate represents one operand. It does not
construct candidates, select a winner, own a threshold, rank a collection,
adopt evidence, invoke a model, or read/write graph state.

The destination already owns every dependency except
`candidate_has_operand_context_surface` and
`candidate_supports_segment_metric_combo`; add those two public names from the
existing row-surface owner. The move makes graph imports of those two names,
`_text_has_positive_surface`, `candidate_local_aggregate_context`,
`operand_prefers_contextual_aggregate_match`, and
`operand_lookup_surface_match` dead and removable. All module relationships
already exist, so the full 48-module/203-internal-edge DAG remains unchanged.
Current public/private counts are graph helpers 9/78 and operand resolution
47/37; projected counts are 9/77 and 48/37. The selected span contains zero of
the 217 reviewed runtime-domain records.

Preserve the exact 15-statement body, two returns, docstring, and float result.
Concept conflict is first and returns `0.0` before metadata work. Then shallow-
copy candidate metadata, normalize candidate kind, and eagerly construct the
base surface list in exact weighted order: semantic label `3.0`, row label
`2.5`, joined semantic aliases `2.0`, joined row headers `1.5`, and aggregate
label `1.0`. Only non-`table_row` candidates extend it with table-row-label text
`1.25` and row text `1.0`.

For each surface, normalize before blank rejection, materialize a variant set,
and preserve exact-match, variant-match, then operand-text-match precedence.
Exact and variant matches adopt the full surface weight; the fallback adopts
half. Preserve repeated operand-needle and surface-variant generation, iterable
materialization, first-hit `any(...)` short circuits, `max(...)` accumulation,
and per-surface continuation.

The specialized branches remain in current order. CAPEX preference builds the
five-part context text, three context surfaces, and normalized preferred-section
list; a section hit plus positive surface and aggregate role or final/direct/
subtotal stage raises the best score to `2.25`. Contextual aggregate preference
then uses local aggregate context and the same role/stage gate to raise it to
`2.0`. Aggregate-label/semantic-label/row-label signal matching follows: direct
operand text plus aggregate role/stage raises `2.25`; lookup-surface match plus
operand-context surface plus aggregate role/stage also raises `2.25`. Segment-
metric combination is last and raises `2.25`; final return is the accumulated
best score.

There is no exception boundary. Candidate/operand/metadata mapping and truth,
string/strip/normalization, eager list/set/join/extend construction, iterators,
needle/variant/text/positive/lookup/context/segment helper calls and result
truth, comparisons, `max`, role/stage projection, and final return failures stay
uncaught in current order. Candidate, operand, metadata source, and nested
objects remain unmodified and retain identity.

The projection has eight direct `ast.Name` calls across six graph callers. All
remain positional exact `candidate, operand`, with no keywords and caller `try`
depth zero:

- `_candidate_is_canonical_statement_winner(...)` body statement 14/17 keeps
  its `< 2.5` rejection before target-year work;
- `_direct_candidate_semantic_priority(...)` body statement 8/19 keeps the
  assigned value used only in the final `int(strength * 10)` tuple component;
- `_candidate_is_direct_grounding_candidate(...)` body statement 5/30 keeps
  its `< 1.0` rejection before binding and scope work;
- `_candidate_satisfies_direct_acceptance_contract(...)` body statement 6/19
  keeps its lookup/single-value `< 2.0` rejection;
- `_candidate_satisfies_ratio_component_acceptance_contract(...)` keeps body
  statement 9/22 `>= 1.0` inside `direct_row_like` and statement 15/22 `< 2.0`
  rejection in their exact lazy positions;
- `_score_operand_candidate(...)` keeps body statement 8/62 immediate
  `score += strength` and statement 11/62 structured-candidate recomputation
  with `>= 2.5`/`>= 1.5` bonuses.

Helper calls, result comparisons, multiplication/int conversion, addition, or
truth failures stop the caller at the same point. Thresholds, duplicate calls,
score weights, later period/table/report scoring, direct/ratio acceptance,
ranking, candidate/evidence adoption, I/O, retrieval, graph state, model
invocation, artifact/ledger mutation, retry, and final sequencing remain graph/
existing-owner responsibilities and are rejected from this batch.

Before production movement, add exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_candidate_direct_match_strength_pins_surface_weights_iteration_and_fallback`;
- `test_current_source_candidate_direct_match_strength_pins_specialized_laziness_identity_immutability_and_exceptions`;
- `test_current_source_candidate_direct_match_strength_bindings_pin_owner_def_calls_dag_imports_and_baseline`;
- `test_current_source_candidate_direct_match_strength_callers_pin_args_threshold_adoption_and_stops`.

They must pin the exact definition/signature/body, weighted surface order,
iteration and short-circuit behavior, specialized-branch precedence, repeated
reads and calls, exact float results, identities, immutability, every uncaught
failure, all eight caller expressions/placements/arguments/adoption/stops,
current/projected function counts, import DAG, and zero selected-body runtime-
domain records.

Projected post-move gates are focused 4/4, graph-helper characterization owner
146/146, affected eleven-module semantic set 1,106/1,106,
import-side-effects 19/19, audit 217, and full discovery 1,999/1,999, plus
pycompile/fresh import and public identity, selected-body parity 1/1, retained
graph exact 80/86 and call-normalized 86/86, all 84 retained operand-resolution
functions, all eight calls/six callers, full 48-module/203-edge DAG parity,
retired executable graph-private refs zero, non-ASCII preservation, and
`git diff --check`. These are projections to verify, not completed results.

Static definition/call/DAG/function-count/import and selected-body audit
inspection passed for this characterization. Benchmark refresh and remote CI
were **NOT RUN**. This characterization makes no behavior, accuracy, ranking,
performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed Candidate-To-Operand Matching Characterization

Commit `1a24bc1` moved the exact former 83-line graph predicate to public
`financial_operand_resolution.candidate_matches_operand(...)` with its body
unchanged. The old private definition and executable private refs are gone; no
wrapper or compatibility bridge was added.

The pre-move characterization counted only the deterministic graph caller.
Live source inventory before editing found two additional executable direct
callers: the active reconciliation rerank list-comprehension and the ops
ontology-shadow filter. All three now call the public owner, and the static
CURRENT-SOURCE contract pins both agent callers plus the ops caller. This is a
correction of the earlier inventory, not a newly added runtime path.

Production source is `+96/-90`, net `+6`; tests are `+1,410/-230`, net
`+1,180`; and the whole commit is `+1,506/-320`, net `+1,186`. Graph helpers
moved from 5,268 to 5,184 physical lines, operand resolution from 3,842 to
3,931, graph-helper tests from 30,434 to 31,614, and four methods moved
discovery from 1,991 to 1,995. Final public/private counts are graph 9/78 and
operand resolution 47/37. The source diff SHA-256 is
`4774eaf925d6dcbc9e0d6da1cc268b889096b4ce9089e13a436bb5fdd41c987a`.

Focused 4/4, owner 142/142, affected semantic 1,102/1,102, reconciliation plan
51/51, import 19/19, audit 217, and full 1,995/1,995 passed. Pycompile, fresh
public identity across owner/graph/reconciliation/ops, exact 83-line body
parity, retained graph exact 86/87 and call-normalized 87/87, all 83 retained
operand-resolution functions, all three normalized caller bodies, full
48-module/203-edge DAG parity, retired private refs zero, non-ASCII
preservation, and `git diff --check` also passed. The first operand-owner run
failed only two absolute source-line contracts after insertion; measured AST
positions were updated and its 69/69 tests passed. Benchmark refresh and remote
CI were **NOT RUN**.

This milestone changes only deterministic matching ownership. It proves no
behavior, accuracy, ranking, performance, benchmark, schedule, ledger, or
Phase 3 completion claim.

## Historical Candidate-To-Operand Matching Characterization Checkpoint

The following text records the pre-move projection. Its one-caller inventory
was incomplete; the completed section above is authoritative for the three
live executable callers found and migrated in `1a24bc1`.

The characterize-only inventory selects exactly one production follow-on. Add
four CURRENT-SOURCE contracts, then move only the current exact 83-line
`_candidate_matches_operand(candidate, operand)` definition from
`financial_graph_helpers.py` to the existing
`financial_operand_resolution.py` owner as public
`candidate_matches_operand(...)`. Do not leave a graph alias or compatibility
bridge.

No production source or test has moved for this projection. The predicate owns
deterministic matching between one already prepared candidate and one operand.
It does not build candidates, choose a winner, compute a rank, apply direct or
ratio acceptance, retrieve evidence, invoke a model, or read/write graph state.

The destination already imports `Any`, `Dict`, `_normalise_spaces`,
`_operand_text_match`, `_text_has_positive_surface`,
`candidate_local_aggregate_context`, `is_capex_total_operand`, and
`operand_prefers_contextual_aggregate_match`. Add only
`candidate_conflicts_with_operand_concept` from the existing surface owner and
`aggregate_like_row_stage`, `candidate_aggregation_stage`, and
`candidate_value_role` from the existing row-surface owner. Graph already
reaches operand resolution, operand resolution already reaches both dependency
owners, and operand resolution does not reach graph. The full
48-module/203-internal-edge DAG therefore remains unchanged. Current
public/private counts are graph helpers 9/79 and operand resolution 46/37;
projected counts are 9/78 and 47/37. The selected span contains zero of the 217
reviewed runtime-domain records.

Preserve the exact 19-statement body and eleven returns. First call
`candidate_conflicts_with_operand_concept(candidate, operand)` with both
original identities. Truth returns exact `False` before any candidate read;
call or result-truth failure stops all later work.

Next project `candidate_kind` through exact candidate get, raw `or ""`,
`str(...)`, and `.strip()`. Build `structured_candidate` by case-sensitive
membership in the exact set `structured_value`, `structured_row`,
`structured_column_value`, `table_row`, and `evidence_row`. Then call candidate
metadata get, apply raw `or {}`, and shallow-copy with `dict(...)`; nested
objects retain identity and inputs remain unmodified.

Test authoritative metadata surfaces in exact order: stripped `row_label`,
stripped `semantic_label`, joined `semantic_aliases`, joined `row_headers`, and
stripped `aggregate_label`. Each surface enters `_operand_text_match(surface,
operand)` with original operand identity and truth returns exact `True` before
later reads. Alias and header iterables are eager; their filters stringify and
strip every item once, retained items are stringified and stripped a second
time, and exact retained strings feed one space join. Preserve iteration,
truth, conversion, join, and short-circuit order.

After those surfaces, only a non-`table_row` candidate reads
`table_row_labels_text`, applies raw `or ""` and `str(...)` without strip, and
passes it to `_operand_text_match(...)`. A table row skips that metadata read
and match entirely. A truthy match returns exact `True`.

The CAPEX branch stays next. On a true `is_capex_total_operand(operand)` gate,
build `section_context` from nonempty stripped local heading, table context,
section path, row context, and candidate text in that order. Build
`preferred_sections` eagerly from `operand["preferred_sections"]`: the filter
stringifies and strips once, retained items stringify again and enter
`_normalise_spaces(...)`. A nonempty list then runs ordered `any(section in
_normalise_spaces(section_context) ...)`, preserving one context normalization
per attempted section and first-hit short circuit. Only a section hit calls
`_text_has_positive_surface(section_context, operand)`. Positive truth then
calls `candidate_value_role(candidate)`; exact aggregate returns `True` without
stage lookup, otherwise `candidate_aggregation_stage(candidate)` accepts exact
final/direct/subtotal and returns `True`. Every miss continues.

The contextual branch follows. A true
`operand_prefers_contextual_aggregate_match(operand)` gate first calls
`candidate_local_aggregate_context(candidate)`. It then rereads aggregate,
row, and semantic labels from the metadata copy, strips nonempty parts, joins
them, and normalizes the result as `aggregate_surface`. Compute
`aggregate_like` before positive-surface matching: candidate value-role exact
aggregate short-circuits stage and row-stage work; otherwise exact final or
subtotal stage short-circuits row-stage work; otherwise
`aggregate_like_row_stage(aggregate_surface) != "none"` decides it. Then call
`_text_has_positive_surface(section_context, operand)` first in the final
condition; positive truth plus `aggregate_like` returns exact `True`.

After both specialized branches, an unmatched structured candidate returns
exact `False` without reading candidate text for fallback. Only an unstructured
candidate performs exact candidate text get/raw-or/string conversion and
returns the exact object from `_operand_text_match(text, operand)` without a
second coercion.

There is no exception boundary. Predicate calls/result truth, candidate and
metadata get/result truth/copy, string/strip, set membership, iterable
materialization, join, surface-match call/truth, section list construction,
normalization, membership and `any`, role/stage/row-stage projection and
comparison, fallback read/match, and returned-result failures remain uncaught
in current order. Inputs and nested objects remain unmodified. No wrapper,
callback, carrier, reason, flag, trace, retry, fallback, normalization change,
or compatibility bridge is permitted.

The projection has exactly one direct `ast.Name` call. In
`_deterministic_reconcile_task(...)` it remains inside top-level body statement
9 of 17, the `for operand in required_operands` loop, at loop-body statement 1.
Preserve the exact assignment
`matches = [candidate for candidate in candidates if
candidate_matches_operand(candidate, operand)]`: one generator, original
candidate iteration order and identities, positional exact `candidate,
operand`, no keywords, caller `try` depth zero, and immediate `comprehension`
parent under `ListComp` and `Assign`. Helper result truth selects the original
candidate; falsehood skips it. Helper or result-truth failure stops remaining
candidates and all later segment filtering, ranking, acceptance, match/missing
projection, retry-query work, and final return.

Candidate construction, the required-operand loop, segment-local filtering,
`_candidate_direct_match_strength(...)`, direct/ratio acceptance, all score
weights and ranking, top-candidate collapse, candidate/evidence adoption,
report-file I/O, retrieval, graph state, model invocation, artifact/ledger
mutation, retry, and final sequencing remain graph/existing-owner
responsibilities and are rejected from this batch.

Before production movement, add exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_candidate_matches_operand_pins_conflict_structured_surface_and_text_precedence`;
- `test_current_source_candidate_matches_operand_pins_capex_contextual_laziness_identity_immutability_and_exceptions`;
- `test_current_source_candidate_matches_operand_bindings_pin_owner_def_calls_dag_imports_and_baseline`;
- `test_current_source_candidate_matches_operand_caller_pins_comprehension_args_adoption_and_stops`.

They must pin the exact 83-line definition/signature, 19 body statements,
eleven returns, conflict and structured-candidate precedence, all surface and
specialized-branch access order/laziness, repeated conversion, joins,
identities, immutability, every uncaught failure, final exact return object,
sole caller expression/placement/arguments/iteration/adoption/stops,
current/projected function counts, import DAG, and zero selected-body runtime-
domain records.

Projected post-move gates are focused 4/4, graph-helper characterization owner
142/142, affected eleven-module semantic set 1,102/1,102,
import-side-effects 19/19, audit 217, and full discovery 1,995/1,995, plus
pycompile/fresh import and public identity 1/1, selected-body parity 1/1,
retained graph exact 86/87 and call-normalized 87/87, all 83 retained operand-
resolution functions, the sole caller, full 48-module/203-edge DAG parity,
retired executable graph-private refs zero, non-ASCII preservation, and
`git diff --check`. These are projections to verify, not completed results.

Static definition/call/DAG/function-count/import and selected-body audit
inspection, direct behavior probes 12/12, gate/access-order probes 2/2, caller
iteration/identity adoption 1/1, and caller call/truth failure stops 2/2 passed.
Benchmark refresh and remote CI were **NOT RUN**. This characterization makes
no behavior, accuracy, ranking, performance, benchmark, schedule, ledger, or
Phase 3 completion claim.

## Completed Candidate Source-Priority Score Characterization

Commit `334fff0` moved the exact former 76-line graph scorer to public
`financial_operand_resolution.candidate_source_priority_bonus(...)` with its
body unchanged. The old private definition and all executable private
references are gone; no graph alias or bridge was added.

Balance-sheet, CAPEX, contextual-aggregate, and note-aggregate branch order,
all score weights, policy and candidate access laziness, shallow copies,
filter-versus-expression stringification, cumulative arithmetic, exact return,
identities, immutability, and uncaught failures remain pinned by four CURRENT-
SOURCE methods. The one graph call remains positional exact `candidate` plus
five exact keyword arguments, caller `try` depth zero, and immediate
`AugAssign`; the broad scorer and later period/table/report work remain graph-
owned.

Production source is `+85/-80`, net `+5`: graph helpers are `+2/-80` and move
from 5,346 to 5,268 physical lines; operand resolution is `+83/-0` and moves
from 3,759 to 3,842. Tests are `+993/-152`, net `+841`: graph-helper tests are
`+990/-149` and move from 29,593 to 30,434 lines, while operand-resolution
static line contracts are `+3/-3` with unchanged physical length. The whole
commit is `+1,078/-232`, net `+846`, and four methods move discovery from 1,987
to 1,991. Final public/private counts are graph 9/79 and operand resolution
46/37. The source diff SHA-256 is
`83b28fa8e35aae9a69981142c705b38a85c471148683c69f470999acc3f1914e`.

Focused 4/4, owner 138/138, affected semantic 1,098/1,098, import 19/19, audit
217, and full 1,991/1,991 passed. Pycompile, fresh import/public identity 2/2,
selected-body parity 1/1, retained graph exact 87/88 and call-normalized 88/88,
all 82 retained operand-resolution functions, sole caller, full
48-module/203-edge DAG parity, retired executable private refs zero, non-ASCII
preservation, and `git diff --check` also passed. The first affected-set run
failed only two absolute source-line contracts after the owner file moved; the
measured current AST positions were updated and the identical 1,098-test set
then passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic source-priority score ownership. It
proves no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

## Completed Note-Aggregate Lookup-Preference Characterization

Commit `1119ac3` moved the exact former 23-line graph predicate to public
`financial_surface_contracts.operand_prefers_note_aggregate_lookup(...)` with
its body unchanged. The old private definition and all executable private
references are gone; no alias or bridge was added.

Statement-type set construction and note short circuit, binding-policy shallow
copy, role-set-before-stage-set construction, dropped-versus-retained
stringification, case-sensitive membership/intersection, exact result,
identities, input immutability, and every uncaught failure remain pinned by four
CURRENT-SOURCE methods. One graph call finishes external/local 1/0, positional
exact `operand`, without keywords, caller `try` depth zero, and immediate `If`
parent. Candidate metadata reads and note score remain caller-owned.

Production source is `+27/-26`, net `+1`: graph helpers are `+2/-26` and move
from 5,370 to 5,346 physical lines; surface contracts are `+25/-0` and move
from 473 to 498. Graph-helper tests are `+987/-36`, net `+951`, and move from
28,642 to 29,593 lines. The whole commit is `+1,014/-62`, net `+952`, and four
methods move discovery from 1,983 to 1,987. Final public/private counts are
graph 9/80 and surface owner 15/7. The source diff SHA-256 is
`0426929d4ef1e09147f9a21dbd661c595fea67a01e38e30f03d81144250e494c`.

Focused 4/4, owner 134/134, affected semantic 1,094/1,094, import 19/19, audit
217, and full 1,987/1,987 passed. Pycompile, fresh import/public identity 2/2,
selected-body parity 1/1, retained graph exact 88/89 and call-normalized 89/89,
retained surface owner 21/21, sole caller, full 48-module/203-edge DAG parity,
retired private refs zero, non-ASCII preservation, and `git diff --check` also
passed. Benchmark refresh and remote CI were **NOT RUN**.

## Historical Note-Aggregate Lookup-Preference Characterization Checkpoint

The following section preserves the pre-`1119ac3` characterization and its
then-projected gates. It is historical evidence, not the active priority.

The historical characterize-only inventory selected exactly one production follow-on. Add
four CURRENT-SOURCE contracts, then move only the current exact 23-line
`_operand_prefers_note_aggregate_lookup(operand: Dict[str, Any]) -> bool`
definition from `financial_graph_helpers.py` to the existing
`financial_surface_contracts.py` owner as public
`operand_prefers_note_aggregate_lookup(...)`. Do not leave a graph alias or
compatibility bridge.

No production source or test has moved for this projection. The predicate
classifies already prepared generic statement-type, value-role, and aggregation-
stage schema values. It does not define or expand domain vocabulary, build or
score a candidate, admit evidence, retrieve documents, or read/write graph
state. Exact `notes`, `aggregate`, `final`, `subtotal`, and `direct` values are
existing runtime schema terms, not a new financial keyword policy.

The destination already imports `Any`, `Dict`, and `_normalise_spaces`. Graph
already reaches the destination and it does not reach graph, so the move adds no
module edge. Current public/private counts are graph helpers 9/81 and surface
contracts 14/7; projected counts are 9/80 and 15/7. The full
48-module/203-internal-edge DAG remains unchanged, and the selected span
contains zero of the 217 reviewed runtime-domain records.

Preserve statement-type preparation first. Call
`operand.get("preferred_statement_types")` once with the original operand
identity, apply raw `or []`, and eagerly build a fresh set. For every item the
filter calls exact `str(item)` and `.strip()` once. Blank or whitespace-only
items are dropped. A retained item is stringified a second time and passed once
to `_normalise_spaces(...)`. Preserve source iteration, hashing/equality,
duplicate collapse, complete set materialization, and exact case. Do not change
the set to a list/tuple or add case folding, sorting, aliasing, or a policy
lookup.

After the first set completes, test exact `"notes" not in
preferred_statement_types`. Absence returns exact `False` before any
`binding_policy` access. Presence continues. Only then call
`operand.get("binding_policy")`, apply raw `or {}`, and shallow-copy with exact
`dict(...)`, preserving nested identities and input immutability.

Build `preferred_value_roles` first and `preferred_aggregation_stages` second.
Each is a fresh set using exact `binding_policy.get(...)`, raw `or []`, one
filter `str(item).strip()` for every item, a second `str(item)` only for retained
items, and one retained-item `_normalise_spaces(...)`. Both sets fully
materialize before the return expression. Preserve iteration, hashing/equality,
duplicate collapse, dropped/retained conversion counts, and case sensitivity.

Return exact `"aggregate" in preferred_value_roles and bool({"final",
"subtotal", "direct"} & preferred_aggregation_stages)`. Role falsehood returns
exact `False` without building the intersection. Role truth constructs the
fresh allowed-stage set and intersection, then calls exact `bool(...)` once.
Do not broaden stages, accept partial values, reuse the prepared set as output,
or add a second coercion.

There is no exception boundary. Operand get/result-truth/iteration, item
string/strip, normalization, set hash/equality, note membership, binding-policy
get/result-truth/mapping copy, role membership, allowed-stage set creation and
intersection, and `bool(...)` lookup/call failures remain uncaught in current
order. Inputs and nested collections remain unmodified. No wrapper, callback,
reason, flag, trace, fallback, retry, or compatibility bridge is permitted.

The projection has exactly one direct `ast.Name` call, positional exact
`operand`, with no keywords, caller `try` depth zero, and an immediate `If`
parent. In `_candidate_source_priority_bonus(...)` it remains exact
`source_priority.body[4]` of six statements, after `score = 0.0` and the
balance-sheet, CAPEX, and contextual-aggregate branches but before final
return. Falsehood skips the note block without reading candidate kind or
metadata. Truth first reads candidate kind, copies metadata, and reads row
context even for a non-notes statement; only the score update is nested under
exact `statement_type == "notes"`.

Preserve the existing caller score branch. A notes structured-value aggregate
receives `+2.75`, `+1.5`, or `+1.0` for exact final, subtotal, or direct stage.
A notes table row receives `-1.0`, another `-0.75` only for nonempty row context
longer than 2,500 characters, and another `-0.5` for a nonaggregate role.
Other candidate kinds, stages, or statement types add nothing. Both truth and
falsehood paths continue to final score return; predicate/result-truth or any
entered candidate/metadata failure stops later caller work.

Moving schema values or normalization, the caller score weights/branch,
candidate kind/metadata projection, value-role or aggregation-stage derivation,
balance-sheet/CAPEX/contextual predicates, broader matching/acceptance/scoring/
ranking, candidate/evidence construction or adoption, report-file I/O,
retrieval, graph state, model invocation, artifact/ledger mutation, retry, or
final sequencing is rejected.

Before production movement, add exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_operand_prefers_note_aggregate_lookup_pins_statement_role_stage_and_result`;
- `test_current_source_operand_prefers_note_aggregate_lookup_pins_laziness_identity_immutability_and_exceptions`;
- `test_current_source_operand_prefers_note_aggregate_lookup_bindings_pin_owner_def_calls_dag_imports_and_baseline`;
- `test_current_source_operand_prefers_note_aggregate_lookup_caller_pins_gate_order_args_adoption_and_stops`.

They must pin the exact 23-line current definition/signature, statement/role/
stage set construction and ordering, dropped-versus-retained conversions,
note-gate and final-and laziness, case/whitespace behavior, identities,
immutability, every uncaught failure, sole caller expression/position/argument/
branch/stop, current/projected function counts, import DAG, and zero selected-
body runtime-domain records.

Projected post-move gates are focused 4/4, graph-helper characterization owner
134/134, affected eleven-module semantic set 1,094/1,094,
import-side-effects 19/19, audit 217, and full discovery 1,987/1,987, plus
pycompile/fresh import and public identity 2/2, selected-body parity 1/1,
retained graph exact 88/89 and call-normalized 89/89, all 21 retained surface-
owner functions, the sole caller, full 48-module/203-edge DAG parity, retired
executable graph-private refs zero, non-ASCII preservation, and
`git diff --check`. These are projections to verify, not completed results.

Static definition/call/DAG/function-count/import and selected-body audit
inspection, direct behavior probes 6/6, note-gate laziness 1/1, caller score
probes 5/5, and caller-gate laziness 1/1 passed. Benchmark refresh and remote CI
were **NOT RUN**. This characterization makes no behavior, accuracy, ranking,
performance, benchmark, schedule, ledger, or Phase 3 completion claim.

## Completed CAPEX-Total-Operand Policy And Owner Characterization

Commit `cefde44` declared the inline canonical ontology identifier as retrieval-
policy `CAPEX_TOTAL_CONCEPT_KEY` and moved the exact former 13-line graph
predicate to public `financial_surface_contracts.is_capex_total_operand(...)`.
The literal-to-policy-name substitution is its only body delta. The old private
definition and all executable private references are gone; no alias or bridge
was added.

Concept fast-path precedence, operand-needle normalization/set construction and
blank discard, scoring-policy shallow copy and configured surface-set
construction, native membership, exact result, identities, policy/ontology/
input immutability, and every uncaught failure remain pinned by four CURRENT-
SOURCE methods. Four graph calls finish external/local 4/0, positional exact
`operand`, without keywords, caller `try` depth zero, and immediate `If`
parents. Their score, acceptance, match, and strength branches remain graph-
owned and unchanged.

Production source is `+23/-19`, net `+4`: graph helpers are `+5/-19` and move
from 5,384 to 5,370 physical lines; surface contracts are `+17/-0` and move
from 456 to 473; retrieval policy is `+1/-0` and moves from 2,070 to 2,071.
Graph-helper tests are `+1,364/-58`, net `+1,306`, and move from 27,336 to
28,642 lines. The whole commit is `+1,387/-77`, net `+1,310`, and four methods
move discovery from 1,979 to 1,983. Final public/private counts are graph 9/81
and surface owner 14/7. The source diff SHA-256 is
`3fcf523be5e9727cbc0b902beb30a899051d288a01459af8799da45071ec02d8`.

Focused 4/4, owner 130/130, affected semantic 1,090/1,090, import 19/19, audit
217, and full 1,983/1,983 passed. Pycompile, fresh import/public identity 2/2,
policy-normalized selected-body parity 1/1, retained graph exact 86/90 and call-
normalized 90/90, retained surface owner 20/20, all four callers, full
48-module/203-edge DAG parity, retired private refs zero, non-ASCII
preservation, and `git diff --check` also passed. Benchmark refresh and remote
CI were **NOT RUN**.

## Historical CAPEX-Total-Operand Characterization Checkpoint

The following section preserves the pre-`cefde44` characterization and its
then-projected gates. It is historical evidence, not the active priority.

The historical characterize-only inventory selected exactly one production follow-on.
First classify the current inline canonical ontology identifier
`capital_expenditure_total` in `src/config/retrieval_policy.py` as named
declarative `CAPEX_TOTAL_CONCEPT_KEY`. Then move only the current exact 13-line
`_is_capex_total_operand(operand: Dict[str, Any]) -> bool` definition from
`financial_graph_helpers.py` to the existing `financial_surface_contracts.py`
owner as public `is_capex_total_operand(...)`. The literal-to-policy-name
substitution at the exact concept comparison is the only permitted body delta.

No production source or test has moved for this projection. The canonical key
already exists in `financial_ontology_concepts_v3.draft.json`; the named
retrieval-policy constant will declare only which ontology concept receives the
existing CAPEX candidate policy. The predicate otherwise classifies already
prepared operand needles against existing declarative
`OPERAND_CANDIDATE_SCORING_POLICY["capex_total_surfaces"]`. It does not define or
expand the ontology, surface or section vocabulary, build a candidate, score or
admit a row, retrieve evidence, or read/write graph state.

The destination already imports `re` and `_normalise_spaces`, owns
`_operand_needles(...)`, and reaches `src.config.retrieval_policy`; importing
`CAPEX_TOTAL_CONCEPT_KEY` and `OPERAND_CANDIDATE_SCORING_POLICY` adds no module
edge. Graph already reaches the destination and it does not reach graph.
Current public/private counts are graph helpers 9/82 and surface contracts
13/7; projected counts are 9/81 and 14/7. The full
48-module/203-internal-edge DAG remains unchanged, and the selected span
contains zero of the 217 reviewed runtime-domain records.

Preserve the exact concept phase first. Call `operand.get("concept")` once with
the original operand identity, apply raw `or ""`, then exact `str(...)` and
`.strip()` once each. Compare that exact case-sensitive result to
`CAPEX_TOTAL_CONCEPT_KEY`. Equality truth returns exact `True` immediately,
before `_operand_needles(...)` or scoring-policy access. A blank, falsey, or
nonmatching concept continues. Do not case-fold, normalize, alias, query the
ontology at runtime, or turn the policy constant into a collection in this
batch.

On continuation, call `_operand_needles(operand)` once with the original
operand identity and consume its result eagerly in the current set
comprehension. Every returned needle, including a falsey or blank one, goes
directly to `_normalise_spaces(needle)` without local string conversion or
filter. Pass that exact result to positional `re.sub(r"\s+", "", normalized)`
and insert the substitution result into a fresh set. Preserve hashing,
equality, duplicate collapse, and complete materialization. Only after the set
is complete call `needles.discard("")` once. Do not replace the set with an
ordered collection, add a pre-filter, or move blank removal into the
comprehension.

Only after needle preparation and discard evaluate exact
`dict(OPERAND_CANDIDATE_SCORING_POLICY)`. Preserve the shallow copy, then exact
`scoring_policy.get("capex_total_surfaces")`, raw `or ()`, and the set
comprehension. For each surface, the filter calls `str(surface)` once and
`.strip()` once; empty and whitespace-only results are dropped. A retained
surface is stringified a second time, normalized once, then passed to exact
positional `re.sub(r"\s+", "", ...)`. Preserve eager policy iteration, fresh
set construction, hashing/equality, duplicate collapse, nested identities, and
the fact that the second set has no post-construction blank discard. Do not
mutate the checked-in policy.

After both sets are complete, preserve exact
`any(needle in capex_surfaces for needle in needles)`. It scans native needle-
set iteration, not original operand order; membership stops at the first hit
and the `any(...)` result is returned without a second coercion. Empty needle
or policy sets return exact `False`. Matching remains case-sensitive. Do not
sort, alias, broaden, add configured surfaces, or synthesize candidate support.

There is no exception boundary. Operand get/truth/string/strip/equality,
operand-needle call/iteration, normalization, `re.sub` lookup/call, first-set
hash/equality and discard, policy mapping copy/get/result-truth/iteration, surface
string/strip, second-set hash/equality, membership, and `any(...)` lookup/call
failures remain uncaught. Inputs, nested objects, ontology data, and checked-in
policy remain unmodified. No wrapper, graph alias, callback, reason, flag,
trace, fallback, or compatibility bridge is permitted.

The projection has exactly four direct `ast.Name` calls, each positional exact
`operand`, with no keywords, caller `try` depth zero, and immediate `If`
parent. In `_candidate_source_priority_bonus(...)` the gate remains body
statement 2 of 6, after `score = 0.0` and the balance-sheet branch but before
contextual-aggregate and note-aggregate work. Truth only enters the existing
CAPEX source-priority branch: configured priority-section hits retain `+2.75`,
aggregate role `+1.0`, final/direct/subtotal stage `+0.75`, cash-flow `-2.5`,
and nonaggregate cash-flow `-0.5`. Falsehood skips that branch; either path then
continues later caller work unchanged.

In `_candidate_satisfies_direct_acceptance_contract(...)` the gate remains body
statement 14 of 19, after grounding, selected-cell/period, binding-policy,
lookup-unit/direct-strength, prepared statement/value-role/stage/context,
canonical-statement, and balance-sheet guards, but before metadata-period/
target-year and final-return work. A truthy gate retains the existing
structured-value aggregate-like requirement and preferred-section fallback;
falsehood skips only that block. Every non-returning path continues.

In `_candidate_matches_operand(...)` the gate remains body statement 15 of 19,
after conflict and direct row/semantic/alias/header/aggregate/table-surface
checks but before contextual-aggregate matching and the structured-candidate
stop. Truth retains the current preferred-section plus positive-surface plus
aggregate-role/stage branch and may return exact `True`; otherwise it continues.
Falsehood skips only the CAPEX block.

In `_candidate_direct_match_strength(...)` the gate remains body statement 8
of 15, after conflict handling and ordinary weighted-surface scoring but before
contextual and aggregate-signal scoring. Truth retains the preferred-section,
positive-surface, aggregate-role/stage branch and exact `best = max(best, 2.25)`;
falsehood skips it. Both paths continue later strength work. Helper or caller-
side result-truth failures stop all later work in all four callers.

Moving CAPEX surface or priority-section values, ontology contents,
`_operand_needles(...)`, any caller branch, source-priority scoring, direct
grounding/acceptance preparation, candidate matching or strength, balance-sheet
or contextual/note predicates, period/unit/report/canonical policy, broader
matching/scoring/ranking, candidate/evidence construction or adoption, report-
file I/O, retrieval, graph state, model invocation, artifact/ledger mutation,
retry, or final sequencing is rejected.

Before production movement, add exactly these four CURRENT-SOURCE methods to
`FinancialGraphHelperTests`:

- `test_current_source_capex_total_operand_pins_concept_precedence_needles_policy_and_result`;
- `test_current_source_capex_total_operand_pins_laziness_identity_immutability_and_exceptions`;
- `test_current_source_capex_total_operand_bindings_pin_policy_owner_def_calls_dag_imports_and_baseline`;
- `test_current_source_capex_total_operand_callers_pin_gate_order_args_adoption_and_stops`.

They must pin the exact 13-line current definition/signature, inline current
concept key and projected named-policy ownership, concept short-circuit and
original operand identity, needle-set normalization/substitution/dedupe/discard
ordering, scoring-policy copy/get/or and filter-versus-expression string/strip
conversions, whitespace and case behavior, eager policy-set materialization,
native set membership and exact result, ontology/policy/input immutability,
every uncaught failure, all four caller expressions/positions/arguments/
branches/stops, current/projected function counts, import DAG, and zero selected-
body runtime-domain records.

Projected post-move gates are focused 4/4, graph-helper characterization owner
130/130, affected eleven-module semantic set 1,090/1,090,
import-side-effects 19/19, audit 217, and full discovery 1,983/1,983, plus
pycompile/fresh import and public identity 2/2, policy-normalized selected-body
parity 1/1, retained graph exact 86/90 and call-normalized 90/90, all 20 retained
surface-owner functions, all four callers, full 48-module/203-edge DAG parity,
retired executable graph-private refs zero, non-ASCII preservation, and
`git diff --check`. These are projections to verify, not completed results.

Static definition/call/DAG/function-count and ontology/policy/selected-body
audit inspection, direct behavior probes 6/6, and caller branch probes 4/4
passed. Benchmark refresh and remote CI were **NOT RUN**. This characterization
makes no behavior, accuracy, ranking, performance, benchmark, schedule, ledger,
or Phase 3 completion claim.

## Completed Balance-Sheet-Aggregate-Operand Characterization

Commit `f35be1a` moved the exact former 9-line graph predicate to public
`financial_surface_contracts.is_balance_sheet_aggregate_operand(...)` with its
body unchanged. The old private definition and all executable private
references are gone; no graph alias or compatibility bridge was added.

Operand-needle normalization/whitespace removal, eager fresh-set construction,
dedupe and blank-discard ordering, declarative label-policy get/or and second-
set construction, filter-versus-expression string conversion, native set
membership, exact result, original identities, input/policy immutability, and
every uncaught failure remain pinned by four CURRENT-SOURCE methods. The two
graph calls finish external/local 2/0 with positional exact `operand`, no
keywords, caller `try` depth zero, and immediate `If` parents. Their source-
priority and direct-acceptance branches remain caller-owned and unchanged.

Production source is `+14/-13`, net `+1`: graph helpers are `+3/-13` and move
from 5,394 to 5,384 physical lines; surface contracts are `+11/-0` and move
from 445 to 456. Graph-helper tests are `+1,014/-34`, net `+980`, and move from
26,356 to 27,336 lines. The whole commit is `+1,028/-47`, net `+981`, and four
methods move discovery from 1,975 to 1,979. Final public/private counts are
graph 9/82 and surface owner 13/7. The source diff SHA-256 is
`e9e8b46382ecdb20982d1ec90c19343aec4a8b769d3812272a54da930dd00f51`.

Focused 4/4, owner 126/126, affected semantic 1,086/1,086, import 19/19,
audit 217, and full 1,979/1,979 passed. Pycompile, fresh import/public identity
2/2, selected-body parity 1/1, retained graph exact 89/91 and call-normalized
91/91, retained surface owner 19/19, both callers, full 48-module/203-edge DAG
parity, retired private refs zero, non-ASCII preservation, and
`git diff --check` also passed. The first full-suite attempt hit the command
wrapper's 60-second limit without a test failure; the identical rerun passed in
104.415 seconds. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic balance-sheet-aggregate-operand
ownership. It proves no behavior, accuracy, ranking, performance, total-code or
executed-path reduction, benchmark improvement, schedule, ledger completion,
or Phase 3 completion.

### Historical Balance-Sheet-Aggregate-Operand Characterization Contract

The prior characterize-only inventory selected exactly one production follow-on:
move only the then-current exact 9-line
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
