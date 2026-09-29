# Final evidence-selection result

Status: **COMPLETE_GATE_NOT_MET**, 2026-09-30. Product adoption: **none**.

The [frozen eight-question comparison](final_selection_contract_preparation.md)
completed all16 selector calls and one embedding request containing eight exact
queries. No answer generation, retry, repair, substitution, resume or question
replacement occurred. All original questions, gold, previous results and the
active v5 store are preserved.

**Complete request-evidence coverage was6/8 for RRF and7/8 for each LLM repeat.**
The selector recovered two previously missing evidence bundles in both repeats,
but lost the required as-of-date support on one previously complete question in
both repeats. The frozen no-regression criterion therefore fails. These are
source-support judgments, not answer accuracy or validated arithmetic.

## Fixed comparison and execution

- Familiar 2023 reports: LG Energy Solution, KakaoBank, NAVER and Samsung
  Electronics; two newly authored questions each, four numeric and four narrative.
- The exact fixed query strings were embedded once using the existing store's
  `text-embedding-3-large`,3,072-dimensional identity:745 input tokens.
- Existing full11 corpus BM25/tokenization code and saved document vectors were
  reused without opening or rebuilding the active Chroma store. Each explicit
  report scope used exact Dense16, BM25 up to24, RRF60 and top8. This is the
  proposed exact-Dense experiment, not a claim to have rerun ANN search.
- Each frozen union contained31–36 candidates,270 candidate occurrences in total.
  The source texts and hydrated metadata matched the stored graph. No gold source
  insertion, truncation or candidate replacement was used.
- A is deterministic RRF top8. B is one selection of up to8 IDs from the identical
  union using `gpt-5.6-terra`, low reasoning,1,024 output-token limit. Both repeats
  use fresh requests with no conversation history. The second repeat reverses
  question order; candidate display uses the frozen source-ID hash order.
- The whole candidate inputs were84,774–120,021 bytes, below262,144. All A/B final
  packets were built through actual SimpleRagAgent serialization, below65,536
  bytes with zero omitted selected sources. B IDs were restored to RRF order.

