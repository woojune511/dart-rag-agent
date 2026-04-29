# Answer Generation Principles

이 문서는 최근 benchmark에서 드러난 **metric gaming 신호**를 줄이고, 답변 생성 단계를 더 principled하게 유지하기 위한 원칙을 정리한다.

더 큰 구조 변경 방향(예: GraphRAG / multi-agent 대비 어떤 구조가 적절한가)은 [architecture_direction.md](architecture_direction.md)를 참고한다.

## 문제 인식

최근 `v5`와 `v6`/`v7` 실험에서 확인된 사실:

- retrieval 계열 지표는 크게 바뀌지 않았는데 `faithfulness`만 크게 흔들릴 수 있다.
- 이 경우 문제의 중심은 retrieval이 아니라 answer synthesis일 가능성이 높다.
- 질문 유형별 hardcoded rule을 계속 추가하면 특정 benchmark 문항은 좋아질 수 있지만, 다른 문항에서 부작용이 생긴다.
- 특히 `business_overview`와 `risk`는 짧은 규칙 수정만으로도 점수가 출렁여, 시스템 개선보다 judge 최적화에 가까워질 위험이 있다.

따라서 앞으로의 목표는:

- benchmark 점수 자체를 최대화하는 것
보다
- **근거 중심, 질문 적합성, 일반화 가능성**을 함께 만족하는 답변 생성 구조를 유지하는 것이다.

## 상위 원칙

### 1. Retrieval 문제와 Generation 문제를 분리해서 다룬다

- retrieval hit/section match가 유지되는데 faithfulness만 떨어지면 retrieval을 먼저 고치지 않는다.
- 이런 경우는 answer generation이 근거보다 더 많이 말하고 있는지부터 점검한다.

### 2. 규칙보다 구조를 우선한다

- 질문별 예외 규칙을 계속 늘리는 대신, evidence 표현과 answer 조합 방식을 더 구조화한다.
- 좋은 방향:
  - evidence를 더 명시적으로 구조화
  - unsupported sentence 제거
  - 질문이 요구한 범위만 남기는 압축 단계
- 덜 좋은 방향:
  - 특정 question id나 특정 benchmark 표현만 맞추는 하드코딩

### 3. Faithfulness는 중요하지만 단독 목표가 아니다

- faithfulness는 hallucination 억제 지표로 중요하다.
- 그러나 faithfulness만 올리면 너무 소극적이고 덜 유용한 답변이 될 수 있다.
- 앞으로는 아래를 함께 본다.
  - faithfulness
  - answer_relevancy
  - context_recall
  - retrieval_hit_at_k
  - section_match_rate
  - 실제 답변의 유용성 / 과잉 설명 여부

### 4. 답변은 “질문에 필요한 만큼만” 말한다

- 문제는 대개 “못 찾는 것”보다 “더 많이 말하는 것”에서 생긴다.
- 질문이 요구하지 않은 배경 설명, 예시 법인명, 회계 기준, taxonomy 재구성은 기본적으로 불필요한 것으로 본다.
- 다만 이런 제약은 benchmark 문항별 예외 처리보다 상위 원칙과 구조로 구현해야 한다.

### 5. Canonical eval dataset도 시스템과 함께 개선 대상이다

- `numeric_fact_001`처럼 정답 표현이 지나치게 좁거나 특정 표현 형식에 의존하는 경우는 metric 해석을 왜곡할 수 있다.
- 시스템만 고치기보다:
  - `answer_key`
  - `evidence quote`
  - judge rubric
  - allowed paraphrase 범위
를 함께 재검토한다.

## 최근 규칙 인벤토리

아래는 2026-04-20 기준 최근 answer-generation 관련 규칙을 분류한 것이다.

### 유지할 것

- `docs[:8]` evidence 입력 확대
  - 이유: retrieval은 성공했는데 evidence 단계에서 hard abstain하는 문제를 줄이는 구조적 개선
- `coverage=missing` + docs 존재 시 deterministic fallback
  - 이유: evidence LLM의 보수성 때문에 바로 abstain하는 문제를 완화
- `risk` evidence 단계의 verbatim 제한
  - 이유: 원문에 없는 리스크 카테고리 생성 방지라는 명확한 안정성 목적
- evaluator context `[:5] -> [:8]`
  - 이유: agent 실제 사용 범위와 evaluator 범위를 일치시키는 정합성 수정

### 실험용으로만 유지할 것

- query_type별 section bias
  - `business_overview`에서 `사업의 개요`, `주요 제품 및 서비스` 우대
  - `numeric_fact`에서 `요약재무정보`, `연결재무제표` 우대
- query_type별 output style 강제
  - 예: `numeric_fact` 한 문장, `business_overview` 최대 4 bullets
- post-generation guard pass
  - unsupported detail 제거 목적

이 규칙들은 완전히 잘못된 것은 아니지만, benchmark-specific 최적화로 기울 가능성이 있어 장기 기본 구조로 고정하지 않는다.

### 제거 후보

- 질문 표현을 직접 읽어 `"얼마"`, `"몇 개"` 등에 따라 세부 출력 규칙을 바꾸는 로직
- category별로 너무 세밀한 hardcoded 금지어/허용어 누적
- 특정 benchmark 문항의 judge 성향을 맞추기 위한 문장 길이/형식 최적화

이 부류는 코드 복잡도를 높이고 다른 질문 유형에서 부작용을 만들 가능성이 크다.

## 다음 리팩터링 방향

다음 단계는 규칙을 더 붙이는 것이 아니라 answer generation 구조를 더 단순하고 설명 가능하게 바꾸는 것이다.

### 1. Evidence representation 개선

- 현재 bullet 문자열 중심 구조를 더 구조화한다.
- 상세 설계 초안은 [evidence_schema.md](evidence_schema.md)를 참고한다.
- 예:
  - `claim`
  - `source_anchor`
  - `quote_span`
  - `support_level`
  - `allowed_terms`

### 2. Answer synthesis를 compression 단계로 재정의

- answer 생성은 “새 답을 쓰는 단계”가 아니라 “evidence를 질문 범위에 맞게 압축하는 단계”로 본다.
- 특히 `business_overview`와 `risk`는
  - 범주 재구성
  - 배경 확장
  - 추가 해설
를 기본적으로 하지 않는 방향으로 간다.

### 3. Unsupported claim detection을 별도 계층으로 둔다

- generation prompt에 제약을 계속 쌓는 대신,
- answer 초안 이후 unsupported sentence를 지우는 경량 validator를 별도 계층으로 두는 쪽이 더 설명 가능하다.

### 4. Benchmark와 운영 기본값을 분리해 해석한다

- benchmark에서 특정 규칙이 점수를 올리더라도, 운영 기본값에 바로 반영하지 않는다.
- 기본값 채택 기준:
  - 다기업 generalization
  - answer usefulness
  - metric consistency
  - 코드 단순성

## 현재 결론

현재 시점의 결론은 다음과 같다.

- 최근 `v6`/`v7` 수정은 일부 `business_overview` 문항의 faithfulness 회복에 도움이 됐다.
- 하지만 동시에 `risk` 같은 다른 문항에서 새 부작용이 생겼다.
- 이는 “규칙 추가”가 장기 해법이 아니라는 신호다.

따라서 다음 우선순위는:

1. answer generation 원칙을 문서화하고
2. 최근 규칙을 `유지 / 실험용 / 제거 후보`로 분리하며
3. 구조적 리팩터링 방향을 먼저 고정하는 것이다.
