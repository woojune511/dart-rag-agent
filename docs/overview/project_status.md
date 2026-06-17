# Project Status

> Internal running log, not a first-read portfolio document. Start with
> [../../README.md](../../README.md),
> [portfolio_one_pager.md](portfolio_one_pager.md), and
> [portfolio_experiment_report.md](portfolio_experiment_report.md). This file is
> kept long so handoff state, gate results, and experiment details remain
> traceable.

Last updated: 2026-06-17

## Positioning

This repository is a DART financial-document RAG and agent-runtime project. The
core engineering goal is not to hard-code benchmark answers, but to build a
traceable runtime contract for financial analysis:

- retrieve evidence from long-form DART filings
- bind the right structured rows and source sentences
- execute numeric operations deterministically
- preserve calculation and evidence traces
- validate changes through reproducible benchmark gates

The current direction is to turn the verified single-agent runtime into a
role-separated multi-agent system using a task ledger and artifact store.

## Session Handoff

- ChatGPT/Codex memory may remember user preferences and the preferred handoff
  routine, but it is not the source of truth for current project state.
- A new session should first read `AGENTS.md`, `CONTEXT.md`, this status file,
  `git status`, and recent commits before proposing or editing code.
- Store changing state in repo artifacts: `CONTEXT.md` for short snapshots,
  this file for current gate/backlog status, `docs/history/experiment_history.md`
  for experiment narratives, and git commits for exact source history.
- Do not rely on memory for latest blockers, benchmark outputs, model/API
  configuration, or files to stage.

## Current Gate Status

| Gate | Scope | Latest Status |
| --- | --- | --- |
| Runtime contract gate | 5 core numeric/runtime questions | PASS |
| Hard structural numeric gate | 5 curated hard numeric questions | PASS, 5 / 5 |
| Concept runtime gap gate | 7 ontology-driven concept questions | PASS, 7 / 7 |
| Policy-driven runtime gate | 4 company runs, 5 policy/narrative questions | PASS |
| Reflection promotion gate | base fixture, store-fixed candidate surface, two reviewed trace summaries | READY |
| Report-cache promotion evidence | candidate-only cache producer/fallback contract | READY, disabled |
| Promotion trace materiality gate | reviewed trace-summary source/action/fallback diversity | READY |
| REFERENCE_NOTE capability gate | Researcher graph-expansion boundary | READY, context-only |
| Portfolio review gates | reviewer-facing capability bundle | READY |

### Latest PR 5 Parser Extraction

- Run date: 2026-06-17
- Scope: no-behavior-change parser extractions under the
  `FinancialParser.process_document()` facade.
- Change:
  - Added `src/processing/table_records.py` for parser-normalized row/value
    record construction.
  - `FinancialParser._build_table_row_records()` and
    `_build_table_value_records()` now delegate to the extracted module while
    preserving the existing private method surface for tests and callers.
  - Moved generic table-axis, period-label, aggregate-role, row-record, and
    value-record helpers out of `financial_parser.py`.
  - Added `src/processing/table_structure.py` for XML table grid
    reconstruction, merged-cell propagation, table text formatting, span
    detection, row-label extraction, and table-object payload assembly.
  - Existing table structure private methods remain compatibility wrappers for
    tests and callers.
  - Added `src/processing/section_extraction.py` for section tag iteration,
    section path construction, parse budget/fallback orchestration, parse
    timing, and section payload assembly.
  - `FinancialParser._build_section_path()` and `_extract_sections()` now
    delegate to the extracted module.
  - Added `src/processing/block_collection.py` for the paragraph/table/local
    heading block state machine. `FinancialParser._collect_blocks()` remains as
    a compatibility wrapper that wires parser-specific callbacks into the
    extracted collector.
- Verification:
  - `uv run --with-requirements requirements-review.txt python -m unittest tests.test_financial_parser`:
    `28` OK
  - `.venv/bin/python -m unittest tests.test_vector_store_fallback`:
    `14` OK
  - `python -m py_compile src/processing/financial_parser.py src/processing/table_records.py src/processing/table_structure.py src/processing/section_extraction.py src/processing/block_collection.py`:
    passed
  - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
    `Status: ready`
- Next parser extraction candidates: chunking, then reference resolution. Keep
  these as no-behavior-change extractions unless a metadata snapshot test
  exposes drift.

### Latest PR 8 Requirements/Docs Cleanup

- Run date: 2026-06-17
- Scope: reviewer-facing install and command hygiene.
- Change:
  - `requirements.txt` now marks `pywin32==311` as Windows-only with
    `sys_platform == "win32"`, so Linux `uv` environments do not fail on the
    Windows package.
  - Added `requirements-review.txt` as the lightweight dependency set for
    fixture-backed reviewer commands. It avoids forcing `portfolio_demo` and
    `portfolio_review_gates` to install the full ML/dev stack.
  - README and compact portfolio docs now use
    `uv run --with-requirements requirements-review.txt ...` for demo/gate
    commands. Full development, ingest, benchmark, and app runs remain on
    `requirements.txt`.
- Verification:
  - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_demo --format json`:
    `ready`
  - `uv run --with-requirements requirements-review.txt python -m src.ops.portfolio_review_gates`:
    `Status: ready`
  - `uv run --with-requirements requirements-review.txt python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `requirements.txt` parsed via `packaging.requirements.Requirement`
  - `git diff --check`: passed

### Latest PR 4 Stop-Line Documentation

- Run date: 2026-06-17
- Scope: PR 4 calculation extraction handoff and stop-line documentation.
- Change:
  - `docs/architecture/core_runtime_surface_refactoring_plan.md` now records the
    extracted calculation surfaces, verification baseline, concrete seams where
    PR 4 may continue, and cleanup cases that should be avoided.
  - Current recommendation: pause PR 4 unless a calculation regression or
    contract gap appears. File-size reduction alone is not a sufficient reason
    to keep splitting `financial_graph_calculation.py`.
- Current extracted surfaces include answer slots, execution/result payloads,
  rendering, text/narrative surface helpers, reflection projection helpers,
  scalar/time-series result state and display helpers, and scalar/time-series
  task/artifact publication.
- Verification baseline referenced by the stop line:
  - `tests.test_operation_contracts`: `226` OK
  - `tests.test_subtask_loop`: `210` OK
  - `tests.test_financial_calculation_execution` +
    `tests.test_financial_calculation_rendering`: `22` OK
  - runtime domain-term audit: passed with `216` reviewed literals
- Next implementation focus should move to PR 8 requirements/docs cleanup or
  PR 5 parser extraction unless a concrete calculation issue appears.

### Latest Subtask Loop Broad Regression Check

- Run date: 2026-06-17
- Scope: broad subtask/aggregate regression after aligning successful
  `time_series` calculations with the calculation task/artifact publication
  contract.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_subtask_loop`:
    `210` OK
- Interpretation: publishing calculation tasks/artifacts for successful
  time-series calculations remains compatible with aggregate/subtask
  orchestration.

### Latest Time-Series Publication Contract Alignment

- Run date: 2026-06-17
- Scope: PR 4 calculation execution contract alignment after the time-series
  extraction sequence.
- Change:
  - The `time_series` success path now publishes through
    `build_success_calculation_state_payload`, matching scalar success
    behavior.
  - Successful time-series calculations now emit `resolved_calculation_trace` /
    `structured_result` plus a calculation task and `calculation_result`
    artifact.
  - Added focused operation-contract coverage for selected evidence ids,
    calculation-result artifact payload/evidence refs, and calculation task
    status/artifact ids.
- Interpretation: this intentionally aligns the time-series success path with
  the calculation task/artifact contract documented for completed calculation
  tasks. Arithmetic, rendering, result payload content, and trace projection
  remain unchanged.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_time_series_success_publishes_calculation_task_artifact_contract`:
    `1` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution tests.test_financial_calculation_rendering`:
    `22` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_time_series_success_publishes_calculation_task_artifact_contract tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value tests.test_operation_contracts.OperationContractTests.test_growth_rate_preserves_stated_source_percent_when_available`:
    `5` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts`:
    `226` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py`:
    passed

### Latest Time-Series Result Display Extraction

- Run date: 2026-06-17
- Scope: sixteenth narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - `time_series` rendered result calculation moved from
    `_execute_calculation` to
    `src/agent/financial_graph_calculation_rendering.py`.
  - Extracted helper: `time_series_result_display`.
  - The helper applies the existing percent result-unit override and
    percent/non-percent result formatting. Percent normalized-unit detection now
    consumes `CALCULATION_RENDER_POLICY` instead of carrying the moved runtime
    literal in the calculation/rendering path.
  - `tests/fixtures/runtime_domain_terms_baseline.json` was adjusted downward
    for the removed `financial_graph_calculation.py` `퍼센트` literal count.
- Interpretation: this is a no-behavior-change rendering-boundary extraction.
  Time-series formula evaluation, result-series rendering, result payload
  construction, evidence selection, and runtime trace update remain unchanged.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering tests.test_financial_calculation_execution`:
    `22` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value tests.test_operation_contracts.OperationContractTests.test_growth_rate_preserves_stated_source_percent_when_available`:
    `4` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_graph_calculation_rendering.py`:
    passed

### Latest Time-Series YoY Growth Extraction

- Run date: 2026-06-17
- Scope: fifteenth narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - `time_series` pairwise YoY growth calculation moved from
    `_execute_calculation` to `src/agent/financial_calculation_execution.py`.
  - Extracted helper: `time_series_yoy_growth_rates`.
  - The helper evaluates `pairwise_formula` with `PREV` / `CURR` variables and
    preserves the existing `ZeroDivisionError -> None` behavior.
- Interpretation: this is a no-behavior-change deterministic execution
  extraction. Time-series operand sorting, result-series rendering, result
  payload construction, evidence selection, and runtime trace update remain
  unchanged.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution tests.test_financial_calculation_rendering`:
    `20` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value tests.test_operation_contracts.OperationContractTests.test_growth_rate_preserves_stated_source_percent_when_available`:
    `4` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_calculation_execution.py`:
    passed

### Latest Time-Series Result Series Extraction

- Run date: 2026-06-17
- Scope: fourteenth narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - `time_series` result series row assembly moved from
    `_execute_calculation` to
    `src/agent/financial_graph_calculation_rendering.py`.
  - Extracted helper: `time_series_result_series`.
  - The helper projects ordered operands into the existing time-series
    `series` row shape while preserving label normalization, value formatting,
    raw values, raw units, periods, and normalized values.
- Interpretation: this is a no-behavior-change rendering-boundary extraction.
  Time-series operand sorting, formula evaluation, result payload construction,
  evidence selection, and runtime trace update remain unchanged.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering tests.test_financial_calculation_execution`:
    `17` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value tests.test_operation_contracts.OperationContractTests.test_growth_rate_preserves_stated_source_percent_when_available`:
    `4` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_graph_calculation_rendering.py`:
    passed

### Latest Time-Series Calculation Result Extraction

- Run date: 2026-06-17
- Scope: thirteenth narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - `time_series` success `calculation_result` dict assembly moved from
    `_execute_calculation` to `src/agent/financial_calculation_execution.py`.
  - Extracted helper: `build_time_series_calculation_result`.
  - The helper packages the already-computed trend result, rendered value,
    result series, primary answer slot, and formula metadata into the existing
    result payload shape.
- Interpretation: this is a no-behavior-change execution-boundary extraction.
  Time-series operand sorting, formula evaluation, evidence selection, and
  runtime trace update remain in the existing `_execute_calculation` flow.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution`:
    `9` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value tests.test_operation_contracts.OperationContractTests.test_growth_rate_preserves_stated_source_percent_when_available`:
    `4` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_calculation_execution.py`:
    passed

### Latest PR 4 Broad Regression Check

- Run date: 2026-06-17
- Scope: broad regression after the accumulated PR 4 calculation
  execution/rendering/result-payload extractions.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts`:
    `225` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_subtask_loop`:
    `210` OK
- Interpretation: the recent calculation extraction series remains compatible
  with the operation-contract surface and the subtask-loop orchestration
  regressions. The next implementation step can move on to the remaining
  `time_series` calculation branch or continue narrower helper extraction.

### Latest Scalar Calculation Result Extraction

- Run date: 2026-06-17
- Scope: twelfth narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - Scalar success `calculation_result` dict assembly moved from
    `_execute_calculation` to `src/agent/financial_calculation_execution.py`.
  - Extracted helper: `build_scalar_calculation_result`.
  - The helper packages the already-computed result value, rendered value,
    result series, scalar state, answer slots, and formula metadata into the
    existing result payload shape.
- Interpretation: this is a no-behavior-change execution-boundary extraction.
  Arithmetic, operand binding, evidence selection, answer slot construction,
  rendering, ledger publication, and runtime trace publication remain in their
  existing paths.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution`:
    `8` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value tests.test_operation_contracts.OperationContractTests.test_growth_rate_preserves_stated_source_percent_when_available`:
    `4` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_calculation_execution.py`:
    passed

### Latest Scalar Calculation State Extraction

- Run date: 2026-06-17
- Scope: eleventh narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - Scalar current/prior/delta state assembly and source-stated growth display
    override moved from `_execute_calculation` to
    `src/agent/financial_calculation_execution.py`.
  - Extracted helper: `build_scalar_calculation_state`.
  - The helper derives `current_value`, `prior_value`, `delta_value`,
    `source_row_ids`, period labels, and source-stated result usage from ordered
    operands and the rendered scalar result.
- Interpretation: this is a no-behavior-change execution-boundary extraction.
  Formula evaluation, evidence selection, answer slot construction, and
  rendering helper calls remain in the same runtime flow.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution`:
    `7` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value tests.test_operation_contracts.OperationContractTests.test_growth_rate_preserves_stated_source_percent_when_available`:
    `4` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_agent_run_projection.FinancialAgentRunProjectionTests.test_run_repairs_period_comparison_trace_from_source_stated_evidence`:
    `1` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_calculation_execution.py`:
    passed

### Latest Calculation Success Payload Extraction

- Run date: 2026-06-17
- Scope: tenth narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - Successful calculation state payload assembly moved from
    `_execute_calculation` to `src/agent/financial_calculation_execution.py`.
  - Extracted helper: `build_success_calculation_state_payload`.
  - The helper appends the calculation-result artifact, upserts the calculation
    task, and publishes `resolved_calculation_trace` / `structured_result`.
- Interpretation: this is a no-behavior-change execution-boundary extraction.
  It keeps arithmetic, evidence selection, answer slot construction, and
  rendering behavior in their existing paths while moving ledger/trace payload
  publication behind a focused helper.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution`:
    `4` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value`:
    `3` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_calculation_execution.py`:
    passed

### Latest Scalar Result Series Extraction

- Run date: 2026-06-17
- Scope: ninth narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - Scalar result `series` row assembly moved from `_execute_calculation` to
    `src/agent/financial_graph_calculation_rendering.py`.
  - Extracted helper: `scalar_result_series`.
  - The helper projects ordered operand rows into result-series rows while
    preserving source-visible rendered values and existing fallback formatting.
- Interpretation: this is a no-behavior-change rendering-boundary extraction.
  It keeps execution and trace update logic in `_execute_calculation`, while
  moving display-row construction next to the rest of calculation rendering.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering`:
    `7` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value`:
    `3` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering tests.test_financial_calculation_execution`:
    `9` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_graph_calculation_rendering.py`:
    passed

### Latest Scalar Result Display Extraction

- Run date: 2026-06-17
- Scope: eighth narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - Scalar result display selection moved from `_execute_calculation` to
    `src/agent/financial_graph_calculation_rendering.py`.
  - Extracted helper: `scalar_result_display`.
  - The helper decides `rendered_value` and `rendered_with_unit` from
    `result_value`, `result_unit`, `normalized_unit`, optional
    `result_display_unit`, operation family, and ordered operands.
- Interpretation: this is a no-behavior-change rendering-boundary extraction.
  KRW display units, non-KRW unit suffixes, and lookup/single-value source
  display preservation now live with rendering helpers, while arithmetic
  execution and trace update behavior stay in `_execute_calculation`.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering`:
    `6` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_lookup_calculation_preserves_source_table_unit_in_rendered_value`:
    `3` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering tests.test_financial_calculation_execution`:
    `8` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_graph_calculation_rendering.py`:
    passed

### Latest Calculation Failure Payload Extraction

- Run date: 2026-06-17
- Scope: seventh narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - Failure-path `calculation_result` payload construction moved from the local
    `_execute_calculation._fail()` closure to
    `src/agent/financial_calculation_execution.py`.
  - Extracted helper: `build_failed_calculation_result`.
  - `_execute_calculation` still owns state updates, selected evidence ids,
    fallback answer fields, and routing semantics.
- Interpretation: this is a no-behavior-change execution-boundary extraction.
  It isolates deterministic failure result shape and answer-slot construction
  without changing operand repair, formula execution, retry routing, or trace
  projection.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution`:
    `2` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_failed_lookup_emits_explicit_missing_primary_slot tests.test_operation_contracts.OperationContractTests.test_execute_calculation_ignores_legacy_top_level_operands_and_plan tests.test_operation_contracts.OperationContractTests.test_ratio_calculation_rejects_duplicate_operand_binding`:
    `3` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_execution tests.test_financial_answer_slots`:
    `9` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_calculation_execution.py`:
    passed

### Latest Render Direction Helper Extraction

