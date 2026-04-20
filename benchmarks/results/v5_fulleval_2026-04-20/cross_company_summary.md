# Cross-Company Summary

## Per-Company Results

| Company | Experiment | Screen Pass | Critical Misses | Hit@k | Section | Citation | Contam | API Calls | Est. Cost (USD) | Ingest (s) | API Δ | Time Δ | Cost Δ | Full Faithfulness | Full Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성전자 2024 | contextual_all_2500_320 | no | 1 | 0.800 | 0.325 | 0.867 | 0.000 | 0 | 0.0000 | 0.000 | - | - | - | 0.380 | 0.600 |
| 삼성전자 2024 | contextual_parent_only_2500_320 | yes | 0 | 1.000 | 0.300 | 0.800 | 0.000 | 0 | 0.0000 | 0.000 | - | - | - | 0.500 | 0.620 |
| 삼성전자 2024 | contextual_selective_v2_2500_320 | no | 2 | 0.600 | 0.250 | 0.733 | 0.000 | 0 | 0.0000 | 0.000 | - | - | - | - | - |

## Winner Ranking

| Rank | Experiment | Pass Count | Company Count | Critical Misses | Avg API Δ | Avg Time Δ | Avg Cost Δ | Avg Faithfulness | Avg Recall |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | contextual_parent_only_2500_320 | 1 | 1 | 0 | - | - | - | 0.500 | 0.620 |
| 2 | contextual_all_2500_320 | 0 | 1 | 1 | - | - | - | 0.380 | 0.600 |

Failure Notes for `contextual_all_2500_320`
- 삼성전자 2024: retrieval_hit_at_k == 0 for business_overview_001
| 3 | contextual_selective_v2_2500_320 | 0 | 1 | 2 | - | - | - | - | - |

Failure Notes for `contextual_selective_v2_2500_320`
- 삼성전자 2024: risk smoke query failed: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가요? | retrieval_hit_at_k == 0 for business_overview_001 | retrieval_hit_at_k == 0 for risk_analysis_001 | retrieval_hit_at_k dropped by 0.200

## Selection Policy

The default candidate is ranked by:
1. cross-company screening pass count
2. critical category misses
3. average API call reduction ratio
4. average ingest time reduction ratio
5. full evaluation faithfulness
6. full evaluation context recall
