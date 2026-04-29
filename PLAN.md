# 실행 계획

이 문서는 **현재 active plan만 유지하는 실행 문서**다.  
끝난 실험이나 과거 단계는 여기 누적하지 않고 [DECISIONS.md](DECISIONS.md)로 보낸다.

## 현재 목표

다음 구조 확장 순서를 따른다.

1. `REFERENCE_NOTE Phase 1a`
2. `REFERENCE_NOTE Phase 1b`
3. 제한적 `self-reflection`
4. `cross-document / cross-company reasoning`

현재는 **Phase 1a를 구현하고 실제 graph expansion에 태우는 것**이 1순위다.

## 병렬 트랙: Retrospective Scorecard

구조 확장과 별개로, 이미 내린 중요한 기술 결정이 정량적으로 어떤 차이를 만들었는지 남기는 **회고 실험 트랙**을 병렬로 준비한다.

원칙:
- 새 기능 구현과 retrospective scorecard를 섞지 않는다.
- scorecard는 포트폴리오/면접용 evidence track으로 운영한다.
- 시스템 품질 실험과 evaluator 메타-실험을 분리한다.

현재 우선 실험:
1. `Section Match Evaluator vs Operand Grounding Evaluator`
2. `Direct Calc vs Operation Path vs Formula Planner + AST`
3. `Standard Retrieval vs Ontology-Guided Retrieval`

정리 위치:
- 실험 설계와 scorecard 형식은 [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md)의 `Retrospective Scorecard Track` 섹션을 기준으로 본다.

## Active Work

### 1. `REFERENCE_NOTE Phase 1a`

구현 범위:
- section-path reference 추출
- `reference_section_paths`, `reference_parent_ids` metadata 생성
- structure graph에 `reference_note` relation 추가
- graph expansion이 referenced section lead를 함께 가져오게 연결

남은 일:
1. 새 메타데이터가 실제 인덱스에 반영되도록 reindex / reingest
2. graph expansion enabled 상태에서 end-to-end smoke
3. representative why 질문으로 효과 확인

종료 조건:
- debug trace에서 `reference_note` relation 사용 확인
- why 질문에서 표 수치 + 참조 설명 섹션을 함께 사용하는 답변 생성

### 2. `REFERENCE_NOTE Phase 1b`

선행 조건:
- Phase 1a 종료

구현 범위:
- `(주석 14 참조)`, `(*1)` 추출
- note number -> target chunk resolve
- note relation을 graph expansion에 추가

종료 조건:
- numbered note target이 metadata와 graph에 저장됨
- note reference가 실제 answer context에 자동 병합됨

### 3. 제한적 `self-reflection`

선행 조건:
- REFERENCE_NOTE 최소 1차 정착

구현 범위:
- state에 `missing_operands`, `retry_count`, `retry_reason`
- planner가 `needs_more_info` 반환
- `retry_count < 1`일 때만 1회 보조 retrieval

적용 질문군:
- `comparison`
- `ratio`
- `growth`
- 일부 `why`

종료 조건:
- 실패 재현 케이스에서 `1회 재검색 -> 성공` 로그 확인
- retry는 bounded되고 latency 폭증이 없음

### 4. `cross-document / cross-company reasoning`

선행 조건:
- single-document graph/reflection baseline 안정화

구현 범위:
- multi-entity target extraction
- 기업별 병렬 retrieval
- `[기업 A 컨텍스트]`, `[기업 B 컨텍스트]` namespace 분리
- operand schema에 `entity_id`, `report_id`, `period` 추가

종료 조건:
- 복수 기업 ratio / comparison 질문에서 binding 혼동 없이 정답 계산

## 지금 하지 않을 것

- `business_overview_001`, `risk_analysis_001` local patch deep dive
- retrieval purity 점수만 올리기 위한 cosmetic tuning
- evaluator 점수만 좋아 보이게 만드는 local patch

이들은 backlog로 남기고, 현재는 구조 확장을 우선한다.

## 문서 사용 규칙

- 현재 상태 요약: [CONTEXT.md](CONTEXT.md)
- 누적 결정 로그: [DECISIONS.md](DECISIONS.md)
- backlog / future epics: [docs/planning/backlog_and_next_epics.md](docs/planning/backlog_and_next_epics.md)
