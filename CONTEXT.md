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
- Admission `24322d93...9aaf` was consumed exactly once on commit `5c4c796`.
  The store-fixed eval-only runner completed in `339.1s` without runner retry,
  fresh ingest, document embedding, or source-store mutation. Estimated
  non-embedding cost was USD `0.1187678` under the USD `0.40` ceiling.
- Release is `HOLD`. Mechanical runtime completeness is `2 / 3`; the reviewed
  source-consistent gate is `1 / 3`.
- T2 kept `87.0`, `78.1`, and visible `11.5%`, but the compiler omitted the
  source-display binding and rendered the recomputed `11.4%`.
- T3 passed: table 82 row `9:2` supplied `26%` and `700,691백만원`, table 90
  row `21:4` supplied the complete four-value summary, and BHAF `53%` was not
  selected.
- Samsung first selected accepted candidate `cand_27da082cf5bcd0cb9f27`, then
  rejected planner `display_unit=KRW` as a display surface. The retry wrongly
  promoted another bundle, leaving numeric obligation `ob_001` missing.

Provider-free fixtures cover exact current/prior context and parentheses,
physical row grouping, source-text deduplication, owner/bundle visibility,
byte-exact assertion grounding, unchanged-cohort assertion retry, next-bundle
promotion after candidate rejection, and pre-call capacity failure.

## Hard boundaries and next step

1. Do not reuse exhausted admissions `06a40243...016`, `729d1f53...4b93`, or
   `24322d93...9aaf`.
2. Do not change dataset answers, evaluator tolerances, historical artifacts,
   candidate IDs, store bytes, or parser table identity to make a gate pass.
3. Fix the unit boundary provider-free: canonical dimension symbols such as
   `KRW` must be accepted or projected before display-unit validation, and that
   error must not reject a correct candidate bundle.
4. Tighten the compiler contract so a source-stated derived display visible in
   the selected bundle is considered explicitly and preserved when it matches
   the obligation. Do not add a keyword rule or deterministic semantic guess.
5. Re-run focused local fixtures and the saved artifact projection. A new paid
   run requires a new manifest and separate approval; automatic retry and fresh
   ingest remain forbidden.