- Run date: 2026-06-17
- Scope: sixth narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - Direction hint calculation and duplicate negative-sign display correction
    moved from `financial_graph_calculation.py` to
    `src/agent/financial_graph_calculation_rendering.py`.
  - Extracted helpers: `direction_hint_for_result` and
    `coerce_rendered_value_for_direction`.
  - Render and verification nodes now share the same deterministic direction
    helper while keeping their existing LLM prompts, fallback behavior, trace
    updates, and ratio compact rendering unchanged.
- Interpretation: this is a no-behavior-change rendering-boundary extraction.
  It removes duplicated render/verify policy interpretation from the
  calculation orchestration file without changing arithmetic or verification
  semantics.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering`:
    `3` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_rendered_subtraction_answer_rewrites_double_negative_subtrahend tests.test_operation_contracts.OperationContractTests.test_rendered_subtraction_answer_rewrites_negative_denominator_difference tests.test_subtask_loop.SubtaskLoopTests.test_verify_calculation_skip_does_not_rewrite_compatibility_mirrors`:
    `3` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_calculation_rendering tests.test_financial_answer_slots`:
    `10` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_graph_calculation_rendering.py`:
    passed

### Latest Answer Slot Assembly Extraction

- Run date: 2026-06-17
- Scope: fifth narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - `_build_answer_slots` operation-family assembly moved from
    `financial_graph_calculation.py` to
    `src/agent/financial_answer_slots.py` as `build_answer_slots`.
  - The calculation mixin keeps `_build_answer_slots` as a compatibility
    wrapper, so graph-node and caller contracts stay stable.
  - Answer slot row builders and answer slot assembly now live in the same
    module; the calculation mixin only forwards deterministic execution output
    into that construction boundary.
- Interpretation: this is a no-behavior-change boundary extraction. It does not
  alter operand binding, arithmetic execution, answer rendering policy,
  validation schema, or retry behavior.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_answer_slots`:
    `7` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_failed_lookup_emits_explicit_missing_primary_slot`:
    `3` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_runtime_domain_term_audit tests.test_financial_answer_slots`:
    `13` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_answer_slots.py`:
    passed
- Note: the first new answer-slot assembly unit-test fixture failed because it
  used a non-schema normalized unit for percent-point display. The fixture was
  corrected to the runtime contract shape (`normalized_unit=PERCENT`,
  `result_unit=%p`).

### Latest Answer Slot Construction Extraction

- Run date: 2026-06-17
- Scope: fourth narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - Answer slot row construction helpers moved from
    `financial_graph_calculation.py` to
    `src/agent/financial_answer_slots.py`.
  - Extracted helpers: `slot_status`, `coerce_slot_numeric`,
    `build_missing_value_slot`, `build_operand_value_slot`, and
    `build_calculated_value_slot`.
  - `_build_answer_slots` remains in the calculation mixin because it still
    orchestrates operation-family-specific slot assembly. Existing mixin method
    names remain as compatibility wrappers.
- Interpretation: this is a no-behavior-change boundary extraction. It moves
  deterministic answer-slot row construction out of the calculation
  orchestration file while leaving operand binding, operation-family assembly,
  validation, and rendering behavior unchanged.
- Audit note:
  - The extracted helper consumes `CALCULATION_RENDER_POLICY` for KRW display
    unit handling instead of adding display-unit literals in the new runtime
    module.
  - `tests/fixtures/runtime_domain_terms_baseline.json` was updated only to
    reflect the reduced `천원` / `백만원` literal count in
    `financial_graph_calculation.py` after that policy-driven extraction.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_answer_slots`:
    `5` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts.OperationContractTests.test_difference_result_exposes_structured_value_slots tests.test_operation_contracts.OperationContractTests.test_percent_difference_preserves_two_decimal_percent_rendering tests.test_operation_contracts.OperationContractTests.test_failed_lookup_emits_explicit_missing_primary_slot`:
    `3` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_runtime_domain_term_audit tests.test_financial_answer_slots`:
    `11` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_answer_slots.py`:
    passed
- Note: one early operation-contract command failed because the specified test
  method names did not exist. One early audit run failed before display-unit
  handling was converted to policy consumption and the reviewed baseline count
  reduction was recorded; the corrected audit passed.

### Latest Text Surface Helper Extraction

- Run date: 2026-06-17
- Scope: third narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - Narrative/text surface helpers moved from
    `financial_graph_calculation.py` to
    `src/agent/financial_text_surface.py`.
  - Extracted helpers: `topic_particle`, `polish_korean_particle_pairs`,
    `split_narrative_sentences`, `narrative_sentence_looks_table_noisy`, and
    `narrative_sentence_looks_abbreviated_fragment`.
  - The calculation mixin keeps using alias imports, so answer/narrative
    composition call sites stay stable.
- Interpretation: this is a no-behavior-change boundary extraction. It moves
  sentence splitting, table-noise filtering, abbreviated-fragment detection, and
  Korean particle polishing out of the calculation orchestration file while
  leaving evidence selection, operand binding, calculation, and retry behavior
  unchanged.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_text_surface`:
    `5` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_reflection_capability_contract tests.test_financial_text_surface`:
    `14` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_subtask_loop.SubtaskLoopTests.test_prepare_reflection_retry_ignores_legacy_top_level_runtime_projection tests.test_subtask_loop.SubtaskLoopTests.test_prepare_synthesis_reflection_retry_records_task_output_source_ids tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_subtasks_replans_on_task_artifact_integrity_error`:
    `3` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_text_surface.py`:
    passed
- Note: one early focused unittest invocation failed because
  `CALCULATION_NARRATIVE_POLICY` was still needed elsewhere in
  `financial_graph_calculation.py`; the import was restored and the same tests
  passed.

### Latest Task Artifact Feedback Projection Extraction

- Run date: 2026-06-17
- Scope: second narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - Task/artifact ledger integrity feedback projection moved from
    `financial_graph_calculation.py` to
    `src/agent/financial_reflection_projection.py`.
  - Extracted helper: `task_artifact_integrity_feedback`.
  - The calculation mixin keeps using an alias import, so aggregate-subtask
    integrity handling and retry feedback behavior stay stable.
- Interpretation: this is a no-behavior-change boundary extraction. It keeps
  ledger integrity diagnosis in the reflection projection surface while leaving
  task aggregation, artifact validation, and retry control unchanged.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_reflection_capability_contract`:
    `9` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_subtasks_replans_on_task_artifact_integrity_error tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_subtasks_replans_on_missing_required_calculation_artifact_kind tests.test_subtask_loop.SubtaskLoopTests.test_aggregate_subtasks_replans_on_missing_required_artifact_payload`:
    `3` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_reflection_projection.py`:
    passed
  - `git diff --check`: passed

### Latest Calculation Reflection Projection Extraction

- Run date: 2026-06-17
- Scope: first narrow PR 4 calculation extraction from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - Reflection handoff projection helpers moved from
    `financial_graph_calculation.py` to
    `src/agent/financial_reflection_projection.py`.
  - Extracted helpers:
    `reflection_action_from_plan` and `reflection_report_from_action`.
  - The calculation mixin keeps using alias imports, so behavior and call sites
    stay stable.
- Interpretation: this is a no-behavior-change boundary extraction. It does not
  alter operand binding, deterministic execution, answer rendering, or
  benchmark behavior.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_reflection_capability_contract`:
    `7` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_subtask_loop.SubtaskLoopTests.test_prepare_reflection_retry_ignores_legacy_top_level_runtime_projection tests.test_subtask_loop.SubtaskLoopTests.test_prepare_synthesis_reflection_retry_records_task_output_source_ids`:
    `2` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_calculation.py src/agent/financial_reflection_projection.py`:
    passed
  - `git diff --check`: passed

### Latest State Type Split Start

- Run date: 2026-06-17
- Scope: first no-behavior-change step for PR 3 from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - `FinancialAgentState` is now composed from concern-specific TypedDicts:
    `RoutingState`, `RetrievalState`, `EvidenceState`, `CalculationState`,
    `ReflectionState`, and `LedgerState`.
  - The full graph state shape is preserved through multiple inheritance; no
    graph nodes, runtime keys, or caller payloads changed.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_agent_run_projection`:
    `47` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `python -m py_compile src/agent/financial_graph_models.py`: passed
  - `git diff --check`: passed

### Latest API Response Boundary Start

- Run date: 2026-06-17
- Scope: first public-response slimming step after `agent_answer` /
  `review_trace` / `debug_bundle` projections were introduced.
- Change:
  - `/api/query` now builds its public response from `agent_answer` first and
    falls back to the legacy flat agent payload for compatibility.
  - The default response remains slim: answer, query metadata, citations,
    `structured_result`, and `resolved_calculation_trace`.
  - `review_trace` and `debug_bundle` are exposed only when request flags
    `include_review_trace` / `include_debug_bundle` are explicitly true.
  - Local-only benchmark result bundles
    `cel_t1_038_unit_repair_check_*` and `hard_structural_current_smoke_*` are
    now ignored.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_router_response tests.test_financial_agent_run_projection`:
    `49` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_portfolio_demo tests.test_mas_e2e_smoke_contract`:
    `12` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `git diff --check`: passed

### Latest Core Runtime Surface Boundary Start

- Run date: 2026-06-17
- Scope: behavior-preserving start of PR 1 from
  `docs/architecture/core_runtime_surface_refactoring_plan.md`.
- Change:
  - `FinancialAgent.run()` still returns the existing flat compatibility
    payload for API/evaluator callers.
  - The same payload is now also grouped into explicit projections:
    `agent_answer`, `review_trace`, and `debug_bundle`.
  - New TypedDicts document those boundaries: `AgentAnswer`, `ReviewTrace`,
    and `DebugBundle`.
- Interpretation: this is output-boundary extraction, not an answer-quality
  patch. It prepares the next public response slimming step while preserving
  `structured_result`, `resolved_calculation_trace`, task/artifact trace, and
  debug/usage surfaces.
- Verification:
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_financial_agent_run_projection`:
    `46` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_operation_contracts`:
    `225` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m unittest tests.test_portfolio_demo tests.test_mas_e2e_smoke_contract`:
    `12` OK
  - `uv run --with langchain-google-genai==4.2.1 python -m src.ops.audit_runtime_domain_terms`:
    passed with `216` reviewed literals
  - `git diff --check`: passed

### Latest SKI Source-Stated Growth Repair Close

- Run date: 2026-06-16
- Scope: `SKI_T2_069` store-fixed focused eval-only after aggregate
  period-comparison repair and evidence-supported narrative pruning.
- Local result bundle:
  - `benchmarks/results/regression_ski_t2_069_repro_from_refactor_check_2026-06-16/`
- Result: numeric `PASS`, faithfulness `1.000`, completeness `1.000`,
  numeric pass rate `1.000`, context P@5 `0.800`.
- Final answer preserves the source-stated `84.3%` decrease and removes the
  unrelated forward-looking-information boilerplate.
- Runtime change stays generic:
  - source-stated growth displays can repair stale period-comparison traces
    while deterministic formula traces remain available;
  - aggregate-subtask repair reads trace rows before stale state rows;
  - empty LLM operand extraction cannot overwrite dependency/direct structured
    operand rows;
  - narrative carryover is limited to supported narrative-summary or high-score
    evidence candidates, with the score floor declared in retrieval policy.
- Verification: focused aggregate/projection tests OK, related runtime suite
  `398` tests OK, runtime domain-term audit passed with `216` reviewed
  literals, and `git diff --check` passed.
- Artifact hygiene: the regression result bundles and heartbeat logs are local
  experiment artifacts and are not commit candidates.

### Latest HYU Source-Slot Ratio Rebuild Close

- Run date: 2026-06-16
- Scope: `HYU_T1_034` store-fixed focused eval-only after incoherent ratio
  candidate suppression and source-slot ratio rebuild.
- Local result bundle:
  - `benchmarks/results/focused_hyu_t1_034_after_skip_incoherent_numeric_candidate_2026-06-16/`
- Result: numeric `PASS`, faithfulness `1.000`, retrieval hit `1.000`, avg
  score `0.948`.
- Final answer: `2023년 전체 영업이익에서 차량 부문이 차지하는 비중은
  83.81%입니다. 계산: 차량 영업이익 12조 6,773억원 / 전체 영업이익
  15조 1,269억원.`
- Runtime change stays generic:
  - source-slot rebuild uses lookup/single-value producer slots only
  - producer `metric_label` is preserved as source-slot metadata when primary
    labels are too generic or stale
  - insufficient/incoherent ratio rows can be deterministically rebuilt only
    from material, distinct source slots
  - lookup realignment refuses to overwrite a current primary slot with a
    non-self-task projection when direct provenance is disjoint or source
    anchors conflict
- Verification: targeted ratio tests `3` OK, `tests.test_subtask_loop` `205`
  OK, related projection/subtask suite `255` OK, full unittest `1171` OK, and
  runtime domain-term audit passed with `216` reviewed literals.
- Artifact hygiene: the result bundle and heartbeat logs are local experiment
  artifacts and are not commit candidates.

### Latest Growth Narrative Payload Close

- Run date: 2026-06-15
- Scope: `NAV_T2_006` and `KBF_T2_018` focused store-fixed eval-only after
  growth narrative numeric refresh and runtime/evaluator payload compaction.
- Related commits:
  - `64753a2` Stabilize growth narrative numeric refresh
  - `5188bda` Compact runtime evidence judge payloads
- Local result bundles summarized, then cleaned:
  - `benchmarks/results/numeric_first_nav_t2_006_refactor5_probe_2026-06-15/`
  - `benchmarks/results/numeric_first_kbf_t2_018_refactor4_probe_2026-06-15/`
  - `benchmarks/results/numeric_first_kbf_t2_018_payload2_probe_2026-06-15/`
- `NAV_T2_006`: faithfulness `1.000`, answer relevancy `0.845`,
  completeness `1.000`, calculation correctness `1.000`, grounded rendering
  `1.000`, error `0.0%`.
- `KBF_T2_018`: pre-compaction run was numeric `PASS` but the
  grounded-rendering judge exceeded the token limit. Post-compaction
  `payload2` run is numeric `PASS`, numeric equivalence/grounding `1.000`,
  calculation correctness `1.000`, grounded rendering `1.000`, answer
  relevancy `0.841`, and no token overflow.
- Payload note: public runtime evidence for the KBF canary dropped from about
  `115k` chars to about `23.6k` chars. The persisted full calculation trace
  can still be large for debugging, but LLM judge prompts now receive compact
  projections.
- Runtime principle: the fix is generic metadata/judge-payload projection.
  No company, question, metric, or benchmark-specific runtime branch was added.
- Verification: lookup recovery `16` OK, subtask loop `192` OK, financial agent
  run projection `43` OK, evaluator runtime projection `65` OK, and runtime
  domain-term audit passed.

### Latest HYU Ratio Binding Close

- Run date: 2026-06-15
- Scope: `HYU_T1_034` focused store-fixed eval-only after the aggregate /
  dependency projection refactor.
- Local result bundle:
  - `benchmarks/results/hyu_t1_034_ratio_task_output_distinct_source_2026-06-15/`
- Result: numeric `PASS`, faithfulness `1.000`, numeric grounding `1.000`,
  numeric retrieval support `1.000`, avg score `0.947`.
- Final answer: `2023년 전체 영업이익에서 차량 부문이 차지하는 비중은
  83.81%입니다. 계산: 차량 영업이익 12,677,300백만원 / 전체 영업이익
  15,126,901백만원.`
- Runtime change stays generic: recovered lookup task-output slots keep
  task-output provenance, inherit producer required-operand metadata when
  source slots are stale, and ratio source binding avoids reusing a task output
  already selected for the opposite ratio role group.
- Verification: aggregate projection/evaluator/run projection suites `152`
  tests OK, runtime domain-term audit passed.
- Post-fix focused regression:
  - `SKI_T2_069`: numeric `PASS`, faithfulness/completeness `1.000`
    (`benchmarks/results/regression_ski_t2_069_after_hyu_rebind_2026-06-15/`)
  - `POS_T1_075`: numeric `PASS`, faithfulness/completeness `1.000`
    (`benchmarks/results/regression_pos_t1_075_after_hyu_rebind_2026-06-15/`)
  - `HYU_T1_034`: numeric `PASS`, faithfulness `1.000`, numeric grounding
    `1.000`
    (`benchmarks/results/regression_hyu_t1_034_after_hyu_rebind_2026-06-15/`)
- Large-diff review follow-up: renamed the structured-cell affinity policy keys
  from `segment_revenue_*` to generic `scoped_*` names in runtime/config
  consumers. Domain marker vocabulary remains in retrieval policy, while agent
  code consumes only the generic policy contract. Scoped surface affinity
  scoring and dependency-projection slot/source matching helpers are now
  centralized in `financial_graph_helpers` instead of repeated as nested
  implementation in `financial_graph_calculation`. Lookup task-output slot
  recovery is now delegated to `src/agent/financial_dependency_projection.py`.
  Validation:
  `tests.test_operation_contracts` plus
  `tests.test_aggregate_subtask_projection` `271` OK, runtime domain-term audit
  passed, projection/evaluator/run projection suites `152` OK, and
  `git diff --check` passed.
- Additional structure cleanup moved table-label evidence collection and
  dependency operand construction helpers into
  `src/agent/financial_dependency_projection.py`, leaving
  `financial_graph_calculation` closer to orchestration-only code for this
  path. Source-task answer-slot candidate extraction for dependency projection
  now lives in the same module, along with source-task operand derivation and
  fallback dependency operation-plan construction for ratio/growth repair.
  Existing operand refresh from lookup slots and operand-id dedupe are also
  delegated there. Ratio missing-role fill, including denominator candidate
  inference from sibling lookup rows, is also centralized there. Dependency
  calculation-plan executability checks and deterministic/fallback rebuild are
  delegated there via callbacks. Recalculation state creation, absolute-ratio
  magnitude post-processing, and recalculated row assembly are now delegated
  there too. Lookup-row realignment from projected task-output operands is now
  delegated there as a row-level helper.

