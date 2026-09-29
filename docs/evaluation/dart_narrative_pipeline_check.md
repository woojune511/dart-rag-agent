# Real DART narrative pipeline check

Executed 2026-09-18 from clean `74fb36d2`. The actual NAVER 2023 search/display
question returns **HTTP 200 but structured `incomplete`**, with **0/2 completed
outputs** and none of the four required contents delivered. All six provider
requests return 200. The failure occurs in **Planner request quotation and source
scope**, before evidence reaches the Compiler. This is neither a 503 nor evidence
that the current Compiler instruction succeeds or fails.

The [raw run](../../benchmarks/results/dart_narrative_pipeline_2026-09-18/),
[review](../../benchmarks/results/dart_narrative_pipeline_review_2026-09-18/) and
[admission](../../benchmarks/results/dart_narrative_pipeline_admission_2026-09-18/)
are preserved locally. Runtime, model settings, stores and historical results
are unchanged; this handoff commits documentation only.

## Scope and observed result

The user continued the proposed small real-DART retrieval-to-answer check.
One previously frozen search/display question was selected because its earlier
application answer had an unsupported product-expansion paraphrase. The question,
NAVER 2023 filing/section restriction and four source-grounded content criteria
remain unchanged. This is a known-source regression check, not a new holdout.

Fresh single-use manifest
`331b8c2c1a47936587e1bc1d87c6224994678abcfc638f1d39d06b4b3f971d73`
was consumed under a **USD 1.50** cap inside the existing 3.16643496 remainder,
with no budget increase. The normal app/lifespan, ASGI `/api/query`, routing,
Planner and subsequent phases ran against a verified disposable copy of the
existing source-complete store. Historical answers and reviewer criteria were
not read by the running application or injected into model inputs.

The public answer is unchanged:

> 필요한 근거를 충분히 확인하지 못했습니다: 검색·디스플레이 사업 연결·노출 비교, 검색·디스플레이 서비스·상품 개선 비교

| Boundary | Observed evidence |
| --- | --- |
| Store readiness | Ready, non-degraded, 1,872 indexed chunks; required source still present |
| Routing and Planner | Completed Terra responses, valid response schema |
| Planner source restriction | Both outputs have `invalid_source_section_request` |
| Retrieval | 15 query entries return `empty_scope`; zero vector attempts or retrieval embedding calls |
| Evidence exposure | No retrieved/seed documents or candidates; 0/4 criterion witnesses exposed |
| Compiler | Zero requests or repair attempts |
| Public output | HTTP 200, structured `incomplete`, 0/2 outputs, no citations |
| Ledger | Integrity `ok`, which does not make the answer complete |

Under the frozen rubric, semantic judgment remains **not evaluable** because
the relevant source never reaches the evaluated window. Public content coverage
is 0/4, but these are not four measured Compiler interpretation failures.
The generic public message describes insufficient evidence without naming the
underlying Planner contract error; the diagnostic record supplies that distinction.

## Exact failure and local isolation

Mechanical request addressing losslessly splits the question after punctuation,
including the periods in the quoted numbered section path. `request_003` starts:

```
주요 제품 및 서비스'를 기준으로, 서치플랫폼의 검색과 디스플레이를 같은 두 기준으로 비교해 줘.
```

In both output restrictions the model selects `request_003` but emits:

```
'주요 제품 및 서비스'를 기준으로, 서치플랫폼의 검색과 디스플레이를 같은 두 기준으로 비교해 줘.
```

That extra opening **`'`** is absent from the selected request unit and from the
complete question at that location. The selected section ID itself exists in the
52-entry observed inventory and identifies the correct requested report section.
The failure is the invented request excerpt, not a missing section or missing
filing. Code retains the unresolved restriction, yields an empty source scope
and blocks both Compiler owners instead of silently dropping the restriction.

Five provider-free contrasts use the actual raw plan and current section-binding
functions. The untouched plan reproduces both errors. In a separately authored
copy, removing only the additional quote from the two bindings gives exact owned
request spans and matches the original source section. Wrong-unit, unknown-section
and unowned-unit variants remain rejected. All original plan/source bytes remain
unchanged. These contrasts isolate section-link validity; they do not provide a
new model response, automatically repaired plan, full retrieval run or final answer.

The split title and added quote are observed. Whether the fragmentation caused
the model's error is a hypothesis requiring further controlled evidence. The
existing Planner instruction already requires unique contiguous original text;
loosening that validator or stripping model punctuation would hide the error.

## Calls, accounting and checks

| Phase | Model | Counted input = generated input | Output tokens | Full output bound |
| --- | --- | ---: | ---: | ---: |
| Routing | Terra | 1,251 | 79 | 8,192 |
| Requirements | Terra | 15,950 | 1,803 | 8,192 |

Six HTTP calls comprise two embeddings, two exact input counts and two
generations. Count and generation bodies match; complete configured output bounds
are reserved before each generation. Whole-run duration is about 39 seconds.
No SDK/whole-query retry, Compiler repair, extra question, Google call, fallback,
ingest or budget interruption occurs. The manifest remains consumed.

[Official pricing](https://developers.openai.com/api/docs/pricing) was checked on
2026-09-18. Conservative usage accounting is **0.06581751**, plus **0.02** count
contingency, adding **USD 0.08581751**. Shared accounting is **10.91938255 / 14**,
remaining **3.08061745**, pending **0**. Count contingency is not an observed
tariff and these totals are not an invoice. Historical failed-request reserves
remain retained. No additional paid run followed the incomplete answer.

Caller/dispatcher checks **24**, provider/diagnostic checks **45**, section/request
contracts **45** and documentation checks **4** pass: **118** local checks.
Two fresh-process actual-store mock rehearsals captured nine identical SDK requests.
Their authored responses are transport witnesses, not live answer-quality evidence.
An initial test run lacked the fixture's artifact-label environment variable;
its failed receipt is retained, and the later correctly configured tests pass.
The opt-in dispatcher now records existing allowlisted error metadata if a future
HTTP error occurs, without raw error text, credentials or retries. No such live
error occurred here. All **6577 predecessor artifacts**, **174 source files**,
**24 store files** and local settings retain hashes.

## Next boundary

Next characterize the **Planner's section restriction request references** with
anonymous numbered/quoted headings and exact owned excerpts, then design a generic
contract improvement if warranted. Keep model interpretation separate from
deterministic source linkage; do not add company/title exceptions, infer missing
quotes or weaken the current guard. A future paid successor needs fresh bounded
admission and must preserve this incomplete result. The adopted narrative
instruction and earlier synthetic comparisons retain their existing claim limits.
