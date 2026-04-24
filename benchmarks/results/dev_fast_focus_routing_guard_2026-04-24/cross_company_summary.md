# Cross-Company Summary

## Per-Company Results

| Company | Experiment | Screen Pass | Critical Misses | Hit@k | Section | Citation | Contam | API Calls | Est. Cost (USD) | Ingest (s) | API Δ | Time Δ | Cost Δ | Full Faithfulness | Full Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성전자 2024 | contextual_all_2500_320 | no | 1 | 0.750 | 0.312 | 0.833 | 0.000 | 300 | 0.9172 | 322.633 | 0.0% | 0.0% | 0.0% | 0.800 | 0.500 |
| 삼성전자 2024 | contextual_parent_only_2500_320 | no | 1 | 0.750 | 0.281 | 0.750 | 0.000 | 40 | 0.1280 | 56.690 | 86.7% | 82.4% | 86.0% | 0.800 | 0.625 |
| 삼성전자 2024 | plain_prefix_2500_320 | yes | 0 | 1.000 | 0.312 | 0.833 | 0.000 | 0 | 0.0000 | 7.550 | 100.0% | 97.7% | 100.0% | 1.000 | 0.500 |
| 삼성전자 2024 | contextual_selective_v2_prefix_2500_320 | yes | 0 | 1.000 | 0.312 | 0.833 | 0.000 | 127 | 0.4011 | 142.364 | 57.7% | 55.9% | 56.3% | 1.000 | 0.625 |

## Winner Ranking

| Rank | Experiment | Pass Count | Company Count | Critical Misses | Avg API Δ | Avg Time Δ | Avg Cost Δ | Avg Faithfulness | Avg Recall |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | plain_prefix_2500_320 | 1 | 1 | 0 | 100.0% | 97.7% | 100.0% | 1.000 | 0.500 |
| 2 | contextual_selective_v2_prefix_2500_320 | 1 | 1 | 0 | 57.7% | 55.9% | 56.3% | 1.000 | 0.625 |
| 3 | contextual_parent_only_2500_320 | 0 | 1 | 1 | 86.7% | 82.4% | 86.0% | 0.800 | 0.625 |

Failure Notes for `contextual_parent_only_2500_320`
- 삼성전자 2024: retrieval_hit_at_k == 0 for risk_analysis_001
| 4 | contextual_all_2500_320 | 0 | 1 | 1 | 0.0% | 0.0% | 0.0% | 0.800 | 0.500 |

Failure Notes for `contextual_all_2500_320`
- 삼성전자 2024: retrieval_hit_at_k == 0 for business_overview_001

## Selection Policy

The default candidate is ranked by:
1. cross-company screening pass count
2. critical category misses
3. average API call reduction ratio
4. average ingest time reduction ratio
5. full evaluation faithfulness
6. full evaluation context recall
