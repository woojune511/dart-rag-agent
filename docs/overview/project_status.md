# Project Status

Last updated: 2026-09-02

## At a glance

| Question | Current answer |
| --- | --- |
| Product | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Active branch | `codex/runtime-contract-integration` from clean redesign `8790f92` |
| Runtime state | Boundary redesign and the preserved predecessor changes are integrated in a clean worktree |
| Public result | `FinancialRunResultV1`; review/debug are opt-in and the HTTP answer wire shape is unchanged |
| Store readiness | Legacy store dry-run is compatible, but no manifest was written; missing/mismatch still returns 503 unless explicit BM25-only degraded mode is configured |
| Provider evidence | Not refreshed; no call, paid run, fresh ingest, or embedding was performed in this integration |
| Release status | Local source gates pass; release remains withheld until separately approved manifest adoption and store-fixed eval-only validation |

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

A dry-run against a temporary copy of `data/chroma_dart` found the expected
`dart_reports_v2` collection and dimension `3072`, with the canonical ingest
profile declared. The copy and original store remained byte-identical and no
manifest was written. Provider validation still requires a separate approval
covering a written manifest SHA and estimated cost. Only one store-fixed
eval-only run with a 30-second heartbeat is allowed; automatic retry and fresh
ingest are forbidden.

## Next work

1. Review or merge `codex/runtime-contract-integration`; the original dirty
   checkout remains the immutable predecessor.
2. If store adoption is desired, approve the manifest write separately and
   record the resulting manifest SHA. Compatibility alone is not authorization.
3. Prepare a new store-fixed eval-only manifest and cost estimate. The one
   provider-backed run remains a separate approval decision.

See [runtime_flow_roles.md](runtime_flow_roles.md) for the checked topology,
[agent_runtime_contract.md](../architecture/agent_runtime_contract.md) for the
normative contract, and the history documents for superseded implementation and
experiment detail.
