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
| Execution | Immutable visibility plus V2 content/program/validation fingerprints; units, arithmetic, source-first display and ledger ownership retained |

Ranking factors and free subject/metric mismatch diagnostics no longer masquerade
as Compiler selection permissions. Exact filing metadata takes precedence over
local/company-looking text; different filing names cannot match by containment.
Narrative subject support remains separate from each claim's exact fact ranges.
Invalid source addresses stay invalid; lowering never guesses replacements.
Compiler exception messages are not copied into retry prompts or public diagnostics.

No parser/store/candidate-ID/hash redesign, extra runtime model call, source-store
mutation, dataset/evaluator change or HTTP/public-result change was included.
The separately delegated compiler-only verification is recorded below.

## Local verification

Python 3.13 integration gate: **1,678/1,678 unittest tests passed**, no skips
(44.240s). Display-intent/numeric/source/retry/compiler/admission focused tests **90/90**,
import/topology/docs **24/24**, domain audit **83 reviewed literals**, pycompile,
checked topology and `git diff --check` passed.
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

The [two-question display-intent successor](../../benchmarks/results/display_intent_compiler_2026-09-15/RESULTS.md)
ran once on clean `a2d89d40` under the user's no-additional-approval delegation.
Source/execution acceptance is **2/2**; separate Codex source-semantic review is
**2/2**, not a blended rate. Generation 2 / count 2, retries 0, provider errors 0.
On the unchanged source, both questions bind current 110 / previous 100 and compute
forward growth 10%. The model selects source 11.5% with separate calculated 10%
when both are requested; calculation-only selects null source display and primary
10%. These choices appear in raw responses, with request-based reasons and no
fabricated rounding cause; lowering does not correct semantic choices.

Estimated generation USD 0.039515 (without cache discount), count contingency
USD 0.12, accounted total USD 0.159515 below assistant-selected USD 0.50.
Not invoice/count tariff observations. Manifest `67788de2...2c09ff` is consumed.
Focused tests 39/39 and two byte-identical socket-blocked SDK receipts preceded
calls. Runtime and bound files were verified unchanged; each prior case and criterion
is canonically byte-identical. Each request grew 892 SDK bytes / 120 input tokens.
Previously exposed synthetic fixed plans only: not unseen/general accuracy, isolated
causal ablation, planner/retrieval/full-agent/final-answer/HTTP/ledger acceptance.

The [prior numeric successor](../../benchmarks/results/numeric_grounding_compiler_2026-09-15/RESULTS.md)
on `51330fe5` remains structural **3/3**, separate semantic review **2/3**. Its
calculation-only display failure is unchanged, not retroactively marked correct.
The separate-row lookup had only one eligible candidate, not two-visible-row proof.
Manifest `8998a347...0a87d3` is also consumed; neither run is automatically repeated.

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

- The display-intent pair now has bounded model evidence. Preserve both requests,
  source/calculated provenance and semantic negatives; do not broaden its claim.
- Reproduce over-abstention/comparison direction provider-free from existing traces
  before choosing the next generic change. These remain separate semantic errors;
  this two-case run does not establish context-rich accuracy or retry improvement.
  Further provider work needs a new bounded successor; no automatic paid rerun.
  Store-fixed full-agent validation remains later work, not established by this probe.
- Preserve qualifiers, complete entity/group scope and independent topics; do not add
  alias/suffix/benchmark rules or infer semantic success from ledger integrity.
- Default `data/chroma_dart` remains incomplete and untouched. Acquisition ambiguity,
  whole-source consistency, retired helper deletion and formula-wide rounding
  propagation are separate tasks.

See [runtime contract](../architecture/agent_runtime_contract.md),
[code map](codebase_map.md), [checked topology](runtime_flow_roles.md) and Git history.
