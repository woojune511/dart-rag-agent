# Single cash-flow question admission

The first [frozen additional question](independent_question_criteria.md) now has
a dedicated single-use caller and provider-free rehearsal. **62 focused tests**,
**three application failure rehearsals** and **40 saved-evidence checks** pass.
This work made **zero real provider calls** and added **USD 0**. It does not
establish retrieval coverage or answer quality for this question.

## Exact scope

The sole admitted question, `scope_cash_flow`, is:

> NAVER의 2023년 사업보고서에 있는 연결 현금흐름표와 별도 현금흐름표에서 2023사업연도 영업활동현금흐름을 각각 찾아 원문 금액과 단위 그대로 알려 줘.

The selected report remains NAVER 2023, 사업보고서, receipt `20240318000844`.
Its question, scope and two diagnostic flags exactly match the frozen input.
The original two numeric source witnesses and acceptance criteria are unchanged.
The dividend and unsupported-2024 questions remain outside this execution scope.

The future run uses the actual health/companies/query endpoints and native Chroma
with normal BM25/RRF retrieval on a verified disposable copy of the selected
store. The caller and admission helpers are byte-identical to the prior reviewed
engine. The native runner changes only its dedicated output directory; no
production source, model, output limit, retrieval policy or setting changes.

Review files and historical answers are barred from reads during the query.
Expected values are never inserted into prompts; normal retrieved source values
remain available to the Compiler. Each runtime-generated model request is counted
with the same input/schema before generation, following the
[official token-counting guide](https://developers.openai.com/api/docs/guides/token-counting).

## Offline evidence

The real application starts against a disposable store and accepts the exact
question through its API. Mock HTTP returns identical, nonzero embedding vectors
to create tied routing scores and exercise the existing LLM fallback. These
vectors and the generation rehearsal's count of 100 are deliberately synthetic;
they are not measured embeddings, input tokens or billing.

| Rehearsal | Mock HTTP attempts | Observed stop |
| --- | ---: | --- |
| Routing count A | 3 | Two embeddings, then injected count 503 |
| Routing count B | 3 | The same three request bodies and SDK bytes as A |
| Routing generation | 4 | Two embeddings, synthetic count, then injected generation 503 |

All three stop immediately with zero retries, persist sanitized diagnostics, and
produce no final-answer artifact. The app returns HTTP 500 while preserving the
upstream 503 in diagnostics. Unknown generation usage retains the full simulated
reservation as accounted cost; outstanding reservation becomes zero. These
simulated amounts are never added to the real experiment ledger.

The scope ends at the first routing request: **no Planner, native search or
Compiler runs in these rehearsals**. A fresh paid plan, selected cells, semantic
accuracy and native-search variation remain unobserved for this question.
The existing unchanged caller's later-phase constraints retain their prior
evidence; no new question-specific success fixture is supplied.

The 62 tests cover the current budget boundary, exact draft and question/scope
binding, review-data exclusion, single-use dispatch, retry/endpoint restrictions,
count/generation pairing and persisted errors. Saved-evidence review additionally
checks helper derivation, repeated request bytes and preserved source identity.
A verification-only field-name mistake was corrected from saved receipts; the
application was not rerun for that correction and its contracts were unchanged.

## Funding and dispatch

[Official pricing](https://developers.openai.com/api/docs/pricing) was rechecked
on 2026-09-19. The proposal retains conservative per-million-token input/output
rates of **12.5/50 for Astra**, **2.5/12 for Terra**, and **0.13 for embeddings**.
Input ceilings use the published short-context cache-write rates. Four count
allowances of 0.01 remain an explicit contingency, not a verified endpoint tariff.

| Retained budget | USD |
| --- | ---: |
| Shared accounted / approved cap | 16.02259344 / 17 |
| Remaining, pending zero | 0.97740656 |
| Exact one-question envelope | 1.69972608 |
| Rounded one-question cap | 1.70 |
| Shortfall to rounded cap | 0.72259344 |
| Proposed cent-rounded increase, not applied | **0.73** |
| Available if that increase is accepted | 1.70740656 |

The ceiling permits at most two Terra and two Astra generations, four counts
and 48 embeddings, with unchanged full output limits and no Compiler repair.
It bounds estimated exposure; it does not guarantee completion or predict the
invoice. A plan requiring additional calls must stop instead of enlarging scope.

Whole-batch funding is checked before transport construction or application
bootstrap. A paid authorization must bind the exact new draft and unchanged
accounting. An exclusive consumption marker precedes transport creation; any
attempt consumes it. There is no SDK/HTTP/whole-query retry, provider fallback,
fresh ingest or automatic run of the two other questions.

The current balance fails the real draft entrypoint before any transport,
bootstrap, output or consumption. **No budget increase or paid execution has
been authorized.** The next action is the user's acceptance of additional
funding and this one question, after which the frozen attempt can execute once.

## Preservation and local artifacts

All **9743 predecessor files**, **174 source files**, seven runtime owners,
**24 original store files** and local settings retain their hashes. Only each
disposable copy's SQLite bytes changed during loading. Two documentation
authority checks pass; the working change is documentation only.

Local evidence: [question](../../benchmarks/results/scope_cash_flow_admission_2026-09-19/questions.json),
[draft](../../benchmarks/results/scope_cash_flow_admission_2026-09-19/draft_manifest.json),
[focused controls](../../benchmarks/results/scope_cash_flow_admission_2026-09-19/controls.json),
[saved-evidence review](../../benchmarks/results/scope_cash_flow_admission_2026-09-19/preparation_review.json),
[current-balance stop](../../benchmarks/results/scope_cash_flow_admission_2026-09-19/current_balance_stop.json),
[handoff](../../benchmarks/results/scope_cash_flow_admission_2026-09-19/handoff.json).
