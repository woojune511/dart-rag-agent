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
곧바로 MAS를 더 크게 확장하는 것도 아니다. 현재 선행 과제는
**single-agent numeric path 안에서 planner / synthesizer / structured result
contract를 먼저 안정화하고, 그 contract를 MAS의 task/artifact communication
contract로 승격할 준비를 끝내는 것**이다.

## Active Architecture Bet

현재 가장 중요한 architectural bet은 다음 세 가지다.

| 축 | 현재 판단 |
| --- | --- |
| Topology | 장기적으로는 `Orchestrator -> Analyst / Researcher -> Critic -> Merge`가 유망하지만, 단기적으로는 single-agent graph 안에서 planner / synthesizer 경계를 먼저 닫아야 함 |
| Communication | 자유 대화보다 `task ledger + artifact store`가 적합 |
| Memory | ChatGPT/Codex memory는 사용자 선호와 handoff 시작 절차에만 쓰고, runtime 상태 기억은 `report-scoped cache`와 repo 문서/git 기록이 우선 |

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

### Alignment rule

현재 backlog는 portfolio long-term goal과 아래 순서로 연결한다.

1. **Gate / contract prerequisites**
   - broader curated gate maintenance residual refreshes when fresh artifacts
     show a new blocker
   - concept-runtime promotion baseline refreshes before future planner/runtime
     changes
   - table payload sidecar store-size telemetry refreshes before fresh-store
     cost comparisons
2. **MAS migration**
   - MAS skeleton과 typed artifact schema
   - Analyst / Researcher / Critic 역할 분리
   - runtime critic과 offline evaluator 경계 고정
3. **Cross-document / cross-company expansion**
   - report-scoped cache
   - reference-note / multi-hop capability
   - entity/report namespace 기반 cross-company reasoning

즉 gate maintenance는 단순 score chasing이 아니라, MAS가 안전하게 재사용할
runtime contract를 고정하는 선행 작업으로 본다.

### 0. Planner and final synthesizer contract

현재:

- concept-only ontology와 LLM concept planner가 들어왔고
- planner feedback을 이용한 `pre_calc_planner` 재사용 replan loop도 생겼다

하지만:

- planner가 모은 재료와 최종 답변 요구사항 사이의 contract는 아직 약하다
- `difference`, `lookup`, `ratio`, `sum` 결과가 같은 structured result vocabulary로 더 단단히 고정되어야 한다
- direct lookup false positive를 score만으로 성공 처리하지 않도록 acceptance contract를 더 세게 둘 필요가 있다

다음:

- planner는 재료 수집 task에 집중
- final synthesizer는 원본 질문 충족 여부와 최종 refusal을 책임
- `planner_feedback -> replan -> close/refusal` loop를 benchmark 문항으로 고정
- direct-first policy는 eager dual-plan보다 lazy replan + runtime acceptance contract로 정착

최근 상태:

- `NAV_T1_071`에서 이 루프의 최소 실전 검증은 끝났다
- direct structured row grounding, same-table current/prior pairing,
  aggregate evidence propagation이 함께 닫혔다
- `answer_slots`와 deterministic gap checker가 들어와,
  aggregate 단계가 `primary/current/prior/delta` 누락을 structured하게 먼저 판단할 수 있게 됐다
- `SAM_T2_002`는 `growth_rate` aggregate가 current/prior/result 슬롯을 모두
  갖고도 최종 답변에서 operand 값을 누락하는 경우를 드러냈고, 이제
  sibling `task_output:*` lookup slot을 이용한 generic complete-growth
  rendering으로 닫혔다
- `NAV_T2_006` follow-up smoke에서 `task_output:*` dependency operand가
  sibling lookup의 직접 evidence id와 anchor를 보존하도록 provenance 계약을
  보강했다. aggregate projection도 null-like source id를 정리하므로,
  `source_row_ids` 표면에 `"None"` 같은 값이 citation/evaluator 경로로
  흘러가는 문제는 닫혔다
- concept planner store-fixed promotion smoke에서 `NAV_T1_071`과
  `MIX_T1_021`은 통과했지만, `NAV_T1_030` FCF 계열은 cash-flow outflow
  sign 처리와 evaluator-visible evidence projection debt를 드러냈다. sign
  처리는 generic `difference` role contract로 닫혔고, 남은 blocker는
  retrieval/evidence visibility다
- 2026-06-01 concept planner shadow check에서 curated 11개 모두
  concept/operation/operand-role task를 만들었고, required operand concept
  누락은 0건이었다. 다만 planner-only 결과이므로 broad default 전환 전에
  store-fixed end-to-end runtime gate가 필요하다
- 2026-06-04 concept runtime gap gate는 answer-composition residual까지
  store-fixed eval-only 기준 `7 / 7 PASS`로 닫혔다. `KBF_T2_018`,
  `POS_T1_057`, `SAM_T3_028` closure는 source-visible display 보존,
  evidence-visible impact relation assembly, unscoped context-dependent table
  rejection 같은 일반 contract로 처리했고, runtime domain-term audit도
  통과했다.
- task-ledger/artifact-store boundary hardening의 첫 단계로 runtime caller,
  evaluator, review CSV/Markdown, benchmark summary가 공통
  `task_artifact_trace` projection을 노출한다. 이 projection은 task/artifact
  count, missing artifact reference, orphan artifact, duplicate id,
  completed/partial task without artifact 같은 generic integrity issue를
  구조화해서 보여준다.
- aggregate final synthesis는 `task_artifact_trace.integrity_status = error`를
  blocking acceptance condition으로 사용한다. replan budget이 남으면 planner
  feedback을 내고, budget이 소진되면 partial answer에 명시적 refusal을 붙인다.
