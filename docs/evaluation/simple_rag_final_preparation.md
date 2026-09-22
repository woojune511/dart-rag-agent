# Simple-RAG final panel preparation

Prepared 2026-09-22 on `a9270221`. Status: **PREPARED / PAID EVALUATION NOT_RUN**.
The user continued the proposed question/reference/cost preparation. No runtime,
prompt, retrieval, store, funding or historical-result changes were made.

## Frozen scope

Selected store: `data/app_nav_2023_20260916`; collection:
`dart_reports_v2_structural-selective-v2-prefix-2500-320`. The graph contains
NAVER2022 (`20230314001049`, 782 chunks) and NAVER2023 (`20240318000844`, 1,090 chunks).
These filings are development-exposed. This is a **new source-authored question
panel, not independent human gold or an unseen holdout**. Several questions share
source sections, so the 12 cases are not independent samples.

There are 239 unique prior questions in the inspected tracked benchmark JSONs and
two historical inputs; normalized exact overlap is zero. Manual topic review
excludes repeatedly repaired cash, commerce-growth, acquisition, R&D, FCF and
missing-shipbuilding questions. This does not establish semantic novelty against
every historical prompt. No retrieval rankings or model answers were sampled
while authoring the panel.

Local reproducible artifacts, intentionally excluded from Git:

- [questions.json](../../benchmarks/results/simple_rag_final_preparation_2026-09-22/questions.json): fixed order, exact questions and explicit report scopes.
- [rubric.json](../../benchmarks/results/simple_rag_final_preparation_2026-09-22/rubric.json): reviewer-only facts, exclusions, calculations and source excerpts.
- [plan.json](../../benchmarks/results/simple_rag_final_preparation_2026-09-22/plan.json): source/runtime hashes, future execution constraints and cost assumptions.
- [verified.json](../../benchmarks/results/simple_rag_final_preparation_2026-09-22/verified.json): source anchors, overlap inventory, actual-SDK mock checks and protected hashes.
- [preflight.py](../../benchmarks/results/simple_rag_final_preparation_2026-09-22/preflight.py): provider-free preparation checks; no paid execution mode.

| Input | SHA-256 |
| --- | --- |
| Questions | `39bf4b14388087e06e54db882201cff883a331f0343dceaef21ca50adb2b4261` |
| Rubric | `d9b2fcd1d457a4db1b1f10ae264b97e9d35aeffdc7bd143886c62e2333b685b6` |
| Plan | `f1028bd804c79dcc5bbea349678e2ca6ba75225a95520c142a9a95a037d34a72` |
| Source graph | `76f144b977bfcdf6d0ee5a1145bc4b3b8d82e53d42796a0d02815f6c7e2d421a` |

Only `query` and `report_scope` enter the app. IDs, task categories, rubric,
reference values and source anchors are never retrieval or generation inputs.

## Question and reference map

Exact wording is frozen in the question file. Every positive case has a source
excerpt and matching filing scope checked before sampling. References are review
criteria, not runtime rules.

| ID | Type / filing | Question topic | Required reference |
| --- | --- | --- | --- |
| F01 | Lookup / 2022 | Consolidated auditor and opinion | 한영회계법인; 적정 |
| F02 | Lookup / 2023 | Issued common shares, distinguished from authorized/circulating shares | 162,408,594 shares; distinguish 300,000,000 authorized and 150,613,742 circulating |
| F03 | Lookup / 2023 | Consolidated defined-contribution retirement expense | 3,436백만원, not prior-year1,523 |
| F04 | Calculation / 2022 | Contracted minus actual audit hours | 23,000 − 21,619 = 1,381 hours fewer |
| F05 | Calculation / 2023 | Female employee proportion, fixed-term included and outside workers excluded | 1,776 / 4,383 × 100 = 40.5%, with inputs/formula |
| F06 | Calculation / 2023 | Consolidated lease contractual cash flows due in at least one year | 430,123,658 + 162,147,775 = 592,271,433천원 |
| F07 | Explanation / 2022 | Board secretariat support for outside directors | Advance materials/briefings and site visits/status reports/internal education |
| F08 | Explanation / 2023 | Short/long-term paid-leave benefit liabilities | Current-service annual leave and long leave due within12 months versus long leave due after12 months, from reporting-period end |
| F09 | Explanation / 2023 | Lease-extension recognition and office/vehicle exclusions | Include when reasonably certain; most excluded because assets can be replaced without significant cost/disruption |
| F10 | Insufficient / absent company | Kakao2023 issued shares in this store | Empty explicit company scope; abstain without a generation call |
| F11 | Insufficient / future period | End2025 headcount from the2023 filing alone | Acknowledge missing period evidence; never relabel2023 headcount |
| F12 | Insufficient / daily granularity | Search-platform revenue on2023-12-18 | Acknowledge unavailable daily evidence; never relabel/prorate annual revenue |

