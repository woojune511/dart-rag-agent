# Different-source compact-JSON comparison

All four first responses completed and passed the unchanged source/execution and
assistant content checks: **4/4 responses, 6/6 runtime outputs**. In these two
known-source cases, the compact-JSON candidate used **13.19% and 23.21% fewer output
tokens**. Both conditions already completed; this is not a reliability improvement.
One candidate internal display-format description contains Japanese and remains
an explicit presentation-language limitation.

## Approved execution

The user explicitly increased the shared experimental budget from **USD 14 to 15**
after the [input-count result](compiler_compact_json_transfer_count.md). The
[fresh local packet](../../benchmarks/results/compiler_compact_json_transfer_comparison_2026-09-18/)
starts on clean `d55874fa`, retains prior accounting **12.73919659**, and allows at
most **2.26080341** for this run. Account billing settings were not changed.

Manifest `2d77084c...383e1af3` was consumed once. Four new input counts all completed
before any generation, measured the same 15,882/15,965 and 27,399/27,482 inputs,
and fully funded the complete **2.1481** schedule. Execution retained numeric
baseline/candidate then mixed candidate/baseline order, one first response per slot.
All **eight transmissions returned HTTP 200**. No retry, repair or resume occurred.

The caller's input rejection threshold is 30,000, covering the measured sizes;
this threshold is not a claim that four maximum-sized inputs fit the cap. The
actual whole-batch reservation must fit before generation. The original 5,120
output ceiling, model `gpt-6-astra`, medium reasoning, strict schema, `store=false`,
default tier, request bytes and source objects remain unchanged. Only the same
serialization prefix differs within each pair.

## Measured comparison

| Metric | Numeric baseline | Numeric candidate | Mixed baseline | Mixed candidate |
| --- | ---: | ---: | ---: | ---: |
| Input tokens | 15,882 | 15,965 | 27,399 | 27,482 |
| Output tokens, including reasoning | 1,092 | 948 | 1,594 | 1,224 |
| Reasoning tokens | 229 | 183 | 286 | 224 |
| JSON structural whitespace characters | 1,499 | 0 | 2,142 | 0 |
| Provider/schema/execution/content checks | pass | pass | pass | pass |

The candidate adds 83 input tokens per case. Output reduction is 144 tokens
(13.19%) for numeric and 370 (23.21%) for mixed; combined **514/2,686 = 19.14%**.
These independent samples also differ in wording, rationale, reasoning and one
format-description language. The total change cannot be attributed exactly to
whitespace removal. No source quotation was normalized or model response repaired.

## Source and content review

The [frozen preparation criteria](compiler_compact_json_transfer_preparation.md)
were unchanged. Conditions, dispatch order, usage and cost were omitted from the
review projection; the assistant assessment was locked before joining those
fields. The preparer knew the design, so this is not independent blinding or human gold.

- Both numeric responses selected consolidated operating cash flow for 2025 and
  2024: **2,481,608,395 - 2,255,253,477 = 226,354,918 thousand KRW**. Source periods,
  positive sign and scale were retained; the requested computed difference was displayed.
- Both mixed responses selected current and restated previous liquidity totals:
  **12,823 - 16,612 = -3,789 hundred-million KRW**. They separately retained the
  filing's attributed principal cause, a **2,628** decline in cash/equivalents, and
  the comparison-restatement reason, withdrawal of the Selecta sale plan. Neither
  called that withdrawal a cause of the liquidity decline or called cash the sole cause.
- All **four public narrative claims, eight support occurrences and eight numeric
  input occurrences** were checked. Stored narrative spans match exactly; six
  original XML witnesses were verified through the unchanged parser. All 166
  candidate objects equal their original catalog objects. Linkage and arithmetic
  acceptance remain separate from the assistant's semantic judgments.

The mixed candidate's internal `display_format` is Japanese. Its current-minus-
previous meaning matches the request; execution renders **-3,789억원** and the
public narrative claims are Korean. This anomaly remains in the raw response.
The experiment does not certify the final application display or language policy.

## Budget settlement

| Item | USD |
| --- | ---: |
| Prior shared accounting | 12.73919659 |
| Generation usage estimate | 1.327 |
| Four retained count contingencies | 0.04 |
| Added accounting | 1.367 |
| Shared accounting / approved cap | 14.10619659 / 15 |
| Remaining allowance | 0.89380341 |
| Pending reservations | 0 |

The [official rates](https://developers.openai.com/api/docs/pricing#standard-pricing-data)
were rechecked on 2026-09-18. Accounting conservatively prices all input at $12.50
and output at $50 per million tokens, without cache discounts. Historical failed
provider reservations remain retained. These are usage estimates and contingencies,
not invoices; the count endpoint tariff was not observed. The full initial
reservation reached **14.88729659** shared, within 15.

## Verification and next boundary

Caller checks **14/14**, existing transport/count contracts **29/29**, and docs
checks **4/4** pass. Two fresh-process rehearsals yield **36 byte-identical files**;
their counts and missing-output controls are authored, not live model evidence.
All four untouched sampled payloads pass offline runtime reconstruction without
repair; only original JSON object key order is normalized for prompt comparison.
Live execution uses the original frozen request bodies directly.

All **8,012 protected predecessor files**, 174 source files, seven runtime owners,
24 original store files and local settings retain hashes. Only documentation is
committed; local caller controls and experiment results remain ignored. No runtime,
default prompt, store, ingest or local settings change was made.

These are two known-source excerpts with authored plans and one response per
case/condition, not retrieval, Planner, unseen-source or end-to-end application
validation. Next is a provider-free trace of whether the internal display-format
language can reach public output, followed by a separate compact-JSON adoption
decision. This consumed manifest permits no more provider calls.
