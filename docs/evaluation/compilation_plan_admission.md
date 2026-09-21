# Compilation-plan admission

The experimental caller now checks the runtime's complete compilation schedule
**before its first Compiler request**. In the saved three-owner failure, the old
two-response cap now stops before any Compiler count or generation. A separately
configured three-response mock envelope admits all three first requests; its
third count receives an injected 503 and stops without generation or retry.
These are provider-free controls, not a new completed model answer.

## Implementation boundary

`src/ops/compilation_plan_admission.py` provides an explicit context used only
inside a serialized experimental compilation phase. It consumes the existing
`build_semantic_compilation_islands` result after physical bundle discovery.
Dependencies, request relationships and physical bundle groups retain their
existing membership. It does not count raw outputs as independent calls, use
copied diagnostics as authority, or force Planner outputs to merge.

Before compilation it checks:

- The configured first-response limit against valid runtime groups. Already
  invalid islands receive no new permission and retain runtime validation.
- Remaining generation slots and count slots independently, including calls
  already used by routing and planning.
- Full configured input/output ceilings and count contingencies, together with
  existing charges, allowances and reservations. No token ceiling is reduced to
  make a plan fit, and no early approval bypasses normal final-SDK counting.

Each request must match one unused complete group. A repeated owner, subset
repair, foreign group, regrouping or reordered membership fails before counting.
Capacity is rechecked for the remaining groups before each first request. A
terminal provider/admission error keeps its first cause. Snapshot data is a copy
for review, never model input or execution authority.

The new helper is opt-in. Product planning, retrieval, compilation, validation,
answer assembly and default retry policy are unchanged. Question/phase binding,
transport, pre-bootstrap whole-run funding and exclusive execution authority
remain the enclosing caller's responsibility. The local derived caller shares
one explicit first-response setting between its phase gate and full funding
calculation; incompatible generation/count limits fail before bootstrap.
Its transport accepts only mocks and its live entrypoint is disabled. Consumed
callers and historical manifests are unchanged.

## Verification

**14 new tests** cover group membership, actual dependency/physical-bundle
grouping, early capacity rejection, independent count/generation slots, full
funding, policy drift, invalid schedules, first-cause preservation, real SDK
serialization through mocked HTTP, and denied repair/fault paths. The combined
focused/import/topology suite passes **86 tests**, without skips. Two separate
documentation authority checks pass after the handoff update.

| Actual-application replay | Mock HTTP | Compiler generations | Result |
| --- | ---: | ---: | --- |
| Two first-response slots | 20 | 0 | `compilation_first_response_limit` before any Compiler prompt/count |
| Three first-response slots, third count fault | 25 | 2 saved replies | Third first request reaches count once; injected 503 stops generation/retry |

Both replays run real native Chroma/BM25/RRF against verified disposable copies,
with recorded embedding vectors and provider replies preloaded before the same
no-history-read guard. Each performs **14 native queries**. Complete requirements,
candidate catalogs and native query results equal the paid predecessor. The
first **20 / 24 SDK bodies** and recorded responses respectively are identical;
the two Compiler programs and validation records in the second replay are also
identical. There is no authored third answer, fresh plan, live token measurement,
semantic improvement estimate or final answer reconstructed from partial drafts.

**115 saved-evidence checks** pass with external sockets blocked. All **10499
predecessor artifacts**, **174 preexisting source files**, seven protected owners,
**24 original store files** and local settings retain their hashes. One new ops
module is added; no existing product source changes. Only each disposable copy's
SQLite file changes. Experimental scripts/results remain local.

## Budget and next work

Actual provider calls and added cost: **zero**. Shared accounting remains
**17.71533922 / 18.82 USD**, remaining **1.10466078**, pending zero. Mock usage is
not added to that ledger. The [paid failure](dividend_policy_successor_result.md)
retains HTTP 500 and zero delivered outputs.

At unchanged model/token/embedding limits, two routing/Planner responses plus
three first Compiler responses and five counts have a hypothetical full ceiling
of **USD 2.34072608**, rounded to **2.35**. Existing funds do not cover that whole
ceiling; this work neither raises the real budget nor prepares a paid manifest.
A separate [three-slot application packet](dividend_policy_three_slot_admission.md)
is now prepared and verified without provider calls. It needs a separately accepted
USD 1.25 increase and one execution bound to its exact new draft; it is unconsumed
and uses this gate. This earlier mock-only implementation packet stays immutable. Normal planning can still produce more groups than an admitted cap;
the gate now detects that before Compiler expense. Unsupported-2024 remains
unexecuted, and consumed drafts cannot be resumed.

Local evidence: [baseline](../../benchmarks/results/compilation_plan_admission_2026-09-21/baseline.json),
[86-test result](../../benchmarks/results/compilation_plan_admission_2026-09-21/focused_checks.json),
[early-stop replay](../../benchmarks/results/compilation_plan_admission_2026-09-21/replay_two/verification.json),
[third-count fault replay](../../benchmarks/results/compilation_plan_admission_2026-09-21/replay_three/verification.json),
[115-check review](../../benchmarks/results/compilation_plan_admission_2026-09-21/review.json),
[mock-only caller](../../benchmarks/results/compilation_plan_admission_2026-09-21/caller.py).
