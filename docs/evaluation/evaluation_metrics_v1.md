# Evaluation Metrics v1

이 문서는 single-document Golden Dataset 기준선에서 사용할 평가 지표를 정의한다.

기준 문서:

- `삼성전자 2024 사업보고서`

핵심 원칙:

- retrieval, generation, domain-specific metric을 분리한다
- `numeric_fact`는 generic `faithfulness` 하나로만 해석하지 않는다
- `adversarial-out-of-domain`은 `refusal_accuracy`를 별도 핵심 지표로 본다

## Retrieval Metrics

### `retrieval_hit_at_k`

- top-k 안에 기대 회사 / 연도 / 섹션을 만족하는 문서가 하나라도 있으면 `1.0`

### `ndcg_at_3`, `ndcg_at_5`

- relevant context가 상위에 얼마나 잘 정렬됐는지 본다
- `hit@k`보다 순위 품질을 더 잘 본다

### `context_precision_at_3`, `context_precision_at_5`

- top-k retrieved docs 중 relevant context 비율

### `section_match_rate`

- retrieved docs 중 기대 section과 일치하는 비율

### `citation_coverage`

- citation이 기대 company / year / section을 얼마나 반영하는지 본다

### `entity_coverage`

- `required_entities`가 retrieved context 안에 얼마나 포함됐는지 본다

## Generation Metrics

### `faithfulness`

- answer가 retrieved context에 얼마나 근거하는지에 대한 LLM-as-a-judge 점수
- 단, 숫자 질문에서는 보조 지표로만 해석한다

### `answer_relevancy`

- question / answer embedding similarity
- correctness보다 질문 적합성 보조 지표에 가깝다

### `context_recall`

- canonical evidence quote가 retrieved context에 얼마나 회수됐는지 보는 proxy metric

### `completeness`

- 질문이 요구한 핵심 요소를 답변이 빠뜨리지 않았는지 본다
- 현재 구현은 `required_entities`와 answer coverage 기준의 proxy metric이다

## Refusal Metric

### `refusal_accuracy`

- 문서에 없는 질문에 대해 적절히 거절했는지
- 문서에 있는 질문에서 잘못 거절하지 않았는지도 함께 본다

## Numeric Metrics

### `numeric_equivalence`

- answer 숫자와 canonical answer / evidence 숫자가 단위 변환까지 포함해 동치인지 본다

### `numeric_grounding`

- answer 숫자가 runtime evidence와 canonical evidence에 grounded되는지에 대한 judge score

### `numeric_retrieval_support`

- 숫자 답변이 기대 회사 / 연도 / 섹션 retrieval 위에 올라와 있는지 본다

### `numeric_final_judgement`

- `PASS / FAIL / UNCERTAIN`
- numeric evaluator resolver의 최종 판정

### `absolute_error_rate`

- answer 숫자와 reference 숫자의 상대 오차율

### `calculation_correctness`

- `multi-hop-calculation` 질문에서 최종 계산 결과가 맞는지 본다

## 해석 원칙

### `single-hop-fact`

주요 지표:

- `retrieval_hit_at_k`
- `ndcg_at_5`
- `faithfulness`
- `completeness`

### `multi-hop-comparison`

주요 지표:

- `context_recall`
- `completeness`
- `answer_relevancy`

### `multi-hop-calculation`

주요 지표:

- `numeric_equivalence`
- `absolute_error_rate`
- `calculation_correctness`

### `synthesis-abstract`

주요 지표:

- `faithfulness`
- `context_recall`
- `completeness`

### `adversarial-out-of-domain`

주요 지표:

- `refusal_accuracy`
- `citation_coverage`

## 현재 구현 상태

이미 구현된 것:

- `retrieval_hit_at_k`
- `section_match_rate`
- `citation_coverage`
- `faithfulness`
- `answer_relevancy`
- `context_recall`
- `numeric_equivalence`
- `numeric_grounding`
- `numeric_retrieval_support`
- `numeric_final_judgement`
- `absolute_error_rate`
- `calculation_correctness`
- `entity_coverage`
- `completeness`
- `refusal_accuracy`
- `ndcg_at_3`, `ndcg_at_5`
- `context_precision_at_3`, `context_precision_at_5`

다음 보완 과제:

- `completeness`를 entity coverage proxy보다 더 구조적인 방식으로 개선
- `refusal_accuracy`의 `false_refusal / hallucinated_answer / correct_refusal` 세분화
- single-document Golden Dataset의 `draft -> verified` 검수 후 metric 해석 안정화
