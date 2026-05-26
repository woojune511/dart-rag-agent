# 실행 계획

> 이 문서는 **현재 active plan만 유지하는 실행 문서**다.  
> 과거 실험과 장기 방향은 [DECISIONS.md](C:/Users/geonj/Desktop/research%20agent/DECISIONS.md)와 [docs/planning/backlog_and_next_epics.md](C:/Users/geonj/Desktop/research%20agent/docs/planning/backlog_and_next_epics.md)로 보낸다.

## Active Snapshot

| 항목 | 현재 상태 |
| --- | --- |
| 현재 1순위 | **`structural_parent_hybrid_v2` 실험을 설계하고, structural routine default 위에 다음 ingest 후보를 정의** |
| 지금 하지 않을 것 | 범용 agent 확장, broad web workflow, cosmetic retrieval tuning |
| 다음 큰 순서 | `ingest candidate selection -> next chunking experiment -> concept-only planner canary -> DART multi-document reasoning` |

## Immediate Focus

- curated dataset 연결과 parser baseline regression은 1차 기준선까지는 지나갔다.
- active benchmark track은 이제 `curated_single_doc_core`, `curated_runtime_contract_gate`, `multi_metric_numeric_smoke`, `curated_multi_report_smoke`를 기본으로 본다.
- `dev_fast*`, `dev_math_*`, `release_generalization`은 2024 legacy dataset 기반 historical asset으로만 유지한다.
- 공식 gate 비교 결과는 현재 다음처럼 정리된다.
  - `plain_prefix_8000_400`: speed / cost baseline, 그러나 `SKH_T1_060` FAIL
  - `contextual_selective_v2_prefix_2500_320`: quality baseline, 대표 gate PASS
  - `structural_selective_v2_prefix_2500_320`: 대표 gate PASS, multi-entity gate PASS, broader curated blocker close까지 확인된 current operating default
- 지금 가장 가까운 구현 초점은 **next ingest experiment design + concept-only planner 확대 검증** 이다.
  - `SAM_T2_002`, `MIX_T1_046` wider curated blocker는 현재 PASS로 닫혔다
  - fresh structural store 기준 `SAM_T2_002`도 multi-source receipt inventory + dependency binding guard 보강 이후 `numeric_final_judgement = PASS`로 재확인됐다
  - 다만 `SAM_T2_002`는 mixed benchmark wording(`메모리 반도체 업황 악화에도 불구하고`)을 충분히 반영하지 못해 `completeness = 0.7`이 남아 있다
  - `SKH_T1_060`는 structural note-aggregate query-surface / acceptance hardening 이후 다시 PASS로 닫혔다
  - `MIX_T1_064`는 targeted official rerun까지 닫혔다
    - `numeric_equivalence = 1.0`
    - `numeric_grounding = 1.0`
    - `numeric_retrieval_support = 1.0`
    - `numeric_final_judgement = PASS`
  - `NAV_T2_006`도 official targeted rerun까지 닫혔다
    - `faithfulness = 1.0`
    - `completeness = 1.0`
  - routine curated validation은 `structural_selective_v2`를 기본값으로 본다
  - `contextual_selective_v2`는 arbitration-only quality reference로 유지한다
  - 다음 실험 후보는 `structural_parent_hybrid_v2`처럼 parent/section/table lineage를 더 보강하는 쪽으로 잡는다

## Active Workstreams

### 0. Ingest candidate selection

| 항목 | 내용 |
| --- | --- |
| 목표 | `plain / structural / contextual` 3자 비교를 정리한 뒤, structural default 위에서 다음 ingest 후보를 설계 |
| 현재 자산 | `curated_runtime_contract_gate`, `curated_multi_entity_grounding_gate`, `structural_selective_v2`, broader curated blocker close, winner ranking policy |
| 현재 문제 | `structural_selective_v2`는 이제 default로 굳었지만, 다음 ingest 실험 후보(`structural_parent_hybrid_v2`)를 어떤 평가 축으로 볼지 아직 설계가 덜 됐다. `contextual_selective_v2`는 품질은 좋지만 ingest 비용이 너무 크고, `SAM_T2_002`에는 narrative completeness calibration이 조금 남아 있다 |
| 다음 할 일 | structural default는 고정하고, `structural_parent_hybrid_v2` 실험 설계와 concept-only planner 확대 검증으로 넘어간다. 병행해서 `SAM_T2_002` mixed-query wording calibration은 benchmark maintenance로 처리한다 |
| 종료 조건 | `structural_selective_v2` default가 운영 문서와 curated profile에 고정되고, next ingest experiment 비교 축이 정의됨 |

