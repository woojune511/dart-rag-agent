# Planner input-count error diagnostic preparation

Prepared from clean **`eca4ea64`** on 2026-09-22 after continuation of the
[bounded error-observation work](openai_request_error_diagnostics.md). This is
**preparation only**: no credential loading, paid authority, consumption or API
request. The new manifest is bound to the resulting clean documentation commit.

## Frozen question and request

The [consumed Planner probe](planner_uniform_period_probe_result.md) stopped on
its first input count, HTTP400, without detailed error metadata. Its cause is
unknown. This diagnostic copies that exact `u01` count body, including the full
input, model, reasoning and structured text schema; it does not rewrite a prompt
or remove fields to obtain acceptance.

- Model **gpt-5.6-terra**, reasoning **low**; canonical UTF-8 **40,444 bytes**.
- Count-body SHA256: `4b39118088f09035bf83f34afa2c85ab6057f2d5bef1d5656e9bb26cdaf68ab8`.
- The copied generation body is a reference only; its supported four-field count
  projection matches exactly. Output8192, storefalse and default tier remain
  historical generation settings, without generation authority in this packet.
- Criteria, identity, policy, accounting and package versions are hashed before
  authored mocks. The two SDK mock processes also preserve actual serialized
  request identity. Model decisions and semantic answer criteria are not sampled.

The [official counting guide](https://developers.openai.com/api/docs/guides/token-counting),
searched and fetched on 2026-09-22, describes counting model-visible messages,
formatting and schema tokens before generation. A successful count establishes
an input-size observation; it does not establish generation-schema acceptance,
Planner correctness or the cause of an earlier response.

## One-count boundary and funding

| Item | Fixed scope |
| --- | --- |
| Request | One POST to `https://api.openai.com/v1/responses/input_tokens` |
| Generation / Planner / Compiler / retrieval / embedding / ingest | Zero calls |
| SDK / HTTP retries, redirects and resume | Disabled; first failure is terminal |
| Count contingency and packet cap | **USD0.01** for one transport attempt |
| Shared accounting / cap | **USD19.74502393 / 20.32** |
| Available / pending | **USD0.57497607 / 0** |
| New funding and preparation accounting | **0 / 0** |

The whole count envelope is funded within the existing balance. The contingency
is not a verified endpoint tariff or invoice. A transport attempt retains0.01
even when delivery or usage is uncertain; a proved failure before dispatch
retains0.00. No generation reserve is required because there is zero generation
authority. The runtime's coupled count/generation guard is unchanged.

The dedicated caller checks exact endpoint, method, body, model, policy, one-use
schedule and funds. Live entry requires exact-manifest authority and current
accounting, then verifies the clean commit, frozen files, production sources,
original stores, settings and SDK versions before credentials or transport.
Consumption is exclusive and occurs before the network client is constructed.
The actual entry without authority stops before credentials, transport,
consumption or live output. No authorization file is created during preparation.

## Observation and verification

HTTP200 must contain `object=response.input_tokens` and an actual positive integer
at most200000, with matching SDK projection. The validated response and count are
saved. Invalid JSON, wrong objects, strings, booleans, missing or out-of-range
counts stop without a replacement estimate or generation.

For HTTP400–599, the caller records opt-in v2 metadata before SDK error handling:
reviewed code/type/parameter names, bounded request ID and Retry-After, and
independent availability states. Both the receipt and an exclusive sidecar retain
the projection. Unknown fields remain unavailable. Failed bodies, free messages,
arbitrary header maps, request values and credential values are not saved.

Metadata capture or sidecar persistence failure records only its exception class;
the original SDK HTTP error and terminal result survive. Existing sidecars are
not overwritten. Pre-dispatch logging must succeed before marking an attempt.
A30-second heartbeat covers the90-second read timeout; it never authorizes retry.
Process crashes, partial writes and failure to save the final receipt are not
made recoverable by this diagnostic.

- **20 caller tests**, including27 execution scenarios, cover HTTP400/401/429/503,
  timeout/redirect, invalid success shapes, null/unknown/ambiguous error fields,
  capture/persistence failure, existing sidecars, pre-dispatch failures, endpoint
  and body drift, second calls, resume, missing authority and funding/scope drift.
- Two fresh-process actual-SDK healthy mocks have **6 identical output files**,
  one exact count each, zero generations and six healthy assertions per process.
  Their14000-token responses are authored; they are not measured provider counts.
- **29 existing metadata contracts** and **2 documentation tests** pass. Syntax,
  diff, local links, frozen identities and the actual unadmitted entry are checked.
  External connections, credential reads and real transport construction are0.
- All **13,874 predecessor files**, **177 production sources**, **24 original
  stores** and local settings retain hashes. Only five documents are committed;
  `benchmarks/results/planner_count_error_probe_2026-09-22` stays ignored. Prior
  full **2238/2238** and audit83 remain historical, not rerun for this preparation.

Next execute this one frozen count under its fresh exact-manifest admission and
review its bounded metadata separately. There is no automatic retry or generation
successor. The earlier HTTP400 remains unexplained and all six Planner meanings
remain unassessed; mocks do not change historical period2/6 or scope6/6 results.
