# Evidence Schema Design

이 문서는 현재 문자열 bullet 중심의 evidence 표현을 **구조화된 evidence schema**로 바꾸기 위한 최소 설계를 정리한다.

목표는 다음과 같다.

- answer generation이 “새 답을 쓰는 단계”보다 “근거를 압축하는 단계”에 가까워지게 만들기
- faithfulness 디버깅을 쉽게 만들기
- benchmark / canonical eval dataset / reviewer artifact가 같은 근거 단위를 공유하게 만들기
- 최근 늘어난 hardcoded answer rule을 줄일 기반을 마련하기

## 왜 필요한가

현재 구조의 핵심 한계:

- evidence가 사실상 bullet 문자열이라, `_analyze`가 다시 해석하고 재서술해야 한다
- 어떤 claim이 실제 근거인지, 어떤 표현이 answer 단계에서 새로 생겼는지 추적이 어렵다
- unsupported sentence 제거, numeric drift 탐지, risk taxonomy drift 탐지 같은 validation을 일반 규칙으로 구현하기 어렵다
- canonical eval dataset은 이미 `answer_key + evidence quote` 구조인데, runtime evidence는 같은 수준으로 구조화되어 있지 않다

즉 지금은 **retrieval / evidence / answer / evaluation이 서로 다른 표현 단위를 쓰고 있는 상태**다.

## 설계 원칙

### 1. evidence는 문자열이 아니라 데이터여야 한다

최소한 아래 질문에 답할 수 있어야 한다.

- 이 claim은 정확히 무엇인가?
- 어떤 quote에서 왔는가?
- 어느 section / chunk / parent에서 왔는가?
- 질문과의 관련도는 어느 정도인가?
- 이 claim에서 answer가 사용해도 되는 용어는 무엇인가?

### 2. answer 단계는 이 schema를 조합/압축만 해야 한다

answer generation은:

- 새로운 taxonomy를 만들거나
- 배경 설명을 확장하거나
- 근거 표현을 임의로 재구성하는 단계가 아니라

**selected evidence를 질문 범위에 맞게 압축하는 단계**여야 한다.

### 3. validator는 schema를 기반으로 동작해야 한다

validator가 보기 좋은 단위:

- `claim`
- `quote_span`
- `allowed_terms`
- `support_level`
- `source_anchor`

이 정보가 있어야:

- unsupported sentence 제거
- 숫자/단위 drift 탐지
- risk category drift 탐지

를 일반 규칙으로 구현할 수 있다.

## 최소 schema 제안

권장 최소 schema:

```json
{
  "evidence_id": "ev_0001",
  "claim": "DX 부문은 TV, 모니터, 냉장고, 세탁기 등을 생산·판매한다.",
  "quote_span": "Set 사업은 DX(Device eXperience) 부문이 TV를 비롯하여 모니터, 냉장고, 세탁기...",
  "source_anchor": "[삼성전자 | 2024 | II. 사업의 내용 > 1. 사업의 개요]",
  "support_level": "direct",
  "question_relevance": "high",
  "allowed_terms": ["DX", "TV", "모니터", "냉장고", "세탁기"],
  "metadata": {
    "company": "삼성전자",
    "year": 2024,
    "report_type": "사업보고서",
    "section": "사업개요",
    "section_path": "II. 사업의 내용 > 1. 사업의 개요",
    "block_type": "paragraph",
    "chunk_uid": "samsung_2024_...",
    "parent_id": "parent_..."
  }
}
```

## 필드 설명

### 필수 필드

- `evidence_id`
  - 각 evidence의 stable identifier
- `claim`
  - answer에서 바로 사용할 수 있을 정도로 짧은 근거 진술
- `quote_span`
  - 실제 원문에서 발췌한 근거 스팬
- `source_anchor`
  - 사람이 읽는 출처 앵커
- `support_level`
  - `direct | partial | context`

### 강력 권장 필드

- `question_relevance`
  - `high | medium | low`
  - answer 압축 시 우선순위 결정에 도움
- `allowed_terms`
  - 이 evidence에서 answer가 써도 되는 핵심 용어
  - 특히 `risk`, `numeric_fact`에서 유용
- `metadata`
  - section / block / chunk 식별용

### 선택 필드

- `normalized_value`
  - numeric_fact에서만 사용 가능
  - 예: `300870903`
- `display_value`
  - 예: `300조 8,709억원`
- `unit`
  - 예: `억원`, `백만원`, `%`
- `row_header`
  - table evidence일 때 row label
- `column_header`
  - table evidence일 때 column label

## 현재 `EvidenceItem`에서의 확장 방향