### 1. Planner and synthesizer contract

| 항목 | 내용 |
| --- | --- |
| 목표 | planner는 재료 수집만 하고, final synthesizer가 질문 충족 여부와 최종 refusal을 책임지는 구조 정착 |
| 현재 자산 | concept-only ontology v3 draft, LLM concept planner, lightweight validator, `planner_feedback`, `plan_loop_count`, aggregate synthesizer |
| 현재 문제 | direct false positive를 hard acceptance contract로 막는 규칙을 더 넓혀야 하고, planner/synthesizer contract를 다른 numeric family에도 일관되게 적용해야 함 |
| 다음 할 일 | direct-first acceptance + evidence propagation을 shared scoring/acceptance policy로 더 굳히고, 부족 재료는 aggregate replan/refusal loop로 닫히게 일반화 |
| 종료 조건 | planner와 synthesizer의 책임 경계가 안정되고, direct success는 score-only가 아닌 grounded contract로 일관되게 승인됨 |

### 2. Result schema settling

| 항목 | 내용 |
| --- | --- |
| 목표 | lookup/difference/ratio 결과를 answer-friendly structured result로 남겨 synthesizer와 evaluator가 안정적으로 사용 |
| 현재 상태 | `CalculationResult.answer_slots`와 `resolved_calculation_trace`가 runtime contract로 자리잡았고, public boundary의 flat `calculation_*`는 제거됐다 |
| 다음 할 일 | internal compatibility mirror를 더 줄일지 범위를 정리하고, slot `status + provenance`를 internal source of truth로 더 굳히기 |
| 종료 조건 | single-task와 multi-subtask 모두 원본 질문 충족 여부와 numeric grading을 structured result만 보고 판정 가능 |

### 3. Concept-only planner validation

| 항목 | 내용 |
| --- | --- |
| 목표 | concept-only ontology + LLM planner가 implicit / shorthand / multi-metric query를 runtime default로 감당할 수 있는지 검증 |
| 현재 관측 | concept planner canary에서 `SKH_T1_060`, `MIX_T1_021`, implicit `부채비율` / `유동비율` / `FCF`는 잘 분해된다. `NAV_T1_071`와 `KBF_T1_017`도 `lookup + difference` + direct-first/evaluator close까지 확인됐다 |
| 다음 할 일 | concept planner canary와 ontology shadow compare를 계속 돌리며 default 승격 기준 정리 |
| 종료 조건 | planner가 benchmark-shaped `metric_family` 없이도 주요 numeric family를 안정적으로 재료 수집 task로 분해 |

### 4. DART multi-document reasoning

| 항목 | 내용 |
| --- | --- |
| 목표 | 같은 회사의 사업/반기/분기/정정공시를 함께 읽는 DART 범위 reasoning으로 확장 |
| 선행 조건 | single-doc planner/synthesizer contract와 structured result schema가 안정화되고, mainline ingest candidate가 확정 |
| 다음 할 일 | `multi_report_eval_full.curated.json`를 기준으로 report linker / period comparator / disclosure diff 방향 정리 |
| 종료 조건 | multi-report 질문에서 report binding과 period binding이 안정적으로 유지됨 |

## Success Criteria

- planner가 답변 문장을 직접 결정하지 않고 필요한 재료를 안정적으로 수집한다.
- final synthesizer가 원본 질문 충족 여부를 보고 close / replan / refusal을 일관되게 결정한다.
- runtime source of truth가 `tasks + artifacts + table objects + structured results`로 이동한다.
## 2026-05-17 Immediate Update

- Keep the current scope DART-only and finish the disclosure-analysis loop cleanly.
- Near-term runtime priority is now:
  1. reduce retrieval fan-out for `lookup + difference` style questions
  2. reuse query embeddings and/or collapse near-duplicate retrieval queries
  3. re-run `NAV_T1_071` end-to-end after the fan-out reduction
- Resume-aware indexing is now in place and should be treated as the default benchmark behavior.
  - preserve partial store when config matches
  - skip already indexed `chunk_uid`s
  - batch missing additions so interrupted ingest can continue on retry
- Parser and structured value binding are no longer the main blocker for `NAV_T1_071`.
  - The blocker is repeated retrieval-time embedding calls created by planner query expansion.

