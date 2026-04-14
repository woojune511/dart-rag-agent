# 실험 및 확장 계획

> 이 문서는 앞으로의 구현 아이디어를 모두 적는 메모가 아니라, 실제로 실행할 다음 실험과 확장 우선순위를 정리한 문서입니다.

---

## 1. 현재 기준선

현재 채택된 기본 설정:

- `chunk_size = 2500`
- `chunk_overlap = 320`
- `ingest_mode = contextual`
- retrieval = Dense + BM25 + RRF
- reasoning = evidence-first

현재 중요한 기준점:

- `1500 / 200`: 정확도는 괜찮지만 ingest가 너무 느림
- `2800 / 350`: 가장 빠르지만 리스크 질의 품질 회귀
- `2500 / 320`: 현재 가장 균형 잡힌 기본값

---

## 2. 다음 스프린트 목표

다음 스프린트의 핵심 목표는 아래 하나입니다.

**정확도, 처리 시간, API 비용의 trade-off를 측정 가능한 형태로 만들고, 그 위에서 기본값을 더 정교하게 선택한다.**

즉 이번 계획의 중심은 “기능 추가”보다 “설정 비교와 근거 축적”입니다.

---

## 3. 우선 실험할 축

### A. Chunking

- `1500 / 200`
- `2000 / 250`
- `2500 / 320`
- `2800 / 350`

목표:

- 청크 수 감소가 ingest 시간과 retrieval 품질에 어떤 영향을 주는지 확인

### B. Contextualization 범위

- `plain`
- `contextual_all`
- `contextual_parent_only`
- `contextual_selective`

목표:

- 모든 청크에 대해 LLM을 호출하지 않아도 retrieval 품질을 유지할 수 있는지 확인

### C. Contextual ingest 병렬도

- `max_workers = 4`
- `max_workers = 8`
- `max_workers = 12`

목표:

- 속도 개선 한계와 안정성 범위를 확인

### D. Metadata prefix

- `prefix on`
- `prefix off`

목표:

- larger chunk에서 deterministic prefix가 retrieval 품질을 얼마나 보완하는지 확인

### E. Cache

- `cache off`
- `cache on`

목표:

- 재인덱싱과 반복 실험에서 API 비용을 얼마나 줄일 수 있는지 확인

---

## 4. 측정 기준

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

- `api_calls`
- `prompt_tokens`
- `output_tokens`
- `estimated_ingest_cost_usd`

### 품질 회귀 체크

- single-company contamination 재발 여부
- risk 질의 품질 회귀 여부
- “문서에 없음” 답변 처리 안정성

---

## 5. 평가셋 계획

최소 다섯 가지 범주는 항상 유지합니다.

1. 숫자 질의
2. 사업 개요 질의
3. 리스크 질의
4. 연구개발 / 투자 질의
5. 문서에 없는 정보 질의

추가할 회귀 사례:

- repeated boilerplate
- 표 기반 수치 질문
- section ambiguity
- wrong-company contamination

---

## 6. 기대 산출물

실험이 끝나면 아래 결과물이 남아야 합니다.

- `benchmarks/results/.../results.json`
- `benchmarks/results/.../summary.csv`
- `benchmarks/results/.../summary.md`
- MLflow run 비교 기록
- 문서용 benchmark summary

최종적으로는 아래 메시지가 문서에서 보이게 만드는 것이 목표입니다.

- 어떤 설정이 가장 빨랐는지
- 어떤 설정이 가장 정확했는지
- 왜 최종안이 그 둘과 다를 수 있는지
- 왜 현재 기본값이 합리적인지

---

## 7. 추천 실행 순서

1. 삼성전자 2024 사업보고서 기준 baseline matrix 실행
2. curated eval set 보강
3. 다른 기업 1~2개로 동일 matrix 재실행
4. contextual cache 도입 전/후 비교
5. selective contextualization 실험
6. 결과 문서화 및 기본값 재선정

---

## 8. 성공 기준

다음 조건을 만족하면 이번 계획은 성공입니다.

- retrieval 품질 저하 없이 ingest 시간이 의미 있게 감소
- API 비용을 정량적으로 설명 가능
- 같은 실패 사례를 반복해서 재현하고 비교 가능
- 최종 기본값 선택 이유를 수치로 설명 가능
