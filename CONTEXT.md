# Current Handoff Context

Last updated: 2026-09-14

## Product and current boundary

The product is the single-agent `FinancialAgent`, on
`codex/reviewed-compiler-selection-gate`.
The approved request/source/execution simplification starts at `d9c36d8d`.
Read [AGENTS.md](AGENTS.md), [runtime contract](docs/architecture/agent_runtime_contract.md),
[code map](docs/overview/codebase_map.md), and [project status](docs/overview/project_status.md).

- Planner preserves exact request units, required outputs, display intent and explicit
  report/section/period constraints. Subject/metric wording is a reading target,
  not an allowlist of source names.
- Existing Compiler calls interpret the selected source. Numeric selections requiring
  local subject/scope interpretation carry request-to-own-axis/attached-context
  correspondence; code checks source linkage, not semantic equivalence.
- Ranking allocates exposure; immutable owner visibility is recomputed from the
  exposed union using actual source conditions. Same-source narrative requirements
  can share evidence, but hidden/foreign-period/section/filing sources remain barred.
  Ranking matches stay in diagnostics, not the Compiler payload.
- Production accepts only nested `CompilerResponseV1`: kind-specific output schemas,
  short source references, nested input/requirement ownership, separate narrative
  subject support and fact evidence. `lower_compiler_response` resolves references
  without guessing or repairing choices, then the execution program is revalidated.
- Explicit request-grounded output relationships replace arbitrary `coupling_key`.
  Dependencies and physical shared-row constraints remain separate. At most eight
  islands, one retry each, numeric 96 / narrative 32 unique IDs, atomic bundles.
- Format/reference/source-correspondence repair keeps the same evidence. Actual
  source/dimension conflicts can replace a bundle. Invalid plans are not sent back
  to Compiler for unauthorized repair. Accepted outputs/proofs remain byte-identical.
- `CompilationEnvelopeV2` binds full source content, ordered requests, lowered
  program and source proofs. No global-only execution or production legacy-wire path.
  Explicit offline/test fixture projections are not new model answers.
- Public `FinancialRunResultV1`/HTTP, parser/store formats, candidate IDs/catalog hash
  algorithms, unit/sign/arithmetic/source-first display and final-answer/ledger
  ownership are unchanged. No source store, dataset or historical result was rewritten.

## Evidence and claim limits

[Boundary controls and local comparison](docs/architecture/request_source_boundary.md)
fix 12 anonymous semantic controls before runtime changes. Wrong meaning with valid
source linkage remains a semantic negative control, not a code-detected error.

Provider-free baseline/current replay of five reviewed cases uses explicitly authored
schema successors: 6 calls / 0 retries in both, same selected IDs/numeric/display
signature. Prompt bytes 208,427 → 134,135; schema bytes 59,832 → 37,115.
These are local UTF-8 serializations, not measured SDK tokens, bills, latency or
model accuracy. Current validation gates are recorded in project status.

The subsequent [anonymous Compiler probe](benchmarks/results/request_source_boundary_compiler_2026-09-14_v2/RESULTS.md)
ran once on `ad51fa61` under the user's delegated no-additional-approval instruction
(assistant-selected USD 1.60 cap). Of 12 fixed questions, 9 received completed
model runs: 7 accepted/source-reviewed correct, one over-abstention and one wrong
comparison direction in a source-invalid draft. Question 10 stopped at Google
`countTokens` HTTP 404; two were unattempted. Generation 14 / count attempts 15,
5 internal retries, estimated generation USD 0.257575 plus USD 0.90 count contingency
(not billing). Manifest `aa88c29e...ccb163` is consumed; no automatic rerun occurred.

The latest historical [full-agent result](benchmarks/results/subject_grounding_full_agent_2026-09-14/RESULTS.md)
remains 2/3 complete, 3/5 outputs accepted on `054c6b22`; its admission
`af784682...a8f0` is consumed. The [fixed-plan compiler result](benchmarks/results/narrative_address_compiler_2026-09-14/RESULTS.md)
remains 9/9 structurally complete, not current-build or unseen-question evidence.
These results are not retroactively repaired by this change.
[Reviewed evidence index](docs/evaluation/reviewed_case_evidence_status.md) preserves
older fixture/source/result limitations.

## Next work and hard stops

1. Characterize duplicate numeric axis/context fields: five questions needed repair
   for invalid context IDs; preserve source checks while reducing invalid choices
   in model transport. Separately address comparison direction and over-abstention
   through general instructions/independent contrasts, not query-specific rules.
2. Bare prose quantities `110`/`100` were absent from the current candidate projection
   before the run; do not inject them to claim source-display coverage. Unattempted
   questions and the opposite consolidation variant remain unmeasured. Further
   provider work needs a new bounded successor, never reuse the consumed manifest.
   Only then consider a store-fixed full-agent follow-up. No automatic paid retry,
   fresh ingest, store adoption/mutation, answer-key/tolerance change, or artifact commit.
3. Default `data/chroma_dart` remains a separate incomplete store, not repaired by
   this task. Source acquisition ambiguity/pagination, whole-source consistency,
   retired narrative helpers and formula-wide rounding propagation remain deferred.
4. Source support does not prove attribution, group scope, causal entailment or
   requested-theme completeness. Those still require independent model evaluation.

Chronology: [implementation history](docs/history/implementation_history.md),
[experiment history](docs/history/experiment_history.md), and Git.
