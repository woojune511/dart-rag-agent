# Request-to-source boundary review

Status: provider-free isolation at diagnostic baseline `845704bd`/runtime `83755b1e`
is complete. Its first bounded successor applies section eligibility before search
top-K; source identity, narrative admission and claim construction remain separate.
The [paid successor](../../benchmarks/results/request_source_full_agent_2026-09-13/RESULTS.md)
remains **0/3 complete**, **1/5 outputs accepted**, ledger **3/3 ok**,
API/execution exceptions **0**, estimated **USD 0.38085963/0.80**, billing unobserved.
Admission `673329a6...f3cb0` is consumed; no new paid run is authorized here.

## Current evidence

The [source replay and single-seam controls](../../benchmarks/results/request_source_boundary_isolation_2026-09-13/README.md)
reconstruct all three saved catalogs (**484 / 228 / 83** members) with unchanged
source counts, candidate IDs and catalog fingerprints. All **8/8** parsed attempts
reproduce visible IDs, model and merged program JSON, validation errors/status,
retry feedback and final merged programs. **76** protected input/result/store
files and the **155-file** runtime build fingerprint remain unchanged.
This is exact replay of saved programs through current compiler orchestration,
not model inference, a repaired answer or unseen-question generalization.

| Boundary | Observed mechanism | What the contrast establishes |
| --- | --- | --- |
| Request name → numeric cell | Planner still declares the descriptive phrase `커머스 부문`; both selected cells retain `영업부문 > 커머스` in their own axes. Extra context cannot replace that identity. | Copied `local_subjects` changed to the observed cell name remove only subject errors. Attempt 1 retains scope errors; attempt 2 exposes a later `context_quote_not_exact` for a source-display quote containing literal `...`. Instruction-only clarification has not resolved the whole failure. |
| Narrative claim → subject quote | A retry quotes a subjectless later paragraph although an earlier paragraph in the same visible source names the subject. Another claim's quote does not ground this claim. | Attaching the exact earlier subject quote to the same claim makes authored validation ready. The existing multi-quote contract can express this reading; no blanket quote/subject relaxation is justified. |
| Required input → selectable evidence | Relevant prose IDs are island-visible but admitted only for one input. Another input's six slots are all numeric rows; the compiler assigns prose to that input anyway. | Rebinding to the existing allowed input removes the wrong-owner error but still leaves the other input missing. This is allocation plus binding failure, not globally hidden-ID invention. |
| Located section → retrieval coverage | The requested note location resolves correctly and contains the omitted passage. Search truncates vector/BM25/RRF candidates before section filtering, which retains **15/65**. The passage is absent from retrieved and seed windows. | Real lexical replay and anonymous top-K contrasts expose a late-filter coverage defect. No original query vectors/per-search IDs were retained, so the exact historical hybrid omission remains unproven. |

### Why prose loses the requirement shortlist

Current [fact matching](../../src/agent/financial_candidate_matching.py) has a
length-dependent containment rule. A short name inside longer prose can remain
`unknown`, while that exact name on a table axis is a subject `match`.
Anonymous `Elm`, `Oak` and `별빛팀` controls reproduce this; longer `Aster`
and `Birch` prose names match. This is a literal threshold, not semantic evidence.

In the saved explanatory input, selected rows rank `[1,3,2,1,0,0]` and the
two prose sources rank `[1,1,2,1,0,0]`. The difference is subject authority,
not a numeric-format quota, repeated-keyword bonus or rank tie. Six rows exhaust
the input cohort despite not establishing the requested explanation.
Fixing this requires source-grounded identity/admission, not widening every
input to every island-visible ID or treating arbitrary substrings as identity.

### What retrieval replay can and cannot show

The original missing passage is present in the committed requested-section store.
For seven saved executed queries, report-filtered versus requested-section BM25
ranks are **11→3, 31→7, 399→223, 49→3, 128→3, 318→40, 841→261**.
Each search had `k=32`, lexical cap 96 and vector cap 64. The passage enters
the report-filtered lexical pool for three queries, so it is not unindexed or
universally absent from lexical retrieval. All 15 retained documents fit seeds;
the final eight-document window is not the sole explanation.

The section-restricted ranks are diagnostic contrasts, not production outcomes.
The original dense results and RRF membership cannot be reconstructed from those
scores. Early eligibility is a general correction to bounded selection order,
not proof that this one change makes the full question complete.

## Already implemented contracts

