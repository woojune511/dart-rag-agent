# OpenAI compiler migration probe

Two separately approved trials executed on 2026-09-16, each with a USD 6 cap.
The six-case Compiler trial passes all 12 frozen outputs. Fresh full-agent integration
completes 2/3 real questions, with 5/6 planned outputs accepted and no API/runtime
errors. Its numeric exposure gap is fixed locally; a new USD 7 capped admission
is prepared but unexecuted. Google stays the default provider.

The current `FinancialAgent` factory supports an explicit `openai` route with
output/retry limits, reasoning effort, endpoint mode, storage, tier, timeout and
the existing per-phase usage callback. `temperature: null` omits the sampling
parameter. Google-only thinking options fail locally on an OpenAI route.
Google and OpenRouter defaults are unchanged.

The OpenAI structured adapter requires all fields explicitly, removes schema
default annotations and retains enums, references and value/array constraints.
It validates the returned JSON against this stricter schema and the original
Pydantic model. It never fills missing wire values or repairs an answer. Refusals
and incomplete responses cannot become valid programs. Invocation remains on
the caller's thread so phase usage is retained. Native OpenAI answer/reasoning
counts are disjoint; reasoning is already included in the API output total.

## Executed settings

```json
{
  "provider": "openai",
  "model": "gpt-6-astra",
  "temperature": null,
  "max_output_tokens": 5120,
  "reasoning_effort": "medium",
  "provider_client_retries": 0,
  "use_responses_api": true,
  "store": false,
  "service_tier": "default",
  "timeout_seconds": 90
}
```

