# Portfolio One-Pager

## DART Financial Agentic RAG

An evidence-first financial QA agent for Korean DART filings. It retrieves
structured source evidence, uses an LLM to plan the required analysis, executes
numeric operations deterministically, and returns an answer with inspectable
calculation and provenance traces.

The portfolio claim is applied LLM systems engineering. It is not a new model,
a general TableQA algorithm, or a multi-agent framework.

## Problem

Financial-document RAG often produces plausible but incorrect answers because
it selected the wrong row, subtotal, period, unit, segment, or reporting entity.
Even a citation can be misleading when the answer does not reveal which values
were bound to the formula.

This project treats those failures as runtime contract violations. A numeric
answer should show:

- which retrieval queries and filters ran;
- which chunks, table rows, and source sentences were selected;
- which operands and periods were bound;
- which deterministic formula was executed;
- whether the final display agrees with signed source values and provenance.

## Core pipeline

```text
Question
  -> LLM semantic plan
  -> Chroma dense retrieval + BM25 sparse retrieval
  -> reciprocal-rank fusion and structural reranking
  -> evidence selection and operand binding
  -> deterministic formula execution
  -> provenance and consistency validation
  -> answer + structured_result + resolved_calculation_trace
```

### What the LLM does

- classifies intent and operation family;
- maps the question to ontology concepts;
- proposes retrieval queries and required operands;
- interprets ambiguous narrative evidence when deterministic structure is not
  sufficient.

### What deterministic code does

- applies filing metadata filters and retrieval budgets;
- fuses dense and sparse retrieval results;
- matches rows, headers, periods, units, and consolidation scope;
- binds dependencies and deduplicates operands;
- performs arithmetic and unit conversion;
- verifies evidence, calculation, and final-answer consistency.

This separation is the main agentic design choice: LLMs handle semantics, while
code owns execution and acceptance.

## Technical highlights

### Hybrid retrieval with traceability

The canonical Chroma runtime uses OpenAI `text-embedding-3-large` dense vectors
with 3,072 dimensions. BM25 is a separate lexical index. Their candidates are
combined with reciprocal-rank fusion, then reranked using document structure and
query scope. `retrieval_debug_trace` explains the query bundle, filters,
candidate counts, and final selection.

### Structure-preserving financial evidence

The parser retains section paths, table context, row/header relationships,
period focus, unit hints, statement type, and consolidation scope. Numeric
answers preserve source row identifiers and source-visible display values.

### Canonical numeric contracts

- `answer_slots` preserve display, role, period, unit, and provenance.
- `structured_result` is the caller-facing structured answer.
- `resolved_calculation_trace` is the canonical operand/formula/result trace.

Legacy flat mirrors may not override these surfaces.

### Generalization guardrails

Financial vocabulary lives in ontology, retrieval policy, config, or documented
data—not company- or benchmark-specific runtime branches. Benchmark failures
are classified by system layer before any change is made.

## Representative result

The latest recorded expanded structural run closed `9 / 9` numeric questions.
The most recent plain-retrieval comparison remains `5 / 9` and exposes three
useful failure families: display/unit mismatch, wrong denominator, and wrong
row/period binding.

These numbers are not presented as a freshly synchronized leaderboard
ablation. They are reproducible engineering evidence for the failure taxonomy.
The methodology and limitations are in
[portfolio_experiment_report.md](portfolio_experiment_report.md).

A compact representative case is the CIR calculation:

```text
4,355억원 / 11,623억원 = 37.47%
```

The important part is not the division itself. The runtime must find both
operands in coherent source context, reject plausible competing rows, preserve
their provenance, execute the formula, and force the final prose to follow the
verified trace.

## Review path

Run the fixture-backed core demo from the repository README:

```bash
uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_demo
```

The first scan should confirm four connected surfaces in one output:

1. an LLM-backed semantic plan with required operands;
2. a hybrid retrieval trace with candidate and selected-chunk counts;
3. deterministic operands, formula, and result;
4. citations, task/artifact integrity, and critic acceptance.

The demo is a source-controlled runtime projection, not a live provider call.
Use the [question trace walkthrough](question_trace_walkthrough.md),
[experiment report](portfolio_experiment_report.md), or
[technical highlights](technical_highlights.md) only when a deeper code,
evidence, or implementation review is useful.

## Scope boundary

The default product runtime is `FinancialAgent.run()`.

- Core: parser, hybrid retrieval, evidence/operand binding, deterministic
  calculation, answer projection, and runtime traces.
- Evaluation: benchmark runner, evaluator, regression fixtures, and review
  gates that consume core contracts without defining runtime behavior.
- Experimental: MAS orchestration, graph-expansion variants, cache promotion,
  and extended reflection/review workflows.
- Legacy: compatibility imports and response mirrors scheduled for removal once
  callers and contract tests no longer require them.

This boundary keeps the portfolio story focused while preserving deeper
experiments as optional evidence of system design work.
