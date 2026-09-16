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
of the historical abstention. The separate live successor below tests the corrected
contract with fresh plans; consumed admissions remain unusable.

## Fresh three-question application verification (2026-09-17)

The [normal-app successor](../../benchmarks/results/period_quality_v2_2026-09-17/RESULTS.md)
used clean `10ee083d` and three fixed questions through real ASGI/shared services.
All returned HTTP 200, but only **1/3 questions and 2/4 requested outputs** completed.

- The known Commerce question now calculates **41.4%** using the unchanged exact
  current/prior context proofs for 2023/2022. Its acquisition explanation is missing.
- A new consolidated cash-flow question returns **1,361,609,576,268 KRW** after
  subtracting the PPE acquisition outflow magnitude; source signs/period/units pass review.
- A new cloud AI strategy question returns no explanation. Both narrative outputs
  were blocked before Compiler dispatch by `invalid_obligation_unit`: Planner wrote
  `text` and `서술` into `display_unit`. Related sources were retrieved; narrative
  faithfulness/completeness remain untested, not failed model-writing samples.

The subsequent provider-free correction below separates narrative display format
from numeric units in the generation schema; these sampled answers stay unchanged.
Fresh plans/retrieval prevent isolated prompt/model attribution; these are two new
source-reviewed questions, not unseen holdout or a release gate.

New `a1b7ef41...300a0` consumed once after identical SDK rehearsals and full caller
success/failure controls. All 56 provider requests completed: Terra 6, Astra 2,
embeddings 48; Google/context calls and SDK/whole-query/Compiler retries 0.
Usage estimate USD 0.82543298; with the predecessor's local reservation,
USD 0.82566256 accounted within the shared USD 7 limit, not billed cost.
The predecessor failed in caller logging before any HTTP transmission or question;
its consumed manifest/result remain preserved. All 528 protected files and logical
source tables pass; no production source changes, fresh ingestion or original-store writes.

## Narrative unit generation contract (2026-09-17)

The [offline correction](../../benchmarks/results/narrative_unit_contract_2026-09-17/RESULTS.md)
reproduces both narrative blocks from clean `243bddf2`. The old Planner schema
accepted format labels as units. Production generation now uses separate numeric
and narrative obligation branches: narratives require `display_unit=""`, while
requested presentation stays in `display_format`. Numeric units remain declared
and pass through the unchanged deterministic checks. There is no unit alias,
format-label whitelist, automatic relabeling or historical-response repair.

Six authored contracts cover schema rejection, null compatibility, both narrative
evidence modes, free presentation labels, a blocked numeric sibling, and unsupported
numeric claims. The real OpenAI SDK mock sends the nested strict schema and parses
all three output kinds. The shape follows the [official supported schema subset](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas);
SDK serialization is not live provider admission or model-quality evidence.

Full unittest **1,867/1,867**, no skips (52.611s); focused **158/158**, domain audit
83, import/topology/documentation and pycompile/diff checks pass. External network
was blocked with 0 attempted connections/provider calls; all 564 protected files
are unchanged. Original sampled narrative units remain invalid under preflight;
explicitly authored blank-unit copies pass that gate without fabricating answers.
That paid result remains **1/3 questions, 2/4 outputs**; the separate live successor
below checks fresh generation and source quality without rewriting those answers.

## Live narrative-unit successor (2026-09-17)

The [two-question successor](../../benchmarks/results/narrative_quality_2026-09-17/RESULTS.md)
on clean `136a1a06` completed **2/2 questions and 3/3 outputs**, HTTP 200 and ledger
ok throughout. Both narrative display units are empty, with presentation intent
retained separately. Commerce growth remains 41.3957043439745% → 41.4%; its direct
acquisition-impact explanation retains other contributors and the acquired-group
scope of post-acquisition revenue/loss. Cloud strategy covers organizational and
technical integration, HyperCLOVA X, CLOVA Studio and the security-oriented hybrid
offering, preserving completed-versus-intended distinctions. Six claims and 20
subject/fact support occurrences pass source linkage plus separate assistant
semantic review. Some cloud wording is repetitive, a remaining readability issue.

Cloud used one allowed same-candidate feedback repair after an unauthorized context
reference; both attempts are preserved. All 45 requests completed: Terra 4, Astra 4,
embeddings 37; no API/parsing/runtime error, Google/context call, SDK/whole-query retry
or fresh ingest. New admission `0a08e0eb...aa189e` consumed once after identical SDK
and full-wrapper rehearsals. Estimated USD 1.46798135; including prior accounting,
USD 2.29364391 under the shared USD 7 ceiling, not invoice. All 582 protected files
and original source bytes remain unchanged; logical working-source tables match.

This is fresh application evidence for two known-source questions, not unseen
accuracy, human gold, or an isolated schema/model causal comparison. Source and
model settings remain unchanged during the run. The separate broader-question
successor below does not reuse this consumed admission.

## Broader normal-application verification (2026-09-17)

The [three-question successor](../../benchmarks/results/broader_app_2026-09-17/RESULTS.md)
on clean `173d5d02` uses the same runtime and default OpenAI application routes.
All three questions return HTTP 200 and ledger ok, producing **4/4 outputs**.
Runtime completeness is **2/3**, with one partial; all frozen criteria pass for
**1/3**, with two partial. No production source code changed during the run.

- Consolidated cash and cash equivalents are correctly retrieved as
  **3,576,456,533,329원** at 2023-12-31 / 제25기, preserving source unit and scope.
  Planner also supplies unsupported direct-value evidence requirements, leaving
  `evidence_requirement_on_unsupported_obligation` beside the accepted binding.
- Operating margin uses exact consolidated source inputs and calculates
  15.395255319023432%, explicitly rounded to **15.4%**. Arithmetic and calculation-only
  intent pass; fixed presentation **15.40%** is lost when the renderer strips zeros.
  Exact inputs and formula remain in trace; no separate unrounded scalar is stored.
- Naver Pay payment expansion and financial-service activities pass separate
  assistant review. Ten claims/28 source-support occurrences cover both themes
  and preserve explicit timing, report-as-of reach and aspirational platform wording.

Anonymous offline controls reproduce the two contract/presentation gaps without
external connections or source edits. Next: align direct-value Planner/preflight
with the existing strict requirement contract, then address requested decimal
precision separately. Do not weaken validation, add question-specific rules,
rewrite old answers or treat this as an automatic paid-rerun authorization.

New `5a7767e2...b376d` consumed once after identical SDK and full-wrapper rehearsals.
All **43 requests** completed: Terra 6, Astra 4, embeddings 33; no Compiler feedback,
SDK/whole-question retry, API/parsing/unhandled runtime error, Google/context call
or fresh ingest. One program-validation error remains as reported above.
Estimate USD **1.05468823**; prior accounting plus this run **3.34833214**, peak with
reservations **4.03783214** under shared USD 7; pending 0, not observed billing.
All 618 protected predecessor files and original source bytes remain unchanged;
read-only logical source tables match the working copy. These newly authored but
source-reviewed questions are not unseen holdout or a general release gate.
