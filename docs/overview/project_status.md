# Project Status

Last updated: 2026-09-05

## Current implementation

The product is the single-agent `FinancialAgent`, on
`codex/bounded-semantic-tiebreaker`. Contract repairs start from `5e13bc6`; the
latest planner dependency-boundary fix is `af9a07e`.
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
- Final integrated source before provider replay: full unittest `874 / 874`.
- Planner dependency successor: planner `5 / 5`, semantic contracts `164 / 164`,
  import/topology `28 / 28`, full unittest `878 / 878`.
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

Release remains `HOLD`. Immutable `HYU_T3_072` and `SAM_T2_078` successes remain
the carried evidence, so the combined same-runtime gate is `2 / 3`.

Admission `640ef7be...986c` was consumed exactly once on clean commit `145982f`
for OpenAI-store-fixed `HYU_T2_010`. All 11 query embeddings completed without
the prior Google capacity error. There was no fresh fetch, parse, ingest,
document embedding, source mutation, or automatic runner retry. Optional-null
normalization worked: narrative `ob_002` compiled once, selected
`cand_bbd863eb396fa724d814`, and completed without retry.

Numeric `ob_001` was blocked before compilation because the planner put its own
raw evidence IDs `us_sales_2023` and `us_sales_2022` into `depends_on`. Evidence
requirements were then assigned stable IDs, leaving those raw names as unknown
answer-obligation dependencies. Island preflight therefore made zero provider
calls and serialized zero prompt bytes for the numeric island. Visible numeric
candidates were present, so this is a planner dependency-projection defect, not
retrieval, ranking, embedding, compiler, or executor evidence.

The process exited zero in `79.721s`; runtime error is `0`, ledger is `ok`, and
completeness/faithfulness are `0.5 / 0.0`. Usage is 5 LLM calls / 26,782 tokens
and 11 query / 0 document embedding calls. The recorded non-embedding estimate
is USD `0.0285496`; actual billing and embedding cost are unavailable. The source
store remained byte-identical at `6231cd8e...24e9`, no disposable store remains,
root result SHA-256 is `d86b650c...3040`, and ignored receipt SHA-256 is
`859a2483...021f`.

Commit `af9a07e` fixes the generic seam: planner projection removes only an exact
reference to the current obligation's evidence requirement, but preserves known
other answer dependencies and unknown/self references for fail-closed preflight.
Planner `5 / 5`, semantic contracts `164 / 164`, import/topology `28 / 28`, full
unittest `878 / 878`, runtime audit, pycompile, and diff checks pass. No provider
call followed the fix. The consumed admission cannot be reused; provider
confirmation requires a fresh clean-HEAD manifest and separate egress/cost
approval.

Deferred: formula-wide rounding-error propagation and separate T3 dataset/
evaluator governance. Existing answer keys, tolerances, and faithfulness policy
are unchanged.

See [runtime contract](../architecture/agent_runtime_contract.md),
[checked topology](runtime_flow_roles.md), and
[experiment history](../history/experiment_history.md).
