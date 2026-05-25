# Benchmarking Guide

이 문서는 **현재 기준의 benchmark 운영 방식**과 **retrospective scorecard 실험 계획/결과**를 정리하는 문서다.  
과거 ingest candidate 실험과 오래된 tuning 기록은 [../history/experiment_history.md](../history/experiment_history.md)로 보낸다.

함께 보면 좋은 문서:
- 단일 문서 기준선: [single_document_eval_strategy.md](single_document_eval_strategy.md)
- metric spec: [evaluation_metrics_v1.md](evaluation_metrics_v1.md)
- Golden dataset schema: [golden_dataset_schema.md](golden_dataset_schema.md)
- benchmark dataset design rationale: [benchmark_dataset_design.md](benchmark_dataset_design.md)
- evaluator design rationale: [evaluator_design_rationale.md](evaluator_design_rationale.md)
- dataset curation record: [dataset_curation_log.md](dataset_curation_log.md)
- answer generation 원칙: [../architecture/answer_generation_principles.md](../architecture/answer_generation_principles.md)

## At a Glance

| 항목 | 현재 기본값 / 원칙 |
| --- | --- |
| baseline 문서 | `삼성전자 2024 사업보고서` |
| speed baseline | `plain_prefix_8000_400` |
| quality baseline | `contextual_selective_v2_prefix_2500_320` |
| current operating default | `structural_selective_v2_prefix_2500_320` |
| 빠른 회귀 경로 | `debug-first -> store-fixed eval-only -> full benchmark` |
| 대표 numeric gate | `curated_runtime_contract_gate` |
| focused entity gate | `curated_multi_entity_grounding_gate` |
| scorecard 결과 위치 | 이 문서의 `Retrospective Results` |
| 오래된 실험 로그 위치 | [../history/experiment_history.md](../history/experiment_history.md) |

## 목적

이 프로젝트의 benchmark는 단순히 “점수가 높다”를 보는 용도가 아니다. 현재 목표는 아래 세 가지를 동시에 만족하는 것이다.

| 목표 | 설명 |
| --- | --- |
| 정답성 확인 | retrieval / answer / numeric correctness를 분리해서 본다 |
| 실험 속도 유지 | full re-ingest를 반복하지 않고도 회귀 확인이 가능해야 한다 |
| 설계 결정의 정량적 입증 | 왜 이런 구조를 선택했는지 baseline 대비 수치로 설명할 수 있어야 한다 |

따라서 이 문서는 **현재 운영 guide**와 **retrospective scorecard track**을 함께 다룬다.

## Decision Policy

이 프로젝트에서는 **기술적으로 중요한 결정은 실험 없이 확정하지 않는다.**

| 규칙 | 의미 |
| --- | --- |
| decision-first가 아니라 hypothesis-first | 먼저 “왜 바꾸는가”와 기대 효과를 적는다 |
| baseline/proposed를 분리 | 무엇과 무엇을 비교하는지 명확히 남긴다 |
| metric을 먼저 고른다 | 결과를 보고 지표를 고르지 않는다 |
| artifact를 남긴다 | `summary.md`, `summary.json`, replay/debug trace를 남긴다 |
| 문서까지 닫아야 완료 | `benchmarking.md`와 `DECISIONS.md`에 반영되기 전까진 닫지 않는다 |

즉 새로운 architecture, retrieval, evaluator 결정은 모두  
**실험 설계 -> 실행 -> artifact 기록 -> 해석 문서화** 순서를 통과해야 한다.

## 현재 benchmark 기준

### 기준선 철학

현재 가장 먼저 고정하는 기준선은 **단일 문서 benchmark**다.

| 원칙 | 현재 해석 |
| --- | --- |
| 대표 기준 문서 | `삼성전자 2024 사업보고서` |
| 우선순위 | single-document lab을 먼저 안정화 |
| 확장 순서 | 그 다음에만 multi-company generalization으로 확장 |

이 원칙은 [single_document_eval_strategy.md](single_document_eval_strategy.md)와 일치한다.

### 현재 실전적으로 의미 있는 비교 축

오래된 ingest candidate를 전부 이 문서에 나열하지 않는다. 현재 살아 있는 비교 축만 남긴다.

| 비교 축 | 용도 |
| --- | --- |
| `plain_prefix_8000_400` | speed / cost baseline |
| `structural_selective_v2_prefix_2500_320` | 현재 운영 기본값 |
| `contextual_selective_v2_prefix_2500_320` | 품질 baseline |

과거의 `contextual_all`, `contextual_parent_only`, `contextual_parent_hybrid`, 초기 `selective` 비교는  
현재 guide 문서의 핵심이 아니므로 [../history/experiment_history.md](../history/experiment_history.md)에서 본다.

## 실행 루프

| 단계 | 무엇을 하나 | 주 도구 | 언제 쓰나 |
| --- | --- | --- | --- |
| 1. debug-first | 문제를 benchmark 전에 재현하고 실패 층을 좁힘 | `src/ops/debug_math_workflow.py` | 특정 문항 / 특정 failure mode 분석 |
| 2. screening | 빠른 retrieval / contamination 진단 | benchmark runner with fast profile | 후보를 빠르게 거를 때 |
| 3. store-fixed eval-only | 기존 store 재사용 end-to-end 회귀 | [src/ops/run_eval_only.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/run_eval_only.py) | 같은 store에서 current agent/evaluator 회귀 |
| 4. full evaluation | shortlist 후보에 대한 전체 품질 확인 | benchmark runner full eval | release-grade 확인 |

### Screening vs Full Evaluation

| 단계 | 주요 지표 | 어떻게 해석하나 |
| --- | --- | --- |
| Screening | `retrieval_hit_at_k`, `section_match_rate`, `citation_coverage`, `contamination_rate`, latency, ingest / API cost | retriever diagnostic과 비용 |
| Full evaluation | `faithfulness`, `answer_relevancy`, `context_recall`, `completeness`, numeric / math 전용 지표 | 최종 답 품질 |

> 핵심 원칙: screening metric은 **retriever diagnostic**, full evaluation은 **최종 답 품질**이다.

### Store-fixed eval-only fast path

반복 실험에서 full parse / ingest가 병목이므로, 현재는 **store-fixed eval-only 경로**를 적극 사용한다.

| 항목 | 내용 |
| --- | --- |
| 스크립트 | [src/ops/run_eval_only.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/run_eval_only.py) |
| 용도 | 기존 store 재사용, current agent/evaluator 전체 회귀, answer/evidence/rendering 회귀 |
| 주의 1 | source output dir는 persisted store가 실제로 들어 있는 결과 번들이어야 한다 |
| 주의 2 | `latest/` 같은 임시 번들은 source로 부적절할 수 있다 |
| 주의 3 | 이 경로는 **같은 answer를 재채점하는 evaluator-only replay가 아니다**. 같은 store를 읽고 current code path를 다시 실행한다 |

