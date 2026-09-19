# Native application execution preparation

Provider-free preparation on `b09e1d35` is complete. The proposal is one fresh,
store-fixed full-application attempt with native Chroma retrieval and unchanged
OpenAI routes/settings. At preparation handoff it was **not funded or authorized**.
The subsequently approved +USD 1 and [native execution](native_application_result.md)
completed once with two source-reviewed outputs; the draft is now consumed.
The [fixed-retrieval replay](fixed_retrieval_app_replay.md) remains separate
offline integration evidence; its dense fixtures are not used by this proposal.

## Proposed execution

- One existing mixed numeric/narrative question through actual ASGI health,
  companies and query endpoints, using a verified disposable store copy.
- Normal native dense retrieval, BM25, hydration, RRF, candidate construction,
  Compiler validation, answer composition and ledger. Native HNSW variation
  remains unresolved; prior catalog cardinality or response hashes are not
  acceptance requirements for a fresh model request.
- Terra routing/requirements: two generations, low effort, 8192 output tokens.
  Astra Compiler: two first responses for disjoint owners, medium effort,
  5120 output tokens. At most four runtime-generated token counts, four
  generations and 48 embeddings; 30,000 input tokens, 100,000 request bytes,
  8192 embedding input bound. `store=false`, standard tier, 90-second deadline.
- Whole-batch funding and exact source/draft/authorization identity checks
  precede single-use consumption, HTTP client construction and app bootstrap.
  The exclusive consumption marker is written before any possible transmission.
- No SDK/HTTP/whole-query retry, Compiler feedback repair, provider fallback,
  Google call, fresh ingest or original-store write. Diagnostics persist on
  failure; unknown generation usage retains its full reserve in accounting.
  Thirty-second progress heartbeat and safe error/status receipts are enabled.
- Review numeric operands, periods, units, intent, formula, narrative scope,
  source support and requested-theme completeness outside the provider prompts.
  Ledger/source linkage alone does not establish semantic correctness.

The draft and runner are experiment-local. Creating the draft does not create
`authorization.json`, consume a manifest, launch an application or alter a cap.
A later authorization must bind the final draft hash and unchanged shared
accounting. Exact Git/runtime/source drift requires a fresh review before use.

## Budget

| Item | USD |
| --- | ---: |
| Current shared cap | 16.00 |
| Accounted, including retained historical reservations | 15.22872845 |
| Available, pending zero | 0.77127155 |
| Proposed complete bounded envelope | 1.69972608 |
| Rounded single-run cap | 1.70 |
| Shortfall to rounded cap | 0.92872845 |
| Recommended additional allowance, not approved | 1.00 |

The envelope includes 1.608608 for generation, 0.05111808 for embeddings and
0.04 in count contingency. Published standard short-context prices were checked
on 2026-09-19; reservations use the highest ordinary/cache-write input rate,
without assuming cache discounts. The count contingency is experimental, not
an observed tariff, and accounting is not an invoice. Sources: [API pricing](https://developers.openai.com/api/docs/pricing),
[token counting](https://developers.openai.com/api/docs/guides/token-counting).

The current balance stops execution before bootstrap. A simulated +1.00 leaves
1.77127155 available and admits the proposed 1.70 cap; this simulation changes
neither the shared cap nor execution authority. Funding does not guarantee a
complete or semantically correct answer.

## Provider-free verification

**58 tests pass**: 14 new admission/transport controls and 44 existing provider,
token-count, runtime-admission and diagnostics contracts. They cover unfunded
and unauthorized runs, changed identity/accounting, single-use consumption,
endpoint/redirect constraints, 503 dispatch, owner retry rejection and retained
failure accounting. **20 evidence assertions** and **2 documentation checks**
also pass.

Two fresh app processes each execute **17 native Chroma queries** with normal
retrieval and an exact historical HTTP prefix, then receive one injected 503:

| Injected failure | Mock HTTP attempts | Count/generation/embedding attempts | Result |
| --- | ---: | --- | --- |
| First Compiler input count | 24 | 3 / 2 / 19 | Terminal `provider_token_count_failed`; no Compiler generation |
| First Compiler generation | 25 | 3 / 3 / 19 | Terminal `provider_request_failed`; 0.5518 simulated unknown-usage reserve retained |

Both return application HTTP 500 while retaining provider HTTP 503 in the safe
diagnostics; neither retries, continues to the next Compiler owner or emits a
final answer. Each retains the simulated 0.03 count contingency. These are
deliberately injected failures, not current provider incidents or new charges.
No dense result fixture is installed. Original storage remains untouched.

Two local verifier assumptions were corrected without changing production
source or tests: global log suppression initially broke three `assertLogs`
checks; the failed-generation reserve is accounted as unknown-usage estimated
cost rather than pending. Its saved evidence was reviewed without rerunning
the app. The generation run's blocked-socket-attempt counter was not persisted;
external sockets were denied and the provider transport was mock-only.

All **9531** predecessor files, **174** source files, seven runtime owners,
**24** original store files and local settings retain their hashes. New paid
calls/cost are **0**; no authorization or consumption marker exists. This is
execution preparation and failure-boundary evidence, not a live full-app pass,
native-search stability result, unseen accuracy measurement or release claim.

Local evidence: [preparation review](../../benchmarks/results/compiler_native_app_preparation_2026-09-19/preparation_review.json),
[58 controls](../../benchmarks/results/compiler_native_app_preparation_2026-09-19/controls_green.json),
[draft manifest](../../benchmarks/results/compiler_native_app_preparation_2026-09-19/draft_manifest.json),
[native review criteria](../../benchmarks/results/compiler_native_app_preparation_2026-09-19/native_review_criteria.json).

The [authorized follow-up](native_application_result.md) completed this attempt
and its source review after the user approved +USD 1. The above preparation
and mock evidence remain unchanged; the separately appended authorization
and consumption records permit no further paid run.
