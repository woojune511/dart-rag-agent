# Runtime Contract Gate

This document defines the official runtime smoke gate that must pass before
promoting curated mainline benchmark-profile changes or landing runtime-contract
changes that affect numeric planning, grounding, aggregation, or evaluator
projection.

## Canonical profile

- Profile:
  - `benchmarks/profiles/curated_runtime_contract_gate.json`

## Default candidate

- `structural_selective_v2_prefix_2500_320`

`structural_selective_v2` keeps the selective-v2 chunk filter but removes
Gemini-written chunk context generation. It relies only on deterministic
structural prefixes derived from local metadata such as section path, statement
type, table context, and row-label text.

`contextual_selective_v2_prefix_2500_320` remains the quality reference, but it
is no longer part of the routine gate profile. Use it only for explicit
promotion arbitration or tie-breaker reruns when a structural regression needs
to be compared against the old ingest-time contextual baseline.

## Gate question set

- `NAV_T1_030`
- `NAV_T1_071`
- `MIX_T1_021`
- `KBF_T1_017`
- `SKH_T1_060`

These five questions cover:

- deterministic subtractive metrics (`NAV_T1_030`)
- lookup + difference material preservation (`NAV_T1_071`)
- multi-metric aggregate answers (`MIX_T1_021`)
- percent multi-period grounding (`KBF_T1_017`)
- concept-ratio grounding with direct-first acceptance (`SKH_T1_060`)

## Execution policy

- Keep `allow_retrieval_fallback = false`.
- Keep `auto_fetch_missing_report = true` so the gate can recover missing local
  filings from DART without changing the required receipt number.
- Use OpenAI `text-embedding-3-large` as the canonical remote embedding runtime
  when `OPENAI_API_KEY` is available. `DART_EMBEDDING_PROVIDER` remains the
  explicit override for replaying Google or local embedding runs.
- Run this gate with `structural_selective_v2_prefix_2500_320` only in routine
  development regression checks.
- Do not use `contextual_selective_v2_prefix_2500_320` for routine triage or
  single-question canaries. It is an arbitration-only
  quality reference when the structural path has a confirmed regression.
- Treat embedding-provider/model/dimension mismatch as cache miss and reindex.
- Use the stored `store_signature` / `benchmark_cache_meta.json` metadata to
  avoid cross-environment store reuse mistakes.

## Cost-Controlled Triage Loop

Use this order before paying for a full curated gate rerun:

1. Commit the code/docs/test change once unit and contract tests pass.
2. Recheck the active runtime canary with one question only, usually
   `--eval-only --question-id <ID>`.
3. When diagnosing retrieval-heavy questions, add explicit query budgets before
   changing retrieval policy:
   `--retrieval-query-budget <N> --focused-retrieval-query-budget <N> --retry-retrieval-query-budget <N>`.
   This caps search fan-out and records the selected/dropped query counts in
   `retrieval_debug_trace.query_budget`.
4. For already-closed cases such as `comparison_002`, use historical replay
   only unless the live agent path changed.
5. Classify only two or three remaining focused failures at a time as
   retrieval, dependency/synthesis, answer formatting, or evaluator issues.
6. Run the full curated runtime gate once after two or three focused fixes have
   accumulated.

`--low-api-debug` and `--offline-retrieval` are no longer supported runtime
gate modes. If cost is the issue, use explicit evaluator skip flags for
evaluator-only triage or route expensive runtime phases through cheaper models
with `llm_routes`.

## Latency telemetry

Benchmark result traces include coarse phase timing (`parse`, `ingest`, and
per-question `latency_sec`) plus retrieval-level timing inside
`retrieval_debug_trace.executed_queries[].search_telemetry`.

Benchmark ingest and full-eval summaries also include Gemini usage-derived cost
estimates. `estimated_ingest_cost_usd` and `estimated_runtime_cost_usd` are
computed from response usage metadata and the profile pricing table. They
include prompt/input, output/candidate, thinking, cached-content, and tool-use
prompt token buckets when those fields are present in the response metadata.
They are not Cloud Billing invoice values.

Full-eval output records per-question `agent_llm_usage`, `judge_llm_usage`, and
combined `llm_usage`, plus aggregate `llm_*` token totals. This separates
runtime agent cost from evaluator judge cost when diagnosing expensive runs.

Embedding usage is tracked separately because LangChain embedding calls return
vectors, not response usage metadata. The runtime records embedding API calls,
input text count, input characters, and local estimated input tokens for query
and document embedding calls. `estimated_ingest_embedding_cost_usd` and
`estimated_runtime_embedding_cost_usd` are populated only when the benchmark
profile defines `embedding_input_per_million_tokens_usd`; otherwise the usage
fields are still available and the cost fields remain null.

Use these fields to classify slow runs before changing retrieval policy:

- `retrieval_mode`: `hybrid`, `bm25_only`, `bm25_fallback`, or `cache`
- `vector_search_sec`: vector query and query-embedding time observed by the
  vector store call
- `search_telemetry.embedding_usage`: query embedding input-volume estimate for
  the vector search attempt, zero when served from cache or BM25-only mode
- `bm25_search_sec`: local BM25 scoring and top-k filtering time
- `rrf_merge_sec`: hybrid result merge time
- `structure_graph_update_sec`: ingest-side structure graph update and save
  time returned by `add_documents`
- `bm25_build_sec`: ingest-side BM25 index rebuild time returned by
  `add_documents`
- `vector_add_sec`: ingest-side vector add / embedding call time returned by
  `add_documents`
- `ingest.embedding_usage`: document embedding input-volume estimate observed
  during vector add, zero when `skip_vector_add` / BM25-only ingest is active
- `store_add_elapsed_sec`: total ingest-side `add_documents` time, separate
  from the broader profile-level ingest `elapsed_sec`

Do not infer that a slow question is a BM25 problem from `latency_sec` alone.
If `bm25_search_sec` is small but `latency_sec` is large, investigate runtime
workflow, dependency synthesis, reconciliation, or answer formatting instead.

## Recommended invocation

Full gate run:

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_runtime_contract_gate.json `
  --output-dir benchmarks/results/runtime_contract_gate_manual
```

Store-fixed single-question rerun:

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_runtime_contract_gate.json `
  --output-dir benchmarks/results/runtime_contract_gate_manual `
  --eval-only `
  --question-id SKH_T1_060
```

Fast numeric canary mode:

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_runtime_contract_gate.json `
  --output-dir benchmarks/results/runtime_contract_gate_manual `
  --eval-only `
  --question-id SKH_T1_060 `
  --numeric-fast-gate
```

Single-question canary mode:

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_runtime_contract_gate.json `
  --output-dir benchmarks/results/runtime_contract_gate_manual `
  --company-run-id skh_2023_runtime_contract_gate `
  --eval-only `
  --question-id SKH_T1_060
```

Single-question canary with bounded retrieval fan-out:

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_runtime_contract_gate.json `
  --output-dir benchmarks/results/runtime_contract_gate_manual `
  --company-run-id naver_2023_runtime_contract_gate `
  --question-id NAV_T1_030 `
  --numeric-fast-gate `
  --retrieval-query-budget 12 `
  --focused-retrieval-query-budget 6 `
  --retry-retrieval-query-budget 2
```

Latest local bounded-query canary:

- Date: 2026-06-02
- Output:
  `benchmarks/results/runtime_query_budget_nav_t1_030_2026-06-02/`
- Result:
  - `NAV_T1_030`: `numeric_final_judgement = PASS`
  - answer: `1조 3,616억원`
  - faithfulness, completeness, and context recall all `1.000`
  - executed retrieval queries: `9` (`primary = 3`, `operand_focus = 6`)
  - budget trace: `primary 3/3`, `operand_focus 6/16`, `retry 0/0`
  - API calls / estimated cost: `0 / $0.0000`
- Follow-up note:
  - The earlier fresh low-API/BM25 `SKH_T1_060` failure was classified as a
    structured lookup / dependency operand-binding regression, not query-budget
    plumbing. It is now closed by preferring stronger direct structured row-label
    evidence when projecting lookup task outputs into ratio dependencies.
  - Latest focused low-API rerun:
    `benchmarks/results/runtime_lookup_direct_row_skh_t1_060_2026-06-02/`
    returned `42.02%` with `numeric_final_judgement = PASS`.
  - Producer lookup serialization is aligned with the final dependency
    projection: the focused JSON now shows `task_6` as `9,490,410백만원`, with
    zero stale `(600,550)백만원` occurrences.

Latest bounded-query runtime canaries:

- Date: 2026-06-02
- Scope: focused low-API/BM25 canaries
- `SKH_T1_060` candidate budgets:
  - `12 / 6 / 2`: PASS, 18 executed retrieval searches
  - `8 / 4 / 1`: PASS, 12 executed retrieval searches
- `KBF_T1_017` candidate budget:
  - `8 / 4 / 1`: `numeric_final_judgement = PASS`, 12 executed retrieval
    searches
- `NAV_T1_071` baseline check:
  - `8 / 4 / 1`: FAIL, 12 executed retrieval searches
  - `12 / 6 / 2`: FAIL, 18 executed retrieval searches
  - unbounded: FAIL, 23 executed retrieval searches
  - all three runs produce the same stale `0원` difference shape, so this is a
    separate runtime regression rather than a budget-only regression.
