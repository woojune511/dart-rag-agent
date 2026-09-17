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

## Fresh numeric source and display verification (2026-09-17)

The [fresh normal-application run](../../benchmarks/results/numeric_final_app_2026-09-17/RESULTS.md)
on clean `e0a7f40e` returns HTTP 200 and ledger ok for both unchanged known-source
questions: **1/2 runtime complete**, **1/2 outputs**, **1/2 full frozen acceptance**.
Margin now uses exact consolidated 2023 revenue and operating profit, computes
15.395255319023432% before request-grounded rounding and displays **15.40%** in the
answer, slot and trace. No source-stated ratio display or feedback repair is used.
This is live fixed-decimal evidence for the sampled question.

Cash now retrieves the exact full statement, with **3,576,456,533,329원** cataloged
and owner-visible. It remains incomplete because Planner puts `원문 단위` in the
numeric `display_unit` field. The existing `invalid_obligation_unit` preflight
blocks before any Compiler call; direct child inputs remain empty. Final cash
source selection is unverified. This is a requirement-contract error, not an API
failure or Compiler refusal. A provider-free diagnostic copy with empty unit clears
preflight only; original plan/response bytes are unchanged and no answer is implied.

Fresh `3b03b442...de07c7` consumed once after identical SDK rehearsals and full-wrapper
controls. **22/22** requests complete: Terra 4, Astra 1, embeddings 17; API/parsing/
unhandled runtime errors and all retries 0, requirement preflight error 1. Estimate
**USD 0.36485839**; shared **4.40195231 / 7**, remaining **2.59804769**, pending 0;
not invoice. All 820 predecessor and 16 admission files/original source bytes remain
intact; the ready working store's 1,872 source/59,477 metadata rows match the original.
Runtime did not change; its existing full 1,898/audit 83 gate was not rerun here.

This paid result remains unchanged after the provider-free clarification below.
These fresh plans and known sources do not establish unseen accuracy or isolate
individual patch effects; older results remain unchanged.

## Numeric Planner unit/presentation clarification (2026-09-17)

The [provider-free correction](../../benchmarks/results/planner_numeric_presentation_2026-09-17/RESULTS.md)
updates Planner policy and field descriptions only. Concrete named units and
their scale remain in display_unit, even when unsupported. Source-unit/notation
preservation and precision requests go in display_format and exact owned requests;
no unit is guessed before retrieval. Both fields may coexist. Numeric strings
remain open so explicit unsupported requests reach the unchanged preflight;
there is no phrase alias, silent clearing, new field/call or runtime classifier.

Four new authored tests cover numeric presentation/source precision, explicit
scaled units, misplaced/unsupported-unit blocking and actual SDK serialization.
Focused **155/155**, import/topology and domain audit pass; provider calls and
attempted external test connections **0**. Prior full 1,898 gate was not rerun
for this instruction-only change. Strict schema constraints are identical after
removing descriptions; local schema/template sizes grow 15,612→16,719 and
10,553→11,323 UTF-8 bytes, not SDK token measurements.

Exact two-case replay preserves catalog/cohorts and original cash rejection;
the saved margin program and answer remain **15.40%**. The authored empty-unit
cash copy clears preflight with exact source visible and unchanged permissions,
without a Compiler call or answer. All **863** predecessor files are preserved.
One initial SDK test fixture lacked its required callback; fixing the fixture
resolved that local error without any provider request or runtime change.

This local turn made no paid calls: shared estimate at that point was
**4.40195231 / 7**, remaining **2.59804769**. Authored plans are not new model
responses. Fresh Planner behavior and cash selection are separately verified below.

## Fresh verification after numeric Planner clarification (2026-09-17)

The [normal-app run](../../benchmarks/results/planner_numeric_app_2026-09-17/RESULTS.md)
on clean `930325f0` completes both unchanged known-source questions through real
shared services and ASGI /api/query: HTTP 200/ledger ok **2/2**, runtime/output
completion **2/2**, full frozen source/arithmetic/display acceptance **2/2**.

Cash Planner emits empty display_unit and keeps 원문 단위로 in display_format
and both owned request units. The final direct answer selects the full
consolidated balance-sheet cell for 2023-12-31: **3,576,456,533,329원**, with
original precision/unit and selected-source citation. Direct child inputs stay
empty. Its first Compiler response already selects this cell, but adds a
liquidity discussion from a different source context as compatibility support.
The existing direct_compatibility_context_mismatch validator rejects it. One
allowed feedback response removes only that witness; selected cell, interpretation,
attached basis/date context and visible candidates remain identical.

