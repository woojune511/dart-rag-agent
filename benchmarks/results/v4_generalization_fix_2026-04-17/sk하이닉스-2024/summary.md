# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | no | 0.418 | 186.761 | 0.5626 | 0.0% | 0.0% | 0.0% | 0 | 0 | 179 | 0.000 | 1.000 | 0.175 | 1.000 | 0.340 | 0.484 | 0.600 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | no | 0.442 | 45.840 | 0.1239 | 77.1% | 75.5% | 78.0% | 41 | 0 | 41 | 0.000 | 0.600 | 0.250 | 0.867 | - | - | - |
| contextual_parent_hybrid_2500_320 | 2500 | 320 | contextual_parent_hybrid | no | 0.190 | 698.213 | 0.9539 | -12.8% | -273.9% | -69.6% | 41 | 161 | 202 | 0.000 | 1.000 | 0.275 | 1.000 | - | - | - |
| contextual_selective_v2_2500_320 | 2500 | 320 | contextual_selective_v2 | no | 0.735 | 133.740 | 0.3907 | 33.5% | 28.4% | 30.6% | 0 | 119 | 119 | 0.000 | 0.400 | 0.100 | 0.800 | - | - | - |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