## 2026-05-18 Immediate Update

- Keep the current scope DART-only and keep pushing on the single-document numeric close loop before widening task scope again.
- Runtime priority has shifted one step further down the stack:
  1. prefer direct pretax-income rows over indirect reconstructions for `lookup`
  2. bind `prior_period` from the same table/cell family for `difference`
  3. re-run `NAV_T1_071` until both:
     - `2023 current value`
     - `2022 prior value`
     are preserved in structured results
- Newly stabilized infrastructure should now be treated as baseline behavior:
  - concept-v3 ontology overlay loaded by default runtime ontology
  - BM25-only fallback when query embedding returns `429 RESOURCE_EXHAUSTED`
  - single-document retrieval scoped primarily by `rcept_no`, not strict company-name matching
- `NAV_T1_071` is no longer blocked by:
  - planner decomposition
  - parser statement-type propagation
  - partial-store survival
- `NAV_T1_071` is now blocked by:
  - direct-row vs derived-value selection policy
  - same-table prior-period cell binding for the difference task

## 2026-05-18 Latest Update

- `NAV_T1_071` has now been closed end-to-end and should be treated as a completed canary for the direct-first mini-epic.
- What actually closed it:
  1. direct lookup stopped degrading into generic context fallback
  2. surrogate metrics such as `계속영업순이익` stopped being accepted as pretax-income direct values
  3. raw table rows remained available as reconciliation candidates even when row/value JSON existed
  4. same-table `2023 current` / `2022 prior` split rows could be paired into a true subtraction result
  5. aggregate projection preserved subtask `runtime_evidence`, restoring evaluator `numeric_retrieval_support`
- Verified outcome on the NAVER rerun bundle:
  - `Numeric Pass Rate = 1.000`
  - `Faithfulness = 1.000`
  - `Completeness = 1.000`
- Active priority now shifts to:
  1. generalized result schema settling
  2. broadening direct-first acceptance/evidence propagation beyond this single canary
  3. concept-only planner default promotion criteria

## 2026-05-18 Result Contract Update

- `answer_slots`가 이제 numeric runtime의 공통 result contract로 추가되었다.
- aggregate 단계는 LLM synthesizer에 앞서 deterministic gap checker를 실행한다.
  - `lookup/single_value`: `primary_value`
  - `difference`: `current_value`, `prior_value`, `delta_value`
  - `growth_rate`: `current_value`, `prior_value`, `primary_value`
  - `ratio/sum`: `primary_value`
- direct numeric grounding 대상도 확장됐다.
  - 기존: `lookup`, `single_value`, single-concept `difference/growth_rate`
  - 현재: explicit concept operand를 가진 `ratio`, `sum`도 structured direct grounding 대상으로 취급

## 2026-05-19 Percent and Evaluator Close

- `KBF_T1_017` is now closed and should no longer be treated as the open percent canary.
- What actually closed it:
  1. single-concept `current/prior` pair selection was generalized into joint pair selection with same-cell reuse rejection
  2. `net_interest_margin` direct lookup stopped accepting `NIM(은행+카드)` style variant rows through ontology-level surface contracts
  3. percent rendering preserved source precision (`1.83%`, `1.73%`, `0.10%p`)
  4. evaluator operand grounding learned to accept unitless structured percent rows from runtime evidence
  5. evaluator operand selection now tolerates alias-level label differences when period and normalized numeric payload match exactly
- Active priority now shifts away from percent-specific debugging.
  - next focus is keeping `answer_slots` as the runtime default contract
  - then pushing `tasks + artifacts` further toward source-of-truth status

## 2026-05-19 Ingest Scope Clarification

- `selective_v2_sections`는 runtime 전역 설정이 아니다.
- 현재 적용 범위는 benchmark runner의 `contextual_selective_v2` ingest mode에 한정된다.
- 따라서 이 값으로 생기는 실패는 우선:
  - planner bug
  - reconciliation bug
  가 아니라, selective benchmark store가 필요한 섹션을 누락했는지부터 확인해야 한다.
## 2026-05-19 Projection Unification

- runtime legacy projection and evaluator runtime projection now share the same
  `_resolve_runtime_calculation_trace(...)` helper path.
- planning subtask capture now also reuses the shared projection helpers instead
  of carrying its own ledger trace copy.
