# Architecture Direction

이 문서는 `dart-rag-agent`를 **DART 도메인 위의 multi-agent financial analysis lab**으로 재구성하기 위한 방향성을 정리한다.

핵심 메시지는 단순하다.

- 기존 single-agent graph와 evaluator 자산은 버리지 않는다
- 대신 그것을 **Orchestrator / Analyst / Researcher / Critic** 역할로 분해한다
- 의미 해석은 LLM에게, 실행/계산/grounding은 deterministic code에 맡긴다

## Executive Summary

| 질문 | 현재 답 |
| --- | --- |
| 지금 목표는 single-agent pipeline 최적화인가? | 아니다 |
| full MAS로 방향을 틀어도 되는가? | 된다. 다만 단계적으로 간다 |
| 기존 자산은 버리나? | 아니다. Analyst / Researcher / Critic 자산으로 이식한다 |
| 가장 먼저 고정할 것은 무엇인가? | topology, shared state, communication contract |

> 현재 단계의 핵심은 “더 많은 patch”가 아니라 **MAS skeleton과 agent boundary를 명확히 하는 것**이다.

## Why MAS Now

초기 단계에서 single-agent structured pipeline을 먼저 만든 판단은 틀리지 않았다.  
그 덕분에 아래 자산이 쌓였다.

| 자산 | 현재 상태 |
| --- | --- |
| DART structure parser | 안정적 |
| hybrid retrieval | 안정적 |
| parent-child / graph expansion | 안정적 |
| formula planner + safe AST | 안정적 |
| operand grounding evaluator | 안정적 |
| benchmark / replay infra | 안정적 |

이제 남은 질문은 “단일 파이프라인을 조금 더 미세 조정할까?”가 아니라:

- 어떤 작업을 어떤 agent에게 맡길까
- agent가 어떤 artifact를 생성해야 할까
- critic이 무엇을 기준으로 결과를 반려할까
- memory/cache를 어느 계층에 둘까

이다.  
즉 **문제의 중심이 시스템 설계로 이동했기 때문에** MAS로 전환할 시점이다.

## Target Topology

```text
User Query
  -> Orchestrator
      -> Analyst Agent   ----\
      -> Research Agent  -----+-> Critic Stack -> Orchestrator Merge -> Final Report
      -> Cache / State   -----/
```

### Logical Agents

| Agent | 핵심 책임 | 맡기지 않을 일 |
| --- | --- | --- |
| Orchestrator | query interpretation, task decomposition, assignment, final merge | 직접 retrieval/계산 |
| Analyst | 수치 추출, formula planning, 계산, numeric artifact 생성 | why/context 서술 |
| Researcher | 비정형 텍스트 탐색, why/context 요약, note traversal | 최종 numeric 계산 |
| Critic | grounding/binding/completeness/scope 검증 | 원문 검색 대행 |

## Communication Model

이 시스템은 agent 간 자유 텍스트 대화보다 **task ledger + artifact store**를 기본 통신 모델로 둔다.

### Shared State Principles

| 원칙 | 설명 |
| --- | --- |
| shared chat 지양 | 자유형 대화 로그 대신 typed artifact 위주 |
| task-first | 모든 agent work는 task 단위로 추적 |
| append-only artifacts | 각 agent는 결과를 state에 추가하고, 타 agent 결과를 덮어쓰지 않음 |
| critic-mediated acceptance | 최종 채택은 critic artifact를 거침 |

### Recommended State Shape

```python
class AgentState(TypedDict):
    original_query: str
    report_scope: ReportScope
    tasks: list[Task]
    task_results: dict[str, TaskResult]
    evidence_pool: list[EvidenceItem]
    critic_reports: list[CriticReport]
    final_report: str | None
    execution_trace: list[TraceEvent]
```

### Why Shared State Over Direct Messaging

| 이유 | 설명 |
| --- | --- |
| 재현성 | 어떤 agent가 어떤 artifact를 남겼는지 추적 가능 |
| 평가 용이성 | critic과 evaluator가 같은 구조화 결과를 읽을 수 있음 |
| benchmark 연결 | runtime trace와 offline scorecard를 자연스럽게 잇기 쉬움 |
| 포트폴리오 설명력 | “agent들이 무엇을 주고받는가”를 명확히 보여줄 수 있음 |

## Memory Model

이 프로젝트는 generic long-term memory보다 먼저 **report-scoped memory/cache**를 설계한다.

### Memory Layers

| 계층 | 용도 | 현재 판단 |
| --- | --- | --- |
| Graph State | 한 실행 안의 공유 상태 | 필수 |
| Report-scoped cache | 같은 보고서 안에서 재사용 가능한 metric/value | 우선 구현 대상 |
| Benchmark artifacts | 회고 실험 / 재현성 | 이미 강함 |
| Long-term user memory | 사용자별 지속 메모리 | 현재 우선순위 아님 |

