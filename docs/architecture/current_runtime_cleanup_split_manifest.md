# Current Runtime Cleanup Split Manifest

This manifest captures the current local runtime cleanup diff so it can be
split before any further extraction work. It is intentionally file-oriented:
use it to stage reviewable commits/PRs without mixing runtime contracts,
owner-module extraction, primitive helper moves, and documentation/audit
updates.

Generated from the current worktree after the local cleanup pass:

- `runtime_projection`: 21 files
- `task_trace`: 13 files
- `primitive_owner`: 34 files
- `docs_audit`: 12 files
- `import_time_perf_overlay`: 71 files, overlapping source buckets plus
  API/MAS/RAG/storage/ops import boundaries
- `direct_run_surface`: 6 files, overlapping source buckets plus ingestion
  direct-run cleanup
- `ambiguous`: 0 files

Latest split-readiness measurement:

- changed source/docs/test paths covered by this manifest: `134`, missing: `0`
- numbered review bucket coverage:
  - `runtime_projection`: `21 / 21` touched, tracked diff `+1445 / -1202`,
    untracked touched files `1`
  - `task_trace`: `13 / 13` touched, tracked diff `+862 / -311`,
    untracked touched files `3`
  - `primitive_owner`: `34 / 34` touched, tracked diff `+1887 / -4588`,
    untracked touched files `12`
  - `docs_audit`: `12 / 12` touched, tracked diff `+1905 / -194`,
    untracked touched files `1`
- numbered bucket file overlap in the current changed set: `0`
- owner-foundation import gate:
  `owner_foundation_imports_ok=23`, `heavy_modules_loaded=<none>`
- latest source-bucket union gate:
  - runtime projection focused gate: `169` tests OK
  - task trace focused gate: `317` tests OK
  - primitive owner focused gate: `428` tests OK
  - portfolio review gates: `Status: ready`
  - runtime domain-term audit: passed with `215` reviewed literals
  - full unittest discovery: `1324` tests OK, `full_elapsed=15.033`

Stop line:

- Do not continue extracting semantic numeric planning or reconciliation scorer
  internals in this local diff.
- Do not move functions only to reduce line count.
- Do not add runtime domain vocabulary to compensate for behavior changes.
- Keep benchmark outputs, local stores, temporary profiles, and one-off
  datasets out of every split.

## Buildable Split Guidance

The buckets below are review-topic buckets, not an automatically buildable
file-only commit sequence. Runtime-projection files already import new
task/trace owners, task-trace files import primitive normalization owners, and
primitive call sites import task-artifact owners. A file-only commit in bucket
order can therefore leave an intermediate revision with missing modules.

Use one of these buildable approaches:

1. Lowest-risk local split:
   - Commit or PR all source/test runtime cleanup together as one source
     commit. This is broader than the three numbered review buckets: include
     `runtime_projection`, `task_trace`, `primitive_owner`, plus the source/test
     files that appear only in `import_time_perf_overlay` or
     `direct_run_surface`.
   - Current source commit path set: `122` paths matching `main.py`, `src/**`,
     and `tests/**`, excluding
     `tests/fixtures/runtime_domain_terms_baseline.json`.
   - Commit or PR `docs_audit` separately. Current docs/audit path set: `12`
     paths matching `README.md`, `CONTEXT.md`, `docs/**`, and
     `tests/fixtures/runtime_domain_terms_baseline.json`.
   - Run the union of the three numbered runtime bucket gates plus the overlay
     import/storage/direct-run gates before the source commit, then run the
     docs/audit gates before the docs commit.
   - Lowest-risk source staging command:

     ```bash
     git add main.py src tests \
       ':!tests/fixtures/runtime_domain_terms_baseline.json'
     ```

   - Latest dry-run check for the source staging command:
     `git add --dry-run main.py src tests ':!tests/fixtures/runtime_domain_terms_baseline.json'`
     selects `122` paths.
   - Suggested source commit title:
     `refactor runtime surfaces and import boundaries`

   - Lowest-risk docs/audit staging command:

     ```bash
     git add README.md CONTEXT.md docs tests/fixtures/runtime_domain_terms_baseline.json
     ```

   - Latest dry-run check for the docs/audit staging command:
     `git add --dry-run README.md CONTEXT.md docs tests/fixtures/runtime_domain_terms_baseline.json`
     selects `12` paths.
   - Suggested docs/audit commit title:
     `document runtime cleanup split and audit baseline`
   - Current source/docs path partition check: source `122`, docs/audit `12`,
     overlap `0`, uncovered changed paths `0`.

2. More granular patch series:
   - First add a foundation commit containing new owner/helper modules only.
     This commit should be additive and buildable by itself. It must not include
     caller rewrites that require the new modules.
   - Agent owner foundation:
     `financial_aggregate_projection.py`, `financial_aggregate_state.py`,
     `financial_artifact_contracts.py`, `financial_formula_eval.py`,
     `financial_graph_model_loaders.py`, `financial_langchain_loaders.py`,
     `financial_operation_policies.py`,
     `financial_retrieval_hints.py`,
     `financial_row_surfaces.py`, `financial_runtime_normalization.py`,
     `financial_runtime_trace.py`, `financial_scope_policies.py`,
     `financial_structured_cells.py`, `financial_surface_contracts.py`, and
     `financial_task_artifacts.py`.
   - Import-boundary foundation:
     `src/routing/format_policy.py`, `src/schema/runtime_enums.py`,
     `src/storage/chroma_backend.py`, `src/storage/document_batches.py`,
     `src/storage/graph_persistence.py`, `src/storage/parent_store.py`,
     `src/storage/search_merge.py`, and `src/utils/gemini_usage_counts.py`.
   - Owner-foundation gate. Use `py_compile` for a parse-only check, or the
     import check below when you want to verify import-time dependencies
     without writing bytecode:

     ```bash
     PYTHONDONTWRITEBYTECODE=1 python3 - <<'PY'
     import importlib
     import sys
     modules = [
         "src.agent.financial_aggregate_projection",
         "src.agent.financial_aggregate_state",
         "src.agent.financial_artifact_contracts",
         "src.agent.financial_formula_eval",
         "src.agent.financial_graph_model_loaders",
         "src.agent.financial_langchain_loaders",
         "src.agent.financial_operation_policies",
         "src.agent.financial_retrieval_hints",
         "src.agent.financial_row_surfaces",
         "src.agent.financial_runtime_normalization",
         "src.agent.financial_runtime_trace",
         "src.agent.financial_scope_policies",
         "src.agent.financial_structured_cells",
         "src.agent.financial_surface_contracts",
         "src.agent.financial_task_artifacts",
         "src.routing.format_policy",
         "src.schema.runtime_enums",
         "src.storage.chroma_backend",
         "src.storage.document_batches",
         "src.storage.graph_persistence",
         "src.storage.parent_store",
         "src.storage.search_merge",
         "src.utils.gemini_usage_counts",
     ]
     for name in modules:
         importlib.import_module(name)
     heavy_modules = [name for name in ("pydantic", "langchain_core") if name in sys.modules]
     print(f"owner_foundation_imports_ok={len(modules)}")
     print(f"heavy_modules_loaded={heavy_modules or '<none>'}")
     PY
     ```

   - Owner-foundation staging command:

     ```bash
     git add \
       src/agent/financial_aggregate_projection.py \
       src/agent/financial_aggregate_state.py \
       src/agent/financial_artifact_contracts.py \
       src/agent/financial_formula_eval.py \
       src/agent/financial_graph_model_loaders.py \
       src/agent/financial_langchain_loaders.py \
       src/agent/financial_operation_policies.py \
       src/agent/financial_retrieval_hints.py \
       src/agent/financial_row_surfaces.py \
       src/agent/financial_runtime_normalization.py \
       src/agent/financial_runtime_trace.py \
       src/agent/financial_scope_policies.py \
       src/agent/financial_structured_cells.py \
       src/agent/financial_surface_contracts.py \
       src/agent/financial_task_artifacts.py \
       src/routing/format_policy.py \
       src/schema/runtime_enums.py \
       src/storage/chroma_backend.py \
       src/storage/document_batches.py \
       src/storage/graph_persistence.py \
       src/storage/parent_store.py \
       src/storage/search_merge.py \
       src/utils/gemini_usage_counts.py
     ```

   - Owner-foundation staged review command:

     ```bash
     # after the staging command above
     git diff --cached --stat -- \
       src/agent/financial_aggregate_projection.py \
       src/agent/financial_aggregate_state.py \
       src/agent/financial_artifact_contracts.py \
       src/agent/financial_formula_eval.py \
       src/agent/financial_graph_model_loaders.py \
       src/agent/financial_langchain_loaders.py \
       src/agent/financial_operation_policies.py \
       src/agent/financial_retrieval_hints.py \
       src/agent/financial_row_surfaces.py \
       src/agent/financial_runtime_normalization.py \
       src/agent/financial_runtime_trace.py \
       src/agent/financial_scope_policies.py \
       src/agent/financial_structured_cells.py \
       src/agent/financial_surface_contracts.py \
       src/agent/financial_task_artifacts.py \
       src/routing/format_policy.py \
       src/schema/runtime_enums.py \
       src/storage/chroma_backend.py \
       src/storage/document_batches.py \
       src/storage/graph_persistence.py \
       src/storage/parent_store.py \
       src/storage/search_merge.py \
       src/utils/gemini_usage_counts.py
     ```

   - Then land caller rewrites/removals by review topic. This requires partial
     staging for files such as `financial_graph.py`,
     `financial_graph_calculation.py`, `financial_graph_helpers.py`,
     `src/routing/__init__.py`, `src/routing/query_router.py`,
     `src/schema/__init__.py`, `src/schema/dart_schema.py`, and
     `src/storage/vector_store.py`.
     `src/agent/financial_graph_state.py` is intentionally kept with the
     runtime-projection bucket because it defines the live runtime output/state
     contracts that the caller rewrites consume, even though its direct import
     remains lightweight.
   - Recommended caller split after the foundation commit:
     1. Runtime projection and task-artifact trace callers.
     2. Primitive-owner caller rewrites in calculation/evidence/reconciliation.
     3. Import-time performance overlay across agent/API/MAS/RAG/storage/ops.
     4. Tests.
     5. Docs/audit notes.
   - Re-run the relevant focused gate plus full unittest whenever a caller
     rewrite removes compatibility from the broad helper module or changes an
     import boundary that affects package import side effects.

