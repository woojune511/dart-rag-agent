# Documentation Claim Boundaries

This note defines the reader profile and terminology boundary for portfolio and
architecture documents in this repo.

## Target Reader

Assume the reader is comfortable with LLM application engineering and has
working familiarity with:

- RAG, embeddings, hybrid retrieval, reranking, and chunking tradeoffs
- LLM agents or graph/workflow runtimes
- grounding, citation support, faithfulness, and evaluation-driven development
- basic financial statement concepts and table QA failure modes

The documents therefore do not need to explain what RAG or an LLM agent is from
scratch. They should instead explain which failure mode is being addressed,
which runtime surface carries the state, and which gate verifies the claim.

## Claim Level

Use a systems/research-engineering claim:

- This project designs a contract-driven financial RAG runtime.
- The contribution is in representation, runtime boundaries, traceability,
  evaluation, and cost-control instrumentation.
- Novelty, when mentioned, means domain-specific systems novelty rather than a
  new foundation model, new embedding model, or general TableQA algorithm.

Avoid unsupported claims:

- Do not claim SOTA or paper-grade algorithmic novelty.
- Do not say arithmetic hallucination is completely eliminated; say arithmetic
  and unit execution are moved out of free-form generation and into deterministic
  calculation paths.
- Do not call value-cell records "cell-level embeddings" unless an embedding
  method is actually defined at that level. The current term is
  `value-cell-first structured metadata` or `table_value_records_json`.
- Do not describe retry behavior as generic Reflexion/ReAct unless the text
  explicitly means the bounded `ReflectionRequest -> ReflectionPlan ->
  ReflectionAction -> ReflectionReport` contract implemented in this repo.
- Do not use multi-agent orchestration as the product headline. The product
  surface is the single-agent `FinancialAgent`; MAS orchestration is an
  optional experimental surface.

## Evidence Classes

Do not collapse these surfaces into a generic `ready` or `reproducible` claim.

| Evidence class | What it establishes | Required limitation |
| --- | --- | --- |
| Curated demo fixture | Fixture-byte integrity and internal cross-surface invariants | State `curated_contract_fixture`, upstream lineage `not_provided`, and no live DART/LLM replay |
| Recorded benchmark result | A scoped result from a named run, profile, and date | Say `recorded`; report whether raw artifacts are published, local-only, deleted, or otherwise unavailable for that run |
| `review_surface_ready` | The fixture and optional reviewer handoff checks passed | Unit tests and the domain audit are `not_run` by this command; it is not publication readiness |
| Publication validation | Focused reviewer tests, domain audit, and full unit discovery at a named revision | It does not reproduce benchmark runs; distinguish workflow definition, local PASS, and observed remote PASS |

SHA-256 binding proves that fixture bytes match the manifest. It does not prove
runtime provenance, authenticity, or an upstream execution unless that lineage
is separately supplied and verified.

## Preferred Terms

| Use | Meaning in this repo |
| --- | --- |
| `contract-driven runtime` | acceptance is tied to typed artifacts, traces, critic reports, and integrity gates |
| `artifact ledger` | shared `tasks`, `artifacts`, `evidence_pool`, `critic_reports`, and `task_artifact_trace` state |
| `value-cell-first structured metadata` | table values preserve row headers, column headers, period, aggregate role, and unit hints |
| `required-operand contract` | numeric tasks must recover the operands required by the operation before rendering |
| `deterministic execution path` | arithmetic, unit handling, dependency binding, and validation are handled by code |
| `bounded reflection` | retry preparation is budgeted and recorded as a reviewable artifact, not a final-answer authority |
| `trace-based numeric grounding` | evaluation inspects operands, formula, source references, and rendered displays |

## Terms To Use Carefully

| Term | Safer usage |
| --- | --- |
| `neuro-symbolic` | acceptable as shorthand for LLM semantic planning plus deterministic execution, but define it once |
| `ontology` | keep it tied to concept aliases, binding policy, retrieval hints, and surface contracts; do not imply a complete financial knowledge graph |
| `agentic` | tie it to the typed planning, evidence, calculation, and review workflow inside the single-agent `FinancialAgent` graph |
| `multi-agent` | reserve it for the optional `src.experimental.mas` surface; do not use it as the product headline |
| `grounding` | specify whether it means source text, row/cell provenance, numeric operand support, or citation coverage |
| `faithfulness` | distinguish offline judge metrics from runtime acceptance gates |

## Review Checklist

Before publishing or committing documentation:

- every technical term should point to a concrete file, state field, command, or
  evaluation gate
- benchmark numbers should identify the recorded run/profile/date and whether
  they are store-fixed eval-only or historical screening evidence;
  raw-artifact availability must be stated per run
- current local validation claims should name the revision or working-tree
  snapshot they cover
- disabled capabilities such as cache serving and LLM critic authority should
  remain explicit
- workflow definition, local validation, and observed remote CI status should
  never be presented as interchangeable
- wording should prefer "reduced", "moved into deterministic execution", or
  "verified by gate" over "solved", "guaranteed", or "fundamentally eliminated"
