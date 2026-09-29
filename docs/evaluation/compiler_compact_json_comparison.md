# Compiler compact-JSON comparison

The serialization-only candidate produced **zero whitespace characters outside
JSON strings** in both scheduled responses. Baseline responses contained 3,501
and 3,298 such characters. Both conditions completed **2/2 first responses**,
and all four samples passed the existing execution contracts and separate
four-criterion content review. Mean output usage fell from **2,135 to 1,858
tokens**, about **13%** in this small sample.

This supports compact serialization for this known input. It does not establish
better completion reliability: neither condition reproduced the earlier failure.
Independent wording and reasoning also changed, so the token difference cannot
be attributed entirely to whitespace. The production prompt remains unchanged.

## Frozen comparison

The user continued the concrete instruction-validation next step with standing
direction to proceed without repeated approval. A fresh four-response comparison
ran on clean `76b89b5c` inside the unchanged USD 14 shared cap, with a **1.70**
experiment cap. Manifest
`f3baae2ce4c062beee6df48250e11b90e66bbdba8cbaef52c93fee20e2f0f200`
was consumed once; it cannot authorize another run.

[Local packet](../../benchmarks/results/compiler_compact_json_comparison_2026-09-18/)
retains the manifest, raw requests/responses, semantic-review lock, source checks
and exact accounting. The baseline is the frozen first Compiler request from
the [Planner range application check](planner_section_range_app_check.md),
`wire/033_request.json`. Its old failed response is not counted as a new sample.
The question and four source-content criteria concern the same previously
reviewed NAVER 2023 search/display paragraph. No new Planner, retrieval,
embedding, application query or ingest occurs.

The candidate prefixes one 466-character instruction requesting a single JSON
object without optional whitespace outside strings. It explicitly retains every
required field, output, claim, qualification and evidence reference, forbids
shortening content, and preserves whitespace/punctuation inside exact quotations.
Every original prompt character and every non-input field remain equal.
Astra, medium reasoning, strict schema, `store=false`, default service tier and
the 5,120-output ceiling are identical. No feedback repair is allowed here.

The fixed order is baseline, candidate, candidate, baseline. Each response gets
an independent request with no conversation history. All four exact input counts
precede generation, and all full output ceilings are funded before dispatch.
First count/provider/incomplete/refusal/schema/identity/usage failure stops the
entire schedule, without retry, resume or replacement.

## Observations

| Scheduled sample | Input tokens | Output tokens, including reasoning | Reasoning tokens | Whitespace outside strings | Content criteria |
| --- | ---: | ---: | ---: | ---: | ---: |
| Baseline 1 | 11,315 | 2,123 | 94 | 3,501 | 4/4 |
| Candidate 1 | 11,398 | 1,865 | 199 | 0 | 4/4 |
| Candidate 2 | 11,398 | 1,851 | 225 | 0 | 4/4 |
| Baseline 2 | 11,315 | 2,147 | 181 | 3,298 | 4/4 |

All eight HTTP calls return 200; all four generations are completed, valid JSON
under the unchanged schema. No incomplete response, refusal, provider error,
repair, SDK retry or whole-query retry occurred. Trailing whitespace is zero
in every sample. Counts match reported generation input usage exactly.

All **16 output/claim objects** execute unchanged. **48 subject/fact support
occurrences** match their exact source-bundle and original paragraph spans,
including quoted whitespace. This is physical linkage, not semantic proof.
Separate assistant review confirms every sample retains search's role, product
improvement, category expansion and AI search advancement; display's role,
platform/performance/new-product improvements; and advertising effectiveness as
an effort, not an established measured outcome. The candidate's added statement
about continuing search growth explicitly attributes the supporting source.
No unsupported public claim or source/subject transfer was found.

Review projections omit condition, generation order, cost and structural verdicts.
The content assessment was locked before joining conditions and executing the
fresh payloads locally. The preparer knows the design and has access to the key;
this is not independent blinding, human gold or an unseen holdout. Public claim
text totals are 297/297 characters for baseline and 334/324 for candidate, so the
observed compactness is not evidence of shortened required answer content.

## Verification and accounting

Eleven batch controls and four packet tests pass, including two identical
eight-request SDK rehearsals, exact decimal cap boundaries, full reservation,
first/last 503 stops, incomplete/refusal/usage failures and credential-safe error
receipts. Six production-SDK replay cases preserve exact frozen request objects
and raw response text; incomplete status stays rejected. Six anonymous JSON
codec controls preserve strings. Thirty-seven existing count/transport/admission
contracts and four documentation checks pass with external connections blocked.
The first test command named a nonexistent module: 29 tests passed and one
loader error was retained; the corrected 37-test set passes. Post-run analysis
corrected a syntax typo and a synthetic whitespace-count expectation before any
comparison result was written; no provider call or raw evidence was repeated.

Saved-payload and fresh-payload Compiler replays each pass 4/4 without another
invocation. Current state reconstruction changes object key order in four JSON
prompt sections because stored records sort keys. Local comparison canonicalizes
only those JSON objects; arrays, string contents and all other prompt text remain
exact. Live requests use the frozen request objects directly. No literal original
HTTP-byte replay or freshly repeated full application is claimed.

The full ceiling at the 12,000-input limit is **1.664**; measured inputs reserve
**1.6318250** before generation. Usage estimate **0.9671250** plus **0.04** count
contingency adds **1.0071250**. Shared accounting becomes **12.69919659 / 14**,
remaining **1.30080341**, pending **0**; peak including reservations is
**13.32389659**. Historical failed-request reserves remain retained.
[Official pricing](https://developers.openai.com/api/docs/pricing#standard-pricing-data)
was checked on 2026-09-18; accounting conservatively retains 12.5 input / 50
output USD per million, with no cached-input discount. The 0.01/count provision
is a project contingency, not an observed tariff. These figures are not invoices.

All **6,841 predecessor files**, **388 sealed packet files**, **174 source files**,
**24 original store files** and local settings retain their hashes. Only documents
are committed; the packet stays local. No runtime, model, schema, output limit,
retry policy, default setting or original evidence changes.

The [earlier whitespace diagnosis](compiler_output_limit_diagnosis.md) and failed
draft retain their original conclusions. Two repeats of one known input cannot
establish rare-loop elimination or transfer to numeric/mixed requests. Next,
characterize the same instruction provider-free across numeric, mixed and exact
multiline-quotation fixtures before considering broader independent-source model
evidence. No further paid run or default promotion follows from this batch.

The subsequent [provider-free compatibility check](compiler_compact_json_compatibility.md)
covers numeric, mixed and multiline-quotation controls with the same instruction.
Its authored replies preserve execution and rejection boundaries; it adds no
model samples, measured savings or reliability evidence to the comparison above.
