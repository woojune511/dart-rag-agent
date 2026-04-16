# Cross-Company Summary

## Per-Company Results

| Company | Experiment | Screen Pass | Critical Misses | Hit@k | Section | Citation | Contam | API Calls | Est. Cost (USD) | Ingest (s) | API Δ | Time Δ | Cost Δ | Full Faithfulness | Full Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성전자 2024 | contextual_all_2500_320 | no | 1 | 0.800 | 0.300 | 0.800 | 0.000 | 300 | 0.9139 | 334.913 | 0.0% | 0.0% | 0.0% | 0.400 | 0.600 |
| 삼성전자 2024 | contextual_parent_only_2500_320 | no | 1 | 0.800 | 0.275 | 0.733 | 0.000 | 40 | 0.1279 | 59.321 | 86.7% | 82.3% | 86.0% | - | - |
| 삼성전자 2024 | contextual_parent_hybrid_2500_320 | yes | 0 | 1.000 | 0.375 | 0.800 | 0.000 | 321 | 1.0285 | 370.160 | -7.0% | -10.5% | -12.5% | 0.800 | 0.700 |
| 삼성전자 2024 | contextual_selective_v2_2500_320 | no | 2 | 0.600 | 0.275 | 0.733 | 0.000 | 127 | 0.4013 | 151.629 | 57.7% | 54.7% | 56.1% | - | - |
| SK하이닉스 2024 | contextual_all_2500_320 | yes | 0 | 1.000 | 0.175 | 1.000 | 0.000 | 179 | 0.5714 | 209.846 | 0.0% | 0.0% | 0.0% | 0.600 | 0.600 |
| SK하이닉스 2024 | contextual_parent_only_2500_320 | no | 2 | 0.600 | 0.250 | 0.867 | 0.000 | 41 | 0.1292 | 55.270 | 77.1% | 73.7% | 77.4% | - | - |
| SK하이닉스 2024 | contextual_parent_hybrid_2500_320 | no | 1 | 0.800 | 0.275 | 0.933 | 0.000 | 202 | 0.8100 | 484.335 | -12.8% | -130.8% | -41.8% | - | - |
| SK하이닉스 2024 | contextual_selective_v2_2500_320 | no | 2 | 0.600 | 0.100 | 0.867 | 0.000 | 119 | 0.5438 | 375.203 | 33.5% | -78.8% | 4.8% | - | - |
| NAVER 2024 | contextual_all_2500_320 | no | 1 | 0.800 | 0.625 | 0.933 | 0.000 | 733 | 2.5583 | 917.419 | 0.0% | 0.0% | 0.0% | 0.500 | 0.467 |
| NAVER 2024 | contextual_parent_only_2500_320 | no | 1 | 0.800 | 0.625 | 0.933 | 0.000 | 42 | 0.1280 | 80.673 | 94.3% | 91.2% | 95.0% | - | - |
| NAVER 2024 | contextual_parent_hybrid_2500_320 | no | 1 | 0.800 | 0.650 | 0.933 | 0.000 | 768 | 3.0853 | 1651.686 | -4.8% | -80.0% | -20.6% | - | - |
| NAVER 2024 | contextual_selective_v2_2500_320 | no | 1 | 0.800 | 0.650 | 0.933 | 0.000 | 113 | 0.5246 | 393.761 | 84.6% | 57.1% | 79.5% | - | - |

## Winner Ranking

| Rank | Experiment | Pass Count | Company Count | Critical Misses | Avg API Δ | Avg Time Δ | Avg Cost Δ | Avg Faithfulness | Avg Recall |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | contextual_all_2500_320 | 1 | 3 | 2 | 0.0% | 0.0% | 0.0% | 0.500 | 0.556 |

Failure Notes for `contextual_all_2500_320`
- 삼성전자 2024: retrieval_hit_at_k == 0 for business_overview_001
- NAVER 2024: retrieval_hit_at_k == 0 for business_overview_001
| 2 | contextual_parent_hybrid_2500_320 | 1 | 3 | 2 | -8.2% | -73.8% | -25.0% | 0.800 | 0.700 |

Failure Notes for `contextual_parent_hybrid_2500_320`
- SK하이닉스 2024: retrieval_hit_at_k == 0 for risk_analysis_001 | retrieval_hit_at_k dropped by 0.200
- NAVER 2024: missing-information smoke query hallucinated: NAVER 2024 사업보고서에서 신규사업 및 중단사업이 있다고 명시하나요? | retrieval_hit_at_k == 0 for business_overview_001
| 3 | contextual_parent_only_2500_320 | 0 | 3 | 4 | 86.0% | 82.4% | 86.1% | - | - |

Failure Notes for `contextual_parent_only_2500_320`
- 삼성전자 2024: retrieval_hit_at_k == 0 for risk_analysis_001
- SK하이닉스 2024: retrieval_hit_at_k == 0 for business_overview_001 | retrieval_hit_at_k == 0 for risk_analysis_001 | retrieval_hit_at_k dropped by 0.400
- NAVER 2024: missing-information smoke query hallucinated: NAVER 2024 사업보고서에서 신규사업 및 중단사업이 있다고 명시하나요? | retrieval_hit_at_k == 0 for business_overview_001
| 4 | contextual_selective_v2_2500_320 | 0 | 3 | 5 | 58.6% | 11.0% | 46.8% | - | - |

Failure Notes for `contextual_selective_v2_2500_320`
- 삼성전자 2024: risk smoke query failed: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가요? | retrieval_hit_at_k == 0 for business_overview_001 | retrieval_hit_at_k == 0 for risk_analysis_001 | retrieval_hit_at_k dropped by 0.200
- SK하이닉스 2024: retrieval_hit_at_k == 0 for business_overview_001 | retrieval_hit_at_k == 0 for business_overview_003 | retrieval_hit_at_k dropped by 0.400
- NAVER 2024: missing-information smoke query hallucinated: NAVER 2024 사업보고서에서 신규사업 및 중단사업이 있다고 명시하나요? | retrieval_hit_at_k == 0 for business_overview_001

## Selection Policy

The default candidate is ranked by:
1. cross-company screening pass count
2. critical category misses
3. average API call reduction ratio
4. average ingest time reduction ratio
5. full evaluation faithfulness
6. full evaluation context recall
