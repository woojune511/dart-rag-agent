# Project Status

Last updated: 2026-09-15

## Current implementation

`FinancialAgent` on `codex/reviewed-compiler-selection-gate` now separates
request preservation, Compiler interpretation and deterministic source/execution
checks. Baseline: `d9c36d8d`.
[Boundary details and frozen controls](../architecture/request_source_boundary.md).

| Boundary | Current behavior |
| --- | --- |
| Request | Exact owned question spans, outputs and explicit source/display constraints; no source-name allowlist |
| Exposure / authority | Ranking selects bounded bundles; actual source conditions govern use of their visible union |
| Numeric interpretation | Compiler links requests to the selected cell's full axes or attached exact context; code validates linkage, not meaning |
| Model transport | CompilerResponseV2; selected-cell axes assembled by code, one outside-context quote with declared uses and owner-exposed addresses; no narrative expressions |
| Group / retry | Request-grounded output relationships, declared dependencies and physical-row constraints; one targeted retry, accepted bytes preserved |
| Display intent | Explicit request precedes source-first defaults; existing Compiler chooses nullable source display with request-based reason, no keyword classifier |
| Numeric reading | Required nullable comparison request ID; existing variables reference/target link exact owned instructions to sources and formula; no semantic auto-repair |
| Execution | V2 fingerprints; interpretation scope stays on proofs, never overwrites source/context facts; no free-label expression gate; units/physical constraints/explicit output relations retained |

Ranking factors and free subject/metric mismatch diagnostics no longer masquerade
as Compiler selection permissions. Exact filing metadata takes precedence over
local/company-looking text; different filing names cannot match by containment.
Narrative subject support remains separate from each claim's exact fact ranges.
Invalid source addresses stay invalid; lowering never guesses replacements.
Compiler exception messages are not copied into retry prompts or public diagnostics.

No parser/store/candidate-ID/hash redesign, extra runtime model call, source-store
mutation, dataset/evaluator change or HTTP/public-result change was included.

## Local verification

Python 3.13 comparison-binding focused **190/190**, import/topology/docs **24/24**,
domain audit **83 reviewed literals**, pycompile/diff passed. Full unittest
**1,706/1,706**, no skips (71.314s). Twelve new contracts use actual normalization,
direction-only pairs, owned request/source links, same-cohort/dependency retry and V2 proofs.
The 12 anonymous controls were frozen before source edits. Historical fixtures stay
byte-identical; test-only copies explicitly author new request/proof/transport fields.
An authored response is an execution witness, not a sampled model answer.
Eleven new numeric-transport contracts cover available fields, foreign/inexact
contexts, owner/input isolation, offline invalid-proof rejection and V2 tampering.
Real SDK count/generation serialization is tested with blocked sockets and mocked HTTP.
Schema sizes versus `dd61e466`: axis-only 3,477 → 2,309 bytes; one context
3,477 → 3,234; parsed located-context fixture 3,469 → 3,293. These are local UTF-8
schema sizes, not total request/token savings or measured model success.
Numeric instructions grow 2,890 → 3,420 UTF-8 bytes; schema reduction alone
does not imply a smaller complete request, especially for contextual inputs.
Those sizes precede display-intent clarification. Its six new contracts cover
initial/retry request guidance, actual normalization through final answer/ledger,
positive/negative/equal values, direct precision and query/program tampering.
One authored expression grows 16,474 → 17,062 prompt bytes and 4,151 → 4,454 schema
bytes; candidate fingerprint/permissions and one mock call are unchanged.
No new schema fields, classifier or semantic validator; no SDK-token/accuracy claim.
Comparison wiring adds one nullable request ID, not a quote or candidate role. One
fixture's local prompt/schema/response grows 298/387/43 UTF-8 bytes; one mock call, no retry.
The [latest exact-response replay](../../benchmarks/results/semantic_scope_isolation_2026-09-15/RESULTS.md)
uses eight saved cases with blocked sockets: numeric outputs 4→5, mock calls 10→8,
retries 2→0. Forward -10% now executes unchanged; reverse -10% remains wrong.
All source/raw response/initial prompt/schema/visible IDs and six other programs/output
bytes are unchanged. No live retry-reduction, semantic repair or new model sample.
Schema preparation errors now retain the original error class and scoped diagnostics,
with unavailable schema bytes marked null; they no longer become UnboundLocalError.

The earlier five-case provider-free boundary comparison passed in both versions
(before the subsequent bare-value and V2 numeric-transport changes):

| Measurement | Baseline `d9c36d8d` | Earlier boundary build |
| --- | ---: | ---: |
| Authored fixture cases | 5 | 5 |
| Mock Compiler invocations / retries | 6 / 0 | 6 / 0 |
| Prompt UTF-8 bytes | 208,427 | 134,135 |
| Schema UTF-8 bytes across calls | 59,832 | 37,115 |
| Provider / embedding / store writes | 0 | 0 |

Selected IDs and numeric/display output signature are identical
(`2ca7903e16772081eb5bed50489e7ce982fc83e020521b586983a200ab5880d5`).
Prompt/schema reductions are 35.6% / 38.0%, not SDK token or latency measurements.
Source-linked wrapper/name contrasts now execute without a literal-equality gate;
unlinked/foreign axes still fail. Structurally valid wrong interpretations remain
semantic negative controls. These local gates do not measure model semantic accuracy.

