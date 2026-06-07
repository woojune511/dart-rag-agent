# Portfolio One-Pager

## Project

**DART Multi-Agent Financial Analysis Lab**

An evidence-backed financial-document RAG runtime for Korean DART filings. The
project focuses on numeric answers that can be traced back to source evidence,
structured calculation artifacts, and reproducible benchmark gates instead of
free-form LLM text alone.

## Problem

General-purpose RAG systems often fail on financial filings for reasons that
look small but are fatal for numeric QA:

- selecting the wrong row, subtotal, segment, or reporting period
- treating a calculated value as if it were directly stated
- losing citation and provenance while composing the final answer
- passing benchmark rows by adding brittle question-specific rules
- accepting stale compatibility fields over the canonical runtime trace

The goal of this project is not only to answer questions, but to make each
answer inspectable: what was retrieved, what was calculated, why it was accepted,
and which gate would catch a regression.

## What I Built

### Evidence-First Runtime

- section/table-aware DART parsing and hybrid retrieval
- explicit retrieval debug traces and provenance-carrying evidence items
- structured numeric outputs through `answer_slots`, `structured_result`, and
  `resolved_calculation_trace`
- deterministic calculation execution for arithmetic, ratios, differences, and
  growth rates

### Multi-Agent Skeleton

- `Orchestrator` decomposes the query and merges accepted artifacts
- `Analyst` handles numeric extraction, formula planning, and calculation
- `Researcher` handles narrative/context retrieval
- `Critic` validates grounding, target refs, acceptance reasons, and blocking
  issues
- shared `tasks`, `artifacts`, `evidence_pool`, `critic_reports`, and
  `task_artifact_trace` contracts replace ad hoc agent chat state
- self-reflection retry decisions are bounded as `ReflectionRequest ->
  ReflectionPlan -> ReflectionAction -> ReflectionReport`, then recorded as a
  `reflection_report` artifact when retry preparation runs

### Runtime Acceptance Gates

- final synthesis blocks on task/artifact integrity errors
- critic acceptance is contract-based, not score-threshold-based
- rejected critic reports block final close even when a diagnostic score is high
- planner/replan feedback surfaces critic rejection status, reasons, and target
  refs for reviewer handoff

### Report-Scoped Cache Safety

- report-cache candidates are trace-only and non-serving by default
- local cache-index diagnostics can be reviewed without bypassing retrieval
- rehydrated candidates remain outside the live ledger unless a future producer
  policy explicitly admits them
- `review_report_cache_index_contract` provides a one-command reviewer gate for
  the candidate-only cache path

## Key Design Choices

### LLMs For Semantics, Code For Execution

The LLM can help infer intent, concepts, and narrative meaning. Deterministic
code owns arithmetic, dependency binding, dedupe, ordering, provenance checks,
and answer acceptance.

### Domain Terms Stay Out Of Runtime Branches

Financial vocabulary belongs in ontology, retrieval policy, config, or reviewed
data artifacts. Runtime control-flow code implements generic mechanisms such as
slot coverage, evidence diversity, required operands, and contract validation.

### Benchmark Results Are Gates, Not Patch Targets

Benchmarks expose the layer that is failing: ontology, retrieval policy, parser
structure, planner contract, evidence schema, or evaluator definition. Runtime
patches should generalize across questions instead of memorizing benchmark IDs.

### Cache Is Candidate-Only Until Proven Safe

Report-scoped cache work is intentionally staged. The current system can inspect
and validate cache candidates, but cache serving, writes, ledger insertion, and
retrieval bypass remain disabled. The disabled capability boundary is documented
in [report_cache_capability_contract.md](../architecture/report_cache_capability_contract.md).

## Evidence Of Progress

| Area | Current evidence |
| --- | --- |
| Runtime contract | `task_artifact_trace` exposes task/artifact integrity status and structured issues |
| Critic boundary | `critic_report_runtime_acceptance_state()` separates runtime acceptance from diagnostic scores |
| Reflection boundary | `reflection_report` artifacts record retry action, budget use, targets, and blocking issues without accepting final answers |
| Final close gate | rejected critic reports produce blocking integrity errors |
| MAS smoke | real Orchestrator + Analyst + Researcher + Critic + Merge path is covered by smoke tests |
| Runtime cleanup | canonical calculation state lives in `resolved_calculation_trace` / artifacts; legacy top-level calculation/debug fields are optional compatibility bridges |
| Cache safety | `review_report_cache_index_contract` reports `reviewer_handoff.status = ready` while serving remains disabled |
| Experiment report | [portfolio_experiment_report.md](portfolio_experiment_report.md) summarizes problem framing, method comparison, and quantitative evidence |
| Portfolio demo | `portfolio_demo` prints answer, citations, trace, integrity, critic, and cache handoff surfaces |
| Test coverage | latest full `python -m unittest discover -s tests` passed 940 tests after reflection ledger handoff |

## Representative Commands

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe -m src.ops.audit_runtime_domain_terms
.\.venv\Scripts\python.exe -m src.ops.portfolio_demo
.\.venv\Scripts\python.exe -m src.ops.review_report_cache_index_contract
```

## Portfolio Story

This project shows how to turn a financial RAG prototype into a contract-driven
runtime. The core engineering work is not prompt tuning; it is designing the
handoff between retrieval, structured evidence, deterministic calculation,
bounded reflection, critic acceptance, and benchmark review so that
improvements remain auditable and hard to overfit.

## What Is Still Intentionally Disabled

- cache serving and retrieval bypass
- automatic cache writes
- ledger insertion from rehydrated cache candidates
- LLM critic as an acceptance authority
- benchmark-specific runtime branches

## Reviewer Path

For a quick review, start with
[portfolio_demo_walkthrough.md](portfolio_demo_walkthrough.md), then scan the
runtime cleanup row above to understand why stale top-level calculation mirrors
are no longer treated as the source of truth. For an interview or project
presentation, use [portfolio_presentation_outline.md](portfolio_presentation_outline.md).
