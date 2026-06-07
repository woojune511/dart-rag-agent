# Concept Planner Shadow

## Purpose

`curated_concept_planner_shadow.json` is the planner-only comparison profile used to
measure how far the numeric planning path has moved from legacy
`metric_family`-first decomposition toward `concept + operation + operand role`
planning.

This is a **shadow compare**, not a runtime quality gate:

- it compares planner output only
- it does not prove retrieval / grounding / evaluator closure by itself
- it is meant to show whether concept-style planning is becoming the default
  shape for representative numeric questions

## Official Profile

- Profile:
  - `benchmarks/profiles/curated_concept_planner_shadow.json`
- Tool:
  - `src/ops/compare_concept_planner_shadow.py`

Recommended invocation:

```powershell
.\.venv\Scripts\python.exe -m src.ops.compare_concept_planner_shadow `
  --profile benchmarks/profiles/curated_concept_planner_shadow.json `
  --output benchmarks/results/curated_concept_planner_shadow_<date>.json
```

## Current Curated Coverage

The current curated shadow profile mixes:

- runtime contract canaries
  - `NAV_T1_030`
  - `NAV_T1_071`
  - `MIX_T1_021`
  - `KBF_T1_017`
  - `SKH_T1_060`
- focused multi-entity comparison canaries
  - `comparison_001`
  - `comparison_002`
  - `comparison_003`
- implicit shorthand prompts
  - `implicit_debt_ratio_samsung_2023`
  - `implicit_current_ratio_samsung_2023`
  - `implicit_fcf_naver_2023`

## 2026-05-21 Snapshot

Latest curated shadow run:

- output:
  - `benchmarks/results/curated_concept_planner_shadow_2026-05-21.json`

Observed pattern:

- all 11 curated cases changed between legacy and concept planning
- concept planner status was `concept_fallback` for all 11 cases
- key transitions:
  - `free_cash_flow` -> `concept_difference`
  - `generic_numeric` -> `concept_lookup + concept_difference`
  - `debt_ratio/current_ratio` -> `concept_ratio`
  - `concept_single_value` -> `concept_sum` for repeated-entity revenue sum

Representative examples:

- `NAV_T1_071`
  - legacy: one `generic_numeric` task
  - concept: `concept_lookup` + `concept_difference`
- `KBF_T1_017`
  - legacy: one `generic_numeric` task
  - concept: `concept_lookup` + `concept_difference`
- `comparison_002`
  - legacy: `concept_single_value`
  - concept: `concept_sum`

## 2026-05-28 Expanded Probe

An expanded 24-case shadow probe was run with the official curated canary plus
recent blocker and mixed numeric cases.

- output:
  - `benchmarks/results/tmp_curated_concept_planner_shadow_expanded_2026-05-28_concepts.json`
- profile:
  - `benchmarks/profiles/tmp_curated_concept_planner_shadow_expanded_2026-05-28.json`
  - temporary profile/result artifacts are not source commit targets
  - temporary local artifacts were summarized here and later cleaned

Observed pattern:

- concept planner status:
  - `concept_fallback`: 24 / 24
  - `heuristic_fallback`: 0 / 24
- legacy planner status:
  - `ok`: 9 / 24
  - `concept_fallback`: 9 / 24
  - `heuristic_fallback`: 6 / 24
- `implicit_fcf_naver_2023` is back to `concept_difference` after adding the
  generic `free_cash_flow_components` concept group:
  - `operating_cash_flow` as `minuend`
  - `property_plant_equipment_acquisition` as `subtrahend`
- repeated same-concept ratio operands are now preserved when the operands
  differ by role/segment/scope, e.g. segment operating income divided by
  company operating income.

## 2026-05-28 Gap Closure Rerun

After adding the ontology concepts identified by the expanded probe and local
DART report scans, the same 24-case shadow profile was rerun.

- output:
  - `benchmarks/results/tmp_curated_concept_planner_shadow_expanded_2026-05-28_concepts.json`
- artifact status:
  - temporary local output was summarized here and later cleaned
- concept planner status:
  - `concept_fallback`: 24 / 24
  - `heuristic_fallback`: 0 / 24

Closed gap cases:

