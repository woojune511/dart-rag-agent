# Project Status

Last updated: 2026-06-04

## Positioning

This repository is a DART financial-document RAG and agent-runtime project. The
core engineering goal is not to hard-code benchmark answers, but to build a
traceable runtime contract for financial analysis:

- retrieve evidence from long-form DART filings
- bind the right structured rows and source sentences
- execute numeric operations deterministically
- preserve calculation and evidence traces
- validate changes through reproducible benchmark gates

The current direction is to turn the verified single-agent runtime into a
role-separated multi-agent system using a task ledger and artifact store.

## Session Handoff

- ChatGPT/Codex memory may remember user preferences and the preferred handoff
  routine, but it is not the source of truth for current project state.
- A new session should first read `AGENTS.md`, `CONTEXT.md`, this status file,
  `git status`, and recent commits before proposing or editing code.
- Store changing state in repo artifacts: `CONTEXT.md` for short snapshots,
  this file for current gate/backlog status, `docs/history/experiment_history.md`
  for experiment narratives, and git commits for exact source history.
- Do not rely on memory for latest blockers, benchmark outputs, model/API
  configuration, or files to stage.

## Current Gate Status

| Gate | Scope | Latest Status |
| --- | --- | --- |
| Runtime contract gate | 5 core numeric/runtime questions | PASS |
| Concept runtime gap gate | 7 ontology-driven concept questions | PASS, 7 / 7 |
| Policy-driven runtime gate | 4 company runs, 5 policy/narrative questions | PASS |

### Runtime Contract Gate

- Profile: `benchmarks/profiles/curated_runtime_contract_gate.json`
- Candidate: `structural_selective_v2_prefix_2500_320`
- Current interpretation: default short smoke gate is stable.
- Latest focused repair:
  - `SKH_T1_060` now passes the fresh low-API structural path with answer
    `42.02%`.
  - The fix is generic structured evidence selection: direct row-label /
    semantic-label evidence is preferred when projecting lookup task outputs
    into downstream ratio dependencies.
  - Producer lookup subtask result views are also aligned with that dependency
    projection, so serialized intermediate displays preserve the same direct
    structured value used by the final ratio.
  - No company name, benchmark ID, or metric-specific runtime branch was added.

### Concept Runtime Gap Gate

- Profile: `benchmarks/profiles/curated_concept_runtime_gap_gate.json`
- Latest representative local output:
  `benchmarks/results/concept_gate_refresh_after_answer_composition_2026-06-04/`
- Result:
  - 6 / 6 company runs completed
  - 7 / 7 questions pass
  - `numeric_final_judgement = PASS` for all seven questions
  - full-eval faithfulness is `1.000` for all seven questions
  - full-eval numeric pass rate is `1.000` for all seven questions
  - `KBF_T2_018`, `POS_T1_057`, and `SAM_T3_028` answer-composition
    residuals are closed
- Main closure:
  - multi-concept lookup tasks now split into independent task-ledger entries
  - sibling table evidence can recover missing lookup slots generically
  - lookup-list rendering is constrained to lookup-only aggregates
  - source-visible value displays are preserved when they are stronger than
    recomputed rounded displays
  - quantitative-impact composition assembles only evidence-visible numeric
    claims and relations
  - context-dependent segment/total table rows are rejected for unscoped
    lookup and ratio operands
  - post-fix runtime blockers for `KBF_T2_018`, `POS_T1_057`, and
    `SAM_T3_028` are closed without adding runtime domain keyword branches

### Policy-Driven Runtime Gate

- Profile: `benchmarks/profiles/curated_policy_driven_runtime_gate.json`
- Canonical remote embedding runtime:
  OpenAI `text-embedding-3-large` when `OPENAI_API_KEY` is available.
- Latest post-fix fresh OpenAI embedding refresh result:
  - 4 / 4 company runs passed
  - 0 full-eval failures
  - 0 critical misses
  - five-question average faithfulness, completeness, context recall, and
    retrieval hit@k are all `1.000`
  - average section match is `0.975`, citation coverage is `0.933`, entity
    coverage is `0.927`, and error rate is `0.0%`
- Note:
  - `numeric_final_judgement = null` is not a failure for narrative or mixed
    questions when the other evaluator signals are healthy.
