# Portfolio Deep-Dive Q&A

이 문서는 DART financial RAG 프로젝트를 면접에서 깊게 설명하기 위한
질문/답변 노트다. 짧은 소개는
[portfolio_interview_narrative.md](portfolio_interview_narrative.md)를 먼저
보고, 이 문서는 follow-up 질문에 대비할 때 사용한다.

## 1. Project Positioning

### Q1. 이 프로젝트를 한 문장으로 설명하면?

Korean DART 공시 문서 위에서 numeric financial QA를 수행하되, 최종 답변
텍스트가 아니라 evidence, operands, formula, calculation trace, critic
state, reviewer gate로 답변을 검증하는 contract-driven Agentic RAG
runtime입니다.

핵심은 "모델이 그럴듯하게 답했다"가 아니라 "어떤 근거와 계산 계약으로 이
답을 accept했는지 감사할 수 있다"입니다.

### Q2. 이 프로젝트는 일반 RAG와 뭐가 다른가?

일반 RAG는 보통 retrieval chunk와 final answer를 중심으로 봅니다. 이
프로젝트는 그 사이의 runtime state를 더 중요하게 봅니다.

- 어떤 row/table/period에서 숫자를 가져왔는가
- 그 숫자가 어떤 operand slot에 들어갔는가
- 어떤 formula가 실행됐는가
- source-visible display와 계산 결과가 어떻게 보존됐는가
- final answer가 canonical trace를 따랐는가
- critic과 artifact integrity가 final close를 허용했는가

Financial QA에서는 관련 chunk를 찾았어도 wrong row, wrong subtotal, wrong
period, wrong unit이면 틀린 답입니다. 그래서 final answer만 평가하지 않고
trace contract를 평가합니다.

### Q3. 이 프로젝트의 claim boundary는 어디까지인가?

새 모델, SOTA TableQA, 범용 agent framework를 주장하지 않습니다. Claim은
systems engineering입니다.

- LLM semantic planning과 deterministic execution을 분리했다.
- DART 문서 구조와 numeric provenance를 runtime state로 보존했다.
- benchmark regression을 회사명/질문ID runtime branch가 아니라 일반
  contract fix로 닫았다.
- reviewer가 lightweight command로 readiness와 trace surface를 확인할 수
  있게 했다.

최신 expanded structural store-fixed replay는 `9 / 9` numeric PASS지만, 이건
프로젝트의 현재 gate evidence이지 일반 TableQA 성능 주장으로 말하지 않습니다.

## 2. Problem And Failure Modes

### Q4. 왜 financial RAG가 특히 어렵나?

공시 문서의 숫자는 문맥이 강합니다. 같은 숫자처럼 보여도 row label, column
header, period, consolidation scope, unit, subtotal 여부가 달라지면 의미가
바뀝니다. 예를 들어 "차입금" 관련 질문에서 current-period debt row 대신
prior-period debt row를 묶으면 formula는 정확히 실행돼도 답은 틀립니다.

즉 실패가 retrieval miss만이 아닙니다. 관련 chunk 안에서도 binding failure가
날 수 있습니다.

### Q5. 답변이 맞아 보이는데도 틀릴 수 있는 대표 패턴은?

대표적으로 다섯 가지입니다.

- citation은 맞지만 숫자가 wrong row에서 온 경우
- period/current/prior가 뒤바뀐 경우
- source display unit과 계산 unit이 어긋난 경우
- final text는 맞는데 public calculation trace가 stale한 경우
- aggregate subtask의 correct operand가 later direct evidence repair에 의해
  overwrite되는 경우

마지막 두 패턴이 PR #78의 핵심이었습니다.

### Q6. final answer text만 보면 안 되는 이유는?

`KBF_T2_018` 같은 경우 final answer와 evidence에는 `3,146,409`,
`1,847,775`, `70.28%`가 보였지만, public `calculation_result` /
`calculation_plan` projection이 stale할 수 있었습니다. 사람은 답을 맞게
봤다고 느낄 수 있지만 evaluator나 downstream caller가 trace를 보면 다른
값을 읽을 수 있습니다.

그래서 "text가 맞다"와 "runtime contract가 맞다"를 분리해서 봐야 합니다.

## 3. Architecture

### Q7. 전체 runtime flow는 어떻게 되나?

큰 흐름은 다음과 같습니다.

```text
User question
  -> Orchestrator plan
      -> Analyst numeric artifacts
      -> Researcher narrative artifacts
      -> Critic reports
  -> Orchestrator merge
  -> Final answer + task_artifact_trace
```

