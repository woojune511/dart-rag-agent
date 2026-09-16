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

Normalization and rendering share `UnitSpecV1`: source numbers multiply by its scale; calculated displays divide by it. Direct values preserve source units/signs/precision;
non-finite values cannot yield slots, and precision comparisons use base units. Formula literals exclude booleans/overflow; scalar function arity is validated, with variable names independent of function positions.
Table-unit projection preserves inline and explicit column/annotated-row units (not bare row categories); conflicting axes stay unknown. Otherwise policy column labels select only among units declared in attached preceding/caption context.
Ambiguous mixed-unit cells never inherit the first table unit. `source_unit_hint` stays in identity/provenance; exact declarations/header evidence reach prompt and operands as `source_unit_provenance`. Original row quotes stay intact; synthesized row text uses effective units within the existing bound.
Corrected effective units change catalog-content fingerprints, not candidate IDs or hash algorithms; V2 binds the complete projection. Store/parser payloads and historical artifacts are not rewritten.
Compiler emits formula and `display_unit`, not `result_unit`; code infers dimensions. Display priority: expression -> obligation -> inferred canonical unit (count: unitless).
Legacy `result_unit` is an offline/internal projection concern, not a production Compiler field.

Source signs stay intact. Compiler explains comparison target, transformations and formula in diagnostic `rationale`, using generic contrasts rather than a role enum.
Production calculations require nullable `comparison_request_unit_id`. A directed comparison selects an owned request unit and binds expression-local variables `reference` and `target`; those names must be bound and used by the unchanged formula validator. Code copies the unit's exact text/Python span and endpoint source/requirement IDs into `comparison_resolution`, recomputed on validation and covered by existing V2 fingerprints. No model-written request quote, candidate-role enum, inferred endpoint, formula rewriting or extra call. Null is an explicit model choice for other calculations; historical formulas acquire no inferred comparison declaration through offline transport.
Input period labels, chronological order and listing order do not set direction. The selected request unit, endpoint assignment, transformations and formula remain model interpretations: `request_binding_not_semantic_equivalence` validates linkage, not correct meaning. Consistently reversed assignments/formulas remain semantic negatives; null does not certify non-comparison intent. For direct lookup, distinguish a reported row from unrequested aggregation using full axes/context; related/equal-valued rows alone establish neither ambiguity nor inclusion. Genuine uncertainty stays unanswered, with no forced row or retry.
Code never flips signs; undefined/uncertain comparisons stay unanswered. Offline oracles never drive retries or prove model accuracy.

Production calculations require a nonempty `formula` array of `{operation, arguments}` steps. The final step is the result; every earlier step must contribute. Arguments are source/dependency `{variable}` references, strictly earlier one-based `{step}` references, neutral strings `0`/`1`/`100`, inline `{value, request_unit_id, interpretation}` quantities, or `binding_count`. Operation-specific schema enforces arity: ordered binary add/subtract/multiply/divide/power, unary identity/positive/negative/abs/exp, one-or-two-argument round/log, and min/max with 2–96 arguments. No punctuation tokens, recursive expression schema, model step IDs or separate request-input list. Non-neutral quantities require their owned address and nonblank interpretation in place; bare numbers/missing proofs are invalid. Whole-instruction linkage is not quantity meaning or unique occurrence; wrong interpretations remain semantic negatives. Algebraic equivalence need not explicitly expose a request scalar, so this is not semantic proof completeness.
`financial_formula_wire` rechecks shape/arity/references and assembles only the stated operations into the existing arithmetic AST. Code supplies parentheses without folding, reordering or repairing a choice. Transport bounds are 64 steps and 4,096 expanded arithmetic nodes, checked before joining shared subexpressions; overflow, self/forward references and unused steps fail without truncation. Inline quantities lower to collision-free step/argument-position names and exact complete owned request text; a shared step reuses its original proof. `binding_count` counts source/dependency bindings only. The existing AST, variable-set equality, source/physical/unit validator and arithmetic engine remain authoritative. Code never infers a value, inserts a missing proof or repairs syntax. Format/request/reference errors identify the output and argument location and keep the same cohort; they never exclude candidates. Neutral-literal policy is unchanged.
Internal expressions retain named `request_inputs`, optional `binding_count_variable` and validator-recomputed `constant_resolutions` (value, code-owned origin, exact request spans, `request_binding_not_semantic_equivalence` or `binding_cardinality`). V2 binds lowered formula, proofs, resolutions and query; scalar proofs remain separate from physical `input_rows` and cannot replace required evidence/dependencies. Accepted retry outputs/assertions/calculated inputs stay byte-identical. Legacy internal constants retain offline exact quote/use checks; mixed declarations are invalid. Explicit authored-fixture projection may express an existing AST as steps and inline already-declared proofs; invalid/missing/unused proofs stay invalid and sampled responses are never transformed. Production has no infix-token/free-string/named-list fallback and adds no model call. Schema admissibility proves neither model generation stability, correct operands/operators, reduced size nor latency.

