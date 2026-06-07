# Experiment History

이 문서는 benchmark와 retrieval 파이프라인이 버전별로 어떻게 바뀌었는지, 그리고 그때 실험 결과가 어떻게 달라졌는지를 한 번에 보기 위한 기록이다.

## At a Glance

| 항목 | 현재 해석 |
| --- | --- |
| 문서 역할 | append-only experiment log |
| 읽는 순서 | `큰 흐름 -> Timeline Index -> 필요한 버전 상세` |
| 초기 국면 | 저비용 ingest 후보 탐색과 다기업 일반화 검증 |
| 중간 전환 | retrieval 문제와 generation 문제를 분리해서 보기 시작 |
| 최근 전환 | single-document benchmark와 evaluator를 먼저 고정 |
| raw artifact 위치 | 각 버전 디렉터리의 `summary.md`, `results.json`, `cross_company_summary.md` |

## Timeline Index

| 버전 / 단계 | 무엇을 검증했나 | 핵심 takeaway |
| --- | --- | --- |
| [v1 Legacy Local Test](#v1-legacy-local-test) | 초기 low-cost ingest 후보 비교 | `contextual_all`만 안정적인 baseline으로 남음 |
| [v2 Low-Cost Retrieval](#v2-low-cost-retrieval) | parent/selective/hybrid 저비용 retrieval | 비용 절감 가능성은 보였지만 single-doc 한계 존재 |
| [v3 Generalization](#v3-generalization) | 삼성전자 -> 다기업 일반화 | single-company winner가 cross-company winner가 아님 |
| [v4 Generalization Fix](#v4-generalization-fix) | parser / evaluation 보정 후 재검증 | ingest 비용보다 query-stage miss와 abstention이 더 큰 문제로 드러남 |
| [dev_fast Cache Check](#dev_fast-cache-check) | 빠른 반복 실험 루프 점검 | cache 기반 반복 속도 개선 확인 |
| [Graph Micro + Zero-Cost Prefix (2026-04-22)](#graph-micro--zero-cost-prefix-2026-04-22) | graph / zero-cost prefix 실험 | 구조 그래프의 가능성과 한계를 함께 확인 |
| [v5 / v6 / v7 Faithfulness Follow-up](#v5--v6--v7-faithfulness-follow-up) | faithfulness 흔들림 원인 추적 | retrieval보다 answer synthesis 문제가 큼 |
| [Typed Compression / Validation and Sentence-Level Validator](#typed-compression--validation-and-sentence-level-validator) | generation을 compression 문제로 재정의 | free-form generation보다 structured pipeline이 유리 |
| [Numeric Evaluator Follow-up](#numeric-evaluator-follow-up) | 숫자 질문 평가 문제 정리 | generic faithfulness만으로는 부족 |
| [Numeric Evaluator Implementation](#numeric-evaluator-implementation) | numeric evaluator 1차 구현 | numeric path를 별도 evaluator/resolver로 분리 |
| [Typed Compression / Validation Outputs](#typed-compression--validation-outputs) | structured output artifact 보강 | debugging/traceability 향상 |
| [Reset Point: Single-Document Evaluation First](#reset-point-single-document-evaluation-first) | 방향 재정렬 | single-document benchmark와 evaluator를 먼저 고정 |
| [Prefix + Selective Contextual Retrieval Focus Run (2026-04-23)](#prefix--selective-contextual-retrieval-focus-run-2026-04-23) | selective/prefix retrieval 재평가 | source miss와 routing 연계 문제 확인 |
| [Evaluator + Routing Cascade v1 (2026-04-23)](#evaluator--routing-cascade-v1-2026-04-23) | evaluator + routing 구조 개편 | query routing을 cascade로 재구성 |
| [Routing Calibration + Ambiguity Guard (2026-04-24)](#routing-calibration--ambiguity-guard-2026-04-24) | ambiguity guard / calibration | routing variance를 줄이는 쪽으로 이동 |
| [Numeric Extractor Node (2026-04-26)](#numeric-extractor-node-2026-04-26) | numeric generation path 분리 | numeric 질문은 extractor 기반 path가 더 안정적 |
| [MAS Smoke Outcome Refresh (2026-06-07)](#mas-smoke-outcome-refresh-2026-06-07) | live/default MAS smoke outcome 관측 | acceptance contract는 선명해졌고, valid default-store compact contract는 source-controlled baseline으로 고정 |

## 보는 법

| 섹션 | 무엇을 보면 되나 |
| --- | --- |
| `코드 / 설정 변화` | 무엇을 바꿨는지 |
| `핵심 결과` | 어떤 후보가 좋아졌거나 실패했는지 |
| `해석` | 왜 다음 버전으로 넘어갔는지 |

상세 원본 결과는 각 버전 디렉터리의 `results.json`, `summary.md`, `cross_company_summary.md`를 참고한다.

## MAS Smoke Outcome Refresh (2026-06-07)

참조:

- `benchmarks/results/mas_e2e_smoke_outcome_refresh_2026-06-07/`
- `benchmarks/results/mas_e2e_smoke_outcome_refresh_replan1_2026-06-07/`
- `benchmarks/results/mas_e2e_smoke_failure_diagnostics_2026-06-07/`
- `benchmarks/results/mas_direct_worker_probe_2026-06-07/`

### 무엇을 검증했나

- PR #39 이후 `mas_e2e_smoke`의 새 `final_acceptance_outcome` surface가
  실제 live/default MAS smoke에서 어떤 상태를 보여주는지 확인했다.
- raw output은 local experiment artifact로만 유지하고 commit 대상에는
  포함하지 않는다.

### 결과

| Run | Key outcome |
| --- | --- |
| default `replan_budget = 0` | `final_acceptance_outcome_counts = {"blocked_without_replan": 2}`, `blocked_count = 2`, final source counts all `0` |
| `--replan-budget 1` | `final_acceptance_outcome_counts = {"blocked_after_replan": 2}`, `replan_routed_count = 2`, `blocked_count = 2`, final source counts all `0` |

Both runs reported `embedding_compatibility.status = unknown`, no critic
acceptance issues, and no task/artifact integrity error in the final trace. The
blocking condition was material-empty execution: Analyst tasks failed with
incomplete numeric results, Researcher tasks failed with empty narrative
results, and final synthesis emitted a blocked/refusal answer because there were
no completed worker artifacts to carry forward.

Follow-up diagnostic surface:

| Run | Key diagnostic |
| --- | --- |
| `mas_e2e_smoke_failure_diagnostics_2026-06-07` | `worker_failure_count = 4`, `worker_failure_missing_artifact_count = 4`, `worker_failure_assignee_counts = {"Analyst": 2, "Researcher": 2}`, `worker_failure_reason_counts = {"incomplete numeric result": 2, "empty narrative result": 2, "missing_worker_artifact": 4}` |
| `mas_direct_worker_probe_2026-06-07` | Planner created `2` Analyst and `2` Researcher tasks, but direct Analyst status was `no_retrieved_docs = 2` and direct Researcher status was `no_raw_retrieval = 2`; store inventory reported `chroma_count = 0`, `bm25_doc_count = 0`, `parent_count = 0`, and `structure_graph_node_count = 0` |
| empty-store preflight | `mas_e2e_smoke` now stops before `VectorStoreManager` / LLM work when the Chroma collection exists but embeddings and sidecar material are all zero; the live default run fails in about `5s` with `Store appears empty for MAS smoke` |
| `mas_default_valid_store_restored_2026-06-07` | Default store moved to the populated Samsung 2023 policy-gate store and the smoke derives embedding runtime from store signature; override-free live run reports `accepted_without_replan = 2`, `blocked_count = 0`, `integrity_error_count = 0`, `worker_failure_count = 0`, final source tasks `4`, artifacts `8`, and evidence refs `55` |
| source-controlled compact baseline | `tests/fixtures/mas_e2e_smoke/default_valid_store_contract_baseline.json` now captures the reviewed valid-store compact contract; `check_mas_e2e_smoke_contract` uses it by default while raw live smoke output remains local-only |

The follow-up changed only smoke observability and CLI robustness: failed worker
diagnostics are now surfaced per case and in the summary, and `--output` creates
its parent directory before writing. The raw JSON remains a local-only
experiment artifact.

### 해석

- The new smoke outcome contract is doing useful work: it distinguishes
  `blocked_without_replan` from `blocked_after_replan` without manual trace
  reading.
- This is not a critic acceptance bug. Critic rejection issue counts stayed
  `0`; the final close was blocked by lack of source material.
- The direct worker probe separated the immediate blocker from planner,
  self-reflection, critic, and final merge behavior. The empty-store preflight
  now prevents API waste when collection and sidecar counts are all zero, and
  the default smoke has been restored to a populated store with matching
  store-signature embedding runtime selection.


## 큰 흐름

버전 흐름을 큰 설계 변화 기준으로 요약하면 다음과 같다.

1. **저비용 ingest 후보 탐색**
   - `plain`, `parent_only`, `selective` 계열을 비교
2. **multi-company generalization**
   - 삼성전자 1건에서 좋아 보이던 후보가 다른 기업에서도 재현되는지 확인
3. **query-stage / answer-stage failure 분리**
   - abstention, risk drift, business over-extension을 분리해서 보기 시작
4. **structured evidence / compression / validation**
   - answer generation을 free-form generation보다 compression 문제로 재정의
5. **single-document Golden Dataset + evaluator 우선**
   - 이제는 multi-company 실험보다, 단일 문서 기준선과 metric을 먼저 고정하는 단계로 이동

---

## v1 Legacy Local Test

참조:

- [archive/v1_legacy_local_test_2026-04-16](../../benchmarks/archive/v1_legacy_local_test_2026-04-16)

### 코드 / 설정 변화

- 초기 low-cost retrieval 비교
- 삼성전자 2024 사업보고서 1건 기준
- 후보 비교:
  - `plain_2500_320`
  - `contextual_all_2500_320`
  - `contextual_parent_only_2500_320`
  - `contextual_selective_2500_320`
  - `contextual_1500_200`

### 핵심 결과

- `contextual_all_2500_320`
  - screening 통과
- `plain_2500_320`
  - 비용은 거의 없지만 risk retrieval miss
- `contextual_parent_only_2500_320`
  - 숫자 질문에서 retrieval miss
- `contextual_selective_2500_320`
  - 비용 절감 폭이 작고 business overview miss
- `contextual_1500_200`
  - 더 느리고 business overview miss

### 해석

- 저비용 후보는 가능성이 있었지만 아직 retrieval 품질이 충분히 안정적이지 않았다.
- 이후 실험은 selective rule과 parent-child 변형을 더 세밀하게 다듬는 방향으로 넘어갔다.

---

## v2 Low-Cost Retrieval

참조:

- [v2_low_cost_2026-04-16/summary.md](../../benchmarks/results/v2_low_cost_2026-04-16/summary.md)

### 코드 / 설정 변화

- benchmark 전용 ingest mode 확장
  - `contextual_parent_hybrid`
  - `contextual_selective_v2`
- selector reason, contamination, failure example 기록 강화

### 핵심 결과

- `contextual_parent_only_2500_320`
  - screening 통과
  - baseline 대비
    - `API calls -86.7%`
    - `ingest time -77.8%`
- `contextual_selective_v2_2500_320`
  - 비용 절감은 컸지만 business overview miss로 탈락
- `contextual_parent_hybrid_2500_320`
  - 통과는 했지만 baseline보다 비싸 실익이 없었음

### 해석

- “저비용 후보도 품질 하한선을 넘길 수 있다”는 가능성을 처음 보여준 버전이다.
- 다만 삼성전자 1건만으로는 일반화 판단이 불가능해, 다음 단계는 다기업 일반화 검증으로 이동했다.

---

## v3 Generalization

참조:

- [v3_generalization_2026-04-16/cross_company_summary.md](../../benchmarks/results/v3_generalization_2026-04-16/cross_company_summary.md)

### 코드 / 설정 변화

- 기업별 canonical eval dataset 도입
  - 삼성전자
  - SK하이닉스
  - NAVER
- cross-company summary와 winner ranking 생성

### 핵심 결과

- 공통 screening 통과 후보 없음
- `삼성전자`
  - `contextual_parent_hybrid_2500_320`만 통과
- `SK하이닉스`
  - `contextual_all_2500_320`만 통과
- `NAVER`
  - 통과 후보 없음

### 해석

- 삼성전자 1건에서 좋아 보인 후보가 다른 기업에서는 재현되지 않았다.
- 특히 NAVER는 `section_path` 비정상 누적과 business overview retrieval 문제가 드러나, parser / evaluation 보정이 먼저 필요하다는 결론으로 이어졌다.

---

## v4 Generalization Fix

참조:

- [v4_generalization_fix_2026-04-17/cross_company_summary.md](../../benchmarks/results/v4_generalization_fix_2026-04-17/cross_company_summary.md)

### 코드 / 설정 변화

- NAVER `section_path` heading-level 정규화
- numeric section alias 확장
  - `매출현황`
  - `재무제표`
  - `요약재무`
  - `연결재무제표`
  - `연결재무제표 주석`
- answerable query 평가에서 full abstention 패턴만 강하게 페널티
- release generalization을 회사별 job으로 분리해 partial / completed run을 지원

### 핵심 결과

- `run_status = completed`
- 3개 기업 공통 screening 통과 후보 없음

후보별 요약:

- `contextual_all_2500_320`
  - 가장 안정적인 baseline
  - 평균 full eval:
    - `faithfulness 0.453`
    - `context recall 0.589`
- `contextual_parent_only_2500_320`
  - 평균 절감:
    - `API calls -86.0%`
    - `ingest time -84.7%`
    - `estimated cost -86.8%`
  - 그러나 numeric / risk / R&D에서 answerable smoke abstention 반복
- `contextual_selective_v2_2500_320`
  - 평균 절감:
    - `API calls -59.6%`
    - `ingest time -61.6%`
    - `estimated cost -60.6%`
  - 그러나 business overview / risk miss 반복
- `contextual_parent_hybrid_2500_320`
  - 평균 비용 이점이 없고 baseline보다 비싼 경우가 있었음

### 해석

- parser / evaluation 보정 이후에도 저비용 후보의 주된 문제는 ingest 비용이 아니라 query-stage abstention과 category-specific retrieval miss였다.
- 그래서 다음 실험 우선순위는
  - 더 싼 ingest mode 추가
  보다
  - numeric / risk / R&D abstention 완화
  - NAVER business overview retrieval 개선
  - missing-information hallucination 억제
  로 이동했다.

---

## dev_fast Cache Check

참조:

- [dev_fast_cache_check_2026-04-17/삼성전자-2024/summary.md](../../benchmarks/results/dev_fast_cache_check_2026-04-17/삼성전자-2024/summary.md)

### 코드 / 설정 변화

- `dev_fast` / `release_generalization` 프로파일 분리
- `Hybrid Cache` 도입
  - `stores/...`
  - `context_cache/...`
- 같은 설정 재실행 시 contextual ingest API를 다시 호출하지 않도록 변경

### 핵심 결과

- 삼성전자 1회사 screening-only를 2회 연속 실행
- 1차 run:
  - 약 `13분 16초`
- 2차 run:
  - 약 `5분 27초`
- 2차 run에서는 모든 후보가:
  - `cache_hit = true`
  - `cache_level = store`
  - `ingest.api_calls = 0`
  - `ingest.elapsed_sec = 0.0`

### 해석

- 반복 실험에서 가장 비싼 contextual ingest 비용을 다시 쓰지 않는 구조가 실제로 검증됐다.
- 이후 일상 루프는 `dev_fast`, release-grade 비교는 회사별 분리 실행이 기본 운영 방식으로 자리 잡았다.

---

## Current Takeaway

현재까지의 실험 흐름은 이렇게 요약할 수 있다.

1. 삼성전자 1건에서 저비용 후보 가능성을 확인했다.
2. 다기업 일반화로 확장하자 공통 승자가 사라졌다.
3. parser / evaluation / workflow를 보정했지만, 핵심 실패는 여전히 query-stage abstention과 category-specific retrieval miss였다.
4. 따라서 지금의 핵심 과제는 “더 싼 ingest mode를 찾는 것”보다 “현재 저비용 후보가 왜 답을 포기하는지 줄이는 것”이다.

---

## Graph Micro + Zero-Cost Prefix (2026-04-22)

참조:

- [graph_micro_2026-04-22](../../benchmarks/results/graph_micro_2026-04-22)
- [graph_micro_constrained_2026-04-22](../../benchmarks/results/graph_micro_constrained_2026-04-22)
- [graph_micro_prefix_2026-04-22](../../benchmarks/results/graph_micro_prefix_2026-04-22)

### 코드 / 설정 변화

- `document-structure graph` 추가
  - `parent_id`
  - `sibling_prev`, `sibling_next`
  - `section_lead`
  - `described_by_paragraph`
  - `table_context`
- `retrieve -> expand_via_structure_graph -> evidence` 경로 추가
- `compact_review.md/html` 추가
  - 질문 / 예시 답변 / 실제 답변 / retrieved chunks / runtime evidence를 간결하게 검수하기 위한 artifact

### 1차 결과

- `plain + graph expansion`만으로는 `contextual_all` 대체 실패
- 비용/시간은 크게 줄었지만
- `q_009` 재무 리스크 질문에서 seed retrieval miss가 반복
- graph expansion은 잘못 잡힌 `이사회`, `경영진단`, `감사제도` 섹션을 더 증폭시키는 경우가 있었다

### 2차 결과: constrained graph

- 제약 추가:
  - `table -> paragraph prev만 허용`
  - `sibling_next 제거`
  - `max_docs = 8`
- noise는 줄었지만, seed retrieval miss 자체는 해결하지 못했다

### 3차 결과: zero-cost prefix

- `plain` / `plain_graph` 인덱싱 텍스트 앞에
  - `[섹션]`
  - `[분류]`
  - `[키워드]`
  를 hardcoded prefix로 삽입
- 목적: LLM 비용 없이 vocabulary mismatch를 줄여 seed retrieval을 보강

핵심 결과:

- `q_009` 재무 리스크 질문
  - prefix 후 plain 계열에서도 `hit@k = 1.0`
  - `plain_graph_1500_200`는 `section_match = 0.75`
- `q_001` 연결 기준 매출액 질문
  - 여전히 `연결재무제표 주석` 표들에 많이 쏠림
  - answerable abstention이 남음

### 해석

- graph expansion은 retrieval replacement가 아니라 **retrieval booster**다
- `q_009`의 핵심 병목은 graph가 아니라 seed retrieval miss였고, 이는 zero-cost prefix로 크게 개선됐다
- 반면 `q_001`은 retrieval만의 문제가 아니라
  - `연결 기준 매출액`
  - `매출 및 수주상황`
  - `연결 손익계산서`
  - `요약재무정보`
  를 하나의 target family로 보지 못하는 **numeric query planning / target alignment** 문제로 더 좁혀졌다

---

## v5 / v6 / v7 Faithfulness Follow-up

참조:

- [v5_fulleval_2026-04-20/삼성전자-2024/summary.md](../../benchmarks/results/v5_fulleval_2026-04-20/삼성전자-2024/summary.md)
- [v6_faithfulness_guard_2026-04-20/삼성전자-2024/summary.md](../../benchmarks/results/v6_faithfulness_guard_2026-04-20/삼성전자-2024/summary.md)
- [v7_faithfulness_guard_refine_2026-04-20/삼성전자-2024/summary.md](../../benchmarks/results/v7_faithfulness_guard_refine_2026-04-20/삼성전자-2024/summary.md)

### 코드 / 설정 변화

- `v5`
  - query_type 6종 확장
  - retrieval lane 분리
  - risk evidence verbatim 제한
  - evaluator context 확장
- `v6`
  - business_overview / numeric / risk answer를 더 보수적으로 만드는 guard 추가
  - section bias와 output style 강화
- `v7`
  - 숫자 1개 / 개수 1개 질문을 더 짧게 답하도록 추가 제약

### 핵심 결과

- baseline `contextual_all_2500_320`의 삼성전자 5문항 full eval faithfulness:
  - `v5`: `0.380`
  - `v6`: `0.500`
  - `v7`: `0.600`
- 하지만 `v7`에서는:
  - `business_overview_001`, `business_overview_003` 회복
  - `risk_analysis_001`은 다시 `0.0`

### 해석

- 일부 metric 회복은 가능했지만, 질문 유형별 rule 추가가 다른 유형에서 새 부작용을 만들었다.
- 이건 “hardcoded rule을 더 붙이면 장기적으로 안 된다”는 신호로 해석한다.
- 따라서 이후 방향은 점수 자체를 더 올리는 것보다:
  - answer generation 원칙 문서화
  - 최근 rule inventory 분류
  - evidence compression 중심의 구조 재정의
로 옮긴다.

---

## Typed Compression / Validation and Sentence-Level Validator

참조:

- [dev_fast_cache_check_2026-04-17/삼성전자-2024/review.md](../../benchmarks/results/dev_fast_cache_check_2026-04-17/삼성전자-2024/review.md)
- [dev_fulleval_sentence_validator_2026-04-21/삼성전자-2024/summary.md](../../benchmarks/results/dev_fulleval_sentence_validator_2026-04-21/삼성전자-2024/summary.md)
- [dev_focus_validator_2026-04-21/삼성전자-2024/summary.md](../../benchmarks/results/dev_focus_validator_2026-04-21/삼성전자-2024/summary.md)

### 코드 / 설정 변화

- `compression -> validation`을 typed output으로 확장
  - `selected_claim_ids`
  - `draft_points`
  - `kept_claim_ids`
  - `dropped_claim_ids`
  - `unsupported_sentences`
  - `sentence_checks`
- sentence-level validator 추가
- validator 결과를 그대로 쓰지 않고, 후처리에서
  - intro sentence 제거
  - 근거 없는 keep 강등
  - 중복 claim 제거
  - 과잉 일반화 문장 제거
  로 연결

### 핵심 결과

- typed artifact는 review artifact에 안정적으로 남는다.
- 하지만 5문항 full eval 기준으로는:
  - retrieval / citation 지표는 소폭 개선
  - `contextual_all`의 answer 품질 지표는 오히려 하락
- 3문항 focus run에서는 처음으로 실제 pruning이 의미 있게 발생했다.
  - `contextual_all / risk_analysis_001`
    - 도입 문장 `drop_redundant`
  - `contextual_parent_only / risk_analysis_001`
    - 도입 문장 `drop_unsupported`
    - `dropped_claim_ids = ev_002`

### 해석

- validator는 이제 “보이기만 하는 단계”는 지났다.
- 하지만 아직 “잘 자르는 validator”는 아니다.
- 현재 병목은 validator 강도보다, `business_overview` / `risk`에서 어떤 claim을 같이 선택하느냐에 더 가깝다.
- 따라서 다음 단계는 validator를 더 세게 만드는 것보다:
  - `claim_type`
  - `topic_key`
  - group-wise selection
  중심으로 compression 앞단을 더 구조화하는 쪽이다.

---

## Numeric Evaluator Follow-up

참조:

- [../architecture/numeric_evaluation_architecture.md](../architecture/numeric_evaluation_architecture.md)
- [dev_fast_cache_check_2026-04-17/삼성전자-2024/review.md](../../benchmarks/results/dev_fast_cache_check_2026-04-17/삼성전자-2024/review.md)

### 코드 / 설정 변화

- structured runtime evidence를 benchmark 결과에 기록
- 숫자 질문 false fail을 generation 문제가 아니라 evaluator 문제로 분리해서 해석
- `numeric_fact`는 일반 서술형 `faithfulness`와 분리해 다루는 architecture 방향 문서화

### 핵심 관찰

- `numeric_fact_001`은 사람이 보기엔 사실상 맞는 답인데도 `faithfulness = 0.0`이 반복됐다.
- 대표 케이스:
  - canonical 표현: `300조 8,709억원`
  - actual answer 표현: `300,870,903 백만원`
- runtime evidence와 retrieved context는 충분했기 때문에, 이 케이스는 retrieval failure보다 evaluator limitation에 가깝다고 판단했다.

### 해석

- 숫자 질문은 값 동치성, grounding, retrieval support를 따로 봐야 한다.
- 따라서 다음 단계는 generation rule 추가보다:
  - `Numeric Extractor`
  - `Numeric Equivalence Checker`
  - `Grounding Judge`
  - `Retrieval Support Check`
  - `Conflict Resolver`
  구조를 실제 evaluator에 반영하는 것이다.

---

## Numeric Evaluator Implementation

참조:

- [dev_fast_cache_check_2026-04-17/삼성전자-2024/results.json](../../benchmarks/results/dev_fast_cache_check_2026-04-17/삼성전자-2024/results.json)
- [dev_fast_cache_check_2026-04-17/삼성전자-2024/review.csv](../../benchmarks/results/dev_fast_cache_check_2026-04-17/삼성전자-2024/review.csv)

### 코드 / 설정 변화

- `src/ops/evaluator.py`에 `numeric_fact` 전용 evaluator path 추가
  - `Numeric Extractor`
  - `Numeric Equivalence Checker`
  - `Grounding Judge`
  - `Retrieval Support Check`
  - `Conflict Resolver`
- `src/ops/benchmark_runner.py`가 numeric evaluator 결과를 benchmark artifact에 직렬화

### 핵심 결과

- `numeric_fact_001`
  - generic `faithfulness = 0.0`
  - `numeric_equivalence = 1.0`
  - `numeric_grounding = 1.0`
  - `numeric_retrieval_support = 1.0`
  - `numeric_final_judgement = PASS`

### 해석

- 숫자 질문에서 generic `faithfulness`와 실제 정답성 / grounding 해석이 갈라질 수 있다는 점이 benchmark 결과에 명확히 드러났다.
- 이 시점부터 `numeric_fact`의 주 판정은 `numeric_final_judgement`로 보고, generic `faithfulness`는 보조 참고치로 낮춰 해석한다.

---

## Typed Compression / Validation Outputs

참조:

- [../architecture/answer_generation_principles.md](../architecture/answer_generation_principles.md)
- [../architecture/architecture_direction.md](../architecture/architecture_direction.md)

### 코드 / 설정 변화

- `src/agent/financial_graph.py`
  - `CompressionOutput`
  - `ValidationOutput`
- `src/ops/evaluator.py`
  - per-question 결과에 claim selection / drop 정보 추가
- `src/ops/benchmark_runner.py`
  - `results.json`, `review.csv`, `review.md`에 새 필드 직렬화

추가된 필드:

- `selected_claim_ids`
- `draft_points`
- `kept_claim_ids`
- `dropped_claim_ids`
- `unsupported_sentences`

동시에 질문 wording을 직접 읽어 output style을 바꾸던 local optimization은 제거했다.

### 핵심 의의

- 기존 `compression -> validation`은 구조적으로는 분리됐지만, 결과 artifact에는 여전히 문자열 중심 정보만 남았다.
- 이제는 reviewer artifact에서
  - 어떤 claim을 선택했는지
  - 무엇을 버렸는지
  - 어떤 문장을 unsupported로 제거했는지
  를 직접 볼 수 있게 됐다.

### 현재 상태

- 코드 반영 완료
- 문법 검증 완료
- 아직 이 새 typed field를 포함한 full eval 재실행은 하지 않았다

### 해석

- 이 단계의 목적은 점수 개선이 아니라 **failure analysis를 더 설명 가능하게 만드는 것**이다.
- 다음 실험부터는 `business_overview` / `risk` 회귀를 “점수 변화”가 아니라 “claim 선택과 제거 흐름”까지 포함해 분석할 수 있어야 한다.

---

## Reset Point: Single-Document Evaluation First

최근 validator, numeric evaluator, typed artifact까지 진행한 뒤 내린 결론은 다음과 같다.

- retrieval / generation의 국소 조정은 계속 가능하다
- 하지만 그 전에 “무엇을 좋은 답으로 볼 것인가”를 단일 문서에서 먼저 고정해야 한다

이 판단의 이유:

- multi-company benchmark는 parser 차이, section alias 차이, evaluator 차이가 함께 섞인다
- local rule이 늘어나면 benchmark-specific optimization으로 흐르기 쉽다
- single-document 기준선이 먼저 있어야 이후 구조 변경을 더 신뢰성 있게 비교할 수 있다

따라서 다음 큰 방향은:

1. 삼성전자 2024 사업보고서 1건 기준 Golden Dataset 구축
2. 질문 taxonomy 확정
3. evaluator 분리
4. single-document benchmark runner 정리
5. 그 다음에만 retrieval / compression / validation 실험 재개

이 전략은 [../evaluation/single_document_eval_strategy.md](../evaluation/single_document_eval_strategy.md)에 정리했다.

---

## Prefix + Selective Contextual Retrieval Focus Run (2026-04-23)

참조:

- [dev_fast_focus_selective_prefix_2026-04-23/삼성전자-2024/summary.md](../../benchmarks/results/dev_fast_focus_selective_prefix_2026-04-23/삼성전자-2024/summary.md)
- [dev_fast_focus_selective_prefix_2026-04-23/삼성전자-2024/results.json](../../benchmarks/results/dev_fast_focus_selective_prefix_2026-04-23/삼성전자-2024/results.json)

### 코드 / 설정 변화

- `src/ops/benchmark_runner.py`
  - `contextual_selective_v2` 경로가 `use_zero_cost_prefix`를 함께 받을 수 있도록 확장
- `benchmarks/profiles/dev_fast_focus.json`
  - `contextual_selective_v2_prefix_2500_320` 후보 추가

### 핵심 결과

- `plain_prefix_2500_320`
  - retrieval seed는 강했지만 `numeric_fact_001`에서 “구체적인 수치 정보가 없다”고 답함
  - `numeric_final_judgement = FAIL`
- `contextual_selective_v2_prefix_2500_320`
  - `screen_pass = yes`
  - `faithfulness 0.675`
  - `answer_relevancy 0.580`
  - `context_recall 0.625`
  - `numeric_pass = 1.000`

질문별 메모:

- `numeric_fact_001`
  - `plain_prefix`는 실패
  - `selective_v2_prefix`는 `300조 8,709억원`으로 복구
- `risk_analysis_001`
  - `selective_v2_prefix`는 `위험관리 및 파생거래` 중심 retrieval과 grounded answer를 유지

### 해석

- `Zero-Cost Prefix`만으로는 표 기반 숫자 질문의 구조적 희소성을 충분히 복원하지 못한다.
- `table` 청크에만 선택적으로 contextualization을 주고 prefix를 함께 유지하는 조합이 더 현실적인 타협점이다.
- 이 시점부터 low-cost 방향의 주력 후보는 `plain_prefix`보다 `contextual_selective_v2_prefix`가 된다.

### 다음 단계

- retrieval / ingest 코드는 잠시 freeze
- numeric evaluator aggregate / reporting을 먼저 정리
- 그 다음 `business_overview` / `risk` generation 튜닝으로 넘어가기

---

## Evaluator + Routing Cascade v1 (2026-04-23)

참조:

- [dev_fast_focus_eval_tuned_2026-04-23/삼성전자-2024/summary.md](../../benchmarks/results/dev_fast_focus_eval_tuned_2026-04-23/삼성전자-2024/summary.md)
- [dev_fast_focus_routing_cascade_2026-04-23/삼성전자-2024/summary.md](../../benchmarks/results/dev_fast_focus_routing_cascade_2026-04-23/삼성전자-2024/summary.md)
- [../architecture/query_routing_rearchitecture.md](../architecture/query_routing_rearchitecture.md)

### 코드 / 설정 변화

- evaluator
  - numeric PASS 시 generic faithfulness short-circuit
  - completeness judge 및 reason 추가
- query routing
  - `intent + format_preference` state 분리
  - semantic router fast-path
  - few-shot LLM fallback
  - rerank / retrieval block-type 보정을 `format_preference` 기준으로 전환

### 핵심 결과

- evaluator tuning 후
  - `numeric_fact_001`에서 `raw_faithfulness=0.0`이어도 `faithfulness=1.0` 보정이 실제로 적용됨
- routing cascade v1 후 `contextual_selective_v2_prefix_2500_320`
  - `faithfulness 0.925`
  - `answer_relevancy 0.632`
  - `context_recall 0.625`
  - `completeness 0.775`
  - `numeric_pass 1.000`
- `risk_analysis_001`
  - semantic top-1이 흔들려도 fast-path가 억제되고 fallback에서 `risk / paragraph`로 교정
- `business_overview_001`
  - fallback에서 `business_overview / mixed`로 교정
- `business_overview_003`
  - fast-path로 `business_overview / mixed`

### 해석

- 이 시점부터 병목은 “retrieval 규칙을 더 붙일 것인가”보다
  - query routing variance를 얼마나 줄일 것인가
  - routing metadata를 결과에서 어떻게 읽을 것인가
로 이동했다.
- selective contextual + prefix 조합의 retrieval 자체는 충분히 유망했고,
  최종 품질을 흔들던 큰 축 중 하나가 routing variance였음이 확인됐다.

### 다음 단계

- `intent / format_preference / routing_source`를 benchmark artifact에 노출
- semantic router threshold와 canonical query set을 Golden Set 기준으로 보정
- fallback 로그를 semantic router 자산으로 다시 흡수

## Routing Calibration + Ambiguity Guard (2026-04-24)

참조:

- [query_router_calibration_2026-04-24/summary.md](../../benchmarks/results/query_router_calibration_2026-04-24/summary.md)
- [query_router_calibration_guard_2026-04-24/summary.md](../../benchmarks/results/query_router_calibration_guard_2026-04-24/summary.md)
- [dev_fast_focus_routing_calibrated_2026-04-24/삼성전자-2024/summary.md](../../benchmarks/results/dev_fast_focus_routing_calibrated_2026-04-24/삼성전자-2024/summary.md)
- [dev_fast_focus_routing_guard_2026-04-24/삼성전자-2024/summary.md](../../benchmarks/results/dev_fast_focus_routing_guard_2026-04-24/삼성전자-2024/summary.md)

### 코드 / 설정 변화

- `benchmarks/golden/query_routing_eval_v1.json`
  - held-out routing 검증셋 추가
- `src/ops/calibrate_query_router.py`
  - semantic router score / margin calibration 스크립트 추가
- `benchmarks/golden/query_routing_canonical_v1.json`
  - risk canonical query 2개 추가
- `src/agent/financial_graph.py`
  - 전역 threshold 완화 시도
  - confusion-pair dynamic margin guard 추가

### 핵심 결과

1. 전역 threshold 완화만 적용한 run
   - calibration 기준으로는
     - coverage `0.733 -> 0.833`
     - accuracy `1.000 -> 1.000`
   - 하지만 실제 `dev_fast_focus_routing_calibrated_2026-04-24`에서는
     - `risk_analysis_001`이 `business_overview / mixed / semantic_fast_path`로 오분류
     - selective-prefix 품질이 오히려 악화

2. ambiguity guard + risk canonical 보강 적용 후
   - `dev_fast_focus_routing_guard_2026-04-24`에서
     - `risk_analysis_001`이 다시 `risk / paragraph / semantic_fast_path`로 복구
     - `business_overview_001`은 애매해서 `llm_fallback`으로 전환
   - 즉 전역 threshold보다
     - canonical query 품질
     - confusion pair margin
     - few-shot fallback
     의 조합이 더 안정적이었다

### 해석

- semantic router는 전역 threshold sweep만으로 운영하기 어렵다
- 특히 `business_overview`, `risk`, `numeric_fact`는 class boundary보다 **confusion pair safety**가 더 중요하다
- routing은 다시 안정화됐고, 현재 병목은
  - `numeric_fact` evidence extraction
  - `risk` / `business_overview` generation completeness
  쪽으로 이동했다

## Numeric Extractor Node (2026-04-26)

참조:

- [numeric_extractor_v2_2026-04-26/삼성전자-2024/summary.md](../../benchmarks/results/numeric_extractor_v2_2026-04-26/삼성전자-2024/summary.md)

### 코드 / 설정 변화

- `src/agent/financial_graph.py`
  - `NumericExtraction` Pydantic 스키마 추가 (`period_check`, `consolidation_check`, `unit`, `raw_value`, `final_value`)
  - `_extract_numeric_fact` 노드: `compress → validate` bypass, CoT structured output으로 수치 추출
  - `_route_after_expand`: `intent == "numeric_fact"` → `numeric_extractor` → `cite` 분기

### 핵심 결과

| 실험 | numeric_pass | faithfulness | ingest cost |
|---|---|---|---|
| contextual_all | 1.000 | 0.700 | $0.919 |
| contextual_parent_only | 1.000 | 0.875 | $0.130 |
| plain_prefix | 0.000 | 0.454 | $0.000 |
| selective_v2_prefix | **1.000** | 0.825 | $0.401 |

- `selective_v2_prefix`: routing_guard 대비 FAIL → PASS 회복
- `plain_prefix`: UNCERTAIN 지속 — plain chunk에 수치 추출 실패, 별도 추적 필요

### 해석

- `compress → validate` 파이프라인은 표 기반 숫자 추출에 구조적으로 취약하다
- `numeric_extractor`는 당기/전기, 연결/별도, 단위를 CoT로 먼저 확인하고 raw_value를 추출
- grounding judge는 numeric_extractor가 생성한 synthetic evidence_item 기준으로 판정
- `plain_prefix`의 numeric_fact 실패는 ingest-side 문제로 별도 추적

## Concept Runtime Gap Gate Answer-Composition Closure (2026-06-04)

참조:

- `benchmarks/results/concept_gate_refresh_after_answer_composition_2026-06-04/`

### 코드 / 설정 변화

- `answer_slots`와 `resolved_calculation_trace`를 최종 answer assembly의
  canonical surface로 더 강하게 사용한다.
- lookup sibling recovery는 table metadata에서 값을 찾더라도 primary row label
  match와 ambiguous context-table guard를 통과해야만 값을 승격한다.
- ratio / lookup direct structured operands도 scope가 명시되지 않은 경우
  context-dependent segment/total table row를 사용하지 않는다.
- aggregate answer composition은 source-visible display와 evidence-visible
  impact relation을 우선하고, recomputed trace는 provenance metadata로 보존한다.

### 핵심 결과

- concept runtime gap gate 최신 store-fixed eval-only refresh:
  - `KBF_T2_018`: PASS
  - `POS_T1_057`: PASS
  - `SKH_T3_080`: PASS
  - `SAM_T3_028`: PASS
  - `CEL_T1_013`: PASS
  - `CEL_T3_040`: PASS
  - `KAB_T1_066`: PASS
- 전체 요약: `7 / 7 PASS`
- `POS_T1_057`는 segment/total context table의 `(718,937)` 또는
  `(1,180,096)` 값을 unscoped denominator로 쓰지 않고, notes evidence의
  `1,001,290백만원`을 denominator로 사용해 `3.5269배`를 계산한다.
- 검증:
  - runtime domain-language audit passed (`215` reviewed literals)
  - related answer-composition / lookup-recovery regression suite: `45` tests OK
  - `POS_T1_057` focused eval-only: faithfulness, completeness, context recall,
    retrieval hit, numeric pass rate all `1.000`

### Broader Operation Contract Follow-up

- Pull 후 broader unittest에서 operand precision, value-local unit refinement,
  direct runtime evidence replacement, growth+narrative answer composition
  regressions이 드러났다.
- 수정은 특정 회사/문항 branch 없이 다음 일반 contract로 정리했다:
  - semantic contextual table row가 있으면 numeric proximity 후보보다 우선
  - direct quote/raw-row local unit은 table unit보다 우선하되, 확정 unit은
    weak metadata/claim만으로 바꾸지 않음
  - table-label metadata와 direct runtime evidence가 weak/stale lookup slot을
    교체할 수 있음
  - growth answer는 evidence-visible prior display를 보존하고, narrative
    fallback은 table-fragment noise를 sentence filter로 제거
- 검증:
  - `python -m src.ops.audit_runtime_domain_terms`: passed
  - related answer-composition / lookup-recovery regression suite: `182` tests OK
  - `python -m unittest tests.test_subtask_loop`: `91` tests OK
  - `python -m unittest discover -s tests`: `687` tests OK

### 해석

- 남은 blocker는 benchmark answer를 직접 맞추는 문제가 아니라
  answer-composition contract와 context-dependent table scope contract였다.
- 이번 closure는 특정 회사/문항/계정명 branch가 아니라, evidence schema와
  structured-cell metadata를 이용한 일반 runtime contract로 닫혔다.
- concept-only planner promotion 검토는 이제 "불합격 문항 고치기"가 아니라
  현재 7/7 gate를 baseline으로 잡고 runtime cost, promotion risk, task-ledger
  boundary를 관리하는 단계로 넘어간다.

## Retrieved Driver Evidence Preservation Follow-up (2026-06-07)

참조:

- `benchmarks/results/nav_t2_006_driver_doc_repair_evalonly_2026-06-07/`
  (local store-fixed repair artifact, not committed)

### 배경

- Same-trace duplicate guard 이후 `NAV_T2_006` diagnostic replay에서
  retrieval health는 유지됐지만 final answer가 source-visible growth driver
  하나를 빠뜨리는 현상이 다시 보였다.
- 이 실패는 retrieval miss나 benchmark-specific answer mismatch가 아니라,
  aggregate growth+narrative composition이 retrieved docs에 남아 있는
  policy-backed driver evidence를 evidence item으로 보존하지 못한 문제로
  분류했다.

### 코드 / 테스트 변화

- `src/agent/financial_graph_calculation.py`
  - aggregate evidence assembly 전에 policy-backed narrative driver groups를
    확인한다.
  - 해당 driver surface가 current evidence에는 없지만 `seed_retrieved_docs`
    또는 `retrieved_docs`에 source-visible sentence로 남아 있으면
    `retrieved_driver::*` evidence item으로 승격한다.
  - 회사명, benchmark ID, commerce-specific keyword branch는 추가하지 않고,
    retrieval policy가 제공한 driver groups와 retrieved evidence surface만
    사용한다.
- `tests/test_subtask_loop.py`
  - retrieved docs가 missing growth driver evidence를 보강하는 helper test
    추가.
  - aggregate growth+narrative answer가 promoted retrieved-driver evidence를
    final answer와 selected claim ids에 반영하는 regression test 추가.

### 핵심 결과

- Focused `NAV_T2_006` store-fixed eval-only repair:
  - faithfulness `1.000`
  - completeness `1.000`
  - context recall `1.000`
  - retrieval hit@k `1.000`
  - error rate `0.0%`
- 검증:
  - targeted subtask-loop regression tests: `2` tests OK
  - runtime domain-language audit passed
  - full unittest discovery passed before PR publication

### 해석

- Cross-trace repeated retrieval surfaces remain a runtime/cost topic, not a
  quality blocker by themselves.
- The quality fix is evidence preservation: if the planner/retrieval policy has
  already recovered a relevant driver sentence, aggregate composition must keep
  it visible rather than relying on a later synthesizer to reconstruct it.
- At this point, the remaining non-gate quality cleanup target was
  material-gap replan behavior such as `KBF_T2_043`, not the closed
  `NAV_T2_006` mixed-synthesis gap. This was later closed by the
  `KBF_T2_043` material-gap follow-up described below.

## KBF_T2_043 Material-Gap Follow-Up Close (2026-06-07)

Reference:

- PR #35: `Improve contract-driven narrative numeric handling`

### Result

- Focused store-fixed eval-only replay closed the material-gap/narrative
  numeric blocker.
- Metrics:
  - `numeric_final_judgement = PASS`
  - `faithfulness = 1.0`
  - `numeric_grounding = 1.0`
  - `context_recall = 0.9`
  - `completeness = 0.7`
  - `retrieval_hit_at_k = 0.0`
  - `absolute_error_rate = 0.0`
  - `unit_consistency_pass = 1.0`

### Interpretation

- The original non-gate inventory result remains useful as historical
  screening evidence: `KBF_T2_043` was not a query-budget truncation failure.
- The follow-up fix was contract-driven rather than benchmark-specific:
  material-gap detection, source-visible growth display preservation, and
  policy-required realized context handling were generalized through runtime
  contracts and policy data.
- Remaining work for this case is broader replay and completeness/render
  calibration, not a known material-gap runtime blocker.

## MIX_T1_046 Resolved Dependency Grounding Close (2026-05-28)

참조:

- `benchmarks/results/naver_mix_t1_046_2026-05-28-grounding-fix`

### 코드 / 설정 변화

- `src/ops/evaluator.py`
  - deterministic numeric grounding override가 resolved `task_output:*`
    operand provenance를 인정하도록 일반화
  - 조건은 `dependency_resolved = true`, `source_anchor`, 그리고
    `source_task_id` 또는 `source_slot`이 있는 경우로 제한
  - unresolved `task_output:*` operand는 기존처럼 grounded로 보지 않음
- `tests/test_evaluator_runtime_projection.py`
  - resolved task-output dependency는 override 가능하고, unresolved
    task-output-only operand는 override 불가한 회귀 테스트 추가/유지

### 핵심 결과

- `MIX_T1_046` targeted replay:
  - `numeric_final_judgement = PASS`
  - `numeric_equivalence = 1.0`
  - `numeric_grounding = 1.0`
  - `numeric_retrieval_support = 1.0`
  - `completeness = 1.0`
- 최종 답변은 `종업원급여 1,701,418,940천원 / 영업비용 8,181,823,307천원 = 20.8%`로 계산됨

### 해석

- 남은 문제는 ratio 계산 하드코딩이 아니라 evaluator runtime projection의
  provenance contract였다.
- composed calculation에서 subtask 결과가 `task_output:*`로 전달되더라도,
  원천 subtask provenance가 보존되어 있으면 grounded operand로 인정하는 것이
  맞다.
- 특정 문항/회사/계정명을 직접 처리하는 rule은 추가하지 않았다.

