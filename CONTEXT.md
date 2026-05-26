# 프로젝트 컨텍스트

> 이 문서는 **현재 상태만 빠르게 파악하기 위한 snapshot 문서**다.  
> 과거 판단과 이유는 [DECISIONS.md](C:/Users/geonj/Desktop/research%20agent/DECISIONS.md), 장기 backlog는 [docs/planning/backlog_and_next_epics.md](C:/Users/geonj/Desktop/research%20agent/docs/planning/backlog_and_next_epics.md)를 본다.

## 현재 범위

- 이 프로젝트의 현재 범위는 **DART 공시 분석 내부**에 한정한다.
- 범용 agent, broad web workflow, productivity tool 확장은 당분간 하지 않는다.
- 목표는 DART single-document / multi-document 분석을 빠르게 안정화하고 닫는 것이다.

## 최신 상태

- curated benchmark 경로를 실제 profile과 evaluator에 연결했다.
- active benchmark/profile track도 curated 중심으로 재정렬하기 시작했다.
  - mainline: `curated_single_doc_core`, `curated_runtime_contract_gate`, `multi_metric_numeric_smoke`, `curated_multi_report_smoke`
  - legacy historical: `dev_fast*`, `dev_math_*`, `release_generalization`
- 공식 gate 비교 기준도 한 단계 정리됐다.
  - `plain_prefix_8000_400`: speed / cost baseline
  - `contextual_selective_v2_prefix_2500_320`: quality baseline
  - `structural_selective_v2_prefix_2500_320`: current operating default
  - `runtime_contract_gate`에서는 `plain`이 `SKH_T1_060`를 놓쳤고, `structural`과 `contextual`은 대표 5문항을 모두 통과했다
  - `multi_entity_grounding_gate`에서도 `structural`과 `contextual`이 `comparison_001~003`을 모두 통과했다
- 최신 runtime hardening도 추가로 닫혔다.
  - `SKH_T1_060`는 structural path에서 `장기차입금` / `사채` note aggregate lookup hardening 이후 다시 `PASS`로 닫혔다.
  - `MIX_T1_064`는 ontology-driven component ratio shape, evaluator composed-ratio grounding, uncertainty suffix 정리 이후 공식 targeted rerun까지 `PASS`로 닫혔다.
    - `numeric_equivalence = 1.0`
    - `numeric_grounding = 1.0`
    - `numeric_retrieval_support = 1.0`
    - `numeric_final_judgement = PASS`
  - `NAV_T2_006`는 direct `financial_graph` 경로에서도 hybrid query decomposition(`lookup -> lookup -> growth_rate -> narrative_summary`)이 실제 runtime에서 끝까지 돌도록 정리됐다.
  - 최신 official targeted rerun에서 `NAV_T2_006`는 `커머스 매출 성장률 41.4%`, `Poshmark 체질 개선`, `연결 편입효과`, `스마트스토어/브랜드스토어 성장`까지 포함한 답으로 닫혔다.
    - `faithfulness = 1.0`
    - `completeness = 1.0`
- parser는 단순 chunk normalization을 넘어 **table-aware grounding** 단계로 들어갔다.
  - 병합된 `ROWSPAN/COLSPAN`을 canonical grid로 복원
  - `table_summary_text`, `table_row_labels_text`, `table_row_records_json`, `table_object_json` 생성
  - structured row-aware reconciliation 추가
- numeric question 경로에는 아래가 들어갔다.
  - ontology 기반 pre-retrieval semantic planning
  - post-retrieval reconciliation
  - multi-metric 질문용 subtask loop / aggregation
  - ready 상태 numeric subtask에 대한 direct `structured_row -> operand` 추출
  - `table_value_records_json -> structured_value` 기반 value-cell-first grounding
- planner / ontology 경로는 최근 아래 방향으로 이동했다.
  - benchmark-shaped `metric_family` 확장을 줄이고 concept-only ontology v3 draft를 추가
  - ontology는 `concept`, `concept_group`, statement/section prior, binding prior 중심으로 축소 시작
  - planner는 `metric_family`보다 `operation_family + required_operands` 중심의 IR로 점진 이동
  - implicit query도 LLM concept planner가 concept 조합으로 풀도록 canary path를 추가
  - planner validator는 형식 / 허용 concept / 허용 operation만 보는 얇은 contract checker로 유지
