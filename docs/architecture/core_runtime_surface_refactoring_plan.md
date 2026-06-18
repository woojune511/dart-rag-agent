# Core Runtime Surface Refactoring Plan

This plan defines the preferred direction for reducing project complexity without
removing the core financial QA capabilities. The goal is not line-count
reduction by itself. The goal is to make the default product path small and
explicit, while moving review, debug, benchmark, and experimental surfaces behind
clear boundaries.

This document complements `docs/architecture/agent_runtime_contract.md`. If a
runtime behavior question conflicts with the runtime contract, the contract wins.
If a structural refactor changes the contract, update both documents.

## Primary Direction

The default runtime should make one user question resolve to one grounded answer:

```text
main.py -> financial_router.py -> FinancialAgent
  -> parser/vector/router/graph -> answer
```

The core runtime should stay focused on:

- DART section and table structure preservation
- `section_path`, `table_context`, `period_focus`, `unit_hint`,
  `statement_type`, and `consolidation_scope`
- value-cell-first table metadata
- operand binding trace
- deterministic calculation
- `structured_result`
- `resolved_calculation_trace`
- reviewer gate and task artifact trace

These are structural capabilities and should not be removed merely to make code
shorter.

The surfaces that should move away from the default product path are:

- benchmark and eval workflows
- MAS experiments and skeleton nodes
- broad internal debug fields in public API responses
- disabled-by-design cache or reviewer handoff paths
- portfolio and retrospective ops scripts
- legacy compatibility mirrors that can conflict with canonical traces

## Target Layout

The long-term target is a clearer split between core product runtime, ingest,
experiments, evaluation, and ops:

```text
src/
  app/
    api/
      financial_router.py
    main.py

  core/
    runtime/
      agent.py
      graph.py
      state.py
      output.py

    retrieval/
      query_planning.py
      retriever.py
      evidence.py
      structure_expansion.py

    calculation/
      operands.py
      binding.py
      formula_planner.py
      executor.py
      renderer.py
      verifier.py
      reflection.py

    contracts/
      answer_slots.py
      traces.py
      artifacts.py
      evidence_schema.py

  ingest/
    parser/
      financial_parser.py
      sections.py
      tables.py
      chunking.py
      value_records.py
    storage/
      vector_store.py
      embeddings.py
      bm25.py
      structure_graph.py

  experimental/
    mas/

  eval/
    evaluator.py
    benchmark_runner.py
    gates/

  ops/
```

Do not make this move as a big-bang change. Preserve public facades first, then
move implementation behind them.

## Refactoring Principles

1. Hide execution surfaces before deleting features.
2. Keep `FinancialAgent` as the product runtime facade until a replacement has
   the same tests and review gates.
3. Keep benchmark, eval, and MAS compatibility adapters outside the core answer
   path.
4. Preserve canonical trace schemas before removing legacy fields.
5. Prefer no-behavior-change extraction before behavioral repair.
6. Do not introduce benchmark-specific or company-specific runtime branches.
7. Keep deterministic calculation and provenance validation in code; keep domain
   vocabulary in ontology, policy, config, or documented data artifacts.

## Recommended PR Sequence

### PR 1: Output Boundary Cleanup

Add typed projections without changing existing behavior:

- `AgentAnswer`: public answer fields
- `ReviewTrace`: evidence, retrieval, numeric, and task artifact review fields
- `DebugBundle`: usage, retry, and raw debug fields

`FinancialAgent.run()` may continue returning the existing dict shape through a
compatibility adapter, but new code should consume explicit projections.

### PR 2: Public Response Slimming

Keep the API default response focused on answer, citations, query metadata,
`structured_result`, and `resolved_calculation_trace`.

Expose review/debug bundles only through explicit reviewer, ops, or debug flags.
Keep evaluator compatibility in an adapter, not in the default API model.

### PR 3: State Type Split

Split `FinancialAgentState` into concern-specific TypedDicts while preserving the
current graph node contract:

- `RoutingState`
- `RetrievalState`
- `EvidenceState`
- `CalculationState`
- `ReflectionState`
- `LedgerState`

Then compose `FinancialAgentState` from those pieces. This reduces conceptual
surface without changing runtime behavior.

### PR 4: Calculation Extraction

Refactor `financial_graph_calculation.py` so the mixin becomes orchestration
only. Extract stable responsibilities in this order:

1. pure helper functions
2. normalization
3. operand binding
4. deterministic execution
5. answer slot construction and rendering
6. verification
7. reflection and repair

Responsibilities should remain clear:

- binding decides which numbers are used
- executor calculates only
- renderer formats answer text from slots and trace
- verifier checks trace and answer consistency
- reflection decides the next action after failure

#### PR 4 Current Status And Stop Line

Status as of 2026-06-17: the high-risk calculation extraction work is
functionally complete enough to pause. The file is still large, but the most
important runtime boundaries now have focused modules and regression coverage:

- answer slot construction:
  `src/agent/financial_answer_slots.py`
- calculation execution/result payload helpers:
  `src/agent/financial_calculation_execution.py`
- calculation rendering helpers:
  `src/agent/financial_graph_calculation_rendering.py`
- text/narrative surface helpers:
  `src/agent/financial_text_surface.py`
- reflection/task-artifact projection helpers:
  `src/agent/financial_reflection_projection.py`

The extracted surfaces now cover:

- failure `calculation_result` payloads
- scalar current/prior/delta state assembly
- scalar and time-series result payload construction
- scalar and time-series result `series` rows
- scalar and time-series rendered result display
- time-series pairwise YoY growth calculations
- successful scalar and time-series task/artifact publication
- answer-slot row construction and aggregate slot assembly
- reflection action/report and task-artifact integrity feedback

Verification baseline after the extraction sequence:

- `tests.test_operation_contracts`: `226` OK
- `tests.test_subtask_loop`: `210` OK
- `tests.test_financial_calculation_execution` +
  `tests.test_financial_calculation_rendering`: `22` OK
- `python -m src.ops.audit_runtime_domain_terms`: passed with `216` reviewed
  literals

Stop line: do not continue splitting `financial_graph_calculation.py` merely to
reduce file size. Continue PR 4 only when a concrete bug or contract gap points
to one of these specific seams:

- metric-name derivation for time-series results
- remaining calculation normalization/repair helpers that can be moved without
  adding domain vocabulary to runtime code
- verification/reflection callbacks that need a clearer typed boundary
- removal of compatibility aliases after callers no longer depend on them

Do not start new PR 4 work for broad aesthetic cleanup, unrelated rename churn,
or benchmark-specific score tuning. The next implementation focus should move
to PR 8 requirements/docs cleanup or PR 5 parser extraction unless a
calculation regression appears.

#### PR 4 Simplification Addendum

Status as of 2026-06-17: PR 4 was briefly reopened for deletion-oriented
simplification, not helper extraction.

- Removed runtime-dead `_preferred_complete_nested_numeric_narrative_answer`
  and its dedicated `_preserve_evidence_numeric_display` helper.
- Removed private-helper-only tests for that unused branch while preserving
  source-stated growth conflict coverage.
- Removed `_apply_mutable_numeric_answer` so its two call sites use the
  canonical `_apply_numeric_answer_to_aggregate_state` path directly.
- Removed runtime-dead `_narrative_summary_gap_is_satisfied` and its
  private-helper-only test.
- Removed the deleted helper's regex literal from the reviewed runtime
  domain-term audit baseline.
- Removed 7 thin wrapper shims that only forwarded to
  `calculation_rendering` / `financial_answer_slots` and had no remaining
  agent runtime callers.
- Removed `_replace_aggregate_final_answer` and `_replace_aggregate_results`
  as middle wrappers used only by mutable aggregate state helpers.
- Removed the unused `_render_grounded_operand_display` agent shim; the
  module-level rendering helper remains the active implementation.
