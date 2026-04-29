# Benchmarking Guide

이 문서는 **현재 기준의 benchmark 운영 방식**과 **retrospective scorecard 실험 계획/결과**를 정리하는 문서다.  
과거 ingest candidate 실험과 오래된 tuning 기록은 [../history/experiment_history.md](../history/experiment_history.md)로 보낸다.

함께 보면 좋은 문서:
- 단일 문서 기준선: [single_document_eval_strategy.md](single_document_eval_strategy.md)
- metric spec: [evaluation_metrics_v1.md](evaluation_metrics_v1.md)
- Golden dataset schema: [golden_dataset_schema.md](golden_dataset_schema.md)
- answer generation 원칙: [../architecture/answer_generation_principles.md](../architecture/answer_generation_principles.md)

## 목차
- [Benchmarking Guide](#benchmarking-guide)
  - [목차](#목차)
  - [목적](#목적)
  - [현재 benchmark 기준](#현재-benchmark-기준)
    - [기준선 철학](#기준선-철학)
    - [현재 운영 baseline](#현재-운영-baseline)
    - [현재 실전적으로 의미 있는 비교 축](#현재-실전적으로-의미-있는-비교-축)
  - [실행 루프](#실행-루프)
    - [1. debug-first](#1-debug-first)
    - [2. screening -\> full evaluation](#2-screening---full-evaluation)
      - [1차 Screening](#1차-screening)
      - [2차 Full Evaluation](#2차-full-evaluation)
    - [3. eval-only fast path](#3-eval-only-fast-path)
  - [실행 프로파일](#실행-프로파일)
    - [`dev_fast`](#dev_fast)
    - [`single_document_graph_micro`](#single_document_graph_micro)
    - [`release_generalization`](#release_generalization)
    - [`dev_math_focus`](#dev_math_focus)
    - [`dev_math_edge_focus`](#dev_math_edge_focus)
  - [데이터셋](#데이터셋)
    - [Canonical dataset](#canonical-dataset)
    - [Math focus dataset](#math-focus-dataset)
  - [지표 해석](#지표-해석)
    - [1. 최종 품질 지표](#1-최종-품질-지표)
    - [2. retrieval diagnostic 지표](#2-retrieval-diagnostic-지표)
    - [3. numeric / math 지표](#3-numeric--math-지표)
  - [Reviewer artifacts](#reviewer-artifacts)
  - [캐시 정책](#캐시-정책)
  - [Retrospective Scorecard Track](#retrospective-scorecard-track)
    - [실험 설계 원칙](#실험-설계-원칙)
    - [핵심 retrospective 실험 3개](#핵심-retrospective-실험-3개)
      - [실험 1. `Direct Calc vs Operation Path vs Formula Planner + AST`](#실험-1-direct-calc-vs-operation-path-vs-formula-planner--ast)
      - [실험 2. `Standard Retrieval vs Ontology-Guided Retrieval`](#실험-2-standard-retrieval-vs-ontology-guided-retrieval)
      - [실험 3. `Section Match Evaluator vs Operand Grounding Evaluator`](#실험-3-section-match-evaluator-vs-operand-grounding-evaluator)
    - [권장 실행 순서](#권장-실행-순서)
    - [Scorecard 산출물 형식](#scorecard-산출물-형식)
  - [Retrospective Results](#retrospective-results)
    - [Result 1. `Section Match Evaluator -> Operand Grounding Evaluator`](#result-1-section-match-evaluator---operand-grounding-evaluator)
    - [Result 2. `Direct Calc -> Formula Planner + AST`](#result-2-direct-calc---formula-planner--ast)
  - [이 문서에 더 이상 쌓지 않을 것](#이-문서에-더-이상-쌓지-않을-것)
  - [실행 예시](#실행-예시)

## 목적

이 프로젝트의 benchmark는 단순히 “점수가 높다”를 보는 용도가 아니다.  
현재 목표는 아래 세 가지를 동시에 만족하는 것이다.

1. **정답성 확인**
   - retrieval / answer / numeric correctness를 분리해서 본다.
2. **실험 속도 유지**
   - full re-ingest를 반복하지 않고도 회귀 확인이 가능해야 한다.
3. **설계 결정의 정량적 입증**
   - 왜 이런 구조를 선택했는지 baseline 대비 수치로 설명할 수 있어야 한다.

따라서 이 문서는 다음 두 층을 함께 다룬다.
- 현재 운영 benchmark guide
- retrospective scorecard track

## 현재 benchmark 기준

### 기준선 철학

현재 가장 먼저 고정하는 기준선은 **단일 문서 benchmark**다.

- 대표 기준 문서: `삼성전자 2024 사업보고서`
- single-document lab을 먼저 안정화
- 그 다음에만 multi-company generalization으로 확장

이 원칙은 [single_document_eval_strategy.md](single_document_eval_strategy.md)와 일치한다.

### 현재 운영 baseline

현재 대표 baseline은 다음과 같다.

- `contextual_all_2500_320`

이 baseline은 “가장 싸다”가 아니라, **현재까지 가장 안정적인 품질 기준점**으로 사용한다.

### 현재 실전적으로 의미 있는 비교 축

오래된 ingest candidate를 전부 이 문서에 나열하지 않는다.  
현재 살아 있는 비교 축만 남긴다.

1. `contextual_all_2500_320`
   - 품질 baseline
2. `contextual_selective_v2_prefix_2500_320`
   - 저비용 retrieval 후보
3. `plain + graph expansion`
   - structure-aware retrieval / graph 계열 구조 실험
4. `plain + reference_note expansion`
   - `REFERENCE_NOTE` 확장 효과 검증용

과거의 `contextual_parent_only`, `contextual_parent_hybrid`, 초기 `selective` 비교는  
현재 guide 문서의 핵심이 아니므로 [../history/experiment_history.md](../history/experiment_history.md)에서 본다.

## 실행 루프

### 1. debug-first

복잡한 문제는 benchmark부터 다시 돌리지 않는다.

우선순위:
1. 재현 스크립트
2. 작은 focus benchmark
3. eval-only 회귀
4. 마지막에만 full benchmark

대표 도구:
- `src/ops/debug_math_workflow.py`
- `src/ops/run_eval_only.py`

### 2. screening -> full evaluation

benchmark는 여전히 2단계 구조로 본다.

#### 1차 Screening

빠르고 싼 retrieval 진단용 지표를 본다.

- `retrieval_hit_at_k`
- `section_match_rate`
- `citation_coverage`
- `contamination_rate`
- smoke query latency
- ingest / API cost 계열

#### 2차 Full Evaluation

screening을 통과한 후보에 대해서만 깊은 평가를 본다.

- `faithfulness`
- `answer_relevancy`
- `context_recall`
- `completeness`
- numeric / math 전용 지표

핵심 원칙:
- screening metric은 **retriever diagnostic**
- full evaluation은 **최종 답 품질**

### 3. eval-only fast path

반복 실험에서 full parse / ingest가 병목이므로, 현재는 **eval-only 경로**를 적극 사용한다.

- 스크립트: [src/ops/run_eval_only.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/run_eval_only.py)
- 용도:
  - 기존 store 재사용
  - evaluator 변경 회귀
  - answer/evidence/rendering 회귀

주의:
- source output dir는 persisted store가 실제로 들어 있는 결과 번들이어야 한다.
- `latest/` 같은 임시 번들은 source로 부적절할 수 있다.

## 실행 프로파일

현재 기준으로 자주 쓰는 프로파일만 남긴다.

### `dev_fast`

- 빠른 screening용
- 단일 회사
- 새 후보를 빠르게 거르는 기본 루프

### `single_document_graph_micro`

- graph / structure-aware retrieval 비교용
- 소수 문항 마이크로 실험

### `release_generalization`

- 다기업 일반화 확인용
- shortlist 후보에만 사용

### `dev_math_focus`

- math / numeric reasoning 기준선
- `comparison`, `ratio`, `growth`, `trend` 질문군 중심

### `dev_math_edge_focus`

- 엣지 케이스 빠른 회귀용
- `%p`, ratio row miss, operand shortfall 같은 문제 확인

## 데이터셋

### Canonical dataset

현재 기본 평가셋은 evidence-backed canonical 형식이다.

대표 파일:
- `benchmarks/eval_dataset.canonical.json`
- `benchmarks/eval_dataset.math_focus.json`
- 기업별 canonical dataset

핵심 필드:
- `question`
- `answer_key`
- `expected_sections`
- `evidence`
- `missing_info_policy`

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

- `faithfulness`
- `answer_relevancy`
- `context_recall`
- `completeness`
- `numeric_pass_rate`

이 지표들은 사용자가 실제로 받은 답 품질을 본다.

### 2. retrieval diagnostic 지표

- `retrieval_hit_at_k`
- `section_match_rate`
- `context_precision_at_k`
- `ndcg_at_k`
- `citation_coverage`

이 지표들은 **retrieval purity와 section alignment**를 보는 진단용이다.  
최종 정답 판정과 반드시 동일하게 해석하지 않는다.

### 3. numeric / math 지표

- `numeric_equivalence`
- `numeric_grounding`
- `numeric_retrieval_support`
- `numeric_final_judgement`
- `operand_selection_correctness`
- `unit_consistency_pass`
- `numeric_result_correctness`
- `trend_interpretation_correctness`
- `grounded_rendering_correctness`
- `calculation_correctness`

핵심 원칙:
- generic judge 하나로 숫자 질문을 채점하지 않는다
- 최종 numeric PASS는 **정답성 + grounding** 중심으로 본다
- `retrieval_hit_at_k`는 이제 numeric PASS의 직접 기준이 아니라 retriever diagnostic이다

## Reviewer artifacts

결과 검수는 단순 summary만으로 끝내지 않는다.

주요 artifact:
- `summary.md`
- `review.md`
- `review.csv`
- `results.json`
- `compact_review.md`
- `compact_review.html`

특히 아래 필드는 answer debugging에 중요하다.

- `runtime_evidence`
- `selected_claim_ids`
- `kept_claim_ids`
- `dropped_claim_ids`
- `unsupported_sentences`
- `sentence_checks`
- `calculation_operands`
- `calculation_plan`
- `calculation_result`

## 캐시 정책

기본 캐시 정책은 `Hybrid Cache`다.

- `reuse_store = true`
- `reuse_context_cache = true`
- `force_reindex = false`

캐시는 두 층으로 나뉜다.
- `stores/...`
- `context_cache/...`

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

#### 실험 1. `Direct Calc vs Operation Path vs Formula Planner + AST`

- 목적:
  - direct calculation과 rule-based operation path의 한계를 보여주고,
  - `formula planner + safe AST`의 가치를 수치로 입증
- 비교군:
  - `Baseline A`: direct-calc RAG
  - `Baseline B`: operation-based math path
  - `Proposed`: formula planner + safe AST
- 벤치셋:
  - `dev_math_focus`
- 주요 지표:
  - `numeric_pass`
  - `calculation_correctness`
  - 단위/포맷 오류 수

#### 실험 2. `Standard Retrieval vs Ontology-Guided Retrieval`

- 목적:
  - 일반 semantic retrieval의 source miss를 보이고,
  - ontology-guided retrieval이 operand 회수율을 복구하는지 확인
- 비교군:
  - `Baseline`: ontology off
  - `Proposed`: ontology-guided retrieval on
- 벤치셋:
  - `comparison_005`
  - `comparison_006`
  - 가능하면 `operating_margin` 1~2문항
- 주요 지표:
  - `operand_grounding_score`
  - `retrieval_hit_at_k`
  - `ratio_row_candidates > 0`
  - `numeric_pass`

#### 실험 3. `Section Match Evaluator vs Operand Grounding Evaluator`

- 목적:
  - section match 중심 evaluator가 false negative를 만들 수 있음을 보이고,
  - operand grounding evaluator가 사람 판정과 더 잘 맞는지 검증
- 성격:
  - evaluator meta-experiment
- 비교군:
  - `Baseline`: `expected_sections` 기반 numeric support
  - `Proposed`: operand grounding 기반 numeric support
- 벤치셋:
  - `comparison_001` 같은 억울한 FAIL 포함 small adjudication set
- 주요 지표:
  - false negative rate
  - human adjudication alignment
  - `numeric_final_judgement` stability

### 권장 실행 순서

1. `Section Match Evaluator vs Operand Grounding Evaluator`
2. `Direct Calc vs Operation Path vs Formula Planner + AST`
3. `Standard Retrieval vs Ontology-Guided Retrieval`

### Scorecard 산출물 형식

각 실험은 아래 표 한 줄로 남긴다.

- `Decision`
- `Benchmark`
- `Baseline`
- `Proposed`
- `Primary metric delta`
- `Secondary metric delta`
- `Runtime / cost delta`
- `Interpretation`
- `Kept / Reverted / Ambiguous`

## Retrospective Results

이 섹션은 **실제로 완료된 retrospective experiment**를 scorecard 형태로 누적 기록하는 곳이다.  
raw artifact는 각 run directory의 `summary.md`, `summary.json`, `results.json`에 남기고, 여기에는 빠르게 읽을 수 있는 해석만 압축해 적는다.

### Result 1. `Section Match Evaluator -> Operand Grounding Evaluator`

- `Decision`
  - numeric support 판정을 `expected_sections` 기반 section hit 중심에서, 실제 계산에 사용한 operand의 grounded 여부 중심으로 재정의
- `Type`
  - evaluator meta-experiment
- `Source bundle`
  - [dev_math_focus_evalonly_2026-04-28](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/dev_math_focus_evalonly_2026-04-28/삼성전자-2024/results.json)
- `Replay script`
  - [src/ops/retrospective_operand_grounding_eval.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/retrospective_operand_grounding_eval.py)
- `Adjudication set`
  - positive-only 8문항
  - 포함:
    - `comparison_001`, `comparison_002`, `comparison_004`, `trend_002`, `trend_003`, `comparison_005`, `comparison_006`, `comparison_007`
  - 제외:
    - `comparison_003` (`display-aware equivalence` 영향 혼입)
    - `trend_001` (`numeric_final_judgement` 없음)
- `Primary metric`
  - false negative rate on human-correct numeric questions
- `Result`
  - old false negative rate: `0.125`
  - new false negative rate: `0.000`
  - recovered case: `comparison_001`
- `Interpretation`
  - section-based support는 같은 숫자가 다른 유효 섹션에 있을 때 억울한 FAIL을 만들 수 있었다.
  - operand grounding support는 “실제로 읽은 텍스트에 계산 operand가 있었는가”를 보므로, 금융 문서처럼 수치가 여러 섹션에 반복되는 도메인에서 사람 판정과 더 잘 맞는다.
- `Evidence`
  - [retrospective summary.md](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_operand_grounding_2026-04-29/summary.md)
  - [retrospective summary.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_operand_grounding_2026-04-29/summary.json)

### Result 2. `Direct Calc -> Formula Planner + AST`

- `Decision`
  - 수치 질문에서 LLM이 직접 계산한 답을 쓰게 하지 않고, LLM은 답안/수식 planner 역할만 맡기고 실제 연산은 symbolic executor(AST)로 분리
- `Type`
  - system architecture retrospective experiment
- `Source bundle`
  - [dev_math_focus_evalonly_operandgrounding_v2_2026-04-29](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/dev_math_focus_evalonly_operandgrounding_v2_2026-04-29/삼성전자-2024/results.json)
- `Replay script`
  - [src/ops/retrospective_math_architecture_eval.py](/C:/Users/admin/Desktop/dart-rag-agent/src/ops/retrospective_math_architecture_eval.py)
- `Slice`
  - numeric-only 9문항
  - 포함:
    - `comparison_001`, `comparison_002`, `comparison_003`, `comparison_004`, `comparison_005`, `comparison_006`, `comparison_007`, `trend_002`, `trend_003`
  - 제외:
    - `trend_001` (정성적 추이 서술형)
- `Primary metric`
  - strict correctness rate
  - 정의: `numeric_equivalence == 1.0` and `numeric_grounding == 1.0`
- `Result`
  - direct calc: `0.556`
  - formula planner + AST: `1.000`
  - delta: `+0.444`
  - 부가 지표:
    - direct calc equivalence rate: `0.556`
    - direct calc grounding rate: `0.778`
    - formula planner + AST equivalence / grounding: `1.000 / 1.000`
  - legacy operation-path overlap (2문항):
    - strict correctness: `0.500`
- `Interpretation`
  - retrieval과 evidence는 고정한 채 answer generation만 바꿨을 때, direct calc baseline은 9문항 중 4문항에서 단위/표현/부호 처리에 흔들렸다.
  - 대표 실패:
    - `comparison_002`: `43조 4,327억원` 대신 `475,963억원`
    - `comparison_003`: `81조 9,082억원` 대신 `819,082 백만원`
    - `comparison_004`: `10.9%` 기대값에 `10.88%`
    - `trend_003`: 감소 질문을 `-24.55% 변했습니다`로 답변
  - 같은 evidence를 기반으로 formula planner + AST 경로는 9문항을 모두 통과했다.
- `Evidence`
  - [retrospective summary.md](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_math_architecture_2026-04-29/summary.md)
  - [retrospective summary.json](/C:/Users/admin/Desktop/dart-rag-agent/benchmarks/results/retrospective_math_architecture_2026-04-29/summary.json)

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
