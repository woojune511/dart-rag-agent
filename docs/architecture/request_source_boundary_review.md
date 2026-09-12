# Request-to-source boundary review

Status: provider-free characterization and proposed next change, **not implemented**.
Baseline: `fe6448b4`, unchanged runtime `f5a2241a`; reviewed 2026-09-12.

## Findings

The latest full-agent run remains **0/3 complete**. Two failures expose a mismatch
between the representation of a request and the representation of its evidence;
the narrative failure does not yet establish the same defect.

| Boundary | Observed evidence | What it establishes |
| --- | --- | --- |
| Requested section | Query says `연결 주석`; plan says `연결재무제표 주석`. The latter fails query-copy validation. Copying the former in a diagnostic plan passes that check but conflicts with all 86 reconstructed candidate paths. | `source_sections` currently has two jobs: preserve query wording and identify a literal document path. An informal request and a formal title cannot necessarily satisfy both. |
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

## Smallest useful implementation order

### 1. Separate requested section text from selected source location

Change the planning/source-scope seam first. Preserve the exact request reference
(request-unit ID plus exact text/span); separately select observed section IDs or
paths from a report-scoped inventory supplied to the **existing planner call**.
Build that inventory read-only from retained located section metadata, not body
mentions, inferred headings, arbitrary aliases or a new provider call.

The planner interprets informal wording against the inventory. Code verifies the
query span, inventory membership/report identity and parent/input intersections;
retrieval and validation use the resolved paths. Preserve the original request in
compiler input/V2 content so resolution cannot erase its qualifiers. Explicitly
named exact paths keep their current authority. Unknown/ambiguous resolution must
not silently remove restrictions or fall back to foreign sections.

This requires a deliberate internal contract/schema transition, not changing
`_title_matches` to containment. Exact ID/path checks prove location, not semantic
equivalence between informal wording and a title; that interpretation remains an
LLM responsibility and needs positive/negative source-reviewed controls. Bound the
inventory visibly; do not claim that a truncated inventory covers the whole report.

### 2. Clarify the planner's local-subject projection, without a new alias system

First use the existing `semantic_target.local_subjects` for the **complete named
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

Use the existing opt-in debug/export seam to retain each attempted program and
its validation locations for the next separately approved run. Keep accepted and
unvalidated output distinguishable; do not add another model call or a default
HTTP payload. Test that targeted retries expose exactly the draft sent and leave
other accepted outputs unchanged. Only then decide whether a concrete prompt,
transport or quote-construction repair is needed.

## Verification and limits

[Anonymous characterization tests](../../tests/test_request_source_boundary_characterization.py):
**12/12**, including literal section dead ends, fixed-target retry, whole-cell
identity controls, multi-quote subject grounding and an explicitly false semantic
control. Together with existing source-scope, subject, claim, query-subject and
planner transport tests: **76/76**. These green tests expose current limitations;
they do not certify a repaired system. Replace characterization expectations
deliberately when the corresponding contract changes.

Documentation/import/topology checks: **24/24**, domain-term audit: **83** reviewed
literals, plus syntax and diff checks. No full-suite rerun for tests/docs-only work;
the runtime's prior 1,424-test gate is historical, not new answer acceptance.

[Local reproduction packet](../../benchmarks/results/request_source_contract_review_2026-09-12/README.md)
contains source projections, authored controls, hashes and reproduction commands.
It is ignored experimental evidence, not a fixture to fit runtime behavior to.
Runtime, candidate IDs, source stores and paid-run artifacts remain unchanged.
