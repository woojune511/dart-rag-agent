# Structural Trace Diagnostics

Read-only diagnostics comparing dataset expected values with retrieval,
structured runtime state, and final calculation operands.

## Closed-Structural Full System: 2026-06-10 Regression

Result directory:

- `benchmarks/results/ablation_closed_structural_full_system_regression_2026-06-10`

| Question | Judgement | Expected values in retrieval | Expected values before final calc | Expected values in final operands | Final operands | Failure layer |
| --- | --- | --- | --- | --- | --- | --- |
| `CEL_T1_013` | PASS | 2/2: `342,736,271천원`, `181,624,107천원` | 2/2 | 2/2 | `181,624,107천원`<br>`342,736,271천원` | pass |
| `KAB_T1_066` | PASS | 2/2: `4355억원`, `11623억원` | 2/2 | 2/2 | `435,542백만원`<br>`11,623백만원` | pass |
| `POS_T1_057` | PASS | 2/2: `3,531,423백만원`, `1,001,290백만원` | 2/2 | 2/2 | `3,531,423백만원`<br>`1,001,290백만원` | pass |
| `SAM_T3_028` | PASS | 2/2: `5,037,579`, `180,388,580` | 2/2 | 2/2 | `5,037,579백만원`<br>`5,037,579백만원`<br>`180,388,580백만원` | pass |

Notes:

- The fixed full-system path preserves the required operands through retrieval,
  pre-calculation state, and final operands on all four closed-structural
  questions.
- `POS_T1_057` validates that task-output operands are not overwritten by a
  sibling direct-context row with different provenance.
- `SAM_T3_028` validates row-label specificity and structured provenance unit
  preservation for note-table values.

## Closed-Structural Plain Retrieval: 2026-06-10 Baseline

Result directory:

- `benchmarks/results/ablation_closed_structural_plain_retrieval_2026-06-10`

| Question | Judgement | Expected values in retrieval | Expected values before final calc | Expected values in final operands | Final operands | Failure layer |
| --- | --- | --- | --- | --- | --- | --- |
| `CEL_T1_013` | PASS | 2/2: `342,736,271천원`, `181,624,107천원` | 2/2 | 2/2 | `181,624,107백만원`<br>`342,736,271원` | pass |
| `KAB_T1_066` | PASS | 2/2: `4355억원`, `11623억원` | 2/2 | 2/2 | `435,542백만원`<br>`11,623억원` | pass |
| `POS_T1_057` | FAIL | 1/2: `1,001,290백만원` | 1/2 | 1/2 | `3,531,422,506,439백만원`<br>`1,001,290백만원` | retrieval coverage or evidence preservation |
| `SAM_T3_028` | PASS | 2/2: `5,037,579`, `180,388,580` | 2/2 | 0/2 | - | pass |

Notes:

- Plain retrieval passes three of four questions, so it is a strong baseline
  rather than a strawman.
- The key separating failure is `POS_T1_057`: the plain path retrieves or
  preserves only one expected value, then renders the operating-profit operand
  with a scale error (`3,531,422,506,439백만원`) and fails final numeric
  judgement.
- `CEL_T1_013` and `SAM_T3_028` pass by final numeric judgement, but the trace
  still exposes unit/display instability that should be discussed as residual
  risk rather than hidden.

## Interpretation

The current closed-structural slice supports a narrow measured claim:

- structural full-system: `4/4` numeric PASS
- plain retrieval baseline: `3/4` numeric PASS
- observed delta: `POS_T1_057`, where provenance-aware operand/unit handling
  prevents a scale mismatch that survives plain retrieval

This is not yet evidence for broad RAG superiority. It is evidence that the
structural path reduces one concrete failure mode: correct numeric evidence can
be present somewhere in the run, but final operand selection and unit rendering
can still drift without structured provenance and dependency-preservation
contracts.