Do not treat the staging commands below as proof that an intermediate commit is
independently buildable. They are exact file buckets for review and artifact
hygiene.

## Import-Time Performance Overlay

Scope: lazy-import heavyweight LangChain/provider dependencies at the exact
runtime construction points instead of importing them while loading the
FinancialAgent module. This is a performance overlay on top of the source
cleanup buckets, not a separate file-only bucket, because it touches files that
already belong to runtime-projection and primitive-owner review topics.

Files:

- `main.py`
- `src/agent/financial_graph.py`
- `src/agent/financial_graph_calculation.py`
- `src/agent/financial_graph_contextual.py`
- `src/agent/financial_graph_evidence.py`
- `src/agent/financial_graph_planning.py`
- `src/agent/financial_graph_reconciliation.py`
- `src/agent/mas_graph.py`
- `src/agent/nodes/__init__.py`
- `src/agent/nodes/orchestrator_node.py`
- `src/agent/nodes/researcher_node.py`
- `src/agent/rag_chain.py`
- `src/api/financial_router.py`
- `src/experimental/mas/diagnostics.py`
- `src/ops/audit_benchmark_fanout_cost.py`
- `src/ops/benchmark_runner.py`
- `src/ops/calibrate_query_router.py`
- `src/ops/check_routing_confusions.py`
- `src/ops/portfolio_review_gates.py`
- `src/ops/reference_note_capability_gate.py`
- `src/ops/report_cache_promotion_evidence_gate.py`
- `src/ops/review_report_cache_index_contract.py`
- `src/ops/check_report_cache_index_smoke_contract.py`
- `src/ops/compare_concept_planner_shadow.py`
- `src/ops/compare_ontology_shadow.py`
- `src/ops/debug_math_workflow.py`
- `src/ops/debug_reference_note_workflow.py`
- `src/ops/dump_report_structure.py`
- `src/ops/evaluator.py`
- `src/ops/eval_single_question.py`
- `src/ops/generate_grounded_answer_drafts.py`
- `src/ops/mas_analyst_smoke.py`
- `src/ops/mas_direct_worker_probe.py`
- `src/ops/mas_e2e_smoke.py`
- `src/ops/mas_researcher_smoke.py`
- `src/ops/portfolio_demo.py`
- `src/ops/report_cache_index_smoke.py`
- `src/ops/rebuild_vector_store.py`
- `src/ops/render_dart_preview.py`
- `src/ops/run_eval_only.py`
- `src/ops/retrospective_ontology_retrieval_eval.py`
- `src/ops/retrospective_math_architecture_eval.py`
- `src/ops/retrospective_operand_grounding_eval.py`
- `src/processing/chunking.py`
- `src/processing/financial_parser.py`
- `src/processing/pdf_parser.py`
- `src/processing/table_records.py`
- `src/routing/__init__.py`
- `src/routing/format_policy.py`
- `src/routing/query_router.py`
- `src/routing/types.py`
- `src/schema/__init__.py`
- `src/schema/dart_schema.py`
- `src/schema/runtime_enums.py`
- `src/storage/bm25_index.py`
- `src/storage/chroma_backend.py`
- `src/storage/document_batches.py`
- `src/storage/embedding_config.py`
- `src/storage/graph_persistence.py`
- `src/storage/parent_store.py`
- `src/storage/search_merge.py`
- `src/storage/structure_graph.py`
- `src/storage/vector_store.py`
- `src/utils/gemini_usage.py`
- `src/utils/gemini_usage_counts.py`
- `tests/test_financial_parser.py`
- `tests/test_embedding_runtime_config.py`
- `tests/test_gemini_usage.py`
- `tests/test_import_side_effects.py`
- `tests/test_resumable_ingest.py`
- `tests/test_vector_store_fallback.py`

Measured import-time effect:

- Before lazy provider imports: `src.agent.financial_graph import_elapsed=3.807`
- After lazy provider imports only: `src.agent.financial_graph import_elapsed=2.702`
- After lazy router/prompt/parser imports:
  `src.agent.financial_graph import_elapsed=0.450`, repeat
  `import_elapsed=0.165`
- `src.routing import_elapsed=0.099`, repeat `import_elapsed=0.090`
- MAS/RAG import smoke after extending the same lazy-import pattern:
  - `src.agent.nodes.researcher_node import_elapsed=0.161`
  - `src.agent.nodes.orchestrator_node import_elapsed=0.176`
  - `src.agent.rag_chain import_elapsed=0.036`
  - `src.storage.embedding_config import_elapsed=0.038`
  - `src.storage.vector_store import_elapsed=0.442`
- Ops/evaluator import smoke after extending provider lazy-imports and fixing
  evaluator's package import path:
  - `src.ops.evaluator import_elapsed=1.070`
  - `src.ops.check_routing_confusions import_elapsed=0.400`
  - `src.ops.compare_concept_planner_shadow import_elapsed=0.165`
  - `src.ops.retrospective_math_architecture_eval import_elapsed=1.017`
  - `src.ops.generate_grounded_answer_drafts import_elapsed=3.771`
- MAS/debug/retrospective ops import smoke after moving graph/default-node,
  parser/store, and evaluator helper imports to execution points:
  - `src.agent.mas_graph import_elapsed=0.379` -> `0.080`
  - `src.ops.debug_math_workflow import_elapsed=0.378` -> `0.114`
  - `src.ops.debug_reference_note_workflow import_elapsed=3.179` -> `0.099`
  - `src.ops.retrospective_ontology_retrieval_eval import_elapsed=0.871`
    -> `0.110`
- API entrypoint import smoke after moving parser/store/agent/fetcher imports
  to FastAPI lifespan initialization:
  - `main import_elapsed=4.844` -> `0.286`
  - `src.api.financial_router import_elapsed=0.158`
- Store-fixed eval/benchmark/draft-generation CLI import smoke after keeping
  path/JSON/merge helpers local and loading parser/vector-store/runtime only at
  execution points:
  - `src.ops.benchmark_runner import_elapsed=4.354` -> `0.196`
  - `src.ops.run_eval_only import_elapsed=3.314` -> `0.029`
  - `src.ops.eval_single_question import_elapsed=4.030` -> `0.019`
  - `src.ops.generate_grounded_answer_drafts import_elapsed=2.819` -> `0.126`
- Evaluator import smoke after moving MLflow and vector-store embedding imports
  to evaluation execution points:
  - `src.ops.evaluator import_elapsed=0.853` -> `0.158`
- Ops import smoke after moving routing-confusion vector-store embeddings to
  execution and fixing retrospective operand-grounding script bootstrap:
  - `src.ops.check_routing_confusions import_elapsed=0.326` -> `0.075`
  - `src.ops.retrospective_operand_grounding_eval`: package import failure
    fixed, current `import_elapsed=0.171`
- Ops CLI/MAS smoke import boundary pass after moving parser/vector-store/MAS
  runtime imports to execution points:
  - `src.ops.compare_ontology_shadow import_elapsed=2.676` -> `0.021`
  - `src.ops.dump_report_structure import_elapsed=2.640` -> `0.008`
  - `src.ops.render_dart_preview import_elapsed=3.000` -> `0.009`
  - `src.ops.calibrate_query_router import_elapsed=0.486` -> `0.072`
  - `src.ops.mas_analyst_smoke import_elapsed=0.287` -> `0.092`
  - `src.ops.mas_direct_worker_probe import_elapsed=0.277` -> `0.134`
  - `src.ops.mas_e2e_smoke import_elapsed=0.272` -> `0.144`
  - `src.ops.mas_researcher_smoke import_elapsed=0.207` -> `0.010`
  - `src.ops.rebuild_vector_store import_elapsed=0.228` -> `0.031`
  - full `src.ops` package import smoke: `modules=42`, `failures=0`,
    `slow_ge_0_20=0`
- Storage/evaluator import boundary pass after moving Chroma backend and
  evaluator trace/numeric-surface usage helpers to execution points:
  - `src.storage.vector_store import_elapsed=0.429` -> `0.093`
  - `src.ops.evaluator import_elapsed=0.188` -> `0.129`
  - combined agent/ops/routing/storage import smoke: `modules=88`,
    `failures=0`, `slow_ge_0_20=0`
- Processing parser import boundary pass after moving text splitter and PDF
  extraction backends to parser construction/extraction points:
  - `src.processing.financial_parser import_elapsed=3.290` -> `0.099`
  - `src.processing.pdf_parser import_elapsed=3.589` -> `0.093`
  - `src.processing.chunking import_elapsed=0.006`
  - combined agent/ops/routing/storage/processing import smoke: `modules=96`,
    `failures=0`, `slow_ge_0_20=0`
- Follow-up lightweight schema/diagnostic import boundary pass:
  - `src.routing.query_router import_elapsed=0.061` -> `0.029`, with
    `pydantic_loaded=False` and `langchain_core_loaded=False`
  - `src.processing.table_records import_elapsed=0.060` -> `0.006`,
    `src.processing.financial_parser import_elapsed=0.094` -> `0.042`,
    and `src.processing.pdf_parser import_elapsed=0.056` -> `0.001`, all
    without importing Pydantic or LangChain Core
  - `src.ingestion.dart_fetcher import_elapsed=0.110` -> `0.032`, with
    `requests_loaded=False` and `pydantic_loaded=False`
  - `src.experimental.mas.diagnostics import_elapsed=0.009` and
    `src.ops.mas_direct_worker_probe import_elapsed=0.009`, both with
    `langchain_core_loaded=False` and `pydantic_loaded=False`
  - combined agent/experimental MAS/ops/routing/storage/processing import
    smoke: `modules=124`, `failures=0`, `slow_ge_0_05=11`,
    `state_changes=0`
- Follow-up evaluator/replay CLI import boundary pass:
  - replay and retrospective evaluator CLI modules now lazy-load evaluator and
    runtime-trace helpers only when replay/scoring executes
  - `src.ops.evaluator` no longer imports NumPy at module import time; NumPy is
    local to answer-relevancy cosine calculation
  - `src.ops.generate_grounded_answer_drafts` lazy-loads its structured-output
    Pydantic draft schema when `FilingDraftGenerator` is constructed; module
    import now reports `pydantic_loaded=False`
  - `tests/test_import_side_effects.py` now has a fresh-process regression
    guard for these heavy-dependency boundaries, including Pydantic, LangChain
    Core, NumPy, BM25, and requests where those packages are not needed at
    module import time
  - dead import cleanup removed unused import edges from RAG/API/routing/ops
    helper/vector-store modules while preserving compatibility imports that
    tests and public callers still use
  - combined agent/experimental MAS/ops/routing/storage/processing import
    smoke: `modules=124`, `failures=0`, `slow_ge_0_05=4`,
    `state_changes=0`
