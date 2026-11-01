# Application Runtime Contract

Status: normative. Updated 2026-09-22 after the user's explicit simple-RAG adoption.

## 1. Product and authority boundary

FastAPI and Streamlit use `SimpleRagAgent` from `src/agent/simple_rag.py` through
`src/api/services.py`. There is no question classifier, Planner, Compiler, graph
execution, tool-selection loop, or automatic fallback to the compiled workflow.
The explicit `FinancialAgent` comparison retains its unchanged calculation/source
protections under [compiled_workflow_contract.md](compiled_workflow_contract.md).
Its checks and historical scores do not describe the default application's guarantees.

Domain vocabulary belongs in reviewed configuration/data. Do not add per-question,
company, metric, or benchmark branches. A policy exception still needs a general
purpose. Retrieved text is evidence, never a source of execution instructions.

## 2. Query execution

1. Preserve the exact original question. Reject an empty question or invalid scope.
2. Search the existing store once with `k=8` and exact caller metadata constraints.
3. Form a bounded packet of whole retrieved text, original source identity and
   stored context. Default application construction does not load experimental
   caption sidecars. No Planner queries, semantic catalog or general graph expansion.
4. If no addressable source fits, return an explicit abstention without generation.
5. Otherwise invoke one structured answer generation, with transport retries zero.
6. Validate response shape and cited-source membership. Return answer, citations,
   explicit validation limits and optional observations. Never repair or retry a
   malformed answer, fabricate a calculation trace or dispatch the Compiler.

Existing storage may perform query embedding and dense/BM25 retrieval; those are
separate from the single answer-generation call. Ingest may also use an LLM.

## 3. Explicit source scope and retrieval

`report_scope_filter` in `src/storage` interprets metadata fields only. It never
extracts a company/year from the question or interprets measurement periods.
`company`/`corp_name` match stored company, `year` matches filing year, and
`report_type`, `rcept_no`, `consolidation` match their stored metadata. Company and
receipt lists are membership filters. All top-level supplied constraints intersect;
`source_reports` is a union of exact report-field conjunctions, also intersected
with those top-level constraints. Conflicting caller fields do not widen the search.
Empty optional lists mean unspecified. Unknown fields, malformed values and empty
source-report alternatives are rejected; HTTP scope validation returns 422.

The same filter reaches native dense and lexical search before top-K. Returned
sources are rechecked before generation. A backend scope leak fails the request.
No unfiltered retry or semantic alias/subsidiary expansion is permitted. Existing
explicit storage BM25 fallback remains visible, including cached fallback results.

An explicit `VectorStoreManager(experimental_lexical_policy_id="country_location_v1")`
enables the reviewed vocabulary in `src/config/retrieval_policy.py` for BM25 only.
The default is `None`; API/Streamlit and environment settings do not activate it.
Generic matching appends each missing configured term once, preserving the exact
original dense/answer query, scope, candidate budgets and RRF behavior. This is
lexical source-field discovery, not entity linkage or sales-geography validation.
Search telemetry records `query`, `bm25_query`, policy ID, matched rules and added
terms, including on cache hits. Opt-in cache identity includes the versioned policy
ID and effective lexical query; unknown policies fail before store/provider setup.
The [offline comparison](../evaluation/new18_v9_country_lexical_policy.md) retains
saved Dense16/BM25-24 and projects final12 separately; application default k=8 stays.

## 4. Evidence and answer boundary

A source requires existing filing/document and chunk identity plus nonempty text.
Its public source ID is the URL-escaped document ID, colon, and URL-escaped chunk
ID. Different filings cannot collide through a shared chunk ID. Duplicate identical
sources collapse; different visible content/context under one ID fails closed.
Missing-identity/empty sources are omitted with a trace reason, never assigned
invented physical provenance. Context retains source company/year, section/table
headers and units when present; the model interprets their meaning.
Stored `unit_hint`, `period_focus` and `period_labels` are also passed through
unchanged when present, alongside `unit`. Missing fields are not inferred from
the question or filing year. These hints remain source context, not verified
semantic interpretation, and count toward the same whole-packet byte limit.

The serialized question/scope/documents packet is bounded to 65,536 UTF-8 bytes.
Oversized documents are omitted whole and reported; source text is not truncated.
An oversized question/scope fails before search. This byte bound is not a tokenizer,
provider context-window check, billing estimate or total experiment budget.

### Canonical XML recovery admission

Canonical parsing retains literal-preserving sanitization and recovery parsing, then
rejects any remaining libxml ERROR/FATAL diagnostics with `XMLRecoveryError`.
The exception propagates through section, outline and chunk parsing to ingest;
it is not converted to an empty result or a partial successful report. No context
generation or indexing occurs for that rejected report. Earlier reports in the
same ingest request may already have been written; this is not batch rollback.
Diagnostics contain the file, reported error count and at most five error
types/positions in sanitized XML, including the final error. Warning-only input
remains accepted. The original file is not rewritten and no repair retry runs.

