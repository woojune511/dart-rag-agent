# Portfolio Experiment Report

This report packages the experiment story behind the portfolio version of the
project. It does not introduce a new benchmark run. Instead, it summarizes
existing repo evidence and the current publication gate into one reviewer-facing
case study. Store-fixed policy-gate refreshes from 2026-06-06 and 2026-06-07
are reported separately from older screening evidence, and provider-specific
local artifacts are not treated as the current official quality baseline.

## Problem

Financial-document RAG can look correct while failing in ways that matter for
numeric analysis:

- the retrieved row is from the wrong subtotal, segment, entity, or period
- the final sentence uses a value that is not present in the evidence
- a calculated value is presented as if it were directly stated
- citations survive in prose but disappear from structured runtime state
- stale compatibility fields override the canonical calculation trace

The working problem was therefore not only "retrieve a relevant chunk." The
target was a runtime that can answer a filing question and expose the evidence,
calculation trace, critic decision, and review gate that justify the answer.

## Hypothesis

A contract-driven runtime should reduce financial RAG failures better than a
plain retrieval-and-answer pipeline if it:

- preserves document structure during retrieval and chunk preparation
- binds numeric operands to structured rows and source evidence
- executes arithmetic deterministically
- publishes `structured_result` and `resolved_calculation_trace`
- blocks final close on task/artifact integrity errors and rejected critic
  reports
- keeps domain vocabulary in ontology, retrieval policy, config, or data rather
  than runtime control-flow branches

The expected tradeoff was that structural retrieval signals could keep most of
the quality of contextual ingest while avoiding per-chunk LLM contextualization
cost.

## Method

The project compared three retrieval/ingest approaches and the current
contract-driven runtime layer:

| Method | Role | Structure signal | Extra ingest LLM calls | Current interpretation |
| --- | --- | --- | ---: | --- |
| `plain_prefix_8000_400` | Speed/cost baseline | zero-cost prefix only | 0 | Cheap, but misses a representative runtime contract row |
| `contextual_selective_v2_prefix_2500_320` | Historical quality baseline | selected chunks plus LLM-written context | selected chunk count | Strong quality reference, but higher ingest cost |
| `structural_selective_v2_prefix_2500_320` | Current operating default | selected chunks plus deterministic structural prefix | 0 | Keeps gate quality while avoiding contextualization calls |
| Current contract runtime | Acceptance layer | task/artifact ledger, critic reports, calculation trace | n/a | Makes answer acceptance inspectable |

Important boundary: historical ingest/cost results are used as screening
evidence only. They are not mixed into the current official gate as if they came
from the same run.

## Experiment Setup

The evidence is split into current gate evidence and historical screening
evidence.

Current gate evidence:

- `curated_runtime_contract_gate`: 5 numeric/runtime canaries
- `curated_concept_runtime_gap_gate`: 7 ontology-driven concept questions
- `curated_policy_driven_runtime_gate`: 5 policy/narrative questions across
  4 company runs
- publication gate: portfolio demo, cache reviewer handoff, runtime domain-term
  audit, and full unit-test discovery

Historical screening evidence:

- ingest and retrieval comparisons in `docs/evaluation/benchmarking.md`
- structural/default notes in `docs/overview/technical_highlights.md`
- older local `benchmarks/results/**` bundles used only for cost/time context

Primary metrics:

- quality: pass/fail, faithfulness, completeness, context recall, retrieval
  hit@k, numeric judgement
- grounding: operand grounding, row candidate recovery, citation coverage,
  entity coverage
- cost/runtime: ingest LLM call count, estimated ingest cost, ingest time
  reduction when available, executed retrieval-query count, query-embedding
  calls/input volume, LLM call count, and estimated runtime cost
- contract health: task/artifact integrity, critic acceptance, trace
  preservation, domain-term audit

## Quantitative Comparison

### Gate Summary

