# Project Status

Last updated: 2026-09-22

## Current implementation

`FinancialAgent` on `codex/reviewed-compiler-selection-gate` now separates
request preservation, Compiler interpretation and deterministic source/execution
checks. Baseline: `d9c36d8d`. The [portfolio completion scope](portfolio_scope.md) now prioritizes a simple RAG comparison; the unused alternate narrative answer/selection path is removed.
[Boundary details and frozen controls](../architecture/request_source_boundary.md).

| Boundary | Current behavior |
| --- | --- |
| Request | Exact owned question spans, outputs and explicit source/display constraints; no source-name allowlist |
| Exposure / authority | Bounded bundles; numeric own-axis and narrative same-surface request-term hints rank relevance without changing identity or source permissions |
| Numeric interpretation | Compiler links requests to the selected cell's full axes or attached exact context; code validates linkage, not meaning |
| Model transport | CompilerResponseV2 with compact JSON by default; exact source/request addresses; bounded operation steps with inline quantity/proof and backward-only references, code-computed binding_count; separate prose subject/metric support; no narrative expressions |
| Group / retry | Request-grounded relationships with one shared declaration and explicit member refs; independent local proofs; one targeted retry with accepted bytes/declarations preserved |
| Display intent | Explicit request precedes source-first defaults; existing Compiler chooses nullable source display with request-based reason, no keyword classifier |
| Numeric reading | Required nullable comparison request ID; existing variables reference/target link exact owned instructions to sources and formula; no semantic auto-repair |
| Execution | V2 fingerprints; interpretation scope stays on proofs, never overwrites source/context facts; no free-label expression gate; units/physical constraints/explicit output relations retained |

Ranking factors and free subject/metric mismatch diagnostics no longer masquerade
as Compiler selection permissions. Exact filing metadata takes precedence over
local/company-looking text; different filing names cannot match by containment.
Narrative subject support remains separate from each claim's exact fact ranges.
Invalid source addresses stay invalid; lowering never guesses replacements.
Compiler exception messages are not copied into retry prompts or public diagnostics.

No product parser/store/candidate-ID/hash redesign, extra runtime model call or
source-store mutation. New comparison tooling/data are separate from product behavior.

## Current verification

The [shared-evidence workflow comparison](../evaluation/portfolio_workflow_comparison.md) is prepared: four exposed development questions, eight frozen chunks each, shared Terra settings. It compares text RAG with structured metadata plus Planner/Compiler; it is not a pure component ablation or production-retrieval evaluation. Full unittest **2,266/2,266** (73.490s), including 11 new comparison contracts; domain audit **66**. Quality evaluation **NOT_RUN**; no paid calls. Recorded USD0.29082457 remaining does not fund the proposed USD6 cap (conservative envelope USD5.96608). Final holdout is not yet frozen.

Portfolio cleanup: retired narrative generation/validation, dividend/entity-specific answer assembly, alternate narrative selection, and their dedicated models/policies/tests are removed. Runtime/config is **3,723 lines smaller** (70 added/3,793 removed). Full unittest **2,255/2,255** (79.243s), runtime domain audit **66**, import/topology/documentation gates and focused contracts pass. All **15,050** protected predecessor files and local `.env` retain their hashes. The public Planner/Compiler path and source/calculation guards remain. Paid calls, fresh ingest and new accuracy evaluation: **NOT_RUN**.

Prior [real-question Planner evidence](../evaluation/planner_real_questions_result.md) remains period1/2, scope2/2, combined1/2. Cash year-end meaning was lost; unchanged-cell replay2/2 does not prove semantic success. Accounted USD20.02917543/20.32, remaining0.29082457, pending0; no new spend or funding. This is a documented limitation, not the automatic next prompt patch.
Earlier source-choice tests cover input enums, source-kind fields, mixed/dependency/empty spaces,
stable refs/authority; import/topology/docs 24, audit 83, pycompile/diff pass. Prior contracts use
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

The [six-control run](../../benchmarks/results/source_choice_controls_2026-09-15/RESULTS.md)
on clean `386cf867`: six first responses, current schema; runtime and separate meaning **6/6**.
Row-mirror/equal-value/Korean pairs each 2/2; six counts/generations, errors/retries 0.
Manifest `55029ef1...3000e0` consumed; USD 0.1201475 + count allowance 0.36 < 0.75, not invoice.
The [preceding schema A/B](../../benchmarks/results/source_choice_schema_2026-09-15/INTERPRETATION.md) retains runtime 5/6→6/6 and meaning 3/6→5/6.
Its temporal error remains; these single-sample controls do not establish general accuracy or its repair.
Prior [naming-only comparison](../../benchmarks/results/requirement_id_ablation_2026-09-15_v2/INTERPRETATION.md) retains both gates 2/4 each; no naming remedy.
The [previous input deletion](../../benchmarks/results/compiler_instruction_plan_ablation_2026-09-15/INTERPRETATION.md)
retains 14 responses, one 503, nine not run; both arms 5/7. Neither probe is general/full-agent proof.
The [preceding factorial](../../benchmarks/results/comparison_formula_factorial_2026-09-15/INTERPRETATION.md)
retains current/current+formula/minimum/minimum+formula 9/12, 9/12, 12/12, 10/12.
No formula benefit observed; minimum jointly changes input/schema and is not V2 authority.
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

- Preceding Google [subject-grounding full-agent run](../../benchmarks/results/subject_grounding_full_agent_2026-09-14/RESULTS.md)
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

1. Fund and run the prepared four-case development comparison once; preserve partial results on failure and review correctness/source support separately from execution status and resource cost.
2. Keep known retrieval and meaning failures visible, including the missing exact cash source; do not insert gold evidence or question-specific corrections into shared inputs.
3. Use the development comparison for at most one broadly useful improvement; do not add a rule for every answer miss. Source-integrity defects remain bugs.
4. Complete one final evaluation and a reproducible demo/report, including negative results and unsupported scope. See [portfolio scope](portfolio_scope.md) for the stopping point.

No paid comparison or store mutation was performed. The year-end miss, selected NAVER2023 filing and inactive default-store mismatch remain limitations. The source graph contains two filings, but this comparison selects one. Historical evidence is linked above; current work is no longer the accumulated per-error repair queue.
