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

The independent live validation packet is prepared under
`benchmarks/results/app_openai_migration_admission_2026-09-16/`. Its manifest is
one-shot, with a USD 7 ceiling, mocked HTTP rehearsals and protected source/store
hashes. Scope is one normal application query plus one context-generation
sample; no full fresh ingest or store write is part of that check. Results will
be reported separately from provider-free checks.
