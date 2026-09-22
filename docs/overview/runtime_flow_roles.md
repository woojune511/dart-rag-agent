# Runtime Flow And Roles

이 문서는 현재 source에서 실행되는 경계만 설명한다. 완료된 이전 구조와 실험
기록은 [implementation_history.md](../history/implementation_history.md)와
[experiment_history.md](../history/experiment_history.md)에 있다.

## Product path

```text
FastAPI lifespan
  -> AppServices
  -> strict StoreManifestV1 readiness
  -> SimpleRagAgent.run
  -> scoped hybrid search -> one structured answer -> citation checks
  -> FinancialRunResultV1
  -> HTTP answer/cited sources/abstention/explicit validation limits
```

- [main.py](../../main.py)는 lifespan에서 서비스를 한 번 조립한다.
- [services.py](../../src/api/services.py)는 manifest readiness와 query/ingest
  service를 소유한다.
- [financial_router.py](../../src/api/financial_router.py)는 request validation,
  503 readiness gate, threadpool dispatch, HTTP projection만 담당한다.
- [simple_rag.py](../../src/agent/simple_rag.py)는 검색·답변 생성·출처 ID 검사와 결과 조립을 소유한다. 원문 범위·ID 검사 외의 산술·의미·요청 누락 검증은 수행하지 않는다.

## Explicit comparison: checked FinancialAgent topology

아래 graph와 candidate/Compiler 계약은 명시적 비교·replay 전용이다. 기본 API와 Streamlit은 이를 초기화하거나 호출하지 않는다.

아래 블록은 [financial_graph.py](../../src/agent/financial_graph.py)의
`FinancialAgent._build_graph()` AST에서 생성된다. 변경 후
`python -m src.ops.render_runtime_topology --check`를 통과해야 한다.

<!-- BEGIN GENERATED FINANCIAL GRAPH TOPOLOGY -->
```text
entry: plan_requirements
nodes:
  plan_requirements -> FinancialAgent._plan_requirements_phase
  retrieve_evidence -> FinancialAgent._retrieve_evidence_phase
  build_candidates -> FinancialAgent._build_candidates_phase
  compile_program -> FinancialAgent._compile_program_phase
  execute_numeric -> FinancialAgent._execute_numeric_phase
  assemble_ledger -> FinancialAgent._assemble_ledger_phase
  assemble_final -> FinancialAgent._assemble_final_phase
edges:
  plan_requirements -> retrieve_evidence
  retrieve_evidence -> build_candidates
  build_candidates -> compile_program
  compile_program -> execute_numeric
  execute_numeric -> assemble_final
  assemble_final -> assemble_ledger
  assemble_ledger -> END
```
<!-- END GENERATED FINANCIAL GRAPH TOPOLOGY -->

각 node는 명시적인 typed input projection을 읽고 `FinancialAgentStateV2`의 자기
phase key 하나만 쓴다. 모든 답변은 Compiler와 `execute_numeric`를 거쳐 계산·서술 근거를
반환한다. `assemble_final`만 answer, citation, structured result를 조립하고,
`assemble_ledger`는 이 확정된 결과로 ledger를 한 번 만든다. `run()`은 완성된
결과의 공개 trace 사본에서 내부 Compiler/검증 기록을 제외하고 opt-in review/debug를 포장한다. 원본·ledger·답변·근거는 다시 계산하거나 수정하지 않는다.

## Numeric compilation boundary

모든 request는 requirement dependency와 명시적으로 연결한 output relationship으로
compilation island를 만든다. 각 island는 독립 candidate
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

## Compiled comparison retrieval boundary

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

`src/ops`의 evaluator와 benchmark runner는 명시적 비교·검증 도구다. Streamlit은 API와 같은 단순 RAG 서비스를 사용하고, 기존 계산 경로 전용 평가 탭은 제거했다.
기본 product import와 query contract의 권위가 아니다. 별도 질문 분류와 MAS,
보고서 결과 캐시·승격 경로는 [삭제했다](../architecture/portfolio_feature_retirement.md).
