# Query Routing Rearchitecture

이 문서는 현재 `financial_graph.py`의 query routing 병목과, 다음 단계에서 도입할 routing 재설계 방향을 정리한다.

현재 상태:

- `routing cascade v1` 구현 완료
  - `intent + format_preference` state 분리
  - semantic router fast-path
  - few-shot LLM fallback
- `routing cascade v1.5` 구현 완료
  - runtime router를 `src/routing/query_router.py`로 분리
  - routing 스키마를 `src/routing/types.py`로 분리
  - calibration script가 shared routing helper를 재사용
- 현재 남은 일은 구현 자체보다
  - fallback 로그를 canonical query 세트로 흡수
  - 라우터 전용 테스트 보강
  - threshold / guard 재보정
  이다

## 배경

현재 query routing은 아래 두 단계를 LLM에 맡긴다.

1. `_classify_query`
   - `query_type`를 `numeric_fact / business_overview / risk / comparison / trend / qa` 중 하나로 분류
2. `_extract_entities`
   - `companies`
   - `years`
   - `topic`
   - `section_filter`
   를 추출

이 구조는 간단하고 유연하지만, 최근 실험에서 다음 문제가 드러났다.

- `risk` 질문이 `numeric_fact`로 오분류될 수 있다
- `business_overview` 질문도 zero-shot 분류가 흔들릴 수 있다
- `query_type` 하나가
  - 질문의 의도
  - retrieval 시 표/문단 선호
  - section bias
  를 동시에 결정해 충돌을 만든다

즉 현재 병목은 retrieval 자체보다 **query routing variance**에 더 가깝다.

## 최근 확인된 사실

### 1. `business_overview` table penalty는 구조적 충돌이었다

이전 구조에서는:

- `_classify_query` 프롬프트가 일부 수치 질문을 `business_overview`로 보내려 했고
- `_rerank_docs`는 `business_overview`면 table에 `-0.08` 페널티를 줬다

그래서 "각 부문별 매출 비중"처럼 표가 정답인 overview-ish 질문이 불리해질 수 있었다.

이 충돌은 최근 수정으로 완화했다.

- `business_overview`에 대한 table penalty 제거
- `_classify_query` 프롬프트에서
  - `매출 비중`
  - `규모`
  같은 수치형 질문은 `numeric_fact`로 가도록 문구 수정

하지만 이것만으로는 충분하지 않았다.

### 2. 현재 더 큰 문제는 classification variance다

최근 직접 실행에서 같은 store를 재사용해 `contextual_selective_v2_prefix_2500_320`를 확인했을 때:

- `주요 재무 리스크는 무엇인가요?`
  - `query_type = numeric_fact`
- `회사가 영위하는 주요 사업은 무엇인가요?`
  - `query_type = numeric_fact`

같은 잘못된 분류가 발생했다.

즉 문제는 이제 reranking 이전에:

- zero-shot LLM classifier가 흔들리고
- 뒤의 extract 단계도 같이 틀어질 수 있다는 점이다

## 핵심 설계 판단

### 1. `query_type` 하나에 너무 많은 의미를 실지 않는다

장기적으로는 아래 두 축을 분리하는 것이 맞다.

- `intent`
  - `numeric_fact`
  - `business_overview`
  - `risk`
  - `comparison`
  - `trend`
  - `qa`
- `format_preference`
  - `table`
  - `paragraph`
  - `mixed`

예:

- `각 부문별 매출 비중은 어떻게 되나요?`
  - `intent = numeric_fact`
  - `format_preference = table`
- `회사가 영위하는 주요 사업은 무엇인가요?`
  - `intent = business_overview`
  - `format_preference = mixed`

이 분리가 있어야 retrieval bias와 block type 보정이 훨씬 설명 가능해진다.

### 2. routing은 rule-based 확대보다 ML/AI-native 방식으로 재설계한다

현재 결론은 다음과 같다.

