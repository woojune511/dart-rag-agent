# Vanilla dense baseline comparison

Status: completed once on 2026-09-28. This is a paired, development-exposed
comparison, not an independent holdout or a population accuracy estimate.

## Question

Does the default hybrid retrieval path provide useful evidence-selection value
over a simpler dense-only RAG baseline when the answer model and visible context
budget are held fixed?

## Fixed comparison

Both arms use the same 12 NAVER 2022/2023 questions, explicit report scopes,
top-8 context limit, `SimpleRagAgent` answer instructions, `RagAnswer` schema and
`gpt-5.6-terra` answer route. The saved hybrid arm is the completed
[final application evaluation](simple_rag_final_result.md).

The vanilla arm removes BM25 and reciprocal-rank fusion. It replays the exact
saved `text-embedding-3-large` query vectors against the same Chroma collection
and exposes the resulting dense top-8 documents to the unchanged answer path.
No query embedding was purchased again. Each nonempty case received one answer
call, with zero retries, repairs or Compiler fallback.

This isolates visible evidence more tightly than rerunning the complete product,
but it also means dense latency is not a live end-to-end retrieval measurement.

## Result

| Metric | Current hybrid | Vanilla dense-only |
| --- | ---: | ---: |
| Runtime completion | 12/12 | 12/12 |
| Positive required-evidence coverage | **9/9** | 5/9 |
| Positive frozen-anchor hit@8 | **9/9** | 5/9 |
| Positive mean reciprocal rank | **0.578** | 0.322 |
| Answerable: correct, complete and fully source-supported | **9/9** | 5/9 |
| Answerable: correct and complete content | **9/9** | 6/9 |
| Insufficient-evidence: safe abstention | 2/3 | **3/3** |

Dense-only answered F01, F02, F03, F05, F07 and F08 correctly. F03 used an
equivalent current-period, consolidated structured source rather than the frozen
anchor. F05 contained the correct employee counts and calculation but lacked the
separate `2023-12-31` date source, so it is not included in the fully
source-supported count.

F04, F06 and F09 lacked the required values or claims in the dense top-8. The
model abstained instead of inventing an answer. These are honest abstentions but
remain unanswered positive cases. On F12 the dense arm avoided the hybrid arm's
unsupported annual-to-daily substitution, although it described absence from
the report more broadly than the retrieved window proves. A separate model call
was used for each arm, so the different F12 behavior is an observation rather
than a retrieval-only causal claim.

## Execution and cost

The dense arm completed with 11 answer calls, no new embeddings, no retries and
no errors. It used 62,127 input tokens and 2,046 output tokens, including 162
reasoning tokens. The experiment guard conservatively accounted USD0.1798695 by
charging all input at USD2.50/M and output at USD12/M, below the approved USD1.65
one-run cap. At the published USD2/M uncached input and USD12/M output rates, the
same observed usage is USD0.148806. These are usage-based estimates, not invoice
observations. Pricing reference: <https://developers.openai.com/api/docs/models/gpt-5.6-terra>.

The 30.74-second dense batch time includes fixed-document replay and generation.
It must not be compared as product retrieval latency with the hybrid run, which
performed live query embeddings and store search.

## Integrity and publication boundary

Raw requests, responses, per-case results, authorizations and source stores stay
under ignored `benchmarks/results/**`; they are not publication artifacts. Before
review, 35 live request/response/result files were frozen by SHA-256, and the
post-review integrity check found zero mismatches. The predeclared rubric was
applied by assistant source review with zero paid judge calls.

An exploratory Chroma open changed only the source SQLite file's byte hash.
Formal retrieval used a copied store, and a canonical digest over all 1,872
sorted IDs, documents, metadata and embeddings matched the historical evaluation
copy. This supports logical-store equality, not byte-identical source-store
preservation for the exploratory step.

The public claim is therefore narrow: on this exposed panel, hybrid BM25 plus
dense RRF selected complete positive evidence more often and produced more fully
supported positive answers than the dense-only baseline. It does not establish
general superiority, unseen-company performance or production accuracy.
