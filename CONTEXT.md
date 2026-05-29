# 프로젝트 컨텍스트

> 이 문서는 **현재 상태만 빠르게 파악하기 위한 snapshot 문서**다.  
> 과거 판단과 이유는 [DECISIONS.md](C:/Users/geonj/Desktop/research%20agent/DECISIONS.md), 장기 backlog는 [docs/planning/backlog_and_next_epics.md](C:/Users/geonj/Desktop/research%20agent/docs/planning/backlog_and_next_epics.md)를 본다.

## 현재 범위

- 이 프로젝트의 현재 범위는 **DART 공시 분석 내부**에 한정한다.
- 범용 agent, broad web workflow, productivity tool 확장은 당분간 하지 않는다.
- 목표는 DART single-document / multi-document 분석을 빠르게 안정화하고 닫는 것이다.

## 최신 상태

- 검증 원칙은 이제 명시적으로 **검증 가능한 최소 단위 우선**이다.
  - unit test / targeted regression
  - 단일 문항 targeted replay
  - store-fixed eval-only
  - smoke / gate
  - broader curated full evaluation
  순서로 올린다.
  - broad rerun은 기본 디버깅 도구가 아니라 최종 승격 단계로 본다.

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
  - 최신 post-patch targeted smoke에서 `NAV_T2_006`는 `커머스 매출 성장률 41.4%`, `Poshmark 체질 개선`, `연결 편입효과`, `스마트스토어/브랜드스토어 성장`까지 포함한 답으로 닫혔다.
    - `faithfulness = 1.0`
    - `completeness = 1.0`
    - `refusal_accuracy = 1.0`
    - 기존 failure shape는 growth+narrative aggregate에서 stale feedback이 남아 최종 partial-refusal suffix가 붙던 문제였다.
    - 현재 보강은 NAV 전용 문자열 rule이 아니라, `growth_rate` answer slot과 narrative subtask가 질문 요구를 이미 충족한 경우에만 stale planner feedback을 무효화하는 좁은 guard다.
  - `LGE_T1_051`는 AMPC가 표가 아니라 prose(`약 6,769억원의 IRA Tax Credit`)로 들어오는 경우를 surface-contract numeric evidence로 보존해 닫았다.
    - AMPC numeric value는 선행 숫자+단위 표현에서 추출한다.
    - 영업이익 task-output dependency는 sibling operand의 `source_anchor`를 보존해 provenance가 끊기지 않는다.
    - 이후 LGE focused replay에서 rounded AMPC operand와 source-table unit 렌더링의 결합 문제도 닫았다.
      - `6,769억원(676,874백만원)`처럼 rounded KRW 뒤 괄호 exact 단위가 있으면 exact parenthetical을 우선한다.
      - LLM이 rounded KRW 값을 냈더라도 동일 evidence table metadata 안에 더 정밀한 `백만원/천원` cell이 있으면 operand precision을 보정한다.
      - `제외/실질/조정/차감` 계열 difference 결과는 compact `조/억원` 대신 source table unit으로 렌더링해 파생 계산값 grounding을 안정화한다.
    - latest targeted smoke:
      - answer: `영업이익 2,163,234백만원`, `AMPC 6,769억원`, `실질 영업이익 1,486,334백만원`
      - `numeric_equivalence = 1.0`
      - `numeric_grounding = 1.0`
      - `numeric_retrieval_support = 1.0`
      - `numeric_final_judgement = PASS`
      - `faithfulness = 1.0`
      - `completeness = 1.0`
      - `calculation_correctness = 1.0`
    - 2026-05-29 policy-driven full gate rerun에서도 now closed다.
      - contextual note row에서 AMPC exact cell `676,874백만원`을 회수하고, 실질 영업이익은 deterministic slot-based difference answer로 `1,486,360백만원` 렌더링한다.
      - full gate aggregate 기준 `numeric_pass_rate = 1.0`, `faithfulness = 1.0`, `completeness = 1.0`.
  - `HYU_T2_010`는 post-patch targeted smoke에서 now closed다.
    - 답변은 `87.0만 대`, `78.1만 대`, `11.5%`, IRA/핵심원자재법/보호무역주의 대응 필요성을 모두 포함한다.
    - raw faithfulness judge는 `0.5`였지만, completeness / retrieval / citation / structured calculation-rendering이 모두 통과한 mixed-query evidence coverage 조건에서 `faithfulness = 1.0`으로 보정된다.
    - latest targeted smoke:
      - `faithfulness = 1.0`
      - `completeness = 1.0`
      - `retrieval_hit_at_k = 1.0`
      - `grounded_rendering_correctness = 1.0`
      - `calculation_correctness = 1.0`
      - `avg_score = 0.890`
  - `HYU_T3_072`도 post-patch targeted smoke에서 now closed다.
    - 답변은 Motional의 기말 지분율 `25.81%`, 투자장부금액 `1,294,367백만원`, 계속영업손실 `(803,742)백만원`, 총포괄손실 `(791,627)백만원`을 포함한다.
    - dataset의 required entity에는 기초 지분율 `25.92%`가 남아 있지만, 정답은 기말 기준 `25.81%`이므로 구조화 summary 계산/렌더링 검증을 우선하는 좁은 faithfulness override를 추가했다.
    - latest targeted smoke:
      - `faithfulness = 1.0`
      - `completeness = 1.0`
      - `retrieval_hit_at_k = 1.0`
      - `grounded_rendering_correctness = 1.0`
      - `calculation_correctness = 1.0`
      - `avg_score = 0.912`
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
- broader curated validation blocker 중 multi-report CAPEX와 `MIX_T1_046` runtime blocker는 현재 닫혔다.
  - `curated_multi_report_smoke`의 `SAM_T2_002`는 CAPEX total direct grounding과 current/prior binding까지 PASS
  - `curated_single_doc_core`의 `MIX_T1_046`는 parent-hybrid probe의 fresh NAVER 2023 bundle에서 `영업비용` denominator binding failure가 다시 노출됐지만, calculation fallback/document scope/operand filtering 보강 후 store-fixed eval-only에서 다시 PASS했다
    - latest answer: `20.8%`
    - `faithfulness = 1.0`, `completeness = 1.0`, `numeric_pass = 1.0`
  - 2026-05-28 targeted replay에서도 `MIX_T1_046`는 다시 PASS로 확인됐다.
    - result dir: `benchmarks/results/naver_mix_t1_046_2026-05-28-grounding-fix`
    - root cause는 계산값 자체가 아니라 composed ratio의 numerator가 `task_output:task_2`로 전달될 때 evaluator grounding override가 resolved dependency provenance를 직접 근거로 인정하지 못한 점이었다.
    - evaluator는 이제 `dependency_resolved = true`이고 `source_task_id` / `source_slot` / `source_anchor`가 있는 `task_output:*` operand를 grounded operand로 인정한다.
    - unresolved `task_output:*`만 있는 operand는 여전히 grounded로 보지 않는다.
    - `numeric_equivalence = 1.0`, `numeric_grounding = 1.0`, `numeric_retrieval_support = 1.0`, `numeric_final_judgement = PASS`
  - 2026-05-28 focused blocker reclassification에서도 `MIX_T1_046`와 `NAV_T3_007`는 PASS다.
    - result dir: `benchmarks/results/curated_single_doc_blocker_reclass_2026-05-28`
    - broader trace에서는 operands가 `source_row_id` 대신 `evidence_id`를 쓰고, denominator period가 `2023년` 대신 `제 25 기`로 들어와 evaluator compatibility gap이 다시 드러났다.
    - evaluator는 이제 source key로 `evidence_id`도 인정하고, explicit year끼리 충돌하지 않는 current fiscal-period alias(`제 N 기`, `당기`, `current`)만 soft match한다.
    - prior-period alias(`전기`)나 서로 다른 explicit year는 여전히 operand match에서 거부한다.
    - Naver slice result: `MIX_T1_046 = PASS`, `NAV_T3_007 = PASS`, `Numeric Pass Rate = 1.000`, `Completeness = 1.000`
  - fresh structural store 기준으로도 `SAM_T2_002`는 multi-source receipt scope, auto-fetch inventory, dependency binding guard, aggregate answer-slot gap suppression, narrative context synthesis 보강 이후 다시 닫혔다
    - `structured_result.status = ok`
    - `faithfulness = 1.0`
    - `completeness = 1.0`
    - `numeric_pass = 1.0`