| Gate | Scope | Result | Evidence source |
| --- | --- | --- | --- |
| Runtime contract gate | 5 core numeric/runtime questions | PASS | `docs/overview/project_status.md` |
| Concept runtime gap gate | 7 ontology-driven concept questions | 7 / 7 PASS | `docs/overview/project_status.md` |
| Policy-driven runtime gate | 4 company runs, 5 policy/narrative questions | 4 / 4 company runs passed in the latest OpenAI-backed refresh; later 2026-06-07 store-fixed replays kept all five rows at faithfulness, completeness, context recall, and retrieval hit@k `1.000`, task/artifact integrity `ok` for 5 / 5 rows, error rate `0.0%`, and `LGE_T1_051` numeric judgement `PASS` | `docs/overview/project_status.md`, `docs/evaluation/benchmarking.md` |
| Publication gate | current portfolio-ready main | `portfolio_demo` ready; cache reviewer `status = ok`; domain-term audit passed; latest local validation passed 887 unit tests | current local publication gate |

### Method Comparison

| Method | Quality signal | Cost/runtime signal | Decision |
| --- | --- | --- | --- |
| `plain_prefix_8000_400` | Fails the representative `SKH_T1_060` runtime-contract row | no contextualization calls | Keep as speed/cost baseline, not default |
| `contextual_selective_v2_prefix_2500_320` | Runtime contract and multi-entity gates pass as historical quality reference | selected chunks require LLM-written context | Keep as quality reference |
| `structural_selective_v2_prefix_2500_320` | Runtime contract and multi-entity gates pass | deterministic structural prefix, no per-chunk contextualization calls | Use as current operating default |
| Current contract runtime | Concept gate 7 / 7; latest OpenAI-backed policy gate has faithfulness, completeness, context recall, and retrieval hit@k all `1.000`; 2026-06-07 store-fixed replays preserved those quality signals; PR #33 recovered the `NAV_T2_006` retrieved-driver wording gap in a focused repair; publication gate clean | store-fixed refresh reused existing stores instead of fresh ingest; later cost-control replays reduced observed query pressure without a quality drop | Use as the reviewer-facing runtime story |

### Runtime Cost-Control Follow-Up

The 2026-06-07 replays below are local, store-fixed runtime evidence. They are
not fresh ingest benchmarks and they are not presented as isolated causal
proof for a single optimization. They are useful because they show that the
current quality gate stayed healthy while executed-query pressure and runtime
cost signals were brought under tighter control.

| Follow-up | Scope | Quality guard | Runtime/cost signal | Interpretation |
| --- | --- | --- | --- | --- |
| Retrieval hint and section-enrichment budget | focused `NAV_T2_006` / `LGE_T1_051` canary, then five-row policy-gate replay | focused canary core metrics `1.000`; full replay core metrics `1.000`, task/artifact integrity `ok` for 5 / 5 rows, error rate `0.0%`, `LGE_T1_051` numeric `PASS` | NAV query-embedding chars `7,672 -> 2,662`, tokens `1,935 -> 676`; LGE chars `6,120 -> 4,056`, tokens `1,539 -> 1,019`; full replay snapshot: 97 executed retrieval queries, 100 query-embedding calls, 13,948 query-embedding chars, 3,522 estimated query-embedding tokens, 58 LLM calls, runtime cost `$0.444073` | Shorten executed query enrichment while preserving full policy trace, reranker signals, and supplemental evidence signals |
| Exact-text query embedding cache | five-row policy-gate replay after PR #23 | all five rows kept faithfulness, completeness, context recall, and retrieval hit@k `1.000`; task/artifact integrity `ok` for 5 / 5 rows; error rate `0.0%`; `LGE_T1_051` numeric `PASS` | observed post-cache snapshot: 88 executed retrieval queries, 89 query-embedding calls, 12,722 query-embedding chars, 3,211 estimated query-embedding tokens, 40 LLM calls, runtime cost `$0.407527` | Safe provider-call cache; treat the measured reduction as a post-cache replay result, not cache-only attribution, because live query fan-out and LLM calls also changed |
| Same-trace duplicate guard validation | focused `HYU_T2_010` / `NAV_T2_006` replay after duplicate-query audit | both rows kept faithfulness, completeness, context recall, and retrieval hit@k `1.000`; error rate `0.0%` | HYU replay: 16 executed / 16 unique / 0 duplicate signatures versus historical audit baseline 28 / 15 / 13; NAV replay: 28 / 24 / 4, exposing remaining cross-trace repeats | Confirms the narrow guard did not regress the highest duplicate-pressure rows; remaining cost work should target sibling-task reuse, not broader hidden dedupe |
| Retrieved-driver evidence preservation | focused `NAV_T2_006` repair after cross-trace diagnostic instrumentation | faithfulness, completeness, context recall, and retrieval hit@k recovered to `1.000`; error rate `0.0%` | no new fresh ingest; reused retrieved docs and policy-backed driver groups from the existing store-fixed path | Closed a narrative wording gap by preserving source-visible retrieved evidence, not by adding a benchmark-specific runtime branch |

