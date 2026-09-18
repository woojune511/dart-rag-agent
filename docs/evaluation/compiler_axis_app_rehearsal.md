# Normal-application replay and budget preparation

Prepared 2026-09-19 from clean `8e6a4c5a`, after the
[two-case Compiler API probe](compiler_axis_probe.md). One provider-free replay
reaches the final public answer and completed ledger. A second fresh process
stops at the narrative request because the retrieved seed window changes.
**Repeated exact-input reproducibility is not established.** No runtime source,
budget cap, original store or earlier paid result was changed; new provider calls
and added cost are **zero**.

## What was exercised

The actual FastAPI app runs through its in-process health, companies and query
endpoints with a verified temporary copy of the selected NAVER 2023 store. The
existing OpenAI profile, model settings, prompts, retrieval, Compiler validation,
answer assembly and ledger code are preserved. External sockets are blocked,
credentials are dummy values, and the caller only accepts `httpx.MockTransport`.
Ingest, context generation and explicit document-store writes are forbidden.

The replay preloads 27 recorded HTTP request/response pairs before app startup:
19 embeddings, two Terra count/generation pairs from the earlier app attempt,
and two Astra pairs from the current-format Compiler probe. Every response is
served only for its exact request body and position. Historical answers are
fixtures at the mocked HTTP boundary, never added to prompts or core state.
The app cannot read historical result files while running.

| Fresh process | Outcome |
| --- | --- |
| A | All 27 pairs match; HTTP 200, complete structured result, both outputs and ledger `ok` |
| B | First 25 bodies match; narrative count body differs, recorded response refused; local HTTP 500 |

Run A's store is ready, compatible and non-degraded with 1,872 chunks. The actual
phase sequence is routing → requirements → retrieval → candidates → compilation
→ numeric result → final result → ledger. The mixed program carries the narrative
through that shared result path; no separate narrative-result node is required.

The completed answer contains the calculated **41.4%** with both exact thousand-KRW
inputs, and all three previously source-reviewed narrative claims. Acquisition
purpose, other Commerce growth drivers, and Poshmark/subsidiary post-acquisition
revenue/loss scope remain intact. Both obligation results are `ok`, with no missing
obligations or Compiler repair. Public answer, structured answer and aggregate
artifact agree. Their traces agree after the existing public projection removes
whole Compiler/validation records; canonical ledger records remain intact.
Two tasks are completed, five artifacts are linked and all six emitted evidence
IDs resolve. Required source anchors are retained among public citations.

This validates integration with recorded responses for that execution. It does
not add a new live model sample, input-token measurement, app acceptance result,
unseen-question result or semantic score to the earlier paid evidence.

## Repeat mismatch

Both runs start from byte-identical original store copies and use the same saved
embedding vectors, routing reply and plan. The final eight retrieved documents,
their order and scores are identical. The 32-document seed window differs:
run A includes chunk 76; run B includes chunk 96 in its place. The catalogs contain
**521 / 530** candidates, with four removed and thirteen added. All common
candidates are unchanged, including the six candidates supporting Run A's answer.
The numeric Compiler body still matches exactly; the narrative body does not.

Those initial traces located the difference in retrieval/seed selection. The
subsequent [provider-free diagnosis](retrieval_seed_drift_diagnosis.md) isolates
Chroma HNSW membership and reproduces both catalogs by exchanging only one
query's observed dense results. No quality degradation is established. Run B's
`provider_token_count_failed` is the local guard's classification of the mock
identity rejection, **not an observed provider failure**. Neither a new count nor
a narrative generation was made, and its original stopped result is retained.

The matching rule was not relaxed, candidates were not changed to fit fixtures,
and no further full-app repeats were run to obtain a favorable result. The
diagnosis preserves both original outcomes. Next prepare an experiment-local
dense-result fixture replay with exact query/vector/filter/source guards, then
repeat full-app integration under those explicitly fixed retrieval inputs.

Only `chroma.sqlite3` changes inside each disposable copy during startup/use;
other copied source files retain their bytes. Both original stores and local
settings are protected by the predecessor hash map. Copy database-byte equality
is not claimed, and its exact internal write cause was not inspected.

## Proposed cost, not new authority

[Official pricing](https://developers.openai.com/api/docs/pricing#standard-pricing-data),
fetched 2026-09-19, supports conservative cache-write input rates of $2.50/M for
Terra and $12.50/M for Astra, with output rates $12/M and $50/M. The same page lists
`text-embedding-3-large` at $0.13/M. No cache discount is assumed. The existing
$0.01 per count is a contingency, not a verified tariff or invoice amount.

The proposed first-response application envelope permits one routing, one
requirements and two Compiler generations, at most four counts and 48 embedding
requests. Repeated Compiler owners and repeated routing/planning calls are denied
before another count. Generation inputs are capped at 30,000 measured tokens and
100,000 request bytes. Existing output limits remain Terra 8,192 / Astra 5,120.
Each embedding request is capped at the existing conservative input reservation
of 8,192, including its 128-token margin, before reservation/transmission.

| Whole proposed envelope reservation | USD |
| --- | ---: |
| Two Terra inputs and full outputs | 0.346608 |
| Two Astra inputs and full outputs | 1.262000 |
| 48 maximum embedding reservations | 0.05111808 |
| Four count contingencies | 0.040000 |
| Calculated maximum | **1.69972608** |
| Rounded proposed run cap | **1.70** |
| Current remaining allowance | **0.77127155** |
| Shortfall against proposed cap | **0.92872845** |
| Minimum cent top-up / recommended round top-up | **0.93 / 1.00** |

Historical usage replay totals **0.72609436**, but its sequential peak with full
pending output reservation is **0.90964436**, already above the current remainder.
Reserving all full outputs against those recorded inputs is **1.29754252**.
These are distinct scenarios, not forecasts or new charges. Future planning,
retrieval, input lengths and response lengths can change; the bounded maximum
funds permitted limits, not successful completion. Whole-batch funding must pass
before even bootstrap embeddings.

A hypothetical $1 increase would raise the shared cap from $16 to $17 and leave
0.07127155 after the full proposed $1.70 allowance. **No increase is applied or
authorized here.** Shared accounting stays **15.22872845 / 16**, remainder
**0.77127155**, pending zero. There is no new live runner or paid manifest.

## Controls and preservation

Seven caller controls pass: whole-batch funding, real-transport rejection,
oversized embeddings before reservation, repeated Compiler owner and routing
attempts before a second count, wrong phase/model pairing, and refusing a changed
request's stored response. Documentation gates pass 2/2: **nine local checks**.
The complete and stopped application replays are reported separately from these
checks; they are not two successful or byte-identical rehearsals.

All **9,224 predecessor files**, **174 sources**, seven runtime owners,
**24 original store files** and settings retain hashes. Only documentation is
committed; mock responses, diagnostics and proposed policy remain ignored local
evidence. The original budget-stopped app still has no live final mixed answer.

Local evidence: [complete replay review](../../benchmarks/results/compiler_axis_app_rehearsal_2026-09-19/completed_replay_review.json),
[repeat drift](../../benchmarks/results/compiler_axis_app_rehearsal_2026-09-19/repeat_drift_review.json),
[decimal budget](../../benchmarks/results/compiler_axis_app_rehearsal_2026-09-19/budget_plan_exact.json),
[caller controls](../../benchmarks/results/compiler_axis_app_rehearsal_2026-09-19/controls.json).