The tested configuration targets `llm_routes.program_compilation` only.
This generation-provider change does not require rebuilding the embedding store.
Account access and schema acceptance succeeded for this run's six requests.
Sources: [migration parameters](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md#migration-quickstart),
[structured output constraints](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas),
and [API prices](https://developers.openai.com/api/docs/pricing).

## Approved comparison and results

The local ignored [packet](../../benchmarks/results/openai_compiler_preparation_2026-09-16/)
reuses the previous six anonymous inputs and fixed criteria: mixed unit scales,
source-format swap, signs, source display versus calculated dependency, half,
and negative multiplier. Each receives one first response. No planner, retrieval,
embedding, fresh ingest, store mutation, Google call or automatic retry is included.
The consumed Google manifests and responses remain immutable.

Two real SDK rehearsals with blocked sockets produce identical bodies. Six
authored responses pass the unchanged execution and ledger checks, including
12 numeric/display outputs. These are local witnesses, not model answers.
OpenAI's explicit-field schema differs from Google's wire; this is a historical
provider/transport comparison, not an isolated model A/B or a generalization test.

The approved cap was **USD 6.00**. Six independent request reservations summed to
**USD 4.73755** using canonical UTF-8 request bytes plus 1,024 as a conservative
input estimate and all 5,120 output tokens per call, including reasoning.
Input accounting uses the **USD 12.50/M cache-write rate** for every input token,
above the USD 10/M uncached and USD 1/M cached rates; output uses USD 50/M.
This stays below the long-context threshold. Reservations are conservative
estimates, not server token counts or a billing guarantee.

The approved manifest `8144726f02bea29f8bc0e7b8f1a8d07fcf9e8e5567969f965c535b158a6273d3`
was consumed once on clean `3354fbc9`. No SDK, Compiler or automatic retry occurred.
All six actual request hashes match the frozen SDK rehearsal; runtime, packet and
67 predecessor file hashes were checked before and after the blocked-socket review.

| Observed result | Value |
| --- | --- |
| API responses / provider errors / parse errors | 6 / 0 / 0 |
| Strict wire / original schema / runtime / ledger | 6/6 each |
| Frozen source, finite-formula, display and value/unit checks | 12/12 outputs |
| Input / output tokens, including reasoning | 53,677 / 5,352 |
| Reported reasoning / cached input tokens | 226 / 0 |
| Generation time total / mean | 89.27s / 14.88s |
| Conservative accounted cost / cap | USD 0.9385625 / USD 6.00 |

[Detailed results and original replies](../../benchmarks/results/openai_compiler_preparation_2026-09-16/RESULTS.md)
retain source-display/dependency checks, including half and negative multipliers.
Actual billing is unobserved. This is six known synthetic cases, one sample each;
it establishes acceptance for these requests, not general availability, unseen
semantic accuracy or current full-agent performance. The prior Google HTTP 400
has no model response and cannot be an accuracy denominator. No default promotion
was included. The separately approved full-agent successor below preserves these
inputs, criteria, responses and consumed history.

## Executed full-agent successor

The [three-question packet](../../benchmarks/results/openai_compiler_full_agent_admission_2026-09-16/)
keeps the existing NAVER and Celltrion questions and source-review criteria. Routing,
planning and retrieval run fresh; only `program_compilation` changes to the OpenAI
route above. Original stores are verified and copied; the default incomplete store
is not used. Previous plans, catalogs, answers and review criteria are not injected.

One shared **USD 6** cap covers Google generation/counts, OpenAI Responses and query/
canonical embeddings. Outer limits: 12 Google generations and 12 counts, 12 OpenAI
Responses, 64 embedding calls. Existing Compiler repair is at most one per island;
SDK retries, automatic run retries, fresh ingest and paid judges remain zero.
Limits do not guarantee all calls or questions fit the cap; unknown usage or errors
stop the run. No point cost prediction is made for fresh plans and tokenization.

Python 3.13 full unittest **1,807/1,807**, no skips (51.415s); mixed-provider focused
46 and packet checks 7 pass. Both store copies open and pass existing-vector probes.
Separate SDK/runner no-call processes produce identical receipts. These checks do
not measure live OpenAI narrative acceptance, fresh retrieval or full-agent accuracy.
After user approval, manifest `9a85a367a80f37ffdb213afa135e2d3fbe6e7e750e8460bbdce2a15fe14f2f0d`
was consumed once on clean `5dbcdb0c`. **2/3 questions complete, 5/6 outputs accepted**;
API/runtime errors 0, all three ledgers `ok`, five parsed Compiler responses and no
Compiler/SDK/run retry. NAVER B2B/AI strategy and Celltrion risk policies complete;
NAVER acquisition impact is supported but its growth calculation is missing.
All 29 accepted subject/fact support occurrences match immutable stored sources.
Separate Codex source review uses the frozen criteria; this is not human gold.

Offline reconstruction matches the live 509-candidate catalog's ID/content hashes.
Commerce current/prior amounts are present, but each numeric input exposes only
total consolidated revenue alternatives. The Compiler declines those substitutes
and discloses the missing calculation. This is a candidate-exposure loss, not an
API rejection or missing source catalog; the offline follow-up below diagnoses the ranking cause.
No received answer, source or validation rule was repaired to create success.

Observed calls: Astra 5, Flash 6, query/canonical embeddings 22, Google counts 6.
Astra input/output usage is 76,758/4,803; conservative generation/embedding estimate
USD 1.23127504 plus count contingency 0.36 = **USD 1.59127504 / 6.00**. Outstanding
reservation 0, peak reserved 2.27336254; actual invoice unobserved. Source stores,
169 runtime files, 16 packet and 191 protected files verified before docs edits.
Captured Compiler attempts preserve schema-parsed JSON, not original HTTP bytes.

[Results and exposure diagnosis](../../benchmarks/results/openai_compiler_full_agent_2026-09-16/RESULTS.md)
retain original output hashes. Fresh plans split the first question into two outputs;
code and plans differ from the historical Google 2/3, 3/5 result, so counts cannot
establish a causal model improvement. Next: provider-free exposure diagnosis with
anonymous total/segment and row/column controls, preserving eligibility. No automatic
paid retry, new default, unseen accuracy or release claim follows this run.

## Provider-free exposure follow-up

The [offline follow-up](../../benchmarks/results/candidate_exposure_offline_2026-09-16/RESULTS.md)
reproduces the live exposure from immutable catalog/plan inputs. Exact subject
comparison left the descriptive target and observed table label unresolved; the
total-revenue rows then won on exact metric names. A complete own-axis label
appearing literally in a declared numeric target now supplies a ranking hint.
Unknown identity/applicability stays unknown; source conditions, interpretation,
bundle limits and execution validation are unchanged. No suffix stripping or alias
inference is used. The hint stays in diagnostics, outside Compiler input.

Local replay now exposes both Commerce segment-note cells; four narrative island
payloads remain byte-identical. The numeric island grows from 9 to 18 visible
candidates and 51,302 to 88,405 local candidate-payload UTF-8 bytes because whole
physical rows remain atomic. These are not SDK tokens, cost or a new model answer.
Original source/plan/result artifacts are unchanged; no API call or store write.
The paid result above remains 2/3 complete. Further live validation needs a new
approved manifest/cost cap and must account for the larger numeric input.
Eight anonymous exposure contracts and focused 101 tests pass; full Python 3.13
unittest **1,815/1,815**, no skips (47.747s), audit 83 and import/topology/docs pass.

## Prepared exposure successor

The [new admission packet](../../benchmarks/results/openai_compiler_exposure_admission_2026-09-16_v2/PREPARED.md)
keeps the same three questions, source stores, models, generation controls and call
limits. Runtime source matches the tested `96dcf198` fingerprint. Ten packet checks
pass and two separate-process no-call SDK/runner receipts are byte-identical;
270 predecessor/input files and both original stores are preserved. No paid call,
new answer, fresh ingest, document embedding, or default change occurred.

Actual SDK serialization of the recorded independent first-island inputs gives
77,809 to 114,063 canonical UTF-8 bytes for the numeric request. Its reservation
increases by USD 0.453175; all four narrative request hashes match the paid run.
Five first-request reservations total USD 5.4372125. Adding historical Google/query
embedding usage (USD 0.03165004) and the maximum count allowance (USD 0.72) gives
USD 6.18886254, so the proposed shared cap is **USD 7**. This mixes reservations
with labeled historical usage for sizing, not a future cost prediction or bill.
Fresh plans/retrieval and any permitted repair may change inputs; every call still
requires a reservation within the remaining shared cap, with no automatic rerun.
The original USD 6 preparation draft is retained as unexecuted sizing evidence.
Offline saved-input sizing is excluded from live reads. Separate approval of the
new immutable manifest and cost cap remains required before the single run.
