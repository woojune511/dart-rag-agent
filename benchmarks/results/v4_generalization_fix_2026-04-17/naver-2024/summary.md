# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | no | 2.655 | 1129.565 | 2.6271 | 0.0% | 0.0% | 0.0% | 0 | 0 | 733 | 0.000 | 0.800 | 0.525 | 0.933 | 0.360 | 0.409 | 0.567 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | no | 2.706 | 94.000 | 0.1385 | 94.3% | 91.7% | 94.7% | 42 | 0 | 42 | 0.000 | 0.800 | 0.475 | 0.933 | - | - | - |
| contextual_parent_hybrid_2500_320 | 2500 | 320 | contextual_parent_hybrid | no | 1.834 | 1196.127 | 2.6585 | -1.0% | -5.9% | -1.2% | 42 | 698 | 740 | 0.000 | 0.800 | 0.575 | 0.933 | - | - | - |
| contextual_selective_v2_2500_320 | 2500 | 320 | contextual_selective_v2 | no | 0.619 | 187.148 | 0.2958 | 87.7% | 83.4% | 88.7% | 0 | 90 | 90 | 0.000 | 0.800 | 0.500 | 0.933 | - | - | - |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
