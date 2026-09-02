# Semantic Calculation Runtime Cleanup Manifest

> **Status: completed predecessor manifest.** Paths and buckets below preserve
> the review snapshot from that transition, including test files that were
> subsequently split. They are not the current runtime topology.

This manifest replaces the pre-transition extraction manifest. It describes the
review boundaries for the canonical semantic calculation program introduced on
2026-08-27. Numeric and mixed questions now follow one path:

`requirements -> retrieval/evidence -> candidate catalog -> semantic program -> validate/execute -> render/verify`

The user's existing `src/api/financial_router.py` change and untracked
`tests/test_financial_router_http_contract.py` are explicitly outside this
change. Benchmark result directories, stores, caches, and one-off datasets are
also outside every bucket.

The owner modules below are intentionally import-light and can be reviewed
without loading Pydantic or LangChain:

```python
     modules = [
         "src.agent.financial_calculation_execution",
         "src.agent.financial_formula_eval",
         "src.agent.financial_graph_model_loaders",
         "src.agent.financial_operation_policies",
         "src.agent.financial_reconciliation_candidates",
         "src.agent.financial_retrieval_hints",
         "src.agent.financial_runtime_normalization",
         "src.agent.financial_runtime_trace",
         "src.agent.financial_scope_policies",
         "src.agent.financial_task_artifacts",
     ]
```

Owner-foundation staging command:

```bash
git add \
src/agent/financial_calculation_execution.py \
src/agent/financial_formula_eval.py \
src/agent/financial_graph_model_loaders.py \
src/agent/financial_operation_policies.py \
src/agent/financial_reconciliation_candidates.py \
src/agent/financial_retrieval_hints.py \
src/agent/financial_runtime_normalization.py \
src/agent/financial_runtime_trace.py \
src/agent/financial_scope_policies.py \
src/agent/financial_task_artifacts.py
```

Owner-foundation staged review command:

```bash
git diff --cached -- \
src/agent/financial_calculation_execution.py \
src/agent/financial_formula_eval.py \
src/agent/financial_graph_model_loaders.py \
src/agent/financial_operation_policies.py \
src/agent/financial_reconciliation_candidates.py \
src/agent/financial_retrieval_hints.py \
src/agent/financial_runtime_normalization.py \
src/agent/financial_runtime_trace.py \
src/agent/financial_scope_policies.py \
src/agent/financial_task_artifacts.py
```

Then land caller rewrites/removals only after the semantic contract and graph
gates pass. The commands below are review aids; this worktree is not staged by
this document.

## Dependency Closure Addendum

The clean-worktree checkpoint at `9a5a2e6` showed that the owner-foundation
bucket was not dependency-closed. Included runtime owners import four changed
support owners, and the included semantic-program test reads two untracked
fixtures directly. These paths are part of the semantic transition checkpoint,
not of the later candidate-boundary repair:

- `src/agent/financial_artifact_contracts.py`
- `src/agent/financial_graph_calculation_rendering.py`
- `src/agent/financial_numeric_surface.py`
- `src/agent/financial_row_surfaces.py`
- `tests/fixtures/semantic_program_contract_residuals.json`
- `tests/fixtures/semantic_program_rendering_residuals.json`

The fixture SHA-256 values captured before staging are respectively
`e27f165c2586e61200557980b882f12e13193ef6e669ec5cf3f8896478a22149`
and `b4dfd1439a0e790d26c47093db54c4e42bd12151e1f85f287fd76f191f34075a`.
`src/processing/financial_parser.py` and every other path outside the original
manifest remain excluded because they were not required by this checkpoint's
observed failures.

Minimum closure gate:

```bash
python -m unittest \
  tests.test_semantic_calculation_program \
  tests.test_financial_agent_run_projection \
  tests.test_financial_answer_slots \
  tests.test_financial_task_artifacts \
  tests.test_financial_retrieval_hints \
  tests.test_financial_text_surface \
  tests.test_retrieval_scope
```

## 1. Runtime Projection

Files:

- `src/agent/financial_agent_run_projection.py`
- `src/agent/financial_graph.py`
- `src/agent/financial_graph_calculation.py`
- `src/agent/financial_graph_evidence.py`
- `src/agent/financial_graph_model_loaders.py`
- `src/agent/financial_graph_models.py`
- `src/agent/financial_graph_planning.py`
- `src/agent/financial_graph_state.py`
- `tests/test_financial_agent_run_projection.py`
- `tests/test_semantic_calculation_program.py`

Minimum gates:

- The compiled DAG contains only the canonical numeric program nodes.
- Numeric and mixed routing never reads `operation_family` before execution.
- Runtime projection copies the graph-owned answer and canonical trace without
  reverse-synchronizing final prose into evidence.

Staging command:

```bash
git add \
src/agent/financial_agent_run_projection.py \
src/agent/financial_graph.py \
src/agent/financial_graph_calculation.py \
src/agent/financial_graph_evidence.py \
src/agent/financial_graph_model_loaders.py \
src/agent/financial_graph_models.py \
src/agent/financial_graph_planning.py \
src/agent/financial_graph_state.py \
tests/test_financial_agent_run_projection.py \
tests/test_semantic_calculation_program.py
```

## 2. Task Trace

Files:

- `src/agent/financial_answer_slots.py`
- `src/agent/financial_runtime_trace.py`
- `src/agent/financial_task_artifacts.py`
- `tests/test_financial_answer_slots.py`
- `tests/test_financial_numeric_provenance.py`
- `tests/test_financial_task_artifacts.py`

Minimum gates:

- Candidate references remain stable through program, result, answer-slot, and
  artifact projections.
- Ledger integrity and semantic completeness remain independent signals.
- Missing required obligations produce `partial`, even when another output was
  executed successfully.

Staging command:

```bash
git add \
src/agent/financial_answer_slots.py \
src/agent/financial_runtime_trace.py \
src/agent/financial_task_artifacts.py \
tests/test_financial_answer_slots.py \
tests/test_financial_numeric_provenance.py \
tests/test_financial_task_artifacts.py
```

## 3. Primitive Owner

Files:

- `src/agent/financial_aggregate_projection.py`
- `src/agent/financial_aggregate_state.py`
- `src/agent/financial_calculation_execution.py`
- `src/agent/financial_dependency_projection.py`
- `src/agent/financial_formula_eval.py`
- `src/agent/financial_graph_helpers.py`
- `src/agent/financial_graph_reconciliation.py`
- `src/agent/financial_lookup_recovery.py`
- `src/agent/financial_operand_resolution.py`
- `src/agent/financial_operation_policies.py`
- `src/agent/financial_reconciliation_candidates.py`
- `src/agent/financial_retrieval_hints.py`
- `src/agent/financial_retrieval_pipeline.py`
- `src/agent/financial_scope_policies.py`
- `src/agent/financial_structured_cells.py`
- `src/agent/financial_surface_contracts.py`
- `src/config/financial_ontology.json`
- `src/config/financial_ontology_v2.draft.json`
- `src/config/ontology.py`
- `src/config/retrieval_policy.py`
- `src/ops/compare_concept_planner_shadow.py`
- `src/ops/compare_ontology_shadow.py`
- `src/ops/debug_math_workflow.py`
- `src/ops/debug_reference_note_workflow.py`
- `src/ops/retrospective_math_architecture_eval.py`
- `src/ops/retrospective_ontology_retrieval_eval.py`
- `tests/fixtures/semantic_program_offline_comparison.json`
- `tests/test_aggregate_subtask_projection.py`
- `tests/test_calculation_debug_trace_contract.py`
- `tests/test_concept_runtime_contracts.py`
- `tests/test_financial_aggregate_rank_dedupe.py`
- `tests/test_financial_answer_projection.py`
- `tests/test_financial_calculation_execution.py`
- `tests/test_financial_dependency_projection.py`
- `tests/test_financial_graph_helpers.py`
- `tests/test_financial_operand_resolution.py`
- `tests/test_financial_ratio_presentation.py`
- `tests/test_financial_ratio_readiness.py`
- `tests/test_financial_ratio_scale.py`
- `tests/test_financial_reconciliation_candidates.py`
- `tests/test_financial_retrieval_hints.py`
- `tests/test_financial_text_surface.py`
- `tests/test_lookup_recovery_policy.py`
- `tests/test_math_parsing.py`
- `tests/test_operation_contracts.py`
- `tests/test_ops_runtime_projection_modes.py`
- `tests/test_part_whole_ratio_contract.py`
- `tests/test_reconciliation_plan.py`
- `tests/test_reflection_capability_contract.py`
- `tests/test_retrieval_scope.py`
- `tests/test_semantic_numeric_plan.py`
- `tests/test_semantic_numeric_planner.py`
- `tests/test_structured_operand_extraction.py`
- `tests/test_subtask_loop.py`

Minimum gates:

- The validator rejects missing candidates, invented values, unregistered
  constants, cycles, incompatible units/scopes, and zero division.
- The executor supports the restricted AST and derives compatibility
  `operation_family` only after validation.
