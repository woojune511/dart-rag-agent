# Reviewed Five-Case Evidence Status

Saved-trace audit: 2026-09-08 on `6d1f7ee3`; fixture revision starts from `3157ab77`.
Saved-run runtime baseline is `5f2e86b1`, Python 3.13.13; newer source-visibility repairs are
`d59986ac` / `9f0e1810`. KB compiler-only admission on `f015faf1` passed 2/2 at that build,
not a new full-agent run or a release gate on the latest source.

## Current result

The five saved live answers completed at their respective historical commits.
Corrected v2 reviewed-fixture contracts pass **5/5**, but exact saved-program replay passes
**3/5**: both KB catalogs are rejected before execution. The exact replay aggregate
is **failed**, not a five-case pass. Quality judges were not measured, and there is
no synchronized five-case full-agent result on this runtime. A separate fresh compiler-only
run over current KB catalogs passes **2/2**, without reusing old program/visibility authority.

| Case | Saved live answer / calculation | Original numeric verdict | Current exact replay / remaining limit |
| --- | --- | --- | --- |
| `KBF_T1_017` | NIM `1.83%`, change `+0.10%p` from `1.73%` | FAIL; count-unit evaluator-only successor PASS | Old catalog replay mismatch; separate current compiler/validator/executor PASS |
| `KBF_T2_018` | `70.28%`; inputs `(3,146,409)` and `(1,847,775)` 백만원 | PASS | Old catalog replay mismatch; separate current compiler/validator/executor PASS |
| `LGE_T1_051` | `2,163,234 - 676,874 = 1,486,360` 백만원 | FAIL; explicit reviewed evaluation v2 PASS | PASS; original verdict/default dataset unchanged |
| `NAV_T2_006` | Source `41.4%`, calculation `41.39574110852439%`, multi-source narrative | null / N/A | PASS; fixture-only unit defect corrected in v2 below |
| `CEL_T1_013` | `181,624,107 / 342,736,271 * 100 = 52.99%` | PASS | PASS; consolidated 2023 cells, same physical table |

All five historical runs have runtime completeness, zero runtime errors and ledger
`ok`; this does not establish unmeasured narrative quality or current full-agent success.
All previous paid approvals are exhausted.

## Inspectable evidence

- [KB saved answers and traces](../../benchmarks/results/reviewed_full_agent_kbf_2026-09-07/kb-2023/results.json).
  [Evaluator-only successor](../../benchmarks/results/kbf_count_unit_boundary_replay_2026-09-07/receipt.json)
  preserves the original T1 FAIL; it is not another agent run.
- [Current KB compiler-only result](../../benchmarks/results/kbf_current_compiler_admission_2026-09-08/RESULT.md)
  and [captured-response replay](../../benchmarks/results/kbf_current_compiler_admission_2026-09-08/post_run_review.json)
  record fresh current-catalog source selection and execution, not old-ID compatibility.
- [LG saved answer and trace](../../benchmarks/results/reviewed_full_agent_lge_nav_v2_candidate_2026-09-07/lge-2023/results.json),
  [NAV saved answer and trace](../../benchmarks/results/reviewed_full_agent_lge_nav_v2_candidate_2026-09-07/nav-2023/results.json).
  [LG source-reviewed evaluation v2](lge_t1_051_calculation_source_review_v2.md) is explicit opt-in,
  not a change to old verdicts or default datasets.
- [Celltrion saved answer and trace](../../benchmarks/results/reviewed_full_agent_celltrion_fiscal_2026-09-08/celltrion-2023/results.json)
  and [post-run review](../../benchmarks/results/reviewed_full_agent_celltrion_fiscal_2026-09-08/post_run_review.json).
- [Combined current audit](../../benchmarks/results/reviewed_case_evidence_audit_2026-09-08/audit_a.json)
  includes every selected candidate's saved source text, raw value/unit, period,
  filing/table/row/cell provenance, and result-file SHA. No selected evidence row is missing.
  Its fixture links join by question ID only: reviewed fixture IDs are not remapped live IDs.

These result files are ignored local artifacts, not newly committed experiment outputs.

## Remaining defects and gaps

### KB exact replay: explained version incompatibility

