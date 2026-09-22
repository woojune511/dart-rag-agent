# Project Status

Last updated: 2026-09-22

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

Ingest/parser/store/embedding identity is unchanged. Application model construction
uses only answer and ingest-context routes; compiler-only profile selection is
rejected. The old Streamlit compiled-evaluation tab is removed. Comparisons remain
separate; their [contract](../architecture/compiled_workflow_contract.md) is preserved.

## Current verification

The [simple-RAG transition](../architecture/simple_rag_adoption.md) passes **2,125/2,125 tests** (64.083s), including 16 new application-boundary controls. Focused56, final API/profile48 and comparison/import48 pass; domain audit35 and documentation/topology checks pass. Actual SDK serialization and HTTP projection use mocked transport, with one answer call and no Compiler. All110 protected files retain their hashes. Paid calls and new model-quality/latency evaluation: **NOT_RUN**.

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

## Next work

1. Build a separate final evaluation set and demo for the adopted simple-RAG app.
2. Keep retrieval, supported-answer quality, abstention, source-ID checks and arithmetic/semantic limitations separate in the report.
3. Do not add per-question prompt/schema rules or restore Planner/Compiler as an automatic fallback.
4. Historical compiled comparisons remain explicit tools; previous one-batch approvals are consumed.

Shared conservative accounting remains USD21.00190943/26.32, remaining5.31809057,
pending0. A final paid run needs a separately frozen scope and ceiling. The stored
comparison selected one NAVER2023 filing; that is not unseen multi-company coverage.
The inactive default-store manifest mismatch and previously observed semantic/
retrieval failures are not repaired by this architecture change.
