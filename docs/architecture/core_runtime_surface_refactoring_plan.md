# Core Runtime Surface Refactoring Plan

Last revised: 2026-08-08

This is the completed execution record for reducing repository complexity while
preserving the verified financial QA behavior. Git history,
`docs/history/implementation_history.md`, and
`docs/history/experiment_history.md` retain detailed chronology;
`docs/overview/project_status.md` contains current state only. This document
describes the resulting boundaries and stop lines.

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

Status: in progress. The first slice was merged in PR #80 on 2026-07-22 and the
second slice was merged in PR #81 on the same date. Both changes tighten public
projection ownership without splitting calculation helpers by file size. The
current owner-extraction slice does not complete Phase 3.

Completed first slice:

- owner: `src/api/financial_router.py::_query_response_from_agent_result`;
- when `agent_answer` is present, treat it as the canonical projection and
  preserve intentional empty strings, lists, and dictionaries;
- use legacy flat result fields only when `agent_answer` itself is absent;
- add the regression contract to `tests/test_financial_router_response.py`;
- keep retrieval, formula execution, and answer-generation behavior unchanged.

Proof: the focused router/projection/import suite passed `79` tests, full unit
test discovery passed `1350` tests, and `git diff --check` passed. No benchmark
refresh was required for this API-only compatibility change.

Second slice:

- `FinancialAgent.run()` now rejects legacy top-level `calculation_*` mirrors;
- public structured output reads explicit `structured_result` or the canonical
  trace calculation result;
- the callerless `_resolve_runtime_structured_result()` wrapper and its
  private-helper compatibility test were deleted;
- stale aggregate replacement remains covered through canonical active
  task/artifact ledger material;
- historical replay and retrospective resolver opt-ins remain unchanged.

Proof: the runtime domain-term audit passed with `216` reviewed literals, the
focused calculation projection suite passed `625` tests, full unit test
discovery passed `1348` tests, and `git diff --check` passed. No benchmark
refresh was required because retrieval and calculation behavior did not change.

Current owner-extraction slice:

- `financial_graph_calculation.py` remains the graph-state adapter and
  orchestrator: it decides when calculation owners run and projects their
  results into trace, task, and artifact state;
- `financial_operand_resolution.py` owns state-free operand candidate matching,
  grounding, generic candidate selection, and merge behavior;
- `financial_dependency_projection.py` owns dependency-binding summaries,
  state-free dependency projection, and the direct-versus-dependency source-set
  selector, including an explicit reason and provenance contract. It also owns
  the typed main-path application covering final ratio override or purge,
  producer-scope filtering, duplicate guarding, and missing-binding fill. Its
  typed late application performs coherent-first context merge, alignment and
  direct-context preference, complete-context veto, and dependency re-merge.
  Its typed terminal finalization applies an optional generic normalized-unit
  filter and, only without a filter, post-main-selected-snapshot-first then
  active-dependency-snapshot preservation;
- `financial_calculation_execution.py` validates ordered operand ids and variable
  bindings against the operand set, then returns a typed execution outcome for
  the graph adapter to project. It also owns state-free deterministic
  difference/growth plan construction, the typed raw/guarded plan decision, and
  value-only stale freshness assessment over a canonical prepared result;
- the graph adapter contains a graph-private typed candidate seam separating
  preparation/execution, deterministic result projection, and state/ledger
  projection. It also retains the operation-plan state/query adapter and primary
  runtime/task/artifact projection. This candidate decomposition is not itself an
  execution-owner move;
- candidate selection is invariant to input order: tied conflicting values
  abstain, while equivalent ties use a stable selection rule.

The bounded selector co-location removes the graph-injected callback seam: the
source-set selector invokes its co-located period-conflict and sibling-alignment
decisions directly. The following typed application slice moves the final ratio
override or purge, selector application, producer-scope filtering, duplicate
guard, and missing-binding fill behind the same dependency owner. The graph
still prepares that input through context/evidence retrieval gates and owns
retry, dependency-guard, logging, artifact, trace, and state projection.
Commit `b16a6c5` is a separate behavior fix: it removes consolidation- or
producer-scope-rejected rows from the active dependency snapshot before any late
fallback can reuse it. That fix passed `78` focused owner/graph contracts, the
`217`-literal runtime audit, and full discovery over `1,457` unit tests.

The following late-owner slice moves coherent-first direct-context merge,
alignment and preference, the complete-context veto, and dependency re-merge
application behind a typed state-free result. The graph still builds the sibling
and coherent evidence contexts. Commit `c6f6fdf` is a separate behavior fix: a
terminal percent-point filter that removes every late row can no longer restore
an unfiltered post-main selected or active dependency snapshot.

