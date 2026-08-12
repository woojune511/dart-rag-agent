# Project Status

> Single authority for current product state, gates, blockers, and priority.
> Stable runtime semantics live in
> [agent_runtime_contract.md](../architecture/agent_runtime_contract.md); completed
> implementation and experiment chronology live in
> [implementation_history.md](../history/implementation_history.md) and
> [experiment_history.md](../history/experiment_history.md).

Last updated: 2026-08-13

## At A Glance

| Question | Current answer |
| --- | --- |
| What is the product? | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Is the core path blocked? | No known unit/contract correctness blocker |
| What is the architecture state? | Phase 3 OPEN; aggregate calculation/public projection and subtask upsert/rank are now owner-held, four named debt groups remain |
| What just changed? | The 156-line aggregate subtask projection/upsert cluster moved to `financial_aggregate_projection.py` in `06710c1` |
| What passed? | Focused 7/7, aggregate-subtask owner 118/118, affected seven-module semantic set 780/780, import-side-effect 19/19, semantic/import union 799/799, runtime audit 217, full unittest 1,771/1,771 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 128-line nested subtask selection/promotion batch into `financial_answer_projection.py`; graph-state capture, broader nested-result replacement, synchronization/rebuild, and final sequencing remain hard stops |

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
- The latest owner batch moved aggregate calculation/public projection and
  subtask upsert/rank. In `06710c1`, exactly eleven source/test files changed.
  The four selected definition spans totaled 156 lines and became three public
  plus one owner-private functions totaling 153 owner lines. Six calls finish as
  four graph-external and two owner-local. Retired planning-mixin definitions and
  selected qualified refs are zero; the distinct runtime-trace private aggregate
  builder and its six calls remain live. Source is `+181/-184`, net `-3`; tests
  are `+1,143/-41`, net `+1,102`; the whole commit is `+1,324/-225`, net `+1,099`.
  Planning moved from 2,356 to 2,180 physical lines, aggregate projection from
  3,180 to 3,350, calculation from 14,716 to 14,718, and the main graph from 936
  to 937. The committed source diff SHA-256 is
  `0cb0b708ee672f115f0a06eea62217f598e87d1a194f6422d422ba126bb51f7b`.
  State capture, projection filtering, broader nested promotion, recovery/
  alignment/synchronization, artifact/ledger mutation, and final sequencing
  remain graph-owned. This is ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 14,718 lines, main graph 937,
  graph helpers 6,269,
  planning 2,180, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 411, operand resolution 3,603,
  dependency projection 3,417, reconciliation 1,667, reconciliation candidates
  329, aggregate projection 3,350, task artifacts 1,460, reflection projection
  374, and run projection 302.

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
| Structured reconciliation candidates | `financial_reconciliation_candidates.py`; state-free statement/unit/period/score/identity/row/match and candidate-ID projection over already prepared mappings |
| Calculation rendering | `financial_graph_calculation_rendering.py`, including ratio unit/query/result projection and scalar/time-series display helpers |
| Answer and numeric surfaces | `financial_answer_slots.py`, `financial_answer_projection.py`, `financial_numeric_surface.py`, and `financial_text_surface.py`, including period/material, ratio-readiness, narrative validation, numeric/scale predicates, and shared sentence/token surfaces |
| Aggregate projection | `financial_aggregate_projection.py`, including aggregate calculation/public projection, subtask upsert/rank, selectors, dependency-source preparation, source/coherence preparation, result/nested ranks, stable dedupe, narrative row-focus/gap policy, lookup-answer surfaces, growth display/material projection, prepared growth-numeric rendering and trace inspection, result support/reuse predicates, prepared growth/ratio material inspection, final-answer evidence filtering/operand append/surface-operand projection, and growth-answer completion/sanitization |
| Composition, trace, artifacts | `financial_aggregate_state.py`, `financial_runtime_trace.py`, and `financial_task_artifacts.py`; the task-artifact owner includes bounded reconciliation artifact refs, runtime-evidence merge, and ratio result-row projection but not ledger mutation orchestration |
| Caller-facing run projection | `financial_agent_run_projection.py`; state-free runtime-evidence metadata/citation, agent-answer/review/debug, structured missing-answer selection, aggregate completion, and prepared public-answer state projection, excluding evidence selection, dynamic answer/trace repair, graph execution, and final sequencing |
| Reflection projection | `financial_reflection_projection.py`; deterministic retry-query construction/finalization, action/report, synthesis-source, request/plan normalization, strict summaries, and bounded request construction are owner-held |
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
| Latest focused owner checkpoint | PASS, new focused 7 / 7; aggregate-subtask owner 118 / 118 |
| Latest semantic regression set | PASS, affected seven-module set 780 / 780; semantic/import union 799 / 799 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,771 / 1,771 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_aggregate_rank_dedupe`,
`tests.test_aggregate_subtask_projection`, `tests.test_financial_answer_projection`,
`tests.test_lookup_recovery_policy`, `tests.test_financial_agent_run_projection`,
`tests.test_subtask_loop`, and `tests.test_operation_contracts`.
`tests.test_import_side_effects` passed separately at 19 / 19 and together with
the semantic set as a 799-test union.

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
| Aggregate repair and precedence | Partially advanced through aggregate calculation/public projection, subtask upsert/rank, period/material/source/coherence/rank/dedupe, narrative validation, growth display/material, prepared growth-numeric rendering and trace inspection, result support/reuse, prepared material inspection, bounded row/gap/lookup-answer ownership, final-answer evidence/surface-operand projection, and growth-answer completion/sanitization; broader nested promotion, sync/rebuild, and final sequencing remain graph-owned |
| Dependency and ratio/absolute seams | Partially advanced through ratio presentation/readiness/scale, bounded operand preparation, lookup magnitude, same-block unit/table repair, and dependency input matching/binding; graph-state lookup, broader evidence orchestration, and surrounding sequencing remain graph-owned |
| Broader task/artifact ledger synchronization | Minimally advanced through bounded read-only reconciliation artifact-reference projection; artifact mutation and whole-ledger synchronization require separate contracts |
| Private API mesh and test co-location | Partially advanced as public contracts move |

These are debt groups, not a promised count of four implementation slices. Each
may split or close only after caller, test, and stop-line characterization.

## Next Work

The sole selected architecture batch is one characterize-first nested subtask
selection/promotion move from `financial_graph_planning.py` into the existing
`financial_answer_projection.py` owner. Move `_nested_subtask_rows(...)` (20
current definition-span lines) as public `nested_subtask_rows(...)`,
`_subtask_row_operation_family(...)` (19) as owner-private
`_subtask_row_operation_family(...)`, `_subtask_row_specificity_score(...)` (38)
as owner-private `_subtask_row_specificity_score(...)`, and
`_promote_nested_subtask_result_if_more_specific(...)` (51) as public
`promote_nested_subtask_result_if_more_specific(...)`. Removing the two
standalone `self` lines projects the 128 former lines to 126 owner lines. Six
selected calls finish as two graph-external and four owner-local calls. Delete
the old bodies and retarget directly; add no wrapper, compatibility alias,
callback, carrier, reason, flag, or output field. The answer-projection owner
becomes public 12 plus owner-private nine.

`nested_subtask_rows(...)` must preserve depth-first source order across direct
and answer-slot child lists, non-dict skips, fresh top-level child copies,
nested-object identity, recursive calculation-result access, and input
immutability. Owner-private `_subtask_row_operation_family(...)` must preserve
row, answer-slot, and calculation-result precedence; aggregate-child fallback;
`concept_` metric fallback; normalization/lowercasing; access laziness; and
uncaught exceptions. Owner-private `_subtask_row_specificity_score(...)` must
preserve task-ID mismatch rejection and the exact status, material,
non-aggregate, operation, family, and label rank tuple, including exact,
substring, and token-overlap label precedence.

`promote_nested_subtask_result_if_more_specific(...)` must preserve the active-
operation and child-list gates, stable candidate order under equal scores,
score-prefix filtering, current-material protection, aggregate-child rejection,
answer/status/result fallback order, fresh best-result copying, unchanged-path
identity, input immutability, and uncaught exception propagation. It must not
absorb the caller's state capture or the separate broader nested-result
replacement policy.

The answer-projection owner already owns `re`, `Dict`, `List`, runtime
normalization, and `subtask_row_has_material(...)`; no new module edge is needed.
Planning and calculation already import answer projection, while answer
projection reaches neither graph mixin. Retarget one promotion call in
`_capture_current_subtask_result(...)` and one nested-row call in
`_promote_stronger_nested_aggregate_results(...)`. The other four calls become
owner-local: promotion to nested rows, specificity, and operation family, plus
specificity to operation family. All six calls remain outside `try` blocks with
their exact args/kwargs. Remove planning's now-dead
`subtask_row_has_material` import; its `re`, typing, and normalization imports
remain live. The selected spans hit no runtime-domain baseline record and the
reviewed count remains 217.

Before production movement, add exactly six CURRENT-SOURCE methods to
`tests.test_financial_answer_projection`: a direct recursive nested-row
order/copy/access/exception matrix; a direct operation-family plus specificity
precedence/rank/laziness/exception matrix; a direct promotion gate/tie/adoption/
identity/no-mutation/exception matrix; exact 20/19/38/51-definition, six-call,
planned 20/19/37/50-owner-span, public-two/private-two, external-two/local-four,
import-DAG, baseline, dead-import and try-depth inventory; an executable
`_capture_current_subtask_result(...)` caller test; and an executable
`_promote_stronger_nested_aggregate_results(...)` caller test. Pin exact args,
mapping/list identity, call order, result adoption, input/nested identity, no
mutation, and owner-exception downstream stop. Only after focused 6/6 is green
may source move.

Then retarget the existing private references in
`tests.test_financial_answer_projection`,
`tests.test_aggregate_subtask_projection`, and
`tests.test_financial_aggregate_rank_dedupe`. Require retired planning
definitions and selected mixin-qualified refs to be zero, and run answer-
projection owner 23/23, affected six-module semantic 770/770,
import-side-effect 19/19, union 789/789, runtime audit 217, projected full
discovery 1,777/1,777, pycompile/fresh import, DAG/body/caller parity, and diff-
check gates sequentially. The semantic set is
`tests.test_financial_answer_projection`,
`tests.test_aggregate_subtask_projection`,
`tests.test_financial_aggregate_rank_dedupe`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, and
`tests.test_operation_contracts`.

Keep `_capture_current_subtask_result(...)` and its task-trace/state/evidence
projection in planning. Keep `_promote_stronger_nested_aggregate_results(...)`,
dependency-coherence comparison, row replacement, projection synchronization/
rebuild, mutable state/evidence, artifact/ledger mutation, and final sequencing
in calculation. The previously rejected aggregate-owner variant remains
forbidden because it creates the documented planning/aggregate reverse cycle;
the selected answer-projection owner avoids that cycle and already owns the
material predicate. Also reject direct structured-value/precision, compact-
ratio, ontology-compatibility, bound-callback, evidence-mutation, state,
carrier, and ledger seams. No behavior, accuracy, ranking, performance, total-
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
