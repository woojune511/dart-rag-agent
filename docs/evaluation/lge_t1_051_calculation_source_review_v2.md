# LG Calculation Source Review v2

Reviewed: 2026-09-08. Scope: evaluator contract, not answer generation.

## Decision and immutable boundary

`LGE_T1_051` can use either precise consolidated-note inputs or precise summary
profit plus note AMPC. Both compute **2,163,234 − 676,874 = 1,486,360백만원**.
The separately declared rounded management-discussion variant is retained
unchanged; mixing its inputs with precise-note inputs is still rejected.

The explicit one-question successor is
[`lge_t1_051_calculation_v2.json`](../../benchmarks/datasets/reviewed/lge_t1_051_calculation_v2.json),
SHA-256 `c3f9bb839d988ebc853abf438a5d089c2294b14e8bb7cbddb234bda990421150`.
It changes only calculation variants and adds review metadata. Question, answer
key, evidence, tolerance, faithfulness, runtime and default profiles are unchanged.
Select this dataset explicitly in a future replay/admission; there is no automatic
overlay or lookup by question ID. It is a reviewed contract, not a temporary score patch.

Predecessor `benchmarks/datasets/single_doc_eval_full.curated.json` remains
SHA-256 `60539c9ebf557855154d9ebd24736273752d2a30d80908c77fa4387aab5b72e0`.
The other curated slices, old paid verdicts, source stores and artifacts are not rewritten.

## Filing evidence

Authority: `data/reports/LG에너지솔루션/2023_사업보고서_20240314001110.html`,
SHA-256 `1f7940b57ec1e423626a738e6de6a16794c9204d27077648dedd907e6767e293`.
The XML tree is parsed with entity resolution and network disabled.

| Field | Original source | Period and amount |
| --- | --- | --- |
| Consolidated summary profit | `III. 재무에 관한 사항 > 1. 요약재무정보`, row `영업이익` | 2023 column `2,163,234백만원`; 2022 column `1,213,719` |
| Consolidated note profit | Note 21, `영업이익(손실)` | preceding `당기`, row `2,163,234백만원` |
| Note AMPC | Note 21, `기타영업손익` and adjacent production-tax-credit explanation | preceding `당기`, row `676,874백만원`; previous-period row is `0` |

Exact XML locator bases and cells:

- Summary: `/DOCUMENT/BODY/SECTION-1[4]/SECTION-2[1]/TABLE[2]`;
  `TBODY/TR[30]` gives the annual date ranges and `TBODY/TR[32]/TD[2]` the profit.
- Note 21: `/DOCUMENT/BODY/SECTION-1[4]/LIBRARY/SECTION-2[2]/TABLE-GROUP[21]`;
  `TABLE[2]` says `당기 (단위 : 백만원)`, `TABLE[3]/THEAD` says `공시금액`.
  `TABLE[3]/TBODY/TR[4]/TE[2]/P` is AMPC, `TR[5]` explains its meaning, and
  `TR[23]` reports profit. `TABLE[5]`/`TABLE[6]` are the previous-period counterpart.

The original curated row already cited summary profit and note AMPC as valid
evidence, but its precise variant required both operands to come from notes.
It also used the non-temporal heading `공시금액` as `period`, and compared raw
row names to human-facing answer labels. These were independent contract mismatches.

## Corrected matching contract

- `connected_note_precise_v2`: note profit row plus note AMPC row.
- `summary_note_precise_v2`: summary profit row plus note AMPC row.
- Both require resolved `2023`, consolidated scope, the exact filing ID,
  source-specific row names/headings and existing value/unit checks.
- `공시금액` stays in `source_period_surface`; it never becomes a year alias.
- Derived output identity is its value, `derived_value`, difference operation,
  and binding to every selected operand. No verbatim derived-answer label is required.
- Legacy `strict_label` remains unchanged; source row names cannot satisfy it.

## Verification and limits

The compact committed fixture is a field-for-field projection of the frozen
LG trace, not a reconstructed candidate selection. Source result SHA-256 is
`e26ea797b056dcd56d9adb885c3d1c24297e018675ba72fe030c4e71d61bae92`.
The live-selected IDs remain `cand_4cdfeaa9d5eeda825282` and
`cand_38f964d793d8e1c9cb40`. Note-only selection is source-reviewed, not a new live result.

Socket-blocked replay checks the original XML, exact fixture projection, and
current LG/NAV numeric/final/ledger execution. Both frozen LG answer and current
dependency-explanation answer retain old-contract FAIL and reach successor numeric
PASS with `summary_note_precise_v2`. Sixteen altered-source negative controls fail.
Receipt: `benchmarks/results/lge_calculation_contract_v2_review_2026-09-08/receipt.json`,
SHA-256 `6c961c96db0dc88ffd01e442104917f8dd83a6efc6339e7e72aaa3f0d5f91c8e`.

Python 3.13.13: 120 focused evaluator tests, 1,090 full tests, 24 docs/import/topology
tests pass; runtime domain audit (84 reviewed literals), pycompile and diff checks pass.

Provider/compiler/store writes: zero. This is evaluator-only re-scoring, not a new
model/retrieval run or qualitative judge result. Historical provider approvals
are exhausted; any paid run still needs a new manifest and explicit approval.
