# Project Status

> Single authority for current product state, gates, blockers, and priority.
> Stable runtime semantics live in
> [agent_runtime_contract.md](../architecture/agent_runtime_contract.md); completed
> implementation and experiment chronology live in
> [implementation_history.md](../history/implementation_history.md) and
> [experiment_history.md](../history/experiment_history.md).

Last updated: 2026-08-11

## At A Glance

| Question | Current answer |
| --- | --- |
| What is the product? | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Is the core path blocked? | No known unit/contract correctness blocker |
| What is the architecture state? | Phase 3 OPEN; aggregate dependency-source preparation owner milestone closed, four named debt groups remain |
| What just changed? | Four public dependency-source preparation APIs plus one owner-private scorer moved to `financial_aggregate_projection.py` in `df3b63b` |
| What passed? | New focused 6/6 and combined focused 13/13, semantic regression set 725/725, nine-module union 744/744, import-side-effect 19/19, runtime audit 217, full unittest 1,644/1,644 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 95-line narrative row-focus batch into `financial_aggregate_projection.py`; dynamic narrative-driver and composition/state paths remain hard stops |

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
- The latest owner batch moved the five-function aggregate dependency-source
  preparation boundary. Across `8dc6054..df3b63b`, the exact changed files are
  `financial_aggregate_projection.py`, `financial_graph_calculation.py`,
  `test_financial_aggregate_rank_dedupe.py`,
  `test_aggregate_subtask_projection.py`, and `test_financial_text_surface.py`.
  The 131 old graph definition-span lines became four public APIs with spans
  33, 15, 35, and 23 plus one 21-line owner-private scorer. Nine calls finish as
  seven graph-external and two owner-local: seed collection 1/0, text score 0/1,
  slot score 1/1, best-source selection 3/0, and component projection 2/0.
  Retired graph-private references are zero. Source is `+157/-147`, net `+10`;
  tests are `+1,299/-27`, net `+1,272`; the whole range is `+1,456/-174`, net
  `+1,282`. The frozen source diff SHA-256 is
  `0ed48e13a232281d0f05e70f83b5f8b617e739dc3854265316a4910bf82495e3`.
  Source-slot mapping with its bound callback and the compact-ratio
  state/trace/result carrier remain graph-owned. This is ownership relocation,
  not a behavior claim.
- Current physical sizes are: calculation graph 16,164 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,235, and aggregate projection 1,845.

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
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative-row/gap policy, and lookup-answer surfaces |
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
| Latest focused owner checkpoint | PASS, new focused 6 / 6; combined owner and migrated caller surface 13 / 13 |
| Text-owner module | PASS, 20 / 20 |
| Latest semantic regression set | PASS, eight-module set 725 / 725 |
| Latest semantic/import union | PASS, nine-module set 744 / 744 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,644 / 1,644 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_text_surface`,
`tests.test_financial_aggregate_rank_dedupe`,
`tests.test_financial_answer_projection`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, `tests.test_lookup_recovery_policy`,
and `tests.test_operation_contracts`. Adding `tests.test_import_side_effects`
forms the 744-test union.

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
| Aggregate repair and precedence | Partially advanced through period/material/source/coherence/rank/dedupe, narrative validation, and bounded row/gap/lookup-answer ownership; promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, and unit/table repair; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Essentially untouched; requires a separate behavior contract |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is one characterize-first aggregate
narrative row-focus move from graph lines 8054-8149 into
`financial_aggregate_projection.py`:

1. publish `narrative_row_focus_sentence(...)` from the current 27-line body;
2. publish `narrative_row_focus_context(...)` from the current 68-line body.

The profiled boundary is 95 old definition-span lines, two public APIs, and
three calls. Projected owner spans are 26 + 67 = 93 lines. All three calls remain
graph-external: the sentence selector is called once by
`_compose_growth_narrative_answer(...)`, while the context selector is called
once by that composer and once by
`_answer_satisfies_growth_narrative_intent(...)`. The functions read prepared
aggregate rows and return an optional scored sentence/context tuple; they do not
mutate rows, evidence, state, artifacts, or ledgers.

The aggregate owner already has `aggregate_result_operation_family(...)`,
normalization, `re`, typing, `narrative_context_terms(...)`, and the sentence
splitter on existing dependency directions. Add only the existing text-owner
noise/abbreviation predicates and `CALCULATION_NARRATIVE_POLICY`; text and
config have no reverse aggregate edge. No runtime-domain baseline record moves,
so the reviewed count remains 217.

Before source movement, add at least five CURRENT-SOURCE methods: a direct
sentence-selector branch/access/laziness/order/no-mutation/exception matrix; a
direct context scoring/tie/adjacent-sentence/max-limit matrix; one exact
definition/call/distribution/import-DAG/baseline method; one executable composer
method covering both selector arguments, adoption/order/laziness, input identity,
and owner-exception stop; and one executable intent-check caller method covering
exact context arguments, boolean adoption, no mutation, and exception stop. Then
publish/retarget/delete without a wrapper or compatibility alias, migrate the
three existing test references, including two instance-private patches, to owner
or graph-imported public bindings, require retired graph-private refs zero, and
run focused, affected
semantic, import-side-effect, runtime audit, full discovery, and diff-check gates
sequentially.

Keep `_growth_narrative_sentence_candidates(...)` and
`_supported_growth_driver_groups(...)` in the graph because they consume the
inherited dynamic `self._narrative_driver_groups(...)` seam. Keep
`_compose_growth_narrative_answer(...)` and
`_answer_satisfies_growth_narrative_intent(...)` because they own broader
growth-row/evidence selection, answer composition/validation, and caller
sequencing. Existing instance-patched tests must be retargeted; production has no
`hasattr`, callback binding, or compatibility alias for the selected pair.

Reject `_preserve_source_visible_query_terms(...)` because it consumes the
inherited `_query_focus_marker_groups(...)` retrieval seam and ontology lookup.
Reject direct structured-evidence movement because its correct operand owner is
blocked by the graph-helpers/operand-resolution cycle. Compact-ratio rendering
retains state/trace carriers and thirteen callers. Dependency-slot matching is a
smaller mixed graph-helper period-focus boundary, while evidence construction or
mutation, precision/carrier, ontology compatibility, mutable state/evidence,
artifact/ledger, callback, promotion, sync/rebuild, and final orchestration remain
out of scope. No behavior, accuracy, ranking, performance, total-code or
executed-path reduction, benchmark, schedule, or Phase 3 completion claim follows.

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