- Importtime no longer shows top-level LangChain provider,
  Transformers, or Torch loading through `src.agent.financial_graph`.

Import optimization stop-line:

- Current final import smokes report no `slow_ge_0_05` modules for the package
  smoke or the source-wide file import smoke. Do not add compatibility shims
  merely to reduce import timing unless a measured caller imports a public
  surface on a hot path without needing its contract.
- Future import-time work should first prove one of:
  1. a non-schema CLI/helper import pulls in provider/vector/model backends,
  2. a package import mutates process state, or
  3. a new dependency boundary regresses one of the fresh-process guards in
     `tests/test_import_side_effects.py`.

Minimum gates:

- `PYTHONDONTWRITEBYTECODE=1 python3 -c 'import src.agent.financial_graph'`
- `PYTHONDONTWRITEBYTECODE=1 python3 -c 'import src.agent.nodes.researcher_node; import src.agent.nodes.orchestrator_node; import src.agent.rag_chain; import src.storage.embedding_config'`
- `PYTHONDONTWRITEBYTECODE=1 python3 -c 'import src.ops.evaluator; import src.ops.check_routing_confusions; import src.ops.compare_concept_planner_shadow; import src.ops.retrospective_math_architecture_eval'`
- `PYTHONDONTWRITEBYTECODE=1 python3 -c 'import src.agent.mas_graph; import src.ops.debug_math_workflow; import src.ops.debug_reference_note_workflow; import src.ops.retrospective_ontology_retrieval_eval'`
- `PYTHONDONTWRITEBYTECODE=1 python3 -c 'import main; import src.api.financial_router'`
- `PYTHONDONTWRITEBYTECODE=1 python3 -c 'import src.ops.run_eval_only; import src.ops.eval_single_question; import src.ops.generate_grounded_answer_drafts'`
- `PYTHONDONTWRITEBYTECODE=1 python3 -c 'import src.ops.benchmark_runner'`
- `python3 -m unittest tests.test_query_router tests.test_query_router_low_api tests.test_evaluator_runtime_projection tests.test_financial_agent_run_projection tests.test_ops_runtime_projection_modes tests.test_report_scoped_cache_contract tests.test_financial_graph_helpers tests.test_semantic_numeric_plan tests.test_semantic_numeric_planner tests.test_reconciliation_plan tests.test_operation_contracts tests.test_part_whole_ratio_contract tests.test_concept_runtime_contracts tests.test_structured_operand_extraction`
- `python3 -m unittest tests.test_critic_node tests.test_subtask_loop tests.test_aggregate_subtask_projection tests.test_query_router tests.test_query_router_low_api tests.test_vector_store_fallback tests.test_rebuild_vector_store tests.test_embedding_runtime_config tests.test_embedding_usage`
- `python3 -m unittest tests.test_researcher_node tests.test_orchestrator_node tests.test_mas_e2e_smoke tests.test_mas_e2e_smoke_contract tests.test_mas_researcher_smoke_contract tests.test_mas_direct_worker_probe tests.test_experimental_mas_namespace`
- `python3 -m unittest tests.test_evaluator_runtime_projection tests.test_embedding_runtime_config tests.test_embedding_usage tests.test_query_router tests.test_query_router_low_api tests.test_mas_direct_worker_probe tests.test_mas_researcher_smoke_contract`
- `python3 -m unittest tests.test_ops_runtime_projection_modes tests.test_experimental_mas_namespace tests.test_multi_agent_graph tests.test_analyst_node tests.test_researcher_node tests.test_orchestrator_node`
- `python3 -m unittest tests.test_financial_router_response`
- `python3 -m unittest tests.test_run_eval_only tests.test_evaluator_runtime_projection`
- `python3 -m unittest tests.test_benchmark_runner_runtime_projection tests.test_resumable_ingest tests.test_eval_company_aliases tests.test_run_eval_only`
- `python3 -m unittest tests.test_generate_grounded_answer_drafts`
- `python3 -m unittest tests.test_evaluator_progress tests.test_evaluator_runtime_projection`
- `python3 -m unittest tests.test_ops_runtime_projection_modes tests.test_query_router tests.test_query_router_low_api`
- `python3 -m unittest tests.test_mas_researcher_smoke_contract tests.test_mas_e2e_smoke tests.test_mas_e2e_smoke_contract tests.test_mas_direct_worker_probe`
- `python3 -m py_compile src/ops/rebuild_vector_store.py src/ops/mas_researcher_smoke.py src/ops/mas_e2e_smoke.py`
- `python3 -m unittest tests.test_vector_store_fallback tests.test_resumable_ingest tests.test_rebuild_vector_store tests.test_embedding_runtime_config tests.test_embedding_usage tests.test_run_eval_only`
- `python3 -m unittest tests.test_evaluator_runtime_projection tests.test_evaluator_progress tests.test_ops_runtime_projection_modes`
- `python3 -m unittest tests.test_financial_parser`
- `python3 -m unittest tests.test_import_side_effects`
- `python3 -m src.ops.audit_runtime_domain_terms`
- `python3 -m unittest discover -s tests`

## Direct-Run Surface Cleanup Overlay

Scope: remove stale direct-run demo surfaces from library/runtime modules while
keeping maintained execution entry points in README and `src.ops` commands.
This overlay is deletion-only except for removing `dart_fetcher.py`'s import-time
`logging.basicConfig()` side effect.

Files:

- `src/agent/financial_graph.py`
- `src/agent/rag_chain.py`
- `src/ingestion/dart_fetcher.py`
- `src/processing/financial_parser.py`
- `src/processing/pdf_parser.py`
- `src/storage/vector_store.py`

Minimum gates:

- `python3 -m py_compile src/storage/vector_store.py src/agent/financial_graph.py src/agent/rag_chain.py src/ingestion/dart_fetcher.py src/processing/financial_parser.py src/processing/pdf_parser.py`
- `python3 -m unittest tests.test_financial_parser tests.test_vector_store_fallback tests.test_financial_agent_run_projection`
- `python3 -m unittest tests.test_resumable_ingest tests.test_generate_grounded_answer_drafts tests.test_financial_router_response`
- `rg -n "if __name__ == ['\"]__main__['\"]" src/agent src/api src/ingestion src/processing src/routing src/storage -g '*.py'`
- `python3 -m src.ops.audit_runtime_domain_terms`
- `python3 -m unittest discover -s tests`

Latest validation:

- `python3 -m unittest discover -s tests`: `1273` tests OK,
  `full_elapsed=3.48`
- `python3 -m unittest tests.test_generate_grounded_answer_drafts tests.test_ops_runtime_projection_modes tests.test_run_eval_only tests.test_benchmark_runner_runtime_projection`:
  `40` tests OK, `focused_ops_boundary_elapsed=0.01`
- repeat after grounded draft generator import boundary pass:
  `python3 -m unittest discover -s tests`: `1273` tests OK,
  `full_elapsed=3.41`
- repeat after evaluator lazy MLflow/vector-store boundary pass:
  `python3 -m unittest tests.test_evaluator_progress tests.test_evaluator_runtime_projection`:
  `65` tests OK, `focused_evaluator_boundary_elapsed=0.01`
- repeat after evaluator lazy MLflow/vector-store boundary pass:
  `python3 -m unittest discover -s tests`: `1273` tests OK,
  `full_elapsed=3.33`
- repeat after routing-confusion vector-store lazy boundary and retrospective
  operand bootstrap fix:
  `python3 -m unittest tests.test_ops_runtime_projection_modes tests.test_query_router tests.test_query_router_low_api`:
  `20` tests OK, `focused_routing_ops_boundary_elapsed=0.01`
- repeat after routing-confusion vector-store lazy boundary and retrospective
  operand bootstrap fix:
  `python3 -m unittest discover -s tests`: `1273` tests OK,
  `full_elapsed=3.32`
- repeat after ops CLI/MAS smoke import boundary pass:
  `python3 -m unittest tests.test_mas_researcher_smoke_contract tests.test_mas_e2e_smoke tests.test_mas_e2e_smoke_contract tests.test_mas_direct_worker_probe`:
  `24` tests OK, `focused_mas_cli_boundary_elapsed=0.66`
- repeat after ops CLI/MAS smoke import boundary pass:
  `python3 -m py_compile src/ops/rebuild_vector_store.py src/ops/mas_researcher_smoke.py src/ops/mas_e2e_smoke.py`:
  passed
- repeat after ops CLI/MAS smoke import boundary pass:
  `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
  reviewed literals
- repeat after ops CLI/MAS smoke import boundary pass:
  `python3 -m unittest discover -s tests`: `1273` tests OK,
  `full_elapsed=3.03`
- repeat after storage/evaluator import boundary pass:
  `python3 -m unittest tests.test_vector_store_fallback tests.test_resumable_ingest tests.test_rebuild_vector_store tests.test_embedding_runtime_config tests.test_embedding_usage tests.test_run_eval_only`:
  `51` tests OK, `focused_storage_boundary_elapsed=3.33`
- repeat after storage/evaluator import boundary pass:
  `python3 -m unittest tests.test_evaluator_runtime_projection tests.test_evaluator_progress tests.test_ops_runtime_projection_modes`:
  `82` tests OK, `focused_evaluator_boundary_elapsed=0.16`
- repeat after storage/evaluator import boundary pass:
  `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
  reviewed literals
- repeat after storage/evaluator import boundary pass:
  `python3 -m unittest discover -s tests`: `1277` tests OK,
  `full_elapsed=5.57`
- repeat after storage/evaluator import boundary pass:
  combined agent/ops/routing/storage import smoke: `modules=88`,
  `failures=0`, `slow_ge_0_20=0`
- repeat after processing parser import boundary pass:
  `python3 -m unittest tests.test_financial_parser`: `30` tests OK,
  `focused_processing_boundary_elapsed=3.67`
- repeat after processing parser import boundary pass:
  combined agent/ops/routing/storage/processing import smoke: `modules=96`,
  `failures=0`, `slow_ge_0_20=0`
