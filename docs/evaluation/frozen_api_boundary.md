# Frozen results through the public API

Base `b7d9c874`; provider-free API-boundary rehearsal on 2026-09-18.
All **12** requests preserve the three frozen results through the actual app
factory, ASGI router, `FinancialAgent.run()` packaging and HTTP serialization.
Services and the graph result are explicit test doubles. No runtime fix was needed.

| Frozen result | API modes checked | Public result | Ledger when requested |
| --- | --- | --- | --- |
| Search/display, from saved provider responses | Default, review, debug, both | Two outputs, `ok` | Integrity `ok`, aggregate `completed` |
| Research count/scope, from authored responses | Default, review, debug, both | **21건** and scope explanation, `ok` | Integrity `ok`, aggregate `completed` |
| Missing costs, from authored responses | Default, review, debug, both | Bounded explanation, costs missing, `partial` | Integrity `ok`, aggregate `partial` |

HTTP **200** reports successful request handling; it does not turn the missing
cost collection into a completed output. The result still identifies `ob_001`
as missing in all four modes. Prior source/model claim limits remain unchanged:
paid search/display **0/4**, its exact offline replay **4/4**, and the other two
questions live-unexecuted. These are not new model answers or a release gate.

## Executed boundary

`main.create_app()` and its lifespan use a mocked service factory with an
explicit ready fixture. The real `/api/query` endpoint validates input, acquires
the service lock and dispatches the actual `FinancialAgent.run()` method to a
worker thread. Only `graph.invoke()` is replaced with a copy of each saved
phase-integration result. No graph node, planner, Compiler, retrieval, provider,
embedding, store client or fresh service construction runs. Store readiness is
not re-certified by the ready fixture, and no external server is started.

The original question and report scope reach the wrapper unchanged. All public
answer text, citations, `structured_result` and `resolved_calculation_trace`
match the frozen graph result, including nested nulls and the original numeric,
period, unit and narrative proof values. Source criteria never enter this replay.

Review and debug flags operate independently. Defaults omit both fields, even
when a debug-enabled request has just used the same agent. Requested review
retains the final ledger's tasks, artifacts and integrity trace. Requested debug
retains the historical Compiler attempts and calculation diagnostics. The public
answer projection contains no Compiler-attempt or request-diagnostic envelope.

New request diagnostics cover only the executed wrapper: `run_started`,
`usage_snapshot`, `run_completed`. They contain the current request, with no
fabricated phase or model events. Historical Compiler attempts remain replayed
evidence. Usage objects are empty because no usage callback/store exists in this
harness; they are not measured live zero-token receipts.

## Failure boundary

| Injected condition | HTTP | Graph invocations | Public response |
| --- | --- | --- | --- |
| Service not ready | 503 | 0 | Error detail only |
| Blank question | 422 | 0 | Error detail only |
| Agent unavailable | 503 | 0 | Error detail only |
| Graph raises | 500 | 1 | Generic error detail, no private exception text |

None receives a fabricated answer, successful structured result, review bundle
or ledger. These failures are distinct from evidence-backed bounded abstention.
The synthetic graph error is deliberate; there are no unexpected API failures.

## Validation and preservation

**12** positive ASGI requests, **4** injected failure controls and focused
**35/35** existing contracts pass. Documentation checks **4/4** pass; no skips
or external connection attempts. Six representative full HTTP payloads retain
default/both modes; the other six modes retain exact body hashes and comparison
receipts. All three original execution artifacts remain unchanged.

All **173** source files, **2029** protected predecessor artifacts, **24** store
files and local settings retain hashes. `main.py` and the executed API/wrapper
owners are separately hashed in the packet. Only documentation is tracked.
Prior full **2029/2029** and domain audit **83** are unchanged-source evidence,
not newly rerun results. Local receipts:
[`frozen_api_boundary_2026-09-18`](../../benchmarks/results/frozen_api_boundary_2026-09-18/RESULTS.md).

Provider/count/embedding requests, paid retries, new admissions, ingest and added
cost are **0**. Shared accounting remains **7.38602105 / 8**, remainder
**0.61397895**, pending 0, including historical count contingency rather than
invoice. Current live completion and input-token budget fit remain unverified.

## Next bounded work

The phase and API replay gates are complete. Next prepare a **no-call admission**
for one fresh search/display application run on current source, using its frozen
question/criteria and the existing **0.61397895** remainder. Check the current
caller guards, exact inputs and fail-closed budget boundaries before any dispatch;
keep output limits and runtime behavior unchanged. The old consumed manifest
cannot be resumed. Preparation makes no provider/count/embedding request and
does not schedule a paid retry, the other two questions, ingest or a cap increase.
