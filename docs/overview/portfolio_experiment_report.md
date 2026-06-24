# Portfolio Experiment Report

This report summarizes the portfolio experiment story. It does not introduce a
new benchmark run; it packages the current repo evidence into a reviewer-facing
case study. Historical `benchmarks/results/**` artifacts are treated as
screening context, not as the current official quality baseline.

## Audience And Claim Boundary

The target reader is familiar with LLM/RAG systems, agent workflows, and
grounding/evaluation vocabulary. The claim is systems-level: a
contract-driven runtime for financial-document RAG that separates semantic
planning from deterministic numeric execution and makes answer acceptance
auditable through traces. It does not claim a new foundation model, new
embedding method, or SOTA TableQA result.

## Problem

Financial-document RAG can look correct while failing in ways that matter for
numeric analysis:

- the retrieved row is from the wrong subtotal, segment, entity, or period
- the final sentence uses a value that is not present in the evidence
- a calculated value is presented as if it were directly stated
- citations survive in prose but disappear from structured runtime state
- stale compatibility fields override the canonical calculation trace

The working problem is therefore not just "retrieve a relevant chunk." The
target is a runtime that exposes the evidence, operands, formula, critic
decision, and review gate that justify an accepted answer.

## Hypothesis

A contract-driven runtime should reduce financial RAG failures better than a
plain retrieval-and-answer pipeline if it:

- preserves document structure during retrieval and chunk preparation
- binds numeric operands to structured rows and source evidence
- executes arithmetic and unit handling deterministically
- publishes `structured_result` and `resolved_calculation_trace`
- records bounded retry/reflection actions as reviewable artifacts
- blocks final close on artifact integrity errors and rejected critic reports
- keeps financial vocabulary in ontology, retrieval policy, config, or data
  rather than runtime control-flow branches

## Method

The project compares retrieval/ingest strategies and layers a runtime contract
over the selected evidence.

| Method | Role | Current interpretation |
| --- | --- | --- |
| `plain_prefix_8000_400` | speed/cost baseline | Cheap, but misses a representative runtime-contract row |
| `contextual_selective_v2_prefix_2500_320` | historical quality baseline | Strong quality reference, but selected chunks need LLM-written context |
| `structural_selective_v2_prefix_2500_320` | current operating default | Keeps gate quality with deterministic structural prefixes and no per-chunk contextualization calls |
| Contract runtime | acceptance layer | Uses task/artifact ledger, critic reports, calculation trace, and final close gates |

The main comparison is not "which prompt sounds better." It is whether the
system can preserve source shape, recover required operands, execute formulas,
and expose the trace that explains acceptance.

## Evaluation Setup

Current gate evidence:

- `curated_runtime_contract_gate`: 5 numeric/runtime canaries
- `curated_concept_runtime_gap_gate`: 7 ontology-driven concept questions
- `curated_policy_driven_runtime_gate`: 5 policy/narrative questions across
  4 company runs
- publication gate: portfolio demo, cache reviewer handoff, runtime domain-term
  audit, and unit/contract tests

Primary metrics:

- quality: pass/fail, faithfulness, completeness, context recall, retrieval
  hit@k, numeric judgement
- grounding: operand grounding, row candidate recovery, citation coverage,
  entity/source coverage
- runtime contract: task/artifact integrity, critic acceptance, trace
  preservation, domain-term audit
- cost: executed retrieval-query count, query-embedding volume, LLM call count,
  and estimated runtime cost

Generic RAG metrics are useful baseline signals, but final acceptance for this
project depends on trace-based numeric grounding: operands, formula, unit
normalization, source references, and rendered displays.

## Results

| Gate / case | Result |
| --- | --- |
| Runtime contract gate | PASS on 5 core numeric/runtime questions |
| Concept runtime gap gate | 7 / 7 PASS |
| Policy-driven runtime gate | latest OpenAI-backed refresh and 2026-06-07 store-fixed replays kept core metrics at `1.000`; task/artifact integrity `ok`; error rate `0.0%` |
| Publication gate | `portfolio_review_gates` reports `Status: ready` |
| Focused CIR close `KAB_T1_066` | numeric `PASS`; faithfulness, completeness, context recall, retrieval hit@k, and grounded rendering correctness all `1.000` |
| Latest expanded structural refresh | structural full-system `9 / 9` numeric PASS after PR #78 operand projection repair |
| Plain retrieval comparison | most recent plain retrieval comparison remains `5 / 9`; use as diagnostic baseline evidence rather than a freshly synchronized final ablation |
| Reproduced structural separators | `POS_T1_057`, `CEL_T1_013`, and `SKH_T3_080` pass structurally while the plain baseline fails |
| Final residual closure | `KBF_T2_018` stale growth projection and `SKH_T1_060` disjoint-source operand overwrite are closed in focused replays and the final full structural replay |

