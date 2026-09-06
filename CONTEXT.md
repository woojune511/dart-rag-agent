# Current Handoff Context

Last updated: 2026-09-07

## Working source

- Product: single-agent `FinancialAgent`.
- Working branch: `codex/reviewed-compiler-selection-gate`; compiler-gate
  baseline `e9a5be0`. Repair baseline: `5e13bc6`; dependency fix: `af9a07e`.
- Unit/retry, compiler, persistence/API, and final-state ownership repairs are
  implemented as separate changes. Git is the commit chronology.
- HTTP shape, `FinancialRunResultV1`, candidate identity/catalog fingerprint
  inputs, parser table identity, and storage formats remain unchanged.
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
- Source bundles preserve neighboring values in shared bounded windows. Actual
  unique selectable IDs enforce numeric 96/narrative 32, including every retry.
- Expressions explicitly select or decline a source display and give a reason.
  Source values are primary; differing calculated values are also shown.
  Downstream formulas use calculated values, with separate display provenance.
- Formula-input execution rows keep the validated evidence-requirement role,
  label, period, and year. A requirement-supplied period is marked as such and
  does not masquerade as source period text; the same row reaches evaluator
  projection unchanged.
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
Provider-free replay verifies all three saved catalog identities and unchanged
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

Exact saved-trace replay: `9/9` (`6 ready/ok`, `3 partial/partial`), 3 questions,
2 old schemas skipped; reversed receipts match (`9901c8fc...e9180`), without new
compiler/provider evidence. Receipt: `benchmarks/results/exact_saved_runtime_trace_replay_2026-09-06/replay_final.json`.

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

KB's two-case integration admission is prepared; the five-case gate still needs work:

| Scope | Existing source | Blocker |
| --- | --- | --- |
| KB 2023, two questions | Approved copy: 2,093 OpenAI vectors, manifest/source checks pass, stored-vector probes 3/3 | Admission prepared; paid approval pending |
| LG / NAV 2023 | Reviewed sources and payload coverage present | Manifest missing; legacy Google vectors are not canonical OpenAI vectors |
| Celltrion 2023 | Original filing HTML present | No vector store found in the checkout |

Default `data/chroma_dart` instead contains KB 2022 and has 52 missing table payloads;
its compatible manifest alone does not establish readiness. Do not repair it for this gate.
Approved KB copy: `benchmarks/results/reviewed_full_agent_kbf_store_copy_2026-09-07`.
Manifest SHA `58251b09...9239`; preserve its benchmark collection name, not the API default.
Original files and copied sidecars are unchanged; only the copy's local index materialized.
Stored-vector self-search passed 3/3 after restart; no new-query/full-agent/API claim.
Adoption receipt: `benchmarks/results/reviewed_full_agent_kbf_adoption_2026-09-07/receipt_restart.json`.
Admission: `benchmarks/results/reviewed_full_agent_kbf_admission_2026-09-07/manifest.json`
(`138b5fbc...a028`): dataset order T2 → T1, Pro compiler/evidence, Flash elsewhere,
OpenAI query/canonical routing embeddings; estimate USD 0.10–0.25, requested cap 0.40.
Two no-call receipts match (`151039e7...5cc2`); 7 admission + 51 focused tests pass.
Next: separate approval, then one store-fixed run with 30s heartbeat. No paid judges,
fresh ingest, filing embedding or automatic rerun; other cases remain pending.

Production Google phase routes now forward explicit output/thinking/retry/thought-text controls;
missing settings retain defaults. Real installed SDK request tests verify both production and
compiler-only factories; zero SDK retries stop after one simulated 429 attempt.
Formula-wide rounding-error propagation remains deferred. T3 dataset governance is complete;
runtime/dataset ownership, tolerances, faithfulness, and source-evidence requirements stay separate.

Historical evidence stays in [implementation history](docs/history/implementation_history.md), [experiment history](docs/history/experiment_history.md), and Git.
