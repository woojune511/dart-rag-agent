# Cross-Company Summary

## Per-Company Results

| Company | Experiment | Screen Pass | Critical Misses | Hit@k | Section | Citation | Contam | API Calls | Est. Cost (USD) | Ingest (s) | API Δ | Time Δ | Cost Δ | Full Faithfulness | Full Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성전자 2024 | contextual_all_2500_320 | yes | 0 | 1.000 | 0.350 | 0.867 | 0.000 | 300 | 1.0775 | 545.977 | 0.0% | 0.0% | 0.0% | 0.500 | 0.600 |
| 삼성전자 2024 | contextual_parent_only_2500_320 | yes | 0 | 1.000 | 0.300 | 0.800 | 0.000 | 40 | 0.1287 | 54.233 | 86.7% | 90.1% | 88.1% | 0.660 | 0.700 |
| 삼성전자 2024 | contextual_selective_v2_2500_320 | no | 2 | 0.600 | 0.250 | 0.733 | 0.000 | 127 | 0.4052 | 140.410 | 57.7% | 74.3% | 62.4% | - | - |

## Winner Ranking

| Rank | Experiment | Pass Count | Company Count | Critical Misses | Avg API Δ | Avg Time Δ | Avg Cost Δ | Avg Faithfulness | Avg Recall |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | contextual_parent_only_2500_320 | 1 | 1 | 0 | 86.7% | 90.1% | 88.1% | 0.660 | 0.700 |
| 2 | contextual_all_2500_320 | 1 | 1 | 0 | 0.0% | 0.0% | 0.0% | 0.500 | 0.600 |
| 3 | contextual_selective_v2_2500_320 | 0 | 1 | 2 | 57.7% | 74.3% | 62.4% | - | - |

Failure Notes for `contextual_selective_v2_2500_320`
- 삼성전자 2024: retrieval_hit_at_k == 0 for business_overview_001 | retrieval_hit_at_k == 0 for risk_analysis_001 | retrieval_hit_at_k dropped by 0.400

## Selection Policy

The default candidate is ranked by:
1. cross-company screening pass count
2. critical category misses
3. average API call reduction ratio
4. average ingest time reduction ratio
5. full evaluation faithfulness
6. full evaluation context recall
