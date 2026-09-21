# Planner count diagnostic: schema rejected

The user continued the [prepared one-count diagnostic](planner_count_error_probe.md).
It ran once on clean **`f11947f7`**, 2026-09-22, within the existing **USD0.01** cap.
Manifest `977908cdd0c0ef4d9e84e649f12ffc7b30953cb014ae9ea506215bd965f474da`
was consumed before transport. No source, prompt, schema, model or budget changed.

## Observed result

| Observation | Recorded value |
| --- | --- |
| Count attempts / successful counts | **1 / 0** |
| Generation calls / Planner plans | **0 / 0** |
| HTTP / SDK error | **400 / BadRequestError** |
| Provider error code | **invalid_json_schema** |
| Provider error type | **invalid_request_error** |
| Provider parameter | **text.format.schema** |
| Request ID / Retry-After | Bounded ID captured locally / absent |
| Retry / resume / fallback | None; caller stopped |

The provider explicitly rejected the structured output schema during input
counting. This establishes the failure category for **this request**, but the
exact offending subschema or keyword is not identified. No count or generation
was accepted. The earlier uninstrumented HTTP400 still has no saved detailed
error; the new observation does not recover that missing response.

The complete frozen `u01` count body was retained. Its canonical identity and
the actual new SDK wire bytes both match SHA256
`4b39118088f09035bf83f34afa2c85ab6057f2d5bef1d5656e9bb26cdaf68ab8`
and **40,444 bytes**, including model **gpt-5.6-terra**, low reasoning and the full
input/text schema. The older failed request is available as canonical JSON;
its original raw serialization and detailed error body were not saved.

V2 capture succeeded before SDK error handling. The receipt and exclusive
sidecar contain identical bounded metadata, with code/type/parameter/request ID
marked captured and Retry-After absent. No capture or persistence error occurred.
Free-form error messages, raw failed response bodies, header maps and credential
values were not saved. The retained request ID is in the ignored local packet.

## Local schema review and claim boundary

The [official Structured Outputs subset](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas)
requires an object root, required declared fields and closed objects, and lists
unsupported composition keywords. The page was searched and fetched on
2026-09-22. These checks on the exact submitted schema found:

- General `Draft202012Validator.check_schema` validity passes.
- The root is an object without root `anyOf`.
- All **10 object schemas**, with **88 properties**, have complete `required`
  lists and `additionalProperties: false`.
- All **20 references** resolve; the reviewed unsupported composition keywords
  (`allOf`, `oneOf`, `not`, `if/then/else`, dependency compositions) are absent.

This is a bounded local inspection, **not an exhaustive provider-compatibility
validator**. It found no specific defect explaining the provider rejection.
No field constraint was removed, no alternative schema was sent, and no mock or
general JSON Schema pass is presented as provider acceptance. The six Planner
period/scope meanings remain unassessed. Historical period2/6 and scope6/6
results are unchanged.

## Accounting, preservation and next work

The single actual count attempt retains **USD0.01** contingency; generation
estimate is0 and pending is0. Shared accounting is now **USD19.75502393 / 20.32**,
with **USD0.56497607** remaining. This is conservative experiment accounting,
not a verified count tariff or invoice. No funding increase occurred.

**42 provider-free evidence checks** pass: manifest/authority/consumption,
exact request and wire identity, original HTTP outcome, bounded receipt/sidecar,
absence of later calls, accounting, schema inspection and file preservation.
A consumed entry check stops before credentials or transport. Documentation2,
syntax, diff and local-link gates pass. Prepared51 tests and the two SDK mocks
remain prior evidence and were not rerun; production sources did not change.

All **14,045 predecessor files**, **177 production sources**, **24 original
stores** and local settings retain hashes. The only additions to the sealed
preparation packet are the new authority, consumption and live evidence files.
The result packet `benchmarks/results/planner_count_error_run_2026-09-22` remains
ignored; six documents are committed. Prior full2238/2238 and audit83 remain
historical evidence.

Next investigate the emitted Planner schema and transport against the supported
schema subset without provider calls. Identify a specific compatibility defect
before changing constraints. Any subsequent paid diagnostic needs a new frozen,
fully funded manifest; this consumed run grants no retry, resume or generation.
