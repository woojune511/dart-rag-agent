# Portfolio Demo Walkthrough

This walkthrough explains the smallest reviewer-facing demo for the current
single-agent runtime contract. It is fixture-backed, so it runs without DART
downloads, vector-store setup, API keys, or benchmark result bundles.

The fixture is a source-controlled projection of real runtime fields. It proves
that the public contract remains coherent and reviewable; it does not claim to
perform live retrieval or an LLM call during the demo command.

## Run It

```bash
uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_demo
```

For machine-readable output:

```bash
uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_demo --format json
```

## Review Order

The default output keeps the core portfolio story in execution order:

1. `Semantic Plan` shows the planner strategy, operation, and required
   operands.
2. `Retrieval Trace` shows hybrid-search telemetry, query count, candidates,
   and the selected chunk.
3. `Calculation Trace` binds source-visible operands to a deterministic
   formula and result.
4. `Citations` and the selected source keep provenance visible.
5. `Task/Artifact Integrity` shows that runtime work and produced artifacts
   remain linked.
6. `Critic Acceptance` records the reviewed target and explicit acceptance
   reason.

## Expected Output

```text
# Portfolio Runtime Demo

Readiness: ready
Question: 카카오뱅크 2023년 연결기준 CIR(판매비와관리비/경비차감전영업이익)을 계산해 줘.
Answer: 2023년 CIR은 37.47%입니다. 계산: 판매비와관리비 4,355억원 / 경비차감전영업이익 11,623억원.

Citations:
  - [카카오뱅크 | 2023 | IV. 이사의 경영진단 및 분석의견::table:3]

Semantic Plan:
  - planner: concept_llm_planner
  - operation: ratio
  - required_operands:
    - numerator: 판매비와관리비
    - denominator: 경비차감전영업이익

Retrieval Trace:
  - mode: hybrid
  - queries: 2
  - vector_results: 6
  - bm25_results: 6
  - candidates: 8
  - selected: 1
  - selected_source: IV. 이사의 경영진단 및 분석의견 [2023-mda-table-3]

Calculation Trace:
  - operation: ratio
  - result: 37.47% (ok)
  - operands:
    - 판매비와관리비: 4,355억원 from IV. 이사의 경영진단 및 분석의견::table:3
    - 경비차감전영업이익: 11,623억원 from IV. 이사의 경영진단 및 분석의견::table:3

Task/Artifact Integrity:
  - status: ok
  - tasks: 2
  - artifacts: 4
  - issue_count: 0

Critic Acceptance:
  - status: accepted
  - target_task_id: task_1
  - target_artifact_ids: artifact:calculation_result
  - reason: Source-visible operands, ratio trace, and target refs are present.
```

## What It Demonstrates

| Output section | Contract demonstrated |
| --- | --- |
| `Semantic Plan` | Semantic interpretation is explicit before execution |
| `Retrieval Trace` | Dense and sparse search telemetry and selection are inspectable |
| `Calculation Trace` | Arithmetic is backed by bound operands, formula, and result |
| `Citations` | Source anchors remain visible to callers |
| `Task/Artifact Integrity` | Agent runtime tasks and artifacts have valid references |
| `Critic Acceptance` | Acceptance uses target refs and an explicit reason |

The important point is not the fixture value itself. The command presents the
four core engineering stages—semantic planning, retrieval, deterministic
calculation, and provenance—as one coherent trace.

## Optional Systems Appendix

Cache promotion, reflection promotion, `REFERENCE_NOTE`, and the MAS facade are
supporting experiments, not prerequisites for the core demo. Review their
aggregate gates separately:

```bash
uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates
```

To append the candidate-only cache handoff to the demo output explicitly:

```bash
uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_demo --include-cache-review
```

The optional cache surface keeps retrieval bypass, writes, serving, and ledger
insertion disabled.

## Source Files

| File | Role |
| --- | --- |
| `src/ops/portfolio_demo.py` | CLI and compact readiness projection |
| `tests/fixtures/portfolio_demo/demo_payload.json` | Source-controlled runtime projection |
| `tests/test_portfolio_demo.py` | Contract and output regression tests |
| `src/ops/portfolio_review_gates.py` | Separate optional-system gate bundle |
