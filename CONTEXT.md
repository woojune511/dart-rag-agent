# Current Handoff Context

Last updated: 2026-09-05

## Working source

- Product: single-agent `FinancialAgent`.
- Branch: `codex/bounded-semantic-tiebreaker`; repair baseline: `5e13bc6`;
  latest runtime-contract fix: `af9a07e`.
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
  rendering. Currency/count scales, composite signs, canonical units, USD direct
  values, and non-finite results are covered by real-normalizer tests.
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

Python 3.13 full unittest `878 / 878`, domain audit (84 reviewed literals),
import/topology, pycompile, and diff checks pass; detailed counts are in project
status.
Provider-free replay verifies all three saved catalog identities and unchanged
input-file hashes:

- T2: explicit source-display copy renders `11.5% (재계산값 11.4%)`.
- T3: original program bytes and physical row/evidence remain unchanged.
- Samsung: restoring its recorded first binding accepts `28,352,769백만원`
  and preserves the existing narrative evidence.

T2 and Samsung are explicitly counterfactual runtime-contract tests. That replay
itself made no compiler/provider/evaluator call and is not a release claim.
Receipt: `benchmarks/results/runtime_contract_provider_free_replay_2026-09-05/replay_final.json`.

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
8. T3 answer-key/evaluator governance is separate; do not change tolerance,
   faithfulness policy, dataset answers, or source evidence to improve a score.

Historical evidence stays in [implementation history](docs/history/implementation_history.md),
[experiment history](docs/history/experiment_history.md), and Git.
