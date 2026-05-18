# 실행 계획

> 이 문서는 **현재 active plan만 유지하는 실행 문서**다.  
> 과거 실험과 장기 방향은 [DECISIONS.md](C:/Users/geonj/Desktop/research%20agent/DECISIONS.md)와 [docs/planning/backlog_and_next_epics.md](C:/Users/geonj/Desktop/research%20agent/docs/planning/backlog_and_next_epics.md)로 보낸다.

## Active Snapshot

| 항목 | 현재 상태 |
| --- | --- |
| 현재 1순위 | **planner는 재료를 모으고, synthesizer가 질문 충족 여부를 판단하는 구조를 runtime에 정착** |
| 지금 하지 않을 것 | 범용 agent 확장, broad web workflow, cosmetic retrieval tuning |
| 다음 큰 순서 | `planner/synthesizer contract -> result schema settling -> concept-only planner canary -> DART multi-document reasoning` |

## Immediate Focus

- curated dataset 연결과 parser baseline regression은 1차 기준선까지는 지나갔다.
- 지금 가장 가까운 구현 초점은 **planner/synthesizer contract + concept-only planning + result schema settling** 이다.
  - ontology는 metric recipe보다 concept / group concept / binding prior 중심으로 축소
  - planner는 질문을 `operation_family + required_operands` 형태의 재료 수집 task로 분해
  - final synthesizer는 원본 질문과 `subtask_results`를 보고 최종 답 또는 `planner_feedback`를 결정
  - planner는 `planner_feedback`를 받아 기존 `pre_calc_planner`에서 patch append 방식으로 replan
  - direct lookup은 planner recipe가 아니라 runtime grounding policy로 다룬다
  - direct candidate는 score만으로 accept하지 않고 binding contract를 만족해야 성공으로 본다
  - runtime state에 `tasks`, `artifacts`, `table_object_json`을 남겨 source of truth를 만들기 시작
  - ambiguous top candidate는 deterministic scoring 후에만 LLM rerank로 보정

## Active Workstreams

### 0. Planner and synthesizer contract

| 항목 | 내용 |
| --- | --- |
| 목표 | planner는 재료 수집만 하고, final synthesizer가 질문 충족 여부와 최종 refusal을 책임지는 구조 정착 |
| 현재 자산 | concept-only ontology v3 draft, LLM concept planner, lightweight validator, `planner_feedback`, `plan_loop_count`, aggregate synthesizer |
| 현재 문제 | `lookup`, `difference`, `ratio`가 answer contract를 충분히 구조화해 남기지 않아 synthesizer가 일부 질문에서 약함. direct false positive를 hard acceptance contract로 막는 규칙도 다른 concept family로 더 넓혀야 함 |
| 다음 할 일 | `NAV_T1_071`에서 검증한 direct-first acceptance + evidence propagation 계약을 다른 numeric families에도 일반화 |
| 종료 조건 | planner와 synthesizer의 책임 경계가 안정되고, 부족 재료는 planner replan으로 보강하거나 aggregate refusal로 닫히며, direct success는 score-only가 아닌 grounded contract로 일관되게 승인됨 |

### 1. Result schema settling

| 항목 | 내용 |
| --- | --- |
| 목표 | lookup/difference/ratio 결과를 answer-friendly structured result로 남겨 synthesizer가 안정적으로 조합 |
| 현재 상태 | `current_value`, `prior_value`, `delta_value` 같은 슬롯은 생겼지만, renderer / synthesizer / evaluator가 이 슬롯을 일관되게 우선 사용하도록 더 정리해야 함 |
| 다음 할 일 | operation별 structured result schema를 정리하고 renderer / synthesizer / evaluator contract를 맞추기 |
| 종료 조건 | single-task와 multi-subtask 모두 원본 질문 충족 여부를 structured result만 보고 판정 가능 |

### 2. Concept-only planner validation

| 항목 | 내용 |
| --- | --- |
| 목표 | concept-only ontology + LLM planner가 implicit / shorthand / multi-metric query를 runtime default로 감당할 수 있는지 검증 |
| 현재 관측 | concept planner canary에서 `SKH_T1_060`, `MIX_T1_021`, implicit `부채비율` / `유동비율` / `FCF`는 잘 분해된다. `NAV_T1_071`도 `lookup + difference` decomposition과 e2e close까지 확인됐다 |
| 다음 할 일 | concept planner canary와 ontology shadow compare를 계속 돌리며 default 승격 기준 정리 |
| 종료 조건 | planner가 benchmark-shaped `metric_family` 없이도 주요 numeric family를 안정적으로 재료 수집 task로 분해 |

### 3. DART multi-document reasoning

| 항목 | 내용 |
| --- | --- |
| 목표 | 같은 회사의 사업/반기/분기/정정공시를 함께 읽는 DART 범위 reasoning으로 확장 |
| 선행 조건 | single-doc planner/synthesizer contract와 structured result schema가 안정화 |
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
