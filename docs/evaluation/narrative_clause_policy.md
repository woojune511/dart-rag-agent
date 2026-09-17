# Narrative clause fidelity instruction

Applied 2026-09-18 from clean `891c9e80`. The [reviewed proposal](narrative_paraphrase_diagnosis.md)
is now part of `src/config/retrieval_policy.py::_COMPILER_NARRATIVE_INSTRUCTIONS`.
The production diff adds one instruction: every claim sentence/clause must retain
the selected evidence's action/object relationships, conditions, degree, negation
and tense. Paraphrasing remains allowed; unnecessary restatement must not add meaning.

This is a generic Compiler instruction, not a semantic validator. No financial
vocabulary, case names, source permission, schema, execution logic, model setting
or additional call changes. Both general and narrative-only templates grow by
**418 UTF-8 bytes**, not a measured token estimate.

## Provider-free delivery and compatibility

The [verification packet](../../benchmarks/results/narrative_clause_policy_2026-09-18/)
freezes the predecessor evidence and baseline templates. The installed templates
exactly equal the earlier reviewed proposal. With external sockets blocked:

- The saved paid narrative response compiles once under each instruction version.
  Its original accepted program and execution stay unchanged.
- Authored narrative source-error and general numeric schema-error cases exercise
  initial and existing repair calls. Both actual template selections receive the
  instruction once per prompt; the rest of each prompt is byte-identical.
- Across those three paired cases, response schemas, source/input values, programs,
  validations, executions and repair counts are equal. Two repair examples retain
  their existing one-repair behavior; this is not a reduction in model retries.
- Sixteen frozen anonymous responses reproduce the prior candidate prompts,
  schemas and results exactly. Eight faithful and eight unsupported statements
  remain structurally accepted: source attachment still does not prove meaning.

These checks use **26 fixed-response adapter invocations**, not provider calls or
new model answers. They establish delivery and compatibility, not improved model
compliance, preserved recall, or a repaired historical answer. The paid
[search/display result](search_display_current_app.md) retains its fidelity concern.

## Gates and preservation

Post-adoption focused tests **40/40**, full suite **2029/2029**, and updated-document
checks **4/4** pass without skips or external connection attempts. The full suite
includes import-side-effect and topology contracts. Domain audit passes with
**83** reviewed literals; source compilation and `git diff --check` pass.
No new persistent test mirrors the instruction text; the existing behavior
contracts and captured delivery comparisons provide the local evidence.

The frozen patch's CRLF context did not apply to the LF source; both unsuccessful
Git apply commands left source bytes intact. The initial `focused.json` is therefore
a **pre-adoption** 40/40 baseline. Direct insertion preserved the reviewed wording;
`focused_adopted.json` and the full suite verify the actual modified source.

Only the policy file changes among **173** source files; **172** retain their hashes.
All **2238** predecessor artifacts, **24** store files, runtime owners and local
settings remain unchanged. Historical packets and consumed manifests are intact.
Provider/count/embedding calls and added cost are **0**. Shared accounting remains
**7.69277754 / 8**, remainder **0.30722246**, pending 0; not invoice data.

Next: assess the budget feasibility of a fresh Compiler semantic check with the
frozen anonymous controls and current complete request/output/count bounds,
provider-free. A new model response is needed to assess effectiveness. Do not
silently reduce bounds, change models, create an admission, spend the remainder
or increase the cap during that feasibility review.
