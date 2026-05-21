# Contextual Arbitration Profile

This profile exists for explicit arbitration only.

## Canonical profile

- `benchmarks/profiles/curated_contextual_arbitration.json`

## Purpose

Use this profile only when a routine structural validation fails and we need to
compare the same curated set against the older contextual selective ingest
baseline.

This is not a routine smoke profile.

## When to use it

- a structural-only gate regresses and we need to know whether the problem is:
  - specific to `structural_selective_v2_prefix_2500_320`
  - or already present in the older contextual path
- a default-promotion decision needs a final reference rerun
- a tie-breaker is needed between two structural retrieval/ranking variants

## When not to use it

- ordinary code-change validation
- routine regression checks
- every pull or every ingest tweak

## Recommended invocation

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_contextual_arbitration.json `
  --output-dir benchmarks/results/contextual_arbitration_manual
```

## Policy

- Keep `allow_retrieval_fallback = false`.
- Treat `contextual_selective_v2_prefix_2500_320` as the historical quality
  reference, not the routine operating path.
- Prefer structural-only curated profiles for normal smoke and regression work.
