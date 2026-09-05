# Project Status

Last updated: 2026-09-05

## Current implementation

The product is the single-agent `FinancialAgent`, on
`codex/bounded-semantic-tiebreaker`. Contract repairs start from `5e13bc6`.
Public HTTP fields, `FinancialRunResultV1`, candidate identity inputs, catalog
fingerprints, parser table structure, and stored formats remain compatible.

The implemented boundaries are:

- Shared unit scales and source-preserving numeric display; canonical
  KRW/USD/PERCENT/COUNT, signed composite amounts, USD lookups, and finite-value
  checks use one normalizer contract.
- Planner unit errors block only affected islands. Compiler format retries keep
  candidates; explicit candidate conflicts carry exact replacement ownership.
- `CompilationEnvelopeV2` checks full execution content before revalidation or
  arithmetic. Existing visibility/program/validation checks remain independent.
- Bundle-first selection retains adjacent source values and counts the actual
  query-wide unique selectable IDs, including retry replacement.
- Source-first output and separately labelled recomputation coexist.
  Dependencies use calculated values; primary answer slots use display values.
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

Python 3.13 is the verification interpreter.

- Numeric/compiler independent snapshot: full unittest `837 / 837`.
- Persistence/API independent snapshot: focused + import/topology/docs `79 / 79`.
- Final integrated source: full unittest `874 / 874`.
- Runtime domain audit: pass, `84` reviewed literals.
- Import/topology, pycompile, and `git diff --check`: pass.
- Tests inject failures into actual lower file writes, check same-process and
  restart recovery, and prove no context/embedding calls during sidecar repair.
- Actual graph-node tests check declared phase keys, unchanged inputs, and exact
  public answer/structured-result/trace agreement with the final ledger artifact.
- The graph-rebuild manifest seam passes 59/59 Python 3.13 adjacent tests,
  runtime domain audit, pycompile, topology/import coverage, and diff checks.

New local outputs under `benchmarks/results/` are not committed.

## Read-only saved-case replay

`src.ops.replay_runtime_contract_cases` reads immutable result and source JSON
without constructing a provider, vector store, agent, or benchmark runner.
All three complete catalog IDs/fingerprints verify; original input SHA-256 values
are unchanged after replay.

| Case | Provider-free result | Claim limit |
| --- | --- | --- |
| T2 | `11.5% (재계산값 11.4%)`; calculated value `11.395646606914212` | A copy explicitly selects the already-visible source display |
| T3 | `26%`, `700,691백만원`, and the existing four-value narrative | Saved program bytes, physical rows, and evidence remain unchanged |
| Samsung | `28,352,769백만원` plus the existing narrative | A copy restores the recorded first binding and first-attempt authority |

Both modified programs are labelled counterfactual. These checks prove
validator/executor/display behavior, not that a new LLM will select the same
program. Receipt: `benchmarks/results/runtime_contract_provider_free_replay_2026-09-05/replay_final.json`.
Synthetic actual-node tests separately verify ledger integrity; the replay is
not an evaluator or release run.

## Provider status and next gate

Release remains `HOLD`. Admission `45ef0f6e...4f03` ran exactly once on commit
`8410691`. Follow-up admission `da9cd31e...0acf` ran exactly once on commit
`e3ee77f`, targeting only the two rows that had failed on provider capacity.
Neither run used automatic runner retry, fresh ingest, document embedding, or
source mutation.

- `HYU_T3_072` passed with `26%` and `700,691백만원` from table 82 row `9:2`,
  the four Motional values from table 90 row `21:4`, no BHAF `53%`, runtime
  error `0`, and ledger `ok`. The follow-up binds this immutable same-runtime
  result instead of paying to rerun it.
- `SAM_T2_078` passed on the follow-up with both obligations complete. It chose
  `cand_27da082cf5bcd0cb9f27`, rendered `28,352,769백만원`, synthesized its
  two-source Harman narrative, recorded runtime error `0`, and kept ledger,
  faithfulness, completeness, grounded rendering, and calculation all `ok`/`1.0`.
- `HYU_T2_010` again stopped on Google query-embedding
  `429 RESOURCE_EXHAUSTED`, after planning but before compiler output. Its
  source-display contract therefore remains provider-unverified.

The follow-up's accounted successful Samsung trace reports 6 LLM calls, 41,405
tokens, 10 query-embedding calls, and USD `0.0448187` non-embedding runtime
cost. Calls made before the T2 exception and embedding pricing are absent, so
exact total cost is unavailable. The immutable source result/SQLite hashes and
complete store fingerprints are unchanged, and no disposable store remains.
Its root result SHA-256 is `d30a321c...422fd`; ignored run receipt SHA-256 is
`0fefdb88...9ac27`.

The combined same-runtime question gate remains `2 / 3`, with T3 carried
forward by exact artifact hashes. The two Google eval admissions are consumed.
Admission `10c8ca9c...2786` was then consumed once on `36fcf62` for only the
side-by-side Hyundai OpenAI `text-embedding-3-large` store rebuild. All 28
document batches completed with HTTP 200, external search health passed, and
the post-health manifest makes the 1,764-vector store strictly `compatible`.
The rebuilt source projection (chunks, metadata, parents) has exact SHA-256
`e3cb6060...ad7f` on both stores; the immutable Google source fingerprint stays
`5cdc0e8f...0ff6`. The USD `0.25071982` local-tokenizer estimate is below the
approved USD `0.30` ceiling, while actual provider billing remains unavailable.
Run receipt SHA-256 is `6fa0c805...d4719`; no automatic retry occurred. This
approval is exhausted. A new exact admission is required for a Hyundai T2-only
store-fixed eval against the OpenAI store.

Deferred: formula-wide rounding-error propagation and separate T3 dataset/
evaluator governance. Existing answer keys, tolerances, and faithfulness policy
are unchanged.

See [runtime contract](../architecture/agent_runtime_contract.md),
[checked topology](runtime_flow_roles.md), and
[experiment history](../history/experiment_history.md).