Numeric path만 보면:

```text
retrieve/evidence
  -> reconcile_plan
  -> operand extraction
  -> formula/calculator
  -> aggregate subtasks
  -> public projection
```

최종 답변은 이 state 위에 얹히는 presentation layer입니다.

### Q8. Agentic이라고 부르는 이유는?

free-form chat agent라서가 아니라, 역할과 artifact handoff가 분리되어 있기
때문입니다.

- Orchestrator: query decomposition과 final merge
- Analyst: numeric extraction, formula planning, calculation
- Researcher: narrative/context evidence
- Critic: grounding, target refs, acceptance reasons, blocking issues

다만 현재 핵심 claim은 "agent가 자율적으로 생각했다"가 아닙니다. `tasks`,
`artifacts`, `evidence_pool`, `critic_reports`, `task_artifact_trace` 같은 typed
ledger state로 handoff를 inspectable하게 만든 것입니다.

### Q9. `task_artifact_trace`는 왜 중요한가?

면접에서 이렇게 답하면 됩니다:

`task_artifact_trace`는 final answer 뒤의 runtime integrity projection입니다.
어떤 task가 있었고, 어떤 artifact가 생성됐고, integrity issue가 있었는지
caller/reviewer가 compact하게 볼 수 있습니다.

이게 없으면 final answer text와 내부 계산 trace가 어긋나도 외부에서 알기
어렵습니다.

### Q10. `resolved_calculation_trace`와 top-level calculation field는 뭐가 다른가?

현재 canonical numeric state는 `resolved_calculation_trace`와 artifact입니다.
오래된 top-level calculation/debug field는 compatibility bridge에 가깝습니다.

PR #78에서 중요했던 것도 이 경계입니다. final answer의 source-visible numeric
surface가 public projection에 반영되지 않으면, canonical trace와 compatibility
surface가 어긋날 수 있습니다. 그래서 final-answer surface operand를 projected
calculation trace로 sync하는 contract를 추가했습니다.

## 4. LLM Semantics vs Deterministic Execution

### Q11. LLM은 어디에 쓰고 code는 어디에 쓰나?

LLM은 semantic 판단에 씁니다.

- intent 파악
- concept interpretation
- formula planning support
- narrative evidence interpretation

Code는 execution과 validation에 씁니다.

- arithmetic
- unit handling
- dependency binding
- dedupe and ordering
- provenance checks
- final rendering
- artifact integrity checks

숫자 계산을 LLM에게 맡기는 것이 아니라, LLM이 계획을 보조하고 deterministic
code가 실행합니다.

### Q12. 왜 이런 분리가 필요한가?

금융 숫자는 작은 오류가 치명적입니다. LLM이 산술과 단위 변환까지 자유롭게
하면 그럴듯한 답을 만들 수 있지만, 어떤 operand를 썼는지 재현하기 어렵습니다.

반대로 deterministic code는 의미 판단을 잘 못합니다. 그래서 LLM은 meaning,
code는 execution이라는 경계를 둡니다.

### Q13. "neuro-symbolic"이라고 말해도 되나?

말할 수는 있지만 조심해야 합니다. 새 알고리즘 이름처럼 말하지 말고, 이
프로젝트에서는 "LLM semantic planning + deterministic numeric execution"의
역할 분리를 설명하는 shorthand라고 말해야 합니다.

## 5. Retrieval And Evidence

### Q14. structural retrieval이 왜 필요했나?

DART 공시는 섹션, 표, 주석, row/column header가 답의 일부입니다. 일반 text
chunk만으로는 관련 문단을 찾더라도 숫자가 어느 row/period에 속하는지 약해질
수 있습니다.

그래서 structural selective ingest는 section/table metadata, deterministic
prefix, row/header context를 evidence state에 남깁니다.

### Q15. plain retrieval `5 / 9`와 structural `9 / 9`를 어떻게 설명해야 하나?

최신 structural replay는 `9 / 9` numeric PASS입니다. 가장 최근 plain retrieval
comparison은 `5 / 9`이고, PR #78 이후 같은 코드 상태로 다시 rerun한 것은
아닙니다.

따라서 이렇게 말해야 합니다:

- structural `9 / 9`는 현재 structural quality gate다.
- plain `5 / 9`는 diagnostic baseline evidence다.
- 이 비교로 broad leaderboard를 주장하지 않는다.
- plain failure는 display/unit, denominator, row-binding failure taxonomy를
  보여주는 데 사용한다.

