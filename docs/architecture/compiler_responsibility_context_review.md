# Compiler output responsibility context review

Status: implemented in production compiler presentation, provider-free gate, 2026-09-12.
Implementation starts at clean `ead37a80`; prior measured runtime was `47fafc12`.
Normative authority remains [runtime contract](agent_runtime_contract.md).

## Decision

Carry a small, read-only map of **planned output responsibilities** into existing
narrative-bearing compiler calls. Keep semantic interpretation with the compiler;
do not turn overlap into a new keyword, source-ID, claim-count or semantic-validator rule.
No new LLM call, final synthesis stage, obligation merge or coupling edge is added.

The [measured predecessor](../../benchmarks/results/narrative_partition_pipeline_2026-09-12/RESULTS.md)
contains scheduling in both an intake output and a scheduling output. It also repeats
conditions across broad explanations and separate qualifiers. This is an observed
output-responsibility overlap, not proof that additional context will fix model behavior.

Previously only active owner metadata reached each island compiler. The real-prompt
regression reproduced that missing sibling responsibility boundary. The query compiler
now projects the full normalized plan once after global preflight and passes immutable
JSON to island calls through an explicit argument, separate from phase state/authority.

## Implemented information contract

`output_responsibility_context_v1` has role `planning_context_only`.
Its inputs are the exact query and the existing validated, ordered obligations, never
catalogs, compiler responses, execution values, statuses or review labels.

Each output copies only:

- `obligation_id`, `kind`, `label`, `request_unit_ids`;
- query-declared `local_subjects`;
- declared `scope`: company, period, consolidation scope, segment and basis;
- `source_sections`.

A shared `request_units_by_id` preserves exact text and Python-string spans in query
order, once per context, not once per output. This prevents short labels from becoming
the sole carrier of detailed instructions. Shared request IDs are allowed. No trimming,
semantic clause classification or loss of source/subject/scope distinctions is added.
Projection copies nested values and preserves original output order.

Do not include evidence requirements, candidate IDs/provenance, selected values,
accepted answers, validation status, rationale, soft retrieval hints or rank features.
These are field allowlists, not a promise that arbitrary user text cannot spell an ID.
Seeing a spelling in planning context cannot make it a candidate, quote or binding target.
Single-output plans add no context. Numeric-only calls retain their previous prompt
bytes; mixed calls receive the map only while at least one narrative output is active.

## Meaning and authority

- The map says what was planned, **not that another output has succeeded**.
- Read active explanations in relation to independently assigned topics, but retain
  conditions and relationships needed to make the active answer accurate.
- A common condition applied to different subjects/actions is legitimate content.
  Sharing a subject, request, source, quote or wording is not a deletion rule.
- `Compilation scope.active_obligation_ids`, active `Answer obligations` and existing
  per-owner candidate cohorts remain the sole output/selection authority.
- Initial and retry calls derive context from the same original plan. Retry targets
  alone remain editable; accepted answer text is not copied into this context.
- Existing explicit dependency inputs remain a different, validated pathway. The map
  does not create dependency authority or replace verified calculated inputs.
- Global V2 already binds the query and full ordered obligations. This derived display
  adds no execution authority and does not require a new execution envelope or graph phase.

## Provider-free evidence

`financial_compiler_presentation.py` owns the copied projection; `CALCULATION_PROMPT_POLICY`
owns interpretation instructions. The test-only queue decorator/helper is removed.
`tests/test_compiler_responsibility_context.py` inspects actual production prompts with
fixed authored responses: allowlists/copy ownership, long/Unicode requests and distinct
scopes, single/numeric-only omission, mixed/narrative retry transitions, unchanged active
cohorts and V2/program/answer/evidence, shared conditions, declared coupling and rejection
of inactive output IDs, registered-but-invisible candidates and query-only quotes.
Global invalid ownership blocks before projection/dispatch. Context is built once and
per-attempt fingerprint/JSON/policy bytes agree with actual prompt content. A policy-off
counterfactual changes only the new presentation block/byte diagnostic, not answer or
execution authority. Validated claim locations remain trace, not accepted program JSON.
An authored duplicate deliberately survives; no semantic deletion or model improvement
is claimed. Related focused suites pass **101/101**; domain audit passes 83 reviewed literals.
Python 3.13.13 full unittest **1424/1424** in 36.892s, docs/import/topology **24/24**,
pycompile and diff gates pass. No provider calls, paid admission or store mutation.

[Saved-plan projection receipt](../../benchmarks/results/compiler_responsibility_context_review_2026-09-12/receipt.json)
is a historical **test-only prototype on `97232a56`**. It adds a proposed suffix to copies of 12 saved compiler requests, without dispatch or recompiling
those cases. Eleven receive context; the one-output case receives none. Serialized SDK
bytes total **353,458 → 375,561**, **+22,103 (+6.2534%)**; largest request **31,666 bytes**.
Schema, original request prefix and all frozen files remain unchanged. This is not token,
cost or latency measurement. API calls 0; runtime/config 157 and protected evidence 216
hashes unchanged at that predecessor. These byte figures are not measurements of the
new production prompt. Its probe imports the retired review helper: reproduce it at the
recorded predecessor, not by modifying the immutable probe. The paid outcome is unchanged.

## Separate existing limit

While constructing an explicit-conflict control, current company applicability treated
`Issuer` and `OtherIssuer` as compatible: `_scope_surface_matches` permits containment.
It rejects the disjoint surface `Elsewhere`. A dedicated characterization records that
company-surface compatibility is not exact filing identity. This test does not show that
foreign documents pass real scoped retrieval, which is not exercised here. No company
matching rule is changed as part of this compiler-context review; identity/alias handling
would need its own bounded review before claiming stricter protection.

## Next measurement boundary

The [fixed-plan successor](../../benchmarks/results/compiler_responsibility_compiler_2026-09-12/README.md)
now freezes runtime `f5a2241a`, the same five inputs/catalogs and prior model plans. Pro
initial calls remain 12; no planner is rerun. All initial SDK differences are exactly
this context block, +21,850 bytes; two no-call receipts match. Admission `436771c0...6c7b0`
proposes USD 0.60 and still needs fresh approval. No paid call or model improvement exists.
Keep independent topics, shared qualifiers and unsupported omissions beside repetition;
do not optimize only for shorter output or a fixed count. Prior provider artifacts stay intact.
