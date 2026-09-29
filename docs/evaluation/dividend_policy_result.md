# Dividend-policy application result

The single authorized attempt on clean `526965ca` **did not deliver a final
answer**. All **23 external API calls returned 200**, but the application's
payment-status binding failed validation. Its subsequent repair request was
blocked by the frozen caller before another count or generation; the application
returned **HTTP 500**. This was neither a provider outage nor monetary-cap exhaustion.

The user accepted **+USD 0.47** and exactly one attempt of the
[prepared dividend-policy question](dividend_policy_admission.md). The shared cap
became **18.27**, with an unchanged **1.70** run cap. Draft
`8e4db03c61ef3ede05afa841b8dafae376b42ebba6735224206bc41a67da22ee`
is consumed. No retry, fallback, runtime edit, fresh ingest or other-question
execution was performed.

## Observed failure boundary

The **72,014-byte** Planner SDK request equals the prepared rehearsal. Its fresh
plan preserves the whole request and selects the existing dividend section for
both outputs. It assigns policy/basis/period to a `narrative` obligation, but
payment completion to `direct_value`, with period `2023사업연도`.

Native Chroma executes **13 searches**, producing **3 seed / 3 visible documents**
and **66 candidates**. The relevant paragraph and pending-payment sentence are
present and visible to the Compiler. Missing retrieval is not the observed blocker.

| Stage | Observed result |
| --- | --- |
| Policy/period Compiler first response | Parsed and validated `ready`; two supported partial claims |
| Payment-status Compiler first response | Parsed, then invalid; selects the planned **1,190억원** as a numeric direct result |
| Internal repair preparation | `ob_002`, attempt 2 is recorded; no repair is sent to a provider |
| Caller boundary | Two Compiler calls already authorized; rejects the third before count/transport |
| Application | HTTP 500, persisted diagnostics, no final answer or final ledger |

The payment model's prose interpretation correctly recognizes future shareholder
approval and payment. However, it puts that meaning into interpretation metadata
around a monetary selection, not a valid status answer. Three exact validation
errors are reproduced from saved inputs without providers:

- `source_interpretation_quote_mismatch`: the emitted quote equals the visible
  bundle text, including its leading space; the selected candidate's separate
  `source_text` omits that space, so exact contiguous quotation fails.
- `candidate_scope_mismatch`: the selected amount has no resolved period,
  conflicting with the requested period.
- `source_assertion_candidate_not_selected`: the rejected direct binding leaves
  its amount assertion without a selected candidate.

The last error is downstream of the rejected binding. The caller's terminal
`BudgetStop/unapproved_runtime_request` records a local authorization limit;
its name does not establish dollar-budget exhaustion. The fifth token-count
request and third Compiler generation never reach transport.

## Source review and limits

Five frozen witnesses still match their unique original parent/node spans.
The first island's two partial claims retain the approximate **15–30% of two-year
average consolidated FCF**, business/debt-repayment considerations, the optional
source FCF definition, and **three fiscal years including 2022**, subject to
business/market conditions and board decisions. Six exact support occurrences
link those claims and their subject to the original dividend paragraph.

These are **partial internal drafts**, not delivered answers. The required
payment-status meaning has no valid output. Full frozen acceptance fails;
there is no completed three-meaning result or successful abstention. This assistant
review of known sources is not independent human gold or general accuracy evidence.

## Accounting and preservation

| Accounting | USD |
| --- | ---: |
| Generation and embedding estimate | 0.51124148 |
| Four count contingencies | 0.04 |
| Added accounted estimate | **0.55124148** |
| Peak including reservations | 0.78169148 |
| Shared accounted / approved cap | **17.11707679 / 18.27** |
| Remaining | **1.15292321** |
| Pending | 0 |

There were four generations, four counts and fifteen embeddings, including
bootstrap. All generation input counts match response usage; all four response
texts are compact JSON. Accounting retains the prepared conservative rates and
count contingency; it is not an invoice or a verified count-endpoint tariff.

**113 saved-evidence checks** and **two documentation checks** pass. An offline
review initially mistook persisted canonical candidate IDs for wire aliases;
the review was corrected from saved records without repeating the application.
All **10132 predecessor files**, **174 source files**, seven runtime owners,
**24 original store files** and settings are unchanged. Only the disposable
copy's SQLite bytes changed during loading. Experiment artifacts remain local.

The [generic Planner output-kind contract](planner_output_kind_boundary.md) is
now clarified and tested provider-free. A separate successor below observes
new classification; this original failure remains unchanged. The separate
[exact quote-source correction](numeric_quote_source_boundary.md) removes only
the false quote error in offline replay; period rejection and the old monetary
selection remain. The [paid successor](dividend_policy_successor_result.md)
correctly plans three narratives but its two-response caller blocks the third
first request. All 24 provider requests succeed; no final answer is delivered.
That separately consumed result does not repair this historical failure.
The unsupported-2024 question remains unexecuted; this consumed draft authorizes
no additional paid run.

Local evidence: [source review](../../benchmarks/results/dividend_policy_execution_2026-09-19/source_review.json),
[failure analysis](../../benchmarks/results/dividend_policy_execution_2026-09-19/failure_analysis.json),
[113-check review](../../benchmarks/results/dividend_policy_execution_2026-09-19/live_review.json),
[accounting](../../benchmarks/results/dividend_policy_execution_2026-09-19/accounting.json),
[API result](../../benchmarks/results/dividend_policy_app_2026-09-19/dividend_policy_status/api_result.json),
[request diagnostics](../../benchmarks/results/dividend_policy_app_2026-09-19/dividend_policy_status/request_diagnostics.json),
[HTTP receipts](../../benchmarks/results/dividend_policy_app_2026-09-19/http_receipts.json),
[handoff](../../benchmarks/results/dividend_policy_execution_2026-09-19/handoff.json).
