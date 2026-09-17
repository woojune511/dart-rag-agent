# Research count and organization-scope readiness

Provider-free review on 2026-09-17, clean base `852da9ef`. The second
[frozen question](new_question_controls.md) remains unexecuted. Its source supports
the answer, but the current direct-numeric path has a reproducible unit boundary.
No provider request, new admission, ingest, runtime change or store edit occurred.

## Source and projection

The five stored nodes in the requested section were read as JSON and hydrated
with the existing table-payload function. Production source/catalog construction
produces **13 source candidates and 37 catalog entries**: 28 numeric, 9 narrative.
This supplies the whole requested section to an offline diagnostic. It does not
measure normal retrieval coverage or exercise a sampled Planner.

- Source `20240318000844:56:3` links year cell `3:0:5` = **2023** with count cell
  `3:1:5` = **21**, both in column 5. Column 4 is **2022** and also **21**.
  Distinct cell/candidate IDs survive extraction; value equality cannot prove the
  requested year. The total **154** and ongoing **152** are separate cells.
- The table yields **12 numeric candidates**: five years and seven counts, plus
  two narrative candidates. Stored `normalized_value=null` does not mean a missing
  runtime scalar: production extraction recovers 21. Its unit remains `UNKNOWN`,
  raw unit blank, period blank and `value_year=null`.
- Both count cells retain row header `건수` and column header `연구마감년도`.
  The year row is separately visible, not a located year axis of the count cell.
  Planner inventory exposes the query-matching header, not scalar-derived years.
- Source `20240318000844:54:1` preserves both organization-scope statements:
  business units have R&D functions; the introduction covers mainly R&D
  organizations and excludes R&D-related teams inside each business unit.
  Both are selectable for an authored narrative owner. Their complete quote
  ranges resolve through visible pieces **p1–p2** and **p3** respectively.

## Reproduced numeric boundary

Owners and selections below are explicitly authored diagnostics using the frozen
request and unchanged catalog. They are neither model responses nor accepted
answers. Reviewer criteria never enter source/catalog construction.

| Diagnostic | Observation |
| --- | --- |
| Blank display unit, full section | Both year/count rows are exposed. Correct count selection fails `empty_direct_rendering`; without period proof it also fails `candidate_scope_mismatch`. |
| Explicit `건`, full section | Known-COUNT prose candidates consume the two numeric bundle slots before the UNKNOWN-unit count row. The target is not exposed; selecting it is schema-rejected. This is a ranking/quota effect, not an explicit owner-scope conflict. |
| Explicit `건`, table-only diagnostic | The target becomes exposed but fails `direct_result_unit_mismatch` and `empty_direct_rendering`. Removing other source candidates therefore does not solve the unit boundary. The subset is not a proposed runtime override. |
| Full attached 2019–2023 context quote | `context_period_mismatch`: the range cannot resolve one requested year. |
| Exact substring `2023년 말 현재` | Period context validation accepts it for both 2022 and 2023 count cells. Final numeric validation still fails on rendering. Context linkage is not same-column semantic attribution. |

All **12** full-section selection diagnostics and **6** isolated-table selections
are retained, including rejected cases. A future change that only enables numeric
display must not mistake the short context quote for proof of the selected year.
The source itself is adequate; the current dimension/period representation and
validation limits must stay separate from source availability and model quality.

## Verification and preservation

- **17/17** local characterization checks, including seven anonymous boundary
  controls, pass. **37/37** existing unit/Compiler-grounding/Planner-axis/source
  interpretation tests pass. Documentation gates **4/4** pass.
- Full **1983/1983** and domain audit **83** remain the preceding build's evidence;
  source bytes are unchanged, so those broad gates were not repeated.
- **1650** predecessor files, **172** source files, **24** original/selected store
  files and local settings retain hashes. No real store client was opened.
- Provider/count/embedding calls, external test connections and added cost are
  **0**. Shared accounting stays **USD 7.38602105 / 8**, remainder **0.61397895**,
  pending 0, including prior count contingency rather than a verified invoice.

Local artifacts are under
[`research_count_readiness_2026-09-17`](../../benchmarks/results/research_count_readiness_2026-09-17/RESULTS.md).
Initial diagnostic lookup/fixture assumptions were corrected in separate receipts;
no runtime contract, frozen source or old experiment was changed to pass a check.
The preceding paid search/display result remains failed **0/4**; its later offline
replay remains a separate **4/4** result. This question has no live score.

## Next bounded work

Implement a provider-free, source-grounded dimension contract for bare numeric
cells with count-label evidence. First choose the correct owner among evidence
schema and declarative unit policy, then test explicit units, semantic count
labels, absent/conflicting evidence and misleading numeric headers anonymously.
Keep meaning selection with the Compiler and execution/physical linkage in code;
put vocabulary in ontology/policy/config. Do not force `COUNT`, widen quotas,
clear the requested unit or return a bare number merely to bypass the failure.

Same-column year attribution remains a separate acceptance gate after that seam.
Preserve original stores and source bytes; no paid rerun or fresh ingest is
scheduled by this readiness review.
