# Development comparison: interrupted during result persistence

2026-09-22, source `8f749023`. **INTERRUPTED; zero completed pairs.** The user
approved USD6 additional funding and one four-question/two-arm batch under a
USD6 cap. The attempt was made once and is consumed; no paid retry or resume.
The [frozen comparison design](portfolio_workflow_comparison.md) remains available.

## Observed result

The simple RAG answer for `lookup_cash` completed and was saved. The current
workflow admitted two requests (Planner and Compiler), then returned a result
whose review record contained a LangChain `Document`. The comparison writer
called plain `json.dumps` on that object. Both the per-arm write and final receipt
write failed with `TypeError: Object of type Document is not JSON serializable`.

This is a comparison-tool persistence defect, not observed OpenAI unavailability
or evidence that the current workflow's answer was wrong. Its answer and usage
records were lost when the process exited. They cannot be reconstructed from
the preserved prompt or a new model response. Initial tests exercised the graph
and transport separately but missed serialization of the complete graph result.

| Case | Simple RAG | Current workflow |
| --- | --- | --- |
| Cash lookup | Answer retained | Output unavailable after two admitted calls |
| Commerce growth | NOT_RUN | NOT_RUN |
| Acquisition explanation | NOT_RUN | NOT_RUN |
| Insufficient evidence | NOT_RUN | NOT_RUN |

The retained baseline used one call, 5,186 input / 282 output tokens (reasoning
already included), and 5.236 seconds. Its primary answer, `3조 5,765억 원`, matches
the rounded management discussion in selected source `20240318000844:894:11`.
The cited material does not supply the precise balance-sheet cell requested by
the question. This is a qualitative source observation, not an accepted exact
lookup or a comparative correctness score. There are no quality/cost/latency
conclusions comparing the two workflows and no general improvement selected.

## Cost evidence and remaining funding

The first call's retained usage gives a conservative USD0.016349 estimate at the
prepared rates. The other two usage records were not persisted. Charge each at
its maximum admitted request envelope, USD0.298304, without inventing token
counts or treating missing records as free calls:

`0.016349 + 2 * 0.298304 = USD0.612957`.

This combines one usage-based estimate with two conservative upper bounds; it
is **not observed billing**. Shared accounting moves from USD20.02917543 to
**USD20.64213243 / USD26.32**, leaving **USD5.67786757**, pending zero after charging
the unknown calls conservatively. The unused budget does not authorize automatic
reuse of this consumed one-batch approval. A successor must explicitly cover
its own full bound; do not silently reduce reserves to fit remaining funds.

Immutable local evidence under
`benchmarks/results/portfolio_workflow_comparison_2026-09-22/`:

- `ready/plan.json` and `ready/authorization.json`: frozen inputs and authorization.
- `progress.log`, `run/00_simple_rag.json`, the two empty failed output files,
  and `run/plan.json` / `run/policy.json`: original attempt, left unchanged.
- `failure_receipt.json`: separate terminal accounting, NOT_RUN statuses and raw
  file hashes. It is an explicit recovery record, not a repaired original receipt.

All frozen source sidecar and packet hashes still match. No new ingest, source
mutation, old-manifest resume or additional provider call was performed.

## Provider-free correction

The comparison writer now projects typed Pydantic records, including Documents,
to JSON while preserving text and metadata. It encodes before opening a file, so
an unsupported type does not leave an empty output. Unknown record types still
fail; they are not replaced with opaque string representations.

Each arm's budget is checkpointed separately before rich result serialization;
the final budget also has its own file. If output serialization fails, the run
retains the cost records, marks that output unavailable and stops remaining arms.
The regression tests persist an actual graph result and exercise a charged request
followed by an unsupported output. This correction does not recover the lost paid
answer, establish live acceptance, or change product prompts or domain behavior.

Post-fix validation: **2,267/2,267** provider-free tests (67.897s), including
**12** comparison contracts. The existing domain audit remains at **66** reviewed
literals. Original failed-run files and frozen source/packet hashes are unchanged.

The next experiment is still the shared-evidence development comparison. Do not
infer an architectural winner from this interrupted attempt or replace it with
question-specific repairs. Final holdout and the final demo/report remain open.
