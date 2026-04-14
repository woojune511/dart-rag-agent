# Benchmarking Guide

이 문서는 DART RAG 시스템의 정확도, 속도, API 비용을 함께 비교하기 위한 실험 가이드입니다.

---

## 1. 목적

이 프로젝트에서 중요한 것은 단순히 “가장 높은 점수”를 찾는 것이 아닙니다.

실제 목표는 아래 세 항목 사이의 균형점을 찾는 것입니다.

- retrieval 정확도
- answer 품질
- 처리 시간과 API 비용

특히 현재 병목은 `contextual_ingest()`이므로, 인덱싱 단계의 trade-off를 정량적으로 보여주는 것이 중요합니다.

---

## 2. 무엇을 측정하는가

### 정확도

- `faithfulness`
- `answer_relevancy`
- `context_recall`
- `retrieval_hit_at_k`
- `section_match_rate`
- `citation_coverage`

### 속도

- `parse.elapsed_sec`
- `ingest.elapsed_sec`
- smoke query 평균 latency

### 비용

- `ingest.api_calls`
- `ingest.prompt_tokens`
- `ingest.output_tokens`
- `estimated_ingest_cost_usd`

---

## 3. 실험 축

우선순위가 높은 실험 축은 아래와 같습니다.

1. chunk size
2. overlap
3. contextual ingest 사용 여부
4. contextual ingest 병렬도
5. batch size
6. metadata prefix on/off
7. cache on/off

권장 시작점:

- `plain_1500_200`
- `contextual_1500_200`
- `contextual_2500_320`
- `contextual_2800_350`

---

## 4. 실행 방법

### 준비

1. `benchmarks/experiment_matrix.sample.json`을 복사해 실제 보고서 경로를 채웁니다.
2. 필요하면 `benchmarks/eval_dataset.template.json`을 실제 평가셋으로 바꿉니다.
3. pricing 정보가 있으면 config에 넣어 비용도 함께 계산합니다.

### 실행

프로젝트 루트에서:

```bash
python -m src.ops.benchmark_runner --config benchmarks/experiment_matrix.sample.json
```

또는 `src` 디렉터리 기준:

```bash
python -m ops.benchmark_runner --config ..\benchmarks\experiment_matrix.sample.json
```

---

## 5. 산출물

기본 출력 경로:

- `benchmarks/results/latest/results.json`
- `benchmarks/results/latest/summary.csv`
- `benchmarks/results/latest/summary.md`

각 파일 역할:

- `results.json`: 전체 실험 원본 결과
- `summary.csv`: 표 비교용
- `summary.md`: 문서와 보고서에 바로 인용 가능한 요약

---

## 6. 해석 방법

가장 좋은 설정은 항상 가장 빠른 설정도, 가장 높은 faithfulness를 가진 설정도 아닙니다.

예를 들어:

- chunk를 키우면 ingest 시간은 줄어들 수 있습니다.
- 하지만 risk 질문에서 retrieval 품질이 약해질 수 있습니다.
- 반대로 작은 chunk는 품질이 좋아도 API 비용과 시간이 너무 커질 수 있습니다.

따라서 최종 설정은 아래 질문으로 고릅니다.

- retrieval 품질이 무너지지 않는가
- 처리 시간이 의미 있게 줄어드는가
- 비용 증가가 감당 가능한가
- 기존 실패 사례가 다시 발생하지 않는가

---

## 7. 보고서에 남길 포인트

실험 결과를 문서화할 때는 단순 최고 점수보다 아래 내용을 같이 남기는 것이 중요합니다.

- baseline 대비 무엇이 얼마나 변했는지
- 속도 개선이 어떤 품질 회귀를 만들었는지
- 왜 최종안이 채택됐는지
- 남은 한계가 무엇인지

추천 문장 예시:

- "`2800 / 350`은 가장 빨랐지만 리스크 질의 품질이 흔들렸다."
- "`2500 / 320`은 ingest 시간을 줄이면서도 리스크 질의를 안정적으로 유지했다."
- "병렬화만으로는 부족했고, API 호출 수 자체를 줄이는 chunk tuning이 함께 필요했다."
