# Current Handoff Context

Last updated: 2026-09-05

## Working source

- Branch: `codex/bounded-semantic-tiebreaker`
- Base: `8d1b97d`
- First source-bundle contract commit: `d4aaf37`
- Compiler integration and legacy-path removal commit: `30607cd`
- Product path: single-agent `FinancialAgent`
- Historical benchmark results, stores, datasets, caches, and review packets are
  immutable and remain uncommitted.

Stable rules are in
[agent_runtime_contract.md](docs/architecture/agent_runtime_contract.md), the
minimal code map is in [codebase_map.md](docs/overview/codebase_map.md), and
chronology remains in
[implementation_history.md](docs/history/implementation_history.md) and
[experiment_history.md](docs/history/experiment_history.md).

## Current change

The prose seven-role classifier and disabled local cross-encoder path have been
replaced by source-bundle compilation:

- `SourceBundleV1` groups exact prose sentence/windows or one physical table row.
- Numeric owner admission is bundle-first: at most two bundles, compatible
  before unknown-only, with every non-conflicting member kept together.
- Compiler payload v5 stores source text once per bundle; candidates retain IDs,
  metadata, physical provenance, and bundle-local value spans.
- The existing compiler decides which facts and formulas satisfy an obligation.
  No total/component/rate enum controls runtime selection.
- Selected prose numeric bindings require an exact `source_assertion`. Validator
  checks bundle membership, visibility, exact substring bytes, and value-span
  coverage before execution.
- Candidate failure advances to the next bundle; assertion/schema/AST/binding
  failure keeps the cohort for the single targeted retry.
- Unaffected islands and assertions remain byte-identical. Diagnostics use
  `semantic_candidate_stage_diagnostics_v9`.
- The old fact-role, cross-encoder, interpreter, promotion-gate, export/mining,
  policy, fixture, and dedicated test surfaces are removed.

Unchanged boundaries:

- Candidate IDs and catalog fingerprint inputs
- Physical table/row/cell parser contracts
- Source store and ingest format
- HTTP response shape and `FinancialRunResultV1`
- Retrieval, API, ledger, MAS, Streamlit, evaluator, and dataset governance

## Verification

- Source-bundle/catalog/matching focused tests pass `28 / 28`.
- Cohort/compiler/validator/evidence-bundle/island tests pass `90 / 90`.
- Runtime domain-term audit passes with `86` reviewed literals; import/topology
  tests pass `21 / 21`; portfolio review gates report
  `review_surface_ready`.
- `compileall`, `git diff --check`, and full unittest discovery pass. Full
  discovery is `805 / 805` in `19.636s`.
- Provider-free replay of the immutable three-question predecessor verifies all
  three catalogs. T2 keeps `87.0`, `78.1`, and `11.5` in the applicable owner
  visibility; T3 exposes Motional `26%` while excluding BHAF `53%`; all four
  previously selected Samsung candidates remain visible.
- No provider call, fresh ingest, document embedding, store mutation, benchmark
  retry, or paid manifest execution has occurred for this change.

Provider-free fixtures cover exact current/prior context and parentheses,
physical row grouping, source-text deduplication, owner/bundle visibility,
byte-exact assertion grounding, unchanged-cohort assertion retry, next-bundle
promotion after candidate rejection, and pre-call capacity failure.

## Hard boundaries and next step

1. Do not reuse exhausted admissions `06a40243...016` or
   `729d1f53...4b93`.
2. Do not change dataset answers, evaluator tolerances, historical artifacts,
   candidate IDs, store bytes, or parser table identity to make a gate pass.
3. Commit the verified current-state documentation only.
4. Then create a new store-fixed eval-only manifest and byte-stable no-call
   rehearsal. Report its hash and cost ceiling for separate approval before any
   provider run. Automatic retry and fresh ingest remain forbidden.
