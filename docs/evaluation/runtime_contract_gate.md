# Runtime Contract Gate

This document defines the official runtime smoke gate that must pass before
promoting curated mainline benchmark-profile changes or landing runtime-contract
changes that affect numeric planning, grounding, aggregation, or evaluator
projection.

## Canonical profile

- Profile:
  - `benchmarks/profiles/curated_runtime_contract_gate.json`

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
- Runtime outputs must preserve:
  - `structured_result`
  - `resolved_calculation_trace`
- No fallback retrieval backend should be used in benchmark mode.

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
