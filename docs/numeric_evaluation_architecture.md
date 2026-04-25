# Numeric Evaluation Architecture

이 문서는 `numeric_fact` 질문을 기존 단일 `faithfulness` judge만으로 채점할 때 생기는 한계를 정리하고, 더 신뢰할 수 있는 **병렬 numeric evaluator + resolver** 구조를 제안한다.

핵심 문제는 다음과 같다.

- `300조 8,709억원`과 `300,870,903 백만원`처럼 **표현은 다르지만 값은 같은 답**이 있다.
- 현재 `faithfulness`는 retrieval grounding을 보는 데는 유용하지만, 숫자 문항에서는 **표현 차이**에 과도하게 민감할 수 있다.
- 그 결과, 사실상 맞는 답인데도 `faithfulness = 0.0`이 나오는 false fail이 발생한다.

즉 숫자 질문은 일반 서술형 질문과 같은 evaluator로만 다루기 어렵다.

## 목표

숫자 질문에서는 다음을 동시에 보장하고 싶다.

- 값이 실제로 같은지
- 그 숫자가 질문이 묻는 **대상 필드**와 맞는지
- 그 숫자가 검색된 evidence에 grounded되는지
- judge 하나의 오판으로 잘못 채점되지 않는지

따라서 목표 구조는 **여러 채점기를 병렬로 돌리고, 최종 resolver가 합의 기반으로 판정하는 구조**다.

## 왜 단일 judge만으로는 부족한가

단일 LLM judge는 아래 문제를 가진다.

### 1. 표현 차이에 약하다

- `억원`, `백만원`, `%`, `bp`, `조` 같은 단위 차이
- 표 셀 값 vs 문단 요약 값
- 쉼표, 자릿수 구분, 한글 수사 표현

### 2. 숫자 동치성과 grounding을 한 번에 보려 한다

숫자 질문의 채점은 사실 두 축이다.

- **equivalence**
  - 값이 같은가?
- **grounding**
  - 그 값이 evidence에 근거하는가?

단일 judge는 이 둘을 분리해 설명하기 어렵다.

### 3. confidence를 표현하기 어렵다

현재는 사실상 pass/fail에 가깝지만, 실제로는 아래 같은 상태가 존재한다.

- 값은 같지만 target field가 애매함
- target field는 맞지만 단위 변환이 헷갈림
- retrieval은 맞는데 judge가 숫자 표현을 못 읽음

이런 경우는 `uncertain`으로 다뤄야 한다.

## 제안 구조

숫자 질문은 아래 4개 evaluator를 병렬로 실행한다.

1. `Numeric Extractor`
2. `Numeric Equivalence Checker`
3. `Grounding Judge`
4. `Retrieval Support Check`

그리고 마지막에 `Conflict Resolver`가 최종 판정을 만든다.

## 1. Numeric Extractor

### 역할

답변과 evidence에서 아래 정보를 구조화해 뽑는다.

- 값
- 단위
- 대상 항목
- 시점
- 출처 anchor

### 입력

- question
- answer
- runtime evidence
- canonical evidence

### 출력 예시

```json
{
  "value_text": "300,870,903",
  "unit": "백만원",
  "normalized_value": 300870903000000,
  "field": "연결 기준 매출액",
  "year": 2024,
  "source_anchor": "[삼성전자 | 2024 | III. 재무에 관한 사항 > 1. 요약재무정보]"
}
```

### 구현 후보

- LLM extraction
- hybrid extraction
  - 숫자/단위 regex + LLM field resolution

초기엔 hybrid extraction이 가장 현실적이다.

## 2. Numeric Equivalence Checker

### 역할

추출된 answer 숫자와 canonical/evidence 숫자가 **동치인지** 판단한다.

### 판단 대상

- `300조 8,709억원`
- `300,870,903 백만원`

같은 값을 같은 기준 스케일로 정규화해 비교한다.

### 출력

- `true`
- `false`
- `uncertain`

### 장점

- 숫자 자체의 맞고 틀림을 deterministic하게 볼 수 있다.
- LLM judge가 표현 차이 때문에 틀리게 보는 문제를 줄일 수 있다.

## 3. Grounding Judge

### 역할

LLM judge가 다음만 본다.

- 답변 숫자가 실제 evidence span에 grounded되는가
- 단위 변환이 evidence와 충돌하지 않는가
- 질문의 target field와 숫자가 맞는가

### 중요한 점

이 judge는 “값이 같은가”를 주로 보는 게 아니라,
**그 값이 질문과 evidence에 맞는가**를 본다.

### 출력

- `grounded`
- `not_grounded`
- `uncertain`

### 권장 방식

자유 점수보다 3값 분류가 낫다.

- `grounded`
- `not_grounded`
- `uncertain`

## 4. Retrieval Support Check

### 역할

답변 숫자가 나온 evidence가 정말 기대 섹션 / 기대 회사 / 기대 연도와 맞는지 확인한다.

### 목적

- retrieval이 틀렸는데 우연히 비슷한 숫자를 말한 경우 방지
- section alias와 함께 숫자 질문의 grounding을 더 안정적으로 해석

