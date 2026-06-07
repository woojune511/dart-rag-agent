# Broader Curated Gate Residual Review

Date: 2026-06-07

This review reconciles the broader curated maintenance notes after the focused
runtime-contract and policy-gate follow-ups. It does not introduce a new
benchmark run or a new official cross-profile score.

## Scope

Reviewed sources:

- `CONTEXT.md`
- `docs/overview/project_status.md`
- `docs/evaluation/benchmarking.md`
- `docs/evaluation/runtime_contract_gate.md`
- `docs/evaluation/concept_planner_shadow.md`
- `docs/history/experiment_history.md`

Local artifact policy:

- No new `benchmarks/results/**` bundle was generated for this review.
- Existing raw benchmark bundles remain local experiment artifacts and are not
  commit targets.
- Historical non-PASS rows are kept as screening evidence only when a later
  focused replay or follow-up document has superseded the blocker.

## Current Classification

| Case / area | Current classification | Evidence basis | Next action |
| --- | --- | --- | --- |
| `NAV_T1_030` | Calibration / presentation debt | Focused runtime-contract replay closed arithmetic, retrieval, section, citation, and provenance blockers; remaining `entity_coverage = 0.750` is display/entity normalization debt. | Track in evaluator/display cleanup only if a new broader artifact reproduces user-visible harm. |
| `KBF_T2_043` | Closed runtime blocker; broader replay/calibration candidate | PR #35 follow-up focused eval-only returned `numeric_final_judgement = PASS`, `faithfulness = 1.0`, `numeric_grounding = 1.0`, `context_recall = 0.9`, `completeness = 0.7`. The older `UNCERTAIN` row was not caused by query-budget truncation. | Recheck in a future broader replay; treat any remaining gap as completeness/render calibration unless material-gap evidence is reproduced. |
| `NAV_T2_006` | Closed mixed numeric+narrative quality target | Policy-driven gate follow-up recovered faithfulness/completeness/context recall/retrieval hit at `1.000` and preserved the growth display plus driver context. | Keep as policy-gate regression coverage; no broader blocker open. |
| `SAM_T3_028` | Closed source-level numeric blocker | Parser row-axis preservation and generic structured row/value assembly closed the inventory valuation row/value evidence path in focused fresh structural rerun. | No runtime rule should be reintroduced; rerun only if a fresh structural artifact regresses. |
| `SKH_T3_080`, `CEL_T1_013`, `CEL_T3_040` | Closed concept-runtime blocker set | The concept runtime gap baseline is frozen as `concept_runtime_gap_gate_7of7_2026-06-04` with `7 / 7 PASS`. Earlier blocker lists are historical triage. | Future concept-runtime changes should refresh the store-fixed gate first when stores are available. |
| `KBF_T1_017`, `NAV_T1_071` answer wording | Renderer polish, not numeric blocker | Focused runtime-contract gate passed numerically under bounded `8 / 4 / 1` budgets; remaining issues are partial-refusal suffix / awkward difference wording. | Address under answer-language polish, not gate maintenance. |

## Review Decision

There is no current active broader curated runtime blocker that justifies a new
fresh full benchmark run before more targeted work. The maintenance rule is:

1. Keep closed blockers closed unless a new artifact reproduces the failure as
   a runtime evidence, dependency, calculation, or provenance issue.
2. Keep `KBF_T2_043` and `NAV_T1_030` visible as calibration/replay watch items,
   not as active runtime blockers.
3. Prefer store-fixed focused eval-only refreshes for future residual checks.
4. Use monitored fresh ingest only when parser/ingest/cache-signature changes or
   missing/stale stores make store-fixed replay invalid.

For the dedicated material-gap and mixed numeric/narrative maintenance policy,
see `docs/evaluation/material_gap_mixed_canary_maintenance.md`.

## Next Priority

Broader curated maintenance should return only when a new broader artifact
reproduces a concrete blocker rather than display, entity-normalization, or
completeness-render calibration debt.