- Latest focused repair:
  - `HYU_T2_010` now preserves the source-stated growth display when the DART
    sentence already says `87.0만 대`, `78.1만 대 대비 11.5%`.
  - The deterministic formula trace is still retained, but the final rendered
    answer and `answer_slots.primary_value.rendered_value` use the
    evidence-visible `11.5%` instead of drifting to a recomputed rounding.
  - If a growth calculation accidentally binds duplicate current/prior
    material, runtime now recovers the prior-period display from retrieved
    evidence sentences using generic year/unit/value matching before executing
    the formula.
  - Aggregate growth+narrative composition now treats the structured
    `current_value`, `prior_value`, and growth display slots as required answer
    displays before accepting a mixed-query answer as complete.
  - `NAV_T2_006` now gets commerce-growth driver retrieval from declarative
    retrieval policy suffixes, then rejects source-task display strings whose
    KRW unit conflicts with the already bound growth slot display.
  - The same answer guard replaces growth sentences that mix slot/trace values
    with untraced numeric displays, preserving grounded narrative sentences.
  - Latest OpenAI store-fixed eval-only policy-gate refresh reports
    faithfulness, completeness, context recall, and retrieval hit@k of `1.000`
    for every per-question full-eval row:
    - `NAV_T2_006`: relevancy `0.759`, section match `0.875`,
      citation coverage `0.667`, entity coverage `1.000`
    - `HYU_T2_010`: relevancy `0.696`, section match `1.000`
    - `HYU_T3_072`: relevancy `0.609`, section match `1.000`
    - `LGE_T1_051`: relevancy `0.563`, section match `1.000`,
      `numeric_final_judgement = PASS`
    - `SAM_T2_078`: relevancy `0.817`, section match `1.000`
  - Follow-up diagnosis classified the `SAM_T2_078` section precision gap as
    evaluator-definition drift: the retrieved Harman technology-focus evidence
    from `IV. 이사의 경영진단 및 분석의견` was faithful and complete but was not
    listed as an acceptable expected section. The curated datasets now include
    that section and quote, and recomputing the existing local bundle gives
    section match `1.000`.
  - Latest dependency-slot growth refresh:
    - aggregate growth rows can derive operands from `answer_slots` pointing at
      `task_output:*` lookup rows and recalculate from those sibling lookup
      slots
    - producer lookup slots are propagated back into the serialized growth
      trace, so stale aggregate operands do not survive in `structured_result`
    - `NAV_T2_006` now renders `2,546,649백만원`, `1,801,079백만원`, and
      `41.4%` in the final mixed numeric+narrative answer
    - this is a generic dependency-binding/display-preservation fix, not a
      company/question keyword rule
    - focused `NAV_T2_006` policy-gate smoke confirmed faithfulness `1.000`,
      completeness `1.000`, error rate `0.0%`, and growth-rate answer slots
      aligned to the producer lookup values
    - follow-up focused store-fixed eval-only over the available Google-backed
      policy-gate artifact closed the narrative completeness gap without adding
      runtime domain keyword rules:
      - `NAV_T2_006`: policy-backed supported driver groups are now preserved
        through growth narrative composition; faithfulness `1.000`,
        completeness `1.000`, error rate `0.0%`
      - `LGE_T1_051`: ontology alias-bound compact query markers such as
        source-visible abbreviations are preserved after numeric locking and
        slot-based answer composition; faithfulness `1.000`, completeness
        `1.000`, numeric final judgement `PASS`
  - Validation: runtime domain-term audit passed, focused dependency-growth and
    aggregate preservation regression tests passed, the full unittest suite
    passed, and the full policy gate completed without embedding quota errors.

## Operating Principles

- Domain vocabulary belongs in ontology, retrieval policy, config, or reviewed
  data artifacts, not runtime control-flow code.
- Runtime code should implement generic mechanisms: evidence preservation,
  structured row/header matching, dependency binding, dedupe, ordering,
  validation, and display preservation.
- Benchmark regressions are classified by layer before implementation:
  ontology, retrieval policy, parser structure, planner contract, evidence
  schema, runtime execution, or evaluator definition.
- Store-fixed `--eval-only` refreshes come before fresh ingest unless parser,
  ingest, or cache signatures changed.
- Experiment result directories are local artifacts and are not committed.
- Embedding provider/model/dimension is part of the store signature. Changing
  it requires a fresh store or a signature-matched cache, not silent store
  reuse.

## Portfolio Framing

The strongest portfolio story is:

> I built a financial-document RAG runtime that treats numbers as structured
> evidence-bound artifacts rather than free-form LLM text. The system separates
> semantic planning from deterministic execution, stores explicit calculation
> traces, and uses focused benchmark gates to prevent benchmark-specific
> patches from entering runtime code.

Useful supporting points:

- The project handles noisy DART filings with section/table-aware parsing and
  hybrid retrieval.
- Numeric questions use formula planning and safe deterministic execution.
- Evaluation is split into faithfulness, completeness, numeric equivalence,
  numeric grounding, and retrieval support.
- The runtime now has gate-backed concept and policy-driven paths without
  adding company/question-specific branches to agent code.

## Next Work

1. Freeze the current concept-runtime 7/7 gate as the promotion baseline and
   use store-fixed eval-only refreshes for future canaries before paying for
   fresh ingest.
2. Reduce benchmark runtime and embedding cost through profiling, cache
   hygiene, and explicit retrieval query-budget controls for focused canaries.
