# Core Runtime Surface Refactoring Plan

Last revised: 2026-08-14

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
| Operand resolution and policy | `financial_operand_resolution.py` | State-free candidate resolution and complete deterministic candidate scoring, direct/ratio acceptance, lookup-hint projection/matching, candidate location/entity subject scoring, deterministic positional preference scoring, unit/period coercion, dependency-task KRW consistency, table-metadata/raw-unit repair, growth alignment/period conflict, and ratio sign policy; no graph-state lookup |
| Dependency projection | `financial_dependency_projection.py` | State-free dependency precedence, projection, recalculation disposition, provenance adoption, and related predicates; KRW-consistency implementation now belongs to operand resolution |
| Formula execution | `financial_calculation_execution.py` | Deterministic plan construction, validation, execution, and value freshness |
| Rendering and answer surfaces | `financial_graph_calculation_rendering.py`, `financial_answer_slots.py`, `financial_answer_projection.py`, `financial_numeric_surface.py`, `financial_text_surface.py` | Ratio/result rendering, slot/readiness contracts, narrative validation, numeric comparison, table support, scale predicates, and shared term/variant/context sentence surfaces |
| Aggregate projection | `financial_aggregate_projection.py` | State-free aggregate calculation/public projection, subtask upsert/rank, signatures, source preparation, dependency-coherence ranks, own-evidence lookup-unit alignment, repair/projection transforms, compact prompt rows, row/sentence/rendered selectors, narrative-row/gap policy, and lookup-answer surfaces |
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
operand append and surface-operand projection. Candidate report/period scope,
single-report-scope classification,
surface/segment contracts, delta-like row-label classification, local aggregate
context, consolidation scope,
binding-shape admission, selected-unit-family projection, deterministic
positional preference scoring, and complete operand-candidate scoring are also
owner-held.
Current
validation and benchmark
status belong only in
[project_status.md](../overview/project_status.md); commit-level diffs and claim
limits belong only in
[implementation_history.md](../history/implementation_history.md).

Phase 3 remains open for four durable debt groups:

1. partially advanced: aggregate calculation/public projection and subtask
   upsert/rank, period/material/source/coherence/rank/dedupe, selected
   narrative-validation policy, bounded row/gap/lookup-answer surfaces, and
   final-answer evidence/surface-operand projection and growth-answer completion/
   sanitization are owned, while promotion, sync/rebuild, mutable state/evidence,
   and final sequencing remain graph-owned;
2. partially advanced: ratio presentation/readiness/scale, bounded operand-
   preparation, and unit/table-repair seams are owned; isolate remaining dependency
   and ratio/absolute seams that do not require graph-state lookup; lookup answer-
   slot/support projection is now owner-held, while broader evidence orchestration
   and surrounding sequencing remain graph-owned;
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
state-free owners. Lookup active-task matching, prose answer-slot synthesis,
evidence-unit refinement, and supporting-document projection are also owner-
resident. Aggregate dependency-source seed/scoring/selection/component
preparation, narrative row-focus selection, and aggregate growth display/material
projection, result support/reuse predicates, prepared growth/ratio material
inspection, prepared growth-numeric rendering, and growth trace inspection are
also owner-resident. Dependency input matching, sibling-output synthesis
preference, task-output binding projection, prepared runtime-evidence merge, and
ratio task-artifact row projection are owner-resident as well. Final-answer
evidence filtering, operand-evidence append, and surface-operand projection are
also owner-resident. Generic operand-period, single-report-scope classification,
structured-cell selection/scoring, and candidate report/period-scope matching/
scoring are owner-resident as well.
Retained external graph call placements remain,
while broader evidence repair,
dependency-source lookup/source mapping, answer composition/refresh,
evidence construction, promotion, sync/rebuild, mutable state/evidence, ledger,
callbacks, and final projection remain outside those owner batches.

The completed `06710c1` follow-on is another ownership relocation only. It moved
the former 69 + 36 + 23 + 28 = 156 aggregate projection/upsert definition-span
lines to three public plus one owner-private aggregate-owner functions totaling
68 + 35 + 22 + 28 = 153 lines. Six calls finish as four graph-external and two
owner-local; the distinct runtime-trace private aggregate builder remains live.
Source is `+181/-184`, tests are `+1,143/-41`, and the whole commit is
`+1,324/-225`. Planning moved from 2,356 to 2,180 physical lines, aggregate
projection from 3,180 to 3,350, calculation from 14,716 to 14,718, and the main
graph from 936 to 937. Seven new unittest methods moved full discovery from
1,764 to 1,771. Final gates passed focused 7/7, aggregate-subtask owner 118/118,
affected semantic 780/780, import 19/19, semantic/import union 799/799, audit
217, full discovery 1,771/1,771, pycompile/fresh import, DAG/body/caller parity,
and diff check. Its source diff SHA-256 is
`0cb0b708ee672f115f0a06eea62217f598e87d1a194f6422d422ba126bb51f7b`.
Benchmark refresh was **NOT RUN** and remote CI is unverified.

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

The completed `bb0a982` follow-on is another ownership relocation only. It moved
the former 293 structured-reconciliation candidate-projection definition-span
lines to seven public plus four owner-private functions totaling 285 lines in the
new `financial_reconciliation_candidates.py` owner. Twenty-six calls finish as
19 reconciliation-external and seven owner-local; retired selected private refs
are zero. Source is `+357/-331`, tests are `+686/-30`, and the whole commit is
`+1,043/-361`. Reconciliation moved from 2,079 to 1,776 physical lines, the new
owner contains 329, and eight new unittest methods moved full discovery from
1,750 to 1,758. Final gates passed focused 8/8, candidate owner 8/8, affected
semantic 486/486, import 19/19, semantic/import union 505/505, audit 217, full
discovery 1,758/1,758, pycompile/fresh import, DAG/body/caller parity, and diff
check. Its source diff SHA-256 is
`6469dfd06b0efd36c92d252753ba96ecdeb5421e4dc3fdaac0c492cdd4167a5f`.
Benchmark refresh was **NOT RUN** and remote CI is unverified.

Candidate collection/selection, structured-pair and operand extraction
orchestration, LLM reranking, evidence construction, retry, artifact/state,
ledger, and final sequencing remain excluded.

The completed `b74535e` follow-on is another ownership relocation only. It moved
the former 107 reflection retry-query definition-span lines to two public
functions totaling 106 lines in the existing reflection owner. Three calls
finish as two graph-external and one owner-local; retired selected private refs
are zero. Source is `+118/-112`, tests are `+1,113/-4`, and the whole commit is
`+1,231/-116`. Reconciliation moved from 1,776 to 1,667 physical lines,
reflection projection from 260 to 374, and six new unittest methods moved full
discovery from 1,758 to 1,764. Final gates passed focused 6/6, reflection owner
24/24, affected semantic 758/758, import 19/19, semantic/import union 777/777,
audit 217, full discovery 1,764/1,764, pycompile/fresh import, DAG/body/caller
parity, and diff check. Its source diff SHA-256 is
`728603f15ce24c0915444755442bc6cf3be4a2bbd26c6f41adffedcb08ccdbb1`.
Benchmark refresh was **NOT RUN** and remote CI is unverified.

Heuristic dependency/calc-family resolution, prompt/LLM planning, action/report/
artifact projection, mutable state, routing/promotion, and final sequencing
remain excluded. The nested subtask selection/promotion batch and its two-seam
aggregate-result follow-on are now complete. Commits `8e840b8` and `b5d97ee`
moved the former 64 + 124 definition-span lines into two public aggregate-owner
functions totaling 186 lines. Four calls remain graph-external. Across the
range, source is `+197/-204`, tests are `+1,569/-184`, and full discovery is
1,789/1,789. Task/state capture, dependency alignment, projection rebuild,
mutable state/evidence, artifact/ledger mutation, and final sequencing remain
excluded.

The completed `b3bb764` follow-on moved the former 53-line duplicate
growth-prior recovery transform into `financial_aggregate_projection.py` as one
52-line public function. Its sole call remains graph-external in calculation
candidate preparation. Source is `+56/-55`, tests are `+629/-26`, and the whole
commit is `+685/-81`. Calculation moved from 14,521 to 14,468 physical lines,
aggregate projection from 3,541 to 3,595, and four new unittest methods moved
full discovery from 1,789 to 1,793. Final gates passed focused 4/4, aggregate
owner 80/80, affected semantic 838/838, import 19/19, semantic/import union
857/857, audit 217, full discovery 1,793/1,793, pycompile/fresh import,
DAG/body/caller parity, and diff check. The source diff SHA-256 is
`1a02ec371d28b6012b064281260ad3b274bc9f1ef0b330d0724c36d545b56d1a`.
Benchmark refresh was **NOT RUN** and remote CI is unverified. Candidate
preparation, direct evidence selection, unit/period alignment, execution,
state/evidence orchestration, rebuild, artifact/ledger mutation, and final
sequencing remain graph-owned.

The completed `d31e67a` follow-on moved the former 48-line final aggregate
evidence/provenance projection transform into `financial_aggregate_projection.py`
as one 47-line public function. Its two calls remain graph-external in aggregate
orchestration. Source is `+52/-53`, tests are `+646/-41`, and the whole commit
is `+698/-94`. Calculation moved from 14,468 to 14,418 physical lines,
aggregate projection from 3,595 to 3,644, and four new unittest methods moved
full discovery from 1,793 to 1,797. Final gates passed focused 4/4, aggregate
owner 84/84, affected semantic 806/806, import 19/19, semantic/import union
825/825, audit 217, full discovery 1,797/1,797, pycompile/fresh import,
DAG/body/caller parity, retired-ref zero, and diff check. The source diff
SHA-256 is
`f10c327aca0fb5a4a885892354bef1b840caaf224a9696ae113c9d650df45df1`.
Benchmark refresh was **NOT RUN** and remote CI is unverified. Evidence
preparation, stale/runtime-ratio repair, mutable state synchronization,
composition, artifact/ledger mutation, and final sequencing remain graph-owned.

The completed `8861253` follow-on moved the former 310-line collapsed-ratio
evidence repair transform into `financial_runtime_trace.py` as one 309-line
public function. Its two calls remain graph-external. Source is `+322/-315`,
tests are `+1,574/-166`, and the whole commit is `+1,896/-481`. Calculation
moved from 14,418 to 14,106 physical lines, main graph from 937 to 938, runtime
trace from 1,094 to 1,412, and six new unittest methods moved full discovery
from 1,797 to 1,803. Final gates passed focused 6/6, aggregate-subtask 124/124,
text-surface 20/20, affected semantic 832/832, import 19/19,
semantic/import union 851/851, audit 217, full discovery 1,803/1,803,
pycompile/fresh import, DAG/body/caller parity, retired-ref zero, and diff check.
The source diff SHA-256 is
`a83d1ddaa2167516789bc9de1a90033dd7183d6764ddf0609bf91a777199e451`.
Benchmark refresh was **NOT RUN** and remote CI is unverified. Public-answer
orchestration, period repair, retrieval/canonical evidence construction,
mutable state/evidence, artifact/ledger mutation, and final sequencing remain
graph-owned.