The current official model information and [standard API pricing](https://developers.openai.com/api/docs/pricing)
were checked before the first paid call. A read-only model metadata request
confirmed account visibility. [Explicit-only prompt caching without breakpoints](https://developers.openai.com/api/docs/guides/prompt-caching)
was used to avoid cache writes; no cached-input discount was assumed. No cache
read tokens were observed. Global/default service tier was fixed.

The full pre-embedding worst-case reservation was **USD8.724097 /10**. After exact
candidate packets were frozen, the reservation tightened to **USD3.600949**.
The observed uncached-rate estimate is **USD1.057661** including embeddings.
For continuity with conservative reporting, charging every selector input token
at the higher cache-write rate gives **USD1.320009**. Neither is an invoice.

## Paired results

PASS means all frozen request slots are supported; FAIL means at least one
required slot is missing. Multiple repeats do not increase the unique question
count. A was evaluated once and reused as the deterministic baseline.

| ID | Type and target | RRF A | LLM B repeat1 | LLM B repeat2 | Finding |
|---|---|---|---|---|---|
| FSEL01 | Numeric: LGES cash reconciliation | FAIL | PASS | PASS | Recovered connected cash-flow statement, net cash change and FX effect |
| FSEL02 | Narrative: LGES credit policy | PASS | PASS | PASS | Equivalent policy wording in connected notes also accepted |
| FSEL03 | Numeric: KakaoBank household allowance ratio | PASS | PASS | PASS | Gross amount/allowance/current period present |
| FSEL04 | Numeric: KakaoBank written-off claims | PASS | PASS | PASS | Both current/prior balances explicitly stated in prose |
| FSEL05 | Numeric: NAVER treasury shares | PASS | FAIL | FAIL | Correct total row selected; separate as-of-date caption omitted |
| FSEL06 | Narrative: NAVER Put/Call rights | PASS | PASS | PASS | Both trigger and exercising party supported |
| FSEL07 | Narrative: Samsung lease policy | PASS | PASS | PASS | Connected lease thresholds and expense method present |
| FSEL08 | Narrative: Samsung benefit discount rate | FAIL | PASS | PASS | Recovered explanatory policy instead of rate/sensitivity tables alone |

| Metric | A | B repeat1 | B repeat2 |
|---|---:|---:|---:|
| Complete questions |6/8|7/8|7/8|
| Numeric questions |3/4|3/4|3/4|
| Narrative questions |3/4|4/4|4/4|
| Mean selected source count |8.000|1.000|1.125|
| Sum of final packet bytes over8 questions |221,275|39,666|49,693|

All8 candidate pools contained a reviewed complete bundle. Thus the observed
differences occur in final selection, not candidate recall. Full candidate
selection still adds input cost even when the eventual answer packet is smaller;
no end-to-end cost saving is established without answer generation.

## What changed in the evidence

For FSEL01, RRF selected subsidiary Ultium cash-flow tables, cash balances and
financing-liability movements. Some requested balance numbers were visible, but
the connected net cash decrease920,458 and FX effect51,274 million KRW were not.
Both LLM repeats selected the full connected cash-flow chunk`81:5`, which was
already in the candidate union. The first RRF balance-linkage slot is marked
UNDETERMINED; the clearly missing reconciliation slot makes the question FAIL.

For FSEL08, RRF delivered discount-rate values, sensitivities and liability totals
from connected and separate notes. These did not explain when or how the
discount rate is determined. Both LLM repeats selected connected chunk`169:41`,
which explicitly states year-end assessment, high-grade corporate bond rates
and present-value measurement of expected settlement cash outflows.

For FSEL05, both LLM repeats selected the correct total treasury-share table
`23:3`, including the5-share difference from the direct-acquisition subtotal.
They omitted`22:2`, containing the2023-12-31 as-of date and units caption, which
RRF retained. The table's retained prefix has `period_focus: unknown`; its
report-year field is not an explicit measurement date. The fixed gold required
the as-of-date support slot, so this is a loss under that criterion. It is **not
an observed wrong-number answer**. Relaxing the caption requirement after seeing
the result would change this finding; that relaxation and rescoring were not done.

This suggests that semantic selection can help distinguish a requested policy or
statement from similar tables, while selecting only the central table may discard
its supporting caption. It does not justify a broad Agentic RAG or product change.
Any future caption-preservation experiment would need a separate general source-
linkage design and new evaluation; no rule was added for this NAVER example.

## Review and verification limits

Condition labels were randomized for24 source packets, and source-support reviews
were saved before reading the A/B mapping. Packet size/source count can reveal
the likely condition, and the same assistant authored and reviewed the panel.
This is neither independent evaluator validation nor independent-report holdout.
Exact quote matching was used to locate evidence, not as the semantic decision.
An equivalent connected-note policy passage was accepted after reviewing its
subject and meaning. Requirements and old gold were not edited after execution.

Before execution, real-SDK mock transport exercised16 selectors and one8-input
embedding batch,8 actual packet fixtures, and five stop controls. After real
candidates were frozen, all16 exact request bodies and8 baseline packets were
rehearsed. Final verification bound16 unique raw responses to the ordered frozen
requests, reconstructed16 B packets, checked24 review-packet hashes and confirmed
caps, original source content, no cache reads and no extra calls.

Selector usage totals **524,696 input /681 output tokens**. Selector wall time was
35.87 seconds; embedding3.76 seconds; offline candidate construction85.29 seconds.
These phase timings exclude preparation/review and are not production latency.
All8 inputs are positive: no answerability confusion matrix, abstention safety,
calculation accuracy or final-answer score is claimed.

The frozen exploratory gate required at least two stable recoveries **and zero
losses on previously complete questions**. Two recoveries pass the first condition;
one stable caption-support loss fails the second. Stop here without prompt tuning,
same-panel rerun or automatic new-report validation.

Local artifacts: `benchmarks/results/final_selection_live_2026-09-30/`.
Requests, source candidates, raw responses and blinded packets:
`D:/CodexArtifacts/dart-rag-agent/final_selection_live_2026-09-30/`.
`paired_rows.json`, `blind_reviews.json`, `analysis.json`, `verification.json`,
`completion.json` and `seal.json` retain the review and execution evidence.
Experiment artifacts remain ignored; no commit, push or runtime adoption occurred.
