# Prepared Planner period and scope diagnostic

**Executed once:** see the [result](planner_period_scope_probe_result.md). The
preparation record below describes the pre-execution state; its manifest is now
consumed. Period semantics were 2/6 and reporting scope 6/6, with all failures kept.

Preparation baseline **`60ec339f`**, 2026-09-22. The user's continuation requests
the next bounded experiment preparation after the period-instruction and scope
ownership fixes. **No live token count or generation has been performed.**
Questions, semantic criteria and order are frozen in the ignored packet
`benchmarks/results/planner_period_scope_probe_2026-09-22`.

## Frozen scope

All five questions select only the fictitious issuer's 2053 business report.
Each receives one current-runtime Planner first response; routing is fixed numeric,
section/axis inventories are empty, and no source-store client opens.

| Case | Requested period | Requested reporting basis |
| --- | --- | --- |
| n01 | Complete 2051 business year | Unknown; ordinary separate-conversion wording supplies no accounts scope |
| n02 | Any allowed measurement within 2051 | Same unknown scope; shorter periods permitted |
| n03 | Whole year two years before the explicit 2052 anchor | Consolidated, with standalone accounts explicitly excluded |
| n04 | Any allowed measurement within the same relative target year | Standalone, specified in English while excluding consolidated accounts |
| n05 | Point 2050-04-30 and inclusive interval 2049-10-01–2050-09-30 | Consolidated cash balance and separate cumulative revenue, kept distinct |

There are **six requested period/scope meanings in five questions**. Review raw
and normalized operative constraints, original owned request units, and selected
report filters separately. Correct rationales do not repair wrong fields. Exact
dates must keep their point/interval shape; years must not invent fiscal endpoints.
Do not require fixture IDs, exact labels or a fixed output decomposition if the
operative source requirements preserve every requested meaning.

This is an assistant-authored synthetic diagnostic, not hidden holdout or human
gold. The absolute pair contrasts coverage; the relative cases also change scope,
so they do not isolate a coverage effect. There is one current-runtime condition,
not an A/B comparison or an isolated measure of either patch's effect. Historical
[2/6 period acceptance](measurement_coverage_probe_result.md) remains unchanged.
No source availability, actual retrieval, Compiler, arithmetic or full-app result
will be inferred from this Planner-only check.

## Cost and stop conditions

Production settings stay **gpt-5.6-terra / low / 8,192 output tokens**, default tier,
`store=false`, zero SDK retries. Experiment-only admission permits at most **five
counts and five generations**, in exact frozen order, with a **16,000-token input
guard** and 100,000 canonical request-byte limit. The application limit is unchanged.
If the actual server count exceeds the guard, stop before generation without
truncation, an automatic cap increase, fallback, retry or resume.

[Official pricing](https://developers.openai.com/api/docs/pricing) was searched and
fetched on 2026-09-22: short-context Terra input/output are USD 2/12 per million;
cache writes are 2.50. Conservative accounting keeps **2.50/12**, without a cache
discount, plus a **0.01 count contingency per attempt**. The count contingency is
not a verified tariff and no invoice is observed.

| Funding item | USD |
| --- | ---: |
| Per-generation ceiling | 0.138304 |
| Five full generations plus five count contingencies | **0.741520** |
| Run accounting cap | **0.75** |
| Current shared accounting / allowance | **19.54154943 / 20.32** |
| Available / pending | **0.77845057 / 0** |
| Remaining after the full modeled envelope | 0.03693057 |
| Added actual calls / accounting during preparation | **0 / 0** |

Unknown usage, provider/count failure, incomplete responses, invalid plans or body
drift stop subsequent calls. Failed generation reserves and attempted count
contingencies are retained. The caller consumes its newly bound manifest before
transport, permits no restart, and emits 30-second heartbeats. Future authority
must bind this exact manifest and balance; preparation creates no live authority.

## No-call validation and handoff

Two fresh-process rehearsals use the real installed SDK and final execution path
with authored HTTP replies, blocked sockets and synthetic usage at the configured
ceiling. All ten request bodies and all five normalized plans are identical.
Request bodies are 42,788–43,202 canonical UTF-8 bytes; these are not measured
tokens. The first rehearsal assertions compared binary floating-point totals
exactly; the retained receipts show complete mocks, and a Decimal tolerance in the
test assertion resolves the representation difference. Runtime budget code and
the frozen questions/criteria were unchanged.

**57 caller controls** and **119 focused tests** pass. Controls include ordered
body/scope drift, forbidden criteria reads, count overflow, terminal failures,
retained reserves, funding, consumed authority and separate semantic negatives.
Wrong well-formed coverage/scope remains structurally accepted, not semantically
corrected. All five authored plans preserve the selected report in filter
construction; the mixed n05 fixture has neutral shared ranking scope.

All **13,087 predecessors**, **176 production sources**, **24 original stores** and
local settings retain hashes. Unchanged runtime retains its preceding full
**2,225/2,225** and audit **83** without repeating them for this preparation.
Documentation/syntax/diff checks and the final manifest's no-authority stop are
recorded in the packet. Only documentation is committed. The fresh manifest stays
unconsumed; there is no model accuracy result, budget increase or store mutation.

The planned whole-batch execution and separate review are now complete in the
linked result. Preserve the frozen criteria and raw failures; the consumed
manifest cannot authorize another run.
