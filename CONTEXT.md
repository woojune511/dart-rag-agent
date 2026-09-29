# Current Handoff Context

Last updated: 2026-09-30

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
Compiler, general graph expansion, numeric execution, repair or retry runs by default.
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

The [table-context preservation fix](docs/evaluation/table_context_hint_preservation.md) restores prose tables previously consumed as period/unit labels. Eleven original reports/473 sections preserve all19,408 prior block texts/headings and table grids;1,559 blocks are added, including four carbon-policy tables verified through chunking. Mixed captions retain their bodies and forward only explicit unit declarations.10 regression tests and full2,154 pass. At parser-fix completion, v3 store/.env were unchanged and readiness was mismatch; the subsequent v4 rebuild resolved that mismatch at its checkpoint; the v5 successor above now resolves the subsequent paragraph-style mismatch. At fix completion answer quality was NOT_RUN with no provider calls; the later v4 regression supplied bounded answer evidence for that version. Prior strict11/12 and v3 audit are historical, unchanged.

The [offline release-readiness review](docs/operations/release_readiness_2026-09-30.md) is PASS_OFFLINE_REGRESSION:default API/Streamlit construction ignores experimental caption sidecars;only an explicit `experimental_caption_links_path` enables the preserved comparison path. A red default-isolation test now passes;focused64/full2,177 tests and35-literal domain audit pass. Read-only store inspection finds compatible/ready metadata and15,608 matching graph/vector-record IDs across11 filings. Provider calls/cost0;source store and prior experiment evidence unchanged. Caption adoption remains COMPLETE_GATE_NOT_MET;the saved citation-criteria review remains diagnostic,not new accuracy. Existing source dependencies are classified together;no staging,commit,push,deployment or new paid evaluation. The subsequent [commit packaging review](docs/operations/commit_packaging_2026-09-30.md) prepares two ordered patches (9 code/test/contract files,67 record files);a Git-only source export passes64 focused tests and domain audit using installed dependencies. Actual index/HEAD unchanged;commit,push,fresh dependency install and remote CI NOT_RUN.

The [full11 store activation](docs/operations/full11_store_activation_2026-09-29.md) is PASS_ACTIVATED by subsequent user authorization, separate from the unchanged strict11/12 answer gate. Only two local dotenv store settings changed. Actual FastAPI startup/readiness and11 companies/2023 reports/14005 chunks pass; six actual hybrid searches with saved exact-query embeddings find all required witnesses. At activation there were no provider calls or persistent server; the subsequent v4 and current v5 successors are separate checkpoints.762 protected files unchanged; target SQLite bytes changed on open while sidecars/index bytes stayed unchanged. Rollback records preserve previous settings.

The [heading delivery verification](docs/evaluation/heading_scope_delivery_verification.md) confirms the existing parser correction through persisted graph/table metadata, actual temporary Chroma reopen, dense/BM25/RRF, alternating cached queries and SimpleRagAgent packets. Three new integration tests fail with the pre-fix HEAD parser and pass with current code; focused58 pass. KB/Samsung original table bodies are unchanged, and corrected headings match the rebuilt store and four saved real provider requests. That delivery check made no additional product-code changes, provider calls, source-store writes or app activation; the separate citation gate remains unmet.

The [new-store answer regression](docs/evaluation/heading_scope_answer_regression.md) is COMPLETE_ACTIVATION_GATE_NOT_MET: six exposed questions x two actual SimpleRagAgent calls on an identical store copy. Required evidence and core answers12/12; strict cited support11/12 (5/6 then6/6), stable strict5/6. KB/Samsung target confusion is absent and four prior successes hold twice; first KB answer adds correct domestic ratings from a delivered but uncited source.12 answers+12 fresh query embeddings, no errors/retries/omissions; conservative USD0.24016150/6, application batch60.77s.35 focused tests,12 blocked-network rehearsals and3 fault controls pass;963 protected files verify. At that regression stage, no product/prompt changes, app activation or paid follow-up occurred; activation was subsequently authorized separately above. Not a heading-only causal comparison or independent accuracy claim.