### Historical Screening Evidence

The following cost/time numbers are historical screening evidence. They are
useful for explaining the cost tradeoff, but they are not treated as current
official quality scores.

| Historical artifact | Comparison | Observed cost/runtime signal |
| --- | --- | --- |
| `benchmarks/results/dev_fast_cache_check_2026-04-17` | contextual parent-only vs contextual-all | about 88.5% estimated ingest-cost reduction and 91.6% ingest-time reduction on the Samsung 2024 screening bundle |
| `benchmarks/results/dev_fast_cache_check_2026-04-17` | contextual selective-v2 vs contextual-all | about 63.1% estimated ingest-cost reduction and 74.2% ingest-time reduction on the Samsung 2024 screening bundle |
| `benchmarks/results/v4_generalization_fix_2026-04-17` | contextual parent-only vs contextual-all | about 86.8% average estimated ingest-cost reduction across three company screening runs |
| `benchmarks/results/v4_generalization_fix_2026-04-17` | contextual selective-v2 vs contextual-all | about 60.6% average estimated ingest-cost reduction across three company screening runs |

These older runs helped motivate selective and structural ingest work. The
current portfolio claim is narrower: the routine default is structural-selective
because the current gate documentation treats it as preserving quality while
removing per-chunk contextualization calls.

### Focused Improvement Examples

| Improvement | Before | After | Interpretation |
| --- | ---: | ---: | --- |
| Ontology-guided retrieval operand grounding | 0.50 | 1.00 | Retrieval policy recovered source rows that semantic search missed |
| Calculation success rate | 0.33 | 1.00 | Better operand recovery enabled deterministic formula execution |
| Row candidate recovery rate | 0.00 | 0.67 | Structured/domain retrieval signals restored candidate rows |
| Concept runtime gap gate | residual failures | 7 / 7 PASS | Concept lookup/composition issues closed without runtime keyword branches |
| Policy-driven runtime gate | mixed-query regressions | latest OpenAI-backed refresh: faithfulness, completeness, context recall, and retrieval hit@k all `1.000`; focused `HYU_T2_010` follow-up and PR #33 `NAV_T2_006` repair both keep core metrics at `1.000` | Policy-backed retrieval, display preservation, task/artifact provenance, and retrieved-driver evidence preservation closed the representative mixed-query failures |
| Retrieval hint budget canary | NAV query-embedding chars `7,672`, LGE chars `6,120` | NAV chars `2,662`, LGE chars `4,056` with both focused rows at core metrics `1.000` | Reduced executed-query inflation without hiding policy/reranker evidence signals |
| Query embedding cache replay | 97 executed queries, 100 query-embedding calls, 58 LLM calls, runtime cost `$0.444073` | 88 executed queries, 89 query-embedding calls, 40 LLM calls, runtime cost `$0.407527` | Post-cache replay improved observed runtime pressure while preserving the five-row policy gate |

