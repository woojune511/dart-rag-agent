# Narrative subject display boundary

Status: provider-free characterization and diagnostic prototype, **not a runtime contract change**.
The current [runtime contract](agent_runtime_contract.md) still requires source-copied subjects.

## Observed boundary

`financial_program_projection.render_narrative_claim` already folds display whitespace with
`" ".join(text.split())`. `financial_narrative_claims` independently requires the model's
subject string to occur verbatim in one selected source range. A copied line-broken name
and its single-line display therefore render identically but have different validation outcomes.
The selected source text, piece addresses and offsets are unchanged; this is not retrieval loss.

Five [current-path tests](../../tests/test_narrative_subject_display_boundary.py) cover eight
whitespace layouts, unchanged evidence/offsets, non-whitespace name changes, unavailable
tails and an existing semantic negative. Related boundary/retry tests pass **29/29**.

## Recommended narrow contract

Keep the model statement, source evidence and rendered label separate:

- Preserve the raw model `subject` and its explicit source selections. Do not overwrite
  captured programs or ask the model to produce character offsets or another role enum.
- Resolve owner/requirement permissions, source attachment and physical partitions first.
  Only an already selected, exact contiguous range can supply subject support.
- Keep existing exact matches unchanged. If exact containment fails, compare whitespace
  layout only and map the matching display characters back to their original source spans.
  Preserve every non-whitespace character, case, punctuation and internal word boundary;
  do not join words, resolve aliases, strip suffixes or search unselected source text.
- A new layout-only match needs one unambiguous source occurrence. Record the original
  `source_subject`, exact source-surface character span (not XML byte offsets) and provenance
  in validator-owned trace, alongside the unchanged model subject. Multiple occurrences
  require a narrower model selection or withholding.
- Render from the validated label using the existing display projection. The source quote
  and its bytes remain untouched. Separate selections/cells are never joined into a name.

The [diagnostic prototype](../../benchmarks/results/subject_display_boundary_2026-09-14/README.md)
demonstrates that mapping. It is not imported by runtime. Its counterfactual temporarily
substitutes the recovered raw name into an in-memory model-response copy so the unchanged
validator/executor can test the proposal. **That substitution is not the proposed production
implementation**: production must retain the actual model statement and a separate witness.

## Interpretation limits

Literal or whitespace-equivalent containment does not establish complete entity/group scope.
The existing path accepts a shorter source-copied prefix of a longer group name; the new
test records this as a semantic negative, not a successful identity check. Layout matching
does not solve it, and no claim that omitted qualifiers are generally detected is warranted.
The compiler still interprets requested identity, attribution and completeness. This proposal
must not add a keyword-based entity-boundary classifier or treat containment as entailment.

## Implementation boundary, not yet done

One small subject-grounding helper should serve addressed validation and retry diagnostics.
Update the policy/schema description and normative contract together, without a new model
field/call or a production program-rewriting fallback. Keep existing exact-path program and
trace bytes stable; attach the extra witness only to newly admitted layout-only support.
Owner/requirement restrictions, source partitions, fact-local number authority, immutable
compile validation, V2 execution checks, public HTTP shape and all source/candidate IDs stay intact.

Gate the change with anonymous layout/ambiguity/name-change/authority tests, the remaining
semantic negative, and unchanged accepted outputs. Saved-response replay is local execution
evidence, not new model performance. The consumed paid result remains **3/4 pre-fixed criteria**;
no further paid run, source-store mutation or full-agent release claim is part of this work.
