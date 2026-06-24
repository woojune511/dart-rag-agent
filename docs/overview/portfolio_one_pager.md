# Portfolio One-Pager

## Project

**DART Multi-Agent Financial Analysis Lab**

An evidence-backed financial-document RAG runtime for Korean DART filings. The
project focuses on numeric answers that can be traced back to source evidence,
structured calculation artifacts, and reproducible benchmark gates instead of
free-form LLM text alone.

## Reader And Claim Boundary

This one-pager assumes the reader already understands RAG, embeddings, agentic
workflows, and grounding/evaluation terminology. The claim is not a new LLM
architecture or a general TableQA algorithm; it is a research-engineering system
for making financial RAG answers inspectable through representation, runtime
contracts, deterministic numeric execution, and trace-based gates.

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
| Cache safety | `review_report_cache_index_contract` reports `reviewer_handoff.status = ready` while bypass, writes, serving, and ledger insertion remain disabled |
| Cache promotion evidence | fixture plus reviewed trace-summary cases without enabling cache behavior |
| REFERENCE_NOTE boundary | `reference_note_capability_gate` keeps note traversal as Researcher graph-expansion context, not cache serving or final acceptance authority |
| Promotion trace materiality | reviewed trace summaries cover distinct source/action/fallback surfaces |
| Source-visible ratio close | `KAB_T1_066` resolves CIR from one MDA table: `4,355억원 / 11,623억원 = 37.47%`, numeric `PASS`, grounded rendering `1.000` |
| Expanded structural refresh | structural full-system `9 / 9` numeric PASS after PR #78 operand projection repair |
| Plain retrieval comparison | most recent plain retrieval comparison remains `5 / 9`; use it as diagnostic baseline evidence, not a freshly synchronized final ablation |
| Structural separators | `POS_T1_057`, `CEL_T1_013`, and `SKH_T3_080` remain representative plain-vs-structural failure diagnostics |
| Historical hard replay | prior structural `5 / 5` vs plain `4 / 5` replay remains diagnostic evidence for current/prior row binding, not the latest promoted result |
| Experiment report | [portfolio_experiment_report.md](portfolio_experiment_report.md) summarizes problem framing, method comparison, and quantitative evidence |
| Portfolio demo | `portfolio_demo` prints answer, citations, trace, integrity, critic, and cache handoff surfaces |
| Review gate bundle | `portfolio_review_gates` aggregates demo, cache, reflection, trace materiality, and REFERENCE_NOTE boundary proof into one ready/not-ready command |
| Test coverage | full unittest discovery and runtime domain-term audit are maintained as gates; latest counts live in [project_status.md](project_status.md) and [current_runtime_cleanup_split_manifest.md](../architecture/current_runtime_cleanup_split_manifest.md) |

## Review Commands

Use the lightweight reviewer commands in [../../README.md](../../README.md).
This one-pager avoids duplicating the command list so dependency-profile
guidance stays in one place.

## Portfolio Story

This project shows how to turn a financial RAG prototype into a contract-driven
runtime. The core engineering work is not prompt tuning; it is designing the
handoff between retrieval, structured evidence, deterministic calculation,
bounded reflection, critic acceptance, and benchmark review so that
improvements remain auditable and hard to overfit.

The compact example starts with KAB CIR: the system had to reject a plausible
wrong row, avoid overzealous aggregate-result blocking, recover both operands
from the same source table, and force final prose to follow the canonical
calculation trace. The expanded story is deliberately conservative: the latest
structural full-system refresh is `9 / 9` numeric PASS, but the most recent
plain-retrieval comparison remains the earlier `5 / 9` diagnostic baseline.
The useful signal is the failure taxonomy: `POS_T1_057`, `CEL_T1_013`, and
`SKH_T3_080` show display/unit, denominator, and row-binding improvements,
while the final `KBF_T2_018` and `SKH_T1_060` closure shows how stale
projection and disjoint-source operand repair were fixed without adding
benchmark-specific runtime branches.

## What Is Still Intentionally Disabled

- cache serving and retrieval bypass
- automatic cache writes
- ledger insertion from rehydrated cache candidates
- LLM critic as an acceptance authority
- benchmark-specific runtime branches

## Reviewer Path

For a quick review, start with the README commands, then use
[portfolio_demo_walkthrough.md](portfolio_demo_walkthrough.md) for the compact
runtime output and [portfolio_experiment_report.md](portfolio_experiment_report.md)
for the ablation evidence. For an interview or project presentation, use
[portfolio_interview_narrative.md](portfolio_interview_narrative.md) or
[portfolio_presentation_outline.md](portfolio_presentation_outline.md).
