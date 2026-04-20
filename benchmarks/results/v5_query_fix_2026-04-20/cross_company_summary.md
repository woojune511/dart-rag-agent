# Cross-Company Summary

## Per-Company Results

| Company | Experiment | Screen Pass | Critical Misses | Hit@k | Section | Citation | Contam | API Calls | Est. Cost (USD) | Ingest (s) | API Δ | Time Δ | Cost Δ | Full Faithfulness | Full Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성전자 2024 | contextual_all_2500_320 | no | 1 | 0.600 | 0.275 | 0.867 | 0.000 | 0 | 0.0000 | 15.050 | - | 0.0% | - | - | - |
| 삼성전자 2024 | contextual_parent_only_2500_320 | yes | 0 | 0.800 | 0.275 | 0.867 | 0.000 | 0 | 0.0000 | 16.031 | - | -6.5% | - | - | - |
| 삼성전자 2024 | contextual_selective_v2_2500_320 | no | 2 | 0.400 | 0.225 | 0.800 | 0.000 | 0 | 0.0000 | 7.790 | - | 48.2% | - | - | - |

## Winner Ranking

| Rank | Experiment | Pass Count | Company Count | Critical Misses | Avg API Δ | Avg Time Δ | Avg Cost Δ | Avg Faithfulness | Avg Recall |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | contextual_parent_only_2500_320 | 1 | 1 | 0 | - | -6.5% | - | - | - |
| 2 | contextual_all_2500_320 | 0 | 1 | 1 | - | 0.0% | - | - | - |

Failure Notes for `contextual_all_2500_320`
- 삼성전자 2024: retrieval_hit_at_k == 0 for business_overview_001
| 3 | contextual_selective_v2_2500_320 | 0 | 1 | 2 | - | 48.2% | - | - | - |

Failure Notes for `contextual_selective_v2_2500_320`
- 삼성전자 2024: missing-information smoke query hallucinated: 삼성전자 2024 사업보고서에서 2024년말 현재 재무제표에 중요한 영향을 미치는 장기공급계약 수주거래가 있다고 명시하나요? | retrieval_hit_at_k == 0 for risk_analysis_001 | retrieval_hit_at_k == 0 for business_overview_001 | retrieval_hit_at_k dropped by 0.200

## Selection Policy

The default candidate is ranked by:
1. cross-company screening pass count
2. critical category misses
3. average API call reduction ratio
4. average ingest time reduction ratio
5. full evaluation faithfulness
6. full evaluation context recall
