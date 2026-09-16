# Current Handoff Context

Last updated: 2026-09-16

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
  numeric owner-allowed source enums, cell/prose/dependency-specific fields, and
  separate narrative subject/fact support. `lower_compiler_response` resolves refs
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

The [source-choice schema A/B](benchmarks/results/source_choice_schema_2026-09-15/INTERPRETATION.md)
on clean `830233aa` completed 12 generations/counts: two questions x two schemas x three repeats.
Before/after runtime accepts **5/6 → 6/6**, meaning and both gates **3/6 → 5/6**.
Reverse direction remains wrong once after; source validation does not certify meaning.
Full production prompts/sources/authority unchanged; only schema differs. No automatic repair.
Manifest `8b0468ed...f3b6b1` consumed; API/schema errors/retries 0; identical SDK rehearsals.
Estimate USD 0.241115 + count contingency 0.72 = 0.961115 < 1.20, not invoice.
Earlier [naming-only conditions](benchmarks/results/requirement_id_ablation_2026-09-15_v2/INTERPRETATION.md) retain both gates 2/4 each; no ID-rename remedy.
The [previous input deletion](benchmarks/results/compiler_instruction_plan_ablation_2026-09-15/INTERPRETATION.md)
retains its 503 partial run: 14 responses, nine not run, both arms 5/7; no resume.
Predecessor evidence unchanged. Tiny repeated diagnostics, not general/full-agent evidence.
The [preceding factorial](benchmarks/results/comparison_formula_factorial_2026-09-15/INTERPRETATION.md)
retains current/current+formula/minimum/minimum+formula 9/12, 9/12, 12/12, 10/12.
No formula benefit was observed; minimum jointly changes input and schema, not V2 authority.
The earlier [plan-hint A/B](benchmarks/results/plan_metric_hint_compiler_2026-09-15/RESULTS.md)
retains structural 4/4, original/neutral semantic 2/2 and 1/2; no hint clearing.
Its consumed `045a3eb5...dfe53` and historical same-input response variation stay preserved.
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
Historical comparison-binding gate: 190 focused, 24 import/topology/docs and domain audit 83 passed.
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

1. [Operation-step formulas](tests/test_formula_steps.py) replace punctuation-token generation. Compiler chooses operation/arguments and backward-only step references; code supplies parentheses for the unchanged arithmetic engine. Inline quantities retain their owned request address and interpretation. Arity, final-step reachability and bounded expansion fail without guessing or truncation; no extra call or old-wire fallback.
   Python 3.13 provider-free full unittest **1,786/1,786**, no skips (59.807s); ten added contracts, import/topology/docs 24, audit 83 and pycompile/diff checks pass. Source/dependency authority, signs/units/display, exact proofs, accepted retry bytes and V2 checks remain. Explicit offline authored transport alone projects existing formulas/proofs; sampled responses stay untouched.
   [Local six-case replay](benchmarks/results/formula_steps_local_2026-09-16/RESULTS.md) passes six authored witnesses / 12 output checks / six ledgers, one mock call/no retry each. All 32 predecessor files remain identical. Prompt/schema totals 220,889 -> 247,463 UTF-8 bytes (+12.0%); authored replies 9,589 -> 10,328 bytes. Removing punctuation choice is not token savings or observed generation stability.
   Immutable [inline-operand paid result](benchmarks/results/inline_request_operands_compiler_2026-09-16/RESULTS.md) stays JSON/schema 4/6, runtime 4/6, ledger 4/4. Double newly passed; half/negative repeated 1,433/1,419 opening parentheses in the first growth formula and never executed. Model versus constrained-decoder causes remain unisolated. `950de7e7...e53ae1` is consumed; USD 0.554205 including count contingency < 0.80 is an estimate, not invoice. No sampled response is repaired or replayed as a success.
   [Approved step-formula run](benchmarks/results/formula_steps_compiler_2026-09-16/RESULTS.md) consumed `e2dc8c1e...f626dd` once on clean `6e25dedb`: first count succeeds (6,644 tokens), first generation returns HTTP 400 INVALID_ARGUMENT, other five not attempted, all retries zero. No model response: syntax/meaning/runtime acceptance unassessable, not 0/6 accuracy. Sent bodies match both SDK rehearsals; all 32 predecessor files unchanged. Budget accounting USD 0.119505 includes the failed request reservation and count contingency, not observed billing. Detailed provider message was not retained, so the exact rejection cause is unknown. Next: generation-schema compatibility and narrowly scoped credential-safe diagnostics, not another quality run or automatic suffix continuation. Local SDK/schema/count success did not establish generation acceptance.
2. Structural output constraints are not a remedy for semantic direction errors.
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
