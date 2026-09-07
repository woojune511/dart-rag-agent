# Current Handoff Context

Last updated: 2026-09-08

## Working source

- Product: single-agent `FinancialAgent`.
- Working branch: `codex/reviewed-compiler-selection-gate`; compiler-gate
  baseline `e9a5be0`. Repair baseline: `5e13bc6`; dependency fix: `af9a07e`.
- Unit/retry, compiler, persistence/API, final-state, periods, source-context, query spellings,
  filing-qualified identity, exact-axis/metric-subject ranking, compact compiler JSON, typed admission stops and declared table units are implemented. Git is the chronology.
- HTTP shape, `FinancialRunResultV1`, store manifest shape and ID/fingerprint hashing stay intact;
  parser `financial_parser_v2_source_context` honors explicit headers; new row/cell IDs may differ. Historical IDs are not rewritten.
- Historical results, datasets, stores, caches, and review packets are immutable.
  New local replay/gate outputs remain ignored and uncommitted.

Authority: [runtime contract](docs/architecture/agent_runtime_contract.md),
[code map](docs/overview/codebase_map.md), and
[project status](docs/overview/project_status.md).
The fast development loop is in [AGENTS.md](AGENTS.md).

## Current runtime

- One unit specification controls normalization, applicability, validation, and
  rendering. Compiler chooses formula/display intent; code infers calculation units.
  Redundant `result_unit` is absent from the schema and ignored in legacy inputs.
  Real scale, sign, currency, display compatibility, and finite-value checks remain.
- Compiler prompt leads with comparison target, input transformations, and formula,
  using generic contrast examples and existing `rationale`, not a new enum.
  Raw signs stay intact; undefined ratios and unresolved meaning remain unanswered.
- Unsupported planner units retain their obligations and block affected islands.
  Compiler-format errors retry the same cohort; candidate replacement uses
  explicit typed ownership, never IDs inferred from diagnostic prose.
- Optional planner text serializations `null`/`none` normalize to blank for
  display unit, display format, and coupling key. Real unsupported unit strings
  remain errors, and blank coupling keys cannot merge independent islands.
- `depends_on` names only other answer obligations. Redundant references to the
  same obligation's evidence requirements are removed during projection; true
  unknown, self, and cross-obligation dependencies keep fail-closed semantics.
- `CompilationEnvelopeV2` binds complete catalog content, ordered obligations,
  and query before executor revalidation. Production has no V1 fallback.
- Source bundles preserve neighboring values and located document-context references. Actual
  unique selectable IDs enforce numeric 96/narrative 32, including every retry.
- Expressions explicitly select or decline a source display and give a reason.
  Source values are primary; differing calculated values are also shown.
  Downstream formulas use calculated values, with separate display provenance.
- Every formula input records its variable and candidate/prior-obligation reference.
  Calculated value/unit, validated owner/requirement metadata and physical/context evidence survive.
  Transitive arithmetic provenance excludes display/compatibility witnesses without widening authority.
  Dependency input summaries use calculated values and resolved periods; source surfaces remain in trace.
- Located cell periods override unbound table hints; ambiguous/unanchored numeric periods
  cannot borrow filing-year scope, even via a narrative witness. Bound formulas may span scope-compatible sources;
  coupling/physical-row contracts remain enforced; assertion coverage has stable owner order.
- Source writes publish payload union then graph atomically and memory last.
  Incomplete stores block queries but allow recovery ingest. Missing sidecars
  reuse stored text/parser metadata without context generation or embedding.
- Graph-source vector rebuilds now take one `StoreManifestV1` authority and
  publish it only after index health succeeds. A failed side-by-side build stays
  manifest-less and can be resumed without making the partial store query-ready.
- Query readiness, execution, and snapshot share one operation lock; DB work,
  ingest, and post-ingest readiness refresh run in workers.
- Explicit phase TypedDicts replace the full-state merge. Numeric execution and
  narrative validation return facts, not final answers. The graph finishes
  `assemble_final → assemble_ledger → END`; `run()` only packages the result.
  TypedDicts describe static shape, not runtime immutability.

## Verification and claim boundary

