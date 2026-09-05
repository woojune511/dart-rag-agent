# Current Handoff Context

Last updated: 2026-09-05

## Working source

- Product: single-agent `FinancialAgent`.
- Branch: `codex/bounded-semantic-tiebreaker`; repair baseline: `5e13bc6`;
  latest runtime-contract fix: `bacb9c2`.
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

Python 3.13 full unittest `877 / 877`, domain audit (84 reviewed literals),
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

1. Admission `45ef0f6e...4f03` was consumed once on this build. T3 passed all
   runtime/evidence/ledger gates; T2 and Samsung stopped on Google query-
   embedding `429 RESOURCE_EXHAUSTED` before compiler output. Runtime gate:
   `1 / 3` in that artifact.
2. Follow-up admission `da9cd31e...0acf` was then consumed exactly once for the
   two failed rows. Samsung passed both obligations with accepted candidate
   `cand_27da082cf5bcd0cb9f27`, rendered `28,352,769백만원`, runtime error `0`,
   evaluator faithfulness/completeness `1.0`, and ledger `ok`. T2 again stopped
   on Google query-embedding `429` before compiler output.
3. The immutable same-runtime T3 success plus the new Samsung success make the
   combined runtime gate `2 / 3`; release remains `HOLD`. Both admissions are
   exhausted. Do not repeat either run. The remaining blocker is provider
   capacity at the Google query-embedding boundary, not another semantic patch.
4. Admission `10c8ca9c...2786` was consumed once on `36fcf62` to rebuild only
   the Hyundai store side-by-side with canonical OpenAI
   `text-embedding-3-large`. All 28 document batches returned HTTP 200; the
   separate-process search health passed before manifest publication. The new
   store has 1,764 vectors and strict readiness `compatible`. Reconstructed
   chunks, metadata, and parents match the Google source projection exactly,
   and source fingerprint `5cdc0e8f...0ff6` is unchanged. Actual provider
   billing is unavailable; the local-tokenizer estimate through health remains
   USD `0.25071982` under the approved USD `0.30` ceiling. Run receipt SHA-256:
   `6fa0c805...d4719`. The approval is exhausted; T2 eval-only needs a new exact
   admission and is not authorized by this rebuild.
5. Admission `9bdd8db4...30fe3` was consumed exactly once on `b29b239` for
   OpenAI-store-fixed `HYU_T2_010`. All query embeddings completed; there was no
   fresh ingest, document embedding, source mutation, or runner retry. The numeric
   obligation selected `87.0만 대`, `78.1만 대`, and source display `11.5%`, while
   preserving the calculated `11.395646606914212` as `11.4%`. The narrative
   obligation had six visible candidates, including one explicit match, but the
   planner serialized its absent display unit as string `"null"`; preflight
   therefore blocked that island before a compiler call. Runtime status is
   partial, error `0`, ledger `ok`, so the combined gate remains `2 / 3` and
   release `HOLD`. The run used 5 LLM calls / 34,430 tokens and 11 query / 0
   document embedding calls; local non-embedding estimate USD `0.0379082`, actual
   billing unavailable. Root result SHA-256 is `8aac48c7...32b69`; ignored receipt
   SHA-256 is `86d21248...ead74`.
6. Generic successor `bacb9c2` normalizes serialized null sentinels only at the
   optional planner-field boundary. Focused planner `4 / 4`, compiler/validator/
   executor integration `101 / 101`, import/topology `28 / 28`, full unittest
   `877 / 877`, audit, and pycompile pass. It has not received a provider replay;
   the consumed `9bdd8db4...30fe3` admission must not be reused, and any successor
   requires a fresh exact manifest and approval.
7. Formula-wide rounding-error propagation is deferred. Source precision
   comparison currently scales only the selected source's rounding interval.
8. T3 answer-key/evaluator governance is separate; do not change tolerance,
   faithfulness policy, dataset answers, or source evidence to improve a score.

Historical evidence stays in [implementation history](docs/history/implementation_history.md),
[experiment history](docs/history/experiment_history.md), and Git.
