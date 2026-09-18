# Compiler input-size and duplicate-metadata audit

Completed 2026-09-19 from clean `1e052f05`, using the two immutable Compiler
requests from the [budget-stopped application smoke](compiler_compact_json_app_smoke.md).
**Repeated axis provenance is a bounded reduction opportunity.** An experiment-local
lossless projection reduces canonical request bytes by **7.64% numeric / 0.46%
narrative**. Runtime/default prompts are unchanged. No provider, token-count,
embedding or ingestion calls, new paid admission, retry or resume occurred.

## Measured input components

These are exact UTF-8 field sizes and compact JSON component sizes, not additive
provider-token counts. Request bytes are canonical JSON, including escaping;
they are not observed HTTP framing. The original server counts remain historical.

| Component | Numeric request | Narrative request |
| --- | ---: | ---: |
| Original server-counted input tokens | 26,131 | 17,529 |
| Prompt text bytes | 81,592 | 59,045 |
| Instructions within prompt | 16,468 | 7,844 |
| Candidate payload within prompt | 62,666 | 46,970 |
| Candidate objects within payload | 38,924 | 11,562 |
| Source readings within payload | 8,408 | 23,435 |
| Context index within payload | 6,442 | 3,146 |
| Output schema, serialized separately | 9,800 | 2,847 |
| Entire canonical request bytes | 97,309 | 65,447 |

The numeric payload contains 14 candidates, including 12 numeric cells with two
axis records each. Their `interpretation_axis_sources` field entries account for
17,342 bytes including field names. Every axis repeats its cell/file/row provenance.
The narrative payload has ten candidates and one numeric cell; source readings
occupy **49.89%** of that payload. The same metadata optimization consequently has
little effect on the narrative request.

The installed tiktoken 0.12.0 has no `gpt-6-astra` encoding mapping. The audit uses
only a hash-verified local `cl100k_base` cache, with all external sockets blocked.
Canonical-request proxies decrease 31,981 → 29,182 and 23,430 → 23,262. These are
**local representation-size proxies**, not new server input counts or a billing
estimate; component token proxies are non-additive. No budget-fit claim follows.

## Lossless prototype and preservation

`diagnostic_axis_common_v1` places identical provenance fields in a candidate-local
`axis_source_common`, retaining each axis reference, `field` and full `path`.
Only keys present with exactly the same JSON value in every axis are shared.
Different/missing values and unknown fields stay local. The prototype adds a
243-byte explanation and its own diagnostic version; it is not a production format.

| Prototype result, including explanatory overhead | Numeric | Narrative |
| --- | ---: | ---: |
| Candidates factored | 12 / 14 | 1 / 10 |
| Candidate payload bytes removed | 7,226 | 508 |
| Canonical request bytes after projection | 89,875 | 65,149 |
| Canonical request byte reduction | 7,434 (7.640%) | 298 (0.455%) |

Both payloads expand to **exactly identical canonical JSON trees**. Candidate order,
source strings, units, periods, axes, contexts, piece partitions, visibility/cohorts,
physical provenance and request/output schemas are preserved. Non-input settings,
models and output limits remain identical. Nothing grants a new candidate or quote.
Seven anonymous controls pass, including distinct cells with equal text, missing
fields, null/empty/type distinctions, future fields, single-axis no-ops and rejection
of ambiguous overrides or an unversioned projection. This proves local information
preservation, not model interpretation, instruction compliance or answer quality.

## Source repetition and integration decision

Current readings already use **8 numeric / 5 narrative** `surface_ref` entries.
The remaining repeated source literals form **3 / 20 groups**, all with different
address contexts; repeated literal value bytes total 356 / 4,577. Two narrative
piece arrays are identical across distinct surfaces. Equal text does not make their
source/owner/attachment authority interchangeable. No surface, quote or context was
deleted, merged or normalized. Replacing them with existing `surface_ref` would
change that contract; any future content-sharing design needs separate review.

First implementation candidate: the narrow prompt-presentation boundary in
`financial_compiler_presentation.py`, after short-reference projection in
`financial_graph_calculation.py`. Keep `interpretation_axis_sources` in the canonical
catalog, address book and validators unchanged; do not change source IDs/hashes or
move factoring into retrieval policy as a selection rule. Before adoption, verify
numeric/direct/mixed/narrative, shared-basis and retry SDK fixtures, preserved
rejections and exact source/authority boundaries. Sampled model behavior and budget
feasibility remain separate later gates requiring fresh funded admission.

All **9,022 predecessor files**, **174 source files**, seven runtime owners,
**24 original store files** and local settings retain hashes. Only documentation is
committed. Added cost **0**; shared **14.57777845 / 15**, remaining **0.42222155**,
pending **0**, not invoice. The preceding app query remains stopped with no final
mixed answer; this audit does not retrospectively complete or resume it.

Local evidence: [audit and decomposition](../../benchmarks/results/compiler_input_payload_audit_2026-09-18/audit_report.json),
[source overlap review](../../benchmarks/results/compiler_input_payload_audit_2026-09-18/source_overlap_review.json),
[numeric roundtrip](../../benchmarks/results/compiler_input_payload_audit_2026-09-18/numeric/roundtrip_proof.json),
[narrative roundtrip](../../benchmarks/results/compiler_input_payload_audit_2026-09-18/narrative/roundtrip_proof.json),
and [anonymous controls](../../benchmarks/results/compiler_input_payload_audit_2026-09-18/prototype_controls.json).