Both cases still return `catalog_replay_not_verified` / `saved_fingerprint_mismatch`.
The diagnosis on `d200e793` holds the saved retrieval window, graph and payloads fixed
and substitutes eight historical versions of the candidate-owner module, using current
helper dependencies. The original owner (`ba410b99`) reproduces **all five saved
count/ID/content checks for both questions**: T1 `205/653`, T2 `471/1363` source/catalog
candidates. This is a verified owner-level comparison, not a historical full-runtime run.

| Candidate-owner change | KB T1 effect | KB T2 effect |
| --- | --- | --- |
| `6ed51fda`: preserve prose alongside attached tables | +23 narrative and +47 sentence-number candidates; `653 → 723` | +29 narrative and +5 sentence-number candidates; `1363 → 1397` |
| `16d2c403`: qualify physical table identity by filing | 600 table/context IDs change; count unchanged | 1,345 table IDs change; count unchanged |
| `bb8eba2d`: honor annotated row units | 4 unselected `(비중, %)` cells change from 십억원 to `%`; IDs unchanged, content fingerprint changes | No effective-unit/content-fingerprint change |

Prose preservation removes no previous candidate ID. Period fixes also change catalog
metadata, but not these count/ID/catalog-fingerprint fields. The current owner exactly
matches the final diagnostic projection: T1 `228/723`, T2 `500/1397`.

Exact filing/table/row/cell matching finds all four selected numeric cells in the
current catalog. Their raw values, signs, units, normalized amounts, periods, scopes,
headers and source text match the **actual saved selected evidence**, not just the
recreated owner output: T1 `1.83% / 1.73%`, T2 `(3,146,409) / (1,847,775)` 백만원.
Those four IDs changed with filing-qualified identity; the selected narrative keeps
its ID and identical text. None of these comparisons remaps a program or grants visibility.

Thus this specific rejection is expected cross-version incompatibility, not missing
answer evidence or a new arithmetic failure. Keep old receipts as historical evidence;
do not restore old IDs, suppress new prose, or weaken fingerprint validation. Fresh
current compiler selection is verified separately below; current full-agent success remains unmeasured.

[Projection](../../benchmarks/results/kbf_catalog_compatibility_diagnosis_2026-09-08/projection.json),
[per-change attribution](../../benchmarks/results/kbf_catalog_compatibility_diagnosis_2026-09-08/attribution.json)
and [confirmation against saved evidence](../../benchmarks/results/kbf_catalog_compatibility_diagnosis_2026-09-08/confirmation.json)
are ignored artifacts. Confirmation SHA `1a70aff197afec93076eec11854bbe4034324087b623e6eb7823d8f6d7520d71`;
related source-context/identity/replay tests **28/28**. Provider calls, store writes and
program executions: **0**. Original store fingerprint `9312082b...95f4` and saved inputs
are unchanged; the unmodified strict replay still rejects both old catalogs.

### Current KB compiler-input coverage

Provider-free inspection on `7f803aae` regenerates current candidates from the same
saved source windows and requirements, then builds global cohorts, per-island cohorts,
fresh owner visibility and the actual v6 candidate payload. Historical selected IDs
are used only afterward to label exact source-atom comparisons, never as selection
inputs or remapped program authority.

| Case | Reviewed evidence in its intended owner | Current unique numeric / narrative IDs | Candidate payload UTF-8 bytes |
| --- | --- | --- | --- |
| KB T1 | `1.83%` direct and current input; `1.73%` prior input: 3/3 uses | 6 / 2 | 30,345 |
| KB T2 | Both negative provision inputs plus risk-management narrative: 3/3 uses | 6 / 6 | 46,779 |

All **5 distinct reviewed atoms / 6 uses** remain selectable in the correct owner,
present in the candidate dictionary and included in their source bundle. Both questions
have one dependency/coupling island and no pre-call capacity/dependency error. All four
numeric cells are `compatible`; the narrative is `unknown_only` and remains selected.
These are candidate-payload sizes, not full prompts, tokens or cost estimates.

Table values, signs, units, periods and physical provenance match saved evidence.
The narrative bundle is the exact first 1,200 characters of source `20240326000894:493:16`,
including original newlines, not the whitespace-normalized catalog display. The complete
risk-scenario paragraph at `[422, 847)` survives byte-exactly; the 2,666-character source
is not entirely visible. No whole-document or narrative-quality pass is claimed.

