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
| What is the architecture state? | Phase 3 OPEN; bounded final-answer surface operand ownership is closed, four named debt groups remain |
| What just changed? | Final-answer surface operand projection moved to `financial_aggregate_projection.py` in `fae0516` |
| What passed? | Focused 6/6, aggregate owner 64/64, affected nine-module semantic set 790/790, import-side-effect 19/19, semantic/import union 809/809, runtime audit 217, full unittest 1,728/1,728 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | Two characterize-first seams totaling 135 lines of operand magnitude and same-block unit resolution into `financial_operand_resolution.py`; report-file lookup, structured-cell selection, mutable reconciliation state, artifact/ledger work, and final sequencing remain hard stops |

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
- The latest owner batch moved bounded final-answer surface operand projection.
  In `fae0516`, exactly six source/test files changed. The 313 selected
  definition-span lines became one public 312-line aggregate-owner function.
  Both selected calls remain graph-external; retired selected private source/test
  refs are zero and no wrapper or alias remains. Source is `+325/-319`, net `+6`;
  tests are `+983/-9`, net `+974`; the whole commit is `+1,308/-328`, net `+980`.
  Calculation moved from 15,030 to 14,715 physical lines, main graph from 1,204
  to 1,205, and aggregate projection from 2,860 to 3,180. The committed source
  diff SHA-256 is
  `6b45dd51cfe790304227f99242525c54a7ddb2c0a65dafe940cb7e42069b8020`.
  Both callers, evidence preparation/filtering, public-answer/runtime-evidence
  assembly, mutable state/evidence, artifact and ledger mutation, and final
  sequencing remain graph-owned. This is ownership relocation, not a behavior
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
| Latest focused owner checkpoint | PASS, new focused 6 / 6; aggregate owner 64 / 64 |
| Latest semantic regression set | PASS, affected nine-module set 790 / 790; semantic/import union 809 / 809 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,728 / 1,728 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_aggregate_rank_dedupe`,
`tests.test_financial_text_surface`, `tests.test_lookup_recovery_policy`,
`tests.test_subtask_loop`, `tests.test_aggregate_subtask_projection`,
`tests.test_operation_contracts`, `tests.test_financial_agent_run_projection`,
`tests.test_financial_answer_projection`, and
`tests.test_financial_numeric_provenance`. `tests.test_import_side_effects`
passed separately at 19 / 19 and together with the semantic set as an 809-test
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
| Aggregate repair and precedence | Partially advanced through period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, prepared growth-numeric rendering and trace inspection, result support/reuse, prepared material inspection, bounded row/gap/lookup-answer ownership, final-answer evidence/surface-operand projection, and growth-answer completion/sanitization; promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, unit/table repair, and dependency input matching/binding; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Minimally advanced through bounded read-only reconciliation artifact-reference projection; artifact mutation and whole-ledger synchronization require separate contracts |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is two sequential characterize-first seams
into the existing `financial_operand_resolution.py` owner. The combined current
definition spans are 16 + 32 + 29 + 58 = 135 lines; the final owner surface is
four public functions spanning a projected 16 + 32 + 29 + 57 = 134 lines. Across
15 current direct calls, final placement is 12 graph/existing-owner external and
three operand-owner-local. Delete every old body and retarget directly; do not add
a wrapper, alias, callback, result carrier, reason, or compatibility attribute.

Seam A moves existing public `lookup_hints_for_concept_key(concept_key)` and
`coerce_lookup_magnitude_value(...)` from `financial_lookup_recovery.py` without
renaming them. Their current calls are four and three. After co-location, three
graph-helper hint calls remain external, the magnitude helper calls the hint
owner-locally, and magnitude calls remain external from lookup-record coercion
and two reconciliation placements. After Seam B, one of those reconciliation
magnitude calls becomes owner-local, producing final per-API placement of hints
3 external/1 local and magnitude coercion 2 external/1 local.

Seam B publishes graph-helper `_candidate_row_block_signature(candidate)` as
`candidate_row_block_signature(candidate)` and reconciliation-private
`_repair_note_operand_units_from_same_block(operand_rows, candidate_map)` as
`repair_note_operand_units_from_same_block(...)`. The current calls are seven and
one. Final placement is signature 6 external/1 owner-local and repair 1 external/
0 local. The signature preserves row-context normalization, integer-row-index
soft failure, bounds checks, nearest contiguous table-header discovery, and
table-source/header-position identity. The repair preserves initial list identity
for fewer than two rows, shallow row copies otherwise, note-only same-block
grouping, exactly-one-resolved-unit inheritance, normalized-value and ontology-
declared magnitude coercion, stable row order, nested aliases, and no input or
candidate-map mutation. Only the existing `TypeError`/`ValueError` conversions
remain soft; other mapping, iteration, truthiness, string, normalization,
ontology, policy, and coercion exceptions propagate.

The operand owner already has `Any`/`Dict`/`List`, `get_financial_ontology()`,
`_normalise_operand_value(...)`, and `_normalise_spaces(...)`. Add only
`RECONCILIATION_POLICY` to its existing retrieval-policy import. No new module
edge is created: lookup recovery and graph helpers already import operand
resolution, reconciliation already imports it, and the owner imports none of
those three modules. Seam A removes the now-dead `get_financial_ontology` import
from lookup recovery. All remaining imports stay live. None of the four selected
spans hits the runtime-domain baseline; the reviewed count remains 217.

Before each source movement, add exactly four CURRENT-SOURCE methods, eight total.
For Seam A require direct hint lookup and magnitude-gate/case/access/laziness/
exception matrices, an exact two-definition/seven-call/import-DAG distribution
method, and executable lookup-record plus reconciliation adoption/exception-stop.
For Seam B require direct signature and repair matrices, an exact two-definition/
eight-call/dead-import/baseline method, and executable structured-operand caller
adoption/order/laziness/exception-stop. Pin shallow copies and nested identity,
stable order, exact ontology and policy gates, first-match behavior, raw/rendered
fallback, unchanged inputs, and uncaught downstream exceptions. Then move,
retarget, delete, migrate all current private/import-owner test refs, require
retired refs zero, and run focused eight, operand owner, affected eight-module
semantic, import-side-effect, union, runtime-audit, full-discovery, pycompile/
fresh-import, DAG, parity, and diff-check gates sequentially. Current inventory is
61 operand-owner, 805 affected semantic, 824 union, and 1,728 full tests; eight
new methods project 69 owner, 813 semantic, 832 union, and 1,736 full tests.
The affected semantic set is `tests.test_financial_operand_resolution`,
`tests.test_operation_contracts`, `tests.test_reconciliation_plan`,
`tests.test_financial_task_artifacts`, `tests.test_subtask_loop`,
`tests.test_aggregate_subtask_projection`,
`tests.test_financial_agent_run_projection`, and
`tests.test_lookup_recovery_policy`.

Keep `coerce_lookup_magnitude_record(...)` and lookup selection/recovery in
`financial_lookup_recovery.py`. Keep report-file lookup and
`_resolve_candidate_local_unit_hint(...)` in graph helpers; keep structured-cell
selection, operand-row construction, candidate extraction, LLM reranking,
reconciliation state/artifact projection, retry, and final sequencing in the
reconciliation graph. The nearby structured-unit helper is excluded because it
depends on report-file lookup; the direct structured-row/value pair remains
excluded by the graph-helper/operand-owner reverse edge. Collapsed-ratio repair,
prepared-candidate and compact-ratio state/trace carriers, bound callbacks,
ontology compatibility gates, retrieval/provenance construction, evidence
mutation, and ledger work remain excluded. No behavior, accuracy, ranking,
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
