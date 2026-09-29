# OpenAI compiler migration probe

Three separately approved trials executed on 2026-09-16: the first two under USD 6
caps, the exposure successor under USD 7. The six-case Compiler trial passes all
12 frozen outputs. Both full-agent runs complete 2/3 questions and 5/6 outputs,
with no API/runtime errors. The successor calculates Commerce growth correctly,
but acquisition-impact narrative exposure is incomplete in that recorded run.
The narrative exposure fix below is provider-free; Google stays the default.

The current `FinancialAgent` factory supports an explicit `openai` route with
output/retry limits, reasoning effort, endpoint mode, storage, tier, timeout and
the existing per-phase usage callback. `temperature: null` omits the sampling
parameter. Google-only thinking options fail locally on an OpenAI route.
Google and OpenRouter defaults are unchanged.

The OpenAI structured adapter requires all fields explicitly, removes schema
default annotations and retains enums, references and value/array constraints.
It validates the returned JSON against this stricter schema and the original
Pydantic model. It never fills missing wire values or repairs an answer. Refusals
and incomplete responses cannot become valid programs. Invocation remains on
the caller's thread so phase usage is retained. Native OpenAI answer/reasoning
counts are disjoint; reasoning is already included in the API output total.

## Executed settings

```json
{
  "provider": "openai",
  "model": "gpt-6-astra",
  "temperature": null,
  "max_output_tokens": 5120,
  "reasoning_effort": "medium",
  "provider_client_retries": 0,
  "use_responses_api": true,
  "store": false,
  "service_tier": "default",
  "timeout_seconds": 90
}
```

