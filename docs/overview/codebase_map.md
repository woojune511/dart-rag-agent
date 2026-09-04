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
| `src/agent/financial_graph.py` | `FinancialAgent`, phase graph, public result assembly |
| `src/agent/financial_graph_state.py` | `FinancialAgentStateV2` phase envelopes |
| `src/agent/financial_runtime_contracts.py` | immutable candidate visibility and compilation envelope |
| `src/agent/financial_run_result.py` | versioned `FinancialRunResultV1` |

## Semantic numeric path

| Path | Responsibility |
| --- | --- |
| `src/agent/financial_graph_planning.py` | routing and requirement planning |
| `src/agent/financial_retrieval_pipeline.py` | retrieval plan, searches, selection, trace |
| `src/agent/financial_reconciliation_candidates.py` | source candidate and catalog construction |
| `src/agent/financial_source_bundles.py` | deterministic prose-sentence and physical-row source bundles |
| `src/agent/financial_candidate_matching.py` | typed owner applicability and deterministic bundle rank inputs |
| `src/agent/financial_graph_calculation.py` | bundle-first cohorts, compiler payload, islands, targeted retry |
| `src/agent/financial_calculation_execution.py` | applicability, exact source-assertion validation, deterministic execution |
| `src/agent/financial_graph_evidence.py` | narrative evidence and validation path |
| `src/agent/financial_agent_run_projection.py` | answer/review/debug projection functions |

## Ingest and storage

| Path | Responsibility |
| --- | --- |
| `src/ingestion/dart_fetcher.py` | DART report fetch |
| `src/processing/financial_parser.py` | document structure recovery and chunks |
| `src/ingestion/context_generator.py` | contextual text generation and indexing payloads |
| `src/ingestion/ingest_service.py` | end-to-end ingest ownership |
| `src/storage/vector_store.py` | dense/BM25 store and search |
| `src/storage/store_manifest.py` | versioned store identity and readiness |

## Support and experimental surfaces

| Path | Responsibility |
| --- | --- |
| `src/ops/evaluator.py` | evaluator-only numeric and source-qualified variant contracts |
| `src/ops/benchmark_runner.py` | explicit benchmark, store-only, and store-fixed eval-only modes |
| `src/ops/adopt_store_manifest.py` | read-only legacy-store compatibility inspection and separately approved adoption |
| `src/ops/` remainder | audit, replay, review-pack, and diagnostic entry points |

- `src/experimental/mas/`: optional MAS facade over the single-agent runtime.
- `app.py`: experimental Streamlit client.
- `tests/`: unit and contract gates. Semantic program coverage is split by
  catalog, cohort, compiler, validator, executor, and integration boundary.

These surfaces do not define the default product result or store contract.
