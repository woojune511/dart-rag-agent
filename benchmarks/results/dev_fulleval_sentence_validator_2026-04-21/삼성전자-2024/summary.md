# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | yes | 1.844 | 328.106 | 0.8959 | 0.0% | 0.0% | 0.0% | 0 | 0 | 300 | 0.000 | 1.000 | 0.325 | 0.867 | 0.540 | 0.586 | 0.600 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | yes | 2.035 | 66.841 | 0.1283 | 86.7% | 79.6% | 85.7% | 40 | 0 | 40 | 0.000 | 1.000 | 0.325 | 0.800 | 0.700 | 0.616 | 0.720 |
| contextual_selective_v2_2500_320 | 2500 | 320 | contextual_selective_v2 | no | 1.065 | 158.601 | 0.4004 | 57.7% | 51.7% | 55.3% | 0 | 127 | 127 | 0.000 | 0.600 | 0.225 | 0.733 | - | - | - |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
