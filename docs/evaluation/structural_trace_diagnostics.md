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

The earlier closed-structural slice supported a narrow measured claim:

- structural full-system: `4/4` numeric PASS
- plain retrieval baseline: `3/4` numeric PASS
- observed delta: `POS_T1_057`, where provenance-aware operand/unit handling
  prevents a scale mismatch that survives plain retrieval

This is not yet evidence for broad RAG superiority. It is evidence that the
structural path reduces one concrete failure mode: correct numeric evidence can
be present somewhere in the run, but final operand selection and unit rendering
can still drift without structured provenance and dependency-preservation
contracts.

## Historical Expanded Candidate Refresh: 2026-06-10

Result directories:

- `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10`
- `benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10`

Run-level comparison:

| Metric | Structural full-system | Plain retrieval |
| --- | ---: | ---: |
| Avg numeric pass rate | `1.000` | `0.833` |
| Avg faithfulness | `1.000` | `0.875` |
| Avg completeness | `0.867` | `0.875` |
| Avg context recall | `0.889` | `0.861` |

Key question-level deltas:

| Question | Structural judgement | Plain judgement | Structural answer shape | Plain answer shape | Diagnostic read |
| --- | --- | --- | --- | --- | --- |
| `KBF_T1_017` | PASS | FAIL | `1.83%`, `1.73%`, `0.1%p` difference | same visible values, but operand selection `0.5` and numeric grounding `0` | plain representation could surface values but did not pass grounding/operand acceptance |
| `SKH_T3_080` | PASS | FAIL | `573,884백만원 - 906,120백만원 = -332,236백만원` | `868,767백만원 - 906,120백만원 = -37,353백만원` | structural row binding selected the correct foreign-currency translation gain surface |
| `SKH_T1_060` | PASS | PASS | `42.02%` debt-to-asset ratio | `42.02%` debt-to-asset ratio | hard aggregate case now passes both variants; useful positive control, not a separator |
| `MIX_T1_021` | PASS | PASS | debt ratio `25.36%`; current ratio `258.77%` | same final values | balance-sheet ratio control case |

Notes:

- This expanded refresh is historical diagnostic evidence, not the latest
  portfolio-facing result.
- `Full Eval Fails` in the cross-company summary is not identical to numeric
  failure. It also reflects completeness threshold misses. For this experiment,
  the reliable comparison is numeric grounding/faithfulness plus the
  per-question operand traces above.
- `SKH_T3_080` is the strongest narrative example because the plain path did
  not merely omit a value; it selected a plausible but wrong gain row and then
  produced a wrong deterministic difference.

## Current Expanded Full-System Refresh: 2026-06-17

Result directory:

- `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10`

Heartbeat log:

- `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_evalonly_current_2026-06-17.jsonl`

Run-level readout:

| Metric | Full-system refresh |
| --- | ---: |
| Numeric PASS | `6 / 9` |
| Avg numeric pass rate | `0.667` |
| Avg completeness | `0.600` |
| Avg faithfulness | `0.783` |
| Avg context recall | `0.889` |

Question-level read:

| Question | Judgement | Diagnostic read |
| --- | --- | --- |
| `KAB_T1_066` | PASS | positive CIR control remains stable |
| `POS_T1_057` | FAIL | high retrieval support, but signed/displayed interest-cost handling made the final ratio invalid |
| `SAM_T3_028` | PASS | inventory valuation loss and cost-of-sales denominator preserved |
| `MIX_T1_021` | PASS | both ratios computed, with partial final-answer completeness |
| `CEL_T1_013` | PASS | capitalized development cost and R&D denominator preserved |
| `KBF_T2_018` | FAIL | growth operands appeared in trace, but final answer was narrative-only |
| `KBF_T1_017` | PASS | NIM difference recovered through retry/aggregate fallback |
| `SKH_T3_080` | PASS | foreign-currency gain/loss row binding reproduced |
| `SKH_T1_060` | FAIL | debt-component numerator aggregation remains unstable |

Interpretation:

- The current refresh is a stop-line. It did not clear the `7 / 9`
  full-system threshold for running the plain-retrieval counterpart.
- `SKH_T3_080` remains the strongest current structural case-study trace.
- `POS_T1_057` and `KBF_T2_018` are higher-value residual fixes than spending
  on the plain baseline now because both expose final-state/composition issues
  after relevant evidence has been recovered.

## Hard Replay Separator: `SKH_T1_060` (2026-06-11)

Result directories:

- structural:
  summarized from `benchmarks/results/hard_current_evalonly_2026-06-10`
  before that local raw bundle was deleted under benchmark artifact hygiene
- plain:
  `benchmarks/results/ablation_structural_hard_plain_retrieval_2026-06-11`

Run-level comparison on the five-question hard set:

| Variant | Numeric pass | Avg completeness | Avg faithfulness | Avg recall |
| --- | ---: | ---: | ---: | ---: |
| Structural full-system | `5 / 5` | `0.938` | `1.000` | `0.827` |
| Plain retrieval | `4 / 5` | `0.812` | `0.875` | `0.932` |

`SKH_T1_060` is the separating case:

| Field | Structural | Plain |
| --- | --- | --- |
| Final judgement | PASS | FAIL |
| Final answer | `42.02%` | `34.32%` |
| Operand selection correctness | `1.0` | `0.4` |
| Faithfulness / completeness | `1.0 / 1.0` | `0.5 / 0.5` |
| Numerator rows | `4,145,647 + 10,121,033 + 9,490,410` | `3,833,263 + 9,073,567 + 6,497,790` |
| Denominator rows | `52,704,853 + 3,834,567` | `52,704,853 + 3,834,567` |

Trace-level read:

| Trace field | Structural path | Plain path |
| --- | --- | --- |
| borrowing summary table | `::table:93` | `::table:94` |
| `period_focus` | `current` | `prior` |
| `period_labels` | `["당기"]` | `["전기"]` |
| `table_value_labels_text` | `단기차입금 4,145,647`, `장기차입금 10,121,033`, `사채 9,490,410`, `공시금액 29,468,632` | `단기차입금 3,833,263`, `장기차입금 9,073,567`, `사채 6,497,790`, `공시금액 22,994,604` |

Important nuance:

- The plain run did retrieve both current and prior-looking chunks near the top
  of the candidate window. Its previews included the current aggregate borrowing
  row with `차입금 (D) 29,468,632` and the prior aggregate borrowing row with
  `차입금 (D) 22,994,604`.
- The failure occurred when numeric extraction bound the numerator operands to
  the prior borrowing table (`period_focus=prior`, `period_labels=["전기"]`) while
  the denominator operands still came from current-period asset rows.
- The deterministic calculator then faithfully computed the wrong operand set.
  This is why the failure is not an arithmetic problem and cannot be fixed by
  the formula layer alone.

Interpretation:

- This trace supports a narrower and stronger claim than "structural retrieval
  is always better." The actual measured advantage is row binding under
  period-ambiguous note tables.
- Structural metadata made the current/prior distinction explicit enough for
  the runtime to preserve the current borrowing rows through final calculation.
- Plain text still contained the relevant numbers, but without reliable
  period-aware row selection it produced a plausible, grounded, and internally
  consistent answer for the wrong period.
