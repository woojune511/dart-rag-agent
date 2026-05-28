# Retrieval Trace Debugging

Use this checklist before changing retrieval or answer logic for a benchmark failure.

## Required Evidence

Every evaluated question should expose `retrieval_debug_trace`.

Check these fields first:

- `query_bundle`: whether the planner produced the right semantic search requests
- `executed_queries`: actual search text, `k`, and `where_filter`
- `policy_trace`: intent, operation family, format preference, preferred sections, and scope flags
- `candidate_count`: whether retrieval found enough candidates before final selection
- `selected_chunks`: whether the selected chunks contain the needed section, company, year, and receipt

## Failure Classification

Classify the failure before editing code.

| Failure layer | Trace signal | Correct fix |
| --- | --- | --- |
| Query planning | `query_bundle` misses the concept/entity | ontology or semantic planner |
| Metadata scope | `where_filter` excludes required report/year/company | scope builder or report metadata |
| Retrieval recall | candidates are missing even with correct query/filter | ingest/chunking/vector store |
| Rerank/selection | candidates exist but `selected_chunks` drops them | reranker or retrieval policy |
| Evidence extraction | selected chunks are correct but evidence is missing | evidence schema/extractor |
| Answer synthesis | evidence is present but answer adds unsupported text | composer/validator |

## Rule Boundary

Do not add runtime query branches for a specific company, question, or benchmark row.

Allowed:

- semantic planner emits retrieval queries from ontology concepts
- named retrieval policy adds general domain priors
- evidence assembler selects rows already present in retrieved docs/evidence

Not allowed:

- code creates a query only for one known entity or benchmark example
- answer composer injects a fact not present in selected evidence
- evaluator-only normalization leaks into runtime answer behavior
