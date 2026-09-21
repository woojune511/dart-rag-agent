# Structured measurement-period Planner probe preparation

Prepared from clean `d4d4df10` on 2026-09-21. The new
[measurement-period contract](structured_measurement_period.md) has a frozen,
provider-free eight-question probe. **Execution remains unfunded:** the unchanged
USD **1.27** run cap exceeds the remaining **1.05143757** by **0.21856243**.
No funding increase, provider request, live dispatcher or paid authority is added.

## Fixed questions and separate semantic review

The [questions](../../benchmarks/results/structured_period_probe_preparation_2026-09-21/questions.json)
are byte-identical to the preceding eight-question probe. The original criteria
are retained separately, and the
[new criteria](../../benchmarks/results/structured_period_probe_preparation_2026-09-21/review_criteria.json)
extend them to inspect the actual nonnull structured constraint. These known
questions are a schema compatibility diagnostic, not a blinded holdout.

| Pair | Structured meaning to review |
| --- | --- |
| p01 / p02 | No measurement restriction versus the explicitly requested 2037 business year; filing selection remains separate |
| p03 / p04 | Complete inclusive intervals 2036-07-01–2037-06-30 versus 2037-07-01–2038-06-30, with actual cumulative basis |
| p05 / p06 | Previous/current business year under the owned 2037 anchor: resolved 2036 versus 2037 |
| p07 / p08 | Distinct 2035/2036 inputs with forward/reverse reference instructions preserved |

Semantic review must inspect raw and normalized operative scopes, including
children/dependencies. A correct year only in a rationale or free-text label
cannot repair a wrong structured target. Owned references must include the
relevant anchor/endpoints; linkage is not semantic proof. Equivalent supported
representations are allowed, including an anchored relative year or a correctly
resolved year. Authored fixture IDs, wording, output counts and reference-list
ordering are not answer keys. A comparison output may remain unspecified or
unresolved when its separately constrained inputs and reference instruction are
preserved. An unresolved explicit input period is not an executable success.

The existing Terra/low Planner uses the production prompt, schema and ontology,
supplied numeric routing and empty source inventories. No retrieval, Compiler,
embedding, ingest or source-store client is involved. Review criteria and saved
answers cannot be read during planning; authored outputs are preloaded solely
for the HTTP mock. One first response per question is proposed. All failures
remain reported, with no review-driven repair or retry. The prior paid 8/8 review
and original partial app results remain immutable; this packet adds no new
provider sample, numerical correctness or general/full-app accuracy claim.

## Exact requests and offline controls

Two fresh-process installed-SDK rehearsals reproduce all eight captured request
bodies and normalized authored plans. Each sends eight mocked count/generation
pairs with synthetic usage at the configured ceilings. Canonical UTF-8 generation
bodies are **39,853–40,057 bytes**, not measured tokens. Counts preserve every
model-visible input/schema field. Strict wire schemas require the six nonnull
period branches; all eight authored replies satisfy their captured schemas.

**160 assertions across 22 controls pass.** Query/report scope/schema/order or
caller-phase drift prevents transmission; source identity drift and insufficient
funding stop before constructing transport. Repeated/extra questions cannot send
another pair. Count 503 or input overflow prevents generation. Generation 503,
unknown usage, incomplete output, absent/null constraints, foreign request IDs,
invalid/reversed dates and relative-year overflow stop later questions without
retry. Failed/unknown generation usage retains its full reserve. A well-formed
wrong 2099 target remains structurally accepted, requiring separate semantic review.

Existing count/transport/period/Planner contracts **70/70** and documentation
contracts **2/2** pass. The first wrapper blocked Windows asyncio's internal
loopback socket pair; its failed log is preserved. The corrected test-only wrapper
allows literal loopback connections while continuing to deny DNS and external
connections. Successful gates record zero external attempts. Production source
and the strict mock rehearsal boundary are unchanged. The preceding full
**2,165/2,165** runtime gate is not repeated for this documentation-only preparation.

## Budget and execution boundary

The [official OpenAI pricing page](https://developers.openai.com/api/docs/pricing)
was searched and fetched on 2026-09-21. Standard short-context Terra input/output
rates remain USD 2/12 per million tokens, with cache writes at 2.50. Accounting
retains the conservative **2.50/12** rates without a cache discount. The 0.01
count-call contingency is not a verified tariff, and accounting is not an invoice.

| Bound | USD |
| --- | ---: |
| One generation: 20,000 input / 8,192 output | 0.148304 |
| Eight full generations plus eight count contingencies | **1.266432** |
| Rounded run cap | **1.27** |
| Current shared remaining allowance | **1.05143757** |
| Shortfall against the full envelope / rounded cap | **0.21499443 / 0.21856243** |
| Suggested additional allowance, not applied | **0.25** |

All positive mock rehearsals use an explicitly hypothetical funded balance of
1.27; they do not change the real ledger. The real-balance control stops before
transport construction. Question count, 8,192 output limit, low reasoning,
`store=false`, default tier and zero SDK retries stay unchanged. No partial paid
batch is substituted to fit the remaining allowance.

All **11,686 protected predecessor files**, **176 source files**, **24 original
store files** and local settings retain hashes. Added provider calls/accounting
are **0**; shared accounting stays **19.01856243 / 20.07**, pending **0**.
Only documentation is committed; the experiment packet remains ignored.

The [draft manifest](../../benchmarks/results/structured_period_probe_preparation_2026-09-21/draft_manifest.json)
has SHA-256 `726e6f52826cdd80c3ecf980d23be6c6cd3b6a23069d9ffaa627c8ea3f98bb5c`.
It binds inputs, criteria, source/SDK identities, settings and ordered request
hashes. After an explicit funding decision, prepare a fresh single-use admission
and recheck all bindings and whole-batch funding before any provider transport.
Suggested +0.25 would make the shared cap 20.32 and remaining allowance 1.30143757;
neither change has been applied. No consumed manifest can be reused.

Local evidence: [controls](../../benchmarks/results/structured_period_probe_preparation_2026-09-21/controls.json),
[rehearsal A](../../benchmarks/results/structured_period_probe_preparation_2026-09-21/rehearsal_a/verification.json),
[rehearsal B](../../benchmarks/results/structured_period_probe_preparation_2026-09-21/rehearsal_b/verification.json),
[focused tests](../../benchmarks/results/structured_period_probe_preparation_2026-09-21/focused_verified.json),
[budget](../../benchmarks/results/structured_period_probe_preparation_2026-09-21/budget_assessment.json).
