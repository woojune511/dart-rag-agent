# Local OpenAI error metadata

The subsequent [authorized diagnostic pair](narrative_long_pair_diagnostic.md)
uses the unchanged caller and completes successfully. The local-only scope and
historical verification described below remain unchanged.

Implemented from `093cde70` on 2026-09-18 after the user continued the logging
recommendation. A new opt-in ops helper and a separate successor experiment runner
retain selected metadata from failed HTTP responses. **No new provider call or
paid retry occurs.** The earlier HTTP 503 still has no recoverable detailed cause.

## Recorded fields and boundary

`src.ops.openai_error_diagnostics.openai_http_error_metadata` reads an already
received HTTP error. It performs no I/O, credential access, waiting or retry.

| Field | Local recording rule |
| --- | --- |
| `http_status` | Integer HTTP error status, 400–599 |
| `error_code` | Reviewed `server_is_overloaded`, `slow_down`, `rate_limit_exceeded`; other values omitted |
| `request_id` | `x-request-id` with `req_` plus 6–128 ASCII letters/digits |
| `retry_after` | Integer delay 0–604800 seconds, or canonical GMT HTTP date normalized to UTC |
| `availability` | Explicit captured, absent, unrecognized, unavailable or malformed/oversized-body state |

The request-ID shape and delay bound are local disclosure rules, not a guarantee
about all provider formats. Other formats remain visibly unrecognized. The JSON
body parsing limit is 64 KiB. Free-form error messages, raw failed response bodies,
complete header maps, authentication/cookie/organization fields and arbitrary
unknown error codes are not recorded. Neither HTTP status nor an SDK exception
class is used to invent a missing provider code.

The [official overload guidance](https://developers.openai.com/api/docs/guides/rate-limits#handle-rapid-traffic-increases-and-model-overload)
distinguishes HTTP status and `error.code`, including older code combinations.
The [request debugging guide](https://developers.openai.com/api/reference/overview#debugging-requests)
identifies `x-request-id` as the provider troubleshooting identifier. Recorded
`Retry-After` remains evidence, not authorization to repeat a paid request.

The [local successor](../../benchmarks/results/openai_error_diagnostics_2026-09-18/runner.py)
adds metadata to `execution.json` under `calls[].http_error` and an exclusive
`wire/NN_error_metadata.json` sidecar before the SDK raises. Count and generation
failures both retain it. Extraction or sidecar-write failure records only the
exception class and preserves the original HTTP failure/admission stop; metadata
still reaches the final execution receipt when only its sidecar write fails.
Final-receipt failure or process crash is not made recoverable by this change.

The consumed predecessor runner, admission and failed result are unchanged.
Runtime/public `provider_error_projection`, API error responses, successful
requests/responses, source interpretation and budget accounting remain unchanged.
The helper is excluded from default runtime imports and used explicitly only by
the successor experiment caller. No live manifest is created in this work.

## Verification and next work

Provider-free checks pass: projection **12/12**, actual-SDK mocked diagnostic
transport **4/4**, existing caller controls **7/7**, import/API/request-diagnostic
boundaries **24/24**, documentation **4/4**; **51 total**, no external attempts.
Controls cover 503 and 429 codes, missing/unknown values, malformed/oversized JSON,
header injection/duplicate fields, bounded delay/date values, private-data canaries,
full failed-request reservation retention, no next arm/retry, and diagnostic
capture/write failures preserving the original cause. Pycompile/diff checks pass.

One ops source is added; all **173** original source files, **2659** protected
predecessor artifacts, **24** store files and local settings retain hashes.
The new source total is **174**. Prior full **2029/2029** and domain audit **83**
are earlier core evidence and were not rerun for this isolated ops addition.
Shared accounting stays **8.20432754 / 9**, remaining **0.79567246**, pending **0**;
no added cost, cap change, count, generation or embedding request.

Logging preparation is complete. Next continuation can prepare one fresh pair
using this caller under the remaining cap and unchanged model/output bounds,
funding both complete requests before generation. The historical comparison
remains incomplete; mocked overload metadata does not establish its missing cause.