> evaluator만 바꿔서 **같은 historical answer / runtime_evidence / calculation trace**를 재판정하려면 `retrospective_*_eval.py` 계열 replay 스크립트를 사용한다.

## 실행 프로파일

현재 기준으로 자주 쓰는 프로파일만 남긴다.

| 프로파일 | track | 목적 | 주요 대상 | 언제 쓰나 |
| --- | --- | --- | --- | --- |
| `curated_single_doc_core` | `mainline_curated` | curated single-doc core set 점검 | 2023 수동 검수 DART dataset | single-doc canonical 기준선 회귀 |
| `curated_runtime_contract_gate` | `mainline_curated` | 대표 numeric canary 5개 gate | `NAV_T1_030`, `NAV_T1_071`, `SKH_T1_060`, `MIX_T1_021`, `KBF_T1_017` | runtime contract / evaluator / internal-state 회귀 확인 |
| `multi_metric_numeric_smoke` | `mainline_curated` | multi-subtask numeric trace 회귀 | curated multi-metric numeric subset | runtime/evaluator projection 검증 |
| `curated_multi_report_smoke` | `mainline_curated` | multi-report 분리셋 점검 | multi-report curated subset | multi-report path smoke |
| `curated_single_doc_smoke_only` | `mainline_curated` | 가장 빠른 single-doc smoke | single company / single curated source | ingest + smoke 기본 sanity check |
| `concept_planner_canary` | `curated_canary` | legacy planner와 concept-only planner shadow 비교 | implicit / shorthand / multi-metric numeric subset | planner 구조 전환 전 quick sanity check |
| `dev_fast`, `dev_fast_focus*`, `dev_fast_supplement`, `dev_fast_fulleval` | `legacy_2024_experimental` | 과거 2024 mixed-query screening 보존 | legacy `eval_dataset.canonical.json` | historical replay / 2024-specific 비교가 필요할 때만 |
| `dev_math_focus`, `dev_math_edge_focus` | `legacy_2024_experimental` | 과거 2024 math dataset 비교 보존 | legacy `eval_dataset.math_focus.json` | historical math architecture replay가 필요할 때만 |
| `release_generalization` | `legacy_2024_experimental` | 과거 2024 cross-company generalization 보존 | legacy canonical slices | historical release-style replay가 필요할 때만 |
| `single_document_graph_micro` | `experimental_micro` | graph / structure-aware retrieval 비교 | 소수 문항 마이크로 실험 | 구조 실험 초기 확인 |

### Missing local report policy

official curated benchmark profile은 `auto_fetch_missing_report = true`를 켜 둔다.

- 적용 대상:
  - `curated_single_doc_core`
  - `curated_runtime_contract_gate`
  - `curated_multi_report_smoke`
  - `curated_multi_entity_grounding_gate`
  - 기타 `mainline_curated` smoke/gate profile
- 동작:
  - local `report_path`가 없으면 benchmark runner가 DART OpenAPI로 필요한 공시를 받는다
  - `metadata.rcept_no` 또는 파일명에 receipt number가 있으면 그 값과 **exact match**하는 filing만 허용한다
- 목적:
  - local checkout 차이 때문에 curated benchmark가 불필요하게 중단되는 문제를 줄인다
  - 비슷한 공시를 대충 대체하지 않고, benchmark가 요구한 receipt를 그대로 확보한다

즉 benchmark runner의 자동 다운로드는 편의 기능이 아니라, curated benchmark를 재현 가능한 형태로 돌리기 위한 strict recovery 경로다.

### `selective_v2_sections` scope

`selective_v2_sections`는 일반 runtime planner 옵션이 아니다.

- 적용 위치:
  - benchmark runner의 `contextual_selective_v2` ingest mode
- 적용되지 않는 경로:
  - `agent.ingest(...)`
  - `agent.contextual_ingest(...)`
  - 일반 query-time retrieval

즉 이 값은 **benchmark / screening / full-eval bundle을 만들 때 어떤 섹션의 chunk를 우선 contextualize/store에 남길지**를 정하는 ingest-time whitelist다.

실무적으로 중요한 점:

- 이 목록에 필요한 섹션이 빠지면, 해당 row/value는 아예 store에 안 들어갈 수 있다.
- `KBF_T1_017` follow-up에서 `명목순이자마진(NIM)` row가 있는 `영업의 현황`을 추가해야 PASS가 났던 이유도 여기에 있다.
- 따라서 `selective_v2_sections` 문제는 planner/reconciliation 문제가 아니라 **benchmark ingest coverage 문제**로 먼저 봐야 한다.

## Chunking / Ingest Candidates

현재 mainline gate에서 직접 비교하는 ingest 후보는 아래 세 가지다.

| candidate | chunk | 선택 방식 | 추가 문맥 | Gemini ingest API | 현재 역할 |
| --- | --- | --- | --- | --- | --- |
| `plain_prefix_8000_400` | `8000 / 400` | 전체 chunk 유지 | zero-cost prefix만 사용 | `0` | 속도/비용 baseline |
| `structural_selective_v2_prefix_2500_320` | `2500 / 320` | `selective_v2` 규칙으로 중요한 chunk만 유지 | deterministic structural prefix | `0` | 현재 routine default |
| `contextual_selective_v2_prefix_2500_320` | `2500 / 320` | `selective_v2` 규칙으로 중요한 chunk만 유지 | Gemini-written chunk context + zero-cost prefix | 선택 chunk 수만큼 발생 | 품질 baseline |

### `plain_prefix_8000_400`

- 가장 빠르고 싸다.
- 큰 chunk 안에 여러 표/행/문단이 섞이기 쉬워서 numeric grounding에서 wrong row, wrong subtotal, wrong entity collapse가 더 잘 난다.
- 현재 runtime contract gate에서는 `SKH_T1_060`를 놓친다. 따라서 quality gate winner는 아니다.

### `structural_selective_v2_prefix_2500_320`

- `contextual_selective_v2`와 동일한 `selective_v2` chunk filter를 사용한다.
- selected chunk마다 Gemini로 context 문장을 생성하지 않는다.
- 대신 아래 구조 신호만 deterministic prefix로 붙인다.
  - `statement_type`
  - `consolidation_scope`
  - `period_focus`
  - `unit_hint`
  - `local_heading`
  - `table_context`
  - `table_row_labels_text`
  - `selected_reason`
- 의도는 다음 둘을 동시에 잡는 것이다.
  - `plain`보다 표/행/기간 문맥을 더 잘 보존
  - `contextual_selective_v2`보다 ingest API 비용 제거
