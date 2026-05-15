# Financial Ontology V2 Draft

This draft proposes a non-breaking next-step ontology shape for the DART agent.

## Why a V2 draft exists

The current runtime ontology is good at:

- matching a question to a metric family
- nudging retrieval with `preferred_sections`, `query_hints`, and `statement_type_hints`
- expanding a metric into component operands

It is weaker at:

- deciding which structured value to bind when a table exposes detail, subtotal, adjustment, and final aggregate values together
- expressing metric-specific selection policy in data instead of code

Wide note tables exposed this gap most clearly. The parser can now recover many more value cells, but the runtime still needs concept-level policy such as:

- prefer `notes` over generic chunks for `사채`
- prefer `aggregate` over `detail`
- prefer `final` over `subtotal`

## Top-level structure

The draft JSON keeps two distinct layers:

- `metric_families`
  - question classification
  - planning hints
  - retrieval priors
  - formula / component structure
- `concepts`
  - canonical operand meaning
  - aliases and keywords
  - statement / section priors
  - binding policy for structured value selection

## Binding policy intent

`binding_policy` is where metric-specific semantic preference should live.

The parser should continue to output generic structural facts such as:

- `semantic_label`
- `row_headers`
- `column_headers`
- `value_role`
- `aggregation_stage`
- `period_text`

The ontology should decide how much to prefer or avoid those facts for a given concept.

## Component override contract

Each metric-family component should point at a reusable concept via `concept_ref`.

If a specific metric needs different binding behavior than the concept default,
the component may add `binding_policy_override`.

Example:

```json
{
  "components": {
    "numerator_3": {
      "concept_ref": "bonds_payable",
      "required": true,
      "binding_policy_override": {
        "prefer_value_roles": ["aggregate"],
        "prefer_aggregation_stages": ["final"]
      }
    }
  }
}
```

The intended precedence is:

1. `binding_policy_defaults`
2. `concept.binding_policy`
3. component-local `binding_policy`
4. component-local `binding_policy_override`

The last matching layer wins.

## Enum contract

The parser and ontology should share the same normalized vocabulary for
structured value binding.

Current target contract:

- `value_role`: `detail | aggregate | adjustment`
- `aggregation_stage`: `none | direct | subtotal | final`

The runtime still keeps `aggregate_role` as a compatibility field for older
paths, but new policy should bind against the normalized pair above.

## Migration path

This draft is not wired into runtime yet.

Recommended migration order:

1. Keep `src/config/financial_ontology.json` as the active runtime file.
2. Land concept-aware readers in `ontology.py` that can understand this V2 draft shape.
3. Migrate reconciliation scoring to consume `concept.binding_policy`.
4. Reduce code-local special cases once concept policy is stable.

## Design notes

- Existing metric families were migrated into the draft with component references changed from raw labels to `concept` keys.
- Existing metric families were migrated into the draft with component references changed from raw labels to `concept_ref` keys.
- `asset_debt_burden_ratio` was added as a concrete prototype for the current `SKH_T1_060`-style binding problem.
- The current draft now assumes the parser exposes normalized `value_role` and `aggregation_stage` fields; `aggregate_role` remains a compatibility bridge during migration.
