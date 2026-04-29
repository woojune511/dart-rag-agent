# Math Pipeline Refactor Plan

이 문서는 `comparison / trend / ratio / percent` 계산 경로에서 누적된 국소 패치를 정리하고,
무엇을 유지하고 무엇을 걷어낼지, 그리고 어떤 순서로 실험할지를 기록한다.

## 왜 이 문서가 필요한가

최근 `comparison_005`, `comparison_006`을 고치면서 다음 문제가 분명해졌다.

- retrieval source miss를 planner / evaluator / fallback으로 덮으려는 패치가 늘었다.
- `%`, `비중`, `연구개발`, `영업이익률` 같은 질문 의미 해석이 파이썬 `if`문으로 새어 나왔다.
- 일부 rescue path는 실제 정답 숫자나 특정 섹션명에 지나치게 묶여 있었다.

반면, `debug_math_workflow.py`로 실제 워크플로를 짧게 재현해 본 결과
`comparison_005`, `comparison_006`의 핵심 병목은 planner가 아니라
**retrieval seed에 `연구개발 활동` 계열 source가 안 들어오는 것**임이 확인됐다.

즉 앞으로는:

1. 먼저 실패 위치를 디버그 스크립트로 확정하고
2. 그 층만 수정하고
3. 같은 재현 스크립트로 다시 확인한 뒤
4. 마지막에만 benchmark를 돌린다

는 원칙으로 간다.

## 유지할 구조 개선

다음은 duct tape가 아니라 현재 구조의 장기 자산으로 본다.

- `intent + format_preference` 분리
- `formula planner + safe AST evaluator`
- math 전용 evaluator 분리
- `debug_math_workflow.py` 같은 재현용 디버그 경로
- `direction_hint`처럼 **부호/대소 관계만 파이썬이 확정**하고, 자연어 표현은 LLM renderer가 맡는 분업

특히 `direction_hint`는 유지한다.
다만 `growth_rate -> 증가/감소`, `subtract -> 더 큽니다/더 작습니다` 수준의
**수학적 방향성 확정**까지만 파이썬이 맡고, 그 이상 의미 해석은 늘리지 않는다.

## 임시 패치로 간주하는 것

다음은 현재 문제를 일시적으로 막는 장치로 본다.

- `_preferred_calc_sections()`의 metric-specific 섹션 우선순위
- `_supplement_section_seed_docs()`의 `연구개발 활동` 보조 seed 주입
- `_is_ratio_percent_query()` / `_is_percent_point_difference_query()` 기반 분기
- `%p` 질문에서의 type-guard fallback
- comparison KRW 절대 허용 오차 `1억원`
- `allowed_grounded_extras`

이들은 당장 제거하지는 않지만, 장기 기본값으로 굳히지 않는다.

## 즉시 걷어낼 대상은 아닌데, 다음에 비워내야 할 것

### 1. 질문 의미 해석용 하드코딩

현재는 아래 함수들이 계산 질문 해석 일부를 직접 떠안고 있다.

- `_preferred_calc_sections`
- `_supplement_section_terms_for_query`
- `_retrieval_hint_from_topic`
- `_is_ratio_percent_query`
- `_is_percent_point_difference_query`

이 로직은 새 metric family가 들어올 때마다 확장 부담이 커진다.

### 2. retrieval 응급 주입

`_supplement_section_seed_docs()`는 이번 문제를 해결하는 데는 유효했지만,
본질적으로는 **특정 source family를 강제로 후보에 밀어 넣는 rescue path**다.

특히 아래처럼 특정 값까지 scoring에 쓰는 부분은 반드시 제거해야 한다.

- `11.6%`
- `10.9%`
- `35조 215억원`

### 3. ratio/percent 전용 fallback 의존

현재 row candidate 추출과 component candidate 추출 자체는 유용하다.
다만 이들이 planner 실패 후 우회로가 아니라,
**planner가 기본적으로 받는 pre-extracted candidates** 쪽으로 이동해야 구조가 더 단순해진다.

## 새 방향: 하드코딩을 대체할 재무 온톨로지

질문 의미 해석용 지식을 파이썬 `if`문에 계속 쌓지 않고,
구조화된 설정으로 빼내는 방향을 다음 실험의 핵심 가설로 둔다.

초안:

```json
{
  "metrics": {
    "R_AND_D_RATIO": {
      "keywords": ["연구개발", "R&D"],
      "preferred_sections": ["연구개발 활동", "연구개발실적", "요약재무정보"],
      "row_patterns": ["연구개발비 / 매출액 비율"],
      "requires_components": ["연구개발비용", "매출액"]
    },
    "OPERATING_MARGIN": {
      "keywords": ["영업이익률", "이익률"],
      "preferred_sections": ["요약재무정보", "손익계산서"],
      "requires_components": ["영업이익", "매출액"]
    }
  }
}
```

핵심은:

- metric family 지식은 설정 파일로 이동
- retrieval은 이 설정을 읽어 보조 쿼리와 section bias를 생성
- planner는 `target_metric`, `target_section_family` 같은 구조화된 힌트를 내놓음

즉 코드는 범용 로직을 유지하고, 도메인 지식은 설정으로 관리한다.

## 실험 계획

### Phase 0. 기준선 고정

목표:

- 현재 `dev_math_edge_focus_retrievalfixed_2026-04-28`을 math edge baseline으로 고정
- `debug_math_workflow.py` 출력도 함께 보존

