# FinancialAgent Runtime Contract

Status: normative

This document defines only the supported v1 public/storage contracts and the v2
internal graph contract. Superseded designs and completed migrations belong in
[implementation_history.md](../history/implementation_history.md) and
[experiment_history.md](../history/experiment_history.md).

## 1. Product and authority boundary

The product runtime is the single-agent `FinancialAgent`. It may use an LLM to
interpret intent and evidence, but code owns arithmetic, unit conversion,
dependency binding, candidate authority, dedupe, ordering, validation, and
ledger integrity.

Runtime behavior must remain generic. Company names, benchmark IDs, expected
answers, report-specific phrases, and metric recipes may not control routing,
retrieval, candidate selection, compilation, execution, or rendering. Domain
vocabulary belongs in reviewed ontology, policy, configuration, or data.

Evidence is authoritative over generated text. A numeric value may enter an
answer only through a registered candidate and validated program binding. Source
display and deterministic calculated display may coexist, but their provenance
must remain distinct.

Numeric normalization and rendering share `UnitSpecV1`: source numbers multiply
by its scale; calculated displays divide by the same scale. Canonical currency,
percentage, and count dimensions are valid unit declarations. Direct values keep
the source unit, parentheses, and precision. Non-finite normalized or calculated
values cannot produce answer slots; source precision comparisons use base units.

Unsupported planner units remain recorded on their obligations and block the
affected compilation island. Validation errors identify the owner, candidate,
location, and repair action explicitly. Compiler format errors retry the same
cohort; only an explicit candidate dimension, scope, or subject conflict permits
candidate replacement. Unknown applicability is not a replacement instruction,
and retry selection must never infer candidate IDs from diagnostic prose.

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
provenance fail before revalidation or arithmetic as `execution_content_mismatch`.
Production accepts no V1 envelope fallback. Existing candidate IDs and catalog
identity fingerprints are unchanged.

Any mismatch fails closed as `visibility_mismatch` or `validation_drift`.
Execution must not overwrite immutable compile validation.

## 4. Candidate applicability and coupling

Candidate applicability has exactly three states:

- `compatible`
- `unknown_only`
- `explicit_conflict`

Each obligation and evidence requirement may declare `SemanticTargetV1` with
`local_subjects`, ontology-backed `concept_keys`, and query-visible
`metric_surfaces`. `scope.company` remains the filing boundary and is never
silently copied into local subject identity. Unknown concept keys are discarded
with a planner note rather than becoming runtime vocabulary.

The complete immutable candidate catalog is projected into generic fact views.
Owner matching then evaluates independent scope, local-subject, owner-kind,
document-subject, unit, metric, and physical-locality factors. Repeated words do
not accumulate an additive relevance score and cannot compensate for an
explicit scope, subject, or unit conflict. Within each owner cohort,
`compatible` candidates always rank before `unknown_only`; explicit conflicts
are excluded. Equal factor tiers are deterministic and source-diverse.

`SourceBundleV1` is the compiler's source-reading unit. It has a deterministic
bundle ID, source kind, source anchor, context fingerprint, exact contiguous
source text, member candidate IDs, and bundle-local value spans. Prose values
from the same source sentence share a bundle. A sentence longer than the prompt
window is split into maximal consecutive value-span groups within 420 characters;
each group shares one window containing all its values without cutting a
neighboring numeric span or normalizing bytes. Every value belongs to one window.
Table values share a bundle only through the same physical table and row;
row headers and cell provenance remain on their candidates.

Numeric selection is bundle-first. Code excludes `explicit_conflict`, gives
`compatible` bundles precedence over `unknown_only`, and ranks a bundle by its
best member's existing factor vector. Each numeric owner receives at most two
bundles. Every non-conflicting numeric member of a selected bundle is visible to
that owner so period pairs, signs, and neighboring operands are not separated by
an arbitrary top-one cutoff. Selecting the same bundle for more than one owner
does not duplicate its source text in one compiler payload.

