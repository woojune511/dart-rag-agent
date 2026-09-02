# Current Handoff Context

Last updated: 2026-09-02

## Checkout

- Integration worktree: `C:\Users\geonj\Desktop\dart-rag-agent-runtime-integration`
- Branch: `codex/runtime-contract-integration`
- Immutable base: `a278c1a`
- Clean redesign predecessor: `8790f92`
- The original dirty checkout's 23 tracked/untracked predecessor paths remain
  byte-identical and unstaged. The separately approved ignored store manifest
  was added under its `data/chroma_dart` directory.

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
- No existing store receives a manifest automatically. The approved adoption
  wrote only `data/chroma_dart/store_manifest.json`; its seven predecessor files
  remained byte-identical.
- No provider call, paid evaluation, fresh ingest, automatic benchmark retry, or
  document embedding is authorized until the exact admission below receives a
  separate approval.
- The `data/chroma_dart` manifest layer now reports exact `compatible`,
  `ready=true`, and `degraded=false`. This is not provider-query validation.

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

The approved legacy-store adoption wrote one 394-byte manifest with SHA-256
`98ec5dcb6a376c490d3ced20c5ffe56c276a8f5e382d97dc18dcbe59d3920615`.
Its collection is `dart_reports_v2`, dimension is `3072`, and the declared
profile is canonical. All seven predecessor store files remained byte-identical.

The ignored local admission directory
`benchmarks/results/runtime_contract_integration_focused_admission_2026-09-02`
binds the current 134-file runtime build, unchanged profile/dataset, immutable
Hyundai and Samsung source stores, and the ordered questions `HYU_T2_010`,
`HYU_T3_072`, then `SAM_T2_078`. Two fresh no-call processes produced the same
5,640-byte receipt. Admission manifest SHA-256 is
`cb188492de5b51ee3b42cf5cf9aaf6c12192d92567c001a0426c4e6e785683a8`;
receipt SHA-256 is
`d63ae5e34e939b68f03f4bc69b897af2f2b755c47039e4a4873352d1117105b3`.
Both recorded zero provider constructors, network calls, and outputs.

Provider validation remains a separate final gate. The proposed authorization
is one store-fixed eval-only run, no automatic run retry, a 30-second heartbeat,
and a USD `0.40` ceiling. The latest same-scope runner estimate is USD
`0.1442999`, excluding embedding pricing. This exact hash-and-cost scope still
requires explicit approval.
