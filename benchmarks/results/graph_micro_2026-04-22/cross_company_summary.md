# Cross-Company Summary

## Per-Company Results

| Company | Experiment | Screen Pass | Critical Misses | Hit@k | Section | Citation | Contam | API Calls | Est. Cost (USD) | Ingest (s) | API Δ | Time Δ | Cost Δ | Full Faithfulness | Full Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성전자 2024 | contextual_all_2500_320 | yes | 0 | 0.800 | 0.125 | 0.800 | 0.000 | 300 | 1.0620 | 550.957 | 0.0% | 0.0% | 0.0% | - | - |
| 삼성전자 2024 | plain_1500_200 | no | 0 | 0.400 | 0.050 | 0.667 | 0.000 | 0 | 0.0000 | 12.736 | 100.0% | 97.7% | 100.0% | - | - |
| 삼성전자 2024 | plain_graph_1500_200 | no | 0 | 0.400 | 0.056 | 0.667 | 0.000 | 0 | 0.0000 | 12.575 | 100.0% | 97.7% | 100.0% | - | - |
| 삼성전자 2024 | plain_2500_320 | no | 0 | 0.600 | 0.100 | 0.733 | 0.000 | 0 | 0.0000 | 7.545 | 100.0% | 98.6% | 100.0% | - | - |
| 삼성전자 2024 | plain_graph_2500_320 | no | 0 | 0.600 | 0.078 | 0.733 | 0.000 | 0 | 0.0000 | 7.678 | 100.0% | 98.6% | 100.0% | - | - |

## Winner Ranking

| Rank | Experiment | Pass Count | Company Count | Critical Misses | Avg API Δ | Avg Time Δ | Avg Cost Δ | Avg Faithfulness | Avg Recall |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | contextual_all_2500_320 | 1 | 1 | 0 | 0.0% | 0.0% | 0.0% | - | - |
| 2 | plain_2500_320 | 0 | 1 | 0 | 100.0% | 98.6% | 100.0% | - | - |

Failure Notes for `plain_2500_320`
- 삼성전자 2024: risk smoke query failed: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가? | answerable smoke query abstained: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가? | retrieval_hit_at_k dropped by 0.200
| 3 | plain_graph_2500_320 | 0 | 1 | 0 | 100.0% | 98.6% | 100.0% | - | - |

Failure Notes for `plain_graph_2500_320`
- 삼성전자 2024: answerable smoke query abstained: 2024년 삼성전자의 연결 기준 매출액은 얼마인가? | retrieval_hit_at_k dropped by 0.200
| 4 | plain_graph_1500_200 | 0 | 1 | 0 | 100.0% | 97.7% | 100.0% | - | - |

Failure Notes for `plain_graph_1500_200`
- 삼성전자 2024: answerable smoke query abstained: 2024년 삼성전자의 연결 기준 매출액은 얼마인가? | retrieval_hit_at_k dropped by 0.400
| 5 | plain_1500_200 | 0 | 1 | 0 | 100.0% | 97.7% | 100.0% | - | - |

Failure Notes for `plain_1500_200`
- 삼성전자 2024: retrieval_hit_at_k dropped by 0.400

## Selection Policy

The default candidate is ranked by:
1. cross-company screening pass count
2. critical category misses
3. average API call reduction ratio
4. average ingest time reduction ratio
5. full evaluation faithfulness
6. full evaluation context recall
