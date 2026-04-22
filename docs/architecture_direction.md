# Architecture Direction

이 문서는 현재 DART 공시 QA 시스템의 구조적 한계를 정리하고, 앞으로 어떤 방향으로 아키텍처를 바꾸는 것이 적절한지를 설명한다.

핵심 질문은 다음이다.

- 지금 문제를 해결하기 위해 full GraphRAG가 필요한가?
- multi-agent system으로 가는 것이 맞는가?
- 아니면 더 작고 구조적인 리팩터링이 먼저인가?

결론부터 말하면, **현재 단계에서는 full GraphRAG나 full multi-agent보다, document-structure graph + structured evidence + answer compression/validation 구조가 더 적합하다.**

추가로, 숫자 질문(`numeric_fact`)의 평가는 일반 서술형 `faithfulness` judge 하나에 의존하지 않고, 별도의 **parallel numeric evaluators + resolver** 구조로 분리하는 것이 바람직하다. 자세한 설계는 [numeric_evaluation_architecture.md](numeric_evaluation_architecture.md)를 참고한다.

## 현재 구조

현재 파이프라인은 대략 다음과 같다.

1. DART XML 파싱
2. structure-first chunking
3. hybrid retrieval
   - dense
   - BM25
   - RRF
4. evidence extraction
5. answer generation
6. citation formatting

이미 좋은 기반이 몇 가지 있다.

- parent-child retrieval
- section/path metadata
- table / paragraph block type
- evidence-first reasoning
- benchmark / canonical eval dataset

즉 완전히 밑바닥부터 새로 만드는 상황은 아니다.

## 현재의 핵심 문제

최근 실험 기준으로 보면, 문제의 중심은 다음과 같다.

### 1. Retrieval보다 generation 쪽이 더 흔들린다

- `hit@k`, `section_match_rate`, `context_recall`은 유지되는데
- `faithfulness`만 크게 흔들리는 케이스가 반복된다.

이건 “못 찾는 문제”보다 “찾은 근거보다 더 많이 말하는 문제”에 가깝다.

### 2. answer generation이 자유 서술에 너무 의존한다

- evidence는 있지만 최종 answer에서
  - taxonomy 재구성
  - 배경 확장
  - 예시 추가
  - 숫자 표현 drift
가 발생한다.

### 3. 최근 하드코딩은 local optimization 성격이 강하다

- query type별 section bias
- output style 강제
- 질문 표현 기반 추가 제약
- post-generation guard

이런 규칙은 일부 benchmark 문항에는 먹히지만, 다른 문항에서 새 부작용을 만들었다.

## 왜 full GraphRAG는 지금 과한가

GraphRAG가 특히 강한 경우는 아래와 같다.

- 여러 문서 간 entity 관계가 핵심일 때
- 복수 회사 / 복수 연도 / 복수 이벤트 연결이 중요할 때
- “누가 누구와 어떤 관계인지”를 추적해야 할 때

하지만 현재 주요 실패는 이쪽이 아니다.

- 현재는 entity relation missing보다
- answer synthesis over-generation이 더 큰 문제다.

또한 full GraphRAG는 새로운 복잡성을 만든다.

- entity extraction 오류
- relation extraction 오류
- graph maintenance 비용
- index / sync 복잡도
- evaluation 복잡도 증가

즉 지금 당장 full GraphRAG로 가면, 현재 문제를 해결하기 전에 새로운 실패면을 더 많이 만들 가능성이 크다.

## 왜 full multi-agent도 지금은 과한가

multi-agent system은 아래 장점이 있다.

- planner / retriever / writer / verifier 역할 분리
- 실패 원인 분리
- 각 단계의 독립 개선 가능

하지만 지금은 이미 LangGraph 기반 단계적 구조가 있다.

- classify
- extract
- retrieve
- evidence
- analyze
- cite

따라서 지금 필요한 것은 “여러 agent” 그 자체보다:

- 각 노드의 입출력을 더 구조화하고
- answer generation을 더 제약 가능하게 만들고
- validation을 별도 계층으로 분리하는 것

즉 **multi-agent화**보다 **structured pipeline화**가 우선이다.

## 추천 방향: Document-Structure Graph

full knowledge graph 대신 먼저 **document-structure graph**를 도입하는 것이 적절하다.

이 그래프는 공시 문서 내부 구조를 반영한다.

### 노드

- section
- chunk
- table
- paragraph
- note / footnote

### 엣지

- `parent_of`
- `child_of`
- `adjacent_to`
- `precedes`
- `describes_table`
- `belongs_to_section`
- `same_parent`

### 효과

- retrieval에서 단순 similarity 외에 구조적 이웃을 더 활용 가능
- table 질문에서 preceding paragraph를 안정적으로 결합 가능
- answer에서 “직접 근거”와 “배경 근거”를 더 명확히 구분 가능

