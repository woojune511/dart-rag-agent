# Unsupported 2024 actual: live result

The one-question run on clean `0a77fcdd` completed with **HTTP 200**, preserving
the requested full-year 2024 period and returning no fabricated amount.
The sampled abstention is appropriate, but **full frozen acceptance is withheld**:
the final answer omits the explanation tying the evidence limit to the selected
2023 report. This is a completed diagnostic with a partial semantic outcome,
not a provider failure, full answer-quality pass or release result.

The user accepted continuation under existing funds. Fresh draft
`c10838014d3d1453efa9179e705439ed8ef7e82276557d4c799581ff0fa7cc37`
was consumed once at the [prepared USD 1.06 cap](unavailable_2024_admission.md),
with **no budget increase, retry, feedback repair or fresh ingest**.

## Answer and separate review boundaries

The unchanged question requests actual 2024-01-01 through 2024-12-31 consolidated
operating cash flow using only NAVER's selected 2023 annual report,
receipt `20240318000844`. The delivered answer is:

> 필요한 근거를 충분히 확인하지 못했습니다: 2024년 연결 영업활동현금흐름

| Boundary | Observed result |
| --- | --- |
| Runtime | HTTP 200; structured result `incomplete`; one missing obligation; ledger integrity `ok`, no issues |
| Planner interpretation | One direct-value output retains the exact 2024 full-year range, actual basis, consolidated scope and both original request units; no guessed display unit |
| Retrieval | Eight native ANN searches, 32 seed and eight final documents, all from the selected 2023 filing; 696 candidates |
| Source authority | The original 2023 cash-flow cell is present in the catalog and excluded from the Compiler's visible set; no year relabeling |
| Compiler decision | Two unresolved-period change cells are visible; one first response explicitly chooses `missing`, with no value or selected binding |
| Delivered explanation | Insufficient-evidence wording is present, but the selected-report/full-year mismatch is not explained; frozen semantic acceptance remains **partial** |

The original consolidated cash-flow witness, cell `47:0:1`, still contains
**2,002,233,273,518원** with its attached 2023 period context. It was retrieved
into the catalog but not exposed as an eligible 2024 amount. The two exposed
cells instead describe changes in intangible assets and total liabilities in
the management discussion table. Their row/cell values, full axes, document
identity and three attached contexts match the original stored table exactly.
The sampled Compiler declines to substitute them for operating cash flow.

The model's diagnostic rationale correctly limits its conclusion to the provided
excerpts. That diagnostic is not counted as the delivered explanation. Existing
rendering uses the generic missing-evidence template plus the obligation label;
it does not carry the selected-report/full-year limitation into the answer.
Eight public citations list retrieved 2023-report documents, with no accepted
value binding. They are retrieval anchors, not proof of document-wide absence.

This review uses the unchanged [pre-run criteria](independent_question_criteria.md).
It separately accepts the sampled decision to withhold an unsupported number
and withholds full acceptance of the final explanation. It is assistant review
of known sources, not independent human gold or a keyword-based semantic score.
No exhaustive corpus-absence or real-world zero-value claim is established.
The earlier blank-Planner-period boundary remains; this successful period
interpretation in one sample does not fix or generalize across that boundary.

## Execution and accounting

All **16/16 external requests** returned HTTP 200: two Terra generations, one
Astra generation, three input counts and ten embedding requests. The actual
compilation plan contained one complete group, admitted once under the full
configured ceilings. JSON parsing and contract validation errors were zero.
The saved validator status is `invalid` because no requested output is supplied,
with **zero validation errors**; it is not a malformed response or transport error.

| Actual generation | Input tokens | Output tokens | SDK request bytes |
| --- | ---: | ---: | ---: |
| Routing / Terra | 1,239 | 27 | 3,621 |
| Planner / Terra | 20,412 | 538 | 76,278 |
| Compiler / Astra | 7,786 | 320 | 32,737 |

Each server input count equals actual generation input usage; all three returned
compact JSON without whitespace outside strings. Embedding input totals 2,616
tokens. The complete query took approximately 46 seconds and the runner finished
its integrity checks in approximately 53 seconds; this is one observation.

| Experimental accounting | USD |
| --- | ---: |
| Conservative generation/embedding estimate | 0.17457258 |
| Separate count contingency | 0.03000000 |
| Added accounted amount | **0.20457258** |
| Shared accounted / unchanged cap | **18.74967693 / 20.07** |
| Remaining / pending | **1.32032307 / 0** |
| Peak run accounting with reservation / run cap | **0.44457258 / 1.06** |

These use the frozen conservative rates checked against
[official pricing](https://developers.openai.com/api/docs/pricing) on 2026-09-21.
The count contingency is not an observed endpoint charge. This is experimental
accounting, not an invoice or an account-credit balance.

## Preservation and next work

**70 saved-evidence assertions** pass with external connections blocked during
review, including exact output revalidation, source links and independent Decimal
accounting. All **10,996 predecessor artifacts**, **175 source files**, seven
protected owners, **24 original store files** and local settings retain hashes.
Only the disposable copy's SQLite file changed. The prior 53 admission controls
and 67 preparation assertions remain separate evidence and were not rerun.

Next characterize the missing-evidence answer contract without provider calls:
how to express the selected-source and requested-period limits from structured
request/source facts, and how to distinguish retrieved material from evidence
supporting an answer. Keep raw diagnostic rationale internal; do not paste it
into the answer, add a case-specific template, infer report-wide absence, or
change source eligibility to improve this case's score. Preserve the sampled
run as partial. No additional paid run, consumed-draft resume or ingest follows
automatically from this result.

Local evidence: [70-check review](../../benchmarks/results/unavailable_2024_execution_2026-09-21/live_review.json),
[source/semantic review](../../benchmarks/results/unavailable_2024_execution_2026-09-21/source_review.json),
[accounting](../../benchmarks/results/unavailable_2024_execution_2026-09-21/accounting.json),
[API answer](../../benchmarks/results/unavailable_2024_app_2026-09-21/unavailable_2024_actual/api_result.json),
[HTTP receipts](../../benchmarks/results/unavailable_2024_app_2026-09-21/http_receipts.json),
[handoff](../../benchmarks/results/unavailable_2024_execution_2026-09-21/handoff.json).