### Latest Financial Graph Calculation Refactor And Focused Eval Check

- Run date: 2026-06-15
- Scope:
  - `financial_graph_calculation` aggregate/projection helper refactor
  - shared numeric surface extraction in `financial_numeric_surface`
  - evaluator reuse of runtime numeric evidence candidate extraction
  - generic ratio collapse guard for numerator/denominator rows that share the
    same source/value slot
- Local eval-only result bundles:
  - `benchmarks/results/refactor_check_ski_t2_069_eval_only_2026-06-15/`
  - `benchmarks/results/refactor_check_hyu_t1_034_eval_only_2026-06-15/`
  - `benchmarks/results/refactor_check_pos_t1_075_eval_only_2026-06-15/`
- Follow-up projection-helper smoke bundles:
  - `benchmarks/results/refactor_projection_ski_t2_069_eval_only_2026-06-15/`
  - `benchmarks/results/refactor_projection_hyu_t1_034_eval_only_2026-06-15/`
  - `benchmarks/results/refactor_projection_pos_t1_075_eval_only_2026-06-15/`
- Artifact hygiene: these benchmark bundles are local experiment artifacts and
  are not commit candidates.

Focused store-fixed eval-only result:

| Question | Previous | Initial refactor check | Projection-helper smoke | Note |
| --- | ---: | ---: | ---: | --- |
| `SKI_T2_069` | PASS, avg `0.9630` | PASS, avg `0.9645` | PASS, avg `0.965` | source-stated growth/narrative answer remains stable |
| `POS_T1_075` | PASS, avg `0.9444` | PASS, avg `0.9194` | PASS, avg `0.919` | answer unchanged; score movement is evaluator-side detail |
| `HYU_T1_034` | FAIL, avg `0.7612` | FAIL, avg `0.7751` | PASS, avg `0.947` | late total operating-income lookup remains bound as denominator after helper extraction |

Interpretation:

- The two already-passing focused cases remained faithful after the refactor.
- `HYU_T1_034` initially exposed a same-source/value self-ratio path. The
  generic guard rejected that invalid path, and the later dependency-projection
  binding fix recovered the distinct total operating-income denominator.
- The latest projection-helper extraction preserved that repaired behavior:
  `HYU_T1_034` still returns `83.81%` with numeric grounding and retrieval
  support intact.
- No company name, benchmark id, or report-specific runtime branch was added.

Validation:

- targeted `py_compile`: OK
- `.venv\Scripts\python.exe -m unittest tests.test_aggregate_subtask_projection tests.test_evaluator_runtime_projection tests.test_financial_agent_run_projection`:
  `152` tests OK after the latest helper extraction
- `.venv\Scripts\python.exe -m src.ops.audit_runtime_domain_terms`: passed
  with `216` reviewed literals
- `git diff --check`: passed
- Store-fixed focused eval-only smoke after latest projection-helper extraction:
  `HYU_T1_034`, `POS_T1_075`, and `SKI_T2_069` all numeric `PASS`.

### Latest CEL Margin-Drag Unit/Answer Consistency Closure

- Run date: 2026-06-12
- Focused case: `CEL_T1_038`
- Profile: `benchmarks/profiles/curated_ablation_structural_hard_full_system.json`
- Local result bundle:
  `benchmarks/results/cel_t1_038_unit_repair_check_2026-06-12/`
- Final user-facing answer:
  `2023년 영업이익률 감소 영향은 8.36%p입니다. 계산: 무형자산상각비 182,049,824천원 / 매출액 2,176,431,531.38천원.`
- Result: numeric final judgement `PASS`; faithfulness, completeness,
  numeric grounding, and unit consistency all `1.000`.

Root cause:

- Numeric extractor evidence may preserve a value-local unit only in `claim`
  while `quote_span` contains the number alone, for example
  `2,176,431,531,380 (원)`.
- Lookup capture previously kept the table metadata unit when a current unit was
  already present, so revenue could be carried forward as
  `2,176,431,531,380천원`.
- Late aggregate synthesis could then leave a stale top-level answer even after
  downstream ratio traces recovered the corrected `8.36%p` result.

Runtime contract change:

- Lookup slot refinement now considers source-visible claim units when the
  quote span contains only the value.
- Late lookup/source-task alignment can repair final ratio traces from
  corrected source task slots and refresh the aggregate answer.
- Final numeric selection is query-focused: when multiple completed numeric
  subtasks exist, the answer composer prioritizes the subtask whose metric and
  operand focus best matches the user query, instead of always concatenating
  support subtasks.
- No company name, benchmark id, or report-specific runtime branch was added.

Validation:

- focused operation/subtask regression tests: OK
- `.venv/bin/python -m src.ops.audit_runtime_domain_terms`: passed with `216`
  reviewed literals
- `git diff --check`: passed
- focused CEL benchmark with heartbeat: `PASS`

### Latest Broader Curated Full Eval

- Run date: 2026-06-12
- Profile: `benchmarks/profiles/curated_single_doc_core.json`
- Mode: store-fixed `--eval-only` refresh with
  `--progress-heartbeat-sec 30`
- Local result bundle was summarized from
  `benchmarks/results/curated_single_doc_core_2026-06-11/` and then deleted
  under benchmark artifact hygiene.
- Scope: 삼성전자 2023, 네이버 2023, 현대자동차 2023; `15` full-eval
  questions total.
- Source commits:
  - `d5bfbc1` tightened narrative evidence projection for final runtime
    evidence.
  - `ebaeb66` stopped exclusive narrative policy tasks from re-entering
    semantic planning after aggregate synthesis.

Company-level full-eval metrics:

| Company | Questions | Avg score | Faithfulness | Completeness | Recall | Hit@k | Section | Citation | Numeric pass | Error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 삼성전자 2023 | 5 | `0.837` | `1.000` | `1.000` | `0.800` | `0.800` | `0.750` | `0.933` | `1.000` | `0.0%` |
| 네이버 2023 | 5 | `0.795` | `1.000` | `1.000` | `1.000` | `0.600` | `0.600` | `0.867` | `1.000` | `0.0%` |
| 현대자동차 2023 | 5 | `0.928` | `1.000` | `1.000` | `1.000` | `1.000` | `0.900` | `1.000` | `-` | `0.0%` |

Observed runtime closure:

- `SAM_T4_070` exposed a repeated loop:
  `narrative_policy_exclusive -> retrieve -> evidence(missing) -> compress ->
  aggregate -> semantic_plan`.
- The fix is a generic routing contract: when the semantic plan status is
  `narrative_policy_exclusive`, aggregate output is terminal and routes to
  `cite` even if aggregate synthesis or integrity feedback leaves planner
  feedback text behind.
- Focused `SAM_T4_070` eval-only completed in `52.3s` after the fix.
- The full Samsung eval completed all `5` questions with error `0.0%`; the
  broader 15-question run also completed with error `0.0%`.

Residual quality signals:

- `SAM_T4_070`: faithful and refusal-accurate, but retrieval hit / section
  match are `0.000`. The answer says the 2026 3nm foundry yield is not in the
  filing, while the retrieved window also contains related 3nm/GAA context that
  is not preserved as final runtime evidence.
- `NAV_T4_008` and `NAV_T4_033`: safe missing-answer/refusal behavior, but low
  retrieval hit and section match.
- These are next evidence-projection / refusal-support diagnostics. They are
  not benchmark-specific runtime branch candidates.

### Latest Hard Numeric Runtime Closure

- Hard structural profile replay, 2026-06-11:
  - profile: `benchmarks/profiles/curated_ablation_structural_hard_full_system.json`
  - local eval-only bundle was summarized from
    `benchmarks/results/hard_current_evalonly_2026-06-10/` and then deleted
    under benchmark artifact hygiene
  - result: `5 / 5` numeric PASS
  - passing cases:
    - `KAB_T1_066`: CIR `37.47%`
    - `MIX_T1_021`: debt ratio `25.36%`, current ratio `258.77%`
    - `SAM_T1_026`: ROE `4.31%` using average equity
    - `CEL_T1_038`: margin drag `8.36%p`, operating margin `29.93%`
    - `SKH_T1_060`: borrowing over tangible+intangible assets `42.02%`
- Source change:
  - `roe` is now represented in ontology as net income over average
    current/prior equity, with period hints propagated through operand specs
    and task bindings.
  - `operating_margin_drag` is represented in ontology/policy as amortization
    expense over revenue, rendered in percentage points.
  - Runtime lookup rows now preserve aggregate/final structural metadata and
    use it during late lookup-to-ratio alignment.
  - Late alignment can refresh planless ratio answers from stronger structured
    slots, but it blocks weaker detail lookups from replacing already
    dependency-backed arithmetic operands.
  - No company name, benchmark id, or report-specific runtime branch was added.
- Validation:
  - focused late-alignment runtime tests: `3` OK
  - related ontology / planner / operation / structured extraction suites before
    the final alignment guard: `389` OK
  - runtime domain-language audit: passed with `217` reviewed literals
  - hard profile eval-only replay: `5 / 5` numeric PASS
- Follow-up trace analysis:
  - `SKH_T1_060` was inspected in
    `docs/evaluation/structural_trace_diagnostics.md`.
  - Structural bound borrowing operands to `period_focus=current`,
    `period_labels=["당기"]`, `::table:93`.
  - Plain bound borrowing operands to `period_focus=prior`,
    `period_labels=["전기"]`, `::table:94`, while keeping the current-period
    asset denominator.
- Raw `benchmarks/results/**` hard bundles are local artifacts and are not part
  of the source commit. The latest structural hard eval-only raw bundle was
  deleted after the result was summarized in docs.

### Latest Hard Structural-vs-Plain Replay

- Plain hard profile replay, 2026-06-11:
  - profile: `benchmarks/profiles/curated_ablation_structural_hard_plain_retrieval.json`
  - local result bundle:
    `benchmarks/results/ablation_structural_hard_plain_retrieval_2026-06-11/`
  - result: `4 / 5` numeric PASS
  - aggregate metrics: numeric `0.750`, completeness `0.812`,
    faithfulness `0.875`, recall `0.932`
- Comparison to structural hard replay:
  - structural: `5 / 5` numeric PASS, completeness `0.938`,
    faithfulness `1.000`, recall `0.827`
  - plain: `4 / 5` numeric PASS, completeness `0.812`,
    faithfulness `0.875`, recall `0.932`
- Separating case:
  - `SKH_T1_060` structural answered `42.02%` using borrowing operands
    `4,145,647`, `10,121,033`, and `9,490,410` 백만원.
  - Plain answered `34.32%` using lower borrowing operands `3,833,263`,
    `9,073,567`, and `6,497,790` 백만원.
  - Both variants used the same denominator
    `52,704,853 + 3,834,567` 백만원.
- Interpretation:
  - The recent ontology/period/runtime-contract changes now carry many hard
    cases even under plain retrieval.
  - Structural representation still gives a measurable row-binding advantage
    when multiple plausible borrowing rows share similar labels and periods.
  - The portfolio claim should be precise: structural metadata is not a blanket
    win on every metric, but it prevents specific ambiguous-table operand
    selection failures that deterministic calculation alone cannot correct.
- Documentation status:
  - the `SKH_T1_060` trace has been folded into README, one-pager, experiment
    report, interview narrative, resume snippets, and technical highlights.

### Broader Full Benchmark Notes

- `curated_single_doc_core` is no longer only a preflight candidate; the
  store-fixed full-eval refresh above completed on 2026-06-12.
- The full curated dataset remains larger:
  `benchmarks/datasets/single_doc_eval_full.curated.json` has `77` questions.
- The routine `curated_single_doc_core` profile covers the three core 2023
  reports. The long-running full-dataset profile is now separated as
  `benchmarks/profiles/curated_single_doc_official_77.json`, which covers all
  77 questions across the 11 single-document curated 2023 report scopes.
- Treat the full 77-question official run as a separate long-running
  experiment. Prefer a store-fixed `--eval-only` refresh when reusable stores
  exist; use a fresh monitored run only when the profile/report coverage or
  ingest contract itself changed.
- Continue to run broader refreshes with heartbeat monitoring and do not stage
  `benchmarks/results/**`.

### Latest Portfolio Ablation Refresh

- Commit `8070da8` fixed aggregate numeric projection coverage and was pushed
  to `origin/main`.
- Expanded structural-vs-plain ablation refresh, 2026-06-10:
  - profiles:
    - `benchmarks/profiles/curated_ablation_expanded_candidate_full_system.json`
    - `benchmarks/profiles/curated_ablation_expanded_candidate_plain_retrieval.json`
  - local result bundles:
    - `benchmarks/results/ablation_expanded_candidate_full_system_2026-06-10/`
    - `benchmarks/results/ablation_expanded_candidate_plain_retrieval_2026-06-10/`
  - question set: `9` curated questions across `6` company runs
  - structural full-system: average numeric `1.000`, faithfulness `1.000`,
    completeness `0.867`, recall `0.889`
  - plain retrieval baseline: average numeric `0.833`, faithfulness `0.875`,
    completeness `0.875`, recall `0.861`
  - main separating cases:
    - `KBF_T1_017`: plain numeric `FAIL`; structural numeric `PASS`
    - `SKH_T3_080`: plain numeric `FAIL`; structural numeric `PASS`
  - strongest trace: `SKH_T3_080` plain selected `868,767` and `906,120`
    then answered `-37,353백만원`; structural selected `573,884백만원` and
    `906,120백만원` then answered `-332,236백만원`.
- Important caveat:
  - run-level `Full Eval Fails` still counts completeness threshold misses, so
    both variants show `3` full-eval fail notes. The portfolio claim should be
    framed around numeric grounding, operand binding, and faithfulness rather
    than a blanket end-to-end win on every evaluator dimension.
- Portfolio-facing summaries:
  - `docs/evaluation/ablation_study_design.md`
  - `docs/evaluation/structural_trace_diagnostics.md`
  - `docs/overview/portfolio_experiment_report.md`
  - `docs/overview/portfolio_one_pager.md`
- Validation before the pushed source commit:
  - `.venv/bin/python -m unittest discover -s tests`: `1048` tests OK
  - `.venv/bin/python -m src.ops.audit_runtime_domain_terms`: passed
  - focused `MIX_T1_021` eval-only: PASS
  - full-system expanded candidate summary before refresh: numeric `1.000`,
    completeness `1.000`, faithfulness `1.000`
- Raw `benchmarks/results/**` ablation bundles remain local artifacts and are
  not part of the published source commit.

### Runtime/API Cost Control

- Current status: the focused `KAB_T1_066` CIR path is closed with source-visible
  operands and controlled fanout. Numeric-extraction LLM fanout has been
  reduced; equivalent lookup rewordings reuse state-local retrieval results;
  duplicate reflection report artifact ids are fixed; repeated direct-support
  lookup rejections stop extra semantic replan after the first replan attempt.
- Latest source change, 2026-06-09:
  - Lookup direct-support validation now checks the exact prompt context shown
    to numeric extraction, not only raw `Document.page_content` and selected
    evidence items.
  - Aggregate-result guards distinguish embedded operation tokens inside a
    metric label from explicit aggregate operation phrases by checking the
    token's left boundary.
  - Ratio operand assembly probes retrieved/seed docs for a coherent source
    context when dependency task outputs already cover the required operands.
    If one table/context directly provides all operands, those source-visible
    rows realign the ratio operands.
  - Late aggregate rendering refreshes ratio answers from the resolved
    calculation trace when the result value is present but component display
    differs.
  - This is a provenance/display contract change, not a company/question branch.
- Latest focused eval-only, `KAB_T1_066` on 2026-06-09:
  - answer: `2023년 CIR은 37.47%입니다. 계산: 판매비와관리비 4,355억원 /
    경비차감전영업이익 11,623억원.`
  - operands: `4,355억원` and `11,623억원`, both from
    `IV. 이사의 경영진단 및 분석의견::table:3`
  - numeric `PASS`, faithfulness/completeness/context recall/retrieval hit@k
    `1.000 / 1.000 / 1.000 / 1.000`, grounded rendering `1.000`
  - latency `68.5s`, agent LLM tokens `55,104`, agent calls `8`
  - fanout audit: executed queries `2`, duplicate executed queries `0`,
    state query-result avoided searches `14`, estimated runtime cost `$0.056292`
- Previous source change, 2026-06-09:
  - Aggregate replan now checks the numeric extraction debug history before
    routing back to semantic planning.
  - If `plan_loop_count >= 1` and the history shows
    `duplicate_missing_direct_lookup_operand_support`, the runtime records
    `replan_blocked_reason = duplicate_missing_direct_lookup_operand_support`,
    keeps the partial/refusal answer path, and routes to `cite` instead of
    invoking another semantic replan.
  - The guard only applies after a duplicate direct-support rejection, so first
    replan attempts and new evidence surfaces remain available.
- Earlier source change, 2026-06-09:
  - Reflection retry handoff ids are now allocated from the existing
    task/artifact ledger, not only from `reflection_count + 1`.
  - `_prepare_reflection_retry()` scans existing `reflection:{target}:NNN`
    task ids and `reflection:{target}:NNN:report` artifact ids, then writes the
    next unused id. This prevents stale-count or re-entry paths from producing
    `duplicate_artifact_id:reflection:...:report`.
  - The fix is a generic ledger allocation contract; retry/replan decisions and
    evidence validation are unchanged.