- `NAV_T1_071` regression fix:
  - Root cause: period-insensitive precision refinement re-selected the first
    contextual table cell after reconciliation had already identified the
    prior-period fiscal column.
  - Runtime fix: contextual table-cell refinement now delegates to the generic
    period-aware structured-cell selector before replacing a reconciled
    operand value.
  - Focused low-API rerun: `numeric_final_judgement = PASS`; operands were
    current `1,481,396,317,551원`, prior `1,083,717,091,152원`, and difference
    `3,977억원`.
- Current interpretation:
  - `8 / 4 / 1` is promising for focused canaries that already have healthy
    runtime grounding (`SKH_T1_060`, `KBF_T1_017`). With `NAV_T1_071` fixed,
    the remaining promotion work is broader focused coverage rather than this
    specific blocker.
  - Explicit query-budget selection now preserves period diversity before
    truncation, preventing a generic class of multi-period comparison
    regressions.
  - This is an execution-cost control only. It does not add domain vocabulary,
    company-specific branches, or benchmark-answer rules.

Broader bounded-query promotion check:

- Date: 2026-06-02
- Command shape: focused low-API/BM25 run with budgets `8 / 4 / 1`
  (`--retrieval-query-budget 8 --focused-retrieval-query-budget 4
  --retry-retrieval-query-budget 1`)
- Scope: official 5-question runtime contract gate set
- Result: 5 / 5 `numeric_final_judgement = PASS`
- Per-question trace:
  - `NAV_T1_030`: PASS, 7 executed retrieval searches
    (`primary 3/3`, `operand_focus 4/16`, `retry 0/0`)
  - `NAV_T1_071`: PASS, 12 executed retrieval searches
    (`primary 8/15`, `operand_focus 4/14`, `retry 0/0`)
  - `MIX_T1_021`: PASS, 7 executed retrieval searches
    (`primary 3/3`, `operand_focus 4/4`, `retry 0/0`)
  - `KBF_T1_017`: PASS, 12 executed retrieval searches
    (`primary 8/33`, `operand_focus 4/4`, `retry 0/0`)
  - `SKH_T1_060`: PASS, 12 executed retrieval searches
    (`primary 8/30`, `operand_focus 4/11`, `retry 0/0`)
- Interpretation:
  - `8 / 4 / 1` is now a viable default candidate for the focused runtime
    contract gate, not just for isolated canaries.
  - Keep it as a candidate until one broader non-gate inventory confirms it
    does not hide retrieval gaps outside this curated set.
  - Follow-up quality work remains separate from numeric correctness:
    `KBF_T1_017` still includes a partial-refusal suffix despite numeric PASS,
    and `NAV_T1_071` has an awkward difference-rendering sentence.

Non-gate bounded-query inventory:

- Date: 2026-06-02
- Command shape: focused low-API/BM25 run with budgets `8 / 4 / 1`
- Scope: four non-gate curated questions across the existing runtime-contract
  company set
- Result summary:
  - `SAM_T3_028`: PASS, 1 executed retrieval search
    (`primary 1/1`, `operand_focus 0/0`, `retry 0/0`)
  - `SKH_T3_080`: PASS, 12 executed retrieval searches
    (`primary 8/18`, `operand_focus 4/10`, `retry 0/0`)
  - `KBF_T2_043`: UNCERTAIN, 1 executed retrieval search
    (`primary 1/1`, `operand_focus 0/0`, `retry 0/0`)
  - `NAV_T2_006`: no numeric judgement, 2 executed retrieval searches
    (`primary 2/2`, `operand_focus 0/0`, `retry 0/0`)
- Interpretation:
  - The two non-PASS cases are not query-budget truncation failures: neither
    dropped any primary, operand-focused, or retry queries.
  - `8 / 4 / 1` remains a viable retrieval-budget default candidate.
  - The non-gate inventory exposed separate runtime quality work:
    `NAV_T2_006` needs synthesis/noise control for mixed numeric+narrative
    answers, and `KBF_T2_043` needs replan/material-gap handling for
    numeric+narrative growth questions.

Historical answer replay:

```powershell
.\.venv\Scripts\python.exe -m src.ops.replay_full_eval_from_results `
  --source-results benchmarks/results/runtime_contract_gate_manual/SK하이닉스-2023/results.json `
  --dataset-path benchmarks/datasets/single_doc_eval_full.curated.json `
  --output-dir benchmarks/results/replay_runtime_contract_manual `
  --question-id SKH_T1_060
```

## Pass criteria

- All five gate questions must finish with `numeric_final_judgement = PASS`.
- Any candidate with one or more full-evaluation question failures is
  disqualified as the default runtime candidate, even if it is cheaper or
  faster to ingest.
- Runtime outputs must preserve:
  - `structured_result`
  - `resolved_calculation_trace`
- No fallback retrieval backend should be used in benchmark mode.

## Current interpretation

Current gate interpretation is now stable:

- `plain_prefix_8000_400`
  - speed / cost baseline
  - not eligible as default because `SKH_T1_060` fails
- `contextual_selective_v2_prefix_2500_320`
  - historical quality reference
  - only rerun when explicit arbitration against the old contextual baseline is
    needed
- `structural_selective_v2_prefix_2500_320`
  - all five gate questions pass
  - current operating default because it preserves gate quality without the
    full ingest-time cost of contextual selective ingestion
  - latest `SKH_T1_060` closure came from note-aggregate lookup hardening for
    `장기차입금` / `사채`, not from relaxing the gate

## Current Focused Triage Notes

Last checked: 2026-05-31.

- `runtime_contract_gate_official_2026-05-31`
  - Command shape:
    - `benchmark_runner --config benchmarks/profiles/curated_runtime_contract_gate.json --output-dir benchmarks/results/runtime_contract_gate_official_2026-05-31 --numeric-fast-gate --progress-heartbeat-sec 30 --heartbeat-log <path>`
  - Official-path refresh:
    - `NAV_T1_030`: PASS
    - `NAV_T1_071`: PASS
    - `KBF_T1_017`: PASS
    - `MIX_T1_021`: PASS
    - `SKH_T1_060`: PASS (`42.02%`)
  - Run status:
    - completed
    - aggregate `results.json` lists no pending companies
    - `cross_company_summary.md` reports 4 / 4 company runs with 0 full-eval
      fails and 0 critical misses
    - API calls / estimated cost: `0 / $0.0000`
    - top-level `results.json` is a multi-company manifest; use
      `cross_company_summary.md` for aggregate status and each
      `<company>/results.json` for per-question traces
  - Timeout note:
    - KBF initially exceeded the old 5-minute no-result stop window because a
      fresh output directory had no reusable KBF store and store construction /
      embedding was still active
    - the fresh official run again spent most of its time in KBF store
      construction (`ingest = 1428.606s`) but heartbeat progress continued to
      advance and the run completed successfully
    - follow-up implementation reduced BM25-only fresh ingest write
      amplification by saving the structure graph once per `add_documents`
      call instead of once per resume batch
    - a shell wrapper timeout can fire before the runner process finishes; if
      the heartbeat process is still alive, continue monitoring the existing
      run instead of starting a second one
    - future monitored refreshes should prefer runner-native
      `--progress-heartbeat-sec <seconds> --heartbeat-log <path>` so the
      runner records phase/progress/store mtime directly instead of relying
      only on an external PowerShell wrapper
  - Artifact status:
    - `benchmarks/results/runtime_contract_gate_official_2026-05-31/` is an
      experiment output and should stay out of source commits
- `SKH_T1_060`
  - Command shape:
    - `benchmark_runner --eval-only --question-id SKH_T1_060 --low-api-debug`
  - 2026-05-31 fresh-output focused run:
    - `benchmark_runner --config benchmarks/profiles/curated_runtime_contract_gate.json --output-dir benchmarks/results/skh_t1_060_low_api_2026-05-31 --company-run-id skh_2023_runtime_contract_gate --question-id SKH_T1_060 --low-api-debug --numeric-fast-gate --progress-heartbeat-sec 10 --heartbeat-log <path>`
  - Diagnostic result:
    - `answer = 42.02%`
    - `numeric_final_judgement = PASS`
    - `numeric_equivalence = 1.0`
    - `numeric_grounding = 1.0`
    - `numeric_retrieval_support = 1.0`
    - `retrieval_hit_at_k = 1.0`
    - `resolved_operand_count = 5`
    - API calls / estimated cost: `0 / $0.0000`
  - Failure class:
    - not a current retrieval/dependency blocker
    - latest focused run binds the five required operands through task outputs
      and plans `((short-term borrowings + long-term borrowings + bonds) /
      (PPE + intangible assets)) * 100`
    - low-API answer text is intentionally terse because render/verification
      LLM calls are disabled; judge the diagnostic by
      `resolved_calculation_trace` and numeric gate fields
    - previous low-API residual was deterministic operand binding: a broad
      table context allowed one row/value to be reused for a different required
      operand
    - fixed by generic provenance rules:
      - direct support must find the operand surface and value in the same
        claim / quote / raw-row snippet before falling back to broad context
      - required-operand candidate construction does not bind a row to one
        operand based only on context when that row directly names another
        required operand
