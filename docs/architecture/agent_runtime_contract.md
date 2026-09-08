# FinancialAgent Runtime Contract

Status: normative

This document defines the supported v1 public/storage and v2 internal graph contracts.
Superseded designs belong in [implementation history](../history/implementation_history.md) and [experiment history](../history/experiment_history.md).

## 1. Product and authority boundary

The single-agent `FinancialAgent` uses an LLM to interpret intent and evidence.
Code owns arithmetic, unit conversion, dependency binding, candidate authority,
dedupe, ordering, validation, and ledger integrity.

Company names, benchmark IDs, expected answers, report-specific phrases, and metric
recipes may not control routing, retrieval, selection, compilation, execution, or
rendering. Domain vocabulary belongs in reviewed ontology, policy, config, or data.

Evidence is authoritative over generated text. Numeric answers require registered
candidates and validated program bindings. Source and calculated displays may
coexist, but their provenance must remain distinct.

Normalization and rendering share `UnitSpecV1`: source numbers multiply by its scale;
calculated displays divide by it. Direct values preserve source units/signs/precision;
non-finite values cannot yield slots, and precision comparisons use base units.
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
Usage and calculation debug telemetry belongs in `debug_bundle`.

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
provenance (including attached document contexts) fail before revalidation or arithmetic as `execution_content_mismatch`.
Production has no V1 fallback. Historical catalogs/programs are never silently remapped to new identities.

Any mismatch fails closed as `visibility_mismatch` or `validation_drift`.
Execution must not overwrite immutable compile validation; validator-selected
IDs follow declared obligation order with first-occurrence dedupe.

## 4. Candidate applicability and coupling

Candidate applicability has exactly three states: `compatible`, `unknown_only`,
and `explicit_conflict`.

Each obligation/requirement may declare `SemanticTargetV1`: `local_subjects`, ontology-backed `concept_keys`,
and query-visible `metric_surfaces`. Keep query-written bilingual parenthetical spellings of a selected subject;
do not invent translations/entities. `scope.company` is a filing boundary, not a local subject; unknown concept keys get a planner note.

Located calendar labels resolve first, then fiscal columns using the existing row-ordinal/report-year mapping, then relative labels and generic roles. Fiscal columns precede row-derived `period_text`; repeated equivalent labels resolve once. Raw period surfaces remain identity/provenance, not an override.
Ambiguous/unanchored fiscal columns stay `unknown_only`; retained row-relative text cannot resolve them again in validation. Other ambiguous/unanchored numeric periods cannot borrow filing year. Relative-only comparisons need no invented year; parser-wide `period_labels`/`period_focus` remain unlocated hints.
Non-temporal headers stay in `source_period_surface`/`column_headers`, not `period`. `period_label_scope` distinguishes cell/source-period evidence from `unbound_table` hints in catalog, prompt and operand trace; IDs/raw bytes/catalog fingerprints stay intact.
Narratives may use filing-year document scope, but that scope cannot bridge a numeric period. A numeric period witness needs located period evidence and the same source context; missing period evidence requests program repair, not candidate exclusion.

The complete immutable candidate catalog is projected into generic fact views.
Owner ranking compares scope/applicability, explicit local-subject, owner-kind, unit, metric, and physical-locality. Document-company matches are diagnostic only; filing scope rejects conflicts but adds no implicit value-subject bonus.
Repeated words do not accumulate additive relevance or compensate for conflicts. Legacy subject inference must not promote a fragment of a declared concept alias/metric surface into a local entity; explicit local subjects remain authoritative.
Within each cohort, `compatible` precedes `unknown_only`; explicit conflicts are excluded. Exact row/cell metric matches precede containment-only matches as ordinal tiers, not additive scores. Comparison keys remove parser footnotes, never semantic qualifiers; empty keys cannot match. Source axes, IDs and catalog fingerprints stay intact. Equal tiers remain deterministic and source-diverse.

`SourceBundleV1` is the source-reading unit: deterministic ID, source kind/anchor, context fingerprint,
exact contiguous text, member IDs and local value spans. Same-source sentence values share a bundle.
Long sentences split into maximal consecutive value-span groups within 420 characters; each window
covers every member without cutting adjacent numeric spans or normalizing bytes. Each value has one window.
Table bundles share a physical table/row and retain row headers/cell provenance. Parser v2 uses leading THEAD/all-TH structure before row-text inference; text body rows are not promoted to headers. Table-attached paragraphs
also retain separate prose slices; table cells and metadata prefixes are not re-extracted as prose values.
Uniquely located numeric rows may carry adjacent textual rows within 420 characters, with exact source ID/span
in `source_context_provenance`. Context is not a new cell/role; it may supply existing text-match factors.
Repeated attachments select context deterministically within the same report/scope/cells; context enrichment does not rewrite cell identity.

