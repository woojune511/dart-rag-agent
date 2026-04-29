# Benchmarking Guide

이 문서는 **현재 기준의 benchmark 운영 방식**과 **retrospective scorecard 실험 계획/결과**를 정리하는 문서다.  
과거 ingest candidate 실험과 오래된 tuning 기록은 [../history/experiment_history.md](../history/experiment_history.md)로 보낸다.

함께 보면 좋은 문서:
- 단일 문서 기준선: [single_document_eval_strategy.md](single_document_eval_strategy.md)
- metric spec: [evaluation_metrics_v1.md](evaluation_metrics_v1.md)
- Golden dataset schema: [golden_dataset_schema.md](golden_dataset_schema.md)
- answer generation 원칙: [../architecture/answer_generation_principles.md](../architecture/answer_generation_principles.md)

## At a Glance

| 항목 | 현재 기본값 / 원칙 |
| --- | --- |
| baseline 문서 | `삼성전자 2024 사업보고서` |
| 운영 baseline | `contextual_all_2500_320` |
| 빠른 회귀 경로 | `debug-first -> eval-only -> full benchmark` |
| math 기준선 | `dev_math_focus` |
| broader sanity check | `dev_fast_focus_selective_serial` |
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

## 현재 benchmark 기준

### 기준선 철학

현재 가장 먼저 고정하는 기준선은 **단일 문서 benchmark**다.

| 원칙 | 현재 해석 |
| --- | --- |
| 대표 기준 문서 | `삼성전자 2024 사업보고서` |
| 우선순위 | single-document lab을 먼저 안정화 |
| 확장 순서 | 그 다음에만 multi-company generalization으로 확장 |

이 원칙은 [single_document_eval_strategy.md](single_document_eval_strategy.md)와 일치한다.

### 현재 운영 baseline

현재 대표 baseline은 다음과 같다.

| baseline | 역할 |
| --- | --- |
| `contextual_all_2500_320` | 가장 저렴한 후보가 아니라, 현재까지 가장 안정적인 품질 기준점 |

### 현재 실전적으로 의미 있는 비교 축

오래된 ingest candidate를 전부 이 문서에 나열하지 않는다. 현재 살아 있는 비교 축만 남긴다.

| 비교 축 | 용도 |
| --- | --- |
| `contextual_all_2500_320` | 품질 baseline |
| `contextual_selective_v2_prefix_2500_320` | 저비용 retrieval 후보 |
| `plain + graph expansion` | structure-aware retrieval / graph 구조 실험 |
| `plain + reference_note expansion` | `REFERENCE_NOTE` 확장 효과 검증 |

과거의 `contextual_parent_only`, `contextual_parent_hybrid`, 초기 `selective` 비교는  
현재 guide 문서의 핵심이 아니므로 [../history/experiment_history.md](../history/experiment_history.md)에서 본다.

## 실행 루프

| 단계 | 무엇을 하나 | 주 도구 | 언제 쓰나 |
| --- | --- | --- | --- |
| 1. debug-first | 문제를 benchmark 전에 재현하고 실패 층을 좁힘 | `src/ops/debug_math_workflow.py` | 특정 문항 / 특정 failure mode 분석 |
| 2. screening | 빠른 retrieval / contamination 진단 | benchmark runner with fast profile | 후보를 빠르게 거를 때 |
| 3. eval-only | 기존 store 재사용 회귀 | [src/ops/run_eval_only.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/run_eval_only.py) | evaluator / answer / rendering 회귀 |
| 4. full evaluation | shortlist 후보에 대한 전체 품질 확인 | benchmark runner full eval | release-grade 확인 |

### Screening vs Full Evaluation

| 단계 | 주요 지표 | 어떻게 해석하나 |
| --- | --- | --- |
| Screening | `retrieval_hit_at_k`, `section_match_rate`, `citation_coverage`, `contamination_rate`, latency, ingest / API cost | retriever diagnostic과 비용 |
| Full evaluation | `faithfulness`, `answer_relevancy`, `context_recall`, `completeness`, numeric / math 전용 지표 | 최종 답 품질 |

> 핵심 원칙: screening metric은 **retriever diagnostic**, full evaluation은 **최종 답 품질**이다.

### Eval-only fast path

반복 실험에서 full parse / ingest가 병목이므로, 현재는 **eval-only 경로**를 적극 사용한다.

| 항목 | 내용 |
| --- | --- |
| 스크립트 | [src/ops/run_eval_only.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/run_eval_only.py) |
| 용도 | 기존 store 재사용, evaluator 변경 회귀, answer/evidence/rendering 회귀 |
| 주의 1 | source output dir는 persisted store가 실제로 들어 있는 결과 번들이어야 한다 |
| 주의 2 | `latest/` 같은 임시 번들은 source로 부적절할 수 있다 |

## 실행 프로파일

현재 기준으로 자주 쓰는 프로파일만 남긴다.

| 프로파일 | 목적 | 주요 대상 | 언제 쓰나 |
| --- | --- | --- | --- |
| `dev_fast` | 빠른 screening | 단일 회사, mixed query | 새 후보를 빠르게 거를 때 |
| `single_document_graph_micro` | graph / structure-aware retrieval 비교 | 소수 문항 마이크로 실험 | 구조 실험 초기 확인 |
| `release_generalization` | 다기업 일반화 확인 | shortlist 후보 | release-grade 확인 |
| `dev_math_focus` | math / numeric reasoning 기준선 | `comparison`, `ratio`, `growth`, `trend` | 계산 구조 비교 |
| `dev_math_edge_focus` | 엣지 케이스 회귀 | `%p`, ratio row miss, operand shortfall | math regression debug |

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