- `KBF_T2_018`: `credit_loss_provision_expense` now plans as
  `concept_growth_rate` with current/prior operands.
- `SKH_T3_080`: `foreign_currency_translation_gain` and
  `foreign_currency_translation_loss` now plan as lookup tasks plus a
  `concept_difference` net-effect task.
- `CEL_T1_013`: `capitalized_development_cost` over
  `research_and_development_expense` now plans as `concept_ratio`.
- `CEL_T3_040`: inventory valuation loss, reversal, and disposal loss now plan
  as separate concept lookup tasks plus narrative summary.
- `SAM_T3_028`: inventory valuation loss is represented explicitly and can be
  compared against `cost_of_sales` without query-specific runtime row injection.
- `POS_T1_057`: interest coverage now plans as
  `operating_income / interest_expense`.
- `KAB_T1_066`: CIR now plans as
  `selling_general_administrative_expense / pre_expense_operating_profit`.

Additional DART-derived ontology additions:

- Local DART report scans under `data/reports` showed recurring note/statement
  surfaces for interest income/expense, allowance and bad debt terms,
  impairment, depreciation, and amortization.
- The concept ontology now includes generic DART note concepts for
  `interest_income`, `interest_expense`, `bad_debt_expense`,
  `depreciation_expense`, `amortization_expense`, `impairment_loss`, and
  `goodwill_impairment_loss`.

Verification:

- `python -m unittest tests.test_ontology tests.test_semantic_numeric_plan -v`
  passed: 69 tests.
- `python -m unittest discover -s tests -v` passed: 386 tests.
- Expanded shadow rerun passed planner-structure validation:
  `concept_fallback = 24 / 24`.

Runtime follow-up:

- The expanded probe showed where concept coverage was missing or weak, but it
  did not by itself prove retrieval, structured row binding, or final numeric
  grounding.
- The 2026-05-28 runtime gap gate rerun covered the seven then-closed gap cases:
  `KBF_T2_018`, `SKH_T3_080`, `CEL_T1_013`, `CEL_T3_040`, `POS_T1_057`,
  `KAB_T1_066`, and `SAM_T3_028`.
- Result:
  - 7 / 7 `numeric_final_judgement = PASS`
  - all seven had `numeric_equivalence = 1.0`
  - all seven had `numeric_grounding = 1.0`
- The reusable gate profile is now
  `benchmarks/profiles/curated_concept_runtime_gap_gate.json`.
- A 2026-06-01 reusable-profile rerun changed the promotion interpretation:
  `KBF_T2_018` is now closed as a small percent-rounding evaluator issue, while
  `SKH_T3_080`, `CEL_T1_013`, and `CEL_T3_040` remain runtime blockers after
  tightening multi-value numeric equivalence. Concept-only planner promotion is
  still blocked until those three close through generic runtime contracts.

Implementation boundary:

- The ontology additions remain concept-level aliases, surface contracts,
  section priors, and aggregate query surfaces.
- Runtime row selection uses structured candidate evidence and sibling-surface
  scoring. It should not grow question-specific deterministic fallback recipes
  for these benchmark rows.
- Direct lookup answers preserve source table units for grounded table values,
  which avoids evaluator failures caused by rounded compact display units.

## 2026-06-01 Runtime Promotion Check

After closing the remaining `SAM_T2_002` aggregate rendering issue, the concept
planner shadow was rerun to check whether the planner shape is ready for a
limited runtime promotion.

Commands:

```powershell
.\.venv\Scripts\python.exe -m src.ops.compare_concept_planner_shadow `
  --profile benchmarks\profiles\concept_planner_canary.json `
  --output benchmarks\results\tmp_concept_planner_canary_2026-06-01.json

.\.venv\Scripts\python.exe -m src.ops.compare_concept_planner_shadow `
  --profile benchmarks\profiles\curated_concept_planner_shadow.json `
  --output benchmarks\results\tmp_curated_concept_planner_shadow_2026-06-01.json

.\.venv\Scripts\python.exe -m unittest `
  tests.test_concept_runtime_contracts `
  tests.test_semantic_numeric_plan `
  tests.test_operation_contracts
