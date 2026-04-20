# Cross-Company Summary

## Per-Company Results

| Company | Experiment | Screen Pass | Critical Misses | Hit@k | Section | Citation | Contam | API Calls | Est. Cost (USD) | Ingest (s) | API Δ | Time Δ | Cost Δ | Full Faithfulness | Full Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성전자 2024 | contextual_all_2500_320 | yes | 0 | 1.000 | 0.188 | 0.667 | 0.000 | 0 | 0.0000 | 14.762 | - | 0.0% | - | - | - |
| 삼성전자 2024 | contextual_parent_only_2500_320 | yes | 0 | 1.000 | 0.125 | 0.667 | 0.000 | 0 | 0.0000 | 16.043 | - | -8.7% | - | - | - |
| 삼성전자 2024 | contextual_selective_v2_2500_320 | yes | 0 | 1.000 | 0.188 | 0.667 | 0.000 | 0 | 0.0000 | 8.902 | - | 39.7% | - | - | - |

## Winner Ranking

| Rank | Experiment | Pass Count | Company Count | Critical Misses | Avg API Δ | Avg Time Δ | Avg Cost Δ | Avg Faithfulness | Avg Recall |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | contextual_selective_v2_2500_320 | 1 | 1 | 0 | - | 39.7% | - | - | - |
| 2 | contextual_all_2500_320 | 1 | 1 | 0 | - | 0.0% | - | - | - |
| 3 | contextual_parent_only_2500_320 | 1 | 1 | 0 | - | -8.7% | - | - | - |

## Selection Policy

The default candidate is ranked by:
1. cross-company screening pass count
2. critical category misses
3. average API call reduction ratio
4. average ingest time reduction ratio
5. full evaluation faithfulness
6. full evaluation context recall
