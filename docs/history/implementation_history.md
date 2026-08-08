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
