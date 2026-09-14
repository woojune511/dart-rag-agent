# Project Status

Last updated: 2026-09-14

## Current implementation

The product is `FinancialAgent`, on `codex/reviewed-compiler-selection-gate`. Next: [current-build full-agent admission](../../benchmarks/results/subject_grounding_full_agent_admission_2026-09-14/README.md), prepared only, **USD 1.60** cap and separate approval pending; provider calls **0**.
Latest [server-count full-agent result](../../benchmarks/results/server_count_full_agent_2026-09-14/RESULTS.md), run HEAD `ac8798f8` / runtime SHA `275ee5db...d6409`: manifest `5295c516ec186d4310203a2b97db15bb79bbf939ceae678e9d56cc5cc0599a14` consumed once. **2/3 runtime complete, 4/5 outputs accepted**; NEW_NARRATIVE_01 and NEW_NARRATIVE_02 meet frozen source criteria in Codex review. NAV_T2_006 calculates **41.4%** but withholds acquisition impact: numeric presentation is repaired on retry, yet subject selection still ends at `Inc.` in p2 while the rest remains in p3. Provider/execution exceptions **0**, ledger **3/3 ok**, aggregate `ok/partial/ok`; no budget stop or source loss, not release/unseen-question success. Gemini **12 counts + Flash 6 / Pro 6 generations**, OpenAI **25** requests, 168.161s; all 12 server-count/input-reservation/prompt-usage pairs equal. Usage estimate **USD 0.28009336** + count contingency **0.72** (not billing) = accounted **1.00009336/1.60**, peak **1.03065336**, pending **0**. Receipt `18f285ab...a8acf` / review `3569946f...62cb`: six attempt hashes/locations, 18 exact stored/sidecar quote occurrences, accepted calculation bytes and retry cohorts verified; **161 runtime / 124 protected / 23 store files** intact. Numeric source display remains null: 41.4% is rounded calculation, not source-display selection success. No runtime/SDK/default change, paid rerun, fresh ingest or document embedding. The [budget-interrupted predecessor](../../benchmarks/results/narrative_address_full_agent_2026-09-14/RESULTS.md) remains immutable; its lost NAV drafts are not recovered.
Latest [source-address compiler-only result](../../benchmarks/results/narrative_address_compiler_2026-09-14/RESULTS.md), run HEAD `9771417f`/runtime `7ed5f332`: **9/9 structurally complete**, **11/11 outputs accepted**, Codex pre-fixed source criteria **9/9** (anonymous **6/6**, saved DART **3/3**). Pro **13 calls / 2 internal retries**, 202.996s, estimated **USD 0.4594425/0.90**, billing unobserved; API/execution exceptions **0**. NAV acquisition and CEL liquidity now complete; NAV's numeric values, IDs and physical/display provenance are unchanged. Receipt `0fbaf3d6...9e75c0`: nine V2 execution/final replays byte-identical, 43 exact transmitted fact/subject selections, all retry candidate payloads unchanged; **110** protected and **161** runtime files intact. Initial accepted programs remain byte-identical. The two NAV retries repair missing source-display period support and narrative subject/source-number presentation, respectively. No runtime patch, planner/retrieval/embedding/store call or batch rerun; not human gold, unseen holdout, full-agent/ledger/release success. The [7/9 compiler predecessor](../../benchmarks/results/subject_fact_compiler_2026-09-13/RESULTS.md) and frozen **0/3** full-agent result remain unchanged.
[Audit findings and residual boundaries](../architecture/general_correctness_audit.md) are the current work map, not case-by-case trial-and-error.

Implemented generic repairs:

- All intents use required-output planning and the existing source-bundle compiler. Planner input now includes bounded report-scoped whole axes and observed references before subject fixation; deduplicated/query-literal hints are not alias, quote or candidate authority. Exact request conditions/full names/groups and frozen targets survive; no suffix rule, validator change or extra call.
  Narrative-bearing multi-output calls receive copied full-plan responsibility context, fixed across retries and separate from active owners/cohorts/verified dependency inputs. Single-output and numeric-only calls add nothing. Policy preserves qualifiers/independent topics; no semantic dedup, fixed count or extra call.
