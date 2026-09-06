# Project Status

Last updated: 2026-09-07

## Current implementation

The product is the single-agent `FinancialAgent`. The current working branch is
`codex/reviewed-compiler-selection-gate`, with compiler-gate baseline `e9a5be0`.
Contract repairs start from `5e13bc6`; the dependency-boundary fix is `af9a07e`.
Public HTTP fields, `FinancialRunResultV1`, parser/store formats and ID/fingerprint hashing stay intact.
New table candidate IDs are filing-qualified; old catalogs/programs remain immutable predecessor artifacts.

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
- Bundle-first selection retains adjacent source values, attached prose and row notes; query-written bilingual spellings survive planning.
  Physical identity includes explicit filing provenance before dedupe; raw parser IDs remain traceable. Unique selectable-ID caps include retries.
- Source-first output and separately labelled recomputation coexist.
  Dependencies use calculated values; primary answer slots use display values.
- Formula inputs retain their validated evidence-requirement label, period,
  year, and role when projected into execution and evaluator operand rows.
  Requirement-derived periods are marked separately from source period text.
- Annual relative cell labels resolve against report year before generic roles/table focus;
  ambiguity stays unknown. Bound formulas may span sources without physical-ID equality,
  while scope conflicts, assertions, visibility, coupling and row contracts stay enforced; assertion owner order is stable.
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

No role classifier, cross-encoder, metric-specific branch, new provider call, source-store
mutation, evaluator relaxation, or dataset correction. MAS/Streamlit remain experimental.

## Local acceptance

Python 3.13.13: filing-identity full suite `1004 / 1004` (29.105s), focused `160 / 160`, new regressions `11 / 11`, import/topology `22 / 22`, docs `2 / 2`.
Runtime domain audit passes (`84` reviewed literals); pycompile and `git diff --check` pass.

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

## Read-only saved-case replay

`src.ops.replay_runtime_contract_cases` reads immutable results without providers or store writes.
The following exact-ID receipts predate filing-qualified identity; they are historical evidence,
not current-ID compatibility. Current exact replay still rejects a mismatched catalog; inputs are unchanged.

| Case | Provider-free result | Claim limit |
| --- | --- | --- |
| T2 | `11.5% (재계산값 11.4%)`; calculated value `11.395646606914212` | A copy explicitly selects the already-visible source display |
| T3 | `26%`, `700,691백만원`, and the existing four-value narrative | Saved program bytes, physical rows, and evidence remain unchanged |
| Samsung | `28,352,769백만원` plus the existing narrative | A copy restores the recorded first binding and first-attempt authority |

The modified programs are counterfactual validator/executor/display tests, not
new LLM or release evidence. The successor also verifies T2 operand metadata.
The predecessor generic exact-trace audit passed 9 then-current-schema variants, skipped 2 old
schemas, and covers only 3 questions; reversed inputs produce byte-identical
receipts (`9901c8fc...e9180`) with no provider/compiler/store activity.

## Reviewed provider-free corpus

`tests/fixtures/reviewed_runtime_replay_corpus_v1.json` adds five reviewed questions
outside the three-question exact-trace inventory:
`KBF_T1_017`, `KBF_T2_018`, `LGE_T1_051`, `NAV_T2_006`, and `CEL_T1_013`.
Raw values, source excerpts, receipt/row/table provenance, owner visibility, and
programs go through the real normalizer, validator, `CompilationEnvelopeV2`, and executor.

The saved 5/5 receipt (`fc530335...304f`) had zero provider,
compiler, retrieval, or store-write calls. Four cases project historical
filing-linked selections; Celltrion uses manually verified dataset filing evidence.
This proves downstream contracts, not exact candidate replay or fresh compiler choices.

## Provider status and next gate

The historical source-consistent release gate reached `3 / 3 PASS`; immutable T3/Samsung
artifacts and the one approved `HYU_T2_010` run provide its evidence. T2 selected
`87.0만 대`, `78.1만 대`, and source display `11.5%`, retaining `11.4%` as the
labelled recalculation. Both obligations completed with runtime error `0`, ledger
`ok`, and faithfulness/completeness `1.0 / 1.0`.

That admission is exhausted; timing, usage, cost and provenance remain in experiment history.

Earlier four-case comparison: Flash `3/4`, Pro `4/4`; details remain in experiment history.

