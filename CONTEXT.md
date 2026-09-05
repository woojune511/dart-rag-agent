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

1. Immutable T3 and Samsung successes remain the carried evidence for the
   three-question gate. Both have runtime error `0` and ledger `ok`; together
   they keep the current combined gate at `2 / 3` and release at `HOLD`.
2. Admission `640ef7be...986c` was consumed exactly once on clean commit
   `145982f` for OpenAI-store-fixed `HYU_T2_010`. All 11 query embeddings
   completed, with no fresh ingest, document embedding, source mutation, or
   runner retry. The optional-null fix worked: narrative `ob_002` compiled once,
   selected `cand_bbd863eb396fa724d814`, and completed without retry.
3. Numeric `ob_001` did not reach the compiler. The planner duplicated its own
   raw inputs `us_sales_2023` and `us_sales_2022` into `depends_on`; after the
   evidence requirements received stable IDs, island preflight correctly saw
   those stale names as unknown answer-obligation dependencies. The island had
   zero calls and zero prompt bytes. This is a planner projection/schema boundary,
   not a retrieval, ranking, embedding, compiler, or executor failure.
4. The run exited zero in `79.721s`, with runtime error `0`, ledger `ok`,
   completeness `0.5`, faithfulness `0.0`, 5 LLM calls / 26,782 tokens, and
   11 query / 0 document embedding calls. The recorded non-embedding estimate is
   USD `0.0285496`; actual billing remains unavailable. Source-store fingerprint
   stayed `6231cd8e...24e9`. Root result SHA-256 is `d86b650c...3040`; ignored
   receipt SHA-256 is `859a2483...021f`.
5. Generic successor `af9a07e` removes only exact same-obligation evidence IDs
   from `depends_on`, while preserving real answer dependencies and fail-closed
   unknown/self checks. Planner `5 / 5`, semantic contracts `164 / 164`,
   import/topology `28 / 28`, full unittest `878 / 878`, audit, pycompile, and
   diff checks pass. It has made no provider call.
6. The `640ef7be...986c` approval is exhausted and must not be reused. A provider
   confirmation of `af9a07e` requires a fresh clean-HEAD manifest plus separate
   egress and cost approval; no automatic retry is authorized.
7. Formula-wide rounding-error propagation is deferred. Source precision
   comparison currently scales only the selected source's rounding interval.
8. T3 answer-key/evaluator governance is separate; do not change tolerance,
   faithfulness policy, dataset answers, or source evidence to improve a score.

Historical evidence stays in [implementation history](docs/history/implementation_history.md),
[experiment history](docs/history/experiment_history.md), and Git.