### Report-scoped Cache Key

권장 키는 아래처럼 충분히 좁게 잡는다.

| 필드 | 이유 |
| --- | --- |
| `company` | 기업 구분 |
| `report_type` | 사업보고서/분기보고서 구분 |
| `rcept_no` | 실제 보고서 인스턴스 구분 |
| `year` | 기간 구분 |
| `consolidation` | 연결/별도 구분 |
| `metric` | 재무 지표 구분 |
| `source_section` | 출처 추적 |

## Tool Ownership

agentic하게 만들더라도 모든 것을 LLM에게 맡기지 않는다.

### LLM-owned work

| 범주 | 예시 |
| --- | --- |
| semantic planning | task decomposition, retry objective 판단 |
| reformulation | retrieval-friendly subquery 생성 |
| interpretation | evidence 압축, why/context 요약 |
| critique opinion | scope overreach, coherence, acceptance opinion |

### Deterministic work

| 범주 | 예시 |
| --- | --- |
| retrieval execution | vector search, BM25, RRF, metadata filters |
| graph expansion | parent/sibling/reference traversal |
| numeric execution | AST calculator |
| grounding checks | operand grounding, unit checks |
| control flow | bounded retry, route gating, merge policy |

> 원칙: **LLM은 semantics, code는 execution**.

## Critic Architecture

Critic은 하나의 막연한 judge보다 **2층 구조**가 적합하다.

| Layer | 역할 |
| --- | --- |
| Deterministic Critic | operand grounding, unit consistency, entity/period binding, task coverage |
| LLM Critic | relevance, scope overreach, coherence, acceptance opinion |

이렇게 하면:
- 수치/바인딩 오류는 deterministic하게 잡고
- 서술 범위 문제는 LLM이 판단하게 할 수 있다

## Capability Placement

`REFERENCE_NOTE`, self-reflection, cross-company는 더 이상 메인 로드맵 자체가 아니라 **MAS 안으로 편입될 capability**로 본다.

| Capability | 어느 agent에 붙는가 |
| --- | --- |
| `REFERENCE_NOTE` | 주로 Researcher retrieval capability |
| ontology-guided retrieval | Analyst / Researcher query planning input |
| bounded self-reflection | Orchestrator + Critic mediation이 있는 retry behavior |
| cross-company reasoning | Orchestrator namespace planning + Analyst binding |

## Migration From Current Code

현재 코드베이스는 single-agent graph 중심이지만, 아래처럼 읽으면 MAS로 자연스럽게 옮길 수 있다.

| 현재 자산 | 미래 역할 |
| --- | --- |
| `financial_graph.py` retrieval/evidence path | Researcher proto-path |
| `financial_graph.py` formula planner / calculator | Analyst proto-path |
| `calc_verify`, evaluator grounding logic | Critic proto-logic |
| benchmark / retrospective replay | offline critic / scorecard layer |

즉 지금 할 일은 “새 시스템을 완전히 다시 쓰는 것”보다,  
**이미 있는 강한 자산을 어떤 agent의 책임으로 이동시킬지 결정하는 것**이다.

## Recommended Build Order

| 순서 | 목표 |
| --- | --- |
| 1 | MAS skeleton과 typed state schema 고정 |
| 2 | Orchestrator가 single-task / multi-task를 모두 다루는 뼈대 구성 |
| 3 | Analyst migration |
| 4 | Critic deterministic layer 분리 |
| 5 | Researcher attachment |
| 6 | bounded self-reflection을 MAS behavior로 재설계 |
| 7 | cross-document / cross-company 확장 |

## Out of Scope for This Phase

| 항목 | 지금 제외하는 이유 |
| --- | --- |
| unrestricted autonomous agents | 통제/재현성이 떨어짐 |
| direct agent-to-agent free chat | artifact 추적이 어려움 |
| generic long-term memory | report-scoped cache보다 우선순위가 낮음 |
| full knowledge graph database | 현재 목표 대비 과도함 |
| metric gaming용 local patch | topology 설계보다 우선순위가 낮음 |

## Current Conclusion

현재 가장 적절한 방향은:

1. single-agent pipeline을 계속 patch하는 것이 아니라
2. existing assets를 **Analyst / Researcher / Critic**로 분해하고
3. Orchestrator와 shared state contract를 먼저 고정한 뒤
4. self-reflection과 note traversal을 capability로 편입하는 것이다

즉 앞으로의 방향은 “더 큰 RAG”가 아니라,  
**DART 도메인을 이용해 multi-agent systems의 topology, communication, memory, tool boundary를 검증하는 구조**다.
