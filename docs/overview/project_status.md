# Project Status

Last updated: 2026-09-07

## Current implementation

The product is the single-agent `FinancialAgent`. The current working branch is
`codex/reviewed-compiler-selection-gate`, with compiler-gate baseline `e9a5be0`.
Contract repairs start from `5e13bc6`; the dependency-boundary fix is `af9a07e`.
Public HTTP fields, `FinancialRunResultV1`, candidate identity inputs, catalog
fingerprints, parser table structure, and stored formats remain compatible.

The implemented boundaries are:

- Shared unit scales and source-preserving numeric display; canonical
  KRW/USD/PERCENT/COUNT, signed composite amounts, USD lookups, and finite-value
  checks use one normalizer contract. Compiler emits formula/display intent only;
  code infers dimensions. Legacy `result_unit` has no validation/render authority.
- Compiler prompt leads with comparison target, transformations/operations, then
  formula; generic contrasts use existing `rationale`, not a role enum or new call.
  Raw signs stay intact; no arithmetic rewrite or validator relaxation was added.
  Undefined ratios and ambiguous comparisons can remain unanswered.
- Google phase routes forward explicit output/thinking/retry/thought-text controls;
  missing settings retain defaults, and explicit zero/false values survive.
- Planner unit errors block only affected islands. Compiler format retries keep
  candidates; explicit candidate conflicts carry exact replacement ownership.
- Structured-output `null`/`none` sentinels normalize to blank only for optional
  planner display/coupling text. Genuine unsupported units remain fail-closed.
- `depends_on` is reserved for other answer obligations. Same-obligation raw
  evidence requirement IDs are removed at planner projection, while known answer
  dependencies, unknown IDs, and self references retain preflight validation.
- `CompilationEnvelopeV2` checks full execution content before revalidation or
  arithmetic. Existing visibility/program/validation checks remain independent.
- Bundle-first selection retains adjacent source values and counts the actual
  query-wide unique selectable IDs, including retry replacement.
- Source-first output and separately labelled recomputation coexist.
  Dependencies use calculated values; primary answer slots use display values.
- Formula inputs retain their validated evidence-requirement label, period,
  year, and role when projected into execution and evaluator operand rows.
  Requirement-derived periods are marked separately from source period text.
- Atomic payload-superset/graph-last persistence, failure propagation, strict
  source coverage, and provider-free sidecar recovery replace partial publication.
- Graph-source vector rebuilds use one expected store manifest for collection,
  embedding, and ingest identity. The manifest is published only after health;
  an interrupted side-by-side target stays unready and resumable.
- API query/readiness snapshots share a lock. DB/ingest/readiness refresh work is
  off the event loop. Health reads cached readiness only.
- Concrete phase inputs/outputs replace the production full-state merge.
  Numeric/narrative owners return facts; final assembly precedes ledger assembly.
  `run()` does not rebuild the answer. TypedDicts are not immutability guarantees.

No role classifier, cross-encoder, metric-specific runtime branch, new provider
call, source-store mutation, evaluator relaxation, or dataset correction is part
of these repairs. MAS and Streamlit remain experimental, without physical moves.

## Local acceptance

Python 3.13.13: last runtime gate on `c28f384` passed focused `20 / 20` and full
`958 / 958`, including import/topology. Admission-local `7 / 7` and related focused `51 / 51` pass.
Runtime domain audit passes with `84` reviewed literals; pycompile and `git diff --check` pass.

- Tests inject failures into actual lower file writes, check same-process and
  restart recovery, and prove no context/embedding calls during sidecar repair.
- Actual graph-node tests check declared phase keys, unchanged inputs, and exact
  public answer/structured-result/trace agreement with the final ledger artifact.
- The reviewed real-question corpus passes `5 / 5` cases twice with
  byte-identical receipts. Its three contract tests prove deterministic replay,
  fail-closed requirement visibility, and raw-value normalization rather than
  trusting copied normalized fields.
- `semantic_comparison_contrasts_v1.json` adds 9 synthetic cases: 7 calculations
  and 2 explicit abstentions. Identical inputs/different intents distinguish valid
  math from intended math. Offline expected values never drive runtime retry;
  rehearsals test harness/execution only, not model accuracy or DART evidence.
- Installed Gemini/LangChain adapters run with a fake client and external sockets
  blocked. Tests distinguish `MAX_TOKENS` from `STOP`/missing fields, preserve
  successful and failed responses across retry, exclude private metadata, and
  verify worker-thread token totals without making a provider request. Both model
  factories preserve explicit budgets; the installed SDK stops after one simulated 429.

New local outputs under `benchmarks/results/` are not committed.

