# Runtime Domain Term Audit

This audit keeps domain vocabulary out of runtime control-flow code. It scans
high-risk agent paths for reviewed Korean string literals and compares them
against `tests/fixtures/runtime_domain_terms_baseline.json`.

The baseline is a debt ledger, not an approval to add more runtime keywords.
When a new literal appears, first move the vocabulary to ontology, retrieval
policy, config, or a documented data artifact. Update the baseline only for
structural/runtime text that cannot reasonably live in a declarative layer.

## Commands

```bash
python -m src.ops.audit_runtime_domain_terms
python -m src.ops.audit_runtime_domain_terms --summary
python -m src.ops.audit_runtime_domain_terms --by-function
python -m src.ops.audit_runtime_domain_terms --write-baseline
```

Use `--write-baseline` only after reviewing why records disappeared or why a
remaining literal is justified.
Use `--by-function` when picking the next cleanup target inside a large runtime
module; it groups reviewed literal occurrences by class/function symbol without
changing the baseline format.

## Current Snapshot

Generated on 2026-06-01 after excluding `if __name__ == "__main__"` demo
blocks and replacing the MAS orchestrator fallback keyword classifier with a
generic two-worker fallback. The helpers cleanup also removed a company-specific
operand-label normalization rule and moved calculation section/topic hinting to
ontology data. Later passes moved generic numeric operand surface extraction
off a hard-coded runtime regex list and onto ontology concept surfaces, then
moved numeric section hints and segment-label extraction vocabulary into
retrieval policy/config. The latest evidence pass moved quantitative-impact,
entity-table summary, and required-operand assembly surfaces into retrieval
policy/config, then moved technology-focus assembly wording and ratio component
candidate scoring surfaces into policy/ontology-driven data. The most recent
pass moved lookup surface token handling and ratio operand assembly patterns
into required-operand assembly policy. A follow-up pass moved narrative rerank
causal markers, quantitative-impact focus stopwords, dividend policy period
markers, ratio row candidate patterns, ratio component percent-value allowance,
and sentence-normalisation messages into policy/config. The latest calculation
pass moved growth-narrative explanatory markers, context stopwords, missing
answer markers, growth intent checks, direction wording, and the numeric
sentence template into calculation narrative policy. The latest render pass
moved slot-based difference answer scope labels, fallback labels, and answer
templates into calculation render policy. A display-unit follow-up moved
adjusted-difference trigger markers and source/converted display-unit sets into
calculation render policy. A renderer follow-up moved direction hints,
calculation-render fallback messages, and the structured renderer prompt into
calculation render policy. A grounded-display follow-up moved normalized-unit
groups, KRW display units, and embedded-unit markers into calculation render
policy. A feedback-policy follow-up moved planner feedback fallback labels,
missing-slot labels, joiners, and feedback templates into calculation feedback
policy. The latest slot/unit/verification pass moved calculation slot cleanup
terms, dependency unit groups, KRW magnitude markers, direction hints, and the
verification prompt into calculation policy. A sign/ratio rendering follow-up
moved sign-aware subtraction replacement templates, ratio compact answer
wording, ratio period patterns, and ambiguous KRW unit coercion rules into
calculation render policy. A growth/display follow-up moved growth narrative
period-prefix templates and KRW display-unit scale factors into calculation
policy. A helper retrieval-hint follow-up moved document statement hint
policies, segment section hint policy, numeric statement hint policies, and
consolidation scope markers into retrieval policy. A helper scoring follow-up
moved numeric unit normalization policy, generic metric alias substitutions,
operation-family query markers, percent-point detection markers, and
structured-cell affinity terms into retrieval policy. A ratio/period helper
follow-up moved metric topic extraction terms, ratio percent query markers,
generic operand label expansions/drop labels, period-focus markers, explicit
ratio definition markers/templates, and operand candidate scoring penalty
terms into retrieval policy. A structured-cell/value helper follow-up moved
generic unit-family markers, concept metric label templates, segment-scope
markers, structured-cell period scoring markers, direct-acceptance period
presence checks, note-context markers, and nearby value/unit extraction
patterns into retrieval policy. A period-operand helper follow-up moved metric
label cleanup boundaries, period operand label templates, comparison markers,
KRW compact-format labels/scales, and reconciliation query scope prefixes into
retrieval policy. A candidate-scoring helper follow-up moved concept ratio
result-unit markers, metric-task query templates, aggregate row-stage tokens,
candidate explicit-year period markers, consolidation context markers, CAPEX
source-priority surfaces, balance-sheet scope markers, and delta-row markers
into retrieval policy. A schema-audit follow-up taught the audit scanner to
classify Pydantic `Field(description=...)` text as `schema_description` so
structured-output contracts are tracked separately from runtime decision
literals. An evidence prompt-policy follow-up moved compression guidance,
evidence extraction extra rules, and the evidence extraction prompt template
into retrieval policy.

