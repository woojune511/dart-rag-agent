# Project Status

Last updated: 2026-06-02

## Positioning

This repository is a DART financial-document RAG and agent-runtime project. The
core engineering goal is not to hard-code benchmark answers, but to build a
traceable runtime contract for financial analysis:

- retrieve evidence from long-form DART filings
- bind the right structured rows and source sentences
- execute numeric operations deterministically
- preserve calculation and evidence traces
- validate changes through reproducible benchmark gates

The current direction is to turn the verified single-agent runtime into a
role-separated multi-agent system using a task ledger and artifact store.

## Current Gate Status

| Gate | Scope | Latest Status |
| --- | --- | --- |
| Runtime contract gate | 5 core numeric/runtime questions | PASS |
| Concept runtime gap gate | 7 ontology-driven concept questions | PASS |
| Policy-driven runtime gate | 4 company runs, 5 policy/narrative questions | PASS |

### Runtime Contract Gate

- Profile: `benchmarks/profiles/curated_runtime_contract_gate.json`
- Candidate: `structural_selective_v2_prefix_2500_320`
- Current interpretation: default short smoke gate is stable.
- Latest focused repair:
  - `SKH_T1_060` now passes the fresh low-API structural path with answer
    `42.02%`.
  - The fix is generic structured evidence selection: direct row-label /
    semantic-label evidence is preferred when projecting lookup task outputs
    into downstream ratio dependencies.
  - Producer lookup subtask result views are also aligned with that dependency
    projection, so serialized intermediate displays preserve the same direct
    structured value used by the final ratio.
  - No company name, benchmark ID, or metric-specific runtime branch was added.

### Concept Runtime Gap Gate

- Profile: `benchmarks/profiles/curated_concept_runtime_gap_gate.json`
- Latest representative local output:
  `benchmarks/results/concept_runtime_gap_gate_refresh_2026-06-02_042728/`
- Result:
  - 7 / 7 questions passed
  - `numeric_final_judgement = PASS` for all seven questions
  - aggregate numeric pass, completeness, and faithfulness are all `1.000`
- Main closure:
  - multi-concept lookup tasks now split into independent task-ledger entries
  - sibling table evidence can recover missing lookup slots generically
  - lookup-list rendering is constrained to lookup-only aggregates

### Policy-Driven Runtime Gate

- Profile: `benchmarks/profiles/curated_policy_driven_runtime_gate.json`
- Source/output store bundle:
  `benchmarks/results/policy_gate_regression_2026-05-31_2212/`
- Latest store-fixed refresh result:
  - 4 / 4 company runs passed
  - 0 full-eval failures
  - 0 critical misses
  - average faithfulness, completeness, and context recall are all `1.000`
- Note:
  - `numeric_final_judgement = null` is not a failure for narrative or mixed
    questions when the other evaluator signals are healthy.
- Latest focused repair:
  - `NAV_T2_006` regressed after low-API/offline fallback removal because the
    growth calculation paired same-concept operands with incompatible display
    units (`백만원` versus `천원`), producing `141295.74%`.
  - The fix is a generic growth operand unit-binding contract: when current and
    prior operands are the same concept, raw numeric scale is plausible, and
    normalized scale is distorted by at least 100x, the prior operand is
    re-normalized to the current display unit.
  - Repeated row-label table evidence also now supports role-aware current/prior
    value selection.
  - Focused eval-only canary now returns `41.4%`, with faithfulness `1.000`,
    context recall `1.000`, context P@5 `0.800`, completeness `0.700`, and
    error rate `0.0%`.
- Latest mixed-query closure:
  - `HYU_T2_010` now preserves the source-stated growth display when the DART
    sentence already says `87.0만 대`, `78.1만 대 대비 11.5%`.
  - The deterministic formula trace is still retained, but the final rendered
    answer and `answer_slots.primary_value.rendered_value` use the
    evidence-visible `11.5%` instead of drifting to a recomputed rounding.
  - Focused eval-only canary: faithfulness `1.000`, completeness `1.000`,
    context recall `1.000`, retrieval hit `1.000`, avg score `0.958`, error
    rate `0.0%`.
  - Validation: runtime domain-term audit passed, and
    `python -m unittest discover -s tests` passed with `604` tests.

