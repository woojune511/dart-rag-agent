# Benchmark Dataset Design

이 문서는 이 프로젝트에서 **왜 benchmark를 직접 만들었는지**, 그리고  
**질문 taxonomy, curation 기준, 운영 데이터셋 구분을 어떻게 잡았는지**를 설명한다.

기존 문서와의 역할 분리는 다음과 같다.

- [golden_dataset_schema.md](golden_dataset_schema.md)
  - 필드 스키마 정의
- [evaluation_metrics_v1.md](evaluation_metrics_v1.md)
  - metric registry 정의
- 이 문서
  - 왜 이런 dataset과 benchmark 운영 방식을 택했는지에 대한 설계 rationale

## Why a custom benchmark was necessary

일반적인 QA benchmark나 generic RAG 평가만으로는 이 프로젝트의 핵심 문제를 설명하기 어려웠다.

이 프로젝트가 다루는 실패는 단순한 “검색 실패”가 아니라 아래에 가깝다.

- wrong row selection
- wrong subtotal / aggregate row acceptance
- wrong period binding (`current` / `prior`)
- wrong entity/segment binding (`DX`, `DS`, `SDC`, `Harman`)
- retrieval은 맞지만 numeric rendering / evaluator가 동치성을 놓치는 경우

즉 필요한 benchmark는 단순 정답 문자열 비교가 아니라:

- retrieval support
- evidence grounding
- numeric equivalence
- calculation correctness
- refusal policy

를 같이 다룰 수 있어야 했다.

## Design goals

이 benchmark 체계의 목표는 네 가지다.

| 목표 | 의미 |
| --- | --- |
| Reproducibility | 같은 profile과 store 조건에서 회귀를 반복 가능해야 한다 |
| Diagnosis | retrieval, grounding, calculation, rendering을 분리해서 실패를 설명할 수 있어야 한다 |
| Domain fit | DART 공시의 표/주석/사업부문 구조를 반영해야 한다 |
| Decision support | architecture와 ingest 후보를 비교해 설계 결정을 뒷받침할 수 있어야 한다 |

## Dataset tracks

현재 이 프로젝트의 dataset은 크게 두 트랙으로 나뉜다.

### 1. Curated mainline datasets

이 트랙은 현재 active regression과 official gate의 기준선이다.

| 파일 | 역할 |
| --- | --- |
| `benchmarks/datasets/single_doc_eval_full.curated.json` | single-document canonical source of truth |
| `benchmarks/datasets/single_doc_eval_multi_subtask.curated.json` | multi-subtask subset |
| `benchmarks/datasets/single_doc_eval_multi_metric_numeric.curated.json` | multi-metric numeric smoke subset |
| `benchmarks/datasets/multi_report_eval_full.curated.json` | multi-report canonical source of truth |

이 트랙의 특징:

- 사람이 DART 원문을 직접 보고 answer/evidence를 검수한다
- gate에 들어가는 질문은 소수지만 의미가 명확하다
- architecture regression과 candidate 비교에 바로 사용할 수 있다

### 2. Legacy historical datasets

이 트랙은 과거 2024 실험을 재현하거나 비교할 때 유지한다.

| 파일 | 역할 |
| --- | --- |
| `benchmarks/eval_dataset.canonical.json` | legacy canonical benchmark |
| `benchmarks/eval_dataset.math_focus.json` | legacy math / comparison benchmark |

이 트랙의 특징:

- historical replay 자산이다
- 현재 mainline gate의 source of truth는 아니다
- 다만 2024-specific 비교나 과거 실험 해석에는 여전히 유용하다

## Question taxonomy

이 프로젝트는 질문을 자연어 표면 형태가 아니라 **실패 모드와 reasoning 구조** 기준으로 본다.

대표 taxonomy는 아래와 같다.

