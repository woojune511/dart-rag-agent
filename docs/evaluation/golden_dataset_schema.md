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
- `accepted_calculation_variants`
  - 같은 질문에 둘 이상의 source-backed 계산 표현이 정당할 때 쓰는 atomic variant 목록
  - 각 항목은 `id`, `answer_key`, `expected_operands`, `expected_operation`,
    `expected_calculation_result`를 함께 가져야 한다
  - evaluator는 서로 다른 항목의 operand/result를 섞어 채점하지 않는다

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

## accepted_calculation_variants 예시

```json
[
  {
    "id": "note_precise",
    "answer_key": "기초 343백만원, 기말 380백만원, 차이 37백만원",
    "expected_operands": [
      {
        "label": "기말",
        "raw_value": "380",
        "raw_unit": "백만원",
        "source_anchor_contains": "재무제표 주석",
        "consolidation_scope": "consolidated"
      },
      {
        "label": "기초",
        "raw_value": "343",
        "raw_unit": "백만원",
        "source_anchor_contains": "재무제표 주석",
        "consolidation_scope": "consolidated"
      }
    ],
    "expected_operation": "difference",
    "expected_calculation_result": {
      "label": "차이",
      "raw_value": "37",
      "raw_unit": "백만원",
      "operation_family": "difference",
      "source_anchor_contains": "재무제표 주석"
    }
  }
]
```

`source_anchor_contains`는 문자열 또는 허용 가능한 source 표현 목록이다. 필요하면
operand에 `strict_label`, `statement_type`, `consolidation_scope`,
`table_source_id_contains`, `source_row_id`를 추가할 수 있다. 이 필드는 runtime
라우팅 입력이 아니라 evaluator-only 정답 계약이다.

## accepted_answer_variants 계약 (active, evaluator-only)

여러 direct output이 하나의 답을 이루고 연결/별도 같은 source basis별 완전한
묶음이 각각 정당할 수 있을 때를 위한 필드다. Production loader와 evaluator가
strict하게 소비하지만 runtime agent의 routing/retrieval/selection 입력은 아니다.
현재 curated dataset에는 아직 등록하지 않았고,
`tests/fixtures/multi_output_answer_variants.json`은 합성 contract fixture만 제공한다.

각 variant는 다음을 가져야 한다.

- 고유한 `id`
- 해당 source basis를 명시한 completeness용 `answer_key`
- 모든 required semantic output ID를 정확히 한 번 포함하는 `expected_outputs`
- 각 output의 `output_id`, `kind`, `label`, `subject`, `raw_value`, `raw_unit`,
  `normalized_unit`, `period`, `consolidation_scope`, `source_anchor_contains`

Variant matcher는 서로 다른 actual output을 각 expected output에 배정하고 하나의
variant 전체가 완전할 때만 성공한다. Canonical direct output은 immutable ID로
정확히 하나의 pre-supplementation operand에 결합되어야 하며 required output ID
집합도 정확히 같아야 한다. 다른 variant의 값/출처/기준 혼합, 누락/추가 output,
unknown scope, 동일값 wrong-row, invalid/ambiguous binding은 실패한다. 답변 숫자와
trace가 같은 유일 variant를 가리킬 때만 completeness reference가 해당
`answer_key`로 바뀌고, 그 외에는 canonical key를 쓴다. 이 계약은 기존 scalar
`accepted_calculation_variants`를 대체하거나 그 result-binding 규칙을 약화하지
않으며 score를 직접 승격하지 않는다. 실제 dataset variant는 별도 source review와
명시적 결정 뒤에만 추가할 수 있다.

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
