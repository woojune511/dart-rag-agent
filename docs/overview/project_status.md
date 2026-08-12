# Project Status

> Single authority for current product state, gates, blockers, and priority.
> Stable runtime semantics live in
> [agent_runtime_contract.md](../architecture/agent_runtime_contract.md); completed
> implementation and experiment chronology live in
> [implementation_history.md](../history/implementation_history.md) and
> [experiment_history.md](../history/experiment_history.md).

Last updated: 2026-08-12

## At A Glance

| Question | Current answer |
| --- | --- |
| What is the product? | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Is the core path blocked? | No known unit/contract correctness blocker |
| What is the architecture state? | Phase 3 OPEN; bounded lookup magnitude and same-block note-unit ownership is closed, four named debt groups remain |
| What just changed? | Four lookup/unit helpers moved to `financial_operand_resolution.py` in `5bd9e6f` |
| What passed? | Focused 8/8, operand owner 69/69, affected eight-module semantic set 813/813, import-side-effect 19/19, semantic/import union 832/832, runtime audit 217, full unittest 1,736/1,736 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | Two characterize-first seams totaling 189 lines of caller-facing answer/evidence/review/debug projection into a dedicated `financial_agent_run_projection.py`; graph execution, evidence selection, answer repair, trace/ledger work, and final sequencing remain hard stops |

## Product Boundary

The reviewer-facing product is the single-agent `FinancialAgent` runtime:

1. preserve DART section and table structure during ingest;
2. retrieve through dense/BM25 hybrid search and structure-aware expansion;
3. use an LLM for intent and semantic planning;
4. bind operands and execute calculations deterministically;
5. return evidence-backed answers with calculation and provenance traces.

MAS, report-cache promotion, evaluators, benchmark runners, and extended review
workflows are optional or experimental. They must not load during default imports
or an unconfigured `FinancialAgent` invocation.

## Current Source State

- PRs #79 through #84 completed the July portfolio-core simplification; PR #85
  compressed the earlier handoff documents. Latest confirmed upstream merge is
  `main@f0a5145`.
- The local checkpoint is the current HEAD of
  `codex/finalize-five-minute-review`; use `git log` for the exact commit. It is
  not represented here as pushed or merged.
- Canonical numeric output is `resolved_calculation_trace`, explicit
  `structured_result`, and task/artifact projection. Default output does not
  revive top-level `calculation_*` compatibility mirrors.
- Default import and deterministic invocation gates isolate MAS, evaluator,
  benchmark, promotion, portfolio-review, and persisted cache-index code.
- Tracked benchmark output remains limited to compact history-linked summaries
  and diagnostics. Full bundles, stores, caches, and heartbeat logs are local-only.
- The latest owner batch moved bounded lookup/magnitude and same-block note-unit
  resolution. In `5bd9e6f`, exactly seven source/test files changed. The four
  selected definition spans totaled 135 lines and became four public 134-line
  operand-owner functions. Fifteen calls finish as 12 external and three owner-
  local; retired selected private source/test refs are zero and no wrapper or
  alias remains. Source is `+156/-154`, net `+2`; tests are `+867/-13`, net
  `+854`; the whole commit is `+1,023/-167`, net `+856`. Graph helpers moved from
  6,299 to 6,269 physical lines, reconciliation from 2,137 to 2,079, lookup
  recovery from 609 to 557, and operand resolution from 3,461 to 3,603. The
  committed source diff SHA-256 is
  `b7bcf68a9cd79ab91f6e30978e434d9b5b504f06a85b4e582c20b0497bbecf21`.
  Lookup-record recovery, report-file/local-unit lookup, structured-cell
  selection, candidate extraction, mutable reconciliation state/evidence,
  artifact/ledger mutation, and final sequencing remain graph/existing-owner
  responsibilities. This is ownership relocation, not a behavior
  claim.
- Current physical sizes are: calculation graph 14,715 lines, main graph 1,205,
  graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,417, reconciliation 2,137, aggregate projection 3,180,
  task artifacts 1,460, and reflection projection 260.

