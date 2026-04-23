# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | NDCG@5 | P@5 | Entity | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall | Full Completeness | Refusal | Numeric Pass |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | yes | 0.828 | 328.156 | 0.9100 | 0.0% | 0.0% | 0.0% | 0 | 0 | 300 | 0.000 | 1.000 | - | - | - | 0.344 | 0.833 | 0.825 | 0.575 | 0.562 | 0.525 | 1.000 | 1.000 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | yes | 0.746 | 51.644 | 0.1239 | 86.7% | 84.3% | 86.4% | 40 | 0 | 40 | 0.000 | 1.000 | - | - | - | 0.344 | 0.833 | 0.750 | 0.645 | 0.625 | 0.600 | 1.000 | 1.000 |
| plain_prefix_2500_320 | 2500 | 320 | plain | yes | 0.531 | 11.499 | 0.0000 | 100.0% | 96.5% | 100.0% | 0 | 0 | 0 | 0.000 | 1.000 | - | - | - | 0.312 | 0.833 | 1.000 | 0.679 | 0.500 | 0.425 | 0.750 | 0.000 |
| contextual_selective_v2_prefix_2500_320 | 2500 | 320 | contextual_selective_v2 | yes | 0.597 | 155.013 | 0.4022 | 57.7% | 52.8% | 55.8% | 0 | 127 | 127 | 0.000 | 1.000 | - | - | - | 0.281 | 0.833 | 0.625 | 0.467 | 0.500 | 0.475 | 0.750 | 0.000 |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