- answer path는 최근 아래 방향으로 이동했다.
  - planner는 “최종 문장을 최소화”하는 대신 **필요한 재료를 빠짐없이 모으는 방향**으로 조정
  - final synthesizer가 원본 질문과 `subtask_results`를 함께 읽고 최종 답을 조합
  - 재료가 부족하면 synthesizer가 `planner_feedback`를 남기고 기존 `pre_calc_planner`를 replan mode로 재사용
  - replan budget을 모두 써도 재료가 부족하면 `aggregate_subtasks`가 사용자-facing 최종 refusal / partial answer를 확정
  - direct lookup 우선 정책은 planner recipe가 아니라 runtime grounding / acceptance policy로 다룬다
  - direct candidate는 score만 높다고 성공으로 확정하지 않고 binding contract를 만족해야 accept한다
  - `CalculationResult.answer_slots`가 `lookup / difference / ratio / sum`의 공통 structured result contract로 추가됐다
  - aggregate 단계는 이제 `answer_slots`를 보고 `current / prior / delta / primary` 재료 누락을 deterministic하게 먼저 감지할 수 있다
- 내부 실행 구조 일반화를 위한 1차 schema를 추가했다.
  - `tasks`, `artifacts` state 추가
  - parser의 `table_object / row_record / cell_record`를 정식 출력으로 승격 시작
  - semantic plan / reconciliation / operand set / calculation plan / calculation result / aggregated answer를 artifact로 기록 시작
- evaluator는 이제 top-level `calculation_*`만 읽지 않고 runtime ledger를 다시 투영해 trace를 복원한다.
  - single-task 계산은 `tasks + artifacts`에서 operand/plan/result를 다시 읽는다
  - multi-subtask 계산은 `subtask_results`를 aggregate projection으로 다시 묶는다
- numeric reconciliation은 최근 아래 방향으로 보강됐다.
  - `structured_row` 중 `범위/하위범위/상위범위` 같은 descriptor row penalty
  - `chunk`보다 `structured_row / table_row / evidence_row` 우대
  - top candidate가 애매할 때만 LLM rerank helper 사용
  - `retrieved_docs`뿐 아니라 `seed_retrieved_docs`도 reconciliation candidate pool에 포함
  - `유형자산/무형자산/자산총계/부채총계/자본총계` 계열은 `summary_financials / balance_sheet` row를 우대
- parser/table grounding은 최근 아래 방향으로 더 확장됐다.
  - `table_value_records_json`과 `structured_value` candidate 추가
  - `TBODY/TE` 셀을 실제 value cell로 읽도록 확장
  - `(단위 : 백만원)` 같은 unit-only standalone table도 다음 실제 표의 context hint로 승격
  - wide merged-header note table에서 `direct_total / subtotal / final_total / adjustment` aggregate role 복원
- 최근 canary / e2e 관측은 다음과 같다.
  - ontology-v2 canary에서 `SKH_T1_060`은 `42.0%`, `MIX_T1_021`은 부채비율 `25.4%` / 유동비율 `258.8%`로 닫혔다
  - concept-planner shadow canary에서는 `SKH_T1_060`, `MIX_T1_021`, implicit `부채비율` / `유동비율` / `FCF`가 concept-only planner로도 자연스럽게 분해된다
  - `NAV_T1_071`는 now closed end-to-end:
    - planner는 `lookup + difference` 재료 수집 구조로 분해
    - direct structured row grounding으로 `2023 current` / `2022 prior`를 직접 바인딩
    - aggregate 단계가 subtask evidence를 최종 state까지 보존해 evaluator `numeric_retrieval_support`까지 `1.0`으로 복구
  - `KBF_T1_017`도 now closed:
    - `lookup`은 `명목순이자마진(NIM)` canonical row를 직접 바인딩
    - `difference`는 같은 structured row 안의 distinct `2023 / 2022` cell pair를 사용
    - evaluator는 unitless structured percent row와 operand alias mismatch를 허용해 `numeric_retrieval_support = 1.0`, `operand_selection_correctness = 1.0`으로 복구
  - `NAV_T1_030`도 now closed:
    - FCF는 deterministic `subtract` plan으로 유지된다
    - 괄호 음수 outflow row는 runtime과 evaluator에서 같은 operand로 해석된다
    - final rendering은 `-X를 차감` 같은 이중 음수 표현을 남기지 않는다
    - `numeric_grounding = 1.0`, `numeric_retrieval_support = 1.0`, `numeric_final_judgement = PASS`

## 현재 핵심 한계

