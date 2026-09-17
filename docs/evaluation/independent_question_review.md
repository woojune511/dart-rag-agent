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

Next: provider-free sizing/feasibility for a fresh narrative-only packet. The last
observed **1.0099** request reservation exceeds the current remainder before any
new planning/embedding costs. A paid successor needs a fresh feasible admission;
no automatic rerun, cap increase, reservation weakening or inferred missing replies.
Repeated scope wording remains separate presentation work.