`semantic_program_candidate_payload_v5` stores source text once in
`source_bundles_by_id`. Candidate rows retain their existing IDs and metadata,
refer to `source_bundle_id`, and carry a bundle-local value span instead of a
repeated source excerpt. The prompt receives the factor projection but does not
perform a second ranking pass. Validation recomputes applicability for declared
semantic targets and rejects a visible but conflicting ID as
`candidate_semantic_target_mismatch`.

When the compiler selects a prose `sentence_value` as a direct binding,
expression source, or source display, `source_assertions` must identify the
bundle and selected candidate IDs and copy an exact contiguous source substring
covering every referenced value span. Code verifies bundle membership, owner
visibility, exact bytes, and span coverage before execution and fingerprints the
validated assertion. Table cells use physical row/cell provenance instead;
narrative obligations keep their existing multi-evidence bindings. Meaning such
as total, component, rate, or derived display is represented by obligation
bindings and formula AST, not a candidate role enum or a separate reranker.

Every expression explicitly supplies nullable `source_display_candidate_id` and
a nonblank `source_display_reason`; omission is a compiler format error and
retries the same cohort. A selected source display passes the same authority,
scope, dimension, and exact-assertion checks as other sources. Its value and
source spelling are primary even when they differ from recomputation. The
answer then also labels the recalculated value. Numeric equivalence remains a
separate scaled-precision comparison, not a condition for source authority.
Dependency formulas consume calculated values; public primary answer slots use
display values. Trace preserves both values and their separate provenance.

Numeric owners have capacity two source bundles, narrative requirements six
candidates, and numeric compatibility narrative capacity two. Query-wide
visibility remains bounded by 96 unique numeric and 32 narrative candidates.
Bundle expansion is atomic: overflow fails before compiler calls, and a bundle
is never partially trimmed to meet capacity.

Coupling applies only when two or more distinct obligations share the same
non-empty `coupling_key`. Multiple period operands of one derived obligation do
not create a cross-obligation coupling mismatch. A true coupled basis conflict
must fail validation.

Physical table, row, and cell identity and existing candidate IDs/fingerprints
remain stable. `document_company` is metadata, not proof of a value's local
subject. Row headers and local entity surfaces remain part of candidate
provenance and applicability.

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
`ledger`, and `final_result`.

Every graph node writes exactly one top-level phase key. Diagnostics stay inside
the phase that produced them. A phase transition moves its downstream readers in
the same change; long-lived dual-write is forbidden.

Intermediate nodes do not write `tasks`, `artifacts`, or the final answer.
`assemble_ledger` creates one `LedgerSnapshot` from phase results.
`assemble_final` is the only graph node that assembles answer, citations, and
structured result. The checked node/edge list is generated in
[runtime_flow_roles.md](../overview/runtime_flow_roles.md).

## 6. Compilation islands

Each answer obligation is a vertex. Two vertices share an island when one
declares a dependency on the other, both have the same non-empty `coupling_key`,
or they are members of the same inferred evidence-bundle constraint.

Unknown dependency, self-dependency, and cycle fail the affected island before a
compiler call. A query may contain at most eight islands. All candidate
selectable ID unions are preflighted before any compiler call, counting a shared
ID only once (numeric 96, narrative 32). Owner quota sums are not reservations.
Every retry candidate replacement also checks the query-wide union, including
already accepted and not-yet-compiled islands. An overflowing retry makes no
provider call and preserves accepted program bytes; bundles are never truncated.

Islands are ordered by original obligation order and compiled sequentially. Each
island has one internal retry at most:

- candidate validation failure excludes the rejected candidate's source bundle
  for that owner and promotes the next ranked bundle;
- assertion, AST, schema, or binding format failure retains the same cohort.

If any member of an evidence bundle needs retry, every obligation in that bundle
is retried together. Candidate rejection rebuilds the bounded cohorts and bundle
ranking. If the active row is no longer complete, the next complete option is
selected; AST, schema, and binding-format retries retain the active option.

