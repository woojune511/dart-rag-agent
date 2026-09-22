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
| `src/agent/financial_graph.py` | `FinancialAgent`, explicit phase inputs/provider controls, final assembly then ledger; run applies caller projection without recomputing answers |
| `src/agent/financial_graph_state.py` | concrete phase input/output TypedDicts and `FinancialAgentStateV2` |
| `src/agent/financial_runtime_contracts.py` | immutable visibility and V2 full execution-content fingerprint |
| `src/agent/financial_run_result.py` | versioned `FinancialRunResultV1` |
| `src/agent/financial_run_observation.py`, `src/utils/request_diagnostics.py` | opt-in request-owned copied phase/attempt/SDK observations and exception-safe caller delivery; no state writer, answer or execution authority |

## Shared numeric and narrative path

| Path | Responsibility |
| --- | --- |
| `src/agent/financial_graph_planning.py` | required-output planning for every intent; original request references/themes, complete named subjects and conditions; same-call scoped section selection and observed-axis reading before target fixation; measurement periods stay separate from filing-year defaults |
| `src/agent/financial_source_axis_inventory.py` | bounded query-literal whole axes from report-scoped hydrated table records, deterministic observed examples/spans and omission trace; planning context only, not subject/alias or candidate authority |
| `src/agent/financial_request_units.py` | exact query partition/addresses, output ownership and contiguous fully owned request ranges; active-owner text projection, not semantic classification or evidence |
| `src/agent/financial_retrieval_pipeline.py` | one source scope across searches/supplements/seeds/selection; section eligibility before bounded search; numeric supplement priority requires a complete value cell on the same line; narrative ownership, filing-qualified dedupe, trace |
| `src/agent/financial_reconciliation_candidates.py` | filing-qualified identity, source/catalog construction and fiscal periods; scalar-independent readings, balanced parser-prefix separation, exact bounded body windows and separate local-heading hints |
| `src/agent/financial_scope_policies.py` | shared report/consolidation scope; located annual period resolution separate from filing year/unbound parser hints |
| `src/agent/financial_measurement_periods.py` | typed request periods/coverage and owned references; independent source-axis dates plus exact own-column attached declarations, bounded annual geometry and operand provenance; no request inference, assumed fiscal dates or axis joining |
| `src/agent/financial_planner_period_wire.py` | one seven-field Planner period declaration; validates active/inactive fields and lowers explicit precision/year-offset/coverage/dates to existing internal types without query interpretation or semantic repair |
| `src/agent/financial_source_scope.py` | bounded filing-qualified section inventory and separately bounded attached table-title hints for existing parent IDs; code-copied whole request ranges, strict historical excerpts, descendant membership and parent/input intersection; no title promotion, quote repair or body/context authority |
| `src/agent/financial_source_bundles.py` | deterministic prose-sentence/physical-row bundles with shared located context references and exact row cell partitions |
| `src/agent/financial_candidate_matching.py` | factorized exposure ranking and diagnostics; numeric declared basis stays separate from inferred subjects and supplies an attached-context tie-break after metric; hints are relevance, not source-use prohibitions |
| `src/agent/financial_graph_calculation.py` | bundle exposure then hard-condition owner authority over the visible union; request-grounded islands, typed dispatch/targeted retry and verified dependencies; unresolved semantic answers cite accepted evidence rather than retrieval-only material |
| `src/agent/financial_compiler_wire.py`, `financial_graph_models.py` | nested CompilerResponseV2; owner-authorized source/request choices, exact value-span and whole-request copying; arity-typed operation steps with inline request proofs; separate prose interpretation evidence, cell axes/attached context; shared relationship declarations and member references; explicit lowering |
| `src/agent/financial_formula_wire.py` | bounded backward-only operation steps to existing AST formulas and position-named scalar proofs; final-step reachability, safe expansion and collision-free names, no quantity inference or choice repair |
| `src/agent/financial_source_interpretation.py` | owned request to full cell-axis/attached-context or exact located prose-bundle correspondence; finite count-unit and same-column annual readings; binding-local source coordinates preserve fields without certifying meaning |
| `src/agent/financial_column_periods.py` | structured same-document/table/column annual-axis evidence, finite selectable readings and operand projection; original candidate fields preserved, no parser/store mutation or automatic measurement-year assignment |
| `src/agent/financial_output_relationships.py` | explicit output sets with shared owned request excerpts; declaration/reference ownership validation and accepted-proof projection; distinct from dependencies and physical-row constraints |
| `src/agent/financial_compiler_presentation.py` | canonical source layout and filing metadata; numeric wire v9, addressed-piece rows in v10, candidate-local exact axis provenance in v11; owner permission and responsibility allowlists, no ranking-state instructions |
| `src/agent/financial_evidence_addresses.py` | lossless, content/provenance/partition-bound source pieces and exact range resolution; only visible candidate bodies/own contexts, no semantic segmentation or selection |
| `src/agent/financial_compiler_debug.py` | opt-in immutable JSON snapshots of attempted/merged programs, validation locations and exact retry feedback; observational only, exported separately from accepted answers/scoring |
| `src/agent/financial_program_projection.py` | explicit local subject references and one claim renderer; parent text/evidence/ID projection and description-only separation, no implicit inheritance or historical ID widening |
| `src/agent/financial_narrative_claims.py` | separate exact subject/fact ranges, fact-local numbers and raw/rendered trace; unique whitespace-only subject witness with original span/provenance, shared with owner/requirement-filtered retry diagnostics; no source/model rewrite, range repair or semantic entailment |
| `src/utils/openai_structured.py` | OpenAI strict wire with annotation-only local-ref expansion and preserved constraints; pure refs and original-model validation retained, ambiguous/invalid/cyclic expansion rejected; caller-thread usage, no response repair |
| `src/config/retrieval_policy.py` | declarative retrieval priors, compact kind-specific planner/compiler and retry instructions; not source or attribution authority |
| `src/agent/financial_calculation_execution.py` | hard source conditions, units/AST/provenance and immutable execution; final renderer describes error-free missing outputs using explicit selected-report/request-period facts, never rationale or inferred source absence; owned comparison links and free interpretation proofs remain separate from source facts |
| `src/agent/financial_formula_constants.py` | internal named dimensionless request inputs, code-computed source/dependency binding count and exact owned request proofs; offline legacy scalar validation; no numeral rules, inferred inputs, formula rewriting or semantic certification |
| `src/agent/financial_runtime_normalization.py` | shared UnitSpec, declared table/header-unit projection with provenance, numeric normalization and display precision |
| `src/agent/financial_numeric_surface.py` | shared numeric surfaces plus catalog-only standalone scalar exposure; legacy identity order and evaluation extraction preserved |
| `src/agent/financial_graph_evidence.py` | optional structural expansion and source anchors; the separate narrative extraction/compression/validation path is removed |
| `src/agent/financial_agent_run_projection.py` | answer/review/debug projections; caller trace copies omit whole Compiler/validation records after ledger assembly, preserving canonical records and evidence |
| `src/agent/financial_task_artifacts.py` | artifact/ledger projection; aggregate status follows finalized public result |

