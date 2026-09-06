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
  checks use one normalizer contract. Compiler emits formula/display intent only;
  code infers dimensions. Legacy `result_unit` has no validation/render authority.
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
`git diff --check` also pass. Full unittest discovery passes `929 / 929`.

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

Latest compiler-only admission `9d1f74a4...1d6a` ran once on clean `14628e0`, after
two byte-identical no-call receipts. KBF T1 passed in one call with `1.83%`, `1.73%`,
and `0.10%p`. KBF T2 failed the numeric review gate; LGE/NAV/CEL were not called.
Both responses ended `STOP` and parsed. Both programs passed structural validation
and execution with zero runtime errors and the reviewed candidate IDs.

KBF T2 preserved `(3,146,409)` and `(1,847,775)` million KRW, but the compiler chose
`((current-prior)/abs(prior))*100`, yielding `-70.28%` rather than reviewed magnitude
growth `+70.28%`. Its rationale describes an absolute cost increase, inconsistent with
that signed numerator. This is a semantic formula-selection failure, not unit parsing
or input loss. Structural validity triggered no internal retry; the dependency-input
repair therefore remains provider-free verified, not exercised in this paid run.

The captured programs, checks, and prompt hashes reproduce exactly provider-free.
Usage: 2 calls, 15,059 input (0 cached), 897 answer and 1,863 thinking tokens,
17,819 total in 19.38s; estimated USD `0.0114177`, not actual billing. Retrieval,
planner, evaluator, embedding, and store calls are zero. Result SHA `8c4b28b6...f371`.
Corpus, admission, rehearsals, and predecessor artifacts remain unchanged.

Approval exhausted; no runtime patch or paid rerun followed. Next isolate comparison semantics provider-free;
do not auto-flip negatives or relax review tolerances. Gate v2 capture and `4096/1024` budgets are unchanged.

Deferred: formula-wide rounding-error propagation. T3 dataset/evaluator
governance completed on 2026-09-03; runtime and dataset ownership remain
separate, and tolerances and faithfulness policy are unchanged.

See [runtime contract](../architecture/agent_runtime_contract.md), [checked topology](runtime_flow_roles.md), and
[experiment history](../history/experiment_history.md).
