# Simple RAG application adoption

2026-09-22. Architecture change from `2a926a6e`, explicitly authorized after
explaining the loss of compiled arithmetic, cell linkage and request-coverage checks.
This is a product-scope decision; four familiar development questions do not prove
general superiority. The [earlier comparison](../evaluation/portfolio_workflow_comparison_successor.md)
and all of its raw outputs remain unchanged.

## Application

FastAPI and Streamlit now construct `SimpleRagAgent`. It uses the existing store's
hybrid search once, packs whole retrieved text/context, generates one structured
answer and checks source IDs. Empty evidence abstains without generation. Invalid
responses/citations, scope leaks and conflicting source identities fail without
another generation. Caller scope is explicit and conjunctive, with report-list
unions; question years/entities never become inferred metadata filters.

`FinancialAgent` remains for explicitly invoked comparison/replay tools. The app
does not initialize a Compiler client or import its execution path. Shared model
construction moved unchanged to `src/utils/chat_model_routes.py`; existing compiler
transport and execution checks remain separate. The old embedded evaluation tab
was removed from Streamlit rather than misreporting compiler metrics for simple RAG.

## Compatibility and guarantees

- Answer/citation/review/debug result carrier and API readiness gates remain.
- `workflow`, `abstained`, `cited_sources` and `validation` expose actual behavior.
  Compiler result/trace objects are empty; there is no task/artifact ledger.
- Citation membership and explicit metadata scope are checked. Semantic support,
  requested-output completeness and arithmetic are not automatically verified.
- Retrieved companies/years describe sources, not interpreted request entities.
- A 65,536-byte packet bound omits whole oversized documents with visible reasons.
  Missing source identity also omits a document; no physical ID is invented.
- `openai` keeps the existing answer/ingest-context models; no Compiler is built.
  `openai_compiler` is rejected as an application setting with migration guidance.
  Blank/`google` retains provider selection, with zero generation retries.
- Unknown/malformed scope fields are rejected. Unlike the comparison path, all
  explicit outer fields intersect source lists; receipts do not erase other filters.
- Ingest/parser/store/embedding identity, source bytes and saved results are unchanged.

## Verification and remaining work

Provider-free controls cover one generation, exact question/caller scope, missing
evidence, malformed/unknown citations, context omission, duplicate identities,
scope leaks, explicit abstention, degraded retrieval, interrupted diagnostics and
import isolation. Real SDK serialization and HTTP response checks use mocked
transport. Full suite **2,125/2,125** passes in 64.083 seconds; 16 new controls,
focused56, final API/profile48, comparison/import48 and runtime domain audit35
pass. All110 protected files retain their hashes. The lightweight reviewer CI
keeps fixture-only checks; application/graph tests run with full dependencies.
Current results are also recorded in [project status](../overview/project_status.md).

Local evidence is under `benchmarks/results/simple_rag_default_2026-09-22/` and is
not committed. The protected-input manifest covers settings, store files and prior
comparison outputs. No provider calls, ingest or store mutation were performed.
Shared conservative accounting remains USD21.00190943/26.32, remaining5.31809057,
pending0. New model accuracy, end-to-end latency and price benefit are NOT_RUN.

The next milestone is the separate final evaluation and reproducible demo/report,
including retrieval misses and validation limits. No new per-question patch loop.