- keyword if-else를 계속 늘리는 방식은 피한다
- 가장 현실적인 다음 단계는:
  - `few-shot LLM classifier`
  - `semantic router`
  를 함께 준비하는 것이다

### 3. 초기 운영 구조는 병렬보다는 직렬 cascade가 유력하다

최종 목표는 다음과 같은 cascade다.

1. `Semantic Router`
   - canonical query embedding 기반 fast path
   - 확실한 질문은 여기서 즉시 분류
2. `Few-shot LLM classifier`
   - semantic score가 낮거나 margin이 작을 때만 slow path로 호출

다만 초기 고도화 단계에서는

- semantic router score
- few-shot LLM 분류 결과

를 함께 관찰하면서 threshold를 튜닝할 필요가 있다.

## 다음 단계 준비물

다음 구현 전 준비물은 아래 4가지다.

### 1. `QueryClassification` 스키마 변경안

현재:

- `query_type`

목표:

- `intent`
- `format_preference`
- 필요 시 `confidence`
- 필요 시 `routing_source`

### 2. Few-shot 프롬프트 예제 세트

현재 가장 자주 흔들린 edge case를 few-shot으로 고정한다.

최소 포함 예:

- `주요 재무 리스크는 무엇인가요?` -> `intent=risk`
- `회사가 영위하는 주요 사업은 무엇인가요?` -> `intent=business_overview`
- `각 부문별 매출 비중은 어떻게 되나요?` -> `intent=numeric_fact`
- `DX와 DS 매출 차이는?` -> `intent=comparison`
- `최근 3년 영업이익 추이는?` -> `intent=trend`

### 3. Semantic Router용 canonical query 세트

클래스별로 10~15개 수준의 대표 질문을 초기 세트로 만든다.

초기 목적:

- fast path routing
- top-1 / top-2 similarity와 margin 측정
- LLM fallback 비율 측정

### 4. 최소 변경 코드 적용 방안

`financial_graph.py`에서 가장 먼저 바꿀 지점은 `_classify_query`다.

목표 구조:

1. semantic router가 top-1 class와 similarity score를 반환
2. score가 충분히 높으면 그대로 사용
3. 애매하면 few-shot LLM classifier fallback
4. 최종 결과는 `intent`, `format_preference`를 함께 state에 기록

## 현재 준비된 문서 / 자산

- 스키마 초안:
  - [query_routing_schema.md](query_routing_schema.md)
- few-shot 예제 세트:
  - [query_routing_examples.md](query_routing_examples.md)
- semantic router용 canonical queries:
  - [benchmarks/golden/query_routing_canonical_v1.json](../benchmarks/golden/query_routing_canonical_v1.json)
- held-out routing 검증셋:
  - [benchmarks/golden/query_routing_eval_v1.json](../benchmarks/golden/query_routing_eval_v1.json)
- calibration 스크립트:
  - [src/ops/calibrate_query_router.py](../src/ops/calibrate_query_router.py)

## 현재 구현 상태

현재 시스템에는 아래가 이미 들어가 있다.

- `intent + format_preference` state 분리
- semantic fast-path
- few-shot LLM fallback
- routing metadata (`routing_source`, `routing_confidence`, `routing_scores`) 기록
- ambiguity guard
- 독립 routing 모듈
  - `src/routing/query_router.py`
  - `src/routing/types.py`
  - `src/routing/__init__.py`

또한 `2026-04-24` 기준으로 아래 보정 흐름을 거쳤다.

1. held-out calibration으로 전역 threshold 완화 시도
   - `0.86 / 0.04 -> 0.76 / 0.04`
2. 실제 benchmark에서 `risk_analysis_001` false positive 확인
3. risk canonical query 보강
4. confusion pair dynamic margin 도입
   - `business_overview ↔ risk`
   - `business_overview ↔ numeric_fact`

결론:

