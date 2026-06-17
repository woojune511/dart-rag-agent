# Ablation Study Design

This document defines the small-start ablation plan for the portfolio
experiment. The goal is to show that the project design choices are not only
reasonable narratives, but measurable controls over concrete financial-RAG
failure modes.

## Scope

Start with a two-question smoke before running broader canaries. The first
smoke uses only reports already present in the local workspace so it can test
the harness without also testing DART auto-fetch.

| Question id | Company | Failure mode under test |
| --- | --- | --- |
| `KAB_T1_066` | 카카오뱅크 | ratio operands, coherent table context, source-visible rendering |
| `SKH_T1_060` | SK하이닉스 | subtotal / numerator / structured row binding |
| `NAV_T2_006` | NAVER | mixed numeric+narrative answer and retrieved-driver preservation; add in phase 2 after confirming report auto-fetch/store availability |

## Variants

| Variant | Profile | Purpose |
| --- | --- | --- |
| Full system | `curated_ablation_smoke_full_system.json` | Current structural-selective runtime baseline |
| Plain retrieval | `curated_ablation_smoke_plain_retrieval.json` | Remove structural-selective ingest and zero-cost prefix signals |

Both variants use the same question ids, company runs, chunk size, retrieval
budget, model routes, evaluator, and output shape. The first smoke intentionally
changes only the ingest/retrieval representation layer.

## Metrics

The smoke should report:

- numeric final judgement
- faithfulness / completeness / context recall / retrieval hit@k
- numeric grounding and calculation correctness when available
- grounded rendering correctness when available
- task/artifact integrity
- executed retrieval queries
- query-embedding calls/input volume
- agent LLM calls/tokens and estimated runtime cost

## Success Criteria

The smoke succeeds if:

- both profiles complete and produce `results.json`
- the full-system variant stays close to current gate behavior
- the plain-retrieval variant produces at least one visible quality drop or
  failure explanation, or else establishes that these three canaries are not
  sufficient to isolate structure effects
- cost/fanout fields are available for comparison

## Scaling Plan

After the smoke:

1. Add `NAV_T2_006` once NAVER report auto-fetch/store availability is
   confirmed.
2. Expand to a 8-12 question ablation canary.
3. Add policy-hint and deterministic-calculation variants.
4. Run the full curated 77 single-document questions for the full-system
   variant.
5. Promote only the most explanatory ablation variants to the full benchmark.

Raw `benchmarks/results/**` artifacts remain local. Commit only compact reports
or docs summaries unless explicitly publishing experiment artifacts.

## Structural-Hard Canary

The next canary keeps `KAB_T1_066` as a positive control and adds cases where
plain chunk retrieval should struggle because the answer depends on row,
period, scope, aggregate, or same-table binding.

Profiles:

- `benchmarks/profiles/curated_ablation_structural_hard_full_system.json`
- `benchmarks/profiles/curated_ablation_structural_hard_plain_retrieval.json`

Question set:

| Question id | Company | Structural pressure |
| --- | --- | --- |
| `KAB_T1_066` | 카카오뱅크 | positive control; single MDA table ratio |
| `MIX_T1_021` | 삼성전자 | two ratios from four balance-sheet rows: liabilities/equity and current assets/current liabilities |
| `SAM_T1_026` | 삼성전자 | ROE with current-period income and average current/prior equity |
| `CEL_T1_038` | 셀트리온 | amortization note row plus operating profit / revenue binding for percentage-point effect |
| `SKH_T1_060` | SK하이닉스 | debt component aggregation plus tangible/intangible asset denominator |

Primary readout:

- final numeric judgement delta
- context recall and context precision delta
- completeness delta
- numeric grounding / retrieval support delta
- calculated value divergence when both variants answer but bind different
  operands

Expected interpretation:

- `KAB_T1_066` should remain a control; if it fails, the run is likely noisy.
- `MIX_T1_021` and `SAM_T1_026` are the cleanest structural metadata tests
  because all required values live in financial-statement tables where
  period/scope and row identity matter.