Numeric selection is bundle-first: exclude `explicit_conflict`, prefer `compatible`
over `unknown_only`, and rank by the best member's existing factor vector. Each numeric
owner gets at most two bundles with every non-conflicting member visible together.
Period pairs/signs/neighboring operands are not split by a top-one cutoff; a shared
bundle's source text appears once per compiler payload, even across owners.

`semantic_program_candidate_payload_v6` stores source text once in `source_bundles_by_id` and located document fragments once in `source_contexts_by_id`. Compiler JSON framing is compact; source strings, fields, provenance and assertion spans remain exact.
Table bundles reference context IDs/relations; parser payloads retain full ancestor titles, captions, adjacent blocks and textual table rows, file SHA, XML locator and exact decoded-XML-text span (not raw HTML byte offsets). Each fragment is bounded to 1200 characters, each table to 4800; adjacency is not applicability.
Contexts attach before cohort matching, without rewriting cells/IDs/catalog fingerprints. Existing factor matching may read headings/captions/preceding context; no additive score or model call is added. Owner authority still applies.
Direct/variable `context_bindings` and expression `source_display_context_bindings` cite attached context IDs and exact quotes for interpreted period/consolidation/segment/basis. Validator checks attachment, quote, known period consistency and explicit candidate conflicts; semantic applicability remains the compiler's responsibility. A binding-local `context_resolution` reaches execution/trace without changing raw catalog scope. Context errors repair the same cohort; accepted island bindings stay unchanged.

When the compiler selects a prose `sentence_value` as a direct binding,
expression source, or source display, `source_assertions` must identify the
bundle and selected candidate IDs and copy an exact contiguous source substring
covering every referenced value span. Code verifies bundle membership, owner
visibility, exact bytes, and span coverage before execution and fingerprints the
validated assertion; coverage follows declared obligation order. Table cells use row/cell provenance; narratives keep multi-evidence bindings.
Narratives emit `evidence_bindings` once; `candidate_ids` is a code-derived, schema-hidden projection. Blank requirement IDs identify owner-only support and satisfy no requirement; owner/scope/number/group validation remains enforced.
Explicit historical `candidate_ids` are validated as declared, never widened from bindings. Current compiler prompts do not request that duplicate list; input objects and saved programs are not mutated.
Narrative bodies exclude recognized parser metadata prefixes and use exact consecutive windows of at most 1200 characters, 4800 body characters per source. Later windows are `source_continuation` context links on the same candidate, serialized once; source-candidate offsets are not XML offsets. `source_body_coverage` exposes omitted tails. No extra selectable IDs; numeric/table projection and ID/catalog hashing stay intact.
The retained body grounds narrative matching/number validation; window/context content is bound by V2 execution authority. Meaning such as total, component, rate, or derived display is represented by obligation
bindings and formula AST, not a candidate role enum or a separate reranker. No extra model call or keyword selection chooses the body windows.

Every expression supplies nullable `source_display_candidate_id` and a nonblank `source_display_reason`; omission is a compiler format error. A selected source display passes the same authority,
scope, dimension, and exact-assertion checks as other sources. Its value and
source spelling are primary even when they differ from recomputation. The
answer then also labels the recalculated value. Numeric equivalence remains a
separate scaled-precision comparison, not a condition for source authority.
Dependencies use calculated values; public slots use display values. Each binding has a copied `input_rows` record of variable, source ID/kind and executed value/unit; repeated bindings stay separate.
Candidate/direct-dependency rows retain validated requirement/owner metadata, physical provenance and context. Derived inputs reference prior obligations/calculated displays, never fabricated cells.
`calculated_provenance` dedupes transitive input candidate IDs, row IDs and anchors in first-use order, excluding display/compatibility witnesses. General evidence IDs retain witnesses without extra authority.
Requirement scope fallback stays marked `period_source=requirement_scope`; source text stays source-only.

Numeric owners have capacity two source bundles, narrative requirements six
candidates, and numeric compatibility narrative capacity two. Query-wide
visibility remains bounded by 96 unique numeric and 32 narrative candidates.
Bundle expansion is atomic: overflow fails before compiler calls, and a bundle
is never partially trimmed to meet capacity.

Coupling applies only when two or more distinct obligations share the same
non-empty `coupling_key`. Multiple period operands of one derived obligation do
not create a cross-obligation coupling mismatch. A true coupled basis conflict
must fail validation.

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
the phase that produced them. A phase transition moves its downstream readers in
the same change; long-lived dual-write is forbidden.

