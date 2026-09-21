# Planner coverage semantics: six-question result

On 2026-09-22, the user's continuation authorized the next independent Planner
period-interpretation check within the existing allowance. Six new questions and
separate criteria were frozen before any response. Four contrast whole-year versus
within-year permission under absolute/relative years; two preserve an exact point
and an inclusive noncalendar interval. This is a new bounded diagnostic, not a
partial rerun of the previous eight questions or an A/B experiment.

**All six first responses completed, but period meaning passes only 2/6.**
The four coverage cases fail; both precise-date controls pass. API/schema success
and request-reference ownership do not establish semantic correctness.

## Frozen semantic review

| Case | Required meaning | Actual operative constraint | Verdict |
| --- | --- | --- | --- |
| c01 | 2045 whole business year | `unresolved` because exact fiscal endpoints were not supplied | Fail: year/whole_year needs no invented endpoints |
| c02 | Any allowed measurement within 2045 | Exact 2045-01-01–2045-12-31 interval | Fail: containment permission becomes exact-interval equality |
| c03 | Prior year under the explicit 2045 anchor, whole year | Exact 2044-01-01–2044-12-31 interval | Fail: unsupported fiscal-calendar endpoints |
| c04 | Prior year under 2045, shorter measurements within that year allowed | `unresolved` | Fail: target 2044 and within_year permission are resolvable |
| c05 | Point 2044-06-30 | `date: 2044-06-30` | Pass |
| c06 | Inclusive 2043-07-01–2044-06-30, actual cumulative basis | Both exact endpoints and cumulative basis retained | Pass |

Coverage cases **0/4**, paired contrasts **0/2**, exact point/interval controls
**2/2**. Raw and normalized measurement objects are identical in all six cases;
the four errors originate in the sampled model choices, not period normalization.
Several rationales describe the desired meaning, but that text does not repair the
operative constraint. The captured prompt explicitly describes both coverage
choices, and the admitted schema contains the required year/relative-year coverage
field. Missing prompt/schema transmission is not the observed failure.

Production filter construction from the six exact saved plans keeps the selected
**2046 report only: 6/6**. c04 emits raw year hints `[2046,2045,2044]`, but the existing
caller-year filter correction preserves report scope. This is filter construction,
not actual retrieval. Combined period/report acceptance remains **2/6**. The old
paid combined **6/8** result and the preceding saved-source **5/5** authored replay
remain separate and unchanged.

## Separate normalization defect

c04 also exposes an unrequested reporting-basis change. Its raw scope is `unknown`,
but normalized scope becomes `separate`. The ordinary instruction
`별도의 특정 날짜나 분기를 지정하지 마.` concerns date selection, not standalone accounts.
The policy marker `별도` matches as a substring; `normalize_scope` then applies that
single query marker to consolidation scope.

An offline replay of the exact raw plan reproduces the changed scope, and the
isolated phrase produces the same marker. Five other scopes remain `unknown`.
This is an additional observed code/policy defect, separate from the frozen period
score. No phrase-specific exception, historical-plan rewrite or runtime fix was
introduced during this experiment.

## Admission, accounting and validation

Clean source **`2be41eb2`**; fresh manifest
`316c54ff1b5233cbdc3e76e68bdaabb1b7ed9d152250a7a155f9477155f5ca71`
was consumed once before transport. Production Terra/low, 8,192 maximum output,
20,000 input guard, default tier, `store=false` and zero SDK retries remain.
Fixed numeric routing and empty inventories isolate Planner. Criteria and saved
answers cannot be read during generation. No Compiler, retrieval, embedding,
ingest or source-store call occurs.

Two fresh-process caller rehearsals reproduce exact requests and authored plans.
**54 controls** cover body/order/scope drift, history-read denial, count overflow,
provider failures, unknown usage, incomplete output, retained failed reserves,
funding and single-use authority. A wrong but well-formed coverage choice remains
structurally accepted, demonstrating the separate semantic boundary. **107 focused
contracts** pass with no external test connections. The initial mock fixture used
an unsupported `scope.subject`; its separate completion uses the existing
`scope.company` field without changing questions, criteria or production.

All **12 actual API requests returned HTTP 200**: six counts and six generations.
No API/parsing/requirement errors, SDK/whole-question retries or semantic repairs.
Input counts equal reported generation input usage in all six cases. The run and
integrity check took about **55 seconds**, with 30-second heartbeats.

| Accounting item | USD |
| --- | ---: |
| Whole-batch ceiling / run cap | 0.949824 / 0.95 |
| Available before the run | 1.00396007 |
| Generation estimate, 51,655 input / 3,031 output tokens | 0.16550950 |
| Six count contingencies | 0.06000000 |
| Added accounting | **0.22550950** |
| Shared accounting / unchanged allowance | **19.54154943 / 20.32** |
| Remaining / pending | **0.77845057 / 0** |
| Peak run accounting including reservations | 0.31709350 |

[Official OpenAI pricing](https://developers.openai.com/api/docs/pricing) was searched
and fetched on 2026-09-22. Conservative accounting keeps USD 2.50/12 per million
input/output tokens without a cache discount. Output includes 354 reasoning
tokens. Count contingencies are not a verified tariff; accounting is not an invoice.
No budget increase was made.

All **12,676 predecessor files**, **176 production source files**, **24 original
store files** and local settings retain hashes. Documentation/syntax/diff gates
pass; the unchanged production source retains its preceding **2,213/2,213** full
suite and audit **83**, without repeating them for this documentation-only result.
Only documentation is committed; packet `measurement_coverage_probe_2026-09-22`
remains ignored. No hidden holdout, independent human gold, general accuracy,
source availability or full-application correctness is claimed.

The [provider-free period-kind clarification](planner_period_kind_clarification.md)
now explains that year plus coverage needs no fiscal endpoints and within_year is
not exact-interval equality. Its saved-plan replay preserves all four failures;
there is no new model result. The ordinary-word consolidation override remains a
separate contract seam. Any later model experiment requires fresh whole-batch
admission; do not retry or repair this consumed run.

Local evidence: [frozen criteria](../../benchmarks/results/measurement_coverage_probe_2026-09-22/review_criteria.json),
[run receipt](../../benchmarks/results/measurement_coverage_probe_2026-09-22/live/run_receipt.json),
[semantic review](../../benchmarks/results/measurement_coverage_probe_2026-09-22/semantic_review.json),
[normalization diagnosis](../../benchmarks/results/measurement_coverage_probe_2026-09-22/consolidation_diagnostic.json),
[evidence checks](../../benchmarks/results/measurement_coverage_probe_2026-09-22/evidence_review.json),
[accounting](../../benchmarks/results/measurement_coverage_probe_2026-09-22/accounting.json).
