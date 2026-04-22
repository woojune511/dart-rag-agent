# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | NDCG@5 | P@5 | Entity | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall | Full Completeness | Refusal | Numeric Pass |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| contextual_all_2500_320 | 2500 | 320 | contextual_all | no | 1.295 | 572.056 | 1.0590 | 0.0% | 0.0% | 0.0% | 0 | 0 | 300 | 0.000 | 0.800 | - | - | - | 0.125 | 0.800 | - | - | - | - | - | - |
| plain_1500_200 | 1500 | 200 | plain | no | 0.509 | 16.563 | 0.0000 | 100.0% | 97.1% | 100.0% | 0 | 0 | 0 | 0.000 | 0.400 | - | - | - | 0.050 | 0.667 | - | - | - | - | - | - |
| plain_graph_1500_200 | 1500 | 200 | plain | no | 1.472 | 29.841 | 0.0000 | 100.0% | 94.8% | 100.0% | 0 | 0 | 0 | 0.000 | 0.400 | - | - | - | 0.075 | 0.667 | - | - | - | - | - | - |
| plain_2500_320 | 2500 | 320 | plain | no | 0.568 | 10.176 | 0.0000 | 100.0% | 98.2% | 100.0% | 0 | 0 | 0 | 0.000 | 0.600 | - | - | - | 0.100 | 0.733 | - | - | - | - | - | - |
| plain_graph_2500_320 | 2500 | 320 | plain | no | 0.487 | 10.173 | 0.0000 | 100.0% | 98.2% | 100.0% | 0 | 0 | 0 | 0.000 | 0.400 | - | - | - | 0.125 | 0.667 | - | - | - | - | - | - |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.
- `Contam` is the average screening contamination rate across retrieved top-k docs.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
