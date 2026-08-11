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
| What is the architecture state? | Phase 3 OPEN; narrative text-surface owner milestone closed, four named debt groups remain |
| What just changed? | Five narrative term/variant/context surfaces moved to `financial_text_surface.py` in `c1ec720` and `e8482bd` |
| What passed? | Focused 5/5, semantic regression set 714/714, nine-module union 733/733, import-side-effect 19/19, runtime audit 217, full unittest 1,633/1,633 |
| Was the benchmark refreshed? | **NOT RUN**; recorded benchmark evidence predates the latest calculation changes |
| What is next? | One characterize-first 141-line narrative presentation/preservation batch into `financial_text_surface.py`; graph orchestration remains a hard stop |

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
- The latest owner batch published narrative context-term, focus-variant,
  parenthetical-variant, prepared-evidence sentence-selection, and context-
  inclusion surfaces. Across `a2bb6cc..e8482bd`, 147 old graph definition-span
  lines became five public APIs. The 25 calls now place 21 in the graph and four
  owner-locally; retired graph-private references are zero. Query/evidence
  preparation, composition, mutable state/evidence, artifacts/ledger, promotion,
  sync/rebuild, callbacks, and final sequencing remain graph-owned. This is
  ownership relocation, not a behavior claim.
- Current physical sizes are: calculation graph 16,438 lines, graph helpers 6,299,
  planning 2,356, calculation rendering 708, answer slots 734, numeric surface
  670, answer projection 491, text surface 264, operand resolution 3,461,
  dependency projection 3,235, and aggregate projection 1,702.

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
| Latest semantic regression set | PASS, eight-module set 714 / 714 |
| Latest semantic/import union | PASS, nine-module set 733 / 733 |
| Import-side-effect regression set | PASS, 19 / 19 |
| Runtime domain-term audit | PASS, 217 reviewed literals |
| Full unittest discovery | PASS, 1,633 / 1,633 |
| Benchmark refresh after latest calculation changes | **NOT RUN** |
| GitHub Actions validation | Workflow defined; no remote run claimed for this local branch |

The semantic set is `tests.test_financial_text_surface`,
`tests.test_financial_aggregate_rank_dedupe`,
`tests.test_financial_answer_projection`,
`tests.test_aggregate_subtask_projection`, `tests.test_subtask_loop`,
`tests.test_financial_agent_run_projection`, `tests.test_lookup_recovery_policy`,
and `tests.test_operation_contracts`. Adding `tests.test_import_side_effects`
forms the 733-test union.

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

The sole selected architecture batch is one characterize-first narrative
presentation/preservation move into `financial_text_surface.py`:

1. publish `policy_required_realized_snippet_from_doc(...)` from the current
   69-line graph body;
2. publish `preserve_retrieved_narrative_source_surface(...)` from the current
   72-line graph body.

The read-only profiled boundary is 141 old definition-span lines, two public APIs,
and two graph calls. Both new public calls remain external, while the preservation
body's existing context-term call becomes owner-local. The cumulative selected
text-surface boundary therefore becomes seven public APIs and 27 calls: 22
external graph calls and five owner-local calls. Final per-API placement is
context terms 13/5, focus variants 2/0, parenthetical variants 3/0, context
sentence selection 1/0, context inclusion 1/0, document snippet 1/0, and
retrieved-source preservation 1/0. The two functions are adjacent by owner and
validation boundary; no schedule or behavior claim follows.

The text owner already has regex, normalization, narrative policy, context-term,
sentence-splitting, and particle dependencies. Add only
`narrative_policy_terms` from retrieval policy and
`extract_numeric_surface_candidates` plus `text_supports_numeric_candidates`
from `financial_numeric_surface.py`. Numeric surface imports only normalization
and configuration, so the new text-to-numeric edge has no reverse path. No
runtime-domain baseline record moves and the reviewed count remains 217.

Before source movement, add at least five CURRENT-SOURCE methods: two direct
methods, one exact binding/distribution method, and two executable caller methods.
Direct coverage must pin branch/access/laziness, stable order and tie behavior,
copy/no-mutation, normalization, and uncaught exceptions. In particular, the
snippet reads/copies metadata before the required-policy-term gate and eagerly
assembles the configured document surfaces; retrieved preservation keeps the
first highest-overlap quote sentence, preserves stable evidence/answer order,
and vetoes replacement of numerically supported answer sentences. Caller tests
must pin exact arguments, adoption position, input identity/content, and owner-
exception stop.

The second owner may select only the best quote sentence within already-prepared
evidence and replace the corresponding prepared answer sentence. Retrieval,
evidence ids/windows/provenance, evidence construction or list mutation, query/
evidence preparation, LLM/composition/feedback, mutable state, artifact/ledger,
promotion, sync/rebuild, callbacks, and final sequencing remain graph-owned. Do
not add wrappers, compatibility aliases, or callback seams.

Reject the 204-line expansion that also moves
`_preserve_policy_required_realized_context(...)`: it would silently replace the
inherited `_active_narrative_policies_for_query(...)` dynamic-dispatch boundary.
Moving narrative-row focus into the text owner creates an aggregate-to-text
reverse cycle, while the precision/structured-row cluster retains its carrier/
reverse-cycle problem. Also reject ratio-helper public-surface sprawl coupled to
stateful compact-ratio rendering, prepared-candidate carriers, state/evidence
mutation, and ledger/final-orchestration bundling. Hold source until the current-
source gate passes; then retarget/delete, require retired refs zero, and run
focused, semantic, import-side-effect, audit, full, and diff-check gates
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
