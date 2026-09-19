# Additional question criteria

Three questions and their source/semantic review criteria are frozen on clean
`2cb90b59`, following the [native application result](native_application_result.md).
This preparation made **zero API calls**, attempted no network connections and
added **USD 0**. All three questions were unexecuted at that preparation boundary.
The work changes evaluation documentation only, with no runtime or store change.

All requests select NAVER's 2023 annual report, receipt **20240318000844**.
The API input file contains only each question, report scope and diagnostic
flags. Expected answers, source witnesses, overlap review and acceptance criteria
are separate review files; they must not enter a future model request.

## Frozen questions

1. **scope_cash_flow**: NAVER의 2023년 사업보고서에 있는 연결 현금흐름표와 별도 현금흐름표에서 2023사업연도 영업활동현금흐름을 각각 찾아 원문 금액과 단위 그대로 알려 줘.
2. **dividend_policy_status**: NAVER의 2023년 사업보고서 '배당에 관한 사항'을 근거로 현금배당 정책의 산정 기준과 적용 대상기간을 설명하고, 2023사업연도 결산배당이 보고서 작성 시점에 지급 완료된 것인지도 알려 줘.
3. **unavailable_2024_actual**: 선택한 NAVER의 2023년 사업보고서만 사용해서 2024년 1월 1일부터 12월 31일까지의 실제 연결 영업활동현금흐름을 원문 금액과 단위로 알려 줘. 다른 보고서나 외부 자료는 사용하지 마.

## Source and acceptance criteria

| Case | Required interpretation | Source and rejection boundary |
| --- | --- | --- |
| Consolidated/separate cash flow | Consolidated **2,002,233,273,518원**, separate **1,627,845,864,966원**, preserving both labels and source precision | Full cash-flow statements, table 4 in sections 2 and 4; cells `47:0:1` and `39:0:1`. Their attached contexts explicitly bind 제25기 to 2023-01-01 through 2023-12-31. A prior-year column, subsidiary amount, rounded management summary or swapped scope fails. |
| Dividend policy/status | About **15–30% of two-year average consolidated FCF**, with business/debt-repayment considerations; **three fiscal years including 2022**, subject to business/market conditions; FY2023 final dividend still planned, with shareholder approval and payment pending | Five exact spans in the stored dividend-section parent and paragraph node `20240318000844:837:0`. Equivalent paraphrases are allowed. The report's announced approximately 1,190억원/790원 per share is optional detail, not another required output. Do not confuse the earlier interim payment with this final dividend. |
| Unsupported 2024 actual | Explain that the selected evidence does not establish the requested full-year 2024 actual; supply no invented amount | The attached cash-flow period is 2023. Do not relabel it as 2024, return zero for missing evidence, substitute a forecast, or use an outside filing. This is not an exhaustive claim that the source contains no mention of 2024. |

A meaningful evidence-limited answer may pass the third case. A safe explicit
scope rejection before model execution is recorded separately as scope-control
evidence; its semantic answer remains **not assessed**. Provider errors, timeouts,
budget stops and empty responses are not successful abstention.

Future review must separate runtime completion, retrieval coverage, source
linkage and semantic correctness. A numerically correct answer without matching
source axes and citations does not pass full acceptance. Exact source matching
establishes provenance, not correct interpretation. No keyword scorer or synthetic
answer is used to assert semantic success in this preparation.

The numeric witnesses preserve raw document SHA
`234a3df95222e4dbcd55be980bac45431cff091345855747abe611d5db7a4113`,
table payload references, original row/cell objects and attached contexts.
Narrative witnesses preserve both unique parent-text and indexed-paragraph
occurrences. All source files have frozen hashes. Their presence in storage
does not prove future retrieval visibility or candidate selection.

## Overlap and evidence limits

The bounded inventory covers **201 JSON files and 249 distinct question strings**,
with no skipped files or whitespace-normalized exact match to the new questions.
It includes tracked benchmark datasets and named historical question/case/dataset/
manifest files, not every prompt, test, conversation or model-training example.

