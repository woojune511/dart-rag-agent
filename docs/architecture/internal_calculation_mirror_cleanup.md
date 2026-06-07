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
| `calculation_debug_trace` | legacy top-level debug compatibility bridge | optional only |

## Reader Categories

| Category | Examples | Required mode |
| --- | --- | --- |
| Live graph readers | formula planning, calculation execution, retry/reflection, active-task capture | strict: `allow_legacy_top_level = false` |
| Current export/review readers | evaluator, benchmark serialization, benchmark review, MAS analyst handoff | strict current-contract projection |
| Public bridge | `FinancialAgent.run()` projection | compatibility allowed, but must mark projection metadata |
| Historical tools | replay and retrospective rescoring scripts | compatibility allowed, canonical trace wins |
| Helper compatibility adapters | `_resolve_runtime_structured_result()`, omitted-part carry-forward in `_runtime_trace_state_update()` | compatibility allowed only by explicit surface contract |

## Findings From 2026-06-07 Audit

- `src/agent/financial_graph_models.py` still carries top-level calculation
  state keys on `FinancialAgentState`, but `calculation_operands`,
  `calculation_plan`, and `calculation_result` are now typed as optional
  compatibility mirrors. `calculation_debug_trace` is also optional; the owned
  debug surface is `debug_traces.calculation`.
- `src/agent/financial_graph_helpers.py` owns the compatibility boundary:
  `_resolve_runtime_calculation_trace()` can allow or reject top-level fallback,
  and `_runtime_trace_state_update()` defaults to
  `include_compatibility_mirrors = false`.
- Most live graph readers already use strict mode or mirror-free updates.
  `financial_graph_calculation.py` call sites rely on the helper default and
  pass `include_compatibility_mirrors = false` on explicit update branches.
- Aggregate reconciliation artifact enrichment now uses canonical aggregate
  projection material, ordered subtask source refs, and selected claims. It no
  longer reads top-level `calculation_result` source refs when deciding whether
  to backfill reconciliation artifact evidence refs.
- `FinancialAgent.run()` still uses `_project_runtime_calculation_trace()` as a
  public compatibility bridge. This is intentional while older callers may still
  send or inspect legacy top-level fields.
- Retrospective scripts that read old bundles intentionally allow legacy
  fallback. They should not be used as evidence that live runtime readers still
  need top-level mirrors.

## Safe Cleanup Order

1. Keep resolver defaults unchanged for now. Changing
   `_resolve_runtime_calculation_trace(..., allow_legacy_top_level = true)` by
   default would affect public bridges and retrospective readers.
2. Add or keep strict-mode assertions around every live graph reader before
   removing state fields. Existing tests already cover many stale top-level
   rejection paths.
3. Stop adding new top-level `calculation_*` writes. New runtime updates should
   use `_runtime_trace_state_update()` and leave
   `include_compatibility_mirrors = false`.
4. Keep `calculation_debug_trace` as a top-level compatibility bridge only while
   callers migrate to `debug_traces.calculation`. It is not a required runtime
   state surface.
5. Remove top-level `calculation_operands`, `calculation_plan`, and
   `calculation_result` from `FinancialAgentState` only after compatibility
   bridges and typed adapters no longer require them as accepted optional keys.
6. Keep explicit compatibility support for historical replay and retrospective
   tools. Their contract is to read old artifacts safely while preferring
   canonical `resolved_calculation_trace` when present.

## Completed Increment

- 2026-06-07: closed one live aggregate reader gap. Reconciliation artifact
  evidence refs are no longer backfilled from stale top-level
  `calculation_result` source refs. Focused regression tests cover canonical
  `resolved_calculation_trace` source-ref preservation and stale top-level
  source-ref rejection.
- 2026-06-07: closed the state typing follow-up for legacy calculation mirrors.
  `FinancialAgentState` now marks top-level `calculation_operands`,
  `calculation_plan`, and `calculation_result` as optional compatibility
  mirrors. Focused projection tests lock this state-shape distinction.
- 2026-06-07: closed the debug ownership follow-up. `FinancialAgentState` now
  marks `calculation_debug_trace` optional and exposes the owned public debug
  surface as `debug_traces.calculation`; the old top-level
  `calculation_debug_trace` remains a compatibility bridge in `FinancialAgent.run()`.
- 2026-06-07: removed initial live-state seeding for optional top-level
  calculation mirrors and `calculation_debug_trace`. Calculation nodes may still
  write the debug scratch field when they have diagnostic material, but a fresh
  run no longer starts with empty compatibility fields.
- 2026-06-07: separated calculation-node scratch writes from the public
  compatibility bridge in code. Calculation diagnostics now flow through
  `_calculation_debug_state_update()` / `_clear_calculation_debug_state()` and
  the public `FinancialAgent.run()` bridge uses the runtime-contract field
  constant.

## Next Implementation Candidate

The next code cleanup should target compatibility bridge boundaries, not answer
behavior:

- audit whether public compatibility bridges still need to accept the optional
  legacy calculation mirror keys and top-level debug bridge;
- keep calculation-node diagnostics on the explicit scratch helpers; new
  callsites should not write the top-level debug key directly;
- update tests that seed stale top-level fields so they remain explicit
  compatibility or regression fixtures;
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
