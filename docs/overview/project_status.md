# Project Status

Last updated: 2026-09-11

## Current implementation

The product is `FinancialAgent`, on `codex/reviewed-compiler-selection-gate`.
General correctness review baseline: clean `327002c0`.
Source-preservation baseline: `7aa4adf2`; period/subject repair: `3d3f64cd`; current successor separates narrative reading/selection.
[Audit findings and residual boundaries](../architecture/general_correctness_audit.md)
replace case-by-case trial-and-error as the current work map.

Implemented generic repairs:

- All intents use required-output planning and the existing source-bundle compiler.
  Pure narrative can no longer bypass requested-theme/evidence coverage.
- Formula inputs require declared dependency authority; targeted assertion retry cannot
  poison accepted outputs. Boolean/non-finite/overflowing literals and invalid scalar
  function arity fail validation; function names may also be legitimate variable names.
- Source filters remain intact across vector failure, BM25 ranking, local supplements,
  seeds and final selection. No all-filtered-results fallback to unrelated reports.
- Filing-qualified narrative identity preserves sources sharing local chunk numbers.
  Table-fragment splitting preserves prose before the first numbered item.
- Fixed absolute-year bonuses/penalties and dated stopword entries are gone; router
  examples are anonymous config. No benchmark/company/answer branches were added.
- Whole calendar/relative/fiscal labels cannot become inferred subjects, including
  abbreviated years. Explicit subjects and names containing temporal text stay intact.
- Initial/retry prompts explicitly limit active outputs and mark evidence as bounded
  excerpts. Narrative instructions preserve local subjects and required themes; missing
  visible evidence is not report-wide absence. No extra model call or validator relaxation.
- Canonical routing validates full finite vector batches before success caching;
  incomplete embedding identity disables cross-instance reuse. Cosine is scale-stable.
- Search-cache Documents/provenance are copied, committed writes invalidate caches,
  and actual persistence errors propagate. Terminal admission failures do not retry
  through context generation, planning, routing, search or evidence fallbacks.
- API failure responses redact raw provider text. Aggregate ledger status follows the
  final public result, including partial/incomplete coverage.
- XML recovery preserves ampersand text, entity controls and quoted attributes;
  explicit header/body tables are data even with one small value. Narrative modes can
  read scalar rows; non-scalar rows retain reading-only evidence. Adding reading rows
  preserves existing chunk numeric extraction and absolute spans. No scalar guessing,
  new role taxonomy, company-specific branch or extra model call was introduced.

Existing public, source-bundle, unit, physical-row, typed-state, strict-readiness,
manifest-last ingest and source-first display contracts remain.
HTTP/`FinancialRunResultV1`, ID/hash algorithms, datasets/evaluator, source stores
and historical result bytes are not changed by this audit.

## Local verification

Python 3.13.13; current full unittest: **1274/1274** in 36.969s.
Twelve new anonymous reading/selection regressions cover local context, format neutrality,
hierarchical diversity, input order, parent ownership and preserved explicit conflicts.
Focused reading/matching/subject/windows: **47/47**; cohort/compiler/validator/executor/
source/integration: **133/133**. Domain audit: **83 reviewed literals**, no new exception; pycompile/diff pass.
The [period/subject predecessor projection](../../benchmarks/results/period_subject_boundary_2026-09-10/v2/README.md)
restored four asset cells' proper owner visibility and retained three accepted cash-flow
IDs without changing catalogs. That receipt remains bound to `3d3f64cd`, not this selection change.
The [reading/selection replay](../../benchmarks/results/narrative_reading_selection_2026-09-11/README.md)
exposes both previously omitted overview passages and a channel-table row in actual
payloads: six mock calls, no retry, unchanged catalogs. Runtime SHA `cb6ebb3a...da7ba`.

These are provider-free mechanism/prompt tests, not fresh answer accuracy or generalization.
These implementation gates used no provider, fresh ingest, actual-store repair or
evaluator/dataset changes. The 12-question pilot below belongs to the earlier runtime.

Latest [reading/selection provider comparison](../../benchmarks/results/narrative_reading_compiler_2026-09-11/RESULTS.md):
clean `ff283a58`, admission `8eae0a6b...65c61`, Pro **7 calls**, one internal retry,
provider/execution errors **0**, estimated **USD 0.221395 / 0.90**; billing unobserved.
Runtime complete **2/3**, Codex source-reviewed semantic complete **1/3**. Both overview
omissions improve; KT&G still broadens subsidiary scope. CJ uses an unrequested section,
omits logistics, and loses channel output after scalar-period rejection. Saved-response
replay matches all three prompt hashes/final program bytes; inputs/criteria remain frozen.

## Independent pilot: immutable compiler-only predecessor