- Result:
  - `src/agent/financial_graph_calculation.py`: `18,623` -> `18,296` lines.
  - Latest runtime-only diff: `3` deletions.
- Verification:
  - `python -m src.ops.audit_runtime_domain_terms`: passed
    (`215` reviewed literals).
  - `.venv/bin/python -m unittest tests.test_aggregate_subtask_projection tests.test_operation_contracts tests.test_subtask_loop tests.test_financial_calculation_execution tests.test_financial_calculation_rendering`:
    `507` OK.
  - `.venv/bin/python -m unittest tests.test_financial_answer_slots tests.test_financial_calculation_rendering tests.test_operation_contracts tests.test_subtask_loop tests.test_financial_calculation_execution`:
    `464` OK.
  - `.venv/bin/python -m unittest tests.test_runtime_domain_term_audit tests.test_subtask_loop tests.test_aggregate_subtask_projection tests.test_operation_contracts tests.test_financial_calculation_execution tests.test_financial_calculation_rendering`:
    `513` OK.
  - `.venv/bin/python -m unittest discover -s tests`: `1223` OK.
  - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
    `Status: ready`.
  - `git diff --check`: passed.

Further PR 4 work should use the same deletion-oriented rule: remove a dead or
duplicated patch path only when runtime callers, private-helper-only tests, and
review gates confirm the behavior is covered elsewhere. Do not count moving
code to another file as simplification.

#### PR 4 Post-Stop-Line Cleanup Addendum

Status as of 2026-06-18: a follow-up cleanup pass was completed after the
stop line, but only for duplicated runtime contracts and large nested patch
layers. It did not add domain terms or benchmark-specific runtime branches.

- Lookup recovery helpers moved into `src/agent/financial_lookup_recovery.py`.
- `_project_task_artifact_trace()` no longer owns artifact payload-contract
  validators as local nested helpers.
- `_refine_operand_precision_from_evidence_table()` now delegates contextual
  note-row and flattened-table-surface cell recovery to named helpers.
- `_extract_calculation_operands()` now publishes operand-set artifacts through
  `_operand_set_artifact_update()` instead of repeating task/artifact ledger
  publication in three branches.

Measured cleanup:

- `_project_task_artifact_trace()`: `501` -> `279` lines, nested helpers
  `5` -> `0`.
- `_refine_operand_precision_from_evidence_table()`: `567` -> `258` lines,
  nested helpers `2` -> `0`.
- `_extract_calculation_operands()`: `1196` -> `1139` lines.

Validation:

- targeted operand/ledger/subtask suites: `479` OK
- full unittest discovery: `1248` OK
- runtime domain-term audit: passed with `215` reviewed literals
- latest pushed commit for this cleanup sequence: `9de3c16`

Continue from here only for similarly concrete duplication or contract seams,
especially `_extract_calculation_operands()` fallback assembly. Do not reopen
PR 4 for broad file-size reduction or cosmetic helper moves.

### PR 5: Parser Extraction

Keep `FinancialParser.process_document()` as the public facade. Move XML loading,
section extraction, table reconstruction, value record construction, chunking,
and reference resolution behind that facade.

Add or preserve metadata snapshot tests because table/value-record drift can
change retrieval behavior.

#### PR 5 Current Status

Status as of 2026-06-17: PR 5 is functionally complete enough to pause. The
main parser facade remains `FinancialParser.process_document()`, while the
largest parser responsibilities now sit behind focused modules.

- Added `src/processing/table_records.py` for parser-normalized table row/value
  record construction.
- `FinancialParser._build_table_row_records()` and
  `FinancialParser._build_table_value_records()` remain as compatibility
  wrappers behind the `FinancialParser.process_document()` facade.
- Generic table-axis, period-label, aggregate-role, row-record, and value-record
  helpers now live in the parser table-record module instead of the main parser
  facade.
