# Project Status

Last updated: 2026-09-03

## At a glance

| Question | Current answer |
| --- | --- |
| Product | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Active branch | `codex/typed-candidate-ranking` from integration predecessor `729e0fb` |
| Runtime state | Typed owner targets and deterministic fact matching replace additive candidate keyword scoring |
| Public result | `FinancialRunResultV1`; review/debug are opt-in and the HTTP answer wire shape is unchanged |
| Store readiness | Approved manifest written; exact manifest check is `compatible`, `ready=true`, `degraded=false` |
| Provider evidence | Exact admission `cb188492...683a8` was consumed once in a store-fixed three-question `eval-only` run; no fresh ingest or document embedding |
| Release status | **HOLD, 2/3 runtime-complete**; T3 is missing the Motional investment carrying-amount obligation |

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
- Numeric compilation is isolated by declared dependency and non-empty coupling
  key. Unknown dependency, self-dependency, cycle, island overflow, or candidate
  reservation overflow fails before compiler calls.
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

The source-change gate is focused tests, runtime-domain audit, import/topology
checks, full unittest discovery, pycompile, and `git diff --check`. The preceding
integration gate passed 751 total unittest cases, 124 focused
evaluator/provenance cases, 30 benchmark-runner cases, 50 focused
authority/import/topology/service cases, and 86 reviewed domain literals.
Historical benchmark scores and bundles are not evidence for this candidate
ranking build.

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

A new ignored three-row admission bound the current runtime and the ordered
scope `HYU_T2_010`, `HYU_T3_072`, `SAM_T2_078`. Its manifest SHA-256 is
`cb188492de5b51ee3b42cf5cf9aaf6c12192d92567c001a0426c4e6e785683a8`.
Two production-order no-call processes produced byte-identical 5,640-byte
receipts at
`d63ae5e34e939b68f03f4bc69b897af2f2b755c47039e4a4873352d1117105b3`,
with provider/network/output counts all zero and source/target/temp invariants
intact. A third immediate pre-dispatch rehearsal reproduced both hashes with the
target absent.

The separately approved provider run executed exactly once, in the specified
Hyundai-then-Samsung order, and completed in 314.7 seconds with runner exit code
zero. The ignored root result is
`benchmarks/results/runtime_contract_integration_focused_successor_2026-09-02/results.json`
(SHA-256
`59e43b35a2b013b13f53ff33ecbc8a43a04d7590f7ca8d5752ca1a62f286e5f3`).

| Question | Runtime result | Gate evidence |
| --- | --- | --- |
| `HYU_T2_010` | `ok`, 2/2 obligations | `87.0만 대` and `78.1만 대` produced `11.4%` with source display `11.5%`; narrative also present; error 0, ledger `ok` |
| `HYU_T3_072` | `partial`, 2/3 obligations | Motional `26%` and summary present; `ob_002` investment carrying amount missing; error 0, ledger `ok` |
| `SAM_T2_078` | `ok`, 2/2 obligations | `28,352,769백만원` and Harman narrative present; error 0, ledger `ok` |

The missing T3 value is not absent from the parsed table. The same Motional row
projects `cand_e2f2596cb81e73b80bbc = 26%` and
`cand_a8aa299ad5dea4f29cd5 = 700,691백만원`. The latter appears in the global
prompt ID set but not in `ob_002`'s selectable owner cohort. Both attempts for
that island therefore returned no candidate and the same visibility
fingerprint. Dependency/coupling edges and preflight errors were empty, and the
wrong-row BHAF `53%` physical candidate was not selectable. The observed owner
is cohort ranking/admission, not table parsing or coupling.

The runner estimated USD `0.1575934` for 21 LLM calls and 146,156 tokens, below
the approved USD `0.40` ceiling. Embedding pricing remains unavailable; usage
was 33 query-embedding calls and zero document-embedding calls. Source result
hashes, both store directory fingerprints, and both SQLite hashes remained
unchanged, and no disposable store remains.

## Next work

1. Finish the local source gate and review this branch without changing stores,
   datasets, evaluator tolerances, or historical artifacts.
2. Do not rerun the paid gate automatically. Any provider replay requires a new
   immutable manifest, cost estimate, no-call receipts, and separate approval.
3. Treat a local semantic reranker, deterministic unique-match auto-bind, and a
   persisted typed fact index as deferred designs. They need their own measured
   benefit and migration contract rather than being bundled into this repair.

See [runtime_flow_roles.md](runtime_flow_roles.md) for the checked topology,
[agent_runtime_contract.md](../architecture/agent_runtime_contract.md) for the
normative contract, and the history documents for superseded implementation and
experiment detail.
