# Agent Operating Rules

이 저장소에서 일하는 자동화 에이전트는 코드를 고치기 전에 이 문서를 먼저 적용한다. 목표는 점수 맞추기식 패치를 줄이고, 시간/토큰/실험 비용을 통제하면서 일반화 가능한 변경만 남기는 것이다.

구현 단위의 세부 계약은 `docs/architecture/agent_runtime_contract.md`를 따른다. 이 문서와 충돌하면 더 구체적인 runtime contract를 우선하고, 원칙 변경이 필요하면 두 문서를 함께 갱신한다.

## Core Principles

### Domain Knowledge Boundary

- DART/financial-domain vocabulary must live in ontology, retrieval policy, config, or documented data artifacts, not in runtime control-flow code.
- Runtime code may implement generic mechanisms only: slot coverage, entity/marker extraction, evidence diversity, provenance checks, structured row/header matching, dependency binding, dedupe, ordering, and validation.
- Do not add Korean/English financial terms, company names, benchmark IDs, report-specific phrases, or metric-specific keyword bundles directly inside agent routing, retrieval, evidence selection, calculation, or answer composition code unless they are parser-structure terms required to recover the DART document shape.
- When a benchmark exposes a missing concept, first classify the gap as ontology, retrieval policy, parser structure, planner contract, evidence schema, or evaluator definition. Add domain vocabulary to the appropriate declarative layer, then make runtime code consume that layer generically.
- If a temporary keyword is needed to unblock diagnosis, mark it as diagnostic-only, keep it out of committed runtime paths, and replace it with policy/ontology-driven behavior before commit.
- LLMs may propose candidate concepts, sections, and slots, but final runtime behavior must be grounded against retrieved evidence or structured store artifacts. The fallback for LLM uncertainty is not hard-coded vocabulary in code; it is better policy/schema plus traceable validation.
- Any PR/change that adds domain terms to runtime code must explain why the same behavior cannot be represented in ontology/policy/config. If that explanation is weak, stop and refactor the design.

1. **Benchmark를 답안지로 쓰지 않는다.**
   - 특정 회사, 특정 질문, 특정 평가 row를 맞추기 위한 runtime branch를 추가하지 않는다.
   - benchmark에서 발견한 문제는 `ontology`, `retrieval_policy`, `parser`, `planner contract`, `evidence schema` 중 어느 층의 일반 문제인지 먼저 분류한다.
   - 예외가 필요하면 코드 분기가 아니라 명명된 policy/config/data로 분리하고, 왜 일반 정책인지 문서화한다.

2. **LLM은 semantics, code는 execution.**
   - LLM은 intent, concept, evidence interpretation처럼 의미 판단에 쓴다.
   - 산술, 단위 변환, dependency binding, dedupe, ordering, validation은 deterministic code로 처리한다.
   - deterministic fallback은 없는 근거를 만들어내는 답변 생성이 아니라, 이미 구조화된 row/evidence를 조립하는 경우에만 허용한다.

3. **Evidence-first.**
   - 답변 품질 개선은 먼저 retrieval/evidence coverage를 확인한 뒤 진행한다.
   - answer composer는 evidence에 없는 claim을 추가하지 않는다.
   - numeric answer는 `structured_result`, `resolved_calculation_trace`, `evidence_items`의 계약을 우선한다.

4. **작게 검증하고 크게 돌린다.**
   - 먼저 unit/contract test로 실패 층을 좁힌다.
   - 그 다음 focused benchmark 또는 eval-only를 실행한다.
   - full benchmark는 필요한 입력/store/cache 조건을 확인한 뒤에만 실행한다. 장시간 결과 파일이 생성되지 않으면 중단하고 원인을 기록한다.

5. **실험 산출물과 소스 변경을 분리한다.**
   - `benchmarks/results/**`, 임시 profile/dataset, local store/cache는 기본적으로 commit 대상이 아니다.
   - 문서/코드 변경과 실험 결과는 별도로 보고한다.
   - 커밋 전에는 stage 대상에 실험 결과가 섞였는지 확인한다.

6. **Parser regex와 agent decision rule을 구분한다.**
   - parser regex는 DART 문서 구조 복원용으로 허용된다.
   - retrieval/routing/answer 경로의 keyword rule은 policy/config로 분리하거나 semantic planner로 대체한다.
   - parser 구조 규칙을 benchmark answer 보정 용도로 사용하지 않는다.

7. **Routing guardrail은 intent를 덮어쓰는 최후 수단이다.**
   - 단일 keyword만으로 semantic fast-path를 차단하지 않는다.
   - guardrail은 operation signal이 함께 있을 때만 적용한다.
   - routing 변경은 confusion benchmark나 전용 unit test로 확인한다.

## Change Workflow

1. **Classify**
   - bug, architecture cleanup, benchmark regression, docs-only 중 하나로 분류한다.
   - 관련 owner file과 계약 테스트를 먼저 찾는다.

2. **Design**
   - 새 분기를 추가하기 전에 기존 policy/config/ontology로 표현할 수 있는지 확인한다.
   - code path에 케이스별 문자열이 들어가야 한다면 중단하고, policy data로 이동할 수 있는지 검토한다.

3. **Implement**
   - 변경 범위를 최소화한다.
   - unrelated refactor는 하지 않는다.
   - 사용자 변경이나 untracked experiment artifact를 되돌리지 않는다.

4. **Verify**
   - 최소 관련 test를 먼저 돌린다.
   - 그 다음 `python -m unittest discover -s tests`를 돌릴 수 있으면 돌린다.
   - benchmark가 필요하면 focused/eval-only를 우선한다.

5. **Report**
   - 무엇을 바꿨는지, 어떤 원칙 때문에 그렇게 했는지, 어떤 검증을 했는지 짧게 보고한다.
   - benchmark가 실패/중단되면 코드 실패인지 환경/시간/store 문제인지 구분한다.

## Design Rules For This Project

- Runtime default는 일반 사용자 질문에 맞춘다. benchmark profile은 별도 profile/config로 둔다.
- Canonical ingest는 `src/config/runtime_contract.py`의 `CANONICAL_INGEST_PROFILE_ID`를 기준으로 한다. 다른 ingest는 명시적 experimental profile로만 쓴다.
- Retrieval 변경은 `retrieval_debug_trace`로 query bundle, filter, selected chunk, policy trace를 남겨야 한다.
- Agentic workflow는 task ledger와 artifact store를 기준으로 설계한다. 자유 텍스트 agent chat은 상태 계약으로 쓰지 않는다.
- `src/config/retrieval_policy.py` 같은 policy 파일은 runtime branch를 숨기는 장소가 아니라, 검토 가능한 domain prior 목록이다.
- ontology는 concept/alias/binding policy를 담고, benchmark metric recipe book이 되면 안 된다.
- evaluator는 평가 편의를 위해 더 많은 normalization을 가질 수 있지만, agent runtime은 evaluator trick을 따라가면 안 된다.
- answer formatting은 evidence와 query intent를 보존하는 범위에서만 조정한다.

## Stop Conditions

다음 상황에서는 코드를 계속 고치기 전에 사용자에게 보고한다.

- full benchmark가 5분 이상 결과 파일 없이 멈춘 경우
- 새 rule이 특정 회사/질문 이름 없이는 설명되지 않는 경우
- 점수 개선이 evidence faithfulness를 낮추는 경우
- 테스트를 통과시키려면 기존 계약을 약화해야 하는 경우
- 실험 산출물을 commit해야 할지 애매한 경우