### Q16. `seed_retrieved_docs`까지 evidence로 볼 수 있게 한 이유는?

graph expansion이나 reranking 과정에서 relevant raw chunk가 final
`retrieved_docs` window 밖으로 밀릴 수 있습니다. 그렇다고 source-grounded
operand가 사라지면 answer trace가 약해집니다.

그래서 active required-operand와 provenance contract를 만족하면 seed candidate를
evidence로 승격할 수 있게 했습니다. 단, 이것은 topic-specific fallback이 아니라
evidence preservation rule입니다.

## 6. Numeric Pipeline

### Q17. `reconcile_plan`은 무엇을 하나?

질문에 필요한 operand가 무엇인지, 어떤 evidence candidate가 그 operand를
채울 수 있는지 정리합니다. 단순히 "숫자를 뽑기" 전에, required operand와
source candidate 사이의 binding 문제를 다룹니다.

예를 들어 ratio라면 numerator와 denominator가 각각 어느 source row에서 와야
하는지, period/scope/unit이 맞는지 확인해야 합니다.

### Q18. numeric extractor와 operand extractor는 어떻게 다른가?

numeric extractor는 text/evidence에서 숫자 surface를 찾는 성격이 강합니다.
operand extractor는 그 숫자가 어떤 required operand slot에 들어갈 수 있는지
계약을 확인합니다.

즉 숫자를 찾는 것과, 그 숫자가 "이 질문의 numerator/current_period/prior_period"
로 맞는지 판단하는 것은 다릅니다.

### Q19. formula/calculator는 어떤 역할인가?

formula/calculator는 이미 grounding된 operands를 deterministic하게 실행합니다.
ratio, difference, growth rate 같은 operation을 계산하고, unit/display policy에
맞춰 result를 구성합니다.

중요한 점은 calculator가 evidence를 만들어내지 않는다는 것입니다. 없는 근거를
산술로 보충하는 것이 아니라, 이미 구조화된 source-backed operands를 조립합니다.

### Q20. aggregate subtasks가 왜 복잡한가?

질문 하나가 여러 lookup task와 downstream ratio/difference task로 쪼개질 수
있기 때문입니다. 하위 task output은 downstream task의 operand가 됩니다.

복잡한 지점은 다음입니다.

- producer task output이 correct인데 later direct evidence가 overwrite할 수 있음
- same table context라도 source row id가 다르면 충돌할 수 있음
- unit repair가 강한 evidence인지 weak repair인지 구분해야 함
- final answer text와 projected calculation trace가 어긋날 수 있음

PR #78의 `SKH_T1_060`은 이 복잡도를 잘 보여줍니다.

## 7. Representative Bugs

### Q21. 가장 어려웠던 bug 하나를 설명한다면?

`SKH_T1_060`을 설명하겠습니다.

문제는 유/무형자산 대비 차입금 비중을 계산하는 ratio였습니다. 필요한 값은
단기차입금, 장기차입금, 사채, 유형자산, 무형자산입니다. focused run에서는
각 task output이 맞게 나왔지만, aggregate repair 단계에서 direct evidence row가
correct task-output operand를 덮어쓸 수 있었습니다.

이게 어려운 이유는 "같은 retrieved table context에 있다"만으로는 충분하지
않기 때문입니다. source row id가 disjoint이고 value가 conflict하면, direct
evidence가 task output보다 항상 강하다고 볼 수 없습니다.

Fix는 source-row provenance를 보고 disjoint conflicting direct slot이 correct
task-output source slot을 overwrite하지 못하게 하는 것이었습니다. 동시에
period-prefixed operand label을 table row label과 맞추기 위해 periodless
table-label metadata lookup도 보강했습니다.

### Q22. `KBF_T2_018` bug는 뭐였나?

이 문제는 final answer/evidence는 맞는데 public trace가 stale할 수 있다는
문제였습니다.

질문은 신용손실충당금전입액 증가율이었고, source-visible values는:

- current: `3,146,409`
- prior: `1,847,775`
- growth: `70.28%`

final answer에는 맞는 값이 보였지만 `calculation_result`,
`calculation_plan`, `answer_slots`가 stale하면 evaluator나 downstream consumer가
다른 trace를 볼 수 있습니다.

Fix는 final-answer numeric surface와 evidence operands를 projected growth trace에
sync하는 것이었습니다.

### Q23. `KAB_T1_066`은 왜 demo case로 좋은가?

작고 설명하기 좋기 때문입니다. CIR 계산 하나에 세 가지 failure가 들어있습니다.

