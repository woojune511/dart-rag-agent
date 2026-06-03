# Project Status

Last updated: 2026-06-03

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
- Canonical remote embedding runtime:
  OpenAI `text-embedding-3-large` when `OPENAI_API_KEY` is available.
- Latest post-fix fresh OpenAI embedding refresh result:
  - 4 / 4 company runs passed
  - 0 full-eval failures
  - 0 critical misses
  - five-question average faithfulness, completeness, context recall, and
    retrieval hit@k are all `1.000`
  - average section match is `0.975`, citation coverage is `0.933`, entity
    coverage is `0.927`, and error rate is `0.0%`
- Note:
  - `numeric_final_judgement = null` is not a failure for narrative or mixed
    questions when the other evaluator signals are healthy.
- Latest focused repair:
  - `HYU_T2_010` now preserves the source-stated growth display when the DART
    sentence already says `87.0만 대`, `78.1만 대 대비 11.5%`.
  - The deterministic formula trace is still retained, but the final rendered
    answer and `answer_slots.primary_value.rendered_value` use the
    evidence-visible `11.5%` instead of drifting to a recomputed rounding.
  - If a growth calculation accidentally binds duplicate current/prior
    material, runtime now recovers the prior-period display from retrieved
    evidence sentences using generic year/unit/value matching before executing
    the formula.
  - Aggregate growth+narrative composition now treats the structured
    `current_value`, `prior_value`, and growth display slots as required answer
    displays before accepting a mixed-query answer as complete.
  - `NAV_T2_006` now gets commerce-growth driver retrieval from declarative
    retrieval policy suffixes, then rejects source-task display strings whose
    KRW unit conflicts with the already bound growth slot display.
  - The same answer guard replaces growth sentences that mix slot/trace values
    with untraced numeric displays, preserving grounded narrative sentences.
  - Latest OpenAI store-fixed eval-only policy-gate refresh reports
    faithfulness, completeness, context recall, and retrieval hit@k of `1.000`
    for every per-question full-eval row:
    - `NAV_T2_006`: relevancy `0.759`, section match `0.875`,
      citation coverage `0.667`, entity coverage `1.000`
    - `HYU_T2_010`: relevancy `0.696`, section match `1.000`
    - `HYU_T3_072`: relevancy `0.609`, section match `1.000`
    - `LGE_T1_051`: relevancy `0.563`, section match `1.000`,
      `numeric_final_judgement = PASS`
    - `SAM_T2_078`: relevancy `0.817`, section match `1.000`
  - Follow-up diagnosis classified the `SAM_T2_078` section precision gap as
    evaluator-definition drift: the retrieved Harman technology-focus evidence
    from `IV. 이사의 경영진단 및 분석의견` was faithful and complete but was not
    listed as an acceptable expected section. The curated datasets now include
    that section and quote, and recomputing the existing local bundle gives
    section match `1.000`.
  - Latest dependency-slot growth refresh:
    - aggregate growth rows can derive operands from `answer_slots` pointing at
      `task_output:*` lookup rows and recalculate from those sibling lookup
      slots
    - producer lookup slots are propagated back into the serialized growth
      trace, so stale aggregate operands do not survive in `structured_result`
    - `NAV_T2_006` now renders `2,546,649백만원`, `1,801,079백만원`, and
      `41.4%` in the final mixed numeric+narrative answer
    - this is a generic dependency-binding/display-preservation fix, not a
      company/question keyword rule
    - focused `NAV_T2_006` policy-gate smoke confirmed faithfulness `1.000`,
      completeness `1.000`, error rate `0.0%`, and growth-rate answer slots
      aligned to the producer lookup values
  - Validation: runtime domain-term audit passed, focused dependency-growth and
    aggregate preservation regression tests passed, the full unittest suite
    passed, and the full policy gate completed without embedding quota errors.

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
- Embedding provider/model/dimension is part of the store signature. Changing
  it requires a fresh store or a signature-matched cache, not silent store
  reuse.

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
- `retrieval_debug_trace.search_summary` now aggregates executed searches,
  cache hits, vector attempts, and query-embedding calls by retrieval source.
  A local `HYU_T2_010` trace showed `12` searches for the numeric subtask
  (`primary 8`, `operand_focus 4`) and `3` searches for the narrative subtask,
  making retrieval fan-out visible without hand-counting `executed_queries`.
- The same `HYU_T2_010` rerun exposed a remaining answer-composition issue:
  the answer can preserve `87.0만 대` and `11.5%` while omitting the prior
  `78.1만 대` display, which lowers completeness despite correct retrieval and
  calculation. Treat this as an aggregate rendering follow-up, not a retrieval
  budget failure.
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
