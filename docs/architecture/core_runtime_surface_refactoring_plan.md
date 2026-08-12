# Core Runtime Surface Refactoring Plan

Last revised: 2026-08-10

This is the active boundary and phased plan for reducing repository complexity
while preserving verified financial QA behavior. Detailed chronology lives in
Git history, `docs/history/implementation_history.md`, and
`docs/history/experiment_history.md`; `docs/overview/project_status.md`
contains current state and is the sole authority for next-work priority.

`docs/architecture/agent_runtime_contract.md` remains authoritative for runtime
behavior. Update both documents if a structural change alters that contract.

## Portfolio outcome

The repository should communicate one product claim:

> Retrieve numeric evidence from DART filings, use an LLM to plan the required
> calculation, execute it deterministically, and return a provenance-validated
> answer with an inspectable trace.

The default path should be understandable in about ten minutes:

```text
main.py -> financial_router.py -> FinancialAgent.run()
  -> semantic plan
  -> hybrid retrieval and structural rerank
  -> evidence and operand binding
  -> deterministic formula execution
  -> answer, structured_result, resolved_calculation_trace
```

Multi-agent orchestration is an experiment around this runtime. It is not the
default product engine and must not dominate reviewer-facing documentation.

## Surface classification

### Core

Core code is required by the default user path:

- FastAPI boundary and `FinancialAgent.run()` facade
- DART parsing, chunking, and structural metadata
- embedding configuration, Chroma, BM25, and structure storage
- query planning, retrieval, reranking, evidence selection, and reconciliation
- operand binding, deterministic execution, rendering, and verification
- `answer_slots`, `structured_result`, `resolved_calculation_trace`, citations,
  and `retrieval_debug_trace`
- ontology, retrieval policy, and runtime config consumed by those paths

Core runtime code may not import evaluator, benchmark, portfolio-review, MAS,
or cache-promotion implementations.

### Evaluation

Evaluation proves core behavior but is not part of request execution:

- evaluator and benchmark runner
- focused profiles and regression fixtures
- portfolio and capability gates
- experiment reports and reproducibility logs

Evaluation may consume public core contracts. Core must never depend on
evaluation normalization or score rules.

### Experimental and internal

These surfaces remain opt-in and outside the default product story:

- `src/experimental/mas/`
- disabled query-time graph-expansion variants
- report-cache and reflection promotion workflows
- diagnostic probes, smoke commands, and retrospective scripts

Keep an explicit import boundary. A feature that is disabled by default does
not justify extra state fields or imports in the core request path unless the
runtime contract requires them.

### Legacy compatibility

Legacy code includes old import paths, flat response mirrors, stale aliases,
callerless wrappers, and test-only production helpers. It is temporary, not a
fourth architecture layer.

Every compatibility surface must have:

1. a known caller;
2. a canonical replacement;
3. a removal condition;
4. a contract test only when external compatibility is still required.

If no caller remains, delete the surface and its private-helper-only test in the
same change.

## Refactoring rules

1. Preserve behavior before changing behavior. Do not mix owner extraction with
   retrieval tuning or benchmark repair.
2. Move implementation to an actual owner. A new facade that merely adds
   another forwarding layer is not progress.
3. Delete duplicated or callerless surfaces after migration. File splitting
   without caller migration does not reduce the conceptual surface.
4. Keep one canonical answer and calculation trace. Compatibility mirrors may
   read from them but may not override them.
5. Keep domain vocabulary in ontology, policy, config, or documented data.
6. Keep LLM semantics separate from deterministic execution and validation.
7. Keep benchmark artifacts, local stores, and caches out of source changes.

## Execution sequence

### Phase 0: Correctness prerequisites

Status: completed on 2026-07-22.

Close correctness gaps that would be hidden by structural work:

- numeric evidence equivalence must preserve sign;
- final-answer numeric backfill must select provenance using value, label, and
  period compatibility rather than numeric equality and list order alone.

Required proof: small contract tests, runtime-domain-term audit, and full unit
test discovery. No fresh benchmark ingest is required for these projection-only
changes.

