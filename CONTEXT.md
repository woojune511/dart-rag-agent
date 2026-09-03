# Current Handoff Context

Last updated: 2026-09-03

## Checkout

- Integration worktree: `C:\Users\geonj\Desktop\dart-rag-agent-runtime-integration`
- Branch: `codex/typed-candidate-ranking`
- Immutable base: `a278c1a`
- Clean redesign predecessor: `8790f92`
- Candidate-ranking predecessor: `729e0fb`
- The original dirty checkout remains an unstaged predecessor outside this
  worktree. The separately approved ignored store manifest was added under its
  `data/chroma_dart` directory.

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
7. Current source change: typed per-owner semantic targets and deterministic
   fact matching replace the additive keyword selector. The full catalog stays
   immutable; only owner cohorts are bounded, structured prompts are cell-local,
   and the validator rechecks declared targets with the same matcher.
8. Current source successor: complete physical rows become immutable
   evidence-bundle options for related same-subject outputs. Bundle membership
   adds a compilation-island edge even when planner coupling is empty; validator
   and executor reject mixed-row selections and retry the bundle atomically.

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
- Provider-capable runs remain exact-admission scoped. Evidence-bundle admission
  `b068ac4b...5501` was approved and consumed by one store-fixed `eval-only`
  process on 2026-09-03. It does not authorize another run, fresh ingest,
  automatic benchmark retry, or document embedding.
- The `data/chroma_dart` manifest layer now reports exact `compatible`,
  `ready=true`, and `degraded=false`. This is not provider-query validation.

## Verification authority

Current source and tests are authoritative. Stable rules are in
[agent_runtime_contract.md](docs/architecture/agent_runtime_contract.md), live
topology is in [runtime_flow_roles.md](docs/overview/runtime_flow_roles.md), and
historical evidence remains in [implementation_history.md](docs/history/implementation_history.md)
and [experiment_history.md](docs/history/experiment_history.md).

The candidate-ranking change has provider-free contract coverage for typed
targets, catalog-order determinism, compatibility-tier precedence, legacy
catalog grounding, cell-local prompt projection, validator revalidation, and
the added ontology concepts. Its source gate passes 752 total unittest cases,
146 focused semantic/import/topology/documentation cases, the 86-literal runtime
domain audit, pycompile, JSON validation, and `git diff --check`. Read-only
reconstruction of stored source windows
places Hyundai T2's two period values and T3's Motional carrying amount in their
intended owner cohorts while excluding the conflicting market/BHAF rows. This is
local source evidence only, not a new provider acceptance result.

The evidence-bundle successor adds provider-free contracts for complete-row
inference, cross-row rejection, context-compatible cross-table narrative,
immutable visibility, bundle-island construction, and atomic retry. Its local
source gate passes 760 total unittest cases, including eight focused bundle cases,
the 86-literal runtime-domain audit, import/topology checks, pycompile, and
`git diff --check`. No provider, network, fresh ingest, store mutation, dataset
change, or evaluator relaxation is part of this source gate.

A read-only reprojection of the three saved source windows confirms no inferred
bundle for T2 or Samsung and one three-owner T3 island with two physical options:
table 82 row `9:2` (`26%`, `700,691백만원`) or table 83 row `9:2` (`25.92%`,
`907,061백만원`), each with context-compatible source-defined narrative IDs.
Structure-graph and table-payload SHA-256 values were identical before and after.

The approved legacy-store adoption wrote one 394-byte manifest with SHA-256
`98ec5dcb6a376c490d3ced20c5ffe56c276a8f5e382d97dc18dcbe59d3920615`.
Its collection is `dart_reports_v2`, dimension is `3072`, and the declared
profile is canonical. All seven predecessor store files remained byte-identical.

The evidence-bundle build used ignored admission
`benchmarks/results/evidence_bundle_focused_admission_envbound_2026-09-03`.
Its manifest SHA-256 is
`b068ac4b108d8243a417b61e355439ef1f25106c3b707db12ce0561015a45501`;
two persisted no-call receipts and the immediate pre-dispatch receipt are the
same 6,710 bytes at
`98484f569246a4cc4af07b4e0070426a73aee9def2a4317b4011082593ecb191`.
The runtime resolved the worktree `.env` before provider configuration; no key
value or `.env` hash is recorded.

The separately approved runner process completed exactly once in 313.9 seconds
at runtime head `cc14901`. The ignored result bundle is
`benchmarks/results/evidence_bundle_focused_successor_envbound_2026-09-03`;
its root `results.json` SHA-256 is
`e679e712d3e228a9e19d6ef4c52b64e649853d9f5a44a83ed700deac48fea6b2`.

T2 and Samsung remain runtime-complete with error zero and ledger integrity
`ok`; their accepted evidence ID sequences are identical to the predecessor.
T2 retains `87.0만 대`, `78.1만 대`, calculated `11.4%`, and source display
`11.5%`. Samsung retains `28,352,769백만원` and the Harman narrative.

T3 now forms one three-owner island with one physical-row bundle and two valid
options: table 82 row `9:2` (`26%`, `700,691백만원`) or table 83 row `9:2`
(`25.92%`, `907,061백만원`). The first compiler attempt was partial. The one
allowed internal retry proposed the table 83 ownership candidate together with
the table 82 carrying-amount candidate. Validation rejected that mixed proposal
as `evidence_bundle_mismatch`; execution emitted no T3 output and all three
obligations remain missing. The release gate is therefore **2/3 runtime-complete,
HOLD**. The safety boundary works, but the compiler still chooses IDs per owner
instead of selecting a bundle option atomically.

The runner recorded 18 LLM calls, 166,963 LLM tokens, 32 query-embedding calls,
zero document-embedding calls, and estimated runtime cost USD `0.1645241`, below
the approved USD `0.40` ceiling. Embedding cost remains unavailable. Source
result hashes, SQLite hashes, and complete store fingerprints remain unchanged,
and no disposable store remains. No automatic runner retry was made or is
authorized.
