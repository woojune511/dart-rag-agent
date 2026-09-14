# FinancialAgent Runtime Contract

Status: normative

This document defines the supported v1 public/storage and v2 internal graph contracts.
Superseded designs belong in [implementation history](../history/implementation_history.md) and [experiment history](../history/experiment_history.md).

## 1. Product and authority boundary

The single-agent `FinancialAgent` uses an LLM to interpret intent and evidence. Code owns arithmetic, unit conversion, dependency binding, candidate authority,
dedupe, ordering, validation, and ledger integrity. Every intent uses required-output planning and compilation. Code losslessly partitions the original query at mechanical sentence/line boundaries into `RequestUnitV1` addresses with exact text and Python-string spans; no semantic clause classifier or truncation. Every obligation declares required `request_unit_ids`; every unit needs at least one owner, and shared units are allowed. Labels name outputs, linked original text carries detailed instructions, and rationale stays diagnostic. Planner policy asks to keep an explanation with its qualifying conditions and all linked units, preserving independent requested topics and shared conditions. Shared subject/sentence/unit identity or a fixed output count is not a merge rule; this is a model instruction, not a code merge or semantic-dedup guarantee. Unknown/missing/malformed refs or unassigned units remain requirement errors and block all compiler calls without candidate exclusion or a new planner retry. There is no production legacy-assignment fallback. Planner `status=ok` requires a nonempty, fully linked plan, not semantic completeness or correct assignment. The original query remains visible; code never infers omitted meaning.

Company names, benchmark IDs, expected answers, report-specific phrases, and metric recipes may not control routing, retrieval, selection, compilation, execution, or rendering. Domain vocabulary belongs in reviewed ontology, policy, config, or data; fixed-year priorities and case-specific routing examples are not generic domain priors.

Evidence is authoritative over generated text. Numeric answers require registered candidates and validated program bindings. Source and calculated displays may
coexist, but their provenance must remain distinct.

Normalization and rendering share `UnitSpecV1`: source numbers multiply by its scale;
calculated displays divide by it. Direct values preserve source units/signs/precision;
non-finite values cannot yield slots, and precision comparisons use base units. Formula literals exclude booleans/overflow; scalar function arity is validated, with variable names independent of function positions.
Table-unit projection preserves inline and explicit column/annotated-row units (not bare row categories); conflicting axes stay unknown. Otherwise policy column labels select only among units declared in attached preceding/caption context.
Ambiguous mixed-unit cells never inherit the first table unit. `source_unit_hint` stays in identity/provenance; exact declarations/header evidence reach prompt and operands as `source_unit_provenance`. Original row quotes stay intact; synthesized row text uses effective units within the existing bound.
Corrected effective units change catalog-content fingerprints, not candidate IDs or hash algorithms; V2 binds the complete projection. Store/parser payloads and historical artifacts are not rewritten.
Compiler emits formula and `display_unit`, not `result_unit`; code infers dimensions.
Display priority: expression -> obligation -> inferred canonical unit (count: unitless).
Legacy `result_unit` is discarded on copied model ingress; public display fields stay intact.

Source signs stay intact. Compiler explains comparison target, transformations and formula in existing per-obligation `rationale`, using generic contrasts rather than a role enum.
Code never flips signs; undefined/uncertain comparisons stay unanswered. Offline oracles never drive retries or prove model accuracy.

Unsupported planner units remain recorded and block the affected island. Errors identify owner, candidate, location, and repair action. Compiler format errors keep the cohort; only
explicit dimension/scope/subject conflicts replace candidates, never unknowns or diagnostic prose.
Typed validation normalizes `null`/`none` only for optional planner text
(`display_unit`, `display_format`, `coupling_key`); real unsupported units still block their island.

## 2. Public result v1

`FinancialAgent.run()` returns `FinancialRunResultV1`:

```text
schema_version: "financial_run_result_v1"
agent_answer: AgentAnswer
review_trace: ReviewTrace | None
debug_bundle: DebugBundle | None
```

`include_review_trace=False` and `include_debug_bundle=False` are the defaults.
The result is not a `Mapping` and has no flat compatibility projection. Internal
consumers must read typed attributes. Explicit serialization uses
`FinancialRunResultV1.to_projection()`.

`AgentAnswer` contains the user answer, citations, routing summary,
`structured_result`, and `resolved_calculation_trace`. Review-only retrieval,
candidate, validation, retry, and ledger material belongs in `review_trace`.
Usage/calculation telemetry, opt-in `compiler_attempts` and `request_diagnostics` belong only in `debug_bundle`. `compiler_attempt_debug_v1` retains each schema-parsed model JSON before merge, the merged validation-input JSON before pruning, their UTF-8 SHA-256, island/attempt/active-owner/visible IDs, validation errors/locations and compile-valid owners, and exact retry-feedback text. JSON is local `model_dump()` serialization, not provider wire bytes or hidden reasoning. Programs remain diagnostic, not execution authority. Missing parsed responses stay `unavailable` with null programs and an error class, never reconstructed from exception bodies. `request_diagnostics_v1` immediately copies completed plan/retrieval/catalog phases, pending compiler prompts, observed attempts/island results and opt-in SDK request/settlement events. Only source/schema SDK fields are retained; HTTP options, headers and arbitrary error bodies are excluded. UTF-8 component sizes are separate SDK-call JSON serializations, not additive wire sizes or measured tokens. Available callback usage is copied on interruption; unavailable sources are null or a safe error class. Caller-owned `capture_request_diagnostics()` receives each debug-enabled run snapshot in `finally`, even when its original exception propagates; success includes the same copied snapshot in debug. Context-local, nested/concurrent request isolation uses neither agent-instance nor exception attributes. Capture is off by default, in-memory until the caller persists it; process crashes are not covered. Call/retry limits, prompts and execution authority are unchanged.