### Phase 1: Reviewer-facing repositioning

Status: completed on 2026-07-22 for README, portfolio one-pager, project status,
and this execution plan. Follow-up reviewer documents should adopt the same
boundary when they are next touched.

- Make `DART Financial Agentic RAG` the primary name and story.
- Show the single-agent pipeline before optional capabilities.
- Keep the first-read path to README, one-pager, one trace walkthrough, one
  experiment report, and technical highlights.
- Move MAS, cache promotion, reflection promotion, and internal gates to an
  optional/experimental section.
- State benchmark limitations next to quantitative claims.

Completion condition: a reviewer can identify the problem, core pipeline,
representative result, and demo command without reading internal status logs.

### Phase 2: Give retrieval one owner

Status: completed on 2026-07-22 as a no-behavior-change owner extraction.

- `_retrieve`, query/filter construction, reranking, candidate selection, and
  trace projection now live in `financial_retrieval_pipeline.py`.
- Retrieval-only module helpers moved with the implementation; evidence imports
  only the shared lookup/evidence helpers it still consumes.
- `FinancialAgentEvidenceMixin` no longer defines `_retrieve` or reranking.
- Focused owner/scope/query/import tests cover the new boundary.
- Full unittest discovery passes with `1349` tests.

Create `src/agent/financial_retrieval_pipeline.py` as the implementation owner
for:

- retrieval query bundle assembly;
- metadata filter construction;
- dense/BM25 execution and reuse;
- deterministic structural reranking;
- visible and seed candidate selection;
- `retrieval_debug_trace` construction.

`financial_graph_evidence.py` should retain evidence construction, evidence
preservation, narrative support, and final evidence validation. Its `_retrieve`
node may delegate to the retrieval owner, but it must not keep a second copy of
the pipeline.

Completion conditions:

- one retrieval implementation owner;
- unchanged graph node contract and debug trace schema;
- focused retrieval tests import or exercise the new owner;
- no retrieval behavior tuning in the extraction change;
- old implementation deleted after caller migration.

### Phase 3: Converge on one calculation path

Status: in progress. The July canonical public-projection milestone is complete:
legacy flat mirrors cannot override `agent_answer` or the resolved trace. The
broader single-calculation-path and ledger ownership phase remains open.

The target flow is:

```text
OperandResolver -> FormulaExecutor -> AnswerRenderer -> Verifier
```

Current ownership is intentionally split by state boundary:

| Surface | Owner | Stop line |
| --- | --- | --- |
| Graph-state orchestration | `financial_graph_calculation.py` | Reads and writes graph state, prepares evidence/query/rows, places owner calls, and projects task/artifact/final state |
| Operand resolution and policy | `financial_operand_resolution.py` | State-free candidate resolution, unit/period coercion, dependency-task KRW consistency, table-metadata/raw-unit repair, growth alignment/period conflict, and ratio sign policy; no graph-state lookup |
| Dependency projection | `financial_dependency_projection.py` | State-free dependency precedence, projection, recalculation disposition, provenance adoption, and related predicates; KRW-consistency implementation now belongs to operand resolution |
| Formula execution | `financial_calculation_execution.py` | Deterministic plan construction, validation, execution, and value freshness |
| Rendering and answer surfaces | `financial_graph_calculation_rendering.py`, `financial_answer_slots.py`, `financial_answer_projection.py`, `financial_numeric_surface.py`, `financial_text_surface.py` | Ratio/result rendering, slot/readiness contracts, narrative validation, numeric comparison, table support, scale predicates, and shared term/variant/context sentence surfaces |
| Aggregate projection | `financial_aggregate_projection.py` | State-free aggregate signatures, source preparation, dependency-coherence ranks, repair/projection transforms, compact prompt rows, row/sentence/rendered selectors, narrative-row/gap policy, and lookup-answer surfaces |
| Composition, trace, artifacts | `financial_aggregate_state.py`, `financial_runtime_trace.py`, `financial_task_artifacts.py` | State carriers and prepared projection transforms; graph retains surrounding orchestration |