Representative KAB answer:

```text
2023년 CIR은 37.47%입니다. 계산: 판매비와관리비 4,355억원 / 경비차감전영업이익 11,623억원.
```

Both operands come from `IV. 이사의 경영진단 및 분석의견::table:3`. The
fanout audit recorded `2` executed queries, `0` duplicate executed queries,
`8` agent LLM calls, and estimated runtime cost `$0.056292`.

### Current Expanded Structural Refresh

After the operand projection repair in PR #78, the expanded structural
full-system profile was rerun as a store-fixed `eval-only` refresh. This is the
current structural quality claim for portfolio review.

| Metric | Structural full-system |
| --- | ---: |
| Numeric PASS | `9 / 9` |
| Scope | six company runs, nine numeric/mixed questions |
| Refresh mode | store-fixed `eval-only` |
| Final heartbeat | `heartbeat_full9_final_after_kbf_skh_repairs_2026-06-24.jsonl` |

Per-question numeric final judgement:

| Company bundle | Questions |
| --- | --- |
| `kb금융-2023` | `KBF_T2_018: PASS`, `KBF_T1_017: PASS` |
| `posco홀딩스-2023` | `POS_T1_057: PASS` |
| `sk하이닉스-2023` | `SKH_T3_080: PASS`, `SKH_T1_060: PASS` |
| `삼성전자-2023` | `SAM_T3_028: PASS`, `MIX_T1_021: PASS` |
| `셀트리온-2023` | `CEL_T1_013: PASS` |
| `카카오뱅크-2023` | `KAB_T1_066: PASS` |

The most recent plain-retrieval expanded comparison was not rerun after PR #78.
It remains useful as diagnostic baseline evidence:

| Metric | Earlier structural full-system | Plain retrieval |
| --- | ---: | ---: |
| Numeric PASS | `8 / 9` | `5 / 9` |
| Avg numeric pass rate | `0.917` | `0.556` |
| Avg faithfulness | `0.942` | `0.589` |
| Avg completeness | `0.850` | `0.522` |
| Avg context recall | `0.889` | `0.926` |
| Estimated runtime cost | `$0.6334` | `$0.6681` |
| Heartbeat runtime | `42.5m` | `41.5m` |

| Question | Structural | Plain | Diagnostic read |
| --- | --- | --- | --- |
| `KAB_T1_066` | PASS | PASS | CIR positive control remains stable. |
| `POS_T1_057` | PASS | FAIL | Structural keeps the public display/unit path; plain renders a scale-broken interest-coverage answer. |
| `SAM_T3_028` | PASS | PASS | Runtime/operand fixes now carry both variants; this is no longer a current structural-only separator. |
| `MIX_T1_021` | PASS | PASS | Both compute the balance-sheet ratios with partial completeness. |
| `CEL_T1_013` | PASS | FAIL | Structural returns `52.99%`; plain selects a broader denominator and returns `49.74%`. |
| `KBF_T2_018` | PASS | PASS | Mixed numeric+narrative projection now survives. |
| `KBF_T1_017` | PASS | PASS | Both recover the NIM difference. |
| `SKH_T3_080` | PASS | FAIL | Structural preserves foreign-currency gain/loss row binding; plain binds the loss surface incorrectly. |
| `SKH_T1_060` | FAIL | FAIL | Former debt-component numerator residual; closed later by PR #78 projection/provenance repair. |

The result supports a narrow structural-representation claim: it improves
display/unit, denominator, and row-binding behavior on several hard cases. The
later PR #78 structural-only refresh closes the remaining numeric residuals,
but the plain profile has not been rerun under that exact code state.

### Historical Expanded Structural Ablation