The [fresh rank-gate validation](docs/evaluation/rank_gate_validation_result.md) completed60 generations+8 query embeddings, no live errors/retries/NOT_RUN, estimated USD1.904832/20,195.73s. Eight new source-authored positives+2 dependent removal controls, two repetitions. Frozen disagreement>6/7 calls only G03; both paths pass it twice. RRF/conditional positives6–7/8 then7/8, always-selector7/8 twice; G07 first RRF18.9% vs exact18.950342% remains precision-undetermined because rounding/truncation tolerance was not preregistered. G02 all four answers misattribute KB Financial ratings to KB Life; original heading/context conflict recorded, causal metadata effect not isolated. Controls2/2 each repeat, zero requested-value fabrication. No confirmed stable benefit; even strict-rounding sensitivity yields only one missed G07 benefit. Progression fails. Conditional estimated USD0.487708 vs RRF0.372364 (+31.0%) and always1.532576. Nine contract tests/10 fault controls,60 request reconstructions and zero packet omissions; runtime/old artifacts unchanged, authority consumed.

The [selector-call audit](docs/evaluation/selector_call_audit.md) is COMPLETE_OFFLINE_NOT_ADOPTED. Saved strict-supported/nonabstaining outcomes: development never3/12, always9/12, oracle9/12 with6 calls; separate panel never11/12, always11/12, oracle12/12 with1 call. One unlabeled-development-median dense/BM25 disagreement rule calls4/12 development (5 passes, misses4/6 primary wins, induces1 core/evidence regression),2/12 separate (12 passes, N02 improvement/N05 tie). Separate saved estimated costs USD0.256140 never,0.416701 rule,1.067338 always; not new paid evaluation or validated routing. Both panels exposed, all candidate pools have sufficient evidence per at least one saved arm; no corpus-insufficient cases. Nine blocked-network tests and1,204 protected inputs verify. No provider/embedding calls, runtime router or automatic follow-up.

The [lossless structural catalog audit](docs/evaluation/structural_selection_feasibility.md) is COMPLETE_OFFLINE_NO_GO. All text/context/IDs/order preserved on24 saved inputs (785 candidate occurrences);12 blocked-network tests,34 old anchor controls and21 separate-panel witness occurrences pass. Local request tokens decrease3.53% on development12 and7.74% on separate N01–N12, below frozen50% gate. No cross-panel source-ID overlap, but familiar/exposed reports, not independent holdout. No provider/embedding/ingest calls, runtime change or automatic follow-up; model quality/cost NOT_RUN.2,261 input hashes protected. This successor resolves truncation loss mechanically, not model interpretation or high selector cost.

The [compact-selection feasibility audit](docs/evaluation/compact_selection_feasibility.md) is COMPLETE_OFFLINE_NO_GO: six exposed questions x flat/table,391 candidate occurrences, local paired request tokens750,537→338,938 (-54.8%). Representative candidate clues are lost in9/12 inputs; this is not model accuracy or exhaustive pool coverage. Nine network-blocked contract tests pass; original IDs/order,1,685 exact spans and full-source rehydration verify. No provider/embedding/ingest calls, paid comparison or runtime changes. Frozen v1 rejected without post-review tuning. A historical SKH DRAM witness annotation points to raw-material share; actual selected654:2 supports DRAM share. Old scores/artifacts remain unchanged; see report for limits.

The [header-link reader pilot](docs/evaluation/header_link_pilot_result.md) completed64/64 calls: A original and B original plus mechanical column/header links both pass12/12 positive questions and4/4 dependent missing-source controls in each of two repetitions. Stable B wins0, regressions0; progression gate not met. B input tokens+17.4%, conservative cost+14.5%; total USD0.846894,183.26s. Fixed gold-containing context on four familiar reports, not retrieval or independent/new-report evaluation. H16 refuses the requested values but adds correctly distinguished supported average-balance calculations. No production adoption, tuning or follow-up; one-run authority consumed. Original sources, runtime and previous experiment outputs preserved.

