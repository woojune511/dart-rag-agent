# Multi-sentence narrative comparison

The [prepared six-case comparison](narrative_multisentence_design.md) completed
on 2026-09-18 from clean `77791423`. Both the baseline and adopted narrative
instructions receive **4/6 accepted answers** and **23/25 required content
criteria**. There are **four accepted ties and two rejected ties**, with no
observed better/worse pair. The two shared omissions are described below.
This is a descriptive Compiler-only pilot, not evidence of general instruction
equivalence, DART accuracy or full-agent readiness.

## Fixed scope and collection

The [local packet](../../benchmarks/results/narrative_multisentence_run_2026-09-18/)
preserves the six fictional passages/questions, three Korean and three English,
18 paragraphs, 25 source-linked criteria and balanced schedule frozen during
preparation. Each question requests a summary in at most three sentences.
All original paragraphs remain visible. Only the reviewed narrative instruction
differs; source, question, schema, Astra/medium/Standard/5120/`store=false` are fixed.
No authored answer or reviewer criterion enters the model input.

The user's continuation authorized this exact **6 x 2 x 1** batch within the
existing allowance. Fresh single-use manifest
`5c190bd65ba125ee8eb358c3bef7eb9d291777e8bfcac75fd91c64b1cbd75bce`
was consumed once. All twelve exact input counts (**3709-3859**) completed before
any generation; each was below the 6000 ceiling. The batch reserved every full
5120-output ceiling before dispatch, totaling **USD 3.7580500**, below cap 4.092.

All **12 counts and 12 generations returned HTTP 200**. The twelve first responses
completed in approximately **181 seconds** for the whole batch, without SDK or
whole-run retries, repairs, resume, replacement samples or additional questions.
Response input usage matches the respective count; outputs used **764-1153**
tokens. No Planner, retrieval, embedding, ingest or fresh-store work was executed.
Success here does not establish the cause or permanent resolution of the older 503.

## Separate semantic and execution results

The assistant reviewed the unchanged sampled claims against the complete sources
and all predefined criteria. The record contains **50 criterion decisions** and
**35 claim/clause reviews**, with response/source quotations and reasons. It was
locked before joining condition labels and before reading structural replay
outcomes. The preparer knows the design and can access execution order/telemetry;
label masking is **not independent or securely blinded review**, nor human gold.

| Dimension | Baseline | Adopted |
| --- | ---: | ---: |
| Collected first responses | 6/6 | 6/6 |
| Stated claims faithful to source | 6/6 | 6/6 |
| At most three sentences and request form satisfied | 6/6 | 6/6 |
| Required content criteria retained | 23/25 | 23/25 |
| Fully complete and semantically accepted | **4/6** | **4/6** |
| Unsupported additions / unnecessary abstentions | 0 / 0 | 0 / 0 |
| Compiler/source/execution accepted | 6/6 | 6/6 |

Faithfulness concerns what the response states; required omissions are scored
separately as incomplete. No uncertain or unavailable answer was silently scored
as success. All twelve responses were ready rather than sampled abstentions.
Sentence compliance was assessed across each combined answer, not by a punctuation
counter; eleven contain three sentences and the adopted M06 answer contains two.

| Case | Paired acceptance | Required omission in both responses |
| --- | --- | --- |
| M01: equipment and storage | Both accepted | None observed |
| M02: local and group scope | Both accepted | None observed |
| M03: conditional route trial | Both rejected | R4: delivery-time savings have not been established |
| M04: reporting and inspection coverage | Both accepted | None observed |
| M05: contributors and causality | Both accepted | None observed |
| M06: superseded access proposal | Both rejected | R1: the earlier proposal covered both halls |

For **M03**, both answers correctly preserve the limited northern trial, both
pending expansion conditions, the next meeting as a decision point and the absence
of fixed rollout dates. Neither states the source's separate finding that delivery
time reduction is unconfirmed. R4 required both the effects and date limitations;
retaining only the latter is partial coverage, not a full pass.

For **M06**, both answers correctly distinguish the operating east extension from
the unchanged west period and retain the staffing/no-start-date qualifications.
Both describe the earlier notice as a superseded proposal, but omit that this
proposal covered **both halls**. Mentioning both halls in the current arrangement
does not convey that earlier proposal's scope. This is a completeness finding
under the frozen rubric, not a fabricated claim or an exact-wording requirement.

Untouched sampled JSON was subsequently replayed through the current Compiler
and deterministic execution with external sockets blocked: **12/12** pass,
one saved-response invocation each, zero retries. Frozen prompt/schema/state
match, raw payloads and all 35 claim texts remain unchanged. **87 subject/fact
support occurrences** match exact spans of the original paragraph candidates.
These checks prove physical source linkage and execution acceptance; they do not
detect or excuse the semantic omissions. No runtime rule or contract was weakened.

## Accounting and caller verification

| Accounting item | USD |
| --- | ---: |
| Observed-token estimate, conservative retained rates | 1.1066000 |
| Twelve input-count contingencies | 0.1200000 |
| Added project accounting | **1.2266000** |
| Shared accounting after this run | **10.83356504 / 14** |
| Shared allowance remaining | **3.16643496** |
| Pending reservation / authorized increase | **0 / 0** |

[Official Standard pricing](https://developers.openai.com/api/docs/pricing#standard-pricing-data)
was rechecked on 2026-09-18. The caller retains conservative input/output rates
of 12.5/50 USD per million tokens without a cache discount. The USD 0.01 per
count is a project contingency, not a published count tariff. These figures are
not an observed invoice; the older failed-request reserve remains in shared
accounting. The consumed manifest cannot authorize further paid work.

Before live admission, a mock at the exact USD 4.092 ceiling exposed binary-float
addition producing 4.0920000000000005 and blocking a funded batch. Its failed
receipt is preserved. The **local experimental caller only** now uses Decimal
for budget comparisons/reservations and converts values for JSON receipts after
decisions. No epsilon or increased cap is used. Exact-ceiling admission and
rejection at 4.091999999999999 both pass. Production budget code and request
bodies are unchanged.

Final checks: **11 caller controls**, **27 existing count/admission contracts**,
and **4 documentation checks** pass without external connections. Twelve authored
Compiler rehearsals passed before sampling; these are separate from the twelve
raw sampled replays. All **1857 sealed preparation files**, **4601 predecessor
artifacts**, **174 source files**, **24 store files**, local settings and runtime
owners retain hashes. Only six documentation files are committed; local experiment
artifacts stay outside Git. No full runtime suite or broad benchmark was rerun.

## Interpretation and next boundary

The adopted instruction remains in place, without a new benefit claim or a
prompt patch tuned to these two omissions. Earlier short/eight-case ties, the
single long-source difference and consumed 503 run retain their original findings.
Six purposively authored cases with one response per condition cannot establish
variance, population efficacy or transfer to real filings. This set is now known
development evidence and must not be reused as an unseen test.

The next useful task is a small **real DART retrieval-to-answer check**: preserve
an existing source-complete store, freeze questions and source-grounded required
content, then distinguish evidence exposure from Compiler omission and final
answer rendering. Prepare and validate that scope locally first; a future paid
run needs its own concrete count/cost bounds and fresh single-use admission.
This completed batch does not start that separate run or increase the allowance.
