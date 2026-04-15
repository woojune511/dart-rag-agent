# Benchmarking Guide

이 문서는 DART 공시 RAG 시스템에서 정확도, 처리 속도, API 비용 사이의 trade-off를 비교하기 위한 benchmark 가이드다.

---

## 목적

benchmark의 목표는 단순히 가장 높은 점수 하나를 찾는 것이 아니다. 아래 세 축을 함께 비교해, 품질 하한선을 넘기면서도 운영 가능한 기본값을 찾는 것이 목적이다.

- retrieval 정확도
- answer 품질
- ingest 시간과 API 비용

현재 가장 큰 병목은 `contextual_ingest()`의 LLM 호출이다. 그래서 실험도 "저비용 후보를 먼저 screening하고, 통과안만 정식 평가로 올리는 구조"로 설계한다.

---

## Ingest 모드

### `plain`

- child chunk 원문만 인덱싱
- LLM contextualization 없음
- API calls 0

가장 저렴한 baseline이다. 대신 리스크 질의처럼 문맥 신호가 약한 경우 retrieval miss가 발생할 수 있다.

### `contextual_all`

- 모든 child chunk에 대해 LLM 1문장 context 생성
- `context + metadata prefix + child chunk`를 인덱싱

현재 품질 기준선이다. 비용과 시간이 가장 큰 편이다.

### `contextual_parent_only`

- 같은 `parent_id`를 공유하는 parent section마다 1회만 context 생성
- 각 child chunk는 `parent context + metadata prefix + child chunk` 형태로 인덱싱

호출 수를 child chunk 수에서 parent section 수 수준으로 줄이기 위한 후보다.

### `contextual_selective`

- retrieval에 취약한 chunk만 context 생성
- 초기 selector 규칙:
  - `block_type == table`
  - 짧은 chunk
  - 특정 section:
    - `리스크`
    - `연구개발`
    - `매출현황`
    - `사업개요`
    - `경영진단`

비용을 줄이면서도 retrieval signal을 유지하려는 후보다.

---

## 2단계 평가 구조

### 1차 Screening

목적:

- 저비용 후보를 빠르게 탈락시키기

측정 지표:

- `parse.elapsed_sec`
- `ingest.elapsed_sec`
- `api_calls`
- `prompt_tokens`
- `output_tokens`
- `estimated_ingest_cost_usd`
- smoke query latency
- `retrieval_hit_at_k`
- `section_match_rate`
- `citation_coverage`

이 단계에서는 비용이 큰 아래 지표를 계산하지 않는다.

- `faithfulness`
- `answer_relevancy`
- `context_recall`

### 2차 Full Evaluation

목적:

- screening을 통과한 상위 후보만 정식 품질 비교

추가 지표:

- `faithfulness`
- `answer_relevancy`
- `context_recall`

정식 평가는 MLflow에도 기록한다.

---

## 지표 정의

### 속도

- `parse.elapsed_sec`
  - `FinancialParser.process_document()` 실행 시간
- `ingest.elapsed_sec`
  - 인덱싱 완료까지 전체 시간
  - contextual mode는 LLM context 생성 시간 포함
- `smoke query latency`
  - `agent.run()` end-to-end 시간

### 비용

- `api_calls`
  - 실제 context 생성 대상 수
  - `contextual_all`: child chunk 수
  - `contextual_parent_only`: parent section 수
  - `contextual_selective`: 선택된 chunk 수
- `prompt_tokens`, `output_tokens`
  - contextual ingest 응답 usage metadata 합계
- `estimated_ingest_cost_usd`
  - config의 백만 토큰당 단가 기준 추정치

### Retrieval / Answer 품질

- `retrieval_hit_at_k`
  - 기대 `company + year + section`을 만족하는 문서가 top-k 안에 하나라도 있으면 `1.0`
- `section_match_rate`
  - retrieved docs 중 기대 section과 일치하는 비율
- `citation_coverage`
  - citation 문자열 안에 기대 `company`, `year`, `section`이 얼마나 반영됐는지 비율
- `faithfulness`
  - 답변과 retrieved context를 LLM judge로 비교한 점수