The expanded structural slice compares the current structural-selective runtime
against a plain-retrieval counterpart on nine curated questions across six
company runs. Both variants use the same questions, evaluator, retrieval
budgets, and chunk size; the controlled difference is the retrieval
representation: structural selective chunks with deterministic prefixes versus
plain chunks without structural prefixes.

| Metric | Structural full-system | Plain retrieval |
| --- | ---: | ---: |
| Avg numeric pass rate | `1.000` | `0.833` |
| Avg faithfulness | `1.000` | `0.875` |
| Avg completeness | `0.867` | `0.875` |
| Avg context recall | `0.889` | `0.861` |

Separating numeric cases:

| Question | Structural | Plain | Interpretation |
| --- | --- | --- | --- |
| `KBF_T1_017` | PASS | FAIL | Plain surfaced NIM values but failed operand grounding; structural recovered a numeric-passable difference. |
| `SKH_T3_080` | PASS | FAIL | Plain used the wrong gain row and answered `-37,353백만원`; structural answered `-332,236백만원`. |

This historical run remains useful as a diagnostic trace source, especially for
`SKH_T3_080`. It is no longer the active portfolio-facing result because the
latest store-fixed structural refresh supersedes it with structural `9 / 9`
numeric PASS.

### Historical Hard Structural-vs-Plain Replay

After the ontology and runtime-contract fixes, the same five hard numeric
questions were replayed under structural and plain retrieval profiles. This
run is useful because it separates formula/period-contract improvements from
retrieval-representation effects: several hard questions now pass even with
plain retrieval, but one ambiguous note-table case still depends on structural
row metadata.

| Metric | Structural full-system | Plain retrieval |
| --- | ---: | ---: |
| Numeric pass | `5 / 5` | `4 / 5` |
| Avg completeness | `0.938` | `0.812` |
| Avg faithfulness | `1.000` | `0.875` |
| Avg context recall | `0.827` | `0.932` |

Question-level read:

| Question | Structural | Plain | What it shows |
| --- | --- | --- | --- |
| `KAB_T1_066` | PASS, `37.47%` | PASS, `37.47%` | coherent-ratio and direct-support contracts carry both variants |
| `MIX_T1_021` | PASS, `25.36%` / `258.77%` | PASS, same | explicit balance-sheet operands are robust |
| `SAM_T1_026` | PASS, `4.31%` | PASS, `4.31%` | ROE improvement is mainly ontology/period binding |
| `CEL_T1_038` | PASS, `8.36%p` / `29.93%` | PASS, same | late slot alignment can recover aggregate rows even under plain retrieval |
| `SKH_T1_060` | PASS, `42.02%` | FAIL, `34.32%` | structural metadata prevents current/prior borrowing-row confusion |

The `SKH_T1_060` trace is a historical period-binding example. Structural
retrieval bound the borrowing operands to `period_focus=current`,
`period_labels=["당기"]`, `::table:93`:

```text
4,145,647 + 10,121,033 + 9,490,410
```

Plain retrieval bound the numerator to the prior-period table
`period_focus=prior`, `period_labels=["전기"]`, `::table:94`, while keeping the
current-period asset denominator:

```text
3,833,263 + 9,073,567 + 6,497,790
```

The deterministic calculator then correctly computed the wrong operand set.
This is not an arithmetic failure; it is a row/period binding failure that
answer-level faithfulness alone can miss.

Reproduction profiles:

- `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`
- `benchmarks/profiles/curated_ablation_expanded_candidate_plain_retrieval.json`
- `benchmarks/profiles/curated_ablation_structural_hard_full_system.json`
- `benchmarks/profiles/curated_ablation_structural_hard_plain_retrieval.json`

Local result bundles:

