# Canonical-section hybrid selection result

Date: 2026-09-30. Status: **COMPLETE; exploratory gate NOT_MET; not adopted**.

The frozen title-catalog selector recovered two representative sources in both repetitions, but lost two previously delivered sources in both repetitions and one in one repetition. Final answer-input delivery was **A 8/26, B1 7/26, B2 8/26**. These are source-delivery measurements on an exposed diagnostic panel, not answer accuracy or complete-question sufficiency.

## Fixed comparison and execution

- [Preparation](section_hybrid_preparation.md) supplies the frozen prototype, canonical catalogs and question/source mappings. This is a PageIndex-inspired section-selection experiment, not an evaluation of the PageIndex implementation.
- A: report-global saved exact Dense16 + native BM25 up to24, global IDF, RRF60, top8, unchanged SimpleRagAgent input construction with65,536-byte cap. It is not a new production ANN run or the previous Dense32 experiment.
- B: one title-only LLM selection of0–3 disjoint canonical sections, including descendants; apply the resulting scope before Dense16/BM25 up to24, then the same fusion and packet construction. No query rewrite, answer generation, additional search, truncation or backfill. Original packet byte omission behavior remains active.
- All27 frozen questions have two independent selections:54 real Responses calls. Repeat1 uses frozen order; repeat2 reverses it. No shared conversation, retries, automatic resume, substituted models or post-result question/prompt changes. No empty or invalid selections occurred.
- Model `gpt-5.6-terra`, low reasoning, maximum1,024 output tokens, strict structured output, `store=false`, default service tier. A read-only model lookup succeeded before generation;54 completed calls subsequently verified actual compatibility.
- Catalogs contain580 content-bearing canonical nodes over11 reports and15,608 preserved source references. The earlier experimental-only parent repairs and20 empty-node exclusions are unchanged; source-bearing ambiguous paths are not accepted. Selector inputs contain the query, caller report scope, catalog hash and titles; no representative-source mapping, gold answer or original source text.
- Primary analysis:26 representative sources. `SAM_T2_027` remains diagnostic-only because its annotation is unresolved. `HYU_T3_036` tracks the frozen consolidated warranty source while retaining the existing separate/consolidated reference conflict; it is not a whole-answer correctness judgment.

## Results

| Primary source position | A | B repeat1 | B repeat2 |
|---|---:|---:|---:|
| Inside selected section union | Not applicable |15/26|15/26|
| In Dense/BM25 candidate union | See paired traces |14/26|14/26|
| In fused top8 | See paired traces |8/26|9/26|
| Delivered in actual answer-input packet |8/26|7/26|8/26|

The frozen gate required at least two sources recovered in **both** B repetitions and no A-delivered primary source lost in **either** B repetition. The recovery condition passed; preservation failed. Therefore the gate is **NOT_MET**. Repeated generations are not54 independent questions.

| Representative component | A → B1/B2 | Observed boundary |
|---|---|---|
| `MIX_T3_048` connected dividend cash outflow | absent → present/present | Restricting to connected statements and dividends leaves13 of1,064 sources; the witness rises from outside top8 to delivery. |
| `HYU_T3_011` sales mix/material-cost improvement | absent → present/present | Management discussion leaves15 of1,265 sources; the witness reaches top8 and delivery. |
| `CEL_T2_039` US/Canada direct-sales expansion | present → absent/present | Repeat1 selects business overview, other reference matters and management discussion, excluding the witness. Repeat2 selects the broader business section and preserves it. |
| `KBF_T3_044` group total-capital regulatory threshold | present → absent/absent | Both title-based selections exclude the frozen witness despite selecting financial-soundness-related sections. This does not establish that alternative evidence is absent. |
| `HYU_T3_036` consolidated warranty provision increase | present → absent/absent | Correct broad notes scope contains426 sources; witness remains BM25 rank1 but outside Dense16 and fused top8 in both repeats. Section inclusion alone does not ensure fusion retention. |

