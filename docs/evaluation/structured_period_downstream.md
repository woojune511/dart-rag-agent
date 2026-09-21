# Saved structured plans: downstream execution and annual coverage

This historical diagnosis is preserved. The [coverage contract successor](measurement_period_coverage.md)
blocks its two partial-year counterexamples without changing these plans or results.

Provider-free replay on `d4a8d7b6` confirms the report-year correction and exposes
a remaining measurement-period boundary: **a partial-year source can pass a
year-only request and be rendered as the business-year amount**. This is an
authored semantic counterexample, not a newly sampled model failure. Production
source is unchanged and the annual-coverage gap is **not fixed**.

## What ran

All eight exact paid plans from the [structured Planner probe](structured_period_probe_result.md)
run unchanged. Thirteen previous synthetic source cells and three explicit
foreign/missing-document-year controls feed an in-memory search double. It returns
the prescribed sources without filtering, so the production retrieval pipeline
must enforce the selected company, report year and report type itself.

The real retrieval, candidate construction, bounded exposure, Compiler V2
conversion/validation, numeric execution, final assembly and ledger phases run.
Compiler choices and their request/axis proofs are authored fixtures using the
existing test wire adapter. The same choice is returned on the single permitted
validation retry; no new choice is invented. Graph expansion stays at its
disabled default. No provider, embedding, real search backend or source-store
client is opened; external sockets are denied.

The first attempt incorrectly supplied candidate-ready `structured_cells` as
search-document metadata. Plain-text recovery produced different row identities
and lost period axes, so fixture admission stopped before retrieval/Compiler.
A separate authored adapter copies the existing row/cell IDs, headers, periods,
values and units into supported parser row records, declaring column positions.
Original bodies, fixtures and failed script remain intact. This is not actual
parsing/ingest validation, source availability or repaired paid input.

## Observed results

| Control | Result |
| --- | --- |
| 21 inherited isolated selections | **21/21 expected outcomes**: correct values execute and rejected alternatives remain incomplete |
| Full pool, eight fixed authored choices | **6/8 complete**; two choices fall outside bounded exposure |
| Swapped comparison inputs and foreign-report-only inputs | **4/4 rejected** |
| Two separately authored visible annual choices | **2/2 complete**, each 140원 |
| Two deliberately wrong visible partial-year choices | Both execute **31원** with yearly answer labels; semantic negatives remain |

The original 33 frozen-choice scenarios retain **31/33** expected outcomes.
Their two failures are not rewritten after the additional controls. All **37**
completed traces have ledger integrity `ok`, including rejected programs and the
two semantically wrong yearly answers. Ledger integrity is not answer accuracy.

Correct isolated/full-pool controls retain prior-year 120원, exact intervals
131원/151원 and forward/reverse comparisons **20% / -16.666666666666664%** from
authored 100/120 inputs. Unknown-period, wrong-period, interval substitutes,
foreign-company, swapped-input and unselected-report controls cannot supply the
requested number. The full-pool source filter removes all four foreign/missing
scope rows from sixteen, leaving twelve numeric candidates; raw axes stay intact.

For p01/p06 full-pool runs, the fixed choices `annual_2035`/`relative_current`
exist in the catalog but are outside the output's two exposed source bundles.
Both attempts reject them as `candidate_not_authorized_for_output_input`.
The visible annual 2037 source and partial 2037 source remain available. Separate
annual choices return 140원 for the unrestricted/current-year plans. This verifies
the exposure boundary; it does not justify widening quotas or prove an
unanswerable request. p01's unrestricted plan does not require the preselected
older value.

## Remaining annual-coverage boundary

p02 and p06 explicitly request the selected report's 2037 business-year amount.
Their exact Planner constraints are `measurement_period.kind=year`, year 2037.
The visible synthetic partial source states **2037-01-01 through 2037-03-31**, with
value **31원**, while the separate annual source is **140원**.

`financial_calculation_execution._period_scope_state` handles `date` and
`date_interval` by comparing complete source shapes, but handles `year` and
`relative_year` using the projected `value_year`. The partial interval therefore
matches 2037. Its original full interval survives in the operand/source proof,
yet both authored selections pass V2 validation and produce yearly final answers.
The proof correctly labels itself `source_linkage_not_semantic_equivalence`.
No code here verifies that the selected interval covers the requested whole
business year; source linkage and same-year matching cannot establish that fact.

Next define an explicit request/source **period-coverage contract** using anonymous
controls for whole-year, within-year, point-date, exact-interval and relative
requests. Preserve the LLM's responsibility for semantic interpretation; do not
infer a fiscal calendar, convert every year request into a calendar interval,
hard-code a metric, widen exposure or repair historical plans. Characterize the
general boundary before implementing the smallest Planner/evidence/execution
change. No fresh paid evaluation is needed to preserve or reproduce these cases.

## Validation and retained state

**510 evidence assertions**, **66 focused contracts**, documentation **2/2** and
syntax/diff checks pass. These checks validate the observations, including the
failures; they are not an all-pass semantic score. Source is unchanged, so the
preceding full **2,176/2,176** and audit **83** are retained, not rerun.

All **12,252 predecessor files**, **176 source files**, **24 original store files**
and local settings retain hashes. Only documentation is committed; packet
`structured_period_downstream_2026-09-21` stays ignored. Added calls/accounting
**0**; shared **USD 19.31603993 / 20.32**, remaining **1.00396007**, pending **0**.
These are experiment allowances/estimates, not an invoice. The original paid
combined **6/8** and its two report-scope failures remain unchanged. No new model
accuracy, real source availability, full-application acceptance or release claim.

Local evidence: [33 frozen outcomes](../../benchmarks/results/structured_period_downstream_2026-09-21/completion_review.json),
[510 checks](../../benchmarks/results/structured_period_downstream_2026-09-21/evidence_review.json),
[annual-coverage counterexamples](../../benchmarks/results/structured_period_downstream_2026-09-21/findings.json),
[four visible choices](../../benchmarks/results/structured_period_downstream_2026-09-21/visible_control_summary.json),
[focused tests](../../benchmarks/results/structured_period_downstream_2026-09-21/focused.json).
