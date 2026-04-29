# Architecture Direction

이 문서는 현재 DART 공시 QA 시스템의 구조적 한계를 정리하고, 앞으로 어떤 방향으로 아키텍처를 바꾸는 것이 적절한지를 설명한다.

## Executive Summary

| 질문 | 현재 답 |
| --- | --- |
| 지금 문제를 해결하기 위해 full GraphRAG가 필요한가? | 아직은 과함 |
| full multi-agent system으로 가는 것이 맞는가? | 아직은 과함 |
| 그 대신 무엇이 필요한가? | document-structure graph + structured evidence + compression / validation |

> 현재 단계에서는 **full GraphRAG / full multi-agent보다, document-structure graph + structured evidence + answer compression/validation 구조가 더 적합하다.**

숫자 질문(`numeric_fact`)의 평가는 일반 서술형 `faithfulness` judge 하나에 의존하지 않고, 별도의 **parallel numeric evaluators + resolver** 구조로 분리하는 것이 바람직하다. 자세한 설계는 [numeric_evaluation_architecture.md](numeric_evaluation_architecture.md)를 참고한다.

## Current Pipeline

| 단계 | 현재 구현 |
| --- | --- |
| 1 | DART XML 파싱 |
| 2 | structure-first chunking |
| 3 | hybrid retrieval (`dense + BM25 + RRF`) |
| 4 | evidence extraction |
| 5 | answer generation |
| 6 | citation formatting |

이미 있는 강한 기반:

- parent-child retrieval
- section/path metadata
- table / paragraph block type
- evidence-first reasoning
- benchmark / canonical eval dataset

즉 완전히 밑바닥부터 새로 만드는 상황은 아니다.

## Problem Diagnosis

| 관찰 | 해석 |
| --- | --- |
| `hit@k`, `section_match_rate`, `context_recall`은 유지되는데 `faithfulness`만 흔들림 | retrieval보다 generation 문제가 클 가능성 |
| evidence는 있는데 answer에서 taxonomy 재구성 / 배경 확장 / 숫자 표현 drift 발생 | answer generation이 자유 서술에 과도하게 의존 |
| query-type별 bias / output style / post-generation guard가 늘어남 | local optimization이 누적되고 있음 |

## Why Not Full GraphRAG Yet

### Full GraphRAG가 특히 강한 경우

| 상황 | 설명 |
| --- | --- |
| 여러 문서 간 entity relation이 핵심일 때 | 회사/이벤트/인물/거래 관계 추적 |
| 복수 회사 / 복수 연도 연결이 중요할 때 | cross-document reasoning 중심 |
| “누가 누구와 어떤 관계인지”를 추적해야 할 때 | explicit relation graph가 강함 |

### 지금 과한 이유

| 이유 | 설명 |
| --- | --- |
| 현재 주요 실패와 mismatch | entity relation missing보다 answer over-generation이 더 큰 문제 |
| 새로운 오류면 증가 | entity extraction, relation extraction, graph maintenance, sync 복잡도 |
| evaluation 복잡도 증가 | 현재 benchmark 해석이 더 어려워질 수 있음 |

즉 지금 당장 full GraphRAG로 가면, 현재 문제를 해결하기 전에 새로운 실패면을 더 많이 만들 가능성이 크다.

## Why Not Full Multi-agent Yet

### Multi-agent의 장점

| 장점 | 설명 |
| --- | --- |
| planner / retriever / writer / verifier 역할 분리 | 실패 원인 분해가 쉬움 |
| 각 단계 독립 개선 가능 | 모듈화 |

### 지금 과한 이유

| 이유 | 설명 |
| --- | --- |
| 이미 LangGraph 기반 단계적 구조가 있음 | `classify -> extract -> retrieve -> evidence -> analyze -> cite` |
| 필요한 것은 agent 수 증가보다 structured I/O | 노드 입출력 구조화, answer generation 제약, validation 분리 |

즉 **multi-agent화**보다 **structured pipeline화**가 우선이다.

## Recommended Direction

### 1. Document-Structure Graph

full knowledge graph 대신 먼저 **document-structure graph**를 도입하는 것이 적절하다.

#### 노드 / 엣지

| 범주 | 구성 |
| --- | --- |
| 노드 | section, chunk, table, paragraph, note / footnote |
| 엣지 | `parent_of`, `child_of`, `adjacent_to`, `precedes`, `describes_table`, `belongs_to_section`, `same_parent` |

#### 기대 효과

