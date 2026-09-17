# One-source narrative instruction comparison

Completed 2026-09-18 on clean `9f9a26e5`. Existing and adopted instructions both
produce the same faithful claim. **This paired sample shows a tie, not an observed
improvement or regression.** The earlier application fidelity concern remains.

## Frozen scope and result

The user accepted adding at most USD 1 for one anonymous old/new comparison.
Shared cap increases **8 → 9**; this experiment itself is capped at **1**, with
the previous **0.30722246** outside its allowance. Fresh manifest
`7a6a20d2f00d61a36728d14d7588d9f833b6f86a1b786eb83fe39edb162b0f51`
was consumed once. All earlier manifests and results remain immutable.

The pre-existing `predicate_attachment_ko` control supplies one source:
**“솔라는 장비를 정비하고 창고를 확장한다.”** The request is “Describe the activity.”
Expected statements and review labels remain outside model input. Complete
requests differ only by the reviewed 418-byte instruction; source, schema and
Astra/medium/Standard/5120/`store=false` settings match. Baseline runs first,
then adopted, one initial generation each, without repair or retry.

| Arm | Measured / usage input tokens | Output tokens, including reasoning | Sampled claim | Source/execution | Separate meaning review |
| --- | ---: | ---: | --- | --- | --- |
| Existing instructions | 2644 / 2644 | 405 | 솔라는 장비를 정비하고 창고를 확장한다. | Pass | Both actions preserved |
| Adopted instructions | 2745 / 2745 | 420 | 솔라는 장비를 정비하고 창고를 확장한다. | Pass | Both actions preserved |

Neither claim expands equipment, omits either action, adds an unsupported claim,
or abstains. Subject/fact references match in both responses: four exact support
occurrences in total. Both untouched raw payloads pass current schema/lowering,
V2 source validation and deterministic execution, with zero offline repairs.
The actual first prompts and schemas match the frozen sent requests.

This is assistant semantic review of one known anonymous source, not independent
human gold or unseen accuracy. Both responses copy the source, so the experiment
does not establish paraphrase quality, harder synthesis, general effectiveness,
full-agent behavior, or repair of the old search/display answer. Other response
fields differ; whole-response equality is not claimed. Keep the existing policy
without another runtime change based on this tie.

## Cost and verification

Both counts complete before either generation. Measured inputs plus both full
5120-token ceilings and count contingency reserve **USD 0.5993625**, below 1.
All **4/4 HTTP requests return 200**; elapsed time is approximately 34 seconds.
No API/schema/runtime/budget error, SDK retry, internal repair or whole-run retry.

Pinned conservative rates remain input **12.5** and output **50** USD per million,
consistent with the [official Standard pricing table](https://developers.openai.com/api/docs/pricing#standard-pricing-data)
(input uses the higher cache-write reserve). Usage estimate **0.1086125** plus
**0.02** count contingency accounts **0.1286125**. Shared accounting becomes
**7.82139004 / 9**, remaining **1.17860996**, pending **0**. This is not an invoice;
the count tariff remains unobserved. Reasoning is already included in output usage.

Caller controls **7/7**, counted-budget contracts **27/27**, and docs **4/4** pass.
Two identical mocked SDK rehearsals and two authored Compiler replays precede
dispatch; these are transport/execution evidence, not model-quality samples.
All **173** sources, **2309** protected predecessor artifacts, **147** sealed
pre-dispatch files, **24** store files and local settings retain hashes.
Prior full **2029/2029** and domain audit **83** remain unchanged-source evidence
and were not rerun. Only documentation is committed; the
[local raw packet](../../benchmarks/results/narrative_clause_pair_2026-09-18/)
preserves requests, responses, count receipts, review and accounting.

Next: use the already frozen longer search/display input for one old/new
comparison to test the observed failure more directly. Retain the shared cap,
full-output reservation and one response per arm; establish the complete pair's
cost before either generation. This completed manifest permits no further calls.
