# Runtime Flow And Roles

이 문서는 현재 source에서 실행되는 경계만 설명한다. 완료된 이전 구조와 실험
기록은 [implementation_history.md](../history/implementation_history.md)와
[experiment_history.md](../history/experiment_history.md)에 있다.

## Product path

```text
FastAPI lifespan
  -> AppServices
  -> strict StoreManifestV1 readiness
  -> FinancialAgent.run
  -> FinancialRunResultV1
  -> stable HTTP answer/citation/structured-result shape
```

- [main.py](../../main.py)는 lifespan에서 서비스를 한 번 조립한다.
- [services.py](../../src/api/services.py)는 manifest readiness와 query/ingest
  service를 소유한다.
- [financial_router.py](../../src/api/financial_router.py)는 request validation,
  503 readiness gate, threadpool dispatch, HTTP projection만 담당한다.
- [financial_graph.py](../../src/agent/financial_graph.py)는 graph wiring과 최종
  `FinancialRunResultV1` 조립을 소유한다.

## Checked FinancialAgent topology

아래 블록은 [financial_graph.py](../../src/agent/financial_graph.py)의
`FinancialAgent._build_graph()` AST에서 생성된다. 변경 후
`python -m src.ops.render_runtime_topology --check`를 통과해야 한다.

<!-- BEGIN GENERATED FINANCIAL GRAPH TOPOLOGY -->
```text
entry: route_request
nodes:
  route_request -> FinancialAgent._route_request_phase
  plan_requirements -> FinancialAgent._plan_requirements_phase
  retrieve_evidence -> FinancialAgent._retrieve_evidence_phase
  build_candidates -> FinancialAgent._build_candidates_phase
  compile_program -> FinancialAgent._compile_program_phase
  execute_numeric -> FinancialAgent._execute_numeric_phase
  build_narrative -> FinancialAgent._build_narrative_phase
  assemble_ledger -> FinancialAgent._assemble_ledger_phase
  assemble_final -> FinancialAgent._assemble_final_phase
edges:
  route_request -> plan_requirements
  plan_requirements -> retrieve_evidence
  retrieve_evidence -- build_candidates --> build_candidates
  retrieve_evidence -- build_narrative --> build_narrative
  build_candidates -> compile_program
  compile_program -> execute_numeric
  execute_numeric -> assemble_final
  build_narrative -> assemble_final
  assemble_final -> assemble_ledger
  assemble_ledger -> END
```
<!-- END GENERATED FINANCIAL GRAPH TOPOLOGY -->

각 node는 명시적인 typed input projection을 읽고 `FinancialAgentStateV2`의 자기
phase key 하나만 쓴다. Numeric/narrative node는 계산 결과와 검증된 근거만
반환한다. `assemble_final`만 answer, citation, structured result를 조립하고,
`assemble_ledger`는 이 확정된 결과로 ledger를 한 번 만든다. `run()`은 완성된
결과와 opt-in review/debug를 포장할 뿐 답변이나 근거를 다시 계산하지 않는다.

## Numeric compilation boundary

Numeric 또는 mixed request는 requirement의 dependency와 non-empty
`coupling_key`만으로 compilation island를 만든다. 각 island는 독립 candidate
visibility와 prompt를 가지며 순차 compile된다. Compiler가 만든 immutable
`CompilationEnvelopeV2`를 validator와 executor가 공유한다. executor는 catalog,
obligation, source bundle, visibility, validation fingerprint가 달라지면 실행 전에
fail-closed한다.

Candidate 생성과 물리 provenance는
[financial_reconciliation_candidates.py](../../src/agent/financial_reconciliation_candidates.py),
compile/island orchestration은
[financial_graph_calculation.py](../../src/agent/financial_graph_calculation.py),
검증과 deterministic 실행은
[financial_calculation_execution.py](../../src/agent/financial_calculation_execution.py)가
소유한다.

## Retrieval boundary

[financial_retrieval_pipeline.py](../../src/agent/financial_retrieval_pipeline.py)는
동일 owner 안에서 다음 네 단계로 실행된다.

1. `_build_plan`: scope, filter, query budget을 결정한다.
2. `_execute_searches`: primary/retry search와 query-result cache를 실행한다.
3. `_select_evidence`: strict scope filter, rerank, visible window를 결정한다.
4. `_build_trace`: 선택 결과와 telemetry를 `retrieval_debug_trace`로 투영한다.

검색 결과 순서와 외부 graph node는 이 내부 분해의 영향을 받지 않는다.

## Ingest and store boundary

[ingest_service.py](../../src/ingestion/ingest_service.py)가 fetch, parse, context
generation, index, manifest 기록을 소유한다. Context 생성은
[context_generator.py](../../src/ingestion/context_generator.py), store identity는
[store_manifest.py](../../src/storage/store_manifest.py)에 있다.

Manifest가 없거나 runtime contract와 다르면 기본 query path는 503이다. 기존
non-empty store는 자동 채택하지 않는다. BM25-only는 환경 설정으로 명시한
degraded mode에서만 허용되며 readiness와 retrieval trace에 표시된다.

## Optional surfaces

`src/ops`, Streamlit UI, evaluator, benchmark runner와 `src/experimental/mas`는
검증 또는 실험 surface다. 기본 product import와 query contract의 권위가 아니다.
MAS는 single-agent 결과를 소비하는 optional adapter이며 별도 제품 topology로
간주하지 않는다.