The completed `5f9dc5c` follow-on moved the former 81-line direct structured
lookup-row and 139-line direct structured operand-value projections into
`financial_lookup_recovery.py` as public 80-line and 138-line functions. All
five calls remain graph-external. Source is `+241/-229`, tests are `+1,229/-8`,
and the whole commit is `+1,470/-237`. Calculation moved from 14,106 to 13,887
physical lines, lookup recovery from 557 to 788, and eight new unittest methods
moved full discovery from 1,803 to 1,811. Final gates passed focused 4/4 per
seam and combined 8/8, lookup owner 24/24, migrated operation contracts 4/4,
affected semantic 818/818, import 19/19, semantic/import union 837/837, audit
217, full discovery 1,811/1,811, pycompile/fresh import, DAG/body/caller parity,
retired-ref zero, and diff check. The source diff SHA-256 is
`c4b9c78f90715b4332b559159220e00e6f00d46d2912a4f982cdbabaf0fd271e`.
Benchmark refresh was **NOT RUN** and remote CI is unverified. Evidence-pool
selection/scoring, graph state/report scope, table-label lookup, precision
refinement, mutable evidence, artifact/ledger mutation, and final sequencing
remain graph-owned.

The completed `a476dd9` follow-on moved the former 62-line own-evidence lookup-
unit alignment transform into `financial_aggregate_projection.py` as one
61-line public function. Its two calls remain graph-external. Source is
`+74/-68`, tests are `+786/-13`, and the whole commit is `+860/-81`.
Calculation moved from 13,887 to 13,823 physical lines, aggregate projection
from 3,644 to 3,714, and four new unittest methods moved full discovery from
1,811 to 1,815. Final gates passed focused 4/4, aggregate owner 88/88, migrated
direct contract 1/1, affected semantic 882/882, import 19/19,
semantic/import union 901/901, audit 217, full discovery 1,815/1,815,
pycompile/fresh import, DAG/body/caller parity, retired-ref zero, and diff
check. The source diff SHA-256 is
`bbe5f3cc62535f3fe8b6d2c2a4a56a27b10d0515cf0fff2083105d34ed171e19`.
Benchmark refresh was **NOT RUN** and remote CI is unverified. Peer-source
callback alignment, evidence preparation, dedupe/rebuild, dependency
alignment, mutable state/evidence, artifact/ledger mutation, and final
sequencing remain graph-owned.

The completed `c021d30` follow-on moved the former 37-line runtime deterministic-
operation adapter and 200-line ontology plan into
`financial_calculation_execution.py` as public 36-line and 195-line functions.
All four selected calls remain graph-external. Source is `+247/-244`, tests are
`+1,111/-17`, the reviewed baseline is `+9/-9`, and the whole commit is
`+1,367/-270`. Calculation moved from 13,823 to 13,589 physical lines, the
execution owner from 837 to 1,074, and nine new unittest methods moved full
discovery from 1,815 to 1,824. Final gates passed focused 4/4 then 5/5 and
combined 9/9, execution owner 45/45, affected semantic 883/883, import 19/19,
semantic/import union 902/902, audit 217, full discovery 1,824/1,824,
pycompile/fresh import, DAG/body/caller parity, retired executable private-ref
zero, and diff check. Its source diff SHA-256 is
`3d93584b12246297296b01f738fedb55e3b8aa71b7805b5d7003f430bbfd411b`.
Benchmark refresh was **NOT RUN** and remote CI is unverified. Dynamic metric-
family dispatch, deterministic lookup/LLM planning, state/trace/artifact work,
execution orchestration, and final sequencing remain graph-owned.

The completed `6d54b2f` follow-on moved the former 85-line marker-group, 8-line
flattened-marker, and 127-line source-visible term-preservation definitions into
`financial_text_surface.py` as three public functions totaling 219 lines.
Twelve selected calls finish external ten/local two, the text owner is now
public/private 15/4, and retired private definitions/calls/patches plus the
evidence stopword alias are zero. Source is `+255/-245`, tests are
`+1,199/-41`, the baseline is `+12/-3`, and the whole commit is
`+1,466/-289`. Calculation moved from 13,589 to 13,464 physical lines, graph
evidence from 4,581 to 4,579, retrieval from 2,736 to 2,642, and text surface
from 411 to 642. Ten new tests moved full discovery from 1,824 to 1,834.
Final gates passed focused 5/5 per seam, combined 10/10, text owner 30/30,
affected semantic 808/808, import 19/19, audit 218, full discovery
1,834/1,834, pycompile/fresh import, DAG/body/caller parity, retired-ref zero,
and diff check. The source-only diff SHA-256 is
`b27abac6c0b25f3e8aa888856ba7017c5b300463c7da4cbe68c7096e401781be`.
Benchmark refresh was **NOT RUN** and remote CI is unverified. Retrieval/
reranking, evidence construction, aggregate orchestration, mutable state/
evidence, artifact/ledger work, and final sequencing remain graph-owned.

The completed `79a460a` follow-on moved the former 202-line prepared structured
period-pair projection from `financial_graph_reconciliation.py` into
`financial_reconciliation_candidates.py` as public 201-line
`extract_structured_period_pair_rows(...)`. Its sole nine-keyword call remains
direct, graph-external, and outside `try`; the candidate owner is now
public/private 8/4. Source is `+207/-204`, tests are `+763/-29`, and the whole
commit is `+970/-233`. Reconciliation moved from 1,667 to 1,465 physical lines,
the candidate owner from 329 to 534, and six new test methods moved full
discovery from 1,834 to 1,840. Final gates passed focused 6/6, candidate owner
14/14, affected semantic 787/787, import 19/19, audit 218, full discovery
1,840/1,840, pycompile/fresh import, DAG/body/caller parity, retired-ref zero,
and diff check. Its source diff SHA-256 is
`8bd82f6adb5e9722771953888dbeef6e129332ae4b749b6483ba46017db7cf3e`.
Benchmark refresh was **NOT RUN** and remote CI is unverified. Full operand
extraction, candidate collection/selection, LLM reranking, evidence
construction, artifact/retry/state mutation, ledger work, and final sequencing
remain graph-owned.

The completed `fb970a5` follow-on moved eight semantic-planner normalization
and validation definitions totaling 273 old lines from
`financial_graph_planning.py` into `financial_graph_helpers.py` as five public
and three owner-private functions totaling 271 lines. Sixteen selected calls
finish graph-external nine and owner-local seven, all outside `try`. Source is
`+303/-296`, tests are `+1,557/-9`, and the whole commit is `+1,860/-305`.
Planning moved from 2,048 to 1,765 physical lines, graph helpers from 6,269 to
6,559, and seven new tests moved discovery from 1,840 to 1,847. Final gates
passed focused 7/7, helper owner 12/12, affected semantic 434/434, import 19/19,
audit 218, full discovery 1,847/1,847, pycompile/fresh import, DAG/body/caller
parity, retired-ref zero, and diff check. Its source diff SHA-256 is
`9e0310f17edd4ea004425957e8044fc6ae0f79538ab140bd4a9e8007aa4d63cc`.
Benchmark refresh was **NOT RUN** and remote CI is unverified. Model invocation,
query routing, plan adoption, mutable task/state/artifact/ledger work, and final
sequencing remain graph-owned.

The completed `f9244d6` follow-on moved six narrative-task policy definitions
totaling 143 lines from `financial_graph_planning.py` into
`financial_graph_helpers.py` as four public and two owner-private functions.
Thirteen selected calls finish graph-external six and owner-local seven, all
outside `try`. Source is `+173/-173`, tests are `+1,245/-15`, and the whole
commit is `+1,418/-188`. Planning moved from 1,765 to 1,602 physical lines,
graph helpers from 6,559 to 6,722, and six new tests moved discovery from 1,847
to 1,853. Final gates passed focused 6/6, helper owner 18/18, affected semantic
440/440, import 19/19, audit 218, full discovery 1,853/1,853,
pycompile/fresh import, DAG/body/caller parity, retired-ref zero, and diff
check. Its source diff SHA-256 is
`da20f913c7205a1e0694ce655b91b8dad0b1d43437a6099626881716ded176b0`.
Benchmark refresh was **NOT RUN** and remote CI is unverified. LLM/model
invocation, logical/execution task projection, query routing, plan adoption,
task/state/artifact/ledger mutation, retrieval/evidence work, and final
sequencing remain graph-owned.

The completed `ae1f599` follow-on moved ten lookup answer-slot/support
definitions totaling 342 lines plus three policy regex bindings from planning
into `financial_lookup_recovery.py` as public four plus owner-private six.
Fifteen calls finish graph-external six and owner-local nine. Source is
`+383/-379`, tests are `+1,133/-12`, and the whole commit is `+1,516/-391`.
Planning moved from 1,602 to 1,240 physical lines, lookup recovery from 788 to
1,154, and eight new tests moved discovery from 1,853 to 1,861. Final gates
passed focused 8/8, owner 32/32, affected semantic 864/864, import 19/19, audit
218, full 1,861/1,861, pycompile/fresh import, DAG/body/caller parity, retired-
ref zero, and diff check. Retrieval/prepared-document pool construction,
mutable result/evidence/state, nested-result promotion, calculation/dependency
orchestration, trace/artifact/ledger work, and final sequencing remain hard
stops.

The completed `02d1422` follow-on moved three read-only evidence-hint
definitions totaling 117 lines from `financial_graph_evidence.py` into
`financial_retrieval_hints.py` as three public functions. All three calls remain
graph-external, while the active preferred-section helper call is owner-local.
Source is `+134/-125`, tests are `+830/-0`, and the whole commit is
`+964/-125`. Graph evidence moved from 4,579 to 4,461 physical lines, retrieval
hints from 167 to 294, and five new tests moved discovery from 1,861 to 1,866.
Final gates passed focused 5/5, affected semantic 692/692, import 19/19, audit
218, full 1,866/1,866, pycompile/fresh import, DAG/body/caller parity, retired-
ref zero, and diff check. Its source diff SHA-256 is
`d2925a071c1555658c448d0779168e851304e7602431df8da216904dc60959ec`.
Context/model construction, evidence construction/ranking/mutation, mutable
state, trace/artifact/ledger work, and final sequencing remain graph-owned.

The completed `4cdbf93` and `6d6ce2a` follow-on moved generic operand-period
policy and structured-cell selection/scoring from `financial_graph_helpers.py`
into `financial_scope_policies.py` and `financial_structured_cells.py`. The old
29/11/42/84/53/66-line definitions total 285 lines; five are public and affinity
remains owner-private. The 57 selected calls finish external 53/owner-local
four, and retired graph-private source/test refs are zero. Across
`9fe1a45..6d6ce2a`, source is `+390/-371`, tests `+2,086/-49`, and the whole
range `+2,476/-420`. Graph helpers moved from 6,722 to 6,429 physical lines,
scope policy 168 to 215, structured cells 73 to 335, and ten new tests moved
discovery from 1,871 to 1,881. Final gates passed combined focused 10/10,
affected semantic 838/838, import 19/19, audit 218, full 1,881/1,881,
pycompile/fresh import, DAG/body/full-caller parity, retired-ref zero, and diff
check. Candidate/evidence construction and adoption, direct structured lookup/
value projection, reconciliation orchestration, mutable state/evidence,
callbacks, carriers, trace/artifact/ledger work, and final sequencing remain
graph-owned.