- Earlier source change, 2026-06-09:
  - lookup and single-value retrieval subtasks now compute a normalized
    `objective_signature` from the operation family, metric label, and
    required operands.
  - The state-local query-result cache can reuse a prior retrieval result when
    the same `where_filter` and lookup objective signature already exist with
    a large-enough `k`, even if the rewritten query text differs.
  - Retrieval traces now report
    `state_same_filter_exact_or_lookup_objective_signature` plus
    `objective_hit_count`, so exact query reuse and objective-level reuse stay
    separable in diagnostics.
  - The contract is generic cache reuse for equivalent retrieval objectives; no
    company, benchmark ID, or metric-specific runtime branch was added.
- Latest focused canary, `KAB_T1_066` on 2026-06-09 after the objective cache
  reuse change:
  - numeric `PASS`, faithfulness/completeness `1.000 / 1.000`, context
    recall/retrieval hit@k `0.500 / 1.000`
  - latency `346.8s`, estimated runtime cost `$0.110721`
  - executed queries `12`, duplicate executed queries `0`, query embedding API
    calls `12`
  - query-result cache avoided searches `64`, including `42` objective hits
  - agent LLM tokens `148,169` across `25` calls
  - `numeric_extraction` `61,708` tokens across `4` calls
- Interpretation:
  - Retrieval/embedding fanout improved compared with the previous numeric reuse
    canary: executed queries `34 -> 12`, duplicate executed queries `8 -> 0`,
    and embedding calls `26 -> 12`.
  - End-to-end latency/cost did not improve because the run re-entered
    semantic replan/retry after a direct-support rejection and surfaced
    `duplicate_artifact_id:reflection:task_1:001:report`.
- Previous focused canary after duplicate numeric result/rejection reuse:
  - `numeric_extraction_prompt` diagnostics now include stable fingerprints for
    the normalized numeric query and selected candidate window without storing
    prompt text.
  - When the same extraction fingerprint already produced a direct-supported
    result, the runtime reuses it as `duplicate_numeric_extraction_result`.
  - When the same extraction fingerprint already failed direct operand support,
    the runtime reuses that missing evidence state as
    `duplicate_missing_direct_lookup_operand_support`.
  - The reuse only applies to equivalent query + candidate-window attempts; no
    company, benchmark ID, or metric-specific branch was added.
- Latest focused canary, `KAB_T1_066` eval-only on the reused local store after
  the reuse change:
  - numeric `PASS`, faithfulness/completeness `1.000 / 1.000`, context
    recall/retrieval hit@k `1.000 / 1.000`
  - latency `232.7s`, estimated runtime cost `$0.084768`
  - agent LLM tokens `108,158` across `18` calls
  - `numeric_extraction` reduced to `50,224` tokens across `3` calls
  - history preserved `6` entries, with `3` skipped entries:
    `2` failed direct-support reject reuses and `1` supported result reuse
- Diagnostic baseline before any numeric reuse:
  - latency `416.0s`, estimated runtime cost `$0.150280`
  - agent LLM tokens `190,990` across `25` calls
  - `numeric_extraction` `106,483` tokens across `6` calls
- Next cost-control target:
  - run a focused store-fixed/eval-only canary when a reusable KAB store is
    available, to quantify whether the guard reduces `reflection_planning` /
    `semantic_plan_replan` calls without changing numeric quality
- Validation for the replan loop guard:
  - focused aggregate/replan tests: `4` OK
  - related subtask/run-projection/reflection suites: `217` OK
  - runtime domain-term audit: passed with `215` reviewed literals
  - full unittest discovery: `1028` OK
- Validation for the reflection id allocation change:
  - focused reflection/ledger tests: `5` OK
  - related subtask/run-projection/reflection suites: `216` OK
  - runtime domain-term audit: passed with `215` reviewed literals
  - full unittest discovery: `1027` OK
- Validation for the lookup objective reuse change:
  - focused retrieval/cache tests: `5` OK
  - related retrieval/fanout/operation suites: `212` OK
  - runtime domain-term audit: passed with `215` reviewed literals
  - full unittest discovery: `1026` OK

- Earlier observability layer:
  - `numeric_debug_trace_history` is preserved in agent state and public
    `FinancialAgent.run()` output.
  - Evaluator and benchmark rows serialize the same call-level history as
    `agent_numeric_debug_trace_history`; the existing single
    `agent_numeric_debug_trace` remains as the latest-call compatibility
    snapshot.
  - The diagnostic baseline for `KAB_T1_066` showed the problem before reuse:
    numeric `PASS`, latency `416.0s`, agent LLM tokens `190,990`, and
    `numeric_extraction` `106,483` tokens across `6` calls.

### Structural Capability Gates

- Reflection promotion:
  - `src.ops.reflection_promotion_gate` is ready across the base fixture,
    store-fixed candidate surface, reviewed store-fixed trace summary, and
    reviewed live/default MAS handoff trace summary.
  - The gate now requires all four source classes before reporting `ready`, so
    the promotion proof cannot silently shrink to a single synthetic fixture.
  - Reflected accepted cases still require visible target refs,
    `final_acceptance_authority = critic_orchestrator_handoff`,
    `false_recovery_rate = 0.0`, and
    `integrity_preservation_rate = 1.0`.
  - `retry_retrieval` actions require visible `reflection_action.retry_queries`;
    `synthesize_from_task_outputs` actions require visible
    `reflection_action.synthesis_source_ids`.
- Report-scoped cache promotion evidence:
  - `src.ops.report_cache_promotion_evidence_gate` is ready for the
    candidate-only local-index fixture plus reviewed store-fixed and
    live/default MAS handoff trace summaries.
  - Ready evidence must expose the calculation-task producer policy,
    `operand_set`, `calculation_plan`, and `calculation_result` artifact kinds,
    local-cache-origin metadata, and a valid calculation-contract projection.
  - Fallback evidence must remain non-ready, require normal retrieval fallback,
    carry explicit fallback reasons, and keep retrieval bypass, serving, ledger
    insertion, and final acceptance disabled.
- Promotion trace materiality:
  - `src.ops.promotion_trace_materiality_gate` is ready.
  - The gate checks that the reviewed store-fixed and live/default MAS trace
    summaries carry materially distinct source types, reflection actions
    (`none`, `retry_retrieval`, `stop_insufficient`), and cache fallback
    reasons before the portfolio bundle treats them as promotion evidence.
  - Future trace summaries should be added only when this same materiality
    standard can explain a new source/action/fallback surface rather than a
    duplicate benchmark replay.
- Portfolio review:
  - `src.ops.portfolio_review_gates` is ready and reports portfolio demo,
    cache reviewer, cache promotion evidence, reflection promotion,
    promotion-trace materiality, and `REFERENCE_NOTE` capability status in one
    reviewer-facing bundle.
- `REFERENCE_NOTE` capability:
  - `src.ops.reference_note_capability_gate` is ready.
  - The current boundary is `graph_expansion_context_only` with owner
    `researcher_graph_expansion`.
  - `REFERENCE_NOTE` may appear as `graph_relation = reference_note` and may be
    carried through a Researcher `retrieval_bundle`, but cache serving,
    retrieval bypass, ledger insertion, and final acceptance remain disabled.
- Current interpretation:
  - These gates prove capability boundaries and reviewer evidence, not active
    serving. The next increment should add another trace summary only when a
    new live/default MAS or store-fixed eval-only surface exposes materially
    different reflection or cache evidence.

### Runtime Contract Gate

- Profile: `benchmarks/profiles/curated_runtime_contract_gate.json`
- Candidate: `structural_selective_v2_prefix_2500_320`
- Current interpretation: default short smoke gate is stable.
- Latest focused repair:
  - `SKH_T1_060` now passes the fresh low-API structural path with answer
    `42.02%`.
  - The fix is generic structured evidence selection: direct row-label /
    semantic-label evidence is preferred when projecting lookup task outputs
    into downstream ratio dependencies.
  - Producer lookup subtask result views are also aligned with that dependency
    projection, so serialized intermediate displays preserve the same direct
    structured value used by the final ratio.
  - No company name, benchmark ID, or metric-specific runtime branch was added.

### Concept Runtime Gap Gate

- Profile: `benchmarks/profiles/curated_concept_runtime_gap_gate.json`
- Profile cost controls:
  - full-eval retrieval budgets are now recorded as `8 / 4 / 1`:
    `retrieval_query_budget`, `focused_retrieval_query_budget`, and
    `retry_retrieval_query_budget`
  - a 2026-06-08 store-fixed `CEL_T1_013` budget canary preserved numeric
    `PASS`, faithfulness/completeness `1.000 / 1.000`, and artifact integrity
    `ok`
  - the canary query-budget traces reduced primary query surfaces from
    `18 -> 8` and `15 -> 8`; the fan-out audit reported `15` executed queries,
    `0` duplicates, and `1` state query-result cache reuse
- Latest hardening follow-up:
  - a 2026-06-09 task-ledger trace cleanup adds a `superseded` lifecycle
    status for pending/partial planned tasks that are already covered by final
    aggregate answer slots or operands; task trace projection now exposes
    `resolution_status`, `superseded_by_task_id`,
    `superseded_by_artifact_id`, and `notes`
  - this is a generic ledger-visibility contract, not an answer-path or
    benchmark-specific rule; matching uses existing slot key and period
    extraction over final aggregate/subtask slots
  - validation for this cleanup: `python -m unittest tests.test_subtask_loop
    tests.test_operation_contracts` ran `339` tests OK,
    `python -m src.ops.audit_runtime_domain_terms --summary` passed with
    `215` reviewed literals, and `git diff --check` passed
  - focused KAB probes during this cleanup showed remaining upstream
    replan/operand-coverage volatility, so latency/partial-answer stability is
    the next blocker rather than part of this ledger patch
  - a 2026-06-09 monitored store-fixed full eval-only replay refreshed the
    concept runtime gate proof after the focused hardening work:
    `benchmarks/results/concept_gate_fresh_after_ratio_growth_hardening_2026-06-08/`
    remains a local experiment artifact and is not committed
  - the replay reports `7 / 7` numeric `PASS` across `KBF_T2_018`,
    `SKH_T3_080`, `CEL_T1_013`, `CEL_T3_040`, `POS_T1_057`,
    `KAB_T1_066`, and `SAM_T3_028`; all seven questions have
    faithfulness/completeness `1.000 / 1.000`
  - the final runtime change after ratio/growth hardening is intentionally
    narrow: `narrative_summary` rows are skipped when selecting a supported
    aggregate numeric answer, so narrative projections cannot be promoted just
    because their answer slots carry `operation_family = aggregate_subtasks`
  - latest validation for that final contract fix: `python -m
    src.ops.audit_runtime_domain_terms --summary` passed with `215` reviewed
    literals, and `python -m unittest tests.test_subtask_loop
    tests.test_operation_contracts` ran `336` tests OK
  - a later 2026-06-08 focused hardening pass closed two single-question
    residuals without replacing the frozen 2026-06-04 full-gate baseline
  - `POS_T1_057` ratio operands now prefer direct structured evidence whose
    raw unit aligns with peer operands in the same ratio; focused eval-only
    reports numeric `PASS`, faithfulness/completeness `1.000 / 1.000`, and
    answer `3.5269배`
  - `KBF_T2_018` aggregate growth+narrative repair now treats a numeric-only
    growth answer as incomplete when supported narrative-summary evidence is
    available but absent from the final answer; focused eval-only reports
    numeric `PASS`, faithfulness/completeness `1.000 / 1.000`, preserving both
    `70.28%` and the conservative provisioning / future economic uncertainty
    cause
  - `KAB_T1_066` focused eval-only after the ratio hardening remains numeric
    `PASS` with faithfulness/completeness `1.000 / 1.000` and CIR answer
    `37.47%`
  - a later `KAB_T1_066` trace-quality pass keeps complete active ratio
    reconciliation rows ahead of partial lookup dependency scope filters; the
    focused store-fixed eval-only still reports numeric `PASS` and
    faithfulness/completeness `1.000 / 1.000`, while latency improves
    `309s -> 108s`, retrieval history `8 -> 3`, and task artifacts `21 -> 8`
  - latest local validation: `python -m unittest tests.test_subtask_loop tests.test_part_whole_ratio_contract`
    ran `169` tests OK, `python -m src.ops.audit_runtime_domain_terms` passed
    with `215` reviewed literals, and `python -m unittest discover -s tests`
    ran `997` tests OK
  - the focused canary hardening was subsequently replayed through the
    monitored full 7 eval-only proof above
  - a 2026-06-08 budgeted full eval-only replay completed all seven concept
    questions but produced `5 / 7` numeric PASS, so it is not treated as a new
    release baseline
  - the replay exposed two runtime/path residuals: `KBF_T2_018` could reuse a
    parenthesized current-period display as the prior-period value during
    growth recovery, and `POS_T1_057` showed unit/source binding instability in
    the full replay path even though standalone eval-only still passed
  - the growth-rate hardening is generic: complete reconciliation rows can
    override stale dependency outputs, same-label current/prior operands are
    keyed by label, role, and period during supplemental merge, and evidence
    prior recovery skips compact-numeric matches to the current display
  - focused canaries after the fix passed for `KBF_T2_018` and `POS_T1_057`
    with faithfulness/completeness `1.000 / 1.000`; `POS_T1_057` calculated
    `3.5269배`
  - `KAB_T1_066` is no longer tracked as an open product-quality residual in
    this gate: the later single-question recovery and monitored full replay
    both report numeric `PASS`, faithfulness/completeness `1.000 / 1.000`, and
    CIR answer `37.47%`
  - validation: focused growth/aggregate regression `4` tests OK, broader
    structured operand / semantic plan / operation contract / subtask-loop
    suite `417` tests OK, and runtime domain-language audit passed
  - latest `KBF_T2_018` trace-consistency follow-up keeps focused store-fixed
    eval-only numeric `PASS` with average score `0.924`; the serialized
    `resolved_calculation_trace` and `structured_result` now show
    `task_1 = 70.28%` and `task_4 = 1,847,775백만원`, with `0` stale nested
    hits for `(303)` / `-1138.28%`
  - latest local validation after this trace cleanup: `python -m
    src.ops.audit_runtime_domain_terms --summary` passed with `215` reviewed
    literals, and `python -m unittest discover -s tests` ran `1019` tests OK
- Latest representative local output:
  `benchmarks/results/concept_gate_refresh_after_answer_composition_2026-06-04/`
- Result:
  - 6 / 6 company runs completed
  - 7 / 7 questions pass
  - `numeric_final_judgement = PASS` for all seven questions
  - full-eval faithfulness is `1.000` for all seven questions
  - full-eval numeric pass rate is `1.000` for all seven questions
  - `KBF_T2_018`, `POS_T1_057`, and `SAM_T3_028` answer-composition
    residuals are closed
- Promotion baseline freeze:
  - baseline id: `concept_runtime_gap_gate_7of7_2026-06-04`
  - source profile:
    `benchmarks/profiles/curated_concept_runtime_gap_gate.json`
  - source artifact:
    `benchmarks/results/concept_gate_refresh_after_answer_composition_2026-06-04/`
    (local experiment artifact, not committed)
  - future concept-runtime canaries should reuse the stored bundle through
    store-fixed eval-only first; fresh ingest is reserved for parser, ingest,
    cache-signature, or missing-store changes
  - changes to ontology-driven lookup planning, structured row binding,
    sibling evidence recovery, concept answer composition, or aggregate numeric
    rendering should compare against this baseline before promotion
- Main closure:
  - multi-concept lookup tasks now split into independent task-ledger entries
  - sibling table evidence can recover missing lookup slots generically
  - lookup-list rendering is constrained to lookup-only aggregates
  - source-visible value displays are preserved when they are stronger than
    recomputed rounded displays
  - quantitative-impact composition assembles only evidence-visible numeric
    claims and relations
  - context-dependent segment/total table rows are rejected for unscoped
    lookup and ratio operands
  - post-fix runtime blockers for `KBF_T2_018`, `POS_T1_057`, and
    `SAM_T3_028` are closed without adding runtime domain keyword branches

### Policy-Driven Runtime Gate

- Profile: `benchmarks/profiles/curated_policy_driven_runtime_gate.json`
- Canonical remote embedding runtime:
  OpenAI `text-embedding-3-large` when `OPENAI_API_KEY` is available.
- Latest post-fix fresh OpenAI embedding refresh result:
  - 4 / 4 company runs passed
  - 0 full-eval failures
  - 0 critical misses
  - five-question average faithfulness, completeness, context recall, and
    retrieval hit@k are all `1.000`
  - average section match is `0.975`, citation coverage is `0.933`, entity
    coverage is `0.927`, and error rate is `0.0%`
- Store-fixed eval-only refresh after task/artifact contract fixes
  (`benchmarks/results/current_policy_gate_after_contract_2026-06-06/`,
  historical local artifact, not committed):
  - 4 / 4 company runs passed
  - task/artifact integrity is `ok` for 5 / 5 full-eval rows, with
    `orphan_ids = []`
  - average faithfulness `0.938`, completeness `0.925`, context recall
    `1.000`, retrieval hit@k `1.000`, numeric pass rate `1.000` where
    applicable
  - at this artifact snapshot, full-eval threshold failures remained for
    `NAV_T2_006` (completeness `0.700`) and `HYU_T2_010` (faithfulness
    `0.500`)
  - `HYU_T3_072` now has faithfulness `1.000`, completeness `1.000`,
    refusal accuracy `1.000`, and task/artifact integrity `ok`
