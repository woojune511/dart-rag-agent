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
