# Backlog And Next Epics

이 문서는 **현재 backlog와 future epics를 관리하는 living document**다.
즉,

- 끝난 실험의 상세 로그를 계속 누적하지는 않고
- 현재 backlog 우선순위와 future epic 정의를 최신 상태로 유지

하는 용도로 쓴다.

## 현재 판단

현재 시스템은 적어도 아래 기준에서는 이미 실용적인 baseline에 도달했다.

- `dev_math_focus` 전체에서 `Faithfulness 1.000`, `Completeness 1.000`, `Numeric Pass 1.000`
- `comparison_001` 같은 케이스도 이제는
  - 정답 수치가 맞고
  - 계산이 맞고
  - 사용한 operand가 실제 읽은 텍스트에 grounded되어 있으면
  section match와 무관하게 `PASS`

즉 앞으로의 backlog는 대부분 “정답성 복구”보다
**retrieval purity / answer packaging / 구조 일반화**에 가깝다.

## Non-Blocking Quality Debt

다음 항목들은 현재 알고 있지만, 시스템 확장을 멈추고 즉시 고쳐야 하는 blocker로 보지는 않는다.

### 1. Retrieval purity

상태:

- `dev_math_focus`: `Context P@5 0.540`, `Section Match 0.500`
- `dev_fast_focus`: `Context P@5 0.550`, `Section Match 0.406`

의미:

- 필요한 근거는 대부분 찾고 있다
- 다만 top-k에 `주석`, `주주`, `정관` 같은 덜 관련된 섹션이 아직 많이 섞인다

판단:

- 이건 정답성보다는 explainability / retriever hygiene 문제다
- 당장 제품 실패로 보진 않지만, 장기적으로는 정리해야 한다

### 2. `business_overview_001`

상태:

- canonical한 `사업의 개요` 섹션을 이미 찾고 있다
- 하지만 top-k purity가 낮고, 실제 evidence는 `I. 회사의 개요`에서 더 많이 뽑히는 경향이 있다
- 답변은 대체로 맞지만 evaluator가 긴 설명형 답변을 다소 보수적으로 본다

판단:

- retrieval purity
- section alias / dataset 설계
- answer style mismatch

가 함께 섞인 mixed case다.

### 3. `risk_analysis_001`

상태:

- top retrieval은 `위험관리 및 파생거래`로 비교적 건강하다
- 문제는 답변이 `시장/신용/유동성`보다 더 넓게 퍼지며
  `이자율`, `자본위험` 등까지 남긴다는 점이다

판단:

- retrieval 실패가 아니라
- selection / compress / rendering 쪽 quality debt에 가깝다

### 4. 남아 있는 duct tape

예:

- percent operand filtering
- 일부 section seed supplement
- query-type별 section bias 하드코딩

판단:

- 지금 당장 다 지우는 것은 위험하다
- ontology와 candidate input 구조가 충분히 대체한 뒤 하나씩 걷어낸다

## Near-Term Structural Backlog

이 항목들은 “언젠가”가 아니라, 다음 몇 개 스프린트 안에서 실제로 다룰 가치가 큰 구조 과제다.

### 1. Ontology 확장과 하드코딩 축소

현재:

- ontology는 retrieval hint / preferred section / planner prior까지만 얇게 연결됨

다음:

- `operating_margin`, `debt_ratio` 등 metric family 추가
- metric-specific section bias / component scan을 설정 기반으로 더 옮김
- retrieval rescue path를 ontology-driven multi-query expansion으로 치환

### 2. Row / component candidates를 정식 입력 계층으로 승격

현재:

- ratio row / component row 추출은 fallback 냄새가 아직 남아 있음

다음:

- planner 실패 후 우회로가 아니라
- planner가 처음부터 받는 기본 input layer로 올림

### 3. Retrieval diagnostic metric과 final success의 분리 유지

현재:

- `retrieval_hit_at_k`, `section_match_rate`, `P@5`는 diagnostic
- `numeric PASS/FAIL`은 operand grounding 기반

다음:

- 이 원칙을 math 외 경로에도 일관되게 적용할지 검토
- retrieval metric을 정답 판정에 다시 섞지 않도록 주의

## Major Future Epics

이 항목들은 다음 단계의 “큰 장” 후보들이다. 각 Epic은

- 왜 필요한가
- 무엇을 구현할 것인가
- 어디까지 하면 한 phase를 닫을 것인가

를 함께 적는다.

### A. `REFERENCE_NOTE` / note-aware graph expansion

문제:

- 본문 표와 실제 설명 주석이 멀리 떨어져 있는 DART 특성

가치:

- 단일 문서 질의응답 품질을 한 단계 끌어올릴 가능성이 큼
- 현재 문서 구조 기반 pipeline 위에 비교적 자연스럽게 확장 가능

#### 계획

이 Epic은 두 단계로 나눈다.

**Phase 1a. section-path reference**

- parser에서
  - `'III. 재무에 관한 사항'의 '3. 연결재무제표 주석'`
  - `'XII. 상세표'의 '1. 연결대상 종속회사 현황(상세)'`
  같은 **명시적 섹션 경로 참조**를 추출
