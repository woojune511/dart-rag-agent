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

Compiler authority is represented by frozen, slotted standard-library
contracts:

- `OwnerCandidateVisibility`
- `EvidenceBundleOptionV1`
- `EvidenceBundleConstraintV1`
- `CandidateVisibilityV1`
- `CompilationEnvelopeV1`

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

An optional local cross-encoder may break a tie only inside the strongest exact
factor-vector tier for an atomic numeric owner. Narrative synthesis,
source-defined groups, and non-numeric compatibility cohorts are not top-one
selection problems and never enter this scorer. It never admits an explicit
conflict, promotes a lower tier, changes owner visibility, or selects cells
independently of a physical-row bundle.

Pair schema `semantic_tie_break_pair_v5` presents a natural query, typed target,
and immutable `CandidateFactRoleV1` with period/table/physical provenance inside
bounded cell-local evidence. Sentence values use an exact saved `source_span` or
one unique value surface; ambiguity keeps a bounded fallback. Tables project
parser structure, while runtime prose remains `unresolved`. The evaluation-only
role interpreter groups all values from one exact source, excludes query and
answer labels, and accepts only visible IDs plus exact source surfaces whose
relation contains that value. Only validated `CandidateSemanticRoleV1` enters a
model fixture; runtime wiring, candidate IDs, and catalog fingerprints stay fixed.

The initial query pass scores at most 12 candidates per cohort and 64 pairs in
one batch. A top-versus-runner margin below `0.05`, capacity overflow, or scorer
unavailability preserves the deterministic order. The score transform is an
explicit part of scorer identity; the pinned runtime policy uses `sigmoid`,
while `raw_logit` is available only as an explicitly selected calibration
variant. Model loading is lazy, pair scores are process-local and bounded. The
feature remains disabled by default
until `src.ops.semantic_tiebreaker_promotion_gate` shows a labeled top-1 gain,
no confident error, correct ambiguity abstention, and warm p95 within one
second. Its margin calibration is diagnostic and never rewrites runtime policy.
`src.ops.export_semantic_tiebreak_cases` reads fingerprint-verified catalogs;
`src.ops.mine_semantic_tiebreak_cases` binds exact verified dataset-quote hard negatives to graph source ID or physical table source and exports exact node text/hash plus a filing link; review may exclude operand-only derived cases without blocking valid source-stated derived displays.
This remains evidence-scoped, not runtime-frequency or promotion evidence. The gate uses cached model files unless download is explicitly enabled.

Activation is explicit through routing config
`enable_semantic_candidate_tiebreaker` or
`DART_SEMANTIC_TIEBREAKER_ENABLED=1`. The policy-pinned model and code revisions
are the default; overriding the model does not inherit remote-code trust unless
`DART_SEMANTIC_TIEBREAKER_TRUST_REMOTE_CODE` is also explicitly enabled. The
promotion gate may compare another transform with `--score-transform`, but the
runtime transform changes only through reviewed policy together with its margin.

Structured prompt rows contain only the physical cell value and its row/column
axes, not the parent chunk's flattened table body. The prompt receives the
factor projection but does not rerank it. Validation recomputes the same matcher
for explicitly declared semantic targets and rejects a visible but conflicting
ID as `candidate_semantic_target_mismatch`. During the schema transition, a
target-less legacy owner may derive a local subject only from catalog identity
surfaces that also occur in the owner text.

Numeric owners have capacity four, narrative requirements six, and numeric
compatibility narrative capacity two. Query-wide reservation remains bounded by
96 numeric and 32 narrative candidates. Overflow fails before compiler calls;
owners may not be silently dropped.

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
Each complete row is one option. Options are ordered by the sum of their best
owner-cohort positions, then their worst owner position, then physical table and
row ID. Before compilation, code selects the first option and projects every
constrained output and requirement cohort through that physical row. Numeric
compatibility narratives remain auxiliary selectable IDs. The compiler receives
only the active one-option constraint and its candidate dictionary; ranked
alternatives remain diagnostics and never enter the prompt.

All constrained outputs therefore share one physical-row selection by
construction. Mixing rows is not representable through normal compiler
visibility, while validator and executor retain `evidence_bundle_mismatch` as a
defense-in-depth check. This invariant is inferred independently of planner
`coupling_key`.

A required `source_defined_group` narrative may join that bundle across tables
only when local subject and declared scope agree and its filing company, report
year, consolidation scope, and basis do not conflict with the direct row.
Explicitly compatible narrative context is used before unknown context. If no
complete physical row exists, the runtime does not infer a bundle or force
otherwise independent outputs together.

## 5. Internal graph state v2

`FinancialAgentStateV2` has these phase envelopes, in order:

```text
request
routing
requirements
retrieval
candidates
compilation
numeric_result | narrative_result
ledger
final_result
```

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
reservations are preflighted before any compiler call.

Islands are ordered by original obligation order and compiled sequentially. Each
island has one internal retry at most:

- candidate validation failure excludes the rejected ID and promotes the next
  ranked candidate;
- AST, schema, or binding format failure retains the same cohort.

If any member of an evidence bundle needs retry, every obligation in that bundle
is retried together. Candidate rejection rebuilds the bounded cohorts and bundle
ranking. If the active row is no longer complete, the next complete option is
selected; AST, schema, and binding-format retries retain the active option.

Accepted program JSON from an island that is not retried must remain byte-for-byte
identical. Final programs, missing/ambiguous IDs, and diagnostics merge in
original obligation order. `semantic_candidate_stage_diagnostics_v8` records
owner factor counts, factor-vector tier separation, unknown-only share inputs,
the active constraint, complete-row option counts and ranked option selection,
island composition, call/retry counts, visibility fingerprints, prompt bytes,
and bounded semantic tie-break eligibility, exclusion reason, scorer identity,
scores, and margin.
Ranking diagnostics are observability-only and are not serialized into the
compiler prompt.

## 7. Retrieval boundary

Retrieval runs in four owner-local stages without changing the external graph
node or search-result order:

1. build plan;
2. execute searches;
3. select evidence;
4. build trace.

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
