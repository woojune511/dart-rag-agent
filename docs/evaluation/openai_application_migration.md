# OpenAI application migration

`DART_LLM_PROFILE=openai` selects OpenAI for shared API/Streamlit LLM calls:
Terra/low/8192 for default routing/planning, the unchanged reviewed
Astra/medium/5120 Compiler, and Luna/none/512 for ingest context sentences.
All use Responses, standard tier, `store=false`, timeout 90 seconds and zero
SDK retries. Explicit `google` and `openai_compiler` modes remain available;
unset selection keeps the existing default. This is application wiring, not
retirement of historical benchmark/MAS/legacy provider implementations.

The context generator now reads plain strings and completed text blocks, omits
reasoning/refused/incomplete text, and reports metadata fallbacks and actual
usage. It preserves source text and metadata. Existing stores, context caches,
canonical parser/embedding identities and query contracts are unchanged.

## Model basis

The current official [Terra model card](https://developers.openai.com/api/docs/models/gpt-5.6-terra)
describes the balanced mini tier, while [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)
targets low-cost high-volume work. Both support Responses/structured outputs
and the selected reasoning controls. Compiler settings retain their prior
[Astra compatibility](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md#migration-quickstart).
Model fit for this application still requires application evidence; product
positioning alone does not prove answer quality.

## Validation boundary

Focused provider-free tests: 46 passed. Real installed SDK serialization covers
router/planner schemas, nested required fields, plain context responses, usage,
empty/refused/incomplete text, startup without Google credentials, strict source
readiness, failure/no-retry behavior and prior Compiler transport contracts.
Full provider-free regression: **1,855/1,855**, no failures/errors/skips (49.777s),
external network blocked and attempted connections/provider calls 0. Domain
audit: 83 reviewed literals, no additions.

## Actual query: transport passes, numeric output remains incomplete

The [normal-app result](../../benchmarks/results/app_openai_migration_2026-09-16/RESULTS.md)
used clean source `068ade52` and real API lifespan/shared services through ASGI.
Health/companies/query returned HTTP 200. The known-source mixed question
produced **1/2 outputs**, with ledger integrity ok: four supported narrative
claims, but no numeric growth result. Overall query status is **partial**.

Both original numeric cells reached the Compiler; their value, unit, period,
source-context and provenance fields match the previous complete run. The
Compiler explicitly abstained because it did not resolve attached relative
period labels to the requested calendar years. This is a semantic period-grounding
gap, not an observed API/schema error or proof of a planner/filter failure.
Fresh plans differ, so the result cannot isolate a model or prompt effect.

Fresh admission `d787579d...0f390` was consumed once after two identical mocked-HTTP
rehearsals and terminal-stop checks, under USD 7. All 23 attempts completed:
Terra 2, Astra 2, embeddings 19; Google clients/calls 0, SDK/whole-query/Compiler
feedback retries 0. Conservative usage estimate **USD 0.78708574**, peak reservation
1.69237324, pending 0; no invoice claim. The packet stopped on partial output and
did not run its context sample. Its immutable response is not counted as complete.

Separate offline review verified nine narrative subject/fact support occurrences,
including direct acquisition-impact evidence with group/subsidiary qualifications.
All 453 protected files are unchanged. Read-only SQLite comparison confirms the
working copy retains the original 1,872 source rows and 59,477 metadata rows;
normal working-copy database bookkeeping may differ.

## Independent first context preview and local activation

The separate [context preview](../../benchmarks/results/app_openai_context_2026-09-16/RESULTS.md)
did not rerun the question or resume its consumed packet. New admission
`283485c1...93b3`, USD 0.10, binds one exact plain-text Luna request rehearsed twice.
One actual response returned a 39-character Korean context sentence consistent
with the source topic, without fallback; usage estimate **USD 0.0001225**.
All 478 protected files passed. No app startup, embeddings, fetch, indexing or
store writes occurred in this preview; full fresh ingest remains untested.

Local `.env` now selects `DART_LLM_PROFILE=openai`; only that setting's bytes
changed, preserving credentials and storage settings. The API and Streamlit
share this selection. A running process must be restarted to reload it; no
external listening server was started. Total observed usage estimate across
the two independent checks is **USD 0.78720824**, not billed cost.

The provider migration is implemented and selected. It is not a complete answer
quality or release gate: calendar-period grounding and independent-question
coverage remain next. Keep source/request/execution validation strict; do not
fill the missing calculation from the known answer or rerun consumed admissions.

## Provider-free period-contract correction (2026-09-17)

The [stored-source reconstruction](../../benchmarks/results/relative_period_contract_2026-09-17/RESULTS.md)
found a contract mismatch: ingestion `year` is the business year, but the Compiler
prompt described it as the filing year. The unchanged current/prior exact attached
quotes already resolve to 2023/2022 through existing validation. Instructions now
explain the business-year anchor and the existing `context_evidence.resolves` path
for a selected cell whose catalog period is still unknown. No new candidate field,
automatic context selection, parser change or provider call was introduced.

Anonymous controls also reproduced a validator gap: an explicit model-written year
could replace absent, ambiguous or unanchored quote evidence. Period bindings now
require the exact attached quote to resolve one matching year. Explicit source
years still work without a report-year anchor; physical attachment, source conflicts,
raw values and V2 execution proofs remain enforced.

Focused tests **146/146** pass, including six new contracts with authored transport,
initial/retry prompts and execution; blocked external connection attempts 0.
All 494 protected files, catalog/payload/cohort hashes and historical source proofs
remain unchanged. The actual sampled missing response remains missing. This proves
the local contract correction, not a live completion improvement or isolated cause
of the historical abstention. Next is a fresh bounded quality check and independent
question coverage; consumed admissions remain unusable.
