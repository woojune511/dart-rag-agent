# Financial Ontology Concept-Only Draft

This draft is a deliberate reset from the benchmark-shaped `metric_families`
direction explored in `financial_ontology_v2.draft.json`.

The goal is to keep ontology small, general, and reusable across unseen DART
questions.

## Core judgement

The ontology should contain:

- canonical financial concepts
- reusable concept groups for common shorthand
- aliases and keywords for those concepts
- statement / section priors that are broadly true across DART filings
- lightweight binding preferences such as:
  - prefer `notes` for `사채`
  - prefer `aggregate` over `detail`
  - prefer `current` period when the question does not say otherwise

The ontology should **not** contain:

- benchmark-specific metric families
- question-shaped composite metrics
- hard-coded numerator / denominator combinations for every evaluation item
- one-off formulas that are really planner responsibilities
- per-metric direct-plan / fallback-plan recipes that belong in runtime control
  flow rather than reusable DART knowledge

## What to keep

These parts of the current ontology direction are still good:

- `concepts`
  - `부채총계`, `자본총계`, `유동자산`, `유동부채`, `유형자산`, `무형자산`, `사채` ...
- `concept_groups`
  - `tangible_and_intangible_assets`
  - `borrowings`
- `binding_policy_defaults`
  - generic defaults for `value_role`, `aggregation_stage`, `period_focus`, `consolidation_scope`
- concept-level `preferred_statement_types`
- concept-level `preferred_sections`
- concept-level `binding_policy`

These express reusable DART knowledge rather than benchmark recipes.

## What to delete or de-emphasize

The following are the main over-engineered parts of the current V1/V2 ontology:

- metric families such as:
  - `rnd_ratio`
  - `operating_margin`
  - `debt_ratio`
  - `current_ratio`
  - `asset_debt_burden_ratio`
- metric-local `formula_template`
- metric-local `components`
- metric-local `row_patterns`
- metric-local `query_hints` and `retrieval_keywords` when they mostly duplicate concept aliases

Those fields make ontology behave like a benchmark answer book instead of a
general DART knowledge layer.

## What should move to the planner

The planner should infer at runtime:

- which concepts are mentioned or implied by the question
- whether the user wants:
  - `ratio`
  - `difference`
  - `growth_rate`
  - `sum`
- which concepts belong in numerator / denominator
- whether multiple subtasks are needed
- whether the question needs raw lookup materials in addition to derived arithmetic

Example:

Question:

`2023년 연결기준 부채비율과 유동비율을 각각 계산해 줘.`

The ontology does **not** need to know `debt_ratio` and `current_ratio` as
first-class benchmark metrics. The planner can infer:

- task 1: ratio(total_liabilities, total_equity)
- task 2: ratio(current_assets, current_liabilities)

Ontology only needs to help bind:

- `total_liabilities`
- `total_equity`
- `current_assets`
- `current_liabilities`

The planner should also be free to gather both:

- raw values the user explicitly asks to see
- derived values needed for arithmetic

For example, a question such as:

`2023년 A값을 보여주고 전년 대비 증감액을 계산해 줘.`

should be decomposed by the planner into material-gathering tasks such as:

- `lookup(A, current_period)`
- `difference(A current_period, A prior_period)`

rather than forcing ontology to encode that query as a dedicated metric family.

## Direct-first is a runtime policy, not a metric recipe

The current architectural direction deliberately avoids turning ontology into a
catalog of:

- direct-lookup-enabled metrics
- per-metric fallback formulas
- graph branching recipes

Why:

- that would re-inflate ontology into a benchmark answer book
- it couples reusable DART knowledge to transient control-flow design
- it weakens the boundary between ontology, planner, and runtime binder

Instead, ontology should provide:

- concept aliases
- concept groups
- preferred statement / section priors
- lightweight binding preferences

and the runtime should decide:

- whether a direct candidate is acceptable
- whether the system should fall back to derived reconstruction
- whether planner re-entry is needed to gather more material

This split was validated concretely on `NAV_T1_071`.

- ontology supplied concept aliases and priors for
  `income_before_income_taxes`
- planner gathered `lookup + difference` materials
- runtime grounding enforced direct-first acceptance and rejected surrogate
  metrics
- aggregate synthesis preserved the accepted direct evidence into the final
  trace

In other words, the canary closed because ontology stayed concept-centric while
runtime handled the direct-vs-fallback decision.

In short:

- ontology = what the domain concepts are
- planner = what material the query seems to require
- runtime binder = whether a direct grounded value is good enough
- synthesizer = whether the gathered material actually satisfies the question

## Group concepts are acceptable, metric recipes are not

This draft intentionally allows concept groups such as:

- `tangible_and_intangible_assets`
- `borrowings`

because those are reusable shorthand patterns in DART language.

This draft intentionally avoids metric-shaped entries such as:

- `debt_ratio`
- `current_ratio`
- `free_cash_flow`

when they are being used only as baked-in query decomposition recipes.

That decomposition should come from planner reasoning over:

- query text
- ontology concepts
- ontology concept groups
- allowed operation families

not from an ever-growing metric answer catalog.

## Proposed V3 shape

The new draft file is:

- [financial_ontology_concepts_v3.draft.json](../../src/config/financial_ontology_concepts_v3.draft.json)

Top-level structure:

- `binding_policy_defaults`
- `planner_guidance`
- `concepts`
- `concept_groups`

Notably absent:

- `metric_families`

This is intentional.

## Why this is better

- smaller ontology surface area
- less benchmark leakage into runtime config
- more robust to unseen questions
- cleaner separation:
  - ontology = domain knowledge
  - planner = query decomposition
  - binder = deterministic value selection
  - calculator = arithmetic

## Migration recommendation

1. Keep current runtime ontology working as-is.
2. Treat V3 as a design target, not an immediate drop-in replacement.
3. Move the planner toward:
   - concept extraction
   - generic operation classification
   - runtime concept composition
4. Once planner quality is good enough, retire most benchmark-shaped metric
   families from the active runtime ontology.

## Practical note

This draft does not say the runtime should become fully unconstrained.

It says:

- structure- and concept-level priors belong in ontology
- query-specific arithmetic recipes belong in the planner

That boundary is the main change.
