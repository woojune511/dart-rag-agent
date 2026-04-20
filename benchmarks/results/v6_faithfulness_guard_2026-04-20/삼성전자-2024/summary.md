# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | yes | 0.618 | 545.977 | 1.0775 | 0.0% | 0.0% | 0.0% | 0 | 0 | 300 | 0.000 | 1.000 | 0.350 | 0.867 | 0.500 | 0.700 | 0.600 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | yes | 0.547 | 54.233 | 0.1287 | 86.7% | 90.1% | 88.1% | 40 | 0 | 40 | 0.000 | 1.000 | 0.300 | 0.800 | 0.660 | 0.684 | 0.700 |
| contextual_selective_v2_2500_320 | 2500 | 320 | contextual_selective_v2 | no | 0.233 | 140.410 | 0.4052 | 57.7% | 74.3% | 62.4% | 0 | 127 | 127 | 0.000 | 0.600 | 0.250 | 0.733 | - | - | - |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
