# Numeric prose quote source boundary

Numeric interpretation quotes now use the selected value's located, exact source
bundle. Previously the model saw `source_bundle_text`, while validation compared
its reply with the separately normalized `source_text` excerpt. An original
leading space or internal tab could therefore cause a false rejection; conversely,
a normalized excerpt could pass despite differing from the visible source.

This is an evidence-surface contract correction in
`financial_source_interpretation.py`, with no question-specific rule, source
rewrite, model call, Planner coercion or period fallback.

## Exact source contract

For a located prose value, both existing bundle coordinates must be integer pairs:
the context interval must match the exact text length, and the nonempty value
interval must fit inside it. The existing bundle builder supplies source identity,
membership and physical partitions. A quote must occur exactly within that selected
prose window and one retained partition. Table identities cannot enter this path.

The binding-local proof keeps the untouched quote, candidate and bundle IDs,
`source_field=source_bundle_text`, the bundle-local `source_span`, its enclosing
`source_bundle_context_span`, and the composed `source_candidate_span`. These are
Python decoded-text offsets in the existing source candidate, not raw XML byte
offsets. Repeated exact occurrences use the first occurrence wholly inside an
allowed partition; this is deterministic location, not semantic disambiguation.

There is no trimming, fuzzy matching, neighboring-window search or fallback to a
normalized excerpt when located bundle metadata is present. Malformed or partial
coordinates fail. Historical rows without either coordinate retain their previous
exact `source_text` contract; another unlocated bundle string grants no authority.
Numbers, source IDs, catalogs, source assertions, owner visibility and raw periods
are unchanged. Existing V2 content/proof fingerprints protect the new resolution.
Source linkage still does not certify subject, metric, status or entailment.

## Provider-free verification

**10 new tests** cover leading/trailing whitespace, tabs and nonbreaking spaces,
both coordinate spaces, partial quotes, foreign/inexact quotations, malformed
coordinates, physical source kinds, old unlocated rows, long bounded windows,
partition-safe repeated occurrences, repeated values, actual lowering/execution,
V2 tampering and independent period rejection. The first eight controls exposed
false quote rejections, acceptance of a normalized quote and incorrect offsets on
the old implementation. All ten now pass, plus **124 related regression tests**.
The domain audit passes with **83 reviewed literals**; **24 import/topology/docs
checks** pass separately. No full benchmark or fresh model evaluation was run.

A blocked-network review of the unchanged sampled dividend program passes
**23 checks**. Its quote equals the actual Compiler-visible bundle, including its
leading space. The new proof points to bundle
`srcb_b83b86e264208a097612`, local quote `[0,114)`, source paragraph `[426,540)` and
original stored node `20240318000844:837:0` at `[578,692)`. Reading the saved graph
JSON confirms the exact original substring; Chroma was not opened.

The replay removes only `source_interpretation_quote_mismatch`.
`candidate_scope_mismatch` and `source_assertion_candidate_not_selected` remain;
the program is still invalid with no accepted direct binding. Its `1,190억원`
assertion remains separate and unchanged. The old `direct_value` status plan is
not rewritten, and source linkage cannot turn a planned amount into payment status.
The [original paid HTTP 500](dividend_policy_result.md), partial claims, consumed
draft and cost remain immutable. No new live answer or Planner choice is claimed.

## Preservation and next step

All **10228 predecessor files**, **24 original store files**, seven protected
runtime owners and local settings retain their hashes. Only one of **174** source
files changes. The history file receives an append-only entry, and local review
artifacts are excluded from the commit.

Provider calls and added cost for that offline change were **zero**. Accounting then was
**17.11707679 / 18.27 USD**, with **1.15292321 remaining**, pending zero.
The [fresh provider-free application admission/rehearsal](dividend_policy_successor_admission.md)
preceded the separately authorized [paid successor](dividend_policy_successor_result.md).
It plans three narratives and validates two partial islands before its caller
blocks the third first request. This narrative run does not exercise the numeric
quote correction live and delivers no final answer. Current accounting is
17.71533922/18.82 USD, remaining 1.10466078, pending zero. Next is provider-free
caller-capacity work; no consumed-draft reuse or unsupported-2024 execution.

Local evidence: [baseline](../../benchmarks/results/numeric_quote_source_boundary_2026-09-19/baseline.json),
[new controls](../../benchmarks/results/numeric_quote_source_boundary_2026-09-19/new_contracts.json),
[regressions](../../benchmarks/results/numeric_quote_source_boundary_2026-09-19/focused_checks.json),
[audit](../../benchmarks/results/numeric_quote_source_boundary_2026-09-19/domain_audit.json),
[23-check review](../../benchmarks/results/numeric_quote_source_boundary_2026-09-19/review.json),
[exact source resolution](../../benchmarks/results/numeric_quote_source_boundary_2026-09-19/quote_resolution.json),
[before](../../benchmarks/results/numeric_quote_source_boundary_2026-09-19/before_validation.json),
[after](../../benchmarks/results/numeric_quote_source_boundary_2026-09-19/after_validation.json),
[handoff](../../benchmarks/results/numeric_quote_source_boundary_2026-09-19/handoff.json).
