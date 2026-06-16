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

### PR 5: Parser Extraction

Keep `FinancialParser.process_document()` as the public facade. Move XML loading,
section extraction, table reconstruction, value record construction, chunking,
and reference resolution behind that facade.

Add or preserve metadata snapshot tests because table/value-record drift can
change retrieval behavior.

### PR 6: Vector Store Extraction

Keep `VectorStoreManager.search()` public behavior stable. Move embedding
provider selection, Chroma access, BM25, hybrid merge, structure graph expansion,
and metadata sidecars behind smaller internal modules.

Search telemetry keys should remain stable.

### PR 7: MAS Isolation

Move MAS code under `experimental/mas` and keep compatibility shims only where
needed. Documentation should describe MAS as an experimental wrapper around the
core financial runtime, not as the default product engine.

### PR 8: Requirements And Docs Cleanup

Split dependencies or introduce extras so core, API, ingest, eval, dev, and UI
dependencies are not all presented as one default install surface.

Simplify reviewer-facing docs and move stale benchmark or retrospective material
to appendix/internal locations.

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
