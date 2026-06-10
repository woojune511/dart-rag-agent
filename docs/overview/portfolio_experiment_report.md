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
| Expanded structural ablation | structural avg numeric / faithfulness `1.000 / 1.000` vs plain `0.833 / 0.875`; separating failures are `KBF_T1_017` and `SKH_T3_080` |

Representative KAB answer:

```text
2023년 CIR은 37.47%입니다. 계산: 판매비와관리비 4,355억원 / 경비차감전영업이익 11,623억원.
```

Both operands come from `IV. 이사의 경영진단 및 분석의견::table:3`. The
fanout audit recorded `2` executed queries, `0` duplicate executed queries,
`8` agent LLM calls, and estimated runtime cost `$0.056292`.

### Expanded Structural Ablation

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

This is still a narrow systems ablation, not a broad SOTA claim. The measured
delta supports a specific engineering claim: structural representation and
provenance-aware operand binding reduce numeric failures when relevant values
are present but can be rebound to the wrong row, unit, or table surface.

Reproduction profiles:

- `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`
- `benchmarks/profiles/curated_ablation_expanded_candidate_plain_retrieval.json`

Local result bundles:

- `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
- `benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10/`

Trace summary:

- [../evaluation/structural_trace_diagnostics.md](../evaluation/structural_trace_diagnostics.md)

## Focused Failure Analysis

### `SKH_T1_060`: wrong numerator or subtotal row

Failure: a ratio question could bind a plausible but wrong numerator/subtotal
row, and the cheap baseline missed the representative row.

Fix layer: structured evidence selection, direct row/semantic-label preference,
and dependency projection alignment from producer lookup tasks into downstream
ratio tasks.

Result: the structural path passes this row without adding a company or
benchmark-id branch.

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
