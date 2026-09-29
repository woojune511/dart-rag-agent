# New question controls and budget readiness

Prepared 2026-09-17 on `ef7772ae`, without a provider call or runtime change.
Subsequent [first live query](search_display_app_probe.md) on `73a5b68c` failed:
all 25 API requests returned 200, but optional-owner handling discarded both
outputs and produced an empty `ok` result caught by the ledger. Public criteria
0/4; that failed attempt and its consumed manifest remain immutable.
The separate [current-source application run](search_display_current_app.md) completes
2/2 outputs and covers all four required contents, with full semantic acceptance
withheld for one paraphrase-fidelity concern. Shared remainder is now **0.30722246**.
The later [research count/source-scope readiness review](research_count_readiness.md)
confirms source support but reproduces numeric unit/rendering and year-attribution
limits offline. That question remains unexecuted, with no additional cost.
The preparation facts and budget scenarios below retain their original boundary.
Three exact questions and eight source-review criteria are frozen in the
[local packet](../../benchmarks/results/new_question_controls_2026-09-17/).
Questions contain only normal API request fields. Reviewer criteria and source
witnesses are separate and must never be supplied to the runtime as answers,
candidate overrides, Planner outputs or repair feedback.

## Frozen questions and acceptance

All three requests select NAVER's 2023 business report, receipt `20240318000844`.
The existing store is sufficient for this preparation; no fresh ingest is needed.

1. **Shared comparison**
   > NAVER의 2023년 사업보고서 'II. 사업의 내용 > 2. 주요 제품 및 서비스'를 기준으로, 서치플랫폼의 검색과 디스플레이를 같은 두 기준으로 비교해 줘. 각각 무엇을 연결하거나 노출하는 사업인지, 어떤 서비스·상품 개선을 추진하는지 구분해서 설명해 줘.

   Four criteria: search connects information-seeking needs with business activity;
   its improvements cover products/categories and AI search; display exposes
   advertisers' commercial messages; its improvements cover the platform,
   performance ads and video/premium products. Preserve each subject's attribution.
   Source: `20240318000844:21:0`. No invented performance figures or charging model.

2. **Number plus qualified explanation**
   > NAVER의 2023년 사업보고서 'II. 사업의 내용 > 6. 주요계약 및 연구개발활동'에서 연구마감년도가 2023년인 과제는 몇 건인지 알려 줘. 또한 이 절의 연구개발조직 소개가 각 사업단위의 연구개발 관련 업무조직까지 모두 포함하는지, 소개 범위를 설명해 줘.

   Two criteria: **21 completed projects for 2023**, and an explanation that the
   introduction covers organizations mainly doing R&D while excluding R&D-related
   teams within individual business units, which themselves have R&D functions.
   Sources: `20240318000844:56:3` and `20240318000844:54:1`. The 2022 cell is also
   21; equal numbers do not prove correct year selection. The physical witness
   links the year cell `3:0:5` and count cell `3:1:5` in the same column. Total
   154 and ongoing 152 are separate quantities, not the requested count.

3. **Source-limited abstention**
   > NAVER의 2023년 사업보고서 'II. 사업의 내용 > 6. 주요계약 및 연구개발활동'만 근거로, 2023년에 연구가 마감된 각 과제의 개별 연구개발비를 알려 줘. 이 절에서 과제별 금액을 확인할 수 없다면 확인할 수 없다고 명시해 줘.

   Two criteria: explicitly report that individual project costs cannot be
   established from the requested material, and keep that conclusion within
   the inspected scope. The full stored section and its five nodes contain
   aggregate R&D cost and completion counts, not per-project cost allocation.
   Never divide total cost by project count or transfer acquisition amounts.
   A missing numeric result can be correct abstention; a retrieval failure,
   empty answer or API/budget exception is not evidence of successful abstention.

Do not force a fixed Planner output count or relationship. Record whether a
sampled plan actually exercises `shared_basis`; a correct answer without that
relationship does not test the new declaration mechanism. Source linkage,
semantic acceptance, API errors, retries and cost are separate observations.

## Novelty and source limits

The scan covers **766 local benchmark/test JSON files and 974 unique literal
question/query values**, including ignored result directories. All three questions
have zero literal or normalized matches. Previous records include platform-revenue
and R&D-cost ratios, but not these exact tasks. This is a bounded local record
check, not proof of global semantic novelty. The document and some topics were
already used; these are assistant-authored controls, not unseen-document or human
gold evidence. Six immutable source nodes and exact reviewer quote spans are saved.

The research-count table has an additional preparation caveat: its stored cells
have `UNKNOWN` normalized units and the year is a separate same-column row.
The source supports the count; normal retrieval and numeric-candidate exposure
have not been tested for this new question. Preserve that distinction during a run.

## Budget and execution boundary

Shared accounting remains **USD 7.08344260 / 8**, leaving **0.91655740**, pending 0.
Current [official pricing](https://developers.openai.com/api/docs/pricing) matches
the pinned Standard policy: Astra input reserve/output **12.5/50** and Terra
**2.5/12** USD per million tokens; inputs use the cache-write rate conservatively.
The [counting guide](https://developers.openai.com/api/docs/guides/token-counting)
supports measuring complete request inputs, including formatting/schema overhead.
It does not establish a count-specific tariff; **USD 0.01/count** stays a contingency.

| Illustrative attempt shape | Full output plus count allowance | Headroom for inputs and embeddings |
| --- | ---: | ---: |
| Two Terra + one Astra | 0.482608 | 0.43394940 |
| Two Terra + two Astra | 0.748608 | 0.16794940 |
| Two Terra + three Astra | 1.014608 | -0.09805060 |

These reserve Terra's full 8192 and Astra's full 5120 output tokens. They are
scenarios, not predictions of future plans, retries or costs. Three questions
with two Terra/one Astra each require **1.447824** for those full-output/count
reserves before inputs or embeddings. Settled outputs may cost less, so this
does not prove three runs must fail; it means completion cannot be guaranteed.
The earlier known-source run's peak reservation was **0.70076026**, also not a
new-question estimate. Eleven exact-arithmetic/read-only admission checks pass.

All **three API request envelopes validate unchanged**. No new provider input
count, model response, retrieval run, live schema acceptance or execution manifest
exists. All **1494** predecessors, **172** source files, settings and **24** store
files retain their hashes. Documentation checks pass **2/2**; the prior full
**1968/1968** remains applicable source evidence and was not rerun.

Prepared next step (now executed, with failure recorded above): run only `search_display_comparison` through the normal application
with a fresh single-query admission under the remaining cap, full output bounds,
per-call counting and existing single internal repair. Stop on provider/budget
failure without whole-query retry, and reassess remaining funds after settlement
before another question. Fresh plans and responses preclude an isolated causal
retry-reduction claim. This packet completes question/criteria/readiness work;
it does not dispatch that live run.
