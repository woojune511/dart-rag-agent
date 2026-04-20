# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | yes | 0.630 | 317.568 | 0.9015 | 0.0% | 0.0% | 0.0% | 0 | 0 | 300 | 0.000 | 1.000 | 0.325 | 0.800 | 0.600 | 0.712 | 0.650 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | no | 0.713 | 55.947 | 0.1311 | 86.7% | 82.4% | 85.5% | 40 | 0 | 40 | 0.000 | 0.800 | 0.300 | 0.800 | - | - | - |
| contextual_selective_v2_2500_320 | 2500 | 320 | contextual_selective_v2 | no | 1.283 | 151.407 | 0.4001 | 57.7% | 52.3% | 55.6% | 0 | 127 | 127 | 0.000 | 0.600 | 0.250 | 0.733 | - | - | - |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