## Latest compiler-only evidence

The [reading/formula factorial](../../benchmarks/results/comparison_formula_factorial_2026-09-15/INTERPRETATION.md)
on clean `ff36d19e` uses four synthetic questions x four conditions x three samples.
Semantic correct: current **9/12**, current+formula **9/12**, minimum **12/12**,
minimum+formula **10/12**. Errors all reverse the temporal request; formulas pass 48/48.
Current runtime accepts 10/12 and 12/12; minimum ID/arithmetic is not V2 authority.
Two current drafts also violate input ownership. Wrong rationales prefer conventional
chronology over the request. Formula addition shows no benefit in this small sample.
Minimum jointly changes plan/instruction/schema burden, not one isolated cause.
Generation/count 48/48, retries/errors 0; estimate USD 0.74502 + count contingency
2.88 = accounted 3.62502 < 4.00, not invoice. Delegated manifest `2f4535a1...75cb3` consumed.
51 pre-call + six offline-review tests; two identical SDK rehearsals match actual bodies.
Runtime/predecessors unchanged. Four questions, not 48 independent/general/full-agent cases.
Earlier [plan-hint A/B](../../benchmarks/results/plan_metric_hint_compiler_2026-09-15/RESULTS.md)
retains structural 4/4 and original/neutral semantic 2/2 versus 1/2; no hint clearing.
The [preceding comparison probe](../../benchmarks/results/comparison_binding_compiler_2026-09-15/RESULTS.md)
retains 3/4 correct directions, an original reverse error and two correct explicit-reference
controls. Its consumed `b2a68ca0...ff0f0` and raw responses are not retroactively repaired.
The [prior numeric-reading run](../../benchmarks/results/numeric_reading_compiler_2026-09-15/RESULTS.md)
on `02c799a0` retains 3 correct / 1 wrong numeric, 1 appropriate / 2 excess abstentions
and 1 scope rejection. Its consumed `24deb343...d2141a` and original results are immutable.

The [earlier display-intent pair](../../benchmarks/results/display_intent_compiler_2026-09-15/RESULTS.md)
on `a2d89d40` remains structural **2/2**, separate semantic review **2/2**: reported
11.5% plus calculated 10% when both requested; null display/10% for calculation-only.
The [prior numeric successor](../../benchmarks/results/numeric_grounding_compiler_2026-09-15/RESULTS.md)
retains structural 3/3, separate semantic 2/3, including the old display error.
Its single-eligible-candidate lookup is not two-visible-row proof. Both manifests consumed.

The [earlier twelve-question probe](../../benchmarks/results/request_source_boundary_compiler_2026-09-14_v2/RESULTS.md)
and [interrupted-question continuation](../../benchmarks/results/request_source_boundary_remaining_2026-09-14/RESULTS.md)
remain immutable. Prior over-abstention and reverse-direction errors are separate
semantic issues. The earlier count 404's provider-side cause remains unestablished.
Bare-scalar catalog exposure preserves existing IDs, spans and table provenance;
it does not inject answers or change shared evaluation extraction.

## Historical evidence, not current-build acceptance

- Latest [subject-grounding full-agent run](../../benchmarks/results/subject_grounding_full_agent_2026-09-14/RESULTS.md)
  on `054c6b22`: 2/3 runtime complete, 3/5 outputs accepted, runtime errors 0,
  ledger 3/3 ok. Admission `af784682...a8f0` consumed; no new release claim.
- [Addressed compiler-only run](../../benchmarks/results/narrative_address_compiler_2026-09-14/RESULTS.md)
  on `9771417f`: 9/9 structurally complete and source-reviewed against pre-fixed
  criteria; not human gold, unseen holdout or current full-agent performance.
- [Independent pilot](../../benchmarks/results/independent_pilot_compiler_2026-09-10/README.md):
  7/12 runtime complete, 4/9 reference-scalar questions, all three narratives had
  a completeness/faithfulness concern in source review. Source-exposed, immutable.
- [Reviewed-case index](../evaluation/reviewed_case_evidence_status.md) and
  [experiment history](../history/experiment_history.md) retain earlier results,
  source/fixture provenance and their claim limits. No predecessor bytes were edited.

## Next work

- Preserve the bounded display-intent pair and its source/calculated provenance.
- Next isolate plan/instruction exposure from output-schema burden in provider-free
  intermediate inputs. The minimum arm is diagnostic, not a production V2 replacement.
  [Baseline controls](../../benchmarks/results/comparison_reading_baseline_2026-09-15/README.md)
  retain untested row-mirror/equal-value/Korean model cases. No automatic paid expansion.
- Preserve qualifiers, complete entity/group scope and independent topics; do not add
  alias/suffix/benchmark rules or infer semantic success from ledger integrity.
- Default `data/chroma_dart` remains incomplete and untouched. Acquisition ambiguity,
  whole-source consistency, retired helper deletion and formula-wide rounding
  propagation are separate tasks.

See [runtime contract](../architecture/agent_runtime_contract.md),
[code map](codebase_map.md), [checked topology](runtime_flow_roles.md) and Git history.
