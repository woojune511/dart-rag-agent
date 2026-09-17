# Counted narrative application experiment

Verified 2026-09-17 on `c7aefc4f`. The single authorized experiment finished with
**local budget interruption and no final answer**. All **24** transmitted OpenAI
requests returned HTTP 200. No Google request, SDK retry, whole-query retry,
provider fallback, fresh ingest or budget increase occurred.

The user explicitly requested an experiment after the
[read-only readiness review](counted_narrative_readiness.md). Fresh manifest
`41749c341258eac16475e7a9a1b8601a06648db22b1b6749014f62d211c6d61f`
was consumed once. Endpoint access was observed through the bounded attempt;
count-specific billing was still unknown. USD 0.01 per count was retained as
experimental contingency, not represented as an actual tariff.

The [local result](../../benchmarks/results/counted_narrative_app_2026-09-17/RESULTS.md)
contains the manifest link, actual HTTP bodies, accounting, and finally-persisted
Compiler diagnostics. Historical response gaps remain unchanged.

## Scope and observed behavior

One fixed question requested NAVER's 2023 report descriptions of the Chuncheon
and Sejong datacenters' environmental activities and Sejong's building certification
status. The normal FastAPI application used a verified disposable copy of the
existing NAVER 2023 store. Original and selected store bytes stayed unchanged.

The frozen allowance remained **USD 0.95556423**, with at most 12 counts,
12 generations and 48 embeddings. Astra retained 5120 output tokens and Terra
8192, including reasoning; input limits remained 300,000 bytes / 200,000 tokens.

Actual transport: **15 embeddings, five input counts, four generations**
(Terra 2 / Astra 2). Count access succeeded for both models. For all four generated
responses, measured input exactly matched returned input usage:

| Request | Counted input | Generation input | Output usage | Full output reserve |
| --- | ---: | ---: | ---: | ---: |
| Routing | 1,229 | 1,229 | 26 | 8,192 |
| Requirements | 16,276 | 16,276 | 1,369 | 8,192 |
| Activities, initial | 13,171 | 13,171 | 1,133 | 5,120 |
| Activities, allowed repair | 14,623 | 14,623 | 1,124 | 5,120 |
| Certification, blocked generation | 11,664 | unavailable | unavailable | 5,120 |

The first activities response parsed but failed
`relationship_interpretation_missing_or_inconsistent` for both outputs. Planner
had placed them in a shared-basis relationship. Their basis declarations differed,
while the current validator requires one identical declaration across that relation.
The permitted repair supplied matching declarations and passed validation for
`ob_001` and `ob_002`. These are **two attempts on one island**, not two completed
islands. Original wire responses match the saved parsed programs and both program
and lowered-input hashes verify.

The certification island's first input count succeeded. Its generation required
**USD 0.40180000**, including the full 5120-token output reserve. Only
**0.38441766** remained, a **0.01738234** shortfall for that next request.
The guard blocked generation before transmission and the app returned HTTP 500.
No certification response, final answer or ledger was reconstructed.

## Accounting and verification

Generation/embedding estimate: **USD 0.52114657**. Five count contingencies:
**0.05000000**. This experiment accounted **0.57114657**, making the shared total
**6.61558234 / 7**, remaining **0.38441766**, pending 0. These are conservative
estimates and allowances, not an invoice or account balance.

Counting reduced the input reservation for these exact bodies. For example,
the first activities request reserved **0.42063750**; the former canonical-byte
plus 1024 rule would reserve **0.92962500** for that same body. This arithmetic
comparison does not establish a cheaper bill, improved model quality or a causal
comparison with the earlier run's different plan.

**20 caller controls and three live-runner controls passed** with blocked external
connections and authored responses. The latter included actual application/store
startup, count/generation serialization and result delivery. The rehearsal's
authored missing answer was only a transport witness. Initial control setup errors
(missing receipt label and incomplete authored request-unit coverage) were corrected
before manifest creation. All **1224** predecessor files, **172** sources, local
settings and original/selected stores were verified unchanged. Previous full
1940-test and audit-83 results remain prior evidence; source did not change.

Next work is provider-free characterization of Planner relationship selection and
shared-basis declaration ownership using these saved traces. Preserve validation
strength and original responses. A successful repair is not proof of complete
question accuracy. The shortfall above is for one pending request, not a guaranteed
completion price; this consumed run must not resume. One successful API sample
also does not establish general provider reliability or resolve count billing.
