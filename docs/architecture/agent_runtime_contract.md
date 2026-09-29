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

## 4. Evidence and answer boundary

A source requires existing filing/document and chunk identity plus nonempty text.
Its public source ID is the URL-escaped document ID, colon, and URL-escaped chunk
ID. Different filings cannot collide through a shared chunk ID. Duplicate identical
sources collapse; different visible content/context under one ID fails closed.
Missing-identity/empty sources are omitted with a trace reason, never assigned
invented physical provenance. Context retains source company/year, section/table
headers and units when present; the model interprets their meaning.

The serialized question/scope/documents packet is bounded to 65,536 UTF-8 bytes.
Oversized documents are omitted whole and reported; source text is not truncated.
An oversized question/scope fails before search. This byte bound is not a tokenizer,
provider context-window check, billing estimate or total experiment budget.

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
