# Project Status

Last updated: 2026-09-02

## At a glance

| Question | Current answer |
| --- | --- |
| Product | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Active branch | `codex/runtime-contract-integration` from clean redesign `8790f92` |
| Runtime state | Boundary redesign and the preserved predecessor changes are integrated in a clean worktree |
| Public result | `FinancialRunResultV1`; review/debug are opt-in and the HTTP answer wire shape is unchanged |
| Store readiness | Approved manifest written; exact manifest check is `compatible`, `ready=true`, `degraded=false` |
| Provider evidence | Not refreshed; no call, paid run, fresh ingest, or embedding was performed in this integration |
| Release status | Local source and manifest gates pass; release remains withheld until the exact store-fixed eval-only admission is separately approved and executed |

## Current boundaries

- `FinancialAgentStateV2` has one top-level writer for each phase. Intermediate
  nodes do not mutate the task/artifact ledger or final answer.
- Compiler, validator, and executor share one immutable visibility envelope.
  Catalog or validation drift fails before execution.
- Numeric compilation is isolated by declared dependency and non-empty coupling
  key. Unknown dependency, self-dependency, cycle, island overflow, or candidate
  reservation overflow fails before compiler calls.
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

The source-change gate is focused tests, runtime-domain audit, import/topology
checks, full unittest discovery, pycompile, and `git diff --check`. It currently
passes: 751 total unittest cases, 124 focused evaluator/provenance cases, 30
benchmark-runner cases, 50 focused authority/import/topology/service cases, and
86 reviewed domain literals. Historical benchmark scores and bundles are not
evidence for this integrated runtime build.

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

A new ignored three-row admission binds the current runtime and the ordered
scope `HYU_T2_010`, `HYU_T3_072`, `SAM_T2_078`. Its manifest SHA-256 is
`cb188492de5b51ee3b42cf5cf9aaf6c12192d92567c001a0426c4e6e785683a8`.
Two production-order no-call processes produced byte-identical 5,640-byte
receipts at
`d63ae5e34e939b68f03f4bc69b897af2f2b755c47039e4a4873352d1117105b3`,
with provider/network/output counts all zero and source/target/temp invariants
intact. The latest same-scope runner estimate is USD `0.1442999`, excluding
embedding pricing; the proposed one-run ceiling is USD `0.40`.

## Next work

1. Approve or decline the exact admission manifest
   `cb188492...683a8`, one-run scope, and USD `0.40` ceiling. Rehearsal and
   compatibility do not authorize provider dispatch.
2. If approved, rerun the no-call rehearsal immediately before dispatch and
   require the same hashes, then execute once with the 30-second heartbeat.
3. Preserve the artifacts and stop without a paid retry unless all three rows
   meet runtime completeness, runtime error `0`, and ledger `ok`; then review or
   merge `codex/runtime-contract-integration`.

See [runtime_flow_roles.md](runtime_flow_roles.md) for the checked topology,
[agent_runtime_contract.md](../architecture/agent_runtime_contract.md) for the
normative contract, and the history documents for superseded implementation and
experiment detail.
