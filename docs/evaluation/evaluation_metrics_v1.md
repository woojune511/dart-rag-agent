# Evaluation Metrics v1

이 문서는 single-document Golden Dataset 기준선에서 사용할 평가 지표를 **registry 형태로 정리**한 문서다.

## Scope

| 항목 | 현재 기준 |
| --- | --- |
| 기준 문서 | `삼성전자 2024 사업보고서` |
| 평가 철학 | retrieval, generation, numeric/domain-specific evaluator를 분리 |
| 주의점 1 | `numeric_fact`는 generic `faithfulness` 하나로만 해석하지 않음 |
| 주의점 2 | `adversarial-out-of-domain`은 `refusal_accuracy`를 별도 핵심 지표로 봄 |

## Metric Registry

### Retrieval Metrics

| Metric | 타입 | 정의 | 주요 용도 | 최종 PASS/FAIL 직접 개입 | 주의점 |
| --- | --- | --- | --- | --- | --- |
| `retrieval_hit_at_k` | retrieval diagnostic | top-k 안에 기대 회사 / 연도 / 섹션을 만족하는 문서가 하나라도 있으면 `1.0` | canonical section hit 여부 확인 | 아니오 | 좋은 문서 하나만 있어도 `1.0`이므로 purity를 충분히 설명하지 못함 |
| `ndcg_at_3`, `ndcg_at_5` | retrieval diagnostic | relevant context가 상위에 얼마나 잘 정렬됐는지 측정 | ranking quality 비교 | 아니오 | section labeling 품질에 영향 받음 |
| `context_precision_at_3`, `context_precision_at_5` | retrieval diagnostic | top-k retrieved docs 중 relevant context 비율 | top-k purity 측정 | 아니오 | expected section 정의가 좁으면 과소평가될 수 있음 |
| `section_match_rate` | retrieval diagnostic | retrieved docs 중 기대 section과 일치하는 비율 | section alignment 확인 | 아니오 | 금융 문서의 대체 유효 섹션을 충분히 반영하지 못할 수 있음 |
| `citation_coverage` | retrieval diagnostic | citation이 기대 company / year / section을 얼마나 반영하는지 측정 | citation 정합성 진단 | 아니오 | 답 자체가 맞아도 canonical section이 아니면 낮게 나올 수 있음 |
| `entity_coverage` | retrieval diagnostic | `required_entities`가 retrieved context 안에 얼마나 포함됐는지 측정 | entity recall 확인 | 아니오 | entity annotation 품질에 영향 받음 |

### Generation Metrics

| Metric | 타입 | 정의 | 주요 용도 | 최종 PASS/FAIL 직접 개입 | 주의점 |
| --- | --- | --- | --- | --- | --- |
| `faithfulness` | generation quality | answer가 retrieved context에 얼마나 근거하는지에 대한 LLM-as-a-judge 점수 | hallucination 억제 지표 | 부분적 | 숫자 질문에서는 표현 차이에 민감할 수 있어 보조 지표로 해석 |
| `answer_relevancy` | generation quality | question / answer 의미적 적합도 | 질문 적합성 보조 지표 | 아니오 | correctness 자체를 대체하지 못함 |
| `context_recall` | generation quality | canonical evidence quote가 retrieved context에 얼마나 회수됐는지 보는 proxy metric | evidence 회수 품질 | 아니오 | dataset quote 설계에 영향 받음 |
| `completeness` | generation quality | 질문이 요구한 핵심 요소를 답변이 빠뜨리지 않았는지 평가 | 답변 누락 여부 확인 | 부분적 | math 질문에서는 final result / unit / direction 중심으로 해석 |

### Refusal Metric

| Metric | 타입 | 정의 | 주요 용도 | 최종 PASS/FAIL 직접 개입 | 주의점 |
| --- | --- | --- | --- | --- | --- |
| `refusal_accuracy` | safety / abstention | 문서에 없는 질문에 적절히 거절했는지, 문서에 있는 질문에서 잘못 거절하지 않았는지 평가 | abstention quality | 부분적 | `false_refusal / hallucinated_answer / correct_refusal`로 더 세분화할 여지 있음 |

