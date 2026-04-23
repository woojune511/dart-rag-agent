# Query Routing Schema v1

이 문서는 query routing 재설계의 첫 단계로, `intent`와 `format_preference`를 분리한 스키마 초안을 정리한다.

## 목표

현재 `query_type` 하나가 동시에 아래를 결정한다.

- 질문 의도
- retrieval 시 표/문단 선호
- section bias 해석

이 구조는 다음 문제를 만든다.

- `business_overview`가 표를 필요로 하는 질문에서도 table penalty를 받을 수 있음
- `risk` / `business_overview` / `numeric_fact`가 서로 흔들릴 때 downstream 정책도 같이 흔들림

그래서 다음 단계에서는 질문의 **의도**와 필요한 **증거 형식**을 분리한다.

## 스키마 초안

### Intent

`intent`는 질문이 무엇을 알고 싶은지 나타낸다.

- `numeric_fact`
- `business_overview`
- `risk`
- `comparison`
- `trend`
- `qa`

### Format Preference

`format_preference`는 retrieval / reranking이 어떤 block type을 우선해야 하는지 나타낸다.

- `table`
- `paragraph`
- `mixed`

### Routing Source

초기 실험 단계에서는 routing이 어디서 결정되었는지 남기는 것이 유용하다.

- `semantic_fast_path`
- `llm_fallback`
- `manual_override`

## Pydantic 스키마 초안

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field


class QueryRoutingDecision(BaseModel):
    intent: Literal[
        "numeric_fact",
        "business_overview",
        "risk",
        "comparison",
        "trend",
        "qa",
    ] = Field(description="질문의 핵심 의도")

    format_preference: Literal["table", "paragraph", "mixed"] = Field(
        description="retrieval 및 reranking에서 선호할 evidence 형식"
    )

    confidence: Optional[float] = Field(
        default=None,
        description="0.0~1.0 범위의 분류 확신도. semantic router 또는 LLM confidence를 기록"
    )

    routing_source: Optional[Literal["semantic_fast_path", "llm_fallback", "manual_override"]] = Field(
        default=None,
        description="최종 routing 결정이 어디서 왔는지 기록"
    )
```

## 해석 가이드

### 1. `intent`는 answer objective

예:

- `연결 기준 매출액은 얼마인가?`
  - `intent = numeric_fact`
- `회사가 영위하는 주요 사업은 무엇인가?`
  - `intent = business_overview`
- `주요 재무 리스크는 무엇인가?`
  - `intent = risk`

### 2. `format_preference`는 evidence retrieval objective

예:

- `각 부문별 매출 비중은 어떻게 되나?`
  - `intent = numeric_fact`
  - `format_preference = table`
- `회사가 영위하는 주요 사업은 무엇인가?`
  - `intent = business_overview`
  - `format_preference = mixed`
- `주요 재무 리스크는 무엇인가?`
  - `intent = risk`
  - `format_preference = paragraph`

## edge case 예시

| 질문 | intent | format_preference | 메모 |
|---|---|---|---|
| 삼성전자의 연결 기준 매출액은 얼마인가? | `numeric_fact` | `table` | 표 기반 숫자 질문 |
| 각 부문별 매출 비중은 어떻게 되나? | `numeric_fact` | `table` | overview처럼 보이지만 최종 답은 수치 |
| 회사가 영위하는 주요 사업은 무엇인가? | `business_overview` | `mixed` | 문단 중심이지만 summary 표도 가능 |
| 주요 재무 리스크는 무엇인가? | `risk` | `paragraph` | 설명 문단 중심 |
| DX와 DS 매출 차이는? | `comparison` | `table` | 비교 + 표 기반 |
| 최근 3년 영업이익 추이는? | `trend` | `table` | 시계열 수치 |

## 초기 적용 원칙

초기에는 아래 원칙만 지킨다.

- `intent`와 `format_preference`는 반드시 둘 다 기록
- downstream retrieval은 `format_preference`를 기준으로 block type 보정
- section bias는 `intent`를 기준으로 계산
- `routing_source`와 `confidence`는 실험 로그 해석용으로만 먼저 사용

## 이후 확장 포인트

향후 필요하면 다음 필드를 추가할 수 있다.

- `secondary_intent`
- `requires_calculation`
- `requires_synthesis`
- `expected_output_shape`
  - `single_value`
  - `bullet_list`
  - `short_summary`

하지만 현재 단계에서는 스키마를 너무 크게 만들지 않고, `intent + format_preference`만 먼저 도입하는 것이 맞다.
