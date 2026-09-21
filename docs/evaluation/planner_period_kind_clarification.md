# Planner period-kind instruction clarification

The [six-question model probe](measurement_coverage_probe_result.md) already
received the coverage instructions and schema, but four responses chose an
unnecessary unresolved period or invented calendar endpoints. This follow-up
clarifies that choice in the existing Planner prompt and field descriptions.
It changes no fields, validation rules, normalization, source selection or calls.

## Interpretation boundary

- Choose the kind from the precision requested, before considering source
  availability. A named year uses year and coverage; an explicitly anchored
  relative year uses anchor_year, year_offset and coverage.
- Whole_year requires the complete named year. Within_year permits measurements
  inside that year, including a point or shorter period, without requiring a
  single exact full-year interval.
- A known year and coverage need no fiscal start/end dates. Missing endpoints
  alone do not require unresolved, and do not justify January-December dates.
- Exact requested dates and inclusive intervals retain their endpoints and
  point-versus-interval shape. Truly uninterpretable constraints remain unresolved.
- Owned request references, original text, independent comparison-input periods
  and the separation from report selection remain unchanged. A correct rationale
  does not replace a correct operative constraint.

Only the generic Planner policy and two model field descriptions change. No case,
company, metric or failed question is added to the instructions. Source matching
still verifies the existing period contract independently after retrieval.

## Provider-free verification

Clean baseline **`d2b73b8b`**. Before and after use the installed SDK with blocked
network connections, the exact six saved raw responses, and the original queries.
All **6/6** normalized plans and scope plans remain identical. The four period
errors and the separate c04 consolidation defect remain observable; no saved
answer is repaired and the original semantic score remains **2/6**, coverage **0/4**.

Before-edit SDK bodies exactly reproduce the six original live request bodies.
After-edit bodies differ only in the period instruction block and three generated
schema descriptions (the shared coverage description appears in two branches).
Removing descriptions leaves identical schemas; fields, required lists, enums and
validation limits are unchanged. Model, reasoning, limits and all other input are
identical. Each serialized body grows **1,537 UTF-8 bytes**: prompt text +843 and
schema +691, plus JSON escaping. These are not token counts or billing estimates.

**107/107 focused tests**, domain audit **83**, import/topology/documentation and
syntax/diff checks pass. The earlier **2,213/2,213** full suite is historical and was
not rerun for description-only edits. The initial offline capture used an unbound
HTTP mock incorrectly; fixing the mock binding produced the verified before/after
captures without changing production or saved responses. Its failed log is kept.

All **12,977 predecessor files**, **174 unrelated source files**, **24 original
store files** and local settings retain hashes. Packet
`benchmarks/results/planner_period_kind_clarification_2026-09-22` remains ignored.
Added provider calls/accounting **0**; shared **19.54154943/20.32**, remaining
**0.77845057**, pending zero. No new model-accuracy result is claimed.

This is an instruction hypothesis, consistent with OpenAI's distinction between
structured output and correct content in its
[handling-mistakes guidance](https://developers.openai.com/api/docs/guides/structured-outputs#handling-mistakes).
The subsequent [scope-ownership correction](consolidation_scope_ownership.md)
addresses the ordinary-word override separately. Any later model comparison needs
fresh admission and frozen criteria; this instruction change still has no new
model result, and the consumed probe's four period failures remain unchanged.
