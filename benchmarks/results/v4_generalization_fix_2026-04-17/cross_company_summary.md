# Cross-Company Summary

## Per-Company Results

| Company | Experiment | Screen Pass | Critical Misses | Hit@k | Section | Citation | Contam | API Calls | Est. Cost (USD) | Ingest (s) | API Δ | Time Δ | Cost Δ | Full Faithfulness | Full Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성전자 2024 | contextual_all_2500_320 | no | 1 | 0.800 | 0.300 | 0.800 | 0.000 | 300 | 1.0689 | 559.522 | 0.0% | 0.0% | 0.0% | 0.660 | 0.600 |
| 삼성전자 2024 | contextual_parent_only_2500_320 | no | 0 | 1.000 | 0.300 | 0.800 | 0.000 | 40 | 0.1300 | 73.323 | 86.7% | 86.9% | 87.8% | - | - |
| 삼성전자 2024 | contextual_parent_hybrid_2500_320 | no | 0 | 1.000 | 0.350 | 0.800 | 0.000 | 321 | 1.0194 | 364.091 | -7.0% | 34.9% | 4.6% | - | - |
| 삼성전자 2024 | contextual_selective_v2_2500_320 | no | 2 | 0.600 | 0.250 | 0.733 | 0.000 | 127 | 0.4011 | 151.583 | 57.7% | 72.9% | 62.5% | - | - |
| SK하이닉스 2024 | contextual_all_2500_320 | no | 0 | 1.000 | 0.175 | 1.000 | 0.000 | 179 | 0.5626 | 186.761 | 0.0% | 0.0% | 0.0% | 0.340 | 0.600 |
| SK하이닉스 2024 | contextual_parent_only_2500_320 | no | 2 | 0.600 | 0.250 | 0.867 | 0.000 | 41 | 0.1239 | 45.840 | 77.1% | 75.5% | 78.0% | - | - |
| SK하이닉스 2024 | contextual_parent_hybrid_2500_320 | no | 0 | 1.000 | 0.275 | 1.000 | 0.000 | 202 | 0.9539 | 698.213 | -12.8% | -273.9% | -69.6% | - | - |
| SK하이닉스 2024 | contextual_selective_v2_2500_320 | no | 3 | 0.400 | 0.100 | 0.800 | 0.000 | 119 | 0.3907 | 133.740 | 33.5% | 28.4% | 30.6% | - | - |
| NAVER 2024 | contextual_all_2500_320 | no | 1 | 0.800 | 0.525 | 0.933 | 0.000 | 733 | 2.6271 | 1129.565 | 0.0% | 0.0% | 0.0% | 0.360 | 0.567 |
| NAVER 2024 | contextual_parent_only_2500_320 | no | 1 | 0.800 | 0.475 | 0.933 | 0.000 | 42 | 0.1385 | 94.000 | 94.3% | 91.7% | 94.7% | - | - |
| NAVER 2024 | contextual_parent_hybrid_2500_320 | no | 1 | 0.800 | 0.575 | 0.933 | 0.000 | 740 | 2.6585 | 1196.127 | -1.0% | -5.9% | -1.2% | - | - |
| NAVER 2024 | contextual_selective_v2_2500_320 | no | 1 | 0.800 | 0.500 | 0.933 | 0.000 | 90 | 0.2958 | 187.148 | 87.7% | 83.4% | 88.7% | - | - |

## Winner Ranking

| Rank | Experiment | Pass Count | Company Count | Critical Misses | Avg API Δ | Avg Time Δ | Avg Cost Δ | Avg Faithfulness | Avg Recall |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | contextual_parent_hybrid_2500_320 | 0 | 3 | 1 | -6.9% | -81.6% | -22.0% | - | - |