Production Planner schema uses nested `anyOf` for numeric and narrative obligations, preserving internal/public field keys. Numeric outputs retain their declared `display_unit`; narrative generation requires the empty-string literal and uses `display_format` for presentation. Requested facts remain in linked request/evidence requirements, with separately requested scalar outputs kept numeric. Historical/internal rows are never silently coerced or rewritten.
Unsupported numeric planner units remain recorded and block the affected island; existing preflight checks still reject invalid historical rows. Typed validation retains `null`/`none` normalization only for optional planner text (`display_unit`, `display_format`). Errors identify owner, candidate, location, and repair action. Compiler format errors keep the cohort; only explicit dimension/source-condition conflicts replace candidates, never free subject wording, unknowns or diagnostic prose. Free-string coupling keys are not planner fields.

## 2. Public result v1

`FinancialAgent.run()` returns `FinancialRunResultV1` with
`schema_version="financial_run_result_v1"`, `agent_answer: AgentAnswer`,
`review_trace: ReviewTrace | None`, and `debug_bundle: DebugBundle | None`.

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

Exposure ranking and source authority are separate. Owner quotas select the
visible bundle union; `exposure_candidate_ids` records that allocation. Each
owner may select visible sources satisfying its report, section, period,
consolidation and unit conditions, independently of another owner's topic rank.
Unknown fields still need execution-time grounding. Retry exclusions, atomic
physical-row choices and source-defined complete-row selections cannot be
widened by sharing. Requirement periods override output periods; section
restrictions intersect. Parent visibility includes its required inputs, without
granting those inputs to other requirements. No hidden source is admitted.

Visibility stores catalog and authority-cohort fingerprints, all visible candidate IDs,
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

## 4. Exposure ranking, source interpretation and physical constraints

Candidate applicability has exactly three states: `compatible`, `unknown_only`,
and `explicit_conflict`.

Each obligation/requirement may declare `SemanticTargetV1`: `local_subjects` preserve query-written targets and modifiers for retrieval/reading, never a source-name allowlist; `concept_keys` are ontology-backed and `metric_surfaces` query-visible.
Before fixing targets, the existing planner receives `source_axis_inventory_v1` from the same report-filtered, already-hydrated metadata as its section inventory. Whole row/column axes with literal query occurrences retain hierarchy, exact first-occurrence query spans and one observed table/row/cell or value reference; identical paths share one example per filing/section. At most 64 axes / 16,384 UTF-8 axis-list bytes appear in query-position/location order. Counts, omissions, fingerprint and bytes remain in `semantic_plan.source_axis_inventory`. This is a planning hint, not a subject classifier, name allowlist, quote or candidate authority; no scalar/body/alias extraction, new output schema, store access or model call. Empty/truncated hints do not establish absence or permit target rewriting.
The planner distinguishes names from descriptions. Full-name modifiers/groups remain identity; other conditions remain in exact request units and scope/requirements. Each input identifies its own subject. Code never strips suffixes, shortens names, clears targets or substitutes observed aliases; structural checks do not certify this interpretation. Keep only query-written bilingual spellings, never invented translations/entities. Filing `scope.company` is not local subject; unknown concepts get a planner note. Compiler retry cannot rewrite the frozen target, and strict cell identity/visibility are unchanged.