Latest Pro-only admission `dd8e92f1...42f1` ran once on clean `bd6bd49`: all five reviewed
cases passed. Six calls, no internal retry, `74.3s`; estimated USD `0.120409375` (billing unobserved).
Normal dependency bindings, source-first NAV display and multi-evidence narrative passed;
retry dependency context was not exercised live. All six responses ended STOP and parsed.
Validation ready/execution ok, runtime errors 0; socket-blocked replay matched exactly.
Result: `benchmarks/results/reviewed_compiler_pro_2026-09-07/result.json`.
Approval exhausted; defaults unchanged. Compiler-only success does not prove fresh retrieval.

Approved KB copy: `benchmarks/results/reviewed_full_agent_kbf_store_copy_2026-09-07`.
2,093 vectors; manifest/source coverage and pre-run self-search 3/3 pass. Original store/sidecar bytes are intact.
Admission `138b5fbc...a028` ran once on `457d776`: T2 → T1, runtime 2/2, errors 0, ledger ok.
T2: 70.28%, source negatives preserved. T1: 1.83%, +0.10%p; original evaluator headcount false FAIL retained.
6 Gemini + 17 OpenAI embedding calls, no retries; 107.5s, estimated USD 0.10416639 (not billing).
Result: `benchmarks/results/reviewed_full_agent_kbf_2026-09-07/kb-2023/results.json`; exact replay 2/2.
Count-unit repair excludes word prefixes, retains grammatical suffixes and rejects unsupported real counts.
Evaluator-only replay is 2/2: `benchmarks/results/kbf_count_unit_boundary_replay_2026-09-07/summary.json`.
Answers/evidence/programs/dataset unchanged; calls 0. Approval exhausted; judges unmeasured, no new release claim.
LG/NAV stores retain 2,620 OpenAI vectors, 125 parents and 2,099 payloads; strict readiness/dense health pass 2/2, degraded false. Earlier live 0/2 and local repair evidence remain immutable in experiment history.
Successor `03f03d99...237e` ran once on clean `5fe3a5f`: required-output completion 2/2, final validation ready/execution ok, errors 0, ledgers ok. 8 Gemini + 19 OpenAI calls, 116.909s; usage-estimated USD 0.17174414 < 0.40, billing unobserved. One allowed LG compiler retry; API failures/run retries 0.
LG completes 3/3 outputs, preserving original bindings/assertion: precise profit minus approximate 6,769억원 = 1,486,334,000,000원. Numeric FAIL remains: no atomic accepted source/scope/precision variant; do not treat it as a transport or arithmetic failure.
NAV completes 2/2 outputs without retry: same-row 당기/전기 resolve to 2023/2022, calculation 41.39574110852439%, source display 41.4%. Its new narrative only describes Poshmark service positioning, not acquisition performance; heuristic completeness 0.625, judges unmeasured. An out-of-island missing-ID diagnostic remains in attempt history, not final validation.
Socket-blocked exact replay 2/2; runtime/input/store hashes unchanged. Review SHA `66d5b927...a051`. Approval exhausted; no runtime/evaluator/dataset edit or paid rerun. `benchmarks/results/reviewed_full_agent_lge_nav_period_context_2026-09-07/README.md`.
Source-context/query-spelling and filing-identity repairs now preserve precise LG components and NAV acquisition-performance evidence, separating receipt-local tables before dedupe. Raw table/row/cell IDs remain alongside qualified provenance in prompt/execution evidence. Socket-blocked successor: LG 567 candidates/537 physical cells; NAV 345 → 462 candidates, 218 → 331 physical cells. Every predecessor cell value/period/unit remains; no cross-filing row bundle exists. Catalog contents/fingerprints, owner IDs and prompts match under source reversal and retrieved/seed swap. Numeric/narrative visibility stays 4/3 and 10/6; caps 96/32, provider/store writes 0, 11 input hashes unchanged. New table IDs intentionally differ; old exact-ID receipts are not silently migrated. No fresh compiler or quality-pass claim. Receipt SHA `cbcb383a...3920`; report: `benchmarks/results/filing_table_identity_2026-09-07/README.md`. Next: inspect LG period/source contract versus evaluator governance before paid admission; `공시금액` and source/scope constraints remain unresolved, not relaxed.

Celltrion has no store; default KB 2022 stays outside scope. Formula-wide rounding propagation is deferred. T3 governance is complete; dataset/tolerance/faithfulness boundaries remain unchanged.

See [runtime contract](../architecture/agent_runtime_contract.md), [checked topology](runtime_flow_roles.md), and [experiment history](../history/experiment_history.md).
