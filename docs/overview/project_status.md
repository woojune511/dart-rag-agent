# Project Status

Last updated: 2026-09-03

## At a glance

| Question | Current answer |
| --- | --- |
| Product | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Active branch | `codex/typed-candidate-ranking`, successor of provider-gate snapshot `9641563` |
| Runtime state | Typed owner matching plus compiler-visible atomic physical-row selection replace additive keyword scoring and independent multi-output selection |
| Public result | `FinancialRunResultV1`; review/debug are opt-in and the HTTP answer wire shape is unchanged |
| Store readiness | Approved manifest written; exact manifest check is `compatible`, `ready=true`, `degraded=false` |
| Provider evidence | Evidence-bundle admission `b068ac4b...5501` was consumed once in a completed store-fixed three-question `eval-only` run; no fresh ingest or document embedding |
| Release status | **HOLD, 2/3 runtime-complete**; T3 rejects a mixed-row proposal and emits no unsupported answer |

## Current boundaries

- `FinancialAgentStateV2` has one top-level writer for each phase. Intermediate
  nodes do not mutate the task/artifact ledger or final answer.
- Compiler, validator, and executor share one immutable visibility envelope.
  Catalog or validation drift fails before execution.
- Each obligation or evidence requirement may carry a typed semantic target.
  Candidate admission compares scope, local subject, owner kind, unit, metric,
  and physical locality as separate factors; explicit conflicts are excluded
  and compatible candidates precede unknown-only candidates.
- The candidate catalog remains complete and stable. Cohort prompts contain
  cell-local structured text and one factor projection; they do not perform a
  second keyword ranking pass.
- Numeric compilation is isolated by declared dependency, non-empty coupling
  key, and inferred complete-row evidence bundles. A bundle adds an island edge
  even when planner coupling is empty. Code ranks complete rows from existing
  owner cohorts, selects one before compiler invocation, and removes alternative
  row IDs from output and requirement visibility. Numeric compatibility
  narratives remain available. Unknown dependency, self-dependency, cycle,
  island overflow, or candidate reservation overflow fails before compiler calls.
- Retrieval is internally split into plan, search, selection, and trace stages.
- `IngestService` owns fetch through manifest recording. `FinancialAgent` no
  longer exposes ingest methods.
- FastAPI dependencies live in lifespan-owned `AppServices`; sync query and ingest
  execute in a threadpool. Liveness and readiness are separate endpoints.
- Evaluator-only accepted calculation/answer variants require one complete,
  source-qualified atomic match. They do not alter runtime selection or promote
  qualitative scores.
- Benchmark `store-only` excludes question/evaluator work, while `eval-only`
  evaluates from a disposable store copy and preserves its source bytes.
- MAS and Streamlit remain experimental consumers, not the product authority.

## Evidence and remaining gate

The current provider-free source combines typed target matching, cell-local
prompts, complete-row bundle inference, and fail-closed validation. Complete
options use the existing per-owner ranks: lowest summed position, then lowest
worst position, then physical IDs. Only the selected row enters the compiler's
candidate dictionary and active constraint. Candidate rejection rebuilds the
cohorts so the next complete row can be promoted; format-only retry keeps the
same row. Ranked alternatives are diagnostic-only. The source gate passes 763
unittest cases, including 134 focused semantic/runtime-contract and 23
documentation/import/topology cases, plus the 86-literal domain audit,
pycompile, and `git diff --check`.

Read-only projection of the consumed T3 calculation plan selects table 82 row
`9:2`, reduces its visible IDs from 16 to 10, retains both numeric compatibility
cohorts and all five compatible source-defined narrative IDs, and removes the
table 83 numeric pair. This directly exercises the saved failure shape without
calling a provider or writing an artifact. The historical release status remains
HOLD until a separately approved successor run demonstrates runtime completeness.

The clean redesign predecessor's read-only reprojection rebuilt candidates from
the three stored source windows with network access blocked. It retained both
Hyundai T2 period values
while excluding the two market totals, retained Motional 26% while excluding
both BHAF 53% candidates, and restored all three accepted Samsung evidence IDs;
the saved Samsung program validated `ready`. Source hashes did not change and no
result artifact was written.

