# 실행 계획

> 이 문서는 다음 실험과 확장 우선순위를 정리한 계획서다. 현재 상태는 `CONTEXT.md`, 중요한 설계 판단은 `DECISIONS.md`를 참고한다.

---

## 현재 기준선

현재 기본값:

- `chunk_size = 2500`
- `chunk_overlap = 320`
- `ingest_mode = contextual_all`
- retrieval = dense + BM25 + RRF
- reasoning = evidence-first

현재 확인된 사실:

- contextual ingest가 여전히 가장 큰 시간과 비용 병목이다.
- `contextual_all_2500_320`만 screening을 통과했다.
- `plain`, `parent_only`, `selective`는 모두 다른 실패 양상을 보였다.

---

## 다음 목표

다음 단계의 목표는 단순히 더 빠른 설정을 찾는 것이 아니라, 아래 조건을 동시에 만족하는 저비용 후보를 찾는 것이다.

- retrieval 품질 하한선 유지
- risk 질문 실패 방지
- wrong-company contamination 재발 방지
- ingest 시간 또는 API 비용의 의미 있는 감소

---

## 우선순위 실험

### 1. `contextual_parent_only`의 hybrid 변형 실험

목표:

- parent-only의 큰 비용 절감 효과는 살리고, 숫자/표 중심 질의에서 child-level precision 손실을 줄인다.

아이디어:

- 기본은 parent context 사용
- 예외적으로 아래 chunk는 child contextualization 유지
  - `block_type == table`
  - `매출현황`
  - `재무제표`
  - `연구개발`
  - `리스크`

성공 기준:

- API calls가 `contextual_all_2500_320`보다 유의미하게 감소
- numeric fact miss가 재현되지 않을 것

### 2. `contextual_selective_v2` 실험

목표:

- 지금 selector는 너무 넓고도 business overview retrieval을 놓친다.

개선 방향:

- 반드시 contextualize할 section과 block을 더 좁고 명확하게 정의
- 대표 paragraph와 table만 선택하고, 나머지는 plain 유지

예상 포함 후보:

- `사업개요`
- `위험관리 및 파생거래`
- `연구개발`
- `매출 및 수주상황`
- 짧은 표, 표 중심 chunk

성공 기준:

- contextualized chunk 수가 현재 selective보다 확실히 줄어들 것
- business overview miss가 없어질 것

### 3. retrieval 평가 기준 보강

목표:

- 현재 `section_match_rate`는 baseline도 낮아, "정답 섹션 1개는 찾지만 top-k가 많이 섞이는" 현상을 충분히 설명하지 못한다.

후보 작업:

- 허용 가능한 section alias 정의
- 숫자 질의에서 `매출현황`, `재무제표`, `요약재무`를 동급으로 볼지 기준 정리
- contamination을 별도 지표로 분리

### 4. benchmark coverage 확장

목표:

- 삼성전자 한 문서에서 유효했던 기본값이 다른 기업에도 유지되는지 확인한다.

후보 기업:

- SK하이닉스
- NAVER
- LG전자

성공 기준:

- 최소 2개 기업에서 동일한 실험 매트릭스를 다시 실행
- 같은 실패 패턴이 반복되는지 확인

---

## 유지할 실험 축

앞으로도 아래 축은 유지한다.

### Chunking

- `1500 / 200`
- `2500 / 320`
- 필요 시 `2800 / 350`을 speed reference로만 사용

### Ingest mode

- `plain`
- `contextual_all`
- `contextual_parent_only`
- `contextual_selective`
- 향후 `contextual_parent_hybrid`
- 향후 `contextual_selective_v2`

### Parallelism

- `screening.parallel_experiments = 1`
- `screening.parallel_experiments = 2`
- `screening.parallel_experiments = 3`

### Cost controls

- metadata prefix on/off
- cache on/off

---

## 측정 항목

### 품질

- `retrieval_hit_at_k`
- `section_match_rate`
- `citation_coverage`
- `faithfulness`
- `answer_relevancy`
- `context_recall`

### 속도

- `parse.elapsed_sec`
- `ingest.elapsed_sec`
- smoke query latency

### 비용

- `api_calls`
- `prompt_tokens`
- `output_tokens`
- `estimated_ingest_cost_usd`

### 안정성

- wrong-company contamination
- risk query failure
- missing-information hallucination

---

## 문서화 산출물

실험이 끝나면 아래 자산을 유지한다.

- `benchmarks/results/.../results.json`
- `benchmarks/results/.../summary.csv`
- `benchmarks/results/.../summary.md`
- `docs/benchmarking.md`
- 필요 시 `DECISIONS.md`의 핵심 비교 요약

---

## 성공 조건

다음 단계의 성공은 아래를 모두 만족하는 후보를 찾는 것이다.

- screening quality floor 통과
- risk/business 핵심 질의에서 hit@k 유지
- contamination 없음
- baseline 대비 ingest 시간 또는 API cost가 의미 있게 감소
- 결과를 수치와 사례로 문서화할 수 있을 것