The [holdout protocol](../evaluation/independent_holdout_protocol.md) fixes 12 questions
over 대한항공, KT&G and CJ제일제당 2025. The user accepted unchanged provisional references
after qualified HTML review, not individual human source verification (still 0).
The source-preservation successor retains 15 numeric facts, 12 prose quotes and seven
descriptive row associations; original files and all 44,757 frozen numeric records stay
unchanged. [Repair receipt](../../benchmarks/results/independent_holdout_preparation_2026-09-10/preservation_repair_v1/README.md).

The user then delegated one paid pilot without another confirmation. Admission
`98956685...fd916` ran once on clean `7c7f079a`, unchanged runtime `7aa4adf2` /
`5a74ff8d...9d7b`. [Result and source review](../../benchmarks/results/independent_pilot_compiler_2026-09-10/README.md).
Whole-filing catalogs (51,388 candidates) and question-authored requirements feed current
bounded cohorts. Gold reads are blocked in the runner. Two separate abstention-only SDK
rehearsals are byte-identical; provider budget/usage tests pass 16/16.

- Gemini 2.5 Pro: **21 calls**, **3 internal retries**, 12 questions attempted; transport errors 0.
- Runtime complete **7/12**; exact reference scalars **4/9 numeric questions** (8/21 outputs).
- Codex source review finds all **3 narratives incomplete/unfaithful in at least one respect**.
  This is not a new human or paid-judge score. Same-value summary evidence remains distinct;
  coarser source displays are source-selection/precision differences, not conversion errors.
- Cost estimate **USD 0.90074875 / 2.00**, without cache discount; billing unobserved.
  Compiler loop 1,109.637s includes whole-catalog work, not normal query latency measurement.
- OpenAI/embedding/store/planner/retrieval/judge calls and batch reruns: **0**.

No full-agent, ledger, release or untouched-source generalization claim. This later
period/subject repair does not rewrite that run's results, inputs, labels or source stores.

## Latest full-agent evidence (immutable predecessor)

The [four-question full-agent run](../../benchmarks/results/diagnostic_four_full_agent_2026-09-09/README.md)
used clean `cf721258`, admission `a2bd7bdd...a311`, once.
API/runtime errors were zero and ledgers 4/4 ok; this was not four complete answers.

| Question group | Observed source outcome |
| --- | --- |
| LG context | Consolidated amount answered; requested-period local amount withheld |
| KB context | Bank-specific ratio cells selected |
| NAV narrative | Both requested themes covered |
| Celltrion narrative | Only liquidity theme from management discussion; credit theme and requested note scope missing |

Calls: Flash 10 + Pro 6 + OpenAI 21, retries 0, 177.599s;
usage-estimated USD 0.18370008 / 0.80, billing unobserved.
Offline numeric replay reproduced 2/2 programs/outputs; eight narrative quotes match
frozen source chunks, not proof of semantic completeness. Review `5a691fb5...6ac7`.
The two narrative questions used the old evidence/compression/validation path; its
completed aggregate status cannot establish question coverage. Approval exhausted.

The [KB successor store](../../benchmarks/results/kbf_parser_openai_store_2026-09-09/README.md)
has 2,110 vectors, 1,707 payloads and 51 parents, including 536 newly embedded inputs.
Its recorded publication/readback is strict-ready/non-degraded; all original files
were preserved. Embedding admission `e5aecbba...d567` is exhausted.
Application default `data/chroma_dart` is a different incomplete KB 2022 store with
52 missing payloads. Its manifest alone is not readiness, and it remains untouched.

[Reviewed-case evidence status](../evaluation/reviewed_case_evidence_status.md) is the
index for historical three-case/five-case results, counterfactual runtime tests,
fixture v2 provenance and known catalog incompatibilities. They do not establish a
synchronized current-build full-agent release or unseen-question performance.

## Next work

- Next: provider-free contracts separating document/row reading from scalar measurement
  periods, preserving explicit requested-section/local-subject scope. Reproduce incorrect
  local-heading inheritance with anonymous XML fixtures; do not tune reviewed-source IDs.
- Keep source-exposed regression, full-agent retrieval and semantic completeness distinct;
  ID/scope/number validation is not entailment. New reports are not indexed.
- Paid admissions are consumed. New paid work/store preparation needs scoped authority and
  a current manifest; no automatic rerun, fresh ingest, gold-ID oracle or validator relaxation.
- Acquisition ambiguity/pagination, complete vector/source text consistency, removal of
  retired narrative helpers, formula-wide rounding propagation, and default-store
  recovery are separate bounded work, not silently included fixes.

See [runtime contract](../architecture/agent_runtime_contract.md),
[code map](codebase_map.md), [checked topology](runtime_flow_roles.md),
and [experiment history](../history/experiment_history.md).