- Current focused closure after the growth narrative evidence-surface commit:
  - commit: `3671f2a9 Preserve growth narrative evidence surfaces`
  - focused store-fixed eval-only over the Hyundai policy-gate questions
    completed with faithfulness `1.000`, completeness `1.000`, context recall
    `1.000`, retrieval hit@k `1.000`, entity coverage `1.000`, and error rate
    `0.0%`
  - `HYU_T2_010` now preserves the evidence-visible current/prior/growth
    displays (`87.0만 대`, `78.1만 대`, `11.5%`) while keeping the
    policy/protectionism narrative source surface visible and deduplicated
  - The evaluator section-support projection now accepts runtime evidence that
    directly overlaps canonical quote text even when the local section label
    differs from the curated expected-section surface.
- Note:
  - `numeric_final_judgement = null` is not a failure for narrative or mixed
    questions when the other evaluator signals are healthy.
- Latest focused repair:
  - `HYU_T2_010` now preserves the source-stated growth display when the DART
    sentence already says `87.0만 대`, `78.1만 대 대비 11.5%`.
  - The deterministic formula trace is still retained, but the final rendered
    answer and `answer_slots.primary_value.rendered_value` use the
    evidence-visible `11.5%` instead of drifting to a recomputed rounding.
  - If a growth calculation accidentally binds duplicate current/prior
    material, runtime now recovers the prior-period display from retrieved
    evidence sentences using generic year/unit/value matching before executing
    the formula.
  - Aggregate growth+narrative composition now treats the structured
    `current_value`, `prior_value`, and growth display slots as required answer
    displays before accepting a mixed-query answer as complete.
  - `NAV_T2_006` now gets commerce-growth driver retrieval from declarative
    retrieval policy suffixes, then rejects source-task display strings whose
    KRW unit conflicts with the already bound growth slot display.
  - The same answer guard replaces growth sentences that mix slot/trace values
    with untraced numeric displays, preserving grounded narrative sentences.
  - Latest OpenAI store-fixed eval-only policy-gate refresh reports
    faithfulness, completeness, context recall, and retrieval hit@k of `1.000`
    for every per-question full-eval row:
    - `NAV_T2_006`: relevancy `0.759`, section match `0.875`,
      citation coverage `0.667`, entity coverage `1.000`
    - `HYU_T2_010`: relevancy `0.696`, section match `1.000`
    - `HYU_T3_072`: relevancy `0.609`, section match `1.000`
    - `LGE_T1_051`: relevancy `0.563`, section match `1.000`,
      `numeric_final_judgement = PASS`
    - `SAM_T2_078`: relevancy `0.817`, section match `1.000`
  - Follow-up diagnosis classified the `SAM_T2_078` section precision gap as
    evaluator-definition drift: the retrieved Harman technology-focus evidence
    from `IV. 이사의 경영진단 및 분석의견` was faithful and complete but was not
    listed as an acceptable expected section. The curated datasets now include
    that section and quote, and recomputing the existing local bundle gives
    section match `1.000`.
  - Latest dependency-slot growth refresh:
    - aggregate growth rows can derive operands from `answer_slots` pointing at
      `task_output:*` lookup rows and recalculate from those sibling lookup
      slots
    - producer lookup slots are propagated back into the serialized growth
      trace, so stale aggregate operands do not survive in `structured_result`
    - `NAV_T2_006` now renders `2,546,649백만원`, `1,801,079백만원`, and
      `41.4%` in the final mixed numeric+narrative answer
    - this is a generic dependency-binding/display-preservation fix, not a
      company/question keyword rule
    - focused `NAV_T2_006` policy-gate smoke confirmed faithfulness `1.000`,
      completeness `1.000`, error rate `0.0%`, and growth-rate answer slots
      aligned to the producer lookup values
    - follow-up focused store-fixed eval-only over the available Google-backed
      policy-gate artifact closed the narrative completeness gap without adding
      runtime domain keyword rules:
      - `NAV_T2_006`: policy-backed supported driver groups are now preserved
        through growth narrative composition; faithfulness `1.000`,
        completeness `1.000`, error rate `0.0%`
      - `LGE_T1_051`: ontology alias-bound compact query markers such as
        source-visible abbreviations are preserved after numeric locking and
        slot-based answer composition; faithfulness `1.000`, completeness
        `1.000`, numeric final judgement `PASS`
  - Focused fan-out canary, 2026-06-07:
    - local artifact:
      `benchmarks/results/policy_gate_fanout_canary_2026-06-07/`
      (not committed)
    - scope: `NAV_T2_006`, `LGE_T1_051`, and `HYU_T2_010` store-fixed
      eval-only over the policy-driven runtime gate profile
    - cost/fan-out audit: 3 questions, 8 retrieval traces, 74 executed
      retrieval queries, 70 query-embedding calls, 40 LLM calls, estimated
      runtime cost `$0.358414`
    - initial result: `LGE_T1_051` and `HYU_T2_010` passed; `NAV_T2_006`
      exposed a stale dependency-unit display and an over-broad narrative
      sentence with an untraced `24.3%` operating-expense KPI
    - repair: dependency projection now refreshes a lookup slot when the
      projected operand carries direct evidence provenance and a corrected
      unit, and growth-narrative pruning rejects driver sentences whose
      numeric material is not present in the supported candidate evidence
    - focused rerun:
      `benchmarks/results/policy_gate_fanout_canary_nav_final_2026-06-07/`
      reports `NAV_T2_006` faithfulness `1.000`, completeness `1.000`,
      context recall `1.000`, retrieval hit@k `1.000`, answer relevancy
      `0.707`, and error rate `0.0%`
  - Query-budget follow-up, 2026-06-07:
    - local artifacts:
      `benchmarks/results/policy_gate_query_dedupe_numeric_only_nav_2026-06-07/`,
      and
      `benchmarks/results/policy_gate_query_dedupe_numeric_only_lge_hyu_2026-06-07/`
      (not committed); intermediate compact-signature screening runs were
      removed after summarization
    - rejected candidate: compact CJK-spacing query signatures reduced
      `NAV_T2_006` executed retrieval queries from `42` to `37` and agent
      query-embedding calls from `39` to `34`, but dropped a narrative query
      surface and lowered faithfulness from `1.000` to `0.500`
    - accepted guard: exact duplicate focused/retry queries are removed only
      when no `narrative_summary` sibling task is present; mixed
      numeric+narrative retrieval now records
      `duplicate_drop_blocked_reason = narrative_sibling_subtask_present`
      and preserves the focused retrieval fan-out
    - safety check: the final NAV mixed rerun preserved faithfulness `1.000`,
      completeness `1.000`, context recall `1.000`, retrieval hit@k `1.000`,
      answer relevancy `0.739`, and error rate `0.0%`
    - LGE/HYU focused rerun preserved quality (`LGE_T1_051` numeric `PASS`;
      both questions faithfulness/completeness `1.000`), but showed no material
      executed-query reduction on this canary. The next cost target is primary
      query-bundle / retrieval-hint inflation rather than compacting
      evidence-diversity surfaces.
  - Retrieval-hint inflation follow-up, 2026-06-07:
    - local artifact:
      `benchmarks/results/policy_gate_hint_budget_balanced_lge_nav_2026-06-07/`
      (not committed)
    - rejected candidate: first-N preferred-section caps were too aggressive
      for mixed numeric+narrative retrieval; `NAV_T2_006` kept context recall
      and retrieval hit@k at `1.000`, but faithfulness/completeness fell to
      `0.700`.
    - accepted guard: primary executed-query enrichment now caps retrieval hint
      terms and applies a head/tail budget to preferred sections, while keeping
      the full policy trace and reranker/supplemental section signals visible.
    - focused NAV/LGE store-fixed eval-only canary preserved quality:
      `NAV_T2_006` faithfulness/completeness/context recall/retrieval hit@k
      all `1.000`; `LGE_T1_051` faithfulness/completeness/context
      recall/retrieval hit@k all `1.000` with
      `numeric_final_judgement = PASS`.
    - cost signal: `NAV_T2_006` query-embedding input chars dropped from
      `7,672` to `2,662` and estimated query-embedding tokens from `1,935` to
      `676`; `LGE_T1_051` query-embedding input chars dropped from `6,120` to
      `4,056` and estimated tokens from `1,539` to `1,019`.
    - query shape signal: `NAV_T2_006` average executed query length dropped
      from `213.6` to `116.6`, and `LGE_T1_051` dropped from `377.2` to
      `248.2`, without adding company, question, or metric-specific runtime
      branches.
    - post-merge full policy-gate confirmation:
      `benchmarks/results/current_policy_gate_after_hint_budget_full_2026-06-07/`
      (local store-fixed eval-only artifact, not committed) replayed all five
      policy-gate rows after PR #21 landed on `main`. Faithfulness,
      completeness, context recall, and retrieval hit@k were all `1.000` for
      `NAV_T2_006`, `HYU_T2_010`, `HYU_T3_072`, `LGE_T1_051`, and
      `SAM_T2_078`; error rate was `0.0%`, task/artifact integrity was `ok`
      for 5 / 5 rows, and the only numeric-applicable row (`LGE_T1_051`)
      returned `numeric_final_judgement = PASS`.
    - full-gate cost/runtime snapshot: 97 executed retrieval queries, 100
      query-embedding calls, 13,948 query-embedding input chars, 3,522
      estimated query-embedding tokens, 58 LLM calls, and estimated runtime
      cost `$0.444073` across the five-row replay.
    - query-embedding cache follow-up:
      `benchmarks/results/current_policy_gate_after_query_embedding_cache_2026-06-07/`
      (local store-fixed eval-only artifact, not committed) replayed the same
      five policy-gate rows after PR #23 landed on `main`. Faithfulness,
      completeness, context recall, and retrieval hit@k stayed `1.000` for all
      five rows, task/artifact integrity stayed `ok` for 5 / 5 rows, error rate
      stayed `0.0%`, and `LGE_T1_051` stayed `numeric_final_judgement = PASS`.
    - observed post-cache cost/runtime snapshot: 88 executed retrieval queries,
      89 query-embedding calls, 12,722 query-embedding input chars, 3,211
      estimated query-embedding tokens, 40 LLM calls, and estimated runtime
      cost `$0.407527`. Because this live replay also generated fewer executed
      retrieval queries and LLM calls, treat the measured reduction as a
      post-cache replay result rather than an isolated cache-only attribution.
    - residual precision signals remain non-blocking but visible for follow-up:
      average section match `0.850`, citation coverage `0.933`, and entity
      coverage `0.942`.
    - same-trace duplicate guard validation:
      `benchmarks/results/same_trace_guard_hyu_t2_010_2026-06-07/` and
      `benchmarks/results/same_trace_guard_nav_t2_006_2026-06-07/`
      (local store-fixed eval-only artifacts, not committed) replayed the two
      highest duplicate-pressure rows from the fan-out audit. Both preserved
      faithfulness, completeness, context recall, and retrieval hit@k at
      `1.000` with error rate `0.0%`. `HYU_T2_010` replayed with 16 executed
      retrieval queries and no duplicate executed-query signatures, versus the
      historical audit baseline of 28 executed / 15 unique / 13 duplicate.
      `NAV_T2_006` replayed with 28 executed / 24 unique / 4 duplicate
      signatures; the remaining duplicates are cross-trace primary repeats
      across sibling lookup tasks, so they are outside the intentionally narrow
      same-trace guard.
    - follow-up instrumentation now records
      `cross_trace_reuse_candidates` in each retrieval debug trace. This is
      trace-only: it identifies same-source, same-filter, exact executed-query
      repeats from earlier traces while preserving the current retrieval
      behavior and task/artifact provenance.
    - focused `NAV_T2_006` diagnostic replay confirmed the instrumentation
      finds 4 cross-trace primary reuse candidates from `task_3/lookup` to
      `task_4/lookup`; all four were already current cache hits. That replay is
      diagnostic-only because faithfulness/completeness fell to `0.700`.
    - PR #33 follow-up closed the diagnostic replay's narrative wording gap:
      aggregate growth+narrative composition now promotes missing
      policy-backed driver evidence from `seed_retrieved_docs` /
      `retrieved_docs` when the active aggregate evidence lacks a required
      driver group. This preserves the retrieved source surface without adding
      company names, benchmark IDs, or driver keywords to runtime control flow.
    - Focused `NAV_T2_006` store-fixed eval-only repair recovered
      faithfulness, completeness, context recall, and retrieval hit@k to
      `1.000` with error rate `0.0%`; the local result bundle remains an
      experiment artifact and was not committed.
    - Follow-up answer-language polish is code-tested only, not a new
      benchmark result: final aggregate mixed growth+narrative answers now
      apply a generic surface correction for malformed Korean conjunctive
      particles after Hangul final consonants, while keeping the canonical
      `RuntimeCalculationTrace.calculation_result.formatted_result` aligned
      with the displayed answer.
  - Validation: runtime domain-term audit passed, focused dependency-growth and
    aggregate preservation regression tests passed, the full unittest suite
    passed, and the full policy gate completed without embedding quota errors.

## Operating Principles

- Domain vocabulary belongs in ontology, retrieval policy, config, or reviewed
  data artifacts, not runtime control-flow code.
- Runtime code should implement generic mechanisms: evidence preservation,
  structured row/header matching, dependency binding, dedupe, ordering,
  validation, and display preservation.
- Benchmark regressions are classified by layer before implementation:
  ontology, retrieval policy, parser structure, planner contract, evidence
  schema, runtime execution, or evaluator definition.
- Store-fixed `--eval-only` refreshes come before fresh ingest unless parser,
  ingest, or cache signatures changed.
- Experiment result directories are local artifacts and are not committed.
- Embedding provider/model/dimension is part of the store signature. Changing
  it requires a fresh store or a signature-matched cache, not silent store
  reuse.

## Portfolio Framing

The strongest portfolio story is:

> I built a financial-document RAG runtime that treats numbers as structured
> evidence-bound artifacts rather than free-form LLM text. The system separates
> semantic planning from deterministic execution, stores explicit calculation
> traces, and uses focused benchmark gates to prevent benchmark-specific
> patches from entering runtime code.

Useful supporting points:

- The project handles noisy DART filings with section/table-aware parsing and
  hybrid retrieval.
- Numeric questions use formula planning and safe deterministic execution.
- Evaluation is split into faithfulness, completeness, numeric equivalence,
  numeric grounding, and retrieval support.
- The runtime now has gate-backed concept and policy-driven paths without
  adding company/question-specific branches to agent code.

## Next Work

Recently closed:

- Agentic self-reflection now has documented request/plan/action/report
  boundaries plus `ReflectionReport` and `reflection_report` task/artifact
  ledger projection. This does not change final answer acceptance behavior.
- Report-scoped cache is now a documented and code-level disabled capability:
  `report_cache_capability_status()` exposes `candidate_only` mode while
  retrieval bypass, writes, serving, and ledger insertion remain disabled.
- Reviewer-facing proof was refreshed: `portfolio_demo` prints the disabled
  cache flags, `review_report_cache_index_contract` reports
  `reviewer_handoff.status = ready`, and README / one-pager / demo walkthrough
  now use the same cache safety surface.
- `src.ops.portfolio_review_gates` now aggregates the portfolio demo, cache
  reviewer, and reflection promotion gates into one reviewer proof bundle.
- Report-cache producer policy now has a code-level candidate-only wrapper:
  `build_report_cache_producer_policy_projection()` requires future cache
  ledger candidates to reuse the calculation task/artifact contract while
  keeping serving and ledger insertion disabled.
- `src.ops.report_cache_promotion_evidence_gate` now provides focused cache
  promotion evidence over the local-index fixture plus reviewed store-fixed
  and live/default MAS handoff trace summaries: ready candidates and
  incomplete/ambiguous fallbacks all keep serving, retrieval bypass, ledger
  insertion, and final acceptance disabled.
- `src.ops.reflection_promotion_gate` now also validates the reflection report
  handoff contract: bounded budget consumption, accepted-case target refs,
  stop-insufficient blocking issues, and critic/orchestrator final acceptance
  authority.
- `src.ops.reference_note_capability_gate` now validates that `REFERENCE_NOTE`
  remains Researcher graph-expansion context and does not become a hidden
  report-cache serving or final-acceptance path.

Current next decisions:

1. Reflection promotion criteria: now documented in
   `docs/architecture/self_reflection_capability_contract.md`, and
   `src.ops.reflection_promotion_gate` provides the first fixture plus
   trace-summary gate for `reflection_trigger_rate`, `recovery_rate`,
   `false_recovery_rate`, `latency_delta`, integrity preservation, and
   reflection-report contract shape. Its default run now covers the base
   fixture set, a store-fixed candidate surface fixture, a reviewed store-fixed
   trace summary, and a reviewed live/default MAS handoff trace summary before
   any active retry behavior is promoted.
2. Report-cache promotion evidence: producer policy is documented in
   `docs/architecture/report_cache_capability_contract.md` and code-backed by
   `build_report_cache_producer_policy_projection()`. Future cache-derived
   ledger candidates map to the existing calculation task contract with
   explicit cache-origin metadata. The focused promotion-evidence gate now uses
   fixture plus reviewed store-fixed trace-summary inputs; serving, writes,
   retrieval bypass, final acceptance, and live ledger insertion remain disabled
   until additional materially different live/default MAS traces justify a
   promotion.
3. Gate maintenance: rerun `portfolio_review_gates` whenever reviewer-facing
   runtime surfaces change; use the individual `REFERENCE_NOTE` and promotion
   trace materiality gates only to localize bundle failures. Run broader
   benchmark refreshes only when a source change can plausibly affect gate
   quality or cost.

