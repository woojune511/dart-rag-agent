# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | no | 1.821 | 917.419 | 2.5583 | 0.0% | 0.0% | 0.0% | 0 | 0 | 733 | 0.000 | 0.800 | 0.625 | 0.933 | 0.500 | 0.406 | 0.467 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | no | 1.881 | 80.673 | 0.1280 | 94.3% | 91.2% | 95.0% | 42 | 0 | 42 | 0.000 | 0.800 | 0.625 | 0.933 | - | - | - |
| contextual_parent_hybrid_2500_320 | 2500 | 320 | contextual_parent_hybrid | no | 2.012 | 1651.686 | 3.0853 | -4.8% | -80.0% | -20.6% | 42 | 726 | 768 | 0.000 | 0.800 | 0.650 | 0.933 | - | - | - |
| contextual_selective_v2_2500_320 | 2500 | 320 | contextual_selective_v2 | no | 2.091 | 393.761 | 0.5246 | 84.6% | 57.1% | 79.5% | 0 | 113 | 113 | 0.000 | 0.800 | 0.650 | 0.933 | - | - | - |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
