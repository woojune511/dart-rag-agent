# Two-case axis-provenance probe preparation

Prepared 2026-09-19 from clean `f2c14af4`, following the production
[candidate-local axis projection](compiler_axis_provenance.md). Two current v11
Compiler requests, their full count descriptors, review criteria and proposed
limits are frozen. Two fresh-process SDK rehearsals produce five byte-identical
files, including all four count/generation request bodies. **No actual model or
input-count call was made, and no budget was increased.**

## Scope and review

This is a proposed current-format smoke test: numeric then narrative, one first
response each, with at most two counts and two generations. Both inputs come
from the same known NAVER 2023 application question. They are not independent
holdouts, a paired baseline comparison or a fresh Planner/retrieval/application run.
The historical numeric response and blocked narrative attempt stay unchanged.

- Numeric: read the 2023/2022 Commerce cells, preserve full axes, attached period
  evidence, units and comparison direction, then verify deterministic growth.
  The original values are 2,546,648,516 and 1,801,079,126 thousand KRW; their
  independently computed growth is 41.3957043439745%, or 41.4% at one decimal.
  Source display and calculation intent require separate review.
- Narrative: cover acquisition facts/scope and direct Commerce performance impact.
  Distinguish Poshmark/subsidiary results from segment/group results, actual
  post-acquisition performance from hypothetical full-year consolidation, and
  observed contributions from expected benefits. Retain other source-stated
  growth drivers without asserting sole causation. Review every emitted subject,
  qualifier, number, period and citation; equivalent grounded wording is allowed.
- Both: schema/lowering/source linkage and semantic correctness remain separate.
  Missing/ambiguous output can be valid transport but is not task-quality success.
  Keep raw responses; inspect compact JSON without post-response normalization.
  Review-only criteria and earlier answers are not added to the model prompts.

The frozen bodies preserve current sources, instructions, schemas and settings:
`gpt-6-astra`, medium reasoning, default service tier, `store=false`, no streaming,
5,120 output tokens and zero SDK/HTTP/Compiler retries or repairs. The proposed
caller permits only exact body hashes in the fixed order. Canonical request sizes
remain **89,817 / 65,090 bytes**; full JSON output schemas are included in counts.

## Proposed budget

The [official standard pricing table](https://developers.openai.com/api/docs/pricing#standard-pricing-data)
was fetched on 2026-09-19: Astra short-context input is $10, cache writes $12.50
and output $50 per million tokens. The plan retains **$12.50 input / $50 output**
for conservative reservation without assuming cache savings. The existing
**$0.01 per count** is a contingency; the count tariff and invoice are unverified.

The [official token-counting guide](https://developers.openai.com/api/docs/guides/token-counting)
includes request formatting and model-specific tokenization in server counts;
local bytes are not that measurement. Output ceilings include visible and
non-visible tokens. No current-input server count has been substituted with old
counts, synthetic rehearsal usage or the previous byte-reduction percentages.

Each future input is capped at **30,000 measured tokens** and 100,000 canonical
request bytes. The token ceiling rounds the larger old-wire count of 26,131 up to
a bounded threshold; it is not proof that v11 fits. The old narrative count was
17,529. Any new count above 30,000 stops before that generation without changing
the source input, output limit or budget.

| Full reservation for both cases | USD |
| --- | ---: |
| Input: 2 × 30,000 × $12.50 / million | 0.750 |
| Output: 2 × 5,120 × $50 / million | 0.512 |
| Two count contingencies | 0.020 |
| Proposed batch accounting ceiling | **1.282** |
| Existing experiment remainder | **0.42222155** |
| Additional funding needed at that ceiling | **0.85977845** |
| Minimum top-up rounded upward to cents | **0.86** |
| Recommended top-up, not authorized or applied | **1.00** |

Even output ceilings plus counts alone require **0.532**, above the remainder.
Using both historical counts only as an illustrative scenario would reserve
1.07775; this is not a prediction of the new requests. A $1 increase would make
the shared cap $16 and available allowance 1.42222155, leaving 0.14022155 after
the full proposed ceiling. A later full-app smoke is outside this proposal.

These are conservative local admission/accounting amounts, not a guaranteed
invoice or expected spend. New counts must be checked before generation. Unknown
usage retains reservations; reported usage beyond bounds closes the guard and
rejects the response, but cannot undo a provider overrun. No completion or
semantic-quality guarantee follows from funding the permitted ceilings.

## Rehearsal and next boundary

The packet has an explicit **mock-only** transport with a dummy key and blocked
external sockets. It exercises the installed SDK and existing counted admission
guard against exact frozen hashes. Counts of 30,000 and output usage of 5,120 are
authored maximum-budget controls, not measurements. Schema-valid missing-output
replies prove transport shape only and are not accepted financial answers.

Nine new local controls pass: full-ceiling funding, whole-batch rejection before
even counting when underfunded, input-limit rejection, changed/reordered requests,
invalid/failed counts, a 503 generation failure without retry, usage overrun,
denied third generation, and exact decimal budget/authorization boundaries.
Existing count/provider admission contracts **38/38** and docs **2/2** pass:
**49 total**, no skips or external connections. Two fresh processes agree on
all five captured files and four request bodies.

All **9,079 predecessor files**, **174 sources**, seven runtime owners,
**24 store files** and local settings retain hashes. Only documentation is
committed; packet controls, requests and criteria remain ignored local evidence.
Added accounting **0**; shared **14.57777845 / 15**, remainder **0.42222155**,
pending **0**, not invoice. Production code and defaults are unchanged.

Preparation is complete. A paid successor still needs the additional funding,
a fresh single-use admission and a reviewed live caller binding the exact source,
policy and SDK request hashes plus original lowering/execution authority. This
packet contains no live runner or paid manifest and grants no paid execution,
automatic retry, resume, cap increase or full-app authority. The prior app request
still has no final mixed answer.

Local evidence: [protocol](../../benchmarks/results/compiler_axis_probe_preparation_2026-09-19/protocol.json),
[budget arithmetic](../../benchmarks/results/compiler_axis_probe_preparation_2026-09-19/budget_plan.json),
[review criteria](../../benchmarks/results/compiler_axis_probe_preparation_2026-09-19/review_criteria.json),
[rehearsal comparison](../../benchmarks/results/compiler_axis_probe_preparation_2026-09-19/rehearsal_comparison.json)
and [admission controls](../../benchmarks/results/compiler_axis_probe_preparation_2026-09-19/preparation_controls.json).
