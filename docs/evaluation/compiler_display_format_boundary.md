# Compiler display-format public boundary

The saved mixed candidate's Japanese `display_format` reached **six locations in
the default API calculation traces**, although the answer text was Korean.
Caller projection now excludes the complete internal program/validation records.
The four saved responses retain identical answers, values, periods and citations;
the original Japanese field remains in explicit review/debug records.

## Evidence and scope

The provider-free follow-up starts on clean `d4fab63f`, after the
[different-source comparison](compiler_compact_json_transfer_comparison.md).
The [local replay packet](../../benchmarks/results/compiler_display_format_boundary_2026-09-18/)
preserves all four sampled responses and their authored plans/catalogs. It runs
the actual Compiler validation/lowering, numeric execution, final assembly,
ledger, `FinancialAgent.run()` and in-memory ASGI `/api/query` projection.
Planner/retrieval are frozen inputs; no new model, store or browser run occurred.

Before the fix, the root `resolved_calculation_trace` and its nested copy under
`structured_result` each exposed the Japanese field through:

- `calculation_plan.semantic_program.expressions`
- `calculation_plan.program_validation.valid_expressions`
- `calculation_result.validation.valid_expressions`

Compiler `display_format` is not the deterministic renderer's display authority.
Streamlit source reads the final answer text; browser rendering was not tested.
This is a public metadata boundary defect, not observed wrong-language answer text.

## Bounded correction

`financial_agent_run_projection.project_caller_agent_answer` runs after canonical
final and ledger assembly. For the two public trace copies, it excludes whole
`calculation_plan.semantic_program`, `program_validation`,
`program_validation_history` and `calculation_result.validation` records.
This follows the [review-only contract](../architecture/agent_runtime_contract.md).

Canonical programs, validations, execution outputs, final graph answers and ledger
artifacts remain intact, including their fingerprints. Explicit review retains
full program/validation and ledger records; debug retains original model attempts.
No model text is translated, repaired or recursively filtered. Planner display
intent, source quotations and same-named keys in evidence remain unchanged.
Other calculation-trace fields and the public schema version stay unchanged.
This change addresses the observed program/validation paths, not every diagnostic field.

## Verification

| Check | Result |
| --- | --- |
| Saved responses / executed outputs | 4 / 6, before and after |
| In-memory HTTP responses | 16/16 before; 16/16 after, all four review/debug combinations |
| Mixed candidate field in default API | 6 paths before; 0 after |
| Other API differences | Only the eight specified record removals per response |
| Canonical files | 20/20 byte-identical: program, validation, execution, final graph answer, ledger |
| Explicit review/debug payloads | Identical before/after, including the original language anomaly |
| Final answers / citations | Identical for all four saved responses |

Both numeric responses retain **226,354,918천원** for the 2025-minus-2024 cash-flow
difference. Both mixed responses retain **-3,789억원**, the original periods and
the separate cash-decline and comparison-restatement explanations. The complete
remaining API payloads are equal, preserving source/value/unit/period/quote fields.
This preserves the prior source review; it is not a new semantic-accuracy sample.

Three new caller/HTTP contracts first fail on the old runtime and then pass. They
also preserve original-language evidence with matching field names, Planner intent,
all four opt-in combinations and canonical state. Focused caller/API **25/25** and
execution/ledger/evaluator/portfolio regression **135/135** pass, with zero external
connections. Import/topology/documentation checks **24/24** pass, for **184** passing
checks in total. Runtime domain audit passes with **83 reviewed literals**; syntax
and diff checks pass. The full suite was not run for this bounded projection change.

The local replay harness initially blocked Windows asyncio's loopback socketpair
before its first API request; allowing literal loopback fixed the harness while
external socket, HTTP and SDK requests stayed blocked. The first integrity script
compared an owner metadata object to a hash; reading its `working_sha256` field
corrected that local assertion. Neither event was a provider or runtime failure.

## Preservation and next work

All **8,589 predecessor files**, 24 original store files and local settings retain
hashes. Of 174 tracked source files, only the two caller-projection owners change;
the other 172 remain unchanged. Historical paid results and consumed manifests
are preserved. Experiment artifacts remain local and ignored.

Provider/count/embedding calls and added accounting are **zero**. Shared accounting
remains **USD 14.10619659 / 15**, allowance **0.89380341**, pending zero; estimates
and contingencies are not invoices. Compact-JSON default adoption remains a separate
decision. This fix neither changes its prompt nor establishes broad language,
reliability, unseen-source or end-to-end application accuracy.
