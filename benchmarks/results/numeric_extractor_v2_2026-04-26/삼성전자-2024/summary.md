# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | NDCG@5 | P@5 | Entity | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall | Full Completeness | Refusal | Numeric Pass |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | no | 0.727 | 286.648 | 0.9186 | 0.0% | 0.0% | 0.0% | 0 | 0 | 300 | 0.000 | 0.750 | - | - | - | 0.250 | 0.833 | 0.700 | 0.684 | 0.500 | 0.600 | 1.000 | 1.000 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | no | 0.691 | 52.791 | 0.1295 | 86.7% | 81.6% | 85.9% | 40 | 0 | 40 | 0.000 | 0.750 | - | - | - | 0.312 | 0.750 | 0.875 | 0.643 | 0.625 | 0.700 | 1.000 | 1.000 |
| plain_prefix_2500_320 | 2500 | 320 | plain | yes | 0.397 | 9.129 | 0.0000 | 100.0% | 96.8% | 100.0% | 0 | 0 | 0 | 0.000 | 1.000 | - | - | - | 0.312 | 0.833 | 1.000 | 0.454 | 0.500 | 0.500 | 0.750 | 0.000 |
| contextual_selective_v2_prefix_2500_320 | 2500 | 320 | contextual_selective_v2 | yes | 0.474 | 140.888 | 0.4006 | 57.7% | 50.8% | 56.4% | 0 | 127 | 127 | 0.000 | 1.000 | - | - | - | 0.312 | 0.833 | 0.825 | 0.615 | 0.500 | 0.700 | 1.000 | 1.000 |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
