# Portfolio Presentation Outline

This outline is for a short portfolio presentation, interview walkthrough, or
project review. It focuses on the engineering story: turning a financial RAG
prototype into a contract-driven runtime where answers are inspectable.

## Slide 1. Title

**DART Multi-Agent Financial Analysis Lab**

Message:

- Evidence-backed numeric QA over DART filings
- Multi-agent RAG with explicit calculation traces
- Reviewer-ready runtime contracts instead of opaque answer text

Optional visual:

- One-line pipeline from user question to final answer and `task_artifact_trace`

## Slide 2. Problem

Financial-document RAG failures often look small but change the answer:

- wrong row, subtotal, segment, or reporting period
- calculated value treated as a directly stated value
- citation preserved in prose but lost in structured state
- benchmark score improved by brittle question-specific rules
- stale compatibility fields overriding the canonical calculation trace

Message:

- The hard part is not only retrieval. It is keeping evidence, calculation,
  acceptance, and review state aligned.

## Slide 3. Goal

Build a runtime that can answer numeric filing questions and show why the answer
was accepted.

The accepted answer should expose:

- final answer text
- citations and evidence items
- `structured_result`
- `resolved_calculation_trace`
- critic acceptance state
- `task_artifact_trace`
- benchmark or reviewer gate status

Message:

- The answer is a presentation layer. The contract is the structured runtime
  trace behind it.

## Slide 4. System Architecture

High-level flow:

```text
User question
  -> Orchestrator plan
      -> Analyst numeric artifacts
      -> Researcher narrative artifacts
      -> Critic reports
  -> Orchestrator merge
  -> Final answer + task_artifact_trace
```

Key shared state:

- `tasks`
- `artifacts`
- `evidence_pool`
- `critic_reports`
- `task_artifact_trace`

Message:

- Agent communication is modeled as typed ledger state, not free-form chat.

## Slide 5. Key Design Choices

Design choices that keep the system general:

- LLMs handle semantics; deterministic code handles execution
- domain vocabulary stays in ontology, retrieval policy, config, or data
- numeric answers publish `answer_slots`, `structured_result`, and
  `resolved_calculation_trace`
- critic acceptance is based on verdict, target refs, reasons, and blocking
  issues, not just a score threshold
- report-cache work is candidate-only until the safety contract is proven

Message:

- The project is less about prompt tuning and more about runtime boundaries.

## Slide 6. Retrieval And Ingest Strategy

The retrieval layer must preserve document shape, not only semantic similarity.

Important surfaces:

- section/table-aware DART parsing
- hybrid retrieval with structure-aware chunks
- retrieval debug traces
- evidence items with source anchors and row provenance
- parser rules limited to recovering document structure

Message:

- Financial filings need source shape. A relevant chunk is not enough if the
  row, period, or table context is wrong.

## Slide 7. Numeric Execution Path

Numeric questions are decomposed into calculation tasks:

1. identify required operands
2. retrieve and reconcile evidence
3. extract structured operands
4. plan the formula
5. execute deterministically
6. render and verify the result
7. expose `resolved_calculation_trace`

Message:

- The calculator does not invent evidence. It assembles already-grounded
  operands into an inspectable trace.

## Slide 8. Acceptance And Review Gates

Current gates:

- task/artifact integrity projection
- final close blocking on integrity errors
- critic acceptance state and rejection feedback
- report-cache reviewer handoff
- runtime domain-term audit
- full unit-test discovery

Representative commands:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m src.ops.audit_runtime_domain_terms
.\.venv\Scripts\python.exe -m src.ops.portfolio_demo
.\.venv\Scripts\python.exe -m src.ops.review_report_cache_index_contract
```

Message:

- The gates are designed to catch regressions in evidence, calculation,
  acceptance, and overfitting boundaries.

## Slide 9. Portfolio Demo

Use the fixture-backed demo as the reviewer path:

```powershell
.\.venv\Scripts\python.exe -m src.ops.portfolio_demo
```

The demo shows:

- final answer
- citations
- calculation trace
- task/artifact integrity
- critic acceptance
- cache reviewer handoff

Expected headline:

- `Readiness: ready`
- cache mode remains `candidate_only`
- `serving_enabled = false`
- `ledger_insertion_enabled = false`

Message:

- A reviewer can scan the runtime contract without needing API keys, a vector
  store, DART downloads, or benchmark result bundles.

## Slide 10. What This Demonstrates

Engineering capabilities shown by the project:

- long-form financial RAG failure-mode analysis
- LLM/deterministic boundary design
- structured evidence and calculation provenance
- multi-agent handoff through typed artifacts
- contract tests and reviewer gates
- quality/cost tradeoff awareness

Message:

- The repo demonstrates how to make financial RAG auditable instead of merely
  plausible.

## Slide 11. Current Limits And Future Work

Intentionally disabled today:

- cache serving and retrieval bypass
- automatic cache writes
- cache candidate insertion into the live task/artifact ledger
- LLM critic as an acceptance authority
- benchmark-specific runtime routing branches

Longer-term work:

- promotion-risk management for any future cache consumer
- cost/runtime control for larger benchmark refreshes
- task-ledger and artifact-contract cleanup
- broader benchmark coverage after the contract surfaces stabilize

Message:

- The disabled features are part of the safety story, not unfinished hidden
  behavior.

## Slide 12. Closing

Close on three points:

- The project defines financial RAG quality as an inspectable runtime contract.
- Numeric answers are accepted through evidence, calculation trace, critic
  state, and ledger integrity.
- The current repo is packaged with a README, one-pager, codebase map, question
  trace walkthrough, portfolio demo, and reviewer commands.

Suggested final line:

> This project is my answer to the question: how do we make a financial RAG
> system that a reviewer can audit, not just a model that sounds confident?