```

Planner-only results:

- `concept_planner_canary.json`:
  - cases: `6`
  - changed vs legacy: `6 / 6`
  - legacy status: `ok = 5`, `heuristic_fallback = 1`
  - concept status: `concept_fallback = 6`
  - concept task families: `concept_ratio = 5`, `concept_difference = 2`,
    `concept_lookup = 1`
  - missing required operand concepts: `0`
- `curated_concept_planner_shadow.json`:
  - cases: `11`
  - changed vs legacy: `11 / 11`
  - legacy status: `ok = 6`, `heuristic_fallback = 5`
  - concept status: `concept_fallback = 11`
  - concept task families: `concept_difference = 6`, `concept_ratio = 5`,
    `concept_lookup = 2`, `concept_sum = 1`
  - missing required operand concepts: `0`

Validation:

- `tests.test_concept_runtime_contracts`,
  `tests.test_semantic_numeric_plan`, and `tests.test_operation_contracts`
  passed: `202` tests.

Promotion verdict:

- The concept planner is a **limited runtime-promotion candidate** for numeric
  planning because every curated shadow case now produces explicit
  concept/operation/operand-role tasks and none falls back to general search.
- It should not be promoted as a broad runtime default yet. The current shadow
  check is planner-only; it does not prove retrieval, reconciliation, answer
  rendering, or evaluator behavior.
- The next validation step is an end-to-end, store-fixed runtime gate on the
  same families that recently closed: `NAV_T1_071`, `KBF_T1_017`,
  `MIX_T1_021`, `SKH_T1_060`, and the implicit ratio/FCF prompts where stores
  are available.

Artifact policy:

- `benchmarks/results/tmp_concept_planner_canary_2026-06-01.json` and
  `benchmarks/results/tmp_curated_concept_planner_shadow_2026-06-01.json` are
  local planner-shadow outputs and should not be committed.

## 2026-06-01 Store-Fixed Runtime Promotion Smoke

After the planner-only promotion check, a minimal store-fixed runtime smoke was
run against cases whose stores were already available in
`benchmarks/results/policy_driven_runtime_gate_rerun_2026-05-29/`. This was not
a full promotion run; it was a cost-controlled check for whether planner shape
survives retrieval, reconciliation, calculation, rendering, and evaluator
contracts.

Commands:

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks\profiles\curated_runtime_contract_gate.json `
  --output-dir benchmarks\results\policy_driven_runtime_gate_rerun_2026-05-29 `
  --company-run-id naver_2023_runtime_contract_gate `
  --eval-only `
  --question-id NAV_T1_071 `
  --progress-heartbeat-sec 30

.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks\profiles\curated_runtime_contract_gate.json `
  --output-dir benchmarks\results\policy_driven_runtime_gate_rerun_2026-05-29 `
  --company-run-id samsung_2023_runtime_contract_gate `
  --eval-only `
  --question-id MIX_T1_021 `
  --progress-heartbeat-sec 30

.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks\profiles\curated_runtime_contract_gate.json `
  --output-dir benchmarks\results\policy_driven_runtime_gate_rerun_2026-05-29 `
  --company-run-id naver_2023_runtime_contract_gate `
  --eval-only `
  --question-id NAV_T1_030 `
  --progress-heartbeat-sec 30
