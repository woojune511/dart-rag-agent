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
policy.

| Metric | Count |
| --- | ---: |
| Reviewed records | 528 |
| Literal occurrences | 785 |
| `runtime_literal` records | 427 |
| `regex_or_pattern` records | 70 |
| `prompt_or_template` records | 31 |

Top files:

| File | Records | Initial disposition |
| --- | ---: | --- |
| `src/agent/financial_graph_helpers.py` | 224 | P0: likely mix of generic mechanisms, unit labels, and domain terms |
| `src/agent/financial_graph_models.py` | 113 | P1: mostly schema descriptions and structured-output guidance |
| `src/agent/financial_graph_evidence.py` | 67 | P0: evidence selection and answer assembly must be reviewed first |
| `src/agent/financial_graph_calculation.py` | 54 | P0: numeric execution text is allowed, metric/topic selectors need review |
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
   `financial_graph_models.py`, `financial_graph_contextual.py`,
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
  current top helper targets are `_infer_statement_and_section_hints`,
  `_extract_segment_labels_from_query`, `_desired_consolidation_scope`, and
  `_desired_statement_types`.
- `_infer_statement_and_section_hints()` no longer carries concept-specific
  section branches for pretax income, foreign-currency translation, borrowings,
  CAPEX, or operating expense. Runtime now merges generic document-structure
  hints with ontology preferred sections and named numeric section hint policies
  from retrieval config. This keeps legacy/experimental ontology profiles from
  changing planner status while still avoiding runtime domain branches.
- `_extract_segment_labels_from_query()` now consumes segment markers,
  stopwords, split patterns, and token patterns from retrieval policy config.
  The runtime function keeps the generic extraction mechanics: normalize,
  reject blocked labels, split near a segment anchor, and dedupe.
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

## Calculation Hotspots

The current calculation-module audit was inspected with:

```bash
python -m src.ops.audit_runtime_domain_terms --by-function --scan-root src/agent/financial_graph_calculation.py
```

Top calculation targets for the next cleanup are:

| Symbol | Occurrences | Initial read |
| --- | ---: | --- |
| `_slot_metric_keys` | 8 | slot normalization terms; move metric suffixes to policy if selector-like |
| `_refine_operand_precision_from_evidence_table` | 8 | evidence table unit precision; likely unit policy candidate |
| `_coerce_sign_aware_subtraction_answer` | 8 | sign-aware answer rewrite; inspect templates and evidence preservation |
| `_infer_dependency_row_unit` | 7 | dependency unit normalization; likely shared unit policy candidate |
| `_verify_calculation_answer` | 7 | answer verification prompt/messages; separate templates from checks |
| `_compose_growth_narrative_answer` | 5 | growth answer validation/composition; check remaining selector-like text |
| `_coerce_operand_unit_from_evidence` | 5 | evidence unit coercion; likely shared unit policy candidate |
| `_format_calculation_value_in_display_unit` | 5 | display-unit formatting; check if remaining unit vocabulary belongs in policy |

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