3. Continue projection cleanup by reducing internal writes to top-level
   `calculation_*` mirrors now that `RuntimeCalculationTrace` and
   `TaskResultRecord` typed contracts exist. Deterministic incomplete-plan,
   LLM formula-plan guard, and operand/formula planning structured-output
   failure branches now use `include_compatibility_mirrors = false`. Render,
   verification, and aggregate synthesis fallback branches now do the same; the
   render, verification, and aggregate success branches have also moved to
   canonical trace readers. `_execute_calculation` success and operand
   extraction direct/guard/synthesis/LLM success readers now also consume the
   canonical trace while those branches omit top-level mirrors. Formula planning
   deterministic lookup/operation/ontology success and LLM success readers now
   do the same, and the remaining formula planning guard/incomplete branches
   are now also mirror-free. Formula planning now reads incoming operands with
   strict current-state resolution and preserves them explicitly in canonical
   trace updates, so legacy top-level operands cannot seed a new formula plan.
   Calculation execution now also reads operands and plans with strict
   current-state resolution, preserving the strict operands and plan through
   result/failure trace updates. Late runtime numeric answer shaping now also
   uses strict current-state resolution, so legacy top-level calculation results
   cannot rewrite final answers. Dependency-projection recalculation readers now
   also use strict current-state resolution for `_execute_calculation()` outputs,
   so legacy top-level recalculation results cannot refresh aggregate rows. The
   calculation node's remaining non-formula
   reset/no-op branches now also omit top-level mirrors, and
   `_runtime_trace_state_update()` now defaults to mirror-free canonical trace
   publication. Helper-level compatibility fallback is documented and tested for
   export/review structured-result adapters and omitted trace-part carry-forward
   only. Benchmark runner serialized results, smoke summaries, and review
   exports are strict current-contract projection surfaces: they surface
   projection source metadata without re-promoting legacy top-level mirrors into
   resolved traces. Live evaluator rows now follow the same strict contract for
   fresh scoring, rejecting stale top-level mirrors while retaining canonical
   projection metadata. Historical answer replay is the first explicitly
   classified ops compatibility reader: it accepts legacy top-level mirrors from
   older saved bundles, but treats them as fallback behind canonical
   `resolved_calculation_trace`. Retrospective operand-grounding rescoring now
   follows the same policy for historical rows, and retrospective evaluator
   ablation now applies it to both operand and calculation-result inputs.
   Retrospective ontology retrieval ablation reruns the current graph against a
   persisted store, so it is now documented and tested as a strict
   current-runtime projection reader. Current-run debug helpers are now also
   documented and tested as strict readers, including structured-result output
   paths that no longer revive stale top-level calculation results. Resolver
   fallback now distinguishes structured-result-only and mixed legacy fallback,
   and evaluator/benchmark exports surface projection source metadata so
   remaining legacy fallback consumers can be audited from output artifacts.
4. Add a small portfolio demo script that runs a representative query and emits
   answer, evidence, and calculation trace side by side.

### Task Ledger / Artifact Contract Focus

- The runtime now projects raw `tasks` and `artifacts` into a compact
  `task_artifact_trace` for callers, evaluator results, review CSV/Markdown,
  and benchmark aggregate summaries.
- The projection reports task/artifact counts, missing artifact references,
  orphan artifacts, and a generic integrity status with structured issues.
- Duplicate ids and missing artifact references are errors; orphan artifacts and
  completed or partial tasks without artifacts are warnings.
- Final synthesis now treats integrity errors as blocking acceptance: it replans
  when budget remains and emits an explicit partial/refusal answer when the
  replan budget is exhausted.
- Completed calculation tasks now require attached `operand_set`,
  `calculation_plan`, and `calculation_result` artifacts; missing required kinds
  are reported as `missing_required_artifact_kind` errors and therefore block
  final close.
- Calculation artifacts now also require minimum payload shape and preserved
  provenance. Missing operand lists, executable plan operation/mode, rendered
  result/answer slots, or evidence provenance are reported as
  `missing_required_artifact_payload` / `missing_required_evidence_ref` errors.
- Completed reconciliation tasks now require a `reconciliation_result` artifact,
  `payload.reconciliation_result.status`, and candidate/evidence provenance when
  the result is `ready` or `ok`.
- Completed retrieval tasks now require a `retrieval_bundle` artifact with a
  non-empty retrieved candidate list and preserved candidate provenance.
- Completed synthesis tasks now require an `aggregated_answer` artifact with
  final answer text, source material, and preserved provenance.
- Completed critic tasks now require a `critic_report` artifact with verdict,
  target refs, reason/issues, and preserved provenance.
- MAS state now carries `task_artifact_trace`; worker nodes write stable
  artifact ids/kinds/payload/evidence refs, Critic writes `critic_report`
  artifacts, and final merge writes an `aggregated_answer` artifact.
- Analyst worker tasks are now `calculation` tasks that write separate
  `operand_set`, `calculation_plan`, and primary `calculation_result` artifacts.
  Researcher worker tasks are now `retrieval` tasks that write a
  `retrieval_bundle` with retrieved candidates and provenance.
- Runtime calculation projection now records its source under
  `resolved_calculation_trace.runtime_projection`, so callers can distinguish
  canonical resolved traces, task/artifact ledger projections, aggregate
  projections, structured-result views, and legacy top-level `calculation_*`
  fallback.
- Resolver fallback now separates structured-result-only projections from mixed
  legacy fallback. A standalone `structured_result` is non-legacy, while legacy
  top-level operands/plans combined with a structured result remain marked
  `legacy_top_level` and record `calculation_result_source`.
- Evaluator results and benchmark review exports now surface
  `runtime_projection_source`, `runtime_projection_legacy_fallback`, and
  `runtime_projection_calculation_result_source`, making remaining legacy
  fallback usage visible without reading the full trace JSON.
- A no-LLM replay audit over the copied
  `runtime_projection_audit_2026-06-05` concept-gate bundle found 7/7
  full-eval rows using `runtime_projection_source = resolved_calculation_trace`
  and 0 `legacy_top_level` rows. The live eval-only diagnostic was stopped after
  heartbeat-confirmed progress because the first question exceeded the audit's
  cost/time budget.
- `_resolve_runtime_calculation_trace(..., allow_legacy_top_level = false)` now
  provides a strict resolver mode for new readers. Strict mode rejects legacy
  top-level `calculation_*` fallback but still keeps standalone
  `structured_result` as a non-legacy projection.