- `CEL_T1_038` tests cross-section binding between note-level expense detail
  and summary financial metrics.
- `SKH_T1_060` remains a hard diagnostic case rather than a guaranteed pass.

### Full-System Probe: 2026-06-10

Local artifact directory:

- `benchmarks/results/ablation_structural_hard_full_system_2026-06-10`

Only the full-system profile was run. The plain-retrieval counterpart was not
run after this probe because the proposed path failed all structural-hard
questions. Running the baseline at that point would spend additional API budget
without establishing a positive ablation delta.

| Question id | Numeric judgement | Context recall | Context P@5 | Completeness | Numeric grounding | Answer / failure shape |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `KAB_T1_066` | PASS | 1.000 | 0.800 | 1.000 | 1.000 | `37.47%` |
| `MIX_T1_021` | FAIL | 1.000 | 1.000 | 0.300 | 0.000 | answered only current ratio as `90.53%`; debt ratio path bound incorrectly |
| `SAM_T1_026` | FAIL | 0.857 | 1.000 | 0.000 | 0.000 | `178.79%`; current/prior average-equity binding failed |
| `CEL_T1_038` | FAIL | 1.000 | 1.000 | 0.000 | 0.000 | recovered amortization candidates, but did not produce the required percentage-point effect |
| `SKH_T1_060` | FAIL | 1.000 | 1.000 | 0.000 | 0.000 | `42.02%`; debt-component aggregation remains ungrounded |

Interpretation:

- The selected hard cases are useful for residual analysis, but they are too
  hard for a clean structural ablation win in the current runtime.
- `MIX_T1_021` and `SAM_T1_026` show that high retrieval metrics can still
  hide wrong row/period binding. These should be debugged as reconciliation or
  formula-planning gaps before using them as portfolio success cases.
- `CEL_T1_038` demonstrates that reflexion can recover missing evidence, but
  final answer composition/calculation completeness is still weak for
  cross-section percentage-point questions.
- `SKH_T1_060` remains a stable diagnostic for debt-component aggregation, not
  a success-rate ablation candidate.

Next action: build a smaller ablation slice from questions where the current
full-system path already passes and plain retrieval is expected to degrade. Do
not spend on the structural-hard plain profile until at least two hard
questions pass under the full-system profile.

## Closed-Structural Slice

The structural-hard probe above showed that several attractive questions are
too hard for the current proposed path. The next slice therefore starts from
questions with prior focused PASS evidence and only then checks whether plain
retrieval degrades.

Profiles:

- `benchmarks/profiles/curated_ablation_closed_structural_full_system.json`
- `benchmarks/profiles/curated_ablation_closed_structural_plain_retrieval.json`

Question set:

| Question id | Company | Why it belongs in this slice |
| --- | --- | --- |
| `KAB_T1_066` | 카카오뱅크 | source-visible single-table ratio control |
| `POS_T1_057` | POSCO홀딩스 | interest coverage ratio across operating profit and interest expense evidence |
| `SAM_T3_028` | 삼성전자 | inventory valuation row preservation and quantitative impact rendering |
| `CEL_T1_013` | 셀트리온 | R&D capitalization ratio using business-section and note evidence |

Execution rule:

1. Run the full-system profile first.
2. Run the plain-retrieval counterpart only if at least two non-control
   questions still pass under the full-system profile.
3. If the full-system profile regresses, classify the failures as residual
   runtime/debugging work instead of spending on the baseline.

### Full-System Probe: 2026-06-10

Local artifact directory:

- `benchmarks/results/ablation_closed_structural_full_system_2026-06-10`

Trace diagnostic:

- `docs/evaluation/structural_trace_diagnostics.md`

Only the full-system profile was run. The plain-retrieval counterpart was
skipped because the non-control pass count was `0/3`, below the execution rule
threshold. Running a degraded representation baseline would not isolate a
structural effect when the current full-system path already fails the target
questions.