`year` is the report's business year, not its receipt calendar year or automatically a value's measurement period. Located calendar labels resolve first, then fiscal columns using the existing row-ordinal/report-year mapping, then relative labels and generic roles. Fiscal columns precede row-derived `period_text`; repeated equivalent labels resolve once. Raw period surfaces remain identity/provenance, not an override.
Ambiguous/unanchored fiscal columns stay `unknown_only`; retained row-relative text cannot resolve them again in validation. Other ambiguous/unanchored numeric periods cannot borrow document year alone. Relative-only comparisons need no invented year; parser-wide `period_labels`/`period_focus` remain unlocated hints.
Non-temporal headers stay in `source_period_surface`/`column_headers`, not `period`. `period_label_scope` distinguishes cell/source-period evidence from `unbound_table` hints in catalog, prompt and operand trace; IDs/raw bytes/catalog fingerprints stay intact.
Narratives may use report-year document scope, but that scope alone cannot bridge a numeric period. A numeric period witness needs located period evidence and the same source context. For attached `context_evidence.resolves` period choices, the exact selected quote must independently resolve one calendar year using existing period policy and the candidate's business-year anchor, matching the declared value. A model-written year cannot replace missing/ambiguous/unanchored quote evidence. Explicit source years need no business-year anchor and take precedence over relative labels. Unresolved catalog periods remain eligible for this Compiler-selected proof; no context is selected automatically. Invalid proofs request program repair, not candidate exclusion.

The complete immutable candidate catalog is projected into generic fact views.
Numeric owner ranking compares scope/applicability, explicit local-subject, owner-kind, unit, metric, and physical-locality. Document-company matches are diagnostic only; filing scope rejects conflicts but adds no implicit value-subject bonus. Source-defined grouping remains separate.
For declared numeric subjects, a complete non-temporal own row/column label occurring as a word-bounded literal phrase in the target supplies `numeric_subject_hint`. Unknown subjects with this hint rank between exact correspondence and no hint; `subject_state`, applicability and source authority do not change. Case/whitespace/parser annotations may normalize comparison only; qualifiers and word separation remain. No target shortening, alias/translation inference, body/context/metadata borrowing or cross-axis joining. Repetition adds no score. Hints stay out of Compiler input; source interpretation remains required.
Narrative exposure has separate `reading_state`, `reading_subject_state` and `reading_hint_state`; original applicability/metric/subject fields retain their existing meaning for diagnostics and bundle compatibility. All explicit conflicts still exclude candidates. Reading eligibility uses scope/unit checks, not whether a passage repeats the subject name. Within that tier, topic relevance precedes a literal mention; unknown scope cannot outrank an eligible scoped overview. Existing owner-local `retrieval_hints`, after removing declared subject/scope surfaces, may supply a shorter topic for the same body/context match mechanism. They do not inherit sibling/parent hints or rewrite `SemanticTargetV1`; numeric matching is unchanged. Any positive primary-topic or search-hint match shares one ordinal tier, with no keyword-count bonus. Independent of complete subject mentions, `reading_joint_hint_state` may use one literal term from an explicit subject and a different term from this owner's scope/subject-stripped search hints in the same retained body or attached context partition. Terms have at least two characters and a letter; period-only terms and subject terms already present in original/resolved metric, concept-alias or scope fields are excluded. Nested spellings or overlapping occurrences cannot form a pair, and separate contexts/cells never join. Unpartitioned structured body renderings cannot supply this new joint signal; existing reading rules stay intact. A pair supplies one topic tier and one request-anchor tier, without repetition bonuses; a complete subject mention cannot disable that independent topic signal, and a bare mention without a pair gains no topic tier. Within a positive-topic tier, a literal subject plus independently matched primary/search topic precedes a joint-pair fallback or bare mention; topic-only evidence follows anchored evidence. These are ordinal tiers, not additive keyword counts. Full targets, `reading_subject_state`, identity/applicability and source permissions remain unchanged. This is lexical co-occurrence, not shortened-name/alias inference, attribution or completeness proof. Only retained bundle/body/continuations, own axes and attached heading/caption/preceding context supply reading hints; filing metadata, inferred entities and hidden tails cannot supply hint evidence. Mentions have no minimum name length, alias inference or punctuation/word-joining normalization. Even a literal overlap within another name is not identity/attribution or quote authority. Subsequent rank factors are mention, owner kind, unit and neutral locality; prose and structured rows have equal reading eligibility. Reading exposure fields stay diagnostic-only, not compiler instructions; quote, subject, scope and numeric permissions remain independent.
Repeated words do not accumulate additive relevance or compensate for source conflicts. Ranking subject inference excludes fragments of declared concepts/metrics and whole calendar (including abbreviated year), relative or fiscal labels. This neither resolves a value's year nor strips substrings from names; explicit subjects remain reading targets, not source-name authority. Numeric cohorts prefer `compatible` over `unknown_only`; narrative tiers apply that ordering to reading applicability, without upgrading underlying identity/scope or coupling authority. Explicit conflicts remain excluded. Numeric exact row/cell metric matches precede containment-only matches as ordinal tiers, not additive scores. Comparison keys remove parser footnotes, never semantic qualifiers; empty keys cannot match. Source axes, IDs and catalog fingerprints stay intact. Equal numeric tiers remain deterministic and source-diverse.
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