Exact behavior, laziness, identity, exception, and caller-placement contracts are
kept in [agent_runtime_contract.md](../architecture/agent_runtime_contract.md).
Commit-level diffs and validation are kept in
[implementation_history.md](../history/implementation_history.md).

## Runtime Ownership

| Surface | Current owner and boundary |
| --- | --- |
| Public entry | `FinancialAgent.run()` |
| DART ingest | parser modules plus canonical profile in `src/config/runtime_contract.py` |
| Retrieval | `financial_retrieval_pipeline.py`; graph evidence owns structure expansion and evidence construction |
| Calculation orchestration | `financial_graph_calculation.py`; reads graph state, prepares inputs, places owner calls, and projects state/task/artifact results |
| Operand policy and resolution | `financial_operand_resolution.py`, including ratio sign policy, evidence-local unit/period coercion, dependency-task KRW consistency, table-metadata/raw-unit repair, and growth alignment/period conflict |
| Dependency and execution | `financial_dependency_projection.py`, including dependency input matching/binding, sibling-output synthesis preference, sibling lookup-surface preparation, and resolved reconciliation projection, plus `financial_calculation_execution.py` |
| Calculation rendering | `financial_graph_calculation_rendering.py`, including ratio unit/query/result projection and scalar/time-series display helpers |
| Answer and numeric surfaces | `financial_answer_slots.py`, `financial_answer_projection.py`, `financial_numeric_surface.py`, and `financial_text_surface.py`, including period/material, ratio-readiness, narrative validation, numeric/scale predicates, and shared sentence/token surfaces |
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering and trace inspection, result support/reuse predicates, prepared growth/ratio material inspection, final-answer evidence filtering/operand append/surface-operand projection, and growth-answer completion/sanitization |
| Composition, trace, artifacts | `financial_aggregate_state.py`, `financial_runtime_trace.py`, and `financial_task_artifacts.py`; the task-artifact owner includes bounded reconciliation artifact refs, runtime-evidence merge, and ratio result-row projection but not ledger mutation orchestration |
| Reflection projection | `financial_reflection_projection.py`; deterministic action/report, synthesis-source, request/plan normalization, strict summaries, and bounded request construction are owner-held |
| Optional systems | `src.experimental.mas` and explicitly configured cache/eval/review paths |

For topology rather than normative behavior, use
[runtime_flow_roles.md](runtime_flow_roles.md).

## Current Gate Status

