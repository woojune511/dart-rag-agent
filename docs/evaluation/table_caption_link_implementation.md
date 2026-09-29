# Explicit table-caption attachment implementation

Date: 2026-09-30. Status: **IMPLEMENTED_OFFLINE_VERIFIED_NOT_ACTIVATED**.

The [caption diagnosis](table_caption_link_audit.md) is now implemented as an
explicit optional stored relationship. The source parser and embeddings remain
unchanged. No company, question or gold-dependent rule is added to retrieval or
answer generation. This is a physical evidence-delivery change, not a semantic
selector or a demonstrated improvement in answer accuracy.

## Implementation

| Owner | Contract |
|---|---|
| `src/processing/table_caption_links.py` | Recognize isolated DART date/unit caption tables; validate immediate XML/storage adjacency, unique complete table match and persisted source provenance. Mixed, ambiguous or split matches are excluded. |
| `src/ops/build_table_caption_links.py` | Read explicit local receipt-to-XML mapping and existing graph/payload files; require original document hashes; write a new versioned sidecar without opening Chroma or rewriting sources. Existing output files are refused. |
| `src/storage/table_caption_links.py` | Load the sidecar and validate source body, hydrated metadata, adjacency, scope, XML locator and document-hash bindings on every lookup. Stale/deleted/mismatched bound sources fail closed. |
| `src/storage/vector_store.py` | Read an optional `table_caption_links.json` at store initialization and expose validated whole caption lookup, including when search results are cached. |
| `src/agent/simple_rag.py` | Preserve original search hits; attach captions before their tables; deduplicate, recheck caller scope and validate source IDs. No additional search, embedding or model call. |

Lookup attachments have null scores in observations because they have no
relevance score. `retrieval_debug_trace.caption_bundles` records filing and both
chunk identities. Original source text, metadata and citation identity survive;
no combined synthetic source or inferred date/unit is generated.

## Bounds and operational behavior

The original top-K search stays unchanged. Attached captions count toward the
same physical-source cap (`k`, default8) and65,536-byte packet bound. If any
bound attachment makes the complete packet exceed either cap, the request raises
`ValueError` before generation. It does not evict another original hit, truncate
text or silently deliver a table without its bound caption. Existing whole-source
omission behavior remains when no caption bundle is active.

Consequently, eight distinct hits plus a missing caption will fail this bound.
This is an intentional conservative limit, not a claim that every retrieval can
use the feature. A future capacity/selection policy needs separate evaluation;
it is not implemented here. No sidecar means the existing application behavior.

The sidecar is generated explicitly, not as an automatic ingest migration.
Installing it in a store and reloading the application enables attachment lookup.
Rebuilding or modifying bound source nodes requires a newly verified sidecar;
old bindings are not repaired or accepted heuristically. Neither
`described_by_uid` nor an arbitrary preceding paragraph authorizes a caption.

## Provider-free verification

- 12 focused tests cover four-column captions, invalid/mixed labels, duplicate
  raw/stored tables, intervening prose, scope/location/hash mismatch, stale or
  deleted nodes, persistence/reload, actual SimpleRagAgent packet delivery,
  cached BM25 lookup revalidation, count/byte limits and citation conflicts.
- Existing SimpleRagAgent, vector-store, documentation and import-side-effect
  suites pass; the runtime domain-language audit passes unchanged.
- On the11 existing original reports, the implementation reproduces exactly the
  prior178 verified pairs. Every pair passes actual answer-packet construction
  with unmodified source bodies; maximum9,426 bytes for the fixed audit query.
- All24 saved input packets produce exactly the prior diagnostic expansion.
  Every existing source object remains. Only the two exposed NAVER B packets
  add a caption, each increasing4,521 to5,736 bytes. This is development replay,
  not a new model result or a new holdout test.
- The disk graph/payload persistence and manager initialization tests use a
  substituted Chroma backend. The cached BM25 path is real; the11-report replay
  uses saved selected sources. No new dense retrieval or live answer is claimed.

The prior final-selection result remains6/8 versus7/8 twice and
**COMPLETE_GATE_NOT_MET**. No old gold, response, score or gate was modified.
Calls, fresh embeddings and cost are zero. The generated sidecar is a separate
ignored artifact; the current app store and dotenv settings were not changed.

## Reproduction and activation boundary

`reports.json` is an object mapping existing receipt IDs to original local XML
paths. To prepare a new sidecar in an existing review directory:

```powershell
.venv\Scripts\python.exe -X utf8 -m src.ops.build_table_caption_links --store-dir data/app_full11_2023_v5_20260929 --reports-json <reports.json> --output <review-directory>/table_caption_links.json
```

The builder refuses to overwrite output. Inspect the returned per-report
dispositions and run the tests before a separately scoped store installation.
No network access, re-embedding or parser/store rebuild is needed to build it.
The checked artifact for this implementation is:

`benchmarks/results/table_caption_link_implementation_2026-09-30/table_caption_links.json`

That directory also contains the baseline hash manifest, source mapping,
11-report verification script/result, final verification log and completion/seal.
These artifacts are not staged or published. Implementation is complete;
activation and fresh LLM-quality evaluation remain separate work.
