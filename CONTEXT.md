# Current Handoff Context

Last updated: 2026-09-03

## Checkout

- Integration worktree: `C:\Users\geonj\Desktop\dart-rag-agent-runtime-integration`
- Branch: `codex/typed-candidate-ranking`
- Immutable base: `a278c1a`
- Clean redesign predecessor: `8790f92`
- Candidate-ranking predecessor: `729e0fb`
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
- Provider-capable runs remain exact-admission scoped. The latest env-bound
  admission was approved and consumed by one store-fixed `eval-only` run on
  2026-09-03. It does not authorize another run, fresh ingest, automatic
  benchmark retry, or document embedding.
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

The candidate-ranking build used ignored env-bound admission
`benchmarks/results/typed_candidate_ranking_focused_admission_envbound_2026-09-03`.
Its manifest SHA-256 is
`9c1d1807f74397d528278592c6867e491decf23abbb03977fb33c837cf86a3c3`;
two persisted no-call receipts and the immediate pre-dispatch receipt are the
same 6,552 bytes at
`31adb7b259247b9006be373e2aa2ff9def635dec50f6416ecbb9e921ff98c5f9`.
The runtime resolved the worktree `.env` before provider configuration; no key
value or `.env` hash is recorded.

The separately approved run completed exactly once in 295.5 seconds at runtime
head `12fe139`. The ignored result bundle is
`benchmarks/results/typed_candidate_ranking_focused_successor_envbound_2026-09-03`;
its root `results.json` SHA-256 is
`a80fdbdff7b7b8d05091b74f2cffcdfaf76822549d992ca5311ee6118d89617d`.
The predecessor `b6762027...61e3` attempt had already been consumed by an
environment-binding failure before provider construction and was not retried.

All three current rows report structured result `ok`, calculation `ok`, no
missing obligation, runtime error zero, and ledger integrity `ok`. T2 selected
`87.0만 대` and `78.1만 대`; Samsung preserved the accepted research-cost and
Harman evidence. T3 now sees and selects `700,691백만원`, and the wrong-row BHAF
`53%` value remains outside its owner cohort.

The release gate nevertheless remains **2/3 source-consistent, HOLD**. T3's
three obligations had empty coupling keys and compiled as separate islands. The
compiler chose `25.92%` from consolidated-notes table 83 because it considered
that value more precise, then chose `700,691백만원` from table 82; the narrative
used only detailed-table `당기순손익 -803,742` without its unit. Mechanical
runtime completeness is 3/3, but the selected evidence is not one compatible
Motional reporting tuple and does not contain the complete consolidated summary.
That paid artifact predates the evidence-bundle successor; local contract success
does not retroactively change it or authorize another provider run.

The runner recorded 20 LLM calls, 136,312 LLM tokens, 30 embedding calls, zero
document-embedding calls, and estimated runtime cost USD `0.1356168`. Embedding
cost remains unavailable. One initial canonical-routing embedding request
returned HTTP 429 and degraded safely; later calls completed. Source result
hashes, SQLite hashes, and complete store fingerprints remain unchanged, and no
disposable store remains. No automatic run retry was made or authorized.
