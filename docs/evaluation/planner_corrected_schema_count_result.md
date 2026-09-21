# Corrected Planner schema: input count accepted

The user continued the explicit one-count verification after the
[annotated-reference correction](openai_schema_reference_compatibility.md).
One new request ran on clean **`5fb9558c`**, 2026-09-22, within the existing
**USD0.01** envelope. No further production source, schema, prompt or model changed.

## Observed result

| Observation | Recorded value |
| --- | --- |
| Count attempts / successful counts | **1 / 1** |
| HTTP status | **200** |
| Measured input tokens | **8,417** |
| Generation / Planner outputs | **0 / 0** |
| SDK / HTTP retries and resume | **0 / 0; disabled** |
| Execution or heartbeat errors | **None** |

The response is exactly `{"input_tokens":8417,"object":"response.input_tokens"}`.
The saved raw-success projection, SDK value, measurement and receipt agree.
The [official counting guide](https://developers.openai.com/api/docs/guides/token-counting),
searched and fetched on 2026-09-22, covers input structure and schema tokens.
This establishes acceptance by the **input-count endpoint** for this exact body.
It does not establish generation acceptance, a valid generated plan, or period
and scope interpretation accuracy. The six unsampled Planner meanings and
historical period2/6 and scope6/6 results remain unchanged.

## Exact request and one-use admission

The existing `u01` question, full prompt/input, **gpt-5.6-terra** and **low**
reasoning are retained. The only change from the preceding rejected count body
is the reviewed expansion of the annotated `measurement_period` reference.
No constraint, required field, enum, date bound or original-model validation
was removed. Canonical input grows **40,444 → 42,611 bytes** (+2,167).

- Count-body and actual new SDK wire SHA256:
  `4eee5fc8f96cdcdb37aaec9f325445bfb83e5a06e8238b3661bbb52efa1f8507`.
- Fresh manifest, consumed before transport:
  `e1d70dc6582a2ededf6b8a983787c7062995aea63784da84a62de97d57ec4d1d`.
- Endpoint: one POST to `https://api.openai.com/v1/responses/input_tokens`.
- The copied generation body is a reference for exact input projection only.
  No generation, retrieval, embedding, Compiler or ingest request was admitted.

The reviewed caller and its test file were copied byte-for-byte into a new
ignored packet. Only its helper's predecessor path/count and accounting
constants changed. Criteria, request, policy, package versions and source hashes
were frozen before mocks. A fresh authority records the latest user continuation
for this exact manifest; neither old consumed manifest was reused.

The previous HTTP400/invalid_json_schema result and its error sidecar remain
unchanged. This successful changed-schema count does not recover an old detailed
error or prove the sole historical failure cause. It supplies the missing live
observation for the corrected count body.

## Validation, accounting and next step

- **20 caller tests**, with **27 execution scenarios**, pass on the frozen body,
  covering failures, retries/redirects, request drift, invalid success values,
  diagnostics persistence, funding and one-use admission.
- Two independent actual-SDK healthy mocks have **6 byte-identical result
  files** and six healthy assertions each. Their authored14,000-token values
  are separate from the actual **8,417-token** measurement.
- **39 provider-free evidence checks** confirm actual wire/response identity,
  the single call, consumption, accounting and preserved files. Reentering the
  consumed caller stops before credentials or transport. Documentation2,
  syntax, diff and local-link checks pass.
- All **14,147 predecessor files**, **177 production sources**, **24 original
  stores** and local settings retain hashes. Only six documents are committed;
  `benchmarks/results/planner_corrected_schema_count_2026-09-22` remains ignored.
  Prior full2267/2267, focused109 and audit83 are not rerun for this source-unchanged
  experiment and documentation update.

One attempted count retains **USD0.01** contingency, with zero generation cost
estimate and pending0. Shared accounting is **USD19.76502393 / 20.32** and remaining
funding is **USD0.55497607**. The contingency is not a verified endpoint tariff
or invoice; the total budget has not increased.

Next prepare one frozen-question Planner generation probe with explicit semantic
criteria and complete funding inside the existing balance. Use a fresh
count/generation admission with unchanged output bounds. This consumed one-count
manifest grants no generation, automatic retry or resume.