Accepted program JSON from an island that is not retried must remain byte-for-byte
identical. Final programs, missing/ambiguous IDs, and diagnostics merge in
original obligation order. `semantic_candidate_stage_diagnostics_v9` records
owner factor counts, selected bundle IDs, bundle/member counts and fingerprint,
the active physical-row constraint, island composition, call/retry counts,
attempt-visible IDs, prompt bytes, and assertion coverage/errors.
Ranking diagnostics are observability-only and are not serialized into the
compiler prompt.

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

`StoreManifestV1` is stored as `store_manifest.json` and contains exactly:

```text
schema_version
collection_name
embedding { provider, model_name, dimension }
ingest { profile_id, parser_schema_version, chunk_size, chunk_overlap }
```

Query startup reads this manifest. Missing, invalid, or non-exact manifests make
readiness false and query returns 503. Runtime must not infer or write identity
for an existing non-empty store. Explicit BM25-only degraded mode is the sole
exception; it must be enabled by configuration and exposed in readiness,
response, and retrieval trace.

Exactness includes the complete top-level, embedding, and ingest field sets;
unknown or missing fields make the manifest invalid.

A manifest-less Chroma directory whose embedding and pending-operation counts
are both zero remains eligible for ingest initialization after restart. It is
not query-ready, and ingest writes the manifest only after indexing documents.

Legacy-store adoption uses a separate CLI. Its default is dry-run; writing a
manifest requires the explicit write flag after collection, dimension, and
declared profile validation.

`IngestService(fetcher, parser, context_generator, store)` owns fetch, parse,
context generation, indexing, and manifest recording. A manifest is written only
after documents are indexed. Multi-report ingest records it after the first
successful store batch so a later failure remains resumable. A report is skipped
only when every parsed `chunk_uid` is already present; otherwise document adds
resume by chunk identity. Ingest results count only chunks actually added after
resume filtering. Vector-batch progress is recorded immediately after the vector
commit, and resume reconciles already-indexed chunks into the structure sidecar.
`FinancialAgent` exposes no ingest method.

Benchmark-only `in_progress` cache metadata may preserve a manifest-less partial
store only when cache and store signatures match exactly and partial resume is
enabled. It never makes that store query-ready; the store manifest remains a
completion boundary.

## 9. API and optional surfaces

FastAPI creates `AppServices` in lifespan and stores it on `app.state`. Query and
ingest execute in a threadpool. `/api/health/live` reports process liveness;
`/api/health/ready` reports strict store readiness; `/api/health` is a readiness
alias. `QueryRequest.report_scope` is typed and passed without invented fields.

Repository `.env` values are resolved before application settings, with process
environment values taking precedence and imports leaving process state
unchanged. Query and ingest operations sharing one `AppServices` instance are
serialized before threadpool dispatch because the agent and store are mutable.
Readiness is refreshed inside that serialization boundary after every ingest
attempt, including a partial failure. The experimental Streamlit path uses a
process-wide synchronous lock on its cached `AppServices` for store inspection,
query, ingest, and evaluation; ingest readiness refresh remains inside that
same boundary on success or failure.

Each run projects retrieval status from all executed-query telemetry. When a
compatible store falls back to BM25 for a query, the HTTP response exposes that
query as degraded without changing the persistent store readiness.

CORS is disabled unless an environment allowlist is configured. Streamlit and
MAS are experimental. Evaluator dependencies load only for an actual evaluation
action. Core runtime imports may not depend on ops or experimental modules.
Explicit forced BM25-only startup does not initialize a dense embedding client;
it is selected only when persisted BM25 source data exists. A new or verified
empty store stays on the manifest-declared dense initialization and ingest path.

## 10. Validation and release gate

Every runtime change runs focused tests, runtime-domain audit, import/topology
checks, pycompile, and `git diff --check`. Candidate, compilation, and public
result boundary changes additionally run full unittest discovery.

Provider validation is never implied by local success. It requires separate
approval for a new manifest hash and cost estimate, then one store-fixed
eval-only run with a 30-second heartbeat. Automatic retry and fresh ingest are
forbidden. A release requires runtime completeness for all approved questions,
zero runtime errors, and ledger integrity `ok`. Dataset answer-key governance and
evaluator tolerance are separate work.