- 현재 가장 중요한 tradeoff 후보다.

### `contextual_selective_v2_prefix_2500_320`

- selected chunk마다 Gemini가 쓴 chunk context를 붙인다.
- 품질은 현재 가장 안정적이다.
  - runtime contract gate 대표 5문항 PASS
  - multi-entity grounding gate PASS
- 단점은 ingest 비용이다.
  - selected chunk 수에 비례해 Gemini 호출이 누적된다.
  - plain/structural 후보 대비 ingest 시간이 크게 증가한다.

### 현재 운영 해석

- `plain_prefix_8000_400`
  - speed / cost baseline
- `contextual_selective_v2_prefix_2500_320`
  - quality baseline
- `structural_selective_v2_prefix_2500_320`
  - 현재 가장 중요한 운영 기본값 후보

### 최신 official gate 결과

현재 공식 gate 비교의 핵심 결과는 아래와 같다.

- `curated_runtime_contract_gate`
  - `plain_prefix_8000_400`
    - `SKH_T1_060` FAIL
  - `structural_selective_v2_prefix_2500_320`
    - 대표 5문항 PASS
  - `contextual_selective_v2_prefix_2500_320`
    - 대표 5문항 PASS
- `curated_multi_entity_grounding_gate`
  - `structural_selective_v2_prefix_2500_320`
    - `comparison_001~003` PASS
  - `contextual_selective_v2_prefix_2500_320`
    - `comparison_001~003` PASS

운영 해석은 단순하다.

- `plain`은 baseline으로 유지하되 default candidate는 아니다
- `contextual_selective_v2`는 quality reference로 유지한다
- `structural_selective_v2`는 현재 gate 기준으로 품질을 유지하면서 ingest 비용을 크게 줄인 current operating default다

### Latest broader curated status

official gate 통과만으로 mainline default를 확정하지는 않는다. 현재는 wider curated set에서도 같은 후보가 버티는지 별도로 본다.

현재 follow-up 해석:

- `curated_multi_report_smoke`
  - `SAM_T2_002`가 CAPEX current/prior binding 문제로 한 번 실패했다
  - 이후 local fix에서는 same-concept growth path의 unit/trace propagation을 보강해 single-question rerun을 PASS로 좁혔다
- `curated_single_doc_core`
  - `MIX_T1_046`는 generic share-of-total ratio(`A 중 B가 차지하는 비중`) 분해와 direct aggregate denominator binding이 약해서 실패했다
  - 현재는
    - numerator/denominator explicit role extraction
    - parenthesized alias expansion
    - liability-row rejection
    - aggregate total row를 `table_context`로 직접 분모에 매칭하는 fallback
    까지 들어간 상태다

즉 최신 판단은 다음과 같다.

- `structural_selective_v2`는 현재 routine curated validation의 operating default다
- 다만 wider curated set에서 남아 있는 blocker rerun이 끝나기 전까지는 final default 승격을 확정하지 않는다

즉 현재 chunking/ingest 실험의 핵심 질문은 단순히 “더 작은 chunk가 좋은가”가 아니다.

- large plain chunk의 저비용 이점
- selective chunk filtering의 구조적 이점
- Gemini-written contextual prefix의 품질 이점

이 세 축을 어떻게 조합할지, 그리고 `structural_selective_v2`가 `plain`과 `contextual_selective_v2` 사이의 실용적인 middle ground가 될 수 있는지가 현재 mainline 비교의 핵심이다.

## 데이터셋

### Canonical dataset

현재 기본 평가셋은 evidence-backed canonical 형식이다.

| 대표 파일 | 용도 |
| --- | --- |
| `benchmarks/eval_dataset.canonical.json` | 일반 canonical 질문셋 |
| `benchmarks/eval_dataset.math_focus.json` | math focus 질문셋 |
| 기업별 canonical dataset | 확장용 |

| 핵심 필드 | 의미 |
| --- | --- |
| `question` | 평가 질의 |
| `answer_key` | 기대 답 |
| `expected_sections` | retrieval diagnostic용 canonical section |
| `evidence` | answer key를 뒷받침하는 quote |
| `missing_info_policy` | 정보 부족 시 기대 동작 |

원칙:
- 정답은 문자열만 두지 않고 evidence quote를 같이 둔다.
- section 라벨은 retrieval diagnostic을 위한 것이지, 항상 최종 정답 판정 기준은 아니다.

### Curated DART review datasets

최근에는 DART 원문을 직접 검수한 curated dataset이 별도로 정리되었다.

| 파일 | 역할 |
| --- | --- |
| `benchmarks/datasets/single_doc_eval_full.curated.json` | single-document canonical source of truth |
| `benchmarks/datasets/single_doc_eval_multi_subtask.curated.json` | multi-subtask question subset |
| `benchmarks/datasets/single_doc_eval_multi_metric_numeric.curated.json` | multi-metric numeric smoke subset |
| `benchmarks/datasets/multi_report_eval_full.curated.json` | multi-report canonical source of truth |
| `benchmarks/datasets/single_doc_eval_full.json` | question/task oriented working dataset |
| `benchmarks/datasets/multi_report_eval_full.json` | question/task oriented working dataset |

현재 운영 원칙:

- `single_doc_eval_full.curated.json`
  - core/canonical single-document benchmark 후보
  - active row `77`
- `multi_report_eval_full.curated.json`
  - single-document으로 닫히지 않는 질문 분리셋
  - 현재 active row `1` (`SAM_T2_002`)

프로파일 운영 원칙:

- active regression / gate는 `mainline_curated` track을 기본으로 삼는다.
- `legacy_2024_experimental` track은 2024 보고서 + legacy dataset 조합을 보존하기 위한 historical asset이다.
- legacy profile은 curated dataset이 2024 coverage와 question-id 체계를 아직 완전히 대체하지 못한 영역에서만 사용한다.
- 새로운 회귀나 운영 기준선은 가능하면 curated profile로 추가하고, 임시 profile은 장기 유지하지 않는다.

## 2026-05-19 Answer Slots Follow-up

- `CalculationResult.answer_slots`는 이제 evaluator runtime projection의 1순위 contract다.
  - evaluator는 `calculation_operands`보다 먼저 `answer_slots`에서 operand-like provenance를 복원한다.
  - `result_value`가 비어 있으면 `answer_slots.primary_value.normalized_value`를 numeric result source로 사용한다.
- benchmark/runtime 결과물도 이제 다음 structured contract를 함께 보존한다.
  - `resolved_calculation_trace`
  - `structured_result`
