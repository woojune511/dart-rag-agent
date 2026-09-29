# Final evidence selection: contract preparation

Status: **COMPLETE_OFFLINE_PREPARATION**, 2026-09-30. Live experiment: **NOT_RUN / NOT_ADMITTED**.

The [capacity audit](evidence_capacity_audit.md) found seven exposed questions with
feasible missing evidence bundles inside the frozen candidate pool. This motivates
a final-selection comparison, not another document-section router. The default
SimpleRagAgent, retrieval, parser and stored documents are unchanged.

## Old evaluation dispositions

Original questions, gold and saved outputs are preserved. No historical scores
are recomputed. The local `held_contracts_v2.json` retains each original record,
source references, successor wording and explicit limitations.

| Original ID | Disposition | Source-grounded boundary |
|---|---|---|
| HYU_T3_036 | Corrected gold, same question | Connected current warranty provision increase is 2,175,691 million KRW; 1,569,085 belongs to separate statements. Recall experience explains recognition, not attribution of the entire increase to one engine. |
| SKH_T2_061 | Development successor | Ask for the disclosed DRAM share, 63%; the reviewed evidence does not supply direct operands for the original recalculation requirement. |
| KAK_T3_055 | Development successor | Distinguish qualitative SM consolidation effects, acquired intangible assets of 608,409,502 thousand KRW, and ending intangible assets plus goodwill of 5,688,507,563 thousand KRW. 4,065,637,170 is the goodwill column, not the total. |
| SAM_T2_027 | Development successor | Preserve DX/DS share calculation, ask for explicitly DS-labelled R&D achievements instead of inferring future profit-defense strategy or attributing corporate Gauss disclosure to DS. |
| CEL_T2_073 | Development successor | Connected geographic foreign revenue share is 376,681,248 / 2,176,431,531 = 17.31%; geographic foreign sales, exports and separate sales are not interchangeable. Describe the stated distribution-cost initiative, not a measured causal margin contribution. |
| HYU_T2_035 | Development successor | Separately ask for the 2021 E-GMP IONIQ5 mention and IONIQ6's three 2023 World Car Awards; do not transfer the 2022 IONIQ5 awards into 2023. |
| MIX_T3_063 | Still held | A complete current connected investee universe has not been verified. Two large observed holdings do not establish an exhaustive top-two ranking. No replacement numerical gold is approved. |

Five successors change the requested task and are development material. They are
not fresh evaluation questions or repaired historical successes. The remaining
ranking hold does not block the separate new-question panel.

## Frozen new questions

Eight positive, source-authored questions on four familiar 2023 reports are frozen
before retrieving any new-query candidates. Four require numerical evidence,
four require narrative distinctions. None depends on the seven old questions.

| ID | Report | Target |
|---|---|---|
| FSEL01 | LG Energy Solution | Reconcile opening/closing cash with net cash change and exchange-rate effects |
| FSEL02 | LG Energy Solution | Distinguish new-customer credit-limit policy and bank credit-rating condition |
| FSEL03 | KakaoBank | Household loan allowance divided by gross carrying amount, current period |
| FSEL04 | KakaoBank | Current/prior written-off claims outstanding and increase |
| FSEL05 | NAVER | Total ordinary treasury shares: opening, closing, disposal and cancellation |
| FSEL06 | NAVER | Put/Call trigger, exercising party and effect |
| FSEL07 | Samsung Electronics | Short-term/low-value lease thresholds and expense recognition |
| FSEL08 | Samsung Electronics | Defined-benefit discount-rate timing, benchmark and valuation purpose |

An inventory of 73 local question/gold files contains 181 distinct questions.
Exact duplication checks and review of related targets were performed. An initial
KakaoBank liquidity-management draft overlapped a prior question and was rejected
before freezing. This is not proof of semantic independence: the same assistant
authored the panel from familiar reports. No candidate-rank or model-outcome
screening was used to select the eight questions. They may all be easy for RRF.

Gold contains request slots, exact source-body spans, reference answers and numeric
tolerances. It is separate from the selector input. Reference calculations are
evaluation data; the proposed experiment does not execute model answers.

## Proposed bounded comparison

This is a proposal for a separate live admission, not authorization to run it.

1. Keep the existing v5 full11 store fixed. Obtain embeddings for exactly the
   eight frozen query strings using its existing embedding model identity.
   Do not reuse a different question's vector or insert known gold sources.
