# Portfolio Interview Narrative

This is the compact version of the project story for a portfolio review,
screening call, or interview. It assumes the listener already understands RAG,
LLM agents, retrieval traces, and grounding/evaluation terminology.

## 60-Second Version

I built a contract-driven financial RAG runtime for Korean DART filings. The
project is not a new foundation model or a SOTA TableQA benchmark; the systems
claim is that numeric financial answers should be accepted through inspectable
runtime state, not through plausible final text.

The core failure mode is that a financial RAG answer can look grounded while the
wrong row, period, subtotal, unit, or provenance path is used underneath. To
address that, the runtime separates LLM semantics from deterministic execution:
LLMs help with intent, concept interpretation, and planning, while code handles
operand binding, arithmetic, unit handling, validation, and final acceptance
gates.

The system represents agent handoff as a typed artifact ledger:
`tasks`, `artifacts`, `evidence_pool`, `critic_reports`, and
`task_artifact_trace`. Numeric answers publish `answer_slots`,
`structured_result`, and `resolved_calculation_trace`, so a reviewer can inspect
which operands were used, where they came from, which formula ran, and whether
the final answer followed the trace.

The strongest current evidence is narrow but defensible. A closed structural
ablation shows the structural full-system path at `4/4` numeric PASS versus a
plain retrieval counterpart at `3/4`. The separating case is not "better prose";
it is unit/provenance drift in the plain path. The structural path preserves the
expected operands through final calculation.

## Problem Framing

The project treats financial-document RAG failures as runtime contract failures.
A relevant chunk and a fluent answer are not enough if the selected value comes
from the wrong table row, reporting period, subtotal, entity scope, or unit.

The target behavior is:

- retrieve evidence with enough source shape to identify table/row context
- bind required operands to source-backed structured state
- execute numeric operations deterministically
- render answers from the canonical calculation trace
- block or flag final close when artifact integrity or critic acceptance fails
- keep domain vocabulary out of runtime control-flow branches

## Method Summary

The runtime has three main design choices.

First, DART ingestion preserves document shape. The current claim is not
"cell-level embeddings." It is value-cell-first structured metadata:
`table_value_records_json` preserves row headers, column headers, period text,
aggregate role, and unit hints so retrieval and extraction can reason over more
than flat text.

Second, numeric execution is deterministic after semantic planning. The LLM can
help infer the intended concept or formula, but arithmetic, unit handling,
dependency binding, dedupe, and validation are code paths with testable
contracts.

Third, agent behavior is ledger-based. Orchestrator, Analyst, Researcher, and
Critic roles communicate through typed artifacts rather than free-form chat
state. Reflection is bounded as `ReflectionRequest -> ReflectionPlan ->
ReflectionAction -> ReflectionReport`; it is recorded as reviewer evidence, not
treated as final-answer authority.

## Experiment Claim

The main experiment claim is deliberately scoped:

> Structured provenance plus dependency-operand preservation reduces final
> operand/unit drift when relevant numeric evidence is available but can be
> rebound or rendered at the wrong scale.

Current closed structural ablation:

| Variant | Numeric result | Interpretation |
| --- | ---: | --- |
| Structural full-system | `4/4` PASS | Preserves structural provenance and dependency operands through final calculation. |
| Plain retrieval counterpart | `3/4` PASS | Fails the separating case through unit/provenance drift. |

The point is not that every question needs more structure or that a baseline was
artificially weakened. The point is that financial RAG needs trace-preserving
runtime contracts because answer-level text can hide operand and unit mistakes.

## What I Would Emphasize In An Interview

- I did not solve numeric reliability by prompt wording alone.
- I kept domain vocabulary in ontology, policy, config, or data artifacts
  instead of adding benchmark-specific runtime branches.
- I used LLMs where semantic judgment is useful and deterministic code where
  execution must be auditable.
- I treated evaluation as trace inspection: operands, formula, unit handling,
  source references, critic state, and rendered display.
- I kept cache serving, retrieval bypass, cache writes, and LLM critic authority
  intentionally disabled until their safety contracts are proven.

## What I Would Not Overclaim

- This is not a new model architecture.
- This is not a general TableQA SOTA result.
- This does not prove structure helps every DART question.
- This does not claim arithmetic hallucination is impossible; it moves numeric
  execution out of free-form generation.
- This does not use RAGAS-style generic metrics as final acceptance. Generic
  metrics are useful signals, but final acceptance depends on trace-based
  numeric grounding.

## Best Demo Path

Use these commands for a reviewer-facing walkthrough:

```powershell
.\.venv\Scripts\python.exe -m src.ops.portfolio_review_gates
.\.venv\Scripts\python.exe -m src.ops.portfolio_demo
```

Then open:

- [portfolio_one_pager.md](portfolio_one_pager.md)
- [portfolio_experiment_report.md](portfolio_experiment_report.md)
- [structural_trace_diagnostics.md](../evaluation/structural_trace_diagnostics.md)