The HTTP response keeps its existing answer/citation/structured-result fields.
Review and debug fields appear only when requested. The internal result schema
version does not alter that wire shape.

## 3. Candidate visibility v1

Compiler authority uses frozen, slotted standard-library contracts:

- `OwnerCandidateVisibility`
- `EvidenceBundleOptionV1`
- `EvidenceBundleConstraintV1`
- `CandidateVisibilityV1`
- `CompilationEnvelopeV2`

Visibility stores catalog and cohort fingerprints, all visible candidate IDs,
and selectable IDs per obligation or requirement owner as tuples. Construction
copies caller inputs. Serialization is available only through explicit
projection methods.

The compiler creates visibility once. Validator and executor receive that same
object. There is no global-only `selectable_candidate_ids` execution path.

Before execution, the executor must verify:

1. the current catalog fingerprint equals the compile-time fingerprint;
2. the program fingerprint equals the validated program fingerprint;
3. the validation fingerprint equals the envelope fingerprint;
4. every binding is selectable for its declared owner.

V2 additionally binds the complete catalog contents (sorted by candidate ID),
ordered obligations, and query with `execution_content_fingerprint`. Changed
normalized numbers, dimensions, scope, source bytes, spans, or physical
provenance (including attached document contexts), request references or original query fail before revalidation or arithmetic as `execution_content_mismatch`.
Production has no V1 fallback. Historical catalogs/programs are never silently remapped to new identities.

Any mismatch fails closed as `visibility_mismatch` or `validation_drift`.
Execution must not overwrite immutable compile validation; validator-selected
IDs follow declared obligation order with first-occurrence dedupe.

## 4. Candidate applicability and coupling

Candidate applicability has exactly three states: `compatible`, `unknown_only`,
and `explicit_conflict`.

Each obligation/requirement may declare `SemanticTargetV1`: `local_subjects` are complete query-written subject identities, not whole request phrases/descriptive wrappers; `concept_keys` are ontology-backed and `metric_surfaces` query-visible.
Before fixing targets, the existing planner receives `source_axis_inventory_v1` from the same report-filtered, already-hydrated metadata as its section inventory. Whole row/column axes with literal query occurrences retain hierarchy, exact first-occurrence query spans and one observed table/row/cell or value reference; identical paths share one example per filing/section. At most 64 axes / 16,384 UTF-8 axis-list bytes appear in query-position/location order. Counts, omissions, fingerprint and bytes remain in `semantic_plan.source_axis_inventory`. This is a planning hint, not a subject classifier, name allowlist, quote or candidate authority; no scalar/body/alias extraction, new output schema, store access or model call. Empty/truncated hints do not establish absence or permit target rewriting.
The planner distinguishes names from descriptions. Full-name modifiers/groups remain identity; other conditions remain in exact request units and scope/requirements. Each input identifies its own subject. Code never strips suffixes, shortens names, clears targets or substitutes observed aliases; structural checks do not certify this interpretation. Keep only query-written bilingual spellings, never invented translations/entities. Filing `scope.company` is not local subject; unknown concepts get a planner note. Compiler retry cannot rewrite the frozen target, and strict cell identity/visibility are unchanged.

Located calendar labels resolve first, then fiscal columns using the existing row-ordinal/report-year mapping, then relative labels and generic roles. Fiscal columns precede row-derived `period_text`; repeated equivalent labels resolve once. Raw period surfaces remain identity/provenance, not an override.
Ambiguous/unanchored fiscal columns stay `unknown_only`; retained row-relative text cannot resolve them again in validation. Other ambiguous/unanchored numeric periods cannot borrow filing year. Relative-only comparisons need no invented year; parser-wide `period_labels`/`period_focus` remain unlocated hints.
Non-temporal headers stay in `source_period_surface`/`column_headers`, not `period`. `period_label_scope` distinguishes cell/source-period evidence from `unbound_table` hints in catalog, prompt and operand trace; IDs/raw bytes/catalog fingerprints stay intact.
Narratives may use filing-year document scope, but that scope cannot bridge a numeric period. A numeric period witness needs located period evidence and the same source context; missing period evidence requests program repair, not candidate exclusion.