Intermediate nodes do not write `tasks`, `artifacts`, or the final answer.
Numeric execution returns calculation rows, display slots, and evidence;
narrative validation returns supported sentences and evidence.
`assemble_ledger` records the already completed public answer, structured result,
trace, and narrative source material as one `LedgerSnapshot`.
`assemble_final` is the only graph node that assembles answer, citations, and
structured result. The checked node/edge list is generated in
[runtime_flow_roles.md](../overview/runtime_flow_roles.md).
The final edges are `assemble_final → assemble_ledger → END`; `run()` packages
typed results and telemetry without modifying answers, citations, or evidence.

## 6. Compilation islands

Google phase routes forward explicit `max_output_tokens`, `thinking_budget`,
`provider_client_retries`, and `include_thoughts` to the SDK; zero/false must survive.
Omitted controls retain defaults. Zero retries permit only the initial HTTP attempt. `ProviderAdmissionError` is terminal, not a compiler/schema failure: preserve its first cause and propagate without semantic retry or an evidence-insufficiency program.

Each answer obligation is a vertex. Islands connect only through a dependency on
another user-visible answer obligation, a shared non-empty `coupling_key`, or an
inferred evidence-bundle constraint. `depends_on` never names raw inputs; those
live in `evidence_requirements` and are not vertices. Projection drops an exact
own-requirement reference only after known answer IDs are resolved. Unknown,
self, and cyclic dependencies fail before compilation. At most eight islands and
all candidate selectable ID unions are preflighted before calls, counting a shared
ID only once (numeric 96, narrative 32). Owner quota sums are not reservations.
Every retry candidate replacement also checks the query-wide union, including
already accepted and not-yet-compiled islands. An overflowing retry makes no
provider call and preserves accepted program bytes; bundles are never truncated.

Islands compile sequentially in obligation order, with at most one internal retry:

- candidate validation failure excludes the rejected candidate's source bundle
  for that owner and promotes the next ranked bundle;
- assertion, AST, schema, or binding format failure retains the same cohort. Explicit
  missing/ambiguous with no owned error is terminal; undeclared omissions still retry.
If an evidence-bundle member needs retry, every member is retried together. Candidate
rejection rebuilds bounded cohorts and promotes the next complete row option when needed;
AST/schema/binding-format repairs retain the active option; an abstaining row stays atomic. Unretried abstentions survive targeted merge.

Retry targets alone remain editable. Their accepted `depends_on` outputs are read-only
inputs projected through the same V2-authorized executor, using calculated rather than
source-display values. Failed execution yields no input. Dependency obligation IDs may
be bound as sources; attached candidate provenance never widens owner selection authority.

Unretried island program JSON stays byte-identical. Programs, missing/ambiguous IDs,
and diagnostics merge in obligation order. `semantic_candidate_stage_diagnostics_v9`
records owner factors, bundle/member counts and fingerprints, row constraints, islands,
call/retry counts, attempt-visible/context/dependency IDs/fingerprints/bytes, and assertion errors.
Ranking diagnostics are observability-only, never compiler prompt input.

## 7. Retrieval boundary

Retrieval runs `build_plan → execute_searches → select_evidence → build_trace`
inside one owner without changing the external graph node or search-result order.

`retrieval_debug_trace` records query bundles, filters, executed and reused
queries, selected chunks, policy decisions, and degraded mode. Seed evidence may
be preserved when graph expansion pushes it outside the final window only if it
satisfies the active operand and provenance contract.
Search-cache hits preserve the originating retrieval mode and fallback reason.

Canonical routing embeddings use a process-wide success cache keyed by canonical
file SHA-256, provider, model, and dimension. Failed results are never cached and
their reason is recorded in routing trace.

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
write failures propagate; old payloads are not automatically garbage-collected.

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
Typed `QueryRequest.report_scope` is forwarded without invented fields.

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
Opt-in comparisons/admissions fix inputs/budgets and retain failures, without a release claim. `src.ops.provider_admission` shares SDK-request serialization/reservation between preflight and dispatch, records denied requests separately, and preserves the first cause. The experiment evaluator catches terminal admission errors only to return a failed artifact with unchanged completed cases and an unexecuted `interrupted_case` containing captured responses; core propagation/no-retry remains unchanged. Error projections allow numeric HTTP codes and standard RPC status names, never messages/headers/bodies. Interrupted usage/cost covers completed responses only; unknown total calls/retries are null, while SDK budget receipts retain failed-request reservations. Process crashes are not covered. Estimates are not billing; frozen admission scripts/results remain immutable.
