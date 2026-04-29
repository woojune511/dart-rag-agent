# Retrospective Experiment: Operand Grounding Evaluator

## Setup

- Source bundle: `benchmarks\results\dev_math_focus_evalonly_2026-04-28\삼성전자-2024\results.json`
- Adjudication positives: `8`
- Excluded questions: `comparison_003: display-aware equivalence 변경의 영향이 섞여 있어 operand grounding 실험에서 제외, trend_001: numeric_final_judgement가 없는 trend 서술형 문항이라 제외`

## Aggregate

- Old false negative rate: `0.125`
- New false negative rate: `0.000`
- Recovered question ids: `comparison_001`

## Per Question

| Question | Human Correct | Old Judgement | Old Support | New Judgement | New Support | Note |
|---|---:|---|---:|---|---:|---|
| comparison_001 | yes | FAIL | 0.0 | PASS | 1.0 | 정답 수치와 계산은 맞지만 historical evaluator에서 section support 부족으로 FAIL이 난 대표 케이스 |
| comparison_002 | yes | PASS | 1.0 | PASS | 1.0 |  |
| comparison_004 | yes | PASS | 1.0 | PASS | 1.0 |  |
| trend_002 | yes | PASS | 1.0 | PASS | 1.0 |  |
| trend_003 | yes | PASS | 1.0 | PASS | 1.0 |  |
| comparison_005 | yes | PASS | 1.0 | PASS | 1.0 |  |
| comparison_006 | yes | PASS | 1.0 | PASS | 1.0 |  |
| comparison_007 | yes | PASS | 1.0 | PASS | 1.0 |  |
