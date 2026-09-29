# Compiler output-limit diagnosis

The saved first response in the
[Planner request-range application check](planner_section_range_app_check.md)
stops making JSON progress during its first output and emits a long whitespace
suffix. **32,342 of 33,676 characters (96.04%) are trailing spaces/newlines.**
It then reports `incomplete / max_output_tokens`. The final response completes
all four outputs at 2,176 tokens under the same 5,120-token ceiling.

This identifies the observed failure as **generation noncompletion with repeated
structural whitespace**. It does not establish whether model generation,
constrained decoding or another provider component caused the repetition.
Neither a globally insufficient ceiling nor excessive reasoning is established.
No runtime/default, prompt, schema, output limit or retry policy changed here.

## Frozen evidence

The user continued the concrete offline diagnosis on clean `63b29393`.
[Local diagnosis packet](../../benchmarks/results/compiler_output_limit_diagnosis_2026-09-18/)
records the analysis, real-SDK replay and checks. Raw first/final responses remain
in the prior run's `wire/033_response.json` and `wire/035_response.json`.
All **6,824 predecessor files**, **174 source files**, **24 protected store files**
and local settings were hash-verified. No provider/count/embedding call, new
admission, consumed-manifest reuse, application query or store mutation occurred.

| Observation | First response | Final response |
| --- | ---: | ---: |
| Provider output tokens, including reasoning | 5,120 | 2,176 |
| Reported reasoning tokens | 162 | 150 |
| Output-text characters | 33,676 | 7,378 |
| Output-text UTF-8 bytes | 33,770 | 8,895 |
| Trailing JSON whitespace characters | 32,342 | 0 |
| Whitespace outside quoted strings | 33,026 | 3,261 |
| JSON parse | Incomplete | Valid |

The suffix contains **30,032 spaces and 2,310 newlines**, including 2,309
identical thirteen-space lines. The last non-whitespace character ends the
first claim's source-selection array; nine enclosing containers remain open.
Only the first of four requested output keys has begun. No second output,
completed program or final answer exists in that response.

The 96.04% figure measures characters, **not provider tokens**. We did not infer
per-span token attribution from a local tokenizer. The saved usage explicitly
records 162 reasoning tokens, about 3.16% of the output total.

## Schema and repair boundaries

Both calls use `text.format.type=json_schema`, `strict=true`, the same schema,
route/settings and output ceiling. Canonical schema size is 9,750 UTF-8 bytes.
Only their inputs differ; the second includes the existing validation feedback.
Candidate identities and payload size remain equal in the saved trace.
Schema input bytes are not output-token demand. The completed four-output
response demonstrates that this instance can fit the same configured ceiling;
it does not isolate a causal effect of the feedback or promise future success.

The [official Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs)
confirms that reaching a token limit can leave a structured response incomplete
and requires explicit handling. Its separate missing-JSON-instruction whitespace
warning concerns **JSON mode**. Although neither saved prompt contains the word
`JSON`, this incident used strict `json_schema`, not `json_object`. That warning
does not establish why this response repeated whitespace.

`StrictOpenAIChatModel` rejects incomplete provider status before parsing.
The Compiler records its safe `ValueError` as `compiler_response_schema_error`
for the four active owners; this label does not prove that the schema itself
was invalid. The original wire receipt supplies the more specific
`max_output_tokens` reason. The existing one feedback repair succeeds without
changing the schema or ceiling; the failed draft remains preserved.

Removing only trailing whitespace still leaves invalid JSON at character 1,334.
Removing all whitespace outside strings leaves a 650-character fragment that
is also invalid. Neither projection inserts delimiters, missing fields or
answers, and neither enters production. The successful response can be locally
serialized in 4,117 characters / 5,634 bytes while preserving its entire object.
This is an authored serialization witness, not new model output, measured token
savings or evidence that a compact-output instruction prevents repetition.

## Provider-free verification and next step

Eight anonymous lexical controls preserve quoted spaces, escapes, Unicode and
invalid/incomplete syntax. Four actual installed-SDK replay cases pass with
external connections blocked and exact frozen request-body equality:

- Original incomplete response: text/whitespace preserved, program rejected.
- Original completed response: text preserved, original program parsed.
- Explicitly authored compact successful text: identical parsed program.
- Valid JSON with explicitly authored incomplete status: still rejected.

The two authored cases carry synthetic usage metadata and are excluded from
paid accounting. These are transport-boundary replays, not fresh generations
or reruns of the complete application. Existing transport contracts pass
**10/10**; documentation checks pass **4/4**. The full suite was not rerun for
this documentation-only change; prior runtime results retain their scope.

Added cost is **0**. Shared accounting remains **11.69207159 / 14**, remaining
**2.30792841**, pending **0**, with previous reservations retained; not an invoice.
The previous completed answer and its separate four-criterion review are unchanged.

The next bounded candidate is a serialization-only instruction: emit one compact
JSON object while preserving every required field and all string contents,
including evidence quotes. First prepare unchanged-schema/input controls; any
later sampled comparison needs a fresh bounded admission. There is no evidence
here to raise the output ceiling, strip or complete provider responses, remove
grounding fields, shorten required content or add retries. A serialization
instruction remains a hypothesis until model behavior is separately measured.

The separate [compact-JSON comparison](compiler_compact_json_comparison.md) now
records four newly scheduled first responses under a fresh bounded manifest.
It observes compact output in both candidate samples; both baselines also
complete, so the original failure and its unknown upstream cause remain unchanged.