```

Results:

- `NAV_T1_071` passed as a store-fixed runtime smoke:
  `numeric_final_judgement = PASS`, `faithfulness = 1.0`,
  `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`,
  `section_match_rate = 1.0`, `citation_coverage = 1.0`,
  `completeness = 1.0`, `avg_score = 0.970`.
- `MIX_T1_021` passed as a store-fixed runtime smoke:
  `numeric_final_judgement = PASS`, `faithfulness = 1.0`,
  `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`,
  `section_match_rate = 1.0`, `citation_coverage = 1.0`,
  `entity_coverage = 1.0`, `completeness = 1.0`, `avg_score = 0.980`.
- `NAV_T1_030` exposed a real runtime promotion blocker. The first run was
  evaluator-passing but arithmetically wrong because a cash-flow outflow
  operand was already signed negative and the metric-family task used
  `numerator` / `denominator` roles rather than `minuend` / `subtrahend`.
  The fix is generic: for `difference` operations, `numerator` / `denominator`
  are treated as left/right operands, and an already-negative right operand
  uses sign-aware subtraction (`A + B`). Answer rendering also rewrites the
  right operand as a positive amount when the answer says it is being
  subtracted.
- After the sign/rendering fix, `NAV_T1_030` produces the correct answer:
  `네이버의 2023년 연결기준 잉여현금흐름은 1조 3,616억원입니다. 이는
  영업활동현금흐름 2조 22억원에서 유형자산 취득액 6,406억원을 차감하여
  계산된 결과입니다.`
  Runtime metrics: `numeric_final_judgement = PASS`, `faithfulness = 1.0`,
  `context_recall = 1.0`, `completeness = 1.0`,
  `calculation_correctness = 1.0`.
- At this checkpoint, `NAV_T1_030` still had weak evaluator-visible retrieval
  metrics (`retrieval_hit_at_k = 0.0`, `section_match_rate = 0.0`,
  `citation_coverage = 0.667`, `entity_coverage = 0.5`). That made FCF
  numerically closed but not yet promotion-ready as an official runtime gate.

Updated promotion verdict:

- `NAV_T1_071` and `MIX_T1_021` support limited promotion for those operation
  families.
- `NAV_T1_030` blocks broad default promotion until retrieval/evidence
  visibility is fixed. The next work should improve evidence projection and
  evaluator-visible citation/section support, not add a question-specific
  calculation rule.

2026-06-07 projection follow-up:

- The public `FinancialAgent.run()` projection now promotes calculation-trace
  operand evidence into runtime evidence even when the graph did not emit
  separate top-level evidence rows.
- Runtime evidence metadata is filled from report scope when the operand row
  only carries a source anchor. The same evidence anchors are also exposed as
  citations, so evaluator-visible retrieval, section, and citation surfaces can
  see calculation provenance instead of depending only on the final retrieved
  window.
- This is a generic provenance projection change: it uses existing
  calculation trace operands, source anchors, report scope, and final-answer
  numeric surfaces. It does not add FCF-, company-, or benchmark-specific
  retrieval/routing behavior.
- Verification:
  - `python -m src.ops.audit_runtime_domain_terms`
  - `python -m unittest tests.test_financial_agent_run_projection tests.test_evaluator_runtime_projection tests.test_operation_contracts`
  - `python -m unittest tests.test_benchmark_runner_runtime_projection tests.test_eval_company_aliases tests.test_structured_operand_extraction`
  - `python -m unittest discover -s tests`
- Benchmark replay status: the local store-fixed bundle referenced by the
  older smoke note was not available in this workspace. The next empirical
  check should rerun `NAV_T1_030` under `curated_runtime_contract_gate` with a
  store-fixed bundle when available, or with a monitored fresh run if the store
  must be rebuilt.

2026-06-07 empirical replay:

- Profile:
  - `benchmarks/profiles/curated_runtime_contract_gate.json`
- Command shape:
  - `benchmark_runner --config benchmarks/profiles/curated_runtime_contract_gate.json --output-dir benchmarks/results/nav_t1_030_projection_replay_2026-06-07 --company-run-id naver_2023_runtime_contract_gate --eval-only --question-id NAV_T1_030 --progress-heartbeat-sec 30 --heartbeat-log <path>`
- Store/cache source:
  - copied local `naver-2023` bundle from
    `benchmarks/results/policy_gate_regression_2026-06-03_1138_actual/`
    into a new local replay directory before running eval-only, to avoid
    overwriting the older artifact
- Result:
  - `numeric_final_judgement = PASS`
  - `faithfulness = 1.000`
  - `context_recall = 1.000`
  - `retrieval_hit_at_k = 1.000`
  - `ndcg_at_5 = 1.000`
  - `context_precision_at_5 = 1.000`
  - `section_match_rate = 1.000`
  - `citation_coverage = 0.667`
  - `entity_coverage = 0.500`
  - `completeness = 1.000`
  - `numeric_pass_rate = 1.000`
  - `avg_score = 0.896`
  - `error_rate = 0.0%`
- Interpretation:
  - The original evaluator-visible retrieval/section blocker is closed for
    this replay: runtime evidence now exposes cash-flow calculation provenance
    strongly enough for hit@k and section match to reach `1.000`.
  - Broad concept-planner promotion should still keep a residual caveat for
    citation/entity surfaces. The replay citations include the relevant NAVER
    2023 source anchors, but citation coverage remains `0.667` and entity
    coverage remains `0.500`, so the remaining work is citation/entity surface
    normalization or display projection, not arithmetic, retrieval coverage, or
    FCF-specific planning.
- Artifact policy:
  - `benchmarks/results/nav_t1_030_projection_replay_2026-06-07/` is a local
    experiment artifact and should not be committed.

2026-06-07 surface-normalization replay:

- Change under test:
  - Evaluator runtime-evidence contexts now include metadata surfaces such as
    company, year, section path, statement type, and source anchor.
  - Citation coverage can use runtime evidence metadata directly when the
    final citation list has lossy or duplicated anchor strings.
  - Entity coverage accepts compact Korean surface variants for evaluator
    matching, such as possessive `의` differences, amount-label suffix `액`,
    and numeric year labels with or without `년`.
- This is evaluator-layer normalization only. It does not change retrieval,
  routing, answer composition, or add company-, benchmark-, or FCF-specific
  runtime behavior.
- Command shape:
  - `benchmark_runner --config benchmarks/profiles/curated_runtime_contract_gate.json --output-dir benchmarks/results/nav_t1_030_surface_replay_2026-06-07 --company-run-id naver_2023_runtime_contract_gate --eval-only --question-id NAV_T1_030 --progress-heartbeat-sec 30 --heartbeat-log <path>`
- Store/cache source:
  - copied the same local `naver-2023` bundle from
    `benchmarks/results/policy_gate_regression_2026-06-03_1138_actual/`
    into a fresh local replay directory before running eval-only.
- Result:
  - `numeric_final_judgement = PASS`
  - `faithfulness = 1.000`
  - `answer_relevancy = 0.707`
  - `context_recall = 1.000`
  - `retrieval_hit_at_k = 1.000`
  - `ndcg_at_5 = 1.000`
  - `context_precision_at_5 = 1.000`
  - `section_match_rate = 1.000`
  - `citation_coverage = 1.000`
  - `entity_coverage = 0.750`
  - `completeness = 1.000`
  - `refusal_accuracy = 1.000`
  - `numeric_pass_rate = 1.000`
  - `avg_score = 0.951`
  - `error_rate = 0.0%`
- Interpretation:
  - The prior residual citation-surface gap is closed for this focused replay:
    runtime evidence metadata supplies the expected company, year, and
    statement-section contract even when citation strings are noisy.
  - Entity coverage improves from `0.500` to `0.750`. The remaining miss is a
    display/metric-label surface issue rather than an arithmetic, retrieval,
    section, or evidence-provenance blocker.
  - The result supports promoting the generic runtime projection path with a
    smaller residual caveat around display/entity normalization. It should not
    be treated as a fresh full benchmark or a new official cross-profile score.
- Artifact policy:
  - `benchmarks/results/nav_t1_030_surface_replay_2026-06-07/` is a local
    experiment artifact and should not be committed.

Validation:

- `python -m unittest tests.test_operation_contracts tests.test_semantic_numeric_plan tests.test_subtask_loop`
  passed: `256` tests.
- `python -m unittest discover -s tests` passed: `555` tests.
- `python -m src.ops.audit_runtime_domain_terms --summary` passed with
  reviewed records `215` and literal occurrences `246`.

Artifact policy:

- The heartbeat logs and rewritten `benchmarks/results/policy_driven_runtime_gate_rerun_2026-05-29/`
  result files are local experiment artifacts and should not be committed.

## How To Interpret It

Good signs:

- fewer numeric questions are being flattened into opaque `generic_numeric`
- repeated-entity comparison questions are preserved as explicit
  `sum` / `difference` tasks
- implicit shorthand prompts are represented in the same concept-style operand
  schema as explicit benchmark questions

What this does **not** replace:

- `curated_runtime_contract_gate.json`
- `curated_multi_entity_grounding_gate.json`

Those remain the official runtime-quality smoke gates. The shadow profile is
specifically for planner-structure drift and regression detection.