- Evaluator result export, benchmark serialized/review export, eligible
  analyst/MAS artifact handoff consumers, current-runtime debug readers,
  reflection retry planning, route-decision readers after formula
  planning/calculation, and render/verification/retry preparation readers now
  use strict resolver mode, so legacy top-level mirrors no longer reappear in
  those review, runtime handoff, debug, retry planning, routing, or answer
  preparation surfaces. Historical replay, retrospective readers, and the public
  runtime projection bridge explicitly opt into legacy compatibility because
  they may read older result bundles or older caller surfaces. The public bridge
  is covered as a `FinancialAgent.run()`/export boundary and must not be used by
  new internal current-state readers.
- `FinancialAgentState` now types `resolved_calculation_trace` as
  `RuntimeCalculationTrace` and `subtask_results` as `TaskResultRecord`; the old
  `_project_legacy_calculation_fields()` name remains only as a compatibility
  alias for `_project_runtime_calculation_trace()`.
- `_runtime_trace_state_update()` can now omit top-level `calculation_*`
  compatibility mirrors. The first applied branch is calculation verification
  skip for non-ok calculation results, which keeps `resolved_calculation_trace`
  current without rewriting mirror fields.
- The no-operands formula plan, missing-required-operands formula plan, and
  calculation execution failure paths now also omit top-level compatibility
  mirrors; focused tests read these results through `_resolve_runtime_calculation_trace()`.
- Deterministic incomplete-plan branches now omit top-level compatibility
  mirrors as well: incomplete deterministic lookup plans and deterministic
  operation guard failures are consumed through `resolved_calculation_trace`.
- LLM formula-plan guard failures and operand/formula planning structured-output
  failures also omit top-level compatibility mirrors; focused tests read these
  results through `_resolve_runtime_calculation_trace()`.
- Render fallback, verification structured-output failure, and aggregate
  synthesis fallback branches now omit top-level compatibility mirrors as well.
  Focused tests read render/verification results through
  `_resolve_runtime_calculation_trace()`, and aggregate fallback readers now use
  the same projection instead of direct top-level `calculation_*` fields.
- Render and verification success branches now also omit top-level
  compatibility mirrors. Focused tests cover both LLM-rendered and slot-rendered
  answers, plus successful verification, through `_resolve_runtime_calculation_trace()`.
- Aggregate success branches now omit top-level compatibility mirrors too.
  Aggregate result tests now read formatted results, rendered values, and status
  through `_resolve_runtime_calculation_trace()` instead of direct top-level
  `calculation_*` fields.
- Calculation execution success branches and operand extraction
  direct/guard/synthesis/LLM success branches now omit top-level compatibility
  mirrors. Focused tests read produced operands/results through
  `_resolve_runtime_calculation_trace()` before feeding the next graph step.
- Formula planning deterministic lookup/operation/ontology success branches and
  LLM success branches now omit top-level compatibility mirrors. Focused tests
  read planned operations through `_resolve_runtime_calculation_trace()`.
- Formula planning guard/incomplete branches now also omit top-level
  compatibility mirrors, so the entire formula planning node publishes through
  the canonical runtime trace contract.
- Non-formula calculation-node reset/no-op branches now omit top-level
  compatibility mirrors too. All `_runtime_trace_state_update()` call sites in
  `financial_graph_calculation.py` now publish through the canonical trace
  contract.
- Active-task artifact projection now uses strict current-state resolution too:
  empty `resolved_calculation_trace` no longer falls back to legacy top-level
  `calculation_*` fields, while the deliberate stale-aggregate to live
  non-aggregate override remains covered by focused tests.
- Formula planning now also uses strict current-state resolution for its input
  operands. Focused tests cover the legacy top-level operand rejection case and
  existing deterministic/LLM plan branches feed operands through
  `resolved_calculation_trace`.
- Calculation execution now uses strict current-state resolution for operands
  and plans. Focused tests cover the legacy top-level operand/plan rejection
  case, and execution fixtures feed calculation inputs through
  `resolved_calculation_trace`.
- Late runtime numeric answer shaping now uses strict current-state resolution
  too. Focused tests cover both canonical trace answer recovery and legacy
  top-level calculation-result rejection.
- Dependency-projection recalculation now reads `_execute_calculation()` outputs
  through strict current-state resolution. Focused tests cover rejection of
  legacy top-level recalculation results.
- `_runtime_trace_state_update()` now defaults to omitting top-level
  compatibility mirrors. Compatibility mirrors remain available only as an
  explicit opt-in for older external readers.
- Helper-level compatibility fallbacks are now explicitly documented and tested:
  `_resolve_runtime_structured_result()` may read older top-level calculation
  results for export/review adapters, and `_runtime_trace_state_update()` may
  carry omitted trace parts from older state surfaces.
- Benchmark runner exports are now explicitly strict projection consumers:
  serialized eval rows, smoke summaries, and review CSV/Markdown rows ignore
  stale top-level calculation mirrors while exposing runtime projection and task
  artifact integrity metadata for audit.
- Live evaluator rows are also strict projection consumers: `evaluate_one()`
  ignores legacy top-level calculation mirrors during fresh scoring and records
  projection metadata only from canonical runtime traces.
- Historical answer replay is explicitly compatibility-oriented. It may read
  older top-level calculation mirrors from saved benchmark bundles, but canonical
  `resolved_calculation_trace` takes precedence whenever both are present.
- Retrospective operand-grounding rescoring is also compatibility-oriented for
  historical rows, with canonical `resolved_calculation_trace` taking precedence
  over stale top-level operand mirrors.