- plausible but wrong denominator row
- direct-support guard over-blocking correct lookup
- final prose using stale component display

현재 demo answer는:

```text
2023년 CIR은 37.47%입니다. 계산: 판매비와관리비 4,355억원 / 경비차감전영업이익 11,623억원.
```

둘 다 같은 MDA table에서 source-visible하게 나옵니다. 그래서 reviewer demo로
좋습니다.

## 8. Evaluation And Gates

### Q24. 왜 RAGAS/faithfulness만으로 부족한가?

Faithfulness는 useful signal이지만, numeric QA에서는 충분하지 않습니다.

예를 들어 answer가 cited context와 모순되지 않아도 wrong row나 wrong period를
쓸 수 있습니다. 또는 final answer text는 맞는데 calculation trace가 stale할 수
있습니다.

그래서 numeric evaluator는 다음을 봐야 합니다.

- numeric equivalence
- operand grounding
- formula correctness
- source references
- rendered display
- retrieval support
- artifact integrity

### Q25. `numeric_final_judgement = null`은 실패인가?

항상 실패는 아닙니다. narrative 또는 mixed question에서 numeric final
judgement가 not-applicable일 수 있습니다. faithfulness, completeness,
retrieval, error-rate signal이 건강하면 `null`을 failure로 단정하지 않습니다.

다만 numeric question인데 필요한 trace가 있는데도 judgement가 없거나 stale하면
그건 contract issue로 봐야 합니다.

### Q26. store-fixed `eval-only`는 왜 사용했나?

parser/ingest를 바꾸지 않은 runtime/evaluator/rendering/projection 변경은 기존
store를 재사용해도 됩니다. `eval-only`는 parse/ingest/screening은 생략하지만,
current code path로 agent answer generation과 evaluator를 다시 실행합니다.

이렇게 하면 full fresh ingest 비용을 피하면서도 runtime regression을 end-to-end로
확인할 수 있습니다.

### Q27. 최신 검증 상태를 어떻게 말할까?

면접에서는 이렇게 말하면 됩니다.

- latest expanded structural store-fixed eval-only: `9 / 9` numeric PASS
- full unittest discovery: `1345` tests OK at the PR #78 validation point
- runtime domain-term audit: passed with `215` reviewed literals
- `portfolio_demo`: `Readiness: ready`
- `portfolio_review_gates`: aggregate `Status: ready`

숫자는 "그 시점의 gate evidence"로 말하고, SOTA claim처럼 말하지 않습니다.

## 9. Overfitting And Domain Terms

### Q28. benchmark overfitting은 어떻게 막았나?

원칙은 benchmark를 answer key로 쓰지 않는 것입니다.

- runtime branch에 company name, question ID, metric-specific keyword bundle을
  넣지 않는다.
- domain vocabulary는 ontology, retrieval policy, config, documented data로
  이동한다.
- runtime code는 slot coverage, evidence diversity, provenance check,
  structured row/header matching, dependency binding 같은 generic mechanism만
  구현한다.
- `python -m src.ops.audit_runtime_domain_terms`로 runtime domain literals를
  감시한다.

PR #78도 KBF/SKH를 직접 hard-code하지 않고 projection/provenance contract로
고쳤습니다.

### Q29. 그래도 benchmark에 맞춘 것 아닌가?

좋은 follow-up입니다. 답은 "benchmark가 failure를 드러낸 것은 맞지만, fix는
benchmark-specific하지 않다"입니다.

예를 들어 `SKH_T1_060`에서 추가한 것은 회사명이나 "차입금" 특별 rule이 아니라:

- source-row id가 disjoint하고 value conflict가 있으면 direct evidence가
  task-output source slot을 overwrite하지 못하게 하는 provenance rule
- leading period marker를 제거해 table label과 operand label을 matching하는
  generic table-label rule

이런 rule은 다른 회사/metric에도 적용되는 일반 contract입니다.

## 10. Tradeoffs And Limitations

### Q30. 이 코드가 왜 이렇게 복잡한가?

복잡한 이유는 여러 failure layer를 한 경로에서 다뤄야 하기 때문입니다.

- retrieval candidate
- evidence schema
- reconcile plan
- operand extraction
- formula/calculator
- aggregate subtask dependency
- final projection/rendering
- evaluator-facing trace