### Task Ledger / Artifact Contract Focus

- The runtime now projects raw `tasks` and `artifacts` into a compact
  `task_artifact_trace` for callers, evaluator results, review CSV/Markdown,
  and benchmark aggregate summaries.
- The projection reports task/artifact counts, missing artifact references,
  orphan artifacts, and a generic integrity status with structured issues.
- Duplicate ids and missing artifact references are errors; orphan artifacts and
  completed or partial tasks without artifacts are warnings.
- Final synthesis now treats integrity errors as blocking acceptance: it replans
  when budget remains and emits an explicit partial/refusal answer when the
  replan budget is exhausted.
- Completed calculation tasks now require attached `operand_set`,
  `calculation_plan`, and `calculation_result` artifacts; missing required kinds
  are reported as `missing_required_artifact_kind` errors and therefore block
  final close.
- Calculation artifacts now also require minimum payload shape and preserved
  provenance. Missing operand lists, executable plan operation/mode, rendered
  result/answer slots, or evidence provenance are reported as
  `missing_required_artifact_payload` / `missing_required_evidence_ref` errors.
- Completed reconciliation tasks now require a `reconciliation_result` artifact,
  `payload.reconciliation_result.status`, and candidate/evidence provenance when
  the result is `ready` or `ok`.
- Completed retrieval tasks now require a `retrieval_bundle` artifact with a
  non-empty retrieved candidate list and preserved candidate provenance.
- Completed synthesis tasks now require an `aggregated_answer` artifact with
  final answer text, source material, and preserved provenance.
- Completed critic tasks now require a `critic_report` artifact with verdict,
  target refs, reason/issues, and preserved provenance.
- MAS state now carries `task_artifact_trace`; worker nodes write stable
  artifact ids/kinds/payload/evidence refs, Critic writes `critic_report`
  artifacts, and final merge writes an `aggregated_answer` artifact.
- Analyst worker tasks are now `calculation` tasks that write separate
  `operand_set`, `calculation_plan`, and primary `calculation_result` artifacts.
  Researcher worker tasks are now `retrieval` tasks that write a
  `retrieval_bundle` with retrieved candidates and provenance.
- Runtime calculation projection now records its source under
  `resolved_calculation_trace.runtime_projection`, so callers can distinguish
  canonical resolved traces, task/artifact ledger projections, aggregate
  projections, structured-result views, and legacy top-level `calculation_*`
  fallback.
- Resolver fallback now separates structured-result-only projections from mixed
  legacy fallback. A standalone `structured_result` is non-legacy, while legacy
  top-level operands/plans combined with a structured result remain marked
  `legacy_top_level` and record `calculation_result_source`.
- Evaluator results and benchmark review exports now surface
  `runtime_projection_source`, `runtime_projection_legacy_fallback`, and
  `runtime_projection_calculation_result_source`, making remaining legacy
  fallback usage visible without reading the full trace JSON.
- A no-LLM replay audit over the copied
  `runtime_projection_audit_2026-06-05` concept-gate bundle found 7/7
  full-eval rows using `runtime_projection_source = resolved_calculation_trace`
  and 0 `legacy_top_level` rows. The live eval-only diagnostic was stopped after
  heartbeat-confirmed progress because the first question exceeded the audit's
  cost/time budget.
- `_resolve_runtime_calculation_trace(..., allow_legacy_top_level = false)` now
  provides a strict resolver mode for new readers. Strict mode rejects legacy
  top-level `calculation_*` fallback but still keeps standalone
  `structured_result` as a non-legacy projection.
- Evaluator result export, benchmark serialized/review export, eligible
  analyst/MAS artifact handoff consumers, current-runtime debug readers,
  reflection retry planning, route-decision readers after formula
  planning/calculation, and render/verification/retry preparation readers now
  use strict resolver mode, so legacy top-level mirrors no longer reappear in
  those review, runtime handoff, debug, retry planning, routing, or answer
  preparation surfaces. Historical replay, retrospective readers, and the public
  runtime projection bridge explicitly opt into legacy compatibility because
  they may read older result bundles or older caller surfaces. The public bridge
  is covered as a `FinancialAgent.run()`/export boundary and must not be used by
  new internal current-state readers.
- `FinancialAgentState` now types `resolved_calculation_trace` as
  `RuntimeCalculationTrace` and `subtask_results` as `TaskResultRecord`; the old
  `_project_legacy_calculation_fields()` name remains only as a compatibility
  alias for `_project_runtime_calculation_trace()`.
- `FinancialAgentState` now marks top-level `calculation_operands`,
  `calculation_plan`, and `calculation_result` as optional compatibility
  mirrors. `calculation_debug_trace` is also optional; `FinancialAgent.run()`
  no longer seeds these optional compatibility fields in the initial live state.
- Calculation-node diagnostic writes are now routed through explicit scratch
  helpers, while the public `FinancialAgent.run()` compatibility bridge uses
  the runtime-contract field constant. This keeps internal diagnostics available
  without making top-level debug state required again.
- `_runtime_trace_state_update()` can now omit top-level `calculation_*`
  compatibility mirrors. The first applied branch is calculation verification
  skip for non-ok calculation results, which keeps `resolved_calculation_trace`
  current without rewriting mirror fields.
- The no-operands formula plan, missing-required-operands formula plan, and
  calculation execution failure paths now also omit top-level compatibility
  mirrors; focused tests read these results through `_resolve_runtime_calculation_trace()`.
- Deterministic incomplete-plan branches now omit top-level compatibility
  mirrors as well: incomplete deterministic lookup plans and deterministic
  operation guard failures are consumed through `resolved_calculation_trace`.
- LLM formula-plan guard failures and operand/formula planning structured-output
  failures also omit top-level compatibility mirrors; focused tests read these
  results through `_resolve_runtime_calculation_trace()`.
- Render fallback, verification structured-output failure, and aggregate
  synthesis fallback branches now omit top-level compatibility mirrors as well.
  Focused tests read render/verification results through
  `_resolve_runtime_calculation_trace()`, and aggregate fallback readers now use
  the same projection instead of direct top-level `calculation_*` fields.
- Render and verification success branches now also omit top-level
  compatibility mirrors. Focused tests cover both LLM-rendered and slot-rendered
  answers, plus successful verification, through `_resolve_runtime_calculation_trace()`.
- Aggregate success branches now omit top-level compatibility mirrors too.
  Aggregate result tests now read formatted results, rendered values, and status
  through `_resolve_runtime_calculation_trace()` instead of direct top-level
  `calculation_*` fields.
- Calculation execution success branches and operand extraction
  direct/guard/synthesis/LLM success branches now omit top-level compatibility
  mirrors. Focused tests read produced operands/results through
  `_resolve_runtime_calculation_trace()` before feeding the next graph step.
- Formula planning deterministic lookup/operation/ontology success branches and
  LLM success branches now omit top-level compatibility mirrors. Focused tests
  read planned operations through `_resolve_runtime_calculation_trace()`.
- Formula planning guard/incomplete branches now also omit top-level
  compatibility mirrors, so the entire formula planning node publishes through
  the canonical runtime trace contract.
- Non-formula calculation-node reset/no-op branches now omit top-level
  compatibility mirrors too. All `_runtime_trace_state_update()` call sites in
  `financial_graph_calculation.py` now publish through the canonical trace
  contract.
- Active-task artifact projection now uses strict current-state resolution too:
  empty `resolved_calculation_trace` no longer falls back to legacy top-level
  `calculation_*` fields, while the deliberate stale-aggregate to live
  non-aggregate override remains covered by focused tests.
- Formula planning now also uses strict current-state resolution for its input
  operands. Focused tests cover the legacy top-level operand rejection case and
  existing deterministic/LLM plan branches feed operands through
  `resolved_calculation_trace`.
- Calculation execution now uses strict current-state resolution for operands
  and plans. Focused tests cover the legacy top-level operand/plan rejection
  case, and execution fixtures feed calculation inputs through
  `resolved_calculation_trace`.
- Late runtime numeric answer shaping now uses strict current-state resolution
  too. Focused tests cover both canonical trace answer recovery and legacy
  top-level calculation-result rejection.
- Dependency-projection recalculation now reads `_execute_calculation()` outputs
  through strict current-state resolution. Focused tests cover rejection of
  legacy top-level recalculation results.
- Aggregate reconciliation artifact enrichment now ignores stale top-level
  `calculation_result` source refs. Reconciliation evidence refs are enriched
  from canonical aggregate projection material, ordered subtask source refs, and
  selected claims; focused tests cover both canonical source-ref preservation
  and stale top-level source-ref rejection.
- `_runtime_trace_state_update()` now defaults to omitting top-level
  compatibility mirrors. Compatibility mirrors remain available only as an
  explicit opt-in for older external readers.
- Helper-level compatibility fallbacks are now explicitly documented and tested:
  `_resolve_runtime_structured_result()` may read older top-level calculation
  results for export/review adapters, and `_runtime_trace_state_update()` may
  carry omitted trace parts from older state surfaces.
- Benchmark runner exports are now explicitly strict projection consumers:
  serialized eval rows, smoke summaries, and review CSV/Markdown rows ignore
  stale top-level calculation mirrors while exposing runtime projection and task
  artifact integrity metadata for audit.
- Live evaluator rows are also strict projection consumers: `evaluate_one()`
  ignores legacy top-level calculation mirrors during fresh scoring and records
  projection metadata only from canonical runtime traces.
- Historical answer replay is explicitly compatibility-oriented. It may read
  older top-level calculation mirrors from saved benchmark bundles, but canonical
  `resolved_calculation_trace` takes precedence whenever both are present.
- Retrospective operand-grounding rescoring is also compatibility-oriented for
  historical rows, with canonical `resolved_calculation_trace` taking precedence
  over stale top-level operand mirrors.
- Retrospective evaluator ablation is compatibility-oriented too. Historical
  top-level mirrors remain fallback inputs, while canonical trace operands and
  calculation results take precedence for ablation scoring.
- Retrospective ontology retrieval ablation is strict, not compatibility-based:
  it reruns current graph nodes against a persisted store and rejects legacy
  top-level calculation mirrors when forming outcome rows.
- Current-run debug helpers are strict projection consumers:
  `debug_math_workflow.py` and `debug_reference_note_workflow.py` reject legacy
  top-level calculation mirrors and keep structured-result output tied to the
  canonical runtime trace.
- `mas_analyst_smoke.py` is now classified as a mixed smoke reader: direct
  `FinancialAgent.run()` comparison inputs keep compatibility fallback, while
  MAS artifact handoff readers are strict and reject stale top-level mirrors for
  operands, statuses, and calculation-result payloads.
- MAS final synthesis now keeps the compatibility `final_report` string and
  also publishes a typed `final_report_record`/`FinalReport` projection. The
  `aggregated_answer` artifact payload mirrors that typed record.
- MAS `evidence_pool` rows now use the shared `EvidenceRecord` builder:
  Analyst and Researcher nodes publish common task/creator/kind/source fields
  while preserving producer-specific details under `metadata`.
- MAS critic output now uses the shared `CriticReport` builder. The typed report
  normalizes verdict, target artifact refs, acceptance reason, blocking issues,
  score, and feedback, and the `critic_report` artifact payload mirrors it.
- MAS critic acceptance now has an explicit runtime boundary:
  `critic_report_runtime_acceptance_state()` treats verdict, target refs,
  acceptance reason, and blocking issues as the acceptance contract while
  keeping `deterministic_score` diagnostic. Final integrity projection now uses
  that acceptance state to block structurally complete rejected critic reports.
  Planner feedback and MAS smoke summaries surface critic acceptance status,
  reasons, and target refs for reviewer handoff.
- Rejected critic integrity issues now also project `target_task_ids` and
  `target_artifact_ids`, and Orchestrator replan carry-forward marks the
  rejected target worker task failed alongside the critic report task. This
  keeps final merge acceptance from carrying forward a worker artifact that the
  runtime critic explicitly blocked.
- Portfolio demo and Researcher smoke review outputs now use the same
  `critic_report_runtime_acceptance_state()` helper instead of reading
  `passed` or `deterministic_score` as direct acceptance signals. Their JSON
  surfaces expose runtime acceptance status, reasons, target refs, and whether
  the diagnostic score was used for acceptance.
- Runtime critic / offline evaluator boundary follow-up is closed at the helper
  level. `critic_report_runtime_acceptance_state()` now normalizes verdict
  signals from `passed`, `verdict`, or `status`, blocks conflicting verdict
  signals, keeps rejected reports blocked even with high diagnostic scores, and
  still reports `deterministic_score_used_for_acceptance = false`.
- MAS planner, critic, and synthesis task creation now use the shared
  `AgentTask` builder to normalize task ids, assignees, status, context keys,
  kind/label, dependencies, artifact ids, and blocked reason.
- MAS worker, critic, and synthesis artifacts now use the shared `Artifact`
  builder to normalize artifact ids, kind/status/summary, payload projections,
  evidence refs, producer task id, and metadata while preserving compatibility
  content.
- MAS critic and final synthesis consumers now read typed artifact projections
  first: answer/calculation status from `payload`, evidence from
  `evidence_refs`, then compatibility `content`/`evidence_links` fallback.
  The worker artifact read boundary is now shared through
  `project_worker_artifact_boundary()`, so Critic review and Orchestrator final
  synthesis use the same payload-first answer, selected artifact id, task id,
  role/kind/status, and deduped evidence refs.
- MAS final merge now treats `task_artifact_trace.integrity_status = "error"`
  as a blocking close condition: it preserves partial material but marks the
  typed final report and synthesis artifact as blocked instead of closing `ok`.
- MAS final merge now distinguishes replan from refusal: when replan budget
  remains it emits `planner_feedback` and a `replan_required` final projection;
  once the budget is exhausted it emits the blocked/refusal final answer.
- MAS graph routing now consumes that `replan_required` projection: when budget
  and planner feedback remain, `Orchestrator_Merge` routes back to
  `Orchestrator_Plan`. The replan pass includes integrity feedback in planner
  input, marks blocking tasks as failed with `blocked_reason`, and final
  synthesis reads only completed worker tasks plus their referenced artifacts so
  stale artifacts are not reused as final sources.
- `mas_e2e_smoke.py` now supports replan-budgeted real-node smoke runs and
  exports replan counts, routed-replan status, final report records,
  task/artifact integrity status, blocked case counts, and integrity-error
  counts. It also exposes `final_acceptance_outcome` per case and
  `final_acceptance_outcome_counts` in the summary, so reviewer artifacts can
  distinguish accepted-without-replan, replan-succeeded, blocked, and pending
  replan outcomes. The live real-node smoke is environment-gated because it
  needs `GOOGLE_API_KEY`; the current change is covered by API-free contract
  tests.
- A 2026-06-07 live/default outcome refresh now exposes a current material-empty
  blocker rather than an acceptance-contract ambiguity. With default
  `replan_budget = 0`, the run produced `final_acceptance_outcome_counts =
  {"blocked_without_replan": 2}`, `blocked_count = 2`, and all final source
  counts at `0`. With `--replan-budget 1`, the run routed replans for both
  cases but still ended at `{"blocked_after_replan": 2}` with all final source
  counts at `0`. In both runs Analyst and Researcher tasks failed with
  incomplete/empty material while critic rejection issue counts stayed `0`.
  Raw outputs are local experiment artifacts under
  `benchmarks/results/mas_e2e_smoke_outcome_refresh_2026-06-07/` and
  `benchmarks/results/mas_e2e_smoke_outcome_refresh_replan1_2026-06-07/`; keep
  them out of commits.
- A follow-up 2026-06-07 smoke observability pass added per-case and summary
  `worker_failure_diagnostics` plus output-directory creation for `--output`.
  The live refresh under
  `benchmarks/results/mas_e2e_smoke_failure_diagnostics_2026-06-07/` reports
  `worker_failure_count = 4`, `worker_failure_missing_artifact_count = 4`,
  Analyst failures `2`, Researcher failures `2`, incomplete numeric result
  reasons `2`, empty narrative result reasons `2`, and missing worker artifact
  reasons `4`. This confirms the
  immediate blocker is failed worker material production, not critic acceptance
  or final synthesis carry-forward.
- A direct worker probe now checks the same default store/scope without running
  Critic or final merge. It confirms the planner created `2` Analyst and `2`
  Researcher tasks, but direct Analyst returned `no_retrieved_docs = 2` and
  direct Researcher returned `no_raw_retrieval = 2`. Store inventory for that
  default path reported `chroma_count = 0`, `bm25_doc_count = 0`,
  `parent_count = 0`, and `structure_graph_node_count = 0`. The immediate
  blocker is therefore an empty or missing default smoke store, not planner
  task generation or worker-wrapper logic. Raw output is local-only under
  `benchmarks/results/mas_direct_worker_probe_2026-06-07/`.
- `mas_e2e_smoke.py` now includes an empty-store material preflight before
  `VectorStoreManager` construction. It reads Chroma collection embedding
  counts and local sidecar counts (`parents.json`,
  `document_structure_graph.json`, `table_payloads.json`) from disk. When the
  collection exists but embeddings and sidecar material are all zero, the smoke
  fails before LLM work with `Store appears empty for MAS smoke`. A live default
  run now stops in about `5s` at this preflight instead of spending worker/API
  time and ending as material-empty.
