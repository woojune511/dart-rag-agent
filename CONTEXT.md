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
- Numeric reading instructions distinguish requested comparison reference/target
  from period labels/order, and reported-row lookup from unrequested aggregation.
  Genuine ambiguity stays unanswered; no formula repair or forced answer/retry.
  The bounded model probe below still exposes abstention, scope and direction errors.
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

The [numeric-reading Compiler probe](benchmarks/results/numeric_reading_compiler_2026-09-15/RESULTS.md)
ran eight fixed synthetic questions once on clean `02c799a0` under delegated
no-additional-approval authority. Four numeric outputs pass source/execution checks;
separate Codex source review finds **3 correct numeric / 1 wrong reverse direction**.
The four withheld outputs are **1 appropriate evidence-gap abstention / 2 excess
abstentions / 1 scope-declaration rejection**. The rejected forward formula is right,
but both model drafts assign period names to segment. These outcomes are not a
blended semantic success rate; a structurally accepted reverse formula is wrong.
Original four inputs/criteria are unchanged; four variations were authored before
calls but after implementation, not unseen holdout. All attempts expose two candidates.
Generations/counts 10/10, existing retries 2, provider errors 0. Estimated generation
USD 0.19730625 + USD 0.60 count contingency = USD 0.79730625 accounted against the
assistant-selected USD 1.20 cap, not observed billing. Manifest `24deb343...d2141a`
is consumed. Focused 41/41 and two byte-identical socket-blocked SDK rehearsals
preceded calls; runtime and all bound files were verified unchanged afterward.
No automatic rerun, runtime patch, source mutation or current full-agent claim.

The [earlier display-intent pair](benchmarks/results/display_intent_compiler_2026-09-15/RESULTS.md)
on `a2d89d40` remains source/execution 2/2 and separate source-semantic review 2/2:
source-plus-calculation gives 11.5%/10%; calculation-only gives null display/10%.
The [prior numeric run](benchmarks/results/numeric_grounding_compiler_2026-09-15/RESULTS.md)
retains its source-display error (structural 3/3, separate semantic 2/3); no relabeling.
Both older manifests are consumed, not current full-agent/general accuracy evidence.

The preceding [12-question probe](benchmarks/results/request_source_boundary_compiler_2026-09-14_v2/RESULTS.md)
and [one-question continuation](benchmarks/results/request_source_boundary_remaining_2026-09-14/RESULTS.md)
retain their original results, including over-abstention, reverse comparison and a
token-count 404 of unestablished cause. General bare-scalar admission preserves old
candidate identities and evaluation extraction; no expected operands were injected.
Current Python 3.13 numeric-reading focused gate: 104 passed; import/topology/docs
24, domain audit 83, pycompile/diff checks passed. Most recent full suite on
`a2d89d40`: 1,678 passed (44.240s); not rerun for this instruction-only seam.
Six new contracts cover initial/retry guidance, actual normalization through final
answer/ledger, positive/negative/equal values, direct precision and fingerprint
tampering. Authored wrong semantics remain a negative, not silently repaired.
One local expression fixture grows by 588 prompt / 303 schema UTF-8 bytes, with
unchanged candidate fingerprint/permissions and one mock call. Not SDK token or
model-quality evidence.

[Comparison/abstention local replay](benchmarks/results/numeric_reading_intent_2026-09-15/RESULTS.md)
isolates the old reverse formula (-10%) from its invalid context fields; an explicitly
authored reverse formula produces +11.111…% with the same inputs. The explicit parent
row also executes when selected. Seven before/after replay paths preserve program,
schema, source hashes, authority and 8 mock calls / 1 mock retry; prompt strings grow
1,012 local JSON UTF-8 bytes each. No provider call, hidden repair or changed criterion.

The latest historical [full-agent result](benchmarks/results/subject_grounding_full_agent_2026-09-14/RESULTS.md)
remains 2/3 complete, 3/5 outputs accepted on `054c6b22`; its admission
`af784682...a8f0` is consumed. The [fixed-plan compiler result](benchmarks/results/narrative_address_compiler_2026-09-14/RESULTS.md)
remains 9/9 structurally complete, not current-build or unseen-question evidence.
These results are not retroactively repaired by this change.
[Reviewed evidence index](docs/evaluation/reviewed_case_evidence_status.md) preserves
older fixture/source/result limitations.

## Next work and hard stops

1. Before more paid trials, reproduce the free interpretation.scope/grounding/retry
   seam provider-free: period labels became conflicting segment/basis declarations.
   Keep genuine cross-scope negatives; do not merely ignore the resulting conflict.
   Separately examine requested lookup scope and comparison reference preservation.
   Parent-row abstention repeats; wrong reverse arithmetic follows the model formula.
   Do not force a row, flip a formula or relabel fixed criteria to pass.
2. No arithmetic defect or general instruction-only remedy was established.
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