- Retrospective evaluator ablation is compatibility-oriented too. Historical
  top-level mirrors remain fallback inputs, while canonical trace operands and
  calculation results take precedence for ablation scoring.
- Retrospective ontology retrieval ablation is strict, not compatibility-based:
  it reruns current graph nodes against a persisted store and rejects legacy
  top-level calculation mirrors when forming outcome rows.
- Current-run debug helpers are strict projection consumers:
  `debug_math_workflow.py` and `debug_reference_note_workflow.py` reject legacy
  top-level calculation mirrors and keep structured-result output tied to the
  canonical runtime trace.
- `mas_analyst_smoke.py` is now classified as a mixed smoke reader: direct
  `FinancialAgent.run()` comparison inputs keep compatibility fallback, while
  MAS artifact handoff readers are strict and reject stale top-level mirrors for
  operands, statuses, and calculation-result payloads.
- MAS final synthesis now keeps the compatibility `final_report` string and
  also publishes a typed `final_report_record`/`FinalReport` projection. The
  `aggregated_answer` artifact payload mirrors that typed record.
- MAS `evidence_pool` rows now use the shared `EvidenceRecord` builder:
  Analyst and Researcher nodes publish common task/creator/kind/source fields
  while preserving producer-specific details under `metadata`.
- MAS critic output now uses the shared `CriticReport` builder. The typed report
  normalizes verdict, target artifact refs, acceptance reason, blocking issues,
  score, and feedback, and the `critic_report` artifact payload mirrors it.
- MAS planner, critic, and synthesis task creation now use the shared
  `AgentTask` builder to normalize task ids, assignees, status, context keys,
  kind/label, dependencies, artifact ids, and blocked reason.
- MAS worker, critic, and synthesis artifacts now use the shared `Artifact`
  builder to normalize artifact ids, kind/status/summary, payload projections,
  evidence refs, producer task id, and metadata while preserving compatibility
  content.
- MAS critic and final synthesis consumers now read typed artifact projections
  first: answer/calculation status from `payload`, evidence from
  `evidence_refs`, then compatibility `content`/`evidence_links` fallback.
- MAS final merge now treats `task_artifact_trace.integrity_status = "error"`
  as a blocking close condition: it preserves partial material but marks the
  typed final report and synthesis artifact as blocked instead of closing `ok`.
- MAS final merge now distinguishes replan from refusal: when replan budget
  remains it emits `planner_feedback` and a `replan_required` final projection;
  once the budget is exhausted it emits the blocked/refusal final answer.
- MAS graph routing now consumes that `replan_required` projection: when budget
  and planner feedback remain, `Orchestrator_Merge` routes back to
  `Orchestrator_Plan`. The replan pass includes integrity feedback in planner
  input, marks blocking tasks as failed with `blocked_reason`, and final
  synthesis reads only completed worker tasks plus their referenced artifacts so
  stale artifacts are not reused as final sources.
- `mas_e2e_smoke.py` now supports replan-budgeted real-node smoke runs and
  exports replan counts, routed-replan status, final report records,
  task/artifact integrity status, blocked case counts, and integrity-error
  counts. The live real-node smoke is environment-gated because it needs
  `GOOGLE_API_KEY`; the current change is covered by API-free contract tests.
- Live real-node smoke was then run with a local OpenAI-3072 Samsung 2023 store
  and matching report scope. It completed in `68.2s` with
  `final_report_record.status = ok`, `task_artifact_trace.integrity_status =
  ok`, `replan_count = 0`, completed Analyst / Researcher / Critic / synthesis
  tasks, and no blocked or integrity-error cases. The earlier default-store run
  correctly exposed a store compatibility problem (`384` stored dimension vs
  `3072` query embeddings), not a `.env` loading issue.
- The same live smoke exposed and closed a MAS retry-control bug: failed worker
  tasks were being reviewed by Critic and could be resurrected as
  `REJECTED_BY_CRITIC`, causing repeated Analyst retries. Critic now reviews
  completed worker tasks only.
- `mas_e2e_smoke.py` now performs an embedding/store compatibility preflight
  before graph nodes are invoked. It reads benchmark/vector-store metadata and
  falls back to Chroma collection dimension, so incompatible persisted stores
  fail before LLM/API work. The no-argument smoke default now uses the local
  OpenAI-3072 Samsung 2023 structural-selective store and matching report scope.
  A default run completed 2 cases with `embedding_compatibility.status = ok`,
  `blocked_count = 0`, and `integrity_error_count = 0`.
- `check_mas_e2e_smoke_contract.py` extracts and compares compact MAS smoke
  contract fields from full smoke JSON output, covering embedding compatibility,
  case count, blocked/integrity/replan summary counts, per-case final status,
  artifact-integrity status, replan flags, and task status distribution. This is
  the default local delta check for MAS quality work. The 2026-06-05 local
  compact baseline compare is clean: `status = ok`, `difference_count = 0`,
  `case_count = 2`, `blocked_count = 0`, `integrity_error_count = 0`, and both
  cases have five completed tasks.
- MAS final report provenance now dedupes final source task IDs, source artifact
  IDs, and evidence refs while preserving first-seen order; the synthesis
  artifact uses the same deduped evidence refs as the final report record. A
  live default smoke kept compact contract comparison clean and confirmed zero
  duplicates in final record and synthesis evidence refs.
