# Runtime Contract Gate

This document defines the official runtime smoke gate that must pass before
promoting curated mainline benchmark-profile changes or landing runtime-contract
changes that affect numeric planning, grounding, aggregation, or evaluator
projection.

## Canonical profile

- Profile:
  - `benchmarks/profiles/curated_runtime_contract_gate.json`

## Default candidate

- `structural_selective_v2_prefix_2500_320`

`structural_selective_v2` keeps the selective-v2 chunk filter but removes
Gemini-written chunk context generation. It relies only on deterministic
structural prefixes derived from local metadata such as section path, statement
type, table context, and row-label text.

`contextual_selective_v2_prefix_2500_320` remains the quality reference, but it
is no longer part of the routine gate profile. Use it only for explicit
promotion arbitration or tie-breaker reruns when a structural regression needs
to be compared against the old ingest-time contextual baseline.

## Gate question set

- `NAV_T1_030`
- `NAV_T1_071`
- `MIX_T1_021`
- `KBF_T1_017`
- `SKH_T1_060`

These five questions cover:

- deterministic subtractive metrics (`NAV_T1_030`)
- lookup + difference material preservation (`NAV_T1_071`)
- multi-metric aggregate answers (`MIX_T1_021`)
- percent multi-period grounding (`KBF_T1_017`)
- concept-ratio grounding with direct-first acceptance (`SKH_T1_060`)

## Execution policy

- Keep `allow_retrieval_fallback = false`.
- Keep `auto_fetch_missing_report = true` so the gate can recover missing local
  filings from DART without changing the required receipt number.
- Run this gate with `structural_selective_v2_prefix_2500_320` only in normal
  development and release checks.
- Treat embedding-provider/model/dimension mismatch as cache miss and reindex.
- Use the stored `store_signature` / `benchmark_cache_meta.json` metadata to
  avoid cross-environment store reuse mistakes.

## Recommended invocation

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_runtime_contract_gate.json `
  --output-dir benchmarks/results/runtime_contract_gate_manual
```

## Pass criteria

- All five gate questions must finish with `numeric_final_judgement = PASS`.
- Any candidate with one or more full-evaluation question failures is
  disqualified as the default runtime candidate, even if it is cheaper or
  faster to ingest.
- Runtime outputs must preserve:
  - `structured_result`
  - `resolved_calculation_trace`
- No fallback retrieval backend should be used in benchmark mode.

## Current interpretation

Current gate interpretation is now stable:

- `plain_prefix_8000_400`
  - speed / cost baseline
  - not eligible as default because `SKH_T1_060` fails
- `contextual_selective_v2_prefix_2500_320`
  - historical quality reference
  - only rerun when explicit arbitration against the old contextual baseline is
    needed
- `structural_selective_v2_prefix_2500_320`
  - all five gate questions pass
  - current operating default because it preserves gate quality without the
    full ingest-time cost of contextual selective ingestion
  - latest `SKH_T1_060` closure came from note-aggregate lookup hardening for
    `장기차입금` / `사채`, not from relaxing the gate

## Related canary

- `comparison_002` is the current multi-entity / segment-grounding canary.
- Latest runtime fix:
  - repeated `revenue` addends from the LLM concept planner are rehydrated with
    `segment_label` metadata (`SDC`, `Harman`) before grounding
  - segment-scoped direct grounding rejects non-matching company-total rows
- Latest direct runtime result on Samsung 2024:
  - `SDC 매출액 = 29조 1,578억원`
  - `Harman 매출액 = 14조 2,749억원`
  - `합계 = 43조 4,327억원`

## Related focused gate

- Multi-entity / segment-style comparisons now have a dedicated focused gate:
  - `docs/evaluation/multi_entity_grounding_gate.md`
  - `benchmarks/profiles/curated_multi_entity_grounding_gate.json`
- Current covered questions:
  - `comparison_001`
  - `comparison_002`
  - `comparison_003`

## Concept Runtime Gap Gate

Concept-planner gap closures now have a dedicated focused runtime gate:

- Profile:
  - `benchmarks/profiles/curated_concept_runtime_gap_gate.json`
- Candidate:
  - `structural_selective_v2_prefix_2500_320`
- Covered questions:
  - `KBF_T2_018`
  - `SKH_T3_080`
  - `CEL_T1_013`
  - `CEL_T3_040`
  - `POS_T1_057`
  - `KAB_T1_066`
  - `SAM_T3_028`

The gate exists because the expanded concept-planner shadow probe identified
real runtime gaps that planner-structure validation alone could not prove:

- missing or underspecified ontology concepts
- concept aliases and section priors that were too weak for retrieval
- row-family selection failures when the right structured table was retrieved
  but the wrong sibling row was selected
