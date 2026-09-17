# Provider admission contract

This is the experiment-only extension of the [runtime contract](../architecture/agent_runtime_contract.md#10-validation-and-release-gate).
Default runtime behavior and policies without this option are unchanged.

## Server-count input reservation

`google_input_counting="server_count_tokens_v1"` explicitly enables one full-request
`countTokens` call before each admitted generation. The policy must also supply
`max_google_count_calls` and a positive finite `google_count_allowance_usd_per_call`;
these calls and the allowance require successor-manifest approval, not an old
generation-only approval. Runtime defaults do not install this guard.

- `src.ops.google_server_token_count` intercepts the installed SDK's final Developer
  API text body, after schema/system conversion and `extra_body`. It copies that
  body into `generateContentRequest` plus the model; the frozen generation input
  is otherwise unchanged. Shared canonical body hashes link count and generation
  receipts; they are not literal HTTP byte lengths. Headers remain memory-only.
- A positive integer server total replaces the byte-plus-overhead input estimate.
  Output reservation remains **4096 + 1024 = 5120**; existing rates and the long-input
  tier still apply. No schema omission, local tokenizer, byte ratio, framing
  correction, provider fallback, SDK retry, redirect, stream or async generation.
  The private SDK seam has real-SDK/HTTP-stub regression tests; it is not a public
  SDK compatibility guarantee or support for tools, caches, media or Vertex AI.
- Before counting, check closed state, generation/count limits and the minimum
  output reservation plus count allowance. After counting, check the full shared
  budget again. Every attempted count retains its allowance, including failure;
  it is separately reported, not added to observed generation usage or called a
  billed expense. The cap covers usage estimates, pending reservations and count
  allowances; actual count tariffs/invoices remain unobserved.
- Count errors or invalid totals stop before generation with
  `provider_token_count_failed`, without falling back to a byte estimate. Unknown
  generation usage retains its reservation; usage above either bound closes the
  run and the response is not returned as an accepted result. Already-in-flight
  calls still settle. This detects discrepancy, not a guarantee against a
  provider exceeding its count or an invoice exceeding the accounting estimate.

Verification: `tests/test_server_count_admission.py` uses anonymous text/schema inputs, actual LangChain/genai serialization and mocked HTTP with external sockets blocked. No count total is fabricated during no-call rehearsal; local success is not paid-provider or financial-answer correctness.

## OpenAI Responses successor

`src.ops.openai_provider_admission` adds an opt-in synchronous text-only Responses
guard. A policy must explicitly allow `openai_response`, its call limit, fixed
settings, rates and short-context input reservation; legacy policies do not gain
generation permission. Exact ordered rehearsal hashes bind the final SDK bodies.
Only `https://api.openai.com/v1/responses` is admitted; tools, extra endpoints,
streaming, async, SDK retries, redirects and altered bodies are rejected locally.
This is a separately approved successor, never reuse of a Google admission.

The input reservation is canonical UTF-8 body bytes plus an explicit allowance,
not server counting. Output usage already includes reasoning. Failed/unknown
usage retains its reservation; an overrun closes the guard and cannot return an
accepted response. Cache-write upper pricing may conservatively account for all
input. Detailed errors, keys and headers are not included in receipts.
The private SDK request seam is exercised with real serialization and mocked HTTP.
The [six-case migration packet](openai_compiler_probe.md) records its approved
settings and six successful first responses; runtime defaults install no guard.

## OpenAI in a fresh full-agent run

`guarded_runtime_openai_responses` is a separate opt-in for inputs produced by a
fresh planner/retrieval run. It requires `openai_response_binding="runtime_generated_v1"`,
an explicit Responses call limit, and a caller-owned request authorizer bound to
the approved question and active Compiler invocation. It shares the enclosing
`guarded_providers` budget, including Google count allowances and query embeddings.
No initial body-hash equality is claimed for future model-generated plans; the
fixed-input ordered-hash guard above retains its unchanged contract.

Only the official synchronous Responses endpoint, fixed strict-output settings,
zero SDK retries and bounded UTF-8 input reservations are admitted. Other OpenAI
transport is denied except an embedding already inside this same budget's admitted
dispatch. The context-local dispatch marker is reset even on failure. Unknown
usage retains reservations and closes subsequent work; provider diagnostics remain
credential-safe. Caller validation sees a copy and cannot rewrite the SDK body.

The [three-question successor](../../benchmarks/results/openai_compiler_full_agent_admission_2026-09-16/)
uses verified copies of existing stores, fresh routing/planning/retrieval and
OpenAI only for Compiler. Runtime repair remains at most one per island, under
the explicit call and cost caps. Source criteria and old answers are excluded
from live reads. New manifest/cost approval is required before any provider work.

## OpenAI input-token-count extension

`src.ops.openai_server_token_count.guarded_counted_runtime_openai_responses` is a
separate opt-in context for a caller-authorized runtime question/phase. It requires
`openai_response_binding="runtime_generated_v1"`,
`openai_input_counting="responses_input_tokens_v1"`, explicit
`max_openai_response_calls`, `max_openai_count_calls`, positive finite
`openai_count_allowance_usd_per_call`, `max_openai_request_bytes`, and a positive
`max_openai_input_tokens` no greater than 200000. Fixed `request_settings` or
`request_settings_by_model` and reviewed rates still govern each generation.
This API does not authorize a run, install itself in the application, or supply
a default count price. Policies without counting retain their existing behavior.

- Freeze the final SDK request after conversion, `extra_body` and SDK preparation.
  The count body preserves the complete `model`, `input`, `instructions`,
  `reasoning` and `text` schema fields that are present. Only generation controls
  absent from the count API are omitted: `max_output_tokens`, `store`,
  `service_tier`, `stream`. Unknown top-level fields, external state, tools,
  media and non-text inputs are rejected. Numeric source/proof semantics do not change.
- Use the installed SDK's `responses.input_tokens.count` resource, verifying its
  final body against the frozen projection before sending. A matching
  `object="response.input_tokens"` and positive integer total are required. The
  count method is `responses_input_tokens_v1`; hashes and the shared count index
  connect each count receipt to its generation. Canonical hashes are not literal
  HTTP byte-length or semantic-equivalence claims.
- Build each generation once and use that request after counting. Cached SDK raw
  wrappers use the same `SyncAPIClient.request` authorization boundary as new clients.
  A caller receives a deep copy for approval and cannot rewrite the frozen request.
  Count/generation pairs serialize on the shared budget. HTTP hooks/custom auth,
  redirects, streaming, async and retries are outside this narrow private-SDK path.
  An embedding still requires the enclosing shared provider guard; other endpoints
  and unscoped direct counts fail before transmission.
- Check known generation/count limits and output cost plus the count allowance
  before counting. Recheck the full measured-input/output reservation afterwards.
  The original full `max_output_tokens` bound remains in force, including reasoning;
  no byte ratio, local-tokenizer correction or output-bound reduction is applied.
  Each attempted count retains its separate allowance, including failure. Google
  and OpenAI have independent count limits while allowances share the same cap.
- Invalid/failed counts stop before generation without fallback. Measured input
  above the explicit limit also stops. Unknown generation usage keeps the reserve;
  actual usage above a bound closes subsequent work and the response is not returned
  as accepted. These controls detect discrepancies; they do not guarantee that a
  provider or bill never exceeds its estimate. Receipts omit credentials and
  arbitrary provider error text. The legacy `openai_request_parameters` cannot
  fabricate a counted generation reservation from a no-call descriptor.

The official [token-counting guide](https://developers.openai.com/api/docs/guides/token-counting)
documents the endpoint and inclusion of schema/formatting tokens. Compatibility is
locally checked with OpenAI SDK 2.29.0, httpx 0.28.1 and langchain-openai 1.1.11;
it is not a live account/model acceptance claim. Tests author their count/usage
responses explicitly. Endpoint tariffs and billing remain unverified, so the test
allowance is not a recommended live price or proof of budget feasibility.
See [local verification](../../benchmarks/results/openai_input_count_admission_2026-09-17/RESULTS.md).

## Mock-only application caller preparation

[The local successor](../../benchmarks/results/counted_application_caller_2026-09-17/RESULTS.md) connects this counted guard to exact query envelopes, graph-owned phase bindings and finally-persisted diagnostics. It requires a fresh output path and an explicit mock transport, supplies no live dispatcher/admission/CLI, and never treats observations as execution authority. Its frozen USD 0.95556423 shared remainder includes up to 12 counts with an explicit USD 0.01 allowance each, 12 generations and 48 embeddings; output reserves remain Astra 5120/Terra 8192. These are proposed experimental limits, not measured costs or confirmed endpoint terms. Mock success cannot establish actual token savings, account access or a complete-run budget.

The [read-only readiness review](counted_narrative_readiness.md) refreshes official generation rates and general key/project permission requirements. Count-specific price/free status and effective account permissions remain unknown. Nine conditional budget boundaries pass; no actual count, model request or authenticated model listing is performed. The review is complete and supplies no execution authority or complete-run guarantee.

## Single-use counted application execution

The later explicit user experiment request authorized the [concrete successor](counted_narrative_experiment.md), including one fixed question and the existing count contingency under the unchanged shared cap. Its fresh manifest binds the source/caller/policy and is consumed before app construction. Original mock/paid packets remain immutable. The live egress client forces official endpoints, no redirects/retries/proxies/hooks, and stores bodies without credentials/headers. It opens only a verified disposable existing-store copy, denies historical answer reads and ingest/context generation, and persists the original interruption diagnostics. A 30-second heartbeat does not wait on the in-flight count/generation budget lock. Observed endpoint access is separate from count tariff verification, conservative accounting and complete-answer acceptance. This packet stopped at its unchanged budget; it supplies no resume or runtime-default authority.

The subsequent explicit request to increase the budget authorized a [fresh successor](counted_narrative_budget_successor.md) with shared cap USD 8, one dollar above the previous cap. Earlier accounting remains 6.61558234, so its single-run allowance is 1.38441766. Only that allowance and fresh output path change; all models, full output bounds, call limits, rates, count contingency and source/transport controls remain identical. The old run is not resumed. The successor completes one known-source question, accounting 0.46786026; shared total 7.08344260, remainder 0.91655740. Neither this approval nor its successful sample changes account billing settings or authorizes automatic additional runs.

## First frozen new-question settlement (2026-09-17)

The user-authorized [search/display run](search_display_app_probe.md) consumes
fresh manifest `f896a23e...82ac8a` once with allowance **0.91655740**, without
increasing the USD 8 shared cap. All 25 requests return 200; three measured inputs
match usage. No budget request is blocked. Runtime ownership/completion defects
produce an empty answer, and the ledger assertion stops the caller; HTTP success
does not make this a successful application result. No paid retry follows.
Usage estimate **0.27257845** plus **0.03** count contingency settles **0.30257845**,
leaving shared accounting **7.38602105 / 8**, remainder **0.61397895**, pending 0.
The count tariff/invoice remains unobserved. Next work is provider-free contract
correction; this consumed admission cannot authorize another question or rerun.