The 17 excerpt anchors are in the selected stored graph. F06 also checks the table's
`당기`, consolidated scope, maturity headers and `천원` unit. This verifies the
reference against stored parser artifacts; it is not a fresh audit of original
DART XML or semantic validation of model output. For negative cases, company
inventory, the employee table/date and revenue section review establish the
intended evidence limitation. Exact-date searches only corroborate it; they do not
prove absence from every document.

## Scoring fixed before execution

Record all 12 runtime outcomes as COMPLETED, ERROR or NOT_RUN. Report fully correct,
complete and source-supported answers over **9 answerable cases**, safe abstention
over **3 insufficient-evidence cases**, and attempted/completed denominators.
F10 is deterministic; report F11/F12 model abstention separately. Do not hide failed
or not-run cases, or count an answerable retrieval miss as success because the
model honestly abstained.

Review retrieval support, cited-source entailment, correctness, completeness,
units/display, abstention, latency and estimated cost separately. Anchor-ID hits
are only a retrieval proxy: alternative evidence qualifies after source review
for the same entity, period and scope. Source-ID validity is not semantic support;
offline reference arithmetic does not imply runtime execution.

Freeze raw outputs before rubric review. No paid judge, second attempt, question
replacement or prompt/schema tuning on this panel. A disputed reference remains
DISPUTED with evidence. The report is descriptive, without a general accuracy
threshold or production guarantee.

## One-run cost envelope

Keep the existing `openai` profile: Terra, reasoning low, output limit 8,192,
Responses, store=false, service_tier=default, SDK retries 0. One scoped hybrid
search, k=8, at most 65,536 bytes in the whole-source packet. Embedding remains
`text-embedding-3-large`, 3,072 dimensions. No Compiler, judge, token-count or ingest calls.

Official Standard short-context rates checked 2026-09-22: Terra input 2.00,
cache-write 2.50 and output 12.00 USD/M; embeddings input 0.13 USD/M. Reserve
**2.50 for every input token without cache discounts** for conservative accounting.
[Official pricing](https://developers.openai.com/api/docs/pricing).

| Boundary | Limit |
| --- | ---: |
| Answer calls / query embeddings | At most 12 each |
| Reserved answer input per call | 135,168 |
| Maximum output per answer | 8,192 |
| Reserved embedding input per question | 512 |
| Whole-panel reservation ceiling | USD5.23548672 |
| Proposed one-run accounting cap | **USD5.25** |
| Existing remaining / new funding / new spend | USD5.31809057 / 0 / 0 |

Input reservation is canonical actual SDK-body UTF-8 bytes plus 1,024, not a
provider token count. The unchanged SDK wrapper/schema is 1,094 bytes: doubling
the 65,536-byte JSON packet for outer escaping gives a conservative 133,190 bound,
within 135,168. Each question's byte-based embedding reservation is at most 512.
The ceiling assumes all 12 calls even though F10 should make none:
`12 × (135168 × 2.50 + 8192 × 12 + 512 × 0.13) / 1000000`.
This is a worst-case reservation under stated rates, not an expected invoice.
The future adapter must enforce these limits, the official endpoint and shared
budget before transmission; unknown usage retains its reservation.

## Verification and remaining work

Provider-free checks pass: 12 unique cases (3 per category), explicit scopes,
17 exact excerpts, 3 Decimal references, zero normalized question overlaps and
actual SDK serialization for 11 mocked answers plus 1 no-generation empty scope.
External sockets were blocked. Real retrieval ranking, real embedding, model
quality, provider admission and latency: **NOT_RUN**. All 135 protected settings,
store and prior-artifact files are unchanged; 86 runtime/dependency hashes are
bound. No runtime changes or full test rerun.

Recheck without overwriting the receipt:

```powershell
.\.venv\Scripts\python.exe -B -X utf8 benchmarks/results/simple_rag_final_preparation_2026-09-22/preflight.py --receipt benchmarks/results/simple_rag_final_preparation_2026-09-22/recheck.json
```

The actual-run adapter remains to be prepared: `build_app_services` and unchanged
agent/search, existing cost guards, a verified disposable store copy if Chroma
open writes state, per-case checkpoints and a 30-second heartbeat. Rehearse
embedding admission, failure charging and JSON persistence before paid execution.
Bind that adapter and one future run decision to this frozen plan. Previous
comparison authority is consumed; no automatic run/resume. Then run once, retain
failures, and produce the demo/report without a per-question repair queue.
Accounting remains USD21.00190943/26.32, remaining5.31809057, pending0.