Canonical presentation uses addressed narrative readings (v8) and numeric bundles (v7); production projects both to `semantic_program_candidate_payload_v9` short references. `source_readings` orders enclosing headings, preceding context, bodies, then following context. Only identical observed document/context attachments share a unit. Headings order by located parent depth/path, formal before intermediate within that parent, then natural locator/span; title text never ranks them. This is hierarchy, not a full cross-tag XML order guarantee. Repeated contexts use `surface_ref`, not concatenated source authority.
`source_bundles_by_id` and `source_contexts_by_id` index unchanged identities, spans, physical provenance and attachments; quote text appears only in readings. Candidate `attached_context_ids`, when present, restrict a shared bundle's context union to that member's own attachments. `document_provenance` separates filing metadata/anchors from quoteable sources; neither presentation order nor metadata resolves a subject.
Prompt allowlists omit all per-owner ranking matches, vectors and counts; traces retain them. Only source-condition permissions authorize selections. Narrative-only cohorts omit empty fields (not explicit unknowns) and numeric instructions; numeric/mixed calls retain scalar contracts. Numeric row-description options require the existing exact-axis/provenance validator.
Paragraph/table contexts retain file SHA, XML locator and exact decoded-text span, bounded to 1200 characters each / 4800 per collection. Fresh cell-containing contexts add optional `source_segments`: `text_span` is local to retained `source_text`, with observed cell/row locators, no inserted whitespace or rowspan/colspan expansion. Inline text stays together; nested cells and inter-cell text stay separate. Clipping preserves the partition and original container offsets.
Cell-segment metadata travels through the existing sidecar and exact matching row bundles. V7 exposes independent segment text; v8 retains these hard partitions in its pieces. Narrative selections/scope quotes cannot cross cells; multiple selections may support one claim. V2/content fingerprints bind partitions. Address projection preserves candidate/context IDs, raw text and catalog-ID hashes; it creates no new evidence. Admission of previously unrepresented text rows remains separate. Old catalogs without segments are not auto-repaired. Attachment, owner authority and ranking/unit policies remain unchanged; no new call or semantic inference.
Lowered direct/variable `context_bindings` and expression `source_display_context_bindings` cite attached context IDs and exact quotes for interpreted period/consolidation/segment/basis. Validator checks attachment, quote, known period consistency and explicit candidate conflicts; semantic applicability remains the compiler's responsibility. A binding-local `context_resolution` reaches execution/trace without changing raw catalog scope. Context errors repair the same cohort; accepted island bindings stay unchanged.

