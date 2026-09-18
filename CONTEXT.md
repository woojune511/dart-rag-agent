# Current Handoff Context

Last updated: 2026-09-18

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
  algorithms, unit/sign/arithmetic and final-answer/ledger
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

The preceding Google [full-agent result](benchmarks/results/subject_grounding_full_agent_2026-09-14/RESULTS.md)
remains 2/3 complete, 3/5 outputs accepted on `054c6b22`; its admission
`af784682...a8f0` is consumed. The [fixed-plan compiler result](benchmarks/results/narrative_address_compiler_2026-09-14/RESULTS.md)
remains 9/9 structurally complete, not current-build or unseen-question evidence.
These results are not retroactively repaired by this change.
[Reviewed evidence index](docs/evaluation/reviewed_case_evidence_status.md) preserves
older fixture/source/result limitations.

## Next work and hard stops

1. [OpenAI Compiler integration](docs/evaluation/openai_compiler_probe.md) now has a fresh [three-question successor](benchmarks/results/openai_compiler_narrative_full_agent_2026-09-16/RESULTS.md) on clean `e07b2704`: **3/3 complete, 6/6 outputs**, API/parsing/runtime errors 0, ledger 3/3. The direct acquisition-impact paragraph is exposed and cited; grounded Commerce growth remains 41.3957043439745%, displayed 41.4%. Fifteen narrative claims and 35 support occurrences were source-reviewed; this is assistant review of known sources, not unseen accuracy or human gold.
   User delegated continuation without another approval question. New manifest `ec2e65e1...98892f` consumed once under the same USD 7 cap: 43 API attempts, six Compiler first responses plus one allowed feedback repair for an unauthorized context reference; no SDK/whole-run retry. Accounted USD 2.03351403 includes 0.36 count contingency, not invoice. Runtime/21 packet/335 predecessor/23 original-store files verified; originals remain unchanged. Fresh plans/retrieval differ from prior runs, so 3/3 is not an isolated model or patch effect.
2. The [different-source compact-JSON comparison](docs/evaluation/compiler_compact_json_transfer_comparison.md), clean `d55874fa`, completes **4/4 first responses**, **6/6 runtime outputs** and **4/4 frozen content reviews** after four fresh counts; eight HTTP 200s, no repair/retry. User explicitly increased the experimental shared cap **14 to 15 (+1)**. Fresh manifest `2d77084c...383e1af3` consumed once; all counts precede generation and **2.1481** fully reserves the schedule. Numeric output tokens **1092 -> 948 (-13.19%)**; mixed **1594 -> 1224 (-23.21%)**; structural whitespace **1499/2142 -> 0/0**, with +83 input tokens per candidate. Both retain **226354918 thousand KRW** and **-3789 hundred-million KRW**, periods/signs/scale, the attributed 2628 cash-decline cause and separate Selecta restatement reason. Four narrative claims/eight support occurrences and eight numeric input occurrences checked against original evidence. One mixed candidate internal `display_format` is Japanese; executed value/claims remain Korean, and application display is untested. Two known excerpts, one sample per case/condition, assistant review: no reliability/holdout/default claim. Caller/transport **43**, docs **4** pass; two rehearsals give **36 identical files**. All **8012 predecessor files**, sources/stores/settings retain hashes. Added **1.367** (1.327 usage estimate + 0.04 count contingency), shared **14.10619659/15**, remaining **0.89380341**, pending zero, not invoice. Next provider-free work traces whether the internal display-format language can reach user-facing output, then considers compact-JSON adoption separately. No runtime/default change or further-call authority.
3. [Full OpenAI application migration](docs/evaluation/openai_application_migration.md) is implemented and locally selected with `DART_LLM_PROFILE=openai`: Terra routing/planning, unchanged Astra Compiler and Luna ingest context. Google clients/calls are unnecessary for this profile; old modes remain explicit. Seven new contracts cover real SDK schemas, source readiness, completed text, usage, refusal/incomplete handling and no retry. Only the local profile bytes changed; credentials/store settings are preserved. Provider switching does not certify full answer quality.
4. [Preceding normal-app smoke](benchmarks/results/app_store_smoke_2026-09-16/RESULTS.md), clean `4bab8ea7`: real shared services and providers through ASGI `/api/query`, HTTP 200, **2/2 runtime outputs**, ledger ok, no API/parsing/runtime errors or retries. Health/companies show 1,872 NAVER 2023 chunks, compatible/non-degraded source-complete storage. Exact collection selection retains canonical identity checks; local `.env` now connects `data/app_nav_2023_20260916` with its original collection. No external listening server was started.
   Fresh `230fceea...fbb71a` consumed once under USD 7 after two identical no-call rehearsals and a terminal-error check. Eighteen attempts (Astra 2, Flash 2, embeddings 14), usage estimate USD 0.61264133, no count calls, pending 0; not invoice. Normal application model/retrieval bodies were preserved; caller-only caps and single-dispatch guards applied. All 398 protected files, including both original stores and the inactive default store, are unchanged.
   Separate source review confirms 41.3957043439745% → 41.4%, two narrative claims/four support occurrences and retained subsidiary/group scope. **Narrative completeness remains partial**: the direct Commerce-impact paragraph was retrieved but none of its candidates reached the narrative window. This previous sample remains incomplete; the current successor below is separate evidence.