- direct lookup rendering that rounded source table units and weakened numeric
  grounding

Promotion decision:

- Keep the original five-question `curated_runtime_contract_gate.json` as the
  default short runtime smoke gate.
- Promote these seven cases as a separate official focused gate rather than
  merging them into the default smoke gate.
- Run this gate when changing concept ontology, concept planning, structured
  row binding, lookup rendering, reconciliation retry queries, or numeric
  evaluator projection.

Latest verification:

- Date: 2026-05-28
- Temporary validation profile:
  - `benchmarks/profiles/tmp_concept_runtime_gap_gate_2026-05-28.json`
- Output directory:
  - `benchmarks/results/tmp_concept_runtime_gap_gate_2026-05-28/`
- Artifact status:
  - temporary local output was summarized here and later cleaned; use the
    reusable profile below for reruns.
- Result:
  - 7 / 7 questions finished with `numeric_final_judgement = PASS`
  - `numeric_equivalence = 1.0` and `numeric_grounding = 1.0` for all seven
    questions

Recommended invocation:

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_concept_runtime_gap_gate.json `
  --output-dir benchmarks/results/concept_runtime_gap_gate_manual
```

## Policy-Driven Runtime Gate

Retrieval-policy changes have a separate focused gate:

- Profile:
  - `benchmarks/profiles/curated_policy_driven_runtime_gate.json`
- Candidate:
  - `structural_selective_v2_prefix_2500_320`
- Covered full-evaluation questions:
  - `NAV_T2_006`
  - `HYU_T2_010`
  - `HYU_T3_072`
  - `LGE_T1_051`
  - `SAM_T2_078`
- Additional smoke coverage:
  - Samsung dividend cash outflow + shareholder-return policy mixed query

Run this gate when changing `src/config/retrieval_policy.py`, narrative summary
selection, policy-driven deterministic composers, or planner fallback tracing.
The purpose is to prove that vocabulary has moved into policy/config without
losing behavior on the previously hard-coded retrieval/composition cases.

Current gate status:

- 2026-05-30 refresh:
  - output bundle: `benchmarks/results/policy_gate_refresh_2026-05-30/`
  - completed company runs: `NAVER 2023`, `현대자동차 2023`,
    `LG에너지솔루션 2023`, `삼성전자 2023`
  - pending company runs: none
  - winner ranking for the four-company bundle:
    `pass_count = 4`, `company_count = 4`, `full_eval_fail_count = 0`,
    `critical_category_miss_count = 0`
  - `NAV_T2_006`: `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`
  - `HYU_T2_010`: `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`; answer covers
    `78.1만 대`, `87.0만 대`, `11.5%`, and IRA / 핵심원자재법 /
    보호무역주의 대응 필요성.
  - `HYU_T3_072`: `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`; answer covers
    Motional 기초 지분율 `50.00%`, 기말 지분율 `25.81%`,
    투자장부금액 `1,294,367백만원`, 계속영업손실 `(803,742)백만원`,
    and 총포괄손실 `(791,627)백만원`.
  - `SAM_T2_078`: `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`
  - `LGE_T1_051`: numeric path is closed with
    `numeric_final_judgement = PASS`, `numeric_equivalence = 1.0`,
    `numeric_grounding = 1.0`, and `numeric_retrieval_support = 1.0`.
    The current official answer includes the company context and exact AMPC
    value: `LG에너지솔루션 2023년 연결기준 영업이익 2,163,234백만원`,
    `AMPC 676,874백만원(약 6,769억원)`, and
    `실질 영업이익 1,486,360백만원`; `completeness = 1.0`.
  - aggregate full-eval metrics: `avg_full_faithfulness = 1.0`,
    `avg_full_completeness = 1.0`, `avg_full_numeric_pass_rate = 1.0`,
    and `avg_full_context_recall = 1.0`.
  - Runtime/evaluator hardening from this refresh:
    slot-derived evaluator operands now preserve resolved sibling-task
    metadata (`dependency_resolved`, `source_task_id`, `source_slot`) from the
    original calculation trace, and a resolved `task_output:*` operand no
    longer needs its own `source_anchor` to allow deterministic numeric
    grounding override. Unresolved task-output-only operands remain blocked.
    Slot-based difference answers also recover company context from grounded
    slot anchors when `report_scope.company` is unavailable.