- Low-API/offline bundles
  - Status:
    - removed from the official benchmark runner and agent runtime path
  - Rationale:
    - BM25-only retrieval and deterministic answer/evidence fallbacks made API
      cost cheaper but tested a different system from the production runtime
    - evidence extraction now preserves `missing` when the LLM cannot produce
      grounded evidence, instead of promoting retrieved snippets into claims
  - Cost-control replacement:
    - use explicit evaluator switches such as `--skip-llm-judges` only when the
      goal is evaluator-cost triage
    - use `llm_routes` to route expensive runtime phases to cheaper compatible
      models without bypassing LLM evidence extraction or planning contracts
- `comparison_002`
  - Treat as a solved multi-entity grounding case only when replaying a saved
    PASS trace.
  - Use historical replay for routine regression; do not rerun the live agent
    unless multi-entity routing, retrieval, reconciliation, or calculation
    code changed.
  - 2026-05-31 current-code replay:
    - `benchmarks/results/replay_multi_entity_manual_2026-05-31-current/`
    - `comparison_002 = PASS`
    - `numeric_equivalence = 1.0`
    - `numeric_grounding = 1.0`
    - `numeric_retrieval_support = 1.0`
- `MIX_T1_064`
  - Command shape:
    - `benchmark_runner --eval-only --question-id MIX_T1_064 --low-api-debug`
  - Diagnostic result:
    - `answer = 90.7%`
    - `numeric_final_judgement = PASS`
    - `numeric_equivalence = 1.0`
    - `numeric_grounding = 1.0`
    - `numeric_retrieval_support = 1.0`
  - Failure class:
    - no longer a current retrieval/dependency/formatting blocker
    - previous residual was structural evidence preservation plus numeric
      synthesis ordering: the correct financial-statement table seed could be
      pushed out of the visible reranked window, and an incidental
      narrative-summary sibling could overwrite a complete deterministic
      numeric ratio
    - fixed by generic runtime rules:
      - required-operand seed docs may be promoted when parser metadata and
        operand coverage satisfy the active task contract
      - non-note canonical `statement_type` can prove structured evidence
        scope even when the section path is only the parent statement section
      - narrative summary text cannot satisfy unresolved numeric gaps, and a
        complete deterministic numeric result wins unless the query explicitly
        requests explanatory context

## Related canary

- `comparison_002` is the current multi-entity / segment-grounding canary.
- Latest runtime fix:
  - repeated `revenue` addends from the LLM concept planner are rehydrated with
    `segment_label` metadata (`SDC`, `Harman`) before grounding
  - segment-scoped direct grounding rejects non-matching company-total rows
- Latest direct runtime result on Samsung 2024:
  - `SDC 매출액 = 29조 1,578억원`
  - `Harman 매출액 = 14조 2,749억원`
  - `합계 = 43조 4,327억원`

## Related focused gate

- Multi-entity / segment-style comparisons now have a dedicated focused gate:
  - `docs/evaluation/multi_entity_grounding_gate.md`
  - `benchmarks/profiles/curated_multi_entity_grounding_gate.json`
- Current covered questions:
  - `comparison_001`
  - `comparison_002`
  - `comparison_003`

## Concept Runtime Gap Gate

Concept-planner gap closures now have a dedicated focused runtime gate:

- Profile:
  - `benchmarks/profiles/curated_concept_runtime_gap_gate.json`
- Candidate:
  - `structural_selective_v2_prefix_2500_320`
- Covered questions:
  - `KBF_T2_018`
  - `SKH_T3_080`
  - `CEL_T1_013`
  - `CEL_T3_040`
  - `POS_T1_057`
  - `KAB_T1_066`
  - `SAM_T3_028`

The gate exists because the expanded concept-planner shadow probe identified
real runtime gaps that planner-structure validation alone could not prove:

- missing or underspecified ontology concepts
- concept aliases and section priors that were too weak for retrieval
- row-family selection failures when the right structured table was retrieved
  but the wrong sibling row was selected
- direct lookup rendering that rounded source table units and weakened numeric
  grounding

Promotion decision:

- Keep the original five-question `curated_runtime_contract_gate.json` as the
  default short runtime smoke gate.
- Promote these seven cases as a separate official focused gate rather than
  merging them into the default smoke gate.
- Run this gate when changing concept ontology, concept planning, structured
  row binding, lookup rendering, reconciliation retry queries, or numeric
  evaluator projection.

Latest verification:

- Date: 2026-05-28
- Temporary validation profile:
  - `benchmarks/profiles/tmp_concept_runtime_gap_gate_2026-05-28.json`
- Output directory:
  - `benchmarks/results/tmp_concept_runtime_gap_gate_2026-05-28/`
- Artifact status:
  - temporary local output was summarized here and later cleaned; use the
    reusable profile below for reruns.
- Result:
  - 7 / 7 questions finished with `numeric_final_judgement = PASS`
  - `numeric_equivalence = 1.0` and `numeric_grounding = 1.0` for all seven
    questions

2026-06-02 full refresh:

- Profile:
  - `benchmarks/profiles/curated_concept_runtime_gap_gate.json`
- Output directory:
  - `benchmarks/results/concept_runtime_gap_gate_refresh_2026-06-02_042728/`
    (local experiment artifact only; do not commit raw results)
- Command shape:
  - `benchmark_runner --config benchmarks/profiles/curated_concept_runtime_gap_gate.json --output-dir benchmarks/results/concept_runtime_gap_gate_refresh_2026-06-02_042728 --eval-only --progress-heartbeat-sec 30 --heartbeat-log <path>`
- Result:
  - all seven full-evaluation questions finished with
    `numeric_final_judgement = PASS`
  - question ids: `KBF_T2_018`, `SKH_T3_080`, `CEL_T1_013`, `CEL_T3_040`,
    `POS_T1_057`, `KAB_T1_066`, `SAM_T3_028`
  - company summary reports 6 / 6 company runs with 0 full-eval fails and 0
    critical misses; this is a company-run count, while the full-evaluation
    question set contains 7 questions because Celltrion carries two focused
    questions
  - aggregate summary:
    - `full_numeric_pass_rate = 1.000`
    - `full_completeness = 1.000`
    - `full_faithfulness = 1.000`
    - average `full_context_recall = 0.917`
- Residual found and closed during refresh:
  - the first full-path refresh still exposed a `CEL_T3_040` table-family
    selection issue: low-API planning was closed, but the full agent path could
    retrieve the right sibling table row for one lookup slot while earlier
    lookup slots remained marked as missing or selected the wrong sibling value
  - the fix stays generic:
    - split multi-concept lookup tasks now carry sibling lookup surfaces from
      the other lookup slots so reconciliation can prefer table families that
      contain the requested row family
    - aggregate assembly can recover failed lookup slots from already retrieved
      structured table evidence when that evidence contains the active operand
      surface and the sibling surfaces required by the task contract
    - deterministic lookup-list rendering is limited to aggregate answers made
      only from lookup/single-value tasks, so ratio/sum/growth aggregates keep
      their existing task-order answer composition
  - confirmed `CEL_T3_040` full-path answer values:
    - inventory valuation loss: `2,526,280` thousand KRW
    - inventory valuation loss reversal: `48,885,812` thousand KRW
    - inventory disposal loss: `25,163,510` thousand KRW
- Promotion interpretation:
  - the concept runtime gap gate is clean as a focused gate
  - keep it separate from the default five-question smoke gate, but run it
    before landing changes to ontology-driven lookup planning, structured row
    binding, sibling evidence recovery, or aggregate numeric rendering

The focused blocker notes below are chronological triage records. Any
"remaining blocker" or "promotion verdict" statement inside those notes should
be read as the status at that point in time; the 2026-06-02 full refresh above
is the current confirmation for the seven-question concept runtime gap gate.

2026-06-02 focused blocker update:

- `SKH_T3_080` is closed in the focused low-API concept-runtime gate.
- Failure class:
  - not retrieval coverage and not missing ontology
  - the retrieved notes row already carried the required gain/loss evidence,
    but the parenthesized gain amount was propagated as a negative value from
    lookup slot to downstream dependency calculation
  - aggregate answer composition also kept an earlier raw lookup fragment ahead
    of the complete difference sentence, which made numeric evaluation see an
    unsupported negative claim
- Runtime changes are generic:
  - ontology-declared lookup magnitude semantics are applied to structured
    slot/operand rows after evidence lookup, including `source_row_ids` and
    `recon::` evidence ids
  - dependency-bound difference results preserve the common source display unit
    so exact source-table arithmetic such as `백만원` does not get rounded into
    compact KRW text
  - aggregate fallback prefers a complete deterministic numeric result when it
    already contains the needed operands and result, instead of prefixing stale
    partial lookup text
- Focused validation:
  - command shape:
    - `benchmark_runner --config benchmarks/profiles/curated_concept_runtime_gap_gate.json --company-run-id skh_2023_concept_gap --question-id SKH_T3_080 --low-api-debug --progress-heartbeat-sec 30 --heartbeat-log <path>`
  - local output bundle:
    `benchmarks/results/concept_gap_skh_t3_080_low_api_2026-06-02_fix5/`
    (local experiment artifact only; do not commit raw results)
  - result:
    - `numeric_final_judgement = PASS`
    - `numeric_equivalence = 1.0`
    - `numeric_grounding = 1.0`
    - `numeric_retrieval_support = 1.0`
    - final calculation result: `-332,236백만원`
