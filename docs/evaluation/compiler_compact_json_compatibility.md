# Compact-JSON compatibility across output kinds

The unchanged serialization instruction passes **32/32 authored positive
combinations** across eight numeric, narrative and mixed cases. Baseline versus
candidate prompts and pretty versus compact replies produce identical compiled
programs, validation and execution. **28/28 invalid combinations** remain rejected.
Four deliberately false narrative readings remain structurally accepted, retaining
the boundary between source linkage and semantic accuracy.

This is provider-free compatibility evidence, not new model behavior. Replies are
authored before execution; the instruction cannot influence them. No generation,
count, embedding, retrieval, ingest or application request occurred. Production
prompts, schemas, settings and retry limits remain unchanged.

## Scope and cases

The user continued the documented compatibility step after the
[four-response comparison](compiler_compact_json_comparison.md). Work starts on
clean `292d3d0a` with the same 466-character candidate prefix. The
[local packet](../../benchmarks/results/compiler_compact_json_compatibility_2026-09-18_v2/)
freezes source/catalog/query objects, schemas, authored replies and expectations.
The numeric cases reuse existing synthetic test fixtures; direct-context and
narrative cases explicitly exercise CRLF/LF, tabs, consecutive spaces, quotes,
backslashes and Korean text. These are development controls, not unseen sources.

| Case | Contract checked |
| --- | --- |
| Mixed scale | Table/prose units: 120,000, then 128,000 won |
| Source-format swap | Same operation across reversed source formats: 120, then 128 |
| Signed adjustment | Signed prose operand: 76, then 82 |
| Display and dependency | Calculated 20%, reported display 21%, dependent calculation 40% |
| Inline request quantity | Owned factor 2.75 applied to calculated 20%, yielding 55% |
| Direct multiline context | Exact attached context quote and period proof, quantity 23 |
| Narrative multiline | Exact source addresses and raw claim strings across multiple lines |
| Numeric plus narrative | Quantity 12 and the same narrative within one compilation island |

Each case runs through two prompt conditions and two response serializations.
The installed OpenAI/LangChain SDK produces the real strict-schema request shape;
HTTP is mocked with dummy credentials and external sockets are blocked. Captured
requests differ only by the candidate prefix. Model, medium reasoning, schema,
5,120 output ceiling, `store=false` and default service tier remain equal.
No original/source string or selected reference is rewritten.

The current Compiler lowers and executes every positive payload with one mocked
SDK call and zero repairs. All **56 positive output instances** retain their
expected calculation/display distinction, units, source references and dependency
values. Parsed response strings match authored values; raw SDK text matches the
supplied mock reply. Reloading sorted stored JSON changes object-key order in
prompt sections and mock reply objects while preserving all string values.
The prompt comparison canonicalizes only JSON sections. Actual paired SDK requests
retain exact prefix-only differences; paired compilations are byte-identical.

## Rejection and meaning boundaries

The negative controls cover an inexact multiline context quote, foreign source
reference, missing request-quantity proof, self-referencing formula step, missing
mixed output, completed JSON with incomplete provider status, refusal and truncated
JSON. All 28 combinations fail their existing boundary without repair.
Whitespace normalization inside the context quotation specifically yields
`context_quote_not_exact`; the formula control retains
`invalid_formula_step_reference`. Compact formatting does not bypass either check.

The deliberately wrong claim says a subject uses no local partners while its
selected source says it retains local partners. All four variants still pass
structural validation. This expected negative demonstrates that well-formed JSON
and exact source linkage do not establish entailment. No semantic grader or
meaning-repair rule was added.

Raw narrative claims and exact evidence retain line breaks and consecutive spaces.
The existing `render_narrative_claim` display formatter joins display whitespace
and avoids repeating an already present subject. The displayed sentence therefore
has normalized spacing in both conditions; the model claim and source quote do
not. This pre-existing display behavior is distinct from response serialization.

The [official Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs)
documents refusal and incomplete-response handling. The local checks preserve
those boundaries; the guide does not establish that this prompt prevents repeated
whitespace or preserves semantics in future model generations.

## Validation, corrections and remaining work

The completed matrix contains **64 mocked SDK requests**: 32 positive, 28 rejected,
and four structurally accepted semantic negatives. **55 existing contracts** and
**four documentation checks** pass with zero attempted external connections.
The full suite was not rerun for this documentation-only scope.

Initial authored preparation exposed two fixture-construction mismatches: dumping
a parsed union inserted an unsupported null field into a dependency selection,
while a legacy paragraph helper omitted a now-explicit nullable row-description
field. The controls now retain dependency wire objects and explicitly author null
paragraph row descriptions. No production or saved provider response was repaired.
Initial result assertions also confused calculated value with display value and
raw narrative text with its existing display formatting. Both were characterized
and mapped to the correct fields, retaining the same expected quantities and exact
source/model strings. Original scripts, failures and passing receipts remain;
the completed matrix reuses 24 passing receipts unchanged. Including superseded
local attempts, this packet made 78 mocked SDK calls, all with synthetic usage
metadata and no provider billing.

All **7,283 preceding evidence files**, plus 27 retained first-preparation files,
**174 source files**, seven runtime owners, **24 original store files** and local
settings are hash-verified. Only documents are committed; local controls remain
ignored. Added cost is **0**. Shared accounting stays **12.69919659 / 14**,
remaining **1.30080341**, pending **0**, not invoice.

The earlier two-per-condition model samples retain their original results and
limits. Compatibility is now covered locally; default adoption still needs model
evidence beyond the one known narrative input. Next prepare a small contrast on
different frozen source material with numeric/mixed outputs and content criteria,
then assess whether its complete request/output reserves fit the existing budget.
No paid successor, larger ceiling or default promotion is part of this step.

The [different-source comparison preparation](compiler_compact_json_transfer_preparation.md)
now freezes numeric/mixed inputs and paired SDK bodies. Its two rehearsals agree;
actual input counts remain unknown and the old full input ceiling exceeds the
remaining allowance. It adds no paid sample to the evidence above.