This is a conservative recovery-error gate, not proof that text was lost in every
rejected document or that error-free parsing preserves all source information.
It does not audit sanitizer changes, section/chunk coverage, table semantics or
existing stores. The current manifest rejects older parser identities under normal
strict readiness; no store migration, rebuild or activation is automatic.

### Canonical literal angle boundaries

Parser v11 prevents an unclosed literal `<` from consuming the following tag's
closing `>`. When no complete quoted tag matches, the first character cannot
start the parser's supported markup spelling, and another `<` precedes the next
`>`, only the literal angle is escaped; its following text is preserved and
scanning resumes at the next tag. Existing quoted attributes, comments, CDATA,
processing instructions and complete markup retain their prior handling.

This angle-boundary rule does not reclassify possible tag names or incomplete
attributes. The schema-bound rule below is a separate, narrower authority for
unpaired bare labels. The recovery-error gate remains in force. Lexical recovery
does not establish semantic interpretation or complete downstream coverage.

### Canonical schema-bound literal labels

Parser v12 derives the closed element vocabulary and mixed-content parents from
the pinned official `src/config/schemas/Dart4.xsd`. Recovery applies only when
the document's root is declared in that schema and its XML Schema instance
`noNamespaceSchemaLocation` names `dart4.xsd` (case-insensitive basename only).
There is no network schema resolution, automatic refresh or full XSD validation.
If the local schema is missing or malformed, this repair is disabled and the
unchanged XML error gate still applies; the report is not returned as empty.

An undefined bare opening token is escaped as literal text only inside a known
mixed-content parent with known ancestors, and only when no closing token of
that name occurs anywhere outside comments, CDATA, instructions or attributes.
Paired, attributed, self-closing and qualified unknown tags are not rewritten.
DTD declarations, namespace scope changes, incomplete markup, mismatched known
tags and unclosed remaining structure disable this repair. Any remaining XML
ERROR/FATAL still rejects the report. No company or label-name exception is used.

The rule preserves the token's exact spelling and all surrounding content; it
does not infer a label's meaning or repair misspelled structural elements. The
official vocabulary snapshot is not proof of historical schema equivalence.
Parser v12 does not rewrite, migrate or adopt existing stores.

### Canonical parser table captions

The canonical parser binds a short explicit period paragraph or a two-row title/period/unit
table to a following value table only within the same XML parent and heading
scope. Blank separators, page breaks and unit-only labels may intervene; other
content, a different period label, or unconsumed XML text prevents the binding.
The whole caption must fit its source-fragment budget without evicting existing
physical context. An ordinary period mention in prose is not a caption.

A bound forward caption cannot trail the preceding table's chunk. Its text is
retained and the value table carries it in `table_context`, including split
table fragments; raw cells, axes and values are unchanged. The located caption
is retained in the table's source contexts. Neither the caption link nor report-year metadata proves semantic
period correctness. This is an ingest/chunking contract, distinct from the
optional query-time caption attachment path below. The current manifest does not
adopt or rewrite older stores. Retrieval scores and answer quality after fresh
indexing require separate verification.

### Canonical table axes and headerless values

Parser v8 projects existing wide-table fragments from the original normalized
cell grid, retaining blank cell positions and repeating leading row axes with
the selected column headers. Numeric identifiers before textual row axes stay
with those axes. All header rows accompany each row fragment. The existing
admission threshold for splitting a whole table is unchanged. Cells and rows
are not cut to meet the soft character target; an intact header plus one row
may exceed that target, while the downstream source-packet byte limit remains.

Without an explicit header, an isolated single row with a named textual axis
and only non-period numeric values can have zero header rows. Its existing
values retain their original column positions and unit hints, with no invented
column header. Explicit THEAD/TH, ambiguous year-like cells and multi-row header
inference retain their existing rules. These structural rules do not validate
a generated answer.

### Canonical relative periods and explicit row units

Parser v9 extracts existing relative period labels with longest-first,
non-overlapping matches. A single `전기말` occurrence contributes that whole
label, not an additional `전기`. Independently occurring labels retain the
existing priority order; absolute-year/date rules and coarse focus mapping
are unchanged. `전전기말` stays an exact label with `unknown` coarse focus;
the parser does not reinterpret it as the preceding period or infer a year.

Structured cells and values preserve an unambiguous unit declared on their
existing row axes, overriding the table fallback locally. Whole-unit bracket
annotations and explicit `단위:`/`unit:` declarations retain their source
surface; values and table-wide hints are unchanged. Bare currency row names,
unscaled currency references, company abbreviations and descriptive prose do
not declare a unit. Equivalent scaled-currency annotations may coalesce.
Conflicting or unresolved explicit row declarations, or contrary explicit
column units, leave an empty cell/value hint. A standalone repetition of the
same table-wide declaration is not a contrary column unit. A present empty
cell hint remains empty in its ValueRecord; a missing legacy cell hint still
permits the table fallback.

