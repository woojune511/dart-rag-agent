# Compact JSON application smoke: stopped by the budget guard

On clean `2879db60`, one known-source mixed question reached the normal OpenAI
application through FastAPI lifespan/shared services and in-process ASGI HTTP.
The numeric Compiler program passed validation, but the following narrative
generation was denied before transmission. **No final mixed answer was delivered.**
This is partial application evidence, not a completed quality or release gate.

The question requests NAVER Commerce revenue growth for 2023 and Poshmark's
acquisition impact. It reuses a previously inspected question; no unseen claim.
Fresh planning and retrieval used a verified disposable copy of the selected
NAVER store. Health/companies returned HTTP 200, ready and non-degraded, with
1,872 chunks. No external listening server, fresh ingest or original-store write.

## Observed response and source review

- One raw numeric response is schema-valid compact JSON: **zero whitespace
  characters outside strings**, no reviewer minification, and no validation errors.
- Both Compiler requests contain the current exact compact prefix. The narrative
  request was counted but its generation was blocked, so compliance is unobserved.
- Selected original Commerce cells retain **2,546,648,516** and **1,801,079,126
  thousand KRW**, matching row/column axes and attached current/prior contexts.
  Assistant review supports 2023/2022, signed growth direction and calculation intent.
  Independent Decimal calculation gives **41.3957043439745% → 41.4%**. This checks
  the accepted program; it does not reconstruct an app answer or completed execution.
- No final answer, narrative claims, final citations, public result trace or ledger
  was produced. Those frozen acceptance criteria remain unverified. Original raw
  responses, interrupted diagnostics and the application's HTTP 500 are preserved.

The numeric response used **26,131 input / 996 output tokens**, including 191
reasoning tokens. Its conservative input estimate is USD 0.32663750 versus
0.04980000 for output: **86.77% of that Compiler estimate is input**. This run has
no paired baseline and does not measure token savings or isolated policy efficacy.

## Budget stop and accounting

Fresh manifest `9c86b2cf755faa0f4584e26100f2466f3406235b241677769b21cb0a0dc9b7a7`
was consumed once under the existing USD 15 shared ceiling. Its run allowance was
0.89380341. Admission was conditional per call, with unchanged full output limits;
whole-query worst-case completion was explicitly not guaranteed.

All **26 provider transmissions returned HTTP 200**: 19 embeddings, four input
counts, two Terra generations and one Astra generation. The second Astra input
measured **17,529 tokens**; input plus its unchanged **5,120-output** reservation
required **USD 0.47511250** against **0.42222155** available. The **0.05289095**
shortfall caused local `budget_reservation_exceeded`, mapped by the app to HTTP
500. There was no provider 503, second Astra generation, feedback repair, SDK/HTTP
retry, whole-query retry or resume. A new attempt would need a fresh admission;
the shortfall at this interrupted point is not a quote for rerunning the query.

Generation/embedding estimate **0.43158186** plus four count contingencies **0.04**
gives **0.47158186** added accounting. Shared total **14.57777845 / 15**; remaining
**0.42222155**, pending **0**. Peak admitted reservation was **0.66778186** within
the run cap. These are estimates, not an invoice. The USD 0.01 count allowance is
experimental, not a verified endpoint tariff. Standard rates, conservatively using
cache-write pricing for all input, follow [OpenAI pricing](https://developers.openai.com/api/docs/pricing);
requests use the [official input count method](https://developers.openai.com/api/docs/guides/token-counting).

## Controls, preservation and next step

Caller/transport controls **23/23** pass with zero external attempts/provider calls,
including actual-store app rehearsal, frozen question/phase binding, terminal
budget/provider failures and retry denial. Rehearsal replies/counts are authored,
not model-quality or affordability evidence. The initial local test invocation
omitted an evidence-label variable; its six fixture errors remain preserved. A
fresh labeled invocation passed without changing runtime contracts or the caller.

All **8,913 predecessor files**, **174 source files**, seven runtime owners,
**24 original store files** and local settings retain hashes. Runtime, models,
output ceilings, source quotations and the compact default remain unchanged.
Only documentation is committed; raw evidence stays local and immutable.

Next: inspect input payload size and repeated metadata **without provider calls**,
preserving exact sources, schema and semantic context. Compact output alone does
not address the observed input-dominated cost. Any later paid work needs a fresh
funded admission; this consumed request must not be resumed or automatically retried.

Local evidence: [accounting](../../benchmarks/results/compiler_compact_json_app_2026-09-18/analysis.json),
[source/format review](../../benchmarks/results/compiler_compact_json_app_2026-09-18/partial_source_and_format_review.json),
[original diagnostics](../../benchmarks/results/compiler_compact_json_app_2026-09-18/commerce_growth_acquisition/request_diagnostics.json),
and [admission controls](../../benchmarks/results/compiler_compact_json_app_admission_2026-09-18/controls_green.json).