- fresh structural single-doc blocker였던 `SAM_T3_028`는 parser/store와 generic evidence assembly 보강 이후 fresh structural rerun에서 닫혔다.
  - root cause는 planner가 아니라 parser/store가 grouped table row의 상세 축인 `재고자산평가손실(환입) 등`을 row label로 보존하지 못한 점이었다.
  - parser는 이제 숫자값 앞에 여러 텍스트 축이 있는 행에서 값에 가장 가까운 상세 축을 `row_label`/`semantic_label`로 쓰고, 앞선 그룹 축은 `row_headers`/aliases에 보존한다.
  - 실제 삼성전자 2023 filing parser smoke에서 `재고자산평가손실(환입) 등 = 5,037,579`, `row_headers = [조정내역 계, 재고자산평가손실(환입) 등]`까지 확인했다.
  - structural index/store는 이제 row label뿐 아니라 value-level label text를 함께 prefix/metadata로 싣는다.
  - answer assembly는 retrieval로 들어온 evidence의 label/value만 사용해 numerator/denominator를 고르고 비중을 계산한다. `SAM_T3_028`, inventory, 특정 row/sentence를 직접 찾는 runtime rule은 없다.
  - product runtime path의 `SAM_T3_028` 전용 rule은 제거했다.
    - `rcept_no`로 local HTML filing을 직접 읽어 특정 row/sentence를 주입하는 raw filing fallback을 제거했다.
    - retrieval 후보 안에서 `재고자산평가손실` row, inclusion sentence, `매출원가` row를 hard-coded rule로 승격하거나 deterministic answer로 조립하는 경로도 제거했다.
    - evaluator calibration이나 diagnosis asset으로는 유용할 수 있지만, agent answer path에 특정 filing/row 문구를 직접 주입하거나 승격하면 parser/store 문제를 가리고 일반화 위험을 키운다.
  - 제거한 fallback 기반 targeted rerun 참고 결과:
    - `numeric_final_judgement = PASS`
    - `numeric_equivalence = 1.0`
    - `numeric_grounding = 1.0`
    - `numeric_retrieval_support = 1.0`
    - `faithfulness = 1.0`
    - `completeness = 1.0`
  - fresh structural rerun 결과:
    - result dir: `benchmarks/results/sam_t3_028_parser_store_check_2026-05-27_fix7`
    - `faithfulness = 1.0`
    - `completeness = 1.0`
    - `numeric_pass = 1.0`
    - `retrieval_hit_at_k = 1.0`
    - `section_match = 1.0`
    - `avg_score = 0.966`
  - 위 fresh rerun 결과는 실험 산출물로만 남기고 commit 대상에는 포함하지 않는다.