- completed `calculation` task는 `operand_set`, `calculation_plan`,
  `calculation_result` artifact kind를 모두 요구한다. 누락된 kind는
  `missing_required_artifact_kind` error로 projection되고 final close를 막는다.
- completed calculation artifact는 최소 payload와 provenance도 요구한다.
  operand list, plan operation/mode, rendered result 또는 answer slots, 그리고
  artifact-level evidence refs 또는 payload provenance가 없으면 각각
  `missing_required_artifact_payload` / `missing_required_evidence_ref` error가
  된다.
- completed `reconciliation` task도 `reconciliation_result` artifact,
  `payload.reconciliation_result.status`, ready/ok 상태의 candidate/evidence
  provenance를 요구한다. 누락은 기존 generic integrity error type으로
  projection되고 final close를 막는다.
- completed `retrieval` task도 `retrieval_bundle` artifact, non-empty retrieved
  candidate list, candidate provenance를 요구한다. 빈 retrieval bundle이나
  source 없는 retrieved candidate는 generic integrity error로 projection되고
  final close를 막는다.
- completed `synthesis` task도 `aggregated_answer` artifact, final answer text,
  source material, provenance를 요구한다. text-only final answer나 source 없는
  aggregate는 generic integrity error로 projection되고 final close를 막는다.
- completed `critic` task도 `critic_report` artifact, verdict, target refs,
  reason/issues, provenance를 요구한다. target 없는 critic 또는 이유 없는
  pass/fail verdict는 generic integrity error로 projection되고 final close를
  막는다.
- 따라서 이제 남은 일은 이 구조를 다른 numeric family로 일반화하고,
  mixed growth+narrative 계열의 retrieval fan-out과 answer-language polish를
  question-specific rule 없이 줄이는 것이다. 다만 concept-gate blocker
  chasing은 종료하고, 다음 우선순위는 gate baseline 고정, runtime/API cost
  control, 그리고 legacy projection cleanup이다.

종료 조건:

- `NAV_T1_071`류 질문에서 raw value와 derived value 요구가 함께 닫히고,
- replan loop가 불필요한 중복 task를 만들지 않으며,
- 재료 부족 시 aggregate 단계에서 명시적 final refusal이 나오고,
- false positive direct binding은 planner feedback 또는 fallback으로 안전하게 내려간다

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

- single-agent graph state가 raw task/artifact 기록을 유지한다
- caller/evaluator/benchmark surface에는 compact `task_artifact_trace`와
  generic integrity issue projection이 생겼다
- final synthesis는 trace의 error 상태를 close 차단 조건으로 사용한다
- completed calculation task의 required artifact-kind contract는 close 차단
  조건으로 승격됐다
- completed calculation task의 required payload/provenance contract도 close
  차단 조건으로 승격됐다
- completed reconciliation task의 required artifact/status/provenance contract도
  close 차단 조건으로 승격됐다
- completed retrieval task의 required bundle/provenance contract도 close 차단
  조건으로 승격됐다
- completed synthesis task의 aggregated answer/source/provenance contract도
  close 차단 조건으로 승격됐다
- completed critic task의 critic report/verdict/target/provenance contract도
  close 차단 조건으로 승격됐다
- MAS state도 `task_artifact_trace`를 유지하고, Critic은 `critic_report`
  artifact를, final merge는 `aggregated_answer` artifact를 artifact store에
  남긴다
- warning-level integrity signal은 기본 non-blocking이지만, final
  aggregated answer가 orphan artifact나 artifact 없는 completed/partial task를
  직접 source로 삼으면 blocking error로 승격된다
- Analyst worker는 `calculation` task로 `operand_set`, `calculation_plan`,
  primary `calculation_result`를 분리해서 쓰고, Researcher worker는
  retrieved candidate와 provenance를 담은 `retrieval_bundle`을 쓴다
- Runtime calculation projection source is now explicit under
  `resolved_calculation_trace.runtime_projection`; legacy top-level
  `calculation_*` fallback is marked compatibility-only with
  `legacy_fallback = true`.
- Resolver fallback now distinguishes standalone `structured_result` projection
  from mixed legacy fallback. If legacy operands/plans are combined with
  `structured_result`, the trace stays `legacy_top_level` and records
  `calculation_result_source`.
- Evaluator per-question results, benchmark serialized results, review CSV, and
  review Markdown now surface runtime projection source, legacy-fallback status,
  and calculation-result source as first-class audit fields.
- `RuntimeCalculationTrace` and `TaskResultRecord` typed contracts now describe
  the preferred graph-state projection; remaining cleanup should reduce writes
  to top-level `calculation_*` mirrors.