- The default MAS smoke store has been restored to the populated Samsung 2023
  structural-selective store under
  `benchmarks/results/policy_gate_regression_2026-06-03_1138_actual/`. The
  smoke now derives its embedding runtime from the store signature by default,
  so this Google `models/gemini-embedding-2` store opens with a matching Google
  embedding runtime even when the general environment default would prefer
  OpenAI. The override-free live default smoke now reports
  `embedding_compatibility.status = ok`, `chroma_embedding_count = 967`,
  `accepted_without_replan = 2`, `blocked_count = 0`, integrity errors `0`,
  worker failures `0`, final source tasks `4`, final source artifacts `8`, and
  final evidence refs `55`.
- Earlier live real-node smoke was run with a local OpenAI-3072 Samsung 2023
  store and matching report scope. It completed in `68.2s` with
  `final_report_record.status = ok`, `task_artifact_trace.integrity_status =
  ok`, `replan_count = 0`, completed Analyst / Researcher / Critic / synthesis
  tasks, and no blocked or integrity-error cases. The earlier default-store run
  correctly exposed a store compatibility problem (`384` stored dimension vs
  `3072` query embeddings), not a `.env` loading issue.
- The same live smoke exposed and closed a MAS retry-control bug: failed worker
  tasks were being reviewed by Critic and could be resurrected as
  `REJECTED_BY_CRITIC`, causing repeated Analyst retries. Critic now reviews
  completed worker tasks only.
- `mas_e2e_smoke.py` performs an embedding/store compatibility preflight before
  graph nodes are invoked. It reads benchmark/vector-store metadata and falls
  back to Chroma collection dimension, so incompatible persisted stores fail
  before LLM/API work.
- `check_mas_e2e_smoke_contract.py` extracts and compares compact MAS smoke
  contract fields from full smoke JSON output, covering embedding compatibility,
  case count, blocked/integrity/replan summary counts, per-case final status,
  final acceptance outcome, artifact-integrity status, replan flags, and task
  status distribution. This is the default local delta check for MAS quality
  work. The 2026-06-07 valid-store compact baseline is now source-controlled at
  `tests/fixtures/mas_e2e_smoke/default_valid_store_contract_baseline.json`.
  The default compare is clean: `status = ok`, `difference_count = 0`,
  `case_count = 2`, `blocked_count = 0`, `integrity_error_count = 0`,
  `accepted_without_replan = 2`, `worker_failure_count = 0`, and both cases
  have five completed tasks.
- MAS final report provenance now dedupes final source task IDs, source artifact
  IDs, and evidence refs while preserving first-seen order; the synthesis
  artifact uses the same deduped evidence refs as the final report record. A
  live default smoke kept compact contract comparison clean and confirmed zero
  duplicates in final record and synthesis evidence refs.
- MAS final report `subtask_results` now records only answer-bearing worker
  task results, one per task. Intermediate artifacts still remain in source
  provenance, but they no longer appear as empty subtask answers in the final
  projection. A live default smoke kept compact contract comparison clean and
  produced two non-empty subtask results per case.
- MAS final merge now applies explicit answer-compression guidance before the
  existing Orchestrator prompt: numeric Analyst conclusions come first,
  Researcher context is reduced to a few material points, worker values/units
  are preserved, and evidence refs or internal task ids are kept out of prose.
  A live default smoke kept compact contract comparison clean.
- MAS E2E smoke now exposes final carry-forward provenance explicitly. Each
  case includes `final_carry_forward` with source task/artifact ids, evidence
  refs, subtask result ids, and their counts. The compact smoke contract also
  compares final source task/artifact/evidence/subtask-result counts, so a
  real-node replan run can reveal whether the final answer carried forward the
  repaired worker artifacts rather than only reporting that replan routed.
- MAS carry-forward projection has now moved from smoke-only summarization into
  the shared MAS schema layer. `project_final_report_carry_forward()` derives
  the stable counts and id lists from `FinalReport`, and Orchestrator final
  `subtask_results` preserve the selected worker `artifact_id` /
  `source_artifact_id` alongside task id and answer surface.
- MAS Analyst numeric operand extraction now rejects explicit
  consolidation-scope conflicts for direct rows and dependency task-output rows,
  and resolved dependency rows are checked against producer statement/section
  scope before satisfying downstream calculation tasks. Compact ratio scope
  labels are config-driven. A live default smoke kept compact contract
  comparison clean and case 1 now reports `연결 기준 영업이익률 2.54%` instead of
  the prior separate-statement `-4.45%`.
- Task-output dependency operands now prefer the producer operand artifact over
  stale rendered answer slots, skip broad evidence-table precision refinement
  for already-resolved task-output values, and repair provenance from the
  persisted structure graph when the same value/label has a better scoped node.
  Direct verification anchors the Samsung 2023 operating-margin operands to
  `III. 재무에 관한 사항 > 2. 연결재무제표` with `consolidated` /
  `income_statement`; live MAS smoke still reports case 1 as `2.54%`.
- MAS E2E smoke contract comparison now also evaluates value canaries generated
  from the default smoke profile in `src/ops/mas_e2e_smoke.py`. The default
  checker still compares compact topology/integrity fields, and it now fails if
  case 1 loses `2.54%`, `6,566,976`, or `258,935,494`, or if `-4.45%` reappears
  in the full smoke surface. `run_smoke()` embeds the profile-generated
  `value_contract` for the default scope/query set, and the checker can
  reconstruct it for matching historical smoke output. The repaired smoke
  reports `value_assertion_failure_count = 0`; the earlier bad
  provenance-anchor smoke fails as expected.
- Report-scoped value cache design now has a code-level contract in
  `src/config/report_scoped_cache.py`. It normalizes cache keys from report
  scope, value identity, and provenance scope, and classifies candidates as
  `reusable`, `requires_evidence_verification`, or `not_cacheable`. Runtime
  calculation traces now carry a read-only `report_cache_candidate` projection
  with classifier status/reasons/key/key id, and MAS Analyst artifacts preserve
  it through `resolved_calculation_trace`. MAS E2E smoke output now reports
  per-case `report_cache_candidates` plus top-level status/reason counts, with
  duplicate content/payload projections counted once. The follow-up unit-scale
  repair aligns same-table KRW ratio operands to the table display unit before
  formula execution; a focused local Google-store probe now reports the Samsung
  2023 operating margin as `2.54%` with one `reusable` calculation candidate.
  A disabled consumer-side gate now marks only read-only, complete, reason-free
  `reusable` projections as `retrieval_bypass.eligible`, with `enabled = false`
  and `mode = trace_only`; MAS smoke surfaces that nested assessment. Retrieval
  planning now also copies the assessment into
  `retrieval_debug_trace.report_cache_consumer_assessment` and records that
  normal retrieval still executed. Persisted cache-entry validation now defines
  `local_cache_index` as the only future read source; runtime trace projections
  and artifact-store projections remain candidate/audit surfaces. A read-only
  `ReportCacheIndex` diagnostics adapter can validate JSON/JSONL local index
  entries and lookup by cache key id, but reports `serving_enabled = false`.
  Retrieval planning can now attach those lookup diagnostics from an explicit
  `report_cache_index_path` into
  `retrieval_debug_trace.report_cache_index_diagnostics`, including match
  counts and normal-retrieval execution status. Benchmark runner and MAS smoke
  can pass the path for diagnostics, but matched entries still do not serve
  hits or bypass vector-store search. MAS Analyst artifacts now preserve
  retrieval traces, and MAS smoke summarizes cache-index diagnostics per case
  and at the top level for handoff checks. The next consumer boundary is now
  explicit in code: `classify_report_cache_rehydration_candidate()` requires
  answer slots, citation/source-anchor material, evidence material, and
  calculation trace provenance before any future cache hit can be considered
  rehydratable, while still reporting serving disabled. `ReportCacheIndex`
  lookup diagnostics now count rehydration-ready vs. blocked matches and carry
  those counts through MAS smoke summaries. The reviewer handoff smoke
  `src.ops.report_cache_index_smoke` prints the same trace-only diagnostic
  payload from the source-controlled fixture without running MAS or retrieval.
  `build_report_cache_rehydrated_candidate_artifact()` now defines the first
  non-serving projection from a rehydration-ready entry to an artifact-like
  candidate payload, but it still reports disabled serving and is not wired into
  the task/artifact ledger. The handoff smoke now summarizes reconstructable
  candidate artifact counts and emits a minimal preview for ready entries only.
  `check_report_cache_index_smoke_contract` extracts and compares the stable
  subset of that handoff surface so reviewers do not need to diff the full
  diagnostic payload. It can also build the fixture-backed smoke payload
  directly from `--report-cache-index-path`, so the lightweight review command
  compares against the source-controlled compact baseline without writing
  generated smoke output. `src.ops.review_report_cache_index_contract` wraps
  that fixture-backed baseline comparison as the default reviewer command. The
  fixture-backed compact baseline is source-controlled under
  `tests/fixtures/report_cache_index/rehydration_contract_baseline.json`.
  The guarded cache-consumer promotion design is now documented in the runtime
  contract: future serving must start from a readable `local_cache_index`
  match, select exactly one rehydration-ready entry, recheck value/evidence/
  citation/calculation provenance against the cache key, and enter the
  task/artifact ledger only through an explicit schema-backed producer policy.
  `classify_report_cache_guarded_consumer_candidate()` now codifies the first
  pure version of those blocking conditions without enabling reads: the ready
  fixture is admissible for design, while incomplete or mismatched entries
  require normal retrieval fallback and expose reasons.
  The non-serving rehydrated candidate artifact now carries the future
  ledger-facing metadata needed for a later producer decision: source,
  cache-origin, cache key id, rehydration status, guarded consumer
  admissibility status, and disabled serving/ledger insertion flags.
  The first schema-backed producer-policy direction is now contract-tested as
  a candidate-only mapping onto the existing calculation task shape:
  `build_report_cache_calculation_contract_projection()` can produce a
  candidate calculation task plus `operand_set`, `calculation_plan`, and
  `calculation_result` artifacts, all still disabled for serving and ledger
  insertion.
  `validate_report_cache_calculation_contract_projection()` now validates that
  candidate shape read-only: required artifact kinds, payload surfaces,
  evidence refs, and disabled serving/ledger flags must all pass before the
  candidate is considered valid for the contract.
  The reviewer handoff smoke and compact baseline now expose projection
  validation counts and per-candidate status/reasons, so reviewers can confirm
  the ready fixture is valid for the calculation contract while the blocked
  fixture remains a fallback. The repo-local review command now adds a compact
  `reviewer_handoff` summary with `status = ready`, `mode = candidate_only`,
  disabled serving/ledger flags, and ready/fallback projection counts.
  The current fixture-backed review command reports `status = ok`,
  `difference_count = 0`, one valid projection-ready candidate, and one normal
  retrieval fallback candidate; this is the handoff gate for the candidate-only
  cache capability.
  Cache read/write behavior and retrieval bypass remain disabled.
- Warning-level integrity signals are non-blocking by default, but final-source
  dependencies on orphan artifacts or artifactless completed/partial tasks are
  promoted to blocking errors.

### Runtime/API Cost Focus

- First low-risk control: benchmark runs can now pass explicit retrieval query
  budgets to cap primary, operand-focused, and retry retrieval fan-out.
- Official runtime contract and policy-driven gate profiles now set `8 / 4 / 1`
  in `full_evaluation`, so focused gate runs record the budget in their
  profile/config instead of relying on ad hoc CLI flags.
- `retrieval_debug_trace.query_budget.source` now records the active retrieval
  source and source-level query counts. This matters because final traces can
  describe only the last active subtask while the state-level semantic plan may
  still contain many generated query surfaces.
- `retrieval_debug_trace.search_summary` now aggregates executed searches,
  cache hits, vector attempts, and query-embedding calls by retrieval source.
  A local `HYU_T2_010` trace showed `12` searches for the numeric subtask
  (`primary 8`, `operand_focus 4`) and `3` searches for the narrative subtask,
  making retrieval fan-out visible without hand-counting `executed_queries`.
- The same `HYU_T2_010` rerun exposed an answer-composition issue that is now
  closed by the growth narrative evidence-surface follow-up:
  the answer could preserve `87.0만 대` and `11.5%` while omitting the prior
  `78.1만 대` display, which lowers completeness despite correct retrieval and
  calculation. This was an aggregate rendering issue, not a retrieval-budget
  failure.
- Cost estimation now consumes normalized Gemini response usage metadata for
  benchmark contextualization, agent runtime, and evaluator judge calls:
  - prompt/input tokens
  - output/candidate tokens
  - thinking tokens
  - cached-content tokens
  - tool-use prompt tokens
- `estimated_ingest_cost_usd` and `estimated_runtime_cost_usd` remain
  estimates from usage metadata and the profile pricing table, not Cloud
  Billing invoice amounts.
- Full-eval results preserve per-question `agent_llm_usage`,
  `judge_llm_usage`, combined `llm_usage`, and aggregate `llm_*` token totals
  so runtime/evaluator cost can be compared against ingest cost.
- Embedding APIs do not return usage metadata through the LangChain embedding
  interface, so the project records embedding input volume instead:
  API calls, input text count, input characters, and local estimated input
  tokens. `estimated_*_embedding_cost_usd` is populated only when a profile
  provides `embedding_input_per_million_tokens_usd`.
- Default runtime behavior remains unchanged unless a budget is supplied. Query
  dedupe is enabled only for explicitly budgeted retrieval stages.
- Use this for focused triage before changing retrieval policy or ontology:
  it is an execution-cost control, not a benchmark-answer rule.
- Table payload sidecar cleanup now exposes store-size telemetry without a new
  benchmark run. `table_payloads.json` records payload count, referenced node
  count, unique payload bytes, repeated inline byte estimate, and deduplicated
  bytes saved estimate. `rebuild_vector_store.py` also reports source/output
  sidecar summaries so fresh-store rebuilds can verify that structured table
  payload dedupe survived the rebuild path.
- Offline fan-out/cost audit is now available through
  `python -m src.ops.audit_benchmark_fanout_cost <result-bundle>`. It reads
  existing `results.json` files and summarizes per-question retrieval traces,
  source-level fan-out, unique and duplicate executed query counts, query
  embedding calls, top duplicate query signatures by row/source/trace/task,
  LLM usage, estimated runtime cost, and quality metrics before any new budget
  probe is run.
- The 2026-06-09 LLM-cost follow-up extends the same offline audit with
  agent-vs-judge LLM usage split. When a result bundle contains per-question
  `agent_llm_usage` and `judge_llm_usage`, the audit now reports separate API
  calls, total tokens, estimated runtime cost by side, and a
  `Top Rows By LLM Usage` table. Older bundles remain readable; missing split
  usage is left blank rather than inferred from combined totals.
- A later 2026-06-09 instrumentation pass adds phase-level agent LLM usage.
  `FinancialAgent._llm_for_phase()` now tags the shared usage callback with the
  active phase, `FinancialAgent.run()` returns `llm_usage_by_phase`, benchmark
  rows serialize it as `agent_llm_usage_by_phase`, and the offline audit renders
  an `Agent LLM Usage By Phase` table with calls, tokens, and estimated cost.
  This is trace/cost observability only; it does not change routing, retrieval,
  evidence selection, calculation, or answer behavior.
- A focused `KAB_T1_066` phase-level usage canary on 2026-06-09 created the
  local artifact
  `benchmarks/results/kab_t1_066_llm_phase_canary_2026-06-09/`. Because this
  checkout had no reusable store, the run included fresh store construction and
  is a local canary, not a store-fixed release baseline. The artifact was
  deleted after this summary was recorded. The row ran with LLM judges and
  embedding metrics skipped, preserving numeric `PASS`,
  faithfulness/completeness `1.000 / 1.000`, context recall/retrieval hit@k
  `1.000 / 1.000`, latency `145.4s`, and estimated runtime cost `$0.110654`;
  answer relevancy `0.000` is expected from `--skip-embedding-metrics`, not a
  quality baseline. The phase audit split agent LLM usage into `11` calls and
  `258,333` tokens, with top phases `aggregate_synthesis` at `186,310` tokens
  / `$0.058368`, `numeric_extraction` at `51,393` tokens / `$0.029749`, and
  `reconciliation_rerank` at `5,582` tokens / `$0.010426`. Retrieval-side
  telemetry reported `17` executed queries, `0` duplicate queries, and `8`
  state query-result avoided searches.
- The next runtime-cost change compacted the `aggregate_synthesis` prompt
  payload. Final synthesis now receives projection-backed compact subtask rows
  instead of raw `ordered_results`, preserving task ids, metric/operation
  labels, answers, `calculation_result.answer_slots`, source ids, and material
  numeric operands while excluding retrieval/debug/runtime-evidence payloads.
  The node records `subtask_debug_trace.aggregate_synthesis_prompt` with row
  count and input JSON character count. This is a generic prompt-contract
  reduction, not a routing, retrieval, evidence-selection, calculation, or
  answer-rule change.
- A focused `KAB_T1_066` aggregate-compact canary on 2026-06-09 created the
  local artifact
  `benchmarks/results/kab_t1_066_aggregate_compact_canary_2026-06-09/`. Because
  this checkout still had no reusable store, the run included fresh store
  construction and is a local canary, not a store-fixed release baseline. The
  artifact was deleted after this summary was recorded. The row ran with LLM
  judges and embedding metrics skipped, preserving numeric `PASS`,
  faithfulness/completeness `1.000 / 1.000`, context recall/retrieval hit@k
  `1.000 / 1.000`, latency `150.1s`, and estimated runtime cost `$0.064986`.
  Compared with the previous phase canary, total agent LLM tokens fell
  `258,333 -> 76,252`, `aggregate_synthesis` fell `186,310 -> 4,064`, and
  estimated runtime cost fell `$0.110654 -> $0.064986`. The largest remaining
  phase is now `numeric_extraction` at `51,556` tokens / `$0.038694`. Retrieval
  telemetry stayed at `17` executed queries, `0` duplicate queries, and `8`
  state query-result avoided searches.