Existing questions already cover cash flow, dividends and consolidation. One
prior benchmark asks about a 2024–2026 shareholder-return period; this review
instead follows the source's three fiscal years including 2022. The existing
dataset remains unchanged. This is additional same-report coverage with new
wording, **not a blind or unseen holdout**, independent human gold, an A/B result
or evidence of improved accuracy.

## Budget and next step

At preparation, retained accounting was **16.02259344 / 17 USD**, leaving
**0.97740656**, pending zero. This criteria preparation authorized no increase or run.
Current accounting follows the separate [dividend-policy result](dividend_policy_result.md).

| Planning envelope using the previous frozen policy | USD |
| --- | ---: |
| Exact ceiling per question | 1.69972608 |
| Rounded cap per question | 1.70 |
| Three rounded question caps | 5.10 |
| Shortfall to one rounded cap | 0.72259344 |
| Shortfall to three rounded caps | 4.12259344 |

This reuses the prior rates and count contingency without a new pricing lookup;
it is neither a forecast nor an invoice. Per question, the envelope assumes two
Terra calls, at most two Astra calls, four counts and 48 embeddings under the
unchanged full output limits. A fresh plan needing more calls must stop at the
limit, so funding that ceiling does not guarantee task completion.

The first [cash-flow result](scope_cash_flow_result.md) remains **0/2 outputs**,
with unresolved section bindings and no API error. After the located table-heading
correction, a separately authorized [successor](scope_cash_flow_heading_result.md)
now passes **2/2 outputs** against these same criteria, without retry. Both drafts
are consumed. The separately authorized [dividend-policy attempt](dividend_policy_result.md)
returned application HTTP 500 after a numeric payment-status binding failed,
with all 23 external calls successful and the subsequent repair blocked locally.
Two source-supported policy/period claims remain partial internal drafts; no
final answer passed these three required meanings. Shared accounting is
**17.11707679 / 18.27 USD**, leaving **1.15292321**, pending zero.
The dividend draft is consumed and unsupported-2024 remains unexecuted.
The [Planner output-kind clarification](planner_output_kind_boundary.md) is
implemented and tested provider-free; no new sampled answer is established.
The [exact quote-source correction](numeric_quote_source_boundary.md) is also verified provider-free; only the false quote rejection clears, with period checks and old failure intact. Next prepare fresh provider-free application admission/rehearsal on the new source identity. No automatic paid successor, budget increase or consumed-draft reuse; unsupported-2024 remains unexecuted.
This original criteria preparation created no live caller or authorization;
the separate execution owns the accepted increase and consumed attempt.

## Verification and artifacts

**60 provider-free checks** pass: actual API request-schema validation for all
three inputs, two source-cell bindings, five exact prose witnesses, review/input
separation, overlap inventory identity, budget arithmetic and preservation checks.
All **9721 predecessor files**, **174 source files**, seven runtime owners,
**24 original store files** and local settings retain their hashes. Original
Chroma stores were not opened; source inspection reads JSON artifacts only.

Local artifacts: [questions](../../benchmarks/results/native_independent_question_preparation_2026-09-19/questions.json),
[review criteria](../../benchmarks/results/native_independent_question_preparation_2026-09-19/review_criteria.json),
[source witnesses](../../benchmarks/results/native_independent_question_preparation_2026-09-19/source_witnesses.json),
[overlap review](../../benchmarks/results/native_independent_question_preparation_2026-09-19/overlap_review.json),
[budget assessment](../../benchmarks/results/native_independent_question_preparation_2026-09-19/budget_assessment.json),
[frozen identity](../../benchmarks/results/native_independent_question_preparation_2026-09-19/frozen_criteria.json),
[verification](../../benchmarks/results/native_independent_question_preparation_2026-09-19/verification.json).