- chunk metadata에
  - `reference_section_paths`
  - `reference_parent_ids`
  저장
- structure graph에서 `reference_note` relation으로 보존
- graph expansion이 seed chunk 주변의
  - parent
  - sibling
  - table_context
  와 함께 referenced section lead도 추가로 끌어오게 함

**Phase 1b. numbered note reference**

- `(주석 14 참조)`, `(*1)` 같은 표식 추출
- note number를 실제 note section / note chunk로 resolve하는 매핑 추가
- `linked_footnotes` / `note_target_ids` 계열 metadata로 확장
- seed chunk가 note number를 가리키면 검색 없이 graph relation으로 즉시 병합

#### 종료 조건

**Phase 1a 종료 조건**

- section-path reference가 parser metadata와 graph expansion 로그에 실제로 찍힌다
- reference edge를 통해 주석 섹션이 context에 합쳐지는 것을 debug trace에서 확인한다

**Phase 1 전체 종료 조건**

- `"2024년 삼성전자 매출채권 대손충당금이 증가한 원인이 뭐야?"`
  같은 why 질문에서
  - 표의 수치
  - 연결된 주석 설명
  을 함께 사용해 원인을 답할 수 있다

### B. 제한적 self-reflection / retry loop

문제:

- `insufficient_operands`, source miss, missing previous year 같은 실패는
  사람이라면 한 번 더 찾아볼 문제다

가치:

- 1회 재검색 루프만 넣어도 robustness가 크게 올라갈 수 있다

주의:

- 무한 loop가 아니라 bounded retry여야 함

#### 계획

- LangGraph state에
  - `missing_operands`
  - `retry_count`
  - `retry_reason`
  추가
- planner가 `mode=none`으로 죽는 대신
  - `status="needs_more_info"`
  - 부족한 operand 목록
  을 반환하도록 수정
- 상태가 `needs_more_info`이고 `retry_count < 1`이면
  - 부족한 항목을 타겟으로 보조 retrieval를 1회만 수행
  - `retry_count += 1`
- 적용 범위는 처음엔
  - `comparison`
  - `ratio`
  - `growth`
  - 일부 why 질문
  으로 제한

#### 종료 조건

- 실패 재현 케이스에서
  - `"operand 누락 감지 -> 1회 재검색 -> 계산 성공"`
  흐름이 로그에 남는다
- `retry_count`가 1을 넘지 않는다
- retry가 없는 baseline 대비 정답성이 개선되고, latency 증가는 허용 가능한 수준으로 유지된다

### C. Cross-document / cross-company reasoning

문제:

- 지금 구조는 사실상 단일 문서, 단일 기업 중심

가치:

- 사용자 가치가 크고, “시니어 애널리스트 레벨”로 가는 핵심 과제

주의:

- retrieval, operand binding, evaluator까지 모두 다시 설계해야 할 수 있음

#### 계획

- router 또는 별도 metric resolver가
  - 타겟 기업 리스트
  - 타겟 연도 리스트
  를 추출
- retrieval은 기업/문서별로 병렬 실행
- planner 입력은
  - `[삼성전자 컨텍스트]`
  - `[SK하이닉스 컨텍스트]`
  처럼 namespace를 분리
- operand schema에
  - `entity_id`
  - `report_id`
  - `period`
  를 명시적으로 추가해 binding 혼동을 방지
- evaluator도 기업별 ground truth와 cross-company 계산 결과를 분리해서 판정

#### 종료 조건

- `"2024년 삼성전자와 SK하이닉스의 연구개발비 비중 차이를 구해줘"` 같은 질의에 대해
  - 각 기업 문서를 헷갈리지 않고
  - 각 기업의 ratio를 먼저 계산한 뒤
  - 최종 차이값까지 정확히 도출한다

### D. Table-to-SQL / Table-native reasoning

문제:

- 복잡한 재무 표를 텍스트 chunk만으로 해석할 때 row/column 의미가 깨질 수 있음

가치:

- 장기적으로 가장 큰 구조 점프

주의:

- parser / storage / query path를 크게 바꾸는 high-cost epic

## 현재 추천 우선순위

지금 시점의 추천 순서는 아래다.

1. 현재 math baseline과 evaluator 구조를 기준선으로 문서화하고 고정
2. non-blocking quality debt는 backlog로 남기되 당장 deep dive하지 않음
3. 다음 구조 작업은 `REFERENCE_NOTE`의
   - `Phase 1a section-path`
   - `Phase 1b numbered-note`
   순서로 진행
4. 그 다음은 제한적 `self-reflection`
5. cross-document / cross-company는 그 다음 큰 epic으로 둔다

## 지금 당장 하지 않을 것

- `business_overview_001`, `risk_analysis_001`을 score 맞추기용으로 과도하게 패치
- retrieval purity metric만 보고 ranking 로직을 계속 국소 조정
- evaluator 점수를 더 좋게 보이게 하려는 cosmetic patch

핵심 원칙:

- 지금은 **더 좋은 정답을 만들기 위한 구조 개선**을 우선한다
- **이미 맞는 답을 더 점수 잘 받게 만들기 위한 local patch**는 최대한 뒤로 미룬다