Each repetition excludes11 primary witnesses at section selection. Of the15 retained, one is outside the candidate union, another six/five fall below top8, and one is omitted by the existing packet byte limit. `MIX_T3_023` reaches top8 in both repetitions but its full chunk does not fit: top8 visibility is not delivery. No chunk was shortened to force it in.

The useful signal is narrow: title-guided scope reduction can recover evidence, while hard exclusion and remaining within-section ranking can remove existing evidence. This experiment does not support adopting the tested hard-filter selector. It also does not prove that all LLM retrieval or all document-tree approaches are ineffective. Close this exposed-panel comparison without tuning and rerunning these questions. No successor or product change was executed.

## All paired components

`Y` means the frozen representative source is included in the actual packet; `N` is its absence, not necessarily unanswerability.

| ID | Representative role | Primary | A | B1 | B2 | B1 stage | B2 stage |
|---|---|---|---|---|---|---|---|
| SKH_T3_080 | 외화환산 이익·손실 | Y | Y | Y | Y | PACKET_PRESENT | PACKET_PRESENT |
| NAV_T3_007 | 연결 영업권 기말·손상 | Y | N | N | N | CANDIDATE_NOT_TOP8 | CANDIDATE_NOT_TOP8 |
| MIX_T3_048 | 연결 배당금 지급 현금유출 | Y | N | Y | Y | PACKET_PRESENT | PACKET_PRESENT |
| HYU_T3_011 | 판매체질·재료비 개선 | Y | N | Y | Y | PACKET_PRESENT | PACKET_PRESENT |
| POS_T1_057 | 연결 영업이익 | Y | N | N | N | SCOPE_EXCLUDED | SCOPE_EXCLUDED |
| SKH_T1_060 | 연결 유·무형자산 | Y | N | N | N | SCOPE_EXCLUDED | SCOPE_EXCLUDED |
| SAM_T3_028 | 연결 재고자산평가손실(환입) 등 | Y | N | N | N | CANDIDATE_NOT_TOP8 | CANDIDATE_NOT_TOP8 |
| CEL_T2_039 | 미국·캐나다 직접판매 확대 | Y | Y | N | Y | SCOPE_EXCLUDED | PACKET_PRESENT |
| KAK_T3_055 | SM 편입과 제작·유통 성장 연결 | Y | N | N | N | SCOPE_EXCLUDED | SCOPE_EXCLUDED |
| HYU_T3_072 | 모셔널 별도 출자·요약손익 | Y | N | N | N | CANDIDATE_NOT_TOP8 | CANDIDATE_NOT_TOP8 |
| KBF_T3_044 | 그룹 총자본 규제 기준 | Y | Y | N | N | SCOPE_EXCLUDED | SCOPE_EXCLUDED |
| KBF_T4_020 | KB데이타시스템 매출·원가 | Y | Y | Y | Y | PACKET_PRESENT | PACKET_PRESENT |
| MIX_T3_025 | 연결 지배기업주주 귀속 순이익 | Y | N | N | N | SCOPE_EXCLUDED | SCOPE_EXCLUDED |
| SKI_T2_069 | 전기 SK에너지 영업이익 | Y | Y | Y | Y | PACKET_PRESENT | PACKET_PRESENT |
| SKH_T2_061 | DRAM 전체 매출 비중 | Y | N | N | N | SCOPE_EXCLUDED | SCOPE_EXCLUDED |
| MIX_T3_063 | 당기 투자 장부금액 순위 | Y | N | N | N | CANDIDATE_NOT_TOP8 | CANDIDATE_NOT_TOP8 |
| SAM_T2_027 | 기술전략 주석의 가우스 | N | N | N | N | SCOPE_EXCLUDED | SCOPE_EXCLUDED |
| SAM_T3_003 | 웰스토리 단체급식 과징금·소송 | Y | N | N | N | SCOPE_EXCLUDED | SCOPE_EXCLUDED |
| CEL_T1_038 | 무형자산상각비·매출 | Y | Y | Y | Y | PACKET_PRESENT | PACKET_PRESENT |
| CEL_T2_073 | 해외·전체 매출 | Y | N | N | N | SCOPE_EXCLUDED | SCOPE_EXCLUDED |
| CEL_T3_015 | 합병 이전대가 총액 | Y | N | N | N | NOT_CANDIDATE | NOT_CANDIDATE |
| CEL_T3_040 | 재고자산 손실·환입·폐기 | Y | N | N | N | CANDIDATE_NOT_TOP8 | SCOPE_EXCLUDED |
| KAB_T3_067 | 연계대출·계좌 수수료 | Y | Y | Y | Y | PACKET_PRESENT | PACKET_PRESENT |
| HYU_T2_035 | E-GMP 모델별 성과 | Y | N | N | N | SCOPE_EXCLUDED | SCOPE_EXCLUDED |
| HYU_T3_036 | 연결 판매보증 기존 충당부채 증가 | Y | Y | N | N | CANDIDATE_NOT_TOP8 | CANDIDATE_NOT_TOP8 |
| MIX_T1_064 | 매출원가·판관비·매출 | Y | N | N | N | SCOPE_EXCLUDED | SCOPE_EXCLUDED |
| MIX_T3_023 | 배출권 회계 인식 문단 | Y | N | N | N | TOP8_BYTE_OMITTED | TOP8_BYTE_OMITTED |

