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
| What is the architecture state? | Phase 3 OPEN; aggregate answer-surface owner milestone closed, four named debt groups remain |
| What just changed? | Aggregate row/gap and lookup-answer surfaces moved to `financial_aggregate_projection.py` in `515ccab` and `18e75a3` |
| What passed? | Focused 5/5, affected seven-module set 699/699, import-side-effect 19/19, runtime audit 217, full unittest 1,623/1,623 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | Two characterize-first narrative text-surface commits into `financial_text_surface.py`; graph orchestration remains a hard stop |

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
- The latest owner batch published aggregate narrative-row classification,
  numeric-gap safe-partial selection, lookup-list composition, and uncovered-
  lookup preservation, while keeping the lookup-item formatter owner-private.
  Across `c4fd42a..18e75a3`, 183 old graph definition-span lines became four
  public APIs plus one owner-private helper. The 28 calls now place 23 in the
  graph and five owner-locally; retired graph-private references are zero.
  Composition, mutable state/evidence, artifacts/ledger, promotion, sync/rebuild,
  and final sequencing remain graph-owned. This is ownership relocation, not a
  behavior claim.
- Current physical sizes are: calculation graph 16,585 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, operand resolution 3,461, dependency projection
  3,235, and aggregate projection 1,702.

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
| Aggregate projection | `financial_aggregate_projection.py`, including selectors, source/coherence preparation, result/nested ranks, stable dedupe, narrative-row/gap policy, and lookup-answer surfaces |
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
| Latest focused owner checkpoint | PASS, 5 / 5 |
| Latest affected regression set | PASS, seven-module set 699 / 699 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,623 / 1,623 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The affected set is `tests.test_financial_dependency_projection`,
`tests.test_financial_operand_resolution`, `tests.test_financial_calculation_execution`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, and `tests.test_operation_contracts`.

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

The next architecture batch is one two-commit, one-owner characterize-first
narrative text-surface sequence into `financial_text_surface.py`:

1. publish `narrative_context_terms(...)` (18 old definition-span lines),
   `narrative_focus_variants(...)` (30), and
   `parenthetical_focus_variants(...)` (15). Their current call counts are 18,
   two, and three; after A, placement is 21 external graph calls and two
   owner-local term calls;
2. publish `narrative_context_sentence_from_evidence(...)` (58 lines) and
   `include_narrative_context_if_needed(...)` (26). Each has one external graph
   caller and each term call becomes owner-local.

The read-only profiled boundary is 147 old definition-span lines, five public
APIs, and 25 calls. Final placement is 21 external graph calls and four owner-
local calls: terms 14/4, focus variants 2/0, parenthetical variants 3/0,
context-sentence selection 1/0, and context inclusion 1/0. Commit order is A then
B; it is neither a dependency arrow nor a schedule estimate.

The text owner already has regex, normalization, narrative policy, and sentence-
splitting dependencies. Add only `Any`/`Dict` typing and
`_query_requests_narrative_context` from `financial_operation_policies.py`; that
module imports normalization/config only, so this creates no reverse edge. A also
relocates exactly one reviewed runtime-domain baseline record,
`[가-힣A-Za-z0-9()]+`, from the graph path to the text-owner path. Its literal,
category, and count remain unchanged; only path, fingerprint, and first line move,
and the reviewed total remains 217.

Each seam requires at least five CURRENT-SOURCE methods before source movement.
A must directly pin term tokenization/filtering/stable dedupe, focus and
parenthetical variants, access/laziness/no-mutation/exceptions, exact current and
post-A bindings, and executable caller argument/adoption/exception-stop behavior.
B must directly pin context gate, source/claim precedence, score/tie/support/
priority order, first-sentence truncation, inclusion/exclusion/overlap/prefix
behavior, copy/no-mutation/exceptions, exact final distribution, and executable
`_aggregate_calculation_subtasks` selection plus
`_apply_initial_aggregate_answer_composition` inclusion order/adoption/exception
stop.

All 21 graph callers remain. The context selector may choose only a text sentence
from its already-prepared evidence input; evidence ids, windows, provenance, and
selection orchestration remain graph-owned. Retain query/evidence preparation,
LLM/composition/feedback, mutable state/evidence, artifact/ledger, promotion,
sync/rebuild, callbacks, and final sequencing. Do not add wrappers, compatibility
aliases, or callback seams.

Reject the 289-line slot/gap expansion because it crosses an existing callback
binding and a ledger-only consumer. Ontology completion remains blocked at four
placements and three `hasattr` gates; the 720-line precision cluster retains its
carrier/reverse-cycle problem. Also reject prepared-candidate carriers, stateful
compact-ratio work, and evidence-selection/mutation bundling. Hold source until
each current-source gate passes; then retarget/delete, require retired refs zero,
and run focused, affected, import-side-effect, audit, full, and diff-check gates
sequentially. No behavior, accuracy, ranking, performance, total-code or executed-
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