| 유형 | 의미 |
| --- | --- |
| `lookup` | 문서에서 특정 수치/사실을 직접 찾아야 하는 질문 |
| `difference` | current/prior 또는 entity/entity 차이를 계산해야 하는 질문 |
| `ratio` | numerator/denominator 구성과 단위 처리가 필요한 질문 |
| `growth_rate` | 기간 변화율을 계산해야 하는 질문 |
| `sum` | 여러 operand를 합산해야 하는 질문 |
| `multi-entity grounding` | 같은 concept라도 entity/segment가 다르면 distinct operand로 잡아야 하는 질문 |
| `multi-metric aggregate` | 답에 둘 이상의 metric 결과가 함께 들어가야 하는 질문 |

이 taxonomy를 택한 이유는 planner, grounding, evaluator를 모두 같은 축으로 설명할 수 있기 때문이다.

## Curation principles

질문과 answer key를 만드는 기준은 아래와 같다.

### 1. Evidence-backed answers only

정답은 문자열만 적지 않는다.

- canonical answer
- 근거 quote
- 기대 section
- numeric constraint

를 같이 둔다.

이렇게 해야 retrieval과 generation을 같은 dataset으로 평가할 수 있다.

### 2. Question selection by failure mode

질문은 단순히 “자주 나오는 질문”이 아니라 **시스템이 실제로 실패했던 문제 유형**을 대표하도록 고른다.

예:

- `NAV_T1_071`
  - current/prior value preservation
- `SKH_T1_060`
  - ratio grounding and wrong subtotal rejection
- `KBF_T1_017`
  - percent metric + period binding
- `comparison_002`
  - repeated concept under different business entities

### 3. Minimal but representative gates

gate는 크게 만들지 않는다.  
대신 architecture regression을 잘 드러내는 **작고 강한 질문 세트**를 만든다.

현재 official gate는:

- runtime contract gate: 5문항
- multi-entity grounding gate: 3문항

이다.

### 4. Missing-information policy is explicit

문서에 답이 없는 질문은 evaluator가 오답으로만 보면 안 된다.  
따라서 refusal / missing-info 케이스는 answer key 차원에서 명시한다.

## Annotation workflow

권장 workflow는 다음과 같다.

1. source report 선택
2. 질문 초안 작성
3. 원문에서 canonical evidence quote 확인
4. expected section / entity / period / unit 명시
5. numeric constraint와 reasoning type 지정
6. evaluator와 replay 경로에서 sanity check
7. verified 상태로 승격

이 프로젝트의 의도는 대규모 weakly labeled benchmark를 만드는 것이 아니라,  
**작더라도 strong supervision을 가진 gate set을 운영**하는 것이다.

## Why curated and legacy assets coexist

둘을 동시에 유지하는 이유는 명확하다.

- curated track
  - current architecture / gate의 기준선
- legacy track
  - historical replay와 장기 비교 자산

즉 이는 미정리 상태가 아니라, **운영 기준선과 역사적 비교군을 분리한 상태**로 보는 것이 맞다.

## Current official gates

### Runtime contract gate

- `NAV_T1_030`
- `NAV_T1_071`
- `MIX_T1_021`
- `KBF_T1_017`
- `SKH_T1_060`

이 gate는 다음을 본다.

- numeric planning
- direct-first grounding
- calculation trace preservation
- evaluator/runtime projection

### Multi-entity grounding gate

- `comparison_001`
- `comparison_002`
- `comparison_003`

이 gate는 다음을 본다.

- repeated concept under multiple entities
- company-total row collapse 방지
- segment/entity-aware operand binding

## What this shows in a portfolio

이 benchmark 체계는 단순한 데이터셋 구축 작업이 아니다.  
포트폴리오 관점에서 이 문서가 보여주는 것은 아래다.

- 문제를 “정답률”이 아니라 failure mode로 분해했다
- 그 failure mode를 잡는 benchmark와 gate를 직접 설계했다
- 평가 지표를 generic judge 하나에 맡기지 않고 domain-specific contract로 나눴다
- architecture change를 실험과 gate로 검증하는 엔지니어링 루프를 만들었다

