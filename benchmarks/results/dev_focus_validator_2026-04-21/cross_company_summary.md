# Cross-Company Summary

## Per-Company Results

| Company | Experiment | Screen Pass | Critical Misses | Hit@k | Section | Citation | Contam | API Calls | Est. Cost (USD) | Ingest (s) | API Δ | Time Δ | Cost Δ | Full Faithfulness | Full Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성전자 2024 | contextual_all_2500_320 | no | 1 | 0.667 | 0.083 | 0.778 | 0.000 | 0 | 0.0000 | 0.000 | - | - | - | 0.667 | 0.750 |
| 삼성전자 2024 | contextual_parent_only_2500_320 | no | 1 | 0.667 | 0.083 | 0.667 | 0.000 | 0 | 0.0000 | 0.000 | - | - | - | 0.833 | 0.667 |

## Winner Ranking

| Rank | Experiment | Pass Count | Company Count | Critical Misses | Avg API Δ | Avg Time Δ | Avg Cost Δ | Avg Faithfulness | Avg Recall |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | contextual_parent_only_2500_320 | 0 | 1 | 1 | - | - | - | 0.833 | 0.667 |

Failure Notes for `contextual_parent_only_2500_320`
- 삼성전자 2024: retrieval_hit_at_k == 0 for risk_analysis_001
| 2 | contextual_all_2500_320 | 0 | 1 | 1 | - | - | - | 0.667 | 0.750 |

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
