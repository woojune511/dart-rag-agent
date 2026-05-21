# Evaluator Design Rationale

이 문서는 이 프로젝트의 evaluator가 왜 generic QA judge 하나가 아니라  
**여러 축으로 분리된 contract**를 갖는지 설명한다.

## Core argument

재무 공시 QA에서 “답이 맞는가”는 단일 질문이 아니다.  
적어도 아래 네 가지가 분리되어야 한다.

- 숫자 자체가 맞는가
- 그 숫자가 실제 근거 텍스트에 grounded되어 있는가
- retrieval이 그 숫자를 뒷받침하는 operand를 실제로 가져왔는가
- 답변이 질문이 요구한 material을 빠뜨리지 않았는가

따라서 evaluator는 하나의 `faithfulness` 점수로 충분하지 않다.

## Why generic faithfulness was insufficient

generic LLM judge는 아래 케이스를 자주 제대로 다루지 못한다.

- `300조 8,709억원` vs `300,870,903 백만원`
  - 같은 값이지만 표현이 다름
- `2023 current`, `2022 prior`, `증감`
  - 값은 일부 맞아도 required material이 빠질 수 있음
- `DX`, `DS`, `SDC`, `Harman`
  - 문장 전체는 자연스러워도 wrong entity row일 수 있음
- ratio / subtraction
  - 최종 숫자는 맞아도 operand grounding이 약할 수 있음

즉 evaluator는 **답변 자연스러움**보다 **structured correctness**를 먼저 봐야 했다.

## Evaluator split

현재 핵심 분리는 다음과 같다.

### Retrieval diagnostics

- `retrieval_hit_at_k`
- `ndcg_at_3`, `ndcg_at_5`
- `context_precision_at_k`
- `section_match_rate`
- `citation_coverage`
- `entity_coverage`

이 지표들은 “잘 찾았는가”를 본다.  
하지만 이것만으로 최종 품질을 판정하지 않는다.

### Generation quality

- `faithfulness`
- `answer_relevancy`
- `context_recall`
- `completeness`
- `refusal_accuracy`

이 지표들은 “질문에 맞는 답을 근거 있게 말했는가”를 본다.

### Numeric-specific metrics

- `numeric_equivalence`
- `numeric_grounding`
- `numeric_retrieval_support`
- `numeric_final_judgement`
- `absolute_error_rate`
- `calculation_correctness`

이 지표들은 “숫자가 맞고, grounded되어 있고, retrieval support가 있는가”를 본다.

## Why `numeric_final_judgement` exists

실무적으로는 숫자 질문에 대해 여러 sub-metric을 다 보고도 최종 verdict가 필요하다.  
그래서 `numeric_final_judgement = PASS / FAIL / UNCERTAIN`를 둔다.

이 verdict는 다음을 위한 것이다.

- official gate pass/fail
- candidate selection
- benchmark summary ranking

즉 sub-metric은 diagnosis용이고, final judgement는 gate용이다.

## Why operand grounding matters

이 프로젝트에서 가장 중요했던 evaluator 개선 중 하나는  
section-based support에서 **operand-grounding support**로 옮긴 것이다.

이유:

- 같은 section 안에 있다고 해서 답이 grounded된 것은 아니다
- 실제로 중요한 것은 답에 들어간 숫자가
  - 어떤 operand였는지
  - 어떤 row/value에서 왔는지
  - 어떤 unit/period/entity를 가졌는지
  가 드러나는 것이다

그래서 runtime 결과도 flat text가 아니라:

- `answer_slots`
- `structured_result`
- `resolved_calculation_trace`

를 보존하도록 정리했다.

## Why `answer_slots` became the runtime contract

`answer_slots`는 evaluator 관점에서 아래 장점이 있다.

- operation별 required material을 구조적으로 표현할 수 있다
- `current_value`, `prior_value`, `delta_value`, `primary_value`를 명시적으로 가질 수 있다
- `status`, `source_row_id`, `source_anchor`, `normalized_unit` 같은 provenance를 같이 담을 수 있다

즉 evaluator는 더 이상 문장을 다시 해석하지 않고도:

- missing material
- wrong period
- wrong unit
- wrong provenance

를 직접 검사할 수 있다.

## Why refusal is separate

재무 공시 QA에서는 문서에 답이 없는 질문도 의미가 있다.  
이 경우 시스템은 “아무 말이나 하는 것”보다 **근거 없음을 말하는 것**이 더 낫다.

그래서 refusal은 단순 실패가 아니라 evaluator의 별도 축으로 다룬다.

- `correct_refusal`
- `false_refusal`
- `hallucinated_answer`

를 구분할 수 있어야 시스템의 product quality를 설명할 수 있다.

## Current evaluator philosophy

한 줄로 요약하면:

> Retrieval은 diagnostic, generation은 answer quality, numeric evaluator는 gate verdict를 담당한다.

즉:

- retrieval metric만 높아도 안 된다
- faithfulness 하나만 높아도 안 된다
- 숫자 질문은 numeric contract를 통과해야 한다

## What this shows in a portfolio

이 evaluator 설계는 “metric을 많이 썼다”는 의미가 아니다.  
포트폴리오 관점에서 보여주는 것은 아래다.

- 평가 문제를 task-specific contract로 재정의했다
- generic LLM judge의 한계를 알고 있었다
- domain-specific evaluator를 설계해 false negative / false positive를 줄였다
- benchmark gate를 운영 가능한 pass/fail 체계로 만들었다