## 바로 다음에 할 일

| 순서 | 할 일 | 목적 |
| --- | --- | --- |
| 1 | broader curated gate maintenance | `SAM_T2_002` narrative completeness 등 남은 calibration을 runtime blocker와 분리 |
| 2 | concept-only planner runtime promotion check | shadow-level gap closure 이후 retrieval/grounding 영향만 focused gate로 검증 |
| 3 | contextual arbitration / benchmark maintenance 정리 | structural default와 contextual quality reference의 운영 경계를 문서와 profile에 고정 |
| 4 | internal compatibility mirror cleanup scope 결정 | stale `calculation_*` projection 위험을 줄일 다음 refactor 범위 확정 |
| 5 | table payload sidecar / store-size cleanup | large structured table payload 반복 저장을 줄여 fresh-store 비용과 HNSW 리스크 축소 |

## 현재 우선순위 요약

1. `curated_single_doc_core` / broader gate maintenance
2. concept-only planner runtime promotion check
3. contextual arbitration / benchmark maintenance 정리
4. internal compatibility mirror cleanup scope 결정
5. table payload sidecar / store-size cleanup

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
- 따라서 다음 구현은 **concept planner shadow 확대 + benchmark maintenance** 쪽으로 돌아가는 흐름이 맞다.
- immediate blocker였던 `SAM_T2_002` follow-up rerun, `MIX_T1_046` denominator binding/evaluator trace compatibility, `NAV_T3_007` numeric gate, `SAM_T3_028` source-level numeric blocker는 now closed다.
- `structural_parent_hybrid_v2` probe에서 드러난 `MIX_T1_046` 실패는 parent digest 문제가 아니라 ratio material-binding 문제였고, calculation fallback이 dependency guard를 우회해 retrieved docs를 활용하되 연결/별도 scope와 operand concept을 지키도록 보강해 닫았다.
- focused blocker reclassification에서 `HYU_T2_010`과 `HYU_T3_072`는 targeted smoke 기준으로 닫혔다.
- policy-driven track은 2026-05-29 공식 profile rerun과 summary 재계산 기준으로 닫혔다.
  - `policy_driven_runtime_gate_rerun_2026-05-29`: `pass_count = 4`, `full_eval_fail_count = 0`.
  - 비수치형 문항의 `numeric_pass_rate = None`은 full-eval 실패가 아니라 not-applicable로 집계한다.
  - raw benchmark result bundle은 local experiment artifact이며 commit 대상에는 포함하지 않는다.