## Operating Principles

- Domain vocabulary belongs in ontology, retrieval policy, config, or reviewed
  data artifacts, not runtime control-flow code.
- Runtime code should implement generic mechanisms: evidence preservation,
  structured row/header matching, dependency binding, dedupe, ordering,
  validation, and display preservation.
- Benchmark regressions are classified by layer before implementation:
  ontology, retrieval policy, parser structure, planner contract, evidence
  schema, runtime execution, or evaluator definition.
- Store-fixed `--eval-only` refreshes come before fresh ingest unless parser,
  ingest, or cache signatures changed.
- Experiment result directories are local artifacts and are not committed.

## Portfolio Framing

The strongest portfolio story is:

> I built a financial-document RAG runtime that treats numbers as structured
> evidence-bound artifacts rather than free-form LLM text. The system separates
> semantic planning from deterministic execution, stores explicit calculation
> traces, and uses focused benchmark gates to prevent benchmark-specific
> patches from entering runtime code.

Useful supporting points:

- The project handles noisy DART filings with section/table-aware parsing and
  hybrid retrieval.
- Numeric questions use formula planning and safe deterministic execution.
- Evaluation is split into faithfulness, completeness, numeric equivalence,
  numeric grounding, and retrieval support.
- The runtime now has gate-backed concept and policy-driven paths without
  adding company/question-specific branches to agent code.

## Next Work

1. Reduce benchmark runtime and embedding cost through profiling, cache
   hygiene, and explicit retrieval query-budget controls for focused canaries.
2. Harden task-ledger and artifact-store contracts for the multi-agent workflow.
3. Clean up legacy projection paths now that `answer_slots` and
   `resolved_calculation_trace` are the durable runtime surfaces.
4. Add a small portfolio demo script that runs a representative query and emits
   answer, evidence, and calculation trace side by side.

### Runtime/API Cost Focus

- First low-risk control: benchmark runs can now pass explicit retrieval query
  budgets to cap primary, operand-focused, and retry retrieval fan-out.
- Official runtime contract and policy-driven gate profiles now set `8 / 4 / 1`
  in `full_evaluation`, so focused gate runs record the budget in their
  profile/config instead of relying on ad hoc CLI flags.
- `retrieval_debug_trace.query_budget.source` now records the active retrieval
  source and source-level query counts. This matters because final traces can
  describe only the last active subtask while the state-level semantic plan may
  still contain many generated query surfaces.
- Cost estimation now consumes normalized Gemini response usage metadata for
  benchmark contextualization, agent runtime, and evaluator judge calls:
  - prompt/input tokens
  - output/candidate tokens
  - thinking tokens
  - cached-content tokens
  - tool-use prompt tokens
- `estimated_ingest_cost_usd` and `estimated_runtime_cost_usd` remain
  estimates from usage metadata and the profile pricing table, not Cloud
  Billing invoice amounts.
- Full-eval results preserve per-question `agent_llm_usage`,
  `judge_llm_usage`, combined `llm_usage`, and aggregate `llm_*` token totals
  so runtime/evaluator cost can be compared against ingest cost.
- Embedding APIs do not return usage metadata through the LangChain embedding
  interface, so the project records embedding input volume instead:
  API calls, input text count, input characters, and local estimated input
  tokens. `estimated_*_embedding_cost_usd` is populated only when a profile
  provides `embedding_input_per_million_tokens_usd`.
- Default runtime behavior remains unchanged unless a budget is supplied. Query
  dedupe is enabled only for explicitly budgeted retrieval stages.
- Use this for focused triage before changing retrieval policy or ontology:
  it is an execution-cost control, not a benchmark-answer rule.
- Benchmark runner now supports focused LLM route probes without editing the
  profile via `--llm-route phase=provider:model`.