| 효과 | 설명 |
| --- | --- |
| retrieval 후 구조 확장 | similarity 외 구조적 이웃 활용 |
| table 질문 보강 | preceding paragraph를 안정적으로 결합 |
| answer grounding 구분 | 직접 근거와 배경 근거 분리 용이 |

현재 1차 구현은 full graph가 아니라 **retrieval 후 후처리 확장용 최소 구조 그래프**다.

- `parent_id` 기반 parent context
- 같은 `parent_id` 안에서의 `sibling_prev` / `sibling_next`
- parser가 이미 보존하던 `table_context`

### 2. Structured Evidence Schema

현재 evidence는 사실상 bullet 문자열에 가깝다. 이를 더 구조화하는 것이 핵심이다.

상세 스키마 초안은 [evidence_schema.md](evidence_schema.md)를 참고한다.

예시:

```json
{
  "claim": "DX 부문은 TV, 모니터, 냉장고, 세탁기 등을 생산·판매한다.",
  "quote_span": "Set 사업은 DX(Device eXperience) 부문이 TV를 비롯하여...",
  "source_anchor": "[삼성전자 | 2024 | II. 사업의 내용 > 1. 사업의 개요]",
  "support_level": "direct",
  "allowed_terms": ["DX", "TV", "모니터", "냉장고", "세탁기"],
  "question_relevance": "high"
}
```

핵심은 answer가 free-form generation이 아니라, 이 structured evidence를 **질문 범위에 맞게 압축하는 단계**가 되도록 만드는 것이다.

### 3. Answer Compression + Validator

현재 `_analyze`는 여전히 “답을 써라”에 가깝다. 앞으로는 다음 두 단계로 나누는 것이 좋다.

| 단계 | 역할 | 하지 말아야 할 것 |
| --- | --- | --- |
| Compression | evidence 집합에서 질문에 필요한 claim만 선택하고 짧게 정리 | 새로운 설명 생성 |
| Validator | unsupported sentence 제거, taxonomy / numeric drift 탐지, duplicated claim 제거 | 새 내용을 추가하는 것 |

중요한 점은 validator가 “새 내용을 쓰는 단계”가 아니라는 것이다. validator는 제거/축소만 해야 한다.

## Target Pipeline

```text
classify
  -> extract
  -> retrieve
  -> expand_via_structure_graph
  -> [intent == numeric_fact] -> numeric_extractor -> cite
  -> [그 외]                  -> build_structured_evidence
                               -> compress_answer
                               -> validate_answer
                               -> cite
```

기존 구조와의 차이:

| 변화 | 의미 |
| --- | --- |
| `retrieve` 뒤에 구조 그래프 기반 확장 계층 추가 | structure-aware retrieval 강화 |
| `evidence`는 bullet 생성이 아니라 structured object 생성 | 근거 구조화 |
| `analyze`는 free-form generation이 아니라 compression | over-generation 억제 |
| validation은 별도 계층으로 분리 | 후단 안정화 |

## Migration Plan

| Phase | 범위 | 목표 |
| --- | --- | --- |
| Phase 1 | Evidence schema 도입 | answer generation과 evaluation이 같은 evidence 구조를 보게 만들기 |
| Phase 2 | Answer compression 도입 | “더 많이 말하는 문제”를 구조적으로 줄이기 |
| Phase 3 | Validator 계층 분리 | generation prompt 제약 누적 대신 후단 안정화 |
| Phase 4 | Document-structure graph 확장 | full GraphRAG 없이도 문서 구조를 더 잘 활용 |

## Out of Scope for Now

| 항목 | 지금 제외하는 이유 |
| --- | --- |
| full entity knowledge graph 구축 | 현재 문제 대비 비용이 큼 |
| company-wide graph database 도입 | 운영 복잡도 증가 |
| full multi-agent orchestration | 지금은 structured pipeline이 더 적합 |
| 모든 benchmark 문항을 맞추기 위한 rule 추가 | metric gaming 위험 |

## Current Conclusion

현재 시점에서 가장 적절한 구조 변화는 다음 세 가지다.

1. full GraphRAG가 아니라 **document-structure graph**
2. full multi-agent가 아니라 **structured pipeline**
3. rule accumulation이 아니라 **structured evidence + compression + validation**

즉 앞으로의 방향은 “더 큰 시스템”이 아니라, **지금 있는 시스템을 더 설명 가능하고 구조화된 형태로 리팩터링하는 것**이다.
