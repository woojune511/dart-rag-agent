# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | NDCG@5 | P@5 | Entity | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall | Full Completeness | Refusal | Numeric Pass |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | yes | 0.813 | 325.985 | 0.9111 | 0.0% | 0.0% | 0.0% | 0 | 0 | 300 | 0.000 | 1.000 | - | - | - | 0.312 | 0.833 | 0.875 | 0.587 | 0.500 | 0.625 | 1.000 | 1.000 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | no | 0.869 | 59.783 | 0.1276 | 86.7% | 81.7% | 86.0% | 40 | 0 | 40 | 0.000 | 0.750 | - | - | - | 0.312 | 0.750 | 0.850 | 0.573 | 0.625 | 0.600 | 1.000 | 1.000 |
| plain_prefix_2500_320 | 2500 | 320 | plain | no | 0.421 | 10.989 | 0.0000 | 100.0% | 96.6% | 100.0% | 0 | 0 | 0 | 0.000 | 1.000 | - | - | - | 0.312 | 0.833 | 1.000 | 0.525 | 0.500 | 0.500 | 0.750 | 0.000 |
| contextual_selective_v2_prefix_2500_320 | 2500 | 320 | contextual_selective_v2 | yes | 0.353 | 147.564 | 0.4057 | 57.7% | 54.7% | 55.5% | 0 | 127 | 127 | 0.000 | 1.000 | - | - | - | 0.312 | 0.833 | 0.750 | 0.504 | 0.500 | 0.525 | 0.750 | 1.000 |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
