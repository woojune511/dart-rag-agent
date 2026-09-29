# Bounded Agentic RAG search comparison

Frozen before live dispatch, 2026-09-28. User requested proceeding with a single-agent
search/read loop after reviewing the fixed-pool selection experiment. This is an
isolated experiment, not a change to the SimpleRagAgent application default.

## Comparison

Six exposed questions use the frozen table corpus C: KAK_T3_055, SAM_T3_003 and
CEL_T3_015 have reviewed candidate-recall gaps; MIX_T3_023 has a corpus omission;
SKH_T3_080 and CEL_T2_039 are previous successes. This deliberately selected sample
is neither an unseen holdout nor representative of all77 questions.

Both arms share the same initial semantic decision and its fixed-evidence answer.
The baseline stops there. The agent arm may execute the decision's search query,
read the retrieved source texts, and decide again, with at most two extra searches.
If the initial decision stops, the exact baseline answer is shared, not regenerated.
Thus no-search agreement is by construction, not two independent observations.

The controller selects up to eight sources, reports missing information and chooses
a search query or null. The initial prompt favors a jointly sufficient selection;
it differs from the previous experiment's individual-relevance prompt. This is a
common-prefix search-enabled versus search-disabled comparison, not a direct score
comparison to the previous12 inputs. Baseline answers and generated answer contents
are never given to the controller. Rubrics, failure categories and reference answers
are evaluation-only and never enter provider packets.

Search uses existing table source texts/vectors in the explicit caller report scope:
exact squared-L2 dense16, existing BM25 positive top24 and RRF60 candidate union.
All six original dense/BM25 lists reproduce exactly from saved question vectors.
New query embeddings use text-embedding-3-large,3072 dimensions. No fresh ingest,
document embedding, cross-report or web retrieval is enabled. Search results include
whole source texts/context automatically; there is no separate free-form browse tool.

The next decision retains the previous selected sources before adding the fresh
candidate union. Other previous sources can leave the context. Whole sources only,
with a200,000-byte-plus-overhead admission bound and logged omissions; retained
source overflow stops. Selection is restricted to IDs visible in that decision.
Answers retain the existing prompt/schema, at most eight selected documents and
65,536-byte whole-source packet limit. Structured ledger events and saved artifacts
record state, queries, candidates, selected IDs, omissions and provider usage.

## Budget and stops

- Same model/settings as the preceding comparison: gpt-5.6-terra, low reasoning,
 8,192 output tokens, standard service tier, store=false.
- At most18 decisions +12 answers +12 query embeddings. No extra answer call when
 there is no additional search, or when evidence is empty.
- New one-batch cap USD15; conservative all-call reservation USD14.0106. Rates use
 input2.5/output12 per1M and embedding input0.13; no cache discount. These are estimates,
 not observed billing. [Official price source](https://developers.openai.com/api/docs/pricing).
- Maximum two additional searches per question; one query at a time,500 characters,
 3,000 embedding tokens. Repeated queries, foreign IDs, invalid scope, malformed
 output, missing usage, incomplete generation, HTTP error or budget exhaustion stop
 the batch with unrun cases preserved as NOT_RUN. No repair, retry or resume.
- Compact20-second heartbeat; no credentials, headers or duplicate request body in
 heartbeat. Full public-evidence request/response bodies are separate local artifacts.

## Verification and evaluation

Before dispatch, blocked-network SDK rehearsal must exercise the maximum42 calls
and stopping controls. Source, corpus, vector, previous-result and frozen-panel
hashes are checked before and after the batch. These checks establish execution
boundaries, not semantic correctness or provider acceptance.

After dispatch, inspect new query -> recovered source -> selected packet -> answer
for each case. Report strict all-claim/cited support, missing-component recovery,
safe abstention on corpus omission, regressions, search counts, tokens, estimated
cost and timing. Arithmetic and semantic accuracy are reviewed separately from
runtime ID/shape checks; the prototype does not execute arithmetic or certify claims.
Do not tune the frozen controller after seeing results or automatically rerun all77.

Local ignored artifacts: `benchmarks/results/agentic_search_2026-09-28/` contains
the executable experiment, panel, evaluation-only references, hash manifest, mock
controls, consumed marker, ledger and live outputs. No experiment artifacts are staged.
