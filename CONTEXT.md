# Current Handoff Context

Last updated: 2026-09-06

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

1. Admission `0f0c0d52...0445` was consumed exactly once on clean commit
   `58551c7` for OpenAI-store-fixed `HYU_T2_010`. Both obligations completed,
   runtime error is `0`, ledger is `ok`, and evaluator faithfulness/completeness
   are `1.0 / 1.0`. There was no fetch, ingest, document embedding, source
   mutation, or runner retry.
2. Numeric `ob_001` selected `87.0만 대`, `78.1만 대`, and source display
   `11.5%`; deterministic calculation is `11.395646606914212`, rendered as
   `11.4%`. Narrative `ob_002` selected `cand_bbd863eb396fa724d814`. Both islands
   had empty preflight errors, confirming the dependency-projection repair.
3. Numeric compilation used its allowed one same-cohort internal retry to repair
   source assertions; narrative compilation was not retried. Final program is
   ready with four selected candidates, two outputs, and no missing obligation.
4. The run exited zero in `118.936s`, using 7 total LLM calls / 71,359 tokens and
   11 query / 0 document embedding calls. Recorded non-embedding cost is USD
   `0.0664263`; actual billing remains unavailable. Source-store fingerprint is
   unchanged at `6231cd8e...24e9`, and no disposable store remains. Root result
   SHA-256 is `a765a132...0ad9`; ignored receipt is `4dd004f2...a3b4`.
5. With the manifest-bound immutable T3 and Samsung successes, the defined
   source-consistent runtime release gate is now `3 / 3 PASS`: completeness 3/3,
   runtime error 0, ledger `ok`. The mixed-question
   `numeric_final_judgement=null` is evaluator N/A, not a runtime failure.
6. The approval is exhausted. No further provider retry is authorized or needed
   for this gate.
7. Formula-wide rounding-error propagation is deferred. Source precision
   comparison currently scales only the selected source's rounding interval.
8. T3 dataset governance completed on 2026-09-03: the active curated answer and
   evaluator canonical reference use one consolidated Motional tuple (`26%`,
   `700,691백만원`, and the four same-basis summary measures). Runtime and
   dataset/evaluator ownership remain separate; do not relax tolerance,
   faithfulness policy, or source-evidence requirements to improve a score.
9. Latest compiler-only admission `11b34e4b...c7dd` was consumed once on `4fefb27`.
   Synthetic cases passed `8/9`: seven requested calculations and the zero-prior
   ratio abstention. The ninth case explicitly left comparison target/denominator
   unspecified, but the model negated both inputs and returned `-125%` instead of
   declaring ambiguity. Structural validation/execution accepted that valid math;
   the semantic review gate failed. All five real questions were not dispatched.
10. All 10 responses ended `STOP` and parsed; runtime errors are zero. The only
    internal retry repeated the zero-prior abstention, not dependency input repair.
    Captured outputs and prompt hashes reproduce exactly with network blocked.
    Estimated USD `0.0408142`; retrieval/planner/evaluator/embedding/store activity
    is zero. Result SHA `14e7490c...a9d8`; approval is exhausted. No automatic rerun.
    Result: `benchmarks/results/semantic_comparison_compiler_successor_2026-09-06/result.json`.
    Inputs and runtime are unchanged. Next: compare models on the frozen ambiguity
    case, with separate manifest/cost/transmission approval, not more warning rules.

Historical evidence stays in [implementation history](docs/history/implementation_history.md), [experiment history](docs/history/experiment_history.md), and Git.
