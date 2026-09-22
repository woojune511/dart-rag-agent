# Portfolio scope and completion

Decision: 2026-09-22. The user adopted simple RAG as the default after explicitly
reviewing what it preserves and which compiled guarantees it loses. DART remains
the domain. The product demonstrates structured document ingest, hybrid retrieval,
source visibility, reproducible evaluation and cost-conscious architecture.
Exhaustive financial coverage and autonomous agent planning are not product claims.

## Product

- Preserve original document/table structure and source identity in ingest.
- Search explicit caller scope and generate a source-cited answer in one call.
- Validate response shape, source identity and citation membership.
- Show insufficient evidence, context omissions and validation limits.
- Record retrieval, token usage and timings without treating them as correctness.

The app does not execute arithmetic or verify semantic support/request completeness.
Those limits are explicit in its response. [Application contract](../architecture/agent_runtime_contract.md).
`FinancialAgent` remains an explicitly invoked comparison/replay implementation;
its [compiled contract](../architecture/compiled_workflow_contract.md) is preserved.

## Completed decisions

The earlier topic-specific narrative path and [peripheral features](../architecture/portfolio_feature_retirement.md)
were removed. The [four-case development comparison](../evaluation/portfolio_workflow_comparison_successor.md)
found no clear Planner/Compiler answer-quality advantage at 3.47x estimated cost
and 4.79x measured time. These familiar cases do not prove general superiority.
[Simple-RAG adoption](../architecture/simple_rag_adoption.md) changes the application
by user direction; the transition adds no paid accuracy or latency evidence.

## Remaining milestone

1. Freeze a separate final question set covering lookup, calculation, explanation and missing evidence. Previously inspected/repaired questions remain development cases.
2. Evaluate the actual simple-RAG application with recorded source/retrieval/model settings and a bounded one-time run. Keep historical fixed-BM25 comparison measurements separate from end-to-end hybrid retrieval.
3. Report correctness, source support, abstention, retrieval misses, latency and cost separately. Numeric text is not a deterministic execution proof.
4. Publish a reproducible demo/report with successful answers, an abstention and observed limitations; close the milestone instead of tuning repeatedly on the final questions.

A separate final set, demo and report remain outstanding. The previous batch's
paid authority is consumed. No store rebuild, historical-result rewrite, automatic
Compiler fallback or new question-specific rule is required by this milestone.