- semantic router는 전역 threshold만으로 운영하지 않는다
- ambiguity가 큰 혼동쌍은 별도 safety guard를 둔다
- routing은 이제 `financial_graph.py` 내부 보조 로직이 아니라
  - 독립 코드
  - 독립 스키마
  - 독립 calibration 자산
  을 가진 코어 모듈로 관리한다
- fallback 로그를 canonical query 세트로 다시 흡수하는 운영이 중요하다

## 성공 기준

다음 단계 성공 기준은 아래와 같다.

- `risk` / `business_overview` 질문이 `numeric_fact`로 흔들리는 사례를 재현 가능하게 줄일 것
- block type penalty가 intent와 format preference를 혼동하지 않을 것
- canonical query와 few-shot 예제가 문서로 먼저 정리되어 구현 전에 검토 가능할 것
- routing 변경 이후에도 retrieval / generation 실험 해석이 더 단순해질 것

추가 성공 기준:

- 전역 threshold 조정이 아니라도 confusion pair guard로 false positive를 안정적으로 막을 것
- `results.json`, `review.md`, `review.csv`만 보고도
  - semantic fast-path였는지
  - llm fallback이었는지
  - 어떤 점수 분포였는지
  를 추적할 수 있을 것

## Intent Taxonomy 메모

현재 `6-intent` 구조는 당분간 유지한다.

- `numeric_fact`
- `business_overview`
- `risk`
- `comparison`
- `trend`
- `qa`

이 분류를 유지하는 이유는, 각 intent가 후속 파이프라인 행동과 비교적 직접적으로 연결되기 때문이다.

- `numeric_fact`
  - 단일 수치 조회
  - numeric evaluator와 가장 강하게 연결
- `business_overview`
  - 사업 내용 / 제품 / 서비스 / 고객군 / 사업 구조 설명
  - paragraph 또는 mixed evidence 조합과 잘 연결
- `risk`
  - 위험관리 / 파생거래 / 재무위험 설명
  - `business_overview`와 문서 위치, 서술 방식이 달라 독립 intent로 유지 가치가 큼
- `comparison`
  - 두 항목 비교
  - 향후 계산 노드나 structured reasoning과 연결 가능
- `trend`
  - 시계열 변화 / 전년 대비 / 성장 흐름
  - comparison과 마찬가지로 계산 / 재배열 성격이 강함
- `qa`
  - fallback / 일반 사실 질의

즉 현재 6-intent는 “질문 분류”이면서 동시에 “다음 노드를 무엇으로 열 것인가”와 연결되는 실무적 분류 체계로 본다.

## 장기 확장 후보 메모

지금 당장 intent를 늘리지는 않지만, 아래 3가지는 후속 확장 후보로 기억해 둔다.

### 1. `comparison` + `trend` -> `complex_numeric`

장기적으로는 두 intent를 묶어 `complex_numeric` 또는 `calculation`으로 재설계할 수 있다.

이유:

- 둘 다 검색 후 단순 인용이 아니라
  - 비교
  - 차이 계산
  - 성장률 계산
  - 시계열 재배열
  이 필요할 수 있음
- 라우터 입장에서는 `comparison`과 `trend`의 경계가 애매할 수 있음

다만 지금 단계에서는:

- benchmark와 라우팅 자산이 이미 6-intent 기준으로 정리돼 있고
- downstream도 아직 `complex_numeric` 전용 노드로 분화되지 않았으므로

즉시 통합하지는 않는다.

### 2. `governance` / `corporate_info`

향후 DART 특화 질문이 늘어나면 `qa`에서 아래 축을 독립시킬 수 있다.

- 이사회
- 최대주주
- 배당
- 임원 / 대표이사
- 감사 / 내부통제

이유:

- DART 사용자의 실제 질문 비중이 높고
- `VII. 주주에 관한 사항`, `VIII. 임원 및 직원 등에 관한 사항` 등 특정 섹션 bias를 따로 줄 가치가 큼

현재는 `qa`로 유지하되, canonical query와 benchmark에서 이 축이 반복되면 독립 intent로 승격한다.

### 3. `r_and_d`