- Added `src/processing/table_structure.py` for XML table grid reconstruction,
  merged-cell propagation, table text formatting, span detection, row-label
  extraction, and table-object payload assembly.
- `FinancialParser._cell_span_int()`, `_normalize_table_grid()`,
  `_format_table_grid()`, `_table_has_spans()`,
  `_extract_table_row_labels_from_grid()`, `_build_table_object()`, and
  `_grid_row_to_text()` remain compatibility wrappers.
- Added `src/processing/section_extraction.py` for section tag iteration,
  section path construction, parse budget/fallback orchestration, parse timing,
  and section payload assembly.
- `FinancialParser._build_section_path()` and `_extract_sections()` remain
  compatibility wrappers.
- Added `src/processing/block_collection.py` for the paragraph/table/local
  heading block state machine. `FinancialParser._collect_blocks()` remains as a
  compatibility wrapper that wires parser-specific callbacks into the extracted
  collector.
- Added `src/processing/chunking.py` for table row/window splitting, narrative
  table-row splitting, wide-table column windows, table metadata propagation,
  and section block chunk assembly.
- `FinancialParser._split_table_by_rows()`, `_looks_like_table_header_row()`,
  `_split_table_text_fragment()`, `_split_long_table_row()`,
  `_split_wide_table_by_columns()`, `_split_table_for_chunks()`, and
  `_chunk_blocks()` remain compatibility wrappers.
- Added `src/processing/reference_resolution.py` for quoted intra-filing
  reference hint canonicalization, reference index construction, and section
  path resolution.
- `FinancialParser._canonicalize_reference_text()`,
  `_build_reference_index()`, `_resolve_reference_path()`, and
  `_extract_reference_section_paths()` remain compatibility wrappers.
- Verification:
  - `uv run --with-requirements requirements-review.txt python -m unittest tests.test_financial_parser`:
    `28` OK
  - `.venv/bin/python -m unittest tests.test_vector_store_fallback`:
    `14` OK
  - `python -m py_compile src/processing/financial_parser.py src/processing/table_records.py src/processing/table_structure.py src/processing/section_extraction.py src/processing/block_collection.py src/processing/chunking.py src/processing/reference_resolution.py`:
    passed
  - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
    `Status: ready`
  - `git diff --check`: passed

Stop line: do not continue splitting `financial_parser.py` merely to reduce
file size. Continue PR 5 only when a concrete parser regression or metadata
snapshot drift points to one of these specific seams:

- XML loading and parser input normalization
- parser configuration/value defaults that need a typed boundary
- remaining small helpers that can move without changing metadata schema
- removal of compatibility wrappers after callers no longer depend on them

The next implementation focus should move to PR 6 vector store extraction unless
a parser-specific bug appears.

### PR 6: Vector Store Extraction

Keep `VectorStoreManager.search()` public behavior stable. Move embedding
provider selection, Chroma access, BM25, hybrid merge, structure graph expansion,
and metadata sidecars behind smaller internal modules.

Search telemetry keys should remain stable.

#### PR 6 Current Status

Status as of 2026-06-17: PR 6 has started with a no-behavior-change extraction
behind the `VectorStoreManager` facade.

- Added `src/storage/embedding_config.py` for embedding provider selection,
  default model selection, known dimension lookup, runtime spec construction,
  and embedding factory creation.
- Preserved the existing `src.storage.vector_store` import surface for
  `DEFAULT_EMBEDDING_PROVIDER`, `DEFAULT_EMBEDDING_MODEL`,
  `create_embeddings`, `get_embedding_runtime_spec`,
  `infer_embedding_dimension`, and `_select_default_embedding_provider`.
- Added `src/storage/metadata_payloads.py` for Chroma metadata sanitization,
  table payload sidecar id/stats/load, metadata hydration, and compact node
  storage helpers.
- Preserved the existing metadata/payload helper surface in
  `src.storage.vector_store` through compatibility wrappers.