- public/runtime boundary에서 legacy `calculation_*`는 이미 projection 계층으로 내렸다.
- 남아 있는 `calculation_*`는 주로 internal compatibility mirror / scratch state다.
- planner / synthesizer / result schema의 경계가 이제 막 생겼기 때문에, single-task와 multi-subtask가 항상 같은 answer contract를 공유하지는 못한다.
- concept-only planner는 single-metric / group concept / multi-metric 분해 품질이 좋아졌지만, 모든 numeric family에서 runtime default로 올리기엔 아직 canary가 더 필요하다.
- `difference` / `lookup` / `ratio` 결과를 더 구조적으로 남기는 result schema 정리는 대부분 끝났지만, internal mirror를 완전히 없애는 수준의 graph-state refactor는 아직 남아 있다.
- profile 운영 기준은 이제 curated track이 우선이고, legacy 2024 dataset profile은 historical replay 용도로만 남긴다.
- final refusal ownership은 `aggregate_subtasks`로 올라왔고, `NAV_T1_071`를 통해 `planner_feedback -> replan / close` 루프의 최소 실전 검증은 끝났다.
- direct-first runtime policy는 `NAV_T1_071`에서 닫혔고, 이제 `ratio / sum`처럼 explicit concept numeric task까지 direct grounding 대상으로 확대됐다.
- percent multi-period rows도 별도 metric hardcoding 없이 shared pair-selection / evaluator contract로 닫히기 시작했다.
- 다만 ingest 쪽은 여전히 tradeoff가 남아 있다.
  - `contextual_selective_v2`는 품질은 안정적이지만 ingest 비용이 크다
  - `structural_selective_v2`는 현재 gate 기준으로 같은 품질을 더 낮은 비용으로 달성한 routine default다
- broader curated validation blocker는 현재 닫혔다.
  - `curated_multi_report_smoke`의 `SAM_T2_002`는 CAPEX total direct grounding과 current/prior binding까지 PASS
  - `curated_single_doc_core`의 `MIX_T1_046`는 note-sibling unit inheritance와 evaluator period normalization 이후 PASS

## 바로 다음에 할 일

| 순서 | 할 일 | 목적 |
| --- | --- | --- |
| 1 | `structural_parent_hybrid_v2` 실험 설계 | structural default 위에 parent/section/table lineage를 더 보강할 수 있는지 확인 |
| 2 | `curated_concept_planner_shadow` 확대 검증 | concept-only planner drift를 runtime gate와 분리해서 확인 |
| 3 | contextual arbitration / benchmark maintenance 정리 | structural default와 contextual quality reference의 운영 경계를 문서와 profile에 고정 |

## 현재 우선순위 요약

1. next ingest experiment design (`structural_parent_hybrid_v2`)
2. concept-only planner default 승격 검토
3. contextual arbitration / benchmark maintenance 정리
4. internal compatibility mirror cleanup scope 결정

## 현재 해석

- 지금 시스템은 “질문 1개 -> 답 1개” 구조에서 더 멀어져, `task + artifact + structured table object + final synthesizer` 중심으로 이동 중이다.
- planner는 점점 benchmark-shaped metric family보다 **concept + operation + material gathering** 쪽으로 옮겨가고 있다.
- answer completeness와 최종 refusal은 planner가 아니라 final synthesizer / aggregate 단계가 책임지는 방향으로 경계가 정리되고 있다.
- final synthesizer는 이제 LLM 판단만 쓰지 않고, `answer_slots` 기반 deterministic gap checker를 먼저 사용해 재료 부족을 감지한다.
- direct-first policy는 metric-specific planner branching보다 runtime acceptance contract와 lazy replan 쪽으로 구현하는 것이 현재 방향에 더 맞다.
- `NAV_T1_071`는 이 방향으로 실제로 닫혔다.
  - direct structured row grounding
  - same-family current/prior pairing
  - aggregate evidence propagation
  - evaluator numeric pass `1.0`
- public/runtime contract 정리는 거의 끝났고, 남은 리팩터링은 internal mirror 정리 쪽에 가깝다.
- 현재 더 중요한 운영 질문은 planner보다 ingest candidate selection이다.
  - `plain`은 여전히 하나의 대표 gate를 놓친다
  - `contextual_selective_v2`는 품질 baseline이지만 ingest 비용이 크다
  - `structural_selective_v2`는 현재 routine default로 가장 실용적인 middle ground다
- 따라서 다음 구현은 당분간 retrieval/parser local patch보다 **composed-ratio / hybrid mixed-query benchmark promotion + next ingest experiment design** 쪽이 맞다.
- immediate blocker였던
  - `SAM_T2_002` follow-up rerun
  - `MIX_T1_046` ratio direct-binding rerun
  은 now closed다.
