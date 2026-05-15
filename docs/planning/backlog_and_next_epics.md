# Backlog And Next Epics

이 문서는 **현재 backlog와 future epics를 관리하는 living document**다.

- 끝난 실험의 상세 로그를 계속 누적하지는 않고
- 현재 backlog 우선순위와 future epic 정의를 최신 상태로 유지

하는 용도로 쓴다.

## 현재 판단

현재 시스템은 단일 문서 기준으로 강한 baseline을 이미 확보했다.

- `dev_math_focus` 전체에서 `Faithfulness 1.000`, `Completeness 1.000`, `Numeric Pass 1.000`
- retrospective scorecard를 통해
  - evaluator fairness
  - formula planner + AST
  - ontology retrieval
  의 효과를 수치로 설명 가능
- single-doc curated core dataset `77`문항과 multi-report 분리셋 `1`문항까지 수동 검수 완료

따라서 다음 backlog의 중심은 “당장 정답률 복구”만도 아니고,  
곧바로 MAS로 확장하는 것도 아니다. 현재 선행 과제는  
**single-agent numeric path 안에서 planner / synthesizer / structured result contract를 먼저 안정화**하는 것이다.

## Active Architecture Bet

현재 가장 중요한 architectural bet은 다음 세 가지다.

| 축 | 현재 판단 |
| --- | --- |
| Topology | 장기적으로는 `Orchestrator -> Analyst / Researcher -> Critic -> Merge`가 유망하지만, 단기적으로는 single-agent graph 안에서 planner / synthesizer 경계를 먼저 닫아야 함 |
| Communication | 자유 대화보다 `task ledger + artifact store`가 적합 |
| Memory | generic long-term memory보다 `report-scoped cache`가 우선 |

즉 앞으로의 epic은 `REFERENCE_NOTE`나 retry patch 자체보다,  
**planner / synthesizer / artifact boundary와 shared state contract를 먼저 고정하는 것**을 기준으로 정렬한다.

## Non-Blocking Quality Debt

다음 항목들은 현재 알고 있지만, 시스템 확장을 멈추고 즉시 고쳐야 하는 blocker로 보지는 않는다.

### 1. Retrieval purity

상태:

- `dev_math_focus`: `Context P@5 0.540`, `Section Match 0.500`
- `dev_fast_focus`: `Context P@5 0.550`, `Section Match 0.406`

판단:

- 필요한 근거는 대부분 찾고 있다
- 다만 top-k에 `주석`, `주주`, `정관` 같은 덜 관련된 섹션이 아직 섞인다
- 정답성보다는 explainability / retriever hygiene 문제다

### 2. `business_overview_001`

판단:

- canonical section을 이미 찾는다
- 남은 문제는 retrieval purity + section alias + answer style mismatch가 섞인 mixed case다
- MAS 전환을 멈출 blocker는 아니다

### 3. `risk_analysis_001`

판단:

- retrieval보다는 selection / compress / formatting debt에 가깝다
- Researcher / Critic 분리 후 다시 볼 가치가 크다

### 4. 남아 있는 duct tape

예:

- percent operand filtering
- 일부 section seed supplement
- query-type별 section bias 하드코딩

판단:

- 지금 당장 다 지우는 것은 위험하다
- Analyst / Researcher / Critic 역할이 정리된 뒤 하나씩 걷어낸다

## Near-Term Structural Backlog

이 항목들은 다음 몇 개 스프린트 안에서 실제로 다룰 가치가 큰 구조 과제다.

### 0. Planner and final synthesizer contract

현재:

- concept-only ontology와 LLM concept planner가 들어왔고
- planner feedback을 이용한 `pre_calc_planner` 재사용 replan loop도 생겼다

하지만:

- planner가 모은 재료와 최종 답변 요구사항 사이의 contract는 아직 약하다
- `difference`, `lookup`, `ratio` 결과가 answer-friendly structured result로 충분히 남지 않는다

다음:

- planner는 재료 수집 task에 집중
- final synthesizer는 원본 질문 충족 여부와 최종 refusal을 책임
- `planner_feedback -> replan -> close/refusal` loop를 benchmark 문항으로 고정

종료 조건:

- `NAV_T1_071`류 질문에서 raw value와 derived value 요구가 함께 닫히고,
- replan loop가 불필요한 중복 task를 만들지 않으며,
- 재료 부족 시 aggregate 단계에서 명시적 final refusal이 나온다

### 1. Curated dataset 운영 경로 정리

현재:

- `benchmarks/datasets/single_doc_eval_full.curated.json`
- `benchmarks/datasets/multi_report_eval_full.curated.json`

이 canonical source of truth가 존재한다.

하지만:

- 일부 benchmark profile
- 일부 retrospective script
- 일부 evaluator 기본 경로

는 아직 `benchmarks/eval_dataset.canonical.json`, `benchmarks/eval_dataset.math_focus.json` 같은 legacy dataset을 기본값으로 유지하고 있다.

다음:

- profile별 dataset path를 의도적으로 정리
- curated dataset과 legacy experiment dataset의 역할을 문서상으로도 분리
- single-doc / multi-report / multi-company 셋의 운영 규칙을 명시

### 2. MAS skeleton + typed state schema

현재:

- single-agent graph state는 존재하지만 task ledger와 artifact schema는 약하다

