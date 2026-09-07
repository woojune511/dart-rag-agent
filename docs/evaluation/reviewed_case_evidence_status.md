# Reviewed Five-Case Evidence Status

Saved-trace audit: 2026-09-08 on `6d1f7ee3`; fixture revision starts from `3157ab77`.
Runtime source stays `5f2e86b1`, Python 3.13.13. No new provider/full-agent run or release gate.

## Current result

The five saved live answers completed at their respective historical commits.
Corrected v2 reviewed-fixture contracts pass **5/5**, but exact saved-program replay passes
**3/5**: both KB catalogs are rejected before execution. The exact replay aggregate
is **failed**, not a five-case pass. Quality judges were not measured, and there is
no synchronized five-case full-agent result on this runtime.

| Case | Saved live answer / calculation | Original numeric verdict | Current exact replay / remaining limit |
| --- | --- | --- | --- |
| `KBF_T1_017` | NIM `1.83%`, change `+0.10%p` from `1.73%` | FAIL; count-unit evaluator-only successor PASS | Catalog fingerprint mismatch; no current execution |
| `KBF_T2_018` | `70.28%`; inputs `(3,146,409)` and `(1,847,775)` 백만원 | PASS | Catalog fingerprint mismatch; no current execution |
| `LGE_T1_051` | `2,163,234 - 676,874 = 1,486,360` 백만원 | FAIL; explicit reviewed evaluation v2 PASS | PASS; original verdict/default dataset unchanged |
| `NAV_T2_006` | Source `41.4%`, calculation `41.39574110852439%`, multi-source narrative | null / N/A | PASS; fixture-only unit defect corrected in v2 below |
| `CEL_T1_013` | `181,624,107 / 342,736,271 * 100 = 52.99%` | PASS | PASS; consolidated 2023 cells, same physical table |

All five historical runs have runtime completeness, zero runtime errors and ledger
`ok`; this does not establish unmeasured narrative quality or current KB compatibility.
All previous paid approvals are exhausted.

## Inspectable evidence

- [KB saved answers and traces](../../benchmarks/results/reviewed_full_agent_kbf_2026-09-07/kb-2023/results.json).
  [Evaluator-only successor](../../benchmarks/results/kbf_count_unit_boundary_replay_2026-09-07/receipt.json)
  preserves the original T1 FAIL; it is not another agent run.
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
current compiler selection and full-agent success remain unmeasured for these inputs.

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
this bounded coverage check. Current compiler responses and full-agent quality remain unmeasured.

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

### Current KB compiler-only admission: pending approval

[Manifest](../../benchmarks/results/kbf_current_compiler_admission_2026-09-08/manifest.json)
and [local run instructions](../../benchmarks/results/kbf_current_compiler_admission_2026-09-08/README.md)
freeze T1 → T2, Gemini 2.5 Pro, two initial islands/calls, at most four calls including
the existing one retry per failed island. Full current catalogs (723/1,397 candidates)
and saved requirements are frozen; only current bounded payloads reach the model.
Fresh offline witness programs exercise validation/execution without reusing old
program/visibility authority. Witnesses and expected answers are never provider inputs.

Preparation exposed a harness boundary: raw-fixture normalization changes two
non-visible catalog entries per question because raw surfaces omit source-derived unit
context. The ops-only `runtime_projection_v1` input verifies a full-content SHA and copies
the current catalog unchanged. The raw-fixture path and runtime arithmetic are unchanged.
Its fingerprint proves identity, **not financial correctness**. The incidental extraction
of a document-standard identifier in T1 remains a separate prose-number eligibility issue;
it is outside these visible cohorts and was not fixed or suppressed for this experiment.

Provider-free witness rehearsal passes 2/2; tests cover projection preservation, mutation
rejection before compiler invocation and unchanged fixture prompts/outputs. Ops/capture/
budget tests pass 34/34; import/topology/docs 24/24; audit, pycompile and diff checks pass.
Installed SDK preflight confirms the actual schema/config and no witness-marker leakage.
Two initial requests reserve USD **0.30422625** when every fake response consumes its full
conservative bound. This is not estimated actual usage or billing.

Requested cap: **USD 0.40**. The existing SDK guard checks every request's reservation
before dispatch; a retry may be denied if the remaining cap cannot cover it. There is
no in-flight cancellation guarantee. Request/client retries and automatic reruns are
disabled; the runtime's one internal island retry remains allowed. A single-use claim
prevents reusing this admission; heartbeat is 30 seconds. No provider has run.

**Next:** obtain separate approval of the exact manifest SHA, Google transmission and
cost cap, then run once. Any failure preserves artifacts and stops. Exact evidence-set
matching is a regression diagnostic: a different source set requires review, not an
automatic claim of a wrong answer. Narrative wording is not fixed to the offline witness.
Fresh retrieval, unseen questions and full-agent quality remain separate; runtime math,
benchmark answer keys, evaluator tolerances and original stores/results stay unchanged.

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
- Provider/compiler/retrieval calls and source-store writes: **0**. Frozen admission
  inputs, old result files and four original source-store fingerprints are unchanged.
- Fixture SHA: `2af019ff9d3163038bb8bd190edb88996b229b47ac88700d15d1e6068b77bb33`.
  NAV filing SHA: `234a3df95222e4dbcd55be980bac45431cff091345855747abe611d5db7a4113`.
  Source-check receipt SHA: `66170e2c6854c8722e0793e3f61961e315719641e22d5e121b046a30e5524097`.