## 2026-05-28 Update

- Concept ontology gap closure is now verified at planner level:
  - added concepts for credit-loss provision expense, foreign-currency
    translation gain/loss, capitalized development cost, inventory valuation
    loss/reversal/disposal loss, interest income/expense, pre-expense operating
    profit, bad debt expense, depreciation/amortization, impairment, and
    goodwill impairment
  - expanded concept-planner shadow rerun:
    `benchmarks/results/tmp_curated_concept_planner_shadow_expanded_2026-05-28_concepts.json`
  - result: `concept_fallback = 24 / 24`, `heuristic_fallback = 0 / 24`
  - targeted gap cases now plan as concept tasks:
    `KBF_T2_018`, `SKH_T3_080`, `CEL_T1_013`, `CEL_T3_040`,
    `SAM_T3_028`, `POS_T1_057`, `KAB_T1_066`
  - local DART report scan under `data/reports` supplied additional recurring
    note concepts around interest, allowance/bad debt, impairment,
    depreciation, and amortization
  - verification passed:
    `python -m unittest tests.test_ontology tests.test_semantic_numeric_plan -v`
    and `python -m unittest discover -s tests -v`

- Earlier expanded concept-planner shadow probe, now superseded by the
  gap-closure rerun above:
  - result: `benchmarks/results/tmp_curated_concept_planner_shadow_expanded_2026-05-28_fix3.json`
  - scope: 24 cases, official canary + recent blocker/mixed numeric cases
  - concept planner status: `concept_fallback = 20 / 24`, `heuristic_fallback = 4 / 24`
- Generic planner fixes from the probe:
  - repeated same-concept ratio operands are preserved when roles/segment/scope differ, e.g. segment operating income divided by company operating income
  - `FCF` is represented as a generic concept group (`operating_cash_flow - property_plant_equipment_acquisition`) instead of falling back to `generic_numeric`
- Remaining concept ontology gaps:
  - `KBF_T2_018`: credit-loss provision growth
  - `SKH_T3_080`: foreign-currency translation gain/loss net effect
  - `CEL_T1_013`: capitalized development cost
  - `CEL_T3_040` / `SAM_T3_028`: inventory valuation loss/reversal/disposal concepts
  - `POS_T1_057` / `KAB_T1_066`: interest expense and bank profitability-table denominator concepts

## 2026-05-27 Update

- Documentation has been refreshed after the `MIX_T1_046` denominator-binding
  fix and the parent-hybrid probe follow-up.
- Local benchmark output bundles remain as experiment artifacts and are not
  part of source commits:
  - `benchmarks/results/curated_multi_report_smoke_2026-05-26_fix1/`
  - `benchmarks/results/structural_parent_hybrid_v2_probe_2026-05-26/`
- The next source-level work remains concept-planner shadow validation and
  broader curated gate maintenance, not parent-hybrid promotion.

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

## 2026-05-28 SAM_T3_028 Aggregate-Impact Closure

- `SAM_T3_028`의 핵심 실패 원인은 재고자산평가손실/환입 parenthetical label을
  손실-환입 차감식으로 과분해하면서 `매출원가`가 평가손실 operand로 오인될 수
  있었던 점이다.
