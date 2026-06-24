# Technical Highlights

이 문서는 reviewer-facing 핵심 기술 요약이다. 상세 실험 로그는
[project_status.md](project_status.md),
[../evaluation/benchmarking.md](../evaluation/benchmarking.md),
[../history/experiment_history.md](../history/experiment_history.md)에 둔다.

독자는 RAG, embedding retrieval, agent workflow, grounding/evaluation에
익숙하다고 가정한다. `neuro-symbolic`, `ontology`, `grounding`,
`agentic` 같은 용어는 repo의 구체적인 state field, policy file, evaluator,
gate와 연결해서만 사용한다.

## 1. Structure-Aware DART Ingestion

일반 웹문서 splitter 대신 DART XML의 문서 구조를 복원한다.

핵심 surface:

- `SECTION-*`, `TITLE`, `P`, `TABLE`, `TABLE-GROUP` parsing
- `section_path`, block type, table context metadata
- high-value section에만 보수적인 `local_heading` 복원
- wide table의 `column_window`, `row_window`, `column_row_window` split
- narrative-heavy table row의 추가 split

의미:

- 공시 문서는 표, 섹션, 주석 문맥이 답의 일부다.
- retrieval chunk가 semantic하게 비슷해도 row/period/table context가 틀리면
  numeric QA는 실패한다.

## 2. Value-Cell-First Table Metadata

표를 row text로만 펴지 않고, 값 셀 중심의 structured metadata로 정규화하는
방향으로 이동했다.

핵심 surface:

- parser가 `table_value_records_json` 생성
- 각 값 셀에 `semantic_label`, `row_headers`, `column_headers`,
  `aggregate_label`, `aggregate_role`, `period_text`, `unit_hint` 저장
- unit-only standalone table을 다음 실제 표의 context hint로 승격
- runtime은 value record에서 `structured_value` reconciliation candidate를
  만들고 direct operand extraction에 사용

의미:

- merged header / multi-period note table에서 row label만으로는 부족하다.
- 현재 claim은 "cell-level embedding"이 아니라 **value-cell-first structured
  metadata**다.
- historical hard structural replay의 `SKH_T1_060`은 이 차이를 보여준다.
  plain retrieval은 prior-period borrowing table의
  `3,833,263 + 9,073,567 + 6,497,790`을 numerator로 묶었고, structural path는
  current-period table의 `4,145,647 + 10,121,033 + 9,490,410`을 보존했다.
  최신 PR #78 refresh에서는 같은 case가 `42.02%`로 닫혔다. 핵심 교훈은
  structural metadata만으로 끝나지 않고, period-prefixed operand label을
  table row label과 맞추는 table-label lookup과 disjoint-source operand
  protection까지 trace contract에 포함해야 한다는 점이다.

## 3. LLM Semantics, Deterministic Execution

숫자 질문은 free-form generation이 아니라 계획, 근거, 실행, 렌더링을 분리한다.

핵심 surface:

- LLM: intent, concept, narrative meaning, formula planning support
- code: arithmetic, unit handling, dependency binding, dedupe, ordering,
  validation
- numeric state: `answer_slots`, `structured_result`,
  `resolved_calculation_trace`
- execution path: `formula planner -> safe AST calculator -> grounded renderer`

Retrospective numeric-only architecture comparison:

| Path | Strict correctness |
| --- | ---: |
| direct LLM calculation baseline | `0.556` |
| formula planner + AST executor | `1.000` |

의미:

- `neuro-symbolic`은 새 알고리즘 이름이 아니라, LLM semantic planning과
  deterministic numeric execution의 역할 분리를 설명하는 shorthand다.
- arithmetic hallucination을 "완전히 제거"했다고 주장하지 않고, 산술/단위
  실행을 free-form generation 밖으로 옮겼다고 설명한다.

## 4. Required-Operand Grounding

재무 비율/차이/증감률은 최종 숫자만 맞아도 충분하지 않다. 필요한 operands가
올바른 source/table/period에서 왔는지 검증해야 한다.

핵심 surface:

- reconciliation candidates: `chunk`, `structured_row`, `table_row`,
  `evidence_row`, `structured_value`
- scoring signals: row label match, statement type, period, scope, table
  source, numeric value signal
- same-table current/prior pairing
- source-visible display preservation
- fallback보다 direct numeric grounding을 우선하는 lookup/difference/ratio
  contracts

KAB CIR repair에서 닫힌 failure:

- denominator가 다른 financial statement surface의 plausible row로 묶임
- operation-like substring이 metric label 안에 있어 correct lookup이
  over-blocked됨
- calculation trace는 맞지만 final prose가 stale lookup display를 사용함

최종 answer:

```text
2023년 CIR은 37.47%입니다. 계산: 판매비와관리비 4,355억원 / 경비차감전영업이익 11,623억원.
```

두 operand 모두 `IV. 이사의 경영진단 및 분석의견::table:3`에서 온다.

Hard replay row-binding evidence:

| Case | Structural | Plain | Technical read |
| --- | --- | --- | --- |
| `SKH_T1_060` | `42.02%`, borrowing rows from `period_focus=current`, `["당기"]` | `34.32%`, borrowing rows from `period_focus=prior`, `["전기"]` | Formula execution was deterministic in both paths; the failure layer was period-aware row binding. |

Latest PR #78 repair adds a second lesson on top of this historical separator:
even when task-output operands are correct, a later direct-evidence repair can
corrupt the aggregate if it ignores source-row provenance. The current runtime
therefore protects task-output source slots from disjoint conflicting direct
rows and syncs final-answer numeric surfaces back into public calculation
projection.

## 5. Artifact-Ledger Agent Runtime

agentic workflow는 자유 채팅 transcript가 아니라 typed ledger state로 유지한다.

핵심 surface:

- `Orchestrator -> Analyst / Researcher -> Critic -> Merge`
- shared state: `tasks`, `artifacts`, `evidence_pool`, `critic_reports`,
  `task_artifact_trace`
- `Analyst`: numeric extraction, formula planning, calculation
- `Researcher`: narrative/context retrieval
- `Critic`: grounding, target refs, acceptance reasons, blocking issues
- `Orchestrator`: decomposition and final merge

의미:

- agent handoff는 "agent가 생각했다"가 아니라 artifact contract로 검토된다.
- final answer text는 presentation layer이고, reviewer-facing contract는 trace와
  artifact integrity다.

## 6. Bounded Reflection And Critic Acceptance

retry/reflection은 final answer authority가 아니라 budgeted handoff artifact다.

핵심 surface:

- `ReflectionRequest -> ReflectionPlan -> ReflectionAction -> ReflectionReport`
- `reflection_report` artifact records retry action, budget use, targets, and
  blocking issues
- critic acceptance checks verdict, target refs, reasons, and blocking issues
- rejected critic reports can block final close even when a diagnostic score is
  high

의미:

- generic Reflexion/ReAct claim이 아니라, bounded retry contract다.
- LLM critic은 아직 final acceptance authority로 쓰지 않는다.

## 7. Evaluation Is Trace-Based

RAGAS-style metrics are useful as generic baseline signals, but this project
needs numeric QA metrics that inspect internal runtime state.

핵심 metrics:

- `numeric_equivalence`
- `numeric_grounding`
- `numeric_retrieval_support`
- `numeric_final_judgement`
- `calculation_correctness`
- faithfulness / completeness / context recall / retrieval hit@k
- task/artifact integrity
- critic acceptance
- grounded rendering correctness

의미:

- final answer exact match만으로는 wrong operand, wrong unit, stale display를
  잡기 어렵다.
- evaluator는 operands, formula, source references, and rendered displays를
  함께 본다.

## 8. Structural Selective Ingestion For Cost/Quality

LLM-written chunk context를 많이 붙이는 것이 유일한 해법은 아니다.

비교 해석:

| Method | Role | Interpretation |
| --- | --- | --- |
| `plain_prefix_8000_400` | speed/cost baseline | representative runtime-contract row를 놓침 |
| `contextual_selective_v2_prefix_2500_320` | historical quality baseline | quality reference지만 selected chunks에 LLM-written context 필요 |
| `structural_selective_v2_prefix_2500_320` | current operating default | deterministic structural prefix로 gate 품질 유지 |

핵심 surface:

- ingest-time prefix markers: `[섹션]`, `[분류]`, `[키워드]`
- parser/config/policy-managed section/category aliases
- `statement_type`, `consolidation_scope`, `period_focus`, `table_context`,
  `table_row_labels_text`

의미:

- 핵심은 semantic summary의 양이 아니라, 어떤 구조 신호를 어떤 chunk와
  evidence state에 남기느냐다.
- historical hard replay에서는 ontology/runtime fixes 덕분에 plain도
  `4 / 5` hard numeric questions를 통과했다. 최신 structural refresh는
  9문항에서 `9 / 9` numeric PASS이고, 가장 최근 plain comparison은 `5 / 9`
  diagnostic baseline으로 남아 있다. 현재 structural-selective claim은
  broad leaderboard가 아니라 display/denominator/row-binding failure taxonomy
  and trace-contract repair story로 제시해야 한다.

## 9. Runtime/API Cost Control

품질 gate를 유지하면서 query fanout과 provider calls를 관찰/축소한다.

핵심 surface:

- executed retrieval-query count
- duplicate query signatures
- query-embedding calls and input volume
- LLM call count
- estimated runtime cost
- exact-text query embedding cache
- same-trace duplicate guard

대표 evidence:

- KAB CIR final focused run: `2` executed queries, `0` duplicate executed
  queries, `8` agent LLM calls, estimated runtime cost `$0.056292`
- policy-gate replay after exact-text embedding cache preserved core metrics at
  `1.000` while lowering observed query/API pressure

의미:

- 비용 최적화는 evidence를 숨기는 dedupe가 아니라, trace를 유지한 상태에서
  불필요한 query/API fanout을 줄이는 방향이어야 한다.
