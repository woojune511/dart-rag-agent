# Self-Reflection Capability Contract

This note defines the target boundary for retry/reflection behavior. The goal
is to stop adding local rule branches to the live graph and make reflection a
bounded capability with explicit inputs, outputs, limits, and ledger effects.

## Current Problem

The current retry path is spread across:

- eligibility and routing in `financial_graph_calculation.py`
- heuristic retry query construction in `financial_graph_reconciliation.py`
- LLM-backed `ReflectionQueryPlan`
- retry state mutation in `_prepare_reflection_retry()`
- retrieval fan-out behavior that depends on `reflection_count`

That path works, but it is still shaped like a graph escape hatch. If new
failures keep adding more branch conditions, reflection becomes another hidden
runtime policy instead of a reviewable capability.

## Target Shape

Reflection should be represented as a capability invocation:

```text
ReflectionRequest
  -> ReflectionPlan
  -> ReflectionAction
  -> ReflectionReport
```

The capability may request one bounded retry action, but it should not directly
own final answer acceptance.

## Contract Surfaces

| Surface | Required fields | Owner |
| --- | --- | --- |
| `ReflectionRequest` | query, active task id, failure status, missing info, runtime trace summary, evidence/retrieval summary, remaining retry budget | Orchestrator or current graph adapter |
| `ReflectionPlan` | status, objective, strategy, missing info, subqueries, preferred sections, rationale | reflection planner |
| `ReflectionAction` | action type, retry queries, retrieval scope hints, synthesis source ids, stop reason | deterministic adapter |
| `ReflectionReport` | outcome, action taken, budget consumed, target task/artifact ids, blocking issues | Critic/Orchestrator handoff |

Allowed strategies:

- `retry_retrieval`
- `synthesize_from_task_outputs`
- `stop_insufficient`

No other strategy should be accepted without updating this contract and tests.

## Required Limits

- Maximum retry budget is explicit and defaults to one retry in the current
  single-agent graph.
- Reflection may not add domain vocabulary in runtime code. Missing concepts
  still belong in ontology, retrieval policy, parser structure, planner
  contract, evidence schema, or evaluator definition.
- Reflection may not bypass task/artifact integrity checks.
- Reflection may not mark a final answer accepted. It only proposes the next
  bounded action or a stop reason.
- Reflection retry queries must be visible in state and reviewer output.
- Reflection report handoff is recorded as a `reflection` task with a
  `reflection_report` artifact. The artifact must contain
  `reflection_report.outcome`, `reflection_report.action_taken`, and
  `reflection_report.budget_consumed`; target refs and blocking issues remain
  reviewer/orchestrator handoff metadata, not acceptance authority.

## Current-Code Mapping

| Current code | Target responsibility |
| --- | --- |
| `_is_reflection_eligible()` | request builder / budget gate |
| `_plan_reflection_retry()` | reflection planner adapter |
| `_heuristic_reflection_query_plan()` | deterministic fallback planner |
| `_finalize_retry_queries()` | action builder |
| `_prepare_reflection_retry()` | action applier |
| `_route_after_formula_planner()` / `_route_after_calculator()` | temporary graph adapter |

## First Implementation Increment

The first code increment avoids changing answer behavior. It makes the contract
boundary visible:

1. Add TypedDicts for request, plan, action, and report.
2. Make `_plan_reflection_retry()` normalize planner output through one helper.
3. Make `_prepare_reflection_retry()` expose a normalized action shape.
4. Make `_prepare_reflection_retry()` emit a bounded `ReflectionReport` handoff.
5. Add `reflection` / `reflection_report` to the task/artifact ledger contract.
6. Add tests for allowed strategies, legacy trace rejection, report shape, and
   ledger integrity.
7. Keep current graph routes intact.

Current status: TypedDicts, request builder, plan normalization, and action
projection are in place. `_prepare_reflection_retry()` now also records a
`ReflectionReport` with the selected action, retry budget consumption,
target task/artifact ids when visible, and blocking issues for
`stop_insufficient`. The same report is also persisted as a
`reflection_report` artifact attached to a `reflection` task so critic and
orchestrator handoff readers can inspect it through `task_artifact_trace`.
This is a handoff record only; final acceptance behavior and graph routes are
unchanged.

## Promotion Criteria

Reflection should not become an active retry capability just because the
handoff shape exists. Promotion requires a focused gate that shows reflection
recovers real missing-material failures without creating unsupported answers or
hiding task/artifact integrity issues.

Required focused-gate signals:

| Signal | Definition | Promotion expectation |
| --- | --- | --- |
| `reflection_trigger_rate` | Share of eligible failed or incomplete tasks that invoke reflection | Non-zero on known reflection-eligible failures, bounded on clean passes |
| `recovery_rate` | Share of reflection-triggered cases that become accepted after one bounded retry | Positive on the focused recovery set |
| `false_recovery_rate` | Share of reflected cases accepted despite unsupported evidence, bad calculation trace, or integrity errors | Must be `0.0` on the focused promotion set |
| `latency_delta` | Added runtime or step count versus the same case without reflection | Reported and bounded before promotion |
| `integrity_preservation_rate` | Share of reflected accepted cases with `task_artifact_trace.integrity_status = ok` | Must be `1.0` for accepted reflected cases |

Minimum focused promotion set:

- at least one case where normal execution lacks retrieved evidence and
  reflection can issue a bounded `retry_retrieval` action
- at least one case where normal execution has enough task outputs and
  reflection can choose `synthesize_from_task_outputs`
- at least one case where reflection must choose `stop_insufficient`
- at least one clean-pass case where reflection is not triggered

Promotion is blocked if any reflected accepted answer:

- uses evidence that is not visible in retrieved docs, task outputs, or the
  artifact ledger
- changes final acceptance without a critic/orchestrator acceptance record
- bypasses `task_artifact_trace` integrity checks
- consumes more retry budget than the request allows
- adds company, benchmark id, metric, or question-specific runtime branches

## Promotion Test Plan

The repo-local `src.ops.reflection_promotion_gate` command is the first
fixture plus trace-summary version of this gate. Its default run evaluates the
base fixture set, a store-fixed candidate surface fixture, and a reviewed
store-fixed trace summary distilled from local eval-only artifacts. The gate
also checks that triggered reflection reports include bounded budget
consumption, target task/artifact refs for accepted reflected cases, blocking
issues for `stop_insufficient`, retry-query visibility for `retry_retrieval`,
source-id visibility for `synthesize_from_task_outputs`, and
`final_acceptance_authority = critic_orchestrator_handoff` rather than
reflection. A future active-reflection PR should keep that gate green or
extend it with additional store-fixed or live/default trace summaries before
any broader benchmark refresh:

1. Unit tests for trigger eligibility, request construction, allowed strategies,
   budget consumption, and `ReflectionReport` ledger shape.
2. A focused reflection promotion command or profile that reports the five
   promotion signals above.
3. A negative case proving `stop_insufficient` remains a safe terminal action
   and does not produce a final accepted answer.
4. A clean-pass case proving reflection does not run when the initial
   task/artifact and critic contracts are already healthy.

Full benchmark refresh is not required for the first promotion PR unless the
implementation changes retrieval, calculation, answer composition, or final
acceptance behavior outside the reflection path.

## Non-Goals

- Do not add new benchmark-specific retry branches.
- Do not expand the retry budget.
- Do not make cache candidates or `REFERENCE_NOTE` retrieval part of reflection
  until the report-scoped cache capability has its own producer contract.
- Do not promote LLM reflection output to acceptance authority.
