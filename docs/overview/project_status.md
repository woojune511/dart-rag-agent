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
| What is the architecture state? | Phase 3 OPEN; prepared growth-numeric renderer owner milestone closed, four named debt groups remain |
| What just changed? | Public `compose_complete_growth_numeric_answer(...)` moved to `financial_aggregate_projection.py` in `5fb0267` |
| What passed? | New focused 5/5, aggregate-owner module 40/40, affected semantic set 755/755, nine-module union 774/774, import-side-effect 19/19, runtime audit 217, full unittest 1,674/1,674 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 130-line prepared growth trace-inspection cluster into `financial_aggregate_projection.py`; answer replacement/refresh, sentence repair, mutable state/evidence, and final sequencing remain hard stops |

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
- The latest owner batch moved the prepared growth-numeric renderer. In
  `5fb0267`, exactly six source/test files changed. The 100-line graph body became
  one 99-line public aggregate-owner function; all nine selected calls remain
  graph-external and retired graph-private source/test references are zero.
  Source is `+117/-111`, net `+6`; tests are `+989/-38`, net `+951`; the whole
  commit is `+1,106/-149`, net `+957`. The graph moved from 15,743 to 15,643
  physical lines and aggregate projection from 2,288 to 2,394. The committed
  source diff SHA-256 is
  `a92591876808e7e4744d7deb5d9ff83d7282d61cfaaeb7bfcf852ea232a2687b`.
  Answer replacement/refresh, sentence repair, arithmetic synchronization,
  retrieved-ratio artifact/state handling, mutable state/evidence, and final
  sequencing remain graph-owned. This is ownership relocation, not a behavior
  claim.
- Current physical sizes are: calculation graph 15,643 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,235, and aggregate projection 2,394.

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
| Dependency and execution | `financial_dependency_projection.py` and `financial_calculation_execution.py` |
| Calculation rendering | `financial_graph_calculation_rendering.py`, including ratio unit/query/result projection and scalar/time-series display helpers |
| Answer and numeric surfaces | `financial_answer_slots.py`, `financial_answer_projection.py`, `financial_numeric_surface.py`, and `financial_text_surface.py`, including period/material, ratio-readiness, narrative validation, numeric/scale predicates, and shared sentence/token surfaces |
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering, result support/reuse predicates, and prepared growth/ratio material inspection |
| Composition, trace, artifacts | `financial_aggregate_state.py`, `financial_runtime_trace.py`, and `financial_task_artifacts.py` |
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
| Latest focused owner checkpoint | PASS, new focused 5 / 5; aggregate-owner module 40 / 40 |
| Text-owner module | PASS, 20 / 20 |
| Latest semantic regression set | PASS, affected eight-module set 755 / 755 |
| Latest semantic/import union | PASS, nine-module set 774 / 774 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,674 / 1,674 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_text_surface`,
`tests.test_financial_aggregate_rank_dedupe`,
`tests.test_financial_answer_projection`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, `tests.test_lookup_recovery_policy`,
and `tests.test_operation_contracts`. Adding `tests.test_import_side_effects`
forms the 774-test union.

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
| Aggregate repair and precedence | Partially advanced through period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, prepared growth-numeric rendering, result support/reuse, prepared material inspection, and bounded row/gap/lookup-answer ownership; promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, and unit/table repair; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Essentially untouched; requires a separate behavior contract |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is one characterize-first prepared growth
trace-inspection move into `financial_aggregate_projection.py`. Publish the
current graph predicates `_growth_answer_has_untraced_numeric_material(...)`,
`_narrative_summary_conflicts_with_growth_trace(...)`, and
`_growth_narrative_numeric_incompatible_with_trace(...)` as public owner APIs
without the leading underscore.

The current definition spans are 29 + 57 + 44 = 130 lines at graph lines
3284-3312, 3314-3370, and 3422-3465. Removing only `self` produces projected
owner spans 28 + 56 + 43 = 127 lines. Their 16 + 1 + 2 = 19 production uses are
all direct `self` calls at Try depth zero; there are no non-call bindings,
`hasattr` gates, callbacks, wrappers, aliases, or production override surfaces.
All 19 selected calls remain graph-external and owner-local selected calls remain
zero.

The aggregate owner already has normalization, regex, typing, narrative policy,
operation-family resolution, period-conflict policy, the completed renderer and
required-display projection, numeric extraction/equivalence, and sentence
splitting. Add only `growth_answer_has_untraced_numeric_sentence(...)` and
`growth_sentence_has_untraced_material_numeric(...)` on the existing answer-
projection edge plus `evidence_numeric_display_candidates(...)` on the existing
numeric-surface edge. The latter graph import becomes dead and must be removed;
no new module edge or cycle is introduced. The three bodies hit no runtime-domain
baseline record and the reviewed count remains 217.

`growth_answer_has_untraced_numeric_material(...)` normalizes the answer, scans
prepared rows in order, filters operation family and conflicting periods, builds
the complete renderer and required displays, then checks whole-answer and split-
sentence untraced numeric material in that order. The narrative-summary conflict
predicate builds a stable evidence/metadata surface, adds evidence-visible numeric
display candidates, and returns on the first percent token absent from the
allowed trace surface. The numeric-incompatibility predicate builds trace and
narrative numeric candidates and returns `True` only when at least one narrative
candidate has no equivalent trace candidate. They mutate no answer, row,
ordered-result, or evidence input and catch no mapping, copy, iteration,
truthiness, string, normalization, regex, policy, owner, extraction, or comparison
exception.

Before source movement, add exactly six CURRENT-SOURCE methods: one direct matrix
for each predicate; one exact definition/span/19-call/argument/Try-depth/
distribution/import-DAG/dead-import/baseline method; one executable matrix for
representative untraced-material callers; and one executable matrix for the
conflict and incompatibility callers. Pin access order, early-return laziness,
stable row/evidence/sentence order, candidate equivalence, input and nested
identity, no mutation, exact call arguments, boolean adoption, and owner-exception
downstream stop. Then move/retarget/delete without a wrapper or alias, migrate all
private direct/patch/static references, require retired graph-private refs zero,
and run focused six, aggregate-owner, affected semantic, import-side-effect,
runtime-audit, full-discovery, fresh-import, DAG, and diff-check gates
sequentially.

Keep `_ensure_complete_growth_numeric_answer(...)`,
`_final_growth_answer_without_untraced_numeric_sentences(...)`,
`_enforce_source_stated_growth_answer_contract(...)`,
`_strip_untraced_numeric_material_from_growth_narrative_sentence(...)`,
`_refresh_numeric_answer_preserving_narrative_context(...)`, answer replacement
and refresh, source-visible sentence repair, arithmetic synchronization,
retrieved-ratio artifact/state, evidence construction or mutation, mutable state,
ledger, callbacks, promotion, sync/rebuild, and final orchestration in the graph.
Numeric-coverage helpers coupled to `_compact_ratio_answer`, direct structured/
precision reverse cycles, ontology compatibility, carriers, and source-visible
query-term expansions remain rejected. No behavior, accuracy, ranking,
performance, total-code or executed-path reduction, benchmark, schedule, or
Phase 3 completion claim follows.

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
