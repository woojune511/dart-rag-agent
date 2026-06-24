# Portfolio Presentation Outline

This outline is for a short portfolio presentation, interview walkthrough, or
project review. It assumes the audience already knows LLM/RAG basics, so the
talk should focus on the engineering story: making financial RAG answers
inspectable through runtime contracts, traces, and gates.

For spoken answers, start from
[portfolio_interview_narrative.md](portfolio_interview_narrative.md). This file
is the slide structure.

## Slide 1. Title And Claim

**DART Multi-Agent Financial Analysis Lab**

Message:

- Contract-driven Agentic RAG runtime for numeric QA over Korean DART filings.
- The claim is not a new model or TableQA SOTA result.
- The claim is systems engineering: numeric financial answers should be
  accepted through evidence, operands, formulas, critic state, and trace gates.

Headline evidence:

- Latest expanded structural store-fixed refresh: `9 / 9` numeric PASS.
- Lightweight reviewer gates: `Status: ready`.
- Benchmark-specific runtime branches remain disabled.

## Slide 2. Problem

Financial-document RAG can look grounded while being numerically wrong.

Failure modes:

- wrong row, subtotal, segment, entity, or reporting period
- correct citation in prose but missing provenance in runtime state
- calculated value presented as directly stated
- stale compatibility fields overriding the canonical trace
- benchmark score improved by brittle question-specific rules

Message:

- The hard part is not only retrieving a relevant chunk. The hard part is
  keeping evidence, operand binding, calculation, rendering, and acceptance
  aligned.

## Slide 3. Runtime Contract

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

Key state:

- `tasks`
- `artifacts`
- `evidence_pool`
- `critic_reports`
- `task_artifact_trace`
- `answer_slots`, `structured_result`, `resolved_calculation_trace`

Message:

- Agent communication is typed ledger state, not free-form chat.
- Final answer text is the presentation layer; the contract is the trace behind
  it.

## Slide 4. LLM Semantics, Deterministic Execution

Boundary:

- LLMs: intent, concept interpretation, narrative meaning, planning support.
- Code: arithmetic, unit handling, dependency binding, dedupe, ordering,
  provenance checks, validation, and rendering.

Numeric path:

```text
retrieve/evidence
  -> reconcile_plan
  -> operand extraction
  -> formula/calculator
  -> aggregate subtasks
  -> public projection
```

Message:

- The calculator does not invent evidence. It assembles grounded operands into
  an inspectable result.
- Domain vocabulary lives in ontology, retrieval policy, config, or reviewed
  data, not runtime branches.

## Slide 5. Representative Demo Case

Use `KAB_T1_066` as the compact visible case.

Question:

```text
카카오뱅크 2023년 연결기준 CIR(판매비와관리비/경비차감전영업이익)을 계산해 줘.
```

Expected demo answer:

```text
2023년 CIR은 37.47%입니다. 계산: 판매비와관리비 4,355억원 / 경비차감전영업이익 11,623억원.
```

Why it matters:

- rejects a plausible wrong denominator row
- recovers both operands from one MDA table
- renders from the canonical calculation trace
- exposes citations, operands, formula, integrity, critic acceptance, and cache
  handoff

Command:

```bash
uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_demo
```

## Slide 6. Final Regression Story

Use `KBF_T2_018` and `SKH_T1_060` to show why trace contracts matter.

`KBF_T2_018`:

- final answer/evidence showed the right numbers:
  `3,146,409`, `1,847,775`, `70.28%`
- public `calculation_result` / `calculation_plan` projection could remain
  stale
- fix: synchronize final-answer numeric surfaces back into projected growth
  trace

`SKH_T1_060`:

- correct task-output operands could be overwritten by a conflicting direct row
  from a disjoint source context
- fix: periodless table-label metadata lookup plus source-row provenance guard
- final structural answer: `42.02%`

Message:

- The fixes were projection/provenance contracts, not company-specific or
  benchmark-ID branches.

## Slide 7. Evaluation And Gates

Current structural evidence:

| Scope | Result |
| --- | ---: |
| Expanded structural store-fixed eval-only | `9 / 9` numeric PASS |
| Plain retrieval diagnostic comparison | `5 / 9` numeric PASS |
| Runtime domain-term audit | pass |
| Portfolio review gates | ready |

Reviewer commands:

```bash
uv run --with-requirements requirements-review.txt python -m src.ops.audit_runtime_domain_terms
uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_demo
uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates
```

Capability-specific gates:

```bash
uv run --with-requirements requirements-review.txt python -m src.ops.review_report_cache_index_contract
uv run --with-requirements requirements-review.txt python -m src.ops.report_cache_promotion_evidence_gate
uv run --with-requirements requirements-review.txt python -m src.ops.reflection_promotion_gate
uv run --with-requirements requirements-review.txt python -m src.ops.reference_note_capability_gate
uv run --with-requirements requirements-review.txt python -m src.ops.promotion_trace_materiality_gate
```

Message:

- Generic metrics are useful signals, but final acceptance depends on operands,
  formulas, source references, rendered displays, integrity, and critic state.

## Slide 8. Limits And Closing

Do not overclaim:

- not a new model architecture
- not a general TableQA SOTA result
- not proof that structure helps every question
- not a claim that arithmetic hallucination is impossible

Intentionally disabled:

- cache serving and retrieval bypass
- automatic cache writes
- cache candidate insertion into the live ledger
- LLM critic as final acceptance authority
- benchmark-specific runtime routing branches

Closing line:

> This project is my answer to the question: how do we make a financial RAG
> system that a reviewer can audit, not just a model that sounds confident?