| Question id | Numeric judgement | Context recall | Context P@5 | Completeness | Numeric grounding | Answer / failure shape |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `KAB_T1_066` | PASS | 1.000 | 0.600 | 1.000 | 1.000 | `37.47%`; positive control still works |
| `POS_T1_057` | FAIL | 1.000 | 1.000 | 0.000 | 1.000 | `1.4534배`; high retrieval/grounding, but final formula path used wrong operating-profit binding |
| `SAM_T3_028` | FAIL | 0.667 | 0.600 | 0.000 | 0.000 | `34.9%`; numerator row was recovered, but denominator binding/scale made the impact ratio invalid |
| `CEL_T1_013` | FAIL | 0.667 | 1.000 | 0.000 | 0.000 | `2%`; reflection reached a ratio, but the final operands did not match the benchmark contract |

Interpretation:

- This slice is not suitable as a portfolio ablation result yet. It is useful as
  residual runtime debugging evidence, not as an architecture comparison.
- The main signal is that strong retrieval metrics are insufficient when
  calculation dependencies bind to the wrong row, denominator, or benchmark
  contract. This supports the project narrative, but it should not be presented
  as a measured win until the full-system variant passes the relevant cases.
- Next ablation candidates should be selected from a known-passing gate or
  refreshed after fixing the residual dependency-binding/completeness issues.
  The plain-retrieval profile should remain available but unrun until the
  full-system profile has at least two non-control passes.

### Regression Refresh And Plain Baseline: 2026-06-10

After fixing task-output operand preservation, contextual row-label
specificity, and structured provenance unit realignment, the closed-structural
slice was rerun against both variants.

Local artifact directories:

- `benchmarks/results/ablation_closed_structural_full_system_regression_2026-06-10`
- `benchmarks/results/ablation_closed_structural_plain_retrieval_2026-06-10`

Trace diagnostic:

- `docs/evaluation/structural_trace_diagnostics.md`

| Question id | Full system | Plain retrieval | Separating observation |
| --- | --- | --- | --- |
| `KAB_T1_066` | PASS | PASS | Positive control; both variants solve the simple ratio. |
| `POS_T1_057` | PASS | FAIL | Plain retrieval finds/preserves only one expected value and renders the operating-profit operand with a scale error; full system keeps both expected operands through final calculation. |
| `SAM_T3_028` | PASS | PASS | Both pass final numeric judgement; the full-system trace keeps expected operands visible in final operands, while the plain trace still shows unit/display instability. |
| `CEL_T1_013` | PASS | PASS | Both pass final numeric judgement; the full-system trace preserves source-visible `천원` units, while the plain trace shows display-unit drift. |

Run-level readout:

- full system: `4/4` numeric PASS
- plain retrieval: `3/4` numeric PASS
- main measured delta: `POS_T1_057`

Interpretation:

- This is a narrow but useful ablation result. It does not claim broad
  dominance over plain retrieval.
- The result supports a specific engineering claim: structured provenance and
  dependency-preservation contracts reduce final operand/unit drift when
  evidence is available but can be rebound or rendered at the wrong scale.
- The plain baseline is not a weak baseline. Three questions still pass, so the
  portfolio narrative should emphasize failure-mode isolation rather than a
  large pass-rate gap.

## Expanded Candidate Slice: 2026-06-10

After the narrow four-question slice, the ablation was expanded to the current
candidate set of nine curated questions across six company runs. The goal was
to check whether the structural representation advantage survives beyond the
single `POS_T1_057` separating case.

Profiles:

- `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`
- `benchmarks/profiles/curated_ablation_expanded_candidate_plain_retrieval.json`

Local artifact directories:

- `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10`
- `benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10`

Question set:

| Question id | Company | Role in slice |
| --- | --- | --- |
| `KAB_T1_066` | 카카오뱅크 | positive control; source-visible CIR ratio |
| `POS_T1_057` | POSCO홀딩스 | interest coverage ratio and unit/provenance stress |
| `SAM_T3_028` | 삼성전자 | inventory valuation row plus cost denominator |
| `CEL_T1_013` | 셀트리온 | R&D capitalization ratio and source-unit preservation |
| `KBF_T2_018` | KB금융 | multi-report growth rate plus narrative driver |
| `KBF_T1_017` | KB금융 | multi-report NIM difference and operand grounding |
| `SKH_T3_080` | SK하이닉스 | foreign-currency gain/loss row binding |
| `SKH_T1_060` | SK하이닉스 | debt component aggregation over asset denominator |
| `MIX_T1_021` | 삼성전자 | two balance-sheet ratios from four rows |

Run-level readout:

| Metric | Structural full-system | Plain retrieval |
| --- | ---: | ---: |
| Avg numeric pass rate | `1.000` | `0.833` |
| Avg completeness | `0.867` | `0.875` |
| Avg faithfulness | `1.000` | `0.875` |
| Avg context recall | `0.889` | `0.861` |

Separating observations:

| Question id | Structural | Plain | Observation |
| --- | --- | --- | --- |
| `KBF_T1_017` | PASS | FAIL | The plain run surfaced NIM values but failed operand selection/grounding; the structural run recovered a numeric-passable `0.1%p` difference. |
| `SKH_T3_080` | PASS | FAIL | Plain selected `868,767` and `906,120`, answering `-37,353백만원`; structural selected `573,884백만원` and `906,120백만원`, answering `-332,236백만원`. |

Interpretation:

- The expanded result is stronger than the earlier four-question slice for the
  numeric-grounding claim: structural keeps numeric pass rate at `1.000`, while
  plain falls to `0.833`.
- It is not an across-the-board evaluator victory. `Full Eval Fails` still
  appears for both variants because the runner also flags completeness
  threshold misses. The portfolio claim should therefore focus on operand
  binding, numeric grounding, and faithfulness.
- `SKH_T3_080` is the clearest case-study trace because both variants retrieve
  plausible values, but only the structural path binds the right
  foreign-currency translation gain row.

## Smoke Run: 2026-06-10

Local artifact directories:

- `benchmarks/results/ablation_smoke_full_system_2026-06-10`
- `benchmarks/results/ablation_smoke_plain_retrieval_2026-06-10`

These raw result bundles are local experiment artifacts and are not intended for
commit.

| Variant | Question id | Numeric judgement | Context recall | Context P@5 | Completeness | Numeric grounding | Answer |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| Full system | `KAB_T1_066` | PASS | 1.000 | 0.800 | 1.000 | 1.000 | 37.47% |
| Plain retrieval | `KAB_T1_066` | PASS | 1.000 | 0.400 | 1.000 | 1.000 | 37.47% |
| Full system | `SKH_T1_060` | FAIL | 1.000 | 1.000 | 0.300 | 0.000 | 42.02% |
| Plain retrieval | `SKH_T1_060` | FAIL | 0.600 | 1.000 | 0.000 | 0.000 | 36.17% |

Run-level notes:

- Both variants completed and produced `results.json`.
- `KAB_T1_066` is too easy to separate final-answer accuracy: both variants
  pass. It still shows a retrieval precision difference (`Context P@5`: 0.800
  vs 0.400).
- `SKH_T1_060` is a useful diagnostic canary rather than a clean win: both
  variants fail numeric final judgement, but the full system preserves higher
  context recall/completeness and produces a different calculation trace.
  The plain run logs show weaker direct operand support and unit instability
  around debt components.
- Heartbeat elapsed time was about 8.5 minutes for full-system and about 6.7
  minutes for plain-retrieval on this fresh-store smoke. Ingest
  contextualization cost was recorded as `0.0` for both profiles; API cost is
  primarily from embeddings plus agent/evaluator LLM calls.

Interpretation: this smoke validates that the ablation harness works and that
the representation layer can be compared without changing the evaluator or
question set. It is not yet strong enough to claim a broad success-rate lift.
The next canary should add more questions where structure, unit normalization,
and operand binding are known to be independently observable.

### Store-Fixed Refresh: 2026-06-17

