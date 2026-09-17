# Shared-basis declaration characterization

Verified 2026-09-17 from `bc5116f0`. Four saved Compiler responses reproduce their
original lowering, validation status and errors without provider calls. The
declaration mismatch remains a representation problem; this work does not claim
to have eliminated model repairs. A separate source-scope omission found by the
controls is fixed in the existing validation owner.

## Saved-response evidence

The [local packet](../../benchmarks/results/shared_basis_characterization_2026-09-17/)
uses each run's own preserved requirements, candidate catalog, prompt, model
response and lowered validation input from `request_diagnostics.json`. It does
not borrow the successful run's catalog for the interrupted run. Complete
Compiler payloads and active obligations round-trip exactly, both saved program
hashes verify, and current lowering reproduces each internal program exactly.

| Preserved response | Replayed status | Relationship result |
| --- | --- | --- |
| Interrupted run, activity island, first attempt | invalid | Two `relationship_interpretation_missing_or_inconsistent` errors |
| Interrupted run, activity island, repair | ready | Both declarations identical |
| Budget successor, activity island, first attempt | ready | Both declarations identical |
| Budget successor, certification island, first attempt | ready | Independent output |

The first response's two basis explanations share an opening sentence but add
different qualifications. Current code requires nonblank, exactly equal text;
the prompt only asks for a consistent declaration. Code does not decide whether
those qualifications are semantically compatible. The real repair also changed
claim wording, so it is not an isolated one-field model experiment.

Two explicitly authored diagnostic copies isolate the gate: copying the first
basis into the other binding makes the original claims pass, as does removing
only the planned relationship. Neither copy is a sampled response, a production
repair, a new answer or proof of semantic equivalence. The interrupted run's
missing final answer stays missing. The successor's first-try success did not
change the underlying declaration contract.

## Source-scope correction and controls

Twelve new anonymous controls extend the relationship suite to **17** tests.
Before the source edit, **15** passed and **two** failed: narrative/narrative and
numeric/narrative outputs with the same declaration incorrectly accepted known
`consolidated` and `separate` sources under one shared-basis relationship.
Accepted narrative sources were absent from `resolved_sources_by_output`, so
the existing cross-output conflict check could not see them.

One assignment in `financial_calculation_execution.py` now retains those already
selected sources for that existing check. It adds no classifier, source rewrite,
scope inference, schema, model instruction, retry, permission or field. Unknown
scope remains unknown; independent outputs can retain different scopes.

The controls also preserve distinct physical sources, exact declaration matching,
empty-declaration rejection, owner visibility, selected subject grounding,
explicit owner-scope conflicts, mixed-output proof matching and same-cohort repair
without candidate exclusion. An intentionally false but identical basis still
passes structural checks, documenting that agreement is not semantic truth.
Every control checks that program, obligations and catalog inputs stay unchanged.

After the correction: **17/17** relationship and **147/147** focused contracts pass,
with no skips or external connection attempts; domain audit passes with **83**
reviewed literals. The four exact saved responses replay unchanged again.
Documentation checks pass **2/2**. The historical full **1940/1940** result belongs
to the previous source snapshot; this bounded change does not rerun the full suite.

All **1432** protected predecessor files, local settings and **24** original/selected
store files retain their hashes. No store client was opened. One of **172** source
files changes; experiments remain local artifacts. New API calls and cost are **0**.
Shared accounting remains **USD 7.08344260 / 8**, remaining **0.91655740**, pending 0;
these include contingencies and are not an invoice.

## Next bounded design

The next implementation should separate a relationship's common declaration from
each source's local interpretation, rather than require repeated free text:

1. Expose the existing request-grounded relationship IDs to Compiler and declare
   the common interpretation once per active relationship. Members explicitly
   reference that declaration; code checks ownership and complete membership.
2. Keep numeric request/axis/context proofs and narrative subject/fact selections
   intact. Do not overwrite their local basis with a copied relationship sentence,
   choose one member's text automatically or infer semantic equivalence.
3. Preserve known source-scope conflicts, owner authority, physical-row rules and
   abstention. Overlapping relationships need independent declarations; one output
   may reference more than one without forcing unrelated groups' text to match.
4. Bind declarations and references into lowering, immutable V2 fingerprints and
   targeted retry. Missing/foreign references fail closed. New authored transport
   fixtures must be labeled; sampled historical responses must not be rewritten.

This is a proposed next seam, not an implemented schema change. Provider-free
schema/lowering/execution/retry and semantic-negative controls come first. No
additional paid run is scheduled; reduced retries and unseen accuracy still need
separate evidence after implementation.