Two fresh processes produce identical projections/payloads; related source-bundle,
cohort, capacity and island tests pass **23/23**. [Projection](../../benchmarks/results/kbf_current_cohort_visibility_2026-09-08/visibility.json)
and [confirmation](../../benchmarks/results/kbf_current_cohort_visibility_2026-09-08/confirmation.json)
remain ignored artifacts. Confirmation SHA `abb3f66554c4001b7b31001f122dd0853f7830e2443814252f619f032956d2df`.
Provider/retrieval/validation/execution calls and store writes are **0**; full source-store
fingerprint and frozen input hashes are unchanged. No runtime repair was needed for
this bounded coverage check. Fresh compiler responses are measured separately below;
full-agent quality remains unmeasured on this current source.

### NAV fixture source-unit correction

The unchanged [v1 fixture](../../tests/fixtures/reviewed_runtime_replay_corpus_v1.json)
labels `2,546.6` and `1,801.1` as **억원**, but the
[filing](../../data/reports/NAVER/2023_사업보고서_20240318000844.html) says **십억원**.
Raw file lines 188675 and 188725–188726 locate the adjacent unit table and value cells;
the data headers are `사업부문 / 연결 / 제25기 / 제24기 / 증(감)률 / 매출비중`.
The fixture's absolute amounts are ten times too small. The common scale cancels
in growth arithmetic, so its passing ratio test cannot detect this error.

The latest live NAV trace instead uses precise `2,546,649` and `1,801,079` **백만원**,
with a `41.4%` source display; it does not have this fixture error.
[Source check](../../benchmarks/results/reviewed_case_evidence_audit_2026-09-08/fixture_source_check.json)
records exact unit/header/row surfaces and file hashes. Its recovery-parser XPath
is diagnostic, not a canonical original locator; raw filing lines were also inspected.
The [active v2 fixture](../../tests/fixtures/reviewed_runtime_replay_corpus_v2.json)
corrects those unit/source-text annotations and independently checks absolute amounts:
2023 **2,546,600,000,000원**, 2022 **1,801,100,000,000원**, with direct displays
`2,546.6십억원` and `1,801.1십억원`. Growth remains `41.3913719393704%` / source `41.4%`.
It retains 3,666 exact UTF-8 bytes spanning the adjacent unit and data tables,
source SHA and byte range `[6736389, 6740055)`, plus fragment-local cell/header paths.
The bounded fragment parses strictly without full-document recovery.

V2 retains the v1 schema (data revision only); the original fixture/source/receipts
stay unchanged. Programs, owner visibility, selected IDs, narrative, requested display
units and the other four cases are preserved. Seven test consumers use v2; no production
or frozen admission code changes. Direct values still prioritize the source's unit.
Regression checks cover normalization, direct displays and dependency input amounts.
A self-consistent wrong-unit/wrong-normalization mutation still matches growth but
now fails the independent direct-amount/output checks.

### Current KB compiler-only admission: 2/2 passed, approval exhausted

[Manifest](../../benchmarks/results/kbf_current_compiler_admission_2026-09-08/manifest.json)
SHA `409a8ed269a8d7d5a25e62a040f99338e579d3e920aca8d22c76f924f2f91318`
was approved and executed once on clean `f015faf1`: T1 → T2, Gemini 2.5 Pro,
temperature 0, output/thinking caps 4096/1024, SDK retries 0. Full current catalogs
(723/1,397 candidates) and saved requirements stay frozen; only bounded current
payloads reached the model. Offline witnesses and expected answers were not provider inputs.

- **2/2 passed**, two islands/calls, zero retries and zero validation/execution errors.
  Both actual raw responses ended `STOP` and parsed without error.
- T1 selects the reviewed same-row `1.83% / 1.73%` cells and emits `A - B`:
  direct `1.83%`, calculated positive `0.10%p`.
- T2 retains `(3,146,409) / (1,847,775)` 백만원 as negative normalized inputs;
  the compiler chooses `(abs(A) - abs(B)) / abs(B) * 100`, yielding **70.28%**.
  Its narrative selects the reviewed risk-scenario source `20240326000894:493:16`.
- Wall time **50.292s**, monitored at 30 seconds. Usage: 33,833 prompt, 1,017 output,
  1,955 thinking tokens, with 3,491 cached input tokens. Usage-estimated cost
  **USD 0.068083875**, or **0.07201125** without cache discount, below the **0.40** cap.
  Billing was not observed; these are estimates, not an invoice.
