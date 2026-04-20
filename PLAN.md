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

추가로, `v6` / `v7` faithfulness 보정 실험을 통해 **question-type별 hardcoded rule을 계속 늘리는 방식은 장기적으로 위험하다**는 점이 분명해졌다. 앞으로는 점수 자체를 올리는 것보다, [answer_generation_principles.md](docs/answer_generation_principles.md)에 정리한 원칙에 맞춰 answer generation 구조를 더 단순하고 설명 가능하게 만드는 것을 우선한다.

또한 구조 개편 방향은 [architecture_direction.md](docs/architecture_direction.md)에 정리했다. 현재 결론은 full GraphRAG / full multi-agent로 바로 가기보다, document-structure graph + structured evidence + answer compression/validation 쪽 리팩터링이 더 적절하다는 것이다.

숫자 질문(`numeric_fact`)은 일반 서술형 `faithfulness` judge와 분리해서 다루기로 했고, 현재 [numeric_evaluation_architecture.md](docs/numeric_evaluation_architecture.md)에 정리한 **parallel numeric evaluators + resolver** 구조의 1차 구현이 들어간 상태다. 삼성전자 `numeric_fact_001` 재검증에서는 generic `faithfulness=0.0`인데도 `numeric_final_judgement=PASS`가 나와, false fail을 줄이는 방향이 유효함을 확인했다. 다음 단계는 설계 그 자체보다, 이 numeric evaluator를 aggregate와 해석 규칙에 제대로 반영하는 것이다.

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

### 1. Answer generation 원칙 정리와 rule inventory 정리

목표:

- 최근 answer-stage rule을 `유지 / 실험용 / 제거 후보`로 분류
- benchmark score와 운영 기본값 최적화를 분리
- answer generation 구조를 “새 내용을 쓰는 단계”가 아니라 “evidence를 질문 범위에 맞게 압축하는 단계”로 재정의

산출물:

- `docs/answer_generation_principles.md`
- 최근 rule inventory와 각 rule의 목적/부작용 메모

### 2. Query-stage abstention 분석

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

### 3. NAVER business overview retrieval 개선

현재 관찰:

- NAVER는 parser 보정 후에도 `business_overview_001`이 계속 miss된다.
- 상위 검색 결과가 `I. 회사의 개요`, `IV. 이사의 경영진단 및 분석의견`, `III. 재무에 관한 사항` 쪽으로 편중된다.

목표:

- NAVER에서 실제 사업 설명이 들어 있는 section 우선순위를 다시 정의
- rerank나 section bias 조정이 필요한지 확인
- 다음 run에서 `business_overview_001` miss를 먼저 줄이기

### 4. Missing-information 안정화

현재 관찰:

- NAVER에서 `신규사업 및 중단사업` 질문은 smoke 단계에서 hallucination으로 잡힌다.

목표:

- missing-information prompt / 판정 기준을 점검
- partial limitation과 true missing response를 더 분명히 구분
- “근거 없음” 응답이 citation 없이 단정으로 흐르지 않도록 제어

### 5. 평가 보강

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

### 6. Numeric evaluator 분리

목표:

- `numeric_fact`를 일반 서술형 judge 하나로 채점하지 않기
- 값 동치성, evidence grounding, retrieval support를 분리해서 보기
- false fail을 줄이되, 불확실한 케이스는 `uncertain`으로 남기기

방향:

- `Numeric Extractor`
- `Numeric Equivalence Checker`
- `Grounding Judge`
- `Retrieval Support Check`
- `Conflict Resolver`

참조:

- [numeric_evaluation_architecture.md](docs/numeric_evaluation_architecture.md)

현재 상태:

- `Numeric Extractor`, `Numeric Equivalence Checker`, `Grounding Judge`, `Retrieval Support Check`, `Conflict Resolver`가 `numeric_fact` path에 1차 구현됨
- `results.json`, `review.csv`, `review.md`에 `numeric_equivalence`, `numeric_grounding`, `numeric_retrieval_support`, `numeric_final_judgement`, `numeric_confidence`가 기록됨
- 다음 단계는 이 값을 aggregate / summary / 승자 해석에 더 직접 반영하는 것

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

- 최근 hardcoded answer-stage rule이 어떤 역할을 하는지 문서로 설명 가능할 것
- benchmark-only 최적화와 운영 기본값 후보를 구분하는 기준이 문서에 명시될 것
- NAVER `business_overview_001` miss 원인을 retrieval / reasoning 중 어디인지 분리
- numeric / risk / R&D abstention이 반복되는 대표 케이스 3개 이상을 설명 가능하게 정리
- missing-information hallucination을 유발하는 대표 패턴을 재현 가능하게 문서화
- 위 수정 후 `dev_fast` 기준 재실험으로 적어도 1개 failure type이 줄어드는지 확인
- numeric 질문의 false fail을 answer generation 문제와 evaluator 문제로 분리해 설명 가능할 것

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

1. answer generation 원칙과 rule inventory 문서화
2. query-stage abstention을 유발하는 evidence / analyze 단계 패턴 점검
3. NAVER business overview retrieval 실패 원인 정리
4. missing-information hallucination 억제
5. numeric evaluator aggregate / reporting 반영
6. 그 다음에 `dev_fast` 기준 재실험
7. 실패 유형이 줄어든 뒤에만 release generalization 재실행