- The existing planner selects observed filing-qualified section IDs separately from exact owned request wording (`source_section_bindings`); code adds spans/paths/fingerprint. Its read-only metadata inventory shares the retrieval scope and visibly bounds capacity.
  Unresolved/foreign references fail closed. Parent/input restrictions intersect through retrieval/cohorts/dependency validation and V2; body mentions and inherited context cannot grant authority.
  `source_sections` remains strict literal compatibility, without dual-writing the same restriction or adding a model call. Exact ID/path checks do not prove semantic equivalence.
- Formula inputs require declared dependency authority; targeted assertion retry cannot
  poison accepted outputs. Boolean/non-finite/overflowing literals and invalid scalar
  function arity fail validation; function names may also be legitimate variable names.
- Source filters remain intact across vector failure, BM25 ranking, local supplements,
  seeds and final selection. No all-filtered-results fallback to unrelated reports.
- Filing-qualified narrative identity preserves sources sharing local chunk numbers.
  Table-fragment splitting preserves prose before the first numbered item. Narrative eligibility uses scope/unit, not name repetition. Topic matches (including existing owner-local search hints) precede literal mention within a scope tier; hierarchy diversity stays format-neutral. Hints do not change numeric ranking, semantic targets, conflicts, ownership or quote authority.
- Fixed absolute-year bonuses/penalties and dated stopword entries are gone; router
  examples are anonymous config. No benchmark/company/answer branches were added.
- Whole calendar/relative/fiscal labels cannot become inferred subjects, including
  abbreviated years. Explicit subjects and names containing temporal text stay intact.
- Initial/retry prompts limit active outputs and mark bounded excerpts. Current narrative
  schema uses explicit shared `subject_bindings` plus claim-local fact selections. V8
  source addresses extract exact ranges; unique whitespace-only subject correspondence adds a raw-source/span witness without model/source rewriting. Exact-path traces stay unchanged; both number checks consume fact ranges/report year only, never shared subject support.
  Address/subject/number errors keep same-cohort repair and exact field locations. Targeted subject errors now compare declared text with exact selected ranges; malformed addresses expose only a resolution code, never neighboring text. Initial/numeric-only prompts and other accepted bytes stay unchanged. Registry/claim drafts and opt-in capture remain non-authoritative; no automatic expansion, inheritance, numeric authority change, extra call or semantic correctness claim.
- Canonical routing validates full finite vector batches before success caching;
  incomplete embedding identity disables cross-instance reuse. Cosine is scale-stable.
- Search-cache Documents/provenance are copied, committed writes invalidate caches,
  and actual persistence errors propagate. Terminal admission failures do not retry
  through context generation, planning, routing, search or evidence fallbacks.
- API failure responses redact raw provider text. Aggregate ledger status follows the
  final public result, including partial/incomplete coverage.
- XML recovery preserves ampersand text, entity controls and quoted attributes;
  explicit header/body tables are data even with one small value. Narrative modes can
  read scalar rows; non-scalar rows retain reading-only evidence. Optional exact
  `row_description_quote` uses physical/document scope without scalar permission;
  description-only references stay out of numeric operands/raw-value evidence. No new IDs or calls.
- Peer headings survive layout variation; table context cannot cross heading boundaries.
  Exact located intermediate headings reach paragraph/table candidates via the sidecar;
  full scope separates chunks/adjacency, captions stay local, and `local_heading` remains a hint. Fresh cell partitions preserve raw text/spans but present independent quote surfaces; narrative/scope quotes cannot bridge cells. Multi-cell claims use separate bindings. Existing stores remain untouched.

Existing public, source-bundle, unit, physical-row, typed-state, strict-readiness,
manifest-last ingest and source-first display contracts remain.
Default HTTP/`FinancialRunResultV1`, ID/hash algorithms, datasets/scoring, source stores
and historical result bytes are not changed by this audit.

## Local verification

