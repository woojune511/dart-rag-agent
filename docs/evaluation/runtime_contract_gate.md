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
  - current operating default candidate because it preserves gate quality
    without the
    full ingest-time cost of contextual selective ingestion

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
