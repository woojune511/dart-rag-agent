# Current Handoff Context

Last updated: 2026-09-22

## Product and current boundary

The product is the single-agent `FinancialAgent`, on
`codex/reviewed-compiler-selection-gate`.
The request/source/execution boundary starts at `d9c36d8d`; the accepted [portfolio scope](docs/overview/portfolio_scope.md) now governs further work.
Read [AGENTS.md](AGENTS.md), [runtime contract](docs/architecture/agent_runtime_contract.md),
[code map](docs/overview/codebase_map.md), and [project status](docs/overview/project_status.md).

- Planner preserves exact request units, required outputs, display intent and explicit
  report/section/period constraints. Subject/metric wording is a reading target,
  not an allowlist of source names.
- Compiler defaults to compact JSON while preserving exact strings and required content; explicit request intent precedes source-first
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
- Public trace copies omit internal Compiler/validation records after final/ledger
  assembly. Values, citations, request intent, canonical records, parser/store formats,
  candidate IDs/hashes and arithmetic are preserved; historical results stay immutable.

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

The preceding Google [full-agent result](benchmarks/results/subject_grounding_full_agent_2026-09-14/RESULTS.md)
remains 2/3 complete, 3/5 outputs accepted on `054c6b22`; its admission
`af784682...a8f0` is consumed. The [fixed-plan compiler result](benchmarks/results/narrative_address_compiler_2026-09-14/RESULTS.md)
remains 9/9 structurally complete, not current-build or unseen-question evidence.
These results are not retroactively repaired by this change.
[Reviewed evidence index](docs/evaluation/reviewed_case_evidence_status.md) preserves
older fixture/source/result limitations.

## Next work and hard stops

1. The [feature retirement](docs/architecture/portfolio_feature_retirement.md) additionally removes query classification/embedding/fallback, MAS, report-result cache/promotion, unused reflection and ratio-repair paths plus dedicated tools/tests. The graph starts at Planner; initial filing hints come only from explicit caller scope, not query-year regex. Public query_type is neutral qa. Planner → retrieval → Compiler → execution → final answer remains, with source, period/scope, arithmetic and coverage contracts. Prior topic-specific narrative deletions remain in effect; no replacement runtime or measured cost/quality gain is claimed.
2. The [successor comparison](docs/evaluation/portfolio_workflow_comparison_successor.md) on `6bc4aae5` completed four development pairs: seven new arms/11 calls plus one reused baseline; no provider errors/retries. Separate source review finds no clear quality advantage for Planner/Compiler at 3.47x estimated cost and 4.79x measured time. Cash retrieval/year-end meaning and one-decimal display remain gaps. Freeze per-error additions; take simple RAG as a candidate into a separate final set/demo, retaining current source/calculation guards. No production-default change or holdout claim.
3. [Real-question Planner result](docs/evaluation/planner_real_questions_result.md) still has period1/2, scope2/2, combined1/2; source replay2/2 does not resolve the lost year-end boundary. Keep this as a known development failure. Old provider outputs and stores are unchanged; no new model-quality or full-app acceptance claim.
4. Shared accounting is USD21.00190943/26.32, remaining5.31809057, pending0. Successor adds0.359777 under cap5.67; reused0.016349 is not charged again, and original lost-record ceilings remain charged. These are conservative estimates, not billing. This one-batch approval is consumed; no new funding or automatic additional batch. The [original failed attempt](docs/evaluation/portfolio_workflow_comparison_result.md), source stores, raw answers and separate accounting/review receipts remain preserved.
5. The comparison selects the NAVER2023 filing (1,090 chunks); its source graph contains 1,872 chunks across two filings. Inactive default `data/chroma_dart` keeps its manifest mismatch. Additional coverage, MAS/cache expansion and broad schema redesign are outside this milestone. Ledger/source-link integrity does not establish semantic correctness.

Current checks: [project status](docs/overview/project_status.md). Chronology: [implementation history](docs/history/implementation_history.md), [experiment history](docs/history/experiment_history.md), and Git.
