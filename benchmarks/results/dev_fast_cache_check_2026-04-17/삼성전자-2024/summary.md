# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | yes | 0.637 | 0.000 | 0.0000 | - | - | - | 0 | 0 | 0 | 0.000 | 1.000 | 0.562 | 0.833 | 0.500 | 0.801 | 0.500 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | yes | 0.757 | 0.000 | 0.0000 | - | - | - | 40 | 0 | 0 | 0.000 | 1.000 | 0.500 | 0.833 | 0.500 | 0.749 | 0.750 |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