Selected prose direct/input/display values require internal `source_assertions`: lowering resolves the permitted source_ref to its existing bundle-local value span and copies that full exact substring, including retained signs/units. There is no model-written value quote, range expansion or neighboring-value inference; absent spans fail. Validator independently checks membership, owner authority, bytes and coverage, then fingerprints the assertion in output order. Source/metric interpretation remains separately grounded. Tables use physical row/cell provenance; narratives retain multiple evidence sources.
The lowered internal narrative program has a local `subject_bindings` registry and nonempty claims; the model uses nested subjects/support/claims instead. Code assigns unique subject links and rejects duplicate/missing/unused internal links. No previous-claim inheritance, issuer fallback or deterministic attribution is permitted. Subject support may be shared; fact selections remain claim-local.
Each narrative selection supplies `candidate_id`, `source_requirement_id`, `surface_id`, `first_piece_id`, `last_piece_id`. The address book contains only visible bodies and that candidate's own attached contexts. Lossless pieces use generic punctuation/line boundaries and a 160-character fallback within physical partitions; labels are not source bytes. Surface IDs bind source contents/provenance and piece offsets/partitions, excluding visible-member/attachment unions. Code extracts one exact ordered range; repeated text positions are distinct, and stale/hidden/reversed/cross-cell selections fail. No model quote, fuzzy repair or missing-selection whole-body fallback. Numeric assertions retain their independent span contract.
Code validates selected subject support once and derives parent `text`, `evidence_bindings` and `candidate_ids` (schema-hidden) from each claim's fact and referenced subject selections. Existing exact containment is unchanged. Otherwise, only whitespace-layout equivalence within one already permitted selected range may ground the subject; non-whitespace characters, case, punctuation and internal word boundaries remain exact. One unambiguous physical occurrence is required, deduplicating overlapping selections of the same surface/span; no cross-range/cell joining, unselected search, alias inference or model/source rewriting. The renderer retains normalized text containing subject, otherwise prefixes `subject: text`; source excerpts are never normalized. Explicit flat projections must agree, IDs never widen. Current compiler/protected executor require addressed claims. Historical raw/flat inspection explicitly disables enforcement, not a production fallback; supplied V2 fingerprints still apply. Owner/requirement visibility, scope, row-description and group checks remain independent; blank requirement IDs grant only owner-level support.
Validator-owned `claim_readings` retain raw subject/text, `subject_binding_id`, optional `rendered_text`, separate fact `evidence` and `subject_evidence`, exact extracted text, addresses, candidate/context/bundle/physical provenance and surface-relative offsets plus container span (not XML offsets). Only new layout-only matches add `subject_grounding`: `match_kind=whitespace_layout`, unchanged `model_subject`, exact `source_subject`, Python-character `source_subject_span` and `evidence_index` into this reading's unchanged `subject_evidence` provenance. Exact-path trace bytes stay unchanged; V2 revalidation binds the witness. Only each claim's fact ranges/report year ground its numeric statements, never shared subject support, other claims or unselected tails. Address/subject/number errors carry owner/candidate/field location and repair detail; `ambiguous_narrative_subject` requests same-cohort program repair, never candidate exclusion. Retry stays bounded to one. Per-attempt history and untouched island bytes survive. Literal/layout support proves neither complete entity scope, attribution, causality nor completeness; interpretation remains in the existing compiler call.
An optional binding-local `row_description_quote` must be exact text in a row axis and its retained source, backed by document ID/year and physical table/row IDs. It excludes scalar tokens and authorizes document-scoped description, not measurement-period resolution. Known scope conflicts remain invalid; absent quotes retain the existing contract. Invalid quotes request same-cohort repair.
Only that quote and document year ground numbers for description-only use; each ordinary numeric carrier needs its own period, not another reading's filing scope. Validated `description_readings` retain exact quote/local span/source field and physical/document provenance in execution/evidence; description-only IDs never become scalar operands or raw-value evidence. Mixed numeric use keeps independent scalar authority. Catalogs/IDs are unchanged; exact text/ID checks do not certify semantic entailment.
Narrative bodies exclude complete recognized parser-prefix lines, including balanced brackets within metadata values. Mixed, unknown or malformed prefix-looking prose remains source text. Exact consecutive windows are at most 1200 characters, 4800 body characters per source; later windows are `source_continuation` context links serialized once. Offsets are source-candidate, not XML offsets; `source_body_coverage` exposes omitted tails. No extra IDs or changed ID/catalog hashing.
Retained `local_heading` is a parser hint, not subject/section authority. Located headings and preceding blocks are addressable evidence: Compiler interprets them with body/row facts and supplies subject support when warranted, without overwriting explicit body subjects. No fixed quote count, concatenated surface, automatic subject assignment or extra call. Co-occurrence/filing metadata do not establish attribution. V2 binds context; legacy metadata is never silently corrected.
Fresh intermediate headings additionally carry exact paragraph-local spans, tracked with the existing heading stack. Full located scope (not the shortened hint) separates chunks and paragraph-to-table context; captions do not become enclosing scopes. Mixed/peer heading paragraphs are not wholesale adjacent evidence. Unlocatable normalized headings remain hints, never invented quotes.
Optional `source_contexts_json` preserves chunk heading context losslessly in the existing payload sidecar, including prose-only chunks; catalog ingress decodes it without rekeying candidates. Structured rows retain their table contexts. Existing context-match factors can read intermediate headings, but no entity inference, extra call or relaxation of numeric row/section/quote authority is added. Historical stores and results stay unchanged.
Retained body/context grounds matching. Current narrative numbers use validator-extracted claim fact ranges/report year in both claim-local and aggregate checks, never raw candidate bodies or shared subject support as a second authority. Description-only use remains limited to its validated descriptor/year; other claims and unselected body/context tails cannot ground a claim's numbers. Explicit historical flat inspection retains its original source/description checks. V2 binds source windows, contexts and claims. Meaning such as total, component, rate, or derived display is represented by obligation bindings/formula AST, not a role enum. No extra model call or keyword selection chooses body windows.

