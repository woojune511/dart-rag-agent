# Project Status

Last updated: 2026-09-29

## Current implementation

The default API and Streamlit runtime is `SimpleRagAgent`, on
`codex/reviewed-compiler-selection-gate`, adopted by explicit user direction from
`2a926a6e`. [Decision and compatibility](../architecture/simple_rag_adoption.md).
`FinancialAgent` is now an explicitly invoked compiled comparison/replay path.

| Boundary | Application behavior |
| --- | --- |
| Request | Exact question and explicit caller report scope; no inferred company/year filters |
| Retrieval | One existing hybrid search, scope before top-K and after retrieval |
| Context | Whole source text/context, document-qualified IDs, 65,536-byte packet bound with omission reasons |
| Generation | One structured answer call; empty evidence abstains without a call; no retry/Compiler fallback |
| Validation | Response shape, source IDs and explicit metadata scope only |
| Limitations | Arithmetic is not executed; semantic support and output coverage are not checked |
| Response | Answer, cited source text, abstention and validation labels; empty compiler result/trace fields |
| Observation | Optional JSON-native retrieval/review data, usage, timing and interrupted diagnostics |

Parser schema is v5; the local full11 successor store is compatible/ready=true. Embedding model identity is preserved. Application model construction
uses only answer and ingest-context routes; compiler-only profile selection is
rejected. The old Streamlit compiled-evaluation tab is removed. Comparisons remain
separate; their [contract](../architecture/compiled_workflow_contract.md) is preserved.

## Current verification

The [parser v5 adoption](../architecture/parser_v5_adoption.md) records the user-approved parser/tests/docs commit separately from the unchanged [answer regression](../evaluation/paragraph_heading_v5_answer_regression.md): core14/14,strict11/14,stable4/7 (absence-wording sensitivity12/14,still gate not met). Plain and paragraph-style heading ownership, table-body preservation and bounded separator parsing are adopted. The verified local full11 v5 store has15,608 chunks; source/metadata delivery fixes do not certify all headings or general answer accuracy. Remaining added-claim citation omissions and overbroad absence wording are separate follow-up items. No new provider calls,prompt tuning,store mutation or automatic rerun is authorized by this adoption.

The [final application evaluation](../evaluation/simple_rag_final_result.md) on `6083bf36` completed all12 frozen questions once: 9/9 answerable cases meet correctness/completeness/source-support criteria, safe abstention2/3 (deterministic1/1, model1/2). F11's abstention has an overbroad period explanation; F12 incorrectly substitutes an annual average for actual daily revenue. No positive retrieval miss was observed. This is assistant review on familiar NAVER2022/2023 filings, not independent gold or unseen-company performance. No post-result prompt/runtime tuning.

The actual application service path used11 answer calls/12 embeddings, with errors/retries/unknown usage/NOT_RUN0. Question mean4.02s, generation-case mean4.37s, overall57.73s including startup; these local instrumented times are not production HTTP latency. Estimated incremental cost USD0.20762954, no new funding. The [saved-response demo](simple_rag_demo.md) shows all answers/cited sources and opens on the failure; raw artifacts remain local and ignored.

The subsequent [vanilla dense baseline](../evaluation/vanilla_dense_comparison.md) keeps the same exposed panel, answer model, prompt/schema and top-8 limit. Hybrid versus dense-only positive required-evidence coverage and fully supported answers are9/9 versus5/9. Dense-only has6/9 correct-complete positive contents and safe abstention3/3; three answerable retrieval misses remain unanswered. It uses saved query vectors, so its30.74s batch is not live retrieval latency. Eleven answer calls, zero new embeddings/retries/errors, 62,127 input and2,046 output tokens were observed; conservative accounting is USD0.1798695 under the consumed standalone USD1.65 cap, not billing.

The [flat/structured × dense/RRF retrieval comparison](../evaluation/structure_retrieval_factorial.md) uses nine exposed table questions across six filings. Original annotation coverage is13/26,18/26,12/26,19/26, not semantic coverage: the NIM reference incorrectly uses bank values for a group question. Excluding it leaves13/24,16/24,10/24,17/24. Representation jointly changes extraction, chunking and metadata; one supporting Celltrion sentence is missing. Embedding phase:118 calls/11,355,288 tokens, zero retries/errors, estimated USD1.47618744; USD1.60 authority consumed.

The subsequent [actual answer comparison](../evaluation/structure_answer_result.md) completes36/36 once,8 primary questions plus1 diagnostic per arm. Correct/complete/cited-supported answers are flat dense2/8, flat RRF5/8, structured dense3/8, structured RRF4/8. No aggregate structured-RRF advantage; a specific FX table recovery succeeds. Samsung narrative attribution and SK borrowing-scope sensitivities are explicit, not hidden score changes.36 calls/402,659 input/10,571 output tokens, zero errors/retries/NOT_RUN/embeddings; conservative USD1.1334995 under consumed USD6.85 cap.188 sealed files and156 frozen inputs verify; focused26 tests and prior two36-case offline rehearsals/five stop controls pass. No runtime/prompt tuning.

