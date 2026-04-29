# Single-Document Evaluation Strategy

이 문서는 시스템 전반을 다시 정렬하기 위한 새 기준선을 정의한다.

핵심 원칙:

- 먼저 **단일 문서** 기준으로 Golden Dataset과 evaluator를 고정한다.
- 그 다음에 retrieval, compression, validation을 개선한다.
- multi-company generalization은 그 이후 단계로 둔다.

현재 추천 기준 문서:

- `삼성전자 2024 사업보고서`
- 접수번호 `20250311001085`

## 왜 이 방향으로 바꾸는가

최근 실험으로 다음 사실이 더 분명해졌다.

- retrieval / generation의 국소 조정은 가능하다
- 하지만 무엇이 실제 개선인지 해석하는 기준선이 아직 약하다
- 질문 몇 개에 맞춘 local optimization으로 흐르기 쉽다
- multi-company benchmark는 parser 차이, section alias 차이, evaluator 차이가 함께 섞인다

따라서 다음 단계는 retrieval / generation tweak보다 먼저,
**질문 taxonomy, 정답 기준, 평가 지표를 단일 문서에서 먼저 고정하는 것**이다.

## 개발 순서

### Phase 1. Golden Dataset 설계

대상:

- 삼성전자 2024 사업보고서 1건

초기 규모:

- `20~30개`

확장 목표:

- `50~100개`

질문 taxonomy:

- `single-hop-fact`
- `multi-hop-comparison`
- `multi-hop-calculation`
- `synthesis-abstract`
- `adversarial-out-of-domain`

### Phase 2. JSON schema v1 확정

권장 필드:

```json
{
  "query_id": "q_001",
  "document_id": "samsung_2024_business_report",
  "company": "삼성전자",
  "year": 2024,
  "category": "multi-hop-calculation",
  "question": "2023년 대비 2024년 삼성전자 DX부문 매출 증감액은?",
  "ground_truth_answer": "2024년 DX부문 매출은 X원, 2023년은 Y원으로 총 Z원 증가했습니다.",
  "expected_sections": ["매출 및 수주상황"],
  "ground_truth_context_ids": ["section4_table2", "section4_paragraph3"],
  "ground_truth_evidence_quotes": ["...", "..."],
  "required_entities": ["DX부문", "매출", "증가액"],
  "answer_type": "numeric",
  "expected_refusal": false,
  "numeric_constraints": {
    "unit": "억원",
    "tolerance": 0.0
  },
  "reasoning_steps": [
    "2024 DX부문 매출 추출",
    "2023 DX부문 매출 추출",
    "차이 계산"
  ],
  "aliases": {
    "DX부문": ["DX", "Device eXperience"]
  }
}
```

핵심 필드:

- `document_id`
- `ground_truth_context_ids`
- `ground_truth_evidence_quotes`
- `answer_type`
- `expected_refusal`
- `numeric_constraints`
- `reasoning_steps`

### Phase 3. Evaluator 분리

공통 retrieval 지표:

- `hit@k`
- `ndcg@k`
- `context_precision@k`
- `context_recall`
- `section_match_rate`
- `entity_coverage`

공통 generation 지표:

- `faithfulness`
- `answer_relevance`
- `completeness`

도메인 전용 지표:

- `numeric_equivalence`
- `absolute_error_rate`
- `unit_consistency`
- `calculation_correctness`
- `refusal_accuracy`

원칙:

- `numeric_fact`는 generic `faithfulness` 하나로 채점하지 않는다
- `adversarial-out-of-domain`은 `refusal_accuracy`를 주 지표로 본다
- `synthesis-abstract`는 `completeness`와 `faithfulness`를 함께 본다

### Phase 4. benchmark runner 연결

이 단계에서 `src/ops/benchmark_runner.py`를 다음 방식으로 재정렬한다.

1. single-document dataset 읽기
2. category별 evaluator 분기
3. 노드 단위 로그 남기기
   - `classify`
   - `retrieve`
   - `build_evidence`
   - `compress`
   - `validate`
   - `cite`
4. 질문 단위 / category 단위 / run 단위 요약

### Phase 5. 시스템 개선 재개

여기까지 끝난 뒤에만 다시 손댄다.

- chunk size
- retrieval bias
- parent-child 전략
- compression
- validator
- calculator / tool use

즉 앞으로는 evaluator 없이 시스템을 바꾸지 않는다.

## 추천 산출물

- `benchmarks/golden/samsung_2024_v1.json`
- `docs/evaluation/golden_dataset_schema.md`
- `docs/evaluation/evaluation_metrics_v1.md`
- `benchmarks/profiles/single_document_dev.json`

## 성공 조건

- 삼성전자 2024 기준 Golden Dataset 20개 이상 구축
- category별 evaluator가 분리되어 동작
- numeric / refusal / synthesis를 서로 다른 기준으로 해석 가능
- 이후 retrieval / generation 실험이 모두 이 dataset 기준으로 비교됨

## 하지 않을 것

당분간은 아래를 먼저 하지 않는다.

- 다기업 full benchmark 확대
- full GraphRAG
- full multi-agent
- benchmark 질문 몇 개에 맞춘 rule 추가

한 줄 요약:

**다음 단계의 기준선은 “단일 문서에서 질문셋과 평가를 먼저 고정하고, 그 위에서만 시스템을 바꾼다”이다.**
