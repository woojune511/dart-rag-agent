# Codebase Map

이 문서는 현재 제품 경계의 최소 탐색 지도다. 세부 계약은
[agent_runtime_contract.md](../architecture/agent_runtime_contract.md), 실제 graph
순서는 [runtime_flow_roles.md](runtime_flow_roles.md), 과거 변경은
[implementation_history.md](../history/implementation_history.md)에서 확인한다.

## Product runtime

| Path | Responsibility |
| --- | --- |
| `main.py` | FastAPI lifespan과 환경 기반 CORS |
| `src/api/services.py` | `AppServices`, strict readiness, dependency assembly |
| `src/api/financial_router.py` | HTTP schema, readiness gate, threadpool dispatch |
| `src/agent/financial_graph.py` | `FinancialAgent`, explicit phase inputs/provider controls, final assembly then ledger; run packages only |
| `src/agent/financial_graph_state.py` | concrete phase input/output TypedDicts and `FinancialAgentStateV2` |
| `src/agent/financial_runtime_contracts.py` | immutable visibility and V2 full execution-content fingerprint |
| `src/agent/financial_run_result.py` | versioned `FinancialRunResultV1` |

## Semantic numeric path

| Path | Responsibility |
| --- | --- |
| `src/agent/financial_graph_planning.py` | routing/requirements and query-written bilingual subject spellings |
| `src/agent/financial_retrieval_pipeline.py` | retrieval plan, searches, selection, trace |
| `src/agent/financial_reconciliation_candidates.py` | filing-qualified table/row/cell identity with raw provenance, source/catalog construction, attached prose and exact row context |
| `src/agent/financial_scope_policies.py` | shared report/consolidation scope and policy-owned annual relative-period labels |
| `src/agent/financial_source_bundles.py` | deterministic prose-sentence and physical-row source bundles |
| `src/agent/financial_candidate_matching.py` | typed owner applicability and deterministic bundle rank inputs |
| `src/agent/financial_graph_calculation.py` | bundle-first cohorts, islands, targeted retry with read-only executed dependency inputs |
| `src/agent/financial_calculation_execution.py` | evidence/formula dimensions, semantic cross-source scope checks, display selection, validation/execution, pure final assembly |
| `src/agent/financial_runtime_normalization.py` | shared UnitSpec, numeric normalization and display precision |
| `src/agent/financial_graph_evidence.py` | narrative evidence and validation path |
| `src/agent/financial_agent_run_projection.py` | answer/review/debug projection functions |

## Ingest and storage

| Path | Responsibility |
| --- | --- |
| `src/ingestion/dart_fetcher.py` | DART report fetch |
| `src/processing/financial_parser.py` | document structure recovery and chunks |
| `src/ingestion/context_generator.py` | contextual text generation and indexing payloads |
| `src/ingestion/ingest_service.py` | end-to-end ingest ownership |
| `src/storage/vector_store.py` | dense/BM25 store, source coverage and no-embedding sidecar repair |
| `src/storage/atomic_json.py` | atomic JSON replace used by graph, payload, and parent persistence |
| `src/storage/store_manifest.py` | versioned store identity and readiness |

## Support and experimental surfaces

| Path | Responsibility |
| --- | --- |
| `src/ops/evaluator.py` | evaluator-only numeric and source-qualified variant contracts |
| `src/ops/benchmark_runner.py` | explicit benchmark, store-only, and store-fixed eval-only modes |
| `src/ops/adopt_store_manifest.py` | read-only legacy-store compatibility inspection and separately approved adoption |
| `src/ops/replay_runtime_contract_cases.py` | read-only saved-case/counterfactual runtime contract replay; no provider/release claim |
| `src/ops/replay_saved_runtime_traces.py` | generic exact saved-program replay through current catalog/visibility/validator/executor contracts |
| `src/ops/replay_reviewed_runtime_corpus.py` | provider-free replay of source-derived reviewed fixtures through normalization/visibility/validator/envelope/executor; no retrieval/compiler claim |
| `src/ops/replay_reviewed_compiler_selection.py` | explicit Flash/Pro single-model v2 gate and opt-in comparison v1; model-bound pricing, shared compiler/capture, frozen inputs and expectations; no retrieval/evaluator/embedding/store access |
| `src/utils/gemini_usage_counts.py` | dependency-light answer/thinking/cache normalization and cost accounting; no double-counted reasoning |
| `src/ops/` remainder | audit, replay, review-pack, and diagnostic entry points |

- `src/experimental/mas/`: optional MAS facade over the single-agent runtime.
- `app.py`: experimental Streamlit client.
- `tests/`: unit and contract gates. Semantic program coverage is split by
  catalog, cohort, compiler, validator, executor, and integration boundary.

These surfaces do not define the default product result or store contract.
