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
| `src/config/llm_profiles.py` | reviewed opt-in application LLM routes; shared API/Streamlit profile selection, no benchmark inputs or credentials |
| `src/api/financial_router.py` | HTTP schema, readiness gate, threadpool dispatch |
| `src/agent/financial_graph.py` | `FinancialAgent`, explicit phase inputs/provider controls, final assembly then ledger; run packages only |
| `src/agent/financial_graph_state.py` | concrete phase input/output TypedDicts and `FinancialAgentStateV2` |
| `src/agent/financial_runtime_contracts.py` | immutable visibility and V2 full execution-content fingerprint |
| `src/agent/financial_run_result.py` | versioned `FinancialRunResultV1` |
| `src/agent/financial_run_observation.py`, `src/utils/request_diagnostics.py` | opt-in request-owned copied phase/attempt/SDK observations and exception-safe caller delivery; no state writer, answer or execution authority |

## Shared numeric and narrative path

| Path | Responsibility |
| --- | --- |
| `src/agent/financial_graph_planning.py` | required-output planning for every intent; original request references/themes, complete named subjects and conditions; same-call scoped section selection and observed-axis reading before target fixation |
| `src/agent/financial_source_axis_inventory.py` | bounded query-literal whole axes from report-scoped hydrated table records, deterministic observed examples/spans and omission trace; planning context only, not subject/alias or candidate authority |
| `src/agent/financial_request_units.py` | exact query partition/addresses and output ownership checks; active-owner text projection, not semantic classification or evidence |
| `src/agent/financial_retrieval_pipeline.py` | one source scope across searches/supplements/seeds/selection; section eligibility before bounded search, narrative ownership, filing-qualified dedupe, trace |
| `src/agent/financial_reconciliation_candidates.py` | filing-qualified identity, source/catalog construction and fiscal periods; scalar-independent readings, balanced parser-prefix separation, exact bounded body windows and separate local-heading hints |
| `src/agent/financial_scope_policies.py` | shared report/consolidation scope; located annual period resolution separate from filing year/unbound parser hints |
| `src/agent/financial_source_scope.py` | bounded filing-qualified section inventory, exact request-to-location projection and descendant membership; literal-title compatibility, parent/input intersection and shared retrieval union; no body/heading-context authority |
| `src/agent/financial_source_bundles.py` | deterministic prose-sentence/physical-row bundles with shared located context references and exact row cell partitions |
| `src/agent/financial_candidate_matching.py` | factorized exposure ranking and diagnostics; free subject/metric differences are relevance, not source-use prohibitions |
| `src/agent/financial_graph_calculation.py` | bundle exposure then hard-condition owner authority over the visible union; request-grounded islands, typed dispatch/targeted retry, verified dependency inputs and terminal admission propagation |
| `src/agent/financial_compiler_wire.py`, `financial_graph_models.py` | nested CompilerResponseV2; owner-authorized source/request choices, exact value-span and whole-request copying; arity-typed operation steps with inline request proofs; separate prose interpretation evidence, cell axes/attached context; explicit lowering |
| `src/agent/financial_formula_wire.py` | bounded backward-only operation steps to existing AST formulas and position-named scalar proofs; final-step reachability, safe expansion and collision-free names, no quantity inference or choice repair |
| `src/agent/financial_source_interpretation.py` | owned request to full cell-axis/attached-context correspondence; exact physical linkage, explicitly not semantic-equivalence proof |
| `src/agent/financial_output_relationships.py` | explicit output sets with shared owned request excerpts; distinct from dependencies and physical-row constraints |
| `src/agent/financial_compiler_presentation.py` | canonical addressed source layout and filing metadata projected to wire v9; owner permission and responsibility allowlists, no ranking-state instructions |
| `src/agent/financial_evidence_addresses.py` | lossless, content/provenance/partition-bound source pieces and exact range resolution; only visible candidate bodies/own contexts, no semantic segmentation or selection |
| `src/agent/financial_compiler_debug.py` | opt-in immutable JSON snapshots of attempted/merged programs, validation locations and exact retry feedback; observational only, exported separately from accepted answers/scoring |
| `src/agent/financial_program_projection.py` | explicit local subject references and one claim renderer; parent text/evidence/ID projection and description-only separation, no implicit inheritance or historical ID widening |
| `src/agent/financial_narrative_claims.py` | separate exact subject/fact ranges, fact-local numbers and raw/rendered trace; unique whitespace-only subject witness with original span/provenance, shared with owner/requirement-filtered retry diagnostics; no source/model rewrite, range repair or semantic entailment |
| `src/utils/openai_structured.py` | opt-in OpenAI strict wire and original-model validation; explicit fields, caller-thread usage, no response repair |
| `src/config/retrieval_policy.py` | declarative retrieval priors, compact kind-specific planner/compiler and retry instructions; not source or attribution authority |
| `src/agent/financial_calculation_execution.py` | hard source conditions, units/AST/provenance and immutable execution; owned comparison request to reference/target trace, not direction certification; free scope stays on proofs, not source facts/equality gates |
| `src/agent/financial_formula_constants.py` | internal named dimensionless request inputs, code-computed source/dependency binding count and exact owned request proofs; offline legacy scalar validation; no numeral rules, inferred inputs, formula rewriting or semantic certification |
| `src/agent/financial_runtime_normalization.py` | shared UnitSpec, declared table/header-unit projection with provenance, numeric normalization and display precision |
| `src/agent/financial_numeric_surface.py` | shared numeric surfaces plus catalog-only standalone scalar exposure; legacy identity order and evaluation extraction preserved |
| `src/agent/financial_graph_evidence.py` | structural expansion/evidence helpers; retained legacy narrative helpers are no longer selected by the public planner |
| `src/agent/financial_agent_run_projection.py` | answer/review/debug projection functions |
| `src/agent/financial_task_artifacts.py` | artifact/ledger projection; aggregate status follows finalized public result |
| `src/routing/query_router.py`, `src/config/query_routing_prompt.py` | validated canonical success cache, scale-stable similarity, anonymous declarative routing prompt |

