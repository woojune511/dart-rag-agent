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
9. `28d26dc`: complete bundle options are ranked from existing owner-cohort
   positions and one physical row is selected before compiler invocation.
   Output and source-defined requirement visibility is projected through that
   option, while numeric compatibility narratives remain available.

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
- Provider-capable runs remain exact-admission scoped. Atomic-bundle admission
  `06a40243...016` was approved and consumed by one store-fixed `eval-only`
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

The current provider-free lineage covers typed owner matching, deterministic
cohort ranking, cell-local prompts, complete-row bundle inference, cross-row
rejection, and atomic option projection. The repair tests catalog-order-independent
choice, next-row promotion, compatibility narrative preservation, and
source-defined requirement projection. Read-only projection of the consumed T3
result reduces its visible set from 16 IDs to 10, selects table 82 row `9:2`,
retains the two numeric compatibility cohorts and five narrative IDs, and removes
the table 83 numeric pair. The gate passes 763 total unittest cases, 134 focused
semantic/runtime-contract cases, 23 documentation/import/topology cases, the
86-literal domain audit, pycompile, and `git diff --check`. This is local source
evidence only; no provider, network, store write, dataset change, or evaluator
change was used.

A read-only reprojection of the three saved source windows confirms no inferred
bundle for T2 or Samsung and one three-owner T3 island with two physical options:
table 82 row `9:2` (`26%`, `700,691백만원`) or table 83 row `9:2` (`25.92%`,
`907,061백만원`), each with context-compatible source-defined narrative IDs.
Structure-graph and table-payload SHA-256 values were identical before and after.

The approved legacy-store adoption wrote one 394-byte manifest with SHA-256
`98ec5dcb6a376c490d3ced20c5ffe56c276a8f5e382d97dc18dcbe59d3920615`.
Its collection is `dart_reports_v2`, dimension is `3072`, and the declared
profile is canonical. All seven predecessor store files remained byte-identical.

The atomic-bundle build used ignored admission
`benchmarks/results/atomic_evidence_bundle_focused_admission_envbound_2026-09-03`.
Its manifest is `06a402433efa892f016f537dac1eceb4776e62cc67c83e2e4494309c310dd016`;
both persisted rehearsals and the immediate pre-dispatch rehearsal produced the
same 6,730-byte receipt at
`0e7ea486665d42d0be3686a067281461069bb887981dcd9e0d92a9409f95889f`.

The approved runner completed exactly once in 276.8 seconds at `28d26dc`. The
ignored root result is
`benchmarks/results/atomic_evidence_bundle_focused_successor_envbound_2026-09-03/results.json`,
SHA-256 `b103657a301aea72ae1d529a163f6db4a686361c061fe4c0029092817f44753e`.
All three questions are runtime-complete with error zero and ledger `ok`.

- T2 retained the same four evidence IDs, `87.0만 대`, `78.1만 대`, calculated
  `11.4%`, and source display `11.5%`.
- T3 compiled once without retry. Both direct outputs use table 82 row `9:2`:
  `26%` and `700,691백만원`; no table 83 numeric ID reached execution. Its
  Motional summary remains grounded in the separate source summary rows.
- Samsung retained all three predecessor evidence IDs and added one compatible
  Harman overview source; `28,352,769백만원` and the Harman narrative remain.

The bounded runtime release gate is therefore **3/3, PASS**. This does not change
the T3 mixed-basis answer key or promote qualitative evaluator scores: the raw
benchmark still reports T2/T3 completeness `0.7/0.3`, Samsung faithfulness
`0.7`, and two company-level full-eval failures.

The run recorded 17 LLM calls, 117,631 LLM tokens, 32 query-embedding calls,
zero document-embedding calls, and estimated runtime cost USD `0.1212257`.
Embedding cost remains unavailable. Source result hashes, SQLite hashes, and
complete store fingerprints are unchanged; no disposable store remains. The
admission is exhausted and no automatic retry is authorized.
