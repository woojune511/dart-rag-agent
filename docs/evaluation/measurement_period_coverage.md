# Explicit annual and within-year measurement coverage

The provider-free implementation on baseline `da30a50e` blocks the two preserved
[partial-year counterexamples](structured_period_downstream.md). A matching year
alone no longer lets a finer source period satisfy an annual request. Historical
plans, sampled provider responses and source catalogs are not rewritten.

This is the historical baseline. The [real-source successor](real_source_period_coverage.md)
adds physically linked column-label/declaration geometry and a bounded annual
interval check; the original evidence and conservative unlinked-interval rule below remain.

## Contract

New Planner `year` and `relative_year` objects require nonnull `coverage` on the
strict wire schema. The model interprets the owned request as `whole_year` for an
annual measurement or `within_year` when a point/shorter measurement inside that
year is allowed. Unknown interpretation uses the existing `unresolved` kind.
The same owned request references cover this interpretation; code does not scan
question text or infer coverage from the selected report. Other period kinds,
original free text, comparison input ownership and exact interval behavior stay
unchanged. Explicit child constraints retain their own coverage.

Historical year objects without coverage still serialize unchanged. Annual source
labels retain their existing annual reading. Located full dates/intervals and
reviewed quarter/month/partial-period markers cannot silently pass those old
constraints or `whole_year`: coverage remains unknown and final numeric validation
blocks them. Marker grammar lives in `MEASUREMENT_PERIOD_POLICY`, not request
routing or metric-specific branches. Source axes remain separate, never joined.

For `within_year`, full date geometry must be unambiguous and all endpoints must
be in the declared target year; source-year matching still applies. Cross-year
intervals conflict. An explicit different source year remains a conflict even
when coverage is unknown. Context year resolution, same-column year projection
and an attempted unknown-field waiver cannot erase the finer original axes.
Coverage is included in the existing V2 execution binding.

No fiscal calendar is inferred. Even a full January–December source interval does
not establish equivalence to an unspecified business-year calendar. Such a source
needs an explicitly requested exact interval or a separately supported calendar
binding; `whole_year` conservatively leaves that relation unresolved. Annual labels
are a granularity reading, not proof of actual fiscal endpoints or semantic truth.
A deliberately wrong, well-formed `within_year` interpretation still permits a
partial source: model semantics require separate evaluation.

## Saved evidence replay

All 37 previous states reuse exact request/normalized plan, retrieved-document
projection, source catalog and authored Compiler program. Current candidate
exposure, Compiler V2, numeric execution, final assembly and ledger run; retrieval
and real stores are not rerun. Sockets are denied. Existing mock transport supplies
the same authored selection on the single allowed validation retry.

| Observation | Current outcome |
| --- | --- |
| Two old yearly answers using partial value 31 | Both incomplete, no numeric output |
| Eighteen previously healthy calculations | Entire calculation results unchanged |
| Exact-interval controls | 131 / 151 retained |
| Forward / reverse comparisons | 20% / -16.666666666666664% retained |
| p06 full-pool fixed relative choice | Now completes at 140 after annual-compatible evidence ranks ahead of unknown partial coverage |
| p01 full-pool fixed older choice | Still outside bounded exposure; remains incomplete |
| Separate visible annual choices | Both remain complete at 140 |

The original 33 expected outcomes now match **32/33**; the remaining p01 fixed-choice
failure is preserved, not relabelled or repaired. Its unrestricted plan can use
the separately selected visible annual source. This does not justify widening
quotas or claim unanswerability. All 37 ledgers are structurally `ok`. The original
paid combined **6/8**, both report-scope failures and prior replay results retain
their original status; these are authored execution controls, not new model scores.

## Validation and retained state

**20 new coverage contracts**, **41 period contracts**, **146 focused tests**, full
**2,196/2,196** and domain audit **83** pass. **150 replay assertions** and **347
independent evidence checks** pass, retaining the separate **32/33** outcome result.
Strict JSON-schema and actual SDK serialization use mocked HTTP;
no fresh provider admission has been tested.

Initial characterization records nine failed assertions for finer periods accepted
as a year. Four new test-fixture shape/serialization errors were corrected without
loosening production contracts. The first full run found one real regression:
foreign-year evidence became unknown before its explicit conflict was checked.
Source-year conflict precedence and a dedicated regression test now preserve it.
A final token-boundary control also keeps nonperiod words such as H1N1 from becoming
half-year markers. Import/topology/documentation **24/24** and syntax/diff gates pass.
All first-attempt receipts remain in the ignored packet.

All **12,337 predecessor files**, **24 original store files**, local settings and
the **172 source files outside four approved owners** retain hashes. Added provider
calls/accounting **0**; shared **USD 19.31603993 / 20.32**, remaining **1.00396007**,
pending **0**. These are experiment allowances/estimates, not an invoice. No fresh
ingest, budget change, paid retry, full-app acceptance or release claim.

The saved real-source inspection is complete in the successor above. Next prepare
an independent Planner coverage probe with exact SDK bodies and whole-batch budget
admission. Do not reuse a consumed manifest or turn authored coverage choices into
a model-quality result.

Local evidence: [final replay](../../benchmarks/results/period_coverage_2026-09-21/verified_replay/replay_review.json),
[37 outcomes](../../benchmarks/results/period_coverage_2026-09-21/verified_replay/replay_summary.json),
[independent checks](../../benchmarks/results/period_coverage_2026-09-21/verified_evidence_review.json),
[coverage tests](../../benchmarks/results/period_coverage_2026-09-21/coverage_release.json),
[focused tests](../../benchmarks/results/period_coverage_2026-09-21/focused_release.json),
[full tests](../../benchmarks/results/period_coverage_2026-09-21/full_release.json).