The complete immutable candidate catalog is projected into generic fact views.
Numeric owner ranking compares scope/applicability, explicit local-subject, owner-kind, unit, metric, and physical-locality. Document-company matches are diagnostic only; filing scope rejects conflicts but adds no implicit value-subject bonus. Source-defined grouping remains separate.
Narrative exposure has separate `reading_state`, `reading_subject_state` and `reading_hint_state`; original applicability/metric/subject fields retain their existing meaning for diagnostics and bundle compatibility. All explicit conflicts still exclude candidates. Reading eligibility uses scope/unit checks, not whether a passage repeats the subject name. Within that tier, topic relevance precedes a literal mention; unknown scope cannot outrank an eligible scoped overview. Existing owner-local `retrieval_hints`, after removing declared subject/scope surfaces, may supply a shorter topic for the same body/context match mechanism. They do not inherit sibling/parent hints or rewrite `SemanticTargetV1`; numeric matching is unchanged. Any positive primary-topic or search-hint match shares one ordinal tier, with no keyword-count bonus. Only retained bundle/body/continuations, own axes and attached heading/caption/preceding context supply reading hints; filing metadata, inferred entities and hidden tails cannot supply hint evidence. Mentions have no minimum name length, alias inference or punctuation/word-joining normalization. Even a literal overlap within another name is not identity/attribution or quote authority. Subsequent rank factors are mention, owner kind, unit and neutral locality; prose and structured rows have equal reading eligibility. Reading exposure fields stay diagnostic-only, not compiler instructions; quote, subject, scope and numeric permissions remain independent.
Repeated words do not accumulate additive relevance or compensate for conflicts. Legacy subject inference excludes fragments of declared concepts/metrics and whole calendar (including abbreviated year), relative or fiscal period labels. This does not resolve a value's year or strip temporal substrings from entity names; explicit local subjects remain authoritative.
Numeric cohorts prefer `compatible` over `unknown_only`; narrative tiers apply that ordering to reading applicability, without upgrading underlying identity/scope or coupling authority. Explicit conflicts remain excluded. Numeric exact row/cell metric matches precede containment-only matches as ordinal tiers, not additive scores. Comparison keys remove parser footnotes, never semantic qualifiers; empty keys cannot match. Source axes, IDs and catalog fingerprints stay intact. Equal numeric tiers remain deterministic and source-diverse.
Within an equal narrative tier, budget is interleaved by document, section hierarchy, source and physical row, then candidate ID. Section paths use retained metadata/canonical anchors (excluding graph-relation suffix) or attached ancestor titles; missing document identity falls back to source identity. Grouping only allocates visibility, never merges IDs or grants scope authority. No format quota, preferred title vocabulary, extra call or semantic-coverage certification is implied.

`SourceBundleV1` is the source-reading unit: deterministic ID, source kind/anchor, context fingerprint, exact contiguous text, member IDs and local value spans. Same-source sentence values share a bundle. Long sentences split into maximal consecutive value-span groups within 420 characters; each window covers every member without cutting adjacent numeric spans or normalizing bytes. Each value has one window.
Table bundles share a physical table/row and retain row headers/cell provenance. Rows without a normalizable scalar remain reading-only narrative evidence; parser-located text-row contexts supply independent row readings when scalar records omit them. Existing numeric carriers also serve narratives, without duplicate reading candidates or relaxed scalar validation. Parser v2 uses leading THEAD/all-TH structure before row-text inference; text body rows are not promoted to headers. Table-attached paragraphs
also retain separate prose slices; table cells and metadata prefixes are not re-extracted as prose values.
Uniquely located numeric rows may carry adjacent textual rows within 420 characters, with exact source ID/span
in `source_context_provenance`. Context is not a new cell/role; it may supply existing text-match factors.
Repeated attachments select context deterministically within the same report/scope/cells; context enrichment does not rewrite cell identity.

Numeric selection is bundle-first: exclude `explicit_conflict`, prefer `compatible`
over `unknown_only`, and rank by the best member's existing factor vector. Each numeric
owner gets at most two bundles with every non-conflicting member visible together.
Period pairs/signs/neighboring operands are not split by a top-one cutoff; a shared
bundle's source text appears once per compiler payload, even across owners.

Narrative-bearing `semantic_program_candidate_payload_v8` presents lossless addressed surfaces in `source_readings`: enclosing headings, preceding context, independent bundle bodies, then following context. Numeric-only payloads retain v7. Only identical observed document/context attachments share a unit. Headings order by located parent depth/path, then formal ancestor before intermediate within that parent, then natural locator indices/span; title text never ranks them. This is heading hierarchy, not a full cross-tag XML document-order guarantee. Repeated contexts use `surface_ref`, not repeated text or concatenated source authority.
`source_bundles_by_id` and `source_contexts_by_id` index unchanged identities, spans, physical provenance and attachments; quote text appears only in readings. Candidate `attached_context_ids`, when present, restrict a shared bundle's context union to that member's own attachments. `document_provenance` separates filing metadata/anchors from quoteable sources; neither presentation order nor metadata resolves a subject.
Explicit prompt allowlists omit rank vectors, match counts and ranking diagnostics while traces retain them. Narrative-only owner cohorts omit empty fields (not explicit unknown states) and numeric-only template/retry instructions; numeric/mixed calls keep scalar contracts. Ordinary narrative rows use source selections; numeric row-description options are advertised only when the existing exact-axis/provenance validator accepts them, without changing its rules, exact `row_description_quote` or selection.
Paragraph/table contexts retain file SHA, XML locator and exact decoded-text span, bounded to 1200 characters each / 4800 per collection. Fresh cell-containing contexts add optional `source_segments`: `text_span` is local to retained `source_text`, with observed cell/row locators, no inserted whitespace or rowspan/colspan expansion. Inline text stays together; nested cells and inter-cell text stay separate. Clipping preserves the partition and original container offsets.
Cell-segment metadata travels through the existing sidecar and exact matching row bundles. V7 exposes independent segment text; v8 retains these hard partitions in its pieces. Narrative selections/scope quotes cannot cross cells; multiple selections may support one claim. V2/content fingerprints bind partitions. Address projection preserves candidate/context IDs, raw text and catalog-ID hashes; it creates no new evidence. Admission of previously unrepresented text rows remains separate. Old catalogs without segments are not auto-repaired. Attachment, owner authority and ranking/unit policies remain unchanged; no new call or semantic inference.
Direct/variable `context_bindings` and expression `source_display_context_bindings` cite attached context IDs and exact quotes for interpreted period/consolidation/segment/basis. Validator checks attachment, quote, known period consistency and explicit candidate conflicts; semantic applicability remains the compiler's responsibility. A binding-local `context_resolution` reaches execution/trace without changing raw catalog scope. Context errors repair the same cohort; accepted island bindings stay unchanged.