Current subject-display grounding gate: Python **3.13.13**, full unittest **1,628/1,628**, no skips (44.017s); focused **55/55**, import/topology/docs **24/24**, domain audit **83**, pycompile **7** files and `git diff --check` pass. Controls cover eight whitespace layouts, exact-path trace preservation, source-character offsets, duplicate/ambiguous positions, owner/requirement/physical boundaries, fact-local numbers, same-cohort retry and V2 source/witness tampering. Two separate-process saved-response replays are byte-identical (`faa9c39b...c5ace`, runtime `ed5e0736...ab22a`): all model-response and candidate-payload bytes are preserved, only line-break acceptance changes, three whole program/validation/execution results remain identical. **146** protected files and **46** frozen admission/result/prototype files unchanged; one deliberately migrated source test has its committed predecessor hash verified. Provider calls **0**, no source-store/dataset mutation, not model accuracy or full-agent/release evidence.

Earlier source-address gate: Python 3.13.13; full unittest **1,567/1,567**, no skips (46.905s). Domain audit **83**, import/topology/docs **24/24**, pycompile **39** changed/new Python files and `git diff --check` all pass. Address/registry/compiler controls **22/22** plus migrated source/owner/requirement/retry/negative controls. Current narrative schema is source-addressed, not a replay of old model choices. Read-only nine-input/11-island reprojection preserves candidate metadata/IDs, cohorts, bundle/context fingerprints and constraints; numeric-only payload bytes identical. Candidate payload bytes **213,843 → 229,617 (+7.38%)**. Network-blocked real SDK serialization with abstention stubs completes **11/11**, max **88,784/196,608 bytes**, total **545,494 bytes**; semantic acceptance and retry-request size unmeasured. All **77** protected files, **9** admission-local files and consumed result/receipt hashes unchanged; provider calls **0**.
Earlier request-boundary/transport controls still retain intentional semantic negatives; structural success does not certify attribution or requested-theme completeness.
Historical fixtures are not rewritten: explicit temporary/test copies add authored request assignments and source selections for current-schema transport. These are execution regressions, not planner/compiler inference or new model answers.
The earlier full gate was **1383/1383** on `222ffba9`; six saved planner responses replay identically on that measured predecessor, not under the new required-field schema. Historical admission/result receipts remain immutable.
The [period/subject projection](../../benchmarks/results/period_subject_boundary_2026-09-10/v2/README.md) remains bound to `3d3f64cd`; [reading/selection replay](../../benchmarks/results/narrative_reading_selection_2026-09-11/README.md) to `cb6ebb3a...da7ba`. Neither is current-head model output.

The [counterfactual](../../benchmarks/results/narrative_row_description_2026-09-11/README.md) removes the carrier-period error with three authored quotes; two other responses remain unchanged. This is not new compiler output or semantic success.
The [section-authority counterfactual](../../benchmarks/results/requested_source_sections_2026-09-11/README.md) rejects two foreign-section CJ IDs without new planner/compiler output; runtime `f95f3cd2...705b`.
The [source-local probe](../../benchmarks/results/local_heading_scope_2026-09-11/README.md) corrects inherited headings in memory: 27 source/table blocks unchanged, 18 chunks before/after. Same saved source retains candidate IDs/catalog fingerprint. Runtime `9d3b36e7...3cec`; no provider, ingest, store or evaluator/dataset mutation.
The [claim counterfactual](../../benchmarks/results/narrative_claim_grounding_2026-09-11/README.md), runtime `cfb9dff5...28be6`, rejects metadata-only subject attribution but still accepts a deliberately retagged broadened paragraph. This is a semantic negative control, not solved faithfulness; all predecessor bytes remain.
Current compiler/protected execution require addressed claims and explicit subject references. Historical raw/flat inspection disables enforcement explicitly; old receipts/model outputs remain predecessor-only. Test-only address migration is not a production fallback or new human/model review.

Latest paid [claim run](../../benchmarks/results/narrative_claim_compiler_2026-09-11/RESULTS.md): clean `5962d1f7`, admission `966a0fa7...759a5` consumed.
Pro **10 calls**, retry **3**, runtime **3/7**, provider/execution exceptions **0**;
estimated **USD 0.212920 / 0.60**, billing unobserved. Three structured readings were
rejected for not repeating subject in text; one causal abstention was faithful, not complete.
Current [rendering replay](../../benchmarks/results/narrative_claim_rendering_2026-09-11/README.md), runtime `b9d31c60...70b0b`, uses unchanged first responses: **6/7**, retry/API **0**.
The three old accepted programs and causal abstention keep identical program/execution bytes.
Raw claim subject/text/quotes, candidates and frozen artifacts stay intact. Known-source
"당사" coreference and semantic contradictions remain unresolved; this is not new model accuracy.