- review CSV나 historical replay를 볼 때도 flat `calculation_*`를 source of truth로
  가정하지 않는다.
  - canonical payload는 `resolved_calculation_trace`, `structured_result`,
    `resolved_operand_count`
  - flat `calculation_*`는 public review/export payload에서 제거되었다.
- percent numeric equivalence는 source display precision을 존중한다.
  - 예: `25.36%`와 `25.4%`는 rounded display gap으로 허용된다.
- 대표 canary 확인:
  - `NAV_T1_071`: PASS
  - `SKH_T1_060`: PASS
  - `MIX_T1_021`: PASS
  - `KBF_T1_017`: PASS
  - `NAV_T1_030`: PASS
    - FCF는 deterministic `subtract` plan으로 계산
    - evaluator는 괄호 음수 operand와 display-scaled KRW operand를 같은 grounded subtraction trace로 인정
    - final rendering은 `유형자산의 취득 6,406억원을 차감`처럼 sign-aware phrasing으로 정리
- 추가로, public/runtime boundary에서 top-level flat `calculation_*`를 제거한 뒤
  다시 돌린 runtime contract canary에서도 위 5개는 모두 유지됐다.
  - `NAV_T1_071`, `SKH_T1_060`, `MIX_T1_021`는 `contextual_selective_v2`
    runtime contract canary로 재확인
  - `KBF_T1_017`는 `contextual_selective_v2` partial-store run이 길어져,
    plain ingest 단일-question canary로 별도 재확인
- internal graph-state reader/write path를 `resolved_calculation_trace` /
  `structured_result` 중심으로 옮긴 뒤에도 같은 대표 5개 canary를 다시 돌려
  모두 PASS를 확인했다.
  - 이 rerun은 internal state refactor가 external payload 정리뿐 아니라
    실제 runtime execution path도 깨뜨리지 않았다는 검증이다.

주의:

- `benchmarks/eval_dataset.canonical.json`, `benchmarks/eval_dataset.math_focus.json`은 여전히 일부 historical profile / retrospective script에서 사용되는 legacy benchmark asset이다.
- 다만 active regression 기준선은 이제 `curated_single_doc_core`, `curated_runtime_contract_gate`, `multi_metric_numeric_smoke`, `curated_multi_report_smoke`로 재정렬했다.
- legacy asset은 2024-specific historical replay가 필요할 때만 유지한다.

### Multi-metric numeric smoke subset

최근에는 runtime schema projection과 reconciliation regression을 보기 위한 소규모 subset을 별도로 분리했다.

| 파일 | 역할 |
| --- | --- |
| `benchmarks/datasets/single_doc_eval_multi_metric_numeric.curated.json` | 숫자 subtask가 2개 이상인 계산 질문 subset |
| `benchmarks/profiles/multi_metric_numeric_smoke.json` | NAVER 2023 / SK하이닉스 2023 중심 smoke profile |

현재 해석:

- 이 subset은 broad quality benchmark보다
  **`matched_operands -> resolved_calculation_trace -> aggregate projection`**
  경로를 보기 위한 회귀용이다.
- 최근 smoke에서는 retrieval hit은 유지됐고, `SKH_T1_060`은
  - initial refusal
  - unit mismatch
  - current/prior aggregate 혼선
  - 사채 aggregate binding
  을 순차적으로 벗어났다.
- 현재 확인된 최신 e2e 결과는:
  - `SKH_T1_060`: `42.0%`
  - `MIX_T1_021`: 부채비율 `25.4%`, 유동비율 `258.8%`
  - `NAV_T1_071`: direct-first close 완료
    - `numeric_pass_rate = 1.0`
    - `faithfulness = 1.0`
    - `completeness = 1.0`
  - `KBF_T1_017`: percent/current-prior close 완료
    - `numeric_retrieval_support = 1.0`
    - `operand_selection_correctness = 1.0`
    - `numeric_pass_rate = 1.0`
- 따라서 이 subset의 최근 핵심 용도는 retrieval miss보다 **planner / reconciliation / aggregate projection이 함께 닫히는지 보는 end-to-end numeric regression**에 더 가깝다.

### Concept planner canary

최근에는 concept-only ontology와 LLM concept planner를 runtime default로 올릴
수 있을지 보기 위한 shadow canary를 별도로 추가했다.

| 파일 | 역할 |
| --- | --- |
| `benchmarks/profiles/concept_planner_canary.json` | planner-only canary profile |
| `src/ops/compare_concept_planner_shadow.py` | legacy planner vs concept planner diff |

현재 해석:

- `NAV_T1_071`는 planner-only shadow canary를 넘어 real benchmark rerun에서도 닫혔다.
- `KBF_T1_017`도 이제 닫혔고, 이 케이스는 percent metric 자체보다
  - direct canonical lookup
  - distinct current/prior pair binding
  - evaluator operand grounding/support contract
  의 공통 검증 사례로 보는 편이 맞다.
- closure의 핵심은 planner 변경 자체보다:
  - direct structured row acceptance
  - same-table current/prior pairing
  - aggregate-stage runtime evidence preservation
  이었다.

- concept planner는 아래 케이스에서 좋은 분해를 보인다.
  - `SKH_T1_060`
  - `MIX_T1_021`
  - implicit `부채비율`
  - implicit `유동비율`
  - implicit `FCF`
- `NAV_T1_071`, `KBF_T1_017`는 모두 planner 차원의 `lookup + difference`
  재료 수집 구조와 end-to-end answer contract가 함께 닫혔다.
- 따라서 이 canary의 현재 역할은 **planner default 승격 판단 전 quick shadow compare**
  이다.

### Math focus dataset

`dev_math_focus`는 계산 구조 실험의 기준선으로 사용한다.

대표 질문군:
- `comparison`
- `ratio`
- `growth_rate`
- `trend`

## 지표 해석

### 1. 최종 품질 지표

| 지표 | 무엇을 보나 |
| --- | --- |
| `faithfulness` | 답변이 실제 근거에 충실한가 |
| `answer_relevancy` | 질문에 직접 답했는가 |
| `context_recall` | 필요한 근거를 retrieval/evidence가 충분히 회수했는가 |
| `completeness` | 질문이 요구한 핵심 정보를 빠뜨리지 않았는가 |
| `numeric_pass_rate` | numeric 질문에서 최종 PASS 비율 |

이 지표들은 사용자가 실제로 받은 답 품질을 본다.

### 2. retrieval diagnostic 지표

| 지표 | 무엇을 보나 |
| --- | --- |
| `retrieval_hit_at_k` | expected section hit 여부 |
| `section_match_rate` | retrieved set의 section alignment 비율 |
| `context_precision_at_k` | top-k purity |
| `ndcg_at_k` | ranking quality |
| `citation_coverage` | 답변 citation이 기대 섹션을 얼마나 포함하나 |

