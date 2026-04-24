# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | NDCG@5 | P@5 | Entity | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall | Full Completeness | Refusal | Numeric Pass |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | no | 0.594 | 322.633 | 0.9172 | 0.0% | 0.0% | 0.0% | 0 | 0 | 300 | 0.000 | 0.750 | - | - | - | 0.312 | 0.833 | 0.800 | 0.560 | 0.500 | 0.650 | 1.000 | 1.000 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | no | 0.518 | 56.690 | 0.1280 | 86.7% | 82.4% | 86.0% | 40 | 0 | 40 | 0.000 | 0.750 | - | - | - | 0.281 | 0.750 | 0.800 | 0.580 | 0.625 | 0.775 | 1.000 | 1.000 |
| plain_prefix_2500_320 | 2500 | 320 | plain | yes | 0.310 | 7.550 | 0.0000 | 100.0% | 97.7% | 100.0% | 0 | 0 | 0 | 0.000 | 1.000 | - | - | - | 0.312 | 0.833 | 1.000 | 0.634 | 0.500 | 0.550 | 0.750 | 0.000 |
| contextual_selective_v2_prefix_2500_320 | 2500 | 320 | contextual_selective_v2 | yes | 0.307 | 142.364 | 0.4011 | 57.7% | 55.9% | 56.3% | 0 | 127 | 127 | 0.000 | 1.000 | - | - | - | 0.312 | 0.833 | 1.000 | 0.525 | 0.625 | 0.350 | 0.750 | 0.000 |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
