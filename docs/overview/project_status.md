# Project Status

Last updated: 2026-09-04

## At a glance

| Question | Current answer |
| --- | --- |
| Product | Single-agent `FinancialAgent` for evidence-backed DART filing analysis |
| Canonical source | `main`; runtime redesign through PR #89 and provider-free ambiguity audit through PR #90 |
| Runtime state | Typed owner matching, atomic direct-output rows, and complete policy-defined source rows replace additive keyword scoring and independent multi-output selection |
| Public result | `FinancialRunResultV1`; review/debug are opt-in and the HTTP answer wire shape is unchanged |
| Store readiness | Approved manifest written; exact manifest check is `compatible`, `ready=true`, `degraded=false` |
| Provider evidence | Atomic-bundle admission `06a40243...016` was consumed once in a completed store-fixed three-question `eval-only` run; no fresh ingest or document embedding |
| Release status | **PASS, 3/3 runtime-complete** with runtime error 0 and ledger `ok`; qualitative evaluator thresholds remain separate |

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
- An opt-in local cross-encoder can reorder only atomic numeric ties in the exact
  strongest tier. Pair v4 carries typed period/table context and isolates
  sentence values. Narrative/group selection is excluded; low confidence or
  failure keeps the default order, and the feature remains disabled.
- Numeric compilation is isolated by declared dependency, non-empty coupling
  key, and inferred complete-row evidence bundles. A bundle adds an island edge
  even when planner coupling is empty. Code ranks complete rows from existing
  owner cohorts, selects one before compiler invocation, and removes alternative
  row IDs from output and requirement visibility. Numeric compatibility
  narratives remain available. Unknown dependency, self-dependency, cycle,
  island overflow, or candidate reservation overflow fails before compiler calls.
- Retrieval is internally split into plan, search, selection, and trace stages.
- `IngestService` owns fetch through manifest recording. `FinancialAgent` no
  longer exposes ingest methods.
- FastAPI dependencies live in lifespan-owned `AppServices`; sync query and ingest
  execute in a threadpool. Liveness and readiness are separate endpoints.
- Cached Streamlit services serialize store inspection, query, ingest plus
  readiness refresh, and evaluation across sessions.
- Evaluator-only accepted calculation/answer variants require one complete,
  source-qualified atomic match. They do not alter runtime selection or promote
  qualitative scores.
- A `source_defined_group` with a selected structured row exposes every
  policy-defined cell from that physical row as required. Candidate failure
  rejects that row as a unit, and capacity overflow fails before compilation.
- Derived values render their source-visible inputs. Faithfulness judge output
  records a short rationale without changing score thresholds or overrides.
- Benchmark `store-only` excludes question/evaluator work, while `eval-only`
  evaluates from a disposable store copy and preserves its source bytes.
- MAS and Streamlit remain experimental consumers, not the product authority.

## Evidence and remaining gate

The merged provider-free source combines typed target matching, cell-local
prompts, complete-row bundle inference, and fail-closed validation. Complete
options use the existing per-owner ranks: lowest summed position, then lowest
worst position, then physical IDs. Only the selected row enters the compiler's
candidate dictionary and active constraint. Candidate rejection rebuilds the
cohorts so the next complete row can be promoted; format-only retry keeps the
same row. Ranked alternatives are diagnostic-only. The feature branch passes 818
local unittest cases, the 86-literal domain audit, import/topology checks,
pycompile, and `git diff --check`. The predecessor main build passed both Python
3.13 CI jobs; this feature branch has not been pushed or remotely reviewed.

The exact atomic-bundle admission preserved the order `HYU_T2_010`,
`HYU_T3_072`, `SAM_T2_078`. Manifest
`06a402433efa892f016f537dac1eceb4776e62cc67c83e2e4494309c310dd016`
and all three no-call rehearsals resolve to the same 6,730-byte receipt SHA-256
`0e7ea486665d42d0be3686a067281461069bb887981dcd9e0d92a9409f95889f`.

The separately approved process ran once, exited zero after 276.8 seconds, and
wrote the ignored atomic-bundle result with SHA-256
`b103657a301aea72ae1d529a163f6db4a686361c061fe4c0029092817f44753e`.

