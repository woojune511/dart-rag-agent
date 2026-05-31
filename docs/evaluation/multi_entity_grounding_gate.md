# Multi-Entity Grounding Gate

This document defines the focused smoke gate for multi-entity and segment-style
numeric grounding. It complements the broader runtime-contract gate by checking
that repeated concepts such as `revenue` do not collapse into the same
company-total row when the query asks about multiple business entities.

## Canonical profile

- Profile:
  - `benchmarks/profiles/curated_multi_entity_grounding_gate.json`

## Default candidate

- `structural_selective_v2_prefix_2500_320`

This focused gate is intended to keep multi-entity and segment grounding stable
on the structural ingest path that we expect to run routinely.

`contextual_selective_v2_prefix_2500_320` remains a historical quality
reference, but it is no longer part of the default focused-gate profile. Use it
only when a structural regression needs explicit arbitration against the old
contextual ingest baseline.

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
- Run this gate with `structural_selective_v2_prefix_2500_320` only in routine
  validation.
- Treat embedding-provider/model/dimension mismatch as cache miss and reindex.
- Reuse the validated Samsung 2024 selective store only when the
  `store_signature` matches exactly.

## Recommended invocation

Full gate run, including parse / ingest / screening when the store is missing
or invalidated:

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_multi_entity_grounding_gate.json `
  --output-dir benchmarks/results/multi_entity_grounding_gate_manual
```

Store-fixed rerun, for current agent/evaluator validation after a successful
full gate has already produced `results.json` and `stores/`:

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_multi_entity_grounding_gate.json `
  --output-dir benchmarks/results/multi_entity_grounding_gate_manual `
  --company-run-id samsung_2024_multi_entity_grounding_gate `
  --eval-only
```

`--eval-only` skips parse / ingest / screening, but it still reruns answer
generation and full evaluation. Use retrospective evaluator scripts instead
when the goal is to re-score the exact historical answers without rerunning the
agent.

Focused single-question rerun:

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_multi_entity_grounding_gate.json `
  --output-dir benchmarks/results/multi_entity_grounding_gate_manual `
  --company-run-id samsung_2024_multi_entity_grounding_gate `
  --eval-only `
  --question-id comparison_002
```

Fast numeric canary mode:

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_multi_entity_grounding_gate.json `
  --output-dir benchmarks/results/multi_entity_grounding_gate_manual `
  --company-run-id samsung_2024_multi_entity_grounding_gate `
  --eval-only `
  --question-id comparison_002 `
  --numeric-fast-gate
```

Historical answer replay, with no agent rerun:

```powershell
.\.venv\Scripts\python.exe -m src.ops.replay_full_eval_from_results `
  --source-results benchmarks/results/multi_entity_grounding_gate_manual/삼성전자-2024/results.json `
  --dataset-path benchmarks/eval_dataset.math_focus.json `
  --output-dir benchmarks/results/replay_multi_entity_manual `
  --question-id comparison_002
```

## Pass criteria

- All three gate questions must finish with `numeric_final_judgement = PASS`.
- Operand binding must preserve distinct entity-scoped operands in
  `resolved_calculation_trace` / `structured_result`.
- No fallback retrieval backend should be used in benchmark mode.

## Latest validation notes

- Last checked: 2026-05-31
- Historical replay source for `comparison_002`:
  - `benchmarks/results/dev_math_focus_evalonly_2026-04-28/삼성전자-2024/results.json`
- Latest replay output:
  - `benchmarks/results/replay_multi_entity_manual_2026-05-31/`
  - current-code replay refresh:
    `benchmarks/results/replay_multi_entity_manual_2026-05-31-current/`
- Replay result:
  - `comparison_002 = PASS`
  - `numeric_equivalence = 1.0`
  - `numeric_grounding = 1.0`
  - `numeric_retrieval_support = 1.0`
- Artifact hygiene note:
  - `benchmarks/results/multi_entity_grounding_gate_final_smoke_2026-05-30`
    currently contains a later cap-affected `comparison_002 = UNCERTAIN`
    result, so do not use that bundle as the replay source for the solved-case
    regression check.
- Operating rule:
  - solved multi-entity cases should be checked by historical replay first
  - rerun the live focused gate only when multi-entity routing, retrieval,
    reconciliation, calculation, or evaluator projection changed

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
  - `차이 = 81조 9,081억원`

## Regression fixed on 2026-05-30

The multi-entity failure mode was not retrieval miss. The correct segment row
was retrieved, but the lookup fast path could accept an LLM-extracted aggregate
or partial numeric substring as `ev_001` before reconciliation had a chance to
bind the structured segment row.

The runtime now protects component lookups by:

- focusing `numeric_extractor` on the active lookup operand rather than the
  whole comparison question
- rejecting lookup fast-path values that look like aggregate outputs such as
  difference, sum, ratio, or growth
- requiring exact numeric-token support instead of substring matches
- letting reconciliation bind the structured row when the fast path cannot
  prove direct operand support

## Current interpretation

- `contextual_selective_v2_prefix_2500_320`
  - historical quality reference
  - only rerun when explicit comparison against the old contextual baseline is
    needed
- `structural_selective_v2_prefix_2500_320`
  - focused gate PASS
  - current practical default because it preserves entity-scoped grounding
    quality without paying the full contextual ingest cost

This focused gate exists to reject structural regressions that collapse
repeated concepts onto the same company-total row. `structural_selective_v2`
currently clears that bar, so multi-entity grounding is no longer the blocking
concern for that candidate.