- benchmark review row flattening now resolves `calculation_*` through the same
  runtime trace helper, so review CSV export follows `answer_slots +
  tasks/artifacts` before falling back to flat top-level fields.
- retrospective evaluator/grounding scripts and MAS smoke checks now also read
  resolved runtime traces instead of raw top-level `calculation_*` where
  applicable.
- `FinancialAgent.run()` now uses:
  - `resolved_calculation_trace`
  - `structured_result`
  as the first-class public runtime contract.
- FastAPI `/api/query` now forwards the same structured result contract so
  external API consumers can adopt it directly.
- debug/smoke tooling now also carries `structured_result` /
  `resolved_calculation_trace` in its output where practical.
- benchmark review rows persist `structured_result`,
  `resolved_calculation_trace`, and `resolved_operand_count` as the canonical
  replay/debug contract.
- This makes `answer_slots + tasks/artifacts` the practical source-of-truth
  contract at the runtime boundary.
- Remaining cleanup targets are now mostly internal:
  1. `FinancialAgentState` still carries `calculation_*` as working state
  2. some internal node/test fixtures still serialize legacy names for
     compatibility with older traces

## 2026-05-20 Runtime validation note

- legacy flat runtime projection 제거 이후 fresh narrow runtime reruns now confirm:
  - `NAV_T1_071`: PASS
  - `SKH_T1_060`: PASS
  - `MIX_T1_021`: PASS
  - `KBF_T1_017`: PASS
  - `NAV_T1_030`: PASS
- 즉 public/runtime contract를 `resolved_calculation_trace + structured_result`
  중심으로 정리한 뒤에도 대표 numeric canary는 유지됐다.
- `NAV_T1_030` closure details:
  - FCF now uses deterministic subtract planning instead of drifting into ratio-style planning
  - parenthesized negative outflows normalize correctly through runtime/evaluator paths
  - final rendering rewrites double-negative subtraction phrasing into sign-aware natural language
  - evaluator now accepts display-scaled KRW operands and parenthesized negative support rows in structured traces

## 2026-05-20 Internal-state runtime note

- internal graph-state readers/writers now also prefer
  `resolved_calculation_trace + structured_result` over top-level
  `calculation_*`.
- fresh internal-state canary reruns confirmed no regression:
## 2026-05-22 Structural routine + multi-report update

- routine curated validation should now assume:
  - `structural_selective_v2_prefix_2500_320` is the default operating path
  - `contextual_selective_v2_prefix_2500_320` is arbitration-only
- official curated profiles were reduced to structural-only candidates for
  normal smoke/regression work:
  - `curated_runtime_contract_gate`
  - `curated_multi_entity_grounding_gate`
  - `curated_single_doc_core`
  - `curated_multi_report_smoke`
- `SAM_T2_002` is no longer blocked by the old cash-flow fallback path.
  - runtime now recognizes business-section `시설투자(CAPEX)` totals through
    the `capital_expenditure_total` concept
  - aggregate `합 계 / 총 계 / 계` rows from business tables can be promoted
    as direct numeric candidates when CAPEX-positive context is present
  - deterministic reconciliation now keeps direct row/value candidates ahead of
    stale chunk-only matches
- latest direct structural-store replay on Samsung 2023 now closes:
  - `2023년 시설투자(CAPEX) 총액 = 53조 1,139억원`
  - `전년(2022년) 대비 증감률 = 0%`
- still pending:
  - rerun the formal `curated_multi_report_smoke` benchmark bundle so the
    repaired `SAM_T2_002` result is captured in official `review.csv`
  - then decide whether multi-report structural validation is strong enough to
    treat `structural_selective_v2_prefix_2500_320` as the effective mainline
    default rather than just the leading candidate
  - `NAV_T1_030`: PASS
  - `NAV_T1_071`: PASS
  - `SKH_T1_060`: PASS
  - `MIX_T1_021`: PASS
  - `KBF_T1_017`: PASS
- external/public contract cleanup is effectively complete.
- remaining `calculation_*` fields are now internal compatibility mirrors /
  scratch state, not runtime source of truth.

## Runtime contract gate

## 2026-05-21 Multi-entity grounding gate

- `comparison_001`, `comparison_002`, `comparison_003` now form the focused
  multi-entity / segment-grounding smoke set.
- Official profile:
  - `benchmarks/profiles/curated_multi_entity_grounding_gate.json`
- Official runbook:
  - `docs/evaluation/multi_entity_grounding_gate.md`