Detailed identity, laziness, exception, precedence, and caller-placement semantics
are normative only in
[agent_runtime_contract.md](agent_runtime_contract.md). Execution topology is
summarized in [runtime_flow_roles.md](../overview/runtime_flow_roles.md). This
plan does not repeat those contracts.

The current checkpoint has explicit owners for the major bounded seams completed
so far, including ratio sign and presentation/readiness/scale policy, generic
numeric support, aggregate row/sentence/rendered selection, answer-slot period and
material policy, aggregate source/coherence preparation, result/nested ranking,
stable dedupe, narrative intent/surface/trace validation, bounded aggregate row/
gap/lookup-answer policy, narrative term/variant/context presentation, prepared
KRW raw-unit/growth alignment/period-conflict policy, dependency-task KRW
consistency, table-metadata KRW repair, and final-answer evidence filtering/
operand append and surface-operand projection. Current
validation and benchmark
status belong only in
[project_status.md](../overview/project_status.md); commit-level diffs and claim
limits belong only in
[implementation_history.md](../history/implementation_history.md).

Phase 3 remains open for four durable debt groups:

1. partially advanced: period/material/source/coherence/rank/dedupe, selected
   narrative-validation policy, bounded row/gap/lookup-answer surfaces, and
   final-answer evidence/surface-operand projection and growth-answer completion/
   sanitization are owned, while promotion, sync/rebuild, mutable state/evidence,
   and final sequencing remain graph-owned;
2. partially advanced: ratio presentation/readiness/scale, bounded operand-
   preparation, and unit/table-repair seams are owned; isolate remaining dependency
   and ratio/absolute seams that do not require graph-state lookup, broader evidence
   orchestration, or surrounding sequencing;
3. essentially untouched: specify broader task/artifact ledger synchronization
   as a separate behavior contract before attempting ownership convergence;
4. partially advanced: reduce the private-API mesh and co-locate tests only as
   the corresponding public contracts move.