The completed `ba35519` follow-on moved 228 candidate report/period-scope
definition-span lines from `financial_graph_helpers.py` into
`financial_scope_policies.py` as public four plus owner-private two. Its 18
calls finish external 10/local eight. Source is `+257/-253`, tests are
`+1,416/-16`, and the whole commit is `+1,673/-269`. Graph helpers moved from
6,429 to 6,191 physical lines, scope policy from 215 to 457, and six new methods
moved discovery from 1,881 to 1,887. Final gates passed focused 6/6, affected
semantic 844/844, import 19/19, audit 218, full 1,887/1,887, pycompile/fresh
import, DAG/body/full-caller parity, retired-ref zero, and diff check. The source
diff SHA-256 is
`853f3a95a4ef0bf8aa5e4900b62d04deef48b1dd6fb58278d75a7b550c61dc01`.
Candidate/evidence construction/adoption, broad scoring/reconciliation, mutable
state/evidence, callback, carrier, trace/artifact/ledger work, and final
sequencing remain hard stops.

The completed `3ca0144` follow-on moved 128 candidate surface-contract/segment-
binding definition-span lines from `financial_graph_helpers.py` into
`financial_surface_contracts.py` as public five plus owner-private segment-
surface assembly. Its 17 calls finish external 15/local two. Source is
`+162/-158`, tests are `+781/-7`, and the whole commit is `+943/-165`. Graph
helpers moved from 6,191 to 6,056 physical lines, reconciliation from 1,467 to
1,466, surface contracts from 69 to 209, and six new methods moved discovery
from 1,887 to 1,893. Final gates passed focused 6/6, owner modules 41/41,
affected semantic 851/851, import 19/19, audit 218, full 1,893/1,893,
pycompile/fresh import, DAG/body/full-caller parity, retired-ref zero, and diff
check. The source diff SHA-256 is
`cdd2ced140b9add6bd549e839514038dacede28700ebd25854b7fb6c3e9e1702`.
Candidate/evidence construction/adoption, direct/ratio acceptance, broad
scoring/reconciliation, mutable state/evidence, callback, carrier,
trace/artifact/ledger work, and final sequencing remain hard stops.

The completed `a904f28` follow-on moved exact 12/26/38/40-line candidate local-
aggregate-context, consolidation-scope, binding-policy-shape, and selected-unit-
family definitions from `financial_graph_helpers.py` into
`financial_surface_contracts.py` as public four. Their eight direct calls remain
graph-external 3/2/2/1 and owner-local zero. Source is `+139/-134`, tests are
`+1,116/-9`, and the whole commit is `+1,255/-143`. Graph helpers moved from
6,056 to 5,936 physical lines and surface contracts from 209 to 334. Final gates
passed focused 6/6, owner 47/47, affected semantic 857/857, import 19/19, audit
218, full 1,899/1,899, pycompile/fresh import, DAG/body/full-caller parity over
121 retained graph functions, retired-ref zero, and diff check. The source diff
SHA-256 is
`0e62e924b473c256d505164160b8e00419a8be0c022c7b3d036da0465bafcae7`.
Direct/ratio acceptance, broad scoring/reconciliation, candidate/evidence
construction/adoption, mutable state/evidence, callback, carrier,
trace/artifact/ledger work, and final sequencing remain hard stops.

The completed `d1305f8` follow-on moved the exact 7/15-line segment-local/
segment-metric pair from graph helpers to public row-surface ownership. Calls
are external 2/local 1 and the existing graph-to-row and row-to-surface edges
remain acyclic. Source is `+31/-29`, tests `+606/-7`, and the whole commit
`+637/-36`; graph helpers moved from 5,936 to 5,912 lines and row surfaces from
312 to 338. Focused 4/4, owner 51/51, semantic 861/861, import 19/19, audit 218,
full 1,903/1,903, pycompile/fresh import, body/retained/caller/DAG parity, and
retired-ref zero passed. The source diff SHA-256 is
`6e02e16ff3f7ee300c880b74ae8a413eae7cc343ed86e4a0a8165d5f8942278d`.

The completed `80a37f8` follow-on moved only the exact 10/2-line aggregate-like
row stage/role pair to public `financial_row_surfaces.py` ownership. The 16/18-
line candidate value-role/stage pair remains graph-owned with its 11 calls each
across priority, direct grounding, direct/ratio acceptance, operand matching,
direct strength, and broad scoring. Calls finish external five/local one on the
existing graph-to-row and structured-to-row DAG. Source is `+27/-22`, tests
`+584/-5`, and the whole commit `+611/-27`; graph helpers moved from 5,912 to
5,898 lines and row surfaces from 338 to 357. Focused 4/4, owner 55/55, semantic
865/865, import 19/19, audit 218, full 1,907/1,907, pycompile/fresh import,
body/retained/caller/DAG parity, and retired-ref zero passed. The source diff
SHA-256 is
`075e776a65b50061c7751b2340b7eb256ad8d8f0cfbc85887a3f42867f2ae55a`.

The completed `2eec794` follow-on moved the exact 5/14/7/5-line lookup-hint
projection/match group from graph helpers to four public functions in
`financial_operand_resolution.py`. Its 17 calls finish graph-external 16/owner-
local one. Source is `+60/-57`, tests `+1,673/-20`, and the whole commit
`+1,733/-77`; graph helpers moved from 5,898 to 5,861 lines and operand
resolution from 3,603 to 3,643. Focused 4/4, owner 127/127, affected semantic
938/938, import 19/19, audit 218, full 1,911/1,911, pycompile/fresh import/public
identity, body/retained/caller/DAG parity, retired-ref zero, and diff check
passed. The source diff SHA-256 is
`262d0304e03d9574acd45cb97e1c8b4ec4c32164f766a60c057c7bb526cc8416`.
Lookup task construction, candidate admission/scoring, retry assembly, state/
evidence, artifacts/ledger, and final sequencing remain hard stops.

The completed `8cdcc94` follow-on moved the exact 26/22-line direct logical/
family candidate-signature pair from graph helpers to public
`candidate_direct_logical_signature(...)` and
`candidate_direct_family_signature(...)` in the operand owner. Calls finish
graph-external two/local zero and the seven block-signature calls finish external
four/local three. Source is `+56/-55`, tests `+1,428/-10`, and the whole commit
`+1,484/-65`; graph helpers moved from 5,861 to 5,810 lines and operand
resolution from 3,643 to 3,695. Focused 4/4, owner 131/131, affected semantic
942/942, import 19/19, audit 218, full 1,915/1,915, pycompile/fresh import/public
identity, body/retained/caller/DAG parity, retired-ref zero, and diff check
passed. The source diff SHA-256 is
`d22527be5fbcc25f8ab381134312fcb030f74d52c2e9c6b9a682060f0cbed68e`.
Selected-cell construction, direct acceptance, collapse, sibling/canonical/
semantic/score policy, state/evidence, artifacts/ledger, and final sequencing
remain hard stops.

The completed `a530033` follow-on moved the exact current 30-line sibling-
surface hit-count projection from graph helpers to public
`candidate_sibling_surface_hit_count(...)` in `financial_row_surfaces.py`. Its
three direct calls remain graph-external/local 3/0 in sorted-key, top-hit, and
positive-top filter positions. Source is `+36/-36`, tests `+968/-9`, and the
whole commit `+1,004/-45`; graph helpers moved from 5,810 to 5,778 lines and row
surfaces from 357 to 389. Focused 4/4, owner 67/67, affected semantic 946/946,
import 19/19, audit 218, full 1,919/1,919, pycompile/fresh import/public identity,
body/retained/caller/DAG parity, retired-ref zero, and diff check passed. The
source diff SHA-256 is
`0c369d873a91d678a19d9a766a41152afaa8c97aca83cd7270ca2d81ea9d7466`.
Sibling-list preparation, sorted/top/filter ranking, canonical/semantic/score
policy, candidate/evidence adoption, state/evidence, artifacts/ledger, and final
sequencing remain hard stops.

The completed `8e4dca4` follow-on moved the exact current 6/14-line query-to-
metric/operand match pair from graph helpers to public
`query_mentions_metric(...)` and `query_component_match_count(...)` in
`financial_retrieval_hints.py`. Their four direct calls finish graph-external/
local 4/0 inside `_build_semantic_numeric_plan(...)`. Source is `+30/-28`, tests
`+1,321/-8`, and the whole commit `+1,351/-36`; graph helpers moved from 5,778
to 5,756 lines and retrieval hints from 294 to 318. Focused 4/4, owner 75/75,
affected semantic 955/955, import 19/19, audit 218, full 1,923/1,923,
pycompile/fresh import/public identity, body/retained/caller/DAG parity,
retired-ref zero, and diff check passed. The source diff SHA-256 is
`5199849efa1388dfdd30178ba0bbe14f198e3c46f4e365647cc031070cab0fbd`.
Ontology lookup, operation/formula policy, metric admission, task/query
construction, and plan/state adoption remain hard stops.

The completed `55bc286` follow-on moved the exact current 11/25-line query/task
period-focus pair from graph helpers to public `query_period_focus(...)` and
`task_period_focus_from_operands(...)` in `financial_scope_policies.py`. Their
six direct calls finish graph-external/local 6/0 across hybrid, concept,
heuristic, and metric-task constraint builders. Source is `+48/-46`, tests
`+1,238/-18`, and the whole commit `+1,286/-64`; graph helpers moved from 5,756
to 5,718 lines and scope policy from 457 to 497. Focused 4/4, owner 74/74,
affected semantic 1,034/1,034, import 19/19, audit 218, full 1,927/1,927,
pycompile/fresh import/public identity, body/retained/caller/DAG parity,
retired executable private refs zero, and diff check passed. The source diff
SHA-256 is
`aa560ff1fd01dca72fe55120b8dc8fbd67e95d27d6f3ebc87e863012a7054da9`.
Consolidation/default resolution, operation inference, operand/task/query
construction, caller policy, candidate ranking/admission, and plan/state
adoption remain hard stops.

The completed `9092f5e` follow-on moved the exact current 16/18-line candidate
value-role/aggregation-stage pair from graph helpers to public
`candidate_value_role(...)` and `candidate_aggregation_stage(...)` in
`financial_row_surfaces.py`. Their 22 direct calls finish graph-external/local
22/0 across semantic priority, direct grounding/acceptance, ratio acceptance,
matching, direct strength, and scoring. Source is `+59/-57`, tests `+1,167/-69`,
and the whole commit `+1,226/-126`; graph helpers moved from 5,718 to 5,682
lines and row surfaces from 389 to 427. Focused 4/4, owner 78/78, affected
semantic 1,038/1,038, import 19/19, audit 218, full 1,931/1,931,
pycompile/fresh import/public identity, body/retained/caller/DAG parity, retired
executable private refs zero, and diff check passed. The source diff SHA-256 is
`5bde3c6eb94508a4afab190cd3db4d866b265ff6f0103a028711e41c2159d8b8`.
Direct/ratio acceptance, matching, match strength, semantic priority, scoring/
ranking, candidate/evidence adoption, and graph/artifact/ledger state remain
hard stops.