Selected prose `sentence_value` direct bindings, expression sources and source displays
require `source_assertions`: bundle/selected IDs and an exact contiguous substring
covering every referenced value span. Code verifies bundle membership, owner visibility,
exact bytes and span coverage before execution and fingerprints the
validated assertion; coverage follows declared obligation order. Table cells use row/cell provenance; narratives keep multi-evidence bindings.
Narrative schema requires a local `subject_bindings` registry (unique `subject_binding_id`, source-copied nonblank `subject`, nonempty `evidence_selections`) and nonempty `claims` (`subject_binding_id`, nonblank `text`, nonempty `fact_evidence_selections`). Every claim explicitly references this output's registry; duplicates, missing references and unused entries fail. No previous-claim inheritance, issuer fallback or deterministic attribution is permitted. Subject support may be shared; fact selections remain claim-local.
Each selection supplies `candidate_id`, `source_requirement_id`, `surface_id`, `first_piece_id`, `last_piece_id`. The address book contains only visible bodies and that candidate's own attached contexts. Lossless pieces use generic punctuation/line boundaries and a 160-character fallback within physical partitions; labels are not source bytes. Surface IDs bind source contents/provenance and piece offsets/partitions, excluding visible-member/attachment unions. Code extracts one exact ordered range; repeated text positions are distinct, and stale/hidden/reversed/cross-cell selections fail. No model quote, fuzzy repair or missing-selection whole-body fallback. Numeric source assertions remain unchanged.
Code validates selected subject support once and derives parent `text`, `evidence_bindings` and `candidate_ids` (schema-hidden) from each claim's fact and referenced subject selections. Existing exact containment is unchanged. Otherwise, only whitespace-layout equivalence within one already permitted selected range may ground the subject; non-whitespace characters, case, punctuation and internal word boundaries remain exact. One unambiguous physical occurrence is required, deduplicating overlapping selections of the same surface/span; no cross-range/cell joining, unselected search, alias inference or model/source rewriting. The renderer retains normalized text containing subject, otherwise prefixes `subject: text`; source excerpts are never normalized. Explicit flat projections must agree, IDs never widen. Current compiler/protected executor require addressed claims. Historical raw/flat inspection explicitly disables enforcement, not a production fallback; supplied V2 fingerprints still apply. Owner/requirement visibility, scope, row-description and group checks remain independent; blank requirement IDs grant only owner-level support.
Validator-owned `claim_readings` retain raw subject/text, `subject_binding_id`, optional `rendered_text`, separate fact `evidence` and `subject_evidence`, exact extracted text, addresses, candidate/context/bundle/physical provenance and surface-relative offsets plus container span (not XML offsets). Only new layout-only matches add `subject_grounding`: `match_kind=whitespace_layout`, unchanged `model_subject`, exact `source_subject`, Python-character `source_subject_span` and `evidence_index` into this reading's unchanged `subject_evidence` provenance. Exact-path trace bytes stay unchanged; V2 revalidation binds the witness. Only each claim's fact ranges/report year ground its numeric statements, never shared subject support, other claims or unselected tails. Address/subject/number errors carry owner/candidate/field location and repair detail; `ambiguous_narrative_subject` requests same-cohort program repair, never candidate exclusion. Retry stays bounded to one. Per-attempt history and untouched island bytes survive. Literal/layout support proves neither complete entity scope, attribution, causality nor completeness; interpretation remains in the existing compiler call.
An optional binding-local `row_description_quote` must be exact text in a row axis and its retained source, backed by document ID/year and physical table/row IDs. It excludes scalar tokens and authorizes document-scoped description, not measurement-period resolution. Known scope conflicts remain invalid; absent quotes retain the existing contract. Invalid quotes request same-cohort repair.
Only that quote and document year ground numbers for description-only use; each ordinary numeric carrier needs its own period, not another reading's filing scope. Validated `description_readings` retain exact quote/local span/source field and physical/document provenance in execution/evidence; description-only IDs never become scalar operands or raw-value evidence. Mixed numeric use keeps independent scalar authority. Catalogs/IDs are unchanged; exact text/ID checks do not certify semantic entailment.
Narrative bodies exclude complete recognized parser-prefix lines, including balanced brackets within metadata values. Mixed, unknown or malformed prefix-looking prose remains source text. Exact consecutive windows are at most 1200 characters, 4800 body characters per source; later windows are `source_continuation` context links serialized once. Offsets are source-candidate, not XML offsets; `source_body_coverage` exposes omitted tails. No extra IDs or changed ID/catalog hashing.
Retained `local_heading` reaches prompt rows separately as a parser hint, not subject or source-section authority. Located headings/preceding blocks in `source_readings` are addressable evidence: the compiler interprets local references jointly with body/row facts and explicitly links shared subject support when warranted; an explicit body subject is not overwritten by a heading. Initial/retry policy includes an anonymous non-authoritative address example. No fixed quote count, concatenated surface, automatic subject assignment or extra call. Co-occurrence and filing metadata do not establish attribution. V2 binds context; legacy metadata is never silently corrected, and exact source checks do not establish narrative attribution.
Fresh intermediate headings additionally carry exact paragraph-local spans, tracked with the existing heading stack. Full located scope (not the shortened hint) separates chunks and paragraph-to-table context; captions do not become enclosing scopes. Mixed/peer heading paragraphs are not wholesale adjacent evidence. Unlocatable normalized headings remain hints, never invented quotes.
Optional `source_contexts_json` preserves chunk heading context losslessly in the existing payload sidecar, including prose-only chunks; catalog ingress decodes it without rekeying candidates. Structured rows retain their table contexts. Existing context-match factors can read intermediate headings, but no entity inference, extra call or relaxation of numeric row/section/quote authority is added. Historical stores and results stay unchanged.
Retained body/context grounds matching. Current narrative numbers use validator-extracted claim fact ranges/report year in both claim-local and aggregate checks, never raw candidate bodies or shared subject support as a second authority. Description-only use remains limited to its validated descriptor/year; other claims and unselected body/context tails cannot ground a claim's numbers. Explicit historical flat inspection retains its original source/description checks. V2 binds source windows, contexts and claims. Meaning such as total, component, rate, or derived display is represented by obligation bindings/formula AST, not a role enum. No extra model call or keyword selection chooses body windows.

