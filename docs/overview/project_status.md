# Project Status

Last updated: 2026-09-06

## Current implementation

The product is the single-agent `FinancialAgent`. The current working branch is
`codex/reviewed-compiler-selection-gate`, with compiler-gate baseline `e9a5be0`.
Contract repairs start from `5e13bc6`; the dependency-boundary fix is `af9a07e`.
Public HTTP fields, `FinancialRunResultV1`, candidate identity inputs, catalog
fingerprints, parser table structure, and stored formats remain compatible.

The implemented boundaries are:

- Shared unit scales and source-preserving numeric display; canonical
  KRW/USD/PERCENT/COUNT, signed composite amounts, USD lookups, and finite-value
  checks use one normalizer contract.
- Compiler sign interpretation uses the existing formula AST and `rationale`.
  Raw signs stay intact; negative operands do not mandate `abs()` and growth
  need not be positive. No sign enum, arithmetic rewrite, or validator relaxation
  was added. Undefined ratios and ambiguous comparisons can remain unanswered.
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

Python 3.13.13 is the verification interpreter. Focused usage/response-capture/
reviewed replay gates pass `25 / 25`; import/topology passes `22 / 22`.
Runtime domain audit passes with `84` reviewed literals; pycompile and
`git diff --check` also pass. Full unittest discovery passes `915 / 915`.

- Tests inject failures into actual lower file writes, check same-process and
  restart recovery, and prove no context/embedding calls during sidecar repair.
- Actual graph-node tests check declared phase keys, unchanged inputs, and exact
  public answer/structured-result/trace agreement with the final ledger artifact.
- The reviewed real-question corpus passes `5 / 5` cases twice with
  byte-identical receipts. Its three contract tests prove deterministic replay,
  fail-closed requirement visibility, and raw-value normalization rather than
  trusting copied normalized fields.
- Sign tests cover negative magnitude increase/decrease, signed changes,
  differing conventions across sign transitions, and zero denominators versus
  valid absolute differences. Stubbed compiler choices test prompt wiring and
  execution only; no provider improvement is established by these tests.
- Installed Gemini/LangChain adapters run with a fake client and external sockets
  blocked. Tests distinguish `MAX_TOKENS` from `STOP`/missing fields, preserve
  successful and failed responses across retry, exclude private metadata, and
  verify worker-thread token totals without making a provider request.

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

That run made no fetch, ingest, document embedding, store mutation, or runner
retry. Its admission is exhausted. Exact timing, usage, cost estimate, store and
result hashes remain in experiment history rather than this current snapshot.

Latest compiler-only admission `66af6f4d...3eef` ran once on clean `88e1760`, after
two byte-identical no-call receipts. KBF T1 failed after its one internal retry;
the other four questions were not dispatched. Both responses ended `STOP` and
parsed successfully, so this failure is not output truncation.
The first selected the correct `1.83%`/`1.73%` candidates and subtraction, but
unsupported result unit `PERCENT_POINT` triggered `result_unit_mismatch`.
The targeted retry exposed only the 2023 candidate, without the accepted upstream
dependency results. It returned missing `nim_change`; two direct outputs survived,
but validation/execution are partial. Provider-free replay matches both recorded
prompt hashes and the final program. No formula or validation change was made.

Usage: 2 calls, 10,773 input (2,908 cached), 572 answer and 1,822 thinking tokens,
13,167 total; estimated USD `0.0092169` against USD `0.20`, not actual billing.
Retrieval/planner/evaluator/embedding/store calls are zero. Result SHA is
`7d415ab4...a766`; corpus and predecessor artifacts remain unchanged.

Gate v2 preserves pre-parser final text (not wire bytes), finish reasons, parse
errors, and disjoint usage; no thought content/signatures or credentials are saved.
It binds output `4096` / thinking `1024`; thinking is guidance within the total cap.
Approval exhausted. Next fix unit vocabulary and retry dependency context provider-free,
preserving accepted outputs and strict validation. New paid runs need separate approval.

Deferred: formula-wide rounding-error propagation. T3 dataset/evaluator
governance completed on 2026-09-03; runtime and dataset ownership remain
separate, and tolerances and faithfulness policy are unchanged.

See [runtime contract](../architecture/agent_runtime_contract.md),
[checked topology](runtime_flow_roles.md), and
[experiment history](../history/experiment_history.md).
