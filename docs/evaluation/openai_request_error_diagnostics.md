# Bounded OpenAI request-error diagnostics

Implemented from **`7772dc2a`** on 2026-09-22 after the user continued the
provider-free logging work. The [failed Planner count](planner_uniform_period_probe_result.md)
returned HTTP400 without a saved error body. This change prepares useful bounded
metadata for a future caller; **it cannot recover that missing cause**. No API
request, credential loading, paid authority or new live manifest is created.

## Projection contract

`src.ops.openai_error_diagnostics.openai_request_error_metadata` is an explicit
v2 projection of an already received HTTP400–599 response. It performs no I/O.
Existing `openai_http_error_metadata` callers retain their v1 schema and behavior.

| Field | v2 recording rule |
| --- | --- |
| `error_code` | Legacy overload/rate-limit codes plus the finite reviewed request-error vocabulary below |
| `error_type` | Exactly `invalid_request_error`, `server_error` or `rate_limit_error` |
| `error_param` | Exactly one reviewed protocol field/path below; no values or arbitrary schema/input paths |
| `request_id`, `retry_after` | Unchanged v1 shape and bound checks |
| `availability` | Each field independently captured, absent, unrecognized, unavailable or malformed/oversized |

Added codes are `invalid_json_schema`, `invalid_value`, `invalid_type`,
`missing_required_parameter`, `unknown_parameter`, `unsupported_parameter`,
`unsupported_value`, `context_length_exceeded` and `model_not_found`. These are
local disclosure choices, not an exhaustive or guaranteed provider taxonomy.
The recorded strings are observations, not conclusions about the earlier400.

Permitted parameter names are `model`, `input`, `instructions`, `reasoning`,
`reasoning.effort`, `text`, `text.format`, `text.format.type`, `text.format.name`,
`text.format.schema`, `text.format.strict`, `max_output_tokens`, `service_tier`,
`store` and `stream`. Matching is exact; a field does not need to be present in
the request to be named as missing by the provider. No prefix matching, case
repair, dynamic property names, indexed input paths or request values are copied.

Unknown values are explicitly unavailable. Missing/null code does not hide a
recognized type or parameter. Status and free text never infer fields. Parsing
is bounded to64KiB; malformed, deeply nested or duplicate-key JSON cannot supply
body fields. Valid bounded headers may remain available independently. Messages,
raw failed bodies, complete header maps, credentials, cookies and organization
metadata remain excluded. Public/runtime error projections remain unchanged.

The [official error guide](https://developers.openai.com/api/docs/guides/error-codes)
documents `invalid_request_error` with `error.param=service_tier` for a project
tier restriction. The [request debugging guide](https://developers.openai.com/api/reference/overview#debugging-requests)
describes `x-request-id` as a troubleshooting identifier. Neither establishes
the cause of the preserved count failure. Both pages were searched and fetched;
the installed SDK's `APIError` code/type/param fields were also inspected.

## Caller observation and failure behavior

The ignored packet `benchmarks/results/openai_request_error_diagnostics_2026-09-22`
contains a new `instrumented_runner.py`, derived from the frozen Planner caller.
It admits **authored HTTP mocks only**. Its `run` entry and `mock_only=False`
execution stop before output creation, credentials or transport. It has no live
transport constructor and does not alter the consumed script or manifest.

Before the SDK processes a failed response, the caller saves the v2 projection
in `http_attempts[].http_error` and an exclusive `wire/NNN_error_metadata.json`
sidecar. Count and generation failures use the same observation point. Success
bodies follow the existing path, while raw non-2xx bodies are never persisted.

Capture failure records only its exception class and returns the original HTTP
response to the SDK. Sidecar failure leaves captured metadata in the receipt,
records its exception class and preserves the original failure. Existing sidecar
files are never overwritten. These observations do not authorize a retry, change
the request, settle missing usage or suppress terminal admission. Count allowance
and failed-generation reservations retain their existing behavior. Process crash,
partial filesystem writes and a final receipt failure are not made recoverable.

## Provider-free verification

- **17 new** projection tests and **12 existing v1** tests pass; with existing
  count/runtime admission contracts, **56 focused tests** pass.
- Two fresh-process healthy SDK rehearsals retain all **8** exact request bodies
  and **4** normalized plans from the prior mock. No error sidecars appear on
  success. Full synthetic usage costs0.573216 within a mock cap0.574 and current
  balance0.57497607; this is not live authority or measured token usage.
- **119 caller controls**, plus six healthy assertions in each process, cover
  count400, generation400/503, null code, unknown fields, malformed body, timeout,
  capture failure, OSError/TypeError persistence failures and existing sidecars.
  Private-data canaries never enter saved outputs. Terminal status, no next call,
  count allowance and full failed-generation reserves remain intact.
- Public/API, request-diagnostic, import/topology and documentation gates are
  recorded in the packet. All **13,759 predecessors**, **176 unrelated sources**,
  **24 original stores** and local settings retain hashes. Production source
  changes are limited to the appended opt-in projection in one existing ops file;
  source count remains177. Prior full **2238/2238** and audit83 are not rerun for
  this isolated ops extension.

Added provider calls/accounting are **0**. Shared accounting stays
**USD19.74502393/20.32**, remaining **0.57497607**, pending0. The previous one-count
HTTP400 failure, zero generations and unassessed six meanings remain unchanged.
The subsequent [one-count diagnostic result](planner_count_error_probe_result.md)
captures invalid_json_schema / invalid_request_error / text.format.schema
from an actual HTTP400. Its fresh manifest is consumed, generations remain0,
and USD0.01 contingency is added separately. This confirms v2 observation
on that response; the exact rejected subschema and older missing error remain
unknown. Implementation-only accounting above remains historical.
