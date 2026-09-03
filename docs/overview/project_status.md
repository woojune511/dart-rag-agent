# Project Status

Last updated: 2026-09-03

## At a glance

| Question | Current answer |
| --- | --- |
| Product | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Active branch | `codex/typed-candidate-ranking`, successor of provider-gate snapshot `9641563` |
| Runtime state | Typed owner matching plus immutable physical-row evidence bundles replace additive candidate keyword scoring and independent multi-output selection |
| Public result | `FinancialRunResultV1`; review/debug are opt-in and the HTTP answer wire shape is unchanged |
| Store readiness | Approved manifest written; exact manifest check is `compatible`, `ready=true`, `degraded=false` |
| Provider evidence | Env-bound admission `9c1d1807...86a3c3` was consumed once in a completed store-fixed three-question `eval-only` run; no fresh ingest or document embedding |
| Release status | **HOLD, 2/3 source-consistent**; mechanical runtime status is 3/3, but T3 combines different Motional table bases |

## Current boundaries

- `FinancialAgentStateV2` has one top-level writer for each phase. Intermediate
  nodes do not mutate the task/artifact ledger or final answer.
- Compiler, validator, and executor share one immutable visibility envelope.
  Catalog or validation drift fails before execution.
- Each obligation or evidence requirement may carry a typed semantic target.
  Candidate admission compares scope, local subject, owner kind, unit, metric,
  and physical locality as separate factors; explicit conflicts are excluded
  and compatible candidates precede unknown-only candidates.
- The candidate catalog remains complete and stable. Cohort prompts contain
  cell-local structured text and one factor projection; they do not perform a
  second keyword ranking pass.
- Numeric compilation is isolated by declared dependency, non-empty coupling
  key, and inferred complete-row evidence bundles. A bundle adds an island edge
  even when planner coupling is empty; all outputs must select one physical-row
  option. Unknown dependency, self-dependency, cycle, island overflow, or
  candidate reservation overflow fails before compiler calls.
- Retrieval is internally split into plan, search, selection, and trace stages.
- `IngestService` owns fetch through manifest recording. `FinancialAgent` no
  longer exposes ingest methods.
- FastAPI dependencies live in lifespan-owned `AppServices`; sync query and ingest
  execute in a threadpool. Liveness and readiness are separate endpoints.
- Evaluator-only accepted calculation/answer variants require one complete,
  source-qualified atomic match. They do not alter runtime selection or promote
  qualitative scores.
- Benchmark `store-only` excludes question/evaluator work, while `eval-only`
  evaluates from a disposable store copy and preserves its source bytes.
- MAS and Streamlit remain experimental consumers, not the product authority.

## Evidence and remaining gate

The new provider-free matcher contract covers typed targets, deterministic
catalog-order independence, compatible-before-unknown ordering, catalog-grounded
legacy fallback, cell-local prompt projection, validator rejection of a visible
semantic conflict, and ontology unit families. The current source gate passes
752 total unittest cases, 146 focused semantic/import/topology/documentation
cases, the 86-literal runtime-domain audit, pycompile, JSON validation, and
`git diff --check`. Stored-source reconstruction
places the Motional carrying-amount cell in the intended owner cohort and keeps
the BHAF row out; it also prioritizes the two Hyundai T2 period values over
market totals and preserves Samsung's accepted evidence visibility. It does not
claim a new LLM/compiler outcome.

The current provider-free successor infers a bundle only when two or more
same-subject direct outputs have a complete compatible physical row. It rejects
mixed-row programs, can attach required source-defined narrative only through a
compatible report context, and retries all bundle owners together while
excluding only rejected IDs. The source gate passes 760 unittest cases,
including eight focused bundle cases, the 86-literal runtime-domain audit,
import/topology checks, pycompile, and `git diff --check`. This is local contract
evidence, not a new provider result. Read-only reprojection gives T3 one island
with two coherent options: table 82 row `9:2` (`26%`, `700,691백만원`) or table 83
row `9:2` (`25.92%`, `907,061백만원`); T2 and Samsung gain no spurious bundle.

