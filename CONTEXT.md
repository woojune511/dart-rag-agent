# Current Handoff Context

Last updated: 2026-09-05

## Working source

- Product: single-agent `FinancialAgent`.
- Branch: `codex/bounded-semantic-tiebreaker`; repair baseline: `5e13bc6`.
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
- Query readiness, execution, and snapshot share one operation lock; DB work,
  ingest, and post-ingest readiness refresh run in workers.
- Explicit phase TypedDicts replace the full-state merge. Numeric execution and
  narrative validation return facts, not final answers. The graph finishes
  `assemble_final → assemble_ledger → END`; `run()` only packages the result.
  TypedDicts describe static shape, not runtime immutability.

## Verification and claim boundary

Python 3.13 local tests, domain audit (84 reviewed literals), import/topology,
pycompile, and diff checks pass; detailed counts are in project status.
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

1. Admission `45ef0f6e...4f03` was consumed once on this build. T3 passed all
   runtime/evidence/ledger gates; T2 and Samsung stopped on Google query-
   embedding `429 RESOURCE_EXHAUSTED` before compiler output. Runtime gate:
   `1 / 3`; release remains `HOLD`.
2. Do not retry under this admission. T2 source-display selection and Samsung
   numeric selection therefore remain provider-unverified on the repaired
   build. Preserve the failed artifact and diagnose provider capacity before
   proposing any new exact manifest.
3. Formula-wide rounding-error propagation is deferred. Source precision
   comparison currently scales only the selected source's rounding interval.
4. T3 answer-key/evaluator governance is separate; do not change tolerance,
   faithfulness policy, dataset answers, or source evidence to improve a score.

Historical evidence stays in [implementation history](docs/history/implementation_history.md),
[experiment history](docs/history/experiment_history.md), and Git.