Stage meanings: `SCOPE_EXCLUDED` outside selected union; `NOT_CANDIDATE` inside scope but outside both candidate lists; `CANDIDATE_NOT_TOP8` inside candidates but outside fused top8; `TOP8_BYTE_OMITTED` top8 but omitted by packet cap; `PACKET_PRESENT` delivered.

## Cost, variability and verification

- Selected section sets differed across repetitions for8/27 questions. Eligible source counts over54 calls: minimum6, median424, maximum971. These are scope widths, not semantic coverage scores.
- Provider usage: input185,062, output4,721 tokens, including reported reasoning usage. Estimated standard-rate cost **$0.426776**, excluding any cache discount; this is not an invoice. Rates checked before execution: input$2/output$12 per1M tokens ([official pricing](https://developers.openai.com/api/docs/pricing)). Full-batch conservative reservation was$2.313528 within the$5 cap, based on serialized request bytes plus4,096 input-token allowance and maximum outputs.
- Total measured selector latency129.35s; median2.33s per call, maximum7.39s. This is provider request time, not end-to-end answer latency. Maximum final B packet65,435bytes, within65,536.
- Before payment:54 actual-SDK mocked requests and7 fault controls passed with no network. Guard bound requests to exact hashes/order, model/settings, response schema and budget. Model visibility check was a separate read-only metadata request.
- After generation: independent offline recomputation verified54 request/raw-response bindings, scope unions, Dense filters, native BM25 rankings, RRF packets and usage receipts. All27 A packets matched the saved baseline. Both offline evaluation and verification recorded zero network attempts. This is independent computation within the same agent workflow, **not an independent semantic evaluator**.
- Answer generation, answer accuracy, arithmetic, whole-question sufficiency and abstention confusion matrix: **NOT_RUN / NOT_EVALUATED**. Fresh embedding calls0; actual selector calls54; retries0. Runtime, parser, active store and prior strict answer gate11/14 NOT_MET remain unchanged.

## Local evidence

- Local directory: `benchmarks/results/section_hybrid_live_2026-09-30/` (ignored experiment artifacts).
- Bulk directory: `D:/CodexArtifacts/dart-rag-agent/section_hybrid_live_2026-09-30/`.
- `manifest.json`, `policy.json`, `calls.json`, `pricing.json`, `preflight.json`, `model_availability.json`, `admission.json`, `consumed.json` freeze and admit the one-shot execution.
- `execution.json`,54 raw provider responses,54 parsed outputs,54 selection records and receipts preserve actual execution. Frozen requests,54 retrieval traces and54 final packets support replay.
- `paired_rows.json`, `paired_components.json`, `analysis.json`, `verification.json` contain per-repeat positions and independently checked usage. `completion.json` and `seal.json` record final preservation and hashes after documentation checks.
- Prior experiments and their initial rejected attempts remain intact. No staging, commit, push or experiment artifact publication.