Every expression has a nullable source display and nonblank reason; omission is a format error. Lowering produces `source_display_candidate_id` and `source_display_reason`.
Explicit linked request intent precedes source-first defaults: calculation-only uses null even when a reported result exists or happens to equal the calculation. The reason explains the request/decision relationship, not just source availability. The existing Compiler interprets intent; no new classifier, schema choice field, keyword gate or model call. Code does not certify semantic compliance or silently repair a wrong display choice.
Catalog-only prose extraction exposes standalone unitless scalars regardless of digit count, preserving signs and exact shared-window spans. New surfaces append after the legacy sequence so existing candidate identity indices do not move; added membership changes catalog fingerprints normally. Obvious date/time, multipart identifier and reference/list-marker spans are excluded from this extension; existing calendar exclusions remain. Lexical admission is not proof of a quantity's meaning.
New bare values use the existing unitless COUNT convention without borrowing a neighboring currency/scale. Known explicit unit spans are not recast as bare values. Evaluation extraction, table projection and physical identities are unchanged; selected prose operands still require assertions, owner authority and atomic 96/32 capacity checks.
Displays pass the same authority/scope/dimension/assertion checks as operands. A selected request-compatible source spelling/value is primary, with a differing recalculation labelled separately; null retains the calculated primary. Source-first is a default only when the request supplies no different display instruction.
Numeric equivalence remains an independent scaled-precision comparison, not source authority.
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

`OutputRelationshipV1` names two or more output IDs, `kind=shared_basis`, a request unit owned by every member and its exact substring. Unknown/duplicate IDs or ungrounded requests block affected islands. Shared topic/company/string is not an edge. Compiler declarations must be consistent and cannot mix known consolidated/separate sources; declaration agreement does not prove semantic equivalence. Narrative support and physical same-row constraints remain independent. A lone multi-period expression creates no cross-output relationship. Historical non-empty `coupling_key` needs an explicitly authored offline successor, never a runtime fallback.

Declared formula inputs/dependencies may span physical sources and a separately sourced display. Hard filing/consolidation/period conditions, units, assertions, owner authority and physical-row contracts remain enforced, not context-fingerprint equality or free segment/basis labels (including legacy catalog labels). Expression filing checks prefer `document_company` over legacy `company`, as owner checks do. Only an explicit request-grounded output relationship requires shared-basis declaration consistency.