## Ingest and storage

| Path | Responsibility |
| --- | --- |
| `src/ingestion/dart_fetcher.py` | DART report fetch |
| `src/processing/financial_parser.py` | literal-preserving XML recovery, data-table/unit-context structure, and located heading parts without changing heading recognition |
| `src/processing/block_collection.py`, `chunking.py` | full located heading scope, caption/enclosing-scope separation and heading-bounded paragraph/table context; compact hints cannot merge foreign scopes |
| `src/processing/source_context.py` | bounded exact heading/table fragments, physical cell partitions, XML spans, hierarchy/adjacency links and file identity; no entity inference |
| `src/utils/source_segments.py` | source-local partition clipping, independent prompt quote surfaces and contiguous-quote checks shared by narrative/scope validation |
| `src/processing/table_structure.py`, `table_records.py` | explicit THEAD/TH header scope before grid inference; v2 parser row/cell projection |
| `src/ingestion/context_generator.py` | contextual text generation, completed provider text projection, fallback/usage counts and indexing payloads |
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
| `src/ops/application_diagnostics.py` | explicit caller persistence of opt-in run snapshots on return or exception; exclusive files, safe persistence-error reporting, no runtime-default import or provider dispatch |
| `src/ops/compilation_plan_admission.py` | opt-in experimental preflight of actual runtime groups before Compiler calls; full remaining count/generation/funding bounds and one first request per complete group; no plan rewriting, default installation or paid authority |
| `src/ops/provider_admission.py` | opt-in budget/first-cause ownership; explicit server-count call limits and separate allowances, measured input vs fixed output reservation; legacy policies unchanged, no HTTP credentials in receipts |
| `src/ops/google_server_token_count.py` | final SDK body copied into count + generation, canonical hash-linked receipts; text-only Developer API, single HTTP attempts, no fallback/redirect/async or runtime-default installation |
| `src/ops/openai_server_token_count.py` | opt-in counted stateless text Responses; frozen final SDK input/schema, independent count/generation limits and shared budget, cached wrappers, no default installation or fallback |
| `src/ops/openai_error_diagnostics.py` | opt-in local failure metadata: unchanged v1 plus v2 exact reviewed request code/type/parameter names, restricted request IDs and normalized Retry-After; no raw error text, dynamic paths, public projection, I/O or retry |
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

- All questions enter the Planner directly. MAS, query classification, report-result cache and reflection-promotion features were [removed](../architecture/portfolio_feature_retirement.md); historical evidence remains outside the runtime.
- `app.py`: experimental Streamlit client.
- `tests/`: unit and contract gates. Semantic program coverage is split by
  catalog, cohort, compiler, validator, executor, and integration boundary.

These surfaces do not define the default product result or store contract.