| Gate | Latest status |
| --- | --- |
| Runtime contract gate | Recorded PASS; upstream raw bundle local-only |
| Hard structural numeric gate | Recorded PASS, 5 / 5; upstream raw bundle local-only |
| Concept runtime gap gate | Recorded PASS, 7 / 7; upstream raw bundle local-only |
| Policy-driven runtime gate | Recorded PASS; upstream raw bundle local-only |
| Expanded structural numeric gate | Recorded PASS, 9 / 9; upstream raw bundle local-only |
| Plain-retrieval comparison | Recorded 5 / 9 diagnostic baseline; not synchronized after later repairs |
| Reflection promotion gate | READY |
| Report-cache promotion evidence | READY, serving disabled |
| Promotion trace materiality gate | READY |
| REFERENCE_NOTE capability gate | READY, Researcher context-only |
| Demo fixture contract | `fixture_contract_ready`; manifest verified, live replay false |
| Portfolio review surface | `review_surface_ready`; unit suite and audit are `not_run` by that command |
| Latest focused owner checkpoint | PASS, new focused 8 / 8; operand owner 69 / 69 |
| Latest semantic regression set | PASS, affected eight-module set 813 / 813; semantic/import union 832 / 832 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,736 / 1,736 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_operand_resolution`,
`tests.test_operation_contracts`, `tests.test_reconciliation_plan`,
`tests.test_financial_task_artifacts`, `tests.test_subtask_loop`,
`tests.test_aggregate_subtask_projection`,
`tests.test_financial_agent_run_projection`, and
`tests.test_lookup_recovery_policy`. `tests.test_import_side_effects` passed
separately at 19 / 19 and together with the semantic set as an 832-test union.

Recorded structural and plain-retrieval numbers are historical evidence, not a
claim that the latest owner changes reran a paid benchmark. Their upstream raw
bundles are not checked in and are not independently reproducible from this
checkout. A fresh benchmark is required before publishing a new score after a
material parser, ingest, store-signature, retrieval, or answer-contract change.

## Active Blockers And Remaining Debt

| Area | State |
| --- | --- |
| Core correctness | No known unit/contract blocker |
| Latest benchmark evidence | Limited: refresh not run after the latest calculation changes |
| Phase 3 | Open; owner moves do not establish an end-to-end calculation or ledger owner |
| Optional MAS/cache serving | Intentionally disabled or experimental, not a product blocker |

The durable Phase 3 debt is:

| Debt group | Progress boundary |
| --- | --- |
| Aggregate repair and precedence | Partially advanced through period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, prepared growth-numeric rendering and trace inspection, result support/reuse, prepared material inspection, bounded row/gap/lookup-answer ownership, final-answer evidence/surface-operand projection, and growth-answer completion/sanitization; promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, lookup magnitude, same-block unit/table repair, and dependency input matching/binding; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Minimally advanced through bounded read-only reconciliation artifact-reference projection; artifact mutation and whole-ledger synchronization require separate contracts |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is two sequential characterize-first seams
from `financial_graph.py` into a new state-free
`financial_agent_run_projection.py` owner. The eight current definition spans are
11 + 25 + 26 + 2 + 34 + 45 + 14 + 32 = 189 lines. Removing the five standalone
`self` signature lines projects 184 owner lines. Their 11 current direct calls
finish as nine graph-external and two owner-local. Publish six graph-called
functions without the leading underscore; keep the defaults and compaction
helpers owner-private because their only calls become local. Delete every old
body and retarget directly. Do not add a
mixin wrapper, compatibility alias, callback, result carrier, reason, flag, or
new output field.

Seam A moves owner-private `_runtime_evidence_defaults(final)`, owner-private
`_compact_runtime_evidence_metadata(metadata)`, and public
`enrich_runtime_evidence_metadata(final, evidence_items)`. The first two calls
become owner-local to enrichment, while the four existing calls from
`_runtime_evidence_from_retrieved_docs(...)` remain graph-external. Preserve
company/year fallback precedence, copied metadata and evidence rows, source-
anchor fallback order, 4,000/20,000-character compaction thresholds, sorted
unique compaction fields, stable evidence order, nested aliases, and no mutation
of final/evidence/metadata inputs. Mapping, iteration, truthiness, string, copy,
and normalization exceptions continue to propagate.

Seam B moves `project_debug_traces(final)`,
`project_agent_answer(final, *, public_answer, citations, structured_result,
runtime_calculation_trace)`, `project_review_trace(final, *, runtime_evidence,
task_artifact_trace)`, `project_debug_bundle(*, debug_traces, llm_usage,
llm_usage_by_phase, embedding_usage)`, and
`augment_citations_from_runtime_evidence(citations, runtime_evidence)`. All five
calls remain direct from `FinancialAgent.run()` at Try depth zero. Preserve exact
output keys, fallback/get/default order, supplied list/dict identities where the
current literal projection retains them, stable citation order and normalized
case-insensitive dedupe, anchor/company/year formatting, shallow row/metadata
copies, and unchanged inputs. These functions only project already prepared
values; they do not select evidence, repair answers, resolve traces, or mutate
runtime state.

The new owner imports only `Any`/`Dict`, the existing `AgentAnswer`,
`DebugBundle`, `DebugTraceBundle`, `ReviewTrace`, and `RuntimeCalculationTrace`
typed contracts from `financial_graph_state`, `_normalise_spaces` from runtime
normalization, and `CALCULATION_DEBUG_TRACE_FIELD` from runtime config. None of
those modules imports the new owner or `financial_graph`, so the import DAG is
acyclic. The selected spans hit no runtime-domain baseline record; the reviewed
count remains 217. Graph retains the regex and narrative-policy imports for
unmoved public-answer repair, and all other touched imports remain live.

Before each source movement, add exactly four CURRENT-SOURCE methods, eight total.
For Seam A require direct defaults/metadata compaction, direct enrichment, exact
three-definition/six-call/import-DAG/baseline inventory, and executable
`_runtime_evidence_from_retrieved_docs(...)` adoption/order/laziness/exception-
stop. For Seam B require direct public-answer/debug projection, direct review-
trace/citation projection, exact five-definition/five-call/import-DAG inventory,
and executable `FinancialAgent.run()` exact args/order/adoption/exception-stop.
Pin shallow copies and nested identity, stable order, compaction thresholds,
source-anchor fallback, citation formatting/dedupe, exact projection keys,
unchanged mutable inputs, and uncaught exceptions. Then move, retarget, delete,
migrate current private/mixin test patches, require retired refs zero, and run
focused eight, new owner, affected semantic, import-side-effect, union, runtime-
audit, full-discovery, pycompile/fresh-import, DAG, body/caller parity, and diff-
check gates sequentially. The final surface is public six plus owner-private two.
Current inventory is 57 run-projection, 507 affected semantic, 526 union, and
1,736 full tests; eight new methods project 65, 515, 534, and 1,744. The
provisional affected semantic set is
`tests.test_financial_agent_run_projection`,
`tests.test_financial_aggregate_rank_dedupe`,
`tests.test_evaluator_runtime_projection`,
`tests.test_benchmark_runner_runtime_projection`,
`tests.test_operation_contracts`, `tests.test_financial_router_response`,
`tests.test_ops_runtime_projection_modes`, and
`tests.test_report_scoped_cache_contract`; it currently contains 507 tests, or
526 with the 19 import-side-effect tests, and should become 515/534 after the
characterization methods.

Keep `_runtime_evidence_from_retrieved_docs(...)`, structured/public-answer
repair, trace resolution/repair, task-artifact projection, `FinancialAgent.run()`
sequencing, graph construction, and the legacy flat compatibility assembly in
`financial_graph.py`. Keep retrieval/provenance construction, evidence
selection/filtering, answer composition, mutable state/evidence, task/artifact
ledger mutation, promotion, sync/rebuild, and final sequencing in their current
owners. The nearby structured-result and retrieved-ratio projection methods are
excluded because they call graph-owned repair/rebuild/stateful owners; runtime-
evidence fallback is excluded because it selects evidence and resolves traces.
Do not revive the direct structured-row/value pair, which remains blocked by the
graph-helper/operand-owner reverse edge, or expand collapsed-ratio, prepared-
candidate, compact-ratio, ontology-compatibility, bound-callback, evidence-
mutation, or ledger seams. No behavior, accuracy, ranking, performance, total-
code or executed-path reduction, benchmark, schedule, or Phase 3 completion
claim follows.

Priority is owned by this section. The durable plan records debt and stop lines,
not a competing queue.

## Reviewer Evidence Surface

- Product and quick start: [README.md](../../README.md)
- Five-minute summary: [portfolio_one_pager.md](portfolio_one_pager.md)
- Experiment narrative: [portfolio_experiment_report.md](portfolio_experiment_report.md)
- Demo evidence manifest:
  [evidence_manifest.json](../../tests/fixtures/portfolio_demo/evidence_manifest.json)
- Publication workflow: [validation.yml](../../.github/workflows/validation.yml)
- Architecture debt and stop lines:
  [core_runtime_surface_refactoring_plan.md](../architecture/core_runtime_surface_refactoring_plan.md)
- Benchmark interpretation: [benchmarking.md](../evaluation/benchmarking.md)
- Implementation chronology: [implementation_history.md](../history/implementation_history.md)
- Experiment chronology: [experiment_history.md](../history/experiment_history.md)

Local `benchmarks/results/**` data is not part of the published product surface.

## Session Handoff

Read in order:

1. [AGENTS.md](../../AGENTS.md)
2. [CONTEXT.md](../../CONTEXT.md)
3. this document
4. `git status -sb`
5. `git log -5 --oneline`

Repository documents and Git history override ChatGPT/Codex memory for current
commits, blockers, benchmark results, API/model state, and artifact locations.