After the PR 4 simplification sequence, the same two-question smoke was
refreshed with `--eval-only` against existing local stores. This checked that
the harness and result shape still reproduce before spending on a broader
benchmark refresh.

Heartbeat logs:

- `benchmarks/results/ablation_smoke_full_system_2026-06-10/_logs/heartbeat_evalonly_current_2026-06-17.jsonl`
- `benchmarks/results/ablation_smoke_plain_retrieval_2026-06-10/_logs/heartbeat_evalonly_current_2026-06-17.jsonl`

| Variant | Question id | Numeric judgement | Context recall | Context P@5 | Completeness | Faithfulness | Numeric grounding | Cost | Latency |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Full system | `KAB_T1_066` | PASS | 1.000 | 0.800 | 1.000 | 1.000 | 1.000 | `$0.0483` | `60.9s` |
| Plain retrieval | `KAB_T1_066` | PASS | 1.000 | 0.400 | 1.000 | 1.000 | 1.000 | `$0.0459` | `56.8s` |
| Full system | `SKH_T1_060` | FAIL | 1.000 | 1.000 | 0.000 | 0.000 | 0.000 | `$0.0807` | `160.9s` |
| Plain retrieval | `SKH_T1_060` | FAIL | 0.800 | 1.000 | 0.000 | 0.300 | 0.000 | `$0.1054` | `216.6s` |

Refresh interpretation:

- The smoke remains a harness sanity check. It should not be promoted to the
  main portfolio ablation result because both variants have the same final
  numeric pass rate (`1/2`).
- `KAB_T1_066` still works as an easy positive control. The structural variant
  keeps better top-5 evidence precision, but final accuracy does not separate.
- `SKH_T1_060` is still a hard diagnostic for debt-component aggregation and
  asset-denominator binding. Structural retrieval preserves stronger evidence
  coverage, but the final answer remains wrong under both variants.
- Raw result bundles remain local experiment artifacts.

## Expanded Candidate Slice

The next expansion step uses locally available reports and questions that have
prior full-system pass evidence from the closed structural, concept-runtime, or
runtime-contract gates.

Profiles:

- `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`
- `benchmarks/profiles/curated_ablation_expanded_candidate_plain_retrieval.json`

Question set:

| Question id | Company | Prior evidence | Structural pressure |
| --- | --- | --- | --- |
| `KAB_T1_066` | 카카오뱅크 | closed structural PASS | source-visible ratio from one profitability table |
| `POS_T1_057` | POSCO홀딩스 | closed structural PASS | operating profit / interest expense provenance and unit preservation |
| `SAM_T3_028` | 삼성전자 | closed structural PASS | inventory valuation row preservation and source-visible display stability |
| `CEL_T1_013` | 셀트리온 | closed structural PASS | R&D capitalization ratio across business and note evidence |
| `KBF_T2_018` | KB금융 | concept-runtime gate PASS | current/prior comparison plus narrative cause evidence |
| `SKH_T3_080` | SK하이닉스 | concept-runtime gate PASS | gain/loss sign handling and same-note operand pairing |
| `KBF_T1_017` | KB금융 | runtime-contract gate PASS | current/prior percentage-point change from ratio table |
| `SKH_T1_060` | SK하이닉스 | runtime-contract gate PASS | multi-operand debt aggregation plus asset denominator |
| `MIX_T1_021` | 삼성전자 | runtime-contract gate PASS | two balance-sheet ratios from four row/period-bound values |

Execution rule:

1. Run the full-system profile first.
2. Run the plain-retrieval counterpart only if the full-system profile keeps at
   least `7/9` numeric PASS and does not show a systemic integrity regression.
3. Use monitored runs:

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json `
  --output-dir benchmarks/results/ablation_expanded_candidate_full_system_YYYY-MM-DD `
  --progress-heartbeat-sec 60 `
  --heartbeat-log benchmarks/results/ablation_expanded_candidate_full_system_YYYY-MM-DD/heartbeat.jsonl
```