The completed `78e3508` follow-on moved the exact current 15/19-line candidate
operand-context/structured-sibling pair from graph helpers to public
`candidate_has_operand_context_surface(...)` and
`table_row_has_matching_structured_sibling(...)` in
`financial_row_surfaces.py`. Their two direct calls finish graph-external/local
2/0 in direct-match strength and direct grounding. Source is `+49/-41`, tests
`+986/-17`, and the whole commit `+1,035/-58`; graph helpers moved from 5,682
to 5,646 lines and row surfaces from 427 to 471. Focused 4/4, owner 82/82,
affected semantic 1,042/1,042, import 19/19, audit 218, full 1,935/1,935,
pycompile/fresh import/public identity, body/retained/caller/DAG parity, retired
executable private refs zero, and diff check passed. The source diff SHA-256 is
`228c458d7909609f45806214d1d0dcb4f0a0969648582552ba03b93d1e0b1966`.
Direct grounding/acceptance, matching, match strength, scoring/ranking,
candidate/evidence adoption, and graph/artifact/ledger state remain hard stops.

The completed `0bfa1f0` follow-on moved the exact current 21-line candidate
selected-cell projection from graph helpers to public
`candidate_selected_cell_for_operand(...)` in
`financial_structured_cells.py`. Its sole direct call finishes graph-external/
local 1/0 in deterministic reconciliation, and the seven direct selector calls
finish external/local 6/1. Source is `+30/-26`, tests `+1,266/-27`, and the
whole commit `+1,296/-53`; graph helpers moved from 5,646 to 5,623 lines and
structured cells from 335 to 362. Focused 4/4, owner 86/86, affected semantic
1,046/1,046, import 19/19, audit 218, full 1,939/1,939, pycompile/fresh import/
public identity, body/retained/caller/DAG parity, retired executable private
refs zero, and diff check passed. The source diff SHA-256 is
`eba52c11252de00d12fa808276b8c7b80b7d8dccbd7bbb828696fe5b2c37494f`.
Direct acceptance, signatures, matching/scoring, candidate/evidence adoption,
retry assembly, and graph/artifact/ledger state remain hard stops.

The completed `2b0e9c1` follow-on moved the exact former 56-line scoped
surface-affinity projection from graph helpers to public
`scoped_surface_affinity_priority(...)` in
`financial_surface_contracts.py`. Its two direct `AugAssign` calls finish
owner-external/local 2/0 in evidence prioritization and coherent ratio-context
scoring; the selected segment-label dependency is owner-local and the full
agent-module DAG is unchanged. Source is `+67/-64`, tests `+851/-15`, and the
whole commit `+918/-79`; graph helpers moved from 5,623 to 5,564 lines and
surface contracts from 334 to 396. Focused 4/4, owner 90/90, affected semantic
1,050/1,050, import 19/19, audit 218, full 1,943/1,943, pycompile/fresh import/
public identity, body/retained/caller/DAG parity, retired executable private
refs zero, and diff check passed. The source diff SHA-256 is
`a9d2c5aad44530e9cbcc9d6c27e9644109251adfcc3f17ae705c6936f2015377`.
Eligibility/schema scoring, evidence/operand-row construction, direct/ratio
acceptance, broader ranking, result adoption, and graph/artifact/ledger state
remain hard stops.

The completed `7ec0cc3` follow-on moved the exact former 30-line candidate
period/table coherence projection from graph helpers to public
`candidate_period_table_coherence_bonus(...)` in
`financial_scope_policies.py`. Its sole direct `AugAssign` call remains owner-
external/local 1/0 in `_score_operand_candidate(...)`; explicit-year calls
finish external/local 0/5 and target-year calls 8/6. Source is `+34/-34`, tests
`+788/-30`, and the whole commit `+822/-64`; graph helpers moved from 5,564 to
5,532 lines and scope policy from 497 to 529. Focused 4/4, owner 94/94,
affected semantic 1,054/1,054, import 19/19, audit 218, full 1,947/1,947,
pycompile/fresh import/public identity, body/retained/caller/full 48-module DAG
parity, retired executable private refs zero, and diff check passed. The source
diff SHA-256 is
`33d6fdd3e6216ab2e963fe6480484d7d7b59ee5d333c58b678479d0ed90c139d`.
Candidate/year extraction, target-year policy, source/report/other scoring,
matching/admission/acceptance, broader ranking/adoption, retrieval, and graph/
artifact/ledger state remain hard stops.

The completed `23f08b2` follow-on moved the exact former 53-line candidate
location/entity subject-score projection from graph helpers to public
`candidate_location_entity_subject_score(...)` in
`financial_operand_resolution.py`. Its sole direct `AugAssign` remains owner-
external/local 1/0 in `_score_operand_candidate(...)`, after numeric-signal and
before descriptor/statement/scope/period/source/table work. Source is `+57/-56`,
tests `+890/-23`, and the whole commit `+947/-79`; graph helpers moved from
5,532 to 5,478 lines and operand resolution from 3,695 to 3,750. Focused 4/4,
owner 98/98, affected semantic 1,058/1,058, import 19/19, audit 218, full
1,951/1,951, pycompile/fresh import/public identity, body/retained/caller/full
48-module DAG parity, retired executable private refs zero, and diff check
passed. The source diff SHA-256 is
`4d1144206071e440dbb5815904ab2f30cc5d955c8938fb767ea3673a6e31f105`.
Operand policy, candidate construction, other scoring, matching/acceptance/
ranking, adoption, retrieval, and graph/artifact/ledger state remain hard stops.

The completed `e04a7bf` follow-on moved the exact former 7-line delta-like row-
label classifier from graph helpers to public `is_delta_like_row_label(...)` in
`financial_row_surfaces.py`. Its three direct calls finish owner-external/local
3/0 across direct grounding and operand scoring. Source is `+14/-12`, tests
`+811/-25`, and the whole commit `+825/-37`; graph helpers moved from 5,478 to
5,470 lines and row surfaces from 471 to 481. Focused 4/4, owner 102/102,
affected semantic 1,062/1,062, import 19/19, audit 218, full 1,955/1,955,
pycompile/fresh import/public identity, body/retained/all three callers/full
48-module DAG parity, retired executable private refs zero, and diff check
passed. The source diff SHA-256 is
`b3ceafde06df105a8d62b77dae1e8d6f61711ed04e2132e9f90213012d4c7e0c`.
Period policy, candidate construction, broader scoring, matching/acceptance/
ranking, adoption, retrieval, and graph/artifact/ledger state remain hard stops.

The completed `c4558b7` follow-on moved the exact former 7-line preference-bonus
definition from graph helpers to public `preference_bonus(...)` in
`financial_operand_resolution.py`. Its two direct scorer calls finish owner-
external/local 2/0 as consecutive `AugAssign` expressions. Exact eager
preference iteration, repeated normalization, target truth/membership/index,
first-equal position, raw base multiplication, identities, immutability, and
exception stops remain pinned by four CURRENT-SOURCE methods. Source is
`+12/-11`, tests `+734/-21`, and the whole commit `+746/-32`; graph helpers
moved from 5,470 to 5,462 lines and operand resolution from 3,750 to 3,759.
Focused 4/4, owner 106/106, affected semantic 1,066/1,066, import 19/19, audit
218, full 1,959/1,959, pycompile/fresh import/public identity, body/retained/
caller/full 48-module DAG parity, retired executable private refs zero, and
diff check passed. The source diff SHA-256 is
`319be70af91d64a48d09ec63a1524fe3f5b4834b32238a32a1f1e967e1ec69e5`.
Caller collection construction, role/stage derivation, other scoring, matching/
acceptance/ranking, adoption, retrieval, and graph/artifact/ledger state remain
hard stops.

The completed `0dc278e` follow-on moved the exact former 10-line column-
candidate-label definition from graph helpers to public
`column_candidate_label(...)` in `financial_row_surfaces.py`. Its sole direct
call finishes owner-external/local 1/0 in the table-column reconciliation
candidate builder. Exact eager header iteration, repeated normalization, blank
stop, direct generic-container membership, last non-generic/all-generic
fallback, target-only year regex, identities, immutability, and exception stops
remain pinned by four CURRENT-SOURCE methods. Source is `+14/-14`, graph-helper
tests are `+688/-22`, the baseline is `+3/-3`, and the whole commit is
`+705/-39`; graph helpers moved from 5,462 to 5,450 lines and row surfaces from
481 to 493. Focused 4/4, owner 110/110, affected semantic 1,070/1,070, import
19/19, audit 218, full 1,963/1,963, pycompile/fresh import/public identity,
body/retained/caller/full 48-module/203-edge DAG parity, retired executable
private refs zero, and diff check passed. The source diff SHA-256 is
`053f3195dce934a7d005e8d61b57355c2639b215834eb29f741ed6592d86a9f7`.
The audit corrected the characterization's stale line-derived zero-hit claim:
the unchanged year regex is one reviewed record, and only that record's owner
path, path-derived fingerprint, and line moved while the 218-record total stayed
fixed. Row/cell preparation, grouping/candidate construction, scoring/
acceptance, adoption, retrieval, and graph/artifact/ledger state remain hard
stops.

The completed `471f6a5` follow-on moved the exact former 8-line single-report-
scope predicate from graph helpers to public `has_single_report_scope(...)` in
`financial_scope_policies.py`. Its sole direct call finishes owner-external/
local 1/0 in `align_scope_hints(...)`. Exact raw input truth, one shallow copy,
explicit receipt precedence, source-receipt cardinality, narrow `Exception`
boundary, identities, immutability, and caller gate/order/adoption/stops remain
pinned by four CURRENT-SOURCE methods. Source is `+12/-12`, tests `+620/-29`,
and the whole commit `+632/-41`; graph helpers moved from 5,450 to 5,440 lines
and scope policies from 529 to 539. Focused 4/4, owner 114/114, affected
semantic 1,074/1,074, import 19/19, audit 218, full 1,967/1,967,
pycompile/fresh import/public identity, body/retained/caller/full
48-module/203-edge DAG parity, retired private refs zero, and diff check passed.
The source diff SHA-256 is
`2deab9c118170b25431f43717bd2dc0328798416cbd3da18cc29891b7ab369cf`.
Company/year alignment, report inventory/selection, candidate/evidence work,
report-file I/O, retrieval, and graph/artifact/ledger state remain hard stops.

The completed `4c8c89c` follow-on classified the exact inline candidate
concept-conflict marker as declarative
`CANDIDATE_CONCEPT_CONFLICT_EXCLUSIVE_MARKER` in retrieval policy and moved the
former 27-line graph helper to public
`candidate_conflicts_with_operand_concept(...)` in
`financial_surface_contracts.py`. All three calls remain positional exact
`candidate, operand`, owner-external/local 3/0, at caller `try` depth zero and
immediate `If` parents. Marker precedence, ordered authoritative surfaces,
negative/positive/text fallback, shallow-copy identity, uncaught failures, and
caller returns/stops remain pinned by four CURRENT-SOURCE methods. Source is
`+36/-32`; tests plus fixture are `+1,004/-118`; the whole commit is
`+1,040/-150`. Graph helpers move from 5,440 to 5,412 lines and surface
contracts from 396 to 426. Focused 4/4, owner 118/118, affected semantic
1,078/1,078, import 19/19, audit 217, full 1,971/1,971, pycompile/fresh
identity, policy-normalized body, retained-function/caller/full DAG parity,
retired private refs zero, and diff check passed. The removed inline marker was
one grouped reviewed record, so the exact baseline correctly moves from 218 to
217 rather than retaining a synthetic runtime literal. Benchmark refresh and
remote CI were **NOT RUN**.

