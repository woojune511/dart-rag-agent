# Core Runtime Surface Refactoring Plan

Last revised: 2026-08-08

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
broader single-calculation-path phase is not complete.

Current calculation ownership is:

- `financial_graph_calculation.py` remains the graph-state adapter and
  orchestrator. It constructs and coerces direct rows, applies consolidation
  scope and target-override policy, prepares evidence/query inputs, builds
  required candidates, applies dependency producer-scope filtering, and invokes
  the coherent-context builder lazily. It also owns direct structured preference
  preparation through runtime evidence overlay, row iteration, peer-unit
  preparation, strongest-slot building and scoring, recovered-context
  eligibility, document/evidence and context-row builders, recovery logging and
  ratio-recovered flag projection, retry gates,
  graph-private candidate preparation, state/task/artifact projection, repair
  acceptance, aggregate/filter sequencing, and remaining fallbacks.
- `financial_operand_resolution.py` owns state-free candidate matching,
  grounding, selection, and merge behavior, including coherent-first required
  candidate merge followed by complete-ratio candidate-first or current-first
  precedence. It also owns ordered typed direct structured acceptance across
  required match/surface, ambiguity, and lookup direct-support gates, plus typed
  prepared preferred-slot score/ratio-alignment adoption and exact overlay. It
  owns recovered-context period merge or coherent-ratio replacement and
  referenced evidence adoption after graph-owned builders run.
- `financial_dependency_projection.py` owns dependency binding/projection,
  direct-versus-dependency selection, typed main/late/final application, and
  dependency recalculation plan disposition. Executable `single_value` plans
  are reused, invalid or absent plans rebuild once, and executable
  non-`single_value` plans are `unsupported_mode`, do not recalculate that row,
  and preserve original result identity on the enclosing no-change path before
  builder, candidate, or formatter work.
- `financial_calculation_execution.py` owns deterministic difference/growth
  plan construction, plan validation, formula execution, and value-only stale
  assessment.
- `financial_aggregate_projection.py` owns pure stale provenance target
  selection and canonical aggregate operation-family normalization.

At the latest checkpoint, the graph is 19,756 lines, the operand owner is 2,151,
the dependency owner is 2,813, and the execution owner is 837. The latest owner
slice passed 5/5 targeted and 153/153 affected tests, the 217-literal audit, and
full discovery over 1,484/1,484 tests on Python 3.13. Benchmark refresh is NOT
RUN. Exact commit boundaries, intermediate metrics, and claim limits live in
`docs/history/implementation_history.md`; they are intentionally not repeated
in this plan.

Phase 3 remains open for these unordered follow-ups:

- characterize bounded post-coercion LLM selection and remaining graph-prepared
  direct-preference builder/scoring seams as separate slices without moving graph
  state or builders;
- move bounded aggregate repair/precedence decisions behind the aggregate owner;
- isolate dependency post-candidate finalization and ratio
  artifact/absolute-magnitude seams without moving graph state lookup;
- keep broader task/artifact ledger synchronization as a separately specified
  behavior contract;
- reduce the remaining private-API mesh and co-locate tests only as their public
  contracts move.

Priority and sequencing are owned by
`docs/overview/project_status.md#next-work`; this plan records debt and stop
lines, not a competing queue.

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

- partial: converge on one source of truth for operands, formula result, and
  rendered answer;
- met: legacy flat mirrors cannot override `agent_answer` or the resolved trace;
- partial: remove wrappers with no runtime caller as each bounded owner move
  deletes its old implementation;
- open: organize tests by operand, execution, rendering, verification, and
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
