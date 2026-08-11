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