The completed `c837e31` follow-on moved the exact former 17-line contextual-
aggregate-preference predicate from graph helpers to public
`operand_prefers_contextual_aggregate_match(...)` in
`financial_surface_contracts.py`. Its three calls finish owner-external/local
3/0 in source priority, candidate matching, and direct strength. Exact binding-
policy copy, role/stage list materialization and membership, positive-contract
laziness, identities, uncaught errors, caller branches, and stops remain pinned
by four CURRENT-SOURCE methods. Production source is `+23/-22`, tests are
`+1,084/-32`, and the whole commit is `+1,107/-54`; graph helpers move from
5,412 to 5,394 lines and surface contracts from 426 to 445. Focused 4/4, owner
122/122, affected semantic 1,082/1,082, import 19/19, audit 217, full
1,975/1,975, pycompile/fresh identity, body/retained/caller/full
48-module/203-edge DAG parity, retired private refs zero, non-ASCII
preservation, and diff check passed. Benchmark refresh and remote CI were
**NOT RUN**.

The completed `f35be1a` follow-on moved the exact former 9-line balance-sheet-
aggregate-operand predicate from graph helpers to public
`is_balance_sheet_aggregate_operand(...)` in
`financial_surface_contracts.py`. Its two calls finish owner-external/local 2/0
in source priority and direct acceptance. Exact operand-needle and policy-set
materialization, whitespace removal, dedupe/blank-discard ordering, native-set
membership, identities, uncaught failures, caller branches, and stops remain
pinned by four CURRENT-SOURCE methods. Production source is `+14/-13`, tests
are `+1,014/-34`, and the whole commit is `+1,028/-47`; graph helpers move from
5,394 to 5,384 lines and surface contracts from 445 to 456. Focused 4/4, owner
126/126, affected semantic 1,086/1,086, import 19/19, audit 217, full
1,979/1,979, pycompile/fresh identity, body/retained/caller/full
48-module/203-edge DAG parity, retired private refs zero, non-ASCII
preservation, and diff check passed. The source diff SHA-256 is
`e9e8b46382ecdb20982d1ec90c19343aec4a8b769d3812272a54da930dd00f51`.
Benchmark refresh and remote CI were **NOT RUN**.

The completed `cefde44` follow-on declared the inline ontology key as retrieval-
policy `CAPEX_TOTAL_CONCEPT_KEY` and moved the exact former 13-line CAPEX-total-
operand predicate from graph helpers to public `is_capex_total_operand(...)` in
`financial_surface_contracts.py`. Its four calls finish owner-external/local
4/0 in source priority, direct acceptance, candidate matching, and direct
strength. Concept short-circuit, operand-needle and policy-set materialization,
native membership, identities, uncaught failures, caller branches, and stops
remain pinned by four CURRENT-SOURCE methods. Production source is `+23/-19`,
tests are `+1,364/-58`, and the whole commit is `+1,387/-77`; graph helpers move
from 5,384 to 5,370 lines, surface contracts from 456 to 473, retrieval policy
from 2,070 to 2,071, and graph-helper tests from 27,336 to 28,642. Focused 4/4,
owner 130/130, affected semantic 1,090/1,090, import 19/19, audit 217, full
1,983/1,983, pycompile/fresh identity, body/retained/caller/full
48-module/203-edge DAG parity, retired private refs zero, non-ASCII
preservation, and diff check passed. The source diff SHA-256 is
`3fcf523be5e9727cbc0b902beb30a899051d288a01459af8799da45071ec02d8`.
Benchmark refresh and remote CI were **NOT RUN**.

The completed `1119ac3` follow-on moved the exact former 23-line note-aggregate
lookup-preference predicate from graph helpers to public
`operand_prefers_note_aggregate_lookup(...)` in
`financial_surface_contracts.py`. Its one call finishes owner-external/local
1/0 in source-priority scoring. Statement/role/stage set materialization,
laziness, identities, uncaught failures, caller branch, and stop remain pinned
by four CURRENT-SOURCE methods. Production source is `+27/-26`, tests are
`+987/-36`, and the whole commit is `+1,014/-62`; graph helpers move from 5,370
to 5,346 lines, surface contracts from 473 to 498, and graph-helper tests from
28,642 to 29,593. Focused 4/4, owner 134/134, affected semantic 1,094/1,094,
import 19/19, audit 217, full 1,987/1,987, pycompile/fresh identity,
body/retained/caller/full 48-module/203-edge DAG parity, retired private refs
zero, non-ASCII preservation, and diff check passed. The source diff SHA-256 is
`0426929d4ef1e09147f9a21dbd661c595fea67a01e38e30f03d81144250e494c`.
Benchmark refresh and remote CI were **NOT RUN**.

The completed `334fff0` follow-on moved the exact former 76-line candidate
source-priority scorer from graph helpers to public
`candidate_source_priority_bonus(...)` in
`financial_operand_resolution.py`. Its one call finishes owner-external/local
1/0 inside the broad graph scorer. Exact four-branch order, declarative-policy
and candidate access laziness, shallow copies, score arithmetic, identities,
failures, and caller stop remain pinned by four CURRENT-SOURCE methods.
Production source is `+85/-80`, tests are `+993/-152`, and the whole commit is
`+1,078/-232`; graph helpers move from 5,346 to 5,268 lines, operand resolution
from 3,759 to 3,842, and graph-helper tests from 29,593 to 30,434. Focused 4/4,
owner 138/138, affected semantic 1,098/1,098, import 19/19, audit 217, full
1,991/1,991, pycompile/fresh identity, body/retained/caller/full
48-module/203-edge DAG parity, retired private refs zero, non-ASCII
preservation, and diff check passed. The source diff SHA-256 is
`83b28fa8e35aae9a69981142c705b38a85c471148683c69f470999acc3f1914e`.
Benchmark refresh and remote CI were **NOT RUN**.

The completed `1a24bc1` follow-on moved the exact former 83-line candidate-to-
operand matcher from graph helpers to public `candidate_matches_operand(...)`
in `financial_operand_resolution.py`. Exact conflict/surface/CAPEX/contextual/
fallback precedence, access and materialization laziness, identities, failures,
and caller stops remain pinned by four CURRENT-SOURCE methods. Production
source is `+96/-90`, tests are `+1,410/-230`, and the whole commit is
`+1,506/-320`; graph helpers move from 5,268 to 5,184 lines, operand resolution
from 3,842 to 3,931, and graph-helper tests from 30,434 to 31,614. Focused 4/4,
owner 142/142, affected semantic 1,102/1,102, reconciliation plan 51/51, import
19/19, audit 217, full 1,995/1,995, pycompile/fresh identity, exact body and
retained-function parity, full 48-module/203-edge DAG parity, retired private
refs zero, non-ASCII preservation, and diff check passed. The source diff
SHA-256 is
`4774eaf925d6dcbc9e0d6da1cc268b889096b4ce9089e13a436bb5fdd41c987a`.
Benchmark refresh and remote CI were **NOT RUN**.

The pre-move docs counted only `_deterministic_reconcile_task(...)`. Live source
inventory found two more executable direct callers in active reconciliation
reranking and the ops ontology-shadow diagnostic. All three were migrated and
the static contract now pins both agent list-comprehension callers and the ops
filter. This corrects characterization coverage; it does not add a runtime path.

The completed `91ceae7` follow-on moved the exact former 122-line direct-match-
strength scorer from graph helpers to public
`candidate_direct_match_strength(...)` in `financial_operand_resolution.py`.
The exact 15-statement/two-return body, weighted surfaces, non-table extension,
exact/variant/half-weight fallback, specialized branch order, materialization,
short circuits, identities, immutability, float scores, and uncaught failures
remain pinned by four CURRENT-SOURCE methods. No graph alias was added.

All eight direct calls across six graph callers now bind the public owner while
their thresholds, additions, tuple use, duplicate evaluation, acceptance,
ranking, and adoption remain graph-owned. Production source is `+135/-138`,
tests are `+1,078/-226`, and the whole commit is `+1,213/-364`; graph helpers
move from 5,184 to 5,055 lines and operand resolution from 3,931 to 4,057.
Focused 4/4, graph owner 146/146, operand owner 69/69, affected semantic
1,106/1,106, reconciliation plan 51/51, import 19/19, audit 217, full
1,999/1,999, pycompile/fresh identity, body/retained/caller/full
48-module/203-edge DAG parity, retired private refs zero, non-ASCII
preservation, and diff check passed. The source diff SHA-256 is
`fb7cf8e1824f26bc4fd54a303602491f79956eb277d999e2fd45872c0e361de3`.
Benchmark refresh and remote CI were **NOT RUN**.

The completed `1be4cad` follow-on moved the exact former 53-line direct-
candidate semantic-priority projection from graph helpers to public
`direct_candidate_semantic_priority(...)` in
`financial_operand_resolution.py`. The exact 19-statement/one-return body,
metadata and binding-policy shallow copies, three eager normalization
comprehensions, helper order, independent ranks, target-year/structured-value
truth projection, tuple order, integer truncation, identities, immutability,
and uncaught failures remain pinned by four CURRENT-SOURCE methods. No graph
alias was added.

All three direct calls in one graph caller now bind the public owner while
sort-key order, top/next recomputation, strict comparison, score fallback,
collapse, and adoption remain graph-owned. Production source is `+60/-58`,
tests are `+1,332/-109`, and the whole commit is `+1,392/-167`; graph helpers
move from 5,055 to 5,001 lines and operand resolution from 4,057 to 4,113.
Focused 4/4, graph owner 150/150, operand owner 69/69, affected semantic
1,110/1,110, reconciliation plan 51/51, import 19/19, audit 217, full
2,003/2,003, pycompile/fresh identity, body/retained/caller/full
48-module/204-edge DAG parity, retired private refs zero, non-ASCII
preservation, and diff check passed. The source diff SHA-256 is
`6fe4cf715b6ea401a379f3ca40725ad7ea25e8b0bae16deb0752433f3937d304`.
Benchmark refresh and remote CI were **NOT RUN**.

The completed `73a049c` follow-on moved the exact former 42-line canonical-
statement-winner predicate from graph helpers to public
`candidate_is_canonical_statement_winner(...)` in
`financial_operand_resolution.py`. The exact 17-statement/seven-return body,
preference-first gate, metadata/policy shallow copies, marker and section
iteration, `< 2.5` strength threshold, target-year/period fallback, identities,
immutability, and uncaught failures remain pinned by four CURRENT-SOURCE
methods. No graph alias was added.

The sole graph call now binds the public owner while direct-entry dictionary
order, `canonical_winner` storage, later rank/collapse, semantic/score fallback,
and adoption remain graph-owned. Production source is `+50/-46`, tests are
`+1,593/-67`, and the whole commit is `+1,643/-113`; graph helpers move from
5,001 to 4,958 lines, operand resolution from 4,113 to 4,160, and graph-helper
tests from 33,689 to 35,215. Focused 4/4, graph owner 154/154, operand owner
69/69, affected semantic 1,114/1,114, reconciliation plan 51/51, import 19/19,
audit 217, full 2,007/2,007, pycompile/fresh identity, body/retained/caller/full
48-module/204-edge DAG parity, retired private refs zero, non-ASCII
preservation, and diff check passed. The source diff SHA-256 is
`f3733afbfbbeaec72deafed6a9cfcde10e2c8b1b88e03ece43c10dcd73c563d6`.
Benchmark refresh and remote CI were **NOT RUN**.