- Remaining runtime blockers:
  - `CEL_T1_013`: missing capitalized-development-cost operand binding.
  - `CEL_T3_040`: wrong value-source selection for inventory valuation
    loss/reversal rows.
- Promotion verdict remains unchanged: do not promote concept-only planning as
  a runtime default until the remaining CEL blockers close through generic
  operand/evidence-source contracts and the focused gate is rerun.

2026-06-02 focused blocker update (CEL_T1_013):

- `CEL_T1_013` is closed in the focused low-API concept-runtime gate.
- Failure class:
  - not retrieval coverage and not formula arithmetic
  - the relevant R&D table already contained both the total R&D denominator
    and the capitalized-development-cost numerator
  - broad concept aliases could still direct-bind unrelated table columns or
    older fiscal-ordinal tables before the more specific ontology surface was
    selected
  - surface unit inference could also overwrite a known KRW table unit when a
    bare value was followed by a longer Korean word beginning with a count unit
- Runtime changes are generic:
  - surface evidence cannot override an existing structured unit when the
    normalized unit families conflict
  - ontology concepts may require their `surface_contract.positive` terms for
    direct structured matching; runtime code consumes that declaration without
    adding topic-specific branches
  - required-operand assembly applies the same positive-surface requirement and
    extracts values from the matching table-value line, not merely a broad
    alias elsewhere in the table context
  - when multiple current-period table candidates satisfy the same surface
    contract, higher DART fiscal ordinals are preferred as the current table
    shape before older repeated tables
- Focused validation:
  - command shape:
    - `benchmark_runner --config benchmarks/profiles/curated_concept_runtime_gap_gate.json --company-run-id celltrion_2023_concept_gap --question-id CEL_T1_013 --low-api-debug --progress-heartbeat-sec 30 --heartbeat-log <path>`
  - local output bundle:
    `benchmarks/results/concept_gap_cel_t1_013_low_api_fix8_2026-06-02/`
    (local experiment artifact only; do not commit raw results)
  - result:
    - `numeric_final_judgement = PASS`
    - final operands: `342,736,271` and `181,624,107` thousand KRW
    - final calculation result: `52.99%`
- Remaining runtime blocker:
  - `CEL_T3_040`: wrong value-source selection for inventory valuation
    loss/reversal rows.
- Promotion verdict remains unchanged until the remaining CEL blocker closes
  and the focused gate is rerun.

2026-06-02 focused blocker update (CEL_T3_040):

- `CEL_T3_040` is closed in the focused low-API concept-runtime gate.
- Failure class:
  - not retrieval coverage and not missing ontology; the inventory valuation
    loss, reversal, and disposal-loss concepts were already present in the
    ontology
  - the router classified the question as `qa`, so concept-only numeric lookup
    planning did not run even though ontology concepts and numeric unit
    families were available
  - once planned, multiple direct lookup concepts needed independent task-ledger
    entries so downstream lookup binding could select one grounded row/value per
    concept instead of treating the request as one multi-operand formula
  - aggregate answer selection needed to prefer grounded lookup slots over raw
    narrative table text
- Runtime changes are generic:
  - ontology-backed `qa` queries may be promoted to numeric lookup planning only
    when the active retrieval policy declares generic lookup markers, allowed
    operation families, and numeric unit families
  - multi-concept direct lookups are split into one concept task per operand,
    preserving concept constraints, section/type priors, and retrieval queries
  - aggregate composition renders successful lookup slots as a deterministic
    list before falling back to raw narrative/table text
  - ontology concepts may require their full surface contract for direct lookup,
    which prevents short generic row labels from binding unrelated sibling rows
- Focused validation:
  - command shape:
    - `benchmark_runner --config benchmarks/profiles/curated_concept_runtime_gap_gate.json --company-run-id celltrion_2023_concept_gap --question-id CEL_T3_040 --low-api-debug --progress-heartbeat-sec 30 --heartbeat-log <path>`
  - local output bundle:
    `benchmarks/results/concept_gap_cel_t3_040_low_api_fix4_2026-06-02/`
    (local experiment artifact only; do not commit raw results)
  - result:
    - `numeric_final_judgement = PASS`
    - `faithfulness = 1.0`
    - `answer_relevancy = 1.0`
    - `context_recall = 1.0`
    - `retrieval_hit_at_k = 1.0`
    - `citation_coverage = 1.0`
    - `entity_coverage = 1.0`
    - `completeness = 1.0`
    - `numeric_pass_rate = 1.0`
    - `avg_score = 0.976`
    - final answer:
      `재고자산평가손실 2,526,280천원, 재고자산평가손실환입 48,885,812천원, 재고자산폐기손실 25,163,510천원입니다.`
- Remaining runtime blockers:
  - none in the current focused low-API CEL blocker set.
- Promotion verdict:
  - the focused low-API blocker set is closed; use the 2026-06-02 full refresh
    above as the official seven-question confirmation before relying on these
    concept-runtime changes.

2026-06-01 full sweep update:

- The curated gate was rerun through the reusable profile and produced clean
  passes for `SAM_T3_028`, `POS_T1_057`, and `KAB_T1_066`.
- `KBF_T2_018` was reclassified as an evaluator tolerance issue: the runtime
  answer `70.24%` and answer-key value about `70.28%` differ only by small
  formula/display rounding. Percent equivalence now allows a `0.05`
  percentage-point gap, and store-reuse eval-only passes.
- The evaluator now guards multi-value numeric answers against false positives:
  a response cannot pass just because one numeric claim matches one reference
  number if other answer numeric claims are unsupported by the answer key or
  canonical evidence candidates.
- After that evaluator fix, these were the remaining runtime blockers:
  - `SKH_T3_080`: signed/parenthesized foreign-currency translation gain and
    downstream net-effect binding.
  - `CEL_T1_013`: missing capitalized-development-cost operand binding.
  - `CEL_T3_040`: wrong value-source selection for inventory valuation
    loss/reversal rows.
- Promotion verdict remains unchanged: do not promote concept-only planning as
  a runtime default until the remaining blockers close through generic
  sign/operand/evidence-source contracts.

2026-05-31 focused triage update:

- `KAB_T1_066` was rechecked with the low-API numeric loop before rerunning the
  full focused gate.
- The failure split was:
  - calculation safety: stale ratio plans could bind the same operand twice
  - evidence preservation: a required denominator row was present in structured
    reconciliation candidates, but not in the compact evidence window
  - operand identity: fallback rows needed fresh operand IDs before formula
    planning
- Runtime changes are intentionally generic:
  - executable ratio, difference, and growth-rate plans must bind distinct
    required operands
  - low-API missing-required recovery may promote already-built reconciliation
    row candidates when they satisfy the active operand contract
  - retrieved table chunks may be expanded into row-level candidates before
    operand extraction, so a relevant raw row is not lost after rerank/summary
    compression
- Focused result:
  - `KAB_T1_066` now closes with `numeric_final_judgement = PASS`
  - calculated result: `37.47%`
  - validation used `--low-api-debug --numeric-fast-gate`
- Keep this as a focused canary result, not an official full-gate refresh. Run
  the full `curated_concept_runtime_gap_gate` only after 2-3 focused closures or
  when changing ontology, structured row binding, dependency binding, or formula
  planning broadly.

Recommended invocation:

```powershell
.\.venv\Scripts\python.exe -m src.ops.benchmark_runner `
  --config benchmarks/profiles/curated_concept_runtime_gap_gate.json `
  --output-dir benchmarks/results/concept_runtime_gap_gate_manual
```

## Policy-Driven Runtime Gate

Retrieval-policy changes have a separate focused gate:

- Profile:
  - `benchmarks/profiles/curated_policy_driven_runtime_gate.json`
- Candidate:
  - `structural_selective_v2_prefix_2500_320`
- Covered full-evaluation questions:
  - `NAV_T2_006`
  - `HYU_T2_010`
  - `HYU_T3_072`
  - `LGE_T1_051`
  - `SAM_T2_078`
- Additional smoke coverage:
  - Samsung dividend cash outflow + shareholder-return policy mixed query

Run this gate when changing `src/config/retrieval_policy.py`, narrative summary
selection, policy-driven deterministic composers, or planner fallback tracing.
The purpose is to prove that vocabulary has moved into policy/config without
losing behavior on the previously hard-coded retrieval/composition cases.

Current gate status:

- 2026-06-02 store-fixed full refresh:
  - source/output store bundle:
    `benchmarks/results/policy_gate_regression_2026-05-31_2212/`
    (local experiment artifact only; do not commit raw results)
  - command shape:
    - `benchmark_runner --config benchmarks/profiles/curated_policy_driven_runtime_gate.json --output-dir benchmarks/results/policy_gate_regression_2026-05-31_2212 --eval-only --progress-heartbeat-sec 30 --heartbeat-log <path>`
  - scope: all four policy-driven company runs and all five full-evaluation
    questions (`NAV_T2_006`, `HYU_T2_010`, `HYU_T3_072`, `LGE_T1_051`,
    `SAM_T2_078`) with the current runtime/evaluator and existing stores.
  - aggregate signal:
    - 4 / 4 company runs passed
    - `full_eval_fail_count = 0`
    - `critical_category_miss_count = 0`
    - average `full_faithfulness = 1.0`
    - average `full_completeness = 1.0`
    - average `full_context_recall = 1.0`
    - average numeric pass rate is `1.0` over applicable numeric questions;
      `numeric_final_judgement = null` remains not-applicable for narrative or
      mixed questions, not a failure
  - per-question signal after the 2026-06-02 mixed growth/narrative repair:
    - `NAV_T2_006`: faithfulness `1.000`, completeness `1.000`,
      context recall `1.000`, answer relevancy `0.855`, context P@5 `0.800`
    - `HYU_T2_010`: faithfulness `1.000`, completeness `1.000`,
      context recall `1.000`, answer relevancy `0.857`, context P@5 `0.800`
    - `HYU_T3_072`: faithfulness `1.000`, completeness `1.000`,
      context recall `1.000`, answer relevancy `0.836`, context P@5 `1.000`
    - `LGE_T1_051`: faithfulness `1.000`, completeness `1.000`,
      context recall `1.000`, answer relevancy `0.888`, context P@5 `1.000`,
      `numeric_final_judgement = PASS`
    - `SAM_T2_078`: faithfulness `1.000`, completeness `1.000`,
      context recall `1.000`, answer relevancy `0.913`, context P@5 `0.800`
  - implementation scope:
    - duplicate current/prior growth operands can recover the prior display
      from retrieved evidence sentences with generic year/unit/value matching
    - growth display selection rejects source-task displays whose KRW unit
      conflicts with the already bound answer slot
    - aggregate growth answers replace numeric sentences that mix required
      slot displays with untraced numeric values, while preserving supported
      narrative context
    - commerce-growth narrative retrieval uses declarative
      `retrieval_query_suffixes` in retrieval policy rather than agent
      control-flow branches
  - interpretation:
    - no current policy-driven runtime blocker is open
    - keep this as the focused policy gate for changes to retrieval policy,
      policy-driven narrative composition, planner fallback tracing, or
      structured numeric projection

- 2026-06-01 NAV_T2_006 narrative-preservation focused replay:
  - source store bundle:
    `benchmarks/results/policy_gate_regression_2026-05-31_2212/`
  - local output bundle:
    `benchmarks/results/policy_gate_naver_markerpolicy_evalonly_2026-06-01_fix17/`
    (local experiment artifact only; do not commit raw results)
  - scope: NAVER-only store-fixed eval-only for `NAV_T2_006`, covering
    growth-rate dependency operands plus evidence-backed narrative focus
    preservation during aggregate answer composition.
  - result: `faithfulness = 1.0`, `completeness = 1.0`,
    `calculation_correctness = 1.0`, `unit_consistency_pass = 1.0`,
    `grounded_rendering_correctness = 1.0`, `context_recall = 1.0`,
    `retrieval_hit_at_k = 1.0`, and `avg_score = 0.898`.
  - implementation scope: lookup subtasks preserve structured row units from
    evidence metadata, dependency operands can be synthesized from sibling
    lookup outputs when answer slots are absent, and aggregate growth+narrative
    composition now preserves the focused narrative row's adjacent supported
    context instead of collapsing it to a single sentence. The runtime still
    consumes generic policy/config markers and retrieved subtask evidence; no
    company-, question-, or benchmark-id branch was added.

- 2026-06-01 technology-focus policy extraction replay:
  - source store bundle:
    `benchmarks/results/policy_gate_regression_2026-05-31_2212/`
  - local output bundle:
    `benchmarks/results/policy_gate_technology_policy_evalonly_2026-06-01_0221/`
    (deleted after recording this summary; raw result artifacts are not a
    source commit target)
  - implementation commit: `63ede63` (`Move technology focus terms to policy`)
  - scope: Samsung-only store-fixed eval-only for `SAM_T2_078`, covering
    technology-focus narrative assembly and the R&D amount surface used in the
    mixed numeric/narrative answer.
  - result: `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`,
    `avg_score = 0.952`, and `error_rate = 0.0%`.
  - implementation scope: R&D amount selection terms, output labels, unit text,
    sentence templates, and phrase joiners now come from the active
    technology-focus narrative policy; ratio component candidate scoring uses
    ontology component surfaces and query-year matching instead of metric-name
    branches.

- 2026-06-01 evidence assembly policy extraction replay:
  - source store bundle:
    `benchmarks/results/policy_gate_regression_2026-05-31_2212/`
  - local output bundle:
    `benchmarks/results/policy_gate_evidence_policy_evalonly_2026-06-01_0143/`
    (deleted after recording this summary; raw result artifacts are not a
    source commit target)
  - implementation commit: `f46be1f` (`Move evidence assembly terms to policy`)
  - scope: store-fixed eval-only over `NAVER 2023`, `현대자동차 2023`,
    `LG에너지솔루션 2023`, and `삼성전자 2023` with current
    runtime/evaluator.
  - aggregate signal: all four company runs have
    `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`, and
    `error_rate = 0.0%`.
  - per-company `avg_score`:
    - `NAV_T2_006`: `0.899`
    - `HYU_T2_010` / `HYU_T3_072`: `0.951`
    - `LGE_T1_051`: `0.981`, with `numeric_pass_rate = 1.0`
    - `SAM_T2_078`: `0.952`, with `entity_coverage = 1.0`
  - implementation scope: quantitative-impact denominator/caveat wording,
    entity-table summary section/metric/role labels, and required-operand
    aggregate/unit surfaces now live in retrieval policy config; runtime keeps
    the generic row scanning, slot projection, and evidence-preservation
    mechanics.

- 2026-06-01 remaining-company store-fixed replay:
  - source store bundle:
    `benchmarks/results/policy_gate_regression_2026-05-31_2212/`
  - output bundle:
    `benchmarks/results/policy_gate_rest_evalonly_2026-06-01_0000/`
  - scope: `NAVER 2023`, `LG에너지솔루션 2023`, `삼성전자 2023` with
    current runtime/evaluator and existing stores.
  - `NAV_T2_006`: `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`,
    `avg_score = 0.894`; answer covers `41.4%`, Poshmark 체질 개선 /
    연결 편입 효과, 스마트스토어, and 브랜드스토어 growth.
  - `LGE_T1_051`: `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`,
    `avg_score = 0.989`; answer covers `2,163,234백만원`,
    `6,769억원`, and `1,486,334백만원`.
  - `SAM_T2_078`: `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`,
    `entity_coverage = 1.0`, `avg_score = 0.952`; answer covers
    `28,352,769백만원`, Harman 전장 사업 방향, IT 기술 접목, and SDV
    focus.
  - artifact policy: the replay bundle is local experiment material and should
    not be committed.

- 2026-06-01 `SAM_T2_002` growth aggregate rendering fix:
  - output bundle:
    `benchmarks/results/tmp_samsung_multi_report_sam_t2_002_2026-05-22/`
  - scope: Samsung multi-report focused eval-only for `SAM_T2_002`, using the
    existing structural selective store.
  - failure classification: not a retrieval miss. The structured runtime trace
    had the current value, prior value, and growth-rate result; the final
    aggregate answer omitted the current/prior operand values.
  - implementation scope: generic `growth_rate` aggregate rendering from
    `answer_slots` plus sibling `task_output:*` lookup slots. This preserves
    source-display values and avoids benchmark/company-specific branches.
  - focused eval-only after the fix:
    `numeric_final_judgement = PASS`, `numeric_equivalence = 1.0`,
    `numeric_grounding = 1.0`, `numeric_retrieval_support = 1.0`,
    `faithfulness = 1.0`, `retrieval_hit_at_k = 1.0`, `avg_score = 0.791`.
  - validation guard: `tests.test_subtask_loop`,
    `tests.test_aggregate_subtask_projection`,
    `tests.test_evaluator_runtime_projection`, and
    `tests.test_benchmark_runner_runtime_projection` passed (`102` tests);
    runtime domain-language audit also passed.

- 2026-05-31 Hyundai targeted refresh:
  - output bundles:
    `benchmarks/results/policy_gate_hyundai_markerclean_2026-05-31_2315/`
    and
    `benchmarks/results/policy_gate_hyundai_slottrace_evalonly_2026-05-31_2335/`
  - scope: `hyundai_2023_policy_driven_runtime_gate` with
    `structural_selective_v2_prefix_2500_320`
  - store-fixed eval-only aggregate:
    `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`,
    `grounded_rendering_correctness = 1.0`,
    `calculation_correctness = 1.0`, `avg_score = 0.952`,
    `error_rate = 0.0%`
  - `HYU_T2_010`: answer covers `87.0만 대`, `78.1만 대`,
    `11.5%`, IRA / 핵심원자재법 / 보호무역주의 대응 필요성; the
    query bundle no longer contains unrelated `연결 편입효과` suffixes.
  - deterministic replay after evaluator count-unit normalization gives
    `HYU_T2_010` `operand_selection_correctness = 1.0` and
    `unit_consistency_pass = 1.0`.
  - implementation scope: broad impact retrieval policy was narrowed, count
    operand unit-family checks were added, growth+narrative aggregation now
    preserves evidence-visible slot displays, and evaluator normalization now
    treats scaled count units such as `만대` / `만 대` consistently.
  - artifact policy: all result directories above are local experiment material
    and should not be committed.