- `_runtime_trace_state_update(include_compatibility_mirrors = false)` is now
  available and applied to calculation verification skip, formula no-operands,
  formula missing-required-operands, calculation execution failure, incomplete
  deterministic lookup, deterministic operation guard, LLM formula-plan guard,
  operand/formula planning structured-output failure, render fallback,
  verification structured-output failure, and aggregate synthesis fallback
  branches. Render, verification, and aggregate success branches are now
  converted as well. `_execute_calculation` success and operand extraction
  direct/guard/synthesis/LLM success branches are now converted too. Formula
  planning deterministic lookup/operation/ontology success and LLM success
  branches are converted as well, and the remaining formula planning
  guard/incomplete branches now follow the same canonical trace contract.
  Non-formula calculation-node reset/no-op branches are converted too, and
  `_runtime_trace_state_update()` now defaults to omitting top-level
  compatibility mirrors. Compatibility mirrors are explicit opt-in for older
  external readers. A no-LLM replay audit over
  `runtime_projection_audit_2026-06-05` found all 7 copied concept-gate
  full-eval rows already on `resolved_calculation_trace` and no
  `legacy_top_level` rows. `_resolve_runtime_calculation_trace(...,
  allow_legacy_top_level = false)` now provides a strict mode for new readers:
  it rejects legacy top-level fallback while preserving non-legacy
  `structured_result` projection. Evaluator result export, benchmark
  serialized/review export, eligible analyst/MAS artifact handoff consumers, and
  current-runtime debug readers, reflection retry planning, route-decision
  readers after formula planning/calculation, and render/verification/retry
  preparation readers now use strict mode. Formula planning now reads incoming
  operands through strict current-state resolution and carries those operands
  explicitly through canonical trace updates, so legacy top-level operands
  cannot drive a new formula plan. Calculation execution now also reads operands
  and plans through strict current-state resolution, and every execution
  result/failure update carries the strict operands and plan explicitly. Late
  runtime numeric answer shaping now also reads through strict current-state
  resolution, so legacy top-level calculation results cannot rewrite final
  answers. Dependency-projection recalculation result readers now also use
  strict current-state resolution after `_execute_calculation()`, preventing
  legacy top-level recalculation results from refreshing aggregate rows. The
  active-task artifact projection helper now also ignores legacy top-level
  `calculation_*` fallback unless it is deliberately overriding a stale
  aggregate trace with live non-aggregate state.
  Historical replay, retrospective readers, and the public runtime projection
  bridge explicitly opt into legacy compatibility. The public bridge is now
  documented and tested as a `FinancialAgent.run()`/export boundary, not an
  internal current-state reader. Helper-level compatibility readers are now
  documented and tested: `_resolve_runtime_structured_result()` preserves legacy
  top-level fallback for export/review adapters, and
  `_runtime_trace_state_update()` may carry omitted trace parts from older
  state surfaces while migrated live graph nodes pass updated trace parts
  explicitly. Benchmark runner serialized results, smoke summaries, and review
  exports are now classified as strict current-contract projection surfaces;
  they expose projection metadata without promoting legacy top-level mirrors
  into exported resolved traces. Live evaluator rows are now classified the same
  way: fresh eval scoring consumes canonical runtime projection only and rejects
  stale top-level mirrors. Historical answer replay is now classified as a
  deliberate compatibility reader: it accepts legacy top-level mirrors from
  older saved result bundles, but canonical `resolved_calculation_trace` still
  wins when both surfaces are present. Retrospective operand-grounding
  rescoring follows the same compatibility policy for historical rows: legacy
  top-level operands are accepted only as resolver fallback behind canonical
  trace data. Retrospective evaluator ablation follows the same policy for
  historical rows, covering both operand-selection ablations and
  calculation-result-based override ablations. Retrospective ontology retrieval
  ablation is classified differently: it reruns the current graph against a
  persisted store, so it uses strict current-state projection and rejects
  top-level mirror fallback. Current-run debug helpers now follow the same
  strict projection policy: `debug_math_workflow.py` and
  `debug_reference_note_workflow.py` reject top-level mirror fallback and avoid
  structured-result fallback through stale top-level calculation results.
  `mas_analyst_smoke.py` is now explicitly mixed: direct `FinancialAgent.run()`
  comparison payloads remain compatibility-oriented, while MAS artifact handoff
  readers are strict and reject stale top-level mirrors for operands, statuses,
  and calculation-result payloads. The ops raw resolver callsites are now
  classified as strict current-runtime readers or deliberate compatibility
  readers.

다음:

- `Task`
- `TaskResult`
- `EvidenceItem`
- `CriticReport`
- `FinalReport`

First step completed: MAS merge now keeps the compatibility `final_report`
string while also publishing a typed `final_report_record`/`FinalReport`
projection, and the `aggregated_answer` artifact payload mirrors that record.
Second step completed: MAS Analyst and Researcher evidence-pool rows now use a
shared `EvidenceRecord` builder with common task/creator/kind/source fields and
producer-specific details preserved under `metadata`.
Third step completed: MAS critic output now uses a shared `CriticReport`
builder, and `critic_report` artifact payloads mirror the typed report.
Fourth step completed: MAS planner, critic, and synthesis task creation now use
a shared `AgentTask` builder to normalize task ids, status, context keys,
kind/label, dependencies, artifact ids, and blocked reason.
Fifth step completed: MAS worker, critic, and synthesis artifact creation now
uses a shared `Artifact` builder to normalize artifact ids, kind/status/summary,
payload projections, evidence refs, producer task id, and metadata while keeping
the compatibility `content` field intact.
Sixth step completed: MAS critic and final synthesis consumers now read typed
artifact projections first, using `payload` for answer/calculation status and
`evidence_refs` for grounding before falling back to compatibility fields.
Seventh step completed: MAS final merge now blocks `ok` close when
`task_artifact_trace.integrity_status = "error"`, preserves visible partial
material, and marks the typed final report plus synthesis artifact as blocked.
Eighth step completed: MAS final merge now distinguishes budgeted replan from
budget-exhausted refusal by emitting `planner_feedback`, incrementing
`replan_count`, and publishing a `replan_required` final projection while budget
remains.
Ninth step completed: the MAS graph now routes `replan_required` merge outcomes
back to planning when budget and feedback remain. Replanning passes the
integrity feedback into planner input, closes blocking tasks as failed with
`blocked_reason`, and keeps final synthesis source selection limited to completed
worker tasks and their referenced artifacts so stale artifacts do not re-enter
the final answer.