- repeat after removing `src.processing.pdf_parser` import-time logging side
  effect:
  `python3 -m py_compile src/processing/pdf_parser.py`: passed
- repeat after removing `src.processing.pdf_parser` import-time logging side
  effect:
  `python3 -m unittest tests.test_financial_parser`: `30` tests OK,
  `focused_processing_boundary_elapsed=2.99`
- repeat after removing `src.processing.pdf_parser` import-time logging side
  effect:
  `src.processing.pdf_parser import_elapsed=0.054`,
  `root_logging_level changed=False`
- repeat after removing `src.processing.pdf_parser` import-time logging side
  effect:
  `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
  reviewed literals
- repeat after removing `src.processing.pdf_parser` import-time logging side
  effect:
  `python3 -m unittest discover -s tests`: `1277` tests OK,
  `full_elapsed=5.686`
- repeat after extracting Chroma backend/probe wrappers:
  `python3 -m py_compile src/storage/chroma_backend.py src/storage/vector_store.py`:
  passed
- repeat after extracting Chroma backend/probe wrappers:
  `python3 -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config tests.test_resumable_ingest tests.test_rebuild_vector_store`:
  `44` tests OK, `focused_storage_boundary_elapsed=0.151`
- repeat after extracting Chroma backend/probe wrappers:
  `src.storage.chroma_backend import_elapsed=0.004`,
  `src.storage.vector_store import_elapsed=0.090`, Chroma backend loaded `False`
- repeat after extracting Chroma backend/probe wrappers:
  combined agent/ops/routing/storage/processing import smoke: `modules=97`,
  `failures=0`, `slow_ge_0_20=0`
- repeat after extracting Chroma backend/probe wrappers:
  `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
  reviewed literals
- repeat after extracting Chroma backend/probe wrappers:
  `python3 -m unittest discover -s tests`: `1278` tests OK,
  `full_elapsed=5.617`
- repeat after extracting Chroma backend/probe wrappers:
  `git diff --check`: passed
- artifact hygiene check for `benchmarks/results`, `benchmarks/*.tmp`,
  benchmark stores, and `mlruns`: no tracked or untracked cleanup artifacts
  reported
- repeat after extracting search identity/RRF merge helpers:
  `python3 -m py_compile src/storage/search_merge.py src/storage/vector_store.py`:
  passed
- repeat after extracting search identity/RRF merge helpers:
  `python3 -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config tests.test_resumable_ingest tests.test_rebuild_vector_store`:
  `46` tests OK, `focused_storage_boundary_elapsed=0.147`
- repeat after extracting search identity/RRF merge helpers:
  `src.storage.search_merge import_elapsed=0.084`,
  `src.storage.vector_store import_elapsed=0.005`, Chroma backend loaded `False`
- repeat after extracting search identity/RRF merge helpers:
  combined agent/ops/routing/storage/processing import smoke: `modules=98`,
  `failures=0`, `slow_ge_0_20=0`
