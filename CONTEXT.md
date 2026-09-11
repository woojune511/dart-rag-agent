# Current Handoff Context

Last updated: 2026-09-11

## Product and authority

The product is the single-agent `FinancialAgent`.
Working branch: `codex/reviewed-compiler-selection-gate`.
The general correctness audit starts at clean `327002c0`; Git records the implementation history.
Source-local boundaries: `3cbae398`; claim-local narrative grounding: `5962d1f7`. The latest paid diagnosis used that unchanged runtime.

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
- Each compiler attempt declares active outputs and bounded-excerpt coverage. Narrative
  `claims` connect source-copied subjects/text to exact visible quotes; code derives the
  final paragraph/evidence IDs and checks claim-local numbers. Current compiler/executor
  reject flat unattributed text. These checks do not prove semantic entailment/completeness.
- `CompilationEnvelopeV2` binds full catalog content, ordered obligations and query.
  Only declared `depends_on` outputs may become formula inputs. Retry assertion
  projection cannot modify unrelated accepted outputs or introduce foreign evidence.
- Source bundles preserve adjacent values and document context. Actual unique selectable
  unions are bounded by numeric 96 / narrative 32; at most eight islands and one internal
  retry per island. Budget/admission stops propagate without fallback or extra calls.
- XML recovery preserves ampersand text and quoted attributes; explicit header/body
  tables remain data. Both narrative modes can read numeric rows. Non-scalar rows gain
  reading-only evidence without changing existing chunk numeric extraction or spans.
- Standalone peer headings persist; paragraph-to-table context stops at heading changes,
  while captions retain enclosing scope. Nested metadata stays outside exact narrative
  body windows; `local_heading` is a separate parser hint, never subject authority.
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

1. The claim contract is implemented, not a semantic judge. Its
   [socket-blocked counterfactual](benchmarks/results/narrative_claim_grounding_2026-09-11/README.md)
   rejects a metadata-only issuer subject and accepts an authored source-local quote.
   Retagging the old broadened paragraph with its mentioned subsidiary still passes:
   this negative control remains open. No new model answer or semantic score is claimed.
2. The [claim interpretation run](benchmarks/results/narrative_claim_compiler_2026-09-11/RESULTS.md)
   consumed `966a0fa7...759a5`: Pro 10 calls, three internal retries, runtime **3/7**,
   estimated USD **0.212920 / 0.60**, provider/execution exceptions zero; billing unobserved.
   Three source-supported structured readings fail only because text does not repeat
   the separate subject field; one causal abstention is faithful, not runtime complete.
   The known excerpt names the local company/routes but leaves "당사" coreference unresolved.
   Ten saved responses replay with identical prompts/programs/validation/execution, no API.
   Next: align subject representation with final rendering and explicit repair feedback;
   preserve quote/owner/number authority, not a company rule or validator relaxation.
   This authored contrast/known-source diagnosis is not full-agent or generalization evidence.
3. Paid admissions are consumed. The [12-question pilot](benchmarks/results/independent_pilot_compiler_2026-09-10/README.md)
   remains runtime 7/12, reference-scalar 4/9, with three incomplete/unfaithful narratives.
   The [three-narrative comparison](benchmarks/results/narrative_reading_compiler_2026-09-11/RESULTS.md)
   remains runtime 2/3, Codex source-review 1/3 on `ff283a58`, not current-head output.
   Original sources/results/labels remain immutable. Provisional reference adoption is
   not individual human source verification or untouched-source generalization.
4. Prior [row-description](benchmarks/results/narrative_row_description_2026-09-11/README.md),
   [section](benchmarks/results/requested_source_sections_2026-09-11/README.md) and
   [source-local](benchmarks/results/local_heading_scope_2026-09-11/README.md) probes are
   source-exposed contract regressions, not repaired stores or paid response improvements.
5. No automatic paid rerun, fresh ingest, store adoption/mutation, answer-key adjustment,
   tolerance relaxation, or experimental artifact commit.
6. Remaining characterized limits: planner theme omission/semantic faithfulness still
   require independent review; document acquisition ambiguity/pagination, full source
   text bijection, and retired narrative-helper removal need separate bounded work.
   Formula-wide rounding propagation and default-store recovery remain deferred.

Chronology: [implementation history](docs/history/implementation_history.md),
[experiment history](docs/history/experiment_history.md), and Git.