The following `5b44875` slice moves the generic normalized-unit filter and the
no-filter preservation order behind a typed state-free finalization result. The
graph retains the percent-point query gate and passes only
`required_normalized_unit`; it also retains logging, coverage, artifact, trace,
and state projection. Commit `8ebb239` is a separate behavior fix that recomputes
post-filter coverage so an empty result is `missing` and an incomplete required
set is `partial`. Other deterministic/LLM fallback, aggregate repair, and
stale-result execution remain graph orchestration. This is not end-to-end
precedence consolidation, and the typed late/finalization reasons are not yet
runtime trace fields.

The earlier calculation owner-extraction slice changed
`financial_graph_calculation.py` from `21,642` to `19,682` lines (`-1,960`),
while its source diff as a whole was `+1,095` lines. The typed main-path
application slice changes the graph adapter from `19,686` to `19,587` lines
(`-99`) while the two changed source files have a net increase of `109` lines
because the policy body moves into the dependency owner. Product-runtime
behavior is intended to remain unchanged; the precedence logic is relocated
behind one owner contract rather than removed from the executed path.

The late-owner slice changes `financial_graph_calculation.py` from `19,587` to
`19,564` lines (`-23`) and `financial_dependency_projection.py` from `2,656` to
`2,760` lines (`+104`). The two changed source files therefore have a net
increase of `81` lines. Product-runtime behavior is intended to remain
unchanged; the late precedence logic is relocated, not removed from execution.

After `c6f6fdf` moves the graph to `19,565` lines, the behavior-preserving
`5b44875` finalization relocation changes the graph to `19,567` lines (`+2`) and
the dependency owner from `2,760` to `2,833` lines (`+73`), for a structural
source net of `+75`. The separate `8ebb239` coverage fix leaves the final graph
at `19,576` lines. From the `77d5bff` baseline, the whole bounded slice changes
the graph by `+12` and the owner by `+73`, for a two-source net of `+85` lines.
The executed finalization policy moved owners; it was not removed from runtime.

Commit `f0eafae` is a separate behavior fix that prevents a source-stated display
from being repeatedly classified as stale when its traced formula value still
matches the current operands. The following structural commit `2496fce` moves
only the bound-operand formula comparison and typed freshness assessment into
`financial_calculation_execution.py`. That structural checkpoint changes
`financial_graph_calculation.py` from `19,591` to `19,558` lines (`-33`) and the
execution owner from `614` to `712` lines (`+98`), for a two-source net of `+65`.
From the `73d593e` baseline, the whole stale-result bounded slice changes the
graph from `19,576` to `19,558` lines (`-18`) and the execution owner by `+98`,
for a two-source net of `+80`.

Commit `406c1ef` separately characterizes stale execution snapshots. Structural
commit `c2a5e96` then decomposes the inline calculation path into graph-private
typed candidate preparation, result projection, and state/ledger projection.
Stale repair calls the preparation and result projection seam directly, removing
its recursive `_execute_calculation()` call and discarded ledger/trace projection
without changing product behavior. This changes the graph from `19,558` to
`19,730` lines (`+172`); full discovery at that checkpoint passed `1,473` tests.
The candidate seam remains graph-private and this commit does not remove the two
formula evaluations in an actual stale repair.

Behavior fix `f2af4f4` makes the prepared canonical value the freshness authority.
A pre-preparation raw value of `0.0035` that previously appeared current is now
compared with the prepared canonical value `3.5` and repaired. The stale path
evaluates its formula once instead of twice. Current results still prepare and
evaluate once, and deterministic result projection runs only for a stale value.
The execution owner changes from `712` to `679` lines (`-33`) and the graph from
`19,730` to `19,736` (`+6`), for a source net of `-27`; the whole source/test diff
for this behavior slice is net `-83` lines. No ledger or selected-claim
synchronization is added.

Behavior fix `be2e7bf` then synchronizes accepted stale-repair provenance at the
three production caller boundaries without changing numeric freshness or repair
acceptance. Render updates selected/kept refs and the latest same-id
calculation-result artifact; planning capture updates only its returned row refs;
aggregate repair uses a pre-filter evidence snapshot, supersedes only a unique
provenance target, and re-filters after acceptance. Ambiguous refs are preserved.
This changes the graph from `19,736` to `19,933` lines (`+197`), graph planning
from `2,367` to `2,371` (`+4`), and task artifacts from `1,047` to `1,128`
(`+81`). The production-source diff is `+332/-50`, net `+282`; the whole commit is
`+792/-69`, net `+723`. This is caller-specific synchronization, not completion
of the whole task/artifact ledger contract.

