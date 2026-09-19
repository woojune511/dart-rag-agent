# Native OpenAI application result

The authorized native application attempt on clean `29dedb3b` completed with
**HTTP 200, 2/2 complete outputs and ledger integrity ok**. All **27 real API
attempts** returned HTTP 200: four generations, four input-token counts and
19 embeddings. There was no API/parsing/runtime error, Compiler repair,
SDK retry, whole-query retry or provider fallback.

The user approved the [prepared execution plan](native_application_admission.md)
and an additional **USD 1**, raising the experiment cap from **16 to 17**.
Draft `79f4cb6c...5ffddd` was bound to that authorization and consumed once.
Whole-batch funding passed before client construction/bootstrap; models, full
output limits, input caps, native search and production settings stayed fixed.
This result uses a fresh plan, retrieval and model responses through the actual
ASGI health/companies/query endpoints, not the earlier dense or HTTP fixtures.

## Result and source review

The query asks for 2023 Commerce revenue growth and the impact of the Poshmark
acquisition. Both Compiler islands passed on their first response.

| Output | Observed result | Source review |
| --- | --- | --- |
| Growth calculation | 41.3957043439745%, displayed **41.4%** | 2023 revenue **2,546,648,516천원** and 2022 revenue **1,801,079,126천원**, with original table cells, full axes and period contexts preserved |
| Acquisition impact | **Two supported narrative claims** | Other Commerce growth drivers remain visible; Poshmark and subsidiaries' post-acquisition **473,849백만원 revenue / 19,063백만원 net loss** retain their own scope and period |

The numeric calculation uses `(target-reference)/reference*100`, independently
recomputed from the selected cells in original stored tables 308/309. It does
not substitute the source-stated percentage for the requested calculation.
The model supplied precision metadata that the user did not request; the
runtime displays 41.4%. This sample does not establish general format fidelity.

The first narrative claim cites the management discussion's Smart Store,
Brand Store and Poshmark restructuring explanation. It attributes that account
to the report and does not assign the full growth rate to acquisition alone.
The second retains the acquired company and subsidiaries' post-acquisition
consolidated results; it does not turn their loss into a Commerce-wide loss or
use the adjacent hypothetical full-year figures as actual results.

All **six subject/fact support occurrences** match their selected source spans
and original stored parent text or table payload. Four answer evidence IDs
resolve, citations include the selected source anchors, and ledger artifacts
retain those references. This is assistant review of a known source against
pre-frozen criteria, not independent human gold or unseen-question accuracy.

Native retrieval made **17 Chroma queries**, retaining 32 seeds and 521
candidates. The app finalized two completed tasks and five artifacts. Ready,
non-degraded storage reports 1,872 chunks and remains source-complete after the
query. The disposable copy's SQLite bytes changed during native loading; all
original storage bytes were preserved. This one sample does not resolve the
separate [native ANN variation](retrieval_seed_drift_diagnosis.md).

## Token and budget evidence

| Generation | Server-counted input = reported input | Output including reasoning |
| --- | ---: | ---: |
| Terra routing | 1,217 | 26 |
| Terra requirements | 12,836 | 1,569 |
| Astra numeric Compiler | 23,675 | 933 |
| Astra narrative Compiler | 23,437 | 1,270 |

All four final request bodies matched their count inputs and remained within
the prepared bounds. All four raw generated JSON texts contain zero whitespace
outside strings. The observed native run took about 104 seconds after admission.
Fresh planning and narrative choices differ from prior runs, so this is not an
isolated paired model/patch comparison or a causal token-savings measurement.

| Accounting | USD |
| --- | ---: |
| Generation and embedding estimate | 0.75386499 |
| Four count contingencies | 0.04 |
| This run accounted | **0.79386499** |
| Peak with reservations | 0.98636499 |
| Approved single-run cap | 1.70 |
| Shared total / cap | **16.02259344 / 17** |
| Remaining, pending zero | **0.97740656** |

Generation/embedding accounting uses the same conservative rates rechecked
against [official API pricing](https://developers.openai.com/api/docs/pricing).
The count contingency is the explicit experimental allowance, not an observed
endpoint tariff. These are estimates and retained accounting, not an invoice.

## Verification and handoff

**95 post-run evidence assertions** and **two documentation checks** pass.
The unchanged preparation's 58 tests and two native failure controls remain
valid prior evidence; they were not repeated as paid requests. The persisted
single-run diagnostic snapshot equals the API's diagnostic projection.

All **9635** predecessor files, **174** source files, seven runtime owners,
**24** original store files and local settings retain their hashes. There is
no production-code, default, ingest or source-store change. Historical paid
results, fixed-input fixtures and consumed admissions remain intact. The new
authorization and consumption records are appended alongside the frozen draft.

Local evidence: [live/source review](../../benchmarks/results/compiler_native_app_execution_2026-09-19/live_review.json),
[accounting](../../benchmarks/results/compiler_native_app_execution_2026-09-19/accounting.json),
[run receipt](../../benchmarks/results/compiler_native_app_2026-09-19/run_receipt.json),
[actual API result](../../benchmarks/results/compiler_native_app_2026-09-19/commerce_growth_acquisition/api_result.json).

This once-only task is complete. Next prepare a small independent-question
evaluation set and freeze its source/semantic acceptance criteria without
provider calls, then assess its budget separately. Do not automatically repeat
the consumed known-source question. General semantic accuracy, native-search
stability and presentation refinements remain separate validation questions.
