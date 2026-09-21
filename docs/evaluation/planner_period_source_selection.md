# Saved Planner periods: downstream selection diagnosis

Provider-free characterization on clean `571d87fb` finds two downstream period
defects in the [eight actual Planner plans](planner_period_probe_result.md): an
anchored previous-year request uses its anchor as the target, and complete date
intervals are checked as sets of years. Production source is unchanged. These
defects were reproduced, **not fixed** by that documentation-only change. The
subsequent [structured-period implementation](structured_measurement_period.md)
fixes execution for explicit new constraints and blocks unsupported legacy guesses;
the original diagnosis and paid responses below remain unchanged.

## Evidence and limits

All eight paid normalized plans and original requests are used unchanged.
Thirteen authored structured source cells pass through the production candidate
builder. They cover annual/current/prior values, two exact intervals, a wrong
interval sharing years, a partial interval, a point date, missing period and a
foreign company. These are synthetic source fixtures, not retrieved DART data or
evidence that the fictional 2037 report contains any particular number.

The production document-scope builder retains the same company, annual-report
type and document year 2037 for all eight questions. Source applicability is
checked for twelve output/input owners against all thirteen cells: 156 results.
Twenty-one authored Compiler selections then run through bounded cohorts, V2
reference conversion/validation, deterministic execution, final answer and ledger.
No Planner/Compiler provider, embedding, search or source-store client is opened.

| Saved plan | Source-selection observation |
| --- | --- |
| p01, no measurement period | An older 2035 value can be selected from the chosen 2037 document |
| p02, 2037 business year | The annual 2037 control executes; 2036, foreign-company and unknown-period controls do not produce a number |
| p03, 2036-07-01 through 2037-06-30 | Exact interval remains unknown and fails period validation; annual 2037, 2037 Q1 and a 2037 point-date substitute can each execute |
| p04, 2037-07-01 through 2038-06-30 | Exact interval remains unknown and fails period validation; annual 2037 substitute can execute |
| p05, previous business year anchored to 2037 | Correct 2036 / source-labelled prior values are excluded; wrong 2037 value executes even when the 2036 cell is also supplied |
| p06, current business year anchored to 2037 | Source-labelled current value executes; source-labelled prior value is excluded |
| p07 / p08, reversed comparisons | Child permissions retain 2035/2036 in the requested order; authored reference/target bindings execute 20% and -16.67% from fixture values 100/120 |

The table records specific controls, not an eight-question correctness score.
Actual Compiler choices, retrieval coverage, source availability, fiscal-calendar
meaning and unseen full-application quality remain untested. The previous **8/8
Planner semantic review remains unchanged**; faithful plan wording does not imply
that downstream code enforces that meaning.

## Failure boundaries

`financial_calculation_execution._period_scope_state` first extracts all explicit
four-digit years from the requested free-form period. For p05 this yields 2037
from `2037사업연도의 직전 사업연도`, although the request designates its predecessor.
With both annual cells present, only the 2037 candidate is authorized for the
output. A supplied 2036 choice fails reference conversion; a supplied 2037 choice
passes and returns **140원** instead of using the authored 2036 value **120원**.
This is a request-interpretation/execution contract gap before Compiler selection.

For p03/p04, the requested endpoints become a set of two years. Candidate period
projection retains exact source text but provides a scalar `value_year` only when
one year is identified. An exact cross-year interval therefore has no scalar
period and fails `candidate_scope_mismatch: period`. An annual value, same-year
partial interval or point date supplies a matching scalar year, so endpoints and
measurement duration are not checked. The wrong cross-year interval is also
rejected; this does not establish that the exact interval is supported.

Nonempty basis fields require a source interpretation. The initial 21 selections
omit that proof and correctly encounter separate interpretation failures. A
second, explicit authored-fixture pass adds only request/axis-linked interpretation
proofs; every selected ID, formula, number, request, paid plan and source stays
identical. The interval counterexamples still reach final answers, while exact
intervals retain only the period error. These proofs demonstrate linkage, not
semantic equivalence. All 21 complete diagnostic traces have ledger integrity
`ok`, including semantically wrong or incomplete outputs.

The recorder initially could not serialize `CompilationEnvelopeV2`. Only the
recorder now uses its existing `to_projection`; the failed script/partial files
remain. First-attempt fixture, catalog, plan, scope and matrix bytes are identical.

## Verification and next implementation boundary

**221 evidence assertions** confirm the counterexamples and input preservation.
Existing period/Planner/source-boundary contracts pass **39/39**; documentation
contracts pass **2/2**. Passing these checks confirms this diagnosis, not correct
period selection. No production change warrants a full-suite or domain-audit
rerun; preceding full 2144/2144 and audit 83 remain historical validation only.
All **11,527 predecessor files**, **175 source files**, **24 original store files**
and local settings retain hashes. Artifacts remain ignored.

Next define and implement a structured measurement-period contract. Planner
semantics must distinguish an anchor from the requested business year and retain
full interval endpoints, with ownership of original request units. Code should
validate structure, provenance and comparable period shapes; it must not infer a
target year by scanning a request sentence. Source year, interval and point-date
evidence must remain distinct, with ambiguity explicit. Preserve existing
source-label precedence (for example, a cell's explicit year over its relative
label); changing that rule cannot repair request interpretation.

Begin with anonymous contract fixtures spanning shifted years, anchors, complete
versus partial intervals, date points, missing evidence and input-specific periods.
Keep the free-form request/period text and raw source axes unchanged. Then replay
these exact saved plans and negative selections without provider calls. Resolving
the new contract and its compatibility policy precedes a paid semantic probe;
no question-specific regex, report-year fallback or hidden response repair.

Added provider calls/accounting **0**. Shared accounting stays **USD
19.01856243 / 20.07**, remaining **1.05143757**, pending **0**, not an invoice.
No paid retry, new funding, ingest, store mutation or consumed-manifest reuse.

Local evidence: [review](../../benchmarks/results/planner_period_source_selection_2026-09-21/review.json),
[source matrix](../../benchmarks/results/planner_period_source_selection_2026-09-21/replay/applicability_matrix.json),
[final replay results](../../benchmarks/results/planner_period_source_selection_2026-09-21/grounded_summary.json),
[wrong-year visibility and output](../../benchmarks/results/planner_period_source_selection_2026-09-21/grounded_replay/p05_both_choose_current.json),
[exact-interval rejection](../../benchmarks/results/planner_period_source_selection_2026-09-21/grounded_replay/p03_exact_interval.json).