현재 1차 구현은 full graph가 아니라 **retrieval 후 후처리 확장용 최소 구조 그래프**다.

- `parent_id` 기반 parent context
- 같은 `parent_id` 안에서의 `sibling_prev` / `sibling_next`
- parser가 이미 보존하던 `table_context`

즉 실험 목표는 "그래프 자체를 복잡하게 만드는 것"이 아니라, **plain 인덱싱 상태에서도 parent/sibling/table 주변 문맥을 retrieval 이후에 붙여서 contextual ingest의 일부 효과를 대체할 수 있는지**를 보는 것이다.

이건 현재 parent-child 구조의 자연스러운 확장이다.

## 추천 방향: Structured Evidence Schema

현재 evidence는 사실상 bullet 문자열에 가깝다.  
이걸 더 구조화하는 것이 핵심이다.

상세 스키마 초안은 [evidence_schema.md](evidence_schema.md)를 참고한다.

권장 스키마 예시는 다음과 같다.

```json
{
  "claim": "DX 부문은 TV, 모니터, 냉장고, 세탁기 등을 생산·판매한다.",
  "quote_span": "Set 사업은 DX(Device eXperience) 부문이 TV를 비롯하여...",
  "source_anchor": "[삼성전자 | 2024 | II. 사업의 내용 > 1. 사업의 개요]",
  "support_level": "direct",
  "allowed_terms": ["DX", "TV", "모니터", "냉장고", "세탁기"],
  "question_relevance": "high"
}
```

핵심은:

- answer가 free-form generation이 아니라
- 이 structured evidence를 **질문 범위에 맞게 압축하는 단계**가 되도록 만드는 것이다.

## 추천 방향: Answer Compression + Validator

현재 `_analyze`는 여전히 “답을 써라”에 가깝다.  
앞으로는 다음 두 단계로 나누는 것이 좋다.

### 1. Compression

- evidence 집합에서 질문에 필요한 claim만 선택
- claim을 짧게 정리
- 근거 범위를 넘는 확장 설명 금지

### 2. Validator

- unsupported sentence 제거
- risk taxonomy drift 탐지
- numeric format drift 탐지
- duplicated claim 제거

중요한 점은 validator가 “새 내용을 쓰는 단계”가 아니라는 것이다.
validator는 제거/축소만 해야 한다.

## 제안하는 목표 구조

```text
classify
  -> extract
  -> retrieve
  -> expand_via_structure_graph
  -> build_structured_evidence
  -> compress_answer
  -> validate_answer
  -> cite
```

기존 구조와의 차이는 다음이다.

- `retrieve` 뒤에 구조 그래프 기반 확장 계층 추가
- `evidence`는 bullet 생성이 아니라 structured object 생성
- `analyze`는 free-form generation이 아니라 compression
- validation은 별도 계층으로 분리

## 단계별 마이그레이션 계획

### Phase 1. Evidence schema 도입

범위:

- `EvidenceItem` 확장
- bullet 문자열 대신 structured payload 유지
- benchmark 결과에도 structured evidence를 기록

목표:

- answer generation과 evaluation이 같은 evidence 구조를 보게 만들기

### Phase 2. Answer compression 도입

범위:

- `_analyze`를 compression 중심으로 재작성
- category-specific prose rule을 줄이기
- 질문 범위 외 정보 제거를 일관된 상위 규칙으로 처리

목표:

- “더 많이 말하는 문제”를 구조적으로 줄이기

### Phase 3. Validator 계층 분리

범위:

- unsupported claim 제거
- numeric drift 탐지
- risk taxonomy drift 탐지

목표:

- generation prompt에 제약을 계속 쌓지 않고 후단에서 안정화

### Phase 4. Document-structure graph 확장

범위:

- parent-child 외에 adjacency / table-context link 추가
- retrieval 후 graph expansion 실험

목표:

- full GraphRAG 없이도 문서 구조를 더 잘 활용

## 이번에 하지 않을 것

다음 항목은 지금 당장 범위에 넣지 않는다.

- full entity knowledge graph 구축
- company-wide graph database 도입
- 복수 independent agent를 orchestration하는 full multi-agent system
- 모든 benchmark 문항을 맞추기 위한 rule 추가

이들은 지금 문제 대비 비용이 크고, metric gaming 위험도 높다.

## 현재 결론

현재 시점에서 가장 적절한 구조 변화는:

1. full GraphRAG가 아니라 **document-structure graph**
2. full multi-agent가 아니라 **structured pipeline**
3. rule accumulation이 아니라 **structured evidence + compression + validation**

즉 앞으로의 방향은 “더 큰 시스템”이 아니라, **지금 있는 시스템을 더 설명 가능하고 구조화된 형태로 리팩터링하는 것**이다.
