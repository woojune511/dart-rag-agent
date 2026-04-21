# Cross-Company Summary

## Per-Company Results

| Company | Experiment | Screen Pass | Critical Misses | Hit@k | Section | Citation | Contam | API Calls | Est. Cost (USD) | Ingest (s) | API Δ | Time Δ | Cost Δ | Full Faithfulness | Full Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성전자 2024 | contextual_all_2500_320 | yes | 0 | 1.000 | 0.325 | 0.867 | 0.000 | 300 | 0.8959 | 328.106 | 0.0% | 0.0% | 0.0% | 0.540 | 0.600 |
| 삼성전자 2024 | contextual_parent_only_2500_320 | yes | 0 | 1.000 | 0.325 | 0.800 | 0.000 | 40 | 0.1283 | 66.841 | 86.7% | 79.6% | 85.7% | 0.700 | 0.720 |
| 삼성전자 2024 | contextual_selective_v2_2500_320 | no | 2 | 0.600 | 0.225 | 0.733 | 0.000 | 127 | 0.4004 | 158.601 | 57.7% | 51.7% | 55.3% | - | - |

## Winner Ranking

| Rank | Experiment | Pass Count | Company Count | Critical Misses | Avg API Δ | Avg Time Δ | Avg Cost Δ | Avg Faithfulness | Avg Recall |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | contextual_parent_only_2500_320 | 1 | 1 | 0 | 86.7% | 79.6% | 85.7% | 0.700 | 0.720 |
| 2 | contextual_all_2500_320 | 1 | 1 | 0 | 0.0% | 0.0% | 0.0% | 0.540 | 0.600 |
| 3 | contextual_selective_v2_2500_320 | 0 | 1 | 2 | 57.7% | 51.7% | 55.3% | - | - |

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
