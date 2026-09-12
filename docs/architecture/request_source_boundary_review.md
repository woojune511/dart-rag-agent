# Request-to-source boundary review

Status: section separation, planner name/description instructions and opt-in failed-draft
export are implemented and locally verified. Latest seam baseline: `623e0c80`, 2026-09-13.

## Findings

The latest full-agent run remains **0/3 complete**. Two failures expose a mismatch
between the representation of a request and the representation of its evidence;
the narrative failure does not yet establish the same defect.

| Boundary | Observed evidence | What it establishes |
| --- | --- | --- |
| Requested section | Query says `연결 주석`; the paid plan says `연결재무제표 주석`. The latter fails query-copy validation. Copying the former in a diagnostic plan passes that check but conflicts with all 86 reconstructed candidate paths. | The literal-only predecessor gives `source_sections` two jobs: preserve query wording and identify a document path. An informal request and a formal title cannot necessarily satisfy both. |
| Numeric subject | Query/paid planner uses `커머스 부문`; both selected cells retain `영업부문 > 커머스` in their column axes. They are visible but `candidate_subject_unresolved`. | The full request phrase is being used as a cell identity. Repeating the same selection cannot repair a fixed planner target. This is not missing table extraction. |
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

Implemented as a bounded **planner instruction/schema-description change**. The old
description said to preserve names "including qualifiers", without distinguishing
identity-bearing qualifiers from surrounding descriptions. `local_subjects` now
asks for the complete named subject, not its whole descriptive request phrase.
Anonymous policy contrasts distinguish a role wrapper from a full multiword name
and from a named group; the same rule applies to each required input's own subject.

Full-name modifiers and group membership remain identity. Other period, region,
exclusion and whole/part conditions stay in owned exact request units and applicable
scope/requirements. Existing transport already preserves these, so no new field,
runtime suffix deletion, alias mechanism, extra call or frozen-plan rewrite was
needed. Whole-axis, period, scope, visibility and V2 checks are unchanged.

This clarifies what the **existing planner** should decide; it is not proof that a
new model response will comply. A deliberately wrong shortened authored target can
still pass structural validation against a matching short source name. That known
semantic negative control remains explicit. Genuine aliases absent from the query
need a separate source-grounded contract, not a new bypass or model rationale.

### 3. Preserve failed narrative drafts before changing their semantics

Implemented in the existing `include_debug_bundle=True` path. Request-local
`compiler_attempt_debug_v1` records retain the schema-parsed model program before
merge and the complete validation input before rejected bindings are pruned.
These are local JSON serializations with UTF-8 SHA-256, not raw provider responses.
Validation locations refer to the merged input; compile-valid owner IDs are listed
separately. Exact projected retry-feedback text shows the filtered draft actually
sent, not a reconstruction from the final accepted program.

Records follow island/attempt order and own their data. Debug-off requests do not
collect them; default HTTP, answer/review/ledger and scoring do not include them.
The evaluator/benchmark and compiler-only exporters retain the separate diagnostic
field for future runs. No prompt, schema, validator, visibility or call-count change.
Unavailable parsed responses have null program snapshots and an error class, not
fabricated model output or a captured exception body. Terminal admission stops
still raise; a call that never returned parsed output cannot supply a lost draft.

The nine authored-response tests cover failed drafts after pruning, exact errors,
same-island merge vs raw retry, separate accepted islands, debug-on/off prompt and
validation equality, per-request graph capture, owned copies and export isolation.
Only a new separately approved model run can show the model's actual quote repair.

## Verification and limits

[New anonymous contract tests](../../tests/test_source_section_bindings.py): **20/20**.
They cover inventory order/bounds, exact owned requests, unknown IDs, same-title
foreign filings/branches, descendants, parent/input intersections, runtime-field
injection, overwide visibility, same-cohort retry, unaffected islands and V2 drift.
Related source-scope, retry/dependency, authority, presentation and planner tests:
**75/75** on the section seam. Current full unittest: **1,474/1,474**, Python 3.13.13,
47.962s; draft/export contracts **9/9**, related compiler/retry/export tests **156/156**;
domain audit **83**. Documentation/import/topology, syntax and diff checks pass.

[Planner name-projection tests](../../tests/test_planner_subject_projection.py): **9/9**;
combined source/subject/request tests **63/63**. Authored projections cover role
wrappers, complete names, named groups versus members, bilingual spellings,
required-input identity, period/region/basis conflicts, exact request retention,
same-cohort retry, unchanged accepted output bytes and execution-content drift.
They check instructions and transport, not model inference or semantic accuracy.

[Saved-source transport control](../../benchmarks/results/source_section_bindings_2026-09-12/README.md)
reconstructs all three original catalogs with unchanged IDs/fingerprints. An
**authored** binding preserves `연결 주석` and selects the observed filing-qualified
`III. 재무에 관한 사항 > 3. 연결재무제표 주석`: four requirement errors become zero,
and the same 86 candidates match both owners. The two NAVER saved validations and
accepted acquisition IDs are unchanged. Fifty protected files (including the
[prior characterization](../../benchmarks/results/request_source_contract_review_2026-09-12/README.md))
retain their SHA-256. No original plan, store, dataset or result was rewritten.

[Subject transport control](../../benchmarks/results/planner_subject_projection_2026-09-12/README.md)
uses the same reviewed numeric source and earlier authored formula/period witnesses.
An authored complete name passed through the current planner owner removes two
subject errors, with the request/scopes/labels and accepted narrative bytes intact.
The 482-member catalog and 52 protected files retain their hashes. This is not a
replay of a newly generated model plan or correction of the paid output.

Source-exposed controls are not new inference, answer acceptance or unseen-question
generalization. Paid **0/3** is unchanged; provider/ingest/store writes are zero.
New planner behavior still needs model validation. Earlier unexported narrative drafts
cannot be recovered; the new capture applies to future opt-in runs. A new model test
requires a new manifest, two identical no-call rehearsals and authority.
