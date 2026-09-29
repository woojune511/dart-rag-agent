# Saved retrieval failure boundary audit

Completed 2026-09-28 on `ec714bd0`, without new model calls, embeddings, store
clients, ingest, prompt changes or runtime edits. This diagnoses the
[completed table comparison](structure_answer_result.md), not a new quality run.

**The strongest repeated observed boundary is final candidate selection.** Six
of seven failed primary hybrid question/representation pairs have a useful
missing source already in their saved candidate pool but below RRF top eight.
The remaining pair lacks required asset values in its candidate pool. These are
source-location findings, not six recovered answers or a projected accuracy gain.
Five distinct questions account for the seven failed pairs.

## Scope and method

- Read six original HTML filings, both frozen JSONL corpora, saved dense/BM25
  candidates, actual generation requests and the prior answer review. No Chroma
  client or database was opened.
- Execute the existing pure `merge_rrf_results` against saved ranks: all 18 hybrid
  lists, including the diagnostic question, reproduce exact top-eight IDs and
  scores. Inputs are dense top 16 and BM25 top 24, with RRF constant 60.
- Check all 32 primary model packets: each contains exactly the saved eight
  whole chunk texts. No further context-packet omission explains these failures.
- Recheck 54 annotation/representation matches, then inspect source context and
  alternative evidence. Anchors are only a search aid. NIM stays diagnostic-only;
  no original rubric, answer or score changes.
- Preserve the 32 primary ratings: 14 pass, 16 retrieval gaps, one borrowing-scope
  ambiguity and one arithmetic error. A retrieval gap can coexist with an
  unsupported partial claim or period error.

## Where the seven hybrid failures lose evidence

Chunk suffixes below are filing-qualified in the local audit. Ranks are one-based.
A dash under dense means absent from the saved top 16, not from the corpus.

| Question / representation | Missing useful source | BM25 rank | Dense rank | Full RRF rank | Boundary |
| --- | --- | ---: | ---: | ---: | --- |
| POSCO interest coverage / flat | `flat:248`: current interest expense 1,001,290 million KRW | 5 | — | 11 | Final selection |
| POSCO interest coverage / structured | `1048`: consolidated operating profit 3,531,423 million KRW | 21 | — | 30 | Final selection |
| Samsung inventory loss / structured | `285`: current consolidated loss/reversal etc. 5,037,579 million KRW | 5 | — | 13 | Final selection |
| KB provision growth/cause / structured | `1637`: direct annual conservative-provisioning explanation | 4 | — | 9 | Final selection |
| SK translation gain/loss / flat | `flat:76`: current gain 573,884 and loss 906,120 million KRW | 1 | — | 14 | Final selection |
| SK borrowing/assets / flat | `flat:61`: current short-term debt, long-term debt and bonds | 3 | — | 11 | Final selection; answer also mixes periods/bases |
| SK borrowing/assets / structured | `98` / `655`: asset denominator values | — | — | — | Absent from all 35 unique saved candidates |

The structured SK corpus retains 52,704,853 and 3,834,567 million KRW in the
appropriate asset rows. A numeric-surface scan also finds neither in the entire
saved candidate union, beyond the original anchor check. Reranking that fixed
pool cannot supply these values.

The six candidate-loss rows do not imply fully sufficient corrected packets:
Samsung attribution remains scope-sensitive; SK's question remains ambiguous;
and selection alone cannot guarantee interpretation or arithmetic. Nine witness
chunks were inspected against unchanged raw HTML, not only their added prefixes.

## Why fusion can discard a strong lexical hit

The function adds `1 / (60 + rank)` for each list in which a chunk appears. With
these truncated lists, even the lowest-ranked shared candidate gets
`1/76 + 1/84 = 0.025063`, exceeding single-list first place's `1/61 = 0.016393`.
Every shared candidate therefore outranks every single-list candidate under this
input depth and constant.