Tenth step completed: `src/ops/mas_e2e_smoke.py` now accepts a replan budget
and reports `final_report_record`, `task_artifact_trace`, planner feedback,
replan counts, routed-replan status, blocked case counts, and integrity error
counts for real Orchestrator / Analyst / Researcher / Critic / Merge runs.
This makes the real-node smoke observable for replan behavior without changing
the real node wiring. The live run still requires `GOOGLE_API_KEY` and a
store-backed query, so it remains an environment-gated smoke rather than a
unit-test gate.
Eleventh step completed: live real-node smoke was run against a local
OpenAI-3072 Samsung 2023 store. The first attempt against the default Samsung
2024 reference-note store exposed an embedding dimension mismatch
(`384` stored vs `3072` query embeddings) and, before the Critic fix, an
unbounded Analyst retry loop. Critic review now ignores failed worker tasks
instead of resurrecting them as `REJECTED_BY_CRITIC`. The store-compatible
Samsung 2023 run completed with `final_report_record.status = ok`,
`task_artifact_trace.integrity_status = ok`, `replan_count = 0`, and completed
Analyst / Researcher / Critic / synthesis tasks.

Twelfth step completed: `mas_e2e_smoke.py` now fails fast on embedding/store
signature mismatch before invoking graph nodes. It reads benchmark/vector store
metadata when present and falls back to the Chroma `collections.dimension`
column, so stale stores stop before LLM/API work. The default E2E MAS smoke now
points at the local OpenAI-3072 Samsung 2023 structural-selective store and
matching report scope, keeping the no-argument smoke path compatible with the
current runtime embedding contract. A no-argument default run completed 2 cases
with `embedding_compatibility.status = ok`, `blocked_count = 0`, and
`integrity_error_count = 0`.

Thirteenth step completed: `src/ops/check_mas_e2e_smoke_contract.py` now extracts
and compares the stable MAS smoke contract from full smoke JSON output:
embedding compatibility status, case count, blocked/integrity/replan summary
counts, per-case final status, artifact-integrity status, replan flags, and task
status distribution. This lets the default E2E smoke act as a local regression
check without treating generated final-answer prose as a strict golden string.
The 2026-06-05 local baseline was refreshed and compared cleanly:
`status = ok`, `difference_count = 0`, `case_count = 2`, `blocked_count = 0`,
`integrity_error_count = 0`, and both cases have five completed tasks. The full
output and compact contract remain local `benchmarks/results/**` artifacts, not
source-controlled handoff files.

Fourteenth step completed: MAS final report provenance now applies
order-preserving dedupe to final `source_task_ids`, `source_artifact_ids`, and
`evidence_refs`, and the synthesis artifact reuses the deduped final evidence
refs. A live default smoke after the change kept compact contract comparison at
`status = ok`, `difference_count = 0`; both cases still had five completed
tasks, while final record and synthesis evidence refs had `duplicates = 0`.

Fifteenth step completed: MAS final report `subtask_results` now includes only
answer-bearing worker task results, one per task, while source artifact
provenance still retains intermediate artifacts such as operand sets and plans.
A live default smoke after the change kept compact contract comparison at
`status = ok`, `difference_count = 0`; both cases had `subtask_results = 2`
with `empty_answers = 0` and task ids `task_1`, `task_2`.

Sixteenth step completed: MAS final merge now prepends an answer-compression
policy to the Orchestrator prompt. The policy keeps numeric Analyst conclusions
first, compresses Researcher context into a few material points, preserves
worker-provided values/units/periods, and avoids leaking evidence refs or
internal task ids into the final answer. A live default smoke after the change
kept compact contract comparison at `status = ok`, `difference_count = 0`; both
final answers started with the direct numeric conclusion and used compressed
narrative follow-up.

Carry-forward review completed: MAS E2E smoke now exposes final carry-forward
provenance explicitly. Each case reports `final_carry_forward` with source
task/artifact ids, evidence refs, subtask task/artifact ids, and counts; the
compact smoke contract compares those counts. This keeps the real-node replan
smoke from only saying "replan routed" and makes it clear whether repaired
worker artifacts actually reached the final report.

Schema productization follow-up completed: final carry-forward projection now
lives in the shared MAS schema layer via `project_final_report_carry_forward()`,
and Orchestrator final `subtask_results` preserve selected worker artifact ids
alongside task ids and answer surfaces. The smoke contract still compares the
same compact counts, but no longer owns the projection definition.

Role-boundary follow-up completed: worker artifact reads now share
`project_worker_artifact_boundary()` in the MAS schema layer. Critic review and
Orchestrator final synthesis consume the same payload-first answer, selected
artifact id, task id, role/kind/status, and deduped evidence refs, instead of
duplicating artifact fallback rules inside each role node.

Mixed growth+narrative fan-out review completed: the offline fan-out audit now
separates cross-trace reuse candidates by current cache hit vs current cache
miss counts. This keeps sibling lookup repeats, especially in mixed
numeric+narrative rows, visible without treating already cached repeats as the
next runtime-cost target.

Seventeenth step completed: Analyst numeric operand extraction now rejects
explicit consolidation-scope conflicts in both direct structured rows and
dependency task-output rows. Resolved dependency rows are also checked against
their producer statement/section scope before they can satisfy a downstream
calculation task, so note-scoped numeric rows cannot stand in for
income-statement operands. Compact ratio scope labels are rendered from
`CALCULATION_RENDER_POLICY.consolidation_scope_answer_prefixes`, keeping the
display vocabulary in config. A live default smoke after the change kept compact
contract comparison at `status = ok`, `difference_count = 0`; the first case
now answers `2023년 연결 기준 영업이익률은 2.54%` instead of using the separate
statement operands that produced `-4.45%`.