Physical table identity namespaces report-local `table_source_id` by explicit receipt/document ID before row/cell dedupe.
Raw parser IDs remain provenance; qualified IDs bind bundles, context checks, prompt and execution evidence. This boundary change preserves candidate IDs and existing artifacts.
Anonymous legacy tables use report scope plus content, not chunk order; indistinguishable anonymous copies cannot prove distinct filings. Hash algorithms stay intact.
`document_company` is not a value's local subject; a scope witness cannot cross known filing identity. Numeric selections with declared subject/semantic scope require `SourceInterpretationV1`: owned exact request references, interpreted subject/metric, and complete cell-axis references or physically attached exact context quotes (prose may cite its own exact body). The validator recomputes references and a binding-local resolution without mutating query/catalog. Foreign cell/row/document axes, unlinked headings and cross-cell quotes fail closed. Free segment/basis labels stay on the interpretation proof, never overwrite source fields or attached-context resolutions in validation/operand projection, and are not name equality gates; filing, consolidation, measurement period, units and physical-row contracts remain hard checks. Scope/text/normalized value and the resulting program/proof remain bound by V2 execution/revalidation fingerprints. Missing/malformed correspondence is same-cohort program repair, never candidate replacement. `validation_scope=source_linkage_not_semantic_equivalence` explicitly disclaims semantic correctness; independent anonymous controls retain wrong-target cases. No alias/suffix repair or extra model call is introduced.

Two or more direct outputs sharing an explicit subject and compatible declared scope may form an immutable evidence-bundle constraint only when a physical row covers every output.
Complete-row options order by summed best owner positions, worst position, then physical table/row ID. Only the active option enters the prompt; alternatives stay diagnostic and compatibility narratives stay auxiliary.

Constrained outputs share one row. Validator and executor also reject mixing
rows as `evidence_bundle_mismatch`, independently of semantic output relationships.

A required source-defined narrative may join across tables only when its declared subject/scope and physical-bundle compatibility agree; compatible context precedes unknown.
Without a complete physical row, no inferred bundle forces otherwise independent outputs together.

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
another user-visible answer obligation, a request-grounded output relationship, or an
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
`semantic_candidate_stage_diagnostics_v10` records owner factors, bundle/member counts and fingerprints, row constraints, islands, call/retry counts, attempt-visible/context/dependency IDs/fingerprints/bytes, assertion errors, compiler schema bytes and reference fingerprint. Candidate payload bytes include reading surfaces/pieces/indices, not SDK schema. Per-attempt output responsibility context bytes/fingerprint describe compact request context, not accepted answers. Admission must inspect the final SDK request, not infer total size from candidate bytes.

### Compiler transport

Production uses only `CompilerResponseV2` with `semantic_program_candidate_payload_v9`. Each active output is a required nested key with its own direct/calculation/narrative result schema; narrative results cannot contain expressions. Requirements are nested input/evidence keys, subject support and claim support stay separate, and code assigns local subject links. Missing/ambiguous outputs explicitly carry `result=null`. Candidate/bundle/context/surface/piece references are stable short execution-local addresses; complete axes remain in the source payload. Output/request IDs remain readable checklist keys. The immutable reference index never rewrites source text or catalog identity and is not a source-name alias system.
Numeric `interpretation` carries request/subject/metric/scope; lowering attaches the selected cell's complete observed axes, never another cell's axis or an inferred label. Model-written `axis_refs`, nested interpretation contexts and `context_bindings` are forbidden. Optional selection-level `context_evidence` supplies one exact quote and exposed `context_ref`, `supports_interpretation`, and `resolves[] {field,value}`. Only declared uses become internal interpretation/context-binding proofs; unused context or support without interpretation is rejected, not guessed. Scope-only context does not become subject evidence.
Context fields exist only when that output/input has exposed numeric attachments; addresses are a finite per-owner enum, never the full catalog registry. Dependencies do not gain context fields from input requirements. A permitted address still must attach to the selected member and satisfy exact quote/physical-partition checks. Unit, period, scope, assertion, visibility and V2 program/revalidation gates are unchanged. Preparation failures retain scoped diagnostics with unavailable schema bytes as null, never an uninitialized-variable exception or a false zero-byte measurement.
Numeric generation schemas project `source_ref` enums from the same attempt visibility used by lowering, split into cell/prose/declared-dependency alternatives. Numeric selections forbid value `evidence_text`; source_ref already addresses the value. Known cell/prose refs cannot parse through the other source kind to bypass its interpretation shape; unknown/unauthorized refs still receive independent lowering checks. Supplied prose interpretation requires nonempty own-body `source_evidence_text` without exposed numeric contexts; with context it requires an explicit quote or null, valid only with actual attached interpretation support. Value provenance does not imply subject/metric interpretation. Dependencies carry no source grounding. Mixed/multiple legal members remain available; empty spaces admit only empty lists/null results. Identical choice/field sets reuse types. Explicit offline authored transport projects only valid prior assertions/request quotes to the new addresses; invalid/missing old proofs stay schema-invalid. It never rewrites provider responses, invents a choice/scalar/interpretation or adds a call.
`lower_compiler_response` is the sole production conversion: resolve references, check owner visibility, copy exact addressed value spans and complete selected request units, assemble/parse the internal program, then run existing source/unit/AST/physical validation. No missing address or choice is guessed or repaired. Prose interpretation quotes and attached-context evidence remain model selections, separate from the assembled value assertion. Reference failures are target-local same-source repair; accepted outputs and original correspondence JSON survive retries. Transport errors are attempt diagnostics, not execution-validation fingerprints. Old internal programs are not provider responses; explicit offline fixture transport lives under `src/ops`, never in core imports. Authored legacy-witness projections are not sampled model evidence.
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

