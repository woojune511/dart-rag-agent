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
