# OpenAI compiler migration probe

Executed on 2026-09-16 after approval of the exact six-case manifest and USD 6 cap.
All six first responses pass API, strict schema and original execution checks;
all 12 outputs match the frozen criteria. Google remains the default provider.

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
was included. Next: a bounded real-question/compiler integration evaluation with
a new approved manifest, preserving the current inputs and consumed history.
