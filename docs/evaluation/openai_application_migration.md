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
external connections or source edits. The direct-value correction below aligns
Planner/preflight with the existing strict requirement contract; requested decimal
precision remains separate. Do not weaken validation, add question-specific rules,
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

## Direct lookup contract correction (2026-09-17)

The [provider-free correction](../../benchmarks/results/direct_lookup_contract_2026-09-17/RESULTS.md)
separates direct/derived/narrative Planner branches. A direct lookup owns its source
selection on the output and requires an empty child-input list. Subject, scope,
request and retrieval hints remain intact; derived/narrative inputs remain allowed.
Preflight preserves malformed old plans and blocks their dependent component
before Compiler calls, without retrying or excluding source candidates. Independent
valid outputs continue. The existing final source/program validator is unchanged.

Six new contracts, real SDK strict-schema serialization and anonymous execution
pass; array length constraints follow [official Structured Outputs support](https://developers.openai.com/api/docs/guides/structured-outputs#supported-properties).
Full unittest **1,873/1,873**, no skips (52.591s), focused 164, scope regression 44,
audit 83 and import/topology/docs 24 pass with external networking blocked and
attempted connections/provider calls 0. Two historical authored scope fixtures
were made structurally valid while retaining their original assertions and direct
scope coverage. Frozen catalog/program hashes, source proofs and 659 protected
predecessor files remain unchanged. No original store writes or consumed admission reuse.

This does not alter the preceding paid partial cash answer or prove live provider
acceptance/answer quality for the new schema. The fixed-decimal correction below
is separate local evidence; fresh provider verification remains a bounded run.

## Final-round presentation correction (2026-09-17)

The [provider-free replay and contracts](../../benchmarks/results/fixed_decimal_display_2026-09-17/RESULTS.md)
on baseline `5ede1b83` preserve the exact saved program, request, source catalog,
visibility and validation. Its final `round(..., 2)` now renders **15.40%** throughout
the calculated slot, trace, final answer and ledger. The numeric value stays 15.4;
source rows and source/calculated provenance remain unchanged. Original paid
answers/results and all 684 protected predecessor files are preserved.

Only outermost rounding supplies precision; intermediate operations and dependency
values do not propagate it. Source displays keep their original precision. Unit
conversion shifts base-unit precision, with fixed formatting bounded to 324 places;
larger requests retain the existing formatter. No query keyword parsing, new model
schema/prompt, source mutation or arithmetic change was introduced.

Nine new tests, focused **156/156**, full unittest **1,882/1,882** without skips
(53.272s), and domain audit 83 pass with external connections blocked; attempts
and provider calls are 0. This is an exact-program execution comparison, not fresh
model generation, current provider acceptance, or general answer-quality evidence.
The separate successor below tests direct-lookup Planner generation and attempts
fixed-decimal verification using the ready store and a fresh admission. No consumed
admission is reusable, and the historical answers remain unchanged.

## Live verification after numeric contract corrections (2026-09-17)

The [two-question successor](../../benchmarks/results/corrected_numeric_app_2026-09-17/RESULTS.md)
on clean `7326ae58` uses the real ASGI/shared services and unchanged OpenAI routes.
Both return HTTP 200 and ledger ok, but runtime is **1/2 complete**, with **1/2
outputs** and **0/2** passing every frozen acceptance criterion. This verifies API
execution and direct-lookup generation; it does not establish full answer quality.

- Cash has empty direct child requirements and no old contract error. Its selected
  summary-financial row really reports **3,576,456백만원**, but the requested full
  consolidated statement reports **3,576,456,533,329원**. The exact full-statement
  source was absent from retrieved/seed windows and the catalog. Selected-source
  fidelity passes; requested statement and precision fail. No rounding explanation
  is inferred for the difference.
- Margin's exact revenue/profit cells are retrieved and cataloged but both absent
  from Compiler exposure. The parsed response declines unrelated available amounts
  and returns missing. No expression executes, so fixed-decimal live behavior is
  **unexercised**, not a passed or failed presentation check. The earlier exact
  saved-program `15.40%` replay remains separate local evidence.

Provider-free reconstruction reproduces catalog fingerprints and candidate cohorts.
Statement-type wording in scope/search hints becomes an implicit local subject,
weakening the correct input cells' rank. An authored control removes only the exact
declared basis from copied search hints: profit becomes visible, revenue still does
not. This is partial diagnostic evidence, not a complete fix or a new model answer.
Next is numeric requirement exposure characterization/correction, including source
bundle ranking, with permissions/IDs/accepted evidence preserved. Requested-statement
cash retrieval remains a separate seam; add no company/metric-specific runtime rule.

Fresh `72b5dced...4b3ca` consumed once after identical SDK and full-wrapper rehearsals.
All **23 requests** completed: Terra 4, Astra 2, embeddings 17; no API/parsing/unhandled
runtime error, Compiler feedback/SDK/whole-question retry, Google/context call or
fresh ingest. Estimate **USD 0.68876178**; shared accounting **4.03709392 / 7**,
remaining **2.96290608**, peak with reservations **5.44039392**, pending 0; not invoice.
All **717** protected predecessor files, 19 frozen admission files and original
source bytes remain unchanged; working source tables match at 1,872/59,477 rows.
No production source code changed during verification. These known-source cases
and fresh plans/retrieval are neither unseen holdout nor isolated patch/model proof.

## Numeric input exposure correction without API calls (2026-09-17)

The [frozen replay and anonymous contracts](../../benchmarks/results/numeric_requirement_exposure_2026-09-17/RESULTS.md)
on baseline `0d4f619d` reproduce both missing exact margin inputs. Numeric matching
now keeps declared basis fragments out of inferred subjects. Within the existing
scope/subject/kind/unit/metric tiers, basis terms in one attached source-context
partition rank before the arbitrary source-identity tie-break. Repeated words,
metadata, row bodies and separate cells/contexts add no hint. Explicit subjects,
source conditions, bundle atomicity/capacities and Compiler interpretation remain.

Both exact inputs now appear in their requirement permissions, candidate payload
and generated Compiler schema choices. All seven cases retain saved program
source IDs; six payloads are byte-identical. The changed margin payload is
94,416 → 48,421 UTF-8 bytes in the same local serialization, not SDK tokens or
measured cost. Queries/plans, catalogs/source windows and historical replies are
unchanged. The saved response still reports missing; no new answer is synthesized.

Eight new contracts, focused **164/164**, full **1,890/1,890**, no skips (53.692s),
and domain audit 83 pass with provider/external connection attempts 0. All 765
protected predecessor files remain unchanged. Next is the separate cash query's
requested-statement retrieval gap, followed by a bounded fresh normal-app check
of source choice, calculation and fixed decimals. The shared budget remains
unchanged; no consumed admission is reusable.

## Cash source supplementation without API calls (2026-09-17)

The [read-only source replay](../../benchmarks/results/cash_source_retrieval_2026-09-17/RESULTS.md)
on baseline `4688a070` identifies a retrieval mechanism bug: numbered column names
in a notes header received atomic-value priority, overriding the existing statement
preference and displacing the requested full statement from the numeric supplement.
The latest saved Planner had no explicit section binding; this correction does not
invent one or change the Planner's semantic responsibilities.

The retrieval owner now requires a complete finite numeric value cell on the same
physical line, using shared number/unit parsing. Existing scores, source scope,
statement ordering, supplement quotas and Compiler/source contracts remain.
Replaying all 1,872 source chunks changes only the latest cash supplement to the
full consolidated statement. The saved 32-source seed pool plus this supplement
exposes **3,576,456,533,329원** in its output permissions, payload and schema choices.
The old summary candidate remains in the catalog but is displaced from exposure;
the original paid answer remains unchanged. Six other catalog/payloads are identical,
including the now-exposed margin inputs. Cash payload is 22,810 → 24,137 UTF-8 bytes
in local serialization, not SDK tokens or measured cost.

Eight new contracts, focused **98/98**, full **1,898/1,898**, no skips (55.322s),
and domain audit 83 pass. Provider/external connection attempts 0; all 790 protected
predecessor files remain unchanged. Primary searches and model responses were not
rerun, so this is retrieval/exposure evidence, not a new answer or semantic accuracy.
Next is bounded fresh normal-app verification of requested source choice, margin
calculation and fixed decimals. Accounting remains **USD 4.03709392 / 7**, remaining
**2.96290608**, not invoice; use a new immutable admission, never a consumed packet.
