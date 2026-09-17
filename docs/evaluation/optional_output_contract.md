# Optional output authority and honest completion

Provider-free correction on 2026-09-17, based on `c3d9a751` and the immutable
[search/display application failure](search_display_app_probe.md). That paid run
remains an empty-answer failure with public acceptance **0/4**. This change fixes
the runtime contract and replays its exact saved response without a provider call.

## Runtime behavior

- Every declared evidence requirement receives its own bounded candidate cohort,
  including optional requirements. Parent/child source restrictions still
  intersect; parent visibility does not grant a child another owner's authority.
  A narrative input with no authorized source exposes an empty selection list.
- Optional means that omission is permitted. A selected optional input must still
  validate, and an invalid optional output is eligible for the existing bounded
  repair. Explicit missing/ambiguous abstentions do not trigger repair merely
  because nothing was produced. Planner field descriptions distinguish requested
  outputs from optional supplements; the runtime does not force optional flags.
- Failed output IDs survive final validation and island pruning as code-owned
  `failed_obligation_ids`. The field is absent from the provider schema and omitted
  from healthy program projections. Deterministic `compiler_output_failed` errors
  and the existing V2 program/validation fingerprint preserve the terminal failure;
  detailed errors stay in attempt diagnostics. Successful repair clears failure
  for the repaired output while preserving accepted siblings.
- A program with no validated outputs cannot be `ready` or `ok`. It produces an
  incomplete result with an explanation. A valid required output can coexist with
  an omitted optional supplement; an invalid selected optional output remains
  material and makes the result partial.

Only three runtime owners change: candidate/schema models, compilation, and
deterministic validation/execution. No domain vocabulary, company branch,
benchmark-specific output requirement or relaxed owner validation is introduced.
The [runtime contract](../architecture/agent_runtime_contract.md) records the seam.

## Verification

| Evidence | Result and scope |
| --- | --- |
| Anonymous optional-output controls | **15/15**, including numeric/narrative inputs, source restrictions, abstention, schema/transport/semantic failure, bounded repair, sibling preservation and V2 tampering |
| Existing narrative rendering plus new controls | **22/22** |
| Full unittest suite | **1983/1983**, no skips or attempted external connections |
| Runtime domain-term audit | **83** reviewed literals, pass |
| Documentation gates | **4/4**, current authority documents remain within their line limits |
| Exact sampled-response replay | **2/2** outputs, **4** original claims, one shared declaration/two member refs, `ready`, public `ok`, ledger `ok`, no repair |
| Preservation | **1616** predecessor files, **24** original/selected store files and local settings unchanged; **169/172** source files unchanged |

The replay supplies the original saved plan, catalog and unmodified sampled
Compiler response to the current compilation and application projection phases.
Its sampled response hash remains
`e1ff11b1dc0be48d2b1e82aebde3e4082f1924e82cee506ea576ba131e30f92d`.
Original optional flags, source readings and provenance remain unchanged; cohorts
increase from two parent owners to six parent/child owners. No authored model
response, new retrieval, fresh Planner or live application request is involved.
The original four claims now reach the public answer verbatim. Assistant review
against the same frozen source criteria passes **4/4 in offline replay**, separate
from the failed paid run. This is neither unseen-source accuracy nor human gold.

Initial failing controls and the first full-suite failure remain in the local
packet. The full-suite failure expected final errors to disappear after rejected
claim attempts; that assertion now requires the persistent failure disposition.
Historical diagnostic assertions and source/owner validation remain intact.

Local evidence: [packet summary](../../benchmarks/results/optional_output_contract_2026-09-17/RESULTS.md),
`full_final.json`, `replay.json`, `public_replay.json`, `review.json` and
`final_integrity.json`. Raw artifacts stay outside Git.

The subsequent [research count readiness review](research_count_readiness.md)
completes the next source check without changing this runtime build; the numeric
unit boundary and same-column year attribution remain separate work.

## Cost and remaining boundary

Provider/count/embedding calls and added cost are **0**. Shared accounting remains
**USD 7.38602105 / 8**, remainder **0.61397895**, pending 0, including the previously
recorded count contingency rather than a verified tariff or invoice. The consumed
search/display admission and its actual failed result are unchanged.

Fresh provider acceptance of the modified schema, new Planner behavior and live
application quality remain unverified. Next bounded work is provider-free
readiness for frozen `research_count_and_scope`: inspect the UNKNOWN-unit count
and same-column year/source scope before deciding on another live question.
No paid rerun, new admission, ingest or budget increase is part of this correction.