The [new-question selector comparison](docs/evaluation/semantic_selection_new_questions_result.md) completed12/12 pairs with36 generations and12 query embeddings, no errors/retries/NOT_RUN. Both arms delivered sufficient evidence12/12; frozen supported-complete criteria11/12 RRF versus11/12 LLM selection (explicit-question sensitivity11/12 versus12/12). One period-reading improvement and one rubric-sensitive answer omission, not retrieval recovery. Average sources8.00→1.92; workflow cost4.17x/time1.57x, total estimated USD1.32334789 and151.31s. Four familiar reports, source-authored non-independent positive-only panel. Actual candidate/answer omissions0;12 search/12 selection/24 answer packets and790 protected hashes verify. No production adoption or post-result tuning; one-run authority consumed.

The [chunk-reference ledger batch](docs/evaluation/agentic_ledger_chunk_refs_result.md) completes6/6 with22 generations and6 query embeddings, zero execution errors/retries/NOT_RUN. Source_id+note replaces coordinates/duplicated quotes; validation is chunk linkage, not exact spans/semantics/arithmetic. Kakao decline survives; Celltrion merger total is recovered; Samsung misses Welstory and omits delivered joint liability; SKH retrieves correct operands but computes -1,480,004 instead of -332,236 million, regressing a prior success. Current core-content1/5→2/5 after search, historical final3/5→2/5; corpus-omission control remains partial/abstained=false. Exposed assistant review, no causal or general accuracy claim. USD1.25090466,164.50s; historical workflow cost1.05x/time1.45x.12 decisions/10 answers/6 search traces/61 chunk references and2,078 protected files verify. Authority consumed; no post-result tuning or product adoption.

The [single-selection live batch](docs/evaluation/agentic_ledger_single_selection_live_result.md) stopped on the first decision:0 completed,1 ERROR,5 NOT_RUN. Provider/JSON completed, but an existing visible source selected pieces1–11 (11 pieces) over the per-reference maximum8. Five of six references pass physical validation; this is a span-length contract error, not missing coordinates or duplicate selection. One generation, zero search/answer calls; conservative USD0.127243,11.27s. No retry/repair/resume; one-run authority consumed.1,753 protected files verify. Answer quality remains NOT_RUN, with production and historical outputs unchanged.

The [single-selection successor](docs/evaluation/agentic_ledger_single_selection.md) removes model-owned selected_ids from the isolated ledger experiment: code derives unique sources from evidence and qualifications for retention and answer delivery.24 contract tests,42 blocked-network mock calls and15 fault/scope controls pass;18 decisions/12 answers/12 search traces reconstruct. Eight new-candidate omissions, zero retained-source omissions.1,438 protected files and prior1,043/394 manifest/seal hashes verify. No fresh provider calls, live entry disabled, quality NOT_RUN; old failures remain unchanged. This completes the authorized offline contract work, not a new evaluation or default-app adoption.

The [addressed-ledger live result](docs/evaluation/agentic_ledger_addressed_result.md) completed3 cases then rejected the fourth because a visible, valid ledger reference was absent from selected_ids; two remaining cases are NOT_RUN.13 generation +4 query-embedding calls, USD1.06809,138.51s, no retry/resume. Kakao preserved the decline qualification, Samsung retained uncertainty/joint liability but still missed Welstory, and Celltrion falsely declared sufficiency without total consideration. Completed-case historical cost1.47x, phase time1.91x; not a full six-case comparison or adoption result.7 decisions/5 answer requests/4 searches and53 accepted references reconstruct;1,043 protected files unchanged. This successor is now consumed/sealed. The earlier [quote-ledger failure](docs/evaluation/agentic_ledger_result.md), USD0.1261835, remains separate. Production stays SimpleRagAgent; no automatic follow-up batch.

