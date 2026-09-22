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
by user direction. The later [final application evaluation](../evaluation/simple_rag_final_result.md)
provides separate live hybrid-retrieval results on the smaller default path.

## Completed evaluation and demo milestone

1. [Frozen questions and criteria](../evaluation/simple_rag_final_preparation.md): 12 new source-authored questions, three per category, on two familiar filings. No independent gold or unseen-holdout claim.
2. [One actual-app run](../evaluation/simple_rag_final_result.md): 12/12 completed, 9/9 supported complete positive answers, 2/3 safe abstentions. F11 retains a wording caveat; F12's daily-average substitution fails.
3. The report separates retrieval, source support, correctness, abstention and runtime guarantees from observed cost/time: mean 4.02 s per question, estimated USD0.208 total. Numeric text is not a deterministic execution proof.
4. [Saved-response demo](simple_rag_demo.md): all answers and cited sources, with the failure visible first. The local ignored bundle enables inspection without API calls; raw artifacts are not published with Git.

This scoped milestone is complete. No runtime or prompt was tuned after the final
answers. The run's paid authority is consumed. Broader independent evaluation,
artifact publication or deployment would be separately scoped work; none is an
automatic continuation of this panel. Existing store and historical-result
identities remain intact, and Compiler remains comparison-only.