| Metric | Count |
| --- | ---: |
| Reviewed records | 354 |
| Literal occurrences | 419 |
| `runtime_literal` records | 156 |
| `schema_description` records | 117 |
| `regex_or_pattern` records | 60 |
| `prompt_or_template` records | 21 |

Top files:

| File | Records | Initial disposition |
| --- | ---: | --- |
| `src/agent/financial_graph_models.py` | 113 | P1: all current records classify as schema descriptions; keep as structured-output contract unless text starts steering runtime selection |
| `src/agent/financial_graph_helpers.py` | 94 | P0: likely mix of generic mechanisms, unit labels, and domain terms |
| `src/agent/financial_graph_evidence.py` | 47 | P0: evidence selection and answer assembly must be reviewed first |
| `src/agent/financial_graph_calculation.py` | 30 | P0: numeric execution text is allowed, metric/topic selectors need review |
| `src/agent/financial_graph_reconciliation.py` | 19 | P1: check generic missing-value messages vs selection terms |
| `src/agent/nodes/critic_node.py` | 14 | P1: mostly validation messages and unit display checks |
| `src/agent/financial_graph_contextual.py` | 11 | P1: prompt/context templates |
| `src/agent/financial_graph_planning.py` | 8 | P0/P1: planning hints and query text need review |
| `src/agent/nodes/dummy_nodes.py` | 8 | P2: MAS skeleton fixtures, not production retrieval policy |
| `src/routing/types.py` | 4 | P1: schema field descriptions |
| `src/agent/nodes/orchestrator_node.py` | 3 | P1: prompt/fallback answer text; keyword fallback removed |
| `src/agent/nodes/researcher_node.py` | 2 | P1: refusal text |

## Review Priority

1. P0 runtime decision paths:
   `financial_graph_helpers.py`, `financial_graph_evidence.py`,
   `financial_graph_calculation.py`, `financial_graph_planning.py`.
2. P1 schema/prompt/message paths:
   `financial_graph_contextual.py`,
   `financial_graph_reconciliation.py`, `critic_node.py`,
   `researcher_node.py`, `routing/types.py`.
3. P2 fixture or skeleton paths:
   `nodes/dummy_nodes.py`.

For each P0 record, classify it as one of:

- generic runtime mechanism: keep in code if it is not domain vocabulary;
- parser/structure term: move only if it affects agent decisions outside
  parsing;
- domain prior: move to ontology/retrieval policy/config;
- answer wording: keep only if evidence-grounded and not a selector;
- diagnostic/test/demo text: remove from runtime scan or move to tests/docs.

## First Cleanup Completed

- The scanner now ignores `if __name__ == "__main__"` demo blocks. This removed
  five non-production demo literals from the reviewed baseline and keeps the
  audit focused on import-time runtime paths.
- `src/agent/nodes/orchestrator_node.py` no longer classifies fallback planner
  tasks with query keyword lists. Planner failure now creates generic Analyst
  and Researcher tasks, letting workers handle applicability from their
  contracts. This removed 19 reviewed records from the baseline.
- `src/agent/financial_graph_helpers.py` no longer strips only one hard-coded
  company name from operand display labels. It now removes a generic
  company/entity prefix when followed by a year, preserving the same display
  behavior without company-specific vocabulary. This removed one reviewed
  regex record from the baseline.
- `src/agent/financial_graph_helpers.py` now resolves calculation preferred
  sections and retrieval hints from ontology instead of appending runtime
  keyword branches for common financial metrics. The ontology manager now
  merges metric-family and concept priors generically, and the CAPEX concept
  includes the equipment-investment alias needed by that data layer. This
  removed 3 reviewed records and 59 literal occurrences from the runtime
  baseline.
- `_extract_generic_operand_labels()` no longer carries a hard-coded list of
  numeric operand regexes for individual financial concepts. It now consumes
  matched ontology concept surfaces generically, with redundant alias cleanup
  based on display/parenthetical structure. The operating-loss surface needed by
  the same concept family lives in the v3 ontology overlay instead of runtime
  control-flow code. This removed 11 reviewed records and 13 literal
  occurrences from the runtime baseline.