- MAS final report `subtask_results` now records only answer-bearing worker
  task results, one per task. Intermediate artifacts still remain in source
  provenance, but they no longer appear as empty subtask answers in the final
  projection. A live default smoke kept compact contract comparison clean and
  produced two non-empty subtask results per case.
- MAS final merge now applies explicit answer-compression guidance before the
  existing Orchestrator prompt: numeric Analyst conclusions come first,
  Researcher context is reduced to a few material points, worker values/units
  are preserved, and evidence refs or internal task ids are kept out of prose.
  A live default smoke kept compact contract comparison clean.
- MAS Analyst numeric operand extraction now rejects explicit
  consolidation-scope conflicts for direct rows and dependency task-output rows,
  and resolved dependency rows are checked against producer statement/section
  scope before satisfying downstream calculation tasks. Compact ratio scope
  labels are config-driven. A live default smoke kept compact contract
  comparison clean and case 1 now reports `연결 기준 영업이익률 2.54%` instead of
  the prior separate-statement `-4.45%`.
- Task-output dependency operands now prefer the producer operand artifact over
  stale rendered answer slots, skip broad evidence-table precision refinement
  for already-resolved task-output values, and repair provenance from the
  persisted structure graph when the same value/label has a better scoped node.
  Direct verification anchors the Samsung 2023 operating-margin operands to
  `III. 재무에 관한 사항 > 2. 연결재무제표` with `consolidated` /
  `income_statement`; live MAS smoke still reports case 1 as `2.54%`.
- MAS E2E smoke contract comparison now also evaluates value canaries generated
  from the default smoke profile in `src/ops/mas_e2e_smoke.py`. The default
  checker still compares compact topology/integrity fields, and it now fails if
  case 1 loses `2.54%`, `6,566,976`, or `258,935,494`, or if `-4.45%` reappears
  in the full smoke surface. `run_smoke()` embeds the profile-generated
  `value_contract` for the default scope/query set, and the checker can
  reconstruct it for matching historical smoke output. The repaired smoke
  reports `value_assertion_failure_count = 0`; the earlier bad
  provenance-anchor smoke fails as expected.
- Report-scoped value cache design now has a code-level contract in
  `src/config/report_scoped_cache.py`. It normalizes cache keys from report
  scope, value identity, and provenance scope, and classifies candidates as
  `reusable`, `requires_evidence_verification`, or `not_cacheable`. Runtime
  calculation traces now carry a read-only `report_cache_candidate` projection
  with classifier status/reasons/key/key id, and MAS Analyst artifacts preserve
  it through `resolved_calculation_trace`. MAS E2E smoke output now reports
  per-case `report_cache_candidates` plus top-level status/reason counts, with
  duplicate content/payload projections counted once. The follow-up unit-scale
  repair aligns same-table KRW ratio operands to the table display unit before
  formula execution; a focused local Google-store probe now reports the Samsung
  2023 operating margin as `2.54%` with one `reusable` calculation candidate.
  A disabled consumer-side gate now marks only read-only, complete, reason-free
  `reusable` projections as `retrieval_bypass.eligible`, with `enabled = false`
  and `mode = trace_only`; MAS smoke surfaces that nested assessment. Retrieval
  planning now also copies the assessment into
  `retrieval_debug_trace.report_cache_consumer_assessment` and records that
  normal retrieval still executed. Persisted cache-entry validation now defines
  `local_cache_index` as the only future read source; runtime trace projections
  and artifact-store projections remain candidate/audit surfaces. A read-only
  `ReportCacheIndex` diagnostics adapter can validate JSON/JSONL local index
  entries and lookup by cache key id, but reports `serving_enabled = false`.
  Retrieval planning can now attach those lookup diagnostics from an explicit
  `report_cache_index_path` into
  `retrieval_debug_trace.report_cache_index_diagnostics`, including match
  counts and normal-retrieval execution status. Benchmark runner and MAS smoke
  can pass the path for diagnostics, but matched entries still do not serve
  hits or bypass vector-store search. MAS Analyst artifacts now preserve
  retrieval traces, and MAS smoke summarizes cache-index diagnostics per case
  and at the top level for handoff checks. The next consumer boundary is now
  explicit in code: `classify_report_cache_rehydration_candidate()` requires
  answer slots, citation/source-anchor material, evidence material, and
  calculation trace provenance before any future cache hit can be considered
  rehydratable, while still reporting serving disabled. `ReportCacheIndex`
  lookup diagnostics now count rehydration-ready vs. blocked matches and carry
  those counts through MAS smoke summaries. The reviewer handoff smoke
  `src.ops.report_cache_index_smoke` prints the same trace-only diagnostic
  payload from the source-controlled fixture without running MAS or retrieval.
  `build_report_cache_rehydrated_candidate_artifact()` now defines the first
  non-serving projection from a rehydration-ready entry to an artifact-like
  candidate payload, but it still reports disabled serving and is not wired into
  the task/artifact ledger. The handoff smoke now summarizes reconstructable
  candidate artifact counts and emits a minimal preview for ready entries only.
  `check_report_cache_index_smoke_contract` extracts and compares the stable
  subset of that handoff surface so reviewers do not need to diff the full
  diagnostic payload. It can also build the fixture-backed smoke payload
  directly from `--report-cache-index-path`, so the lightweight review command
  compares against the source-controlled compact baseline without writing
  generated smoke output. `src.ops.review_report_cache_index_contract` wraps
  that fixture-backed baseline comparison as the default reviewer command. The
  fixture-backed compact baseline is source-controlled under
  `tests/fixtures/report_cache_index/rehydration_contract_baseline.json`.
  The guarded cache-consumer promotion design is now documented in the runtime
  contract: future serving must start from a readable `local_cache_index`
  match, select exactly one rehydration-ready entry, recheck value/evidence/
  citation/calculation provenance against the cache key, and enter the
  task/artifact ledger only through an explicit schema-backed producer policy.
  `classify_report_cache_guarded_consumer_candidate()` now codifies the first
  pure version of those blocking conditions without enabling reads: the ready
  fixture is admissible for design, while incomplete or mismatched entries
  require normal retrieval fallback and expose reasons.
  Cache read/write behavior and retrieval bypass remain disabled.
