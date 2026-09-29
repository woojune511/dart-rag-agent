# Independent holdout pilot

Last updated: 2026-09-10

## Current state

**One current-build compiler-only pilot completed; further runtime repairs remain.**
The user accepted the review HTML while explicitly noting that they had not read all
original filings. This permits pilot-reference use, not a claim of full-report or
per-answer human source verification. The user's later task-scoped request delegated
one paid compiler pilot without another approval prompt. That run is completed below;
store builds and full-agent evaluation did not run. Independent human gold is not claimed.
This pilot checks the generic repairs in the
[correctness audit](../architecture/general_correctness_audit.md), without selecting
new fixes from repeated attempts on the previous failed questions.

The [local review packet](../../benchmarks/results/independent_holdout_preparation_2026-09-10/source_review_packet.html)
contains 12 fixed questions and full-source previews. The
[answer/evidence review](../../benchmarks/results/independent_holdout_preparation_2026-09-10/gold_review_v1/gold_review_readable.html)
adds Codex-reviewed answer drafts, actual table headers/rows, exact prose quotations,
and source-scope notes. Original XML/ZIP, questions and pending labels remain unchanged;
draft successor labels and hash receipts are ignored artifacts, not runtime data.
The [adoption successor](../../benchmarks/results/independent_holdout_preparation_2026-09-10/label_adoption_v1/README.md)
hash-binds the exact draft, HTML, narrative criterion and pre-run receipt without
changing answer content. Earlier pending/score-ineligible receipts stay immutable;
all 12 now permit provisional pilot comparison, with this review limitation reported.

Offline verification checked 15 numeric source values, six calculated outputs, 27 exact
raw-byte quotation spans, both themes for three narrative questions, and unchanged
runtime/predecessor hashes. This verifies provenance and arithmetic, not human agreement
on narrative completeness or FinancialAgent accuracy. Four-decimal percentage displays
are for review only; no evaluator tolerances were selected or changed.

The user approved this pre-run narrative criterion: explain principal businesses and
source-backed representative sales channels, identifying the company/business scope of
each channel. An exhaustive list of every subsidiary's channels is not required.
Both requested themes need evidence; alternative faithful quotations/summaries are valid,
not only one candidate ID or wording. A parent's/subsidiary's or business-specific channel
must not be generalized to the group. Absence in a selected excerpt cannot establish
absence from the report. The ignored `narrative_scope_decision.v1.json` binds this decision
to the draft-label hash. Questions, label bytes, runtime and evaluator remain unchanged.

## Selection and freeze

- Inventory: 17 local filings and eight dataset metadata files. Their companies already
  occur in development materials; changing their questions alone is not company holdout.
- Three companies were selected before reading their new sources or model responses.
  Exact company identity and the latest final annual filing for 2025 available on the
  selection date determine the source; parser/model outcomes do not select substitutes.
- This is a manual cross-industry pilot, not a random population sample. Company/period
  novelty is relative to the inspected repository materials, not proof of absence from
  every historical experiment or model pretraining. Question families are existing
  supported product shapes, not claimed unseen templates.

| Company | Fiscal year | Primary source |
| --- | --- | --- |
| 대한항공 | 2025 | [DART 20260318001125](https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260318001125) |
| 케이티앤지 (KT&G) | 2025 | [DART 20260318001422](https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260318001422) |
| CJ제일제당 | 2025 | [DART 20260316001116](https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20260316001116) |

The selected Korean spelling of CJ was resolved to its official DART name and company
code, not replaced by another company. Raw originals are retained alongside convenience
HTML previews; recovered XML rendering is not a substitute for checking the original.

`selection_lock.json` SHA-256:
`8337a3276c16af90714464005993120cce79f934e4ecd1b28b6a55ce7c0a0c69`.
Runtime byte snapshot SHA-256:
`183f01da1a231f882fdcdd210622f57628bc0ac9856b84ac3bd170ac1ac89046`.
The snapshot includes tracked and nonignored untracked runtime files over HEAD
`327002c0`; it is **not a clean committed build**. This is the immutable pre-repair
snapshot. The approved source-preservation successor is
`5a74ff8dae428d314a329615038c45034229098ab15885c45406eb199c809d7b`, recorded separately
with the [repair verification](../../benchmarks/results/independent_holdout_preparation_2026-09-10/preservation_repair_v1/README.md).
Original report/dataset hashes and predecessor views remain unchanged.
The successor implementation is now committed at `7aa4adf2`, with identical runtime
bytes. The [pre-run review receipt](../../benchmarks/results/independent_holdout_preparation_2026-09-10/pre_run_review_v1/README.md)
records the final clean checkout commit, not an authorized provider manifest.

## Questions and gold review

Each source has one reported cash-flow lookup, one two-period asset calculation, two
independent financial outputs, and a two-theme narrative question: four questions per
source, 12 total. Questions were written without candidate rankings or model answers.

Before evaluation, review source answerability and every requested output. Record exact
source quotes/locations, table headers, period, scope, sign and units; calculations need
both operands and the formula, while narrative needs evidence for both requested themes.
Alternative faithful evidence is acceptable; do not enforce one candidate ID as gold.
Unresolved labels remain unscored, never silently counted as passes. Report all 12
statuses, including pre-run exclusions and their reasons.

Keep pending labels immutable; publish a reviewed successor before the first model run.
Resolve ambiguous question wording in a versioned successor before that run as well.
Do not change labels, drop cases, relax criteria or add runtime rules after viewing
outputs to improve the measured result. Gold answers must not enter model inputs.