## 2026-05-17 Update

- Indexing now supports partial-store resume in the benchmark path.
  - `benchmark_runner` writes `benchmark_cache_meta.json` with `status: "in_progress"` before ingest.
  - `resume_partial_store=true` preserves a matching partial store instead of deleting it.
  - `VectorStoreManager.add_documents(..., resume=True)` skips already indexed `chunk_uid`s and adds only missing chunks in batches.
- This was verified on the NAVER 2023 large-chunk reindex path.
  - A legacy partial store was preserved and then completed successfully.
  - A second run hit store cache immediately and skipped re-ingest.
- `NAV_T1_071` status is now clearer.
  - planner / replan loop: implemented and observed on a real question
  - structured current/prior value binding: fixed locally for the NAVER 2023 income-statement row
  - remaining blocker: retrieval fan-out still triggers repeated embedding calls and can hit `429 RESOURCE_EXHAUSTED`
- Immediate bottleneck is no longer parser correctness or fresh-store survival.
  - The next runtime optimization target is retrieval query count and/or query-embedding reuse for `lookup + difference` style questions.

## 2026-05-18 Update

- `NAV_T1_071` moved forward from a planner failure to a much narrower runtime issue.
  - planner now consistently decomposes the question into:
    - `2023년 법인세비용차감전순이익` / `lookup`
    - `법인세비용차감전순이익 증감액` / `difference`
- Runtime ontology now auto-loads the concept-v3 overlay through the default loader, so concept-only planning is no longer a shadow-only path.
- Parser and grounding were tightened for pretax-income style rows.
  - standalone statement title tables are promoted into table context hints
  - statement body tables inherit those hints for `statement_type` / `consolidation_scope`
  - ontology aliases now include spaced variants such as `법인세비용 차감 전 당기순손익`
  - deterministic candidate scoring now penalizes delta-like rows for explicit `current_period` / `prior_period` operands
- Retrieval/runtime stability was improved in two ways.
  - when `rcept_no` is present for a single-document DART run, retrieval now treats it as the primary scope and disables strict company-name filtering
  - vector query embedding `429 RESOURCE_EXHAUSTED` now falls back to BM25-only retrieval instead of aborting the run
- Current `NAV_T1_071` status after these changes:
  - retrieval is alive again on the completed NAVER store
  - task 1 no longer collapses to a generic planner failure
  - the remaining error is now operand choice policy:
    - the system can still prefer an indirect construction (`당기순이익 + 법인세비용`) over a direct pretax-income row
    - prior-period (`2022`) binding remains incomplete for the difference task
- Immediate next fix is no longer broad retrieval tuning.
  - prefer direct pretax-income rows over derived reconstructions when both exist
  - make same-table prior-period cell binding win for `difference` / `prior_period`

## 2026-05-18 Direct-First Close

- `NAV_T1_071` is now closed end-to-end.
  - planner decomposition remains `lookup + difference`
  - direct numeric tasks no longer degrade into generic context fallback
  - pretax-income lookup rejects surrogate metrics such as `계속영업순이익`
  - raw table rows are preserved as reconciliation candidates even when row/value JSON exists
  - `difference` can pair split same-table raw rows into `2023 current` / `2022 prior`
- The final runtime fix was not retrieval itself but state propagation.
  - subtask-level `runtime_evidence` now survives into aggregate projection
  - aggregate state now exposes the same direct row evidence that operand grounding used
  - evaluator `numeric_retrieval_support` therefore returns to `1.0`
- Verified outcome on `benchmarks/results/nav_t1_071_direct_acceptance_2026-05-18-rerun5`:
  - `Numeric Pass Rate = 1.000`
  - `Faithfulness = 1.000`
  - `Completeness = 1.000`
- Immediate priority has therefore shifted away from this canary.
  - next focus is generalized result schema settling
  - then broadening the same direct-first acceptance/evidence propagation policy to other numeric families

## 2026-05-18 Result Contract Update

- `CalculationResult.answer_slots`가 공통 structured result contract로 추가됐다.
  - `primary_value`
  - `current_value`
  - `prior_value`
  - `delta_value`
  - `components_by_role`
