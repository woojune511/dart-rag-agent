# Planner output-kind boundary

The Planner now distinguishes a requested scalar numeric result from a fact or
status explanation in both its policy prompt and generation-schema descriptions.
This addresses an ambiguity exposed by the [dividend-policy failure](dividend_policy_result.md),
where payment status was assigned `direct_value` and an associated amount was
selected. The change is a **generic Planner contract clarification**, not a
keyword classifier or a general model-accuracy result. The separately paid
[successor](dividend_policy_successor_result.md) now samples three narrative
owners, but its caller stops before the third owner is compiled; no completed
answer or isolated causal effect is established.

## Contract and scope

| Kind | Requested result |
| --- | --- |
| `direct_value` | A single numeric value reported by the source |
| `derived_value` | A numeric result calculated from evidence or declared dependencies |
| `narrative` | A fact, status, occurrence, condition, relationship or explanation, including a brief yes/no answer |

Numbers, amounts or dates in a question or its evidence do not turn a requested
status into a numeric result. Narrative requirements retain relevant facts and
qualifiers; independently requested quantities remain separate numeric outputs.
The model still chooses the kind. Code does not reinterpret question keywords,
force output counts, coerce old plans or rewrite their selected candidates.

Only `PLANNING_POLICY.requirement_planner_prompt_template` and the three production
Planner `kind` descriptions change. AST comparison confirms no other production
logic changes. Local and strict JSON schemas are structurally identical after
removing descriptions; no fields, literals, defaults, requirements or validation
constraints change. Models, output limits, candidate permissions, retry policy,
source validation and stores are unchanged.

## Provider-free evidence

Six new controls cover actual SDK serialization, English/Korean status facts
with numbers and pending conditions, mixed status and scalar outputs, preservation
of a misclassified authored plan, exact numeric quotation and the separate limit
of semantic validation. Before the source change, five controls passed and the
SDK instruction check failed; afterward all six pass. The focused regression
suite totals **82 passing tests**. Runtime domain audit retains **83 reviewed
literals** with no new unexpected terms.

A deliberate counterfactual claim can still pass physical source linkage.
That negative control demonstrates why authored transport or runtime `ready`
cannot establish entailment, correct model classification or full answer quality.

The saved real question was passed through the actual Planner SDK with sockets
blocked and its old sampled response returned locally. The successful replay
passes **25 checks**: request bytes change from **72,014 to 73,374** only through
the intended instructions and three `kind` descriptions. The original question,
scope, section/axis inventories and model settings remain byte-identical outside
those edits. These are SDK bytes, not measured provider tokens.

The review initially reconstructed report-scope keys in question-file order;
an offline comparison isolated that difference. Using the real API request
serialization restored the expected bytes. Three local SDK interceptions were
used during this review; no external request was made.

On `3a8ae0e2`, replaying the unchanged old response retained the wrong
`direct_value` status plan and the exact same three Compiler errors:
`source_interpretation_quote_mismatch`, `candidate_scope_mismatch` and
`source_assertion_candidate_not_selected`. The original application HTTP 500,
partial claims, consumed draft and cost remain unchanged. No new Planner choice,
Compiler answer, native retrieval or live success was sampled by that offline work.

## Preservation and next work

All **10208 predecessor files**, **24 original store files**, seven protected
runtime owners and local settings retain their hashes. Of 174 tracked source
files, only the two declared prompt/schema files change; the other 172 remain
identical. Import, topology and documentation gates pass separately. No original
Chroma store was opened and no experiment artifact is staged.

Provider calls and cost for that offline change were **zero**. Accounting then was
**17.11707679 / 18.27 USD**, with **1.15292321 remaining**, pending zero.
That offline work did not authorize a paid successor or budget increase.

The separate [exact quote-source correction](numeric_quote_source_boundary.md)
now removes the false quote rejection provider-free while preserving period
rejection, exact bytes and physical source ownership. The [fresh application
admission/rehearsal](dividend_policy_successor_admission.md) preceded the separately
authorized [paid successor](dividend_policy_successor_result.md). That execution
observes narrative payment classification, but three owners exceed its two
Compiler slots. No final answer is delivered. Current accounting is
17.71533922/18.82 USD, remaining 1.10466078, pending zero. Next is provider-free
caller-capacity work; consumed drafts cannot be reused and unsupported-2024 remains unexecuted.

Local evidence: [baseline](../../benchmarks/results/planner_output_kind_boundary_2026-09-19/baseline.json),
[focused tests](../../benchmarks/results/planner_output_kind_boundary_2026-09-19/focused_checks.json),
[audit](../../benchmarks/results/planner_output_kind_boundary_2026-09-19/domain_audit.json),
[25-check review](../../benchmarks/results/planner_output_kind_boundary_2026-09-19/review.json),
[SDK request](../../benchmarks/results/planner_output_kind_boundary_2026-09-19/replayed_sdk_request.json),
[unchanged validation](../../benchmarks/results/planner_output_kind_boundary_2026-09-19/unchanged_validation.json),
[handoff](../../benchmarks/results/planner_output_kind_boundary_2026-09-19/handoff.json).
