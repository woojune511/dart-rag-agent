# Independent question review set

Prepared 2026-09-17 from clean `d2f62aca`; runtime
`83dfc4c93419d320709f237db8c070f6ae27efd4a82f8c451de894310c7cf0e4` is unchanged.
The review packet was **prepared only** before dispatch. The subsequent normal-app
pass below completed two questions and interrupted the narrative at the budget limit.

The three questions below extend the recent cash/margin/payment/cloud examples
to standalone statements, a comparative measurement year and environmental
attribution. They use known NAVER 2023 report sources and assistant-reviewed
criteria. This is not a blind holdout, unseen-company evaluation or human gold.
Twenty protected admission files contain ten unique earlier questions; none is
an exact duplicate. This limited novelty check does not establish absence from
every historical dataset or model training.

## Frozen questions and review criteria

1. **Direct lookup** — NAVER의 2023년 사업보고서에 포함된 별도 현금흐름표에서 2022년 배당금수취 금액은 얼마야? 원문 금액과 단위를 그대로 알려 줘.

   Expected: **468,978,562,474원** from the standalone cash-flow dividends-received
   row, 제24기 / 2022, within the **2023** filing. Preserve all digits, the original
   unit and source citation. Current-year 191,541,688,548원 or consolidated
   prior-year 34,753,150,218원 does not satisfy the request. Dividends paid is a
   different row. The direct empty-child-input contract stays in force.

2. **Calculation** — NAVER의 2023년 사업보고서에 포함된 별도 손익계산서를 기준으로, 2022년에서 2023년으로의 영업수익 증가율을 계산해 줘. 공시된 비율 대신 두 연도의 금액으로 계산하고 소수점 둘째 자리까지 보여 줘.

   Standalone operating revenue: 2022 **5,512,586,322,305원**, 2023
   **5,609,799,005,883원**. Use 2022 as the reference denominator and 2023 as target:
   `(target - reference) / reference * 100` = 1.7634677789018652…%, displayed
   **1.76%**. Preserve source inputs and deterministic calculation/rounding trace;
   no consolidated inputs, reversed endpoints or source-stated ratio substitution.

3. **Narrative** — NAVER의 2023년 사업보고서에 따르면 데이터센터 각 춘천과 각 세종은 어떤 방식으로 환경 영향을 줄이고 있어? 두 센터의 활동을 구분하고, 세종의 친환경 건물 인증 진행 상태도 설명해 줘.

   Required coverage: Chuncheon's outside-air conditioning, solar/natural energy
   and efficient equipment; Sejong's natural-environment use and minimizing/reusing
   existing green space during construction; Sejong's **LEED Platinum pending**
   status as stated in the report. Keep the centers and achieved/planned status
   separate. PUE **1.1x** is optional context belonging to Chuncheon; do not turn
   it into an exact figure or Sejong result. Headquarters renewable-energy
   percentages do not describe either center. Dates/PUE are optional, not required
   for this question about methods and certification status.

## Source and execution boundaries

| Reference | Source chunk | Located evidence |
| --- | --- | --- |
| Prior dividends received | `20240318000844:548:4` | 4-4. 현금흐름표, 배당금수취, 제24기 |
| Operating revenue pair | `20240318000844:546:2` | 4-2. 포괄손익계산서, 영업수익 (주33), 제24/25기 |
| Environmental methods/status | `20240318000844:61:3` | II. 사업의 내용 > 7. 기타 참고사항, exact center-specific passages |

These are **review references**, not a runtime candidate allowlist. Equivalent
faithful source evidence may satisfy review. Only the question, normal report_scope
and existing review/debug flags enter `/api/query`. No expected values, selected
source IDs, reference candidates, frozen plans or review controls enter the model.
The report filter remains 2023 even when the requested measured value is 2022.

Check transport/ledger, request/source scope, source values/provenance,
arithmetic/display and narrative attribution/completeness separately. All applicable
axes must pass for full acceptance; narrative arithmetic is not applicable.
Keep raw initial/feedback replies. Runtime completion and linked source text alone
do not certify correct subject attribution or semantic completeness.

## Provider-free verification

- Three numeric cells reconstructed from immutable table payloads, with physical
  identity, source periods and attached headings/date/unit contexts preserved.
- Four narrative quotes located exactly in both candidate text and stored chunk;
  three required themes and one optional performance-context criterion.
- Calculation independently verified with rational arithmetic and Decimal display.
- Three ordinary API request shapes validate without reference information.
- Eleven altered pack copies are rejected: leaked answers/review fields, wrong
  report or measurement year, altered cell/pointer, swapped endpoints, wrong display,
  altered quote/span and omitted required theme. These are **pack checks**, not
  measured runtime refusals or an automatic narrative-meaning grader.