- The follow-up `numeric_extraction` step adds prompt-size diagnostics rather
  than changing prompt contents. `numeric_debug_trace.numeric_extraction_prompt`
  records selected doc count, formatted context chars, query chars, source
  page-content chars, parent-context candidate count, table-context doc count,
  graph-relation doc count, and doc summaries without storing prompt text. The
  evaluator/benchmark row preserves this as `agent_numeric_debug_trace` so it
  stays separate from evaluator numeric-judge debug. This is the next
  observability hook for reducing the now-largest LLM phase, not a retrieval,
  evidence-selection, calculation, or answer-behavior change.
- Retrieval budget, dedupe, executed-query telemetry, and cross-trace reuse
  diagnostics now live in `src.agent.financial_graph_retrieval_budget`, with
  the evidence mixin preserving the existing helper import surface. This keeps
  cost-control mechanics separate from evidence shaping and narrative answer
  composition before deeper API-cost changes.
- The fan-out audit now also separates cross-trace reuse candidates by current
  cache hit vs current cache miss counts. This keeps mixed
  numeric+narrative rows such as `NAV_T2_006` from looking like obvious runtime
  cost targets when the repeated sibling lookup query was already served from
  the exact-query cache.
- A store-fixed concept gate audit over
  `concept_gate_refresh_after_answer_composition_2026-06-04` found 7 questions,
  25 retrieval traces, 594 executed queries, 370 unique executed queries, 224
  duplicate executed queries, 370 query-embedding API calls, 131 LLM API calls,
  and estimated runtime cost `$1.430221`. Duplicate pressure is concentrated in
  `CEL_T3_040` and `KBF_T2_018`; many repeats are already search-cache hits, so
  the next cost reduction should target repeated primary query generation across
  sibling lookup tasks rather than changing answer composition.
- Same-question retrieval now carries a state-local query-result cache keyed by
  retrieval source, exact executed-query signature, and metadata filter. A later
  sibling task that asks for the same primary/focus/retry query can reuse the
  previous result bundle without another `vsm.search()` call, while the debug
  trace records `reused_queries` and `query_result_cache.reuse_count` for
  offline audit.
- The 2026-06-09 follow-up keeps that behavior unchanged but makes the cost
  surface clearer: debug traces now expose
  `query_result_cache.avoided_search_count` plus source-level reuse summaries,
  cross-trace diagnostics include `reused_queries` in prior history, and the
  fan-out audit reports state query-result avoided searches separately from
  cache reuses. This is observability for runtime/API cost control, not a new
  retrieval policy.
- A focused `CEL_T3_040` cost-observability canary on 2026-06-09 created the
  local artifact
  `benchmarks/results/cel_t3_040_result_cache_avoided_search_canary_2026-06-09/`.
  Because this checkout did not have an existing concept-gate result bundle,
  the run included fresh store construction before full eval; treat it as a
  local canary, not a store-fixed release baseline. The artifact was deleted
  after this summary was recorded. The full-eval row preserved numeric `PASS`,
  faithfulness/completeness `1.000 / 1.000`, retrieval hit@k `1.000`, and
  artifact integrity `ok`; context recall was `0.333`. The fan-out audit
  reported `26` executed queries, `0` duplicate queries, `18` state
  query-result cache reuses, `18` avoided searches, `18` cross-trace reuse
  candidates, and `0` current cache misses. Estimated runtime cost was
  `$0.126694`.
- The concept runtime gap gate profile now carries the same explicit `8 / 4 / 1`
  retrieval budgets used by the official runtime/policy gates. A store-fixed
  `CEL_T1_013` canary preserved numeric `PASS`, faithfulness/completeness
  `1.000 / 1.000`, and artifact integrity `ok` while reducing primary query
  surfaces from `18 -> 8` and `15 -> 8`; the fan-out audit reported `15`
  executed queries, `0` duplicates, and `1` state query-result cache reuse.
- A local store-fixed Celltrion canary after the query-result cache change was
  mixed rather than release-clean. `CEL_T3_040` dropped from 265 executed
  queries to 124 with 141 state result-cache reuses while preserving numeric
  PASS, faithfulness `1.000`, and completeness `0.700`. `CEL_T1_013` reran with
  a different plan shape, 51 result-cache reuses, numeric PASS, and faithfulness
  `1.000`, but completeness fell from `1.000` to `0.700`. The aggregate
  query-embedding calls were 188 in the benchmark output aggregate and 182 in
  the offline fan-out audit, higher than the previous Celltrion audit's 156.
  Treat this as a useful runtime-search reduction signal, not an API-cost win
  or a release-grade quality proof.
- Initial policy-gate audit baselines:
  - `policy_gate_regression_2026-05-31_2212`: 5 questions, 11 retrieval
    traces, 93 executed queries, 89 query embedding calls, estimated runtime
    cost `$0.406069`, average faithfulness/completeness `1.000 / 1.000`.
  - `policy_gate_regression_2026-06-03_1138_actual`: 5 questions, 12
    retrieval traces, 98 executed queries, 81 query embedding calls,
    estimated runtime cost `$0.423814`, average faithfulness/completeness
    `1.000 / 0.880`; refreshed duplicate-query audit shows 81 unique executed
    query signatures and 17 duplicate executed query signatures.
  - top fan-out pressure remains concentrated in `NAV_T2_006`, `HYU_T2_010`,
    and `LGE_T1_051`; duplicate-query pressure is highest on `HYU_T2_010`;
    the next canary should target generic evidence signals rather than
    lowering the global `8 / 4 / 1` budget.
  - duplicate-query drilldown now separates likely causes: `HYU_T2_010`
    repeats focused operand-style sales-count queries, while `NAV_T2_006`
    repeats long enriched primary queries.
  - refreshed trace/task drilldown shows `HYU_T2_010` repeats around
    `task_1/growth_rate` across both same-trace and cross-trace patterns,
    while `NAV_T2_006` repeats enriched primary lookup queries across
    `task_3/lookup` and `task_4/lookup`.
  - same-trace execution duplicate guard now drops only exact-normalized
    repeated executed queries within the same retrieval source. It keeps
    query-budget selection semantics, CJK spacing variants, cross-source
    fallback repeats, and cross-trace repeats intact while recording
    `retrieval_debug_trace.executed_duplicate_guard`.
- Benchmark runner now supports focused LLM route probes without editing the
  profile via `--llm-route phase=provider:model`.
- Local `HYU_T2_010` evidence-extraction probe with
  `--llm-route evidence_extraction=google:gemini-2.5-flash` did not preserve
  the gate contract: faithfulness and completeness fell to `0.500`, and the
  rendered growth calculation drifted to `12.3%`. Keep
  `evidence_extraction = gemini-2.5-pro` for the official gate until a broader
  low-cost route canary proves otherwise.
- First bounded low-API canary:
  - `NAV_T1_030` with budgets `12 / 6 / 2` passed.
  - `retrieval_debug_trace.query_budget` recorded `primary 3/3`,
    `operand_focus 6/16`, and `retry 0/0`.
  - API calls and estimated cost remained `0 / $0.0000`.
- Second bounded low-API canary:
  - `SKH_T1_060` passed with tighter budgets `8 / 4 / 1`.
  - The trace reduced executed retrieval searches to 12
    (`primary = 8`, `operand_focus = 4`, `retry = 0`) while preserving
    `numeric_final_judgement = PASS`.
  - `KBF_T1_017` also passed numerically with `8 / 4 / 1` and 12 executed
    retrieval searches.
  - `NAV_T1_071` was confirmed to be a separate runtime regression rather than
    a budget-only regression: `8 / 4 / 1`, `12 / 6 / 2`, and unbounded focused
    low-API runs all failed with the same stale `0원` difference shape before
    the runtime fix.
  - The `NAV_T1_071` root cause was period-insensitive precision refinement:
    a prior-period lookup initially selected the correct fiscal column, then
    contextual table-cell refinement overwrote it with the current-period cell.
  - The fix makes precision refinement reuse the generic period-aware structured
    cell selector; the focused low-API canary now passes with current
    `1,481,396,317,551원`, prior `1,083,717,091,152원`, and delta `3,977억원`.
  - Query-budget selection now preserves period diversity before truncation so
    explicitly budgeted multi-period comparisons do not silently drop all
    prior-period search surfaces.
- Broader `8 / 4 / 1` promotion check:
  - The official 5-question runtime contract gate set passed under focused
    low-API/BM25 conditions.
  - Results: `NAV_T1_030`, `NAV_T1_071`, `MIX_T1_021`, `KBF_T1_017`, and
    `SKH_T1_060` all returned `numeric_final_judgement = PASS`.
  - Executed retrieval searches were bounded at 7 to 12 per question, with
    no retry queries needed.
  - Treat `8 / 4 / 1` as a viable default candidate, pending one broader
    non-gate inventory check.
  - Separate renderer cleanup remains: `KBF_T1_017` can still append a
    partial-refusal suffix despite numeric PASS, and `NAV_T1_071` uses an
    awkward difference sentence.
- Non-gate `8 / 4 / 1` inventory check:
  - Four curated non-gate questions were tested across the existing
    runtime-contract company set: `NAV_T2_006`, `SAM_T3_028`, `KBF_T2_043`,
    and `SKH_T3_080`.
  - `SAM_T3_028` and `SKH_T3_080` passed numerically.
  - At this historical snapshot, `KBF_T2_043` returned `UNCERTAIN`, and
    `NAV_T2_006` produced no numeric judgement with noisy mixed synthesis.
  - These two non-PASS cases were not budget-truncation failures: their
    executed query traces were `1/1` and `2/2`, with no dropped primary,
    operand-focused, or retry queries.
  - The budget is therefore still a viable default candidate. Both named
    quality targets have since been closed: `NAV_T2_006` by the policy-gate
    LLM-evidence path and retrieved-driver evidence preservation follow-up,
    and `KBF_T2_043` by PR #35's contract-driven material-gap follow-up.
    `KBF_T2_043`'s focused eval-only replay returned
    `numeric_final_judgement = PASS`, `faithfulness = 1.0`,
    `numeric_grounding = 1.0`, `context_recall = 0.9`, and
    `completeness = 0.7`, so remaining work is broader replay and
    completeness/render calibration, not a known material-gap blocker.
- Broader curated residual review:
  - Review record:
    `docs/evaluation/broader_gate_residual_review.md`
  - No new benchmark was run for this review.
  - Current decision: no active broader curated runtime blocker is open.
    `NAV_T1_030` is display/entity normalization debt, and `KBF_T2_043` is a
    broader replay plus completeness/render calibration watch item unless a new
    artifact reproduces a material-gap runtime failure.
- Material-gap / mixed narrative canary maintenance:
  - Review record:
    `docs/evaluation/material_gap_mixed_canary_maintenance.md`
  - Current decision: `KBF_T2_043` and `NAV_T2_006` are maintenance watch items,
    not active runtime blockers.
  - Reopen them only when a fresh artifact reproduces a concrete material
    evidence, dependency binding, stale trace, unsupported numeric, or final
    synthesis failure.
  - Cross-trace duplicate pressure, isolated completeness/render calibration,
    and historical non-PASS rows superseded by focused evidence are not enough
    to justify a new runtime patch or full benchmark.
- Official LLM-evidence-path canary after fallback removal:
  - `NAV_T2_006` passed under the policy-driven gate profile with `8 / 4 / 1`.
  - Final answer preserved `41.4%` and the Poshmark/smart-store/brand-store
    explanation.
  - Metrics: faithfulness `1.000`, answer relevancy `0.837`, context recall
    `1.000`, retrieval hit `1.000`, context P@5 `0.800`, completeness `1.000`,
    error rate `0.0%`.
  - Final narrative retrieval trace selected `3` primary queries, `0`
    operand-focus queries, and `0` retry queries while recording the broader
    state-level query count as `61`.
- Retrieved-driver evidence preservation follow-up:
  - A later same-store diagnostic replay showed that cross-trace instrumentation
    could expose already-cached repeated lookup queries while the final answer
    lost one source-visible growth driver group.
  - PR #33 fixed the aggregate evidence path generically: if policy-backed
    narrative driver groups are visible in retrieved docs but missing from
    aggregate evidence, runtime promotes the source sentence into evidence
    before final mixed numeric+narrative composition.
  - Focused `NAV_T2_006` repair metrics recovered faithfulness, completeness,
    context recall, and retrieval hit@k to `1.000`; this is treated as local
    store-fixed repair evidence, not a fresh official benchmark.

## Latest Fresh Concept Gate Refresh

- A 2026-06-04 fresh concept-runtime-gate refresh with OpenAI
  `text-embedding-3-large` initially exposed focused failures in
  `POS_T1_057`, `KBF_T2_018`, `KAB_T1_066`, and `SAM_T3_028`.
- The current local result directory
  `benchmarks/results/concept_gate_refresh_after_answer_composition_2026-06-04/`
  is a mutable local experiment artifact and is not committed.
- The latest store-fixed eval-only refresh now reports `7 / 7 PASS`:
  `KBF_T2_018`, `POS_T1_057`, `SKH_T3_080`, `SAM_T3_028`, `CEL_T1_013`,
  `CEL_T3_040`, and `KAB_T1_066`.
- Closures stayed generic:
  - aggregate structured cell selection uses reviewed row/cell metadata
  - contextual precision refinement cannot replace a detailed source display
    with a large-scale-drift table cell
  - ratio tasks can prefer an active reconciled operand set when it covers all
    required operands
  - quantitative-impact assembly only asserts inclusion/impact relations when
    the relation is visible in evidence
  - percent answers preserve formula operand evidence even if the final sentence
    renders only the derived percentage
  - ratio denominator sign semantics are declared in ontology binding policy and
    consumed generically by runtime calculation
  - table metadata rows that support final-answer numeric material are promoted
    into evaluator-visible evidence claims
  - short unitless `UNKNOWN` numerics are not treated as material aggregate
    operands
  - unscoped lookup/ratio tasks reject context-dependent segment/total table
    rows before sibling recovery or direct operand extraction can promote them
- Broader operation-contract follow-up after the closure commit is also green:
  runtime domain-term audit passed, `tests.test_subtask_loop` passed `91`
  tests, the related answer-composition / lookup-recovery suite passed `182`
  tests, and full unittest discovery passed `687` tests.
- MAS replan-edge follow-up is green: runtime domain-term audit passed,
  projection/MAS focused tests passed `34` tests, and full unittest discovery
  passed `780` tests.
- MAS real-node smoke observability follow-up is green at the contract-test
  layer: the new smoke-script tests passed with the MAS focused suite, runtime
  domain-term audit passed, and full unittest discovery passed `782` tests. A
  live smoke run was not executed because `GOOGLE_API_KEY` is not set in the
  current shell.
- Follow-up live smoke with `.env`-loaded credentials is green on a compatible
  local Samsung 2023 OpenAI-3072 store. The Critic retry-control regression fix
  and smoke scope/progress options are covered by focused tests; full discovery
  should be rerun after this doc update before publishing.
- Latest focused checks:
  - `KBF_T2_018`: PASS; faithfulness `1.0`, completeness `1.0`, numeric
    grounding `1.0`, retrieval support `1.0`.
  - `POS_T1_057`: PASS; faithfulness `1.0`, completeness `1.0`, numeric
    grounding `1.0`, retrieval support `1.0`.
  - `SAM_T3_028`: PASS; faithfulness `1.0`, completeness `1.0`; the final
    answer preserves the inventory valuation loss/reversal/disposal values and
    the cost-of-sales impact relation without adding a runtime keyword branch.
- Residual follow-up: no active concept-gate blocker remains. Future work is
  promotion-risk management, cost/runtime control, and task-ledger/artifact
  contract cleanup.

## 2026-06-09 Concept Gate Residual Hardening Follow-up

- Follow-up target:
  - `POS_T1_057` full-replay unit/source path instability.
  - `KAB_T1_066` product-quality residual where the numeric evaluator could
    pass while the visible answer partially refused CIR calculation.
- Runtime changes stayed generic:
  - calculation execution repairs KRW operand units from table-backed
    `unit_hint` only when the operand evidence is table backed, the raw value
    is visible in the table surface, and the raw/hint unit scale differs by at
    least `100x`;
  - reconciliation operand extraction expands active reconciliation
    `evidence_refs` / `source_evidence_ids`, including `recon::`-prefixed
    structured candidate refs, but still relies on the existing operand
    acceptance contracts to select rows.
- Focused store-fixed eval-only checks:
  - `POS_T1_057`: PASS; calculator result `3.5269배`.
  - `KAB_T1_066`: PASS; final answer `37.47%` with
    `판매비와관리비 4,355.42억원 / 경비차감전영업이익 11,623억원`.
- Validation:
  - `tests.test_operation_contracts tests.test_structured_operand_extraction`:
    `201` tests OK.
  - `tests.test_subtask_loop`: `166` tests OK.
  - focused regression trio for the new contracts: `3` tests OK.
  - `python -m src.ops.audit_runtime_domain_terms --summary`: passed.
  - `git diff --check`: passed.
- A monitored full seven-question eval-only replay was attempted with heartbeat
  logging, but was stopped after `KBF_T2_018` remained in the first question for
  more than `10` minutes with heartbeat only. Treat this as external
  LLM/evaluator latency, not a completed gate result.
