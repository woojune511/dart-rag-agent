# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | NDCG@5 | P@5 | Entity | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall | Full Completeness | Refusal | Numeric Pass |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | yes | 0.274 | 550.957 | 1.0620 | 0.0% | 0.0% | 0.0% | 0 | 0 | 300 | 0.000 | 0.800 | - | - | - | 0.125 | 0.800 | - | - | - | - | - | - |
| plain_1500_200 | 1500 | 200 | plain | no | 0.245 | 12.736 | 0.0000 | 100.0% | 97.7% | 100.0% | 0 | 0 | 0 | 0.000 | 0.400 | - | - | - | 0.050 | 0.667 | - | - | - | - | - | - |
| plain_graph_1500_200 | 1500 | 200 | plain | no | 0.239 | 12.575 | 0.0000 | 100.0% | 97.7% | 100.0% | 0 | 0 | 0 | 0.000 | 0.400 | - | - | - | 0.056 | 0.667 | - | - | - | - | - | - |
| plain_2500_320 | 2500 | 320 | plain | no | 0.349 | 7.545 | 0.0000 | 100.0% | 98.6% | 100.0% | 0 | 0 | 0 | 0.000 | 0.600 | - | - | - | 0.100 | 0.733 | - | - | - | - | - | - |
| plain_graph_2500_320 | 2500 | 320 | plain | no | 0.229 | 7.678 | 0.0000 | 100.0% | 98.6% | 100.0% | 0 | 0 | 0 | 0.000 | 0.600 | - | - | - | 0.078 | 0.733 | - | - | - | - | - | - |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