- Current direct runtime validation closes all three:
  - `comparison_001`: `DX = 174조 8,877억원`, `DS = 111조 660억원`, `차이 = 63조 8,217억원`
  - `comparison_002`: `SDC = 29조 1,578억원`, `Harman = 14조 2,749억원`, `합계 = 43조 4,327억원`
  - `comparison_003`: `DS = 111조 660억원`, `SDC = 29조 1,578억원`, `차이 = 81조 9,082억원`
- The key planner/runtime change was generalizing repeated-concept multi-entity
  grounding beyond `sum`:
  - entity/segment labels are now reattached to repeated `revenue` operands for
    `difference` as well as `sum`
  - deterministic concept fallback can now build entity-scoped `difference`
    tasks even when ontology concept matching only yields a generic `revenue`
    concept

- official curated smoke profile:
  - `benchmarks/profiles/curated_runtime_contract_gate.json`
- current canonical gate question set:
  - `NAV_T1_030`
  - `NAV_T1_071`
  - `MIX_T1_021`
  - `KBF_T1_017`
  - `SKH_T1_060`
- intent:
  - use this as the preferred runtime-contract smoke before promoting mainline curated-profile changes
  - keep `allow_retrieval_fallback = false` so gate comparisons stay backend-stable
  - canonical runbook lives at `docs/evaluation/runtime_contract_gate.md`

## 2026-05-20 Runtime gate procedure

- Treat `benchmarks/profiles/curated_runtime_contract_gate.json` as the required
  smoke suite before changing the curated mainline benchmark profile or
  promoting runtime-contract related planner/grounding changes.
- Current official gate questions:
  - `NAV_T1_030`
  - `NAV_T1_071`
  - `MIX_T1_021`
  - `KBF_T1_017`
  - `SKH_T1_060`
- Execution policy:
  - keep `allow_retrieval_fallback = false`
  - treat any store-signature mismatch as cache miss / reindex, not reuse
  - record backend identity in `benchmark_cache_meta.json`

## 2026-05-20 Multi-entity comparison status

- `comparison_002` should now be treated as the active multi-entity grounding
  canary.
- The failure mode was:
  - two repeated `revenue` addends collapsing onto the same company-total row
  - LLM concept planner preserving operation shape (`sum`) but dropping segment
    identity (`SDC`, `Harman`)
- Runtime fix now in place:
  - segment-scoped direct grounding rejects candidates that do not match the
    operand `segment_label`
  - LLM concept planner conversion rehydrates segment labels from the original
    query / metric label when repeated `revenue` addends are used
- Latest direct runtime check on the Samsung 2024 selective store now closes:
  - `SDC 매출액 = 29조 1,578억원`
  - `Harman 매출액 = 14조 2,749억원`
  - `합계 = 43조 4,327억원`

## 2026-05-21 Ingest candidate status

- official gate comparison now implies:
  - `plain_prefix_8000_400`
    - stays as speed / cost baseline
    - is not eligible as default because `SKH_T1_060` fails
  - `contextual_selective_v2_prefix_2500_320`
    - remains the quality baseline
    - passes both official gates
  - `structural_selective_v2_prefix_2500_320`
    - passes both official gates
    - is now the current operating default
- immediate work therefore shifts from “can this candidate pass the gate?” to:
  1. “what is the next cheaper-or-better ingest experiment after this baseline?”
  2. “how far can concept-only planner and multi-document reasoning be pushed on top of this default?”
## 2026-05-21 Concept planner shadow

- official curated shadow profile:
  - `benchmarks/profiles/curated_concept_planner_shadow.json`
- official shadow runbook:
  - `docs/evaluation/concept_planner_shadow.md`
- current curated shadow scope includes:
  - runtime contract canaries
  - focused multi-entity grounding canaries
  - implicit shorthand numeric prompts
- latest curated shadow run confirms:
  - `11 / 11` curated cases changed between legacy and concept planning
  - all concept-side plans were emitted as `concept_fallback`
- important planner transitions confirmed:
  - `free_cash_flow` -> `concept_difference`
  - `generic_numeric` -> `concept_lookup + concept_difference`
  - `debt_ratio/current_ratio` -> `concept_ratio`
  - repeated-entity revenue prompts preserve `sum` / `difference` task shape
- use this profile as the planner-structure smoke whenever changing:
  - concept ontology
  - planner prompt / conversion logic
  - generic numeric fallback behavior
