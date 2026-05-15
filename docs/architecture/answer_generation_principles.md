# Answer Generation Principles

이 문서는 최근 benchmark에서 드러난 **metric gaming 신호**를 줄이고, 답변 생성 단계를 더 principled하게 유지하기 위한 원칙을 정리한다.

더 큰 구조 변경 방향은 [architecture_direction.md](architecture_direction.md)를 참고한다.

## Executive Summary

| 질문 | 현재 답 |
| --- | --- |
| 최근 흔들림의 중심은 retrieval인가 generation인가? | generation 쪽일 가능성이 더 큼 |
| hardcoded rule을 계속 쌓아야 하는가? | 아니오, 구조를 먼저 바꿔야 함 |
| 앞으로의 답변 생성 목표는 무엇인가? | 근거 중심, 질문 적합성, 일반화 가능성 유지 |

## Problem Recognition

최근 `v5`, `v6`, `v7` 실험에서 확인된 관찰은 다음과 같다.

| 관찰 | 해석 |
| --- | --- |
| retrieval 계열 지표는 크게 바뀌지 않았는데 `faithfulness`만 크게 흔들림 | 문제의 중심이 retrieval보다 answer synthesis일 수 있음 |
| 질문 유형별 hardcoded rule을 계속 추가하면 특정 문항은 좋아지지만 다른 문항에서 부작용 발생 | 시스템 개선보다 judge 최적화에 가까워질 위험 |
| `business_overview`, `risk`는 짧은 규칙 수정만으로도 점수가 출렁임 | 안정적인 구조 제약이 필요 |

따라서 목표는 benchmark 점수 극대화보다 **근거 중심, 질문 적합성, 일반화 가능성**을 함께 만족하는 답변 생성 구조를 유지하는 것이다.

## Top-level Principles

| 원칙 | 설명 |
| --- | --- |
| Retrieval 문제와 Generation 문제를 분리해서 다룬다 | retrieval hit/section match가 유지되는데 faithfulness만 떨어지면 generation부터 점검 |
| 규칙보다 구조를 우선한다 | question-specific hardcoding보다 evidence 구조화 / compression / validation을 우선 |
| Faithfulness는 중요하지만 단독 목표가 아니다 | faithfulness, answer_relevancy, context_recall, retrieval metric, 실제 usefulness를 함께 봄 |
| 답변은 “질문에 필요한 만큼만” 말한다 | 과잉 설명, taxonomy 재구성, 불필요한 배경 확장을 기본적으로 피함 |
| Canonical eval dataset도 개선 대상이다 | answer_key / evidence quote / judge rubric / allowed paraphrase를 함께 재검토 |

## Recent Rule Inventory

### 유지할 것

| 규칙 | 유지 이유 |
| --- | --- |
| `docs[:8]` evidence 입력 확대 | retrieval은 성공했는데 evidence 단계에서 hard abstain하는 문제를 줄이는 구조적 개선 |
| `coverage=missing` + docs 존재 시 deterministic fallback | evidence LLM의 보수성 때문에 바로 abstain하는 문제 완화 |
| `risk` evidence 단계의 verbatim 제한 | 원문에 없는 리스크 카테고리 생성 방지라는 명확한 안정성 목적 |
| evaluator context `[:5] -> [:8]` | agent 실제 사용 범위와 evaluator 범위를 일치시키는 정합성 수정 |

### 실험용으로만 유지할 것

| 규칙 | 이유 |
| --- | --- |
| query_type별 section bias | benchmark-specific 최적화로 기울 가능성 |
| query_type별 output style 강제 | 운영 기본값으로 고정하기엔 부작용 위험 |
| post-generation guard pass | unsupported detail 제거에는 유용하지만 장기 기본 구조는 아님 |

### 제거 후보

| 규칙 | 제거 후보인 이유 |
| --- | --- |
| 질문 표현을 직접 읽어 `"얼마"`, `"몇 개"` 등에 따라 세부 출력 규칙 변경 | 로컬 최적화 성격이 강함 |
| category별 hardcoded 금지어/허용어 누적 | 코드 복잡도와 부작용 증가 |
| 특정 benchmark judge 성향을 맞추기 위한 문장 길이/형식 최적화 | metric gaming 위험 |

