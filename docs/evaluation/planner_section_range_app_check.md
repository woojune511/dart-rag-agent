# Planner request-range application check

On clean `5f68bff4`, the ordinary OpenAI application completed the same NAVER
2023 search/display question with **4/4 runtime outputs** and ledger integrity
`ok`. Assistant review of the final public answer passes the **four unchanged
content criteria**, with **12 exact subject/fact support occurrences** checked
separately. This is one known-source regression check, not an independent
holdout, isolated patch comparison or general answer-quality claim.

## Scope and preserved evidence

The user continued the concrete next step after the
[Planner range contract](planner_section_request_ranges.md). Fresh manifest
`280f7bd612febaaf7e0d66444cc6f13cd6222c024a40e36ac50d41668538c957`
was consumed once under **USD 1.50**, inside the unchanged shared remainder
**3.08061745**. No cap increase, runtime/model/profile change, fresh ingest,
SDK/transport/whole-query retry or consumed-manifest reuse occurred.

The real FastAPI lifespan, shared services and `/api/query` ran through ASGI
using a verified disposable copy of the existing 1,872-chunk NAVER 2023 store.
No external listening server was started. Original settings, all **174** source
files, **24** protected store files and **6,684** predecessor artifacts retain
their hashes. Evaluation criteria and historical answers were unavailable to
the running query. Google clients/calls and ingest-context calls were zero.

Local packets: [admission](../../benchmarks/results/planner_section_range_app_admission_2026-09-18/),
[raw run](../../benchmarks/results/planner_section_range_app_2026-09-18/),
[offline review](../../benchmarks/results/planner_section_range_app_review_2026-09-18/).
These ignored artifacts remain separate from the documentation commit.

## Request, retrieval and final answer

The fresh Planner creates four required outputs: search role, display role,
search improvement and display improvement. Each selects owned
`request_001` through `request_003`, resolving the requested
`II. 사업의 내용 > 2. 주요 제품 및 서비스` section. Code copies the original
91-character range, including punctuation and whitespace. All four range
bindings pass; no quote repair or authored plan enters the live run.

One source node is eligible, retrieved and retained as seed evidence; three
candidates reach both Compiler attempts. The selected original source is
`20240318000844:21:0`. One shared-basis declaration and all four member references
are valid. These are request/source/execution checks, not semantic judgments.

| Frozen criterion | Final public content | Assistant review |
| --- | --- | --- |
| Search role | User information-search demand connected through NAVER to promote business activity | Pass |
| Display role | Advertiser commercial messages exposed to users through offered products | Pass |
| Search improvement | Product improvement, category expansion and AI search advancement kept distinct | Pass |
| Display improvement | Platform advancement, performance advertising, video/premium and other new products; advertising-effect improvement described as an effort | Pass |

All four public claims were reviewed, including additions and attribution.
No unsupported product-expansion paraphrase, business substitution, invented
quantity or advertising charge model was observed. The answer remains four
concatenated sentences rather than a comparison table; the improvement clauses
identify search and display. Exact support spans, source body and bundle
context match the unchanged graph and frozen source witness. Link validity
does not itself establish the semantic decisions in the table.

## HTTP success includes one incomplete generation

All **36 HTTP requests return 200**: 28 embeddings, four input counts and four
generations. Routing and requirements use Terra; compilation uses Astra.
The application returns HTTP 200 / structured `ok` after about 136 seconds;
the caller finishes integrity checks after about 139 seconds.

| Generation | Counted/observed input | Output | Provider result |
| --- | ---: | ---: | --- |
| Routing | 1,251 | 96 | Completed |
| Requirements | 16,079 | 2,277 | Completed |
| Compiler first draft | 11,319 | 5,120 | Incomplete: `max_output_tokens` |
| Compiler feedback repair | 12,330 | 2,176 | Completed |

The first draft spends 162 reasoning tokens within its 5,120 output tokens.
The application rejects it as unavailable and records schema errors for all
four owners; it is not parsed or graded as a successful answer. The existing
single validation-feedback repair succeeds with the same candidate identities,
candidate payload size, output schema and 5,120 ceiling. Final validation has
no errors. This is a repaired completion, **not an error-free first attempt**.
There was no HTTP error, timeout, budget stop or unhandled run exception.

The final completed answer is the semantic-review target. The incomplete draft
stays visible in reliability evidence and is not counted as a semantic pass.
Fresh planning also changes the earlier two-output grouping to four outputs,
so this run cannot isolate the range-contract effect. The
[preceding incomplete result](dart_narrative_pipeline_check.md) and older
[paraphrase concern](search_display_current_app.md) retain their original claims.

## Accounting and checks

The [official pricing table](https://developers.openai.com/api/docs/pricing#standard-pricing-data)
was rechecked before dispatch. Conservative cache-write input rates, full
configured output reservations and the existing count contingency were retained.
Each measured full generation input matches the later usage receipt.

Usage estimate **0.73268904** plus count contingency **0.04** adds
**0.77268904**; peak with reservations is approximately **0.91988904**, below
the 1.50 experiment cap. Shared accounting becomes **11.69207159 / 14**,
remaining **2.30792841**, pending **0**. Earlier failed-request reserves remain
retained. This is conservative accounting, not an invoice or observed count tariff.

Before dispatch, **87 provider-free checks** pass: 24 caller/transport controls,
one independent actual-store repeat and 62 provider/diagnostic/range contracts.
Two actual-store mock rehearsals preserve nine identical SDK requests. Those
authored responses are not quality evidence. The unchanged runtime retains its
previous **160 focused / 2,058 full-suite** pass; those suites were not rerun here.
Documentation checks pass **4/4**, with no external calls during review/testing.

The subsequent [provider-free diagnosis](compiler_output_limit_diagnosis.md)
finds 32,342 trailing whitespace characters after an unfinished first output,
not evidence that the complete answer requires a larger ceiling. Exact SDK
replay preserves rejection of the incomplete response. The upstream generation
cause remains unknown; this historical paid result and its accounting are unchanged.