4. Record pass rate, failed question ids, failure taxonomy, latency, retrieval
   query count, LLM call count, token use, and estimated runtime cost.
5. Keep raw result bundles local unless explicitly publishing experiment
   artifacts.

Interpretation rule:

- This slice is a candidate expansion, not a portfolio result yet.
- If full-system quality drops, classify residual failure modes before spending
  on the plain baseline.
- If both variants pass most questions, focus the write-up on trace quality,
  unit/display stability, and failure taxonomy rather than pass-rate delta.

### Expanded Store-Fixed Ablation Refresh: 2026-06-17

After the aggregate public-answer projection fix, the expanded candidate
full-system profile was refreshed with `--eval-only` against the existing local
stores. It cleared the `7 / 9` execution rule, so the plain-retrieval
counterpart was rerun for a current ablation comparison.

Local artifact directories:

- `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10`
- `benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10`

Heartbeat logs:

- `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/heartbeat_evalonly_after_kbf_projection_fix_2026-06-17.jsonl`
- `benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10/heartbeat_evalonly_after_fullsystem_7of9_2026-06-17.jsonl`

Run-level readout:

| Metric | Structural full-system | Plain retrieval |
| --- | ---: | ---: |
| Numeric PASS | `7/9` | `4/9` |
| Avg numeric pass rate | `0.778` | `0.444` |
| Avg completeness | `0.578` | `0.389` |
| Avg faithfulness | `0.833` | `0.678` |
| Avg context recall | `0.867` | `0.904` |
| Avg Context P@5 | `0.867` | `0.778` |
| Estimated runtime cost | `$0.6156` | `$0.8348` |
| LLM calls / tokens | `133` / `732,650` | `120` / `687,109` |
| Query embedding calls | `54` | `62` |
| Heartbeat wall-clock runtime | `28.5m` | `32.1m` |

Question-level readout:

| Question id | Structural | Plain | Diagnostic read |
| --- | --- | --- | --- |
| `KAB_T1_066` | PASS | PASS | CIR control passes in both variants; plain has lower Context P@5. |
| `POS_T1_057` | FAIL | FAIL | Both variants still expose interest-cost sign/display and unit binding instability. |
| `SAM_T3_028` | PASS | FAIL | Structural preserves the cost-of-sales denominator and returns `2.79%`; plain drifts to a scale-broken `2792.63%`. |
| `MIX_T1_021` | PASS | PASS | Both compute the balance-sheet ratios, with partial completeness. |
| `CEL_T1_013` | PASS | FAIL | Structural binds the R&D denominator and returns `52.99%`; plain selects a broader denominator and returns `49.74%`. |
| `KBF_T2_018` | PASS | PASS | Both pass after aggregate public-answer projection, but the plain trace shows noisier unit/value surfaces. |
| `KBF_T1_017` | PASS | PASS | Both recover the NIM difference as `0.1%`. |
| `SKH_T3_080` | PASS | FAIL | Structural preserves the foreign-currency gain/loss row binding and returns `-3,322억원`; plain binds the loss surface incorrectly. |
| `SKH_T1_060` | FAIL | FAIL | Debt-component numerator/asset denominator aggregation remains the hard residual. |

Interpretation:

- The full-system variant cleared the documented `7/9` threshold, so the
  plain-retrieval counterpart was rerun and now provides a current ablation
  comparison.
- Structural representation separates on `SAM_T3_028`, `CEL_T1_013`, and
  `SKH_T3_080`. In each case, plain retrieval still reaches nearby evidence but
  loses scale, denominator, or row-binding semantics.
- `POS_T1_057` and `SKH_T1_060` remain shared residuals. They are useful
  follow-up cases, not proof that the structural layer should be removed.

Next action before full benchmark expansion:

1. Debug `POS_T1_057` as sign/display handling for cost-like operands in ratio
   composition.
2. Keep `SKH_T1_060` as the debt-component aggregation diagnostic.
3. Use this expanded comparison as the current portfolio ablation result while
   keeping raw `benchmarks/results/**` artifacts local.
