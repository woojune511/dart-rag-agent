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
| What is the architecture state? | Phase 3 OPEN; bounded final-answer evidence projection ownership is closed, four named debt groups remain |
| What just changed? | Final-answer evidence filtering and operand-evidence append moved to `financial_aggregate_projection.py` in `cde3d98` |
| What passed? | Focused 6/6, aggregate owner 52/52, affected eight-module semantic set 767/767, import-side-effect 19/19, semantic/import union 786/786, runtime audit 217, full unittest 1,716/1,716 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 155-line growth-answer numeric completion/sanitization pair into `financial_aggregate_projection.py`; answer refresh, mutable evidence/state, compact-ratio trace, and final sequencing remain hard stops |

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
- The latest owner batch moved bounded final-answer evidence projection. In
  `cde3d98`, exactly seven source/test files changed. The 66 + 102 = 168 selected
  definition-span lines became two public aggregate-owner functions spanning 65
  + 101 = 166 lines. All seven selected calls remain graph-external; retired
  selected private source/test refs are zero and no wrapper or alias remains.
  Source is `+186/-179`, net `+7`; tests are `+1,426/-34`, net `+1,392`; the
  whole commit is `+1,612/-213`, net `+1,399`. Calculation moved from 15,355 to
  15,185 physical lines, the main graph from 1,200 to 1,204, and aggregate
  projection from 2,530 to 2,703. The committed source diff SHA-256 is
  `1e9aadbbef8bf83438337b2a68f753344f564a2c4a49c5192a61a7c2d02917b8`.
  Retrieved-doc/evidence preparation, provenance projection, answer composition/
  refresh, artifact and ledger mutation, mutable state/evidence, and final
  sequencing remain graph-owned. This is ownership relocation, not a behavior
  claim.
