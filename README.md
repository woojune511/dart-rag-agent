# DART Multi-Agent Financial Analysis Lab

Evidence-backed numeric QA over Korean DART filings with multi-agent RAG,
explicit calculation traces, critic acceptance gates, and reviewer-ready runtime
contracts.

Current gate and portfolio status: [docs/overview/project_status.md](docs/overview/project_status.md)

## Why This Exists

Financial-document RAG fails in ways that are easy to miss:

- the answer uses the wrong row, subtotal, segment, or period
- a calculated value is treated as a directly stated value
- citations survive in prose but not in structured runtime state
- evaluator score improvements come from brittle benchmark-specific rules
- stale compatibility fields override the canonical calculation trace

This project treats those failures as runtime contract problems. The goal is not
just to generate a plausible answer, but to expose the evidence, calculation
trace, critic decision, and benchmark/review gate that explain why the answer
was accepted.

## What The System Builds

```text
User question
  -> Orchestrator plan
      -> Analyst numeric artifacts
      -> Researcher narrative artifacts
      -> Critic reports
  -> Orchestrator merge
  -> Final answer + task_artifact_trace
```

The runtime uses shared ledger-style state instead of free-form agent chat:

- `tasks`: planned work and ownership
- `artifacts`: typed outputs such as operand sets, calculation plans, results,
  retrieval bundles, reflection reports, critic reports, and aggregated answers
- `evidence_pool`: source-grounded evidence records
- `critic_reports`: acceptance/rejection reports with target refs and reasons
- `task_artifact_trace`: compact integrity projection for callers and reviewers

## Key Engineering Decisions

### LLMs For Semantics, Code For Execution

LLMs can help interpret intent, concepts, and narrative context. Deterministic
code owns arithmetic, unit handling, dependency binding, dedupe, provenance
checks, and final acceptance rules.

### Runtime Code Stays Generic

DART and financial-domain vocabulary belongs in ontology, retrieval policy,
config, or reviewed data artifacts. Runtime control flow implements generic
mechanisms such as required operands, evidence coverage, target refs, and
artifact integrity.

### Numeric Answers Are Structured Artifacts

Numeric paths publish `answer_slots`, `structured_result`, and
`resolved_calculation_trace`. Answer text is the presentation layer; the
contract is the structured trace.

### Critic Acceptance Is Not A Score Threshold

Runtime critic acceptance is based on verdict, target refs, acceptance reasons,
and blocking issues. Rejected critic reports block final close even when a
diagnostic score is high, and the rejection reasons are surfaced to planner
feedback and smoke summaries.

### Reflection Is A Bounded Capability

Self-reflection is modeled as `ReflectionRequest -> ReflectionPlan ->
ReflectionAction -> ReflectionReport`. Retry preparation records the report as a
`reflection_report` artifact on a `reflection` task, so reviewers can inspect
what action was proposed without giving reflection authority to accept final
answers.

### Report Cache Is Candidate-Only

Report-scoped cache work is intentionally staged. The repo can inspect local
cache-index candidates, validate rehydration/projection contracts, and provide a
reviewer handoff summary, but cache serving, cache writes, ledger insertion, and
retrieval bypass remain disabled.

## Portfolio Entry Points

| Document | Purpose |
| --- | --- |
| [docs/overview/project_status.md](docs/overview/project_status.md) | Current implementation and gate status |
| [docs/overview/portfolio_one_pager.md](docs/overview/portfolio_one_pager.md) | One-page portfolio summary |
| [docs/overview/portfolio_experiment_report.md](docs/overview/portfolio_experiment_report.md) | Problem, experiment design, quantitative comparison, and interpretation |
| [docs/overview/portfolio_readme_blueprint.md](docs/overview/portfolio_readme_blueprint.md) | Suggested README/story structure |
| [docs/overview/portfolio_presentation_outline.md](docs/overview/portfolio_presentation_outline.md) | Interview or presentation slide outline |
| [docs/overview/portfolio_demo_walkthrough.md](docs/overview/portfolio_demo_walkthrough.md) | Fixture-backed demo output and reviewer notes |
| [docs/overview/codebase_map.md](docs/overview/codebase_map.md) | Codebase ownership and execution map |
| [docs/overview/question_trace_walkthrough.md](docs/overview/question_trace_walkthrough.md) | Example question trace |
| [docs/overview/technical_highlights.md](docs/overview/technical_highlights.md) | Deeper technical notes |
| [docs/architecture/agent_runtime_contract.md](docs/architecture/agent_runtime_contract.md) | Runtime and MAS contract |
| [docs/architecture/report_cache_capability_contract.md](docs/architecture/report_cache_capability_contract.md) | Disabled report-cache capability boundary |
| [docs/evaluation/benchmarking.md](docs/evaluation/benchmarking.md) | Benchmark and review gate notes |