- Warning-level integrity signals are non-blocking by default, but final-source
  dependencies on orphan artifacts or artifactless completed/partial tasks are
  promoted to blocking errors.

### Runtime/API Cost Focus

- First low-risk control: benchmark runs can now pass explicit retrieval query
  budgets to cap primary, operand-focused, and retry retrieval fan-out.
- Official runtime contract and policy-driven gate profiles now set `8 / 4 / 1`
  in `full_evaluation`, so focused gate runs record the budget in their
  profile/config instead of relying on ad hoc CLI flags.
- `retrieval_debug_trace.query_budget.source` now records the active retrieval
  source and source-level query counts. This matters because final traces can
  describe only the last active subtask while the state-level semantic plan may
  still contain many generated query surfaces.
- `retrieval_debug_trace.search_summary` now aggregates executed searches,
  cache hits, vector attempts, and query-embedding calls by retrieval source.
  A local `HYU_T2_010` trace showed `12` searches for the numeric subtask
  (`primary 8`, `operand_focus 4`) and `3` searches for the narrative subtask,
  making retrieval fan-out visible without hand-counting `executed_queries`.
- The same `HYU_T2_010` rerun exposed a remaining answer-composition issue:
  the answer can preserve `87.0만 대` and `11.5%` while omitting the prior
  `78.1만 대` display, which lowers completeness despite correct retrieval and
  calculation. Treat this as an aggregate rendering follow-up, not a retrieval
  budget failure.
- Cost estimation now consumes normalized Gemini response usage metadata for
  benchmark contextualization, agent runtime, and evaluator judge calls:
  - prompt/input tokens
  - output/candidate tokens
  - thinking tokens
  - cached-content tokens
  - tool-use prompt tokens
- `estimated_ingest_cost_usd` and `estimated_runtime_cost_usd` remain
  estimates from usage metadata and the profile pricing table, not Cloud
  Billing invoice amounts.
- Full-eval results preserve per-question `agent_llm_usage`,
  `judge_llm_usage`, combined `llm_usage`, and aggregate `llm_*` token totals
  so runtime/evaluator cost can be compared against ingest cost.
- Embedding APIs do not return usage metadata through the LangChain embedding
  interface, so the project records embedding input volume instead:
  API calls, input text count, input characters, and local estimated input
  tokens. `estimated_*_embedding_cost_usd` is populated only when a profile
  provides `embedding_input_per_million_tokens_usd`.
- Default runtime behavior remains unchanged unless a budget is supplied. Query
  dedupe is enabled only for explicitly budgeted retrieval stages.
- Use this for focused triage before changing retrieval policy or ontology:
  it is an execution-cost control, not a benchmark-answer rule.
- Benchmark runner now supports focused LLM route probes without editing the
  profile via `--llm-route phase=provider:model`.
- Local `HYU_T2_010` evidence-extraction probe with
  `--llm-route evidence_extraction=google:gemini-2.5-flash` did not preserve
  the gate contract: faithfulness and completeness fell to `0.500`, and the
  rendered growth calculation drifted to `12.3%`. Keep
  `evidence_extraction = gemini-2.5-pro` for the official gate until a broader
  low-cost route canary proves otherwise.
- First bounded low-API canary:
  - `NAV_T1_030` with budgets `12 / 6 / 2` passed.
  - `retrieval_debug_trace.query_budget` recorded `primary 3/3`,
    `operand_focus 6/16`, and `retry 0/0`.
  - API calls and estimated cost remained `0 / $0.0000`.
- Second bounded low-API canary:
  - `SKH_T1_060` passed with tighter budgets `8 / 4 / 1`.
  - The trace reduced executed retrieval searches to 12
    (`primary = 8`, `operand_focus = 4`, `retry = 0`) while preserving
    `numeric_final_judgement = PASS`.
  - `KBF_T1_017` also passed numerically with `8 / 4 / 1` and 12 executed
    retrieval searches.
  - `NAV_T1_071` was confirmed to be a separate runtime regression rather than
    a budget-only regression: `8 / 4 / 1`, `12 / 6 / 2`, and unbounded focused
    low-API runs all failed with the same stale `0원` difference shape before
    the runtime fix.
  - The `NAV_T1_071` root cause was period-insensitive precision refinement:
    a prior-period lookup initially selected the correct fiscal column, then
    contextual table-cell refinement overwrote it with the current-period cell.
  - The fix makes precision refinement reuse the generic period-aware structured
    cell selector; the focused low-API canary now passes with current
    `1,481,396,317,551원`, prior `1,083,717,091,152원`, and delta `3,977억원`.
  - Query-budget selection now preserves period diversity before truncation so
    explicitly budgeted multi-period comparisons do not silently drop all
    prior-period search surfaces.