- Deleted files have zero production callers, and the ontology retains only
  concepts, aliases, sections, and binding/source hints needed for retrieval.

Staging command:

```bash
git add \
src/agent/financial_aggregate_projection.py \
src/agent/financial_aggregate_state.py \
src/agent/financial_calculation_execution.py \
src/agent/financial_dependency_projection.py \
src/agent/financial_formula_eval.py \
src/agent/financial_graph_helpers.py \
src/agent/financial_graph_reconciliation.py \
src/agent/financial_lookup_recovery.py \
src/agent/financial_operand_resolution.py \
src/agent/financial_operation_policies.py \
src/agent/financial_reconciliation_candidates.py \
src/agent/financial_retrieval_hints.py \
src/agent/financial_retrieval_pipeline.py \
src/agent/financial_scope_policies.py \
src/agent/financial_structured_cells.py \
src/agent/financial_surface_contracts.py \
src/config/financial_ontology.json \
src/config/financial_ontology_v2.draft.json \
src/config/ontology.py \
src/config/retrieval_policy.py \
src/ops/compare_concept_planner_shadow.py \
src/ops/compare_ontology_shadow.py \
src/ops/debug_math_workflow.py \
src/ops/debug_reference_note_workflow.py \
src/ops/retrospective_math_architecture_eval.py \
src/ops/retrospective_ontology_retrieval_eval.py \
tests/fixtures/semantic_program_offline_comparison.json \
tests/test_aggregate_subtask_projection.py \
tests/test_calculation_debug_trace_contract.py \
tests/test_concept_runtime_contracts.py \
tests/test_financial_aggregate_rank_dedupe.py \
tests/test_financial_answer_projection.py \
tests/test_financial_calculation_execution.py \
tests/test_financial_dependency_projection.py \
tests/test_financial_graph_helpers.py \
tests/test_financial_operand_resolution.py \
tests/test_financial_ratio_presentation.py \
tests/test_financial_ratio_readiness.py \
tests/test_financial_ratio_scale.py \
tests/test_financial_reconciliation_candidates.py \
tests/test_financial_retrieval_hints.py \
tests/test_financial_text_surface.py \
tests/test_lookup_recovery_policy.py \
tests/test_math_parsing.py \
tests/test_operation_contracts.py \
tests/test_ops_runtime_projection_modes.py \
tests/test_part_whole_ratio_contract.py \
tests/test_reconciliation_plan.py \
tests/test_reflection_capability_contract.py \
tests/test_retrieval_scope.py \
tests/test_semantic_numeric_plan.py \
tests/test_semantic_numeric_planner.py \
tests/test_structured_operand_extraction.py \
tests/test_subtask_loop.py
```

## 4. Docs Audit

Files:

- `CONTEXT.md`
- `docs/architecture/agent_runtime_contract.md`
- `docs/architecture/core_runtime_surface_refactoring_plan.md`
- `docs/architecture/current_runtime_cleanup_split_manifest.md`
- `docs/architecture/semantic_numeric_planner_design.md`
- `docs/history/experiment_history.md`
- `docs/overview/project_status.md`
- `tests/fixtures/runtime_domain_terms_baseline.json`
- `tests/test_import_side_effects.py`
- `tests/test_ontology.py`

Minimum gates:

- Runtime domain-term audit matches the reviewed baseline.
- Full unittest discovery, graph import/DAG validation, and `git diff --check`
  pass in the complete repository dependency environment.
- Documentation labels the offline fixture as curated/no-call evidence and does
  not claim a fresh benchmark result.

Staging command:

```bash
git add \
CONTEXT.md \
docs/architecture/agent_runtime_contract.md \
docs/architecture/core_runtime_surface_refactoring_plan.md \
docs/architecture/current_runtime_cleanup_split_manifest.md \
docs/architecture/semantic_numeric_planner_design.md \
docs/history/experiment_history.md \
docs/overview/project_status.md \
tests/fixtures/runtime_domain_terms_baseline.json \
tests/test_import_side_effects.py \
tests/test_ontology.py
```

## Gate Order

1. Run focused semantic program, retrieval, rendering, projection, and ledger
   tests without provider calls.
2. Run the import/DAG and runtime domain-term audits.
3. Run full unittest discovery in the repository dependency environment.
4. Confirm deleted legacy symbols and modules have zero production callers.
5. Run `git diff --check` and confirm no benchmark/store/cache artifacts are
   changed.
6. Only after these gates pass, request separate cost authority for the named
   focused replays and the five-question store-fixed gate.
