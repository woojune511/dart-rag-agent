# Known-source narrative comparison: provider-stopped attempt

A later [fresh diagnostic pair](narrative_long_pair_diagnostic.md) completes both
responses and records a sample-level semantic difference. It does not change this
consumed failure, reconstruct its missing metadata or repair the historical answer.

A later [local diagnostic improvement](openai_error_diagnostics.md) prepares
safer metadata capture for a successor. It makes no new call and cannot recover
this attempt's missing error details. The incomplete result below is unchanged.

Attempted 2026-09-18 on clean `a28cc398`. Both input counts succeed and the
complete pair fits its budget, but the first generation returns **HTTP 503**.
**No new model answer is available; the old/new comparison remains incomplete.**
The preceding short-source tie and historical application fidelity concern remain.

## Fixed scope and observed outcome

The user continued the planned comparison on the already frozen longer NAVER
search/display input. The shared cap remains **USD 9**; this attempt is capped
at **1** within the verified **1.17860996** remainder. No cap increase occurs.
Fresh manifest
`a804af9943fb9d2a0944d758cee86a01f84e9594f62802d45b68ccdfd70b3c4b`
was consumed once. It authorizes no retry, resume or additional call.

Both complete Compiler requests preserve the same source/catalog, plan, schema
and Astra/medium/Standard/5120/`store=false` settings. Only the reviewed narrative
instruction differs. The four existing source criteria and the product-improvement
versus category-expansion review remain outside model input. No live routing,
retrieval, Planner, embedding, ingest or full application run was attempted.

| Arm | Input count | Count response | Generation outcome | New answer |
| --- | ---: | --- | --- | --- |
| Existing instructions | 8555 | HTTP 200 | HTTP 503, usage unavailable | None |
| Adopted instructions | 8656 | HTTP 200 | Not attempted after failure | None |

The first generation is admitted only after both counts and a full pair reserve
of **0.7471375**, below the caller cap of 1. Three transmissions occur in about
four seconds. The SDK reports `InternalServerError`; the budget closes with
`provider_request_failed`. There are **zero SDK retries, repairs or whole-run
retries**, and zero sampled responses reach schema or runtime validation.

This is a provider generation failure after successful counting and admission,
not evidence of a local compilation failure or an efficacy result. The underlying
provider cause is not established beyond HTTP 503. Historical saved-response
rehearsals cannot substitute for missing new samples. Neither arm receives a
semantic pass/fail score, and no runtime-policy change follows this attempt.

## Conservative accounting and preservation

The failed generation returns no usage, so its entire **0.3629375** reservation
is retained. Adding **0.02** count contingency accounts **0.3829375**. The unsent
adopted generation's **0.3642** reserve is released. Shared accounting becomes
**8.20432754 / 9**, remaining **0.79567246**, pending **0**.
These are retained reserves, **not measured consumption or an invoice**; the count
tariff and actual failure charge remain unobserved. Pinned conservative input/output
rates stay 12.5/50 per million, verified against the
[official Standard pricing table](https://developers.openai.com/api/docs/pricing#standard-pricing-data).

The caller is byte-identical to the preceding verified runner. Its **7/7** controls
pass with the longer request/schema, including failed generation, no retry,
reservation retention and stopping before the other arm. Two identical mocked
SDK runs and two untouched historical-response Compiler replays preserve exact
first prompts/schemas and pass source/execution checks. All four source witnesses
match the frozen and selected current store node and are visible in the catalog.
These are local compatibility checks, not fresh answer-quality evidence.

Documentation checks **4/4** pass. All **173** source files, **2488** protected
predecessor artifacts, **149** sealed preparation files, **24** store files and
local settings retain hashes. Prior budget **27/27**, full **2029/2029** and
domain audit **83** remain unchanged-source evidence and were not rerun.
Only documentation is committed; the
[local attempt packet](../../benchmarks/results/narrative_long_pair_2026-09-18/)
retains both measurements, the attempted request, safe HTTP failure record,
consumed manifest and conservative accounting.

Next continuation: a fresh single-use pair on these same frozen inputs, capped
at the remaining **0.79567246**, with no model/output change or cap increase.
The measured reservation from this attempt would fit with **0.04853496** margin,
but a new attempt must establish both complete reserves before either generation.
Do not resume this manifest or run only the previously unsent arm. If the same
failure recurs, reclassify the provider condition instead of repeating unchanged
attempts. No additional paid attempt is made in this turn.