### Numeric Metrics

| Metric | 타입 | 정의 | 주요 용도 | 최종 PASS/FAIL 직접 개입 | 주의점 |
| --- | --- | --- | --- | --- | --- |
| `numeric_equivalence` | numeric correctness | answer 숫자와 canonical answer / evidence 숫자가 단위 변환까지 포함해 동치인지 판정 | 숫자 자체의 정답성 | 예 | 현재는 display-aware equivalence로 해석 |
| `numeric_grounding` | numeric grounding | answer 숫자가 runtime evidence와 canonical evidence에 grounded되는지 평가 | 숫자 grounding 확인 | 예 | generic faithfulness와 별도로 보는 것이 중요 |
| `numeric_retrieval_support` | numeric support | 숫자 답변이 실제 읽은 텍스트에 있는 operand에 supported되는지 판정 | numeric PASS 보조축 | 예 | 과거 section-based support에서 operand-grounding support로 재정의됨 |
| `numeric_final_judgement` | resolver output | `PASS / FAIL / UNCERTAIN` 최종 판정 | numeric 최종 판정 | 예 | evaluator 메타-실험의 핵심 지표 |
| `absolute_error_rate` | numeric diagnostic | answer 숫자와 reference 숫자의 상대 오차율 | 수치 오차 크기 확인 | 부분적 | formatting mismatch와 수학 오차를 구분해서 해석해야 함 |
| `calculation_correctness` | math correctness | `multi-hop-calculation` 질문에서 최종 계산 결과가 맞는지 평가 | math path 품질 | 예 | 단순 operation string 일치보다 결과 / grounding 중심 해석 필요 |

## Query-type Interpretation

| Query type | 1차로 볼 지표 | 보조로 볼 지표 | 해석 메모 |
| --- | --- | --- | --- |
| `single-hop-fact` | `retrieval_hit_at_k`, `ndcg_at_5`, `faithfulness`, `completeness` | `citation_coverage` | retrieval과 generation을 함께 봄 |
| `multi-hop-comparison` | `context_recall`, `completeness`, `answer_relevancy` | numeric 계열 | 비교 설명과 grounding 모두 중요 |
| `multi-hop-calculation` | `numeric_equivalence`, `absolute_error_rate`, `calculation_correctness` | `numeric_grounding`, `numeric_final_judgement` | generic faithfulness보다 numeric evaluator를 우선 |
| `synthesis-abstract` | `faithfulness`, `context_recall`, `completeness` | `answer_relevancy` | evidence 압축/조합 능력 확인 |
| `adversarial-out-of-domain` | `refusal_accuracy` | `citation_coverage` | 잘못된 응답보다 적절한 거절이 중요 |

## Current Implementation Status

### 이미 구현된 것

| 범주 | 구현된 지표 |
| --- | --- |
| Retrieval | `retrieval_hit_at_k`, `section_match_rate`, `citation_coverage`, `entity_coverage`, `ndcg_at_3`, `ndcg_at_5`, `context_precision_at_3`, `context_precision_at_5` |
| Generation | `faithfulness`, `answer_relevancy`, `context_recall`, `completeness`, `refusal_accuracy` |
| Numeric / Math | `numeric_equivalence`, `numeric_grounding`, `numeric_retrieval_support`, `numeric_final_judgement`, `absolute_error_rate`, `calculation_correctness` |

### 다음 보완 과제

| 과제 | 이유 |
| --- | --- |
| `completeness`를 entity coverage proxy보다 더 구조적으로 개선 | 질문 의도 반영을 더 정교하게 하기 위해 |
| `refusal_accuracy`를 `false_refusal / hallucinated_answer / correct_refusal`로 세분화 | abstention 품질을 더 선명하게 보기 위해 |
| single-document Golden Dataset의 `draft -> verified` 검수 강화 | metric 해석 안정성 확보 |
