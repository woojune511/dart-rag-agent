# Planner measurement period and selected report year

The Planner normalizer no longer fills a blank numeric measurement period from
`report_scope.year`. This is a Planner-contract correction: the selected document
can contain values from other periods, and its year is not a requested value's
measurement period. Narrative normalization already followed this rule.

## Contract and limits

- Preserve explicitly declared dates, ranges and relative period labels through
  the existing whitespace normalization. Do not extract or repair a period from
  question keywords, candidate values, report identity or current time.
- Leave an unspecified top-level period empty for every output kind. A child
  keeps its own declared period or inherits its explicitly declared parent
  period; an empty parent cannot lend the report year. Comparisons must declare
  each input's period separately.
- Keep selected report scope and report-year retrieval hints unchanged. The
  original query and owned request units still reach Compiler. Prompt and schema
  descriptions distinguish measurement periods from document selection; no new
  field, enum, model call, retry or provider setting is introduced.
- Empty means no declared period restriction, not missing-evidence proof. A
  question without a period remains answerable from compatible selected sources.
  Code does not interpret the question to decide whether an empty period was
  intentional. If Planner omits an explicit period or declares the wrong one,
  a source-valid but semantically wrong answer can still pass. Both cases remain
  explicit semantic negative controls, not corrected or certified outcomes.
- Preserving a full date range does not establish correct interval interpretation
  or date-level entailment. Source-period checks, source evidence, arithmetic and
  the existing V2 envelope remain independently authoritative.

## Local verification

**14 new contracts / 94 focused tests pass.** Anonymous controls cover blank
numeric outputs and inputs, absent/different report years, explicit full periods,
same-report-year requests, relative/non-calendar periods, multiple outputs,
comparison inputs, parent inheritance and child override. A two-period subtraction
executes to 6 with ledger `ok`; an explicit foreign period stays incomplete with
zero Compiler calls. An unspecified-period lookup can use an older measured
value in the selected report, preserving the source value and unit.

Initial fixture errors referenced a nonexistent plan field, the wrong expression
binding keys/missing required display fields, and a retrieval-only projection key.
Only those test fixtures were corrected; runtime validation was not weakened.
Before-edit records separately reproduce numeric report-year substitution and
rejection of the older source for an unspecified-period request.

**Full unittest: 2,144/2,144 pass**, zero skips (63.810 seconds).
Import/topology/documentation: **24/24**; domain audit: **83 reviewed literals**.
All test gates deny external connections; no external attempt was observed.

**24 saved-replay assertions pass** across the actual missing-evidence, cash-flow
and dividend cases. Exact original Planner response text is parsed again through
the current model and normalizer using the saved source inventories. All three
plans retain identical obligations and requirement errors. Their exact saved
programs/catalogs revalidate and execute with reconstructed V2 envelopes and
valid ledgers. Entire final answer projections equal the preceding presentation
replay, including values, citations and the bounded missing-evidence explanation.
These responses already declare their periods; replay does not measure the new
prompt's effect on fresh Planner generation. No native search or store was opened.
The original paid missing-evidence result remains partial and consumed.

All **11,087 predecessor artifacts**, **24 original store files** and local
settings retain hashes. Three runtime/config files change; source identities,
stored data and historical responses remain unchanged. Added API calls/cost are
zero; shared accounting remains **18.74967693 / 20.07 USD**, remaining
**1.32032307**, pending zero.

The next semantic check should distinguish a report-only year, a requested
measurement period, a relative period and comparison inputs. Existing wrong/blank
period controls cannot be counted as semantic passes. Any fresh provider run
needs its own bounded admission; no consumed draft is resumed by this correction.

Local evidence: [focused](../../benchmarks/results/planner_measurement_period_2026-09-21/focused.json),
[full unittest](../../benchmarks/results/planner_measurement_period_2026-09-21/full.json),
[saved replay](../../benchmarks/results/planner_measurement_period_2026-09-21/replay_result.json),
[handoff](../../benchmarks/results/planner_measurement_period_2026-09-21/handoff.json).