## Independent pilot: immutable compiler-only predecessor

The [holdout protocol](../evaluation/independent_holdout_protocol.md) fixes 12 questions
over 대한항공, KT&G and CJ제일제당 2025. The user accepted unchanged provisional references
after qualified HTML review, not individual human source verification (still 0).
The source-preservation successor retains 15 numeric facts, 12 prose quotes and seven
descriptive row associations; original files and all 44,757 frozen numeric records stay
unchanged. [Repair receipt](../../benchmarks/results/independent_holdout_preparation_2026-09-10/preservation_repair_v1/README.md).

User-delegated admission `98956685...fd916` ran once on clean `7c7f079a`, unchanged runtime `7aa4adf2` / `5a74ff8d...9d7b`. [Result and source review](../../benchmarks/results/independent_pilot_compiler_2026-09-10/README.md).
Whole-filing catalogs (51,388 candidates) and question-authored requirements feed current
bounded cohorts. Gold reads are blocked in the runner. Two separate abstention-only SDK
rehearsals are byte-identical; provider budget/usage tests pass 16/16.

- Gemini 2.5 Pro: **21 calls**, **3 internal retries**, 12 questions attempted; transport errors 0.
- Runtime complete **7/12**; exact reference scalars **4/9 numeric questions** (8/21 outputs).
- Codex source review finds all **3 narratives incomplete/unfaithful in at least one respect**.
  This is not a new human or paid-judge score. Same-value summary evidence remains distinct;
  coarser source displays are source-selection/precision differences, not conversion errors.
- Cost estimate **USD 0.90074875 / 2.00**, without cache discount; billing unobserved.
  Compiler loop 1,109.637s includes whole-catalog work, not normal query latency measurement.
- OpenAI/embedding/store/planner/retrieval/judge calls and batch reruns: **0**.

No full-agent, ledger, release or untouched-source generalization claim. This later
period/subject repair does not rewrite that run's results, inputs, labels or source stores.

## Earlier full-agent evidence (immutable predecessor)

The [four-question full-agent run](../../benchmarks/results/diagnostic_four_full_agent_2026-09-09/README.md)
used clean `cf721258`, admission `a2bd7bdd...a311`, once.
API/runtime errors were zero and ledgers 4/4 ok; this was not four complete answers.

| Question group | Observed source outcome |
| --- | --- |
| LG context | Consolidated amount answered; requested-period local amount withheld |
| KB context | Bank-specific ratio cells selected |
| NAV narrative | Both requested themes covered |
| Celltrion narrative | Only liquidity theme from management discussion; credit theme and requested note scope missing |

Calls: Flash 10 + Pro 6 + OpenAI 21, retries 0, 177.599s;
usage-estimated USD 0.18370008 / 0.80, billing unobserved.
Offline numeric replay reproduced 2/2 programs/outputs; eight narrative quotes match
frozen source chunks, not proof of semantic completeness. Review `5a691fb5...6ac7`.
The two narrative questions used the old evidence/compression/validation path; its
completed aggregate status cannot establish question coverage. Approval exhausted.

The [KB successor store](../../benchmarks/results/kbf_parser_openai_store_2026-09-09/README.md)
has 2,110 vectors, 1,707 payloads and 51 parents, including 536 newly embedded inputs.
Its recorded publication/readback is strict-ready/non-degraded; all original files
were preserved. Embedding admission `e5aecbba...d567` is exhausted.
Application default `data/chroma_dart` is a different incomplete KB 2022 store with
52 missing payloads. Its manifest alone is not readiness, and it remains untouched.

[Reviewed-case evidence status](../evaluation/reviewed_case_evidence_status.md) indexes historical runs, fixture v2 provenance and catalog limits.
Those records do not establish current-build release readiness or unseen-question performance.

## Next work

