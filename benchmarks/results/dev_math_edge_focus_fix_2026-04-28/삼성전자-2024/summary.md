# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | NDCG@5 | P@5 | Entity | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall | Full Completeness | Refusal | Numeric Pass |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_selective_v2_prefix_2500_320 | 2500 | 320 | contextual_selective_v2 | yes | 0.328 | 268.983 | 0.4072 | 0.0% | 0.0% | 0.0% | 0 | 128 | 128 | 0.000 | 1.000 | - | - | - | 0.292 | 1.000 | 1.000 | 0.380 | 0.833 | 0.333 | 1.000 | 0.333 |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
