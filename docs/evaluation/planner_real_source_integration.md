# Planner constraints and saved real-source execution

Provider-free review on clean **`97bd38e1`**, 2026-09-22, confirms that current
execution preserves explicit period and consolidation constraints against saved
NAVER evidence. Five cases with separately authored typed periods reproduce the
old values. Ten controls changing only period or statement scope reject those
same selected values. Production code, historical plans and sources are unchanged.

This continues the [sampled Planner contrasts](planner_remaining_contrasts_result.md)
and refreshes the earlier [real-source coverage replay](real_source_period_coverage.md).
It does not connect the fictional2056/2060 questions to a NAVER2023 source by
changing their company, date or report scope.

## Fixed inputs and result

Five immutable saved cases contain **4,202 catalog rows**, **4,036 numeric rows**
and **eight selected cells**. Original questions, report selections, retrieved
document projections, catalog contents, source IDs, values, formulas and Compiler
choices stay fixed. Separate replay copies add the previously reviewed explicit
period declarations; original paid artifacts are never rewritten.

| Saved case | Explicit period and original statement scope | Reproduced value |
| --- | --- | --- |
| Cash balance | Consolidated, point2023-12-31 | 3,576,456,533,329 KRW |
| Operating margin | Consolidated, whole2023 | 15.40% |
| Operating cash less property/equipment purchases | Consolidated, whole2023 | 1,361,609,576,268 KRW |
| Prior dividends | Separate, whole2022 inside the2023 report | 468,978,562,474 KRW |
| Revenue growth | Separate, distinct whole2023/2022 inputs | 1.76% |

The real compilation, source permissions, V2 validation, numeric execution, final
assembly and ledger phases run with network access denied. The existing test
transport supplies saved internal Compiler choices through its authored V2 wire
adapter. Two empty relationship defaults are the only additions to the old
program model projection. There are no fresh Planner/Compiler samples, actual
retrieval, embeddings, source-store clients or ingestion.

| Replay condition | Observation |
| --- | --- |
| Original historical requirements | 4/5 complete; legacy cash phrase remains incomplete |
| Explicit typed period copies | **5/5 complete**, same old calculation fields and values |
| Consolidation scope alone reversed | **5/5 rejected**, no numeric outputs |
| Measurement year/date alone changed | **5/5 rejected**, no numeric outputs |
| Cash point represented as whole-year | **1/1 rejected**, no numeric output |
| All21 traces | 9 successful, 12 incomplete as expected; ledger21/21 ok |

The negative controls deliberately contradict the original request while keeping
the source and saved selection fixed. Recorded field states isolate the failure:
scope controls have matching company/period and conflicting consolidation;
period controls have matching company/consolidation and conflicting period.
The replay checks that only the specified owner-scope field family changes.

Some rejected saved choices have no authorized source before the mock Compiler;
others fail the source enum or output/input authority check when the unchanged
choice is supplied. Mock schema failures here are local rejection observations,
not provider schema errors. No alternate source is chosen to make a control pass.
The ledger being valid does not imply a complete or semantically correct answer.

The old cash plan contains free text **2023년 말**, without a typed date. That
original plan remains incomplete. Its separately declared **2023-12-31** copy
executes correctly using the same cell. The runtime does not infer a missing
date from the filing or repair historical Planner output. Current model selection
of the right typed date for this real question remains the next sampling boundary.

## Source linkage and report isolation

All eight selected cells reproduce their original own-column period witness.
The exact quote, source span, document hash, table locator and physical cell ID
match the saved attached context. The cash column links **제 25 기** to
**제 25 기          2023.12.31 현재**; annual cells retain their own dated interval
declarations. Raw values, units, column headers and source text are unchanged.
This establishes physical linkage and period compatibility, not independent
semantic correctness or whole-store source coverage.

Production filters retain all **36 saved document occurrences** across five
cases under the2023 annual report and receipt20240318000844. Changing only the
filing year to2022 rejects them, including the prior-dividend case whose value
year is2022. Document scope and measurement period remain distinct.

All four newly sampled synthetic plans remain byte-identical. Their filters
reject the saved NAVER2023 documents. Across their six meanings and eight real
cells, **48/48 pairs** explicitly conflict on both company and period. This is
incompatibility evidence; it is not a successful real-source execution of those
paid synthetic plans or an isolated one-variable period comparison.

## Validation, accounting and next step

Existing focused period/schema/scope/filter contracts pass **125/125**, with no
skips. The packet records **136 replay**, **138 source/linkage** and **88 result
review assertions**, plus **2 documentation tests**. All are provider-free;
new tests or runtime changes were unnecessary. Prior full2267/2267 and audit83
were not rerun. Known saved evidence and authored choices are not blind evaluation,
fresh model accuracy, retrieval recall, full-application or release acceptance.

All **14,761 predecessor files**, **177 production sources**, **24 original store
files** and local settings retain hashes. Five documentation files are committed;
the local packet `benchmarks/results/planner_source_integration_2026-09-22` stays
ignored. Added provider calls/accounting **0**. Shared accounting remains
**USD19.92634743 / 20.32**, remaining **0.39365257**, pending0; no budget increase.

At this handoff, the next step was the two unchanged real questions for **cash balance** and **prior
standalone dividends** under one fresh Planner-only manifest. Review new typed
period/scope choices against the original request and fixed saved evidence,
then replay saved Compiler choices locally. With unchanged14000 input/8192 output
bounds and the existing conservative accounting rates, two count/generation
pairs require **USD0.286608**, fitting a proposed **0.29** cap within the balance.
This is funding feasibility only: exact request capture, criteria and SDK checks
must precede new execution. No Compiler generation, retrieval, ingest, automatic
retry/resume or additional funding is included.

The [completed real-question Planner probe](planner_real_questions_result.md)
now records period1/2 and scope2/2: the cash plan loses the end-of-year boundary
by declaring within_year. Both saved choices replay successfully, which does not
erase that semantic negative. Prior authored and historical results above remain unchanged.