- `answer_relevancy`
  - 질문과 답변 embedding cosine similarity
- `context_recall`
  - ground truth 문장 토큰이 retrieved context 토큰과 50% 이상 겹치는 문장 비율

---

## Screening 통과 기준

아래 중 하나라도 깨지면 탈락이다.

- risk smoke query가 근거를 찾지 못했다고 실패
- wrong-company contamination 발생
- citation이 다른 회사나 연도를 가리킴
- risk 또는 business query에서 `retrieval_hit_at_k == 0`
- missing-information query에서 근거 없는 단정 답변 생성

정량 기준:

- baseline 대비 `retrieval_hit_at_k` 하락 폭이 `0.10` 초과면 탈락
- baseline 대비 `section_match_rate` 하락 폭이 `0.15` 초과면 탈락

현재 baseline은 `contextual_all_2500_320`이다.

---

## 병렬 실행 정책

- `screening.parallel_experiments`
  - screening 실험을 동시에 몇 개까지 실행할지 결정
  - 기본값은 `2`

실험 간 병렬화는 screening 단계에만 적용한다. full evaluation은 해석 일관성과 안정성을 위해 순차로 유지한다.

---

## 현재 기본 실험 매트릭스

1차 screening:

- `plain_2500_320`
- `contextual_all_2500_320`
- `contextual_parent_only_2500_320`
- `contextual_selective_2500_320`
- `contextual_1500_200`

2차 full evaluation:

- screening 통과안
- legacy reference인 `contextual_1500_200`

---

## 현재 로컬 benchmark 결과

기준 문서:

- 삼성전자 2024 사업보고서

요약:

| Experiment | Pass | Ingest (s) | API Calls | Hit@k | Section Match | Notes |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `plain_2500_320` | No | 19.183 | 0 | 0.800 | 0.125 | 저렴하지만 risk retrieval miss |
| `contextual_all_2500_320` | Yes | 558.723 | 300 | 1.000 | 0.250 | 현재 baseline |
| `contextual_parent_only_2500_320` | No | 67.964 | 40 | 0.800 | 0.175 | numeric fact miss |
| `contextual_selective_2500_320` | No | 331.002 | 289 | 0.800 | 0.150 | business overview miss, 비용 절감도 제한적 |
| `contextual_1500_200` | No | 774.632 | 502 | 0.800 | 0.225 | 더 느리고 business overview miss |

full evaluation:

- `contextual_all_2500_320`
  - `faithfulness = 0.400`
  - `answer_relevancy = 0.651`
  - `context_recall = 0.500`
- `contextual_1500_200`
  - `faithfulness = 0.640`
  - `answer_relevancy = 0.500`
  - `context_recall = 0.300`

---

## 실행 방법

프로젝트 루트에서:

```bash
python -m src.ops.benchmark_runner --config benchmarks/experiment_matrix.sample.json
```

또는 `src` 디렉터리 기준으로:

```bash
python -m ops.benchmark_runner --config ..\benchmarks\experiment_matrix.sample.json
```

---

## 결과 자산

기본 출력 경로:

- `benchmarks/results/<run_name>/results.json`
- `benchmarks/results/<run_name>/summary.csv`
- `benchmarks/results/<run_name>/summary.md`

역할:

- `results.json`
  - screening과 full evaluation의 원본 결과
- `summary.csv`
  - 실험별 수치 비교용 표
- `summary.md`
  - 문서와 발표에 바로 사용할 수 있는 요약

---

## 해석 원칙

가장 좋은 설정은 무조건 가장 빠른 설정도, 무조건 가장 높은 점수의 설정도 아니다. 아래 질문에 동시에 답할 수 있어야 한다.

- retrieval 품질이 무너지지 않았는가
- risk 질의가 안정적으로 유지되는가
- ingest 시간과 API 비용이 의미 있게 줄었는가
- 실패 패턴을 재현 가능하게 설명할 수 있는가

현재까지의 결론은 "비용을 줄이는 시도는 가능하지만, 품질 하한선을 유지하는 후보는 아직 `contextual_all_2500_320`뿐"이라는 점이다.
