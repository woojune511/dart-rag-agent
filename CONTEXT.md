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
- Calculations now explicitly select nullable `comparison_request_unit_id` before
  binding existing variables `reference`/`target`. Code copies the owned exact request
  and source/requirement links into trace; no repeated model quote, new candidate role,
  direction inference, formula repair or additional call. Other calculations choose null.
  Four-case model probing used this wiring, but the original reverse question still
  has wrong endpoints; request linkage is not evidence of semantic equivalence.
  Reported-row lookup versus aggregation and genuine abstention remain separate issues.
- Existing Compiler calls interpret the selected source. Numeric selections requiring
  local subject/scope interpretation carry request-to-own-axis/attached-context
  correspondence; code checks source linkage, not semantic equivalence.
  Free segment/basis interpretations stay on their fingerprint-bound proofs, not in
  source/context fields or cross-input equality gates. Filing metadata takes priority;
  explicit shared-basis output relationships remain independently checked.
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

The [plan-hint A/B probe](benchmarks/results/plan_metric_hint_compiler_2026-09-15/RESULTS.md)
ran the original forward/reverse synthetic pair with original/neutral prompt projections
once each on clean `60593584`, under exact SHA/cap approval. Source/execution **4/4**;
separate direction review: original **2/2**, neutral **1/2**. Neutral reverse gives
-10% instead of +11.111…%; all four link the exact request, only three assign correct
endpoints. Clearing the two post-exposure metric hints shows no benefit in this run;
no production target clearing. This fixture hint is not a sampled Planner output.
Same canonical plans, questions, sources, permissions and schema; one sample per cell,
not causal/systematic-harm/general-accuracy evidence. Original reverse now succeeds
despite the same initial SDK body as the previous failed run; response variation's
cause is unestablished. No arithmetic or semantic auto-repair was performed.
Generations/counts 4/4, retries/errors 0. Generation estimate USD 0.08805750 + count
contingency USD 0.24 = accounted USD 0.32805750 below USD 0.60, not an invoice/tariff.
Manifest `045a3eb5...dfe53` consumed. Five diagnostic + 41 focused tests and two identical
SDK rehearsals preceded calls. Paid request hashes, runtime and all bound files verified
unchanged after execution, before docs. No runtime patch, source mutation or paid rerun.
The [preceding comparison probe](benchmarks/results/comparison_binding_compiler_2026-09-15/RESULTS.md)
retains 3/4 correct directions, including the original reverse error after an ownership
retry; both explicit-reference controls were correct. `b2a68ca0...ff0f0` remains consumed.
The [prior numeric-reading run](benchmarks/results/numeric_reading_compiler_2026-09-15/RESULTS.md)
on `02c799a0` retains 3 correct / 1 wrong numeric, 1 appropriate / 2 excess abstentions
and 1 scope rejection. Its consumed `24deb343...d2141a` and original results are immutable.

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
Current comparison-binding gate: 190 focused, 24 import/topology/docs and domain audit 83 passed.
Twelve new contracts cover direction-only pairs, signs/order, exact owned requests,
null/schema/hidden-source/period checks, zero reference, dependency repair, accepted
island bytes and V2 tampering. Full unittest **1,706/1,706**, no skips (71.314s);
pycompile/diff checks passed. Authored replies are not model-accuracy evidence.
One paired fixture grows prompt/schema by 298/387 UTF-8 bytes and response by 43;
one mock call, no retry. These are local serializations, not SDK tokens or billing.

[Exact scope-isolation replay](benchmarks/results/semantic_scope_isolation_2026-09-15/RESULTS.md)
reuses all eight paid cases' original wire responses with blocked sockets. The forward
case now executes -10% from its first draft; the reverse case still wrongly yields
-10%. Two excess abstentions and one appropriate gap abstention are unchanged.
Local numeric outputs 4→5, mock calls 10→8 / retries 2→0; six other final programs and
outputs are byte-identical. All source/response bytes and first prompt/schema/visible
IDs are unchanged. No new model sample, semantic repair, paid retry-reduction claim
or retroactive correction of the paid result above.

The latest historical [full-agent result](benchmarks/results/subject_grounding_full_agent_2026-09-14/RESULTS.md)
remains 2/3 complete, 3/5 outputs accepted on `054c6b22`; its admission
`af784682...a8f0` is consumed. The [fixed-plan compiler result](benchmarks/results/narrative_address_compiler_2026-09-14/RESULTS.md)
remains 9/9 structurally complete, not current-build or unseen-question evidence.
These results are not retroactively repaired by this change.
[Reviewed evidence index](docs/evaluation/reviewed_case_evidence_status.md) preserves
older fixture/source/result limitations.

## Next work and hard stops

1. [Minimum/current reading baseline](benchmarks/results/comparison_reading_baseline_2026-09-15/README.md)
   prepares five synthetic pairs / ten conditions, including physical-row mirrors.
   Twelve diagnostic + 41 focused tests pass; two socket-blocked captures are identical.
   Authored replies only; minimum ID/arithmetic checks do not replace production V2.
   Next assess first-response consistency under a new bounded admission, not hint clearing.
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