- Socket-blocked replay uses the actual captured responses, not offline witnesses:
  both programs, validation/execution, island outputs and prompt hashes match byte-for-byte.
  Both actual SDK request hashes/bytes/reservations match preflight. Original input and
  full store hashes remain unchanged; no extra provider call or store write occurred.

[Result](../../benchmarks/results/kbf_current_compiler_admission_2026-09-08/result.json)
SHA `9f32ce93223c567809b6a35eb34898e9d7b9b0d3d5d407e3b49d8d68d0c174e9`;
[post-run review](../../benchmarks/results/kbf_current_compiler_admission_2026-09-08/post_run_review.json)
SHA `731dd64078e265939831b492734a6e3ae39761564537cc21ab98b3892f5a32a8`.
The single-use claim is retained and approval is exhausted. Preparation README and
receipts remain historical; the [result note](../../benchmarks/results/kbf_current_compiler_admission_2026-09-08/RESULT.md)
is the completed-run entry point. No automatic rerun is permitted.

Preparation exposed a harness boundary: raw-fixture normalization changes two
non-visible catalog entries per question because raw surfaces omit source-derived unit
context. The ops-only `runtime_projection_v1` input verifies a full-content SHA and copies
the current catalog unchanged. The raw-fixture path and runtime arithmetic are unchanged.
Its fingerprint proves identity, **not financial correctness**. The incidental extraction
of a document-standard identifier in T1 remains a separate prose-number eligibility issue;
it is outside these visible cohorts and was not fixed or suppressed for this experiment.

Preparation's provider-free witness rehearsal passes 2/2; tests cover projection preservation, mutation
rejection before compiler invocation and unchanged fixture prompts/outputs. Ops/capture/
budget tests pass 34/34; import/topology/docs 24/24; audit, pycompile and diff checks pass.
Installed SDK preflight confirms the actual schema/config and no witness-marker leakage.
Two initial requests reserve USD **0.30422625** when every fake response consumes its full
conservative bound. This is not estimated actual usage or billing.

Exact evidence-set matching is a regression diagnostic: a different source set requires
review, not an automatic claim of a wrong answer. Narrative wording is not fixed to the
offline witness. No retrieval, planner, evaluator, embedding or ledger assembly ran.
This closes current KB compiler selection, not fresh full-agent or narrative-quality
acceptance; the old exact replay stays 3/5. Runtime math, benchmark answer keys,
evaluator tolerances and original stores/results are unchanged.

There is no need to repeat this KB compiler gate merely to close old-ID compatibility;
any future provider run needs its own approved manifest and cost cap.

### Eight new source-coverage questions: local repairs verified

The [repair report](../../benchmarks/results/new_question_source_repairs_2026-09-08/REPORT.md)
reprojects the same eight authored questions, manual requirements and source-picked windows.
This is not an unbiased holdout or retrieval/planner/compiler/answer-quality evaluation.

- Numeric owner visibility improves **6/8 → 8/8**: comparison-only parser-footnote
  normalization restores NAV prior revenue and Celltrion revenue to the exact metric tier.
  Source qualifiers, IDs and numeric records remain untouched; no keyword bonus or quota increase.
- Checked body quotes improve **4/6 → 6/6**. Recognized metadata prefixes do not consume
  the body budget. Exact windows are at most 1,200 characters, at most 4,800 body characters
  per source; continuations share the existing candidate/context dictionary, and omitted tails
  are explicit. Bracketed original notes survive; V2 detects window/context drift before execution.
- All eight cases retain IDs/catalog fingerprints and byte-identical numeric records.
  Reversed catalog/bundle/payload/owner projections agree **8/8**; new exact body-span checks **13**.
  Original filings/four stores and the predecessor audit stay hash-identical. Calls/writes **0**.
- The inspected Ultium table still reports a current group amount with a blank standalone cell.
  Group/period/note evidence stays visible, but no standalone amount or model decision is established.
- Focused tests **107/107**, full unittest **1,128/1,128**, audit/import/topology/docs/pycompile/diff pass.
  Final receipt SHA `ac3d4add408432f433e463bed587bac9fee7557ea0565e25991c60ca75da8d17`.

The [predecessor source review](../../benchmarks/results/new_question_source_coverage_2026-09-08/REPORT.md)
remains immutable (`e5d04ca0...c182`). Compiler semantic selection/synthesis is the next boundary.

### Eight-question compiler admission: pending separate approval