Repository `.env` loads before settings; process environment wins and imports do not mutate it.
Shared API/Streamlit services resolve `DART_LLM_PROFILE` from reviewed `src/config/llm_profiles.py` data: unset/blank/`google` preserves defaults; `openai_compiler` selects only compilation; `openai` adds Terra/low/8192 default routes and Luna/none/512 context generation while retaining Astra/medium/5120 compilation. OpenAI routes use Responses, zero SDK retries, standard tier, `store=false`, timeout 90s and no Google fallback/client. Context generation uses its dedicated route or the default; string/text-block output excludes reasoning, refused or incomplete text, with metadata fallback and usage/fallback counts. Unknown profiles and missing required OpenAI credentials fail before store/query-router startup when initialization is allowed. `DART_STORE_PATH`/`DART_COLLECTION_NAME` preserve canonical identity and strict readiness; blank collection keeps `dart_reports_v2`. Selection never adopts, rewrites or rebuilds stores, changes existing context caches, or adds benchmark inputs/budgets. FastAPI retains its project path independently of endpoint names.
Experimental Streamlit serializes cached services with a process-wide synchronous lock, including readiness refresh on ingest failure; changing its cached configuration requires restart.
Per-query retrieval fallback is exposed as degraded without rewriting persistent
store readiness. Forced BM25-only startup never initializes dense embeddings;
new/verified-empty stores retain manifest-declared dense ingest initialization.

CORS requires an environment allowlist. Streamlit and MAS remain experimental.
Evaluator dependencies load only for actual evaluation; core imports may not
depend on ops/experimental modules.

## 10. Validation and release gate

Every runtime change runs focused tests, domain audit, import/topology, pycompile,
and `git diff --check`; candidate/compilation/public-result changes also run full unittest.

Provider validation requires separate manifest/cost approval (including [OpenAI successors](../evaluation/provider_admission.md)), then one store-fixed
eval-only run with a 30-second heartbeat; no automatic retry or fresh ingest.
A release needs all approved questions complete, zero runtime errors, and ledger `ok`;
dataset governance and evaluator tolerance remain separate. Local success is not provider evidence.
Opt-in comparisons/admissions fix inputs/budgets and retain failures, without a release claim. `src.ops.provider_admission` records denied requests separately and preserves the first cause. Policies without server counting retain legacy SDK-request preflight/reservation and make no extra calls; the explicit [server-count extension](../evaluation/provider_admission.md) requires separate count authority/allowance, preserves exact generation input and output bounds, and has no failure fallback. Request observations label admission allowed/denied before transmission and completed/failed settlement afterwards; estimates are not billing. The compiler-only evaluator retains completed cases and an unexecuted `interrupted_case`; full-agent `RAGEvaluator` exports the caller-owned snapshot separately as `interrupted_run` on a graph exception. Partial plans, drafts, validations and usage remain diagnostic only: no answer, runtime trace, ledger or judge input is reconstructed. The normal artifact shape is unchanged when there is no interruption. Empty canonical trace/usage defaults on an interrupted row mean unavailable, not zero activity or an accepted incomplete answer. Error projections allow error/admission classes, numeric HTTP codes and standard RPC status names, never messages/headers/bodies. SDK budget receipts retain failed-generation reservations; process crashes and previously lost traces cannot be recovered. Frozen admission scripts/results remain immutable.