## Repository Guide

```text
src/
  agent/       runtime graph, MAS nodes, task/artifact contracts
  config/      ontology, retrieval policy, cache classification
  ops/         evaluator, benchmark runner, smoke/review commands
  processing/  DART parsing and chunk preparation
  storage/     vector/BM25 storage and retrieval support
tests/         contract and regression tests
docs/          architecture, evaluation, planning, and portfolio notes
benchmarks/    profiles and local result bundles
```

## Representative Checks

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

The report-cache reviewer command should report:

- `status = ok`
- `reviewer_handoff.status = ready`
- `reviewer_handoff.mode = candidate_only`
- `retrieval_bypass_enabled = false`
- `write_enabled = false`
- `serving_enabled = false`
- `ledger_insertion_enabled = false`

The portfolio demo command should report `Readiness: ready` and show the final
answer, citations, calculation trace, task/artifact integrity summary, critic
acceptance, and cache reviewer handoff in one compact terminal view. See
[docs/overview/portfolio_demo_walkthrough.md](docs/overview/portfolio_demo_walkthrough.md).
The portfolio review gates command should report aggregate `status = ready`
when the demo, cache reviewer, and reflection promotion gates all pass.
The report-cache promotion evidence gate should report fixture plus trace
summary coverage, with ready and fallback cases and disabled serving,
retrieval-bypass, ledger-insertion, and final-acceptance flags.

## Current Status

Implemented and validated:

- section/table-aware retrieval and structured numeric traces
- MAS skeleton with Orchestrator, Analyst, Researcher, Critic, and final merge
- task/artifact integrity projection and final close blocking
- critic runtime acceptance boundary and rejection feedback surface
- bounded self-reflection request/action/report handoff through the ledger
- reflection promotion gate with report-contract checks for budget, target refs,
  stop blocking issues, and final acceptance authority
- candidate-only report-cache reviewer handoff with bypass, writes, serving,
  and ledger insertion disabled
- code-backed report-cache producer policy that maps future cache-derived
  candidates to the existing calculation task/artifact contract
- fixture plus trace-summary report-cache promotion evidence gate for ready,
  incomplete, and ambiguous local-index entries without enabling cache behavior
- fixture-backed portfolio demo command for answer, evidence, trace, integrity,
  critic, and cache handoff surfaces
- aggregate portfolio review gate bundle for demo, cache, and reflection
  promotion proof
- runtime domain-term audit to keep domain vocabulary out of runtime branches

Intentionally disabled:

- cache serving and retrieval bypass
- automatic cache writes
- cache candidate insertion into the live task/artifact ledger
- LLM critic as an acceptance authority
- benchmark-specific runtime routing branches

## Reviewer Path

For a quick review:

1. Run `python -m src.ops.portfolio_review_gates` to confirm the aggregate
   reviewer proof bundle.
2. Run `python -m src.ops.portfolio_demo` to scan the answer, citation,
   calculation, integrity, critic, and cache-handoff surfaces.
3. Read [docs/overview/portfolio_one_pager.md](docs/overview/portfolio_one_pager.md)
   for the concise engineering story.
4. Use [docs/overview/portfolio_experiment_report.md](docs/overview/portfolio_experiment_report.md)
   for the problem, method, quantitative comparison, and failure analysis.

The current reviewer claim is narrow: canonical runtime state is carried by
typed traces and artifacts, reflection retry decisions are recorded as bounded
handoff reports, `REFERENCE_NOTE` traversal remains Researcher graph-expansion
context rather than cache serving, and legacy calculation/debug mirrors are
optional compatibility bridges that are not seeded into new live runs.
