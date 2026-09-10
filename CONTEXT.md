# Current Handoff Context

Last updated: 2026-09-11

## Product and authority

The product is the single-agent `FinancialAgent`.
Working branch: `codex/reviewed-compiler-selection-gate`.
The general correctness audit starts at clean `327002c0`; Git records the implementation history.
Source-preservation baseline: `7aa4adf2`; reading/selection: `ff283a58`; row-description authority: `16e4a1eb`. Current successor enforces explicit requested source sections.

Read [AGENTS.md](AGENTS.md), [runtime contract](docs/architecture/agent_runtime_contract.md),
[code map](docs/overview/codebase_map.md), and [project status](docs/overview/project_status.md).
The [general audit](docs/architecture/general_correctness_audit.md) records reproduced
defects, generic regressions, coverage limits, and remaining work.

## Current runtime

- Every intent, including pure narrative, uses the existing requirement planner and
  source-bundle compiler. Intent/format cannot bypass requested-output coverage.
  The planner preserves explicitly requested themes and source hierarchy.
- Query-copied `source_sections` is separate from soft search hints. Parent/input
  restrictions intersect; located paths gate cohorts and validation, including dependency
  evidence. Wrong/unlocated sections cannot spend owner budgets or bypass via context.
- Compiler selects meaning, bindings, formulas and source display. Deterministic code
  owns units, arithmetic, scope/ID authority, exact source assertions and execution.
  No seven-role classifier, cross-encoder, extra judge or benchmark-ID branch was added.
- Each compiler attempt declares active outputs and bounded-excerpt coverage. Original
  query is context, not a request to answer other islands. Narrative instructions preserve
  local subjects/themes and forbid inferring report absence from missing visible evidence.
  These instructions are not deterministic proof of narrative faithfulness/completeness.
- `CompilationEnvelopeV2` binds full catalog content, ordered obligations and query.
  Only declared `depends_on` outputs may become formula inputs. Retry assertion
  projection cannot modify unrelated accepted outputs or introduce foreign evidence.
- Source bundles preserve adjacent values and document context. Actual unique selectable
  unions are bounded by numeric 96 / narrative 32; at most eight islands and one internal
  retry per island. Budget/admission stops propagate without fallback or extra calls.
- XML recovery preserves ampersand text and quoted attributes; explicit header/body
  tables remain data. Both narrative modes can read numeric rows. Non-scalar rows gain
  reading-only evidence without changing existing chunk numeric extraction or spans.
- Narrative selection reads local row/body context with format-neutral positive-match
  tiers and document/section/source/row diversity. Numeric metric isolation, explicit
  scope/subject/unit conflicts, owner quotas and global visibility caps remain intact.
- Optional `row_description_quote` binds exact row-axis text to a physical row and filing.
  Only that quote/report year ground description numbers; ordinary scalar use retains
  its own period checks. Validated description-only IDs are not numeric operands or
  raw-value evidence. No candidate rewrite, role enum, ranking change or extra call.
- One unit contract preserves scale, sign, currency and finite arithmetic.
  Source display is primary; a differing recalculation is labelled separately.
  Downstream formulas consume calculated values, not rounded display values.
- Search, local supplements, seeds and final evidence share the same explicit source
  filter. Empty scoped results stay empty. BM25 filters before candidate cutoff.
  Filing-local chunk numbers cannot collapse distinct or unidentified documents.
- Fixed-year selection priorities were removed. Generic year patterns replace dated
  stopword lists. Routing prompt examples are anonymous declarative data.
- Whole calendar/relative/fiscal labels, including abbreviated years, cannot become
  inferred local subjects. Entity-name substrings and explicit subject authority stay intact.
- Canonical routing caches only complete, finite, correctly dimensioned successful
  batches with known identity. Search-cache values are owned copies, invalidated at
  successful source commits. Persistence failures propagate.
- Atomic source publication is payload union then graph, memory last. Incomplete stores
  block queries but allow ingest recovery using existing vectors/context.
- Query readiness/execution/snapshot share one lock; blocking DB/ingest work runs in
  workers. Public API errors do not interpolate raw provider exception text.
- Explicit phase TypedDicts describe static shape, not runtime immutability.
  `assemble_final → assemble_ledger → END` publishes one answer; ledger status reflects
  partial/incomplete public results rather than calling every aggregate complete.
- HTTP shape, `FinancialRunResultV1`, manifest format and candidate ID/hash algorithms
  are unchanged. Parser prefix preservation affects future parsing only; stored
  catalogs, physical IDs, source stores, datasets and past artifacts are not rewritten.

## Evidence and claim limits

Use Python 3.13 (`.venv/Scripts/python.exe`). Current local validation is recorded in
project status; unit/no-call success is not model accuracy or release acceptance.
Synthetic tests vary names, years, source identities, input order, scope, errors and
mutation, rather than turning reviewed benchmark answers into runtime rules.