Every expression supplies nullable `source_display_candidate_id` and a nonblank `source_display_reason`; omission is a compiler format error. A selected source display passes the same authority,
scope, dimension, and exact-assertion checks as other sources. Its value and
source spelling are primary even when they differ from recomputation. The
answer then also labels the recalculated value. Numeric equivalence remains a
separate scaled-precision comparison, not a condition for source authority.
Dependencies use calculated values; public slots use display values. Each binding has a copied `input_rows` record of variable, source ID/kind and executed value/unit; repeated bindings stay separate.
Candidate/direct-dependency rows retain validated requirement/owner metadata, physical provenance and context. Derived inputs reference prior obligations/calculated displays, never fabricated cells.
`calculated_provenance` dedupes transitive input candidate IDs, row IDs and anchors in first-use order, excluding display/compatibility witnesses. General evidence IDs retain witnesses without extra authority.
Requirement scope fallback stays marked `period_source=requirement_scope`; source text stays source-only.

Section restrictions preserve requested wording separately from observed location. The existing planner can emit `source_section_bindings` with an owned `request_unit_id`, a unique exact `requested_text` excerpt and alternative observed `section_ids`. Code adds Python query spans, copied filing-qualified paths and the inventory fingerprint; model-supplied resolutions are schema-invalid. Empty selected IDs mean unresolved, not unrestricted. No new planner call or semantic alias dictionary.
The planner receives `source_section_inventory_v1` from already-loaded committed BM25 metadata filtered by the same pre-plan report predicate as retrieval. IDs bind explicit document identity and a located full path/prefix; company/year alone, body mentions, local headings, contexts and graph suffixes cannot create locations. At most 256 sections / 65,536 UTF-8 section-list bytes are exposed deterministically; omitted/unlocated counts and observed-only coverage remain visible, never a whole-report absence claim.
Each binding is an additional intersection, including parent/input restrictions; IDs within one binding are alternatives. Resolved membership requires the same filing and full path prefix. Existing `source_sections` remains a strict literal-title/path form: query-copied whole components, case/space and omitted ordinal handling only. Do not dual-write one restriction in both forms. An explicitly named observed path cannot resolve to a foreign path; no partial-title or foreign-section fallback.
Malformed, unowned/non-exact requests, unknown IDs and unresolved bindings remain requirement errors and block affected compiler islands, not independent outputs. Wrong/unlocated sources cannot spend their owner budgets. The original request and selected paths reach compiler initial/retry prompts and copied responsibility context; changing location cannot erase request qualifiers. This interpretation is an LLM responsibility, not mechanically certified semantic equivalence.
Validation independently checks direct/operand/display/compatibility/narrative sources and transitive dependency evidence against each owner. Source-defined groups copy the same bindings. V2 binds request excerpts/spans, selected IDs/locations and inventory fingerprint in the ordered obligations; mutation fails before execution. Candidates, ID/catalog hashing, store bytes and public HTTP shape are unchanged. Source scope is not a proof of entailment or parser correctness.
Numeric owners have capacity two source bundles, narrative requirements six candidates, and numeric compatibility narrative capacity two. Query-wide visibility stays bounded by 96 unique numeric and 32 narrative candidates. Bundle expansion is atomic: capacity overflow fails before compiler calls, never trims a bundle.

Coupling applies only when two or more distinct obligations share the same non-empty `coupling_key`. Multiple period operands of one derived obligation do not create a cross-obligation coupling mismatch. A true coupled basis conflict must fail validation.

Formula inputs bound to declared requirements or validated dependencies may span
physical sources, including a separately sourced display. Formula compatibility checks
semantic company/scope/segment/basis, not `context_fingerprint` equality. Owner visibility,
periods, units, assertions, explicit coupling and physical-row contracts remain enforced.

Physical table identity namespaces report-local `table_source_id` by explicit receipt/document ID before row/cell dedupe.
Raw parser IDs remain provenance; qualified IDs bind bundles, context checks, prompt and execution evidence. New table candidate IDs change; old artifacts do not.
Anonymous legacy tables use report scope plus content, not chunk order; indistinguishable anonymous copies cannot prove distinct filings. Hash algorithms stay intact.
`document_company` is not a value's local subject; a scope witness cannot cross known filing identity. For numeric cells with explicit `local_subjects`, direct bindings, required inputs (inheriting the parent target when absent) and source displays require complete query-declared identity in their own row/column axes. Case/spacing/parser-footnote differences are ignored, not punctuation or semantic qualifiers. An expanded descendant cannot borrow its parent's identity. Partial names/unknown aliases stay unresolved, not established equivalence; `candidate_subject_unresolved` requests the same-cohort retry without candidate exclusion. Context/compatibility/soft scope overrides cannot replace cell identity. Unspecified local subjects, prose assertions and multi-source narratives retain their existing contracts.