Eighteenth step completed: task-output dependency operands now treat the
producer operand artifact as the numeric source of truth when it conflicts with
a stale rendered answer slot, and they skip broad evidence-table precision
refinement once a resolved task-output value is already material. The dependency
row also checks the persisted structure graph for the same value/label under the
active report scope and requested consolidation scope, then promotes the matched
structured node's `source_anchor`, `consolidation_scope`, `statement_type`, and
`table_source_id`. Direct verification for the Samsung 2023 operating-margin
query now produces `2.54%` with both operands anchored to
`III. 재무에 관한 사항 > 2. 연결재무제표`; a live default MAS smoke kept compact
contract comparison at `status = ok`, `difference_count = 0`.

Nineteenth step completed: `check_mas_e2e_smoke_contract.py` now evaluates MAS
value canaries in addition to the compact topology/integrity contract. For the
Samsung 2023 connected/consolidated smoke, case 1 must include `2.54%`,
`6,566,976`, and `258,935,494`, and must not include `-4.45%`; case 2 must
include `10.95%`, `28,352,769`, and `258,935,494`. The repaired final smoke
passes with `value_assertion_failure_count = 0`, while the earlier
provenance-anchor smoke that surfaced `-4.45%` now fails the checker with value
assertion mismatches.

Twentieth step completed: MAS value canaries now live with the default smoke
profile in `src/ops/mas_e2e_smoke.py` instead of a separate golden assertion
file. `run_smoke()` embeds the profile-generated `value_contract` when the
default smoke scope/query set is used, and the checker can also reconstruct the
same contract from historical smoke output that has matching scope and query
strings but no embedded contract. Explicit `--value-contract` JSON remains as an
override for one-off checks.

Twenty-first step completed: report-scoped cache now has a code-level contract
in `src/config/report_scoped_cache.py`. The first contract version normalizes
keys from report scope (`company`, `report_type`, `rcept_no`, `year`), value
identity (`concept_id` or `metric_label`, plus `period`), and provenance scope
(`consolidation_scope`, `statement_type`, `source_section`, `source_table_id`).
It classifies candidates as `reusable`, `requires_evidence_verification`, or
`not_cacheable`, so future runtime cache reads cannot silently reuse
synthesized/LLM-only material or values with incomplete provenance.

Twenty-second step completed: runtime calculation traces now carry a read-only
`report_cache_candidate` projection. `_runtime_trace_state_update()` classifies
the active calculation result with `classify_report_cache_candidate()`, attaches
status/reasons/key/key id under `resolved_calculation_trace`, and the runtime
trace resolver preserves that projection through public output and MAS Analyst
artifacts. This is observability only: no cache read/write or retrieval bypass
is enabled.

Twenty-third step completed: MAS E2E smoke output now exposes
`report_cache_candidates` per case plus top-level candidate status/reason
counts. Public runtime projection also backfills a read-only candidate when a
resolved trace has enough report/value/provenance context but no candidate yet,
and table-source ids can recover their source section for cache-key
classification. A focused local Google-store MAS probe produced one deduped
`reusable` candidate for the calculation artifact, but the same probe surfaced a
value-canary risk: the operating-margin answer surface showed `2536.14%` rather
than the expected `2.54%`. Do not promote cache retrieval-bypass behavior until
the value canary is stable on the intended store/provider path.

Twenty-fourth step completed: the MAS operating-margin unit-scale canary is now
closed on the intended Google-store path. Ratio operands that come from the same
structured table context and normalize to the same KRW unit family now align
their source display unit from `CALCULATION_RENDER_POLICY` before formula
execution. A focused local Google-store MAS probe for Samsung 2023 produced
`2.54%`, preserved `6,566,976` and `258,935,494`, and still surfaced one
deduped `reusable` report-cache candidate. Cache read/write and retrieval bypass
remain disabled; the next step is to design the guarded consumer path rather
than simply trusting every reusable projection.

Next structural step: keep report-scoped cache as observability only while
designing the first guarded retrieval-bypass consumer. The consumer should only
consider `reusable` projections, preserve the source evidence contract, and
fall back to normal retrieval when cache provenance or value identity is
incomplete.

Twenty-fifth step completed: report-scoped cache now has a disabled
consumer-side gate. `classify_report_cache_consumer_candidate()` only marks a
read-only `reusable` projection with complete report/value/provenance key,
matching key id, empty reasons, and table provenance as `eligible`; all other
projections are blocked with explicit reasons. Runtime traces attach this as
`report_cache_candidate.retrieval_bypass` with `enabled = false` and
`mode = trace_only`, and MAS smoke output surfaces the nested assessment for
handoff review. No cache read/write or retrieval bypass behavior is enabled.

Next structural step: connect the disabled consumer assessment to the earliest
retrieval planning surface as trace-only telemetry, then verify that normal
retrieval still runs when the assessment is blocked or disabled.

Twenty-sixth step completed: the disabled consumer assessment is now visible on
the retrieval planning surface. `_retrieve()` copies the current
`report_cache_candidate.retrieval_bypass` assessment into
`retrieval_debug_trace.report_cache_consumer_assessment`, marks whether normal
retrieval actually executed, and records the executed query count. Focused tests
cover both an eligible trace-only candidate and a blocked candidate; both cases
still call the vector store search path because `enabled = false`.

Next structural step: before adding an enable flag, decide where report-cache
entries would be persisted/read from and define the source-of-truth boundary
between runtime trace projections, artifact stores, and any local cache index.

Twenty-seventh step completed: report-scoped cache now has a persisted-entry
source-of-truth contract. `REPORT_CACHE_ENTRY_VERSION` and
`classify_report_cache_entry()` define the only readable source as
`local_cache_index`; runtime trace projections and artifact-store projections
remain candidate/audit surfaces and are blocked as cache read sources. A
readable entry must carry a complete report/value/provenance key, matching key
id, value surface or normalized value, and provenance refs. This is still a
schema/validation contract only: no cache index is written, read, or used for
retrieval bypass.

