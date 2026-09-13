# Narrative evidence selection: proposed boundary change

Status: **characterized, not implemented** (2026-09-13). This is a design note,
not a replacement for the [current runtime contract](agent_runtime_contract.md).
No runtime, compiler schema, provider, store or historical result changed.

## Evidence and diagnosis

The consumed [subject/fact compiler run](../../benchmarks/results/subject_fact_compiler_2026-09-13/RESULTS.md)
remains **7/9 structurally complete**, not a general semantic-accuracy result.
Its two withheld explanations have visible source support: one quotation adds
newlines to a continuous list; another claim cites a paragraph's final sentence
but omits the subject-bearing sentence required by the claim-local contract.
The latter is not evidence that the coherent paragraph has the wrong subject.

[Eight anonymous characterization tests](../../tests/test_narrative_binding_boundaries.py)
exercise the real validator, protected executor and mocked compiler retry:

- Formatting-only quote drift fails; using the original bytes succeeds. Real
  source newlines must also survive, so blanket whitespace removal is not a fix.
- One claim missing subject support withholds the whole narrative binding.
  Explicitly reusing its subject-bearing quote preserves all four fact readings.
- Repeating the invalid draft fails again; authored repairs fit the existing
  single retry and preserve the independent accepted island and cohort bytes.
- Contrasting subject assignments for a pronoun can both pass with literal
  subject quotes. Structural acceptance does not prove semantic attribution.
- Deleting the failed claim can pass structural validation while omitting a
  requested detail. Automatic pruning is not a completeness repair.

The bounded diagnosis is an avoidable **output-construction burden**: the
compiler must recopy exact source bytes and repeatedly spell out shared support.
These tests do not prove that a new schema will improve model behavior. They also
do not justify weakening exact provenance or implementing deterministic coreference.

## Selected mechanism

Keep interpretation in the existing compiler; make evidence a source selection,
not model-generated quotation text. Share subject support only by explicit refs.

### 1. Source-addressed evidence

Project a transient address map from the **currently visible** body/bundle and
attached located contexts. Each address retains candidate/context/bundle IDs,
source fingerprint, exact surface-relative offsets and physical provenance.
Existing physical cell/source-segment boundaries remain hard partitions.

Within each partition expose deterministic, lossless text pieces with short IDs.
Use generic line/punctuation boundaries and a bounded-length fallback, not a
financial sentence parser. Pieces are display addresses, not semantic units:
the original text must reconstruct exactly, and adjacent pieces may be selected
as a range. Pin this mechanical policy with multilingual fixtures before runtime
integration; measure its prompt overhead against existing prompt limits.

The compiler selects `{candidate_id, source_requirement_id, surface_id,
first_piece_id, last_piece_id}`. It does not calculate character offsets or return
a replacement quotation. Code resolves one ordered, contiguous range inside one
partition and extracts the original substring. Multiple sources/cells require
separate selections. Selecting an entire paragraph must be explicit; an invalid
or missing selection never expands to the full candidate as a fallback.

Addresses bind source identity, content and offsets, not input order. Repeated
identical text at different positions remains distinguishable. Recompute and
validate against the execution-bound source; stale, hidden, reversed, cross-cell
or cross-owner references fail. An address grants no new candidate eligibility.
Candidate IDs, catalog hashing, parser/store shape and numeric assertions stay
unchanged. No normalized/fuzzy quote repair or hidden-source lookup is introduced.

### 2. Explicit shared subject support

Each narrative obligation declares a small `subject_bindings` registry containing
`subject_binding_id`, source-copied `subject` and evidence selections above.
Each claim supplies `subject_binding_id`, `text` and its own fact selections.
The compiler, not code, decides which claims share that subject and whether the
source actually attributes those facts to it. There is no previous-claim subject
inheritance, issuer fallback or first-entity rule.

Code resolves and checks the cited subject once, then checks permission for every
use. Subject selections ground the label; **only that claim's fact selections**
plus the existing report-year allowance ground its numeric statements. Sharing
subject support must not authorize numbers from other claims or paragraph tails.
Owner/requirement, scope and row-description checks remain independent.
Validated readings retain subject and fact spans separately; public text and
citations are deterministic projections, with the current HTTP shape preserved.

## Small implementation sequence

1. Add only the provider-free address projector/resolver contract. Test lossless
   reconstruction, repeated occurrences, input-order invariance, multiline and
   multilingual text, physical partitions, stale content, and visibility limits.
   Check prompt bytes on anonymous sources and existing saved payloads, without
   changing those payloads or treating their accepted answers as an oracle.
2. Switch the internal narrative schema, prompt, validator, retry merge and
   reading projection together. Add explicit subject references; do not maintain
   a long-lived production dual-write/quote fallback. Update the normative runtime
   contract in that implementation commit. Numeric programs/assertions and
   multi-evidence narrative capability are outside the schema replacement.

Use the same compiler calls and **one** internal retry. Errors return the failed
owner/address/claim location and preserve unrelated accepted program bytes.
Do not couple this change to automatic claim deletion, partial-answer publication,
new semantic judges, candidate ranking, ontology changes or added LLM calls.

Local gates: address tests, current/new claim and number-authority controls,
targeted retry/island tests, domain/import/topology checks, then full unittest at
the schema integration boundary. Keep wrong-subject and omitted-request controls
as explicitly semantic negatives, not passing correctness scores. Any provider
comparison needs a fresh scoped manifest/approval after these local gates; the
consumed admission and old result bytes remain immutable.

## Characterization verification

The new eight tests and related claim/context/retry controls pass **55/55**;
import/topology/documentation checks pass **24/24**. Domain audit (83 reviewed
literals), `py_compile` and `git diff --check` pass. Full unittest was not rerun
for this test/docs-only change. The consumed result/receipt hashes and all **160**
runtime and **77** protected files remain unchanged; provider calls: **0**.