The clean redesign predecessor's read-only reprojection rebuilt candidates from
the three stored source windows with network access blocked. It retained both
Hyundai T2 period values
while excluding the two market totals, retained Motional 26% while excluding
both BHAF 53% candidates, and restored all three accepted Samsung evidence IDs;
the saved Samsung program validated `ready`. Source hashes did not change and no
result artifact was written.

The three curated dataset slices now carry identical source-qualified
calculation variants for `LGE_T1_051`; their existing primary answer, tolerance,
operand, and result fields are unchanged. The HYU T3 source review records one
possible same-basis consolidated tuple but deliberately does not register it or
change the mixed-basis canonical key.

The approved adoption added only `data/chroma_dart/store_manifest.json`, SHA-256
`98ec5dcb6a376c490d3ced20c5ffe56c276a8f5e382d97dc18dcbe59d3920615`.
All seven predecessor store files remained byte-identical. The pure manifest
readiness check returns exact `compatible`, `ready=true`, and `degraded=false`;
no provider query was made.

The current ignored env-bound admission fixes the predecessor's missing runtime
credential binding and preserves the ordered scope `HYU_T2_010`, `HYU_T3_072`,
`SAM_T2_078`. Its manifest SHA-256 is
`9c1d1807f74397d528278592c6867e491decf23abbb03977fb33c837cf86a3c3`.
Two no-call processes plus the immediate pre-dispatch rehearsal produced the
same 6,552-byte receipt at
`31adb7b259247b9006be373e2aa2ff9def635dec50f6416ecbb9e921ff98c5f9`,
with provider/network/output counts zero and source/target/temp invariants
intact.

The separately approved provider run executed exactly once in Hyundai-then-
Samsung order and completed in 295.5 seconds with exit code zero. The ignored
root result is
`benchmarks/results/typed_candidate_ranking_focused_successor_envbound_2026-09-03/results.json`
(SHA-256
`a80fdbdff7b7b8d05091b74f2cffcdfaf76822549d992ca5311ee6118d89617d`).

| Question | Runtime result | Gate evidence |
| --- | --- | --- |
| `HYU_T2_010` | mechanically `ok`, source-consistent | `87.0만 대` and `78.1만 대` produced `11.4%` with source display `11.5%`; narrative present; error 0, ledger `ok` |
| `HYU_T3_072` | mechanically `ok`, source-inconsistent | Selected `25.92%` from table 83, `700,691백만원` from table 82, and one detailed-table loss; 3/3 obligations, error 0, ledger `ok` |
| `SAM_T2_078` | mechanically `ok`, source-consistent | `28,352,769백만원` and Harman narrative present; error 0, ledger `ok` |

The paid artifact shows that the typed matcher repaired the original visibility
loss: the `26%` candidate
`cand_e2f2596cb81e73b80bbc` is first in the ownership cohort, and
`cand_a8aa299ad5dea4f29cd5 = 700,691백만원` is first in the carrying-amount
cohort. The wrong-row BHAF `53%` candidate is not selectable. The compiler may
still choose any visible ID in that predecessor runtime, however. It independently preferred the more
precise-looking `25.92%` candidate from a different table. Because all three
planner coupling keys were empty, no island or execution validation compared
the physical row/table basis across outputs. The source successor now infers
that missing bundle edge, but the immutable paid result remains HOLD until a
separately approved run validates the new runtime.

The run recorded 20 LLM calls, 136,312 LLM tokens, 30 embedding calls, zero
document-embedding calls, and estimated runtime cost USD `0.1356168`. Embedding
pricing remains unavailable. One initial canonical-routing embedding call
returned HTTP 429 and degraded safely. Source result hashes, both store
directory fingerprints, and both SQLite hashes remained unchanged; no
disposable store remains.

## Next work

1. Do not rerun the paid gate automatically. Any provider replay requires a new
   immutable manifest, cost estimate, no-call receipts, and separate approval.
2. Treat a local semantic reranker, deterministic unique-match auto-bind, and a
   persisted typed fact index as deferred designs. They need their own measured
   benefit and migration contract rather than being bundled into this repair.

See [runtime_flow_roles.md](runtime_flow_roles.md) for the checked topology,
[agent_runtime_contract.md](../architecture/agent_runtime_contract.md) for the
normative contract, and the history documents for superseded implementation and
experiment detail.