Failure Notes for `contextual_parent_hybrid_2500_320`
- 삼성전자 2024: answerable smoke query abstained: 삼성전자 2024 사업보고서에서 연결 기준 매출액은 얼마인가요? | answerable smoke query abstained: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가요? | answerable smoke query abstained: 삼성전자 2024 사업보고서에서 연구개발비용은 얼마이며 어떻게 회계처리되나요?
- SK하이닉스 2024: answerable smoke query abstained: SK하이닉스 2024 사업보고서에서 연결 기준 매출액은 얼마인가요?
- NAVER 2024: answerable smoke query abstained: NAVER 2024 사업보고서에서 연결 기준 영업수익은 얼마인가요? | missing-information smoke query hallucinated: NAVER 2024 사업보고서에서 신규사업 및 중단사업이 있다고 명시하나요? | retrieval_hit_at_k == 0 for business_overview_001
| 2 | contextual_all_2500_320 | 0 | 3 | 2 | 0.0% | 0.0% | 0.0% | 0.453 | 0.589 |

Failure Notes for `contextual_all_2500_320`
- 삼성전자 2024: retrieval_hit_at_k == 0 for business_overview_001
- SK하이닉스 2024: answerable smoke query abstained: SK하이닉스 2024 사업보고서에서 주요 재무 리스크는 무엇인가요?
- NAVER 2024: answerable smoke query abstained: NAVER 2024 사업보고서에서 연결 기준 영업수익은 얼마인가요? | missing-information smoke query hallucinated: NAVER 2024 사업보고서에서 신규사업 및 중단사업이 있다고 명시하나요? | retrieval_hit_at_k == 0 for business_overview_001
| 3 | contextual_parent_only_2500_320 | 0 | 3 | 3 | 86.0% | 84.7% | 86.8% | - | - |

Failure Notes for `contextual_parent_only_2500_320`
- 삼성전자 2024: answerable smoke query abstained: 삼성전자 2024 사업보고서에서 연결 기준 매출액은 얼마인가요? | answerable smoke query abstained: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가요? | answerable smoke query abstained: 삼성전자 2024 사업보고서에서 연구개발비용은 얼마이며 어떻게 회계처리되나요?
- SK하이닉스 2024: answerable smoke query abstained: SK하이닉스 2024 사업보고서에서 연결 기준 매출액은 얼마인가요? | answerable smoke query abstained: SK하이닉스 2024 사업보고서에서 연구개발비용은 얼마이며 매출 대비 비율은 얼마인가요? | retrieval_hit_at_k == 0 for business_overview_001 | retrieval_hit_at_k == 0 for risk_analysis_001 | retrieval_hit_at_k dropped by 0.400
- NAVER 2024: answerable smoke query abstained: NAVER 2024 사업보고서에서 연결 기준 영업수익은 얼마인가요? | missing-information smoke query hallucinated: NAVER 2024 사업보고서에서 신규사업 및 중단사업이 있다고 명시하나요? | retrieval_hit_at_k == 0 for business_overview_001
| 4 | contextual_selective_v2_2500_320 | 0 | 3 | 6 | 59.6% | 61.6% | 60.6% | - | - |

Failure Notes for `contextual_selective_v2_2500_320`
- 삼성전자 2024: risk smoke query failed: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가요? | answerable smoke query abstained: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가요? | answerable smoke query abstained: 삼성전자 2024 사업보고서에서 연구개발비용은 얼마이며 어떻게 회계처리되나요? | retrieval_hit_at_k == 0 for business_overview_001 | retrieval_hit_at_k == 0 for risk_analysis_001 | retrieval_hit_at_k dropped by 0.200
- SK하이닉스 2024: answerable smoke query abstained: SK하이닉스 2024 사업보고서에서 연구개발비용은 얼마이며 매출 대비 비율은 얼마인가요? | retrieval_hit_at_k == 0 for business_overview_001 | retrieval_hit_at_k == 0 for business_overview_003 | retrieval_hit_at_k == 0 for risk_analysis_001 | retrieval_hit_at_k dropped by 0.600
- NAVER 2024: answerable smoke query abstained: NAVER 2024 사업보고서에서 연결 기준 영업수익은 얼마인가요? | missing-information smoke query hallucinated: NAVER 2024 사업보고서에서 신규사업 및 중단사업이 있다고 명시하나요? | retrieval_hit_at_k == 0 for business_overview_001

## Selection Policy

The default candidate is ranked by:
1. cross-company screening pass count
2. critical category misses
3. average API call reduction ratio
4. average ingest time reduction ratio
5. full evaluation faithfulness
6. full evaluation context recall