2. Freeze each report-scoped exact Dense16 / BM25 up to24 candidate union,
   scores, RRF60 order and top8 baseline. Retain all questions, including misses.
   Source snapshots and hashes must precede selector calls.
3. A is deterministic RRF top8. B is one LLM selection of up to8 IDs from the
   identical full-source candidate union. No re-search, section routing,
   calculator or answer generation. LLM sees neither retrieval scores nor gold.
   Candidate presentation order is SHA256(source ID) order in both B repetitions.
4. Run B twice in fresh conversations: **16 selector calls maximum**, eight
   embedding inputs maximum, zero answer calls. Proposed model is
   `gpt-5.6-terra`, low reasoning, output limit1,024; unavailable model stops the
   experiment without substitution. Repeat1 uses question order, repeat2 reverse.
   A has one deterministic result reused for comparison, not two independent runs.
5. Selector system+JSON input is at most262,144 UTF-8 bytes; original source text
   is preserved. The projected context fields match the product field whitelist;
   this is not a claim that every stored metadata field is delivered. No source
   truncation or dropping candidates to pass the limit. Selected IDs are returned
   to frozen RRF order before final packet construction, isolating membership.
6. Both final packets must use actual SimpleRagAgent construction and fit65,536
   bytes with zero omissions. Packet construction parity is a **pending live
   admission gate**, not established by the selector fixture tests.
7. Proposed total ceiling is **USD10 including embeddings, both selector repeats,
   input and output/reasoning tokens**. Before any paid call, verify current model
   availability, context limits, pricing and conservative worst-case reservation
   for the entire batch. No discounted/cached-input assumption. Recheck exact
   packets before selection. If reservation is infeasible, stop; do not silently
   reduce questions, truncate evidence or increase the ceiling.
8. No retry, repair, resume or question replacement after retrieval or outcomes.
   A provider/contract/cap error stops the remaining batch, recorded as NOT_RUN.
   A retrieval miss remains a retrieval miss; do not supply a gold candidate.

The experiment-only `selection_contract.py` has no provider client or execution
loop. Its reservation check validates supplied limits; it does not verify a live
price or grant execution authority. Actual candidate snapshots, embedding code,
provider runner and budget accounting still require the separate admission work.

## Evaluation frozen before calls

Primary endpoint: all requested source slots supported in the final packet with
the requested period, subject, scope and unit. An exact source-ID match is not
semantic sufficiency. Review equivalent evidence against the fixed slots without
changing question or requirements. Unclear evidence stays UNDETERMINED and cannot
count as a win. Blind A/B labels during source review; this is same-assistant
review, not an independent evaluator.

Report candidate-pool coverage, A/B packet slot coverage, source IDs, whole-packet
bytes, source count, tokens, conservative cost and elapsed time per unique
question and by numeric/narrative type. Separate retrieval misses, final-selection
losses, size/format failures and undetermined cases. Eight all-positive questions
do not support an answerability confusion matrix, hallucination safety result,
final-answer accuracy or corpus-insufficient behavior claim.

Exploratory continuation criterion: at least two unique questions where B covers
all slots in both repeats and A does not; zero questions where A covers all slots
and B loses coverage in either repeat; no execution/contract errors. Retrieval
misses and undetermined cases cannot be credited as gains. Even a pass only
justifies separate validation on new reports. A tie, uniformly high coverage or
failed gate ends this panel without prompt tuning or product adoption.

## Offline verification and artifacts

Seven network-blocked contract tests pass: frozen quote bindings, full-source
preservation/gold isolation, unknown/duplicate/output ID rejection, report scope,
input size/no mutation, reservation limits and original-record preservation.
Fixtures are built from reviewed gold witnesses only to test serialization;
**they are not genuine retrieved candidates or an experimental result**.

Local artifacts: `benchmarks/results/selection_contract_preparation_2026-09-30/`.
Source snapshots: `D:/CodexArtifacts/dart-rag-agent/selection_contract_preparation_2026-09-30/`.
These remain ignored experiment material, separate from source/docs and historical
artifacts. `freeze.json` fixes questions/contracts; `completion.json` records
checks and preservation; `seal.json` hashes the completed package.

Calls, new embeddings and cost: **0 / 0 / USD0**. Candidate retrieval, selector
quality and comparative cost: **NOT_RUN**. Next executable step is separate
admission and a monitored eight-query candidate freeze, after the budget and
provider preflight gates above; this preparation does not auto-launch it.