성공 기준:

- `comparison_005`, `comparison_006`, `comparison_007` 모두 pass
- 디버그 JSON에서
  - `seed_retrieved_docs`에 `연구개발 활동`이 포함되고
  - `ratio_row_candidates > 0` 또는 `component_candidates > 0`

### Phase 1. retrieval rescue path의 원인 분리

질문:

- `연구개발 활동` 보조 seed가 없으면 왜 miss가 나는가?
- `preferred_sections` bias만으로는 충분하지 않은가?

실험:

1. 현재 rescue path 유지
2. rescue path를 끄고, bias / query expansion만 켠 variant
3. rescue path 없이 ontology-driven multi-query만 켠 variant

출력:

- `debug_math_workflow.py` 기준 비교
- full benchmark보다 먼저 debug JSON으로 비교

### Phase 2. 온톨로지 기반 multi-query expansion

목표:

- `_supplement_section_seed_docs()`의 하드코딩을 설정 기반 보조 retrieval로 대체

작업:

1. `financial_ontology.json` 초안 생성
2. planner 또는 extractor가 `target_metric`을 구조화해 반환
3. retrieval이 `preferred_sections`, `row_patterns`, `requires_components`를 읽어
   - 보조 query 생성
   - section bias 생성

성공 기준:

- `comparison_005`, `comparison_006`에서
  - 특정 숫자 하드코딩 없이
  - `연구개발 활동` source를 다시 seed에 올릴 수 있음

진행 메모:

- 1차 thin ontology는 이미 연결했다
  - `src/config/financial_ontology.json`
  - `src/config/ontology.py`
- 현재는 retrieval hint / preferred section / row pattern / component keyword / planner prior만 ontology를 읽는다
- 아직 `router` 전체를 ontology-driven prompt로 바꾸지는 않았다

### Phase 3. row candidate 추출의 위치 이동

목표:

- ratio row / component row 추출을 fallback이 아니라 앞단 기본 컨텍스트로 이동

작업:

1. `% / 비중 / 비율 / %p` 질문이면
   - row candidates를 evidence 이후가 아니라 operand planning 전 기본 입력으로 제공
2. `source_context + raw_row_text + header context` 조합 유지

성공 기준:

- planner는 "operand 0개"보다
  - row candidates를 보고 formula를 고르는 역할에 집중

진행 메모:

- `%p` 질문의 pre-LLM planner short-circuit guard는 제거했다
- planner는 이제 항상 직접 계획을 세운다
- 다만 `%p` 질문에서 non-PERCENT operand를 제거하는 최소 candidate filtering은 남아 있다
- 이 filtering이 정말 필요한 최소 안전장치인지, 아니면 또 다른 duct tape인지 `dev_math_focus` 전체에서 다시 확인해야 한다

### Phase 4. component scan의 독립성 강화

목표:

- `comparison_005`처럼 비대칭 추출이 일어나는 단일 ratio 질문 안정화

작업:

- numerator scan / denominator scan을 독립적으로 유지
- LLM이 아니라 Python이 candidate pool을 두 개로 제공
- planner는 후보를 받아 formula를 선택

성공 기준:

- `comparison_005`는
  - direct ratio row가 있으면 `A`
  - 없으면 `연구개발비용`, `매출액` 후보 2개로 `(A / B) * 100`

### Phase 5. direction hint 최소주의 검증

목표:

- `direction_hint`는 남기되, operation별 렌더링 규칙이 다시 커지지 않게 관리

질문:

- `direction_hint` 없이도 renderer가 안정적인가?
- `direction_hint`는 유지하되 operation 텍스트 의존을 더 줄일 수 있는가?

실험:

- 현행 renderer
- direction_hint만 유지하고 operation 텍스트 의존을 더 줄인 renderer

## 지금 당장 하지 않을 것

- full GraphRAG
- self-correction loop
- cross-document reasoning
- table-to-sql
- renderer에 새로운 operation별 문장 템플릿 추가

지금은 계산 경로를 더 영리하게 만드는 것보다,
**어느 층이 문제인지 분리하고 retrieval/source 문제를 retrieval에서 해결하는 것**이 우선이다.

## 다음 세션 체크리스트

1. `dev_math_focus_evalonly_2026-04-28`에서 남은 실패 문항을 retrieval / evaluator / answer completeness로 분리
2. `comparison_005`, `comparison_006` 기준 row candidates를 fallback이 아니라 기본 planning input으로 옮기는 스파이크
3. ontology를 `operating_margin` 외 한 metric family 더 늘렸을 때 retrieval/source 품질이 유지되는지 확인
4. rescue path의 특정 숫자 하드코딩을 더 줄일 수 있는지 확인
5. `run_eval_only.py`를 기준 fast regression loop로 계속 사용할지, source bundle 관리 규칙을 문서화할지 결정

## 빠른 회귀 루프 메모

현재 full `benchmark_runner`는 cache signature에 runner hash가 포함되어 있어, 코드가 조금만 바뀌어도 re-ingest를 유발하기 쉽다.

따라서 math 실험의 기본 루프는 다음 순서로 잡는다.

1. `src/ops/debug_math_workflow.py`
2. `src/ops/run_eval_only.py`
3. 마지막에만 full `benchmark_runner`

주의:

- `run_eval_only.py`는 source output dir의 persisted store가 실제로 채워져 있어야 한다
- `latest`처럼 중간에 끊긴 결과 번들은 source로 쓰지 않는다
