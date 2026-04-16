# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | yes | 1.516 | 209.846 | 0.5714 | 0.0% | 0.0% | 0.0% | 0 | 0 | 179 | 0.000 | 1.000 | 0.175 | 1.000 | 0.600 | 0.743 | 0.600 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | no | 1.414 | 55.270 | 0.1292 | 77.1% | 73.7% | 77.4% | 41 | 0 | 41 | 0.000 | 0.600 | 0.250 | 0.867 | - | - | - |
| contextual_parent_hybrid_2500_320 | 2500 | 320 | contextual_parent_hybrid | no | 0.957 | 484.335 | 0.8100 | -12.8% | -130.8% | -41.8% | 41 | 161 | 202 | 0.000 | 0.800 | 0.275 | 0.933 | - | - | - |
| contextual_selective_v2_2500_320 | 2500 | 320 | contextual_selective_v2 | no | 0.319 | 375.203 | 0.5438 | 33.5% | -78.8% | 4.8% | 0 | 119 | 119 | 0.000 | 0.600 | 0.100 | 0.867 | - | - | - |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
