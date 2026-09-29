# Candidate-local Compiler axis provenance

Implemented 2026-09-19 from clean `c8b325bf`, following the
[provider-free input audit](compiler_input_payload_audit.md). Production Compiler
input now shares repeated provenance within each candidate. This is a lossless
presentation change; model interpretation and answer quality remain unmeasured.

## Representation and authority

`financial_compiler_presentation.project_wire_axis_provenance` runs after short
reference and addressed-piece projection. For candidates with at least two axes,
it moves only present, exactly JSON-equal provenance fields into that candidate's
`axis_source_common`: candidate/document/hash/anchor, physical table/row/cell/value,
source-row and table-source identities. Boolean, integer, float and string values
are not conflated. Missing, unequal and future fields remain on their original axes.
Axis addresses, `field`, full `path`, candidate order and source strings stay intact.
Reserved common fields or repeated projection fail without mutating the input.

Changed payloads use `semantic_program_candidate_payload_v11`, retaining any
`piece_columns`; otherwise the existing v9/v10 payload and complete SDK request
remain unchanged. A 234-byte policy instruction explains candidate-local
inheritance only for v11, in both initial and retry prompts. The compact JSON
instruction remains the unchanged leading instruction. Canonical catalogs,
reference maps, response schemas, lowering, source/owner permissions, arithmetic,
V2 fingerprints, provider settings and call/retry limits are unchanged.

Equal text in different source addresses is retained. Shared provenance within a
candidate does not authorize another candidate, cell, context or owner. No runtime
decoder accepts model-supplied common provenance; the inverse is test-only.

## Frozen-request measurements

The two immutable app requests were projected with the production helper and
policy. No provider/count/embedding/ingest call or new admission occurred.
Request sizes include the explanation and JSON escaping, with canonical UTF-8
serialization; these are not model-token counts or billing measurements.

| Measure | Numeric | Narrative |
| --- | ---: | ---: |
| Candidates with shared axes / total | 12 / 14 | 1 / 10 |
| Candidate payload bytes, before → after | 62,666 → 55,395 | 46,970 → 46,416 |
| Prompt UTF-8 bytes, before → after | 81,592 → 74,555 | 59,045 → 58,725 |
| Canonical request bytes, before → after | 97,309 → 89,817 | 65,447 → 65,090 |
| Canonical request bytes saved | 7,492 (7.6992%) | 357 (0.5455%) |

Both projected payloads restore to identical canonical JSON trees. All untouched
subtrees, source strings, physical identities, axes, units, periods, context
attachments, readings, cohorts and settings remain identical. Narrative gains are
small because its payload is dominated by source readings, which this change
preserves. The earlier diagnostic prototype included different version/explanation
overhead; its measurements remain historical.

## Verification and remaining boundary

- Ten new contracts cover exact restoration, nonmutation, typed/missing/unknown
  fields, distinct-source authority, collisions, direct/calculated/mixed/narrative
  SDK requests, shared-basis proofs and targeted retry. Authored mocked SDK replies
  preserve identical lowered programs, validation, execution, V2 envelopes, strict
  response schemas and accepted outputs. Pure narrative/single-axis requests are
  byte-identical. This does not test how a model interprets the new representation.
- Existing Compiler/source-authority/retry regression: **118 passed**. Phase/API,
  import and topology checks: **46 passed**. Documentation: **2 passed**;
  **176 total**, no skips or external connections. Runtime domain audit passes
  with **83 reviewed literals**. No full benchmark was needed for this seam.
- The first new-test run had one authored-fixture projection mismatch after a
  deliberately corrupted narrative claim; retaining the typed fixture fixed the
  test setup. Production validation and its negative cases were not weakened.
- **9,050 predecessor files**, **24 store files** and local settings retain hashes;
  only three production source files change, with **171/174 unchanged**. Historical
  replies, source catalogs, consumed manifests and the budget-stopped app result
  remain immutable. Evidence packets are local and excluded from the commit.

Added cost **0**; shared accounting **14.57777845 / 15**, remaining **0.42222155**,
pending **0**, not invoice. No new server-token, cost-saving, quality or budget-fit
claim. The previous mixed app request still has no final answer. A future sampled
model/application check requires a fresh funded admission; this change does not
resume a consumed manifest or authorize another paid call.

Local evidence: [measurements](../../benchmarks/results/compiler_axis_provenance_2026-09-19/measurement.json),
[new contracts](../../benchmarks/results/compiler_axis_provenance_2026-09-19/axis_contracts_fixed.json),
[Compiler regression](../../benchmarks/results/compiler_axis_provenance_2026-09-19/compiler_regression.json),
[integration](../../benchmarks/results/compiler_axis_provenance_2026-09-19/integration.json),
[numeric restoration](../../benchmarks/results/compiler_axis_provenance_2026-09-19/numeric/roundtrip_proof.json)
and [narrative restoration](../../benchmarks/results/compiler_axis_provenance_2026-09-19/narrative/roundtrip_proof.json).