The last full-agent four-question run used clean `cf721258` and exhausted admission
`a2bd7bdd...a311`: four attempts, API/runtime errors zero, ledgers 4/4 ok.
It did **not** complete four answers: LG omitted the requested-period local value;
Celltrion omitted one theme and used the wrong requested source scope. Those frozen
results are not retroactively fixed by the current code.
[Full-agent result and limits](benchmarks/results/diagnostic_four_full_agent_2026-09-09/README.md).

The separately approved KB successor store is strict-ready/non-degraded in its recorded
receipt; default `data/chroma_dart` is a different, incomplete KB 2022 store and was
not repaired. [Store receipt](benchmarks/results/kbf_parser_openai_store_2026-09-09/README.md).

[Reviewed-case evidence status](docs/evaluation/reviewed_case_evidence_status.md) separates
historical live runs, counterfactual contract replays, and current catalog compatibility.
Old 3/3 and five-case successes are historical, not a synchronized current-head release.

## Next work and hard stops

1. The 12-question paid predecessor's runtime SHA is
   `5a74ff8dae428d314a329615038c45034229098ab15885c45406eb199c809d7b`.
   That run used `7aa4adf2`; the [pre-run check](benchmarks/results/independent_holdout_preparation_2026-09-10/pre_run_review_v1/README.md)
   and the [12-question compiler pilot](benchmarks/results/independent_pilot_compiler_2026-09-10/README.md)
   bind unchanged runtime bytes. Under the user's task-scoped delegation, admission
   `98956685...fd916` ran once on clean `7c7f079a`: Gemini Pro 21 calls, 3 internal retries,
   no transport errors, estimated USD 0.90074875 / 2.00 without cache discount.
2. Runtime complete is 7/12; exact reference-scalar comparison is 4/9 numeric questions.
   All three narratives have omissions, scope expansion or unsupported absence claims.
   These dimensions are not interchangeable. Same-value summary-table evidence retains
   its own provenance; rounded alternatives are not called arithmetic failures.
   [Adopted references](benchmarks/results/independent_holdout_preparation_2026-09-10/label_adoption_v1/README.md)
   remain provisional, with individual human source verifications 0. Whole-filing catalogs
   and question-authored requirements exclude gold from model inputs; no planner/retrieval,
   store build, full-agent, ledger, release or untouched-source generalization was tested.
3. Period-to-subject inference is repaired with anonymous real-catalog tests; no rank
   weights, owner visibility or source validation were relaxed. Offline projection is
   candidate-visibility evidence only, not a new answer result; see project status.
   The [reading/selection comparison](benchmarks/results/narrative_reading_compiler_2026-09-11/RESULTS.md)
   ran once on clean `ff283a58`, admission `8eae0a6b...65c61`: Pro 7 calls, one internal
   retry, provider/execution errors 0, estimated USD 0.221395 / 0.90. Runtime complete
   is 2/3; Codex source-reviewed semantic completeness is 1/3, not a human/judge score.
   Both overview omissions improve. Korean Air covers both themes; KT&G broadens a
   subsidiary's channels to group-level wording. CJ uses the wrong requested source
   section, omits logistics, and has no final channel output. The visible channel row
   was rejected for its scalar carrier's unresolved period, not absent from the source.
   A socket-blocked replay of three saved responses matches every paid prompt hash and
   final program/validation bytes. The same cohort is retained on retry; no new call.
   The [prior prompt comparison](benchmarks/results/narrative_scope_compiler_2026-09-10/RESULTS.md)
   remains immutable (runtime 2/3, source review 0/3). Current local tests are 1307/1307.
   Description-use authority is now implemented with 15 anonymous regressions; the
   [offline counterfactual](benchmarks/results/narrative_row_description_2026-09-11/README.md)
   is an authored-quote contract check, not new model output. Explicit section authority
   now has 18 anonymous regressions. Its [counterfactual](benchmarks/results/requested_source_sections_2026-09-11/README.md)
   rejects CJ's two foreign-section IDs while retaining the other saved in-section IDs;
   no new planner/compiler output is claimed. Next: source-local subject scope and
   anonymous heading-inheritance repair, not another paid trial of known semantic gaps.
   This admission is consumed; no fresh paid execution is prepared or authorized.
4. No automatic paid rerun, fresh ingest, store adoption/mutation, answer-key adjustment,
   tolerance relaxation, or experimental artifact commit.
5. Remaining characterized limits: planner theme omission/semantic faithfulness still
   require independent review; document acquisition ambiguity/pagination, full source
   text bijection, and retired narrative-helper removal need separate bounded work.
   Formula-wide rounding propagation and default-store recovery remain deferred.

Chronology: [implementation history](docs/history/implementation_history.md),
[experiment history](docs/history/experiment_history.md), and Git.
