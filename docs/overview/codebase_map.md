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

## Shared numeric and narrative path

| Path | Responsibility |
| --- | --- |
| `src/agent/financial_graph_planning.py` | required-output planning for every intent; query-written subjects/themes and explicit source-section constraints, separately from retrieval hints |
| `src/agent/financial_retrieval_pipeline.py` | one source scope across searches/supplements/seeds/selection; narrative ownership, filing-qualified dedupe, trace |
| `src/agent/financial_reconciliation_candidates.py` | filing-qualified identity, source/catalog construction and fiscal periods; scalar-independent readings, balanced parser-prefix separation, exact bounded body windows and separate local-heading hints |
| `src/agent/financial_scope_policies.py` | shared report/consolidation scope; located annual period resolution separate from filing year/unbound parser hints |
| `src/agent/financial_source_scope.py` | query-copied section/path authority, whole-component descendant membership from located metadata/legacy anchors, parent/input intersection and shared retrieval union; no body/heading-context authority |
| `src/agent/financial_source_bundles.py` | deterministic prose-sentence/physical-row bundles with shared located context references |
| `src/agent/financial_candidate_matching.py` | typed applicability and row/column subject identity; numeric metric isolation, owner-aware narrative reading and document/section/source/row budget diversity; no cell-precision or filing-company narrative bonus |
| `src/agent/financial_graph_calculation.py` | bundle-first cohorts, compact lossless JSON, explicit active-output/bounded-evidence call scope, islands/targeted retry with read-only dependency inputs; merged explanation uses final validation, local rationale stays in island diagnostics; terminal admission errors propagate |
| `src/agent/financial_program_projection.py` | claim-to-text/evidence/ID projection, no second model-written paragraph; validated description-only separation, no historical ID widening |
| `src/agent/financial_narrative_claims.py` | exact claim-local quote/subject/number attachment to visible bundles or candidate-linked contexts and located trace; not semantic entailment |
| `src/agent/financial_calculation_execution.py` | dimensions/scope, numeric cell-subject and explicit source-section authority (including dependencies); exact row descriptions without scalar authority; provenance, validation/execution and pure final assembly |
| `src/agent/financial_runtime_normalization.py` | shared UnitSpec, declared table/header-unit projection with provenance, numeric normalization and display precision |
| `src/agent/financial_graph_evidence.py` | structural expansion/evidence helpers; retained legacy narrative helpers are no longer selected by the public planner |
| `src/agent/financial_agent_run_projection.py` | answer/review/debug projection functions |
| `src/agent/financial_task_artifacts.py` | artifact/ledger projection; aggregate status follows finalized public result |
| `src/routing/query_router.py`, `src/config/query_routing_prompt.py` | validated canonical success cache, scale-stable similarity, anonymous declarative routing prompt |

## Ingest and storage

| Path | Responsibility |
| --- | --- |
| `src/ingestion/dart_fetcher.py` | DART report fetch |
| `src/processing/financial_parser.py` | literal-preserving XML recovery, explicit data-table versus unit-context structure, and peer-heading classification |
| `src/processing/block_collection.py`, `chunking.py` | local-heading scope, caption/enclosing-scope separation and heading-bounded paragraph-to-table context |
| `src/processing/source_context.py` | bounded exact XML context fragments, hierarchy/adjacency links and source-file identity; no scope inference |
| `src/processing/table_structure.py`, `table_records.py` | explicit THEAD/TH header scope before grid inference; v2 parser row/cell projection |
| `src/ingestion/context_generator.py` | contextual text generation and indexing payloads |
| `src/ingestion/ingest_service.py` | end-to-end ingest ownership |
| `src/storage/vector_store.py` | scoped dense/BM25 search, private cache copies/commit invalidation, source coverage and no-embedding sidecar repair |
| `src/storage/atomic_json.py` | atomic JSON replace used by graph, payload, and parent persistence |
| `src/storage/store_manifest.py` | versioned store identity and readiness |

## Support and experimental surfaces

| Path | Responsibility |
| --- | --- |
| `src/ops/evaluator.py` | evaluator-only numeric variants; opt-in canonical row/period/document identity separate from answer labels |
| `src/ops/benchmark_runner.py` | explicit benchmark, store-only, and store-fixed eval-only modes |
| `src/ops/provider_admission.py` | opt-in SDK preflight/dispatch, shared reservations and first-cause preservation; safe failure status codes, frozen scripts unchanged |
| `src/utils/provider_errors.py` | dependency-light terminal admission error and safe code-only projection; no core-to-ops import or error-message capture |
| `src/ops/adopt_store_manifest.py` | read-only legacy-store compatibility inspection and separately approved adoption |
| `src/ops/plan_parser_store_successor.py` | socket-blocked full-filing reparse inventory, exact table/unit/header drift and index-text reuse candidates; no vector/store publication |
| `src/ops/build_parser_store_successor.py` | explicit source-copy preparation, exact-input vector reuse, separately supplied missing vectors, snapshot readback and manifest-last publication; no provider clients |
| `src/ops/replay_runtime_contract_cases.py` | read-only saved-case/counterfactual runtime contract replay; no provider/release claim |
| `src/ops/replay_saved_runtime_traces.py` | generic exact saved-program replay through current catalog/visibility/validator/executor contracts |
| `src/ops/replay_reviewed_runtime_corpus.py` | provider-free fixture replay with V2 fingerprints; legacy flat narrative explicitly marks claim enforcement off, not current compiler/semantic acceptance |
| `src/ops/replay_reviewed_compiler_selection.py` | explicit Flash/Pro admissions; source-bound selection checks; terminal stops retain completed cases and interrupted raw responses without executing that case, continuing models or inventing usage; narrative semantic review stays separate; no retrieval/evaluator/embedding/store access |
| `src/utils/gemini_usage_counts.py` | dependency-light answer/thinking/cache normalization and cost accounting; no double-counted reasoning |
| `src/ops/` remainder | audit, replay, review-pack, and diagnostic entry points |

- `src/experimental/mas/`: optional MAS facade over the single-agent runtime.
- `app.py`: experimental Streamlit client.
- `tests/`: unit and contract gates. Semantic program coverage is split by
  catalog, cohort, compiler, validator, executor, and integration boundary.

These surfaces do not define the default product result or store contract.