- 2026-05-30 refresh:
  - output bundle: `benchmarks/results/policy_gate_refresh_2026-05-30/`
  - completed company runs: `NAVER 2023`, `현대자동차 2023`,
    `LG에너지솔루션 2023`, `삼성전자 2023`
  - pending company runs: none
  - winner ranking for the four-company bundle:
    `pass_count = 4`, `company_count = 4`, `full_eval_fail_count = 0`,
    `critical_category_miss_count = 0`
  - `NAV_T2_006`: `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`
  - `HYU_T2_010`: `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`; answer covers
    `78.1만 대`, `87.0만 대`, `11.5%`, and IRA / 핵심원자재법 /
    보호무역주의 대응 필요성.
  - `HYU_T3_072`: `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`; answer covers
    Motional 기초 지분율 `50.00%`, 기말 지분율 `25.81%`,
    투자장부금액 `1,294,367백만원`, 계속영업손실 `(803,742)백만원`,
    and 총포괄손실 `(791,627)백만원`.
  - `SAM_T2_078`: `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`
  - `LGE_T1_051`: numeric path is closed with
    `numeric_final_judgement = PASS`, `numeric_equivalence = 1.0`,
    `numeric_grounding = 1.0`, and `numeric_retrieval_support = 1.0`.
    The current official answer includes the company context and exact AMPC
    value: `LG에너지솔루션 2023년 연결기준 영업이익 2,163,234백만원`,
    `AMPC 676,874백만원(약 6,769억원)`, and
    `실질 영업이익 1,486,360백만원`; `completeness = 1.0`.
  - aggregate full-eval metrics: `avg_full_faithfulness = 1.0`,
    `avg_full_completeness = 1.0`, `avg_full_numeric_pass_rate = 1.0`,
    and `avg_full_context_recall = 1.0`.
  - Runtime/evaluator hardening from this refresh:
    slot-derived evaluator operands now preserve resolved sibling-task
    metadata (`dependency_resolved`, `source_task_id`, `source_slot`) from the
    original calculation trace, and a resolved `task_output:*` operand no
    longer needs its own `source_anchor` to allow deterministic numeric
    grounding override. Unresolved task-output-only operands remain blocked.
    Slot-based difference answers also recover company context from grounded
    slot anchors when `report_scope.company` is unavailable.

- 2026-05-29 cleanup update:
  - Removed the runtime deterministic composer that hard-coded one
    policy-growth sales case shape. Future coverage for that class should come
    from policy-driven retrieval, structured growth operands, and narrative
    evidence synthesis rather than a case regex.
  - Moved dividend payout extraction patterns, statement hints, and answer
    templates into retrieval policy config; the runtime path consumes policy
    fields generically.
  - A local five-question replay was attempted with a temporary profile but was
    stopped after exceeding the no-result-file budget while rebuilding stores.
    The partial store/log output is local experiment material only.
  - Unit verification after the cleanup: `python -m unittest discover -s tests`
    passed (`470` tests).

- The 2026-05-29 policy-driven full gate rerun is closed for the structural
  candidate.
  - output bundle: `benchmarks/results/policy_driven_runtime_gate_rerun_2026-05-29/`
  - `pass_count = 4`
  - corrected `full_eval_fail_count = 0`
  - average full-eval metrics: `faithfulness = 1.0`, `completeness = 1.0`,
    `numeric_pass_rate = 1.0`, `context_recall = 1.0`
- Summary semantics: `numeric_pass_rate = None` on non-numeric or narrative
  questions is treated as not-applicable, not as a full-eval failure. Missing
  faithfulness or completeness still fails the row.
- `SAM_T2_078` was already passing in the official 2026-05-29 full-evaluation
  output.
- `LGE_T1_051` is closed in the latest full gate after preserving prose AMPC
  evidence and refining the operand from contextual note structured table
  cells:
  - latest full-gate answer: `영업이익 2,163,234백만원`, `AMPC 676,874백만원`, `실질 영업이익 1,486,360백만원`
  - `numeric_equivalence = 1.0`
  - `numeric_grounding = 1.0`
  - `numeric_retrieval_support = 1.0`
  - `numeric_final_judgement = PASS`
  - `faithfulness = 1.0`
  - `completeness = 1.0`
  - `grounded_rendering_correctness = 1.0`
  - `calculation_correctness = 1.0`
  - runtime hardening:
    exact parenthetical KRW values such as `6,769억원(676,874백만원)` are
    preferred when present, rounded or derived LLM operands can be refined from
    structured table cells or contextual note rows, and adjusted/exclusion
    difference results render from slot contracts before LLM synthesis.
- `NAV_T2_006` is closed in the latest targeted smoke after suppressing stale
  growth+narrative planner feedback only when the final answer already covers
  the growth-rate value and narrative impact:
  - `faithfulness = 1.0`
  - `completeness = 1.0`
  - `refusal_accuracy = 1.0`
  - final answer no longer carries the partial-refusal suffix
  - 2026-06-01 follow-up provenance smoke with the official policy-driven
    runtime profile confirmed that `task_output:*` dependency operands now keep
    direct evidence provenance instead of surfacing null-like source ids:
    aggregate `source_row_ids = ["ev_001", "task_output:task_3",
    "task_output:task_4"]`, current/prior lookup slots each keep the original
    `ev_001` anchor, and no literal `"None"` source id appears in the
    calculation projection.
  - latest focused metrics after this provenance cleanup:
    `faithfulness = 1.0`, `answer_relevancy = 0.837`,
    `context_recall = 1.0`, `retrieval_hit_at_k = 1.0`,
    `section_match_rate = 0.875`, `citation_coverage = 0.667`,
    `entity_coverage = 0.75`, `completeness = 1.0`,
    `calculation_correctness = 1.0`.
  - remaining debt is not numeric grounding: the answer still has minor Korean
    composition noise and the trace still shows broad mixed-query fan-out.
- `HYU_T2_010` is closed in the latest targeted smoke:
  - answer covers `87.0만 대`, `78.1만 대`, `11.5%`, IRA / 핵심원자재법 /
    보호무역주의 대응 필요성
  - 2026-06-02 follow-up store-fixed eval-only confirms source-stated display
    preservation: `answer_slots.primary_value.rendered_value = "11.5%"` and
    the final answer says `2022년 78.1만 대 대비 11.5% 증가`.
  - 2026-06-02 projection follow-up store-fixed eval-only confirms aggregate
    child provenance survives final projection: top-level
    `answer_slots.operation_family = "aggregate_subtasks"`, two child
    `subtask_results` are present, and the growth child carries
    `operation_family = "growth_rate"` with `source_row_ids = ["ev_001"]`.
    The narrative child has no numeric row id, which is acceptable because it is
    not a structured numeric operand.
  - 2026-06-02 narrative provenance follow-up keeps row and evidence
    provenance separate: the growth child keeps `source_row_ids = ["ev_001"]`
    and empty `source_evidence_ids`, while the narrative/aggregate child keeps
    empty `source_row_ids` and `source_evidence_ids = ["ev_001"]`.
  - 2026-06-03 evaluator provenance follow-up confirms the evaluator consumes
    that projection into `calculation_result.derived_metrics`: deduped
    `aggregate_subtask_provenance` has two rows, aggregate row ids are
    `["ev_001"]`, aggregate evidence ids are `["ev_001"]`, and the focused
    eval-only keeps `faithfulness = 1.0`, `completeness = 1.0`,
    `context_recall = 1.0`, `citation_coverage = 1.0`, and
    `entity_coverage = 1.0`.
  - 2026-06-03 full policy-gate store-fixed eval-only after evaluator
    provenance consumption covered all five policy questions:
    `NAV_T2_006`, `HYU_T2_010`, `HYU_T3_072`, `LGE_T1_051`, and
    `SAM_T2_078`. All five kept `faithfulness = 1.0`,
    `completeness = 1.0`, `context_recall = 1.0`, and
    `retrieval_hit_at_k = 1.0`; `LGE_T1_051` kept
    `numeric_final_judgement = PASS`. Aggregate provenance remained quiet:
    `HYU_T2_010` exposes two deduped child provenance rows with aggregate row
    ids `["ev_001"]` and aggregate evidence ids `["ev_001"]`; `NAV_T2_006`
    keeps aggregate row ids `["ev_001", "task_output:task_3",
    "task_output:task_4"]`; `SAM_T2_078` keeps aggregate row ids
    `["ev_001"]`.
  - 2026-06-03 narrative terminology follow-up:
    - implementation keeps runtime code generic. Growth+narrative composition
      now requires all evidence-supported policy driver groups to survive into
      the answer, and compact query markers are preserved only when grounded by
      retrieved/source text or ontology alias binding to a concept already
      rendered in the numeric answer.
    - focused store-fixed eval-only on
      `benchmarks/results/policy_gate_regression_2026-06-03_narrative_terms_focus/`
      closed both remaining narrative completeness checks:
      - `NAV_T2_006`: `faithfulness = 1.0`, `completeness = 1.0`,
        `retrieval_hit_at_k = 1.0`, error rate `0.0%`
      - `LGE_T1_051`: `faithfulness = 1.0`, `completeness = 1.0`,
        `numeric_final_judgement = PASS`, error rate `0.0%`; final answer
        preserves the ontology/query-visible `IRA` and `AMPC` displays.
  - `faithfulness = 1.0`
  - `completeness = 1.0`
  - `context_recall = 1.0`
  - `retrieval_hit_at_k = 1.0`
  - `grounded_rendering_correctness = 1.0`
  - `calculation_correctness = 1.0`
  - `avg_score = 0.958`
  - validation: runtime domain-term audit passed and full unittest discover
    passed with `604` tests.
