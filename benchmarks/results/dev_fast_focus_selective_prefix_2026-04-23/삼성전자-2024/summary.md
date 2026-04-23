# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | NDCG@5 | P@5 | Entity | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall | Full Completeness | Refusal | Numeric Pass |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | yes | 2.493 | 535.908 | 1.0632 | 0.0% | 0.0% | 0.0% | 0 | 0 | 300 | 0.000 | 1.000 | - | - | - | 0.312 | 0.833 | 0.575 | 0.684 | 0.500 | - | 1.000 | 1.000 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | no | 2.620 | 57.930 | 0.1263 | 86.7% | 89.2% | 88.1% | 40 | 0 | 40 | 0.000 | 1.000 | - | - | - | 0.312 | 0.833 | 0.500 | 0.545 | 0.625 | - | 1.000 | 1.000 |
| plain_prefix_2500_320 | 2500 | 320 | plain | no | 0.422 | 10.371 | 0.0000 | 100.0% | 98.1% | 100.0% | 0 | 0 | 0 | 0.000 | 1.000 | - | - | - | 0.312 | 0.833 | 0.925 | 0.630 | 0.500 | - | 0.750 | 0.000 |
| contextual_selective_v2_prefix_2500_320 | 2500 | 320 | contextual_selective_v2 | yes | 0.393 | 141.292 | 0.3995 | 57.7% | 73.6% | 62.4% | 0 | 127 | 127 | 0.000 | 1.000 | - | - | - | 0.344 | 0.833 | 0.675 | 0.580 | 0.625 | - | 1.000 | 1.000 |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