The verification interpreter is Python 3.13.13. Full discovery, domain audit,
import/topology, pycompile, and diff results are recorded in project status.
Nine synthetic comparison contrasts cover signed/magnitude changes, sign transitions,
and explicit abstentions. Their rehearsals do not establish fresh model accuracy.
Predecessor provider-free replay verified three saved catalog identities and unchanged
input-file hashes:

- T2: explicit source-display copy renders `11.5% (재계산값 11.4%)`.
- T3: original program bytes and physical row/evidence remain unchanged.
- Samsung: restoring its recorded first binding accepts `28,352,769백만원`
  and preserves the existing narrative evidence.

T2 and Samsung are explicitly counterfactual runtime-contract tests. That replay
itself made no compiler/provider/evaluator call and is not a release claim.
Receipt: `benchmarks/results/runtime_contract_provider_free_replay_2026-09-05/replay_final.json`.

The successor replay retains all three cases and T2 operand metadata. Its
deterministic evaluator projection changes operand selection from `0.0` to `1.0`
without changing selected IDs, formula, answer, dataset, or evaluator.

A separate reviewed-fixture corpus adds five distinct real questions outside
that three-question inventory: `KBF_T1_017`, `KBF_T2_018`, `LGE_T1_051`,
`NAV_T2_006`, and `CEL_T1_013`. All 5/5 pass current raw-value normalization,
owner visibility, structured-program validation, `CompilationEnvelopeV2`, and
deterministic execution. The cases cover same-row period comparison,
parenthesized negative values, component subtraction, source-first rounded
display plus multi-evidence narrative, and a thousand-won ratio. Two local
receipts are byte-identical at `fc530335...304f`; provider/compiler/retrieval
and store writes are all zero. These are source-derived reviewed projections,
not exact current candidate IDs or proof that a new compiler will choose them.
Fixture: `tests/fixtures/reviewed_runtime_replay_corpus_v1.json`; ignored receipt:
`benchmarks/results/reviewed_runtime_replay_corpus_2026-09-06/replay_a.json`.

## Provider result, remaining work, and hard stops

The earlier source-consistent release gate remains `3 / 3 PASS`: immutable T3/Samsung
successes plus admission `0f0c0d52...0445` on `58551c7` for `HYU_T2_010`.
T2 selected `87.0만 대`, `78.1만 대`, source display `11.5%`, and the existing
narrative evidence, with labelled recalculation `11.4%`. Both obligations completed,
runtime error 0, ledger `ok`, faithfulness/completeness `1.0 / 1.0`; no source mutation.
That approval is exhausted. Mixed-question `numeric_final_judgement=null` is evaluator N/A.

Comparison `3edbcb94...1558` on `847ebfc`: Flash `3/4`, Pro `4/4` on identical prompts
and `4096/1024` budgets. Only Flash answered the unspecified comparison; Pro abstained.
Pro-only admission `dd8e92f1...42f1` ran once on clean `bd6bd49`: reviewed cases `5/5`.
Six calls, zero internal retries, `74.3s`; estimated USD `0.120409375`, billing unobserved.
All responses ended STOP and parsed; validation ready, execution ok, runtime errors 0.
Socket-blocked replay reproduced every program/output/check/prompt; input hashes match.
Normal dependency bindings passed; retry dependency context was not exercised live.
Result: `benchmarks/results/reviewed_compiler_pro_2026-09-07/result.json`.
Approval exhausted; model defaults unchanged. This is compiler-only, not fresh retrieval evidence.

KB's two-case integration ran once; the five-case gate still needs work:

| Scope | Existing source | Blocker |
| --- | --- | --- |
| KB 2023, two questions | 2,093 OpenAI vectors; fresh full-agent runtime 2/2, errors 0, ledger ok | Count-unit repair: evaluator-only replay 2/2; approval exhausted |
| LG 2023 / NAV 2022+2023 | New v2 stores: 2,655 vectors, integrity/readiness 2/2 | Full-agent runtime 2/2; historical LG FAIL preserved, explicit v2 evaluation replay PASS; judges unmeasured |
| Celltrion 2023 | OpenAI store unchanged: 1,083 vectors, 978 payloads, 41 parents; compatible/non-degraded | `e68bc998...865e` is exhausted and remains runtime 0/1, Pro calls 0. Local repair now exposes both reviewed cells; compact payload 50,130 bytes, same-SDK saved-input reservation plus prior spend USD 0.17478992 / 0.20. Typed budget denial makes no compiler retry. Receipt `000746bc...1047b`; [local review](benchmarks/results/celltrion_visibility_budget_repair_2026-09-08/README.md). Next: provider-free fiscal-column versus row-relative period correction before any new admission; no paid retry. |