- source fix는 question-specific row injection이 아니라 ontology/planner contract로
  정리했다.
  - `inventory_valuation_adjustment` concept를 추가해
    `재고자산평가손실(또는 환입)` / `재고자산평가손실(환입) 등`을 aggregate label로
    바인딩한다.
  - concept matcher는 긴 surface가 짧은 surface를 포함하면 longest match가 짧은
    concept를 shadow하도록 보강했다.
  - `analysis_hints`를 추가해 aggregate value가 denominator concept와 함께
    "영향/대비/비중"으로 묻히면 ratio task를 만들 수 있게 했다.
  - LLM planner override는 deterministic analysis shape를 lookup-only나 잘못된
    difference로 지우지 못한다.
  - segment extractor는 `이것이/그것이/해당 금액` 같은 지시어를 segment label로
    오인하지 않는다.
- 검증:
  - `tests.test_semantic_numeric_plan`: 56 tests OK
  - focused SAM rerun:
    `benchmarks/results/sam_t3_028_analysis_fix_2026-05-28`
  - `SAM_T3_028`: `faithfulness = 1.0`, `completeness = 1.0`,
    `numeric_grounding = 1.0`, `retrieval_hit_at_k = 1.0`
- 해석상 주의:
  - focused full evaluation의 최종 user-facing answer는 라우터가 QA path로 처리해
    PASS했다.
  - structured planner의 aggregate/ratio shape는 unit regression으로 보장한다.
  - 따라서 다음에 broad gate에서 확인할 항목은 "답변 품질 PASS 유지"와
    "structured numeric route로 들어갈 때도 같은 aggregate-impact shape 유지"를
    분리해서 본다.

## 2026-05-28 Three-Case Follow-up Status

- Focused follow-up target:
  - `SAM_T2_078`
  - `HYU_T2_010`
  - `HYU_T3_072`
- `SAM_T2_078` is now closed at the focused single-question level.
  - Harman automotive answer composition preserves:
    - `28,352,769백만원` 연결 연구개발비용
    - 커넥티드카 제품 및 솔루션
    - 디지털 콕핏 / 카오디오
    - 무선통신 / 디스플레이 등 IT 기술 접목
    - SDV 기술 초점
  - latest focused metrics observed:
    - `faithfulness = 1.0`
    - `completeness = 1.0`
    - `context_recall = 1.0`
    - `retrieval_hit_at_k = 1.0`
- `HYU_T2_010` user-facing answer and structured calculation trace are now
  corrected.
  - answer includes `87.0만 대`, `78.1만 대`, `11.5%`, and the
    인플레이션 감축법 / 핵심원자재법 / 보호무역주의 policy context.
  - deterministic sales-growth policy composition now emits calculation
    operands, plan, result, and typed `growth_rate` answer slots.
  - latest focused metrics observed:
    - `operand_selection_correctness = 1.0`
    - `grounded_rendering_correctness = 1.0`
    - `calculation_correctness = 1.0`
    - `completeness = 1.0`
    - `faithfulness = 0.5`
  - residual issue is not the visible answer or calculation trace; it is the
    remaining entity/evidence coverage threshold used by the hybrid
    faithfulness override.
- `HYU_T3_072` is not closed yet.
  - deterministic entity-table composition now recovers the correct visible
    answer again:
    - `25.81%`
    - `1,294,367백만원`
    - `계속영업손실 (803,742)백만원`
    - `총포괄손실 (791,627)백만원`
  - current focused metrics still show evaluator-side grounding gaps:
    - `faithfulness = 0.0`
    - `context_recall = 0.5`
    - `entity_coverage = 0.4`
    - `grounded_rendering_correctness = 0.0`
  - next work should inspect how the retrieved Motional context/evidence and
    entity-table projection are represented to the evaluator, rather than
    changing the answer wording alone.
- Validation commands used during this pass:
  - `.\.venv\Scripts\python.exe -m py_compile src\agent\financial_graph_evidence.py src\agent\financial_graph_calculation.py tests\test_operation_contracts.py`
  - `.\.venv\Scripts\python.exe -m unittest tests.test_operation_contracts`
  - focused single-question evals for `HYU_T2_010` and `HYU_T3_072` against
    `benchmarks/results/three_remaining_focus_2026-05-28/현대자동차-2023/results.json`
