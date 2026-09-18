# Eight-control narrative review preparation

Prepared on 2026-09-18 from clean `70f70aa0` after the user continued the
provider-free review/budget recommendation. **No API call, live admission,
budget increase or new semantic score** is produced. Shared accounting remains
**8.64771504 / 9**, remaining **0.35228496**, pending **0**.

## Review materials

The [local packet](../../benchmarks/results/narrative_blind_review_2026-09-18/)
reuses the eight previously frozen anonymous sources, their original faithful /
unsupported examples and all **16** captured Compiler request files without
changing their bytes. The existing examples remain assistant-authored semantic
contrasts, not sampled model responses or independent human gold.

- [Reviewer table](../../benchmarks/results/narrative_blind_review_2026-09-18/reviewer/review.md)
  and [JSON template](../../benchmarks/results/narrative_blind_review_2026-09-18/reviewer/review.json):
  eight original sources, the unchanged `Describe the activity.` question,
  **16 not-collected slots**, and null/unfilled decisions.
- [Reviewer-only archive](../../benchmarks/results/narrative_blind_review_2026-09-18/reviewer_packet.zip):
  only the table, JSON template and reviewer instructions. Condition names,
  expected statements, request hashes, generation order and internal validation
  outcomes are excluded.
- The separate local `admin` directory preserves exact source/label provenance,
  captured requests and the condition key. Do not give this key to a reviewer
  before their decisions are fixed. Existing historical responses must not fill
  the new response slots.

These preparation files are immutable snapshots. A future caller copies the
templates into a fresh run/review directory and inserts newly collected responses
there; it never fills or grades the sealed templates in place.

Case order is shuffled once. Existing/adopted instructions are each scheduled
first in **four** cases and displayed as A in **four** cases. The four joint
generation-first / display-A combinations each contain **two** cases. The
recorded local seed and request hashes fix the schedule before any sampling.
A/B presentation is not a condition name or a generation timestamp.

Review checks every sentence for source-supported action/object relationships,
subject, condition, negation, tense, quantified scope and additional claims.
Coverage and unnecessary abstention remain separate fields. Reviewers quote the
relevant response and source spans and may record uncertainty; alternative faithful
wording is allowed. Code does not infer semantic correctness from wording or
source-address validation. The original labels and reasons are not redefined.

Missing, failed or malformed responses remain unavailable rather than receiving
an accuracy score. Review decisions must be fixed before joining the condition key.
Report per-condition faithful-and-complete acceptance and paired better/worse/tied/
uncertain results, with missingness separate. Eight known inputs and one sample
per condition would still be a descriptive pilot, not stable efficacy or unseen
accuracy. The preparer knows the inputs, condition key and prior outcomes and
cannot be described as an independent blinded reviewer. Folder separation is not
access control; style or prior familiarity can also reveal a condition.

## Proposed execution and budget

The [protocol proposal](../../benchmarks/results/narrative_blind_review_2026-09-18/protocol_proposal.json)
is deliberately non-executable. It specifies **8 cases × 2 conditions × 1 response**,
with Astra / medium / Standard / `store=false`, unchanged **5120** output-token
ceilings, and no SDK retry, semantic repair, resume or whole-run retry.

All **16 complete input counts** must precede any generation. A proposed local
admission ceiling of **4000 input tokens per request** bounds planning; it is
**not a measured token count** and does not trim input or change model output
settings. Any larger, missing or invalid count stops before generation.
Reserve all measured inputs, full output ceilings and count allowances first.
Any later provider/refusal/incomplete/schema/usage failure stops the whole batch,
preserving completed responses and unknown-usage reservations, with unexecuted
requests marked not run. There is no partial-arm fallback or automatic cap change.

The [official Standard pricing table](https://developers.openai.com/api/docs/pricing#standard-pricing-data)
was rechecked: the pinned conservative input rate is **12.5** and output rate
**50** USD per million tokens. Count allowance **0.01 per attempt** remains project
contingency, not an observed provider tariff.

| Reservation component | USD |
| --- | ---: |
| Sixteen complete output ceilings, `16 × 5120 × 50 / 1M` | 4.096 |
| Sixteen count contingencies | 0.160 |
| Input at proposed ceiling, `16 × 4000 × 12.5 / 1M` | 0.800 |
| Proposed full-suite maximum reservation | **5.056** |
| Current available allowance | **0.35228496** |
| Additional allowance needed for this ceiling | **4.70371504** |

A practical **USD 5 additional allowance** would move the shared cap from **9**
to **14**, make **5.35228496** available and leave **0.29628496** outside the proposed
suite cap. **This is a proposal; the current cap is still 9.** Reservation is not
predicted consumption, a bill or a guarantee about the unknown count tariff.
No cache discount or release of the historical failed-request reserve is assumed.

A later paid continuation needs accepted budget/scope, a freshly verified batch
caller and a single-use admission bound to its hashes and fixed schedule. The
existing two-count/two-response caller cannot execute this sixteen-request design
unchanged. This preparation does not silently raise its limits or create a live
manifest. The known-source short tie and longer-source difference remain separate
historical evidence; neither is substituted for a newly scheduled sample.

## Local verification

All eight controls and sixteen captured request files preserve their source hashes;
only the already reviewed narrative instruction differs between request conditions.
The 4/4 order balance and 2/2/2/2 joint balance, sixteen empty response/score records,
reviewer archive contents, condition/example exclusion and Decimal budget arithmetic
pass provider-free checks. **Eight negative checks** reject condition leakage,
premature scoring, changed source, missing response slot, oversized/missing/boolean/
nonpositive hypothetical counts. External network attempts **0**; docs **4/4** pass.

All **174** source files, **3067** protected predecessor artifacts, **24** stores
and local settings retain hashes. Prior runtime/full-test results are unchanged
evidence and were not broadly rerun for this documentation/artifact preparation.
Only documentation is committed; no experimental data, condition key or prepared
request is staged. Preparation is complete; sampling and independent review remain
future work under a separately funded scope.
