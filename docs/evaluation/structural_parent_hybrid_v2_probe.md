# Structural Parent Hybrid v2 Probe

This document defines the first experimental comparison profile for
`structural_parent_hybrid_v2`.

## Goal

`structural_selective_v2_prefix_2500_320` is now the routine curated default.
The next ingest experiment should test whether we can recover some parent
lineage benefits without paying the ingest-time LLM cost of
`contextual_parent_hybrid`.

`structural_parent_hybrid_v2` keeps:

- the same `selective_v2` child-selection rules used by the current default
- zero-cost deterministic structural prefixes

and adds:

- deterministic parent digest text derived from the stored parent chunk
- no ingest-time LLM calls

## Canonical profile

- Profile:
  - `benchmarks/profiles/curated_structural_parent_hybrid_v2_probe.json`

## Candidate comparison

- baseline:
  - `structural_selective_v2_prefix_2500_320`
- proposed:
  - `structural_parent_hybrid_v2_prefix_2500_320`

## Probe question set

- `NAV_T1_071`
  - direct lookup + prior-period difference preservation
- `MIX_T1_046`
  - share-of-total ratio with note-table aggregate denominator
- `SAM_T2_002`
  - multi-report CAPEX total grounding and prior comparison

This probe is intentionally small. It is not a release gate. Its job is to tell
us whether deterministic parent digest text improves binding/ranking enough to
justify a broader curated rerun.

## Execution policy

- Keep `allow_retrieval_fallback = false`.
- Reuse validated structural stores when the `store_signature` matches.
- Treat this as an experiment profile, not a routine smoke profile.
- Only promote `structural_parent_hybrid_v2` to a broader validation if it does
  not regress the three probe questions.

## Recommended invocation

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_structural_parent_hybrid_v2_probe.json `
  --output-dir benchmarks/results/structural_parent_hybrid_v2_probe_manual
```

## Pass interpretation

- `structural_parent_hybrid_v2` is interesting if it:
  - preserves `numeric_final_judgement = PASS` on all probe questions
  - improves screening or completeness on `SAM_T2_002`
  - does not regress `MIX_T1_046` or `NAV_T1_071`
- If it only matches the current structural default with no meaningful quality
  gain, keep `structural_selective_v2` as the mainline default and stop there.