- `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
- `benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10/`
- `benchmarks/results/ablation_structural_hard_plain_retrieval_2026-06-11/`

The structural hard replay was summarized from the local eval-only bundle
`benchmarks/results/hard_current_evalonly_2026-06-10/`; that raw bundle was
deleted after documentation under benchmark artifact hygiene.

Trace summary:

- [../evaluation/structural_trace_diagnostics.md](../evaluation/structural_trace_diagnostics.md)

## Focused Failure Analysis

### `KBF_T2_018`: numeric trace preservation in mixed final answer

Failure observed in the latest expanded refresh: growth operands were recovered
during the trace, but final answer composition returned a narrative-only public
answer. The failure was not primarily retrieval; it was numeric trace
preservation into mixed numeric+narrative rendering.

Fix layer: aggregate public-answer projection now promotes the supported
`structured_result.formatted_result` only when it covers the numeric projection
from nested answer slots and has no untraced growth numeric material.

Current status: focused store-fixed `KBF_T2_018` replay passed, and the
follow-up nine-question expanded refresh also passed this case in both
structural and plain variants. The fix is now part of the current ablation
comparison rather than only a focused closure.

### `POS_T1_057`: signed cost-like operand rendered as invalid ratio

Failure: the latest expanded refresh retrieved the relevant support, but the
final answer rendered a signed/displayed interest-cost surface into a negative
ratio (`-791.7%`).

Fix layer: cost-like operand sign/display handling and source-unit preservation
in ratio composition.

Current status: the focused interest-coverage closure now holds in the latest
full structural refresh. `POS_T1_057` is a structural PASS in the refreshed
expanded slice; the latest plain refresh still fails by rendering a
scale-broken public answer despite recovering the internal ratio.

### `SKH_T1_060`: wrong numerator or subtotal row

Failure: a ratio question could bind plausible borrowing rows from the wrong
reporting period. In the hard replay, plain retrieval selected prior-period
borrowing rows while keeping current-period asset rows in the denominator.

Fix layer: period-aware structural metadata, structured evidence selection,
direct row/semantic-label preference, and dependency projection alignment from
producer lookup tasks into downstream ratio tasks.

Current status: closed in PR #78. Historical traces still show a clean
current/prior row-binding separator, and the latest focused/full structural
refresh now returns `42.02%` with the current-period debt and asset operands.
The closing fix is a projection/provenance repair: exact periodless table-label
metadata lookup and disjoint-source task-output protection, not a
company-specific branch.

### `NAV_T2_006`: mixed numeric and narrative growth answer

Failure: the answer needed both growth numbers and supported narrative driver
groups. Earlier paths could preserve numeric faithfulness while losing
completeness or mixing display values from different trace surfaces.

Fix layer: policy-backed retrieval, display preservation, dependency-slot
growth trace alignment, and retrieved-driver evidence preservation.

Result: focused repair recovered faithfulness, completeness, context recall,
and retrieval hit@k to `1.000` in store-fixed evidence.

### `KAB_T1_066`: wrong row, over-blocked lookup, stale display

Failure: CIR could bind the denominator to the wrong financial statement
surface; direct-support validation then over-blocked the correct value because
an operation token appeared inside a metric label; final prose could still use a
stale component display after the trace was fixed.

Fix layer: direct-support validation against prompt-visible context, token
boundary checks for aggregate-operation detection, coherent table/source
operand selection, and trace-first ratio rendering.

Result: final answer uses source-visible operands from one MDA table and passes
all focused numeric/grounding/rendering checks.

## Interpretation

The strongest result is the pattern across gates:

- cheap baselines are useful but can miss financial table structure
- LLM-written contextual ingest is a quality reference, not always the cheapest
  default
- deterministic structural prefixes can preserve the needed document-shape
  signal without per-chunk contextualization calls
- ontology and runtime contracts carry formula and period-binding improvements
  across retrieval variants; structural metadata still matters when similar
  current/prior rows compete inside note tables
- numeric QA needs operand/formula/rendering traces, not only answer-level
  faithfulness
- agentic behavior is useful only when task handoff, retry, critic reports, and
  final close are typed and inspectable
- cost-control work must preserve trace evidence while reducing query fanout

The portfolio claim is narrow: the project improves financial RAG reliability
by moving failure handling into general runtime contracts and reviewed policy
data, not by patching individual benchmark answers.

## Source Evidence

Primary evidence lives in:

- [project_status.md](project_status.md)
- [technical_highlights.md](technical_highlights.md)
- [../evaluation/runtime_contract_gate.md](../evaluation/runtime_contract_gate.md)
- [../evaluation/benchmarking.md](../evaluation/benchmarking.md)
- [../history/experiment_history.md](../history/experiment_history.md)

Artifact hygiene: `benchmarks/results/**` remains local experiment output and
should not be staged unless explicitly requested.