현재 코드의 `EvidenceItem`:

- `source_anchor`
- `claim`
- `support_level`

즉 현재도 최소 뼈대는 이미 있다. 다음 확장이 자연스럽다.

### Phase 1

`EvidenceItem`에 아래 필드 추가:

- `quote_span: str`
- `question_relevance: Literal["high", "medium", "low"]`
- `allowed_terms: List[str]`
- `metadata: Dict[str, Any]`

이 단계에서는 기존 prompt / benchmark 흐름을 크게 깨지 않으면서 구조화 정도만 올린다.

### Phase 2

numeric 전용 선택 필드 추가:

- `display_value`
- `normalized_value`
- `unit`

이 단계부터 numeric drift 검사가 쉬워진다.

### Phase 3

table evidence 보강:

- `row_header`
- `column_header`
- `cell_span`

이 단계부터 표 질의에 더 강해진다.

## 질문 유형별 사용 방식

### numeric_fact

핵심:

- answer는 `display_value` 또는 `quote_span`의 숫자 표현을 그대로 사용
- `normalized_value`는 비교/검증용으로만 사용
- 다른 표현으로 변환하지 않음

효과:

- `300조 8,709억원` vs `300,870,903 백만원` 같은 drift를 더 명시적으로 다룰 수 있다

### business_overview

핵심:

- `claim`과 `allowed_terms`를 바탕으로 필요한 항목만 선택
- `question_relevance = high` 중심으로 압축
- 배경 설명이나 예시 법인명은 별도 evidence가 없으면 추가하지 않음

효과:

- 과한 확장 설명을 줄일 수 있다

### risk

핵심:

- `allowed_terms`에 없는 리스크 카테고리명 사용 금지
- `support_level = direct`인 항목을 우선
- answer에서 taxonomy를 새로 구성하지 않음

효과:

- risk hallucination과 category drift를 줄일 수 있다

## answer generation에 어떻게 연결할까

목표 구조:

1. retrieve
2. build_structured_evidence
3. select_relevant_evidence
4. compress_answer
5. validate_answer

여기서 중요한 건:

- `compress_answer`는 raw context를 직접 쓰지 않고
- **selected evidence objects**만 본다는 점이다.

### compress 단계 예시

입력:

- `query`
- `query_type`
- `selected_evidence[]`

출력:

- final answer

규칙:

- selected evidence 밖 내용 금지
- `allowed_terms` 밖 taxonomy 생성 금지
- `question_relevance = high` 위주

## validator에 어떻게 연결할까

validator는 아래를 검사할 수 있다.

### 1. unsupported sentence check

- answer의 각 문장이 어떤 `evidence_id`에 의해 지지되는지 매핑
- 매핑 안 되는 문장은 제거 후보

### 2. numeric drift check

- answer에 등장한 수치가 `display_value` / `normalized_value`와 맞는지 확인
- 단위 변환 여부 감지

### 3. taxonomy drift check

- `risk`에서 answer에 등장한 카테고리명이 `allowed_terms` 집합 밖인지 확인

## benchmark / reviewer artifact에 어떻게 연결할까

이 schema를 쓰면 reviewer artifact도 더 강해진다.

현재 reviewer artifact:

- question
- answer_key
- evidence quote
- actual answer

향후 reviewer artifact:

- question
- selected evidence ids
- claim
- quote_span
- support_level
- actual answer
- unsupported sentence 여부

즉 사람이 “왜 이 답이 나왔는지”를 훨씬 빠르게 볼 수 있다.

## 마이그레이션 전략

### Step 1. Non-breaking 확장

- `EvidenceItem` 확장
- 기존 bullet 직렬화는 유지
- 내부적으로만 structured field를 추가

### Step 2. Benchmark logging 확장

- `results.json`, `review.csv/md`에 structured evidence 일부 기록
- reviewer artifact 개선

### Step 3. `_analyze` 입력 전환

- bullet 문자열 대신 selected evidence object를 사용
- answer 생성 프롬프트 단순화

### Step 4. Validator 도입

- unsupported claim / numeric drift / taxonomy drift 검사

## 현재 결론

evidence schema를 도입하면 좋은 점은 명확하다.

1. answer generation이 더 구조화된다
2. faithfulness 디버깅이 쉬워진다
3. hardcoded prompt rule을 줄일 수 있다
4. benchmark / evaluator / reviewer artifact가 같은 단위를 공유한다
5. 이후 document-structure graph 리팩터링의 기반이 된다

즉 evidence schema는 단순한 타입 확장이 아니라, **retrieval 이후 answer generation 계층을 더 principled하게 재설계하기 위한 출발점**이다.