Next structural step: add a read-only local cache index adapter skeleton that
can load and validate entries with `classify_report_cache_entry()` but still
returns trace-only diagnostics rather than serving runtime hits.

Twenty-eighth step completed: `src/storage/report_cache_index.py` now provides a
read-only `ReportCacheIndex` diagnostics adapter. It can load JSON or JSONL
local-cache-index payloads, validate each entry with
`classify_report_cache_entry()`, count readable/blocked/malformed entries, and
return lookup diagnostics by report-cache key id. The adapter always reports
`enabled = false` / `serving_enabled = false`, so it cannot serve runtime hits or
bypass retrieval.

Next structural step: wire `ReportCacheIndex.lookup_diagnostics()` into the
retrieval debug trace as optional trace-only telemetry, using an explicit path
configuration and preserving normal retrieval execution.

Twenty-ninth step completed: retrieval planning can now attach optional
read-only local-cache-index diagnostics. `FinancialAgent` accepts an explicit
`report_cache_index_path` through routing config, `_retrieve()` calls
`ReportCacheIndex.lookup_diagnostics()` only when a report-cache candidate key
is available, and `retrieval_debug_trace.report_cache_index_diagnostics`
records lookup status, match counts, index load status, and whether normal
retrieval executed. Benchmark runner and MAS smoke entry points can pass the
path for trace diagnostics, but `enabled = false` and `serving_enabled = false`
remain hard-coded; matched entries do not bypass vector-store search.

Next structural step: add a handoff-focused trace fixture or smoke assertion
that exercises `--report-cache-index-path` against a tiny local index and
checks only diagnostics, not serving behavior. Keep cache hit serving disabled
until evidence rehydration and provenance preservation are designed.

Thirtieth step completed: MAS smoke now has a handoff-level cache-index
diagnostics assertion. Analyst artifacts preserve `retrieval_debug_trace` and
`retrieval_debug_trace_history`, and `src/ops/mas_e2e_smoke.py` summarizes
`report_cache_index_diagnostics` per case and at the top level. A tiny local
JSON index fixture in the smoke unit test exercises the explicit
`report_cache_index_path` plumbing, verifies a readable match is counted once
even when trace data appears in both content and payload, and checks that
`enabled = false`, `serving_enabled = false`, and normal retrieval execution
remain visible in the summary.

Next structural step: design evidence rehydration for a future cache consumer
without enabling it yet. The design should specify which stored value/evidence
fields are needed to reconstruct answer slots, citations, and calculation
trace provenance before any retrieval bypass flag can become active.

Thirty-first step completed: report-scoped cache now has a disabled
rehydration-readiness contract. `normalise_report_cache_entry()` preserves
future consumer payload surfaces (`answer_slots`, `calculation_trace`,
`citations`, and `evidence_items`), and
`classify_report_cache_rehydration_candidate()` blocks readable entries unless
they can reconstruct the answer slot, citation/source anchor, evidence material,
and calculation trace provenance. Passing that classifier still reports
`enabled = false` and `serving_enabled = false`; it defines the minimum future
consumer contract but does not enable cache serving or retrieval bypass.

Next structural step: add trace-only rehydration diagnostics to
`ReportCacheIndex.lookup_diagnostics()` so smoke/benchmark output can show how
many matched readable entries are also rehydration-ready, still without serving
hits.

Thirty-second step completed: `ReportCacheIndex` now reports rehydration
readiness as trace-only diagnostics. Local index load diagnostics attach a
disabled `rehydration` assessment to each entry, count
`rehydration_ready_count`, and lookup diagnostics expose
`rehydration_ready_match_count`, `rehydration_blocked_match_count`, and
rehydration block reason counts. MAS smoke carries those counts into per-case
and top-level summaries. This still does not serve cache hits; the diagnostics
only show whether a matched readable entry has enough answer/evidence/trace
payload for a future consumer.

Next structural step: build a tiny persisted-index fixture profile for
eval-only or MAS smoke documentation so a reviewer can reproduce readable vs.
rehydration-ready diagnostics without relying on ad hoc temporary test data.

Thirty-third step completed: a source-controlled local-cache-index fixture now
lives at `tests/fixtures/report_cache_index/rehydration_diagnostics.json`. It
uses one cache key with two readable local-index entries: one intentionally
blocked for rehydration because it lacks answer slots/citation/trace material,
and one rehydration-ready entry with answer slots, citations, evidence items,
and calculation trace provenance. `tests/test_report_cache_index.py` reads the
fixture directly and verifies `match_count = 2`, `readable_match_count = 2`,
`rehydration_ready_match_count = 1`, and
`rehydration_blocked_match_count = 1`, while serving stays disabled.

Thirty-fourth step completed: `src/ops/report_cache_index_smoke.py` now prints
a reviewer-facing trace-only diagnostics payload for a local cache index. By
default it uses the first entry key in
`tests/fixtures/report_cache_index/rehydration_diagnostics.json`, so the
handoff command only needs `--report-cache-index-path` and shows
`match_count = 2`, `readable_match_count = 2`,
`rehydration_ready_match_count = 1`, and
`rehydration_blocked_match_count = 1` while both `enabled` and
`serving_enabled` remain false. `tests/test_report_cache_index_smoke.py` keeps
the emitted summary shape fixed.

