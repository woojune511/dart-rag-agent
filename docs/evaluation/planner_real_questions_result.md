# Real-question Planner sampling and saved-source replay

On clean **`3ad921f5`**, 2026-09-22, two unchanged real questions received fresh
Planner responses. All four HTTP calls succeeded, but only **1/2 period
interpretations** passed the criteria frozen before sampling. Consolidation
scope passed **2/2**. The cash question's **2023년 말** became **2023 / within_year**,
which permits other measurements within the year. Its free text still says
year-end; the operative constraint does not preserve that boundary.

This follows the [provider-free real-source integration](planner_real_source_integration.md).
Production code, historical plans, saved Compiler choices and sources are unchanged.
The user authorized continuation within the existing balance; no budget was added.

## Fixed requests and observed meanings

The original questions are:

- `2023년 말 연결 재무상태표 기준 NAVER의 현금및현금성자산은 얼마야? 원문 단위로 알려 줘.`
- `NAVER의 2023년 사업보고서에 포함된 별도 현금흐름표에서 2022년 배당금수취 금액은 얼마야? 원문 금액과 단위를 그대로 알려 줘.`

Their original routing and selected NAVER2023 annual filing, receipt20240318000844,
remain fixed. Production helpers project1,872 saved source metadata rows into
the normal bounded Planner inventories: **52 observed sections**, none omitted,
and **zero observed/visible source axes**. Reading the graph/table JSON requires
no store client, retrieval, embedding or ingestion. Old selected IDs, values,
answers and review criteria do not enter the Planner request.

| Question | Frozen intended period | Observed raw and canonical period | Scope | Review |
| --- | --- | --- | --- | --- |
| Cash balance | Point2023-12-31 | year2023, offset0, within_year, null dates | Consolidated | Period fail; scope pass |
| Prior dividends | Whole2022, independent of report2023 | year2022, offset0, whole_year, null dates | Separate | Period and scope pass |

Both raw responses satisfy the strict schema and typed cross-field checks.
Normalization preserves their explicit choices. Each has one direct output,
both original request units, the first unit as period support, empty numeric
display_unit and original-unit display intent. The dividend section binds the
exact complete first request unit to the observed **III. 재무에 관한 사항 /
4. 재무제표** path. Filing filters retain2023 independently of the dividend's2022
measurement and raw year hints. No response, free text or field was repaired.

Assistant review reports **period1/2, scope2/2, combined questions1/2**. The
negative is a model interpretation observation, not an API or schema error.
This known two-question panel is neither blinded evaluation nor human gold.

## Why successful replay is insufficient

The entire new requirements objects replace requirements in separate replay
copies. Original requests, routing,1,581 catalog rows, two selected cells and
saved Compiler programs stay fixed. The real compilation, execution, final
assembly and ledger phases use the existing offline transport for saved choices.
The only old-program model additions are two empty relationship dictionaries.

| Saved selection | Local result | Meaning boundary |
| --- | --- | --- |
| Cash cell at2023-12-31 | 3,576,456,533,329 KRW; ledger ok | A correct saved cell also satisfies the overly broad within-year declaration |
| Separate2022 dividend cell | 468,978,562,474 KRW; ledger ok | Matches the correctly declared year/scope |

Both replays complete, with one mock Compiler invocation each and no retry.
All **50 retrieved/seed document occurrences**, including duplicates, pass the
selected2023 filing filter; changing only that filter to2022 rejects them.
Physical period witnesses and source applicability remain separate from meaning.
There is no fresh Compiler selection, retrieval or full-application run:
**full application = NOT_RUN**. Saved-choice replay2/2 is not semantic success2/2.

Five anonymous source-geometry contrasts demonstrate the permission difference.
The sampled within-year declaration accepts a2023-06-30 point, a first-half
interval and a coarse2023 label; an independently authored exact2023-12-31
declaration rejects all three. Both accept the year-end point and reject2022.
Only the period declaration differs. These are authored generic fixtures, not
observed alternative NAVER cells or a newly observed wrong numeric answer.

The failure belongs to Planner meaning/contract guidance. Source validation
correctly follows the declared broad constraint. Current wire descriptions
require explicitly requested full dates and prohibit deriving dates from a year;
the prompt distinguishes whole-year from within-year but does not explicitly
separate unambiguous calendar-boundary shorthand. This guidance tension is a
supported hypothesis, not a proven sole cause from one sample.

## Admission, checks and accounting

Fresh manifest **`ccb9fba3...1515c6`** was consumed once under **USD0.29**.
At most two fresh counts and two generations were admitted, using unchanged
gpt-5.6-terra, low reasoning,14000 input and8192 output limits, default tier,
store=false and zero SDK/whole-question retries. The full conservative envelope
was **0.286608**. Count/generation body identities and separate SDK wire hashes
match frozen requests and rehearsals; generation bodies are60,778/60,928 bytes.

| Question | Measured input | Output including reasoning | Reasoning subset |
| --- | ---: | ---: | ---: |
| Cash balance | 13,823 | 496 | 142 |
| Prior dividends | 13,865 | 638 | 230 |

Preflight passed **72 controls** and two fresh mock processes with **12 identical
files /15 checks each**; initial counted capture passed14 checks. Post-run
verification passed **87 evidence/accounting checks**, **15 saved-replay checks**,
**41 existing period/source contracts** and **2 documentation tests**. Consumed
reentry stops before credentials/transport. No new tests or runtime edits were
needed; prior full2267/2267 and audit83 were not rerun.

All **14,811 predecessor files**, **177 production sources**, **24 original store
files** and local settings retain hashes. Five documentation files are committed;
`benchmarks/results/planner_real_questions_2026-09-22` remains a local ignored packet.
Conservative generation accounting is **USD0.082828**, using input2.5/output12
per million; current standard pricing was checked in the
[official pricing documentation](https://developers.openai.com/api/docs/pricing).
Adding **0.02** attempted-count contingency gives **0.102828** added accounting.
Shared accounting is **20.02917543 /20.32**, remaining **0.29082457**, pending0.
The count contingency is not a verified tariff or invoice; there was no funding increase.

Next clarify request-grounded calendar boundaries in a provider-free Planner
contract/prompt change, first freezing anonymous contrasts for year-end versus
any point within a year and unresolved fiscal boundaries. Preserve the semantic
negative and avoid query-keyword source filters, invented fiscal dates or
historical response repair. Any later paid sample needs a fresh exact manifest;
no automatic retry/resume, Compiler call, ingestion or added budget is included.
