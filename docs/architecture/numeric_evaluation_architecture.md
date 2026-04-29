# Numeric Evaluation Architecture

이 문서는 `numeric_fact` 질문을 기존 단일 `faithfulness` judge만으로 채점할 때 생기는 한계를 정리하고, 더 신뢰할 수 있는 **병렬 numeric evaluator + resolver** 구조를 설명한다.

## Executive Summary

| 문제 | 현재 해석 |
| --- | --- |
| `300조 8,709억원` vs `300,870,903 백만원`처럼 표현은 다르지만 값은 같은 답 | 단일 faithfulness judge는 표현 차이에 과민할 수 있음 |
| 숫자 동치성과 grounding을 한 번에 보려는 평가 | 축을 분리해서 봐야 함 |
| PASS / FAIL만 강제하는 판정 | `UNCERTAIN` 상태가 필요함 |

> 숫자 질문은 일반 서술형 질문과 같은 evaluator 하나로만 다루기 어렵다.  
> 가장 신뢰할 수 있는 방향은 **여러 evaluator를 병렬로 실행하고 resolver가 최종 판정을 내리는 구조**다.

## Design Goals

숫자 질문에서는 다음을 동시에 보장하고 싶다.

| 목표 | 설명 |
| --- | --- |
| 값 동치성 | 값이 실제로 같은가 |
| field identity | 그 숫자가 질문이 묻는 대상 필드와 맞는가 |
| evidence grounding | 그 숫자가 검색된 evidence에 grounded되는가 |
| robust judgement | judge 하나의 오판으로 잘못 채점되지 않는가 |

## Why a Single Judge Is Not Enough

| 한계 | 설명 |
| --- | --- |
| 표현 차이에 약함 | `억원`, `백만원`, `%`, `bp`, `조`, 쉼표, 한글 수사 표현 등 |
| equivalence와 grounding을 동시에 보려 함 | 값 동치성과 evidence alignment를 분리해 봐야 함 |
| confidence 표현이 어려움 | 값은 같지만 field가 애매한 경우 등을 `uncertain`으로 다뤄야 함 |

## Proposed Evaluator Stack

숫자 질문은 아래 4개 evaluator를 병렬로 실행하고, 마지막에 resolver가 최종 판정을 만든다.

| Evaluator | 역할 | 출력 형태 |
| --- | --- | --- |
| `Numeric Extractor` | answer와 evidence에서 값 / 단위 / 필드 / 시점 / 출처를 구조화 | structured numeric object |
| `Numeric Equivalence Checker` | answer 숫자와 canonical/evidence 숫자의 값 동치 여부 확인 | `true / false / uncertain` |
| `Grounding Judge` | 값이 evidence와 질문 field에 맞게 grounded되는지 확인 | `grounded / not_grounded / uncertain` |
| `Retrieval Support Check` | 답변 숫자가 실제 읽은 텍스트 / retrieval context에 supported되는지 확인 | `supported / unsupported / uncertain` |
| `Conflict Resolver` | 위 결과를 종합해 최종 판정 생성 | `PASS / FAIL / UNCERTAIN` |

## Component Details

### 1. Numeric Extractor

| 항목 | 내용 |
| --- | --- |
| 입력 | question, answer, runtime evidence, canonical evidence |
| 출력 | 값, 단위, 대상 항목, 시점, 출처 anchor |
| 구현 후보 | LLM extraction, hybrid extraction |
| 현재 추천 | 숫자/단위 regex + LLM field resolution을 섞은 hybrid extraction |

예시:

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

### 2. Numeric Equivalence Checker

| 항목 | 내용 |
| --- | --- |
| 역할 | 추출된 answer 숫자와 canonical/evidence 숫자가 동치인지 판단 |
| 예시 | `300조 8,709억원` vs `300,870,903 백만원` |
| 출력 | `true / false / uncertain` |
| 장점 | 숫자 자체의 맞고 틀림을 deterministic하게 볼 수 있음 |

### 3. Grounding Judge

| 항목 | 내용 |
| --- | --- |
| 역할 | answer 숫자가 evidence span에 grounded되는지, 단위 변환이 충돌하지 않는지, 질문의 target field와 맞는지 확인 |
| 핵심 | “값이 같은가”보다 “질문과 evidence에 맞는가”를 본다 |
| 출력 | `grounded / not_grounded / uncertain` |
| 권장 방식 | 자유 점수보다 3값 분류 |

### 4. Retrieval Support Check