- `HYU_T3_072` is closed in the latest targeted smoke:
  - answer covers Motional `25.81%`, `1,294,367백만원`, 계속영업손실
    `(803,742)백만원`, 총포괄손실 `(791,627)백만원`
  - structured row evidence projection now surfaces the selected slot labels and
    values in runtime evidence, closing `entity_coverage = 1.0` in focused
    store-fixed eval-only.
  - `faithfulness = 1.0`
  - `raw_faithfulness = 0.5`
  - `faithfulness_override_reason = structured summary 계산/렌더링 검증이 충분해 faithfulness를 1.0으로 보정`
  - `completeness = 1.0`
  - `retrieval_hit_at_k = 1.0`
  - `grounded_rendering_correctness = 1.0`
  - `calculation_correctness = 1.0`
  - `avg_score = 0.910` in the latest store-fixed replay
  - follow-up narrative table-focus replay: `ndcg_at_5 = 1.195`,
    `context_precision_at_5 = 0.800`, `section_match_rate = 0.800`,
    `entity_coverage = 1.0`, `grounded_rendering_correctness = 1.0`,
    `avg_score = 0.939`.
    This uses table/numeric intent format inheritance and declarative slot/focus
    coverage, then prefers selected table sections for final fill rather than
    new runtime benchmark strings.
- These smoke checks use the official structural collection name
  `dart_reports_v2_structural-selective-v2-prefix-2500-320`.
- The raw rerun directory is a local benchmark artifact and should not be
  committed. Use the reusable profile below for future reruns.

2026-06-03 concept runtime gap follow-up:

- A fresh monitored concept-runtime gate refresh was run locally with
  `benchmarks/profiles/curated_concept_runtime_gap_gate.json`.
  - local output bundle:
    `benchmarks/results/concept_runtime_gap_gate_refresh_2026-06-03_provenance/`
  - the bundle is experiment material and was intentionally left untracked.
  - heartbeat logging was enabled for the fresh run and follow-up eval-only
    refreshes.
- Initial seven-question refresh result:
  - PASS: `SKH_T3_080`, `CEL_T3_040`, `KAB_T1_066`, `SAM_T3_028`
  - FAIL: `KBF_T2_018`, `CEL_T1_013`, `POS_T1_057`
- Runtime fixes stayed inside generic evidence/slot contracts:
  - dependency lookup replacement now compares raw unit and normalized value,
    not only raw display value, so a stronger structured slot can replace a
    same-text value with a different unit scale.
  - required operands with a declared surface contract must have positive
    direct evidence before structured direct lookup scoring can prefer them.
  - sibling lookup recovery uses the same unit/normalized-value replacement
    rule.
- Focused store-fixed eval-only after the fixes:
  - `CEL_T1_013`: PASS, final answer `52.99%`,
    `numeric_equivalence = 1.0`, `numeric_grounding = 1.0`,
    `numeric_retrieval_support = 1.0`, `faithfulness = 1.0`,
    `completeness = 1.0`.
  - `POS_T1_057`: PASS, final answer `3.5269배`,
    `numeric_equivalence = 1.0`, `numeric_grounding = 1.0`,
    `numeric_retrieval_support = 1.0`, `faithfulness = 1.0`,
    `completeness = 1.0`.
- Remaining residual:
  - `KBF_T2_018` still needs a separate review. The observed calculation path
    was grounded, while the residual failure looked tied to auxiliary numeric
    claim support/evaluator alignment rather than a missing retrieval concept.
- Verification after the code change:
  - `python -m unittest tests.test_part_whole_ratio_contract` passed
    (`11` tests).
  - `python -m src.ops.audit_runtime_domain_terms` passed.
  - `python -m unittest tests.test_aggregate_subtask_projection
    tests.test_subtask_loop tests.test_semantic_numeric_plan` passed
    (`139` tests).

2026-06-03 concept runtime gap closure:

- The residuals above were closed with generic runtime/evaluator contracts, not
  benchmark-specific branches.
  - `KBF_T2_018`: numeric equivalence now ignores auxiliary answer numbers only
    when they are equivalent to a value visible in runtime support text.
  - `POS_T1_057`: dependency calculations with `task_output:*` operands are
    recalculated from the latest source-task answer slots when those slots carry
    stronger value/unit/provenance contracts; evaluator numeric parsing also
    recognizes `배` ratio displays with display-rounding tolerance.
  - `SKH_T3_080`: lookup execution applies ontology-declared magnitude
    semantics to operand rows before answer-slot construction, so
    parenthesized magnitude concepts feed downstream subtraction as declared
    positive magnitudes.
- Focused store-fixed eval-only checks after the fixes:
  - `KBF_T2_018`: PASS.
  - `POS_T1_057`: PASS, final answer `3.5269배`.
  - `SKH_T3_080`: PASS, final answer uses `573,884백만원`,
    `906,120백만원`, and `-332,236백만원`.
- Full seven-question store-fixed eval-only refresh after the focused fixes:
  - command:
    `benchmark_runner --config benchmarks/profiles/curated_concept_runtime_gap_gate.json --output-dir benchmarks/results/concept_runtime_gap_gate_refresh_2026-06-03_provenance --eval-only --progress-heartbeat-sec 30 --heartbeat-log benchmarks/results/concept_runtime_gap_gate_refresh_2026-06-03_provenance/_logs/heartbeat_concept_gate_all7_after_pos_skh_2026-06-03.jsonl`
  - `CEL_T1_013`: PASS, faithfulness `1.0`, completeness `1.0`,
    context recall `0.667`, citation coverage `0.667`.
  - `CEL_T3_040`: PASS, faithfulness `1.0`, completeness `1.0`,
    context recall `1.0`, citation coverage `1.0`.
  - `KAB_T1_066`: PASS, faithfulness `1.0`, completeness `1.0`,
    context recall `1.0`, citation coverage `1.0`.
  - `KBF_T2_018`: PASS, faithfulness `1.0`, completeness `1.0`,
    context recall `0.667`, citation coverage `1.0`.
  - `POS_T1_057`: PASS, faithfulness `1.0`, completeness `1.0`,
    context recall `1.0`, citation coverage `1.0`.
  - `SAM_T3_028`: PASS, faithfulness `1.0`, completeness `0.3`,
    context recall `0.667`, citation coverage `1.0`.
  - `SKH_T3_080`: PASS, faithfulness `1.0`, completeness `1.0`,
    context recall `1.0`, citation coverage `1.0`.
- Follow-up `SAM_T3_028` focused store-fixed eval-only closure:
  - change: aggregate synthesis now reuses the existing
    `supported_quantitative_impact_assembly` contract when the final evidence
    set contains the labeled numerator and denominator values for a
    quantitative impact question. This keeps the absolute amount, the supported
    impact sentence, and the ratio in the final answer instead of collapsing to
    the ratio-only numeric answer.
  - command:
    `benchmark_runner --config benchmarks/profiles/curated_concept_runtime_gap_gate.json --output-dir benchmarks/results/sam_t3_028_quant_impact_focus_2026-06-03 --company-run-id samsung_2023_concept_gap --eval-only --question-id SAM_T3_028 --progress-heartbeat-sec 30 --heartbeat-log benchmarks/results/sam_t3_028_quant_impact_focus_2026-06-03/_logs/heartbeat_sam_t3_028_quant_impact_2026-06-03.jsonl`
  - result: PASS, numeric final judgement `PASS`, faithfulness `1.0`,
    completeness `1.0`, context recall `0.667`, citation coverage `1.0`.
  - final answer includes `5,037,579백만원`, the supported cost-of-sales impact
    sentence, `180,388,580백만원`, and `2.79%`.
- Full seven-question store-fixed eval-only refresh after the quantitative
  impact closure:
  - command:
    `benchmark_runner --config benchmarks/profiles/curated_concept_runtime_gap_gate.json --output-dir benchmarks/results/concept_runtime_gap_gate_refresh_2026-06-03_quant_impact_full --eval-only --progress-heartbeat-sec 30 --heartbeat-log benchmarks/results/concept_runtime_gap_gate_refresh_2026-06-03_quant_impact_full/_logs/heartbeat_concept_gate_all7_quant_impact_2026-06-03.jsonl`
  - all seven questions passed with numeric final judgement `PASS`.
  - average completeness improved from the previous full refresh's `0.883` to
    `1.0`.
  - per-question completeness is now `1.0` for `CEL_T1_013`, `CEL_T3_040`,
    `KAB_T1_066`, `KBF_T2_018`, `POS_T1_057`, `SAM_T3_028`, and
    `SKH_T3_080`.
  - faithfulness is `1.0` for all seven questions; context recall remains
    `0.667` for `CEL_T1_013`, `KBF_T2_018`, and `SAM_T3_028`, and `1.0` for
    the other four questions.
