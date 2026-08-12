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
| What is the architecture state? | Phase 3 OPEN; bounded task-artifact read projection ownership is closed, four named debt groups remain |
| What just changed? | Two public runtime-evidence/task-artifact row projections moved to `financial_task_artifacts.py` in `8d627a6` |
| What passed? | Focused 6/6, task-artifact owner 15/15, affected ten-module semantic set 832/832, import-side-effect 19/19, semantic/import union 851/851, runtime audit 217, full unittest 1,710/1,710 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 168-line final-answer evidence projection pair into `financial_aggregate_projection.py`; composition, mutable evidence/state, artifact/ledger mutation, and final sequencing remain hard stops |

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
- The latest owner batch moved bounded task-artifact read projection. In
  `8d627a6`, exactly five source/test files changed. The 21 + 43 = 64 calculation
  definition-span lines became two public task-artifact functions spanning 20 +
  42 = 62 lines. All four selected calls remain graph-external;
  retired selected private source/test refs are zero and no wrapper or alias
  remains. Source is `+74/-70`, net `+4`; tests are `+911/-8`, net `+903`;
  the whole commit is `+985/-78`, net `+907`. Calculation moved from 15,419 to
  15,355 physical lines and task artifacts from 1,392 to 1,460.
  The committed source diff SHA-256 is
  `07ffa0657a4e7762442aa3d79d88dd06084a0c0319c0eb7fce8185902061018e`.
  Operand extraction/evidence selection, ratio conflict/arithmetic, artifact and
  ledger mutation, mutable state/evidence, and final sequencing remain
  graph-owned. This is ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 15,355 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,417, reconciliation 2,137, aggregate projection 2,530,
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
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering and trace inspection, result support/reuse predicates, and prepared growth/ratio material inspection |
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
| Latest focused owner checkpoint | PASS, new focused 6 / 6; task-artifact owner 15 / 15 |
| Latest semantic regression set | PASS, affected ten-module set 832 / 832; semantic/import union 851 / 851 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,710 / 1,710 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_task_artifacts`,
`tests.test_financial_aggregate_rank_dedupe`,
`tests.test_financial_ratio_presentation`, `tests.test_financial_ratio_readiness`,
`tests.test_structured_operand_extraction`,
`tests.test_financial_dependency_projection`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_operation_contracts`, and
`tests.test_financial_agent_run_projection`. `tests.test_import_side_effects`
passed separately at 19 / 19 and together with the semantic set as an 851-test
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
| Aggregate repair and precedence | Partially advanced through period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, prepared growth-numeric rendering and trace inspection, result support/reuse, prepared material inspection, and bounded row/gap/lookup-answer ownership; promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, unit/table repair, and dependency input matching/binding; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Minimally advanced through bounded read-only reconciliation artifact-reference projection; artifact mutation and whole-ledger synchronization require separate contracts |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is one characterize-first final-answer
evidence projection move into the existing `financial_aggregate_projection.py`
owner. Publish `_filter_aggregate_evidence_for_final_answer(...)` as
`filter_aggregate_evidence_for_final_answer(...)` and
`_append_operand_evidence_for_final_answer(...)` as
`append_operand_evidence_for_final_answer(...)`. Delete both mixin bodies and
retarget every caller directly; do not add a wrapper, alias, callback, result
carrier, reason, or compatibility attribute.

The current calculation definition spans are 66 + 102 = 168 lines at lines
5017-5082 and 5084-5185. Removing only `self` yields projected owner spans 65 +
101 = 166. The seven current loads are all direct calls at Try depth zero with
no non-call binding. Filtering is called once by
`_filter_final_aggregate_evidence_and_projection(...)` and twice by
`FinancialAgent._runtime_evidence_from_retrieved_docs(...)`; operand-evidence
append is called once by that graph method, once by
`_replace_mutable_aggregate_answer(...)`, and twice by
`_apply_final_narrative_repair_pipeline(...)`. Final selected distribution is
seven graph-external and zero owner-local calls.

The aggregate owner already has `re`, `Any`/`Dict`/`List`,
`extract_numeric_surface_candidates(...)`,
`numeric_surface_candidates_equivalent(...)`, and `_normalise_spaces(...)`. Add
only `evidence_supports_numeric_candidates(...)`,
`promote_table_numeric_support_evidence(...)`, and
`text_supports_numeric_candidates(...)` on its existing numeric-surface import
edge. Calculation already imports the aggregate owner, the main graph already
reaches it through the calculation mixin, and adding the main graph's direct
public-function import creates no cycle; the owner has no reverse path to either
graph module. All other touched graph imports remain live after deletion;
calculation's now-dead
`evidence_supports_numeric_candidates(...)` and
`promote_table_numeric_support_evidence(...)` imports must be removed with the
old bodies. The spans hit no runtime-domain baseline record, so the reviewed
count remains 217.

Evidence filtering preserves stable evidence order, selected/operand numeric-
support precedence, retrieved-narrative and recon gates, percent support,
table-numeric promotion, quote/raw-row consistency, fresh shallow copies, and
the current all-filtered fallback. Operand-evidence append preserves stable
operand order, numeric equivalence and literal-surface support, derived-percent
roles, source-anchor and duplicate-id gates, generated evidence schema, fresh
top-level copies, and nested identity. Neither function mutates caller inputs or
catches mapping, iteration, truthiness, string, regex, normalization, numeric-
surface, or copy exceptions.

Before source movement, add exactly six CURRENT-SOURCE methods in the aggregate
owner suite: direct filter and direct append matrices; one exact definition/
span/seven-call/argument/Try-depth/distribution/import-DAG/baseline method; one
executable graph runtime-evidence caller matrix covering both functions; one
executable final filter/provenance caller matrix; and one combined mutable-answer
and final-narrative append caller matrix. Pin branch/access order, stable order,
selected and prefix gates, percent/numeric equivalence, fallback behavior,
generated schema, fresh top-level copies and nested identities, exact argument
identity, caller adoption, laziness, no mutation, and exception propagation/
downstream stop. Then move, retarget, delete, migrate all existing graph-private
test refs, require retired refs zero, and run focused six, the aggregate owner,
the affected eight-module semantic set, import-side-effect, union, runtime-audit,
full-discovery, pycompile/fresh-import, DAG, parity, and diff-check gates
sequentially. At the current inventory the semantic set is 761 tests and its
import union is 780; exactly six new methods project 767 semantic, 786 union, and
1,716 full tests.

Keep all four caller methods and both graph modules' surrounding orchestration.
In particular, retain retrieved-doc/evidence preparation, selected-claim and
projection provenance updates, answer choice/composition/refresh, mutable
state/evidence, artifact/ledger mutation, promotion, sync/rebuild, and final
sequencing. Do not expand into `_slot_metric_keys(...)` or
`_iter_answer_slots(...)`: the former is passed as a bound callback and its
deletion changes the dynamic mixin surface. Do not expand into structured-cell
helpers, ratio conflict selection, reflection planning, compact-ratio state/
trace, ontology compatibility, prepared carriers, or evidence mutation. No
behavior, accuracy, ranking, performance, total-code or executed-path reduction,
benchmark, schedule, or Phase 3 completion claim follows.

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
