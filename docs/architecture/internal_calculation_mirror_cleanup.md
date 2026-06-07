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
| `calculation_debug_trace` | internal debug state | keep until debug trace ownership is separated |

## Reader Categories

| Category | Examples | Required mode |
| --- | --- | --- |
| Live graph readers | formula planning, calculation execution, retry/reflection, active-task capture | strict: `allow_legacy_top_level = false` |
| Current export/review readers | evaluator, benchmark serialization, benchmark review, MAS analyst handoff | strict current-contract projection |
| Public bridge | `FinancialAgent.run()` projection | compatibility allowed, but must mark projection metadata |
| Historical tools | replay and retrospective rescoring scripts | compatibility allowed, canonical trace wins |
| Helper compatibility adapters | `_resolve_runtime_structured_result()`, omitted-part carry-forward in `_runtime_trace_state_update()` | compatibility allowed only by explicit surface contract |

## Findings From 2026-06-07 Audit

- `src/agent/financial_graph_models.py` still declares top-level
  `calculation_operands`, `calculation_plan`, `calculation_result`, and
  `calculation_debug_trace` on `FinancialAgentState`. These are the main
  remaining state-shape mirrors.
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
4. Split debug ownership before removing `calculation_debug_trace` from
   `FinancialAgentState`. It is a debug surface, not a calculation-result
   compatibility mirror.
5. Remove top-level `calculation_operands`, `calculation_plan`, and
   `calculation_result` from `FinancialAgentState` only after live graph nodes,
   tests, and any typed adapters no longer require them as working-state keys.
6. Keep explicit compatibility support for historical replay and retrospective
   tools. Their contract is to read old artifacts safely while preferring
   canonical `resolved_calculation_trace` when present.

## Completed Increment

- 2026-06-07: closed one live aggregate reader gap. Reconciliation artifact
  evidence refs are no longer backfilled from stale top-level
  `calculation_result` source refs. Focused regression tests cover canonical
  `resolved_calculation_trace` source-ref preservation and stale top-level
  source-ref rejection.

## Next Implementation Candidate

The next code cleanup should still target state typing and tests, not answer
behavior:

- introduce a narrower internal scratch-state note or helper for calculation
  working values;
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