The tested configuration targets `llm_routes.program_compilation` only.
This generation-provider change does not require rebuilding the embedding store.
Account access and schema acceptance succeeded for this run's six requests.
Sources: [migration parameters](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md#migration-quickstart),
[structured output constraints](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas),
and [API prices](https://developers.openai.com/api/docs/pricing).

## Approved comparison and results

The local ignored [packet](../../benchmarks/results/openai_compiler_preparation_2026-09-16/)
reuses the previous six anonymous inputs and fixed criteria: mixed unit scales,
source-format swap, signs, source display versus calculated dependency, half,
and negative multiplier. Each receives one first response. No planner, retrieval,
embedding, fresh ingest, store mutation, Google call or automatic retry is included.
The consumed Google manifests and responses remain immutable.

Two real SDK rehearsals with blocked sockets produce identical bodies. Six
authored responses pass the unchanged execution and ledger checks, including
12 numeric/display outputs. These are local witnesses, not model answers.
OpenAI's explicit-field schema differs from Google's wire; this is a historical
provider/transport comparison, not an isolated model A/B or a generalization test.

The approved cap was **USD 6.00**. Six independent request reservations summed to
**USD 4.73755** using canonical UTF-8 request bytes plus 1,024 as a conservative
input estimate and all 5,120 output tokens per call, including reasoning.
Input accounting uses the **USD 12.50/M cache-write rate** for every input token,
above the USD 10/M uncached and USD 1/M cached rates; output uses USD 50/M.
This stays below the long-context threshold. Reservations are conservative
estimates, not server token counts or a billing guarantee.

The approved manifest `8144726f02bea29f8bc0e7b8f1a8d07fcf9e8e5567969f965c535b158a6273d3`
was consumed once on clean `3354fbc9`. No SDK, Compiler or automatic retry occurred.
All six actual request hashes match the frozen SDK rehearsal; runtime, packet and
67 predecessor file hashes were checked before and after the blocked-socket review.

| Observed result | Value |
| --- | --- |
| API responses / provider errors / parse errors | 6 / 0 / 0 |
| Strict wire / original schema / runtime / ledger | 6/6 each |
| Frozen source, finite-formula, display and value/unit checks | 12/12 outputs |
| Input / output tokens, including reasoning | 53,677 / 5,352 |
| Reported reasoning / cached input tokens | 226 / 0 |
| Generation time total / mean | 89.27s / 14.88s |
| Conservative accounted cost / cap | USD 0.9385625 / USD 6.00 |

[Detailed results and original replies](../../benchmarks/results/openai_compiler_preparation_2026-09-16/RESULTS.md)
retain source-display/dependency checks, including half and negative multipliers.
Actual billing is unobserved. This is six known synthetic cases, one sample each;
it establishes acceptance for these requests, not general availability, unseen
semantic accuracy or current full-agent performance. The prior Google HTTP 400
has no model response and cannot be an accuracy denominator. No default promotion
was included. The separately approved full-agent successor below preserves these
inputs, criteria, responses and consumed history.

## Executed full-agent successor

The [three-question packet](../../benchmarks/results/openai_compiler_full_agent_admission_2026-09-16/)
keeps the existing NAVER and Celltrion questions and source-review criteria. Routing,
planning and retrieval run fresh; only `program_compilation` changes to the OpenAI
route above. Original stores are verified and copied; the default incomplete store
is not used. Previous plans, catalogs, answers and review criteria are not injected.

One shared **USD 6** cap covers Google generation/counts, OpenAI Responses and query/
canonical embeddings. Outer limits: 12 Google generations and 12 counts, 12 OpenAI
Responses, 64 embedding calls. Existing Compiler repair is at most one per island;
SDK retries, automatic run retries, fresh ingest and paid judges remain zero.
Limits do not guarantee all calls or questions fit the cap; unknown usage or errors
stop the run. No point cost prediction is made for fresh plans and tokenization.

Python 3.13 full unittest **1,807/1,807**, no skips (51.415s); mixed-provider focused
46 and packet checks 7 pass. Both store copies open and pass existing-vector probes.
Separate SDK/runner no-call processes produce identical receipts. These checks do
not measure live OpenAI narrative acceptance, fresh retrieval or full-agent accuracy.
After user approval, manifest `9a85a367a80f37ffdb213afa135e2d3fbe6e7e750e8460bbdce2a15fe14f2f0d`
was consumed once on clean `5dbcdb0c`. **2/3 questions complete, 5/6 outputs accepted**;
API/runtime errors 0, all three ledgers `ok`, five parsed Compiler responses and no
Compiler/SDK/run retry. NAVER B2B/AI strategy and Celltrion risk policies complete;
NAVER acquisition impact is supported but its growth calculation is missing.
All 29 accepted subject/fact support occurrences match immutable stored sources.
Separate Codex source review uses the frozen criteria; this is not human gold.

Offline reconstruction matches the live 509-candidate catalog's ID/content hashes.
Commerce current/prior amounts are present, but each numeric input exposes only
total consolidated revenue alternatives. The Compiler declines those substitutes
and discloses the missing calculation. This is a candidate-exposure loss, not an
API rejection or missing source catalog; the offline follow-up below diagnoses the ranking cause.
No received answer, source or validation rule was repaired to create success.

Observed calls: Astra 5, Flash 6, query/canonical embeddings 22, Google counts 6.
Astra input/output usage is 76,758/4,803; conservative generation/embedding estimate
USD 1.23127504 plus count contingency 0.36 = **USD 1.59127504 / 6.00**. Outstanding
reservation 0, peak reserved 2.27336254; actual invoice unobserved. Source stores,
169 runtime files, 16 packet and 191 protected files verified before docs edits.
Captured Compiler attempts preserve schema-parsed JSON, not original HTTP bytes.

[Results and exposure diagnosis](../../benchmarks/results/openai_compiler_full_agent_2026-09-16/RESULTS.md)
retain original output hashes. Fresh plans split the first question into two outputs;
code and plans differ from the historical Google 2/3, 3/5 result, so counts cannot
establish a causal model improvement. Next: provider-free exposure diagnosis with
anonymous total/segment and row/column controls, preserving eligibility. No automatic
paid retry, new default, unseen accuracy or release claim follows this run.

## Provider-free exposure follow-up

The [offline follow-up](../../benchmarks/results/candidate_exposure_offline_2026-09-16/RESULTS.md)
reproduces the live exposure from immutable catalog/plan inputs. Exact subject
comparison left the descriptive target and observed table label unresolved; the
total-revenue rows then won on exact metric names. A complete own-axis label
appearing literally in a declared numeric target now supplies a ranking hint.
Unknown identity/applicability stays unknown; source conditions, interpretation,
bundle limits and execution validation are unchanged. No suffix stripping or alias
inference is used. The hint stays in diagnostics, outside Compiler input.

Local replay now exposes both Commerce segment-note cells; four narrative island
payloads remain byte-identical. The numeric island grows from 9 to 18 visible
candidates and 51,302 to 88,405 local candidate-payload UTF-8 bytes because whole
physical rows remain atomic. These are not SDK tokens, cost or a new model answer.
Original source/plan/result artifacts are unchanged; no API call or store write.
The paid result above remains 2/3 complete. Further live validation needs a new
approved manifest/cost cap and must account for the larger numeric input.
Eight anonymous exposure contracts and focused 101 tests pass; full Python 3.13
unittest **1,815/1,815**, no skips (47.747s), audit 83 and import/topology/docs pass.

## Exposure successor preparation

The [new admission packet](../../benchmarks/results/openai_compiler_exposure_admission_2026-09-16_v2/PREPARED.md)
keeps the same three questions, source stores, models, generation controls and call
limits. Runtime source matches the tested `96dcf198` fingerprint. Ten packet checks
pass and two separate-process no-call SDK/runner receipts are byte-identical;
270 predecessor/input files and both original stores are preserved. Preparation
made no paid call, new answer, fresh ingest, document embedding, or default change.

Actual SDK serialization of the recorded independent first-island inputs gives
77,809 to 114,063 canonical UTF-8 bytes for the numeric request. Its reservation
increases by USD 0.453175; all four narrative request hashes match the paid run.
Five first-request reservations total USD 5.4372125. Adding historical Google/query
embedding usage (USD 0.03165004) and the maximum count allowance (USD 0.72) gives
USD 6.18886254, so the proposed shared cap is **USD 7**. This mixes reservations
with labeled historical usage for sizing, not a future cost prediction or bill.
Fresh plans/retrieval and any permitted repair may change inputs; every call still
requires a reservation within the remaining shared cap, with no automatic rerun.
The original USD 6 preparation draft is retained as unexecuted sizing evidence.
Offline saved-input sizing is excluded from live reads. The user separately approved
the immutable manifest and USD 7 cap before the single execution below.

## Executed exposure successor

Manifest `f9bbe243b2e6ac04306b399c847f613a65361e37610d6dc3b6f78ef58584dc41`
was consumed once on clean `5a8fd0ad`. [Results and source review](../../benchmarks/results/openai_compiler_exposure_full_agent_2026-09-16_v2/RESULTS.md):
**2/3 complete, 5/6 outputs**, API/runtime errors 0, ledger 3/3, six Compiler first
responses and no repair. Both complete narrative questions retain source support.

Commerce current/prior segment-note operands now reach Compiler. The selected
2,546,648,516 and 1,801,079,126 thousand-KRW cells share scope; attached current/
prior contexts ground the periods. Independent Decimal recomputation matches
41.3957043439745%, displayed 41.4%; source display is null for the calculation.
The acquisition narrative instead abstains: its visible excerpts show a group-wide
effect, while a direct Commerce-impact paragraph remains unexposed in the current
537-candidate catalog. All six previously visible related sources still exist.
Offline crossed previous/current catalogs and plans reproduce exposure according
to the plan in both catalogs. This isolates a planner/exposure boundary in these
inputs, not one specific changed field, new model accuracy, or a model A/B effect.

Calls: Astra 6, Flash 6, query/canonical embeddings 24, counts 6, all 42 complete.
Generation/embedding estimate USD 1.41336055 + count contingency 0.36 =
**USD 1.77336055 / 7**, pending 0, peak reserved 2.45749805, not an invoice.
Runtime, 19 packet, 270 protected and 23 original-store files verified; all
26 accepted support occurrences match stored sources. No raw response/result or
source mutation, new runtime code, fresh ingest or default change. Next: provider-free
anonymous narrative exposure controls for planner expression variation. No paid
retry, resume or release claim follows from this consumed run.


## Offline narrative exposure successor

The [saved-input comparison](../../benchmarks/results/narrative_exposure_offline_2026-09-16/RESULTS.md)
reproduces the omission on `025794cc`. Eight field combinations show that restoring
only subjects, metrics or search hints does not recover the direct paragraph;
subjects plus either metrics or hints do. No saved plan is injected into a live run.

The narrative matcher now admits a same-surface pair of a declared subject term
and an owner-local search-hint term when the full subject mention is absent.
Original/resolved metric, concept-alias and scope terms are excluded from subject
anchors. Separate cells/contexts, hidden tails, repeated/nested terms, sibling hints
and unpartitioned structured bodies cannot create this new signal. It preserves
full targets, identity/applicability, source conditions and existing mention paths;
Compiler receives no rank hint and still must ground each claim.

The direct impact paragraph is exposed within the existing six-candidate limit.
All five other candidate payloads, including the growth input, remain byte-identical;
all source catalogs and plans retain their fingerprints. Changed narrative payload
is 26,096 to 25,823 UTF-8 JSON bytes, not an SDK-body/token/cost measurement.
No answer is generated or repaired, so the live 2/3 result remains unchanged.

Fourteen anonymous contracts and full Python 3.13 unittest **1,829/1,829** pass,
no skips (51.111s); audit 83, import/topology/docs, pycompile and diff checks pass.
The 326 protected original files and 23 store files remain unchanged. Further paid
validation needs a new immutable manifest, cost bound, no-call rehearsal and
separate approval; the previous consumed manifest grants no retry authority.

## Executed narrative exposure successor

The user's explicit instruction to proceed without another approval question
superseded repeated confirmation for this bounded successor. New manifest
`ec2e65e15179b1180ef5cf67176cdff68f55c04e575a3fde2d954cd1cd98892f` bound clean
`e07b2704`, the same three questions/stores/routes and shared USD 7 ceiling.
Ten admission checks passed, two separate no-call rehearsals were byte-identical,
and reconstructed SDK requests preserved five of six prior first-request hashes.
Saved-input reservation scenario USD 6.65749805 was not a live cost prediction.

[Results and source review](../../benchmarks/results/openai_compiler_narrative_full_agent_2026-09-16/RESULTS.md):
**3/3 complete, 6/6 outputs**, API/parsing/runtime errors 0 and ledger 3/3. Seven
Astra responses comprise six first attempts and one allowed feedback repair after
an unauthorized context reference in the first narrative question. Its rejected
program remains recorded; SDK and whole-run retries are zero. The other five first
island programs passed. The direct Commerce-impact paragraph is exposed and cited.
The answer separates other growth factors from consolidation effect and preserves
post-acquisition Poshmark/subsidiary revenue/net-loss scope. Independent operand/
period review retains 41.3957043439745%, displayed 41.4%, with no source-display
substitution for the explicit calculation. Both other narrative themes are complete.

All 43 attempts completed: Astra 7, Flash 6, query/canonical embeddings 24, counts 6.
Usage estimate USD 1.67351403 + count contingency 0.36 = **USD 2.03351403 / 7**,
pending 0, peak reserved 2.70855153; not observed billing. All 35 accepted support
occurrences from 15 narrative claims match stored sources. Assistant review supports
the frozen question-derived criteria, not human gold or unseen generalization.
Runtime/21 packet/335 protected/23 original-store files were verified before docs.

Original runtime/results/stores are unchanged by review. The raw execution receipt
keeps `completed_once_pending_review`; source and integrity reviews are separate.
Prior paid 2/3 results and the Google admission failure remain historical facts.
Fresh plans and retrieval differ, so this is not an isolated causal model/patch test.
Google remains the default and routing/planning provider. Next: normal-entrypoint
OpenAI Compiler configuration and broader independent regression coverage before
any default promotion; no automatic paid rerun or consumed-manifest reuse.

## Application profile wiring (provider-free)

[Normal API/Streamlit configuration](../../README.md#run-the-api) now selects the
reviewed Compiler route through `DART_LLM_PROFILE=openai_compiler`. The shared
service builder forwards this named profile to `FinancialAgent`; routing/planning
and contextual ingestion retain the Google default. The profile does not import
any frozen benchmark input or install its shared cost/call admission. Unknown
profiles and missing Compiler keys fail before store/query-router startup when
initialization is otherwise allowed. Unselected/blank/`google` preserves defaults;
process environment overrides `.env`. Local activation only appended the profile
setting; previous settings and credential bytes were preserved.

A real FastAPI lifespan test also reproduced and fixed project-path shadowing by
the nested root endpoint. [No-call validation](../../benchmarks/results/app_openai_profile_no_call_2026-09-16/RESULTS.md)
passes **1,838/1,838**, no skips (53.600s), with nine new profile tests, external
network blocked and zero external connection attempts. Audit 83, import/topology/
docs, pycompile and diff checks pass. Actual SDK serialization and no-transport-
retry behavior are exercised using authored responses and mocked storage/routing.
This changes no historical paid result and does not certify a new live answer.

No server, fresh ingest or provider run was started. Read-only default-store
manifest readiness is `mismatch`; the next normal-entrypoint smoke run needs a
verified disposable store copy. Original source stores and frozen results remain
unchanged. Remaining Google phases and independent question coverage are pending.

## Normal application store connection and API smoke

Clean `4bab8ea7` adds explicit `DART_COLLECTION_NAME` selection alongside
`DART_STORE_PATH`; the default collection and canonical manifest/source checks
remain strict. Local settings connect a byte-identical NAVER 2023 source-store
copy at `data/app_nav_2023_20260916`, with its existing collection and vectors.
No collection rename, manifest adoption, fresh ingest or original-store write.

[Actual API result and source review](../../benchmarks/results/app_store_smoke_2026-09-16/RESULTS.md)
use normal FastAPI lifespan/shared services through in-process ASGI HTTP, with real
providers and fresh planning/retrieval. Health, companies and one mixed query return
200; storage is compatible/non-degraded/source-complete, 1,872 chunks. Runtime
accepts 2/2 outputs and ledger integrity is ok; API/parsing/runtime errors, feedback
repairs and SDK/whole-run retries are zero. No external listening server was started.

Fresh manifest `230fceea0b85052267c91729def00721bc8ecc9cc6a473a63a7cc303bcfbb71a`
was consumed once under delegated USD 7 authority, after two identical no-call
app/SDK rehearsals and a terminal-failure check. Normal app model and retrieval
settings were preserved; an external caller applied cost/call/single-dispatch limits.
Google default bodies used a conservative byte input bound and model-ceiling output
reservation, without a count call or the earlier benchmark's generation settings.
All 18 attempts completed: Astra 2, Flash 2, embeddings 14. Estimated usage cost
USD 0.61264133, peak reserved 1.70867883, pending 0; not observed billing.
Full unittest 1,841/1,841, no skips (53.618s), external network blocked and zero
attempted external connections; audit 83, import/topology/docs and diff pass.
All 398 protected files, including both original stores and inactive default, match.

Independent arithmetic/source review retains 41.3957043439745%, displayed 41.4%.
Two narrative claims and four subject/fact support occurrences match original
sources and retain subsidiary versus segment scope. Narrative completeness remains
partial: direct Commerce-impact source `20240318000844:888:5` is retrieved but none
of its candidates reaches the narrative window. The emitted answer supports the
platform role and acquired-group revenue/net loss; it omits management's direct
Commerce-growth explanation. Runtime 2/2 therefore does not satisfy the complete
narrative review criterion. This is one known-source app sample, not unseen quality,
a release gate or a causal comparison with the differently planned benchmark run.
Next: reproduce the normal-profile exposure gap offline before another live run,
then expand independent questions and migrate remaining Google phases.

## Normal-app narrative evidence successor

The [frozen-input diagnosis](../../benchmarks/results/app_narrative_exposure_offline_2026-09-16/RESULTS.md)
reproduces a ranking inconsistency: a complete literal subject mention disabled an
independent same-surface joint topic hint. The ranking owner now evaluates that
hint independently, while preferring a literal mention with an independently
matched primary/search topic over a weak lexical pair. Seven new anonymous controls
cover both the omission and protection against displacing stronger evidence.
All source conditions, physical partitions, identities, validation and numeric
matching remain strict. Five of eight saved payloads are identical; the two changed
cloud windows retain all accepted evidence, as do the other historical narratives.

[Fresh normal-app validation](../../benchmarks/results/app_narrative_smoke_2026-09-16/RESULTS.md)
on clean `abf87889` completes one ASGI `/api/query` with actual providers and normal
app settings: HTTP 200, **2/2 complete outputs**, ledger ok, errors/repairs/retries 0.
The direct Commerce-impact paragraph is now visible and cited. Independent arithmetic
retains 41.3957043439745% → 41.4%; two narrative claims and five support occurrences
match original sources. Other growth factors, acquired-group revenue/net loss and
segment/group scope remain distinct. The frozen numeric/narrative/runtime criteria
pass separate assistant review, not human gold or unseen-question evaluation.

New manifest `70d63a929fb5f2140dd7906d4a22f8c65d0d8d1e9291dc84343211ef4e8b96f7`
was consumed once under delegated USD 7, after identical no-call app/SDK rehearsals
and terminal-failure validation. Seventeen completed attempts: Astra 2, Flash 2,
embeddings 13; estimated USD 0.59734408, peak reserved 1.45699408, pending 0, no
count calls; not invoice. The ready working copy and local configuration are unchanged.
All 433 protected original/source/result files match. No ingest or external server.

Full unittest **1,848/1,848**, no skips (53.931s), external network blocked and zero
attempted external connections; focused 53/53, audit 83, import/topology/docs,
pycompile and diff pass. The earlier incomplete live answer remains a historical
fact. Fresh plans differ, so the new sample is not an isolated causal patch test or
a general accuracy/release claim. Next: independent question coverage and remaining
Google phase migration; no automatic paid rerun or consumed-manifest reuse.