- repeat after extracting search identity/RRF merge helpers:
  `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
  reviewed literals
- repeat after extracting search identity/RRF merge helpers:
  `python3 -m unittest discover -s tests`: `1280` tests OK,
  `full_elapsed=5.763`
- repeat after extracting search identity/RRF merge helpers:
  `git diff --check`: passed
- artifact hygiene check for `benchmarks/results`, `benchmarks/*.tmp`,
  benchmark stores, and `mlruns`: no tracked or untracked cleanup artifacts
  reported
- repeat after extracting add-document preparation/batching helpers:
  `python3 -m py_compile src/storage/document_batches.py src/storage/vector_store.py`:
  passed
- repeat after extracting add-document preparation/batching helpers:
  `python3 -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config tests.test_resumable_ingest tests.test_rebuild_vector_store`:
  `48` tests OK, `focused_storage_boundary_elapsed=0.152`
- repeat after extracting add-document preparation/batching helpers:
  `src.storage.document_batches import_elapsed=0.028`,
  `src.storage.vector_store import_elapsed=0.005`, Chroma backend loaded `False`
- repeat after extracting add-document preparation/batching helpers:
  combined agent/ops/routing/storage/processing import smoke: `modules=99`,
  `failures=0`, `slow_ge_0_20=0`
- repeat after extracting add-document preparation/batching helpers:
  `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
  reviewed literals
- repeat after extracting add-document preparation/batching helpers:
  `python3 -m unittest discover -s tests`: `1282` tests OK,
  `full_elapsed=6.901`
- repeat after splitting the remaining `add_documents()` runtime path:
  `python3 -m py_compile src/storage/document_batches.py src/storage/vector_store.py`:
  passed
- repeat after splitting the remaining `add_documents()` runtime path:
  `python3 -m unittest tests.test_vector_store_fallback tests.test_resumable_ingest tests.test_rebuild_vector_store`:
  `46` tests OK
- repeat after splitting the remaining `add_documents()` runtime path:
  `python3 -m unittest tests.test_benchmark_runner_runtime_projection tests.test_run_eval_only tests.test_embedding_runtime_config tests.test_financial_parser`:
  `52` tests OK
- repeat after splitting the remaining `add_documents()` runtime path:
  source-wide import smoke reports `modules=112`, `failures=0`,
  `slow_ge_0_05=1`
- repeat after splitting the remaining `add_documents()` runtime path:
  `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
  reviewed literals
- repeat after splitting the remaining `add_documents()` runtime path:
  `python3 -m unittest discover -s tests`: `1324` tests OK,
  `full_elapsed=13.522`
- repeat after extracting add-document preparation/batching helpers:
  `git diff --check`: passed
- artifact hygiene check for `benchmarks/results`, `benchmarks/*.tmp`,
  benchmark stores, and `mlruns`: no tracked or untracked cleanup artifacts
  reported
- repeat after extracting parent persistence helpers:
  `python3 -m py_compile src/storage/parent_store.py src/storage/vector_store.py`:
  passed
- repeat after extracting parent persistence helpers:
  `python3 -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config tests.test_resumable_ingest tests.test_rebuild_vector_store`:
  `49` tests OK, `focused_storage_boundary_elapsed=0.180`
- repeat after extracting parent persistence helpers:
  `src.storage.parent_store import_elapsed=0.013`,
  `src.storage.vector_store import_elapsed=0.006`, Chroma backend loaded `False`
- repeat after extracting parent persistence helpers:
  combined agent/ops/routing/storage/processing import smoke: `modules=100`,
  `failures=0`, `slow_ge_0_20=0`
- repeat after extracting parent persistence helpers:
  `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
  reviewed literals
- repeat after extracting parent persistence helpers:
  `python3 -m unittest discover -s tests`: `1283` tests OK,
  `full_elapsed=7.111`
- repeat after extracting parent persistence helpers:
  `git diff --check`: passed
- artifact hygiene check for `benchmarks/results`, `benchmarks/*.tmp`,
  benchmark stores, and `mlruns`: no tracked or untracked cleanup artifacts
  reported
- repeat after extracting structure graph persistence helpers:
  `python3 -m py_compile src/storage/graph_persistence.py src/storage/vector_store.py`:
  passed
- repeat after extracting structure graph persistence helpers:
  `python3 -m unittest tests.test_vector_store_fallback tests.test_embedding_runtime_config tests.test_resumable_ingest tests.test_rebuild_vector_store`:
  `50` tests OK, `focused_storage_boundary_elapsed=0.155`
- repeat after extracting structure graph persistence helpers:
  `src.storage.graph_persistence import_elapsed=0.094`,
  `src.storage.vector_store import_elapsed=0.004`, Chroma backend loaded `False`
- repeat after extracting structure graph persistence helpers:
  combined agent/ops/routing/storage/processing import smoke: `modules=101`,
  `failures=0`, `slow_ge_0_20=0`
- repeat after extracting structure graph persistence helpers:
  `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
  reviewed literals
- repeat after extracting structure graph persistence helpers:
  `python3 -m unittest discover -s tests`: `1284` tests OK,
  `full_elapsed=6.774`
- repeat after extracting structure graph persistence helpers:
  `git diff --check`: passed
- artifact hygiene check for `benchmarks/results`, `benchmarks/*.tmp`,
  benchmark stores, and `mlruns`: no tracked or untracked cleanup artifacts
  reported
- repeat after reviewer-doc link/claim duplication cleanup:
  reviewer-facing local link check: `checked_links=49`, `missing=0`
- repeat after reviewer-doc link/claim duplication cleanup:
  stale reviewer-facing test-count search for `1223` and
  `latest full unittest discovery passed`: no matches
- repeat after reviewer-doc link/claim duplication cleanup:
  `requirements.txt` and `requirements-review.txt` parsed via
  `packaging.requirements.Requirement`: `193` and `1` entries
- repeat after reviewer-doc link/claim duplication cleanup:
  `python3 -m src.ops.portfolio_review_gates`: `Status: ready`
- repeat after reviewer-doc link/claim duplication cleanup:
  `python3 -m src.ops.portfolio_demo --format json`: readiness `ready`
- manifest/worktree file coverage check: `changed=102`, `manifest_paths=102`,
  `missing=0`
- repeat after stale direct-run demo deletion:
  removed `if __name__ == "__main__"` demo surfaces from
  `src/agent/financial_graph.py`, `src/agent/rag_chain.py`,
  `src/storage/vector_store.py`, `src/processing/financial_parser.py`, and
  `src/processing/pdf_parser.py`; the same deletion-only rule was then applied
  to `src/ingestion/dart_fetcher.py`, and its import-time
  `logging.basicConfig()` side effect was removed. Maintained review/execution
  entry points remain README and `src.ops` commands.
- repeat after stale direct-run demo deletion:
  `python3 -m py_compile src/storage/vector_store.py src/agent/financial_graph.py src/agent/rag_chain.py src/ingestion/dart_fetcher.py src/processing/financial_parser.py src/processing/pdf_parser.py`:
  passed across the touched direct-run cleanup files
- repeat after stale direct-run demo deletion:
  `python3 -m unittest tests.test_financial_parser tests.test_vector_store_fallback tests.test_financial_agent_run_projection`:
  `103` tests OK
- repeat after stale direct-run demo deletion:
  `python3 -m unittest tests.test_resumable_ingest tests.test_generate_grounded_answer_drafts tests.test_financial_router_response`:
  `28` tests OK
- repeat after stale direct-run demo deletion:
  direct import smoke:
  `src.agent.rag_chain import_elapsed=0.026`,
  `src.processing.financial_parser import_elapsed=0.063`,
  `src.processing.pdf_parser import_elapsed=0.000`,
  `src.storage.vector_store import_elapsed=0.016`,
  `src.agent.financial_graph import_elapsed=0.041`,
  `src.ingestion.dart_fetcher import_elapsed=0.126`,
  `root_logging_level_changed=False`
- repeat after stale direct-run demo deletion:
  `rg -n "if __name__ == ['\"]__main__['\"]" src/agent src/api src/ingestion src/processing src/routing src/storage -g '*.py'`:
  no remaining non-ops direct-run demo surfaces
- repeat after stale direct-run demo deletion:
  combined agent/ops/routing/storage/processing import smoke: `modules=101`,
  `failures=0`, `slow_ge_0_20=0`
- repeat after stale direct-run demo deletion:
  combined agent/api/ingestion/ops/routing/storage/processing import smoke:
  `modules=103`, `failures=0`, `slow_ge_0_20=0`,
  `logging_level_changes=0`; remaining package-import `sys.path` mutations
  were ops-only bootstrap scripts and are now covered by the bounded ops
  bootstrap cleanup below.
- repeat after API import side-effect cleanup:
  `src/api/financial_router.py` no longer mutates `sys.path` at import time;
  component construction still lazy-loads parser/store/fetcher/agent at FastAPI
  lifespan initialization using package-qualified `src.*` imports.
- repeat after API import side-effect cleanup:
  `python3 -m py_compile src/api/financial_router.py main.py`: passed
- repeat after API import side-effect cleanup:
  `python3 -m unittest tests.test_financial_router_response`: `3` tests OK
- repeat after API import side-effect cleanup:
  `src.api.financial_router import_elapsed=0.211/0.245/0.210`,
  `syspath_changed=False`
- repeat after ops package-import bootstrap cleanup:
  package imports no longer mutate `sys.path` for
  `src.ops.audit_benchmark_fanout_cost`,
  `src.ops.report_cache_index_smoke`,
  `src.ops.check_report_cache_index_smoke_contract`,
  `src.ops.benchmark_runner`,
  `src.ops.compare_concept_planner_shadow`,
  `src.ops.compare_ontology_shadow`,
  `src.ops.debug_math_workflow`,
  `src.ops.debug_reference_note_workflow`,
  `src.ops.dump_report_structure`,
  `src.ops.mas_analyst_smoke`,
  `src.ops.eval_single_question`, and
  `src.ops.mas_direct_worker_probe`; the same conditional direct-run bootstrap
  pattern now also covers the later touched grounded draft, MAS E2E,
  researcher smoke, rebuild, render, replay, retrospective, and eval-only
  scripts. Direct file execution still has conditional project-root bootstrap.
- repeat after ops package-import bootstrap cleanup:
  direct `--help` smoke passed for the touched ops CLI files.
- repeat after ops package-import bootstrap cleanup:
  focused ops/bootstrap suites:
  `python3 -m unittest tests.test_mas_direct_worker_probe tests.test_ops_runtime_projection_modes tests.test_run_eval_only tests.test_benchmark_runner_runtime_projection tests.test_benchmark_fanout_cost_audit tests.test_report_cache_index_smoke_contract`:
  `45` tests OK
- repeat after ops package-import bootstrap cleanup:
  interim combined package import side-effect smoke: `modules=103`,
  `failures=0`, `slow_ge_0_20=0`, `logging_level_changes=0`, with two
  remaining ops bootstrap path changes before the final bounded pass.
- final repeat after completing the bounded ops package-import bootstrap
  cleanup:
  combined agent/api/ingestion/ops/routing/storage/processing import smoke:
  `modules=111`, `failures=0`, `slow_ge_0_20=0`,
  `logging_level_changes=0`, `syspath_changes=0`.
- final repeat after completing the bounded ops package-import bootstrap
  cleanup:
  `python3 -m unittest tests.test_run_eval_only tests.test_benchmark_runner_runtime_projection tests.test_ops_runtime_projection_modes`:
  `34` tests OK.
- final repeat after completing the bounded ops package-import bootstrap
  cleanup:
  `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
  reviewed literals.
- final repeat after completing the bounded ops package-import bootstrap
  cleanup:
  `python3 -m unittest discover -s tests`: `1284` tests OK,
  `full_elapsed=6.716`.
- follow-up direct-run entrypoint bootstrap pass:
  `src/ops/evaluator.py` now uses conditional project-root bootstrap for
  direct-file import context and `src.*` imports in its direct-run smoke body.
  Direct `--help` smoke passes for `calibrate_query_router.py`,
  `check_mas_e2e_smoke_contract.py`, `check_routing_confusions.py`,
  `portfolio_demo.py`, `portfolio_review_gates.py`,
  `reference_note_capability_gate.py`,
  `report_cache_promotion_evidence_gate.py`, and
  `review_report_cache_index_contract.py`.
- follow-up direct-run entrypoint focused gate:
  `python3 -m unittest tests.test_query_router tests.test_query_router_low_api tests.test_portfolio_demo tests.test_portfolio_review_gates tests.test_reference_note_capability_gate tests.test_report_cache_promotion_evidence_gate tests.test_review_report_cache_index_contract tests.test_ops_runtime_projection_modes`:
  `39` tests OK.
- follow-up evaluator/ops focused gate:
  `python3 -m unittest tests.test_evaluator_runtime_projection tests.test_evaluator_progress tests.test_ops_runtime_projection_modes`:
  `82` tests OK.
- follow-up combined package import smoke: `modules=111`, `failures=0`,
  `slow_ge_0_20=0`, `logging_level_changes=0`, `syspath_changes=0`.
- follow-up full unittest repeat:
  `python3 -m unittest discover -s tests`: `1284` tests OK,
  `full_elapsed=8.775`.
- full argparse ops entrypoint direct-run help smoke:
  `checked=41`, `failures=0`.
- import-state side-effect check after the full ops direct-run smoke:
  combined package import over agent/api/ingestion/ops/routing/storage/
  processing reports `modules=111`, `failures=0`, `environ_changes=0`.
- current key import latency sample:
  `src.agent.financial_graph=0.133s`, `src.api.financial_router=0.099s`,
  `src.ops.benchmark_runner=0.003s`, `src.ops.evaluator=0.047s`,
  `src.ops.run_eval_only=0.000s`, `src.ops.portfolio_review_gates=0.002s`,
  `src.storage.vector_store=0.002s`,
  `src.processing.financial_parser=0.021s`, and
  `src.processing.pdf_parser=0.000s`.
- source parse gate:
  `python3 -m compileall -q src/ops src/agent src/storage src/processing src/routing src/api src/ingestion`
  passed.
- follow-up dotenv/import-state cleanup:
  `main.py` no longer mutates `sys.path` or configures root logging during
  import; API `.env` loading moved to component initialization; `FinancialAgent`,
  RAG/MAS node, DART fetcher, and selected retrospective/routing ops dotenv
  loading moved to constructor or CLI execution points. `embedding_config.py`
  now reads `.env` through `dotenv_values()` for default provider/model
  calculation without mutating `os.environ`.
- follow-up fresh-process import-state smoke:
  `main`, `src.api.financial_router`, `src.agent.financial_graph`,
  `src.agent.rag_chain`, `src.agent.nodes.researcher_node`,
  `src.agent.nodes.orchestrator_node`, `src.storage.embedding_config`,
  `src.ingestion.dart_fetcher`, `src.ops.check_routing_confusions`,
  `src.ops.retrospective_math_architecture_eval`, and
  `src.ops.retrospective_ontology_retrieval_eval` all report
  `env=False`, `path=False`, `logging=False`.
- follow-up combined package import smoke:
  `modules=111`, `failures=0`, `slow_ge_0_20=0`,
  `logging_level_changes=0`, `syspath_changes=0`, `environ_changes=0`.
- follow-up focused gates:
  embedding/storage/eval-only suite `58` tests OK; runtime/API/MAS/router
  suite `90` tests OK; earlier agent operation/subtask suite `527` tests OK.
- follow-up full gates:
  `python3 -m src.ops.audit_runtime_domain_terms` passed with `215`
  reviewed literals; `python3 -m unittest discover -s tests`: `1284` tests OK,
  `full_elapsed=7.292`; source `compileall` passed.
- follow-up import side-effect contract test:
  `python3 -m unittest tests.test_import_side_effects`: `2` tests OK.
- latest full unittest repeat after adding the import side-effect contract:
  `python3 -m unittest discover -s tests`: `1286` tests OK,
  `full_elapsed=9.199`.
- follow-up package-wide import side-effect contract:
  `tests/test_import_side_effects.py` now walks all `src.agent`, `src.api`,
  `src.experimental`, `src.ingestion`, `src.ops`, `src.routing`,
  `src.schema`, `src.storage`, `src.processing`, and `src.utils` modules and
  asserts package imports do not mutate `sys.path`, `os.environ`, or the root
  logging level.
- package-wide import contract was tightened to check package `__init__`
  imports before module discovery, so side effects from re-export packages such
  as `src.routing` are covered directly.
- latest full unittest repeat after the package-wide import contract:
  `python3 -m unittest discover -s tests`: `1287` tests OK, latest repeat
  `full_elapsed=8.538`; runtime domain-term audit passed with `215` reviewed
  literals.
- follow-up import dependency check:
  `FinancialAgent` now imports `GeminiUsageCallbackHandler` only when an agent
  instance is constructed, not while importing `src.agent.financial_graph`.
  Remaining `langchain_core` import-time warning comes from `Document` surfaces
  used by evidence/reconciliation/storage contracts, so it was left in place
  instead of moving broad document types in this pass.
- latest full unittest repeat after the callback lazy-import cleanup:
  `python3 -m unittest discover -s tests`: `1286` tests OK,
  `full_elapsed=9.128`; runtime domain-term audit passed with `215` reviewed
  literals; combined package import smoke stayed at `modules=111`,
  `failures=0`, `slow_ge_0_20=0`, `logging_level_changes=0`,
  `syspath_changes=0`, `environ_changes=0`.
- repeat after stale direct-run demo deletion:
  `python3 -m src.ops.audit_runtime_domain_terms`: passed with `215`
  reviewed literals
- repeat after stale direct-run demo deletion:
  `python3 -m unittest discover -s tests`: `1284` tests OK,
  `full_elapsed=6.178`
- manifest/worktree file coverage check after direct-run demo deletion:
  `changed=106`, `manifest_paths=106`, `missing=0`
- `git diff --check`: passed
- artifact hygiene check for `benchmarks/results`, `benchmarks/*.tmp`, and
  benchmark stores, plus `mlruns`: no tracked or untracked cleanup artifacts
  reported
- latest static import/path guard repeat:
  `python3 -m unittest tests.test_import_side_effects`: `5` tests OK; package
  import performance/state smoke over agent/api/ingestion/ops/routing/storage/
  processing reports `modules=111`, `failures=0`, `slow_ge_0_20=0`,
  `state_changes=0`; `python3 -m src.ops.audit_runtime_domain_terms` passed
  with `215` reviewed literals; `python3 -m unittest discover -s tests`:
  `1289` tests OK, `full_elapsed=10.689`.
- latest LangChain `Document` import boundary repeat:
  `financial_graph_evidence.py` and `financial_graph_reconciliation.py` keep
  `Document` imports type-only or local to document construction. Current import
  smoke reports `src.agent.financial_graph_evidence import_elapsed=0.133`,
  `src.agent.financial_graph_reconciliation import_elapsed=0.001`, and
  `src.agent.financial_graph import_elapsed=0.025`; package import
  performance/state smoke remains `modules=111`, `failures=0`,
  `slow_ge_0_20=0`, `state_changes=0`. Focused
  import/evidence/reconciliation/planning suite: `408` tests OK; runtime
  domain-term audit passed with `215` reviewed literals; full unittest:
  `1289` tests OK, `full_elapsed=10.532`.
- latest Gemini usage accounting split:
  pure usage/cost helpers now live in `src.utils.gemini_usage_counts`, while
  `src.utils.gemini_usage` remains the LangChain callback adapter. Contextual
  ingest, benchmark runner, fanout audit, and evaluator usage totals consume the
  pure module. `tests/test_import_side_effects.py` includes a fresh-process
  guard that imports the pure usage module and contextual ingest without loading
  `langchain_core`. Current import smoke:
  `src.utils.gemini_usage_counts=0.006`,
  `src.agent.financial_graph_contextual=0.025`,
  `src.agent.financial_graph=0.156`, `src.ops.benchmark_runner=0.133`,
  `src.ops.audit_benchmark_fanout_cost=0.014`, `src.ops.evaluator=0.110`;
  these pure-path imports report `langchain_core_loaded=False`, while callback
  adapter import remains isolated at `src.utils.gemini_usage=0.072`.
  Focused Gemini/import/benchmark/evaluator/ingest suite: `115` tests OK;
  package import smoke including `src.utils`: `modules=115`, `failures=0`,
  `slow_ge_0_20=0`, `state_changes=0`; runtime domain-term audit passed with
  `215` reviewed literals; full unittest: `1290` tests OK,
  `full_elapsed=11.608`.
- latest benchmark runner projection import boundary:
  `benchmark_runner.py` lazy-loads runtime trace and task-artifact projection
  helpers only when result projection executes. Current import smoke:
  `src.ops.benchmark_runner import_elapsed=0.039`, `pydantic_loaded=False`,
  `langchain_core_loaded=False`; adjacent ops smoke:
  `src.ops.run_eval_only=0.030`, `src.ops.evaluator=0.117`. Focused
  import/benchmark/evaluator/ingest suite: `133` tests OK; package import smoke
  including `src.utils`: `modules=115`, `failures=0`, `slow_ge_0_20=0`,
  `state_changes=0`; runtime domain-term audit passed with `215` reviewed
  literals; full unittest: `1290` tests OK, `full_elapsed=11.144`.
- latest storage `Document` import boundary:
  `src.storage.search_merge` keeps `Document` type-only, and
  `src.storage.bm25_index` / `src.storage.structure_graph` import it only when
  constructing result documents. Current import smoke:
  `src.storage.vector_store import_elapsed=0.032`, `langchain_core_loaded=False`,
  `pydantic_loaded=False`; BM25 and structure-graph construction smoke still
  returns `Document` instances. `py_compile` passed for the touched storage
  modules; `python3 -m unittest tests.test_import_side_effects`: `6` tests OK;
  focused vector-store/ingest/embedding suite: `56` tests OK; combined package
  import smoke over agent/api/ingestion/ops/routing/storage/processing/utils:
  `modules=110`, `failures=0`, `slow_ge_0_20=0`, `state_changes=0`; runtime
  domain-term audit passed with `215` reviewed literals; full unittest:
  `1290` tests OK, `full_elapsed=9.990`; `git diff --check` passed.
- latest schema enum and MAS node import boundary:
  `src.schema.runtime_enums` owns lightweight ledger/document enums, and
  `src.schema` lazy-loads Pydantic record models only when requested.
  `src.agent.financial_answer_slots` lazy-loads answer-slot validation at
  `build_answer_slots()` return points. `src.agent.nodes` now keeps
  compatibility exports lazy; analyst/researcher nodes no longer import
  LangChain `Document`, and analyst node imports `FinancialAgent` only when the
  real node factory runs. Current import smoke:
  `src.agent.financial_answer_slots import_elapsed=0.010`,
  `pydantic_loaded=False`; `src.agent.financial_artifact_contracts`
  `import_elapsed=0.006`, `pydantic_loaded=False`; `src.agent.nodes`
  `import_elapsed=0.000`, `pydantic_loaded=False`; individual MAS node imports
  stay in the `0.009` to `0.025` second range without Pydantic or LangChain
  Core. Combined package import smoke over
  agent/api/ingestion/ops/routing/storage/processing/utils/schema:
  `modules=113`, `failures=0`, `slow_ge_0_05=4`, `state_changes=0`; runtime
  domain-term audit passed with `215` reviewed literals; full unittest:
  `1290` tests OK, `full_elapsed=9.374`; `git diff --check` passed.
- latest FinancialAgent/mixin import boundary:
  runtime trace, calculation execution, planning, calculation, evidence,
  reconciliation, and `financial_graph.py` now keep Pydantic structured-output
  models and task-artifact Pydantic record helpers behind phase execution
  wrappers. `src.routing.format_policy` owns lightweight format preference
  helpers, and `src.routing` keeps compatibility exports lazy. Current smoke:
  `src.agent.financial_runtime_trace=0.017`,
  `src.agent.financial_calculation_execution=0.013`,
  `src.agent.financial_graph_planning=0.030`,
  `src.agent.financial_graph_evidence=0.079`,
  `src.agent.financial_graph_reconciliation=0.026`, and
  `src.agent.financial_graph=0.044`; each reports `pydantic_loaded=False`,
  `langchain_core_loaded=False`. Combined package import smoke over
  agent/api/ingestion/ops/routing/storage/processing/utils/schema:
  `modules=114`, `failures=0`, `slow_ge_0_05=4`, `state_changes=0`; runtime
  domain-term audit passed with `215` reviewed literals; full unittest:
  `1290` tests OK, `full_elapsed=8.382`; `git diff --check` passed.
- latest split-readiness gate:
  the owner-foundation import check covers `23` additive helper modules and
  now reports `heavy_modules_loaded=<none>`. `financial_task_artifacts.py`
  lazy-loads Pydantic record models only when ledger mutation helpers execute.
  Follow-up lightweight schema/processing/ingestion/MAS diagnostic and
  evaluator/replay CLI import cleanup keeps Pydantic record/schema, LangChain
  document, evaluator, runtime-trace, NumPy, and draft-generation structured
  output schema imports behind the execution paths that need them.
  Earlier `src.agent.financial_graph` import smoke reports
  `financial_graph_import_elapsed=0.038689`, `pydantic_loaded=False`,
  `langchain_core_loaded=False`. Earlier combined import smoke over
  agent/experimental MAS/api/ingestion/ops/routing/storage/processing/schema/
  utils reports `modules=114`, `failures=0`, `slow_ge_0_05=0`,
  `state_changes=0`. Dead-wrapper pruning removed unused pass-through helpers
  from the parser/reference-resolution and vector-store/search boundaries after
  static `src`/`tests` reference checks showed no callers. Follow-up graph
  state/schema split moves the `FinancialAgentState` and runtime calculation
  trace TypedDict contracts to `src.agent.financial_graph_state`; fresh imports
  of `financial_graph_state` and `financial_runtime_trace` report
  `pydantic_loaded=False` and `langchain_core_loaded=False`, while
  `financial_graph_models.py` remains the Pydantic structured-output schema and
  compatibility export surface. State-only imports in runtime mixins and state
  shape tests now point at `financial_graph_state.py` instead of the Pydantic
  schema module; `tests/test_import_side_effects.py` now guards that boundary
  plus the graph facade and planning/evidence/calculation/reconciliation mixin
  imports against accidental Pydantic/LangChain loads. Answer-slot payload
  validation keeps its Pydantic `TypeAdapter` lazy so the adapter is built only
  when validation runs, not at schema module import time. Structured-output
  Pydantic models use `defer_build=True`, reducing
  `src.agent.financial_graph_models` fresh import to roughly `0.058-0.064s`.
  The same deferred-build base is now used by `src.schema.dart_schema` and
  `src.routing.types`; `src.routing.query_router` still imports without
  Pydantic. Follow-up structured-output surface cleanup removed the unused
  `financial_graph_state` compatibility re-export from
  `src.agent.financial_graph_models`; direct import now reports
  `financial_graph_state_loaded=False`, `has_agent_answer=False`. The aggregate
  subtask state carriers now live in lightweight
  `src.agent.financial_aggregate_state`; direct import reports
  `pydantic_loaded=False` and `langchain_core_loaded=False`, and tests import
  `_AggregateSynthesisState` from that owner instead of the large calculation
  mixin. Pure aggregate selected-claim-id, ordered source-ref, source-task-id,
  integrity projection selection, integrity extra-ref projection, period-context
  evidence merge projection, completion base payload projection, aggregate
  artifact payload projection, calculation projection override application, and
  aggregate task status selection and selected-claim-id extension now live in lightweight
  `src.agent.financial_aggregate_projection`; focused tests cover order
  preservation, de-duplication, nested source-ref collection, ledger integrity
  input assembly, period-context evidence de-duplication, non-trace completion
  payload assembly, aggregate artifact payload assembly, non-empty override
  field application, feedback-driven task status selection, and selected claim
  id extension without importing the calculation mixin. The aggregate
  orchestration also dropped an unused `task_artifact_trace` local after static
  use analysis and routes the remaining projection/answer updates through the
  existing `_sync_state()` helper where possible instead of direct tuple
  replacement. `_AggregateMutableState.with_synthesis_state()` now centralizes
  whole synthesis-state replacement so the calculation mixin no longer reaches
  into the NamedTuple representation directly. `_AggregateSynthesisState.with_updates()`
  now owns field-wise synthesis updates as well, removing the remaining direct
  synthesis-state `_replace()` calls from the calculation mixin. The import
  side-effect test suite now also validates that the owner-foundation manifest
  import list, staging command, and staged-review command stay in sync, that
  review bucket file lists match their staging commands, and that heavyweight
  Pydantic/LangChain imports stay out of the additive owner foundation.
  Combined package import smoke reports `modules=116`, `failures=0`,
  `slow_ge_0_05=0`, `state_changes=0`. `src.api.financial_router` now keeps
  FastAPI router construction and API Pydantic schema creation behind
  `get_router()`/compatibility attribute access; direct import reports
  `financial_router_import_elapsed=0.021619`, `fastapi_loaded=False`,
  `pydantic_loaded=False`, while `main` still registers `/api/health`,
  `/api/companies`, `/api/ingest`, and `/api/query`. Follow-up calculation
  surface cleanup replaced duplicate lazy task-artifact/reflection projection
  wrappers in the planning, reconciliation, calculation mixins, runtime trace,
  calculation execution helper, and graph facade with direct lightweight alias
  imports; the touched runtime modules still import with `pydantic_loaded=False`
  and `langchain_core_loaded=False`. Operand-set artifact/task publication
  assembly now lives in `src.agent.financial_task_artifacts` as
  `operand_set_artifact_update()`; the calculation mixin keeps only the
  reconciliation-reference enrichment and state-specific parameter adapter.
  Calculation-plan artifact/task publication assembly now follows the same
  owner boundary through `calculation_plan_artifact_update()`, replacing the
  repeated deterministic/LLM formula-planner ledger blocks in the calculation
  mixin without changing plan construction or guards. Aggregate-answer and
  reflection-report publication assembly also moved behind
  `aggregate_answer_artifact_update()` and `reflection_report_artifact_update()`;
  aggregate supersession remains in the calculation mixin because it includes
  task-specific conflict checks and replacement-summary construction. The import
  side-effect test suite now explicitly guards `src.agent.financial_task_artifacts`
  against import-time Pydantic/LangChain loading so schema-backed record
  construction stays lazy. `financial_task_artifacts` caches its lazy
  `ArtifactRecord` and `TaskRecord` model resolution after first use, reducing
  repeated ledger-write overhead without moving schema imports back to module
  import time. Calculation-result artifact/task publication now also uses
  `calculation_result_artifact_update()`, removing direct ledger enum/upsert
  dependencies from `financial_calculation_execution.py`. Semantic-plan and
  reconciliation-result publication now also use
  `semantic_plan_artifact_update()` and `reconciliation_result_artifact_update()`,
  so planning and reconciliation no longer own direct ledger append/upsert or
  enum construction. Aggregate supersession conflict detection remains in the
  calculation mixin, but the final supersession artifact/task record write now
  uses `supersede_task_with_aggregate_result()`, leaving direct
  `append_artifact()`/`upsert_task()` writes centralized in
  `financial_task_artifacts`. The import side-effect suite now has a static
  regression guard that rejects direct public or private ledger primitive
  imports/calls from other `src.agent` modules. The calculation-task ledger
  helpers now share one private artifact/task publication helper inside
  `financial_task_artifacts`, so operand-set, calculation-plan, and
  calculation-result record assembly stay centralized without changing the
  public helper contracts. The low-level `_append_artifact()` and
  `_upsert_task()` primitives are no longer exported through `__all__`.
  Runtime-trace-only task lookup/artifact value helpers in
  `financial_task_artifacts` now also use private names, with
  `financial_runtime_trace.py` as the only direct caller. The remaining ledger
  normalization and artifact-payload extraction helpers are private, so
  `financial_task_artifacts.py` has no public-looking top-level function
  outside its caller-facing `__all__` surface; the import side-effect suite now
  checks that top-level public functions exactly match `__all__`.
  `project_task_artifact_trace()` now delegates task/artifact view projection
  and integrity issue assembly to private owner-internal helpers and is down
  from `279` to `78` lines.
  Shared lazy LangChain prompt/parser loader helpers now live in
  `src.agent.financial_langchain_loaders`, replacing repeated
  `ChatPromptTemplate`/`StrOutputParser` loader definitions in the calculation,
  evidence, planning, reconciliation, RAG, orchestrator, and researcher modules
  while preserving the import-time `langchain_core` boundary. Agent-runtime
  `Document` construction now also routes through that loader owner, leaving
  only TYPE_CHECKING direct `langchain_core.documents` imports outside it.
  Shared lazy structured-output model loaders now live in
  `src.agent.financial_graph_model_loaders`, replacing repeated one-line
  `financial_graph_models` loader definitions in the calculation, evidence,
  planning, reconciliation, runtime-trace, and answer-slot modules while
  preserving the import-time Pydantic boundary. Model resolution is cached after
  first use inside the loader owner. Answer-slot operation assembly in
  `src.agent.financial_answer_slots` now keeps component grouping, lookup
  primary slot construction, and current/prior period slot construction in
  private owner-internal helpers; `build_answer_slots()` stays the public
  contract and is down from `210` to `96` lines. Period-comparison detection,
  current/prior/delta slot assembly, and difference direction projection also
  live in private owner-internal helpers. Contextual ingest and benchmark
  contextual ingest now share contextual batch generation, response/fallback
  handling, index-payload construction, and usage metric collection helpers in
  `src.agent.financial_graph_contextual`; `benchmark_contextual_ingest()` is
  down from `115` to `80` lines. Aggregate-subtask calculation
  projection in `src.agent.financial_runtime_trace` now delegates per-subtask
  row projection, source id rollup, and nested answer-slot subtask payload
  construction to private owner-internal helpers; `_build_aggregate_calculation_projection()`
  is down from `159` to `59` lines. Dependency lookup-slot collection in
  `src.agent.financial_dependency_projection` now delegates operation
  normalization, producer-task synthesis, answer-numeric context filling, and
  per-result slot selection to private owner-internal helpers;
  `build_dependency_lookup_slots_by_task()` is down from `100` to `32` lines.
  Slot-based difference answer rendering in
  `src.agent.financial_graph_calculation_rendering` now delegates nested
  aggregate-subtask difference lookup, prefix construction, and template
  rendering to private owner-internal helpers; `compose_slot_based_difference_answer()`
  is down from `103` to `69` lines. Lookup value-refinement acceptance in
  `src.agent.financial_lookup_recovery` now delegates scope gating,
  structured-surface checks, table-label precision acceptance, and same-unit
  refinement checks to private owner-internal helpers;
  `lookup_recovery_value_refinement_allowed()` is down from `120` to `47` lines.
  Shared numeric-surface extraction in `src.agent.financial_numeric_surface`
  now delegates mixed-currency extraction, numeric pattern construction, and
  per-match candidate classification to private owner-internal helpers;
  `extract_numeric_surface_candidates()` is down from `101` to `28` lines.
  Numeric-after-operand extraction in `src.agent.financial_row_surfaces` now
  delegates parenthetical exact-value/unit handling and nearest prefix/suffix
  candidate collection to private owner-internal helpers;
  `_extract_numeric_value_after_operand_text()` is down from `107` to `16`
  lines. Lookup row realignment in `src.agent.financial_dependency_projection`
  now delegates required operand selection, projection candidate/source
  validation, and updated slot/result construction to private owner-internal
  helpers; `realign_lookup_row_from_dependency_projection()` is down from `138`
  to `66` lines. Ratio dependency fill in
  `src.agent.financial_dependency_projection` now delegates present-group
  detection, inferred denominator requirement synthesis, operand seed
  construction, source-slot recovery, table-evidence recovery, and source-value
  dedupe to private owner-internal helpers;
  `fill_missing_ratio_dependency_operands()` is down from `129` to `52` lines.
  Runtime
  `financial_graph_models` imports
  are now guarded so only `financial_graph_model_loaders.py` may load them
  outside TYPE_CHECKING blocks. Runtime LangChain prompt/parser/runnable/document
  imports are similarly guarded so only `financial_langchain_loaders.py` owns
  those direct runtime imports.
  Runtime domain-term audit passed with `215` reviewed literals;
  latest full unittest discovery: `1324` tests OK, `full_elapsed=15.033`;
  latest runtime trace/calculation execution focused gate reports `417` tests OK;
  latest graph/reconciliation/planning/import focused gate reports `730` tests OK;
  latest import/operand/aggregate focused gate reports `583` tests OK;
  latest graph/model focused gate reports `411` tests OK; latest API/import
  focused gate reports `63` tests OK; latest answer-slot/projection focused gate
  reports `216` tests OK; latest task-artifact/projection focused gate reports
  `456` tests OK; latest aggregate runtime-trace focused gate reports `423`
  tests OK; latest dependency/projection focused gate reports `550` tests OK;
  latest broader dependency projection focused gate reports `238` tests OK;
  latest rendering/operation focused gate reports `254` tests OK; latest broader
  rendering projection focused gate reports `384` tests OK; latest
  lookup/operation focused gate reports `260` tests OK; latest broader
  lookup/projection focused gate reports `400` tests OK; latest numeric-surface
  focused gate reports `550` tests OK; latest broader numeric projection focused
  gate reports `238` tests OK; latest row-surface focused gate reports `324`
  tests OK; latest broader row-surface projection/subtask gate reports `464`
  tests OK; latest dependency realignment focused gate reports `550` tests OK;
  latest broader dependency realignment projection gate reports `238` tests OK;
  latest ratio dependency focused gate reports `550` tests OK; latest broader
  ratio dependency projection gate reports `238` tests OK; latest answer-slot
  period focused gate reports `493` tests OK; latest broader answer-slot
  projection gate reports `238` tests OK; latest contextual ingest focused
  gate reports `86` tests OK; latest broader contextual ingest projection gate
  reports `169` tests OK; latest storage add-document focused gate reports
  `46` tests OK; latest broader storage ingest/eval gate reports `52` tests OK;
  latest package import smoke reports `modules=64`, `failures=0`,
  `slow_ge_0_05=0`; latest source-wide file import smoke over the current
  `src/**/*.py` set reports `modules=123`, `failures=0`, `slow_ge_0_05=0`;
  manifest coverage over changed source/docs reports
  `changed=134`, `missing=0`; `git diff --check` passed.

## 1. Runtime Projection

Scope: canonical runtime projection and legacy top-level calculation mirror
cleanup. Public export/replay compatibility stays at explicit projection
boundaries.

Files:

- `src/api/financial_router.py`
- `src/agent/financial_answer_slots.py`
- `src/agent/financial_calculation_execution.py`
- `src/agent/financial_graph.py`
- `src/agent/financial_graph_calculation_rendering.py`
- `src/agent/financial_graph_models.py`
- `src/agent/financial_graph_state.py`
- `src/agent/financial_reflection_projection.py`
- `src/ops/benchmark_runner.py`
- `src/ops/build_grounded_review_sheet.py`
- `src/ops/debug_math_workflow.py`
- `src/ops/debug_reference_note_workflow.py`
- `src/ops/evaluator.py`
- `src/ops/replay_full_eval_from_results.py`
- `src/ops/retrospective_evaluator_ablation_eval.py`
- `src/ops/retrospective_ontology_retrieval_eval.py`
- `src/ops/retrospective_operand_grounding_eval.py`
- `tests/test_evaluator_runtime_projection.py`
- `tests/test_financial_agent_run_projection.py`
- `tests/test_ops_runtime_projection_modes.py`
- `tests/test_report_scoped_cache_contract.py`

Minimum gates:

- `python3 -m unittest tests.test_evaluator_runtime_projection tests.test_financial_agent_run_projection tests.test_financial_router_response tests.test_ops_runtime_projection_modes tests.test_report_scoped_cache_contract`
- `python3 -m unittest discover -s tests`

Staging command:

```bash
git add \
  src/api/financial_router.py \
  src/agent/financial_answer_slots.py \
  src/agent/financial_calculation_execution.py \
  src/agent/financial_graph.py \
  src/agent/financial_graph_calculation_rendering.py \
  src/agent/financial_graph_models.py \
  src/agent/financial_graph_state.py \
  src/agent/financial_reflection_projection.py \
  src/ops/benchmark_runner.py \
  src/ops/build_grounded_review_sheet.py \
  src/ops/debug_math_workflow.py \
  src/ops/debug_reference_note_workflow.py \
  src/ops/evaluator.py \
  src/ops/replay_full_eval_from_results.py \
  src/ops/retrospective_evaluator_ablation_eval.py \
  src/ops/retrospective_ontology_retrieval_eval.py \
  src/ops/retrospective_operand_grounding_eval.py \
  tests/test_evaluator_runtime_projection.py \
  tests/test_financial_agent_run_projection.py \
  tests/test_ops_runtime_projection_modes.py \
  tests/test_report_scoped_cache_contract.py