| Question | Runtime result | Gate evidence |
| --- | --- | --- |
| `HYU_T2_010` | `ok`, 2/2 obligations | Same four predecessor evidence IDs; `87.0만 대` and `78.1만 대` produce `11.4%`, with source display `11.5%`; error 0, ledger `ok` |
| `HYU_T3_072` | `ok`, 3/3 obligations | One compiler call, no retry; ownership `26%` and carrying amount `700,691백만원` both come from table 82 row `9:2`; no table 83 numeric ID; error 0, ledger `ok` |
| `SAM_T2_078` | `ok`, 2/2 obligations | All three predecessor evidence IDs retained plus one compatible Harman overview source; `28,352,769백만원` and Harman narrative remain; error 0, ledger `ok` |

T3's option ranker considered both complete direct-output rows, selected table
82 before compiler invocation, and projected the direct owner spaces through
that choice. Its Motional summary is still grounded in the distinct summary
tables appropriate to those measures. Across all questions the compiler made
five island calls and no internal retry.

The bounded provider runtime gate is **3/3 PASS**. It does not change the HYU T3
historical provider output or relax evaluator criteria. The raw evaluator still
reports T2/T3 completeness `0.7/0.3`, Samsung faithfulness `0.7`, and two
company-level full-eval failures; those are not promoted into runtime acceptance.

After that paid gate, the source review decision corrected the canonical HYU T3
key from a mixed separate/consolidated basis to the complete consolidated tuple.
Provider-free replay of the saved source window now keeps table 90 row `21:4`
as four required cells: `1,775`, `(803,742)`, `12,115`, and `(791,627)`
백만원. Re-rendering the saved T2 execution trace includes the source inputs
`2023 87.0만 대` and `2022 78.1만 대` without exposing an internal obligation
ID. These are local successor checks, not a new benchmark result.

The historical Samsung faithfulness judge returned `0.7` without a persisted
rationale, so its exact concern cannot be reconstructed. New evaluator outputs
retain the judge reason; no score, tolerance, or acceptance rule was relaxed.

The run recorded 17 LLM calls, 117,631 LLM tokens, 32 query-embedding calls,
zero document-embedding calls, and estimated runtime cost USD `0.1212257`, below
the approved USD `0.40` ceiling. Embedding pricing is unavailable. Both source
result hashes, SQLite hashes, and complete store fingerprints remain unchanged;
no disposable store remains.

## Provider-free candidate ambiguity baseline

The read-only audit matched all three immutable source/catalog fingerprints
(4,107 candidates). Eight of 16 cohorts had a multi-candidate top tier and
3,301/3,323 non-conflicting matches were `unknown_only`. The original exporter
found 8 tied cohorts / 31 pairs; applicability, visibility, and row bundles
remained authoritative.

The reviewed successor preserves parser-owned `당기/current` and `전기/prior`
labels in candidates and compiler rows without changing candidate IDs or the
three saved catalog fingerprints. T3's ownership-share tie now resolves by
period applicability before semantic scoring. Exporter v2 leaves 3 atomic ties
with 7 pairs and records 4 source-defined output/requirement cohorts as
non-atomic. On those 3 human-reviewed cases, pair v4 achieved top-1 `1.0`, one
confident selection, zero confident errors, and warm CPU p95 about `739 ms`.
This is a provider-free no-regression/context check, not promotion evidence.

## Next work

1. Do not rerun the paid gate. Admission `06a40243...016` is exhausted.
2. Keep benchmark artifacts uncommitted. The predecessor remains recoverable in
   its named stash; restore it on a separate branch only for explicit
   archaeology, and do not port its superseded contracts.
3. Keep the tie-breaker opt-in. Pair v4's reviewed atomic set has no top-1
   regression but cannot show gain because its deterministic baseline is
   already `1.0`; do not lower the `0.05` margin based on three cases.
4. Collect and label genuine baseline-error atomic numeric ties before comparing
   numeric-binding or smaller/GPU/ONNX models. Treat narrative and
   source-defined evidence as set selection plus synthesis, not top-one labels.
5. Keep the typed fact index behind a versioned store migration.

See [runtime_flow_roles.md](runtime_flow_roles.md) for checked topology and
[agent_runtime_contract.md](../architecture/agent_runtime_contract.md) for the normative contract; superseded detail stays in history documents.