다만 이 복잡도는 무조건 좋은 것은 아닙니다. 그래서 최근에는 문서화와 refactor
plan을 통해 core runtime, review trace, debug/eval/experimental surface를
분리하려고 했습니다. 지금 당장은 기능 리팩터링보다 claim boundary와 면접
설명이 더 ROI가 높다고 판단했습니다.

### Q31. 지금 남은 가장 큰 한계는?

세 가지입니다.

- benchmark size가 아직 제한적이므로 broad generalization claim은 조심해야 함
- FinancialAgent calculation path가 여전히 길고, owner boundary를 더 분리할
  여지가 있음
- cache serving, retrieval bypass, automatic cache writes, LLM critic final
  authority는 intentionally disabled 상태라 production feature로 주장하면 안 됨

### Q32. 다음 기술 작업을 한다면 무엇을 하겠나?

면접 답변으로는 이렇게 말하는 것이 좋습니다.

1. core runtime과 review/debug/eval surface를 더 분리한다.
2. numeric pipeline의 owner boundary를 좁혀 calculation/projection repair가 한
   파일에 몰리지 않게 한다.
3. broader benchmark를 추가하되, 먼저 failure taxonomy와 gate contract를
   유지한다.
4. cache consumer는 candidate-only에서 serving으로 바로 올리지 않고 promotion
   risk gate를 추가한다.

## 11. Behavioral Interview Hooks

### Q33. 이 프로젝트에서 가장 중요한 engineering judgement는?

점수 하나를 올리는 patch보다 failure layer를 분류하고, 일반 contract로 고치는
것이 더 중요하다는 판단입니다.

예를 들어 KBF/SKH residual을 바로 hard-code하면 빠르게 점수는 올릴 수 있었지만
프로젝트 claim을 망칩니다. 대신 evidence/projection/provenance contract로
고치고, focused replay 후 full replay, unit tests, audit, docs를 함께 닫았습니다.

### Q34. 실패에서 배운 점은?

Final answer가 맞아 보여도 runtime trace가 틀리면 시스템 품질이 낮다는 점입니다.
LLM/RAG 시스템에서는 "보이는 답"과 "downstream이 읽는 contract"가 다를 수
있습니다.

그래서 acceptance는 text가 아니라 trace, evidence, artifacts, gates의 합으로
봐야 합니다.

### Q35. 팀에서 이 프로젝트를 설명해야 한다면 어떤 원칙을 공유하겠나?

- Benchmark는 answer key가 아니라 failure detector다.
- LLM은 semantic judgement에 쓰고, execution은 deterministic code에 둔다.
- Evidence에 없는 claim을 composer가 만들면 안 된다.
- Raw benchmark artifacts는 commit하지 않고, command/result/interpretation을
  docs에 기록한다.
- Public answer와 public trace가 diverge하면 user-visible answer가 맞아도 bug다.

## 12. Quick Practice Answers

### "왜 이 프로젝트가 좋은 포트폴리오인가?"

단순히 RAG 앱을 만든 것이 아니라, 금융 RAG에서 실제로 문제가 되는 wrong row,
wrong unit, stale trace, provenance overwrite 같은 failure를 runtime contract로
정의하고 검증했습니다. 코드, 테스트, benchmark gate, reviewer command, 방법론
문서까지 남아 있어 결과를 재현하고 검토할 수 있습니다.

### "가장 기술적으로 깊은 부분은?"

`retrieve/evidence -> reconcile_plan -> operand extraction -> formula/calculator
-> aggregate subtasks -> public projection` 사이에서 source-backed operands를
잃지 않는 것입니다. 특히 aggregate subtask output과 direct evidence repair가
충돌할 때 source-row provenance를 기준으로 어느 slot을 유지할지 결정하는 부분이
핵심입니다.

### "리팩터링보다 면접 준비를 선택한 이유는?"

현재 gate는 닫혔고 reviewer commands도 통과했습니다. 추가 리팩터링은 regression
risk가 있고 포트폴리오 가치가 제한적입니다. 반면 면접에서는 왜 이 구조가
필요했는지, 어떤 failure를 어떻게 일반화해서 고쳤는지 설명하는 능력이 더
중요합니다.

### "한계까지 포함해서 솔직하게 말하면?"

이 프로젝트는 broad TableQA benchmark가 아니라 DART financial numeric RAG의
contract-driven runtime 실험입니다. 최신 structural gate는 `9 / 9` PASS지만,
dataset size는 제한적이고 plain comparison은 PR #78 이후 동기화 rerun이
아닙니다. 그래서 결과를 leaderboard가 아니라 failure taxonomy와 engineering
methodology evidence로 제시합니다.
