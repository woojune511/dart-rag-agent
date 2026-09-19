# Planner table-heading exposure

The Planner now receives located table titles linked to the existing parent
section IDs. This corrects the missing-input boundary observed in the
[cash-flow attempt](scope_cash_flow_result.md), using existing stored metadata.
It adds no provider call and changes no section authority or source store.
The original paid answer remains **incomplete, 0/2 outputs**; model behavior with
the new input has not been sampled.

## Mechanism and boundary

`build_source_section_inventory` keeps the original filing-qualified paths,
section IDs, section capacity and membership fingerprint. Its new
`table_heading_hints` field contains exact stored nearest ancestor TITLE text
and one observed table/context reference for each title, linked to an existing
visible parent section. It reads only already-hydrated table metadata after the
existing report filter. No Chroma opening, new retrieval or ingest is required.

The projection checks table ID/path agreement with metadata, document hash,
context content identity and exact span, TITLE locator and physical attachment.
Malformed, foreign/unattached, body-fragment and unknown-table inputs cannot
supply hints. Existing parent-path text is not repeated. Duplicate located
titles retain one deterministic table example; duplicate payloads are decoded
once per projection.

Visible parent sections take turns contributing a title. This generic ordering
prevents one large section from consuming the entire hint budget. At most **64
hints / 16,384 UTF-8 list bytes** are exposed, with whole stored fragments,
separate fingerprint, visible/observed/omitted counts and a truncation flag.
An omitted parent cannot acquire a selectable location through a hint.

The Planner instruction permits reading this attachment to select an existing
parent ID while preserving the complete requested table, scope and exclusions.
The title/context ID itself is not a section ID, citation or candidate permission.
Same-parent sibling tables still share coarse section membership; identifying
the correct table and amount remains a semantic decision grounded by Compiler
evidence. No title alias, financial keyword branch, inferred selection or
relaxed unresolved-restriction check is added.

## Verification

**15 new anonymous tests** cover exact qualified/Unicode text, attachment and
identity failures, body fragments, metadata conflicts, malformed payloads,
deduplication, deterministic ordering, section diversity, byte/count omission,
omitted parents, unchanged authority, invalid selections and scoped same-call
Planner transport. The initial 14 controls exposed the missing feature before
implementation; the additional body-fragment control tightens the final boundary.
The complete focused set passes **98 tests**. Runtime domain audit passes with
the unchanged **83 reviewed literals**. Import/topology/documentation gates are
recorded separately in the final verification artifact.

The final saved-input replay performs **25 checks** with network connections
blocked. It uses the actual OpenAI SDK transport under mocked HTTP and returns
the unchanged saved Planner response; no expected answer or replacement section
choice is injected. The callback/interception setup and scope-key order were
corrected in this local harness before the recorded final replay, without
provider attempts or production contract changes for those corrections.

| Saved-input observation | Before | After |
| --- | ---: | ---: |
| Selectable source sections | 52 | 52 |
| Membership fingerprint | `521a3750...3165c` | unchanged |
| Attached heading hints visible | 0 | 24 of 85 |
| Hint-list UTF-8 bytes | 0 | 16,070 |
| Serialized Planner request bytes | 54,189 | 72,967 |
| Original cash-flow titles visible | 0 of 2 | 2 of 2 |

Both exact source titles, their original context IDs/locators and their respective
parent IDs reach the SDK request. Source axes, output schema and generation
settings remain identical. Apart from the new inventory field and its reading
instruction, the saved prompt is byte-identical. Original review amounts are
absent. These are local request bytes, not measured provider tokens or savings.

Replaying the old response still leaves both section selections empty, preserves
the same normalized obligations, rejects both with
`unresolved_source_section_request`, produces an empty search filter and blocks
Compiler calls. This verifies the unchanged failure behavior; it is not a new
answer or proof that the model will now choose correctly. The anonymous authored
valid-parent control likewise proves execution linkage, not semantic accuracy.

## Preservation and next step

All **9862 predecessor files**, seven protected runtime owners, **24 original
store files** and local settings retain their hashes. Of 174 tracked sources,
only `financial_source_scope.py`, `financial_graph_planning.py` and
`retrieval_policy.py` change. Original Chroma stores are not opened; source review
reads JSON artifacts. Historic paid responses, criteria and consumption markers
remain unchanged, and no other frozen question is executed.

**New provider calls/cost: 0.** Retained shared accounting is **16.09071086 /
17.73 USD**, remaining **1.63928914**, pending zero; these are estimates, not an
invoice. Next prepare a fresh bounded single-question admission and no-call
rehearsal for this changed build before any provider verification. The consumed
draft cannot be reused, and no paid retry is implied by this correction.

Local artifacts: [focused tests](../../benchmarks/results/planner_table_heading_offline_2026-09-19/focused_final.json),
[final saved-input review](../../benchmarks/results/planner_table_heading_offline_2026-09-19/final_replay/review.json),
[projected inventory](../../benchmarks/results/planner_table_heading_offline_2026-09-19/final_replay/projected_inventory.json),
[mock SDK request](../../benchmarks/results/planner_table_heading_offline_2026-09-19/final_replay/mock_sdk_request.json),
[unchanged-response replay](../../benchmarks/results/planner_table_heading_offline_2026-09-19/final_replay/saved_response_replay.json),
[final verification](../../benchmarks/results/planner_table_heading_offline_2026-09-19/verification.json).