The three curated dataset slices now carry identical source-qualified
calculation variants for `LGE_T1_051`; their existing primary answer, tolerance,
operand, and result fields are unchanged. The HYU T3 source review records one
possible same-basis consolidated tuple but deliberately does not register it or
change the mixed-basis canonical key.

The approved adoption added only `data/chroma_dart/store_manifest.json`, SHA-256
`98ec5dcb6a376c490d3ced20c5ffe56c276a8f5e382d97dc18dcbe59d3920615`.
All seven predecessor store files remained byte-identical. The pure manifest
readiness check returns exact `compatible`, `ready=true`, and `degraded=false`;
no provider query was made.

The current ignored evidence-bundle admission preserves the ordered scope
`HYU_T2_010`, `HYU_T3_072`, `SAM_T2_078`. Its manifest SHA-256 is
`b068ac4b108d8243a417b61e355439ef1f25106c3b707db12ce0561015a45501`.
Two no-call processes plus the immediate pre-dispatch rehearsal produced the
same 6,710-byte receipt at
`98484f569246a4cc4af07b4e0070426a73aee9def2a4317b4011082593ecb191`,
with provider/network/output counts zero and source/target/temp invariants
intact.

The separately approved provider run executed exactly once in Hyundai-then-
Samsung order and completed in 313.9 seconds with exit code zero. The ignored
root result is
`benchmarks/results/evidence_bundle_focused_successor_envbound_2026-09-03/results.json`
(SHA-256
`e679e712d3e228a9e19d6ef4c52b64e649853d9f5a44a83ed700deac48fea6b2`).

| Question | Runtime result | Gate evidence |
| --- | --- | --- |
| `HYU_T2_010` | `ok`, 2/2 obligations | Predecessor evidence IDs are unchanged; `87.0만 대` and `78.1만 대` produce `11.4%`, with source display `11.5%`; error 0, ledger `ok` |
| `HYU_T3_072` | `incomplete`, 0/3 obligations | One retry proposed table 83 ownership plus table 82 carrying amount; `evidence_bundle_mismatch` rejected it and no output was emitted; error 0, ledger `ok` |
| `SAM_T2_078` | `ok`, 2/2 obligations | Predecessor evidence IDs are unchanged; `28,352,769백만원` and Harman narrative remain; error 0, ledger `ok` |

T3 had one inferred bundle, one compilation island, and two complete physical
options: table 82 row `9:2` (`26%`, `700,691백만원`) and table 83 row `9:2`
(`25.92%`, `907,061백만원`). The first compiler attempt selected only narrative
evidence and remained partial. The allowed retry selected the table 83 ownership
candidate and table 82 carrying-amount candidate despite the explicit option
map. The validator rejected it. This confirms that the remaining defect is not
parsing, visibility, island construction, or fail-closed validation; the
compiler interface still ranks owner IDs independently instead of making an
atomic bundle-option choice.

The run recorded 18 LLM calls, 166,963 LLM tokens, 32 query-embedding calls,
zero document-embedding calls, and estimated runtime cost USD `0.1645241`, below
the approved USD `0.40` ceiling. Embedding pricing remains unavailable. Source
result hashes, both store directory fingerprints, and both SQLite hashes remain
unchanged; no disposable store remains.

## Next work

1. Do not rerun the paid gate automatically. The current admission is consumed.
2. The provider-free source gate is complete. Preserve the consumed result as an
   immutable predecessor; any new provider admission must be generated from the
   committed successor and separately approved before replay.
3. Keep a broader local semantic reranker and persisted typed fact index as
   deferred designs. They need measured benefit and a migration contract rather
   than being bundled into the atomic-bundle repair.

See [runtime_flow_roles.md](runtime_flow_roles.md) for the checked topology,
[agent_runtime_contract.md](../architecture/agent_runtime_contract.md) for the
normative contract, and the history documents for superseded implementation and
experiment detail.