When two or more direct outputs have the same explicit local subject, compatible
declared scope, and at least one physical row containing a compatible candidate
for every output, the runtime creates an immutable evidence-bundle constraint.
Each complete row is an option, ordered by summed best owner positions, worst
position, then physical table/row ID. Code projects constrained cohorts through
the first option. Compatibility narratives remain auxiliary IDs. Only the active
option enters the prompt; ranked alternatives remain diagnostics.

Constrained outputs share one row. Validator and executor also reject mixing
rows as `evidence_bundle_mismatch`, independently of planner `coupling_key`.

A required `source_defined_group` narrative may join that bundle across tables
only when local subject and declared scope agree and its filing company, report
year, consolidation scope, and basis do not conflict with the direct row.
Explicitly compatible narrative context is used before unknown context. If no
complete physical row exists, the runtime does not infer a bundle or force
otherwise independent outputs together.

## 5. Internal graph state v2

`FinancialAgentStateV2` phases are `request`, `routing`, `requirements`,
`retrieval`, `candidates`, `compilation`, `numeric_result | narrative_result`,
`final_result`, and `ledger`.

Concrete phase input/output TypedDicts define static shapes, not runtime
immutability. Owners receive explicitly projected fields, never a full-phase
dictionary merge. Every graph node writes exactly one top-level phase key. Diagnostics stay inside
the phase that produced them; request-local observers may copy outputs/events outside state, never feed them back to any graph reader. A phase transition moves its downstream readers in
the same change; long-lived dual-write is forbidden.

Intermediate nodes do not write `tasks`, `artifacts`, or the final answer.
Numeric execution returns calculation rows, display slots, and evidence;
narrative validation returns scope/ID/number-checked text and evidence, not certified semantic entailment.
`assemble_ledger` records the finalized public answer, structured result,
trace, and narrative source material as one `LedgerSnapshot`. Aggregate status follows public `structured_result.status`; partial/incomplete results are not completed tasks. Ledger integrity is structural, not semantic completeness.
`assemble_final` is the only graph node that assembles answer, citations, and
structured result. The checked node/edge list is generated in
[runtime_flow_roles.md](../overview/runtime_flow_roles.md).
The final edges are `assemble_final → assemble_ledger → END`; `run()` packages
typed results and telemetry without modifying answers, citations, or evidence.

## 6. Compilation islands

Google phase routes forward explicit `max_output_tokens`, `thinking_budget`,
`provider_client_retries`, and `include_thoughts` to the SDK; zero/false must survive.
Omitted controls retain defaults. Zero retries permit only the initial HTTP attempt. `ProviderAdmissionError` is terminal across planning, routing, search, context generation and compiler/evidence helpers: propagate its first cause without fallback, another call or an evidence-insufficiency program.

Each answer obligation is a vertex. Islands connect only through a dependency on
another user-visible answer obligation, a shared non-empty `coupling_key`, or an
inferred evidence-bundle constraint. `depends_on` never names raw inputs; those
live in `evidence_requirements` and are not vertices. Projection drops an exact
own-requirement reference only after known answer IDs are resolved. Unknown,
self, and cyclic dependencies fail before compilation. Every formula dependency must be explicitly declared by its owner, even inside a shared island.
At most eight islands and all selectable ID unions are preflighted before calls, counting shared IDs once (numeric 96, narrative 32); owner quota sums are not reservations.
Every retry replacement checks the query-wide union, including accepted and not-yet-compiled islands. Overflow makes no call and preserves accepted bytes; bundles are never truncated.

Every initial/retry prompt declares `semantic_compilation_scope_v1`: active output IDs, their referenced `request_units_by_id` (exact text/spans in query order), original question as context only, bounded excerpts and no established document-wide absence. Request units are user instructions, never candidate/quote authority, ranking factors or coupling edges. Context-only restricts emitted owners, not linked detailed requirements; labels/rationale cannot substitute for them. Requested distinctions/relations/limitations belong in public claims. Complete candidate bodies do not establish document coverage; insufficient support requests missing/ambiguous, not full-report absence. This is a compiler instruction, not a semantic validator.
Multi-output queries additionally project `output_responsibility_context_v1` once after global preflight, passing immutable JSON through an explicit internal argument to narrative-bearing calls. Ordered outputs copy only ID/kind/label, request refs, local subjects, declared scope and source sections; shared exact request text/spans appear once. No candidates, evidence requirements, accepted answers, execution status or retrieval/rank hints enter this map. It describes planned responsibilities, not successful sibling outputs or new source/dependency authority. Initial/retry maps are identical while a narrative remains active; single-output and numeric-only calls add no context. Policy retains necessary shared conditions and independent topics, never merges/deletes by shared subject/request/source/wording. Global V2 already binds query/plan; no new schema field, graph phase or model call.
Islands compile sequentially in obligation order, with at most one internal retry:

- candidate validation failure excludes the rejected candidate's source bundle
  for that owner and promotes the next ranked bundle;
- assertion, AST, schema, or binding format failure retains the same cohort. Explicit
  missing/ambiguous with no owned error is terminal; undeclared omissions still retry.
