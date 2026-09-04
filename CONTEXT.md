# Current Handoff Context

Last updated: 2026-09-04

## Canonical source

- `main` is the canonical source. The runtime redesign and checkout closeout
  landed through [PR #89](https://github.com/woojune511/dart-rag-agent/pull/89);
  provider-free candidate ambiguity instrumentation is delivered by
  [PR #90](https://github.com/woojune511/dart-rag-agent/pull/90).
- The ambiguity instrumentation does not change candidate IDs, stores, or
  compiler prompt input.
- The product path is the single-agent `FinancialAgent`. MAS, Streamlit,
  benchmark, evaluator, replay, and promotion tools remain optional or
  experimental consumers.

## Current runtime

- `FinancialAgentStateV2` is phase-owned and the final assembler is the only
  task-ledger and answer writer.
- Compiler, validator, and executor share one immutable candidate-visibility
  envelope. Catalog, cohort, or validation drift fails before execution.
- Typed per-owner matching replaces additive keyword scoring. Candidate prompts
  are cell-local, and related outputs select one complete physical row before
  compiler invocation.
- The current feature branch adds an opt-in local cross-encoder only for atomic
  numeric ties in the exact strongest factor tier. Pair v4 uses a validated
  source span or unique value surface for sentence clauses and carries typed
  target/candidate period plus bounded table context. Narrative synthesis,
  source-defined groups, and compatibility cohorts stay outside the scorer.
- Declared dependencies, non-empty coupling keys, and inferred complete-row
  bundles define bounded compilation islands. Candidate failure promotes the
  next complete row; format-only retry keeps the selected row.
- Retrieval, ingest, store readiness, API services, and the typed
  `FinancialRunResultV1` have explicit ownership boundaries. Store compatibility
  is exact, unknown occupancy fails closed, and degraded BM25 use is visible.
- FastAPI serializes shared query and ingest work before threadpool dispatch.
  Cached Streamlit services separately serialize store inspection, query,
  ingest, readiness refresh, and evaluation across sessions.

Stable rules are in
[agent_runtime_contract.md](docs/architecture/agent_runtime_contract.md), the
checked topology is in
[runtime_flow_roles.md](docs/overview/runtime_flow_roles.md), and historical
detail remains in [implementation_history.md](docs/history/implementation_history.md)
and [experiment_history.md](docs/history/experiment_history.md).

## Verification

- The current feature branch passed 818 local unittest cases, the 86-literal runtime
  domain audit, import/topology checks, pycompile, and `git diff --check`.
- The predecessor main build's Python 3.13 reviewer-contract and full-unittest
  jobs passed. This local feature branch has not been pushed or remotely
  reviewed.
- The approved store-fixed three-question gate remains **3/3 runtime-complete**
  with runtime error 0 and ledger `ok`: T2 retains `87.0만 대` and `78.1만 대`;
  T3 selects one table-82 row for `26%` and `700,691백만원`; Samsung retains its
  accepted numeric and Harman evidence.
- Admission `06a40243...016` was consumed exactly once. The run used 17 LLM
  calls, 117,631 LLM tokens, 32 query-embedding calls, zero document-embedding
  calls, and an estimated USD `0.1212257` under the approved USD `0.40` cap.
- The approved `data/chroma_dart` manifest is compatible and its predecessor
  store files remained byte-identical. This is store readiness, not a new
  provider-query result.

## Predecessor cleanup

On 2026-09-04 the original checkout
`C:\Users\geonj\Desktop\dart-rag-agent` was converted into the primary clean
`main` checkout at `9006ae7`. Its 24 visible dirty paths were preserved in the
local recoverable stash named
`pre-main-cleanup semantic-candidate-boundary predecessor 2026-09-04`; the
`codex/semantic-candidate-boundary-repair` branch pointer remains at `a278c1a`.

A read-only blob comparison against merged `main` found:

- 12 paths are already byte-identical to `main`.
- The other 12 contain no change that should be ported. They are superseded
  module-global API wiring, flat-result consumers, permissive partial-store
  reuse, pre-rationale evaluator code, the mixed-basis T3 key, stale authority
  prose, and tests for those predecessor contracts.
- The divergent paths are `AGENTS.md`, the full curated dataset, numeric
  evaluation and T3 review docs, `financial_router.py`, `benchmark_runner.py`,
  `evaluator.py`, four associated test modules, and the standalone legacy HTTP
  contract test.

The clean, already-merged `runtime-integration` and `runtime-redesign` linked
worktrees were removed. Before removal, 86 ignored result files found only in
the integration worktree were copied into the primary `benchmarks/results`
tree and verified by SHA-256; `.env`, reports, stores, and all benchmark
artifacts remain uncommitted. Do not merge or rebase the predecessor branch
into `main`; restore its stash on a separate branch only for explicit
archaeology.

## Hard boundaries and next work

1. Do not rerun the exhausted paid gate, perform fresh ingest, or rewrite saved
   stores, caches, benchmark results, candidate IDs, or historical artifacts.
2. The provider-free audit rebuilt all three saved catalogs from their exact
   structure-graph source windows and matched every saved source/catalog
   fingerprint: 4,107 candidates, 16 owner cohorts, and 154,689 compiler-prompt
   bytes. Eight cohorts have a multi-candidate top factor tier, while 3,301 of
   3,323 non-conflicting candidate-owner evaluations are `unknown_only`. The
   one complete-row bundle has two options; the selected row wins by
   position-sum margin 2 and
   worst-position margin 1. Five compiler islands recorded no retry or failure.
3. Parser-owned `period_focus` and `period_labels` now reach candidates and the
   compiler prompt without changing candidate IDs or saved catalog
   fingerprints. In the verified T3 replay, table 82 remains `당기/current/2023`
   and table 83 becomes `전기/prior/2022`; the ownership-share cohort therefore
   resolves deterministically to `cand_e2f2596cb81e73b80bbc`.
4. Exporter v2 now yields 3 atomic tied cohorts and 7 pairs, and records 4
   source-defined output/requirement cohorts as non-atomic exclusions (template
   fingerprint `7864f55f...8c24`). The original 8-case packet remains immutable.
5. Pair v4's three human-reviewed atomic cases keep all model top-1 choices
   correct, with one confident selection, zero confident errors, and warm CPU
   p95 about `739 ms`. Promotion remains `needs_review`: the deterministic
   baseline is already `1.0`, so this set cannot demonstrate the required gain.
6. Collect genuine baseline-error atomic ties before another model bakeoff.
   Prefer numeric-binding hard negatives or smaller/GPU/ONNX inference; do not
   lower the margin or add keyword weights merely to manufacture coverage.
7. Keep the persisted typed fact index deferred behind a separately approved,
   versioned ingest/store migration.
