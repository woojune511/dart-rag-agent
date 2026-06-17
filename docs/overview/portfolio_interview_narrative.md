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

The strongest current evidence is narrow and partly diagnostic. Reviewer gates
are ready, and the latest store-fixed expanded full-system refresh reached
`6 / 9` numeric PASS. That is below the documented `7 / 9` threshold for
rerunning the plain baseline, so I treat it as a stop-line rather than a
promoted ablation win. The useful reproduced separator is `SKH_T3_080`, where
the structural path binds the right foreign-currency gain/loss rows. The
remaining failures identify concrete residual work in final numeric
preservation and sign/display handling.

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

Current expanded refresh:

| Run | Result | Interpretation |
| --- | ---: | --- |
| Structural full-system refresh | `6 / 9` numeric PASS | Below the `7 / 9` threshold for running the plain baseline; use as a stop-line. |
| Reproduced separator | `SKH_T3_080` PASS | Structural binding keeps `573,884백만원 - 906,120백만원 = -3,322억원`. |
| Residual failures | `POS_T1_057`, `KBF_T2_018`, `SKH_T1_060` | Evidence is often present, but final composition/sign/display or aggregation remains unstable. |

Historical hard structural replay:

| Variant | Result | Interpretation |
| --- | ---: | --- |
| Structural full-system | `5 / 5` numeric PASS | Current-period borrowing rows stayed bound in `SKH_T1_060`. |
| Plain retrieval counterpart | `4 / 5` numeric PASS | Formula/runtime fixes carried most cases, but `SKH_T1_060` used prior-period borrowing rows. |

The point is not that every question needs more structure or that a baseline was
artificially weakened. The point is that financial RAG needs trace-preserving
runtime contracts because answer-level text can hide operand and unit mistakes.
The current expanded refresh also shows why I do not promote an ablation until
the full-system variant itself clears the documented threshold.

If asked why structure matters after adding ontology and deterministic
calculation, use `SKH_T1_060`: both variants had a deterministic formula and
the same denominator, but plain selected `3,833,263 + 9,073,567 + 6,497,790`
from `period_focus=prior`, while structural selected
`4,145,647 + 10,121,033 + 9,490,410` from `period_focus=current`.

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

```bash
uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates
uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_demo
```

Then open:

- [portfolio_one_pager.md](portfolio_one_pager.md)
- [portfolio_resume_snippets.md](portfolio_resume_snippets.md)
- [portfolio_experiment_report.md](portfolio_experiment_report.md)
- [structural_trace_diagnostics.md](../evaluation/structural_trace_diagnostics.md)
