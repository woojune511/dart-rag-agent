# Cross-Company Summary

## Per-Company Results

| Company | Experiment | Screen Pass | Critical Misses | Hit@k | Section | Citation | Contam | API Calls | Est. Cost (USD) | Ingest (s) | API Δ | Time Δ | Cost Δ | Full Faithfulness | Full Recall |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 삼성전자 2024 | contextual_all_2500_320 | yes | 0 | 1.000 | 0.312 | 0.833 | 0.000 | 300 | 1.0632 | 535.908 | 0.0% | 0.0% | 0.0% | 0.575 | 0.500 |
| 삼성전자 2024 | contextual_parent_only_2500_320 | no | 0 | 1.000 | 0.312 | 0.833 | 0.000 | 40 | 0.1263 | 57.930 | 86.7% | 89.2% | 88.1% | 0.500 | 0.625 |
| 삼성전자 2024 | plain_prefix_2500_320 | no | 0 | 1.000 | 0.312 | 0.833 | 0.000 | 0 | 0.0000 | 10.371 | 100.0% | 98.1% | 100.0% | 0.925 | 0.500 |
| 삼성전자 2024 | contextual_selective_v2_prefix_2500_320 | yes | 0 | 1.000 | 0.344 | 0.833 | 0.000 | 127 | 0.3995 | 141.292 | 57.7% | 73.6% | 62.4% | 0.675 | 0.625 |

## Winner Ranking

| Rank | Experiment | Pass Count | Company Count | Critical Misses | Avg API Δ | Avg Time Δ | Avg Cost Δ | Avg Faithfulness | Avg Recall |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | contextual_selective_v2_prefix_2500_320 | 1 | 1 | 0 | 57.7% | 73.6% | 62.4% | 0.675 | 0.625 |
| 2 | contextual_all_2500_320 | 1 | 1 | 0 | 0.0% | 0.0% | 0.0% | 0.575 | 0.500 |
| 3 | plain_prefix_2500_320 | 0 | 1 | 0 | 100.0% | 98.1% | 100.0% | 0.925 | 0.500 |

Failure Notes for `plain_prefix_2500_320`
- 삼성전자 2024: risk smoke query failed: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가요? | answerable smoke query abstained: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가요?
| 4 | contextual_parent_only_2500_320 | 0 | 1 | 0 | 86.7% | 89.2% | 88.1% | 0.500 | 0.625 |

Failure Notes for `contextual_parent_only_2500_320`
- 삼성전자 2024: risk smoke query failed: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가요? | answerable smoke query abstained: 삼성전자 2024 사업보고서에서 주요 재무 리스크는 무엇인가요?

## Selection Policy

The default candidate is ranked by:
1. cross-company screening pass count
2. critical category misses
3. average API call reduction ratio
4. average ingest time reduction ratio
5. full evaluation faithfulness
6. full evaluation context recall
