# Cross-Company Summary

## Per-Company Results

| Company | Experiment | Screen Pass | Critical Misses | Hit@k | Section | Citation | Contam | API Calls | Est. Cost (USD) | Ingest (s) | API Δ | Time Δ | Cost Δ | Full Faithfulness | Full Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성전자 2024 | contextual_all_2500_320 | yes | 0 | 1.000 | 0.281 | 0.833 | 0.000 | 300 | 1.0701 | 565.167 | 0.0% | 0.0% | 0.0% | 0.750 | 0.500 |
| 삼성전자 2024 | contextual_parent_only_2500_320 | yes | 0 | 1.000 | 0.312 | 0.833 | 0.000 | 40 | 0.1279 | 54.764 | 86.7% | 90.3% | 88.1% | 0.750 | 0.625 |
| 삼성전자 2024 | plain_prefix_2500_320 | no | 0 | 1.000 | 0.312 | 0.833 | 0.000 | 0 | 0.0000 | 7.629 | 100.0% | 98.7% | 100.0% | 0.675 | 0.500 |
| 삼성전자 2024 | contextual_selective_v2_prefix_2500_320 | yes | 0 | 1.000 | 0.344 | 0.833 | 0.000 | 127 | 0.4012 | 145.972 | 57.7% | 74.2% | 62.5% | 0.675 | 0.625 |

## Winner Ranking

| Rank | Experiment | Pass Count | Company Count | Critical Misses | Avg API Δ | Avg Time Δ | Avg Cost Δ | Avg Faithfulness | Avg Recall |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | contextual_parent_only_2500_320 | 1 | 1 | 0 | 86.7% | 90.3% | 88.1% | 0.750 | 0.625 |
| 2 | contextual_selective_v2_prefix_2500_320 | 1 | 1 | 0 | 57.7% | 74.2% | 62.5% | 0.675 | 0.625 |
| 3 | contextual_all_2500_320 | 1 | 1 | 0 | 0.0% | 0.0% | 0.0% | 0.750 | 0.500 |
| 4 | plain_prefix_2500_320 | 0 | 1 | 0 | 100.0% | 98.7% | 100.0% | 0.675 | 0.500 |

Failure Notes for `plain_prefix_2500_320`
- 삼성전자 2024: risk smoke query failed: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가요? | answerable smoke query abstained: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가요?

## Selection Policy

The default candidate is ranked by:
1. cross-company screening pass count
2. critical category misses
3. average API call reduction ratio
4. average ingest time reduction ratio
5. full evaluation faithfulness
6. full evaluation context recall
