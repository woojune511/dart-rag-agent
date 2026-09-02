# Current Handoff Context

Last updated: 2026-09-02

## Checkout

- Integration worktree: `C:\Users\geonj\Desktop\dart-rag-agent-runtime-integration`
- Branch: `codex/runtime-contract-integration`
- Immutable base: `a278c1a`
- Clean redesign predecessor: `8790f92`
- The original dirty checkout at `C:\Users\geonj\Desktop\dart-rag-agent` was not
  edited, cleaned, staged, or used as an output directory.

## Current implementation

The boundary redesign is implemented as ordered commits:

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

The separate dirty predecessor was then integrated explicitly:

1. `db67965`: exact-signature retrieval result caching only.
2. `2068203`: parser preservation of `십억원` table units.
3. `0a03b40`: FastAPI JSON request-body contract coverage on the lifespan-owned
   service path.
4. `14460f8`: source-qualified evaluator variants, strict multi-output matching,
   and the reviewed dataset/documentation additions.
5. `89ab496`: explicit store-only and immutable-source eval-only benchmark modes.
6. `ff7f94b`: non-mutating SQLite inspection for legacy-store manifest dry-runs.

The product path is the single-agent `FinancialAgent`. MAS, Streamlit, benchmark,
evaluator, replay, and promotion tools remain optional or experimental.

## Hard boundaries

- No candidate IDs, catalog fingerprints, primary answer keys, evaluator
  tolerances, or historical result bundles are rewritten. The three curated
  dataset slices add the same source-qualified calculation variants only to
  `LGE_T1_051`; `HYU_T3_072` remains review-only and is not registered.
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

The completed integration source gate is 751 unittest cases, 124 focused
evaluator/provenance cases, 30 benchmark-runner cases, 50 focused
authority/import/topology/service cases, 86 reviewed runtime-domain literals,
pycompile, and `git diff --check`. The clean redesign predecessor's read-only,
network-blocked reprojection of the three stored source windows preserved source
hashes and confirmed the expected T2, T3, and Samsung candidate boundaries; the
integration does not claim a new provider or three-row runtime result.

The legacy `data/chroma_dart` store was inspected through a temporary copy. Its
collection `dart_reports_v2`, dimension `3072`, and declared canonical profile
were compatible. The corrected dry-run and the original source store were
byte-identical before and after inspection. No manifest was written.

Provider validation remains a separate final gate. It may run once, store-fixed
and eval-only with a 30-second heartbeat, only after a new manifest hash and cost
estimate receive explicit approval.