| 항목 | 내용 |
| --- | --- |
| 역할 | 답변 숫자가 나온 evidence가 기대 회사 / 연도 / 섹션과 얼마나 맞는지 확인 |
| 목적 | retrieval이 틀렸는데 우연히 비슷한 숫자를 말한 경우 방지 |
| 출력 | `supported / unsupported / uncertain` |

### 5. Conflict Resolver

| 상태 | 권장 규칙 |
| --- | --- |
| `PASS` | equivalence=`true`, grounding=`grounded`, retrieval support가 충분함 |
| `FAIL` | equivalence=`false` 또는 grounding=`not_grounded` |
| `UNCERTAIN` | extraction 실패, evaluator 간 충돌, field ambiguity, retrieval support 약함 |

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

## Metric Mapping

| Metric | 의미 |
| --- | --- |
| `numeric_equivalence` | 값 동치 여부 |
| `numeric_grounding` | evidence grounding 여부 |
| `numeric_retrieval_support` | retrieval / text support 여부 |
| `numeric_final_judgement` | `PASS / FAIL / UNCERTAIN` 최종 판정 |
| `numeric_confidence` | resolver confidence |

## Relationship to Generic Metrics

| 기존 지표 | numeric 질문에서의 역할 |
| --- | --- |
| `faithfulness` | 유지하되 보조 지표로 낮춤 |
| `answer_relevancy` | 의미가 제한적이며 field identity를 대체하지 못함 |
| `context_recall` | retrieval 품질 참고용으로 유지 |

## Recommended Implementation Order

| Phase | 범위 | 목표 |
| --- | --- | --- |
| Phase 1 | Logging / schema | canonical dataset과 runtime artifact에 numeric 전용 필드 추가 |
| Phase 2 | Extractor | answer / evidence 숫자 구조화, numeric 질문 전용 extraction path |
| Phase 3 | Equivalence + Retrieval Support | 값 동치 판정, 기대 company/year/section support 확인 |
| Phase 4 | Grounding Judge | 숫자 전용 rubric으로 LLM judge 분리 |
| Phase 5 | Resolver | `PASS / FAIL / UNCERTAIN` 판정과 aggregate 반영 |

## Current Status

| 상태 | 반영 내용 |
| --- | --- |
| Phase 1 | benchmark 결과와 review artifact에 numeric evaluator 필드 기록 |
| Phase 2~4 최소 버전 | `Numeric Extractor`, `Numeric Equivalence Checker`, `Grounding Judge`, `Retrieval Support Check`, `Conflict Resolver`가 `numeric_fact` path에 1차 구현 |
| Generation-side 분리 | `numeric_extractor` 노드가 `compress -> validate`를 bypass하고 직접 수치 추출 |

삼성전자 `numeric_fact_001` 기준 (`numeric_extractor_v2_2026-04-26`):

| 프로파일 | 결과 |
| --- | --- |
| `contextual_all` | `numeric_final_judgement = PASS` |
| `contextual_parent_only` | `numeric_final_judgement = PASS` |
| `selective_v2_prefix` | `numeric_final_judgement = PASS` |
| `plain_prefix` | `UNCERTAIN` 지속 |

남은 단계:

| 과제 | 이유 |
| --- | --- |
| `plain_prefix`의 numeric_fact 실패 원인 파악 | plain chunk에 table row가 수치를 충분히 포함하지 않는 문제 추적 |
| aggregate / summary에서 `numeric_final_judgement`를 더 전면 반영 | 숫자 질문 해석을 더 직관적으로 만들기 위해 |
| cross-company summary 및 winner selection에 numeric evaluator 반영 | multi-entity 비교를 준비하기 위해 |

## Trade-offs

| 장점 | 단점 |
| --- | --- |
| false fail 감소 | 구현 복잡도 증가 |
| 숫자 질문에서 “왜 맞고 왜 틀린지” 설명 가능 | 일부 evaluator 비용 증가 |
| 단일 judge 의존도 감소 | canonical dataset 보강 필요 |
| `uncertain` 버킷으로 잘못된 강제 판정 방지 | 운영/리뷰 artifact가 더 복잡해짐 |

## Conclusion

숫자 질문은 일반 서술형 질문과 같은 `faithfulness` judge 하나로 채점하기 어렵다.

가장 신뢰할 수 있는 방향은:

- **여러 evaluator를 병렬로 실행하고**
- **값 동치성 / grounding / retrieval support를 분리해 보고**
- **resolver가 최종 판정을 내리는 구조**

이다.

즉 다음 numeric evaluator는 “더 똑똑한 단일 judge”가 아니라, **parallel numeric evaluators + conflict-aware resolver**를 목표로 해야 한다.
