# Current Handoff Context

Last updated: 2026-09-10

## Product and authority

The product is the single-agent `FinancialAgent`.
Working branch: `codex/reviewed-compiler-selection-gate`.
The general correctness audit starts at clean `327002c0`; Git records the implementation history.
Audited runtime and source-preservation fixes are committed at `7aa4adf2`.

Read [AGENTS.md](AGENTS.md), [runtime contract](docs/architecture/agent_runtime_contract.md),
[code map](docs/overview/codebase_map.md), and [project status](docs/overview/project_status.md).
The [general audit](docs/architecture/general_correctness_audit.md) records reproduced
defects, generic regressions, coverage limits, and remaining work.

## Current runtime

- Every intent, including pure narrative, uses the existing requirement planner and
  source-bundle compiler. Intent/format cannot bypass requested-output coverage.
  The planner preserves explicitly requested themes and source hierarchy.
- Compiler selects meaning, bindings, formulas and source display. Deterministic code
  owns units, arithmetic, scope/ID authority, exact source assertions and execution.
  No seven-role classifier, cross-encoder, extra judge or benchmark-ID branch was added.
- `CompilationEnvelopeV2` binds full catalog content, ordered obligations and query.
  Only declared `depends_on` outputs may become formula inputs. Retry assertion
  projection cannot modify unrelated accepted outputs or introduce foreign evidence.
- Source bundles preserve adjacent values and document context. Actual unique selectable
  unions are bounded by numeric 96 / narrative 32; at most eight islands and one internal
  retry per island. Budget/admission stops propagate without fallback or extra calls.
- XML recovery preserves ampersand text and quoted attributes; explicit header/body
  tables remain data. Both narrative modes can read numeric rows. Non-scalar rows gain
  reading-only evidence without changing existing chunk numeric extraction or spans.
- One unit contract preserves scale, sign, currency and finite arithmetic.
  Source display is primary; a differing recalculation is labelled separately.
  Downstream formulas consume calculated values, not rounded display values.
- Search, local supplements, seeds and final evidence share the same explicit source
  filter. Empty scoped results stay empty. BM25 filters before candidate cutoff.
  Filing-local chunk numbers cannot collapse distinct or unidentified documents.
- Fixed-year selection priorities were removed. Generic year patterns replace dated
  stopword lists. Routing prompt examples are anonymous declarative data.
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

The last paid four-question run used clean `cf721258` and exhausted admission
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

1. Source-preservation successor runtime SHA is
   `5a74ff8dae428d314a329615038c45034229098ab15885c45406eb199c809d7b`.
   Runtime code is fixed at `7aa4adf2`; the [pre-run check](benchmarks/results/independent_holdout_preparation_2026-09-10/pre_run_review_v1/README.md)
   binds the final clean checkout and unchanged runtime bytes. This is not provider
   admission: no new manifest or paid approval has been prepared.
2. All 12 holdout questions now have source-grounded answer drafts: 15 numeric source
   values, six calculations, and both themes for three narrative questions. Human label
   confirmation and model runs are both zero. The user approved representative narrative
   channels with explicit business scope; this is not per-answer source verification.
   This is a small company/period holdout, not an unseen-template or population claim.
   The diagnosed XML/row-reading gaps are repaired with anonymous regressions; full
   unittest recheck is 1251/1251. Frozen chunk-to-catalog replay preserves all 44,757 numeric
   records byte-for-byte in JSON content. These source-exposed cases are preservation
   regressions, not an untouched parser/catalog holdout. Final pre-run review found no
   required draft correction: 15 values, six calculations, 27 exact quotes and seven
   table-context lines pass. Label adoption is still pending; no model/store work ran.
3. Any provider run needs a new current-build manifest, transmission scope, cost estimate
   and separate approval. Prior admissions are exhausted; narrative routing changed, so
   prior request/count/cost receipts do not authorize the new path.
4. No automatic paid rerun, fresh ingest, store adoption/mutation, answer-key adjustment,
   tolerance relaxation, or experimental artifact commit.
5. Remaining characterized limits: planner theme omission/semantic faithfulness still
   require independent review; document acquisition ambiguity/pagination, full source
   text bijection, and retired narrative-helper removal need separate bounded work.
   Formula-wide rounding propagation and default-store recovery remain deferred.

Chronology: [implementation history](docs/history/implementation_history.md),
[experiment history](docs/history/experiment_history.md), and Git.