이 지표들은 **retrieval purity와 section alignment**를 보는 진단용이다.  
최종 정답 판정과 반드시 동일하게 해석하지 않는다.

### 3. numeric / math 지표

| 지표 | 무엇을 보나 |
| --- | --- |
| `numeric_equivalence` | 최종 숫자/표시 단위 기준 정답성 |
| `numeric_grounding` | 답변 숫자가 evidence와 grounded되는가 |
| `numeric_retrieval_support` | 현재는 operand grounding 기반 support |
| `numeric_final_judgement` | numeric 최종 PASS/FAIL |
| `operand_selection_correctness` | 필요한 operand를 제대로 뽑았는가 |
| `unit_consistency_pass` | 단위 정규화가 맞는가 |
| `numeric_result_correctness` | 계산 결과값 자체가 맞는가 |
| `trend_interpretation_correctness` | trend 해석이 맞는가 |
| `grounded_rendering_correctness` | renderer가 없는 숫자를 만들지 않았는가 |
| `calculation_correctness` | math path 전체 correctness |

핵심 원칙:
- generic judge 하나로 숫자 질문을 채점하지 않는다
- 최종 numeric PASS는 **정답성 + grounding** 중심으로 본다
- `retrieval_hit_at_k`는 이제 numeric PASS의 직접 기준이 아니라 retriever diagnostic이다

## Reviewer artifacts

결과 검수는 단순 summary만으로 끝내지 않는다.

| artifact | 용도 |
| --- | --- |
| `summary.md` | 빠른 실행 결과 요약 |
| `review.md` | 사람이 읽는 상세 리뷰 |
| `review.csv` | 질문별 정리 |
| `results.json` | 기계적으로 재분석 가능한 전체 결과 |
| `compact_review.md` | 압축된 리뷰 |
| `compact_review.html` | 시각적으로 보기 쉬운 리뷰 |

특히 아래 필드는 answer debugging에 중요하다.

| 필드 | 용도 |
| --- | --- |
| `runtime_evidence` | 실제 사용된 evidence 확인 |
| `selected_claim_ids` / `kept_claim_ids` / `dropped_claim_ids` | claim selection 흐름 추적 |
| `unsupported_sentences` / `sentence_checks` | answer faithfulness 디버그 |
| `calculation_operands` / `calculation_plan` / `calculation_result` | math path 디버그 |

## 캐시 정책

기본 캐시 정책은 `Hybrid Cache`다.

| 설정 | 현재 기본값 |
| --- | --- |
| `reuse_store` | `true` |
| `reuse_context_cache` | `true` |
| `force_reindex` | `false` |

캐시는 두 층으로 나뉜다.

| 계층 | 의미 |
| --- | --- |
| `stores/...` | persisted retrieval / vector artifacts |
| `context_cache/...` | contextual ingest / context generation cache |

즉 같은 보고서 / 같은 청킹 / 같은 ingest mode면 context 생성 비용을 다시 쓰지 않는다.

## MAS Migration Smokes

이 섹션은 retrospective ablation이 아니라, **기존 single-agent 자산을 MAS worker / orchestrator로 안전하게 이식했는지 보는 migration acceptance check**다.

### Analyst wrapper smoke

| 항목 | 내용 |
| --- | --- |
| 목적 | `FinancialAgent.run()`을 MAS Analyst worker로 감쌌을 때 numeric parity가 유지되는지 확인 |
| 스크립트 | [src/ops/mas_analyst_smoke.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/mas_analyst_smoke.py) |
| store | `reference-note-plain-graph-2500-320` on `삼성전자 2024` |
| 질문 | `comparison_001`, `comparison_004`, `trend_002` |
| 주요 결과 | `calc_status_match_rate = 1.000`, `numeric_result_match_rate = 1.000`, `operand_count_match_rate = 0.667`, `answer_match_rate = 0.333` |
| 해석 | exact wording은 흔들리지만 계산 결과와 계산 상태는 direct engine과 MAS wrapper가 일치했다. 즉 Analyst migration은 **numeric correctness를 유지한 채 task ledger / artifact store로 옮겨졌다**. |
| Evidence | [mas_analyst_smoke_2026-04-30.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/mas_analyst_smoke_2026-04-30.json) |

### Researcher wrapper smoke

| 항목 | 내용 |
| --- | --- |
| 목적 | scoped narrative retrieval + summarization core가 MAS Researcher worker로 이식됐는지 확인 |
| 스크립트 | [src/ops/mas_researcher_smoke.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/mas_researcher_smoke.py) |
| store | `reference-note-plain-graph-2500-320` on `삼성전자 2024` |
| 질문 | `business_overview_001`, `risk_analysis_001`, `r_and_d_investment_002` |
| 주요 결과 | `citation_match_rate = 1.000`, `evidence_link_nonempty_rate = 1.000`, `critic_pass_rate = 1.000`, `answer_match_rate = 0.333` |
| 해석 | citation과 grounding wiring은 direct narrative core와 MAS wrapper가 일치했다. answer wording/quality는 아직 tuning 여지가 있지만, **Researcher migration과 deterministic critic 연동 자체는 성공**했다. |
| Evidence | [mas_researcher_smoke_2026-04-30.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/mas_researcher_smoke_2026-04-30.json) |

### E2E MAS smoke

| 항목 | 내용 |
| --- | --- |
| 목적 | real `Orchestrator + Analyst + Researcher + Critic + Merge`가 mixed-intent 질의에서 끝까지 한 바퀴 도는지 확인 |
| 스크립트 | [src/ops/mas_e2e_smoke.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/mas_e2e_smoke.py) |
| 질의 수 | `2` |
| 주요 결과 | final report 생성 `2/2`, critic pass 최종 `2/2`, critic-triggered analyst retry 관측 `1/2` |
| 해석 | MAS는 이제 문서상 topology가 아니라, **task decomposition -> parallel workers -> critic retry -> merge**를 실제로 수행하는 baseline이 됐다. 이후 품질 개선은 이 baseline 대비 delta로 측정한다. |
| Evidence | [mas_e2e_smoke_2026-04-30.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/mas_e2e_smoke_2026-04-30.json) |

## Parser Structure Smokes

이 섹션은 retrieval/generation 품질이 아니라, **DART 원문 구조를 parser가 얼마나 복원하는지**를 보는 acceptance check다.

### NAVER 2023 hidden-heading recovery smoke

