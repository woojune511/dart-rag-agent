# Core Runtime Simplification History

> Chronological implementation summary, not a current-status document. Use
> [../overview/project_status.md](../overview/project_status.md) for the active
> product boundary and gates, and [experiment_history.md](experiment_history.md)
> for benchmark and evaluation chronology.

## Why The Simplification Was Needed

The repository accumulated several valid but competing surfaces: the verified
single-agent runtime, MAS experiments, report-cache promotion work, evaluator
and benchmark tooling, compatibility projections, long handoff logs, and raw
experiment outputs. All of them were visible enough to look equally important.

The simplification goal was not to minimize line count. It was to make the
portfolio's core engineering argument obvious:

1. recover DART structure;
2. retrieve the right evidence;
3. let an LLM interpret intent and semantics;
4. execute arithmetic and binding deterministically;
5. preserve evidence and provenance in the public result.

Optional systems remain available, but they no longer define the default
product surface.

## Earlier Extraction Stop Lines

Before the final portfolio sequence, the repository had already extracted or
isolated several implementation owners:

- calculation planning, execution, rendering, and public projection helpers;
- parser structure recovery and vector-store ownership;
- MAS graph, node, type, and diagnostic facades under an experimental boundary;
- reviewer-only requirements, demos, gates, and operational commands;
- strict task-ledger and artifact projections for agentic workflows;
- runtime critic acceptance separated from offline evaluator scores.

Those extractions established clearer owners but did not by themselves make the
first-read product boundary obvious. The July 2026 PR sequence closed that gap.

## Portfolio Core Simplification Sequence

| PR | Merge commit | Outcome |
| --- | --- | --- |
| #79 | `d88040f` | Refactored portfolio positioning around the single-agent core, fixed generic numeric provenance matching, and separated retrieval ownership without tuning behavior. |
| #80 | `33c756d` | Fixed canonical agent answer projection so public output is assembled from owned canonical contracts. |
| #81 | `db9d6e7` | Removed legacy top-level public calculation fallback while keeping historical replay compatibility explicit. |
| #82 | `511f1bd` | Made persisted `ReportCacheIndex` loading lazy and configuration-dependent. |
| #83 | `69082c6` | Closed the default import and invocation boundary against optional MAS, evaluator, benchmark, promotion, review, and cache-index implementations. |
| #84 | `294b4ea` | Reduced tracked benchmark output from 324 raw/intermediate files to 26 compact history-linked summaries and diagnostics. |

### July Milestone 1: Product And Correctness Boundary

The reviewer-facing entry point became `FinancialAgent.run()`. The repository
story was reordered around hybrid retrieval, semantic planning, deterministic
calculation, and provenance rather than experimental topology.

Two correctness gaps were closed with generic mechanisms:

- numeric evidence equivalence preserves sign;
- final-answer evidence selection uses value, label, period, and provenance
  compatibility instead of numeric equality plus list order.

No company, benchmark ID, or metric-specific runtime branch was added.

### July Milestone 2: Retrieval Ownership

Query construction, filters, vector/BM25 search, reranking, selection, and
`retrieval_debug_trace` moved behind the retrieval pipeline owner. Structure
expansion and evidence construction remain owned by the graph/evidence layer.

This was an ownership refactor, not a retrieval-tuning change, so it did not
require a benchmark refresh.

### July Milestone 3: Canonical Public Projection

The public response stopped reviving stale top-level `calculation_*` mirrors.
Canonical numeric output is expressed through `resolved_calculation_trace`,
explicit `structured_result`, and task/artifact projections.

Historical replay and retrospective tooling may request compatibility behavior
explicitly; default runtime code does not infer it.

This completed the July public-projection milestone. It did not complete the
broader Phase 3 calculation-path convergence defined in
`docs/architecture/core_runtime_surface_refactoring_plan.md`; that phase remains
open.

The first projection slice passed 79 focused router/projection/import tests and
1,350 full tests. The second passed the 216-literal runtime audit, 625 focused
calculation-projection tests, and 1,348 full tests. Both passed
`git diff --check`; neither required a benchmark refresh because retrieval and
calculation behavior were unchanged.

### July Milestone 4: Optional-System Isolation

The persisted report-cache implementation became lazy and configuration-bound.
Subprocess regression gates then verified both import and deterministic
invocation boundaries without API keys or network access.

The default path does not load optional MAS, evaluator, benchmark, promotion,
portfolio-review, or persisted cache-index implementations. Their focused tests
remain independently runnable.

### July Milestone 5: Review And Evidence Noise

Raw and intermediate benchmark output was removed from the published Git
surface unless a compact file is directly used by internal history. Future
`benchmarks/results/**` output is ignored by default; local stores, caches, and
heartbeat logs remain local-only.

The final documentation slice converted `CONTEXT.md` and
`docs/overview/project_status.md` from multi-thousand-line chronological logs
into current-state snapshots. This history file records the structural sequence,
while exact pre-compression text remains available in Git at `main@294b4ea`.

## Post-Stop-Line Calculation Contract Sequence

The 2026-08-07 through 2026-08-08 work resumed only for reproduced calculation,
precedence, and provenance gaps. Correctness fixes were committed separately
from behavior-preserving owner moves so validation evidence remains attributable.
This sequence advances the broader calculation-path Phase 3; it does not finish
that phase, prove a total-code reduction, or establish a broad performance gain.

### Dependency precedence and terminal finalization

- The earlier owner extraction changed `financial_graph_calculation.py` from
  21,642 to 19,682 lines while source as a whole grew by 1,095 lines. The typed
  main-path application then changed the graph from 19,686 to 19,587 lines while
  the two changed source files grew by 109 lines. These were ownership moves,
  not executed-policy removal.
- `b16a6c5` prevents consolidation- or producer-scope-rejected dependency rows
  from re-entering through the active late snapshot. The subsequent late-owner
  move changed the graph from 19,587 to 19,564 lines and the dependency owner
  from 2,656 to 2,760 lines, for a two-source net increase of 81 lines.
- `c6f6fdf` makes the normalized-unit filter terminal. `5b44875` moves that
  filter and no-filter selected-first/dependency-second preservation into a
  typed state-free finalizer. `8ebb239` separately repairs empty and partial
  post-filter coverage. From the `77d5bff` baseline, the bounded slice changes
  the graph by 12 lines and the owner by 73, for a two-source net increase of
  85 lines.

Validation remained separated: the earlier extraction passed 62 focused
operand/execution and 323 focused calculation/projection tests, the 217-literal
runtime audit, and full discovery over 1,451 tests; typed main application passed
76 focused, the same audit, and 1,457 full tests. `b16a6c5` passed 78 focused,
the same audit, and 1,457 full tests; the subsequent late-owner checkpoint passed
78 focused, the same audit, and 1,462 full tests. `c6f6fdf` passed 3 focused and
1,462 full tests, `5b44875` passed 52 focused and 1,468 full tests, and the
`8ebb239` state passed 53 focused and 1,468 full tests, each with the same audit.

### Stale freshness, candidate decomposition, and provenance

- `f0eafae` prevents repeated repair of a source-stated display whose formula
  trace still matches the operands. `2496fce` moves only its bound-operand
  freshness assessment to the execution owner. That structural checkpoint
  changes the graph from 19,591 to 19,558 lines and the execution owner from 614
  to 712, for a two-source net increase of 65 lines; from `73d593e`, the bounded
  slice is net 80 lines across those sources.
- `406c1ef` characterizes stale execution snapshots. `c2a5e96` then decomposes
  graph-private preparation, deterministic result projection, and state/ledger
  projection; stale repair stops recursively invoking `_execute_calculation()`.
  The graph changes from 19,558 to 19,730 lines. This is an internal seam, not an
  execution-owner move.
- `f2af4f4` makes the prepared canonical value the freshness authority: raw
  0.0035 is compared with canonical 3.5, and actual stale repair evaluates its
  formula once. The execution owner changes from 712 to 679 lines, the graph
  from 19,730 to 19,736, production source is net -27, and the whole source/test
  diff is net -83. It adds no ledger or selected-claim synchronization.
- `be2e7bf` synchronizes only accepted repair provenance at render,
  planning-capture, and aggregate caller boundaries. Production source is
  `+332/-50`, net 282, and the whole commit is `+792/-69`, net 723. Ambiguous
  refs remain preserved; this is not whole-ledger synchronization.
- `2cfa867` moves pure aggregate provenance selection and canonical operation
  family normalization to `financial_aggregate_projection.py`. The graph changes
  from 19,933 to 19,802 lines and the owner from 195 to 376; production source is
  `+197/-147`, net 50, and the whole commit is `+392/-184`, net 208. Repair
  acceptance, filtering order, and answer/state orchestration remain graph-owned.

The stale freshness checkpoint passed 29 focused tests, the 217-literal audit,
and 1,472 full tests. The `f2af4f4` state passed 345 unique focused tests plus
the same audit and 1,472 full tests. `be2e7bf` passed 560 affected tests, the
same audit, and 1,472 full tests; `2cfa867` passed 564 affected tests, the same
audit, and 1,476 full tests.

### Candidate recovery and deterministic planning

- `1a3979e` lets dependency and period contract-valid scalar recovery consume
  candidate operands, plan, and result without two discarded state/ledger
  projections. Source is `+36/-25`, net 11; tests are `+176/-57`, net 119; the
  whole commit is `+212/-82`, net 130. The primary projector remains intact.
- `af968a6` moves state-free difference/growth plan construction and typed
  raw/guarded selection to the execution owner. Production source is
  `+249/-118`, net 131; tests are `+182/-5`, net 177; the whole commit is
  `+431/-123`, net 308. Supported-path parity does not imply malformed-input
  evaluation- or exception-order parity.
- `ec93f8a` separately fixes percent-point policy evaluation against an
  incomplete plan. The graph is line-neutral at `+9/-9`; tests add 32 lines;
  the whole commit is `+41/-9`, net 32.

Validation progressed from 3 focused, 564 affected, the 217-literal audit, and
1,476 full tests after `1a3979e`, to 4 targeted, 107 focused owner/aggregate,
564 affected, the same audit, and 1,478 full tests after `af968a6`. After
`ec93f8a`, 4 targeted/adjacent, 29 execution-module, and 593 unique affected
tests passed with the same audit and 1,479 full tests.

### Dependency recalculation isolation and mode disposition

- `8296eb1` prevents stale parent `structured_result` or `subtask_results` from
  overriding the explicit dependency trace. It changes the dependency owner by
  2 lines, adds 63 test lines, and is net 65 overall.
- `ea84921` removes the synthetic recalculation state and raw-plan callback for
  supported scalar recovery. Existing executable plans build no raw plan;
  invalid or absent plans build one and pass it explicitly. The graph changes
  from 19,786 to 19,828 lines and the dependency owner from 2,835 to 2,796;
  production source is `+78/-75`, net 3, tests are `+167/-90`, net 77, and the
  whole commit is `+245/-165`, net 80. The full count moved from 1,480 to 1,479
  because the deleted synthetic helper's obsolete direct test was removed; this
  is not a regression claim.
- `d1114c6` adds the typed `rebuild`, `reuse`, and `unsupported_mode` dependency
  plan disposition. An executable non-`single_value` plan is unsupported and
  does not recalculate that row before raw-plan construction, candidate
  execution, or ratio formatting; the isolated no-change regression retains the
  original list/row identity. Existing scalar reuse and invalid/absent rebuild
  behavior remain unchanged. The graph changes from 19,828 to 19,831
  lines and the dependency owner from 2,796 to 2,813; source is `+22/-2`, net 20,
  tests add 46 lines, and the whole commit is `+68/-2`, net 66.

`8296eb1` passed 4 targeted tests, the 217-literal audit, and 1,480 full tests.
`ea84921` passed 3 targeted and 615 affected tests, the same audit, and 1,479
full tests. `d1114c6` passed 1 targeted and the same 615 affected tests, the same
audit, and 1,479 full tests on Python 3.13. No benchmark refresh ran for any of
these post-stop-line calculation changes.

### Required-candidate operand merge ownership

- `1f67638` moves the post-main required-candidate merge from the graph into the
  existing operand-resolution owner. The typed state-free result merges coherent
  rows into producer-scope-filtered candidates, evaluates required coverage, and
  applies complete-ratio candidate-first or otherwise current-first precedence.
  Candidate/evidence builders, producer-scope filtering, the lazy coherent-context
  builder gate, logging, and runtime projection remain graph-owned.
- The graph changes from 19,831 to 19,823 lines (`+12/-20`, net -8) and the
  operand owner from 1,770 to 1,854 lines (`+84`). Production source is
  `+96/-20`, net 76; tests are `+185/-15`, net 170; the whole commit is
  `+281/-35`, net 246.
- Validation passed 5/5 focused tests, 299/299 affected tests, the 217-literal
  runtime audit, and full discovery over 1,480/1,480 tests on Python 3.13.
  Benchmark refresh was NOT RUN.

This is a required-candidate precedence/merge ownership move, not a total-code,
executed-path, performance, private-mesh, or complete Phase 3 reduction claim.

### Direct structured operand acceptance ownership

- `25eeccb` moves the ordered direct structured-row acceptance stages from the
  graph into the existing operand-resolution owner. The typed state-free owner
  preserves required matching and surface validation, the first ambiguity gate,
  lookup direct-support filtering, the second lookup ambiguity gate, stable row
  order/identity, and no-stage list identity. The graph retains upstream
  row/evidence construction, coercion, consolidation-scope and target policy,
  the applicability gate, direct structured evidence preference/refinement,
  recovered context/evidence adoption, and runtime projection.
- The graph changes from 19,823 to 19,792 lines (`+14/-45`, net -31) and the
  operand owner from 1,854 to 1,953 lines (`+99`). Production source is
  `+113/-45`, net 68; tests are `+259/-10`, net 249; the whole commit is
  `+372/-55`, net 317. The extraction adapter's definition-to-next-definition
  span changes from 851 to 818 lines.
- Validation passed 7/7 targeted tests, 301/301 affected tests, the 217-literal
  runtime audit, and full discovery over 1,482/1,482 tests on Python 3.13.
  Benchmark refresh was NOT RUN.

This is a direct-acceptance ownership move, not a total-code, broad executed-path,
performance, private-mesh, end-to-end calculation-owner, or complete Phase 3
reduction claim.

### Recovered context adoption ownership

- `f1152b7` moves the duplicated state-free adoption bodies for graph-built
  period-comparison and coherent-ratio rows into the operand-resolution owner.
  The typed result preserves period recovered-first/current missing-fill versus
  coherent-ratio replacement, used-evidence filtering and order, existing-id
  exclusion, candidate duplicates, top-level row copies with nested identity,
  and no-context identity. The graph retains recovery eligibility,
  document/evidence collection, context-row builders, logging, the
  ratio-recovered flag, main precedence, and runtime projection.
- The graph changes from 19,792 to 19,776 lines (`+24/-40`, net -16) and the
  operand owner from 1,953 to 2,045 lines (`+92`). Production source is
  `+116/-40`, net 76; tests are `+263/-38`, net 225; the whole commit is
  `+379/-78`, net 301. The extraction adapter's definition-to-next-definition
  span changes from 818 to 800 lines.
- Validation passed 5/5 targeted tests, 355/355 affected tests, the 217-literal
  runtime audit, and full discovery over 1,483/1,483 tests on Python 3.13.
  Benchmark refresh was NOT RUN.

This is a recovered-row/evidence adoption ownership move, not a move of recovery
eligibility or context builders and not a total-code, broad executed-path,
performance, private-mesh, end-to-end calculation-owner, or complete Phase 3
reduction claim.

### Prepared preferred-slot adoption ownership

- `9f68408` moves the prepared direct preferred-slot decision and exact row
  overlay into the operand-resolution owner. The typed state-free resolver
  preserves higher/equal current-score rejection, same-raw ratio peer-unit
  alignment override, strict comparison order including NaN fallthrough,
  top-level row-copy and nested identity, exact field clearing/overlay, sequential
  row application, and input immutability. Its reason and alignment fields are
  inspectable contract outputs, not runtime trace fields. The graph retains
  applicability, runtime evidence overlay, row copying/matching/iteration,
  peer-unit preparation, and the stateful strongest-slot builder and scorer.
- The graph changes from 19,776 to 19,756 lines (`+16/-36`, net -20) and the
  operand owner from 2,045 to 2,151 lines (`+106`). Production source is
  `+122/-36`, net 86; tests are `+247/-9`, net 238; the whole commit is
  `+369/-45`, net 324. The extraction adapter remains 800 lines under the
  definition-to-next-definition count.
- Validation passed 5/5 targeted tests, 153/153 affected tests, the 217-literal
  runtime audit, and full discovery over 1,484/1,484 tests on Python 3.13.
  Benchmark refresh was NOT RUN.

This is a prepared preferred-slot adoption/overlay ownership move, not a move of
stateful evidence preparation, builder/scoring, or graph orchestration and not a
total-code, broad executed-path, performance, private-mesh, end-to-end
calculation-owner, or complete Phase 3 reduction claim.

### Post-coercion LLM operand selection ownership

- `6dc036e` moves two post-coercion state-free decisions into the operand owner.
  The first preserves per-row lookup direct-support, row identity, and reason;
  the second preserves ordered required matching/surface validation, lookup
  rematching, and direct-first missing-fill merge with the existing list,
  top-level copy, nested-identity, and input-immutability contracts. The graph
  retains LLM invocation, evidence lookup, scope-conflict skip, operand-id
  assignment, coercion, applicability, the enclosing exception boundary, and
  fallback orchestration. Owner reasons and application flags are not projected
  into runtime trace fields.
- The graph changes from 19,756 to 19,753 lines (`+20/-23`, net -3) and the
  operand owner from 2,151 to 2,270 lines (`+119`). Production source is
  `+139/-23`, net 116; tests are `+301/-2`, net 299; the whole commit is
  `+440/-25`, net 415. The extraction adapter's definition-to-next-definition
  span changes from 800 to 795 lines.
- Validation passed focused 4/4 tests, affected 279/279 tests, the 217-literal
  runtime audit, and full discovery over 1,486/1,486 tests on Python 3.13.
  Benchmark refresh was NOT RUN.

This move deletes only the graph's two direct imports of the migrated private
operand helpers. It is not a total-code, broad executed-path, performance,
private-mesh, end-to-end calculation-owner, or complete Phase 3 reduction claim.

### Ratio artifact conflict selection ownership

- `a5e4def` moves the state-free prepared-artifact conflict loop into the
  dependency owner. The graph still coerces the recalculated top-level result
  value and skips artifact construction when it is unavailable, then builds the
  ordered task-artifact rows from graph/ledger state. The typed owner receives
  those rows and the already-coerced numeric authority, applies outer-status
  fallback, artifact numeric-field precedence, the existing scaled tolerance,
  and stable first-conflict selection, and returns a shallow-copied row with the
  preservation marker. Its reason and flag are contract outputs, not runtime
  trace fields. Absolute-ratio transformation and caller no-change/final
  projection remain graph-owned, so a local selection is not guaranteed to
  reach final output.
- The graph changes from 19,753 to 19,747 lines (`+10/-16`, net -6) and the
  dependency owner from 2,813 to 2,889 lines (`+76`). Production source is
  `+86/-16`, net 70; tests are `+211/-24`, net 187; the whole commit is
  `+297/-40`, net 257.
- Validation passed focused 3/3 tests, affected 294/294 tests, the 217-literal
  runtime audit, and full discovery over 1,487/1,487 tests on Python 3.13.
  Benchmark refresh was NOT RUN.

This is a behavior-preserving state-free selector relocation, not a move of
task-artifact/ledger construction, absolute-ratio transformation, or final
projection and not a total-code, broad executed-path, performance, private-mesh,
whole-ledger, end-to-end calculation-owner, or complete Phase 3 reduction claim.

### Collapsed-ratio runtime magnitude projection ownership

- `1d6896c` moves only the query-approved negative runtime-ratio magnitude
  transformation into the aggregate owner. The graph retains runtime-trace and
  collapsed-row eligibility, completeness and query gates, prepares mutable
  top-level result/slot/primary copies, and retains downstream coherence,
  compact-answer, coverage, and final projection. The typed owner mutates those
  copies in the original order and returns the same calculation-result identity.
  It catches `TypeError`/`ValueError` with the existing partial `result_value`
  update while the old attached slots/render remain, and allows `RuntimeError`
  to propagate. It adds no reason, flag, or trace field.
- The graph changes from 19,747 to 19,737 lines (`+9/-19`, net -10) and the
  aggregate owner from 376 to 427 lines (`+51`). Production source is `+60/-19`,
  net 41; tests are `+166/-7`, net 159; the whole commit is `+226/-26`, net 200.
- Validation passed targeted 2/2 tests, affected 322/322 tests, the 217-literal
  runtime audit, and full discovery over 1,488/1,488 tests on Python 3.13.
  Benchmark refresh was NOT RUN.

This is a behavior-preserving state-free prepared-copy transformation, not a
move of query or rendering policy, aggregate sequencing, final projection, or
ledger state and not a total-code, broad executed-path, performance,
private-mesh, end-to-end calculation-owner, or complete Phase 3 reduction claim.

### Dependency post-candidate finalization ownership

- `7573d5f` moves two state-free dependency recalculation stages into the
  dependency owner. Stage 1 shallow-copies candidate operand rows, plan, and
  result in the existing order, creates the distinct mutable result copy, and
  decides from normalized `calculation_result.status`. The graph retains the
  absolute-ratio query/transform, task-artifact/ledger conflict short-circuit,
  and formatter. Stage 2 then applies a truthy formatted result and projects the
  final row with trace-first/fallback operands and plan, result-first/current-row
  source ids, and the same result identity. The nested non-`ok` path returns its
  supplied local row; original ordered list/row identities remain guaranteed
  only when the enclosing pass has no other change. No selected-evidence
  projection is added.
- The graph changes from 19,737 to 19,741 lines (`+24/-20`, net 4) and the
  dependency owner from 2,889 to 2,966 lines (`+92/-15`, net 77). Production
  source is `+116/-35`, net 81; tests are `+210/-0`, net 210; the whole commit is
  `+326/-35`, net 291.
- Validation passed targeted 2/2 tests, affected 375/375 tests, the 217-literal
  runtime audit, and full discovery over 1,489/1,489 tests on Python 3.13.
  Benchmark refresh was NOT RUN.

This is a behavior-preserving typed disposition/final-row relocation, not a
query, formatter, artifact/ledger, or selected-provenance ownership move and not
a total-code, broad executed-path, performance, private-mesh, end-to-end
calculation-owner, or complete Phase 3 reduction claim.

### Dependency structured-provenance adoption ownership

- `9089aa1` moves only the prepared structured-provenance adoption body into the
  dependency owner. The graph still constructs and normalizes the dependency
  row, resolves provenance through the stateful `vsm` structure graph, skips the
  owner when no provenance exists, and retains downstream evidence lookup,
  coercion, and append. The owner mutates the same graph-built row in the existing
  anchor, chunk-id, converted-unit preservation or realignment, and metadata
  overlay order. It preserves nested identity and leaves the provenance mapping
  unchanged; its reason and application flag are contract outputs, not trace
  fields. Graph fixtures were corrected to attach the structured graph to the
  actual `vsm` runtime surface, so the source-visible and high-magnitude branches
  now exercise the production lookup path.
- The graph changes from 19,741 to 19,676 lines (`+7/-72`, net -65) and the
  dependency owner from 2,966 to 3,089 lines (`+123`). Production source is
  `+130/-72`, net 58; tests are `+163/-10`, net 153; the whole commit is
  `+293/-82`, net 211.
- Validation passed targeted 5/5 tests, affected 296/296 tests, the 217-literal
  runtime audit, and full discovery over 1,490/1,490 tests. Benchmark refresh was
  NOT RUN.

This is a behavior-preserving in-place adoption relocation, not a move of
stateful provenance lookup, dependency-row construction, downstream evidence
coercion, graph/store state, or final projection and not a total-code, broad
executed-path, performance, private-mesh, end-to-end calculation-owner, or
complete Phase 3 reduction claim.

### Direct structured-evidence scorer ownership

- `e652bac` moves the pure direct structured-evidence base scorer and its ordered
  aggregate-role preference predicate into the operand owner. Typed results expose
  `no_structured_cells`, `surface_contract_not_satisfied`, or `evidence_scored`
  as contract-only reasons. Graph and lookup-recovery callers consume the owner
  directly, and the old graph-private scorer plus lookup-recovery scorer callback
  parameters are deleted. The graph retains evidence iteration, strongest-slot
  building, query/report-scope score augmentation, ambiguity and tie-break policy,
  and sequential preferred-slot adoption.
- Production source is `+217/-144`, net 73: the graph changes from 19,676 to
  19,581 lines, graph helpers from 6,322 to 6,311, reconciliation from 2,426 to
  2,428, lookup recovery from 599 to 609, and the operand owner from 2,270 to
  2,437. Tests are `+326/-30`, net 296; the whole commit is `+543/-174`, net 369.
- Validation passed targeted 6/6 tests, owner 37/37 plus affected 594/594 tests
  (631 total), the 217-literal runtime audit, and full discovery over
  1,490/1,490 tests. Benchmark refresh was NOT RUN.

This is a behavior-preserving scorer and neutral-predicate ownership relocation,
not a move of best-slot construction, graph state/scope iteration,
ambiguity/tie-break policy, sequential adoption, or runtime trace projection and
not a total-code, broad executed-path, performance, broad private-mesh,
end-to-end calculation-owner, or complete Phase 3 reduction claim.

### Prepared aggregate answer application ownership

- `0409dde` moves prepared aggregate answer-candidate application and final-answer
  projection synchronization into the aggregate owner. The owner preserves the
  same aggregate projection and existing calculation-result identities, applies
  formatted, conditional aggregate-rendered, and optional ok-status mutations in
  the existing order, then returns a new normalized current-first stable merged
  claim-id list. Flag lookup, empty-answer laziness, and partial-mutation exception
  boundaries remain unchanged.
- The graph retains candidate construction, refresh and selection, mutable
  aggregate state/evidence, artifact and ledger work, stale repair, answer
  precedence, and final orchestration. All eight prepared-candidate callers and
  both remaining direct synchronization callers use the typed owner; the two old
  graph-private helper bodies are deleted.
- Production source is `+225/-124`, net 101: the graph changes from 19,581 to
  19,578 lines (`+120/-123`, net -3) and the aggregate owner from 427 to 531
  (`+105/-1`, net 104). Tests are `+282/-4`, net 278; the whole commit is
  `+507/-128`, net 379.
- Validation passed targeted 4/4 tests, affected 379/379 tests, the 217-literal
  runtime audit, and full discovery over 1,491/1,491 tests. Benchmark refresh was
  NOT RUN.

This is a behavior-preserving prepared-candidate application and projection-sync
ownership relocation, not a move of aggregate answer selection/precedence,
state/evidence or artifact/ledger orchestration, stale repair, final projection,
or a total-code, broad executed-path, performance, broad private-mesh,
end-to-end calculation-owner, or complete Phase 3 reduction claim.

### Aggregate provenance filtering ownership

- `1a4a826` moves generated aggregate-provenance filtering into the aggregate
  owner. The typed owner receives a graph-prepared projection and kept-evidence-id
  sequence. An empty normalized kept set returns the exact input projection;
  otherwise the owner preserves the existing shallow-copy order, stable source-id
  normalization, `ev_`/`recon::` filtering, retained nested identities, and
  conditional invalid-subtask replacement behavior. It adds no reason, flag, or
  trace field.
- The graph retains aggregate evidence and kept-id selection, the projection-
  rebuild gate, selected-claim filtering, final-answer surface-operand append,
  stale repair, artifact/ledger work, and final orchestration. Both graph callers
  consume the typed owner and the old graph-private helper plus its legacy direct
  test are deleted.
- Production source is `+81/-48`, net 33: the graph changes from 19,578 to
  19,544 lines (`+14/-48`, net -34) and the aggregate owner from 531 to 598
  (`+67`). Tests are `+223/-44`, net 179; the whole commit is `+304/-92`, net 212.
- Validation passed targeted 3/3 tests, affected 339/339 tests, the 217-literal
  runtime audit, and full discovery over 1,491/1,491 tests. Benchmark refresh was
  NOT RUN.

This is a behavior-preserving aggregate-provenance copy/filter ownership
relocation, not a move of evidence selection, selected claims, aggregate answer
selection/precedence, stale repair, artifact/ledger or final projection
orchestration, and not a total-code, broad executed-path, performance, broad
private-mesh, end-to-end calculation-owner, or complete Phase 3 reduction claim.

### Recursive nested aggregate-row synchronization ownership

- `fee6017` moves the graph-private recursive nested-subtask row synchronizer to
  the aggregate owner. The typed state-free owner receives graph-prepared ordered
  rows, builds the normalized current-row authority map before recursion, and
  preserves last-id-wins precedence, all three nested subtask surfaces, stable
  order, invalid-item skipping, ancestor-cycle and depth limits, conditional
  shallow-copy identities, input immutability, and uncaught exception order. It
  adds no reason, flag, callback, graph state, or trace field.
- The graph retains the empty-projection and unchanged promotion/alignment gates,
  nested-result promotion, preliminary and final projection rebuilds, dependency
  alignment, preserved-field merge, and later state/evidence, artifact/ledger,
  repair, and answer orchestration. Its sole caller consumes the typed owner and
  the old graph-private body is deleted.
- Production source is `+78/-53`, net 25: the graph changes from 19,544 to
  19,498 lines (`+7/-53`, net -46) and the aggregate owner from 598 to 669
  (`+71`). Tests are `+218/-6`, net 212; the whole commit is `+296/-59`, net 237.
- Validation passed targeted 3/3 tests, affected 325/325 tests, the 217-literal
  runtime audit, and full discovery over 1,492/1,492 tests. Benchmark refresh was
  NOT RUN.

This is a behavior-preserving prepared recursive nested-row consistency
ownership relocation, not a move of promotion, dependency alignment, projection
rebuild policy, final projection, state/evidence or artifact/ledger work, repair,
answer precedence or final orchestration, and not a total-code, broad executed-
path, performance, broad private-mesh, end-to-end calculation-owner, or complete
Phase 3 reduction claim.

### Aggregate answer-candidate payload packaging ownership

- `3e7394b` moves the base and refreshed aggregate-answer candidate packagers to
  the aggregate owner beside its existing candidate application seam. The typed
  state-free owner preserves answer normalization, stable blank-filtered but
  duplicate-retaining claim-id order, the three existing boolean flags, fresh
  candidate/list identities, input immutability, refreshed mapping copy and
  fallback behavior, and the exact mapping/string/boolean access and exception
  order. It adds no new decision reason or trace field.
- Seven direct base calls and the single refreshed call remain at their original
  graph branch or loop positions. The graph retains candidate discovery,
  scoring/selection, narrative refresh and refresh policy, call placement and
  laziness, application invocation and answer precedence, projection/state/
  evidence mutation, rebuild, and final orchestration. The two old graph-private
  packagers and all exact private self references are deleted.
- Production source is `+130/-80`, net 50: the graph changes from 19,498 to
  19,482 lines (`+64/-80`, net -16) and the aggregate owner from 669 to 735
  (`+66`). Tests are `+210/-1`, net 209; the whole commit is `+340/-81`, net 259.
- Validation passed targeted 3/3 tests, affected 326/326 tests, the 217-literal
  runtime audit, and full discovery over 1,493/1,493 tests. Benchmark refresh was
  NOT RUN.

This is a behavior-preserving prepared candidate payload/schema ownership
relocation, not a move of candidate discovery or selection, refresh policy,
application or answer precedence, aggregate composition, projection/state/
evidence mutation, rebuild, or final orchestration, and not a total-code, broad
executed-path, performance, broad private-mesh, end-to-end calculation-owner, or
complete Phase 3 reduction claim.

### Dependency-source ratio-result projection ownership

- `c932a17` moves the graph-private dependency-source ratio-result builder into
  `financial_dependency_projection.py` as a typed state-free owner seam. It
  receives only graph-prepared result/slot/value/unit/render/source-id inputs and
  preserves literal overwrite and exception order, fresh result/answer-slot/
  primary/group/role/list containers, untouched nested identities, the exact
  four-surface source-id-list alias, and exact numerator/denominator slot reuse.
- The graph keeps dependency source-slot construction and selection, component
  ranking and slot construction, same-slot/numeric gates, ratio formula/query and
  absolute policy, value/unit extraction, source-id cleaning, owner applicability
  and laziness, and compact formatting. The old private builder and all exact self
  references are deleted.
- Production source is `+91/-67`, net 24: the graph changes from 19,482 to
  19,431 lines (`+16/-67`, net -51) and the dependency owner from 3,089 to
  3,164 (`+75`). Tests are `+246/-3`, net 243; the whole commit is `+337/-70`,
  net 267.
- Validation passed targeted 3/3 tests, affected owner/subtask 297/297 tests, the
  217-literal runtime audit, full discovery over 1,494/1,494 tests, and
  `git diff --check`. Benchmark refresh was NOT RUN.

This is a behavior-preserving prepared dependency-source ratio-result projection
ownership relocation, not source selection, ratio formula/query policy,
formatting, dependency precedence, aggregate projection, state/ledger or final-
answer ownership, and not a total-code, broad executed-path, performance, broad
private-mesh, end-to-end calculation-owner, or complete Phase 3 reduction claim.

### Aggregate projection-row surface synchronization ownership

- `e777269` moves the graph-private numeric-slot selector and prepared projection-
  row surface synchronizer into `financial_aggregate_projection.py` as one typed,
  state-free owner seam. It receives only the selected row, raw answer, and raw
  rendered value and preserves first-candidate ratio/growth versus last-candidate
  other selection, exact raw output surfaces, conditional shallow-copy/nested-
  identity behavior, lookup series/container/derived-metric synchronization,
  input immutability, repeated operation-family access, and exception order. It
  adds no reason, application flag, or trace field.
- The graph retains candidate-index and sentence selection, numeric conflict and
  coverage gates, rendered extraction, row iteration, lookup-component
  propagation, updated-row mapping, ordered/slot-row propagation, projection
  rebuild, and final orchestration. Both old graph helpers and exact private self
  references are deleted.
- Production source is `+134/-100`, net 34: the graph changes from 19,431 to
  19,340 lines (`+9/-100`, net -91) and the aggregate owner from 735 to 860
  (`+125`). Tests are `+324/-15`, net 309; the whole commit is `+458/-115`,
  net 343.
- Validation passed targeted 4/4 tests, affected aggregate/subtask 327/327 tests,
  the 217-literal runtime audit, full discovery over 1,495/1,495 tests, and
  `git diff --check`. Benchmark refresh was NOT RUN.

This is a behavior-preserving prepared projection-row surface synchronization
ownership relocation, not answer or candidate selection, aggregate precedence,
lookup propagation, final projection, state/evidence or artifact/ledger
ownership, and not a total-code, broad executed-path, performance, broad private-
mesh, end-to-end calculation-owner, or complete Phase 3 reduction claim.

### Ratio result-display synchronization ownership

- `f8eb8cd` moves the graph-private ratio result-display synchronizer into
  `financial_answer_slots.py` as a typed state-free input/result seam. Status,
  operation-family, source-stated, percent-unit, parser, and equivalence gates
  preserve their order. A material formula mismatch returns a shallow result and
  derived-metric copy that survives later vetoes; ordinary successful display
  synchronization mutates the exact prepared result and creates fresh answer-slot
  and primary-value containers. Untouched nested aliases, policy normalization,
  current-surface precedence, and caught-versus-propagated exception behavior are
  unchanged.
- The graph retains ordered-row copy/family/truthy-result gates, before/after
  display comparison, compact-answer construction, row answer/result updates,
  and all state, active-subtask, operand, period, and metric formatting. Both
  direct calls remain in their original positions; the old graph helper and all
  exact private references are deleted.
- Production source is `+123/-88`, net 35: the graph changes from 19,340 to
  19,264 lines (`+10/-86`, net -76) and the answer-slot owner from 483 to 594
  lines (`+113/-2`, net 111). Tests are `+319/-37`, net 282; the whole commit is
  `+442/-125`, net 317.
- Validation passed targeted 3/3 tests, affected answer-slot/subtask 249/249
  tests, the 217-literal runtime audit, full discovery over 1,495/1,495 tests,
  and `git diff --check`. Benchmark refresh was NOT RUN.

This is a behavior-preserving ratio calculation-result and primary answer-slot
display-consistency ownership relocation, not formula or ratio calculation,
query policy, compact-answer construction, row selection/propagation, aggregate
precedence, state/evidence or artifact/ledger ownership, and not a total-code,
broad executed-path, performance, broad private-mesh, end-to-end calculation-
owner, or complete Phase 3 reduction claim.

### Aggregate arithmetic-component synchronization ownership

- `bfb5887` moves the three graph-private prepared lookup-slot arithmetic-
  component helpers into `financial_aggregate_projection.py` behind a typed,
  state-free input/result seam. It preserves empty/ineligible exact identity,
  eligible conditional shallow-copy and nested aliases, concept-first then
  bidirectional-label stable first-match, `None`-only value overlay, source
  fallback/aliases, role/group/series/delta behavior, input immutability, and
  access/exception order. It adds no reason, application flag, or trace field.
- The graph retains lookup primary-slot preparation and its truthy gate,
  sequential per-row owner invocation, task-id/equality update mapping,
  ordered/slot-row propagation, projection rebuild, and all later state/evidence,
  artifact/ledger, repair, and answer orchestration. The old graph definitions
  and exact private self references are deleted.
- Production source is `+119/-88`, net 31: the graph changes from 19,264 to
  19,184 lines (`+8/-88`, net -80) and the aggregate owner from 860 to 971
  (`+111`). Tests are `+320/-1`, net 319; the whole commit is `+439/-89`, net 350.
- Validation passed targeted 2/2 tests, affected aggregate/subtask 327/327 tests,
  the 217-literal runtime audit, full discovery over 1,496/1,496 tests, and
  `git diff --check`. Benchmark refresh was NOT RUN.

This is a behavior-preserving prepared lookup-slot to arithmetic component,
series, and delta synchronization ownership relocation, not lookup selection,
projection-row surface selection, row-map propagation, aggregate precedence,
state/evidence or artifact/ledger ownership, final projection, and not a total-
code, broad executed-path, performance, broad private-mesh, end-to-end
calculation-owner, or complete Phase 3 reduction claim.

### Aggregate artifact payload synchronization ownership

- `49cbb78` moves the graph-private late aggregate-artifact payload synchronizer
  into `financial_task_artifacts.py` behind a typed, state-free input/result seam.
  It preserves copy-all-before-search, raw exact-id stable first-match, no-match
  fresh top-level copies, target payload/artifact and projection-surface shallow
  copies, raw final-answer summary slicing, nested aliases, input immutability,
  and uncaught access/copy/slice order. It adds no reason, application flag, or
  trace field.
- The graph retains its initial artifact-list copy, all ratio, rendered,
  completeness, compact-formatter and projection-mutation gates, and the exact
  `artifacts is not None` plus truthy-id gate. `None` or blank id remains owner-
  zero, while an empty list plus nonblank id remains owner-one and the applicable
  path retains both copy passes. Aggregate artifact creation/finalization and
  final ledger orchestration remain graph-owned. The old graph definition and
  exact private self reference are deleted.
- Production source is `+62/-35`, net 27: the graph changes from 19,184 to
  19,159 lines (`+10/-35`, net -25) and the task-artifact owner from 1,128 to
  1,180 (`+52`). Tests are `+295/-4`, net 291; the whole commit is `+357/-39`,
  net 318.
- Validation passed targeted 4/4 tests, affected 348/348 tests, the 217-literal
  runtime audit, full discovery over 1,498/1,498 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is a behavior-preserving prepared aggregate artifact payload and summary
synchronization ownership relocation, not artifact creation, ledger-level id/
order or whole-ledger synchronization, ratio/query/formatting policy, state or
final-projection ownership, and not a total-code, broad executed-path,
performance, broad private-mesh, end-to-end calculation-owner, or complete
Phase 3 reduction claim.

### Rendered-unit operand normalization repair ownership

- `7888914` moves the graph-private single-row embedded/rendered-unit
  normalization repair into `financial_operand_resolution.py` as a plain public
  state-free transform. The implementation is relocated literally: every path
  returns a fresh top-level row, preserves untouched nested aliases and input
  immutability, and retains raw/rendered/policy access, scaled tolerance,
  repeated float conversion, embedded-versus-rendered `NaN` behavior, stable
  first rendered match, original-field precedence, and caught/uncaught exception
  order. It adds no wrapper, reason, application flag, callback, or trace field.
- The four graph calls remain in their original semantic positions: dependency
  row construction before structured provenance/evidence coercion; candidate
  preparation after plan guards and before multi-row alignment; and the two
  prepared ratio-append row sites before later coverage, merge, and projection.
  The graph retains every construction and applicability gate, plan/operand-map
  propagation, multi-row sibling-table alignment, ratio/append policy, and
  state/artifact/final orchestration. The old definition and private self
  references are deleted.
- Production source is `+100/-98`, net 2: the graph changes from 19,159 to
  19,066 lines (`+5/-98`, net -93) and the operand owner from 2,437 to 2,532
  (`+95`). Tests are `+314/-3`, net 311; the whole commit is `+414/-101`, net
  313.
- Validation passed targeted 5/5 tests, affected 612/612 tests, the 217-literal
  runtime audit, full discovery over 1,500/1,500 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is a behavior-preserving single-row embedded/rendered-unit normalization-
repair ownership relocation, not multi-row unit alignment, dependency binding,
ratio or append policy, aggregate repair or composition, state/artifact/ledger
ownership, and not a total-code, broad executed-path, performance, broad private-
mesh, end-to-end calculation-owner, or complete Phase 3 reduction claim.

### Shared-table ratio display-unit alignment ownership

- `00b6357` moves the graph-private same-table/context multi-row ratio display-
  unit alignment into `financial_operand_resolution.py` as a plain state-free
  transform. The old body is relocated literally, including length and policy
  gates, eager configured-scale conversion, repeated unit normalization,
  table-id-first or complete section/statement/scope grouping, unsorted
  largest-scale selection, partial repairs, and uncaught access/exception order.
- No-change returns the exact input list and row identities even after discarded
  copies. Any repair returns a fresh list and fresh top-level copy for every row,
  preserves untouched nested aliases and order, and leaves inputs unmodified.
  There is no new tolerance or finiteness gate; existing normalizer behavior,
  including accepted `NaN`, is unchanged.
- The three graph calls retain their original semantic positions after the outer
  length/evidence gates: empty-evidence and unchanged-evidence paths pass the
  original rows, while accepted evidence realignment passes its prepared aligned
  rows. The graph retains the evidence-driven sibling aligner, candidate
  selection, ratio-family preparation and operand-map propagation, ratio policy,
  state/artifact work, and final orchestration. The old definition and private
  self references are deleted.
- Production source is `+82/-81`, net 1: the graph changes from 19,066 to 18,989
  lines (`+4/-81`, net -77) and the operand owner from 2,532 to 2,610 (`+78`).
  Tests are `+242/-2`, net 240; the whole commit is `+324/-83`, net 241.
- Validation passed targeted 5/5 tests, affected 613/613 tests, the 217-literal
  runtime audit, full discovery over 1,501/1,501 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is a behavior-preserving shared-context multi-row ratio display-unit
alignment ownership relocation, not evidence-driven sibling candidate
selection, single-row repair, unit inference, ratio/query policy, preparation
or operand-map propagation, state/artifact/ledger or final orchestration, and
not a total-code, broad executed-path, performance, broad private-mesh,
end-to-end calculation-owner, or complete Phase 3 reduction claim.

### Aggregate composition-state transition ownership

- `93bc72b` promotes the private aggregate-composition carrier to public
  `AggregateCompositionState` with no compatibility alias and moves the common
  graph transition into `financial_aggregate_state.py`. The transition preserves
  answer normalization and lazy fallback; current-first claim processing,
  repeated string conversion and stable dedupe; projection reset/dictionary/
  retained-alias precedence; lock fallback; separately evaluated feedback
  clearing; fresh carrier/list identity; input immutability; and uncaught access,
  normalization, string, hash, truthiness, and constructor exception order.
- The five graph calls remain in their original branch positions and consume each
  returned carrier sequentially. Graph still owns all producer builders and
  gates, initial/final carrier construction, later `_replace` transitions,
  broader answer/claim/projection precedence, state/evidence/LLM work, and final
  orchestration. The old graph helper and private carrier name are deleted.
- Production source is `+61/-58`, net 3: the graph changes from 18,989 to 18,943
  lines (`+10/-56`, net -46) and the aggregate-state owner from 112 to 161
  (`+51/-2`, net 49). Tests are `+328/-1`, net 327; the whole commit is
  `+389/-59`, net 330.
- Validation passed targeted 2/2 tests, affected 594/594 tests, the 217-literal
  runtime audit, full discovery over 1,503/1,503 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is a behavior-preserving public aggregate composition-carrier and common
state-transition ownership relocation, not producer or answer selection,
broader composition or answer precedence, state/evidence/LLM/artifact/ledger or
final-orchestration ownership, and not a total-code, broad executed-path,
performance, broad private-mesh, end-to-end calculation-owner, or complete
Phase 3 reduction claim.

### Aggregate signature and growth sign-rank primitive ownership

- `3d3948b` moves canonical aggregate-result signature and growth operand
  sign-consistency ranking from the graph into plain public
  `financial_aggregate_projection.py` primitives. Seven signature and four rank
  calls remain at their existing graph positions, including the explicit repair
  `dict(row)` input and repeated comprehension/nested-ranking calls; the old graph
  definitions and private self references are deleted.
- Signature metric/family precedence, copy and lazy-return order, growth/non-growth
  disposition, current-before-prior conversion, `TypeError`/`ValueError`, zero,
  `NaN`, infinity, identity, immutability, and uncaught access behavior are
  preserved. Full dedupe, rank tuples, nested promotion, result precedence, and
  graph state/evidence/artifact/ledger orchestration remain graph-owned.
- Production source is `+61/-57`, net 4: the graph changes from 18,943 to 18,899
  lines (`+13/-57`, net -44) and the aggregate owner from 971 to 1,019 (`+48`).
  Tests are `+384/-9`, net 375; the whole commit is `+445/-66`, net 379.
- Validation passed targeted 6/6 tests, affected 576/576 tests, the 217-literal
  runtime audit, full discovery over 1,504/1,504 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is a behavior-preserving canonical signature/sign-rank primitive ownership
relocation, not full aggregate ranking, dedupe, promotion, precedence, state,
artifact, ledger, or final-orchestration ownership, and not a total-code, broad
executed-path, performance, broad private-mesh, end-to-end calculation-owner, or
complete Phase 3 reduction claim.

### Dependency row unit inference ownership

- `db89499` moves dependency-row display and normalized-unit inference from the
  graph into the plain public `financial_dependency_projection.py` primitive.
  The four calls remain at their existing semantic positions, including the
  conditional second inference; the old graph definition and private self
  references are deleted.
- Slot raw-unit precedence, lazy sibling-result fallback, whitespace suppression,
  normalized-unit handling, `UNKNOWN`-only policy access, percent/KRW/count
  membership order, KRW configured-unit fallback, input immutability, and uncaught
  access/exception order are preserved. Caller characterization records the
  combined retrieved-context/task-output sequence as `17454` twice followed by
  `17199` twice, with a separate fixture exercising `17199` three times.
- Production source is `+28/-27`, net 1: the graph changes from 18,899 to 18,877
  lines (`+5/-27`, net -22) and the dependency owner from 3,164 to 3,187 (`+23`).
  Tests are `+254/-2`, net 252; the whole commit is `+282/-29`, net 253.
- Validation passed targeted 4/4 tests, affected 632/632 tests, the 217-literal
  runtime audit, full discovery over 1,505/1,505 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is a behavior-preserving dependency-row unit-inference ownership relocation,
not dependency binding, row construction, conditional re-inference orchestration,
ratio policy, unit-policy cleanup, state/evidence/artifact/final orchestration,
and not a total-code, broad executed-path, performance, broad private-mesh,
end-to-end calculation-owner, or complete Phase 3 reduction claim.

### Dependency task-output KRW consistency ownership

- `991efb2` moves the graph-private dependency task-output normalized-KRW
  consistency predicate into the plain public dependency owner. The row-coercion
  and table-metadata-repair calls remain at their original semantic positions;
  the old graph definition and private self references are deleted.
- The dependency/source/normalized-unit short circuits, raw-before-unit access,
  raw-to-result-unit fallback, whitespace suppression, operand normalization,
  exact scaled tolerance, input immutability, and current-before-expected
  conversion are unchanged. The normalized-value getter is inside the conversion
  `try`, so its `TypeError`/`ValueError` returns `False`; earlier mapping errors of
  those types and all `RuntimeError` instances propagate. The representative
  caller trace remains `False, True, False, True` across numerator/denominator
  row coercion followed by numerator/denominator table repair.
- Production source is `+25/-23`, net 2: the graph changes from 18,877 to 18,857
  lines (`+3/-23`, net -20) and the dependency owner from 3,187 to 3,209 (`+22`).
  Tests are `+391/-1`, net 390; the whole commit is `+416/-24`, net 392.
- Validation passed targeted 2/2 tests, affected 633/633 tests, the 217-literal
  runtime audit, full discovery over 1,506/1,506 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is a behavior-preserving dependency task-output consistency-predicate
ownership relocation, not broader KRW or unit policy, row coercion, table repair,
dependency binding/evidence, state/artifact/final orchestration, and not a
total-code, broad executed-path, performance, broad private-mesh, end-to-end
calculation-owner, or complete Phase 3 reduction claim.

### Table-label metadata lookup-score ownership

- `db84c7c` moves the graph-private table-label metadata scorer into the plain
  public `financial_operand_resolution.py` owner. The three graph calls remain
  immediately after their slot builders and before caller-owned selection policy;
  the direct-lookup and dependency-row callers still score an empty slot, while
  the period-context caller still skips it. The old graph definition and private
  self references are deleted.
- Empty-slot and table-label gates, normalized/raw-unit and digit-threshold
  access, all additive weights, repeated getters and normalizations, compact-label
  matching, input immutability, and uncaught mapping/copy/string/regex/iteration/
  normalization exception order are unchanged. The owner adds no wrapper, reason,
  flag, callback, config input, or trace field.
- Production source is `+57/-56`, net 1: the graph changes from 18,857 to 18,805
  lines (`+4/-56`, net -52) and the operand owner from 2,610 to 2,663 (`+53`).
  Tests are `+490/-9`, net 481; the whole commit is `+547/-65`, net 482.
- Validation passed targeted 5/5 tests, affected 632/632 tests, the 217-literal
  runtime audit, full discovery over 1,507/1,507 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is a behavior-preserving table-label metadata score-ownership relocation
and 52-line old graph-body deletion, not a scoring-policy improvement, slot or
evidence selection ownership, period/context/scope/ambiguity/tie/grouping policy,
total-code or broad executed-path reduction, performance, broader private-mesh
cleanup, end-to-end calculation ownership, or complete Phase 3.

### Reconciliation artifact evidence-reference ownership

- `45aa2de` moves the graph-private reconciliation evidence-reference pair into
  `financial_task_artifacts.py`. The strict-dictionary ten-field operand-ref
  collector remains owner-private; it uses the private `_clean_source_row_ids`
  import from `financial_runtime_normalization.py`. Only the plain public
  `enrich_reconciliation_artifact_refs(...)` function enters the owner export
  surface. The two graph calls remain at their existing semantic positions, and
  the old graph definitions and private self references are deleted.
- The empty-ref path returns the exact artifact-list identity before task-id or
  artifact access. The nonempty path returns a fresh list and fresh top-level copy
  of every artifact with untouched nested aliases. Operand-before-extra and
  existing-raw-before-new stable ref order, task-id union, kind/task/repeated-
  payload/result/status gates, input immutability, and uncaught mapping/copy/
  truthiness/string/iteration/hash/access exception order are unchanged.
- The first graph adapter still prepares artifacts, tasks, active task id, and
  operand rows before enrichment and passes the owner result into operand-set
  artifact construction. The aggregate-feedback adapter still prepares source
  task ids, operands, and integrity refs before enrichment and passes the result
  into task-artifact trace and integrity/replan work. Owner exceptions still stop
  those downstream consumers.
- Production source is `+74/-71`, net 3: the graph changes from 18,805 to 18,738
  lines (`+3/-70`, net -67) and the task-artifact owner from 1,180 to 1,250
  (`+71/-1`, net 70). Tests are `+528/-3`, net 525; the whole commit is
  `+602/-74`, net 528.
- Validation passed targeted 5/5 tests, affected 610/610 tests, the 217-literal
  runtime audit, full discovery over 1,510/1,510 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is a behavior-preserving prepared reconciliation evidence-reference
collection/enrichment ownership relocation and 66-line old graph-body deletion,
not artifact creation/finalization, whole-ledger or graph-state ownership,
integrity/replan policy, total-code or broad executed-path reduction, performance,
broader private-mesh cleanup, end-to-end calculation ownership, or complete
Phase 3.

### Direct target-metric fallback conflict ownership

- `3794f19` moves the graph-private direct target-metric fallback unit/value
  conflict and aggregate-preference predicate into the plain public
  `financial_operand_resolution.py` owner. The sole graph call remains after
  target construction, evidence coercion, target truthiness, and requested-scope
  acceptance. The old graph definition and private self references are deleted;
  no wrapper, result carrier, callback, reason, flag, config input, compatibility
  alias, or trace field is added.
- Target/existing gates, matcher-specific row-copy repetition, repeated known-unit
  normalization, first matching required operand, aggregate-role veto, aggregate-
  like surface laziness, structured-source access, stable first-conflict order,
  and input immutability are unchanged. `operand_row_values_differ` preserves its
  helper-local float `TypeError`/`ValueError` catch and raw/value fallback; the
  predicate adds no broader catch, so mapping, matcher, copy, truthiness, string,
  normalization, source-id cleaning, iteration, `RuntimeError`, and other
  exceptions still propagate.
- Graph retains the target builder, evidence pool/build/coercion, outer scope gate,
  target adoption and evidence append, candidate preparation, state/artifact
  projection, and final orchestration. The owner tests pin the direct decision,
  copy/access and exception contract; the existing graph fixture pins owner-zero
  target/scope gates, exact post-coercion inputs, false/true adoption behavior, and
  exception stop.
- Production source is `+74/-73`, net 1: the graph changes from 18,738 to 18,667
  lines (`+2/-73`, net -71) and the operand owner from 2,663 to 2,735 (`+72`).
  Tests are `+570/-125`, net 445; the whole commit is `+644/-198`, net 446.
- Validation passed targeted 3/3 tests, affected 552/552 tests, the 217-literal
  runtime audit, full discovery over 1,509/1,509 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is a behavior-preserving prepared direct-target fallback conflict-predicate
ownership relocation and 71-line old graph-body deletion, not target construction,
scope/evidence selection, whole-operand precedence, scoring or policy improvement,
callback/private-mesh cleanup, total-code or broad executed-path reduction,
performance, end-to-end calculation ownership, or complete Phase 3.

### Structured-unit source-slot equivalence ownership

- `2662dfa` moves the graph-private structured-unit-realigned operand/source-slot
  equivalence predicate into the plain public dependency owner. The graph imports
  and calls the owner once at the same position inside dependency-coherence ranking;
  the old graph definition and private self references are deleted. No wrapper,
  result carrier, reason, flag, callback, config input, compatibility alias, or
  trace field is added.
- Marker-first direct copy and fallback-sequence laziness are unchanged. Without
  the marker, operand role/raw/ids and each fallback row's role/raw filters precede
  cleaned-id overlap and the survivor copy. A nonempty candidate list retains
  source-id cleaning with `task_output:` exclusion before source raw/unit access,
  then candidate raw/unit and cleaned non-task-id scanning, stable first match,
  input immutability, and uncaught
  mapping/copy/truthiness/string/normalization/cleaning/iteration/hash/prefix
  exceptions. Fallback preselection still includes task-output ids.
- Graph retains operation-family gating, source-slot/candidate/marked-row building,
  source-task selection, material and anchor/projection mismatch gates, rank
  disposition, ratio-scope checks, and all provenance/adoption/state/artifact/final
  orchestration. The owner matrix pins the direct and fallback decision/access/
  exception contract; the graph fixture pins owner-zero gates, exact prepared
  copies, true/false rank disposition, and exception stop before later scope work.
- Production source is `+50/-49`, net 1: the graph changes from 18,667 to 18,620
  lines (`+2/-49`, net -47) and the dependency owner from 3,209 to 3,257 (`+48`).
  Tests are `+404/-0`, net 404; the whole commit is `+454/-49`, net 405.
- Validation passed targeted 3/3 tests, affected 632/632 tests, the 217-literal
  runtime audit, full discovery over 1,511/1,511 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is a behavior-preserving prepared structured-unit/source-slot equivalence
predicate relocation and 47-line old graph-body deletion, not source-task or slot
selection, complete coherence-rank/provenance-adoption ownership, unit-policy
improvement, total-code or broad executed-path reduction, performance, broader
private-mesh cleanup, end-to-end calculation ownership, or complete Phase 3.

### Compact aggregate-synthesis prompt projection ownership

- `b14433d` moves the graph-private compact aggregate-synthesis prompt-row
  projection into the plain public aggregate owner and promotes the shared
  runtime-trace material-numeric predicate to a public function. The graph imports
  and calls the prompt owner once at the same point inside its existing synthesis
  `try`; runtime trace and the aggregate owner consume the same public predicate.
  The old graph body and private predicate name are deleted without a compatibility
  alias, wrapper, result carrier, reason, flag, callback, config input, or trace
  field.
- Calculation-result/answer-slot/ordered fallback precedence, operand copy before
  material filtering and task-id access, stable task grouping/order, fixed compact
  field and repeated-getter order, strict dictionary-row admission, fresh compact
  containers, retained nested aliases, input immutability, and uncaught owner
  exceptions are unchanged. The shared predicate preserves its `missing` gate,
  lazy unit/value fallback order, digit threshold, normalized-value access, raw-
  value fallback, no-mutation, and uncaught-exception behavior.
- Graph retains the LLM gate, model/structured-LLM/prompt construction, post-period-
  realignment inputs, JSON/debug/prompt and LLM invocation, enclosing catch/fallback,
  composition, state, evidence, and final orchestration. Runtime trace retains row/
  source-id preparation before the predicate and key construction, dedupe, and
  append afterward.
- Production source is `+91/-90`, net 1: the graph changes from 18,620 to 18,534
  lines (`+2/-88`, net -86), the aggregate owner from 1,019 to 1,106 (`+87`), and
  runtime trace remains 1,065 lines (`+2/-2`). Tests are `+857/-1`, net 856; the
  whole commit is `+948/-91`, net 857.
- Validation passed targeted 6/6 tests, affected 660/660 tests, the 217-literal
  runtime audit, full discovery over 1,516/1,516 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is behavior-preserving compact aggregate-synthesis input projection and
shared material-predicate ownership plus deletion of the 85-line old graph body,
not LLM/template/answer policy, token or prompt-size improvement, total-code or
broad executed-path reduction, performance, broader private-mesh cleanup, end-to-
end calculation ownership, or complete Phase 3.

### Table numeric-support evidence-promotion ownership

- `4c83b5f` moves the graph-private table numeric-support text helper and evidence
  promoter into `financial_numeric_surface.py`. The support-text helper remains
  owner-private; only `promote_table_numeric_support_evidence(...)` is public. The
  graph imports and calls that function once at the same non-narrative evidence-row
  position. The old graph definitions and self references are deleted without an
  alias, wrapper, result carrier, reason, flag, callback, config input, or trace
  field.
- Metadata copy and table-line splitting, repeated retained-line normalization,
  empty-line-set laziness, render/percent unit-term preparation, numeric/unit/
  punctuation stripping, label and numeric gates, answer-major equivalence, stable
  first-four selection, header access order, and uncaught exceptions are unchanged.
  No support returns the exact evidence identity. Supported promotion preserves
  fresh top-level evidence and metadata copies, claim-before-quote access/write
  order, nested aliases, and input immutability.
- Graph retains answer-candidate and evidence-selection/support gates, local
  evidence and pre-owner metadata copies, evidence-id handling, retrieved-narrative
  skip, returned-row adoption, later filtering, append-evidence behavior, state,
  artifact/ledger work, and final orchestration.
- Production source is `+88/-87`, net 1: the graph changes from 18,534 to 18,449
  lines (`+2/-87`, net -85) and the numeric-surface owner from 453 to 539 lines
  (`+86`). Tests are `+466/-0`, net 466; the whole commit is `+554/-87`, net 467.
- Validation passed targeted 3/3 tests, affected 581/581 tests, the 217-literal
  runtime audit, full discovery over 1,519/1,519 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is behavior-preserving table numeric-support text and prepared evidence-
promotion ownership plus deletion of the 84 graph definition lines, not evidence
selection or faithfulness policy, numeric-policy improvement, append-evidence
ownership, total-code or broad executed-path reduction, performance, broader
private-mesh cleanup, end-to-end calculation ownership, or complete Phase 3.

### Required-operand prose numeric-evidence surface-filter ownership

- `9224a29` moves graph `_surface_contract_numeric_evidence_items` into the plain
  public operand owner as `surface_contract_numeric_evidence_items(...)`. The sole
  graph caller imports the public function at the same unconditional position.
  The old graph definition, self references, and stale instance-test stub are
  deleted without a wrapper, result carrier, reason, flag, callback, config input,
  compatibility alias, or trace field.
- Left-to-right falsy gates, evidence copy before fixed claim/quote/raw surface
  access, blank/digit laziness, per-attempt operand copies, positive then negative
  then numeric predicate order, lazy id/anchor/surface key precedence, global
  first-seen dedupe, unique-break/duplicate-continue behavior, stable ordering,
  fresh retained top-level rows, nested aliases, input immutability, and uncaught
  exception stages remain unchanged.
- Graph retains evidence/reconciliation and required-list preparation, direct-
  grounding computation, unconditional call placement before narrative access,
  narrative/restriction gates, surface-result merge/dedupe/logging, the later
  missing-required fallback-row merge, LLM/state work, and final orchestration.
- Production source is `+48/-43`, net 5: the graph changes from 18,449 to 18,409
  lines (`+2/-42`, net -40) and the operand owner from 2,735 to 2,780 lines
  (`+46/-1`, net 45). Tests are `+441/-9`, net 432; the whole commit is
  `+489/-52`, net 437.
- Validation passed targeted 4/4 tests, affected 639/639 tests, the 217-literal
  runtime audit, full discovery over 1,521/1,521 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is behavior-preserving required-operand prose numeric-evidence surface-filter
ownership and deletion of the 40-line old graph body, not retrieval or evidence
selection, faithfulness or filtering-policy improvement, new runtime behavior,
total-code or broad executed-path reduction, performance, broader private-mesh
cleanup, end-to-end calculation ownership, or complete Phase 3.

### Retrieved ratio-context task-metric surface-detection ownership

- `d40ecc2603221a6eafd660a673d4f55604d9ed63` moves graph
  `_ratio_context_has_metric_surface` into the plain public operand owner as
  `ratio_context_has_metric_surface(...)`. The sole graph caller imports the
  public function at the same first-conflicting-row position; the old private
  definition and self references are deleted without a wrapper, carrier, reason,
  flag, callback, config input, compatibility alias, or trace field.
- Task metric-field and alias collection, repeated string normalization, stable
  label dedupe, all-context evidence/metadata copies and fixed-surface
  materialization before matching, first-match laziness, input immutability, and
  uncaught exception order remain unchanged.
- Graph retains existing ratio-result iteration and family/task/signature/status/
  artifact-backed/value/completeness/tolerance gates, exact context/task object
  invocation and logical result inversion, ratio recalculation/adoption,
  evidence selection, state, artifact, and final orchestration.
- Production source is `+53/-52`, net 1: the graph changes from 18,409 to 18,359
  lines (`+2/-52`, net -50) and the operand owner from 2,780 to 2,831 lines
  (`+51`). Tests are `+416/-0`, net 416; the whole commit is `+469/-52`, net 417.
- Validation passed targeted 3/3 tests, affected 679/679 tests, the 217-literal
  runtime audit, full discovery over 1,523/1,523 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is behavior-preserving retrieved ratio-context task-metric surface-detection
ownership and deletion of the 50-line old graph body, not conflict or precedence
policy, ratio recalculation or adoption, evidence selection, behavior or policy
improvement, total-code or broad executed-path reduction, performance, broader
private-mesh cleanup, end-to-end calculation ownership, or complete Phase 3.

### Source-task display-compatibility ownership

- `544f99d7bf2745d41d86e7c06266f111300ae57d` moves graph
  `_source_task_display_compatible_with_slot` into the plain public answer-slot
  owner as `source_task_display_compatible_with_slot(...)`. The sole graph caller
  invokes the public owner at the same truthy-source position; the old private
  definition and self references are deleted without a wrapper, carrier, reason,
  flag, callback, config input, compatibility alias, or trace field.
- Source-display-first normalization, rendered/raw equality, `task_output:` source,
  raw-unit blank/containment, normalized-unit and configured KRW-display short
  circuits, repeated policy-item stringification, input immutability, and uncaught
  exception order remain unchanged.
- Graph retains source-task/source-slot lookup and material gating, calculation-
  result/answer-slot preparation, blank-source owner-zero, exact call placement,
  True-path source-display adoption, False-path rendered/raw fallback, growth
  calculation/material semantics, state, artifact, and final orchestration.
- Production source is `+33/-33`, net 0: the graph changes from 18,359 to 18,328
  lines (`+1/-32`, net -31) and the answer-slot owner from 594 to 625 lines
  (`+32/-1`, net 31). Tests are `+355/-0`, net 355; the whole commit is
  `+388/-33`, net 355.
- Validation passed targeted 3/3 tests, affected 676/676 tests, the 217-literal
  runtime audit, full discovery over 1,525/1,525 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is behavior-preserving source-task display-compatibility ownership and
deletion of the 30-line old graph body, not source-task lookup, growth semantics,
numeric/render-policy improvement, new behavior, total-code or broad executed-
path reduction, performance, broader private-mesh cleanup, end-to-end calculation
ownership, or complete Phase 3.

### Aggregate-subtask numeric-conflict and direct-source-reference ownership

- `8d5e2c23eede1f73ce33ab650f20cd7022750e78` moves graph
  `_subtask_numeric_answers_conflict` and
  `_subtask_row_has_direct_source_refs` into plain public
  `financial_aggregate_projection.py` functions. The four numeric-conflict calls
  and sole direct-source call remain at their exact graph positions; the old
  private definitions and self references are deleted without a wrapper, carrier,
  reason, flag, callback, config input, compatibility alias, or trace field.
- Numeric conflict preserves candidate-before-current answer/formatted/rendered
  fallback, repeated calculation-result access, both extractor calls before the
  empty-side gate, and asymmetric candidate-major/current-minor lazy equivalence.
  Direct-source detection preserves calculation-result copy before the fixed four-
  field cleaner input, stable source order, and the first non-`task_output:` lazy
  match. Inputs remain unmodified and the existing access/exception order is
  unchanged.
- Graph retains aggregate task-ledger replacement gates and conflict-before-
  preservation disposition, projection sentence scoring, arithmetic-surface
  synchronization, and the status/material/direct-source/family/conflict/sign-rank
  chain inside full nested promotion, plus all state, evidence, provenance,
  artifact/ledger, and final orchestration.
- Production source is `+52/-48`, net 4: the graph changes from 18,328 to 18,287
  lines (`+7/-48`, net -41) and the aggregate owner from 1,106 to 1,151 lines
  (`+45/-0`, net 45). Tests are `+744/-17`, net 727; the whole commit is
  `+796/-65`, net 731.
- Validation passed targeted 5/5 tests, affected 633/633 tests, the 217-literal
  runtime audit, full discovery over 1,527/1,527 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is behavior-preserving aggregate-subtask numeric-conflict and direct-source-
reference predicate ownership plus deletion of the 41 old graph definition lines,
not ledger replacement, sentence selection, arithmetic-surface synchronization,
nested promotion or ranking, source selection or provenance policy, behavior or
performance improvement, total-code or broad executed-path reduction, broader
private-mesh cleanup, end-to-end aggregate ownership, or complete Phase 3.

### Numeric-answer coverage and outside-reference comparison ownership

- `e15445dc45f39eec2fe54c7ab2ec5400e100481c` moves graph
  `_answer_covers_numeric_answer` and
  `_answer_has_numeric_material_outside_reference` into plain public
  `financial_numeric_surface.py` functions. All ten coverage calls and both
  outside-reference calls remain at their exact graph-module positions. The old
  private definitions and self references are deleted without a wrapper, carrier,
  reason, flag, callback, config input, compatibility alias, or trace field.
- Both predicates preserve answer-first then second-input truthiness, string,
  normalization, and extraction. Coverage keeps numeric-list-before-answer-list
  gates and numeric-major/answer-minor lazy `all(any(...))`; outside-reference
  comparison keeps answer-list-before-reference-list gates and answer-major/
  reference-minor lazy `any(not any(...))`. Inputs remain unmodified and the
  existing access/exception order is unchanged.
- Graph retains every prepared answer/reference target, all public and structured
  projection, task-answer preservation, scoring, arithmetic synchronization,
  recovered-ratio, stale-repair, and initial-state gates and polarity, plus
  evidence/text numeric support, state/evidence, artifact/ledger, and final
  orchestration.
- Production source is `+50/-48`, net 2: `financial_graph.py` remains 1,200 lines
  (`+3/-3`), the calculation graph changes from 18,287 to 18,253 lines
  (`+11/-45`, net -34), and the numeric-surface owner from 539 to 575 lines
  (`+36/-0`, net 36). Tests are `+535/-18`, net 517; the whole commit is
  `+585/-66`, net 519.
- Validation passed targeted 6/6 tests, affected 644/644 tests, the 217-literal
  runtime audit, full discovery over 1,531/1,531 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is behavior-preserving generic numeric-answer coverage and outside-reference
comparison ownership plus deletion of the 34 old graph definition lines, not
public projection, preservation, scoring, arithmetic synchronization, stale or
initial-state policy, evidence support, behavior or performance improvement,
total-code or broad executed-path reduction, broader private-mesh cleanup,
end-to-end calculation ownership, or complete Phase 3.

### Prepared calculation-operand slot-overlay ownership

- `db3e58e69e778d32b8be28fe2c265f27acea8f48` moves graph
  `_updated_operands_from_slots` into the plain public
  `financial_runtime_trace.overlay_calculation_operands_from_slots(...)` function.
  The two graph calls remain in place. The old private definition and self
  references are deleted without a wrapper, carrier, reason, flag, callback,
  config input, compatibility alias, or trace field.
- The owner preserves eager calculation-operand list materialization, stable shallow
  row copies, matched-role before lazy role fallback, optional lookup-key-only
  normalization, per-row slot lookup, falsy-slot no-op, and the fixed seven-field
  overwrite order. Fresh list/top-level rows, nested and adopted slot-value aliases,
  input immutability, and uncaught exception order remain unchanged.
- Graph retains collapsed-ratio evidence, eligibility, formula and prepared role-map
  construction, its default-mode owner call and unconditional result adoption before
  calculation-result assignment. It also retains the single-period evidence and
  realignment gates, four-alias role map, normalized-mode call and truthy-only
  adoption, plus all slot/result repair, state, artifact, and final orchestration.
- Production source is `+32/-31`, net 1: the calculation graph changes from 18,253
  to 18,225 lines (`+3/-31`, net -28) and the runtime-trace owner from 1,065 to
  1,094 lines (`+29/-0`, net 29). Tests are `+412/-0`, net 412; the whole commit is
  `+444/-31`, net 413.
- Validation passed targeted 4/4 tests, affected 582/582 tests, the 217-literal
  runtime audit, full discovery over 1,535/1,535 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is behavior-preserving prepared role-slot-to-calculation-operand overlay
ownership plus deletion of the 28 old graph definition lines, not collapsed-ratio
or single-period repair ownership, evidence selection, ranking, formula/query
policy, realignment, call-placement/adoption policy, slot/result repair, behavior
or performance improvement, total-code or broad executed-path reduction, broader
private-mesh cleanup, end-to-end calculation ownership, or complete Phase 3.

### Evidence-local unit and period coercion ownership

- `c355568edf9644e238b569ae0a376a28a0c6d8bc` moves the coherent six-definition
  evidence-local unit/period cluster to `financial_operand_resolution.py`. Public
  `coerce_operand_unit_from_evidence(...)` and
  `coerce_operand_period_from_evidence_surface(...)` replace the graph methods;
  the boundary, core-surface, core-containment, and unit-inference helpers remain
  owner-private. Old graph definitions and self references are zero.
- Unit coercion retains metadata/current/surface precedence, parenthetical-before-
  inline inference, source-context/core asymmetry, boundary and unit/render-policy
  order, repeated access, input immutability, and uncaught exceptions. Period
  coercion retains stable year dedupe, exact no-change identity, conflicting or
  inferred-year shallow copies, nested aliases, access order, and uncaught
  exceptions.
- `financial_lookup_recovery.normalize_lookup_slot_unit(...)` imports the public
  unit owner directly and drops only the injected coercion callback parameter. Its
  direct unit-hint owner-zero branch and both owner-call branches remain in place.
  The graph-local normalize closure remains; graph evidence, own-evidence alignment,
  and the row coordinator call the public owners at their former positions.
- Graph retains raw value/unit and evidence preparation, header/family gates,
  result/slot/evidence selection, own-evidence normalization/copy/adoption, row-
  coordinator dependency/structured-provenance guards, metadata overlay, direct
  structured-value, magnitude and precision work, lookup result construction, and
  all state/evidence/artifact/final orchestration.
- Production source is `+233/-230`, net 3: the calculation graph changes from
  18,225 to 18,003 lines (`+5/-227`, net -222), graph evidence from 4,578 to
  4,581 (`+5/-2`, net 3), lookup recovery remains 609 (`+1/-1`, net 0), and the
  operand owner changes from 2,831 to 3,053 (`+222/-0`, net 222). Tests are
  `+993/-10`, net 983; the whole commit is `+1,226/-240`, net 986.
- Validation passed targeted 6/6 tests, affected 860/860 tests, the 217-literal
  runtime audit, full discovery over 1,540/1,540 tests, and `git diff --check`.
  Benchmark refresh was NOT RUN.

This is only state-free evidence-local unit inference/coercion and period coercion
ownership, one injected-callback removal, and deletion of the 215 old graph
definition lines—not a unit/render policy or behavior improvement, graph row/
evidence/lookup orchestration ownership, structured-value/magnitude/precision
ownership, performance, total-code or broad executed-path reduction, broader
private-mesh cleanup, end-to-end calculation ownership, or complete Phase 3.

### Three-seam Phase 3 owner milestone

- `c392ce6` moves ontology-driven ratio denominator sign-policy merge and
  magnitude transformation to public
  `financial_operand_resolution.apply_operation_sign_policy(...)`, with its
  binding-policy helper owner-private. The graph retains prepared operand order,
  growth recovery/conflict gates, equality-gated map propagation, execution,
  state, artifact, and final orchestration.
- `a05cc07` moves `numeric_surface_conflicts_with_reference(...)`,
  `evidence_supports_numeric_candidates(...)`, and
  `text_supports_numeric_candidates(...)` to `financial_numeric_surface.py`.
  Graph callers retain answer/evidence preparation, applicability, projection,
  and final filtering policy.
- `1897fd1` moves aggregate projection row, answer-sentence, and rendered-value
  selection to `financial_aggregate_projection.py` through
  `select_aggregate_projection_row_for_task(...)`,
  `select_aggregate_projection_answer_sentence(...)`, and
  `aggregate_projection_rendered_value(...)`. The ledger path consumes two row
  selections and one answer-sentence selection; arithmetic-surface synchronization
  consumes two answer-sentence selections and one rendered-value selection.
  Nested promotion, rebuild, mutable state/evidence, ledger, and callback ownership
  stay in the graph.
- Across the three seams, eight graph methods spanning 191 old definition lines
  were deleted. Seven public APIs replace 14 graph calls; retired private
  references are zero, while owner-private `_binding_policy_for_operand_row`
  intentionally remains. Relevant production source changed `+226/-215`, net
  `+11`: the graph changed `+21/-214`, from 18,003 to 17,810 physical lines,
  while the three owner files were net `+204` and reached operand 3,105, numeric
  619, and aggregate 1,259 lines. Tests changed `+1,542/-51`, including ten added
  and one removed test method; the whole milestone changed `+1,768/-266`.
- Final validation passed focused 4/4, affected `tests.test_subtask_loop`
  252/252, the 217-literal runtime
  audit, full discovery over 1,549/1,549 tests, and `git diff --check`.
  Benchmark refresh was **NOT RUN**.

This milestone closes three bounded state-free owner seams. It does not close
the four Phase 3 debt groups, establish an end-to-end calculation or ledger
owner, change numeric or ranking behavior, or prove total-code, executed-path,
performance, or benchmark improvement. The accompanying current-state document
compaction removes repeated owner diaries while keeping this history and the
runtime contract as detailed authorities.

### Aggregate coherence-rank foundation milestone

- `477abff` moves canonical `answer_slot_has_material(...)` to
  `financial_answer_slots.py` and migrates graph and planning consumers without
  changing their gates or callback placement. Source is `+66/-74`, tests are
  `+235/-6`, and the whole commit is `+301/-80`.
- `68d6546` moves aggregate primary-slot selection, source-slot map construction,
  and operand source-task resolution to `financial_aggregate_projection.py`
  through `aggregate_row_primary_answer_slot(...)`,
  `aggregate_source_slot_by_task_id(...)`, and
  `aggregate_source_task_ids_for_operand(...)`. Source is `+70/-62`, tests are
  `+807/-1`, and the whole commit is `+877/-63`.
- `194e397` moves candidate collection owner-private and publishes
  `aggregate_result_dependency_coherence_ranks(...)` plus
  `aggregate_dependency_slot_coherence_rank_for_operands(...)`. Source is
  `+102/-96`, tests are `+1,080/-36`, and the whole commit is `+1,182/-132`.
- Across `f0809f1..194e397`, eight old definitions spanning 152 lines were
  deleted from their former locations: 143 graph lines and nine planning lines.
  Six public APIs replace the selected private boundaries; one owner-private
  candidate helper intentionally remains, while retired moved references and
  graph candidate references are zero. The range-level source diff is
  `+233/-227`, net `+6`; tests are `+2,102/-23`, net `+2,079`; the whole range is
  `+2,335/-250`, net `+2,085`. Twelve test methods were added and none removed;
  full discovery therefore moved from 1,549 to 1,561 tests.
- Final validation passed focused 4/4, 655/655 across
  `tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
  `tests.test_financial_agent_run_projection`, and `tests.test_operation_contracts`,
  the 217-literal runtime audit, full discovery over 1,561/1,561 tests, and
  `git diff --check`. Benchmark refresh was **NOT RUN**.

This milestone establishes shared material, aggregate source-preparation, and
dependency-coherence foundations only. Full result/nested rank, material-gap,
promotion, dedupe, rebuild, state/evidence, artifact/ledger, and callback
orchestration remain graph-owned; row-material policy and nested traversal remain
planning-owned. It proves no ranking change, accuracy or performance improvement,
total-code or executed-path reduction, benchmark improvement, or Phase 3
completion.

### Aggregate material/rank/dedupe owner milestone

- `2f0f29e` publishes `answer_slot_period_hint(...)` and
  `period_match_key(...)` from `financial_answer_slots.py` and preserves 21
  semantic placements. Thirteen old graph definition-span lines were removed.
  Source is `+46/-35`, tests are `+474/-0`, docs are `+1/-1`, and the whole
  commit is `+521/-36`.
- `1efccb2` publishes `growth_row_has_conflicting_periods(...)`,
  `material_gap_feedback_for_subtask_result(...)`, and
  `subtask_row_has_material(...)` from `financial_answer_projection.py`.
  One hundred fifty old graph/planning definition-span lines were removed; 32
  external placements remain and recursion plus growth-conflict composition are
  owner-local. Source is `+207/-186`, tests are `+1,475/-50`, docs are `+1/-1`,
  and the whole commit is `+1,683/-237`.
- `ec266c6` keeps `_aggregate_result_rank(...)` owner-private and publishes
  `nested_aggregate_result_rank(...)` plus
  `dedupe_aggregate_subtask_results(...)` from
  `financial_aggregate_projection.py`. Ninety-four old graph definition-span
  lines were removed; ten graph placements and one owner-private call remain.
  Source is `+113/-107`, tests are `+1,050/-55`, and the whole commit is
  `+1,163/-162`.
- Across `302cf50..ec266c6`, 257 selected old definition-span lines were removed
  and replaced by seven public APIs plus one owner-private rank helper. The
  range-level source diff is `+358/-320`, net `+38`, with changed source modules
  moving from 22,222 to 22,260 physical lines. Tests are `+2,943/-49`, net
  `+2,894`, moving from 34,757 to 37,651 physical lines; docs are `+2/-2`.
  The whole changed-file range is `+3,303/-371`, net `+2,932`, moving from
  57,428 to 60,360 physical lines. Test methods moved from 1,561 to 1,573:
  three, five, and four methods were added by the sequential seams.
- Final validation passed focused 4/4, 664/664 across
  `tests.test_financial_aggregate_rank_dedupe`,
  `tests.test_financial_answer_projection`,
  `tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
  `tests.test_financial_agent_run_projection`, and `tests.test_operation_contracts`,
  the 217-literal runtime audit, full discovery over 1,573/1,573 tests, and
  `git diff --check`. Benchmark refresh was **NOT RUN**; no remote CI run is
  claimed or verified for this local branch.

This milestone closes only the selected period/material/rank/dedupe ownership
boundary. Promotion, sync/rebuild, nested traversal, mutable state/evidence,
artifact/ledger, callbacks, and final orchestration remain outside it. The range
proves no behavior or ranking change, accuracy or performance improvement,
total-code or executed-path reduction, benchmark improvement, or Phase 3
completion.

### Ratio presentation/readiness owner milestone

- `157e9e4` publishes `infer_concept_ratio_result_unit(...)`,
  `ratio_query_requests_absolute_magnitude(...)`, and
  `ratio_result_projection(...)` from calculation rendering. Forty-three old
  definition-span lines were removed; two calls became owner-local and eight
  remain external. Source is `+61/-62`, test code `+927/-13`, the runtime audit
  document `+1/-1`, and the whole commit `+989/-76`.
- `be2af81` publishes `ratio_component_consolidation_scope(...)`,
  `ratio_components_collapse_to_same_slot(...)`, and
  `ratio_components_are_complete(...)` from answer slots. Seventy-one old graph
  definition-span lines were removed; one call became owner-local and 15 remain
  external. Source is `+91/-89`, test code `+1,167/-78`, and the whole commit is
  `+1,258/-167`.
- `7e01f8c` publishes `ratio_components_have_suspicious_scale(...)` and
  `ratio_result_has_suspicious_krw_scale(...)` from numeric surface. Fifty-one old
  graph definition-span lines were removed and three graph calls remain. Source
  is `+56/-56`, test code `+853/-0`, and the runtime-domain baseline is `+3/-3`;
  the whole commit is `+912/-59`. The baseline change only relocates the already
  reviewed `원` record's path, fingerprint, and first line; text, category, and
  count are unchanged.
- Across `f82a2d7..7e01f8c`, 165 selected old definition-span lines were removed
  and replaced by eight public APIs. Of 29 semantic calls, three became
  owner-local and 26 remain external: 24 graph, one graph-helper, and one planning
  placement. Retired exact old identifiers are zero. Source is `+208/-207`, net
  `+1`; test code is `+2,947/-91`, net `+2,856`; the audit fixture is `+3/-3` and
  runtime audit documentation `+1/-1`. The whole range is `+3,159/-302`, net
  `+2,857`. Test methods are `+11/-2`, moving full discovery from 1,573 to 1,582.
- Final validation passed focused 3/3 and 697/697 across
  `tests.test_financial_ratio_scale`, `tests.test_financial_numeric_provenance`,
  `tests.test_financial_calculation_execution`,
  `tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
  `tests.test_financial_agent_run_projection`, and `tests.test_operation_contracts`;
  the 217-literal runtime audit; full discovery over 1,582/1,582 tests; and
  `git diff --check`. Benchmark refresh was **NOT RUN**; no remote CI run is
  claimed or observed for this local branch.

This milestone closes only selected ratio presentation, component readiness, and
scale-policy ownership. Query/evidence preparation, dependency lookup, compact
answer orchestration, sibling-table alignment, promotion, sync/rebuild, mutable
state/evidence, artifact/ledger, callbacks, and final sequencing remain outside
it. The range proves no behavior, accuracy, ranking, performance, total-code or
executed-path reduction, benchmark improvement, or Phase 3 completion.

### Narrative-answer validation owner milestone

- `d6723b8` publishes `query_requests_explanatory_context(...)` and
  `sentence_has_growth_explanatory_signal(...)` from answer projection. Thirty-one
  old graph definition-span lines were removed and all 15 graph calls remain.
  Source is `+50/-49`, tests are `+563/-4`, and the whole commit is `+613/-53`.
- `04a8b3c` publishes `answer_looks_truncated(...)` and
  `answer_covers_narrative_context(...)` from answer projection. Thirty-two old
  graph definition-span lines were removed and all ten graph calls remain. Source
  is `+49/-44`, tests are `+714/-7`, and the runtime-domain baseline is `+3/-3`;
  the whole commit is `+766/-54`. The baseline change relocates only the existing
  terminal-regex record's path, fingerprint, and first line; its text, category,
  and count are unchanged.
- `fd82367` publishes `growth_uses_source_stated_result(...)`,
  `growth_sentence_has_untraced_material_numeric(...)`, and
  `growth_answer_has_untraced_numeric_sentence(...)` from answer projection.
  Ninety-eight old graph definition-span lines were removed and all 11 graph
  calls remain. Source is `+123/-114`, tests are `+727/-0`, and the whole commit
  is `+850/-114`.
- Across `78f59fe..fd82367`, 161 selected old graph definition-span lines were
  removed and replaced by seven public APIs at 36 graph calls. Retired exact old
  identifiers are zero. The range-level source diff is `+221/-206`, net `+15`:
  the graph moved from 17,258 to 17,097 physical lines and answer projection from
  315 to 491. Tests are `+1,997/-4`, net `+1,993`; the baseline is `+3/-3` and
  the whole changed-file range is `+2,221/-213`, net `+2,008`. Twelve test methods
  were added, moving full discovery from 1,582 to 1,594 tests.
- Final validation passed focused 4/4, migrated narrative classes 12/12, and
  690/690 across `tests.test_financial_answer_projection`,
  `tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
  `tests.test_financial_agent_run_projection`,
  `tests.test_lookup_recovery_policy`,
  `tests.test_financial_aggregate_rank_dedupe`, and
  `tests.test_operation_contracts`; the 217-literal runtime audit; full discovery
  over 1,594/1,594 tests; and `git diff --check`. Benchmark refresh was **NOT
  RUN**; no remote CI run is claimed or verified for this local branch.

This milestone closes only the selected narrative intent/signal, answer-surface,
and growth numeric-trace validation ownership. Query/evidence preparation, answer
composition/refresh, LLM work, promotion, sync/rebuild, mutable state/evidence,
artifact/ledger, callbacks, and final orchestration remain graph-owned. The range
proves no behavior, accuracy, ranking, performance, total-code or executed-path
reduction, benchmark improvement, or Phase 3 completion.

### Operand-preparation owner milestone

- `d13c8cd` publishes
  `repair_krw_normalized_values_from_raw_units(...)` from operand resolution.
  Forty-seven old graph definition-span lines were removed and the sole graph
  call remains. Source is `+50/-49`, tests are `+575/-2`, and the whole commit is
  `+625/-51`.
- `ae8acba` publishes
  `align_growth_operand_units_when_raw_scale_matches(...)` from operand
  resolution. Ninety old graph definition-span lines were removed and the sole
  graph call remains. Source is `+94/-92`, tests are `+664/-3`, and the whole
  commit is `+758/-95`.
- `d8bb90d` publishes `growth_operand_periods_conflict(...)` from operand
  resolution. Twenty-four old graph definition-span lines were removed and the
  sole graph call remains. Source is `+29/-26`, tests are `+511/-6`, and the whole
  commit is `+540/-32`.
- Across `abc4552..d8bb90d`, 161 selected old graph definition-span lines were
  replaced by three public APIs at three retained graph calls; retired exact old
  identifiers are zero. The range-level source diff is `+173/-167`, net `+6`:
  the graph moved from 17,097 to 16,936 physical lines and operand resolution from
  3,105 to 3,272. Tests are `+1,747/-8`, net `+1,739`, and the whole changed-file
  range is `+1,920/-175`, net `+1,745`. Twelve test methods were added, moving
  full discovery from 1,594 to 1,606 tests.
- Final validation passed focused 4/4 and 762/762 across
  `tests.test_financial_operand_resolution`,
  `tests.test_financial_calculation_execution`,
  `tests.test_financial_answer_slots`, `tests.test_aggregate_subtask_projection`,
  `tests.test_subtask_loop`, `tests.test_financial_agent_run_projection`, and
  `tests.test_operation_contracts`; the 217-literal runtime audit; full discovery
  over 1,606/1,606 tests; and `git diff --check`. Benchmark refresh was **NOT
  RUN**; no remote CI run is claimed or verified for this local branch.

This milestone closes only prepared KRW raw-unit repair, growth raw-scale
alignment, and growth-period conflict ownership. Table/evidence preparation,
operand-map and plan access, donor propagation, duplicate recovery, sign/execution,
mutable state, artifact/ledger, callbacks, and final orchestration remain graph-
owned. The range proves no behavior, accuracy, ranking, performance, total-code
or executed-path reduction, benchmark improvement, or Phase 3 completion.

### Operand unit/table-repair owner milestone

- `25318f1` moves the existing public
  `dependency_task_output_has_consistent_krw_unit(...)` implementation from
  dependency projection to operand resolution. Twenty old dependency-owner
  definition-span lines were removed; the graph's row-coercion call remains and
  the later table-repair call becomes owner-local. Source is `+23/-23`, tests are
  `+498/-10`, and the whole commit is `+521/-33`.
- `21f3a83` publishes
  `repair_krw_operand_units_from_table_metadata(...)` from operand resolution.
  One hundred sixty-six old graph definition-span lines were removed and the sole
  graph call remains after evidence-row coercion. Source is `+169/-168`, tests are
  `+934/-31`, and the whole commit is `+1,103/-199`.
- Across `941e719..21f3a83`, 186 selected old definition-span lines were replaced
  by two public APIs. Final placement is two external graph calls and one owner-
  local predicate call; old dependency-owner and graph-private references are zero. The range-
  level source diff is `+192/-191`, net `+1`: the graph moved from 16,936 to
  16,770 physical lines, dependency projection from 3,257 to 3,235, and operand
  resolution from 3,272 to 3,461. Tests are `+1,416/-25`, net `+1,391`, and the
  whole changed-file range is `+1,608/-216`, net `+1,392`. Eight test methods were
  added, moving full discovery from 1,606 to 1,614 tests.
- Final validation passed focused 4/4 and 813/813 across
  `tests.test_financial_dependency_projection`,
  `tests.test_financial_operand_resolution`,
  `tests.test_financial_calculation_execution`,
  `tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
  `tests.test_financial_agent_run_projection`, and
  `tests.test_operation_contracts`; the 217-literal runtime audit; full discovery
  over 1,614/1,614 tests; and `git diff --check`. Benchmark refresh was **NOT
  RUN**; no remote CI run is claimed or verified for this local branch.

This milestone closes only dependency-task normalized-KRW consistency and table-
metadata KRW repair ownership. Evidence/query/row preparation, caller carriers,
adoption/failure projection, plan/execution, mutable state, artifact/ledger,
callbacks, and final orchestration remain graph-owned. The range proves no
behavior, accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, or Phase 3 completion.

### Aggregate answer-surface owner milestone

- `515ccab` publishes `row_is_narrative_summary(...)` and
  `safe_partial_answer_for_numeric_gap(...)` from aggregate projection. Thirty
  old graph definition-span lines were removed. All 20 row-predicate and four
  safe-partial calls remain represented; the safe-partial predicate call is now
  owner-local. Source is `+58/-55`, tests are `+550/-5`, and the whole commit is
  `+608/-60`.
- `18e75a3` publishes `compose_lookup_list_numeric_answer(...)` and
  `append_uncovered_lookup_numeric_items(...)`, and co-locates owner-private
  `_lookup_numeric_item_answer(...)`. One hundred fifty-three old graph
  definition-span lines were removed. The compose and append calls remain in the
  graph, while both private-lookup calls are owner-local. Source is `+162/-159`,
  tests are `+1,153/-69`, and the whole commit is `+1,315/-228`.
- Across `c4fd42a..18e75a3`, 183 selected old graph definition-span lines became
  four public APIs plus one owner-private helper. The 28 calls finish at 23
  external graph calls and five owner-local calls; retired graph-private
  references are zero. The range-level source diff is `+218/-212`, net `+6`:
  the graph moved from 16,770 to 16,585 physical lines and aggregate projection
  from 1,511 to 1,702. Tests are `+1,655/-26`, net `+1,629`; the whole changed-
  file range is `+1,873/-238`. Nine test methods were added, moving full discovery
  from 1,614 to 1,623 tests.
- Final clean-HEAD validation passed focused 5/5 and 699/699 across
  `tests.test_financial_aggregate_rank_dedupe`,
  `tests.test_financial_answer_projection`,
  `tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
  `tests.test_financial_agent_run_projection`,
  `tests.test_lookup_recovery_policy`, and `tests.test_operation_contracts`;
  `tests.test_import_side_effects` 19/19; the 217-literal runtime audit; full
  discovery over 1,623/1,623 tests; and `git diff --check`. Benchmark refresh was
  **NOT RUN**; no remote CI run is claimed or verified for this local branch.

This milestone closes only the selected aggregate narrative-row, numeric-gap,
lookup-list composition, and uncovered-lookup preservation ownership. Query and
evidence preparation, answer composition/feedback, mutable state/evidence,
artifact/ledger work, promotion, sync/rebuild, callbacks, and final sequencing
remain graph-owned. The range proves no behavior, accuracy, ranking, performance,
total-code or executed-path reduction, benchmark improvement, or Phase 3
completion.

### Narrative text-surface owner milestone

- `c1ec720` publishes `narrative_context_terms(...)`,
  `narrative_focus_variants(...)`, and
  `parenthetical_focus_variants(...)` from `financial_text_surface.py`.
  Sixty-three old graph definition-span lines were removed. The 23 selected calls
  finish at 21 external graph placements and two owner-local term calls. Source
  is `+93/-87`, test code is `+905/-4`, the runtime-domain baseline is `+3/-3`,
  and the whole commit is `+1,001/-94`. The baseline change relocates exactly the
  existing reviewed context-token regex record; text, category, count, and the
  217-record reviewed total are unchanged.
- `e8482bd` publishes `narrative_context_sentence_from_evidence(...)` and
  `include_narrative_context_if_needed(...)` from the same owner. Eighty-four old
  graph definition-span lines were removed. Both public calls remain external,
  while their two term calls become owner-local. Source is `+92/-89`, test code
  is `+1,242/-3`, and the whole commit is `+1,334/-92`.
- Across `a2bb6cc..e8482bd`, 147 selected old graph definition-span lines became
  five public APIs. The 25 calls finish at 21 external graph calls and four
  owner-local calls; retired exact graph-private references are zero. Source is
  `+183/-174`, net `+9`: the graph moved from 16,585 to 16,438 physical lines
  and the text owner from 108 to 264. Test code is `+2,144/-4`, net `+2,140`;
  the baseline is `+3/-3`; the whole changed-file range is `+2,330/-181`, net
  `+2,149`. Ten test methods were added, moving full discovery from 1,623 to
  1,633 tests.
- Final clean-HEAD validation passed focused 5/5; 714/714 across
  `tests.test_financial_text_surface`,
  `tests.test_financial_aggregate_rank_dedupe`,
  `tests.test_financial_answer_projection`,
  `tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
  `tests.test_financial_agent_run_projection`,
  `tests.test_lookup_recovery_policy`, and `tests.test_operation_contracts`;
  the same set plus `tests.test_import_side_effects` at 733/733, including the
  import module's independent 19/19; the 217-literal runtime audit; full discovery
  over 1,633/1,633 tests; and `git diff --check`. Benchmark refresh was **NOT
  RUN**; no remote CI run is claimed or verified for this local branch.

This milestone closes only the selected narrative term, focus/parenthetical
variant, prepared-evidence sentence-selection, and context-inclusion ownership.
Retrieval and evidence preparation, evidence ids/windows/provenance, answer
composition/feedback, mutable state/evidence, artifact/ledger work, promotion,
sync/rebuild, callbacks, and final sequencing remain graph-owned. The range
proves no behavior, accuracy, ranking, performance, total-code or executed-path
reduction, benchmark improvement, schedule, or Phase 3 completion.

### Prepared narrative presentation owner milestone

- `55f7ce3` publishes `policy_required_realized_snippet_from_doc(...)` and
  `preserve_retrieved_narrative_source_surface(...)` from
  `financial_text_surface.py`. The former 69- and 72-line graph definitions are
  68- and 71-line public owner functions. Both graph calls remain external, while
  the preservation body's context-term call becomes owner-local. Retired exact
  graph-private definitions and references are zero.
- Across `7aa3e23..55f7ce3`, exactly four files changed:
  `src/agent/financial_graph_calculation.py`,
  `src/agent/financial_text_surface.py`,
  `tests/test_financial_text_surface.py`, and `tests/test_subtask_loop.py`.
  Source is `+152/-146`, net `+6`: the graph is `+4/-145` and moves from 16,438
  to 16,297 physical lines; the text owner is `+148/-1` and moves from 264 to
  411. Tests are `+1,304/-11`, net `+1,293`: the text test is `+1,285/-3` and
  moves from 2,169 to 3,451 physical lines; the subtask test is `+19/-8` and
  moves from 23,425 to 23,436. The whole range is `+1,456/-157`, net `+1,299`.
  Five AST-counted unittest methods were added, moving both the method inventory
  and full discovery from 1,633 to 1,638.
- Cumulatively, 288 selected old graph definition-span lines form seven public
  text APIs. Their 27 calls finish at 22 graph-external and five owner-local:
  context terms 13/5, focus variants 2/0, parenthetical variants 3/0, evidence
  sentence selection 1/0, context inclusion 1/0, document snippet 1/0, and
  retrieved-source preservation 1/0. The frozen source-only diff SHA-256 is
  `288189968a74337f54912578d1446f00cf186c64a5a6c6428058100688ee54e4`.
- Final clean-HEAD validation passed the new focused 5/5 and migrated 4/4
  independently, for 9/9 combined; `tests.test_financial_text_surface` 20/20;
  the eight-module semantic set 719/719; `tests.test_import_side_effects` 19/19;
  the nine-module union 738/738; the 217-literal runtime audit; full discovery
  1,638/1,638; and `git diff --check`. Benchmark refresh was **NOT RUN**, and no
  remote CI run is claimed or verified for this local branch.

This milestone closes only prepared-document snippet projection and prepared-
evidence retrieved-source answer-surface preservation. Retrieval/evidence
construction, mutable state/evidence, artifact/ledger work, promotion,
sync/rebuild, callbacks, and final sequencing remain graph-owned. The range
proves no behavior, accuracy, ranking, performance, total-code or executed-path
reduction, benchmark improvement, schedule, or Phase 3 completion.

At this handoff, the sole selected follow-on is the 131-line dependency-source
preparation boundary in graph lines 7339-7473: four public aggregate-projection
functions plus one owner-private text scorer, with nine calls projected as seven
graph-external and two owner-local. The upstream bound-callback function and
downstream compact-ratio state/trace carrier remain hard stops. Exact APIs,
dependencies, characterization gates, and rejected expansions are maintained
only in [Project Status Next Work](../overview/project_status.md#next-work).

### Aggregate dependency-source preparation owner milestone

- `df3b63b` moves five former graph helpers into
  `financial_aggregate_projection.py`: public
  `ratio_rebuild_component_seeds(...)`,
  `dependency_source_slot_match_score(...)`,
  `best_dependency_source_for_seed(...)`, and
  `component_slot_from_dependency_source(...)`, plus owner-private
  `_dependency_source_text_match_score(...)`. The former definition spans were
  34 + 21 + 16 + 36 + 24 = 131 lines; the owner spans are
  33 + 21 + 15 + 35 + 23 = 127. Retired graph-private definitions and references
  are zero.
- Across `8dc6054..df3b63b`, exactly five source/test files changed. Source is
  `+157/-147`, net `+10`: the graph is `+12/-145` and moves from 16,297 to
  16,164 physical lines; aggregate projection is `+145/-2` and moves from 1,702
  to 1,845. Tests are `+1,299/-27`, net `+1,272`: aggregate rank/dedupe is
  `+1,253/-0`, aggregate subtask projection is `+16/-10`, and text surface is
  `+30/-17`. The whole range is `+1,456/-174`, net `+1,282`.
- Nine selected calls finish at seven graph-external and two owner-local: seed
  collection 1/0, text score 0/1, slot score 1/1, best-source selection 3/0,
  and component projection 2/0. The frozen source diff SHA-256 is
  `0ed48e13a232281d0f05e70f83b5f8b617e739dc3854265316a4910bf82495e3`.
  The bound-callback source map and compact-ratio state/trace/result caller remain
  graph-owned.
- Six AST-counted unittest methods were added, moving the method inventory and
  full discovery from 1,638 to 1,644. Final validation passed new focused 6/6,
  combined owner/migrated surface 13/13, the eight-module semantic set 725/725,
  import-side-effects 19/19, the nine-module union 744/744, runtime audit 217,
  full discovery 1,644/1,644, pycompile/fresh-import binding checks, and
  `git diff --check`. Benchmark refresh was **NOT RUN**, and no remote CI run is
  claimed or verified for this local branch.

This milestone closes only the selected aggregate dependency-source seed,
scoring, selection, and component-preparation ownership. Source-slot mapping
with dynamic callback, compact-ratio state/trace/result projection, broader
evidence work, mutable state/evidence, artifact/ledger work, promotion,
sync/rebuild, and final sequencing remain graph-owned. The range proves no
behavior, accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, or Phase 3 completion.

At this handoff, the sole selected follow-on is the 95-line narrative row-focus
pair in graph lines 8054-8149. Two public aggregate-projection functions are
projected at 26 and 67 owner lines; all three calls remain graph-external.
Dynamic narrative-driver discovery and growth composition/validation remain hard
stops. Exact APIs, dependencies, five-method characterization gate, and rejected
expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Aggregate narrative row-focus owner milestone

- `fcf4c55` moves two former graph helpers into
  `financial_aggregate_projection.py`: public
  `narrative_row_focus_sentence(...)` and
  `narrative_row_focus_context(...)`. The former definition spans were
  27 + 68 = 95 lines; the owner spans are 26 + 67 = 93. All three selected calls
  remain graph-external, and retired graph-private definitions are zero.
- Exactly five source/test files changed. Source is `+105/-101`, net `+4`: the
  graph is `+5/-100` and moves from 16,164 to 16,069 physical lines; aggregate
  projection is `+100/-1` and moves from 1,845 to 1,944. Tests are `+721/-3`, net
  `+718`: aggregate rank/dedupe is `+716/-0`, answer projection is `+3/-1`, and
  text surface is `+2/-2`. The whole commit is `+826/-104`, net `+722`.
- The frozen source-only diff SHA-256 is
  `4ce346bc63cd45a6f25efcb758ac491df5bc58a704e8e14c5da2eed17ad44c62`.
  Literal body parity and full composer/intent caller parity passed after only
  self removal and selected call rebinding. The import DAG remains acyclic;
  public import identity is exact; old mixin attributes are absent.
- Five AST-counted unittest methods were added, moving the method inventory and
  full discovery from 1,644 to 1,649. Final validation passed focused 5/5,
  aggregate-owner module 15/15, the three migrated existing methods, the eight-
  module semantic set 730/730, import-side-effects 19/19, the nine-module union
  749/749, runtime audit 217, full discovery 1,649/1,649, pycompile/fresh-import
  binding checks, and `git diff --check`. Benchmark refresh was **NOT RUN**, and
  no remote CI run is claimed or verified for this local branch.

This milestone closes only state-free narrative row-focus sentence/context
selection. Dynamic narrative-driver discovery, growth answer composition and
validation, broader evidence work, mutable state/evidence, artifact/ledger work,
promotion, sync/rebuild, and final sequencing remain graph-owned. The commit
proves no behavior, accuracy, ranking, performance, total-code or executed-path
reduction, benchmark improvement, schedule, or Phase 3 completion.

At this handoff, the sole selected follow-on is the 107-line growth display/
material cluster in graph lines 2945-3054. Three public aggregate-projection
functions plus one owner-private source-task display helper are projected at
23 + 8 + 17 + 55 = 103 owner lines; 18 calls finish as 15 graph-external and
three owner-local. Required-value construction, complete/narrative composition,
duplicate recovery, state/evidence, and artifact/ledger work remain hard stops.
Exact APIs, dependencies, seven-method characterization gate, and rejected
expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Aggregate growth display/material owner milestone

- `d4d19fc` moves four former graph helpers into
  `financial_aggregate_projection.py`: owner-private
  `_slot_display_from_source_task(...)` and public
  `growth_slot_display_value(...)`, `growth_slots_share_material(...)`, and
  `recover_growth_prior_material_from_evidence(...)`. The former definition
  spans were 24 + 9 + 18 + 56 = 107 lines; the owner spans are
  23 + 8 + 17 + 55 = 103. Eighteen selected calls now place 15 in the graph and
  three owner-local, and retired graph-private definitions and test refs are zero.
- Exactly six source/test files changed. Source is `+134/-127`, net `+7`: the
  graph is `+18/-126` and moves from 16,069 to 15,961 physical lines; aggregate
  projection is `+116/-1` and moves from 1,944 to 2,059. Tests are
  `+1,066/-18`, net `+1,048`; the whole commit is `+1,200/-145`, net `+1,055`.
  The four touched test files move from 41,326 to 42,374 physical lines.
- The frozen source-only diff SHA-256 is
  `c25590b321b0cc32e6220d9f33c196c0570b15442cfe840bd34d6242f2ac8d02`.
  Literal body parity passed 4/4 after only self removal and owner-local name
  rebinding. Full caller parity passed for required displays, complete/narrative
  composition, and duplicate recovery. The import DAG remains acyclic; public
  import identity is exact; old mixin attributes are absent.
- Seven AST-counted unittest methods were added, moving the method inventory and
  full discovery from 1,649 to 1,656. Final validation passed focused 7/7,
  aggregate-owner module 22/22, migrated existing methods 4/4, the eight-module
  semantic set 737/737, import-side-effects 19/19, the nine-module union 756/756,
  runtime audit 217, full discovery 1,656/1,656, pycompile/fresh-import binding
  checks, and `git diff --check`. Benchmark refresh was **NOT RUN**, and no remote
  CI run is claimed or verified for this local branch.

This milestone closes only state-free growth display/material projection. Growth
answer construction, duplicate-prior recovery, broader evidence work, mutable
state/evidence, artifact/ledger work, promotion, sync/rebuild, and final
sequencing remain graph-owned. The commit proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, or Phase 3 completion.

At this handoff, the sole selected follow-on is the 81-line aggregate result
support/reuse predicate cluster. Four public aggregate-projection functions are
projected at 39 + 10 + 16 + 12 = 77 owner lines; 12 calls finish as 11 graph-
external and one owner-local. Answer choice, composition, refresh, mutable state/
evidence, and final sequencing remain hard stops. Exact APIs, dependencies, six-
method characterization gate, and rejected expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Aggregate result support/reuse predicate owner milestone

- `6d6c9c3` moves four former graph predicates into
  `financial_aggregate_projection.py`: public
  `aggregate_results_include_dependency_numeric_result(...)`,
  `aggregate_results_include_source_task_slot_realignment(...)`,
  `answer_reuses_narrative_summary_text(...)`, and
  `answer_reuses_numeric_narrative_summary_text(...)`. The former definition
  spans were 40 + 11 + 17 + 13 = 81 lines; the owner spans are
  39 + 10 + 16 + 12 = 77. Twelve selected calls now place 11 in the graph and one
  owner-local, and retired graph-private definitions and test refs are zero.
- Exactly five source/test files changed. Source is `+100/-96`, net `+4`: the
  graph is `+15/-96` and moves from 15,961 to 15,880 physical lines; aggregate
  projection is `+85/-0` and moves from 2,059 to 2,144. Tests are `+906/-6`, net
  `+900`; the whole commit is `+1,006/-102`, net `+904`. The three touched test
  files move from 19,474 to 20,374 physical lines; all five changed files move
  from 37,494 to 38,398.
- The frozen source-only diff SHA-256 is
  `32a2895fe0e196eaff951ba4ef2440ceb3b9596a8e270e7aaac4b296f91ae693`.
  Literal body parity passed 4/4 after only self removal and owner-local name
  rebinding. Full retained-caller parity passed for the five external caller
  methods. The import DAG remains acyclic; public import identity is exact; old
  mixin attributes are absent.
- Six AST-counted unittest methods were added, moving the method inventory and
  full discovery from 1,656 to 1,662. Final validation passed focused 6/6,
  focused plus migrated methods 8/8, aggregate-owner module 28/28, the eight-
  module semantic set 743/743, import-side-effects 19/19, the nine-module union
  762/762, runtime audit 217, full discovery 1,662/1,662, pycompile/fresh-import
  binding checks, and `git diff --check`. Benchmark refresh was **NOT RUN**, and
  no remote CI run is claimed or verified for this local branch.

This milestone closes only state-free result support/reuse predicate ownership.
Answer selection, growth/narrative composition, mutable state/evidence, artifact/
ledger work, promotion, sync/rebuild, and final sequencing remain graph-owned. The
commit proves no behavior, accuracy, ranking, performance, total-code or executed-
path reduction, benchmark improvement, schedule, or Phase 3 completion.

At this handoff, the sole selected follow-on is the 135-line prepared aggregate
material-inspection cluster. Four public functions plus one owner-private helper
are projected at 31 + 32 + 11 + 13 + 43 = 130 owner lines; 17 calls finish as 16
graph-external and one owner-local. Complete/narrative growth composition,
arithmetic surface synchronization, retrieved-ratio artifact/state handling,
mutable state/evidence, and final sequencing remain hard stops. Exact APIs,
cycle-safe dependencies, seven-method characterization gate, and rejected
expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Aggregate prepared material-inspection owner milestone

- `df7afc2` moves five former graph helpers into
  `financial_aggregate_projection.py`: public
  `growth_required_display_values(...)`,
  `has_strong_growth_trace_for_answer_refresh(...)`,
  `aggregate_lookup_primary_slots(...)`, and
  `retrieved_ratio_projection_conflicts_with_existing_complete_result(...)`, plus
  owner-private `_ratio_result_numeric_value(...)`. The former definition spans
  were 32 + 33 + 12 + 44 + 14 = 135 lines; the owner spans are
  31 + 32 + 11 + 43 + 13 = 130. Seventeen selected calls now place 16 in the
  graph and one owner-local, and retired selected graph-private definitions and
  test refs are zero.
- Exactly seven source/test files changed. Source is `+164/-157`, net `+7`: the
  graph is `+20/-157` and moves from 15,880 to 15,743 physical lines; aggregate
  projection is `+144/-0` and moves from 2,144 to 2,288. Tests are
  `+1,039/-44`, net `+995`; the whole commit is `+1,203/-201`, net `+1,002`.
- The committed source-only diff SHA-256 is
  `846da97ce32136e2b05ff221c29c4f09c5a541ed70785df556be195dad81f6fd`.
  Literal body parity passed 5/5 after only self removal and owner-local name
  rebinding. Full retained-caller parity passed 16/16. The import DAG remains
  acyclic; public import identity is exact; old selected mixin attributes are
  absent.
- Seven AST-counted unittest methods were added, moving the method inventory and
  full discovery from 1,662 to 1,669. Final validation passed focused 7/7,
  aggregate-owner module 35/35, the five changed test modules 328/328, the nine-
  module semantic set 754/754, import-side-effects 19/19, the ten-module union
  773/773, runtime audit 217, full discovery 1,669/1,669, pycompile/fresh-import
  binding checks, and `git diff --check`. Benchmark refresh was **NOT RUN**, and
  no remote CI run is claimed or verified for this local branch.

This milestone closes only state-free inspection of prepared growth and ratio
material. Growth answer construction/selection/refresh, arithmetic surface sync,
retrieved-ratio artifact/state handling, mutable state/evidence, artifact/ledger
work, promotion, sync/rebuild, and final sequencing remain graph-owned. The
commit proves no behavior, accuracy, ranking, performance, total-code or executed-
path reduction, benchmark improvement, schedule, or Phase 3 completion.

At this handoff, the sole selected follow-on is the 100-line prepared growth-
numeric renderer. One public aggregate-projection function is projected at 99
owner lines; all nine calls remain graph-external. Answer selection/refresh,
untraced-sentence repair, mutable state/evidence, and final sequencing remain hard
stops. Exact API, dependencies, five-method characterization gate, and rejected
expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Aggregate prepared growth-numeric renderer owner milestone

- `5fb0267` moves the former graph
  `_compose_complete_growth_numeric_answer(...)` body into
  `financial_aggregate_projection.py` as public
  `compose_complete_growth_numeric_answer(...)`. The former definition span was
  100 lines and the owner span is 99 after removing only `self` and rebinding the
  operation-family and topic-particle dependencies. All nine selected calls remain
  graph-external, owner-local selected calls remain zero, and retired graph-private
  source/test references are zero.
- Exactly six source/test files changed. Source is `+117/-111`, net `+6`: the
  graph is `+10/-110` and moves from 15,743 to 15,643 physical lines; aggregate
  projection is `+107/-1` and moves from 2,288 to 2,394. Tests are `+989/-38`,
  net `+951`; the whole commit is `+1,106/-149`, net `+957`.
- The committed source-only diff SHA-256 is
  `a92591876808e7e4744d7deb5d9ff83d7282d61cfaaeb7bfcf852ea232a2687b`.
  Literal body parity passed after only self removal and owner-local name
  rebinding. All ten affected retained caller definitions, including the nested
  sentence predicate, remain AST-identical after selected call normalization.
  The nine live calls are direct names at Try depth zero; the import DAG remains
  acyclic, public import identity is exact, and the old mixin attribute is absent.
- Five AST-counted unittest methods were added, moving the method inventory and
  full discovery from 1,669 to 1,674. Final validation passed focused 5/5,
  aggregate-owner module 40/40, the affected eight-module semantic set 755/755,
  import-side-effects 19/19, the nine-module union 774/774, runtime audit 217,
  full discovery 1,674/1,674, pycompile/fresh-import binding checks, and
  `git diff --check`. Benchmark refresh was **NOT RUN**, and no remote CI run is
  claimed or verified for this local branch.

This milestone closes only state-free projection of an already prepared growth
row/slot/evidence surface into a policy-rendered string. Answer replacement and
refresh, source-visible sentence repair, arithmetic synchronization, retrieved-
ratio artifact/state handling, mutable state/evidence, artifact/ledger work,
promotion, sync/rebuild, and final sequencing remain graph-owned. The commit
proves no behavior, accuracy, ranking, performance, total-code or executed-path
reduction, benchmark improvement, schedule, or Phase 3 completion.

At this handoff, the sole selected follow-on is the 130-line prepared growth
trace-inspection cluster. Three public aggregate predicates are projected at
28 + 56 + 43 = 127 owner lines; all 19 calls remain graph-external. Answer
replacement/refresh, source-visible sentence repair, compact-ratio state/trace,
mutable state/evidence, and final sequencing remain hard stops. Exact APIs,
existing-edge dependencies, six-method characterization gate, and rejected
expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Aggregate prepared growth trace-inspection owner milestone

- `c010a42` moves three former graph predicate bodies into
  `financial_aggregate_projection.py` as public
  `growth_answer_has_untraced_numeric_material(...)`,
  `narrative_summary_conflicts_with_growth_trace(...)`, and
  `growth_narrative_numeric_incompatible_with_trace(...)`. The former definition
  spans were 29 + 57 + 44 = 130 lines; the owner spans are
  28 + 56 + 43 = 127. All 19 selected calls remain graph-external, owner-local
  selected calls remain zero, and retired selected graph-private source/test
  references are zero.
- Exactly seven source/test files changed. Source is `+158/-153`, net `+5`: the
  graph is `+22/-153` and moves from 15,643 to 15,512 physical lines; aggregate
  projection is `+136/-0` and moves from 2,394 to 2,530. Tests are `+946/-80`,
  net `+866`; the whole commit is `+1,104/-233`, net `+871`.
- The committed source-only diff SHA-256 is
  `598f5e476cf0d8fef1c3767f2b6d33c82f1202702fd58e8c7d6e8c625fb7e348`.
  Literal body parity passed 3/3 after only self removal and owner-local name
  rebinding. Full retained-caller parity passed 8/8. The 19 live calls are direct
  names at Try depth zero; the import DAG remains acyclic; public import identity
  is exact; and the three old mixin attributes are absent.
- Six AST-counted unittest methods were added, moving the method inventory and
  full discovery from 1,674 to 1,680. Final validation passed focused 6/6,
  aggregate-owner module 46/46, the affected eight-module semantic set 761/761,
  import-side-effects 19/19, the nine-module union 780/780, runtime audit 217,
  full discovery 1,680/1,680, pycompile/fresh-import binding checks, and
  `git diff --check`. Benchmark refresh was **NOT RUN**, and no remote CI run is
  claimed or verified for this local branch.

This milestone closes only state-free inspection of already prepared growth
trace, answer, and evidence surfaces. Answer replacement and refresh, source-
visible sentence repair, arithmetic synchronization, retrieved-ratio artifact/
state handling, mutable state/evidence, artifact/ledger work, promotion,
sync/rebuild, and final sequencing remain graph-owned. The commit proves no
behavior, accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, or Phase 3 completion.

At this handoff, the sole selected follow-on is the 93-line dependency input-
binding policy cluster in graph lines 6013-6074, 6711-6725, and 6727-6742. Three
public dependency-projection functions are projected at 61 + 14 + 15 = 90 owner
lines; all four calls remain graph-external. Dependency operand-row construction,
binding-resolution state assembly, operand extraction, ratio-result projection,
evidence coercion, mutable state/evidence, and final sequencing remain hard stops.
Exact APIs, cycle-safe dependencies, six-method characterization gate, and
rejected expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Dependency input-binding policy owner milestone

- `7a20aab` moves the former graph policies into
  `financial_dependency_projection.py` as public
  `dependency_slot_matches_input(...)`,
  `task_prefers_sibling_output_synthesis(...)`, and
  `task_output_input_bindings(...)`. The former definition spans were
  62 + 15 + 16 = 93 lines; actual owner spans are 61 + 15 + 16 = 92 because
  removing `self` from the latter two one-line signatures does not reduce their
  physical span.
- A pre-move source audit corrected the prior four-call plan by finding three
  additional reconciliation callers. All seven selected production calls now
  use direct public imports at Try depth zero: four in calculation and three in
  reconciliation. Owner-local selected calls remain zero, and retired selected
  graph-private source/test references are zero. No compatibility wrapper or
  alias remains.
- Exactly five source/test files changed. Source is `+111/-103`, net `+8`:
  calculation graph moved from 15,512 to 15,419 physical lines, reconciliation
  moved from 2,428 to 2,429, and dependency projection moved from 3,235 to 3,335.
  Tests are `+1,164/-2`, net `+1,162`; the whole commit is `+1,275/-105`, net
  `+1,170`.
- The committed source-only diff SHA-256 is
  `b840839073e6d7febe828d75004e15e3a45ae2e298a5ded6c303cc53738162e1`.
  Literal body parity passed 3/3, all seven retained callers were exact after
  selected target normalization, the import DAG remained acyclic, public import
  identity was exact, and the three retired mixin attributes were absent.
- Six AST-counted unittest methods moved the method inventory and full discovery
  from 1,680 to 1,686. Final validation passed focused 6/6, dependency-owner
  69/69, affected nine-module semantic 895/895, import-side-effects 19/19,
  runtime audit 217, full discovery 1,686/1,686, pycompile/fresh-import binding
  checks, DAG/body/caller parity, and `git diff --check`. Benchmark refresh was
  **NOT RUN**, and no remote CI run is claimed or verified for this local branch.

This milestone changes only ownership of already deterministic dependency input
matching and task-output binding policy. Operand/evidence construction,
reconciliation state projection, ratio-result projection, mutable state/evidence,
artifact/ledger work, callbacks, promotion, sync/rebuild, and final sequencing
remain graph-owned. The commit proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, or Phase 3 completion.

At this handoff, the sole selected follow-on is the 127-line reconciliation
artifact-reference projection cluster in `financial_graph_reconciliation.py`.
Three public task-artifact projections plus one owner-private text matcher are
projected at 15 + 50 + 29 + 32 = 126 owner lines. Five selected calls finish as
four graph-external and one owner-local call. Structured-operand extraction,
candidate-map/cell selection, reconciliation state projection, artifact update
and ledger mutation, evidence construction, reranking/LLM work, reflection and
retry planning, mutable state, callbacks, promotion, sync/rebuild, and final
sequencing remain hard stops. Exact APIs, cycle-safe dependencies, the six-method
characterization gate, and rejected expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Reconciliation artifact-reference projection owner milestone

- `c825ab7` moves the former reconciliation helpers into
  `financial_task_artifacts.py` as public
  `reconciliation_artifact_candidate_ids_for_operand(...)`,
  `reconciliation_artifact_candidate_ids(...)`, and
  `reconciliation_evidence_refs(...)`, plus owner-private
  `_artifact_text_matches_operand_surface(...)`. The former definition spans were
  15 + 51 + 29 + 32 = 127 lines; actual owner spans are
  15 + 50 + 29 + 32 = 126. Four selected calls are direct graph imports and the
  matcher's one call is owner-local. Retired selected reconciliation-private
  source/test refs are zero and no compatibility wrapper or alias remains.
- A pre-move audit corrected the prior plan's statement that every selected
  reconciliation import would remain live. `_operand_text_match` had no use after
  relocation and was removed; all other touched imports remain live. The import
  DAG is acyclic and task artifacts do not import reconciliation.
- Exactly five source/test files changed. Source is `+153/-138`, net `+15`:
  reconciliation is `+10/-137` and moves from 2,429 to 2,302 physical lines;
  task artifacts are `+143/-1` and move from 1,250 to 1,392. Tests are
  `+1,455/-4`, net `+1,451`; the whole commit is `+1,608/-142`, net `+1,466`.
- The committed source-only diff SHA-256 is
  `65819999639a808bb95ec29ddf6547751fddaff3eed4e3af321210d367a43b55`.
  Literal body parity passed 4/4 after only `self` removal and owner-local name
  rebinding. Both retained executable callers remained exact after selected
  target normalization; public import identity, fresh import, and DAG checks
  passed; the four retired mixin attributes are absent.
- Six AST-counted unittest methods moved the method inventory and full discovery
  from 1,686 to 1,692. Final validation passed focused 6/6, task-artifact owner
  9/9, affected eight-module semantic 817/817, import-side-effects 19/19,
  semantic/import union 836/836, runtime audit 217, full discovery 1,692/1,692,
  pycompile/fresh-import binding checks, DAG/body/caller parity, and
  `git diff --check`. Benchmark refresh was **NOT RUN**, and no remote CI run is
  claimed or verified for this local branch.

This milestone changes only ownership of deterministic projection over already
prepared reconciliation state, artifact, match, and evidence-reference records.
Structured-candidate/cell selection, evidence construction, reconciliation state
projection, artifact creation/update and whole-ledger mutation, reranking/LLM
work, reflection/retry planning, callbacks, promotion, sync/rebuild, mutable
state/evidence, and final sequencing remain graph-owned. The commit proves no
behavior, accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is the 79-line reflection request/
plan projection cluster in `financial_graph_reconciliation.py`. Public
`normalise_reflection_plan_record(...)` and `build_reflection_request(...)`, two
owner-private summaries, and the bounded strategy/budget constants move to the
existing `financial_reflection_projection.py` owner. Four selected calls finish
as two graph-external and two owner-local calls; projected owner function spans
total 78. Heuristic planning, prompt/model invocation, retry-query finalization,
retry action application, report/artifact ledger mutation, eligibility/routing,
mutable state/evidence, and final sequencing remain hard stops. Exact APIs,
cycle-safe dependencies, the six-method characterization gate, and rejected
alternatives are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Reflection request/plan projection owner milestone

- `c47ac50` moves the former reflection request/plan projections into
  `financial_reflection_projection.py` as public
  `normalise_reflection_plan_record(...)` and `build_reflection_request(...)`,
  owner-private `_reflection_runtime_trace_summary(...)` and
  `_reflection_evidence_summary(...)`, plus their bounded strategy/budget
  constants. The former definition spans were 35 + 15 + 7 + 22 = 79 lines; the
  actual public-two/private-two owner spans are 35 + 15 + 7 + 21 = 78. Two
  selected calls are direct graph imports and the summary calls are owner-local.
  Retired selected reconciliation-private source/test refs are zero and no
  compatibility wrapper or alias remains.
- The import DAG remains acyclic: reflection projection imports the strict
  runtime-trace resolver, runtime trace does not import reflection projection,
  and reflection projection does not import reconciliation. The graph keeps its
  independent strict resolver use for heuristic retry planning. The selected
  spans move no runtime-domain baseline record and the reviewed count remains
  217.
- Exactly three source/test files changed. Source is `+110/-99`, net `+11`:
  reconciliation is `+7/-98` and moves from 2,302 to 2,211 physical lines;
  reflection projection is `+103/-1` and moves from 158 to 260. Tests are
  `+1,199/-14`, net `+1,185`; the whole commit is `+1,309/-113`, net `+1,196`.
- The committed source-only diff SHA-256 is
  `5cf8c743dd07a22ac9281711638f62588ecd771d708434e1cbcf0a70144cc56a`.
  Literal body parity passed 4/4 after only `self` removal and owner-local name
  rebinding. `_plan_reflection_retry(...)` remained exact after selected target
  normalization; public import identity, fresh import, DAG checks, and retired
  mixin-attribute absence passed.
- Exactly six new unittest methods moved full discovery from 1,692 to 1,698.
  Final validation passed focused 6/6, reflection contract 18/18, affected
  seven-module semantic 800/800, import-side-effects 19/19, semantic/import union
  819/819, runtime audit 217, full discovery 1,698/1,698, pycompile/fresh-import
  binding checks, DAG/body/caller parity, and `git diff --check`. Benchmark refresh
  was **NOT RUN**, and no remote CI run is claimed or verified for this local
  branch.

This milestone changes only ownership of deterministic projection over an
already prepared reflection planner record and graph state. Heuristic planning,
missing-info inference, retry-query finalization, prompt/model invocation,
structured-planner catch/fallback, retry action application, report/artifact
ledger mutation, eligibility/routing, mutable state/evidence, promotion, and final
sequencing remain graph-owned. The commit proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, retry activation, promotion evidence, ledger completion, or Phase 3
completion.

At this handoff, the sole selected follow-on is the 76-line dependency
reconciliation preparation pair in `financial_graph_reconciliation.py`. Public
`active_subtask_with_sibling_lookup_surfaces(...)` and
`dependency_resolved_reconciliation_result(...)` are projected at 47 + 27 = 74
owner lines in `financial_dependency_projection.py`. Five selected calls finish
graph-external and none finish owner-local. The four callers, dependency-state
lookup, candidate/cell and evidence construction, ontology completion, LLM
reranking, retry selection, artifact/ledger mutation, mutable state/evidence,
promotion, sync/rebuild, and final sequencing remain hard stops. Exact APIs,
cycle-safe dependencies, the six-method characterization gate, and rejected
expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Dependency reconciliation preparation owner milestone

- `5a0c3e0` moves the former sibling-surface and resolved-reconciliation
  preparations into `financial_dependency_projection.py` as public
  `active_subtask_with_sibling_lookup_surfaces(...)` and
  `dependency_resolved_reconciliation_result(...)`. The former definition spans
  were 48 + 28 = 76 lines; the public owner spans are 47 + 27 = 74. All five
  selected calls remain graph-external, retired selected private source/test
  refs are zero, and no compatibility wrapper or alias remains.
- The import DAG remains acyclic. The owner added only `RECONCILIATION_POLICY` on
  its existing retrieval-policy edge, does not import reconciliation, and the
  selected spans move no runtime-domain baseline record; the reviewed count
  remains 217.
- Exactly four source/test files changed. Source is `+93/-85`, net `+8`:
  reconciliation moved from 2,211 to 2,137 physical lines and dependency
  projection from 3,335 to 3,417. Tests are `+1,228/-28`, net `+1,200`; the whole
  commit is `+1,321/-113`, net `+1,208`.
- The committed source-only diff SHA-256 is
  `c9e931e818cfc7661ccb05bc162078a4db83120aab44f6dd9331dac51fa7a501`.
  Literal body parity passed 2/2 after only `self` removal. All four retained
  executable callers remained exact after selected target normalization; public
  import identity, fresh import, DAG checks, and retired mixin-attribute absence
  passed.
- Exactly six new unittest methods moved full discovery from 1,698 to 1,704.
  Final validation passed focused 6/6, dependency owner 75/75, affected eight-
  module semantic 823/823, import-side-effects 19/19, semantic/import union
  842/842, runtime audit 217, full discovery 1,704/1,704, pycompile/fresh-import
  binding checks, DAG/body/caller parity, and `git diff --check`. Benchmark refresh
  was **NOT RUN**, and no remote CI run is claimed or verified for this local
  branch.

This milestone changes only ownership of deterministic projection over already
prepared active-subtask, sibling-task, and dependency-binding records.
Dependency-state lookup, candidate/cell/evidence construction, ontology
completion, LLM reranking, retry selection, artifact creation/update and ledger
mutation, mutable state/evidence, promotion, sync/rebuild, and final sequencing
remain graph-owned. The commit proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is the 64-line prepared runtime-
evidence/task-artifact row projection pair in `financial_graph_calculation.py`.
Public `evidence_items_with_runtime(...)` and
`ratio_result_rows_from_task_artifacts(...)` are projected at 20 + 42 = 62 owner
lines in `financial_task_artifacts.py`. Four selected calls finish graph-external
and none finish owner-local. Operand extraction/evidence selection, ratio
conflict and arithmetic, artifact/ledger mutation, mutable state/evidence,
promotion, sync/rebuild, and final sequencing remain hard stops. The adjacent
preferred selector is excluded by the aggregate-projection -> runtime-trace ->
task-artifact reverse path. Exact APIs, cycle-safe dependencies, the six-method
characterization gate, and rejected expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Task-artifact read projection owner milestone

- `8d627a6` moves the former calculation-graph runtime-evidence merge and ratio
  task-artifact row projections into `financial_task_artifacts.py` as public
  `evidence_items_with_runtime(...)` and
  `ratio_result_rows_from_task_artifacts(...)`. The former definition spans were
  21 + 43 = 64 lines; the public owner spans are 20 + 42 = 62. All four selected
  calls remain graph-external, retired selected private source/test refs are zero,
  and no compatibility wrapper or alias remains.
- The import DAG remains acyclic. The owner needed no new module dependency,
  does not import the calculation graph, and the selected spans move no runtime-
  domain baseline record; the reviewed count remains 217.
- Exactly five source/test files changed. Source is `+74/-70`, net `+4`:
  calculation moved from 15,419 to 15,355 physical lines and task artifacts from
  1,392 to 1,460. Tests are `+911/-8`, net `+903`; the whole commit is
  `+985/-78`, net `+907`.
- The committed source-only diff SHA-256 is
  `07ffa0657a4e7762442aa3d79d88dd06084a0c0319c0eb7fce8185902061018e`.
  Literal body parity passed 2/2 after only `self` removal. All three retained
  executable callers remained exact after selected target normalization; public
  import identity, fresh import, DAG checks, and retired mixin-attribute absence
  passed.
- Exactly six new unittest methods moved full discovery from 1,704 to 1,710.
  Final validation passed focused 6/6, task-artifact owner 15/15, affected ten-
  module semantic 832/832, import-side-effects 19/19, semantic/import union
  851/851, runtime audit 217, full discovery 1,710/1,710, pycompile/fresh-import
  binding checks, DAG/body/caller parity, and `git diff --check`. Benchmark refresh
  was **NOT RUN**, and no remote CI run is claimed or verified for this local
  branch.

This milestone changes only ownership of deterministic read projection over
already prepared evidence, state, task, and artifact records. Operand extraction
and evidence selection, ratio conflict/arithmetic, artifact creation/update and
ledger mutation, mutable state/evidence, promotion, sync/rebuild, and final
sequencing remain graph-owned. The commit proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is the 168-line final-answer evidence
projection pair in `financial_graph_calculation.py`. Public
`filter_aggregate_evidence_for_final_answer(...)` and
`append_operand_evidence_for_final_answer(...)` are projected at 65 + 101 = 166
owner lines in `financial_aggregate_projection.py`. Seven selected calls finish
graph-external and none finish owner-local. Retrieved-doc/evidence preparation,
selected-claim and provenance projection, answer composition/refresh, artifact/
ledger mutation, mutable state/evidence, promotion, sync/rebuild, and final
sequencing remain hard stops. The adjacent answer-slot iteration family is
excluded because `_slot_metric_keys(...)` is passed as a bound callback. Exact
APIs, cycle-safe dependencies, the six-method characterization gate, and rejected
expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Final-answer evidence projection owner milestone

- `cde3d98` moves the former calculation-graph final-answer evidence filter and
  operand-evidence append projections into `financial_aggregate_projection.py`
  as public `filter_aggregate_evidence_for_final_answer(...)` and
  `append_operand_evidence_for_final_answer(...)`. The former definition spans
  were 66 + 102 = 168 lines; the public owner spans are 65 + 101 = 166. All
  seven selected calls remain graph-external, retired selected private source/
  test refs are zero, and no compatibility wrapper or alias remains.
- The import DAG remains acyclic. The owner added three symbols on its existing
  numeric-surface edge, does not import either graph module, and the selected
  spans move no runtime-domain baseline record; the reviewed count remains 217.
  The calculation graph removed the two numeric-support imports made dead by the
  move while retaining its independently used text-support import.
- Exactly seven source/test files changed. Source is `+186/-179`, net `+7`:
  calculation moved from 15,355 to 15,185 physical lines, the main graph from
  1,200 to 1,204, and aggregate projection from 2,530 to 2,703. Tests are
  `+1,426/-34`, net `+1,392`; the whole commit is `+1,612/-213`, net `+1,399`.
- The committed source-only diff SHA-256 is
  `1e9aadbbef8bf83438337b2a68f753344f564a2c4a49c5192a61a7c2d02917b8`.
  Literal body parity passed 2/2 after only `self` removal. All four retained
  executable callers remained exact after selected target normalization; public
  import identity, fresh import, DAG checks, and retired mixin-attribute absence
  passed.
- Exactly six new unittest methods moved full discovery from 1,710 to 1,716.
  Final validation passed focused 6/6, aggregate owner 52/52, affected eight-
  module semantic 767/767, import-side-effects 19/19, semantic/import union
  786/786, runtime audit 217, full discovery 1,716/1,716, pycompile/fresh-import
  binding checks, DAG/body/caller parity, and `git diff --check`. Benchmark
  refresh was **NOT RUN**, and no remote CI run is claimed or verified for this
  local branch.

This milestone changes only ownership of deterministic filtering and projection
over already prepared answer, evidence, operand, and claim-id surfaces.
Retrieved-doc/evidence preparation, selected-claim/provenance projection, answer
choice/composition/refresh, artifact/ledger mutation, mutable state/evidence,
promotion, sync/rebuild, and final sequencing remain graph-owned. The commit
proves no behavior, accuracy, ranking, performance, total-code or executed-path
reduction, benchmark improvement, schedule, ledger completion, or Phase 3
completion.

At this handoff, the sole selected follow-on is the 155-line growth-answer
numeric completion/sanitization pair in `financial_graph_calculation.py`. Public
`ensure_complete_growth_numeric_answer(...)` and
`strip_untraced_numeric_material_from_growth_narrative_sentence(...)` are
projected at 46 + 107 = 153 owner lines in
`financial_aggregate_projection.py`. Nineteen selected calls finish graph-
external and none finish owner-local. The owner already has every dependency and
the selected spans move no runtime-domain baseline record. Final-growth
selection, answer refresh/composition, compact-ratio state/trace, artifact/
ledger mutation, mutable state/evidence, promotion, sync/rebuild, and final
sequencing remain hard stops. Exact APIs, cycle-safe dependencies, the six-
method characterization gate, and rejected expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Growth-answer numeric completion/sanitization owner milestone

- `3674bb1` moves graph-private growth-answer numeric completion and narrative
  sanitization into `financial_aggregate_projection.py` as public
  `ensure_complete_growth_numeric_answer(...)` and
  `strip_untraced_numeric_material_from_growth_narrative_sentence(...)`. The
  former definition spans were 47 + 108 = 155 lines; the public owner spans are
  46 + 107 = 153. All 19 selected calls remain graph-external, retired selected
  private source/test refs are zero, and no compatibility wrapper or alias
  remains.
- The import DAG is unchanged: the owner already held every dependency, imports
  neither graph module, and the selected spans moved no runtime-domain baseline
  record. The reviewed count remains 217. Literal body parity passed 2/2 after
  only `self` removal and owner-local name normalization; all six retained caller
  bodies remained exact after selected target normalization.
- Exactly six source/test files changed. Source is `+178/-176`, net `+2`:
  calculation moved from 15,185 to 15,030 physical lines and aggregate projection
  from 2,703 to 2,860. Tests are `+1,547/-77`, net `+1,470`; the whole commit is
  `+1,725/-253`, net `+1,472`. The aggregate test file moved from 8,951 to
  10,402 lines and answer projection tests from 3,488 to 3,507; the other two
  modified test files retained their physical sizes.
- The committed source-only diff SHA-256 is
  `fb580debe8b766ce98f9258f55b13b00d712d5844fb6c18268abed685d38ebb5`.
  Public import identity, old mixin-attribute absence, pycompile/fresh import,
  DAG/body/caller parity, and `git diff --check` passed.
- Exactly six new unittest methods moved full discovery from 1,716 to 1,722.
  Final validation passed focused 6/6, aggregate owner 58/58, affected eight-
  module semantic 773/773, import-side-effects 19/19, semantic/import union
  792/792, runtime audit 217, and full discovery 1,722/1,722. Benchmark refresh
  was **NOT RUN**, and no remote CI run is claimed or verified for this local
  branch.

This milestone changes only ownership of deterministic completion/sanitization
over already prepared answer, result, and evidence surfaces. Final-growth
selection, answer refresh/composition, compact-ratio state/trace, mutable state/
evidence, artifact/ledger mutation, promotion, sync/rebuild, and final sequencing
remain graph-owned. The commit proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is graph-private
`_append_final_answer_surface_operands_from_evidence(...)`, a 313-line state-free
projection over already prepared projection, evidence, and answer inputs. It is
projected as public 312-line
`append_final_answer_surface_operands_from_evidence(...)` in
`financial_aggregate_projection.py`; both calls finish graph-external and none
finishes owner-local. The owner adds symbols only on existing numeric-surface and
runtime-normalization edges and normalizes answer-slot calls to existing owner
imports, so the import DAG remains acyclic. Both callers, evidence filtering and
provenance adoption, public-answer/runtime-evidence preparation, retrieval,
evidence-window/provenance construction, evidence-list mutation, mutable state,
artifact/ledger mutation, promotion, sync/rebuild, and final sequencing remain
hard stops. Exact API, the six-method characterize-first gate, projected test
counts, and rejected state/carrier/cycle expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Final-answer surface operand owner milestone

- `fae0516` moves graph-private
  `_append_final_answer_surface_operands_from_evidence(...)` into
  `financial_aggregate_projection.py` as public
  `append_final_answer_surface_operands_from_evidence(...)`. The former definition
  span was 313 lines and the public owner span is 312. Both selected calls remain
  graph-external, retired selected private source/test refs are zero, and no
  compatibility wrapper or alias remains.
- The owner adds only symbols on its existing numeric-surface and runtime-
  normalization edges and normalizes two answer-slot calls to existing owner
  imports. Literal body parity and both complete caller-body parity checks passed
  after only receiver/name normalization. Public import identity, old mixin-
  attribute absence, pycompile/fresh import, DAG, and `git diff --check` passed.
  The selected span moved no runtime-domain baseline record; the reviewed count
  remains 217.
- Exactly six source/test files changed. Source is `+325/-319`, net `+6`:
  calculation moved from 15,030 to 14,715 physical lines, main graph from 1,204
  to 1,205, and aggregate projection from 2,860 to 3,180. Tests are `+983/-9`,
  net `+974`; the whole commit is `+1,308/-328`, net `+980`. The aggregate test
  file moved from 10,402 to 11,375 lines, numeric-provenance tests from 1,014 to
  1,015, and subtask-loop tests from 23,448 to 23,448.
- The committed source-only diff SHA-256 is
  `6b45dd51cfe790304227f99242525c54a7ddb2c0a65dafe940cb7e42069b8020`.
  Exactly six new unittest methods moved full discovery from 1,722 to 1,728.
  Final validation passed focused 6/6, aggregate owner 64/64, affected nine-
  module semantic 790/790, import-side-effects 19/19, semantic/import union
  809/809, runtime audit 217, and full discovery 1,728/1,728. Benchmark refresh
  was **NOT RUN**, and no remote CI run is claimed or verified for this local
  branch.

This milestone changes only ownership of deterministic projection over already
prepared answer, calculation, and evidence surfaces. Both callers, evidence
preparation/filtering and provenance adoption, public-answer/runtime-evidence
assembly, mutable state/evidence, artifact/ledger mutation, promotion,
sync/rebuild, and final sequencing remain graph-owned. The commit proves no
behavior, accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is two characterize-first seams
totaling 135 current definition-span lines in lookup recovery, graph helpers, and
reconciliation. Existing public `lookup_hints_for_concept_key(...)` and
`coerce_lookup_magnitude_value(...)` move first to
`financial_operand_resolution.py`; public
`candidate_row_block_signature(...)` and
`repair_note_operand_units_from_same_block(...)` follow. The projected owner
surface is 134 lines across four public functions. Fifteen current direct calls
finish as 12 external and three owner-local. Existing import directions make the
move cycle-free and no selected span moves a runtime-domain baseline record.
Lookup-record recovery, report-file/local-unit lookup, structured-cell selection,
candidate extraction, LLM reranking, mutable reconciliation state/artifact/retry,
ledger mutation, and final sequencing remain hard stops. Exact APIs, per-seam
four-method characterize-first gates, projected validation counts, and rejected
state/carrier/cycle expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Operand lookup magnitude and same-block note-unit owner milestone

- `5bd9e6f` moves existing public `lookup_hints_for_concept_key(...)` and
  `coerce_lookup_magnitude_value(...)` from lookup recovery, graph-private
  `_candidate_row_block_signature(...)`, and reconciliation-private
  `_repair_note_operand_units_from_same_block(...)` into
  `financial_operand_resolution.py` as four public functions. The former
  definition spans were 16 + 32 + 29 + 58 = 135 lines and the public owner spans
  are 16 + 32 + 29 + 57 = 134.
- Fifteen selected direct calls finish as 12 external and three owner-local:
  hints 3/1, magnitude coercion 2/1, row-block signature 6/1, and note-unit repair
  1/0. Retired selected private source/test refs are zero; no wrapper,
  compatibility alias, callback, flag, reason, or carrier remains.
- Literal body parity passed for all four functions after only name/`self`
  normalization. Complete retained caller parity passed for graph-helper logical/
  family signatures, structured reconciliation extraction, operand-row
  construction, and lookup-record coercion. Public import identity, removed
  mixin attribute absence, pycompile/fresh import, DAG, and diff check passed.
  None of the selected spans moved a runtime-domain baseline record; the reviewed
  count remains 217.
- Exactly seven source/test files changed. Source is `+156/-154`, net `+2`:
  graph helpers moved from 6,299 to 6,269 physical lines, reconciliation from
  2,137 to 2,079, lookup recovery from 609 to 557, and operand resolution from
  3,461 to 3,603. Tests are `+867/-13`, net `+854`; the whole commit is
  `+1,023/-167`, net `+856`. Exactly eight new unittest methods moved full
  discovery from 1,728 to 1,736.
- The committed source-only diff SHA-256 is
  `b7bcf68a9cd79ab91f6e30978e434d9b5b504f06a85b4e582c20b0497bbecf21`.
  Final validation passed focused 8/8, operand owner 69/69, affected eight-module
  semantic 813/813, import-side-effects 19/19, semantic/import union 832/832,
  runtime audit 217, and full discovery 1,736/1,736. Benchmark refresh was
  **NOT RUN**, and no remote CI run is claimed or verified for this local branch.

This milestone changes only ownership of deterministic lookup/magnitude and
same-block unit resolution. Lookup-record recovery, report-file/local-unit lookup,
structured-cell selection, candidate extraction, LLM reranking, mutable
reconciliation state/evidence, artifact/ledger mutation, and final sequencing
remain in their prior owners. The commit proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is two characterize-first seams
totaling 189 current definition-span lines in `financial_graph.py`. Prepared
evidence defaults/metadata compaction/enrichment move first; literal agent-answer,
review/debug bundle, and citation projection follow into a new
`financial_agent_run_projection.py`. The projected owner surface is 184 lines
across six public and two owner-private functions. Eleven current calls finish as
nine graph-external and two owner-local. Runtime-evidence fallback/selection,
structured/stale answer repair, trace resolution/rebuild, graph execution,
compatibility assembly, mutable state/evidence, artifact/ledger mutation, and
final sequencing remain hard stops. Exact APIs, the eight-method characterize-
first gates, projected validation counts, and rejected state/carrier/cycle
expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Caller-facing run-projection owner milestone

- `84fe1d5` creates `financial_agent_run_projection.py` and moves prepared
  runtime-evidence defaults/metadata compaction/enrichment plus literal agent-
  answer, review/debug, and citation projection out of `FinancialAgent`.
  The former 11 + 25 + 26 + 2 + 34 + 45 + 14 + 32 = 189 definition-span lines
  become 184 owner lines across six public and two owner-private functions.
- Eleven selected direct calls finish as nine graph-external and two owner-local.
  Retired selected private source/test refs are zero; no wrapper, compatibility
  alias, callback, reason, flag, carrier, or new output field remains.
- Literal body parity passed for all eight moved functions after only `self` and
  selected-name normalization. Complete caller parity passed for
  `_runtime_evidence_from_retrieved_docs(...)` and `FinancialAgent.run()`.
  Public import identity, removed mixin-attribute absence, pycompile/fresh import,
  DAG, and diff check passed. None of the selected spans moved a runtime-domain
  baseline record; the reviewed count remains 217.
- Exactly four source/test files changed. Source is `+232/-211`, net `+21`:
  main graph moved from 1,205 to 1,011 physical lines and the new owner contains
  215. Tests are `+1,702/-17`, net `+1,685`; the whole commit is
  `+1,934/-228`, net `+1,706`. Run-projection tests moved from 57 to 65 methods,
  and exactly eight new unittest methods moved full discovery from 1,736 to
  1,744.
- The committed source-only diff SHA-256 is
  `84b8d32bee450cde9370fa6f72646f006ce9bb47413169b34c1c50b0053a5a24`.
  Final validation passed focused 8/8, run-projection owner 65/65, affected
  eight-module semantic 515/515, import-side-effects 19/19, semantic/import union
  534/534, runtime audit 217, and full discovery 1,744/1,744. Benchmark refresh
  was **NOT RUN**, and no remote CI run is claimed or verified for this local
  branch.

This milestone changes only ownership of deterministic projection over already
prepared runtime values. Runtime-evidence fallback/selection, structured and
stale public-answer repair, trace resolution/rebuild, graph execution,
compatibility assembly, retrieval/provenance construction, mutable state/
evidence, artifact/ledger mutation, and final sequencing remain graph/existing-
owner responsibilities. The commit proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is one characterize-first seam
totaling 74 current definition-span lines in `financial_graph.py`. Structured-
result missing-answer selection, aggregate complete-answer projection, public-
answer state copying, and public projection-state assembly move into the
existing run-projection owner as four public functions totaling a projected 71
lines. Thirteen current calls finish as 12 graph-external and one owner-local;
the cumulative owner surface becomes public ten plus owner-private two with 24
selected calls split external 21/local three. Dynamic complete-numeric,
structured-subtask, collapsed-ratio, period-repair and retrieved-ratio callers,
runtime-evidence selection, graph execution, compatibility assembly, mutable
state/evidence, artifact/ledger mutation, and final sequencing remain hard stops.
Exact APIs, the six-method characterize-first gate, projected validation counts,
and rejected state/callback/carrier/cycle expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Prepared public-answer state-projection ownership

- `a88b215` moves structured-result missing-answer selection, complete aggregate
  public-answer projection, answer-state copying, and prepared public projection-
  state assembly into the existing `financial_agent_run_projection.py` owner.
  The former 21 + 30 + 17 + 6 = 74 definition-span lines become four public
  functions totaling 20 + 29 + 16 + 6 = 71 owner lines.
- Thirteen selected direct calls finish as 12 graph-external and one owner-local.
  Together with the prior run-projection milestone, the owner now exposes public
  ten plus owner-private two across 24 selected calls split external 21/local
  three. Retired selected private source/test refs are zero; no wrapper,
  compatibility alias, callback, reason, flag, carrier, or output field remains.
- Literal body parity passed for all four moved functions after only `self` and
  selected-name normalization. Complete caller parity passed for stale structured
  public-answer repair, structured public-answer trace projection, public runtime-
  trace repair, and `FinancialAgent.run()`. Public import identity, removed
  mixin-attribute absence, pycompile/fresh import, DAG, and diff check passed.
  None of the selected spans moved a runtime-domain baseline record; the reviewed
  count remains 217.
- Exactly four source/test files changed. Source is `+105/-93`, net `+12`: main
  graph moved from 1,011 to 936 physical lines and the run owner from 215 to 302.
  Tests are `+1,269/-8`, net `+1,261`; the whole commit is `+1,374/-101`, net
  `+1,273`. Run-projection tests moved from 65 to 71 methods, and exactly six new
  unittest methods moved full discovery from 1,744 to 1,750.
- The committed source-only diff SHA-256 is
  `45e12114a8bfb2f7513cbde887b7fe4a8a7b5ed65c2300af902939b6dc38fc45`.
  Final validation passed focused 6/6, run-projection owner 71/71, affected
  eight-module semantic 521/521, import-side-effects 19/19, semantic/import union
  540/540, runtime audit 217, and full discovery 1,750/1,750. Benchmark refresh
  was **NOT RUN**, and no remote CI run is claimed or verified for this local
  branch.

This milestone changes only ownership of deterministic selection and projection
over already prepared answer, trace, evidence, and state values. Dynamic
structured/stale answer repair, trace resolution/rebuild, runtime-evidence
selection, graph execution, compatibility assembly, retrieval/provenance
construction, mutable state/evidence, artifact/ledger mutation, and final
sequencing remain graph/existing-owner responsibilities. The commit proves no
behavior, accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is two sequential characterize-
first seams totaling 293 current definition-span lines in
`financial_graph_reconciliation.py`. Prepared candidate statement/unit/period/
score/identity/row projection moves first; reconciliation-match and candidate-ID
projection follows into a new `financial_reconciliation_candidates.py` owner.
The projected surface is 285 lines across seven public and four owner-private
functions. Twenty-six current calls finish as 19 reconciliation-external and
seven owner-local. Structured-pair and operand extraction orchestration,
candidate selection, LLM reranking, evidence construction, artifact/retry/state
mutation, and final sequencing remain hard stops. Exact APIs, the eight-method
characterize-first gate, projected validation counts, import/DAG boundary, and
rejected state/callback/carrier/cycle expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Structured reconciliation candidate-projection owner milestone

- `bb0a982` creates `financial_reconciliation_candidates.py` and moves prepared
  candidate statement/unit/period/score/identity/row, reconciliation-match, and
  candidate-ID projection out of `FinancialAgentReconciliationMixin`. The former
  36 + 38 + 11 + 10 + 29 + 33 + 17 + 63 + 17 + 26 + 13 = 293 definition-span
  lines become 285 owner lines across seven public and four owner-private
  functions.
- Twenty-six selected direct calls finish as 19 reconciliation-external and
  seven owner-local. Retired selected private source/test refs are zero; no
  wrapper, compatibility alias, callback, reason, flag, carrier, or output field
  remains.
- Literal body parity passed for all eleven moved functions after only `self`
  removal and selected-name normalization. Complete caller parity passed for
  `_extract_structured_period_pair_rows(...)`,
  `_evidence_items_from_reconciliation_matches(...)`, and
  `_extract_structured_operands_from_reconciliation(...)`. Public import
  identity, removed mixin-attribute absence, pycompile/fresh import, DAG, and
  diff check passed. None of the selected spans moved a runtime-domain baseline
  record; the reviewed count remains 217.
- Exactly eight source/test files changed. Source is `+357/-331`, net `+26`:
  reconciliation moved from 2,079 to 1,776 physical lines and the new owner
  contains 329. Tests are `+686/-30`, net `+656`; the whole commit is
  `+1,043/-361`, net `+682`. The touched tests moved from 31,422 to 32,078
  physical lines, and exactly eight new unittest methods moved full discovery
  from 1,750 to 1,758.
- The committed source-only diff SHA-256 is
  `6469dfd06b0efd36c92d252753ba96ecdeb5421e4dc3fdaac0c492cdd4167a5f`.
  Final validation passed focused 8/8, candidate owner 8/8, affected seven-
  module semantic 486/486, import-side-effects 19/19, semantic/import union
  505/505, runtime audit 217, full discovery 1,758/1,758, pycompile/fresh-import
  binding checks, DAG/body/caller parity, and `git diff --check`. Benchmark
  refresh was **NOT RUN**, and no remote CI run is claimed or verified for this
  local branch.

This milestone changes only ownership of deterministic projection over already
prepared candidate, cell, operand, match, constraint, and ID mappings. Candidate
collection/selection, structured-pair and operand extraction orchestration, LLM
reranking, evidence construction, artifact/retry/state mutation, ledger work,
and final sequencing remain graph-owned. The commit proves no behavior,
accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is one characterize-first 107-line
reflection retry-query projection batch into the existing
`financial_reflection_projection.py` owner. Public `build_retry_queries(...)`
and `finalize_retry_queries(...)` project to 106 owner lines. Three current calls
finish as two graph-external and one owner-local. Heuristic dependency/calc-
family resolution, missing-info inference, prompt/model planning, action/report/
artifact construction, state clearing, routing/promotion, and final sequencing
remain hard stops. Exact APIs, the six-method CURRENT-SOURCE gate, projected
validation counts, DAG, and rejected state/callback/carrier/cycle expansions are
maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Reflection retry-query projection owner milestone

- `b74535e` moves `_build_retry_queries(...)` and
  `_finalize_retry_queries(...)` out of the reconciliation and calculation graph
  mixins into public `build_retry_queries(...)` and
  `finalize_retry_queries(...)` in `financial_reflection_projection.py`. The
  former 26 + 81 = 107 definition-span lines become 26 + 80 = 106 owner lines.
- Three selected calls finish as two graph-external and one owner-local builder
  call from the finalizer. Retired selected private refs are zero; no wrapper,
  compatibility alias, callback, reason, flag, carrier, or output field remains.
- Literal body parity passed after only standalone `self` removal and the
  finalizer's owner-local builder rebind. Complete caller parity passed for
  `_heuristic_reflection_query_plan(...)` and `_prepare_reflection_retry(...)`.
  Public import identity, removed mixin-attribute absence, pycompile/fresh
  import, DAG, and diff check passed. None of the selected spans moved a runtime-
  domain baseline record; the reviewed count remains 217.
- Exactly five source/test files changed. Source is `+118/-112`, net `+6`:
  calculation moved from 14,715 to 14,716 physical lines, reconciliation from
  1,776 to 1,667, and reflection projection from 260 to 374. Tests are
  `+1,113/-4`, net `+1,109`; the whole commit is `+1,231/-116`, net `+1,115`.
  Exactly six new unittest methods moved full discovery from 1,758 to 1,764.
- The committed source-only diff SHA-256 is
  `728603f15ce24c0915444755442bc6cf3be4a2bbd26c6f41adffedcb08ccdbb1`.
  Final validation passed focused 6/6, reflection owner 24/24, affected eight-
  module semantic 758/758, import-side-effects 19/19, semantic/import union
  777/777, runtime audit 217, full discovery 1,764/1,764, pycompile/fresh import,
  DAG/body/caller parity, and `git diff --check`. Benchmark refresh was **NOT
  RUN**, and no remote CI run is claimed or verified for this local branch.

This milestone changes only ownership of deterministic retry-query projection
over already prepared state, plan, missing-info, company, year, and section
values. Heuristic dependency/calc-family resolution, missing-info inference,
prompt/model planning, action/report/artifact construction, state clearing,
retrieval routing, retry eligibility/budget/promotion, and final sequencing
remain graph-owned. The commit proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is one characterize-first 156-line
aggregate subtask projection/upsert batch from `financial_graph_planning.py`
into the existing `financial_aggregate_projection.py` owner. Public
`build_aggregate_calculation_projection(...)`,
`structured_subtask_projection_for_public_answer(...)`, and
`upsert_subtask_result(...)` plus owner-private
`_subtask_upsert_quality_rank(...)` project to 152 owner lines. Six selected
calls finish as four graph-external and two owner-local. The distinct runtime-
trace private `_build_aggregate_calculation_projection(...)` remains live and is
not part of the retired-ref rule. Nested traversal/specificity/promotion is a hard
stop because co-moving it would require planning to import aggregate while
aggregate already reaches planning through dependency projection. Mutable state,
filtering, recovery/alignment/synchronization, artifact/ledger mutation, and
final sequencing also remain graph-owned. Exact APIs, the seven-method CURRENT-
SOURCE gate, projected validation counts, DAG, and rejected state/callback/
carrier/cycle expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Aggregate subtask projection/upsert owner milestone

- `06710c1` moves `_build_aggregate_calculation_projection(...)`,
  `_structured_subtask_projection_for_public_answer(...)`,
  `_upsert_subtask_result(...)`, and `_subtask_upsert_quality_rank(...)` out of
  `FinancialAgentPlanningMixin`. They become public
  `build_aggregate_calculation_projection(...)`, public
  `structured_subtask_projection_for_public_answer(...)`, public
  `upsert_subtask_result(...)`, and owner-private
  `_subtask_upsert_quality_rank(...)` in `financial_aggregate_projection.py`.
  The former 69 + 36 + 23 + 28 = 156 definition-span lines become
  68 + 35 + 22 + 28 = 153 owner lines. The prior handoff's projected 27-line
  rank span is corrected here: its one-line signature keeps the physical span at
  28 after `self` removal.
- Six selected calls finish as four graph-external and two owner-local rank
  calls. The distinct runtime-trace private aggregate builder and its six calls
  remain live. Retired planning definitions and selected mixin-qualified refs
  are zero; no wrapper, compatibility alias, callback, reason, flag, carrier, or
  output field remains.
- Literal body parity passed for all four moved definitions after only `self`
  removal and owner-local operation/rank rebinding. Complete caller parity passed
  for `_rebuild_aggregate_projection(...)`, `_advance_calculation_subtask(...)`,
  `_prepare_initial_aggregate_state(...)`, and
  `_structured_public_answer_trace_projection(...)`. Public import identity,
  removed mixin-attribute absence, pycompile/fresh import, DAG, and diff check
  passed. No selected span moved a reviewed runtime-domain record; the count
  remains 217.
- Exactly eleven source/test files changed. Source is `+181/-184`, net `-3`:
  planning moved from 2,356 to 2,180 physical lines, aggregate projection from
  3,180 to 3,350, calculation from 14,716 to 14,718, and the main graph from 936
  to 937. Tests are `+1,143/-41`, net `+1,102`; the whole commit is
  `+1,324/-225`, net `+1,099`. Exactly seven new unittest methods moved full
  discovery from 1,764 to 1,771.
- The committed source-only diff SHA-256 is
  `0cb0b708ee672f115f0a06eea62217f598e87d1a194f6422d422ba126bb51f7b`.
  Final validation passed focused 7/7, aggregate-subtask owner 118/118, affected
  seven-module semantic 780/780, import-side-effects 19/19, semantic/import union
  799/799, runtime audit 217, full discovery 1,771/1,771, pycompile/fresh import,
  DAG/body/caller parity, and `git diff --check`. Benchmark refresh was **NOT
  RUN**, and no remote CI run is claimed or verified for this local branch.

This milestone changes only deterministic projection/upsert ownership. State and
task capture, projection filtering, broader nested promotion, recovery/alignment/
synchronization, mutable state/evidence, artifact/ledger mutation, and final
sequencing remain graph-owned. The commit proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is one characterize-first 128-line
nested subtask selection/promotion batch from `financial_graph_planning.py` into
the existing `financial_answer_projection.py` owner. Public
`nested_subtask_rows(...)` and
`promote_nested_subtask_result_if_more_specific(...)` plus owner-private
operation-family and specificity helpers project to 126 owner lines. Six calls
finish as two graph-external and four owner-local. Planning and calculation
already import answer projection and the owner reaches neither mixin, so this
route is acyclic; the previously rejected aggregate-owner route remains
forbidden. State/task/evidence capture, dependency-coherence replacement,
projection sync/rebuild, artifact/ledger mutation, and final sequencing remain
hard stops. Exact APIs, the six-method CURRENT-SOURCE gate, projected validation
counts, DAG, and rejected state/callback/carrier/cycle expansions are maintained
only in [Project Status Next Work](../overview/project_status.md#next-work).

### Nested subtask selection/promotion owner milestone

- `a8ad25f` moves `_nested_subtask_rows(...)`,
  `_subtask_row_operation_family(...)`, `_subtask_row_specificity_score(...)`,
  and `_promote_nested_subtask_result_if_more_specific(...)` out of
  `FinancialAgentPlanningMixin`. They become public
  `nested_subtask_rows(...)`, owner-private
  `_subtask_row_operation_family(...)`, owner-private
  `_subtask_row_specificity_score(...)`, and public
  `promote_nested_subtask_result_if_more_specific(...)` in
  `financial_answer_projection.py`. The former 20 + 19 + 38 + 51 = 128
  definition-span lines become 20 + 19 + 37 + 50 = 126 owner lines.
- Six selected calls finish as two graph-external and four owner-local. The
  planning caller adopts promoted answer/status/result before later synthesis;
  the calculation caller delegates prepared nested-row traversal before its
  separate dependency-coherence replacement. Retired planning definitions and
  selected mixin-qualified refs are zero; no wrapper, compatibility alias,
  callback, carrier, reason, flag, or output field remains.
- Literal body parity passed for all four definitions after only `self` removal
  and owner-local name rebinding. Complete caller parity passed for
  `_capture_current_subtask_result(...)` and
  `_promote_stronger_nested_aggregate_results(...)`. Public import identity,
  removed mixin-attribute absence, pycompile/fresh import, DAG, and diff check
  passed. No selected span moved a reviewed runtime-domain record; the count
  remains 217.
- Exactly six source/test files changed. Source is `+138/-135`, net `+3`:
  answer projection moved from 491 to 625 physical lines, planning from 2,180
  to 2,048, and calculation from 14,718 to 14,719. Tests are `+673/-23`, net
  `+650`; the whole commit is `+811/-158`, net `+653`. Exactly six new unittest
  methods moved full discovery from 1,771 to 1,777.
- The committed source-only diff SHA-256 is
  `ce62390b757ff986fe704f40fce1e690a6473819890d1725a5aec5e82850687b`.
  Final validation passed focused 6/6, answer-projection owner 23/23, affected
  six-module semantic 770/770, import-side-effects 19/19, semantic/import union
  789/789, runtime audit 217, full discovery 1,777/1,777, pycompile/fresh import,
  DAG/body/caller parity, and `git diff --check`. Benchmark refresh was **NOT
  RUN**, and no remote CI run is claimed or verified for this local branch.

This milestone changes only deterministic nested selection/promotion ownership.
Task/state/evidence capture, dependency-coherence row replacement, projection
alignment/rebuild, mutable state/evidence, artifact/ledger mutation, and final
sequencing remain graph-owned. The commit proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is two sequential
characterize-first aggregate-result seams from
`financial_graph_calculation.py` into the existing
`financial_aggregate_projection.py` owner. Public
`promote_stronger_nested_aggregate_results(...)` moves 64 old lines to 63 owner
lines, then public `sync_aggregate_arithmetic_subtask_surfaces(...)` moves 124
old lines to 123 owner lines. The 188-line batch projects to 186 owner lines;
all four selected calls remain graph-external. The owner already holds all
dependencies except `nested_subtask_rows(...)` on its existing answer-projection
edge and has no path back to calculation. Only these two state-free prepared-row
transforms supersede the prior broad sync hard stop. Alignment, rebuild, graph
state/evidence, artifact/ledger mutation, and final sequencing stay graph-owned.
Exact APIs, the two six-method CURRENT-SOURCE gates, projected validation
counts, dead-import list, DAG, and rejected cycle/callback/state expansions are
maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Aggregate result replacement/surface synchronization owner milestone

- `8e840b8` moves `_promote_stronger_nested_aggregate_results(...)` out of
  `FinancialAgentCalculationMixin` as public
  `promote_stronger_nested_aggregate_results(...)` in
  `financial_aggregate_projection.py`. The former 64-line definition becomes
  63 owner lines. Its three callers remain graph-external, and all owner helper
  dependencies are direct local names. Source is `+70/-72`, tests are
  `+824/-111`, and the whole commit is `+894/-183`. Six new unittest methods
  moved discovery from 1,777 to 1,783.
- `b5d97ee` moves `_sync_aggregate_arithmetic_subtask_surfaces(...)` out of the
  same mixin as public `sync_aggregate_arithmetic_subtask_surfaces(...)` in the
  aggregate owner. The former 124-line definition becomes 123 owner lines. Its
  sole `_aggregate_calculation_subtasks(...)` caller retains exact positional
  arguments and adopts both returned values at the same point. Source is
  `+127/-132`, tests are `+747/-75`, and the whole commit is `+874/-207`. Six
  new unittest methods moved discovery from 1,783 to 1,789.
- Literal body parity passed for both seams after only `self` removal and
  owner-local name rebinding. Complete caller parity passed for all four callers.
  The arithmetic move also removes the six graph imports used only by the old
  body. Public import identity, removed mixin attributes, pycompile/fresh import,
  DAG, runtime audit, and diff check passed; retired private refs are zero.
- Across `6ed195e..b5d97ee`, source is `+197/-204`, net `-7`; tests are
  `+1,569/-184`, net `+1,385`; and the whole range is `+1,766/-388`, net
  `+1,378`. Calculation moved from 14,719 to 14,521 physical lines and aggregate
  projection from 3,350 to 3,541. The selected old spans total 188 lines, the
  two public owner spans total 186, and all four calls remain graph-external.
  The range source diff SHA-256 is
  `ee76d6ffa2c0e1f14e8dec7630a6f11e5f39ad4323e1ed5a23f07e6d0fbda1f8`.
- Final validation passed focused 12/12, aggregate owner 76/76, affected
  seven-module semantic 798/798, import-side-effects 19/19, runtime audit 217,
  full discovery 1,789/1,789, pycompile/fresh import, DAG/body/caller parity,
  and `git diff --check`. Benchmark refresh was **NOT RUN**, and no remote CI
  run is claimed or verified for this local branch.

This milestone changes only deterministic prepared-row ownership. Dependency
alignment, projection rebuild, candidate/state/evidence orchestration,
artifact/ledger mutation, and final sequencing remain graph-owned. It proves no
behavior, accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is one characterize-first 53-line
duplicate growth-prior operand recovery seam from calculation into the existing
aggregate owner. Public `recover_duplicate_growth_prior_operand(...)` projects
to 52 owner lines and retains one graph-external call in
`_prepare_calculation_candidate(...)`. The owner already holds normalization
and growth material/evidence recovery dependencies, so no new edge or cycle is
introduced. Candidate preparation, direct evidence selection, unit/period
alignment, execution, state/evidence, rebuild, artifact/ledger mutation, and
final sequencing remain hard stops. Exact API, four-method CURRENT-SOURCE gate,
projected validation counts, DAG, and rejected cycle/callback/state expansions
are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Duplicate growth-prior recovery owner milestone

- `b3bb764` moves the former 53-line
  `_recover_duplicate_growth_prior_operand(...)` definition out of
  `FinancialAgentCalculationMixin` as public
  `recover_duplicate_growth_prior_operand(...)` in
  `financial_aggregate_projection.py`. The owner definition is 52 lines after
  removing only `self`. Its sole `_prepare_calculation_candidate(...)` call
  remains graph-external with the same two positional arguments after growth
  unit alignment and before the period-conflict check.
- Literal body parity and complete caller parity passed. The old mixin
  definition and source/test private refs are zero, public import identity is
  live, and the aggregate owner contains 73 public and 11 private top-level
  functions. The move adds no import edge or reviewed runtime-domain record.
- Source is `+56/-55`, net `+1`; tests are `+629/-26`, net `+603`; the whole
  commit is `+685/-81`, net `+604`. Calculation moved from 14,521 to 14,468
  physical lines and aggregate projection from 3,541 to 3,595. Four new test
  methods moved discovery from 1,789 to 1,793. The source diff SHA-256 is
  `1a02ec371d28b6012b064281260ad3b274bc9f1ef0b330d0724c36d545b56d1a`.
- Final validation passed focused 4/4, aggregate owner 80/80, affected
  eight-module semantic 838/838, import-side-effects 19/19, semantic/import
  union 857/857, runtime audit 217, full discovery 1,793/1,793,
  pycompile/fresh import, DAG/body/caller parity, retired-ref zero, and
  `git diff --check`. Benchmark refresh was **NOT RUN**, and no remote CI run is
  claimed or verified for this local branch.

This milestone changes only duplicate-prior recovery ownership. Candidate
construction, direct evidence selection, unit/period alignment, calculation
execution, state/evidence, projection rebuild, artifact/ledger mutation, and
final sequencing remain graph-owned. It proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is one characterize-first 48-line
final aggregate evidence/provenance projection seam from calculation into the
same aggregate owner. Public
`filter_final_aggregate_evidence_and_projection(...)` projects to 47 owner
lines and retains two graph-external calls in
`_aggregate_calculation_subtasks(...)`. Its evidence filter, provenance filter,
input carrier, and final-answer surface-operand append dependencies are already
owner-local, so no new edge or cycle is introduced. Evidence preparation,
stale-repair orchestration, mutable state synchronization, runtime-ratio repair,
answer composition, artifact/ledger mutation, and final sequencing remain hard
stops. Exact API, four-method CURRENT-SOURCE gate, projected validation counts,
DAG, and rejected state/cycle/callback expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Final aggregate evidence/provenance projection owner milestone

- `d31e67a` moves the former 48-line
  `_filter_final_aggregate_evidence_and_projection(...)` definition out of
  `FinancialAgentCalculationMixin` as public
  `filter_final_aggregate_evidence_and_projection(...)` in
  `financial_aggregate_projection.py`. The owner definition is 47 lines after
  removing only `self`. Both `_aggregate_calculation_subtasks(...)` calls remain
  graph-external with their original positional and keyword arguments.
- Literal body parity and complete aggregate-caller parity passed. The old
  mixin definition and source/test private refs are zero, public import identity
  is live, and the aggregate owner contains 74 public and 11 private top-level
  functions. The move adds no import edge or reviewed runtime-domain record.
- Source is `+52/-53`, net `-1`; tests are `+646/-41`, net `+605`; the whole
  commit is `+698/-94`, net `+604`. Calculation moved from 14,468 to 14,418
  physical lines and aggregate projection from 3,595 to 3,644. Four new test
  methods moved discovery from 1,793 to 1,797. The source diff SHA-256 is
  `f10c327aca0fb5a4a885892354bef1b840caaf224a9696ae113c9d650df45df1`.
- Final validation passed focused 4/4, aggregate owner 84/84, affected
  seven-module semantic 806/806, import-side-effects 19/19, semantic/import
  union 825/825, runtime audit 217, full discovery 1,797/1,797,
  pycompile/fresh import, DAG/body/caller parity, retired-ref zero, and
  `git diff --check`. Benchmark refresh was **NOT RUN**, and no remote CI run is
  claimed or verified for this local branch.

This milestone changes only final evidence/provenance projection ownership.
Evidence preparation, stale/runtime-ratio repair, mutable state synchronization,
answer composition, artifact/ledger mutation, and final sequencing remain
graph-owned. It proves no behavior, accuracy, ranking, performance, total-code
or executed-path reduction, benchmark improvement, schedule, ledger completion,
or Phase 3 completion.

At this handoff, the sole selected follow-on is one characterize-first 310-line
collapsed-ratio trace-repair seam from calculation into the existing runtime
trace owner. Public `repair_collapsed_ratio_trace_from_evidence(state, trace)`
projects to 309 owner lines and retains two graph-external calls in
`financial_graph.py`. The owner already holds operand overlay and normalization;
the added rendering, numeric-surface, text-surface, and policy imports are
acyclic. Public-answer orchestration, period repair, retrieval/canonical
evidence construction, mutable state/evidence, artifact/ledger mutation, and final
sequencing remain hard stops. Exact API, six-method CURRENT-SOURCE gate,
projected validation counts, DAG, and rejected state/cycle/callback expansions
are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Collapsed-ratio runtime-trace repair owner milestone

- `8861253` moves the former 310-line
  `_repair_collapsed_ratio_trace_from_evidence(...)` definition out of
  `FinancialAgentCalculationMixin` as public
  `repair_collapsed_ratio_trace_from_evidence(state, trace)` in
  `financial_runtime_trace.py`. The owner definition is 309 lines after
  removing only `self`. Both direct calls remain graph-external in
  `financial_graph.py` with their original positional arguments.
- Literal body parity and complete caller parity passed. The old calculation
  definition and source/test private refs are zero, public import identity is
  live, and the runtime-trace owner contains three public and 28 private
  top-level functions. The added rendering, numeric-surface, text-surface,
  graph-state type, and reviewed-policy edges are acyclic. The old calculation
  numeric-span import is deleted; all other touched dependencies remain live.
  The reviewed runtime-domain record count remains 217.
- Source is `+322/-315`, net `+7`; tests are `+1,574/-166`, net `+1,408`; the
  whole commit is `+1,896/-481`, net `+1,415`. Calculation moved from 14,418 to
  14,106 physical lines, main graph from 937 to 938, and runtime trace from
  1,094 to 1,412. Six new test methods moved discovery from 1,797 to 1,803. The
  source diff SHA-256 is
  `a83d1ddaa2167516789bc9de1a90033dd7183d6764ddf0609bf91a777199e451`.
- Final validation passed focused 6/6, aggregate-subtask 124/124, text-surface
  20/20, affected eight-module semantic 832/832, import-side-effects 19/19,
  semantic/import union 851/851, runtime audit 217, full discovery 1,803/1,803,
  pycompile/fresh import, DAG/body/caller parity, retired-ref zero, and
  `git diff --check`. Benchmark refresh was **NOT RUN**, and no remote CI run is
  claimed or verified for this local branch.

This milestone changes only collapsed-ratio evidence-repair ownership.
Public-answer orchestration, period repair, retrieval/canonical evidence
construction, mutable state/evidence, artifact/ledger mutation, and final
sequencing remain graph-owned. It proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is a sequential two-seam direct
structured-evidence batch from calculation into `financial_lookup_recovery.py`.
The former 81-line direct lookup-row projection becomes one 80-line public
function with four graph-external calls. After that seam freezes, the former
139-line direct operand-value coercion becomes one 138-line public function
with one graph-external call. The destination moves from public/private 9/7 to
11/7; the final selected call distribution is external five/local zero.
Evidence-pool selection/scoring, state/report scope, table-label lookup,
precision refinement, mutable evidence, artifact/ledger mutation, and final
sequencing remain hard stops. Exact APIs, two four-method CURRENT-SOURCE gates,
projected validation counts, DAG, and rejected callback/cycle/state expansions
are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Direct structured-evidence lookup-recovery owner milestone

- `5f9dc5c` moves the former 81-line
  `_lookup_row_from_direct_structured_evidence(...)` and 139-line
  `_coerce_operand_value_from_direct_structured_evidence(...)` definitions out
  of `FinancialAgentCalculationMixin` as public 80-line
  `lookup_row_from_direct_structured_evidence(...)` and 138-line
  `coerce_operand_value_from_direct_structured_evidence(...)` in
  `financial_lookup_recovery.py`. All five selected calls remain direct,
  graph-external, and outside `try` blocks.
- Literal body parity and full caller parity passed. The old mixin definitions
  and source/test private refs are zero, public import identity is live, and the
  lookup owner contains 11 public and seven private top-level functions. The
  move adds only acyclic helper edges. The newly dead calculation
  `_structured_cell_period_text` import was removed; all other touched imports
  remain live, and the reviewed runtime-domain count stays 217.
- Source is `+241/-229`, net `+12`; tests are `+1,229/-8`, net `+1,221`;
  the whole commit is `+1,470/-237`, net `+1,233`. Calculation moved from
  14,106 to 13,887 physical lines and lookup recovery from 557 to 788. Eight
  new test methods moved discovery from 1,803 to 1,811. The source diff SHA-256
  is `c4b9c78f90715b4332b559159220e00e6f00d46d2912a4f982cdbabaf0fd271e`.
- Final validation passed focused 4/4 per seam and combined 8/8, lookup owner
  24/24, migrated operation contracts 4/4, affected seven-module semantic
  818/818, import-side-effects 19/19, semantic/import union 837/837, runtime
  audit 217, full discovery 1,811/1,811, pycompile/fresh import,
  DAG/body/caller parity, retired-ref zero, and `git diff --check`. Benchmark
  refresh was **NOT RUN**, and no remote CI run is claimed or verified for this
  local branch.

This milestone changes only direct structured-evidence projection ownership.
Evidence-pool selection/scoring, state/report scope, table-label lookup,
precision refinement, mutable evidence, artifact/ledger mutation, and final
sequencing remain graph-owned. It proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is one characterize-first 62-line
own-evidence lookup-unit alignment seam from calculation into the existing
aggregate owner. Public
`align_lookup_result_units_from_own_evidence(ordered_results, evidence_items)`
projects to 61 owner lines and retains two graph-external calls. Existing
aggregate-to-operand and aggregate-to-dependency edges provide every moved
dependency, so no module edge or reviewed runtime-domain record is added. The
graph's `lookup_primary_slot` and `replace_lookup_primary_slot` imports retire;
the peer-source wrapper remains graph-owned because it binds the dynamic
operation-family callback. Evidence preparation, dedupe/rebuild, dependency
alignment, mutable state/evidence, artifact/ledger mutation, and final
sequencing remain hard stops. Exact API, four-method CURRENT-SOURCE gate,
projected validation counts, DAG/dead-import consequence, and rejected
cycle/callback/state expansions are maintained only
in [Project Status Next Work](../overview/project_status.md#next-work).

### Own-evidence lookup-unit alignment owner milestone

- `a476dd9` moves the former 62-line
  `_align_lookup_result_units_from_own_evidence(...)` definition out of
  `FinancialAgentCalculationMixin` as public 61-line
  `align_lookup_result_units_from_own_evidence(...)` in
  `financial_aggregate_projection.py`. Both selected calls remain direct,
  graph-external, positional, and outside `try` blocks.
- Literal body parity and both full-caller parity checks passed. The old mixin
  definition and source/test private refs are zero, public import identity is
  live, and the aggregate owner contains 75 public and 11 private top-level
  functions. The move adds no module edge. The newly dead calculation
  `lookup_primary_slot` and `replace_lookup_primary_slot` imports were removed;
  all other touched imports remain live, and the reviewed runtime-domain count
  stays 217.
- Source is `+74/-68`, net `+6`; tests are `+786/-13`, net `+773`; the whole
  commit is `+860/-81`, net `+779`. Calculation moved from 13,887 to 13,823
  physical lines and aggregate projection from 3,644 to 3,714. Four new test
  methods moved discovery from 1,811 to 1,815. The source diff SHA-256 is
  `bbe5f3cc62535f3fe8b6d2c2a4a56a27b10d0515cf0fff2083105d34ed171e19`.
- Final validation passed focused 4/4, aggregate owner 88/88, migrated direct
  contract 1/1, affected seven-module semantic 882/882,
  import-side-effects 19/19, semantic/import union 901/901, runtime audit 217,
  full discovery 1,815/1,815, pycompile/fresh import, DAG/body/caller parity,
  retired-ref zero, and `git diff --check`. Benchmark refresh was **NOT RUN**,
  and no remote CI run is claimed or verified for this local branch.

This milestone changes only own-evidence lookup-unit projection ownership.
Peer-source callback alignment, evidence preparation, dedupe/rebuild,
dependency alignment, mutable state/evidence, artifact/ledger mutation, and
final sequencing remain graph-owned. It proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is one-owner, two sequential
characterize-first deterministic-plan seams into
`financial_calculation_execution.py`. The former 37-line runtime operation-plan
wrapper becomes projected public 36-line
`build_runtime_deterministic_operation_plan(...)` with three graph-external
calls. After it freezes, the former 200-line ontology plan becomes projected
public 196-line
`build_deterministic_ontology_plan(active_subtask, operands, *, metric_key)`
with one graph-external call. The execution owner projects from public/private
11/0 to 13/0. Dynamic metric-family dispatch, deterministic lookup planning,
guard/adoption, LLM planning, state/trace/artifact updates, execution, and final
sequencing stay graph-owned. Exact APIs, four- then five-method CURRENT-SOURCE
gates, projected validation counts, DAG/dead-import/baseline consequences, and
rejected callback/compatibility/carrier/state expansions are maintained only
in [Project Status Next Work](../overview/project_status.md#next-work).

### Deterministic calculation-plan ownership milestone

- `c021d30` moves the former 37-line
  `_build_deterministic_operation_plan(...)` adapter and 200-line
  `_build_deterministic_ontology_plan(...)` out of
  `FinancialAgentCalculationMixin` as public 36-line
  `build_runtime_deterministic_operation_plan(...)` and 195-line
  `build_deterministic_ontology_plan(...)` in
  `financial_calculation_execution.py`. All four selected calls remain direct,
  graph-external, and outside `try` blocks.
- Literal body parity passed for both moves. The three runtime-adapter callers
  and the ontology formula caller are AST-identical after normalizing only the
  selected call expression; static tests separately pin exact arguments,
  active-task copying, dynamic metric-family access, adoption, order, and
  exception stop. The old mixin definitions and executable private call/patch
  refs are zero, fresh imports bind both public functions, and the execution
  owner contains 13 public and zero private top-level functions.
- Source is `+247/-244`, net `+3`; tests are `+1,111/-17`, net `+1,094`;
  the reviewed runtime-domain baseline is `+9/-9`; the whole commit is
  `+1,367/-270`, net `+1,097`. Calculation moved from 13,823 to 13,589
  physical lines and execution from 837 to 1,074. Nine new test methods moved
  discovery from 1,815 to 1,824. The source diff SHA-256 is
  `3d93584b12246297296b01f738fedb55e3b8aa71b7805b5d7003f430bbfd411b`.
- Exactly three reviewed runtime-domain records moved from calculation to the
  execution owner with text, category, and count unchanged; audit total remains
  217. The graph's dead base-plan import retired, while its remaining ontology
  and percent-policy loads stay live. The new owner dependencies are acyclic.
- Final validation passed focused runtime adapter 4/4, ontology planner 5/5,
  combined 9/9, execution owner 45/45, affected seven-module semantic 883/883,
  import-side-effects 19/19, semantic/import union 902/902, runtime audit 217,
  full discovery 1,824/1,824, pycompile/fresh import, DAG/body/caller parity,
  and `git diff --check`. Benchmark refresh was **NOT RUN**, and no remote CI
  run is claimed or verified for this local branch.

This milestone changes only deterministic planning ownership. Dynamic metric-
family selection, deterministic lookup planning, guard/adoption, LLM planning,
state/trace/artifact updates, execution orchestration, and final sequencing
remain graph-owned. It proves no behavior, accuracy, ranking, performance,
total-code or executed-path reduction, benchmark improvement, schedule, ledger
completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is one-owner, two sequential
characterize-first query-focus/text-surface seams into
`financial_text_surface.py`. The former 85-line marker-group and 8-line
flattened-marker definitions become projected public 85-line and 8-line
functions. After that seam freezes, the former 127-line source-visible query-
term preserver becomes projected public 126 lines. Across 220 old definition
lines, public 3 total a projected 219 lines and the 12 selected calls finish
external 10/local 2. All caller modules already import the text owner, so no
agent-module edge is added. One reviewed regex occurrence splits a current
path-qualified count-two record, projecting the reviewed record total from 217
to 218 while literal/category/occurrence count stay unchanged. Retrieval/
reranking, evidence construction, active-policy dispatch, aggregate
orchestration, mutable state/evidence, artifact/ledger work, and final
sequencing remain hard stops. The private stopword class alias has no repository
override, patch, guard, or non-call binding; the reviewed config constant becomes
canonical, and a discovered compatibility caller stops the seam. Exact APIs,
five- then five-method CURRENT-SOURCE
gates, projected validation counts, DAG/dead-alias/baseline consequences, and
rejected compatibility/callback/carrier/state expansions are maintained only
in [Project Status Next Work](../overview/project_status.md#next-work).

### Query-focus and source-visible text ownership milestone

- `6d54b2f` moves the former 85-line `_query_focus_marker_groups(...)`, 8-line
  `_query_focus_markers(...)`, and 127-line
  `_preserve_source_visible_query_terms(...)` definitions into
  `financial_text_surface.py` as public 85-line
  `query_focus_marker_groups(...)`, 8-line `query_focus_markers(...)`, and
  126-line `preserve_source_visible_query_terms(...)`. The 220 old definition-
  span lines become 219 owner lines.
- Twelve selected direct calls finish as ten graph-external and two owner-local:
  marker groups external three/local two, flattened markers external five/local
  zero, and source-visible preservation external two/local zero. The text owner
  is public/private 15/4; retired private definitions, executable call/patch
  refs, and the evidence stopword alias are zero. Literal body and complete
  caller parity, public binding identity, pycompile/fresh import, DAG, and diff
  check passed.
- Source is `+255/-245`, net `+10`; tests are `+1,199/-41`, net `+1,158`;
  the reviewed runtime-domain baseline is `+12/-3`, net `+9`; and the whole
  commit is `+1,466/-289`, net `+1,177`. Calculation moved from 13,589 to
  13,464 physical lines, graph evidence from 4,581 to 4,579, retrieval from
  2,736 to 2,642, and text surface from 411 to 642. Exactly ten new test methods
  moved full discovery from 1,824 to 1,834.
- One reviewed `[가-힣]` occurrence split from a path-qualified retrieval
  count-two record into retrieval and text-owner count-one records. Literal,
  category, and occurrence count are unchanged; reviewed records move from 217
  to 218. The source-only diff SHA-256 is
  `b27abac6c0b25f3e8aa888856ba7017c5b300463c7da4cbe68c7096e401781be`;
  source plus baseline is
  `42ae44c153d6bd8af1396a61ef3f23dad37945c7a94422aee8dc8bb66e080e11`.
- Final validation passed focused Seam A 5/5, Seam B 5/5, combined 10/10,
  text owner 30/30, affected seven-module semantic 808/808, import-side-effects
  19/19, runtime audit 218, full discovery 1,834/1,834, pycompile/fresh import,
  DAG/body/caller parity, retired-ref zero, and `git diff --check`. No semantic/
  import union, benchmark refresh, or remote CI run is claimed for this commit.

This milestone changes only deterministic text-surface ownership over already
supplied query, answer, result, evidence, document, and ontology values.
Retrieval/reranking, document/evidence selection and construction, aggregate
adoption, mutable state/evidence, artifact/ledger mutation, and final sequencing
remain graph-owned. It proves no behavior, accuracy, ranking, performance,
total-code or executed-path reduction, benchmark improvement, schedule, ledger
completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is one characterize-first prepared
structured period-pair seam into `financial_reconciliation_candidates.py`.
The former 202-line `_extract_structured_period_pair_rows(...)` becomes projected
public 201-line `extract_structured_period_pair_rows(...)`; its sole direct
nine-keyword call remains graph-external and outside `try`. The owner projects
from public/private 7/4 to 8/4, adds only existing-direction graph-helper and
row-surface symbols, and moves no reviewed runtime-domain record. Full operand
extraction, candidate collection/selection, LLM rerank, evidence construction,
artifact/retry/state mutation, ledger work, and final sequencing remain hard
stops. Exact behavior, the six-method CURRENT-SOURCE gate, projected validation,
DAG, and rejected cycle/state/callback expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

## Verification At The Stop Line

- Full unittest discovery: 1,350 passed at the Phase 5 stop line.
- Portfolio review gates: READY.
- Expanded structural numeric evidence: 9 / 9 PASS.
- Plain-retrieval diagnostic comparison: 5 / 9 PASS.
- Default import and invocation optional-boundary regressions: passing.
- Published benchmark evidence: 26 compact history-linked files.

These numbers are retained evidence, not a claim that docs-only changes rerun a
paid benchmark. Detailed methodology and run interpretation live in
[experiment_history.md](experiment_history.md) and
[../evaluation/benchmarking.md](../evaluation/benchmarking.md).

## Stop Line

The broad July portfolio-surface simplification is complete. The broader Phase 3
calculation-path convergence remains in progress. Future changes should start
from a concrete runtime regression, evidence-faithfulness problem, reviewer demo
gap, dependency change, or real compatibility caller.

Do not restart broad helper extraction, all-at-once test splitting, MAS feature
growth, cache serving, or fresh benchmark ingest solely to make the repository
look more active. Improve the reviewer path and representative demo before
adding scope.

### Structured period-pair ownership milestone

- `79a460a` moves the former 202-line
  `_extract_structured_period_pair_rows(...)` definition from
  `FinancialAgentReconciliationMixin` to public 201-line
  `extract_structured_period_pair_rows(...)` in
  `financial_reconciliation_candidates.py`. The sole caller remains a direct
  imported-name call outside `try` with the exact nine keywords. Literal body
  and full-caller parity passed after normalizing only the selected call target;
  the retired private definition and executable source/test refs are zero.
- Source is `+207/-204`, net `+3`; tests are `+763/-29`, net `+734`; and the
  whole commit is `+970/-233`, net `+737`. Reconciliation moved from 1,667 to
  1,465 physical lines, the candidate owner from 329 to 534, and the changed
  test files grew by 734 physical lines. Six new unittest methods moved full
  discovery from 1,834 to 1,840. The source diff SHA-256 is
  `8bd82f6adb5e9722771953888dbeef6e129332ae4b749b6483ba46017db7cf3e`.
- The candidate owner is public/private 8/4. Its direct-acceptance and row-
  surface dependencies are existing-direction and acyclic; graph-side imports
  remain live. The selected span contains no reviewed runtime-domain record, so
  the audit remains 218 without a baseline change.
- Final validation passed focused 6/6, candidate owner 14/14, affected seven-
  module semantic 787/787, import-side-effects 19/19, runtime audit 218, full
  discovery 1,840/1,840, pycompile/fresh import, DAG/body/full-caller parity,
  retired-ref zero, and `git diff --check`. No semantic/import union, benchmark
  refresh, or remote CI run is claimed for this commit.

This milestone changes only prepared structured period-pair ownership. Full
operand extraction, candidate collection/selection, LLM reranking, evidence
construction, artifact/retry/state mutation, ledger work, and final sequencing
remain graph-owned. It proves no behavior, accuracy, ranking, performance,
total-code or executed-path reduction, benchmark improvement, schedule, ledger
completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is one characterize-first 273-line
semantic-planner normalization and validation batch from
`financial_graph_planning.py` into `financial_graph_helpers.py`. Eight old
definitions become projected public five plus owner-private three totaling 271
lines. Sixteen direct calls finish external nine/local seven, no new module edge
is added, and no reviewed runtime-domain record moves. The exact seven-method
CURRENT-SOURCE gate, projected validations, behavior contracts, import cleanup,
and rejected evidence/cycle/carrier/state expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work). LLM/model
invocation, query routing, plan adoption, task/state/artifact/ledger mutation,
and final sequencing remain graph-owned.

### Semantic planner normalization and validation ownership milestone

- `fb970a5` moves eight definitions totaling 273 old definition-span lines from
  `financial_graph_planning.py` into `financial_graph_helpers.py`. Public
  `llm_plan_preserves_segment_sum_shape(...)`,
  `llm_plan_preserves_analysis_shape(...)`,
  `apply_segment_labels_to_llm_resolved_specs(...)`,
  `align_scope_hints(...)`, and `validate_concept_planner_task(...)` plus three
  owner-private helpers total 271 owner lines. Sixteen selected calls finish
  graph-external nine and owner-local seven; all remain direct and outside
  `try`. Literal body and full retained-caller parity passed after normalizing
  only the selected call targets; retired private definitions and executable
  source/test refs are zero.
- Source is `+303/-296`, net `+7`; tests are `+1,557/-9`, net `+1,548`; and the
  whole commit is `+1,860/-305`, net `+1,555`. Planning moved from 2,048 to
  1,765 physical lines, graph helpers from 6,269 to 6,559, and the changed test
  files grew by 1,548 physical lines. Seven new unittest methods moved full
  discovery from 1,840 to 1,847. The source diff SHA-256 is
  `9e0310f17edd4ea004425957e8044fc6ae0f79538ab140bd4a9e8007aa4d63cc`.
- The helper owner is public/private 5/132. Its planning-policy and report-scope
  dependencies use existing acyclic edges; the planning module's newly dead
  segment-label and report-receipt imports are removed. The selected spans move
  no reviewed runtime-domain record, so the audit remains 218 without a
  baseline change.
- Final validation passed focused 7/7, helper owner 12/12, affected eight-module
  semantic 434/434, import-side-effects 19/19, runtime audit 218, full discovery
  1,847/1,847, pycompile/fresh import, DAG/body/full-caller parity, retired-ref
  zero, and `git diff --check`. Benchmark refresh was **NOT RUN** and no remote
  CI run is claimed for this local commit.

This milestone changes only semantic-planner normalization and validation
ownership. Model invocation, query routing, plan adoption, mutable task/state/
artifact/ledger work, retrieval/evidence work, and final sequencing remain
graph-owned. It proves no behavior, accuracy, ranking, performance, total-code
or executed-path reduction, benchmark improvement, schedule, ledger completion,
or Phase 3 completion.

At this handoff, the sole selected follow-on is one characterize-first 143-line
narrative-task policy batch from `financial_graph_planning.py` into
`financial_graph_helpers.py`. Six old definitions become public four plus
owner-private two. Thirteen direct calls finish external six/local seven; the
move adds one reviewed acyclic routing edge, moves no runtime-domain baseline
record, and retires ten planning imports. The exact six-method CURRENT-SOURCE
gate, projected validations, behavior contracts, import cleanup, and rejected
evidence/cycle/carrier/state expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work). Model
invocation, logical/execution task projection, plan adoption, mutable task/
state/artifact/ledger work, retrieval/evidence work, and final sequencing
remain graph-owned.

### Narrative-task policy ownership milestone

- `f9244d6` moves six definitions totaling 143 definition-span lines from
  `financial_graph_planning.py` into `financial_graph_helpers.py`. Public
  `build_hybrid_narrative_subtask(...)`,
  `append_hybrid_narrative_task(...)`,
  `push_narrative_tasks_after_numeric(...)`, and
  `exclusive_narrative_task_policy_active(...)` plus two owner-private
  predicates retain the exact 143-line total. Thirteen selected calls finish
  graph-external six and owner-local seven; all remain direct and outside
  `try`. Literal body and full retained-caller parity passed after normalizing
  only the selected call targets; retired private definitions and executable
  source/test refs are zero.
- Source is `+173/-173`, net `0`; tests are `+1,245/-15`, net `+1,230`; and the
  whole commit is `+1,418/-188`, net `+1,230`. Planning moved from 1,765 to
  1,602 physical lines, graph helpers from 6,559 to 6,722, and the changed test
  files grew by 1,230 physical lines. Six new unittest methods moved full
  discovery from 1,847 to 1,853. The source diff SHA-256 is
  `da20f913c7205a1e0694ce655b91b8dad0b1d43437a6099626881716ded176b0`.
- The helper owner is public/private 9/134. Its retrieval-policy, operation-
  policy, and routing dependencies are acyclic; the planning module's ten newly
  dead imports are removed. The selected spans move no reviewed runtime-domain
  record, so the audit remains 218 without a baseline change.
- Final validation passed focused 6/6, helper owner 18/18, affected eight-module
  semantic 440/440, import-side-effects 19/19, runtime audit 218, full discovery
  1,853/1,853, pycompile/fresh import, DAG/body/full-caller parity, retired-ref
  zero, and `git diff --check`. Benchmark refresh was **NOT RUN** and no remote
  CI run is claimed for this local commit.

This milestone changes only narrative-task policy ownership. Model invocation,
logical/execution task projection, query routing, plan adoption, mutable task/
state/artifact/ledger work, retrieval/evidence work, and final sequencing remain
graph-owned. It proves no behavior, accuracy, ranking, performance, total-code
or executed-path reduction, benchmark improvement, schedule, ledger completion,
or Phase 3 completion.

At this handoff, the sole selected follow-on is one characterize-first lookup
answer-slot/support projection batch from `financial_graph_planning.py` into
`financial_lookup_recovery.py`. Ten definitions total 342 definition-span lines
and move with three compiled policy regex bindings. Four functions become
public and six owner-private; 15 direct calls finish external six/local nine,
and the owner projects from public/private 11/7 to 15/13. The exact eight-method
CURRENT-SOURCE gate, projected validations, behavior contracts, import cleanup,
and rejected compatibility/callback/carrier/state expansions are maintained
only in [Project Status Next Work](../overview/project_status.md#next-work).
`_capture_current_subtask_result(...)`, calculation/dependency orchestration,
retrieval/prepared-document pool construction, mutable result/evidence/state,
trace/artifact/ledger work, and final sequencing remain graph-owned.

### Lookup answer-slot/support projection ownership milestone

- `ae1f599` moves ten definitions totaling 342 definition-span lines plus three
  compiled policy regex bindings from `financial_graph_planning.py` into
  `financial_lookup_recovery.py`. Public
  `lookup_operand_matches_active_task(...)`,
  `refine_lookup_slot_unit_from_evidence(...)`,
  `synthesize_lookup_answer_slot_from_prose(...)`, and
  `lookup_slot_supporting_doc_evidence(...)` plus six owner-private money/unit,
  answer-text, and document-surface helpers retain the exact 342-line total.
  Fifteen selected calls finish graph-external six and owner-local nine; all
  remain direct and outside `try`. Literal body and full retained-caller parity
  passed after normalizing only the selected public call targets. Retired graph-
  private definitions and executable source/test refs are zero.
- Source is `+383/-379`, net `+4`; tests are `+1,133/-12`, net `+1,121`; and the
  whole commit is `+1,516/-391`, net `+1,125`. Planning moved from 1,602 to
  1,240 physical lines, lookup recovery from 788 to 1,154, and the changed test
  files grew by 1,121 physical lines. Eight new unittest methods moved full
  discovery from 1,853 to 1,861. The source diff SHA-256 is
  `1556379052fd83f517ac559a7ff0e8fb6908ab675032faede3cb94287c56f397`.
- The lookup owner is public/private 15/13. Its answer-slot, model-loader,
  retrieval-policy, graph-helper, operand, and surface dependencies are
  acyclic; the planning module's three newly dead imports are removed. The
  selected bodies move no reviewed runtime-domain record, so the audit remains
  218 without a baseline change.
- Final validation passed focused 8/8, lookup owner 32/32, affected eight-module
  semantic 864/864, import-side-effects 19/19, runtime audit 218, full discovery
  1,861/1,861, pycompile/fresh import, DAG/body/full-caller parity, retired-ref
  zero, and `git diff --check`. Benchmark refresh was **NOT RUN** and no remote
  CI run is claimed for this local commit.

This milestone changes only lookup projection ownership. Retrieval and prepared-
document pool construction, active task/result/evidence mutation, nested-result
promotion, calculation/dependency orchestration, trace/artifact/ledger work,
and final sequencing remain graph-owned. It proves no behavior, accuracy,
ranking, performance, total-code or executed-path reduction, benchmark
improvement, schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is one characterize-first 117-line
read-only evidence-hint projection batch from `financial_graph_evidence.py`
into `financial_retrieval_hints.py`. Three old private definitions become
public focus-term, preferred-section subset, and compression-guidance functions
totaling 114 owner lines. Their three direct calls remain external; one existing
active-section helper call becomes owner-local. The move adds only acyclic
graph-state/operation-policy symbols, retires one graph import, and moves no
reviewed domain-language occurrence. The exact five-method CURRENT-SOURCE gate,
projected validations, behavior contracts, import cleanup, and rejected prompt-
diagnostic/evidence/state/carrier expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work). Model
invocation, evidence construction/ranking/mutation, state, trace/artifact/
ledger work, and final sequencing remain graph-owned.

### Read-only evidence-hint projection ownership milestone

- `02d1422` moves three definitions totaling 117 old definition-span lines from
  `financial_graph_evidence.py` into `financial_retrieval_hints.py`. Public
  `evidence_extraction_focus_terms(...)`,
  `preferred_section_evidence_subset(...)`, and
  `compression_guidance(...)` total 116 owner lines. All three selected calls
  remain graph-external and outside `try`; the preferred-subset body's active-
  section call becomes owner-local. Literal body and full retained-caller parity
  passed after normalizing only the selected call targets. Retired graph-private
  definitions and executable source/test refs are zero.
- Source is `+134/-125`, net `+9`; tests are `+830/-0`; and the whole commit is
  `+964/-125`, net `+839`. Graph evidence moved from 4,579 to 4,461 physical
  lines, retrieval hints from 167 to 294, and the new test file contains 830
  lines. Five new unittest methods moved full discovery from 1,861 to 1,866 and
  AST-counted methods from 1,831 to 1,836. The source diff SHA-256 is
  `d2925a071c1555658c448d0779168e851304e7602431df8da216904dc60959ec`.
- The retrieval-hint owner is public/private 3/9. Its graph-state and operation-
  policy dependencies are acyclic; the graph's newly dead active-section import
  is removed. The selected spans move no reviewed runtime-domain record, so the
  audit remains 218 without a baseline change.
- Final validation passed focused 5/5, affected seven-module semantic 692/692,
  import-side-effects 19/19, runtime audit 218, full discovery 1,866/1,866,
  pycompile/fresh import, DAG/body/full-caller parity, retired-ref zero, and
  `git diff --check`. Benchmark refresh was **NOT RUN** and no remote CI run is
  claimed for this local commit.

This milestone changes only read-only retrieval-hint ownership. Context and
evidence construction/ranking, prompt/model invocation, mutable state/evidence,
trace/artifact/ledger work, and final sequencing remain graph-owned. It proves
no behavior, accuracy, ranking, performance, total-code or executed-path
reduction, benchmark improvement, schedule, ledger completion, or Phase 3
completion.

At this handoff, the sole selected follow-on is one characterize-first 228-line
deterministic quantitative-impact answer projection batch from
`financial_graph_evidence.py` into `financial_aggregate_projection.py`.
Owner-private labeled-numeric parsing and one public supported-impact composer
project to 226 owner lines. Four calls finish graph-external three and owner-
local one. The aggregate owner adds only two policy constants on an existing
config edge; graph evidence adds one acyclic owner edge and retires those two
local policy imports. The exact five-method CURRENT-SOURCE gate, projected
validations, parser/composer contracts, caller `try` placement, import cleanup,
and rejected entity-table/ratio-assembly/evidence/state/carrier expansions are
maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).
Validation/model fallback, evidence combination and selection, mutable
composition state, trace/artifact/ledger work, and final sequencing remain
graph-owned.

### Quantitative-impact projection ownership milestone

- `7aba7f2` moves the former static 33-line
  `_parse_labeled_numeric_lines(...)` and private 195-line
  `_compose_supported_quantitative_impact_answer(...)` from
  `financial_graph_evidence.py` into `financial_aggregate_projection.py` as an
  owner-private 33-line parser and public 194-line
  `compose_supported_quantitative_impact_answer(...)`. The three composition
  calls remain graph-external and the parser call is owner-local. Literal body
  and full retained-caller parity passed after normalizing only selected call
  targets; retired graph-private definitions and executable source/test refs
  are zero.
- Exactly seven source/test files changed. Source is `+237/-235`, net `+2`:
  aggregate projection is `+232/-0` and moves from 3,714 to 3,946 physical
  lines; graph evidence is `+3/-234` and moves from 4,461 to 4,230; calculation
  is `+2/-1` and moves from 13,464 to 13,465. Tests are `+1,119/-12`, net
  `+1,107`: aggregate rank/dedupe is `+1,105/-5`, aggregate subtask projection
  `+7/-2`, text surface `+5/-1`, and operation contracts `+2/-4`. The whole
  commit is `+1,356/-247`, net `+1,109`. Five AST-counted methods moved full
  discovery from 1,866 to 1,871.
- The aggregate owner is public/private 76/12. Both selected policy constants
  moved onto its existing retrieval-policy edge; graph evidence's two newly
  dead imports were removed. The selected spans move no reviewed runtime-domain
  record, so the audit remains 218 without a baseline change. The frozen source
  diff SHA-256 is
  `7c267108053b986aff1eb6ddae9b6d51514a42ad7749e94b4fa96849c5439972`.
- Final validation passed focused 5/5, aggregate owner 93/93, affected six-
  module semantic 812/812, import-side-effects 19/19, runtime audit 218, full
  discovery 1,871/1,871, pycompile/fresh import, DAG/body/full-caller parity,
  retired-ref zero, and `git diff --check`. Benchmark refresh was **NOT RUN**,
  and no remote CI run is claimed or verified for this local branch.

This milestone changes only deterministic quantitative-impact parser/composer
ownership. Validation/model fallback, evidence combination/selection, mutable
composition state, trace/artifact/ledger work, and final sequencing remain
graph-owned. It proves no behavior, accuracy, ranking, performance, total-code
or executed-path reduction, benchmark improvement, schedule, ledger completion,
or Phase 3 completion.

At this handoff, the sole selected follow-on is a sequential two-seam 285-line
batch from `financial_graph_helpers.py`. Seam A moves 29-line target-year and
11-line period-focus policy to two public functions in
`financial_scope_policies.py`; Seam B moves 42/84-line structured-cell selectors,
a 53-line owner-private affinity helper, and a 66-line public score helper to
`financial_structured_cells.py`. Five public functions plus one owner-private
helper finish 57 selected calls at external 53/local four. Candidate/evidence
construction and adoption, existing direct structured lookup/value projection,
reconciliation orchestration, mutable state/evidence, callbacks, carriers,
trace/artifact/ledger work, and final sequencing remain hard stops. Exact APIs,
dependencies, sequential four- and six-method characterization gates, and
rejected expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Operand-period and structured-cell ownership milestone

- `4cdbf93` moves the former 29-line `_operand_target_years(...)` and 11-line
  `_operand_period_focus(...)` graph-helper definitions into
  `financial_scope_policies.py` as public `operand_target_years(...)` and
  `operand_period_focus(...)`. Their 38 calls finish external 37/owner-local
  one. Source is `+95/-89`, tests `+717/-24`, and the whole commit `+812/-113`.
- `6d6ce2a` moves the former 42-line `_select_structured_cell(...)`, 84-line
  `_select_aggregate_structured_cell(...)`, 53-line
  `_structured_cell_operand_affinity(...)`, and 66-line
  `_score_structured_cell(...)` definitions into
  `financial_structured_cells.py` as public `select_structured_cell(...)`,
  `select_aggregate_structured_cell(...)`, and `score_structured_cell(...)`
  plus owner-private affinity. Its 19 calls finish external 16/owner-local
  three. Source is `+297/-284`, tests `+1,373/-29`, and the whole commit is
  `+1,670/-313`.
- The authoritative `9fe1a45..6d6ce2a` range, after later test/import rewrites
  cancel, changes source `+390/-371`, tests `+2,086/-49`, and the whole range
  `+2,476/-420`. Physical changed-source lines move from 31,228 to 31,247:
  graph helpers 6,722 to 6,429, scope policy 168 to 215, and structured cells
  73 to 335. Changed tests move from 25,434 to 27,471. Ten AST-counted methods
  move discovery from 1,871 to 1,881. The range source diff SHA-256 is
  `a8d384543529aa1c3ac9b976c0a46cbde23792fb245e2f9993a51d69e51524d7`.
- Literal body parity passed for all six moved definitions after normalizing
  selected public names. All 191 retained source callers/classes across graph
  helpers, calculation, evidence, reconciliation, lookup recovery, and
  reconciliation candidates are AST-identical after the same normalization.
  The final public/private destination surfaces are scope 3/7 and structured
  cells 3/4. The 57 selected calls finish external 53/local four, retired
  private source/test refs are zero, dependency edges are acyclic, the graph's
  dead fiscal-ordinal import is removed, and runtime-domain records remain 218.
- Validation passed Seam A focused 4/4 and affected 385/385, Seam B focused
  6/6, combined focused 10/10, affected eight-module semantic 838/838,
  import-side-effects 19/19, runtime audit 218, full discovery 1,881/1,881,
  pycompile/fresh import, DAG/body/full-caller parity, retired-ref zero, and
  `git diff --check`. Benchmark refresh was **NOT RUN** and no remote CI run is
  claimed or verified for these local commits.

This milestone changes only ownership. Candidate/evidence construction and
adoption, direct structured lookup/value projection, reconciliation
orchestration, mutable state/evidence, callbacks, carriers, trace/artifact/
ledger work, and final sequencing remain graph-owned. It proves no behavior,
accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is a characterize-first 228-line
candidate report/period-scope batch from `financial_graph_helpers.py` into
`financial_scope_policies.py`. Exact 31/39/46/49/27/36-line definitions become
public four plus owner-private two; their 18 calls finish external 10/local
eight. The destination adds no module edge and only two constants on its
existing config edge. Broad operand scoring, deterministic reconciliation,
candidate/evidence construction/adoption, mutable state, callbacks, carriers,
trace/artifact/ledger work, and final sequencing remain hard stops. Exact APIs,
behavior, six-method CURRENT-SOURCE gate, dependencies, dead imports, projected
validation, and rejected expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Candidate report/period-scope policy ownership milestone

- `ba35519` moves the former 31-line `_operand_target_receipts(...)`, 39-line
  `_candidate_allows_comparative_report_scope_fallback(...)`, 46-line
  `_candidate_matches_target_report_scope(...)`, 49-line
  `_candidate_report_scope_binding_bonus(...)`, 27-line
  `_candidate_matches_operand_target_year(...)`, and 36-line
  `_candidate_explicit_years(...)` definitions from
  `financial_graph_helpers.py` into `financial_scope_policies.py`. Public
  `candidate_matches_target_report_scope(...)`,
  `candidate_report_scope_binding_bonus(...)`,
  `candidate_matches_operand_target_year(...)`, and
  `candidate_explicit_years(...)` plus owner-private receipt and comparative-
  fallback helpers preserve the exact 228-line total. The 18 direct calls finish
  graph-external 10/owner-local eight; retired graph-private source/test refs are
  zero.
- Exactly four source/test files changed. Source is `+257/-253`, net `+4`:
  graph helpers are `+14/-252` and move from 6,429 to 6,191 physical lines;
  scope policy is `+243/-1` and moves from 215 to 457. Tests are `+1,416/-16`,
  net `+1,400`: graph-helper tests are `+1,406/-8` and operation contracts
  `+10/-8`. The whole commit is `+1,673/-269`, net `+1,404`; changed source
  moves from 6,644 to 6,648 physical lines and changed tests from 16,422 to
  17,822. Six AST-counted methods move discovery from 1,881 to 1,887. The
  source diff SHA-256 is
  `853f3a95a4ef0bf8aa5e4900b62d04deef48b1dd6fb58278d75a7b550c61dc01`.
- Literal body parity passes for all six moved definitions, and all 131 retained
  graph-helper functions pass full AST parity after normalizing only selected
  call targets. The scope owner finishes public/private 7/9. The graph's newly
  dead `_report_scope_source_reports` and
  `STRUCTURED_CELL_PERIOD_SCORING_POLICY` imports are removed;
  `PERIOD_FOCUS_POLICY` remains live. Dependency edges stay acyclic, the moved
  spans contain no reviewed runtime-domain occurrence, and the audit remains
  218 without a baseline change.
- Validation passes focused 6/6, affected eight-module semantic 844/844,
  import-side-effects 19/19, runtime audit 218, full discovery 1,887/1,887,
  pycompile/fresh import, DAG/body/full-caller parity, retired-ref zero, and
  `git diff --check`. Benchmark refresh was **NOT RUN**, and no remote CI run is
  claimed or verified for this local branch.

This milestone changes only candidate report/period-scope ownership. Candidate
and evidence construction/adoption, broad scoring/reconciliation, mutable
state/evidence, callbacks, carriers, trace/artifact/ledger work, and final
sequencing remain graph-owned. It proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

At this handoff, the sole selected follow-on is a characterize-first 128-line
candidate surface-contract/segment-binding batch from
`financial_graph_helpers.py` into `financial_surface_contracts.py`. Exact
25/15/20/23/12/33-line definitions become public five plus owner-private
segment-surface assembly. Their 17 calls, including reconciliation's descriptor
call, finish external 15/local two. The destination adds only `Optional` typing
and no module edge. Segment metric-combination support remains graph-owned
because moving its row-surface dependency would form a reverse cycle; concept-
conflict policy remains separate because it owns a distinct concept-specific
contract. Direct/ratio acceptance, broad scoring/reconciliation, candidate/
evidence construction and adoption, mutable state/evidence, callbacks,
carriers, trace/artifact/ledger work, and final sequencing remain hard stops.
Exact APIs, behavior, the six-method CURRENT-SOURCE gate, dependencies,
projected validation, and rejected expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Candidate surface-contract/segment-binding ownership milestone

- `3ca0144` moves the former 25-line
  `_candidate_has_required_surface_contract(...)`, 15-line
  `_candidate_has_numeric_value_signal(...)`, 20-line
  `_candidate_is_descriptor_row(...)`, 23-line
  `_candidate_segment_surfaces(...)`, 12-line
  `_candidate_matches_segment_binding(...)`, and 33-line
  `_candidate_segment_binding_bonus(...)` definitions from
  `financial_graph_helpers.py` into `financial_surface_contracts.py`. Public
  `candidate_has_required_surface_contract(...)`,
  `candidate_has_numeric_value_signal(...)`, `candidate_is_descriptor_row(...)`,
  `candidate_matches_segment_binding(...)`, and
  `candidate_segment_binding_bonus(...)` plus owner-private segment-surface
  assembly preserve the exact 128-line total. The 17 direct calls finish graph/
  reconciliation-external 15 and owner-local two; retired graph-private source/
  test refs are zero.
- Exactly four source/test files changed. Source is `+162/-158`, net `+4`:
  graph helpers are `+19/-154` and move from 6,191 to 6,056 physical lines;
  reconciliation is `+2/-3` and moves from 1,467 to 1,466; surface contracts
  are `+141/-1` and move from 69 to 209. Tests are `+781/-7`, net `+774`, all
  in graph-helper tests. The whole commit is `+943/-165`, net `+778`; changed
  source moves from 7,727 to 7,731 physical lines and the changed test from
  6,264 to 7,038. Six AST-counted methods move discovery from 1,887 to 1,893.
  The source diff SHA-256 is
  `cdd2ced140b9add6bd549e839514038dacede28700ebd25854b7fb6c3e9e1702`.
- Literal body parity passes for all six moved definitions, all 125 retained
  graph-helper functions pass full AST parity after normalizing only selected
  call targets, and the reconciliation class is likewise unchanged modulo the
  descriptor call target. The surface owner finishes public/private 5/7 and
  graph helpers 9/116. Dependency edges remain acyclic, selected spans contain
  no reviewed runtime-domain occurrence, and the audit remains 218 without a
  baseline change.
- Validation passes focused 6/6, graph-helper and surface-owner 41/41, affected
  nine-module semantic 851/851, import-side-effects 19/19, runtime audit 218,
  full discovery 1,893/1,893, pycompile/fresh import, DAG/body/full-caller
  parity, retired-ref zero, and `git diff --check`. Benchmark refresh was
  **NOT RUN**, and no remote CI run is claimed or verified for this local
  branch.

This milestone changes only candidate surface-contract and segment-binding
ownership. Candidate/evidence construction/adoption, direct/ratio acceptance,
broad scoring/reconciliation, mutable state/evidence, callbacks, carriers,
trace/artifact/ledger work, and final sequencing remain graph-owned. It proves
no behavior, accuracy, ranking, performance, total-code or executed-path
reduction, benchmark improvement, schedule, ledger completion, or Phase 3
completion.

At this handoff, the sole selected follow-on is a characterize-first 116-line
candidate metadata-policy projection batch from `financial_graph_helpers.py`
into `financial_surface_contracts.py`. Exact 12/26/38/40-line local aggregate-
context, consolidation-scope, binding-policy shape, and selected-unit-family
definitions become public four. Their eight calls remain external eight/local
zero. The destination adds consolidation policy, operand-value normalization,
and percent-label inference on existing or one-way edges; selected spans contain
no baseline record. Aggregate row-role/stage inference remains graph-owned to
avoid low-level public sprawl, and segment metric-combination remains graph-
owned because its row-surface dependency would form a reverse cycle. Direct/
ratio acceptance, broad scoring/reconciliation, candidate/evidence construction
and adoption, mutable state/evidence, callbacks, carriers, trace/artifact/ledger
work, and final sequencing remain hard stops. Exact APIs, behavior, the six-
method CURRENT-SOURCE gate, dependencies, projected validation, and rejected
expansions are maintained only in
[Project Status Next Work](../overview/project_status.md#next-work).

### Candidate metadata-policy ownership milestone

- `a904f28` moves the former 12-line
  `_candidate_local_aggregate_context(...)`, 26-line
  `_candidate_consolidation_scope(...)`, 38-line
  `_binding_policy_allows_candidate_shape(...)`, and 40-line
  `_candidate_selected_unit_family(...)` definitions from
  `financial_graph_helpers.py` into `financial_surface_contracts.py` as public
  `candidate_local_aggregate_context(...)`,
  `candidate_consolidation_scope(...)`,
  `binding_policy_allows_candidate_shape(...)`, and
  `candidate_selected_unit_family(...)`. The exact 116-line definition-span
  total is preserved. Their eight direct `ast.Name` calls remain graph-external
  3/2/2/1 and owner-local zero, all outside `try`; retired graph-private source/
  test refs are zero.
- Exactly three source/test files changed. Source is `+139/-134`, net `+5`:
  graph helpers are `+12/-132` and move from 6,056 to 5,936 physical lines;
  surface contracts are `+127/-2` and move from 209 to 334. Tests are
  `+1,116/-9`, net `+1,107`, all in graph-helper tests. The whole commit is
  `+1,255/-143`, net `+1,112`; changed source moves from 6,265 to 6,270 physical
  lines and the changed test from 7,038 to 8,145. Six AST-counted methods move
  discovery from 1,893 to 1,899. The source diff SHA-256 is
  `0e62e924b473c256d505164160b8e00419a8be0c022c7b3d036da0465bafcae7`.
- Literal body parity passes for all four moved definitions and all 121 retained
  graph-helper functions pass full AST parity after normalizing only selected
  call targets. The surface owner finishes public/private 9/7 and graph helpers
  9/112. The destination adds the existing consolidation-policy, operand-value-
  normalization, and percent-label-inference dependencies on one-way acyclic
  edges. The moved spans contain no reviewed runtime-domain occurrence, so the
  audit remains 218 without a baseline change.
- Validation passes focused 6/6, graph-helper and surface-owner 47/47, affected
  nine-module semantic 857/857, import-side-effects 19/19, runtime audit 218,
  full discovery 1,899/1,899, pycompile/fresh import, DAG/body/full-caller
  parity, retired-ref zero, and `git diff --check`. Benchmark refresh was
  **NOT RUN**, and no remote CI run is claimed or verified for this local
  branch.

This milestone changes only candidate metadata-policy ownership. Candidate/
evidence construction and adoption, direct/ratio acceptance, broad scoring/
reconciliation, mutable state/evidence, callbacks, carriers, trace/artifact/
ledger work, and final sequencing remain graph-owned. It proves no behavior,
accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, ledger completion, or Phase 3 completion.

At this handoff, no next production owner move is selected. The sole next work
is the characterize-only residual dependency/ratio candidate inventory in
[Project Status Next Work](../overview/project_status.md#next-work). It must
freeze exact callers, dependencies, cycle boundaries, behavior, and projected
gates before proposing one bounded state-free move or recording that no safe
move is currently available.

### Residual dependency/ratio candidate characterization checkpoint

- A docs-only inventory classified the remaining graph-owned candidate seam.
  Exact definition spans are segment local/metric 7/15 lines, aggregate row-
  stage/role and candidate value-role/stage 10/2/16/18, direct grounding/direct
  acceptance/ratio acceptance 86/161/68, and operand matching/direct strength/
  broad scoring 83/122/315. Their direct source-call counts are respectively
  1/2, 4/2/11/11, 3/5/3, and 3/8/7; every caller is outside `try`. Body `try`
  counts are zero except direct acceptance one and broad scoring two.
- Direct policy loads are absent for the selected pair. The aggregate group
  reaches `STRUCTURED_CELL_AFFINITY_POLICY`; direct acceptance reaches
  `OPERAND_CANDIDATE_SCORING_POLICY` and `PERIOD_FOCUS_POLICY`; broad scoring
  reaches `CONSOLIDATION_SCOPE_POLICY` and
  `OPERAND_CANDIDATE_SCORING_POLICY`. Current test-method reference counts and
  exact signatures are recorded in Project Status Next Work.
- The selected follow-on is only the 22-line segment pair, renamed public in
  `financial_row_surfaces.py`. Its projected calls are external 2/local 1. The
  destination already imports `financial_surface_contracts.py`, graph helpers
  already import the destination, neither row nor surface owners reach graph
  helpers, the surface owner cannot reach the row owner, and the selected spans
  contain zero of 218 reviewed runtime-domain records. No source or test file
  moved in this characterization.
- Before the future move, four CURRENT-SOURCE methods must pin both direct
  contracts, exact definitions/signatures/spans/calls/DAG/baseline, and caller
  arguments/adoption/stops. Projected post-move gates are focused 4/4, owner
  51/51, affected semantic 861/861, import 19/19, audit 218, full 1,903/1,903,
  pycompile/fresh import, AST body/retained/caller parity, retired-ref zero, and
  diff check. Aggregate inference, direct/ratio acceptance, matching/scoring,
  reconciliation, state/evidence, callbacks/carriers, artifacts/ledger, and
  final sequencing remain hard stops.

The inventory itself establishes no behavior, accuracy, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim. Current-source audit
218 and the two existing caller-contract tests passed during the inventory;
benchmark refresh and remote CI were **NOT RUN**.

### Segment-local and segment-metric ownership milestone

- `d1305f8` moves the exact 7-line
  `_candidate_has_segment_local_binding(...)` and 15-line
  `_candidate_supports_segment_metric_combo(...)` definitions from
  `financial_graph_helpers.py` into `financial_row_surfaces.py` as public
  `candidate_has_segment_local_binding(...)` and
  `candidate_supports_segment_metric_combo(...)`. One deterministic-
  reconciliation call and one direct-strength call remain graph-external; the
  local-binding function owns one local metric-composition call. The final call
  matrix is external 2/local 1, direct `ast.Name`, caller `try` depth zero.
- Source is `+31/-29`, net `+2`: graph helpers are `+4/-28` and move from 5,936
  to 5,912 physical lines; row surfaces are `+27/-1` and move from 312 to 338.
  Tests are `+606/-7`, net `+599`, moving graph-helper tests from 8,145 to 8,744
  lines. The whole commit is `+637/-36`, net `+601`, and four new methods move
  discovery from 1,899 to 1,903. The source diff SHA-256 is
  `6e02e16ff3f7ee300c880b74ae8a413eae7cc343ed86e4a0a8165d5f8942278d`.
- The row owner reuses its local `_operand_text_match(...)` and imports only
  `_operand_segment_label` plus `candidate_matches_segment_binding` on the
  existing row-to-surface edge. Graph helpers already import row surfaces;
  neither row nor surface owners reach graph helpers. The graph finishes
  public/private 9/110 and row surfaces 2/15. Selected spans contain no reviewed
  domain record and the baseline remains 218.
- Four CURRENT-SOURCE methods passed before and after relocation. They pin empty-
  segment asymmetry, strict-match/fallback order, repeated segment lookup,
  shallow metadata copy, ordered surfaces, blank filtering, lazy `any`, identity,
  immutability, uncaught exceptions, reconciliation filtering before scoring,
  and the direct-strength `2.25` floor. Selected body parity 2/2, all 119 retained
  graph functions, full caller/DAG parity, and retired private source/test refs
  zero passed.
- Validation passed focused 4/4, graph-helper/surface-contract owner 51/51,
  affected nine-module semantic 861/861, import-side-effects 19/19, runtime audit
  218, full discovery 1,903/1,903, pycompile/fresh import, and diff check in the
  project `.venv`. Initial host-system Python attempts lacked `dotenv`,
  `langchain_core`, and `fastapi`; those environment errors are not counted as
  code results. Benchmark refresh was **NOT RUN**, and no remote CI run is
  claimed or verified for this local branch.

This milestone changes only segment-local and segment-metric ownership. Aggregate
row/value role-stage inference, direct/ratio acceptance, operand matching, broad
scoring/reconciliation, candidate/evidence construction/adoption, mutable state/
evidence, callbacks, carriers, trace/artifact/ledger work, and final sequencing
remain graph-owned. It proves no behavior, accuracy, ranking, performance,
total-code or executed-path reduction, benchmark improvement, schedule, ledger
completion, or Phase 3 completion.

At this handoff, no next production owner move is selected. The sole next work
is the characterize-only aggregate row/value role-stage inventory in
[Project Status Next Work](../overview/project_status.md#next-work), which must
resolve the owner, public surface, import cycles, behavior, caller/stop contract,
and projected gates before any source movement.

### Aggregate-like row role-stage characterization checkpoint

- A docs-only inventory resolves the exact 10/2/16/18-line aggregate row/value
  role-stage boundary and all 28 direct `ast.Name` calls. Every caller and all
  four bodies are outside `try`. Current test-method references are 1/0/3/3.
  No production source or test file moves in this checkpoint.
- The selected follow-on is only the 10-line aggregate-like row-stage and
  two-line row-role pair, renamed public in `financial_row_surfaces.py`. Current
  stage/role calls are 4/2; projected calls are graph-external 3/2 and owner-
  local 1/0, for external five/local one. Graph helpers already import row
  surfaces, structured cells already import row surfaces, and the row owner
  already has regex, normalization, and the same config-module edge. Selected
  spans contain zero of the 218 reviewed runtime-domain records.
- Stage behavior preserves normalization then whitespace removal, empty-input
  policy laziness, shallow outer/nested mapping copies, insertion-ordered stage
  search, eager per-stage token-set normalization, exact compact equality, first-
  match stringification, `"none"` fallback, and uncaught errors. Role calls stage
  once and maps only `"none"` to `"detail"`. Caller contracts preserve builder
  stage-then-role repetition, explicit metadata adoption precedence, lazy
  candidate fallback, contextual-match `or` short-circuiting, and downstream
  acceptance stops.
- Structured cells are rejected as the semantic owner of a raw row-label
  classifier. Surface contracts cannot receive a split candidate fallback
  without reversing the existing row-to-surface edge. Reconciliation candidates
  already import graph helpers. Moving all four helpers to row surfaces would
  publicize broad candidate metadata projection merely to reduce graph lines.
  The 16/18-line candidate pair and its 11 calls each therefore remain graph-
  owned across priority, direct grounding, direct/ratio acceptance, matching,
  direct strength, and scoring.
- Four named CURRENT-SOURCE methods must pass before and after the future move.
  Projected gates are focused 4/4, owner 55/55, affected semantic 865/865,
  import 19/19, audit 218, full 1,907/1,907, pycompile/fresh import, selected body
  parity 2/2, all 117 retained graph functions, full caller/DAG parity, retired-
  ref zero, and diff check. Exact names and contracts are maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The inventory itself establishes no behavior, accuracy, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim. Static AST/DAG,
selected-body baseline, and isolated behavior probes passed; benchmark refresh
and remote CI were **NOT RUN**.

### Aggregate-like row role-stage ownership milestone

- `80a37f8` moves the exact 10-line `_aggregate_like_row_stage(...)` and two-line
  `_aggregate_like_row_role(...)` definitions from
  `financial_graph_helpers.py` into `financial_row_surfaces.py` as public
  `aggregate_like_row_stage(...)` and `aggregate_like_row_role(...)`. Stage
  calls finish graph-external three/owner-local one and role calls graph-external
  two, for external five/local one, direct `ast.Name`, caller `try` depth zero.
- Source is `+27/-22`, net `+5`: graph helpers are `+7/-21` and move from 5,912
  to 5,898 physical lines; row surfaces are `+20/-1` and move from 338 to 357.
  Tests are `+584/-5`, net `+579`, moving graph-helper tests from 8,744 to 9,323
  lines. The whole commit is `+611/-27`, net `+584`, and four new methods move
  discovery from 1,903 to 1,907. The source diff SHA-256 is
  `075e776a65b50061c7751b2340b7eb256ad8d8f0cfbc85887a3f42867f2ae55a`.
- The row owner already held regex/normalization and its retrieval-policy module
  edge; adding `STRUCTURED_CELL_AFFINITY_POLICY` introduces no new module edge.
  Graph and structured cells already reach row surfaces, while row surfaces do
  not reach either. Graph helpers finish public/private 9/108 and row surfaces
  4/15. Selected spans contain no reviewed domain record and the baseline
  remains 218.
- Four CURRENT-SOURCE methods passed before and after relocation. They pin
  normalization/copy order, empty-input policy laziness, ordered eager token-set
  construction, exact matching/fallbacks, role projection, uncaught exceptions,
  exact definitions/calls/DAG/baseline, builder adoption, candidate fallback
  laziness, contextual short-circuiting, and exception stops. Selected body
  parity 2/2, all 117 retained graph functions, full caller/DAG parity, and
  retired private source/test refs zero passed.
- Validation passed focused 4/4, graph-helper/surface-contract owner 55/55,
  affected nine-module semantic 865/865, import-side-effects 19/19, runtime audit
  218, full discovery 1,907/1,907, pycompile/fresh import, and diff check in the
  project `.venv`. Benchmark refresh was **NOT RUN**, and no remote CI run is
  claimed or verified for this local branch.

This milestone changes only aggregate-like row label projection ownership.
Candidate value-role/stage interpretation, direct/ratio acceptance, operand
matching, broad scoring/reconciliation, candidate/evidence construction/
adoption, mutable state/evidence, callbacks, carriers, trace/artifact/ledger
work, and final sequencing remain graph-owned. It proves no behavior, accuracy,
ranking, performance, total-code or executed-path reduction, benchmark
improvement, schedule, ledger completion, or Phase 3 completion.

At this handoff, no next production owner move is selected. The sole next work
is the characterize-only lookup-hint projection inventory in
[Project Status Next Work](../overview/project_status.md#next-work). It must
compare the three pure hint projections with the four-function lookup-surface
group, freeze exact owner/DAG/behavior/callers/stops/projected gates, and select
one bounded move or record that the helpers remain graph-owned.

### Lookup-hint projection characterization checkpoint

- A docs-only inventory resolves the exact 5/14/7/5-line lookup-hint projection/
  match group and all 17 direct `ast.Name` calls in
  `financial_graph_helpers.py`. Every call has caller `try` depth zero and all
  four bodies contain no `try`. Current test-method references are 4/2/1/0. No
  production source or test file moves in this checkpoint.
- The selected follow-on moves all four definitions as public
  `lookup_prefers_canonical_statement_rows(...)`,
  `lookup_canonical_statement_preferences(...)`,
  `lookup_query_surface_preferences(...)`, and
  `operand_lookup_surface_match(...)` in `financial_operand_resolution.py`.
  Calls finish graph-external 7/5/3/1 and owner-local 0/0/1/0, for external 16/
  local one. Projected function counts are graph helpers public/private 9/104
  and operand resolution 41/37. Selected spans contain zero of the 218 reviewed
  runtime-domain records.
- Preference behavior preserves segment-first short-circuiting, exact concept
  coercion, one hint lookup, bool projection, identity, and uncaught errors.
  Canonical/query lists preserve ordered non-deduped filtering, blank/retained
  stringification counts, new list identity, and type-before-section evaluation.
  Surface matching preserves one projection call, falsy matcher laziness, exact
  text/list forwarding, uncoerced return, and uncaught errors.
- Eight graph caller contexts retain winner-first stopping, generic query label/
  alias/hint order, producer dual preference checks and adoption, direct-
  grounding and direct-acceptance boolean order, direct-strength short-circuiting,
  scoring position, and retry query/canonical-section order. Task construction,
  candidate admission/scoring, retry assembly, state/evidence, model, artifact/
  ledger work, and final sequencing remain graph-owned.
- The operand owner already defines `lookup_hints_for_concept_key(...)`, imports
  the segment helper and surface-contract module, and does not reach graph.
  Moving all four adds no edge. Moving only the first three would leave a one-
  call graph surface composer and split one semantic boundary; surface-contract
  ownership would reverse the existing operand-to-surface edge. Remaining graph-
  owned has no state, caller, or DAG justification.
- Four named CURRENT-SOURCE methods must pass before and after the future move.
  Projected gates are focused 4/4, graph-helper/operand-resolution owner 127/127,
  affected ten-module semantic 938/938, import 19/19, audit 218, full 1,911/1,911,
  pycompile/fresh import and public identity, selected body parity 4/4, all 113
  retained graph functions, full caller/DAG parity, retired-ref zero, and diff
  check. Exact names and contracts are maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The inventory itself establishes no behavior, accuracy, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim. Static AST/DAG,
selected-body baseline, and isolated behavior probes passed; benchmark refresh
and remote CI were **NOT RUN**.

### Lookup-hint projection ownership milestone

- `2eec794` moves the exact 5-line
  `_lookup_prefers_canonical_statement_rows(...)`, 14-line
  `_lookup_canonical_statement_preferences(...)`, seven-line
  `_lookup_query_surface_preferences(...)`, and five-line
  `_operand_lookup_surface_match(...)` definitions from
  `financial_graph_helpers.py` into `financial_operand_resolution.py` as public
  `lookup_prefers_canonical_statement_rows(...)`,
  `lookup_canonical_statement_preferences(...)`,
  `lookup_query_surface_preferences(...)`, and
  `operand_lookup_surface_match(...)`. Calls finish graph-external 7/5/3/1 and
  owner-local 0/0/1/0, for external 16/local one, direct `ast.Name`, caller
  `try` depth zero.
- Source is `+60/-57`, net `+3`: graph helpers are `+20/-57` and move from
  5,898 to 5,861 physical lines; operand resolution is `+40/-0` and moves from
  3,603 to 3,643. Tests are `+1,673/-20`, net `+1,653`, moving graph-helper
  tests from 9,323 to 10,976 lines while operand-resolution tests remain 7,535
  lines. The whole commit is `+1,733/-77`, net `+1,656`, and four new methods
  move discovery from 1,907 to 1,911. The source diff SHA-256 is
  `262d0304e03d9574acd45cb97e1c8b4ec4c32164f766a60c057c7bb526cc8416`.
- The operand owner already held the ontology hint lookup and segment helper.
  Adding the contract-term primitive reused its existing surface-contract edge;
  graph already reached the owner and the owner did not reach graph. Graph
  helpers finish public/private 9/104 and operand resolution 41/37. Selected
  spans contain zero reviewed domain records and the baseline remains 218.
- Four CURRENT-SOURCE methods passed before and after relocation. They pin
  segment-first preference stops, exact concept coercion, ordered list filtering
  and stringification, surface-match laziness/identity, all 17 calls, eight
  caller contexts, adoption order, exceptions, definitions/imports/DAG, and
  baseline. Selected body parity 4/4, all 113 retained graph functions, full
  caller/DAG parity, retired private source/test refs zero, and public import
  identity passed.
- Validation passed focused 4/4, graph-helper/operand-resolution owner 127/127,
  affected ten-module semantic 938/938, import-side-effects 19/19, runtime audit
  218, full discovery 1,911/1,911, pycompile/fresh import, and diff check in the
  project `.venv`. Benchmark refresh was **NOT RUN**, and no remote CI run is
  claimed or verified for this local branch.

This milestone changes only lookup-hint projection and operand-surface-match
ownership. Lookup task construction, direct grounding/acceptance, canonical-
winner and broad scoring policy, retry query assembly, candidate/evidence
construction/adoption, mutable state/evidence, callbacks, carriers, trace/
artifact/ledger work, and final sequencing remain graph-owned. It proves no
behavior, accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, ledger completion, or Phase 3 completion.

At this handoff, no next production owner move was selected without a new source
inventory. The sole characterization target became the direct logical/family
candidate-signature pair in
[Project Status Next Work](../overview/project_status.md#next-work).

### Direct candidate-signature characterization checkpoint

- A docs-only inventory resolves the exact 26-line
  `_candidate_direct_logical_signature(...)` and 22-line
  `_candidate_direct_family_signature(...)` definitions in
  `financial_graph_helpers.py`. Each has one direct `ast.Name` call from
  `_deterministic_reconcile_task(...)`, with one positional candidate, one
  `selected_cell` keyword, caller/body `try` depth zero, and one current test-
  method reference. No production source or test file moves in this checkpoint.
- The selected follow-on moves both definitions as public
  `candidate_direct_logical_signature(...)` and
  `candidate_direct_family_signature(...)` in
  `financial_operand_resolution.py`. Selected calls remain graph-external two/
  owner-local zero. Their shared `candidate_row_block_signature(...)` call
  matrix changes from external six/local one to external four/local three, still
  seven total. Projected function counts are graph helpers public/private 9/102
  and operand resolution 43/37. Selected spans contain zero of the 218 reviewed
  runtime-domain records.
- Both projections preserve metadata shallow-copy-before-block order, original-
  candidate forwarding, row-label and scope fallback order, nested identity,
  immutability, and uncaught errors. Logical value order is selected cell,
  metadata row, candidate text; its period marker falls back from selected-cell
  headers to metadata `period_focus`. Family uses the same header projection but
  intentionally has no metadata period fallback and then emits normalized
  statement type. Header order/duplicates, retained-item twice and blank-item
  once stringification, and the logical helper's two separate selected-cell
  truth-value checks remain exact.
- The sole caller retains selected-cell construction and acceptance before both
  signatures. Direct-entry evaluation stays candidate, logical, family,
  selected value, score, canonical winner; exceptions stop all later fields and
  prevent partial append. Family signature/distinct-value fast collapse remains
  ahead of logical best-by-signature grouping, sibling ranking, canonical-
  winner, semantic priority, and score policy.
- The operand owner already defines the block primitive and all other selected
  dependencies. Graph already reaches the owner and the owner does not reach
  graph, so the move removes a graph import and adds no edge. Sibling ranking,
  canonical/semantic policy, candidate value-role/stage, direct acceptance, and
  collapse are rejected expansions; reconciliation owners already reach graph,
  while row/surface/structured-cell owners do not own the block signature.
- Four named CURRENT-SOURCE methods must pass before and after the future move.
  Projected gates are focused 4/4, graph-helper/operand-resolution owner 131/131,
  affected ten-module semantic 942/942, import 19/19, audit 218, full
  1,915/1,915, pycompile/fresh import and public identity, selected body parity
  2/2, all 111 retained graph functions, full caller/DAG parity, retired-ref
  zero, and diff check. Exact names and contracts are maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The inventory itself establishes no behavior, accuracy, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim. Static AST/DAG,
selected-body baseline, isolated projection/caller probes, and audit 218 passed;
benchmark refresh and remote CI were **NOT RUN**.

### Direct candidate-signature ownership milestone

- `8cdcc94` moves the exact 26-line
  `_candidate_direct_logical_signature(...)` and 22-line
  `_candidate_direct_family_signature(...)` definitions from
  `financial_graph_helpers.py` into `financial_operand_resolution.py` as public
  `candidate_direct_logical_signature(...)` and
  `candidate_direct_family_signature(...)`. Calls finish graph-external two/
  owner-local zero, direct `ast.Name`, one positional candidate plus one
  `selected_cell` keyword, and caller `try` depth zero. The shared
  `candidate_row_block_signature(...)` calls finish external four/local three.
- Source is `+56/-55`, net `+1`: graph helpers are `+4/-55` and move from 5,861
  to 5,810 physical lines; operand resolution is `+52/-0` and moves from 3,643
  to 3,695. Tests are `+1,428/-10`, net `+1,418`, moving graph-helper tests from
  10,976 to 12,394 lines while operand-resolution tests remain 7,535 lines. The
  whole commit is `+1,484/-65`, net `+1,419`, and four new methods move discovery
  from 1,911 to 1,915. The source diff SHA-256 is
  `d22527be5fbcc25f8ab381134312fcb030f74d52c2e9c6b9a682060f0cbed68e`.
- The operand owner already held the block-signature primitive and all selected
  dependencies. Graph already reached the owner and the owner did not reach
  graph; the move removes the graph block-primitive import and adds no edge.
  Graph helpers finish public/private 9/102 and operand resolution 43/37. The
  selected spans contain zero reviewed domain record and the baseline remains
  218.
- Four CURRENT-SOURCE methods passed before and after relocation. They pin
  metadata shallow-copy order, label/scope/value/period fallback, family no-
  period-fallback asymmetry, truth/stringification counts, exceptions, exact
  definitions/calls/imports/DAG/baseline, direct-entry construction order,
  collapse behavior, candidate/selected-cell identity, and stops. Selected-body
  parity 2/2, all 111 retained graph functions, full caller/DAG parity, retired
  private source/test refs zero, and public import identity 2/2 passed.
- Validation passed focused 4/4, graph-helper/operand-resolution owner 131/131,
  affected ten-module semantic 942/942, import-side-effects 19/19, runtime audit
  218, full discovery 1,915/1,915, pycompile/fresh import, and diff check in the
  project `.venv`. Benchmark refresh was **NOT RUN**, and no remote CI run is
  claimed or verified for this local branch.

This milestone changes only direct candidate identity-projection ownership.
Selected-cell construction, direct acceptance, family/value and logical
collapse, sibling/canonical/semantic/score ranking, candidate/evidence
construction/adoption, mutable state/evidence, callbacks, carriers, trace/
artifact/ledger work, and final sequencing remain graph-owned. It proves no
behavior, accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, ledger completion, or Phase 3 completion.

At this handoff, no next production owner move was selected without a new source
inventory. The sole characterization target became the sibling-surface hit-count
projection in
[Project Status Next Work](../overview/project_status.md#next-work).

### Sibling-surface hit-count characterization checkpoint

- A docs-only inventory resolves the exact 30-line
  `_candidate_sibling_surface_hit_count(candidate, sibling_surfaces) -> int`
  definition in `financial_graph_helpers.py`. It has three direct `ast.Name`
  calls from `_deterministic_reconcile_task(...)`: sorted-key, top-hit
  recomputation, and ranked filtering. Each has two positional arguments, no
  keyword, caller/body `try` depth zero, and the current test-method reference
  count is one. No production source or test moves in this checkpoint.
- The selected follow-on moves the definition as public
  `candidate_sibling_surface_hit_count(...)` in
  `financial_row_surfaces.py`. Calls remain graph-external three/owner-local
  zero. Projected function counts are graph helpers public/private 9/101 and row
  surfaces 5/15. The selected span contains zero of the 218 reviewed runtime-
  domain records.
- Projection behavior preserves sibling-list-first early return, metadata
  shallow-copy identity, six candidate-surface order, one haystack normalization,
  empty-haystack regex/iteration stop, whitespace compaction, raw ordered dedupe
  before coercion, period-prefix stripping, case-sensitive normalized/compact
  substring matching, input immutability, and uncaught mapping/truth/copy/hash/
  iteration/string/normalization/regex errors. Exact raw duplicates count once;
  raw-distinct normalized equivalents may each count.
- The caller prepares stripped nonempty sibling strings, then reaches the helper
  only with more than one collapsed entry. It forwards a fresh shallow candidate
  copy and the same sibling-list identity at every call. Sorting uses hit then
  score in reverse order, recomputes the top hit, and only a positive top hit
  filters equal-top entries. Characterized calls for input `a,b,c` run `a,b,c`,
  top `a`, then ranked filter `a,c,b`; helper exceptions stop semantic priority
  and final adoption. Once later policy leaves winner `a`, review candidate IDs
  remain `a,b,c` because original ranked alternatives are appended up to three.
- The row owner already owns period-prefix stripping, regex, normalization, and
  required types. Graph already reaches it and it does not reach graph, so the
  move replaces one import and adds no edge. Moving sibling preparation or rank/
  filter adoption is rejected; canonical/semantic, role/stage, direct acceptance,
  collapse, state/evidence, and sequencing stay graph-owned. Surface-contract
  ownership would reverse the row-to-surface edge, and reconciliation owners
  already reach graph.
- Four named CURRENT-SOURCE methods must pass before and after the future move.
  Projected gates are focused 4/4, graph-helper/surface-contract owner 67/67,
  affected ten-module semantic 946/946, import 19/19, audit 218, full
  1,919/1,919, pycompile/fresh import and public identity, selected-body parity
  1/1, all 110 retained graph functions, full caller/DAG parity, retired-ref
  zero, and diff check. Exact names and contracts are maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The inventory itself establishes no behavior, accuracy, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim. Static AST/DAG,
selected-body baseline, isolated projection/caller probes, and audit 218 passed;
benchmark refresh and remote CI were **NOT RUN**.

### Sibling-surface hit-count ownership milestone

- `a530033` moves the exact 30-line
  `_candidate_sibling_surface_hit_count(...)` definition from
  `financial_graph_helpers.py` into `financial_row_surfaces.py` as public
  `candidate_sibling_surface_hit_count(...)`. Calls finish graph-external three/
  owner-local zero in sorted-key, top-hit recomputation, and positive-top filter
  positions. Each remains a direct `ast.Name` call with two positional arguments,
  no keywords, and caller `try` depth zero.
- Source is `+36/-36`, net zero: graph helpers are `+4/-36` and move from 5,810
  to 5,778 physical lines; row surfaces are `+32/-0` and move from 357 to 389.
  Tests are `+968/-9`, net `+959`, moving graph-helper tests from 12,394 to
  13,353 lines. The whole commit is `+1,004/-45`, net `+959`, and four new
  methods move discovery from 1,915 to 1,919. The source diff SHA-256 is
  `0c369d873a91d678a19d9a766a41152afaa8c97aca83cd7270ca2d81ea9d7466`.
- Graph helpers finish public/private 9/101 and row surfaces 5/15. The existing
  graph-to-row edge remains one-way, selected dependencies remain acyclic, the
  selected span contains zero reviewed domain records, and the baseline remains
  218. The retired graph-private name has zero source/test refs and public import
  identity is one.
- Four CURRENT-SOURCE methods passed before and after relocation. They pin the
  empty-list stop, metadata shallow-copy/nested identity, six-surface order,
  normalization, period stripping, raw ordered dedupe, compaction, exact match
  count and errors, definition/calls/import/DAG/baseline, sibling preparation,
  candidate-copy identity, sorted/top/filter order, zero-top behavior, final
  candidate review order, and exception stops. Selected-body parity 1/1, all
  110 retained graph functions, full caller/DAG parity, and diff check passed.
- Validation passed focused 4/4, graph-helper/surface-contract owner 67/67,
  affected ten-module semantic 946/946, import-side-effects 19/19, runtime audit
  218, full discovery 1,919/1,919, and pycompile/fresh import in the project
  `.venv`. Benchmark refresh was **NOT RUN**, and no remote CI run is claimed or
  verified for this local branch.

This milestone changes only sibling-surface hit-count ownership. Sibling-list
preparation, direct-entry collapse, sorted/top/filter ranking, canonical/
semantic/score policy, candidate/evidence construction/adoption, mutable state/
evidence, callbacks, carriers, trace/artifact/ledger work, and final sequencing
remain graph-owned. It proves no behavior, accuracy, ranking, performance,
total-code or executed-path reduction, benchmark improvement, schedule, ledger
completion, or Phase 3 completion.

### Query-to-metric/operand match characterization checkpoint

- A docs-only inventory resolves the adjacent exact 6-line
  `_query_mentions_metric(query, metric) -> bool` and 14-line
  `_query_component_match_count(query, operand_specs) -> int` definitions in
  `financial_graph_helpers.py`. The mention helper has three direct calls and
  the component helper one, all from `_build_semantic_numeric_plan(...)`, with
  two positional arguments, no keywords, and caller/body `try` depth zero. No
  production source or test moves in this checkpoint.
- The selected follow-on moves the pair as public `query_mentions_metric(...)`
  and `query_component_match_count(...)` in
  `financial_retrieval_hints.py`. Calls remain graph-external four/owner-local
  zero. Projected function counts are graph helpers public/private 9/99 and
  retrieval hints 5/9. Both selected spans contain zero of the 218 reviewed
  runtime-domain records and current tests contain zero selected-name refs.
- Mention behavior preserves query-first normalization, eager ordered reads of
  display/aliases/intent keywords and full iterable extension, display-only
  immediate string coercion, ordered lazy alias filtering/normalization,
  case-sensitive substring matching, first-match stop, input immutability, and
  uncaught errors. Component behavior preserves per-spec label/aliases/keywords
  collection, the same ordered matching, lazy matched-blank-label concept
  fallback, unmatched concept stop, and final nonempty label/concept identity
  dedupe with `dict.fromkeys(...)`.
- Caller order remains graph-owned: strong-metric mention tests precede formula-
  family admission; component count precedes target mention; a false mention may
  fall through to matched-key plus count-at-least-two admission; and a truthy
  matches collection tests mention before the task-loop target exemption. The
  characterized sequence is mention `target,alpha,weak`, component, target
  mention, then task-loop mention `target,alpha`, producing target and alpha
  tasks. Strong, component, and target-mention exceptions stop before task
  construction at mention/component call counts 1/0, 3/1, and 4/1.
- The retrieval-hint owner already imports normalization and required types.
  Graph already reaches it and it does not reach graph, so only public names are
  added to an existing import edge. Moving ontology lookup, operation/formula
  policy, metric admission, planner notes, task/retrieval-query construction, or
  state adoption is rejected. Four named CURRENT-SOURCE methods and projected
  focused 4/4, owner 75/75, affected semantic 958/958, import 19/19, audit 218,
  full 1,923/1,923, pycompile/fresh import/public identity, selected body 2/2,
  retained graph 108/108, caller/DAG parity, retired-ref zero, and diff check are
  maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The inventory itself establishes no behavior, accuracy, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim. Static AST/DAG,
selected-body baseline, isolated matching/caller probes, current owner 71/71,
and audit 218 passed; benchmark refresh and remote CI were **NOT RUN**.

### Query-to-metric/operand match ownership milestone

- `8e4dca4` moves the exact 6-line `_query_mentions_metric(...)` and 14-line
  `_query_component_match_count(...)` definitions from
  `financial_graph_helpers.py` to public `query_mentions_metric(...)` and
  `query_component_match_count(...)` in `financial_retrieval_hints.py`.
  Calls finish graph-external four/owner-local zero in strong-metric filtering,
  target-component assignment, target mention admission, and the task-loop
  weak-match guard. Each remains a direct `ast.Name` call with positional
  arguments only, no keywords, and caller `try` depth zero.
- Source is `+30/-28`, net `+2`: graph helpers are `+6/-28` and move from 5,778
  to 5,756 physical lines; retrieval hints are `+24/-0` and move from 294 to
  318. Tests are `+1,321/-8`, net `+1,313`, moving graph-helper tests from
  13,353 to 14,666 lines while retrieval-hint tests remain at 830. The whole
  commit is `+1,351/-36`, net `+1,315`, and four new methods move discovery
  from 1,919 to 1,923. The source diff SHA-256 is
  `5199849efa1388dfdd30178ba0bbe14f198e3c46f4e365647cc031070cab0fbd`.
- Graph helpers finish public/private 9/99 and retrieval hints 5/9. The existing
  graph-to-retrieval-hint edge remains one-way, selected dependencies remain
  acyclic, both selected spans contain zero reviewed domain records, and the
  baseline remains 218. Retired graph-private names have zero selected source/
  test refs and public import identity is 2/2.
- Four CURRENT-SOURCE methods passed before and after relocation. They pin
  query-first normalization, eager field/iterable collection, ordered lazy
  matching, case-sensitive raw-value forwarding, matched blank-label concept
  fallback, ordered identity dedupe, immutability, exceptions, exact definitions/
  calls/import/DAG/baseline, semantic-plan admission order, task output, and
  exception stops. Selected-body parity 2/2, all 108 retained graph functions,
  full caller/DAG parity, and diff check passed.
- Validation passed focused 4/4, graph-helper/retrieval-hint owner 75/75,
  affected eleven-module semantic 955/955, import-side-effects 19/19, runtime
  audit 218, full discovery 1,923/1,923, and pycompile/fresh import in the
  project `.venv`. The earlier 958 semantic projection was a counting error:
  current discovery is the prior ten-module 946-test set plus four new graph-
  helper tests and five retrieval-hint tests, or 955. Benchmark refresh was
  **NOT RUN**, and
  no remote CI run is claimed or verified for this local branch.

This milestone changes only prepared query-to-metric/operand matching ownership.
Ontology lookup, operation/formula policy, metric admission, task/retrieval-query
construction, plan/state adoption, ranking, evidence, artifacts/ledger, and final
sequencing remain graph-owned. It proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

### Query/task period-focus characterization checkpoint

- A docs-only inventory resolves the adjacent exact 11-line
  `_infer_period_focus(query, default_value="unknown") -> str` and 25-line
  `_task_period_focus_from_operands(operation_family, operand_specs,
  default_value) -> str` definitions in `financial_graph_helpers.py`. Query
  focus has four direct calls and role refinement two across the hybrid,
  concept, heuristic, and metric-task constraint builders. All six use direct
  names, positional arguments only, no keywords, and caller/body `try` depth
  zero. No production source or test moves in this checkpoint.
- The selected follow-on moves the pair as public `query_period_focus(...)` and
  `task_period_focus_from_operands(...)` in `financial_scope_policies.py`.
  Calls remain graph-external six/owner-local zero. Projected function counts
  are graph helpers public/private 9/97 and scope policy 9/9. Both selected spans
  contain zero of the 218 reviewed runtime-domain records. Current tests contain
  eight text occurrences of the selected graph-private query helper and none of
  the role helper; direct imports and patch targets must move without a graph
  compatibility alias.
- Query focus preserves raw query normalization before a shallow policy copy,
  lazy case-sensitive prior-marker precedence, then current markers, then
  order-deduped explicit-year regex matches, with exactly one distinct year
  yielding current and `default_value or "unknown"` otherwise. Role focus
  preserves full spec consumption, one role get for an empty filter and two for
  a nonempty role, current `or`/string/strip behavior, set dedupe, exact singleton
  lookup/single-value resolution, difference/growth multi-period resolution
  when both roles are present even with extras, and fallback truth-value
  semantics. Inputs remain unchanged and all existing errors remain uncaught.
- Caller order and adoption remain graph-owned. Hybrid constraints resolve
  consolidation, query period, then narrative policy. Concept constraints apply
  query focus after defaults/consolidation and role refinement only for truthy
  operand specs. Heuristic constraints apply query focus, unconditionally refine
  roles, then build retrieval queries from the refined value. Metric constraints
  read ontology defaults, overwrite consolidation, then adopt query focus.
  Exceptions stop later refinement, policy, retrieval-query construction, or
  return projection.
- The scope owner already imports every selected dependency. Graph already
  reaches it and it does not reach graph, so only public names are added to an
  existing edge. Moving consolidation/default resolution, operation inference,
  operand/task/retrieval-query construction, caller bodies, candidate report/
  year matching, ranking/admission, or state adoption is rejected. Four named
  CURRENT-SOURCE methods and projected focused 4/4, owner 74/74, affected
  semantic 1,034/1,034, import 19/19, audit 218, full 1,927/1,927,
  pycompile/fresh import/public identity, selected body 2/2, retained graph
  106/106, caller/DAG parity, retired selected-ref zero, and diff check are
  maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The inventory itself establishes no behavior, accuracy, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim. Static AST/DAG and
selected-body baseline, isolated period-focus/caller probes, current graph-
helper/direct-consumer tests 150/150, and audit 218 passed; benchmark refresh
and remote CI were **NOT RUN**.

### Query/task period-focus ownership milestone

- `55bc286` moves the exact 11-line `_infer_period_focus(...)` and 25-line
  `_task_period_focus_from_operands(...)` definitions from
  `financial_graph_helpers.py` to public `query_period_focus(...)` and
  `task_period_focus_from_operands(...)` in `financial_scope_policies.py`.
  Calls finish graph-external six/owner-local zero across hybrid, concept,
  heuristic, and metric-task constraint builders. Each remains a direct
  `ast.Name` call with positional arguments only, no keywords, and caller
  `try` depth zero.
- Source is `+48/-46`, net `+2`: graph helpers are `+8/-46` and move from 5,756
  to 5,718 physical lines; scope policy is `+40/-0` and moves from 457 to 497.
  Tests are `+1,238/-18`, net `+1,220`, moving graph-helper tests from 14,666
  to 15,886 lines while semantic-plan tests remain 2,949. The whole commit is
  `+1,286/-64`, net `+1,222`, and four new methods move discovery from 1,923 to
  1,927. The source diff SHA-256 is
  `aa560ff1fd01dca72fe55120b8dc8fbd67e95d27d6f3ebc87e863012a7054da9`.
- Graph helpers finish public/private 9/97 and scope policy 9/9. The existing
  graph-to-scope edge remains one-way, selected dependencies remain acyclic,
  both selected spans contain zero reviewed domain records, and the baseline
  remains 218. Retired executable graph-private refs are zero and public import
  identity is 2/2.
- Four CURRENT-SOURCE methods passed before and after relocation. They pin
  query-first normalization, policy shallow copy, marker precedence/laziness,
  exact-year dedupe, fallback truth semantics, full operand-spec consumption,
  role get/string/strip counts, operation-role matrix, immutability, exceptions,
  exact definitions/calls/DAG/baseline, four caller orders/adoptions, and stop
  behavior. Selected-body parity 2/2, all 106 retained graph functions, full
  caller/DAG parity, and diff check passed.
- Validation passed focused 4/4, graph-helper/scope owner 74/74, affected
  eleven-module semantic 1,034/1,034, import-side-effects 19/19, runtime audit
  218, full discovery 1,927/1,927, and pycompile/fresh import in the project
  `.venv`. Benchmark refresh was **NOT RUN**, and no remote CI run is claimed or
  verified for this local branch.

This milestone changes only query/task period-focus ownership. Consolidation/
default resolution, operation inference, operand/task/retrieval-query
construction, caller policy, candidate ranking/admission, plan/state adoption,
artifacts/ledger, and final sequencing remain graph-owned. It proves no
behavior, accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, ledger completion, or Phase 3 completion.

### Candidate value-role/stage characterization checkpoint

- A docs-only inventory resolves the adjacent exact 16-line
  `_candidate_value_role(candidate) -> str` and 18-line
  `_candidate_aggregation_stage(candidate) -> str` definitions in
  `financial_graph_helpers.py`. Each has 11 direct calls, 22 total, across
  semantic priority, direct grounding/acceptance, ratio acceptance, matching,
  direct strength, and scoring. All use one positional candidate argument, no
  keywords, and caller/body `try` depth zero. No production source or test moves
  in this checkpoint.
- The selected follow-on moves the pair as public `candidate_value_role(...)`
  and `candidate_aggregation_stage(...)` in `financial_row_surfaces.py`. Calls
  remain graph-external 22/owner-local zero. Projected function counts are graph
  helpers public/private 9/95 and row surfaces 7/15. Both selected spans contain
  zero of the 218 reviewed runtime-domain records.
- Both projections preserve metadata shallow copy, immediate explicit-field
  normalization, exact aggregate-role mappings, row-label-before-semantic
  fallback, nested identity, input immutability, and uncaught errors. Value role
  defaults to detail unless the row fallback is exactly aggregate; aggregation
  stage defaults to none unless the row fallback differs from none.
- Caller order and short circuits remain graph-owned. Role precedes stage at
  direct semantic priority, grounding/acceptance, ratio acceptance, and scoring;
  matching and direct-strength paths retain their conditional repeated calls.
  Moving acceptance, matching, strength, semantic priority, scoring/ranking, or
  candidate/evidence/state adoption is rejected. Four named CURRENT-SOURCE
  methods and projected focused 4/4, owner 78/78, affected semantic
  1,038/1,038, import 19/19, audit 218, full 1,931/1,931, pycompile/fresh import/
  public identity, selected body 2/2, retained graph 104/104, caller/DAG parity,
  retired executable private-ref zero, and diff check are maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The inventory itself establishes no behavior, accuracy, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim. Static AST/DAG and
selected-body baseline plus two existing role/stage caller probes passed;
benchmark refresh and remote CI were **NOT RUN**.

### Candidate value-role/stage ownership milestone

- `9092f5e` moves the exact 16-line `_candidate_value_role(...)` and 18-line
  `_candidate_aggregation_stage(...)` definitions from
  `financial_graph_helpers.py` to public `candidate_value_role(...)` and
  `candidate_aggregation_stage(...)` in `financial_row_surfaces.py`. Each
  function retains 11 direct graph calls, for graph-external 22/owner-local
  zero, and retired executable graph-private source/test refs are zero.
- Source is `+59/-57`, net `+2`: graph helpers are `+21/-57` and move from
  5,718 to 5,682 physical lines; row surfaces are `+38/-0` and move from 389 to
  427. Tests are `+1,167/-69`, net `+1,098`, moving graph-helper tests from
  15,886 to 16,984. The whole commit is `+1,226/-126`, net `+1,100`, and four
  new methods move discovery from 1,927 to 1,931. The source diff SHA-256 is
  `5bde3c6eb94508a4afab190cd3db4d866b265ff6f0103a028711e41c2159d8b8`.
- Graph helpers finish public/private 9/95 and row surfaces 7/15. The existing
  graph-to-row edge remains one-way. Both selected bodies preserve literal
  parity after only the public-name change; all 104 retained graph and 20
  retained row-owner functions, all 22 caller expressions, the dependency DAG,
  public identity 2/2, selected-body parity 2/2, and the 218-record baseline
  passed without a baseline change.
- Four CURRENT-SOURCE methods passed before and after relocation. They pin
  metadata shallow-copy behavior, explicit-field and aggregate-role precedence,
  row-label-before-semantic fallback, exact maps/defaults, laziness, nested
  identity, immutability, uncaught errors, every call context, and all seven
  callers' order, short-circuit, and stop behavior.
- Validation passed focused 4/4, graph-helper/row-surface owner 78/78, affected
  eleven-module semantic 1,038/1,038, import-side-effects 19/19, runtime audit
  218, full discovery 1,931/1,931, pycompile/fresh import, AST body/caller/DAG
  parity, retired-ref zero, and `git diff --check`. Benchmark refresh was
  **NOT RUN**, and no remote CI run is claimed or verified for this local branch.

This milestone changes only candidate role/stage ownership. Direct/ratio
acceptance, candidate matching, direct-match strength, semantic priority,
scoring/ranking, candidate/evidence adoption, mutable state/evidence, artifacts/
ledger, and final sequencing remain graph-owned. It proves no behavior,
accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, ledger completion, or Phase 3 completion.

### Candidate row-context surface characterization checkpoint

- A docs-only inventory selects the exact current 15-line
  `_candidate_has_operand_context_surface(candidate, operand) -> bool` and
  19-line `_table_row_has_matching_structured_sibling(metadata, operand) ->
  bool` definitions in `financial_graph_helpers.py`. Each has one direct graph
  call with two positional arguments, no keywords, and caller `try` depth zero.
  No production source or test moves for this pair at this checkpoint.
- The selected follow-on moves the pair as public
  `candidate_has_operand_context_surface(...)` and
  `table_row_has_matching_structured_sibling(...)` in
  `financial_row_surfaces.py`. Calls project graph-external two/owner-local
  zero. Current function counts are graph helpers 9/95 and row surfaces 7/15;
  projected counts are 9/93 and 9/15. Both selected spans contain zero of the
  218 reviewed runtime-domain records.
- Candidate context projection preserves a shallow metadata copy, semantic-
  alias/column-chain/table-row/table-summary/row/candidate-text order, repeated
  string/strip and blank filtering, one-space join, and positive-contract-before-
  operand-match short-circuit. Structured-sibling projection preserves raw
  metadata access, row-record payload before value-record payload, blank skips,
  `JSONDecodeError`-only soft continuation, row-label/semantic-label/row-header/
  semantic-alias surface order, and first-hit short-circuit. Inputs remain
  unchanged and all other errors remain uncaught.
- Caller placement remains graph-owned. Direct grounding reaches sibling
  projection only for lookup/single-value table rows after report/year gates;
  a hit rejects before the delta-row check. Direct strength reaches context
  projection only after aggregate-signal and lookup-surface success; a miss
  skips the role/stage checks in that clause but not the later segment-combo
  path. Exceptions stop the remaining caller work.
- Moving direct grounding/acceptance, matching or strength policy, scoring/
  ranking, record construction, candidate/evidence adoption, mutable state,
  artifacts/ledger, or final sequencing is rejected. Four named CURRENT-SOURCE
  methods and projected focused 4/4, owner 82/82, affected semantic
  1,042/1,042, import 19/19, audit 218, full 1,935/1,935, public identity/body
  parity 2/2, retained graph 102/102, retained row 22/22, caller/DAG parity,
  retired-ref zero, and diff check are maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The inventory itself establishes no behavior, accuracy, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim. Static definition,
call, DAG, function-count, and selected-body baseline inspection passed;
benchmark refresh and remote CI were **NOT RUN**.

### Candidate row-context surface ownership milestone

- `78e3508` moves the exact 15-line
  `_candidate_has_operand_context_surface(...)` and 19-line
  `_table_row_has_matching_structured_sibling(...)` definitions from
  `financial_graph_helpers.py` to public
  `candidate_has_operand_context_surface(...)` and
  `table_row_has_matching_structured_sibling(...)` in
  `financial_row_surfaces.py`. Their two calls remain graph-external/owner-local
  2/0 in direct-match strength and direct grounding; retired executable graph-
  private source/test refs are zero.
- Source is `+49/-41`, net `+8`: graph helpers are `+4/-40` and move from 5,682
  to 5,646 physical lines; row surfaces are `+45/-1` and move from 427 to 471.
  Tests are `+986/-17`, net `+969`, moving graph-helper tests from 16,984 to
  17,953. The whole commit is `+1,035/-58`, net `+977`, and four new methods
  move discovery from 1,931 to 1,935. The source diff SHA-256 is
  `228c458d7909609f45806214d1d0dcb4f0a0969648582552ba03b93d1e0b1966`.
- Graph helpers finish public/private 9/93 and row surfaces 9/15. The existing
  graph-to-row and row-to-surface edges remain acyclic. Both selected bodies
  preserve literal parity after only public-name changes; all 102 retained graph
  and 22 retained row-owner functions, both caller expressions, the full agent
  dependency DAG, public identity 2/2, selected-body parity 2/2, and the 218-
  record baseline passed without a baseline change.
- Four CURRENT-SOURCE methods passed before and after relocation. They pin
  metadata copy/no-copy behavior, surface and payload/record order, repeated
  stringification/strip sites, positive-before-fallback matching,
  `JSONDecodeError`-only continuation, identities, immutability, uncaught errors,
  and both callers' gates, short circuits, and exception stops.
- Validation passed focused 4/4, graph-helper/row-surface owner 82/82, affected
  eleven-module semantic 1,042/1,042, import-side-effects 19/19, runtime audit
  218, full discovery 1,935/1,935, pycompile/fresh import, AST body/caller/DAG
  parity, retired-ref zero, and `git diff --check`. Benchmark refresh was
  **NOT RUN**, and no remote CI run is claimed or verified for this local branch.

This milestone changes only candidate row-context ownership. Direct grounding/
acceptance, candidate matching, direct-match strength, scoring/ranking,
candidate/evidence adoption, mutable state/evidence, artifacts/ledger, and final
sequencing remain graph-owned. It proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

### Candidate selected-cell projection characterization checkpoint

- A docs-only inventory selects the exact current 21-line
  `_candidate_selected_cell_for_operand(candidate, *, operand, query_years,
  period_focus) -> Optional[Dict[str, Any]]` definition in
  `financial_graph_helpers.py`. It has one direct graph call from deterministic
  reconciliation with candidate positional, three ordered named arguments, and
  caller `try` depth zero. No production source or test moves for this
  projection at this checkpoint.
- The selected follow-on moves it as public
  `candidate_selected_cell_for_operand(...)` in
  `financial_structured_cells.py`. The call projects graph-external one/owner-
  local zero; the existing seven direct `select_structured_cell(...)` calls
  project external six/local one. Current function counts are graph helpers
  9/93 and structured cells 3/4; projected counts are 9/92 and 4/4. The selected
  span contains zero of the 218 reviewed runtime-domain records.
- The projection preserves metadata copy before candidate-kind projection,
  repeated structured-cell `dict(...)` filter/expression calls, input order,
  structured-before-parser precedence, exact table/evidence-row parser gates,
  row-text/metadata parser arguments, empty `None`, per-cell `_report_year`
  overwrite and year-get count, selector argument and return identities,
  immutability, and every current uncaught error.
- Caller placement remains graph-owned. Selection occurs only for ranked lookup/
  single-value direct grounding after period focus and before acceptance.
  Selection failure stops all later work; acceptance rejection stops signatures
  and entry fields; acceptance success forwards the identical selected cell to
  acceptance, both signatures, and selected-value extraction before score and
  canonical policy.
- Moving acceptance, signatures, matching/scoring, row/record construction,
  candidate/evidence adoption, retry assembly, mutable state, artifacts/ledger,
  or final sequencing is rejected. Four named CURRENT-SOURCE methods and
  projected focused 4/4, owner 86/86, affected semantic 1,046/1,046, import
  19/19, audit 218, full 1,939/1,939, public identity/body parity 1/1, retained
  graph 101/101, retained structured owner 7/7, caller/DAG parity, retired-ref
  zero, and diff check are maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The inventory itself establishes no behavior, accuracy, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim. Static definition,
call, DAG, function-count, and selected-body baseline inspection plus five
existing structured-cell/direct-acceptance probes passed; benchmark refresh and
remote CI were **NOT RUN**.

### Candidate selected-cell projection ownership milestone

- `0bfa1f0` moves the exact 21-line
  `_candidate_selected_cell_for_operand(...)` definition from
  `financial_graph_helpers.py` to public
  `candidate_selected_cell_for_operand(...)` in
  `financial_structured_cells.py`. Its sole direct call remains graph-external/
  owner-local 1/0 in deterministic reconciliation; the seven direct selector
  calls finish external six/local one. Retired executable graph-private source/
  test refs are zero.
- Source is `+30/-26`, net `+4`: graph helpers are `+2/-25` and move from
  5,646 to 5,623 physical lines; structured cells are `+28/-1` and move from
  335 to 362. Tests are `+1,266/-27`, net `+1,239`: graph-helper tests move
  from 17,953 to 19,190 and operation contracts from 11,558 to 11,560. The
  whole commit is `+1,296/-53`, net `+1,243`, and four new methods move full
  discovery from 1,935 to 1,939. The source diff SHA-256 is
  `eba52c11252de00d12fa808276b8c7b80b7d8dccbd7bbb828696fe5b2c37494f`.
- Graph helpers finish public/private 9/92 and structured cells 4/4. Existing
  graph-to-structured and structured-to-row module edges remain acyclic. The
  selected body preserves literal parity after the public-name change; all 101
  retained graph and seven retained structured-owner functions, the sole caller
  expression, full agent DAG, public identity 1/1, selected-body parity 1/1,
  and the 218-record baseline passed without a baseline change.
- Four CURRENT-SOURCE methods passed before and after relocation. They pin
  metadata/kind order, repeated cell-copy counts, structured/parser precedence,
  exact parser gates and arguments, empty return, ordered report-year
  enrichment, selector identities, immutability, every uncaught preparation
  error, and caller gate/order/acceptance and exception stops.
- Validation passed focused 4/4, graph-helper characterization owner 86/86,
  affected eleven-module semantic 1,046/1,046, import-side-effects 19/19,
  runtime audit 218, full discovery 1,939/1,939, pycompile/fresh import, AST
  body/caller/DAG parity, retired-ref zero, and `git diff --check`. Benchmark
  refresh was **NOT RUN**, and no remote CI run is claimed or verified for this
  local branch.

This milestone changes only candidate selected-cell preparation ownership.
Direct acceptance, logical/family signatures, candidate matching/scoring,
candidate/evidence adoption, retry assembly, mutable state/evidence, artifacts/
ledger, and final sequencing remain graph-owned. It proves no behavior,
accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, ledger completion, or Phase 3 completion.

### Scoped surface-affinity projection characterization checkpoint

- A docs-only inventory selects the exact current 56-line
  `_scoped_surface_affinity_priority(items, *, query, topic,
  required_operands=None, require_segment_operand=False, direct_weight=0.0,
  adjustment_weight=0.0) -> float` definition in
  `financial_graph_helpers.py`. It has two direct `AugAssign` calls in evidence
  prioritization and coherent ratio-context selection, both at caller `try`
  depth zero. No production source or test moves for this projection at this
  checkpoint.
- The selected follow-on moves it as public
  `scoped_surface_affinity_priority(...)` in
  `financial_surface_contracts.py`. Both calls project owner-external two/
  owner-local zero and its operand-segment dependency becomes owner-local.
  Current function counts are graph helpers 9/92 and surface contracts 9/7;
  projected counts are 9/91 and 10/7. Both callers already import the
  destination, the agent DAG is unchanged, and the selected span contains zero
  of the 218 reviewed runtime-domain records.
- The projection preserves the disabled segment gate's complete laziness,
  enabled-gate eager operand-list copy and first-hit order, policy copy and
  repeated metric-term stringification, exact query/topic formatting, metric-
  miss stop, direct item iteration, per-item metadata shallow copy, fixed eleven-
  part surface order, repeated part string/strip sites, one-space join and whole-
  surface normalization, direct-before-adjustment marker scans, dual raw
  weights, identities, immutability, and every current uncaught error.
- Evidence prioritization keeps its exact segment-note/metric gate, one-item
  list and `2.5/-1.5` weights; coherent ratio-context selection keeps its row/
  missing/collapse, unit-count, and schema-score order, current group and
  required-operand identities, segment-required flag, and `12.0/-8.0` weights.
  Exceptions stop later ranking or best-row adoption.
- Moving caller eligibility/schema scoring, evidence/group/operand-row
  construction, direct/ratio acceptance, broader ranking, result adoption,
  retrieval, mutable state, artifacts/ledger, or final sequencing is rejected.
  Four named CURRENT-SOURCE methods and projected focused 4/4, owner 90/90,
  affected semantic 1,050/1,050, import 19/19, audit 218, full 1,943/1,943,
  public identity 2/2, selected body 1/1, retained graph 100/100, retained
  surface owner 16/16, caller/DAG parity, retired-ref zero, and diff check are
  maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The inventory itself establishes no behavior, accuracy, ranking, performance,
benchmark, schedule, ledger, or Phase 3 completion claim. Static definition,
call, DAG, function-count, and selected-body baseline inspection, direct
behavior probes 5/5, and four existing caller/ratio probes passed; benchmark
refresh and remote CI were **NOT RUN**.

### Scoped surface-affinity ownership milestone

- Commit `2b0e9c1` moved the exact former 56-line
  `_scoped_surface_affinity_priority(...)` graph-helper definition to public
  `financial_surface_contracts.scoped_surface_affinity_priority(...)`. Both
  direct `AugAssign` calls remain owner-external at caller `try` depth zero in
  evidence prioritization and coherent ratio-context scoring; their caller
  gates, argument identities, weights, score adoption, and exception stops are
  unchanged. The selected `_operand_segment_label(...)` call is owner-local.
- Segment-gate disabled laziness, enabled eager operand-list copy and first-hit
  order, policy copy, repeated term/part/marker stringification, exact query/
  topic formatting, metric miss stop, fixed eleven-part surface order, metadata
  shallow copies, joined normalization, direct-before-adjustment membership,
  dual raw weights, nested identity, input immutability, and every uncaught
  error remain pinned by four CURRENT-SOURCE methods.
- Source is `+67/-64`, net `+3`; tests are `+851/-15`, net `+836`; and the
  whole commit is `+918/-79`, net `+839`. Graph helpers moved from 5,623 to
  5,564 lines, surface contracts from 334 to 396, graph-helper tests from
  19,190 to 20,026, and discovery from 1,939 to 1,943. Graph-helper public/
  private counts finish 9/91 and surface-contract counts finish 10/7. The
  source diff SHA-256 is
  `a9d2c5aad44530e9cbcc9d6c27e9644109251adfcc3f17ae705c6936f2015377`.
- Focused 4/4, graph-helper owner 90/90, affected semantic 1,050/1,050,
  import-side-effects 19/19, runtime-domain audit 218, and full discovery
  1,943/1,943 passed. Pycompile/fresh import and public identity 2/2, selected-
  body parity 1/1, retained graph 100/100, retained surface owner 16/16, both
  caller expressions and bodies, full 48-module DAG parity, zero selected-body
  audit hits, zero retired executable private refs, and diff check also passed.
  Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes ownership only. It establishes no behavior, accuracy,
ranking, performance, total-code or executed-path reduction, benchmark,
schedule, ledger, or Phase 3 completion claim. Caller eligibility/schema
scoring, evidence and operand-row construction, direct/ratio acceptance,
broader ranking, result adoption, and graph/artifact/ledger state remain
outside the moved owner.

### Candidate period/table coherence characterization checkpoint

- A docs-only inventory selects the exact current 30-line
  `_candidate_period_table_coherence_bonus(candidate, *, operand,
  query_years) -> float` definition in `financial_graph_helpers.py`. Its sole
  direct call is an `AugAssign` inside `_score_operand_candidate(...)` at
  caller `try` depth zero. No production source or test moves for this
  projection at this checkpoint.
- The selected follow-on moves it as public
  `candidate_period_table_coherence_bonus(...)` in
  `financial_scope_policies.py`. Current/projected public/private counts are
  graph helpers 9/91 to 9/90 and scope policy 9/9 to 10/9. Graph already reaches
  the scope owner, the owner does not reach graph, and both selected
  dependencies are already owner-held, so the agent import DAG is unchanged.
- The projection preserves metadata shallow copy before the explicit-year
  dependency, falsey-year return before operand/query-year access, original
  candidate/operand/query-year identities, raw year and target-year truth/
  iteration/membership/length behavior, first target hit short circuit, exact
  `+1.0/-1.0` target score, exact period roles and `+0.75`, lazy table-source
  access and `+0.35`, unit strip/uppercase and percent-only `+0.5`, separate
  duplicate-sensitive length calls, score order, nested identity, immutability,
  and every current uncaught error. Full match and miss examples score `2.6`
  and `0.6` respectively.
- The sole caller remains after source priority and metadata-period scoring and
  before report-scope binding, the final table-source `0.25`, and return.
  Success adds the result directly; failure stops the remaining scorer and all
  enclosing ranking/adoption. Moving candidate/year extraction, target-year
  policy, other score contributions, matching/admission/acceptance, broader
  ranking, candidate/evidence adoption, or graph/artifact/ledger state is
  rejected.
- `candidate_explicit_years(...)` calls project from external/local 1/4 to 0/5.
  `operand_target_years(...)` calls project from 9/5 to 8/6; its other callers
  remain in place. The selected span contains zero of the 218 reviewed runtime-
  domain records.
- Four named CURRENT-SOURCE methods and projected focused 4/4, owner 94/94,
  affected semantic 1,054/1,054, import 19/19, audit 218, full 1,947/1,947,
  public identity 1/1, selected body 1/1, retained graph 99/99, retained scope
  owner 18/18, caller/DAG parity, retired-ref zero, and diff check are maintained
  only in [Project Status Next Work](../overview/project_status.md#next-work).

The characterization establishes no implementation or quality improvement.
Static definition/call/DAG/function/dependency inventory and selected-body
baseline inspection, direct behavior probes 5/5, and four existing report/
period caller probes passed; benchmark refresh and remote CI were **NOT RUN**.

### Candidate period/table coherence ownership milestone

- Commit `7ec0cc3` moved the exact former 30-line
  `_candidate_period_table_coherence_bonus(candidate, *, operand,
  query_years) -> float` definition from `financial_graph_helpers.py` to public
  `financial_scope_policies.candidate_period_table_coherence_bonus(...)`.
  Its sole direct `AugAssign` remains graph-external/owner-local 1/0 in
  `_score_operand_candidate(...)` at caller `try` depth zero, after source and
  metadata-period scoring and before report-scope/final-table scoring.
- The exact metadata-before-year shallow-copy order, falsey-year stop, original
  dependency arguments/results, target truth/iteration/membership and first-hit
  short circuit, `+1.0/-1.0`, exact period-role and separate duplicate-sensitive
  length gates, lazy table-source `+0.35`, percent `+0.5`, `2.6/0.6` examples,
  identities, immutability, and every uncaught error remain pinned by four
  CURRENT-SOURCE methods. Explicit-year calls finish external/local 0/5 and
  target-year calls 8/6.
- Source is `+34/-34`, net `0`: graph helpers are `+2/-34` and move from 5,564
  to 5,532 physical lines; scope policy is `+32/-0` and moves from 497 to 529.
  Tests are `+788/-30`, net `+758`, moving graph-helper tests from 20,026 to
  20,784. The whole commit is `+822/-64`, net `+758`, and four new methods move
  full discovery from 1,943 to 1,947. Graph helper public/private counts finish
  9/90 and scope policy counts finish 10/9. The source diff SHA-256 is
  `33d6fdd3e6216ab2e963fe6480484d7d7b59ee5d333c58b678479d0ed90c139d`.
- Focused 4/4, graph-helper owner 94/94, affected eleven-module semantic
  1,054/1,054, import-side-effects 19/19, runtime-domain audit 218, and full
  discovery 1,947/1,947 passed. Pycompile/fresh import/public identity 1/1,
  selected-body parity 1/1, retained graph 99/99, retained scope owner 18/18,
  sole caller expression/body, full 48-module DAG parity, zero selected-body
  audit hits, zero retired executable private refs, and diff check also passed.
  Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only candidate period/table score ownership. Candidate/
year extraction, target-year policy, source/report/other score work, matching/
admission/acceptance, broader ranking/adoption, retrieval, and graph/artifact/
ledger state remain outside. It proves no behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark improvement,
schedule, ledger completion, or Phase 3 completion.

### Candidate location/entity subject-score characterization checkpoint

- A docs-only inventory selects the exact current 53-line
  `_candidate_location_entity_subject_score(candidate, *, operand) -> float`
  definition in `financial_graph_helpers.py`. Its sole direct call is an
  `AugAssign` inside `_score_operand_candidate(...)` at caller `try` depth zero.
  No production source or test moves for this projection at this checkpoint.
- The selected follow-on moves it as public
  `candidate_location_entity_subject_score(...)` in
  `financial_operand_resolution.py`. Current/projected public/private counts are
  graph helpers 9/90 to 9/89 and operand resolution 43/37 to 44/37. Graph
  already reaches the owner, the owner does not reach graph, and the owner
  already imports regex, normalization, policy, and types, so the full agent
  DAG remains unchanged. The call projects external/local 1/0 and the selected
  span contains zero of the 218 reviewed runtime-domain records.
- The projection preserves eager unit/operation/role projection before gates,
  blank-or-COUNT and operation-or-period-role admission, policy copy and subject/
  temporal access order, metadata shallow copy, exact five-part eager surface
  retrieval, repeated truth/string/filter evaluation, one-space join and whole-
  surface normalization, fixed whitespace compaction, eager regex-match list,
  empty stops, ordered subject extraction, temporal classification, first non-
  temporal short circuit, branch-lazy bonus/penalty access, exact checked-in
  `2.0/-1.0`, selective `TypeError`/`ValueError` fallback, identities,
  immutability, and all other uncaught errors.
- The sole caller remains after numeric-signal scoring and before descriptor,
  statement, scope/period, source/table, and return work. Success adds the score
  directly; an uncaught failure stops all later scoring and enclosing ranking/
  adoption. Moving operand policy, candidate construction, concept/direct
  matching, any other scoring, acceptance, broader ranking, evidence adoption,
  retrieval, or graph/artifact/ledger state is rejected.
- Four named CURRENT-SOURCE methods and projected focused 4/4, owner 98/98,
  affected semantic 1,058/1,058, import 19/19, audit 218, full 1,951/1,951,
  public identity 1/1, selected body 1/1, retained graph 98/98, retained operand
  owner 80/80, sole caller/body, full 48-module DAG parity, retired-ref zero,
  and diff check are maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The characterization establishes no implementation or quality improvement.
Static definition/call/DAG/function-count and selected-body baseline inspection,
direct behavior probes 5/5, and four existing scorer/caller probes passed;
benchmark refresh and remote CI were **NOT RUN**.

### Candidate location/entity subject-score ownership milestone

- Commit `23f08b2` moved the exact former 53-line
  `_candidate_location_entity_subject_score(candidate, *, operand) -> float`
  definition from `financial_graph_helpers.py` to public
  `financial_operand_resolution.candidate_location_entity_subject_score(...)`.
  Its sole direct `AugAssign` remains graph-external/owner-local 1/0 in
  `_score_operand_candidate(...)` at caller `try` depth zero, after numeric-
  signal scoring and before descriptor/statement/scope/period/source/table work.
- Exact unit/operation/role access and gates, policy/metadata shallow copies,
  subject/temporal access, eager five-part surface retrieval, repeated truth/
  string/filter evaluation, joined normalization, regex compaction and eager
  match list, ordered subject classification, first non-temporal stop, branch-
  lazy bonus/penalty, exact `2.0/-1.0`, selective `TypeError`/`ValueError`
  fallback, identities, immutability, and every other uncaught error remain
  pinned by four CURRENT-SOURCE methods.
- Source is `+57/-56`, net `+1`: graph helpers are `+2/-56` and move from
  5,532 to 5,478 physical lines; operand resolution is `+55/-0` and moves from
  3,695 to 3,750. Tests are `+890/-23`, net `+867`, moving graph-helper tests
  from 20,784 to 21,651 while the operand-resolution test file stays at 7,535
  lines. The whole commit is `+947/-79`, net `+868`, and four new methods move
  full discovery from 1,947 to 1,951. Graph helper public/private counts finish
  9/89 and operand-resolution counts finish 44/37. The source diff SHA-256 is
  `4d1144206071e440dbb5815904ab2f30cc5d955c8938fb767ea3673a6e31f105`.
- Focused 4/4, graph-helper owner 98/98, affected eleven-module semantic
  1,058/1,058, import-side-effects 19/19, runtime-domain audit 218, and full
  discovery 1,951/1,951 passed. Pycompile 4/4, fresh import 2/2, public identity
  1/1, selected-body parity 1/1, retained graph 98/98, retained operand owner
  80/80, sole caller expression/body, full 48-module DAG parity, zero selected-
  body audit hits, zero retired executable private refs, and diff check also
  passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only candidate location/entity subject-score ownership.
Operand policy, candidate/evidence construction, all other score/rank work,
matching/admission/acceptance, adoption, retrieval, graph state, model
invocation, artifact/ledger mutation, retry assembly, and final sequencing
remain outside. It proves no behavior, accuracy, ranking, performance, total-
code or executed-path reduction, benchmark improvement, schedule, ledger
completion, or Phase 3 completion.

### Delta-like row-label characterization checkpoint

- A docs-only inventory selects the exact current 7-line
  `_is_delta_like_row_label(label: str) -> bool` definition in
  `financial_graph_helpers.py`. Its three direct `ast.Name` calls are
  positional with no keywords and caller `try` depth zero. No production source
  or test moves for this projection at this checkpoint.
- The selected follow-on moves it as public `is_delta_like_row_label(...)` in
  `financial_row_surfaces.py`. Current/projected public/private counts are graph
  helpers 9/89 to 9/88 and row surfaces 9/15 to 10/15. Graph already reaches the
  row owner, the owner does not reach graph, and the owner already imports
  normalization and the retrieval-policy module, so the full agent DAG remains
  unchanged. Calls project external/local 3/0 and the selected span contains
  zero of the 218 reviewed runtime-domain records.
- The projection preserves raw `label or ""` truth, one selected-value string,
  one normalization, falsey-text return before policy, policy shallow copy,
  raw falsey marker fallback, eager marker tuple, filter/expression repeated
  stringification, policy-order membership, first-hit `any(...)`, checked-in
  true/false examples, nested identity, immutability, and all current uncaught
  label/normalization/mapping/truth/iteration/string/tuple/membership errors.
- Direct grounding calls first with prepared `semantic_label` under current/
  prior focus before segment/report/target-period gates, and later with truthy
  `row_text` only for lookup/single-value table rows after structured-sibling
  rejection; either hit rejects. Operand scoring calls with exact left-to-right
  `semantic_label or row_label`; a hit subtracts `4.0` and continues. Failures
  stop all later caller work and enclosing adoption.
- Moving period-focus policy, candidate construction, concept/direct matching,
  acceptance, broader scoring/ranking, evidence adoption, retrieval, or graph/
  artifact/ledger state is rejected. Four named CURRENT-SOURCE methods and
  projected focused 4/4, owner 102/102, affected semantic 1,062/1,062, import
  19/19, audit 218, full 1,955/1,955, public identity 1/1, selected body 1/1,
  retained graph 97/97, retained row owner 24/24, all three callers/two caller
  bodies, full 48-module DAG parity, retired-ref zero, and diff check are
  maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The characterization establishes no implementation or quality improvement.
Static definition/call/DAG/function-count and selected-body baseline inspection,
direct behavior probes 5/5, and four existing grounding/scorer caller probes
passed; benchmark refresh and remote CI were **NOT RUN**.

### Delta-like row-label ownership milestone

- Commit `e04a7bf` moved the exact former 7-line
  `_is_delta_like_row_label(label: str) -> bool` definition from
  `financial_graph_helpers.py` to public
  `financial_row_surfaces.is_delta_like_row_label(...)`. Its three direct calls
  finish graph-external/owner-local 3/0: two in
  `_candidate_is_direct_grounding_candidate(...)` and one in
  `_score_operand_candidate(...)`, all at caller `try` depth zero.
- Raw `label or ""` truth, selected-value stringification, one normalization,
  falsey-text stop, policy shallow copy/access, raw marker fallback, eager tuple,
  retained-marker double and blank-marker single stringification, policy-order
  membership, first-hit `any(...)`, checked-in true/false examples, identities,
  immutability, and every uncaught error remain pinned by four CURRENT-SOURCE
  methods. Caller gates, exact arguments, rejection/penalty adoption, and
  exception stops remain unchanged.
- Source is `+14/-12`, net `+2`: graph helpers are `+4/-12` and move from 5,478
  to 5,470 physical lines; row surfaces are `+10/-0` and move from 471 to 481.
  Tests are `+811/-25`, net `+786`, moving graph-helper tests from 21,651 to
  22,437 lines. The whole commit is `+825/-37`, net `+788`, and four methods
  move full discovery from 1,951 to 1,955. Graph helper public/private counts
  finish 9/88 and row-surface counts finish 10/15. The source diff SHA-256 is
  `b3ceafde06df105a8d62b77dae1e8d6f61711ed04e2132e9f90213012d4c7e0c`.
- Focused 4/4, graph-helper owner 102/102, affected eleven-module semantic
  1,062/1,062, import-side-effects 19/19, runtime-domain audit 218, and full
  discovery 1,955/1,955 passed. Pycompile 3/3, fresh import/public identity 1/1,
  selected-body parity 1/1, retained graph 97/97, retained row owner 24/24,
  all three caller expressions and two caller bodies, full 48-module DAG parity,
  zero selected-body audit hits, zero retired executable private refs, and diff
  check also passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only delta-like row-label classifier ownership. Period-
focus policy, candidate/evidence construction, all surrounding score/rank work,
matching/admission/acceptance, adoption, retrieval, graph state, model
invocation, artifact/ledger mutation, retry assembly, and final sequencing
remain outside. It proves no behavior, accuracy, ranking, performance, total-
code or executed-path reduction, benchmark improvement, schedule, ledger
completion, or Phase 3 completion.

### Preference-bonus characterization checkpoint

- A docs-only inventory selects the exact current 7-line
  `_preference_bonus(...)` definition in `financial_graph_helpers.py`, whose
  complete signature is
  `(value: str, preferred: List[str], *, base: float = 0.4) -> float`. Its two
  direct `ast.Name` calls are consecutive scorer `AugAssign` expressions at
  caller `try` depth zero. No production source or test moves for this
  projection at this checkpoint.
- The selected follow-on moves it as public `preference_bonus(...)` in
  `financial_operand_resolution.py`. Current/projected public/private counts are
  graph helpers 9/88 to 9/87 and operand resolution 44/37 to 45/37. Graph already
  reaches the owner, the owner does not reach graph, and the owner already
  imports `List` and normalization, so the full agent DAG remains unchanged.
  Calls project external/local 2/0 and the selected span contains zero of the
  218 reviewed runtime-domain records.
- The projection preserves eager source-order preference iteration, raw item
  normalization once for dropped and twice for retained items, exact second-
  result retention, completion before one value normalization, raw target truth,
  exact falsey/missing `0.0`, separate ordered membership and first-equal index
  scans, duplicate order, `base * max(len(ordered) - index, 1)`, raw base
  multiplication/product, identities, immutability, and every current uncaught
  iteration/normalization/truth/equality/index/length/subtraction/max/
  multiplication error.
- The scorer calls exact `value_role, preferred_value_roles, base=0.6` and then
  `aggregation_stage, preferred_aggregation_stages, base=0.5` after period-focus
  scoring and before avoid/section/source/period/table/report work. Each result
  is added in order; failures stop the second call when applicable, all later
  work, and enclosing ranking/adoption.
- Moving caller collection preparation, role/stage derivation, candidate
  construction, concept/direct matching, acceptance, other scoring/ranking,
  evidence adoption, retrieval, or graph/artifact/ledger state is rejected.
  Four named CURRENT-SOURCE methods and projected focused 4/4, owner 106/106,
  affected semantic 1,066/1,066, import 19/19, audit 218, full 1,959/1,959,
  public identity 1/1, selected body 1/1, retained graph 96/96, retained operand
  owner 81/81, both caller expressions/sole caller body, full 48-module DAG
  parity, retired-ref zero, and diff check are maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The characterization establishes no implementation or quality improvement.
Static definition/call/DAG/function-count and selected-body baseline inspection,
direct behavior probes 6/6, and caller order/adoption/stop probes 3/3 passed;
benchmark refresh and remote CI were **NOT RUN**.

### Preference-bonus ownership milestone

- Commit `c4558b7` moves the exact former 7-line `_preference_bonus(...)`
  definition from `financial_graph_helpers.py` to public
  `financial_operand_resolution.preference_bonus(...)` with its body unchanged.
  Its complete signature remains
  `(value: str, preferred: List[str], *, base: float = 0.4) -> float`.
- The two direct `ast.Name` calls finish graph-external/owner-local 2/0 as
  consecutive scorer `AugAssign` expressions at caller `try` depth zero. Exact
  `value_role, preferred_value_roles, base=0.6` remains first and exact
  `aggregation_stage, preferred_aggregation_stages, base=0.5` remains second,
  after period-focus score work and before avoid/section/source/period/table/
  report work. Each result is added in order; all current failure stops remain
  uncaught.
- Eager source-order preference iteration, dropped-once/retained-twice raw
  normalization, exact second-result retention, completion before value
  normalization, falsey/missing exact `0.0`, separate membership/index scans,
  first-equal duplicate selection, exact raw
  `base * max(len(ordered) - index, 1)`, identities, immutability, and every
  uncaught error remain pinned by four CURRENT-SOURCE methods. No wrapper,
  graph alias, callback, carrier, reason, flag, trace, coercion, or fallback is
  added.
- Source is `+12/-11`, net `+1`: graph helpers are `+3/-11` and move from
  5,470 to 5,462 physical lines; operand resolution is `+9/-0` and moves from
  3,750 to 3,759. Tests are `+734/-21`, net `+713`: graph-helper tests are
  `+732/-19` and move from 22,437 to 23,150 lines, while the operand-owner
  static line-span update is `+2/-2`. The whole commit is `+746/-32`, net
  `+714`, and four methods move full discovery from 1,955 to 1,959. Graph helper
  public/private counts finish 9/87 and operand-resolution counts finish 45/37.
  The source diff SHA-256 is
  `319be70af91d64a48d09ec63a1524fe3f5b4834b32238a32a1f1e967e1ec69e5`.
- Focused 4/4, graph-helper owner 106/106, affected eleven-module semantic
  1,066/1,066, import-side-effects 19/19, runtime-domain audit 218, and full
  discovery 1,959/1,959 passed. Pycompile 4/4, fresh import/public identity 1/1,
  selected-body parity 1/1, retained graph 96/96, retained operand owner 81/81,
  both caller expressions and the sole caller body, full 48-module DAG parity,
  zero selected-body audit hits, zero retired executable private refs, and diff
  check also passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic positional preference-bonus
ownership. Caller collection preparation, role/stage derivation, candidate/
evidence construction, all surrounding score/rank work, matching/admission/
acceptance, adoption, retrieval, graph state, model invocation, artifact/ledger
mutation, retry assembly, and final sequencing remain outside. It proves no
behavior, accuracy, ranking, performance, total-code or executed-path
reduction, benchmark improvement, schedule, ledger completion, or Phase 3
completion.

### Column-candidate-label characterization checkpoint

- A docs-only inventory selects the exact current 10-line
  `_column_candidate_label(column_headers: List[str]) -> str` definition in
  `financial_graph_helpers.py`. Its sole direct `ast.Name` call is positional
  exact `original_headers`, has no keywords, and appears in an immediate
  `Assign` inside `_build_table_column_reconciliation_candidates(...)` at
  caller `try` depth zero. No production source or test moves for this
  projection at this checkpoint.
- The selected follow-on moves it as public `column_candidate_label(...)` in
  `financial_row_surfaces.py`. Current/projected public/private counts are graph
  helpers 9/87 to 9/86 and row surfaces 10/15 to 11/15. Graph already reaches
  the owner, the owner does not reach graph, and the owner already imports
  `re`, `List`, normalization and owns `_generic_column_headers()`, so the full
  agent DAG remains unchanged. The selected call projects external/local 1/0
  and the then-current line-derived baseline check reported zero selected-body
  records. The later ownership audit established that this was stale line
  metadata: the year regex was already one of the 218 reviewed records.
- The projection preserves eager source-order header consumption, raw
  normalization once for dropped and twice for retained headers, exact second-
  result retention, completion before generic policy access, blank exact `""`
  stop, direct use of the one returned generic-header collection, eager ordered
  `not in` membership, exact last non-generic or all-generic fallback, and one
  target-only `re.fullmatch(r"20\d{2}(?:년)?", target)`. A truthy year match
  returns exact `""`; a falsey match returns the exact target. Duplicate/order,
  identities, immutability, and every current uncaught iteration/
  normalization/truth/policy/containment/equality/hash/regex/match-truth error
  remain exact.
- The caller rebuilds normalized `original_headers` after its row/header and
  numeric-value gates, then calls the helper before label truth, grouping-key
  construction, bucket mutation, and final candidate synthesis. A falsey label
  skips that cell; a truthy label is adopted into its bucket and output
  candidate. Helper or caller-side truth failures stop later cells/final
  synthesis without mutating supplied row records or metadata.
- Moving row/cell preparation, numeric gating, grouping/bucket/candidate
  construction, structured-cell selection, matching/scoring/acceptance,
  adoption, report-file I/O, retrieval, or graph/artifact/ledger state is
  rejected. Four named CURRENT-SOURCE methods and projected focused 4/4, owner
  110/110, affected semantic 1,070/1,070, import 19/19, audit 218, full
  1,963/1,963, public identity/body 1/1, retained graph 95/95, retained row owner
  25/25, sole caller/body, full 48-module DAG parity, retired-ref zero, and diff
  check are maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The characterization establishes no implementation or quality improvement.
Static definition/call/DAG/function-count and selected-body baseline inspection,
direct behavior probes 6/6, and caller order/adoption/stop probes 3/3 passed;
benchmark refresh and remote CI were **NOT RUN**.

### Column-candidate-label ownership milestone

- Commit `0dc278e` moves the exact former 10-line
  `_column_candidate_label(column_headers: List[str]) -> str` definition from
  `financial_graph_helpers.py` to public
  `financial_row_surfaces.column_candidate_label(...)` with its body unchanged.
  The complete signature remains `(column_headers: List[str]) -> str`.
- The sole direct `ast.Name` call finishes graph-external/owner-local 1/0 with
  exact positional `original_headers`, no keywords, caller `try` depth zero,
  and immediate `Assign` parent inside the table-column reconciliation
  candidate builder. Its placement after row/header/numeric preparation and
  before label truth, grouping, bucket mutation, and final candidate synthesis
  is unchanged; all existing adoption and stop behavior remains uncaught.
- Eager header consumption, dropped-once/retained-twice raw normalization,
  second-result retention, blank early return, one direct generic-header
  collection, ordered `not in`, last non-generic/all-generic fallback, exact
  target-only year regex, identities, immutability, and exception behavior are
  pinned by four CURRENT-SOURCE methods. No wrapper, graph alias, callback,
  carrier, reason, flag, trace, coercion, or fallback is added.
- The first post-move runtime-domain audit correctly failed with exactly one
  unexpected row-owner record and one missing graph-owner record. The literal
  `20\d{2}(?:년)?`, category `regex_or_pattern`, and count one were unchanged;
  only the existing reviewed record's owner path, path-derived fingerprint, and
  current line moved. This corrected the characterization's stale line-derived
  zero-hit claim and kept the reviewed baseline total at 218.
- Source is `+14/-14`, net zero: graph helpers are `+2/-14` and move from
  5,462 to 5,450 physical lines; row surfaces are `+12/-0` and move from 481 to
  493. Graph-helper tests are `+688/-22`, net `+666`, and move from 23,150 to
  23,816 lines; the reviewed baseline is `+3/-3`. The whole commit is
  `+705/-39`, net `+666`, and four methods move full discovery from 1,959 to
  1,963. Graph helper public/private counts finish 9/86 and row-surface counts
  finish 11/15. The source diff SHA-256 is
  `053f3195dce934a7d005e8d61b57355c2639b215834eb29f741ed6592d86a9f7`.
- Focused 4/4, graph-helper owner 110/110, affected eleven-module semantic
  1,070/1,070, import-side-effects 19/19, runtime-domain audit 218, and full
  discovery 1,963/1,963 passed. Pycompile, fresh import/public identity 1/1,
  selected-body parity 1/1, retained graph 95/95 after target-call
  normalization, retained row owner 25/25, sole caller expression/body, full
  48-module/203-edge DAG parity, zero retired executable private refs, and diff
  check also passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic column-label ownership. Row/cell
preparation, numeric gating, grouping/bucket/candidate construction, matching/
scoring/acceptance, evidence adoption, retrieval, report-file I/O, graph state,
artifact/ledger mutation, and final sequencing remain outside. It proves no
behavior, accuracy, ranking, performance, total-code or executed-path
reduction, benchmark improvement, schedule, ledger completion, or Phase 3
completion.

### Single-report-scope characterization checkpoint

- A docs-only inventory selects the exact current 8-line
  `_has_single_report_scope(report_scope: Dict[str, Any]) -> bool` definition in
  `financial_graph_helpers.py`. Its sole direct `ast.Name` call is positional
  exact `report_scope`, has no keywords, and is the immediate `If` condition in
  `align_scope_hints(...)` at caller `try` depth zero. No production source or
  test moves for this projection at this checkpoint.
- The selected follow-on moves it as public `has_single_report_scope(...)` in
  `financial_scope_policies.py`. Current/projected public/private counts are
  graph helpers 9/86 to 9/85 and scope policies 10/9 to 11/9. Graph already
  reaches the owner, the owner does not reach graph, and the owner already
  imports `Any`/`Dict` and owns `_report_scope_source_receipts(...)`; the full
  48-module/203-edge agent DAG remains unchanged. The selected call projects
  external/local 1/0 and the span contains zero of 218 reviewed records.
- The projection preserves raw `report_scope or {}` truth before one `dict`
  call, a fresh shallow copy with retained nested identities, exact receipt-key
  get/or/string/strip/truth evaluation outside the `try`, and a truthy explicit-
  receipt fast return before receipt projection. Otherwise it calls the owner-
  private receipt helper once with the exact copied scope, takes one length,
  and returns `len(...) <= 1` inside the current `try`. Exact `Exception`
  failures become `False`; pre-try failures and `BaseException` remain uncaught.
- The caller invokes the predicate only after a truthy normalized scope company
  and after company/year list preparation. `True` replaces companies with the
  scope company; `False` preserves the existing empty/prepend/already-present
  fallback order; scope-year adoption remains later. Caller inputs stay
  unmodified and every uncaught failure stops later adoption.
- Moving caller-owned company/year alignment, report inventory/selection,
  consolidation/candidate scope policy, report-file I/O, candidate/evidence
  construction, retrieval, graph state, or artifact/ledger mutation is
  rejected. The file-I/O unit-hint cluster, policy-unclassified domain
  predicates, cycle-forming candidate builder, and graph-state year helper stay
  excluded. Four named CURRENT-SOURCE methods and projected focused 4/4, owner
  114/114, affected semantic 1,074/1,074, import 19/19, audit 218, full
  1,967/1,967, public identity/body 1/1, retained graph 94/94, retained scope
  owner 19/19, sole caller/body, full DAG parity, retired-ref zero, and diff
  check are maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

The characterization establishes no implementation or quality improvement.
Static definition/call/DAG/function-count and selected-body baseline inspection,
direct behavior probes 6/6, and caller gate/order/adoption probes 3/3 passed;
benchmark refresh and remote CI were **NOT RUN**.

### Single-report-scope ownership milestone

- Commit `471f6a5` moves the exact former 8-line
  `_has_single_report_scope(report_scope: Dict[str, Any]) -> bool` definition
  from `financial_graph_helpers.py` to public
  `financial_scope_policies.has_single_report_scope(...)` with its body and
  complete signature unchanged. The graph imports the public owner and no
  longer imports `_report_scope_source_receipts(...)`.
- The sole direct call finishes graph-external/owner-local 1/0 with exact
  positional `report_scope`, no keywords, caller `try` depth zero, and immediate
  `If` parent in `align_scope_hints(...)`. Its placement after company/year
  list preparation and the truthy scope-company gate but before company and
  later year adoption is unchanged.
- Raw scope truth, one shallow `dict` copy, nested identities, explicit receipt
  get/or/string/strip/truth precedence, source-receipt helper/length laziness,
  exact zero/one/many cardinality, the narrow `Exception` catch, uncaught pre-
  try and `BaseException` failures, caller fallback order, input immutability,
  and all stops are pinned by four CURRENT-SOURCE methods. No graph alias,
  wrapper, callback, carrier, reason, flag, trace, coercion, or fallback was
  added.
- Source is `+12/-12`, net zero: graph helpers are `+2/-12` and move from
  5,450 to 5,440 physical lines; scope policies are `+10/-0` and move from 529
  to 539. Graph-helper tests are `+620/-29`, net `+591`, and move from 23,816
  to 24,407 lines. The whole commit is `+632/-41`, net `+591`, and four methods
  move full discovery from 1,963 to 1,967. Graph helper public/private counts
  finish 9/85 and scope-policy counts finish 11/9. The source diff SHA-256 is
  `2deab9c118170b25431f43717bd2dc0328798416cbd3da18cc29891b7ab369cf`.
- Focused 4/4, graph-helper owner 114/114, affected eleven-module semantic
  1,074/1,074, import-side-effects 19/19, runtime-domain audit 218, and full
  discovery 1,967/1,967 passed. Pycompile, fresh import/public identity,
  whole-function/body parity, retained graph 94/94 after call normalization,
  retained scope owner 19/19, the sole caller/body, full 48-module/203-edge DAG
  parity, zero selected-body audit hits, zero retired executable private refs,
  and diff check also passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic single-report-scope ownership.
Company/year alignment, report inventory/selection, consolidation/candidate
scope policy, candidate/evidence construction, report-file I/O, retrieval,
score/rank/admission/acceptance, graph state, model invocation, artifact/ledger
mutation, retry, and final sequencing remain outside. It proves no behavior,
accuracy, ranking, performance, total-code or executed-path reduction,
benchmark improvement, schedule, ledger completion, or Phase 3 completion.

### Candidate-concept-conflict characterization checkpoint

- A docs-only inventory selects the current 27-line
  `_candidate_conflicts_with_operand_concept(candidate, operand)` graph
  definition. Before owner movement, its two inline exclusive-surface marker
  occurrences must become exact declarative
  `CANDIDATE_CONCEPT_CONFLICT_EXCLUSIVE_MARKER` in retrieval policy. Runtime
  keeps only generic marker membership and no domain-named control variable.
- The selected follow-on then moves the function as public
  `candidate_conflicts_with_operand_concept(...)` to
  `financial_surface_contracts.py`. That owner already contains normalization,
  operand-needle, surface-contract, positive-surface, and negative-surface
  dependencies. Graph already reaches it and it does not reach graph, so the
  48-module/203-edge DAG remains unchanged. Current/projected public/private
  counts are graph 9/85 to 9/84 and surface owner 10/7 to 11/7. Three calls
  project external/local 3/0; the current span has zero of 218 reviewed records.
- The projection preserves dropped-once/retained-twice operand normalization,
  exact policy-marker first-hit membership, one metadata shallow copy, ordered
  semantic/row/aggregate/alias/header authoritative surfaces, repeated retained
  alias/header strings, special-marker precedence and candidate-text exclusion,
  falsey-contract stop, authoritative negative-before-positive precedence, and
  final candidate-text negative fallback with exact returns and uncaught errors.
- All calls are positional exact `candidate, operand`, without keywords, at
  caller `try` depth zero and immediate `If` parents. Conflict truth returns
  `False` from candidate matching, `0.0` from direct strength, and `-10.0` from
  scoring after that caller's metadata copy. Moving the callers, other matching,
  direct/ratio acceptance, score/rank, construction/adoption, file I/O,
  retrieval, or graph/artifact/ledger state is rejected.
- Four named CURRENT-SOURCE methods and projected focused 4/4, owner 118/118,
  affected semantic 1,078/1,078, import 19/19, audit 218, full 1,971/1,971,
  public identity/policy-normalized body parity, retained graph 93/93, retained
  surface owner 17/17, all callers, full DAG parity, retired-ref zero, and diff
  check are maintained only in
  [Project Status Next Work](../overview/project_status.md#next-work).

No production source or test moved for this characterization. Static
definition/call/DAG/function-count and selected-body baseline inspection,
direct behavior probes 8/8, and caller gate/order/return probes 3/3 passed;
benchmark refresh and remote CI were **NOT RUN**.

### Candidate-concept-conflict ownership milestone

- Commit `4c8c89c` declares exact
  `CANDIDATE_CONCEPT_CONFLICT_EXCLUSIVE_MARKER = "부채"` in retrieval policy and
  moves the former 27-line graph predicate to public
  `financial_surface_contracts.candidate_conflicts_with_operand_concept(...)`.
  The old private definition and every executable private reference are gone;
  no graph alias or compatibility bridge was added.
- Repeated operand normalization, ordered semantic/row/aggregate/alias/header
  surface construction, shallow-copy identity, special-marker precedence and
  candidate-text exclusion, negative-before-positive-before-text fallback,
  exact returns, uncaught failures, input immutability, and caller stops remain
  pinned by four CURRENT-SOURCE methods.
- The three calls finish graph-external/owner-local 3/0, positional exact
  `candidate, operand`, with no keywords, caller `try` depth zero, and immediate
  `If` parents. Candidate matching still returns `False`, direct strength still
  returns `0.0`, and scoring still returns `-10.0` after its metadata copy when
  the conflict gate is truthy.
- Production source is `+36/-32`, net `+4`: graph helpers are `+4/-32` and move
  from 5,440 to 5,412 lines; surface contracts are `+30/-0` and move from 396
  to 426; retrieval policy is `+2/-0`. Tests plus fixture are `+1,004/-118`,
  net `+886`; graph-helper tests are `+962/-65`, net `+897`, and move from
  24,407 to 25,304 lines. The whole commit is `+1,040/-150`, net `+890`, and
  four methods move discovery from 1,967 to 1,971. Final public/private counts
  are graph 9/84 and surface owner 11/7. The source diff SHA-256 is
  `bf99e85d3326af212d057d1f6f6fff175768e71149fe44fdb6ae7e865a7b017a`.
- The runtime audit corrected the characterization's stale line-derived zero-
  hit claim. The two inline marker occurrences formed one grouped graph-path
  record; moving their only literal to excluded config reduces the reviewed
  baseline from 218 to 217. The fixture and every exact-count contract were
  updated without weakening comparison behavior.
- Focused 4/4, graph-helper owner 118/118, affected eleven-module semantic
  1,078/1,078, import-side-effects 19/19, runtime-domain audit 217, and full
  discovery 1,971/1,971 passed. Pycompile, fresh import/public identity,
  policy-normalized target body, retained graph exact 90/93 and normalized
  93/93, retained surface owner 17/17, all three callers, full
  48-module/203-edge DAG parity, zero retired private refs, non-ASCII diff audit,
  and diff check also passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic candidate concept-conflict ownership
and vocabulary placement. Other matching, acceptance, scoring/ranking,
candidate/evidence construction or adoption, report-file I/O, retrieval, graph
state, model invocation, artifact/ledger mutation, retry, and final sequencing
remain outside. It proves no behavior, accuracy, ranking, performance,
executed-path reduction, benchmark improvement, schedule, ledger completion,
or Phase 3 completion.

### Contextual-aggregate-preference characterization checkpoint

- A docs-only inventory selects the current exact 17-line
  `_operand_prefers_contextual_aggregate_match(operand)` graph definition for a
  future public move to
  `financial_surface_contracts.operand_prefers_contextual_aggregate_match(...)`.
  No production source or test moved for this projection.
- The function owns only one binding-policy shallow copy, eager preferred value-
  role and aggregation-stage list preparation, exact `aggregate` and
  `final`/`subtotal`/`direct` gates, and one positive surface-contract truth
  result. The surface owner already contains normalization and contract
  dependencies. Graph reaches it, it does not reach graph, and the full
  48-module/203-edge DAG remains unchanged.
- Current/projected public/private counts are graph 9/84 to 9/83 and surface
  owner 11/7 to 12/7. Three direct calls project external/local 3/0, each with
  exact positional `operand`, no keywords, caller `try` depth zero, and
  immediate `If` parent. Their source-priority, candidate-match, and direct-
  strength branches remain caller-owned.
- The projection preserves get/or/copy ordering, dropped-once and retained-
  twice stringification/strip behavior, one normalization per retained item,
  eager list order and duplicates, role-before-stage-before-contract
  precedence, exact case-sensitive membership, original operand identity at the
  contract call, final boolean return, nested identities, input immutability,
  and all uncaught failures.
- Moving caller branches, candidate context, positive-surface matching,
  value-role/stage projection, domain-qualified balance-sheet/capex/note
  predicates, source-priority scoring, other matching/direct-strength work,
  candidate/evidence construction or adoption, I/O, retrieval, or graph/
  artifact/ledger state is rejected.
- Four named CURRENT-SOURCE methods and projected focused 4/4, owner 122/122,
  affected semantic 1,082/1,082, import 19/19, audit 217, full 1,975/1,975,
  public identity/body parity, retained graph 92/92, retained surface owner
  18/18, all callers, full DAG parity, retired-ref zero, and diff check are
  governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/call/DAG/function-count and selected-body audit inspection,
direct behavior probes 8/8, and caller gate/argument probes 3/3 passed.
Benchmark refresh and remote CI were **NOT RUN**. This checkpoint is not a
behavior, quality, performance, benchmark, schedule, or completion claim.

### Contextual-aggregate-preference ownership milestone

- Commit `c837e31` moves the exact former 17-line
  `_operand_prefers_contextual_aggregate_match(operand)` definition from
  `financial_graph_helpers.py` to public
  `financial_surface_contracts.operand_prefers_contextual_aggregate_match(...)`
  with its body unchanged. The graph imports the public owner; the old private
  definition and every executable private reference are gone, with no alias or
  compatibility bridge.
- One binding-policy shallow copy, role-list-before-stage-list eager
  materialization, dropped-once/retained-twice stringification, one
  normalization per retained item, exact role/stage membership, positive-
  contract laziness and original operand identity, final boolean, nested
  identities, immutability, and uncaught failures are pinned by four
  CURRENT-SOURCE methods.
- The three graph calls finish external/local 3/0, positional exact `operand`,
  without keywords, at caller `try` depth zero and immediate `If` parents.
  Source-priority, candidate-match, and direct-strength contextual branches and
  all later caller work are unchanged.
- Production source is `+23/-22`, net `+1`: graph helpers are `+4/-22` and move
  from 5,412 to 5,394 physical lines; surface contracts are `+19/-0` and move
  from 426 to 445. Graph-helper tests are `+1,084/-32`, net `+1,052`, and move
  from 25,304 to 26,356 lines. The whole commit is `+1,107/-54`, net `+1,053`,
  and four methods move discovery from 1,971 to 1,975. Final public/private
  counts are graph 9/83 and surface owner 12/7. The source diff SHA-256 is
  `23f01c478d1d63b68e4f499254fa43ecc388bc0a53cd0b6391ce6f238f044fc5`.
- Focused 4/4, graph-helper owner 122/122, affected eleven-module semantic
  1,082/1,082, import-side-effects 19/19, runtime-domain audit 217, and full
  discovery 1,975/1,975 passed. Pycompile, fresh import/public identity 2/2,
  selected-body parity 1/1, retained graph exact 89/92 and call-normalized
  92/92, retained surface owner 18/18, all three callers, full
  48-module/203-edge DAG parity, zero retired private refs, non-ASCII
  preservation, and diff check also passed. Benchmark refresh and remote CI
  were **NOT RUN**.

This milestone changes only deterministic contextual-aggregate-preference
ownership. Candidate-context construction, positive-surface matching,
value-role/stage projection, domain-qualified predicates, source-priority and
other matching/strength work, candidate/evidence construction or adoption,
I/O, retrieval, graph state, model invocation, artifact/ledger mutation, retry,
and final sequencing remain outside. It proves no behavior, accuracy, ranking,
performance, executed-path reduction, benchmark improvement, schedule, ledger
completion, or Phase 3 completion.

### Balance-sheet-aggregate-operand characterization checkpoint

- A docs-only inventory selects the current exact 9-line
  `_is_balance_sheet_aggregate_operand(operand)` graph definition for a future
  public move to
  `financial_surface_contracts.is_balance_sheet_aggregate_operand(...)`. No
  production source or test moved for this projection.
- The predicate calls `_operand_needles(operand)` once, normalizes and removes
  whitespace from every returned needle into a fresh set, discards exact blank,
  then builds a second set from declarative
  `HELPER_RUNTIME_POLICY["balance_sheet_aggregate_labels"]`. It returns only
  native-set membership through `any(...)`; it does not own the policy values,
  candidate work, scoring, or acceptance.
- Needle preparation preserves direct normalization without local string/filter
  work, positional regex substitution, set hashing/equality/dedupe, full
  materialization, then one blank discard. Policy preparation preserves exact
  get/or, filter `str(item)` without strip, second retained-item stringification,
  normalization/substitution, eager `set(...)`, duplicate collapse, and no
  second-set blank discard. Native set iteration, first-hit membership, exact
  result, identities, immutability, and every uncaught error remain normative.
- The surface owner already owns `_operand_needles(...)` and imports `re`,
  `_normalise_spaces`, and `HELPER_RUNTIME_POLICY`. Graph reaches it, it does not
  reach graph, and the full 48-module/203-edge DAG remains unchanged. Current/
  projected public/private counts are graph 9/83 to 9/82 and surface owner 12/7
  to 13/7; the selected span has zero of 217 reviewed runtime-domain records.
- Two direct calls project external/local 2/0, each positional exact `operand`,
  with no keywords, caller `try` depth zero, and immediate `If` parent. Source
  priority calls at body statement 1/6 after score initialization; direct
  acceptance calls at statement 13/19 after canonical guards and before capex/
  period/final work. Existing scoring and notes-detail rejection remain caller-
  owned; helper or result-truth failures stop later work.
- Four named CURRENT-SOURCE methods and projected focused 4/4, owner 126/126,
  affected semantic 1,086/1,086, import 19/19, audit 217, full 1,979/1,979,
  public identity/body parity, retained graph 91/91, retained surface owner
  19/19, both callers, full DAG parity, retired-ref zero, and diff check are
  governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/call/DAG/function-count and selected-body audit inspection,
direct behavior probes 6/6, and caller gate/branch probes 3/3 passed. Benchmark
refresh and remote CI were **NOT RUN**. This checkpoint is not a behavior,
quality, performance, benchmark, schedule, or completion claim.

### Balance-sheet-aggregate-operand ownership milestone

- Commit `f35be1a` moves the exact former 9-line
  `_is_balance_sheet_aggregate_operand(operand)` definition from
  `financial_graph_helpers.py` to public
  `financial_surface_contracts.is_balance_sheet_aggregate_operand(...)` with
  its body unchanged. The graph imports the public owner; the old private
  definition and every executable private reference are gone, with no alias or
  compatibility bridge.
- Operand-needle normalization/whitespace removal into a fresh set, full
  materialization, dedupe, exact blank discard, declarative policy get/or and
  second-set construction, filter-versus-expression string conversion, native
  set membership, exact result, original identities, immutability, and every
  uncaught failure remain pinned by four CURRENT-SOURCE methods.
- The two graph calls finish external/local 2/0, positional exact `operand`,
  without keywords, at caller `try` depth zero and immediate `If` parents.
  Source-priority scoring and direct-acceptance notes-detail rejection plus all
  later caller work are unchanged.
- Production source is `+14/-13`, net `+1`: graph helpers are `+3/-13` and move
  from 5,394 to 5,384 physical lines; surface contracts are `+11/-0` and move
  from 445 to 456. Graph-helper tests are `+1,014/-34`, net `+980`, and move
  from 26,356 to 27,336 lines. The whole commit is `+1,028/-47`, net `+981`,
  and four methods move discovery from 1,975 to 1,979. Final public/private
  counts are graph 9/82 and surface owner 13/7. The source diff SHA-256 is
  `e9e8b46382ecdb20982d1ec90c19343aec4a8b769d3812272a54da930dd00f51`.
- Focused 4/4, graph-helper owner 126/126, affected eleven-module semantic
  1,086/1,086, import-side-effects 19/19, runtime-domain audit 217, and full
  discovery 1,979/1,979 passed. Pycompile, fresh import/public identity 2/2,
  selected-body parity 1/1, retained graph exact 89/91 and call-normalized
  91/91, retained surface owner 19/19, both callers, full 48-module/203-edge DAG
  parity, zero retired private refs, non-ASCII preservation, and diff check also
  passed. The first full-suite attempt hit only the 60-second command wrapper;
  the identical command rerun with a longer deadline passed in 104.415 seconds.
  Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic balance-sheet-aggregate-operand
ownership. Policy vocabulary, operand-needle ownership, caller scoring and
acceptance, CAPEX/contextual/note predicates, other matching/scoring/ranking,
candidate/evidence construction or adoption, I/O, retrieval, graph state,
model invocation, artifact/ledger mutation, retry, and final sequencing remain
outside. It proves no behavior, accuracy, ranking, performance, total-code or
executed-path reduction, benchmark improvement, schedule, ledger completion,
or Phase 3 completion.

### CAPEX-total-operand policy-and-owner characterization checkpoint

- A docs-only inventory selects the current exact 13-line
  `_is_capex_total_operand(operand)` graph definition for a future public move
  to `financial_surface_contracts.is_capex_total_operand(...)`. It also selects
  only the inline `capital_expenditure_total` ontology identifier for
  declaration as retrieval-policy constant `CAPEX_TOTAL_CONCEPT_KEY`. No
  production source or test moved for this projection.
- The predicate stringifies and strips the operand concept first; exact concept
  equality returns `True` before operand-needle or scoring-policy access. A
  nonmatch prepares normalized/whitespace-removed operand needles in a fresh
  set, discards exact blank, shallow-copies
  `OPERAND_CANDIDATE_SCORING_POLICY`, eagerly prepares its configured
  `capex_total_surfaces` in a second set, and returns native-set membership via
  `any(...)`.
- Concept get/or/string/strip and early-return precedence, no case folding,
  direct needle normalization without local string/filter work, positional
  regex substitution, set materialization/dedupe/discard, policy dict copy,
  dropped/retained surface stringification and strip behavior, native set
  iteration, exact result, identities, immutability, and every uncaught error
  remain normative. Only the literal-to-policy-name substitution is allowed.
- The surface owner already owns `_operand_needles(...)`, imports `re` and
  `_normalise_spaces`, and reaches retrieval policy; graph reaches it and it
  does not reach graph. Adding the two policy imports creates no module edge.
  The full 48-module/203-edge DAG remains unchanged. Current/projected public/
  private counts are graph 9/82 to 9/81 and surface owner 13/7 to 14/7; the
  selected span has zero of 217 reviewed runtime-domain records.
- Four direct calls project external/local 4/0, each positional exact `operand`,
  with no keywords, caller `try` depth zero, and immediate `If` parent. Source
  priority calls at body statement 2/6, direct acceptance at 14/19, candidate
  matching at 15/19, and direct strength at 8/15. Existing score, reject,
  preferred-section/positive-surface match, and strength branches remain
  caller-owned; helper or result-truth failures stop later work.
- Four named CURRENT-SOURCE methods and projected focused 4/4, owner 130/130,
  affected semantic 1,090/1,090, import 19/19, audit 217, full 1,983/1,983,
  public identity, policy-normalized body parity, retained graph 90/90,
  retained surface owner 20/20, all four callers, full DAG parity, retired-ref
  zero, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/call/DAG/function-count and ontology/policy/selected-body
audit inspection, direct behavior probes 6/6, and caller branch probes 4/4
passed. Benchmark refresh and remote CI were **NOT RUN**. This checkpoint is not
a behavior, quality, performance, benchmark, schedule, or completion claim.

### CAPEX-total-operand policy-and-owner milestone

- Commit `cefde44` declares the inline canonical ontology key as retrieval-
  policy `CAPEX_TOTAL_CONCEPT_KEY` and moves the exact former 13-line
  `_is_capex_total_operand(operand)` definition from graph helpers to public
  `financial_surface_contracts.is_capex_total_operand(...)`. The concept
  literal-to-policy-name substitution is the only body delta. The old private
  definition and executable private refs are gone without an alias or bridge.
- Concept get/string/strip and early-return precedence, operand-needle set
  preparation and blank discard, scoring-policy shallow copy and configured
  surface-set preparation, filter-versus-expression stringification, native-
  set membership, exact result, identities, immutability, and uncaught failures
  remain pinned by four CURRENT-SOURCE methods.
- Four graph calls finish external/local 4/0, positional exact `operand`, with
  no keywords, caller `try` depth zero, and immediate `If` parents. Source-
  priority scoring, direct acceptance, candidate matching, direct strength,
  and every later caller branch remain unchanged and graph-owned.
- Production source is `+23/-19`, net `+4`: graph helpers are `+5/-19` and move
  from 5,384 to 5,370 physical lines; surface contracts are `+17/-0` and move
  from 456 to 473; retrieval policy is `+1/-0` and moves from 2,070 to 2,071.
  Graph-helper tests are `+1,364/-58`, net `+1,306`, and move from 27,336 to
  28,642 lines. The whole commit is `+1,387/-77`, net `+1,310`, and four methods
  move discovery from 1,979 to 1,983. Final public/private counts are graph
  9/81 and surface owner 14/7. The source diff SHA-256 is
  `3fcf523be5e9727cbc0b902beb30a899051d288a01459af8799da45071ec02d8`.
- Focused 4/4, graph-helper owner 130/130, affected eleven-module semantic
  1,090/1,090, import-side-effects 19/19, runtime-domain audit 217, and full
  discovery 1,983/1,983 passed. Pycompile, fresh import/public identity 2/2,
  policy-normalized selected-body parity 1/1, retained graph exact 86/90 and
  call-normalized 90/90, retained surface owner 20/20, all four callers, full
  48-module/203-edge DAG parity, zero retired private refs, non-ASCII
  preservation, and diff check also passed. Benchmark refresh and remote CI
  were **NOT RUN**.

This milestone changes only deterministic policy naming and CAPEX-total-
operand classification ownership. Policy values, ontology contents, operand-
needle ownership, caller scoring/acceptance/matching/strength, other predicates,
candidate/evidence construction or adoption, I/O, retrieval, graph state,
model invocation, artifact/ledger mutation, retry, and final sequencing remain
outside. It proves no behavior, accuracy, ranking, performance, benchmark,
schedule, ledger completion, or Phase 3 completion.

### Note-aggregate lookup-preference characterization checkpoint

- A docs-only inventory selects the current exact 23-line
  `_operand_prefers_note_aggregate_lookup(operand)` graph definition for a
  future public move to
  `financial_surface_contracts.operand_prefers_note_aggregate_lookup(...)`. No
  production source or test moved for this projection.
- The predicate eagerly builds a normalized preferred-statement-type set and
  returns exact `False` before binding-policy access unless exact `notes` is
  present. It then shallow-copies binding policy, eagerly builds preferred-
  value-role and preferred-aggregation-stage sets in that order, and returns
  exact aggregate-role membership combined with a boolean intersection against
  exact final/subtotal/direct stages.
- Raw get/or ordering, dropped-once and retained-twice stringification/strip,
  one normalization per retained item, set hashing/equality/dedupe, complete
  materialization, note-gate laziness, mapping-copy identities, role-before-
  stage order, case-sensitive membership/intersection, input immutability, and
  every uncaught failure remain normative.
- The destination already imports `Dict`, `Any`, and `_normalise_spaces`; graph
  reaches it and it does not reach graph. The full 48-module/203-edge DAG stays
  unchanged. Current/projected public/private counts are graph 9/81 to 9/80 and
  surface owner 14/7 to 15/7; the selected span has zero of 217 reviewed
  runtime-domain records.
- One direct call projects external/local 1/0, positional exact `operand`, with
  no keywords, caller `try` depth zero, and immediate `If` parent at exact
  `_candidate_source_priority_bonus` body index 4/6. The existing structured-
  value and table-row score branch remains caller-owned; predicate falsehood
  keeps candidate metadata untouched and helper/result-truth failure stops all
  later work.
- Four named CURRENT-SOURCE methods and projected focused 4/4, owner 134/134,
  affected semantic 1,094/1,094, import 19/19, audit 217, full 1,987/1,987,
  public identity, selected-body parity, retained graph call-normalized 89/89,
  retained surface owner 21/21, sole caller, full DAG parity, retired-ref zero,
  and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/call/DAG/function-count/import and selected-body audit
inspection, direct behavior probes 6/6, note-gate laziness 1/1, caller score
probes 5/5, and caller-gate laziness 1/1 passed. Benchmark refresh and remote CI
were **NOT RUN**. This checkpoint is not a behavior, quality, performance,
benchmark, schedule, or completion claim.

### Note-aggregate lookup-preference ownership milestone

- Commit `1119ac3` moves the exact former 23-line
  `_operand_prefers_note_aggregate_lookup(operand)` definition from graph
  helpers to public
  `financial_surface_contracts.operand_prefers_note_aggregate_lookup(...)` with
  its body unchanged. The graph imports the public owner; the old private
  definition and executable private refs are gone without an alias or bridge.
- Statement-type set materialization and note short circuit, binding-policy
  shallow copy, value-role-set-before-stage-set construction, filter-versus-
  expression stringification, case-sensitive membership/intersection,
  identities, input immutability, and every uncaught failure remain pinned by
  four CURRENT-SOURCE methods.
- The one graph call finishes external/local 1/0, positional exact `operand`,
  without keywords, caller `try` depth zero, and immediate `If` parent.
  Candidate metadata reads and structured-value/table-row note score remain in
  source-priority scoring and all later graph work is unchanged.
- Production source is `+27/-26`, net `+1`: graph helpers are `+2/-26` and move
  from 5,370 to 5,346 physical lines; surface contracts are `+25/-0` and move
  from 473 to 498. Graph-helper tests are `+987/-36`, net `+951`, and move from
  28,642 to 29,593 lines. The whole commit is `+1,014/-62`, net `+952`, and four
  methods move discovery from 1,983 to 1,987. Final public/private counts are
  graph 9/80 and surface owner 15/7. The source diff SHA-256 is
  `0426929d4ef1e09147f9a21dbd661c595fea67a01e38e30f03d81144250e494c`.
- Focused 4/4, graph-helper owner 134/134, affected eleven-module semantic
  1,094/1,094, import-side-effects 19/19, runtime-domain audit 217, and full
  discovery 1,987/1,987 passed. Pycompile, fresh import/public identity 2/2,
  selected-body parity 1/1, retained graph exact 88/89 and call-normalized
  89/89, retained surface owner 21/21, sole caller, full 48-module/203-edge DAG
  parity, zero retired private refs, non-ASCII preservation, and diff check also
  passed. The first affected-set command used system Python and failed only on
  missing `langchain_core`/`dotenv`; the identical project-`.venv` command
  passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic note-aggregate preference ownership.
Schema vocabulary, candidate metadata/value-role/stage preparation, source-
priority weights and branching, broader matching/acceptance/scoring/ranking,
candidate/evidence construction or adoption, I/O, retrieval, graph state,
model invocation, artifact/ledger mutation, retry, and final sequencing remain
outside. It proves no behavior, accuracy, ranking, performance, benchmark,
schedule, ledger completion, or Phase 3 completion.

### Candidate source-priority score characterization checkpoint

- A docs-only inventory selects the current exact 76-line
  `_candidate_source_priority_bonus(...)` graph definition for a future public
  move to `financial_operand_resolution.candidate_source_priority_bonus(...)`.
  No production source or test moved for this projection.
- The scorer initializes zero, then applies balance-sheet, CAPEX, contextual-
  aggregate, and note-aggregate branches in exact order. It preserves current
  statement/kind/role/stage gates, declarative policy copies and marker
  materialization, positive-surface and candidate-context laziness, exact
  weights, cumulative arithmetic, final float, identities, immutability, and
  all uncaught failures.
- Operand resolution already imports normalization, scoring policy, and the
  surface-contract module. Adding the remaining public surface names creates no
  edge. The full 48-module/203-edge DAG stays unchanged. Current/projected
  public/private counts are graph 9/80 to 9/79 and operand resolution 45/37 to
  46/37; the selected span has zero of 217 reviewed runtime-domain records.
- One direct call projects external/local 1/0 at exact
  `_score_operand_candidate` body index 56/62, positional exact `candidate`
  plus exact operand/statement-type/value-role/aggregation-stage/local-heading
  keywords, caller `try` depth zero, and immediate `AugAssign` parent. The
  already accumulated score and later period/table/report work remain graph-
  owned; helper or addition failure stops all later work.
- Four named CURRENT-SOURCE methods and projected focused 4/4, owner 138/138,
  affected semantic 1,098/1,098, import 19/19, audit 217, full 1,991/1,991,
  public identity, selected-body parity, retained graph call-normalized 88/88,
  retained operand owner 82/82, sole caller, full DAG parity, retired-ref zero,
  and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/call/DAG/function-count/import and selected-body audit
inspection, direct score probes 9/9, gate order 4/4, false-gate laziness 1/1,
immutability/identity 1/1, gate-failure stops 4/4, caller adoption 1/1, and
caller-failure stop 1/1 passed. Benchmark refresh and remote CI were **NOT
RUN**. This checkpoint is not a behavior, quality, performance, benchmark,
schedule, or completion claim.

### Candidate source-priority score ownership milestone

- Commit `334fff0` moves the exact former 76-line
  `_candidate_source_priority_bonus(...)` definition from graph helpers to
  public
  `financial_operand_resolution.candidate_source_priority_bonus(...)` with its
  body unchanged. The old private definition and executable private refs are
  gone without an alias or bridge.
- Balance-sheet, CAPEX, contextual-aggregate, and note-aggregate branch order,
  every score weight, policy and candidate access laziness, shallow copies,
  cumulative arithmetic, identities, input immutability, and all uncaught
  failures remain pinned by four CURRENT-SOURCE methods.
- The sole graph call finishes external/local 1/0 inside
  `_score_operand_candidate(...)`, positional exact `candidate` plus five exact
  keywords, caller `try` depth zero, and immediate `AugAssign`. Broad scoring,
  later period/table/report work, ranking, acceptance, and adoption remain
  graph-owned.
- Production source is `+85/-80`, net `+5`: graph helpers are `+2/-80` and move
  from 5,346 to 5,268 physical lines; operand resolution is `+83/-0` and moves
  from 3,759 to 3,842. Tests are `+993/-152`, net `+841`; graph-helper tests
  move from 29,593 to 30,434 lines. The whole commit is `+1,078/-232`, net
  `+846`, and four methods move discovery from 1,987 to 1,991. Final counts are
  graph 9/79 and operand resolution 46/37. The source diff SHA-256 is
  `83b28fa8e35aae9a69981142c705b38a85c471148683c69f470999acc3f1914e`.
- Focused 4/4, owner 138/138, affected eleven-module semantic 1,098/1,098,
  import-side-effects 19/19, runtime-domain audit 217, and full discovery
  1,991/1,991 passed. Pycompile, fresh import/public identity 2/2, selected-body
  parity 1/1, retained graph exact 87/88 and call-normalized 88/88, all 82
  retained operand-resolution functions, sole caller, full 48-module/203-edge
  DAG parity, zero retired private refs, non-ASCII preservation, and diff check
  also passed. The first affected-set run failed only two absolute source-line
  contracts after insertion; measured AST positions were updated and the
  identical 1,098-test set passed. Benchmark refresh and remote CI were **NOT
  RUN**.

This milestone changes only deterministic source-priority score ownership. It
proves no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

### Candidate-to-operand matching characterization checkpoint

- A docs-only inventory selects the current exact 83-line
  `_candidate_matches_operand(candidate, operand)` graph definition for a
  future public move to
  `financial_operand_resolution.candidate_matches_operand(...)`. No production
  source or test moved for this projection.
- The predicate preserves exact concept-conflict, structured-surface, CAPEX,
  contextual-aggregate, structured-miss, and unstructured-text-fallback
  precedence across 19 top-level statements and eleven returns. Candidate and
  metadata reads, eager iterable materialization, repeated conversion/strip,
  joins, normalization, gate laziness, short circuits, identities, shallow-copy
  immutability, exact final match object, and every uncaught failure remain
  normative.
- Operand resolution already reaches the surface and row-surface owners. Adding
  `candidate_conflicts_with_operand_concept`, `aggregate_like_row_stage`,
  `candidate_aggregation_stage`, and `candidate_value_role` creates no edge.
  The full 48-module/203-edge DAG stays unchanged. Current/projected counts are
  graph 9/79 to 9/78 and operand resolution 46/37 to 47/37; the selected span
  has zero of 217 reviewed runtime-domain records.
- One direct call projects external/local 1/0 in the exact
  `_deterministic_reconcile_task(...)` list-comprehension filter, positional
  exact `candidate, operand`, no keywords, caller `try` depth zero, original
  iteration order and identities. Helper truth adopts the original candidate;
  call or result-truth failure stops remaining candidates and later filtering,
  ranking, acceptance, projection, retry-query work, and return.
- Four named CURRENT-SOURCE methods and projected focused 4/4, owner 142/142,
  affected semantic 1,102/1,102, import 19/19, audit 217, full 1,995/1,995,
  public identity, selected-body parity, retained graph call-normalized 87/87,
  retained operand owner 83/83, sole caller, full DAG parity, retired-ref zero,
  non-ASCII preservation, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/call/DAG/function-count/import and selected-body audit
inspection, direct behavior probes 12/12, gate/access-order probes 2/2, caller
iteration/identity adoption 1/1, and call/result-truth failure stops 2/2
passed. Benchmark refresh and remote CI were **NOT RUN**. This checkpoint is
not a behavior, quality, performance, benchmark, schedule, or completion
claim.

### Candidate-to-operand matching ownership milestone

- Commit `1a24bc1` moves the exact former 83-line
  `_candidate_matches_operand(candidate, operand)` graph definition to public
  `financial_operand_resolution.candidate_matches_operand(...)` with the body
  unchanged. The old private definition and executable private references are
  gone without a wrapper or compatibility bridge.
- The four CURRENT-SOURCE methods pin 19 top-level statements, eleven returns,
  concept-conflict and structured-surface precedence, CAPEX/contextual
  branches, structured miss, unstructured fallback, eager materialization,
  repeated conversion/strip, joins, normalization, short circuits, identities,
  shallow-copy immutability, exact final match object, and every uncaught
  failure.
- The pre-move characterization recorded only the deterministic graph filter.
  Live source inventory found two additional executable direct callers: active
  reconciliation reranking and the ops ontology-shadow filter. The two agent
  list comprehensions and the ops negated `If` now bind the public owner with
  positional exact `candidate, operand`, no keywords, and caller `try` depth
  zero. Static CURRENT-SOURCE coverage pins all three. This corrects the old
  inventory; it does not create a new runtime path.
- Production source is `+96/-90`, net `+6`: graph helpers move from 5,268 to
  5,184 physical lines and operand resolution from 3,842 to 3,931. Tests are
  `+1,410/-230`, net `+1,180`; graph-helper tests move from 30,434 to 31,614.
  The whole commit is `+1,506/-320`, net `+1,186`, and four methods move full
  discovery from 1,991 to 1,995. Final counts are graph 9/78 and operand
  resolution 47/37. The source diff SHA-256 is
  `4774eaf925d6dcbc9e0d6da1cc268b889096b4ce9089e13a436bb5fdd41c987a`.
- Focused pre/post movement 4/4, graph owner 142/142, operand owner 69/69,
  affected eleven-module semantic 1,102/1,102, reconciliation plan 51/51,
  import-side-effects 19/19, runtime-domain audit 217, and full discovery
  1,995/1,995 passed. Pycompile, fresh public identity across owner/graph/
  reconciliation/ops, exact body parity, retained graph exact 86/87 and call-
  normalized 87/87, all 83 retained operand functions, all three normalized
  caller bodies, full 48-module/203-edge DAG parity, retired private refs zero,
  non-ASCII preservation, and diff check passed.
- The first graph-owner run after movement exposed 34 stale owner/count/patch
  contracts and no production-behavior failure; they were updated to the new
  boundary and 142/142 passed. The first operand-owner run then failed only two
  absolute source-line contracts after insertion; measured AST positions were
  updated and 69/69 passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic candidate-matching ownership. It
proves no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

### Candidate direct-match-strength characterization checkpoint

- A docs-only inventory selects the current exact 122-line
  `_candidate_direct_match_strength(candidate, operand)` graph definition for a
  future public move to
  `financial_operand_resolution.candidate_direct_match_strength(...)`. No
  production source or test moved for this projection.
- The scorer has 15 top-level statements, two returns, no `try`, and zero of
  217 reviewed runtime-domain records. It preserves conflict-first `0.0`, a
  shallow metadata copy, exact weighted surface order, non-table extension,
  per-surface exact/variant/half-weight fallback, CAPEX/contextual/aggregate-
  signal/lookup-context/segment branches, `max` accumulation, exact float
  results, identities, immutability, and all uncaught failures.
- Operand resolution already holds every dependency except public
  `candidate_has_operand_context_surface(...)` and
  `candidate_supports_segment_metric_combo(...)` from row surfaces. Adding
  those names creates no edge. The full 48-module/203-edge DAG stays unchanged;
  current/projected counts are graph 9/78 to 9/77 and operand resolution 47/37
  to 48/37.
- Eight direct calls across six graph callers remain positional exact
  `candidate, operand`, with no keywords and caller `try` depth zero. They keep
  canonical-winner `< 2.5`, semantic-priority tuple use, direct-grounding
  `< 1.0`, direct-acceptance `< 2.0`, ratio-acceptance `>= 1.0` and `< 2.0`,
  broad-score addition, and structured bonus thresholds in their exact lazy
  positions. Caller thresholds, duplicate evaluation, later work, and stops do
  not move.
- Four named CURRENT-SOURCE methods and projected focused 4/4, owner 146/146,
  affected semantic 1,106/1,106, import 19/19, audit 217, full 1,999/1,999,
  selected-body parity, retained graph call-normalized 86/86, retained operand
  owner 84/84, all eight calls/six callers, full DAG parity, retired-ref zero,
  non-ASCII preservation, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/call/DAG/function-count/import and selected-body audit
inspection passed. Benchmark refresh and remote CI were **NOT RUN**. This
checkpoint is not a behavior, quality, performance, benchmark, schedule, or
completion claim.

### Candidate direct-match-strength ownership milestone

- Commit `91ceae7` moves the exact former 122-line
  `_candidate_direct_match_strength(candidate, operand)` graph definition to
  public
  `financial_operand_resolution.candidate_direct_match_strength(...)` with the
  body unchanged. The old private definition and executable private references
  are gone without a wrapper or compatibility bridge.
- Four CURRENT-SOURCE methods pin the 15-statement/two-return body, conflict-
  first stop, weighted base-surface order, non-table extension, exact/variant/
  half-weight fallback, specialized branch order, repeated calls and eager
  materialization, short circuits, exact float results, identities,
  immutability, and every uncaught failure.
- All eight direct calls across six graph callers now bind the public owner with
  positional exact `candidate, operand`, no keywords, and caller `try` depth
  zero. Their thresholds, additions, tuple conversion, duplicate evaluation,
  acceptance, ranking, and adoption remain graph-owned. Live source confirms
  the ratio-component fallback rejection is `< 1.0`; the historical pre-move
  prose that recorded `< 2.0` was stale and is not a behavior change.
- Production source is `+135/-138`, net `-3`: graph helpers move from 5,184 to
  5,055 physical lines and operand resolution from 3,931 to 4,057. Tests are
  `+1,078/-226`, net `+852`; graph-helper tests move from 31,614 to 32,466. The
  whole commit is `+1,213/-364`, net `+849`, and four methods move full
  discovery from 1,995 to 1,999. Final counts are graph 9/77 and operand
  resolution 48/37. The source diff SHA-256 is
  `fb7cf8e1824f26bc4fd54a303602491f79956eb277d999e2fd45872c0e361de3`.
- Focused pre/post movement 4/4, graph owner 146/146, operand owner 69/69,
  affected eleven-module semantic 1,106/1,106, reconciliation plan 51/51,
  import-side-effects 19/19, runtime-domain audit 217, and full discovery
  1,999/1,999 passed. Pycompile, fresh public identity 1/1, exact selected-body
  parity 1/1, retained graph exact 80/86 and call-normalized 86/86, all 84
  retained operand functions, all eight calls/six callers, full 48-module/
  203-edge DAG parity, retired private refs zero, non-ASCII preservation 5/5,
  and diff check passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic candidate direct-match-strength
ownership. It proves no behavior, accuracy, ranking, performance, benchmark,
schedule, ledger, or Phase 3 completion claim.

### Direct-candidate semantic-priority characterization checkpoint

- A docs-only inventory selects the current exact 53-line
  `_direct_candidate_semantic_priority(candidate, *, operand,
  preferred_statement_types, query_years)` graph definition for a future public
  move to
  `financial_operand_resolution.direct_candidate_semantic_priority(...)`. No
  production source or test moved for this projection.
- The projection preserves 19 top-level statements, one return, no `try`, the
  exact five-integer return annotation, metadata and binding-policy shallow
  copies, three eager normalization comprehensions, repeated conversion and
  normalization, fixed value-role/stage/strength/year helper order, independent
  zero ranks, `len - first index` preference ranking, target-year and structured-
  value truth projection, exact tuple order, integer truncation, identities,
  immutability, and every uncaught failure.
- Operand resolution already owns all dependencies except public
  `candidate_matches_operand_target_year(...)` from scope policy. Adding that
  direct edge keeps the graph acyclic while moving the full DAG from 48 modules/
  203 edges to 48/204. Current/projected counts are graph 9/77 to 9/76 and
  operand resolution 48/37 to 49/37; the selected span has zero of 217 reviewed
  runtime-domain records.
- Three direct calls project external/local 3/0 in the sole
  `_deterministic_reconcile_task(...)` caller, all under body statement index
  9/17 and caller `try` depth zero. The sort-key call keeps the prepared entry
  copy before score with reverse ordering; the other two recompute from ranked
  entries zero and one before strict tuple comparison. Collection sorting,
  fallback, collapse/adoption, broad scoring, acceptance, and later work remain
  graph-owned; every call/helper/comparison failure keeps its current stop.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  150/150, operand owner 69/69, affected semantic 1,110/1,110, reconciliation
  plan 51/51, import 19/19, audit 217, full 2,003/2,003, public identity,
  selected-body parity, retained graph call-normalized 85/85, retained operand
  owner 85/85, all three calls/one caller, full acyclic DAG parity, retired-ref
  zero, non-ASCII preservation, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/call/DAG/function-count/import and selected-body audit
inspection, direct rank/order/identity/immutability, and failure-stop probes
passed. Benchmark refresh and remote CI were **NOT RUN**. This checkpoint is not
a behavior, quality, ranking, performance, benchmark, schedule, or completion
claim.

### Direct-candidate semantic-priority ownership milestone

- Commit `1be4cad` moves the exact former 53-line
  `_direct_candidate_semantic_priority(candidate, *, operand,
  preferred_statement_types, query_years)` graph definition to public
  `financial_operand_resolution.direct_candidate_semantic_priority(...)` with
  the 19-statement/one-return body unchanged. The old private definition and
  executable private references are gone without a wrapper or compatibility
  bridge.
- Four CURRENT-SOURCE methods pin both metadata/binding-policy shallow copies,
  the three eager normalization comprehensions and repeated retained-item work,
  helper order, independent ranks, `len - first index`, target-year/structured-
  value truth projection, tuple order, integer truncation, exact identities,
  immutability, and every uncaught failure.
- All three direct calls in the sole `_deterministic_reconcile_task(...)` caller
  now bind the public owner. Sort-key candidate copying before float score,
  reverse order, top/next recomputation, strict comparison, score fallback,
  collapse, and adoption remain graph-owned.
- Production source is `+60/-58`, net `+2`: graph helpers move from 5,055 to
  5,001 physical lines and operand resolution from 4,057 to 4,113. Tests are
  `+1,332/-109`, net `+1,223`; graph-helper tests move from 32,466 to 33,689.
  The whole commit is `+1,392/-167`, net `+1,225`, and four methods move full
  discovery from 1,999 to 2,003. Final counts are graph 9/76 and operand
  resolution 49/37. The source diff SHA-256 is
  `6fe4cf715b6ea401a379f3ca40725ad7ea25e8b0bae16deb0752433f3937d304`.
- Focused pre/post movement 4/4, graph owner 150/150, operand owner 69/69,
  affected eleven-module semantic 1,110/1,110, reconciliation plan 51/51,
  import-side-effects 19/19, runtime-domain audit 217, and full discovery
  2,003/2,003 passed. Pycompile, fresh public identity 1/1, exact selected-body
  parity 1/1, retained graph exact 84/85 and call-normalized 85/85, all 85
  retained operand functions, all three calls/one caller, full 48-module/
  204-edge acyclic DAG parity, retired private refs zero, non-ASCII preservation
  4/4, and diff check passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic direct-candidate semantic-priority
ownership. It proves no behavior, accuracy, ranking, performance, benchmark,
schedule, ledger, or Phase 3 completion claim.

### Canonical-statement-winner characterization checkpoint

- A docs-only inventory selects the current exact 42-line
  `_candidate_is_canonical_statement_winner(candidate, *, operand,
  query_years)` graph definition for a future public move to
  `financial_operand_resolution.candidate_is_canonical_statement_winner(...)`.
  No production source or test moved for this projection.
- The projection preserves 17 top-level statements, seven returns, no `try`,
  exact boolean results, preference-first early stop, metadata/policy shallow
  copies, statement-type and heading/section fallback order, eager marker tuple
  and retained-item double conversion, marker-outer/section-inner iteration,
  repeated canonical-section normalization, all generator/`any` short circuits,
  exact `< 2.5` threshold, target-year truth, period-focus fallback, identities,
  immutability, and every uncaught failure.
- Operand resolution already owns all dependencies and its existing scope-policy
  edge only needs the public `operand_period_focus(...)` name. The full DAG
  stays acyclic at 48 modules/204 edges. Current/projected counts are graph 9/76
  to 9/75 and operand resolution 49/37 to 50/37; the selected span has zero of
  217 reviewed runtime-domain records.
- One direct call projects external/local 1/0 in
  `_deterministic_reconcile_task(...)`, under body statement index 9/17 and
  caller `try` depth zero. It keeps exact candidate/operand/year arguments and
  its direct-entry dictionary position after broad score. Storage under
  `canonical_winner`, later rank/collapse/adoption, direct-entry construction,
  sorting, scoring, and acceptance remain graph-owned; every failure keeps its
  current stop before append.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  154/154, operand owner 69/69, affected semantic 1,114/1,114, reconciliation
  plan 51/51, import 19/19, audit 217, full 2,007/2,007, public identity,
  selected-body parity, retained graph call-normalized 84/84, retained operand
  owner 86/86, sole call/caller, full acyclic DAG parity, retired-ref zero,
  non-ASCII preservation, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/call/DAG/function-count/import and selected-body audit
inspection passed. Direct branch/laziness/identity probes passed 8/8 and related
caller probes passed 3/3. Benchmark refresh and remote CI were **NOT RUN**. This
checkpoint is not a behavior, quality, ranking, performance, benchmark,
schedule, or completion claim.

### Canonical-statement-winner ownership milestone

- Commit `73a049c` moves the exact former 42-line
  `_candidate_is_canonical_statement_winner(candidate, *, operand,
  query_years)` graph definition to public
  `financial_operand_resolution.candidate_is_canonical_statement_winner(...)`
  with the 17-statement/seven-return body unchanged. The old private definition
  and executable private references are gone without a wrapper or compatibility
  bridge.
- Four CURRENT-SOURCE methods pin preference-first stopping, metadata/policy
  shallow copies, statement-type and heading/section fallback, eager marker
  materialization and repeated conversion, marker/section iteration and
  generator short circuits, `< 2.5` direct strength, target-year/period fallback,
  exact identities, immutability, and every uncaught failure.
- The sole `_deterministic_reconcile_task(...)` call now binds the public owner.
  Direct-entry dictionary evaluation order, `canonical_winner` storage,
  family/logical collapse, semantic-priority and score fallback, and adoption
  remain graph-owned.
- Production source is `+50/-46`, net `+4`: graph helpers move from 5,001 to
  4,958 physical lines and operand resolution from 4,113 to 4,160. Tests are
  `+1,593/-67`, net `+1,526`; graph-helper tests move from 33,689 to 35,215.
  The whole commit is `+1,643/-113`, net `+1,530`, and four methods move full
  discovery from 2,003 to 2,007. Final counts are graph 9/75 and operand
  resolution 50/37. The source diff SHA-256 is
  `f3733afbfbbeaec72deafed6a9cfcde10e2c8b1b88e03ece43c10dcd73c563d6`.
- Focused pre/post movement 4/4, graph owner 154/154, operand owner 69/69,
  affected eleven-module semantic 1,114/1,114, reconciliation plan 51/51,
  import-side-effects 19/19, runtime-domain audit 217, and full discovery
  2,007/2,007 passed. Pycompile, fresh public identity 1/1, exact selected-body
  parity 1/1, retained graph exact 83/84 and call-normalized 84/84, all 86
  retained operand functions, the sole call/caller, full 48-module/204-edge
  acyclic DAG parity, retired private refs zero, non-ASCII preservation 4/4,
  and diff check passed. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic canonical-statement-winner ownership.
It proves no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

### Ratio-component-acceptance ownership milestone

- Commit `20feddc` moves the exact former 68-line
  `_candidate_satisfies_ratio_component_acceptance_contract(candidate, *,
  operand, constraints, query_years, selected_cell=None, report_scope=None)`
  graph definition to public
  `financial_operand_resolution.candidate_satisfies_ratio_component_acceptance_contract(...)`
  with the 22-statement/twelve-return/no-`try` body unchanged. The old private
  definition and executable references are gone without a wrapper or bridge.
- Four CURRENT-SOURCE methods pin metadata/report/binding shallow copies,
  candidate-kind/descriptor/numeric/segment/report order, lazy direct-row truth,
  aggregate precedence, eager positive-term materialization, selected-cell-aware
  surface truth, both strength sites, period truth, identities, immutability,
  and every uncaught failure.
- All three reconciliation calls now bind the public owner. First-hit return,
  combined-condition `continue`, later fallback assignment, same-block fallback,
  candidate/cell adoption, evidence work, and state sequencing remain caller-
  owned.
- Production source is `+80/-74`, net `+6`: graph helpers move from 4,958 to
  4,888 physical lines and operand resolution from 4,160 to 4,236. Tests are
  `+1,325/-99`, net `+1,226`; graph-helper tests move from 35,215 to 36,441.
  The whole commit is `+1,405/-173`, net `+1,232`, and four methods move full
  discovery from 2,007 to 2,011. Final counts are graph 9/74 and operand
  resolution 51/37. The source diff SHA-256 is
  `f0e6496c26ea5ed85c50db99057911f149d4654690a833d09ff725125e0e2139`.
- Focused pre/post movement 4/4, graph owner 158/158, operand owner 69/69,
  affected eleven-module semantic 1,118/1,118, reconciliation plan 51/51,
  import-side-effects 19/19, runtime-domain audit 217, and full discovery
  2,011/2,011 passed. Pycompile, fresh public identity 1/1, exact selected-body
  parity 1/1, retained graph exact 83/83, all 87 retained operand functions,
  all three calls/one caller module, full 48-module/204-edge acyclic DAG parity,
  retired private refs zero, non-ASCII preservation 5/5, and diff check passed.
  Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only deterministic ratio-component-acceptance ownership.
It proves no behavior, accuracy, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

### Direct-grounding characterization checkpoint

- A docs-only inventory selects the current exact 86-line
  `_candidate_is_direct_grounding_candidate(candidate, *, operand, constraints,
  query_years, operation_family="", report_scope=None)` graph definition for a
  future public move to
  `financial_operand_resolution.candidate_is_direct_grounding_candidate(...)`.
  No production source or test moved for this projection.
- The projection preserves 30 top-level statements, fifteen returns, no `try`,
  exact booleans, metadata/binding/report shallow copies, four-kind/descriptor/
  numeric/direct-strength order and `< 1.0`, binding/canonical/consolidation/
  period precedence, both delta-label positions, segment/report order, eager
  target-year result, trusted-period truth, lazy lookup-table structured-sibling/
  row-delta tail, identities, immutability, and every uncaught failure.
- Operand resolution already owns the local helpers and existing row/surface/
  scope module edges. It needs only two row-surface names and one surface-
  contract name. The full DAG stays acyclic at 48 modules/204 edges. Current/
  projected counts are graph 9/74 to 9/73 and operand resolution 51/37 to 52/37;
  the selected span has zero of 217 reviewed runtime-domain records.
- Three direct calls project across graph helpers and reconciliation at caller
  `try` depth zero. Direct acceptance keeps its first rejection, deterministic
  reconciliation keeps ordered non-lookup filtering and unique/ambiguous
  fallback/adoption, and nested reconciliation support keeps the empty operation
  default, first-hit return, non-ratio stop, and ratio-cell fallback. Candidate/
  cell construction, acceptance, scoring/collapse, evidence work, state, I/O,
  retry, and final sequencing remain outside.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  162/162, operand owner 69/69, affected semantic 1,122/1,122, reconciliation
  plan 51/51, import 19/19, audit 217, full 2,015/2,015, public identity,
  selected-body parity, retained graph exact 80/82 and call-normalized 82/82,
  retained operand owner 88/88, all three calls/two caller modules, full acyclic
  DAG parity, retired-ref zero, non-ASCII preservation, and diff check are
  governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/call/DAG/function-count/import and selected-body audit
inspection passed. Benchmark refresh and remote CI were **NOT RUN**. This
checkpoint is not a behavior, quality, ranking, performance, benchmark,
schedule, or completion claim.

### Direct-grounding ownership milestone

- Commit `4c422ed` moves the exact former 86-line
  `_candidate_is_direct_grounding_candidate(candidate, *, operand, constraints,
  query_years, operation_family="", report_scope=None)` graph definition to
  public
  `financial_operand_resolution.candidate_is_direct_grounding_candidate(...)`
  with its 30-statement/fifteen-return/no-`try` body unchanged. The private
  definition and executable references are gone without a wrapper or bridge.
- Four CURRENT-SOURCE methods pin metadata/binding/report shallow copies,
  kind/descriptor/numeric/direct-strength order and `< 1.0`, binding/canonical/
  consolidation/period precedence, both delta-label sites, segment/report
  gates, eager target-year evaluation, lazy lookup-table-row truth, exact
  booleans, identities, immutability, and every uncaught failure.
- All three calls across graph helpers and reconciliation now bind the public
  owner. Direct-acceptance first rejection, ordered non-lookup filtering and
  unique/ambiguous fallback, reconciliation first-hit/non-ratio stop/ratio-cell
  fallback, candidate/cell adoption, evidence work, and state sequencing remain
  caller-owned.
- Production source is `+96/-93`, net `+3`: graph helpers move from 4,888 to
  4,800 physical lines and operand resolution from 4,236 to 4,327. Tests are
  `+1,380/-207`, net `+1,173`; the whole commit is `+1,476/-300`, net
  `+1,176`, and four methods move full discovery from 2,011 to 2,015. Final
  counts are graph 9/73 and operand resolution 52/37. The source diff SHA-256
  is `ed765a77a57fa6cb2a8a0e5e81a384074dd69d22e0311ff62a2561a33bc7c66f`.
- Focused pre/post movement 4/4, graph owner 162/162, operand owner 69/69,
  affected eleven-module semantic 1,122/1,122, reconciliation plan 51/51,
  import-side-effects 19/19, runtime-domain audit 217, and full discovery
  2,015/2,015 passed. Pycompile, fresh public identity 1/1, exact selected-body
  parity 1/1, retained graph exact 80/82 and call-normalized 82/82, all 88
  retained operand functions, all three calls/two caller modules, full
  48-module/204-edge acyclic DAG parity, retired private refs zero, non-ASCII
  preservation 7/7, and diff check passed. Benchmark refresh and remote CI were
  **NOT RUN**.

This milestone changes only deterministic direct-grounding ownership. It proves
no behavior, accuracy, ranking, performance, benchmark, schedule, ledger, or
Phase 3 completion claim.

### Direct-acceptance characterization checkpoint

- A docs-only inventory selects the current exact 161-line
  `_candidate_satisfies_direct_acceptance_contract(candidate, *, operand,
  constraints, query_years, operation_family="", selected_cell=None,
  report_scope=None)` graph definition for a possible future public move to
  `financial_operand_resolution.candidate_satisfies_direct_acceptance_contract(...)`.
  No production source or test moved for this projection.
- The projection preserves nineteen top-level statements, seventeen returns,
  the first direct-grounding rejection, selected-cell period/presence/report-
  year recovery, marker/year gates, surface and unit truth, `< 2.0` direct
  strength, eager statement/role/stage/location projection, canonical lookup,
  balance-sheet aggregate, CAPEX, and final period-label gates. Its sole `try`
  catches exactly `TypeError`/`ValueError` during selected-cell report-year
  integer conversion; all other failures remain uncaught.
- Operand resolution needs `PERIOD_FOCUS_POLICY`,
  `_structured_cell_period_text`, `operand_target_years`, and
  `candidate_selected_unit_family` imports. The new operand-to-structured-cells
  edge projects an acyclic 48-module/205-edge DAG. Current/projected counts are
  graph 9/73 to 9/72 and operand resolution 52/37 to 53/37; the selected span
  has zero of 217 reviewed runtime-domain records.
- Five direct calls project across three modules at caller `try` depth zero.
  Deterministic reconciliation keeps its rejection stop; two nested-
  reconciliation sites retain direct-then-ratio laziness, `continue`, same-
  block fallback and candidate/cell adoption; current/prior period-pair sites
  retain independent score/append decisions and caller-owned pair selection.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  166/166, operand owner 69/69, affected semantic 1,126/1,126, reconciliation
  plan 51/51, import 19/19, audit 217, full 2,019/2,019, public identity,
  selected-body parity, retained graph exact 80/81 and call-normalized 81/81,
  retained operand owner 89/89, all five calls/three caller modules, full
  acyclic 48-module/205-edge DAG, retired-ref zero, non-ASCII preservation, and
  diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/call/DAG/function-count/import and selected-body audit
inspection passed. Benchmark refresh and remote CI were **NOT RUN**. This
checkpoint is not a behavior, quality, ranking, performance, benchmark,
schedule, or completion claim.

### Direct-acceptance ownership milestone

- Commit `6ebcf59` moves the exact former 161-line
  `_candidate_satisfies_direct_acceptance_contract(candidate, *, operand,
  constraints, query_years, operation_family="", selected_cell=None,
  report_scope=None)` graph definition to public
  `financial_operand_resolution.candidate_satisfies_direct_acceptance_contract(...)`
  with its nineteen-statement/seventeen-return body unchanged. The private
  definition and executable references are gone without a wrapper or bridge.
- Four CURRENT-SOURCE methods pin the direct-grounding-first gate, selected-cell
  period text and ordered soft report-year recovery, lazy marker/year truth,
  surface/unit/direct-strength gates, canonical lookup, balance-sheet aggregate
  and CAPEX filters, final period-label gate, exact booleans, identities,
  immutability, and every failure outside the sole `TypeError`/`ValueError`
  conversion boundary.
- All five calls across graph helpers, reconciliation, and period-pair projection
  now bind the public owner. Direct-then-ratio laziness, rejection stops, score/
  append, same-block fallback, candidate/cell adoption, evidence work, and state
  sequencing remain caller-owned.
- Production source is `+178/-175`, net `+3`: graph helpers move from 4,800 to
  4,634 physical lines and operand resolution from 4,327 to 4,494. Tests are
  `+1,631/-258`, net `+1,373`; the whole commit is `+1,809/-433`, net `+1,376`,
  and four methods move full discovery from 2,015 to 2,019. Final counts are
  graph 9/72 and operand resolution 53/37. The source diff SHA-256 is
  `2ed5b13b639fec8480de6594151a6fe63abdc9af776296d33d4e1614a9d51cc6`.
- Focused pre/post movement 4/4, graph owner 166/166, operand owner 69/69,
  affected eleven-module semantic 1,126/1,126, reconciliation plan 51/51,
  import-side-effects 19/19, runtime-domain audit 217, and full discovery
  2,019/2,019 passed. Pycompile, fresh public identity 3/3, exact selected-body
  parity 1/1, retained graph exact 80/81 and call-normalized 81/81, all 89
  retained operand functions, all five calls/three caller modules, full
  48-module/205-edge acyclic DAG parity, retired private refs zero, non-ASCII
  preservation 9/9, and diff check passed. Benchmark refresh and remote CI were
  **NOT RUN**.

This milestone changes only deterministic direct-acceptance ownership. It proves
no behavior, accuracy, ranking, performance, benchmark, schedule, ledger, or
Phase 3 completion claim.

### Operand-candidate scorer ownership milestone

- Commit `3d6986e` moves the exact former 315-line
  `_score_operand_candidate(candidate, *, operand, preferred_statement_types,
  constraints, query_years, report_scope=None)` graph definition to public
  `financial_operand_resolution.score_operand_candidate(...)`. Its 62-statement/
  two-return/two-`try` body is unchanged except for the same-owner public helper
  spelling. The private definition and executable refs are gone without a
  wrapper or bridge.
- Four CURRENT-SOURCE methods pin the metadata copy and exact conflict result,
  complete ordered score pipeline, both narrow `ValueError` boundaries,
  repeated calls and collection materialization, identities, shallow copies,
  immutability, and every other uncaught failure.
- All seven calls across graph helpers, reconciliation, period-pair projection,
  and ontology-shadow diagnostics now bind the public owner. Exact arguments,
  sorting/key assembly, score storage, pair selection, fallback/adoption, and
  exception stops remain caller-owned; the adjacent report-file/local-unit I/O
  helper remains graph-owned.
- Production source is `+338/-356`, net `-18`: graph helpers move from 4,634 to
  4,294 physical lines and operand resolution from 4,494 to 4,816. Tests are
  `+1,542/-364`, net `+1,178`; the whole commit is `+1,880/-720`, net `+1,160`,
  and four methods move discovery from 2,019 to 2,023. Final counts are graph
  9/71 and operand resolution 54/37. The source diff SHA-256 is
  `2e681d92116eb7b6c213dc505ba61bddbb0aafe65b86eacf917bf4c28d594650`.
- Focused pre/post movement 4/4, graph owner 170/170, operand owner 69/69,
  affected eleven-module semantic 1,130/1,130, reconciliation plan 51/51,
  import-side-effects 19/19, runtime-domain audit 217, and full discovery
  2,023/2,023 passed. Pycompile, public identity 4/4, helper-name-normalized
  selected-body parity 1/1, retained graph exact 79/80 and call-normalized
  80/80, all 90 retained operand functions, all seven calls/four modules, full
  unchanged 48-module/205-edge acyclic DAG parity, retired private refs zero,
  non-ASCII preservation, and diff check passed. Benchmark refresh and remote
  CI were **NOT RUN**.

This milestone changes only deterministic scorer ownership. It proves no
behavior, quality, ranking, performance, benchmark, schedule, ledger, or Phase
3 completion claim.

### Operand segment-label public-API milestone

- Commit `cce5700` renames the exact former 3-line private helper in its existing
  surface owner to public `operand_segment_label(...)`. Its two-statement body
  is exact after definition-name normalization; the private definition and
  executable refs are gone without a wrapper or bridge.
- Four CURRENT-SOURCE methods pin the ordered operand get/truth/shallow-copy/
  policy-get/truth/string/normalization pipeline, exact result, identity,
  immutability, laziness, and every uncaught failure.
- All thirteen calls across graph calculation, graph helpers, operand resolution,
  row surfaces, and surface contracts now bind the public API. Exact arguments,
  fallback/normalization, generator laziness, short-circuit returns, query/task
  projection, reconciliation filtering/ranking, later work, and exception stops
  remain caller-owned.
- Production source is `+18/-18`, net `0`; tests are `+925/-63`, net `+862`;
  the whole commit is `+943/-81`, net `+862`; and all production physical line
  counts are unchanged. Four methods move discovery from 2,023 to 2,027. Final
  counts are surface contracts 16/6, graph 9/71, and operand resolution 54/37.
  The source diff SHA-256 is
  `416655cdf1c30a24afa9733cdeece140e43bf66016ad650af6ab8fb79808638e`.
- Focused pre/post rename 4/4, graph owner 174/174, surface owner 1/1, operand
  owner 69/69, affected semantic 1,134/1,134, reconciliation plan 51/51,
  import-side-effects 19/19, runtime-domain audit 217, and full discovery
  2,027/2,027 passed. The first discovery attempt hit the 120-second command
  limit; the identical command passed in 104.557 seconds with a 300-second
  limit. Pycompile, exact production rename parity 5/5, selected-body hash
  parity, public identity 4/4, all thirteen calls/five modules, unchanged
  acyclic 48-module/205-edge DAG parity, retired private refs zero, non-ASCII
  preservation 7/7, and diff check passed. Benchmark refresh and remote CI were
  **NOT RUN**.

This milestone changes only API visibility. It proves no behavior, quality,
ranking, performance, benchmark, schedule, ledger, or Phase 3 completion claim.

### Operand-needles public-API milestone

- Commit `ae964b3` renames the exact former 4-line private helper in its existing
  surface owner to public `operand_needles(...)`. Its three-statement body is
  exact after definition-name normalization; the private definition and
  executable refs are gone without a wrapper or bridge.
- Four CURRENT-SOURCE methods pin label-before-alias get/truth/string/strip
  order, eager alias iteration, retained-alias second conversion, final
  filtering, duplicates, exact result order, identities, immutability,
  exceptions, caller arguments/adoption/stops, and public-name shadow absence.
- All twenty-four calls across nine source modules now bind the public owner at
  caller `try` depth zero. Exact comprehension/loop/starred-list evaluation,
  normalization, matching, scoring/adoption, later work, and exception stops
  remain caller-owned. The rename exposed one pre-existing local list with the
  public name; that collection alone is now `normalized_operand_needles`.
- Production source is `+36/-36`, net `0`; tests are `+998/-113`, net `+885`;
  and the whole commit is `+1,034/-149`, net `+885`. All production physical
  line counts are unchanged. Four methods move discovery from 2,027 to 2,031.
  Final counts are surface contracts 17/5, graph 9/71, and operand resolution
  54/37. The source diff SHA-256 is
  `22b638bd5e610ab14088510908c9c39539f977935589cf1c70a6cdac99a84ef0`.
- Focused pre/post rename 4/4, graph owner 178/178, surface owner 1/1, operand
  owner 69/69, affected eleven-module semantic 1,138/1,138, additional caller
  17/17, reconciliation plan 51/51, import-side-effects 19/19, runtime-domain
  audit 217, and final full discovery 2,031/2,031 passed. Pycompile, exact
  production transform parity 10/10, selected-body SHA-256 parity, owner
  name-normalized parity 22/22, public identity 9/9, all twenty-four calls/nine
  modules, zero public stores/private refs, unchanged 48-module/205-edge
  acyclic DAG, non-ASCII preservation 13/13, and diff check passed. Benchmark
  refresh and remote CI were **NOT RUN**.

The semantic set initially exposed the local-name collision as twenty-one
`UnboundLocalError` paths; the local disambiguation and no-shadow contract fixed
the cause, after which the identical 1,138-test set passed. This milestone
changes only API visibility and one shadow-safe local name. It proves no
behavior, quality, ranking, performance, benchmark, schedule, ledger, or Phase
3 completion claim.

### Negative-surface predicate public-API milestone

- Commit `83cf700` renames the exact former 3-line private helper in its existing
  surface owner to public `text_has_negative_surface(...)`. Its two-statement
  body is exact after definition-name normalization; the private definition and
  executable refs are gone without a wrapper or bridge.
- Four CURRENT-SOURCE methods pin exact operand/text identity, contract-owner
  call order, negative get/truth/fresh-list fallback, eager ordered copy,
  duplicates, element identities, exact term-helper result, immutability,
  exceptions, caller arguments/short-circuit/stops, and public-name store
  absence.
- All ten calls across graph evidence, operand resolution, retrieval pipeline,
  and the surface owner now bind the public owner at caller `try` depth zero.
  Five external modules retain the public binding; graph calculation and graph
  helpers are import-only. Exact boolean/generator evaluation, operand copies,
  surface preparation, later adoption, and exception stops remain caller-owned.
- Production source is `+16/-16`, net `0`; tests are `+990/-27`, net `+963`;
  and the whole commit is `+1,006/-43`, net `+963`. All production physical
  line counts are unchanged. Four methods move discovery from 2,031 to 2,035.
  Final counts are surface contracts 18/4, graph 9/71, and operand resolution
  54/37. The source diff SHA-256 is
  `69d56b303cee0619864af4d3b446b2c344c7f61e035e4f2bea3a54e7a5184991`.
- Focused pre/post rename 4/4, graph owner 182/182, surface owner 1/1, operand
  owner 69/69, affected eleven-module semantic 1,142/1,142, additional
  retrieval-pipeline 1/1, reconciliation plan 51/51, import-side-effects 19/19,
  runtime-domain audit 217, and full discovery 2,035/2,035 passed. Pycompile,
  exact production transform parity 6/6, selected-body SHA-256 parity, owner
  name-normalized parity 22/22, public identity 5/5, all ten calls/four modules,
  zero public stores/private executable refs, unchanged 48-module/205-edge
  acyclic DAG, non-ASCII preservation 8/8, and diff check passed. Benchmark
  refresh and remote CI were **NOT RUN**.

This milestone changes only API visibility. It proves no behavior, quality,
ranking, performance, benchmark, schedule, ledger, or Phase 3 completion claim.

### Positive-surface predicate public-API milestone

- Commit `a0c9a84` renames the exact former 3-line private helper in its existing
  surface owner to public `text_has_positive_surface(...)`. Its two-statement
  body is exact after definition-name normalization; the private definition and
  executable refs are gone without a wrapper or bridge.
- Four CURRENT-SOURCE methods pin exact operand/text identity, contract-owner
  call order, positive get/truth/fresh-list fallback, eager ordered copy,
  duplicates, element identities, exact term-helper result, immutability,
  exceptions, caller arguments/short-circuit/stops, and public-name store
  absence.
- All twenty-six calls across graph calculation, graph evidence, lookup
  recovery, operand resolution, retrieval pipeline, row surfaces, and the
  surface owner now bind the public owner at caller `try` depth zero. External/
  local calls are 25/1; all six external bindings are live. Exact boolean/
  generator/conditional evaluation, operand copies, surface preparation, later
  adoption, and exception stops remain caller-owned.
- Production source is `+33/-33`, net `0`; tests are `+1,234/-73`, net `+1,161`;
  and the whole commit is `+1,267/-106`, net `+1,161`. All production physical
  line counts are unchanged. Four methods move discovery from 2,035 to 2,039.
  Final counts are surface contracts 19/3, graph 9/71, and operand resolution
  54/37. The source diff SHA-256 is
  `fa6ec5508e044215963811971024a2dfe60b375dec46b1435e57a9914163b0cb`.
- Focused pre/post rename 4/4, graph owner 186/186, surface owner 1/1, operand
  owner 69/69, affected eleven-module semantic 1,146/1,146, additional
  retrieval-pipeline 1/1, reconciliation plan 51/51, import-side-effects 19/19,
  runtime-domain audit 217, and full discovery 2,039/2,039 passed. Pycompile,
  exact production transform parity 7/7, untouched-test transform parity 2/2,
  selected-body SHA-256 parity, owner name-normalized parity 22/22, public
  identity 6/6, all twenty-six calls/seven modules, zero public stores/private
  executable refs, unchanged 48-module/205-edge acyclic DAG, non-ASCII
  preservation 10/10, and diff check passed. Benchmark refresh and remote CI
  were **NOT RUN**.

This milestone changes only API visibility. It proves no behavior, quality,
ranking, performance, benchmark, schedule, ledger, or Phase 3 completion claim.

### Text contract-term predicate public-API milestone

- Commit `faf75a0` renames the exact former 13-line private helper in its
  existing surface owner to public `text_has_contract_term(...)`. Its five-
  statement body is exact after definition-name normalization; the private
  definition and executable refs are gone without a wrapper or bridge.
- Four CURRENT-SOURCE methods pin text/term identity, normalization and compact
  order, blank/empty stops, ordered lazy iteration, direct-before-compact
  membership, exact booleans, immutability, exceptions, caller arguments/short-
  circuit/stops, and public-name store absence.
- All four calls across operand resolution and the surface owner now bind the
  public owner at caller `try` depth zero. External/local calls are 1/3 and the
  external binding is live. Exact return identity, list construction, generator
  filtering, later work, and exception stops remain caller-owned.
- Production source is `+6/-6`, net `0`; tests are `+964/-46`, net `+918`; and
  the whole commit is `+970/-52`, net `+918`. All production physical line
  counts are unchanged. Four methods move discovery from 2,039 to 2,043. Final
  counts are surface contracts 20/2, graph 9/71, and operand resolution 54/37.
  The source diff SHA-256 is
  `cca5735d1b0f269dc5ce7b4e3701c3fb448d6a25c3e655376b5400bea462d7e1`.
- Focused pre/post rename 4/4, graph owner 190/190, surface owner 1/1, operand
  owner 69/69, affected eleven-module semantic 1,150/1,150, additional
  retrieval-pipeline 1/1, reconciliation plan 51/51, import-side-effects 19/19,
  runtime-domain audit 217, and full discovery 2,043/2,043 passed. Pycompile,
  exact production transform parity 2/2, selected-body and dependent-wrapper
  hash parity, existing graph-test AST parity 186/186 plus four new methods,
  public identity 1/1, all four calls/two modules, zero public stores/private
  executable refs, unchanged 48-module/205-edge acyclic DAG, non-ASCII
  preservation 3/3, and diff check passed. The first graph-owner run failed only
  two stale raw wrapper-hash expectations; their exact renamed hashes then
  passed with the final 190/190. Benchmark refresh and remote CI were **NOT
  RUN**.

This milestone changes only API visibility and recorded caller-body hashes. It
proves no behavior, quality, ranking, performance, benchmark, schedule, ledger,
or Phase 3 completion claim.

### Operand surface-contract private-API characterization checkpoint

- A docs-only inventory selects the current exact 22-line
  `financial_surface_contracts._operand_surface_contract(operand)` definition
  with `Dict[str, Any] -> Dict[str, List[str]]` typing for an in-place public
  rename to `operand_surface_contract(...)`. No source or test rename has
  occurred.
- The projection preserves eight top-level statements, four returns, three
  `if` nodes, one loop, explicit-contract priority and fresh positive/negative
  projections, copied legacy-policy concept lookup, ordered operand-needle
  fallback, repeated string conversion, exact copies/results, immutability,
  laziness, and every uncaught mapping/truth/string/iteration/normalization/
  membership failure.
- Seven one-positional-argument calls across two source modules remain at caller
  `try` depth zero; external/local calls are 2/5. Operand resolution imports and
  calls the helper, while graph helpers retains an import-only binding. Existing
  edges keep the full DAG unchanged and acyclic at 48 modules/205 edges.
  Projected counts are surface contracts 20/2 to 21/1, with graph 9/71 and
  operand resolution 54/37 unchanged. No future public-name definition/store
  exists. The selected body SHA-256 is
  `bca087bf56ef092bc7487acb54c0de95b04d680f018eef95b3d231d9b18fd29b`
  and its span has zero of 217 reviewed runtime-domain records.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  194/194, surface owner 1/1, operand owner 69/69, affected semantic
  1,154/1,154, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
  import 19/19, audit 217, full 2,047/2,047, public identity across both external
  imports, production transform/selected-body/owner and all seven caller-body
  parity, all seven calls/two call modules plus one import-only binding,
  unchanged acyclic DAG, retired-ref/public-store zero, existing graph-test AST
  parity 190/190 plus four new methods, non-ASCII preservation 4/4, pycompile,
  and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
selected-span audit inspection passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Operand surface-contract public-API milestone

- Commit `5b71fd6` renames the exact former 22-line private helper in its
  existing surface owner to public `operand_surface_contract(...)`. Its eight-
  statement body is exact after definition-name normalization; the private
  definition and executable refs are gone without a wrapper or bridge.
- Four CURRENT-SOURCE methods pin explicit-contract priority and fresh lists,
  copied legacy-policy concept lookup, ordered operand-needle fallback,
  repeated conversions, exact identities/results, immutability, laziness,
  uncaught failures, caller arguments/adoption/stops, imports, DAG, audit, and
  public-name store absence.
- All seven calls across operand resolution and the surface owner now bind the
  public API at caller `try` depth zero. External/local calls are 2/5. Operand
  resolution is a live external caller while graph helpers is an import-only
  binding. Later work and exception stops remain caller-owned.
- Production source is `+10/-10`, net `0`; tests are `+1,185/-85`, net
  `+1,100`; and the whole commit is `+1,195/-95`, net `+1,100`. Production
  physical line counts are unchanged. Four methods move discovery from 2,043
  to 2,047. Final counts are surface contracts 21/1, graph 9/71, and operand
  resolution 54/37. The source diff SHA-256 is
  `0e9efc0d6d5f8d131a762c1200b77e470f91e598d2db4d51d08da6dc096a866b`.
- Focused pre/post rename 4/4, graph owner 194/194, surface owner 1/1, operand
  owner 69/69, affected eleven-module semantic 1,154/1,154, additional
  retrieval-pipeline 1/1, reconciliation plan 51/51, import-side-effects
  19/19, runtime-domain audit 217, and full discovery 2,047/2,047 passed.
  Pycompile, production transform parity 3/3, selected-body and two dependent-
  wrapper hashes, existing graph-test AST parity 190/190 plus four new methods,
  public identity 2/2, all seven calls/two modules plus the import-only binding,
  zero public stores/retired exact private refs, unchanged acyclic 48-module/
  205-edge DAG, UTF-8/non-ASCII preservation 4/4, and diff check passed. The
  first graph-owner run failed only two stale raw wrapper-hash expectations;
  their exact renamed hashes then passed with the final 194/194. Benchmark
  refresh and remote CI were **NOT RUN**.

This milestone changes only API visibility and recorded caller-body hashes. It
proves no behavior, quality, ranking, performance, benchmark, schedule, ledger,
or Phase 3 completion claim.

### Generic-column-header private-API characterization checkpoint

- A docs-only inventory leaves the owner-local
  `financial_surface_contracts._candidate_segment_surfaces(...)` assembly
  private and selects the actual cross-module 2-line
  `financial_row_surfaces._generic_column_headers() -> set[str]` definition for
  an in-place public rename to `generic_column_headers()`. No source or test
  rename has occurred.
- The projection preserves the one policy get/`or ()` sequence, generator-
  under-set laziness, condition-before-result string conversion, dropped-once
  and retained-twice conversion, exact second-result insertion, duplicate
  collapse, fresh set, immutability, and every uncaught mapping/get/truth/
  iteration/string/hash/equality/set failure.
- Two zero-argument calls across row surfaces and structured cells remain at
  caller `try` depth zero; external/local calls are 1/1. The row label caller
  uses the exact collection for generic-header filtering before target/year
  handling. Structured-cell affinity uses it before last-header selection,
  operand needles, scoring, policy work, and return. Existing edges keep the
  full DAG unchanged and acyclic at 48 modules/205 edges.
- Projected counts are row surfaces 11/15 to 12/14 and structured cells 4/4.
  No future public-name definition/store exists. The body SHA-256 is
  `f19ad20d15ac9e560aa70180155bc71dc55fa85770d185c43a07f7eb5f139660`, and
  its span has zero of 217 reviewed runtime-domain records. The private
  spelling appears four times in two production files and as 24 exact test
  string constants.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  198/198, surface owner 1/1, operand owner 69/69, affected semantic
  1,158/1,158, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
  import 19/19, audit 217, full 2,051/2,051, public identity 1/1, production
  transform/selected-body/two caller-body parity, both calls/two modules,
  unchanged DAG, retired-ref/public-store zero, existing graph-test AST parity
  194/194 plus four new methods, UTF-8/non-ASCII preservation 3/3, pycompile,
  and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
selected-span audit inspection passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Generic-column-header public-API milestone

- Commit `ea830ed` renames the exact former 2-line private helper in its existing
  row-surface owner to public `generic_column_headers()`. Its one-return body is
  exact after definition-name normalization; the private definition and
  executable refs are gone without a wrapper or bridge.
- Four CURRENT-SOURCE methods pin the policy get/`or ()`, generator-under-set
  laziness, condition-before-result conversion, dropped-once and retained-twice
  stringification, exact identities/results, duplicate collapse, fresh sets,
  immutability, uncaught failures, caller order/adoption/stops, imports, DAG,
  audit, and public-name store absence.
- Both calls across row surfaces and structured cells now bind the public API at
  caller `try` depth zero. External/local calls are 1/1 and the external binding
  is live. Later work and exception stops remain caller-owned.
- Production source is `+4/-4`, net `0`; tests are `+804/-31`, net `+773`; and
  the whole commit is `+808/-35`, net `+773`. Production physical line counts
  are unchanged. Four methods move discovery from 2,047 to 2,051. Final counts
  are row surfaces 12/14 and structured cells 4/4. The source diff SHA-256 is
  `5b953b411edaf1fd53ac437179eb1a24dac17960398f6df64bfa6d50676cc37c`.
- Focused pre/post rename 4/4, graph owner 198/198, surface owner 1/1, operand
  owner 69/69, affected eleven-module semantic 1,158/1,158, additional
  retrieval-pipeline 1/1, reconciliation plan 51/51, import-side-effects
  19/19, runtime-domain audit 217, and full discovery 2,051/2,051 passed on the
  final bytes. Pycompile, production transform parity 2/2, selected-body and
  two caller hashes, existing graph-test AST parity 194/194 plus four new
  methods, public identity 1/1, both calls/two modules, zero public stores/
  retired exact private refs, unchanged acyclic 48-module/205-edge DAG,
  UTF-8/non-ASCII preservation 3/3, and diff check passed. Benchmark refresh
  and remote CI were **NOT RUN**.

This milestone changes only API visibility and recorded caller-body hashes. It
proves no behavior, quality, ranking, performance, benchmark, schedule, ledger,
or Phase 3 completion claim.

### Table-row-label private-API characterization checkpoint

- A docs-only inventory selects the current exact 9-line
  `financial_row_surfaces._extract_table_row_label(row_text: str) -> str`
  definition for an in-place public rename to `extract_table_row_label(...)`.
  It removes three external private imports with no owner-local call. No source
  or test rename has occurred.
- The projection preserves four top-level statements, three `if` nodes, three
  returns, raw-argument normalization, blank stop, exact pipe membership,
  `split("|", 1)[0]`, second normalization, truthy first-cell return, falsey
  fallthrough to the exact initial normalized object, identities, immutability,
  and every uncaught normalization/truth/containment/split/index failure.
- Three one-positional-argument calls across graph evidence, graph helpers, and
  graph reconciliation remain at caller `try` depth zero; external/local calls
  are 3/0. Exact result adoption, earlier mutation, later work, and exception
  stops remain caller-owned. Existing edges keep the full DAG unchanged and
  acyclic at 48 modules/205 edges.
- Projected row counts are 12/14 to 13/13. No future public-name definition or
  store exists. The body SHA-256 is
  `b6cbee85add69ae9168ecedd1d70f84beedef859629797a6d0a8a34b041e6bd1`, and
  its span has zero of 217 reviewed runtime-domain records. The private spelling
  appears seven times in four production files and once as an exact existing
  graph-helper test patch string.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  202/202, surface owner 1/1, operand owner 69/69, affected semantic
  1,162/1,162, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
  import 19/19, audit 217, full 2,055/2,055, public identity 3/3, production
  transform/selected-body/three-caller parity, all three calls/three modules,
  unchanged DAG, retired-ref/public-store zero, existing graph-test AST parity
  198/198 plus four new methods, UTF-8/non-ASCII preservation 5/5, pycompile,
  and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
selected-span audit inspection passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Table-row-label public-API milestone

- Commit `786a356` renames the exact former 9-line private helper in its existing
  row-surface owner to public `extract_table_row_label(...)`. Its four top-level
  statements, three `if` nodes, and three returns are exact after definition-
  name normalization; the private definition and executable refs are gone
  without a wrapper or bridge.
- Four CURRENT-SOURCE methods pin raw normalization, blank stop, delimiter
  membership/split/index order, truthy first-cell and falsey initial-result
  identity, immutability, uncaught failures, caller arguments/adoption/stops,
  imports, DAG, audit, and public-name store absence.
- All three calls across graph evidence, graph helpers, and graph reconciliation
  now bind the public API at caller `try` depth zero. External/local calls are
  3/0 and all external bindings are live. Earlier mutation, later work, and
  exception stops remain caller-owned.
- Production source is `+7/-7`, net `0`; tests are `+1,224/-9`, net `+1,215`;
  and the whole commit is `+1,231/-16`, net `+1,215`. Production physical line
  counts are unchanged. Four methods move discovery from 2,051 to 2,055. Final
  row counts are 13/13. The source diff SHA-256 is
  `3406b381e79434e1f1b9550e568be93dff39fefd326dbb29a5dd01fab3804c0c`.
- Focused pre/post rename 4/4, graph owner 202/202, surface owner 1/1, operand
  owner 69/69, affected eleven-module semantic 1,162/1,162, additional
  retrieval-pipeline 1/1, reconciliation plan 51/51, import-side-effects
  19/19, runtime-domain audit 217, and full discovery 2,055/2,055 passed.
  Pycompile, production transform parity 4/4, selected-body and three caller
  hashes, existing graph-test AST parity 198/198 plus four new methods, public
  identity 3/3, all three calls/importers, zero public stores/retired exact
  private refs, unchanged acyclic 48-module/205-edge DAG, UTF-8/non-ASCII
  preservation 5/5, and diff check passed. The first graph-owner run failed only
  eight stale row public/private count baselines; their exact 13/13 updates
  produced the final 202/202 pass. Benchmark refresh and remote CI were **NOT
  RUN**.

This milestone changes only API visibility and recorded structural baselines.
It proves no behavior, quality, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

### Financial-label-annotation private-API characterization checkpoint

- A docs-only inventory selects the current exact 9-line
  `financial_row_surfaces._strip_financial_label_annotations(text: str) -> str`
  definition for an in-place public rename to
  `strip_financial_label_annotations(...)`. No source or test rename has
  occurred.
- The projection preserves five top-level statements, one `if`, two returns,
  raw `text or ""`, normalization/blank stop, exact annotation-regex removal,
  whitespace collapse/strip, exact intermediate/result identities,
  immutability, absence of string coercion, and every uncaught truth/
  normalization/regex/strip failure.
- Five one-positional-argument direct calls across row surfaces, graph helpers,
  and operand resolution remain at caller `try` depth zero; external/local calls
  are 3/2. Exact result adoption, eager variant order, aggregate retry-query
  expansion, needle-set hash/dedupe, generic-suffix scoring, later work, and
  exception stops remain caller-owned. Existing edges keep the full DAG
  unchanged and acyclic at 48 modules/205 edges.
- Projected row counts are 13/13 to 14/12, while graph helpers remain 9/71 and
  operand resolution 54/37. No future public-name definition/store exists. The
  body SHA-256 is
  `bd19becbc4292b4e25cd98722eb87276acb36da6cc58fb6261a58d9bbbec4d05`.
  The private spelling appears eight times in three production files and once
  as an exact existing graph-helper test string.
- Baseline fingerprint `04e17ed82b398fc3` has stale `first_lines: [29]`
  metadata: its stored text is the distinct leading-period regex at line 48,
  not the selected annotation regex at line 29. The rename changes no line or
  literal, so the baseline remains unchanged and audit stays projected at 217.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  206/206, surface owner 1/1, operand owner 69/69, affected semantic
  1,166/1,166, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
  import 19/19, audit 217, full 2,059/2,059, public identity 2/2, production
  transform/selected-body/three-caller parity, all five calls/three modules,
  unchanged DAG, retired-ref/public-store zero, existing graph-test AST parity
  202/202 plus four new methods, UTF-8/non-ASCII preservation 4/4, pycompile,
  and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
baseline-provenance inspection passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.


### Financial-label-annotation public-API milestone

- Commit `472906e` renames the exact former 9-line private helper in its
  existing row-surface owner to public
  `strip_financial_label_annotations(...)`. Its five top-level statements, one
  `if`, and two returns are exact after definition-name normalization; the
  private definition and executable refs are gone without a wrapper or bridge.
- Four CURRENT-SOURCE methods pin raw truth, normalization/blank stop,
  annotation-regex and whitespace-strip order, exact result identity,
  immutability, uncaught failures, caller arguments/adoption/stops, imports,
  DAG, stale audit provenance, and public-name store absence.
- All five calls across row surfaces, graph helpers, and operand resolution now
  bind the public API at caller `try` depth zero. External/local calls are 3/2
  and both external bindings are live. Earlier mutation, later work, and
  exception stops remain caller-owned.
- Production source is `+8/-8`, net `0`; tests are `+1,308/-11`, net `+1,297`;
  and the whole commit is `+1,316/-19`, net `+1,297`. Production physical line
  counts are unchanged. Four methods move discovery from 2,055 to 2,059. Final
  row counts are 14/12; graph helpers remain 9/71 and operand resolution 54/37.
  The source diff SHA-256 is
  `fa6221e4d52b393bc3d6d7103a586bc9b09e55b4d8c2e23c153b7caa8057e5d3`.
- Focused pre/post rename 4/4, graph owner 206/206, surface owner 1/1, operand
  owner 69/69, affected eleven-module semantic 1,166/1,166, additional
  retrieval-pipeline 1/1, reconciliation plan 51/51, import-side-effects
  19/19, runtime-domain audit 217, and full discovery 2,059/2,059 passed.
  Pycompile, production transform parity 3/3, selected-body and three caller
  hashes, existing graph-test AST parity 202/202 plus four new methods, public
  identity 2/2, all five calls/importers, zero public stores/retired exact
  private refs, unchanged acyclic 48-module/205-edge DAG, UTF-8/non-ASCII
  preservation 4/4, and diff check passed. The first graph-owner run failed
  only nine stale row public/private count baselines; their exact 14/12 updates
  produced the final 206/206 pass. Benchmark refresh and remote CI were **NOT
  RUN**.

This milestone changes only API visibility and recorded structural baselines.
It proves no behavior, quality, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

### Leading-period-qualifier private-API characterization checkpoint

- A docs-only inventory selects the current exact 14-line
  `financial_row_surfaces._strip_leading_period_qualifiers(text: str) -> str`
  definition for an in-place public rename to
  `strip_leading_period_qualifiers(...)`. No source or test rename has occurred.
- The projection preserves six top-level statements, two `if` nodes, two
  returns, one `while`, one `break`, raw truth, normalization/blank stop, exact
  regex compilation, one-prefix `sub(..., count=1)`/strip/equality looping,
  immediate-stability versus adopted-result identity, immutability, absence of
  string coercion, and every uncaught truth/normalization/compile/sub/strip/
  equality failure.
- Four one-positional-argument direct calls across row surfaces and aggregate
  projection remain at caller `try` depth zero; external/local calls are 1/3.
  Exact result adoption, eager row variants, sibling blank/compact/membership
  scoring, aggregate stripped-label expansion, later work, and exception stops
  remain caller-owned. Existing edges keep the full DAG unchanged and acyclic
  at 48 modules/205 edges.
- Projected row counts are 14/12 to 15/11, while aggregate projection remains
  76/12 with 19 classes. No future public-name definition/store exists. The
  body SHA-256 is
  `a6b4dae69801793d0ce5bc58d281462c22ce99d4eb22d403b95e51a75fda0e47`.
  The private identifier has six production AST references across two files;
  graph-helper and subtask-loop tests are the bounded test transform surface.
- Baseline fingerprint `04e17ed82b398fc3` stores the selected exact line-48
  regex but has stale `first_lines: [29]`, outside the current 43-56 definition
  span. The rename changes no line or literal, so the baseline remains unchanged
  and audit stays projected at 217.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  210/210, surface owner 1/1, operand owner 69/69, affected semantic
  1,170/1,170, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
  import 19/19, audit 217, full 2,063/2,063, public identity 1/1, production
  transform 2/2, selected-body/three-caller parity, all four calls/two modules,
  unchanged DAG, retired-ref/public-store zero, existing graph-test AST parity
  206/206 plus four new methods, existing subtask-loop AST parity 252/252,
  UTF-8/non-ASCII preservation 4/4, pycompile, and diff check are governed only
  by [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
baseline-provenance inspection passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Leading-period-qualifier public-API milestone

- Commit `98aee5a` renames the exact former 14-line private helper in its
  existing row-surface owner to public
  `strip_leading_period_qualifiers(...)`. Its six top-level statements, two
  `if` nodes, two returns, one `while`, and one `break` are exact after
  definition-name normalization; the private definition and executable refs
  are gone without a wrapper or bridge.
- Four CURRENT-SOURCE methods pin raw truth, normalization/blank stop, exact
  regex compilation, iterative one-prefix sub/strip/equality order,
  immediate-stability and adopted-result identities, immutability, uncaught
  failures, caller arguments/adoption/stops, imports, DAG, stale audit
  provenance, and public-name store absence.
- All four calls across row surfaces and aggregate projection now bind the
  public API at caller `try` depth zero. External/local calls are 1/3 and the
  aggregate binding is live. Earlier mutation, later work, result adoption,
  and exception stops remain caller-owned.
- Production source is `+6/-6`, net `0`; tests are `+1,124/-25`, net `+1,099`;
  and the whole commit is `+1,130/-31`, net `+1,099`. Production physical line
  counts are unchanged. Four methods move discovery from 2,059 to 2,063. Final
  row counts are 15/11; aggregate projection remains 76/12 with 19 classes.
  The committed source diff SHA-256 is
  `5556c032ed6fde19f06863ab5833bb919ae1a90189e8b09c1adfa4f2bb2a5307`.
- Focused pre/post rename 4/4, graph owner 210/210, surface owner 1/1, operand
  owner 69/69, affected eleven-module semantic 1,170/1,170, additional
  retrieval-pipeline 1/1, reconciliation plan 51/51, import-side-effects
  19/19, runtime-domain audit 217, and full discovery 2,063/2,063 passed.
  Pycompile, production transform parity 2/2, selected-body and three caller
  bodies, existing graph-test AST parity 206/206 plus four new methods,
  existing subtask-loop AST parity 252/252, public identity 1/1, all four
  calls/two modules, zero public stores/retired exact private refs, unchanged
  acyclic 48-module/205-edge DAG, UTF-8/non-ASCII preservation 4/4, and diff
  check passed. Intermediate graph-owner runs exposed only expected static
  row-count, caller-hash, and prior method-count baselines before final pass.
  Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only API visibility and recorded structural baselines.
It proves no behavior, quality, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

### Surface-match-variants private-API characterization checkpoint

- A docs-only inventory selects the current exact 11-line
  `financial_row_surfaces._surface_match_variants(text: str) -> List[str]`
  definition for an in-place public rename to `surface_match_variants(...)`.
  No source or test rename has occurred.
- The projection preserves four top-level statements, one `if`, two returns,
  one generator expression, raw truth, one normalization, fresh blank-list
  return, exact four-item eager annotation/period projection order, the fresh
  repeated annotation call, truth-filtered ordered-dictionary dedupe, first-
  representative identity, immutability, absence of string coercion, and every
  uncaught truth/normalization/helper/hash/equality/materialization failure.
- Nine one-positional-argument direct calls across row surfaces, graph
  calculation, and operand resolution remain at caller `try` depth zero;
  external/local calls are 7/2 across six caller definitions. Exact result
  assignment, direct iteration, set conversion, lazy `any(...)`, compact
  matching, score adoption, later work, and exception stops remain caller-
  owned. Existing edges keep the full DAG unchanged and acyclic at 48 modules/
  205 edges.
- Projected row counts are 15/11 to 16/10, while operand resolution remains
  54/37. No future public-name definition/store exists. The body SHA-256 is
  `29c48c8cead8adae91f09ba55f963b4eb926a13e2012444c1c401f2d5b461ee6`.
  The private identifier has 12 production AST references across three files;
  27 exact references in 11 graph-helper test methods form the bounded test
  transform surface.
- A naive span lookup selects baseline fingerprints `25f17ac6aad50c38` and
  `29c0f2198b3be826` at stale `first_lines: [66]`, but their `억`/`조` literals
  are not owned by this helper; its only string literal is `""`. The rename
  changes no line or literal, so all 217 records remain unchanged.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  214/214, surface owner 1/1, operand owner 69/69, affected semantic
  1,174/1,174, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
  import 19/19, audit 217, full 2,067/2,067, public identity 3/3, production
  transform 3/3, selected-body/six-caller parity, all nine calls/three modules,
  unchanged DAG, retired-ref/public-store zero, existing graph-test AST parity
  210/210 plus four new methods, UTF-8/non-ASCII preservation 4/4, pycompile,
  and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
baseline-provenance inspection passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Surface-match-variants public-API milestone

- Commit `05415ed` renames the exact former 11-line private helper in its
  existing row-surface owner to public `surface_match_variants(...)`. Its four
  top-level statements, one `if`, two returns, and one generator expression are
  exact after definition-name normalization; the private definition and
  executable refs are gone without a wrapper or bridge.
- Four CURRENT-SOURCE methods pin raw and normalized truth, blank fresh-list
  return, exact eager annotation/period call order, repeated annotation call,
  truth/hash/equality order, first-representative identity, immutability,
  uncaught failures, caller arguments/adoption/stops, imports, DAG, stale audit
  provenance, and public-name store absence.
- All nine calls across row surfaces, graph calculation, and operand resolution
  now bind the public API at caller `try` depth zero. External/local calls are
  7/2 across six caller definitions. Assignment, iteration, set conversion,
  lazy `any(...)`, compact matching, score adoption, fallback, later work, and
  exception stops remain caller-owned.
- Production source is `+12/-12`, net `0`; tests are `+1,514/-42`, net `+1,472`;
  and the whole commit is `+1,526/-54`, net `+1,472`. Production physical line
  counts are unchanged. Four methods move discovery from 2,063 to 2,067. Final
  row counts are 16/10; operand resolution remains 54/37. The committed source
  diff SHA-256 is
  `a49845578a7a70c8479ac01921d75bc30bdd7631799a2ab0498a59511619e7d9`.
- Focused pre/post rename 4/4, graph owner 214/214, surface owner 1/1, operand
  owner 69/69, affected eleven-module semantic 1,174/1,174, additional
  retrieval-pipeline 1/1, reconciliation plan 51/51, import-side-effects
  19/19, runtime-domain audit 217, and full discovery 2,067/2,067 passed.
  Pycompile, production transform parity 3/3, selected-body and six caller
  bodies, existing graph-test AST parity 210/210 plus four new methods, public
  identity 3/3, all nine calls/three modules, zero public stores/retired exact
  private refs, unchanged acyclic 48-module/205-edge DAG, UTF-8/non-ASCII
  preservation 4/4, and diff check passed. Intermediate graph-owner runs
  exposed only the expected static row-count, caller-hash, body-hash, and prior
  method-count baselines before final pass. Benchmark refresh and remote CI
  were **NOT RUN**.

This milestone changes only API visibility and recorded structural baselines.
It proves no behavior, quality, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

### Operand-text-match private-API characterization checkpoint

- A docs-only inventory selects the current exact 16-line
  `financial_row_surfaces._operand_text_match(text: str, operand: Dict[str, Any]) -> bool`
  definition for an in-place public rename to `operand_text_match(...)`. No
  source or test rename has occurred.
- The projection preserves four top-level statements, three assignments, two
  `if` nodes, three nested loops, three returns, five calls, no `try` or
  comprehension, initial variant assignment/blank stop, per-haystack compact
  regex and fresh operand-needle lookup, per-needle fresh variant lookup,
  per-variant compact regex, exact/substring/compact short-circuit order,
  exact bool results, immutability, and every uncaught failure.
- Sixty-two two-positional-argument direct calls across ten source modules
  remain at caller `try` depth zero with no keywords; external/local calls are
  59/3 across 36 caller definitions. Nine external importers already reach row
  surfaces, so the full DAG stays unchanged and acyclic at 48 modules/205
  edges.
- Projected row counts are 16/10 to 17/9. No future public-name definition/store
  exists. The body SHA-256 is
  `08d56d35cbc7cf2256047e0c51fabc9d9fc37569cfed8ab349dd277989b930b0`.
  The private identifier has 72 production AST references; 103 exact references
  in 32 graph-helper test methods form the bounded eleven-file source/test
  transform surface.
- A naive span lookup selects baseline fingerprints `8d15177a51f8ea8a` and
  `508662ee99ee39e5` at stale `first_lines: [79]` and `[83]`, but their numeric-
  unit regexes are not owned by this helper; its literals are `""` and
  `r"\s+"`. The rename moves no line or literal, so all 217 records remain
  unchanged.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  218/218, surface owner 1/1, operand owner 69/69, affected semantic
  1,178/1,178, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
  import 19/19, audit 217, full 2,071/2,071, public identity 10/10, production
  transform 10/10, selected-body/36-caller parity, all 62 calls/ten modules,
  unchanged DAG, retired-ref/public-store zero, existing graph-test AST parity
  214/214 plus four new methods, UTF-8 decode 11/11 and non-ASCII preservation
  9/9, pycompile, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
baseline-provenance inspection passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Operand-text-match public-API milestone

- Commit `6f28f8b` renames the exact former 16-line private helper in its
  existing row-surface owner to public `operand_text_match(...)`. Its four top-
  level statements, three assignments, two `if` nodes, three loops, three
  returns, five calls, initial variant/blank stop, per-haystack fresh needle
  lookup, per-needle fresh variants, and exact/substring/compact short-circuit
  order are exact after definition-name normalization. No wrapper or private
  alias was added.
- Four CURRENT-SOURCE methods pin variant/needle/normalized-needle iteration,
  regex and predicate order, exact bool results, immutability, uncaught
  failures, caller arguments/adoption/stops, imports, DAG, stale audit
  provenance, and public-name store absence.
- All 62 calls across ten source modules now bind the public API at caller
  `try` depth zero with two positional arguments and no keywords. External/
  local calls are 59/3 across 36 caller definitions, and all nine external
  importers share the exact row-owner function identity.
- The checkpoint counted 103 exact references in 32 graph-helper methods.
  Broader owner/semantic runs exposed another 30 live patch/import references
  across operand resolution, aggregate subtask projection, dependency
  projection, task artifacts, and lookup recovery tests. Those live bindings
  were migrated; the verified source/test transform is 16 files, not the
  projected 11. One task-artifact negative source-text assertion and the four
  transition contracts retain the retired spelling only as non-executable
  evidence.
- Production source is `+72/-72`, net `0`; tests are `+1,630/-158`, net
  `+1,472`; and the whole commit is `+1,702/-230`, net `+1,472`. Production
  physical line counts are unchanged. Four methods move discovery from 2,067
  to 2,071. Final row counts are 17/9. The committed source diff SHA-256 is
  `994ebce19f931072d564b7e12678100b79648799b0c09342b4d5e50c65c80a08`.
- Focused pre/post rename 4/4, graph owner 218/218, surface owner 1/1, operand
  owner 69/69, affected eleven-module semantic 1,178/1,178, additional
  retrieval-pipeline 1/1, reconciliation plan 51/51, import-side-effects
  19/19, runtime audit 217, and full discovery 2,071/2,071 passed. The
  additional changed-consumer union passed 246/246. Pycompile, production
  transform 10/10, full transform 16/16, selected-body/36-caller parity,
  existing graph-test AST 214/214 plus four new methods, public identity 10/10,
  all 62 calls/ten modules, zero public stores and retired production refs,
  unchanged acyclic 48-module/205-edge DAG, UTF-8 decode 16/16, non-ASCII
  preservation 12/12, and diff check passed. Intermediate runs exposed only
  expected structural baseline updates and the additional stale test patch
  points. Benchmark refresh and remote CI were **NOT RUN**.

This milestone changes only API visibility and recorded structural baselines.
It proves no behavior, quality, ranking, performance, benchmark, schedule,
ledger, or Phase 3 completion claim.

### Numeric-value-after-operand-text private-API characterization checkpoint

- A docs-only inventory selects the current exact 16-line
  `financial_row_surfaces._extract_numeric_value_after_operand_text(text: str, operand: Dict[str, Any]) -> str`
  definition for an in-place public rename to
  `extract_numeric_value_after_operand_text(...)`. No source or test rename has
  occurred. Parenthetical, numeric-match, and candidate-construction helpers
  remain private and row-local.
- The projection preserves four top-level statements, five assignments, four
  `if` nodes, one loop, two `continue` statements, three returns, nine calls,
  one generator, one lambda, and no `try` or list comprehension. It pins raw
  normalization/blank stop, fresh needle iteration, needle normalization and
  compaction, falsey continue, character-wise escaped spaced-pattern
  construction, one search, one candidate projection, stable distance sort,
  first `[0][1]` result identity, exhausted blank return, immutability, and
  every uncaught failure.
- Five two-positional-argument calls across graph calculation, graph evidence,
  and operand resolution remain at caller `try` depth zero with no keywords;
  external/local calls are 5/0 across three caller definitions. The three
  importers already reach row surfaces, so the full DAG remains unchanged and
  acyclic at 48 modules/205 edges.
- Projected row counts are 17/9 to 18/8. No future public-name definition/store
  exists. The body SHA-256 is
  `bdac2c1b9337a7d415b802d2af850ee5c9e4b1c242995310553e765e748fb8ab`.
  The private identifier has nine production AST references. Twelve exact test
  references across graph helpers, operand resolution, operation contracts,
  and semantic numeric plan make the bounded source/test transform eight
  files.
- The current 226-241 span selects no reviewed runtime-domain record. Its
  string literals are `""`, `r"\s+"`, and `r"\s*"`, so the rename moves no
  reviewed literal and all 217 records remain unchanged.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  222/222, surface owner 1/1, operand owner 69/69, affected semantic
  1,182/1,182, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
  import 19/19, audit 217, full 2,075/2,075, public identity 4/4, production
  transform 4/4, selected-body/three-caller parity, all five calls/three
  modules, unchanged DAG, retired-ref/public-store zero, existing graph-test
  AST parity 218/218 plus four new methods, UTF-8/non-ASCII preservation 8/8,
  pycompile, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
baseline-provenance inspection passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Numeric-value-after-operand-text public-API milestone

- Commit `7739ab0` renames the exact former 16-line private helper in its
  existing row-surface owner to public
  `extract_numeric_value_after_operand_text(...)`. Its four top-level
  statements, five assignments, four `if` nodes, one loop, two continues,
  three returns, nine calls, one generator, one lambda, normalization, compact
  and escaped-pattern construction, search, candidate projection, stable sort,
  and selected `[0][1]` identity are exact after definition-name normalization.
  No wrapper or private alias was added.
- Four CURRENT-SOURCE methods pin normalization and blank stop, fresh needle
  iteration, character escape and generator order, candidate truth/sort/key/
  subscript behavior, stable ties, immutability, every uncaught failure, caller
  arguments/adoption/stops, imports, DAG, audit provenance, and public-store
  absence.
- All five calls across graph calculation, graph evidence, and operand
  resolution now bind the public API at caller `try` depth zero with two
  positional arguments and no keywords. External/local calls are 5/0 across
  three caller definitions, and all three external importers share the exact
  row-owner function identity.
- Production source is `+9/-9`, net `0`; tests are `+1,418/-31`, net `+1,387`;
  and the whole commit is `+1,427/-40`, net `+1,387`. Production physical line
  counts are unchanged. Four methods move discovery from 2,071 to 2,075. Final
  row counts are 18/8. The committed source/test diff SHA-256 is
  `0c1e7bbee0516f8afcc9579c0d66837d586a25522b1e9bb05812e3b5b6daa763`.
- Focused pre/post rename 4/4, graph owner 222/222, surface owner 1/1, operand
  owner 69/69, affected semantic 1,182/1,182, additional retrieval-pipeline
  1/1, reconciliation plan 51/51, import side effects 19/19, runtime audit 217,
  and full discovery 2,075/2,075 passed. Pycompile, production transform 4/4,
  source/test transform 8/8, selected-body/three-caller parity, existing graph-
  test AST 218/218 plus four methods, public identity 4/4, all calls/modules,
  unchanged 48-module/205-edge DAG, retired live refs/public stores zero,
  UTF-8/non-ASCII preservation 8/8, and diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This milestone changes only
  API visibility and structural baselines; it is not a behavior, quality,
  ranking, performance, benchmark, schedule, ledger, or Phase 3 completion
  claim.

### Structured-candidate-row-text private-API characterization checkpoint

- A docs-only inventory selects the smaller remaining cross-module seam: the
  current exact 24-line
  `financial_row_surfaces._format_structured_candidate_row_text(label: str, headers: List[str], cells: List[Dict[str, Any]]) -> str`
  definition for an in-place public rename to
  `format_structured_candidate_row_text(...)`. No source or test rename has
  occurred. The 47-line unstructured-table parser remains private and outside
  this batch.
- The projection preserves four top-level statements, one annotated and three
  plain assignments, two loops, two `if` nodes, one return, 19 calls, four list
  nodes, one starred item, two generators, five boolean operations, two
  comprehension clauses, and no `try`, lambda, or list comprehension. It pins
  eager label/header expansion, raw truth/string/normalization, ordered dedupe,
  repeated retained-header normalization, eager header/value/unit construction,
  exact slash/space/pipe joins, truth-gated cell append without dedupe,
  immutability, and every uncaught failure.
- Two three-positional-argument calls in graph helpers remain at caller `try`
  depth zero with no keywords; external/local calls are 2/0 across table-value
  and table-row candidate builders. The sole importer already reaches row
  surfaces, so the full DAG remains unchanged and acyclic at 48 modules/205
  edges.
- Projected row counts are 18/8 to 19/7. No future public-name definition/store
  exists. The body SHA-256 is
  `596e6a345e220615c487d56760d77ff26b1cac1ed5721301c16f7ddf15e0a127`.
  The private identifier has four production AST references. Two exact test
  patch-name references in one graph-helper method make the bounded source/test
  transform three files.
- The current 304-327 span selects no reviewed runtime-domain record. Its exact
  literals and all 217 baseline records must remain unchanged.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  226/226, surface owner 1/1, operand owner 69/69, affected semantic
  1,186/1,186, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
  import 19/19, audit 217, full 2,079/2,079, public identity 2/2, production
  transform 2/2, full transform 3/3, selected-body/two-caller parity, both
  calls/the sole call module, unchanged DAG, retired-ref/public-store zero,
  existing graph-test AST parity 222/222 plus four methods, UTF-8/non-ASCII
  preservation 3/3, pycompile, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
baseline-provenance inspection passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Structured-candidate-row-text public-API milestone

- Commit `72eb1b8` renames the exact former 24-line private helper in its
  existing row-surface owner to public
  `format_structured_candidate_row_text(...)`. Eager label/header expansion,
  ordered dedupe, repeated retained-header normalization, eager header/value/
  unit construction, exact slash/space/pipe joins, truth-gated cell append
  without dedupe, immutability, and uncaught failures are unchanged. No wrapper
  or private alias was added.
- Both graph-helper calls now bind the public API at caller `try` depth zero
  with three positional arguments and no keywords. External/local calls are
  2/0 across two caller definitions, and the sole importer shares the exact
  row-owner function identity.
- Production source is `+4/-4`, tests are `+1,150/-22`, and the whole commit is
  `+1,154/-26`, net `+1,128`. Production physical line counts are unchanged.
  Four methods move discovery from 2,075 to 2,079; final row counts are 19/7.
  The committed source/test diff SHA-256 is
  `c3cbf8676f4e5df9b66101acdaf05070adf07eb6a3e702de883e65f2557e6789`.
- Focused pre/post rename 4/4, graph owner 226/226, surface owner 1/1, operand
  owner 69/69, affected semantic 1,186/1,186, additional retrieval-pipeline
  1/1, reconciliation plan 51/51, import 19/19, runtime audit 217, full
  2,079/2,079, pycompile, transform 3/3, selected-body/two-caller parity,
  public identity 2/2, unchanged 48-module/205-edge DAG, retired live-ref/
  public-store zero, UTF-8/non-ASCII 3/3, and diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Unstructured-table-row-cell parser private-API characterization checkpoint

- A docs-only inventory selects the sole remaining cross-module row private
  API: the exact current 47-line
  `financial_row_surfaces._parse_unstructured_table_row_cells(row_text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]`
  definition for an in-place public rename to
  `parse_unstructured_table_row_cells(...)`. No source or test rename has
  occurred and no wrapper or private alias is authorized.
- The body has 15 top-level statements, one annotated and 17 plain assignments,
  one loop, seven `if` nodes, three returns, one continue, 44 calls, eight list
  nodes, one dict, five list comprehensions, nine boolean operations, five
  comparisons, three conditional expressions, five comprehension clauses, and
  no `try`, lambda, or generator. It pins row truth/string/normalization,
  pipe/split/strip/filter gates, repeated header and period conversion, header-
  then-period-then-synthetic fallback precedence, digit filtering, exact
  labeled-value regex/group order, fresh four-key cell append, immutability,
  and every uncaught failure.
- Seven two-positional-argument calls in five importers remain at caller `try`
  depth zero with no keywords; external/local calls are 7/0 across six caller
  definitions. Existing-cell and candidate-kind gates, enrichment, scoring,
  selection, reconciliation, evidence/candidate adoption, graph state,
  artifacts, ledgers, and final sequencing remain caller-owned hard stops. The
  DAG remains unchanged and acyclic at 48 modules/205 edges.
- Projected row counts are 19/7 to 20/6. The body SHA-256 is
  `610ff588880f3945b2737923a0c6238b59c4b6e2b8f293c1914b1048fed84496`.
  The private identifier has 13 production AST references. Twenty-one exact
  test refs across four test files make the bounded transform ten files. Call
  records hash to
  `56c133f9852c0e013747dfb6a625d7af13a5713f15dcc06974d6fafe0e9fc201`;
  the six-caller map hashes to
  `d9baa809818738f83553b8eb486972848e9510c6a353ed4520b09164c9214e72`.
- The current 255-301 span selects no reviewed runtime-domain record. Its unit
  regex is parser-structure vocabulary, so all 217 records remain unchanged.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  230/230, surface owner 1/1, operand owner 69/69, affected semantic
  1,190/1,190, retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19,
  audit 217, full 2,083/2,083, public identity 6/6, production transform 6/6,
  full transform 10/10, selected-body/six-caller parity, all seven calls/five
  modules, unchanged DAG, retired-ref/public-store zero, existing graph-test
  AST 226/226 plus four methods, UTF-8 10/10, non-ASCII 9/9, pycompile, and
  diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
baseline-provenance inspection passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Unstructured-table-row-cell parser public-API milestone

- Commit `ac90a62` renames the exact former 47-line private helper in its
  existing row-surface owner to public
  `parse_unstructured_table_row_cells(...)`. Row/header/period fallback order,
  repeated conversions, numeric filtering, labeled-value regex/group order,
  fresh cell construction, immutability, and uncaught failures are unchanged.
  No wrapper or private alias was added.
- All seven calls across five importers now bind the public API at caller `try`
  depth zero with two positional arguments and no keywords. External/local
  calls are 7/0 across six caller definitions, and all five importers share the
  exact row-owner function identity. Caller-owned gates, scoring, reconciliation,
  selection, evidence/candidate adoption, state, artifacts, and ledgers did not
  move.
- Production source is `+13/-13`, tests are `+1,511/-48`, and the whole commit
  is `+1,524/-61`, net `+1,463`. Production physical line counts are unchanged.
  Four methods move discovery from 2,079 to 2,083; final row counts are 20/6.
  The committed source/test diff SHA-256 is
  `8faf60239bc6d907001d3144dadd2aa5201e7fb6e0c701b4a9c02e09439fef17`.
- Focused pre/post rename 4/4, graph owner 230/230, surface owner 1/1, operand
  owner 69/69, affected semantic 1,190/1,190, retrieval-pipeline 1/1,
  reconciliation plan 51/51, import 19/19, runtime audit 217, and full
  2,083/2,083 passed. Pycompile, production transform 6/6, source/test transform
  10/10, selected-body/six-caller parity, existing graph-test AST 226/226 plus
  four methods, public identity 6/6, all-call/DAG/retired-ref/public-store,
  UTF-8 10/10, non-ASCII 9/9, and diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Structured-cell period-text private-API characterization checkpoint

- A docs-only inventory selects the exact current 35-line
  `financial_structured_cells._structured_cell_period_text(cell: Dict[str, Any], query_years: List[int], period_focus: str) -> str`
  definition for an in-place public rename to
  `structured_cell_period_text(...)`. No source or test rename has occurred and
  no wrapper or private alias is authorized.
- The body has 16 top-level statements, one annotated and 12 plain assignments,
  two loops, eight `if` nodes, seven returns, one continue, one try, 33 calls,
  one list, six tuples, one list comprehension, five generators, nine boolean
  operations, 11 comparisons, one conditional expression, six comprehension
  clauses, and no lambda or dict. It pins policy-copy and marker construction
  order, repeated marker/header conversion, eager report-year lookup, narrow
  integer-conversion handling, ordered query-year matching, current/prior
  precedence, report-year/policy-hint projection, fiscal-rank fallback, final
  header fallback, immutability, and every uncaught failure.
- Four three-positional-argument calls in four importers remain at caller `try`
  depth zero with no keywords; external/local calls are 4/0 across four caller
  definitions. Cell scoring, operand/report gates, regex decisions, direct
  acceptance, lookup realignment, reconciliation fallback/pairing, evidence
  adoption, graph state, artifacts, ledgers, and final sequencing remain caller-
  owned hard stops. The DAG remains acyclic at 48 modules/205 edges.
- Projected structured-cell counts are 4/4 to 5/3. The body SHA-256 is
  `52ce9a60948e6d2e3d57f080f4e0577f7c782b99900bd62839f256057be40c44`.
  The private identifier has nine production AST references. Twenty-five exact
  test refs across four test files make the bounded transform nine files. Call
  records hash to
  `541b793fe8e0596a0d0271c2a87e373c1c88d12a34ffe549b641e6b67d7ffec1`;
  the four-caller map hashes to
  `0c001d08e2e10c64ad9dab82bf1ab50a892064e21341a3b6c2c42f5939875222`.
- The current 328-362 span selects no reviewed runtime-domain record, so all
  217 records remain unchanged.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  234/234, surface owner 1/1, operand owner 69/69, affected semantic
  1,194/1,194, retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19,
  audit 217, full 2,087/2,087, public identity 5/5, production transform 5/5,
  full transform 9/9, selected-body/four-caller parity, all four calls/modules,
  unchanged DAG, retired-ref/public-store zero, existing graph-test AST 230/230
  plus four methods, UTF-8 9/9, non-ASCII 7/7, pycompile, and diff check are
  governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
baseline-provenance inspection passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Structured-cell period-text public-API milestone

- Commit `89227aa` renames the exact former 35-line private helper in its
  existing structured-cell owner to public `structured_cell_period_text(...)`.
  Policy-copy/marker construction order, repeated marker/header conversion,
  report/query-year precedence, current/prior and fiscal-rank/header fallback,
  immutability, and uncaught failures are unchanged. No wrapper or private alias
  was added.
- All four calls across four importers now bind the public API at caller `try`
  depth zero with three positional arguments and no keywords. External/local
  calls are 4/0 across four caller definitions, and all importers share the
  exact owner identity. Cell scoring, direct acceptance, lookup realignment,
  reconciliation fallback/pairing, evidence adoption, state, artifacts, and
  ledgers did not move.
- Production source is `+9/-9`, tests are `+1,670/-45`, and the whole commit is
  `+1,679/-54`, net `+1,625`. Production physical line counts are unchanged.
  Four methods move discovery from 2,083 to 2,087; final structured-cell counts
  are 5/3. The committed source/test diff SHA-256 is
  `ce057382b96c939e60bd0e2f6d14d1773e0c4cd2f759c7bc8983cc65847ed938`.
- Focused pre/post rename 4/4, graph owner 234/234, surface owner 1/1, operand
  owner 69/69, affected semantic 1,194/1,194, retrieval-pipeline 1/1,
  reconciliation plan 51/51, import 19/19, runtime audit 217, and full
  2,087/2,087 passed. Pycompile, production transform 5/5, source/test transform
  9/9, selected-body/four-caller parity, existing graph-test AST 230/230 plus
  four methods, public identity 5/5, all-call/DAG/retired-ref/public-store,
  UTF-8 9/9, non-ASCII 7/7, and diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Ratio-percent-query private-API characterization checkpoint

- A docs-only inventory selects the exact current 3-line
  `financial_operation_policies._is_ratio_percent_query(text: str) -> bool`
  definition for an in-place public rename to `is_ratio_percent_query(...)`.
  No source or test rename has occurred and no wrapper or private alias is
  authorized. Loader adapters and shared normalization internals remain
  intentionally outside this batch.
- The body has one assignment, one return, three calls, one generator and
  comprehension, one boolean operation, one comparison, and one tuple, with no
  branch or internal exception handler. It pins exact input identity into
  normalization, subsequent policy-marker lookup, marker-container truth and
  empty-tuple fallback, lazy membership iteration, first-truthy short circuit,
  immutability, and every owner-uncaught failure.
- Seven one-positional-argument calls in four importers use no keywords across
  seven caller definitions. Six remain at caller `try` depth zero. The
  calculation call remains at depth one behind missing-operand/no-direct-
  grounding gates; its existing broad handler preserves the missing/debug-state
  return on classifier failure. Evidence admission, operation inference,
  supplemental scoring, missing-info projection, reflection objective, ratio
  fallback, state, artifacts, ledgers, and sequencing remain caller-owned hard
  stops. The DAG remains acyclic at 48 modules/205 edges.
- Projected operation-policy counts are 0/7 to 1/6. The body SHA-256 is
  `012a658abd30affb03148f954237974188e5b7d64ad10c522753a1cfe803d09e`.
  The private identifier has 12 production AST references. Three exact live
  test refs in one reflection-capability file make the live rename six files;
  the new graph contract file makes the complete transform seven. Call records
  hash to
  `86067daddcf3b370a5219834120499482d0cbec9b38f4088fa35a0fab079aab5`;
  the seven-caller map hashes to
  `53b03c8e7d8175b868aea94c24dd259a23cdf691676a370a38fb8b129f42168b`.
- The current 31-33 span selects no reviewed runtime-domain record, so all 217
  records remain unchanged.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  238/238, surface owner 1/1, operand owner 69/69, affected semantic
  1,198/1,198, reflection capability 24/24, retrieval-pipeline 1/1,
  reconciliation plan 51/51, import 19/19, audit 217, full 2,091/2,091, public
  identity 5/5, production transform 5/5, complete transform 7/7, selected-body/
  seven-caller parity, all seven calls/four modules, unchanged DAG, retired-ref/
  public-store zero, existing graph-test AST 234/234 plus four methods, UTF-8
  7/7, non-ASCII 6/6, pycompile, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
baseline-provenance inspection plus the current reflection-capability 24/24
gate passed. Benchmark refresh and remote CI were **NOT RUN**. This checkpoint
is not a behavior, quality, ranking, performance, benchmark, schedule, or
completion claim.

### Ratio-percent-query public-API milestone

- Commit `f010b6f` renames the exact former 3-line private classifier in its
  existing operation-policy owner to public `is_ratio_percent_query(...)`.
  Input identity, normalization, policy-marker lookup, marker-container truth,
  empty-tuple fallback, lazy membership, first-truthy stop, immutability, and
  owner-uncaught failures are unchanged. No wrapper or private alias was added.
- All seven calls across four importers now bind the public API with one
  positional argument and no keywords. Six callers remain at `try` depth zero;
  the calculation call remains at depth one behind the current short-circuit
  gates and broad missing/debug-state fallback. Evidence admission, operation
  inference, supplemental scoring, missing-info projection, reflection
  objective, ratio fallback, state, artifacts, and ledgers did not move.
- Production source is `+12/-12`, tests are `+1,446/-12`, and the whole commit
  is `+1,458/-24`, net `+1,434`. Production physical line counts are unchanged.
  Four methods move discovery from 2,087 to 2,091; final operation-policy counts
  are 1/6. The committed source/test diff SHA-256 is
  `53eea332fd2447c3ccde0c16e20ae1ccb5c2a5cb48a82a11f3c64746636d044c`.
- Focused pre/post rename 4/4, graph owner 238/238, surface owner 1/1, operand
  owner 69/69, affected semantic 1,198/1,198, reflection capability 24/24,
  retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, runtime audit
  217, and full 2,091/2,091 passed. Pycompile, production transform 5/5,
  complete transform 7/7, selected-body/seven-caller parity, existing graph-
  test AST 234/234 plus four methods, public identity 5/5, all-call/DAG/retired-
  ref/public-store, UTF-8 7/7, non-ASCII 6/6, and diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Narrative-context-query private-API characterization checkpoint

- A docs-only inventory selects the exact current 6-line
  `financial_operation_policies._query_requests_narrative_context(query: str) -> bool`
  definition for an in-place public rename to
  `query_requests_narrative_context(...)`. No source or test rename has
  occurred and no wrapper or private alias is authorized. Loader adapters and
  shared normalization internals remain intentionally outside this batch.
- The body has two assignments, one `if`, two returns, eight calls, two
  generators/comprehensions, two boolean operations, one comparison, one tuple,
  and no `try`, loop, lambda, list, or dict. It pins raw input truth and empty-
  string fallback, conversion/normalization/lowercase order, blank early return,
  later policy lookup and marker-container truth, eager ordered tuple creation
  with retained-item double conversion, lazy membership, first-truthy stop,
  immutability, and every owner-uncaught failure.
- Eighteen one-positional-argument calls in five importers use no keywords
  across 18 caller definitions, all at caller `try` depth zero. Nine calculation
  and five evidence paths plus hybrid-task admission, compression guidance, and
  two text-surface paths retain their current gates, assignments, adoption,
  false-result stops, and exception propagation. Evidence/result mutation,
  retrieval, state, artifacts, ledgers, and sequencing remain caller-owned hard
  stops. The DAG remains acyclic at 48 modules/205 edges.
- Projected operation-policy counts are 1/6 to 2/5. The body SHA-256 is
  `e3ab908fe08a56dd67a302d8fd9f28c20413136e58ab33832e4d858cc9ecf9a9`.
  The private identifier has 24 production AST references. Sixty-one exact live
  test refs across six files make the complete source/test transform 12 files.
  Call records hash to
  `ef07a28d7d4fd72951c8814b810062cb60e49922590f83d0f6585986aa3fb063`;
  the 18-caller map hashes to
  `12c5fb354fe3d80dace6e5d38276d171deb84780820a33c41b3577a7e2aa938a`.
- The current 36-41 span selects no reviewed runtime-domain record, so all 217
  records remain unchanged.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  242/242, surface owner 1/1, operand owner 69/69, affected semantic
  1,202/1,202, answer-projection 23/23, retrieval-hints 5/5, text-surface 30/30,
  reflection capability 24/24, retrieval-pipeline 1/1, reconciliation plan
  51/51, import 19/19, audit 217, full 2,095/2,095, public identity 6/6,
  production transform 6/6, complete transform 12/12, selected-body/18-caller
  parity, all 18 calls/five modules, unchanged DAG, retired-ref/public-store
  zero, existing graph-test AST 238/238 plus four methods, UTF-8 12/12, non-
  ASCII 9/9, pycompile, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
baseline-provenance inspection passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Narrative-context-query public-API milestone

- Commit `1883395` renames the exact former 6-line private classifier in its
  existing operation-policy owner to public
  `query_requests_narrative_context(...)`. Raw input truth/empty-string
  fallback, conversion/normalization/lowercase order, blank early return,
  policy lookup/container truth, eager ordered tuple construction with retained-
  item double conversion, lazy membership, first-truthy stop, immutability, and
  owner-uncaught failures are unchanged. No wrapper or private alias was added.
- All 18 calls across five importers now bind the public API with one positional
  argument, no keywords, and caller `try` depth zero. Nine calculation and five
  evidence callers plus hybrid-task admission, compression guidance, and two
  text-surface projections retain their exact gates, assignments, adoption,
  false-result returns, and failure stops. Evidence/result mutation, retrieval,
  calculation, state, artifacts, and ledgers did not move.
- Production source is `+24/-24`, tests are `+1,467/-76`, and the whole commit
  is `+1,491/-100`, net `+1,391`. Production physical line counts are
  unchanged. Four methods move discovery from 2,091 to 2,095; final operation-
  policy counts are 2/5. The committed source/test diff SHA-256 is
  `653a3d7733bb763cb69a1163293a20bbb6171a022c99ceb80d1375260021bcb4`.
- Focused pre/post rename 4/4, graph owner 242/242, surface owner 1/1, operand
  owner 69/69, affected semantic 1,202/1,202, answer-projection 23/23,
  retrieval-hints 5/5, text-surface 30/30, reflection capability 24/24,
  retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, runtime audit
  217, and full 2,095/2,095 passed. Pycompile, production transform 6/6,
  complete transform 12/12, selected-body/18-caller parity, existing graph-test
  AST 238/238 plus four methods, public identity 6/6, all-call/DAG/retired-ref/
  public-store, UTF-8 12/12, non-ASCII 9/9, and diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Percent-metric-label private-API characterization checkpoint

- A docs-only inventory selects the exact current 8-line
  `financial_operation_policies._label_implies_percent_metric(label: str) -> bool`
  definition for an in-place public rename to
  `label_implies_percent_metric(...)`. No source or test rename has occurred and
  no wrapper or private alias is authorized. Loader adapters and shared
  normalization internals remain intentionally outside this batch.
- The body has one assignment, one `if`, two returns, three calls, one
  generator/comprehension, one boolean operation, one comparison, one tuple,
  one starred element, and no `try`, loop, lambda, list, dict, or attribute. It
  pins raw input truth/empty-string fallback, conversion/normalization order,
  blank early return, eager configured-marker plus `"%"`/`"%p"` tuple
  construction, marker order/duplicates/identity, lazy membership, first-
  truthy stop, immutability, and every owner-uncaught failure.
- Five one-positional-argument calls in four importers use no keywords across
  four caller definitions, all at caller `try` depth zero. Graph unit-family
  inference, operand conflict detection's two short-circuited classifications,
  reconciliation unit hinting, and candidate selected-unit projection retain
  their current gates, arguments, true/false adoption, and exception stops.
  Normalization, unit policy/selection, conflict/adoption, reconciliation,
  candidate/evidence, state, artifacts, ledgers, and sequencing remain caller-
  owned hard stops. The DAG remains acyclic at 48 modules/205 edges.
- Projected operation-policy counts are 2/5 to 3/4. The body SHA-256 is
  `fe788855f6051ae481b30f779b4a0ecb56cd06d57ccb6b6f03eb0819f83405d2`.
  The private identifier has 10 production AST references. Thirteen exact live
  test refs across three files make the complete source/test transform eight
  files. Call records hash to
  `56a5c0f15d8617534785b8c7f3f91751203bfe4a6e6306840cc6cd5e7e460bb4`;
  the four-caller map hashes to
  `4890717f6ee4921092ee3eb2b7c84de31a4efc7846ee54c3ef07e52f6c880706`.
- The current 57-64 span selects no reviewed runtime-domain record, so all 217
  records remain unchanged.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  246/246, surface owner 1/1, operand owner 69/69, affected semantic
  1,206/1,206, reflection capability 24/24, retrieval-pipeline 1/1,
  reconciliation plan 51/51, import 19/19, audit 217, full 2,099/2,099, public
  identity 5/5, production transform 5/5, complete transform 8/8, selected-body/
  four-caller parity, all five calls/four modules, unchanged DAG, retired-ref/
  public-store zero, existing graph-test AST 242/242 plus four methods, UTF-8
  8/8, non-ASCII 5/5, pycompile, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
baseline-provenance inspection passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Percent-metric-label public-API milestone

- Commit `1c8400f` renames the exact former 8-line private classifier in its
  existing operation-policy owner to public
  `label_implies_percent_metric(...)`. Input truth/empty-string fallback,
  string conversion, normalization, blank early return, eager configured-
  marker plus `"%"`/`"%p"` tuple construction, marker order/duplicates/
  identity, lazy membership, first-truthy stop, immutability, and owner-
  uncaught failures are unchanged. No wrapper or private alias was added.
- All five calls across four importers now bind the public API with one
  positional argument, no keywords, and caller `try` depth zero. Graph unit-
  family inference, operand conflict detection's two short-circuited calls,
  reconciliation unit hinting, and candidate selected-unit projection retain
  their exact gates, arguments, true/false adoption, and failure stops.
  Normalization, unit policy/selection, conflict/adoption, reconciliation,
  candidate/evidence, state, artifacts, and ledgers did not move.
- Production source is `+10/-10`, tests are `+1,196/-28`, and the whole commit
  is `+1,206/-38`; production physical line counts are unchanged. Four methods
  move discovery from 2,095 to 2,099; final operation-policy counts are 3/4.
  The committed source/test diff SHA-256 is
  `0f772a3b30a68ebfeb08ef66c4ebcef6778d59d0a457040c341927981e421917`.
- Focused pre/post rename 4/4, graph owner 246/246, surface owner 1/1, operand
  owner 69/69, affected semantic 1,206/1,206, reflection promotion 15/15,
  reflection capability 24/24, retrieval-pipeline 1/1, reconciliation plan
  51/51, import 19/19, runtime audit 217, and full 2,099/2,099 passed.
  Pycompile, production transform 5/5, complete transform 8/8, selected-body/
  four-caller parity, existing graph-test AST 242/242 plus four methods, public
  identity 5/5, all-call/DAG/retired-production-ref/public-store, UTF-8 8/8,
  non-ASCII 5/5, and diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Single-metric-period-comparison private-API characterization checkpoint

- A docs-only inventory selects the exact current 11-line
  `financial_operation_policies._is_single_metric_period_comparison(query: str, operand_labels: List[str]) -> bool`
  definition for an in-place public rename to
  `is_single_metric_period_comparison(...)`. No source or test rename has
  occurred and no wrapper or private alias is authorized. Loader adapters and
  shared normalization internals remain intentionally outside this batch.
- The body has five assignments, two `if` nodes, three returns, ten calls, one
  list comprehension, two generators, three comprehension clauses, one boolean
  operation, two comparisons, one tuple, two attributes, and no `try`, loop,
  lambda, list literal, dict literal, or conditional expression. It pins raw
  query identity into normalization, shallow policy snapshotting, configured-
  marker lookup, eager ordered tuple construction with retained-item double
  conversion, lazy membership, first-truthy stop, and the no-marker return
  before operand access.
- After a marker hit, raw-truth operand-label filtering retains original
  objects; `list(dict.fromkeys(...))` keeps stable native hash/equality dedupe;
  at most one distinct truthy label returns true. Inputs remain immutable and
  every normalization, policy, marker, operand iteration/truth, hash/equality,
  materialization, comparison, and result failure remains uncaught.
- Three two-positional-argument calls in one graph-helper importer plus one
  owner-local call use no keywords across four caller definitions, all at
  caller `try` depth zero. Generic required-operand building, operation-family
  inference, concept required-operand building, and direct-grounding
  classification retain their current gates, exact arguments, result adoption,
  and exception stops. Operand construction, operation precedence, grounding,
  state, artifacts, ledgers, and sequencing remain caller-owned hard stops.
  The DAG remains acyclic at 48 modules/205 edges.
- Projected operation-policy counts are 3/4 to 4/3. The body SHA-256 is
  `0f482ee880c12e58fa61e1f2eebe8f106076206ddb28e5f1b82762678cd92654`.
  The private identifier has six production AST references across two files.
  Three exact live test refs in one file make the complete source/test transform
  three files. Current/projected call-record hashes are
  `8d669d2335fe20a683a7f2cc5ece357bfb67b05e10f9b79dafbe89bb613fc55c` /
  `fcf6044263e7d57e2b76101476a55f977eed4ff198f19784a8406e4f103a451e`;
  current/projected four-caller-map hashes are
  `d4001b30ee151bf9e255897688a3e6cdd5412932e69ae8febca0d7991d4ff1dd` /
  `3d89da74e4978fbe92a335abe1a6909e236b05c51932affdb8b8bec361658035`.
- The current 44-54 span selects no reviewed runtime-domain record, so all 217
  records remain unchanged.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  250/250, surface owner 1/1, operand owner 69/69, affected semantic
  1,210/1,210, reflection capability 24/24, retrieval-pipeline 1/1,
  reconciliation plan 51/51, import 19/19, audit 217, full 2,103/2,103, public
  identity 2/2, production transform 2/2, complete transform 3/3, selected-body/
  four-caller parity, all four calls/two modules, unchanged DAG, retired-ref/
  public-store zero, existing graph-test AST 246/246 plus four methods, UTF-8
  3/3, non-ASCII 2/2, pycompile, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/DAG/function-count/import/public-store and
baseline-provenance inspection passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Single-metric-period-comparison public-API milestone

- Commit `f0fae1f` renames the exact former 11-line classifier in its existing
  operation-policy owner to public
  `is_single_metric_period_comparison(...)`. Query identity/normalization,
  shallow policy snapshotting, eager marker tuple creation, lazy membership,
  truthy-label filtering, stable native hash/equality dedupe, return values,
  immutability, and owner-uncaught failures are unchanged. No wrapper or private
  alias was added.
- All four source calls across two modules now bind the public API with two
  positional arguments, no keywords, and caller `try` depth zero. Generic-
  operand, operation-family, and direct-grounding calls retain their exact
  gates, arguments, adoption, and stops. The renamed concept-operand call is
  source-visible but runtime-unreachable: its condition requires one
  `ordered_specs` element and an empty `raw_explicit_roles` list after that list
  was rebuilt one-to-one from `ordered_specs`. The new CURRENT-SOURCE caller
  contract corrects the earlier characterization without changing behavior.
- Production source is `+6/-6`, tests are `+1,627/-23`, and the whole commit is
  `+1,633/-29`; production physical lines are unchanged. Four methods move
  discovery from 2,099 to 2,103. Final operation-policy public/private counts
  are 4/3. The committed source/test diff SHA-256 is
  `190b8c55912b139f610b4fda1bca8ada5ee4051ac5142eef0bf112116adb869d`.
- Focused pre/post rename 4/4, graph owner 250/250, surface owner 1/1, operand
  owner 69/69, affected semantic 1,210/1,210, reflection promotion 15/15,
  reflection capability 24/24, retrieval-pipeline 1/1, reconciliation plan
  51/51, import 19/19, runtime audit 217, and full 2,103/2,103 passed.
  Pycompile, production transform 2/2, complete transform 3/3, selected-body/
  four-caller parity, graph-test AST 246/246 plus four methods, public identity
  2/2, all four calls/two modules, unchanged 48-module/205-edge DAG, retired
  production refs/public stores zero, UTF-8 3/3, non-ASCII 2/2, and diff check
  passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a quality, ranking, performance, benchmark, schedule,
  ledger, or Phase 3 completion claim.

### Unreachable single-metric concept branch deletion characterization checkpoint

- The next docs-only inventory selects only the exact current 9-line branch at
  graph-helper lines 1623-1631 inside
  `_build_concept_required_operands(...)` for deletion without replacement. No
  adjacent API, helper, policy, state, artifact, ledger, or sequencing change is
  authorized.
- The branch cannot execute. `raw_explicit_roles` is rebuilt one-to-one from
  `ordered_specs`, so `len(ordered_specs) == 1` implies a truthy one-element
  roles list even if that element is `""`; the same guard's
  `not raw_explicit_roles` operand is false. The earlier single-spec
  difference/growth path returns before this condition.
- The branch has one assignment, two `if` nodes, two returns, eight calls, two
  list literals, two boolean operations, one unary operation, two comparisons,
  and two attributes. Its SHA-256 is
  `6e212026aee222ba02c34ec9c0dc2b3c7b38f0ecd46e196c767aa92ccdd3da58`.
  The current 1590-1729 owner body has 19 top-level statements and hashes to
  `97254bbaf62e26bdec28ac9053c9824ed7f9583bd7a4046f4312874d324d5bab`;
  exact deletion projects lines 1590-1720, 18 statements, and
  `dfbc243dd7560578cdab5c18fa33ca0b457c9afc3653a2200d7321b2f2ae4164`.
- The public helper's current/projected call-record hashes are
  `fcf6044263e7d57e2b76101476a55f977eed4ff198f19784a8406e4f103a451e` /
  `76cd32e8d95fd910137283b602d7ef4fc0115f9c5637b6005d67b4bd900769dd`;
  caller-map hashes are
  `3d89da74e4978fbe92a335abe1a6909e236b05c51932affdb8b8bec361658035` /
  `fc94b25b2c63bb160d0732fb17686ba866abbf7183b8f69758dc32e65791d0a5`.
  Calls/callers project 4/4 to 3/3. Public identity 2/2, operation-policy 4/3,
  audit 217, and the 48-module/205-edge DAG remain unchanged.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  254/254, surface owner 1/1, operand owner 69/69, affected semantic
  1,214/1,214, reflection promotion 15/15, reflection capability 24/24,
  retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217,
  full 2,107/2,107, one-file production/two-file complete transform, branch/
  owner/caller hash parity, graph-test AST 250/250 plus four methods, UTF-8/non-
  ASCII 2/2, pycompile, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static branch/cardinality/call/DAG/audit inspection passed. Benchmark refresh
and remote CI were **NOT RUN**. No source deletion has occurred; this checkpoint
is not a behavior, quality, ranking, performance, benchmark, schedule, or
completion claim.

### Unreachable single-metric concept branch deletion milestone

- Commit `ca2969b` removes exactly the former nine-line branch at graph-helper
  lines 1623-1631 without replacement. Its one-spec condition could not coexist
  with an empty `raw_explicit_roles` list immediately after one-to-one role
  recomputation, so neither its classifier call nor body could execute.
- Spec ordering, raw-role recomputation, the earlier difference/growth return,
  downstream role hints, operand construction/dedupe, inputs, and exception
  boundaries are unchanged. The owner now spans lines 1590-1720 with 18 top-
  level statements and body SHA-256
  `dfbc243dd7560578cdab5c18fa33ca0b457c9afc3653a2200d7321b2f2ae4164`.
- The public helper's source calls/callers finish 3/3. Final call-record and
  caller-map hashes are
  `76cd32e8d95fd910137283b602d7ef4fc0115f9c5637b6005d67b4bd900769dd` /
  `fc94b25b2c63bb160d0732fb17686ba866abbf7183b8f69758dc32e65791d0a5`.
  Public identity 2/2, operation-policy counts 4/3, audit 217, and the 48-module/
  205-edge DAG remain unchanged.
- Production source is `+0/-9`, tests are `+786/-32`, and the whole commit is
  `+786/-41`, net `+745`. Four methods move discovery from 2,103 to 2,107. The
  committed source/test diff SHA-256 is
  `0d342c2106e55f4079ee658ddce7a940376ba168bb5532e0e69d1118b96dfcef`.
- Focused pre/post deletion 4/4, graph owner 254/254, surface owner 1/1,
  operand owner 69/69, affected semantic 1,214/1,214, reflection promotion
  15/15, reflection capability 24/24, retrieval-pipeline 1/1, reconciliation
  plan 51/51, import 19/19, audit 217, and full 2,107/2,107 passed. Pycompile,
  exact nine-line deletion, owner/caller hash parity, graph-test AST 250/250
  plus four methods, unchanged public identity/owner count/DAG, UTF-8/non-ASCII
  2/2, and diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This exact dead-code
  deletion is not a quality, ranking, performance, benchmark, schedule,
  ledger, or Phase 3 completion claim.

### Percent-point-difference-query private-API characterization checkpoint

- A docs-only inventory selects the exact current 12-line
  `financial_operation_policies._is_percent_point_difference_query(text: str) -> bool`
  definition for an in-place public rename to
  `is_percent_point_difference_query(...)`. No wrapper/private alias or source/
  test rename is authorized before four CURRENT-SOURCE contracts pass.
- The nine-statement body has six assignments, two `if` nodes, three returns,
  17 calls, six generators/comprehension clauses, three tuples, three boolean
  operations, three comparisons, three attributes, and one unary operation.
  Its SHA-256 is
  `79a0ca39b2d69eae56a6d77402320460106edef15b1edf776f62ce36bb94457e`.
  Preserve input identity/normalization, shallow policy snapshot, exact marker
  access, eager tuple construction with retained-item double conversion, lazy
  membership, direct-marker precedence, ratio-marker gating, exact returns,
  immutability, and every owner-uncaught failure.
- Eight one-positional-argument/no-keyword calls span seven caller definitions,
  five external importers, and one owner-local call. Seven remain at caller
  `try` depth zero; calculation operand finalization remains at depth one.
  Evidence component admission/direct-row selection, operation-family
  precedence, reflection objective selection, operand component suppression,
  calculation percent-unit filtering, and owner-local coercion keep their exact
  gates, arguments, adoption, and stops.
- Fourteen production occurrences span six files. Fifteen existing test refs
  span three test files, so the complete transform is nine files. Operation-
  policy counts project 4/3 to 5/2; public identity projects 6/6. The selected
  span intersects no audit record and the DAG remains 48 modules/205 edges.
  Current/projected call-record hashes are
  `6d616b0dafa05079353357f3a054a4c1becf84a53af35b3a7691589b58a667ab` /
  `0269efe3c2a5fc64b44f70b1c2c02206f577ea68c1f3b088d663e6acdfbac444`;
  caller-map hashes are
  `bd50213612267e31535a9c35410ccc547d051fdcdabe959386dcb1b66b2c4dad` /
  `2f34fd00af1b37503820f103872b91de63d69cc644e53bbe00bf679362e0cf21`.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  258/258, surface owner 1/1, operand owner 69/69, affected semantic
  1,218/1,218, reflection promotion 15/15, reflection capability 24/24,
  retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217,
  full 2,111/2,111, production transform 6/6, complete transform 9/9,
  selected-body/seven-caller parity, eight-call/six-module/public-identity/DAG
  parity, graph-test AST 254/254 plus four methods, UTF-8 9/9, non-ASCII 8/8,
  pycompile, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/import/count/DAG/audit inspection passed.
Benchmark refresh and remote CI were **NOT RUN**. This checkpoint is not a
behavior, quality, ranking, performance, benchmark, schedule, or completion
claim.

### Percent-point-difference-query public API milestone

- Commit `1d8eb67` renames the exact former 12-line classifier in place to
  public `financial_operation_policies.is_percent_point_difference_query(...)`.
  No wrapper or private alias remains. Five importers, seven external calls,
  one owner-local call, and all 15 existing test bindings use the public name.
- Raw-input normalization, shallow policy snapshotting, eager ordered marker
  construction, direct-marker precedence, ratio/comparison gating, lazy
  membership, exact booleans, immutability, caller adoption, and exception
  scopes remain unchanged. Final call-record/caller-map hashes are
  `0269efe3c2a5fc64b44f70b1c2c02206f577ea68c1f3b088d663e6acdfbac444` /
  `2f34fd00af1b37503820f103872b91de63d69cc644e53bbe00bf679362e0cf21`.
- Production source is `+14/-14`, tests are `+1,976/-51`, and the whole commit
  is `+1,990/-65`, net `+1,925`; production physical lines are unchanged. Four
  methods move discovery from 2,107 to 2,111. Final operation-policy public/
  private counts are 5/2. The committed source/test diff SHA-256 is
  `8f6939314dafb61d7aa613afd858c203ed9f0ac454629fd453c2f187f234ed89`.
- Focused pre/post rename 4/4, graph owner 258/258, surface owner 1/1, operand
  owner 69/69, affected semantic 1,218/1,218, reflection promotion 15/15,
  reflection capability 24/24, retrieval-pipeline 1/1, reconciliation plan
  51/51, import 19/19, audit 217, and full 2,111/2,111 passed. Pycompile,
  production transform 6/6, complete transform 9/9, selected-body/seven-caller
  parity, all eight calls/six source modules, public identity 6/6, unchanged
  48-module/205-edge DAG, retired production refs/public stores zero, graph-
  test AST 254/254 plus four methods, UTF-8 9/9, non-ASCII 8/8, and diff check
  passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Percent-point-unit-coercion private-API characterization checkpoint

- A docs-only inventory selects the exact current 21-line
  `financial_operation_policies._should_coerce_percent_point_unit(query,
  operands, plan_data) -> bool` definition for an in-place public rename to
  `should_coerce_percent_point_unit(...)`. No wrapper/private alias or source/
  test rename is authorized before four CURRENT-SOURCE contracts pass.
- Preserve percent-point and mode early gates; eager ordered-ID construction
  with filter-only trimming; duplicate-last operand mapping; ordered selected-
  row and missing-row checks; lazy uppercase `PERCENT` validation; operation/
  formula normalization; exact subtract-or-hyphen result; immutability; and
  every owner-uncaught failure. The 11-statement body has five assignments,
  five `if` nodes, six returns, 23 calls, two list comprehensions, one dictionary
  comprehension, two generators, five comprehension clauses, ten boolean
  operations, and six comparisons. Its SHA-256 is
  `0a76da43e12274f6765449ab02d661d7fd5cabab298cf6e8a584a77c54d93aa1`.
- Two three-positional-argument/no-keyword calls span two external importers and
  callers. The deterministic runtime-plan adapter retains its difference/
  truthy-plan gates, fallback query, raw operand/plan arguments, fresh true
  copy, false plan identity, and propagated failures. The depth-one graph
  formula-plan caller retains its post-normalization/pre-guard location, true-
  only result-unit mutation, false continuation, and broad fallback on failure.
- Five production occurrences span three files. Eighteen existing test refs
  span three test files, so the complete transform is six files. Operation-
  policy counts project 5/2 to 6/1; public identity projects 3/3. The selected
  span intersects no audit record and the DAG remains 48 modules/205 edges.
  Current/projected call-record hashes are
  `ff3cdf0499f96f1e3cc8022b6ed27ce65590a5bf0f0672d986b46bb7965ed06b` /
  `59d36159e78009dbca607854cf4062b920132c1c1944d62f3adefd29861575b5`;
  caller-map hashes are
  `c7bb14e756091352fbb8fcb55be5e3dea34244652a32ac7edcd0903d3eae1c26` /
  `a15eb6644ac2c75175109618f2a9fc926cc39354c0b72b94bbc475edab7dd11d`.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  262/262, calculation-execution owner 45/45, math parsing 24/24, surface owner
  1/1, operand owner 69/69, affected semantic 1,222/1,222, reflection promotion
  15/15, reflection capability 24/24, retrieval-pipeline 1/1, reconciliation
  plan 51/51, import 19/19, audit 217, full 2,115/2,115, production transform
  3/3, complete transform 6/6, selected-body/two-caller parity, both calls/three
  source modules, public identity 3/3, unchanged DAG, graph-test AST 258/258
  plus four methods, UTF-8 6/6, non-ASCII 5/5, pycompile, and diff check are
  governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/import/count/DAG/audit inspection and four
existing owner/caller probes passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Percent-point-unit-coercion public API milestone

- Commit `a893cb3` renames the exact former 21-line policy in place to public
  `financial_operation_policies.should_coerce_percent_point_unit(...)`. No
  wrapper or private alias remains. Two external importers, two calls, and all
  18 existing test bindings use the public spelling.
- Percent-point and mode early gates, ordered-ID materialization, duplicate-last
  operand mapping, selected-row/missing checks, exact uppercase `PERCENT` unit
  validation, operation/formula normalization, subtract-or-hyphen result,
  immutability, caller adoption, and exception scopes remain unchanged. Final
  call-record/caller-map hashes are
  `59d36159e78009dbca607854cf4062b920132c1c1944d62f3adefd29861575b5` /
  `a15eb6644ac2c75175109618f2a9fc926cc39354c0b72b94bbc475edab7dd11d`.
- Production source is `+5/-5`, tests are `+1,589/-48`, and the whole commit is
  `+1,594/-53`, net `+1,541`; production physical lines are unchanged. Four
  methods move discovery from 2,111 to 2,115. Final operation-policy public/
  private counts are 6/1. The committed diff SHA-256 is
  `bae62fda6041a01df827633e1f6c1b38ba8c171fa76338d18dde8761250b217a`.
- Focused pre/post 4/4, graph owner 262/262, calculation-execution owner 45/45,
  math parsing 24/24, surface owner 1/1, operand owner 69/69, affected semantic
  1,222/1,222, reflection promotion 15/15, reflection capability 24/24,
  retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217,
  and full 2,115/2,115 passed. Production/complete transform 3/3 and 6/6,
  selected-body/two-caller parity, both calls/three source modules, public
  identity 3/3, unchanged 48-module/205-edge DAG, retired refs/public stores
  zero, graph-test AST 258/258 plus four methods, UTF-8 6/6, non-ASCII 5/5,
  pycompile, and diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Direct-numeric-grounding private-API characterization checkpoint

- A docs-only inventory selects the exact current 40-line
  `financial_operation_policies._requires_direct_numeric_grounding(
  active_subtask: Dict[str, Any]) -> bool` definition at lines 67-106 for an
  in-place public rename to `requires_direct_numeric_grounding(...)`. No
  wrapper/private alias or source/test rename is authorized before four
  CURRENT-SOURCE contracts pass.
- Preserve truth-gated eager shallow task copying, operation-family
  normalization and precedence, required-row filter-before-copy ordering,
  ratio/sum concept-count equality without dedupe, difference/growth concept/
  role-set behavior, ordered fallback labels, exact classifier-result adoption,
  immutability, and every owner-uncaught failure. The 12-statement body has
  seven assignments, five `if` nodes, six returns, 40 calls, three list
  comprehensions, two set comprehensions, and no loop or `try`. Its SHA-256 is
  `85e93a47025c2c94951961b69e232f1cd8bca4f72a20db298773639f51659746`.
- Three one-positional-argument/no-keyword calls span reconciliation routing,
  evidence extraction, and calculation-operand extraction, all at `try` depth
  zero. Their exact gates, task arguments, false/true result adoption, lazy
  classifier behavior, and propagated failure stops remain caller-owned.
- Seven production occurrences span four files. Nineteen existing test refs
  span four test files, so the complete transform is eight files. Operation-
  policy counts project 6/1 to 7/0; public identity projects 4/4; the DAG stays
  48 modules/205 edges; audit remains 217. Current/projected call-record hashes
  are
  `aa187e357d32f0f88d5df7cfe266c6d08e1eb65209d19763cc6ae702c2ae266a` /
  `d90668f2a62c7ce5d6aff1ee35b4a57c215427ebb0aae86730eeda3252deecdc`;
  caller-map hashes are
  `1aae37e05f6a5c218dd0c5604a691ac7e56207387cc3cf9774aa4fbd891481ef` /
  `66a895f03194fd07f0f54a32075d5229c9f3ebbb5f7d7be4279073a3c1b70bac`.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  266/266, operation contracts 242/242, retrieval hints 5/5, task artifacts
  15/15, surface owner 1/1, operand owner 69/69, affected semantic 1,226/1,226,
  reflection promotion 15/15, reflection capability 24/24, retrieval-pipeline
  1/1, reconciliation plan 51/51, import 19/19, audit 217, full 2,119/2,119,
  production transform 4/4, complete transform 8/8, selected-body/three-caller
  parity, all three calls/four source modules, public identity 4/4, unchanged
  DAG, graph-test AST 262/262 plus four methods, UTF-8 8/8, non-ASCII 4/4,
  pycompile, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/call/import/count/DAG/audit inspection and four
existing owner/caller probes passed. Benchmark refresh and remote CI were
**NOT RUN**. This checkpoint is not a behavior, quality, ranking, performance,
benchmark, schedule, or completion claim.

### Direct-numeric-grounding public-API milestone

- Commit `7de65fc` renames the exact former 40-line operation policy in place to
  public `requires_direct_numeric_grounding(...)`. No wrapper or private alias
  remains. Three external importers, three calls, and all 19 existing test
  bindings use the public spelling.
- Task truth and eager shallow copying, operation-family normalization and
  precedence, required-row filter-before-copy ordering, ratio/sum equality,
  difference/growth concept/role behavior, ordered fallback labels, exact
  classifier adoption, immutability, and caller gates/exceptions remain
  unchanged. Final call-record/caller-map hashes are
  `d90668f2a62c7ce5d6aff1ee35b4a57c215427ebb0aae86730eeda3252deecdc` /
  `66a895f03194fd07f0f54a32075d5229c9f3ebbb5f7d7be4279073a3c1b70bac`.
- Production source is `+7/-7`, tests are `+1,669/-61`, and the whole commit is
  `+1,676/-68`, net `+1,608`; production physical lines are unchanged. Four
  methods move discovery from 2,115 to 2,119. Final operation-policy public/
  private counts are 7/0. The committed diff SHA-256 is
  `a3409380b1d0d56104ab8caebfc94767089ff74098194575a1fde65aa77bc7b0`.
- Focused pre/post 4/4, graph owner 266/266, operation contracts 242/242,
  retrieval hints 5/5, task artifacts 15/15, calculation execution 45/45, math
  parsing 24/24, surface owner 1/1, operand owner 69/69, affected semantic
  1,226/1,226, reflection promotion 15/15, reflection capability 24/24,
  retrieval pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217,
  and full 2,119/2,119 passed. Production/complete transform 4/4 and 8/8,
  selected-body/three-caller parity, all three calls/four source modules, public
  identity 4/4, unchanged 48-module/205-edge DAG, retired refs/stores zero,
  graph-test AST 262/262 plus four methods, UTF-8 8/8, non-ASCII 4/4, pycompile,
  and diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Desired-consolidation-scope private-API characterization checkpoint

- A docs-only inventory selects the exact current 15-line
  `financial_scope_policies._desired_consolidation_scope(
  query: str, report_scope: Dict[str, Any]) -> str` definition at lines 17-31
  for an in-place public rename to `desired_consolidation_scope(...)`.
  Calculation extraction already binds that name locally; the projection also
  renames its one store and eight loads to `requested_consolidation_scope` while
  retaining two `desired_consolidation_scope=` keyword names. No wrapper/private
  alias or source/test rename is authorized before four CURRENT-SOURCE contracts
  pass.
- Preserve raw-query normalization, eager shallow query/metadata policy-map
  copies, query-marker insertion order and lazy first-hit precedence, exact
  report-scope normalization, eager per-scope metadata sets, eager default-
  marker tuple construction followed by lazy membership, exact scope strings,
  immutability, and every owner-uncaught failure. The nine-statement body has
  five assignments, two loops, three total `if` nodes, four returns, 22 calls,
  three generator expressions, one set comprehension, and no `try`. Its source-
  body SHA-256 is
  `999ed0c40d5a422f03afa71c66e341e12a1a54df31cabfa640a8549592acad57`.
- Twelve two-positional-argument/no-keyword calls span eleven task, evidence,
  calculation, rendering, and retrieval caller definitions, all at `try` depth
  zero. Exact caller gates, prepared arguments, constraint/score/filter/label
  adoption, dual sibling-recovery resolutions, and propagated stops remain
  caller-owned. The calculation-extraction public call and collision-free local
  result must stay distinct without changing the eight later uses or two callee
  keyword names.
- Eighteen production occurrences span six files. Twenty-six existing test
  occurrences span four test files, so the complete transform is ten files.
  The current caller collision is nine AST `Name` nodes (one store/eight loads);
  the projection renames only those nodes, retains two keyword labels, and must
  compile without an unbound-local path. Scope-policy counts project 11/9 to
  12/8; public identity projects 6/6; the DAG stays 48 modules/205 edges; audit
  remains 217. Current/projected call-
  record hashes are
  `cd8514984ff6aa3bcf0d8e4adf2b544732a118dd2d561be16bcb6f7613a6e83b` /
  `e0e1670ce1714cc446ad4091bafc8efb38ee1a14cf6f03b4ebeadec36be25291`;
  caller-map hashes are
  `9d4d51b55b4e49a4d6dd759a97246a83fa8af6046b44fa095d1eb6358b8fddb0` /
  `143804328cb07fcfc3d6d6099e59427dafd24296ff0e1f7bb49ba74a1b273ec9`.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  270/270, operation contracts 242/242, retrieval hints 5/5, task artifacts
  15/15, text surface 30/30, calculation execution 45/45, math parsing 24/24,
  surface owner 1/1, operand owner 69/69, affected semantic 1,230/1,230,
  reflection promotion 15/15, reflection capability 24/24, retrieval pipeline
  1/1, reconciliation plan 51/51, import 19/19, audit 217, full 2,123/2,123,
  production transform 6/6, complete transform 10/10, selected-body/eleven-
  caller parity, all twelve calls/six source modules, public identity 6/6,
  unchanged DAG, graph-test AST 266/266 plus four methods, collision-local
  transform 9/9, retained keyword names 2/2, UTF-8 10/10, non-ASCII 8/8,
  projected compile/import, pycompile, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/body/call/import/count/DAG/audit inspection and five
existing owner/caller probes passed after correcting one test-selector typo.
Benchmark refresh and remote CI were **NOT RUN**. This checkpoint is not a
behavior, quality, ranking, performance, benchmark, schedule, or completion
claim.

### Desired-consolidation-scope public-API milestone

- Commit `d6e7765` renames the exact former 15-line scope policy in place to
  public `desired_consolidation_scope(...)`. No wrapper or private alias remains.
  Five external importers, twelve calls, and all 26 existing test bindings use
  the public spelling.
- Query/metadata/default precedence, eager shallow policy copies, eager/lazy
  evaluation, exact scope results, immutability, and caller gates/exceptions
  remain unchanged. Calculation extraction's one colliding local store and
  eight loads alone use `requested_consolidation_scope`; both existing keyword
  labels remain unchanged. Final call-record/caller-map hashes are
  `e0e1670ce1714cc446ad4091bafc8efb38ee1a14cf6f03b4ebeadec36be25291` /
  `143804328cb07fcfc3d6d6099e59427dafd24296ff0e1f7bb49ba74a1b273ec9`.
- Production source is `+26/-26`, tests are `+1,801/-64`, and the whole commit
  is `+1,827/-90`, net `+1,737`; production physical lines are unchanged. Four
  methods move discovery from 2,119 to 2,123. Final scope-policy public/private
  counts are 12/8. The committed diff SHA-256 is
  `383134898960245449744387c078a61a6c02ba538cecb4252c60b8f0bcdc898e`.
- Focused pre/post 4/4, graph owner 270/270, operation contracts 242/242,
  retrieval hints 5/5, task artifacts 15/15, text surface 30/30, calculation
  execution 45/45, math parsing 24/24, surface owner 1/1, operand owner 69/69,
  affected semantic 1,230/1,230, reflection promotion 15/15, reflection
  capability 24/24, retrieval pipeline 1/1, reconciliation plan 51/51, import
  19/19, audit 217, and full 2,123/2,123 passed. Production/complete transform
  6/6 and 10/10, selected-body/eleven-caller parity, all twelve calls/six source
  modules, public identity 6/6, unchanged 48-module/205-edge DAG, retired refs/
  public stores zero, graph-test AST 266/266 plus four methods, collision-local
  transform 9/9, retained keyword names 2/2, UTF-8 10/10, non-ASCII 8/8,
  pycompile, and diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Metadata-period-match-strength private-API characterization checkpoint

- A docs-only inventory selects the exact current 11-line
  `financial_scope_policies._metadata_period_match_strength(
  period_labels: List[str], query_years: List[int]) -> float` definition at
  lines 478-488 for an in-place public rename to
  `metadata_period_match_strength(...)`. No wrapper/private alias or source/test
  rename is authorized before four CURRENT-SOURCE contracts pass.
- Preserve the left-to-right truth short circuit, exact `0.0`, repeated
  `str(label).strip()` filter/projection evaluation, label/year set dedupe and
  intersection, zero/full/partial overlap results, immutability, and every
  owner-uncaught failure. The seven-statement body has three assignments, three
  `if` nodes, four returns, nine calls, two set comprehensions, two comprehension
  clauses, one boolean operation, two comparisons, two binary operations, and
  no loop or `try`. Its source-body SHA-256 is
  `93e219fea17942e8b495fe554af12a4a8d40f3cc34bb0c3273df4e6977f86b29`.
- Three two-positional-argument/no-keyword calls span evidence's nested candidate
  score, operand-candidate scoring, and retrieval reranking at `try` depth zero.
  Their exact metadata-list/period-label and query-year arguments, `* 1.5` or
  positive-gated `0.10 *` adoption, order, and propagated stops remain caller-
  owned.
- Seven production occurrences span four files. Nineteen existing test
  occurrences span two test files, so the complete transform is six files.
  Scope-policy counts project 12/8 to 13/7; public identity projects 4/4; the
  DAG stays 48 modules/205 edges; audit remains 217. Current/projected call-
  record hashes are
  `e19265b9aa7ae72eaa65ca0e644e30c2dace02a26a884a3d6b3b392e5fa47742` /
  `62d3900668cbfdab705d00ce2afba44ed475740ceed66d8dd9f08bdfb0a30d03`;
  caller-map hashes are
  `a8c1b2661c80bc48cf29cdf6eddbdbb46d93a9fabee12476e267855a3be2616b` /
  `b039d1ffb850ce20cf5b001ed8b272f8f49b7057f7a98fc93330e789af09bb7f`.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  274/274, operation contracts 242/242, retrieval hints 5/5, task artifacts
  15/15, text surface 30/30, calculation execution 45/45, math parsing 24/24,
  surface owner 1/1, operand owner 69/69, affected semantic 1,234/1,234,
  reflection promotion 15/15, reflection capability 24/24, retrieval pipeline
  1/1, reconciliation plan 51/51, import 19/19, audit 217, full 2,127/2,127,
  production transform 4/4, complete transform 6/6, selected-body/three-caller
  parity, all three calls/four source modules, public identity 4/4, unchanged
  DAG, graph-test AST 270/270 plus four methods, UTF-8 6/6, non-ASCII 6/6,
  projected compile/import, pycompile, and diff check are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/body/call/import/count/DAG/audit inspection,
projected AST compilation, and five existing owner/caller probes passed.
Benchmark refresh and remote CI were **NOT RUN**. This checkpoint is not a
behavior, quality, ranking, performance, benchmark, schedule, or completion
claim.

### Metadata-period-match-strength public-API milestone

- Commit `5509d78` renames the exact former 11-line scope policy in place to
  public `metadata_period_match_strength(...)`. No wrapper or private alias
  remains. Three external importers, three calls, and all 19 existing test
  bindings use the public spelling.
- Input truth-gate order, repeated label rendering/stripping, label/year set
  dedupe and intersection, exact zero/full/partial overlap results,
  immutability, all three caller score-adoption paths, and exception scopes
  remain unchanged. Final call-record/caller-map hashes are
  `62d3900668cbfdab705d00ce2afba44ed475740ceed66d8dd9f08bdfb0a30d03` /
  `b039d1ffb850ce20cf5b001ed8b272f8f49b7057f7a98fc93330e789af09bb7f`.
- Production source is `+7/-7`, tests are `+1,148/-57`, and the whole commit is
  `+1,155/-64`, net `+1,091`; production physical lines are unchanged. Four
  methods move discovery from 2,123 to 2,127. Final scope-policy public/private
  counts are 13/7. The committed diff SHA-256 is
  `db3d34f22af44759d21e6ead24680aad7c3b7c290cd1ea3d4f3c009bd7afc19b`.
- Focused pre/post 4/4, graph owner 274/274, operation contracts 242/242,
  retrieval hints 5/5, task artifacts 15/15, text surface 30/30, calculation
  execution 45/45, math parsing 24/24, surface owner 1/1, operand owner 69/69,
  affected semantic 1,234/1,234, reflection promotion 15/15, reflection
  capability 24/24, retrieval pipeline 1/1, reconciliation plan 51/51, import
  19/19, audit 217, and full 2,127/2,127 passed. Production/complete transform
  4/4 and 6/6, selected-body/three-caller parity, all three calls/four source
  modules, public identity 4/4, unchanged 48-module/205-edge DAG, retired refs/
  public stores zero, graph-test AST 270/270 plus four methods, UTF-8 6/6,
  non-ASCII 6/6, pycompile, and diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Extract-period-sort-key private-API and unused-import characterization checkpoint

- A docs-only inventory selects the exact current 10-line
  `financial_scope_policies._extract_period_sort_key(period: str) -> int`
  definition at lines 491-500 for an in-place public rename to
  `extract_period_sort_key(...)`. No wrapper/private alias, source rename, or
  import deletion is authorized before four CURRENT-SOURCE contracts pass.
- Preserve `_normalise_spaces(period)`, the first `(19|20)\d{2}` match, and the
  exact matched-year / `당기` 9999 / `전기` 9998 / `-1` precedence. The body has
  two assignments, three `if` nodes, four returns, four calls, two comparisons,
  and no loop, comprehension, boolean operation, binary operation, or `try`.
  Its source-body SHA-256 is
  `ddbbc2f697d6ea65e04e844634aa8e1754e49eded12ebc9948b68208cd84fa48`.
- The sole real call is the nested `str(row.get("period") or "")` sorted-key
  lambda inside `execute_prepared_calculation_plan(...)`. Its time-series and
  operand-count gates, materialization, stable ascending sort, evidence/growth
  adoption, and outer caught-exception boundary remain caller-owned.
- Four private production occurrences span three files: one definition, two
  imports, and one call. The graph-calculation import has no load or call and is
  deleted instead of renamed. No existing test references exist. Scope-policy
  counts project 13/7 to 14/6; public identity projects 2/2; the DAG stays 48
  modules/205 edges; audit remains 217. Current/projected call-record hashes are
  `1529c14d859066e87f3e89a6f48f785267ec450b09b32a00cc61926af3af563f` /
  `257a8c47456cbf8326c10afcbf693f4aa73de321be9736a84c11b3ba6c334057`;
  caller-map hashes are
  `687f6338e91898015ebf31bdc5f64a1f74af6de7d23a6cafed2f09cc4f614298` /
  `d774b540cf895765fab754c99b74d64730d61e8d0e2b63cc5e1dfe67fa67c7d2`.
- Four named CURRENT-SOURCE methods and projected focused 4/4, graph owner
  278/278, operation contracts 242/242, retrieval hints 5/5, task artifacts
  15/15, text surface 30/30, calculation execution 45/45, math parsing 24/24,
  surface owner 1/1, operand owner 69/69, affected semantic 1,238/1,238,
  reflection promotion 15/15, reflection capability 24/24, retrieval pipeline
  1/1, reconciliation plan 51/51, import 19/19, audit 217, full 2,131/2,131,
  selected-body/sole-caller parity, unused-import deletion, public identity 2/2,
  unchanged DAG, graph-test AST 274/274 plus four methods, encoding, compile,
  pycompile, and diff-check gates are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/body/call/import/count/DAG/audit inspection,
projected AST compilation, and the existing time-series ordering caller probe
passed. Benchmark refresh and remote CI were **NOT RUN**. This checkpoint is not
a behavior, quality, ranking, performance, benchmark, schedule, or completion
claim.

### Extract-period-sort-key public-API and unused-import deletion milestone

- Commit `d9dddc4` renames the exact former 10-line scope policy in place to
  public `extract_period_sort_key(...)`. No wrapper or private alias remains.
  The sole real calculation-execution import/call uses the public spelling, and
  the graph-calculation private import with zero loads and zero calls is deleted.
- Whitespace normalization, the first year match, exact matched-year / `당기`
  9999 / `전기` 9998 / `-1` precedence, immutability, caller time-series and
  operand-count gates, stable sort, evidence/growth adoption, and the outer
  caught-exception boundary remain unchanged. Final call-record/caller-map/
  caller-body hashes are
  `257a8c47456cbf8326c10afcbf693f4aa73de321be9736a84c11b3ba6c334057` /
  `d774b540cf895765fab754c99b74d64730d61e8d0e2b63cc5e1dfe67fa67c7d2` /
  `c065ec0fca3b6ba92bc23909c5fd5a3f1cc059dc3c67b48046ef7eeaf665698f`.
- Production source is `+3/-4`, tests are `+1,016/-42`, and the whole commit is
  `+1,019/-46`, net `+973`; production physical lines decrease by one. Four
  methods move discovery from 2,127 to 2,131. Final scope-policy public/private
  counts are 14/6. The committed diff SHA-256 is
  `3e1636144a5ac9308116dee53d920dbed588a6dc7858af366a8ecf7eda4d4e44`.
- Focused pre/post 4/4, retrieval scope 28/28, graph owner 278/278, operation
  contracts 242/242, retrieval hints 5/5, task artifacts 15/15, text surface
  30/30, calculation execution 45/45, math parsing 24/24, surface owner 1/1,
  operand owner 69/69, affected semantic 1,238/1,238, reflection promotion
  15/15, reflection capability 24/24, retrieval pipeline 1/1, reconciliation
  plan 51/51, import 19/19, audit 217, and full 2,131/2,131 passed. Production/
  complete transform 4/4, selected-body/sole-caller parity, public identity 2/2,
  unchanged 48-module/205-edge DAG, retired refs/public stores zero, graph-test
  AST 274/274 plus four methods, UTF-8 4/4, non-ASCII 4/4, pycompile, and diff
  check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility/cleanup
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Strict-company-scope private-API characterization checkpoint

- A docs-only inventory selects the exact current 10-line
  `financial_scope_policies._should_apply_strict_company_scope(
  companies: List[str], report_scope: Dict[str, Any]) -> bool` definition at
  lines 530-539 for an in-place public rename to
  `should_apply_strict_company_scope(...)`. No wrapper/private alias or source/
  test rename is authorized before four CURRENT-SOURCE contracts pass.
- Preserve the companies-first false return, shallow `dict(report_scope or {})`
  copy, explicit stripped `rcept_no` false return, projected source-receipt false
  return, exact final `True`, nested identity, non-mutation, and every owner-
  uncaught failure. The six-statement body has two assignments, three `if`
  nodes, four returns, five calls, one dictionary literal, two boolean
  operations, one unary operation, and no loop, comprehension, comparison,
  binary operation, or `try`. Its source-body SHA-256 is
  `be55d41bf5c284e7240b79ffe1a72f1c6d8741ca23b82b9781296cfa82742117`.
- The sole two-positional-argument/no-keyword call is retrieval `_retrieve(...)`
  at `try` depth zero. Its prepared list/dict arguments, scope-company prepend,
  later company-filter adoption, ordering, and propagated exception stop remain
  caller-owned.
- Three private production occurrences span two files. Four existing test
  occurrences span `tests/test_retrieval_scope.py`; the complete transform adds
  the graph contract test file for four total paths. Scope-policy counts project
  14/6 to 15/5; public identity projects 2/2; the DAG stays 48 modules/205
  edges; audit remains 217. Current/projected call-record hashes are
  `1cd3c7c07259c467518386946b7862d1e266ce16e608fb4e5497fa9f61695b21` /
  `c82616a53264c2b42a488f483c6b833991821a6d2f4ffdb6d1269b4c49fd090b`;
  caller-map hashes are
  `e493e701554347a4058bce545bd4b428dee453fed3ca9ca78717446f4def0f34` /
  `64ff812d9a106fbbd70a092a89f5eb9e8391de756b7f824c6e738fe37c3286e0`.
- Four named CURRENT-SOURCE methods and projected focused 4/4, retrieval scope
  28/28, graph owner 282/282, operation contracts 242/242, retrieval hints 5/5,
  task artifacts 15/15, text surface 30/30, calculation execution 45/45, math
  parsing 24/24, surface owner 1/1, operand owner 69/69, affected semantic
  1,242/1,242, reflection promotion 15/15, reflection capability 24/24,
  retrieval pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217,
  full 2,135/2,135, selected-body/sole-caller parity, public identity 2/2,
  unchanged DAG, graph-test AST 278/278 plus four methods, existing-test and
  encoding/compile/pycompile/diff-check gates are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/body/call/import/count/DAG/audit inspection,
projected AST compilation 4/4, three direct owner probes, and retrieval-scope
28/28 passed. Benchmark refresh and remote CI were **NOT RUN**. This checkpoint
is not a behavior, quality, ranking, performance, benchmark, schedule, or
completion claim.

### Strict-company-scope public-API milestone

- Commit `579141d` renames the exact former 10-line scope policy in place to
  public `should_apply_strict_company_scope(...)`. No wrapper or private alias
  remains. The sole retrieval import/call and four existing bindings in
  `tests/test_retrieval_scope.py` use the public spelling.
- Companies-first short circuit, shallow report-scope copy, explicit/source-
  receipt precedence, exact booleans, nested identity, non-mutation, retrieval
  scope-company prepend/filter adoption, and the propagated exception boundary
  remain unchanged. Final call-record/caller-map/caller-body hashes are
  `c82616a53264c2b42a488f483c6b833991821a6d2f4ffdb6d1269b4c49fd090b` /
  `64ff812d9a106fbbd70a092a89f5eb9e8391de756b7f824c6e738fe37c3286e0` /
  `42f3e9a7359e4c72ddfaeedfdd4441b342ba31b768150db37194d20eeef9f2b4`.
- Production source is `+3/-3`, tests are `+1,014/-42`, and the whole commit is
  `+1,017/-45`, net `+972`. Four methods move discovery from 2,131 to 2,135.
  Final scope-policy public/private counts are 15/5. The committed diff SHA-256
  is `683f170f2dd40d325b4d7ce514054b991dc3465859ac61821dc40b604f293c28`.
- Focused pre/post 4/4, retrieval scope 28/28, graph owner 282/282, operation
  contracts 242/242, retrieval hints 5/5, task artifacts 15/15, text surface
  30/30, calculation execution 45/45, math parsing 24/24, surface owner 1/1,
  operand owner 69/69, affected semantic 1,242/1,242, reflection promotion
  15/15, reflection capability 24/24, retrieval pipeline 1/1, reconciliation
  plan 51/51, import 19/19, audit 217, and full 2,135/2,135 passed. Production/
  complete transform 3/3 and 4/4, selected-body/sole-caller parity, public
  identity 2/2, unchanged 48-module/205-edge DAG, retired refs/public stores
  zero, graph-test AST 278/278 plus four methods, UTF-8 4/4, non-ASCII 4/4,
  pycompile, and diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Report-scope-source-receipts private-API characterization checkpoint

- A docs-only inventory selects the exact current 7-line
  `financial_scope_policies._report_scope_source_receipts(
  report_scope: Dict[str, Any]) -> List[str]` definition at lines 459-465 for an
  in-place public rename to `report_scope_source_receipts(...)`. No wrapper/
  private alias or source/test rename is authorized before four CURRENT-SOURCE
  contracts pass.
- Preserve the fresh result list, identity-preserving source-report helper call,
  lazy source-order iteration, exact receipt get/or/string/strip sequence, raw
  and stripped truth gates, ordered equality-based membership dedupe, first-
  seen append, nested identity, input non-mutation, and all uncaught failures.
  The body has top-level `AnnAssign`, `For`, and `Return`, one nested assignment
  and `if`, five calls, one list literal, two boolean operations, one comparison,
  and no `try` or comprehension. Its source-body SHA-256 is
  `030a5eb40db1f5c1c4a25e0d5d1954b6caa9656448f2a9d1c190d94166df8370`.
- Three one-positional/no-keyword calls stay in place: single-report scope at
  `try` depth one with length/cardinality adoption and caught ordinary errors,
  strict-company scope at depth zero with truth adoption and propagated errors,
  and retrieval at depth zero with multi-source/filter adoption.
- Five private production semantic occurrences span two files. Twenty-eight
  exact test strings are in the graph contract file, for three complete
  transform paths. Scope-policy counts project 15/5 to 16/4; public identity
  projects 2/2; the DAG stays 48 modules/205 edges; audit remains 217. Current/
  projected call-record hashes are
  `b93e7cca713b02cadcafc528492fcd6c672025415af46fcac2ce4dc8c6a6e88d` /
  `03014bbe5bfa18c8d28657847f0cce1ea67b68d9bb024ed13836336ce992e965`;
  caller-map hashes are
  `d08e16c1409894af5ab351f27ac9c4a6e2b8292da8f749d4942a05dabd4f0759` /
  `4a8265bb5bebf1accedc9f46475fc0bf0d44c0cbeb5aace1d52b474230fec0ed`.
- Four named CURRENT-SOURCE methods and projected focused 4/4, retrieval scope
  28/28, graph owner 286/286, operation contracts 242/242, retrieval hints 5/5,
  task artifacts 15/15, text surface 30/30, calculation execution 45/45, math
  parsing 24/24, surface owner 1/1, operand owner 69/69, affected semantic
  1,246/1,246, reflection promotion 15/15, reflection capability 24/24,
  retrieval pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217,
  full 2,139/2,139, selected-body/three-caller parity, public identity 2/2,
  unchanged DAG, graph-test AST 282/282 plus four methods, existing-test and
  encoding/compile/pycompile/diff-check gates are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/body/call/import/count/DAG/audit inspection,
projected AST compilation 3/3, direct probes 5/5, and existing caller probes
10/10 passed. Benchmark refresh and remote CI were **NOT RUN**. This checkpoint
is not a behavior, quality, ranking, performance, benchmark, schedule, or
completion claim.

### Report-scope-source-receipts public-API milestone

- Commit `faba39e` renames the exact former 7-line receipt projection in place
  to public `report_scope_source_receipts(...)`. No wrapper or private alias
  remains. Two owner-local calls, the retrieval import/call, 28 exact graph-test
  strings, and two longer retrieval-caller source strings use the public
  spelling.
- Fresh-list construction, identity-preserving source-report projection, lazy
  source order, receipt get/or/string/strip normalization, raw and stripped
  truth gates, equality-based first-seen dedupe, nested identity, input non-
  mutation, and all three caller exception boundaries remain unchanged. Final
  call-record/caller-map hashes are
  `03014bbe5bfa18c8d28657847f0cce1ea67b68d9bb024ed13836336ce992e965` /
  `4a8265bb5bebf1accedc9f46475fc0bf0d44c0cbeb5aace1d52b474230fec0ed`.
- Production source is `+5/-5`, tests are `+1,193/-75`, and the whole commit is
  `+1,198/-80`, net `+1,118`. Four methods move discovery from 2,135 to 2,139.
  Final scope-policy public/private counts are 16/4. The committed diff SHA-256
  is `b1adfdddca9e994b41d504702dc5fc67661d87c8387282b47327e373bac594d6`.
- Focused pre/post 4/4, retrieval scope 28/28, graph owner 286/286, operation
  contracts 242/242, retrieval hints 5/5, task artifacts 15/15, text surface
  30/30, calculation execution 45/45, math parsing 24/24, surface owner 1/1,
  operand owner 69/69, affected semantic 1,246/1,246, reflection promotion
  15/15, reflection capability 24/24, retrieval pipeline 1/1, reconciliation
  plan 51/51, import 19/19, audit 217, and full 2,139/2,139 passed. Production/
  complete transform 5/5 and 3/3, selected-body/three-caller parity, public
  identity 2/2, unchanged 48-module/205-edge DAG, retired refs/public stores
  zero, graph-test AST 282/282 plus four methods, existing exact-string 28/28
  and caller-source 2/2 transforms, UTF-8 3/3, non-ASCII 3/3, pycompile, and
  diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Extract-year-tokens private-API characterization checkpoint

- A docs-only inventory selects the exact current 25-line
  `financial_scope_policies._extract_year_tokens(
  query: str, report_scope: Dict[str, Any]) -> List[int]` definition at lines
  503-527 for an in-place public rename to `extract_year_tokens(...)`. No
  wrapper/private alias or source/test rename is authorized before four CURRENT-
  SOURCE contracts pass.
- Preserve query `20xx년` extraction order and equality dedupe, nonduplicate
  scope-year insertion at index zero, duplicate scope-year non-reordering,
  source-report direct-year/metadata fallback, source order, integer conversion,
  fresh results, original report-scope identity, lazy source iteration, and
  input non-mutation. Preserve the two narrow `TypeError`/`ValueError` handlers:
  scope conversion passes and row conversion continues; all work outside those
  exact `try` bodies remains uncaught. The six top-level statements are
  `AnnAssign`, `For`, `Assign`, `Try`, `For`, and `Return`; the source-body
  SHA-256 is
  `b6e416b8033425999db29cebe67e3760021910aa836dd78614b61340982dcce8`.
- Three two-positional/no-keyword calls at `try` depth zero stay in graph
  helpers. Generic and concept period-operand builders adopt the first year as
  current and the second or current-minus-one as prior, while empty results use
  policy hints. Dependency-query projection passes its joined task query text,
  returns a truthy result by identity, and applies its existing scope-year
  fallback only to a falsey result. All helper-call failures propagate.
- Five private production semantic occurrences span two files. One existing
  exact test string is in the graph contract file, for three complete transform
  paths. Scope-policy counts project 16/4 to 17/3; public identity projects 2/2;
  the DAG stays 48 modules/205 edges; audit remains 217. Current/projected call-
  record hashes are
  `88f78a94917a59c75e6efbd1ac240e90bb0de7a416b8e6c43c025547b03e3818` /
  `e67fc351713582c74d9c165209ff5bc8449f1439212542ef5bf2cba7e628800b`;
  caller-map hashes are
  `89f3813f0674e25f5132125a95353999caad24594767e58cc532036693df77d6` /
  `9b4ab9d450de2701ec06f798c7832f0fc9214a1bddd0af069e870a5d8bec74c2`.
- Four named CURRENT-SOURCE methods and projected focused 4/4, retrieval scope
  28/28, graph owner 290/290, operation contracts 242/242, retrieval hints 5/5,
  task artifacts 15/15, text surface 30/30, calculation execution 45/45, math
  parsing 24/24, surface owner 1/1, operand owner 69/69, affected semantic
  1,250/1,250, reflection promotion 15/15, reflection capability 24/24,
  retrieval pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217,
  full 2,143/2,143, selected-body/three-caller parity, public identity 2/2,
  unchanged DAG, graph-test AST 286/286 plus four methods, existing-test and
  encoding/compile/pycompile/diff-check gates are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

Static definition/signature/body/call/import/count/DAG/audit inspection,
projected AST compilation 2/2, direct behavior probes 5/5, and caller probes
3/3 passed. Benchmark refresh and remote CI were **NOT RUN**. This checkpoint is
not a behavior, quality, ranking, performance, benchmark, schedule, or
completion claim.

### Extract-year-tokens public-API milestone

- Commit `d2a8f8e` renames the exact former 25-line year-token projection in
  place to public `financial_scope_policies.extract_year_tokens(...)`. No
  wrapper or private alias remains. The graph-helper import, three calls, and
  one exact graph-test string use the public spelling.
- Query `20xx년` extraction order, scope-year front precedence without duplicate
  repositioning, source-report direct-year/metadata fallback, ordered equality
  dedupe, fresh results, original identities, lazy source iteration, input non-
  mutation, narrow conversion exceptions, and all three caller result-adoption
  boundaries remain unchanged. Final scope-policy public/private counts are
  17/3 and public identity is 2/2.
- Production source is `+5/-5`, tests are `+1,148/-51`, and the whole commit is
  `+1,153/-56`, net `+1,097`. The final body hash remains
  `b6e416b8033425999db29cebe67e3760021910aa836dd78614b61340982dcce8`;
  call-record/caller-map hashes are
  `e67fc351713582c74d9c165209ff5bc8449f1439212542ef5bf2cba7e628800b` /
  `9b4ab9d450de2701ec06f798c7832f0fc9214a1bddd0af069e870a5d8bec74c2`.
  The committed diff SHA-256 is
  `997cb4c8e7a9246cfc4371771d792b4a25d0c4de485f990a8523449d17151408`.
- Focused pre/post 4/4, retrieval scope 28/28, graph owner 290/290, operation
  contracts 242/242, retrieval hints 5/5, task artifacts 15/15, text surface
  30/30, calculation execution 45/45, math parsing 24/24, surface owner 1/1,
  operand owner 69/69, affected semantic 1,250/1,250, separate owner set 144/144,
  reflection/retrieval/reconciliation/import set 110/110, audit 217, and full
  2,143/2,143 passed. Selected-body/three-caller parity, public identity,
  unchanged 48-module/205-edge DAG, compile, pycompile, and diff check passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Zero-load cross-module import cleanup characterization checkpoint

- Static inventory selects exactly four imports with one binding and zero loads
  or calls in their importer: evidence `_document` and runtime-trace resolution,
  retrieval-pipeline generic-metric aliases, and graph-calculation direct-
  evidence-surface detection. Delete only those bindings; preserve every helper
  definition and other live import/call.
- Repository-wide retained definition/call counts are one/two for `_document`,
  one/four for `_build_generic_metric_aliases`, one/19 for
  `_resolve_runtime_calculation_trace`, and one/two for
  `_operand_row_has_direct_evidence_surface`. No source/test module-attribute or
  dynamic `getattr`/`hasattr` consumer relies on the selected importer names.
- The selected-import current/empty hashes are
  `9a1a727471d40de8f1f87a5d2ee1505e3bcb000472f11efcf41c55f0178db9b8` /
  `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
  Projected AST compilation is 3/3. Physical source removes four lines across
  three files without changing any helper body.
- The DAG projects from 48 modules/205 edges to 48/203, removing only
  `financial_graph_evidence -> financial_runtime_trace` and
  `financial_retrieval_pipeline -> financial_graph_helpers`. Current/projected
  edge hashes are
  `e4bdbdb848db4c34dfc971c74128114e12c8883a723dbe49b2e0aef57ba931a1` /
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
  Update exactly 19 existing DAG expectations; add no new test method.
- Required post-edit graph/import/retrieval/reconciliation/audit/semantic/full,
  compile, live-ref, dynamic-consumer, and diff gates are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work). Benchmark
  refresh and remote CI remain **NOT RUN**.

### Zero-load cross-module import cleanup milestone

- Commit `be1fbc9` deletes the four selected import bindings and no helper
  definition. Repository-wide helper call counts remain 2, 4, 19, and 2;
  selected importer loads/calls and source/test module-attribute or dynamic
  consumers finish at zero. Production source is exactly `-4`.
- The selected-import record is empty with hash
  `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
  The DAG finishes 48 modules/203 edges after removing only evidence-to-runtime-
  trace and retrieval-pipeline-to-graph-helpers; its hash is
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
- The characterize-only checkpoint counted 19 tuple-form DAG expectations but
  omitted 26 standalone full-DAG expectations. The final test transform updates
  45 current-DAG counts, one prior-edge count, two retrieval call lines, and 12
  call-record fingerprints: `+60/-60`, with no new or weakened test. The whole
  commit is `+60/-64`, net `-4`; its diff SHA-256 is
  `ac9fd2c24689e4c22ea7e16d0471dce7633d2205c8a4894530ab5201378f2ee9`.
- Focused DAG 19/19, graph 290/290, remaining semantic 960/960 for affected
  1,250/1,250, separate owner 144/144, reflection/retrieval/reconciliation/
  import 110/110, audit 217, compile/pycompile, live-ref/dynamic-consumer checks,
  and full 2,143/2,143 passed.
- Benchmark refresh and remote CI were **NOT RUN**. This dead-import-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Dead MAS-node helper cleanup characterization checkpoint

- Static inventory selects exactly three unused 2-line definitions:
  `analyst_node._trace(...)` at 21-22,
  `orchestrator_node._artifact_payload(...)` at 157-158, and
  `researcher_node._trace(...)` at 37-38. Each selected module/name pair has zero
  imports, loads, calls, attributes, `getattr`/`hasattr`, and patch-string
  consumers across `src` and `tests`.
- The live orchestrator `_trace(...)`, `_artifact_answer(...)`,
  `_artifact_refs(...)`, `project_worker_artifact_boundary(...)`, and all imports
  remain outside the deletion. No selected helper has executed behavior to move.
  Trace source/AST hashes are
  `d51ecccce408de70bf0ff9b9607967190b155314a79777014e3c9d55f018b89d` /
  `16b49f6cdfe93089fab003270a7697d53145ec755d4007f2d19c32a94ff06686`;
  artifact-helper hashes are
  `4958b08162a6c19af90f9abc0acc06f55090350a9d53fc3cb5a0190d55421034` /
  `f52c21a79e7b50898e8b8715f1a1c0ce0aaa52f42c732431e2f76d6399e45585`.
- Delete the three definitions and following blank separators only. Nine
  physical lines project module sizes 321/664/372 to 318/661/369; public counts
  stay 2/4/2 and private counts project 11/23/15 to 10/22/14. No import changes.
  Selected-definition current/empty hashes are
  `be896e2857d7766a80b2ee74ce2be96ff8fecfbd17e0ccc1f1262fb998a40f70` /
  `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
- Projected AST compilation passes 3/3. The DAG remains 48/203 at edge hash
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`;
  selected audit occurrences are zero and baseline remains 217. Targeted MAS
  projects 45/45, import 19/19, and full discovery remains 2,143/2,143. Add no
  test method or expectation change. Exact gates are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

### Dead MAS-node helper cleanup milestone

- Commit `3eadee4` deletes only Analyst and Researcher `_trace(...)` plus
  Orchestrator `_artifact_payload(...)`. The live orchestrator trace,
  `_artifact_answer(...)`, `_artifact_refs(...)`,
  `project_worker_artifact_boundary(...)`, and every import remain. Final
  selected definition/import/load/call/attribute/dynamic-consumer counts are
  zero; the canonical empty record hash is
  `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
- The actual source diff is 12 deletions rather than the projected nine because
  each 2-line helper removal also consumes two top-level separator lines. Final
  module sizes are 317/660/368 and public/private function counts are 2/10,
  4/22, and 2/14. No newly unused import remains.
- Targeted Analyst/Orchestrator/Researcher/MAS 45/45, import-side-effect 19/19,
  audit 217, three-file pycompile, unchanged 48-module/203-edge DAG, full
  2,143/2,143 in 211.556 seconds, and diff checks pass. The committed diff
  SHA-256 is
  `2ee08fa81d381d49cc7682926a89ef39b0f9ae856faf2d6411c20f3e45d64d6e`.
  Benchmark refresh and remote CI were **NOT RUN**; this is a dead-code-only
  milestone, not a runtime-quality or Phase 3 completion claim.

### Graph-model-loader public API characterization checkpoint

- The next batch renames all 13 externally imported private wrappers in
  `financial_graph_model_loaders.py` in place:
  `aggregate_synthesis_output_model`, `calculation_plan_model`,
  `calculation_render_output_model`, `calculation_verification_output_model`,
  `compression_output_model`, `concept_planner_output_model`,
  `evidence_extraction_model`, `numeric_extraction_model`,
  `operand_extraction_model`, `reconciliation_candidate_rerank_model`,
  `reflection_query_plan_model`, `validation_output_model`, and
  `validate_answer_slots_payload`. Keep `_graph_model(...)` as the only private
  owner function and add no wrapper or alias.
- Preserve lazy `import_module("src.agent.financial_graph_models")`, exact
  `getattr(module, name)`, `@lru_cache(maxsize=None)`, target identity, exception
  propagation, and the validation wrapper's one-positional-argument call. Rename
  its owner-local target binding to `validator` to avoid public-name shadowing.
  Direct current mapping/identity probes pass 13/13.
- Static scope is 13 definitions, 17 imports, and 18 loads/calls across one
  owner plus seven importers. Eighteen exact private test references span six
  files; with import-side-effect coverage, the affected seven-module suite is
  466 tests. Owner public/private counts project from 0/14 to 13/1.
- The mapping record hash is
  `85172cb3c9344296697d158fa4269e072e45d239be418510b507199697616685`.
  Current/projected binding hashes are
  `5456e27b4ff2a74dd11db97178455bc809425f4e90d5b9a62b337ad9fc0c425c` /
  `5ff10ef6c806bdd88b137253f0b76db5b0b73c4f3d05a7c6a405a431589c261a`;
  current/projected call-record hashes are
  `7a37d9829e9d09d4171d2daa1acf58d1f496dcc2168bca852dd5d4e0213f9528` /
  `713fd152a1760ca7f6c2953f5c6dca053f713b88829539b86a5f6cdfd15736eb`.
  Projected compilation passes source 8/8 and tests 6/6; the DAG remains
  48/203 at
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`,
  audit remains 217, and full discovery remains 2,143. Exact mapping and gates
  are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

### Graph-model-loader public API milestone

- Commit `4dd38ca` renames all 13 selected owner definitions, 17 imports, and 18
  calls to public names without a wrapper or alias. `_graph_model(name)` remains
  the only private owner function. Its `@lru_cache(maxsize=None)`, lazy
  `import_module(...)`, exact `getattr(...)`, returned model identity, and every
  import/attribute/callable/validation failure remain unchanged. The answer-slot
  validator retains payload identity through owner-local `validator`.
- Retired private refs finish zero and owner public/private counts finish 13/1.
  Direct mapping/identity probes pass 13/13. Production source is `+50/-50`:
  15 owner replacements plus 17 imports and 18 calls.
- The characterize-only checkpoint counted 18 direct test refs but missed nine
  caller-body and seven caller-map fingerprint replacements. The final test
  transform is therefore `+34/-34`, not `+18/-18`; the whole commit is
  `+84/-84`. No test method was added or weakened.
- Affected tests 466/466, import-side-effect 19/19, audit 217, source/test
  pycompile, unchanged 48-module/203-edge DAG at
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`,
  full 2,143/2,143 in 213.609 seconds, private-ref zero, and diff checks passed.
  The committed diff SHA-256 is
  `30e6ecf0905c80d799932ade117525ea698afa18b2697bb93d1360091c49ec37`.
  Benchmark refresh and remote CI were **NOT RUN**; this is a visibility-only
  refactor, not a behavior, quality, performance, or Phase 3 completion claim.

### LangChain-loader public API characterization checkpoint

- The next batch renames all four functions in
  `financial_langchain_loaders.py` in place:
  `_chat_prompt_template_from_template` to
  `chat_prompt_template_from_template`, `_str_output_parser` to
  `str_output_parser`, `_runnable_passthrough` to `runnable_passthrough`, and
  `_document` to `document`. Add no compatibility alias or forwarding wrapper;
  owner public/private counts project 0/4 to 4/0.
- Preserve each function-local `langchain_core` import. The prompt wrapper must
  call exact `ChatPromptTemplate.from_template(template)`; parser and
  passthrough wrappers instantiate their exact classes with zero arguments. The
  document wrapper retains keyword-only `page_content`/`metadata` and exact
  `Document(page_content=page_content, metadata=dict(metadata))`, including a
  fresh outer mapping and nested-object identities. Preserve every exception.
  Fresh-import isolation, direct factory identity 4/4, metadata-copy, and
  exception-propagation probes pass.
- Static scope is four definitions, 14 import bindings, and 25 calls across one
  owner plus eight importers. Calls finish 16 prompt, six parser, one
  passthrough, and two document; two parser calls retain `try` depth one and all
  other calls depth zero. Public collisions, non-call loads, attributes, and
  dynamic consumers are zero. Projected compilation passes source 9/9 and tests
  6/6.
- Thirteen direct test strings plus nine caller-body and seven caller-map hash
  occurrences make 29 test replacements. Source/test/whole projections are
  `+42/-42`, `+29/-29`, and `+71/-71`. The fingerprint mapping contains 16
  replacements with hash
  `4d9b13ad5541d99acb2cdc86ee9e5c95bf5c61e480a11e693782e96f89d7c323`.
- Mapping, current/projected binding, and current/projected call hashes are
  `c8e0fa3d0ad375525bbd70a11c3b144e3c8dfa2769208ff1f9ab4b1d77f4e084`,
  `395d4efc19b25d1a9bacbd91288d5f0d54208aa664cc638b3e9e05a89f6d7b64` /
  `59bf77dfac15eaf15b59196bc25ba064965491e1e7092539ae95487d8b295e09`,
  and
  `82d75a0b41292186737024be7b32664d88ac6e6689ce2c49ef818c3423e1cc67` /
  `dbad002ce2f18e9f4c1d7e196682309e3edd06f6d2960bf3d879e44d9be32d46`.
  The DAG projects unchanged at 48/203, audit remains 217, the affected seven-
  module suite is 676 tests, and full discovery remains 2,143. Exact mapping,
  fingerprint pairs, and gates are governed only by
  [Project Status Next Work](../overview/project_status.md#next-work).

### LangChain-loader public API milestone

- Commit `643bdf6` renames all four selected definitions, 14 import bindings,
  and 25 direct calls to public names without a compatibility alias or wrapper.
  Owner public/private counts finish 4/0 and retired private refs finish zero.
- Function-local `langchain_core` imports, exact prompt/parser/passthrough/
  document factories, returned identities, keyword-only document inputs, fresh
  outer metadata copy, nested identities, caller `try` depth, and every uncaught
  import/attribute/factory/mapping error remain unchanged.
- Production source is `+42/-42`, tests are `+29/-29`, and the whole commit is
  `+71/-71`. Thirteen direct test strings and 16 caller-body/map fingerprints
  account for the test transform. The committed diff SHA-256 is
  `d0f499aca84aab0aa6f242fdc308b589e8503c036e342c77b872764a784845e3`.
- Fresh-import isolation, factory identity 4/4, metadata-copy and exception
  probes, affected tests 676/676, import-side-effect 19/19, audit 217,
  source/test pycompile, unchanged 48-module/203-edge DAG at
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`,
  full 2,143/2,143 in 212.658 seconds, and diff checks passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, quality, ranking, performance, benchmark,
  schedule, ledger, or Phase 3 completion claim.

### Text-surface primitive public API characterization checkpoint

- The next batch renames all four externally imported private primitives in
  `financial_text_surface.py` in place: `_tokenize_terms` to `tokenize_terms`,
  `_split_sentences` to `split_sentences`, `_strip_anchor_text` to
  `strip_anchor_text`, and `_strip_rerank_metadata` to
  `strip_rerank_metadata`. Add no alias, wrapper, owner, policy, or behavior
  branch; leave `split_narrative_sentences(...)` unchanged.
- Preserve tokenizer `text or ""`, exact alphanumeric/Hangul regex, lowercase
  set and length filter; splitter direct normalization, blank short circuit,
  exact punctuation/`다` regex, ordered duplicates, and repeated `strip()`;
  anchor two-regex/normalization order; rerank exact `str(text or "")`, bracket
  removal, whitespace collapse, and final strip. Preserve raw truth,
  truthy-only rerank stringification, fresh results, immutability, and every
  uncaught failure. Current direct probes pass 8/8.
- Static scope is four definitions, ten import bindings, and 23 calls over one
  owner plus five importers: 14 token, one sentence, one anchor, and seven
  rerank calls. Every call has one positional argument, no keyword, and `try`
  depth zero; selected owner-local calls, non-call loads, attributes, and
  dynamic consumers are zero. Owner public/private counts project 15/4 to 19/0.
- Thirteen direct test strings plus ten fingerprint pairs occurring 11 times
  make 24 test replacements. Source/tests/whole project `+36/-36`, `+24/-24`,
  and `+60/-60`; the exact temporary projection diff SHA-256 is
  `78d64c25819b505c16ee3962126a98d1e2b6240c09ff41d2fe7749684b189ef0`.
  The fingerprint mapping hash is
  `9e3bc3b412aa48b6b48e84f655e04d1e16ee9d44511832a74bd54e8513957eb8`.
- Mapping, current/projected binding, and current/projected call hashes are
  `bf86fcefc508849d1961e5a8b24f8743fe77f00ff8b1ff62b853deabf1c5b5df`,
  `fbc70d3934774fb1d21e5fcf74924f36c3a28181d98668da4d3b211eb1c70f52` /
  `265e6f5987c7a8d873cbdaac2e35192c0f9048f8297772945b3c8bde1c2f93b9`,
  and
  `2b68507a11ae4fb03d4bc786839efb4cda2675efcfb1bebe7b498b027a5eff59` /
  `0c0021ed4fffe99cd081121800193812633902965f1d0ee809bed3026d053997`.
- The exact temporary projection passed public identity/behavior 4/4, directly
  affected tests 413/413 plus import 19/19 (432/432 combined), audit 217,
  pycompile 9/9, retired private refs zero, diff check, and unchanged 48/203 DAG
  at
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
  Full 2,143/2,143 remained the required implementation gate. Exact fingerprint
  pairs and historical stop lines remain in
  [Project Status Completed Text-Surface Characterization](../overview/project_status.md#completed-text-surface-primitive-characterization).
- Benchmark refresh and remote CI were **NOT RUN**. The projection establishes
  no behavior, accuracy, ranking, performance, schedule, ledger, or Phase 3
  completion claim.

### Text-surface primitive public API milestone

- Commit `4a4550c` renames all four selected definitions, ten import bindings,
  and 23 direct calls to `tokenize_terms`, `split_sentences`,
  `strip_anchor_text`, and `strip_rerank_metadata` without an alias, wrapper,
  owner, policy, or behavior branch. Owner public/private counts finish 19/0
  and retired private refs finish zero.
- Exact regexes, raw truth and stringification, one normalization path per
  primitive, lowercase/set filtering, set/list freshness, sentence order and
  duplicates, repeated `strip()`, caller exact-result versus `or original`
  adoption, and every uncaught error remain unchanged.
- Production source is `+36/-36`, tests are `+24/-24`, and the whole commit is
  `+60/-60`. Thirteen direct test strings and 11 existing CURRENT-SOURCE
  fingerprint replacements account for the test transform. The committed diff
  SHA-256 is
  `78d64c25819b505c16ee3962126a98d1e2b6240c09ff41d2fe7749684b189ef0`.
- Public identity/behavior 4/4, affected plus import tests 432/432 in 180.672
  seconds, audit 217, source/test pycompile 9/9, retired-ref zero, unchanged
  48-module/203-edge DAG at
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`,
  full 2,143/2,143 in 212.018 seconds, and diff checks passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, answer-quality, ranking, performance,
  benchmark, schedule, ledger, or Phase 3 completion claim.

### Preferred complete aggregate-answer public API characterization checkpoint

- The next bounded batch renames the exact current 63-line
  `financial_answer_projection._preferred_complete_aggregate_subtask_answer(...)`
  definition in place to public
  `preferred_complete_aggregate_subtask_answer(...)`. Add no alias, wrapper,
  owner, policy, or behavior branch. Owner public/private counts project 12/9
  to 13/8; its eight private support helpers remain private.
- Preserve blank-answer short circuit before exact eager
  `list(subtask_results or [])`, row identity/non-`Mapping` skip, mapping copies,
  operation/metric/status/candidate precedence, suffix narrative filtering,
  contained numeric-candidate and conflicting-surface paths, longest accepted
  answer, stable row order, immutability, helper laziness, and every uncaught
  error. Current and projected direct probes pass 7/7.
- Static scope is one definition, four imports, and four two-positional-argument
  calls at `try` depth zero across five source paths. Selected owner-local calls,
  non-call loads, attributes, dynamic consumers, and public collisions are zero.
  The exact four caller arguments and adoption/stop boundaries remain governed
  by [Project Status Next Work](../overview/project_status.md#next-work).
- Fourteen direct test strings plus one owner-count expectation make 15 test
  replacements; there is no caller fingerprint replacement. Source/tests/whole
  project `+9/-9`, `+15/-15`, and `+24/-24` across five source and three test
  files. The exact temporary projection diff SHA-256 is
  `0212a1273a1dfda7e87ed5cf3986e238e4433e89cbd0bf9cacc95b5439885c1d`.
- Selected-body, mapping, current/projected binding, and current/projected call
  hashes are
  `5828d88632c45a63a0376cc823682d8ff13d5f451ef3adf7124a5b89262b6bec`,
  `96f1acd9f315cf03c630bab38c42ddae77761c29936a22ff0f296fffe9b060ea`,
  `fbcda4b1226d349d324831f942ac40d4d16c389ef4e69765fec8daf205544502` /
  `4d9c472d5e85ce5c83300ec802c1b1f9905da34fdf6d489d400552928d98ec2a`,
  and
  `d751cfe671ef796048c1464ce42966751060efed2c3acde9b2733083d494ac79` /
  `5eb0ba8d59203ec8787553d03acbe009f076b26f5905ff2ec37fb3bf9b9d7bd3`.
- The exact temporary projection passed public identity 4/4, affected plus
  import tests 527/527 in 181.586 seconds, audit 217, pycompile 8/8, retired-ref
  zero, diff check, and unchanged acyclic 48/203 DAG at
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
  Full 2,143/2,143 remains an implementation gate; benchmark refresh and remote
  CI were **NOT RUN**. The characterization establishes no behavior, quality,
  performance, benchmark, schedule, ledger, or Phase 3 completion claim.

### Preferred complete aggregate-answer public API milestone

- Commit `f220c9c` renames the exact 63-line definition, four import bindings,
  and four direct calls to public
  `preferred_complete_aggregate_subtask_answer(...)` without an alias, wrapper,
  owner, policy, or behavior branch. Owner public/private counts finish 13/8
  and retired private refs finish zero.
- Blank-answer normalization/short circuit, eager row snapshot, mapping copies,
  operation/metric/status/candidate precedence, suffix narrative, contained
  numeric-candidate and conflicting-surface paths, longest/stable selection,
  four distinct caller adoption boundaries, helper laziness, immutability, and
  every exception remain unchanged.
- Production source is `+9/-9`, tests are `+15/-15`, and the whole commit is
  `+24/-24` across five source and three test files. Its committed diff SHA-256
  is `0212a1273a1dfda7e87ed5cf3986e238e4433e89cbd0bf9cacc95b5439885c1d`.
- Direct behavior/order/error 7/7, public identity 4/4, affected plus import
  527/527 in 181.671 seconds, audit 217, pycompile 8/8, retired-ref zero,
  unchanged acyclic 48/203 DAG, full 2,143/2,143 in 214.528 seconds, and diff
  checks passed.
- Benchmark refresh and remote CI were **NOT RUN**. This visibility-only
  milestone is not a behavior, answer-quality, ranking, performance,
  benchmark, schedule, ledger, or Phase 3 completion claim.

### Evidence-owner zero-load import cleanup characterization checkpoint

- The next bounded deletion removes exactly six unused imports from
  `financial_graph_evidence.py`: `classify_report_cache_consumer_candidate`,
  `KOREAN_COUNT_UNIT_RE_FRAGMENT`, `METRIC_TOPIC_EXTRACTION_TERMS`,
  `PERIOD_COMPARISON_COUNT_POLICY`, `active_narrative_policies`, and
  `narrative_policy_facets`. Delete no definition or other import and change no
  runtime path.
- All six bindings have zero owner loads/calls. Source/test analysis finds zero
  direct evidence-owner import, module attribute, or dynamic consumer. Eight
  exact `active_narrative_policies` test strings patch graph helpers instead.
  Current/empty selected-record hashes are
  `842dacd35d7991e45be44f6571c9f9c9924699eb6cc9dfb44e5d5c879156131c` /
  `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
- Source deletes exactly six lines. Absolute line shifts require nine existing
  fingerprint replacements in `test_financial_graph_helpers.py`, representing
  eight unique old/new pairs and no assertion weakening. Their mapping hash is
  `4d6ffde1b5765d0d8c697421f8eb3b6a970d07128b2d2875e17940ff9f57db7f`.
  Source/tests/whole project `+0/-6`, `+9/-9`, and `+9/-15`; the exact temporary
  diff SHA-256 is
  `2f26c4c2be025ddbc7d8c701af0e84707079c17a1934ca82f7a7890dca8d80d3`.
- The temporary projection passed affected graph-helper/text-surface/import
  339/339 in 168.290 seconds, audit 217, pycompile 2/2, selected consumer zero,
  diff check, and unchanged acyclic 48/203 DAG at
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
  Full 2,143/2,143 remains the implementation gate; exact scope and stop lines
  are governed by
  [Project Status Next Work](../overview/project_status.md#next-work).
- Benchmark refresh and remote CI were **NOT RUN**. The projection establishes
  no behavior, quality, performance, benchmark, schedule, ledger, or Phase 3
  completion claim.

### Evidence-owner zero-load import cleanup milestone

- Commit `6d0e21c` deletes exactly six selected imports from
  `financial_graph_evidence.py` and no definition, owner, live import/call,
  policy, or runtime branch. Selected owner loads, external imports, attributes,
  and dynamic consumers finish zero.
- Production source is `-6`, tests are `+9/-9`, and the whole commit is
  `+9/-15` across two files. Nine existing absolute-line fingerprint
  replacements account for the test transform. Its committed diff SHA-256 is
  `2f26c4c2be025ddbc7d8c701af0e84707079c17a1934ca82f7a7890dca8d80d3`.
- Focused graph-helper/text-surface/import 339/339 in 169.551 seconds, audit 217,
  pycompile 2/2, selected consumer zero, unchanged acyclic 48/203 DAG, full
  2,143/2,143 in 213.316 seconds, artifact hygiene, and diff checks passed.
- Benchmark refresh and remote CI were **NOT RUN**. This dead-import-only
  milestone is not a behavior, answer-quality, ranking, performance,
  benchmark, schedule, ledger, or Phase 3 completion claim.

### Graph-calculation query-focus import cleanup characterization checkpoint

- The next bounded deletion removes only the zero-load
  `query_focus_marker_groups` binding from the financial-text-surface import
  tuple in `financial_graph_calculation.py`. Preserve the owner definition,
  every live call, `query_focus_markers`, and all query-focus behavior.
- Static source/test analysis finds zero selected owner load/call, graph-
  calculation direct import, module attribute, patch, constant dynamic, or
  wildcard consumer. Current/empty record hashes are
  `f56c0e04506159ca481caad4ab16f9b8b23d5f686a4a374db94c97a281232209` /
  `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
- Retain adjacent `text_has_negative_surface`: the rejected initial two-import
  projection proved that CURRENT-SOURCE tests contract its graph-calculation
  compatibility identity. Do not weaken that export or expand the batch.
- Source deletes one line. Seven existing fingerprint expectations, representing
  six unique pairs, update only for shifted graph-calculation line numbers.
  Source/tests/whole project `+0/-1`, `+7/-7`, and `+7/-8`; the fingerprint
  mapping and exact temporary diff hashes are
  `6cc72ad0dd24bef2d0eb145a4902bdc8c0cbd465f40e7adbccb34710649ceefd` and
  `5cfe61d2307cdd4dbcd566e9e504a45cae8008eb1113daa4187feb069b3603b9`.
- The exact temporary projection passed focused graph-helper/text-surface/import
  339/339 in 168.418 seconds, audit 217, pycompile 2/2, selected consumer zero,
  retained compatibility identity, diff check, and unchanged acyclic 48/203
  DAG at
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
  Full 2,143/2,143 remains the implementation gate; exact scope and stop lines
  are governed by
  [Project Status Next Work](../overview/project_status.md#next-work).
- Benchmark refresh and remote CI were **NOT RUN**. The projection establishes
  no behavior, quality, performance, benchmark, schedule, ledger, or Phase 3
  completion claim.

### Graph-calculation query-focus import cleanup milestone

- Commit `7cdb317` deletes only the selected zero-load
  `query_focus_marker_groups` import from `financial_graph_calculation.py`.
  The owner definition, every live call, `query_focus_markers`, all query-focus
  behavior, and the contracted `text_has_negative_surface` compatibility
  identity remain unchanged.
- Production source is `-1`, tests are `+7/-7`, and the whole commit is `+7/-8`
  across two files. Seven existing absolute-line fingerprint replacements
  account for the test transform. Its committed diff SHA-256 is
  `5cfe61d2307cdd4dbcd566e9e504a45cae8008eb1113daa4187feb069b3603b9`.
- Focused graph-helper/text-surface/import 339/339 in 168.331 seconds, audit 217,
  pycompile 2/2, selected consumer zero, retained compatibility identity,
  unchanged acyclic 48/203 DAG, full 2,143/2,143 in 211.992 seconds, artifact
  hygiene, and diff checks passed.
- Benchmark refresh and remote CI were **NOT RUN**. This dead-import-only
  milestone is not a behavior, answer-quality, ranking, performance,
  benchmark, schedule, ledger, or Phase 3 completion claim.

### Reconciliation-candidate import cleanup characterization checkpoint

- The next bounded deletion removes only four zero-load bindings from the
  `financial_reconciliation_candidates` import tuple in
  `financial_graph_reconciliation.py`: `effective_structured_cell_unit_hint`,
  `find_reconciliation_match_entry`, `pair_candidate_period_score`, and
  `structured_cell_identity`.
- Importer loads/calls, direct imports through the reconciliation facade,
  attributes, patches, constant dynamic lookups, wildcard/`__all__`, and
  reviewed introspection consumers are all zero. The canonical owner retains
  all four definitions and 2/2/2/4 owner-local calls; the tuple's other four
  imports remain live. Current/empty selected-record hashes are
  `4d8b9f051c6044c2d4faff0260fc77c4838d8291fd3073713491208c899dd547` /
  `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
- Source deletes exactly four lines. Three graph-helper fingerprint
  expectations update and four names leave the existing
  reconciliation-candidate expected import set without weakening a contract.
  Source/tests/whole project `+0/-4`, `+3/-7`, and `+3/-11`; mapping and exact
  temporary diff hashes are
  `9a262825b226e1b55cbcf892e489ae7873d14ce41afbad5d2ace53351ca11395` and
  `133a07f36696c8efd7ac47b5a8459b56198a5293072ef2ef1f29988bdb794e1d`.
- The exact temporary projection passed graph-helper,
  reconciliation-candidate, and import-side-effect 323/323 in 189.466 seconds,
  audit 217, pycompile 3/3, selected consumer zero, diff check, and unchanged
  acyclic 48/203 DAG at
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
  Full 2,143/2,143 remains the implementation gate; exact scope and stop lines
  are governed by
  [Project Status Next Work](../overview/project_status.md#next-work).
- Benchmark refresh and remote CI were **NOT RUN**. The projection establishes
  no behavior, quality, performance, benchmark, schedule, ledger, or Phase 3
  completion claim.

### Reconciliation-candidate import cleanup milestone

- Commit `5de5e23` deletes exactly four zero-load imports from
  `financial_graph_reconciliation.py`: `effective_structured_cell_unit_hint`,
  `find_reconciliation_match_entry`, `pair_candidate_period_score`, and
  `structured_cell_identity`. Their canonical definitions, 2/2/2/4 owner-local
  calls, the tuple's other four live imports, and all reconciliation behavior
  remain unchanged. Selected facade consumers finish zero.
- Production source is `+0/-4`, tests are `+3/-7`, and the whole commit is
  `+3/-11` across three files. Three absolute-line fingerprint replacements
  and four expected-import removals account for the test transform. Its
  committed diff SHA-256 is
  `133a07f36696c8efd7ac47b5a8459b56198a5293072ef2ef1f29988bdb794e1d`.
- Focused graph-helper/reconciliation-candidate/import 323/323 in 173.754
  seconds, audit 217, pycompile 3/3, selected facade-consumer zero, unchanged
  acyclic 48/203 DAG, full 2,143/2,143 in 235.423 seconds, artifact hygiene,
  and diff checks passed.
- Benchmark refresh and remote CI were **NOT RUN**. This dead-import-only
  milestone is not a behavior, answer-quality, ranking, performance,
  benchmark, schedule, ledger, or Phase 3 completion claim.

### Evidence operand-needles import cleanup characterization checkpoint

- The next bounded deletion removes only the zero-load `operand_needles`
  binding from the `financial_surface_contracts` import tuple in
  `financial_graph_evidence.py`. Preserve its canonical definition, all 24
  source calls (four owner-local and twenty caller calls), the other eight
  external importers, and the tuple's three live imports.
- Importer loads/calls, direct imports through the evidence facade, attributes,
  patches, constant dynamic lookups, wildcard/`__all__`, and reviewed
  introspection consumers are all zero. Current/empty selected-record hashes
  are `e2df28a400e6577deca389376356b1bee5e537c1c32bf91d4277efc784c24b29` /
  `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
  Retained evidence imports have load/call counts 3/3, 8/8, and 1/1 for
  `text_has_negative_surface`, `text_has_positive_surface`, and
  `scoped_surface_affinity_priority`.
- Source deletes exactly one line. Nine graph-helper fingerprint occurrences
  representing eight unique pairs update, and two stale evidence-facade
  entries leave the existing operand-needles importer-set and public-identity
  expectations without weakening a contract. Source/tests/whole project are
  `+0/-1`, `+9/-11`, and `+9/-12`. The canonical eight-record
  `{old,new,occurrences}` mapping and exact temporary diff hashes are
  `f68f80850721da7816707b0761a79a9d46186678b8de71d83ae36016080adc7a` and
  `62acdb9c825520f15374b801e142afe37882e0896217cbe424ccb8d363619f44`.
- The exact temporary projection passed graph-helper/text-surface/import
  339/339 in 172.545 seconds, audit 217, pycompile 2/2, selected facade-
  consumer zero, diff check, and the unchanged acyclic 48/203 DAG at
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
  Full 2,143/2,143 remains the implementation gate; exact scope and stop lines
  are governed by
  [Project Status Next Work](../overview/project_status.md#next-work).
- Benchmark refresh and remote CI were **NOT RUN**. The projection establishes
  no behavior, quality, performance, benchmark, schedule, ledger, or Phase 3
  completion claim.

### Evidence operand-needles import cleanup milestone

- Commit `5ff7fd2` deletes only the zero-load `operand_needles` import from
  `financial_graph_evidence.py`. Its canonical definition, all 24 source calls
  (four owner-local and twenty caller calls), the other eight external
  importers, the tuple's three live imports, and all evidence behavior remain
  unchanged. Selected facade consumers finish zero.
- Production source is `+0/-1`, tests are `+9/-11`, and the whole commit is
  `+9/-12` across two files. Nine absolute-line fingerprint replacements and
  two stale facade-expectation removals account for the test transform. Its
  committed diff SHA-256 is
  `62acdb9c825520f15374b801e142afe37882e0896217cbe424ccb8d363619f44`.
- Focused graph-helper/text-surface/import 339/339 in 173.413 seconds, audit
  217, pycompile 2/2, selected facade-consumer zero, unchanged acyclic 48/203
  DAG, full 2,143/2,143 in 216.116 seconds, artifact hygiene, and diff checks
  passed.
- Benchmark refresh and remote CI were **NOT RUN**. This dead-import-only
  milestone is not a behavior, answer-quality, ranking, performance,
  benchmark, schedule, ledger, or Phase 3 completion claim.

### Graph-calculation TYPE_CHECKING import characterization checkpoint

- The next bounded deletion removes only `TYPE_CHECKING` from the existing
  single-line typing import in `financial_graph_calculation.py`. Preserve the
  physical line, `from __future__ import annotations`, every other source line,
  and the retained `Any`, `Dict`, `List`, `Literal`, `NamedTuple`, `Optional`,
  and `Sequence` entries.
- The binding has one import record but zero loads and zero `if TYPE_CHECKING`
  guards. Direct imports through the calculation facade, attributes, patches,
  constant dynamic lookups, wildcard/`__all__`, and reviewed introspection
  consumers are all zero. Two generic `TYPE_CHECKING` strings in import-side-
  effect tests inspect AST guards and are not facade consumers. Current/empty
  selected-record hashes are
  `6f0a5d9a0017ab6923a2f6117662efa41506e3d44d241ba2bb4b28e61fa77f8c` /
  `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
- The physical line count remains unchanged, so no test or fingerprint may
  change. Source/tests/whole project are `+1/-1`, `+0/-0`, and `+1/-1` across
  one file. The exact temporary diff SHA-256 is
  `bbabef4ee357dc074339da22f14fcd998a61c1b335b9e1fd7c3d238fd5880c0a`.
- The exact temporary projection passed graph-helper/text-surface/import
  339/339 in 170.992 seconds, audit 217, pycompile 1/1, selected facade-
  consumer zero, diff check, and the unchanged acyclic 48/203 DAG at
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
  Full 2,143/2,143 remains the implementation gate; exact scope and stop lines
  are governed by
  [Project Status Next Work](../overview/project_status.md#next-work).
- The remaining seventeen non-future zero-load bindings are excluded: ten
  graph compatibility surfaces, two experimental-MAS re-exports, and five
  legacy `multi_agent_graph.__all__` exports require separate contracts.
  Benchmark refresh and remote CI were **NOT RUN**. The projection establishes
  no behavior, quality, performance, benchmark, schedule, ledger, or Phase 3
  completion claim.

### Graph-calculation TYPE_CHECKING import cleanup milestone

- Commit `eea2935` removes only the zero-load, zero-guard `TYPE_CHECKING` entry
  from the existing typing import in `financial_graph_calculation.py`. The
  physical line, `from __future__ import annotations`, every other source line,
  and the live `Any`, `Dict`, `List`, `Literal`, `NamedTuple`, `Optional`, and
  `Sequence` imports remain unchanged. No test changed.
- Production source, tests, and the whole commit are `+1/-1`, `+0/-0`, and
  `+1/-1` across one file. Its committed diff SHA-256 is
  `bbabef4ee357dc074339da22f14fcd998a61c1b335b9e1fd7c3d238fd5880c0a`.
- Focused graph-helper/text-surface/import 339/339 in 169.812 seconds, audit
  217, pycompile 1/1, selected consumer and guard zero, unchanged acyclic
  48/203 DAG, full 2,143/2,143 in 214.291 seconds, artifact hygiene, and diff
  checks passed.
- Benchmark refresh and remote CI were **NOT RUN**. This dead-import-only
  milestone is not a behavior, answer-quality, ranking, performance,
  benchmark, schedule, ledger, or Phase 3 completion claim.

### Retrieval document-factory public API milestone

- Commit `f04e774` renames only the exact two-line
  `financial_retrieval_pipeline._make_document(*, page_content: str, metadata:
  Dict[str, Any]) -> Document` definition in place to public
  `make_document(...)`. Update exactly its one evidence import and three calls
  in `_expand_via_structure_graph`. Do not move or delete the wrapper, alter
  another retrieval helper, or touch unrelated storage-local `_make_document`
  definitions.
- The definition stays at lines 811-812 with two keyword-only arguments, one
  `Document` return annotation, and the exact
  `document(page_content=page_content, metadata=metadata)` return. Its
  normalized body hash is
  `750d355368ac00dbda6bc8c99170cdfe3dae0cfc1e41550cc217fd676fb8150e`.
  The three direct calls stay at evidence lines 242/255/305, preserve zero
  positional and exact two keyword expressions at `try` depth zero, and have
  record hash
  `3d198cada1c995990bc593c176974d327a2da4b028075fceda0c67e7f7a29090`.
- Current selected counts are one definition, one external import, and three
  calls. The future public name has no pre-existing source/test definition,
  import, call, patch, attribute, dynamic, wildcard/`__all__`, introspection,
  or exact test consumer. Both physical line counts remain 2,641/4,220; after
  the rename selected agent-private refs finish zero and the evidence binding
  is identical to the public retrieval owner.
- The rejected direct-loader projection changed the DAG from 48/203 to 48/202
  and triggered 45 graph-wide CURRENT-SOURCE failures before their expected
  updates. It is a separate consolidation contract. The accepted name-only
  projection keeps the 48/203 DAG at
  `e33db2a47885d60850b3defaa6776946fdf263fea190a9dda4611f09f3ad3710`.
- Source/tests/whole commit transforms are `+5/-5`, `+0/-0`, and `+5/-5`
  across two source files. The committed diff SHA-256 is
  `87b8eb4bbafb1f461d6671f7753d6de21a607ac038fecbc47ed7d34f532a0d9e`.
  Public identity/behavior 4/4, focused graph-helper/text-surface/import 339/339
  in 203.334 seconds, audit 217, pycompile 2/2, retired selected refs zero,
  artifact hygiene, diff check, and unchanged DAG passed. Full discovery passed
  2,143/2,143 in 271.268 seconds.
- Benchmark refresh and remote CI were **NOT RUN**. This name-only milestone
  establishes no behavior, quality, performance, benchmark, schedule, ledger,
  or Phase 3 completion claim.

### Retrieval supplement-section public API characterization checkpoint

- The next bounded visibility batch renames only the exact six-line
  `financial_retrieval_hints._supplement_section_terms_for_query(query: str,
  topic: str, intent: str) -> List[str]` definition in place to public
  `supplement_section_terms_for_query(...)`. Update exactly its one import and
  one direct call in `financial_graph_reconciliation.py`. Do not move the body,
  rename adjacent retrieval helpers, add an alias/wrapper, change ontology or
  policy data, or broaden reconciliation orchestration.
- The definition stays at lines 108-113 with three positional arguments, no
  defaults or keyword-only arguments, and a `List[str]` return. Preserve the
  fresh annotated list, exact comparison/trend early gate before ontology
  access, lazy `supplement_sections(query, topic, intent)` delegation, ordered
  dedupe, fresh return, and uncaught failures. Its name-normalized AST hash is
  `d4d297a9b8552e20eaf8d7d46fc49d446743d3e074acf1e08ea670f702d74468`.
- The sole production call stays at reconciliation line 1007 with exact
  positional `query`, `topic`, and `intent`, no keywords, and `try` depth zero.
  Its record hash is
  `e000be70acb3ffafce4974895677d66cad1aeb908843f90849f6097bac1b690c`.
  Owner/caller physical line counts remain 318/1,462.
- Current production counts are one definition, one external import, and one
  call. One exact patch string is the only selected test-name consumer; the
  public name has no pre-existing source/test definition, import, call, patch,
  attribute, dynamic, wildcard/`__all__`, introspection consumer, or collision.
  Projected private refs finish zero, reconciliation/owner identity holds, and
  owner public/private counts move only from 5/9 to 6/8.
- Five exact CURRENT-SOURCE expectations change: the patch target, two owner
  counts, the selected caller fingerprint from
  `8befdd9b9baf7734744d0923e12523f83ce2aba73f4fc7c0968b474a40c7a9a0`
  to `b0b24e7c4c91c76b3ab7765cbaf8fa27f87ed150b9ecaafc000bf204688eea01`,
  and its aggregate fingerprint from
  `0e13e85fed6712b333aa659427686113e24d47022ecd7d28f3a1c2f06be5d53e`
  to `b7cbc7c0fdce629eedfe83a1fffd19f6a7ee93a2816288c64b014343a64e5e14`.
  Add no test method and weaken no assertion.
- Source/tests/whole project exactly project `+3/-3`, `+5/-5`, and `+8/-8`
  across two source and two test files. The exact temporary diff SHA-256 is
  `a2d27efd562dd2134ea1f0f86a41877a9522811236d59b4d998a2ac99efe774c`.
  Identity/absence plus direct behavior 10/10, focused graph-helper/retrieval-
  hint/reconciliation-plan/import 365/365 in 184.397 seconds, audit 217,
  pycompile 4/4, retired selected refs zero, diff check, and unchanged acyclic
  48/203 DAG passed. Full 2,143/2,143 remains the implementation gate; exact
  scope and stop lines are governed by
  [Project Status Next Work](../overview/project_status.md#next-work).
- A first review-only dependency invocation stopped during imports because it
  omitted runtime requirements; it is not counted as a source-test result. The
  correctly provisioned rerun produced the 365/365 result above. Benchmark
  refresh and remote CI were **NOT RUN**. This checkpoint establishes no
  behavior, quality, performance, benchmark, schedule, ledger, or Phase 3
  completion claim.
