# Current Handoff Context

Last updated: 2026-09-02

## Checkout

- Implementation worktree: `C:\Users\geonj\Desktop\dart-rag-agent-runtime-redesign`
- Branch: `codex/runtime-contract-boundary-redesign`
- Immutable base: `a278c1a`
- The original dirty checkout at `C:\Users\geonj\Desktop\dart-rag-agent` was not
  edited, cleaned, staged, or used as an output directory.

## Current implementation

The redesign is implemented as ordered commits:

1. `ea45baf`: immutable candidate visibility and compile/execution drift gates.
2. `608c233`: phase-owned `FinancialAgentStateV2` and single ledger writer.
3. `cf37596`: dependency/coupling compilation islands and bounded retry.
4. `e7cc30b`: retrieval, ingest, store-manifest, API, and routing-cache boundaries.
5. Final change: public `FinancialRunResultV1`, concise normative docs,
   generated topology, semantic-test split, and source-defined narrative
   evidence-cap preservation.
6. Documentation follow-up: authority-first navigation, a bounded fast
   development loop, and explicit historical labels for retired work queues and
   gate logs.

The product path is the single-agent `FinancialAgent`. MAS, Streamlit, benchmark,
evaluator, replay, and promotion tools remain optional or experimental.

## Hard boundaries

- No candidate IDs, catalog fingerprints, datasets, answer keys, evaluator
  tolerances, or historical result bundles are rewritten.
- No existing store receives a manifest automatically. The adoption CLI is
  dry-run unless `--write-manifest` is explicitly supplied after separate review.
- No provider call, paid evaluation, fresh ingest, automatic benchmark retry, or
  document embedding is authorized by this implementation task.
- The current `data/chroma_dart` store remains an immutable predecessor and is
  expected to be unready until separately validated and approved for adoption.

## Verification authority

Current source and tests are authoritative. Stable rules are in
[agent_runtime_contract.md](docs/architecture/agent_runtime_contract.md), live
topology is in [runtime_flow_roles.md](docs/overview/runtime_flow_roles.md), and
historical evidence remains in [implementation_history.md](docs/history/implementation_history.md)
and [experiment_history.md](docs/history/experiment_history.md).

The completed local source gate is 699 unittest cases, 116 split semantic
program cases, 86 reviewed runtime-domain literals, 32 import/DAG/topology
cases, topology source check, pycompile, and `git diff --check`. A read-only,
network-blocked reprojection of the three stored source windows preserved source
hashes and confirmed the expected T2, T3, and Samsung candidate boundaries.

Provider validation remains a separate final gate. It may run once, store-fixed
and eval-only with a 30-second heartbeat, only after a new manifest hash and cost
estimate receive explicit approval.
