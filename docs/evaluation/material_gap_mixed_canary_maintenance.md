# Material-Gap And Mixed Narrative Canary Maintenance

Date: 2026-06-07

This note fixes the current maintenance policy for the two non-gate residual
families that have been easy to confuse with active runtime blockers:

- material-gap / narrative numeric closure, represented by `KBF_T2_043`
- mixed numeric+narrative growth answers, represented by `NAV_T2_006`

No new benchmark was run for this review. Existing `benchmarks/results/**`
bundles remain local experiment artifacts and are not commit targets.

## Current Classification

| Case | Current status | Evidence basis | Maintenance action |
| --- | --- | --- | --- |
| `KBF_T2_043` | Closed runtime blocker; broader replay and completeness/render calibration watch item | PR #35 focused store-fixed eval-only returned `numeric_final_judgement = PASS`, faithfulness `1.0`, numeric grounding `1.0`, context recall `0.9`, completeness `0.7`, absolute error rate `0.0`, and unit consistency pass `1.0`. The older non-gate inventory `UNCERTAIN` row was not caused by query-budget truncation. | Recheck only when a future broader artifact reproduces a material-gap failure. Treat isolated completeness/render gaps as calibration debt unless material evidence is missing from the runtime trace. |
| `NAV_T2_006` | Closed mixed numeric+narrative quality target; policy-gate regression coverage | Policy-driven follow-ups recovered faithfulness, completeness, context recall, and retrieval hit@k to `1.000`. The final answer preserves the `41.4%` growth display and the source-visible driver context. PR #33 preserved retrieved-driver evidence without adding a company/question keyword branch. | Keep in policy-gate coverage. Do not patch runtime for cross-trace duplicate pressure alone; require a reproduced answer-quality or evidence-preservation failure. |

## Maintenance Rule

Use this decision order before changing runtime code:

1. If there is no fresh artifact, do not run a new full benchmark by default.
   Update classification from the current source-controlled docs and focused
   replay evidence only.
2. If a fresh artifact exists, first decide whether the failure is a runtime
   blocker or calibration debt.
3. Runtime blocker means the trace shows missing or wrong material evidence,
   wrong dependency binding, unsupported numeric claims, stale calculation
   projection, or final synthesis that drops source-visible required evidence.
4. Calibration debt means the answer is grounded and numerically correct, but a
   broader score remains low because of display/entity normalization,
   completeness wording, section-label drift, or reviewer/evaluator surface
   mismatch.
5. For runtime blockers, run a store-fixed focused eval-only replay first.
   Fresh ingest is reserved for parser, ingest, cache-signature, missing-store,
   or stale-store changes.
6. For calibration debt, document the classification and avoid adding runtime
   branches unless a user-visible answer failure is reproduced.

## Focused Replay Preference

When a replay is justified, prefer the smallest store-fixed path that covers the
case:

- `NAV_T2_006`: policy-driven runtime gate profile, single-question eval-only
  first.
- `KBF_T2_043`: broader/non-gate residual replay only when a newer artifact
  reproduces material-gap behavior; otherwise keep it as completeness/render
  calibration.

Long-running benchmark refreshes should use the normal heartbeat options and
must keep generated result bundles out of source commits.

## Evidence Requirements For Reopening

Do not reopen these cases as active runtime blockers unless the new artifact
shows at least one of the following:

- final answer has an unsupported numeric claim
- required source-visible numeric or narrative evidence is present in retrieved
  docs but absent from aggregate evidence/final answer
- `resolved_calculation_trace` or task/artifact projection carries stale or
  mismatched material
- material-gap feedback is missing when required operands/evidence are absent
- final synthesis suppresses a valid partial/refusal state despite an integrity
  or material-gap error

Signals that are not enough by themselves:

- cross-trace duplicate retrieval pressure
- a low completeness subscore with grounded numeric answer and visible source
  evidence
- a section/entity display mismatch that does not change the answer
- historical non-PASS rows already superseded by focused follow-up evidence

## Current Decision

There is no active material-gap or mixed narrative runtime blocker open. The
next project work may return to these canaries only when a fresh artifact
reproduces a concrete runtime failure. Until then, they are maintenance watch
items, not reasons to run a full benchmark or add runtime patches.
