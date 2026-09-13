# Project Status

Last updated: 2026-09-13

## Current implementation

The product is `FinancialAgent`, on `codex/reviewed-compiler-selection-gate`.
Latest full-agent [source-reading result](../../benchmarks/results/narrative_reading_full_agent_2026-09-13/RESULTS.md), run HEAD `ec9d4a20`/runtime `c247cb83`, remains **0/3 complete**, **1/5 outputs accepted**, ledger **3/3 ok**, API/execution exceptions **0**, estimated **USD 0.30784205/0.80** (billing unobserved). Admission `6ef93ac86c4a21b3f8b693359b1040058956af7116288a66278800150ebfdcc6` is consumed: Flash **6**, Pro **7**, OpenAI **26**, compiler retries **2**, run retry **0**. The [local number/relevance repairs](../../benchmarks/results/narrative_authority_relevance_2026-09-13/README.md), `fd0f74ed`/`93bab07c`, retain exact source authority and improve scoped reading exposure. Compiler/retry policy at `0a26b9db` teaches separate exact subject and fact bindings, with an anonymous example and unchanged validation. Full unittest **1,537/1,537** and the earlier seven-attempt replay are structural evidence; local repairs made no provider call or store/dataset mutation. The newer compiler-only outcome below does not rewrite the frozen full-agent result.
Latest [compiler-only result](../../benchmarks/results/subject_fact_compiler_2026-09-13/RESULTS.md), run HEAD `2d4802b3`/runtime `0a26b9db`: **7/9 structurally complete**, **9/11 outputs accepted**, Codex pre-fixed source criteria **7/9** (anonymous **6/6**, saved DART **1/3**). Pro **14 calls / 3 internal retries**, 198.542s, estimated **USD 0.4627425/0.90**, billing unobserved; API/execution exceptions **0**. Cloud explanation completes; NAV acquisition and CEL liquidity explanations remain withheld at quote/claim binding, despite relevant visible sources. Receipt `f86514bc...741429`: nine execution/final replays and eight initially accepted items byte-identical, all retry candidate payloads unchanged, **77** protected and **160** runtime files unchanged. No new runtime fix, planner/retrieval/embedding/store call or batch rerun; not a human/holdout/full-agent/ledger/release result.
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
- Initial/retry prompts explicitly limit active outputs and mark evidence as bounded
  excerpts. Source-copied claim subjects need not repeat in text; one renderer labels
  fragments while preserving full statements. Both numeric checks use validated claim quotes, preserving descriptor limits; quote/subject/number errors retain same-cohort
  repair, explicit detail and per-attempt validation history. Initial/retry policy teaches fact-first exact quotes and separate same-claim subject support, optionally repeating a candidate with its own context ID; never insert a subject, replace a pronoun or join surfaces. Examples are not evidence; co-occurrence cannot establish attribution. Opt-in `compiler_attempts` retain model/merged JSON, hashes, errors and feedback separately from accepted outputs. Retry still carries only targeted unvalidated drafts with visible links; no new call/schema, quote-count gate or entailment validator.
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

Python 3.13.13; full unittest **1,537/1,537** in 37.352s. Quote/claim/compiler/context/bundle focused **105/105**, including seven new anonymous construction tests. Domain audit **83**, import/topology/docs **24/24**, pycompile/diff pass. Controls exercise initial mixed/narrative prompts, executable example bindings, names/layout/spans, forged prefixes/pronoun replacement, requirement/owner boundaries and unchanged retry cohorts/accepted bytes; deliberate attribution/negation controls remain structurally valid, not semantically accepted. Structured-output schema SHA stays `8135b55c...f3fad0`; initial template adds 1,333 UTF-8 bytes (no new source payload or call). Read-only replay of seven frozen programs preserves prior local decisions/error codes and accepted numeric bytes; only repair detail changes. The earlier counterfactual receipt `27aac95f...b2b9df2` and all 77 protected files stay immutable. No new model-selection or semantic-completeness claim.
Thirteen new provider-free tests cover exact partition/addresses, schema/ownership errors, active-owner retry, unchanged cohorts/accepted bytes, V2 drift and request text not being evidence. Existing transport tests retain the intentionally incomplete semantic control.
Historical planner-free fixtures are not rewritten: temporary test copies add authored request assignments only. These are harness/execution regressions, not planner inference or new model choices.
The earlier full gate was **1383/1383** on `222ffba9`; six saved planner responses replay identically on that measured predecessor, not under the new required-field schema. Historical admission/result receipts remain immutable.
The [period/subject projection](../../benchmarks/results/period_subject_boundary_2026-09-10/v2/README.md) remains bound to `3d3f64cd`; [reading/selection replay](../../benchmarks/results/narrative_reading_selection_2026-09-11/README.md) to `cb6ebb3a...da7ba`. Neither is current-head model output.

