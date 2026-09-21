# Uniform-period Planner probe: count request rejected

On clean **`251db717`**, 2026-09-22, the user's continuation authorized the
[prepared four-question batch](planner_uniform_period_probe.md) once under
**USD 0.58**, without a budget increase. Manifest
`01c674fc7097d9e19f7e4c626caf5e02cdbfa6530558ece07b8449d545923afe` was
consumed before transport. **The first input-count request returned HTTP 400;
no generation ran.** This is a provider count-admission failure, not a model
interpretation result or completed comparison.

## Observed outcome

| Case | Input count | Generation / semantic assessment |
| --- | --- | --- |
| u01 | HTTP 400, SDK `BadRequestError` | Not run / not assessed |
| u02 | Not attempted after stop | Not run / not assessed |
| u03 | Not attempted after stop | Not run / not assessed |
| u04 | Not attempted after stop | Not run / not assessed |

Exactly **one HTTP attempt**, zero generations, zero completed plans and zero
retries/repairs. The caller closed with `provider_token_count_failed`, preserving
the failed count and stopping the remaining batch. Provider return occurred about
8.2 seconds after entry; final integrity verification finished about12.9 seconds.
The caller retained its 30-second heartbeat mechanism; the run ended before its
first timed heartbeat.

The sent count body exactly matches the frozen manifest and the earlier actual-SDK
mock. It uses the same outer parameter keys, model and reasoning setting as the
previous successful count, with different question/instructions and period schema.
Local JSON Schema validation, the installed SDK parameter names and the four
authored response fixtures pass. Those checks do **not** establish that this
request is accepted by the provider, or identify the cause of HTTP 400.

## Failure boundary and missing detail

Local admission succeeded; there was no budget denial or measured input overflow.
No input count or generation usage was returned. The observation is specifically
**HTTP 400 at `POST /v1/responses/input_tokens`**, before answer generation.

The frozen caller saves response bodies only for HTTP2xx. The count guard retains
error class/status, and this run's runtime log is empty. Provider error code,
parameter, request ID and error message were therefore **not recorded** and cannot
be recovered from these artifacts. The root cause remains **unknown**; the new
schema has not been proven responsible.

The existing opt-in `src/ops/openai_error_diagnostics.py` helper is unused by this
caller, and its reviewed error-code list covers overload/rate-limit cases. The
next bounded work is provider-free diagnostic capture for HTTP400 in a new local
caller, including tests that retain useful bounded metadata without exposing
credentials or changing the original failure. Any later count needs a new frozen
manifest and recomputed funding. This consumed run cannot be retried or resumed.

## Accounting and evidence

| Item | USD |
| --- | ---: |
| Generation estimate; none attempted | 0 |
| One attempted-count contingency | **0.01** |
| Shared accounting / allowance | **19.74502393 / 20.32** |
| Remaining / pending | **0.57497607 / 0** |
| Budget increase | **0** |

The 0.01 is the frozen count contingency, **not an observed charge or verified
count tariff**. No invoice or token measurement is available. Generation usage
fields in the initial accounting artifact are null because no usage arrived;
the accounting review separately confirms zero generation attempts and exactly
one count contingency. The old0.58 run cap exceeds the new remaining balance;
future admission must recheck both its full envelope and its cap.

**34 offline evidence checks** pass, including exact request identity, closed
admission, retained accounting and refusal to replay before credential loading or
transport. Documentation **2/2**, syntax, diff and link checks pass. Runtime is
unchanged; prior **132 focused**, **72 caller controls**, full **2238/2238** and
audit **83** were not rerun. All **13,726 predecessor files**, **177 production
sources**, **24 original stores** and local settings retain hashes. The new
execution/evidence packet is ignored at
`benchmarks/results/planner_uniform_period_run_2026-09-22`; only six docs are
committed. Original requests, criteria, mocked evidence and failed live records
remain unchanged.

Period/scope accuracy for these six meanings is **not assessed**, rather than
0/6. The prior paid sample remains periods **2/6**, scopes **6/6**, coverage
**0/4** and combined questions **1/5**. No source-store client, search, Compiler,
embedding, ingest or full-agent evaluation ran.