연구개발은 기술 기업 분석에서 중요도가 높아 장기적으로 독립 intent 후보가 될 수 있다.

고려 기준:

- `business_overview` 하위 설명으로 보는 것이 더 자연스러운가
- 아니면 `연구개발 조직 / 실적 / 투자 추이`처럼 retrieval, extraction, evaluation이 따로 필요한가

현재는:

- 수치면 `numeric_fact` / `trend`
- 서술이면 `business_overview`

로 처리하고, 추후 질문셋이 늘어나면 독립 intent 여부를 재검토한다.

## 현재 판단

- 지금 단계에서는 **6-intent 유지**가 맞다
- 이유는 taxonomy를 더 늘리기보다
  - canonical query 품질
  - confusion pair 회귀 테스트
  - fallback 로그 플라이휠
  을 안정화하는 것이 우선이기 때문이다
- 위 확장 후보는 모두 **기억해둘 설계 메모**로 관리하고, 실제 승격은
  - 질문셋 분포
  - confusion pattern
  - downstream 분기 필요성
  이 명확해질 때 한다

## Canonical Query Tuning Note

`query_routing_canonical_v2`는 현재 기준으로 충분히 운영 가능한 상태지만, 향후 `comparison`과 `trend` 사이에서 semantic overlap이 생길 수 있다는 점을 기억해 둔다.

대표 예:

- `comparison`
  - `올해와 작년의 영업이익을 비교해줘.`
- `trend`
  - `최근 연도별 영업이익 변화를 보여줘.`

이 둘은 임베딩 공간에서 가깝게 놓일 수 있다.

따라서 실제 오분류가 발생할 경우 canonical query를 아래 기준으로 더 뾰족하게 다듬는다.

- `comparison`
  - **주체 간 비교**에 무게를 싣는다
  - 예:
    - `DX와 DS`
    - `국내와 해외`
    - `삼성전자와 SK하이닉스`
    - `연결 기준과 별도 기준`
- `trend`
  - **시계열 흐름**에 무게를 싣는다
  - 예:
    - `최근 3년`
    - `최근 몇 년간`
    - `연도별`
    - `흐름`
    - `추세`

즉 오분류가 생기면 먼저 알고리즘을 바꾸기보다 canonical query 문장을 이 기준으로 더 선명하게 클렌징한다.

## Fallback Anti-pattern Patch

`canonical_v2`를 runtime 기본값으로 바로 올리기 전에, 실제 `dev_fast_focus`에서는 semantic router보다 **LLM fallback few-shot**이 더 큰 오분류 원인임이 드러났다.

대표 사례:

- `삼성전자의 연결대상 종속기업은 총 몇 개인가요?`
- `회사의 임직원 수는 총 몇 명인가요?`

이 질문들은 `"몇 개"`, `"몇 명"` 때문에 fallback LLM이 `numeric_fact`로 과잉 분류하기 쉬웠다.

대응:

- fallback few-shot에 anti-pattern 예제 추가
- confusion set을 semantic-only가 아니라 **최종 routing 결과 기준**으로 확장
- `semantic_top1`과 `final_intent`를 분리해서 회귀 테스트

현재 기준:

- canonical query 클렌징은 계속 중요하지만
- 실제 라우팅 품질은
  - `semantic router`
  - `ambiguity guard`
  - `few-shot fallback anti-pattern patch`
  의 조합으로 봐야 한다

## Runtime Default Note

현재는 `query_routing_canonical_v2`를 참고 자산으로 유지하고, runtime 기본 canonical은 `v1`을 유지한다.

이유:

- 작은 confusion set에서는 `v2`가 유효했지만
- 실제 `dev_fast_focus`에서는 `business_overview_003` 같은 fallback misroute가 남았기 때문이다

즉:

- `v2`는 계속 확장/클렌징 대상으로 유지
- runtime 기본값 승격은 더 넓은 held-out routing eval이나 실제 benchmark 개선이 확인된 뒤에만 수행
