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
| Operand resolution and policy | `financial_operand_resolution.py` | State-free candidate resolution, lookup-hint projection/matching, candidate location/entity subject scoring, deterministic positional preference scoring, unit/period coercion, dependency-task KRW consistency, table-metadata/raw-unit repair, growth alignment/period conflict, and ratio sign policy; no graph-state lookup |
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
binding-shape admission, selected-unit-family projection, and deterministic
positional preference scoring are also owner-held.
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

The new characterize-only inventory selects one follow-on: move only the
current exact 9-line `_is_balance_sheet_aggregate_operand(...)` definition to
public `is_balance_sheet_aggregate_operand(...)` in
`financial_surface_contracts.py`. The predicate performs only prepared operand-
needle normalization, whitespace removal, set dedupe/blank discard, and
membership against the existing declarative
`HELPER_RUNTIME_POLICY["balance_sheet_aggregate_labels"]` set. The owner already
contains `_operand_needles(...)` and imports `re`, normalization, and the
policy. Graph reaches it and it does not reach graph. Both calls remain
positional exact `operand`, owner-external/local 2/0, at caller `try` depth zero
and immediate `If` parents. The full 48-module/203-edge DAG remains unchanged;
projected function counts are graph helpers 9/82 and surface contracts 13/7,
and the selected span contains zero of 217 reviewed records.

Moving policy values, operand-needle ownership, source-priority or direct-
acceptance branches, capex/contextual/note predicates, candidate/evidence
construction, broader matching/scoring/ranking/adoption, report-file I/O,
retrieval, or plan/state/artifact/ledger work is rejected. Exact needle-set and
policy-set construction, filter-versus-expression string conversion, native
set membership, both caller gates/stops, four required CURRENT-SOURCE methods,
and projected focused 4/4, owner 126/126, affected semantic 1,086/1,086, import
19/19, audit 217, and full 1,979/1,979 gates are defined only in
[project_status.md#next-work](../overview/project_status.md#next-work). No source
or test movement has occurred for this balance-sheet aggregate projection; it
is the sole next priority and this plan maintains no competing queue.

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
