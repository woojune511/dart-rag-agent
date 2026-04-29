# Retrospective Experiment: Standard Retrieval vs Ontology-Guided Retrieval

## Setup

- Source bundle: `benchmarks\results\dev_math_focus_evalonly_operandgrounding_v2_2026-04-29\삼성전자-2024\results.json`
- Dataset: `benchmarks\eval_dataset.math_focus.json`
- Question ids: `comparison_004, comparison_005, comparison_006`
- Ablation scope: retrieval-side ontology hooks only (`preferred_sections`, `supplement_sections`, `query_hints`)
- Planner prior and evaluator are kept fixed.

## Aggregate

| Mode | Hit@k | Section Match | Row Candidate Recovery | Component Candidate Recovery | Avg Operand Count | Operand Grounding | Calc Success |
|---|---:|---:|---:|---:|---:|---:|---:|
| Standard Retrieval | 1.000 | 0.458 | 0.000 | 0.333 | 1.000 | 0.500 | 0.333 |
| Ontology-Guided Retrieval | 1.000 | 0.583 | 0.667 | 0.333 | 1.667 | 1.000 | 1.000 |

## Per Question

| Question | Standard Retrieval | Ontology-Guided Retrieval | Key Delta |
|---|---|---|---|
| comparison_004 | hit=1.0, rows=0, comps=0, operands=2, calc=ok | hit=1.0, rows=0, comps=0, operands=2, calc=ok | no material change |
| comparison_005 | hit=1.0, rows=0, comps=1, operands=1, calc=insufficient_operands | hit=1.0, rows=1, comps=1, operands=1, calc=ok | row 0 -> 1, calc insufficient_operands -> ok |
| comparison_006 | hit=1.0, rows=0, comps=0, operands=0, calc=insufficient_operands | hit=1.0, rows=1, comps=0, operands=2, calc=ok | row 0 -> 1, operand 0 -> 2, calc insufficient_operands -> ok |

## Notes

- This is a retrieval-side ablation, not a planner ablation.
- `operating_margin` is expected to show a smaller delta because the base heuristics already bias toward `요약재무정보` / `손익계산서`.
- `rnd_ratio` questions are expected to show the largest change because ontology-guided retrieval explicitly supplements `연구개발 활동` / `연구개발실적` sections.

