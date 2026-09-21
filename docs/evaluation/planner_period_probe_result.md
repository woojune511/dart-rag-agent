# Planner period interpretation: eight-question result

The [frozen eight-question probe](planner_period_probe_preparation.md) completed
on clean `df4be34b` with **8/8 structurally accepted first responses** and
**8/8 accepted period interpretations across all four contrast pairs** under
separate assistant review. All 16 input-count/generation requests returned
HTTP 200. No retry, repair, runtime edit or budget increase occurred.

These synthetic questions select the same fictional 2037 annual report.
The unchanged production Planner uses empty observed source inventories and a
supplied numeric routing hint. This is Planner interpretation evidence, not
retrieval, source-absence, numeric-answer, Compiler or full-application acceptance.

## Observed interpretation and separate review

The exact pre-run questions and semantic criteria retain their hashes. All raw
responses were saved before review, with criteria and historical answer reads
blocked during planning. The review accepts sampled meanings without requiring
the mock fixtures' IDs, labels, wording or number of outputs.

| Case | Operative period in the actual response | Review |
| --- | --- | --- |
| p01 | Empty measurement period; document year remains 2037 | Pass: report-only year does not constrain the scalar measurement period |
| p02 | `2037사업연도` | Pass: explicitly requested measurement year is retained |
| p03 | `2036년 7월 1일부터 2037년 6월 30일까지` | Pass: both interval endpoints and actual cumulative basis survive |
| p04 | `2037년 7월 1일부터 2038년 6월 30일까지` | Pass: shifted interval survives without report-year clamping or unsupported absence claim |
| p05 | `2037사업연도의 직전 사업연도` | Pass: previous business year retains its explicit 2037 anchor |
| p06 | `2037사업연도(당기)` | Pass: current business year remains distinct from the preceding case |
| p07 | Child inputs `2035년`, `2036년`; output basis `2035년 값을 기준` | Pass: both input periods and owned forward/reference instructions survive |
| p08 | Child inputs `2036년`, `2035년`; output basis `2036년 값을 기준으로` | Pass: reverse direction and its reference year survive |

All four pairs are complete and accepted. Each response has one requested output;
the comparison outputs each have two explicit child inputs. The six direct
outputs retain source amount/unit presentation instructions without inventing a
display unit. All fourteen original request units remain owned. Document-year
hints stay 2037 independently of the measurement periods.

Output and child period fields are identical between raw responses and normalized
plans. Canonical IDs and parent-basis inheritance still apply; no period is
repaired after generation. The p05 expression is accepted because frozen criteria
allow an anchored relative period instead of requiring a literal resolved year.
The later [provider-free source-selection diagnosis](planner_period_source_selection.md)
finds that downstream code treats its anchor as the requested year. Comparison
request preservation alone does not establish Compiler endpoint binding or arithmetic.

This is unblinded assistant review of one first response per synthetic question,
not independent human gold, an A/B effect, general accuracy or unseen full-app
quality. The earlier paid missing-evidence result remains partial and unchanged.

## Execution and accounting

The user accepted actual execution within the prepared USD 1.27 cap. Fresh
manifest `8a2875e3c29764a7f9909d48c29f0a7782264ab0a0397fca18bdf6cda36dfb80`
was consumed before transport construction. Only the eight frozen SDK generation
bodies and count projections were admitted, once and in order. The 20,000 input
rejection limit and full 8,192 output ceiling stayed unchanged. Terra/low,
`store=false`, default tier and zero SDK retries remain the app settings.

| Case | Counted / actual input tokens | Output tokens |
| --- | ---: | ---: |
| p01 | 7,106 / 7,106 | 390 |
| p02 | 7,087 / 7,087 | 391 |
| p03 | 7,068 / 7,068 | 471 |
| p04 | 7,068 / 7,068 | 422 |
| p05 | 7,091 / 7,091 | 372 |
| p06 | 7,091 / 7,091 | 369 |
| p07 | 7,092 / 7,092 | 808 |
| p08 | 7,092 / 7,092 | 706 |
| Total | **56,695 / 56,695** | **3,929** |

The 137 reported reasoning tokens are already included in output usage. Every
count equals generation input usage. Conservative accounting retains USD 2.50/12
per million input/output tokens, with no cache discount, as checked against
[official pricing](https://developers.openai.com/api/docs/pricing) on 2026-09-21.
Count contingency remains separate from observed generation usage.

| Experimental accounting | USD |
| --- | ---: |
| Generation estimate | 0.18888550 |
| Eight count contingencies | 0.08000000 |
| Added accounted amount | **0.26888550** |
| Shared accounted / unchanged cap | **19.01856243 / 20.07** |
| Remaining / pending | **1.05143757 / 0** |
| Peak run accounting including reservation / run cap | **0.35871750 / 1.27** |

This is experimental accounting, not an invoice or observed count tariff. Prior
failed-request reserves remain retained. The last plan completed at approximately
59.4 seconds and post-run integrity at 62.9 seconds after consumption; this is
one observation, not a latency benchmark.

## Verification and next step

Two fresh-process rehearsals reproduce the prepared eight bodies and plans;
**36 caller checks** pass before execution. Missing-authority and consumed-manifest
checks separately prevent even transport construction. **88 saved-evidence and
accounting assertions** pass after execution with external connections denied.
Documentation contracts **2/2** pass; production source and its preceding full
suite are unchanged, so no full-suite rerun was required for this experiment.
An initial offline reviewer used a Pydantic method on the request-unit dataclass;
only that reviewer projection was corrected. Its failed script is retained;
no paid response, criterion or runtime contract changed.

All **11,326 protected predecessor files**, **175 source files**, **24 original
store files** and local settings preserve hashes. No store was opened for planning.
Only documentation is committed; execution artifacts remain ignored. The consumed
manifest cannot authorize another run.

The [saved-plan source-selection diagnosis](planner_period_source_selection.md)
now reproduces anchored-relative and full-interval defects without provider calls.
Next implement a structured measurement-period contract; this paid Planner result
does not establish numeric or source-selection correctness.

Local evidence: [run receipt](../../benchmarks/results/planner_period_probe_execution_2026-09-21/live/run_receipt.json),
[semantic review](../../benchmarks/results/planner_period_probe_execution_2026-09-21/semantic_review.json),
[88-check review](../../benchmarks/results/planner_period_probe_execution_2026-09-21/live_review.json),
[accounting](../../benchmarks/results/planner_period_probe_execution_2026-09-21/accounting.json),
[consumed admission check](../../benchmarks/results/planner_period_probe_execution_2026-09-21/consumed_stop.json).
