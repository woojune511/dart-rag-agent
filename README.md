# DART Multi-Agent Financial Analysis Lab

A contract-driven Agentic RAG runtime for numeric QA over Korean DART filings.
The project focuses on making financial answers inspectable through structured
evidence, deterministic calculation traces, critic reports, and reviewer-ready
runtime gates.

This README is written for reviewers who already know LLM/RAG basics:
embeddings, hybrid retrieval, reranking, RAG evaluation, and agent/workflow
state. The claim is applied systems work, not a new model or SOTA TableQA
result: make financial RAG answers inspectable, testable, and harder to
overfit.

## At A Glance

| Question | Short answer |
| --- | --- |
| What is this? | Financial-document RAG runtime with typed multi-agent artifacts and trace-based numeric acceptance. |
| What problem does it address? | Answers that look grounded while using the wrong row, period, unit, subtotal, or provenance path. |
| What is the key design? | LLMs handle semantic planning; deterministic code handles operand binding, arithmetic, unit handling, validation, and final rendering. |
| What is the current evidence? | `portfolio_review_gates` reports `ready`; expanded structural ablation: structural avg numeric `1.000` / faithfulness `1.000` vs plain avg numeric `0.833` / faithfulness `0.875`. |
| What is intentionally disabled? | Cache serving, retrieval bypass, automatic cache writes, cache-ledger insertion, LLM critic as final acceptance authority, and benchmark-specific runtime branches. |

## Problem

Financial-document RAG often fails in ways that look small but change the
answer:

- wrong row, subtotal, segment, entity, or reporting period
- calculated value presented as if it were directly stated
- citation preserved in prose but missing from structured runtime state
- stale compatibility fields overriding the canonical calculation trace
- benchmark improvements caused by brittle question-specific runtime rules

This project treats those as **runtime contract failures**. An accepted answer
must expose the evidence, operands, formula, critic decision, and gate result
that justify it.

## Runtime Shape

```text
User question
  -> Orchestrator plan
      -> Analyst numeric artifacts
      -> Researcher narrative artifacts
      -> Critic reports
  -> Orchestrator merge
  -> Final answer + task_artifact_trace
```

Shared state is typed rather than free-form chat:

- `tasks`: planned work and ownership
- `artifacts`: operand sets, calculation plans/results, retrieval bundles,
  reflection reports, critic reports, aggregated answers
- `evidence_pool`: source-grounded evidence records
- `critic_reports`: verdicts, target refs, reasons, and blocking issues
- `task_artifact_trace`: compact integrity projection for callers/reviewers

## Design Claims

| Claim | Concrete repo surface |
| --- | --- |
| LLMs handle semantics; code handles execution | arithmetic, unit handling, dependency binding, dedupe, validation, and final acceptance are deterministic |
| Numeric answers are structured artifacts | `answer_slots`, `structured_result`, `resolved_calculation_trace` |
| Domain terms stay out of runtime branches | vocabulary belongs in ontology, retrieval policy, config, or reviewed data |
| Agent handoff is inspectable | `tasks`, `artifacts`, `critic_reports`, `task_artifact_trace` |
| Reflection is bounded | `ReflectionRequest -> ReflectionPlan -> ReflectionAction -> ReflectionReport` |
| Cache is candidate-only | serving, writes, retrieval bypass, and ledger insertion remain disabled |

See [docs/overview/documentation_claim_boundaries.md](docs/overview/documentation_claim_boundaries.md)
for terminology and novelty boundaries.

## Representative Case

`KAB_T1_066` is the compact close-out case. It exposed three financial-RAG
failures at once:

- plausible but wrong denominator row from another financial statement surface
- direct-support guard over-blocking a correct value because an operation-like
  token appeared inside the metric label
- final prose using stale component display instead of the calculation trace

Current answer:

```text
2023년 CIR은 37.47%입니다. 계산: 판매비와관리비 4,355억원 / 경비차감전영업이익 11,623억원.
```

