# Narrative output partition review

Status: bounded planner-policy clarification implemented, 2026-09-12; baseline `3542bc6b`.
Only two planner instructions change; schema, runtime control flow and compiler stay intact.
Normative authority remains [runtime contract](agent_runtime_contract.md).

## Finding

The measured repetition is **semantic overlap between accepted outputs**, not lost
request text, a repeated API attempt, candidate duplication or a new factual error.
Four obligations are not inherently invalid: the frozen review permits equivalent
decomposition. The planner now receives an explicit decomposition preference; its effect
on independently generated output overlap is not yet measured.

| Boundary | Observed behavior | Consequence |
| --- | --- | --- |
| Planner | May separate a role and its conditions into different narrative outputs; original request references survive | Decomposition granularity changes call count and overlap opportunities |
| Compiler islands | Each sees active owner metadata and linked request text, plus the full question as context; no structured sibling responsibility map | A broad role reading can include a condition also assigned to another output |
| Claim validation | Checks IDs, quotes, subjects, numbers and scope, not semantic exclusivity between outputs | Faithful but overlapping claims remain valid |
| Final assembly | Renders validated owner text in obligation order; dedupes evidence identities separately, not narrative meaning | Repeated facts survive into the public answer and the same ledger artifact |

Source pointers:

- `PLANNING_POLICY.requirement_planner_prompt_template` in `src/config/retrieval_policy.py`
  now explicitly keeps an explanation and its qualifiers together, links their original
  request units, and retains independent topics without setting a fixed output count.
- `_build_llm_requirement_plan` in `src/agent/financial_graph_planning.py` preserves the
  model's obligations; code did not split the measured plan after generation.
- `semantic_compilation_scope_v1` in `src/agent/financial_graph_calculation.py` projects
  active owners only. `context_only` restricts output IDs, not provably exclusive meaning.
- `project_narrative_claims` in `src/agent/financial_program_projection.py` joins claim
  text and dedupes evidence links, without silently discarding repeated assertions.
- `_render_semantic_program_answer` in `src/agent/financial_calculation_execution.py`
  appends narrative outputs; `assemble_semantic_execution_result` and the real final/
  ledger nodes preserve that text rather than running another semantic synthesizer.

## Evidence and counterexamples

[Saved-response characterization](../../benchmarks/results/narrative_output_partition_2026-09-12/README.md)
replays the prior ten raw SDK responses with no external network. Requests, requirements,
programs/validation, execution envelope, final answers and ledgers are identical.
All three measured answers have **zero exact rendered-claim duplicate pairs**. The third
answer repeats two facts using compound/shorter or rephrased statements, so exact-string
dedupe would not repair it. The original paid result remains 3/3 under its narrow criteria.

Seven baseline tests in `tests/test_narrative_output_partition.py` characterize:

1. Same question/source, one authored output versus two: both preserve requirements;
   the split plan can repeat a condition and uses two compiler calls rather than one.
   Subject names, years and scripts vary; no reviewed company/question/answer is a fixture.
2. Two distinct required facts can use the **same candidate, bundle, full quote and span**.
   Removing by origin equality would delete valid content.
3. Same request ID, source and raw claim text can describe **different subjects**.
   Removing by shared request, raw text or source would erase one subject's answer.
4. Exact repetition currently survives both within one binding and across outputs.
   This is an explicit open-limit control, not a desired future behavior or score oracle.
5. A rephrased condition can overlap without exact-string equality or containment.
6. Declared coupling changes call grouping but does not mechanically remove overlap.
   This does not authorize adding coupling merely to combine shared-source outputs.
7. A quote repair preserves the other island's accepted bytes and its existing overlap;
   retry is not a cross-output semantic edit pass and cannot be used as one.

These authored-response assertions describe current mechanics. They may change with a
reviewed replacement contract; do not preserve the defect just to keep a characterization
assertion green. None measures whether an LLM will generate the authored better plan.

## Implemented planner policy

The **planner's semantic decomposition policy** uses only existing fields/calls:

- Keep an explanation and conditions that qualify that same explanation in one narrative
  output, with all relevant original `request_unit_ids` linked to it.
- Keep genuinely independent requested topics/subjects as separate outputs. Same entity,
  sentence, source, or request ID alone is not a merge rule. Do not force a fixed count.
- Do not turn a modifier into a new standalone output solely because it occupies another
  request unit. Equally, do not discard explicitly requested independent explanations.
- Retain code ownership/coverage/visibility/quote checks and the current retry boundary.
  No new role enum, domain keyword score, semantic validator or additional model call.

Two additional authored-response tests check that the real planner prompt carries this
policy and that both a qualified explanation plus an independent same-subject topic,
and two subjects sharing a condition preserve every linked request through the real
compiler/executor/final/ledger path. The missing prompt clause was first reproduced
as a failing test. Authored output counts do not predict a model's decomposition.

Only if overlap persists between legitimately independent outputs should a later bounded
change consider a **read-only sibling responsibility projection** for the compiler. That
would describe output ownership, not expose sibling candidate IDs or accepted answers,
authorize bindings, create coupling edges, or weaken retry isolation. It is not implemented.
Do not add this projection or a final LLM synthesis pass preemptively for one small probe.

Post-hoc deletion by candidate/source/span/request-ID or substring is rejected by the
counterexamples above. An exact presentation-only dedupe is a separate possible contract,
not the current case's fix; it would need to retain owner/evidence coverage and scoped
distinctions even when text is displayed once.

## Validation and limits

Output-partition tests 9/9 and related request/claim/retry suites 51/51 pass. Current
broader gates are recorded in [project status](../overview/project_status.md). No provider,
retrieval, embedding, store mutation or new admission. The prior saved-response replay
and hash inventory describe the unchanged measured predecessor, not the updated prompt.
The old admission remains consumed; do not reuse it or call a saved response a new model
choice. A separately approved bounded measurement must check retained independent topics,
all requested conditions, call counts and overlap, without requiring a fixed decomposition.
Local tests do not establish reduced repetition, fluency, unseen-source generalization,
real retrieval performance or release readiness.

The [five-case successor preparation](../../benchmarks/results/narrative_partition_pipeline_2026-09-12/README.md)
now fixes the original three inputs/criteria/catalogs plus two controls on `47fafc12`.
Two independent no-call processes match; model improvement remains unmeasured. New
manifest `9b0d85fb...34776f` proposes one bounded Flash → Pro run under USD 0.80,
pending explicit approval. No further runtime/prompt/schema change or provider call.