```

## 2. Task Trace

Scope: task/artifact contract owner extraction, runtime trace owner extraction,
and MAS/ops/test import rewrites that consume those contracts directly.

Files:

- `src/agent/financial_artifact_contracts.py`
- `src/agent/financial_runtime_trace.py`
- `src/agent/financial_task_artifacts.py`
- `src/agent/mas_types.py`
- `src/agent/nodes/analyst_node.py`
- `src/agent/nodes/critic_node.py`
- `src/ops/mas_analyst_smoke.py`
- `src/ops/mas_direct_worker_probe.py`
- `src/ops/mas_researcher_smoke.py`
- `src/ops/portfolio_demo.py`
- `tests/test_aggregate_subtask_projection.py`
- `tests/test_critic_node.py`
- `tests/test_subtask_loop.py`

Minimum gates:

- `python3 -m unittest tests.test_aggregate_subtask_projection tests.test_critic_node tests.test_subtask_loop`
- `python3 -m src.ops.portfolio_review_gates`
- `python3 -m unittest discover -s tests`

Staging command:

```bash
git add \
  src/agent/financial_artifact_contracts.py \
  src/agent/financial_runtime_trace.py \
  src/agent/financial_task_artifacts.py \
  src/agent/mas_types.py \
  src/agent/nodes/analyst_node.py \
  src/agent/nodes/critic_node.py \
  src/ops/mas_analyst_smoke.py \
  src/ops/mas_direct_worker_probe.py \
  src/ops/mas_researcher_smoke.py \
  src/ops/portfolio_demo.py \
  tests/test_aggregate_subtask_projection.py \
  tests/test_critic_node.py \
  tests/test_subtask_loop.py