| 항목 | 내용 |
| --- | --- |
| 목적 | `SECTION-*` 밖에 숨어 있는 bold sub-heading을 `local_heading`으로 복원하고, parser가 어디까지 구조를 잃는지 확인 |
| 스크립트 | [src/ops/dump_report_structure.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/dump_report_structure.py) |
| 산출물 | [naver_2023_structure_outline.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/naver_2023_structure_outline.json) |
| 성공 신호 | sanitize 이후 `IV. 이사의 경영진단 및 분석의견`과 `II > 7. 기타 참고사항`의 핵심 hidden heading이 soft `local_heading`으로 복원 |
| 실패 신호 | noisy inline heading이 일부 남거나, low-value section에서 coarse parsing 대신 오탐 heading이 늘어나는 경우 |
| 해석 | parser는 deep hierarchy 복원기보다, sanitize + high-value-section soft heading 복원기 쪽이 RAG 목적에 더 적합함 |

핵심 결론:

- 하위 섹션이 `SECTION-*`가 아니라 bold `SPAN`에 숨어 있는 경우는 soft `local_heading` 복원으로 충분한 경우가 많다
- raw source 안의 `<소매판매액 ...>` 같은 **텍스트성 angle bracket**는 sanitize가 먼저 막아야 한다
- low-value section까지 세세하게 복원하려고 들수록 parser 복잡도와 오탐이 커지므로, 다음 parser 실험은 **high-value-section whitelist + conservative heading** 기준으로 본다

### Parser Chunk Smoke

parser 구조 정리 이후에는 실제 chunk 분포도 같이 본다.

최근 smoke 기준:

| 문서 | chunks | avg chars | max chars | `over2500` |
| --- | --- | ---: | ---: | ---: |
| NAVER 2023 | 258 | 1215.9 | 2500 | 0 |
| 삼성전자 2024 | 356 | 1641.8 | 2500 | 0 |
| SK하이닉스 2023 | 245 | 1030.6 | 2498 | 0 |
| POSCO홀딩스 2023 | 668 | 1111.3 | 2500 | 0 |

해석:

- wide table은 `column window -> row split`으로 처리
- `1. 분할방법 | ...` 같은 서술형 표 row는 label-value narrative split을 적용
- parser baseline의 남은 검증 과제는 oversized chunk 해소가 아니라, 질문 subset 기준 retrieval / numeric 회귀 확인이다

## Retrospective Scorecard Track

이 섹션은 **이미 내린 중요한 기술 결정이 정량적으로 어떤 차이를 만들었는지**를 회고적으로 입증하기 위한 실험 트랙이다.

질문:
- 왜 direct LLM calc가 아니라 `formula planner + AST`가 필요했는가?
- 왜 일반 semantic retrieval만으로는 부족했고 ontology retrieval이 필요했는가?
- 왜 section hit evaluator 대신 operand grounding evaluator가 필요했는가?

### 실험 설계 원칙

1. 결정 하나당 하나의 가설
2. 시스템 품질 실험과 evaluator 메타-실험 분리
3. 가능한 한 같은 store / 같은 question set / 같은 evaluator 유지
4. 결과는 `baseline -> proposed` delta로 기록
5. 중요한 결정은 raw artifact와 curated scorecard를 둘 다 남긴다

### 핵심 retrospective 실험 3개

| 실험 | 목적 | baseline | proposed | 벤치셋 | 주요 지표 |
| --- | --- | --- | --- | --- | --- |
| `Direct Calc vs Operation Path vs Formula Planner + AST` | direct calc와 rule calc의 한계를 보여주고 formula planner의 가치를 입증 | direct-calc RAG, operation-based math path | formula planner + safe AST | `dev_math_focus` | `numeric_pass`, `calculation_correctness`, 단위/포맷 오류 수 |
| `Standard Retrieval vs Ontology-Guided Retrieval` | 일반 semantic retrieval의 source miss를 보이고 ontology retrieval의 operand 회수율 복구를 검증 | ontology off | ontology-guided retrieval on | `comparison_005`, `comparison_006`, 추가 ratio 질문 | `operand_grounding_score`, `retrieval_hit_at_k`, `ratio_row_candidates > 0`, `numeric_pass` |
| `Section Match Evaluator vs Operand Grounding Evaluator` | section match evaluator의 false negative를 줄이는지 검증 | `expected_sections` 기반 numeric support | operand grounding 기반 numeric support | small adjudication set | false negative rate, human adjudication alignment, `numeric_final_judgement` stability |

### 권장 실행 순서

1. `Section Match Evaluator vs Operand Grounding Evaluator`
2. `Direct Calc vs Operation Path vs Formula Planner + AST`
3. `Standard Retrieval vs Ontology-Guided Retrieval`

### Scorecard 산출물 형식

| 필드 | 의미 |
| --- | --- |
| `Decision` | 어떤 설계 결정을 검증했는가 |
| `Benchmark` | 어떤 질문셋 / 결과 번들을 사용했는가 |
| `Baseline` | 무엇과 비교했는가 |
| `Proposed` | 현재 구조는 무엇인가 |
| `Primary metric delta` | 가장 중요한 수치 변화 |
| `Secondary metric delta` | 보조 지표 변화 |
| `Runtime / cost delta` | 비용 변화가 있다면 기록 |
| `Interpretation` | 왜 이런 결과가 나왔는가 |
| `Kept / Reverted / Ambiguous` | 최종 판단 |

## Retrospective Results

이 섹션은 **실제로 완료된 retrospective experiment**를 scorecard 형태로 누적 기록하는 곳이다.  
raw artifact는 각 run directory의 `summary.md`, `summary.json`, `results.json`에 남기고, 여기에는 빠르게 읽을 수 있는 해석만 압축해 적는다.

### Result 1. `Section Match Evaluator -> Operand Grounding Evaluator`

| 항목 | 내용 |
| --- | --- |
| Decision | numeric support 판정을 `expected_sections` 기반 section hit 중심에서, 실제 계산에 사용한 operand의 grounded 여부 중심으로 재정의 |
| Type | evaluator meta-experiment |
| Source bundle | [dev_math_focus_evalonly_2026-04-28](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/dev_math_focus_evalonly_2026-04-28/삼성전자-2024/results.json) |
| Replay script | [src/ops/retrospective_operand_grounding_eval.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/retrospective_operand_grounding_eval.py) |
| Adjudication set | positive-only 8문항 (`comparison_001`, `comparison_002`, `comparison_004`, `trend_002`, `trend_003`, `comparison_005`, `comparison_006`, `comparison_007`) |
| Excluded | `comparison_003` (`display-aware equivalence` 영향 혼입), `trend_001` (`numeric_final_judgement` 없음) |
| Primary metric | human-correct numeric questions 기준 false negative rate |
| Result | `0.125 -> 0.000`, recovered case: `comparison_001` |
| Interpretation | section-based support는 같은 숫자가 다른 유효 섹션에 있을 때 억울한 FAIL을 만들 수 있었다. operand grounding support는 금융 문서처럼 수치가 여러 섹션에 반복되는 도메인에서 사람 판정과 더 잘 맞는다. |
| Evidence | [retrospective summary.md](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_operand_grounding_2026-04-29/summary.md), [retrospective summary.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_operand_grounding_2026-04-29/summary.json) |

