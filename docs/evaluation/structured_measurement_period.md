# Structured measurement-period execution

The [saved-plan diagnosis](planner_period_source_selection.md) exposed a mismatch
between faithful Planner wording and downstream year extraction. The runtime now
uses a typed measurement-period constraint. A relative request separates its
anchor and signed year offset; complete date intervals compare both endpoints
and their shape. Free-form period text and original request units remain intact.

## Contract and compatibility

Every new strict Planner wire scope declares `measurement_period` as one of:

| Kind | Meaning and fields |
| --- | --- |
| `unspecified` | No measurement restriction; report selection supplies none |
| `year` | A year-granularity target, `year`; not an inferred full calendar interval |
| `relative_year` | Explicit `anchor_year` plus signed `year_offset`; code performs only this addition |
| `date` | One full ISO `date` |
| `date_interval` | Full ISO `start_date` and `end_date`, both inclusive |
| `unresolved` | A requested period whose interpretation is not resolved; cannot validate a scalar selection |

Every constrained kind, including unresolved, declares nonempty
`request_unit_ids` owned by the output; inputs use their parent's owned request
units. Unknown/foreign/duplicate IDs, malformed fields, booleans as years, invalid
dates, reversed intervals and year overflow fail validation. Planning, compilation
preflight and final program validation share these structural/ownership checks.
The full original query and scopes remain protected by the V2 execution-content
fingerprint. This linkage does not prove that the model interpreted the request
correctly; a wrong but well-formed year remains a semantic negative control.

Blank children with no independent constraint inherit the explicitly declared
parent period and structure. Explicit child text or a separate child structure
does not borrow the parent's target. Inherited references are copied, not shared
mutable lists. Comparison inputs retain their separate year constraints; an
unresolved composite output does not erase valid child permissions.

New strict OpenAI wire schemas require the nonnull object. Internal historical
models may omit it; absent/null historical fields are omitted on serialization,
not replaced with an inferred structure. Only complete annual labels (calendar
year, optional reviewed year notation, or standalone relative label) keep the old
annual execution contract. Complex historical phrases, date ranges, quarter
expressions and year lists remain unchanged but unresolved. For example the
saved current-year phrase with parentheses also needs an explicit new constraint.
This intentional boundary favors withholding a number over guessing from text;
no historical paid response is migrated or repaired automatically.

Source annual projection and its precedence remain unchanged: explicit cell
years precede relative labels and a filing year alone cannot supply a scalar
period. Date matching reads retained local period/header axes, using reviewed
literal date/range grammar from policy. Full hyphen/dot/slash or Korean dates and
explicit range separators are supported. A year alone, point date, partial range,
different endpoint or reversed/invalid interval cannot satisfy an exact interval.
Separate axes are never joined into an interval. Unknown/ambiguous source shapes
remain unresolved. This is a bounded literal-date contract, not a fiscal-calendar
engine, natural-language date interpreter or inferred equivalence of date formats
that omit endpoints. It adds no source retrieval or model call.

Candidate source bytes, IDs and catalog construction are unchanged. New exact
interval operands retain the source period axis instead of filling their period
from the request's prose; source and request provenance stay distinct. Company,
section, unit, source interpretation, retry and immutable-execution gates remain
active. A period match is not metric, actual-versus-forecast or semantic proof.

## Provider-free evidence

The packet on baseline `5df6e9d6` replays all 21 previous authored Compiler choices
against the exact eight saved paid plans and source catalogs. Legacy complex
periods no longer admit the anchor/annual/partial/point-date counterexamples.
Seven annual/unrestricted/comparison controls retain byte-identical calculation
results. Complex legacy cases remain incomplete, including exact-source choices;
no new structured interpretation is attributed to the old provider response.

A separate authored successor adds only explicit period structures to the eight
original raw plans and uses production Planner normalization. Removing those new
fields reproduces the old normalized requirements exactly. The same 21 Compiler
choices, source IDs, values, formulas and catalogs then show:

- Prior-year 2036/source-labelled prior values execute as 120; the 2037 anchor
  value is rejected, including when both cells are visible.
- Exact cross-year intervals execute as 131 and 151. Annual, partial-interval,
  point-date and wrong-endpoint alternatives cannot supply those outputs.
- Unrestricted and explicit annual controls still work; comparison inputs retain
  their order and execute authored 100/120 bindings as 20% and -16.67%.
- Unknown-period and foreign-company controls remain blocked. All 42 replay
  ledgers have integrity `ok`; 264 assertions verify evidence and these outcomes.

These are authored semantic choices and synthetic source cells, not new Planner
or Compiler samples, real DART source availability, general accuracy or paid
full-application acceptance. The prior paid Planner 8/8 interpretation result and
all earlier partial application results remain unchanged.

Validation: **21 new tests**, **93 focused**, full unittest **2,165/2,165**, domain
audit **83**, import/topology contracts, documentation and syntax/diff checks pass.
Actual installed-SDK serialization covers all six period shapes with blocked
sockets. The first full pass found outdated strict-wire fixtures, a legacy
serialization mismatch and a malformed child input exception; these were fixed
without weakening the new wire or the existing source/ownership checks. Its log
is retained alongside the successful full pass.

All **11,599 predecessor files**, **24 original store files** and local settings
retain hashes; unrelated source files are checked against the baseline. No store
client opens for the replay. Added provider calls/accounting **0**; shared
**USD 19.01856243 / 20.07**, remaining **1.05143757**, pending **0**, not an invoice.
Experiment files stay ignored. No ingest, paid retry or consumed-manifest reuse.

The [new-schema probe preparation](structured_period_probe_preparation.md) now
freezes eight exact SDK requests and separate semantic criteria. Offline gates
pass, but the unchanged USD 1.27 run cap exceeds remaining allowance by 0.21856243;
resolve funding before fresh single-use admission. No added calls or budget.
Local schema/replay success is not provider acceptance.

Local evidence: [replay checks](../../benchmarks/results/structured_measurement_period_2026-09-21/replay_review.json),
[42 outcomes](../../benchmarks/results/structured_measurement_period_2026-09-21/replay_summary.json),
[full tests](../../benchmarks/results/structured_measurement_period_2026-09-21/full.json).
