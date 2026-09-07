# Project Status

Last updated: 2026-09-08

## Current implementation

The product is the single-agent `FinancialAgent`. The current working branch is
`codex/reviewed-compiler-selection-gate`, with compiler-gate baseline `e9a5be0`.
Contract repairs start from `5e13bc6`; the dependency-boundary fix is `af9a07e`.
Public HTTP fields, `FinancialRunResultV1`, store manifest shape and ID/fingerprint hashing stay intact.
Parser `financial_parser_v2_source_context` honors THEAD/TH; new row/cell candidate IDs may change. Old catalogs/programs remain immutable.

The implemented boundaries are:

- Shared unit scales and source-preserving numeric display; canonical
  KRW/USD/PERCENT/COUNT, signed composite amounts, USD lookups, and finite-value
  checks use one normalizer contract. Compiler emits formula/display intent only;
  code infers dimensions. Table context/header units retain raw hints and exact provenance; ambiguous mixed units stay unknown. Legacy `result_unit` has no validation/render authority.
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
- Bundle-first selection retains adjacent values, prose, row notes and document contexts; bilingual spellings survive planning. Filing-company matches are diagnostic, not value-rank bonuses; explicit subject/scope checks remain.
  Physical identity includes filing provenance before dedupe. V6 prompts share context text; exact context bindings resolve unknown scope in validation/execution without changing raw IDs. Unique selectable-ID caps include retries.
- Source-first output and separately labelled recomputation coexist.
  Dependencies use calculated values; primary answer slots use display values.
- Each formula input records variable/source ID/kind, executed value/unit and validated metadata.
  Candidate/direct-dependency rows keep physical/context evidence; derived inputs reference prior results.
  Arithmetic lineage dedupes leaf IDs/rows/anchors, excluding display/compatibility witnesses; input summaries use calculated values/resolved periods.
- Located calendar/relative cell labels precede source-period fields; unbound parser focus/labels
  cannot assign value years. Unknown numeric periods cannot borrow filing scope, including via witnesses. Bound formulas may span sources without physical-ID equality,
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

No role classifier, cross-encoder, metric-specific runtime branch, provider call, source-store
mutation or global tolerance/faithfulness relaxation. Reviewed dataset revisions are opt-in; MAS/Streamlit remain experimental.

## Local acceptance

Source-field evaluation contract, Python 3.13.13: full suite `1090 / 1090` (31.809s); focused evaluator tests `120 / 120`, including 16 new tests. Saved LG/NAV numeric/final/ledger replay still passes 2/2. Both frozen/current LG answers pass only the explicit v2 successor; 16 altered-source controls fail. Receipt `6c961c96...1c8e`; original datasets/artifacts/stores unchanged, provider calls 0. Dependency input explanations remain repaired; NAV answer bytes stay identical.
Runtime domain audit passes (`84` reviewed literals); docs/import/topology `24 / 24`, pycompile and `git diff --check` pass.

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
Immutable LG/NAV v1 predecessors retain 2,620 OpenAI vectors, 125 parents and 2,099 payloads; their earlier v1 readiness/dense pass is historical, not current v2 readiness. Earlier live 0/2 and local repair evidence remain in experiment history.
Successor `03f03d99...237e` ran once on clean `5fe3a5f`: required-output completion 2/2, final validation ready/execution ok, errors 0, ledgers ok. 8 Gemini + 19 OpenAI calls, 116.909s; usage-estimated USD 0.17174414 < 0.40, billing unobserved. One allowed LG compiler retry; API failures/run retries 0.
LG completes 3/3 outputs, preserving original bindings/assertion: precise profit minus approximate 6,769억원 = 1,486,334,000,000원. Numeric FAIL remains: no atomic accepted source/scope/precision variant; do not treat it as a transport or arithmetic failure.
NAV completes 2/2 outputs without retry: same-row 당기/전기 resolve to 2023/2022, calculation 41.39574110852439%, source display 41.4%. Its new narrative only describes Poshmark service positioning, not acquisition performance; heuristic completeness 0.625, judges unmeasured. An out-of-island missing-ID diagnostic remains in attempt history, not final validation.
Socket-blocked exact replay 2/2; runtime/input/store hashes unchanged. Review SHA `66d5b927...a051`. Approval exhausted; no runtime/evaluator/dataset edit or paid rerun. `benchmarks/results/reviewed_full_agent_lge_nav_period_context_2026-09-07/README.md`.
Approved v2 build `ac0a3ea7...2c89` and paid admission `2724f2ed...4432` are exhausted. Frozen stores: 783/1,872 vectors, 2,127 payloads and 125 parents, readiness 2/2, degraded false. The LG → NAV run on `90aacc9` (runtime `bb8eba2`) completed 2/2, errors 0, ledgers ok: 8 Gemini + 19 OpenAI requests, one allowed NAV compiler retry, 115.265s, estimated USD 0.19107573 / 0.40 (billing unobserved). LG uses precise profit/AMPC and computes 1,486,360백만원; its original atomic FAIL remains frozen. NAV retains 41.4% source display and Poshmark performance evidence; judges are unmeasured. Dependency-provenance repair preserves both saved programs, values, physical evidence and ledger agreement. Separately reviewed LG evaluation v2 now requires resolved 2023, exact filing/source-row/header identity and consolidated scope; it admits both note-only and summary-plus-note precise tuples. Frozen/current LG answers both replay as old-contract FAIL and explicit-successor numeric PASS; 16 source-mutation controls fail. Default datasets/profiles, prior verdicts and source stores remain unchanged, and no provider ran. Receipt `6c961c96...1c8e`; [source review and successor](../evaluation/lge_t1_051_calculation_source_review_v2.md). Next LG admission must explicitly use `benchmarks/datasets/reviewed/lge_t1_051_calculation_v2.json` (SHA `c3f9bb83...1150`); no new paid run is needed to verify this contract repair. Wider quality/release acceptance and Celltrion store readiness remain separate.

Celltrion build `db6d8481...56a9` ran once on `7a31dae` and is exhausted: embeddings 17/17, errors/retries 0, usage-estimated USD 0.11103274 / 0.15 (billing unobserved), about 53.634s. New store: 1,083 vectors/graph nodes, 41 parents, 978 payloads; full roundtrip and 3 dense probes pass, readiness compatible/non-degraded. Original inputs remain unchanged; receipt `68ac4040...1b9e`, review `7a47bff5...9a17`, store fingerprint `dc6f2a47...657f`. [Build result](../../benchmarks/results/reviewed_full_agent_celltrion_store_2026-09-08/README.md). `CEL_T1_013` full-agent admission `e68bc998...865e` is ready for separate approval: existing Flash/Pro routes, copied-store eval-only, judges/embedding metrics off, estimated USD 0.05–0.12 / proposed cap 0.20. Adapter 6/6, provider guard 7/7, runner/store/import/topology/docs 59/59; two 2,270-byte no-call receipts match (`4d91129b...0b2e`). No new provider call, runtime/evaluator/dataset change or original-store write. [Admission](../../benchmarks/results/reviewed_full_agent_celltrion_admission_2026-09-08/README.md). Next: one separately approved run, then source/formula/runtime/ledger review; rehearsal does not establish fresh retrieval/model accuracy. Default KB 2022 stays out of scope; formula-wide rounding propagation remains deferred and T3 governance boundaries are unchanged.

See [runtime contract](../architecture/agent_runtime_contract.md), [checked topology](runtime_flow_roles.md), and [experiment history](../history/experiment_history.md).
