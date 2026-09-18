# Provider-free retrieval seed drift diagnosis

Diagnosed 2026-09-19 from clean `bf211011`, following the
[normal-application replay mismatch](compiler_axis_app_rehearsal.md).
**The first divergence is Chroma's HNSW dense-search result membership.**
One observed query-result substitution reproduces both historical seed lists
and complete candidate catalogs exactly. BM25, RRF, downstream selection and
candidate construction reproduce their recorded outputs with fixed inputs.
The native internal cause of variation across fresh processes remains unisolated.

## Observations

Two instrumented application prefixes use exact historical HTTP mock replies,
blocked external sockets, dummy credentials and verified temporary store copies.
Each performs 17 searches and 23 mocked requests: 19 embeddings, two routing and
requirements count/generation pairs. Both stop deliberately after candidates,
before Compiler. Their local HTTP 500 is this diagnostic stop, not provider failure
or a completed application result. No final answer or ledger is synthesized.

The requests, actual query vectors, filters, limits, plan, BM25 corpus/metadata/IDF
and all 17 BM25 ranked outputs are identical. Native dense results differ on
zero-based queries **4, 9 and 13**. These particular differences fall outside the
bounded RRF output; both prefixes produce the 530-candidate version. This initial
comparison establishes backend variation but alone does not explain the older
521/530 split.

Two further bounded native-backend probes use the same 17 frozen vectors and
filters directly, with no embedding client or model calls. Each opens a fresh
verified store copy, executes each query once, and repeats query 13 twice within
that process. Production RRF, cross-query merge, reranking, seed selection and
candidate construction are then replayed offline using the captured results.

| Native probe | Query 13: chunk 96 | Seed outcome | Catalog |
| --- | --- | --- | ---: |
| `backend_a` | Dense rank 62 of 64 | Historical app B, exact bytes/scores | 530 |
| `backend_b` | Absent from dense top 64 | Historical app A, exact bytes/scores | 521 |

These probes also differ on queries 4 and 16. Replacing **only query 13's observed
result** in either direction reproduces the other seed list and entire candidate
catalog exactly; the final eight documents remain identical. All other query
outputs, BM25 results and downstream owners stay fixed in that intervention.
Both within-process repeats of query 13 match their process's first result.
This does not establish stability for every query or process.

## Why one source changes the Compiler input

Query 13 is the already-planned acquisition query, not a new diagnostic query or
runtime special case. Its full source text is retained only in the local packet.
Chunk 96's BM25 rank is **47** in both runs. With dense rank 62, RRF gives
`1 / (60 + 62) + 1 / (60 + 47) = 0.017542515703998774`, placing it at merged rank
29 of 32. Without the dense contribution its score is `0.009345794392523364`,
below that search's top-32 cutoff.

The existing reranker scores the included source **0.7713886695501526**. It enters
the 32-document seed window and displaces chunk 76, whose retained score is
**0.7005925447101917**. Rebuilding the catalog yields **521 → 530**: the same four
removed and thirteen added candidates seen in the original app replay. The final
eight retrieved documents, all common candidates and all six previously used
answer-evidence candidates remain unchanged. This establishes input variation,
not a change in answer correctness or source faithfulness.

The relevant production boundaries are
[dense/BM25 search](../../src/storage/vector_store.py),
[rank fusion](../../src/storage/search_merge.py),
[cross-query merge and selection](../../src/agent/financial_retrieval_pipeline.py),
and [candidate construction](../../src/agent/financial_reconciliation_candidates.py).
No runtime branch, financial vocabulary, ranking rule or source limit was changed.

## Store and backend evidence

Both native probes expose the same **1,872 vectors with 3,072 dimensions**, IDs
and metadata, with identical content hashes. Installed Chroma is **1.5.5**;
observed HNSW configuration is L2, `ef_search=100`, `ef_construction=100`,
`max_neighbors=16`, `sync_threshold=1000`, `resize_factor=1.2`.

An independent float32 squared-L2 scan over the same report-filtered stored
vectors places chunk 96 at **rank 62**, distance **1.0787906646728516**. Native
distance when returned is **1.0787913799285889**. The distinct neighboring distances
show a membership difference, not just swapping equal-score ties. Sorting the
returned list by identity alone cannot recover a missing neighbor.

The evidence isolates variation to the native approximate-search boundary. It
does not identify whether index loading, graph traversal, threading or WAL
reconstruction causes the process variation. It also does not establish that
raising `ef_search` guarantees reproducibility or recommend a production setting.
Only disposable-copy `chroma.sqlite3` bytes change; the exact internal database
write cause remains unexamined. Original stores retain their hashes.

## Validation and next boundary

**64 recorded evidence assertions** pass, covering fixed inputs, reconstructed
RRF outputs, original seed bytes/scores, full catalogs and the query-13-only
intervention. Three negative transport/network controls and two documentation
gates pass separately. These are local diagnostic checks, not new benchmark
successes, model samples or full-app completion claims.

All **9,325 predecessor files**, **174 source files**, seven runtime owners,
**24 original store files** and local settings are preserved. New artifacts remain
ignored local evidence; the committed change is documentation only. Provider calls
and added accounting are **zero**; shared accounting stays **15.22872845 / 16**,
remaining **0.77127155**, pending zero. No cap increase or paid successor exists.

Next implement an experiment-local replay of the captured dense results, bound
to exact query vectors, filters, limits and source identity, then repeat the full
application integration replay in two fresh processes. BM25 and downstream code
should execute normally. This will validate integration under fixed retrieval
fixtures; actual dense-search stability remains a separate measured property.
Production search defaults and a fresh paid run require their own evidence.

Local evidence: [diagnosis](../../benchmarks/results/compiler_seed_drift_diagnosis_2026-09-19/diagnosis_review.json),
[64 assertions](../../benchmarks/results/compiler_seed_drift_diagnosis_2026-09-19/checks.json),
[negative controls and docs](../../benchmarks/results/compiler_seed_drift_diagnosis_2026-09-19/controls.json).
