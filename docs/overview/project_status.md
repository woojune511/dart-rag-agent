# Project Status

Last updated: 2026-09-05

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
- Post-fast-forward integration recheck: Python 3.14.5 full unittest
  `878 / 878`; existing LangChain/Pydantic compatibility warnings only.
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

The defined source-consistent runtime release gate is `3 / 3 PASS`. Immutable
`HYU_T3_072` and `SAM_T2_078` successes are carried by exact artifact hashes;
the final row was confirmed by admission `0f0c0d52...0445`, consumed once on
clean commit `58551c7`.

OpenAI-store-fixed `HYU_T2_010` completed both obligations with runtime error `0`
and ledger `ok`. Numeric `ob_001` selected `87.0만 대`, `78.1만 대`, and source
display `11.5%`; it retained deterministic value `11.395646606914212` as the
labelled recalculation `11.4%`. Narrative `ob_002` selected
`cand_bbd863eb396fa724d814`. The final answer has faithfulness/completeness
`1.0 / 1.0`, four selected candidates, two outputs, and no missing obligation.

Both island preflights had zero errors, confirming `af9a07e`. The numeric island
used the permitted one internal retry to correct source-assertion structure while
keeping the same cohort; the narrative island and runner process were not
retried. There was no fresh fetch, parse, ingest, document embedding, or source
mutation.

The process exited zero in `118.936s`, with 7 total LLM calls / 71,359 tokens and
11 query / 0 document embedding calls. Recorded non-embedding cost is USD
`0.0664263`; actual billing and embedding cost are unavailable. Source store is
unchanged at `6231cd8e...24e9`, no disposable store remains, root result SHA-256
is `a765a132...0ad9`, and ignored receipt SHA-256 is `4dd004f2...a3b4`.

`numeric_final_judgement=null` is N/A for this mixed question and is not a
runtime failure because numeric execution, faithfulness, completeness, retrieval,
error rate, and ledger are healthy. The admission is exhausted; no further
provider retry is authorized or needed for this release gate.

Deferred: formula-wide rounding-error propagation and separate T3 dataset/
evaluator governance. Existing answer keys, tolerances, and faithfulness policy
are unchanged.

See [runtime contract](../architecture/agent_runtime_contract.md),
[checked topology](runtime_flow_roles.md), and
[experiment history](../history/experiment_history.md).
