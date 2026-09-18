# Different-source comparison input counts

All four frozen requests were counted successfully by the OpenAI input-token
endpoint. They total **86,728 input tokens**. No answer generation occurred.
The remaining shared allowance is **USD 1.26080341** after retaining **0.04** in
count contingencies. At the same input counts, a fresh counted four-response
comparison needs **2.1481** in full reservations, leaving a **0.88729659** shortfall.
Raising the shared cap from **14 to 15** is proposed, not applied.

## Measured requests

The user continued the concrete count-only step after the
[input preparation](compiler_compact_json_transfer_preparation.md). Work starts
on clean `1663a54a`. The [completed local packet](../../benchmarks/results/compiler_compact_json_transfer_count_2026-09-18_v2/)
retains the exact bodies, fresh manifest, raw count responses, accounting,
rehearsals and the separately preserved local caller failure.

| Case | Baseline input tokens | Candidate input tokens |
| --- | ---: | ---: |
| Cash-flow change | 15,882 | 15,965 |
| Liquidity calculation plus explanation | 27,399 | 27,482 |
| Total | 43,281 | 43,447 |

The unchanged compact-JSON prefix adds **83 input tokens per case**. This measures
input overhead only; output savings, completion behavior and answer accuracy are
unmeasured. Every request exceeds the earlier 12,000-input-token admission ceiling.
Any generation successor must explicitly cover these input sizes while retaining
the 5,120-output ceiling and all frozen source/schema/prompt content.

Four HTTP 200 responses contained `object="response.input_tokens"` and positive
integer totals matching the SDK projection and stored raw response. The
[official token-counting guide](https://developers.openai.com/api/docs/guides/token-counting)
describes counting the model-visible input, including schema and formatting,
before generation. Counts do not establish that a future generation will accept
the schema, complete, or produce a correct financial answer.

## Scope and accounting

The only admitted endpoint was `/v1/responses/input_tokens`, with a fixed four-item
schedule and **zero generation authority**. Complete model/input/reasoning/text
fields, including the strict output schema, were preserved from the frozen SDK
bodies. Count projection omitted only controls absent from that API. Request
hashes, bytes and generation-reference bodies remain unchanged.

The corrected manifest `49fc8888...eb5117cb` was consumed once. Counts ran in the
frozen numeric-baseline, numeric-candidate, mixed-candidate, mixed-baseline order.
Actual provider transmissions were **4**, all successful; generations, embeddings,
Planner/retrieval calls, retries, redirects and resumes were **0**.

| Budget item | USD |
| --- | ---: |
| Shared accounting before this step | 12.69919659 |
| Four retained count contingencies | 0.04 |
| Shared accounting after this step | 12.73919659 |
| Remaining under the unchanged 14 cap | 1.26080341 |
| Generation input reservation at measured counts | 1.0841 |
| Four full output reservations | 1.024 |
| Generation-only reservation | 2.1081 |
| Fresh counted comparison, including four new contingencies | 2.1481 |
| Shortfall for that fresh comparison | 0.88729659 |

These calculations retain the prepared conservative $12.50 input / $50 output
rates per million tokens, reserve every complete output ceiling, and assume no
cache savings. The count allowance is an accounting contingency; the endpoint's
actual tariff and invoice were not observed. Pending reservations are zero.

At unchanged future counts, the combined required cap would be **14.88729659**.
A **15** shared cap would leave **0.11270341** after the full future reservations.
That is a proposed $1 increase; no budget change or generation was performed.
Future counted generation must count again and fund the whole schedule before
dispatch. This count-only manifest cannot authorize generation or be reused.

## Local caller failure and verification

The first local packet's consumed manifest `58b0afb9...5727c4b` stopped before its
HTTP delegate. Its logger accepted an argument named `name`, while dispatch passed
both a positional event name and a keyword arm name. Python raised `TypeError`
before entering the logger or sender; the SDK wrapped this as `APIConnectionError`.
The initial runner set `sent=True` too early, producing a false transmission flag
and a 0.01 allowance in its raw result. The frozen callsite and an isolated
reproduction with the actual callback signature establish **zero transmissions**.

Those original bytes and the consumed marker remain intact. A separate review
records the correction from that pre-transmission 0.01 entry to **0 actual count
allowance**; this does not release any historical provider-failure reserve or claim
knowledge of an invoice. The corrected packet moved the sent marker after the
dispatch log, used a distinct event-name argument, and tested the same recorder
used by live execution. It remained within the user's original four actual counts
and 0.04 cap; no provider request was retried.

Corrected caller checks **11/11** pass, including generation/fifth-call/body-drift
denial, 503, timeout, redirect, invalid counts, diagnostic failures, and pre-send
logging failure accounting. Two fresh-process mock rehearsals produce **18
byte-identical files** with the actual recorder and a fixed mock clock. Mock counts
are labeled authored and never used for financial feasibility. Documentation
checks **4/4** pass.

All **7,848 protected files** (7,737 preceding evidence files plus the initial
111-file caller packet), 174 source-code files, seven runtime owners, 24 original
store files and local settings retain hashes. Only documentation is committed.
Runtime prompts, source data, schemas, output limits and retry policies remain
unchanged. The next bounded action is the proposed full two-case comparison under
a fresh manifest and a proposed shared cap of 15, with new counts and full funding.

The subsequently approved [full comparison](compiler_compact_json_transfer_comparison.md)
raises the shared cap to 15 and completes all four first responses. Its current
shared accounting is 14.10619659/15, remaining 0.89380341. The proposal and
count-only figures above describe this earlier step, not the later settlement.