- `difference`는 현재/전기/증감 슬롯을 모두 명시적으로 남긴다.
- `lookup`은 direct row에서 잡은 값을 `primary_value`로 노출한다.
- aggregate projection과 evaluator runtime projection도 subtask별 `answer_slots`를 그대로 carry한다.
- `aggregate_subtasks`는 LLM synthesizer 전에 deterministic gap checker를 실행한다.
  - `lookup`은 `primary_value`
  - `difference`는 `current_value`, `prior_value`, `delta_value`
  - `ratio`, `sum`은 `primary_value`
  의 존재를 먼저 확인하고, 비어 있으면 `planner_feedback`를 직접 생성한다.

## 2026-05-19 Answer Slots and Selective Ingest Scope

- `answer_slots`는 이제 renderer / synthesizer뿐 아니라 evaluator runtime projection의 1순위 contract다.
  - evaluator는 `calculation_operands`보다 먼저 `answer_slots`에서 operand-like rows를 복원한다.
  - `result_value`가 없으면 `answer_slots.primary_value.normalized_value`를 numeric result source로 사용한다.
- runtime boundary도 같은 방향으로 정리되었다.
  - `FinancialAgent.run()`은 이제 `resolved_calculation_trace`와 `structured_result`를 함께 반환한다.
  - `/api/query`도 같은 structured contract를 전달한다.
  - MAS analyst/critic, benchmark review export, retrospective evaluator scripts도 이 contract를 우선 사용한다.

### Compatibility note

- public/runtime boundary에서는 top-level `calculation_operands`, `calculation_plan`,
  `calculation_result`를 더 이상 기본 contract로 노출하지 않는다.
- 새 consumer / 새 테스트 / 새 디버그 도구는 아래 둘만 기준으로 삼는다.
  - `structured_result`
  - `resolved_calculation_trace`
- 남아 있는 `calculation_*`는 현재 주로 내부 graph state와 계산 노드의 working state다.
  즉 external compatibility layer 정리는 끝났고, 남은 정리는 내부 runtime representation
  리팩터링에 가깝다.
- slot payload는 단순 숫자 dict가 아니라 `status + normalized/raw value + provenance`를 함께 담는 value object로 정리되기 시작했다.
  - missing material은 key omission이 아니라 `status = "missing"`으로 남긴다.
  - direct grounding이 성공한 값은 `source_row_id / source_row_ids / source_anchor`를 carry한다.
- percent numeric evaluation은 display precision을 존중한다.
  - 예: `25.36%`와 `25.4%`는 rounded display gap으로 허용된다.
- 대표 canary는 현재 모두 PASS 상태다.
  - `NAV_T1_071`
  - `SKH_T1_060`
  - `MIX_T1_021`
  - `KBF_T1_017`
  - `NAV_T1_030`
- 최근 public/runtime boundary에서 top-level flat `calculation_*`를 제거한 뒤에도
  위 대표 canary는 모두 PASS로 유지됐다.
- internal graph state도 이제 `resolved_calculation_trace`와
  `structured_result`를 우선 읽도록 정리됐다.
  - fresh internal-state canary rerun에서도
    - `NAV_T1_030`
    - `NAV_T1_071`
    - `SKH_T1_060`
    - `MIX_T1_021`
    - `KBF_T1_017`
    모두 PASS였다.
  - 남은 `calculation_*`는 내부 compatibility mirror / scratch state로만 본다.
- `selective_v2_sections`의 적용 범위도 분명해졌다.
  - 이것은 benchmark runner의 `contextual_selective_v2` ingest mode에서만 쓰이는 ingest-time 섹션 whitelist다.
  - 일반 `agent.ingest(...)`, `agent.contextual_ingest(...)`, query-time retrieval에는 적용되지 않는다.
  - 따라서 `selective_v2_sections` 문제는 runtime planner 이슈가 아니라 benchmark ingest coverage 이슈로 먼저 봐야 한다.

## 2026-05-21 Ingest Candidate Update

- 공식 gate 기준 ingest 후보 해석은 현재 아래처럼 정리된다.
  - `plain_prefix_8000_400`
    - speed / cost baseline
    - `runtime_contract_gate`에서 `SKH_T1_060` FAIL
  - `contextual_selective_v2_prefix_2500_320`
    - quality baseline
    - `runtime_contract_gate`, `multi_entity_grounding_gate` 모두 PASS
  - `structural_selective_v2_prefix_2500_320`
    - `runtime_contract_gate`, `multi_entity_grounding_gate` 모두 PASS
    - current operating default
- 따라서 지금의 실무 우선순위는 새 planner tweak보다 다음 두 가지다.
  1. `structural_parent_hybrid_v2` 같은 next ingest experiment 설계
  2. concept-only planner와 multi-document path를 더 넓게 검증