The completed `20feddc` follow-on moved the exact former 68-line ratio-component-
acceptance predicate from graph helpers to public
`candidate_satisfies_ratio_component_acceptance_contract(...)` in
`financial_operand_resolution.py`. The exact 22-statement/twelve-return/no-
`try` body, metadata/report-scope/binding-policy shallow copies, gate order,
lazy direct-row chain, aggregate precedence, positive-term materialization,
selected-cell-aware surface truth, `< 1.0` fallback, eager target-year result,
period truth, identities, immutability, and uncaught failures remain pinned by
four CURRENT-SOURCE methods. No graph alias was added.

All three reconciliation calls now bind the public owner while their first-hit
return, combined-condition `continue`, fallback assignment, same-block fallback,
candidate/cell adoption, evidence work, and state sequencing remain caller-
owned. Production source is `+80/-74`, tests are `+1,325/-99`, and the whole
commit is `+1,405/-173`; graph helpers move from 4,958 to 4,888 lines and operand
resolution from 4,160 to 4,236. Focused 4/4, graph owner 158/158, operand owner
69/69, affected semantic 1,118/1,118, reconciliation plan 51/51, import 19/19,
audit 217, full 2,011/2,011, pycompile/fresh identity, body/retained/caller/full
48-module/204-edge DAG parity, retired private refs zero, non-ASCII preservation,
and diff check passed. The source diff SHA-256 is
`f0e6496c26ea5ed85c50db99057911f149d4654690a833d09ff725125e0e2139`.
Benchmark refresh and remote CI were **NOT RUN**.

The completed `4c422ed` follow-on moved the exact former 86-line direct-
grounding predicate from graph helpers to public
`candidate_is_direct_grounding_candidate(...)` in
`financial_operand_resolution.py`. The exact 30-statement/fifteen-return/no-
`try` body, metadata/binding/report shallow copies, kind/descriptor/numeric/
direct-strength order, `< 1.0` threshold, binding/canonical/consolidation/
period precedence, both delta-label sites, segment/report gates, eager target-
year result, lazy lookup-table-row tail, exact booleans, identities,
immutability, and uncaught failures remain pinned by four CURRENT-SOURCE
methods. No graph alias was added.

All three calls across graph helpers and reconciliation now bind the public
owner at caller `try` depth zero. Direct-acceptance first rejection, ordered
non-lookup filtering and unique/ambiguous fallback, reconciliation first-hit/
ratio fallback/adoption, evidence work, and state sequencing remain caller-
owned. Production source is `+96/-93`, tests are `+1,380/-207`, and the whole
commit is `+1,476/-300`; graph helpers move from 4,888 to 4,800 physical lines
and operand resolution from 4,236 to 4,327. Focused 4/4, graph owner 162/162,
operand owner 69/69, affected semantic 1,122/1,122, reconciliation plan 51/51,
import 19/19, audit 217, full 2,015/2,015, pycompile/fresh identity, body/
retained/caller parity, acyclic 48-module/204-edge DAG parity, retired private
refs zero, non-ASCII preservation, and diff check passed. The source diff
SHA-256 is
`ed765a77a57fa6cb2a8a0e5e81a384074dd69d22e0311ff62a2561a33bc7c66f`.
Benchmark refresh and remote CI were **NOT RUN**.

The completed `6ebcf59` follow-on moved the exact former 161-line direct-
acceptance predicate from graph helpers to public
`candidate_satisfies_direct_acceptance_contract(...)` in operand resolution.
The nineteen-statement/seventeen-return body and sole `TypeError`/`ValueError`
integer-conversion boundary are unchanged; four CURRENT-SOURCE methods pin the
grounding-first gate, selected-cell period/year logic, surface/unit/direct-
strength truth, canonical/balance-sheet/CAPEX filters, exact identities,
immutability, and failures. No graph alias was added.

All five calls across graph reconciliation, nested reconciliation, and period-
pair extraction now bind the public owner while direct-then-ratio laziness,
rejection stops, score/append, fallback/adoption, evidence work, and state
sequencing remain caller-owned. Production source is `+178/-175`, tests are
`+1,631/-258`, and the whole commit is `+1,809/-433`; graph helpers move from
4,800 to 4,634 lines and operand resolution from 4,327 to 4,494. Focused 4/4,
graph owner 166/166, operand owner 69/69, affected semantic 1,126/1,126,
reconciliation plan 51/51, import 19/19, audit 217, full 2,019/2,019,
pycompile/fresh identity, body/retained/caller parity, acyclic 48-module/205-edge
DAG parity, retired private refs zero, non-ASCII preservation, and diff check
passed. The source diff SHA-256 is
`2ed5b13b639fec8480de6594151a6fe63abdc9af776296d33d4e1614a9d51cc6`.
Benchmark refresh and remote CI were **NOT RUN**.

The completed `3d6986e` follow-on moved the exact former 315-line operand-
candidate scorer from graph helpers to public `score_operand_candidate(...)`
in operand resolution. Its 62-statement/two-return/two-`try` body is unchanged
except for the same-owner public helper spelling. The metadata-copy/conflict
gate, complete ordered score pipeline, two narrow `ValueError` boundaries,
repeated calls, exact identities, shallow copies, immutability, and uncaught
failures are pinned by four CURRENT-SOURCE methods. No graph alias was added,
and the adjacent report-file/local-unit I/O helper remained graph-owned.

All seven calls across graph helpers, reconciliation, period-pair projection,
and ontology-shadow diagnostics now bind the public owner while exact inputs,
sorting/key construction, pair selection, fallback/adoption, evidence work, and
exception stops remain caller-owned. Production source is `+338/-356`, tests
are `+1,542/-364`, and the whole commit is `+1,880/-720`; graph helpers move
from 4,634 to 4,294 lines and operand resolution from 4,494 to 4,816. Focused
4/4, graph owner 170/170, operand owner 69/69, affected semantic 1,130/1,130,
reconciliation plan 51/51, import 19/19, audit 217, full 2,023/2,023,
pycompile/fresh identity, body/retained/caller parity, unchanged acyclic
48-module/205-edge DAG parity, retired private refs zero, non-ASCII preservation,
and diff check passed. The source diff SHA-256 is
`2e681d92116eb7b6c213dc505ba61bddbb0aafe65b86eacf917bf4c28d594650`.
Benchmark refresh and remote CI were **NOT RUN**.

The completed `cce5700` follow-on renamed the exact former 3-line private
segment-label helper in its existing surface-contract owner to public
`operand_segment_label(...)`. Its two-statement copy/fallback/normalization body
and all thirteen calls are exact after name normalization; no wrapper or alias
was added. Production source is `+18/-18`, tests are `+925/-63`, and the whole
commit is `+943/-81`; all production physical line counts are unchanged.

Focused pre/post rename 4/4, graph owner 174/174, surface owner 1/1, operand
owner 69/69, affected semantic 1,134/1,134, reconciliation plan 51/51, import
19/19, audit 217, full 2,027/2,027, pycompile, exact production rename parity
5/5, selected-body/public-identity/caller parity, unchanged acyclic 48-module/
205-edge DAG parity, retired private refs zero, non-ASCII preservation, and diff
check passed. The source diff SHA-256 is
`416655cdf1c30a24afa9733cdeece140e43bf66016ad650af6ab8fb79808638e`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `ae964b3` completed that private-API seam. The exact former 4-line helper
is public `financial_surface_contracts.operand_needles(...)`; its three-
statement body is unchanged after definition-name normalization, all twenty-
four calls/nine call modules and nine external bindings use the public name,
and no private alias exists. One pre-existing same-name local list exposed by
the public rename is now `normalized_operand_needles`; a static no-shadow
contract prevents regression.

Production source is `+36/-36`, tests are `+998/-113`, and the whole commit is
`+1,034/-149`; all production physical line counts are unchanged. Focused 4/4,
graph owner 178/178, surface owner 1/1, operand owner 69/69, affected semantic
1,138/1,138, additional caller 17/17, reconciliation plan 51/51, import 19/19,
audit 217, full 2,031/2,031, pycompile, production transform parity 10/10,
selected-body/name-normalized-owner parity, public identity 9/9, all calls,
zero public stores/private refs, unchanged acyclic 48-module/205-edge DAG,
non-ASCII preservation 13/13, and diff check passed. The source diff SHA-256 is
`22b638bd5e610ab14088510908c9c39539f977935589cf1c70a6cdac99a84ef0`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `83cf700` completed the next private-API seam. The exact former 3-line
helper is public `financial_surface_contracts.text_has_negative_surface(...)`;
its two-statement contract-owner/negative-list/term-helper body is unchanged
after definition-name normalization, all ten calls/four call modules and five
external bindings use the public name, and no private alias exists. Graph
calculation and graph helpers retain import-only bindings.

Production source is `+16/-16`, tests are `+990/-27`, and the whole commit is
`+1,006/-43`; all production physical line counts are unchanged. Focused 4/4,
graph owner 182/182, surface owner 1/1, operand owner 69/69, affected semantic
1,142/1,142, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, full 2,035/2,035, pycompile, production transform
parity 6/6, selected-body/name-normalized-owner parity, public identity 5/5,
all calls, zero public stores/private executable refs, unchanged acyclic
48-module/205-edge DAG, non-ASCII preservation 8/8, and diff check passed. The
source diff SHA-256 is
`69d56b303cee0619864af4d3b446b2c344c7f61e035e4f2bea3a54e7a5184991`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `a0c9a84` completed the symmetric positive-surface private-API seam. The
exact former 3-line helper is public
`financial_surface_contracts.text_has_positive_surface(...)`; its two-statement
contract-owner/positive-list/term-helper body is unchanged after definition-
name normalization, all twenty-six calls/seven call modules and six live
external bindings use the public name, and no private alias exists.

Production source is `+33/-33`, tests are `+1,234/-73`, and the whole commit is
`+1,267/-106`; all production physical line counts are unchanged. Focused 4/4,
graph owner 186/186, surface owner 1/1, operand owner 69/69, affected semantic
1,146/1,146, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, full 2,039/2,039, pycompile, production transform
parity 7/7, untouched-test transform parity 2/2, selected-body/name-normalized-
owner parity, public identity 6/6, all calls, zero public stores/private
executable refs, unchanged acyclic 48-module/205-edge DAG, non-ASCII
preservation 10/10, and diff check passed. The source diff SHA-256 is
`fa6ec5508e044215963811971024a2dfe60b375dec46b1435e57a9914163b0cb`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `faf75a0` completed the text contract-term private-API seam. The exact
former 13-line helper is public
`financial_surface_contracts.text_has_contract_term(...)`; its normalization,
empty stop, whitespace compaction, ordered term scan, direct-before-compact
membership, and exact-return body is unchanged after definition-name
normalization. All four calls/two call modules and the live external binding use
the public name, and no private alias exists.

Production source is `+6/-6`, tests are `+964/-46`, and the whole commit is
`+970/-52`; all production physical line counts are unchanged. Focused 4/4,
graph owner 190/190, surface owner 1/1, operand owner 69/69, affected semantic
1,150/1,150, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, full 2,043/2,043, pycompile, production transform
parity 2/2, selected-body/dependent-wrapper parity, public identity 1/1, all
calls, zero public stores/private executable refs, unchanged acyclic 48-module/
205-edge DAG, non-ASCII preservation 3/3, and diff check passed. The source diff
SHA-256 is `cca5735d1b0f269dc5ce7b4e3701c3fb448d6a25c3e655376b5400bea462d7e1`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `5b71fd6` completed that remaining cross-module surface-owner seam. The
exact former 22-line helper is public
`financial_surface_contracts.operand_surface_contract(...)`; its eight-
statement explicit-contract, copied legacy-policy concept lookup, and ordered
operand-needle fallback body is unchanged after definition-name normalization.
All seven calls/two call modules and both external bindings use the public name;
operand resolution is live and graph helpers remains import-only. No wrapper or
alias was added.