- Historical [subject-context](../../benchmarks/results/narrative_subject_compiler_2026-09-11/RESULTS.md) and [retry-context](../../benchmarks/results/narrative_retry_compiler_2026-09-11/RESULTS.md) runs remain immutable source-exposed evidence, not current-head semantic success. Metadata-only attribution remains invalid.
- [Responsibility comparison](../../benchmarks/results/compiler_responsibility_compiler_2026-09-12/RESULTS.md) consumed manifest `436771c0...6c7b0`; result `0d6a6a9b...9f9f9e`. Same five inputs/plans, Pro 12, source conditions retained, repetition **4 → 1**, no live retry. Further repetition reduction is deferred; preserve distinct topics/conditions and do not add source-ID deletion rules. Company containment remains a separate characterized limit.
- [Server-count admission](../evaluation/provider_admission.md) is implemented as an opt-in ops guard: final SDK input, fixed **5120** output bound, separate count limits/allowance; no byte-ratio correction, fallback, SDK retry, redirect or runtime-default change.
  [Paid guard validation](../../benchmarks/results/server_count_validation_2026-09-14/RESULTS.md), consumed `b3474acd...6c24c` on clean `557177d8`/runtime `d7b52100`: counts **2** + Flash/Pro generation **1 each**, **4/4 HTTP 200**, retries **0**, 14.079s. Server count = input reservation = prompt usage **20 / 4,135**; full schema/system and output bound **5120** retained. Generation estimate **USD 0.01798725** + count allowance **0.12** (not billing) = accounted **0.13798725/0.20**; peak **0.17810725**, pending **0**. Runtime **161** / protected **63** intact; result `1142a959...3d3dc`/review `ceb447ef...d67b7` remain immutable, not semantic/full-agent validation.
  The [fixed-draft retry result](../../benchmarks/results/subject_selection_retry_2026-09-14/RESULTS.md) remains **3/4 pre-fixed criteria / 2/4 structural**, and full-agent `5295c516...99a14` remains **2/3**. [Subject-display grounding](../architecture/narrative_subject_display_boundary.md) and exact selected-source retry feedback are implemented; [saved-response replay](../../benchmarks/results/subject_display_grounding_2026-09-14/README.md) changes only line-break acceptance, preserving all raw responses and other three whole results, including NAV **41.4%**. New [pending full-agent admission](../../benchmarks/results/subject_grounding_full_agent_admission_2026-09-14/README.md), SHA `af784682bf86b817b078699c901c8e121b10c97463d596510318061ea4a2a8f0`, pins runtime `ed5e0736...ab22a` with the same three questions/order/stores/models/source criteria and fresh plans. Proposed cap **USD 1.60**; current controls **50/50**, two process receipts **4,612 bytes** identical (`77820aba...787d3`), **147** protected inputs and **23** source-store files intact. Both copied stores are strict-ready; provider **0**, no approval record/actual target created. Complete entity/group semantics and source-display visibility remain separate; no new model or release claim.
  [Measured predecessor](../../benchmarks/results/server_token_accounting_2026-09-14/RESULTS.md), consumed `1d067e26...bd3fa` on `0f97a533`: counts **20 / 4,135** matched prompt usage; old byte reservations **24,841 / 43,977** were excessive on these two inputs. **8/8 HTTP 200**, retries **0**, estimate **USD 0.01636975 / 0.30**; count tariffs/invoices unobserved, no universal schema-billing or framing rule.
  Frozen result `11a2640f...5ce87`/review `c0ddb285...09813` remain unchanged; prior approvals are consumed. Diagnostic capture stays outside answer/ledger/judge authority, and lost NAV drafts remain unrecoverable.
- Source-exposed regression, full-agent retrieval and semantic completeness stay distinct; ID/scope/number validation is not entailment. New reports are not indexed.
- Earlier paid admissions are consumed; only the new full-agent manifest is pending separate approval. No automatic rerun, fresh ingest, gold-ID oracle or validator relaxation.
- Acquisition ambiguity/pagination, complete vector/source text consistency, retired-helper removal,
  formula-wide rounding and default-store recovery remain separate work, not silently included fixes.

See [runtime contract](../architecture/agent_runtime_contract.md), [code map](codebase_map.md), [checked topology](runtime_flow_roles.md), and [experiment history](../history/experiment_history.md).