- The audit CLI now supports `--by-function`/`--by-symbol`, which reports the
  function or class scopes that still hold the most reviewed literals. The
  current top helper targets are module-level constants,
  `_score_structured_cell`, `_candidate_satisfies_direct_acceptance_contract`,
  `_infer_generic_unit_family`, `_build_concept_metric_label`, and
  `_extract_value_near_match`.
- `_infer_statement_and_section_hints()` no longer carries concept-specific
  section branches for pretax income, foreign-currency translation, borrowings,
  CAPEX, or operating expense. Runtime now merges generic document-structure
  hints with ontology preferred sections and named numeric section hint policies
  from retrieval config. This keeps legacy/experimental ontology profiles from
  changing planner status while still avoiding runtime domain branches.
- `_desired_statement_types()`, `_desired_consolidation_scope()`, and
  `_infer_statement_and_section_hints()` now read document statement hints,
  numeric statement hints, segment section hints, and consolidation scope
  marker groups from retrieval policy. Runtime keeps the generic mechanics:
  match configured marker groups, merge ontology hints, dedupe statement types,
  and infer candidate ranking scope.
- `_normalise_operand_value()`, `_build_generic_metric_aliases()`,
  `_infer_operation_family_from_query()`, `_is_percent_point_difference_query()`,
  and `_structured_cell_operand_affinity()` now read unit normalization scales,
  inline unit parsing policy, metric alias substitutions, operation markers,
  percent-point markers, and structured-cell scoring terms from retrieval
  policy. Runtime keeps the generic mechanics: parse numeric text, apply
  configured substitutions, classify operation families, and score structured
  cell/header affinity.
- `_metric_terms_from_topic()`, `_is_ratio_percent_query()`,
  `_extract_generic_operand_labels()`, `_build_explicit_ratio_definition_task()`,
  `_infer_period_focus()`, and canonical-row sections of
  `_score_operand_candidate()` now read metric topic terms, ratio markers,
  operand label expansions/drop labels, explicit ratio-definition markers and
  templates, period-focus markers, and row scoring penalty terms from retrieval
  policy. Runtime keeps the generic mechanics: match configured marker groups,
  build operand specs, infer period focus, and score evidence candidates.
- `_extract_segment_labels_from_query()` now consumes segment markers,
  stopwords, split patterns, and token patterns from retrieval policy config.
  The runtime function keeps the generic extraction mechanics: normalize,
  reject blocked labels, split near a segment anchor, and dedupe.
- `_infer_generic_unit_family()`, `_build_concept_metric_label()`,
  `_build_concept_task_constraints()`, `_score_structured_cell()`,
  `_candidate_satisfies_direct_acceptance_contract()`, and
  `_extract_value_near_match()` now read unit-family markers, metric label
  templates, segment markers, period-scoring markers, direct-acceptance period
  patterns, note-context markers, and value/unit extraction patterns from
  retrieval policy. Runtime keeps the generic mechanics: infer unit family,
  render concept labels from ordered ontology specs, score table headers,
  validate selected-cell period compatibility, and preserve evidence-visible
  nearby values.
- `_format_korean_won_compact()`, `_clean_metric_label()`,
  `_is_single_metric_period_comparison()`,
  `_build_generic_required_operands()`, `_build_concept_period_operands()`,
  `_structured_cell_period_text()`, `_build_generic_retrieval_queries()`, and
  `_build_reconciliation_retry_queries()` now read KRW compact-format labels,
  metric cleanup boundaries, period operand templates/hints, comparison
  markers, year suffix templates, and consolidation query prefixes from
  retrieval policy. Runtime keeps the generic mechanics: normalize labels,
  build current/prior operands, derive year-aware query surfaces, and assemble
  retry queries from missing operands.
- `_infer_concept_ratio_result_unit()`, `_build_metric_task_query()`,
  `_operand_period_focus()`, `_aggregate_like_row_stage()`,
  `_candidate_explicit_years()`, `_is_capex_total_operand()`,
  `_candidate_consolidation_scope()`, `_candidate_source_priority_bonus()`,
  and `_is_delta_like_row_label()` now read ratio-result units, task query
  templates, period hint groups, aggregate stage tokens, consolidation scope
  markers, CAPEX source-priority surfaces, balance-sheet scope markers, and
  delta-row markers from retrieval policy. Runtime keeps the generic mechanics:
  infer result units, build canonical task text, map period hints, classify
  aggregate rows, infer candidate years, and score source priority.
- The audit scanner now classifies Pydantic `Field(description=...)` and
  `Field(title=...)` literals as `schema_description`. This keeps
  `financial_graph_models.py` visible in the debt ledger while separating
  schema guidance from runtime control-flow vocabulary. The current
  `financial_graph_models.py` records are all schema descriptions, so no
  model-file domain terms were moved into policy in this pass.