If an evidence-bundle member needs retry, every member is retried together. Candidate
rejection rebuilds bounded cohorts and promotes the next complete row option when needed;
AST/schema/binding-format repairs retain the active option; an abstaining row stays atomic. Unretried abstentions survive targeted merge.

Retry targets and their selected assertions alone remain editable; unrelated retry assertions cannot revoke accepted evidence. `unvalidated_narrative_drafts` copies only targeted owners' subject registry and claims in original order/field locations, filtering both subject/fact links to currently owner/requirement-selectable IDs and counting omissions. Only structured `ungrounded_narrative_subject`/`ambiguous_narrative_subject` owner/location errors add `source_selection_check`: declared subject versus each remaining selection's exact text, addresses, surface-relative span and literal containment, resolved from the current prompt's visible address book. Invalid addresses return a resolution code without source text. The validator's same subject-grounding helper optionally reports layout-only correspondence (index into `selections`) or ambiguity/occurrence count; `contains_declared_subject` stays literal. This is read-only feedback, not new authority or attribution validation; no neighbor search, range expansion, concatenation or source normalization. Its repair instruction appears only with a check. Drafts confer no permissions, omit accepted outputs and are absent when unavailable. Compiler may correct/delete unsupported claims or abstain; no claim-count/semantic-coverage gate. Shared assertions retain untouched members and exact quotes. Accepted `depends_on` outputs are read-only
inputs projected through the same V2-authorized executor, using calculated rather than
source-display values. Failed execution yields no input. Dependency obligation IDs may
be bound as sources; attached candidate provenance never widens owner selection authority.

Unretried island program JSON stays byte-identical. Programs, missing/ambiguous IDs, and diagnostics merge in obligation order.
`semantic_candidate_stage_diagnostics_v9` records owner factors, bundle/member counts and fingerprints, row constraints, islands, call/retry counts, attempt-visible/context/dependency IDs/fingerprints/bytes, and assertion errors. Ranking diagnostics are observability-only, never compiler prompt input. In v7/v8, `serialized_context_bytes` measures the context metadata index; `serialized_candidate_bytes` includes reading surfaces/pieces/indices, not SDK schema. Per-attempt `output_responsibility_context_fingerprint` hashes compact UTF-8 context JSON; `serialized_output_responsibility_context_bytes` counts that JSON and `output_responsibility_prompt_bytes` includes its policy/framing. Absent context records empty fingerprint/zero bytes. Admission must inspect the final SDK request, not infer total size from candidate bytes.
Multi-island `rationale` deterministically projects final validation status, ordered valid/missing/ambiguous obligation IDs and error codes, not concatenated model prose.
Original explanations remain in island diagnostics as `program_rationale`, with island/owner IDs, not validated query-wide verdicts. Single-island rationale, including explicit abstention, stays unchanged.
Finalize the merged summary before freezing the V2 envelope; its program fingerprint includes the explanation. This rationale projection alone does not change model schema/prompt, selection, formulas or retry policy.

## 7. Retrieval boundary

Retrieval runs `build_plan → execute_searches → select_evidence → build_trace` inside one owner without changing the external graph node or search-result order.

`retrieval_debug_trace` records query bundles, filters, executed and reused
queries, selected chunks, policy decisions, and degraded mode. Seed evidence may
be preserved when graph expansion pushes it outside the final window only if it
satisfies the active operand and provenance contract. Search, supplements, seeds and final selection use one source filter; empty scoped results stay empty, and failures never authorize unfiltered retries. Explicit source-section restrictions use the union of output scopes; any unrestricted output keeps shared retrieval open, without widening per-owner compilation. BM25 supplements filter before truncation. Trace retains owner section declarations/counts. Narrative requirements inherit narrative ownership; format quotas fill remaining capacity from authorized ranked sources.
When shared retrieval is section-restricted, the existing membership predicate selects observed source IDs from report-filtered committed metadata **before** dense/BM25 top-K and RRF. The native filter groups stored `chunk_uid`/legacy `id` by available explicit document identity, intersects the original report filter, and is identical for primary/retry searches and both cache keys. Missing addressable IDs are counted, never invented; empty eligibility makes no embedding/backend call and does not establish document-wide absence. Unrestricted shared searches keep their original filter. `source_scope_search` records matching/eligible/unaddressable counts and the deterministic filter fingerprint; each executed query retains its actual filter. Final source checks and parent/input validation remain independent. No score, corpus IDF, query enrichment, candidate identity or store format changes.
Search-cache hits preserve retrieval mode/fallback reason and return owned deep copies. Narrative dedupe requires filing-qualified identity; an unidentified local chunk number cannot merge sources. Parser splitting preserves introductory prose as well as numbered fragments. XML recovery preserves literal ampersand text, predefined/numeric entities, CDATA, comments, processing instructions and quoted attributes. Explicit header/body data tables are not standalone unit hints, even with one small value; prior stored text is not rewritten.
Recognized standalone bracket peer headings update the local hierarchy outside title-specific policies, with existing date/table-caption handling retained. Paragraph-to-table adjacency cannot cross local-heading boundaries; table captions preserve enclosing scope in intermediate blocks only. New parsing may change chunk grouping/context, not stored predecessors or physical table records.

Canonical routing embeddings use a process-wide success cache keyed by canonical
file SHA-256, provider, model, and dimension. Unknown identity disables shared caching. Only exact-count, nonempty, finite, nonzero and correctly dimensioned batches are cached; cosine is scale-stable.
Invalid query vectors and nonterminal failures record degraded reasons; terminal admission errors propagate. Routing prompts use anonymous declarative examples, not inline company examples.

## 8. Store and ingest v1