The current main-integration close passes **2,129/2,129 local Python 3.13 tests**
(79.057s), including three public-guide merge regressions. This includes deterministic deep-JSON diagnostics across platforms and
the absence of the retired `src.experimental` package; their focused 50-test set
passes. The earlier simple-RAG transition's focused56, final API/profile48,
comparison/import48, domain audit35 and documentation/topology gates also passed.

## Packaged offline review

Main integration retains PR98's static Pages workflow/F02-first case navigation and PR99's renamed public guides. The current SimpleRag contract and latest paired/table evaluations are preserved; historical compiled material stays labeled. Published demo payload changes only `initial_case` versus the original package, not answers, sources or evaluation metrics.

The [one-page introduction](project_overview.md) now describes simple RAG and the evidence behind simplification. [demo/index.html](../../demo/index.html) is included in Git: five selected saved cases, exact answers and all six cited chunks, with success/abstention/failure and separate full12-case metrics. No installation, credentials, server or source store is needed. The full raw bundle stays local; [provenance](../../demo/provenance.json) hashes are integrity references, not independent execution proof. Older compiled portfolio documents are explicitly historical.

Tracked-tree archive `4e67f378` passes the standard-library verifier with `-I -S` and minimal environment, without `.env`, `.venv`, data or the local run. All five browser selections preserve exact text; desktop/mobile/dark layouts pass, JS errors/external requests0. Changed payload rejects. Current documentation authority2/2 passes. This is local package validation, not a fresh evaluation, remote CI or deployment; runtime/model/settings and paid accounting are unchanged.

## Prior checkpoints (not default-RAG acceptance)

The [feature retirement](../architecture/portfolio_feature_retirement.md) removes duplicate question routing, MAS, report-result cache/promotion, unused reflection/ratio-repair code and dedicated tools/tests: 63 files deleted, net10,855 fewer lines across source/configuration/tools. Seven graph nodes remain; initial filing scope comes only from explicit caller scope, public query_type is neutral qa, and unspecified retrieval format is mixed. Planner/Compiler and source/arithmetic/coverage guards remain. Full suite **2,109/2,109** (73.338s), focused81+64 and domain audit35 pass; all110 protected files retain their hashes. No paid calls or model-quality/speed claim. Earlier measurements below retain their original source version.

The [successor comparison](../evaluation/portfolio_workflow_comparison_successor.md) on clean `6bc4aae5` **completed four development pairs**: 11 new calls plus one reused baseline, no retries/provider errors. Separate assistant source review finds no clear current-workflow quality advantage at **3.47x estimated cost / 4.79x measured elapsed time**; cash retrieval/year-end meaning and one-decimal display remain gaps. One filing, exposed cases, joint representation/workflow changes and reused timing limit inference. New spend0.359777; shared **USD21.00190943/26.32**, remaining **5.31809057**, pending0, not billing. Reuse is not double charged; original loss ceilings remain. Approval consumed. Pre-run **2,271/2,271** tests (72.440s), 16 comparison contracts and blocked-socket SDK/graph/persistence rehearsal pass. Product runtime/prompts/policies/stores unchanged; original and successor raw hashes verified.

The [original shared-evidence attempt](../evaluation/portfolio_workflow_comparison_result.md) remains **INTERRUPTED, zero complete pairs**. One baseline survived; two current-workflow calls lost output/usage to the writer's Document serialization error, and six arms were NOT_RUN. The offline writer fix passed2,267/2,267 tests (67.897s), adding complete-result persistence coverage missed by the earlier2,266 tests. After USD6 added funding, that failed attempt charged0.612957 (known usage0.016349 + lost-record ceilings0.596608). Its consumed approval, failure result and conservative charge are preserved separately from the completed successor above.

Portfolio cleanup: retired narrative generation/validation, dividend/entity-specific answer assembly, alternate narrative selection, and their dedicated models/policies/tests are removed. Runtime/config is **3,723 lines smaller** (70 added/3,793 removed). Full unittest **2,255/2,255** (79.243s), runtime domain audit **66**, import/topology/documentation gates and focused contracts pass. All **15,050** protected predecessor files and local `.env` retain their hashes. The public Planner/Compiler path and source/calculation guards remain. Paid calls, fresh ingest and new accuracy evaluation: **NOT_RUN**.

