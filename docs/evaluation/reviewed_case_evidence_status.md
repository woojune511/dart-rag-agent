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

### KB exact replay compatibility

Both cases return `catalog_replay_not_verified` / `saved_fingerprint_mismatch`.
Recomputed source/catalog counts are T1 `228/723`, T2 `500/1397`; all five saved
count/ID/content checks differ. The audit does not isolate the underlying cause
and does not remap IDs, replace saved programs, or relax fingerprint checks.
Historical evaluator-only PASS and reviewed-fixture PASS do not fill this gap.

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

**Next bounded work:** isolate KB's saved/current catalog differences before deciding
whether a compatibility fix is needed. Expanding to unseen questions is separate;
any provider execution needs its own manifest and cost approval. Runtime math,
benchmark answer keys and tolerances were not changed by the fixture correction.

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