[Admission and exact manifest SHA](../../benchmarks/results/new_question_compiler_admission_2026-09-09/README.md)
freeze the eight diagnostic questions in the same order, their audited manual requirements
and complete repaired catalogs. Current cohorts are rebuilt, not imported as authority.
Source-picked windows are favorable inputs, not an unbiased holdout or retrieval/planner evidence.

- Gemini 2.5 Pro, temperature 0, inclusive output cap 4096 / thinking budget 1024,
  SDK retries 0, one runner attempt; 9 initial islands and at most 18 calls including
  the existing one retry per island. Stop after a failed question or admission denial.
- Fresh source-derived offline witnesses pass **8/8 declared contract expectations**.
  Real SDK framing/schema rehearsal makes 10 mocked calls: Ultium's deliberate
  abstention takes its existing internal retry. No provider request was sent.
- Five numeric cases keep exact source-set/value/formula checks. Ultium must leave
  the standalone amount unresolved in these inspected sources; group/prior values
  are not accepted replacements, and blank does not mean zero or filing-wide absence.
- The two narrative-only cases accept different runtime-valid evidence combinations.
  Their **semantic review stays pending** even when contract checks pass. Exact wording
  and one witness ID set are not a correctness oracle; hidden IDs remain rejected.
  Only the ops harness gained this opt-in mode and declared abstention alternatives;
  runtime/validator/evaluator policies, numeric defaults and old artifacts are unchanged.
- [Official standard pricing](https://ai.google.dev/gemini-api/docs/pricing), checked
  2026-09-09: estimated USD **0.2522625**, retry planning **0.995605**, proposed cap **1.50**.
  Full-reservation SDK simulation charges **1.197425** for its 10 fake responses; this
  is not expected usage. Pre-dispatch reservations can stop a later call/retry before
  transmission; there is no in-flight cancellation or invoice guarantee.
- No retrieval, planner, evaluator, embedding, ingest, source-store access or write in
  the admitted run. Thirty-second foreground monitoring, immutable outputs and a
  single-use approval claim remain required. Offline witnesses/reviews are never sent.
- Ops/admission/capture/budget tests **50/50**; audit and import/topology/docs gates pass.
  The previous runtime integration suite remains **1,128/1,128** at the source-repair build;
  this preparation changes only the ops expectation seam, not FinancialAgent behavior.

Only source-picked compiler behavior can be evaluated by this run. It cannot establish
full-agent completeness, ledger integrity, generalization or narrative answer quality.

## Validation receipts

- Fixture/replay, compiler rehearsal/capture/admission, unit and retry tests:
  **51/51**. The new amount test failed against v1 before correction. No new full-suite claim.
  Domain audit passes (84 reviewed literals); docs/import/topology **24/24**.
  Two v2 replay processes pass **5/5**, byte-identical receipt SHA
  `48634f5cb46b2a89ad84eb485ef33a285874e316fa571ca055cd6aba2e230f9f`;
  [current receipt](../../benchmarks/results/reviewed_runtime_replay_corpus_v2_2026-09-08/replay_a.json).
  V2 fixture SHA `dbd8d488f1f08ca4045a9b1873aafbb51b7319fe1aa4df60f572faeb1ef29c75`.
- The earlier two audit processes produced byte-identical receipts:
  `e0b826cc1fb7f51367bd2db05f48c4ba5ece9033dc94d6ff2846226de775780a`.
  [Fixture replay](../../benchmarks/results/reviewed_case_evidence_audit_2026-09-08/fixture_replay.json):
  5/5 v1 contract checks, with the historical source-unit defect above.
  [Exact saved replay](../../benchmarks/results/reviewed_case_evidence_audit_2026-09-08/exact_saved_replay.json):
  3 passed / 2 rejected, aggregate failed.
- For the provider-free fixture/audit receipts above, provider/compiler/retrieval calls
  and source-store writes are **0**. The separate current KB paid admission used two compiler calls. Frozen admission
  inputs, old result files and four original source-store fingerprints are unchanged.
- Fixture SHA: `2af019ff9d3163038bb8bd190edb88996b229b47ac88700d15d1e6068b77bb33`.
  NAV filing SHA: `234a3df95222e4dbcd55be980bac45431cff091345855747abe611d5db7a4113`.
  Source-check receipt SHA: `66170e2c6854c8722e0793e3f61961e315719641e22d5e121b046a30e5524097`.
