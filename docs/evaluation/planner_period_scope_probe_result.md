# Planner period and scope diagnostic result

Executed once on clean **`c68d7e73`**, 2026-09-22, after the user's continuation.
The [prepared questions and criteria](planner_period_scope_probe.md) were unchanged.
Five first responses completed; **10/10 HTTP requests returned 200**, with no
provider, parsing or requirement errors and no retry. This is a Planner-only
synthetic diagnostic; source retrieval, Compiler and full-app answers were not run.

## Semantic result

| Check | Accepted |
| --- | ---: |
| Requested period meanings | **2/6** |
| Requested consolidated/separate meanings | **6/6** |
| Questions satisfying both period and scope | **1/5** |
| Year/relative-year coverage meanings | **0/4** |
| Exact point and inclusive interval | **2/2** |
| Strict schema and request ownership | **5/5** |
| Selected-report filter construction | **5/5** |
| Raw scope/period preserved through normalization | **6/6** |

| Case | Observed operative period | Frozen-criteria verdict |
| --- | --- | --- |
| n01: complete 2051 business year | Exact 2051-01-01–2051-12-31 interval | Fails: fiscal endpoints were never supplied |
| n02: any allowed measurement within 2051 | Same exact January–December interval | Fails: replaces permission for shorter periods with exact-interval equality |
| n03: whole year two years before 2052 | `unresolved` | Fails: explicit anchor/offset determine 2050 and whole-year coverage |
| n04: any allowed measurement in that relative year | `unresolved` | Fails: known year and partial-period permission are expressible without choosing dates |
| n05: consolidated cash point plus separate cumulative revenue interval | 2050-04-30 point; inclusive 2049-10-01–2050-09-30 interval | Both pass, with distinct targets/scopes and actual cumulative basis |

Ordinary separate-conversion wording stays unknown in n01/n02. The negated
standalone wording in n03 retains consolidated scope, the English instruction in
n04 retains separate scope, and n05 keeps each output's own scope. Shared ranking
scope is unknown/unknown/consolidated/separate/unknown across the five plans.
This checks declaration propagation, not actual reranking or source compatibility.

All relevant period/anchor/coverage request units are linked. Correct prose
rationales do not repair operative fields: n02 describes allowed shorter periods,
while n03/n04 identify 2050, yet their structured constraints remain wrong.
The source filter permits only the selected 2053 report, even where model year
hints include measurement/anchor years; no search or source availability is proven.

## Failure boundary

All ten actual SDK bodies match the prepared hashes. Every request contains the
current year/coverage instructions and reachable year/relative-year schema variants
with required `whole_year`/`within_year` coverage. The intended period structures
validate against those actual schemas in an offline expressibility check; these
authored alternatives are not repaired model results. No review criteria were
included in requests or read during planning.

All six raw scope/period objects reach normalization unchanged. The observed
period errors therefore originate in model field selection, with no lost prompt,
missing schema branch or normalization rewrite in this run. This does not identify
the model's underlying reason for selecting the wrong branch. The added period
instructions did not resolve these four new year-coverage cases.

This is one current-runtime condition with assistant-authored questions and
assistant semantic review, not hidden holdout, human gold or an A/B comparison.
The relative cases change coverage and reporting basis together. The old
[2/6 period result](measurement_coverage_probe_result.md) is a different sample;
neither score establishes an isolated patch effect or general accuracy.

## Accounting and integrity

Manifest **`9dd3ce6b3c29925cfe04722d8fc1afff358e350d6aedc547641937f0506d15a7`**
was consumed before transport. Five counts and five generations completed in
about **62 seconds**, with 30-second heartbeats. Server counts equal observed
generation inputs: **42,409 input / 3,121 output tokens**, including 648 reasoning
tokens in output. Input maximum 8,528 is below the frozen 16,000 guard.

| Accounting item | USD |
| --- | ---: |
| Generation estimate, frozen conservative rates without cache discount | 0.14347450 |
| Five attempted-count contingencies | 0.05 |
| Added accounted amount | **0.19347450** |
| Shared accounted / cap | **19.73502393 / 20.32** |
| Remaining / pending | **0.58497607 / 0** |
| Peak including in-flight reservation | 0.28191450 |
| Run cap / prepared full envelope | 0.75 / 0.741520 |

The [official pricing page](https://developers.openai.com/api/docs/pricing) was
rechecked; frozen conservative input/output accounting remains 2.50/12 per million.
Count contingencies are not a verified tariff, and no invoice was observed.
No additional funding, ingest, fallback, semantic repair or paid retry occurred.

**113 evidence checks** pass separately from the failed semantic criteria.
The consumed entry point rejects reuse before credentials, transport or execution.
All **13,361 predecessor files**, **176 production sources**, **24 original stores**
and local settings retain hashes. The prepared **119 focused tests / 57 controls**
and preceding **2,225 full tests / audit 83** remain prior evidence; unchanged
production was not retested broadly. Current documentation/syntax/diff checks pass.
Only docs are committed; raw requests/responses and reviewed artifacts remain in
ignored packets `planner_period_scope_probe_2026-09-22/live` and
`planner_period_scope_run_2026-09-22`.

The subsequent [uniform period declaration](planner_period_wire.md) implements
the provider-free representation change. Its new wire preserves these original
failures in replay; model accuracy remains unverified on the changed contract.
Next prepare a smaller fresh diagnostic within the remaining allowance.
