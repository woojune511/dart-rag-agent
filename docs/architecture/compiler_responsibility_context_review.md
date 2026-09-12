# Compiler output responsibility context review

Status: provider-free design review and test-only prototype, 2026-09-12.
Baseline `97232a56`, runtime still `47fafc12`. **Not enabled in production.**
Normative authority remains [runtime contract](agent_runtime_contract.md).

## Decision

Carry a small, read-only map of **planned output responsibilities** into existing
narrative-bearing compiler calls. Keep semantic interpretation with the compiler;
do not turn overlap into a new keyword, source-ID, claim-count or semantic-validator rule.
No new LLM call, final synthesis stage, obligation merge or coupling edge is proposed.

The [measured predecessor](../../benchmarks/results/narrative_partition_pipeline_2026-09-12/RESULTS.md)
contains scheduling in both an intake output and a scheduling output. It also repeats
conditions across broad explanations and separate qualifiers. This is an observed
output-responsibility overlap, not proof that additional context will fix model behavior.

Current `_compile_semantic_calculation_program` has the full normalized plan but passes
only each island's obligations to `_compile_semantic_calculation_island`. Initial/retry
prompts project only active owners; the whole question does not describe which other
output was assigned which part. That is the specific information boundary to address.

## Proposed information contract

The test-only `output_responsibility_context_proposal_v1` has role `planning_context_only`.
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
semantic clause classification or loss of source/subject/scope distinctions is proposed.
Projection copies nested values and preserves original output order.

Do not include evidence requirements, candidate IDs/provenance, selected values,
accepted answers, validation status, rationale, soft retrieval hints or rank features.
These are field allowlists, not a promise that arbitrary user text cannot spell an ID.
Seeing a spelling in planning context cannot make it a candidate, quote or binding target.
Single-output plans need no extra context. Numeric-only calls should stay unchanged;
mixed calls may use the same map when an active narrative needs responsibility context.

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

`tests/compiler_responsibility_review_support.py` contains a **test-only** projection and
queue decorator. It appends context at the authored-response queue, not in the real prompt
builder. Production prompt diagnostics therefore do not measure that appended suffix.
The decorator is a disposable review adapter, not a second runtime implementation.

Nine tests cover copied allowlists, long/Unicode requests and distinct scopes, no added
context for one output, unchanged candidates/program/validation/V2/final answer, shared
conditions, declared coupling, separate-island and within-island targeted retries, and
rejection of inactive output IDs, a registered but invisible candidate, and query-only quotes.
An authored duplicate deliberately survives: this is not a measured semantic improvement.

Related request/partition/retry tests: **43/43** in 5.617s; docs/import/topology **24/24**
in 12.758s, pycompile and diff checks pass. Full unittest is not repeated for this
test/docs-only review. The prior runtime full gate remains 1411/1411 on `47fafc12`.

[Saved-plan projection receipt](../../benchmarks/results/compiler_responsibility_context_review_2026-09-12/receipt.json)
adds the proposal to copies of 12 saved compiler requests, without dispatch or recompiling
those cases. Eleven receive context; the one-output case receives none. Serialized SDK
bytes total **353,458 → 375,561**, **+22,103 (+6.2534%)**; largest request **31,666 bytes**.
Schema, original request prefix and all frozen files remain unchanged. This is not token,
cost or latency measurement. API calls 0; runtime/config 157 and protected evidence 216
hashes unchanged. The five-case paid outcome remains repetition goal not met.

## Separate existing limit

While constructing an explicit-conflict control, current company applicability treated
`Issuer` and `OtherIssuer` as compatible: `_scope_surface_matches` permits containment.
It rejects the disjoint surface `Elsewhere`. A dedicated characterization records that
company-surface compatibility is not exact filing identity. This test does not show that
foreign documents pass real scoped retrieval, which is not exercised here. No company
matching rule is changed as part of this compiler-context review; identity/alias handling
would need its own bounded review before claiming stricter protection.

## Next implementation boundary

1. Move the reviewed pure projection into existing `financial_compiler_presentation.py`
   and its interpretation instructions into `CALCULATION_PROMPT_POLICY`. No new planner
   output field, classifier or request-assignment fallback.
2. After existing query preflight, build the context once from the whole plan. Pass it
   to the island compiler through an explicit internal argument, not a new shared state
   key. Keep active owner/quote/cohort projections unchanged on initial and retry calls.
3. Attach it in existing narrative/mixed templates. Record context fingerprint/bytes
   in per-attempt diagnostics; opt-in admission must inspect the final serialized request.
   Do not silently truncate responsibility information to fit a budget.
4. Replace the test decorator with assertions against actual production prompts. Keep
   numeric/dependency, source authority, retry and negative overlap controls; run the
   focused, audit/import/topology and full compilation integration gates. Remove the
   test-only transport adapter once its consumers have moved.

This review does not implement those production steps or prepare a new paid admission.
Any later model-quality measurement needs new frozen inputs/runtime, final request-cost
preflight and separately scoped approval; no old admission may be reused.