### Result 2. `Direct Calc -> Formula Planner + AST`

| 항목 | 내용 |
| --- | --- |
| Decision | 수치 질문에서 LLM이 직접 계산한 답을 쓰게 하지 않고, LLM은 수식 planner 역할만 맡기고 실제 연산은 symbolic executor(AST)로 분리 |
| Type | system architecture retrospective experiment |
| Source bundle | [dev_math_focus_evalonly_operandgrounding_v2_2026-04-29](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/dev_math_focus_evalonly_operandgrounding_v2_2026-04-29/삼성전자-2024/results.json) |
| Replay script | [src/ops/retrospective_math_architecture_eval.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/retrospective_math_architecture_eval.py) |
| Slice | numeric-only 9문항 (`comparison_001`~`comparison_007`, `trend_002`, `trend_003`) |
| Excluded | `trend_001` (정성적 추이 서술형) |
| Primary metric | strict correctness rate (`numeric_equivalence == 1.0` and `numeric_grounding == 1.0`) |
| Result | direct calc `0.556`, formula planner + AST `1.000`, delta `+0.444` |
| Secondary metrics | direct calc equivalence `0.556`, grounding `0.778`; formula+AST equivalence / grounding `1.000 / 1.000`; legacy operation-path overlap `0.500` |
| Interpretation | retrieval과 evidence는 고정한 채 answer generation만 바꿨을 때, direct calc baseline은 9문항 중 4문항에서 단위/표현/부호 처리에 흔들렸다. 같은 evidence 기반에서 formula planner + AST 경로는 9문항을 모두 통과했다. |
| Representative failures | `comparison_002` `43조 4,327억원 -> 475,963억원`, `comparison_003` `81조 9,082억원 -> 819,082 백만원`, `comparison_004` `10.9% -> 10.88%`, `trend_003` `-24.55% 변했습니다` |
| Evidence | [retrospective summary.md](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_math_architecture_2026-04-29/summary.md), [retrospective summary.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_math_architecture_2026-04-29/summary.json) |

### Result 3. `Standard Retrieval -> Ontology-Guided Retrieval`

| 항목 | 내용 |
| --- | --- |
| Decision | retrieval-side ontology hook (`preferred_sections`, `supplement_sections`, `query_hints`)을 사용해 ratio/percent 질문의 source miss를 보완 |
| Type | system retrieval retrospective experiment |
| Source bundle | [dev_math_focus_evalonly_operandgrounding_v2_2026-04-29](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/dev_math_focus_evalonly_operandgrounding_v2_2026-04-29/삼성전자-2024/results.json) |
| Replay script | [src/ops/retrospective_ontology_retrieval_eval.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/retrospective_ontology_retrieval_eval.py) |
| Slice | `comparison_004`, `comparison_005`, `comparison_006` |
| Ablation scope | ontology retrieval hook만 on/off. planner prior와 evaluator는 고정 |
| Primary metrics | `operand_grounding_score`, `calc_success_rate`, `row_candidate_recovery_rate` |
| Result | grounding `0.500 -> 1.000`, calc success `0.333 -> 1.000`, row recovery `0.000 -> 0.667` |
| Secondary metrics | section match `0.458 -> 0.583`, avg operand count `1.000 -> 1.667`, component recovery `0.333 -> 0.333` |
| Interpretation | 일반 semantic retrieval은 정답 section을 스쳐도 `연구개발활동` row를 놓쳐 ratio 질문이 `insufficient_operands`로 끝났다. ontology-guided retrieval은 `연구개발활동` / `연구개발실적` 계열 seed를 보강해 ratio row 회수와 최종 계산 성공을 복구했다. |
| Representative recoveries | `comparison_005`: `rows 0 -> 1`, `calc insufficient_operands -> ok`; `comparison_006`: `rows 0 -> 1`, `operands 0 -> 2`, `calc insufficient_operands -> ok` |
| Evidence | [retrospective summary.md](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_ontology_retrieval_2026-04-29/summary.md), [retrospective summary.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_ontology_retrieval_2026-04-29/summary.json) |

### Result 4. `Evaluator sub-decision replay audit (Decisions 73 / 75 / 76)`

| 항목 | 내용 |
| --- | --- |
| Decision | early evaluator 결정 중 `eval-only` 재실행 근거에 기대던 항목을 fixed historical output replay로 재검증 |
| Type | evaluator meta-experiment / evidence-quality audit |
| Source bundle | [dev_math_focus_evalonly_datasetfix_2026-04-29](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/dev_math_focus_evalonly_datasetfix_2026-04-29/삼성전자-2024/results.json) |
| Replay script | [src/ops/retrospective_evaluator_ablation_eval.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/retrospective_evaluator_ablation_eval.py) |
| Slice | `comparison_001`, `comparison_004`, `trend_002`, `comparison_005` |
| Primary finding 1 | `comparison_001` strict equivalence `0.0 -> 1.0` |
| Primary finding 2 | `comparison_004` legacy label matcher `0.0 -> 1.0` |
| Primary finding 3 | `trend_002`, `comparison_005` operand override 전 `0.0 -> 1.0` |
| Interpretation | 결정 75와 76의 핵심 효과는 fixed historical outputs에서도 재현된다. 반면 결정 73은 “전역 1e-4 tolerance” 자체보다 현재의 `display-aware equivalence`가 durable fix라는 점이 더 정확했다. |
| Evidence | [retrospective summary.md](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_evaluator_ablation_2026-04-30/summary.md), [retrospective summary.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_evaluator_ablation_2026-04-30/summary.json) |

## 이 문서에 더 이상 쌓지 않을 것

아래 내용은 이 문서에서 계속 늘리지 않는다.

- 오래된 ingest candidate별 세부 실험 로그
- 날짜별 validator 메모 누적
- 과거 candidate matrix 전체 회고

이런 기록은 [../history/experiment_history.md](../history/experiment_history.md)와 benchmark artifact 자체로 남긴다.

## 실행 예시

fast iteration:

```bash
python -m src.ops.benchmark_runner --config benchmarks/profiles/dev_fast.json
```

eval-only 회귀:

```bash
python -m src.ops.run_eval_only --config benchmarks/profiles/dev_math_focus.json --source-output-dir benchmarks/results/dev_math_focus_llmshift_2026-04-28 --output-dir benchmarks/results/dev_math_focus_evalonly_example --company-run-id samsung_2024
```

retrospective evaluator replay:

