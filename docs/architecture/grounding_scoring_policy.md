# Grounding Scoring Policy

## Purpose

This note captures the current direction for numeric grounding after the
`NAV_T1_071` close and the follow-up canaries `SKH_T1_060` and `KBF_T1_017`.

The main conclusion is:

- do not keep solving new failures by adding metric-specific local rules
- keep a small set of durable grounding principles
- absorb most future fixes into shared candidate scoring and acceptance policy

## Durable Principles To Keep

These are runtime grounding invariants, not benchmark hacks.

- `direct > derived`
  - if a direct row/value exists, do not prefer a reconstruction path
- `same-table > cross-table`
  - especially for `difference`, current/prior values should come from the
    same table and same row family whenever possible
- `period consistency`
  - explicit `2023/current` and `2022/prior` constraints should remain first-class
- `unit consistency`
  - `%`, `%p`, `KRW`, and `COUNT` should never be mixed opportunistically
- `canonical statement priority`
  - `balance_sheet`, `income_statement`, `cash_flow`, and `summary_financials`
    should outrank loose narrative and weak note hits when the query asks for a
    canonical statement value
- `aggregate/detail fit`
  - total-style questions should prefer aggregate/final/subtotal rows
  - detail-style questions may accept detail rows

## Narrow Exceptions To Avoid Growing

These may help while debugging but should not become the normal maintenance
pattern.

- `NIM always use section X`
- `pretax income may be reconstructed from net income + tax expense`
- qid-specific alias overrides
- one-off label exceptions added only to close one benchmark row
- metric-specific fallback formulas that bypass general grounding policy

## Shared Candidate Features To Elevate

The runtime should increasingly choose candidates through shared features rather
than metric-specific conditionals.

- `concept_match_score`
  - exact concept or semantic-label alignment
- `source_priority_score`
  - canonical statement > summary financials > notes > narrative
- `aggregation_score`
  - aggregate/final/subtotal/direct/detail fitness for the query
- `period_score`
  - exact year/current/prior alignment
- `table_coherence_score`
  - whether operands can be paired inside the same table / same row family
- `unit_family_score`
  - whether candidate units align with the required unit family
- `directness_score`
  - direct grounded row/value vs derived reconstruction

## Current Canary Interpretation

### `NAV_T1_071`

This canary closed because the runtime learned real general principles:

- direct structured row grounding
- same-family current/prior pairing
- aggregate evidence propagation

This is a positive example of a change that should generalize.

### `SKH_T1_060`

This canary now closes under the shared scoring changes. The runtime uses
canonical statement rows for the denominator instead of drifting into weak
note/detail rows.

Interpretation:

- this validates shared `source_priority + aggregation_score + directness`
  features
- this is a positive example that common scoring can replace metric-specific
  patching for ratio questions

### `KBF_T1_017`

This canary now closes under shared runtime rules and evaluator contracts.

Interpretation:

- this was closed without restoring `NIM`-specific helper hardcoding
- the winning changes were still general:
  - joint current/prior pair selection with same-cell reuse rejection
  - ontology-level surface contract for the concept, not a qid patch
  - evaluator support for unitless structured percent rows in runtime evidence
  - evaluator alias tolerance when `period + normalized value/unit` already agree
- this validates that percent multi-period rows can also be handled through
  shared scoring/acceptance plus shared evaluator contracts

## Preferred Refactoring Order

1. keep strengthening shared scoring so aggregate canonical statement rows
   outrank weak detail/note rows when the query asks for a total/current value
   This step already paid off for `SKH_T1_060`.
2. keep only a small number of hard guards
   - unit mismatch rejection
   - current/prior same-cell rejection
   - direct-over-derived acceptance
3. only add a narrow exception if the failure clearly cannot be expressed as a
   shared feature

## Practical Decision Rule

When a new numeric canary fails, ask this first:

`Can the failure be explained by a missing shared scoring or acceptance feature?`

If yes, fix it there first.

Only if the answer is clearly no should a metric-specific exception be added.
