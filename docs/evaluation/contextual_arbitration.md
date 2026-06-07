# Contextual Arbitration Profile

This profile exists for explicit arbitration only.

## Canonical profile

- `benchmarks/profiles/curated_contextual_arbitration.json`

## Purpose

Use this profile only when a routine structural validation fails and we need to
compare the same curated set against the older contextual selective ingest
baseline.

This is not a routine smoke profile.

## Candidate roles

| Candidate | Role | Routine use |
| --- | --- | --- |
| `structural_selective_v2_prefix_2500_320` | current operating default | yes |
| `contextual_selective_v2_prefix_2500_320` | historical quality reference | no |
| `plain_prefix_8000_400` | speed/cost baseline | no |

The arbitration question is narrow: did the structural path regress relative to
the older contextual path, or is the failure shared by both paths? Do not treat
a contextual pass by itself as permission to switch the runtime default.

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
- single-question canary loops before the structural trace has been classified

## Triage order

1. Run the relevant routine structural profile first.
2. If a question fails, classify the trace as retrieval coverage, dependency or
   synthesis, calculation safety, evaluator projection, or answer formatting.
3. Use store-fixed `--eval-only` refreshes before paying for fresh ingest.
4. Run this contextual profile only if the remaining hypothesis is that the
   structural ingest path itself lost evidence that contextual ingest preserved.

## Recommended invocation

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_contextual_arbitration.json `
  --output-dir benchmarks/results/contextual_arbitration_manual `
  --progress-heartbeat-sec 30 `
  --heartbeat-log benchmarks/results/contextual_arbitration_manual/_logs/heartbeat.jsonl
```

## Policy

- Keep `allow_retrieval_fallback = false`.
- Treat `contextual_selective_v2_prefix_2500_320` as the historical quality
  reference, not the routine operating path.
- Prefer structural-only curated profiles for normal smoke and regression work.
- Do not commit `benchmarks/results/contextual_arbitration_manual/`; summarize
  the result in docs when it affects a promotion or blocker decision.