Prior [real-question Planner evidence](../evaluation/planner_real_questions_result.md) remains period1/2, scope2/2, combined1/2. Cash year-end meaning was lost; unchanged-cell replay2/2 does not prove semantic success. Accounted USD20.02917543/20.32, remaining0.29082457, pending0; no new spend or funding. This is a documented limitation, not the automatic next prompt patch.
Earlier source-choice tests cover input enums, source-kind fields, mixed/dependency/empty spaces,
stable refs/authority; import/topology/docs 24, audit 83, pycompile/diff pass. Prior contracts use
direction-only pairs, owned request/source links, same-cohort/dependency retry and V2 proofs.
The 12 anonymous controls were frozen before source edits. Historical fixtures stay
byte-identical; test-only copies explicitly author new request/proof/transport fields.
An authored response is an execution witness, not a sampled model answer.
Eleven new numeric-transport contracts cover available fields, foreign/inexact
contexts, owner/input isolation, offline invalid-proof rejection and V2 tampering.
Real SDK count/generation serialization is tested with blocked sockets and mocked HTTP.
Schema sizes versus `dd61e466`: axis-only 3,477 → 2,309 bytes; one context
3,477 → 3,234; parsed located-context fixture 3,469 → 3,293. These are local UTF-8
schema sizes, not total request/token savings or measured model success.
Numeric instructions grow 2,890 → 3,420 UTF-8 bytes; schema reduction alone
does not imply a smaller complete request, especially for contextual inputs.
Those sizes precede display-intent clarification. Its six new contracts cover
initial/retry request guidance, actual normalization through final answer/ledger,
positive/negative/equal values, direct precision and query/program tampering.
One authored expression grows 16,474 → 17,062 prompt bytes and 4,151 → 4,454 schema
bytes; candidate fingerprint/permissions and one mock call are unchanged.
No new schema fields, classifier or semantic validator; no SDK-token/accuracy claim.
Comparison wiring adds one nullable request ID, not a quote or candidate role. One
fixture's local prompt/schema/response grows 298/387/43 UTF-8 bytes; one mock call, no retry.
The [latest exact-response replay](../../benchmarks/results/semantic_scope_isolation_2026-09-15/RESULTS.md)
uses eight saved cases with blocked sockets: numeric outputs 4→5, mock calls 10→8,
retries 2→0. Forward -10% now executes unchanged; reverse -10% remains wrong.
All source/raw response/initial prompt/schema/visible IDs and six other programs/output
bytes are unchanged. No live retry-reduction, semantic repair or new model sample.
Schema preparation errors now retain the original error class and scoped diagnostics,
with unavailable schema bytes marked null; they no longer become UnboundLocalError.

The earlier five-case provider-free boundary comparison passed in both versions
(before the subsequent bare-value and V2 numeric-transport changes):

| Measurement | Baseline `d9c36d8d` | Earlier boundary build |
| --- | ---: | ---: |
| Authored fixture cases | 5 | 5 |
| Mock Compiler invocations / retries | 6 / 0 | 6 / 0 |
| Prompt UTF-8 bytes | 208,427 | 134,135 |
| Schema UTF-8 bytes across calls | 59,832 | 37,115 |
| Provider / embedding / store writes | 0 | 0 |

Selected IDs and numeric/display output signature are identical
(`2ca7903e16772081eb5bed50489e7ce982fc83e020521b586983a200ab5880d5`).
Prompt/schema reductions are 35.6% / 38.0%, not SDK token or latency measurements.
Source-linked wrapper/name contrasts now execute without a literal-equality gate;
unlinked/foreign axes still fail. Structurally valid wrong interpretations remain
semantic negative controls. These local gates do not measure model semantic accuracy.

## Compiled evidence archive

Detailed compiler-only probes and their immutable source/output restrictions remain
in [experiment history](../history/experiment_history.md) and the
[reviewed evidence index](../evaluation/reviewed_case_evidence_status.md).
They do not establish current simple-RAG model quality or runtime acceptance.

## Historical evidence, not current-build acceptance

- Preceding Google [subject-grounding full-agent run](../../benchmarks/results/subject_grounding_full_agent_2026-09-14/RESULTS.md)
  on `054c6b22`: 2/3 runtime complete, 3/5 outputs accepted, runtime errors 0,
  ledger 3/3 ok. Admission `af784682...a8f0` consumed; no new release claim.
- [Addressed compiler-only run](../../benchmarks/results/narrative_address_compiler_2026-09-14/RESULTS.md)
  on `9771417f`: 9/9 structurally complete and source-reviewed against pre-fixed
  criteria; not human gold, unseen holdout or current full-agent performance.
- [Independent pilot](../../benchmarks/results/independent_pilot_compiler_2026-09-10/README.md):
  7/12 runtime complete, 4/9 reference-scalar questions, all three narratives had
  a completeness/faithfulness concern in source review. Source-exposed, immutable.
- [Reviewed-case index](../evaluation/reviewed_case_evidence_status.md) and
  [experiment history](../history/experiment_history.md) retain earlier results,
  source/fixture provenance and their claim limits. No predecessor bytes were edited.

## Completion and remaining limits

1. The [scoped portfolio milestone](portfolio_scope.md) and subsequent sharing preparation are complete: frozen panel, one actual-app evaluation, paired vanilla baseline, reports, current introduction and packaged offline demo. No automatic follow-up experiment is queued.
2. Broader independent evaluation, remote publication and deployment remain separately scoped work. Package validation is not a release or general accuracy guarantee.
3. Do not add per-question prompt/schema rules or restore Planner/Compiler as an automatic fallback.
4. Historical compiled comparisons remain explicit tools; previous one-batch approvals are consumed.

Shared conservative accounting is USD21.20953897/26.32, remaining5.11046103,
pending0. Final-run authorization `ae05c617...c9543` is consumed; no paid retry or
reuse of the unused run allowance. Historical charges and loss ceilings are preserved.
The inactive default-store manifest mismatch and previously observed semantic/
retrieval failures are not repaired by this architecture change.
