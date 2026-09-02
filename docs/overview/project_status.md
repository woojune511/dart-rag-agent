# Project Status

Last updated: 2026-09-02

## At a glance

| Question | Current answer |
| --- | --- |
| Product | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Active branch | `codex/runtime-contract-boundary-redesign` from `a278c1a` |
| Runtime state | Candidate authority, typed phase state, compilation islands, and service/store boundaries implemented locally |
| Public result | `FinancialRunResultV1`; review/debug are opt-in and the HTTP answer wire shape is unchanged |
| Store readiness | Exact `StoreManifestV1` match required; missing/mismatch is 503 unless explicit BM25-only degraded mode is configured |
| Provider evidence | Not refreshed; no call, paid run, fresh ingest, or embedding was performed in this redesign |
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
- MAS and Streamlit remain experimental consumers, not the product authority.

## Evidence and remaining gate

The source-change gate is focused tests, runtime-domain audit, import/topology
checks, full unittest discovery, pycompile, and `git diff --check`. It currently
passes: 699 total unittest cases, 116 semantic-program cases, 86 reviewed domain
literals, and 32 import/DAG/topology cases. Historical benchmark scores and
bundles are not evidence for this new runtime build.

A read-only reprojection rebuilt candidates from the three stored source
windows with network access blocked. It retained both Hyundai T2 period values
while excluding the two market totals, retained Motional 26% while excluding
both BHAF 53% candidates, and restored all three accepted Samsung evidence IDs;
the saved Samsung program validated `ready`. Source hashes did not change and no
result artifact was written.

After local completion, provider validation still requires a separate approval
covering the new manifest SHA and estimated cost. Only one store-fixed eval-only
run with a 30-second heartbeat is allowed; automatic retry and fresh ingest are
forbidden. T3 mixed-basis answer-key governance remains a separate dataset task.

## Next work

1. Integrate this clean redesign with the separately preserved dirty checkout in
   a third worktree. Do not mutate the original checkout; resolve the four known
   overlapping paths explicitly.
2. Rerun focused, import/topology, full unittest, pycompile, and diff gates on the
   integrated tree before changing store state.
3. Run the store-manifest adoption CLI in dry-run mode. Any manifest write and
   the one provider-backed eval-only run remain separate approval decisions.

See [runtime_flow_roles.md](runtime_flow_roles.md) for the checked topology,
[agent_runtime_contract.md](../architecture/agent_runtime_contract.md) for the
normative contract, and the history documents for superseded implementation and
experiment detail.