### 출력

- `supported`
- `unsupported`
- `uncertain`

## 5. Conflict Resolver

### 역할

위 4개 결과를 모아 최종 판정을 만든다.

### 최종 상태

- `PASS`
- `FAIL`
- `UNCERTAIN`

### 권장 규칙

#### PASS

- equivalence = `true`
- grounding = `grounded`
- retrieval support = `supported` 또는 충분히 강함

#### FAIL

- equivalence = `false`
- 또는 grounding = `not_grounded`

#### UNCERTAIN

- extraction 실패
- evaluator 간 충돌
- 값은 같지만 target field가 애매
- retrieval support가 약함

핵심은 **억지로 pass/fail만 강요하지 않는 것**이다.

## Parallel Evaluation Flow

```text
question
  + answer
  + canonical evidence
  + runtime evidence
      -> Numeric Extractor
      -> Numeric Equivalence Checker
      -> Grounding Judge
      -> Retrieval Support Check
      -> Conflict Resolver
      -> final_numeric_judgement
```

## Metric Design

숫자 질문에서는 기존 `faithfulness`와 별도로 아래 metric을 둔다.

### 1. `numeric_equivalence`

- 값 동치 여부

### 2. `numeric_grounding`

- evidence grounding 여부

### 3. `numeric_retrieval_support`

- retrieval support 여부

### 4. `numeric_final_judgement`

- `pass / fail / uncertain`

### 5. `numeric_confidence`

- resolver confidence

## Existing Metrics와의 관계

### `faithfulness`

- numeric 질문에서는 유지하되 **보조 지표**로 낮춘다.
- 최종 정답 판정은 `numeric_final_judgement`를 우선한다.

### `answer_relevancy`

- numeric 질문에서는 의미가 제한적이다.
- 질문의 target field와 답변 숫자가 같은지 보는 별도 지표가 더 중요하다.

### `context_recall`

- retrieval 품질 참고용으로는 유지한다.

## Recommended Implementation Order

### Phase 1. Logging / Schema

- canonical dataset에 numeric 전용 필드 추가
  - `display_value`
  - `normalized_value`
  - `unit`
- runtime evidence에도 numeric field를 둘 수 있게 준비

### Phase 2. Extractor

- answer / evidence 숫자 구조화
- numeric 질문만 별도 extraction path 사용

### Phase 3. Equivalence + Retrieval Support

- 값 동치 판정
- 기대 section/company/year support 확인

### Phase 4. Grounding Judge

- LLM judge를 숫자 전용 rubric으로 분리

### Phase 5. Resolver

- `pass / fail / uncertain` 판정
- aggregate metric 반영

## Current Status

현재 상태는 아래까지 반영된 것으로 본다.

- Phase 1
  - benchmark 결과와 review artifact에 numeric evaluator 필드 기록
- Phase 2~4의 최소 버전
  - `Numeric Extractor`
  - `Numeric Equivalence Checker`
  - `Grounding Judge`
  - `Retrieval Support Check`
  - `Conflict Resolver`
  가 `numeric_fact` path에 1차 구현됨
- **Generation-side 분리 (결정 60, 2026-04-26)**
  - `numeric_extractor` 노드가 `compress → validate`를 bypass하고 직접 수치 추출
  - `NumericExtraction` Pydantic 스키마로 period/consolidation/unit/raw_value CoT 강제
  - `selective_v2_prefix` 기준 `numeric_fact_001`: FAIL → PASS 회복

삼성전자 `numeric_fact_001` 기준 (`numeric_extractor_v2_2026-04-26`):

- `numeric_final_judgement = PASS` (contextual_all, contextual_parent_only, selective_v2_prefix)
- `plain_prefix`: UNCERTAIN 지속 — ingest-side 문제로 별도 추적

남은 단계:

- `plain_prefix`의 numeric_fact 실패 원인 파악 (plain chunk에 table row가 수치를 포함하지 않는 문제)
- aggregate / summary에서 `numeric_final_judgement`를 더 전면에 반영
- cross-company summary 및 winner selection 해석에 numeric evaluator 반영

## Trade-offs

### 장점

- false fail 감소
- 숫자 질문에서 “왜 맞고 왜 틀린지” 설명 가능
- 단일 judge 의존도 감소
- `uncertain` 버킷으로 잘못된 강제 판정 방지

### 단점

- 구현 복잡도 증가
- 일부 evaluator 비용 증가
- canonical dataset 보강 필요

## 결론

숫자 질문은 일반 서술형 질문과 같은 `faithfulness` judge 하나로 채점하기 어렵다.

가장 신뢰할 수 있는 방향은:

- **여러 evaluator를 병렬로 실행하고**
- **값 동치성 / grounding / retrieval support를 분리해 보고**
- **resolver가 최종 판정을 내리는 구조**

이다.

즉 다음 numeric evaluator는 “더 똑똑한 단일 judge”가 아니라,  
**parallel numeric evaluators + conflict-aware resolver**를 목표로 해야 한다.
