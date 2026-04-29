# 프로젝트 컨텍스트

이 문서는 **현재 상태를 짧게 유지하는 snapshot 문서**다.  
세션이 바뀌거나 기준선이 바뀌면 **덮어써서 최신 상태로 유지**한다.

역사적 실험 기록과 누적 판단은 [DECISIONS.md](DECISIONS.md)를 본다.  
남은 backlog와 다음 큰 구조 과제는 [docs/planning/backlog_and_next_epics.md](docs/planning/backlog_and_next_epics.md)를 본다.

## 현재 기준 상태

- 기준 문서: `삼성전자 2024 사업보고서`
- 기본 retrieval:
  - `Chroma + BM25 + RRF`
  - structure-aware parser / chunking
- 기본 reasoning:
  - evidence-first
  - math 질문은 `formula planner + safe AST evaluator`
- 현재 math evaluator:
  - `display-aware numeric equivalence`
  - `operand grounding`
  - retrieval metric은 diagnostic으로만 사용

## 현재 고정해도 되는 기준선

- math 질문군(`dev_math_focus`)은 현재 기준선으로 고정 가능
  - `Faithfulness 1.000`
  - `Completeness 1.000`
  - `Numeric Pass 1.000`
- broader sanity check(`dev_fast_focus_selective_serial`)에서도
  - math-specialized evaluator 회귀는 현재 보이지 않음

즉 지금은 계산 경로의 정답성보다 **구조 확장**이 다음 우선순위다.

## 현재 해석 원칙

- `final answer correctness`
- `operand grounding`
- `retrieval diagnostic metric`

을 분리해서 본다.

특히:
- `retrieval_hit_at_k`
- `section_match_rate`
- `context_precision_at_k`

는 **retriever 품질을 보는 진단 지표**이지, 최종 정답 판정 자체는 아니다.

## 현재 backlog 해석

다음 항목들은 **blocker가 아니라 non-blocking quality debt**로 본다.

- `business_overview_001`
- `risk_analysis_001`
- retrieval purity debt
- 일부 남은 duct tape

즉 지금은 이 점수들을 맞추기 위한 local patch보다,
다음 구조 과제로 넘어가는 편이 더 낫다.

## 다음 구조 과제 순서

1. `REFERENCE_NOTE Phase 1a`
   - section-path reference graph edge
2. `REFERENCE_NOTE Phase 1b`
   - numbered note reference
3. 제한적 `self-reflection`
   - `retry_count < 1`
   - 우선 `comparison / ratio / growth / why` 질문군만
4. `cross-document / cross-company reasoning`

## 현재 Phase 정의

### `REFERENCE_NOTE Phase 1a`

목표:
- 문서 안의 section-path reference를 graph edge로 연결

종료 조건:
- parser metadata에 reference target이 기록됨
- graph expansion trace에서 `reference_note` relation이 보임
- why 질문에서 표 수치와 참조된 설명 섹션을 함께 사용 가능

### `REFERENCE_NOTE Phase 1b`

목표:
- `(주석 14 참조)`, `(*1)` 같은 numbered note reference 연결

종료 조건:
- note number를 실제 target chunk로 resolve
- seed chunk에서 note target을 검색 없이 graph relation으로 병합 가능

### 제한적 `self-reflection`

목표:
- operand 부족 / source miss에 한해 1회 재검색

종료 조건:
- `operand 누락 감지 -> 1회 재검색 -> 성공` 흐름이 로그에 남음
- 무한 루프 없이 bounded retry 유지

### `cross-document / cross-company reasoning`

목표:
- 기업/문서 경계를 보존한 상태로 비교 계산

종료 조건:
- 복수 기업 metric 비교 질문에서 entity/report/period binding 혼동 없이 정답 도출

## 문서 역할

- [CONTEXT.md](CONTEXT.md)
  - 최신 상태만 유지
- [PLAN.md](PLAN.md)
  - 현재 active plan과 바로 다음 실행 순서만 유지
- [DECISIONS.md](DECISIONS.md)
  - append-only 결정 로그
- [docs/planning/backlog_and_next_epics.md](docs/planning/backlog_and_next_epics.md)
  - backlog와 major epics 관리