- `_compression_guidance()` and `_extract_evidence()` now read compression
  instructions, output-style guidance, coverage notes, evidence extraction
  extra rules, and the evidence extraction prompt template from retrieval
  policy. Runtime keeps the generic mechanics: choose guidance by query type
  and operation family, build evidence context, invoke structured extraction,
  and run deterministic fallback only from retrieved source text.
- `_build_ratio_operands_from_candidates()` no longer carries a fixed
  R&D/revenue component fallback. When row-level percent values are absent, it
  asks the active ontology metric family for ratio component specs and matches
  candidate rows against those configured component surfaces.
- `_supplement_numeric_impairment_lookup()` now reads its trigger terms, table
  row labels, default unit, and deterministic answer template from retrieval
  policy config. Runtime still requires structured table row records and a
  source-backed metric cell before it assembles the answer.
- `_compose_supported_quantitative_impact_answer()` now reads denominator
  markers, impact/caveat terms, and answer wording from retrieval policy. The
  runtime path only parses retrieved labeled numeric rows, selects supported
  numerator/denominator rows, and computes the displayed ratio.
- `_compose_entity_table_summary_answer()` now reads section scoring rules,
  entity-table metric terms, role display labels, units, and sentence templates
  from retrieval policy. Runtime keeps the generic mechanics: scan lines around
  the requested entity, rank candidates, preserve evidence rows, and project
  answer slots.
- `_build_required_operands_from_candidates()` now reads aggregate row labels,
  inline unit parsing, unit fallback rules, and default units from retrieval
  policy. Runtime still requires operand surface/structured-cell/prose support
  before emitting operand rows.
- `_compose_business_technology_focus_answer()` now reads R&D amount selection
  terms, output labels, unit text, and sentence templates from the active
  narrative policy. Runtime only locates the requested entity, matches configured
  facets, extracts evidence-visible numeric surfaces, and assembles policy
  templates.
- `_extract_ratio_component_candidates()` no longer carries metric-name-specific
  scoring branches for R&D or revenue rows. Candidate scoring now boosts query
  year matches and the ontology component surfaces already used to find the
  candidate row.
- `_lookup_line_matches_operand_surface()` now reads token splitting and blocked
  surface tokens from required-operand assembly policy. Runtime keeps only the
  generic check that enough operand surface fragments appear on the same line.
- `_build_ratio_operands_from_candidates()` now reads percent/year/value
  patterns, ratio label/unit text, subject-after-context priority, and unit
  fallback rules from required-operand assembly policy. Runtime still selects
  row-level percentages or ontology-defined ratio components from retrieved
  candidates.
- `_rerank_docs()` now reads narrative causal marker boosts from retrieval
  policy instead of carrying a local keyword tuple.
- `_select_narrative_summary_docs()` now reads quantitative-impact focus
  stopwords and dividend-policy period markers from policy/config. Runtime keeps
  the generic fill mechanics for missing focused evidence.
- `_extract_ratio_row_candidates()` now reads fallback ratio row patterns and
  period/percent parsing patterns from required-operand assembly policy.
- `_extract_ratio_component_candidates()` now gates percent-valued component
  candidates by ontology concept keys configured in required-operand assembly
  policy, instead of a metric-name branch.
- `_normalise_sentence_checks()` and `_is_intro_sentence()` now read intro
  patterns and fallback reason text from sentence-normalisation policy. Runtime
  keeps verdict validation and evidence-overlap checks as code.
- Calculation growth-narrative paths now read explanatory query markers,
  context stopwords, priority section/support-level hints, missing-answer
  markers, growth intent/display patterns, focus stopwords, direction wording,
  and the numeric sentence template from `CALCULATION_NARRATIVE_POLICY`. Runtime
  keeps the generic mechanics: select material growth slots, score supported
  narrative sentences, preserve evidence-visible values, and validate that the
  aggregate answer contains both the numeric result and narrative support.
- `_compose_slot_based_difference_answer()` now reads scope labels, fallback
  operand/result labels, and slot-based difference answer templates from
  `CALCULATION_RENDER_POLICY`. Runtime keeps only the generic mechanics: pick
  material minuend/subtrahend/result slots, infer company/period/scope prefix,
  and preserve rendered slot values.
- `_adjusted_difference_source_display_unit()` now reads adjusted-difference
  trigger markers, exclusion regex, source display units, and converted display
  units from `CALCULATION_RENDER_POLICY`. Runtime keeps the generic mechanics:
  inspect active task text, compare operand units, and preserve the source unit
  when all operands agree or when converted KRW display units are mixed in.