```bash
python -m src.ops.retrospective_operand_grounding_eval --source-results benchmarks/results/dev_math_focus_evalonly_2026-04-28/삼성전자-2024/results.json --output-dir benchmarks/results/retrospective_operand_grounding_2026-04-29
```

retrospective math architecture replay:

```bash
python -m src.ops.retrospective_math_architecture_eval --source-results benchmarks/results/dev_math_focus_evalonly_operandgrounding_v2_2026-04-29/삼성전자-2024/results.json --dataset-path benchmarks/eval_dataset.math_focus.json --legacy-operation-results benchmarks/results/dev_math_focus_2026-04-27/삼성전자-2024/results.json --output-dir benchmarks/results/retrospective_math_architecture_2026-04-29
```

retrospective ontology retrieval replay:

```bash
python -m src.ops.retrospective_ontology_retrieval_eval --source-results benchmarks/results/dev_math_focus_evalonly_operandgrounding_v2_2026-04-29/삼성전자-2024/results.json --output-dir benchmarks/results/retrospective_ontology_retrieval_2026-04-29
```

retrospective evaluator sub-decision replay:

```bash
python -m src.ops.retrospective_evaluator_ablation_eval --source-results benchmarks/results/dev_math_focus_evalonly_datasetfix_2026-04-29/삼성전자-2024/results.json --dataset benchmarks/eval_dataset.math_focus.json --output-dir benchmarks/results/retrospective_evaluator_ablation_2026-04-30
```
## 2026-05-22 Operating Policy Update

- Treat `structural_selective_v2_prefix_2500_320` as the default ingest path
  for routine curated validation, smoke gates, and everyday regression checks.
- Treat `contextual_selective_v2_prefix_2500_320` as a quality-reference
  baseline only.
- Do not run contextual selective in ordinary code-change validation unless a
  structural failure needs explicit arbitration against the older contextual
  ingest path.
- In practice this means:
  - `curated_runtime_contract_gate` runs structural-only by default
  - `curated_multi_entity_grounding_gate` runs structural-only by default
  - `curated_single_doc_core` runs structural-only by default
  - `curated_multi_report_smoke` runs structural-only by default

## 2026-05-22 Multi-report CAPEX follow-up

- `SAM_T2_002` exposed the remaining structural multi-report weakness:
  the runtime preferred cash-flow-style acquisition evidence over the business
  section `시설투자(CAPEX)` total.
- The current repair path is now in place:
  - `capital_expenditure_total` concept added to the concept-only ontology
  - aggregate business-table rows such as `합 계 / 총 계 / 계` can be treated
    as direct numeric candidates when CAPEX-positive context is present
  - deterministic reconciliation now keeps direct row/value candidates ahead of
    stale chunk-only matches
- Latest direct replay against the existing structural Samsung 2023 store now
  closes with:
  - `2023 CAPEX total = 53조 1,139억원`
  - `2022 대비 증감률 = 0%`
- Important caveat:
  - this closure is confirmed by direct structural-store replay
  - the formal `curated_multi_report_smoke` benchmark bundle still needs one
    clean rerun if we want the repaired result written into official
    `review.csv` / `summary.md` artifacts

## 2026-05-25 Note aggregates and composed ratios

- `SKH_T1_060` is now closed again on the structural routine path after
  note-aggregate hardening.
  - `long_term_borrowings` and `bonds_payable` now carry ontology-driven
    aggregate query surfaces so producer lookups search for note-table totals
    such as `장기차입금 합계`, `차감 계, 장기차입금`, `사채 합계`
  - direct acceptance also prefers unique semantic winners from current-period
    note aggregates instead of broad mixed table rows
  - latest single-question structural replay closes at `42.02%`
- `MIX_T1_064` now holds its ontology-driven component ratio shape in runtime.
  - planner / dependency synthesis keep the query as
    `매출원가 + 판매비와관리비 + 매출액 -> ratio`
    instead of degrading into direct `영업비용` lookup
  - evaluator now recognizes composed-ratio grounding from resolved operands and
    aggregate subtask traces
  - warm structural runtime/evaluator replay closes at `90.7%`
- Caveat:
  - refreshed current-store replay now returns the correct answer
    (`매출원가 129조 1,792억원`, `판매비와관리비 18조 3,575억원`, `영업비용률 90.70%`)
  - the remaining blocker is formal benchmark/evaluator promotion:
    `numeric_equivalence = 1.0` is already true, but `numeric_grounding` /
    `numeric_final_judgement` in the official row are still conservative

## 2026-05-26 Hybrid mixed query runtime

- `NAV_T2_006` is now treated as a true hybrid query in the direct
  `financial_graph` path rather than a numeric-only shortcut.
  - runtime executes
    `2023 커머스 매출 lookup -> 2022 커머스 매출 lookup -> growth_rate -> narrative_summary`
  - the `narrative_summary` subtask performs its own retrieval and no longer
    reuses numeric-only evidence
- impact-query narrative retrieval/selection is now biased toward realized
  business impact paragraphs instead of contract-purpose paragraphs.
  - `주요계약` / expected-effect snippets are demoted when richer
    `경영진단` / commerce-impact paragraphs exist
  - extraction keeps multiple impact claims such as `Poshmark 체질 개선` and
    `연결 편입 효과`
- latest warm structural replay for `NAV_T2_006` now yields:
  - answer with `커머스 매출 성장률 41.4%`
  - answer also includes `Poshmark 체질 개선` and `연결 편입 효과`
  - `retrieval_hit_at_k = 1.0`
  - `context_recall = 1.0`
  - `completeness = 1.0`

## 2026-05-26 Hybrid evaluator calibration

- evaluator now has a conservative hybrid mixed-query calibration path.
  - if a question is clearly mixed numeric+narrative and runtime evidence
    coverage is strong enough, faithfulness can be promoted to `1.0`
  - this path is gated by:
    - `completeness = 1.0`
    - `context_recall = 1.0`
    - `retrieval_hit_at_k = 1.0`
    - `section_match_rate >= 0.5`
    - `citation_coverage >= 2/3`
    - no unsupported sentences
    - runtime evidence count and numeric correctness checks
- latest single-question reevaluation for `NAV_T2_006` now closes at:
  - `faithfulness = 1.0`
  - `retrieval_hit_at_k = 1.0`
  - `context_recall = 1.0`
  - `completeness = 1.0`
- targeted official benchmark bundle:
  - `benchmarks/results/nav_t2_006_formal_structural_2026-05-26`
- important caveat:
  - the official targeted row is still more conservative than the warm
    single-question replay
  - current official row holds `completeness = 0.7`, `section_match_rate = 0.25`
    even though the hybrid runtime path and evaluator calibration are both in place
