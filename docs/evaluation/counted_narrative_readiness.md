# Counted narrative readiness review

Verified 2026-09-17 on `82f1d698`. The read-only review is complete; the local
caller remains non-executable. Public documentation establishes generation
pricing and general access requirements, but does not establish count-specific
tariffs, this account's current endpoint permissions, or complete-run feasibility.

The local [specification and arithmetic](../../benchmarks/results/counted_narrative_readiness_2026-09-17/RESULTS.md)
freeze one exact narrative request envelope and the existing caller policy.
No provider/count/generation/embedding request or authenticated model-list query
was made. No source, local profile, budget cap, store or consumed artifact changed.

The subsequent user-authorized [live experiment](counted_narrative_experiment.md) now
supersedes this read-only stage for execution/account-access status and shared
accounting. Count billing is still unknown; the original mock caller remains
immutable and the separately created live manifest is consumed.

## What official documentation establishes

The current [API pricing table](https://developers.openai.com/api/docs/pricing)
confirms these Standard short-context USD rates per million tokens:

| Model | Ordinary input | Cached input | Cache writes | Output |
| --- | ---: | ---: | ---: | ---: |
| gpt-6-astra | 10 | 1 | 12.5 | 50 |
| gpt-5.6-terra | 2 | 0.2 | 2.5 | 12 |
| text-embedding-3-large | 0.13 | — | — | — |

The pinned input reservations already use the cache-write rates, without assuming
cache savings. The [caching guide](https://developers.openai.com/api/docs/guides/prompt-caching)
separates ordinary, read and write tokens. Charging every input token at the write
rate is a conservative bound for those published categories, not a bill calculation.
The 200,000-input-token ceiling stays below the 272,000-input long-context boundary
on the [Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) and
[Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra) model pages.

The [counting guide](https://developers.openai.com/api/docs/guides/token-counting)
documents authenticated `POST /v1/responses/input_tokens`, input/schema formatting
coverage and response identity. It does not state a count-specific price or that
counting is free. The general Responses pricing statement does not resolve that
endpoint-specific uncertainty. The USD 0.01 allowance remains proposed contingency.

The [permissions guide](https://developers.openai.com/api/docs/guides/rbac) separates
model listing from model requests and evaluates both key and applicable project
role permissions. Listing models would therefore not prove permission to generate
or count. Exact count-specific permission and current account access remain unverified.
An effective local key is present; its value was never recorded. Presence and prior
successful generations do not establish current endpoint permissions.

## Conditional budget thresholds

Shared accounted estimate remains **USD 6.04443577 / 7**, remainder **0.95556423**,
pending 0, not an invoice or account balance. The policy retains 12 generations,
12 counts, 48 embeddings, USD 0.01/count, and full Astra 5120/Terra 8192 outputs.

The following uses the [previous cold-start prefix costs](../../benchmarks/results/narrative_budget_feasibility_2026-09-17/RESULTS.md),
adds the proposed count allowance, and replaces the old byte-based input reserve
with an unknown counted input. Earlier actual usage is historical evidence only.

| Compiler request | Historical prefix USD | Counts through this request | Maximum counted input | Prior generation input usage |
| --- | ---: | ---: | ---: | ---: |
| First, historical 45 | 0.06143277 | 3 | 48,650 | 12,776 |
| Second, historical 46 | 0.24603277 | 4 | 33,082 | 12,772 |
| Third, historical 47 | 0.44033277 | 5 | 16,738 | Unavailable; not transmitted |

For example, the third threshold is the floor of
`(0.95556423 - 0.44033277 - 5×0.01 - 5120×50/1,000,000) / (12.5/1,000,000)`.
Nine below/at/above-threshold checks agree with the existing `ProviderBudget`
preflight and leave its snapshots unchanged; no callback or dispatch runs.

Reusing the first two historical generation input totals as hypothetical counts
would require USD 0.50713277 and 0.70168277 respectively. Those are conditional
reservations, not fresh measurements. The third input, later responses, fresh
planning and number of subsequent calls remain unknown.

Two Terra plus three Astra calls spending their full output limits, plus five
count allowances, require **USD 1.014608 before inputs/embeddings**. That exceeds
the current remainder by **0.05904377**. This illustrated upper-output scenario
does not prove that a run must fail: unused output reservations are released.
It does show why the existing call limits are not a complete-run budget guarantee.

## Current decision

- Public-document pricing/access review and one-question readiness specification:
  complete. Nine arithmetic/preflight checks and two documentation checks pass.
- Actual count tariff, effective count/generation access and complete-run budget:
  unresolved. The protected caller accepts mock transport only; no live admission.
- All **1209** predecessor files, **172** sources, local settings and store bytes
  are preserved. Previous runtime/caller tests remain prior evidence, not rerun.
- Historical paid narrative remains interrupted and its missing responses remain
  unavailable. No inferred tokenizer savings, repaired result or semantic claim.

This readiness-review seam is closed. A live successor needs authoritative
count-specific terms/access evidence and a separately bounded execution decision;
repeating the same public search or another mock preparation would not resolve
those facts. Independent provider-free product work remains possible.
