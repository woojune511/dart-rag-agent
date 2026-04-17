# 실행 계획

이 문서는 다음 스프린트의 우선순위와 성공 조건을 정리한 계획서다.

## 현재 기준선

현재 기본 baseline:

- `chunk_size = 2500`
- `chunk_overlap = 320`
- `ingest_mode = contextual_all`
- retrieval = dense + BM25 + RRF
- reasoning = evidence-first

현재까지 확인된 사실:

- 삼성전자 기준으로 `contextual_parent_only_2500_320`가 screening을 통과한 적이 있다
- `plain`은 risk retrieval miss가 반복됐다
- `contextual_selective_v2`는 business overview miss 가능성이 남아 있다
- `contextual_parent_hybrid`는 품질은 보완할 수 있지만 비용 이점이 약할 수 있다
- 3기업을 한 번에 도는 monolithic run은 timeout과 비용 리스크가 커서 기본 루프로 부적합하다

추가로 확인된 평가 한계:

- 기존 `ground_truth` 한 줄만으로는 도메인 비전문가가 정답 타당성을 검수하기 어렵다
- retrieval 지표보다 answer-level 지표의 신뢰도를 설명하기 어려웠다

## 이번 스프린트 목표

이번 스프린트는 운영 기본값을 바꾸는 단계가 아니다.  
`v4_generalization_fix_2026-04-17`까지 완료한 현재 목표는 **더 싼 ingest 후보를 새로 찾는 것보다, 현재 저비용 후보가 실패하는 query-stage 패턴을 줄여 다음 일반화 run에서 다시 비교 가능하게 만드는 것**이다.

기본 운영 방식:

- 평소에는 `benchmarks/profiles/dev_fast.json`으로 단일 기업 + screening only
- shortlist 검증 때만 `benchmarks/profiles/release_generalization.json`으로 3기업 run
- release run도 회사별 job으로 분리 실행하고 partial summary를 허용

핵심 질문:

- 왜 저비용 후보들이 numeric / risk / R&D에서 abstention으로 무너지는가
- 왜 NAVER에서는 business overview가 계속 miss되는가
- missing-information 질문에서 hallucination을 어떻게 줄일 것인가
- 이 문제를 줄인 뒤에도 `contextual_parent_only` 또는 `contextual_selective_v2`가 비용 이점을 유지하는가

## 우선순위 작업

### 1. Query-stage abstention 분석

대상:

- `numeric_fact`
- `risk_analysis`
- `r_and_d_investment`

목표:

- retrieved docs는 충분한데 answer가 abstain하는 케이스를 분리
- 실제 retrieval miss와 reasoning / prompting miss를 구분
- smoke query failure를 “retrieval failure / evidence failure / analyze failure” 수준으로 다시 분류

### 1-1. Cost-efficient workflow 정착

- `reuse_store`, `reuse_context_cache`, `force_reindex`를 실행 설정으로 명시
- 같은 보고서/동일 청킹 설정 재실행 시 contextual ingest 비용을 다시 쓰지 않게 만들기
- `stores/`와 `context_cache/`를 분리해, store를 다시 만들더라도 API 호출은 재사용할 수 있게 유지
- fast loop에서는 full eval을 기본 비활성화

### 2. NAVER business overview retrieval 개선

현재 관찰:

- NAVER는 parser 보정 후에도 `business_overview_001`이 계속 miss된다.
- 상위 검색 결과가 `I. 회사의 개요`, `IV. 이사의 경영진단 및 분석의견`, `III. 재무에 관한 사항` 쪽으로 편중된다.

목표:

- NAVER에서 실제 사업 설명이 들어 있는 section 우선순위를 다시 정의
- rerank나 section bias 조정이 필요한지 확인
- 다음 run에서 `business_overview_001` miss를 먼저 줄이기

### 3. Missing-information 안정화

현재 관찰:

- NAVER에서 `신규사업 및 중단사업` 질문은 smoke 단계에서 hallucination으로 잡힌다.

목표:

- missing-information prompt / 판정 기준을 점검
- partial limitation과 true missing response를 더 분명히 구분
- “근거 없음” 응답이 citation 없이 단정으로 흐르지 않도록 제어

### 4. 평가 보강

- screening cutoff는 그대로 유지:
  - `retrieval_hit_drop_threshold = 0.10`
  - `section_match_drop_threshold = 0.15`
- critical category는 `risk / business / numeric`로 본다
- 산출물:
  - 기업별 `results.json`, `summary.csv`, `summary.md`, `review.csv`, `review.md`
  - 전체 `cross_company_summary.csv`, `cross_company_summary.md`
- 승자 선정 우선순위를 문서화:
  1. pass count
  2. critical miss 여부
  3. API calls 감소율
  4. ingest 시간 감소율
  5. full eval의 `faithfulness`, `context_recall`
  6. reviewer artifact 정성 검토

## 측정 항목

### 품질

- `retrieval_hit_at_k`
- `section_match_rate`
- `citation_coverage`
- `contamination_rate`
- reviewer artifact에서 질문별 정답 근거 추적 가능 여부

### 속도 / 비용

- `ingest.elapsed_sec`
- `api_calls`
- `parent_context_calls`
- `child_context_calls`
- `prompt_tokens`
- `output_tokens`

### 정식 평가

- `faithfulness`
- `answer_relevancy`
- `context_recall`

## 성공 조건

이번 단계의 성공 조건은 “기본값 후보 확정”이 아니라 아래다.

- NAVER `business_overview_001` miss 원인을 retrieval / reasoning 중 어디인지 분리
- numeric / risk / R&D abstention이 반복되는 대표 케이스 3개 이상을 설명 가능하게 정리
- missing-information hallucination을 유발하는 대표 패턴을 재현 가능하게 문서화
- 위 수정 후 `dev_fast` 기준 재실험으로 적어도 1개 failure type이 줄어드는지 확인

## 현재 상태와 다음 단계

`v4_generalization_fix_2026-04-17`의 실제 결과는 다음과 같다.

- `run_status = completed`
- 3개 기업 공통 screening 통과 후보 없음
- `contextual_all_2500_320`
  - 가장 안정적인 baseline
- `contextual_parent_only_2500_320`
  - 가장 큰 비용 절감
  - 하지만 answerable smoke abstention 반복
- `contextual_selective_v2_2500_320`
  - 의미 있는 비용 절감
  - 하지만 business overview / risk miss 반복
- `contextual_parent_hybrid_2500_320`
  - baseline보다 비싼 경우가 있어 실익이 약함

지금 기준 다음 우선순위는 아래다.

1. query-stage abstention을 유발하는 evidence / analyze 단계 패턴 점검
2. NAVER business overview retrieval 실패 원인 정리
3. missing-information hallucination 억제
4. 그 다음에 `dev_fast` 기준 재실험
5. 실패 유형이 줄어든 뒤에만 release generalization 재실행