Thirty-fifth step completed: `build_report_cache_rehydrated_candidate_artifact()`
now defines the first non-serving projection from a rehydration-ready
local-cache-index entry into an artifact-like candidate payload. Blocked entries
produce no artifact; ready entries preserve answer text, citations, evidence
items, structured result, calculation trace, report-cache key metadata, and
disabled rehydration metadata. The artifact status is `candidate`, and both
`enabled` and `serving_enabled` remain false. Fixture tests cover both the
blocked and ready entries in
`tests/fixtures/report_cache_index/rehydration_diagnostics.json`.

Thirty-sixth step completed: `src.ops.report_cache_index_smoke` now summarizes
rehydrated candidate artifact counts for matched local-index entries. The
source-controlled fixture reports `rehydrated_candidate_artifact_count = 1` and
`rehydrated_candidate_artifact_blocked_count = 1`; the ready entry also appears
in a minimal `rehydrated_candidate_artifacts.items` preview with answer,
citation, evidence-item, structured-result, and calculation-trace presence
signals. The preview remains outside the live task/artifact ledger and still
shows disabled serving.

Thirty-seventh step completed: `src.ops.check_report_cache_index_smoke_contract`
now extracts the stable report-cache-index handoff contract from full
`report_cache_index_smoke` output. The contract covers trace-only status flags,
match/readiness counts, rehydration reason counts, index load counts,
rehydrated candidate artifact counts, and candidate preview booleans/counts
without diffing the full matched-entry payload. The CLI supports
`--write-baseline` and comparison against either full smoke output or compact
contract JSON.

Thirty-eighth step completed: the report-cache-index smoke contract now has a
source-controlled compact baseline at
`tests/fixtures/report_cache_index/rehydration_contract_baseline.json`. The
baseline is generated from the fixture-backed smoke output and covers the stable
trace-only handoff fields, including candidate-artifact preview counts. Contract
tests compare live fixture smoke output against this baseline, while local
reviewer output can still be written under `benchmarks/results/**` and kept out
of commits.

Next structural step: use the source-controlled baseline in a lightweight
CI-style check or PR-review command, while keeping generated smoke outputs under
`benchmarks/results/**` untracked.

Thirty-ninth step completed: `src.ops.check_report_cache_index_smoke_contract`
can now build the fixture-backed report-cache-index smoke payload directly from
`--report-cache-index-path` and compare it to the source-controlled compact
baseline in one command. The older `--current` JSON path remains available for
reviewers who want to inspect or archive full smoke output locally, but the
lightweight PR-review path no longer needs to write generated output under
`benchmarks/results/**`.

Next structural step: decide whether this one-command contract check should be
added to an existing local review script or a future CI workflow, keeping it
non-serving and fixture-backed until cache reads are deliberately designed.

Fortieth step completed: `src.ops.review_report_cache_index_contract` now wraps
the report-cache-index reviewer path as a repo-local command with
source-controlled defaults. By default it uses
`tests/fixtures/report_cache_index/rehydration_diagnostics.json` and
`tests/fixtures/report_cache_index/rehydration_contract_baseline.json`, builds
the smoke payload in memory, prints the compact comparison result, and exits
nonzero on mismatch. This keeps the review path reproducible without adding a
new GitHub Actions workflow or writing generated smoke output.

Next structural step: keep cache serving disabled and design the first guarded
consumer-read path on paper before adding any runtime enable flag. The design
should specify where a rehydrated candidate would enter the task/artifact
ledger, how evidence provenance is rechecked, and which trace-only diagnostics
would become blocking.

Forty-first step completed: the guarded report-cache consumer-read design is
now part of `docs/architecture/agent_runtime_contract.md`. The contract keeps
serving disabled, limits future reads to readable `local_cache_index` entries,
requires a single rehydration-ready match, and requires provenance rechecks
across answer slots, citations/source anchors, evidence material, calculation
trace material, and report/value/provenance key scope. It also defines that a
future served cache value must enter the task/artifact ledger through either a
declared cache-rehydration schema path or the existing calculation task contract
with required `operand_set`, `calculation_plan`, and `calculation_result`
artifacts. Until that schema-backed producer policy exists, rehydrated output
must remain a non-serving `candidate`.

Next structural step: add a small contract helper or test-only validator for
the documented guarded-consumer blocking conditions, still without enabling
cache reads. The first validator should classify a rehydration-ready fixture as
admissible-for-design and the blocked fixture as a normal-retrieval fallback.

Forty-second step completed: `classify_report_cache_guarded_consumer_candidate()`
now codifies the first pure guarded-consumer admissibility check without
enabling cache reads. It returns `admissible_for_design` only when a
local-cache-index entry is rehydration-ready, scope-compatible with the expected
key, and not ambiguous; otherwise it returns `normal_retrieval_fallback` with
blocking reasons. The source-controlled fixture now proves the ready entry is
admissible for design while the blocked entry falls back because it lacks the
required rehydration surfaces. The helper still reports `enabled = false`,
`serving_enabled = false`, and `mode = trace_only`.

Next structural step: decide the schema-backed producer policy for a future
served cache value. The two open designs are either a dedicated
cache-rehydration task/artifact kind, or mapping cache rehydration into the
existing calculation task contract with explicit cache-origin metadata.

Forty-third step completed: the non-serving rehydrated candidate artifact now
has an explicit calculation-ledger-oriented metadata contract. Ready candidates
carry `source = report_cache_rehydration`, `cache_origin = local_cache_index`,
`report_cache_key_id`, `rehydration_status`, guarded
`consumer_admissibility.status`, and disabled serving/ledger insertion flags in
addition to the preserved answer, evidence, structured-result, and calculation
trace payload. Blocked candidates also expose guarded consumer fallback status
without producing an artifact. No cache read, write, retrieval bypass, or ledger
insertion behavior is enabled.

