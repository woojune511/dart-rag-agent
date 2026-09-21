# Unsupported 2024 actual: provider-free boundary characterization

On source base `e5edaab2`, the frozen `unavailable_2024_actual` request was
checked without provider calls. **47 boundary assertions and 70 existing
contract tests pass.** Runtime source is unchanged. This checks deterministic
boundaries with authored Planner output and staged source cells; the live
question remains unexecuted and **semantic outcome is `not_assessed`**.

## Frozen question and evidence

The [original criteria](independent_question_criteria.md) ask for actual
consolidated operating cash flow for January 1 through December 31, 2024,
using only NAVER's 2023 annual report, receipt `20240318000844`.
The question, report scope and review criteria remain byte-identical.

The original consolidated cash-flow cell `47:0:1` contains
**2,002,233,273,518원**. Its attached text binds `제 25 기` to
`2023.01.01 부터 2023.12.31 까지`. Cell, unit, table locator, document hash and
attached contexts were rechecked against original JSON sidecars. The staged
physical row contains the observed 2021, 2022 and 2023 values from the earlier
cash-flow run; it is **not newly retrieved evidence for the 2024 question**.
This establishes the inspected row's periods, not exhaustive corpus absence.

## Observed boundaries

| Control | Observed result | Interpretation |
| --- | --- | --- |
| Exact API request and authored Planner period `2024` | Full question, request-unit ownership and selected 2023 report survive planning, retrieval and compilation inputs | Transport and normalization, not Planner inference |
| Source filter | Selected receipt retained; other receipt, later filing and other report type rejected; 1,090 original graph nodes eligible | Metadata eligibility, not ANN retrieval or answer coverage |
| Same receipt with another entity's metadata | Allowed under the existing receipt-first rule | One filing may describe other entities; company metadata does not override receipt authority |
| Select the 2023 cell for a declared 2024 output | `candidate_source_condition_conflict`, `candidate_scope_mismatch`; no numeric output | Known period mismatch is rejected |
| Declare `2024` against the unchanged 2023 period quote | `context_conflicts_with_candidate` plus scope errors; no numeric output | A model declaration cannot relabel the located source |
| Authored Planner plus the staged 2021–2023 row through the real graph and API | HTTP 200, `incomplete`, one missing obligation, no amount or citations | All staged cells conflict with 2024, so no Compiler request is made |
| Actual Planner admission exception / API-boundary timeout and runtime exceptions | HTTP 500, no answer | Failures are not accepted evidence-insufficiency answers |
| Readiness false | HTTP 503, agent not invoked, no answer | Readiness failure is not semantic abstention or safe scope rejection |

The staged graph invokes only one authored Planner response. Its queued
Compiler abstention fixture is **not consumed**. Numeric execution, final
assembly, public projection and ledger use the normal runtime functions.
The visible answer is:

> 필요한 근거를 충분히 확인하지 못했습니다: 2024년 실제 연결 영업활동현금흐름

The scalar result is `null`, with zero operands and subtask outputs. Ledger
integrity is `ok` (two tasks, five artifacts, zero issues); its aggregate result
remains incomplete. Ledger integrity and HTTP 200 do not make this a complete
numeric answer or a sampled semantic PASS. No original Chroma store was opened.

## Remaining semantic boundary

An authored **blank numeric Planner period still defaults to the report year,
2023**. A control with the declared output period changed to 2023 accepts the
same source cell even though the original question asks for 2024. That control
is deliberately a semantic negative: physical source linkage cannot certify
that Planner preserved the requested period. No keyword-based year correction
or question-specific runtime rule was introduced.

The existing abstention tests separately exercise explicit missing and ambiguous
Compiler decisions and verify that they do not trigger a repair. They do not
prove that a model will make those decisions on this question. The current
rehearsal also does not exercise fresh routing, model planning, embedding,
native retrieval, provider SDK transport, or document-wide absence reasoning.

## Verification, accounting and next work

The 70 tests cover abstention, relative and contextual periods, Planner period
scope, retrieval isolation, API contracts and public error boundaries. The
initial local socket guard blocked Windows asyncio's loopback self-pipe;
correcting the harness to permit loopback while denying external connections
made all 70 pass. Fixture expectation/constructor corrections and earlier logs
remain in the local packet. These required no product changes.

All **10,875 predecessor files**, **175 source files**, seven protected owners,
**24 original store files** and local settings preserve hashes. External network
attempts, native queries, provider calls, new cost and pending reservations are
all zero. Shared accounting stays **18.54510435 / 20.07 USD**, leaving
**1.52489565**. No funding increase, live caller or paid authorization was created.

The subsequent [single-question live result](unavailable_2024_result.md) preserves
the full 2024 period and returns missing evidence over actual retrieval, with
16 successful HTTP requests and no retry. Its final explanation remains partial;
it does not repeat the selected-report/full-year limitation. The draft is consumed,
added accounting is 0.20457258 and remaining allowance 1.32032307. Next characterize
the generic explanation/citation contract provider-free; this earlier authored
boundary remains separate evidence and its blank-period concern is unchanged.

Local evidence: [47 boundary assertions](../../benchmarks/results/unavailable_2024_boundary_2026-09-21/boundary_result.json),
[70 contract tests](../../benchmarks/results/unavailable_2024_boundary_2026-09-21/focused_tests_v2.json),
[authored API result](../../benchmarks/results/unavailable_2024_boundary_2026-09-21/empty_cohort_authored_api_result.json),
[baseline](../../benchmarks/results/unavailable_2024_boundary_2026-09-21/baseline.json).
