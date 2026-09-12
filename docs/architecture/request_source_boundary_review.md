# Request-to-source boundary review

Status: request/observed-section separation **implemented and locally verified**;
numeric subject projection and failed-draft export remain deferred. Baseline: `636c1101`, 2026-09-12.

## Findings

The latest full-agent run remains **0/3 complete**. Two failures expose a mismatch
between the representation of a request and the representation of its evidence;
the narrative failure does not yet establish the same defect.

| Boundary | Observed evidence | What it establishes |
| --- | --- | --- |
| Requested section | Query says `연결 주석`; the paid plan says `연결재무제표 주석`. The latter fails query-copy validation. Copying the former in a diagnostic plan passes that check but conflicts with all 86 reconstructed candidate paths. | The literal-only predecessor gives `source_sections` two jobs: preserve query wording and identify a document path. An informal request and a formal title cannot necessarily satisfy both. |
| Numeric subject | Query/planner uses `커머스 부문`; both selected cells retain `영업부문 > 커머스` in their column axes. They are visible but `candidate_subject_unresolved`. | The full request phrase is being used as a cell identity. Repeating the same selection cannot repair a fixed planner target. This is not missing table extraction. |
| Narrative quotes | The two visible sources contain the named company and the relevant surrounding passages. Authored exact multi-quote claims pass current validation. Rejected complete drafts were not exported. | The current claim contract can express these source readings. It is not yet justified to relax quote/subject checks or blame source loss; the exact rejected quote construction cannot be replayed. |

The numeric control uses an **authored** formula and exact attached `당기`/`전기`
witnesses. Changing only the copied owner/requirement local subject to the observed
`커머스` removes the two subject errors. This is diagnostic isolation, not permission
to rewrite the production plan or a replay of the model's missing draft. An earlier
control without period witnesses also fails period checks, as it should.

Reconstruction matched saved source/catalog counts, candidate-ID fingerprints and
catalog fingerprints for all three queries (482 / 246 / 86 catalog members).
The ID/catalog checks alone are not a saved complete-content hash; original store
files were also checked against the admitted SHA-256 values. Forty-eight protected
input/result/store files are unchanged. No gold labels, provider calls, ingest,
embedding or store writes were used.

## What not to do

- Do not delete `부문`, `division`, or other qualifiers using a runtime suffix list.
- Do not enable global substring matching. Anonymous member/group and modified-name
  controls demonstrate why containment is not equivalence.
- Do not drop an unresolvable source restriction, use the filing company as the
  value subject, or widen visibility to repair a compiler format error.
- Do not infer semantic attribution from exact quote occurrence. A deliberately
  false anonymous claim still passes structural checks; that is a known limit,
  not an accepted answer-quality fixture.
- Do not pay for another unchanged retry to diagnose an unexported draft.

## Implementation and remaining seams

### 1. Separate requested section text from selected source location

Implemented in the planning/source-scope owner. The **existing planner call** gets
`source_section_inventory_v1` from already-loaded committed BM25 metadata using the
retrieval owner's report filter. IDs bind explicit filing identity and located
paths, including observed ancestors. Body mentions and attached headings do not
enter this inventory. Its 256-section/64-KiB section-list limits report omissions;
an empty/truncated inventory is not document-wide absence evidence.

The model's `SourceSectionBindingV1` supplies an owned `request_unit_id`, unique
exact `requested_text` and observed `section_ids`. Code copies the selected records,
computes request spans and attaches the inventory fingerprint. Unknown IDs, empty
resolution and foreign request units become requirement errors; the affected
island makes no compiler call. Exact named-title controls stay strict. The old
`source_sections` format remains literal-only; the planner does not dual-write a
restriction into both formats.

Parent/input bindings intersect. Retrieval, seeds, cohorts, dependency validation
and execution use the resolved filing/path, not query-title spelling. Original
wording and resolved provenance stay in compiler input and V2 execution content;
targeted retries preserve them and other accepted program bytes. No extra model
call, alias list, substring bypass, catalog identity or public response change.
Exact ID/path checks prove location, **not semantic equivalence**; interpreting the
request and preserving its qualifiers remain planner responsibilities.

### 2. Clarify the planner's local-subject projection, without a new alias system

Deferred. First use the existing `semantic_target.local_subjects` for the **complete named
entity**, not the entire descriptive request phrase. Keep all modifiers and group
qualifications in exact request units and applicable scope/requirements; no code
strips words or substitutes observed names into a frozen plan. Evaluate anonymous
name-plus-descriptor, member/group, similarly named entities, bilingual names and
wrong-scope controls together.

Retain whole-axis validation and fail-closed member/group controls. The current
case does not justify a universal semantic-alias bypass, new role taxonomy or an
extra judge. If genuine aliases absent from the query still require support,
design an explicit source-grounded binding as a separate seam, with its changed
guarantees stated up front. A model-authored rationale alone is not identity proof.

### 3. Preserve failed narrative drafts before changing their semantics

Deferred. Use the existing opt-in debug/export seam to retain each attempted program and
its validation locations for the next separately approved run. Keep accepted and
unvalidated output distinguishable; do not add another model call or a default
HTTP payload. Test that targeted retries expose exactly the draft sent and leave
other accepted outputs unchanged. Only then decide whether a concrete prompt,
transport or quote-construction repair is needed.

## Verification and limits

[New anonymous contract tests](../../tests/test_source_section_bindings.py): **20/20**.
They cover inventory order/bounds, exact owned requests, unknown IDs, same-title
foreign filings/branches, descendants, parent/input intersections, runtime-field
injection, overwide visibility, same-cohort retry, unaffected islands and V2 drift.
Related source-scope, retry/dependency, authority, presentation and planner tests:
**75/75**. Full unittest: **1,456/1,456**, Python 3.13.13, 42.220s; domain audit **83**.
Documentation/import/topology, syntax and diff checks also pass.

[Saved-source transport control](../../benchmarks/results/source_section_bindings_2026-09-12/README.md)
reconstructs all three original catalogs with unchanged IDs/fingerprints. An
**authored** binding preserves `연결 주석` and selects the observed filing-qualified
`III. 재무에 관한 사항 > 3. 연결재무제표 주석`: four requirement errors become zero,
and the same 86 candidates match both owners. The two NAVER saved validations and
accepted acquisition IDs are unchanged. Fifty protected files (including the
[prior characterization](../../benchmarks/results/request_source_contract_review_2026-09-12/README.md))
retain their SHA-256. No original plan, store, dataset or result was rewritten.

The source-exposed control is not new planner inference, answer acceptance or
unseen-question generalization. Paid **0/3** is unchanged; provider/ingest/store
writes are zero. Numeric target spelling and unexported narrative drafts are not
repaired by this change. A new model test requires a new manifest and authority.