## Read-only saved-case replay

`src.ops.replay_runtime_contract_cases` reads immutable results without creating
a provider, vector store, agent, or benchmark runner. All three catalog
identities verify and input SHA-256 values remain unchanged.

| Case | Provider-free result | Claim limit |
| --- | --- | --- |
| T2 | `11.5% (재계산값 11.4%)`; calculated value `11.395646606914212` | A copy explicitly selects the already-visible source display |
| T3 | `26%`, `700,691백만원`, and the existing four-value narrative | Saved program bytes, physical rows, and evidence remain unchanged |
| Samsung | `28,352,769백만원` plus the existing narrative | A copy restores the recorded first binding and first-attempt authority |

The modified programs are counterfactual validator/executor/display tests, not
new LLM or release evidence. The successor also verifies T2 operand metadata.
The generic exact-trace audit passes all 9 current-schema variants, skips 2 old
schemas, and covers only 3 questions; reversed inputs produce byte-identical
receipts (`9901c8fc...e9180`) with no provider/compiler/store activity.

## Reviewed provider-free corpus

`tests/fixtures/reviewed_runtime_replay_corpus_v1.json` adds five reviewed questions
outside the three-question exact-trace inventory:
`KBF_T1_017`, `KBF_T2_018`, `LGE_T1_051`, `NAV_T2_006`, and `CEL_T1_013`.
Raw values, source excerpts, receipt/row/table provenance, owner visibility, and
programs go through the real normalizer, validator, `CompilationEnvelopeV2`, and executor.

All 5/5 pass with byte-identical receipts (`fc530335...304f`) and zero provider,
compiler, retrieval, or store-write calls. Four cases project historical
filing-linked selections; Celltrion uses manually verified dataset filing evidence.
This proves downstream contracts, not exact candidate replay or fresh compiler choices.

## Provider status and next gate

The source-consistent release gate remains `3 / 3 PASS`; immutable T3/Samsung
artifacts and the one approved `HYU_T2_010` run provide its evidence. T2 selected
`87.0만 대`, `78.1만 대`, and source display `11.5%`, retaining `11.4%` as the
labelled recalculation. Both obligations completed with runtime error `0`, ledger
`ok`, and faithfulness/completeness `1.0 / 1.0`.

That admission is exhausted; timing, usage, cost and provenance remain in experiment history.

Earlier four-case comparison `3edbcb94...1558`: Flash `3/4`, Pro `4/4` on identical
prompts/budgets; only Flash answered an unspecified comparison instead of abstaining.

Latest Pro-only admission `dd8e92f1...42f1` ran once on clean `bd6bd49`: all five reviewed
cases passed. Six calls, no internal retry, `74.3s`; estimated USD `0.120409375` (billing unobserved).
Normal dependency bindings, source-first NAV display and multi-evidence narrative passed;
retry dependency context was not exercised live. All six responses ended STOP and parsed.
Validation ready/execution ok, runtime errors 0; socket-blocked replay matched exactly.
Result: `benchmarks/results/reviewed_compiler_pro_2026-09-07/result.json`.
Approval exhausted; defaults unchanged. Compiler-only success does not prove fresh retrieval.

Approved KB copy: `benchmarks/results/reviewed_full_agent_kbf_store_copy_2026-09-07`.
Manifest/source coverage passes for 2,093 vectors; keep the benchmark collection name.
Stored-vector self-search passes 3/3 after restart; the new run adds full-agent, not HTTP evidence.
Original bytes and copied sidecars are intact; only the copy's local index materialized.
Admission `138b5fbc...a028` ran once on `457d776`: T2 → T1, runtime 2/2, errors 0, ledger ok.
T2: 70.28%, source negatives preserved. T1: 1.83%, +0.10%p; evaluator misreads `2023 명목` as headcount.
6 Gemini + 17 OpenAI embedding calls, no retries; 107.5s, estimated USD 0.10416639 (not billing).
Result: `benchmarks/results/reviewed_full_agent_kbf_2026-09-07/kb-2023/results.json`; exact replay 2/2.
Approval exhausted. Next: provider-free evaluator boundary repair; keep original FAIL. Judges skipped; no release claim.
LG/NAV need legacy-store handling; Celltrion has no store. Default KB 2022 remains outside scope.

Deferred: formula-wide rounding-error propagation. T3 dataset/evaluator
governance completed on 2026-09-03; runtime and dataset ownership remain
separate, and tolerances and faithfulness policy are unchanged.

See [runtime contract](../architecture/agent_runtime_contract.md), [checked topology](runtime_flow_roles.md), and
[experiment history](../history/experiment_history.md).
