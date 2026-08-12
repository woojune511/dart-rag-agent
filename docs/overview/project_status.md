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
| What is the architecture state? | Phase 3 OPEN; bounded growth-answer cleanup ownership is closed, four named debt groups remain |
| What just changed? | Growth-answer numeric completion and narrative sanitization moved to `financial_aggregate_projection.py` in `3674bb1` |
| What passed? | Focused 6/6, aggregate owner 58/58, affected eight-module semantic set 773/773, import-side-effect 19/19, semantic/import union 792/792, runtime audit 217, full unittest 1,722/1,722 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 313-line final-answer surface operand projection into `financial_aggregate_projection.py`; evidence preparation/mutation, mutable state, artifact/ledger work, and final sequencing remain hard stops |

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
- The latest owner batch moved bounded growth-answer numeric completion and
  narrative sanitization. In `3674bb1`, exactly six source/test files changed.
  The 47 + 108 = 155 selected definition-span lines became two public aggregate-
  owner functions spanning 46 + 107 = 153 lines. All 19 selected calls remain
  graph-external; retired selected private source/test refs are zero and no
  wrapper or alias remains. Source is `+178/-176`, net `+2`; tests are
  `+1,547/-77`, net `+1,470`; the whole commit is `+1,725/-253`, net `+1,472`.
  Calculation moved from 15,185 to 15,030 physical lines and aggregate projection
  from 2,703 to 2,860. The committed source diff SHA-256 is
  `fb580debe8b766ce98f9258f55b13b00d712d5844fb6c18268abed685d38ebb5`.
  Final-growth selection, answer refresh/composition, compact-ratio trace,
  artifact and ledger mutation, mutable state/evidence, and final sequencing
  remain graph-owned. This is ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 15,030 lines, main graph 1,204,
  graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,461,
  dependency projection 3,417, reconciliation 2,137, aggregate projection 2,860,
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
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering and trace inspection, result support/reuse predicates, prepared growth/ratio material inspection, final-answer evidence filtering/operand append projection, and growth-answer completion/sanitization |
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
| Latest focused owner checkpoint | PASS, new focused 6 / 6; aggregate owner 58 / 58 |
| Latest semantic regression set | PASS, affected eight-module set 773 / 773; semantic/import union 792 / 792 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,722 / 1,722 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_aggregate_rank_dedupe`,
`tests.test_financial_text_surface`, `tests.test_lookup_recovery_policy`,
`tests.test_subtask_loop`, `tests.test_aggregate_subtask_projection`,
`tests.test_operation_contracts`, `tests.test_financial_agent_run_projection`,
and `tests.test_financial_answer_projection`. `tests.test_import_side_effects`
passed separately at 19 / 19 and together with the semantic set as a 792-test
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
| Aggregate repair and precedence | Partially advanced through period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, prepared growth-numeric rendering and trace inspection, result support/reuse, prepared material inspection, bounded row/gap/lookup-answer ownership, final-answer evidence projection, and growth-answer completion/sanitization; promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, unit/table repair, and dependency input matching/binding; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Minimally advanced through bounded read-only reconciliation artifact-reference projection; artifact mutation and whole-ledger synchronization require separate contracts |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is one characterize-first final-answer
surface operand projection move into the existing
`financial_aggregate_projection.py` owner. Publish graph-private
`_append_final_answer_surface_operands_from_evidence(projection,
evidence_items, *, final_answer)` as public
`append_final_answer_surface_operands_from_evidence(...)`. Delete the mixin
body and retarget both callers directly; do not add a wrapper, alias, callback,
result carrier, reason, or compatibility attribute.

The current calculation definition spans lines 4862-5174, exactly 313 lines.
The body has zero `self` loads, so removing only the receiver yields a projected
312-line owner function. Its two calls are direct and at Try depth zero:
`_filter_final_aggregate_evidence_and_projection(...)` passes the aggregate
projection, filtered evidence list, and `final_answer`; `FinancialAgent.run()`
passes the runtime calculation trace, a freshly assembled final/runtime evidence
list, and the public answer. Both selected calls finish graph-external and none
finishes owner-local.

This is a bounded state-free projection over already prepared projection,
answer, and evidence inputs. It preserves the initial no-answer-candidate/no-
evidence identity return; shallow projection and operand copies; operand numeric-
support detection; recursive period-role hints; stable highest-score evidence
selection; answer-near period and role inference; unique operand-id fallback;
and the exact appended operand schema. Its growth synchronization preserves
absolute current/prior slot recovery, nonzero-prior and percent-tolerance gates,
source-row cleanup, fresh answer-slot components, and calculation-result/plan
updates only when the answer surface supports them. It never mutates caller
projection or evidence inputs. Outside the initial identity gates it returns a
fresh top-level projection even when no operand is appended. Only malformed
candidate span integer conversion catches `TypeError`/`ValueError`; mapping,
iteration, truthiness, string, regex, normalization, numeric-surface, scoring,
slot, copy, and other exceptions retain current propagation behavior.

The aggregate owner already imports `re`, `Any`/`Dict`/`List`/`Optional`, numeric-
surface extraction/equivalence/slot helpers, answer-slot coercion/building,
`_clean_source_row_ids(...)`, and `_normalise_spaces(...)`. Add
`evidence_text_for_numeric_support(...)` and
`numeric_evidence_relevance_score(...)` on the existing numeric-surface edge and
`_normalise_operand_value(...)` on the existing runtime-normalization edge;
normalize the two module-qualified answer-slot calls to owner-local imports.
The move adds no module edge. Numeric surface, answer slots, and runtime
normalization have no reverse path to aggregate projection; neither graph module
is reachable from the owner. The two numeric-support imports become dead in the
calculation graph and must be removed, while all other selected dependencies
remain live there. The selected span hits no runtime-domain baseline record, so
the reviewed count remains 217.

Before source movement, add exactly six CURRENT-SOURCE methods in the aggregate
owner suite: three direct matrices for identity/copy/operand-support gates,
evidence scoring/period-role/appended-row projection, and growth-result/slot
synchronization; one exact definition/span/two-call/argument/Try-depth/import-
DAG/dead-import/baseline method; one executable calculation-filter caller; and
one executable `FinancialAgent.run()` caller. Pin stable order and strict-score
ties, recursive period discovery, tolerance boundaries, raw-value fallback,
duplicate ids, fresh top-level copies with preserved nested aliases, exact
evidence-list identity or construction, caller adoption/order/laziness, no input
mutation, soft span conversion failure, and propagated exception/downstream
stop. Then move, retarget, delete, migrate every current graph-private test ref,
require retired current refs zero, and run focused six, aggregate owner, affected
nine-module semantic, import-side-effect, union, runtime-audit, full-discovery,
pycompile/fresh-import, DAG, parity, and diff-check gates sequentially. Current
inventory is 58 owner, 784 affected semantic, 803 union, and 1,722 full tests;
six new methods project 64 owner, 790 semantic, 809 union, and 1,728 full tests.
Existing current private test refs occur in
`tests.test_financial_numeric_provenance`,
`tests.test_financial_aggregate_rank_dedupe`, and `tests.test_subtask_loop`.
Direct tests must move to the owner while runtime caller patches continue to
target each graph module's imported public symbol. The historical experiment
note remains chronology, not a current API contract.

Keep both callers and all surrounding evidence filtering/provenance adoption,
public-answer choice, runtime evidence assembly, debug/citation projection, and
final agent projection in their graph owners. Retrieved-doc/evidence preparation,
evidence-id/window/provenance construction, evidence-list mutation, answer
composition/refresh, mutable state, artifact/ledger mutation, promotion,
sync/rebuild, and final sequencing remain hard stops. This selection narrowly
supersedes the earlier broad exclusion of all evidence construction: the chosen
function only reads prepared evidence and projects copied calculation operands;
it does not retrieve, select an evidence window, mutate the evidence list, or
write graph state. Do not expand into the 310-line collapsed-ratio trace repair,
the 189-line prepared-candidate carrier, or `_compact_ratio_answer(...)`; each
crosses state/trace or result-carrier boundaries. The direct structured-row/value
pair remains excluded because its natural operand owner would reverse the
existing graph-helper dependency. Bound callbacks, ontology compatibility,
retrieval, provenance construction, carriers, and evidence mutation remain
excluded. No behavior, accuracy, ranking, performance, total-code or executed-
path reduction, benchmark, schedule, or Phase 3 completion claim follows.

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