5. [Earlier mixed-profile app successor](benchmarks/results/app_narrative_smoke_2026-09-16/RESULTS.md), clean `abf87889`: HTTP 200, **2/2 complete outputs**, ledger ok, source-reviewed 41.4% and direct Commerce-impact evidence exposed/cited. Two narrative claims/five support occurrences retain other growth factors and acquired-group scope; frozen numeric/narrative/runtime criteria pass assistant review for this known question only. No API/parsing/runtime error, feedback repair or SDK/whole-run retry.
   Fresh `70d63a92...e8b96f7` consumed once under USD 7 after two identical no-call rehearsals and a terminal-stop check: Astra 2, Flash 2, embeddings 13; estimated USD 0.59734408, pending 0, not invoice. All 433 protected files preserved; local settings and the ready NAVER 2023 copy remain selected. No default promotion or complete provider migration.
   [Frozen-input correction](benchmarks/results/app_narrative_exposure_offline_2026-09-16/RESULTS.md) retains joint topic hints across literal subject mentions; primary/search-topic plus literal mention precedes weak pairs. Catalog/plan hashes stay fixed, five of eight payloads are identical, and all five historical narrative outputs retain accepted evidence. Live plans differ, so no isolated causal/general accuracy claim. That result remains unchanged; the full-OpenAI result below is separate evidence.
6. [Preceding cash/margin OpenAI verification](benchmarks/results/planner_numeric_app_2026-09-17/RESULTS.md), clean `930325f0`: both known-source questions HTTP 200/ledger ok, **2/2 runtime complete**, **2/2 outputs**, **2/2 full frozen acceptance**. Cash Planner now leaves display_unit empty and keeps 원문 단위로 in display_format/both owned request units; direct child inputs remain empty. Actual selected full-statement 2023-12-31 consolidated cell yields **3,576,456,533,329원**, preserving source precision/unit and citation. Its first Compiler response adds a separately located liquidity paragraph as a compatibility witness and fails direct_compatibility_context_mismatch; the existing single feedback repair removes only that witness, retaining the same visible candidates, selected cell, interpretation and exact attached context. Margin uses exact 2023 consolidated revenue/profit and final request-grounded rounding, returning **15.40%** in answer/slot/trace without a reported-ratio substitute or retry. Planner unit/source-choice behavior is now live-verified for these sampled questions; fresh plans and known sources do not establish isolated causal or unseen accuracy.
   Fresh `6857684d...e100df` consumed once after identical SDK and full-wrapper rehearsals: **22/22** completed requests (Terra 4, Astra 3, embeddings 15), API/parsing/unhandled runtime/requirement-preflight errors 0; one Compiler validation-feedback repair, SDK/whole-query retries 0. Estimate **USD 0.70462915**, shared **5.10658146 / 7**, remaining **1.89341854**, peak with reservations **5.89606896**, pending 0; not invoice. All **891** predecessor/16 admission files and original source bytes preserved; working logical source/metadata tables remain 1,872/59,477 and ready. No runtime/config/ingest change; prior same-runtime local 179 checks were not rerun. [Preceding result](benchmarks/results/numeric_final_app_2026-09-17/RESULTS.md) stays 1/2; earlier numeric 0/2, broader 1/3 and narrative 2/2 results keep their original claims. The provider-free direct-witness clarification above preserves this paid result and its original retry. The separate independent-question result, caller persistence and budget feasibility are recorded above.
7. Inactive default `data/chroma_dart` remains untouched with manifest mismatch; the selected application copy above is ready and covers NAVER 2023 only. Source acquisition ambiguity/pagination, whole-source consistency, retired narrative helpers and formula-wide rounding propagation remain separate tasks.
8. Source support does not alone prove attribution, group scope, causal entailment or requested-theme completeness. Those require separate semantic review; ledger integrity is not semantic accuracy.

Chronology: [implementation history](docs/history/implementation_history.md),
[experiment history](docs/history/experiment_history.md), and Git.