Assess source availability/retrieval coverage, runtime errors/ledger integrity, numeric
correctness and scope/provenance, and semantic/requested-output completeness separately.
After a repair informed by these sources or model outputs, the affected boundary's
cases become development regressions; a further generalization claim needs new
untouched sources, not another score on the same set.

## Offline preservation diagnosis

The actual current parser, canonical prefix and candidate/bundle builders processed
all chunks of all three reports before answer drafts were loaded for comparison.
All **15 numeric source facts** retain units, periods, consolidated scope and physical
provenance; all three two-period asset pairs share row bundles. **11/12 prose spans**
survive, but XML recovery removes ampersand-adjacent text in one reviewed footnote.
Three product-table rows survive in source candidates but disappear from the catalog
when their amount/share cells are not scalar-normalizable. Four channel rows retain
text in numeric bundles; narrative eligibility differs by evidence mode. Anonymous
synthetic inputs reproduce the mechanisms, including valid-entity control cases.

The [diagnosis and preserved receipts](../../benchmarks/results/independent_holdout_preparation_2026-09-10/preservation_probe_v1/README.md)
separate exact span/row coverage from alternative faithful evidence. No narrative or
numeric question is graded by these counts. Retrieval, actual-question cohorts,
planner, compiler, validator and answer assembly were not exercised. That diagnostic
runtime and its artifacts remain immutable; original sources, questions and labels
remain unchanged, and new stores still do not exist.

The approved repair uses generic XML lexical preservation and scalar-independent row
reading evidence. Both narrative modes can read scalar rows; arithmetic remains
numeric-only. Supplementary reading rows cannot switch the original chunk's scalar
extraction or spans. Fifteen anonymous regressions and full unittest **1251/1251** pass.
Replaying the complete frozen chunk-to-catalog path preserves all **44,757** existing
numeric IDs and contents. No company, question ID or gold value controls the runtime.
Fresh whole-report reparse also preserves the 15 reviewed numeric values/IDs, restores
all 12 reviewed prose spans and retains seven descriptive row associations. The final
receipt is verification v2; an earlier local receipt missed a chunk-to-source path
switch and is retained only as diagnostic history. No model output guided these fixes.

## Execution boundary and next step

Original preparation used public DART read-only source acquisition only, without model
calls or store mutation. Its immutable zero-call receipts precede the paid run below.
The final offline review rechecked all 12 drafts against source bytes, row/column and
period headers, consolidated scope, sign/scale and exact arithmetic. Fifteen values,
six calculations, 27 quotations and seven table-context lines pass; Codex found no
required answer correction under the approved representative-channel criterion.
Original draft/criteria/selection bytes remain unchanged. Qualified HTML acceptance
adopts these references for the pilot, not independently source-verified human gold.
The clean implementation recheck passed 1251 tests, 78 focused repairs, 24
documentation/import/topology tests, domain audit, pycompile and diff hygiene.
Per-answer human source verification remains unclaimed. Source-exposed cases are
regressions for repaired boundaries, not an untouched generalization test.

### Completed compiler pilot (2026-09-10)

The [execution and review](../../benchmarks/results/independent_pilot_compiler_2026-09-10/README.md)
bind clean `7c7f079a` and unchanged runtime `7aa4adf2` to manifest SHA
`989566857a7ec8394fc1572fdcbb3f9260226581b11856c2cb28d4029c2fd916`.
The user requested continuation through paid execution without another confirmation.
The agent bounded that delegation to these 12 questions and announced a USD 2.00 cap;
it is not a user-quoted SHA approval or standing authority for later experiments.

Inputs use all three source catalogs, not gold-picked windows: 51,388 candidates before
current per-owner admission. Requirements are authored from the four frozen question
families, not planner outputs. Gold files are blocked in the provider runner. Two
separate socket-blocked SDK rehearsals use abstention-only responses and have identical
receipt bytes; no reviewed answers or golden programs supply those responses.

All 12 questions ran once: Pro 21 calls, including three existing island retries;
transport failures 0, arithmetic execution errors 0, runtime complete **7/12**.
Exact normalized reference comparison matches every output for **4/9 numeric questions**
(8/21 individual outputs). Float arithmetic allowance for percentages is 1e-12, not
the four-decimal review display; labels and evaluator tolerances did not change.
Alternative faithful evidence is allowed. CJ asset numbers match from a different
summary table, with its actual provenance retained. Coarser summary numbers elsewhere
are source-selection/precision differences, not failed arithmetic.

Codex's source review finds **0/3 narratives fully meeting both themes and source scope**:
principal-business omissions, subsidiary-to-group channel generalization, and unsupported
document-wide absence claims remain. Two narrative cases are runtime complete despite
these semantic defects; binding coverage must not be reported as answer quality.
Estimated cost is **USD 0.90074875 / 2.00** without cache discount; billing unobserved.

A frozen factor replay confirms a generic selection defect: `2025년` is inferred as
a local subject, so a correct metric row can lose to unrelated date-matching rows.
Correct values may be globally visible but unauthorized for the direct owner; validator
rejection does not justify weakening owner authority. Future repairs need anonymous
mechanism regressions, not benchmark names, answer corrections or repeated paid tuning.

OpenAI, embeddings, planner/retrieval, indexing, store writes, paid judges and batch
reruns were zero. The three reports remain unindexed. This is not a full-agent, ledger,
release, normal query-latency or untouched-source claim. Inputs/results/references remain
immutable. The one-shot delegation is consumed; new paid work needs fresh scoped
authority and a current-build manifest. No automatic paid retry or store preparation.
