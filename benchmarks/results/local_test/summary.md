# Benchmark Summary

| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Chunks | Contextualized | API Calls | Prompt Tokens | Output Tokens | Est. Cost (USD) | Screen Hit@k | Screen Section | Screen Citation | Full Faithfulness | Full Relevancy | Full Recall |
|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| plain_2500_320 | 2500 | 320 | plain | no | 1.395 | 19.183 | 300 | 0 | 0 | 0 | 0 | - | 0.800 | 0.125 | 0.733 | - | - | - |
| contextual_all_2500_320 | 2500 | 320 | contextual_all | yes | 0.345 | 558.723 | 300 | 300 | 300 | 86210 | 417372 | - | 1.000 | 0.250 | 0.733 | 0.400 | 0.651 | 0.500 |
| contextual_parent_only_2500_320 | 2500 | 320 | contextual_parent_only | no | 0.337 | 67.964 | 300 | 40 | 40 | 20424 | 48899 | - | 0.800 | 0.175 | 0.733 | - | - | - |
| contextual_selective_2500_320 | 2500 | 320 | contextual_selective | no | 0.389 | 331.002 | 300 | 289 | 289 | 81435 | 357281 | - | 0.800 | 0.150 | 0.733 | - | - | - |
| contextual_1500_200 | 1500 | 200 | contextual_all | no | 1.066 | 774.632 | 502 | 502 | 502 | 144063 | 655128 | - | 0.800 | 0.225 | 0.733 | 0.640 | 0.500 | 0.300 |

## Reading Guide

- `Screen Pass` means the run cleared the strict quality floor before full evaluation.
- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.
- Full metrics are only populated for shortlisted candidates that proceed to stage 2.
- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.
