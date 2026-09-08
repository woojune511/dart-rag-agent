# Project Status

Last updated: 2026-09-09

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
- Bundle-first selection retains adjacent values, prose, row notes and contexts. Metric fragments are not inferred subjects; exact metric axes precede containment tiers. No additive scores, filing-company relevance bonuses or weakened explicit subject/scope checks.
  Physical identity includes filing provenance before dedupe. V6 prompts use compact JSON with exact source/context text. Context bindings resolve unknown scope without changing raw IDs. Unique selectable-ID caps include retries; terminal admission errors do not retry. Opt-in SDK preflight/dispatch share reservations and preserve the first budget stop.
- Source-first output and separately labelled recomputation coexist.
  Dependencies use calculated values; primary answer slots use display values.
- Each formula input records variable/source ID/kind, executed value/unit and validated metadata.
  Candidate/direct-dependency rows keep physical/context evidence; derived inputs reference prior results.
  Arithmetic lineage dedupes leaf IDs/rows/anchors, excluding display/compatibility witnesses; input summaries use calculated values/resolved periods.
- Calendar labels precede fiscal columns, then row-relative labels/roles; raw labels stay provenance. Ambiguous/unanchored fiscal columns cannot fall back to row-relative text; unbound parser focus/labels
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

No role classifier, cross-encoder, metric-specific runtime branch, source-store
mutation or global tolerance/faithfulness relaxation. Reviewed dataset revisions are opt-in; MAS/Streamlit remain experimental.

## Local acceptance

Current compiler failure-capture repair, Python 3.13.13: full suite `1168 / 1168` (43.096s), new SDK/CLI regression tests `7 / 7`, focused capture/admission/selection `37 / 37`, comparison/import/topology/docs `33 / 33`. Terminal admission errors produce a failed artifact with unchanged completed cases and raw responses from the interrupted, unexecuted case. Safe HTTP/RPC codes exclude private messages; unknown totals remain null and usage/cost is labelled completed-response-only. No later case/model or automatic retry runs. Normal result shape and earlier program/output/evidence bytes remain intact. Previous abstention/narrative repairs and their 4/4 captured-response replay remain valid; no new provider/store activity or model-quality result.
Runtime domain audit passes (`84` reviewed literals); docs/import/topology `24 / 24`, pycompile and `git diff --check` pass.

- Tests inject failures into actual lower file writes, check same-process and
  restart recovery, and prove no context/embedding calls during sidecar repair.
- Actual graph-node tests check declared phase keys, unchanged inputs, and exact
  public answer/structured-result/trace agreement with the final ledger artifact.
- Reviewed-fixture v2 passes `5 / 5` with NAV's corrected 십억원 source unit and
  independent absolute-amount/display/input checks. Common-scale error control fails
  despite unchanged growth. Related tests `51 / 51`; replay receipts match twice, calls/writes 0.
  Exact saved replay stays `3 / 5`: KB's explained version mismatch remains correctly rejected, not a fresh numeric failure.
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

`tests/fixtures/reviewed_runtime_replay_corpus_v2.json` is the active five-question fixture
outside the three-question inventory: `KBF_T1_017`, `KBF_T2_018`, `LGE_T1_051`, `NAV_T2_006`, and `CEL_T1_013`.
Raw values, source excerpts, receipt/row/table provenance, owner visibility, and
programs go through the real normalizer, validator, `CompilationEnvelopeV2`, and executor.

V2 corrects NAV's `2,546.6 / 1,801.1` from 억원 to 십억원 and preserves exact adjacent
unit/table bytes. Direct amounts normalize to `2,546,600,000,000 / 1,801,100,000,000` 원;
source growth stays 41.4%. Programs, selections, narrative and other cases are unchanged.
V1/old receipts remain frozen; all seven test consumers use v2. Receipt `48634f5c...0f9f`.
[Current evidence matrix](../evaluation/reviewed_case_evidence_status.md) separates source review, replay and provider claims. The exhausted admission `0395ef99...adba` on clean `5ca495e4` stopped after 33.088s: two API responses, then `ServerError` on KB's second island; NAV/CEL uncalled, no semantic retry requests observed. Budget accounting USD 0.04766 known usage estimate + 0.121105 failed-request reserve = 0.168765 / 0.90, not billing or a cap denial. Its pre-repair outer handler dropped prior case/raw-response records, so actual answers cannot be reviewed or replayed. [Immutable failure report](../../benchmarks/results/abstention_narrative_compiler_admission_2026-09-09/RESULT.md), result SHA `b872724b...b2db`; originals 50/predecessors 67 and frozen inputs remain unchanged. [Current provider-free repair](../../benchmarks/results/compiler_partial_result_capture_repair_2026-09-09/REPORT.md) closes that terminal-error capture seam but cannot recover old responses. The [current-build four-case successor](../../benchmarks/results/compiler_partial_capture_admission_2026-09-09/README.md) is the next gate: fixed inputs/order/model/budgets, no-call SDK checks and partial-result failure rehearsal before separate manifest/cost approval. Preparation status and exact hashes live in that local packet; no new paid run or current full-agent/generalization/quality/release result is established.

## Provider status and next gate

The historical source-consistent release gate reached `3 / 3 PASS`; immutable T3/Samsung
artifacts and the one approved `HYU_T2_010` run provide its evidence. T2 selected
`87.0만 대`, `78.1만 대`, and source display `11.5%`, retaining `11.4%` as the
labelled recalculation. Both obligations completed with runtime error `0`, ledger
`ok`, and faithfulness/completeness `1.0 / 1.0`.