The [counterfactual](../../benchmarks/results/narrative_row_description_2026-09-11/README.md) removes the carrier-period error with three authored quotes; two other responses remain unchanged. This is not new compiler output or semantic success.
The [section-authority counterfactual](../../benchmarks/results/requested_source_sections_2026-09-11/README.md) rejects two foreign-section CJ IDs without new planner/compiler output; runtime `f95f3cd2...705b`.
The [source-local probe](../../benchmarks/results/local_heading_scope_2026-09-11/README.md) corrects inherited headings in memory: 27 source/table blocks unchanged, 18 chunks before/after. Same saved source retains candidate IDs/catalog fingerprint. Runtime `9d3b36e7...3cec`; no provider, ingest, store or evaluator/dataset mutation.
The [claim counterfactual](../../benchmarks/results/narrative_claim_grounding_2026-09-11/README.md), runtime `cfb9dff5...28be6`, rejects metadata-only subject attribution but still accepts a deliberately retagged broadened paragraph. This is a semantic negative control, not solved faithfulness; all predecessor bytes remain.
Current compiler/protected execution require claims. Historical flat replay explicitly marks enforcement off; fixture v3 adds agent-authored witnesses without changing v2 sources, questions, numeric programs, expected outcomes or selected IDs. Neither is new human/model review.

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

- [Located-heading successor](../../benchmarks/results/located_heading_context_2026-09-11/v2/README.md): intermediate titles become exact quotes. Six unchanged anonymous inputs/14 visible IDs and catalog fingerprints preserved; metadata-only issuer claims still fail.
  [Subject-context result](../../benchmarks/results/narrative_subject_compiler_2026-09-11/RESULTS.md): Pro 10 calls/3 retries, runtime 7/7, fixed-criterion Codex source review 1/7, estimated USD 0.2632575/0.60, billing unobserved; API/execution errors 0. Admission consumed; ten responses replay identically without API.
  [Retry-context predecessor](../../benchmarks/results/narrative_retry_compiler_2026-09-11/RESULTS.md), runtime `ef065b7b...f957a`, consumed `4a1a66f8...8c500`: Pro **10 calls/3 retries**, runtime **6/7**, estimated **USD 0.29252125/0.60**, billing unobserved. Narrow source criteria **1/7**, not full-answer faithfulness. All three retries received their seven draft claims; one repeats a title/body quote error, one fixes the quote but not subject interpretation. Ten responses replay identically without API; usage reconciles and 58 protected files remain unchanged. This frozen outcome is not rewritten by the v7 comparison below.
- [Responsibility comparison](../../benchmarks/results/compiler_responsibility_compiler_2026-09-12/RESULTS.md) consumed manifest `436771c0...6c7b0`; result `0d6a6a9b...9f9f9e`. Same five inputs/plans, Pro 12, source conditions retained, repetition **4 → 1**, no live retry. Further repetition reduction is deferred; preserve distinct topics/conditions and do not add source-ID deletion rules. Company containment remains a separate characterized limit.
- [Eight anonymous boundary tests](../../tests/test_narrative_binding_boundaries.py) reproduce list-format quote drift, missing claim-local subject support and whole-binding withholding; authored repairs preserve facts/other islands, while automatic pruning can omit requested content. Related focused gate **55/55**, no provider calls. [Source-address/shared-subject design](../architecture/narrative_evidence_address_design.md) is **proposed, not implemented**. Next: lossless address projector/resolver, then one coordinated narrative schema/reader switch; no quote normalization, implicit subject inheritance, silent partial acceptance or extra LLM call. Runtime and [consumed paid result](../../benchmarks/results/subject_fact_compiler_2026-09-13/RESULTS.md) remain unchanged; numeric evidence and old receipts stay immutable.
- Source-exposed regression, full-agent retrieval and semantic completeness stay distinct; ID/scope/number validation is not entailment. New reports are not indexed.
- Paid admissions, including the latest compiler-only packet, are consumed. New paid work/store preparation needs scoped authority and
  a current manifest; no automatic rerun, fresh ingest, gold-ID oracle or validator relaxation.
- Acquisition ambiguity/pagination, complete vector/source text consistency, removal of
  retired narrative helpers, formula-wide rounding propagation, and default-store
  recovery are separate bounded work, not silently included fixes.

See [runtime contract](../architecture/agent_runtime_contract.md),
[code map](codebase_map.md), [checked topology](runtime_flow_roles.md),
and [experiment history](../history/experiment_history.md).