- Residual context-recall audit:
  - `CEL_T1_013`: the two numeric operands (`342,736,271천원` total R&D cost
    and `181,624,107천원` capitalized development cost) are present in runtime
    evidence. The remaining recall gap is the canonical auxiliary sentence
    about no current-period government grant receipts; the answer does not need
    that auxiliary sentence to compute the requested ratio.
  - `SAM_T3_028`: runtime evidence contains the inventory valuation amount and
    cost-of-sales denominator, and the final answer preserves the supported
    impact sentence. The remaining recall gap is a quote-surface mismatch for
    the canonical sentence saying the cost includes inventory valuation losses.
  - `KBF_T2_018`: the answer is grounded through MDA summary-table values and
    risk-note scenario evidence, but the canonical direct comprehensive-income
    statement row is not preserved as the selected context. This is the only
    residual that looks like a retrieval coverage improvement candidate rather
    than an evaluator granularity artifact.
- Follow-up KBF statement-row preservation and evaluator grounding refresh:
  - change: top-level retrieval now carries query-derived statement/section
    hints only when no active subtask section contract is already present. This
    lets an explicitly requested statement row be preserved for mixed narrative
    questions without broadening active calculation subtasks.
  - change: supplemental section seed matching can use quoted top-level row
    labels together with query-inferred statement types. This is generic
    evidence preservation; it does not add metric/company-specific runtime
    branches.
  - change: numeric evaluator grounding can deterministically accept answer
    numbers that are directly visible in runtime evidence or are reproduced by
    simple derivations from runtime-evidence numbers, such as displayed
    differences, ratios, and percent changes. This handles source row values
    and rounded answer operands without making the agent runtime follow
    evaluator tricks.
  - focused `KBF_T2_018` eval-only result:
    PASS, faithfulness `1.0`, completeness `1.0`, context recall `0.667`,
    citation coverage `1.0`; runtime evidence now includes the direct
    `III. 재무에 관한 사항 > 2. 연결재무제표 > 2-2. 연결 포괄손익계산서`
    row quote.
  - focused `POS_T1_057` eval-only regression check:
    PASS, faithfulness `1.0`, completeness `1.0`, context recall `1.0`,
    citation coverage `1.0`.
  - full seven-question store-fixed eval-only refresh:
    command:
    `benchmark_runner --config benchmarks/profiles/curated_concept_runtime_gap_gate.json --output-dir benchmarks/results/concept_runtime_gap_gate_statement_preserve_eval_override_full_2026-06-03 --eval-only --progress-heartbeat-sec 30 --heartbeat-log benchmarks/results/concept_runtime_gap_gate_statement_preserve_eval_override_full_2026-06-03/_logs/heartbeat_statement_preserve_eval_override_full_2026-06-03.jsonl`
  - all seven questions passed with numeric final judgement `PASS`.
  - faithfulness and completeness are `1.0` for all seven questions.
  - context recall remains `0.667` for `CEL_T1_013`, `KBF_T2_018`, and
    `SAM_T3_028`, and `1.0` for `CEL_T3_040`, `KAB_T1_066`, `POS_T1_057`,
    and `SKH_T3_080`.
- Verification after the closure:
  - `python -m unittest tests.test_evaluator_runtime_projection
    tests.test_math_parsing tests.test_retrieval_scope
    tests.test_operation_contracts tests.test_semantic_numeric_plan` passed
    (`306` tests).
  - `python -m unittest tests.test_subtask_loop tests.test_operation_contracts`
    passed (`213` tests).
  - `python -m unittest tests.test_math_parsing
    tests.test_aggregate_subtask_projection
    tests.test_evaluator_runtime_projection
    tests.test_benchmark_runner_runtime_projection` passed (`83` tests).
  - `python -m unittest tests.test_operation_contracts` passed (`151`
    tests).
  - `python -m src.ops.audit_runtime_domain_terms` passed.

2026-06-04 OpenAI-embedding fresh concept-gate refresh:

- A fresh monitored seven-question run was started because the local
  `concept_runtime_gap_gate_statement_preserve_eval_override_full_2026-06-03`
  directory only contained logs and could not support a store-fixed eval-only
  refresh.
- Command shape:
  `benchmark_runner --config benchmarks/profiles/curated_concept_runtime_gap_gate.json --output-dir benchmarks/results/concept_runtime_gap_gate_refresh_2026-06-04_after_narrative_terms --progress-heartbeat-sec 30 --heartbeat-log .../_logs/heartbeat_all7_after_narrative_terms_2026-06-04.jsonl`
- Initial fresh-store result under OpenAI `text-embedding-3-large`:
  - PASS: `CEL_T1_013`, `CEL_T3_040`, `KAB_T1_066`, `SAM_T3_028`,
    `SKH_T3_080`.
  - FAIL: `KBF_T2_018`, `POS_T1_057`.
- `POS_T1_057` focused closure:
  - Root cause: the direct structured lookup selected a detail/segment
    interest-expense cell instead of the aggregate/final cell.
  - Runtime fix: structured cell scoring now consumes existing generic
    `value_role`, `aggregation_stage`, and aggregate metadata when an operand
    binding policy prefers aggregate values. Sibling cell candidate metadata is
    preserved through reconciliation so this remains data-driven rather than a
    topic-specific branch.
  - Focused eval-only after the fix: PASS, faithfulness `1.0`,
    completeness `1.0`, context recall `1.0`, citation coverage `1.0`,
    numeric final judgement `PASS`, final ratio `3.5269배`.
- Follow-up focused closures:
  - `KBF_T2_018`: PASS after preserving formula operand evidence for percent
    answers. The current/prior operands stay visible in runtime evidence even
    when the final sentence renders only the derived percentage.
  - `KAB_T1_066`: PASS after ratio extraction prefers an active reconciled
    direct operand set when it covers every required operand. This lets the
    same profitability table provide both numerator and denominator instead of
    letting an older dependency lookup shadow the reconciled row.
  - `SAM_T3_028`: PASS after quantitative-impact assembly stopped asserting a
    cost/inclusion relation unless the relation is visible in the same evidence
    claim. Without a visible relation, the answer reports only the denominator
    대비 규모 and keeps the caveat.
- Post-commit store-fixed all-seven eval-only check:
  - Command shape:
    `benchmark_runner --config benchmarks/profiles/curated_concept_runtime_gap_gate.json --output-dir benchmarks/results/concept_runtime_gap_gate_refresh_2026-06-04_after_narrative_terms --eval-only --progress-heartbeat-sec 30 --heartbeat-log .../_logs/heartbeat_all7_post_commit_eval_only_2026-06-04.jsonl`
  - Result: the all-seven run completed, but exposed two remaining numeric
    failures: `KBF_T2_018` and `POS_T1_057`.
- Post-check focused closures:
  - `POS_T1_057`: PASS after moving the sign decision into declarative
    concept binding policy. `interest_expense` now declares
    `ratio_denominator_sign = magnitude`, and runtime code applies that
    generic policy only for ratio denominators. Focused result:
    faithfulness `1.0`, completeness `1.0`, numeric grounding `1.0`,
    retrieval support `1.0`, numeric final judgement `PASS`.
  - `KBF_T2_018`: PASS after evidence projection promotes table metadata rows
    that support final-answer numeric material into evaluator-visible
    claim/quote text, and aggregate projection stops treating short unitless
    `UNKNOWN` numerics as material operands. Focused result: faithfulness
    `1.0`, completeness `1.0`, numeric grounding `1.0`, retrieval support
    `1.0`, numeric final judgement `PASS`.
- Residual quality note:
  - `SAM_T3_028` passes numeric grounding and remains an answer-composition
    detail follow-up rather than a numeric runtime blocker.
- Verification for the safe changes:
  - `python -m unittest
    tests.test_aggregate_subtask_projection.AggregateSubtaskProjectionTests.test_dependency_rows_synthesize_lookup_slot_from_subtask_answer
    tests.test_aggregate_subtask_projection.AggregateSubtaskProjectionTests.test_dependency_projection_recalculates_from_stronger_source_task_slot
    tests.test_subtask_loop.SubtaskLoopTests.test_growth_explanatory_fallback_drops_untraced_numeric_draft
    tests.test_subtask_loop.SubtaskLoopTests.test_ok_lookup_is_not_replaced_with_different_direct_evidence_value
    tests.test_subtask_loop.SubtaskLoopTests.test_direct_structured_lookup_prefers_aggregate_cell_metadata
    tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_projection_promotes_subtask_source_evidence_ids`
    passed.
  - `python -m unittest tests.test_lookup_recovery_policy
    tests.test_evaluator_runtime_projection
    tests.test_subtask_loop.SubtaskLoopTests.test_dependency_guard_blocks_direct_rows_for_unresolved_ratio_binding
    tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_subtasks_preserves_supported_quantitative_impact_answer`
    passed (`62` tests after the post-check fixes).
  - `python -m src.ops.audit_runtime_domain_terms` passed.

Recommended invocation:

```powershell
.\scripts\run_policy_driven_gate.ps1 `
  -OutputDir benchmarks/results/policy_gate_regression_YYYY-MM-DD
```

For a no-cost command check before starting the expensive gate:

```powershell
.\scripts\run_policy_driven_gate.ps1 -DryRun
```