- All five primary/contrast chunks exist in the selected working collection with
  identical text and filing scope. Original/working source tables remain identical:
  1,872 embeddings / 59,477 metadata rows. All **969** protected predecessor files
  and **170** runtime source files are unchanged. No source store was rebuilt.
- API/provider calls, live app queries and external test connections **0**.
  Current-runtime 241 passing checks are retained from the preceding guidance
  change, not rerun; this preparation adds reference validation and docs checks.

## Frozen review packet and subsequent execution

[Local review packet](../../benchmarks/results/independent_question_review_2026-09-17/RESULTS.md)
contains questions, criteria, exact source references, controls and validation.
`review_set_manifest.json` freezes 12 files, SHA-256:
`89fe64e162f1919c19be88877124a1c02836b701cee061d528fc31d6ec621fd2`.
It is a **review-set manifest, not a provider execution admission**.

[Normal-app execution](../../benchmarks/results/independent_question_app_2026-09-17/RESULTS.md)
ran once on clean `107a00de`, unchanged runtime `83dfc4c9`. Execution manifest
`0ec3c9dcfb9712869c029ec37afbb3c24077b7ca84fe76ef78a233f17b6c92db` is consumed.
Only unchanged ordinary requests entered the app; review IDs/answers stayed outside.

| Question | Observed result | Frozen acceptance |
| --- | --- | --- |
| Standalone 2022 dividends received | **468,978,562,474원**; HTTP 200, ledger ok | Pass |
| Standalone revenue growth | **1.76%**; HTTP 200, ledger ok | Pass |
| Environmental methods/status | Local budget stop; HTTP 500, no final answer | Not assessed |

Both numeric outputs use the correct full standalone cells and measurement years.
Growth uses 2022 as denominator, 2023 as target and request-owned final rounding;
answer/slot/trace retain two decimals. Each has one parsed Compiler response, no
feedback repair and no numeric parsing/validation/execution error.

All **46** transmitted requests completed: Terra 6, Astra 4, embeddings 36; upstream
provider errors 0. One additional narrative Astra request was blocked before
transmission by `budget_reservation_exceeded`: requested reserve **USD 1.0099**,
remaining shared allowance **0.95556423**, shortfall **0.05433577**. Usage estimate
**0.93785431**, shared **6.04443577 / 7**, pending 0; not invoice. No SDK/whole-query
retry, cap increase or fresh ingest. Two identical no-call rehearsals and mocked
success/terminal wrapper controls passed. Original bytes, **997** predecessor and
22 frozen admission files remain intact; logical source tables stay 1,872/59,477.

The interrupted narrative's two completed Astra usage records do not reveal their
parsed outputs, island/repair identities or semantic quality. The caller saved
agent/debug output only after successful return and did not use the existing
`capture_request_diagnostics()` exception-delivery scope. No final narrative result
or intermediate diagnostic snapshot was persisted. It is not a completed 3/3 eval.

## Caller persistence correction (provider-free, 2026-09-17)

[Caller correction](../../benchmarks/results/application_diagnostics_capture_2026-09-17/RESULTS.md)
adds `src.ops.application_diagnostics.persist_request_diagnostics(path)` around the
existing agent call in a new non-executable successor template. It saves the
delivered snapshots as a JSON array in `finally`, for both success and interruption.
Debug remains opt-in. No delivered snapshots means no file; existing files are
never overwritten. Persistence failures log only their class and retain the original
run result/exception. Process crashes and partial filesystem writes are not covered.

Six new contracts cover exact success preservation, first/retry/next-island stops,
debug-off, existing files, filesystem failure and nested capture paths. Focused
**18/18**, import/topology **22/22**, docs **2/2** pass. Five mocked SDK/ASGI checks
exercise three separate narrative outputs: the first two responses/validations and
pending third request remain available when a later budget admission or HTTP 503
stops execution. Attempt/island IDs, hashes and safe stop metadata remain distinct.
Success results/request bodies/call counts match capture-disabled controls; failed
queries retain HTTP 500 without fabricating a partial answer or ledger.

All **1047** predecessor files and **170** existing source files remain unchanged;
one ops helper is added, with no application-default import or core semantic change.
The template has no live finalizer/CLI or new provider admission. Actual model calls
and additional cost **0**; shared estimate remains **6.04443577 / 7**, remainder
**0.95556423**. Authored fixtures do not recover the lost historical narrative or
establish its accuracy; that paid question remains interrupted.

## Narrative budget feasibility (provider-free, 2026-09-17)

