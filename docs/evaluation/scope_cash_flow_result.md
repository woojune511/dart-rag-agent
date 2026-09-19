# Single cash-flow application result

The authorized one-question attempt on clean `83035d30` finished with **0/2
requested outputs**. The app returned HTTP 200 with `structured_status=incomplete`;
all **six provider requests succeeded**. The frozen acceptance criteria fail.
This is a Planner source-section binding failure, not an API or budget failure.

The user accepted the prepared **USD 0.73 increase and one attempt**, bringing
the shared cap to **17.73**. Draft
`da4c8ed074ea3953bc6bae715ceeb5687c8dd79c59a9d7cd29905256cf89a78b`
was consumed once. The [admission](scope_cash_flow_admission.md) and unchanged
[review criteria](independent_question_criteria.md) remain the scope boundary.
The dividend and unsupported-2024 questions are still unexecuted.

## Observed failure

The question requests original 2023 operating cash-flow amounts and units from
the consolidated and separate cash-flow statements in NAVER's selected 2023
annual report. The answer supplies neither amount and reports insufficient
evidence for both obligations, `ob_001` and `ob_002`.

Both Planner obligations retain the requested scope, period and source-display
intent: empty `display_unit`, with `원문 금액과 단위 그대로` in `display_format`.
Their complete owned request span is valid. However, both select an empty
`section_ids` array. The model's recorded rationale says the requested cash-flow
headings are not independently represented in the observed section inventory.

The actual Planner request contains all **52 observed sections**, with zero
omitted and `truncated=false`. It includes the parent paths
`III. 재무에 관한 사항 > 2. 연결재무제표` and
`III. 재무에 관한 사항 > 4. 재무제표`, but neither located table heading
`2-4. 연결 현금흐름표` nor `4-4. 현금흐름표`. Both headings are retained in
the stored tables' attached source contexts. This is an exposure gap, not an
inventory truncation or evidence that the underlying source is missing.

The deterministic resolver marks both restrictions
`unresolved_source_section_request`. Seven retrieval trace records retain an
empty source scope and skip search: **zero native Chroma queries, zero retrieved
documents/candidates and zero Compiler provider calls**. Requirement preflight
rejects the two empty compilation islands. The task ledger is internally valid;
that does not make either requested output complete.

The immediate empty-binding-to-empty-scope failure is reproduced from the saved
plan and inventory without a provider. The inventory construction and the model's
rationale identify a source-section inventory/Planner-contract seam for further
work; they do not prove that exposing headings alone will fix future plans.
No contract was weakened and no section selection or answer was inserted.

## Source review, not generated answers

JSON-only inspection of the original source artifacts confirms both reference
values and their fiscal-year contexts remain present and unchanged:

| Scope | Stored reference value | Table / cell |
| --- | --- | --- |
| Consolidated | 2,002,233,273,518원 | Section 2, table 4, `47:0:1` |
| Separate | 1,627,845,864,966원 | Section 4, table 4, `39:0:1` |

Both cells use `제25기`, connected by attached context to 2023-01-01 through
2023-12-31. These are review witnesses, **not outputs from this app execution**.
The complete payload references, locators and original document hash are in the
[failure replay](../../benchmarks/results/scope_cash_flow_execution_2026-09-19/failure_replay.json).
Original Chroma stores were not opened for this review.

## Requests and accounting

There were two embedding requests, two input-count requests and two Terra
generations. All returned HTTP 200. Both generations completed as valid compact
JSON, with no whitespace outside strings. Each server count equals the generation's
reported input usage. There was no Compiler attempt, feedback repair, SDK/query
retry, fallback, Google call, context generation or fresh ingest.

| Generation | Input tokens | Output tokens | Included reasoning tokens |
| --- | ---: | ---: | ---: |
| Routing | 1,230 | 26 | 0 |
| Planning | 13,266 | 945 | 291 |

| Retained accounting | USD |
| --- | ---: |
| Prior accounted | 16.02259344 |
| Accepted shared-cap increase | 0.73 |
| Generation and embedding estimate | 0.04811742 |
| Two count-call contingencies | 0.02 |
| New accounted | **0.06811742** |
| Shared accounted / approved cap | **16.09071086 / 17.73** |
| Remaining, pending zero | **1.63928914** |
| This run's peak with reservations | 0.15508142 |

These retained estimates use the unchanged conservative admission rates, rechecked
against [official pricing](https://developers.openai.com/api/docs/pricing).
The count allowance is a contingency, not a verified endpoint tariff. No invoice
was observed. The unchanged 1.70 per-run cap was respected; the run did not stop
on funding or call limits.

## Verification and next seam

**56 saved-evidence checks** pass, including exact authorization/consumption,
wire identity, usage reconstruction, deterministic binding-failure replay,
empty-scope traces and both source witnesses. Two documentation authority checks
pass. The prior 62 focused controls and three routing-failure rehearsals were
reused by unchanged hashes, not rerun or represented as new live successes.

All **9819 predecessor files**, **174 sources**, seven runtime owners,
**24 original store files** and local settings retain their hashes. The selected
store remains ready, source-complete and non-degraded with 1,872 chunks. Only
the disposable copy's SQLite bytes changed. Tracked changes are documentation.

Next characterize generic exposure of located table headings and their parent
sections, using the saved failure and anonymous positive/negative controls.
The relevant owner is `build_source_section_inventory` in
`src/agent/financial_source_scope.py`, called by `financial_graph_planning.py`.
Preserve request ownership, source identity and rejection of unresolved
restrictions; add no question/title-specific fallback. No paid retry is implied.

This additional same-report question overlaps known topics and is not a blind
holdout. Retrieval/Compiler effectiveness and semantic operand accuracy were
not assessed because those stages received no evidence or provider execution.
The failed answer remains failed; a later correction would need separate evidence.

Local artifacts: [app result](../../benchmarks/results/scope_cash_flow_app_2026-09-19/scope_cash_flow/api_result.json),
[request receipts](../../benchmarks/results/scope_cash_flow_app_2026-09-19/http_receipts.json),
[review](../../benchmarks/results/scope_cash_flow_execution_2026-09-19/live_review.json),
[accounting](../../benchmarks/results/scope_cash_flow_execution_2026-09-19/accounting.json),
[handoff](../../benchmarks/results/scope_cash_flow_execution_2026-09-19/handoff.json).
