# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | no | 0.841 | 15.050 | 0.0000 | - | 0.0% | - | 0 | 0 | 0 | 0.000 | 0.600 | 0.275 | 0.867 | - | - | - |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | yes | 0.741 | 16.031 | 0.0000 | - | -6.5% | - | 40 | 0 | 0 | 0.000 | 0.800 | 0.275 | 0.867 | - | - | - |
| contextual_selective_v2_2500_320 | 2500 | 320 | contextual_selective_v2 | no | 0.649 | 7.790 | 0.0000 | - | 48.2% | - | 0 | 127 | 0 | 0.000 | 0.400 | 0.225 | 0.800 | - | - | - |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