Production source is `+10/-10`, tests are `+1,185/-85`, and the whole commit is
`+1,195/-95`, net `+1,100`; production physical lines are unchanged. Focused
4/4, graph owner 194/194, surface owner 1/1, operand owner 69/69, affected
semantic 1,154/1,154, additional retrieval-pipeline 1/1, reconciliation plan
51/51, import 19/19, audit 217, full 2,047/2,047, pycompile, production transform
3/3, selected-body/dependent-wrapper, existing-test AST 190/190 plus four new
methods, public identity 2/2, all-call, unchanged acyclic 48-module/205-edge DAG,
retired-ref/public-store zero, UTF-8/non-ASCII preservation, and diff-check
gates passed. The source diff SHA-256 is
`0e9efc0d6d5f8d131a762c1200b77e470f91e598d2db4d51d08da6dc096a866b`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `ea830ed` completed the generic-column-header private-API seam. The exact
former 2-line helper is public
`financial_row_surfaces.generic_column_headers()`; its one-return policy
projection is unchanged after definition-name normalization. Both row-local
and structured-cell-external calls use the public name and no alias exists.

Production source is `+4/-4`, tests are `+804/-31`, and the whole commit is
`+808/-35`, net `+773`; production physical lines are unchanged. Focused 4/4,
graph owner 198/198, surface owner 1/1, operand owner 69/69, affected semantic
1,158/1,158, additional retrieval-pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, full 2,051/2,051, pycompile, production transform 2/2,
selected-body/two-caller parity, existing-test AST 194/194 plus four new
methods, public identity 1/1, all-call, unchanged acyclic 48-module/205-edge
DAG, retired-ref/public-store zero, UTF-8/non-ASCII preservation 3/3, and diff-
check gates passed. The source diff SHA-256 is
`5b953b411edaf1fd53ac437179eb1a24dac17960398f6df64bfa6d50676cc37c`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `786a356` completed the table-row-label private-API seam. The exact
former 9-line helper is public `financial_row_surfaces.extract_table_row_label(...)`;
its raw normalization, blank stop, delimiter membership/split, falsey
fallthrough, and exact result identities are unchanged after definition-name
normalization. All three external calls/imports use the public name and no alias
exists.

Production source is `+7/-7`, tests are `+1,224/-9`, and the whole commit is
`+1,231/-16`, net `+1,215`; production physical lines are unchanged. Focused
4/4, graph owner 202/202, surface owner 1/1, operand owner 69/69, affected
semantic 1,162/1,162, additional retrieval-pipeline 1/1, reconciliation plan
51/51, import 19/19, audit 217, full 2,055/2,055, pycompile, production transform
4/4, selected-body/three-caller parity, existing-test AST 198/198 plus four new
methods, public identity 3/3, all-call, unchanged acyclic 48-module/205-edge DAG,
retired-ref/public-store zero, UTF-8/non-ASCII preservation 5/5, and diff-check
gates passed. The source diff SHA-256 is
`3406b381e79434e1f1b9550e568be93dff39fefd326dbb29a5dd01fab3804c0c`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `472906e` completed the financial-label-annotation private-API seam. The
exact former 9-line helper is public
`financial_row_surfaces.strip_financial_label_annotations(...)`; its raw truth,
normalization/blank stop, annotation regex, whitespace collapse/strip, and exact
result identities are unchanged after definition-name normalization. All five
calls and both external imports use the public name and no alias exists.

Production source is `+8/-8`, tests are `+1,308/-11`, and the whole commit is
`+1,316/-19`, net `+1,297`; production physical lines are unchanged. Focused
4/4, graph owner 206/206, surface owner 1/1, operand owner 69/69, affected
semantic 1,166/1,166, additional retrieval-pipeline 1/1, reconciliation plan
51/51, import 19/19, audit 217, full 2,059/2,059, pycompile, production transform
3/3, selected-body/three-caller parity, existing graph-test AST 202/202 plus
four new methods, public identity 2/2, all-call, unchanged acyclic 48-module/
205-edge DAG, retired-ref/public-store zero, UTF-8/non-ASCII preservation 4/4,
and diff-check gates passed. The source diff SHA-256 is
`fa6221e4d52b393bc3d6d7103a586bc9b09e55b4d8c2e23c153b7caa8057e5d3`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `98aee5a` completed the leading-period-qualifier private-API seam. The
exact former 14-line helper is public
`financial_row_surfaces.strip_leading_period_qualifiers(...)`; raw truth,
normalization/blank stop, exact regex compilation, one-prefix-at-a-time
`sub(..., count=1)`/strip/equality looping, immediate-stability and adopted-
result identities, immutability, and uncaught failures are unchanged after
definition-name normalization. All four calls and the aggregate-projection
external import use the public name; no alias exists.

Production source is `+6/-6`, tests are `+1,124/-25`, and the whole commit is
`+1,130/-31`, net `+1,099`; production physical lines are unchanged. Focused
4/4, graph owner 210/210, surface owner 1/1, operand owner 69/69, affected
semantic 1,170/1,170, additional retrieval-pipeline 1/1, reconciliation plan
51/51, import 19/19, audit 217, full 2,063/2,063, pycompile, production transform
2/2, selected-body/three-caller parity, existing graph-test AST 206/206 plus
four new methods, existing subtask-loop AST 252/252, public identity 1/1,
all-call, unchanged acyclic 48-module/205-edge DAG, retired-ref/public-store
zero, UTF-8/non-ASCII preservation 4/4, and diff-check gates passed. The
committed source diff SHA-256 is
`5556c032ed6fde19f06863ab5833bb919ae1a90189e8b09c1adfa4f2bb2a5307`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `05415ed` completed the surface-match-variants private-API seam. The
exact former 11-line helper is public
`financial_row_surfaces.surface_match_variants(...)`; raw truth,
normalization/blank list return, exact four-item eager helper-call order,
repeated annotation stripping, truth-filtered ordered dictionary dedupe,
first-representative identity, immutability, and uncaught failures are unchanged
after definition-name normalization. All nine calls and both external imports
use the public name; no alias exists.

Production source is `+12/-12`, tests are `+1,514/-42`, and the whole commit is
`+1,526/-54`, net `+1,472`; production physical lines are unchanged. Focused
4/4, graph owner 214/214, surface owner 1/1, operand owner 69/69, affected
semantic 1,174/1,174, additional retrieval-pipeline 1/1, reconciliation plan
51/51, import 19/19, audit 217, full 2,067/2,067, pycompile, production transform
3/3, selected-body/six-caller parity, existing graph-test AST 210/210 plus four
new methods, public identity 3/3, all-call, unchanged acyclic 48-module/205-edge
DAG, retired-ref/public-store zero, UTF-8/non-ASCII preservation 4/4, and diff-
check gates passed. The committed source diff SHA-256 is
`a49845578a7a70c8479ac01921d75bc30bdd7631799a2ab0498a59511619e7d9`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `6f28f8b` completed the operand-text-match private-API seam. The exact
former 16-line helper is public
`financial_row_surfaces.operand_text_match(...)`; initial variant/blank stop,
per-haystack compact and fresh needle lookup, per-needle fresh variants,
exact/substring/compact short-circuit order, exact bool results, immutability,
and uncaught failures are unchanged after definition-name normalization. All
62 calls and nine external imports use the public name; no alias exists.

Production source is `+72/-72`, tests are `+1,630/-158`, and the whole commit is
`+1,702/-230`, net `+1,472`; production physical lines are unchanged. Focused
4/4, graph owner 218/218, surface owner 1/1, operand owner 69/69, affected
semantic 1,178/1,178, additional retrieval-pipeline 1/1, reconciliation plan
51/51, import 19/19, audit 217, full 2,071/2,071, changed-consumer 246/246,
pycompile, production transform 10/10, full transform 16/16, selected-body/36-
caller parity, existing graph-test AST 214/214 plus four new methods, public
identity 10/10, all-call, unchanged acyclic 48-module/205-edge DAG, retired
production-ref/public-store zero, UTF-8 decode 16/16, non-ASCII preservation
12/12, and diff-check gates passed. The checkpoint's graph-only test inventory
missed 30 live references in five other test modules; the completed batch
migrated them and records the verified 16-file surface. The committed source
diff SHA-256 is
`994ebce19f931072d564b7e12678100b79648799b0c09342b4d5e50c65c80a08`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `7739ab0` completed the numeric-value-after-operand-text private-API
seam. The exact former 16-line helper is public
`financial_row_surfaces.extract_numeric_value_after_operand_text(...)`;
normalization/blank stop, fresh needle lookup, compact and escaped spaced-
pattern construction, search, candidate projection, stable distance sort,
first `[0][1]` result identity, immutability, and uncaught failures are
unchanged after definition-name normalization. All five calls and three
external imports use the public name; no alias exists.

Production source is `+9/-9`, tests are `+1,418/-31`, and the whole commit is
`+1,427/-40`, net `+1,387`; production physical lines are unchanged. Focused
4/4, graph owner 222/222, surface owner 1/1, operand owner 69/69, affected
semantic 1,182/1,182, additional retrieval-pipeline 1/1, reconciliation plan
51/51, import 19/19, audit 217, full 2,075/2,075, pycompile, production
transform 4/4, source/test transform 8/8, selected-body/three-caller parity,
existing graph-test AST 218/218 plus four new methods, public identity 4/4,
all-call, unchanged acyclic 48-module/205-edge DAG, retired live-ref/public-
store zero, UTF-8/non-ASCII preservation 8/8, and diff-check gates passed. The
committed source/test diff SHA-256 is
`0c1e7bbee0516f8afcc9579c0d66837d586a25522b1e9bb05812e3b5b6daa763`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `72eb1b8` completed the structured-candidate-row-text private-API seam.
The exact former 24-line helper is public
`financial_row_surfaces.format_structured_candidate_row_text(...)`; no wrapper
or alias exists. Both graph-helper calls and the sole external import use the
public name. Label/header ordering and dedupe, repeated retained-header
normalization, exact cell-part joins, caller assignment/adoption/stops, and all
uncaught failures are unchanged. Row counts finish 19/7.

Production source is `+4/-4`, tests are `+1,150/-22`, and the whole commit is
`+1,154/-26`, net `+1,128`; production physical lines are unchanged. Focused
4/4, graph owner 226/226, surface owner 1/1, operand owner 69/69, affected
semantic 1,186/1,186, additional retrieval-pipeline 1/1, reconciliation plan
51/51, import 19/19, audit 217, full 2,079/2,079, pycompile, production
transform 2/2, source/test transform 3/3, selected-body/two-caller parity,
existing graph-test AST 222/222 plus four methods, public identity 2/2,
unchanged acyclic 48-module/205-edge DAG, retired live-ref/public-store zero,
UTF-8/non-ASCII preservation 3/3, and diff-check gates passed. Benchmark refresh
and remote CI were **NOT RUN**.

