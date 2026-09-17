# Missing project costs and narrative period scope

Base `cde5d824`; provider-free review and one-owner correction on 2026-09-18.
The frozen `missing_project_costs` question now produces a source-reviewed
**2/2 authored abstention**, using the corrected production Planner path. The
requested cost collection remains missing, its supported explanation is ready,
public status stays **partial**, and ledger integrity is `ok`. This is not two
completed cost outputs, a sampled answer or live acceptance.

## Source boundary and finding

The selected store contains five nodes in the exact requested filing/section.
Their unchanged projection yields **13** source candidates and **37** catalog
entries. The Planner reads inventories from **1,872** committed metadata rows.
No store client, normal search, embeddings or fresh ingest runs.

The section contains an acquisition contract, research-organization/cost prose,
consolidated/separate research-cost totals and ratios, annual project counts and
an external-section detail reference. It does not expose individual project
costs in these stored nodes. The answer does not divide totals by project counts
or follow the detail reference outside the user's restriction. This is a review
of the stored section, not proof of absence across the original XML, whole report
or every filing. Criteria stay outside runtime inputs; review is known-source,
not blind evaluation.

## Reproduced issue and correction

The authored Planner declares a required, source-defined collection of requested
project costs plus the requested fallback explanation. The cost collection keeps
measurement period 2023; the explanation describes available source contents and
leaves its measurement period blank. Every original request unit remains owned.

Previously `normalize_scope` filled every blank period from the filing year,
including the narrative explanation and its children. In this case that changed
candidate exposure: the research-summary header remained visible, but the count
row did not. The first authored source selection failed because it addressed that
hidden row. A response restricted to visible evidence could abstain, but omitted
the frozen annual-count detail: **one criterion passed, one remained partial**.
Changing only metric hints did not restore the row. A separately labeled internal
period override exposed it and supported both criteria; those historical
diagnostics remain unchanged and are not production Planner successes.

The correction changes only `financial_graph_planning.py`: an unspecified
narrative period stays blank, including children without an explicit parent
period. Explicit narrative periods, inherited explicit parent periods and
explicit child periods remain intact. Numeric filing-year defaults and child
inheritance remain unchanged. Company, filing identity, report year, requested
section restrictions and exact request text remain enforced. No schema, prompt,
ranking, quota, parser, unit or semantic-validation rule changes.

After correction, the actual Planner path needs **no internal override**. Its
three SDK request bodies/authored responses and final public answer equal the
earlier successful internal diagnostic. The Planner SDK input itself is also
unchanged from the pre-correction production rehearsal. Current SDK body sizes
are **49,940 / 28,585 / 65,614 bytes**, not token counts or billed usage.

## Final behavior and negative controls

The current answer explicitly states that individual costs cannot be determined
from the requested section. It retains legal-entity/business/service aggregation,
annual project counts and the reason those aggregates cannot allocate per-project
amounts. Two narrative claims preserve **seven** exact subject/fact support
occurrences across the original cost prose, total row and count row. No numeric
output or allocation formula is created. One Planner and two Compiler responses
pass strict schema plus actual SDK serialization/parsing against mocked HTTP;
there is no validation repair in the successful abstention.

| Authored control on corrected source | Result |
| --- | --- |
| Both outputs declared missing | `incomplete`, no evidence-backed explanation; not accepted as successful abstention. |
| Empty candidate intake | Compiler calls **0**, `incomplete`; source absence is not inferred from a retrieval failure. |
| New unsupported amount | Numeric-grounding errors reject it after the existing single repair; `incomplete`, invented amount absent from answer. |
| Existing total called every project's cost | Address/number checks pass and the wrong statement reaches a `partial` answer; source review rejects the attribution. |
| Absence expanded to all reports/filings | Address checks pass and the wrong statement reaches a `partial` answer; source review rejects the scope expansion. |

All controls retain ledger integrity `ok`; the aggregate task stays `partial`,
never completed. Execution-task completion and ledger integrity are not answer
correctness. Existing source amounts can still be misinterpreted and a negative
claim can overreach its evidence. No keyword guard or stronger semantic-accuracy
claim is added. The authored correct path avoids allocation, but this does not
prove the model will never invent an allocation in a new plan.

## Validation and preservation

**9** new anonymous period contracts, focused **99/99**, full **2029/2029**
(64.442s, no skips), domain audit **83** and docs **4/4** pass. New controls cover
blank/explicit narrative periods, child inheritance/override, source-defined
groups, unchanged numeric defaults and unchanged request/report/section transport.
The six pre-change anonymous characterizations and setup failures are retained;
current receipts are explicitly separate.

One existing source file changes; **172** other source files, **1827** protected
predecessor files, **24** store files and local settings retain hashes. Packet
fixtures, SDK bodies and controls are ignored local artifacts. Provider/count/
embedding calls, paid retries, new admission, ingest and added cost are **0**.
Shared accounting remains **7.38602105 / 8**, remainder **0.61397895**, pending 0,
including historical count contingency rather than invoice. Current input-token
counts, live output usage and complete-run budget fit remain unknown.

Local receipts: [`missing_project_costs_readiness_2026-09-18`](../../benchmarks/results/missing_project_costs_readiness_2026-09-18/RESULTS.md).

## Next bounded work

The [three-question integration regression](frozen_question_integration.md) now
preserves all expected outputs and ledger states on the corrected source. This
case retains its whole public answer and three SDK bodies/responses, with costs
missing and status partial. Next is provider-free API response projection using
these frozen results. Paid search/display remains **0/4** and both other questions
remain live-unexecuted. No provider dispatch, consumed-manifest resume, fresh
ingest or cap increase is scheduled.
