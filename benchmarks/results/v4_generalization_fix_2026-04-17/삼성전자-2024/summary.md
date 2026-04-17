# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | no | 0.668 | 559.522 | 1.0689 | 0.0% | 0.0% | 0.0% | 0 | 0 | 300 | 0.000 | 0.800 | 0.300 | 0.800 | 0.660 | 0.772 | 0.600 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | no | 0.776 | 73.323 | 0.1300 | 86.7% | 86.9% | 87.8% | 40 | 0 | 40 | 0.000 | 1.000 | 0.300 | 0.800 | - | - | - |
| contextual_parent_hybrid_2500_320 | 2500 | 320 | contextual_parent_hybrid | no | 0.548 | 364.091 | 1.0194 | -7.0% | 34.9% | 4.6% | 40 | 281 | 321 | 0.000 | 1.000 | 0.350 | 0.800 | - | - | - |
| contextual_selective_v2_2500_320 | 2500 | 320 | contextual_selective_v2 | no | 0.412 | 151.583 | 0.4011 | 57.7% | 72.9% | 62.5% | 0 | 127 | 127 | 0.000 | 0.600 | 0.250 | 0.733 | - | - | - |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
