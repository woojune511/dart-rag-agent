# Search/display normal-app experiment

Executed 2026-09-17 on clean `73a5b68c`, using the unchanged 172-file source
digest `5366d3d074ca77b4906ed45063bbbc60b3d2de664cad6ed8bfa1f41e4dc735fe`.
The first [frozen new question](new_question_controls.md) **fails end-to-end**:
the public answer is empty and ledger integrity is `error`, despite HTTP 200
and `structured_result.status=ok`. This is a runtime contract failure, not an
OpenAI transport, schema-parsing or budget interruption. No paid retry followed.

## Execution and result

Fresh single-use manifest
`f896a23e4da1ebb70577438f84eb7a73c117ac44b568dc00e3f59db80882ac8a`
was consumed once under the remaining **USD 0.91655740** of the existing USD 8
shared cap. The user authorized this next step with `진행해줘`; no cap increase.
Normal ASGI `/api/query`, Planner, retrieval, Compiler and application services
ran against a verified disposable copy of the selected NAVER 2023 store.
No expected answer, reviewer criterion, authored plan or candidate override
entered runtime inputs. Historical result reads, Google, ingest/context generation,
store writes, SDK retries and whole-query retries remained disabled.

| Observation | Actual result |
| --- | --- |
| OpenAI HTTP requests | 25/25 returned 200: 19 embeddings, 3 counts, 3 generations |
| Generations | Terra routing/planning 2; Astra Compiler 1 |
| Input counts / generation usage | 1251 / 1251; 15952 / 15952; 8078 / 8078 |
| Output tokens | 114 routing; 1828 planning; 2098 compilation |
| Planner | Two narrative outputs, four child requirements; all marked `required=false` |
| First Compiler response | Parsed; both outputs rejected by owner-permission validation |
| Internal repair / whole-query retry | 0 / 0 |
| Public result | Empty answer, zero subtask results, one source citation; status incorrectly `ok` |
| Ledger | Two missing-payload errors; runner stops on its integrity assertion |
| Frozen public-answer criteria | **0/4 pass**, question fails |

All four required source passages reached the actual Compiler prompt in the
complete narrative candidate from `20240318000844:21:0`. The four draft claims
cover the search/display roles and improvements with correct source attribution
on assistant review. Those claims were rejected and never delivered; they are
not accepted answers or a 4/4 application result. Sources are reused and the
criteria are assistant-authored, not human gold or unseen-document accuracy.

## Reproduced failure boundary

The saved candidate payload, exact sampled response lowering and both errors
reproduce unchanged with external network blocked. No source or response was edited.

1. `_semantic_candidate_cohorts` skips child requirements marked optional.
   The two parent owners receive the narrative source, but none of the four
   child requirement owners receives a candidate cohort. The narrative response
   schema still exposes all child support/evidence keys.
2. The model places source `cand_48a6308b60133927a222` under those child keys.
   Lowering rejects `ob_001:req_001` and `ob_002:req_001` with
   `candidate_not_authorized_for_output_input`. The owner guard remains intact;
   source visibility alone does not grant child ownership.
3. Both outputs are also optional. Required-missing IDs are empty, and retry
   targeting derives from missing/ambiguous IDs rather than the transport-error
   owners. The actual and replayed retry target sets are empty.
4. Final revalidation and island pruning discard the failed outputs and transport
   errors, leaving an empty program marked `ready`, then an empty result marked
   `ok`. The ledger catches missing result payload and final answer. Its failed
   assertion ends the caller; the later store-readiness check is not reached.

The Planner did create one `shared_basis` relationship. The sampled Compiler
response supplies one declaration and both member references, and the current
provider schema parses them. However, **zero outputs/declarations/bindings survive
validation**. This is live schema/representation evidence, not a successful
end-to-end shared-basis test or a measured reduction in repairs.

## Accounting and preservation

Usage-based generation/embedding estimate **USD 0.27257845**, plus **0.03000000**
count contingency, totals **0.30257845**. Pending reservations are zero and no
budget request was blocked. Shared accounting is now **7.38602105 / 8**, remaining
**0.61397895**. These are conservative accounting estimates, not an invoice;
the count-specific tariff remains unverified. Full Terra 8192/Astra 5120 output
reservations, pinned rates and all call limits were retained.

Offline caller/transport/actual-store controls pass **23/23** before dispatch.
They include terminal failure and retry-prevention cases, but did not cover this
sampled all-optional plan. Exact failure replay uses **zero** provider calls or
external connections. Documentation checks pass **2/2**. The prior **1968/1968**
runtime suite and domain audit **83** were not rerun; runtime source is unchanged.
All **1514** protected predecessor files, **172** source files, local settings
and **24** original/selected store files retain their hashes.

[Local evidence](../../benchmarks/results/search_display_app_2026-09-17/RESULTS.md)
preserves raw HTTP bodies, diagnostics, the empty API result, exact replay and
cost reconciliation. The consumed admission and failure remain immutable.

Next: correct the optional output/requirement contract in a provider-free change,
starting with this frozen failure and anonymous controls. Align selectable child
evidence with the emitted schema, preserve invalid-output diagnostics and prevent
an empty answer from being reported as success. Do not relax owner authority or
force this question's outputs. Research count/scope and missing per-project costs
stay frozen; no further live question or paid rerun has been scheduled.