```

## 3. Primitive Owner

Scope: owner modules for runtime normalization, formula evaluation, lazy
structured-output model and LangChain loader boundaries, text and numeric
surfaces, row surfaces, structured-cell period helpers, surface contracts,
scope/operation policies, lookup recovery, dependency projection, retrieval
hints, and evidence-local prioritization.

Files:

- `src/agent/financial_dependency_projection.py`
- `src/agent/financial_formula_eval.py`
- `src/agent/financial_graph_model_loaders.py`
- `src/agent/financial_langchain_loaders.py`
- `src/agent/financial_aggregate_projection.py`
- `src/agent/financial_aggregate_state.py`
- `src/agent/financial_graph_calculation.py`
- `src/agent/financial_graph_evidence.py`
- `src/agent/financial_graph_helpers.py`
- `src/agent/financial_graph_planning.py`
- `src/agent/financial_graph_reconciliation.py`
- `src/agent/financial_graph_retrieval_budget.py`
- `src/agent/financial_lookup_recovery.py`
- `src/agent/financial_numeric_surface.py`
- `src/agent/financial_operation_policies.py`
- `src/agent/financial_retrieval_hints.py`
- `src/agent/financial_row_surfaces.py`
- `src/agent/financial_runtime_normalization.py`
- `src/agent/financial_scope_policies.py`
- `src/agent/financial_structured_cells.py`
- `src/agent/financial_surface_contracts.py`
- `src/agent/financial_text_surface.py`
- `src/ops/compare_concept_planner_shadow.py`
- `src/ops/compare_ontology_shadow.py`
- `tests/test_concept_runtime_contracts.py`
- `tests/test_financial_graph_helpers.py`
- `tests/test_math_parsing.py`
- `tests/test_operation_contracts.py`
- `tests/test_part_whole_ratio_contract.py`
- `tests/test_reconciliation_plan.py`
- `tests/test_retrieval_scope.py`
- `tests/test_semantic_numeric_plan.py`
- `tests/test_semantic_numeric_planner.py`
- `tests/test_structured_operand_extraction.py`

Minimum gates:

- `python3 -m src.ops.audit_runtime_domain_terms`
- `python3 -m unittest tests.test_financial_graph_helpers tests.test_semantic_numeric_plan tests.test_semantic_numeric_planner tests.test_reconciliation_plan tests.test_operation_contracts tests.test_part_whole_ratio_contract tests.test_concept_runtime_contracts tests.test_structured_operand_extraction`
- `python3 -m unittest discover -s tests`

Staging command:

```bash
git add \
  src/agent/financial_dependency_projection.py \
  src/agent/financial_formula_eval.py \
  src/agent/financial_graph_model_loaders.py \
  src/agent/financial_langchain_loaders.py \
  src/agent/financial_aggregate_projection.py \
  src/agent/financial_aggregate_state.py \
  src/agent/financial_graph_calculation.py \
  src/agent/financial_graph_evidence.py \
  src/agent/financial_graph_helpers.py \
  src/agent/financial_graph_planning.py \
  src/agent/financial_graph_reconciliation.py \
  src/agent/financial_graph_retrieval_budget.py \
  src/agent/financial_lookup_recovery.py \
  src/agent/financial_numeric_surface.py \
  src/agent/financial_operation_policies.py \
  src/agent/financial_retrieval_hints.py \
  src/agent/financial_row_surfaces.py \
  src/agent/financial_runtime_normalization.py \
  src/agent/financial_scope_policies.py \
  src/agent/financial_structured_cells.py \
  src/agent/financial_surface_contracts.py \
  src/agent/financial_text_surface.py \
  src/ops/compare_concept_planner_shadow.py \
  src/ops/compare_ontology_shadow.py \
  tests/test_concept_runtime_contracts.py \
  tests/test_financial_graph_helpers.py \
  tests/test_math_parsing.py \
  tests/test_operation_contracts.py \
  tests/test_part_whole_ratio_contract.py \
  tests/test_reconciliation_plan.py \
  tests/test_retrieval_scope.py \
  tests/test_semantic_numeric_plan.py \
  tests/test_semantic_numeric_planner.py \
  tests/test_structured_operand_extraction.py
