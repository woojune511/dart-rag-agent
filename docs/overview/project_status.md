# Project Status

Last updated: 2026-06-02

## Positioning

This repository is a DART financial-document RAG and agent-runtime project. The
core engineering goal is not to hard-code benchmark answers, but to build a
traceable runtime contract for financial analysis:

- retrieve evidence from long-form DART filings
- bind the right structured rows and source sentences
- execute numeric operations deterministically
- preserve calculation and evidence traces
- validate changes through reproducible benchmark gates

The current direction is to turn the verified single-agent runtime into a
role-separated multi-agent system using a task ledger and artifact store.

## Current Gate Status

| Gate | Scope | Latest Status |
| --- | --- | --- |
| Runtime contract gate | 5 core numeric/runtime questions | PASS |
| Concept runtime gap gate | 7 ontology-driven concept questions | PASS |
| Policy-driven runtime gate | 4 company runs, 5 policy/narrative questions | PASS |

### Runtime Contract Gate

- Profile: `benchmarks/profiles/curated_runtime_contract_gate.json`
- Candidate: `structural_selective_v2_prefix_2500_320`
- Current interpretation: default short smoke gate is stable.

### Concept Runtime Gap Gate

- Profile: `benchmarks/profiles/curated_concept_runtime_gap_gate.json`
- Latest representative local output:
  `benchmarks/results/concept_runtime_gap_gate_refresh_2026-06-02_042728/`
- Result:
  - 7 / 7 questions passed
  - `numeric_final_judgement = PASS` for all seven questions
  - aggregate numeric pass, completeness, and faithfulness are all `1.000`
- Main closure:
  - multi-concept lookup tasks now split into independent task-ledger entries
  - sibling table evidence can recover missing lookup slots generically
  - lookup-list rendering is constrained to lookup-only aggregates

### Policy-Driven Runtime Gate

- Profile: `benchmarks/profiles/curated_policy_driven_runtime_gate.json`
- Source/output store bundle:
  `benchmarks/results/policy_gate_regression_2026-05-31_2212/`
- Latest store-fixed refresh result:
  - 4 / 4 company runs passed
  - 0 full-eval failures
  - 0 critical misses
  - average faithfulness, completeness, and context recall are all `1.000`
- Note:
  - `numeric_final_judgement = null` is not a failure for narrative or mixed
    questions when the other evaluator signals are healthy.

## Operating Principles

- Domain vocabulary belongs in ontology, retrieval policy, config, or reviewed
  data artifacts, not runtime control-flow code.
- Runtime code should implement generic mechanisms: evidence preservation,
  structured row/header matching, dependency binding, dedupe, ordering,
  validation, and display preservation.
- Benchmark regressions are classified by layer before implementation:
  ontology, retrieval policy, parser structure, planner contract, evidence
  schema, runtime execution, or evaluator definition.
- Store-fixed `--eval-only` refreshes come before fresh ingest unless parser,
  ingest, or cache signatures changed.
- Experiment result directories are local artifacts and are not committed.

## Portfolio Framing

The strongest portfolio story is:

> I built a financial-document RAG runtime that treats numbers as structured
> evidence-bound artifacts rather than free-form LLM text. The system separates
> semantic planning from deterministic execution, stores explicit calculation
> traces, and uses focused benchmark gates to prevent benchmark-specific
> patches from entering runtime code.

Useful supporting points:

- The project handles noisy DART filings with section/table-aware parsing and
  hybrid retrieval.
- Numeric questions use formula planning and safe deterministic execution.
- Evaluation is split into faithfulness, completeness, numeric equivalence,
  numeric grounding, and retrieval support.
- The runtime now has gate-backed concept and policy-driven paths without
  adding company/question-specific branches to agent code.

## Next Work

1. Reduce benchmark runtime and embedding cost through profiling and cache
   hygiene.
2. Harden task-ledger and artifact-store contracts for the multi-agent workflow.
3. Clean up legacy projection paths now that `answer_slots` and
   `resolved_calculation_trace` are the durable runtime surfaces.
4. Add a small portfolio demo script that runs a representative query and emits
   answer, evidence, and calculation trace side by side.
