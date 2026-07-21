# Internal Calculation Mirror Cleanup

This note scopes the remaining cleanup for legacy top-level
`calculation_operands`, `calculation_plan`, `calculation_result`, and
`calculation_debug_trace` surfaces.

The external/public boundary is already mostly migrated: callers, evaluator
rows, benchmark review exports, MAS handoff surfaces, and smoke summaries should
prefer `structured_result` and `resolved_calculation_trace`. The remaining work
is internal representation cleanup, not a new answer-quality fix.

## Current Contract

| Surface | Current role | Cleanup stance |
| --- | --- | --- |
| `resolved_calculation_trace` | canonical calculation trace | keep |
| `structured_result` | canonical user-facing structured result | keep |
| task/artifact ledger `operand_set`, `calculation_plan`, `calculation_result` | typed MAS/runtime artifact contract | keep |
| top-level `calculation_*` in public/export payloads | legacy compatibility fallback | do not reintroduce |
| top-level `calculation_*` in live graph state | internal scratch/migration mirror | reduce after callsite audit |
| `debug_traces.calculation` | owned calculation debug surface | keep |
| `calculation_debug_trace` | optional calculation-node scratch state | keep internal only |

## Reader Categories

| Category | Examples | Required mode |
| --- | --- | --- |
| Live graph readers | formula planning, calculation execution, retry/reflection, active-task capture | strict: `allow_legacy_top_level = false` |
| Current export/review readers | evaluator, benchmark serialization, benchmark review, MAS analyst handoff | strict current-contract projection |
| Public bridge | `FinancialAgent.run()` projection | strict current-contract projection |
| Historical tools | replay and retrospective rescoring scripts | compatibility allowed, canonical trace wins |
| Historical resolver adapters | explicit `allow_legacy_top_level = true` call sites | compatibility allowed only for old bundles |

## Findings From 2026-06-07 Audit

- `src/agent/financial_graph_models.py` no longer carries top-level
  `calculation_operands`, `calculation_plan`, or `calculation_result` keys on
  `FinancialAgentState`. `calculation_debug_trace` remains optional
  calculation-node scratch state; the owned debug surface is
  `debug_traces.calculation`.
- `src/agent/financial_graph_helpers.py` owns the compatibility boundary:
  `_resolve_runtime_calculation_trace()` rejects top-level fallback by default,
  compatibility readers must opt in with `allow_legacy_top_level = true`, and
  `_runtime_trace_state_update()` now publishes only canonical
  `resolved_calculation_trace` / `structured_result` updates.
- Most live graph readers already use strict mode or mirror-free updates.
  `financial_graph_calculation.py` call sites rely on the helper's mirror-free
  contract.
- Aggregate reconciliation artifact enrichment now uses canonical aggregate
  projection material, ordered subtask source refs, and selected claims. It no
  longer reads top-level `calculation_result` source refs when deciding whether
  to backfill reconciliation artifact evidence refs.
- `FinancialAgent.run()` uses `_project_runtime_calculation_trace()` as a strict
  current-state projection. Top-level calculation mirrors are not accepted by
  the live public path.
- Retrospective scripts that read old bundles intentionally allow legacy
  fallback. They should not be used as evidence that live runtime readers still
  need top-level mirrors.

## Safe Cleanup Order

1. Keep strict-mode assertions around every live graph reader before
   removing state fields. Existing tests already cover many stale top-level
   rejection paths.
2. Stop adding new top-level `calculation_*` writes. New runtime updates should
   use `_runtime_trace_state_update()`, which no longer supports compatibility
   mirror opt-in.
3. Keep `calculation_debug_trace` as optional calculation-node scratch state
   only. Public and current-run ops output should use `debug_traces.calculation`
   instead of recreating a top-level debug bridge.
4. Keep legacy flat `calculation_operands`, `calculation_plan`, and
   `calculation_result` acceptance inside explicit resolver/adapters only for
   historical bundles; do not put those keys back on `FinancialAgentState`.
5. Keep explicit compatibility support for historical replay and retrospective
   tools. Their contract is to read old artifacts safely while preferring
   canonical `resolved_calculation_trace` when present.

## Completed Increment

- 2026-06-07: closed one live aggregate reader gap. Reconciliation artifact
  evidence refs are no longer backfilled from stale top-level
  `calculation_result` source refs. Focused regression tests cover canonical
  `resolved_calculation_trace` source-ref preservation and stale top-level
  source-ref rejection.