- `_render_calculation_answer()` now reads direction hints, fallback messages,
  and the structured renderer prompt from `CALCULATION_RENDER_POLICY`. Runtime
  keeps the generic mechanics: resolve trace state, remove duplicate negative
  signs when a direction hint is present, call deterministic fallbacks, and
  preserve the rendered calculation result in runtime trace.
- `_render_grounded_operand_display()` now reads count/percent normalized-unit
  groups, KRW normalized/display units, and embedded-unit markers from
  `CALCULATION_RENDER_POLICY`. Runtime keeps the generic mechanics: preserve
  evidence-visible raw values when they already carry a unit and append source
  units only when needed.
- `_material_gap_feedback_for_subtask_result()` and the generic planner
  feedback fallback now read fallback metric labels, missing-slot labels,
  joiners, and feedback templates from `CALCULATION_FEEDBACK_POLICY`. Runtime
  keeps the generic mechanics: inspect operation family, status, answer slots,
  and rendered material before reporting which required material is absent.
- `_slot_metric_keys()`, `_slot_period_hint()`,
  `_refine_operand_precision_from_evidence_table()`,
  `_infer_dependency_row_unit()`, and `_verify_calculation_answer()` now read
  slot cleanup terms, period patterns, display-unit groups, KRW magnitude
  markers, direction hints, and the verification prompt from calculation
  policy. Runtime keeps the generic mechanics: normalize labels, infer units
  from declared unit groups, preserve finer evidence-table cells, and verify
  that rendered answers still match calculation traces.
- `_coerce_sign_aware_subtraction_answer()`, `_compact_ratio_answer()`, and
  `_coerce_operand_unit_from_evidence()` now read sign-aware replacement
  templates, ratio answer wording, ratio period patterns, and ambiguous KRW
  unit coercion rules from `CALCULATION_RENDER_POLICY`. Runtime keeps the
  generic mechanics: collect negative subtrahend slots, preserve rendered
  ratio values, and use evidence table unit hints only when a bare numeric
  surface would otherwise carry an ambiguous KRW unit.
- `_compose_growth_narrative_answer()` and
  `_format_calculation_value_in_display_unit()` now read growth period-prefix
  templates and KRW display-unit scale factors from calculation policy. Runtime
  keeps the generic mechanics: remove period text from metric labels, preserve
  source-stated growth values, and render numeric values in the requested
  display unit.

## Calculation Hotspots

The current calculation-module audit was inspected with:

```bash
python -m src.ops.audit_runtime_domain_terms --by-function --scan-root src/agent/financial_graph_calculation.py
```

Top calculation targets for the next cleanup are:

| Symbol | Occurrences | Initial read |
| --- | ---: | --- |
| `_topic_particle` | 4 | Korean particle helper; likely generic answer wording |
| `_compose_growth_narrative_answer` | 3 | remaining growth answer validation/composition; mostly generic direction-state handling |
| `_refine_operand_precision_from_evidence_table` | 3 | remaining structured-table field/period handling; mostly generic |
| `_build_deterministic_ontology_plan` | 3 | formula planner prompt; likely prompt/config boundary review |
| `_execute_calculation` | 3 | numeric execution labels/messages; check if generic execution text |
| `_aggregate_calculation_subtasks` | 3 | aggregation status/messages; check generic missing-result wording |

## Evidence Hotspots

The current evidence-module audit was inspected with:

```bash
python -m src.ops.audit_runtime_domain_terms --by-function --scan-root src/agent/financial_graph_evidence.py
```

Top evidence targets for the next cleanup are:

| Symbol | Occurrences | Initial read |
| --- | ---: | --- |
| `_compression_guidance` | 16 | prompt guidance text; mostly validation/compression wording |
| `_query_focus_marker_groups` | 5 | marker extraction; likely stopword/config boundary review |
| `_build_required_operands_from_candidates` | 5 | remaining literals are mostly period/unit mechanics after policy extraction |
| `_period_comparison_count_value_from_text` | 4 | period/count regex mechanics; check whether existing period fragments cover it |
| `_extract_ratio_component_candidates` | 4 | candidate row extraction; remaining literals are mostly generic numeric surfaces |
| `_augment_narrative_answer_with_supported_drivers` | 4 | answer support assembly; inspect policy-driven driver wording |
| `_compose_entity_table_summary_answer` | 4 | mostly policy-backed entity table assembly, remaining mechanics need review |
| `_normalise_sentence_checks` | 4 | validation verdict labels and schema/control checks |
