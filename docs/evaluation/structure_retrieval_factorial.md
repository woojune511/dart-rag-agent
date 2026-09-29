# Flat/structured × dense/RRF retrieval comparison

Status: retrieval phase completed once on2026-09-28. The subsequent
[answer comparison](structure_answer_result.md) also completed36/36. This page
retains retrieval-proxy results, not an independent holdout or answer accuracy.

Correction before answer generation: `KBF_T1_017`'s frozen reference uses
KB Kookmin Bank NIM, not the group requested in the question. The original
measurements below remain an **annotation-hit proxy**, not verified semantic
evidence coverage. Its interpretation as a structure-success case is withdrawn.
[Answer comparison preparation](structure_answer_preparation.md) excludes this
item from the primary denominator before any model answer is sampled.

## Question

Does preserving DART table structure change evidence retrieval beyond the effect
of adding BM25 and reciprocal-rank fusion?

The comparison includes all four cells needed to separate those two factors:

| Representation | Dense | Dense + BM25/RRF |
| --- | --- | --- |
| Flat visible text | `flat_dense` | `flat_hybrid` |
| Structure-preserving parser output | `structural_dense` | `structural_hybrid` |

Without `flat_hybrid`, a structured-hybrid win could not be distinguished from a
generic RRF gain.

## Fixed inputs and interventions

The panel contains nine table-heavy questions across six 2023 business reports:
KakaoBank, POSCO Holdings, Samsung Electronics, Celltrion, KB Financial Group and
SK hynix. These questions and filings were used in earlier development, so they
are not unseen evaluation data.

Both representations use a 2,500-character chunk target with 320-character
overlap, the same `text-embedding-3-large` model, explicit receipt scope and a
top-8 visible result limit. All nine query vectors were embedded once and reused
unchanged across all four arms.

- **Flat:** HTML visible text followed by a generic character splitter, with only
  report-level metadata.
- **Structured:** `FinancialParser` chunks plus the reviewed structural prefix
  that exposes row/header/period/unit context.
- **Dense:** the first eight results from the shared dense candidate list.
- **Hybrid:** the same dense candidates plus BM25 candidates, combined with the
  production reciprocal-rank-fusion function and returned at top 8.

The representation intervention intentionally changes extraction, chunk
boundaries, metadata visibility and indexed text together. It is a product-level
comparison, not an isolated estimate of one prefix or parser feature. It also
produces 1,923 flat chunks versus 7,099 structured chunks; this corpus-size and
granularity difference is part of the treatment and can dilute dense retrieval.

## Evidence criteria

The original source annotations yielded 26 designated evidence anchors. Every
designated anchor was found in at least one chunk of both representations before
the paid run. Table-cell annotations that were not contiguous source strings were
represented as explicit same-chunk term groups rather than silently rewritten.

One additional Celltrion sentence about the absence of current-period government
grant receipts appears in flat visible text but is absent from parser output. It
is supporting context rather than one of the two operands needed for the requested
capitalization ratio, so it is reported as a parser-loss diagnostic and excluded
from required-anchor scoring.

## Retrieval result

| Arm | Required anchors at 8 | All-required questions | MRR of first required anchor |
| --- | ---: | ---: | ---: |
| Flat + dense | 13/26 (50.0%) | 3/9 | 0.340 |
| Flat + BM25/RRF | 18/26 (69.2%) | 4/9 | 0.421 |
| Structured + dense | 12/26 (46.2%) | 4/9 | 0.389 |
| **Structured + BM25/RRF** | **19/26 (73.1%)** | **5/9** | **0.544** |

Per-question required-anchor coverage:

| Question | Flat dense | Flat RRF | Structured dense | Structured RRF |
| --- | ---: | ---: | ---: | ---: |
| `KAB_T1_066` | 2/2 | 2/2 | 2/2 | 2/2 |
| `POS_T1_057` | 0/2 | 0/2 | 1/2 | 1/2 |
| `SAM_T3_028` | 0/3 | 2/3 | 0/3 | 1/3 |
| `CEL_T1_013` | 2/2 | 2/2 | 2/2 | 2/2 |
| `KBF_T2_018` | 1/3 | 2/3 | 0/3 | 1/3 |
| `SKH_T3_080` | 1/2 | 1/2 | 0/2 | 2/2 |
| `KBF_T1_017` | 0/2 | 2/2 | 2/2 | 2/2 |
| `SKH_T1_060` | 2/5 | 2/5 | 0/5 | 3/5 |
| `MIX_T1_021` | 5/5 | 5/5 | 5/5 | 5/5 |

The factor contrasts are deliberately mixed:

- Adding RRF raises anchor coverage by **5** under flat representation and by
  **7** under structured representation. It raises all-required questions by one
  in both representations.
- Switching from flat to structured changes anchor coverage by **-1** under dense
  retrieval and **+1** under hybrid retrieval. It raises all-required questions
  by one in both retrieval modes.
- The anchor-count difference-in-differences is **+2**, while the all-required
  question interaction is zero.

The strongest defensible reading is therefore not “structure always improves
retrieval.” Structured dense is slightly worse on total annotation recall, and
several questions regress. The NIM reference error demonstrates why matching
numbers cannot establish correct entity attribution. Removing that diagnostic
item leaves flat dense13/24, flat hybrid16/24, structured dense10/24 and structured
hybrid17/24 annotation hits; all-designated questions become3/8,3/8,3/8 and4/8.
These remain proxies, not exhaustively reviewed semantic coverage. `flat_hybrid`
is essential: much of the apparent gain comes from RRF. Whether representation
helps produce supported correct answers requires separate review. The subsequent
answer comparison finds flat+RRF5/8 versus structured+RRF4/8 under its frozen rubric.

## Execution and claim boundary

The run made 118 successful embedding calls with zero retries: 42 flat-document
batches, 75 structured-document batches and one nine-question batch. Actual input
was 11,355,288 tokens, exactly matching the frozen estimate. At the published
USD0.13/M rate, estimated cost is **USD1.47618744**, below the approved USD1.60
cap. This is usage-based accounting, not an invoice observation. Pricing reference:
<https://developers.openai.com/api/docs/models/text-embedding-3-large>.

Raw corpora, stores, vectors, authorization, call ledger and result receipts stay
under ignored `benchmarks/results/**`. The completed result, call log and reused
query vectors are sealed by separate SHA-256 hashes. Product runtime, canonical
stores, prompts and policies were not changed.

These measurements establish retrieval-proxy behavior only. Equivalent relevant
evidence outside the frozen anchors was not exhaustively judged in this phase.
Answer generation and semantic review are reported separately. These retrieval
measurements do not establish answer correctness, general DART
accuracy, unseen-company performance, latency superiority or a universal benefit
from structural parsing.
