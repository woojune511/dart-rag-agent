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
ontology data. The latest pass moved generic numeric operand surface extraction
off a hard-coded runtime regex list and onto ontology concept surfaces.

| Metric | Count |
| --- | ---: |
| Reviewed records | 762 |
| Literal occurrences | 1,187 |
| `runtime_literal` records | 649 |
| `regex_or_pattern` records | 81 |
| `prompt_or_template` records | 32 |

Top files:

| File | Records | Initial disposition |
| --- | ---: | --- |
| `src/agent/financial_graph_helpers.py` | 261 | P0: likely mix of generic mechanisms, unit labels, and domain terms |
| `src/agent/financial_graph_evidence.py` | 191 | P0: evidence selection and answer assembly must be reviewed first |
| `src/agent/financial_graph_calculation.py` | 127 | P0: numeric execution text is allowed, metric/topic selectors need review |
| `src/agent/financial_graph_models.py` | 113 | P1: mostly schema descriptions and structured-output guidance |
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