That admission is exhausted; timing, usage, cost and provenance remain in experiment history.

Earlier four-case comparison: Flash `3/4`, Pro `4/4`; details remain in experiment history.

Earlier five-case Pro-only admission `dd8e92f1...42f1` ran once on clean `bd6bd49`: all five reviewed
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
Result: `benchmarks/results/reviewed_full_agent_kbf_2026-09-07/kb-2023/results.json`; then-current exact replay 2/2, not current catalog compatibility.
Count-unit repair excludes word prefixes, retains grammatical suffixes and rejects unsupported real counts.
Evaluator-only replay is 2/2: `benchmarks/results/kbf_count_unit_boundary_replay_2026-09-07/summary.json`.
Answers/evidence/programs/dataset unchanged; calls 0. Approval exhausted; judges unmeasured, no new release claim.
Immutable LG/NAV v1 predecessors retain 2,620 OpenAI vectors, 125 parents and 2,099 payloads; their earlier v1 readiness/dense pass is historical, not current v2 readiness. Earlier live 0/2 and local repair evidence remain in experiment history.
Successor `03f03d99...237e` ran once on clean `5fe3a5f`: required-output completion 2/2, final validation ready/execution ok, errors 0, ledgers ok. 8 Gemini + 19 OpenAI calls, 116.909s; usage-estimated USD 0.17174414 < 0.40, billing unobserved. One allowed LG compiler retry; API failures/run retries 0.
LG completes 3/3 outputs, preserving original bindings/assertion: precise profit minus approximate 6,769억원 = 1,486,334,000,000원. Numeric FAIL remains: no atomic accepted source/scope/precision variant; do not treat it as a transport or arithmetic failure.
NAV completes 2/2 outputs without retry: same-row 당기/전기 resolve to 2023/2022, calculation 41.39574110852439%, source display 41.4%. Its new narrative only describes Poshmark service positioning, not acquisition performance; heuristic completeness 0.625, judges unmeasured. An out-of-island missing-ID diagnostic remains in attempt history, not final validation.
Socket-blocked exact replay 2/2; runtime/input/store hashes unchanged. Review SHA `66d5b927...a051`. Approval exhausted; no runtime/evaluator/dataset edit or paid rerun. `benchmarks/results/reviewed_full_agent_lge_nav_period_context_2026-09-07/README.md`.
Approved v2 build `ac0a3ea7...2c89` and paid admission `2724f2ed...4432` are exhausted. Frozen stores: 783/1,872 vectors, 2,127 payloads and 125 parents, readiness 2/2, degraded false. The LG → NAV run on `90aacc9` (runtime `bb8eba2`) completed 2/2, errors 0, ledgers ok: 8 Gemini + 19 OpenAI requests, one allowed NAV compiler retry, 115.265s, estimated USD 0.19107573 / 0.40 (billing unobserved). LG uses precise profit/AMPC and computes 1,486,360백만원; its original atomic FAIL remains frozen. NAV retains 41.4% source display and Poshmark performance evidence; judges are unmeasured. Dependency-provenance repair preserves both saved programs, values, physical evidence and ledger agreement. Separately reviewed LG evaluation v2 now requires resolved 2023, exact filing/source-row/header identity and consolidated scope; it admits both note-only and summary-plus-note precise tuples. Frozen/current LG answers both replay as old-contract FAIL and explicit-successor numeric PASS; 16 source-mutation controls fail. Default datasets/profiles, prior verdicts and source stores remain unchanged, and no provider ran. Receipt `6c961c96...1c8e`; [source review and successor](../evaluation/lge_t1_051_calculation_source_review_v2.md). Next LG admission must explicitly use `benchmarks/datasets/reviewed/lge_t1_051_calculation_v2.json` (SHA `c3f9bb83...1150`); no new paid run is needed to verify this contract repair. Celltrion readiness/runtime evidence is recorded below; wider quality/release acceptance remains separate.

Celltrion successor `685b575e...e71fa` ran once on clean `e5f28998` (runtime `5f2e86b1`): **runtime 1/1, numeric PASS, errors 0, ledger ok**. Consolidated 2023 cells `181,624,107천원 / 342,736,271천원` yield **52.99%** from the same physical table; one derived output, two inputs. Flash 2 + Pro 1 + OpenAI 10, no retries, 40.283s, usage-estimated USD 0.04296883 / 0.20 (billing unobserved). Socket-blocked post-run validation/execution outputs are byte-identical; original store and inputs are unchanged. Review `940c972b...526e`; [result and audit](../../benchmarks/results/reviewed_full_agent_celltrion_fiscal_2026-09-08/README.md). Approval exhausted; earlier failed run is preserved. [Five-case consolidation](../evaluation/reviewed_case_evidence_status.md) is complete: NAV fixture correction is complete in v2 without runtime changes; KB catalog mismatch is explained by intentional source/identity/unit changes. Current KB compiler-only selection now passes separately, without admitting old catalog authority. No synchronized five-case current full-agent result exists; unseen-question coverage, judges/release quality, default KB 2022 and formula-wide rounding propagation remain separate.

See [runtime contract](../architecture/agent_runtime_contract.md), [checked topology](runtime_flow_roles.md), and [experiment history](../history/experiment_history.md).
