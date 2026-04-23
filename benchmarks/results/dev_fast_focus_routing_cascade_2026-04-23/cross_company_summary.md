# Cross-Company Summary

## Per-Company Results

| Company | Experiment | Screen Pass | Critical Misses | Hit@k | Section | Citation | Contam | API Calls | Est. Cost (USD) | Ingest (s) | API Δ | Time Δ | Cost Δ | Full Faithfulness | Full Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성전자 2024 | contextual_all_2500_320 | yes | 0 | 1.000 | 0.344 | 0.833 | 0.000 | 300 | 0.9100 | 328.156 | 0.0% | 0.0% | 0.0% | 0.825 | 0.562 |
| 삼성전자 2024 | contextual_parent_only_2500_320 | yes | 0 | 1.000 | 0.344 | 0.833 | 0.000 | 40 | 0.1239 | 51.644 | 86.7% | 84.3% | 86.4% | 0.750 | 0.625 |
| 삼성전자 2024 | plain_prefix_2500_320 | yes | 0 | 1.000 | 0.312 | 0.833 | 0.000 | 0 | 0.0000 | 11.499 | 100.0% | 96.5% | 100.0% | 1.000 | 0.500 |
| 삼성전자 2024 | contextual_selective_v2_prefix_2500_320 | yes | 0 | 1.000 | 0.281 | 0.833 | 0.000 | 127 | 0.4022 | 155.013 | 57.7% | 52.8% | 55.8% | 0.625 | 0.500 |

## Winner Ranking

| Rank | Experiment | Pass Count | Company Count | Critical Misses | Avg API Δ | Avg Time Δ | Avg Cost Δ | Avg Faithfulness | Avg Recall |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | plain_prefix_2500_320 | 1 | 1 | 0 | 100.0% | 96.5% | 100.0% | 1.000 | 0.500 |
| 2 | contextual_parent_only_2500_320 | 1 | 1 | 0 | 86.7% | 84.3% | 86.4% | 0.750 | 0.625 |
| 3 | contextual_selective_v2_prefix_2500_320 | 1 | 1 | 0 | 57.7% | 52.8% | 55.8% | 0.625 | 0.500 |
| 4 | contextual_all_2500_320 | 1 | 1 | 0 | 0.0% | 0.0% | 0.0% | 0.825 | 0.562 |

## Selection Policy

The default candidate is ranked by:
1. cross-company screening pass count
2. critical category misses
3. average API call reduction ratio
4. average ingest time reduction ratio
5. full evaluation faithfulness
6. full evaluation context recall