```

## 4. Docs Audit

Scope: architecture/status/walkthrough documentation and runtime domain-term
audit baseline updates that correspond to file ownership changes.

Files:

- `README.md`
- `docs/architecture/agent_runtime_contract.md`
- `docs/architecture/core_runtime_surface_refactoring_plan.md`
- `docs/architecture/current_runtime_cleanup_split_manifest.md`
- `docs/architecture/internal_calculation_mirror_cleanup.md`
- `docs/overview/portfolio_one_pager.md`
- `docs/overview/project_status.md`
- `docs/overview/question_trace_walkthrough.md`
- `docs/overview/runtime_flow_roles.md`
- `docs/planning/backlog_and_next_epics.md`
- `tests/fixtures/runtime_domain_terms_baseline.json`

Minimum gates:

- `git diff --check`
- `python3 -m src.ops.audit_runtime_domain_terms`
- `git status --short` artifact hygiene check

Staging command:

```bash
git add \
  README.md \
  docs/architecture/agent_runtime_contract.md \
  docs/architecture/core_runtime_surface_refactoring_plan.md \
  docs/architecture/current_runtime_cleanup_split_manifest.md \
  docs/architecture/internal_calculation_mirror_cleanup.md \
  docs/overview/portfolio_one_pager.md \
  docs/overview/project_status.md \
  docs/overview/question_trace_walkthrough.md \
  docs/overview/runtime_flow_roles.md \
  docs/planning/backlog_and_next_epics.md \
  tests/fixtures/runtime_domain_terms_baseline.json
```

## Artifact Hygiene

Before staging each split, verify that no files under these paths are staged
unless explicitly requested:

- `benchmarks/results/**`
- local vector stores or caches
- temporary benchmark profiles
- one-off datasets

The current dry-run had `ambiguous=0`; if that changes, update this manifest
before splitting.