## Failure Analysis

### `SKH_T1_060`: wrong numerator or subtotal row

Failure mode:

- A ratio question could bind a plausible but wrong numerator/subtotal row.
- A plain speed/cost baseline missed this representative runtime-contract row.

Fix layer:

- structured evidence selection
- direct row-label and semantic-label preference
- dependency projection alignment from producer lookup tasks into downstream
  ratio tasks

Result:

- The structural path passes this row with the expected ratio answer.
- The fix is generic evidence and dependency binding, not a company or
  benchmark-id branch.

### `NAV_T2_006`: mixed numeric and narrative growth answer

Failure mode:

- The answer needed both growth numbers and supported narrative driver groups.
- Earlier paths could preserve numeric faithfulness while losing completeness
  or mixing display values from different trace surfaces.

Fix layer:

- policy-backed retrieval for supported driver groups
- answer-slot and display preservation
- dependency-slot growth trace alignment to producer lookup values
- guardrails against untraced numeric displays in mixed answers
- retrieved-driver evidence preservation when a policy-backed driver group is
  visible in retrieved docs but absent from aggregate evidence

Result:

- The latest OpenAI-backed policy gate reports faithfulness, completeness,
  context recall, and retrieval hit@k of `1.000` for this row.
- A historical Google-backed local artifact still recorded completeness `0.700`
  because of narrative wording gaps, so that artifact is kept as screening
  context rather than merged into the current official quality claim.
- The final answer preserves the producer lookup values and growth display in
  the canonical trace.
- A later focused repair after cross-trace diagnostic instrumentation recovered
  the retrieved driver wording gap to faithfulness, completeness, context
  recall, and retrieval hit@k `1.000`. This remains local store-fixed repair
  evidence, not a fresh official benchmark result.

### `KBF_T2_018` and `SAM_T3_028`: concept lookup and composition residuals

Failure mode:

- Some concept-level questions were not pure single-value lookups.
- The runtime needed to split concept work, preserve source-visible displays,
  and compose only evidence-visible numeric claims.

Fix layer:

- multi-concept lookup task splitting
- sibling table evidence recovery
- lookup-list rendering constrained to lookup aggregates
- source-visible value display preservation
- evidence-visible quantitative-impact composition

Result:

- The concept runtime gap gate closed at 7 / 7 PASS.
- The closure explicitly avoided company/question-specific runtime keyword
  branches.

## Interpretation

The strongest result is not a single aggregate score. It is the pattern across
the gates:

- cheap baselines are useful for speed but can miss financial table structure
- contextual ingest is a strong quality reference but costs more at ingest time
- structural-selective ingest keeps the important document-shape signals while
  avoiding per-chunk contextualization calls
- the contract runtime makes answer acceptance auditable through evidence,
  calculation trace, critic acceptance, and task/artifact integrity
- cost-control work now has two layers: shorter executed-query enrichment and
  exact-text query-embedding reuse
- mixed numeric+narrative answers need a separate evidence-preservation layer
  so relevant retrieved driver sentences do not disappear during aggregate
  composition
- the remaining runtime-cost bottleneck is unique query fan-out and LLM planning
  variability, not per-chunk contextualization

This supports the portfolio claim: the project improved financial RAG quality
by moving failure handling into general runtime contracts and reviewed policy
data, not by patching individual benchmark answers.

## Source Evidence

Primary repo evidence used for this report:

- `docs/overview/project_status.md`
- `docs/overview/technical_highlights.md`
- `docs/evaluation/benchmarking.md`
- `docs/evaluation/runtime_contract_gate.md`
- `docs/evaluation/multi_entity_grounding_gate.md`
- `docs/evaluation/structural_parent_hybrid_v2_probe.md`
- historical local summaries under `benchmarks/results/**`

Artifact hygiene note: `benchmarks/results/**` remains local experiment output
and should not be staged for this portfolio report.