Next structural step: choose the schema-backed producer policy before adding
any serving flag. The best next contract test should validate either a
dedicated cache-rehydration artifact kind or the mapping from a rehydrated
candidate into the existing calculation task surfaces.

Forty-fourth step completed: the first schema-backed producer-policy direction
is now contract-tested as a candidate-only mapping into the existing
calculation task contract. `build_report_cache_calculation_contract_projection()`
projects a rehydration-ready local-index entry into a candidate `calculation`
task plus `operand_set`, `calculation_plan`, and `calculation_result` artifacts
using the same artifact id pattern as Analyst output. The projection preserves
cache origin, key id, rehydration status, guarded consumer admissibility, and
evidence refs, while keeping `serving_enabled = false` and
`ledger_insertion_enabled = false`. Blocked entries still produce no projection
and require normal retrieval fallback.

Next structural step: add a read-only integrity/projection validator for this
candidate calculation mapping so reviewers can see whether a projected candidate
would satisfy the existing task/artifact payload and provenance contract before
any producer policy or serving flag is introduced.

Forty-fifth step completed: the candidate calculation mapping now has a
read-only integrity validator. `validate_report_cache_calculation_contract_projection()`
checks that a projected candidate calculation task carries the required
`operand_set`, `calculation_plan`, and `calculation_result` artifact kinds,
their minimum payload surfaces, preserved evidence refs, and disabled
serving/ledger flags. The ready fixture validates as `valid_for_contract`; the
blocked fixture remains a normal retrieval fallback because no projection is
available. This still does not insert the projection into the ledger and does
not enable cache serving.

Next structural step: expose this validator in the reviewer handoff surface,
either through the fixture-backed smoke contract or the repo-local review
command, so PR reviewers can see candidate projection validity without running
the full test suite.

Forty-sixth step completed: the projection validator is now visible in the
reviewer handoff surface. `src.ops.report_cache_index_smoke` adds
calculation-projection validity/fallback counts and per-candidate validation
previews, while `src.ops.check_report_cache_index_smoke_contract` extracts the
stable status, disabled flags, and fallback reasons into the compact baseline.
The source-controlled baseline now proves that the ready fixture is
`valid_for_contract` and the blocked fixture remains
`normal_retrieval_fallback` with `projection_not_available`.

Next structural step: decide whether this reviewer-surface contract is enough
to mark the draft PR ready for review, or add one final repo-local review note
that summarizes the cache path as candidate-only from runtime trace through
projection validation.

Forty-seventh step completed: `src.ops.review_report_cache_index_contract` now
emits a compact `reviewer_handoff` summary for the candidate-only cache path.
The default fixture-backed command reports `status = ready`,
`mode = candidate_only`, disabled serving/ledger insertion flags, one valid
projection-ready candidate, and one fallback candidate. This is enough to treat
the reviewer-surface contract as the handoff gate while cache serving,
read/write behavior, ledger insertion, and retrieval bypass remain disabled.

### 3. Report-scoped cache

현재:

- key/cacheability contract는 `src/config/report_scoped_cache.py`에 있고,
  runtime calculation trace에는 read-only `report_cache_candidate`가 붙음
- readable `local_cache_index` fixture, rehydration readiness, guarded
  consumer admissibility, candidate artifact projection, calculation-task
  projection, read-only projection validation, and reviewer handoff are all
  contract-tested
- `src.ops.review_report_cache_index_contract` is the repo-local handoff gate:
  the default fixture-backed review reports `status = ok`, `difference_count =
  0`, `reviewer_handoff.status = ready`, `mode = candidate_only`, one valid
  projection-ready candidate, and one normal-retrieval fallback candidate
- runtime cache serving, cache read/write, ledger insertion, and retrieval
  bypass remain disabled

다음:

- do not add a serving flag yet
- future work should start from live/default MAS or eval-only traces only when
  deciding whether real runtime values produce enough candidate-only cache
  evidence to justify a separate producer policy
- until then, treat the cache path as a documented capability boundary rather
  than an answer path

### 4. Runtime critic과 offline evaluator의 역할 분리

현재:

- evaluator 자산은 강하고 runtime critic acceptance helper도 생겼다
- reviewer/demo/smoke 출력은 shared runtime acceptance helper를 사용한다
- critic rejection issue는 target task/artifact ids를 분리해 replan
  carry-forward가 rejected worker task를 함께 실패 처리할 수 있다
- MAS smoke output은 final acceptance outcome을 case/summary/compact contract에
  노출해 replan success, blocked answer, pending replan을 구분한다

다음:

- runtime critic은 task acceptance와 final merge 보호용
- offline evaluator는 benchmark/scorecard용
- 다음 follow-up은 live/default MAS trace를 새 smoke outcome contract로 한 번
  refresh할 필요가 있을 때만 진행한다

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

1. runtime critic / offline evaluator boundary follow-up
2. broader curated gate maintenance refresh when a new broader artifact
   reproduces a blocker rather than calibration debt
3. internal calculation debug ownership follow-up
4. agentic self-reflection 재설계
5. `REFERENCE_NOTE`와 report-scoped cache를 capability로 편입
6. cross-company 확장

## 지금 당장 하지 않을 것

- `business_overview_001`, `risk_analysis_001`을 score 맞추기용으로 과도하게 패치
- retrieval purity metric만 보고 ranking 로직을 계속 국소 조정
- rule-based self-reflection 분기를 더 늘리기
- generic long-term memory를 runtime state contract로 먼저 설계하기

핵심 원칙:

- 지금은 **검증 가능한 runtime contract를 MAS communication contract로 승격하는 구조 개선**을 우선한다
- **이미 맞는 답을 더 점수 잘 받게 만들기 위한 local patch**는 뒤로 미룬다
