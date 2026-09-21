# Uniform Planner period declaration

Provider-free change on **`041c0d1d`**, 2026-09-22. The preceding
[live diagnostic](planner_period_scope_probe_result.md) retained correct scope
choices but failed all four year-coverage meanings despite receiving the clarified
prompt and schema. This changes the Planner generation contract; it does not
repair those responses or establish improved model accuracy.

## One response shape

Generation now uses one object with seven required fields, replacing six period
object alternatives. Unused value fields are explicitly null.

| Field | Meaning |
| --- | --- |
| `precision` | unspecified, year, date, date_interval or unresolved |
| `reference_year` | Named year, or explicit anchor of a relative year |
| `year_offset` | Zero for a named year; signed offset for a relative year |
| `coverage` | whole_year or within_year, only for year precision |
| `start_date` | Requested point date or inclusive interval start |
| `end_date` | Inclusive interval end, only for interval precision |
| `request_unit_ids` | Original output-owned units supporting the declaration |

For example, this authored declaration selects the whole year one year before an
explicit anchor, without calendar endpoints:

```json
{
  "precision": "year",
  "reference_year": 2038,
  "year_offset": -1,
  "coverage": "whole_year",
  "start_date": null,
  "end_date": null,
  "request_unit_ids": ["request_001"]
}
```

The adapter lowers zero-offset years to the existing internal `year` type and
nonzero offsets to `relative_year`. Existing execution adds the declared offset.
Point dates, inclusive intervals and unresolved choices keep their shape; an
equal-endpoint interval remains an interval. The adapter reads no query, source,
rationale, financial vocabulary or historical answer to choose meaning.

All three output kinds and their evidence inputs use the new generation scope.
Internal period types, text, source applicability, request ownership, parent
inheritance and Compiler/execution contracts stay intact. Historical omitted
coverage remains omitted; saved internal objects are not converted to new model
answers. Strict generation excludes the old wire shape.

The [official Structured Outputs contract](https://developers.openai.com/api/docs/guides/structured-outputs#all-fields-must-be-required)
supports required fields with nullable values. The uniform schema validates field
shape; Pydantic cross-field validation separately rejects missing active values,
populated inactive values, noninteger/out-of-range year arithmetic, invalid or
reversed calendar dates and invalid references. Invalid responses fail parsing
before accepted planning; no default coverage, dropped conflicting field, inferred
date, semantic repair or extra call is added. Correct field shape remains separate
from correct interpretation.

## Validation and boundaries

- **13 new contracts** cover absolute/relative coverage, point/interval identity,
  inactive-field conflicts, year bounds, dates, reference ownership, historical
  serialization, child/source-group propagation, Compiler context, source matching
  and actual installed-SDK admission/rejection.
- **132 focused tests** and **43 additional transport/presentation tests** pass;
  full **2,238/2,238**, domain audit **83**, import/topology/docs and syntax/diff
  checks pass. Tests make zero external/provider calls. Initial focused/full
  failures came from old wire fixtures; their explicit mock declarations were
  updated, retaining assertions on unchanged internal results and failure behavior.
- Before capture exactly reproduces all five paid SDK requests. After capture
  projects only the existing raw choices to the new wire, retaining both wrong
  calendar intervals, both unresolved choices and both correct exact-date meanings.
  All five normalized plans and all historical model dumps are identical.
- Only the period declaration schema and its instruction block change in captured
  SDK requests. Other schema fields, query/owned units, inventories, report scope,
  settings and routing remain identical. Each body is **2,265 UTF-8 bytes smaller**
  (40,523–40,937 bytes); no token count or cost reduction was measured.

This is contract and transport evidence with authored responses, not a new model
sample. Historical period **2/6**, scope **6/6**, coverage **0/4** and combined
questions **1/5** remain unchanged. Wrong well-formed choices still remain semantic
negatives. Flattening the schema is an experiment in representation; the model
may still choose the wrong precision or coverage.

All **13,416 predecessor files**, **174 unrelated existing production sources**,
**24 original stores** and local settings retain hashes. Production changes are
limited to the new period-wire owner, Planner generation scope integration and its
declarative instructions. Only source/tests/docs are committed; packet
`benchmarks/results/planner_period_wire_2026-09-22` stays ignored.

Added provider calls and accounting are **0**. Shared accounting remains
**USD 19.73502393 / 20.32**, remaining **0.58497607**, pending zero. Old manifests
remain consumed; no fresh paid authority, ingest or funding increase was created.

Next prepare a smaller new Planner-only diagnostic under the remaining allowance,
with frozen period/scope criteria and a fresh complete-batch admission. Test the
new wire's actual interpretation separately from these no-call contracts; retain
every failure without retrying a consumed batch.