[Recorded-request sizing](../../benchmarks/results/narrative_budget_feasibility_2026-09-17/RESULTS.md)
on clean `bbd30fbb` finds that the observed narrative request shape does not fit
the remaining **USD 0.95556423**. Current [official Standard pricing](https://developers.openai.com/api/docs/pricing)
matches the pinned conservative rates; canonical JSON bytes + 1024 input overhead,
the 5120-token Astra output reservation and the shared cap are unchanged.

| Observed Compiler request | Settled prefix, cold start | Request reserve | Allowance needed | Shortfall |
| --- | ---: | ---: | ---: | ---: |
| First | 0.06143277 | 0.91717500 | **0.97860777** | **0.02304354** |
| Second | 0.24603277 | 0.91717500 | 1.16320777 | 0.20764354 |
| Last blocked | 0.44033277 | 1.00990000 | **1.45023277** | **0.49466854** |

These thresholds assume the same historical request bounds and settled usage.
The last row admits only the last known request; its response and subsequent calls
are unknown, so this is not a complete-run budget. Even omitting bootstrap in an
isolated sensitivity check leaves the first threshold at 0.97839483, still over
budget. Merely excluding the two completed numeric questions is insufficient.
At unchanged rates/prefix/output, the first body needs at least 1,844 fewer bytes.
This preceding sizing alone demonstrates no lossless reduction or later-call
feasibility. Missing bodies and island/feedback identities remain unavailable;
fresh plans may differ. The separate complete-request comparison follows below.

All **46** old request costs reconcile. Four isolated real-budget controls using
recorded metadata/usage and six exact-threshold checks pass, with all sockets/DNS
blocked; provider calls **0**. These are sizing descriptors, not replayed SDK
bodies or model responses. All **1081** predecessor files, **171** source files,
local settings and original/working stores are unchanged. Documentation checks
**2/2** pass; shared accounting remains **6.04443577 / 7**, pending 0, not invoice.

The resulting presentation audit is recorded below; this older sizing result
and the missing historical narrative observations remain unchanged. Repeated scope
wording remains separate presentation work.

## Lossless narrative request presentation (provider-free, 2026-09-17)

[Request-composition audit](../../benchmarks/results/narrative_request_composition_2026-09-17/RESULTS.md)
on base `0b5aa608` keeps all source text, piece IDs, partitions, ordering, context
attachments, visible candidates and permissions. Only the model-facing addressed
piece representation changes: wire v10 declares `piece_columns` once and carries
`[piece_id, partition, text]` rows. Internal objects and `CompilerResponseV2` remain
unchanged; numeric-only wire v9 is byte-identical. Unknown piece fields fail instead
of losing metadata. No candidate pruning or source rewording is involved.

| Complete saved SDK request | Before bytes | After bytes | Reduction |
| --- | ---: | ---: | ---: |
| Cloud strategy initial | 60,856 | 56,593 | 7.0051% |
| Cloud strategy feedback | 66,987 | 62,724 | 6.3639% |
| Commerce narrative | 96,230 | 91,319 | 5.1034% |
| Commerce numeric control | 110,757 | 110,757 | 0% |

All four saved full-request hashes match before projection, and decoding the rows
restores every complete SDK body exactly. All four response schemas are identical;
saved responses still satisfy those schemas, with their historical invalid/ready
statuses retained rather than regraded. Four paired real-SDK/mock-HTTP controls
cover initial, feedback-retry, numeric and mixed execution with identical programs,
V2 proofs, retry counts and final execution. Seven new tests, focused **70/70**,
full **1,921/1,921** without skips (57.882s), and domain audit **83** pass.

All **1094** predecessor files, **169** unchanged source files, local settings and
original/working stores retain their bytes; two source files implement presentation
and integration. Actual provider/count calls and new admissions **0**. Shared
estimate remains **6.04443577 / 7**, remainder **0.95556423**, pending 0, not invoice.
The full test process exited successfully after reporting an ignored Windows
`ProactorEventLoop.__del__` cleanup warning; this was not a test or provider failure.

These are wire-byte reductions, not measured model-token or billed savings. The
unchanged byte-bound policy reserves 0.0532875 / 0.0613875 USD less on the three
complete narrative samples while retaining the 5120-token output bound. The lost
datacenter request cannot be reconstructed or assigned these savings. Its paid
result stays interrupted, and fresh narrative completion/quality remain unproven.

The subsequent counted-admission extension is recorded below. The preceding
wire-byte evidence does not establish live token costs or narrative completion.

## OpenAI counted-admission implementation (provider-free, 2026-09-17)

The [separate ops extension](provider_admission.md#openai-input-token-count-extension)
is implemented and verified locally. Exact frozen SDK text/schema input is counted
before its unchanged generation; the original full output bound, shared cap and
separate count-call/allowance limits remain enforced. Old byte-bound policies and
application defaults are unchanged. This does not activate or resume a paid packet.

New contracts **19/19**, focused **99/99**, full **1,940/1,940** without skips, audit
**83** pass. Real-SDK/mock-HTTP controls cover input/schema drift, caller mutation,
cached clients, concurrent identities, counts/errors/redirects/usage overruns,
exact budget thresholds, Terra/Astra plus embeddings and independent Google count
limits. An authored Compiler invalid-then-ready pair retains complete generation
bodies, V2 program/proof and execution. Four saved legacy descriptors, eight budget
success/denial receipts and three Google count controls match exact baseline source.

All **1118** protected files, **169** unchanged source files, settings and stores
retain their bytes. Two ops files change and one is added, total **172** sources.
Actual provider/count calls and new execution admissions **0**; shared estimate
**6.04443577 / 7**, remaining **0.95556423**, pending 0, not invoice. Authored counts
are test fixtures, not measured model tokens, endpoint access or a complete-run
budget. The interrupted datacenter result and missing historical traces remain intact.

## Counted application caller preparation (2026-09-17)

The [counted application-caller preparation](../../benchmarks/results/counted_application_caller_2026-09-17/RESULTS.md) binds the exact question/scope/debug envelope and real graph phase to each counted generation, without using diagnostics as authority. It installs before graph construction and permits mock transport only. Shared count/generation/embedding accounting retains the **USD 0.95556423** cap, **12** count and **12** generation limits, **48** embedding limit, **USD 0.01** allowance per count, **300,000-byte / 200,000-token** limits and full **Astra 5120 / Terra 8192** output reserves. **20/20** caller contracts and **66/66** focused runtime contracts pass; **six pairs (12 executions)** of SDK/ASGI scenarios cover success, measured-budget denial, count failure, generation failure and separate count/generation limits. Success answers, complete results, ledger, request bodies and receipts equal capture-disabled controls. Each later stop retains two parsed/ready Compiler programs and the third pending island, preserves HTTP 500 and skips the next question; no interrupted answer is manufactured. Readiness/planning/retrieval/catalogs/provider outputs and counts are authored fixtures; no real store is opened. All **1145** predecessor files, all **172** source files, local settings and original/working stores remain byte-identical. Actual provider/count calls and new execution admissions **0**; shared **6.04443577 / 7**, remaining **0.95556423**, pending 0, not invoice.

The new local template requires an explicit `httpx.MockTransport`, a fresh output path and installation before graph construction. Copied question/scope/flags, graph owner identity and phase-specific model/schema pairs are checked before any count. Question repetition, out-of-order selection, changed phase state, configuration drift, unscoped embeddings and direct transport are denied. Canonical bootstrap and active routing/retrieval embeddings share the existing provider budget. Counts and generations are linked to the same full input/schema and question/phase receipts.

Six paired scenarios execute real graph/Compiler validation/SDK/ASGI and caller persistence with authored planning, retrieval, source catalogs and readiness. Success includes two anonymous questions, ten counted generations and three embeddings. All five later stops preserve the two earlier parsed/validated programs, island/attempt identities and unchanged original terminal response, with no further question or automatic retry. No live startup/store readiness or model quality is asserted. An additional CLI-entry check passes; the initial failure was a missing collection name in the authored readiness fixture, fixed without source/contract changes. **24/24** import/topology/docs checks pass. The unchanged runtime retains its prior **1,940/1,940** full-suite and audit **83** evidence without rerunning them.

The [read-only counted narrative readiness review](counted_narrative_readiness.md) is complete: current official generation rates match the existing cache-write/full-output reservations, and key/project permission requirements are documented. Count-specific tariff and current endpoint/account access remain unverified; USD 0.01 is contingency, not a tariff. Under historical prefix costs and that allowance, the first/second/third Compiler inputs must be at most **48,650 / 33,082 / 16,738** tokens. Nine Decimal/Fraction/real-preflight boundary checks and docs **2/2** pass; fresh token counts and complete-run feasibility remain unknown. All **1209** predecessor files and **172** source files, settings and stores are preserved. Provider/count/authenticated API calls **0**; shared **6.04443577 / 7**, remaining **0.95556423**. This review seam is closed; the mock-only caller supplies no live admission. A live successor needs authoritative count terms/access evidence and a separately bounded execution decision. Repeating the same public search or another mock preparation cannot resolve the missing facts; independent provider-free product work remains available.
