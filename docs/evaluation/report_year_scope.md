# Explicit report-year scope correction

On 2026-09-21, the user accepted the provider-free correction proposed after the
[structured Planner probe](structured_period_probe_result.md). The baseline is
`057ea5b7`. This is a generic source-scope execution bug in retrieval, separate
from the interpretation of a requested measurement period.

## Behavior

An explicit valid `report_scope.year` now constrains document metadata even when
Planner year hints include other years or the intent is comparison/trend. The
single change is in `FinancialRetrievalPipelineMixin._build_scope_plan`:
explicit year follows the existing multiple-receipt exception and precedes
inferred-year filtering. Query text, normalized Planner hints and structured
measurement constraints remain unchanged.

For example, a selected 2037 report with measurement inputs 2035/2036 now searches
only report metadata year 2037. It still asks for both measurement years within
that report. More than one distinct selected source receipt continues to control
multi-report selection without a primary-year restriction. One receipt intersects
the explicit year. With no valid caller year, existing hint-based behavior stays
intact, including unrestricted multi-period comparison/trend source years.

The shared filter reaches primary/retry queries, cache identity, local supplements,
seed evidence, final selection and the retrieval trace. Missing-year and foreign
report rows cannot re-enter an empty explicit-year result. No financial vocabulary,
benchmark branch, Planner repair, source-axis change or new model call is added.

## Evidence and limits

All eight exact paid plans, questions and source responses retain their hashes.
Before the fix, production normalization and scope construction reproduce the
original **6/8** filter result. After the fix, the same plans accept only the
selected report in **8/8** authored metadata controls. Only p07/p08 filters change;
all non-filter plan fields, query/plan bytes and measurement constraints match.
**66 replay assertions** pass with external sockets denied and no source store.

The original paid combined result stays **6/8**, and its **106/108** review retains
both failures. This replay checks deterministic filter behavior; it is not real
retrieval, a new model sample, Compiler endpoint selection, arithmetic acceptance,
source availability or an improvement in measured full-app accuracy.

Validation: **11 new regression tests**, **112 focused**, full unittest
**2,176/2,176**, domain audit **83**, import/topology, documentation and syntax/diff
gates pass. Tests vary anonymous report years/intents and preserve multiple-report,
single/duplicate-receipt, unscoped, measurement, empty-result and cached/retry paths.
Two targeted tests fail on the baseline and pass with the correction. Initial new
test-harness errors were corrected to use the actual trace key and production merge;
their failed log remains alongside the passing run.

All **12,216 predecessor files**, **175 unrelated source files**, **24 original
store files** and local settings preserve hashes; the one retrieval owner changes.
The packet `report_year_scope_2026-09-21` remains ignored. Source, tests and docs are
committed separately from experimental artifacts. Added provider calls/accounting
**0**; shared **USD 19.31603993 / 20.32**, remaining **1.00396007**, pending **0**.
These are retained experiment allowances/estimates, not billing or credit purchases.

Next replay the saved structured plans through candidate selection and Compiler
validation with authored source controls. That will check downstream execution,
separately from this filter fix and from any fresh provider evaluation. No ingest,
paid retry, budget increase or consumed-manifest reuse is part of this correction.

Local evidence: [before](../../benchmarks/results/report_year_scope_2026-09-21/before.json),
[after](../../benchmarks/results/report_year_scope_2026-09-21/after.json),
[66 checks](../../benchmarks/results/report_year_scope_2026-09-21/replay_review.json),
[focused tests](../../benchmarks/results/report_year_scope_2026-09-21/focused.json),
[full tests](../../benchmarks/results/report_year_scope_2026-09-21/full.json).
