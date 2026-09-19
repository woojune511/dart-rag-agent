# Cash-flow result after table-heading exposure

The authorized successor on clean `41841917` completes the frozen cash-flow
question with **2/2 outputs accepted** by assistant source review. The actual app
returns HTTP 200 / `ok`, ledger integrity is `ok`, and all **17 API attempts**
succeed. Both Compiler first responses validate without repair or retry.
This is one known-source result; it does not establish general accuracy, native
ANN stability or an isolated causal effect of the input correction.

| Requested 2023 operating cash flow | Returned original amount | Verified source |
| --- | ---: | --- |
| Consolidated | **2,002,233,273,518원** | 연결 현금흐름표, cell `47:0:1` |
| Separate | **1,627,845,864,966원** | 현금흐름표, cell `39:0:1` |

Both source tables retain the `영업활동현금흐름` row and `제 25 기` column.
Their respective attached contexts explicitly identify the period as
`2023.01.01 부터 2023.12.31 까지`. Original precision and 원 units remain unchanged,
with the correct consolidated/separate labels, exact physical cells and API
citations to the corresponding statement sections. No prior-year, subsidiary,
rounded management-summary or swapped-scope value is substituted.

## What this run establishes

The sole question, report scope, review criteria, model settings and full output
limits remain those of the [prepared admission](scope_cash_flow_heading_admission.md).
The user accepted **+USD 0.07 and one attempt**, raising the shared cap to **17.80**.
Draft `6b54767a...afb47be` was consumed once after source/hash/funding checks;
the single-run cap remained **1.70**. No other frozen question was executed.

The actual Planner request is byte-identical to the corrected SDK rehearsal:
**72,967 request bytes**, with all **52 existing section IDs**, unchanged
membership fingerprint and **24/85 located heading hints** occupying **16,070
bytes**. Both requested table titles and their existing parent IDs are visible.
This time the fresh Planner selects the corresponding consolidated and separate
parent sections. Both bindings preserve the complete original request and its
source-display intent; replay of the saved plan yields no restriction error.

Native Chroma makes **7 searches**, with **12 seed documents**, **8 final visible
documents** and **928 candidates**. Each selected source cell is visible to its
own Compiler call. The two first responses select the correct cells and exact
attached period contexts; deterministic linkage and execution checks are ready.
Separate assistant review checks requested meaning, full-statement scope, period,
labels, precision and citations against the frozen original source witnesses.
Physical linkage alone is not a semantic-accuracy proof.

Two tasks complete with five consistent artifacts and no missing obligations.
The public answer, structured result, source slots and final trace agree.
The [preceding paid result](scope_cash_flow_result.md) remains 0/2; this successor
does not rewrite that answer or turn the pair into a controlled A/B comparison.

## Calls, cost and preservation

All **17/17** requests return 200: **4 generations** (Terra routing/planning and
two Astra Compiler calls), **4 token counts** and **9 embeddings**. Each measured
input count equals its generation's reported input usage. All four output texts
are compact JSON. Planner input is **19,575 tokens**; request byte growth is not
a causal token-saving or cost-saving comparison.

| Accounting | USD |
| --- | ---: |
| Generation and embedding estimate | 0.43512445 |
| Four count contingencies | 0.04000000 |
| New accounted estimate | **0.47512445** |
| Peak with full reservations | 0.70347445 |
| Shared accounted / approved cap | **16.56583531 / 17.80** |
| Remaining, pending zero | **1.23416469** |

These are conservative usage estimates from the frozen rates, not an invoice;
the count contingency is not a verified tariff. No SDK, HTTP or whole-query
retry, feedback repair, provider fallback, context generation or fresh ingest
occurs. The original stores remain untouched; only disposable-copy SQLite bytes
change while loading the app. Readiness remains source-complete and non-degraded.

**92 saved-evidence checks** and **2 documentation checks** pass. All **9975
predecessor files**, **174 tracked sources**, seven runtime owners, **24 original
store files** and local settings retain their hashes. The prior 62 admission
controls and three failure rehearsals are reused through their frozen identities;
no unchanged runtime suite or paid experiment is rerun. Tracked edits are docs only.

## Next bounded step

The subsequently authorized [dividend-policy attempt](dividend_policy_result.md)
returned application HTTP 500 after a numeric payment-status binding failed;
all 23 external calls succeeded and a repair request was blocked locally.
Its partial policy/period claims are not a final answer. Current accounting
is 17.11707679/18.27, remaining 1.15292321, pending zero. The unsupported-2024
question remains unexecuted; consumed drafts cannot be reused. The
[Planner output-kind clarification](planner_output_kind_boundary.md) is now
tested locally, and the [exact quote-source correction](numeric_quote_source_boundary.md) now removes only the false quote rejection offline. Next prepare fresh provider-free application admission/rehearsal.

Local evidence: [source review](../../benchmarks/results/scope_cash_flow_heading_execution_2026-09-19/source_review.json),
[92-check review](../../benchmarks/results/scope_cash_flow_heading_execution_2026-09-19/live_review.json),
[accounting](../../benchmarks/results/scope_cash_flow_heading_execution_2026-09-19/accounting.json),
[actual response](../../benchmarks/results/scope_cash_flow_heading_app_2026-09-19/scope_cash_flow/api_result.json),
[HTTP receipts](../../benchmarks/results/scope_cash_flow_heading_app_2026-09-19/http_receipts.json),
[handoff](../../benchmarks/results/scope_cash_flow_heading_execution_2026-09-19/handoff.json).
