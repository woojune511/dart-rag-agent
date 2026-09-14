# Request, reading and execution boundary

Baseline: `d9c36d8d`. Approved implementation uses the existing planner/compiler
calls, preserving source stores, physical IDs, units and public results.

## Independent controls

`tests/fixtures/request_source_semantic_controls.json` was frozen before runtime
edits, SHA-256 `6abc1b5687f435bb18c622488c506d0864e1ae967e47540f4e3045bcbb541dc1`.
Six pairs distinguish wrappers, descendants, periods, heading/body attribution,
consolidation and source/calculated displays, including equal-valued distractors.
These are semantic review controls, not runtime policy or provider-free model
accuracy. Both questions in each pair must be assessed separately in any future
approved provider experiment. Existing benchmark questions are regressions only.

## Source authority

Ranking allocates prompt space. Source conditions decide use of the visible
union. Owners with identical source conditions share that union, even when
their topics differ. Different sections, numeric periods, filings, explicit
unit conflicts and retry exclusions do not share authority. Physical-row
atomicity remains enforced independently. Raw catalogs and request conditions
are never changed by the projection.

Validation of provenance and arithmetic does not certify semantic relevance.
No paid run, fresh ingest or source mutation is part of this implementation.