## Recommended Refactoring Direction

### 1. Evidence representation 개선

| 방향 | 설명 |
| --- | --- |
| 현재 상태 | bullet 문자열 중심 구조 |
| 목표 | `claim`, `source_anchor`, `quote_span`, `support_level`, `allowed_terms` 같은 구조화된 evidence |
| 참고 | [evidence_schema.md](evidence_schema.md) |

### 2. Answer synthesis를 compression 단계로 재정의

| 현재 해석 | 목표 해석 |
| --- | --- |
| “새 답을 쓰는 단계” | “evidence를 질문 범위에 맞게 압축하는 단계” |

특히 `business_overview`, `risk`는

- 범주 재구성
- 배경 확장
- 추가 해설

을 기본적으로 하지 않는 방향으로 간다.

### 3. Unsupported claim detection을 별도 계층으로 분리

generation prompt에 제약을 계속 쌓는 대신,

- answer 초안 이후 unsupported sentence를 지우는 경량 validator

를 별도 계층으로 두는 쪽이 더 설명 가능하다.

### 4. Benchmark와 운영 기본값을 분리해서 해석

기본값 채택 기준:

| 기준 | 의미 |
| --- | --- |
| 다기업 generalization | 특정 문항 최적화가 아닌가 |
| answer usefulness | 실제 사용자에게 유용한가 |
| metric consistency | 지표 간 해석 충돌이 적은가 |
| 코드 단순성 | 운영 부채를 과도하게 늘리지 않는가 |

### 5. Planner와 final synthesizer의 책임을 분리

현재 numeric path는 planner가 “무엇을 구해야 하는가”를 정하고,
final synthesizer가 “원본 질문을 실제로 충족했는가”를 판단하는 방향으로
정리되고 있다.

권장 경계:

| 모듈 | 책임 |
| --- | --- |
| planner | concept / operation / scope를 재료 수집 task로 분해 |
| calculator | 조회 / 계산 결과를 structured result로 생성 |
| final synthesizer | 원본 질문과 subtask 결과를 읽고 최종 답 또는 planner feedback 결정 |
| final refusal | replan 기회를 모두 쓴 뒤에도 재료가 부족할 때 aggregate 단계에서 확정 |

즉 planner는 “답변을 최소화”하려고 하면 안 되고,
필요한 raw value와 파생 계산 재료를 빠짐없이 모으는 쪽에 집중하는 것이
좋다.

### 6. 최종 거부는 local failure가 아니라 aggregate decision으로 닫기

단일 subtask가 실패했다고 바로 사용자-facing refusal을 확정하면,
후속 replan이나 다른 subtask 결과로 질문을 회복할 기회를 잃는다.

따라서 권장 구조는:

1. local calculator / renderer는 재료 부족을 감지
2. final synthesizer는 원본 질문 대비 누락 재료를 `planner_feedback`으로 표현
3. planner는 patch-style replan으로 부족한 재료를 더 모음
4. loop budget을 모두 써도 부족할 때만 aggregate 단계에서 최종 refusal 또는 partial answer를 확정

이 원칙은 특히 다음과 같은 질문에서 중요하다.

- `2023년 값과 전년 대비 증감액을 함께 보여줘`
- multi-metric 질문
- 일부 값은 확보됐지만 최종 comparison / ratio가 아직 안 닫힌 질문

## Current Conclusion

현재 시점의 결론은 다음과 같다.

| 결론 | 의미 |
| --- | --- |
| 최근 `v6`/`v7` 수정은 일부 `business_overview` faithfulness 회복에 도움 | 일부 개선은 있었음 |
| 동시에 `risk` 같은 다른 문항에서 새 부작용 발생 | rule accumulation은 장기 해법이 아님 |
| 다음 우선순위는 원칙 문서화와 구조적 리팩터링 | local patch보다 구조 우선 |

따라서 다음 우선순위는:

1. answer generation 원칙을 문서화하고
2. 최근 규칙을 `유지 / 실험용 / 제거 후보`로 분리하며
3. 구조적 리팩터링 방향을 먼저 고정하는 것

이다.