Margin uses the exact 2023 consolidated revenue/profit cells and computes
profit/revenue × 100 with an owned final-round quantity 2. Answer, slot and
trace display **15.40%**; no source-ratio substitution or feedback repair.
This verifies the sampled Planner/source-choice/fixed-decimal path, not unseen
accuracy or an isolated prompt effect; plans/retrieval differ from earlier runs.

Fresh manifest `6857684d...e100df` consumed once. **22/22** requests complete:
Terra 4, Astra 3, embeddings 15; API/parsing/unhandled runtime/requirement errors 0.
One initial Compiler validation error/feedback repair; SDK and whole-query retries 0.
Estimate **USD 0.70462915**; shared **5.10658146 / 7**, remaining **1.89341854**;
peak including reservations **5.89606896**, pending 0, not invoice. All **891**
predecessor/16 admission files and original bytes remain intact. Working source/metadata
tables are identical at 1,872/59,477 rows and the source remains ready. No runtime,
configuration or ingest change; same-runtime local 179 checks reused, not rerun.

The provider-free follow-up below preserves this paid result and its retry. The
preceding 1/2 result and all earlier responses keep their original status.

## Direct compatibility-witness clarification (2026-09-17)

The [provider-free characterization](../../benchmarks/results/direct_compatibility_guidance_2026-09-17/RESULTS.md)
reproduces the exact first cash rejection: the selected balance-sheet cell is
already correct, while a separately located same-topic narrative is insufficient
as direct compatibility support. The actual repair retains the cell, interpretation,
attached basis/date and visibility; only its declared witness list becomes empty.

Numeric Compiler instructions and the direct field description now distinguish
needed scope support from general corroboration and attached context_ref IDs.
Use [] when the selection's own axes/metadata/context already support scope.
Existing validation still requires at least one same-context witness for a nonempty
list and checks each witness's source/owner/company/period independently. Legitimate
located scope support and derived cross-context compatibility remain available;
invalid model refs are not cleared or repaired by code. No schema constraint,
retrieval, store, model-setting or provider-call change is included.

Six new anonymous/authored SDK contracts; focused **217/217**, import/topology
**22/22**, docs **2/2**, domain audit **83** pass. All external test connections and
provider calls are **0**. Exact replay preserves both catalogs/cohorts and all three
original wire lowerings, first cash rejection and both final answers
**3,576,456,533,329원 / 15.40%**. All **936** protected files remain intact.
Direct strict schema grows 3,188→3,639 UTF-8 bytes with identical constraints after
removing descriptions; derived schema remains 9,670 bytes. Numeric template grows
13,240→13,824 bytes. These are local serializations, not SDK token or cost measures.

No new sampled response or measured retry reduction. Latest full 1,898 gate predates
this and the Planner instruction change; focused gates cover this bounded seam.
Shared estimate remains **USD 5.10658146 / 7**, remaining **1.89341854**, not invoice.

The [three-question review set](independent_question_review.md) is now prepared below; no new model result is claimed.

## Independent-question review preparation (2026-09-17)

[Frozen review set](independent_question_review.md), manifest `89fe64e1...21fd2`:
three newly authored known-report questions cover standalone prior-year dividends,
standalone two-period revenue growth and Chuncheon/Sejong environmental attribution.
References are **468,978,562,474원 / 1.76%**, three required narrative themes and one
optional PUE criterion; Sejong LEED Platinum stays pending in the reported context.
No app query or model response was generated. Reference selectors remain review-only.

Three physical cells/four exact quotes, independent arithmetic and ordinary request
schemas pass; 11 altered pack copies are rejected. All five primary/contrast chunks
exist in the working store with exact text/filing scope; original/working logical
tables remain 1,872/59,477 rows. All 969 predecessor and 170 runtime files are
unchanged. These are reference/pack checks, not normal retrieval, Compiler visibility
or semantic accuracy measurements. Existing 241 runtime checks were not rerun.

Next is a fresh immutable admission and one normal-app pass of the frozen requests
under the remaining shared **USD 1.89341854** (accounted **5.10658146 / 7**, not
invoice), preserving existing source/model settings and terminal-stop rules.
No review-answer injection, consumed-manifest reuse, automatic rerun or fresh ingest.
