# Portfolio Interview Narrative

This is the compact version of the project story for a portfolio review,
screening call, or interview. It assumes the listener already understands RAG,
LLM agents, retrieval traces, and grounding/evaluation terminology.

## 30-Second Version

I built a contract-driven financial RAG runtime for Korean DART filings. The
main problem is that numeric answers can look grounded while using the wrong
row, period, subtotal, unit, or provenance path.

My approach separates LLM semantics from deterministic execution: the LLM helps
with intent and planning, while code owns operand binding, arithmetic, unit
handling, validation, and final rendering. The latest expanded structural
store-fixed replay is `9 / 9` numeric PASS across six company runs, and the
reviewer commands now report `ready`.

## 2-Minute Version

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

The strongest current evidence is narrow and trace-based. Reviewer gates are
ready, and the latest expanded structural store-fixed refresh reached `9 / 9`
numeric PASS. The most recent plain-retrieval comparison remains `5 / 9`; I use
it as diagnostic evidence for display/unit, denominator, and row-binding
failure modes rather than as a freshly synchronized leaderboard.

Two final fixes are good examples of the method. `KBF_T2_018` had correct final
text and evidence, but the public calculation projection could remain stale, so
the fix synchronized final-answer numeric surfaces back into the growth trace.
`SKH_T1_060` had correct task-output operands, but direct-evidence repair could
overwrite them with a conflicting row from another source, so the fix protected
task-output slots by source-row provenance and improved table-label matching.

## 5-Minute Walkthrough

Start with the problem: a financial RAG system can cite a relevant DART filing
chunk and still answer incorrectly because the selected number came from the
wrong row, period, subtotal, unit, or source path. That is why the project
treats answer quality as a runtime-contract problem, not just retrieval recall
or final-text fluency.

Then explain the architecture. The runtime keeps a typed ledger with `tasks`,
`artifacts`, `evidence_pool`, `critic_reports`, and `task_artifact_trace`.
Analyst-style numeric work produces operand sets, calculation plans, and
calculation results. Researcher-style work handles narrative context. Critic
reports provide target refs, acceptance reasons, and blocking issues. The final
answer is a presentation layer over that state.

The key design boundary is LLM semantics versus deterministic execution. LLMs
are useful for intent, concept interpretation, and plan support. Code owns
arithmetic, unit conversion, dependency binding, dedupe, ordering, provenance
checks, and final rendering. This makes numeric failures debuggable as
contracts: retrieval, evidence, reconcile plan, operand extraction, formula,
aggregate task reuse, projection, or evaluator.

For a compact case, use `KAB_T1_066`. The system had to reject a plausible
wrong denominator, avoid over-blocking a correct lookup, recover both operands
from the same MDA table, and force final prose to follow the calculation trace.
The demo answer is:

```text
2023년 CIR은 37.47%입니다. 계산: 판매비와관리비 4,355억원 / 경비차감전영업이익 11,623억원.
```

For the final regression story, use `KBF_T2_018` and `SKH_T1_060`.
`KBF_T2_018` showed that correct human-visible answer text is not enough if
`calculation_result`, `calculation_plan`, or `answer_slots` stay stale.
`SKH_T1_060` showed that a later direct-evidence repair can corrupt a correct
aggregate operand if source-row provenance is ignored. Both fixes were generic
projection/provenance contracts, not benchmark-specific branches.

Close with the gates. The lightweight reviewer path runs without DART downloads
or benchmark stores:

```bash
uv run --with-requirements requirements-review.txt python -m src.ops.audit_runtime_domain_terms
uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_demo
uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates
```

All three were verified on the current `main`: domain-term audit passed,
`portfolio_demo` reports `Readiness: ready`, and `portfolio_review_gates`
reports aggregate `Status: ready`.

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
| Structural full-system refresh | `9 / 9` numeric PASS | Current expanded structural quality claim. |
| Plain retrieval comparison | `5 / 9` numeric PASS | Diagnostic baseline; not rerun after PR #78. |
| Reproduced separators | `POS_T1_057`, `CEL_T1_013`, `SKH_T3_080` | Structural binding keeps key numeric surfaces that plain retrieval loses. |
| Final residual closure | `KBF_T2_018`, `SKH_T1_060` | Stale projection and disjoint-source operand overwrite closed by generic contracts. |

Historical hard structural replay:

| Variant | Result | Interpretation |
| --- | ---: | --- |
| Structural full-system | `5 / 5` numeric PASS | Current-period borrowing rows stayed bound in `SKH_T1_060`. |
| Plain retrieval counterpart | `4 / 5` numeric PASS | Formula/runtime fixes carried most cases, but `SKH_T1_060` used prior-period borrowing rows. |

The point is not that every question needs more structure or that a baseline was
artificially weakened. The point is that financial RAG needs trace-preserving
runtime contracts because answer-level text can hide operand and unit mistakes.
The current expanded refresh also shows why I do not promote a result until the
full-system variant itself clears the documented threshold.

If asked why structure matters after adding ontology and deterministic
calculation, use historical `SKH_T1_060`: both variants had a deterministic formula and
the same denominator, but plain selected `3,833,263 + 9,073,567 + 6,497,790`
from `period_focus=prior`, while structural selected
`4,145,647 + 10,121,033 + 9,490,410` from `period_focus=current`.

If asked what changed in the final closure, say that structural metadata was
necessary but not sufficient: the current fix also protects task-output operands
from disjoint conflicting evidence and synchronizes final-answer numeric
surfaces into the public calculation projection.

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
- [portfolio_experiment_report.md](portfolio_experiment_report.md)
- [technical_highlights.md](technical_highlights.md)
- [portfolio_deep_dive_qa.md](portfolio_deep_dive_qa.md)
- [portfolio_resume_snippets.md](portfolio_resume_snippets.md)
- [structural_trace_diagnostics.md](../evaluation/structural_trace_diagnostics.md)