For flat FX, 12 candidates appear in both lists. All eight slots go to shared
candidates; BM25's first-place complete table becomes RRF rank 14. This is
reproduced behavior of the intended scoring function, not an implementation bug.
It explains this lost source mechanically; it does not establish that changing
the constant or always preferring BM25 improves quality. The prior overall
hybrid benefit over dense-only remains a separate result.

## Other boundaries and the neighbor hypothesis

- **Preservation:** all primary required annotated anchors exist in both corpora.
  The ancillary Celltrion grant sentence is missing from structured output, but
  required operands survive and all four answers pass. This is not proof of
  lossless parsing outside the inspected evidence.
- **Alternative sources:** POSCO flat `172` already supplies operating profit in
  won, despite missing the million-KRW annotation. Samsung's optional cost-of-sales
  anchor and KB's original narrative anchors do not exhaust sufficient evidence.
  Do not equate every missing annotation with a missing answer component.
- **Local boundaries:** flat FX `75 -> 76` restores the split table; flat SK
  borrowing `62 -> 61` restores current rows and headings. KB structured
  `503 -> 504` adds current worse/crisis assumptions, but the direct annual cause
  is in distant `1637`. Neighbors are a local opportunity, not the common remedy.
  Corpus ordinal proximity alone is not a physical table link.
- **Generation:** the original flat-dense ratio answer has all four operands but
  states an incorrect two-decimal equality. Structured Samsung misuses prior-year
  costs; structured SK invents a bond subtotal despite abstaining. Better retrieval
  does not certify these claims.
- **Evaluation:** preserve SK's broader-borrowing interpretation and Samsung's
  attribution sensitivity. NIM's group/bank reference error stays excluded; no
  post-hoc gold correction is presented as an improvement.

## Decision and one possible next experiment

Do not add neighbor expansion, tune RRF constants or restore Planner/Compiler
from this audit. The repeated candidate-loss pattern warrants testing final
selection before adding new queries or parser rules.

If further quality work is commissioned, use **flat representation and the same
dense-16/BM25-24 candidate union**, comparing existing RRF selection with one fixed
semantic reranker. Keep report scope, at-most-eight sources, answer model,
prompt/schema and a common context-token ceiling fixed. Candidate IDs/texts stay
immutable; no query rewrite, new search or answer repair. The reranker sees the
question and candidates, never reference answers/anchors. No metric/company rules.

Use exposed questions only to diagnose the mechanism. Before a new comparison,
freeze 12 unambiguous, previously unused questions and source-reviewed criteria
from filings outside this panel. Measure required-evidence completeness, supported
complete answers, abstention, added cost and latency separately. Run one
configuration/one attempt per arm without tuning or retries on the new panel.
A small improvement justifies broader evaluation, not default adoption; no
improvement or degraded support ends this branch of work.

This is a proposed design, not an execution manifest or spending authorization.
No new panel, reranker implementation, answer-quality or latency result exists.
Provider/model choice and full reservation must be fixed before paid work; consumed
authorizations are not reused. The portfolio milestone remains complete and no
automatic experiment is queued.

## Verification and local artifacts

Before/after hashes pass for all 188 sealed output/review files, 156 input entries
and six original HTML sources (overlapping lists; 344 unique protected paths
including audit dependencies). Hashes prove preservation only.
Isolated standard-library Python loads the pure production merge module by file
path without application/provider imports.

Local ignored directory: `benchmarks/results/evidence_failure_audit_2026-09-28/`.
`audit.py` / `audit.json` retain per-case anchor locations, candidate ranks, packet
checks and input hashes. `witnesses.py` / `witnesses.json` retain original
HTML/chunk excerpts and the candidate-absence check. Scripts refuse to overwrite
existing results. Diagnostic terms/artifacts do not enter runtime policy.

New provider calls, embeddings and incremental cost: **0**. New answer-quality
evaluation: **NOT_RUN**. No source-store/settings changes, commit or publication.
