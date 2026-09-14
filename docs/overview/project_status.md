# Project Status

Last updated: 2026-09-14

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
| Model transport | Kind-specific nested output schemas, short source addresses, one explicit lowering function; no narrative expressions |
| Group / retry | Request-grounded output relationships, declared dependencies and physical-row constraints; one targeted retry, accepted bytes preserved |
| Execution | Immutable visibility plus V2 content/program/validation fingerprints; units, arithmetic, source-first display and ledger ownership retained |

Ranking factors and free subject/metric mismatch diagnostics no longer masquerade
as Compiler selection permissions. Exact filing metadata takes precedence over
local/company-looking text; different filing names cannot match by containment.
Narrative subject support remains separate from each claim's exact fact ranges.
Invalid source addresses stay invalid; lowering never guesses replacements.
Compiler exception messages are not copied into retry prompts or public diagnostics.

No parser/store/candidate-ID/hash redesign, new model call, provider run, source-store
mutation, dataset/evaluator change or HTTP/public-result change was included.

## Local verification

Python 3.13 integration gate: **1,650/1,650 unittest tests passed**, no skips
(58.540s). Focused boundary tests **118/118**, reading/presentation cleanup **20/20**,
import/topology/docs **24/24**, domain audit **83 reviewed literals**, pycompile
**70 changed Python files**, checked topology and `git diff --check` passed.
The 12 anonymous controls were frozen before source edits. Historical fixtures stay
byte-identical; test-only copies explicitly author new request/proof/transport fields.
An authored response is an execution witness, not a sampled model answer.

The five-case provider-free baseline/current comparison passed in both versions:

| Measurement | Baseline `d9c36d8d` | Current |
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

## Current-build anonymous Compiler probe

Under the user's delegated instruction to proceed without another approval prompt,
one [12-question probe](../../benchmarks/results/request_source_boundary_compiler_2026-09-14_v2/RESULTS.md)
ran on `ad51fa61`, with an assistant-selected USD 1.60 ceiling. Nine questions
completed: seven structurally accepted and source-reviewed correct, one explicit
over-abstention, and one wrong comparison direction in a structurally rejected draft.
The tenth stopped before generation at Google `countTokens` HTTP 404 `NOT_FOUND`;
two were unattempted. The exact provider-side cause is unestablished, not a runtime
or credential diagnosis. This is not a complete 12-case or full-agent pass.

Generation calls 14 / count attempts 15; five internal retries, no runner restart.
All retries involved redundant invalid context links (nine validation errors),
four repaired and one withheld. Generation estimate USD 0.257575; separate count
contingency USD 0.90, accounted total USD 1.157575, not billing. The source-display
pair had an independently observed pre-run gap: bare `110`/`100` were not candidates;
only `11.5%` was registered. No operands, expected answers or runtime fixes were
injected. Manifest `aa88c29e...ccb163` is consumed. Two real-SDK socket-blocked
rehearsals were byte-identical, and the 32 focused source/wire/admission tests passed.

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

- Reduce duplicate axis/context reference choices through the actual available
  source kinds, without bypassing provenance validation. Treat over-abstention and
  comparison direction as separate model-reading errors, not string/alias rules.
- Characterize bare-value extraction generally; retain the unattempted contrasts.
  Any further provider work needs a new bounded successor; no automatic paid rerun.
  Store-fixed full-agent validation remains later work, not established by this probe.
- Preserve qualifiers, complete entity/group scope and independent topics; do not add
  alias/suffix/benchmark rules or infer semantic success from ledger integrity.
- Default `data/chroma_dart` remains incomplete and untouched. Acquisition ambiguity,
  whole-source consistency, retired helper deletion and formula-wide rounding
  propagation are separate tasks.

See [runtime contract](../architecture/agent_runtime_contract.md),
[code map](codebase_map.md), [checked topology](runtime_flow_roles.md) and Git history.