This is a parser metadata contract, not unit conversion or semantic validation.
Normalized values/units and downstream Compiler unit resolution are unchanged;
the empty hint is not a global rejection signal for every consumer. Neither
fresh retrieval nor generated-answer quality is established by these rules.

### Experimental physical caption attachments

The optional `table_caption_links.json` is built offline from original XML and
the existing graph/table payloads by `src.ops.build_table_caption_links`.
It is not auto-created by ingest or query execution. The default API/Streamlit
does not load this file, even when present. Experimental callers must supply
`VectorStoreManager(experimental_caption_links_path=...)` explicitly; this is
not an API request field, environment switch or application setting. The path
must name an existing valid sidecar; invalid opt-ins fail before provider/store
construction. File installation alone does not activate the feature.
The extractor admits only isolated explicit date/unit captions immediately
before a unique whole data table in XML and stored order. Both source locators,
raw-document SHA256, scope and source-content/metadata/adjacency fingerprints are persisted.
No original source text, metadata, index, parser schema or embedding is rewritten.

`VectorStoreManager.get_table_caption_doc` revalidates those bindings on every
lookup, including cached retrieval. Missing, altered or stale bound sources fail
before generation; there is no heuristic predecessor/description fallback.
`SimpleRagAgent` retains every initial hit and places whole captions before their
tables, deduplicating identical sources and rechecking caller scope. Physical
source count is bounded by `k` (default8), including attached captions. With any
active caption bundle, a count/byte overflow fails before the answer call rather
than evicting a seed, trimming a source or sending an incomplete bundle. Without
caption attachments, existing whole-source omission behavior remains unchanged.
No extra search, embedding or model call occurs. Successful traces include
`caption_bundles`; attached caption scores are null because lookup is not ranking.
This physical association does not prove semantic ownership or answer correctness.
The caption-aware capacity selector remains an experiment artifact, not the
default search implementation. Its answer comparison did not meet the strict
adoption gate; the explicit attachment implementation is retained for comparisons.

The response schema is `answer`, `cited_source_ids`, `abstained`. Empty/malformed
answers and unknown citations fail without another model call. A non-abstained
answer needs at least one visible citation. These checks do not prove support for
every claim, correct period/entity interpretation, arithmetic or complete coverage.
Abstention is a model declaration, except for the deterministic no-evidence case.

## 5. Public result and observations

The lightweight `FinancialRunResultV1` carrier remains. Simple-RAG `agent_answer`
adds `workflow=simple_rag`, `abstained`, cited source records and `validation`.
`source_ids` is passed or not_applicable; `source_scope` is passed when constrained,
otherwise not_applicable. `semantic_support` and `output_coverage` are not_checked;
`arithmetic` is not_executed. `structured_result` and `resolved_calculation_trace`
are empty objects for compatibility, never fake successful compiler outputs.
Companies/years describe retrieved metadata, not inferred question entities.

`review_trace` is opt-in and contains JSON-native retrieved sources and the exact
query/filter/selection/omission/search trace. It has no task/artifact ledger.
`debug_bundle` is opt-in and contains thread-local token/call counts, embedding
usage when available, timings and copied request diagnostics. Errors preserve the
original exception; safe error classes enter diagnostics, not provider bodies.
Unknown usage remains unavailable. Counts and timings are observations, not bills.

## 6. Application assembly and compatibility

Shared model construction lives in `src/utils/chat_model_routes.py`; loading or
running simple RAG does not import compiled planning/calculation or ops modules.
Only default-answer and optional ingest-context clients are constructed. The
existing `openai` profile uses its recorded answer and context models; `google`
and an empty profile preserve provider selection with zero generation retries.
`openai_compiler` is comparison-only and rejected by application startup with a
migration message. Unknown profiles fail before store/client initialization.

The API retains readiness gates, request serialization and threadpool dispatch.
The source store/ingest/parser/embedding identity is unchanged. No automatic store
adoption, migration or rebuild is part of this transition. The Streamlit client
provides optional company/year/receipt filters and shows answer/abstention, cited
text and retrieved sources; its old compiled-workflow
evaluation dashboard is removed. Comparison/evaluation CLIs remain explicit tools.

## 7. Verification and claim limits

Use provider-free execution, invalid-citation/scope/identity/budget controls,
actual SDK serialization with mocked transport, HTTP projection, isolated import
checks and the existing storage/compiled regression suites. The application change
is an authorized product decision, not holdout evidence of better model quality.
Historical comparison prompts, source/result bytes and accounting are immutable.
Fresh quality/cost/latency evaluation needs a separately frozen bounded run.
