# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | no | 1.145 | 334.913 | 0.9139 | 0.0% | 0.0% | 0.0% | 0 | 0 | 300 | 0.000 | 0.800 | 0.300 | 0.800 | 0.400 | 0.764 | 0.600 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | no | 1.302 | 59.321 | 0.1279 | 86.7% | 82.3% | 86.0% | 40 | 0 | 40 | 0.000 | 0.800 | 0.275 | 0.733 | - | - | - |
| contextual_parent_hybrid_2500_320 | 2500 | 320 | contextual_parent_hybrid | yes | 1.065 | 370.160 | 1.0285 | -7.0% | -10.5% | -12.5% | 40 | 281 | 321 | 0.000 | 1.000 | 0.375 | 0.800 | 0.800 | 0.639 | 0.700 |
| contextual_selective_v2_2500_320 | 2500 | 320 | contextual_selective_v2 | no | 0.300 | 151.629 | 0.4013 | 57.7% | 54.7% | 56.1% | 0 | 127 | 127 | 0.000 | 0.600 | 0.275 | 0.733 | - | - | - |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
