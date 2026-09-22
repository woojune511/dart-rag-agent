# Simple-RAG final application evaluation

Completed 2026-09-22 on `6083bf36`, with application source unchanged from
`a9270221`. The [frozen panel](simple_rag_final_preparation.md) ran **once** through
the application's service construction and `SimpleRagAgent`: 12/12 completed,
with no provider errors, retries or unrun cases.

Assistant review against the predeclared source criteria finds **9/9 answerable
questions correct, complete and supported**, and **2/3 insufficient-evidence
questions safely abstained**. One successful abstention has an overbroad ancillary
statement. One failure supplies a daily average in place of unavailable actual
daily revenue. These are descriptive results on two familiar filings, not
independent human gold, unseen-company performance or a population accuracy estimate.

## What ran

- Actual `build_app_services` → serialized service operation → `SimpleRagAgent.run`;
  native scoped Chroma/BM25 hybrid retrieval, reciprocal-rank fusion, top-K 8.
  This exercises the application service path, not an HTTP server or Streamlit session.
- A fresh copy of `data/app_nav_2023_20260916`, collection
  `dart_reports_v2_structural-selective-v2-prefix-2500-320`: NAVER2022, receipt
  `20230314001049`, 782 chunks; NAVER2023, receipt `20240318000844`, 1,090 chunks.
  Original stores/settings and previous outputs remain unchanged; no ingest.
- Existing `openai` profile: `gpt-5.6-terra`, low reasoning, output ceiling 8,192,
  `store=false`, standard tier, zero SDK retries. Query embeddings use
  `text-embedding-3-large`, 3,072 dimensions. No Compiler, paid judge or repair call.
- Exactly the frozen question and explicit report scope enter the app. Categories,
  reference values, source anchors and reviewer rubric are excluded from runtime
  input. Whole-source context stays within 65,536 bytes.
- The current user continuation authorized one run under USD5.25, covering the
  full pre-run cost envelope. The authorization was consumed before the first paid request;
  unused allowance does not authorize a repeat. No additional funding was needed.

All raw outputs were hashed before review. The reviewer compared retrieved and
cited text with the separate, previously frozen rubric. This is assistant source
review, without an independent human or blinded second evaluator. References were
authored from stored parser artifacts, not re-audited against fresh DART XML.

## Quality and retrieval

| Signal | Observed result | Interpretation |
| --- | ---: | --- |
| Attempted / runtime completed | 12 / 12 | No ERROR or NOT_RUN cases |
| Correct, complete, source-supported positive answers | 9 / 9 | Lookup, calculation and explanation: 3 each |
| Safe abstention | 2 / 3 | F10 and F11; F11 has the wording caveat below |
| Deterministic empty-scope abstention | 1 / 1 | F10, no answer-generation call |
| Model-decided abstention | 1 / 2 | F11 abstains; F12 does not |
| Positive retrieval support | 9 / 9 | No observed positive retrieval miss in this panel |
| Source-ID consistency | All 12 responses satisfy the contract | F10 has no citations; identity is not semantic support |
| Context omissions / degraded searches / retrieval cache hits | 0 / 0 / 0 | All 12 use hybrid-search telemetry |

| Case | Topic | Source review |
| --- | --- | --- |
| F01 | 2022 consolidated auditor/opinion | PASS: 한영회계법인, 적정 |
| F02 | 2023 issued common shares | PASS: 162,408,594; distinguishes authorized and circulating shares |
| F03 | 2023 consolidated defined-contribution expense | PASS: 3,436백만원, with current/consolidated scope |
| F04 | Audit contract versus actual hours | PASS: 23,000 − 21,619 = 1,381 hours fewer |
| F05 | Female employee share | PASS: 1,776 / 4,383 × 100 = 40.5%; requested inclusion/exclusion preserved |
| F06 | Lease cash flows due in at least one year | PASS: 430,123,658 + 162,147,775 = 592,271,433천원 |
| F07 | Outside-director support | PASS: advance materials/briefings and visits/reports/education |
| F08 | Paid-leave liability classification | PASS: annual leave and long leave due within/after 12 months, measured from reporting-period end |
| F09 | Lease-extension treatment | PASS: reasonably certain exercise; office/vehicle replacement rationale |
| F10 | Kakao shares, absent company scope | SAFE ABSTENTION: no retrieved evidence, no answer call |
| F11 | End-2025 headcount from the 2023 filing | SAFE ABSTENTION WITH CAVEAT: no invented headcount; ancillary period claim is overbroad |
| F12 | Actual search-platform revenue on 2023-12-18 | FAIL: annual revenue divided by 365 substitutes for unavailable daily evidence |

All predefined positive anchor chunks were retrieved. Alternative citations were
also checked: F08 cites `20240318000844:391:283`, whose table body includes the
same required liability prose as the reference at `390:282`. An anchor-ID match
alone was not treated as answer correctness. The three arithmetic answers were
checked offline; the application itself did not execute or validate their formulas.

## Failure and caveat retained

F12 asks for actual revenue on a particular day. The model uses the supported
annual total, 3,589,061백만원, and computes 9,833.04백만원 per day. Its headline calls
this the revenue on December 18. A later note correctly says it is an annual
average and that actual daily revenue is not disclosed. That caveat does not
fulfil the request or the frozen abstention criterion: `abstained=false` and the
answer substitutes an unrequested estimate. The cited annual table and correct
division establish neither that day's revenue nor source support for the headline.

