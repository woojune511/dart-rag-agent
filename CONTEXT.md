# Current Handoff Context

Last updated: 2026-09-22

## Product boundary

The user authorized simple RAG as the default API/Streamlit path after discussing
its reduced guarantees. Starting source: `2a926a6e`; branch:
`codex/reviewed-compiler-selection-gate`.
Read [AGENTS.md](AGENTS.md), [runtime contract](docs/architecture/agent_runtime_contract.md),
[adoption decision](docs/architecture/simple_rag_adoption.md),
[code map](docs/overview/codebase_map.md), and [project status](docs/overview/project_status.md).

`SimpleRagAgent.run` performs one scoped hybrid search and at most one structured
answer call. Empty evidence abstains without generation. Explicit metadata scope,
source identity and response/citation shape are checked. No classifier, Planner,
Compiler, graph expansion, numeric execution, repair or retry runs by default.
The packet has a whole-source byte bound and visible omissions. API answers expose
workflow, abstention, cited source text and validation limits. Compiler result/trace
objects are empty; no task ledger is fabricated. Review/debug observations are opt-in.

Semantic support/output coverage are not checked; arithmetic is not executed.
Source-ID validity is not entailment or numeric correctness. `FinancialAgent` and
its source/calculation checks remain only for explicit comparison/replay under
[compiled_workflow_contract.md](docs/architecture/compiled_workflow_contract.md).
Shared model construction does not import that path into the application.
Ingest/parser/store/embedding identities and data are unchanged. `openai` keeps
answer/ingest-context routes; `openai_compiler` is comparison-only and rejected by
application startup. The old embedded evaluation dashboard is removed.

## Evidence and accounting

The [development comparison](docs/evaluation/portfolio_workflow_comparison_successor.md)
on `6bc4aae5` completed four familiar pairs using shared frozen evidence. It found
no clear current-workflow quality advantage at 3.47x estimated cost / 4.79x measured
time. These are historical measurements, not current-app or holdout performance.
Its one-batch authority is consumed. The [failed predecessor](docs/evaluation/portfolio_workflow_comparison_result.md)
and loss ceilings remain separate and immutable. The selected NAVER2023 filing has
1,090 chunks in a two-filing source graph; no broader coverage claim.

Shared conservative accounting: USD21.00190943/26.32, remaining5.31809057, pending0.
No provider calls, fresh ingest, store/settings mutation or new funding in this
transition. Protected hashes and local verification receipts live under
`benchmarks/results/simple_rag_default_2026-09-22/`; do not stage them.

## Next work and hard stops

1. Complete a separate final set and reproducible simple-RAG demo/report. Include retrieval misses, abstention and the reduced validation guarantees.
2. Do not restart a per-question repair queue or silently restore Compiler fallback. The default change is user-authorized, not evidence of general superiority.
3. No automatic paid batch/retry or consumed-manifest reuse. Freeze the actual final evaluation scope and cost boundary before any paid execution.
4. Preserve source stores, historical raw outputs and accounting. The inactive default `data/chroma_dart` manifest mismatch remains; this change does not adopt or rebuild it.

Current checks: [project status](docs/overview/project_status.md). Chronology:
[implementation history](docs/history/implementation_history.md),
[experiment history](docs/history/experiment_history.md), and Git.