The [bounded Agentic search comparison](docs/evaluation/agentic_search_result.md) completed six exposed table cases with21 generation and5 query-embedding calls, no retry/error/NOT_RUN. Celltrion total consideration is recovered; Kakao gains acquisition figures but loses a decline qualification; Samsung stops while missing Welstory litigation; the corpus-omission control remains partial with abstained=false. Two controls share unchanged initial answers by design. Estimated USD1.21970122/15; workflow cost1.85x and recorded phase time1.42x fixed-evidence selection. KAK completeness sensitivity is explicit. Production remains SimpleRagAgent; the prototype and traces are local experiment artifacts, with no automatic follow-up run.

The [fixed-pool selection comparison](docs/evaluation/fixed_pool_selection_result.md) completed36 calls once on six exposed discordant questions x A/C (12 inputs): provided-evidence sufficiency6/12→11/12, core content6/12→11/12, strict all-claim/citation support3/12→10/12 (9/12 also nonabstaining). Six missing evidence components recovered, but one previous-success input regressed by dropping current-period evidence. Fresh RRF answers differ from historical outputs; Samsung separate-scope acceptance and unsupported-rounding sensitivity are disclosed. Estimated USD1.9092735/12, no retries/errors/NOT_RUN; selection+answer cost4.04x RRF answer cost. No production adoption, prompt tuning or automatic full rerun.

The offline [full77 failure-boundary audit](docs/evaluation/structure_full77_failure_boundaries.md) traces all77 failed positive question/arm outputs:16 before candidates (14 reviewed source/component recall gaps and2 corpus omissions),39 useful required sources lost below top8,17 failures despite sufficient delivered evidence, and5 unresolved unit/row-linkage cases. Of39 representative selection witnesses,34 are BM25-only and5 dense-only. All231 saved RRF lists and actual request packets match;33 frozen corpora verify. These are failure locations, not77 independent questions or39 recovered answers. No new calls, runtime changes or rescoring; original sealed outputs remain intact.

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

User-requested [77-question flat/document/table ablation](docs/evaluation/structure_full77_result.md) completed231/231 once under a consumed USD12 combined cap (estimated USD10.38216732). Correct/complete/cited-supported positives A38/55, B18/55, C32/55; frozen-policy refusals17/19,17/19,18/19. Newly found HYU_T3_036 reference scope conflict and unit-support sensitivities are explicit; excluding that case gives38/54,18/54,31/54. Assistant source review on exposed data, not holdout accuracy; extraction/chunking/context differ jointly. Raw3,153/frozen241/protected201/review-packet9 hashes verify. No retries or post-result runtime tuning; prior outputs/stores preserved and no further provider call authorized by this consumed run.

Provider-free [failure-boundary audit](docs/evaluation/retrieval_failure_boundary_audit.md): six of seven failed hybrid pairs lose a useful source already in the saved candidate pool; one lacks asset values even there. This supports a proposed fixed-candidate selection comparison, not recovered answers or automatic paid work. Original sealed evidence and source hashes pass; runtime unchanged.

1. The final evaluation, [vanilla baseline](docs/evaluation/vanilla_dense_comparison.md), [updated introduction](docs/overview/project_overview.md) and [packaged offline demo](demo/README.md) are complete. The scoped portfolio and sharing-preparation work is closed; no automatic experiment or deployment is queued.
2. Do not restart a per-question repair queue or silently restore Compiler fallback. The default change is user-authorized, not evidence of general superiority.
3. No automatic paid batch/retry or consumed-manifest reuse. Broader independent evaluation, remote publication or deployment is separately scoped work.
4. Preserve source stores, historical raw outputs and accounting. The inactive default `data/chroma_dart` manifest mismatch remains; this change does not adopt or rebuild it.

Current checks: [project status](docs/overview/project_status.md). Chronology:
[implementation history](docs/history/implementation_history.md),
[experiment history](docs/history/experiment_history.md), and Git.
