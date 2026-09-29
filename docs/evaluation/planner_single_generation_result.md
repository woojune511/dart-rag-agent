# One Planner generation: year, coverage and scope preserved

The user continued the [successful corrected-schema count](planner_corrected_schema_count_result.md)
with one actual Planner generation. A fresh manifest ran once on clean
**`1641781f`**, 2026-09-22, under **USD0.15** within the existing shared balance.
No production code, prompt, model, schema, input/output bound or store changed.

## Observed result

| Observation | Recorded value |
| --- | --- |
| Actual count / generation | **1 / 1**, both **HTTP200** |
| Completed, structurally valid plans | **1 / 1** |
| Sampled period / consolidation scope / combined question | **1/1 / 1/1 / 1/1** |
| Measured input / reported output tokens | **8,417 / 567** |
| Reported reasoning tokens, within output total | **140** |
| SDK retry / question retry / semantic repair | **0 / 0 / 0** |
| Other questions / meanings sampled | **0 / 0**; three questions and five meanings remain |

The frozen synthetic question asks for revenue for the **whole2058 business year**,
using only the **2060 annual report**, with original units and no separate
conversion. It does not request a financial-statement consolidation basis.
The real response preserves these distinctions:

- Raw period: `precision=year`, `reference_year=2058`, `year_offset=0`,
  `coverage=whole_year`, both dates null. The existing typed adapter preserves
  `kind=year`, `year=2058`, `coverage=whole_year` in the operative plan.
- The period references own the original target-year and no-partial-year
  clauses. The output owns all four exact request units; source spans, trailing
  spaces and punctuation remain unchanged.
- Raw and operative `consolidation_scope` are **unknown**. “별도의 환산” was not
  interpreted as separate financial statements. Child inputs remain empty and
  evidence-binding/shared-task constraints retain the same period and scope.
- `display_unit` is empty, with **별도의 환산 없이 원문 단위를 유지** in display format.
  The plan requests one direct revenue value, without a new conversion or date.
- The real production scope builder accepts company/report metadata for **2060**
  and rejects **2058** and **2059**. The model's broader year hints `[2058,2060]`
  do not replace the explicit selected-report filter. No retrieval is executed.

This is assistant review of one previously authored synthetic diagnostic against
criteria frozen before generation. It is not blinded or human gold, and does
not evaluate source availability, selected cells, arithmetic or a final financial
answer. Historical period2/6 and scope6/6 remain separate; no combined improvement
score or general accuracy claim is made.

## Frozen execution and validation

Manifest `fbcf7fd4f85cd0d0a600c8c60e16cfa737935b6f7d7e076b168f6ec635b44bcf`
was consumed before transport. It permits one count then one generation for
`u01`, with **gpt-5.6-terra / low / output8192 / default tier / storefalse**.
The input ceiling remains14000; full modeled funding is **USD0.143304**.
No previous count or consumed admission supplied generation authority.

Canonical count and generation bodies are **42,611 / 42,690 bytes**. They are
identical to the previously frozen corrected bodies; their canonical hashes and
the actual SDK serialization hashes are recorded separately. The same SDK wire
hashes recur in two fresh-process mocks and the actual live call. JSON key order
differs between sorted canonical records and the runtime SDK serialization.

Two healthy mock processes each pass **10 assertions**, with **7 byte-identical
files**. **60 caller/control assertions** cover exact requests, failure stops,
count overflow, unknown usage, incomplete output, malformed fields, history-read
denial, consumption and funding. Wrong period/scope fixtures remain uncorrected
semantic negatives. **55 offline evidence/review assertions** and documentation2
pass. Consumed reentry stops before credentials or transport.

The first mock checker incorrectly equated canonical and SDK wire hashes; its
successfully parsed request and failure record are retained. The first reviewer
compared full request units against clause literals without their trailing
spaces; the corrected check links the original clause span to its unchanged
full unit. Neither correction changes source/model output or permits a retry.

All **14,324 predecessor files**, **177 production sources**, **24 original stores**
and local settings retain hashes. Six documents are committed; the packet
`benchmarks/results/planner_single_generation_2026-09-22` stays ignored.
Prior full2267/2267 and audit83 are not rerun for this source-unchanged experiment.

## Accounting and next work

The generation estimate is **USD0.0278465**; count contingency is **USD0.01**.
Added accounting is **USD0.0378465**, shared **19.80287043 / 20.32**, remaining
**0.51712957**, pending0. No budget increase or invoice is asserted. Reported input
includes8414 cache-write tokens and zero cached tokens. The existing conservative
input rate2.5/output12 per million covers the current short-context cache-write
rate, checked against [official pricing](https://developers.openai.com/api/docs/pricing).

At this handoff, the next step was to prepare **u02/u03/u04** as one fresh batch covering five
period/scope meanings: within-year permission, relative years with mixed
consolidation scopes, and exact point/interval dates. With unchanged14000 input
and8192 output bounds, three count/generation pairs require **USD0.429912** and
fit a proposed **USD0.43** cap inside the remaining balance. This is a funding
assessment only; a new frozen manifest is required. No automatic retry, resume,
old-manifest reuse or additional funding is included.

The [completed remaining-contrast successor](planner_remaining_contrasts_result.md)
now records three counts/generations, period5/5, scope5/5 and combined3/3 under
a fresh USD0.43 admission. This u01 packet and its original accounting remain
unchanged; current shared accounting and next work are in the successor.
