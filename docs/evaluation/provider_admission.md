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
