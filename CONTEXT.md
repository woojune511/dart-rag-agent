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

The [comparison-binding Compiler probe](benchmarks/results/comparison_binding_compiler_2026-09-15/RESULTS.md)
ran four fixed synthetic questions once on clean `9837d78b`, under exact SHA/cap approval.
Source/execution accepts **4/4**; separate Codex review finds **3 correct directions /
1 wrong reverse direction**. All four link the exact request, but only three assign
the right endpoints. Original reverse wording yields -10% instead of +11.111…%; both
explicit-reference controls are correct. Same catalog/plan bytes, original two
inputs/criteria unchanged; not unseen holdout or isolated patch causation.
The reverse retry repairs a previous candidate misplaced under the current input;
it does not repair the wrong comparison direction. No automatic formula correction.
Generations/counts 5/5, internal retries 1, provider errors 0. Generation estimate
USD 0.10857625 + count contingency USD 0.30 = accounted USD 0.40857625 below USD 0.60;
not an invoice/count tariff. Manifest `b2a68ca0...ff0f0` consumed. Focused 41/41 and two
byte-identical socket-blocked SDK rehearsals preceded calls; all first request hashes,
runtime and bound files verified unchanged afterward. No runtime patch or paid rerun.
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

1. Request linkage alone did not fix reverse interpretation. Inspect exact request,
   endpoint assignment and competing fixed-plan instructions provider-free before
   another experiment; a `growth`-label bias remains a hypothesis. Lookup scope /
   over-abstention is separate. Do not force formulas or equate structure with meaning.
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