- Added `src/storage/bm25_index.py` for Korean/ASCII tokenization, metadata
  filter matching, BM25 index construction, and BM25 candidate collection.
- Preserved the existing BM25 helper surface in `src.storage.vector_store`
  through compatibility wrappers.
- Added `src/storage/structure_graph.py` for structure graph payload
  normalization, BM25 payload projection, vector result hydration,
  relationship rebuild/update, indexed chunk uid lookup, and graph accessor
  document creation.
- Preserved the existing structure graph helper/accessor surface in
  `src.storage.vector_store` through compatibility wrappers.
- `VectorStoreManager.search()` behavior and telemetry keys are unchanged.
- Verification:
  - `.venv/bin/python -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config`:
    `18` OK
  - `python -m py_compile src/storage/vector_store.py src/storage/embedding_config.py src/storage/metadata_payloads.py src/storage/bm25_index.py src/storage/structure_graph.py`:
    passed
  - `git diff --check`: passed

Stop line: do not continue splitting `vector_store.py` merely to reduce file
size. Continue PR 6 only when a concrete vector-store bug or telemetry contract
gap points to one of these specific seams:

- Chroma access/probe wrappers
- hybrid merge and result identity helpers
- `add_documents` preparation/batching helpers
- remaining persistence helpers that can move without changing store artifacts

Do not combine these extractions with retrieval behavior tuning.

### PR 7: MAS Isolation

Move MAS code under `experimental/mas` and keep compatibility shims only where
needed. Documentation should describe MAS as an experimental wrapper around the
core financial runtime, not as the default product engine.

#### PR 7 Current Status

Status as of 2026-06-17: PR 7 has started with a no-behavior-change import
boundary.

- Added `src/experimental/mas/` as the experimental namespace for MAS graph,
  typed state, and node factories.
- Existing `src.agent.mas_graph`, `src.agent.mas_types`, and
  `src.agent.nodes.*` implementation/import paths remain compatibility
  surfaces. Files have not moved yet.
- Added `tests/test_experimental_mas_namespace.py` to pin re-export
  compatibility and dummy MAS graph execution through the experimental
  namespace.
- Migrated public MAS imports in ops smoke/review scripts to
  `src.experimental.mas`.
- Kept `mas_direct_worker_probe.py` Researcher private diagnostic helper imports
  on the legacy implementation path to avoid widening the public facade
  prematurely.
- Migrated public MAS graph/type/node factory imports in focused MAS tests to
  `src.experimental.mas`.
- Legacy test imports remain only for compatibility assertions and
  implementation-private helper/constant tests.
- Added `src.experimental.mas.diagnostics` for MAS worker-probe Researcher
  diagnostic helpers, and moved `src/ops/mas_direct_worker_probe.py` off direct
  `src.agent.nodes.researcher_node` private-helper imports.
- Diagnostic helpers are not re-exported by top-level `src.experimental.mas`;
  callers must opt into the diagnostic module explicitly.
- Full caller import scan result:
  - New public/ops/test callers use `src.experimental.mas`.
  - `src.experimental.mas.*` modules intentionally bridge to the current
    `src.agent.*` implementation while files remain unmoved.
  - `tests/test_experimental_mas_namespace.py` keeps legacy imports only for
    compatibility identity assertions.
  - Focused node tests keep legacy imports only for implementation-private
    constants/helpers.
  - `src.agent.*` internal imports remain implementation dependencies.
- Compatibility shim strategy:
  - Keep `src.agent.multi_agent_graph` and `src.agent.nodes.__init__` as
    compatibility surfaces for earlier imports.
  - Keep `src.agent.mas_graph`, `src.agent.mas_types`, and
    `src.agent.nodes.*` as implementation files for now, not redirect shims.
  - Do not move implementation files unless a later PR demonstrates a concrete
    maintenance benefit and preserves compatibility tests.
