# Agent Runtime Contract

이 문서는 에이전트가 코드를 수정하거나 실험을 설계할 때 고정해야 하는 runtime 계약이다. 목표는 benchmark row에 맞춘 즉흥 패치를 막고, ingest, retrieval, planning, calculation, evaluation을 재현 가능한 시스템 경계로 나누는 것이다.

## 1. Canonical Ingest

Routine validation의 기준 ingest는 `structural_selective_v2_prefix_2500_320`이다.

코드 기준값:

- `CANONICAL_INGEST_PROFILE_ID = "structural_selective_v2_prefix_2500_320"`
- `CANONICAL_INGEST_MODE = "structural_selective_v2"`
- `CANONICAL_CHUNK_SIZE = 2500`
- `CANONICAL_CHUNK_OVERLAP = 320`

다른 ingest 방식은 experimental profile로만 사용한다. 품질 비교가 필요하면 profile 이름과 결과 디렉터리로 격리하고, runtime default를 조용히 바꾸지 않는다.

## 2. Retrieval Trace

retrieval 단계는 최소한 `retrieval_debug_trace`를 남긴다.

필수 필드:

- `query_bundle`: 실제 retrieval 후보 query 목록
- `executed_queries`: 실행 query, `k`, `where_filter`, source(`primary` 또는 `retry`)
- `where_filter`: 최종 metadata filter
- `effective_k`: retrieval node가 적용한 k
- `retry_queries`: reflection retry query 목록
- `candidate_count`: rerank 전후 후보 수 판단에 쓸 후보 수
- `seed_count`: seed retrieval docs 수
- `selected_count`: 최종 선택 docs 수
- `selected_chunks`: rank, score, chunk uid, section, block type, company, year, receipt
- `policy_trace`: intent, operation family, format preference, retrieval hint, preferred sections, scope flags

이 trace는 answer 품질을 보정하기 위한 데이터가 아니라, 왜 그 evidence가 선택됐는지 검증하기 위한 감사 로그다.

## 3. Focused Verification Gate

변경 검증 순서는 다음으로 고정한다.

1. 관련 unit/contract test
2. `python -m unittest discover -s tests`
3. 필요한 경우 focused benchmark 또는 eval-only
4. full benchmark

full benchmark는 store/cache/input 조건이 확인됐을 때만 실행한다. 5분 이상 결과 파일이 생성되지 않으면 `results.json` 존재 여부만 보지 말고 실행 heartbeat를 확인한다. 로그 출력, store/cache 파일 갱신, 프로세스 CPU/IO가 계속 움직이면 fresh store 구축 또는 장기 ingest로 분류하고 monitored run으로 전환한다. 가능하면 `benchmark_runner --progress-heartbeat-sec <seconds> --heartbeat-log <path>`로 runner-native heartbeat를 켜서 phase/progress/store mtime을 직접 남긴다. 결과 파일도 없고 heartbeat도 없으면 중단하고, 코드 실패인지 실행 환경 문제인지 분리해서 기록한다.

## 4. Task Ledger And Artifact Store

agentic workflow의 기본 통신 모델은 자유 채팅이 아니라 task ledger와 artifact store다.

Task ledger는 다음을 표현해야 한다.

- task id, assignee, instruction, status
- dependency(`depends_on`)
- produced artifact ids
- retry count와 blocked reason

Artifact store는 다음을 표현해야 한다.

- artifact id, kind, producer task id
- payload 또는 content
- evidence links
- metadata

Orchestrator, Analyst, Researcher, Critic은 이 구조를 통해 상태를 교환한다. LLM 메시지 전문은 보조 로그일 수 있지만, 다음 단계의 입력 계약이 되어서는 안 된다.

## 5. Boundary Rules

Parser regex는 DART 문서 구조 복원용이다. answer나 retrieval decision을 특정 benchmark에 맞추는 용도로 쓰지 않는다.

Retrieval/routing policy는 `src/config/retrieval_policy.py`처럼 명명된 config에 둔다. 특정 회사, 질문, 평가 row 이름이 runtime branch에 들어가면 중단하고 일반 정책인지 다시 분류한다.

Numeric path는 deterministic contract를 따른다. 산술, 단위 변환, operand ordering, dependency binding, dedupe, validation은 코드가 담당한다. LLM은 intent, concept, evidence interpretation처럼 의미 판단에만 쓴다.

Evaluator는 평가 정의를 담을 수 있지만, runtime agent가 evaluator trick을 따라가면 안 된다.

## 6. Concept Planner Candidate Validation

LLM concept planner는 의미 해석을 보조할 수 있지만, ontology concept를
무근거로 선택해서 runtime task를 열면 안 된다.

- query/topic/planner feedback에서 매칭된 ontology concept가 있으면 planner
  후보는 그 concept set과 group member로 제한한다.
- 명시 concept 매칭이 없어 전체 ontology catalog fallback을 쓰는 경우에도,
  `surface_contract.positive`가 정의된 concept는 해당 positive term이
  query/topic/planner feedback에 나타날 때만 허용한다.