Structural commit `2cfa867` then relocates the pure aggregate stale-repair
provenance selection without changing behavior. `financial_aggregate_projection.py`
now owns the typed state-free selection and canonical
`aggregate_result_operation_family`; the old graph provenance bodies are deleted.
The graph retains a one-line delegate for its 68 existing operation-family
callers, plus repair acceptance, pre-filter snapshot, accepted re-filter, and
answer/state orchestration. The graph changes from `19,933` to `19,802` lines
(`-131`, `+15/-146`) and the owner from `195` to `376` (`+181`, `+182/-1`).
Production source is `+197/-147`, net `+50`; the whole commit is `+392/-184`, net
`+208`. These numbers show owner relocation and graph reduction, not total-code
or executed-path reduction.

Structural commit `1a3979e` then adds the graph-private typed
`_CalculationCandidateRun` and `_run_calculation_candidate()` seam. The primary
`_execute_calculation()` graph-node adapter continues to apply the existing
state/ledger projector. Dependency and period contract-valid scalar recovery
consume the candidate projection's operands, plan, and result copies directly,
removing two internal `_execute_calculation()` calls, their strict trace
re-reads, and the state/ledger projections those callers discarded. Result and
operand order, input immutability, and failure/no-op identity remain unchanged.
The graph changes from `19,802` to `19,813` lines; source is `+36/-25`, net `+11`.
Tests are `+176/-57`, net `+119`, and the whole commit is `+212/-82`, net `+130`.
The state projector changes from one call to zero in the two characterized
success paths. These figures are not a broad performance or total-code reduction
claim, and a reused abnormal dependency `time_series` plan is outside the full
exception-parity claim. The seam remains graph-private; this is not an execution
owner move or Phase 3 completion.

Structural commit `af968a6` moves the state-free deterministic difference/growth
builder and typed raw/guarded operation-plan decision into
`financial_calculation_execution.py`. The graph retains a thin state/query adapter
around owner construction and the difference result-unit policy, and the primary
planner retains its full runtime and task/artifact projection. Period recovery consumes a ready or
guarded selected plan directly, with no planner/artifact/runtime projection, while
a `not_applicable` decision continues through the existing fallback without a
second builder call. Dependency recovery still uses the raw-plan callback. The
execution owner changes from `679` to `837` lines (`+158`) and the graph from
`19,813` to `19,786` lines (`-27`, `+91/-118`). Production source is `+249/-118`,
net `+131`; tests are `+182/-5`, net `+177`; the whole commit is `+431/-123`, net
`+308`. Supported, contract-valid result, order, input, failure, and no-op
contracts are preserved. Malformed difference inputs remain outside a full
query-policy evaluation/exception-order parity claim. These figures do not
establish total-code reduction, broad executed-path or performance improvement,
or Phase 3 completion.

Behavior fix `ec93f8a` separately corrects the pre-existing percent-point unit
gate in that adapter. It constructs the complete plan before calling
`_should_coerce_percent_point_unit`; an eligible `%p` query with two `PERCENT`
operands receives a copied plan with `result_unit="%p"`, while non-eligible and
no-plan cases remain unchanged. The graph diff is `+9/-9`, so its line count is
unchanged; tests add `32` lines, and the whole commit is `+41/-9`, net `+32`.
This fixes the incomplete-plan unit-policy bug, but it does not establish full
evaluation/exception-order parity for every malformed difference input.

Behavior fix `8296eb1` separately blocks a stale-parent trace override. Parent
`structured_result` or `subtask_results` can no longer replace the explicit
dependency recalculation trace before candidate preparation. The dependency
owner changes from `2,833` to `2,835` lines (`+2`); the regression test adds `63`
lines, and the whole commit is net `+65`. This is a correctness fix, not part of
the following mechanical relocation.