- Verification:
  - `.venv/bin/python -m unittest tests.test_experimental_mas_namespace tests.test_multi_agent_graph tests.test_analyst_node tests.test_researcher_node tests.test_critic_node tests.test_orchestrator_node`:
    `36` OK
  - `.venv/bin/python -m unittest tests.test_experimental_mas_namespace tests.test_mas_e2e_smoke tests.test_mas_direct_worker_probe tests.test_mas_e2e_smoke_contract tests.test_mas_researcher_smoke_contract tests.test_portfolio_demo`:
    `31` OK
  - `python -m py_compile src/experimental/__init__.py src/experimental/mas/__init__.py src/experimental/mas/graph.py src/experimental/mas/nodes.py src/experimental/mas/types.py src/experimental/mas/diagnostics.py`:
    passed
  - `python -m py_compile src/ops/portfolio_demo.py src/ops/mas_analyst_smoke.py src/ops/mas_researcher_smoke.py src/ops/mas_e2e_smoke.py src/ops/mas_direct_worker_probe.py`:
    passed
  - `python -m py_compile tests/test_analyst_node.py tests/test_researcher_node.py tests/test_critic_node.py tests/test_orchestrator_node.py tests/test_multi_agent_graph.py`:
    passed
  - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
    ready
  - `python -m src.ops.audit_runtime_domain_terms`:
    passed
  - `git diff --check`: passed

Next PR 7 seam should remain no-behavior-change. Do not move implementation
files by default; either reassess whether the move is still useful, or switch to
PR 8 requirements/docs cleanup.

### PR 8: Requirements And Docs Cleanup

Split dependencies or introduce extras so core, API, ingest, eval, dev, and UI
dependencies are not all presented as one default install surface.

Simplify reviewer-facing docs and move stale benchmark or retrospective material
to appendix/internal locations.

#### PR 8 Current Status

Status as of 2026-06-17: PR 8 has a lightweight reviewer profile and a full
development profile.

- `requirements-review.txt` is the quick review profile for fixture-backed
  demo/gate commands.
- `requirements.txt` is documented as the full development / ingest /
  benchmark / app dependency lock.
- README representative checks are split into lightweight reviewer commands,
  capability-specific gates, and full development commands.
- `docs/README.md` documents the dependency profile boundary.
- `docs/overview/portfolio_one_pager.md` now links to README for reviewer
  commands instead of duplicating the command block.
- `docs/README.md` separates the core 5-document reviewer path from optional
  interview/resume deliverables.
- Verification:
  - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_demo --format json`:
    `ready`
  - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
    `Status: ready`
  - `requirements.txt` and `requirements-review.txt` parsed via
    `packaging.requirements.Requirement`
  - reviewer-facing doc local link check:
    passed
  - `git diff --check`: passed
- Next PR 8 seam should stay docs-only unless a command actually needs a new
  dependency profile. Run a link/claim duplication check across reviewer-facing
  docs, or close PR 8 with a stop-line before final portfolio review.

## Deletion Criteria

Before deleting or archiving a module, answer these questions:

1. Is it required by the default `FinancialAgent.run()` query path?
2. Is it required by `FinancialParser.process_document()`?
3. Is it required by `VectorStoreManager.search()`?
4. Is it required to create `structured_result` or
   `resolved_calculation_trace`?
5. Is it required by `portfolio_review_gates` or README quick review commands?
6. Is it current evidence for a reviewer-facing project claim?

If all answers are "no", it is a candidate for deletion or archive. If any
answer is "yes", move or isolate it before deleting.

## First Files To Touch

Prefer starting with:

- `src/agent/financial_graph.py`
- `src/agent/financial_graph_models.py`
- `src/agent/financial_graph_calculation.py`
- `src/processing/financial_parser.py`
- `src/storage/vector_store.py`
- `src/api/financial_router.py`

Prefer touching later:

- `benchmarks/results/**`
- `docs/history/**`
- `docs/evaluation/benchmarking.md`
- `src/ops/**`

Core boundaries should be established before ops and evaluation surfaces are
reshaped.