- Current physical sizes are: calculation graph 15,185 lines, main graph 1,204,
  graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,417, reconciliation 2,137, aggregate projection 2,703,
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
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering and trace inspection, result support/reuse predicates, prepared growth/ratio material inspection, and final-answer evidence filtering/operand append projection |
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
| Latest focused owner checkpoint | PASS, new focused 6 / 6; aggregate owner 52 / 52 |
| Latest semantic regression set | PASS, affected eight-module set 767 / 767; semantic/import union 786 / 786 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,716 / 1,716 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_aggregate_rank_dedupe`,
`tests.test_financial_text_surface`, `tests.test_lookup_recovery_policy`,
`tests.test_subtask_loop`, `tests.test_aggregate_subtask_projection`,
`tests.test_operation_contracts`, `tests.test_financial_agent_run_projection`,
and `tests.test_financial_answer_projection`. `tests.test_import_side_effects`
passed separately at 19 / 19 and together with the semantic set as a 786-test
union.

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
| Aggregate repair and precedence | Partially advanced through period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, prepared growth-numeric rendering and trace inspection, result support/reuse, prepared material inspection, bounded row/gap/lookup-answer ownership, and final-answer evidence projection; promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, unit/table repair, and dependency input matching/binding; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Minimally advanced through bounded read-only reconciliation artifact-reference projection; artifact mutation and whole-ledger synchronization require separate contracts |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is one characterize-first growth-answer
numeric completion/sanitization move into the existing
`financial_aggregate_projection.py` owner. Publish
`_ensure_complete_growth_numeric_answer(...)` as
`ensure_complete_growth_numeric_answer(...)` and
`_strip_untraced_numeric_material_from_growth_narrative_sentence(...)` as
`strip_untraced_numeric_material_from_growth_narrative_sentence(...)`. Delete
both mixin bodies and retarget every caller directly; do not add a wrapper,
alias, callback, result carrier, reason, or compatibility attribute.

The current calculation definition spans are 47 + 108 = 155 lines at lines
2900-2946 and 3160-3267. Removing only `self` yields projected owner spans 46 +
107 = 153. The 12 completion calls and seven sanitization calls are all direct
calls at Try depth zero with no non-call binding. Completion is called once by
`_final_growth_answer_without_untraced_numeric_sentences(...)`, seven times by
`_refresh_numeric_answer_preserving_narrative_context(...)`, once by
`_apply_initial_aggregate_answer_composition(...)`, once by
`_apply_final_narrative_repair_pipeline(...)`, and twice by
`_aggregate_calculation_subtasks(...)`. Sanitization is called once by the final-
growth helper, once by `_uncovered_supported_growth_narrative_candidate(...)`,
four times by the refresh helper, and once by the final narrative pipeline.
Final selected distribution is 19 graph-external and zero owner-local calls.

The aggregate owner already has every dependency: `re`, `Any`/`Dict`/`List`/
`Optional`, `_normalise_spaces(...)`, both calculation policies, growth-period
and untraced-numeric predicates, narrative sentence splitting/noise/fragment
policy, `narrative_context_terms(...)`, and owner-local operation-family,
complete-growth rendering, and required-display helpers. The move adds no module
edge. The owner has no reverse path to either graph module, all affected graph
imports remain live outside the selected bodies, and the selected spans hit no
runtime-domain baseline record; the reviewed count remains 217.

Completion preserves normalized input, reverse ordered-result precedence,
growth-family and conflicting-period skips, complete rendered growth answer and
required-display adoption, the already-complete/untraced guard, stable extra-
sentence retention, and the first eligible growth-row return. Sanitization
preserves complete-answer/required-value preparation, the initial untraced-
numeric gate, configured percent and KRW-unit token removal, punctuation cleanup,
the second untraced gate, narrative-marker and term-count gates, table-noise and
fragment rejection, and empty/unchanged fallbacks. Neither function mutates
caller inputs or catches mapping, iteration, truthiness, string, regex,
normalization, sentence, numeric-surface, or policy exceptions.

Before source movement, add exactly six CURRENT-SOURCE methods in the aggregate
owner suite: direct completion and direct sanitization matrices; one exact
definition/span/19-call/argument/Try-depth/distribution/import-DAG/baseline
method; one executable refresh-caller matrix covering both functions; one
executable final-narrative-pipeline matrix; and one combined remaining-caller
matrix covering final-growth, uncovered-candidate, initial-composition, and
aggregate-subtask placements. Pin branch/access order, reverse and stable order,
required-value and conflict gates, configured token cleanup, marker/term/noise/
fragment gates, exact argument and evidence identity, caller adoption, laziness,
no mutation, and exception propagation/downstream stop. Then move, retarget,
delete, migrate all existing graph-private test refs, require retired refs zero,
and run focused six, the aggregate owner, the affected eight-module semantic
set, import-side-effect, union, runtime-audit, full-discovery, pycompile/fresh-
import, DAG, parity, and diff-check gates sequentially. At the current inventory
the owner has 52 tests, the semantic set has 767, its import union has 786, and
full discovery has 1,716; exactly six new methods project 58 owner, 773 semantic,
792 union, and 1,722 full tests. Existing selected private test references occur
in `tests.test_financial_answer_projection`,
`tests.test_financial_aggregate_rank_dedupe`, `tests.test_financial_text_surface`,
and `tests.test_operation_contracts`; direct tests must move to the owner while
runtime caller patches must continue to target the graph import use site.

Keep all six caller methods and their surrounding answer choice/refresh and
state/evidence sequencing in the graph. In particular,
`_final_growth_answer_without_untraced_numeric_sentences(...)` remains because
it coordinates graph-private numeric-coverage and narrative-intent gates;
refresh, initial composition, final repair, aggregate orchestration, mutable
state/evidence, artifact/ledger mutation, promotion, sync/rebuild, and final
sequencing also remain graph-owned. Do not expand into
`_compact_ratio_answer(...)` or numeric-projection coverage because they consume
runtime state/trace carriers. Do not move `_preserve_source_visible_query_terms`
because it depends on dynamic mixin focus-marker dispatch. The direct structured-
row/value pair remains excluded: its natural operand owner would reverse the
existing graph-helper dependency, while placing it in the general helper module
would enlarge the cross-cutting helper surface instead of establishing a domain
owner. Bound answer-slot callbacks, ontology compatibility, prepared carriers,
and evidence construction/mutation remain excluded. No behavior, accuracy,
ranking, performance, total-code or executed-path reduction, benchmark,
schedule, or Phase 3 completion claim follows.

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