These groups are unordered debt, not four promised implementation slices.
Priority and sequencing are owned by
[project_status.md#next-work](../overview/project_status.md#next-work).

Selected ratio presentation/readiness/scale, narrative intent/surface/trace,
aggregate row/gap/lookup-answer, narrative term/variant/context presentation,
prepared KRW raw-unit/growth alignment/period-conflict, dependency-task KRW
consistency, and table-metadata KRW repair boundaries are complete in their
state-free owners. Aggregate dependency-source seed/scoring/selection/component
preparation, narrative row-focus selection, and aggregate growth display/material
projection, result support/reuse predicates, prepared growth/ratio material
inspection, prepared growth-numeric rendering, and growth trace inspection are
also owner-resident. Dependency input matching, sibling-output synthesis
preference, task-output binding projection, prepared runtime-evidence merge, and
ratio task-artifact row projection are owner-resident as well. Final-answer
evidence filtering, operand-evidence append, and surface-operand projection are
also owner-resident.
Retained external graph call placements remain,
while broader evidence repair,
dependency-source lookup/source mapping, answer composition/refresh,
evidence construction, promotion, sync/rebuild, mutable state/evidence, ledger,
callbacks, and final projection remain outside those owner batches.

The completed `cde3d98` commit is an ownership relocation only. Exactly seven
source/test files changed. Two selected calculation definition spans totaling
168 lines became two public aggregate projections totaling 166 lines. Seven
selected calls finish graph-external and none finish owner-local; retired
selected private source/test refs are zero. Source is `+186/-179`, net `+7`:
calculation moved from 15,355 to 15,185 physical lines, the main graph from 1,200
to 1,204, and aggregate projection from 2,530 to 2,703. Tests are `+1,426/-34`,
net `+1,392`, and the whole commit is `+1,612/-213`, net `+1,399`. Six new
unittest methods moved full discovery from 1,710 to 1,716. Final gates passed
focused 6/6, aggregate owner 52/52, affected semantic 767/767, import 19/19,
semantic/import union 786/786, audit 217, full discovery 1,716/1,716,
pycompile/fresh import, DAG/body/caller parity, and diff check. Benchmark refresh
was **NOT RUN** and remote CI is unverified. This establishes neither behavior,
accuracy, ranking, performance, total-code, executed-path, ledger, benchmark,
nor Phase 3 completion.

The completed `3674bb1` follow-on is another ownership relocation only. It moved
the former 47 + 108 = 155 growth-answer completion/sanitization definition-span
lines to public 46 + 107 = 153 aggregate-owner lines. All 19 calls remain graph-
external and retired private source/test refs are zero. Source is `+178/-176`,
tests are `+1,547/-77`, and the whole commit is `+1,725/-253`; calculation moved
from 15,185 to 15,030 physical lines and aggregate projection from 2,703 to
2,860. Six new unittest methods moved full discovery from 1,716 to 1,722. Final
gates passed focused 6/6, aggregate owner 58/58, affected semantic 773/773,
import 19/19, semantic/import union 792/792, audit 217, full discovery
1,722/1,722, pycompile/fresh import, DAG/body/caller parity, and diff check. Its
source diff SHA-256 is
`fb580debe8b766ce98f9258f55b13b00d712d5844fb6c18268abed685d38ebb5`.
Benchmark refresh was **NOT RUN** and remote CI is unverified.

The completed `fae0516` follow-on is another ownership relocation only. It moved
the former 313-line final-answer surface-operand definition to public 312-line
`append_final_answer_surface_operands_from_evidence(...)` in the aggregate owner.
Both calls remain graph-external and retired private source/test refs are zero.
Source is `+325/-319`, tests are `+983/-9`, and the whole commit is
`+1,308/-328`; calculation moved from 15,030 to 14,715 physical lines, main graph
from 1,204 to 1,205, and aggregate projection from 2,860 to 3,180. Six new
unittest methods moved full discovery from 1,722 to 1,728. Final gates passed
focused 6/6, aggregate owner 64/64, affected semantic 790/790, import 19/19,
semantic/import union 809/809, audit 217, full discovery 1,728/1,728,
pycompile/fresh import, DAG/body/caller parity, and diff check. Its source diff
SHA-256 is
`6b45dd51cfe790304227f99242525c54a7ddb2c0a65dafe940cb7e42069b8020`.
Benchmark refresh was **NOT RUN** and remote CI is unverified.

The completed `5bd9e6f` follow-on is another ownership relocation only. It moved
16 + 32 + 29 + 58 = 135 lookup/magnitude and same-block note-unit definition-
span lines to four public 134-line functions in `financial_operand_resolution`.
Fifteen calls finish as 12 external and three owner-local; retired selected
private refs are zero. Source is `+156/-154`, tests are `+867/-13`, and the whole
commit is `+1,023/-167`. Graph helpers moved from 6,299 to 6,269 physical lines,
reconciliation from 2,137 to 2,079, lookup recovery from 609 to 557, and operand
resolution from 3,461 to 3,603. Eight new unittest methods moved full discovery
from 1,728 to 1,736. Final gates passed focused 8/8, operand owner 69/69,
affected semantic 813/813, import 19/19, semantic/import union 832/832, audit
217, full discovery 1,736/1,736, pycompile/fresh import, DAG/body/caller parity,
and diff check. Its source diff SHA-256 is
`b7bcf68a9cd79ab91f6e30978e434d9b5b504f06a85b4e582c20b0497bbecf21`.
Benchmark refresh was **NOT RUN** and remote CI is unverified.

Lookup-record recovery, report-file/local-unit lookup, structured-cell
selection, candidate extraction, LLM reranking, mutable reconciliation state/
evidence, artifact/ledger mutation, and final sequencing remain in their prior
owners.

The completed `84fe1d5` follow-on is another ownership relocation only. It moved
the former 189 caller-facing run-projection definition-span lines to six public
and two owner-private functions totaling 184 lines in the new
`financial_agent_run_projection.py`. Eleven calls finish as nine graph-external
and two owner-local; retired selected private refs are zero. Source is
`+232/-211`, tests are `+1,702/-17`, and the whole commit is `+1,934/-228`.
Main graph moved from 1,205 to 1,011 physical lines, the new owner contains 215,
and eight new unittest methods moved full discovery from 1,736 to 1,744. Final
gates passed focused 8/8, run-projection owner 65/65, affected semantic 515/515,
import 19/19, semantic/import union 534/534, audit 217, full discovery
1,744/1,744, pycompile/fresh import, DAG/body/caller parity, and diff check. Its
source diff SHA-256 is
`84b8d32bee450cde9370fa6f72646f006ce9bb47413169b34c1c50b0053a5a24`.
Benchmark refresh was **NOT RUN** and remote CI is unverified.

Runtime-evidence fallback/selection, structured and stale public-answer repair,
trace resolution/rebuild, graph execution, compatibility assembly, retrieval/
provenance construction, mutable state/evidence, artifact/ledger work,
collapsed-ratio and prepared-candidate carriers, bound callbacks, ontology
compatibility, and final sequencing remain excluded.

The completed `a88b215` follow-on is another ownership relocation only. It moved
the former 74 prepared public-answer selection/state-projection definition-span
lines to four public functions totaling 71 lines in the existing run-projection
owner. Thirteen calls finish as 12 graph-external and one owner-local; the
cumulative owner surface is public ten plus owner-private two with 24 calls
split external 21/local three. Retired selected private refs are zero. Source is
`+105/-93`, tests are `+1,269/-8`, and the whole commit is `+1,374/-101`.
Main graph moved from 1,011 to 936 physical lines, the run owner from 215 to 302,
and six new unittest methods moved full discovery from 1,744 to 1,750. Final
gates passed focused 6/6, run-projection owner 71/71, affected semantic 521/521,
import 19/19, semantic/import union 540/540, audit 217, full discovery
1,750/1,750, pycompile/fresh import, DAG/body/caller parity, and diff check. Its
source diff SHA-256 is
`45e12114a8bfb2f7513cbde887b7fe4a8a7b5ed65c2300af902939b6dc38fc45`.
Benchmark refresh was **NOT RUN** and remote CI is unverified.

Dynamic structured/stale answer repair, trace rebuild, runtime-evidence
selection, graph execution, compatibility assembly, mutable state/evidence,
artifact/ledger work, callbacks, carriers, and final sequencing remain excluded.
The selected follow-on is now two sequential characterize-first seams totaling
293 state-free structured-reconciliation candidate-projection lines from
`financial_graph_reconciliation.py` into a new
`financial_reconciliation_candidates.py` owner. Seven public and four owner-
private functions project to 285 owner lines; 26 calls finish as 19
reconciliation-external and seven owner-local. The graph mixin keeps candidate
collection/selection orchestration, structured-pair extraction, LLM reranking,
evidence construction, retry, artifact, mutable-state, and final sequencing.
Exact APIs, the eight-method characterization gate, call distribution, DAG, and
stop lines live only in
[project_status.md#next-work](../overview/project_status.md#next-work).
The sole selected implementation priority remains
[project_status.md#next-work](../overview/project_status.md#next-work); this plan
does not maintain a competing queue.

Use the existing owner modules before adding a new one. A Phase 3 batch must:

- start from a concrete caller, regression, reviewer gap, or named debt boundary;
- characterize current behavior before production movement;
- move adjacent seams together only when they share one owner, caller boundary,
  and validation surface;
- keep graph-state lookup, mutable state projection, LLM invocation, evidence
  construction, artifact/ledger mutation, and final orchestration in the graph
  unless a separate contract explicitly moves them;
- replace every selected caller and delete the old implementation in the same
  batch;
- add no wrapper, compatibility alias, callback, reason, flag, or trace field
  merely to make relocation easier;
- report source movement separately from behavior, total-code, executed-path,
  and performance claims.

Continue editing `financial_graph_calculation.py` only for a selected caller
migration, contract gap, or reproduced bug. Do not split the file solely to
reduce line count.

Completion conditions:

- met: legacy flat mirrors cannot override `agent_answer` or the resolved trace;
- partial: one source of truth exists for operands, formula result, and rendered
  answer, but graph-owned repair and ledger boundaries remain;
- partial: wrappers disappear as bounded owner moves delete their old bodies;
- open: broader ledger synchronization has a reviewed behavior contract;
- open: tests are organized by operand, execution, rendering, verification, and
  projection contracts rather than private helper location.

### Phase 4: Isolate optional systems

Status: completed on 2026-07-22. The default entrypoints pass fresh-process
import checks, and a deterministic `FinancialAgent` construction plus `run()`
invocation loads none of the reviewed MAS, evaluator, benchmark, promotion,
portfolio-review, or persisted-cache implementations. The only remaining local
cache-index import is guarded by an explicitly configured index path. Cache
candidate trace policy remains unchanged; further isolation requires a concrete
product requirement or observed default-runtime leak.

- Default runtime imports must not load MAS, evaluator, benchmark, cache
  promotion, or portfolio-review implementations.
- New MAS callers use `src.experimental.mas`; legacy `src.agent` MAS imports
  remain only while a verified external caller requires them.
- Candidate-only cache and promotion gates remain evaluation/internal surfaces
  until a separate product requirement enables them.
- Debug and review bundles are opt-in at API boundaries.

Completion condition: importing and invoking the default runtime does not load
optional systems, while their focused tests still pass independently.

### Phase 5: Reduce review and test noise

Status: completed on 2026-07-22. PR #84 reduced checked-in benchmark outputs to
history-linked compact summaries and small diagnostics, while full result
bundles remain local-only. The final documentation slice converted `CONTEXT.md`
and `docs/overview/project_status.md` from chronological diaries into current
state snapshots. Oversized tests were not split because no public behavior
changed; they remain an opportunistic cleanup alongside the contract they
exercise.

- Split oversized test files by public contract when touching the relevant
  behavior; do not perform an all-at-once test rewrite.
- Publish the portfolio claim through one structural summary, one plain
  comparison, and a small fixture set; internal history may retain compact
  directly linked summaries and diagnostics.
- Keep full local result bundles, stores, caches, and heartbeat logs untracked.
- Prefer current architecture docs over chronological implementation diaries.

Completion condition met: reviewer-facing docs link to a small evidence set,
while implementation history, experiment history, and Git preserve chronology
without defining the product surface.

## Deletion criteria

Before deleting or archiving a module, answer:

1. Is it required by `FinancialAgent.run()`?
2. Is it required by `FinancialParser.process_document()`?
3. Is it required by `VectorStoreManager.search()` or canonical ingest?
4. Is it required to create `structured_result` or
   `resolved_calculation_trace`?
5. Is it required by README quick-review commands?
6. Is it current evidence for a reviewer-facing claim?
7. Does a real external caller still use its compatibility path?

If every answer is no, delete it. If an answer is yes, move it to the correct
surface or preserve a narrow adapter with a named removal condition.

## Verification order

For every phase:

1. run the smallest owner/contract tests;
2. for changes under `src/agent` or `src/routing`, run
   `python -m src.ops.audit_runtime_domain_terms`;
3. run `python -m unittest discover -s tests`;
4. run `portfolio_review_gates` when reviewer-facing behavior changes;
5. use a focused store-fixed eval-only benchmark only when runtime behavior may
   affect answer quality;
6. run a full benchmark only with known store/cache inputs and heartbeat logs.

Always check `git diff --check` and artifact hygiene before handoff.

## Stop lines

Stop and reassess when:

- an extraction creates a new forwarding layer without moving callers;
- a deletion requires weakening a public contract;
- a runtime rule needs company, benchmark, or metric-specific vocabulary;
- evidence faithfulness decreases to improve a score;
- optional systems still leak into the default import path;
- a long benchmark has neither results nor a heartbeat;
- experimental artifacts would need to be committed without explicit approval.
