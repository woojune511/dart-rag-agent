# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | API Δ | Time Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| plain_2500_320 | 2500 | 320 | plain | no | 1.019 | 10.822 | 100.0% | 96.7% | 0 | 0 | 0 | 0.000 | 0.800 | 0.225 | 0.800 | - | - | - |
| contextual_all_2500_320 | 2500 | 320 | contextual_all | yes | 0.929 | 323.270 | 0.0% | 0.0% | 0 | 0 | 300 | 0.000 | 1.000 | 0.400 | 0.800 | 0.460 | 0.624 | 0.500 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | yes | 0.311 | 71.696 | 86.7% | 77.8% | 40 | 0 | 40 | 0.000 | 1.000 | 0.375 | 0.800 | 0.620 | 0.491 | 0.500 |
| contextual_parent_hybrid_2500_320 | 2500 | 320 | contextual_parent_hybrid | yes | 0.854 | 365.201 | -7.0% | -13.0% | 40 | 281 | 321 | 0.000 | 1.000 | 0.475 | 0.800 | 0.100 | 0.499 | 0.400 |
| contextual_selective_v2_2500_320 | 2500 | 320 | contextual_selective_v2 | no | 0.860 | 150.839 | 57.7% | 53.3% | 0 | 127 | 127 | 0.000 | 0.800 | 0.325 | 0.800 | - | - | - |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
