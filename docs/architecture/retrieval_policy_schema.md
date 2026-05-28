# Retrieval Policy Schema

`src/config/retrieval_policy.py` is the boundary for domain vocabulary that
affects retrieval, narrative evidence selection, and deterministic answer
composition.

Runtime code may consume these policies, but it should not introduce new
company-, topic-, or benchmark-specific keyword branches directly in agent
logic. If a term is needed because DART disclosures use that vocabulary, put it
in this policy layer or the ontology, then cover it with a regression test or
benchmark profile.

## Policy Objects

Each object in `NARRATIVE_RETRIEVAL_POLICIES` represents one reusable retrieval
or answer-selection behavior.

| Key | Type | Runtime use |
| --- | --- | --- |
| `name` | string | Stable policy identifier used by runtime consumers |
| `trigger_terms` | tuple[string] | Activates the policy for matching user queries |
| `retrieval_query_suffixes` | tuple[string] | Adds policy-specific query expansion text |
| `preferred_sections` | tuple[string] | Adds retrieval/rerank section preference |
| `paragraph_priority_sections` | tuple[string] | Prioritizes narrative paragraph evidence |
| `focus_terms` | tuple[string] | Scores evidence that matches the query focus |
| `causal_terms` | tuple[string] | Scores explanatory/driver evidence |
| `realized_terms` | tuple[string] | Scores realized business impact evidence |
| `penalty_terms` | tuple[string] | De-emphasizes misleading sections or contexts |
| `driver_groups` | tuple[object] | Maps equivalent evidence terms to answer phrases |
| `entity_metric_slot_groups` | tuple[object] | Selects already-retrieved entity rows/evidence for structured narrative answers |
| `technology_facets` | tuple[object] | Assembles technology-focus answer facets from retrieved evidence |

Policy-specific keys such as `payout_terms`, `policy_terms`, `query_terms`, or
`sentence_terms` are allowed when they are consumed by a generic policy helper
and documented by tests. They should remain data in the policy object, not
inline `if "term" in query` branches in runtime code.

## Runtime Consumption Rules

- Use helper accessors such as `_active_narrative_policies_for_query()` and
  `_narrative_policy_terms_for_query()` from agent code.
- Runtime code should operate on policy names, slot groups, facets, and term
  sets generically.
- A new runtime branch is acceptable only when it introduces a reusable
  operation shape, not when it exists to recognize one benchmark phrase.
- Parser regex and section recognition are separate from answer-selection
  policy. Parser rules may stay parser-local when they recover DART document
  structure rather than tune an answer.

## Validation

Policy changes should use the smallest applicable check first:

1. Unit test for the policy helper or deterministic composer behavior.
2. Targeted replay for a changed question.
3. `benchmarks/profiles/curated_policy_driven_runtime_gate.json` when policy
   vocabulary affects retrieval, evidence selection, or deterministic
   composition.
4. Broader curated gates only after the focused gate is clean.