- 일반 정책/법령/시장 맥락이 특정 세액공제, 특정 회계처리, 특정 metric
  concept로 승격되려면 ontology alias나 surface contract가 그 좁은 의미를
  직접 지지해야 한다.
- 거부된 LLM planner task는 runtime branch로 보정하지 말고 validator note와
  retrieval trace를 통해 원인을 확인한다.

이 규칙은 LLM의 semantic flexibility를 유지하면서, benchmark나 특정 문항에서
그럴듯해 보이는 concept 과매칭이 runtime execution으로 넘어가는 것을 막기
위한 최소 게이트다.

### Segment Binding Scope

Planner/runtime code may attach a `segment_label` only when the segment surface
and the numeric metric surface are co-located in the same query clause or a very
near local span. A segment mentioned only in a separate narrative/background
clause must not scope an unrelated numeric lookup. Mixed numeric+narrative
queries should remain split into a company-level numeric task plus a narrative
task when the query wording supports that split.

This is a generic binding rule, not a place to encode company names, segment
names, or benchmark-specific vocabulary. Metric surfaces must come from the
ontology/policy-backed concept spec or the inferred generic metric label.

## 7. Ontology-Driven Prose Lookup Slots

When a concept lookup obtains the required numeric value from prose rather than
from a structured table row, the runtime contract is:

- use ontology aliases and `surface_contract.positive` terms to locate the
  value in the answer/evidence text
- synthesize a normal `answer_slots.primary_value` record with concept, role,
  period, rendered value, normalized value, and provenance
- promote the retrieved source document containing that value into
  `runtime_evidence`
- compose aggregate difference answers from slot `rendered_value` fields when
  all operands are available

This keeps domain vocabulary in ontology/config while allowing deterministic
dependency binding and evaluator-visible grounding. Runtime code should not add
company-specific or benchmark-specific branches for these cases.

## 8. Retrieved Evidence Preservation For Calculation

Reconciliation is a candidate matcher, not the final authority on whether a
calculation can proceed. If reconciliation reports insufficient operands but the
active calculation subtask still has required operands and retrieved documents,
the graph must route through operand extraction once before advancing or
abstaining.

The operand extractor may promote retrieved raw chunks into calculation evidence
when all of these are true:

- the active task is not a direct numeric lookup that requires structured
  grounding
- the retrieved chunk carries text that matches the required operand surfaces
  from the task/ontology contract
- the extracted value remains attached to the source chunk metadata and evidence
  id

This rule prevents lossy evidence summaries from hiding values that retrieval
already found. It does not permit benchmark-specific fallback answers: extracted
rows still have to satisfy the generic required-operand matcher, unit
normalization, period checks, and provenance checks.

When graph expansion adds parent, table-context, sibling, or other structural
documents, the expanded `retrieved_docs` window can crowd out a raw seed chunk
that contains the required numeric sentence. The calculation path must treat
`seed_retrieved_docs` as eligible candidate evidence for required-operand
extraction, as long as the same generic matcher/provenance/unit checks pass.
Do not recover these chunks by company name, benchmark id, or topic-specific
keywords in runtime code.

When structured table metadata provides both `table_row_labels_text` and row
records, operand precision refinement must prefer the structured cell from the
same matched row label before considering nearby previous rows. Previous-row
fallback is only for explanatory rows that name an operand but carry no value
cell themselves. This avoids binding a requested metric such as cost of sales
to the value from an adjacent revenue row.

If the source text already states a derived display value, such as a
year-over-year percentage next to the current and prior values, the runtime
should preserve that source-stated display in `calculation_result.rendered_value`
and answer slots when it is attached to the same evidence. The deterministic
formula result should remain traceable, for example in `derived_metrics`, when
it differs because the source rounded or displayed the value at a different
precision.

## 9. Aggregate Subtask Projection

Aggregate answers must keep child task provenance visible after the final
projection. Each item in `answer_slots.subtask_results` should expose:

- `task_id`: child task identifier
- `operation_family`: child operation family, copied from the child task,
  answer slots, or calculation result
- `source_row_ids`: cleaned source row ids used by the child result
- `source_evidence_ids`: cleaned evidence item ids used by the child result,
  especially for narrative or prose-only child tasks that do not resolve to a
  structured numeric row
- `calculation_result`: child calculation result when available
- `answer_slots`: child answer slots when available

`source_row_ids` may include deterministic dependency references such as
`task_output:<task_id>` together with structured row/evidence ids, but it must
not contain display-only placeholders such as `"None"`. Runtime code should
derive these fields from existing task, slot, trace, and evidence artifacts.
It must not infer them from company names, benchmark ids, or topic-specific
keywords.

`source_evidence_ids` is not a replacement for `source_row_ids`. Numeric and
structured lookup children should keep row/candidate provenance in
`source_row_ids`; narrative children should keep retrieved evidence ids in
`source_evidence_ids` when the child answer is grounded in prose evidence but
has no structured row id.

The purpose of this projection is traceability: evaluator, citation, and
debugging paths should be able to inspect the same child operation, source
rows, and source evidence ids that the aggregate composer used. If a child
value came from prose lookup or retrieved seed evidence, the promoted evidence
id/source row id should stay attached through the aggregate projection rather
than disappearing during final answer synthesis.
