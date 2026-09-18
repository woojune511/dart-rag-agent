# Full-application replay with fixed dense results

Completed 2026-09-19 from clean `b4ef729c`, following the
[native-search drift diagnosis](retrieval_seed_drift_diagnosis.md).
**Both fresh-process application replays complete with HTTP 200, both requested
outputs and an intact ledger.** Their SDK request bytes, dense fixtures, candidate
catalogs, answers and evidence agree. Only measured search durations differ.
This is integration evidence under fixed retrieval and model-response fixtures;
native approximate-search repeatability remains unproven.

## Replay boundary

An experiment-local wrapper replaces Chroma's private query-result boundary with
17 captured result lists. ID order and distances come from the diagnosis's
`backend_b`; raw documents and metadata come from its protected application
observations. These reconstruct the four result fields consumed by the existing
Chroma adapter, not a purported capture of the complete backend wire response.
This historical result sequence reproduces the original 521-candidate input to
which the immutable Compiler HTTP fixtures belong. It is not a search-quality
winner or a new production selection rule.

Before a query, the wrapper verifies the original store-copy file map, collection
configuration, all 1,872 stored vectors/IDs/metadata, BM25 corpus/IDF and the raw
source bytes returned by the fixtures. It binds the exact store object. Each
search must match its ordered query, vector, filter, result limit and RRF limit.
Mismatch, repetition, extra calls, changed source or fixture mutation causes a
terminal caller stop. Native query dispatch is independently forbidden, with no
fallback. Returned results are owned copies.

The real application continues to execute embedding SDK calls through exact HTTP
mocks, document hydration, BM25, RRF, cross-query merging, seed selection,
candidate construction, Compiler validation, arithmetic, answer assembly and
ledger construction. Every BM25, hydrated dense and RRF result is checked against
the captured inputs/outputs without replacing its calculated values.

The existing full-app harness is copied with seven explicit local edits to load,
install, bind, check and record this boundary. External sockets remain blocked;
credentials are dummy values, HTTP transport is mock-only, and ingest/store writes
are forbidden. Fixtures preload before application execution. Historical result
files cannot be read while the app runs; no accepted answer or diagnostic graph
state is inserted into prompts or phase state.

## Observed results

| Fresh process | HTTP mock pairs | Dense fixtures | Public result | Ledger |
| --- | ---: | ---: | --- | --- |
| A | 27 exact | 17 exact | HTTP 200, 2/2 outputs | Complete, integrity ok |
| B | 27 exact | 17 exact | HTTP 200, 2/2 outputs | Complete, integrity ok |

Both stores are ready, compatible and non-degraded with 1,872 indexed chunks.
Each HTTP sequence contains 19 embedding replies, four count replies and four
generation replies: routing/planning plus the two Compiler outputs. There are
**zero real provider calls and zero native nearest-neighbor queries**.

Both executions traverse routing, requirements, retrieval, candidates,
compilation, numeric result, final result and ledger in the original phase order.
They retain the same 32 seed sources and 521 candidates, with no repair. Numeric
execution remains **41.3957043439745% → 41.4%**, preserving both original source
operands. The three previously source-reviewed narrative claims survive final
composition; this is preservation of recorded claims, not a new semantic sample.

Two tasks complete, five artifacts are linked and all six emitted evidence IDs
resolve. Public answer, structured result and canonical aggregate agree through
the existing caller projection; source anchors remain among the citations.

All **27 actual SDK request-body byte hashes** and **17 dense-boundary receipts**
match across the processes. The complete API JSONs differ at exactly **272 search
duration values**: `vector_search_sec`, `bm25_search_sec`, `rrf_merge_sec` and
`total_sec`, repeated through the existing trace/history/diagnostic projections.
Raw responses remain untouched. Removing only those enumerated timing paths from
a review copy yields identical complete response projections, also equal to the
earlier successful app replay. No other field is normalized or excluded.

## Checks, preservation and remaining work

**11 guard controls** pass: exact sequence/owned-copy behavior, changed search
inputs, changed backend inputs and permanent stop, reordered search, repeated
backend calls, changed corpus/source content, unbound/wrong stores, fixture
mutation, incomplete consumption, terminal propagation through the production
fallback path, and rejection of native-query bypass. **37 evidence assertions**
verify completed outputs, sources, requests, projections and preservation.
Documentation gates pass **2/2**. No production source change requires a new
runtime/domain audit or broad benchmark run.

All **9,426 predecessor files**, **174 source files**, seven runtime owners,
**24 original store files** and settings preserve their hashes. Only each
disposable copy's `chroma.sqlite3` bytes change; its internal write cause remains
unexamined. Experiment fixtures/scripts/results stay ignored; committed changes
are documentation only. Earlier paid outcomes and consumed manifests are intact.

New cost is **$0**. Shared accounting remains **15.22872845 / 16**, remaining
**0.77127155**, pending zero. The earlier proposed future full-app envelope is
**1.70**, exceeding that remainder by **0.92872845**; the suggested +1.00 has not
been approved or applied. Replayed usage is neither a new charge nor a forecast.

The fixed-input integration task is complete. Next prepare a fresh bounded
full-app admission packet using native retrieval and unchanged runtime settings,
with exact source identity, runtime-generated request counting and the existing
whole-batch funding stop before bootstrap. The dense fixture remains offline-only.
Preparation grants no paid execution or budget increase. Native search stability
and fresh end-to-end model quality remain separate evidence boundaries.

Local evidence: [integration review](../../benchmarks/results/compiler_fixed_retrieval_app_2026-09-19/integration_review.json),
[guard controls](../../benchmarks/results/compiler_fixed_retrieval_app_2026-09-19/dense_controls.json),
[fixture protocol](../../benchmarks/results/compiler_fixed_retrieval_app_2026-09-19/protocol.json),
[explicit harness changes](../../benchmarks/results/compiler_fixed_retrieval_app_2026-09-19/runner_derivation.json).