Previous LG/NAV paid admission `03f03d99...237e` is exhausted: completion 2/2, errors 0, ledgers ok, but LG numeric-variant FAIL and NAV impact-quality gaps remain historical.
Current no-call projection preserves all 592/547 candidate IDs, raw values, periods and physical provenance. Filing-company matches no longer boost value rank; explicit local subjects and scope conflicts remain enforced. Table context plus column labels resolves mixed units; annotated row units survive, bare currency row categories do not override table units. Corrected effective units change catalog-content fingerprints, not ID/hash algorithms or stored payloads.
Approved v2 build `ac0a3ea7...2c89` and paid admission `2724f2ed...4432` are exhausted. Frozen stores retain 783/1,872 vectors with compatible, non-degraded readiness. The paid LG → NAV run on `90aacc9` (runtime `bb8eba2`) completed 2/2, errors 0, ledgers ok: 8 Gemini + 19 OpenAI requests, one allowed NAV compiler retry, 115.265s, estimated USD 0.19107573 / 0.40 (billing unobserved). LG selected 2,163,234백만원 and precise AMPC 676,874백만원, computing 1,486,360백만원; its original atomic FAIL is immutable. NAV retains same-row annual amounts, 41.4% source display and acquisition-performance evidence. Dependency provenance is repaired; exact saved-program replay preserves both cases' values, IDs and ledger agreement. The explicit LG evaluation successor now separates resolved year, source row/header and filing identity from answer labels, admitting the reviewed summary-plus-note tuple. Socket-blocked replay of both frozen/current LG answers: old contract FAIL, v2 numeric PASS; 16 negative controls reject wrong metadata. Full tests 1,090/1,090; focused evaluation 120/120; provider calls 0, old datasets/stores/results unchanged. Review `6c961c96...1c8e`; [source decision](docs/evaluation/lge_t1_051_calculation_source_review_v2.md). Next LG admission must explicitly select `benchmarks/datasets/reviewed/lge_t1_051_calculation_v2.json`; default profiles remain unchanged. No paid rerun is needed for this correction, and judges remain unmeasured. Celltrion store readiness and the wider gate remain separate. Parser deadline 0 remains diagnostic/build-specific.
Default `data/chroma_dart` is out-of-scope KB 2022 with 52 missing payloads; its manifest alone does not establish readiness. Do not repair it here.
Approved KB copy: `benchmarks/results/reviewed_full_agent_kbf_store_copy_2026-09-07`.
Manifest SHA `58251b09...9239`; preserve its benchmark collection name, not the API default.
Original files and copied sidecars are unchanged; only the copy's local index materialized.
Adoption receipt: `benchmarks/results/reviewed_full_agent_kbf_adoption_2026-09-07/receipt_restart.json`.
Admission `138b5fbc...a028` ran once on `457d776`: T2 → T1, runtime 2/2, ledger ok.
T2 renders 70.28% with negative source inputs; T1 renders 1.83% and +0.10%p.
T1's original false FAIL is preserved; count-unit token boundaries now prevent `2023 명목` → `2023 명`.
6 Gemini + 17 OpenAI embedding calls, no retries; 107.5s, estimated USD 0.10416639.
Result: `benchmarks/results/reviewed_full_agent_kbf_2026-09-07/kb-2023/results.json`.
Exact runtime replay passes 2/2; inputs/store unchanged; judges skipped. Both answers pass evaluator-only replay.
Evaluator-only successor: `benchmarks/results/kbf_count_unit_boundary_replay_2026-09-07/summary.json`.

Google routes forward explicit output/thinking/retry/thought-text controls; installed-SDK tests cover both factories and a single simulated 429 with retries disabled.
Formula-wide rounding-error propagation remains deferred. T3 dataset governance is complete;
runtime/dataset ownership, tolerances, faithfulness, and source-evidence requirements stay separate.

Historical evidence stays in [implementation history](docs/history/implementation_history.md), [experiment history](docs/history/experiment_history.md), and Git.
