# Current Handoff Context

Last updated: 2026-09-15

## Product and current boundary

The product is the single-agent `FinancialAgent`, on
`codex/reviewed-compiler-selection-gate`.
The approved request/source/execution simplification starts at `d9c36d8d`.
Read [AGENTS.md](AGENTS.md), [runtime contract](docs/architecture/agent_runtime_contract.md),
[code map](docs/overview/codebase_map.md), and [project status](docs/overview/project_status.md).

- Planner preserves exact request units, required outputs, display intent and explicit
  report/section/period constraints. Subject/metric wording is a reading target,
  not an allowlist of source names.
- Compiler display instructions now put explicit request intent before source-first
  defaults: calculation-only chooses null; a selected reported value must fit the
  request. Existing nullable choice/reason fields suffice; no intent classifier,
  keyword gate, extra field or call was added. The preserved synthetic display pair
  passes the bounded model successor below; broader accuracy is not established.
- Existing Compiler calls interpret the selected source. Numeric selections requiring
  local subject/scope interpretation carry request-to-own-axis/attached-context
  correspondence; code checks source linkage, not semantic equivalence.
- Ranking allocates exposure; immutable owner visibility is recomputed from the
  exposed union using actual source conditions. Same-source narrative requirements
  can share evidence, but hidden/foreign-period/section/filing sources remain barred.
  Ranking matches stay in diagnostics, not the Compiler payload.
- Production accepts only nested `CompilerResponseV2`: kind-specific output schemas,
  short source references, nested input/requirement ownership, separate narrative
  subject support and fact evidence. `lower_compiler_response` resolves references
  without guessing or repairing choices, then the execution program is revalidated.
  Code attaches the selected cell's complete axes. Outside context is quoted once
  with declared interpretation/scope uses; its field/addresses exist only for inputs
  with visible numeric attachments. Foreign context and inexact quotes still fail.
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
  algorithms, unit/sign/arithmetic/display execution and final-answer/ledger
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

The [display-intent Compiler successor](benchmarks/results/display_intent_compiler_2026-09-15/RESULTS.md)
ran once on `a2d89d40`: source/execution validation **2/2**, separate Codex
source-semantic review **2/2**, no retries or provider errors. On the unchanged
synthetic source, the model selects 11.5% plus calculated 10% when both are requested,
and null source display / primary 10% for calculation-only. The raw responses make
these choices; lowering does not repair them. Inputs, plans, catalogs, criteria and
predecessor bytes are unchanged. Generation/count calls 2/2, generation estimate
USD 0.039515 plus USD 0.12 count contingency (not billing), below the delegated
assistant-selected USD 0.50 cap. Manifest `67788de2...2c09ff` is consumed.
Focused tests 39/39 and two byte-identical, socket-blocked SDK rehearsals preceded
calls. Previously exposed fixed-plan controls only: not unseen/full-agent evidence,
general semantic accuracy or an isolated causal ablation of prompt components.

The [prior numeric run](benchmarks/results/numeric_grounding_compiler_2026-09-15/RESULTS.md)
on `51330fe5` remains source/execution **3/3**, separate semantic review **2/3**.
Its calculation-only source-display error is preserved, not retroactively corrected.
Its separate-row success had only one eligible candidate, not a two-visible-row test.
Manifest `8998a347...0a87d3` is consumed; no automatic rerun of either manifest.

The preceding [12-question probe](benchmarks/results/request_source_boundary_compiler_2026-09-14_v2/RESULTS.md)
and [one-question continuation](benchmarks/results/request_source_boundary_remaining_2026-09-14/RESULTS.md)
retain their original results, including over-abstention, reverse comparison and a
token-count 404 of unestablished cause. General bare-scalar admission preserves old
candidate identities and evaluation extraction; no expected operands were injected.
Current Python 3.13 gate: 1,678 tests passed (44.240s), display-intent focused 90;
import/topology/docs 24, domain audit 83, pycompile/diff checks passed.
Six new contracts cover initial/retry guidance, actual normalization through final
answer/ledger, positive/negative/equal values, direct precision and fingerprint
tampering. Authored wrong semantics remain a negative, not silently repaired.
One local expression fixture grows by 588 prompt / 303 schema UTF-8 bytes, with
unchanged candidate fingerprint/permissions and one mock call. Not SDK token or
model-quality evidence.

The latest historical [full-agent result](benchmarks/results/subject_grounding_full_agent_2026-09-14/RESULTS.md)
remains 2/3 complete, 3/5 outputs accepted on `054c6b22`; its admission
`af784682...a8f0` is consumed. The [fixed-plan compiler result](benchmarks/results/narrative_address_compiler_2026-09-14/RESULTS.md)
remains 9/9 structurally complete, not current-build or unseen-question evidence.
These results are not retroactively repaired by this change.
[Reviewed evidence index](docs/evaluation/reviewed_case_evidence_status.md) preserves
older fixture/source/result limitations.

## Next work and hard stops

1. The bounded display-intent regression passed; preserve its original pair and
   negative cases without answer injection, keyword branches or relabeled history.
   Reproduce the separate comparison-direction/over-abstention boundaries from
   existing traces with provider-free controls before selecting the next change.
2. Comparison direction and over-abstention remain separate semantic issues.
   Context-rich model accuracy and current full-agent acceptance remain unmeasured.
   Further provider work requires a new bounded successor, never a consumed manifest.
   No automatic paid retry, fresh ingest, store adoption/mutation,
   answer-key/tolerance change, or artifact commit.
3. Default `data/chroma_dart` remains a separate incomplete store, not repaired by
   this task. Source acquisition ambiguity/pagination, whole-source consistency,
   retired narrative helpers and formula-wide rounding propagation remain deferred.
4. Source support does not prove attribution, group scope, causal entailment or
   requested-theme completeness. Those still require independent model evaluation.

Chronology: [implementation history](docs/history/implementation_history.md),
[experiment history](docs/history/experiment_history.md), and Git.
