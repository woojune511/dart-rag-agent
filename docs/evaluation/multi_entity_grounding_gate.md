# Multi-Entity Grounding Gate

This document defines the focused smoke gate for multi-entity and segment-style
numeric grounding. It complements the broader runtime-contract gate by checking
that repeated concepts such as `revenue` do not collapse into the same
company-total row when the query asks about multiple business entities.

## Canonical profile

- Profile:
  - `benchmarks/profiles/curated_multi_entity_grounding_gate.json`

## Gate question set

- `comparison_001`
- `comparison_002`
- `comparison_003`

These three questions cover:

- same-document multi-entity difference (`DX` vs `DS`)
- same-document multi-entity sum (`SDC` + `Harman`)
- mixed segment/plain-entity difference (`DS` vs `SDC`)

## Execution policy

- Keep `allow_retrieval_fallback = false`.
- Treat embedding-provider/model/dimension mismatch as cache miss and reindex.
- Reuse the validated Samsung 2024 selective store only when the
  `store_signature` matches exactly.

## Recommended invocation

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_multi_entity_grounding_gate.json `
  --output-dir benchmarks/results/multi_entity_grounding_gate_manual
```

## Pass criteria

- All three gate questions must finish with `numeric_final_judgement = PASS`.
- Operand binding must preserve distinct entity-scoped operands in
  `resolved_calculation_trace` / `structured_result`.
- No fallback retrieval backend should be used in benchmark mode.

## Latest direct runtime validation

- `comparison_001`
  - `DX 매출액 = 174조 8,877억원`
  - `DS 매출액 = 111조 660억원`
  - `차이 = 63조 8,217억원`
- `comparison_002`
  - `SDC 매출액 = 29조 1,578억원`
  - `Harman 매출액 = 14조 2,749억원`
  - `합계 = 43조 4,327억원`
- `comparison_003`
  - `DS 매출액 = 111조 660억원`
  - `SDC 매출액 = 29조 1,578억원`
  - `차이 = 81조 9,082억원`