Commit `ac90a62` completed the unstructured-table-row parser private-API seam.
The exact former 47-line helper is public
`financial_row_surfaces.parse_unstructured_table_row_cells(...)`; no wrapper or
alias remains. All seven calls and five external imports use the public name.
Row/header/period fallback order, repeated conversions, numeric filtering,
labeled-value regex/group order, fresh four-key cell construction, caller gates,
adoption, stops, and every uncaught failure are unchanged. Row counts finish
20/6.

Production source is `+13/-13`, tests are `+1,511/-48`, and the whole commit is
`+1,524/-61`, net `+1,463`; production physical lines are unchanged. Focused
4/4, graph owner 230/230, surface owner 1/1, operand owner 69/69, affected
semantic 1,190/1,190, retrieval-pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, full 2,083/2,083, pycompile, production transform 6/6,
source/test transform 10/10, selected-body/six-caller parity, public identity
6/6, all-call/DAG/retired-ref/public-store, UTF-8 10/10, non-ASCII 9/9, and
diff-check gates passed. The committed source/test diff SHA-256 is
`8faf60239bc6d907001d3144dadd2aa5201e7fb6e0c701b4a9c02e09439fef17`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `89227aa` completed the structured-cell period-text private-API seam. The
exact former 35-line helper is public
`financial_structured_cells.structured_cell_period_text(...)`; no wrapper or
alias remains. All four calls and four external imports use the public name.
Policy-copy/marker order, report/query-year precedence, current/prior and fiscal-
rank/header fallback, caller gates, adoption, stops, and every uncaught failure
are unchanged. Structured-cell counts finish 5/3.

Production source is `+9/-9`, tests are `+1,670/-45`, and the whole commit is
`+1,679/-54`, net `+1,625`; production physical lines are unchanged. Focused
4/4, graph owner 234/234, surface owner 1/1, operand owner 69/69, affected
semantic 1,194/1,194, retrieval-pipeline 1/1, reconciliation plan 51/51,
import 19/19, audit 217, full 2,087/2,087, pycompile, production transform 5/5,
source/test transform 9/9, selected-body/four-caller parity, public identity
5/5, all-call/DAG/retired-ref/public-store, UTF-8 9/9, non-ASCII 7/7, and diff-
check gates passed. The committed source/test diff SHA-256 is
`ce057382b96c939e60bd0e2f6d14d1773e0c4cd2f759c7bc8983cc65847ed938`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `f010b6f` completed the ratio-percent-query private-API seam. The exact
former 3-line classifier is public
`financial_operation_policies.is_ratio_percent_query(...)`; no wrapper or alias
remains. All seven calls and four external imports use the public name. Input
identity, normalization, policy-marker lookup, marker-container truth, empty-
tuple fallback, lazy membership, first-truthy stop, caller gates, the sole
depth-one calculation exception boundary, and six depth-zero failure stops are
unchanged. Operation-policy counts finish 1/6.

Production source is `+12/-12`, tests are `+1,446/-12`, and the whole commit is
`+1,458/-24`, net `+1,434`; production physical lines are unchanged. Focused
4/4, graph owner 238/238, surface owner 1/1, operand owner 69/69, affected
semantic 1,198/1,198, reflection capability 24/24, retrieval-pipeline 1/1,
reconciliation plan 51/51, import 19/19, audit 217, full 2,091/2,091,
pycompile, production transform 5/5, complete transform 7/7, selected-body/
seven-caller parity, existing graph-test AST 234/234 plus four methods, public
identity 5/5, unchanged acyclic 48-module/205-edge DAG, retired live-ref/public-
store zero, UTF-8 7/7, non-ASCII 6/6, and diff-check gates passed. The committed
source/test diff SHA-256 is
`53eea332fd2447c3ccde0c16e20ae1ccb5c2a5cb48a82a11f3c64746636d044c`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `1883395` completed the narrative-context-query private-API seam. The
exact former 6-line classifier is public
`financial_operation_policies.query_requests_narrative_context(...)`; no
wrapper or alias remains. All 18 calls and five external imports use the public
name. Input truth/empty-string fallback, conversion/normalization/lowercase,
blank early return, policy-hint lookup/container truth, eager ordered tuple
construction with retained-item double conversion, lazy membership, first-
truthy stop, caller gates/adoption, and all depth-zero failure stops are
unchanged. Operation-policy counts finish 2/5.

Production source is `+24/-24`, tests are `+1,467/-76`, and the whole commit is
`+1,491/-100`, net `+1,391`; production physical lines are unchanged. Focused
4/4, graph owner 242/242, surface owner 1/1, operand owner 69/69, affected
semantic 1,202/1,202, answer-projection 23/23, retrieval-hints 5/5, text-
surface 30/30, reflection capability 24/24, retrieval-pipeline 1/1,
reconciliation plan 51/51, import 19/19, audit 217, full 2,095/2,095,
pycompile, production transform 6/6, complete transform 12/12, selected-body/
18-caller parity, existing graph-test AST 238/238 plus four methods, public
identity 6/6, unchanged acyclic 48-module/205-edge DAG, retired live-ref/public-
store zero, UTF-8 12/12, non-ASCII 9/9, and diff-check gates passed. The
committed source/test diff SHA-256 is
`653a3d7733bb763cb69a1163293a20bbb6171a022c99ceb80d1375260021bcb4`.
Benchmark refresh and remote CI were **NOT RUN**.

Commit `1c8400f` completed the percent-metric-label private-API seam. The exact
former 8-line classifier is public
`financial_operation_policies.label_implies_percent_metric(...)`; no wrapper or
alias remains. All five calls and four external imports use the public name.
Input truth/string/normalization, blank-result gate, configured-marker plus
`"%"`/`"%p"` tuple construction, marker order/identity, lazy membership,
caller gates/adoption, and all depth-zero failure stops are unchanged.
Operation-policy counts finish 3/4.

Production source is `+10/-10`, tests are `+1,196/-28`, and the whole commit is
`+1,206/-38`; production physical lines are unchanged. Focused 4/4, graph owner
246/246, surface owner 1/1, operand owner 69/69, affected semantic
1,206/1,206, reflection promotion 15/15, reflection capability 24/24,
retrieval-pipeline 1/1, reconciliation plan 51/51, import 19/19, audit 217, full
2,099/2,099, pycompile, production transform 5/5, complete transform 8/8,
selected-body/four-caller parity, existing graph-test AST 242/242 plus four
methods, public identity 5/5, unchanged acyclic 48-module/205-edge DAG,
retired-production-ref/public-store zero, UTF-8 8/8, non-ASCII 5/5, and diff-
check gates passed. The committed source/test diff SHA-256 is
`0f772a3b30a68ebfeb08ef66c4ebcef6778d59d0a457040c341927981e421917`.
Benchmark refresh and remote CI were **NOT RUN**.

The new characterize-only inventory selects the exact current 11-line
`financial_operation_policies._is_single_metric_period_comparison(query: str, operand_labels: List[str]) -> bool`
classifier for an in-place public rename to
`is_single_metric_period_comparison(...)`, with no wrapper or alias. Loader
adapters and shared normalization internals remain private. Preserve raw query
identity into normalization, the shallow period-policy snapshot, eager ordered
marker tuple construction with retained-item double conversion, lazy marker
membership/first-truthy stop, and the no-marker return before operand access.

After a marker hit, preserve raw-truth label filtering, original label identity,
stable `dict.fromkeys(...)` hash/equality dedupe, the at-most-one-distinct-label
result, immutability, and every owner-uncaught failure. Three two-positional-
argument external calls in the graph helper and one owner-local call use no
keywords and caller `try` depth zero. Generic operand building, operation-family
inference, concept operand building, and direct-grounding classification retain
their current gates, exact arguments, true/false adoption, and exception stops.
Operand construction, operation precedence, grounding, state, artifacts,
ledgers, and final sequencing do not move.

Existing edges keep the DAG acyclic at 48 modules/205 edges. Projected
operation-policy counts are 3/4 to 4/3. The body SHA-256 is
`0f482ee880c12e58fa61e1f2eebe8f106076206ddb28e5f1b82762678cd92654`;
the private identifier has six production AST references across two source
files and no future public-name definition/store exists. Three live test refs
in one file make the complete rename three files. The 44-54 span intersects no
reviewed baseline record, so all 217 records remain unchanged.

Four required CURRENT-SOURCE methods and projected focused 4/4, graph owner
250/250, surface owner 1/1, operand owner 69/69, affected semantic
1,210/1,210, reflection capability 24/24, retrieval-pipeline 1/1,
reconciliation plan 51/51, import 19/19, audit 217, full 2,103/2,103,
production transform 2/2, complete transform 3/3, public identity 2/2, all four
calls/four callers, unchanged DAG, retired-ref/public-store zero, existing
graph-test AST 246/246 plus four methods, UTF-8 3/3, non-ASCII 2/2, pycompile,
and diff-check gates are defined only in
[project_status.md#next-work](../overview/project_status.md#next-work). No
single-metric-period-comparison source or test rename has occurred; it is the
sole next priority.

The following formatter inventory is the historical checkpoint that preceded
`72eb1b8`; it is not active work. It selected the exact then-current 24-line
`financial_row_surfaces._format_structured_candidate_row_text(label: str, headers: List[str], cells: List[Dict[str, Any]]) -> str`
projection for an in-place public rename to
`format_structured_candidate_row_text(...)`, with no wrapper or alias. The
adjacent 47-line unstructured-table parser remains private and outside this
batch. Preserve four top-level statements, one annotated and three plain
assignments, two loops, two `if` nodes, one return, 19 calls, four list nodes,
one starred item, two generators, five boolean operations, two comprehension
clauses, and no `try`, lambda, or list comprehension.

Preserve the fresh result list; eager `[label, *headers]` expansion; per-part raw
truth/string/normalization; ordered duplicate suppression; per-cell eager
header/value/unit construction; separate filter and retained header
normalization; exact `" / "`, `" "`, and `" | "` joins; truth-gated cell append
without dedupe; input/nested-object immutability; and every uncaught failure.

Its two three-positional-argument call sites finish external/local 2/0 across
two caller definitions in one graph-helper importer, with no keywords and
caller `try` depth zero. Table-value candidates materialize a fresh structured-
cell list before the call and append only after successful assignment. Table-
row candidates assign before caller-owned normalization, seen-set adoption, and
append. The existing edge keeps the full DAG acyclic at 48 modules/205 edges.
Projected row-owner counts are 18/8 to 19/7. The body SHA-256 is
`596e6a345e220615c487d56760d77ff26b1cac1ed5721301c16f7ddf15e0a127`, the
private identifier has four production AST references, and no future public-
name definition/store exists. Two exact test refs in one graph-helper method
make the bounded source/test transform three files.

The selected 304-327 span intersects no reviewed baseline record. All 217
records must remain unchanged. Four required CURRENT-SOURCE methods and
projected focused 4/4, graph owner 226/226, surface owner 1/1, operand owner
69/69, affected semantic 1,186/1,186, additional retrieval-pipeline 1/1,
reconciliation plan 51/51, import 19/19, audit 217, and full 2,079/2,079 gates
are defined only in
[project_status.md#next-work](../overview/project_status.md#next-work). At that
historical checkpoint no source or test rename had occurred; `72eb1b8`
supersedes its projected state and priority.

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