다음:

- `Task`
- `TaskResult`
- `EvidenceItem`
- `CriticReport`
- `FinalReport`

같은 typed object를 기준으로 state를 재정의

### 3. Report-scoped cache

현재:

- cache는 주로 store/contextual ingest 재사용 쪽에 집중되어 있음

다음:

- `company + report_type + rcept_no + year + metric + source_section`
  수준의 cache key를 명시
- retrieval을 완전히 생략할 수 있는 값과, 근거 확인이 필요한 값을 구분

### 4. Runtime critic과 offline evaluator의 역할 분리

현재:

- evaluator 자산은 강하지만 runtime critic은 아직 명시적 agent가 아님

다음:

- runtime critic은 task acceptance와 final merge 보호용
- offline evaluator는 benchmark/scorecard용

### 5. Self-reflection을 retry rule이 아닌 capability로 재정의

현재:

- self-reflection branch는 experimental checkpoint이며 rule drift 위험이 있음

다음:

- `ReflectionPlan`
- deterministic executor
- `VerificationReport`

구조로 재설계

## Major Future Epics

### A. MAS Skeleton

문제:

- 지금은 강한 single-agent 파이프라인은 있으나, 역할 분리/통신 계약이 약하다

구현 목표:

- Orchestrator / Analyst / Researcher / Critic 역할 정의
- shared state와 artifact schema 고정
- task ledger 기반 control flow 설계

종료 조건:

- 단일 질문이 task 단위로 분해되고
- 각 task 결과가 구조화된 artifact로 state에 기록되며
- 최종 merge가 그 artifact만 보고 가능하다

### B. Analyst Agent Migration

문제:

- 현재 numeric/evidence path가 하나의 큰 graph 안에 뭉쳐 있다

구현 목표:

- 아래를 Analyst 역할로 캡슐화
  - ontology-guided retrieval
  - operand extraction
  - formula planning
  - AST execution
  - calc verification

종료 조건:

- Analyst가 하나의 numeric task를 독립 처리하고
- 입력/출력이 task artifact 수준으로 분리된다

### C. Critic Stack

문제:

- grounding, binding, scope, completeness가 서로 다른 층의 검증인데 아직 runtime에선 분리도가 낮다

구현 목표:

- deterministic critic
  - grounding
  - unit
  - binding
  - task coverage
- LLM critic
  - relevance
  - scope overreach
  - coherence

종료 조건:

- critic verdict가 최종 answer acceptance의 필수 artifact가 된다

### D. Researcher Agent

문제:

- why/context 추출과 numeric reasoning이 한 파이프라인에 섞여 있다

구현 목표:

- semantic retrieval
- document-structure expansion
- note-aware traversal
- why/context summary

를 Researcher 역할로 분리

종료 조건:

- 비정형 task를 Researcher가 독립 처리하고 evidence artifact를 반환한다

### E. `REFERENCE_NOTE` / note-aware graph expansion

현재 판단:

- phase 1a wiring은 살아 있음
- 하지만 현재 질문셋에선 base retrieval이 이미 강해 marginal gain이 작았다

따라서:

- MAS 전환을 멈추고 이것부터 깊게 파지 않는다
- Researcher capability로 편입한 뒤
- `why / causality / multi-hop` benchmark가 생기면 다시 ablation한다

후속 단계:

- `Phase 1b` numbered note reference
- `causality_focus` benchmark

### F. Agentic Self-Reflection

문제:

- 지금 checkpoint 구현은 bounded retry core를 보여주지만, rule drift 우려가 있다

구현 목표:

- retry objective를 LLM이 구조화
- deterministic retrieval executor가 실행
- critic/verification이 retry result 수용 여부를 판정

중요 지표:

- `reflection_trigger_rate`
- `recovery_rate`
- `false_recovery_rate`
- `latency_delta`

종료 조건:

- bounded retry 1회 내에서 false recovery를 억제하면서 recovery를 재현

### G. Cross-document / Cross-company Reasoning

문제:

- 지금 구조는 사실상 단일 문서, 단일 기업 중심

구현 목표:

- Orchestrator가 multi-entity task를 분해
- retrieval을 entity/report namespace별로 병렬 수행
- Analyst가 entity-aware binding으로 계산

종료 조건:

- `"2024년 삼성전자와 SK하이닉스의 연구개발비 비중 차이를 구해줘"` 같은 질문을
  entity/report/period 혼동 없이 처리

## 현재 추천 우선순위

1. MAS skeleton과 artifact schema 고정
2. Analyst / Critic 분리
3. Researcher 분리
4. agentic self-reflection 재설계
5. `REFERENCE_NOTE`와 report-scoped cache를 capability로 편입
6. cross-company 확장

## 지금 당장 하지 않을 것

- `business_overview_001`, `risk_analysis_001`을 score 맞추기용으로 과도하게 패치
- retrieval purity metric만 보고 ranking 로직을 계속 국소 조정
- rule-based self-reflection 분기를 더 늘리기
- generic long-term memory를 먼저 설계하기

핵심 원칙:

- 지금은 **더 좋은 topology와 communication contract를 만드는 구조 개선**을 우선한다
- **이미 맞는 답을 더 점수 잘 받게 만들기 위한 local patch**는 뒤로 미룬다
