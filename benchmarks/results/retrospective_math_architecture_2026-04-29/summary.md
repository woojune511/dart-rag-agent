# Retrospective Experiment: Direct Calc vs Formula Planner + AST

## Setup

- Source bundle: `benchmarks\results\dev_math_focus_evalonly_operandgrounding_v2_2026-04-29\삼성전자-2024\results.json`
- Dataset: `benchmarks\eval_dataset.math_focus.json`
- Numeric slice: `9` questions
- Excluded qualitative question ids: `trend_001`

## Aggregate

| Mode | Strict Correct | Numeric Equivalence | Numeric Grounding |
|---|---:|---:|---:|
| Direct Calc | 0.556 | 0.556 | 0.778 |
| Formula Planner + AST | 1.000 | 1.000 | 1.000 |

## Legacy Operation-Path Overlap

- Overlap question ids: `comparison_001, trend_002`
- Count: `2`
- Strict Correct: `0.500`
- Numeric Equivalence: `0.500`
- Numeric Grounding: `1.000`

## Per Question

| Question | Direct Correct | Formula Correct | Direct Answer | Formula Answer | Direct Failure Reason |
|---|---:|---:|---|---|---|
| comparison_001 | yes | yes | 삼성전자 2024 사업보고서에서 DX 부문과 DS 부문의 매출 차이는 63,821,733 백만원입니다. | 삼성전자 2024년 사업보고서에서 DX 부문 매출은 DS 부문 매출보다 63조 8,217억원 더 큽니다. | - |
| comparison_002 | no | yes | 삼성전자 2024 사업보고서에서 SDC와 Harman 부문의 매출 합계는 475,963 억원입니다. | 삼성전자 2024년 SDC 부문 매출과 Harman 부문 매출의 합계는 43조 4,327억원입니다. | no_equivalent_value |
| comparison_003 | no | yes | 삼성전자 2024 사업보고서에서 DS 부문 매출은 SDC 매출보다 819,082 백만원 더 큽니다. | 2024년 DS 부문 매출은 2024년 SDC 매출보다 81조 9,082억원 더 큽니다. | no_equivalent_value |
| comparison_004 | no | yes | 삼성전자 2024년 연결 기준 영업이익률은 10.88%입니다. | 삼성전자의 2024년 연결 기준 영업이익률은 10.9%입니다. | no_equivalent_value |
| trend_002 | yes | yes | 삼성전자 2024년 영업이익은 2023년 대비 398.3% 증가했습니다. | 삼성전자의 2024년 영업이익은 2023년 대비 398.3% 증가했습니다. | - |
| trend_003 | no | yes | 삼성전자 2024 사업보고서에서 2024년 영업이익은 2022년 대비 -24.55% 변했습니다. | 삼성전자의 2024년 영업이익은 2022년 영업이익 대비 24.6% 감소했습니다. | no_equivalent_value |
| comparison_005 | yes | yes | 삼성전자 2024 사업보고서에서 연구개발비용이 전체 매출에서 차지하는 비중은 11.6%입니다. | 삼성전자의 2024년 연구개발비용이 전체 매출에서 차지하는 비중은 11.6%입니다. | - |
| comparison_006 | yes | yes | 삼성전자 2024 사업보고서에서 2024년과 2023년의 연구개발비 / 매출액 비중 차이는 0.7%p입니다. | 삼성전자의 2024년 연구개발비/매출액 비중은 2023년보다 0.7%p 더 큽니다. | - |
| comparison_007 | yes | yes | 2023년 영업이익은 2022년 영업이익보다 36,809,654 백만원 더 작습니다. | 삼성전자의 2023년 영업이익은 2022년 영업이익보다 36조 8,097억원 더 작습니다. | - |

