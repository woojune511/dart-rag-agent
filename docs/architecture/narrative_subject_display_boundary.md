# Narrative subject display boundary

Status: implemented in addressed validation and retry diagnostics; **provider-free validation only**.
The normative authority is the [runtime contract](agent_runtime_contract.md).

## Observed boundary

`financial_program_projection.render_narrative_claim` already folds display whitespace with
`" ".join(text.split())`. The predecessor validator independently required the model's
subject to occur verbatim in one selected range, rejecting a single-line display of an
otherwise correctly selected line-broken name. The shared subject-grounding helper now
keeps exact behavior and separately witnesses unique whitespace-only correspondence.
The selected source text, piece addresses and offsets are unchanged; this is not retrieval loss.

[Contract tests](../../tests/test_narrative_subject_display_boundary.py) cover eight layouts,
source-character offsets, duplicate versus ambiguous positions, owner/requirement/cell limits,
fact-local numbers, same-cohort retry, accepted bytes and V2 source/witness tampering.

## Implemented narrow contract

Keep the model statement, source evidence and rendered label separate:

- Preserve the raw model `subject` and its explicit source selections. Do not overwrite
  captured programs or ask the model to produce character offsets or another role enum.
- Resolve owner/requirement permissions, source attachment and physical partitions first.
  Only an already selected, exact contiguous range can supply subject support.
- Keep existing exact matches unchanged. If exact containment fails, compare whitespace
  layout only and map the matching display characters back to their original source spans.
  Preserve every non-whitespace character, case, punctuation and internal word boundary;
  do not join words, resolve aliases, strip suffixes or search unselected source text.
- A layout-only match needs one unambiguous surface/span; overlapping links to the same
  physical location count once. Only these new matches add `claim_readings.subject_grounding`:
  `match_kind`, unchanged `model_subject`, exact `source_subject`, `source_subject_span`
  (Python characters, not XML bytes) and `evidence_index` into `subject_evidence` provenance.
  Multiple locations yield `ambiguous_narrative_subject` and same-cohort repair, not exclusion.
- Render from the validated label using the existing display projection. The source quote
  and its bytes remain untouched. Separate selections/cells are never joined into a name.

The same helper serves structured-error-targeted retry diagnostics. Literal
`contains_declared_subject` is unchanged; optional `subject_grounding` reports layout-only
correspondence or ambiguity within those same selections. Invalid addresses expose only
a resolution code. Diagnostic witness indices refer to the diagnostic `selections` list.
The older [prototype](../../benchmarks/results/subject_display_boundary_2026-09-14/README.md)
remains immutable and unimported; its counterfactual model-text substitution is not production.

## Interpretation limits

Literal or whitespace-equivalent containment does not establish complete entity/group scope.
The existing path accepts a shorter source-copied prefix of a longer group name; the new
test records this as a semantic negative, not a successful identity check. Layout matching
does not solve it, and no claim that omitted qualifiers are generally detected is warranted.
The compiler still interprets requested identity, attribution and completeness. This change
must not add a keyword-based entity-boundary classifier or treat containment as entailment.

## Validation and remaining boundary

Policy/schema descriptions and normative contracts change together, with no new model
field/call or program-rewriting fallback. Exact-path programs and traces remain unchanged.
Owner/requirement restrictions, source partitions, fact-local number authority, immutable
compile validation, V2 execution checks, public HTTP shape and all source/candidate IDs stay intact.

[Saved-response replay](../../benchmarks/results/subject_display_grounding_2026-09-14/README.md)
uses all four actual responses without editing model JSON. Only the line-break case changes
acceptance; other three whole programs/validations/executions and all previously accepted
outputs remain byte-identical. Three supported outputs complete, one faithful withholding stays.
This is local execution evidence, not new model performance. The consumed paid result remains
**3/4 pre-fixed criteria**. No paid rerun, store mutation or full-agent release is included.
