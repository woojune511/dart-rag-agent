# Planner measurement-period probe preparation

Prepared on 2026-09-21 from clean `e1369d0a`. This is a provider-free proposal
for checking the Planner's interpretation after the
[measurement-period correction](planner_measurement_period.md). No runtime,
prompt, schema, default model, output limit, store or local setting changed.

## Frozen inputs and review criteria

Eight synthetic questions form four contrast pairs. Every question selects the
same fictional company's 2037 annual report and asks about operating cash flow.
The production Planner prompt/schema and ontology remain unchanged; source
inventories are empty. Routing is supplied explicitly to isolate planning.
No report body, retrieval, Compiler call, embedding or ingestion is involved.

| Pair | First question | Contrast | Meaning to review |
| --- | --- | --- | --- |
| p01 / p02 | 2037 selects the document only; explicitly no measurement-year restriction | Measurement also restricted to the 2037 business year | Empty numeric period versus explicit requested year |
| p03 / p04 | Actual cumulative 2036-07-01 through 2037-06-30 | Shift both endpoints to 2037-07-01 through 2038-06-30 | Preserve the entire interval without report-year clamping or unsupported source-absence inference |
| p05 / p06 | Previous business year, with current year explicitly anchored to 2037 | Current business year under the same anchor | Retained relative period with its owned anchor, or correctly resolved 2036 versus 2037 |
| p07 / p08 | Change from 2035 to 2036, using 2035 as the reference | Change from 2036 to 2035, using 2036 as the reference | Separate input periods and exact owned reference/direction instructions |

[Exact questions](../../benchmarks/results/planner_period_probe_preparation_2026-09-21/questions.json)
and [review criteria](../../benchmarks/results/planner_period_probe_preparation_2026-09-21/review_criteria.json)
were frozen before any model sample. Criteria are separate from model inputs;
the harness never loads them. One first response per question is proposed, with
no review-driven retry, repair, prompt edit or question replacement during the run.

Review raw Planner responses and normalized plans separately, including operative
output and child/dependency periods. Literal wording, short labels, output counts
and IDs are not fixed answers. An expected year only in a rationale does not
repair a wrong operative scope. Comparison instructions must remain owned and
intact; this Planner probe does not require Compiler formula variables.
Schema/request linkage is structural evidence only. Errors, incomplete/refused
responses and invalid plans are not correct abstentions or semantic passes.

## Proposed budget

The current application profile stays `gpt-5.6-terra`, low reasoning,
`max_output_tokens=8192`, `store=false`, default service tier, SDK retries zero.
The [official pricing page](https://developers.openai.com/api/docs/pricing),
searched and fetched on 2026-09-21, lists short-context standard input/output
rates of USD 2/12 per million tokens and cache writes at 2.50. The proposal keeps
the existing conservative 2.50 input accounting rate and takes no cache discount.

| Bound | USD |
| --- | ---: |
| One generation at 20,000 input and 8,192 output tokens | 0.148304 |
| Eight full generations | 1.186432 |
| Eight count-call contingencies at 0.01 each | 0.080000 |
| Full accounting envelope | **1.266432** |
| Rounded run cap | **1.27** |
| Current remaining shared allowance | **1.32032307** |
| Remaining after the full run cap | **0.05032307** |

Actual input tokens remain unmeasured. The 0.01 count allowance is an experimental
contingency, not a verified tariff or bill. Canonical UTF-8 request bodies are
35,492–35,696 bytes; bytes are not tokens. A future counted request above 20,000
tokens stops before its generation. Full-batch funding must be checked before
any provider request; the 8,192 output ceiling is not reduced to fit the budget.
Any HTTP/count/usage/plan failure stops later questions without retry. Failed or
unknown generation usage retains the full generation reservation.

## Provider-free evidence and limits

Two fresh-process rehearsals reproduce all eight captured generation JSON bodies
and normalized authored plans. Each executes eight mocked count/generation pairs
through the installed SDK; every count preserves the generation's model-visible
input and schema. Synthetic usage deliberately fills the configured ceilings.
It is neither a token measurement nor a billed model response.

**98 assertions across positive replays and 10 controls pass**: changed query or
report scope and insufficient run/shared funding stop before transmission; count
503 and excess input stop before generation; generation 503, unknown usage and
incomplete output stop after one count/generation pair. A deliberately wrong
2099 measurement period remains structurally accepted, demonstrating why separate
semantic review is required. No semantic accuracy result is assigned to mocks.
Existing transport/count/Planner contracts **49/49** and documentation contracts
**2/2** pass with external connections denied and zero attempted external calls.
The preceding runtime change's full 2,144-test gate was not repeated for this
documentation and experiment-preparation step.

All **11,124 protected predecessor files**, **175 source files**, **24 original
store files** and local settings retain their hashes. Added provider calls and
cost are **zero**; shared accounting remains **18.74967693 / 20.07 USD**, remaining
**1.32032307**, pending zero. Historical paid results remain unchanged.

The [draft proposal](../../benchmarks/results/planner_period_probe_preparation_2026-09-21/draft_manifest.json)
binds questions, criteria, source identity, settings, budget and ordered request
hashes; SHA-256 `950e2b775503e6c75b6e5d035b13152b1759ad7f7c56b3380d5d1d5b51d09912`.
It has no live dispatcher or paid execution authority. A fresh single-use
admission must recheck these bindings and available funding before execution.
Subsequent semantic review should report all eight individual and four paired
outcomes, including partial runs. This diagnostic cannot establish general
accuracy, an A/B effect, source absence, numeric correctness or full-app quality.

Local evidence: [rehearsal A](../../benchmarks/results/planner_period_probe_preparation_2026-09-21/rehearsal_a/verification.json),
[rehearsal B](../../benchmarks/results/planner_period_probe_preparation_2026-09-21/rehearsal_b/verification.json),
[controls](../../benchmarks/results/planner_period_probe_preparation_2026-09-21/controls.json),
[focused contracts](../../benchmarks/results/planner_period_probe_preparation_2026-09-21/focused.json),
[budget](../../benchmarks/results/planner_period_probe_preparation_2026-09-21/budget_assessment.json).
