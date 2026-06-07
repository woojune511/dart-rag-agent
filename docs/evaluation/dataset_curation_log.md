# Dataset Curation Log

이 문서는 benchmark dataset과 gate question set에 대해  
**무엇을 유지하고, 무엇을 분리하고, 무엇을 official gate로 채택했는지**를 남기는 기록이다.

성격:

- append-only에 가깝게 유지
- 구현 메모보다 curation / benchmark 운영 결정 위주

## Current active curated assets

| asset | 현재 역할 |
| --- | --- |
| `single_doc_eval_full.curated.json` | single-document canonical source of truth |
| `single_doc_eval_multi_subtask.curated.json` | multi-subtask subset |
| `single_doc_eval_multi_metric_numeric.curated.json` | multi-metric numeric smoke subset |
| `multi_report_eval_full.curated.json` | multi-report canonical source of truth |

## Notable curation decisions

### 1. Single-document curated set를 mainline source of truth로 사용

이유:

- parser/retrieval/evaluator failure를 가장 일관되게 해석할 수 있다
- multi-company noise와 parser 차이를 줄일 수 있다

현재 README 기준 기록:

- single-doc curated core set `77`문항 확정

### 2. Multi-report 질문은 별도 curated set으로 분리

이유:

- single-document failure와 multi-report retrieval failure를 섞지 않기 위해서
- 같은 benchmark 안에서 두 문제를 같이 보면 진단이 흐려진다

현재 운영 문서 기준:

- `multi_report_eval_full.curated.json`
- active row `1` (`SAM_T2_002`)

### 3. Runtime contract gate를 대표 numeric canary 5문항으로 축소

선정 문항:

- `NAV_T1_030`
- `NAV_T1_071`
- `MIX_T1_021`
- `KBF_T1_017`
- `SKH_T1_060`

선정 이유:

- subtraction
- lookup + difference preservation
- multi-metric aggregate answer
- percent multi-period grounding
- concept-ratio grounding

즉 숫자 QA의 주요 failure mode를 최소 질문 수로 커버하도록 골랐다.

### 4. Multi-entity grounding gate를 별도로 분리

선정 문항:

- `comparison_001`
- `comparison_002`
- `comparison_003`

분리 이유:

- entity/segment binding failure는 일반 numeric QA와 failure shape가 다르다
- company-total row collapse 문제를 별도 gate로 봐야 설계 비교가 쉬워진다

### 5. Legacy 2024 benchmark asset은 유지하되 mainline source of truth에서는 내림

대상:

- `eval_dataset.canonical.json`
- `eval_dataset.math_focus.json`

이유:

- 과거 실험 replay에는 필요하다
- 하지만 current curated gate의 기준선 역할은 curated dataset에 넘기는 것이 더 명확하다

## Current candidate-comparison decisions

### Runtime contract gate

운영 역할:

- `plain_prefix_8000_400`
  - speed/cost baseline
- `structural_selective_v2_prefix_2500_320`
  - current operating default
- `contextual_selective_v2_prefix_2500_320`
  - historical quality reference

현재 해석:

- routine runtime-contract validation은
  `benchmarks/profiles/curated_runtime_contract_gate.json`의
  `structural_selective_v2_prefix_2500_320`만 사용한다.
- `contextual_selective_v2_prefix_2500_320`는 더 이상 routine gate 후보가
  아니라, structural regression이 확인됐을 때
  `benchmarks/profiles/curated_contextual_arbitration.json`으로만 돌리는
  arbitration reference다.
- `plain_prefix_8000_400`은 비용/속도 비교용 baseline으로 남기되 default
  승격 후보는 아니다.

### Multi-entity grounding gate

운영 역할:

- `structural_selective_v2_prefix_2500_320`
  - current operating default
- `contextual_selective_v2_prefix_2500_320`
  - historical quality reference

이유:

- routine multi-entity grounding validation은
  `benchmarks/profiles/curated_multi_entity_grounding_gate.json`의 structural
  candidate만 사용한다.
- contextual candidate는 entity grounding 품질을 유지하면서 ingest 비용을
  줄였다는 결론의 historical reference로 남긴다. 새 regression이 structural
  ingest에만 생겼는지 확인해야 할 때만 contextual arbitration profile로
  재실행한다.

## Curation principles to preserve

앞으로도 유지해야 할 기준은 아래와 같다.

1. 질문은 failure mode 기준으로 고른다
2. answer key는 evidence-backed여야 한다
3. official gate는 작고 강해야 한다
4. curated mainline과 historical legacy asset은 역할을 분리한다
5. 설계 비교는 gate를 통과한 뒤에만 default candidate로 승격한다