- 2026-06-07: split state typing into concern-specific TypedDicts and made
  `RuntimeCalculationTrace` / `TaskResultRecord` the canonical calculation and
  subtask ledger contracts.
- 2026-06-07: closed the debug ownership follow-up. `FinancialAgentState` now
  marks `calculation_debug_trace` optional and exposes the owned public debug
  surface as `debug_traces.calculation`.
- 2026-06-07: removed initial live-state seeding for optional top-level
  calculation mirrors and `calculation_debug_trace`. Calculation nodes may still
  write the debug scratch field when they have diagnostic material, but a fresh
  run no longer starts with empty compatibility fields.
- 2026-06-07: separated calculation-node scratch writes from public debug
  projection in code. Calculation diagnostics now flow through
  `_calculation_debug_state_update()` / `_clear_calculation_debug_state()`, and
  `FinancialAgent.run()` exposes them under `debug_traces.calculation`.
- 2026-06-22: removed the unused `_runtime_trace_state_update()` compatibility
  mirror opt-in and the explicit `include_compatibility_mirrors = false` call
  sites. The helper now has a single mirror-free update contract.
- 2026-06-22: removed omitted-part carry-forward from
  `_runtime_trace_state_update()`. Callers must now pass operands, plan, and
  result explicitly; legacy top-level fallback stays only in explicit
  export/review/historical readers.
- 2026-06-22: changed `_resolve_runtime_calculation_trace()` to strict default.
  Legacy top-level fallback is now opt-in and limited to public/export/replay
  compatibility boundaries.
- 2026-06-22: removed empty top-level calculation mirror seeds from current-run
  ops/debug initial states. These scripts now follow the live graph shape and
  read canonical `resolved_calculation_trace` plus owned debug projections
  instead of pre-populating optional compatibility fields.
- 2026-06-22: moved `debug_math_workflow.py` calculation diagnostics in JSON
  output to `debug_traces.calculation`, so this current-run ops helper no
  longer creates a separate top-level `calculation_debug_trace` output bridge.
- 2026-06-22: removed the old top-level `calculation_debug_trace` compatibility
  bridge from `FinancialAgent.run()` output. The scratch state key remains
  optional inside graph calculation nodes; public output now uses
  `debug_traces.calculation`.
- 2026-06-22: removed top-level `calculation_operands`, `calculation_plan`, and
  `calculation_result` from `FinancialAgentState` typing. Legacy fallback
  remains available through explicit resolver/adapters for historical bundles,
  not through the live graph state contract.
- 2026-06-22: removed the live graph flat `calculation_*` reader path from
  `_project_task_trace_from_state()`. Direct aggregate-node tests now provide
  current active-task material through canonical `resolved_calculation_trace`
  or task artifacts; stale top-level flat fields remain regression fixtures
  proving that live capture ignores them.
- 2026-06-22: changed the MAS analyst smoke direct-output readers to strict
  resolver mode by default. Legacy top-level result payloads are still readable
  only through an explicit helper opt-in for compatibility tests, while current
  smoke comparisons now require canonical `resolved_calculation_trace`.
- 2026-07-22: removed legacy top-level calculation fallback from
  `FinancialAgent.run()`. The public projection now resolves only canonical
  `resolved_calculation_trace`, and structured output falls back only to that
  trace's calculation result. The callerless `_resolve_runtime_structured_result()`
  compatibility wrapper and its private-helper test were deleted. Historical
  replay and retrospective opt-ins remain unchanged.

## Remaining Implementation Candidates

Further cleanup should target internal diagnostics or proven callerless
surfaces, not answer behavior:

- keep calculation-node diagnostics on the explicit scratch helpers; new
  callsites should not write the top-level debug key directly;
- update tests that seed stale top-level fields so they remain explicit
  compatibility or regression fixtures;
- keep direct aggregate-node tests on canonical `resolved_calculation_trace` or
  task artifacts; do not reintroduce live graph flat `calculation_*` reads;
- avoid deleting historical-tool fallback until old result-bundle replay is no
  longer needed.

## Verification

For docs-only scope updates:

- `rg -n "internal_calculation_mirror_cleanup|calculation_\\*" docs/architecture CONTEXT.md`
- `git diff --check`

For code changes under `src/agent`:

- `python -m src.ops.audit_runtime_domain_terms`
- `python -m unittest tests.test_operation_contracts tests.test_subtask_loop tests.test_financial_agent_run_projection tests.test_evaluator_runtime_projection tests.test_benchmark_runner_runtime_projection`
- `python -m unittest discover -s tests`
