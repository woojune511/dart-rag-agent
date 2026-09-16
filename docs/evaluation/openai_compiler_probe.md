# OpenAI compiler migration probe

Prepared on 2026-09-16. This is a compiler-only alternative, not a change to the
default provider or evidence of live OpenAI acceptance.

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

## Candidate settings

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

Apply to `llm_routes.program_compilation` only after a successful bounded probe.
This generation-provider change does not require rebuilding the embedding store.
The current official model route was resolved to `gpt-6-astra`; account access
has not been tested. Sources: [migration parameters](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md#migration-quickstart),
[structured output constraints](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas),
and [API prices](https://developers.openai.com/api/docs/pricing).

## Prepared comparison

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

The proposed cap is **USD 6.00**. Six independent request reservations sum to
**USD 4.73755** using canonical UTF-8 request bytes plus 1,024 as a conservative
input estimate and all 5,120 output tokens per call, including reasoning.
Input accounting uses the **USD 12.50/M cache-write rate** for every input token,
above the USD 10/M uncached and USD 1/M cached rates; output uses USD 50/M.
This stays below the long-context threshold. These are conservative accounting
amounts, not measured token counts, latency, official invoices or a billing guarantee.

Before a paid run, finalize the successor manifest on a clean, committed build,
verify file/request hashes and obtain approval for that exact manifest and cap.
The runner consumes one start marker, prints a 30-second heartbeat, stops on
provider/budget errors, and preserves partial failures without rerunning them.
Actual schema acceptance, semantic accuracy, availability and cost remain unmeasured.
