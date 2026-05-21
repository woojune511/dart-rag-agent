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
