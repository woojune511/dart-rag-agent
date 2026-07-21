# DART Financial Agentic RAG

An evidence-first financial QA agent for Korean DART filings. It combines
hybrid retrieval, LLM-based semantic planning, deterministic calculation, and
traceable provenance so a reviewer can inspect how each numeric answer was
produced.

> Portfolio scope: the product is the single-agent `FinancialAgent` runtime.
> Multi-agent orchestration, cache promotion, and extended review machinery are
> experiments around the core, not the main product claim.

## The problem

Financial RAG can return a plausible answer while selecting the wrong row,
period, unit, subtotal, or entity. Free-form citations do not reveal which
operands were used or whether a displayed number was retrieved or calculated.

This project makes that path explicit:

```mermaid
flowchart LR
    Q["User question"] --> P["LLM semantic planner"]
    P --> R["Hybrid retrieval"]
    R --> E["Evidence and operand binding"]
    E --> C["Deterministic calculation"]
    C --> V["Provenance and consistency checks"]
    V --> A["Answer plus trace"]
```

The LLM interprets intent, concepts, and required operands. Code owns metadata
filtering, dense/BM25 fusion, row binding, arithmetic, unit handling, validation,
and final trace construction.

## Core engineering

### 1. Structure-aware DART ingest

The parser preserves filing structure such as `section_path`, table context,
period, unit, statement type, and consolidation scope. Structured cells and
their row/header relationships remain available after chunking.

### 2. Hybrid retrieval

- Chroma stores dense vectors. The canonical remote embedding runtime is OpenAI
  `text-embedding-3-large` with 3,072 dimensions.
- BM25 provides a separate sparse lexical signal.
- Reciprocal-rank fusion combines dense and sparse candidates.
- Metadata filters and deterministic structural reranking prefer compatible
  company, filing, period, section, table, and consolidation context.
- `retrieval_debug_trace` records the query bundle, filters, budgets, selected
  chunks, and policy decisions.

Contextual ingest may prepend an LLM- or metadata-generated context string
before embedding, but the Chroma vector itself is a dense embedding vector, not
a sparse vector and not a chat-model hidden state.

### 3. Agentic numeric reasoning

`FinancialAgent.run()` is the public runtime entry point. The graph plans the
question, retrieves evidence, resolves required operands, executes a formula,
and validates the result. Numeric output is carried through three canonical
surfaces:

- `answer_slots`: display-preserving values and operand roles
- `structured_result`: caller-facing structured answer
- `resolved_calculation_trace`: operands, formula, result, and provenance

### 4. Evidence-first acceptance

An answer is not accepted merely because generated prose sounds correct.
Numeric surfaces must agree with signed evidence values, selected rows must
preserve source identifiers, and calculated claims must be reproducible from
the trace.

### 5. Reproducible evaluation

The repository includes contract tests, runtime-domain-term auditing, focused
benchmark profiles, and store-fixed eval-only workflows. Benchmark failures are
classified by parser, retrieval, ontology/policy, planning, evidence, calculation,
or projection layer instead of being patched with question-specific branches.

## Representative evidence

| Signal | Result | Interpretation |
| --- | ---: | --- |
| Expanded structural numeric set | 9 / 9 PASS | Latest store-fixed full-system close after operand/provenance repairs |
| Plain-retrieval comparison | 5 / 9 PASS | Diagnostic baseline for row, denominator, and display/unit failures |
| Full unit test discovery | 1,349 PASS | Current baseline including provenance and retrieval-owner regressions |
| Portfolio review gates | READY | Fixture-backed review surface is reproducible |

The structural and plain results are not presented as a freshly synchronized
leaderboard ablation. They are engineering evidence for the observed failure
taxonomy. See
[portfolio_experiment_report.md](docs/overview/portfolio_experiment_report.md)
for the methodology and limitations.

## Quick review

The lightweight profile runs without the full ingest, ML, benchmark, and app
stack:

```bash
uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_demo
uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates
uv run --with-requirements requirements-review.txt python -m src.ops.audit_runtime_domain_terms
```

Then read:

1. [Portfolio one-pager](docs/overview/portfolio_one_pager.md)
2. [Question trace walkthrough](docs/overview/question_trace_walkthrough.md)
3. [Experiment report](docs/overview/portfolio_experiment_report.md)
4. [Technical highlights](docs/overview/technical_highlights.md)

## Run the API

The full profile is needed for ingest, Chroma, the API, benchmarks, and the full
test suite. Provider selection also depends on the configured API keys.

```bash
uv run --with-requirements requirements.txt uvicorn main:app --reload --port 8000
uv run --with-requirements requirements.txt python -m unittest discover -s tests
```

Swagger UI is available at `http://localhost:8000/docs`.

## Scope boundary

| Surface | Role | Portfolio treatment |
| --- | --- | --- |
| Core runtime | parser, retrieval, evidence binding, calculation, answer projection | Main product story |
| Evaluation | evaluator, benchmarks, gates, regression fixtures | Supporting proof, never imported by the default runtime |
| Experimental | MAS facade, graph-expansion variants, cache/reflection promotion paths | Optional appendix; disabled or isolated by default |
| Legacy compatibility | flat mirrors, old import paths, callerless wrappers | Remove after caller and contract checks |

The active cleanup sequence and deletion criteria are documented in
[core_runtime_surface_refactoring_plan.md](docs/architecture/core_runtime_surface_refactoring_plan.md).

## Repository map

```text
main.py                    FastAPI entry point
src/api/                   HTTP boundary
src/agent/                 FinancialAgent graph and core runtime contracts
src/processing/            DART parsing and chunk preparation
src/storage/               embeddings, Chroma, BM25, and structure storage
src/config/                ontology, retrieval policy, and runtime config
src/experimental/mas/      optional multi-agent experiment
src/ops/                   evaluation, benchmark, and reviewer commands
tests/                     contract and regression tests
docs/                      reviewer guides and internal history
```

Internal status and experiment logs remain available for reproducibility, but
they are not the recommended first-read path. Start with the four documents in
the quick review section.