- Broader `8 / 4 / 1` promotion check:
  - The official 5-question runtime contract gate set passed under focused
    low-API/BM25 conditions.
  - Results: `NAV_T1_030`, `NAV_T1_071`, `MIX_T1_021`, `KBF_T1_017`, and
    `SKH_T1_060` all returned `numeric_final_judgement = PASS`.
  - Executed retrieval searches were bounded at 7 to 12 per question, with
    no retry queries needed.
  - Treat `8 / 4 / 1` as a viable default candidate, pending one broader
    non-gate inventory check.
  - Separate renderer cleanup remains: `KBF_T1_017` can still append a
    partial-refusal suffix despite numeric PASS, and `NAV_T1_071` uses an
    awkward difference sentence.
- Non-gate `8 / 4 / 1` inventory check:
  - Four curated non-gate questions were tested across the existing
    runtime-contract company set: `NAV_T2_006`, `SAM_T3_028`, `KBF_T2_043`,
    and `SKH_T3_080`.
  - `SAM_T3_028` and `SKH_T3_080` passed numerically.
  - `KBF_T2_043` returned `UNCERTAIN`, and `NAV_T2_006` produced no numeric
    judgement with noisy mixed synthesis.
  - These two non-PASS cases are not budget-truncation failures: their executed
    query traces were `1/1` and `2/2`, with no dropped primary, operand-focused,
    or retry queries.
  - The budget is therefore still a viable default candidate; the next work is
    separate runtime quality cleanup for noisy synthesis and material-gap
    replan behavior.
- Official LLM-evidence-path canary after fallback removal:
  - `NAV_T2_006` passed under the policy-driven gate profile with `8 / 4 / 1`.
  - Final answer preserved `41.4%` and the Poshmark/smart-store/brand-store
    explanation.
  - Metrics: faithfulness `1.000`, answer relevancy `0.837`, context recall
    `1.000`, retrieval hit `1.000`, context P@5 `0.800`, completeness `1.000`,
    error rate `0.0%`.
  - Final narrative retrieval trace selected `3` primary queries, `0`
    operand-focus queries, and `0` retry queries while recording the broader
    state-level query count as `61`.

## Latest Fresh Concept Gate Refresh

- A 2026-06-04 fresh concept-runtime-gate refresh with OpenAI
  `text-embedding-3-large` initially exposed focused failures in
  `POS_T1_057`, `KBF_T2_018`, `KAB_T1_066`, and `SAM_T3_028`.
- The current local result directory
  `benchmarks/results/concept_gate_refresh_after_answer_composition_2026-06-04/`
  is a mutable local experiment artifact and is not committed.
- The latest store-fixed eval-only refresh now reports `7 / 7 PASS`:
  `KBF_T2_018`, `POS_T1_057`, `SKH_T3_080`, `SAM_T3_028`, `CEL_T1_013`,
  `CEL_T3_040`, and `KAB_T1_066`.
- Closures stayed generic:
  - aggregate structured cell selection uses reviewed row/cell metadata
  - contextual precision refinement cannot replace a detailed source display
    with a large-scale-drift table cell
  - ratio tasks can prefer an active reconciled operand set when it covers all
    required operands
  - quantitative-impact assembly only asserts inclusion/impact relations when
    the relation is visible in evidence
  - percent answers preserve formula operand evidence even if the final sentence
    renders only the derived percentage
  - ratio denominator sign semantics are declared in ontology binding policy and
    consumed generically by runtime calculation
  - table metadata rows that support final-answer numeric material are promoted
    into evaluator-visible evidence claims
  - short unitless `UNKNOWN` numerics are not treated as material aggregate
    operands
  - unscoped lookup/ratio tasks reject context-dependent segment/total table
    rows before sibling recovery or direct operand extraction can promote them
- Broader operation-contract follow-up after the closure commit is also green:
  runtime domain-term audit passed, `tests.test_subtask_loop` passed `91`
  tests, the related answer-composition / lookup-recovery suite passed `182`
  tests, and full unittest discovery passed `687` tests.
- MAS replan-edge follow-up is green: runtime domain-term audit passed,
  projection/MAS focused tests passed `34` tests, and full unittest discovery
  passed `780` tests.
- MAS real-node smoke observability follow-up is green at the contract-test
  layer: the new smoke-script tests passed with the MAS focused suite, runtime
  domain-term audit passed, and full unittest discovery passed `782` tests. A
  live smoke run was not executed because `GOOGLE_API_KEY` is not set in the
  current shell.
- Follow-up live smoke with `.env`-loaded credentials is green on a compatible
  local Samsung 2023 OpenAI-3072 store. The Critic retry-control regression fix
  and smoke scope/progress options are covered by focused tests; full discovery
  should be rerun after this doc update before publishing.
- Latest focused checks:
  - `KBF_T2_018`: PASS; faithfulness `1.0`, completeness `1.0`, numeric
    grounding `1.0`, retrieval support `1.0`.
  - `POS_T1_057`: PASS; faithfulness `1.0`, completeness `1.0`, numeric
    grounding `1.0`, retrieval support `1.0`.
  - `SAM_T3_028`: PASS; faithfulness `1.0`, completeness `1.0`; the final
    answer preserves the inventory valuation loss/reversal/disposal values and
    the cost-of-sales impact relation without adding a runtime keyword branch.
- Residual follow-up: no active concept-gate blocker remains. Future work is
  promotion-risk management, cost/runtime control, and task-ledger/artifact
  contract cleanup.