- Local `HYU_T2_010` evidence-extraction probe with
  `--llm-route evidence_extraction=google:gemini-2.5-flash` did not preserve
  the gate contract: faithfulness and completeness fell to `0.500`, and the
  rendered growth calculation drifted to `12.3%`. Keep
  `evidence_extraction = gemini-2.5-pro` for the official gate until a broader
  low-cost route canary proves otherwise.
- First bounded low-API canary:
  - `NAV_T1_030` with budgets `12 / 6 / 2` passed.
  - `retrieval_debug_trace.query_budget` recorded `primary 3/3`,
    `operand_focus 6/16`, and `retry 0/0`.
  - API calls and estimated cost remained `0 / $0.0000`.
- Second bounded low-API canary:
  - `SKH_T1_060` passed with tighter budgets `8 / 4 / 1`.
  - The trace reduced executed retrieval searches to 12
    (`primary = 8`, `operand_focus = 4`, `retry = 0`) while preserving
    `numeric_final_judgement = PASS`.
  - `KBF_T1_017` also passed numerically with `8 / 4 / 1` and 12 executed
    retrieval searches.
  - `NAV_T1_071` was confirmed to be a separate runtime regression rather than
    a budget-only regression: `8 / 4 / 1`, `12 / 6 / 2`, and unbounded focused
    low-API runs all failed with the same stale `0원` difference shape before
    the runtime fix.
  - The `NAV_T1_071` root cause was period-insensitive precision refinement:
    a prior-period lookup initially selected the correct fiscal column, then
    contextual table-cell refinement overwrote it with the current-period cell.
  - The fix makes precision refinement reuse the generic period-aware structured
    cell selector; the focused low-API canary now passes with current
    `1,481,396,317,551원`, prior `1,083,717,091,152원`, and delta `3,977억원`.
  - Query-budget selection now preserves period diversity before truncation so
    explicitly budgeted multi-period comparisons do not silently drop all
    prior-period search surfaces.
- Broader `8 / 4 / 1` promotion check:
  - The official 5-question runtime contract gate set passed under focused
    low-API/BM25 conditions.
  - Results: `NAV_T1_030`, `NAV_T1_071`, `MIX_T1_021`, `KBF_T1_017`, and
    `SKH_T1_060` all returned `numeric_final_judgement = PASS`.
  - Executed retrieval searches were bounded at 7 to 12 per question, with
    no retry queries needed.
  - Treat `8 / 4 / 1` as a viable default candidate, pending one broader
    non-gate inventory check.
  - Separate renderer cleanup remains: `KBF_T1_017` can still append a
    partial-refusal suffix despite numeric PASS, and `NAV_T1_071` uses an
    awkward difference sentence.
- Non-gate `8 / 4 / 1` inventory check:
  - Four curated non-gate questions were tested across the existing
    runtime-contract company set: `NAV_T2_006`, `SAM_T3_028`, `KBF_T2_043`,
    and `SKH_T3_080`.
  - `SAM_T3_028` and `SKH_T3_080` passed numerically.
  - `KBF_T2_043` returned `UNCERTAIN`, and `NAV_T2_006` produced no numeric
    judgement with noisy mixed synthesis.
  - These two non-PASS cases are not budget-truncation failures: their executed
    query traces were `1/1` and `2/2`, with no dropped primary, operand-focused,
    or retry queries.
  - The budget is therefore still a viable default candidate; the next work is
    separate runtime quality cleanup for noisy synthesis and material-gap
    replan behavior.
- Official LLM-evidence-path canary after fallback removal:
  - `NAV_T2_006` passed under the policy-driven gate profile with `8 / 4 / 1`.
  - Final answer preserved `41.4%` and the Poshmark/smart-store/brand-store
    explanation.
  - Metrics: faithfulness `1.000`, answer relevancy `0.837`, context recall
    `1.000`, retrieval hit `1.000`, context P@5 `0.800`, completeness `1.000`,
    error rate `0.0%`.
  - Final narrative retrieval trace selected `3` primary queries, `0`
    operand-focus queries, and `0` retry queries while recording the broader
    state-level query count as `61`.
