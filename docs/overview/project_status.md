# Project Status

Last updated: 2026-09-06

## Current implementation

The product is the single-agent `FinancialAgent`, on `main`. The verified
`codex/bounded-semantic-tiebreaker` source was fast-forwarded locally at
`f46e331`. Contract repairs start from `5e13bc6`; the latest planner
dependency-boundary fix is `af9a07e`.
Public HTTP fields, `FinancialRunResultV1`, candidate identity inputs, catalog
fingerprints, parser table structure, and stored formats remain compatible.

The implemented boundaries are:

- Shared unit scales and source-preserving numeric display; canonical
  KRW/USD/PERCENT/COUNT, signed composite amounts, USD lookups, and finite-value
  checks use one normalizer contract.
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

Python 3.13.13 is the verification interpreter. Current focused gates pass:
semantic `166 / 166`, replay `9 / 9`, and import/topology `22 / 22`.
Runtime domain audit passes with `84` reviewed literals; pycompile and
`git diff --check` also pass. Full unittest discovery passes `893 / 893`.

- Tests inject failures into actual lower file writes, check same-process and
  restart recovery, and prove no context/embedding calls during sidecar repair.
- Actual graph-node tests check declared phase keys, unchanged inputs, and exact
  public answer/structured-result/trace agreement with the final ledger artifact.
- The reviewed real-question corpus passes `5 / 5` cases twice with
  byte-identical receipts. Its three contract tests prove deterministic replay,
  fail-closed requirement visibility, and raw-value normalization rather than
  trusting copied normalized fields.

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

`tests/fixtures/reviewed_runtime_replay_corpus_v1.json` adds five distinct real
questions not present in the exact current-schema trace inventory:
`KBF_T1_017`, `KBF_T2_018`, `LGE_T1_051`, `NAV_T2_006`, and `CEL_T1_013`.
The fixture preserves reviewed raw values, source excerpts, receipt/row/table
provenance, owner visibility, and current structured programs. The replay uses
the real unit normalizer and then the current validator,
`CompilationEnvelopeV2`, and executor.

All 5/5 cases pass. Two independently written receipts have the same SHA-256,
`fc5303358b0236675f2a3aca1444b010e18e97444968160127d652900a47304f`.
There are zero provider, compiler, retrieval, or store-write calls. Four cases
project historical filing-linked runtime selections into compact reviewed
fixtures; the Celltrion case uses the manually verified curated-dataset filing
evidence. Therefore this is downstream contract and numeric generalization
evidence, not exact candidate-catalog replay and not evidence that a fresh
compiler will select the same sources.

## Provider status and next gate

The source-consistent release gate remains `3 / 3 PASS`; immutable T3/Samsung
artifacts and the one approved `HYU_T2_010` run provide its evidence. T2 selected
`87.0만 대`, `78.1만 대`, and source display `11.5%`, retaining `11.4%` as the
labelled recalculation. Both obligations completed with runtime error `0`, ledger
`ok`, and faithfulness/completeness `1.0 / 1.0`.

That run made no fetch, ingest, document embedding, store mutation, or runner
retry. Its admission is exhausted. Exact timing, usage, cost estimate, store and
result hashes remain in experiment history rather than this current snapshot.

Compiler-only admission `ef95dc95...f016` was consumed once. KBF T1 passed. KBF
T2 selected both reviewed signed values and the reviewed narrative, but compiled
`((current-prior)/abs(prior))*100`; execution therefore returned `-70.28%`
instead of reviewed magnitude growth `+70.28%`. Structural validation was ready
and execution was error-free, so no retry occurred. The gate stopped before LGE,
NAVER, and Celltrion as specified. Usage was 2 calls / 18,205 tokens with an
estimated USD `0.0143671`, below the USD `0.12` cap. This is a compiler formula-
semantics gap, not candidate visibility or arithmetic failure. The approval is
exhausted; a provider-free successor must precede any new manifest.

Deferred: formula-wide rounding-error propagation. T3 dataset/evaluator
governance completed on 2026-09-03; runtime and dataset ownership remain
separate, and tolerances and faithfulness policy are unchanged.

See [runtime contract](../architecture/agent_runtime_contract.md),
[checked topology](runtime_flow_roles.md), and
[experiment history](../history/experiment_history.md).