## Ingest and storage

| Path | Responsibility |
| --- | --- |
| `src/ingestion/dart_fetcher.py` | DART report fetch |
| `src/processing/financial_parser.py` | literal-preserving XML recovery, data-table/unit-context structure, and located heading parts without changing heading recognition |
| `src/processing/block_collection.py`, `chunking.py` | full located heading scope, caption/enclosing-scope separation and heading-bounded paragraph/table context; compact hints cannot merge foreign scopes |
| `src/processing/source_context.py` | bounded exact heading/table fragments, physical cell partitions, XML spans, hierarchy/adjacency links and file identity; no entity inference |
| `src/utils/source_segments.py` | source-local partition clipping, independent prompt quote surfaces and contiguous-quote checks shared by narrative/scope validation |
| `src/processing/table_structure.py`, `table_records.py` | explicit THEAD/TH header scope before grid inference; v2 parser row/cell projection |
| `src/ingestion/context_generator.py` | contextual text generation and indexing payloads |
| `src/ingestion/ingest_service.py` | end-to-end ingest ownership |
| `src/storage/vector_store.py` | scoped dense/BM25 search, private cache copies/commit invalidation, source coverage and no-embedding sidecar repair |
| `src/storage/search_scope.py`, `bm25_index.py` | observed source-ID/document filters before dense/lexical top-K, matching union semantics, explicit empty-scope no-call; no agent/domain dependency |
| `src/storage/atomic_json.py` | atomic JSON replace used by graph, payload, and parent persistence |
| `src/storage/store_manifest.py` | versioned store identity and readiness |

## Support and experimental surfaces

| Path | Responsibility |
| --- | --- |
| `src/ops/evaluator.py` | evaluator-only numeric variants; canonical identity separate from answer labels; interrupted-run observations exported separately, never scoring input |
| `src/ops/benchmark_runner.py` | explicit benchmark, store-only, and store-fixed eval-only modes |
| `src/ops/provider_admission.py` | opt-in budget/first-cause ownership; explicit server-count call limits and separate allowances, measured input vs fixed output reservation; legacy policies unchanged, no HTTP credentials in receipts |
| `src/ops/google_server_token_count.py` | final SDK body copied into count + generation, canonical hash-linked receipts; text-only Developer API, single HTTP attempts, no fallback/redirect/async or runtime-default installation |
| `src/utils/provider_errors.py` | dependency-light terminal admission error and safe code-only projection; no core-to-ops import or error-message capture |
| `src/ops/adopt_store_manifest.py` | read-only legacy-store compatibility inspection and separately approved adoption |
| `src/ops/plan_parser_store_successor.py` | socket-blocked full-filing reparse inventory, exact table/unit/header drift and index-text reuse candidates; no vector/store publication |
| `src/ops/build_parser_store_successor.py` | explicit source-copy preparation, exact-input vector reuse, separately supplied missing vectors, snapshot readback and manifest-last publication; no provider clients |
| `src/ops/replay_runtime_contract_cases.py` | read-only saved-case/counterfactual runtime contract replay; no provider/release claim |
| `src/ops/replay_saved_runtime_traces.py` | generic exact saved-program replay through current catalog/visibility/validator/executor contracts |
| `src/ops/replay_reviewed_runtime_corpus.py` | provider-free fixture replay with V2 fingerprints; legacy flat narrative explicitly marks claim enforcement off, not current compiler/semantic acceptance |
| `src/ops/replay_reviewed_compiler_selection.py` | explicit Flash/Pro admissions; source-bound selection checks; terminal stops retain completed cases and interrupted raw responses without executing that case, continuing models or inventing usage; narrative semantic review stays separate; no retrieval/evaluator/embedding/store access |
| `src/ops/compiler_fixture_transport.py` | explicit offline authored-program transport; valid prior proofs map to addresses/inline formula operands, bad/missing/unused proofs remain invalid; no provider-response repair or core import |
| `src/utils/gemini_usage_counts.py` | dependency-light answer/thinking/cache normalization and cost accounting; no double-counted reasoning |
| `src/ops/` remainder | audit, replay, review-pack, and diagnostic entry points |

- `src/experimental/mas/`: optional MAS facade over the single-agent runtime.
- `app.py`: experimental Streamlit client.
- `tests/`: unit and contract gates. Semantic program coverage is split by
  catalog, cohort, compiler, validator, executor, and integration boundary.

These surfaces do not define the default product result or store contract.
