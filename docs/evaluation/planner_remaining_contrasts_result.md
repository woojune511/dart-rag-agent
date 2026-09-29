# Remaining Planner contrasts: five meanings preserved

The user continued the [single-question result](planner_single_generation_result.md)
with the three remaining frozen questions, `u02/u03/u04`. One fresh manifest ran
once on clean **`14216c6f`**, 2026-09-22, under **USD0.43** within the existing
balance. Production source, prompt, model, schema, input/output limits, local
settings and stores were unchanged.

## Observed result

All **3 counts and 3 generations returned HTTP200**, producing **3 valid plans**.
Assistant review against the original pre-sampling criteria passes **5/5 period
meanings**, **5/5 consolidation scopes** and **3/3 combined questions**.
No transport/schema/runtime error, SDK retry, question retry or semantic repair
occurred. Every sampled output was retained and reviewed.

| Case and output | Raw declaration and operative meaning | Statement scope |
| --- | --- | --- |
| u02 revenue | Year2058, offset0, `within_year`; no invented dates or quarter | Unknown, as requested |
| u03 revenue | Reference2059, offset-3, `whole_year`; operative relative year2056 | Consolidated |
| u03 operating profit | Reference2059, offset-3, `within_year`; operative relative year2056 | Separate |
| u04 cash balance | Exact point `2056-05-31`, with null year fields | Consolidated |
| u04 revenue | Inclusive `2055-07-01` through `2056-06-30`; actual cumulative amount retained | Separate |

The raw seven-field declarations lower unchanged into the existing internal
period types. Each output owns its target, period, reporting-basis and shared
request clauses. All **5 / 9 / 4** mechanical request units are owned across
the respective plans; original spans, text, trailing spaces and punctuation
remain intact. Period references retain the relevant year/coverage/date clauses.
The English standalone instruction in u03 is assigned to operating profit.

All five outputs remain direct lookups with empty child inputs and empty numeric
display units. In u02, “별도의 환산” remains a display instruction and does not
create a separate-statements constraint. In u04, the interval output preserves
**실제 누적 금액** in its basis and **양 끝 날짜를 포함한 실제 누적 금액으로 표시**
in display format. Evidence-binding policies preserve each owner's period and
scope. Shared task scope stays **unknown**, including both mixed-scope plans;
there is no common-scope overwrite.

The actual production scope builder accepts the selected **2060** annual report
and rejects **2055, 2056, 2058 and 2059** report metadata for all three questions.
Model year hints `[2058]`, `[2060,2059,2056]` and `[2055,2056]` do not replace the
explicit selected-report filter. This is local filter construction and metadata
checking; no retrieval, source-cell selection, Compiler or arithmetic runs.

The previously sampled u01 whole-year meaning remains **1/1** in its own packet.
The four-question diagnostic panel is now fully sampled across two separate
admissions on identical production source, with six period/scope meanings reviewed.
These are assistant-authored known synthetic questions, not blinded holdout or
human gold. There is no A/B effect estimate, general accuracy, source availability
or final financial-answer claim. Historical period2/6 and scope6/6 are unchanged.

## Execution and validation

Fresh manifest
`21055ff3bde1c9e9fcd4499737dc2d806acc01b3a4b9eaf2629fcb324969171d`
was consumed before transport. It fixes u02 → u03 → u04 with one fresh count then
one generation each: **gpt-5.6-terra / low / output8192 / default / storefalse**,
input ceiling14000. Complete modeled funding is **USD0.429912**, below cap0.43.
The existing caller changed only batch size, maximum transmissions and cap.
API/admission/invalid-plan failure would stop remaining questions; structurally
valid semantic mistakes would remain uncorrected observations.

Canonical count/generation bytes are **42808/42887**, **44226/44305** and
**42919/42998**, identical to the original corrected-schema requests. Actual SDK
serialization hashes are recorded separately from sorted canonical hashes and
match the capture, two fresh-process mocks and all six live requests.

- **72 caller/control assertions** pass, including later count/generation
  failure preserving the first completed plan, full/partial accounting, no
  third-question dispatch after failure, no resume, request drift, count
  overflow, invalid fields and uncorrected semantic-negative fixtures.
- Two fresh SDK mock processes each pass **19 assertions**, with **17 identical
  files**. Authored mock replies are not sampled model answers.
- **133 offline evidence/review assertions** and **2 documentation checks** pass.
  Consumed entry stops before credentials or transport. Linkage/schema checks
  substantiate preservation; semantic acceptance is the separate assistant review.
- All **14,498 predecessor files**, **177 production sources**, **24 original
  stores** and local settings retain hashes. Five documents are committed;
  `benchmarks/results/planner_remaining_contrasts_2026-09-22` remains ignored.
  Prior full2267/2267 and domain audit83 were not rerun for this source-unchanged run.

## Accounting and next work

| Case | Measured input | Reported output | Reasoning within output | Generation estimate USD |
| --- | ---: | ---: | ---: | ---: |
| u02 | 8,476 | 581 | 136 | 0.028162 |
| u03 | 8,838 | 926 | 134 | 0.033207 |
| u04 | 8,528 | 899 | 140 | 0.032108 |

Generation estimate **USD0.093477** plus **0.03** attempted-count contingency
gives **0.123477** added accounting. Shared accounting is **19.92634743 / 20.32**,
remaining **0.39365257**, pending0. No budget increase or invoice is asserted.
Reported input includes8473/8835/8525 cache-write tokens, with zero cached tokens.
Conservative input2.5/output12 per million covers the short-context cache-write
rate checked against [official pricing](https://developers.openai.com/api/docs/pricing).
The count allowance is a contingency, not a verified count-endpoint tariff.

At this handoff, the next step was to review source-period compatibility and report/scope preservation using
provider-free checks and fixed saved evidence before defining a further
real-source integration probe. The synthetic2056/2060 questions are not queries
for the selected NAVER2023 application store. Any future paid probe needs suitable
source-backed questions, a fresh manifest and complete funding within its bounds;
this completed admission supplies no retry, resume, ingest or additional funding.

The [completed provider-free source integration review](planner_real_source_integration.md)
now retains5/5 explicitly declared real-source answers, rejects ten period/scope
conflicts and preserves the legacy cash-plan limitation. No further provider
call or accounting was added. The original sampled Planner result above is unchanged.
