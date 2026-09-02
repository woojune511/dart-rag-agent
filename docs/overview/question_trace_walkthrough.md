# Question Trace Walkthrough

이 문서는 현재 single-agent runtime에서 질문 하나가 통과하는 경계만 설명한다.
정확한 node/edge 목록은 source-generated block이 있는
[runtime_flow_roles.md](runtime_flow_roles.md)를 따른다.

## 1. API entry

`main.py`의 lifespan이 `AppServices`를 만들고 `app.state`에 둔다. Query는 먼저
`StoreManifestV1` readiness를 확인한다. Missing 또는 mismatch이면 agent를
호출하지 않고 503을 반환한다. Ready 상태이면 `QueryRequest.report_scope`를
그대로 전달해 `FinancialAgent.run()`을 threadpool에서 실행한다.

```text
POST /api/query
  -> readiness gate
  -> threadpool FinancialAgent.run
  -> FinancialRunResultV1.agent_answer
  -> QueryResponse
```

HTTP 기본 응답에는 review/debug가 없다. 두 bundle은 요청 플래그가 true일 때만
생성하고 포함한다.

## 2. Request, routing, requirements

`request` envelope에는 query와 report scope만 들어간다. `route_request`가 intent,
format, company, year, topic을 `routing`에 기록하고, `plan_requirements`가 answer
obligation과 required evidence를 `requirements`에 기록한다. 각 node는 자기 phase
외의 top-level key를 쓰지 않는다.

## 3. Retrieval

`retrieve_evidence`는 내부적으로 plan, search, select, trace 네 단계를 순서대로
실행한다. Dense/BM25 결과와 구조 확장 순서는 유지되며, 최종 visible window와
seed window는 `retrieval` envelope에 기록된다. Degraded BM25-only 실행은 명시적
설정일 때만 가능하고 trace에 이유가 남는다.

## 4. Numeric branch

Numeric 또는 mixed requirement이면 `build_candidates`가 물리 provenance를 가진
catalog를 만든다. `compile_program`은 obligation dependency와 non-empty coupling
key로 island를 만들고, island별 candidate visibility 안에서만 program을
compile/validate한다.

```text
retrieve_evidence
  -> build_candidates
  -> compile_program (island by island)
  -> execute_numeric
```

Executor는 compiler와 동일한 `CompilationEnvelopeV1`을 받는다. Catalog,
visibility, validation fingerprint가 달라지거나 owner 밖 ID가 선택되면 산술을
실행하지 않는다. 성공한 island는 retry prompt에 다시 넣지 않으며 merge 후 JSON
bytes를 유지한다.

## 5. Narrative branch

Program이 필요하지 않으면 `build_narrative`가 evidence extraction, compression,
validation을 실행한다. 이 node도 최종 public answer를 쓰지 않고
`narrative_result` envelope만 반환한다.

```text
retrieve_evidence -> build_narrative
```

## 6. Ledger and final result

두 branch는 `assemble_ledger`에서 합쳐진다. 이 node만 phase 결과로부터 tasks,
artifacts, integrity trace를 한 번 생성한다. `assemble_final`은 answer, citations,
structured result를 조립한다.

`FinancialAgent.run()`은 최종 graph state를 다음 typed 결과로 투영한다.

```text
FinancialRunResultV1
  schema_version
  agent_answer
  review_trace?    # opt-in
  debug_bundle?    # opt-in
```

Internal callers must use these attributes; flat dict fallback은 없다.

## 7. Where to inspect a failure

| Symptom | First authority |
| --- | --- |
| 503 before query | `StoreReadiness` and `store_manifest.json` |
| wrong scope/search window | `retrieval_debug_trace` |
| candidate missing or wrong row | candidate catalog and cohort diagnostics |
| hidden/cross-owner ID | `CandidateVisibilityV1` and compile validation |
| compile retry | `semantic_candidate_stage_diagnostics_v3` island attempts |
| execution refusal | `visibility_mismatch`, `validation_drift`, or semantic validation errors |
| answer/evidence mismatch | `AgentAnswer`, `ReviewTrace.evidence_items`, ledger integrity |

Evaluator output and historical benchmark bundles are downstream observations;
they do not override these runtime contracts.