Structural commit `ea84921` then removes the dependency synthetic-state helper
and raw-plan builder callback while preserving supported scalar behavior. The
graph skips raw construction for an existing executable plan and constructs it
once for an invalid or absent plan, passes that explicit raw plan to the
dependency owner, runs a direct `_CalculationCandidateInput`, and supplies ratio
formatting with the active task and the same pre-candidate operands. Result/order,
input immutability, and failure/no-op identity remain unchanged. The graph changes
from `19,786` to `19,828` lines (`+75/-33`, net `+42`) and the dependency owner
from `2,835` to `2,796` (`+3/-42`, net `-39`). Production source is `+78/-75`,
net `+3`; tests are `+167/-90`, net `+77`; the whole commit is `+245/-165`, net
`+80`. These figures show a bounded callback/state cleanup, not total-code
reduction, broad performance improvement, dependency-owner completion, or Phase
3 completion. Primary state/artifact projection, repair acceptance, and
absolute-ratio orchestration remain graph-owned.

Validation for this slice: `62` focused operand/execution contract tests, `323`
focused calculation/projection tests, the runtime domain-language audit over
`217` reviewed literals, and full discovery over `1,451` unit tests passed. This
was the earlier extraction evidence. The typed main-path application passed `76`
focused owner/graph contracts, the same `217`-literal audit, and full discovery
over `1,457` unit tests. These are contract and regression evidence, not a
refreshed benchmark claim. After the separate `b16a6c5` behavior fix, the late
typed application passed `78` focused owner/graph contracts, the same
`217`-literal audit, and full discovery over `1,462` unit tests. The terminal
filter fix `c6f6fdf` passed `3` focused contracts, the same audit, and full
discovery over `1,462` tests. The behavior-preserving `5b44875` extraction passed
`52` focused contracts, the same audit, and full discovery over `1,468` tests.
After `8ebb239`, `53` focused contracts, the same audit, and full discovery over
`1,468` tests passed on Python 3.13. After `f0eafae` and `2496fce`, `29` focused
stale/execution contracts, the same `217`-literal audit, and full discovery over
`1,472` tests passed on Python 3.13. After `f2af4f4`, `345` unique focused
contracts passed; the `7`-contract core subset and `2` adapter/time-series spot
contracts were also rerun. The `217`-literal audit and full discovery over
`1,472` tests passed on Python 3.13. After `be2e7bf`, all `560` affected-module
tests, the same `217`-literal audit, and full discovery over `1,472` tests passed
on Python 3.13. After `2cfa867`, all `564` affected tests, the same `217`-literal
audit, and full discovery over `1,476` tests passed. After `1a3979e`, `3` focused
contracts and all `564` affected tests passed, together with the same
`217`-literal audit and full discovery over `1,476` tests. After `af968a6`, `4`
targeted contracts, `107` focused owner/aggregate tests, all `564` affected tests,
the same `217`-literal audit, and full discovery over `1,478` tests passed.
After `ec93f8a`, `4` targeted/adjacent tests and all `29` execution-module tests
passed; the unique affected matrix contained `593` passing tests, and the same
`217`-literal audit and full discovery over `1,479` tests passed. After
`8296eb1`, `4` targeted tests, the same audit, and full discovery over `1,480`
tests passed. After `ea84921`, `3` targeted contracts, all `615` affected tests,
the same audit, and full discovery over `1,479` tests passed. Benchmark refresh
has not run for these latest changes.

Phase 3 remains open for these follow-ups:

- characterize reused abnormal dependency `time_series` executable plans and the
  state-projector exception boundary before deciding whether they are supported;
- if that abnormal path is not a supported contract, continue with the next
  bounded repair cluster without folding in a behavior change;
- keep broader task/artifact ledger synchronization as a separately specified
  contract rather than inferring it from the three repaired caller surfaces;
- move the remaining deterministic/LLM fallback and aggregate precedence
  orchestration behind named owner contracts;
- reduce the remaining private-API mesh;
- characterize the remaining graph-owned absolute-ratio and trend
  projection/error boundaries before moving them;
- extract the remaining extraction and aggregate repair clusters behind named
  contracts.

The canonical path is:

```text
OperandResolver -> FormulaExecutor -> AnswerRenderer -> Verifier
```

Use existing owner modules before adding new ones:

- `financial_answer_slots.py`
- `financial_operand_resolution.py`
- `financial_dependency_projection.py`
- `financial_calculation_execution.py`
- `financial_graph_calculation_rendering.py`
- `financial_runtime_trace.py`
- `financial_answer_projection.py`

Continue work in `financial_graph_calculation.py` only for a concrete caller
migration, contract gap, or bug. Each extraction must move callers and delete
the old implementation. Do not split the file merely to reduce line count.

Completion conditions:

- one source of truth for operands, formula result, and rendered answer;
- legacy flat mirrors cannot override `agent_answer` or the resolved trace;
- wrappers with no runtime caller are removed;
- tests are organized by operand, execution, rendering, verification, and
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
