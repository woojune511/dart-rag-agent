# Reviewed Five-Case Evidence Status

Checked 2026-09-08 on clean `6d1f7ee3`; runtime source `5f2e86b1`, Python 3.13.13.
This is a provider-free evidence audit, not a new compiler/full-agent run or release gate.

## Current result

The five saved live answers completed at their respective historical commits.
Current reviewed-fixture contracts pass **5/5**, but exact saved-program replay passes
**3/5**: both KB catalogs are rejected before execution. The exact replay aggregate
is **failed**, not a five-case pass. Quality judges were not measured, and there is
no synchronized five-case full-agent result on this runtime.

| Case | Saved live answer / calculation | Original numeric verdict | Current exact replay / remaining limit |
| --- | --- | --- | --- |
| `KBF_T1_017` | NIM `1.83%`, change `+0.10%p` from `1.73%` | FAIL; count-unit evaluator-only successor PASS | Catalog fingerprint mismatch; no current execution |
| `KBF_T2_018` | `70.28%`; inputs `(3,146,409)` and `(1,847,775)` 백만원 | PASS | Catalog fingerprint mismatch; no current execution |
| `LGE_T1_051` | `2,163,234 - 676,874 = 1,486,360` 백만원 | FAIL; explicit reviewed evaluation v2 PASS | PASS; original verdict/default dataset unchanged |
| `NAV_T2_006` | Source `41.4%`, calculation `41.39574110852439%`, multi-source narrative | null / N/A | PASS; old fixture has a separate unit defect below |
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

### KB exact replay compatibility

Both cases return `catalog_replay_not_verified` / `saved_fingerprint_mismatch`.
Recomputed source/catalog counts are T1 `228/723`, T2 `500/1397`; all five saved
count/ID/content checks differ. The audit does not isolate the underlying cause
and does not remap IDs, replace saved programs, or relax fingerprint checks.
Historical evaluator-only PASS and reviewed-fixture PASS do not fill this gap.

### NAV fixture source-unit defect

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
The original fixture, source filing and previous receipts were not rewritten.

**Next bounded change:** create an explicit unit-correct fixture successor with exact
source-unit anchors and absolute normalized-amount assertions. Keep the old fixture
and receipts as predecessors. Do not change runtime math, answer keys or tolerances.
After that, separate KB compatibility work from expanding to unseen questions;
any new provider execution still needs its own manifest and cost approval.

## Validation receipts

- Existing focused replay, fiscal-period, numeric-boundary and LG evaluation tests:
  **29/29**. No runtime change; no new full-suite or provider claim.
- Two separate audit processes produced byte-identical receipts:
  `e0b826cc1fb7f51367bd2db05f48c4ba5ece9033dc94d6ff2846226de775780a`.
  [Fixture replay](../../benchmarks/results/reviewed_case_evidence_audit_2026-09-08/fixture_replay.json):
  5/5 contract checks, with the source-unit caveat above.
  [Exact saved replay](../../benchmarks/results/reviewed_case_evidence_audit_2026-09-08/exact_saved_replay.json):
  3 passed / 2 rejected, aggregate failed.
- Provider/compiler/retrieval calls and source-store writes: **0**. Frozen admission
  inputs, old result files and four original source-store fingerprints are unchanged.
- Fixture SHA: `2af019ff9d3163038bb8bd190edb88996b229b47ac88700d15d1e6068b77bb33`.
  NAV filing SHA: `234a3df95222e4dbcd55be980bac45431cff091345855747abe611d5db7a4113`.
  Source-check receipt SHA: `66170e2c6854c8722e0793e3f61961e315719641e22d5e121b046a30e5524097`.