Both operands are resolved from
`IV. 이사의 경영진단 및 분석의견::table:3`. The verified store-fixed eval-only
run reports numeric `PASS`, faithfulness/completeness/context recall/retrieval
hit@k/grounded rendering correctness all `1.000`, `2` executed queries, `0`
duplicate executed queries, `8` agent LLM calls, and estimated runtime cost
`$0.056292`.

## Quick Review Path

For a fast review, run the first two commands and then read the compact
narrative/snippet documents. The longer experiment and technical documents are
appendix material unless deeper validation is needed.

| Step | Document / command | Purpose |
| --- | --- | --- |
| 1 | `python -m src.ops.portfolio_review_gates` | aggregate ready/not-ready reviewer gate |
| 2 | `python -m src.ops.portfolio_demo` | compact answer/evidence/trace/integrity demo |
| 3 | [docs/overview/portfolio_interview_narrative.md](docs/overview/portfolio_interview_narrative.md) | compact interview talk track and claim boundary |
| 4 | [docs/overview/portfolio_resume_snippets.md](docs/overview/portfolio_resume_snippets.md) | resume and portfolio-ready wording |
| 5 | [docs/overview/portfolio_one_pager.md](docs/overview/portfolio_one_pager.md) | shortest project story |
| 6 | [docs/overview/portfolio_experiment_report.md](docs/overview/portfolio_experiment_report.md) | problem, method, results, failure analysis |
| 7 | [docs/overview/technical_highlights.md](docs/overview/technical_highlights.md) | core technical claims |
| 8 | [docs/overview/portfolio_demo_walkthrough.md](docs/overview/portfolio_demo_walkthrough.md) | fixture-backed demo details |

Everything else is appendix or internal log. Start with
[docs/README.md](docs/README.md) for the full document map.

## Representative Checks

Use the first three commands for normal review. The remaining commands are
capability-specific gates that the aggregate portfolio gate also covers.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m src.ops.audit_runtime_domain_terms
.\.venv\Scripts\python.exe -m src.ops.portfolio_demo
.\.venv\Scripts\python.exe -m src.ops.review_report_cache_index_contract
.\.venv\Scripts\python.exe -m src.ops.report_cache_promotion_evidence_gate
.\.venv\Scripts\python.exe -m src.ops.reflection_promotion_gate
.\.venv\Scripts\python.exe -m src.ops.reference_note_capability_gate
.\.venv\Scripts\python.exe -m src.ops.promotion_trace_materiality_gate
.\.venv\Scripts\python.exe -m src.ops.portfolio_review_gates
```

`portfolio_review_gates` should report aggregate `status = ready`. The cache
reviewer path should remain `candidate_only` with retrieval bypass, writes,
serving, and ledger insertion disabled.

## Current Status

Implemented and validated:

- section/table-aware retrieval and structured numeric traces
- source-visible ratio operand recovery from coherent table context
- MAS skeleton with Orchestrator, Analyst, Researcher, Critic, and merge
- task/artifact integrity projection and final close blocking
- critic runtime acceptance boundary and rejection feedback surface
- bounded reflection request/action/report handoff through the ledger
- candidate-only report-cache reviewer handoff
- aggregate portfolio review gate bundle
- runtime domain-term audit

Intentionally disabled:

- cache serving and retrieval bypass
- automatic cache writes
- cache candidate insertion into the live task/artifact ledger
- LLM critic as an acceptance authority
- benchmark-specific runtime routing branches

Internal logs such as [docs/overview/project_status.md](docs/overview/project_status.md),
[docs/history/experiment_history.md](docs/history/experiment_history.md), and
[docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md) are preserved
for traceability, but they are not first-read portfolio documents.

## Repository Guide

```text
src/
  agent/       runtime graph, MAS nodes, task/artifact contracts
  config/      ontology, retrieval policy, cache classification
  ops/         evaluator, benchmark runner, smoke/review commands
  processing/  DART parsing and chunk preparation
  storage/     vector/BM25 storage and retrieval support
tests/         contract and regression tests
docs/          reviewer docs, architecture appendix, evaluation/internal logs
benchmarks/    profiles and local result bundles
```