F11 correctly refuses to invent the end-2025 employee count. Its explanation says
the provided material contains only 2023 information, while the cited employee
compensation excerpt also includes a 2022 comparison. We count the safe abstention
separately from this partially unsupported explanation; it is not a fully faithful
answer without qualification.

No question-specific prompt, vocabulary, schema or runtime fix followed these
observations. The default still checks response shape, source identity and caller
scope; it does not enforce semantic support, requested-output completeness or
arithmetic correctness. Those limitations are visible in the saved API projection.

## Time and conservative cost

| Measurement | Result |
| --- | ---: |
| Query loop, 12 cases | 48.26 s |
| Mean / median per question | 4.02 / 4.05 s |
| Mean for the 11 generation cases | 4.37 s |
| Total including service initialization | 57.73 s |
| Answer calls / query embeddings | 11 / 12 |
| Generation input / output tokens | 71,701 / 2,356, reasoning included in output |
| Embedding input tokens | 808 |
| Estimated generation / embedding cost | USD0.20752450 / 0.00010504 |
| Total estimated incremental cost | **USD0.20762954** |
| Shared conservative accounting | **USD21.20953897 / 26.32** |
| Remaining / pending | **USD5.11046103 / 0** |

Per-question times include local instrumentation and result checkpoint writes,
exclude service initialization, and describe this one sequential local run. They
are not production HTTP latency or repeated-trial statistics. F10's empty scope
still causes a query embedding before search returns no hits; only generation is
skipped. It contributes 0.16 s to the 12-case mean.

Cost uses observed provider token usage and conservative rates of USD2.50 per
million generation input tokens, USD12 per million output tokens and USD0.13 per
million embedding input tokens, without cache discounts. These assumptions were
checked against [official pricing](https://developers.openai.com/api/docs/pricing)
on 2026-09-22. This is not invoice reconciliation. Previous accounting
USD21.00190943, including historical loss ceilings, remains intact; pending and
unknown usage are zero.

The earlier [four-pair development comparison](portfolio_workflow_comparison_successor.md)
used a different, fixed-evidence setup. Its Compiler/simple-RAG cost and latency
ratios must not be combined with this unpaired application run into a new
superiority claim.

## Validation and local reproduction

Before transmission, 27 provider-admission/simple-RAG tests passed. A complete
blocked-network rehearsal exercised all 12 cases with 23 mocked HTTP calls.
Six terminal controls passed: HTTP503, missing usage, bad citation, result-writer
failure, exhausted cap and changed question. They verify stop/accounting/persistence
behavior, not sampled model quality. The initially missing tokenizer artifact was
resolved with a local official cache before the successful rehearsal.

After execution, all 135 protected settings/store/prior-artifact files and all 86
runtime/dependency files retain their hashes. The 144 frozen raw files also retain
their hashes after review. The 2,125-test full suite belongs to the preceding
unchanged-runtime transition; it was not rerun for this documentation-only close.

The [saved-response walkthrough](../overview/simple_rag_demo.md) shows every answer
and cited source, including the failure. Desktop and mobile browser checks cover
all 12 selections, exact answer/source rendering, no JavaScript exceptions and no
horizontal overflow. Opening the standalone HTML makes no provider requests.

Local artifacts below are **ignored and not distributed with a fresh clone**.
They reproduce inspection of this saved run when present; they do not promise
identical output from a fresh model call. No new paid run is part of reproduction.

| Artifact | Purpose |
| --- | --- |
| [run.py](../../benchmarks/results/simple_rag_final_2026-09-22/run.py), [checks.json](../../benchmarks/results/simple_rag_final_2026-09-22/checks.json) | Bound experiment adapter and rehearsal controls |
| [authorization.json](../../benchmarks/results/simple_rag_final_2026-09-22/authorization.json), [consumed.json](../../benchmarks/results/simple_rag_final_2026-09-22/consumed.json) | One-run authority, already consumed |
| [live/results.json](../../benchmarks/results/simple_rag_final_2026-09-22/live/results.json) | Per-case completion, usage, budget and timings |
| [raw_freeze.json](../../benchmarks/results/simple_rag_final_2026-09-22/raw_freeze.json) | Hash map fixed before semantic review |
| [review_notes.json](../../benchmarks/results/simple_rag_final_2026-09-22/review_notes.json), [review.json](../../benchmarks/results/simple_rag_final_2026-09-22/review.json) | Source-review decisions and offline metric rollup |
| [demo.html](../../benchmarks/results/simple_rag_final_2026-09-22/demo.html), [demo_qa.json](../../benchmarks/results/simple_rag_final_2026-09-22/demo_qa.json) | Saved-response viewer and browser validation |

| Identity | SHA-256 |
| --- | --- |
| Frozen plan | `f1028bd804c79dcc5bbea349678e2ca6ba75225a95520c142a9a95a037d34a72` |
| Consumed authorization | `ae05c61742fb693827fbe017d88de73116e56cdfae84fabf96f973cb1c8c9543` |
| Raw freeze map | `7b6871607f2554cf3f11a75116fdc6ccccf818c05d08a295dfeb96e61139259a` |

This closes the scoped evaluation/report/demo milestone. Broader independent
evaluation or deployment would be separate work; the final panel is not a new
repair queue or a general financial-answering guarantee.