`store_manifest.json` contains exactly:
`schema_version`, `collection_name`,
`embedding {provider, model_name, dimension}`, and
`ingest {profile_id, parser_schema_version, chunk_size, chunk_overlap}`.
Unknown/missing fields or non-exact identity make readiness false and query 503. Canonical parser identity is `financial_parser_v2_source_context`; v1 stores are not automatically adopted or relabelled. New header-derived IDs never replace historical artifacts.
Startup only reads identity; adopting a non-empty legacy store requires the
separate CLI's validated dry-run followed by an explicitly approved write.
Configured BM25-only mode is the sole identity exception and is exposed in
readiness, response, and retrieval trace. It requires persisted BM25 sources.

A manifest-less Chroma store with zero embeddings and pending operations may
initialize ingest after restart but is not query-ready. `IngestService` owns
fetch, parse, context generation, indexing, and manifest recording. Multi-report
ingest records the manifest after its first successful indexed batch so later
failure remains resumable. `FinancialAgent` exposes no ingest methods.

Source persistence builds the next graph from a deep copy. It atomically writes
the union of old/new payloads before replacing the graph, which is the commit
point; memory publishes only after success. Parents also persist before publish.
Readers load graph before payload. Missing referenced payloads and all lower
write failures propagate, including explicit backend persistence; old payloads are not automatically garbage-collected. Successful graph publication invalidates search caches; failed publication preserves the previous cache snapshot.

Startup and ingest completion check committed graph/vector coverage and payload
references. Missing or empty payload content and unidentified vector metadata
block readiness without blocking recovery ingest. Resume reconstructs missing
sidecars from stored contextual text and parser metadata, without repeating
context generation or embedding. Exact stored vector ID / parser chunk-ID
matches permit metadata-only repair; unidentified sources otherwise fail before
provider calls. Resume counts only actual new additions and records vector
progress immediately after each committed batch.

Benchmark-only in-progress cache metadata preserves a manifest-less partial
store only with exact cache/store signatures and explicit partial-resume policy;
it never grants query readiness.

Graph-based vector rebuilds use one expected manifest and publish only after index health; partial successors remain manifest-less.
Source-reparse successors pin original file hashes, fresh parser/prefix projection and the same embedding identity. Original indexes open only through working copies.
Vector reuse requires exact full input text with fresh parser metadata, not chunk-ID equality or historical candidate remapping. Missing vectors are explicit deduplicated inputs, never automatic provider calls.
Explicit resume binds prepared inputs/vectors. Exact graph/payload/parent/vector readback and dense probes precede manifest-last publication; a prepared bundle or prepublication receipt is not readiness.

## 9. API and optional surfaces

FastAPI creates `AppServices` in lifespan on `app.state`. Query, ingest, and
company DB reads/aggregation run in workers. The same operation lock encloses
query readiness checking, execution, and the response readiness snapshot.
Readiness failure is HTTP 503, not a wrapped 500. Ingest's finally-readiness
refresh also runs in its worker and lock. Health only reads the computed state:
`/api/health/live` is liveness; `/api/health/ready` and `/api/health` are readiness.
Typed `QueryRequest.report_scope` is forwarded without invented fields. Public query/ingest/companies failures expose generic messages and safe error-type/status diagnostics, never arbitrary SDK exception text.

Repository `.env` loads before settings; process environment wins and imports
do not mutate it. Experimental Streamlit serializes cached services with a
process-wide synchronous lock, including readiness refresh on ingest failure.
Per-query retrieval fallback is exposed as degraded without rewriting persistent
store readiness. Forced BM25-only startup never initializes dense embeddings;
new/verified-empty stores retain manifest-declared dense ingest initialization.

CORS requires an environment allowlist. Streamlit and MAS remain experimental.
Evaluator dependencies load only for actual evaluation; core imports may not
depend on ops/experimental modules.

## 10. Validation and release gate

Every runtime change runs focused tests, domain audit, import/topology, pycompile,
and `git diff --check`; candidate/compilation/public-result changes also run full unittest.

Provider validation requires separate manifest/cost approval, then one store-fixed
eval-only run with a 30-second heartbeat; no automatic retry or fresh ingest.
A release needs all approved questions complete, zero runtime errors, and ledger `ok`;
dataset governance and evaluator tolerance remain separate. Local success is not provider evidence.
Opt-in comparisons/admissions fix inputs/budgets and retain failures, without a release claim. `src.ops.provider_admission` records denied requests separately and preserves the first cause. Policies without server counting retain legacy SDK-request preflight/reservation and make no extra calls; the explicit [server-count extension](../evaluation/provider_admission.md) requires separate count authority/allowance, preserves exact generation input and output bounds, and has no failure fallback. Request observations label admission allowed/denied before transmission and completed/failed settlement afterwards; estimates are not billing. The compiler-only evaluator retains completed cases and an unexecuted `interrupted_case`; full-agent `RAGEvaluator` exports the caller-owned snapshot separately as `interrupted_run` on a graph exception. Partial plans, drafts, validations and usage remain diagnostic only: no answer, runtime trace, ledger or judge input is reconstructed. The normal artifact shape is unchanged when there is no interruption. Empty canonical trace/usage defaults on an interrupted row mean unavailable, not zero activity or an accepted incomplete answer. Error projections allow error/admission classes, numeric HTTP codes and standard RPC status names, never messages/headers/bodies. SDK budget receipts retain failed-generation reservations; process crashes and previously lost traces cannot be recovered. Frozen admission scripts/results remain immutable.
