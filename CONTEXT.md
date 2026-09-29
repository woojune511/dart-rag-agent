# Current Handoff Context

Last updated: 2026-09-29

## Product boundary

The user authorized simple RAG as the default API/Streamlit path after discussing
its reduced guarantees. Starting source: `2a926a6e`; branch:
`codex/reviewed-compiler-selection-gate`.
Read [AGENTS.md](AGENTS.md), [runtime contract](docs/architecture/agent_runtime_contract.md),
[adoption decision](docs/architecture/simple_rag_adoption.md),
[code map](docs/overview/codebase_map.md), and [project status](docs/overview/project_status.md).

`SimpleRagAgent.run` performs one scoped hybrid search and at most one structured
answer call. Empty evidence abstains without generation. Explicit metadata scope,
source identity and response/citation shape are checked. No classifier, Planner,
Compiler, graph expansion, numeric execution, repair or retry runs by default.
The packet has a whole-source byte bound and visible omissions. API answers expose
workflow, abstention, cited source text and validation limits. Compiler result/trace
objects are empty; no task ledger is fabricated. Review/debug observations are opt-in.

Semantic support/output coverage are not checked; arithmetic is not executed.
Source-ID validity is not entailment or numeric correctness. `FinancialAgent` and
its source/calculation checks remain only for explicit comparison/replay under
[compiled_workflow_contract.md](docs/architecture/compiled_workflow_contract.md).
Shared model construction does not import that path into the application.
Parser schema is v5; the local full11 successor store is compatible/ready=true. Embedding model identity is preserved. `openai` keeps
answer/ingest-context routes; `openai_compiler` is comparison-only and rejected by
application startup. The old embedded evaluation dashboard is removed.

## Evidence and accounting

The [parser v5 adoption](docs/architecture/parser_v5_adoption.md) records the user-approved parser/tests/docs commit separately from the unchanged [answer regression](docs/evaluation/paragraph_heading_v5_answer_regression.md): core14/14,strict11/14,stable4/7 (absence-wording sensitivity12/14,still gate not met). Plain and paragraph-style heading ownership, table-body preservation and bounded separator parsing are adopted. The verified local full11 v5 store has15,608 chunks; source/metadata delivery fixes do not certify all headings or general answer accuracy. Remaining added-claim citation omissions and overbroad absence wording are separate follow-up items. No new provider calls,prompt tuning,store mutation or automatic rerun is authorized by this adoption.

The [development comparison](docs/evaluation/portfolio_workflow_comparison_successor.md)
on `6bc4aae5` completed four familiar pairs using shared frozen evidence. It found
no clear current-workflow quality advantage at 3.47x estimated cost / 4.79x measured
time. These are historical measurements, not current-app or holdout performance.
Its one-batch authority is consumed. The [failed predecessor](docs/evaluation/portfolio_workflow_comparison_result.md)
and loss ceilings remain separate and immutable. The selected NAVER2023 filing has
1,090 chunks in a two-filing source graph; no broader coverage claim.

The [final application evaluation](docs/evaluation/simple_rag_final_result.md) ran
once on `6083bf36`, with runtime unchanged from `a9270221`: 12/12 complete,
9/9 answerable cases correct/complete/source-supported, safe abstention2/3.
F11's successful abstention has an overbroad period explanation; F12 substitutes
annual-average revenue for an unavailable daily fact and fails. Assistant review
on familiar NAVER2022/2023 filings is not independent gold or an unseen holdout.
Mean question time4.02s, including checkpoints but excluding startup; overall57.73s.
Calls:11 answers/12 embeddings; no errors, retries, unknown usage or NOT_RUN cases.

The [vanilla dense baseline](docs/evaluation/vanilla_dense_comparison.md) reused
the same exposed 12-case panel, answer model, prompt/schema and top-8 limit.
Hybrid versus dense-only fully supported positive answers are 9/9 versus5/9;
dense-only safe abstentions are3/3 versus hybrid2/3. The dense arm used saved
query vectors, so its 30.74s batch time is not live retrieval latency. It made11
answer calls, zero new embeddings/retries/errors, and conservatively accounted
USD0.1798695 under a consumed standalone USD1.65 authorization. Raw outputs stay
ignored; the public document is a scoped summary, not independent reproduction.

The separate [table answer2x2 comparison](docs/evaluation/structure_answer_result.md)
completed36/36 on fixed retrieval lists:8 primary questions plus1 NIM diagnostic
per arm. Correct/complete/cited-supported answers are flat dense2/8, flat RRF5/8,
structured dense3/8, structured RRF4/8. No overall structure advantage; explicit
narrative/scope sensitivities prevent a general accuracy claim. Generation cost
USD1.1334995 under consumed standalone USD6.85 authority; prior retrieval cost
USD1.47618744 under consumed USD1.60 authority. No retries/runtime tuning; ignored
artifacts remain under `benchmarks/results/structure_retrieval_factorial_2026-09-28/`.

Historical shared accounting: USD21.20953897/26.32, remaining5.11046103, pending0.
New estimated cost0.20762954 under one-run cap5.25; no new funding or invoice claim.
Authorization `ae05c617...c9543` is consumed. All135 protected files,86 runtime files
and144 frozen raw outputs retain their hashes; no original-store/settings change.
Local raw outputs, receipts and saved-response demo live under
`benchmarks/results/simple_rag_final_2026-09-22/`; do not stage them.

## Public review package

The user subsequently authorized the one-page introduction, shareable offline
demo and clean-checkout verification. `demo/index.html` packages five selected
saved cases (F02/F05/F10/F11/F12), with exact answers and all six cited chunks.
`demo/provenance.json` records selection/origin hashes; `demo/verify.py` is a
standard-library data-integrity check, not an upstream execution or quality proof.
The full12-case metrics remain distinct from this after-run selection. Raw logs,
settings, stores and original result files remain local and unchanged.

Tracked-tree archive `4e67f378` passes isolated Python `-I -S` and browser checks
without `.env`, `.venv`, data or the local run bundle. All five selections render
exactly; desktop/mobile/dark layouts pass with JS errors/external requests0.
Tampered data rejects. Existing26 tracked historical summary files are retained.
Source runtime and paid accounting are unchanged; no provider call, push or deployment.
Receipts: `benchmarks/results/simple_rag_public_demo_2026-09-22/` (ignored).

Subsequent main integration preserves PR98's static Pages workflow and five-case
navigation (F02 first), plus PR99's public guide names and neutral wording.
Current SimpleRag guarantees and the table answer comparison remain authoritative.
Saved answer/source data is unchanged; only the demo's initial selection changed.
Integration gates: full2,129/2,129, focused22, domain audit35, demo integrity and
188 result/156 input hashes pass. No paid run or runtime-source change.

## Completion and hard stops

1. The final evaluation, [vanilla baseline](docs/evaluation/vanilla_dense_comparison.md), [updated introduction](docs/overview/project_overview.md) and [packaged offline demo](demo/README.md) are complete. The scoped portfolio and sharing-preparation work is closed; no automatic experiment or deployment is queued.
2. Do not restart a per-question repair queue or silently restore Compiler fallback. The default change is user-authorized, not evidence of general superiority.
3. No automatic paid batch/retry or consumed-manifest reuse. Broader independent evaluation, remote publication or deployment is separately scoped work.
4. Preserve source stores, historical raw outputs and accounting. The inactive default `data/chroma_dart` manifest mismatch remains; this change does not adopt or rebuild it.

Current checks: [project status](docs/overview/project_status.md). Chronology:
[implementation history](docs/history/implementation_history.md),
[experiment history](docs/history/experiment_history.md), and Git.
