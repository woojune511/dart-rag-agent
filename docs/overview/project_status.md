# Project Status

Last updated: 2026-09-10

## Current implementation

The product is `FinancialAgent`, on `codex/reviewed-compiler-selection-gate`.
General correctness review baseline: clean `327002c0`.
Audited runtime/source-preservation implementation commit: `7aa4adf2`.
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

Baseline: Python 3.13.13, full unittest **1173/1173** before repairs.
Audit integration was **1236/1236**, including 63 new synthetic regressions.
Source-preservation successor: **1251/1251** in 40.630s, including **15 additional
anonymous regressions**. Focused source/compiler/visibility suites and import/topology
**22/22** pass. Frozen chunk-to-catalog replay preserves all **44,757 numeric records**
(IDs and complete field contents), not merely selected answer values.
Pre-commit recheck: **1251/1251** in 33.867s, focused repairs **78/78**, and
documentation/import/topology **24/24**. No runtime change followed these gates.
Runtime domain audit: **83 reviewed literals**, down from 84 because the obsolete
inline router prompt record was removed; no new baseline exception was added.
Focused parser/retrieval, compiler/executor, storage/API, routing and phase tests pass.
Import/topology, changed/new Python pycompile and diff hygiene passed at handoff.

These are provider-free mechanism tests, not fresh answer accuracy or generalization.
No provider, new benchmark run, fresh ingest, actual-store repair, or evaluator/dataset
change was performed. Paid approval is separate from this implementation.

## Independent holdout preparation

The [holdout protocol](../evaluation/independent_holdout_protocol.md) freezes the audited
runtime bytes and a manual three-company/2025 pilot: 대한항공, KT&G and CJ제일제당,
12 fixed questions. Codex source-reviewed answer drafts and an original-evidence view
are ready. Offline checks verified 15 source values, six calculations, 27 exact quoted
byte spans and both narrative themes. The user approved representative narrative sales
channels with explicit business scope. Per-answer human source confirmation remains
unclaimed (0 confirmed), and the drafts are not yet scored gold.
Model runs, Google/OpenAI calls, embeddings, indexing and store mutations are zero.
Existing reports/datasets and predecessor question/pending-label bytes retain their hashes.
Initial preparation did not change runtime; the subsequently approved source repairs
have a separate successor byte freeze and implementation commit, not a holdout score.
The [final pre-run review](../../benchmarks/results/independent_holdout_preparation_2026-09-10/pre_run_review_v1/README.md)
binds the clean build to those exact runtime bytes. Source/period/scale checks,
six calculations, 27 quotations and seven table-context lines pass; no draft change
was needed. All 12 labels still await adoption and remain unscored/human-unconfirmed.

Subsequent offline whole-report parser/catalog projection preserved **15/15** reviewed
numeric facts with scope/period/unit/physical provenance and all three asset operand
pairs in shared row bundles. **11/12** reviewed prose spans survived; XML recovery
deleted ampersand-adjacent text. Three mixed amount/share rows reached source candidates
but disappeared from the catalog; four channel rows survived as numeric evidence but
their narrative admission is mode-dependent. Anonymous synthetic inputs reproduce
these mechanisms. [Preservation diagnosis](../../benchmarks/results/independent_holdout_preparation_2026-09-10/preservation_probe_v1/README.md).
The mechanisms are now repaired locally; original diagnostic bytes remain unchanged.
Successor runtime: `5a74ff8dae428d314a329615038c45034229098ab15885c45406eb199c809d7b`.
New row readings expand catalog fingerprints, not existing candidate-ID algorithms.
Fresh raw-source verification retains all **15 numeric facts, 12 prose quotations and
seven descriptive row associations**. [Final repair evidence](../../benchmarks/results/independent_holdout_preparation_2026-09-10/preservation_repair_v1/README.md)
uses verification v2, including the full frozen chunk-to-catalog path. This is source
preservation, not actual-question retrieval, compiler selection or answer completeness.

## Latest provider evidence (immutable predecessor)

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

- Keep committed source-preservation successor `7aa4adf2` fixed. Source-exposed cases are diagnostic
  regressions, not untouched parser/catalog generalization evidence; use additional
  uninspected sources for a broader claim. Prior stored text was not repaired.
- Adopt/freeze final labels using the approved narrative criterion before any model
  run. Do not optimize against previous failures or holdout outputs.
- Keep retrieval coverage, runtime correctness and semantic completeness separate.
  New reports are not indexed: compiler-only testing would not establish full-agent
  retrieval quality, and new store preparation needs separate approval.
- Before any paid validation, prepare a fresh current-build manifest and cost/transmission
  scope for separate approval. No automatic retry or fresh ingest.
- Acquisition ambiguity/pagination, complete vector/source text consistency, removal of
  retired narrative helpers, formula-wide rounding propagation, and default-store
  recovery are separate bounded work, not silently included fixes.

See [runtime contract](../architecture/agent_runtime_contract.md),
[code map](codebase_map.md), [checked topology](runtime_flow_roles.md),
and [experiment history](../history/experiment_history.md).