- 2026-05-29 cleanup update:
  - Removed the runtime deterministic composer that hard-coded one
    policy-growth sales case shape. Future coverage for that class should come
    from policy-driven retrieval, structured growth operands, and narrative
    evidence synthesis rather than a case regex.
  - Moved dividend payout extraction patterns, statement hints, and answer
    templates into retrieval policy config; the runtime path consumes policy
    fields generically.
  - A local five-question replay was attempted with a temporary profile but was
    stopped after exceeding the no-result-file budget while rebuilding stores.
    The partial store/log output is local experiment material only.
  - Unit verification after the cleanup: `python -m unittest discover -s tests`
    passed (`470` tests).

- The 2026-05-29 policy-driven full gate rerun is closed for the structural
  candidate.
  - output bundle: `benchmarks/results/policy_driven_runtime_gate_rerun_2026-05-29/`
  - `pass_count = 4`
  - corrected `full_eval_fail_count = 0`
  - average full-eval metrics: `faithfulness = 1.0`, `completeness = 1.0`,
    `numeric_pass_rate = 1.0`, `context_recall = 1.0`
- Summary semantics: `numeric_pass_rate = None` on non-numeric or narrative
  questions is treated as not-applicable, not as a full-eval failure. Missing
  faithfulness or completeness still fails the row.
- `SAM_T2_078` was already passing in the official 2026-05-29 full-evaluation
  output.
- `LGE_T1_051` is closed in the latest full gate after preserving prose AMPC
  evidence and refining the operand from contextual note structured table
  cells:
  - latest full-gate answer: `영업이익 2,163,234백만원`, `AMPC 676,874백만원`, `실질 영업이익 1,486,360백만원`
  - `numeric_equivalence = 1.0`
  - `numeric_grounding = 1.0`
  - `numeric_retrieval_support = 1.0`
  - `numeric_final_judgement = PASS`
  - `faithfulness = 1.0`
  - `completeness = 1.0`
  - `grounded_rendering_correctness = 1.0`
  - `calculation_correctness = 1.0`
  - runtime hardening:
    exact parenthetical KRW values such as `6,769억원(676,874백만원)` are
    preferred when present, rounded or derived LLM operands can be refined from
    structured table cells or contextual note rows, and adjusted/exclusion
    difference results render from slot contracts before LLM synthesis.
- `NAV_T2_006` is closed in the latest targeted smoke after suppressing stale
  growth+narrative planner feedback only when the final answer already covers
  the growth-rate value and narrative impact:
  - `faithfulness = 1.0`
  - `completeness = 1.0`
  - `refusal_accuracy = 1.0`
  - final answer no longer carries the partial-refusal suffix
- `HYU_T2_010` is closed in the latest targeted smoke:
  - answer covers `87.0만 대`, `78.1만 대`, `11.5%`, IRA / 핵심원자재법 /
    보호무역주의 대응 필요성
  - `faithfulness = 1.0`
  - `raw_faithfulness = 0.5`
  - `faithfulness_override_reason = hybrid mixed-query evidence coverage가 충분해 faithfulness를 1.0으로 보정`
  - `completeness = 1.0`
  - `retrieval_hit_at_k = 1.0`
  - `grounded_rendering_correctness = 1.0`
  - `calculation_correctness = 1.0`
  - `avg_score = 0.890`
- `HYU_T3_072` is closed in the latest targeted smoke:
  - answer covers Motional `25.81%`, `1,294,367백만원`, 계속영업손실
    `(803,742)백만원`, 총포괄손실 `(791,627)백만원`
  - structured row evidence projection now surfaces the selected slot labels and
    values in runtime evidence, closing `entity_coverage = 1.0` in focused
    store-fixed eval-only.
  - `faithfulness = 1.0`
  - `raw_faithfulness = 0.5`
  - `faithfulness_override_reason = structured summary 계산/렌더링 검증이 충분해 faithfulness를 1.0으로 보정`
  - `completeness = 1.0`
  - `retrieval_hit_at_k = 1.0`
  - `grounded_rendering_correctness = 1.0`
  - `calculation_correctness = 1.0`
  - `avg_score = 0.910` in the latest store-fixed replay
  - follow-up narrative table-focus replay: `ndcg_at_5 = 1.195`,
    `context_precision_at_5 = 0.800`, `section_match_rate = 0.800`,
    `entity_coverage = 1.0`, `grounded_rendering_correctness = 1.0`,
    `avg_score = 0.939`.
    This uses table/numeric intent format inheritance and declarative slot/focus
    coverage, then prefers selected table sections for final fill rather than
    new runtime benchmark strings.
- These smoke checks use the official structural collection name
  `dart_reports_v2_structural-selective-v2-prefix-2500-320`.
- The raw rerun directory is a local benchmark artifact and should not be
  committed. Use the reusable profile below for future reruns.

Recommended invocation:

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_policy_driven_runtime_gate.json `
  --output-dir benchmarks/results/policy_driven_runtime_gate_manual
```
