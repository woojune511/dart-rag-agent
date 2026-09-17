# Source-grounded count-unit contract — 2026-09-17

Base `7d5c6ebe`; provider-free correction of the unit boundary reproduced in
[research count readiness](research_count_readiness.md). The evidence-schema
owner is source interpretation; vocabulary lives in declarative unit policy.
This completes the unit seam, not the frozen question's semantic acceptance.

## Contract

- Located numeric cells with an UNKNOWN unit and no explicit unit may offer
  finite count readings from exact, complete, cell-owned row/column labels.
  The reviewed policy covers generic count labels; runtime has no company,
  question, year or metric-specific branch. Missing, ambiguous, conflicting,
  already known or unsupported explicit units do not receive a replacement.
- These options can rank alongside known-unit sources for the same dimension.
  They do not establish applicability: the candidate stays `unknown_only`,
  owner authority remains separate and the numeric bundle quota stays two.
- Compiler `interpretation.unit_ref` selects an offered reading or null. Its
  generation enum includes only the owner's exposed cells' options. Lowering
  independently requires that the option belongs to the selected cell; a bad
  reference remains an output-local error and preserves valid siblings.
- `SourceInterpretationV1.unit_option_id` records the selection. Validation
  re-derives its complete axis identity and requires owned request references.
  The resulting `unit_resolution` carries the original raw/normalized units,
  exact label and physical source. No scalar, catalog identity, store record,
  query or source bytes are rewritten. Existing interpretations omit an absent
  unit field, preserving their internal projection.
- Validated direct/derived operands use the selected COUNT dimension and unit
  for arithmetic and display. Input traces retain the original raw unit;
  answer slots retain the resolution proof. V2 binds the program, source and
  validation, rejecting later changes. A physical link is not proof that the
  model interpreted the count or year correctly.

## Frozen-source diagnostic

Production catalog reconstruction remains identical: 13 source candidates,
37 catalog entries. Both organization-scope cohort and prompt projections are
unchanged. The explicit `건` owner now exposes the count row within the existing
quota; the original candidates still have UNKNOWN units and unresolved years.

Twenty-four authored selections cover blank/explicit requested units, both
equal-valued count cells, absent/range/short context quotes and null/selected
unit readings. These are diagnostic responses, not sampled model answers.

| Selection | Current result |
| --- | --- |
| No unit option, all 12 cases | Remain invalid; no automatic unit assignment. |
| Selected count unit, no period context, four cases | Unit/rendering errors clear; `candidate_scope_mismatch` remains. |
| Selected count unit, full 2019–2023 context, four cases | `context_period_mismatch`; rejected contextual resolution also retains secondary unit/rendering errors. |
| Selected count unit, exact short 2023 quote, four cases | Both 2023 and 2022 count cells render `21건` and pass current structural validation. This demonstrates the remaining year-attribution gap, not four correct answers. |

## Validation and preservation

- **18** new anonymous contract tests; **128/128** focused tests and full
  **2001/2001** pass without skips. Domain audit: **83** reviewed literals.
  Documentation gates: **4/4** after handoff updates. External connections: 0.
- The first focused receipt retains one incorrect test-fixture assumption:
  changing an unused `company` field did not hide a source. The corrected fixture
  uses a source with an explicit conflicting period. Production rules were not
  weakened. The initial frozen-source harness also assumed a rejected range
  context would still apply its unit proof; final diagnostics preserve that
  rejection and its secondary errors.
- Nine source files change; the other **163/172** source files, **1683** protected
  predecessor files, **24** original/selected store files and local settings
  remain unchanged. Source/test/docs changes and ignored evidence are separate.
- Provider/count/embedding calls, new admission, paid retry, ingest and added
  cost are **0**. Shared accounting stays **USD 7.38602105 / 8**, remainder
  **0.61397895**, pending 0, including prior count contingency, not an invoice.
  Paid search/display remains **0/4**, its preceding offline replay **4/4**;
  this research question and the other frozen question remain unexecuted.

Local receipts and authored diagnostics:
[`source_count_unit_contract_2026-09-17`](../../benchmarks/results/source_count_unit_contract_2026-09-17/RESULTS.md).

## Next bounded work

Provider-free same-column year provenance: connect a selected numeric cell to
the actual year/header source at its own physical column. Preserve equal-value
prior-year controls and source IDs; reject borrowed or clipped context as a
substitute for that linkage. The Compiler retains semantic interpretation.
No fresh paid question is scheduled until this separate gate is addressed.