- **Request/location separation:** the existing planner receives a read-only,
  report-filtered `source_section_inventory_v1`, bounded at 256 sections/64 KiB.
  Owned exact request wording is separate from observed filing-qualified section
  IDs. Code supplies spans, paths and inventory fingerprint. Unknown/foreign
  bindings fail the affected island before compilation. Parent/input restrictions
  intersect, while unrestricted sibling outputs keep shared retrieval open.
  Literal `source_sections` compatibility remains strict, without dual-writing.
  Location checks prove provenance, not request/title semantic equivalence.
- **Planner subject description:** instructions distinguish complete names and
  identity-bearing qualifiers/groups from surrounding role descriptions.
  This is not runtime suffix stripping, an alias list, a source-grounded alias
  contract or proof a newly generated plan follows the instruction.
  Other exact request/scope conditions and complete cell-axis checks remain.
- **Opt-in failed-draft capture:** `compiler_attempt_debug_v1` preserves parsed
  model JSON before merge and complete validation-input JSON before pruning,
  with UTF-8 hashes, locations and exact projected retry feedback.
  Debug-off/default HTTP/answer/review/ledger/scoring are unchanged.
  It records parsed model programs, not raw API responses or absent drafts.

These contracts do not resolve all the failures above. Their implementation
history and earlier source controls remain in Git and the linked artifacts.

## Early-scope implementation and remaining changes

1. **Implemented:** report-filtered committed metadata is tested with the existing
   section-membership predicate before bounded search. Observed source IDs are
   qualified by their document identity and projected to the same native dense/
   lexical filter, including primary/retry searches and both cache keys. Empty
   eligibility makes no embedding/backend call; unaddressable rows are counted,
   not assigned fabricated IDs. Shared unrestricted outputs retain their original
   filter. Final source checks and input intersections stay strict. No query,
   score, corpus IDF, keyword, ranking quota, parser, catalog identity or store
   mutation. This is not a full-answer fix or a new paid result.
2. Separately design source-grounded request-name/cell-name binding. Preserve the
   original request and distinguish identity modifiers/groups from descriptions.
   Changing a frozen planner target in a diagnostic copy is not an authorized
   execution repair; no suffix list or global containment bypass is acceptable.
3. Separately repair narrative admission so short names and exact numeric axes
   do not mechanically hide relevant explanatory sources from an input. Retain
   per-input permission and capacity; no new repeated-keyword scoring or
   company/question-specific rule. Reassess claim construction using the existing
   exact multi-quote contract before inventing another schema or model call.

Do not rerun unchanged paid work, relax validation or claim that a structural
check proves semantic attribution. An intentionally false anonymous attribution
can still pass exact-occurrence checks; it remains a documented negative limit,
not a hard answer-quality oracle.

## Verification and limits

- [New anonymous failure isolation](../../tests/test_request_source_failure_isolation.py):
  **8/8**, with all earlier characterization tests preserved. They cover unchanged
  bad planner projections, complete cell identity, same-claim subject quotation,
  per-input visibility, short/long-name ranking, late top-K filtering and an
  unrestricted sibling. Current failures are expected contrasts, not fixes.
- New plus related subject, narrative, planner and retrieval tests: **89/89**,
  Python 3.13.13. Import/DAG/topology tests: **22/22**; domain audit: **83**.
- [Early-scope regressions](../../tests/test_source_scoped_search.py): **10/10**,
  including actual ephemeral Chroma with supplied synthetic vectors, lexical
  ranking, foreign filings/branches, unions, report/input boundaries, both caches,
  retry, BM25 fallback, empty scope and unaddressable metadata. The first top-K
  test failed on the predecessor and passes with the fix. Related initial suite
  **132/132**; current full unittest **1,492/1,492** (Python 3.13.13, 46.854s).
  Structural/local search success is not provider or semantic acceptance.
- The [section-binding tests](../../tests/test_source_section_bindings.py),
  [planner projection tests](../../tests/test_planner_subject_projection.py) and
  opt-in draft/export contracts retain their existing meaning: transport and
  authority, not semantic model accuracy.
- Authored controls invoke validation only, without V2-authorized execution.
  No provider, ingest, embedding, source/store/dataset change or artifact commit.

Earlier evidence: [literal-boundary characterization](../../benchmarks/results/request_source_contract_review_2026-09-12/README.md),
[section transport](../../benchmarks/results/source_section_bindings_2026-09-12/README.md),
[subject transport](../../benchmarks/results/planner_subject_projection_2026-09-12/README.md).
Prior unexported complete drafts remain unavailable; current captured drafts do not
retroactively recover them. Chronology lives in Git and immutable result bundles.
