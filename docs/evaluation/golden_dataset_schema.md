# Golden Dataset Schema v1

이 문서는 단일 문서 benchmark용 Golden Dataset의 권장 스키마를 정의한다.

현재 기준 문서:

- `삼성전자 2024 사업보고서`

권장 파일 경로:

- `benchmarks/golden/samsung_2024_v1.json`

## 설계 원칙

- 질문은 단일 문서에 대해만 작성한다.
- 정답은 `ground_truth_answer` 한 줄로 끝내지 않는다.
- retrieval 평가와 generation 평가가 모두 가능하도록
  - context id
  - evidence quote
  를 함께 저장한다.
- 숫자 질문은 `numeric_constraints`를 따로 둔다.
- 문서에 없는 질문은 `expected_refusal = true`로 명시한다.

## 필드 정의

### 필수 필드

- `query_id`
  - 데이터셋 내 고유 질문 ID
- `document_id`
  - 기준 문서 식별자
- `company`
  - 단일 문서의 회사명
- `year`
  - 단일 문서 기준 연도
- `category`
  - 질문 taxonomy
- `question`
  - 사용자 질문 원문
- `ground_truth_answer`
  - 사람이 읽는 기준 정답
- `expected_sections`
  - retrieval이 맞아야 하는 섹션/문맥 단위 목록
- `ground_truth_context_ids`
  - 정답이 근거하는 context ID 목록
- `ground_truth_evidence_quotes`
  - 실제 근거 quote 목록
- `required_entities`
  - 질문을 풀기 위해 반드시 포함되어야 하는 엔티티/핵심 키워드
- `answer_type`
  - `numeric`, `boolean`, `span`, `list`, `summary`, `refusal` 중 하나
- `expected_refusal`
  - 문서에 근거가 없어 답변을 거절해야 하는지 여부
- `reasoning_steps`
  - 정답에 도달하기 위한 최소 단계

### 선택 필드

- `numeric_constraints`
  - 숫자 질문 전용 제약
- `aliases`
  - 엔티티 별칭
- `verification_status`
  - `draft`, `verified`, `needs_review`
- `notes`
  - annotator 메모

## category 값

- `single-hop-fact`
- `multi-hop-comparison`
- `multi-hop-calculation`
- `synthesis-abstract`
- `adversarial-out-of-domain`

## answer_type 값

- `numeric`
- `boolean`
- `span`
- `list`
- `summary`
- `refusal`

## numeric_constraints 예시

```json
{
  "unit": "억원",
  "tolerance": 0.0,
  "allow_unit_conversion": true
}
```

권장 의미:

- `unit`
  - canonical 비교 기준 단위
- `tolerance`
  - 허용 오차율 또는 절대 오차
- `allow_unit_conversion`
  - `300조 8,709억원`과 `300,870,903 백만원`처럼 단위 변환을 허용할지 여부

## 전체 스키마 예시

```json
{
  "query_id": "q_004",
  "document_id": "samsung_2024_business_report",
  "company": "삼성전자",
  "year": 2024,
  "category": "multi-hop-calculation",
  "question": "2024년 삼성전자 DX부문 매출은 DS부문 매출보다 얼마나 큰가?",
  "ground_truth_answer": "DX부문 매출은 174조 8,877억원, DS부문은 111조 660억원으로 DX가 63조 8,217억원 더 크다.",
  "expected_sections": [
    "매출 및 수주상황"
  ],
  "ground_truth_context_ids": [
    "sec_2_2_sales_mix"
  ],
  "ground_truth_evidence_quotes": [
    "2024년 매출은 DX 부문이 174조 8,877억원(58.1%), DS 부문이 111조 660억원(36.9%)이며..."
  ],
  "required_entities": [
    "DX부문",
    "DS부문",
    "매출",
    "차이"
  ],
  "answer_type": "numeric",
  "expected_refusal": false,
  "numeric_constraints": {
    "unit": "억원",
    "tolerance": 0.0,
    "allow_unit_conversion": true
  },
  "reasoning_steps": [
    "DX부문 매출 추출",
    "DS부문 매출 추출",
    "차이 계산"
  ],
  "aliases": {
    "DX부문": ["DX", "Device eXperience"],
    "DS부문": ["DS", "Device Solutions"]
  },
  "verification_status": "verified",
  "notes": "단일 표에서 추출 후 계산하는 대표 multi-hop calculation 문항"
}
```

## 평가 연결 방식

### Retrieval

아래 필드를 사용한다.

- `ground_truth_context_ids`
- `required_entities`

지표 예:

- `hit@k`
- `ndcg@k`
- `context_precision@k`
- `entity_coverage`

### Generation

아래 필드를 사용한다.

- `ground_truth_answer`
- `ground_truth_evidence_quotes`
- `reasoning_steps`

지표 예:

- `faithfulness`
- `answer_relevance`
- `completeness`

### Domain-specific

아래 필드를 사용한다.

- `numeric_constraints`
- `expected_refusal`

지표 예:

- `numeric_equivalence`
- `absolute_error_rate`
- `calculation_correctness`
- `refusal_accuracy`

## annotation 가이드

- `single-hop-fact`
  - 문서 내 한 곳에서 직접 답 가능해야 한다
- `multi-hop-comparison`
  - 최소 두 항목 비교가 필요해야 한다
- `multi-hop-calculation`
  - 추출 후 산술 연산이 필요해야 한다
- `synthesis-abstract`
  - 여러 문장 또는 섹션을 압축해 서술해야 한다
- `adversarial-out-of-domain`
  - 문서에 답이 없거나 문서 범위 밖이어야 한다

## v1 추천 운영 방식

- 먼저 `20~30개` 질문으로 시작
- 모든 질문은 `verification_status = draft`로 시작 가능
- 최소 1회 수동 검수 후 `verified`로 승격
- 이후 category별로 균형 있게 확장
